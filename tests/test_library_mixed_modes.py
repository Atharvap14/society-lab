"""An infrastructure append must preserve earlier live evidence scope."""
import tempfile
import unittest
from pathlib import Path

from swarm_lab.library import record_experiment
from swarm_lab.store import Store


class MixedModeLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / 'lab.sqlite3')
        self.behavior = self.store.put('behavior', {'status': 'candidate', 'experiment_ids': [],
                                                   'evidence_level': 'observational_candidate',
                                                   'causal_support': 'none'})

    def append(self, mode):
        result = self.store.put('experiment', {'status': 'complete', 'agent_mode': mode,
                                               'behavior_id': self.behavior['id']})
        return record_experiment(self.store, self.behavior['id'], result)

    def test_scripted_check_after_live_pilot_preserves_scope_and_result_ids(self):
        live = self.append('live')
        mixed = self.append('offline_simulation')
        self.assertEqual(mixed['payload']['status'], 'pilot_tested')
        self.assertEqual(mixed['payload']['evidence_level'], live['payload']['evidence_level'])
        self.assertEqual(mixed['payload']['causal_support'], live['payload']['causal_support'])
        self.assertEqual(len(mixed['payload']['experiment_ids']), 2)
        self.assertEqual(self.store.get(live['id'], live['version']), live)

    def test_scripted_only_stays_infrastructure_until_a_live_result_exists(self):
        scripted = self.append('offline_simulation')
        self.assertEqual(scripted['payload']['status'], 'infrastructure_tested')
        self.assertIn('No evidence about LLM behavior', scripted['payload']['causal_support'])
        live = self.append('live')
        self.assertEqual(live['payload']['status'], 'pilot_tested')
        self.assertEqual(live['payload']['evidence_level'], 'controlled_abstraction_pilot')

    def test_scripted_append_preserves_replication_and_rejection_statuses(self):
        for status in ('replication_tested', 'rejected'):
            live = self.append('live')
            payload = {**live['payload'], 'status': status,
                       'evidence_level': 'controlled_abstraction_with_held_out_seed_test'}
            self.store.put('behavior', payload, self.behavior['id'])
            appended = self.append('offline_simulation')
            self.assertEqual(appended['payload']['status'], status)
            self.assertEqual(appended['payload']['evidence_level'], payload['evidence_level'])
            self.assertEqual(appended['payload']['causal_support'], live['payload']['causal_support'])


if __name__ == '__main__':unittest.main()
