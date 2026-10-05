"""Bounded, payload-free event projection index; no model or Store access.

The artifact authenticates this scan's projections and byte observations, not
recipient reading, source logging completeness, or an upstream snapshot.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import re
import sqlite3
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path

from . import source_scanner as scanner
from .source_links import ACTION_TYPES
from .source_workflow import _metadata


INDEX_VERSION = 'bounded-event-source-index-v1'
SCHEMA_VERSION = '1.0'
READ_CHUNK = 64 * 1024
MAX_ROWS = 1_000_000
MAX_COMPRESSED_BYTES = 1024**3
MAX_EXPANDED_BYTES = 8 * 1024**3
MAX_ROW_BYTES = 8 * 1024**2
MAX_SECONDS = 7200
MAX_INDEX_BYTES = 2 * 1024**3
MAX_QUERY_ROWS = 15000
MAX_PROJECTION_BYTES = 8192
MAX_METADATA_BYTES = 64 * 1024
MAX_OUTPUT_BYTES = 64 * 1024**2
HELPERS = ('source_scanner.py', 'source_links.py', 'source_workflow.py')
_UUID = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z')
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_ACTION = re.compile(r'[A-Z][A-Z0-9_]{0,63}\Z')
ID_FIELDS = ('messageId', 'chatMessageId', 'computerUseSessionId', 'speakerId', 'agentId', 'roomId')
FIELDS = ('created_at', 'event_index', 'data', 'data.actionType', 'data.speakerType', *('data.' + f for f in ID_FIELDS),
          'data.content', 'data.sessionGoal', 'data.seconds', 'data.output')
RECORD_KEYS = {'id', 'created_at', 'time_valid', 'event_index', 'action_type', 'actor_id',
    'actor_field', 'actor_status', 'room_id', 'message_id', 'chat_message_id',
    'computer_use_session_id', 'speaker_id', 'agent_id', 'content_hash',
    'session_goal_hash', 'seconds', 'raw_provider_output_present', 'fields'}
STOP_REASONS = frozenset({'eof', 'row_limit', 'compressed_byte_limit', 'expanded_byte_limit',
    'row_byte_limit', 'time_limit', 'invalid_gzip_header', 'unverified_decoder_eof',
    'invalid_record_id', 'projection_byte_limit', 'duplicate_record_id', 'progress_callback_error',
    'invalid_utf8', 'duplicate_json_key', 'nonfinite_json', 'invalid_record_structure',
    'malformed_json', 'corrupt_gzip', 'truncated_gzip', 'interrupted', 'index_write_error',
    'io_error', 'source_metadata_mismatch', 'unverified_eof'})
SQL_SCHEMA = (
    'CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)',
    'CREATE TABLE events (line INTEGER PRIMARY KEY, id TEXT NOT NULL UNIQUE, '
    'created_at TEXT, action_type TEXT, room_id TEXT, message_id TEXT, chat_message_id TEXT, '
    'record_sha256 TEXT NOT NULL, raw_line_sha256 TEXT NOT NULL, '
    'projection_sha256 TEXT NOT NULL, projection_json TEXT NOT NULL)',
    'CREATE INDEX events_message ON events(message_id)',
    'CREATE INDEX events_chat_message ON events(chat_message_id)',
    'CREATE INDEX events_window ON events(room_id,created_at)',
    'CREATE INDEX events_action ON events(action_type)',
)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def _hash(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def implementation_hashes():
    return {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ('event_source_index.py', *HELPERS)}


def _bound(value, name, ceiling):
    if type(value) is not int or not 1 <= value <= ceiling:
        raise ValueError(name + ' requires a positive bounded integer')


def _field(data, name, kind):
    if name not in data:
        return {'presence': 'absent', 'type_status': 'unknown'}
    value = data[name]
    if value is None:
        return {'presence': 'null', 'type_status': 'unknown'}
    valid = (type(value) is str and _UUID.fullmatch(value) is not None if kind == 'id' else
        type(value) is str and _ACTION.fullmatch(value) is not None if kind == 'action' else
        type(value) is int and 0 <= value <= 2**63 - 1 if kind == 'index' else
        type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 2**31 - 1 if kind == 'seconds' else
        type(value) is str if kind == 'text' else type(value) is dict if kind == 'object' else
        type(value) is str and value in ('agent', 'user') if kind == 'speaker' else False)
    result = {'presence': 'value', 'type_status': 'valid' if valid else 'invalid'}
    if valid:
        if kind in ('id', 'action', 'index', 'seconds', 'speaker'):
            result['value'] = value
        elif kind == 'text':
            result['value_hash'] = _hash(value)
        if kind == 'action':
            result['recognized'] = value in ACTION_TYPES
    return result


def _time_field(record):
    field = _field(record, 'created_at', 'text')
    if field['type_status'] != 'valid':
        return field
    try:
        stamp = datetime.fromisoformat(record['created_at'].replace('Z', '+00:00'))
        policy = 'explicit_offset_to_utc'
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
            policy = 'export_naive_assumed_utc'
        field.update(utc=stamp.astimezone(timezone.utc).isoformat(timespec='microseconds'),
                     timezone_policy=policy)
    except (ValueError, OverflowError):
        field['type_status'] = 'invalid'
    return field


def _project(raw):
    fields = {'created_at': _time_field(raw), 'event_index': _field(raw, 'event_index', 'index'),
              'data': _field(raw, 'data', 'object')}
    data = raw.get('data') if type(raw.get('data')) is dict else {}
    fields['data.actionType'] = _field(data, 'actionType', 'action')
    fields['data.speakerType'] = _field(data, 'speakerType', 'speaker')
    for name in ID_FIELDS:
        fields['data.' + name] = _field(data, name, 'id')
    for name in ('content', 'sessionGoal'):
        fields['data.' + name] = _field(data, name, 'text')
    fields['data.seconds'] = _field(data, 'seconds', 'seconds')
    output = {'presence': 'absent', 'type_status': 'unknown'}
    if 'output' in data:
        value = data['output']
        output = {'presence': 'null' if value is None else 'value',
                  'type_status': 'unknown' if value is None else 'valid',
                  'value_type': 'null' if value is None else
                      ('object' if type(value) is dict else 'array' if type(value) is list else
                       'string' if type(value) is str else 'boolean' if type(value) is bool else 'number')}
    fields['data.output'] = output
    get = lambda key: fields[key].get('value')
    action = get('data.actionType')
    speaker, agent = get('data.speakerId'), get('data.agentId')
    actor_id = actor_field = None
    actor_status = 'unrecognized_action'
    if speaker is not None and agent is not None and speaker != agent:
        actor_status = 'conflicting_fields'
    elif action in ACTION_TYPES:
        candidate = 'data.speakerId' if action in ('AGENT_TALK', 'USER_TALK') else 'data.agentId'
        actor_id = get(candidate)
        actor_status = ('selected_valid' if actor_id is not None else
                        'invalid_field' if fields[candidate]['type_status'] == 'invalid' else 'unknown')
        if actor_id is not None:
            actor_field = candidate
    return {'id': raw['id'], 'created_at': fields['created_at'].get('utc'),
        'time_valid': fields['created_at']['type_status'] == 'valid',
        'event_index': get('event_index'), 'action_type': action,
        'actor_id': actor_id, 'actor_field': actor_field, 'actor_status': actor_status,
        'room_id': get('data.roomId'), 'message_id': get('data.messageId'),
        'chat_message_id': get('data.chatMessageId'),
        'computer_use_session_id': get('data.computerUseSessionId'),
        'speaker_id': speaker, 'agent_id': agent,
        'content_hash': fields['data.content'].get('value_hash'),
        'session_goal_hash': fields['data.sessionGoal'].get('value_hash'),
        'seconds': get('data.seconds'), 'raw_provider_output_present': output['presence'] == 'value',
        'fields': fields}


class _Stop(Exception):
    def __init__(self, reason):
        self.reason = reason


class _Reader:
    def __init__(self, handle, limit, deadline):
        self.handle, self.limit, self.deadline = handle, limit, deadline
        self.bytes_read = 0
        self.eof_observed = False
        self.sha = hashlib.sha256()
        self.md5 = hashlib.md5(usedforsecurity=False)

    def read(self, size=-1):
        if time.monotonic() >= self.deadline:
            raise _Stop('time_limit')
        remaining = self.limit - self.bytes_read
        if remaining <= 0:
            raise _Stop('compressed_byte_limit')
        count = min(READ_CHUNK, remaining, size if type(size) is int and size >= 0 else READ_CHUNK)
        if count == 0:
            return b''
        data = self.handle.read(count)
        if not data:
            self.eof_observed = True
        else:
            self.bytes_read += len(data)
            self.sha.update(data)
            self.md5.update(data)
        return data

    def read1(self, size=-1):
        return self.read(size)


class _Lines:
    def __init__(self, decoder, physical, expanded_limit, row_limit):
        self.decoder, self.physical = decoder, physical
        self.expanded_limit, self.row_limit = expanded_limit, row_limit
        self.expanded_bytes = 0
        self.buffer = bytearray()
        self.decoder_eof = False

    def next(self):
        while True:
            if time.monotonic() >= self.physical.deadline:
                raise _Stop('time_limit')
            newline = self.buffer.find(b'\n')
            if newline >= 0:
                end = newline + 1
                if end > self.row_limit:
                    raise _Stop('row_byte_limit')
                line = bytes(self.buffer[:end]); del self.buffer[:end]
                return line
            if self.decoder_eof:
                if self.buffer:
                    line = bytes(self.buffer); self.buffer.clear(); return line
                return None
            if len(self.buffer) >= self.row_limit:
                raise _Stop('row_byte_limit')
            remaining = self.expanded_limit - self.expanded_bytes
            if remaining <= 0:
                raise _Stop('expanded_byte_limit')
            request = min(READ_CHUNK, remaining, self.row_limit - len(self.buffer))
            data = self.decoder.read1(request)
            if not data:
                if not self.physical.eof_observed:
                    raise _Stop('unverified_decoder_eof')
                self.decoder_eof = True
            else:
                self.expanded_bytes += len(data); self.buffer.extend(data)


def _file_hash(path):
    stat = path.stat()
    if not 0 < stat.st_size <= MAX_INDEX_BYTES:
        raise ValueError('Event index artifact exceeds file bounds')
    digest = hashlib.sha256()
    with path.open('rb', buffering=0) as handle:
        while True:
            block = handle.read(READ_CHUNK)
            if not block:
                break
            digest.update(block)
    after = path.stat()
    if (stat.st_size, stat.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Event index changed while hashing')
    return digest.hexdigest(), after.st_size


def build_event_index(source_path, destination_path, *, max_rows=400000,
    max_compressed_bytes=340 * 1024**2, max_expanded_bytes=2 * 1024**3,
    max_row_bytes=2 * 1024**2, max_seconds=1800, source_metadata=None, on_progress=None):
    """Create a new durable index; failed scans retain explicit partial metadata.

    max_rows counts physical rows, including rejected rows. No timestamp early
    stopping occurs. Progress callbacks receive counters only, never source data.
    """
    for value, name, ceiling in ((max_rows, 'max_rows', MAX_ROWS),
        (max_compressed_bytes, 'max_compressed_bytes', MAX_COMPRESSED_BYTES),
        (max_expanded_bytes, 'max_expanded_bytes', MAX_EXPANDED_BYTES),
        (max_row_bytes, 'max_row_bytes', MAX_ROW_BYTES), (max_seconds, 'max_seconds', MAX_SECONDS)):
        _bound(value, name, ceiling)
    if on_progress is not None and not callable(on_progress):
        raise ValueError('on_progress must be a trusted host callable or None')
    declaration = _metadata(source_metadata)
    scanner._validate_shape(declaration, max_depth=8, max_items=128, max_string=4096)
    if not isinstance(source_path, (str, Path)) or not isinstance(destination_path, (str, Path)):
        raise ValueError('Ordinary filesystem paths required')
    source, resolution = scanner.resolve_source_path(source_path)
    if not source.is_file() or not source.name.lower().endswith(('.jsonl', '.jsonl.gz')):
        raise ValueError('Use an existing JSONL or gzip JSONL source')
    destination = Path(destination_path).absolute()
    if len(str(source).encode('utf-8')) > 4096 or len(str(destination).encode('utf-8')) > 4096:
        raise ValueError('Filesystem path exceeds bounds')
    if not destination.parent.is_dir():
        raise ValueError('Destination parent must already exist')
    # Exclusive creation is the idempotency boundary, including empty old files.
    with destination.open('xb'):
        pass
    started = time.monotonic(); deadline = started + max_seconds
    limits = {'max_rows': max_rows, 'max_compressed_bytes': max_compressed_bytes,
        'max_expanded_bytes': max_expanded_bytes, 'max_row_bytes': max_row_bytes,
        'max_seconds': max_seconds, 'max_physical_read_request': READ_CHUNK,
        'max_json_depth': 16, 'max_row_json_items': 16384, 'max_index_bytes': MAX_INDEX_BYTES}
    coverage = {'physical_rows_seen': 0, 'parsed_rows': 0, 'indexed_rows': 0,
        'malformed_rows': 0, 'duplicate_ids': 0, 'invalid_timestamp_rows': 0,
        'complete_scan': False, 'stop_reason': 'not_started', 'source_eof_observed': False,
        'physical_eof_observed': False, 'decoder_eof_observed': False,
        'gzip_crc_checked': False if source.name.lower().endswith('.gz') else None,
        'compressed_bytes_read': 0, 'expanded_bytes_read': 0, 'pending_expanded_bytes': 0,
        'scanned_file_id_uniqueness_verified': False, 'global_database_id_uniqueness_verified': False}
    meta = {'kind': 'bounded_event_source_index', 'schema_version': SCHEMA_VERSION,
        'instrument_version': INDEX_VERSION, 'state': 'building', 'table': 'events',
        'source_path': str(source), 'path_resolution': resolution, 'limits': limits,
        'source_metadata_declaration': {'value': declaration, 'verified': False},
        'implementation_hashes': implementation_hashes(), 'coverage': coverage,
        'problems': [], 'model_calls': 0, 'raw_payloads_persisted': False,
        'hash_policy': 'SHA256 of compact sorted-key finite UTF-8 JSON; value hashes include JSON string quoting; raw-line SHA256 includes any terminator.',
        'time_policy': 'Explicit source offsets normalize to UTC; naive export timestamps are explicitly assumed UTC. Query windows require explicit UTC.',
        'time_limit_policy': 'Cooperative scan deadline checks before reads/rows/commits; blocking filesystem operations and artifact finalization/hashing cannot be forcibly interrupted by this parameter.',
        'limitations': ['Indexed fields and raw-row pins are this scan observations, not recipient receipt, reading or causal influence.',
            'Whole-file EOF is not global database or upstream logging completeness.',
            'Hashing observes returned physical bytes; mounted-cache prefetch and wire traffic are unmeasured.',
            'Source size/generation/MD5 declarations do not authenticate an upstream snapshot.',
            'Invalid optional fields remain unknown/invalid; no alias or nearest-time assignment.']}
    con = sqlite3.connect(destination)
    physical = lines = None
    try:
        con.execute('PRAGMA journal_mode=DELETE')
        con.execute('PRAGMA synchronous=FULL')
        con.execute('PRAGMA cache_size=-4096')
        con.execute('PRAGMA temp_store=FILE')
        con.execute('PRAGMA max_page_count=' + str(MAX_INDEX_BYTES // 4096))
        for statement in SQL_SCHEMA:
            con.execute(statement)
        con.execute('INSERT INTO metadata VALUES (?,?)', ('metadata', _canonical(meta).decode('utf-8')))
        con.commit()
        try:
            stat = source.stat()
            meta['source_stat_declaration'] = {'bytes_at_start': stat.st_size, 'mtime_ns_at_start': stat.st_mtime_ns, 'verified': False}
            with source.open('rb', buffering=0) as handle:
                physical = _Reader(handle, max_compressed_bytes, deadline)
                compressed = source.name.lower().endswith('.gz')
                decoder = gzip.GzipFile(fileobj=physical, mode='rb') if compressed else physical
                lines = _Lines(decoder, physical, max_expanded_bytes, max_row_bytes)
                try:
                    while True:
                        if coverage['physical_rows_seen'] >= max_rows and not (lines.decoder_eof and not lines.buffer):
                            raise _Stop('row_limit')
                        raw_line = lines.next()
                        if raw_line is None:
                            if compressed and physical.bytes_read == 0:
                                raise _Stop('invalid_gzip_header')
                            coverage['stop_reason'] = 'eof'
                            coverage['complete_scan'] = True
                            break
                        coverage['physical_rows_seen'] += 1
                        line = coverage['physical_rows_seen']
                        raw_sha = hashlib.sha256(raw_line).hexdigest()
                        record = json.loads(raw_line.decode('utf-8-sig' if line == 1 else 'utf-8'),
                            object_pairs_hook=scanner._object_pairs, parse_constant=scanner._nonfinite_constant)
                        scanner._validate_shape(record, max_depth=16, max_items=16384, max_string=max_row_bytes)
                        if type(record) is not dict or type(record.get('id')) is not str or not _UUID.fullmatch(record['id']):
                            raise _Stop('invalid_record_id')
                        coverage['parsed_rows'] += 1
                        projection = _project(record)
                        encoded = _canonical(projection)
                        if len(encoded) > MAX_PROJECTION_BYTES:
                            raise _Stop('projection_byte_limit')
                        try:
                            con.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                                (line, record['id'], projection['created_at'], projection['action_type'],
                                 projection['room_id'], projection['message_id'], projection['chat_message_id'],
                                 scanner._hash_record(record), raw_sha, hashlib.sha256(encoded).hexdigest(), encoded.decode('utf-8')))
                        except sqlite3.IntegrityError:
                            coverage['duplicate_ids'] += 1
                            raise _Stop('duplicate_record_id')
                        coverage['indexed_rows'] += 1
                        coverage['invalid_timestamp_rows'] += not projection['time_valid']
                        if line % 1000 == 0:
                            con.commit()
                            if time.monotonic() >= deadline:
                                raise _Stop('time_limit')
                            if on_progress is not None:
                                try:
                                    on_progress({'physical_rows_seen': line, 'indexed_rows': coverage['indexed_rows'],
                                        'compressed_bytes_read': physical.bytes_read, 'expanded_bytes_read': lines.expanded_bytes,
                                        'elapsed_seconds': round(time.monotonic() - started, 3), 'complete_scan': False})
                                except Exception as exc:
                                    meta['callback_error_type'] = type(exc).__name__
                                    raise _Stop('progress_callback_error') from None
                finally:
                    if compressed:
                        decoder.close()
        except (Exception, KeyboardInterrupt) as exc:
            reason = (exc.reason if isinstance(exc, _Stop) else
                'invalid_utf8' if isinstance(exc, UnicodeDecodeError) else
                'duplicate_json_key' if isinstance(exc, scanner._DuplicateKey) else
                'nonfinite_json' if isinstance(exc, scanner._NonfiniteJSON) else
                'invalid_record_structure' if isinstance(exc, (scanner._JSONShape, RecursionError)) else
                'malformed_json' if isinstance(exc, (json.JSONDecodeError, ValueError)) else
                'corrupt_gzip' if isinstance(exc, (gzip.BadGzipFile, zlib.error)) else
                'truncated_gzip' if isinstance(exc, EOFError) else
                'interrupted' if isinstance(exc, KeyboardInterrupt) else
                'index_write_error' if isinstance(exc, sqlite3.Error) else 'io_error')
            coverage['complete_scan'] = False; coverage['stop_reason'] = reason
            if reason in ('invalid_record_id', 'invalid_utf8', 'duplicate_json_key', 'nonfinite_json',
                          'invalid_record_structure', 'malformed_json'):
                coverage['malformed_rows'] += 1
            parsing_error = reason in ('invalid_record_id', 'duplicate_json_key', 'nonfinite_json',
                'invalid_record_structure', 'malformed_json', 'duplicate_record_id', 'invalid_utf8', 'projection_byte_limit')
            problem = {'kind': reason, 'line': coverage['physical_rows_seen'] if parsing_error else coverage['physical_rows_seen'] + 1,
                       'error_type': type(exc).__name__}
            if parsing_error and 'raw_sha' in locals() and coverage['physical_rows_seen']:
                problem['raw_line_sha256'] = raw_sha
            meta['problems'].append(problem)
        if physical is not None:
            coverage.update(compressed_bytes_read=physical.bytes_read,
                expanded_bytes_read=lines.expanded_bytes if lines else 0,
                pending_expanded_bytes=len(lines.buffer) if lines else 0,
                source_eof_observed=physical.eof_observed and bool(lines and lines.decoder_eof))
            coverage['physical_eof_observed'] = physical.eof_observed
            coverage['decoder_eof_observed'] = bool(lines and lines.decoder_eof)
            coverage['gzip_crc_checked'] = bool(lines and lines.decoder_eof) if source.name.lower().endswith('.gz') else None
            meta['observed_source'] = {'sha256': physical.sha.hexdigest(), 'md5': physical.md5.hexdigest(),
                'bytes': physical.bytes_read, 'whole_file_observed': coverage['source_eof_observed'],
                'hash_scope': 'whole_physical_file' if coverage['source_eof_observed'] else 'physical_prefix_read'}
        else:
            meta['observed_source'] = {'sha256': hashlib.sha256(b'').hexdigest(),
                'md5': hashlib.md5(b'', usedforsecurity=False).hexdigest(), 'bytes': 0,
                'whole_file_observed': False, 'hash_scope': 'physical_prefix_read'}
        checks = {}
        if declaration:
            for declared, observed in (('object_bytes', 'bytes'), ('server_md5', 'md5')):
                if declaration.get(declared) is not None:
                    checks[declared] = {'status': 'matching' if coverage['source_eof_observed'] and
                        declaration[declared] == meta['observed_source'][observed] else
                        'conflicting' if coverage['source_eof_observed'] else 'unverified_partial_scan'}
        meta['declaration_comparison'] = checks
        if coverage['complete_scan'] and any(v['status'] == 'conflicting' for v in checks.values()):
            coverage['complete_scan'] = False; coverage['stop_reason'] = 'source_metadata_mismatch'
            meta['problems'].append({'kind': 'source_metadata_mismatch'})
        if coverage['complete_scan'] and not coverage['source_eof_observed']:
            coverage['complete_scan'] = False; coverage['stop_reason'] = 'unverified_eof'
        actual_rows = con.execute('SELECT COUNT(*),SUM(created_at IS NULL) FROM events').fetchone()
        coverage['indexed_rows'] = actual_rows[0]
        coverage['invalid_timestamp_rows'] = actual_rows[1] or 0
        coverage['scanned_file_id_uniqueness_verified'] = coverage['complete_scan']
        meta['state'] = 'complete' if coverage['complete_scan'] else 'partial'
        meta['source_input_fingerprint'] = _hash({'source_path': str(source), 'path_resolution': resolution,
            'observed_source': meta['observed_source'], 'source_metadata_declaration': meta['source_metadata_declaration']})
        if len(_canonical(meta)) > MAX_METADATA_BYTES:
            raise ValueError('Final index metadata exceeds bounds')
        con.execute('UPDATE metadata SET value=? WHERE key=?', (_canonical(meta).decode('utf-8'), 'metadata'))
        con.commit()
        con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    finally:
        con.close()
    digest, size = _file_hash(destination)
    return {**meta, 'artifact': {'path': str(destination), 'file_sha256': digest, 'bytes': size,
        'hash_scope': 'closed SQLite artifact after final metadata transaction/checkpoint'}}


def _query_plan(message_ids, windows, action_types, max_rows):
    _bound(max_rows, 'max_rows', MAX_QUERY_ROWS)
    def identifiers(values, pattern, name, ceiling=MAX_QUERY_ROWS):
        if values is None:
            return None
        if type(values) is not list or not values or len(values) > ceiling or any(type(v) is not str or not pattern.fullmatch(v) for v in values):
            raise ValueError(name + ' requires a nonempty bounded list of exact typed strings')
        if len(values) != len(set(values)):
            raise ValueError('Duplicate query filter values are ambiguous')
        return sorted(values)
    ids = identifiers(message_ids, _UUID, 'message_ids')
    actions = identifiers(action_types, _ACTION, 'action_types', 64)
    canonical_windows = None
    if windows is not None:
        if type(windows) is not list or not 1 <= len(windows) <= 64:
            raise ValueError('Use a nonempty bounded list of room UTC windows')
        canonical_windows = []
        for window in windows:
            required = {'room_id', 'start', 'end_exclusive'}
            if type(window) is not dict or not required <= set(window) or not set(window) <= required | {'id'}:
                raise ValueError('Windows require room_id/start/end_exclusive and optional id only')
            if type(window['room_id']) is not str or not _UUID.fullmatch(window['room_id']):
                raise ValueError('Window room IDs must be exact UUID strings')
            row = {'room_id': window['room_id']}
            for key in ('start', 'end_exclusive'):
                value = window[key]
                if type(value) is not str or not 20 <= len(value) <= 40 or 'T' not in value:
                    raise ValueError('Window times require explicit UTC ISO timestamps')
                try:
                    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0:
                        raise ValueError('UTC required')
                    row[key] = stamp.astimezone(timezone.utc).isoformat(timespec='microseconds')
                except (ValueError, OverflowError) as exc:
                    raise ValueError('Window times require explicit UTC ISO timestamps') from exc
            if row['start'] >= row['end_exclusive']:
                raise ValueError('Windows require a positive half-open span')
            if 'id' in window:
                if type(window['id']) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', window['id']):
                    raise ValueError('Window labels must be bounded identifiers')
                row['id'] = window['id']
            canonical_windows.append(row)
        canonical_windows.sort(key=lambda w: (w['room_id'], w['start'], w['end_exclusive'], w.get('id', '')))
        if len({_hash(w) for w in canonical_windows}) != len(canonical_windows):
            raise ValueError('Duplicate windows are ambiguous')
    return {'message_ids': ids, 'windows': canonical_windows, 'action_types': actions,
            'max_rows': max_rows, 'combination': '(exact data.messageId/data.chatMessageId match OR valid room/UTC-window match); action_types filter applies globally; OR within each list'}


def _validate_projection(record):
    if type(record) is not dict or set(record) != RECORD_KEYS:
        raise ValueError('Unexpected event projection schema')
    scanner._validate_shape(record, max_depth=6, max_items=512, max_string=4096)
    if type(record['id']) is not str or not _UUID.fullmatch(record['id']):
        raise ValueError('Invalid projected event identity')
    fields = record['fields']
    if type(fields) is not dict or set(fields) != set(FIELDS):
        raise ValueError('Unexpected typed event fields')
    for key, field in fields.items():
        if type(field) is not dict or not {'presence', 'type_status'} <= set(field) or not set(field) <= {
            'presence', 'type_status', 'value', 'value_hash', 'utc', 'timezone_policy', 'recognized', 'value_type'}:
            raise ValueError('Unexpected projected field schema')
        if field['presence'] not in ('absent', 'null', 'value') or field['type_status'] not in ('unknown', 'valid', 'invalid'):
            raise ValueError('Invalid projected field status')
        if field['presence'] != 'value' and field['type_status'] != 'unknown':
            raise ValueError('Invalid absence/type combination')
        if field['presence'] == 'value' and field['type_status'] == 'unknown':
            raise ValueError('Measured field cannot have an unknown type status')
        allowed = {'presence', 'type_status'}
        if key == 'data.output' and field['presence'] != 'absent':
            allowed.add('value_type')
            if field.get('value_type') not in ('null', 'object', 'array', 'string', 'boolean', 'number'):
                raise ValueError('Invalid projected output type')
            if (field['presence'] == 'null') != (field['value_type'] == 'null'):
                raise ValueError('Output null/type inconsistency')
            if field['presence'] == 'value' and field['type_status'] != 'valid':
                raise ValueError('Invalid measured output type status')
        elif field['presence'] == 'value' and field['type_status'] == 'valid':
            if key == 'created_at':
                allowed |= {'value_hash', 'utc', 'timezone_policy'}
            elif key in ('data.content', 'data.sessionGoal'):
                allowed.add('value_hash')
            elif key not in ('data', 'data.output'):
                allowed.add('value')
                if key == 'data.actionType':
                    allowed.add('recognized')
        elif key == 'created_at' and field['presence'] == 'value' and 'value_hash' in field:
            allowed.add('value_hash')
        if set(field) != allowed:
            raise ValueError('Projected field carries unsupported payload or missing typed keys')
        if 'value_hash' in field and (type(field['value_hash']) is not str or not _SHA.fullmatch(field['value_hash'])):
            raise ValueError('Invalid projected value hash')
    if fields['data']['type_status'] != 'valid' and any(fields[key]['presence'] != 'absent' for key in fields if key.startswith('data.')):
        raise ValueError('Projected data children exist without a valid data object')
    # Reconstruct only safe typed inputs; text value hashes remain hashed declarations.
    raw = {'id': record['id'], 'data': {}}
    for key in ('event_index', *('data.' + f for f in ID_FIELDS), 'data.actionType', 'data.speakerType', 'data.seconds'):
        field = fields[key]
        if field['type_status'] == 'valid':
            if 'value' not in field:
                raise ValueError('Missing valid projected typed value')
            target = raw if '.' not in key else raw['data']
            name = key.split('.')[-1]
            kind = 'index' if key == 'event_index' else 'action' if key == 'data.actionType' else 'seconds' if key == 'data.seconds' else 'speaker' if key == 'data.speakerType' else 'id'
            target[name] = field['value']
            if _field(target, name, kind) != field:
                raise ValueError('Projected typed value/status mismatch')
        elif 'value' in field:
            raise ValueError('Unmeasured projected field carries a value')
    reconstructed = _project(raw)
    for key in ('event_index', 'action_type', 'message_id', 'chat_message_id', 'computer_use_session_id', 'speaker_id', 'agent_id', 'room_id'):
        if _canonical(record[key]) != _canonical(reconstructed[key]):
            raise ValueError('Flat projection differs from typed fields')
    for flat, field in (('content_hash', 'data.content'), ('session_goal_hash', 'data.sessionGoal')):
        if _canonical(record[flat]) != _canonical(fields[field].get('value_hash')):
            raise ValueError('Projected text hash differs from field hash')
    timestamp = fields['created_at']
    if type(record['time_valid']) is not bool or record['time_valid'] != (timestamp['type_status'] == 'valid') or record['created_at'] != timestamp.get('utc'):
        raise ValueError('Projected time differs from typed timestamp')
    if record['time_valid']:
        if timestamp.get('timezone_policy') not in ('explicit_offset_to_utc', 'export_naive_assumed_utc') or 'value_hash' not in timestamp:
            raise ValueError('Missing timestamp normalization declaration')
        try:
            stamp = datetime.fromisoformat(record['created_at'])
            if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0 or stamp.isoformat(timespec='microseconds') != record['created_at']:
                raise ValueError('Not canonical UTC')
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError('Invalid canonical projected UTC timestamp') from exc
    # Actor recomputation preserves invalid selected fields (not reconstructed above).
    speaker, agent, action = record['speaker_id'], record['agent_id'], record['action_type']
    actor = actor_field = None; status = 'unrecognized_action'
    if speaker is not None and agent is not None and speaker != agent:
        status = 'conflicting_fields'
    elif action in ACTION_TYPES:
        candidate = 'data.speakerId' if action in ('AGENT_TALK', 'USER_TALK') else 'data.agentId'
        actor = fields[candidate].get('value')
        status = 'selected_valid' if actor is not None else 'invalid_field' if fields[candidate]['type_status'] == 'invalid' else 'unknown'
        if actor is not None:
            actor_field = candidate
    if _canonical([record['actor_id'], record['actor_field'], record['actor_status']]) != _canonical([actor, actor_field, status]):
        raise ValueError('Projected actor differs from attributed typed field')
    if _canonical(record['seconds']) != _canonical(fields['data.seconds'].get('value')) or type(record['raw_provider_output_present']) is not bool or record['raw_provider_output_present'] != (fields['data.output']['presence'] == 'value'):
        raise ValueError('Projected duration/output flag mismatch')


def _validate_build_metadata(meta):
    """Validate the finite finalized scan contract, not upstream source semantics."""
    coverage = meta.get('coverage')
    limits = meta.get('limits')
    observed = meta.get('observed_source')
    if type(coverage) is not dict or type(limits) is not dict or type(observed) is not dict:
        raise ValueError('Missing typed build coverage/limits/source observations')
    for key, ceiling in (('max_rows', MAX_ROWS), ('max_compressed_bytes', MAX_COMPRESSED_BYTES),
        ('max_expanded_bytes', MAX_EXPANDED_BYTES), ('max_row_bytes', MAX_ROW_BYTES), ('max_seconds', MAX_SECONDS)):
        _bound(limits.get(key), key, ceiling)
    if limits.get('max_physical_read_request') != READ_CHUNK or limits.get('max_json_depth') != 16 or limits.get('max_row_json_items') != 16384 or limits.get('max_index_bytes') != MAX_INDEX_BYTES:
        raise ValueError('Unsupported build instrument bounds')
    for key in ('physical_rows_seen', 'parsed_rows', 'indexed_rows', 'malformed_rows', 'duplicate_ids', 'invalid_timestamp_rows'):
        if type(coverage.get(key)) is not int or not 0 <= coverage[key] <= limits['max_rows']:
            raise ValueError('Invalid strict build row counter')
    if not coverage['indexed_rows'] <= coverage['parsed_rows'] <= coverage['physical_rows_seen'] or coverage['invalid_timestamp_rows'] > coverage['indexed_rows']:
        raise ValueError('Inconsistent build row counters')
    for key in ('complete_scan', 'source_eof_observed', 'physical_eof_observed', 'decoder_eof_observed',
                'scanned_file_id_uniqueness_verified', 'global_database_id_uniqueness_verified'):
        if type(coverage.get(key)) is not bool:
            raise ValueError('Strict boolean build coverage required')
    if coverage['global_database_id_uniqueness_verified'] or coverage['scanned_file_id_uniqueness_verified'] != coverage['complete_scan']:
        raise ValueError('Unsupported uniqueness scope')
    if coverage['source_eof_observed'] != (coverage['physical_eof_observed'] and coverage['decoder_eof_observed']):
        raise ValueError('Inconsistent observed EOF flags')
    if coverage.get('stop_reason') not in STOP_REASONS or meta['state'] != ('complete' if coverage['complete_scan'] else 'partial'):
        raise ValueError('Invalid finalized stop reason/state')
    if coverage['complete_scan'] and (coverage['stop_reason'] != 'eof' or not coverage['source_eof_observed'] or
        coverage['indexed_rows'] != coverage['physical_rows_seen'] or coverage['malformed_rows'] or coverage['duplicate_ids']):
        raise ValueError('Complete scan claim contradicts observed coverage')
    if not coverage['complete_scan'] and coverage['stop_reason'] == 'eof':
        raise ValueError('Partial scan requires an explicit failed/bounded stop')
    for key, bound in (('compressed_bytes_read', 'max_compressed_bytes'), ('expanded_bytes_read', 'max_expanded_bytes')):
        if type(coverage.get(key)) is not int or not 0 <= coverage[key] <= limits[bound]:
            raise ValueError('Invalid strict build byte counter')
    if type(coverage.get('pending_expanded_bytes')) is not int or not 0 <= coverage['pending_expanded_bytes'] <= limits['max_row_bytes']:
        raise ValueError('Invalid pending expanded buffer counter')
    if (type(observed.get('bytes')) is not int or observed['bytes'] != coverage['compressed_bytes_read'] or
        type(observed.get('whole_file_observed')) is not bool or observed['whole_file_observed'] != coverage['source_eof_observed'] or
        type(observed.get('sha256')) is not str or not _SHA.fullmatch(observed['sha256']) or
        type(observed.get('md5')) is not str or not re.fullmatch(r'[0-9a-f]{32}', observed['md5']) or
        observed.get('hash_scope') != ('whole_physical_file' if coverage['source_eof_observed'] else 'physical_prefix_read')):
        raise ValueError('Invalid observed source byte/hash scope')
    source_path = meta.get('source_path')
    if type(source_path) is not str or not 0 < len(source_path.encode('utf-8')) <= 4096 or not Path(source_path).is_absolute() or meta.get('path_resolution') not in ('filesystem_resolved', 'lexical_absolute_virtual_filesystem'):
        raise ValueError('Invalid declared source path/resolution')
    gzip_source = source_path.lower().endswith('.jsonl.gz')
    if not source_path.lower().endswith(('.jsonl', '.jsonl.gz')) or (gzip_source and
        (type(coverage.get('gzip_crc_checked')) is not bool or coverage['gzip_crc_checked'] != coverage['decoder_eof_observed'])) or (
        not gzip_source and coverage.get('gzip_crc_checked') is not None):
        raise ValueError('Invalid gzip validation scope')
    declaration = meta['source_metadata_declaration']['value']
    comparisons = {}
    if declaration:
        for declared, actual in (('object_bytes', 'bytes'), ('server_md5', 'md5')):
            if declaration.get(declared) is not None:
                comparisons[declared] = {'status': 'matching' if coverage['source_eof_observed'] and declaration[declared] == observed[actual]
                    else 'conflicting' if coverage['source_eof_observed'] else 'unverified_partial_scan'}
    if meta.get('declaration_comparison') != comparisons or coverage['complete_scan'] and any(v['status'] == 'conflicting' for v in comparisons.values()):
        raise ValueError('Invalid source declaration comparison')


def read_event_index(path, *, expected_file_sha256, message_ids=None, windows=None,
                     action_types=None, max_rows=256):
    """Authenticate an index and return bounded projections; no raw source reread."""
    if type(expected_file_sha256) is not str or not _SHA.fullmatch(expected_file_sha256):
        raise ValueError('Exact expected index file SHA256 is mandatory')
    plan = _query_plan(message_ids, windows, action_types, max_rows)
    index_path, resolution = scanner.resolve_source_path(path)
    if not index_path.is_file():
        raise ValueError('Existing SQLite index required')
    digest, size = _file_hash(index_path)
    if digest != expected_file_sha256:
        raise ValueError('Index artifact SHA256 does not match expected bytes')
    con = sqlite3.connect(index_path.as_uri() + '?mode=ro', uri=True)
    try:
        con.execute('PRAGMA query_only=ON')
        con.execute('PRAGMA trusted_schema=OFF')
        con.execute('PRAGMA cache_size=-4096')
        actual_schema = con.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name").fetchall()
        if sorted(row[0] for row in actual_schema) != sorted(SQL_SCHEMA):
            raise ValueError('Unexpected index database schema')
        rows = con.execute('SELECT key,length(value) FROM metadata').fetchall()
        if len(rows) != 1 or rows[0][0] != 'metadata':
            raise ValueError('Unexpected index metadata keys')
        if rows[0][1] > MAX_METADATA_BYTES:
            raise ValueError('Index metadata exceeds bounds')
        meta = json.loads(con.execute('SELECT value FROM metadata WHERE key=?', ('metadata',)).fetchone()[0],
            object_pairs_hook=scanner._object_pairs, parse_constant=scanner._nonfinite_constant)
        scanner._validate_shape(meta, max_depth=12, max_items=4096, max_string=8192)
        if (meta.get('kind') != 'bounded_event_source_index' or meta.get('schema_version') != SCHEMA_VERSION or
            meta.get('instrument_version') != INDEX_VERSION or meta.get('state') not in ('complete', 'partial') or
            meta.get('table') != 'events' or type(meta.get('model_calls')) is not int or meta.get('model_calls') != 0 or meta.get('raw_payloads_persisted') is not False or
            meta.get('implementation_hashes') != implementation_hashes()):
            raise ValueError('Index version/state/implementation provenance mismatch')
        if meta.get('source_metadata_declaration', {}).get('verified') is not False or _metadata(meta['source_metadata_declaration'].get('value')) != meta['source_metadata_declaration'].get('value'):
            raise ValueError('Invalid source metadata declaration')
        _validate_build_metadata(meta)
        coverage = meta['coverage']
        if type(coverage.get('complete_scan')) is not bool or type(coverage.get('indexed_rows')) is not int or not 0 <= coverage['indexed_rows'] <= MAX_ROWS:
            raise ValueError('Invalid index build coverage')
        if con.execute('SELECT COUNT(*) FROM events').fetchone()[0] != coverage['indexed_rows']:
            raise ValueError('Index row count does not match finalized coverage')
        fingerprint = _hash({key: meta[key] for key in ('source_path', 'path_resolution', 'observed_source', 'source_metadata_declaration')})
        if fingerprint != meta.get('source_input_fingerprint'):
            raise ValueError('Index source fingerprint mismatch')
        clauses, parameters, selections = [], [], []
        if plan['message_ids'] is not None:
            placeholders = ','.join('?' for _ in plan['message_ids'])
            selections.append('(message_id IN (' + placeholders + ') OR chat_message_id IN (' + placeholders + '))')
            parameters.extend(plan['message_ids'] * 2)
        if plan['windows'] is not None:
            selections.append('(' + ' OR '.join('(room_id=? AND created_at>=? AND created_at<?)' for _ in plan['windows']) + ')')
            for w in plan['windows']:
                parameters.extend((w['room_id'], w['start'], w['end_exclusive']))
        if selections:
            clauses.append('(' + ' OR '.join(selections) + ')')
        if plan['action_types'] is not None:
            clauses.append('action_type IN (' + ','.join('?' for _ in plan['action_types']) + ')')
            parameters.extend(plan['action_types'])
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        if len(parameters) + 1 > con.getlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER):
            raise ValueError('Typed query exceeds this SQLite backend bind limit')
        count = con.execute('SELECT COUNT(*) FROM events' + where, parameters).fetchone()[0]
        records, retained = [], 0
        cursor = con.execute('SELECT line,id,created_at,action_type,room_id,message_id,chat_message_id,record_sha256,raw_line_sha256,projection_sha256,projection_json FROM events' + where + ' ORDER BY line LIMIT ?', parameters + [max_rows])
        for row in cursor:
            if type(row[10]) is not str or len(row[10].encode('utf-8')) > MAX_PROJECTION_BYTES:
                raise ValueError('Indexed projection exceeds row bound')
            record = json.loads(row[10], object_pairs_hook=scanner._object_pairs, parse_constant=scanner._nonfinite_constant)
            _validate_projection(record)
            projection_sha = _hash(record)
            if projection_sha != row[9] or tuple(record[k] for k in ('id', 'created_at', 'action_type', 'room_id', 'message_id', 'chat_message_id')) != row[1:7]:
                raise ValueError('Stored selection columns/projection hash mismatch')
            if type(row[0]) is not int or row[0] < 1 or any(type(h) is not str or not _SHA.fullmatch(h) for h in row[7:10]):
                raise ValueError('Invalid indexed source coordinate/hash')
            entry = {'record': record, 'source': {'path': meta['source_path'], 'table': 'events',
                'line': row[0], 'record_sha256': row[7], 'raw_line_sha256': row[8]}, 'projection_sha256': projection_sha}
            retained += len(_canonical(entry))
            if retained > MAX_OUTPUT_BYTES:
                raise ValueError('Projected query exceeds output byte bound')
            records.append(entry)
    except sqlite3.Error as exc:
        raise ValueError('Index database cannot be read under the supported schema') from exc
    finally:
        con.close()
    after_digest, after_size = _file_hash(index_path)
    if after_digest != digest or after_size != size:
        raise ValueError('Index artifact changed during query')
    return {'kind': 'indexed_event_source_query', 'schema_version': SCHEMA_VERSION,
        'instrument_version': INDEX_VERSION, 'model_calls': 0, 'read_only': True,
        'index': {'path': str(index_path), 'path_resolution': resolution,
            'expected_file_sha256': expected_file_sha256, 'read_file_sha256': digest,
            'post_query_file_sha256': after_digest, 'file_hash_authenticated': True,
            'bytes': size, 'implementation_hashes': implementation_hashes(),
            'internal_metadata_sha256': _hash(meta)},
        'query': plan, 'records': records, 'source_input_fingerprint': meta['source_input_fingerprint'],
        'source_metadata_declaration': meta['source_metadata_declaration'],
        'observed_source': meta['observed_source'],
        'coverage': {'build_scan': coverage, 'query_complete': count <= max_rows,
            'truncated': count > max_rows, 'matched_rows': count, 'returned_rows': len(records),
            'scope': 'Filters over finalized indexed rows only; partial builds and unmatched/missing room or time fields cannot establish source/global absence.'},
        'source_pin_scope': 'Index-authenticated scan declarations; original raw JSONL bytes are not freshly reread by this query.',
        'limitations': meta['limitations']}
