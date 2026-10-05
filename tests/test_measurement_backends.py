import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from swarm_lab.classifiers import BackendUnavailable, TypedDecisionBackend
from swarm_lab.discovery import discover_cases, DETECTOR_DEFINITIONS
from swarm_lab.measurement_backends import BoundedMeasurement
from swarm_lab.pipeline import Lab
from swarm_lab.config import Settings
from swarm_lab.store import Store


def messages():
    return [{'id':f'm{i}','agent_id':'a','created_at':f'2026-04-01T10:{i:02d}:00Z',
             'room_id':'r','content':'Task completed' if i==0 else 'Ordinary work'} for i in range(6)]


class Failed(TypedDecisionBackend):
    name='failed_fixture'
    def _invoke(self,*_):raise BackendUnavailable('deliberate resource failure')


class MeasurementIntegrationTests(unittest.TestCase):
    def test_resource_failure_does_not_erase_graph_or_substitute_negative_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            backend=BoundedMeasurement('laya',messages(),Path(directory),limit=3,factory=Failed)
            result=discover_cases(messages(),backend=backend)
            self.assertEqual(backend.attempts,1)
            self.assertEqual(backend.summary()['statuses'],{'operational_failure':3})
            self.assertEqual(len(result['signals']),6)
            self.assertGreater(len(result['graph']['edges']),0)
            first=result['signals'][0]
            self.assertIn('completion_report',first['labels'])
            self.assertIsNone(first['additional_measurement']['labels']['completion_report'])
            self.assertEqual(first['additional_measurement']['status'],'operational_failure')
            self.assertEqual(result['signals'][1]['additional_measurement']['status'],'not_sampled')
            self.assertEqual(backend.summary()['fallback'],'none')
            backend.close()

    def test_missing_provider_key_makes_zero_requests_and_preserves_unknowns(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ',{},clear=True):
            backend=BoundedMeasurement('jev',messages(),Path(directory),limit=2)
            result=backend.classify(messages()[0],DETECTOR_DEFINITIONS)
            self.assertTrue(all(value is None for value in result.values()))
            self.assertEqual(backend.attempts,0)
            self.assertIn('no HTTP call',backend.summary()['operational_error'])

    def test_selected_sample_precedes_outputs_and_covers_endpoints(self):
        with tempfile.TemporaryDirectory() as directory:
            backend=BoundedMeasurement('laya',messages()[::-1],Path(directory),limit=3,factory=Failed)
            self.assertEqual(backend.selected_ids,{'m0','m2','m5'})
            for value in (0,True,251):
                with self.assertRaises(ValueError):BoundedMeasurement('laya',messages(),Path(directory),limit=value)

    def test_lab_persists_failure_diagnostics_and_exact_dataset_version(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ',{},clear=True):
            lab=Lab(Settings())
            lab.store=Store(Path(directory)/'lab.sqlite3')
            dataset=lab.store.put('dataset',{'messages':messages(),'agents':[]})
            with self.assertRaisesRegex(ValueError,'explicit live mode'):
                lab.observe(dataset['id'],measurement_backend='jev',measurement_limit=2)
            result=lab.observe(dataset['id'],measurement_backend='jev',measurement_limit=2,live=True)
            summary=result['payload']['measurement_summary']
            self.assertEqual(summary['selected_messages'],2)
            self.assertEqual(summary['statuses'],{'operational_failure':2})
            self.assertEqual(result['payload']['dataset_ref']['hash'],dataset['hash'])
            self.assertEqual(lab.store.usage()['calls'],0)


if __name__=='__main__':unittest.main()
