"""Recovery product gates and cold connection with fixture-only provider I/O."""
import copy
import io
import json
import tempfile
import unittest
from unittest.mock import patch

from swarm_lab.guide_assistant import _authorized_operations, guide_chat, _study_summary, _source_search, _persist_workspace_reply
from swarm_lab.guide_tools import execute_guide_tool,guide_tool_schemas
from swarm_lab.lab_workspace import chat_snapshot
from tests.test_guide_workspace import working_lab,request,response
from tests.test_guide_agent_tools import call_response
from tests.test_guide_assistant import exact,inventory
from tests import test_village_product_gates as village_ui


class RecoveryProductTests(unittest.TestCase):
    def test_connect_is_explicit_and_does_not_authorize_paid_research_or_subjects(self):
        message='Connect the saved AI Village September source to this chat. Read reported broken links. Do not plan or run.'
        self.assertEqual(_authorized_operations(message),{'connect_source'})
        for text in ['Could a connection help?', 'Explain the quote "connect the source".', 'Connect the source. Do not connect it yet.']:
            self.assertEqual(_authorized_operations(text),set())
        self.assertEqual(_authorized_operations(message,proactive=True),set())
        schema=guide_tool_schemas({'save_village_recovery_plan'})[0]
        self.assertEqual(schema['name'],'save_village_recovery_plan')
        self.assertNotIn('scripted',json.dumps(schema).lower())

    def test_real_cold_chat_connects_exact_source_and_reads_it_without_foreign_chat_or_subject_job(self):
        with tempfile.TemporaryDirectory() as directory:
            lab,active,borrowed,dataset,_,_=working_lab(directory)
            payload=copy.deepcopy(dataset['payload'])
            for i,row in enumerate(payload['messages']):row.update(agent_id='agent-'+str(i),agent_name='Agent '+str(i))
            payload['messages'][0]['content']='Introductory upload note. '+ 'x'*800+' The original link returns 404; canonical reference requested.'
            dataset=lab.store.put('dataset',payload,dataset['id'])
            before=chat_snapshot(lab,borrowed); before_jobs=lab.store.jobs();seen=[]
            def provider(req,timeout):
                payload=json.loads(req.data);seen.append(payload)
                if len(seen)==1:
                    data=json.loads(payload['input'][0]['content'])['saved_data']
                    self.assertIn(exact(dataset),[row['ref'] for row in data['available_dataset_sources']])
                    self.assertEqual(payload['tool_choice'],{'type':'function','name':'connect_source'})
                    self.assertNotIn('run_experiment',[row['name'] for row in payload['tools']])
                    return call_response(payload,'connect_source',{'source_ref':exact(dataset)})
                receipts=[json.loads(row['output']) for row in payload['input'] if row.get('type')=='function_call_output']
                self.assertEqual(receipts[0]['updated_context']['dataset_ref'],exact(dataset))
                self.assertIn('observational_source_read',receipts[0]);self.assertTrue(receipts[0]['observational_source_read']['excerpts'])
                if len(seen)==2:
                    self.assertEqual(payload['tool_choice'],{'type':'function','name':'search_source_messages'})
                    return call_response(payload,'search_source_messages',{'dataset_ref':exact(dataset),'terms':['404','page not found','broken','canonical'],'limit':5},identity='search-2')
                found=receipts[-1];self.assertEqual(found['per_term_message_counts']['404'],1)
                self.assertIn('404',found['excerpts'][0]['text_excerpt']);self.assertGreater(found['excerpts'][0]['excerpt_start'],0)
                self.assertEqual(found['retained_messages_scanned'],len(payload_copy['messages']))
                return response(payload,answer='The exact source contains a reported 404; its original browser state remains unverified.',sources=[found['excerpts'][0]['source_id']])
            payload_copy=copy.deepcopy(payload)
            with patch('swarm_lab.harness.urllib.request.urlopen',side_effect=provider):
                result=guide_chat(lab,request(active,'Connect the saved source. Read its reported links. Do not plan or run.'),inventory=inventory(lab),queue_submit=lambda *_:self.fail('No paid research job authorized'))
            with lab.store.connect() as c:diagnostics=[json.loads(row[0]) for row in c.execute("SELECT payload FROM traces WHERE payload LIKE '%guide_answer_unavailable%'").fetchall()]
            self.assertEqual(result['status'],'ok',diagnostics or result)
            self.assertEqual(result['updated_context']['dataset_ref'],exact(dataset))
            self.assertEqual(len(seen),3)
            self.assertEqual(chat_snapshot(lab,borrowed),before)
            self.assertEqual(lab.store.jobs(),before_jobs)
            linked={row['ref']['id'] for row in chat_snapshot(lab,active)['artifacts']}
            self.assertIn(dataset['id'],linked)
            self.assertFalse(any(row['kind'].endswith('experiment') for row in chat_snapshot(lab,active)['artifacts']))

    def test_literal_search_rejects_unseen_source_and_reports_bounded_dataset_absence_only(self):
        with tempfile.TemporaryDirectory() as directory:
            lab,_,_,dataset,_,_=working_lab(directory)
            refs={'source':{'kind':'dataset','object_ref':exact(dataset)}}
            args={'dataset_ref':exact(dataset),'terms':['not-in-fixture'],'limit':2}
            packet=_source_search(lab,args,refs)
            self.assertEqual(packet['matching_messages'],0);self.assertEqual(packet['excerpts'],[])
            self.assertEqual(packet['retained_messages_scanned'],len(dataset['payload']['messages']))
            self.assertIn('not the entire historical archive',packet['scope'])
            with self.assertRaises(ValueError):_source_search(lab,args,{})
            for bad in [True,1.0,0,9]:
                with self.assertRaises(ValueError):_source_search(lab,{**args,'limit':bad},refs)

    def test_wrapper_only_citation_resolves_exact_current_result_without_working_state_change(self):
        with tempfile.TemporaryDirectory() as directory:
            lab,active,_,dataset,_,_=working_lab(directory)
            payload=village_ui.village_payload();payload['protocol']['environment']['kind']='single_document_reference_repair';payload['protocol']['primary_outcome']='verified_repaired_reference'
            payload['source_refs']['dataset_ref']=exact(dataset);payload['protocol']['grounding']['source_ref']=exact(dataset)
            record=lab.store.put('village_recovery_experiment',payload)
            wrapper=lab.store.put('guided_result',{'result_ref':exact(record)})
            before=copy.deepcopy(chat_snapshot(lab,active)['state']);jobs=lab.store.jobs()
            request={'active_chat_id':active,'request_id':'explain-wrapper','current_context':{'result_ref':exact(record)}}
            answer={'status':'ok','answer_source':'ai','answer':'Both conditions solved the task; the effect remains uncertain.','actions':[],
                'sources':[{'id':'source:'+wrapper['id']+':v1','kind':'guided_result','object_ref':exact(wrapper),'message_id':None}],'plan_draft':None}
            saved=_persist_workspace_reply(lab,request,answer,'fixture-user',{})
            self.assertEqual(saved['result_context_ref'],exact(record));self.assertEqual(saved['scientific_report']['via_execution_ref'],exact(wrapper))
            self.assertTrue(any(row['object_ref']==exact(record) for row in saved['sources']))
            self.assertEqual(chat_snapshot(lab,active)['state'],before);self.assertEqual(lab.store.jobs(),jobs)
            raw_mention={**request,'request_id':'explicit-raw-mention','current_context':{},'mentioned_context':[{'kind':'artifact','ref':exact(record)}]}
            mentioned=copy.deepcopy(answer);mentioned.pop('result_context_ref',None);mentioned.pop('scientific_report',None)
            mentioned['sources']=[{'id':'source:'+record['id']+':v1','kind':record['kind'],'object_ref':exact(record),'message_id':None}]
            saved=_persist_workspace_reply(lab,raw_mention,mentioned,'fixture-user',{})
            self.assertEqual(saved['result_context_ref'],exact(record));self.assertEqual(chat_snapshot(lab,active)['state'],before)
            unrelated=lab.store.put('village_recovery_experiment',payload)
            wrong=copy.deepcopy(answer);wrong.pop('result_context_ref',None);wrong.pop('scientific_report',None);wrong['sources']=wrong['sources'][:1]
            saved=_persist_workspace_reply(lab,{**request,'request_id':'other-current','current_context':{'result_ref':exact(unrelated)}},wrong,'fixture-user',{})
            self.assertNotIn('result_context_ref',saved)

    def test_recovery_count_uses_single_link_outcome_never_old_broad_goal_or_boolean(self):
        p={'status':'complete','protocol':{'environment':{'kind':'single_document_reference_repair'}},'runs':[
            {'run_id':'a','status':'complete','arm':'neutral_note','outcomes':{'verified_repaired_reference':0,'verified_usable_project':1}},
            {'run_id':'b','status':'complete','arm':'canonical_check','outcomes':{'verified_repaired_reference':1,'verified_usable_project':0}}],
            'analysis':{'arms':{'neutral_note':{'n':1,'success_rate':0},'canonical_check':{'n':1,'success_rate':1}}}}
        r={'id':'new','version':1,'kind':'village_recovery_experiment','payload':p}
        value=_study_summary(r)['whole_team_success_counts'];self.assertTrue(value['available']);self.assertEqual(value['arm_counts']['canonical_check']['correct'],1)
        p['runs'][1]['outcomes']['verified_repaired_reference']=True
        self.assertFalse(_study_summary(r)['whole_team_success_counts']['available'])

    def test_ui_recovery_has_distinct_goal_and_exact_source_gate_no_legacy_mixture(self):
        vm=village_ui.VillageProductGateTests();vm.node(r"""
const env=setup();await env.workspace.initialize();const r=village();r.kind='village_recovery_experiment';r.payload.family='single_document_reference_repair';r.payload.protocol.environment.kind='single_document_reference_repair';r.payload.protocol.primary_outcome='verified_repaired_reference';
for(const row of r.payload.runs){row.outcomes.verified_repaired_reference=row.arm==='canonical_check'?1:0;row.outcomes.verified_usable_project=1-row.outcomes.verified_repaired_reference;row.outcomes.per_document=[{document_key:'irb-protocol',content_correct:true,checker_current_profile_authorized:true,checker_opened_current_version:row.arm==='canonical_check'}];}
assert(SocietyExperience.validVillageStudy(r));add(env,r);env.experience.state.study=pin(r);let html=await env.experience.render('findings');assert(html.includes('Single-document reference recovery'));assert(html.includes('auditor'));assert(!html.includes('Four original documents'));assert(html.includes('1 / 1'));assert(html.includes('0 / 1'));assert(!html.includes('4 / 4'));
const bad=clone(r);bad.payload.protocol.primary_outcome='verified_usable_project';assert(!SocietyExperience.validVillageStudy(bad));assert.equal(env.log.jobs.length,0);
""")

    def test_open_narrow_saved_plan_and_world_preserves_draft_and_exact_family(self):
        vm=village_ui.VillageProductGateTests();vm.node(r"""
const env=setup();await env.workspace.initialize();const source=clone(refs.source),plan=env.records.find(r=>r.id===refs.plan.id&&r.version===refs.plan.version),world={id:'guided-simulator-recovery-unit',version:1,hash:'4'.repeat(64),kind:'guided_simulator'};
const fixture=village().payload;plan.payload={family:'single_document_reference_repair',question:'Can the auditor open this original?',control_text:'Neutral note',treatment_text:'Check canonical reference',source_refs:{dataset_ref:source},hypothesis:fixture.hypothesis,fidelity:fixture.fidelity};
world.payload={family:plan.payload.family,plan_ref:pin(plan),source_refs:{dataset_ref:source},environment:{kind:plan.payload.family,agents:['ethics_owner','auditor']},hypothesis:fixture.hypothesis,fidelity:fixture.fidelity};
add(env,world);
const before=JSON.stringify(env.experience.state.draft);await env.experience.openSavedArtifact(clone(plan));let html=await env.experience.render('plan');assert(html.includes('owner and auditor'));assert(html.includes('current version'));assert.equal(JSON.stringify(env.experience.state.draft),before);
await env.experience.openSavedArtifact(clone(world));html=await env.experience.render('simulator');assert(html.includes('Document owner'));assert(html.includes('Teammate'));assert(html.includes('Exact saved plan'));assert(!html.includes('not part of the current'));assert.equal(JSON.stringify(env.experience.state.draft),before);assert.equal(env.log.jobs.length,0);
for(const mutate of [w=>w.payload.family='village_document_access_repair',w=>w.payload.source_refs.dataset_ref.hash='1'.repeat(64),w=>w.payload.environment.kind='shared_artifact_coordination']){const bad=clone(world);mutate(bad);await assert.rejects(env.experience.openSavedArtifact(bad));}
""")


if __name__=='__main__':unittest.main()
