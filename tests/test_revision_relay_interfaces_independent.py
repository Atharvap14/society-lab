"""Public relay interfaces in isolated real stores; all provider access prohibited."""
import contextlib
from dataclasses import replace
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swarm_lab import cli
from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab


SERVER_BOOTSTRAP = r'''
import json
from pathlib import Path
import sys
from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab
from swarm_lab.server import serve
from swarm_lab.store import Store
root=Path(sys.argv[1])
class RecordingStore(Store):
    def job(self, identity, status, payload):
        row={'id':identity,'status':status,'action':payload.get('action'),
            'stage':payload.get('stage'),'component_status':payload.get('component_status'),
            'result_ids':payload.get('result_ids')}
        with (root/'job-publications.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(row)+'\n')
        return super().job(identity,status,payload)
lab=Lab(Settings(root=root,max_calls=int(sys.argv[3])))
lab.store=RecordingStore(lab.settings.runtime/'lab.sqlite3')
def forbidden_harness(name):
    (root/'harness-invoked.txt').write_text(name,encoding='utf-8')
    raise AssertionError('Provider access prohibited in interface fixture')
lab.harness=forbidden_harness
serve(lab,int(sys.argv[2]))
'''


class LoopbackFixture:
    def __init__(self, root, *, max_calls=16):
        self.root = root
        self.lab = Lab(Settings(root=root, max_calls=max_calls))
        with socket.socket() as socket_handle:
            socket_handle.bind(('127.0.0.1', 0))
            port = socket_handle.getsockname()[1]
        self.base = f'http://127.0.0.1:{port}'
        self.process = subprocess.Popen([sys.executable, '-c', SERVER_BOOTSTRAP,
            str(root), str(port), str(max_calls)], cwd=ROOT, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        deadline = time.monotonic() + 20
        try:
            while True:
                if self.process.poll() is not None:
                    raise AssertionError('Isolated server exited during startup')
                try:
                    self.state = self.get('/api/state')
                    break
                except urllib.error.URLError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(.05)
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
        self.process.wait(timeout=10)

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=5) as response:
            return json.load(response)

    def submit(self, action, args):
        request = urllib.request.Request(self.base + '/api/jobs',
            data=json.dumps({'action': action, 'args': args}).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'X-Lab-Token': self.state['csrf']})
        with urllib.request.urlopen(request, timeout=5) as response:
            identity = json.load(response)['job_id']
        deadline = time.monotonic() + 75
        while time.monotonic() < deadline:
            job = next(row for row in self.get('/api/state')['jobs'] if row['id'] == identity)
            if job['status'] in ('completed', 'failed'):
                return job
            time.sleep(.08)
        raise AssertionError('Isolated CPU-only queue did not reach terminal publication')

    def object(self, identity, version=None):
        suffix = '' if version is None else '?version=' + str(version)
        return self.get('/api/object/' + identity + suffix)

    def publications(self, identity):
        path = self.root / 'job-publications.jsonl'
        return [row for row in map(json.loads, path.read_text(encoding='utf-8').splitlines())
                if row['id'] == identity]


