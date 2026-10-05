"""CPU-only production-import tests for the server presentation cache.

No production registry is accessed.
"""
import concurrent.futures
import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path

from swarm_lab.store import Store, fingerprint

from swarm_lab.state_inventory_cache import CompactObjectInventoryCache as Cache


class CompactInventoryCacheTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root/'fixture.sqlite3'
        self.store = Store(self.path)
        self.object = self.store.put('dataset', {'name':'Fixture source',
            'messages':[{'id':'m1'},{'id':'m2'}], 'candidates':[],
            'protocol_ref':{'id':'protocol-fixture','version':1,'hash':'a'*64,
                            'nested':['declared']}})
        self.cache = Cache(self.path)
        self.addCleanup(self.cache.close)

    def mutate(self, payload, digest=None):
        connection = sqlite3.connect(self.path)
        try:
            with connection:
                connection.execute('UPDATE objects SET payload=?,hash=? WHERE id=? AND version=?',
                    (json.dumps(payload, ensure_ascii=False), digest or self.object['hash'],
                     self.object['id'], self.object['version']))
        finally:
            connection.close()

    def test_unchanged_hit_fetches_no_payload_and_returns_independent_summary(self):
        first = self.cache.get()
        self.assertEqual(first[0]['summary']['messages'], 2)
        self.assertNotIn('payload', first[0])
        self.assertEqual(first[0]['hash'], self.object['hash'])
        self.cache._decode_row = lambda row: self.fail('An unchanged hit decoded a payload')
        first[0]['summary']['protocol_ref']['nested'].append('caller mutation')
        first[0]['summary']['name'] = 'Caller mutation'
        second = self.cache.get()
        self.assertEqual(second[0]['summary']['name'], 'Fixture source')
        self.assertEqual(second[0]['summary']['protocol_ref']['nested'], ['declared'])
        self.assertEqual(self.cache.diagnostics['payload_fetches'], 1)
        self.assertEqual(self.cache.diagnostics['hits'], 1)

    def test_append_and_latest_version_invalidate_cache(self):
        self.cache.get()
        newer = self.store.put('dataset', {'name':'Updated source','messages':[]},
                               self.object['id'])
        next_inventory = self.cache.get()
        self.assertEqual(len(next_inventory), 1)
        self.assertEqual(next_inventory[0]['version'], newer['version'])
        self.assertEqual(next_inventory[0]['hash'], newer['hash'])
        self.assertEqual(next_inventory[0]['summary']['name'], 'Updated source')
        self.assertEqual(self.cache.diagnostics['payload_fetches'], 2)

    def test_same_hash_body_tamper_committed_elsewhere_is_rejected(self):
        self.cache.get()
        changed = {**self.object['payload'], 'name':'Changed without hash'}
        self.mutate(changed)
        with self.assertRaisesRegex(ValueError, 'immutable hash'):
            self.cache.get()
        self.assertIsNone(self.cache._cache)
        self.assertIsNone(self.cache._connection)
        self.assertEqual(self.cache.diagnostics['failures'], 1)

    def test_resealed_body_at_same_version_is_revalidated_and_not_masked(self):
        self.cache.get()
        changed = {**self.object['payload'], 'name':'Resealed source'}
        self.mutate(changed, fingerprint(changed))
        inventory = self.cache.get()
        self.assertEqual(inventory[0]['version'], self.object['version'])
        self.assertEqual(inventory[0]['summary']['name'], 'Resealed source')
        self.assertEqual(inventory[0]['hash'], fingerprint(changed))
        self.assertEqual(self.cache.diagnostics['payload_fetches'], 2)

    def test_two_concurrent_readers_share_single_validated_miss(self):
        original = self.cache._decode_row
        def slower(row):
            time.sleep(0.025)
            return original(row)
        self.cache._decode_row = slower
        start = threading.Barrier(2)
        def read():
            start.wait()
            return self.cache.get()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda unused: read(), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertIsNot(results[0][0]['summary'], results[1][0]['summary'])
        self.assertEqual(self.cache.diagnostics['payload_fetches'], 1)
        self.assertEqual(self.cache.diagnostics['hits'], 1)

    def test_legitimate_commit_during_miss_returns_snapshot_once_without_cache(self):
        original = self.cache._decode_row
        def write_job(row):
            self.store.job('job-fixture', 'running', {'stage':'Authored fixture'})
            self.cache._decode_row = original
            return original(row)
        self.cache._decode_row = write_job
        first = self.cache.get()
        self.assertEqual(first[0]['summary']['name'], 'Fixture source')
        self.assertIsNone(self.cache._cache)
        self.assertEqual(self.cache.diagnostics['payload_fetches'], 1)
        self.assertEqual(self.cache.diagnostics['racing_commits_not_cached'], 1)
        second = self.cache.get()
        self.assertEqual(first, second)
        self.assertEqual(self.cache.diagnostics['payload_fetches'], 2)
        self.assertIsNotNone(self.cache._cache)

    def test_append_during_miss_cannot_publish_old_inventory_under_new_token(self):
        original = self.cache._decode_row
        def append(row):
            self.store.put('behavior', {'name':'Newly committed fixture'})
            self.cache._decode_row = original
            return original(row)
        self.cache._decode_row = append
        first = self.cache.get()
        self.assertEqual(len(first), 1)
        self.assertIsNone(self.cache._cache)
        second = self.cache.get()
        self.assertEqual(len(second), 2)
        self.assertEqual(second[0]['summary']['name'], 'Newly committed fixture')
        self.assertEqual(self.cache.diagnostics['payload_fetches'], 2)

    def test_actual_database_file_replacement_reconnects_instead_of_reusing_cache(self):
        self.cache.get()
        replacement = self.root/'replacement.sqlite3'
        replacement_store = Store(replacement)
        replacement_obj = replacement_store.put('behavior', {'name':'Replacement registry'})
        # Windows can deny replacement of an open SQLite file. Release the OS
        # handle without clearing the cached summaries, then perform a real swap.
        self.cache._connection.close()
        for suffix in ('-wal','-shm'):
            sidecar = Path(str(self.path)+suffix)
            if sidecar.exists():
                sidecar.unlink()
        os.replace(replacement, self.path)
        inventory = self.cache.get()
        self.assertEqual([row['id'] for row in inventory], [replacement_obj['id']])
        self.assertEqual(inventory[0]['summary']['name'], 'Replacement registry')
        self.assertEqual(self.cache.diagnostics['replacement_invalidations'], 1)
        self.assertEqual(self.cache.diagnostics['connections_opened'], 2)

    def test_mid_validation_file_identity_change_discards_and_fails_closed(self):
        signature = self.cache._signature
        original_decode = self.cache._decode_row
        replaced = False
        def decode(row):
            nonlocal replaced
            replaced = True
            return original_decode(row)
        def swapped_identity():
            value = signature()
            if replaced:
                db = value[0]
                return ((db[0], db[1]+1, *db[2:]), value[1])
            return value
        self.cache._decode_row, self.cache._signature = decode, swapped_identity
        with self.assertRaisesRegex(ValueError, 'replaced during validation'):
            self.cache.get()
        self.assertIsNone(self.cache._cache)
        self.assertIsNone(self.cache._connection)

    def test_closed_observer_does_not_serve_prior_cache_and_next_read_recovers(self):
        self.cache.get()
        self.cache._connection.close()
        with self.assertRaises(sqlite3.ProgrammingError):
            self.cache.get()
        self.assertIsNone(self.cache._cache)
        self.assertIsNone(self.cache._connection)
        self.assertEqual(self.cache.get()[0]['id'], self.object['id'])

    def test_explicit_close_evicts_and_later_get_reconnects_fresh(self):
        self.cache.get()
        self.cache.close()
        self.assertIsNone(self.cache._cache)
        self.assertIsNone(self.cache._connection)
        newer = self.store.put('dataset', {'name':'After eviction'}, self.object['id'])
        self.assertEqual(self.cache.get()[0]['version'], newer['version'])
        self.assertEqual(self.cache.diagnostics['connections_opened'], 2)

    def test_limit_and_timeout_types_are_bounded(self):
        for limit in (True, False, 0, 201, 2.0, '2'):
            with self.assertRaises(ValueError):
                Cache(self.path, limit=limit)
        for timeout in (True, 0, 31, float('nan'), float('inf'), '2'):
            with self.assertRaises(ValueError):
                Cache(self.path, timeout=timeout)
        additional = self.store.put('behavior', {'name':'Second fixture'})
        cache = Cache(self.path, limit=1)
        self.addCleanup(cache.close)
        self.assertEqual([row['id'] for row in cache.get()], [additional['id']])
