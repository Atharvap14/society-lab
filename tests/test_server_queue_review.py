"""Independent queue review: nested failure evidence and Store authority.

All artifacts, call reservations and loopback jobs are temporary fixtures. No
model, production registry, mounted source or external service is used.
"""
from concurrent.futures import ThreadPoolExecutor as RealExecutor
from contextlib import contextmanager
import json
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab
from swarm_lab.server import LocalResearchServer, _QueuedStore, serve
from swarm_lab.store import Store, StoreConflictError


class NestedFailureLab(Lab):
    """Use the actual workflow envelope around a durable failed experiment."""
    def __init__(self, root):
        super().__init__(Settings(root=root))
        self.entered, self.release = threading.Event(), threading.Event()
        self.partial_ids = []

    def ingest(self, source=None, **kwargs):
        return self.store.put('dataset', {'fixture': True})

    def observe(self, dataset_id, **kwargs):
        return self.store.put('discovery', {'dataset_id': dataset_id, 'fixture': True})

    def investigate(self, discovery_id, **kwargs):
        return [self.store.put('behavior', {'discovery_id': discovery_id,
            'experiment_fit': 'shared_artifact_coordination', 'status': 'proposed'})]

    def design(self, behavior_id, **kwargs):
        return self.store.put('protocol', {'behavior_id': behavior_id, 'fixture': True})

    def experiment(self, protocol_id, *, live=False, job_id=None):
        result = self.store.put('experiment', {'protocol_id': protocol_id,
            'status': 'incomplete', 'analysis': None, 'fixture': True})
        self.partial_ids.append(result['id'])
        self.store.trace(job_id, {'fixture': True, 'stage': 'experiment'})
        self.store.job(job_id, 'failed', {'stage': 'experiment',
            'incomplete_result_id': result['id'],
            'artifact_directory': str(self.settings.runtime / 'fixture-partial')})
        raise RuntimeError('Nested experiment failed after durable evidence')

    def workflow(self, **kwargs):
        try:
            return super().workflow(**kwargs)
        except Exception:
            # The actual workflow has already published its own failure,
            # replacing the child-stage payload without the queue adapter.
            self.entered.set()
            if not self.release.wait(5):
                raise TimeoutError('Fixture release was not received')
            raise


class RecoveredFailureLab(Lab):
    def __init__(self, root):
        super().__init__(Settings(root=root))
        self.entered, self.release = threading.Event(), threading.Event()
        self.partial_ids = []

    def experiment_complementary(self, protocol_id, *, live=False, job_id=None):
        partial = self.store.put('complementary_experiment', {
            'status': 'incomplete', 'analysis': None, 'fixture': True})
        self.partial_ids.append(partial['id'])
        self.store.job(job_id, 'failed', {'stage': 'attempt_one',
            'incomplete_result_id': partial['id']})
        self.store.job(job_id, 'running', {'stage': 'recovered_attempt'})
        result = self.store.put('complementary_experiment', {
            'status': 'complete', 'fixture': True})
        self.store.job(job_id, 'completed', {'stage': 'recovered_attempt',
            'result_id': result['id']})
        self.entered.set()
        if not self.release.wait(5):
            raise TimeoutError('Fixture release was not received')
        return result


