"""Independent compact-cache attacks against temporary real SQLite files.

No production registry, scientific-object cache or provider is involved. Fault
injection is confined to read boundaries of the new presentation cache.
"""
import concurrent.futures
import contextlib
import copy
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from swarm_lab.store import Store, fingerprint


import swarm_lab.state_inventory_cache as module


class IndependentStateCacheTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.path=self.root/'registry.sqlite3'
        self.store=Store(self.path)
        self.first=self.store.put('dataset',{'name':'Original fixture','messages':[{'content':'retained source'}],
            'not_for_inventory':'RAW_BODY_NOT_AN_INVENTORY_FIELD'*5000},'fixture-a')
        self.second=self.store.put('behavior',{'name':'Untested behavior','status':'candidate'},'fixture-b')
        self.cache=module.CompactObjectInventoryCache(self.path)
        self.addCleanup(self.cache.close)

    def mutate(self,body,*,identity='fixture-a',version=1,reseal=False):
        with contextlib.closing(sqlite3.connect(self.path,timeout=5)) as connection:
            with connection:
                if reseal:
                    connection.execute('UPDATE objects SET payload=?,hash=? WHERE id=? AND version=?',
                        (json.dumps(body),fingerprint(body),identity,version))
                else:
                    connection.execute('UPDATE objects SET payload=? WHERE id=? AND version=?',
                        (json.dumps(body),identity,version))

    def warm(self):
        # Opening a WAL observer may change filesystem signatures once; warm
        # until a publication is available, without assuming that is a write.
        for _ in range(3):
            result=self.cache.get()
            if self.cache.diagnostics['publications']:
                return result
        self.fail('Cache never published a stable valid snapshot')

    def test_hot_path_is_compact_alias_free_and_never_fetches_payload(self):
        result=self.warm();before=self.cache.diagnostics
        result[0]['summary']['name']='caller mutation'
        result.append({'payload':{'invented':True}})
        with patch.object(self.cache,'_decode_row',side_effect=AssertionError('Hot hit decoded payload')):
            again=self.cache.get()
        self.assertEqual(self.cache.diagnostics['payload_fetches'],before['payload_fetches'])
        self.assertEqual(len(again),2)
        self.assertNotIn('caller mutation',json.dumps(again))
        self.assertNotIn('RAW_BODY_NOT_AN_INVENTORY_FIELD',json.dumps(again))
        self.assertTrue(all('payload' not in row for row in again))
        self.assertTrue(all('not_for_inventory' not in row['summary'] for row in again))
        diagnostics=self.cache.diagnostics;diagnostics['hits']=-1
        self.assertGreaterEqual(self.cache.diagnostics['hits'],1)

    def test_same_hash_body_tamper_from_another_connection_rejects_instead_of_old_hot_result(self):
        self.warm();before=self.cache.diagnostics
        body=copy.deepcopy(self.first['payload']);body['name']='Invalid source body'
        self.mutate(body)
        with self.assertRaises(ValueError):self.cache.get()
        self.assertEqual(self.cache.diagnostics['failures'],before['failures']+1)
        self.assertIsNone(self.cache._cache)
        self.assertIsNone(self.cache._connection)
        with self.assertRaises(ValueError):self.store.get(self.first['id'],1)

    def test_resealed_mutation_reflected_and_exact_scientific_reader_remains_outside_cache(self):
        self.warm();body=copy.deepcopy(self.first['payload']);body['name']='Resealed current body'
        self.mutate(body,reseal=True)
        result=self.cache.get();changed=next(row for row in result if row['id']=='fixture-a')
        self.assertEqual(changed['summary']['name'],'Resealed current body')
        self.assertEqual(changed['hash'],fingerprint(body))
        # The existing Store remains a full, independently decoded exact reader.
        exact=self.store.get('fixture-a',1)
        self.assertEqual(exact['payload'],body)
        self.assertIn('not_for_inventory',exact['payload'])
        self.assertFalse(hasattr(self.cache,'get_object'))

    def test_append_latest_versions_limit_and_created_order_remain_actual_inventory(self):
        limited=module.CompactObjectInventoryCache(self.path,limit=2);self.addCleanup(limited.close)
        latest=self.store.put('dataset',{'name':'Latest A','messages':[{},{}]},'fixture-a')
        self.store.put('theory',{'name':'Hypothesis C'},'fixture-c')
        with contextlib.closing(sqlite3.connect(self.path)) as connection:
            with connection:
                connection.execute('UPDATE objects SET created=? WHERE id=? AND version=?',('2025-01-01T00:00:00Z','fixture-a',1))
                connection.execute('UPDATE objects SET created=? WHERE id=? AND version=?',('2025-01-04T00:00:00Z','fixture-a',2))
                connection.execute('UPDATE objects SET created=? WHERE id=?',('2025-01-03T00:00:00Z','fixture-b'))
                connection.execute('UPDATE objects SET created=? WHERE id=?',('2025-01-02T00:00:00Z','fixture-c'))
        result=limited.get()
        self.assertEqual([(row['id'],row['version']) for row in result],[('fixture-a',2),('fixture-b',1)])
        self.assertEqual(result[0]['hash'],latest['hash'])
        self.assertEqual(result[0]['summary']['messages'],2)
        self.assertEqual([(row['id'],row['version']) for row in result],
                         [(row['id'],row['version']) for row in self.store.list(limit=2)])

    def test_concurrent_readers_share_validated_compact_state_without_mutable_aliases(self):
        expected=self.warm();before=self.cache.diagnostics;barrier=threading.Barrier(2)
        def read(_):
            barrier.wait(timeout=5);return self.cache.get()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            first,second=list(executor.map(read,range(2)))
        self.assertEqual(first,expected);self.assertEqual(second,expected)
        first[0]['summary']['name']='thread mutation'
        self.assertEqual(second,expected)
        self.assertEqual(self.cache.get(),expected)
        self.assertEqual(self.cache.diagnostics['payload_fetches'],before['payload_fetches'])

    def test_commit_during_cold_decode_returns_old_snapshot_without_publishing_new_token(self):
        # Retain a validated, immutable result from the SELECT snapshot, then
        # commit a legitimate changed body on another SQLite connection.
        original=self.cache._decode_row;committed=[]
        body=copy.deepcopy(self.first['payload']);body['name']='Arrived during cold read'
        def decode(row):
            result=original(row)
            if not committed:
                self.mutate(body,reseal=True);committed.append(True)
            return result
        with patch.object(self.cache,'_decode_row',side_effect=decode):old=self.cache.get()
        self.assertEqual(next(row for row in old if row['id']=='fixture-a')['summary']['name'],'Original fixture')
        self.assertIsNone(self.cache._cache)
        self.assertGreaterEqual(self.cache.diagnostics['racing_commits_not_cached'],1)
        fresh=self.cache.get()
        self.assertEqual(next(row for row in fresh if row['id']=='fixture-a')['summary']['name'],'Arrived during cold read')

    def test_invalid_commit_during_cold_read_is_not_hidden_on_the_next_get(self):
        original=self.cache._decode_row;committed=[]
        body=copy.deepcopy(self.first['payload']);body['name']='Unsealed change during read'
        def decode(row):
            result=original(row)
            if not committed:self.mutate(body);committed.append(True)
            return result
        with patch.object(self.cache,'_decode_row',side_effect=decode):old=self.cache.get()
        self.assertEqual(next(row for row in old if row['id']=='fixture-a')['summary']['name'],'Original fixture')
        self.assertIsNone(self.cache._cache)
        with self.assertRaises(ValueError):self.cache.get()

    def test_closed_observer_or_gate_read_failure_never_serves_existing_hot_data(self):
        self.warm();self.cache._connection.close()
        with self.assertRaises(sqlite3.Error):self.cache.get()
        self.assertIsNone(self.cache._cache)
        self.warm()
        with patch.object(self.cache,'_token',side_effect=sqlite3.OperationalError('Injected observer read error')):
            with self.assertRaises(sqlite3.Error):self.cache.get()
        self.assertIsNone(self.cache._cache)
        self.assertIsNone(self.cache._connection)

    def test_close_evicts_and_a_later_get_revalidates_rather_than_returning_old_data(self):
        self.warm();before=self.cache.diagnostics['payload_fetches'];self.cache.close()
        body=copy.deepcopy(self.first['payload']);body['name']='Changed after explicit eviction'
        self.mutate(body,reseal=True)
        fresh=self.cache.get()
        self.assertEqual(next(row for row in fresh if row['id']=='fixture-a')['summary']['name'],'Changed after explicit eviction')
        self.assertGreater(self.cache.diagnostics['payload_fetches'],before)

    def test_file_replacement_reconnects_or_fails_closed_without_serving_old_inventory(self):
        self.warm();replacement=self.root/'replacement.sqlite3';other=Store(replacement)
        other.put('dataset',{'name':'Replacement database','messages':[]},'new-file-object')
        # Windows may refuse replacing an open SQLite handle. Closing only the
        # observer preserves the stale identity/cache to challenge reconnection.
        try:os.replace(replacement,self.path)
        except PermissionError:
            self.cache._connection.close();os.replace(replacement,self.path)
        try:
            result=self.cache.get()
        except (ValueError,sqlite3.Error):
            self.assertIsNone(self.cache._cache)
            return
        self.assertEqual([row['id'] for row in result],['new-file-object'])
        self.assertEqual(result[0]['summary']['name'],'Replacement database')
        self.assertGreaterEqual(self.cache.diagnostics['replacement_invalidations'],1)

    def test_missing_replacement_or_non_sqlite_file_fail_closed(self):
        self.warm();self.cache._connection.close()
        replacement=self.root/'not-a-database';replacement.write_bytes(b'Invalid SQLite bytes')
        os.replace(replacement,self.path)
        with self.assertRaises(sqlite3.Error):self.cache.get()
        self.assertIsNone(self.cache._cache)
        self.cache.close();self.path.unlink()
        with self.assertRaises(ValueError):self.cache.get()
        self.assertIsNone(self.cache._cache)

    def test_typed_limits_reject_bool_float_nan_and_unbounded_values(self):
        for value in (False,True,1.0,0,201):
            with self.subTest(limit=value),self.assertRaises(ValueError):
                module.CompactObjectInventoryCache(self.path,limit=value)
        for value in (True,False,0,-1,float('nan'),float('inf'),31,'5'):
            with self.subTest(timeout=value),self.assertRaises(ValueError):
                module.CompactObjectInventoryCache(self.path,timeout=value)


if __name__=='__main__':unittest.main()
