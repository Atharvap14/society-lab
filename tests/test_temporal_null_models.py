"""Small synthetic reference graphs; no registry, source scan or model calls."""
from __future__ import annotations

import copy
import json
import random
import unittest
from unittest.mock import patch

from swarm_lab import temporal_null_models as nulls
from tests.test_temporal_network import analyze, explicit_window, row


def packet(rows, *, shadow=False, short=None):
    return analyze(rows, windows=[explicit_window()], include_unicode_shadow=shadow,
                   short_name_allowlist=short)


def cell(result, variant='baseline_exact', window='w'):
    return result['windows'][window]['variants'][variant]


class TemporalNullModelTests(unittest.TestCase):
    def simple(self):
        return packet([row('m1', 'a', 'Bobby', 1), row('m2', 'b', 'Carol', 2), row('m3', 'c', 'ordinary', 3)])

    def reference(self, value=None, **kwargs):
        return nulls.timestamp_permutation_reference(value or self.simple(), variants=['baseline_exact'], resamples=8, **kwargs)

    def test_original_replay_and_source_events_not_mutated(self):
        source = self.simple(); before = copy.deepcopy(source)
        result = self.reference(source)
        self.assertEqual(source, before)
        value = cell(result)
        self.assertTrue(value['observed_replay']['passed'])
        self.assertEqual(value['observed']['reachable_pair_count'], 3)
        self.assertEqual(value['observed']['maximum_loss_fraction'], 1)
        self.assertEqual(value['fixed_node_ids'], source['windows']['w']['node_universe']['ids'])
        self.assertEqual([p['original_timestamp'] for p in value['original_event_pins']],
                         [e['timestamp'] for e in source['windows']['w']['variants']['baseline_exact']['events']])
        self.assertEqual(result['model_calls'], 0); self.assertTrue(result['read_only'])
        json.dumps(result, allow_nan=False)

    def test_message_batch_moves_together_and_time_multiset_preserved(self):
        source = packet([row('m1', 'a', 'Bobby Carol', 1), row('m2', 'b', 'David', 2), row('m3', 'd', 'ordinary', 3)])
        calls = []; original = nulls._measure
        def measured(nodes, groups, assignments):
            calls.append(copy.deepcopy((groups, assignments)))
            return original(nodes, groups, assignments)
        with patch.object(nulls, '_measure', side_effect=measured):
            result = self.reference(source)
        self.assertEqual(len(calls), 9)
        for groups, assignments in calls:
            self.assertEqual(len(groups['m1']['edges']), 2)
            self.assertEqual(sorted(assignments.values()), sorted(g['original_timestamp'] for g in groups.values()))
            self.assertEqual(set(assignments), {'m1', 'm2'})
        self.assertTrue(cell(result)['reference']['message_time_multiset_preserved'])
        self.assertIn('Not guaranteed', cell(result)['reference']['edge_time_multiset_preserved'])

    def test_ties_never_gain_id_order_and_are_structurally_degenerate(self):
        source = packet([row('z', 'a', 'Bobby', 1), row('a', 'b', 'Carol', 1), row('c', 'c', 'ordinary', 2)])
        value = cell(self.reference(source))
        self.assertEqual(value['static_invariants']['static_reachable_pair_count'], 3)
        self.assertEqual(value['observed']['reachable_pair_count'], 2)
        envelope = value['reference']['metrics']['reachable_pair_count']['envelope']
        self.assertEqual(envelope['minimum'], 2); self.assertEqual(envelope['maximum'], 2)
        self.assertTrue(value['degeneracy']['assignment_structurally_degenerate'])
        self.assertEqual(value['degeneracy']['unique_sampled_assignments'], 1)
        self.assertEqual(value['reference']['metrics']['reachable_pair_count']['rank_counts']['equal_to_observed'], 8)

    def test_isolate_fixed_universe_and_zero_edge_messages_excluded(self):
        source = packet([row('m1', 'a', 'Bobby', 1), row('m2', 'b', 'ordinary', 2), row('m3', 'd', 'ordinary', 3)])
        value = cell(self.reference(source))
        self.assertEqual(value['fixed_node_ids'], ['a', 'b', 'd'])
        self.assertEqual([g['message_id'] for g in value['message_groups']], ['m1'])
        self.assertEqual(value['static_invariants']['in_degrees']['d'], 0)
        self.assertEqual(value['observed']['maximum_loss_fraction'], 0)
        self.assertTrue(value['degeneracy']['assignment_structurally_degenerate'])

    def test_empty_graph_has_undefined_loss_counts_not_imputed_zero(self):
        source = packet([])
        value = cell(self.reference(source))
        self.assertEqual(value['observed']['reachable_pair_count'], 0)
        self.assertIsNone(value['observed']['maximum_loss_fraction'])
        metric = value['reference']['metrics']['maximum_loss_fraction']
        self.assertIsNone(metric['envelope']); self.assertIsNone(metric['rank_counts'])
        self.assertEqual(metric['defined_draws'], 0); self.assertEqual(metric['undefined_draws'], 8)
        self.assertIsNotNone(value['degeneracy']['empty_scope_warning'])

    def test_two_node_endpoint_denominators_are_undefined(self):
        source = packet([row('m1', 'a', 'Bobby', 1)])
        value = cell(self.reference(source))
        self.assertEqual(value['observed']['reachable_pair_count'], 1)
        self.assertIsNone(value['observed']['maximum_loss_fraction'])
        self.assertTrue(all(r['eligible_reachable_pairs'] == 0 for r in value['observed']['node_removal']))

    def test_seed_determinism_and_cell_selection_independent_streams(self):
        source = self.simple()
        first = self.reference(source, seed=31); second = self.reference(source, seed=31)
        self.assertEqual(first, second)
        full = nulls.timestamp_permutation_reference(source, resamples=8, seed=31)
        self.assertEqual(cell(first), cell(full))
        different = self.reference(source, seed=32)
        self.assertNotEqual(cell(first)['reference']['permutation_fingerprints'], cell(different)['reference']['permutation_fingerprints'])

    def test_arbitrary_event_input_order_has_identical_reference(self):
        source = self.simple(); reordered = copy.deepcopy(source)
        for v in reordered['windows']['w']['variants'].values():
            if v.get('events') is not None:v['events'].reverse()
        self.assertEqual(self.reference(source), self.reference(reordered))

    def test_unavailable_variants_remain_unavailable_not_zero(self):
        result = nulls.timestamp_permutation_reference(self.simple(), resamples=4)
        value = cell(result, 'unicode_baseline')
        self.assertFalse(value['available']); self.assertEqual(value['status'], 'frozen_variant_unavailable')
        self.assertIsNone(value['original_event_count']); self.assertIsNone(value['reference'])
        self.assertIsNone(value['observed']); self.assertIn('not requested', value['reason'])

    def test_budget_preflight_all_unknown_no_partial_draws_or_ranks(self):
        with patch.object(nulls, '_measure') as measured:
            result = self.reference(max_work=1)
        measured.assert_not_called()
        self.assertEqual(result['status'], 'not_computed_work_budget')
        value = cell(result)
        self.assertFalse(value['available']); self.assertIsNone(value['reference'])
        self.assertIsNone(value['observed_replay']['passed']); self.assertIsNone(value['observed'])
        self.assertTrue(value['original_event_pins'])

    def test_budget_formula_covers_original_all_draws_and_node_deletions(self):
        source = self.simple(); result = self.reference(source)
        value = cell(result); n = len(value['fixed_node_ids']); e = value['original_event_count']; k = len(value['message_groups'])
        self.assertEqual(result['bounds']['estimated_work'], 4 * 9 * (n * (n + 1) * (e + n) + e + k + 1))
        accepted = self.reference(source, max_work=result['bounds']['estimated_work'])
        self.assertEqual(accepted['status'], 'complete_reference')
        self.assertEqual(self.reference(source, max_work=result['bounds']['estimated_work'] - 1)['status'], 'not_computed_work_budget')

    def test_static_graph_degrees_weights_source_counts_invariant(self):
        source = packet([row('m1', 'a', 'Bobby Carol', 1), row('m2', 'a', 'Bobby', 2), row('m3', 'b', 'Alice', 3)])
        value = cell(self.reference(source))
        invariant = value['static_invariants']
        self.assertEqual(invariant['event_count'], 4); self.assertEqual(invariant['edge_count'], 3)
        self.assertEqual(invariant['outgoing_event_counts']['a'], 3)
        self.assertEqual(invariant['incoming_event_counts']['b'], 2)
        self.assertEqual(invariant['out_degrees']['a'], 2)
        self.assertEqual(invariant['edge_bearing_messages_by_source'], {'a': 2, 'b': 1})
        self.assertTrue(invariant['asserted_each_draw']); self.assertIn('no new eigenvector', invariant['operator_policy'])

    def test_backward_path_can_move_to_forward_null_without_claiming_observed(self):
        source = packet([row('late', 'a', 'Bobby', 2), row('early', 'b', 'Carol', 1), row('c', 'c', 'ordinary', 3)])
        result = nulls.timestamp_permutation_reference(source, variants=['baseline_exact'], resamples=32, seed=41)
        value = cell(result)
        self.assertEqual(value['observed']['reachable_pair_count'], 2)
        distribution = value['reference']['metrics']['reachable_pair_count']
        self.assertEqual(distribution['envelope']['minimum'], 2); self.assertEqual(distribution['envelope']['maximum'], 3)
        self.assertGreater(distribution['rank_counts']['greater_than_observed'], 0)
        self.assertTrue(all(p['synthetic'] for p in value['reference']['permutation_fingerprints']))
        self.assertEqual(value['reference']['rank_grid_spacing_with_observed'], 1 / 33)
        self.assertNotIn('witnesses', value['reference'])

    def test_rank_counts_only_no_p_value_or_significance_field(self):
        result = self.reference()
        keys = []
        def collect(value):
            if isinstance(value, dict):
                keys.extend(value); [collect(v) for v in value.values()]
            elif isinstance(value, list):[collect(v) for v in value]
        collect(result)
        self.assertFalse(set(keys) & {'p_value', 'pvalue', 'significant', 'novelty', 'causal_effect'})
        for metric in cell(result)['reference']['metrics'].values():
            counts = metric['rank_counts']
            if counts:self.assertEqual(counts['less_than_observed'] + counts['equal_to_observed'] + counts['greater_than_observed'], counts['comparable_draws'])

    def test_raw_private_fields_nonfinite_cycles_and_bad_shapes_rejected(self):
        for modification in ('content', 'provider', 'nonfinite', 'cycle', 'wrongwindow'):
            source = self.simple()
            if modification == 'content':source['windows']['w']['variants']['baseline_exact']['events'][0]['content'] = 'DO_NOT_LEAK'
            elif modification == 'provider':source['windows']['w']['variants']['baseline_exact']['events'][0]['source']['output'] = {'private': 'DO_NOT_LEAK'}
            elif modification == 'nonfinite':source['bounds']['bad'] = float('nan')
            elif modification == 'cycle':source['bounds']['cycle'] = source['bounds']
            else:source['windows']['w'] = True
            with self.subTest(modification=modification), self.assertRaises(ValueError):self.reference(source)

    def test_parameter_typing_bounds_and_unknown_selection_rejected(self):
        source = self.simple()
        for kwargs in ({'seed': True}, {'seed': -1}, {'seed': float('inf')}, {'resamples': True}, {'resamples': 0}, {'resamples': 257},
            {'max_work': True}, {'max_work': 10000001}, {'max_work': 0}, {'window_ids': ['absent']},
            {'window_ids': ['w', 'w']}, {'variants': ['bogus']}, {'variants': []}, {'source_refs': {'api_key': 'bad'}}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):nulls.timestamp_permutation_reference(source, **kwargs)

    def test_missing_invalid_time_and_source_binding_mismatch_fail_closed(self):
        for modification in ('missing', 'invalid', 'actor', 'hash', 'unknownsource', 'self', 'room'):
            source = self.simple(); event = source['windows']['w']['variants']['baseline_exact']['events'][0]
            if modification == 'missing':event['timestamp'] = None
            elif modification == 'invalid':event['timestamp'] = 'invalid'
            elif modification == 'actor':event['source_agent_id'] = 'd'
            elif modification == 'hash':event['original_text_sha256'] = '0' * 64
            elif modification == 'unknownsource':event['message_id'] = 'fabricated'
            elif modification == 'self':event['target_agent_id'] = event['source_agent_id']
            else:event['room_id'] = 'elsewhere'
            with self.subTest(modification=modification), self.assertRaises(ValueError):self.reference(source)

    def test_duplicate_events_and_changed_fixed_universe_rejected(self):
        for modification in ('duplicate', 'node', 'boolcount', 'boolmetric', 'removal'):
            source = self.simple(); value = source['windows']['w']['variants']['baseline_exact']
            if modification == 'duplicate':value['events'].append(copy.deepcopy(value['events'][0])); value['event_count'] += 1
            elif modification == 'node':value['node_ids'] = ['a', 'b']
            elif modification == 'boolcount':value['event_count'] = True
            elif modification == 'boolmetric':value['strict_temporal']['reachable_pair_count'] = True
            else:value['strict_temporal']['node_removal']['rows'][0]['lost_pairs'] += 1
            with self.subTest(modification=modification), self.assertRaises(ValueError):self.reference(source)

    def test_typed_refs_preserved_without_external_authentication(self):
        refs = {'temporal_audit': {'id': 'temporal_path_audit-fixture', 'version': 1, 'hash': '1' * 64},
                'dataset': {'id': 'dataset-fixture', 'version': 2, 'hash': '2' * 64}}
        result = self.reference(source_refs=refs)
        self.assertEqual(result['source_refs'], refs); self.assertIsNot(result['source_refs'], refs)
        self.assertFalse(result['source_refs_authenticated'])
        for malformed in ({'dataset': {'id': 'dataset-fixture', 'version': True, 'hash': '2' * 64}},
            {'dataset': {'id': 'wrong-kind', 'version': 1, 'hash': '2' * 64}}, {'dataset': {'id': 'dataset-fixture', 'version': 1, 'hash': 'bad'}}):
            with self.assertRaises(ValueError):self.reference(source_refs=malformed)

    def test_unicode_short_variants_retain_frozen_instruments_and_common_nodes(self):
        source = packet([row('m1', 'a', 'o3 GPT\u20114.1', 1), row('m2', 's', 'Alice', 2), row('m3', 'g', 'ordinary', 3)], shadow=True, short=['o3'])
        result = nulls.timestamp_permutation_reference(source, resamples=4)
        nodes = source['windows']['w']['node_universe']['ids']
        self.assertTrue(all(v['fixed_node_ids'] == nodes for v in result['windows']['w']['variants'].values()))
        self.assertTrue(cell(result, 'unicode_expanded')['observed_replay']['passed'])
        statuses = {p['measurement_status'] for p in cell(result, 'unicode_expanded')['original_event_pins']}
        self.assertIn('formatting_match_candidate', statuses); self.assertIn('explicit_short_name_match_candidate', statuses)

    def test_independent_dfs_oracle_for_batch_reachability_and_deletion(self):
        rng = random.Random(71); nodes = ['a', 'b', 'c', 'd']
        for case in range(20):
            groups = {}; assignments = {}
            for i in range(6):
                origin, target = rng.sample(nodes, 2); identity = f'm{i}'
                groups[identity] = {'edges': [(origin, target)]}; assignments[identity] = rng.randrange(3)
            events = [(assignments[mid], a, b) for mid, g in groups.items() for a, b in g['edges']]
            def oracle(removed=None):
                found = set()
                for root in nodes:
                    if root == removed:continue
                    pending = [(root, -1)]
                    while pending:
                        current, previous = pending.pop()
                        for stamp, a, b in events:
                            if a == current and a != removed and b != removed and stamp > previous:
                                if b != root:found.add((root, b))
                                pending.append((b, stamp))
                return found
            self.assertEqual(nulls._temporal_pairs(nodes, groups, assignments), oracle())
            for node in nodes:self.assertEqual(nulls._temporal_pairs(nodes, groups, assignments, removed=node), oracle(node))

    def test_event_window_node_and_output_bounds_fail_closed(self):
        source = self.simple()
        for constant, limit in (('MAX_WINDOWS', 0), ('MAX_NODES', 2), ('MAX_EVENTS', 1), ('MAX_INPUT_BYTES', 64), ('MAX_OUTPUT_BYTES', 64)):
            with self.subTest(constant=constant), patch.object(nulls, constant, limit), self.assertRaises(ValueError):self.reference(source)

    def test_instrument_channel_schema_and_metadata_payload_guard(self):
        for modification in ('channel', 'span', 'nestedbool', 'bindingpayload', 'codehash'):
            source = self.simple(); value = source['windows']['w']['variants']['baseline_exact']
            if modification == 'channel':
                value['events'][0]['instrument'] = 'unicode_shadow'; value['events'][0]['measurement_status'] = 'formatting_match_candidate'
            elif modification == 'span':value['events'][0]['original_span_available'] = False
            elif modification == 'nestedbool':source['windows']['w']['node_universe'] = True
            elif modification == 'bindingpayload':source['source_binding']['raw_private'] = 'DO_NOT_EXPORT'
            else:source['code_hashes']['network.py']['sha256'] = 'not a hash'
            with self.subTest(modification=modification), self.assertRaises(ValueError):self.reference(source)


if __name__ == '__main__':
    unittest.main()
