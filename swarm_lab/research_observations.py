"""Bounded recorded observations for prospective research, without replay.

Registry bodies, current fixed producer files and stored proof bindings are
checked locally. These checks neither reread an index/raw source nor reproduce
an operator. Body limits bound accepted JSON, not Store decoding allocations.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
import re

CONTEXT_VERSION = 'recorded-research-observations-v1'
MAX_JSON_DEPTH = 64
# Declared operator absolute+relative tolerance at unit reference scale.
# This is a local range check, not a rerun of numerical residual diagnostics.
FRACTION_BOUND_TOLERANCE = 1e-10 + 1e-9
_SELECTED = ('dataset.py', 'discovery.py', 'network.py', 'graph_discovery.py',
             'mention_sensitivity.py', 'name_eligibility_sensitivity.py',
             'mention_graph_sensitivity.py', 'selected_lead_sensitivity.py')
_TEMPORAL = ('temporal_network.py', 'dataset.py', 'graph_discovery.py', 'network.py',
             'mention_sensitivity.py', 'name_eligibility_sensitivity.py', 'mention_graph_sensitivity.py')
_ACTOR = (*_SELECTED, 'event_source_index.py', 'indexed_event_audit.py', 'indexed_event_workflow.py',
          'source_scanner.py', 'temporal_workflow.py', 'source_links.py', 'source_workflow.py',
          'actor_event_queries.py', 'actor_event_workflow.py')
_WAIT = (*_ACTOR, 'wait_marker_alignment.py', 'wait_marker_workflow.py')
_HODGE = ('graph_hodge.py', 'graph_hodge_workflow.py', 'temporal_workflow.py')
_FILES = tuple(sorted(set((*_SELECTED, *_TEMPORAL, *_ACTOR, *_WAIT, *_HODGE))))
_KINDS = {'actor_events': 'actor_event_audit', 'wait_markers': 'wait_marker_alignment_audit',
          'edge_algebra': 'graph_hodge_audit'}
_VERSIONS = {'actor_events': 'selected-actor-event-workflow-v1',
             'wait_markers': 'selected-wait-marker-workflow-v1',
             'edge_algebra': 'selected-net-reference-hodge-v1'}
_ACTIONS = ('WAIT', 'PAUSE', 'START_USING_COMPUTER', 'STOP_USING_COMPUTER')
_VARIANTS = ('baseline_exact', 'explicit_short_expanded_exact', 'unicode_baseline', 'unicode_expanded')
_STATUSES = ('candidate_observed', 'candidate_observed_boundary_censored',
             'no_indexed_candidate_boundary_censored', 'no_indexed_candidate_in_complete_recorded_band')
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,199}\Z')
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_SCOPE = ('Recorded measurements only. Local registry/body, fixed current producer-byte and stored-proof gates '
          'are distinct from fresh source attestation, which is false. No index/raw reread or operator rerun. '
          'No pooling, reranking, semantic accuracy, inactivity, receipt, exposure, novelty, causality or status promotion.')


class _Budget(ValueError):
    pass


def _bytes(value, *, compact=False):
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > MAX_JSON_DEPTH:
            raise _Budget('accepted_json_depth_exceeded')
        if type(item) is dict:
            pending.extend((child, depth + 1) for child in item.values())
        elif type(item) in (list, tuple):
            pending.extend((child, depth + 1) for child in item)
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      **({'separators': (',', ':')} if compact else {})).encode('utf-8')


def _ref(value):
    if (type(value) is not dict or set(value) != {'id', 'version', 'hash'} or
            type(value['id']) is not str or not _ID.fullmatch(value['id']) or
            type(value['version']) is not int or not 1 <= value['version'] <= 10**9 or
            type(value['hash']) is not str or not _SHA.fullmatch(value['hash'])):
        raise ValueError('invalid_exact_reference')
    return value


def _pin(obj):
    return {key: obj[key] for key in ('id', 'version', 'hash')}


def _same(ref, expected):
    return _bytes(_ref(ref)) == _bytes(_ref(expected))


def _looks_relevant(ref, expected):
    """Wrong hashes/types at the same parent are relevant failures, not fallbacks."""
    return (type(ref) is dict and ref.get('id') == expected['id'] and
            (type(ref.get('version')) is not int or ref.get('version') == expected['version']))


def _current_code():
    # Filenames are host constants, never caller/payload paths.
    directory = Path(__file__).resolve().parent
    return {name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in _FILES}


def _code_matches(pins, names, current, structured=False):
    if type(pins) is not dict or set(pins) != set(names):
        return False
    if structured:
        if any(type(pins[name]) is not dict or 'sha256' not in pins[name] or
               not set(pins[name]) <= {'sha256', 'purpose', 'hash_purpose'} for name in names):
            return False
        pins = {name: pins[name]['sha256'] for name in names}
    return all(type(pins[name]) is str and pins[name] == current[name] for name in names)


def _count(value):
    if type(value) is not int or not 0 <= value <= 10**9:
        raise ValueError('invalid_recorded_count')
    return value


def _scope(value):
    row = {key: value[key] for key in ('id', 'room_id', 'start', 'end_exclusive')}
    if any(type(v) is not str or not 1 <= len(v) <= 200 for v in row.values()):
        raise ValueError('invalid_original_window')
    if _utc(row['start']) >= _utc(row['end_exclusive']):
        raise ValueError('invalid_original_window')
    return row


def _utc(value):
    if type(value) is not str or len(value) > 80:
        raise ValueError('invalid_recorded_timestamp')
    t = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if t.tzinfo is None:
        raise ValueError('unknown_recorded_timezone')
    return t.astimezone(dt.timezone.utc)


def _counts(row):
    total = _count(row['records'])
    actions = {key: _count(row['action_counts'][key]) for key in _ACTIONS}
    rooms = {key: _count(row['room_status_counts'][key]) for key in ('known', 'missing', 'invalid')}
    if sum(actions.values()) != total or sum(rooms.values()) != total:
        raise ValueError('recorded_counts_do_not_reconcile')
    return {'records': total, 'action_counts': actions, 'room_status_counts': rooms}


def _complete(coverage):
    return (coverage['build_scan']['complete_scan'] is True and
            coverage['build_scan']['invalid_timestamp_rows'] == 0 and
            type(coverage['build_scan']['invalid_timestamp_rows']) is int and
            coverage['query_complete'] is True and coverage['truncated'] is False and
            coverage['candidate_validation_complete'] is True and
            _count(coverage['candidate_rows']) == _count(coverage['candidate_rows_validated']) and
            _count(coverage['returned_rows']) == _count(coverage['matched_rows']))


class _Reader:
    def __init__(self, store, limits):
        self.store, self.limits, self.used, self.cache = store, limits, 0, {}

    def accept(self, obj):
        key = (obj['id'], obj['version'], obj['hash'])
        _ref(_pin(obj))
        if type(obj.get('payload')) is not dict or type(obj.get('kind')) is not str:
            raise ValueError('invalid_registry_record_shape')
        body = _bytes(obj['payload'])
        if len(body) > self.limits['max_registry_body_bytes'] or key not in self.cache and self.used + len(body) > self.limits['max_total_registry_bytes']:
            raise _Budget('accepted_registry_json_budget_exceeded')
        if hashlib.sha256(body).hexdigest() != obj['hash']:
            raise ValueError('local_registry_body_hash_mismatch')
        if key in self.cache:
            return self.cache[key]
        self.used += len(body); self.cache[key] = obj
        return obj


    def load(self, ref, kind):
        _ref(ref)
        obj = self.accept(self.store.get(ref['id'], ref['version']))
        if obj['kind'] != kind or not _same(_pin(obj), ref):
            raise ValueError('local_registry_source_binding_mismatch')
        return obj


def _newest(rows, limit):
    if type(rows) is not list or len(rows) > limit:
        raise ValueError('bounded_registry_listing_contract_mismatch')
    return sorted(rows, key=lambda row: (_utc(row['created']), _ref(_pin(row))['id'], row['version']), reverse=True)


def _author_partition(actor, dataset, scopes):
    messages = {row['id']: row for row in dataset['messages']}
    if len(messages) != len(dataset['messages']) or len(messages) > 15000:
        raise ValueError('invalid_bounded_source_messages')
    output = {}
    all_scopes = {row['id']: _scope(row) for row in actor['original_windows']}
    if len(all_scopes) != len(actor['original_windows']):
        raise ValueError('duplicate_original_author_window')
    for wid, scope in scopes.items():
        if _bytes(all_scopes[wid]) != _bytes(scope):
            raise ValueError('actor_original_window_mismatch')
    pins = actor['author_source_pins']
    if type(pins) is not list or len(pins) > 15000:
        raise ValueError('invalid_author_partition')
    for pin in pins:
        message = messages[pin['message_id']]
        if (pin['message_id'] in output or message['speaker_type'] != 'agent' or
                pin['agent_id'] != message['agent_id'] or pin['speaker_id'] != message['speaker_id'] or
                hashlib.sha256(_bytes(message, compact=True)).hexdigest() != pin['normalized_record_sha256']):
            raise ValueError('author_partition_source_mismatch')
        stamp = _utc(message['created_at'])
        memberships = sorted(wid for wid, window in all_scopes.items()
            if message['room_id'] == window['room_id'] and _utc(window['start']) <= stamp < _utc(window['end_exclusive']))
        if pin['original_window_ids'] != memberships or not memberships:
            raise ValueError('author_partition_window_mismatch')
        output[pin['message_id']] = {'windows': memberships, 'hash': pin['normalized_record_sha256']}
    intervals = {wid: (_utc(row['start']), _utc(row['end_exclusive'])) for wid, row in all_scopes.items()}
    selected = []
    for message in messages.values():
        stamp = _utc(message['created_at'])
        if any(message['room_id'] == row['room_id'] and intervals[wid][0] <= stamp < intervals[wid][1]
               for wid, row in all_scopes.items()):
            if type(message['speaker_type']) is not str or len(message['speaker_type']) > 64:
                raise ValueError('invalid_selected_source_speaker_type')
            selected.append(message)
    agents = [message for message in selected if message['speaker_type'] == 'agent']
    scope = actor['source_scope']
    expected_speakers = dict(sorted(Counter(message['speaker_type'] for message in selected).items()))
    recorded_speakers = {name: _count(count) for name, count in scope['speaker_type_counts'].items()}
    if (_count(scope['selected_chat_records']) != len(selected) or
            _count(scope['agent_authored_records']) != len(agents) or
            _count(scope['selected_actor_count']) != len({message['agent_id'] for message in agents}) or
            recorded_speakers != expected_speakers or set(output) != {message['id'] for message in agents}):
        raise ValueError('actor_source_count_partition_mismatch')
    return output


def _actor_excerpt(p, scopes):
    packet, summary = p['actor_event_packet'], p['actor_event_summary']
    if (not _complete(packet['coverage']) or not _complete(summary['coverage']) or
            set(p['query']['action_types']) != set(_ACTIONS) or
            _bytes(p['query']) != _bytes(packet['query']) or _bytes(p['query']) != _bytes(summary['query']) or
            hashlib.sha256(_bytes(packet)).hexdigest() != p['query_packet_hash'] or
            hashlib.sha256(_bytes(packet, compact=True)).hexdigest() != summary['input_packet_sha256']):
        raise ValueError('actor_recorded_coverage_or_action_scope_incomplete')
    return {'measurement': 'Stored actor/time logged choices and boundaries; no room predicate.',
            'by_original_window': {wid: _counts(summary['by_window'][wid]) for wid in scopes},
            'source_message_counts': {key: _count(p['source_scope'][key]) for key in
                                     ('selected_chat_records', 'agent_authored_records', 'selected_actor_count')},
            'coverage_recorded': {'complete_scan': True, 'query_complete': True, 'truncated': False},
            'room_relationship': 'Event rooms remain observed/missing; original chat rooms are not assigned to events.',
            'clock_scope': 'Recorded event export-clock convention, not synchronized elapsed time.',
            'interpretation': 'WAIT/PAUSE are logged choices, PAUSE seconds are requested duration; START/STOP are boundaries, not verified leases or inactivity. Window counts can reuse events.'}


def _wait_excerpt(p, partition, scopes):
    a = p['alignment']
    if (a['status'] != 'computed_recorded_temporal_association' or a['summary'] is None or
            not _complete(a['coverage']) or a['configuration']['horizons_seconds'] != [30, 60, 300] or
            type(a['alignment_rows']) is not list or len(a['alignment_rows']) > 15000 or
            _bytes(a['source_refs']) != _bytes(p['source_refs'])):
        raise ValueError('wait_recorded_alignment_unavailable')
    pins = {row['message_id']: row for row in a['message_pins']}
    if len(pins) != len(a['message_pins']) or len(pins) > 15000:
        raise ValueError('invalid_wait_message_pins')
    windows = {wid: {group: {'messages': 0, 'by_horizon_seconds': {str(h):
               {'messages_with_candidate': 0, 'status_counts': {}} for h in (30, 60, 300)}}
               for group in ('marker', 'nonmarker_control')} for wid in scopes}
    seen = set()
    for row in a['alignment_rows']:
        identity = row['message_id']; pin = pins[identity]; source = partition[identity]
        if (identity in seen or row['analysis_group'] not in ('marker', 'nonmarker_control') or
                pin['analysis_group'] != row['analysis_group'] or row['scope_unknown_reason'] is not None or
                pin['normalized_record_sha256'] != source['hash']):
            raise ValueError('wait_message_partition_mismatch')
        seen.add(identity)
        for wid in set(source['windows']) & set(scopes):
            group = windows[wid][row['analysis_group']]; group['messages'] += 1
            for h in (30, 60, 300):
                saved = row['by_horizon_seconds'][str(h)]; status = saved['status']
                if (status not in _STATUSES or type(saved['candidate_event_ids']) is not list or
                        any(type(identity) is not str or not _ID.fullmatch(identity) for identity in saved['candidate_event_ids']) or
                        any(type(saved[key]) is not bool for key in ('before_support_complete', 'after_support_complete')) or
                        sum(_count(saved[key]) for key in ('before', 'tie', 'after')) != len(saved['candidate_event_ids']) or
                        status.startswith('candidate_observed') != bool(saved['candidate_event_ids'])):
                    raise ValueError('unknown_wait_recorded_status')
                candidate = bool(saved['candidate_event_ids'])
                complete = saved['before_support_complete'] and saved['after_support_complete']
                expected = ('candidate_observed' if complete else 'candidate_observed_boundary_censored') if candidate else ('no_indexed_candidate_in_complete_recorded_band' if complete else 'no_indexed_candidate_boundary_censored')
                if status != expected:
                    raise ValueError('wait_recorded_censor_status_mismatch')
                bucket = group['by_horizon_seconds'][str(h)]
                bucket['messages_with_candidate'] += bool(saved['candidate_event_ids'])
                bucket['status_counts'][status] = bucket['status_counts'].get(status, 0) + 1
    if seen != set(pins):
        raise ValueError('wait_alignment_pin_coverage_mismatch')
    return {'measurement': 'Literal marker messages and fixed deterministic nonmarker comparisons; semantic meaning unadjudicated.',
            'by_original_author_window': windows,
            'candidate_scope': 'Partition of saved rows by original chat-author window membership. Candidate and censor flags retain the original union-of-query-window scope; they are not recomputed for this excerpt.',
            'fixed_control_selection': 'Original source-ID hash selection, not resampled per window; neither probability sample nor negative semantic ground truth.',
            'horizons_seconds': [30, 60, 300],
            'clock_scope': 'Raw chat clock policies unavailable; signed UTC-coordinate proximity is not synchronized physical delay.',
            'room_relationship': 'Same actor and shared query time window; missing event rooms stay unassigned.',
            'interpretation': 'Before, tie and after all count; censored bands do not establish negatives outside the source scope. Nested horizons, messages and source windows can reuse events; no accuracy or causal effect.'}


def _energy(value):
    if value is None:
        return None
    output = {key: value[key] for key in ('squared_norm', 'fraction_of_signal')}
    for key, number in output.items():
        if number is not None and (type(number) not in (int, float) or not math.isfinite(number)):
            raise ValueError('invalid_recorded_energy')
        if number is not None and (number < 0 if key == 'squared_norm' else
                                   not -FRACTION_BOUND_TOLERANCE <= number <= 1 + FRACTION_BOUND_TOLERANCE):
            raise ValueError('recorded_energy_or_fraction_outside_local_bounds')
    return output


def _hodge_excerpt(p, temporal, scopes):
    if p['configuration']['faces'] is not None or p['status'] != 'all_cells_available' or p['unknown_reasons']:
        raise ValueError('edge_algebra_recorded_scope_unavailable')
    cells = p['cells']
    if type(cells) is not list or len(cells) > 96 or _count(p['available_cells']) != len(cells):
        raise ValueError('invalid_edge_algebra_cell_coverage')
    windows = {wid: {} for wid in scopes}; seen = set()
    for cell in cells:
        wid, variant = cell['window_id'], cell['variant']
        if (wid, variant) in seen:
            raise ValueError('duplicate_edge_algebra_cell')
        seen.add((wid, variant))
        if wid not in scopes:
            continue
        source = temporal['windows'][wid]['variants'][variant]; d = cell['decomposition']
        if (variant not in _VARIANTS or _bytes(_scope(cell['source_scope'])) != _bytes(scopes[wid]) or
                hashlib.sha256(_bytes(source)).hexdigest() != cell['source_graph_sha256'] or
                d is None or d['available'] is not True or d['diagnostics']['passed'] is not True or
                d['canonical_input']['faces'] is not None or d['scope']['two_cell_model'] != 'unspecified' or
                d['energies']['curl'] is not None or d['energies']['harmonic'] is not None):
            raise ValueError('edge_algebra_source_or_face_scope_mismatch')
        edges = cell['edge_source_pins']
        windows[wid][variant] = {'node_count': _count(d['scope']['node_count']),
            'supported_edges': _count(d['scope']['edge_count']),
            'balanced_supported_edges': sum(_count(edge['forward_reference_events']) == _count(edge['reverse_reference_events']) for edge in edges),
            'source_reference_events': _count(cell['source_reference_event_count']),
            'energies': {key: _energy(d['energies'][key]) for key in ('signal', 'gradient', 'circulation')},
            'curl': None, 'harmonic': None, 'source_graph_sha256': cell['source_graph_sha256']}
    if any(set(variants) != set(_VARIANTS) for variants in windows.values()):
        raise ValueError('edge_algebra_original_cell_missing')
    if seen != {(wid, variant) for wid, window in temporal['windows'].items() for variant in window['variants']} or _count(p['bounds']['cells']) != len(cells):
        raise ValueError('edge_algebra_complete_parent_cell_coverage_mismatch')
    return {'measurement': 'Static forward-minus-reverse named-reference counts; balanced supported edges retained.',
            'by_original_window': windows, 'faces': None,
            'fraction_bound_tolerance': FRACTION_BOUND_TOLERANCE,
            'fraction_bound_scope': 'Local dimensionless range check using operator absolute+relative tolerance at unit reference scale; original values are retained without clipping. No numerical replay.',
            'interpretation': 'Unweighted algebraic gradient/circulation. Time order discarded; energy quadratic in net counts, fractions not message proportions. Curl/harmonic unknown without faces. Node universes differ by window; no rankings, hierarchy, physical traffic, rumor or continuum-LBO claim.'}


def recorded_observation_context(lab_or_store, source_refs, comparison, *, max_objects_per_kind=8,
        max_proof_objects=64, max_registry_body_bytes=4*1024**2,
        max_total_registry_bytes=16*1024**2, max_output_bytes=24000):
    """Return recorded summaries of two exact original windows or explicit unknowns.

    Store must expose get(id, version) and list(kind, limit=...). Latest object
    IDs only are searched; historical versions are loaded solely by exact pins.
    No fallback past a newest relevant malformed/stale observation or proof.
    """
    observations = {key: {'available': False, 'reason': 'not_examined', 'summary': None,
                    'ref': None, 'stored_proof_ref': None, 'gates': {}} for key in _KINDS}
    result = {'available': False, 'context_version': CONTEXT_VERSION, 'reason': None,
              'source_refs': None, 'registered_comparison': None, 'original_windows': None,
              'observations': observations, 'search_scope': {}, 'bounds': {},
              'fresh_source_attestation': False, 'raw_or_index_reread': False,
              'operator_rerun': False, 'model_calls': 0, 'database_writes': 0, 'scope': _SCOPE}
    result['base_context_gates'] = {'local_registry_body_hashes_verified': False,
                                   'current_producer_byte_pins_match': False,
                                   'exact_original_comparison_verified': False}
    try:
        limits = {'max_objects_per_kind': max_objects_per_kind, 'max_proof_objects': max_proof_objects,
                  'max_registry_body_bytes': max_registry_body_bytes, 'max_total_registry_bytes': max_total_registry_bytes,
                  'max_output_bytes': max_output_bytes}
        for key, low, high in (('max_objects_per_kind', 1, 32), ('max_proof_objects', 1, 200),
                              ('max_registry_body_bytes', 256, 8*1024**2), ('max_total_registry_bytes', 256, 64*1024**2),
                              ('max_output_bytes', 2048, 32000)):
            if type(limits[key]) is not int or not low <= limits[key] <= high:
                raise ValueError('invalid_context_bound')
        result['bounds'] = {**limits, 'max_json_depth': MAX_JSON_DEPTH, 'scope': 'Accepted/retained serialized JSON ceilings; Store.get/list decoding allocations are not bounded by this helper.'}
        store = getattr(lab_or_store, 'store', lab_or_store); reader = _Reader(store, limits)
        if type(source_refs) is not dict or set(source_refs) != {'dataset', 'discovery', 'selected_audit', 'temporal_audit'}:
            raise ValueError('four_exact_context_source_references_required')
        sources = {name: reader.load(ref, {'selected_audit': 'selected_lead_audit', 'temporal_audit': 'temporal_path_audit'}.get(name, name))
                   for name, ref in source_refs.items()}
        dataset, discovery, selected, temporal = (sources[name]['payload'] for name in ('dataset', 'discovery', 'selected_audit', 'temporal_audit'))
        for name in ('dataset', 'discovery'):
            if not _same(selected['source_refs'][name], source_refs[name]) or not _same(temporal['source_refs'][name], source_refs[name]):
                raise ValueError('base_context_source_mismatch')
        if (discovery['dataset_id'] != source_refs['dataset']['id'] or not _same(discovery['dataset_ref'], source_refs['dataset']) or
                not _same(temporal['selected_audit_ref'], source_refs['selected_audit']) or
                not _same(temporal['source_refs']['selected_audit'], source_refs['selected_audit'])):
            raise ValueError('base_context_parent_mismatch')
        current = _current_code()
        if not _code_matches(selected['code_hashes'], _SELECTED, current, True) or not _code_matches(temporal['code_hashes'], _TEMPORAL, current, True):
            raise ValueError('base_context_current_code_mismatch')
        if type(comparison) is not dict or set(comparison) != {'id', 'feature', 'window_id', 'comparison_window_id'}:
            raise ValueError('exact_original_comparison_required')
        registered = next(row['registered'] for row in selected['per_lead'] if row['lead_id'] == comparison['id'])
        original = next(row for row in temporal['original_comparisons'] if row['id'] == comparison['id'])
        if _bytes(comparison) != _bytes({key: registered[key] for key in comparison}) or _bytes(comparison) != _bytes(original):
            raise ValueError('original_comparison_mismatch')
        scopes = {wid: _scope(temporal['windows'][wid]['scope']) for wid in dict.fromkeys((comparison['window_id'], comparison['comparison_window_id']))}
        if len(temporal['windows']) > 24:
            raise ValueError('original_window_count_bound_exceeded')
        all_scopes = {wid: _scope(window['scope']) for wid, window in temporal['windows'].items()}
        for wid, scope in scopes.items():
            if _bytes(scope) != _bytes(_scope(selected['window_measurements'][wid]['original_window'])):
                raise ValueError('original_window_source_mismatch')
        result.update(source_refs=copy.deepcopy(source_refs), registered_comparison=copy.deepcopy(comparison), original_windows=scopes)
        result['base_context_gates'] = {key: True for key in result['base_context_gates']}
        proof_rows = _newest(store.list('verification', limit=max_proof_objects), max_proof_objects)
        result['search_scope']['verification'] = {'newest_object_ids_returned': len(proof_rows), 'limit': max_proof_objects,
            'possibly_truncated': len(proof_rows) == max_proof_objects,
            'interpretation': 'Newest latest versions only; no proof found here is scoped absence, not global absence. History is not searched.'}
        actor_obj, partition = None, None
        for name, kind in _KINDS.items():
            entry = observations[name]; rows = _newest(store.list(kind, limit=max_objects_per_kind), max_objects_per_kind)
            result['search_scope'][kind] = {'newest_object_ids_returned': len(rows), 'limit': max_objects_per_kind,
                                          'possibly_truncated': len(rows) == max_objects_per_kind}
            anchor = source_refs['temporal_audit'] if name == 'edge_algebra' else source_refs['selected_audit']
            def relevant(obj):
                p = obj.get('payload', {})
                if type(p) is not dict:
                    return False
                refs = p.get('source_refs')
                linked = p.get('temporal_audit_ref') if name == 'edge_algebra' else p.get('selected_audit_ref') if name == 'actor_events' else refs.get('selected_audit') if type(refs) is dict else None
                return _looks_relevant(linked, anchor) or name == 'wait_markers' and actor_obj is not None and _looks_relevant(p.get('actor_audit_ref'), _pin(actor_obj))
            candidate = next((row for row in rows if relevant(row)), None)
            if candidate is None:
                entry['reason'] = 'no_matching_observation_in_bounded_newest_scope'; continue
            try:
                obj = reader.accept(candidate); p = obj['payload']; entry['ref'] = _pin(obj)
                gates = entry['gates'] = {'local_registry_body_hash_verified': True, 'exact_source_parent_binding': False,
                    'current_producer_byte_pins_match': False, 'stored_proof_binding_verified': False,
                    'stored_proof_passed': False, 'fresh_source_attestation': False}
                if obj['kind'] != kind or p['workflow_version'] != _VERSIONS[name] or p['model_calls'] != 0 or type(p['model_calls']) is not int or p['raw_content_persisted'] is not False or p['status_promotion'] is not False or p['source_audit_replay_passed'] is not True:
                    raise ValueError('observation_workflow_shape_mismatch')
                for key in ('dataset', 'discovery', 'selected_audit'):
                    if not _same(p['source_refs'][key], source_refs[key]):
                        raise ValueError('observation_exact_source_mismatch')
                if name == 'edge_algebra':
                    if not _same(p['temporal_audit_ref'], anchor) or not _same(p['source_refs']['temporal_audit'], anchor):
                        raise ValueError('observation_temporal_parent_mismatch')
                elif name == 'actor_events':
                    if not _same(p['selected_audit_ref'], anchor):
                        raise ValueError('observation_selected_parent_mismatch')
                    reader.load(p['index_ref'], 'event_source_index')  # Body only; never open its artifact path.
                else:
                    if actor_obj is None or not _same(p['actor_audit_ref'], _pin(actor_obj)) or not _same(p['source_refs']['actor_audit'], _pin(actor_obj)) or not _same(p['source_refs']['index'], actor_obj['payload']['index_ref']):
                        raise ValueError('newest_wait_actor_parent_unavailable_or_mismatched')
                gates['exact_source_parent_binding'] = True
                if not _code_matches(p['implementation_hashes'], {'actor_events': _ACTOR, 'wait_markers': _WAIT, 'edge_algebra': _HODGE}[name], current):
                    raise ValueError('observation_current_code_mismatch')
                gates['current_producer_byte_pins_match'] = True
                proof_key = 'alignment_ref' if name == 'wait_markers' else 'audit_ref'
                proof_row = next((row for row in proof_rows if type(row.get('payload')) is dict and any(_looks_relevant(row['payload'].get(key), _pin(obj)) for key in ('audit_ref', 'alignment_ref', 'reference_ref'))), None)
                if proof_row is None:
                    raise ValueError('no_bound_proof_in_bounded_newest_scope')
                proof = reader.accept(proof_row); pp = proof['payload']; entry['stored_proof_ref'] = _pin(proof)
                if proof['kind'] != 'verification' or pp.get('result_kind') != kind or not _same(pp[proof_key], _pin(obj)):
                    raise ValueError('stored_proof_binding_mismatch')
                gates['stored_proof_binding_verified'] = True
                completion = ('index_artifact_reread_attempted', 'index_artifact_reread_completed') if name == 'actor_events' else ('source_replay_attempted', 'source_replay_completed')
                if pp['passed'] is not True or type(pp['model_calls']) is not int or pp['model_calls'] != 0 or any(pp[key] is not True for key in completion):
                    raise ValueError('newest_bound_stored_proof_failed_or_incomplete')
                if name != 'edge_algebra' and (pp.get('full_event_source_reread') is not False or name == 'wait_markers' and pp.get('index_artifact_reread_completed') is not True):
                    raise ValueError('stored_proof_scope_mismatch')
                gates['stored_proof_passed'] = True
                if name == 'actor_events':
                    if {row['id'] for row in p['original_windows']} != set(all_scopes):
                        raise ValueError('actor_complete_original_window_coverage_mismatch')
                    summary = _actor_excerpt(p, scopes); partition = _author_partition(p, dataset, all_scopes); actor_obj = obj
                elif name == 'wait_markers': summary = _wait_excerpt(p, partition, scopes)
                else: summary = _hodge_excerpt(p, temporal, scopes)
                entry.update(available=True, reason=None, summary=summary)
            except _Budget:
                raise
            except (ValueError, KeyError, TypeError, OSError, StopIteration, OverflowError, RecursionError) as exc:
                reason = str(exc) if type(exc) is ValueError and re.fullmatch(r'[a-z_]+', str(exc)) else 'newest_matching_record_unavailable_or_invalid'
                entry.update(available=False, reason=reason, summary=None)
        if _current_code() != current:
            raise ValueError('current_producer_files_changed_during_context_read')
        result['available'] = any(entry['available'] for entry in observations.values())
        result['reason'] = None if result['available'] else 'no_available_recorded_observation_in_bounded_scope'
        result['bounds']['accepted_registry_json_bytes'] = reader.used
        if len(_bytes(result)) > max_output_bytes:
            raise _Budget('retained_context_output_budget_exceeded')
    except (ValueError, KeyError, TypeError, OSError, StopIteration, OverflowError, RecursionError) as exc:
        result.update(available=False, reason='context_unavailable_' + ('budget' if isinstance(exc, _Budget) else 'source_or_contract'), source_refs=None, registered_comparison=None, original_windows=None)
        for entry in observations.values():
            entry.update(available=False, reason=result['reason'], summary=None)
    if len(_bytes(result)) > (max_output_bytes if type(max_output_bytes) is int and max_output_bytes >= 2048 else 24000):
        return {'available': False, 'reason': 'context_unavailable_output_budget',
                'context_version': CONTEXT_VERSION, 'observations': {name: {'available': False,
                    'reason': 'retained_context_output_budget_exceeded', 'summary': None} for name in _KINDS},
                'fresh_source_attestation': False, 'raw_or_index_reread': False,
                'operator_rerun': False, 'model_calls': 0, 'database_writes': 0,
                'scope': _SCOPE, 'search_scope': 'Summaries and exact-reference metadata withheld together; no numerical truncation or fallback.'}
    return result
