import builtins
import copy
import hashlib
import itertools
import json
import math
import random
import unittest
from unittest.mock import patch

import numpy as np

from swarm_lab import graph_hodge as hodge


def edge(name, source, target, value):
    return {'id': name, 'source': source, 'target': target, 'value': value}


def triangle():
    return ['a', 'b', 'c'], [edge('ab', 'a', 'b', 1), edge('bc', 'b', 'c', 1), edge('ca', 'c', 'a', 1)]


def dot(a, b):
    return math.fsum(x*y for x, y in zip(a, b))


def gaussian(matrix, rhs):
    """Independent tiny anchored-Laplacian solve; no NumPy or production helpers."""
    a = [list(row) + [b] for row, b in zip(matrix, rhs)]
    n = len(a)
    for column in range(n):
        pivot = max(range(column, n), key=lambda row: abs(a[row][column]))
        if abs(a[pivot][column]) < 1e-12:
            raise AssertionError('Unexpected singular anchored component')
        a[column], a[pivot] = a[pivot], a[column]
        divisor = a[column][column]
        a[column] = [value/divisor for value in a[column]]
        for row in range(n):
            if row == column:
                continue
            factor = a[row][column]
            a[row] = [x-factor*y for x, y in zip(a[row], a[column])]
    return [row[-1] for row in a]


def oracle(nodes, edges, faces):
    """Anchored normal equations plus twice-reorthogonalized boundary vectors."""
    nodes = sorted(nodes)
    edges = sorted(edges, key=lambda e: e['id'])
    adjacency = {node: set() for node in nodes}
    for e in edges:
        adjacency[e['source']].add(e['target'])
        adjacency[e['target']].add(e['source'])
    potential, seen = {}, set()
    for first in nodes:
        if first in seen:
            continue
        pending, component = [first], []
        seen.add(first)
        while pending:
            current = pending.pop()
            component.append(current)
            for other in sorted(adjacency[current]):
                if other not in seen:
                    seen.add(other)
                    pending.append(other)
        component.sort()
        free = component[1:]
        laplacian, rhs = [], []
        for source in free:
            laplacian.append([float(len(adjacency[source])) if source == target else
                              -1.0 if target in adjacency[source] else 0.0 for target in free])
            rhs.append(math.fsum(e['value'] * (int(e['target'] == source)-int(e['source'] == source))
                                  for e in edges))
        values = [0.0] + gaussian(laplacian, rhs)
        average = math.fsum(values)/len(component)
        potential.update({node: value-average for node, value in zip(component, values)})
    gradient = [potential[e['target']]-potential[e['source']] for e in edges]
    circulation = [e['value']-g for e, g in zip(edges, gradient)]
    if faces is None:
        return potential, gradient, circulation, None, None
    basis = []
    for face in sorted(faces, key=lambda f: f['id']):
        loop = set(zip(face['nodes'], face['nodes'][1:] + face['nodes'][:1]))
        vector = [1.0 if (e['source'], e['target']) in loop else
                  -1.0 if (e['target'], e['source']) in loop else 0.0 for e in edges]
        for _ in range(2):
            for q in basis:
                coefficient = dot(vector, q)
                vector = [v-coefficient*b for v, b in zip(vector, q)]
        norm = math.sqrt(dot(vector, vector))
        if norm > 1e-10:
            basis.append([value/norm for value in vector])
    coefficients = [dot(circulation, q) for q in basis]
    curl = [math.fsum(c*q[i] for c, q in zip(coefficients, basis)) for i in range(len(edges))]
    harmonic = [c-u for c, u in zip(circulation, curl)]
    return potential, gradient, circulation, curl, harmonic


