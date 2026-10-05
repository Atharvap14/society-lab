"""Exact-source host binding for conditional timestamp references."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from swarm_lab.config import Settings
from swarm_lab.graph_discovery import discover_graph_leads
from swarm_lab.pipeline import Lab
from tests.test_selected_lead_workflow import fixture


class TemporalNullWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lab = Lab(Settings(root=Path(self.tmp.name)))
        rows, roster = fixture()
        self.dataset = self.lab.store.put('dataset', {'messages': rows, 'agents': roster})
        self.discovery = self.lab.store.put('discovery', {'dataset_id': self.dataset['id'],
            'dataset_ref': {key: self.dataset[key] for key in ('id', 'version', 'hash')},
            'graph_search': discover_graph_leads(rows, roster)})
        self.selected = self.lab.audit_selected_leads(self.discovery['id'],
            short_name_allowlist=['o3'], include_unicode_shadow=True)
        self.temporal = self.lab.audit_temporal_paths(self.selected['id'], version=1)

    def derive(self, **kwargs):
        return self.lab.audit_temporal_reference(self.temporal['id'], version=1,
                                                 resamples=4, **kwargs)

    def test_exact_old_sources_replay_and_deterministic_conditional_draws(self):
        for source in (self.dataset, self.discovery, self.selected, self.temporal):
            self.lab.store.put(source['kind'], {'later': True}, source['id'])
        result = self.derive()
        reference = result['payload']['timestamp_reference']
        self.assertEqual(reference['status'], 'complete_reference')
        self.assertEqual(reference['source_refs']['temporal_audit']['hash'], self.temporal['hash'])
        proof = self.lab.replay_temporal_reference(result['id'], version=1)['payload']
        self.assertTrue(proof['passed'])
        self.assertTrue(proof['source_replay_completed'])
        self.assertEqual(proof['reference_ref']['hash'], result['hash'])
        self.assertEqual(self.lab.store.usage()['calls'], 0)
        self.assertEqual(self.lab.store.list('behavior'), [])

    def test_budget_unknown_can_replay_but_never_contains_partial_ranks(self):
        result = self.derive(max_work=1)
        reference = result['payload']['timestamp_reference']
        self.assertEqual(reference['status'], 'not_computed_work_budget')
        for window in reference['windows'].values():
            for variant in window['variants'].values():self.assertIsNone(variant['reference'])
        self.assertTrue(self.lab.replay_temporal_reference(result['id'])['payload']['passed'])

    def test_forged_original_temporal_source_rejected_before_reference_persistence(self):
        payload = copy.deepcopy(self.temporal['payload'])
        window = next(iter(payload['windows'].values()))
        window['variants']['baseline_exact']['strict_temporal']['reachable_pair_count'] += 1
        bad = self.lab.store.put('temporal_path_audit', payload)
        with self.assertRaisesRegex(ValueError, 'does not reproduce'):
            self.lab.audit_temporal_reference(bad['id'], resamples=4)
        self.assertEqual(self.lab.store.list('temporal_timestamp_reference'), [])

    def test_changed_reference_or_code_has_no_passing_proof(self):
        result = self.derive()
        payload = copy.deepcopy(result['payload'])
        payload['timestamp_reference']['configuration']['seed'] += 1
        bad = self.lab.store.put('temporal_timestamp_reference', payload)
        self.assertFalse(self.lab.replay_temporal_reference(bad['id'])['payload']['passed'])
        with patch('swarm_lab.temporal_null_workflow.implementation_hashes', return_value={}):
            proof = self.lab.replay_temporal_reference(result['id'])['payload']
        self.assertFalse(proof['source_replay_attempted'])
        self.assertEqual(proof['reason'], 'implementation_hash_mismatch')

    def test_bool_versions_and_unsafe_parameters_refused(self):
        with self.assertRaises(ValueError):self.lab.audit_temporal_reference(self.temporal['id'], version=True)
        for kwargs in ({'max_work': True}, {'variants': ['unregistered']}, {'seed': -1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):self.derive(**kwargs)


if __name__ == '__main__':unittest.main()
