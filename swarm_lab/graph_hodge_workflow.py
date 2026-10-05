"""Source-bound static net-reference-count decomposition on fixed graph cells."""
from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path

from . import graph_hodge as operator
from . import temporal_workflow as temporal
from .store import clean, fingerprint

WORKFLOW_VERSION = 'selected-net-reference-hodge-v1'
MAX_CELLS = 96
MAX_OUTPUT_BYTES = 16 * 1024**2


def implementation_hashes():
    return {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ('graph_hodge.py', 'graph_hodge_workflow.py', 'temporal_workflow.py')}


def _ref(obj):
    return {key: obj[key] for key in ('id', 'version', 'hash')}


def _version(value):
    if value is not None and (type(value) is not int or value < 1):
        raise ValueError('Use an exact positive temporal audit version')


def directional_count_signal(nodes, events):
    """Retain reciprocal counts and zero-valued supported unordered edges."""
    if type(nodes) is not list or type(events) is not list or len(events) > 15000:
        raise ValueError('Use bounded source-derived nodes and events')
    node_set = set(nodes)
    if len(node_set) != len(nodes): raise ValueError('Duplicate source graph node')
    counts, pins, seen = Counter(), {}, set()
    for event in events:
        if type(event) is not dict: raise ValueError('Source reference events must be objects')
        identity = event['event_id']; source, target = event['source_agent_id'], event['target_agent_id']
        if (type(identity) is not str or not identity or identity in seen or
                source not in node_set or target not in node_set or source == target):
            raise ValueError('Reference identity or declared node support differs')
        seen.add(identity); counts[source, target] += 1
        pair = tuple(sorted((source, target)))
        pins.setdefault(pair, []).append({'event_id': identity, 'event_sha256': fingerprint(event),
                                         'source': source, 'target': target})
    rows, provenance = [], []
    for number, (pair, event_pins) in enumerate(sorted(pins.items())):
        source, target = pair
        edge_id = f'edge-{number:04d}'
        forward, reverse = counts[source, target], counts[target, source]
        rows.append({'id': edge_id, 'source': source, 'target': target, 'value': forward - reverse})
        provenance.append({'edge_id': edge_id, 'source': source, 'target': target,
            'forward_reference_events': forward, 'reverse_reference_events': reverse,
            'net_reference_events': forward - reverse,
            'event_pins': sorted(event_pins, key=lambda pin: pin['event_id'])})
    return rows, provenance


