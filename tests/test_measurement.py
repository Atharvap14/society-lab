import unittest
from swarm_lab.experiments import create_protocol,run_experiment
from swarm_lab.measurement import inspect_trajectories

class MeasurementTests(unittest.TestCase):
    def test_any_agent_inspection_is_not_publisher_inspection(self):
        result={'runs':[{'run_id':'r','arm':'placebo','initial_state':{},'final_state':{'published':{'version':1}},'turns':[{'agent_id':'verifier','action':{'action':'inspect_artifact'},'tool_result':{'ok':True,'version':1}}],'outcomes':{'success':0,'inspected_publication':1}}]}
        review=inspect_trajectories(result);row=review['runs'][0]
        self.assertEqual(row['any_agent_inspected_published_version'],1)
        self.assertEqual(row['coordinator_inspected_published_version'],0)
        self.assertEqual(row['success'],0)
        self.assertTrue(review['all_registered_inspection_metrics_match'])
    def test_stale_version_inspection_is_not_current_version_check(self):
        result={'runs':[{'run_id':'r','arm':'baseline','initial_state':{},'final_state':{'published':{'version':2}},'turns':[{'agent_id':'coordinator','action':{'action':'inspect_artifact'},'tool_result':{'ok':True,'version':1}}],'outcomes':{'success':1,'inspected_publication':0}}]}
        row=inspect_trajectories(result)['runs'][0]
        self.assertEqual(row['coordinator_inspected_any'],1)
        self.assertEqual(row['coordinator_inspected_published_version'],0)
    def test_realized_scripted_paths_reconcile_to_registered_metric(self):
        r=run_experiment(create_protocol(trials_per_arm=2,max_rounds=3))
        review=inspect_trajectories(r)
        self.assertTrue(review['all_registered_inspection_metrics_match'])
        self.assertIn('not randomized mediators',review['scope'])

if __name__=='__main__':unittest.main()
