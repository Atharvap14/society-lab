"""Exercise real registration, execution, archive integrity and replay routing."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab
from tests.test_environment_authoring import proposal,review


class ResourceWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.lab=Lab(Settings(root=Path(self.tmp.name),max_calls=1))

    def test_authored_resource_world_preserved_then_executed_and_replayed(self):
        p=proposal('exclusive_resource_tasks')
        p['parameters'].update(max_rounds=7,release_rounds=[0,3,7],independent_work_steps=2,
            computer_work_steps=2,max_messages_per_agent=1)
        world=self.lab.construct_environment(proposal=p,fit_review=review(p),required_capabilities=[
            'exclusive_shared_computer','independent_parallel_work'])
        self.assertEqual(world['payload']['experiment_eligibility'],'approved_analogue')
        registered=self.lab.register_blueprint(world['id'],seed=918)
        self.assertEqual(registered['kind'],'resource_protocol')
        self.assertEqual(registered['payload']['protocol']['environment'],world['payload']['spec'])
        result=self.lab.experiment_resource(registered['id'],job_id='resource-authored')
        self.assertEqual(result['payload']['status'],'complete')
        self.assertTrue(self.lab.audit(result['id'])['payload']['passed'])
        claims=self.lab.evaluate_claims(result['id'])['payload']
        self.assertTrue(claims['quantitative_facts_available'])
        self.assertTrue(claims['audit']['all_executable_claims_supported'])
        self.assertEqual(claims['result_ref']['hash'],result['hash'])
        self.assertEqual(self.lab.store.usage()['calls'],0)
        self.assertEqual(self.lab.store.list('theory'),[])
        self.assertEqual(self.lab.store.list('behavior'),[])

    def test_archive_tamper_is_detected_even_when_local_manifest_resealed(self):
        p=self.lab.design_resource();r=self.lab.experiment_resource(p['id'],job_id='resource-tamper')
        directory=Path(r['payload']['artifact_directory'])/'execution-code'
        source=directory/'resource_environment.py';source.write_bytes(source.read_bytes()+b'\n# altered\n')
        import hashlib
        path=directory/'manifest.json';manifest=json.loads(path.read_text(encoding='utf-8'))
        manifest['files'][source.name]=hashlib.sha256(source.read_bytes()).hexdigest()
        path.write_text(json.dumps(manifest),encoding='utf-8')
        audit=self.lab.audit(r['id'])['payload']
        self.assertEqual(audit['execution_archive']['status'],'verified')
        self.assertFalse(audit['passed'])
        self.assertFalse(next(c for c in audit['checks'] if c['name']=='execution_archive_matches_registered_sources')['passed'])
        with self.assertRaisesRegex(ValueError,'quantitative claims are unavailable'):self.lab.evaluate_claims(r['id'])

    def test_mode_mismatch_and_budget_fail_before_creating_execution_artifacts(self):
        scripted=self.lab.design_resource()
        with self.assertRaisesRegex(ValueError,'backend differs'):self.lab.experiment_resource(scripted['id'],live=True)
        hosted=self.lab.design_resource(live=True)
        with patch.object(self.lab,'harness',side_effect=AssertionError('must not call model')):
            with self.assertRaisesRegex(ValueError,'remaining cap'):self.lab.experiment_resource(hosted['id'],live=True,job_id='over-cap')
        self.assertFalse((self.lab.settings.runtime/'runs'/'over-cap').exists())
        self.assertEqual(self.lab.store.usage()['calls'],0)

    def test_existing_result_directory_is_preserved(self):
        p=self.lab.design_resource();r=self.lab.experiment_resource(p['id'],job_id='resource-once')
        raw=Path(r['payload']['artifact_directory'])/'report.json';before=raw.read_bytes()
        with self.assertRaisesRegex(ValueError,'already exists'):self.lab.experiment_resource(p['id'],job_id='resource-once')
        self.assertEqual(raw.read_bytes(),before)


if __name__=='__main__':unittest.main()
