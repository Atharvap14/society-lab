import concurrent.futures
import tempfile
import unittest
from pathlib import Path
from swarm_lab.store import Store


class StoreIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store=Store(Path(self.directory.name)/'lab.sqlite3')

    def test_versioned_source_is_not_rebound_and_kind_is_stable(self):
        original=self.store.put('dataset',{'content':'original'},'d')
        self.store.put('dataset',{'content':'replacement'},'d')
        self.assertEqual(self.store.get('d',original['version'])['payload'],{'content':'original'})
        with self.assertRaisesRegex(ValueError,'cannot change kind'):
            self.store.put('theory',{},'d')

    def test_detects_database_payload_corruption_on_all_object_reads(self):
        self.store.put('dataset',{'content':'original'},'d')
        with self.store.connect() as connection:
            connection.execute("UPDATE objects SET payload=? WHERE id=?",('{"content":"silently changed"}','d'))
        for reader in (lambda:self.store.get('d'),lambda:self.store.list(),lambda:self.store.history('d')):
            with self.assertRaisesRegex(ValueError,'immutable hash'):reader()

    def test_concurrent_call_reservations_cannot_exceed_shared_cap(self):
        def reserve(_):
            try:return self.store.reserve_call(5)
            except RuntimeError:return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            reservations=list(pool.map(reserve,range(20)))
        self.assertEqual(len([r for r in reservations if r]),5)
        self.assertEqual(self.store.usage()['calls'],5)


if __name__=='__main__':unittest.main()