def derive_edge_flow(lab, temporal_audit_id, *, version=None,
                     max_work=10_000_000, max_memory_bytes=16 * 1024**2):
    """Reproduce the parent and describe every declared cell without ranking."""
    _version(version)
    operator._positive_bound(max_work, operator.MAX_WORK, 'max_work')
    operator._positive_bound(max_memory_bytes, operator.MAX_MEMORY_BYTES, 'max_memory_bytes')
    source = lab.store.get(temporal_audit_id, version)
    if source['kind'] != 'temporal_path_audit' or fingerprint(source['payload']) != source['hash']:
        raise ValueError('Use an unchanged exact temporal path audit')
    parent = source['payload']
    selected = temporal._load_pinned(lab, parent['selected_audit_ref'], 'selected_lead_audit')
    reproduced = temporal.derive_temporal_paths(lab, selected['id'], version=selected['version'])
    if fingerprint(reproduced) != source['hash']:
        raise ValueError('Temporal parent does not reproduce from its frozen sources')
    cells = []
    for window_id, window in sorted(parent['windows'].items()):
        for variant, graph in sorted(window['variants'].items()):
            if not graph['available']:
                cells.append({'window_id':window_id,'variant':variant,
                    'source_scope':window['scope'],'source_graph_sha256':fingerprint(graph),
                    'source_reference_event_count':None,'edge_source_pins':None,'preflight':None,
                    'decomposition':None,'source_unavailable_reason':graph.get('reason','source_graph_unavailable'),
                    '_nodes':None,'_edges':None})
                continue
            nodes = graph['node_ids']
            if nodes != window['node_universe']['ids']:
                raise ValueError('Variant changed its declared within-window node universe')
            edges, edge_pins = directional_count_signal(nodes, graph['events'])
            # Public bounded refusal supplies validated input shape and deterministic
            # estimates before any numerical backend is reached. No face is declared.
            preflight = operator.decompose_edge_signal(nodes, edges, faces=None,
                                                        max_work=1, max_memory_bytes=1)
            cells.append({'window_id': window_id, 'variant': variant,
                'source_scope': window['scope'], 'source_graph_sha256': fingerprint(graph),
                'source_reference_event_count': len(graph['events']), 'edge_source_pins': edge_pins,
                'preflight': {key: preflight[key] for key in ('input_fingerprint', 'bounds', 'scope')},
                'decomposition': None, '_nodes': nodes, '_edges': edges})
    if not 1 <= len(cells) <= MAX_CELLS: raise ValueError('Source graph cell bound exceeded')
    total_work = sum(cell['preflight']['bounds']['estimated_work'] for cell in cells if cell['preflight'])
    peak_memory = max((cell['preflight']['bounds']['estimated_workspace_bytes'] for cell in cells if cell['preflight']),default=0)
    reasons = []
    if total_work > max_work: reasons.append('aggregate_work_budget_exceeded')
    if peak_memory > max_memory_bytes: reasons.append('peak_workspace_budget_exceeded')
    for cell in cells:
        nodes, edges = cell.pop('_nodes'), cell.pop('_edges')
        if nodes is not None and not reasons:
            cell['decomposition'] = operator.decompose_edge_signal(nodes, edges, faces=None,
                max_work=max_work, max_memory_bytes=max_memory_bytes)
    available = sum(bool(cell['decomposition'] and cell['decomposition']['available']) for cell in cells)
    payload = {'name': 'Static net-reference-count gradient and circulation',
        'workflow_version': WORKFLOW_VERSION, 'temporal_audit_ref': _ref(source),
        'source_refs': {**parent['source_refs'], 'temporal_audit': _ref(source)},
        'configuration': {'max_work': max_work, 'max_memory_bytes': max_memory_bytes,
            'selection': 'All original parent windows and variants; no ranking or rematching.',
            'signal': 'Lexical orientation; forward reference-event count minus reverse count; supported zero edges retained.',
            'faces': None, 'inner_product': 'unweighted Euclidean'},
        'implementation_hashes': implementation_hashes(), 'source_audit_replay_passed': True,
        'bounds': {'cells': len(cells), 'max_cells': MAX_CELLS, 'estimated_total_work': total_work,
            'max_work': max_work, 'estimated_peak_workspace_bytes': peak_memory,
            'max_memory_bytes': max_memory_bytes, 'memory_scope': 'Sequential operator workspace proxy; parent/input/output and external allocator memory are additional.'},
        'source_hash_policy':'Source event and graph SHA256 use Store.fingerprint sorted finite JSON with default separators; operator input SHA256 uses compact sorted finite JSON. Their purposes differ.',
        'source_replay_scope':'Exact normalized registry rows and source/code pins are regenerated; raw upstream chat/event objects are not reread. Parent regeneration work is additional to the Hodge proxy budget.',
        'status': 'unknown_budget_scope' if reasons else 'all_cells_available' if available == len(cells) else 'some_cells_unavailable',
        'unknown_reasons': reasons, 'available_cells': available, 'cells': cells,
        'model_calls': 0, 'raw_content_persisted': False, 'status_promotion': False,
        'scope': 'Same selected named-reference events under a declared static net-count signal. '
                 'Reciprocal counts cancel; time order is discarded. No 2-cells are declared. '
                 'No verified traffic, address, delivery, reading, rumor, hierarchy, network effect, '
                 'continuum manifold, novelty or causal attestation; no discovery or library status change.'}
    if clean(payload) != payload: raise ValueError('Do not persist credential-shaped decomposition metadata')
    if len(operator._json_bytes(payload)) > MAX_OUTPUT_BYTES:
        raise ValueError('Source-bound decomposition exceeds output byte bound')
    return payload


def audit_edge_flow(lab, temporal_audit_id, **kwargs):
    return lab.store.put('graph_hodge_audit', derive_edge_flow(lab, temporal_audit_id, **kwargs))


def replay_edge_flow(lab, audit_id, *, version=None):
    _version(version)
    source = lab.store.get(audit_id, version)
    if source['kind'] != 'graph_hodge_audit' or fingerprint(source['payload']) != source['hash']:
        raise ValueError('Use an unchanged exact edge-flow audit')
    payload = source['payload']
    proof = {'audit_ref': _ref(source), 'result_kind': 'graph_hodge_audit', 'passed': False,
        'model_calls': 0, 'source_replay_attempted': False, 'source_replay_completed': False,
        'scope': 'Fresh parent/source regeneration and same-backend whole-payload decomposition replay. '
                 'A numerical-backend change can break exact equality; no social or causal attestation.'}
    if payload.get('implementation_hashes') != implementation_hashes():
        proof['reason'] = 'implementation_hash_mismatch'
    else:
        proof['source_replay_attempted'] = True
        try:
            parent = temporal._load_pinned(lab, payload['temporal_audit_ref'], 'temporal_path_audit')
            config = payload['configuration']
            regenerated = derive_edge_flow(lab, parent['id'], version=parent['version'],
                max_work=config['max_work'], max_memory_bytes=config['max_memory_bytes'])
        except (ValueError, OSError, KeyError, TypeError, UnicodeError) as exc:
            proof.update(reason='source_or_operator_unavailable_or_invalid', error_type=type(exc).__name__)
        else:
            passed = fingerprint(regenerated) == source['hash']
            proof.update(passed=passed, source_replay_completed=True,
                         reason='reproduced' if passed else 'source_backend_or_derivation_mismatch')
    return lab.store.put('verification', proof)
