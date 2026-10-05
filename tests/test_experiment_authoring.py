"""Approved authored worlds reach runners without parameter substitution."""
import tempfile
import unittest
from pathlib import Path
from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab
from tests.test_environment_authoring import proposal,review


class ExperimentAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.lab=Lab(Settings(root=Path(self.tmp.name)))

    def blueprint(self,p):
        return self.lab.construct_environment(proposal=p,fit_review=review(p))

    def test_all_compatible_worlds_register_execute_replay_and_check_facts_without_calls(self):
        runners={'shared_artifact_coordination':self.lab.experiment,
            'provenance_diffusion':self.lab.experiment_network,'complementary_information':self.lab.experiment_complementary}
        for kind,runner in runners.items():
            with self.subTest(kind=kind):
                p=proposal(kind)
                if kind=='shared_artifact_coordination':p['parameters']['valid_probability']=.4
                elif kind=='provenance_diffusion':p['parameters']['source_reliability']=.6
                else:p['parameters']['modulus']=31
                world=self.blueprint(p)
                protocol=self.lab.register_blueprint(world['id'],seed=5521)
                self.assertEqual(protocol['payload']['environment_blueprint_ref']['hash'],world['hash'])
                stored=protocol['payload']['protocol']
                actual=stored.get('environment') or next(iter(stored['environments'].values()))
                self.assertEqual(actual,world['payload']['spec'])
                result=runner(protocol['id'],job_id='authored-'+kind)
                self.assertEqual(result['payload']['status'],'complete')
                self.assertTrue(self.lab.audit(result['id'])['payload']['passed'])
                audit=self.lab.evaluate_claims(result['id'])['payload']
                self.assertTrue(audit['audit']['all_executable_claims_supported'])
        self.assertEqual(self.lab.store.usage()['calls'],0)

    def test_review_pending_or_blocked_world_cannot_register(self):
        world=self.lab.construct_environment(proposal=proposal())
        with self.assertRaisesRegex(ValueError,'approving fit review'):self.lab.register_blueprint(world['id'])
        self.assertEqual(self.lab.store.list('complementary_protocol'),[])

    def test_custom_graph_is_not_substituted_with_a_builtin_graph(self):
        p=proposal();p['parameters'].update(topology='custom',custom_edges=[['agent-0','agent-1']])
        world=self.blueprint(p)
        self.assertEqual(world['payload']['experiment_eligibility'],'approved_analogue')
        with self.assertRaisesRegex(ValueError,'no graph substitution'):self.lab.register_blueprint(world['id'])

    def test_nondefault_message_cap_is_not_silently_discarded(self):
        p=proposal();p['parameters']['max_messages_per_agent']=0
        world=self.blueprint(p)
        with self.assertRaisesRegex(ValueError,'world parameters'):self.lab.register_blueprint(world['id'])
        self.assertEqual(self.lab.store.list('complementary_protocol'),[])

    def test_changed_implementation_or_proposal_requires_a_new_review(self):
        world=self.blueprint(proposal());payload=world['payload']
        payload['environment_code_hashes']['environment_authoring.py']='0'*64
        changed=self.lab.store.put('environment_blueprint',payload,world['id'])
        with self.assertRaisesRegex(ValueError,'implementation changed'):self.lab.register_blueprint(changed['id'])

if __name__=='__main__':unittest.main()
