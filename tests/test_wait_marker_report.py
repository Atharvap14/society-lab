"""Fresh local reproduction gates compact literal/action observation tables."""
import copy
import inspect
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.build_research_report import (ReadOnlyRecords,collect_wait_markers,
    collect_report,execution_inventory,render_wait_marker_addition)
from swarm_lab import wait_marker_workflow as workflow


def prepared_fixture():
    """Authored negation/quotation, one human exclusion and a missing-room tie."""
    from tests.test_wait_marker_workflow import WaitMarkerWorkflowTests
    from tests.test_indexed_event_workflow import uid
    from swarm_lab.dataset import normalize_message
    from swarm_lab.graph_discovery import discover_graph_leads
    f=WaitMarkerWorkflowTests('test_read_only_derivation_is_deterministic_and_budget_unknown_is_not_negative')
    f.setUp()
    raw={'id':f.messages[0]['id'],'agent_id':uid(1),'agent_name':'Alice','speaker_type':'agent',
         'content':'Bobby, I am not waiting; someone said pause.','room_id':uid(50),'created_at':'2025-04-02T10:00:00Z'}
    f.messages[0]=normalize_message(raw,source=f.root/'chat_messages.jsonl',line=1)
    f.messages.append(normalize_message({'id':uid(999),'speaker_type':'user','user_speaker_id':uid(99),
        'content':'I am waiting.','room_id':uid(50),'created_at':'2025-04-02T10:00:30Z'},source=f.root/'chat_messages.jsonl',line=25))
    f.events[0]['data']['content']=raw['content']
    f.events.append({'id':uid(2100),'created_at':'2025-04-02T10:00:00Z','event_index':60,
        'data':{'actionType':'WAIT','agentId':uid(1),'output':'PRIVATE_PROVIDER_SENTINEL'}})
    f.source.write_text(''.join(json.dumps(e)+'\n' for e in f.events),encoding='utf-8')
    f.dataset=f.lab.store.put('dataset',{'messages':f.messages,'agents':f.roster},f.dataset['id'])
    f.discovery=f.lab.store.put('discovery',{'dataset_id':f.dataset['id'],'dataset_ref':f.ref(f.dataset),
        'graph_search':discover_graph_leads(f.messages,f.roster)},f.discovery['id'])
    f.selected=f.lab.audit_selected_leads(f.discovery['id'],short_name_allowlist=['o3'],include_unicode_shadow=True)
    return f


