"""Real registry/archive replay, zero-call fixtures and failure retention."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab


class TimedResourceWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lab = Lab(Settings(root=Path(self.tmp.name), max_calls=100))

    def execute(self, identity='timed-once'):
        registered = self.lab.design_timed_resource(seed=6137, resamples=100)
        result = self.lab.experiment_timed_resource(registered['id'], job_id=identity)
        return registered, result

    def test_actual_paired_run_receipts_and_replay(self):
        registered, result = self.execute()
        p = result['payload']
        self.assertEqual(p['status'], 'complete')
        self.assertEqual(len(p['runs']), 4)
        self.assertEqual(p['analysis']['primary_effect']['difference'], 0)
        self.assertEqual(p['analysis']['primary_effect']['paired_differences'], [0, 0])
        self.assertEqual(p['analysis']['primary_effect']['p_two_sided'], 1)
        self.assertEqual(p['protocol_ref']['hash'], registered['hash'])
        self.assertTrue(self.lab.audit(result['id'])['payload']['passed'])
        self.assertEqual(self.lab.store.usage()['calls'], 0)
        self.assertEqual(self.lab.store.list('behavior'), [])
        self.assertEqual(self.lab.store.list('theory'), [])
        claims=self.lab.evaluate_claims(result['id'])['payload']
        self.assertTrue(claims['quantitative_facts_available'])
        self.assertTrue(claims['audit']['all_executable_claims_supported'])
        self.assertEqual(claims['result_ref'],{key:result[key] for key in ('id','version','hash')})
        self.assertEqual(claims['status'],'verified_facts_only')
        self.assertLessEqual(len(claims['claims']),24)

    def test_old_registration_version_and_redundant_binding_tamper(self):
        registered, result = self.execute()
        self.lab.store.put('timed_resource_protocol', {'later': True}, registered['id'])
        self.assertTrue(self.lab.audit(result['id'])['payload']['passed'])
        for key, value in (('status', 'invented_complete'), ('model', 'another_model'),
                           ('registered_hash', '0' * 64), ('protocol_id', 'unrelated')):
            changed = copy.deepcopy(result['payload'])
            changed[key] = value
            bad = self.lab.store.put('timed_resource_experiment', changed)
            self.assertFalse(self.lab.audit(bad['id'])['payload']['passed'], key)
        changed = copy.deepcopy(result['payload'])
        del changed['behavior_id']
        bad = self.lab.store.put('timed_resource_experiment', changed)
        self.assertFalse(self.lab.audit(bad['id'])['payload']['passed'])
        for value in (True, 1.0):
            changed = copy.deepcopy(result['payload'])
            changed['protocol_ref']['version'] = value
            bad = self.lab.store.put('timed_resource_experiment', changed)
            with self.assertRaises(ValueError):
                self.lab.audit(bad['id'])

    def test_resealed_archive_is_still_bound_to_registered_bytes(self):
        _, result = self.execute()
        archive = Path(result['payload']['artifact_directory']) / 'execution-code'
        source = archive / 'intervention_timing.py'
        source.write_bytes(source.read_bytes() + b'\n# altered archival bytes\n')
        path = archive / 'manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        manifest['files'][source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
        path.write_text(json.dumps(manifest), encoding='utf-8')
        verification = self.lab.audit(result['id'])['payload']
        self.assertEqual(verification['execution_archive']['status'], 'verified')
        self.assertFalse(verification['passed'])
        with self.assertRaisesRegex(ValueError,'quantitative facts unavailable'):
            self.lab.evaluate_claims(result['id'])
        self.assertEqual(self.lab.store.list('claim_audit'),[])

    def test_budget_mode_and_duplicate_identity_preserve_existing_evidence(self):
        registered, result = self.execute()
        path = Path(result['payload']['artifact_directory']) / 'report.json'
        before = path.read_bytes()
        saved_job = self.lab.store.get_job('timed-once')
        with self.assertRaisesRegex(ValueError, 'already launched'):
            self.lab.experiment_timed_resource(registered['id'], job_id='timed-once')
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.lab.store.get_job('timed-once'), saved_job)
        with self.assertRaisesRegex(ValueError, 'backend differs'):
            self.lab.experiment_timed_resource(registered['id'], live=True)
        hosted = self.lab.design_timed_resource(live=True, resamples=100)
        self.lab.settings.max_calls = 1
        with patch.object(self.lab, 'harness', side_effect=AssertionError('Must not construct a model')):
            with self.assertRaisesRegex(ValueError, 'remaining cap'):
                self.lab.experiment_timed_resource(hosted['id'], live=True, job_id='over-cap')
        self.assertFalse((self.lab.settings.runtime / 'runs' / 'over-cap').exists())

    def test_failed_subject_fixture_retains_every_assignment_and_pending_request(self):
        # Test transport only: this fixture never invokes a provider or consumes
        # the key. A failed call cannot become an empirical zero outcome.
        class FailedSubject:
            def subject(self, request):
                raise RuntimeError('fixture transport failure')
        hosted = self.lab.design_timed_resource(live=True, resamples=100)
        with patch.object(self.lab, 'harness', return_value=FailedSubject()):
            with self.assertRaises(RuntimeError):
                self.lab.experiment_timed_resource(hosted['id'], live=True, job_id='failed-fixture')
        job = self.lab.store.get_job('failed-fixture')
        self.assertEqual(job['status'], 'failed')
        saved = self.lab.store.get(job['payload']['incomplete_result_id'])
        p = saved['payload']
        self.assertEqual(p['status'], 'incomplete_infrastructure_failure')
        self.assertIsNone(p.get('analysis'))
        self.assertEqual(len(p['runs']), 4)
        self.assertTrue(all(run.get('outcomes') is None for run in p['runs']))
        self.assertTrue((Path(p['artifact_directory']) / 'pending_decision.json').is_file())
        self.assertEqual(self.lab.store.usage()['calls'], 0)
        claims=self.lab.evaluate_claims(saved['id'])['payload']
        self.assertEqual(claims['status'],'metadata_only')
        self.assertFalse(claims['quantitative_facts_available'])
        self.assertTrue(all(fact['scope'] in ('recorded_execution','recorded_design')
            for fact in claims['fact_packet']['facts'].values()))


if __name__ == '__main__':
    unittest.main()
