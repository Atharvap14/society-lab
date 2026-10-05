"""Prompt-driven real adapter contracts with temporary fixtures, no inference."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

from swarm_lab.behavior_rubrics import (BUILTINS, FIELDS, measure_rubric, rubric_catalog,
    save_rubric, validate_rubric_record)
from swarm_lab.classifiers import BackendUnavailable, TypedDecisionBackend, build_questions
from swarm_lab.config import Settings
from swarm_lab.guide_tools import execute_guide_tool, guide_tool_schemas
from swarm_lab.lab_workspace import DEFAULT_CHAT, bootstrap_workspace, chat_snapshot, save_state
from swarm_lab.pipeline import Lab
from swarm_lab.store import fingerprint
from tests import test_lab_workspace as http_fixture


def raw(value): return json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
def ref(obj): return {key: obj[key] for key in ('id', 'version', 'hash')}
def definition(): return {key: BUILTINS[5][key] for key in FIELDS}


class FixtureLaya(TypedDecisionBackend):
    name = 'fixture_no_inference'
    def __init__(self): super().__init__(neutral_labels=True); self.seen = []; self.closed = False
    def _invoke(self, state, questions):
        self.seen.append((state, copy.deepcopy(questions)))
        value = .95 if 'correction' in state else .05 if 'ordinary' in state else .5
        return {'answers': {'explicit_signal': {'type': 'noul', 'noul': value}}, 'model': 'authored fixture, no inference'}
    def close(self): self.closed = True


class FailedLaya(FixtureLaya):
    def _invoke(self, *_): raise BackendUnavailable('Authored RAM gate failure; no inference attempted')


class RubricTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.lab = Lab(Settings(root=Path(self.temp.name), max_calls=0))
        self.dataset = self.lab.store.put('dataset', {'messages': [
            {'id': 'm0', 'timestamp': '2025-04-01T00:00:00Z', 'content': 'I acknowledge the correction.', 'source': {'file': 'authored.jsonl', 'line': 1, 'table': 'chat_messages'}},
            {'id': 'm1', 'timestamp': '2025-04-01T00:01:00Z', 'content': 'ordinary work', 'source': {'file': 'authored.jsonl', 'line': 2}},
            {'id': 'm2', 'timestamp': '2025-04-01T00:02:00Z', 'content': 'This fixture is ambiguous.', 'source': {}}],
            'source_kind': 'authored_test_fixture'})
        bootstrap_workspace(self.lab)

    def saved(self): return save_rubric(self.lab, raw(definition()))['rubric_ref']
    def body(self, rubric, limit=3): return {'dataset_ref': ref(self.dataset), 'rubric_ref': rubric, 'limit': limit}

    def test_catalog_is_compact_adapted_unvalidated_and_read_only(self):
        before = self.lab.store.list(limit=1000)
        packet = rubric_catalog(self.lab)
        self.assertEqual([row['id'] for row in packet['catalog']], ['C' + str(i) for i in range(1, 9)])
        self.assertTrue(all(row['status'] == 'proposed_unvalidated' for row in packet['catalog']))
        self.assertEqual(packet['provenance']['git_blob_sha'], 'ef2a5f56c4d736e9fc250dc0be8147fadabedf6f')
        self.assertNotIn('references', packet['catalog'][0])  # Original short cards, not the private source file.
        self.assertLess(len(raw(packet)), 16000)
        self.assertEqual(self.lab.store.list(limit=1000), before)
        for _ in range(8): self.saved()
        packet = rubric_catalog(self.lab)
        self.assertEqual(len(packet['saved']), 6); self.assertIs(packet['saved_truncated'], True)
        self.assertLess(len(raw(packet)), 16000)

    def test_saved_custom_prompt_drives_exact_noul_schema_not_fixed_behavior_detector(self):
        spec = definition(); spec['screen_prompt'] = 'The author explicitly names a failed build dependency.'
        rubric = save_rubric(self.lab, raw(spec))['rubric_ref']
        original = self.lab.store.get(rubric['id'], rubric['version'])
        backend = FixtureLaya()
        result = measure_rubric(self.lab, raw(self.body(rubric)), backend_factory=lambda: backend)
        self.assertTrue(backend.closed); self.assertEqual(len(backend.seen), 3)
        q = backend.seen[0][1]
        self.assertIn(spec['screen_prompt'], q['explicit_signal']['instructions'])
        self.assertEqual(q['explicit_signal']['labels'], {'true': 'A', 'false': 'B'})
        self.assertEqual(fingerprint(q), original['payload']['question_schema_hash'])
        stored = self.lab.store.get(result['measurement_ref']['id'])['payload']
        self.assertEqual(stored['source_refs'], {'dataset_ref': ref(self.dataset), 'rubric_ref': rubric})
        self.assertEqual([r['text_measurement']['labels']['explicit_signal'] for r in stored['records']], [True, False, None])
        self.assertTrue(all(r['assessment'] == 'not_assessable' and r['opportunity'] == 'uncertain' for r in stored['records']))
        self.assertEqual(result['summary']['assessable_opportunities'], 0)
        self.assertEqual(result['summary']['motif_input'], 'prompt_defined_laya_text_screen_only')
        self.assertEqual(self.lab.store.get(rubric['id'], rubric['version']), original)
        self.assertEqual(self.lab.store.usage()['calls'], 0)

    def test_failure_persists_unknown_once_no_regex_or_negative_fallback(self):
        rubric = self.saved(); backend = FailedLaya()
        result = measure_rubric(self.lab, raw(self.body(rubric)), backend_factory=lambda: backend)
        self.assertEqual(result['status'], 'operational_failure')
        self.assertEqual(result['summary']['backend_attempts'], 1)
        self.assertEqual(result['summary']['text_unknown'], 3)
        self.assertEqual(result['summary']['text_positive'], 0)
        self.assertEqual(result['summary']['text_negative'], 0)
        self.assertEqual(result['summary']['fallback'], 'none')
        records = self.lab.store.get(result['measurement_ref']['id'])['payload']['records']
        self.assertTrue(all(r['text_measurement']['question_schema_hash'] == self.lab.store.get(rubric['id'])['payload']['question_schema_hash'] for r in records))
        self.assertIs(records[1]['text_measurement']['subsequent_attempt_suppressed'], True)
        self.assertTrue(backend.closed)

    def test_default_missing_real_runtime_is_recorded_without_installation_or_model_call(self):
        result = measure_rubric(self.lab, raw(self.body(self.saved())))
        self.assertEqual(result['status'], 'operational_failure')
        self.assertEqual(result['summary']['backend_attempts'], 0)
        self.assertEqual(result['summary']['text_unknown'], 3)
        self.assertEqual(self.lab.store.usage()['calls'], 0)
        self.assertFalse((self.lab.settings.runtime / 'laya-venv').exists())

    def test_exact_old_dataset_and_rubric_do_not_follow_latest(self):
        rubric = self.saved(); original_dataset = copy.deepcopy(self.dataset)
        self.lab.store.put('dataset', {'messages': []}, self.dataset['id'])
        result = measure_rubric(self.lab, raw(self.body(rubric)), backend_factory=FixtureLaya)
        self.assertEqual(result['dataset_ref'], ref(original_dataset))
        self.assertEqual(result['summary']['selected_messages'], 3)
        self.assertEqual(self.lab.store.get(self.dataset['id'], 1), original_dataset)

    def test_resealed_prompt_schema_and_boundary_mutations_refuse_before_backend_or_measurement(self):
        rubric = self.saved(); original = self.lab.store.get(rubric['id'])
        mutations = [('prompt_hash', '0' * 64), ('question_schema_hash', '0' * 64),
            ('assessment_default', 'consistent'), ('opportunity_default', 'present'),
            ('implementation_hashes', {}), ('thresholds', {'false_at_or_below': False, 'true_at_or_above': .8, 'otherwise': 'unknown'})]
        for field, value in mutations:
            invalid = self.lab.store.put('behavior_rubric', {**original['payload'], field: value})
            with self.subTest(field=field), self.assertRaises(ValueError):
                measure_rubric(self.lab, raw(self.body(ref(invalid))), backend_factory=lambda: self.fail('No backend before pin validation'))
        self.assertEqual(self.lab.store.list('rubric_measurement'), [])
        self.assertEqual(validate_rubric_record(self.lab, rubric), original)

    def test_type_unknown_duplicate_and_source_shapes_fail_closed(self):
        rubric = self.saved(); before = self.lab.store.list(limit=1000)
        cases = [self.body(rubric, True), self.body(rubric, 1.0), self.body(rubric, 33),
            self.body(rubric) | {'execute': 'not_allowed'},
            self.body(rubric) | {'dataset_ref': ref(self.dataset) | {'hash': '0' * 64}},
            self.body(rubric) | {'rubric_ref': rubric | {'version': True}},
            self.body(rubric) | {'rubric_ref': rubric | {'version': 1.0}}]
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError): measure_rubric(self.lab, raw(value), backend_factory=lambda: self.fail('No backend'))
        with self.assertRaises(ValueError): save_rubric(self.lab, b'{"title":"a","title":"b"}')
        for key, value in [('screen_prompt', None), ('positive', True), ('question', ''), ('non_examples', 'x' * 301)]:
            with self.assertRaises(ValueError): save_rubric(self.lab, raw(definition() | {key: value}))
        self.assertEqual(self.lab.store.list(limit=1000), before)
        bad = self.lab.store.put('dataset', {'messages': [self.dataset['payload']['messages'][0]] * 2})
        with self.assertRaises(ValueError): measure_rubric(self.lab, raw(self.body(rubric) | {'dataset_ref': ref(bad)}))
        malformed = self.lab.store.put('dataset', {'messages': [{**self.dataset['payload']['messages'][0], 'source': {'line': True}}]})
        with self.assertRaises(ValueError): measure_rubric(self.lab, raw(self.body(rubric) | {'dataset_ref': ref(malformed)}))

    def test_invalid_backend_schema_and_probability_remain_failure_unknown(self):
        class Wrong(FixtureLaya):
            def measure(self, message, definitions):
                result = super().measure(message, definitions)
                result['labels']['explicit_signal'] = 1
                return result
        result = measure_rubric(self.lab, raw(self.body(self.saved())), backend_factory=Wrong)
        self.assertEqual(result['status'], 'operational_failure')
        self.assertEqual(result['summary']['text_unknown'], 3)

    def test_actual_guide_facades_have_seen_ref_guards_origin_and_retry_without_inference(self):
        allowed = ['list_rubrics', 'save_rubric', 'measure_rubric']
        self.assertEqual({s['name'] for s in guide_tool_schemas(allowed)}, set(allowed))
        def call(name, args, key, refs=()):
            return execute_guide_tool(self.lab, name, args, chat_id=DEFAULT_CHAT, request_id=key,
                authorized_tools=allowed, allowed_refs=list(refs))
        listed = call('list_rubrics', {}, 'rubrics-list')
        self.assertEqual(len(listed['rubrics']['catalog']), 8)
        self.assertEqual(len(chat_snapshot(self.lab, DEFAULT_CHAT)['artifacts']), 1)
        saved = call('save_rubric', definition(), 'rubrics-save')
        rubric = saved['updated_context']['rubric_ref']
        self.assertIs(call('save_rubric', definition(), 'rubrics-save')['reused'], True)
        with self.assertRaises(ValueError): call('measure_rubric', self.body(rubric), 'rubrics-unseen')
        measured = call('measure_rubric', self.body(rubric), 'rubrics-measure', [ref(self.dataset), rubric])
        self.assertEqual(measured['status'], 'completed')
        self.assertEqual(measured['measurement_status'], 'operational_failure')
        self.assertEqual(measured['measurement_summary']['text_unknown'], 3)
        self.assertIs(call('measure_rubric', self.body(rubric), 'rubrics-measure', [ref(self.dataset), rubric])['reused'], True)
        snapshot = chat_snapshot(self.lab, DEFAULT_CHAT)
        save_state(self.lab, DEFAULT_CHAT, expected_revision=snapshot['revision'], state={'context': measured['updated_context']}, request_id='rubric-context')
        self.assertEqual(len(self.lab.store.list('rubric_measurement')), 1)
        self.assertEqual(self.lab.store.usage()['calls'], 0)


class RubricHttpTests(unittest.TestCase):
    def test_real_loopback_catalog_save_measure_csrf_and_exact_unknown_result(self):
        host = http_fixture.WorkspaceHttpTests(); self.addCleanup(host.doCleanups); host.setUp()
        packet = host.get('/api/rubrics'); self.assertEqual(len(packet['catalog']), 8)
        dataset = host.lab.store.put('dataset', {'messages': [{'id': 'fixture', 'created_at': '2025-01-01T00:00:00Z', 'content': 'Author statement fixture'}]})
        with self.assertRaises(urllib.error.HTTPError) as error: host.post('/api/rubrics/save', definition(), token=False)
        self.assertEqual(error.exception.code, 403)
        saved = host.post('/api/rubrics/save', definition(), chat=DEFAULT_CHAT)
        result = host.post('/api/rubrics/measure', {'dataset_ref': ref(dataset), 'rubric_ref': saved['rubric_ref'], 'limit': 1}, chat=DEFAULT_CHAT)
        self.assertEqual(result['status'], 'operational_failure'); self.assertEqual(result['summary']['text_unknown'], 1)
        stored = host.lab.store.get(result['measurement_ref']['id'])
        self.assertEqual(stored['payload']['source_refs']['rubric_ref'], saved['rubric_ref'])
        self.assertIs(stored['payload']['episode_assessment_available'], False)
        for path in ('/api/rubrics?extra=1', '/api/rubrics?version=1'):
            with self.assertRaises(urllib.error.HTTPError): host.get(path)
        self.assertEqual(host.lab.store.usage()['calls'], 0)


if __name__ == '__main__': unittest.main()