class HodgeTests(unittest.TestCase):
    def assertComputed(self, result):
        self.assertTrue(result['available'], result['reason'])
        self.assertEqual(result['status'], 'computed')
        self.assertTrue(result['diagnostics']['passed'])
        self.assertTrue(all(row['passed'] for row in result['diagnostics']['checks_in_normalized_signal_coordinates']))
        json.dumps(result, allow_nan=False)

    def assertOracle(self, nodes, edges, faces):
        result = hodge.decompose_edge_signal(nodes, edges, faces=faces)
        self.assertComputed(result)
        p, g, c, u, a = oracle(nodes, edges, faces)
        for row in result['components']['node_potential']:
            self.assertAlmostEqual(row['value'], p[row['node_id']], places=8)
        for i, row in enumerate(result['components']['edges']):
            for name, expected in [('gradient', g), ('circulation', c), ('curl', u), ('harmonic', a)]:
                if expected is None:
                    self.assertIsNone(row[name])
                else:
                    self.assertAlmostEqual(row[name], expected[i], places=8)
        return result

    def test_tree_recovers_every_signal_as_gradient(self):
        result = self.assertOracle(['a', 'b', 'c', 'd'],
                                 [edge('ab', 'a', 'b', 3), edge('cb', 'c', 'b', -2), edge('cd', 'c', 'd', 5)], [])
        self.assertEqual(result['topology']['circulation_dimension_exact'], 0)
        self.assertAlmostEqual(result['energies']['gradient']['fraction_of_signal'], 1)
        self.assertAlmostEqual(result['energies']['circulation']['squared_norm'], 0)

    def test_triangle_unspecified_faces_does_not_invent_harmonic_split(self):
        nodes, edges = triangle()
        result = self.assertOracle(nodes, edges, None)
        self.assertEqual(result['scope']['two_cell_model'], 'unspecified')
        self.assertIsNone(result['energies']['curl'])
        self.assertIsNone(result['energies']['harmonic'])
        self.assertIsNone(result['topology']['harmonic_dimension_numerical'])
        self.assertIsNone(result['components']['face_boundary_coefficients'])

    def test_triangle_explicitly_empty_complex_is_harmonic(self):
        nodes, edges = triangle()
        result = self.assertOracle(nodes, edges, [])
        self.assertEqual(result['scope']['two_cell_model'], 'declared_empty')
        self.assertEqual(result['topology']['harmonic_dimension_numerical'], 1)
        self.assertAlmostEqual(result['energies']['harmonic']['squared_norm'], 3)
        self.assertAlmostEqual(result['energies']['curl']['squared_norm'], 0)

    def test_triangle_explicit_filled_face_is_curl(self):
        nodes, edges = triangle()
        result = self.assertOracle(nodes, edges, [{'id': 'abc', 'nodes': nodes}])
        self.assertEqual(result['topology']['curl_dimension_numerical'], 1)
        self.assertEqual(result['topology']['harmonic_dimension_numerical'], 0)
        self.assertAlmostEqual(result['energies']['curl']['squared_norm'], 3)
        self.assertAlmostEqual(result['components']['declared_face_curl_observables'][0]['value'], 3)
        self.assertAlmostEqual(result['components']['face_boundary_coefficients'][0]['value'], 1)

    def test_long_unfilled_cycle_is_harmonic_relative_to_empty_complex(self):
        edges = [edge('ab', 'a', 'b', 2), edge('bc', 'b', 'c', 2),
                 edge('cd', 'c', 'd', 2), edge('da', 'd', 'a', 2)]
        result = self.assertOracle(['a', 'b', 'c', 'd'], edges, [])
        self.assertAlmostEqual(result['energies']['harmonic']['squared_norm'], 16)
        self.assertEqual(result['topology']['circulation_dimension_exact'], 1)

    def test_known_gradient_curl_harmonic_superposition(self):
        nodes = ['a', 'b', 'c', 'd', 'e', 'f']
        p = dict(zip(nodes, [-2, -1, 0, 1, 2, 3]))
        cycles = [('a', 'b', 2), ('b', 'c', 2), ('c', 'a', 2),
                  ('c', 'd', 3), ('d', 'e', 3), ('e', 'f', 3), ('f', 'c', 3)]
        edges = [edge(a+b, a, b, p[b]-p[a]+cycle) for a, b, cycle in cycles]
        result = self.assertOracle(nodes, edges, [{'id': 'abc', 'nodes': ['a', 'b', 'c']}])
        for row in result['components']['edges']:
            is_triangle = {row['source'], row['target']} <= {'a', 'b', 'c'}
            self.assertAlmostEqual(row['curl'], 2 if is_triangle else 0)
            self.assertAlmostEqual(row['harmonic'], 0 if is_triangle else 3)
        self.assertEqual(result['topology']['harmonic_dimension_numerical'], 1)

    def test_disconnected_component_gauges_and_isolate(self):
        result = self.assertOracle(['a', 'b', 'c', 'd', 'z'],
                                  [edge('ab', 'a', 'b', 4), edge('dc', 'd', 'c', -6)], [])
        self.assertEqual(result['topology']['connected_components'], [['a', 'b'], ['c', 'd'], ['z']])
        p = {row['node_id']: row['value'] for row in result['components']['node_potential']}
        self.assertEqual(p['z'], 0)
        self.assertAlmostEqual(p['a']+p['b'], 0)
        self.assertAlmostEqual(p['c']+p['d'], 0)

    def test_empty_and_isolate_only_graphs(self):
        for nodes in [[], ['a'], ['a', 'b']]:
            result = self.assertOracle(nodes, [], [])
            self.assertEqual(result['topology']['gradient_dimension_exact'], 0)
            self.assertEqual(result['topology']['circulation_dimension_exact'], 0)
            self.assertIsNone(result['energies']['gradient']['fraction_of_signal'])

    def test_zero_signal_has_undefined_fractions(self):
        nodes, edges = triangle()
        for e in edges:
            e['value'] = 0
        result = self.assertOracle(nodes, edges, [{'id': 'face', 'nodes': nodes}])
        self.assertTrue(result['diagnostics']['zero_input_signal'])
        for item in result['energies'].values():
            self.assertEqual(item['squared_norm'], 0)
            self.assertIsNone(item['fraction_of_signal'])

    def test_balanced_zero_valued_supported_edges_are_retained(self):
        result = hodge.decompose_edge_signal(['a', 'b', 'c'],
                                            [edge('ab', 'a', 'b', 0), edge('bc', 'b', 'c', 0)])
        self.assertComputed(result)
        self.assertEqual(result['scope']['edge_count'], 2)
        self.assertEqual(len(result['components']['edges']), 2)
        self.assertEqual(result['topology']['component_count'], 1)
        self.assertEqual(result['topology']['gradient_dimension_exact'], 2)

    def test_orientation_reversal_preserves_fit_and_energies(self):
        nodes, edges = triangle()
        edges[0]['value'] = 4
        faces = [{'id': 'abc', 'nodes': nodes}]
        first = self.assertOracle(nodes, edges, faces)
        changed = copy.deepcopy(edges)
        changed[0]['source'], changed[0]['target'] = changed[0]['target'], changed[0]['source']
        changed[0]['value'] = -changed[0]['value']
        second = self.assertOracle(nodes, changed, faces)
        for one, two in zip(first['components']['node_potential'], second['components']['node_potential']):
            self.assertAlmostEqual(one['value'], two['value'])
        for name in first['energies']:
            self.assertAlmostEqual(first['energies'][name]['squared_norm'], second['energies'][name]['squared_norm'])
        for one, two in zip(first['components']['edges'], second['components']['edges']):
            sign = -1 if one['id'] == 'ab' else 1
            for name in ['gradient', 'circulation', 'curl', 'harmonic']:
                self.assertAlmostEqual(one[name]*sign, two[name])
        self.assertNotEqual(first['input_fingerprint']['sha256'], second['input_fingerprint']['sha256'])

    def test_face_orientation_reversal_changes_coefficients_not_edge_projection(self):
        nodes, edges = triangle()
        first = self.assertOracle(nodes, edges, [{'id': 'f', 'nodes': ['a', 'b', 'c']}])
        second = self.assertOracle(nodes, edges, [{'id': 'f', 'nodes': ['a', 'c', 'b']}])
        self.assertAlmostEqual(first['components']['face_boundary_coefficients'][0]['value'],
                               -second['components']['face_boundary_coefficients'][0]['value'])
        self.assertAlmostEqual(first['components']['declared_face_curl_observables'][0]['value'],
                               -second['components']['declared_face_curl_observables'][0]['value'])
        for a, b in zip(first['components']['edges'], second['components']['edges']):
            self.assertAlmostEqual(a['curl'], b['curl'])

    def test_dependent_face_boundaries_are_ranked_not_counted(self):
        nodes = ['a', 'b', 'c', 'd']
        edges = [edge(a+b, a, b, {'ab': 1, 'bc': 1, 'ac': -1}.get(a+b, 0))
                 for a, b in itertools.combinations(nodes, 2)]
        faces = [{'id': ''.join(vertices), 'nodes': list(vertices)}
                 for vertices in itertools.combinations(nodes, 3)]
        result = self.assertOracle(nodes, edges, faces)
        self.assertEqual(result['scope']['declared_face_count'], 4)
        self.assertEqual(result['topology']['curl_dimension_numerical'], 3)
        self.assertEqual(result['topology']['harmonic_dimension_numerical'], 0)

    def test_random_small_graphs_against_independent_projection_oracle(self):
        rng = random.Random(28019)
        for case in range(50):
            nodes = [str(i) for i in range(rng.randint(1, 7))]
            edges = []
            for a, b in itertools.combinations(nodes, 2):
                if rng.random() < .48:
                    a, b = (a, b) if rng.random() < .5 else (b, a)
                    edges.append(edge(a+'_'+b, a, b, rng.randint(-5, 5)))
            support = {frozenset((e['source'], e['target'])) for e in edges}
            faces = []
            for vertices in itertools.combinations(nodes, 3):
                if all(frozenset(pair) in support for pair in itertools.combinations(vertices, 2)) and rng.random() < .5:
                    faces.append({'id': '_'.join(vertices), 'nodes': list(vertices)})
            with self.subTest(case=case):
                self.assertOracle(nodes, edges, faces)

    def test_input_order_is_canonical_and_inputs_unchanged(self):
        nodes, edges = triangle()
        faces = [{'id': 'face', 'nodes': nodes[:]}]
        before = copy.deepcopy((nodes, edges, faces))
        first = hodge.decompose_edge_signal(nodes, edges, faces=faces)
        second = hodge.decompose_edge_signal(list(reversed(nodes)), list(reversed(edges)), faces=faces)
        self.assertEqual(first, second)
        self.assertEqual((nodes, edges, faces), before)
        payload = first['canonical_input']
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
        self.assertEqual(first['input_fingerprint']['sha256'], hashlib.sha256(encoded).hexdigest())

    def test_numeric_representation_and_face_omission_are_pinned(self):
        nodes, edges = triangle()
        first = hodge.decompose_edge_signal(nodes, edges)
        edges[0]['value'] = 1.0
        second = hodge.decompose_edge_signal(nodes, edges)
        third = hodge.decompose_edge_signal(nodes, edges, faces=[])
        self.assertNotEqual(first['input_fingerprint']['sha256'], second['input_fingerprint']['sha256'])
        self.assertNotEqual(second['input_fingerprint']['sha256'], third['input_fingerprint']['sha256'])

    def test_explicit_budget_unknown_has_no_partial_numeric_claims(self):
        nodes, edges = triangle()
        for kwargs, reason in [({'max_work': 1}, 'aggregate_work_budget_exceeded'),
                               ({'max_memory_bytes': 1}, 'estimated_workspace_budget_exceeded')]:
            result = hodge.decompose_edge_signal(nodes, edges, **kwargs)
            self.assertFalse(result['available'])
            self.assertEqual(result['reason'], reason)
            self.assertIsNone(result['components'])
            self.assertIsNone(result['energies'])
            self.assertIsNone(result['backend'])
            self.assertFalse(result['bounds']['sampling_or_truncation'])

    def test_bounds_are_strict_positive_ints(self):
        for parameter in ['max_work', 'max_memory_bytes']:
            for bad in [True, False, 1.0, 0, -1, None, '8', 10**12]:
                with self.subTest(parameter=parameter, bad=bad), self.assertRaises(ValueError):
                    hodge.decompose_edge_signal([], [], **{parameter: bad})

    def test_missing_optional_backend_is_explicit(self):
        original = builtins.__import__

        def no_numpy(name, *args, **kwargs):
            if name == 'numpy':
                raise ImportError('test')
            return original(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=no_numpy):
            result = hodge.decompose_edge_signal(*triangle())
        self.assertEqual(result['reason'], 'optional_numpy_backend_unavailable')
        self.assertFalse(result['available'])
        self.assertIsNone(result['components'])

    def test_nonfinite_backend_result_cannot_escape_in_unknown_diagnostics(self):
        with patch('numpy.linalg.lstsq', return_value=(np.full(3, float('nan')), np.array([]), 2, np.zeros(3))):
            result = hodge.decompose_edge_signal(*triangle())
        self.assertFalse(result['available'])
        self.assertIsNone(result['components'])
        json.dumps(result, allow_nan=False)

    def test_backend_failures_and_bad_results_remain_unknown(self):
        for failure in [np.linalg.LinAlgError('test'), MemoryError('test')]:
            with patch('numpy.linalg.lstsq', side_effect=failure):
                result = hodge.decompose_edge_signal(*triangle())
            self.assertFalse(result['available'])
            self.assertEqual(result['reason'], 'numerical_backend_or_range_failed')
            json.dumps(result, allow_nan=False)
        with patch('numpy.linalg.lstsq', return_value=(np.zeros(3), np.array([]), 0, np.zeros(3))):
            result = hodge.decompose_edge_signal(*triangle())
        self.assertFalse(result['available'])
        self.assertEqual(result['reason'], 'numerical_validation_failed')
        self.assertIsNone(result['components'])

    def test_energy_underflow_is_unavailable_not_a_zero_signal(self):
        result = hodge.decompose_edge_signal(['a', 'b'], [edge('ab', 'a', 'b', 1e-200)], faces=[])
        self.assertComputed(result)
        self.assertFalse(result['diagnostics']['zero_input_signal'])
        self.assertIsNone(result['energies']['signal']['squared_norm'])
        self.assertEqual(result['energies']['signal']['squared_norm_status'], 'unavailable_float64_underflow')
        self.assertAlmostEqual(result['energies']['gradient']['fraction_of_signal'], 1)

    def test_subnormal_coordinate_conversion_fails_closed_when_not_representable(self):
        result = hodge.decompose_edge_signal(['a', 'b'], [edge('ab', 'a', 'b', 5e-324)], faces=[])
        self.assertFalse(result['available'])
        self.assertEqual(result['reason'], 'natural_unit_conversion_validation_failed')
        self.assertIsNone(result['components'])
        json.dumps(result, allow_nan=False)

    def test_large_finite_signal_is_scaled_and_safe(self):
        result = hodge.decompose_edge_signal(['a', 'b'], [edge('ab', 'a', 'b', 1e100)], faces=[])
        self.assertComputed(result)
        self.assertAlmostEqual(result['energies']['signal']['squared_norm']/1e200, 1)
        self.assertLess(result['diagnostics']['signal_scale'], math.inf)

    def test_extreme_dynamic_range_does_not_silently_drop_nonzero_edge(self):
        result = hodge.decompose_edge_signal(['a', 'b', 'c'],
                                            [edge('ab', 'a', 'b', 1e100), edge('bc', 'b', 'c', 1e-300)])
        self.assertFalse(result['available'])
        self.assertEqual(result['reason'], 'input_signal_normalization_underflow')
        self.assertIsNone(result['components'])

    def test_energy_scaling_can_recover_natural_energy_when_normalized_square_underflows(self):
        energy = hodge._energy(np.array([1e-200, -1e-200]), 1.0, 1e100)
        self.assertIsNone(energy['normalized_squared_norm'])
        self.assertIsNone(energy['fraction_of_signal'])
        self.assertEqual(energy['normalized_squared_norm_status'], 'unavailable_float64_underflow')
        self.assertEqual(energy['squared_norm_status'], 'available')
        self.assertAlmostEqual(energy['squared_norm']/2e-200, 1)

    def test_independent_returned_coordinate_divergence_curl_and_energy_checks(self):
        nodes, edges = triangle()
        edges[0]['value'] = 5
        result = hodge.decompose_edge_signal(nodes, edges, faces=[{'id': 'abc', 'nodes': nodes}])
        self.assertComputed(result)
        rows = result['components']['edges']
        for component in ['circulation', 'curl', 'harmonic']:
            for node in nodes:
                divergence = math.fsum(row[component] * (int(row['source'] == node)-int(row['target'] == node))
                                       for row in rows)
                self.assertAlmostEqual(divergence, 0, places=9)
        self.assertAlmostEqual(math.fsum(row['harmonic'] for row in rows), 0, places=9)
        for first, second in [('gradient', 'curl'), ('gradient', 'harmonic'), ('curl', 'harmonic')]:
            self.assertAlmostEqual(math.fsum(row[first]*row[second] for row in rows), 0, places=9)
        expected_signal = math.fsum(row['signal']**2 for row in rows)
        measured = math.fsum(math.fsum(row[name]**2 for row in rows) for name in ['gradient', 'curl', 'harmonic'])
        self.assertAlmostEqual(expected_signal, measured, places=8)

    def test_malformed_nodes_and_ids_are_rejected(self):
        bad_nodes = [(), None, ['a', 'a'], [True], [''], [' '], ['a\n'], ['x'*129], ['\ud800'], [str(i) for i in range(129)]]
        for nodes in bad_nodes:
            with self.subTest(nodes=repr(nodes)), self.assertRaises(ValueError):
                hodge.decompose_edge_signal(nodes, [])

    def test_nonfinite_bool_and_oversized_signal_values_are_rejected(self):
        for value in [True, False, float('nan'), float('inf'), -float('inf'), '1', None, [], 1e101, 10**400]:
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                hodge.decompose_edge_signal(['a', 'b'], [edge('ab', 'a', 'b', value)])

    def test_nonstring_field_keys_are_rejected_before_callback_hashing(self):
        class Trap:
            active = False

            def __hash__(self):
                if self.active:
                    raise AssertionError('No input callback execution')
                return 128391

        trap = Trap()
        bad = {'id': 'ab', 'source': 'a', 'target': 'b', trap: 1}
        trap.active = True
        with self.assertRaises(ValueError):
            hodge.decompose_edge_signal(['a', 'b'], [bad])
        with self.assertRaises(ValueError):
            hodge.decompose_edge_signal(['a', 'b'], [edge('ab', 'a', 'b', -(1 << 1_000_000))])

    def test_invalid_parallel_self_missing_endpoint_and_duplicate_ids_rejected(self):
        cases = [[edge('ab', 'a', 'a', 1)], [edge('ab', 'a', 'x', 1)],
                 [edge('ab', 'a', 'b', 1), edge('ba', 'b', 'a', 2)],
                 [edge('same', 'a', 'b', 1), edge('same', 'b', 'c', 2)],
                 [dict(id='ab', source='a', target='b')],
                 [dict(edge('ab', 'a', 'b', 1), content='do not execute')],
                 [edge(True, 'a', 'b', 1)], [edge('ab', [], 'b', 1)],
                 [edge('ab', 'a', 'b', 1)]*513]
        for edges in cases:
            with self.subTest(edges=repr(edges)[:180]), self.assertRaises(ValueError):
                hodge.decompose_edge_signal(['a', 'b', 'c'], edges)

    def test_invalid_faces_and_missing_boundary_rejected(self):
        nodes, edges = triangle()
        bad_faces = [True, (), [{'id': 'f', 'nodes': ['a', 'a', 'b']}],
                     [{'id': 'f', 'nodes': ['a', 'b', 'x']}],
                     [{'id': 'f', 'nodes': ('a', 'b', 'c')}],
                     [{'id': 'f', 'nodes': nodes, 'content': 'inert'}],
                     [{'id': 'f', 'nodes': nodes}, {'id': 'g', 'nodes': ['a', 'c', 'b']}],
                     [{'id': 'f', 'nodes': nodes}]*257]
        for faces in bad_faces:
            with self.subTest(faces=repr(faces)[:180]), self.assertRaises(ValueError):
                hodge.decompose_edge_signal(nodes, edges, faces=faces)
        with self.assertRaises(ValueError):
            hodge.decompose_edge_signal(nodes, edges[:2], faces=[{'id': 'f', 'nodes': nodes}])

    def test_dense_budget_preflight_precedes_solver_allocation(self):
        nodes = [str(i) for i in range(128)]
        pairs = list(itertools.combinations(nodes, 2))[:512]
        edges = [edge(str(i), a, b, 1) for i, (a, b) in enumerate(pairs)]
        with patch('numpy.zeros', side_effect=AssertionError('must preflight')):
            result = hodge.decompose_edge_signal(nodes, edges, max_work=100)
        self.assertFalse(result['available'])

    def test_no_source_file_or_network_access_and_no_raw_payload_passthrough(self):
        with patch('builtins.open', side_effect=AssertionError('pure API')), \
                patch('socket.socket', side_effect=AssertionError('pure API')):
            result = hodge.decompose_edge_signal(*triangle())
        self.assertComputed(result)
        self.assertFalse(result['input_fingerprint']['source_authenticated'])
        self.assertFalse(result['scope']['caller_signal_semantics_verified'])
        self.assertEqual(result['model_calls'], 0)
        self.assertNotIn('content', json.dumps(result))


if __name__ == '__main__':
    unittest.main()
