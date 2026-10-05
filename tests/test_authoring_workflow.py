"""Host source pins and model-role reviews stay separate from world validity."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab
from swarm_lab.environment_authoring import blueprint_fingerprint
from swarm_lab.authoring_workflow import provider_schema
from tests.test_environment_authoring import proposal,review


class AuthoringWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.lab=Lab(Settings(root=Path(self.tmp.name)))
        self.dataset=self.lab.store.put('dataset',{'messages':[{'id':'m1','content':'Wait for an owned handoff.'}],'scope':{}})
        self.discovery=self.lab.store.put('discovery',{'graph':{'edges':[]},'candidates':[]})
        self.behavior=self.lab.store.put('behavior',{'name':'Candidate','status':'candidate','evidence_ids':['m1'],
            'source_refs':{kind:{k:o[k] for k in ('id','version','hash')} for kind,o in (('dataset',self.dataset),('discovery',self.discovery))}})

    def test_explicit_blueprint_cannot_silently_drop_trusted_browser_requirement(self):
        p=proposal();r=self.lab.construct_environment(proposal=p,required_capabilities=['browser_tools'])
        self.assertEqual(r['payload']['construction_status'],'unsupported')
        self.assertIn('browser_tools',r['payload']['missing_capabilities'])
        self.assertEqual(self.lab.store.usage()['calls'],0)

    def test_live_role_wiring_materializes_exact_pins_then_binds_review(self):
        p=proposal();p['observed_facts']=[{'statement':'Waiting language was recorded.',
            'source_ids':[self.dataset['id']],'evidence_ids':['m1']}]
        def role(name,task,schema,*args):
            if name=='environment-builder':
                self.assertEqual(schema['properties']['source_refs']['maxItems'],0)
                self.assertEqual(schema['properties']['observed_facts']['items']['properties']['evidence_ids']['minItems'],1)
                self.assertIn(self.dataset['id'],schema['properties']['observed_facts']['items']['properties']['source_ids']['items']['enum'])
                return copy.deepcopy(p)
            self.assertEqual(name,'causal-methodologist')
            signature=task['reviewed_blueprint_hash']
            self.assertEqual(schema['properties']['reviewed_blueprint_hash']['enum'],[signature])
            return review(reviewed_blueprint_hash=signature)
        agent=Mock();agent.run.side_effect=role
        with patch('swarm_lab.authoring_workflow.ResearchAgents',return_value=agent):
            r=self.lab.construct_environment(behavior_id=self.behavior['id'],live=True)
        self.assertEqual(r['payload']['construction_status'],'compiled')
        self.assertEqual(r['payload']['experiment_eligibility'],'approved_analogue')
        self.assertEqual(len(r['payload']['source_refs']),3)
        self.assertEqual(r['payload']['raw_builder_output']['source_refs'],[])
        self.assertEqual(r['payload']['source_verification']['status'],'verified_object_versions_and_record_membership')

    def test_uncited_dataset_observation_retains_builder_and_never_calls_reviewer(self):
        p=proposal();p['observed_facts']=[{'statement':'Waiting language was recorded.',
            'source_ids':[self.dataset['id']],'evidence_ids':[]}]
        agent=Mock();agent.run.return_value=p
        with patch('swarm_lab.authoring_workflow.ResearchAgents',return_value=agent):
            result=self.lab.construct_environment(behavior_id=self.behavior['id'],live=True)
        self.assertEqual(agent.run.call_count,1)
        self.assertEqual(result['payload']['construction_status'],'invalid_blueprint')
        self.assertEqual(result['payload']['experiment_eligibility'],'blocked')
        attempt=self.lab.store.list('environment_construction_attempt')[0]
        self.assertEqual(attempt['payload']['raw_builder_output'],p)
        self.assertIn('Dataset observation claims require specific evidence record IDs',result['payload']['errors'])

    def test_transport_failure_after_builder_preserves_materialized_proposal(self):
        agent=Mock();agent.run.side_effect=[proposal(),RuntimeError('simulated review transport failure')]
        with patch('swarm_lab.authoring_workflow.ResearchAgents',return_value=agent):
            with self.assertRaises(RuntimeError):self.lab.construct_environment(research_question='Synthetic sharing',live=True)
        attempt=self.lab.store.list('environment_construction_attempt')[0]['payload']
        self.assertEqual(attempt['status'],'failed');self.assertEqual(attempt['failed_phase'],'reviewer')
        self.assertEqual(attempt['initial_compilation']['construction_status'],'compiled')
        self.assertIn('materialized_proposal',attempt)
        self.assertEqual(self.lab.store.list('environment_blueprint'),[])

    def test_existing_source_pins_remain_visible_in_explicit_compilation(self):
        p=proposal();p['source_refs']=[{k:self.dataset[k] for k in ('kind','id','version','hash')}]
        p['observed_facts']=[{'statement':'A source record exists.','source_ids':[self.dataset['id']],'evidence_ids':['m1']}]
        r=self.lab.construct_environment(proposal=p)
        self.assertEqual(r['payload']['source_refs'],p['source_refs'])
        self.assertEqual(r['payload']['experiment_eligibility'],'needs_review')

    def test_provider_projection_does_not_weaken_authoritative_schema(self):
        from swarm_lab.environment_authoring import schema_for_capabilities
        schema=schema_for_capabilities()['builder_schema'];mapped=provider_schema(schema)
        self.assertIn('uniqueItems',schema['properties']['required_capabilities'])
        self.assertNotIn('uniqueItems',mapped['properties']['required_capabilities'])
        p=proposal();p['required_capabilities']=['resettable_state']*2
        r=self.lab.construct_environment(proposal=p)
        self.assertEqual(r['payload']['construction_status'],'invalid_blueprint')

    def test_provider_eliminates_only_patterns_implied_by_exact_enum(self):
        schema={'type':'string','pattern':'[0-9a-f]{64}','enum':['a'*64]}
        self.assertNotIn('pattern',provider_schema(schema))
        self.assertIn('pattern',schema)
        self.assertIn('pattern',provider_schema({**schema,'enum':['not-a-hash']}))

    def test_resume_reviews_only_the_unchanged_saved_world_and_is_idempotent(self):
        agent=Mock();agent.run.side_effect=[proposal(),RuntimeError('review interrupted')]
        with patch('swarm_lab.authoring_workflow.ResearchAgents',return_value=agent):
            with self.assertRaises(RuntimeError):self.lab.construct_environment(research_question='Sharing',live=True)
        attempt=self.lab.store.list('environment_construction_attempt')[0]
        saved=copy.deepcopy(attempt['payload']['materialized_proposal'])
        resumed=Mock()
        resumed.run.side_effect=lambda name,task,*args:review(reviewed_blueprint_hash=task['reviewed_blueprint_hash'])
        with patch('swarm_lab.authoring_workflow.ResearchAgents',return_value=resumed):
            result=self.lab.resume_environment_review(attempt['id'],live=True)
            again=self.lab.resume_environment_review(attempt['id'],live=True)
        self.assertEqual(result['id'],again['id']);self.assertEqual(resumed.run.call_count,1)
        self.assertEqual(resumed.run.call_args.args[0],'causal-methodologist')
        self.assertEqual(result['payload']['proposed_blueprint'],saved)
        self.assertEqual(result['payload']['experiment_eligibility'],'approved_analogue')
        self.assertEqual(self.lab.store.get(attempt['id'])['payload']['prior_failure']['error'],'review interrupted')


if __name__=='__main__':unittest.main()