@contextmanager
def running_fixture(lab):
    """Join both HTTP and executor threads before temporary-root deletion."""
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    servers, executors = [], []

    def capture_server(*args, **kwargs):
        server = LocalResearchServer(*args, **kwargs)
        servers.append(server)
        return server

    def capture_executor(*args, **kwargs):
        executor = RealExecutor(*args, **kwargs)
        executors.append(executor)
        return executor

    with patch('swarm_lab.server.LocalResearchServer', side_effect=capture_server), \
            patch('swarm_lab.server.concurrent.futures.ThreadPoolExecutor',
                  side_effect=capture_executor):
        worker = threading.Thread(target=serve, args=(lab, port), daemon=True)
        worker.start()
        base = f'http://127.0.0.1:{port}'

        def get(path='/api/state'):
            with urllib.request.urlopen(base + path, timeout=5) as response:
                return json.load(response)

        try:
            until = time.monotonic() + 5
            while True:
                try:
                    state = get()
                    break
                except urllib.error.URLError:
                    if time.monotonic() > until:
                        raise
                    time.sleep(.02)

            def submit(action, args):
                request = urllib.request.Request(base + '/api/jobs',
                    data=json.dumps({'action': action, 'args': args}).encode(),
                    headers={'Content-Type': 'application/json',
                             'X-Lab-Token': state['csrf']})
                with urllib.request.urlopen(request, timeout=5) as response:
                    return json.load(response)['job_id']

            yield get, submit
        finally:
            lab.release.set()
            if servers:
                servers[0].shutdown()
            worker.join(5)
            # serve uses wait=False: joining its HTTP thread alone would leave
            # a failed assertion racing temporary directory cleanup.
            for executor in executors:
                executor.shutdown(wait=True, cancel_futures=True)
            if worker.is_alive():
                raise AssertionError('Fixture HTTP thread did not stop')


def wait_terminal(get, identity):
    until = time.monotonic() + 5
    while True:
        job = next(row for row in get()['jobs'] if row['id'] == identity)
        if job['status'] in ('completed', 'failed'):
            return job
        if time.monotonic() > until:
            raise AssertionError('Fixture outer job did not publish its result')
        time.sleep(.02)


