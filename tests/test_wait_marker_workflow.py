"""Real small indexed sources exercise the host authentication boundary."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from swarm_lab import actor_event_workflow as actors
from swarm_lab import wait_marker_workflow as workflow
from tests import test_indexed_event_workflow as fixtures


class WaitMarkerWorkflowTests(unittest.TestCase):
    setUp = fixtures.IndexedEventWorkflowTests.setUp
    build = fixtures.IndexedEventWorkflowTests.build
    ref = staticmethod(fixtures.IndexedEventWorkflowTests.ref)

    def actor_audit(self, **options):
        index = self.build()
        return actors.audit_selected_actor_events(self.lab, index['id'], self.selected['id'], **options)

    def test_exact_old_source_versions_reproduce_without_raw_content_or_promotions(self):
        source = self.actor_audit()
        audit = workflow.audit_wait_markers(self.lab, source['id'], version=1)
        for obj in (self.dataset, self.discovery, self.selected, source):
            self.lab.store.put(obj['kind'], {'newer': True}, obj['id'])
        proof = workflow.replay_wait_markers(self.lab, audit['id'], version=1)['payload']
        self.assertTrue(proof['passed'], proof)
        self.assertTrue(proof['index_artifact_reread_completed'])
        self.assertFalse(proof['full_event_source_reread'])
        p = audit['payload']
        self.assertEqual(p['source_refs']['dataset'], self.ref(self.dataset))
        self.assertEqual(p['source_refs']['actor_audit'], self.ref(source))
        self.assertEqual(p['alignment']['message_scope']['agent_authored_messages'], 24)
        self.assertEqual(p['alignment']['summary']['marker_messages'], 0)
        self.assertEqual(p['alignment']['summary']['nonmarker_control_messages'], 24)
        self.assertEqual(p['alignment']['status'], 'computed_recorded_temporal_association')
        self.assertTrue(all(row['chat_clock_policy'] == 'unavailable_in_normalized_chat'
                            for row in p['alignment']['message_pins']))
        serialized = json.dumps(p)
        self.assertNotIn(self.messages[0]['content'], serialized)
        self.assertNotIn('PRIVATE_PROVIDER_SENTINEL', serialized)
        self.assertFalse(p['raw_content_persisted']); self.assertFalse(p['status_promotion'])
        self.assertEqual(self.lab.store.list('behavior'), [])
        self.assertEqual(self.lab.store.list('theory'), [])
        self.assertEqual(self.lab.store.usage()['calls'], 0)

    def test_read_only_derivation_is_deterministic_and_budget_unknown_is_not_negative(self):
        source = self.actor_audit()
        first = workflow.derive_wait_marker_alignment(self.lab, source['id'])
        second = workflow.derive_wait_marker_alignment(self.lab, source['id'])
        self.assertEqual(first, second)
        self.assertEqual(self.lab.store.list('wait_marker_alignment_audit'), [])
        low = workflow.derive_wait_marker_alignment(self.lab, source['id'], max_work=1)
        self.assertEqual(low['alignment']['status'], 'unknown_alignment_scope')
        self.assertIsNone(low['alignment']['summary'])
        self.assertIsNone(low['alignment']['alignment_rows'])
        self.assertIn('aggregate_work_budget_exceeded', low['alignment']['unknown_reasons'])

    def test_action_incomplete_scope_keeps_alignment_unknown(self):
        source = self.actor_audit(action_types=['WAIT'])
        result = workflow.audit_wait_markers(self.lab, source['id'])['payload']['alignment']
        self.assertIn('WAIT_PAUSE_action_scope_incomplete', result['unknown_reasons'])
        self.assertIsNone(result['summary'])

    def test_forged_source_and_wrong_kind_reject_before_persistence(self):
        source = self.actor_audit()
        for field, value in [('model_calls', 4), ('source_audit_replay_passed', False)]:
            changed = copy.deepcopy(source['payload']); changed[field] = value
            forged = self.lab.store.put('actor_event_audit', changed)
            with self.subTest(field=field), self.assertRaises(ValueError):
                workflow.audit_wait_markers(self.lab, forged['id'])
        with self.assertRaises(ValueError): workflow.audit_wait_markers(self.lab, self.dataset['id'])
        self.assertEqual(self.lab.store.list('wait_marker_alignment_audit'), [])

    def test_changed_index_bytes_and_changed_instrument_pins_fail_replay(self):
        source = self.actor_audit()
        audit = workflow.audit_wait_markers(self.lab, source['id'])
        original = workflow.implementation_hashes
        with patch.object(workflow, 'implementation_hashes', side_effect=lambda: {**original(), 'changed': '0'*64}):
            proof = workflow.replay_wait_markers(self.lab, audit['id'])['payload']
        self.assertFalse(proof['passed']); self.assertFalse(proof['source_replay_attempted'])
        index = self.lab.store.get(source['payload']['index_ref']['id'])
        with Path(index['payload']['build_metadata']['artifact']['path']).open('ab') as handle:
            handle.write(b'changed')
        proof = workflow.replay_wait_markers(self.lab, audit['id'])['payload']
        self.assertFalse(proof['passed']); self.assertTrue(proof['source_replay_attempted'])
        self.assertFalse(proof['source_replay_completed'])

    def test_strict_versions_and_bounds_reject(self):
        source = self.actor_audit()
        for options in ({'version': True}, {'max_controls': 0}, {'max_controls': 65},
                        {'max_work': True}, {'max_work': 2_000_001}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                workflow.audit_wait_markers(self.lab, source['id'], **options)
        audit = workflow.audit_wait_markers(self.lab, source['id'])
        with self.assertRaises(ValueError): workflow.replay_wait_markers(self.lab, audit['id'], version=True)


if __name__ == '__main__': unittest.main()
