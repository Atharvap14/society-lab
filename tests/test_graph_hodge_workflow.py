"""Source-bound operator checks with small frozen graph selections."""
import copy
import json
import sys
import unittest
from unittest.mock import patch

from swarm_lab import graph_hodge_workflow as workflow
from tests import test_indexed_event_workflow as fixtures


class GraphHodgeWorkflowTests(unittest.TestCase):
    setUp = fixtures.IndexedEventWorkflowTests.setUp
    ref = staticmethod(fixtures.IndexedEventWorkflowTests.ref)

    def parent(self):
        return self.lab.audit_temporal_paths(self.selected['id'], version=self.selected['version'])

    def test_supported_balanced_edge_survives_with_both_source_directions(self):
        events = [{'event_id': 'one', 'source_agent_id': 'a', 'target_agent_id': 'b'},
                  {'event_id': 'two', 'source_agent_id': 'b', 'target_agent_id': 'a'}]
        edges, pins = workflow.directional_count_signal(['b', 'a', 'isolated'], events)
        self.assertEqual(edges, [{'id': 'edge-0000', 'source': 'a', 'target': 'b', 'value': 0}])
        self.assertEqual(pins[0]['forward_reference_events'], 1)
        self.assertEqual(pins[0]['reverse_reference_events'], 1)
        self.assertEqual({p['event_id'] for p in pins[0]['event_pins']}, {'one', 'two'})
        for bad in ([*events, events[0]], [{'event_id': 'one', 'source_agent_id': 'a', 'target_agent_id': 'a'}],
                    [{'event_id': 'one', 'source_agent_id': 'a', 'target_agent_id': 'absent'}]):
            with self.assertRaises(ValueError): workflow.directional_count_signal(['a', 'b'], bad)

    def test_all_parent_cells_exact_old_versions_and_whole_payload_reproduce(self):
        parent = self.parent()
        expected_cells = sum(len(w['variants']) for w in parent['payload']['windows'].values())
        result = workflow.audit_edge_flow(self.lab, parent['id'], version=1)
        for obj in (self.dataset, self.discovery, self.selected, parent):
            self.lab.store.put(obj['kind'], {'newer': True}, obj['id'])
        proof = workflow.replay_edge_flow(self.lab, result['id'], version=1)['payload']
        self.assertTrue(proof['passed'], proof)
        p = result['payload']
        self.assertEqual(p['bounds']['cells'], expected_cells)
        self.assertEqual(p['available_cells'], expected_cells)
        self.assertEqual(p['source_refs']['dataset'], self.ref(self.dataset))
        for cell in p['cells']:
            decomposition = cell['decomposition']
            self.assertEqual(decomposition['scope']['two_cell_model'], 'unspecified')
            self.assertIsNone(decomposition['canonical_input']['faces'])
            self.assertFalse(decomposition['scope']['cliques_automatically_filled'])
            self.assertEqual(sum(pin['forward_reference_events'] + pin['reverse_reference_events']
                                 for pin in cell['edge_source_pins']), cell['source_reference_event_count'])
        self.assertFalse(p['raw_content_persisted']); self.assertFalse(p['status_promotion'])
        self.assertNotIn(self.messages[0]['content'], json.dumps(p))
        self.assertEqual(self.lab.store.list('behavior'), [])
        self.assertEqual(self.lab.store.list('theory'), [])
        self.assertEqual(self.lab.store.usage()['calls'], 0)

    def test_aggregate_budget_preflight_keeps_every_cell_unknown_without_partial_numerics(self):
        parent = self.parent()
        original = workflow.operator.decompose_edge_signal
        with patch.object(workflow.operator, 'decompose_edge_signal', wraps=original) as calls:
            result = workflow.derive_edge_flow(self.lab, parent['id'], max_work=1)
        self.assertEqual(result['status'], 'unknown_budget_scope')
        self.assertIn('aggregate_work_budget_exceeded', result['unknown_reasons'])
        self.assertEqual(result['available_cells'], 0)
        self.assertTrue(all(cell['decomposition'] is None for cell in result['cells']))
        self.assertTrue(all(call.kwargs['max_work'] == 1 and call.kwargs['max_memory_bytes'] == 1
                            for call in calls.call_args_list))
        self.assertEqual(self.lab.store.list('graph_hodge_audit'), [])

    def test_optional_backend_unknown_is_not_zero_energy(self):
        parent = self.parent()
        with patch.dict(sys.modules, {'numpy': None}):
            p = workflow.derive_edge_flow(self.lab, parent['id'])
        self.assertEqual(p['status'], 'some_cells_unavailable')
        self.assertEqual(p['available_cells'], 0)
        self.assertTrue(all(cell['decomposition']['energies'] is None for cell in p['cells']))

    def test_forged_parent_and_changed_code_pins_reject(self):
        parent = self.parent()
        changed = copy.deepcopy(parent['payload'])
        cell = next(iter(next(iter(changed['windows'].values()))['variants'].values()))
        cell['event_count'] += 1
        forged = self.lab.store.put('temporal_path_audit', changed)
        with self.assertRaises(ValueError): workflow.audit_edge_flow(self.lab, forged['id'])
        with self.assertRaises(ValueError): workflow.audit_edge_flow(self.lab, self.dataset['id'])
        result = workflow.audit_edge_flow(self.lab, parent['id'])
        original = workflow.implementation_hashes
        with patch.object(workflow, 'implementation_hashes', side_effect=lambda: {**original(), 'changed': '0'*64}):
            proof = workflow.replay_edge_flow(self.lab, result['id'])['payload']
        self.assertFalse(proof['passed']); self.assertFalse(proof['source_replay_attempted'])

    def test_typed_versions_work_and_memory(self):
        parent = self.parent()
        for options in ({'version': True}, {'max_work': 0}, {'max_work': True},
                        {'max_memory_bytes': True}, {'max_memory_bytes': 64*1024**2 + 1}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                workflow.audit_edge_flow(self.lab, parent['id'], **options)


if __name__ == '__main__': unittest.main()
