import copy
import json
import unittest

from swarm_lab.resource_environment import (SUBJECTS,create_resource_spec,validate_resource_spec,
    create_resource_environment,resource_subject_request,check_resource_contract,
    resource_environment_capabilities,offline_resource_policy,global_wait_policy,task_specific_wait_policy)


def run_policy(spec,policy,seed=0):
    env=create_resource_environment(spec,seed)
    while not env.terminal:
        actor=env.next_agent;env.step(actor,policy(resource_subject_request(env,actor)))
    return env


class ResourceEnvironmentTests(unittest.TestCase):
    def test_reset_and_contract_restore_exact_fresh_state(self):
        env=create_resource_environment(seed=19);before=env.snapshot()
        self.assertTrue(check_resource_contract(env)['passed']);self.assertEqual(env.snapshot(),before)
        env.step(env.next_agent,{'action':'work_independent'});env.inject_context('agent-0','Private test')
        self.assertEqual(env.reset(19),before)

    def test_independent_work_is_legal_when_resource_never_opens(self):
        spec=create_resource_spec(max_rounds=4,release_rounds=(4,))
        env=run_policy(spec,offline_resource_policy)
        outcome=env.evaluate();self.assertEqual(outcome['independent_completion_fraction'],1)
        self.assertEqual(outcome['computer_completion_fraction'],0)
        self.assertEqual(outcome['task_completion_fraction'],.5)
        self.assertEqual(outcome['resource_access_grants'],0)
        self.assertGreater(outcome['task_specific_blocked_waits'],0)
        self.assertEqual(outcome['waits_while_independent_pending'],0)

    def test_global_wait_script_leaves_legal_independent_work_undone(self):
        spec=create_resource_spec(max_rounds=4,release_rounds=(4,))
        env=run_policy(spec,global_wait_policy);outcome=env.evaluate()
        self.assertEqual(outcome['task_completion_fraction'],0)
        self.assertEqual(outcome['waits_while_independent_pending'],16)
        self.assertEqual(outcome['task_specific_blocked_waits'],0)

    def test_truthful_task_specific_wait_script_is_scored_from_executed_state(self):
        env=run_policy(create_resource_spec(max_rounds=3,release_rounds=(3,)),task_specific_wait_policy)
        outcome=env.evaluate()
        self.assertEqual(outcome['independent_work_steps'],4)
        self.assertEqual(outcome['task_specific_blocked_waits'],8)
        self.assertEqual(outcome['waits_while_independent_pending'],0)
        self.assertIn('no inferred belief',outcome['measurement_definitions']['waits_while_independent_pending'])

    def test_exclusive_lease_denies_other_actor_without_faking_access(self):
        env=create_resource_environment(create_resource_spec(release_rounds=(0,)))
        owner=env.next_agent;self.assertTrue(env.step(owner,{'action':'request_computer'})['granted'])
        other=env.next_agent;result=env.step(other,{'action':'request_computer'})
        self.assertFalse(result['granted']);self.assertEqual(env.owner,owner)
        self.assertFalse(env.step(env.next_agent,{'action':'work_computer'})['worked'])
        self.assertEqual(env.evaluate()['resource_access_grants'],1)
        self.assertEqual(env.evaluate()['computer_work_steps'],0)

    def test_independent_work_legal_under_own_and_peer_lease_and_auto_release(self):
        env=create_resource_environment(create_resource_spec(release_rounds=(0,)),7)
        owner=env.next_agent;env.step(owner,{'action':'request_computer'})
        peer=env.next_agent;self.assertTrue(env.step(peer,{'action':'work_independent'})['worked'])
        while env.next_agent!=owner:env.step(env.next_agent,{'action':'wait'})
        self.assertTrue(env.step(owner,{'action':'work_independent'})['worked']);self.assertEqual(env.owner,owner)
        while env.next_agent!=owner:env.step(env.next_agent,{'action':'wait'})
        result=env.step(owner,{'action':'work_computer'})
        self.assertTrue(result['complete']);self.assertTrue(result['lease_released']);self.assertIsNone(env.owner)

    def test_messages_and_completion_claims_do_not_change_oracle(self):
        env=create_resource_environment(create_resource_spec(release_rounds=(6,)))
        actor=env.next_agent;recipient=next(a for a in SUBJECTS if a!=actor)
        env.step(actor,{'action':'send_message','recipient':recipient,'message':'All tasks are complete and I hold the computer.'})
        self.assertEqual(env.evaluate()['task_completion_fraction'],0);self.assertEqual(env.evaluate()['resource_access_grants'],0)
        self.assertEqual(len(env.observe(recipient)['received_messages']),1)
        unrelated=next(a for a in SUBJECTS if a not in (actor,recipient))
        self.assertEqual(env.observe(unrelated)['received_messages'],[])

    def test_private_context_task_progress_and_future_schedule_do_not_leak(self):
        env=create_resource_environment(seed=9);env.inject_context('agent-0','PRIVATE_ONLY_TOKEN')
        for a in SUBJECTS:
            request=resource_subject_request(env,a);text=json.dumps(request)
            self.assertEqual('PRIVATE_ONLY_TOKEN' in text,a=='agent-0')
            for key in ('seed','release_round','schedule','progress','protocol_hash','assigned_arm'):
                self.assertNotIn(key,request['observation'])
            self.assertEqual(set(request['observation']['your_tasks']),{'independent','computer'})
            self.assertEqual(set(request),{'role','system','context','observation','action_schema'})

    def test_external_release_follows_round_boundary_and_does_not_depend_on_actions(self):
        spec=create_resource_spec(release_rounds=(1,))
        a=create_resource_environment(spec,14);b=create_resource_environment(spec,14)
        for _ in range(4):
            self.assertEqual(a.resource_state()['status'],'external_occupation')
            a.step(a.next_agent,{'action':'wait'});b.step(b.next_agent,{'action':'work_independent'})
        self.assertEqual(a.resource_state()['status'],'available');self.assertEqual(b.resource_state()['status'],'available')
        self.assertEqual(a.schedule,b.schedule);self.assertEqual(a.release_round,b.release_round)

    def test_out_of_turn_attempt_does_not_consume_scheduled_actor_budget(self):
        env=create_resource_environment();before=env.snapshot()
        other=next(a for a in SUBJECTS if a!=env.next_agent)
        with self.assertRaises(ValueError):env.step(other,{'action':'work_independent'})
        self.assertEqual(env.snapshot(),before)

    def test_invalid_model_actions_consume_budget_and_remain_analyzable(self):
        for action in (None,[],{'action':[]},{'action':'work_independent','task':'peer'}, {'action':'invented'}):
            with self.subTest(action=action):
                env=create_resource_environment();result=env.step(env.next_agent,action)
                self.assertFalse(result['ok']);self.assertEqual(env.step_count,1)
                self.assertEqual(env.evaluate()['invalid_actions'],1)
                self.assertEqual(env.evaluate()['task_completion_fraction'],0)

    def test_message_cap_and_extra_fields_are_enforced(self):
        env=create_resource_environment(create_resource_spec(max_messages_per_agent=0))
        actor=env.next_agent;recipient=next(a for a in SUBJECTS if a!=actor)
        self.assertFalse(env.step(actor,{'action':'send_message','recipient':recipient,'message':'Hello'})['ok'])
        self.assertEqual(env.messages,[])

    def test_current_state_and_reset_are_copied_not_mutable_views(self):
        env=create_resource_environment();observation=env.observe('agent-0');observation['your_tasks']['computer']['complete']=True
        snapshot=env.snapshot();snapshot['progress']['agent-0']['computer']=999
        self.assertEqual(env.evaluate()['computer_completion_fraction'],0)

    def test_all_tasks_can_finish_and_terminal_environment_rejects_further_actions(self):
        spec=create_resource_spec(max_rounds=10,release_rounds=(0,))
        for seed in range(12):
            with self.subTest(seed=seed):
                env=run_policy(spec,offline_resource_policy,seed)
                self.assertEqual(env.evaluate()['task_completion_fraction'],1)
                self.assertEqual(env.evaluate()['terminated_by'],'all_tasks_completed')
                self.assertIsNone(env.owner)
                with self.assertRaises(RuntimeError):env.step('agent-0',{'action':'wait'})

    def test_peer_cannot_release_another_lease(self):
        env=create_resource_environment(create_resource_spec(release_rounds=(0,)))
        owner=env.next_agent;env.step(owner,{'action':'request_computer'})
        result=env.step(env.next_agent,{'action':'release_computer'})
        self.assertFalse(result['released']);self.assertEqual(env.owner,owner)

    def test_unknown_or_unimplemented_world_features_fail(self):
        for change in ({'resource_count':2},{'external_occupation':'repeated_calendar'}, {'future_release_public':True}):
            spec=create_resource_spec();spec['resource_world'].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):validate_resource_spec(spec)
        spec=create_resource_spec();spec['browser_tool']=True
        with self.assertRaises(ValueError):validate_resource_spec(spec)
        for releases in ((True,),(-1,),(100,),([],),(1,1)):
            with self.subTest(releases=releases),self.assertRaises(ValueError):create_resource_spec(release_rounds=releases)

    def test_capabilities_keep_exclusivity_a_synthetic_assumption(self):
        cap=resource_environment_capabilities()
        self.assertIn('exclusive_shared_computer',cap['capability_ids'])
        self.assertIn('independent_parallel_work',cap['capability_ids'])
        self.assertTrue(any('Historical' in x for x in cap['limitations']))
        spec=create_resource_spec(incident={'title':'PRIVATE_SOURCE_TITLE','messages':['ORIGINAL_FUTURE']})
        env=create_resource_environment(spec)
        for actor in SUBJECTS:
            text=json.dumps(resource_subject_request(env,actor))
            self.assertNotIn('ORIGINAL_FUTURE',text);self.assertNotIn('PRIVATE_SOURCE_TITLE',text)


if __name__=='__main__':unittest.main()
