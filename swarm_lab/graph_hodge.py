"""Bounded unweighted Hodge decomposition of caller-declared edge signals.

This pure instrument does not extract edges, fill cliques, read source files,
assign agent meanings, or establish communication, influence, or causality.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys


INSTRUMENT_VERSION = 'unweighted-edge-hodge-v1'
MAX_NODES = 128
MAX_EDGES = 512
MAX_FACES = 256
MAX_SIGNAL_MAGNITUDE = 1e100
MAX_INPUT_BYTES = 256 * 1024
MAX_OUTPUT_BYTES = 1024 * 1024
MAX_WORK = 50_000_000
MAX_MEMORY_BYTES = 64 * 1024**2
RCOND = 1e-12
ABSOLUTE_TOLERANCE = 1e-10
RELATIVE_TOLERANCE = 1e-9


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def _identifier(value):
    if type(value) is not str or not 1 <= len(value) <= 128 or not value.strip():
        return False
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return False
    try:
        return len(value.encode('utf-8')) <= 256
    except UnicodeEncodeError:
        return False


def _positive_bound(value, maximum, name):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(name + ' must be a bounded positive integer, not a boolean')
    return value


def _validate_input(node_ids, edges, faces):
    if type(node_ids) is not list or len(node_ids) > MAX_NODES:
        raise ValueError('node_ids must be a list of at most 128 identifiers')
    if any(not _identifier(node) for node in node_ids) or len(node_ids) != len(set(node_ids)):
        raise ValueError('node_ids must be unique bounded identifiers')
    nodes = sorted(node_ids)
    known = set(nodes)
    if type(edges) is not list or len(edges) > MAX_EDGES:
        raise ValueError('edges must be a list of at most 512 declared edges')
    edge_ids, pairs, canonical_edges = set(), set(), []
    for edge in edges:
        if (type(edge) is not dict or len(edge) != 4 or any(type(key) is not str for key in edge) or
                set(edge) != {'id', 'source', 'target', 'value'}):
            raise ValueError('Each edge requires only id/source/target/value; raw payloads are unsupported')
        if not _identifier(edge['id']) or edge['id'] in edge_ids:
            raise ValueError('Edge identifiers must be unique bounded strings')
        source, target, value = edge['source'], edge['target'], edge['value']
        if not _identifier(source) or not _identifier(target) or source not in known or target not in known:
            raise ValueError('Each edge endpoint must be a declared node')
        if source == target:
            raise ValueError('Self edges are unsupported')
        pair = tuple(sorted((source, target)))
        if pair in pairs:
            raise ValueError('One declared orientation per unordered pair is required; no silent cancellation')
        if (type(value) not in (int, float) or
                (type(value) is int and value.bit_length() > 333) or abs(value) > MAX_SIGNAL_MAGNITUDE):
            raise ValueError('Edge values must be finite int/float scalars with magnitude at most 1e100')
        if not math.isfinite(value):
            raise ValueError('Edge values must be finite int/float scalars with magnitude at most 1e100')
        edge_ids.add(edge['id'])
        pairs.add(pair)
        canonical_edges.append(dict(edge))
    canonical_edges.sort(key=lambda item: item['id'])
    canonical_faces = None
    if faces is not None:
        if type(faces) is not list or len(faces) > MAX_FACES:
            raise ValueError('faces must be None or a list of at most 256 explicit triangles')
        face_ids, supports, canonical_faces = set(), set(), []
        for face in faces:
            if (type(face) is not dict or len(face) != 2 or any(type(key) is not str for key in face) or
                    set(face) != {'id', 'nodes'}):
                raise ValueError('Each face requires only id/nodes; automatic clique filling is unsupported')
            if not _identifier(face['id']) or face['id'] in face_ids:
                raise ValueError('Face identifiers must be unique bounded strings')
            vertices = face['nodes']
            if (type(vertices) is not list or len(vertices) != 3 or
                    any(not _identifier(node) or node not in known for node in vertices) or
                    len(set(vertices)) != 3):
                raise ValueError('A face must declare three distinct known nodes in boundary-loop order')
            support = tuple(sorted(vertices))
            if support in supports:
                raise ValueError('A triangle support may be declared only once, regardless of orientation')
            if any(tuple(sorted((vertices[i], vertices[(i + 1) % 3]))) not in pairs for i in range(3)):
                raise ValueError('Every explicitly declared face boundary edge must exist')
            face_ids.add(face['id'])
            supports.add(support)
            canonical_faces.append({'id': face['id'], 'nodes': list(vertices)})
        canonical_faces.sort(key=lambda item: item['id'])
    payload = {'node_ids': nodes, 'edges': canonical_edges, 'faces': canonical_faces}
    encoded = _json_bytes(payload)
    if len(encoded) > MAX_INPUT_BYTES:
        raise ValueError('Canonical input byte bound exceeded')
    return payload, encoded


def _components(nodes, edges):
    adjacent = {node: set() for node in nodes}
    for edge in edges:
        adjacent[edge['source']].add(edge['target'])
        adjacent[edge['target']].add(edge['source'])
    unseen, components = set(nodes), []
    for node in nodes:
        if node not in unseen:
            continue
        pending, component = [node], []
        unseen.remove(node)
        while pending:
            current = pending.pop()
            component.append(current)
            for neighbor in sorted(adjacent[current], reverse=True):
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    pending.append(neighbor)
        components.append(sorted(component))
    return components, [node for node in nodes if not adjacent[node]]


def _base(payload, encoded, max_work, max_memory_bytes):
    n, m = len(payload['node_ids']), len(payload['edges'])
    k = len(payload['faces'] or [])
    components, isolates = _components(payload['node_ids'], payload['edges'])
    # Deterministic proxies, not a wall-clock or BLAS allocator guarantee.
    work = (m * n * min(m, n) + m * k * min(m, k) +
            8 * m * (n + k + 1) + n + m + k)
    memory = 64 * (m*n + m*k + n*n + k*k + n + m + k + 1)
    return {
        'kind': 'declared_edge_hodge_decomposition', 'schema_version': '1.0',
        'instrument_version': INSTRUMENT_VERSION, 'read_only': True, 'model_calls': 0,
        'available': False, 'status': 'unknown', 'reason': None,
        'input_fingerprint': {
            'sha256': hashlib.sha256(encoded).hexdigest(),
            'algorithm': 'sha256_compact_sorted_finite_json_utf8',
            'order_policy': 'sorted_node_and_edge_face_ids_preserved_orientations_and_numeric_types',
            'source_authenticated': False,
        },
        'canonical_input': payload,
        'scope': {'node_count': n, 'edge_count': m, 'declared_face_count': k,
                  'two_cell_model': ('unspecified' if payload['faces'] is None else
                                     'declared_empty' if not payload['faces'] else 'declared_triangles'),
                  'unobserved_edges_imputed': False, 'cliques_automatically_filled': False,
                  'caller_signal_semantics_verified': False},
        'conventions': {
            'inner_product': 'unweighted_Euclidean_one_coordinate_per_unordered_edge',
            'edge_gradient': 'target_potential_minus_source_potential',
            'divergence': 'negative_incidence_transpose_times_edge_signal',
            'face_boundary': 'a_to_b_plus_b_to_c_plus_c_to_a_with_declared_edge_orientation_signs',
            'face_curl_observable': 'face_boundary_transpose_times_edge_signal',
            'curl_edge_component': 'projection_onto_declared_face_boundary_column_space',
            'potential_gauge': 'zero_mean_separately_in_each_connected_component_isolates_zero',
            'boundary_coefficient_gauge': 'minimum_Euclidean_norm_coefficients_may_be_nonunique_before_gauge',
            'harmonic': 'zero_divergence_and_zero_curl_relative_to_declared_faces',
        },
        'configuration': {'dtype': 'float64', 'solver': 'numpy.linalg.lstsq', 'rcond': RCOND,
                          'input_numeric_conversion': 'float64_after_exact_canonical_fingerprint',
                          'absolute_tolerance': ABSOLUTE_TOLERANCE,
                          'relative_tolerance': RELATIVE_TOLERANCE,
                          'diagnostic_coordinates': 'signal_divided_by_maximum_absolute_input_value_or_one_for_zero'},
        'bounds': {'max_nodes': MAX_NODES, 'max_edges': MAX_EDGES, 'max_faces': MAX_FACES,
                   'max_signal_magnitude': MAX_SIGNAL_MAGNITUDE,
                   'max_input_bytes': MAX_INPUT_BYTES, 'max_output_bytes': MAX_OUTPUT_BYTES,
                   'max_work': max_work, 'estimated_work': work,
                   'max_memory_bytes': max_memory_bytes, 'estimated_workspace_bytes': memory,
                   'workspace_is_conservative_proxy_not_external_allocator_guarantee': True,
                   'sampling_or_truncation': False},
        'topology': {'connected_components': components, 'component_count': len(components),
                     'isolated_nodes': isolates, 'gradient_dimension_exact': n - len(components),
                     'circulation_dimension_exact': m - n + len(components),
                     'curl_dimension_numerical': None, 'harmonic_dimension_numerical': None},
        'backend': None, 'components': None, 'energies': None, 'diagnostics': None,
        'limitations': [
            'Declared signal and support are not authenticated observations; the host must bind sources.',
            'A gradient potential is a gauge-dependent mathematical fit, not an agent rank, role, or hierarchy.',
            'Circulation is an algebraic residual, not verified communication, rumor, influence, or causality.',
            'Curl and harmonic components depend on explicitly declared faces; absent face declarations remain unknown.',
            'A net directional count signal would cancel balanced reciprocal activity; this instrument does not construct it.',
            'Unweighted finite-complex results establish no continuum, manifold, or Laplace-Beltrami approximation.',
            'Ranks use a declared numerical threshold; results are tolerance-reproducible, not guaranteed bitwise across backends.',
            'Budget estimates bound declared dense shapes and proxies; external numerical-library memory and runtime vary.',
        ],
    }


def _unknown(result, reason, *, diagnostics=None):
    result['available'] = False
    result['status'] = 'unknown'
    result['reason'] = reason
    try:
        if diagnostics is not None:
            _json_bytes(diagnostics)
    except (ValueError, OverflowError):
        diagnostics = None
    result['diagnostics'] = diagnostics
    result['components'] = None
    result['energies'] = None
    return result


def _finite_output(result):
    try:
        return len(_json_bytes(result)) <= MAX_OUTPUT_BYTES
    except (ValueError, OverflowError):
        return False


def _energy(vector, signal_energy, scale):
    maximum = max((abs(float(value)) for value in vector), default=0.0)
    if maximum:
        unit = vector / maximum
        unit_energy = float(unit @ unit)
        normalized = (unit_energy * maximum) * maximum
        natural_maximum = maximum * scale
        natural = (unit_energy * natural_maximum) * natural_maximum
    else:
        normalized = natural = 0.0
    normalized_underflow = maximum > 0 and normalized == 0
    natural_underflow = maximum > 0 and natural == 0
    return {'normalized_squared_norm': None if normalized_underflow else normalized,
            'normalized_squared_norm_status': 'unavailable_float64_underflow' if normalized_underflow else 'available',
            'squared_norm': None if natural_underflow else natural,
            'squared_norm_status': 'unavailable_float64_underflow' if natural_underflow else 'available',
            'fraction_of_signal': normalized / signal_energy
                if signal_energy > 0 and not normalized_underflow else None}


def decompose_edge_signal(node_ids, edges, *, faces=None, max_work=10_000_000,
                          max_memory_bytes=16 * 1024**2):
    """Project an oriented scalar edge signal onto declared finite cochain spaces.

    Inputs: node_ids list[str]; edges list[{id,source,target,value}]; optional
    faces list[{id,nodes:[a,b,c]}]. Extra fields, self/parallel edges, duplicate
    supports, missing boundary edges, nonfinite/bool values, and oversized input
    are errors. Valid input that exceeds an aggregate budget or cannot pass the
    numerical checks returns available=False with no partial decomposition.

    faces=None deliberately leaves the curl/harmonic split unavailable. faces=[]
    explicitly declares the empty 2-cell complex. No input or source is mutated.
    """
    max_work = _positive_bound(max_work, MAX_WORK, 'max_work')
    max_memory_bytes = _positive_bound(max_memory_bytes, MAX_MEMORY_BYTES, 'max_memory_bytes')
    payload, encoded = _validate_input(node_ids, edges, faces)
    result = _base(payload, encoded, max_work, max_memory_bytes)
    if result['bounds']['estimated_work'] > max_work:
        return _unknown(result, 'aggregate_work_budget_exceeded')
    if result['bounds']['estimated_workspace_bytes'] > max_memory_bytes:
        return _unknown(result, 'estimated_workspace_budget_exceeded')
    try:
        import numpy as np
    except ImportError:
        return _unknown(result, 'optional_numpy_backend_unavailable')
    result['backend'] = {'numpy_version': np.__version__, 'python_version': sys.version.split()[0],
                         'dtype': 'float64', 'solver': 'numpy.linalg.lstsq',
                         'blas_lapack_build_identity': 'not_attested',
                         'bitwise_cross_backend_reproducibility_guaranteed': False}
    try:
        with np.errstate(over='raise', divide='raise', invalid='raise', under='ignore'):
            nodes, declared_edges = payload['node_ids'], payload['edges']
            declared_faces = payload['faces']
            n, m, k = len(nodes), len(declared_edges), len(declared_faces or [])
            node_index = {node: i for i, node in enumerate(nodes)}
            edge_index = {tuple(sorted((edge['source'], edge['target']))): i
                          for i, edge in enumerate(declared_edges)}
            incidence = np.zeros((m, n), dtype=np.float64)
            boundary = np.zeros((m, k), dtype=np.float64)
            for i, edge in enumerate(declared_edges):
                incidence[i, node_index[edge['source']]] = -1
                incidence[i, node_index[edge['target']]] = 1
            for j, face in enumerate(declared_faces or []):
                vertices = face['nodes']
                for a, b in zip(vertices, vertices[1:] + vertices[:1]):
                    i = edge_index[tuple(sorted((a, b)))]
                    edge = declared_edges[i]
                    boundary[i, j] = 1 if (edge['source'], edge['target']) == (a, b) else -1
            scale = max((abs(float(edge['value'])) for edge in declared_edges), default=0.0)
            zero_signal = scale == 0
            if zero_signal:
                scale = 1.0
            signal = np.array([float(edge['value']) / scale for edge in declared_edges], dtype=np.float64)
            if any(edge['value'] != 0 and signal[i] == 0 for i, edge in enumerate(declared_edges)):
                return _unknown(result, 'input_signal_normalization_underflow')
            if m and n:
                potential, _, gradient_rank, gradient_singular = np.linalg.lstsq(incidence, signal, rcond=RCOND)
            else:
                potential, gradient_rank, gradient_singular = np.zeros(n), 0, np.array([])
            for component in result['topology']['connected_components']:
                indices = [node_index[node] for node in component]
                potential[indices] -= float(np.mean(potential[indices]))
            gradient = incidence @ potential
            circulation = signal - gradient
            curl = harmonic = coefficients = None
            curl_rank, curl_singular = None, None
            if declared_faces is not None:
                if k:
                    coefficients, _, curl_rank, curl_singular = np.linalg.lstsq(boundary, circulation, rcond=RCOND)
                else:
                    coefficients, curl_rank, curl_singular = np.zeros(0), 0, np.array([])
                curl = boundary @ coefficients
                harmonic = circulation - curl

            signal_energy = float(signal @ signal)
            signal_norm = float(np.linalg.norm(signal))
            incidence_norm = float(np.linalg.norm(incidence))
            boundary_norm = float(np.linalg.norm(boundary))
            checks = []

            def check(name, residual, reference):
                residual, reference = float(abs(residual)), float(abs(reference))
                tolerance = ABSOLUTE_TOLERANCE + RELATIVE_TOLERANCE * reference
                checks.append({'name': name, 'residual': residual, 'reference_scale': reference,
                               'tolerance': tolerance,
                               'passed': math.isfinite(residual) and residual <= tolerance})

            check('reconstruction_gradient_plus_circulation', np.linalg.norm(signal-gradient-circulation), signal_norm)
            check('gradient_circulation_orthogonality', gradient @ circulation, signal_energy)
            check('circulation_divergence', np.linalg.norm(incidence.T @ circulation), incidence_norm*signal_norm)
            check('two_component_energy_identity', signal_energy-float(gradient@gradient)-float(circulation@circulation), signal_energy)
            check('component_zero_mean_potential', max((abs(float(np.mean(potential[[node_index[node] for node in c]])))
                                                     for c in result['topology']['connected_components']), default=0.0),
                  np.linalg.norm(potential))
            if declared_faces is not None:
                check('boundary_of_boundary_zero', np.linalg.norm(incidence.T @ boundary), 0)
                check('declared_face_curl_of_gradient', np.linalg.norm(boundary.T @ gradient), boundary_norm*signal_norm)
                check('curl_divergence', np.linalg.norm(incidence.T @ curl), incidence_norm*signal_norm)
                check('harmonic_divergence', np.linalg.norm(incidence.T @ harmonic), incidence_norm*signal_norm)
                check('declared_face_curl_of_harmonic', np.linalg.norm(boundary.T @ harmonic), boundary_norm*signal_norm)
                check('gradient_curl_orthogonality', gradient @ curl, signal_energy)
                check('gradient_harmonic_orthogonality', gradient @ harmonic, signal_energy)
                check('curl_harmonic_orthogonality', curl @ harmonic, signal_energy)
                check('reconstruction_gradient_plus_curl_plus_harmonic', np.linalg.norm(signal-gradient-curl-harmonic), signal_norm)
                check('three_component_energy_identity', signal_energy-float(gradient@gradient)-float(curl@curl)-float(harmonic@harmonic), signal_energy)
                check('harmonic_edge_laplacian_residual',
                      np.linalg.norm(incidence @ (incidence.T @ harmonic) + boundary @ (boundary.T @ harmonic)),
                      (incidence_norm**2 + boundary_norm**2)*signal_norm)
            expected_rank = result['topology']['gradient_dimension_exact']
            rank_check = int(gradient_rank) == expected_rank
            curl_dimension = None if curl_rank is None else int(curl_rank)
            harmonic_dimension = None if curl_rank is None else m-expected_rank-int(curl_rank)
            rank_bounds = curl_rank is None or 0 <= int(curl_rank) <= result['topology']['circulation_dimension_exact']
            diagnostics = {'signal_scale': scale, 'zero_input_signal': zero_signal,
                           'checks_in_normalized_signal_coordinates': checks,
                           'numerical_gradient_rank': int(gradient_rank),
                           'gradient_rank_matches_exact_component_count': rank_check,
                           'curl_rank_within_cycle_dimension': bool(rank_bounds),
                           'gradient_singular_values': [float(v) for v in gradient_singular],
                           'face_boundary_singular_values': None if curl_singular is None else [float(v) for v in curl_singular],
                           'passed': rank_check and bool(rank_bounds) and all(c['passed'] for c in checks)}
            if not diagnostics['passed']:
                return _unknown(result, 'numerical_validation_failed', diagnostics=diagnostics)

            def natural(vector, label):
                converted = vector * scale
                if not np.all(np.isfinite(converted)):
                    raise FloatingPointError('Nonfinite natural-unit projection')
                check('natural_unit_roundtrip_' + label,
                      np.linalg.norm(converted / scale - vector), np.linalg.norm(vector))
                return [float(v) for v in converted]

            p_values = natural(potential, 'potential')
            g_values, c_values = natural(gradient, 'gradient'), natural(circulation, 'circulation')
            curl_values = None if curl is None else natural(curl, 'curl')
            harmonic_values = None if harmonic is None else natural(harmonic, 'harmonic')
            face_values = None if coefficients is None else natural(coefficients, 'boundary_coefficients')
            face_observables = None if declared_faces is None else natural(boundary.T @ signal, 'face_curl_observable')
            diagnostics['passed'] = diagnostics['passed'] and all(c['passed'] for c in checks)
            if not diagnostics['passed']:
                return _unknown(result, 'natural_unit_conversion_validation_failed', diagnostics=diagnostics)
            edge_rows = []
            for i, edge in enumerate(declared_edges):
                edge_rows.append({'id': edge['id'], 'source': edge['source'], 'target': edge['target'],
                                  'signal': edge['value'], 'gradient': g_values[i], 'circulation': c_values[i],
                                  'curl': None if curl_values is None else curl_values[i],
                                  'harmonic': None if harmonic_values is None else harmonic_values[i]})
            result['components'] = {
                'node_potential': [{'node_id': node, 'value': p_values[i]} for i, node in enumerate(nodes)],
                'edges': edge_rows,
                'face_boundary_coefficients': None if declared_faces is None else
                    [{'face_id': face['id'], 'value': face_values[j]} for j, face in enumerate(declared_faces)],
                'declared_face_curl_observables': None if declared_faces is None else
                    [{'face_id': face['id'], 'value': face_observables[j]} for j, face in enumerate(declared_faces)],
            }
            result['energies'] = {'signal': _energy(signal, signal_energy, scale),
                                  'gradient': _energy(gradient, signal_energy, scale),
                                  'circulation': _energy(circulation, signal_energy, scale),
                                  'curl': None if curl is None else _energy(curl, signal_energy, scale),
                                  'harmonic': None if harmonic is None else _energy(harmonic, signal_energy, scale)}
            result['topology']['curl_dimension_numerical'] = curl_dimension
            result['topology']['harmonic_dimension_numerical'] = harmonic_dimension
            result['diagnostics'] = diagnostics
            result.update(available=True, status='computed', reason=None)
            if not _finite_output(result):
                result.update(available=False, status='unknown')
                return _unknown(result, 'finite_serialized_output_bound_or_numeric_range_failed')
            return result
    except (np.linalg.LinAlgError, FloatingPointError, OverflowError, MemoryError):
        return _unknown(result, 'numerical_backend_or_range_failed')
