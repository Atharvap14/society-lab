"""Small registry fixtures for exact selected-author observations and replay."""
import contextlib
import copy
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import actor_selected_events_probe as script
from swarm_lab import actor_event_workflow as workflow
from swarm_lab.dataset import normalize_message
from swarm_lab.graph_discovery import discover_graph_leads
from tests import test_indexed_event_workflow as fixtures

uid = fixtures.uid


class ActorEventWorkflowTests(unittest.TestCase):
    setUp = fixtures.IndexedEventWorkflowTests.setUp
    ref = staticmethod(fixtures.IndexedEventWorkflowTests.ref)
    build = fixtures.IndexedEventWorkflowTests.build

    def audit(self, index, **options):
        return workflow.audit_selected_actor_events(self.lab, index['id'], self.selected['id'],
            index_version=options.pop('index_version', index['version']),
            selected_audit_version=options.pop('selected_audit_version', self.selected['version']), **options)

    def extra_events(self):
        self.events.extend([
            {'id':uid(2001),'created_at':'2025-04-02T10:03:00Z','event_index':51,
             'data':{'actionType':'START_USING_COMPUTER','agentId':uid(1),'computerUseSessionId':uid(90)}},
            {'id':uid(2002),'created_at':'2025-04-02T11:03:00Z','event_index':52,
             'data':{'actionType':'STOP_USING_COMPUTER','agentId':uid(1)}},
            {'id':uid(2003),'created_at':'2025-04-02T10:04:00Z','event_index':53,
             'data':{'actionType':'PAUSE','agentId':uid(2),'seconds':4.5}},
            {'id':uid(2004),'created_at':'2025-04-02T10:05:00Z','event_index':54,
             'data':{'actionType':'WAIT','agentId':uid(4)}},
            {'id':uid(2005),'created_at':'2025-04-02T10:06:00Z','event_index':55,
             'data':{'actionType':'WAIT','agentId':uid(1),'speakerId':uid(2)}}])
        self.source.write_text(''.join(json.dumps(row)+'\n' for row in self.events),encoding='utf-8')

    def test_exact_old_versions_replay_and_ghost_roster_target_is_not_actor(self):
        self.extra_events(); index = self.build()
        for obj in (self.dataset,self.discovery,self.selected,index):
            self.lab.store.put(obj['kind'], {'later':True}, obj['id'])
        result = self.audit(index); payload = result['payload']
        proof = workflow.replay_actor_events(self.lab,result['id'],version=1)['payload']
        self.assertTrue(proof['passed']); self.assertTrue(proof['index_artifact_reread_completed'])
        self.assertFalse(proof['full_event_source_reread'])
        self.assertEqual(payload['source_refs']['dataset'],self.ref(self.dataset))
        self.assertEqual(payload['source_refs']['discovery'],self.ref(self.discovery))
        self.assertEqual(payload['selected_audit_ref'],self.ref(self.selected))
        self.assertEqual(payload['index_ref'],self.ref(index))
        self.assertEqual(payload['query']['actor_ids'],[uid(1),uid(2),uid(3)])
        self.assertNotIn(uid(4),payload['query']['actor_ids'])
        self.assertEqual(payload['actor_event_summary']['total']['records'],4)
        self.assertEqual(payload['actor_event_summary']['total']['room_status_counts'],{'known':1,'missing':3,'invalid':0})
        self.assertEqual(payload['actor_event_packet']['coverage']['other_explicit_actor_rows'],1)
        self.assertEqual(payload['actor_event_packet']['coverage']['candidate_actor_status_counts']['conflicting_fields'],1)
        self.assertTrue(all('room_id' in w for w in payload['original_windows']))
        self.assertTrue(all('room_id' not in w for w in payload['query']['windows']))
        self.assertEqual(payload['timestamp_policy_counts'],{'explicit_offset_to_utc':4})
        self.assertFalse(payload['status_promotion']); self.assertEqual(payload['model_calls'],0)
        self.assertEqual(self.lab.store.usage()['calls'],0)
        self.assertEqual(self.lab.store.list('behavior'),[]); self.assertEqual(self.lab.store.list('theory'),[])
        self.assertNotIn('PRIVATE_PROVIDER_SENTINEL',json.dumps(payload))
        self.assertNotIn(self.messages[0]['content'],json.dumps(payload))

    def test_user_source_is_counted_but_never_selects_actor_id(self):
        human = normalize_message({'id':uid(999),'speaker_type':'user','agent_id':uid(99),
            'user_speaker_id':uid(99),'content':'Alice, Bobby, Carol, keep working.',
            'room_id':uid(50),'created_at':'2025-04-02T10:00:30Z'},source=self.root/'chat_messages.jsonl',line=25)
        messages = [*self.messages,human]
        self.dataset = self.lab.store.put('dataset',{'messages':messages,'agents':self.roster})
        self.discovery = self.lab.store.put('discovery',{'dataset_id':self.dataset['id'],'dataset_ref':self.ref(self.dataset),
            'graph_search':discover_graph_leads(messages,self.roster)})
        self.selected = self.lab.audit_selected_leads(self.discovery['id'],short_name_allowlist=['o3'],include_unicode_shadow=True)
        result = self.audit(self.build())['payload']
        self.assertEqual(result['source_scope']['speaker_type_counts'],{'agent':24,'user':1})
        self.assertNotIn(uid(99),result['query']['actor_ids'])
        self.assertEqual(len(result['author_source_pins']),24)

    def test_derivation_is_deterministic_without_audit_store_write(self):
        index = self.build()
        a = workflow.derive_selected_actor_events(self.lab,self.ref(index),self.ref(self.selected))
        b = workflow.derive_selected_actor_events(self.lab,self.ref(index),self.ref(self.selected))
        self.assertEqual(a,b); self.assertEqual(self.lab.store.list('actor_event_audit'),[])

    def test_invalid_versions_ids_bounds_and_actions_refused(self):
        index = self.build()
        for options in ({'index_version':True},{'selected_audit_version':True},{'index_version':0},
            {'max_rows':True},{'max_rows':1.5},{'max_rows':0},{'max_candidate_rows':15001},
            {'action_types':[]},{'action_types':['WAIT','WAIT']},{'action_types':[True]}):
            with self.subTest(options=options),self.assertRaises(ValueError):self.audit(index,**options)
        with self.assertRaises(ValueError):workflow.audit_selected_actor_events(self.lab,False,self.selected['id'])
        result = self.audit(index)
        with self.assertRaises(ValueError):workflow.replay_actor_events(self.lab,result['id'],version=True)
        self.assertEqual(self.lab.store.usage()['calls'],0)

    def test_exact_ref_forgery_or_wrong_kind_rejected_before_audit_put(self):
        index = self.build()
        bad = self.ref(index);bad['hash']='0'*64
        with self.assertRaises(ValueError):workflow.derive_selected_actor_events(self.lab,bad,self.ref(self.selected))
        for field,value in (('version',True),('hash','bad'),('extra','bad')):
            ref=self.ref(self.selected);ref[field]=value
            with self.assertRaises(ValueError):workflow.derive_selected_actor_events(self.lab,self.ref(index),ref)
        with self.assertRaises(ValueError):workflow.derive_selected_actor_events(self.lab,self.ref(self.dataset),self.ref(self.selected))
        self.assertEqual(self.lab.store.list('actor_event_audit'),[])

    def test_forged_selected_windows_do_not_reproduce(self):
        index = self.build(); forged=copy.deepcopy(self.selected['payload'])
        next(iter(forged['window_measurements'].values()))['original_window']['end_exclusive']='2025-04-02T13:00:00Z'
        selected=self.lab.store.put('selected_lead_audit',forged)
        with self.assertRaises(ValueError):workflow.audit_selected_actor_events(self.lab,index['id'],selected['id'])
        self.assertEqual(self.lab.store.list('actor_event_audit'),[])

    def test_forged_registered_metadata_or_artifact_byte_count_rejected(self):
        index=self.build()
        for mutate in (lambda p:p['build_metadata']['coverage'].update(physical_rows_seen=999),
                       lambda p:p['build_metadata']['artifact'].update(bytes=True)):
            modified=copy.deepcopy(index['payload']);mutate(modified)
            forged=self.lab.store.put('event_source_index',modified)
            with self.assertRaisesRegex(ValueError,'Registered build metadata'):self.audit(forged)
        self.assertEqual(self.lab.store.list('actor_event_audit'),[])

    def test_actor_or_source_alias_is_not_silently_inferred(self):
        index=self.build()
        from swarm_lab.indexed_event_workflow import selected_window_sources
        windows,messages,refs=selected_window_sources(self.lab,self.selected['id'],version=1)
        for key,value in (('agent_id',None),('speaker_id',uid(99)),('created_at','invalid'),('source',{})):
            changed=copy.deepcopy(messages);changed[0][key]=value
            with patch.object(workflow.frozen,'selected_window_sources',return_value=(windows,changed,refs)),self.assertRaises(ValueError):self.audit(index)
        self.assertEqual(self.lab.store.list('actor_event_audit'),[])

    def test_saved_summary_packet_query_refs_and_source_pins_tampering_fail_replay(self):
        index=self.build(); result=self.audit(index)
        changes=[lambda p:p['actor_event_summary']['total'].update(records=999),
            lambda p:p['actor_event_packet']['records'][0]['room_observation'].update(status='missing'),
            lambda p:p['query'].update(actor_ids=[uid(99)]),
            lambda p:p['index_ref'].update(hash='0'*64),
            lambda p:p['author_source_pins'][0].update(agent_id=uid(99)),
            lambda p:p.update(status_promotion=True)]
        for change in changes:
            modified=copy.deepcopy(result['payload']);change(modified)
            forged=self.lab.store.put('actor_event_audit',modified)
            self.assertFalse(workflow.replay_actor_events(self.lab,forged['id'])['payload']['passed'])

    def test_changed_artifact_and_implementation_return_failed_verification(self):
        index=self.build();result=self.audit(index)
        with patch.object(workflow,'implementation_hashes',return_value={}):
            proof=workflow.replay_actor_events(self.lab,result['id'])['payload']
        self.assertEqual(proof['reason'],'implementation_hash_mismatch')
        self.assertFalse(proof['index_artifact_reread_attempted'])
        with Path(index['payload']['build_metadata']['artifact']['path']).open('ab') as f:f.write(b'changed')
        proof=workflow.replay_actor_events(self.lab,result['id'])['payload']
        self.assertFalse(proof['passed']);self.assertTrue(proof['index_artifact_reread_attempted'])
        self.assertFalse(proof['index_artifact_reread_completed']);self.assertFalse(proof['full_event_source_reread'])

    def test_invalid_reader_projection_fails_summary_before_persistence(self):
        index=self.build()
        original=workflow.derive_selected_actor_events(self.lab,self.ref(index),self.ref(self.selected))['actor_event_packet']
        broken=copy.deepcopy(original);broken['records'][0]['record']['actor_id']=uid(99)
        with patch.object(workflow.queries,'read_actor_event_index',return_value=broken),self.assertRaises(ValueError):self.audit(index)
        self.assertEqual(self.lab.store.list('actor_event_audit'),[])

    def test_deleted_raw_events_do_not_prevent_local_index_replay(self):
        index=self.build();result=self.audit(index);self.source.unlink()
        proof=workflow.replay_actor_events(self.lab,result['id'])['payload']
        self.assertTrue(proof['passed']);self.assertFalse(proof['full_event_source_reread'])

    def test_returned_only_summary_scope_is_preserved_when_truncated(self):
        self.extra_events();result=self.audit(self.build(),max_rows=1)['payload']
        self.assertTrue(result['actor_event_packet']['coverage']['truncated'])
        self.assertEqual(result['actor_event_summary']['total']['records'],1)
        self.assertEqual(sum(result['timestamp_policy_counts'].values()),1)

    def test_durable_script_reuses_exact_index_job_and_prints_no_payloads(self):
        self.extra_events();index=self.build()
        argv=['--index-id',index['id'],'--index-version','1','--selected-audit-id',self.selected['id'],
            '--selected-audit-version','1','--job-id','actor-fixture-job']
        out=io.StringIO()
        with patch.object(script,'Lab',return_value=self.lab),contextlib.redirect_stdout(out):
            self.assertEqual(script.main(argv),0)
        result=json.loads(out.getvalue())
        self.assertTrue(result['refs']['passed']);self.assertEqual(result['summary_total']['records'],4)
        self.assertNotIn('PRIVATE_PROVIDER_SENTINEL',out.getvalue());self.assertNotIn('actor_event_packet',out.getvalue())
        job=self.lab.store.get_job('actor-fixture-job');self.assertEqual(job['status'],'completed')
        before=copy.deepcopy(job)
        with patch.object(script,'Lab',return_value=self.lab),self.assertRaises(ValueError):script.main(argv)
        self.assertEqual(self.lab.store.get_job('actor-fixture-job'),before)
        self.assertEqual(len(self.lab.store.list('event_source_index')),1)
        self.assertEqual(self.lab.store.usage()['calls'],0)

    def test_script_records_operational_failure_without_raw_error_payload(self):
        index=self.build()
        argv=['--index-id',index['id'],'--selected-audit-id',self.selected['id'],'--job-id','actor-failed-job']
        with (patch.object(script,'Lab',return_value=self.lab),
              patch.object(script,'audit_selected_actor_events',side_effect=ValueError('PRIVATE_PROVIDER_SENTINEL')),
              self.assertRaises(ValueError)):
            script.main(argv)
        job=self.lab.store.get_job('actor-failed-job')
        self.assertEqual(job['status'],'failed');self.assertEqual(job['payload']['error_type'],'ValueError')
        self.assertNotIn('PRIVATE_PROVIDER_SENTINEL',json.dumps(job))

    def test_script_invalid_arguments_do_not_initialize_or_write_registry(self):
        for options in (['--max-rows','0'],['--max-candidate-rows','15001'],
                        ['--index-version','0'],['--selected-audit-version','True']):
            with patch.object(script,'Lab') as lab, contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                script.main(['--job-id','validation-fixture',*options])
            lab.assert_not_called()
        with patch.object(script,'Lab') as lab,contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            script.main(['--job-id',''])
        lab.assert_not_called()


if __name__=='__main__':unittest.main()
