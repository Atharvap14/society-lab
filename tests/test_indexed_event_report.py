"""Fresh index/source proof gates for the standalone report, on temporary data."""
import copy
import inspect
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.build_research_report import (ReadOnlyRecords, collect_indexed_events,
    collect_report, render_indexed_event_addition)


class IndexedEventReportTests(unittest.TestCase):
    def setUp(self):
        # Reuse the public small complete source fixture, not its verdict/assertions.
        from tests.test_indexed_event_workflow import IndexedEventWorkflowTests
        self.f = IndexedEventWorkflowTests('test_bool_versions_and_query_bounds_are_refused')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.index = self.f.build()
        self.audit = self.f.audit(self.index)
        self.verification = self.f.lab.replay_indexed_events(self.audit['id'], version=1)
        self.records = ReadOnlyRecords(self.f.lab.store.path)
        self.addCleanup(self.records.close)

    @staticmethod
    def pin(obj):
        return {k: obj[k] for k in ('id', 'version', 'kind', 'hash')}

    def pins(self, audit=None, verification=None):
        return {'audit': self.pin(audit or self.audit),
                'verification': self.pin(verification or self.verification)}

    def collect(self, pins=None):
        return collect_indexed_events(self.records, self.pins() if pins is None else pins)

    def assert_withheld(self, addition):
        self.assertFalse(addition['proof']['passed'])
        self.assertIsNone(addition['quantities'])
        self.assertEqual(addition['windows'], [])
        self.assertEqual(addition['emissions'], [])
        self.assertEqual(addition['events'], [])
        html = render_indexed_event_addition(addition)
        self.assertIn('withheld', html)
        self.assertNotIn('Speaker-specific chat denominators', html)
        self.assertNotIn('First twelve chat emission diagnostics', html)

    def forged_pair(self, payload):
        audit = self.f.lab.store.put('indexed_event_audit', payload)
        proof = copy.deepcopy(self.verification['payload'])
        proof['audit_ref'] = self.f.ref(audit)
        return self.pins(audit, self.f.lab.store.put('verification', proof))

    def test_fresh_source_query_old_versions_and_provider_privacy(self):
        for record in (self.f.dataset, self.f.discovery, self.f.selected, self.index):
            self.f.lab.store.put(record['kind'], {'later': True}, record['id'])
        before = self.f.lab.store.usage()['calls']
        addition = self.collect()
        self.assertTrue(addition['proof']['passed'], addition['proof'])
        self.assertTrue(addition['proof']['index_artifact_reread_completed'])
        self.assertFalse(addition['proof']['full_event_source_reread'])
        self.assertGreater(addition['quantities']['selected_chat_records'], 0)
        self.assertEqual(addition['quantities']['emission_statuses']['matched'],
                         addition['quantities']['selected_chat_records'])
        self.assertEqual(addition['references']['index']['version'], 1)
        self.assertEqual(addition['references']['selected']['version'], 1)
        self.assertEqual(self.records.connection.total_changes, 0)
        self.assertEqual(self.f.lab.store.usage()['calls'], before)
        encoded = json.dumps(addition) + render_indexed_event_addition(addition)
        self.assertNotIn('PRIVATE_PROVIDER_SENTINEL', encoded)
        self.assertNotIn(self.f.messages[0]['content'], encoded)
        self.assertIn('WAIT', encoded)
        self.assertIn('does not test human emissions', encoded)

    def test_changed_index_bytes_or_missing_index_withhold_tables(self):
        artifact = Path(self.index['payload']['build_metadata']['artifact']['path'])
        original = artifact.read_bytes()
        artifact.write_bytes(original + b'tampered')
        addition = self.collect()
        self.assert_withheld(addition)
        self.assertTrue(addition['proof']['index_artifact_reread_attempted'])
        self.assertFalse(addition['proof']['index_artifact_reread_completed'])
        artifact.unlink()
        self.assert_withheld(self.collect())

    def test_forged_counts_and_numeric_types_cannot_use_saved_success(self):
        original = self.audit['payload']
        for field, value in (('selected_chat_records', 999999), ('selected_chat_records',
                              float(original['indexed_event_audit']['counts']['selected_chat_records'])),
                             ('projected_event_records', True)):
            with self.subTest(field=field, value=value):
                payload = copy.deepcopy(original)
                payload['indexed_event_audit']['counts'][field] = value
                self.assert_withheld(self.collect(self.forged_pair(payload)))

    def test_bad_selected_source_pins_and_resealed_selection_are_rejected(self):
        payload = copy.deepcopy(self.audit['payload'])
        payload['selected_audit_ref']['version'] = True
        self.assert_withheld(self.collect(self.forged_pair(payload)))
        changed = copy.deepcopy(self.f.selected['payload'])
        next(iter(changed['window_measurements'].values()))['original_window']['end_exclusive'] = '2025-04-02T13:00:00Z'
        selected = self.f.lab.store.put('selected_lead_audit', changed)
        payload = copy.deepcopy(self.audit['payload'])
        payload['selected_audit_ref'] = self.f.ref(selected)
        payload['source_refs']['selected_audit'] = self.f.ref(selected)
        self.assert_withheld(self.collect(self.forged_pair(payload)))

    def test_current_implementation_failure_does_not_query_index(self):
        with patch('swarm_lab.indexed_event_workflow.implementation_hashes', return_value={}), \
             patch('swarm_lab.indexed_event_workflow.derive_indexed_event_audit', side_effect=AssertionError('must not query')):
            addition = self.collect()
        self.assert_withheld(addition)
        self.assertFalse(addition['proof']['index_artifact_reread_attempted'])

    def test_resealed_registry_build_metadata_cannot_reinterpret_same_artifact(self):
        metadata = copy.deepcopy(self.index['payload'])
        metadata['build_metadata']['coverage']['physical_rows_seen'] += 1
        forged_index = self.f.lab.store.put('event_source_index', metadata)
        payload = copy.deepcopy(self.audit['payload'])
        payload['index_ref'] = self.f.ref(forged_index)
        addition = self.collect(self.forged_pair(payload))
        self.assert_withheld(addition)
        self.assertTrue(addition['proof']['index_artifact_reread_attempted'])

    def test_exact_verification_type_and_binding_required_before_query(self):
        for update in ({'audit_ref': {**self.f.ref(self.audit), 'version': 2}},
                       {'model_calls': False}, {'index_artifact_reread_completed': False},
                       {'full_event_source_reread': True}):
            proof = {**copy.deepcopy(self.verification['payload']), **update}
            verification = self.f.lab.store.put('verification', proof)
            with patch('swarm_lab.indexed_event_workflow.derive_indexed_event_audit', side_effect=AssertionError('must not query')):
                self.assert_withheld(self.collect(self.pins(verification=verification)))

    def test_partial_build_and_truncated_query_remain_visible_not_global_absence(self):
        partial = self.f.lab.build_event_source_index(self.f.source, max_rows=5)
        audit = self.f.lab.audit_indexed_events(partial['id'], self.f.selected['id'], max_query_rows=2)
        proof = self.f.lab.replay_indexed_events(audit['id'])
        addition = self.collect(self.pins(audit, proof))
        self.assertTrue(addition['proof']['passed'], addition['proof'])
        self.assertFalse(addition['coverage']['build_scan']['complete_scan'])
        self.assertFalse(addition['coverage']['query_complete'])
        self.assertTrue(addition['coverage']['truncated'])
        self.assertIn('cannot establish global absence', render_indexed_event_addition(addition))

    def test_raw_event_source_is_not_reread_and_default_is_compatible(self):
        self.f.source.unlink()
        self.assertTrue(self.collect()['proof']['passed'])
        self.assertFalse(inspect.signature(collect_report).parameters['include_indexed_events'].default)
        self.assert_withheld(self.collect({}))


if __name__ == '__main__':
    unittest.main()
