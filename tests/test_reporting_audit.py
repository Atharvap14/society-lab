import copy
import unittest
from swarm_lab.reporting import quantitative_summary,numeric_free_commentary
from swarm_lab.experiments import create_protocol,run_experiment
from swarm_lab.audit import replay_report

class ReportAuditTests(unittest.TestCase):
    def setUp(self):self.result=run_experiment(create_protocol(trials_per_arm=2,max_rounds=3))
    def test_counts_come_from_actual_runs_and_preserve_uncertainty(self):
        report=copy.deepcopy(self.result)
        report['analysis']['arms']['baseline']['success']=.999
        q=quantitative_summary(report)
        actual=sum(r['outcomes']['success'] for r in report['runs'] if r['arm']=='baseline')
        self.assertEqual(q['arms']['baseline']['correct'],actual)
        self.assertEqual(q['arms']['baseline']['total'],2)
        self.assertIn('whole_swarm_run',q['unit'])
        self.assertIn('Historical causation',q['plain_language'])
    def test_incomplete_report_has_no_effect_summary(self):
        q=quantitative_summary({'status':'incomplete_infrastructure_failure'})
        self.assertNotIn('difference',q)
    def test_model_numeric_prose_flagged_for_review(self):
        self.assertFalse(numeric_free_commentary({'summary':'Two correct results out of 3 (mean 1.0)'}))
        self.assertTrue(numeric_free_commentary({'summary':'The interval is too wide to distinguish the alternatives.'}))
    def test_exact_replay_checks_requests_actions_and_oracle(self):
        verification=replay_report(self.result)
        self.assertTrue(verification['passed']);self.assertEqual(verification['runs_checked'],6)
        self.assertEqual(verification['model_calls'],0)
    def test_narrated_success_cannot_override_executed_oracle(self):
        report=copy.deepcopy(self.result);report.pop('report_hash')
        report['runs'][0]['outcomes']['success']=1-report['runs'][0]['outcomes']['success']
        verification=replay_report(report)
        self.assertFalse(verification['passed'])
        self.assertFalse(verification['checks'][0]['oracle_outcomes_match'])
    def test_future_or_private_request_tampering_is_visible(self):
        report=copy.deepcopy(self.result);report.pop('report_hash')
        report['runs'][0]['turns'][0]['request']['oracle_truth']='leaked'
        verification=replay_report(report)
        self.assertFalse(verification['passed'])
        self.assertFalse(verification['checks'][0]['subject_requests_match'])

if __name__=='__main__':unittest.main()
