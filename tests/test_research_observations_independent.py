"""Independent recorded-context invariants using temporary source fixtures.

These do not ask the context helper to replay a scanner or numeric operator.
They challenge local contradictions before a recorded summary is exposed.
"""
import copy
import unittest

from swarm_lab import research_observations as module
from tests import test_research_observations as original


class RecordedObservationIndependentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        original.ResearchObservationTests.setUpClass()

    @classmethod
    def tearDownClass(cls):
        original.ResearchObservationTests.tearDownClass()

    def setUp(self):
        self.case = original.ResearchObservationTests(
            'test_count_and_byte_budgets_withhold_whole_context_without_truncating_scores')
        self.case.setUp()

    def unavailable(self, result, observation):
        self.assertFalse(result['observations'][observation]['available'])
        self.assertIsNone(result['observations'][observation]['summary'])
        self.assertFalse(result['fresh_source_attestation'])
        self.assertFalse(result['operator_rerun'])

    def test_source_counts_reconcile_with_exact_selected_author_rows(self):
        payload = copy.deepcopy(self.case.actor['payload'])
        # Valid integer syntax cannot make more agent rows than selected rows.
        payload['source_scope']['agent_authored_records'] = 999999
        self.case.rebound('actor_events', payload)
        result = self.case.collect()
        self.unavailable(result, 'actor_events')
        self.unavailable(result, 'wait_markers')
        self.assertTrue(result['observations']['edge_algebra']['available'])

    def test_energy_fraction_cannot_exceed_whole_signal(self):
        payload = copy.deepcopy(self.case.hodge['payload'])
        cell = next(cell for cell in payload['cells']
                    if cell['decomposition']['energies']['signal']['squared_norm'] > 0)
        cell['decomposition']['energies']['gradient']['fraction_of_signal'] = 2.0
        self.case.rebound('edge_algebra', payload)
        self.unavailable(self.case.collect(), 'edge_algebra')

    def test_uncensored_status_cannot_hide_incomplete_support_flags(self):
        payload = copy.deepcopy(self.case.wait['payload'])
        row = next(row for row in payload['alignment']['alignment_rows']
                   if row['by_horizon_seconds']['30']['candidate_event_ids'])
        row['by_horizon_seconds']['30'].update(
            status='candidate_observed', before_support_complete=False,
            after_support_complete=False)
        self.case.rebound('wait_markers', payload)
        self.unavailable(self.case.collect(), 'wait_markers')

    def test_deep_accepted_body_and_decode_failure_are_explicit_unknowns(self):
        reference = self.case.refs['dataset']
        nested = 'leaf'
        for _ in range(1100):
            nested = [nested]
        self.case.store.rows[reference['id'], reference['version']]['payload'][
            'unexpected_nested_value'] = nested

        # Return the object directly so the helper's accepted-JSON boundary,
        # rather than the fixture's copying implementation, sees nesting.
        def shallow_get(identity, version=None):
            if version is None:
                version = max(ver for name, ver in self.case.store.rows
                              if name == identity)
            return self.case.store.rows[identity, version]

        self.case.store.get = shallow_get
        result = self.case.collect()
        self.assertFalse(result['available'])
        self.assertTrue(all(row['summary'] is None
                            for row in result['observations'].values()))

        # The stated byte ceiling does not bound Store decoding allocations.
        # A decoder recursion failure should nevertheless produce unknown.
        def recursion_get(*args, **kwargs):
            raise RecursionError('fixture decoder recursion limit')

        self.case.store.get = recursion_get
        result = self.case.collect()
        self.assertFalse(result['available'])
        self.assertLessEqual(len(module._bytes(result)), 24000)
        self.assertEqual(result['model_calls'], 0)
        self.assertEqual(result['database_writes'], 0)

    def test_honest_context_remains_recorded_without_fresh_attestation(self):
        result = self.case.collect()
        self.assertTrue(result['available'])
        self.assertTrue(all(row['available']
                            for row in result['observations'].values()))
        self.assertFalse(result['fresh_source_attestation'])
        self.assertFalse(result['raw_or_index_reread'])
        self.assertFalse(result['operator_rerun'])
        self.assertEqual(result['model_calls'], 0)
        self.assertEqual(result['database_writes'], 0)


if __name__ == '__main__':
    unittest.main()
