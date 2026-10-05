"""Bounded actor/time observations over a host-authenticated frozen event index.

No raw source is reread, no room is imputed, and an actor's recorded boundary
does not establish a successful computer lease, receipt, exposure, or influence.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import event_source_index as index

VERSION = 'actor-time-event-query-v1'
SCHEMA_VERSION = '1.0'
MAX_ACTORS = 128
MAX_WINDOWS = 24
MAX_ROWS = 15000
MAX_CANDIDATES = 15000
MAX_PACKET_BYTES = 64 * 1024**2
MAX_SUMMARY_ITEMS = 8_000_000
COUNT_ACTIONS = ('WAIT', 'PAUSE', 'START_USING_COMPUTER', 'STOP_USING_COMPUTER')
COMBINATION = 'Exact selected actor AND (OR of valid UTC time windows) AND optional action filter; no room predicate or inferred room.'
COVERAGE_KEYS = ('physical_rows_seen', 'parsed_rows', 'indexed_rows', 'malformed_rows',
    'duplicate_ids', 'invalid_timestamp_rows', 'complete_scan', 'stop_reason',
    'source_eof_observed', 'physical_eof_observed', 'decoder_eof_observed',
    'gzip_crc_checked', 'compressed_bytes_read', 'expanded_bytes_read',
    'pending_expanded_bytes', 'scanned_file_id_uniqueness_verified',
    'global_database_id_uniqueness_verified')
ROW_COLUMNS = 'line,id,created_at,action_type,room_id,message_id,chat_message_id,record_sha256,raw_line_sha256,projection_sha256,projection_json'
PACKET_KEYS = {'kind', 'schema_version', 'instrument_version', 'index_instrument_version',
    'model_calls', 'read_only', 'raw_content_persisted', 'index', 'implementation_hashes',
    'query', 'records', 'source_input_fingerprint', 'source_metadata_declaration',
    'observed_source', 'coverage', 'source_pin_scope', 'limitations'}
QUERY_COVERAGE_KEYS = {'build_scan', 'candidate_rows', 'candidate_rows_validated',
    'candidate_validation_complete', 'candidate_actor_status_counts', 'other_explicit_actor_rows',
    'matched_rows', 'returned_rows', 'query_complete', 'truncated', 'invalid_time_scope',
    'global_absence', 'scope'}
INDEX_BINDING_KEYS = {'path', 'path_resolution', 'expected_file_sha256', 'read_file_sha256',
    'post_query_file_sha256', 'file_hash_authenticated', 'bytes', 'implementation_hashes',
    'internal_metadata_sha256'}
LIMITATIONS = [
    'Expected artifact SHA256 must come from a trusted host pin; these functions do not authenticate that caller or upstream snapshot.',
    'Raw-row and raw-line hashes are scan declarations inside the authenticated local artifact; original source bytes are not reread.',
    'Only explicit frozen-instrument actor attribution is selected; conflicting, invalid, missing or unrecognized attribution remains unassigned.',
    'Missing, null or invalid room fields remain observed missingness; actor/time overlap never supplies a room or recipient.',
    'Invalid or missing timestamps cannot enter a UTC time predicate. Their build count is disclosed, not attributed to requested actors/windows.',
    'Query completeness concerns finalized indexed rows under this predicate; partial builds, logging gaps and upstream/global absence remain unverified.',
    'WAIT/PAUSE are recorded actions; START/STOP are recorded boundaries, not verified inactivity, success, an exclusive lease or a complete concurrent-use interval.',
    'Same-time rows retain physical source order for deterministic output only; that ordering is not a measured relay or causal order.',
    'Overlapping windows reuse records and are not independent observations. Summaries describe returned records only when output is truncated.',
]


def implementation_hashes():
    return {**index.implementation_hashes(),
            'actor_event_queries.py': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def _typed_strings(values, pattern, name, ceiling):
    if type(values) is not list or not 1 <= len(values) <= ceiling or any(
        type(v) is not str or not pattern.fullmatch(v) for v in values):
        raise ValueError(name + ' requires a bounded nonempty list of exact typed strings')
    if len(set(values)) != len(values):
        raise ValueError('Duplicate ' + name + ' entries are ambiguous')
    return sorted(values)


def _utc(value):
    if type(value) is not str or not 20 <= len(value) <= 40 or 'T' not in value:
        raise ValueError('Actor windows require explicit UTC ISO timestamps')
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0:
            raise ValueError('UTC required')
        return stamp.astimezone(timezone.utc).isoformat(timespec='microseconds')
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError('Actor windows require explicit UTC ISO timestamps') from exc


def _plan(actor_ids, windows, action_types, max_rows, max_candidate_rows):
    index._bound(max_rows, 'max_rows', MAX_ROWS)
    index._bound(max_candidate_rows, 'max_candidate_rows', MAX_CANDIDATES)
    actors = _typed_strings(actor_ids, index._UUID, 'actor_ids', MAX_ACTORS)
    actions = None if action_types is None else _typed_strings(action_types, index._ACTION, 'action_types', 64)
    if type(windows) is not list or not 1 <= len(windows) <= MAX_WINDOWS:
        raise ValueError('Use a bounded nonempty list of actor UTC windows')
    canonical = []
    for window in windows:
        if type(window) is not dict or not {'start', 'end_exclusive'} <= set(window) or not set(window) <= {'id', 'start', 'end_exclusive'}:
            raise ValueError('Actor windows require start/end_exclusive and optional id; no room or actor aliases')
        row = {'start': _utc(window['start']), 'end_exclusive': _utc(window['end_exclusive'])}
        if row['start'] >= row['end_exclusive']:
            raise ValueError('Actor windows require a positive half-open span')
        label = window.get('id', 'actor-window-' + index._hash(row)[:16])
        if type(label) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', label):
            raise ValueError('Window labels must be bounded identifiers')
        row['id'] = label
        canonical.append(row)
    if len({w['id'] for w in canonical}) != len(canonical) or len({(w['start'], w['end_exclusive']) for w in canonical}) != len(canonical):
        raise ValueError('Duplicate actor windows are ambiguous')
    canonical.sort(key=lambda w: (w['start'], w['end_exclusive'], w['id']))
    return {'actor_ids': actors, 'windows': canonical, 'action_types': actions,
            'max_rows': max_rows, 'max_candidate_rows': max_candidate_rows,
            'combination': COMBINATION}


def _room(record):
    field = record['fields']['data.roomId']
    status = ('known' if field['type_status'] == 'valid' else
              'invalid' if field['type_status'] == 'invalid' else 'missing')
    return {'status': status, 'presence': field['presence'], 'type_status': field['type_status'],
            'room_id': record['room_id'], 'inferred': False}


def _window_ids(record, plan):
    return [w['id'] for w in plan['windows'] if record['time_valid'] and
            w['start'] <= record['created_at'] < w['end_exclusive']]


def _validate_metadata(con):
    schema = con.execute('SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name').fetchall()
    if sorted(r[0] for r in schema) != sorted(index.SQL_SCHEMA):
        raise ValueError('Unexpected index database schema')
    keys = con.execute('SELECT key,length(value) FROM metadata').fetchall()
    if len(keys) != 1 or keys[0][0] != 'metadata' or keys[0][1] > index.MAX_METADATA_BYTES:
        raise ValueError('Unexpected or oversized index metadata')
    meta = json.loads(con.execute('SELECT value FROM metadata WHERE key=?', ('metadata',)).fetchone()[0],
        object_pairs_hook=index.scanner._object_pairs, parse_constant=index.scanner._nonfinite_constant)
    index.scanner._validate_shape(meta, max_depth=12, max_items=4096, max_string=8192)
    if type(meta) is not dict:
        raise ValueError('Index metadata requires a finalized object')
    if (meta.get('kind') != 'bounded_event_source_index' or meta.get('schema_version') != index.SCHEMA_VERSION or
        meta.get('instrument_version') != index.INDEX_VERSION or meta.get('state') not in ('complete', 'partial') or
        meta.get('table') != 'events' or type(meta.get('model_calls')) is not int or meta['model_calls'] != 0 or
        meta.get('raw_payloads_persisted') is not False or meta.get('implementation_hashes') != index.implementation_hashes()):
        raise ValueError('Index version/state/implementation provenance mismatch')
    declaration = meta.get('source_metadata_declaration')
    if type(declaration) is not dict or declaration.get('verified') is not False or index._metadata(declaration.get('value')) != declaration.get('value'):
        raise ValueError('Invalid source metadata declaration')
    index._validate_build_metadata(meta)
    if con.execute('SELECT COUNT(*) FROM events').fetchone()[0] != meta['coverage']['indexed_rows']:
        raise ValueError('Index row count does not match finalized coverage')
    fingerprint = index._hash({k: meta[k] for k in ('source_path', 'path_resolution', 'observed_source', 'source_metadata_declaration')})
    if fingerprint != meta.get('source_input_fingerprint'):
        raise ValueError('Index source fingerprint mismatch')
    return meta


def _entry(row, meta, plan):
    if type(row[10]) is not str or len(row[10].encode('utf-8')) > index.MAX_PROJECTION_BYTES:
        raise ValueError('Indexed projection exceeds row bound')
    record = json.loads(row[10], object_pairs_hook=index.scanner._object_pairs,
                        parse_constant=index.scanner._nonfinite_constant)
    index._validate_projection(record)
    projection_sha = index._hash(record)
    if projection_sha != row[9] or tuple(record[k] for k in ('id', 'created_at', 'action_type', 'room_id', 'message_id', 'chat_message_id')) != row[1:7]:
        raise ValueError('Stored selection columns/projection hash mismatch')
    if type(row[0]) is not int or not 1 <= row[0] <= meta['coverage']['physical_rows_seen'] or any(
        type(h) is not str or not index._SHA.fullmatch(h) for h in row[7:10]):
        raise ValueError('Invalid indexed source coordinate/hash')
    windows = _window_ids(record, plan)
    if not windows or (plan['action_types'] is not None and record['action_type'] not in plan['action_types']):
        raise ValueError('Stored row does not reproduce the time/action candidate predicate')
    return {'record': record, 'source': {'path': meta['source_path'], 'table': 'events',
        'line': row[0], 'record_sha256': row[7], 'raw_line_sha256': row[8]},
        'projection_sha256': projection_sha, 'room_observation': _room(record),
        'window_ids': windows}


def read_actor_event_index(path, *, expected_file_sha256, actor_ids, windows,
                           action_types=None, max_rows=256, max_candidate_rows=15000):
    """Read exact attributed actor/time events, regardless of room presence.

    Time/action candidates must all fit the validation bound; exceeding it
    rejects the query before parsing any candidate, rather than sampling.
    """
    if type(expected_file_sha256) is not str or not index._SHA.fullmatch(expected_file_sha256):
        raise ValueError('Exact expected index file SHA256 is mandatory')
    plan = _plan(actor_ids, windows, action_types, max_rows, max_candidate_rows)
    index_path, resolution = index.scanner.resolve_source_path(path)
    if not index_path.is_file():
        raise ValueError('Existing SQLite index required')
    digest, size = index._file_hash(index_path)
    if digest != expected_file_sha256:
        raise ValueError('Index artifact SHA256 does not match expected bytes')
    con = sqlite3.connect(index_path.as_uri() + '?mode=ro', uri=True)
    try:
        con.execute('PRAGMA query_only=ON')
        con.execute('PRAGMA trusted_schema=OFF')
        con.execute('PRAGMA cache_size=-4096')
        meta = _validate_metadata(con)
        where = '(' + ' OR '.join('(created_at>=? AND created_at<?)' for _ in plan['windows']) + ')'
        parameters = [value for w in plan['windows'] for value in (w['start'], w['end_exclusive'])]
        if plan['action_types'] is not None:
            where += ' AND action_type IN (' + ','.join('?' for _ in plan['action_types']) + ')'
            parameters.extend(plan['action_types'])
        if len(parameters) + 1 > con.getlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER):
            raise ValueError('Typed query exceeds this SQLite backend bind limit')
        candidate_count = con.execute('SELECT COUNT(*) FROM events WHERE ' + where, parameters).fetchone()[0]
        if candidate_count > max_candidate_rows:
            raise ValueError('Time/action candidate budget exceeded; narrow windows/actions or explicitly raise the bounded candidate limit')
        records, retained, matched, scanned = [], 0, 0, 0
        statuses, other_actors = {}, 0
        cursor = con.execute('SELECT ' + ROW_COLUMNS + ' FROM events WHERE ' + where + ' ORDER BY line LIMIT ?', parameters + [max_candidate_rows])
        for row in cursor:
            entry = _entry(row, meta, plan); scanned += 1
            record = entry['record']; status = record['actor_status']
            statuses[status] = statuses.get(status, 0) + 1
            if status != 'selected_valid':
                continue
            if record['actor_id'] not in plan['actor_ids']:
                other_actors += 1
                continue
            matched += 1
            if len(records) < max_rows:
                retained += len(index._canonical(entry))
                if retained > MAX_PACKET_BYTES:
                    raise ValueError('Actor query exceeds retained output byte bound')
                records.append(entry)
        if scanned != candidate_count:
            raise ValueError('Candidate coverage differs from authenticated query count')
    except (sqlite3.Error, UnicodeError, json.JSONDecodeError, KeyError, TypeError, RecursionError) as exc:
        raise ValueError('Index cannot be read under the actor/time observation contract') from exc
    finally:
        con.close()
    after_digest, after_size = index._file_hash(index_path)
    if after_digest != digest or after_size != size:
        raise ValueError('Index artifact changed during query')
    packet = {'kind': 'actor_event_source_query', 'schema_version': SCHEMA_VERSION,
        'instrument_version': VERSION, 'index_instrument_version': index.INDEX_VERSION,
        'model_calls': 0, 'read_only': True, 'raw_content_persisted': False,
        'index': {'path': str(index_path), 'path_resolution': resolution,
            'expected_file_sha256': expected_file_sha256, 'read_file_sha256': digest,
            'post_query_file_sha256': after_digest, 'file_hash_authenticated': True,
            'bytes': size, 'implementation_hashes': index.implementation_hashes(),
            'internal_metadata_sha256': index._hash(meta)},
        'implementation_hashes': implementation_hashes(), 'query': plan,
        'records': records, 'source_input_fingerprint': meta['source_input_fingerprint'],
        'source_metadata_declaration': {'value': copy.deepcopy(meta['source_metadata_declaration']['value']), 'verified': False},
        'observed_source': {k: meta['observed_source'][k] for k in ('sha256', 'md5', 'bytes', 'whole_file_observed', 'hash_scope')},
        'coverage': {'build_scan': {k: meta['coverage'][k] for k in COVERAGE_KEYS},
            'candidate_rows': candidate_count, 'candidate_rows_validated': scanned,
            'candidate_validation_complete': True, 'candidate_actor_status_counts': statuses,
            'other_explicit_actor_rows': other_actors, 'matched_rows': matched,
            'returned_rows': len(records), 'query_complete': matched <= max_rows,
            'truncated': matched > max_rows,
            'invalid_time_scope': 'Build invalid timestamps are unassigned; they cannot be attributed to this actor/time predicate.',
            'global_absence': 'unverified', 'scope': 'Finalized indexed rows under exact attributed actor/time/action predicate; missing rooms included.'},
        'source_pin_scope': 'Index-authenticated scan declarations; original raw JSONL bytes are not freshly reread by this query.',
        'limitations': list(LIMITATIONS)}
    if len(index._canonical(packet)) > MAX_PACKET_BYTES:
        raise ValueError('Actor query packet exceeds output byte bound')
    return packet


def summarize_actor_events(packet):
    """Compute descriptive counts over retained records in a host query packet.

    This pure function checks packet/record consistency but does not reopen
    files or authenticate the producer. It never constructs access intervals.
    """
    if type(packet) is not dict or set(packet) != PACKET_KEYS:
        raise ValueError('Use an actor query packet')
    index.scanner._validate_shape(packet, max_depth=12, max_items=MAX_SUMMARY_ITEMS, max_string=8192)
    if len(index._canonical(packet)) > MAX_PACKET_BYTES:
        raise ValueError('Actor summary input exceeds byte bound')
    if (packet.get('kind') != 'actor_event_source_query' or packet.get('schema_version') != SCHEMA_VERSION or
        packet.get('instrument_version') != VERSION or packet.get('index_instrument_version') != index.INDEX_VERSION or
        packet.get('read_only') is not True or type(packet.get('model_calls')) is not int or packet['model_calls'] != 0 or
        packet.get('raw_content_persisted') is not False or packet.get('implementation_hashes') != implementation_hashes()):
        raise ValueError('Actor query packet contract mismatch')
    supplied_plan = packet.get('query')
    if type(supplied_plan) is not dict or set(supplied_plan) != {'actor_ids', 'windows', 'action_types', 'max_rows', 'max_candidate_rows', 'combination'}:
        raise ValueError('Unexpected actor query plan')
    plan = _plan(**{k: supplied_plan[k] for k in ('actor_ids', 'windows', 'action_types', 'max_rows', 'max_candidate_rows')})
    if index._canonical(plan) != index._canonical(supplied_plan):
        raise ValueError('Noncanonical actor query plan')
    binding, coverage = packet.get('index'), packet.get('coverage')
    if (type(binding) is not dict or set(binding) != INDEX_BINDING_KEYS or
        binding.get('file_hash_authenticated') is not True or binding.get('implementation_hashes') != index.implementation_hashes() or
        type(binding['bytes']) is not int or not 0 < binding['bytes'] <= index.MAX_INDEX_BYTES or
        type(binding['path']) is not str or not Path(binding['path']).is_absolute() or
        binding['path_resolution'] not in ('filesystem_resolved', 'lexical_absolute_virtual_filesystem')):
        raise ValueError('Missing accepted host artifact binding')
    hashes = [binding.get(k) for k in ('expected_file_sha256', 'read_file_sha256', 'post_query_file_sha256')]
    if any(type(h) is not str or not index._SHA.fullmatch(h) for h in hashes) or len(set(hashes)) != 1:
        raise ValueError('Inconsistent host artifact hashes')
    if type(binding.get('internal_metadata_sha256')) is not str or not index._SHA.fullmatch(binding['internal_metadata_sha256']):
        raise ValueError('Missing internal metadata hash')
    if type(coverage) is not dict or set(coverage) != QUERY_COVERAGE_KEYS or type(coverage.get('build_scan')) is not dict or set(coverage['build_scan']) != set(COVERAGE_KEYS):
        raise ValueError('Missing actor query coverage')
    build = coverage['build_scan']
    for key in ('physical_rows_seen', 'parsed_rows', 'indexed_rows', 'malformed_rows', 'duplicate_ids', 'invalid_timestamp_rows'):
        if type(build[key]) is not int or not 0 <= build[key] <= index.MAX_ROWS:
            raise ValueError('Invalid declared build row counter')
    for key in ('complete_scan', 'source_eof_observed', 'physical_eof_observed', 'decoder_eof_observed', 'scanned_file_id_uniqueness_verified', 'global_database_id_uniqueness_verified'):
        if type(build[key]) is not bool:
            raise ValueError('Strict declared build flags required')
    if (not build['indexed_rows'] <= build['parsed_rows'] <= build['physical_rows_seen'] or
        build['invalid_timestamp_rows'] > build['indexed_rows'] or build['global_database_id_uniqueness_verified'] or
        build['scanned_file_id_uniqueness_verified'] != build['complete_scan'] or
        build['source_eof_observed'] != (build['physical_eof_observed'] and build['decoder_eof_observed']) or
        type(build['stop_reason']) is not str or build['stop_reason'] not in index.STOP_REASONS or
        (build['complete_scan'] and (build['stop_reason'] != 'eof' or not build['source_eof_observed'] or
         build['indexed_rows'] != build['physical_rows_seen'] or build['malformed_rows'] or build['duplicate_ids'])) or
        (not build['complete_scan'] and build['stop_reason'] == 'eof')):
        raise ValueError('Inconsistent declared build coverage')
    for key, ceiling in (('compressed_bytes_read', index.MAX_COMPRESSED_BYTES), ('expanded_bytes_read', index.MAX_EXPANDED_BYTES), ('pending_expanded_bytes', index.MAX_ROW_BYTES)):
        if type(build[key]) is not int or not 0 <= build[key] <= ceiling:
            raise ValueError('Invalid declared build byte counter')
    if build['gzip_crc_checked'] is not None and type(build['gzip_crc_checked']) is not bool:
        raise ValueError('Invalid declared gzip flag')
    declaration = packet['source_metadata_declaration']
    if type(declaration) is not dict or set(declaration) != {'value', 'verified'} or declaration['verified'] is not False or index._metadata(declaration['value']) != declaration['value']:
        raise ValueError('Invalid declared source provenance')
    observed = packet['observed_source']
    if (type(observed) is not dict or set(observed) != {'sha256', 'md5', 'bytes', 'whole_file_observed', 'hash_scope'} or
        type(observed['sha256']) is not str or not index._SHA.fullmatch(observed['sha256']) or
        type(observed['md5']) is not str or not re.fullmatch(r'[0-9a-f]{32}', observed['md5']) or
        type(observed['bytes']) is not int or observed['bytes'] != build['compressed_bytes_read'] or
        type(observed['whole_file_observed']) is not bool or observed['whole_file_observed'] != build['source_eof_observed'] or
        observed['hash_scope'] != ('whole_physical_file' if build['source_eof_observed'] else 'physical_prefix_read') or
        type(packet['source_input_fingerprint']) is not str or not index._SHA.fullmatch(packet['source_input_fingerprint'])):
        raise ValueError('Invalid declared source observation')
    for key in ('candidate_rows', 'candidate_rows_validated', 'other_explicit_actor_rows', 'matched_rows', 'returned_rows'):
        if type(coverage.get(key)) is not int or not 0 <= coverage[key] <= plan['max_candidate_rows']:
            raise ValueError('Invalid strict actor query coverage counters')
    if (coverage.get('candidate_validation_complete') is not True or coverage['candidate_rows'] != coverage['candidate_rows_validated'] or
        type(coverage.get('query_complete')) is not bool or type(coverage.get('truncated')) is not bool or
        coverage['query_complete'] != (coverage['matched_rows'] <= plan['max_rows']) or coverage['truncated'] != (not coverage['query_complete']) or
        coverage['returned_rows'] != min(coverage['matched_rows'], plan['max_rows']) or
        coverage['matched_rows'] + coverage['other_explicit_actor_rows'] > coverage['candidate_rows'] or coverage.get('global_absence') != 'unverified'):
        raise ValueError('Inconsistent actor query coverage')
    statuses = coverage.get('candidate_actor_status_counts')
    if type(statuses) is not dict or any(k not in ('selected_valid', 'conflicting_fields', 'invalid_field', 'unknown', 'unrecognized_action') or
        type(v) is not int or v < 1 for k, v in statuses.items()) or sum(statuses.values()) != coverage['candidate_rows'] or statuses.get('selected_valid', 0) != coverage['matched_rows'] + coverage['other_explicit_actor_rows']:
        raise ValueError('Inconsistent candidate attribution counts')
    records = packet.get('records')
    if type(records) is not list or len(records) != coverage['returned_rows'] or len(records) > MAX_ROWS:
        raise ValueError('Invalid retained actor records')
    seen, lines, rows = set(), set(), []
    for entry in records:
        if type(entry) is not dict or set(entry) != {'record', 'source', 'projection_sha256', 'room_observation', 'window_ids'}:
            raise ValueError('Unexpected retained actor entry')
        record, source = entry['record'], entry['source']
        index._validate_projection(record)
        if (type(source) is not dict or set(source) != {'path', 'table', 'line', 'record_sha256', 'raw_line_sha256'} or
            source['table'] != 'events' or type(source['path']) is not str or not Path(source['path']).is_absolute() or
            type(source['line']) is not int or not 1 <= source['line'] <= build['physical_rows_seen'] or
            any(type(source[k]) is not str or not index._SHA.fullmatch(source[k]) for k in ('record_sha256', 'raw_line_sha256'))):
            raise ValueError('Invalid retained event source pin')
        if record['id'] in seen or source.get('line') in lines:
            raise ValueError('Duplicate retained event identity or coordinate')
        if record['actor_status'] != 'selected_valid' or record['actor_id'] not in plan['actor_ids'] or not _window_ids(record, plan):
            raise ValueError('Retained record violates exact actor/time scope')
        if plan['action_types'] is not None and record['action_type'] not in plan['action_types']:
            raise ValueError('Retained record violates action scope')
        if entry['projection_sha256'] != index._hash(record) or index._canonical(entry['room_observation']) != index._canonical(_room(record)) or entry['window_ids'] != _window_ids(record, plan):
            raise ValueError('Retained record derived fields do not reproduce')
        seen.add(record['id']); lines.add(source['line']); rows.append(entry)
    if [e['source']['line'] for e in rows] != sorted(lines):
        raise ValueError('Retained records require deterministic physical-line order')
    def counts(entries):
        rooms = {k: sum(e['room_observation']['status'] == k for e in entries) for k in ('known', 'missing', 'invalid')}
        actions = {action: sum(e['record']['action_type'] == action for e in entries) for action in sorted({e['record']['action_type'] for e in entries} | set(COUNT_ACTIONS))}
        durations = [e['record']['seconds'] for e in entries if e['record']['action_type'] == 'PAUSE' and e['record']['seconds'] is not None]
        return {'records': len(entries), 'action_counts': actions, 'room_status_counts': rooms,
            'pause_seconds_valid_records': len(durations), 'pause_requested_seconds_sum': sum(durations),
            'pause_seconds_scope': 'Recorded requested seconds; not elapsed inactivity or an observed lease.'}
    result = {'kind': 'actor_time_observation_summary', 'schema_version': SCHEMA_VERSION,
        'instrument_version': VERSION, 'model_calls': 0, 'read_only': True,
        'input_packet_sha256': index._hash(packet), 'producer_authentication': 'Host query packet binding accepted; no independent file authentication by this pure summary.',
        'index_binding': copy.deepcopy(binding), 'query': copy.deepcopy(plan),
        'coverage': copy.deepcopy(coverage), 'scope': 'Returned records only; overlapping windows/actors are descriptive partitions, not independent samples.',
        'total': counts(rows), 'by_actor': {actor: counts([e for e in rows if e['record']['actor_id'] == actor]) for actor in plan['actor_ids']},
        'by_window': {w['id']: counts([e for e in rows if w['id'] in e['window_ids']]) for w in plan['windows']},
        'record_pins': [{k: copy.deepcopy(e[k]) for k in ('source', 'projection_sha256', 'room_observation', 'window_ids')} | {'event_id': e['record']['id']} for e in rows],
        'limitations': list(LIMITATIONS)}
    if len(index._canonical(result)) > MAX_PACKET_BYTES:
        raise ValueError('Actor summary exceeds output byte bound')
    return result
