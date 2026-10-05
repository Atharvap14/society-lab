"""Actual CPU engine progress, with no provider calls or production registry writes."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from swarm_lab.config import ROOT, Settings
from swarm_lab.experiments import ExperimentExecutionError, offline_policy
from swarm_lab.pipeline import Lab


class ExperimentProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.lab = Lab(Settings(root=Path(self.temp.name), max_calls=0))
        dataset = self.lab.ingest(ROOT / 'examples' / 'coordination_fixture', limit=100)
        discovery = self.lab.observe(dataset['id'])
        candidate = next(row for row in discovery['payload']['candidates']
                         if row['kind'] == 'completion_report_cluster')
        self.behavior = self.lab.investigate(discovery['id'], candidate_ids=[candidate['id']])[0]
        self.protocol = self.lab.design(self.behavior['id'], trials_per_arm=2, max_rounds=3)

    def test_completed_unit_progress_is_the_actual_randomized_execution_order(self):
        updates = []
        original = self.lab.store.job
        def record(identity, status, payload):
            updates.append((identity, status, copy.deepcopy(payload)))
            return original(identity, status, payload)
        with patch.object(self.lab.store, 'job', side_effect=record):
            result = self.lab.experiment(self.protocol['id'], job_id='cpu-progress')
        progress = [payload['progress'] for identity, status, payload in updates
                    if identity == 'cpu-progress' and status == 'running']
        self.assertEqual(progress[0], {'completed': 0, 'total': 6, 'arm': None, 'run_id': None})
        self.assertEqual([row['completed'] for row in progress], list(range(7)))
        self.assertEqual([row['run_id'] for row in progress[1:]],
                         [row['run_id'] for row in result['payload']['runs']])
        self.assertEqual([row['arm'] for row in progress[1:]],
                         [row['arm'] for row in result['payload']['runs']])
        self.assertTrue(all(row['total'] == len(result['payload']['assignments']) for row in progress))
        for _, _, payload in updates:
            self.assertEqual(payload['stage'], 'experiment')
            self.assertEqual(payload['protocol_id'], self.protocol['id'])
            self.assertIs(payload['live'], False)
        self.assertEqual(self.lab.store.usage()['calls'], 0)

    def test_partial_failure_retains_only_finished_units_and_no_effect_estimate(self):
        def interrupted(request):
            progress = self.lab.store.get_job('cpu-progress-failed')['payload']['progress']
            if progress['completed']:
                raise RuntimeError('Temporary fixture interruption after one completed swarm')
            return offline_policy(request)
        with patch('swarm_lab.experiments.offline_policy', side_effect=interrupted):
            with self.assertRaises(ExperimentExecutionError):
                self.lab.experiment(self.protocol['id'], job_id='cpu-progress-failed')
        job = self.lab.store.get_job('cpu-progress-failed')
        self.assertEqual(job['status'], 'failed')
        payload = job['payload']
        retained = self.lab.store.get(payload['incomplete_result_id'])['payload']
        self.assertEqual(payload['progress']['completed'], len(retained['runs']))
        self.assertEqual(payload['progress']['completed'], 1)
        self.assertEqual(payload['progress']['total'], 6)
        self.assertEqual(payload['progress']['run_id'], retained['runs'][0]['run_id'])
        self.assertEqual(payload['protocol_id'], self.protocol['id'])
        self.assertEqual(retained['status'], 'incomplete_infrastructure_failure')
        self.assertNotIn('analysis', retained)
        self.assertEqual(self.lab.store.get(self.behavior['id'])['payload']['experiment_ids'], [])
        self.assertEqual(self.lab.store.usage()['calls'], 0)


if __name__ == '__main__':
    unittest.main()
