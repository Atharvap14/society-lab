"""Read-only actor/time report reproduction, source scopes and failure gates."""
import copy
import inspect
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.build_research_report import (ReadOnlyRecords, collect_actor_events,
    collect_indexed_events, collect_report, execution_inventory, render_actor_event_addition)
from swarm_lab import actor_event_workflow as workflow


class ActorEventReportTests(unittest.TestCase):
    def setUp(self):
        from tests.test_actor_event_workflow import ActorEventWorkflowTests
        self.f = ActorEventWorkflowTests('test_derivation_is_deterministic_without_audit_store_write')
        self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.extra_events();self.index = self.f.build()
        self.audit = self.f.audit(self.index)
        self.verification = workflow.replay_actor_events(self.f.lab, self.audit['id'], version=1)
        self.records = ReadOnlyRecords(self.f.lab.store.path);self.addCleanup(self.records.close)

    @staticmethod
    def pin(obj):
        return {k: obj[k] for k in ('id','version','kind','hash')}

    def pins(self, audit=None, verification=None):
        return {'audit':self.pin(audit or self.audit),'verification':self.pin(verification or self.verification)}

    def collect(self, pins=None):
        return collect_actor_events(self.records, self.pins() if pins is None else pins)

    def forged_pair(self, payload):
        audit = self.f.lab.store.put('actor_event_audit', payload)
        proof = copy.deepcopy(self.verification['payload']);proof['audit_ref'] = self.f.ref(audit)
        return self.pins(audit, self.f.lab.store.put('verification', proof))

    def assert_withheld(self, addition):
        self.assertFalse(addition['proof']['passed'])
        self.assertIsNone(addition['quantities'])
        self.assertEqual(addition['record_pins'], [])
        self.assertEqual(addition['author_source_pins'], [])
        self.assertEqual(addition['by_actor'], {})
        html = render_actor_event_addition(addition)
        self.assertIn('withheld', html)
        self.assertNotIn('Returned actor/time records; logged choices', html)
        self.assertNotIn('Actor partitions of retained records', html)

    def test_exact_old_sources_fresh_reproduction_privacy_and_no_writes(self):
        for obj in (self.f.dataset,self.f.discovery,self.f.selected,self.index):
            self.f.lab.store.put(obj['kind'], {'later':True}, obj['id'])
        before = self.records.connection.execute('SELECT COUNT(*) FROM objects').fetchone()[0]
        with patch.object(self.f.lab.store,'put',side_effect=AssertionError('report must not put')):
            addition = self.collect()
        after = self.records.connection.execute('SELECT COUNT(*) FROM objects').fetchone()[0]
        self.assertEqual(before, after)
        self.assertTrue(addition['proof']['passed'], addition['proof'])
        self.assertTrue(addition['proof']['index_artifact_reread_completed'])
        self.assertFalse(addition['proof']['full_event_source_reread'])
        self.assertEqual(addition['quantities']['records'],4)
        self.assertEqual(addition['quantities']['room_status_counts'],{'known':1,'missing':3,'invalid':0})
        self.assertEqual(addition['coverage']['other_explicit_actor_rows'],1)
        text = json.dumps(addition)
        self.assertNotIn('PRIVATE_PROVIDER_SENTINEL', text)
        self.assertNotIn(self.f.messages[0]['content'], text)
        self.assertEqual(self.f.lab.store.usage()['calls'],0)
        self.assertEqual(self.f.lab.store.list('behavior'),[])
        self.assertEqual(self.f.lab.store.list('theory'),[])

    def test_counts_types_room_imputation_query_and_author_forgery_resealed_fail(self):
        original = self.audit['payload']
        mutations = [
            lambda p:p['actor_event_summary']['total'].update(records=4000),
            lambda p:p['actor_event_summary']['total'].update(records=4.0),
            lambda p:p['actor_event_summary']['total']['action_counts'].update(WAIT=True),
            lambda p:p['actor_event_summary']['total']['room_status_counts'].update(known=4,missing=0),
            lambda p:p['query']['actor_ids'].append('00000000-0000-0000-0000-000000000099'),
            lambda p:p['query']['windows'][0].update(room_id='00000000-0000-0000-0000-000000000050'),
            lambda p:p['author_source_pins'][0].update(agent_id='00000000-0000-0000-0000-000000000099'),
            lambda p:p['actor_event_packet']['coverage'].update(query_complete=False),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                payload = copy.deepcopy(original);mutate(payload)
                self.assert_withheld(self.collect(self.forged_pair(payload)))

    def test_strict_verification_binding_and_code_failure_skip_index_read(self):
        for update in ({'audit_ref':{**self.f.ref(self.audit),'version':True}},
                       {'model_calls':False},{'index_artifact_reread_completed':False},
                       {'full_event_source_reread':True},{'result_kind':'indexed_event_audit'}):
            verification = self.f.lab.store.put('verification',{**copy.deepcopy(self.verification['payload']),**update})
            with patch('swarm_lab.actor_event_workflow.derive_selected_actor_events',side_effect=AssertionError('must not query')):
                addition = self.collect(self.pins(verification=verification))
            self.assert_withheld(addition)
            self.assertFalse(addition['proof']['index_artifact_reread_attempted'])
        with patch('swarm_lab.actor_event_workflow.implementation_hashes',return_value={}), \
             patch('swarm_lab.actor_event_workflow.derive_selected_actor_events',side_effect=AssertionError('must not query')):
            self.assert_withheld(self.collect())

    def test_changed_missing_index_and_forged_build_metadata_withhold(self):
        index_payload = copy.deepcopy(self.index['payload'])
        index_payload['build_metadata']['coverage']['physical_rows_seen'] += 1
        changed = self.f.lab.store.put('event_source_index',index_payload)
        payload = copy.deepcopy(self.audit['payload']);payload['index_ref'] = self.f.ref(changed)
        self.assert_withheld(self.collect(self.forged_pair(payload)))
        path = Path(self.index['payload']['build_metadata']['artifact']['path'])
        path.write_bytes(path.read_bytes() + b'altered')
        addition = self.collect();self.assert_withheld(addition)
        self.assertTrue(addition['proof']['index_artifact_reread_attempted'])
        self.assertFalse(addition['proof']['index_artifact_reread_completed'])
        path.unlink();self.assert_withheld(self.collect())

    def test_bad_source_pins_wrong_kinds_and_resealed_selected_window_fail(self):
        for change in ({'version':True},{'hash':'f'*64},{'extra':'unsupported'}):
            payload = copy.deepcopy(self.audit['payload']);payload['selected_audit_ref'].update(change)
            self.assert_withheld(self.collect(self.forged_pair(payload)))
        changed = copy.deepcopy(self.f.selected['payload'])
        next(iter(changed['window_measurements'].values()))['original_window']['end_exclusive'] = '2025-04-02T13:00:00Z'
        selected = self.f.lab.store.put('selected_lead_audit',changed)
        payload = copy.deepcopy(self.audit['payload']);payload['selected_audit_ref'] = self.f.ref(selected);payload['source_refs']['selected_audit'] = self.f.ref(selected)
        self.assert_withheld(self.collect(self.forged_pair(payload)))

    def test_scoped_comparison_only_with_fresh_matching_pins_and_inert_html(self):
        room_audit = self.f.lab.audit_indexed_events(self.index['id'],self.f.selected['id'])
        room_proof = self.f.lab.replay_indexed_events(room_audit['id'])
        room = collect_indexed_events(self.records,{'audit':self.pin(room_audit),'verification':self.pin(room_proof)})
        actor = self.collect();html = render_actor_event_addition(actor,room)
        self.assertIn('Same exact sources, different predicates',html)
        self.assertIn('Explicit room + time',html)
        self.assertIn('Selected actors + time; room omitted',html)
        self.assertIn('does not establish absence of actor activity',html)
        self.assertIn('not elapsed inactivity',html)
        self.assertIn('independent experimental-unit counts remain unchanged',html)
        room['references']['selected']['hash']='f'*64
        html = render_actor_event_addition(actor,room)
        self.assertNotIn('Same exact sources, different predicates',html)
        self.assertIn('numerical cross-instrument comparison is withheld',html)
        room['proof']['passed']=False
        self.assertNotIn('Same exact sources, different predicates',render_actor_event_addition(actor,room))
        actor['references']['audit']['id']='<script>inert</script>'
        html = render_actor_event_addition(actor)
        self.assertIn('&lt;script&gt;inert&lt;/script&gt;',html)
        self.assertNotIn('<script>inert</script>',html)
        before = execution_inventory({'result':{},'runs':[1]*9})
        after = execution_inventory({'result':{},'runs':[1]*9,'selected_actor_events':actor})
        self.assertEqual(before, after)

    def test_partial_build_truncated_output_and_clock_policy_are_explicit(self):
        # The initial fixture contains talks; the action is deliberately moved
        # into the bounded prefix without changing the frozen source instrument.
        events = [self.f.events[-5],*self.f.events]
        self.f.source.write_text(''.join(json.dumps(e)+'\n' for e in events),encoding='utf-8')
        index = self.f.lab.build_event_source_index(self.f.source,max_rows=5)
        audit = self.f.audit(index);proof = workflow.replay_actor_events(self.f.lab,audit['id'])
        addition = self.collect(self.pins(audit,proof))
        self.assertTrue(addition['proof']['passed'],addition['proof'])
        self.assertFalse(addition['coverage']['build_scan']['complete_scan'])
        self.assertIn('Partial builds cannot establish global absence',render_actor_event_addition(addition))
        # A complete source with a retained bound below all matches is still
        # reproducible; it supplies a retained-only summary, never full prevalence.
        audit = self.f.audit(self.index,max_rows=1);proof = workflow.replay_actor_events(self.f.lab,audit['id'])
        addition = self.collect(self.pins(audit,proof))
        self.assertTrue(addition['proof']['passed'],addition['proof'])
        self.assertTrue(addition['coverage']['truncated'])
        self.assertEqual(addition['quantities']['records'],1)
        self.assertIn('truncated summaries describe returned records only',render_actor_event_addition(addition))

    def test_raw_source_not_reread_compatible_default_and_no_unknown_pin_fallback(self):
        self.f.source.unlink()
        self.assertTrue(self.collect()['proof']['passed'])
        self.assertFalse(inspect.signature(collect_report).parameters['include_actor_events'].default)
        self.assert_withheld(self.collect({}))


if __name__ == '__main__':
    unittest.main()
