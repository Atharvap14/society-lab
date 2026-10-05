"""Temporary, payload-private fixtures for bounded event-index contracts."""
from __future__ import annotations

import contextlib
import gzip
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from swarm_lab import event_source_index as index


def uid(n):
    return f'00000000-0000-0000-0000-{n:012x}'


def event(n, *, timestamp='2026-04-18T18:00:00Z', action='AGENT_TALK', data=None):
    body = {'actionType': action, 'roomId': uid(10), 'speakerId': uid(20),
            'messageId': uid(100 + n), 'content': 'private content', 'output': {'secret': 'private provider'}}
    if data is not None:
        body = data
    return {'id': uid(n), 'created_at': timestamp, 'event_index': n, 'data': body}


def encoded(rows, *, terminator=b'\n'):
    return b''.join(index._canonical(r) + terminator for r in rows)


class EventSourceIndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.counter = 0

    def source(self, payload, compressed=False):
        self.counter += 1
        path = self.directory / (f'events{self.counter}.jsonl' + ('.gz' if compressed else ''))
        path.write_bytes(gzip.compress(payload, mtime=0) if compressed else payload)
        return path

    def build(self, payload=None, compressed=False, **kwargs):
        source = self.source(encoded([event(1), event(2)]) if payload is None else payload, compressed)
        destination = self.directory / f'index{self.counter}.sqlite3'
        meta = index.build_event_index(source, destination, **kwargs)
        return source, destination, meta

    def read(self, path, meta, **kwargs):
        return index.read_event_index(path, expected_file_sha256=meta['artifact']['file_sha256'], **kwargs)

    def rehash(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def mutate(self, path, statement, parameters=()):
        with contextlib.closing(sqlite3.connect(path)) as con:
            con.execute(statement, parameters)
            con.commit()
        return self.rehash(path)

    def test_plain_gzip_full_scan_and_original_hashes(self):
        rows = [event(1), event(2, timestamp='2026-04-18 18:01:00.123456')]
        payload = encoded(rows, terminator=b'\r\n')
        for compressed in (False, True):
            with self.subTest(compressed=compressed):
                source, path, meta = self.build(payload, compressed)
                self.assertTrue(meta['coverage']['complete_scan'])
                self.assertEqual(meta['coverage']['stop_reason'], 'eof')
                self.assertEqual(meta['state'], 'complete')
                self.assertEqual(meta['observed_source']['sha256'], self.rehash(source))
                self.assertEqual(meta['observed_source']['md5'], hashlib.md5(source.read_bytes(), usedforsecurity=False).hexdigest())
                self.assertEqual(meta['observed_source']['bytes'], source.stat().st_size)
                self.assertEqual(meta['artifact']['file_sha256'], self.rehash(path))
                packet = self.read(path, meta)
                self.assertTrue(packet['read_only']); self.assertEqual(packet['model_calls'], 0)
                self.assertTrue(packet['index']['file_hash_authenticated'])
                self.assertEqual(packet['index']['read_file_sha256'], meta['artifact']['file_sha256'])
                self.assertEqual(packet['coverage']['matched_rows'], 2)
                self.assertTrue(packet['coverage']['query_complete'])
                for i, entry in enumerate(packet['records']):
                    self.assertEqual(entry['source']['line'], i + 1)
                    self.assertEqual(entry['source']['record_sha256'], index._hash(rows[i]))
                    self.assertEqual(entry['source']['raw_line_sha256'], hashlib.sha256(payload.splitlines(keepends=True)[i]).hexdigest())
                    self.assertEqual(entry['projection_sha256'], index._hash(entry['record']))
                self.assertEqual(packet['records'][1]['record']['fields']['created_at']['timezone_policy'], 'export_naive_assumed_utc')

    def test_no_payload_in_artifact_packet_metadata_or_standard_streams(self):
        secret = 'DO_NOT_PERSIST_PROVIDER_COMMAND_PASSWORD_83742'
        row = event(1); row['data'].update(content=secret, sessionGoal=secret, output={'command': secret}, error=secret)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            _, path, meta = self.build(encoded([row]))
            packet = self.read(path, meta)
        self.assertEqual(out.getvalue(), ''); self.assertEqual(err.getvalue(), '')
        self.assertNotIn(secret.encode(), path.read_bytes())
        self.assertNotIn(secret, json.dumps(meta)); self.assertNotIn(secret, json.dumps(packet))
        record = packet['records'][0]['record']
        self.assertEqual(record['content_hash'], index._hash(secret))
        self.assertNotEqual(record['content_hash'], hashlib.sha256(secret.encode()).hexdigest())
        self.assertTrue(record['raw_provider_output_present'])

    def test_exclusive_destination_refuses_replacement_even_empty_file(self):
        source = self.source(encoded([event(1)]))
        destination = self.directory / 'old.sqlite3'; destination.write_bytes(b'')
        with self.assertRaises(FileExistsError):
            index.build_event_index(source, destination)
        self.assertEqual(destination.read_bytes(), b'')
        _, path, meta = self.build()
        before = path.read_bytes()
        with self.assertRaises(FileExistsError):
            index.build_event_index(source, path)
        self.assertEqual(path.read_bytes(), before)

    def test_hash_is_mandatory_and_checked_before_sqlite_open(self):
        _, path, meta = self.build()
        for digest in (None, True, 'bad', 'A' * 64):
            with self.subTest(digest=digest), self.assertRaises(ValueError):
                index.read_event_index(path, expected_file_sha256=digest)
        with patch.object(index.sqlite3, 'connect') as connect:
            with self.assertRaises(ValueError):
                index.read_event_index(path, expected_file_sha256='0' * 64)
            connect.assert_not_called()
        self.mutate(path, 'UPDATE events SET action_type=? WHERE line=?', ('WAIT', 1))
        with self.assertRaises(ValueError):self.read(path, meta)

    def test_changed_source_is_not_falsely_called_freshly_reread(self):
        source, path, meta = self.build()
        source.write_bytes(encoded([event(99)]))
        packet = self.read(path, meta)
        self.assertEqual(packet['records'][0]['record']['id'], uid(1))
        self.assertIn('not freshly reread', packet['source_pin_scope'])

    def test_query_union_global_action_and_half_open_room_filters(self):
        rows = [event(1), event(2, timestamp='2026-04-18T19:00:00Z'),
            event(3, timestamp='2026-04-17T00:00:00Z'),
            event(4, data={'actionType': 'WAIT', 'seconds': 30, 'agentId': uid(20)}),
            event(5, action='PAUSE'), event(6, data={'actionType': 'AGENT_TALK', 'chatMessageId': uid(500)})]
        _, path, meta = self.build(encoded(rows))
        windows = [{'id': 'window-selected', 'room_id': uid(10), 'start': '2026-04-18T18:00:00Z', 'end_exclusive': '2026-04-18T19:00:00Z'}]
        packet = self.read(path, meta, message_ids=[uid(103), uid(500)], windows=windows, action_types=['AGENT_TALK'])
        self.assertEqual([r['record']['id'] for r in packet['records']], [uid(1), uid(3), uid(6)])
        self.assertIn('OR valid room', packet['query']['combination'])
        self.assertNotIn(uid(4), [r['record']['id'] for r in packet['records']])
        self.assertIn('missing room', packet['coverage']['scope'])

    def test_truncation_distinct_from_partial_source_build(self):
        _, path, meta = self.build()
        packet = self.read(path, meta, max_rows=1)
        self.assertTrue(packet['coverage']['build_scan']['complete_scan'])
        self.assertFalse(packet['coverage']['query_complete']); self.assertTrue(packet['coverage']['truncated'])
        self.assertEqual(packet['coverage']['matched_rows'], 2); self.assertEqual(packet['coverage']['returned_rows'], 1)
        self.assertEqual([e['source']['line'] for e in packet['records']], [1])
        _, path, meta = self.build(max_rows=1)
        packet = self.read(path, meta)
        self.assertFalse(packet['coverage']['build_scan']['complete_scan'])
        self.assertTrue(packet['coverage']['query_complete'])

    def test_uuid_order_and_unordered_timestamps_never_stop_scan(self):
        rows = [event(1, timestamp='2026-09-01T00:00:00Z'), event(2), event(3, timestamp='2025-04-01T00:00:00Z')]
        _, path, meta = self.build(encoded(rows))
        packet = self.read(path, meta, windows=[{'room_id': uid(10), 'start': '2026-04-18T18:00:00Z', 'end_exclusive': '2026-04-18T18:01:00Z'}])
        self.assertEqual([r['record']['id'] for r in packet['records']], [uid(2)])
        self.assertEqual(meta['coverage']['indexed_rows'], 3)

    def test_invalid_optional_fields_preserve_status_without_raw_values(self):
        row = event(1, timestamp='invalid source text', data={'actionType': 'AGENT_TALK', 'roomId': 'bad room',
            'speakerId': 42, 'messageId': False, 'seconds': True, 'content': ['not text'], 'output': None})
        row['event_index'] = True
        _, path, meta = self.build(encoded([row]))
        record = self.read(path, meta)['records'][0]['record']
        self.assertFalse(record['time_valid']); self.assertIsNone(record['created_at'])
        self.assertIsNone(record['event_index']); self.assertIsNone(record['seconds'])
        self.assertEqual(record['actor_status'], 'invalid_field')
        self.assertEqual(record['fields']['data.messageId']['type_status'], 'invalid')
        self.assertEqual(record['fields']['data.content']['type_status'], 'invalid')
        self.assertEqual(record['fields']['data.output']['presence'], 'null')
        self.assertIsNone(record['content_hash'])
        self.assertNotIn('bad room', path.read_bytes().decode('latin1'))

    def test_actor_attribution_conflicts_and_no_alias_fallback(self):
        rows = [event(1, data={'actionType': 'AGENT_TALK', 'speakerId': uid(20), 'agentId': uid(21)}),
            event(2, data={'actionType': 'AGENT_TALK', 'agentId': uid(20)}),
            event(3, data={'actionType': 'START_USING_COMPUTER', 'agentId': uid(20), 'computerUseSessionId': uid(30)}),
            event(4, data={'actionType': 'FUTURE_ACTION', 'agentId': uid(20)})]
        _, path, meta = self.build(encoded(rows))
        records = [e['record'] for e in self.read(path, meta)['records']]
        self.assertEqual(records[0]['actor_status'], 'conflicting_fields'); self.assertIsNone(records[0]['actor_id'])
        self.assertIsNone(records[1]['actor_id']); self.assertEqual(records[1]['actor_status'], 'unknown')
        self.assertEqual(records[2]['actor_id'], uid(20)); self.assertEqual(records[2]['actor_field'], 'data.agentId')
        self.assertEqual(records[3]['action_type'], 'FUTURE_ACTION'); self.assertIsNone(records[3]['actor_id'])
        self.assertFalse(records[3]['fields']['data.actionType']['recognized'])

    def test_missing_null_data_and_timestamps_are_indexed_unknown(self):
        rows = [{'id': uid(1)}, {'id': uid(2), 'created_at': None, 'data': None}, {'id': uid(3), 'data': []}]
        _, path, meta = self.build(encoded(rows))
        records = [e['record'] for e in self.read(path, meta)['records']]
        self.assertEqual([r['fields']['data']['presence'] for r in records], ['absent', 'null', 'value'])
        self.assertEqual(records[2]['fields']['data']['type_status'], 'invalid')
        self.assertTrue(meta['coverage']['complete_scan']); self.assertEqual(meta['coverage']['invalid_timestamp_rows'], 3)

    def test_offset_timestamp_normalization_and_strict_query_utc(self):
        _, path, meta = self.build(encoded([event(1, timestamp='2026-04-18T20:00:00+02:00')]))
        record = self.read(path, meta)['records'][0]['record']
        self.assertEqual(record['created_at'], '2026-04-18T18:00:00.000000+00:00')
        self.assertEqual(record['fields']['created_at']['value_hash'], index._hash('2026-04-18T20:00:00+02:00'))
        self.assertEqual(record['fields']['created_at']['timezone_policy'], 'explicit_offset_to_utc')
        for start in ('2026-04-18T18:00:00', '2026-04-18T20:00:00+02:00', True):
            with self.assertRaises(ValueError):self.read(path, meta, windows=[{'room_id': uid(10), 'start': start, 'end_exclusive': '2026-04-18T21:00:00Z'}])

    def test_duplicate_ids_finalize_partial_without_discard_claim(self):
        _, path, meta = self.build(encoded([event(1), event(1), event(2)]))
        self.assertEqual(meta['coverage']['stop_reason'], 'duplicate_record_id')
        self.assertEqual(meta['coverage']['duplicate_ids'], 1)
        self.assertEqual(meta['coverage']['indexed_rows'], 1); self.assertEqual(meta['coverage']['parsed_rows'], 2)
        self.assertEqual(meta['state'], 'partial'); self.assertFalse(meta['coverage']['complete_scan'])
        packet = self.read(path, meta)
        self.assertFalse(packet['coverage']['build_scan']['scanned_file_id_uniqueness_verified'])
        self.assertEqual(packet['records'][0]['source']['line'], 1)

    def test_malformed_nonfinite_duplicate_key_and_structure_errors_are_partial(self):
        cases = [(b'{bad secret source\n', 'malformed_json'),
            (b'{"id":"' + uid(2).encode() + b'","data":{"x":NaN}}\n', 'nonfinite_json'),
            (b'{"id":"' + uid(2).encode() + b'","x":1e999}\n', 'nonfinite_json'),
            (b'{"id":"' + uid(2).encode() + b'","data":{"x":1,"x":2}}\n', 'duplicate_json_key'),
            (b'[]\n', 'invalid_record_id'), (b'{"id":"non-uuid"}\n', 'invalid_record_id'),
            (b'{"id":"' + uid(2).encode() + b'","x":"\xff"}\n', 'invalid_utf8'),
            (index._canonical({'id': uid(2), 'x': [[[[]]]]}) + b'\n', 'depth fixture')]
        cases.pop()
        deep = {'id': uid(2), 'x': []}; value = deep['x']
        for _ in range(20):value.append([]); value = value[0]
        cases.append((index._canonical(deep) + b'\n', 'invalid_record_structure'))
        for suffix, expected in cases:
            with self.subTest(expected=expected):
                _, path, meta = self.build(encoded([event(1)]) + suffix)
                self.assertEqual(meta['coverage']['stop_reason'], expected)
                self.assertFalse(meta['coverage']['complete_scan'])
                self.assertEqual(meta['coverage']['indexed_rows'], 1)
                self.assertEqual(meta['problems'][0]['line'], 2)
                self.assertEqual(len(self.read(path, meta)['records']), 1)
                self.assertNotIn('secret source', json.dumps(meta))

    def test_corrupt_and_truncated_gzip_never_complete(self):
        for mode in ('crc', 'truncated', 'empty', 'header'):
            source = self.source(encoded([event(1)]), compressed=True)
            raw = source.read_bytes()
            source.write_bytes(raw[:-4] if mode == 'truncated' else raw[:-8] + b'\x00' * 8 if mode == 'crc' else b'' if mode == 'empty' else b'notgzip')
            path = self.directory / f'damaged{self.counter}.sqlite3'
            meta = index.build_event_index(source, path)
            self.assertFalse(meta['coverage']['complete_scan'])
            self.assertIn(meta['coverage']['stop_reason'], ('corrupt_gzip', 'truncated_gzip', 'invalid_gzip_header'))
            self.assertFalse(self.read(path, meta)['coverage']['build_scan']['complete_scan'])

    def test_bounds_are_strict_positive_nonbool_and_preflight_no_artifact(self):
        source = self.source(encoded([event(1)])); path = self.directory / 'invalid.sqlite3'
        for key in ('max_rows', 'max_compressed_bytes', 'max_expanded_bytes', 'max_row_bytes', 'max_seconds'):
            for value in (True, False, 0, -1, 1.5):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):index.build_event_index(source, path, **{key: value})
        self.assertFalse(path.exists())
        for metadata in ({'object_bytes': True}, {'server_md5': 'bad'}, {'unsupported': 'x'}):
            with self.assertRaises(ValueError):index.build_event_index(source, path, source_metadata=metadata)
        with self.assertRaises(ValueError):index.build_event_index(source, path, on_progress='execute this')

    def test_compressed_expanded_and_row_caps_preserve_incomplete_scope(self):
        payload = encoded([event(1)])
        for compressed in (False, True):
            for kwargs, reason in (({'max_compressed_bytes': 5}, 'compressed_byte_limit'),
                ({'max_expanded_bytes': 32}, 'expanded_byte_limit'), ({'max_row_bytes': 32}, 'row_byte_limit')):
                _, path, meta = self.build(payload, compressed, **kwargs)
                self.assertEqual(meta['coverage']['stop_reason'], reason)
                self.assertFalse(meta['coverage']['complete_scan']); self.read(path, meta)
                self.assertLessEqual(meta['coverage']['compressed_bytes_read'], kwargs.get('max_compressed_bytes', index.MAX_COMPRESSED_BYTES))
                self.assertLessEqual(meta['coverage']['expanded_bytes_read'], kwargs.get('max_expanded_bytes', index.MAX_EXPANDED_BYTES))

    def test_exact_row_byte_and_file_byte_caps_do_not_fabricate_eof(self):
        for compressed in (False, True):
            source = self.source(encoded([event(1)]), compressed)
            path = self.directory / f'exact{self.counter}.sqlite3'
            meta = index.build_event_index(source, path, max_compressed_bytes=source.stat().st_size)
            self.assertFalse(meta['coverage']['complete_scan']); self.assertEqual(meta['coverage']['stop_reason'], 'compressed_byte_limit')
        _, _, meta = self.build(encoded([event(1)]), max_rows=1)
        self.assertEqual(meta['coverage']['stop_reason'], 'row_limit')
        _, _, meta = self.build(index._canonical(event(1)), max_rows=1)
        self.assertTrue(meta['coverage']['complete_scan'])

    def test_empty_plain_and_valid_empty_gzip_complete(self):
        for compressed in (False, True):
            _, path, meta = self.build(b'', compressed)
            self.assertTrue(meta['coverage']['complete_scan']); self.assertEqual(self.read(path, meta)['records'], [])

    def test_time_budget_stop_and_interruption_return_durable_partial(self):
        source = self.source(encoded([event(1)])); path = self.directory / 'budget.sqlite3'
        with patch.object(index.time, 'monotonic', side_effect=[0, 2]):
            meta = index.build_event_index(source, path, max_seconds=1)
        self.assertEqual(meta['coverage']['stop_reason'], 'time_limit'); self.assertFalse(meta['coverage']['complete_scan'])
        self.read(path, meta)
        path2 = self.directory / 'interrupted.sqlite3'
        with patch.object(index._Lines, 'next', side_effect=KeyboardInterrupt):
            meta2 = index.build_event_index(source, path2)
        self.assertEqual(meta2['coverage']['stop_reason'], 'interrupted'); self.read(path2, meta2)

    def test_progress_callback_only_counters_and_errors_never_payload(self):
        rows = [event(i) for i in range(1, 1002)]; seen = []
        def progress(value):
            seen.append(value)
            raise RuntimeError('DO_NOT_LEAK_CALLBACK_SECRET')
        _, path, meta = self.build(encoded(rows), on_progress=progress)
        self.assertEqual(meta['coverage']['stop_reason'], 'progress_callback_error')
        self.assertEqual(meta['coverage']['indexed_rows'], 1000)
        self.assertEqual(set(seen[0]), {'physical_rows_seen', 'indexed_rows', 'compressed_bytes_read', 'expanded_bytes_read', 'elapsed_seconds', 'complete_scan'})
        self.assertNotIn('DO_NOT_LEAK', json.dumps(meta)); self.assertEqual(len(self.read(path, meta, max_rows=15000)['records']), 1000)

    def test_physical_reads_are_unbuffered_bounded_and_bomb_expansion_limited(self):
        row = event(1); row['data']['output'] = {'secret': 'x' * 250000}
        source = self.source(encoded([row]), compressed=True); path = self.directory / 'reads.sqlite3'
        original = Path.open; requests = []; buffers = []
        class Reader:
            def __init__(self, handle):self.handle = handle
            def __enter__(self):return self
            def __exit__(self, *args):return self.handle.__exit__(*args)
            def read(self, count):
                requests.append(count); self.assert_count(count); return self.handle.read(count)
            def assert_count(self, count):
                if not 0 < count <= 65536:raise AssertionError('Unbounded physical read')
        def opened(p, *args, **kwargs):
            handle = original(p, *args, **kwargs)
            if p == source and args and args[0] == 'rb':
                buffers.append(kwargs.get('buffering')); return Reader(handle)
            return handle
        with patch.object(Path, 'open', new=opened):
            meta = index.build_event_index(source, path, max_expanded_bytes=128)
        self.assertEqual(meta['coverage']['stop_reason'], 'expanded_byte_limit')
        self.assertEqual(buffers, [0]); self.assertTrue(requests); self.assertLessEqual(meta['coverage']['expanded_bytes_read'], 128)

    def test_metadata_matching_and_conflict_use_actual_eof_only(self):
        source = self.source(encoded([event(1)]), compressed=True)
        declaration = {'object_bytes': source.stat().st_size, 'server_md5': hashlib.md5(source.read_bytes(), usedforsecurity=False).hexdigest(), 'generation': '123'}
        path = self.directory / 'declared.sqlite3'
        meta = index.build_event_index(source, path, source_metadata=declaration)
        self.assertTrue(meta['coverage']['complete_scan']); self.assertFalse(meta['source_metadata_declaration']['verified'])
        self.assertTrue(all(c['status'] == 'matching' for c in meta['declaration_comparison'].values()))
        path2 = self.directory / 'mismatch.sqlite3'
        bad = dict(declaration, server_md5='0' * 32)
        meta2 = index.build_event_index(source, path2, source_metadata=bad)
        self.assertEqual(meta2['coverage']['stop_reason'], 'source_metadata_mismatch')
        self.assertTrue(meta2['coverage']['source_eof_observed']); self.assertFalse(meta2['coverage']['complete_scan'])
        self.read(path2, meta2)
        path3 = self.directory / 'partial_declared.sqlite3'
        meta3 = index.build_event_index(source, path3, source_metadata=declaration, max_rows=1)
        self.assertTrue(all(c['status'] == 'unverified_partial_scan' for c in meta3['declaration_comparison'].values()))

    def test_virtual_volume_fallback_declared_and_other_errors_propagate(self):
        source = self.source(encoded([event(1)])); path = self.directory / 'virtual.sqlite3'
        error = OSError('Unsupported final path'); error.winerror = 1005
        with patch.object(Path, 'resolve', side_effect=error):
            meta = index.build_event_index(source, path)
            packet = self.read(path, meta)
        self.assertEqual(meta['path_resolution'], 'lexical_absolute_virtual_filesystem')
        self.assertEqual(packet['index']['path_resolution'], 'lexical_absolute_virtual_filesystem')
        denied = OSError('Denied'); denied.winerror = 5
        with patch.object(Path, 'resolve', side_effect=denied), self.assertRaises(OSError):
            index.build_event_index(source, self.directory / 'denied.sqlite3')

    def test_query_typed_filters_reject_sql_text_bool_empty_or_duplicates(self):
        _, path, meta = self.build()
        invalid = [{'message_ids': ['DROP TABLE events']}, {'message_ids': [uid(1), uid(1)]},
            {'message_ids': []}, {'action_types': [True]}, {'action_types': ['AGENT_TALK;DROP']},
            {'action_types': []}, {'max_rows': True}, {'max_rows': 0}, {'max_rows': 15001},
            {'windows': []}, {'windows': [{'room_id': uid(10), 'start': '2026-04-18T19:00:00Z', 'end_exclusive': '2026-04-18T18:00:00Z'}]},
            {'windows': [{'room_id': uid(10), 'start': '2026-04-18T18:00:00Z', 'end_exclusive': '2026-04-18T19:00:00Z', 'callback': 'arbitrary'}]}]
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):self.read(path, meta, **kwargs)

    def test_projection_and_selection_column_forgery_detected_even_rehashed_file(self):
        _, path, meta = self.build()
        digest = self.mutate(path, 'UPDATE events SET action_type=? WHERE line=?', ('WAIT', 1))
        with self.assertRaises(ValueError):index.read_event_index(path, expected_file_sha256=digest)
        _, path, meta = self.build()
        with contextlib.closing(sqlite3.connect(path)) as con:
            record = json.loads(con.execute('SELECT projection_json FROM events WHERE line=1').fetchone()[0])
            record['actor_id'] = uid(999)
            con.execute('UPDATE events SET projection_json=?,projection_sha256=? WHERE line=1', (index._canonical(record).decode(), index._hash(record)))
            con.commit()
        with self.assertRaises(ValueError):index.read_event_index(path, expected_file_sha256=self.rehash(path))

    def test_schema_module_metadata_row_counts_and_file_damage_rejected(self):
        _, path, meta = self.build()
        digest = self.mutate(path, 'CREATE VIEW surprise AS SELECT * FROM events')
        with self.assertRaises(ValueError):index.read_event_index(path, expected_file_sha256=digest)
        _, path, meta = self.build()
        with contextlib.closing(sqlite3.connect(path)) as con:
            m = json.loads(con.execute('SELECT value FROM metadata').fetchone()[0]); m['implementation_hashes']['source_scanner.py'] = '0' * 64
            con.execute('UPDATE metadata SET value=?', (index._canonical(m).decode(),))
            con.commit()
        with self.assertRaises(ValueError):index.read_event_index(path, expected_file_sha256=self.rehash(path))
        _, path, meta = self.build()
        digest = self.mutate(path, 'DELETE FROM events WHERE line=1')
        with self.assertRaises(ValueError):index.read_event_index(path, expected_file_sha256=digest)
        damage = self.directory / 'damage.sqlite3'; damage.write_bytes(b'not a database')
        with self.assertRaises(ValueError):index.read_event_index(damage, expected_file_sha256=self.rehash(damage))

    def test_query_detects_file_change_between_before_and_after_hash(self):
        _, path, meta = self.build()
        original = index._file_hash; seen = [0]
        def changed(p):
            seen[0] += 1
            digest, size = original(p)
            return ('0' * 64 if seen[0] == 2 else digest), size
        with patch.object(index, '_file_hash', side_effect=changed), self.assertRaises(ValueError):self.read(path, meta)

    def test_repeat_queries_deterministic_immutable_and_no_sidecars(self):
        _, path, meta = self.build()
        before = path.read_bytes()
        one = self.read(path, meta); two = self.read(path, meta)
        self.assertEqual(one, two); self.assertEqual(before, path.read_bytes())
        self.assertFalse(Path(str(path) + '-wal').exists()); self.assertFalse(Path(str(path) + '-journal').exists())
        self.assertFalse(Path(str(path) + '-shm').exists())

    def test_internal_metadata_hash_binds_exact_final_build_metadata(self):
        _, path, meta = self.build()
        packet = self.read(path, meta)
        self.assertEqual(packet['index']['internal_metadata_sha256'], index._hash({k: v for k, v in meta.items() if k != 'artifact'}))
        self.assertTrue(meta['coverage']['physical_eof_observed'])
        self.assertTrue(meta['coverage']['decoder_eof_observed'])
        self.assertIsNone(meta['coverage']['gzip_crc_checked'])
        _, path, meta = self.build(compressed=True)
        self.assertTrue(meta['coverage']['gzip_crc_checked']); self.read(path, meta)

    def test_speaker_type_exact_enum_and_status_preserved(self):
        rows = [event(1), event(2), event(3), event(4)]
        rows[0]['data']['speakerType'] = 'agent'; rows[1]['data']['speakerType'] = 'user'
        rows[2]['data']['speakerType'] = None; rows[3]['data']['speakerType'] = 'private invalid speaker text'
        _, path, meta = self.build(encoded(rows))
        fields = [e['record']['fields']['data.speakerType'] for e in self.read(path, meta)['records']]
        self.assertEqual(fields[0]['value'], 'agent'); self.assertEqual(fields[1]['value'], 'user')
        self.assertEqual(fields[2]['presence'], 'null'); self.assertEqual(fields[3]['type_status'], 'invalid')
        self.assertNotIn(b'private invalid speaker text', path.read_bytes())

    def test_raw_projection_payload_and_bool_numeric_mirrors_rejected(self):
        for modification in ('payload', 'boolean'):
            _, path, meta = self.build()
            with contextlib.closing(sqlite3.connect(path)) as con:
                record = json.loads(con.execute('SELECT projection_json FROM events WHERE line=1').fetchone()[0])
                if modification == 'payload':
                    record['fields']['data.content']['value'] = 'forbidden raw content'
                else:
                    record['event_index'] = True
                con.execute('UPDATE events SET projection_json=?,projection_sha256=? WHERE line=1', (index._canonical(record).decode(), index._hash(record)))
                con.commit()
            with self.subTest(modification=modification), self.assertRaises(ValueError):
                index.read_event_index(path, expected_file_sha256=self.rehash(path))

    def test_forged_completeness_and_bool_build_counters_rejected(self):
        for modification in ('eof', 'boolean', 'declaration'):
            _, path, meta = self.build(max_rows=1)
            with contextlib.closing(sqlite3.connect(path)) as con:
                m = json.loads(con.execute('SELECT value FROM metadata').fetchone()[0])
                if modification == 'eof':
                    m['coverage']['complete_scan'] = True; m['state'] = 'complete'
                    m['coverage']['stop_reason'] = 'eof'; m['coverage']['scanned_file_id_uniqueness_verified'] = True
                elif modification == 'boolean':
                    m['coverage']['physical_rows_seen'] = True
                else:
                    m['declaration_comparison'] = {'server_md5': {'status': 'matching'}}
                con.execute('UPDATE metadata SET value=?', (index._canonical(m).decode(),)); con.commit()
            with self.subTest(modification=modification), self.assertRaises(ValueError):
                index.read_event_index(path, expected_file_sha256=self.rehash(path))

    def test_concatenated_gzip_members_and_second_member_crc(self):
        source = self.source(b'', compressed=True)
        source.write_bytes(gzip.compress(encoded([event(1)]), mtime=0) + gzip.compress(encoded([event(2)]), mtime=0))
        path = self.directory / 'members.sqlite3'
        meta = index.build_event_index(source, path)
        self.assertTrue(meta['coverage']['complete_scan']); self.assertTrue(meta['coverage']['gzip_crc_checked'])
        self.assertEqual(len(self.read(path, meta)['records']), 2)
        raw = source.read_bytes(); source.write_bytes(raw[:-8] + b'\x00' * 8)
        path = self.directory / 'members_corrupt.sqlite3'
        meta = index.build_event_index(source, path)
        self.assertFalse(meta['coverage']['complete_scan']); self.assertFalse(meta['coverage']['gzip_crc_checked'])
        self.read(path, meta)

    def test_source_open_error_is_partial_not_eof(self):
        source = self.source(encoded([event(1)]), compressed=True); path = self.directory / 'source_error.sqlite3'
        original = Path.open
        def denied(p, *args, **kwargs):
            if p == source and args and args[0] == 'rb':raise OSError('DO_NOT_LEAK_ERROR_DETAIL')
            return original(p, *args, **kwargs)
        with patch.object(Path, 'open', new=denied):
            meta = index.build_event_index(source, path)
        self.assertEqual(meta['coverage']['stop_reason'], 'io_error'); self.assertFalse(meta['coverage']['complete_scan'])
        self.assertFalse(meta['coverage']['source_eof_observed']); self.assertFalse(meta['coverage']['gzip_crc_checked'])
        self.assertNotIn('DO_NOT_LEAK', json.dumps(meta)); self.read(path, meta)

    def test_row_json_item_budget_and_lone_surrogate_are_explicit_partial(self):
        for value in ([0] * 17000, '\ud800'):
            row = event(2); row['data']['output'] = value
            suffix = json.dumps(row, ensure_ascii=True).encode() + b'\n'
            _, path, meta = self.build(encoded([event(1)]) + suffix)
            self.assertEqual(meta['coverage']['stop_reason'], 'invalid_record_structure')
            self.assertEqual(len(self.read(path, meta)['records']), 1)

    def test_unfinalized_database_and_output_budget_are_fail_closed(self):
        _, path, meta = self.build()
        with contextlib.closing(sqlite3.connect(path)) as con:
            m = json.loads(con.execute('SELECT value FROM metadata').fetchone()[0]); m['state'] = 'building'
            con.execute('UPDATE metadata SET value=?', (index._canonical(m).decode(),)); con.commit()
        with self.assertRaises(ValueError):index.read_event_index(path, expected_file_sha256=self.rehash(path))
        _, path, meta = self.build()
        with patch.object(index, 'MAX_OUTPUT_BYTES', 64), self.assertRaises(ValueError):self.read(path, meta)


if __name__ == '__main__':
    unittest.main()
