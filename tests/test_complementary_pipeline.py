"""Study-specific integration gates and recorded-action checks; no paid calls."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab
from swarm_lab.store import fingerprint
from swarm_lab.complementary_experiments import ComplementaryExecutionError


class ComplementaryPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.lab=Lab(Settings(root=Path(self.tmp.name)))

    def test_offline_assignment_execution_and_canonical_audit(self):
        registration=self.lab.design_complementary()
        self.assertEqual(registration['payload']['protocol']['design']['maximum_subject_calls'],96)
        result=self.lab.experiment_complementary(registration['id'],job_id='complete')
        p=result['payload']
        self.assertEqual(p['status'],'complete');self.assertEqual(len(p['runs']),8)
        self.assertEqual(self.lab.store.usage()['calls'],0)
        verification=self.lab.audit(result['id'])['payload']
        self.assertTrue(verification['passed']);self.assertEqual(verification['runs_checked'],8)
        self.assertEqual(verification['execution_archive']['status'],'verified')
        self.assertEqual(p['agent_mode'],'offline_simulation')
        # Registered results and raw report must both stay consistent.
        changed=copy.deepcopy(p);changed['runs'][0]['outcomes']['mean_accuracy']=.25
        self.lab.store.put('complementary_experiment',changed,result['id'])
        self.assertFalse(self.lab.audit(result['id'])['payload']['passed'])

    def test_wrong_study_kind_and_backend_stop_before_harness(self):
        offline=self.lab.design_complementary()
        wrong=self.lab.design_network()
        with patch.object(self.lab,'harness') as backend:
            with self.assertRaisesRegex(ValueError,'study-specific'):
                self.lab.experiment_complementary(wrong['id'],live=True)
            with self.assertRaisesRegex(ValueError,'backend differs'):
                self.lab.experiment_complementary(offline['id'],live=True)
            backend.assert_not_called()

    def test_amended_adapter_and_budget_reject_before_calls(self):
        live=self.lab.design_complementary(live=True)
        self.lab.settings.max_calls=95
        with patch.object(self.lab,'harness') as backend:
            with self.assertRaisesRegex(ValueError,'96 subject calls'):
                self.lab.experiment_complementary(live['id'],live=True)
            backend.assert_not_called()
        self.lab.settings.max_calls=400
        p=copy.deepcopy(live['payload']);p['subject_adapter_hash']='changed'
        self.lab.store.put('complementary_protocol',p,live['id'])
        with patch.object(self.lab,'harness') as backend:
            with self.assertRaisesRegex(ValueError,'adapter changed'):
                self.lab.experiment_complementary(live['id'],live=True)
            backend.assert_not_called()

    def test_frozen_protocol_rejects_unregistered_treatment_change(self):
        registration=self.lab.design_complementary(live=True)
        p=copy.deepcopy(registration['payload']);p['protocol']['contexts']['source_thought']['insertion']='Changed after freeze'
        self.lab.store.put('complementary_protocol',p,registration['id'])
        with patch.object(self.lab,'harness') as backend:
            with self.assertRaisesRegex(ValueError,'Protocol changed'):
                self.lab.experiment_complementary(registration['id'],live=True)
            backend.assert_not_called()

    def test_failed_transport_preserves_partial_report_without_estimate(self):
        registration=self.lab.design_complementary(live=True)
        backend=Mock();backend.subject.side_effect=RuntimeError('simulated service failure')
        with patch.object(self.lab,'harness',return_value=backend):
            with self.assertRaises(ComplementaryExecutionError):
                self.lab.experiment_complementary(registration['id'],live=True,job_id='failed')
        report=json.loads((self.lab.settings.runtime/'runs/failed/report.json').read_text(encoding='utf-8'))
        self.assertEqual(report['status'],'incomplete_infrastructure_failure')
        self.assertNotIn('analysis',report)
        failed=self.lab.store.list('complementary_experiment')[0]['payload']
        self.assertEqual(failed['status'],report['status'])
        self.assertNotIn('analysis',failed)
        self.assertTrue(any(t['payload'].get('type')=='experiment_failure' for t in self.lab.store.traces('failed')))


if __name__=='__main__':unittest.main()