class IndependentQueueReviewTests(unittest.TestCase):
    def test_actual_nested_workflow_preserves_child_evidence_and_final_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            lab = NestedFailureLab(Path(directory))
            with running_fixture(lab) as (get, submit):
                identity = submit('workflow', {'live': False})
                self.assertTrue(lab.entered.wait(5))
                pending = lab.store.get_job(identity)
                self.assertEqual(pending['status'], 'running')
                self.assertEqual(pending['payload']['component_status'], 'failed')
                partial_id = lab.partial_ids[0]
                records = pending['payload']['component_failures']
                self.assertEqual(len(records), 2)
                self.assertEqual(records[0]['stage'], 'experiment')
                self.assertEqual(records[0]['incomplete_result_id'], partial_id)
                self.assertIn('outputs', records[1])
                self.assertEqual(pending['payload']['incomplete_result_id'], partial_id)
                self.assertNotIn('result_ids', pending['payload'])
                lab.release.set()
                done = wait_terminal(get, identity)
                self.assertEqual(done['status'], 'failed')
                self.assertEqual(done['payload']['action'], 'workflow')
                self.assertEqual(done['payload']['component_failures'], records)
                self.assertIn(partial_id, done['payload']['result_ids'])
                self.assertIn('durable evidence', done['payload']['error'])
                partial = lab.store.get(partial_id)
                self.assertEqual(partial['payload']['status'], 'incomplete')
                self.assertIsNone(partial['payload']['analysis'])
                self.assertEqual(len(lab.store.traces(identity)), 1)
                self.assertEqual(lab.store.usage()['calls'], 0)

    def test_later_progress_and_success_keep_failure_history_without_promoting_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            lab = RecoveredFailureLab(Path(directory))
            with running_fixture(lab) as (get, submit):
                identity = submit('experiment_complementary', {'protocol_id': 'fixture'})
                self.assertTrue(lab.entered.wait(5))
                pending = lab.store.get_job(identity)
                self.assertEqual(pending['status'], 'running')
                self.assertEqual(pending['payload']['stage'], 'recovered_attempt')
                self.assertEqual(pending['payload']['component_status'], 'completed')
                partial_id = lab.partial_ids[0]
                self.assertEqual(pending['payload']['component_failures'][0]
                                 ['incomplete_result_id'], partial_id)
                self.assertNotIn('result_ids', pending['payload'])
                lab.release.set()
                done = wait_terminal(get, identity)
                self.assertEqual(done['status'], 'completed')
                result = lab.store.get(done['payload']['result_ids'])
                self.assertEqual(result['payload']['status'], 'complete')
                self.assertNotEqual(result['id'], partial_id)
                self.assertEqual(done['payload']['component_failures'][0]
                                 ['incomplete_result_id'], partial_id)
                self.assertEqual(lab.store.get(partial_id)['payload']['status'], 'incomplete')
                self.assertEqual(lab.store.usage()['calls'], 0)

    def test_adapter_keeps_cycle_cas_trace_and_budget_authority_in_underlying_store(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'fixture.sqlite3')
            store.job('outer', 'running', {'action': 'start_research_cycle'})
            proxy = _QueuedStore(store, 'outer', 'start_research_cycle')
            proxy.start_job('outer.cycle', {'stage': 'cycle'})
            proxy.start_job('outer.cycle.phase.1', {'stage': 'child'})
            with self.assertRaises(ValueError):
                proxy.start_job('outer.cycle', {'stage': 'duplicate'})
            original = proxy.put('research_cycle', {'status': 'running'})
            updated = proxy.compare_and_put('research_cycle', {'status': 'completed'},
                original['id'], expected_version=original['version'],
                expected_hash=original['hash'], job_updates=[
                    {'id': 'outer.cycle', 'status': 'completed',
                     'payload': {'stage': 'cycle'}, 'preserve_completed': False},
                    {'id': 'outer.cycle.phase.1', 'status': 'completed',
                     'payload': {'stage': 'child'}, 'preserve_completed': False}])
            self.assertEqual(updated['version'], original['version'] + 1)
            with self.assertRaises(StoreConflictError):
                proxy.compare_and_put('research_cycle', {'status': 'stale'}, original['id'],
                    expected_version=original['version'], expected_hash=original['hash'])
            self.assertEqual(store.get_job('outer')['status'], 'running')
            for identity in ('outer.cycle', 'outer.cycle.phase.1'):
                self.assertEqual(store.get_job(identity)['status'], 'completed')
                self.assertNotIn('component_status', store.get_job(identity)['payload'])
            proxy.trace('outer', {'stage': 'dispatch'})
            proxy.trace('outer.cycle.phase.1', {'stage': 'subject'})
            self.assertEqual([row['job_id'] for row in store.traces('outer')], ['outer'])
            self.assertEqual([row['job_id'] for row in proxy.traces('outer.cycle.phase.1')],
                             ['outer.cycle.phase.1'])
            reservation = proxy.reserve_call(1)  # Local accounting fixture only.
            proxy.finish_call(reservation, 'completed', {'input_tokens': 7, 'output_tokens': 3})
            self.assertEqual(store.usage(), proxy.usage())
            self.assertEqual(store.usage()['calls'], 1)
            with self.assertRaises(RuntimeError):
                store.reserve_call(1)
            self.assertEqual(proxy.failures, [])

    def test_failure_history_is_immutable_nonrecursive_and_other_jobs_are_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'fixture.sqlite3')
            proxy = _QueuedStore(store, 'outer', 'workflow')
            payload = {'stage': 'child', 'incomplete_result_id': 'partial',
                'artifact_directory': 'fixture', 'details': {'items': ['original']},
                'component_failures': [{'untrusted_prior_history': True}]}
            proxy.job('outer', 'failed', payload)
            payload['details']['items'].append('later mutation')
            proxy.job('outer', 'running', {'stage': 'later'})
            saved = store.get_job('outer')['payload']
            self.assertEqual(saved['component_failures'][0]['details']['items'], ['original'])
            self.assertNotIn('component_failures', saved['component_failures'][0])
            self.assertEqual(saved['incomplete_result_id'], 'partial')
            # An explicit present value is not relabeled as the earlier stage.
            proxy.job('outer', 'running', {'stage': 'other', 'incomplete_result_id': None})
            self.assertIsNone(store.get_job('outer')['payload']['incomplete_result_id'])
            proxy.job('inner', 'failed', {'stage': 'independent'})
            self.assertEqual(store.get_job('inner')['status'], 'failed')
            self.assertEqual(store.get_job('inner')['payload'], {'stage': 'independent'})
            self.assertEqual(len(proxy.failures), 1)


if __name__ == '__main__':
    unittest.main()
