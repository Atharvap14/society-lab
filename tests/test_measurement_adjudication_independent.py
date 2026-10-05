"""Independent temporary-registry tests of bounded measurement adjudication.

No production records, raw source files or provider calls are used. A current
pinned regex consistency check uses authored retained registry rows only.
Resealed fixture bodies test local consistency, not cryptographic truth.
"""
import concurrent.futures
import copy
import hashlib
import json
from pathlib import Path
import random
import tempfile
import threading
import unittest
from unittest.mock import patch

from swarm_lab.dataset import normalize_message
from swarm_lab.store import Store, StoreConflictError, fingerprint, now


from swarm_lab import measurement_adjudication as module


def pin(row):
    return {key: row[key] for key in ('id', 'version', 'hash')}


class ReadOnlyCopies:
    def __init__(self, rows):
        self.rows = {(row['id'], row['version']): copy.deepcopy(row) for row in rows}

    def get(self, identity, version=None):
        if version is None:
            version = max(v for name, v in self.rows if name == identity)
        return copy.deepcopy(self.rows[identity, version])

    def put(self, *args, **kwargs):
        raise AssertionError('presentation must not write')

    def compare_and_put(self, *args, **kwargs):
        raise AssertionError('presentation must not write')


class AdjudicationIndependentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = Store(Path(self.directory.name) / 'temporary.sqlite3')
        self.messages = [normalize_message({
            'id': 'message-%02d' % index,
            'agent_speaker_id': 'actor-a' if index % 2 else None,
            'user_speaker_id': None if index % 2 else 'user-a',
            'speaker_type': 'agent' if index % 2 else 'user',
            'agent_name': 'Agent A' if index % 2 else 'User A',
            'room_id': 'room-a' if index < 8 else 'room-b',
            'created_at': '2025-04-22T18:%02d:00Z' % index,
            'content': ('I am waiting for the draft.' if index % 3 == 0 else
                        'The next step is ordinary work.'),
            'source': {'file': 'authored-fixture.jsonl', 'line': index + 1,
                       'table': 'chat_messages'},
        }) for index in range(12)]
        self.dataset = self.store.put('dataset', {'messages': self.messages}, 'dataset-fixture')

    def sample(self, **changes):
        args = {'question': 'Does this message explicitly report waiting?',
            'positive_definition': 'The author reports waiting on a named dependency.',
            'negative_definition': 'The author does not explicitly report that act.',
            'sample_size': 6, 'seed': 42, 'context_neighbors': 1}
        args.update(changes)
        return module.create_sample(self.store, pin(self.dataset), **args)

    def review(self, sample, version=None):
        return self.store.get(sample['payload']['review_id'], version)

    def judgment(self, sample, message_id, label, version, **changes):
        args = {'reason': 'Declared fixture annotation.', 'reviewer_id': 'reviewer-a',
                'reviewer_mode': 'synthetic_fixture', 'expected_review_version': version}
        args.update(changes)
        return module.record_judgment(self.store, pin(sample), message_id, label, **args)

    def copies(self, sample):
        return ReadOnlyCopies([self.dataset, sample, self.review(sample, 1)])

    def reseal_sample(self, sample, change):
        rows = self.copies(sample)
        changed = copy.deepcopy(sample)
        change(changed['payload'])
        changed['hash'] = fingerprint(changed['payload'])
        rows.rows[changed['id'], changed['version']] = changed
        review = self.review(sample, 1)
        review['payload']['sample_ref'] = pin(changed)
        review['hash'] = fingerprint(review['payload'])
        rows.rows[review['id'], review['version']] = review
        return rows, changed, review

    def test_draw_is_canonical_seeded_without_replacement_not_detector_selected(self):
        sample = self.sample(detector_id='blocker_report')
        expected = random.Random(42).sample(sorted(row['id'] for row in self.messages), 6)
        self.assertEqual(sample['payload']['design']['draw_order'], expected)
        self.assertEqual(len(expected), len(set(expected)))
        self.assertEqual(sample['payload']['design']['population_speaker_type_counts'], {'agent':6, 'user':6})
        reordered = self.store.put('dataset', {'messages': list(reversed(self.messages))}, 'reordered-dataset')
        old = self.dataset
        self.dataset = reordered
        again = self.sample(detector_id='blocker_report')
        self.dataset = old
        self.assertEqual(again['payload']['design']['draw_order'], expected)
        self.assertEqual(again['payload']['items'], sample['payload']['items'])

    def test_source_context_is_same_room_bounded_and_full_content_hash_is_explicit(self):
        sample = self.sample(sample_size=12, context_neighbors=2)
        for item in sample['payload']['items']:
            source = next(row for row in self.messages if row['id'] == item['message_id'])
            self.assertEqual(item['source_record']['full_content_utf8_sha256'], hashlib.sha256(source['content'].encode()).hexdigest())
            self.assertEqual(item['source_record']['declared_message_content_hash'], source['content_hash'])
            for side in ('before', 'after'):
                self.assertLessEqual(len(item['context'][side]), 2)
                self.assertTrue(all(row['room_id'] == source['room_id'] for row in item['context'][side]))

    def test_duplicate_population_ids_fail_before_a_sample_is_persisted(self):
        self.dataset = self.store.put('dataset', {'messages': self.messages + [copy.deepcopy(self.messages[0])]}, 'duplicates')
        with self.assertRaises(ValueError):
            self.sample()
        self.assertEqual(self.store.list('measurement_sample'), [])

    def test_typed_bounds_and_no_arbitrary_detector(self):
        for args in ({'seed':True}, {'seed':42.0}, {'sample_size':True}, {'sample_size':6.0},
                     {'sample_size':0}, {'sample_size':33}, {'context_neighbors':True},
                     {'context_neighbors':3}, {'detector_id':'arbitrary-regex'},
                     {'exclusions':['same', 'same']}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.sample(**args)
        for version in (True, 1.0, 0):
            ref = pin(self.dataset); ref['version'] = version
            with self.subTest(version=version), self.assertRaises(ValueError):
                module.create_sample(self.store, ref, question='Question', positive_definition='Yes', negative_definition='No', sample_size=2)

    def test_exact_dataset_version_remains_used_after_unrelated_latest_version(self):
        sample = self.sample()
        self.store.put('dataset', {'messages': self.messages[:2]}, self.dataset['id'])
        review = self.review(sample, 1)
        packet = module.sample_packet(self.store, pin(sample), pin(review))
        self.assertEqual(packet['dataset_ref'], pin(self.dataset))
        self.assertEqual(packet['design']['population_size'], 12)

    def test_missing_and_uncertain_are_not_negative_confusion_cases(self):
        sample = self.sample(sample_size=4, detector_id='blocker_report')
        identities = sample['payload']['design']['draw_order']
        self.judgment(sample, identities[0], 'yes', 1)
        self.judgment(sample, identities[1], 'no', 2)
        review = self.judgment(sample, identities[2], 'uncertain', 3)
        report = module.review_report(self.store, pin(sample), pin(review))
        self.assertEqual(report['totals']['known_labels'], 2)
        self.assertEqual(report['totals']['uncertain_labels'], 1)
        self.assertEqual(report['totals']['missing_labels'], 1)
        self.assertEqual(report['totals']['compared_messages'], 2)
        self.assertEqual(sum(report['metrics']['confusion'].values()), 2)
        self.assertEqual(report['metrics']['agreement']['denominator'], 2)

    def test_no_detector_or_no_known_labels_has_none_not_zero_accuracy(self):
        for detector in (None, 'blocker_report'):
            sample = self.sample(sample_size=2, detector_id=detector)
            identity = sample['payload']['design']['draw_order'][0]
            review = self.judgment(sample, identity, 'uncertain', 1)
            report = module.review_report(self.store, pin(sample), pin(review))
            self.assertFalse(report['metrics']['available'])
            for key in ('confusion', 'agreement', 'precision', 'recall'):
                self.assertIsNone(report['metrics'][key])
            self.assertEqual(report['totals']['compared_messages'], 0)

    def test_latest_declaration_preserves_conflicts_and_mixed_declared_modes(self):
        sample = self.sample(sample_size=2, detector_id='blocker_report')
        identity, second = sample['payload']['design']['draw_order']
        first = self.judgment(sample, identity, 'yes', 1, reviewer_id='manual-a', reviewer_mode='manual_operator')
        self.judgment(sample, identity, 'uncertain', 2, reviewer_id='agent-a', reviewer_mode='agent_assisted', predictions_visible=True)
        review = self.judgment(sample, second, 'no', 3)
        report = module.review_report(self.store, pin(sample), pin(review))
        packet = module.sample_packet(self.store, pin(sample), pin(review))
        self.assertEqual(report['current_label_counts'], {'yes':0, 'no':1, 'uncertain':1, 'missing':0})
        self.assertEqual(report['current_labels_by_mode']['manual_operator']['yes'], 0)
        self.assertEqual(report['current_labels_by_mode']['agent_assisted']['uncertain'], 1)
        self.assertEqual(report['conflicting_declarations'][0]['labels'], ['uncertain', 'yes'])
        self.assertEqual(self.store.get(first['id'], first['version']), first)
        item = next(row for row in packet['items'] if row['message_id'] == identity)
        self.assertEqual(item['current_judgment']['label'], 'uncertain')
        self.assertEqual(item['prior_judgments'][0]['label'], 'yes')
        self.assertFalse(report['calibration_established'])
        self.assertIn('declared', report['reviewer_provenance'])
        self.assertIn('not consensus', report['scope'])
        self.assertIn('population accuracy', report['scope'])

    def test_stale_cas_and_concurrent_writers_preserve_one_authoritative_update(self):
        sample = self.sample(sample_size=2)
        first, second = sample['payload']['design']['draw_order']
        barrier = threading.Barrier(2)
        real_cas = self.store.compare_and_put
        def together(*args, **kwargs):
            barrier.wait(timeout=10)
            return real_cas(*args, **kwargs)
        def write(identity):
            try:
                return self.judgment(sample, identity, 'yes', 1)
            except StoreConflictError as error:
                return error
        with patch.object(self.store, 'compare_and_put', side_effect=together):
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(write, (first, second)))
        self.assertEqual(sum(isinstance(row, StoreConflictError) for row in results), 1)
        review = self.review(sample)
        self.assertEqual(review['version'], 2)
        self.assertEqual(len(review['payload']['judgments']), 1)
        with self.assertRaises(StoreConflictError):
            self.judgment(sample, second, 'no', 1)
        self.assertEqual(self.review(sample), review)

    def test_label_and_review_type_errors_leave_state_unchanged(self):
        sample = self.sample(sample_size=2)
        identity = sample['payload']['design']['draw_order'][0]
        for label, changes in ((False, {}), ('missing', {}), ('positive', {}),
                               ('yes', {'expected_review_version':True}),
                               ('yes', {'expected_review_version':1.0}),
                               ('yes', {'reviewer_mode':'human_verified'}),
                               ('yes', {'predictions_visible':1})):
            args = {'expected_review_version':1, **changes}
            version = args.pop('expected_review_version')
            with self.subTest(label=label, changes=changes), self.assertRaises(ValueError):
                self.judgment(sample, identity, label, version, **args)
            self.assertEqual(self.review(sample)['version'], 1)

    def test_default_predictions_are_hidden_and_visibility_is_not_authenticated_blinding(self):
        sample = self.sample(detector_id='blocker_report')
        review = self.review(sample, 1)
        packet = module.sample_packet(self.store, pin(sample), pin(review))
        self.assertTrue(all(row['prediction'] is None for row in packet['items']))
        self.assertFalse(packet['predictions_included'])
        self.assertFalse(packet['blinding_authenticated'])
        shown = module.sample_packet(self.store, pin(sample), pin(review), include_predictions=True)
        self.assertTrue(all(row['prediction']['available'] for row in shown['items']))
        with self.assertRaises(ValueError):
            module.sample_packet(self.store, pin(sample), pin(review), include_predictions=1)

    def test_resealed_draw_design_source_and_prediction_type_tampering_fail(self):
        sample = self.sample(detector_id='blocker_report')
        def reverse(p): p['design']['draw_order'].reverse()
        def population_bool(p): p['design']['population_size'] = True
        def source_text(p): p['items'][0]['source_record']['content'] = 'Changed after freezing.'
        def prediction_number(p):
            key = next(iter(p['predictions'])); p['predictions'][key]['value'] = 1
            p['predictions_sha256'] = module._sha(p['predictions'])
        for change in (reverse, population_bool, source_text, prediction_number):
            rows, changed, review = self.reseal_sample(sample, change)
            with self.subTest(change=change.__name__), self.assertRaises(ValueError):
                module.sample_packet(rows, pin(changed), pin(review))

    def reseal_prediction_in_temporary_store(self, sample, identity, prediction, declared_label):
        """A newly hashed sample/review is still constrained by its pinned operator."""
        body = copy.deepcopy(sample['payload'])
        body['predictions'][identity] = copy.deepcopy(prediction)
        body['predictions_sha256'] = module._sha(body['predictions'])
        changed = self.store.put('measurement_sample', body, sample['id'])
        review = self.review(sample, 1)
        body = copy.deepcopy(review['payload']); body['sample_ref'] = pin(changed)
        body['judgments'] = [{'sequence':1, 'message_id':identity, 'label':declared_label,
            'reason':'Declared synthetic test label.', 'reviewer_id':'fixture-a',
            'reviewer_mode':'synthetic_fixture', 'recorded_at':now(),
            'predictions_visible':False}]
        review = self.store.put('measurement_review', body, review['id'])
        return changed, review

    def test_resealed_real_regex_hit_cannot_be_removed_under_unchanged_operator_pin(self):
        sample = self.sample(sample_size=12, detector_id='blocker_report')
        identity = next(key for key, value in sample['payload']['predictions'].items() if value['value'] is True)
        changed, review = self.reseal_prediction_in_temporary_store(sample, identity,
            {'available':True, 'value':False, 'label':'no', 'spans':[], 'reason':None}, 'yes')
        self.assertEqual(changed['payload']['instrument'], sample['payload']['instrument'])
        with self.assertRaises(ValueError):
            module.review_report(self.store, pin(changed), pin(review))

    def test_resealed_arbitrary_source_substring_cannot_become_a_regex_hit(self):
        sample = self.sample(sample_size=12, detector_id='blocker_report')
        identity = next(key for key, value in sample['payload']['predictions'].items() if value['value'] is False)
        content = next(row['content'] for row in self.messages if row['id'] == identity)
        changed, review = self.reseal_prediction_in_temporary_store(sample, identity,
            {'available':True, 'value':True, 'label':'yes', 'spans':[{'start':0, 'end':3, 'text':content[:3]}], 'reason':None}, 'no')
        self.assertEqual(changed['payload']['instrument'], sample['payload']['instrument'])
        with self.assertRaises(ValueError):
            module.review_report(self.store, pin(changed), pin(review))

    def test_changed_dataset_body_cannot_be_borrowed_by_original_sample(self):
        sample = self.sample()
        rows = self.copies(sample)
        dataset = copy.deepcopy(self.dataset)
        dataset['payload']['messages'][0]['content'] = 'A source mutation.'
        dataset['hash'] = fingerprint(dataset['payload'])
        rows.rows[dataset['id'], dataset['version']] = dataset
        with self.assertRaises(ValueError):
            module.sample_packet(rows, pin(sample), pin(self.review(sample, 1)))

    def test_history_binding_cannot_move_review_to_different_sample(self):
        sample = self.sample()
        other = self.sample(seed=43)
        with self.assertRaises(ValueError):
            module.review_report(self.store, pin(sample), pin(self.review(other, 1)))
        rows = self.copies(sample)
        review = self.review(sample, 1)
        review['payload']['judgments'] = [{'invented': True}]
        review['hash'] = fingerprint(review['payload'])
        rows.rows[review['id'], review['version']] = review
        with self.assertRaises(ValueError):
            module.review_report(rows, pin(sample), pin(review))

    def test_current_rule_drift_retains_historical_predictions_without_detection_rerun(self):
        sample = self.sample(detector_id='blocker_report')
        review = self.review(sample, 1)
        before = copy.deepcopy(sample['payload']['predictions'])
        with patch.object(module._DISCOVERY_PATH.__class__, 'read_bytes', return_value=b'different fixed producer bytes'), \
             patch.object(module.discovery, 'detect_behaviors', side_effect=AssertionError('No current classifier rerun')):
            packet = module.sample_packet(self.store, pin(sample), pin(review), include_predictions=True)
            report = module.review_report(self.store, pin(sample), pin(review))
        self.assertFalse(packet['instrument']['current_code_matches'])
        self.assertEqual(packet['instrument']['predictions_scope'], 'frozen_historical_regex')
        self.assertEqual({row['message_id']:row['prediction'] for row in packet['items']}, before)
        self.assertFalse(report['instrument']['current_code_matches'])
        for output in (packet, report):
            instrument = output['instrument']
            self.assertFalse(instrument['cheap_operator_check_performed'])
            self.assertIsNone(instrument['saved_predictions_match_current_operator'])
            self.assertEqual(instrument['prediction_attestation'], 'historical_saved_predictions_unverified')
            self.assertFalse(instrument['historical_execution_attested'])

    def test_current_operator_consistency_uses_only_exact_retained_source_without_persistence(self):
        sample = self.sample(detector_id='blocker_report')
        rows = self.copies(sample)
        before = copy.deepcopy(rows.rows)
        original = module.discovery.detect_behaviors
        with patch.object(module.discovery, 'detect_behaviors', wraps=original) as screen:
            packet = module.sample_packet(rows, pin(sample), pin(self.review(sample, 1)))
            report = module.review_report(rows, pin(sample), pin(self.review(sample, 1)))
        self.assertGreaterEqual(screen.call_count, 2)
        selected_ids = set(sample['payload']['design']['draw_order'])
        for call in screen.call_args_list:
            self.assertEqual(set(row['id'] for row in call.args[0]), selected_ids)
            self.assertEqual(len(call.args), 1)
            self.assertEqual(call.kwargs, {})
            for row in call.args[0]:
                self.assertEqual(row, next(source for source in self.messages if source['id'] == row['id']))
        self.assertEqual(rows.rows, before)
        self.assertEqual(packet['model_calls'], 0)
        self.assertEqual(report['model_calls'], 0)
        self.assertIn('raw source bytes are not reread', report['scope'])
        for output in (packet, report):
            instrument = output['instrument']
            self.assertTrue(instrument['current_code_matches'])
            self.assertTrue(instrument['loaded_code_matches'])
            self.assertTrue(instrument['cheap_operator_check_performed'])
            self.assertTrue(instrument['saved_predictions_match_current_operator'])
            self.assertEqual(instrument['prediction_attestation'], 'matches_current_pinned_regex')
            self.assertFalse(instrument['historical_execution_attested'])

    def test_arbitrary_source_metadata_is_not_forwarded_to_sample_or_context(self):
        messages = copy.deepcopy(self.messages)
        for row in messages:
            row['source']['raw_provider_payload'] = {'private_thinking':'fixture-sensitive-detail'}
        self.dataset = self.store.put('dataset', {'messages':messages}, 'extra-provenance')
        try:
            sample = self.sample()
        except ValueError:
            return
        encoded = json.dumps(sample['payload'], sort_keys=True)
        self.assertNotIn('raw_provider_payload', encoded)
        self.assertNotIn('fixture-sensitive-detail', encoded)


if __name__ == '__main__':
    unittest.main()
