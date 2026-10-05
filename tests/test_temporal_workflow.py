"""Registry/version and source-replay checks for the temporal derivation."""
import copy
import tempfile
import unittest
from pathlib import Path

from swarm_lab.config import Settings
from swarm_lab.graph_discovery import discover_graph_leads
from swarm_lab.pipeline import Lab
from tests.test_selected_lead_workflow import fixture


class TemporalWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lab = Lab(Settings(root=Path(self.tmp.name)))
        rows, roster = fixture()
        self.dataset = self.lab.store.put('dataset', {'messages': rows, 'agents': roster})
        self.discovery = self.lab.store.put('discovery', {
            'dataset_id': self.dataset['id'],
            'dataset_ref': {key: self.dataset[key] for key in ('id', 'version', 'hash')},
            'graph_search': discover_graph_leads(rows, roster)})
        self.selected = self.lab.audit_selected_leads(self.discovery['id'],
            short_name_allowlist=['o3'], include_unicode_shadow=True)

    def test_exact_older_versions_and_actual_zero_call_replay(self):
        self.lab.store.put('dataset', {'messages': [], 'agents': []}, self.dataset['id'])
        self.lab.store.put('discovery', {'later': True}, self.discovery['id'])
        self.lab.store.put('selected_lead_audit', {'later': True}, self.selected['id'])
        result = self.lab.audit_temporal_paths(self.selected['id'], version=1)
        p = result['payload']
        self.assertEqual(result['kind'], 'temporal_path_audit')
        self.assertEqual(p['source_refs']['dataset']['hash'], self.dataset['hash'])
        self.assertEqual(p['source_refs']['discovery']['version'], 1)
        self.assertEqual(p['selected_audit_ref']['hash'], self.selected['hash'])
        self.assertTrue(p['source_audit_replay_passed'])
        self.assertEqual(len(p['windows']), 2)
        replay = self.lab.replay_temporal_paths(result['id'])
        self.assertTrue(replay['payload']['passed'])
        self.assertEqual(replay['payload']['audit_ref']['hash'], result['hash'])
        self.assertEqual(self.lab.store.get(self.selected['id'], 1), self.selected)
        self.assertEqual(self.lab.store.get(self.discovery['id'], 1), self.discovery)
        self.assertEqual(self.lab.store.list('behavior'), [])
        self.assertEqual(self.lab.store.usage()['calls'], 0)

    def test_forged_windows_or_source_refs_fail_before_persistence(self):
        for change in ('window', 'pin'):
            payload = copy.deepcopy(self.selected['payload'])
            if change == 'window':
                first = next(iter(payload['window_measurements'].values()))
                first['original_window']['end_exclusive'] = '2025-04-02T13:00:00Z'
            else:
                payload['source_refs']['dataset']['hash'] = '0' * 64
            bad = self.lab.store.put('selected_lead_audit', payload)
            with self.assertRaises(ValueError):
                self.lab.audit_temporal_paths(bad['id'])
        self.assertEqual(self.lab.store.list('temporal_path_audit'), [])

    def test_changed_derivation_does_not_pass_replay(self):
        result = self.lab.audit_temporal_paths(self.selected['id'])
        changed = copy.deepcopy(result['payload'])
        changed['original_comparisons'][0]['feature'] = 'invented_effect'
        bad = self.lab.store.put('temporal_path_audit', changed)
        checked = self.lab.replay_temporal_paths(bad['id'])
        self.assertFalse(checked['payload']['passed'])
        for method, identity in ((self.lab.audit_temporal_paths, self.selected['id']),
                                 (self.lab.replay_temporal_paths, result['id'])):
            with self.assertRaises(ValueError):
                method(identity, version=True)


if __name__ == '__main__':
    unittest.main()
