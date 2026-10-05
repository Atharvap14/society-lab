"""Independent temporary-source review of missing extraction and source guards."""
import copy
import unittest

from swarm_lab import graph_hodge_workflow as workflow
from swarm_lab.store import fingerprint
from tests import test_indexed_event_workflow as fixtures


class GraphHodgeWorkflowReviewTests(unittest.TestCase):
    setUp = fixtures.IndexedEventWorkflowTests.setUp
    ref = staticmethod(fixtures.IndexedEventWorkflowTests.ref)

    def no_unicode_parent(self):
        selected = self.lab.audit_selected_leads(self.discovery['id'],
            short_name_allowlist=['o3'], include_unicode_shadow=False)
        return self.lab.audit_temporal_paths(selected['id'], version=selected['version'])

    def assertMissingCellsPreserved(self, parent, result):
        original = {(window_id, variant): graph
                    for window_id, window in parent['payload']['windows'].items()
                    for variant, graph in window['variants'].items()}
        measured = {(cell['window_id'], cell['variant']): cell for cell in result['cells']}
        self.assertEqual(set(measured), set(original))
        self.assertEqual(len(result['cells']), len(original))
        self.assertEqual(result['bounds']['cells'], len(original))
        self.assertTrue(any(not graph['available'] for graph in original.values()))
        for key, graph in original.items():
            cell = measured[key]
            self.assertEqual(cell['source_graph_sha256'], fingerprint(graph))
            if not graph['available']:
                for field in ('source_reference_event_count', 'edge_source_pins', 'preflight', 'decomposition'):
                    self.assertIsNone(cell[field], field)
                self.assertIsInstance(cell['source_unavailable_reason'], str)
                self.assertTrue(cell['source_unavailable_reason'])
            else:
                self.assertEqual(cell['source_reference_event_count'], len(graph['events']))
                self.assertIsNotNone(cell['preflight'])
        available = [cell for cell in result['cells'] if cell['preflight'] is not None]
        self.assertEqual(result['bounds']['estimated_total_work'],
                         sum(cell['preflight']['bounds']['estimated_work'] for cell in available))
        self.assertEqual(result['bounds']['estimated_peak_workspace_bytes'],
                         max(cell['preflight']['bounds']['estimated_workspace_bytes'] for cell in available))

    def test_normal_no_unicode_parent_keeps_unknown_cells_and_replays(self):
        parent = self.no_unicode_parent()
        result = workflow.audit_edge_flow(self.lab, parent['id'], version=parent['version'])
        self.assertMissingCellsPreserved(parent, result['payload'])
        expected_available = sum(graph['available'] for window in parent['payload']['windows'].values()
                                 for graph in window['variants'].values())
        self.assertEqual(result['payload']['available_cells'], expected_available)
        self.assertEqual(result['payload']['status'], 'some_cells_unavailable')
        proof = workflow.replay_edge_flow(self.lab, result['id'], version=result['version'])
        self.assertTrue(proof['payload']['passed'])
        self.assertEqual(self.lab.store.usage()['calls'], 0)
        self.assertEqual(self.lab.store.list('behavior'), [])
        self.assertEqual(self.lab.store.list('theory'), [])

    def test_no_unicode_parent_with_budget_refusal_keeps_both_unknown_causes(self):
        parent = self.no_unicode_parent()
        result = workflow.derive_edge_flow(self.lab, parent['id'], version=parent['version'], max_work=1)
        self.assertMissingCellsPreserved(parent, result)
        self.assertEqual(result['status'], 'unknown_budget_scope')
        self.assertEqual(result['available_cells'], 0)
        self.assertTrue(all(cell['decomposition'] is None for cell in result['cells']))
        self.assertIn('aggregate_work_budget_exceeded', result['unknown_reasons'])
        self.assertEqual(self.lab.store.list('graph_hodge_audit'), [])

    def test_direction_forgery_with_unchanged_event_count_fails_before_operator(self):
        parent = self.lab.audit_temporal_paths(self.selected['id'], version=self.selected['version'])
        changed = copy.deepcopy(parent['payload'])
        window = next(iter(changed['windows'].values()))
        graph = next(graph for graph in window['variants'].values() if graph['available'] and graph['events'])
        event = graph['events'][0]
        alternate = next(node for node in graph['node_ids']
                         if node not in (event['source_agent_id'], event['target_agent_id']))
        event['source_agent_id'] = alternate
        forged = self.lab.store.put('temporal_path_audit', changed)
        self.assertEqual(graph['event_count'], len(graph['events']))
        with self.assertRaisesRegex(ValueError, 'does not reproduce'):
            workflow.audit_edge_flow(self.lab, forged['id'], version=forged['version'])
        self.assertEqual(self.lab.store.list('graph_hodge_audit'), [])


if __name__ == '__main__':
    unittest.main()
