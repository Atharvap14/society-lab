"""Recent display bounds cannot hide older execution identities or active jobs."""
import tempfile
import unittest
from pathlib import Path
from swarm_lab.store import Store

class JobHistoryTests(unittest.TestCase):
    def test_old_job_identity_and_active_status_survive_recent_listing_limit(self):
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d)/'lab.sqlite3');store.job('still-running','running',{})
            for i in range(35):store.job('done-'+str(i),'completed',{})
            self.assertNotIn('still-running',[j['id'] for j in store.jobs()])
            self.assertTrue(store.job_exists('still-running'));self.assertFalse(store.job_exists('never-launched'))
            self.assertEqual([j['id'] for j in store.jobs(statuses=['running'])],['still-running'])

    def test_invalid_filters_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d)/'lab.sqlite3')
            for kwargs in ({'limit':0},{'limit':True},{'statuses':[]},{'statuses':['unrecognized']}):
                with self.assertRaises(ValueError):store.jobs(**kwargs)

    def test_execution_identity_claim_is_not_an_upsert_or_retry(self):
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d)/'lab.sqlite3');store.start_job('fixed',{'revision':'original'})
            store.job('fixed','failed',{'failure':'preserved'})
            with self.assertRaisesRegex(ValueError,'already launched'):store.start_job('fixed',{'revision':'repeat'})
            job=store.jobs()[0];self.assertEqual(job['status'],'failed');self.assertEqual(job['payload'],{'failure':'preserved'})

if __name__=='__main__':unittest.main()