class IndependentRelayInterfaceTests(unittest.TestCase):
    def cli_call(self, root, argv):
        def isolated_lab(settings):
            return Lab(replace(settings, root=root))
        with patch('swarm_lab.cli.Lab', side_effect=isolated_lab), \
                patch.object(Lab, 'harness', side_effect=AssertionError('No provider fixture')), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            cli.main(['--runtime', str(root / '.runtime'), '--max-calls', '16', *argv])
        return json.loads(output.getvalue())

    def test_cli_requires_versions_before_creating_any_lab(self):
        for argv in (['experiment-revision-relay', 'fixture'], ['audit-revision-relay', 'fixture']):
            with self.subTest(argv=argv), patch('swarm_lab.cli.Lab') as factory, \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                cli.main(argv)
            self.assertEqual(caught.exception.code, 2)
            factory.assert_not_called()

    def test_cli_exact_historical_scripted_design_execute_audit_is_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registration = self.cli_call(root, ['design-revision-relay', '--blocks', '1', '--seed', '449'])
            lab = Lab(Settings(root=root, max_calls=16))
            original = lab.store.get(registration['id'], registration['version'])
            retired = dict(original['payload'], status='retired')
            lab.store.put('revision_relay_protocol', retired, original['id'])
            result = self.cli_call(root, ['experiment-revision-relay', original['id'],
                '--protocol-version', str(original['version'])])
            saved = lab.store.get(result['id'], result['version'])
            self.assertEqual(saved['payload']['status'], 'complete')
            self.assertEqual(saved['payload']['protocol_ref'],
                             {key: original[key] for key in ('id', 'version', 'hash')})
            self.assertTrue(Path(saved['payload']['artifact_root']).is_relative_to(root / '.runtime' / 'runs'))
            proof = self.cli_call(root, ['audit-revision-relay', result['id'], '--version', str(result['version'])])
            verification = lab.store.get(proof['id'], proof['version'])['payload']
            self.assertIs(verification['passed'], True)
            self.assertIs(verification['complete_execution'], True)
            self.assertIs(verification['quantitative_available'], True)
            self.assertEqual(lab.store.usage()['calls'], 0)
            with self.assertRaises(ValueError):
                self.cli_call(root, ['experiment-revision-relay', original['id'],
                    '--protocol-version', str(original['version'])])
            self.assertEqual(len(lab.store.list('revision_relay_experiment')), 1)
            self.assertEqual(len(list((root / '.runtime' / 'runs').iterdir())), 1)

    def test_loopback_scripted_workflow_queue_closure_and_summary_source_pins(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            server = LoopbackFixture(root)
            try:
                self.assertTrue({'design_revision_relay', 'experiment_revision_relay', 'audit_revision_relay'}
                                <= set(server.state['supported_actions']))
                design = server.submit('design_revision_relay', {'blocks': 1, 'seed': 461})
                self.assertEqual(design['status'], 'completed', design['payload'])
                protocol = server.object(design['payload']['result_ids'])
                required = {'protocol_id': protocol['id'], 'protocol_version': protocol['version'], 'live': False}
                experiment = server.submit('experiment_revision_relay', {**required, 'job_id': 'caller-name-is-not-authority'})
                self.assertEqual(experiment['status'], 'completed', experiment['payload'])
                result = server.object(experiment['payload']['result_ids'])
                self.assertEqual(result['payload']['research_job_id'], experiment['id'])
                self.assertFalse(server.lab.store.job_exists('caller-name-is-not-authority'))
                publications = server.publications(experiment['id'])
                terminal = [row for row in publications if row['status'] in ('completed', 'failed')]
                self.assertEqual(len(terminal), 1, publications)
                self.assertEqual(terminal[0]['status'], 'completed')
                self.assertEqual(terminal[0]['result_ids'], result['id'])
                self.assertTrue(any(row['status'] == 'running' and row['component_status'] == 'completed'
                                    for row in publications), publications)
                audit = server.submit('audit_revision_relay', {'result_id': result['id'], 'version': result['version']})
                self.assertEqual(audit['status'], 'completed', audit['payload'])
                proof = server.object(audit['payload']['result_ids'])['payload']
                self.assertIs(proof['passed'], True)
                self.assertIs(proof['quantitative_available'], True)
                state = server.get('/api/state')
                summary = next(row for row in state['objects'] if row['id'] == result['id'])
                self.assertEqual(summary['summary']['protocol_ref'], result['payload']['protocol_ref'])
                self.assertEqual(summary['hash'], result['hash'])
                self.assertEqual(summary['summary']['agent_mode'], 'scripted_infrastructure')
                self.assertEqual(state['usage']['calls'], 0)
                repeat = server.submit('experiment_revision_relay', {**required, 'job_id': 'different-request-name'})
                self.assertEqual(repeat['status'], 'failed')
                self.assertNotEqual(repeat['id'], experiment['id'])
                self.assertEqual(len(server.lab.store.list('revision_relay_experiment')), 1)
                self.assertEqual(len(list((root / '.runtime' / 'runs').iterdir())), 1)
                self.assertEqual(server.lab.store.get_job(result['payload']['study_claim_id'])['status'], 'completed')
                self.assertEqual(server.lab.store.get_job(experiment['id'])['status'], 'completed')
                self.assertFalse((root / 'harness-invoked.txt').exists())
            finally:
                server.close()

    def test_loopback_explicit_typed_versions_and_reserved_cap_block_before_harness(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seeded = Lab(Settings(root=root, max_calls=16))
            seeded.store.reserve_call(16)  # Reserved, unfinished call consumes the same global ceiling.
            server = LoopbackFixture(root, max_calls=16)
            try:
                designed = server.submit('design_revision_relay', {'blocks': 1, 'seed': 467, 'live': True})
                self.assertEqual(designed['status'], 'completed')
                protocol = server.object(designed['payload']['result_ids'])
                for version in ('missing', None, True, 1.0):
                    arguments = {'protocol_id': protocol['id'], 'live': True}
                    if version != 'missing':
                        arguments['protocol_version'] = version
                    with self.subTest(version=version):
                        failed = server.submit('experiment_revision_relay', arguments)
                        self.assertEqual(failed['status'], 'failed', failed['payload'])
                cap_blocked = server.submit('experiment_revision_relay', {
                    'protocol_id': protocol['id'], 'protocol_version': protocol['version'], 'live': True})
                self.assertEqual(cap_blocked['status'], 'failed')
                self.assertIn('Worst-case subject calls', cap_blocked['payload']['error'])
                failed = server.submit('audit_revision_relay', {'result_id': 'missing-fixture'})
                self.assertEqual(failed['status'], 'failed')
                usage = server.get('/api/state')['usage']
                self.assertEqual(usage['calls'], 1)
                self.assertEqual(usage['completed'], 0)
                self.assertFalse((root / 'harness-invoked.txt').exists())
                self.assertEqual(server.lab.store.list('revision_relay_experiment'), [])
                self.assertFalse(any(row['id'].startswith('relay-study-') for row in server.lab.store.jobs()))
                self.assertFalse((root / '.runtime' / 'runs').exists())
            finally:
                server.close()


if __name__ == '__main__':
    unittest.main()
