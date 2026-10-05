"""Isolated source-shaped fixtures; no provider calls or historical findings."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab
from swarm_lab.demo_visibility import archive_for_village,visible_inventory,visible_jobs,CHAT_ID,PROJECT_ID
from swarm_lab.lab_workspace import bootstrap_workspace,workspace_index,artifact_catalog,chat_snapshot,DEFAULT_CHAT,mutate_workspace
from swarm_lab.guide_tools import execute_guide_tool,guide_tool_schemas,guide_activity
from swarm_lab.guide_assistant import _authorized_operations,grounded_context,_guided_context,RESULT_KINDS

def ref(obj): return {k:obj[k] for k in ('id','version','hash')}

class VillageProductContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.lab=Lab(Settings(root=Path(self.tmp.name),max_calls=0))
        # Explicit authored fixture shaped like imported logs, never a real-source claim.
        self.dataset=self.lab.store.put('dataset',{'messages':[
            {'id':'m'+str(i),'agent_name':'Agent','timestamp':'2025-09-08T17:0'+str(i)+':00Z','room_id':'room',
             'speaker_type':'agent','content':text,'content_hash':'a'*64,'source':{'file':'chat_messages.jsonl.gz','line':i+1}}
            for i,text in enumerate(['The document URL returns 404 in this browser.',
                'The Drive sheet permissions need viewer access.', 'The form URL is mistyped in my incognito session.'])],
            'provenance':{'revision':'a'*40,'source_sha256':'b'*64,'expected_sha256':'b'*64,
                'scope':'Authored isolated fixture only.'}})
        self.discovery=self.lab.store.put('discovery',{'dataset_ref':ref(self.dataset),'candidates':[]})
        self.behavior=self.lab.store.put('behavior',{'status':'rejected','source_refs':{'dataset':ref(self.dataset),'discovery':ref(self.discovery)}})
        self.old=self.lab.store.put('experiment',{'agent_mode':'live','status':'complete','source_refs':{'dataset':ref(self.dataset)}})
        self.tainted=self.lab.store.put('theory',{'source_refs':{'dataset':ref(self.dataset),'experiment':ref(self.old)}})
        self.oldproof=self.lab.store.put('verification',{'source_refs':{'dataset_ref':ref(self.dataset)},'passed':True})
        bootstrap_workspace(self.lab)
        self.lab.store.job('old-pilot-job','completed',{'result_ids':[self.old['id']]})

    def clean(self): return archive_for_village(self.lab,source_ref=ref(self.dataset))
    def args(self): return {'dataset_ref':ref(self.dataset),'behavior_ref':ref(self.behavior),
        'question':'Does a reference check improve document access repair?',
        'control_text':'Continue preparing the assigned project carefully.',
        'treatment_text':'Check document identity and browser principal.'}

    def test_cleanup_keeps_exact_observations_and_rejected_candidate_but_not_pilot_derivatives(self):
        before={(o['id'],o['version']):o['hash'] for o in self.lab.store.list(limit=200)}
        result=self.clean(); index=workspace_index(self.lab)
        self.assertEqual(index['default_chat_id'],CHAT_ID); self.assertEqual(index['default_project_id'],PROJECT_ID)
        self.assertEqual([p['name'] for p in index['projects']],['AI Village'])
        self.assertEqual(index['projects'][0]['chats'][0]['name'],'Document access investigation')
        shown=visible_inventory(self.lab,self.lab.store.list(limit=200))
        self.assertEqual({o['id'] for o in shown},{self.dataset['id'],self.discovery['id'],self.behavior['id']})
        self.assertEqual(before,{(o['id'],o['version']):o['hash'] for o in self.lab.store.list(limit=200)})
        self.assertEqual(self.lab.store.get(self.old['id'])['hash'],self.old['hash'])
        self.assertEqual(chat_snapshot(self.lab,CHAT_ID)['state']['context'],{'dataset_ref':ref(self.dataset)})
        self.assertEqual(self.lab.store.usage()['calls'],0)

    def test_archived_chats_cannot_be_read_or_selected_and_catalog_has_no_hidden_origin(self):
        self.clean()
        with self.assertRaisesRegex(ValueError,'archived'):chat_snapshot(self.lab,DEFAULT_CHAT)
        with self.assertRaisesRegex(ValueError,'archived'):artifact_catalog(self.lab,scope='chat',chat_id=DEFAULT_CHAT)
        packet=artifact_catalog(self.lab)
        self.assertTrue(all(row['origin']['chat_id']==CHAT_ID for row in packet['artifacts']))
        self.assertNotIn(self.old['id'],json.dumps(packet))
        self.assertEqual(visible_jobs(self.lab,self.lab.store.jobs()),[])
        self.lab.store.job('new-source-job','running',{'action':'source investigation'})
        self.assertEqual([r['id'] for r in visible_jobs(self.lab,self.lab.store.jobs())],['new-source-job'])

    def test_new_objects_visible_cleanup_idempotent_and_no_mutable_alias(self):
        self.clean(); self.clean()
        new=self.lab.store.put('village_incident',{'source_ref':ref(self.dataset),'status':'reported_only'})
        rows=[new]; out=visible_inventory(self.lab,rows); out[0]['payload']['status']='changed'
        self.assertEqual(rows[0]['payload']['status'],'reported_only')
        self.assertEqual(self.clean()['visible_object_count'],4)

    def test_new_plan_tool_persists_exact_source_incidents_and_equal_notes_without_calls(self):
        self.clean(); args=self.args()
        value=execute_guide_tool(self.lab,'save_village_plan',args,chat_id=CHAT_ID,request_id='new-plan',
            authorized_tools={'save_village_plan'},allowed_refs=[ref(self.dataset),ref(self.behavior)])
        p=self.lab.store.get(value['updated_context']['plan_ref']['id'])['payload']
        self.assertEqual(p['family'],'village_document_access_repair')
        self.assertEqual(p['source_refs']['dataset_ref'],ref(self.dataset))
        self.assertEqual(p['source_refs']['behavior_ref'],ref(self.behavior))
        self.assertEqual(p['note_length_words'],{'control':6,'intervention':6})
        self.assertEqual((p['trials_per_arm'],p['seed'],p['max_rounds']),(2,42,8))
        self.assertEqual(self.lab.store.usage()['calls'],0)
        self.assertIn(value['updated_context']['incident_ref'],value['result_refs'])
        self.assertEqual([e['phase'] for e in guide_activity(self.lab,CHAT_ID)['events']],['started','completed'])

    def test_refused_generic_mismatched_or_unequal_inputs_start_no_claim(self):
        self.clean(); args=self.args(); bad=[]
        for change in ({'question':'Does a number change consensus?'},{'control_text':'short'},
            {'trials_per_arm':True},{'dataset_ref':ref(self.dataset)|{'hash':'0'*64}}):bad.append(args|change)
        for i,body in enumerate(bad):
            with self.assertRaises(ValueError):execute_guide_tool(self.lab,'save_village_plan',body,chat_id=CHAT_ID,
                request_id='bad-'+str(i),authorized_tools={'save_village_plan'},allowed_refs=[ref(self.dataset),ref(self.behavior)])
        self.assertEqual(guide_activity(self.lab,CHAT_ID)['events'],[])

    def test_active_authorization_is_village_only_questions_and_prohibitions_remain_inert(self):
        self.assertEqual(RESULT_KINDS,{'village_access_experiment'})
        names=_authorized_operations('Save a new experiment plan. Do not build or run it yet.')
        self.assertEqual(names,{'save_village_plan'})
        self.assertNotIn('save_plan',_authorized_operations('Run this experiment.'))
        self.assertEqual(_authorized_operations('What experiments can we run?'),set())
        self.assertNotIn('run_experiment',_authorized_operations('Run this experiment. Do not run it yet.'))
        schema=guide_tool_schemas(names)[0]
        self.assertEqual(set(schema['parameters']['properties']),{'dataset_ref','behavior_ref','question','control_text','treatment_text','trials_per_arm','seed','max_rounds'})

    def test_actual_village_noun_phrases_authorize_only_requested_stage(self):
        self.assertEqual(_authorized_operations('Save a new source-grounded AI Village document-access experiment plan. Do not build or run it yet.'),{'save_village_plan'})
        self.assertEqual(_authorized_operations('Build and review the exact saved AI Village source-grounded document-access simulator. Do not run subjects yet.'),{'build_simulator'})
        self.assertIn('run_experiment',_authorized_operations('Run this exact saved AI Village source-grounded simulator.'))
        self.assertNotIn('run_experiment',_authorized_operations('Run this exact saved AI Village source-grounded simulator. Do not run it yet.'))
        self.assertEqual(_authorized_operations('What would a source-grounded AI Village document-access simulator do?'),set())
        self.assertEqual(_authorized_operations('Discuss "Run this exact saved AI Village simulator." without running anything.'),set())

    def test_guide_never_implicitly_borrows_old_saved_results(self):
        request={'message':'What do these reports suggest?','current_view':'workspace','current_context':{'dataset_ref':ref(self.dataset)}}
        inventory=[{k:o[k] for k in ('id','version','kind','hash')} for o in (self.dataset,self.old)]
        context,_,_=grounded_context(self.lab,request,inventory)
        self.assertIsNone(context['saved_study']);self.assertEqual(context['live_saved_studies'],[])
        self.clean()
        with self.assertRaisesRegex(ValueError,'archived'):grounded_context(self.lab,
            request|{'current_context':{'result_ref':ref(self.old)}},inventory)

    def test_village_world_uses_its_own_validator_and_rejects_different_selected_plan(self):
        self.clean()
        value=execute_guide_tool(self.lab,'save_village_plan',self.args(),chat_id=CHAT_ID,request_id='plan-for-world',
            authorized_tools={'save_village_plan'},allowed_refs=[ref(self.dataset),ref(self.behavior)])
        plan=self.lab.store.get(value['updated_context']['plan_ref']['id'])
        other=self.lab.store.put('guided_plan',copy.deepcopy(plan['payload'])|{'question':'Different access question'})
        simulator=self.lab.store.put('guided_simulator',{'family':'village_document_access_repair','plan_ref':ref(plan)})
        registration=self.lab.store.put('protocol',{'protocol':{'family':'village_document_access_repair'}})
        with patch('swarm_lab.village_access_study.validate_saved_world',return_value=(plan,registration)) as check:
            matched=_guided_context(self.lab,{'simulator_ref':ref(simulator),'dataset_ref':ref(self.dataset)})
            self.assertEqual(ref(matched[0]),ref(plan));check.assert_called_once()
            with self.assertRaisesRegex(ValueError,'disagree'):_guided_context(self.lab,{'simulator_ref':ref(simulator),'plan_ref':ref(other)})

if __name__=='__main__':unittest.main()