class WaitMarkerReportTests(unittest.TestCase):
    def setUp(self):
        self.f=prepared_fixture();self.addCleanup(self.f.doCleanups)
        self.actor=self.f.actor_audit()
        self.audit=workflow.audit_wait_markers(self.f.lab,self.actor['id'],version=1)
        self.proof=workflow.replay_wait_markers(self.f.lab,self.audit['id'],version=1)
        self.records=ReadOnlyRecords(self.f.lab.store.path);self.addCleanup(self.records.close)

    @staticmethod
    def pin(obj):return {key:obj[key] for key in ('id','version','kind','hash')}

    def pins(self,audit=None,proof=None):
        return {'audit':self.pin(audit or self.audit),'verification':self.pin(proof or self.proof)}

    def collect(self,pins=None):return collect_wait_markers(self.records,self.pins() if pins is None else pins)

    def forged_pair(self,payload):
        audit=self.f.lab.store.put('wait_marker_alignment_audit',payload)
        proof=copy.deepcopy(self.proof['payload']);proof['alignment_ref']=self.f.ref(audit)
        return self.pins(audit,self.f.lab.store.put('verification',proof))

    def assert_withheld(self,addition):
        self.assertFalse(addition['proof']['passed'])
        self.assertIsNone(addition['summary']);self.assertEqual(addition['witnesses'],[])
        page=render_wait_marker_addition(addition)
        self.assertIn('withheld',page)
        self.assertNotIn('Recorded candidates: message numerators',page)

    def test_fresh_exact_old_sources_small_denominators_censoring_and_privacy(self):
        for obj in (self.actor,self.f.dataset,self.f.discovery,self.f.selected):
            self.f.lab.store.put(obj['kind'],{'newer':True},obj['id'])
        before=self.records.connection.execute('SELECT COUNT(*) FROM objects').fetchone()[0]
        addition=self.collect()
        self.assertEqual(self.records.connection.execute('SELECT COUNT(*) FROM objects').fetchone()[0],before)
        self.assertTrue(addition['proof']['passed'],addition['proof'])
        self.assertTrue(addition['proof']['index_artifact_reread_completed'])
        self.assertFalse(addition['proof']['full_event_source_reread'])
        self.assertEqual(addition['message_scope']['supplied_messages'],25)
        self.assertEqual(addition['message_scope']['excluded_nonagent_by_speaker_type'],{'user':1})
        self.assertEqual(addition['message_scope']['literal_marker_spans'],2)
        self.assertEqual((addition['summary']['marker_messages'],addition['summary']['nonmarker_control_messages']),(1,23))
        self.assertEqual(addition['summary']['groups']['marker']['by_horizon_seconds']['30']['status_counts'],{'candidate_observed_boundary_censored':1})
        page=render_wait_marker_addition(addition)
        self.assertIn('1 / 1',page);self.assertIn('censored',page)
        self.assertIn('not independent samples',page)
        self.assertIn('raw chat clock policies are unavailable',page.lower())
        self.assertIn('same-source retrospective exploration',page.lower())
        serialized=json.dumps(addition)
        self.assertNotIn('PRIVATE_PROVIDER_SENTINEL',serialized)
        self.assertNotIn(self.f.messages[0]['content'],serialized)
        self.assertEqual(self.f.lab.store.usage()['calls'],0)
        self.assertEqual(self.f.lab.store.list('behavior'),[])
        self.assertEqual(self.f.lab.store.list('theory'),[])
        self.assertEqual(execution_inventory({'result':{},'runs':[1]*9}),execution_inventory({'result':{},'runs':[1]*9,'literal_wait_marker_alignment':addition}))

    def test_resealed_summary_lags_room_clock_censoring_and_source_changes_fail(self):
        mutations=[lambda p:p['alignment']['summary'].update(marker_messages=100),
            lambda p:p['alignment']['summary'].update(marker_messages=1.0),
            lambda p:p['alignment']['summary']['groups']['marker']['by_horizon_seconds']['30'].update(messages_with_candidate=True),
            lambda p:p['alignment']['alignment_rows'][0]['candidates'][0].update(lag_seconds=0.0),
            lambda p:p['alignment']['alignment_rows'][0]['candidates'][0].update(room_inferred=True),
            lambda p:p['alignment']['message_pins'][0].update(chat_clock_policy='explicit_offset_to_utc'),
            lambda p:p['alignment']['summary']['groups']['marker']['by_horizon_seconds']['30']['status_counts'].update(candidate_observed_boundary_censored=0),
            lambda p:p['actor_audit_ref'].update(version=True)]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                payload=copy.deepcopy(self.audit['payload']);mutate(payload)
                self.assert_withheld(self.collect(self.forged_pair(payload)))

    def test_unknown_work_or_action_scope_reproduces_without_zero_filled_summary(self):
        unknown=workflow.audit_wait_markers(self.f.lab,self.actor['id'],max_work=1)
        proof=workflow.replay_wait_markers(self.f.lab,unknown['id'])
        addition=self.collect(self.pins(unknown,proof))
        self.assertTrue(addition['proof']['passed'],addition['proof'])
        self.assertIsNone(addition['summary']);self.assertEqual(addition['witnesses'],[])
        page=render_wait_marker_addition(addition)
        self.assertIn('candidate alignment remains unknown',page)
        self.assertIn('aggregate_work_budget_exceeded',page)
        self.assertNotIn('Recorded candidates: message numerators',page)
        actor=self.f.actor_audit(action_types=['WAIT'])
        audit=workflow.audit_wait_markers(self.f.lab,actor['id']);proof=workflow.replay_wait_markers(self.f.lab,audit['id'])
        addition=self.collect(self.pins(audit,proof))
        self.assertTrue(addition['proof']['passed']);self.assertIsNone(addition['summary'])
        self.assertIn('WAIT_PAUSE_action_scope_incomplete',addition['unknown_reasons'])

    def test_bad_proof_or_current_code_skips_source_work(self):
        updates=[{'alignment_ref':{**self.f.ref(self.audit),'version':True}}, {'model_calls':False},
                 {'source_replay_completed':False},{'index_artifact_reread_completed':False},
                 {'full_event_source_reread':True},{'result_kind':'actor_event_audit'}]
        for update in updates:
            proof=self.f.lab.store.put('verification',{**copy.deepcopy(self.proof['payload']),**update})
            with patch('swarm_lab.wait_marker_workflow.derive_wait_marker_alignment',side_effect=AssertionError('must not read sources')):
                addition=self.collect(self.pins(proof=proof))
            self.assert_withheld(addition);self.assertFalse(addition['proof']['source_replay_attempted'])
        with patch('swarm_lab.wait_marker_workflow.implementation_hashes',return_value={}), \
             patch('swarm_lab.wait_marker_workflow.derive_wait_marker_alignment',side_effect=AssertionError('must not read sources')):
            self.assert_withheld(self.collect())

    def test_changed_missing_index_or_resealed_actor_cannot_authorize_counts(self):
        payload=copy.deepcopy(self.actor['payload']);payload['actor_event_summary']['total']['records']=999
        actor=self.f.lab.store.put('actor_event_audit',payload)
        payload=copy.deepcopy(self.audit['payload']);payload['actor_audit_ref']=self.f.ref(actor);payload['source_refs']['actor_audit']=self.f.ref(actor)
        self.assert_withheld(self.collect(self.forged_pair(payload)))
        path=Path(self.actor['payload']['actor_event_packet']['index']['path'])
        path.write_bytes(path.read_bytes()+b'changed');self.assert_withheld(self.collect())
        path.unlink();self.assert_withheld(self.collect())

    def test_inert_refs_compatible_default_and_no_full_raw_source_reread(self):
        self.f.source.unlink();addition=self.collect()
        self.assertTrue(addition['proof']['passed'])
        addition['references']['audit']['id']='<script>inert</script>'
        page=render_wait_marker_addition(addition)
        self.assertIn('&lt;script&gt;inert&lt;/script&gt;',page);self.assertNotIn('<script>inert</script>',page)
        self.assertFalse(inspect.signature(collect_report).parameters['include_wait_markers'].default)
        self.assert_withheld(self.collect({}))


if __name__=='__main__':unittest.main()
