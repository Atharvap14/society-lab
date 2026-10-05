"""Fresh frozen-source regeneration gates for descriptive timestamp reports."""
import copy
import inspect
import json
import unittest
from unittest.mock import patch

from scripts.build_research_report import (ReadOnlyRecords, collect_report,
    collect_temporal_reference, render_temporal_reference_addition)


class TemporalReferenceReportTests(unittest.TestCase):
    def setUp(self):
        from tests.test_temporal_null_workflow import TemporalNullWorkflowTests
        self.f = TemporalNullWorkflowTests('test_bool_versions_and_unsafe_parameters_refused')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.reference = self.f.derive()
        self.proof = self.f.lab.replay_temporal_reference(self.reference['id'], version=1)
        self.records = ReadOnlyRecords(self.f.lab.store.path)
        self.addCleanup(self.records.close)

    @staticmethod
    def pin(obj):
        return {k: obj[k] for k in ('id', 'version', 'kind', 'hash')}

    def pins(self, reference=None, proof=None):
        return {'reference': self.pin(reference or self.reference), 'verification': self.pin(proof or self.proof)}

    def collect(self, pins=None):
        return collect_temporal_reference(self.records, self.pins() if pins is None else pins)

    def assert_withheld(self, addition):
        self.assertFalse(addition['proof']['passed'])
        self.assertIsNone(addition['quantities'])
        self.assertEqual(addition['windows'], {})
        html = render_temporal_reference_addition(addition)
        self.assertIn('withheld', html)
        self.assertNotIn('Descriptive counts only; columns compare', html)
        self.assertNotIn('fingerprinted synthetic assignments</summary>', html)

    def forged_pair(self, payload):
        reference = self.f.lab.store.put('temporal_timestamp_reference', payload)
        proof = copy.deepcopy(self.proof['payload'])
        proof['reference_ref'] = {k: reference[k] for k in ('id', 'version', 'hash')}
        return self.pins(reference, self.f.lab.store.put('verification', proof))

    def test_fresh_reference_old_source_versions_zero_writes_and_descriptive_scope(self):
        for source in (self.f.dataset, self.f.discovery, self.f.selected, self.f.temporal):
            self.f.lab.store.put(source['kind'], {'later': True}, source['id'])
        addition = self.collect()
        self.assertTrue(addition['proof']['passed'], addition['proof'])
        self.assertTrue(addition['proof']['source_replay_completed'])
        self.assertGreater(addition['quantities']['computed_cells'], 0)
        self.assertEqual(addition['references']['temporal_audit']['version'], 1)
        self.assertEqual(self.records.connection.total_changes, 0)
        self.assertEqual(self.f.lab.store.usage()['calls'], 0)
        self.assertEqual(self.f.lab.store.list('behavior'), [])
        html = render_temporal_reference_addition(addition)
        self.assertIn('not p-values or significance tests', html)
        self.assertIn('edge-time multiplicities can change', html)
        self.assertIn('not confidence intervals', html)
        self.assertIn('Original event pins', html)
        encoded = json.dumps(addition)
        self.assertNotIn('Bobby, inspect the telescope artifact', encoded)
        self.assertNotIn('provider_output', encoded)

    def test_resealed_original_envelope_rank_and_numeric_type_changes_fail_fresh_reproduction(self):
        original = self.reference['payload']
        for change in ('original', 'envelope', 'rank', 'numeric_type'):
            payload = copy.deepcopy(original)
            cell = next(v for w in payload['timestamp_reference']['windows'].values()
                        for v in w['variants'].values() if v['available'])
            metric = cell['reference']['metrics']['reachable_pair_count']
            if change == 'original': cell['observed']['reachable_pair_count'] += 1
            elif change == 'envelope': metric['envelope']['maximum'] += 1
            elif change == 'rank': metric['rank_counts']['greater_than_observed'] += 1
            else: metric['rank_counts']['comparable_draws'] = float(metric['rank_counts']['comparable_draws'])
            with self.subTest(change=change):
                self.assert_withheld(self.collect(self.forged_pair(payload)))

    def test_bad_source_pin_and_resealed_frozen_temporal_metric_cannot_be_references(self):
        payload = copy.deepcopy(self.reference['payload'])
        payload['source_refs']['dataset']['version'] = True
        self.assert_withheld(self.collect(self.forged_pair(payload)))
        changed = copy.deepcopy(self.f.temporal['payload'])
        next(iter(changed['windows'].values()))['variants']['baseline_exact']['strict_temporal']['reachable_pair_count'] += 1
        temporal = self.f.lab.store.put('temporal_path_audit', changed)
        ref = {k: temporal[k] for k in ('id', 'version', 'hash')}
        payload = copy.deepcopy(self.reference['payload'])
        payload['temporal_audit_ref'] = ref
        payload['source_refs']['temporal_audit'] = ref
        self.assert_withheld(self.collect(self.forged_pair(payload)))

    def test_stored_verifier_binding_flags_and_types_gate_before_regeneration(self):
        for update in ({'reference_ref': {**self.proof['payload']['reference_ref'], 'version': 2}},
                       {'model_calls': False}, {'source_replay_completed': False}):
            proof = self.f.lab.store.put('verification', {**self.proof['payload'], **update})
            with patch('swarm_lab.temporal_null_workflow.derive_temporal_reference', side_effect=AssertionError('must not regenerate')):
                self.assert_withheld(self.collect(self.pins(proof=proof)))

    def test_changed_implementation_does_not_start_source_replay(self):
        with patch('swarm_lab.temporal_null_workflow.implementation_hashes', return_value={}), \
             patch('swarm_lab.temporal_null_workflow.derive_temporal_reference', side_effect=AssertionError('must not regenerate')):
            addition = self.collect()
        self.assert_withheld(addition)
        self.assertFalse(addition['proof']['source_replay_attempted'])

    def test_budget_uncomputed_is_unknown_without_partial_metrics_or_ranks(self):
        reference = self.f.derive(max_work=1)
        proof = self.f.lab.replay_temporal_reference(reference['id'])
        addition = self.collect(self.pins(reference, proof))
        self.assertTrue(addition['proof']['passed'], addition['proof'])
        self.assertEqual(addition['quantities']['status'], 'not_computed_work_budget')
        self.assertEqual(addition['quantities']['computed_cells'], 0)
        for w in addition['windows'].values():
            for cell in w['variants'].values():
                self.assertIsNone(cell['observed'])
                self.assertIsNone(cell['reference'])
        html = render_temporal_reference_addition(addition)
        self.assertIn('Uncomputed cells are unknown', html)
        self.assertNotIn('Descriptive counts only; columns compare', html)

    def test_invalid_pin_set_withholds_and_library_flag_defaults_off(self):
        self.assert_withheld(self.collect({}))
        self.assertFalse(inspect.signature(collect_report).parameters['include_temporal_reference'].default)


if __name__ == '__main__':
    unittest.main()
