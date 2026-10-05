"""Authored tool witnesses for solvability/boundaries; no scripted product subjects."""
import copy
import json
import unittest
from swarm_lab.reference_repair_environment import *


def act(env,role,action):
    while env.next_agent!=role:
        if env.terminal:raise AssertionError('Fixture budget exhausted')
        env.step(env.next_agent,{'action':'wait'})
    return env.step(role,action)


class RecoveryWorldTests(unittest.TestCase):
    def test_scoped_reset_and_paired_notes_do_not_change_truth_or_schedule(self):
        spec=create_reference_repair_spec();a=ReferenceRepairEnvironment(spec,19);b=ReferenceRepairEnvironment(spec,19)
        self.assertEqual(a.snapshot(),b.snapshot());initial=a.snapshot()
        for role in AGENTS:b.inject_context(role,'An assigned private note.')
        for key in ('documents','references','browsers','schedule','required_content'):
            self.assertEqual(initial['state'][key],b.snapshot()['state'][key])
        self.assertEqual(a.agent_ids,['ethics_owner','auditor']);self.assertEqual(a.max_steps,16)
        self.assertEqual(len(initial['state']['documents']),1)
        self.assertEqual(set(initial['state']['browsers']),set(AGENTS))
        a.step(a.next_agent,{'action':'wait'});self.assertEqual(a.reset(),initial)

    def test_initial_probe_is_declared_pre_treatment_not_subject_action(self):
        env=ReferenceRepairEnvironment(create_reference_repair_spec(),17)
        self.assertEqual(env.step_count,0)
        self.assertEqual(env.events[0]['type'],'pre_treatment_probe')
        self.assertEqual(env.events[0]['source'],'scenario_generator')
        self.assertEqual(env.observe('auditor')['your_action_history'],[])
        self.assertEqual(env.observe('auditor')['your_last_tool_result']['status_code'],404)
        self.assertEqual(env.evaluate()['reference_failures'],0)

    def test_subject_observation_excludes_truth_schedule_source_and_other_roles(self):
        env=ReferenceRepairEnvironment(create_reference_repair_spec(),22)
        request=reference_repair_subject_request(env,'auditor');text=json.dumps(request)
        for forbidden in ('power_owner','stimuli_owner','coordinator','integrator','source_grounding','historical_role_source','environment_seed','schedule'):
            self.assertNotIn(forbidden,text)
        self.assertEqual(request['context'],[])
        self.assertEqual(len(request['action_schema']['properties']['action']['enum']),10)
        self.assertEqual(request['action_schema']['properties']['recipient']['enum'],AGENTS)
        request['observation']['target_document']['title']='tampered'
        self.assertNotEqual(env.observe('auditor')['target_document']['title'],'tampered')

    def test_drive_tool_title_contract_fixes_bad_id_search_without_auto_repair(self):
        env=ReferenceRepairEnvironment(create_reference_repair_spec(),31)
        bad=env.observe('auditor')['target_document']['your_copied_reference']
        wrong=act(env,'auditor',{'action':'drive_search','query':bad.split('/')[-2]})
        self.assertEqual(wrong['matches'],[])
        proper=act(env,'auditor',{'action':'drive_search','query':'Irb Protocol'})
        self.assertEqual(len(proper['matches']),1)
        self.assertEqual(env.evaluate()[PRIMARY],0)
        act(env,'auditor',{'action':'open_url','url':proper['matches'][0]['view_url']})
        self.assertEqual(env.evaluate()[PRIMARY],1)
        self.assertEqual(env.evaluate()['canonical_reference_queued_to_checker'],0)

    def test_owner_open_or_report_or_message_does_not_score_peer_access(self):
        env=ReferenceRepairEnvironment(create_reference_repair_spec(),4)
        url=env.observe('ethics_owner')['target_document']['your_copied_reference']
        act(env,'ethics_owner',{'action':'open_url','url':url})
        act(env,'ethics_owner',{'action':'send_message','recipient':'auditor','message':url})
        act(env,'auditor',{'action':'report_status','document_key':TARGET,'status':'completed','summary':'Reported only.'})
        self.assertEqual(env.evaluate()[PRIMARY],0)
        self.assertEqual(env.evaluate()['canonical_reference_queued_to_checker'],1)
        self.assertEqual(env.evaluate()['auditor_opened_current_original'],0)
        act(env,'auditor',{'action':'open_url','url':url})
        self.assertEqual(env.evaluate()[PRIMARY],1)
        self.assertEqual(env.evaluate()['auditor_inspected_current_content'],0)
        act(env,'auditor',{'action':'inspect_document'})
        self.assertEqual(env.evaluate()['auditor_inspected_current_content'],1)

    def test_legal_owner_relay_witness_succeeds_across_independent_seeds(self):
        # This is only a CPU solvability witness; live agents choose independently.
        for seed in range(16):
            env=ReferenceRepairEnvironment(create_reference_repair_spec(),seed)
            search=act(env,'ethics_owner',{'action':'drive_search','query':'Irb Protocol'})
            act(env,'ethics_owner',{'action':'open_url','url':search['matches'][0]['view_url']})
            copied=act(env,'ethics_owner',{'action':'copy_current_url'})
            act(env,'ethics_owner',{'action':'send_message','recipient':'auditor','message':copied['copied_url']})
            received=env.observe('auditor')['received_messages'][-1]['content']
            act(env,'auditor',{'action':'open_url','url':received})
            self.assertEqual(env.evaluate()[PRIMARY],1,seed)

    def test_direct_inbox_scoping_and_invalid_channels_consume_turn(self):
        env=ReferenceRepairEnvironment(create_reference_repair_spec(),6)
        act(env,'ethics_owner',{'action':'send_message','recipient':'auditor','message':'A recorded direct message.'})
        self.assertEqual(len(env.observe('auditor')['received_messages']),1)
        self.assertEqual(env.observe('ethics_owner')['received_messages'],[])
        step=env.step_count;act(env,env.next_agent,{'action':'send_message','recipient':'all','message':'Not allowed.'})
        self.assertEqual(env.step_count,step+1)
        self.assertEqual(len(env.base.messages),1)
        with self.assertRaises(ValueError):env.observe('power_owner')

    def test_nonfinite_unsupported_actions_and_pending_navigation_are_honest(self):
        env=ReferenceRepairEnvironment(create_reference_repair_spec(),7)
        role=env.next_agent;receipt=env.step(role,{'action':'recreate_document','content':{}})
        self.assertFalse(receipt['ok']);self.assertEqual(len(env.base.documents),1)
        role=env.next_agent;env.step(role,{'action':'wait','extra':float('nan')})
        self.assertEqual(env.events[-1]['action'],{'invalid_output':'nonfinite_or_unbounded_action'})
        canonical=env.observe('ethics_owner')['target_document']['your_copied_reference']
        act(env,'auditor',{'action':'type_url','url':canonical});self.assertEqual(env.evaluate()[PRIMARY],0)
        act(env,'auditor',{'action':'navigate'});self.assertEqual(env.evaluate()[PRIMARY],1)
        json.dumps(env.snapshot(),allow_nan=False)

    def test_oracle_checks_current_content_and_current_profile_not_just_receipt(self):
        env=ReferenceRepairEnvironment(create_reference_repair_spec(),9)
        canonical=env.observe('ethics_owner')['target_document']['your_copied_reference']
        act(env,'auditor',{'action':'open_url','url':canonical});self.assertEqual(env.evaluate()[PRIMARY],1)
        act(env,'auditor',{'action':'switch_session','profile':'incognito'})
        self.assertEqual(env.evaluate()['auditor_opened_current_original'],1)
        self.assertEqual(env.evaluate()[PRIMARY],0)
        env.base.documents[env.base.originals[TARGET]]['content']['consent']='changed'
        self.assertEqual(env.evaluate()['current_content_correct'],0)

    def test_unsupported_specs_and_seed_types_fail_closed(self):
        original=create_reference_repair_spec()
        for field,value in [('max_rounds',8.0),('active_agents',['ethics_owner','auditor','power_owner']),('tools',['wait'])]:
            spec=copy.deepcopy(original);spec[field]=value
            with self.assertRaises(ValueError):validate_reference_repair_spec(spec)
        for seed in (True,1.0,-1):
            with self.assertRaises(ValueError):ReferenceRepairEnvironment(original,seed)

if __name__=='__main__':unittest.main()
