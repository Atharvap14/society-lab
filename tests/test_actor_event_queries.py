"""Authenticated temporary fixtures for explicit actor/time observations."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from swarm_lab import actor_event_queries as actor
from swarm_lab import event_source_index as index


def uid(n):
    return f'00000000-0000-0000-0000-{n:012x}'


def event(n, *, action='WAIT', timestamp='2026-04-18T18:00:00Z', actor_id=None, room='absent', **extras):
    data = {'actionType': action, 'agentId': uid(20) if actor_id is None else actor_id, **extras}
    if room != 'absent':
        data['roomId'] = room
    if action in ('AGENT_TALK', 'USER_TALK'):
        data['speakerId'] = data.pop('agentId')
    return {'id': uid(n), 'created_at': timestamp, 'event_index': n, 'data': data}


WINDOW = {'id': 'frozen-window', 'start': '2026-04-18T18:00:00Z', 'end_exclusive': '2026-04-18T19:00:00Z'}


class ActorEventQueryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.counter = 0

    def build(self, rows=None, **options):
        self.counter += 1
        source = self.directory / f'events{self.counter}.jsonl'
        source.write_bytes(b''.join(index._canonical(row) + b'\r\n' for row in (rows if rows is not None else [event(1)])))
        path = self.directory / f'index{self.counter}.sqlite3'
        meta = index.build_event_index(source, path, **options)
        return source, path, meta

    def read(self, path, meta, **options):
        return actor.read_actor_event_index(path, expected_file_sha256=meta['artifact']['file_sha256'],
            actor_ids=options.pop('actor_ids', [uid(20)]), windows=options.pop('windows', [WINDOW]), **options)

    def mutate(self, path, sql, parameters=()):
        with contextlib.closing(sqlite3.connect(path)) as con:
            con.execute(sql, parameters); con.commit()
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def meta_change(self, path, transform):
        with contextlib.closing(sqlite3.connect(path)) as con:
            meta = json.loads(con.execute('select value from metadata').fetchone()[0])
            transform(meta)
            con.execute('update metadata set value=?', (index._canonical(meta).decode(),)); con.commit()
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def read_expected(self, path, digest, **options):
        return actor.read_actor_event_index(path, expected_file_sha256=digest,
            actor_ids=options.pop('actor_ids', [uid(20)]), windows=options.pop('windows', [WINDOW]), **options)

    def test_missing_null_invalid_and_known_rooms_are_not_imputed(self):
        rows = [event(1), event(2, room=None, action='PAUSE', seconds=30), event(3, room='bad room'), event(4, room=uid(10))]
        source, path, meta = self.build(rows)
        packet = self.read(path, meta)
        self.assertEqual([e['room_observation']['status'] for e in packet['records']], ['missing', 'missing', 'invalid', 'known'])
        self.assertEqual([e['room_observation']['presence'] for e in packet['records']], ['absent', 'null', 'value', 'value'])
        self.assertTrue(all(e['room_observation']['inferred'] is False for e in packet['records']))
        self.assertEqual(packet['records'][0]['source']['raw_line_sha256'], hashlib.sha256(source.read_bytes().splitlines(keepends=True)[0]).hexdigest())
        self.assertEqual(packet['records'][0]['source']['record_sha256'], index._hash(rows[0]))
        summary = actor.summarize_actor_events(packet)
        self.assertEqual(summary['total']['room_status_counts'], {'known': 1, 'missing': 2, 'invalid': 1})
        self.assertEqual(summary['total']['pause_requested_seconds_sum'], 30)
        self.assertIn('not elapsed inactivity', summary['total']['pause_seconds_scope'])

    def test_room_missing_events_are_excluded_by_old_query_but_selected_here(self):
        _, path, meta = self.build([event(1), event(2, room=uid(10))])
        old = index.read_event_index(path, expected_file_sha256=meta['artifact']['file_sha256'],
            windows=[{**WINDOW, 'room_id': uid(10)}])
        self.assertEqual(len(old['records']), 1)
        self.assertEqual(len(self.read(path, meta)['records']), 2)

    def test_exact_actor_action_and_half_open_time_conjunction(self):
        rows = [event(1), event(2, actor_id=uid(21)), event(3, action='PAUSE'),
            event(4, timestamp='2026-04-18T19:00:00Z'), event(5, timestamp='2026-04-18T17:59:59Z')]
        _, path, meta = self.build(rows)
        packet = self.read(path, meta, action_types=['WAIT'])
        self.assertEqual([e['record']['id'] for e in packet['records']], [uid(1)])
        self.assertEqual(packet['coverage']['candidate_rows'], 2)
        self.assertEqual(packet['coverage']['other_explicit_actor_rows'], 1)

    def test_ties_are_retained_in_physical_line_order_not_causal_order(self):
        _, path, meta = self.build([event(9), event(1), event(8, timestamp='2026-04-18T20:00:00+02:00')])
        packet = self.read(path, meta)
        self.assertEqual([e['record']['id'] for e in packet['records']], [uid(9), uid(1), uid(8)])
        self.assertEqual(len(set(e['record']['created_at'] for e in packet['records'])), 1)
        self.assertIn('not a measured relay', ' '.join(packet['limitations']))

    def test_unordered_source_timestamps_query_all_rows_without_early_stop(self):
        _, path, meta = self.build([event(1, timestamp='2026-12-01T00:00:00Z'), event(2), event(3, timestamp='2020-01-01T00:00:00Z')])
        self.assertEqual([e['record']['id'] for e in self.read(path, meta)['records']], [uid(2)])

    def test_actor_unknown_invalid_conflict_and_future_action_are_unassigned(self):
        rows = [event(1), event(2, agentId=None), event(3, agentId=False),
            event(4, speakerId=uid(21)), event(5, action='FUTURE_ACTION'), event(6, action='AGENT_TALK')]
        rows[5]['data'].pop('speakerId'); rows[5]['data']['agentId'] = uid(20)
        _, path, meta = self.build(rows)
        packet = self.read(path, meta)
        self.assertEqual([e['record']['id'] for e in packet['records']], [uid(1)])
        self.assertEqual(packet['coverage']['candidate_actor_status_counts'], {'selected_valid': 1, 'unknown': 2, 'invalid_field': 1, 'conflicting_fields': 1, 'unrecognized_action': 1})
        self.assertEqual(actor.summarize_actor_events(packet)['total']['records'], 1)

    def test_syntactically_valid_unseen_actor_has_scoped_zero_not_roster_absence(self):
        _, path, meta = self.build()
        packet = self.read(path, meta, actor_ids=[uid(999)])
        self.assertEqual(packet['coverage']['matched_rows'], 0)
        self.assertEqual(packet['coverage']['other_explicit_actor_rows'], 1)
        self.assertEqual(packet['coverage']['global_absence'], 'unverified')
        self.assertEqual(actor.summarize_actor_events(packet)['by_actor'][uid(999)]['records'], 0)

    def test_invalid_missing_timestamps_are_disclosed_without_actor_assignment(self):
        rows = [event(1), event(2, timestamp='invalid')]
        rows.append(event(3)); rows[-1].pop('created_at')
        _, path, meta = self.build(rows)
        packet = self.read(path, meta)
        self.assertEqual(packet['coverage']['build_scan']['invalid_timestamp_rows'], 2)
        self.assertEqual(packet['coverage']['candidate_rows'], 1)
        self.assertIn('unassigned', packet['coverage']['invalid_time_scope'])

    def test_output_truncation_preserves_validation_but_summary_is_retained_only(self):
        _, path, meta = self.build([event(1), event(2, action='PAUSE'), event(3, action='STOP_USING_COMPUTER')])
        packet = self.read(path, meta, max_rows=1)
        self.assertEqual(packet['coverage']['matched_rows'], 3)
        self.assertEqual(packet['coverage']['candidate_rows_validated'], 3)
        self.assertFalse(packet['coverage']['query_complete']); self.assertTrue(packet['coverage']['truncated'])
        summary = actor.summarize_actor_events(packet)
        self.assertEqual(summary['total']['records'], 1)
        self.assertEqual(summary['total']['action_counts']['STOP_USING_COMPUTER'], 0)
        self.assertIn('Returned records only', summary['scope'])

    def test_candidate_budget_rejects_before_parsing_no_partial_summary(self):
        _, path, meta = self.build([event(1), event(2, actor_id=uid(21))])
        with patch.object(actor, '_entry') as entry, self.assertRaisesRegex(ValueError, 'candidate budget'):
            self.read(path, meta, max_candidate_rows=1)
        entry.assert_not_called()

    def test_partial_source_build_not_conflated_with_query_completeness(self):
        _, path, meta = self.build([event(1), event(2)], max_rows=1)
        packet = self.read(path, meta)
        self.assertTrue(packet['coverage']['query_complete'])
        self.assertFalse(packet['coverage']['build_scan']['complete_scan'])
        self.assertIn('upstream/global absence', ' '.join(packet['limitations']))

    def test_overlapping_windows_union_once_and_partitions_reuse_records(self):
        _, path, meta = self.build()
        second = {'id': 'overlap', 'start': '2026-04-18T17:00:00Z', 'end_exclusive': '2026-04-18T18:30:00Z'}
        packet = self.read(path, meta, windows=[WINDOW, second])
        self.assertEqual(packet['coverage']['matched_rows'], 1)
        self.assertEqual(set(packet['records'][0]['window_ids']), {'overlap', 'frozen-window'})
        summary = actor.summarize_actor_events(packet)
        self.assertEqual(sum(w['records'] for w in summary['by_window'].values()), 2)
        self.assertEqual(summary['total']['records'], 1)

    def test_filter_permutations_are_canonical_deterministic_and_do_not_mutate(self):
        _, path, meta = self.build([event(1), event(2, actor_id=uid(21), action='PAUSE')])
        actors, actions, windows = [uid(21), uid(20)], ['WAIT', 'PAUSE'], [copy.deepcopy(WINDOW)]
        before = copy.deepcopy((actors, actions, windows))
        a = self.read(path, meta, actor_ids=actors, windows=windows, action_types=actions)
        b = self.read(path, meta, actor_ids=actors[::-1], windows=windows, action_types=actions[::-1])
        self.assertEqual(a, b); self.assertEqual((actors, actions, windows), before)
        snapshot = copy.deepcopy(a); actor.summarize_actor_events(a); self.assertEqual(a, snapshot)

    def test_strict_filter_and_bound_types_reject_before_file_hash(self):
        _, path, meta = self.build()
        cases = [{'actor_ids': None}, {'actor_ids': []}, {'actor_ids': [True]}, {'actor_ids': ['alias']},
            {'actor_ids': [uid(20), uid(20)]}, {'actor_ids': [uid(i) for i in range(129)]},
            {'windows': []}, {'windows': True}, {'windows': [{**WINDOW, 'room_id': uid(10)}]},
            {'windows': [{**WINDOW, 'actor_id': uid(20)}]}, {'windows': [WINDOW, WINDOW]},
            {'windows': [{**WINDOW, 'start': '2026-04-18T18:00:00'}]},
            {'windows': [{**WINDOW, 'start': '2026-04-18T20:00:00+02:00'}]},
            {'windows': [{**WINDOW, 'end_exclusive': WINDOW['start']}]},
            {'action_types': []}, {'action_types': [True]}, {'action_types': ['wait']},
            {'action_types': ['WAIT', 'WAIT']}]
        for key in ('max_rows', 'max_candidate_rows'):
            cases.extend({key: value} for value in (True, False, 0, -1, 1.5, 15001))
        for options in cases:
            with self.subTest(options=options), patch.object(index, '_file_hash') as fh, self.assertRaises(ValueError):
                self.read(path, meta, **options)
            fh.assert_not_called()

    def test_expected_hash_mandatory_and_preflight_before_database_open(self):
        _, path, meta = self.build()
        for digest in (None, True, 'bad', 'A' * 64, '0' * 64):
            with self.subTest(digest=digest), patch.object(actor.sqlite3, 'connect') as connect, self.assertRaises(ValueError):
                self.read_expected(path, digest)
            connect.assert_not_called()

    def test_corrupt_artifact_changed_bytes_and_wrong_schema_rejected(self):
        _, path, meta = self.build()
        self.mutate(path, 'update events set action_type=?', ('PAUSE',))
        with self.assertRaises(ValueError): self.read(path, meta)
        digest = self.mutate(path, 'create table forged (secret text)')
        with self.assertRaisesRegex(ValueError, 'schema'): self.read_expected(path, digest)
        bad = self.directory / 'broken.sqlite3'; bad.write_bytes(b'not a database')
        with self.assertRaises(ValueError): self.read_expected(bad, hashlib.sha256(bad.read_bytes()).hexdigest())

    def test_forged_projection_actor_or_hash_or_sql_columns_rejected(self):
        for mode in ('actor', 'hash', 'column', 'payload', 'bool_index'):
            with self.subTest(mode=mode):
                _, path, meta = self.build()
                with contextlib.closing(sqlite3.connect(path)) as con:
                    rec = json.loads(con.execute('select projection_json from events').fetchone()[0])
                if mode == 'actor': rec['actor_id'] = uid(999)
                if mode == 'payload': rec['raw_command'] = 'secret command'
                if mode == 'bool_index': rec['event_index'] = True; rec['fields']['event_index']['value'] = True
                if mode in ('actor', 'payload', 'bool_index'):
                    digest = self.mutate(path, 'update events set projection_json=?,projection_sha256=?', (index._canonical(rec).decode(), index._hash(rec)))
                elif mode == 'hash': digest = self.mutate(path, 'update events set projection_sha256=?', ('0' * 64,))
                else: digest = self.mutate(path, 'update events set room_id=?', (uid(555),))
                with self.assertRaises(ValueError): self.read_expected(path, digest)

    def test_metadata_code_fingerprint_count_and_declaration_forgery_rejected(self):
        cases = [lambda m:m['implementation_hashes'].update({'event_source_index.py':'0'*64}),
            lambda m:m.update(source_input_fingerprint='0'*64),
            lambda m:m['coverage'].update(indexed_rows=2),
            lambda m:m['source_metadata_declaration'].update(verified=True),
            lambda m:m['coverage'].update(global_database_id_uniqueness_verified=True),
            lambda m:m['limits'].update(max_rows=True)]
        for change in cases:
            _, path, meta = self.build()
            digest = self.meta_change(path, change)
            with self.assertRaises(ValueError): self.read_expected(path, digest)

    def test_changed_during_query_post_hash_is_rejected(self):
        _, path, meta = self.build()
        expected = meta['artifact']['file_sha256']
        with patch.object(index, '_file_hash', side_effect=[(expected,path.stat().st_size),('0'*64,path.stat().st_size)]), self.assertRaisesRegex(ValueError,'changed during'):
            self.read(path, meta)

    def test_no_raw_content_provider_commands_or_stream_output(self):
        secret = 'PRIVATE_SOURCE_COMMAND_DO_NOT_EMIT_4242'
        _, path, meta = self.build([event(1, content=secret, output={'command':secret}, sessionGoal=secret)])
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            packet = self.read(path, meta); summary = actor.summarize_actor_events(packet)
        self.assertEqual(out.getvalue(), ''); self.assertEqual(err.getvalue(), '')
        self.assertNotIn(secret, json.dumps(packet)); self.assertNotIn(secret, json.dumps(summary))
        self.assertNotIn(secret.encode(), path.read_bytes())

    def test_summary_rejects_forged_records_scope_hashes_and_duplicate_ids(self):
        _, path, meta = self.build([event(1), event(2)])
        packet = self.read(path, meta)
        changes = [lambda p:p['index'].update(post_query_file_sha256='0'*64),
            lambda p:p['records'][0]['room_observation'].update(status='known'),
            lambda p:p['records'][0].update(window_ids=[]),
            lambda p:p['records'][0]['record'].update(actor_id=uid(21)),
            lambda p:p['records'][0].update(projection_sha256='0'*64),
            lambda p:p['coverage'].update(matched_rows=True),
            lambda p:p['coverage'].update(query_complete=1),
            lambda p:p['coverage'].update(candidate_rows=3),
            lambda p:p['records'].__setitem__(1, copy.deepcopy(p['records'][0])),
            lambda p:p['implementation_hashes'].update({'actor_event_queries.py':'0'*64})]
        for change in changes:
            p = copy.deepcopy(packet); change(p)
            with self.assertRaises(ValueError): actor.summarize_actor_events(p)

    def test_summary_rejects_nonfinite_nested_payload(self):
        _, path, meta = self.build()
        packet = self.read(path, meta)
        packet['records'][0]['record']['fields']['data.seconds']['value'] = float('nan')
        with self.assertRaises(ValueError): actor.summarize_actor_events(packet)

    def test_all_candidates_validate_even_other_actors_and_beyond_retention(self):
        for actor_id in (uid(20), uid(21)):
            _, path, meta = self.build([event(1), event(2, actor_id=actor_id)])
            digest = self.mutate(path, 'update events set projection_sha256=? where line=?', ('0' * 64, 2))
            with self.assertRaises(ValueError): self.read_expected(path, digest, max_rows=1)

    def test_summary_unknown_payload_fields_and_bool_build_flags_rejected(self):
        _, path, meta = self.build()
        packet = self.read(path, meta)
        changes = [lambda p:p.update(raw_content='private source content'),
            lambda p:p['coverage'].update(raw_output='private provider output'),
            lambda p:p['coverage']['build_scan'].update(complete_scan=1),
            lambda p:p['coverage']['build_scan'].update(indexed_rows=True),
            lambda p:p['coverage']['build_scan'].update(global_database_id_uniqueness_verified=True),
            lambda p:p['coverage']['build_scan'].update(stop_reason={}),
            lambda p:p['records'][0].update(source=None),
            lambda p:p['records'][0]['source'].update(line=[]),
            lambda p:p['source_metadata_declaration'].update(raw_command='private command')]
        for change in changes:
            p = copy.deepcopy(packet); change(p)
            with self.assertRaises(ValueError): actor.summarize_actor_events(p)

    def test_invalid_durations_are_not_summed_and_no_start_stop_intervals(self):
        rows = [event(1, action='PAUSE', seconds=True), event(2, action='PAUSE', seconds=None),
            event(3, action='PAUSE', seconds=2.5), event(4, action='START_USING_COMPUTER'),
            event(5, action='STOP_USING_COMPUTER')]
        _, path, meta = self.build(rows)
        summary = actor.summarize_actor_events(self.read(path, meta))
        self.assertEqual(summary['total']['pause_seconds_valid_records'], 1)
        self.assertEqual(summary['total']['pause_requested_seconds_sum'], 2.5)
        self.assertNotIn('lease', summary['total'])
        self.assertEqual(summary['total']['action_counts']['START_USING_COMPUTER'], 1)

    def test_malformed_projection_json_duplicate_keys_and_metadata_rejected(self):
        for mode in ('duplicate_keys', 'nonfinite', 'malformed_metadata', 'list_metadata'):
            _, path, meta = self.build()
            if mode == 'duplicate_keys':
                with contextlib.closing(sqlite3.connect(path)) as con:
                    text = con.execute('select projection_json from events').fetchone()[0]
                changed = '{"id":"' + uid(1) + '",' + text[1:]
                digest = self.mutate(path, 'update events set projection_json=?', (changed,))
            elif mode == 'nonfinite':
                digest = self.mutate(path, 'update events set projection_json=?', ('{"id":NaN}',))
            elif mode == 'malformed_metadata':
                digest = self.mutate(path, 'update metadata set value=?', ('{malformed private source',))
            else:
                digest = self.mutate(path, 'update metadata set value=?', ('[]',))
            with self.assertRaises(ValueError): self.read_expected(path, digest)

    def test_query_and_summary_leave_index_bytes_unchanged_and_need_no_source_reread(self):
        source, path, meta = self.build()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        source.unlink()
        packet = self.read(path, meta); actor.summarize_actor_events(packet)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
        self.assertTrue(packet['read_only']); self.assertEqual(packet['model_calls'], 0)
        self.assertEqual(packet['index']['read_file_sha256'], packet['index']['post_query_file_sha256'])
        self.assertIn('not freshly reread', packet['source_pin_scope'])


if __name__ == '__main__':
    unittest.main()
