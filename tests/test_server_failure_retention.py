"""Actual queue failures retain the workflow's partial-evidence identity."""
import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from swarm_lab.config import ROOT


class ServerFailureRetentionTests(unittest.TestCase):
    def test_failed_queue_keeps_incomplete_result_binding(self):
        code = '''
from pathlib import Path
import sys
from swarm_lab.pipeline import Lab
from swarm_lab.config import Settings
from swarm_lab.server import serve
class FailingLab(Lab):
    def audit(self, result_id):
        job = self.store.jobs(statuses=['running'])[0]
        obj = self.store.put('timed_resource_experiment', {'status':'incomplete','analysis':None,'fixture':True})
        self.store.job(job['id'], 'failed', {'stage':'fixture_failure','incomplete_result_id':obj['id'],'retained_reason':'transport_unresolved'})
        raise RuntimeError('fixture failure after durable evidence')
serve(FailingLab(Settings(root=Path(sys.argv[1]))), int(sys.argv[2]))
'''
        with tempfile.TemporaryDirectory() as directory:
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            process = subprocess.Popen([sys.executable, '-c', code, directory, str(port)],
                cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                base = f'http://127.0.0.1:{port}'
                def get(path):
                    with urllib.request.urlopen(base + path, timeout=5) as response:
                        return json.load(response)
                until = time.monotonic() + 8
                while True:
                    try:
                        state = get('/api/state')
                        break
                    except urllib.error.URLError:
                        if time.monotonic() > until:
                            raise
                        time.sleep(.05)
                request = urllib.request.Request(base + '/api/jobs',
                    data=json.dumps({'action': 'audit', 'args': {'result_id': 'fixture'}}).encode(),
                    headers={'Content-Type': 'application/json', 'X-Lab-Token': state['csrf']})
                with urllib.request.urlopen(request, timeout=5) as response:
                    identity = json.load(response)['job_id']
                until = time.monotonic() + 10
                while True:
                    job = next(j for j in get('/api/state')['jobs'] if j['id'] == identity)
                    # The runner can persist partial failure evidence before
                    # the outer queue catches its exception and adds error.
                    if job['status'] == 'failed' and 'error' in job['payload']:
                        break
                    if time.monotonic() > until:
                        self.fail('Fixture queue failure did not finish')
                    time.sleep(.05)
                p = job['payload']
                self.assertEqual(p['stage'], 'fixture_failure')
                self.assertEqual(p['retained_reason'], 'transport_unresolved')
                self.assertIn('durable evidence', p['error'])
                saved = get('/api/object/' + p['incomplete_result_id'])
                self.assertEqual(saved['payload']['status'], 'incomplete')
                self.assertIsNone(saved['payload']['analysis'])
                self.assertEqual(get('/api/state')['usage']['calls'], 0)
            finally:
                process.terminate()
                process.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
