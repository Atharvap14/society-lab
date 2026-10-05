"""Retrospective literal-marker proximity, with no semantic or causal scoring.

Pure in-memory instrument. Host-produced source/index bindings are validated,
not independently authenticated. No files, models, networks or database access.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import actor_event_queries as queries

VERSION = 'literal-wait-action-alignment-v1'
HORIZONS = (30, 60, 300)
MAX_MESSAGES = 15000
MAX_EVENTS = 15000
MAX_CONTENT_BYTES = 32 * 1024**2
MAX_MESSAGE_BYTES = 1024**2
MAX_MARKER_SPANS = 100000
MAX_CONTROLS = 64
MAX_WORK = 2_000_000
MAX_LINKS = 20000
MAX_OUTPUT_BYTES = 16 * 1024**2
EXPECTED_QUERY_SCOPE = 'Finalized indexed rows under exact attributed actor/time/action predicate; missing rooms included.'
EXPECTED_INVALID_TIME_SCOPE = 'Build invalid timestamps are unassigned; they cannot be attributed to this actor/time predicate.'
_MARKERS = re.compile(r'\b(?:wait|waits|waited|waiting|pause|pauses|paused|pausing)\b', re.IGNORECASE | re.ASCII)
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
POLICIES = {'explicit_offset_to_utc', 'export_naive_assumed_utc', 'unavailable_in_normalized_chat'}
EXPECTED_QUERY_IMPLEMENTATIONS = {
    'event_source_index.py': 'be894562af9a436297339ff682859f1c6258e81444e860370ea91d6e9cdf19c3',
    'source_scanner.py': '559f62a1680adc2040456b0f31ff6ef3a8ac15fcd57151b4e7efa349b36edb04',
    'source_links.py': '3ec3dd73677cc94af7b0f4fae22a165397ee39dcbc57f46311cf0eb7415e1723',
    'source_workflow.py': 'fbe24d04c2221636667d563c819fac2b280a5e3927fd6f6fed2ef46e0ee841e2',
    'actor_event_queries.py': '4ea42b85fa74d6a59bec4e4aa24b98df361e92058d7572ed8c5fa2967d218777',
}
REF_PREFIXES = {'actor_audit': 'actor_event_audit-', 'index': 'event_source_index-',
    'dataset': 'dataset-', 'discovery': 'discovery-', 'selected_audit': 'selected_lead_audit-'}
MESSAGE_REQUIRED = {'id', 'agent_id', 'speaker_id', 'speaker_type', 'room_id', 'created_at',
                    'timestamp', 'content', 'source', 'content_hash'}
MESSAGE_ALLOWED = MESSAGE_REQUIRED | {'agent_name', 'reply_to'}
LIMITATIONS = [
    'Literal tokens do not adjudicate negation, quotation, hypothetical speech, reports, instructions or actual waiting.',
    'Nearby same-actor recorded actions are temporal association, not detector precision/recall, inactivity, lease, receipt, exposure, belief or causal influence.',
    'Clock policies are normalization conventions; equal conventions and signed recorded lags do not verify synchronized physical clocks or processing latency.',
    'Event rooms remain explicit known/missing/invalid observations. Shared time-window membership never assigns a room or proves shared context.',
    'The same event can support several messages, overlapping windows and nested horizons; those observations are not independent.',
    'Nonmarker controls are deterministic source-ID selections, not negative ground truth, a probability sample or task/actor matched controls.',
    'No nearby indexed candidate is a scoped descriptive result; boundary censoring, logging gaps and upstream/global absence remain unknown.',
    'This is retrospective same-source post-selection exploration; no held-out replication, significance, novelty or automatic behavioral status change follows.',
    'Raw-line and record hashes remain scan declarations within a host-authenticated index packet; this pure function does not reread or authenticate files or registry objects.',
]


def _hash(value):
    return queries.index._hash(value)


def _micros(value):
    stamp = datetime.fromisoformat(queries._utc(value))
    delta = stamp - _EPOCH
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def _sha(value):
    return type(value) is str and queries.index._SHA.fullmatch(value) is not None


def _refs(values):
    if values is None:
        return {}
    if type(values) is not dict or not set(values) <= set(REF_PREFIXES):
        raise ValueError('Use exact typed source reference roles')
    for role, ref in values.items():
        if (type(ref) is not dict or set(ref) != {'id', 'version', 'hash'} or
            type(ref['id']) is not str or not ref['id'].startswith(REF_PREFIXES[role]) or
            not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,255}', ref['id']) or
            type(ref['version']) is not int or ref['version'] < 1 or not _sha(ref['hash'])):
            raise ValueError('Malformed exact source reference')
    return copy.deepcopy(values)


def _packet(packet):
    """Finite guards without calling file-reading code-pin helper functions."""
    if type(packet) is not dict or set(packet) != queries.PACKET_KEYS:
        raise ValueError('Use an exact released actor query packet')
    queries.index.scanner._validate_shape(packet, max_depth=12, max_items=queries.MAX_SUMMARY_ITEMS, max_string=8192)
    if len(queries.index._canonical(packet)) > queries.MAX_PACKET_BYTES:
        raise ValueError('Actor packet exceeds byte bound')
    expected_base = {k: v for k, v in EXPECTED_QUERY_IMPLEMENTATIONS.items() if k != 'actor_event_queries.py'}
    if (packet['kind'] != 'actor_event_source_query' or packet['schema_version'] != '1.0' or
        packet['instrument_version'] != queries.VERSION or packet['index_instrument_version'] != queries.index.INDEX_VERSION or
        type(packet['model_calls']) is not int or packet['model_calls'] != 0 or packet['read_only'] is not True or
        packet['raw_content_persisted'] is not False or packet['implementation_hashes'] != EXPECTED_QUERY_IMPLEMENTATIONS):
        raise ValueError('Unsupported actor query version or frozen code pins')
    binding = packet['index']
    if (type(binding) is not dict or set(binding) != queries.INDEX_BINDING_KEYS or
        binding['file_hash_authenticated'] is not True or binding['implementation_hashes'] != expected_base or
        type(binding['bytes']) is not int or not 0 < binding['bytes'] <= queries.index.MAX_INDEX_BYTES or
        type(binding['path']) is not str or not Path(binding['path']).is_absolute() or
        binding['path_resolution'] not in ('filesystem_resolved', 'lexical_absolute_virtual_filesystem') or
        not _sha(binding['internal_metadata_sha256'])):
        raise ValueError('Missing typed accepted host index binding')
    digests = [binding[k] for k in ('expected_file_sha256', 'read_file_sha256', 'post_query_file_sha256')]
    if not all(_sha(h) for h in digests) or len(set(digests)) != 1:
        raise ValueError('Inconsistent accepted host artifact hashes')
    plan = packet['query']
    if type(plan) is not dict or set(plan) != {'actor_ids', 'windows', 'action_types', 'max_rows', 'max_candidate_rows', 'combination'}:
        raise ValueError('Invalid actor query plan')
    canonical = queries._plan(**{k: plan[k] for k in ('actor_ids', 'windows', 'action_types', 'max_rows', 'max_candidate_rows')})
    if queries.index._canonical(canonical) != queries.index._canonical(plan):
        raise ValueError('Actor query plan is not canonical')
    coverage = packet['coverage']
    if (type(coverage) is not dict or set(coverage) != queries.QUERY_COVERAGE_KEYS or
        type(coverage['build_scan']) is not dict or set(coverage['build_scan']) != set(queries.COVERAGE_KEYS)):
        raise ValueError('Missing typed actor query coverage')
    if coverage['scope'] != EXPECTED_QUERY_SCOPE or coverage['invalid_time_scope'] != EXPECTED_INVALID_TIME_SCOPE:
        raise ValueError('Actor query scope declarations differ from the frozen contract')
    build = coverage['build_scan']
    for key in ('physical_rows_seen', 'parsed_rows', 'indexed_rows', 'malformed_rows', 'duplicate_ids', 'invalid_timestamp_rows'):
        if type(build[key]) is not int or not 0 <= build[key] <= queries.index.MAX_ROWS:
            raise ValueError('Invalid strict build counter')
    for key in ('complete_scan', 'source_eof_observed', 'physical_eof_observed', 'decoder_eof_observed', 'scanned_file_id_uniqueness_verified', 'global_database_id_uniqueness_verified'):
        if type(build[key]) is not bool:
            raise ValueError('Strict build flags required')
    if (not build['indexed_rows'] <= build['parsed_rows'] <= build['physical_rows_seen'] or
        build['invalid_timestamp_rows'] > build['indexed_rows'] or build['global_database_id_uniqueness_verified'] or
        build['scanned_file_id_uniqueness_verified'] != build['complete_scan'] or
        build['source_eof_observed'] != (build['physical_eof_observed'] and build['decoder_eof_observed']) or
        type(build['stop_reason']) is not str or build['stop_reason'] not in queries.index.STOP_REASONS or
        (build['complete_scan'] and (build['stop_reason'] != 'eof' or not build['source_eof_observed'] or
            build['indexed_rows'] != build['physical_rows_seen'] or build['malformed_rows'] or build['duplicate_ids'])) or
        (not build['complete_scan'] and build['stop_reason'] == 'eof')):
        raise ValueError('Inconsistent build scope')
    for key, ceiling in (('compressed_bytes_read', queries.index.MAX_COMPRESSED_BYTES), ('expanded_bytes_read', queries.index.MAX_EXPANDED_BYTES), ('pending_expanded_bytes', queries.index.MAX_ROW_BYTES)):
        if type(build[key]) is not int or not 0 <= build[key] <= ceiling:
            raise ValueError('Invalid build byte counter')
    if build['gzip_crc_checked'] is not None and type(build['gzip_crc_checked']) is not bool:
        raise ValueError('Invalid declared gzip flag')
    declaration = packet['source_metadata_declaration']
    if type(declaration) is not dict or set(declaration) != {'value', 'verified'} or declaration['verified'] is not False or queries.index._metadata(declaration['value']) != declaration['value']:
        raise ValueError('Invalid declared source metadata')
    observed = packet['observed_source']
    if (type(observed) is not dict or set(observed) != {'sha256', 'md5', 'bytes', 'whole_file_observed', 'hash_scope'} or
        not _sha(observed['sha256']) or type(observed['md5']) is not str or not re.fullmatch(r'[0-9a-f]{32}', observed['md5']) or
        type(observed['bytes']) is not int or observed['bytes'] != build['compressed_bytes_read'] or
        type(observed['whole_file_observed']) is not bool or observed['whole_file_observed'] != build['source_eof_observed'] or
        observed['hash_scope'] != ('whole_physical_file' if build['source_eof_observed'] else 'physical_prefix_read') or not _sha(packet['source_input_fingerprint'])):
        raise ValueError('Invalid declared source observation')
    for key in ('candidate_rows', 'candidate_rows_validated', 'other_explicit_actor_rows', 'matched_rows', 'returned_rows'):
        if type(coverage[key]) is not int or not 0 <= coverage[key] <= plan['max_candidate_rows']:
            raise ValueError('Invalid actor query row counter')
    if (coverage['candidate_validation_complete'] is not True or coverage['candidate_rows'] != coverage['candidate_rows_validated'] or
        type(coverage['query_complete']) is not bool or type(coverage['truncated']) is not bool or
        coverage['query_complete'] != (coverage['matched_rows'] <= plan['max_rows']) or coverage['truncated'] != (not coverage['query_complete']) or
        coverage['returned_rows'] != min(coverage['matched_rows'], plan['max_rows']) or
        coverage['matched_rows'] + coverage['other_explicit_actor_rows'] > coverage['candidate_rows'] or coverage['global_absence'] != 'unverified'):
        raise ValueError('Inconsistent actor query coverage')
    statuses = coverage['candidate_actor_status_counts']
    if (type(statuses) is not dict or any(k not in ('selected_valid', 'conflicting_fields', 'invalid_field', 'unknown', 'unrecognized_action') or
        type(v) is not int or v < 1 for k, v in statuses.items()) or sum(statuses.values()) != coverage['candidate_rows'] or
        statuses.get('selected_valid', 0) != coverage['matched_rows'] + coverage['other_explicit_actor_rows']):
        raise ValueError('Inconsistent candidate attribution diagnostics')
    records = packet['records']
    if type(records) is not list or len(records) != coverage['returned_rows'] or len(records) > MAX_EVENTS:
        raise ValueError('Invalid retained event count')
    ids, lines, seen_lines = set(), [], set()
    for entry in records:
        if type(entry) is not dict or set(entry) != {'record', 'source', 'projection_sha256', 'room_observation', 'window_ids'}:
            raise ValueError('Invalid event wrapper')
        record, source = entry['record'], entry['source']
        queries.index._validate_projection(record)
        if (type(source) is not dict or set(source) != {'path', 'table', 'line', 'record_sha256', 'raw_line_sha256'} or
            source['table'] != 'events' or type(source['path']) is not str or not Path(source['path']).is_absolute() or
            type(source['line']) is not int or not 1 <= source['line'] <= build['physical_rows_seen'] or
            not _sha(source['record_sha256']) or not _sha(source['raw_line_sha256'])):
            raise ValueError('Invalid original event source pin')
        if (record['id'] in ids or source['line'] in seen_lines or record['actor_status'] != 'selected_valid' or record['actor_id'] not in plan['actor_ids'] or
            entry['projection_sha256'] != _hash(record) or entry['window_ids'] != queries._window_ids(record, plan) or not entry['window_ids'] or
            queries.index._canonical(entry['room_observation']) != queries.index._canonical(queries._room(record)) or
            (plan['action_types'] is not None and record['action_type'] not in plan['action_types'])):
            raise ValueError('Event identity/hash/actor/time/window/room diagnostics do not reproduce')
        ids.add(record['id']); lines.append(source['line']); seen_lines.add(source['line'])
    if lines != sorted(set(lines)):
        raise ValueError('Retained events require unique physical-line order')
    return plan, coverage


def _messages(messages, plan, clock_policies):
    if type(messages) is not list or not 1 <= len(messages) <= MAX_MESSAGES:
        raise ValueError('Use bounded normalized selected chat messages')
    queries.index.scanner._validate_shape(messages, max_depth=8, max_items=3_000_000, max_string=MAX_MESSAGE_BYTES)
    ids, agent_rows, content_bytes, spans = set(), [], 0, 0
    excluded = Counter()
    for message in messages:
        if type(message) is not dict or not MESSAGE_REQUIRED <= set(message) or not set(message) <= MESSAGE_ALLOWED:
            raise ValueError('Missing or unexpected normalized chat fields')
        mid = message['id']
        if type(mid) is not str or not queries.index._UUID.fullmatch(mid) or mid in ids:
            raise ValueError('Chat source IDs must be unique exact UUID strings')
        ids.add(mid)
        if type(message['content']) is not str or len(message['content'].encode('utf-8')) > MAX_MESSAGE_BYTES:
            raise ValueError('Chat content exceeds the declared row bound')
        content_bytes += len(message['content'].encode('utf-8'))
        if content_bytes > MAX_CONTENT_BYTES:
            raise ValueError('Aggregate chat content exceeds the declared bound')
        stamp = queries._utc(message['created_at'])
        if queries._utc(message['timestamp']) != stamp:
            raise ValueError('Normalized chat timestamp fields conflict')
        if type(message['speaker_type']) is not str or not 1 <= len(message['speaker_type']) <= 64 or type(message['speaker_id']) is not str or not 1 <= len(message['speaker_id']) <= 256:
            raise ValueError('Explicit normalized speaker metadata required')
        if type(message['room_id']) is not str or not queries.index._UUID.fullmatch(message['room_id']):
            raise ValueError('Exact chat room UUID required; event rooms will not be inferred')
        source = message['source']
        allowed = {'file', 'line', 'table', 'record_sha256', 'raw_line_sha256'}
        if (type(source) is not dict or not {'file', 'line', 'table'} <= set(source) or not set(source) <= allowed or
            type(source['file']) is not str or not Path(source['file']).is_absolute() or len(source['file'].encode('utf-8')) > 4096 or
            type(source['line']) is not int or source['line'] < 1 or source['table'] != 'chat_messages' or
            any(not _sha(source[k]) for k in set(source) & {'record_sha256', 'raw_line_sha256'})):
            raise ValueError('Chat source coordinates must be explicit typed provenance')
        stable = {'speaker': message['speaker_id'], 'timestamp': message['timestamp'],
                  'content': message['content'], 'room_id': message['room_id']}
        compound = hashlib.sha256(json.dumps(stable, sort_keys=True).encode('utf-8')).hexdigest()
        if not _sha(message['content_hash']) or message['content_hash'] != compound:
            raise ValueError('Declared normalized compound content hash does not reproduce')
        if message['speaker_type'] != 'agent':
            excluded[message['speaker_type']] += 1
            continue
        actor = message['agent_id']
        if type(actor) is not str or not queries.index._UUID.fullmatch(actor) or actor != message['speaker_id']:
            raise ValueError('Agent identity fields conflict; no alias inference')
        matches = []
        for match in _MARKERS.finditer(message['content']):
            spans += 1
            if spans > MAX_MARKER_SPANS:
                raise ValueError('Marker span budget exceeded; no sampling')
            matches.append({'token': match.group().lower(), 'start': match.start(), 'end_exclusive': match.end()})
        windows = [w['id'] for w in plan['windows'] if w['start'] <= stamp < w['end_exclusive']]
        pin = {'message_id': mid, 'agent_id': actor, 'timestamp': stamp, 'chat_room_id': message['room_id'],
            'source': copy.deepcopy(source), 'normalized_record_sha256': _hash(message),
            'declared_compound_content_hash': message['content_hash'],
            'original_text_sha256': hashlib.sha256(message['content'].encode('utf-8')).hexdigest(),
            'query_time_window_ids': windows, 'marker_spans': matches,
            'span_coordinates': 'Original normalized content Python string code points; no normalization or byte-offset claim.',
            'marker_semantics': 'unadjudicated_literal_hit' if matches else 'literal_nonmarker_not_negative_ground_truth'}
        agent_rows.append(pin)
    if clock_policies is not None:
        if type(clock_policies) is not dict or not set(clock_policies) <= ids or any(type(v) is not str or v not in POLICIES for v in clock_policies.values()):
            raise ValueError('Chat clock policies require exact supplied message IDs and supported declared conventions')
    for row in agent_rows:
        row['chat_clock_policy'] = (clock_policies or {}).get(row['message_id'], 'unavailable_in_normalized_chat')
        row['chat_clock_policy_authentication'] = 'Host declaration only; raw timestamp policy/synchronization not verified here.'
    return sorted(agent_rows, key=lambda row: row['message_id']), {
        'supplied_messages': len(messages), 'agent_authored_messages': len(agent_rows),
        'excluded_nonagent_by_speaker_type': dict(sorted(excluded.items())),
        'aggregate_content_bytes': content_bytes, 'literal_marker_spans': spans}


def _event_pin(entry):
    r = entry['record']
    return {'event_id': r['id'], 'actor_id': r['actor_id'], 'actor_field': r['actor_field'],
        'timestamp': r['created_at'], 'action_type': r['action_type'],
        'source': copy.deepcopy(entry['source']), 'projection_sha256': entry['projection_sha256'],
        'room_observation': copy.deepcopy(entry['room_observation']), 'window_ids': list(entry['window_ids']),
        'clock_policy': r['fields']['created_at']['timezone_policy'],
        'pause_requested_seconds': r['seconds'] if r['action_type'] == 'PAUSE' else None,
        'pause_duration_scope': 'Requested seconds only; not elapsed inactivity.'}


def analyze_wait_marker_alignment(messages, actor_packet, *, chat_clock_policies=None,
                                  max_controls=32, max_work=1_000_000, source_refs=None):
    queries.index._bound(max_controls, 'max_controls', MAX_CONTROLS)
    queries.index._bound(max_work, 'max_work', MAX_WORK)
    refs = _refs(source_refs)
    plan, coverage = _packet(actor_packet)
    rows, message_scope = _messages(messages, plan, chat_clock_policies)
    markers = [row for row in rows if row['marker_spans']]
    controls = sorted((row for row in rows if not row['marker_spans']),
        key=lambda row: (_hash([VERSION, row['message_id']]), row['message_id']))[:max_controls]
    selected = sorted([('marker', row) for row in markers] + [('nonmarker_control', row) for row in controls], key=lambda pair: pair[1]['message_id'])
    events = [_event_pin(e) for e in actor_packet['records'] if e['record']['action_type'] in ('WAIT', 'PAUSE')]
    events.sort(key=lambda e: e['event_id'])
    work = 64 * (len(messages) + len(actor_packet['records']) + 1) + len(messages) * len(plan['windows']) + 3 * len(selected) * len(events)
    output = {'kind': 'wait_marker_action_alignment', 'schema_version': '1.0',
        'instrument_version': VERSION, 'model_calls': 0, 'read_only': True, 'database_writes': 0,
        'source_refs': refs, 'source_refs_authenticated': False,
        'producer_authentication': 'Supplied host query binding and frozen code/projection declarations validated in memory; no independent artifact, registry or raw-source authentication.',
        'accepted_actor_packet_sha256': _hash(actor_packet), 'normalized_chat_input_sha256': _hash(messages),
        'chat_clock_declarations_sha256': _hash(chat_clock_policies or {}),
        'source_hash_policy': 'Compact sorted-key finite UTF-8 JSON for input/record fingerprints; compound chat hashes retain their normalizer purpose; text SHA256 is original UTF-8 bytes.',
        'accepted_query_implementation_pins': dict(EXPECTED_QUERY_IMPLEMENTATIONS),
        'index_binding': copy.deepcopy(actor_packet['index']), 'query': copy.deepcopy(plan),
        'coverage': copy.deepcopy(coverage), 'message_scope': message_scope,
        'configuration': {'horizons_seconds': list(HORIZONS), 'max_controls': max_controls,
            'marker_rule': _MARKERS.pattern, 'marker_flags': 'ASCII case-insensitive whole ASCII words; no normalization.',
            'control_selection': 'First max_controls by SHA256([instrument_version,message_id]), then message_id; no event-based selection.',
            'candidate_rule': 'Exact actor, shared query time-window ID, inclusive absolute horizon. Negative before, zero tie, positive after. No room predicate.',
            'clock_scope': 'Recorded UTC-coordinate association only; raw chat policy may be unavailable; synchronization unverified.'},
        'bounds': {'max_messages': MAX_MESSAGES, 'max_events': MAX_EVENTS, 'max_content_bytes': MAX_CONTENT_BYTES,
            'max_message_bytes': MAX_MESSAGE_BYTES, 'max_marker_spans': MAX_MARKER_SPANS,
            'max_candidate_links': MAX_LINKS, 'max_output_bytes': MAX_OUTPUT_BYTES,
            'max_work': max_work, 'estimated_work': work,
            'work_formula': '64*(M+E+1)+M*W+3*(selected_marker_and_control_messages)*(retained_WAIT_PAUSE_events); finite input/text bounds are separate.',
            'work_scope': 'Declared work proxy checked before any candidate alignment; finite input validation and literal scanning precede this check. No wall-clock guarantee.'},
        'message_pins': [copy.deepcopy(row) | {'analysis_group': group} for group, row in selected],
        'event_pins': events, 'alignment_rows': None, 'summary': None,
        'status': 'not_computed', 'unknown_reasons': [], 'limitations': list(LIMITATIONS)}
    unknown = []
    if not coverage['build_scan']['complete_scan']: unknown.append('partial_source_build')
    if coverage['truncated'] or not coverage['query_complete']: unknown.append('truncated_query_output')
    if coverage['build_scan']['invalid_timestamp_rows']: unknown.append('unassigned_invalid_source_timestamps')
    if plan['action_types'] is not None and not {'WAIT', 'PAUSE'} <= set(plan['action_types']): unknown.append('WAIT_PAUSE_action_scope_incomplete')
    if any(k != 'selected_valid' and v for k, v in coverage['candidate_actor_status_counts'].items()): unknown.append('unassigned_candidate_actor_attribution')
    if work > max_work: unknown.append('aggregate_work_budget_exceeded')
    if unknown:
        output.update(status='unknown_alignment_scope', unknown_reasons=unknown)
        return _bounded_output(output)
    intervals = {w['id']: (_micros(w['start']), _micros(w['end_exclusive'])) for w in plan['windows']}
    indexed_events = [(event, _micros(event['timestamp'])) for event in events]
    links, alignments, reused = 0, [], Counter()
    for group, row in selected:
        t = _micros(row['timestamp']); window_ids = set(row['query_time_window_ids'])
        scope_reason = ('actor_not_selected_by_query' if row['agent_id'] not in plan['actor_ids'] else
                        'message_outside_query_time_windows' if not window_ids else None)
        candidates = []
        if scope_reason is None:
            for event, event_t in indexed_events:
                shared = sorted(window_ids & set(event['window_ids']))
                if event['actor_id'] != row['agent_id'] or not shared:
                    continue
                delta = event_t - t
                within = [h for h in HORIZONS if abs(delta) <= h * 1_000_000]
                if not within:
                    continue
                links += 1
                if links > MAX_LINKS:
                    raise ValueError('Alignment link/output budget exceeded; no partial sampling')
                room = event['room_observation']
                room_relation = ('known_equal' if room['status'] == 'known' and room['room_id'] == row['chat_room_id'] else
                    'known_different' if room['status'] == 'known' else room['status'])
                policy = row['chat_clock_policy']
                clock_relation = ('chat_policy_unavailable' if policy == 'unavailable_in_normalized_chat' else
                    'declared_conventions_same' if policy == event['clock_policy'] else 'declared_conventions_different')
                candidates.append({'event_id': event['event_id'], 'action_type': event['action_type'],
                    'lag_microseconds': delta, 'lag_seconds': delta / 1_000_000,
                    'direction': 'before' if delta < 0 else 'after' if delta > 0 else 'tie',
                    'within_horizons_seconds': within, 'shared_time_window_ids': shared,
                    'event_room_relation': room_relation, 'room_inferred': False,
                    'clock_convention_relation': clock_relation, 'physical_clock_synchronization': 'unverified'})
                reused[event['event_id']] += 1
        by_horizon = {}
        for h in HORIZONS:
            near = [candidate for candidate in candidates if h in candidate['within_horizons_seconds']]
            left_complete = bool(window_ids) and min(intervals[wid][0] for wid in window_ids) <= t - h * 1_000_000
            right_complete = bool(window_ids) and max(intervals[wid][1] for wid in window_ids) > t + h * 1_000_000
            status = ('unknown_message_scope' if scope_reason else 'candidate_observed_boundary_censored' if near and not (left_complete and right_complete) else
                'candidate_observed' if near else 'no_indexed_candidate_boundary_censored' if not (left_complete and right_complete) else 'no_indexed_candidate_in_complete_recorded_band')
            by_horizon[str(h)] = {'before': sum(c['direction'] == 'before' for c in near),
                'tie': sum(c['direction'] == 'tie' for c in near), 'after': sum(c['direction'] == 'after' for c in near),
                'before_support_complete': left_complete and scope_reason is None,
                'after_support_complete': right_complete and scope_reason is None,
                'status': status, 'candidate_event_ids': [c['event_id'] for c in near]}
        alignments.append({'message_id': row['message_id'], 'analysis_group': group,
            'scope_unknown_reason': scope_reason, 'candidates': sorted(candidates, key=lambda c: c['event_id']),
            'by_horizon_seconds': by_horizon})
    def group_summary(group):
        group_rows = [r for r in alignments if r['analysis_group'] == group]
        return {'messages': len(group_rows), 'by_horizon_seconds': {str(h): {
            'messages_with_candidate': sum(bool(r['by_horizon_seconds'][str(h)]['candidate_event_ids']) for r in group_rows),
            'status_counts': dict(sorted(Counter(r['by_horizon_seconds'][str(h)]['status'] for r in group_rows).items()))}
            for h in HORIZONS}}
    output.update(status='computed_recorded_temporal_association', alignment_rows=alignments,
        summary={'marker_messages': len(markers), 'nonmarker_control_messages': len(controls),
            'candidate_links': links, 'distinct_linked_events': len(reused),
            'event_message_link_reuse': dict(sorted(reused.items())),
            'groups': {group: group_summary(group) for group in ('marker', 'nonmarker_control')},
            'discordance_examples': {
                'literal_marker_without_retained_candidate': [r['message_id'] for r in alignments if r['analysis_group'] == 'marker' and not r['candidates'] and not r['scope_unknown_reason']][:8],
                'literal_nonmarker_control_with_candidate': [r['message_id'] for r in alignments if r['analysis_group'] == 'nonmarker_control' and r['candidates']][:8]},
            'example_scope': 'Presentation-only retrospective examples; no precision/recall, negative ground truth or independent replication.'})
    return _bounded_output(output)


def _bounded_output(output):
    if len(queries.index._canonical(output)) > MAX_OUTPUT_BYTES:
        raise ValueError('Alignment output exceeds byte bound; no sampling')
    return output
