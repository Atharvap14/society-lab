"""Capability-driven construction, provenance and independent-fit gates."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from swarm_lab.environment_authoring import (capability_catalog,schema_for_capabilities,compile_blueprint,blueprint_fingerprint)
from swarm_lab.environment_api import create
from swarm_lab.store import Store


def proposal(template='complementary_information'):
    schemas=capability_catalog()['implementations'][template]['parameter_schema']['properties']
    return {'schema_version':'1.0','title':'Synthetic analogue','template':template,
        'parameters':{key:None for key in schemas},'required_capabilities':['resettable_state'],
        'missing_capabilities':[],'source_refs':[],'observed_facts':[],
        'analogue_inventions':[{'name':'Synthetic task','description':'Fixed small-agent world and generator are invented.',
            'reason_for_invention':'A minimal observable analogue, not a replay of original tools.'}],
        'mechanism_hypothesis':'Information sharing may alter coordinated outcomes.',
        'fit_rationale':'Only an exploratory analogue of a proposed behavioral question.',
        'unmodeled_features':['Persistent cross-day memory is absent.'],'unsupported_reason':'',
        'historical_fidelity':'unestablished'}


def review(p=None,**changes):
    r={'reviewed_blueprint_hash':blueprint_fingerprint(p or proposal()),
        'decision':'approve_analogue','mechanism_fit':'plausible_analogue','rationale':'Plausible bounded analogue only.',
        'blocking_reasons':[],'missing_capabilities':[],'source_misstatements':[],'required_changes':[],
        'limitations':['No historical mechanism is identified.'],'historical_fidelity':'unestablished'}
    r.update(changes);return r


class EnvironmentAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.store=Store(self.root/'lab.sqlite3')
        self.dataset=self.store.put('dataset',{'messages':[{'id':'m1','content':'A source observation.'}]})

    def with_fact(self,p):
        p['source_refs']=[{k:self.dataset[k] for k in ('kind','id','version','hash')}]
        p['observed_facts']=[{'statement':'A source message exists.','source_ids':[self.dataset['id']],'evidence_ids':['m1']}]
        return p

    def test_capability_selection_is_not_a_closed_behavior_ontology(self):
        packet=schema_for_capabilities(['private_complementary_residues','neighbor_multicast'])
        self.assertEqual(packet['eligible_templates'],['complementary_information'])
        self.assertEqual(packet['unknown_capabilities'],[])
        self.assertIn('not a closed ontology',packet['catalog']['ontology_policy'])
        packet=schema_for_capabilities(['novel_market_clearing_mechanism'])
        self.assertEqual(packet['eligible_templates'],[])
        self.assertEqual(packet['unknown_capabilities'],['novel_market_clearing_mechanism'])

    def test_each_template_compiles_and_preserves_reset_and_observation_boundary(self):
        for template in ('shared_artifact_coordination','provenance_diffusion','complementary_information'):
            with self.subTest(template=template):
                p=proposal(template);result=compile_blueprint(p,fit_review=review(p))
                self.assertEqual(result['construction_status'],'compiled')
                self.assertEqual(result['experiment_eligibility'],'approved_analogue')
                self.assertEqual(result['spec']['kind'],template)
                self.assertTrue(result['boundary_audit']['passed']);self.assertEqual(result['boundary_audit']['model_calls'],0)
                self.assertEqual(result['historical_fidelity'],'unestablished')
                env=create(result['spec'],19);before=env.snapshot()
                env.inject_context(result['spec']['agents'][0],'A private probe')
                self.assertEqual(env.reset(19),before)

    def test_browser_memory_and_arbitrary_roles_do_not_silently_degrade(self):
        for required in ('browser_tools','persistent_cross_run_memory','custom_roles','arbitrary_population'):
            with self.subTest(required=required):
                p=proposal();p['required_capabilities'].append(required)
                result=compile_blueprint(p,fit_review=review())
                self.assertEqual(result['construction_status'],'unsupported')
                self.assertIn(required,result['missing_capabilities'])
                self.assertIsNone(result['spec']);self.assertEqual(result['experiment_eligibility'],'blocked')

    def test_builder_cannot_drop_trusted_caller_requirements(self):
        p=proposal()
        result=compile_blueprint(p,required_capabilities=['browser_tools'],fit_review=review())
        self.assertEqual(result['requirements_omitted_by_builder'],['browser_tools'])
        self.assertEqual(result['construction_status'],'unsupported')
        self.assertEqual(result['missing_capabilities'],['browser_tools'])

    def test_known_feature_missing_from_selected_template_is_explicit(self):
        p=proposal('shared_artifact_coordination');p['required_capabilities'].append('neighbor_multicast')
        result=compile_blueprint(p)
        self.assertEqual(result['construction_status'],'unsupported')
        self.assertIn('neighbor_multicast',result['missing_capabilities'])

    def test_unknown_parameters_and_control_metadata_never_enter_subject_spec(self):
        for key,value in (('roles',['customer','brand']),('browser_url','https://example.test'),
                ('persistent_memory',True),('seed',11),('oracle_total',12),('assigned_arm','source_thought')):
            with self.subTest(key=key):
                p=proposal();p['parameters'][key]=value
                result=compile_blueprint(p)
                self.assertEqual(result['construction_status'],'invalid_blueprint')
                self.assertIn('parameter:'+key,result['missing_capabilities'])
                self.assertIsNone(result['spec'])
                self.assertTrue(any(key in error for error in result['errors']))

    def test_generated_code_is_rejected_without_execution(self):
        sentinel=self.root/'should-not-exist.txt'
        p=proposal();p['generated_code']=f"open({str(sentinel)!r},'w').write('bad')"
        result=compile_blueprint(p)
        self.assertEqual(result['construction_status'],'invalid_blueprint')
        self.assertFalse(sentinel.exists());self.assertIsNone(result['spec'])

    def test_source_versions_and_message_membership_are_verified_without_upgrading_truth(self):
        p=self.with_fact(proposal())
        self.store.put('dataset',{'messages':[{'id':'new','content':'Later import'}]},self.dataset['id'])
        result=compile_blueprint(p,store=self.store,fit_review=review(p))
        self.assertEqual(result['construction_status'],'compiled')
        self.assertEqual(result['source_verification']['status'],'verified_object_versions_and_record_membership')
        self.assertEqual(result['source_verification']['source_refs'][0]['version'],1)
        self.assertEqual(result['source_verification']['semantic_fact_truth'],'not_certified')
        self.assertEqual(result['original_observation_claims'],p['observed_facts'])
        self.assertEqual(result['analogue_inventions'],p['analogue_inventions'])

    def test_forged_source_hash_or_missing_records_are_rejected(self):
        p=self.with_fact(proposal());p['source_refs'][0]['hash']='0'*64
        self.assertEqual(compile_blueprint(p,store=self.store)['construction_status'],'invalid_blueprint')
        p=self.with_fact(proposal());p['observed_facts'][0]['evidence_ids']=['not-in-pinned-source']
        result=compile_blueprint(p,store=self.store)
        self.assertEqual(result['construction_status'],'invalid_blueprint')
        self.assertIsNone(result['spec'])

    def test_dataset_fact_without_record_or_unpinned_source_is_rejected(self):
        p=self.with_fact(proposal());p['observed_facts'][0]['evidence_ids']=[]
        result=compile_blueprint(p,store=self.store)
        self.assertIn('specific evidence record IDs',result['errors'][0])
        p=self.with_fact(proposal());p['observed_facts'][0]['source_ids']=['unprovided-source']
        self.assertIn('unpinned source',compile_blueprint(p,store=self.store)['errors'][0])

    def test_unretrieved_pins_cannot_be_approved_as_verified_evidence(self):
        p=self.with_fact(proposal());result=compile_blueprint(p,fit_review=review(p))
        self.assertEqual(result['construction_status'],'compiled')
        self.assertEqual(result['experiment_eligibility'],'needs_source_verification')

    def test_semantic_world_reviewer_can_block_valid_compilation(self):
        r=review(decision='block',mechanism_fit='unsupported',blocking_reasons=['Task lacks the hypothesized incentive conflict.'],
                 missing_capabilities=['strategic_private_incentives'])
        result=compile_blueprint(proposal(),fit_review=r)
        self.assertEqual(result['construction_status'],'compiled')
        self.assertTrue(result['boundary_audit']['passed'])
        self.assertEqual(result['experiment_eligibility'],'blocked')
        self.assertIn('strategic_private_incentives',result['missing_capabilities'])
        self.assertEqual(result['causal_identification'],'not_established_by_compilation')

    def test_unsupported_fit_or_required_changes_override_approval(self):
        result=compile_blueprint(proposal(),fit_review=review(mechanism_fit='unsupported'))
        self.assertEqual(result['experiment_eligibility'],'blocked')
        result=compile_blueprint(proposal(),fit_review=review(required_changes=['Revise the task abstraction.']))
        self.assertEqual(result['experiment_eligibility'],'needs_revision')
        result=compile_blueprint(proposal(),fit_review=review(mechanism_fit='undetermined'))
        self.assertEqual(result['experiment_eligibility'],'needs_review')

    def test_builder_must_declare_inventions_and_cannot_claim_historical_fidelity(self):
        p=proposal();p['analogue_inventions']=[]
        self.assertEqual(compile_blueprint(p)['construction_status'],'invalid_blueprint')
        p=proposal();p['historical_fidelity']='verified'
        result=compile_blueprint(p,fit_review=review())
        self.assertEqual(result['construction_status'],'invalid_blueprint')
        self.assertEqual(result['historical_fidelity'],'unestablished')

    def test_successful_compile_without_review_is_never_ready_for_claims(self):
        result=compile_blueprint(proposal())
        self.assertEqual(result['construction_status'],'compiled')
        self.assertEqual(result['experiment_eligibility'],'needs_review')

    def test_unknown_factory_is_an_extension_request_not_a_fallback(self):
        p=proposal();p['template']='new_auction_environment'
        result=compile_blueprint(p)
        self.assertEqual(result['construction_status'],'unsupported')
        self.assertIsNone(result['spec'])
        self.assertIn('template:new_auction_environment',result['missing_capabilities'])

    def test_explicit_custom_graph_does_not_silently_replace_declared_builtin(self):
        p=proposal();p['parameters']['custom_edges']=[]
        result=compile_blueprint(p)
        self.assertEqual(result['construction_status'],'invalid_blueprint')
        p['parameters']['topology']='custom';result=compile_blueprint(p,fit_review=review(p))
        self.assertEqual(result['construction_status'],'compiled')
        self.assertEqual(result['spec']['topology'],{'kind':'custom','directed':False,'edges':[]})

    def test_failed_boundary_check_blocks_execution_even_when_schema_valid(self):
        with patch('swarm_lab.environment_authoring._boundary_audit',return_value={'passed':False,'model_calls':0}):
            result=compile_blueprint(proposal(),fit_review=review())
        self.assertEqual(result['construction_status'],'boundary_check_failed')
        self.assertEqual(result['experiment_eligibility'],'blocked')

    def test_quoted_original_facts_and_reviewer_metadata_never_enter_subject_requests(self):
        from swarm_lab.environments import subject_request
        from swarm_lab.diffusion_environment import diffusion_subject_request
        from swarm_lab.complementary_environment import complementary_subject_request
        for template,request in (('shared_artifact_coordination',subject_request),
                ('provenance_diffusion',diffusion_subject_request),
                ('complementary_information',complementary_subject_request)):
            with self.subTest(template=template):
                p=self.with_fact(proposal(template));p['observed_facts'][0]['statement']='ORIGINAL_FUTURE_AND_HYPOTHESIS_MARKER'
                p['title']='PRIVATE_PROVENANCE_TITLE_MARKER'
                result=compile_blueprint(p,store=self.store,fit_review=review(p,rationale='PRIVATE_REVIEWER_MARKER'))
                env=create(result['spec'],0)
                for role in result['spec']['agents']:
                    text=json.dumps(request(env,role))
                    self.assertNotIn('ORIGINAL_FUTURE_AND_HYPOTHESIS_MARKER',text)
                    self.assertNotIn('PRIVATE_REVIEWER_MARKER',text)
                    self.assertNotIn('PRIVATE_PROVENANCE_TITLE_MARKER',text)
                    self.assertNotIn('assigned_arm',text);self.assertNotIn('oracle_total',text)

    def test_all_outputs_and_schemas_are_json_declarative(self):
        self.assertIsInstance(json.dumps(schema_for_capabilities()),str)
        result=compile_blueprint(proposal(),fit_review=review())
        self.assertIsInstance(json.dumps(result),str)
        self.assertEqual(set(result['environment_code_hashes']),{'environment_authoring.py','environment_api.py','complementary_environment.py'})

    def test_approval_is_bound_to_exact_blueprint_and_not_later_edits(self):
        p=proposal();r=review(p)
        p['parameters']['topology']='complete'
        result=compile_blueprint(p,fit_review=r)
        self.assertEqual(result['construction_status'],'compiled')
        self.assertEqual(result['experiment_eligibility'],'blocked')
        self.assertIn('different blueprint',result['errors'][0])
        result=compile_blueprint(p,fit_review=review(p))
        self.assertEqual(result['experiment_eligibility'],'approved_analogue')


if __name__=='__main__':unittest.main()
