"""Controlled literal-language fixtures; no production alignment inspections."""
import builtins
import contextlib
import copy
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from swarm_lab import actor_event_queries as queries
from swarm_lab import event_source_index as index
from swarm_lab import wait_marker_alignment as alignment
from swarm_lab.dataset import normalize_message


def uid(n):
    return f'00000000-0000-0000-0000-{n:012x}'


def event(n, time='2026-04-18T18:10:00Z', actor=20, action='WAIT', **extras):
    return {'id':uid(n),'created_at':time,'event_index':n,
        'data':{'actionType':action,'agentId':uid(actor),**extras}}


WINDOW={'id':'original-window','start':'2026-04-18T18:00:00Z','end_exclusive':'2026-04-18T19:00:00Z'}


class WaitMarkerAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.counter=0

    def packet(self, events=None, *, windows=None, actors=None, actions=None, max_rows=15000, build_options=None):
        self.counter+=1;source=self.root/f'events{self.counter}.jsonl';path=self.root/f'index{self.counter}.sqlite3'
        source.write_bytes(b''.join(index._canonical(e)+b'\n' for e in (events if events is not None else [event(1)])))
        meta=index.build_event_index(source,path,**(build_options or {}))
        return queries.read_actor_event_index(path,expected_file_sha256=meta['artifact']['file_sha256'],
            actor_ids=actors or [uid(20)],windows=windows or [WINDOW],
            action_types=['WAIT','PAUSE','START_USING_COMPUTER','STOP_USING_COMPUTER'] if actions is None else actions,
            max_rows=max_rows)

    def message(self,n,text='I am waiting.',time='2026-04-18T18:10:00Z',actor=20,human=False):
        return normalize_message({'id':uid(1000+n),'created_at':time,'content':text,'room_id':uid(30),
            'speaker_type':'user' if human else 'agent',
            'user_speaker_id':uid(actor) if human else None,'agent_id':None if human else uid(actor)},
            source=self.root/'chat_messages.jsonl',line=n+1)

    def run_alignment(self,messages,packet=None,**options):
        return alignment.analyze_wait_marker_alignment(messages,self.packet() if packet is None else packet,**options)

    def test_fixed_literal_tokens_negation_quotation_and_original_unicode_offsets(self):
        text='λ I am not WAITING. Someone said "pause". Await idle blocked.'
        m=self.message(1,text);out=self.run_alignment([m])
        pin=out['message_pins'][0]
        self.assertEqual([s['token'] for s in pin['marker_spans']],['waiting','pause'])
        for span in pin['marker_spans']:
            self.assertEqual(text[span['start']:span['end_exclusive']].lower(),span['token'])
        self.assertEqual(pin['marker_semantics'],'unadjudicated_literal_hit')
        self.assertEqual(out['configuration']['horizons_seconds'],[30,60,300])
        self.assertNotIn(text,json.dumps(out));self.assertEqual(out['summary']['marker_messages'],1)

    def test_all_eight_tokens_and_ascii_word_negatives(self):
        a=self.message(1,'wait waits waited waiting pause pauses paused pausing')
        b=self.message(2,'await awaiting waitlist paused_variable impatience')
        out=self.run_alignment([a,b])
        byid={r['message_id']:r for r in out['message_pins']}
        self.assertEqual(len(byid[a['id']]['marker_spans']),8)
        self.assertEqual(byid[b['id']]['marker_spans'],[])
        self.assertEqual(byid[b['id']]['marker_semantics'],'literal_nonmarker_not_negative_ground_truth')

    def test_before_after_ties_and_inclusive_horizon_endpoints(self):
        p=self.packet([event(1,'2026-04-18T18:09:30Z'),event(2),event(3,'2026-04-18T18:10:30Z'),event(4,'2026-04-18T18:11:00Z'),event(5,'2026-04-18T18:15:00Z')])
        out=self.run_alignment([self.message(1)],p);row=out['alignment_rows'][0]
        self.assertEqual((row['by_horizon_seconds']['30']['before'],row['by_horizon_seconds']['30']['tie'],row['by_horizon_seconds']['30']['after']),(1,1,1))
        self.assertEqual(row['by_horizon_seconds']['60']['after'],2)
        self.assertEqual(row['by_horizon_seconds']['300']['after'],3)
        self.assertEqual(next(c for c in row['candidates'] if c['event_id']==uid(1))['lag_microseconds'],-30_000_000)

    def test_offset_equivalent_timestamp_is_tie_without_physical_order(self):
        p=self.packet([event(1,'2026-04-18T20:10:00+02:00')])
        out=self.run_alignment([self.message(1)],p)
        c=out['alignment_rows'][0]['candidates'][0]
        self.assertEqual(c['direction'],'tie');self.assertEqual(c['physical_clock_synchronization'],'unverified')

    def test_clock_policy_same_different_and_unavailable_are_not_synchronization(self):
        m=self.message(1);p=self.packet([event(1,'2026-04-18 18:10:00')])
        for declared,expected in ((None,'chat_policy_unavailable'),('export_naive_assumed_utc','declared_conventions_same'),('explicit_offset_to_utc','declared_conventions_different')):
            options={} if declared is None else {'chat_clock_policies':{m['id']:declared}}
            out=self.run_alignment([m],p,**options)
            c=out['alignment_rows'][0]['candidates'][0]
            self.assertEqual(c['clock_convention_relation'],expected)
            self.assertEqual(c['physical_clock_synchronization'],'unverified')

    def test_unknown_clock_declarations_and_missing_event_policy_reject(self):
        m=self.message(1);p=self.packet()
        for value in ('synchronized',True,None):
            with self.assertRaises(ValueError):self.run_alignment([m],p,chat_clock_policies={m['id']:value})
        with self.assertRaises(ValueError):self.run_alignment([m],p,chat_clock_policies={uid(999):'explicit_offset_to_utc'})
        broken=copy.deepcopy(p);broken['records'][0]['record']['fields']['created_at'].pop('timezone_policy')
        with self.assertRaises(ValueError):self.run_alignment([m],broken)

    def test_human_literal_markers_are_excluded_from_actor_selection(self):
        out=self.run_alignment([self.message(1),self.message(2,'WAIT WAIT',human=True,actor=999)])
        self.assertEqual(out['message_scope']['excluded_nonagent_by_speaker_type'],{'user':1})
        self.assertEqual(len(out['message_pins']),1)

    def test_cross_actor_event_never_aligns_and_unqueried_actor_is_unknown(self):
        p=self.packet([event(1,actor=21)],actors=[uid(20),uid(21)])
        out=self.run_alignment([self.message(1)],p)
        self.assertEqual(out['alignment_rows'][0]['candidates'],[])
        unknown=self.run_alignment([self.message(2,actor=22)],p)['alignment_rows'][0]
        self.assertEqual(unknown['scope_unknown_reason'],'actor_not_selected_by_query')
        self.assertEqual(unknown['by_horizon_seconds']['30']['status'],'unknown_message_scope')

    def test_adjacent_window_boundary_is_not_crossed_and_band_censored(self):
        a={'id':'first','start':'2026-04-18T18:00:00Z','end_exclusive':'2026-04-18T19:00:00Z'}
        b={'id':'second','start':'2026-04-18T19:00:00Z','end_exclusive':'2026-04-18T20:00:00Z'}
        p=self.packet([event(1,'2026-04-18T19:00:00Z')],windows=[a,b])
        out=self.run_alignment([self.message(1,time='2026-04-18T18:59:50Z')],p)
        row=out['alignment_rows'][0]
        self.assertEqual(row['candidates'],[])
        self.assertFalse(row['by_horizon_seconds']['30']['after_support_complete'])
        self.assertEqual(row['by_horizon_seconds']['30']['status'],'no_indexed_candidate_boundary_censored')

    def test_end_exact_horizon_is_censored_but_start_exact_horizon_observed(self):
        p=self.packet([])
        m=self.message(1,time='2026-04-18T18:00:30Z')
        row=self.run_alignment([m],p)['alignment_rows'][0]['by_horizon_seconds']['30']
        self.assertTrue(row['before_support_complete'])
        m=self.message(2,time='2026-04-18T18:59:30Z')
        row=self.run_alignment([m],p)['alignment_rows'][0]['by_horizon_seconds']['30']
        self.assertFalse(row['after_support_complete'])

    def test_room_missing_invalid_and_known_different_are_explicit_not_inferred(self):
        p=self.packet([event(1),event(2,roomId='invalid'),event(3,roomId=uid(99)),event(4,roomId=uid(30))])
        out=self.run_alignment([self.message(1)],p)
        self.assertEqual({c['event_room_relation'] for c in out['alignment_rows'][0]['candidates']},{'missing','invalid','known_different','known_equal'})
        self.assertTrue(all(c['room_inferred'] is False for c in out['alignment_rows'][0]['candidates']))

    def test_controls_are_source_deterministic_and_outcome_independent(self):
        messages=[self.message(n,'The artifact is ready.',time=f'2026-04-18T18:10:{n:02d}Z') for n in range(1,8)]
        a=self.run_alignment(messages,self.packet([]),max_controls=3)
        b=self.run_alignment(messages[::-1],self.packet([event(1)]),max_controls=3)
        self.assertEqual({p['message_id'] for p in a['message_pins']},{p['message_id'] for p in b['message_pins']})
        expected=sorted(messages,key=lambda m:(alignment._hash([alignment.VERSION,m['id']]),m['id']))[:3]
        self.assertEqual({p['message_id'] for p in a['message_pins']},{m['id'] for m in expected})
        self.assertEqual(a['summary']['nonmarker_control_messages'],3)

    def test_discordant_examples_are_not_false_positive_negative_scores(self):
        messages=[self.message(1,time='2026-04-18T18:40:00Z'),self.message(2,'The artifact is ready.')]
        out=self.run_alignment(messages)
        examples=out['summary']['discordance_examples']
        self.assertEqual(examples['literal_marker_without_retained_candidate'],[messages[0]['id']])
        self.assertEqual(examples['literal_nonmarker_control_with_candidate'],[messages[1]['id']])
        self.assertNotIn('precision',out['summary']);self.assertNotIn('recall',out['summary'])

    def test_reused_event_and_overlapping_windows_count_explicitly(self):
        other={'id':'overlap','start':'2026-04-18T18:05:00Z','end_exclusive':'2026-04-18T18:20:00Z'}
        p=self.packet(windows=[WINDOW,other]);out=self.run_alignment([self.message(1),self.message(2,'paused')],p)
        self.assertEqual(out['summary']['event_message_link_reuse'],{uid(1):2})
        self.assertEqual(out['summary']['candidate_links'],2)
        self.assertEqual(len(out['alignment_rows'][0]['candidates'][0]['shared_time_window_ids']),2)

    def test_partial_truncated_missing_action_and_unknown_attribution_return_no_alignments(self):
        packets=[self.packet([event(1),event(2)],build_options={'max_rows':1}),
            self.packet([event(1),event(2)],max_rows=1),self.packet(actions=['WAIT']),
            self.packet([event(1),event(2,agentId=None)])]
        for p in packets:
            out=self.run_alignment([self.message(1)],p)
            self.assertEqual(out['status'],'unknown_alignment_scope')
            self.assertIsNone(out['alignment_rows']);self.assertIsNone(out['summary'])
            self.assertTrue(out['unknown_reasons'])

    def test_unassigned_invalid_source_time_makes_absence_unknown(self):
        p=self.packet([event(1),event(2,time='bad timestamp')])
        out=self.run_alignment([self.message(1)],p)
        self.assertIn('unassigned_invalid_source_timestamps',out['unknown_reasons'])
        self.assertIsNone(out['summary'])

    def test_budget_preflight_returns_unknown_not_partial_bands(self):
        out=self.run_alignment([self.message(1)],max_work=1)
        self.assertIn('aggregate_work_budget_exceeded',out['unknown_reasons'])
        self.assertIsNone(out['alignment_rows']);self.assertIsNone(out['summary'])

    def test_strict_bounds_refs_and_nonfinite_fail(self):
        p=self.packet();m=self.message(1)
        for key,values in (('max_controls',(True,False,0,1.5,65)),('max_work',(True,0,1.5,2_000_001))):
            for value in values:
                with self.assertRaises(ValueError):self.run_alignment([m],p,**{key:value})
        for ref in ({'unknown':{}},{'dataset':{'id':'dataset-x','version':True,'hash':'0'*64}}):
            with self.assertRaises(ValueError):self.run_alignment([m],p,source_refs=ref)
        broken=copy.deepcopy(p);broken['records'][0]['record']['seconds']=float('nan')
        with self.assertRaises(ValueError):self.run_alignment([m],broken)

    def test_source_identity_hash_time_and_metadata_forgery_rejected(self):
        p=self.packet();m=self.message(1)
        for mutate in (lambda x:x.update(agent_id=uid(21)),lambda x:x.update(content_hash='0'*64),
                       lambda x:x.update(timestamp='invalid'),lambda x:x.update(source={}),
                       lambda x:x.pop('speaker_type')):
            changed=copy.deepcopy(m);mutate(changed)
            with self.assertRaises(ValueError):self.run_alignment([changed],p)
        with self.assertRaises(ValueError):self.run_alignment([m,m],p)
        changes=[lambda x:x['index'].update(post_query_file_sha256='0'*64),
            lambda x:x['coverage'].update(query_complete=True,truncated=False,matched_rows=9),
            lambda x:x['records'][0].update(projection_sha256='0'*64),
            lambda x:x['records'][0]['source'].update(line=True),
            lambda x:x['records'][0]['record'].update(actor_id=uid(22)),
            lambda x:x['records'][0].update(window_ids=[]),
            lambda x:x['coverage'].update(scope='PRIVATE_RAW_COMMAND'),
            lambda x:x['implementation_hashes'].update({'actor_event_queries.py':'0'*64}),
            lambda x:x.pop('source_metadata_declaration')]
        for mutate in changes:
            changed=copy.deepcopy(p);mutate(changed)
            with self.assertRaises(ValueError):self.run_alignment([m],changed)

    def test_no_file_database_model_stream_access_and_no_payload_export(self):
        secret='PRIVATE_CONTENT_COMMAND_CREDENTIAL_MARKER_4242'
        m=self.message(1,secret+' waiting');p=self.packet([event(1,content=secret,output={'command':secret})])
        before=copy.deepcopy((m,p));out_stream,err_stream=io.StringIO(),io.StringIO()
        with (patch.object(builtins,'open',side_effect=AssertionError('file access')),
              patch.object(Path,'open',side_effect=AssertionError('file access')),
              patch.object(Path,'read_bytes',side_effect=AssertionError('file access')),
              patch.object(sqlite3,'connect',side_effect=AssertionError('database access')),
              patch.object(queries,'implementation_hashes',side_effect=AssertionError('code file access')),
              contextlib.redirect_stdout(out_stream),contextlib.redirect_stderr(err_stream)):
            out=self.run_alignment([m],p)
        self.assertEqual((m,p),before);self.assertEqual(out_stream.getvalue(),'');self.assertEqual(err_stream.getvalue(),'')
        self.assertNotIn(secret,json.dumps(out));self.assertEqual(out['model_calls'],0);self.assertEqual(out['database_writes'],0)

    def test_event_source_pins_preserved_and_pause_requested_not_elapsed(self):
        p=self.packet([event(1,action='PAUSE',seconds=60)]);out=self.run_alignment([self.message(1)],p)
        pin=out['event_pins'][0]
        self.assertEqual(pin['source'],p['records'][0]['source'])
        self.assertEqual(pin['projection_sha256'],p['records'][0]['projection_sha256'])
        self.assertEqual(pin['pause_requested_seconds'],60)
        self.assertIn('not elapsed',pin['pause_duration_scope'])

    def test_span_link_and_output_budgets_fail_without_partial_sampling(self):
        p=self.packet();m=self.message(1,'wait pause')
        with patch.object(alignment,'MAX_MARKER_SPANS',1),self.assertRaises(ValueError):self.run_alignment([m],p)
        p=self.packet([event(1),event(2)])
        with patch.object(alignment,'MAX_LINKS',1),self.assertRaises(ValueError):self.run_alignment([m],p)
        with patch.object(alignment,'MAX_OUTPUT_BYTES',1),self.assertRaises(ValueError):self.run_alignment([m],p)

    def test_scope_outside_windows_remains_unknown_and_extreme_date_censored(self):
        p=self.packet()
        out=self.run_alignment([self.message(1,time='2026-04-18T17:59:59Z')],p)
        self.assertEqual(out['alignment_rows'][0]['scope_unknown_reason'],'message_outside_query_time_windows')
        window={'id':'last-date','start':'9999-12-31T23:50:00Z','end_exclusive':'9999-12-31T23:59:59.999999Z'}
        p=self.packet([event(1,'9999-12-31T23:59:59Z')],windows=[window])
        out=self.run_alignment([self.message(1,time='9999-12-31T23:59:59Z')],p)
        self.assertFalse(out['alignment_rows'][0]['by_horizon_seconds']['300']['after_support_complete'])
        self.assertEqual(out['alignment_rows'][0]['by_horizon_seconds']['300']['tie'],1)


if __name__=='__main__':unittest.main()
