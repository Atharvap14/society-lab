"""Actual CLI and loopback jobs for actor and literal-marker observations."""
import contextlib
import io
import json
import socket
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from swarm_lab.cli import main
from swarm_lab.config import ROOT
from tests import test_indexed_event_workflow as fixtures


class ActorEventInterfaceTests(unittest.TestCase):
    setUp = fixtures.IndexedEventWorkflowTests.setUp
    build = fixtures.IndexedEventWorkflowTests.build
    ref = staticmethod(fixtures.IndexedEventWorkflowTests.ref)

    def test_cli_pins_versions_and_replays_actor_and_marker_payloads(self):
        index = self.build()
        def command(args):
            with patch('swarm_lab.cli.Settings', return_value=self.lab.settings), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                main(['--runtime', str(self.lab.settings.runtime), *args])
            identity=json.loads(output.getvalue())
            return self.lab.store.get(identity['id'],identity['version'])
        audit = command(['audit-actor-events', index['id'], self.selected['id'],
                         '--index-version', '1', '--selected-audit-version', '1'])
        self.assertEqual(audit['kind'], 'actor_event_audit')
        proof = command(['replay-actor-events', audit['id'], '--version', '1'])
        self.assertTrue(proof['payload']['passed'])
        alignment = command(['audit-wait-markers', audit['id'], '--version', '1'])
        self.assertEqual(alignment['kind'], 'wait_marker_alignment_audit')
        proof = command(['replay-wait-markers', alignment['id'], '--version', '1'])
        self.assertTrue(proof['payload']['passed'])
        parent=self.lab.audit_temporal_paths(self.selected['id'],version=1)
        flow=command(['audit-edge-flow',parent['id'],'--version','1'])
        self.assertEqual(flow['kind'],'graph_hodge_audit')
        proof=command(['replay-edge-flow',flow['id'],'--version','1'])
        self.assertTrue(proof['payload']['passed'])
        self.assertEqual(self.lab.store.usage()['calls'], 0)

    def test_loopback_jobs_replay_exact_sources_and_reject_malformed_envelopes(self):
        index = self.build()
        parent=self.lab.audit_temporal_paths(self.selected['id'],version=1)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        code = ('from pathlib import Path; import sys; from swarm_lab.pipeline import Lab; '
                'from swarm_lab.config import Settings; from swarm_lab.server import serve; '
                'serve(Lab(Settings(root=Path(sys.argv[1]))),int(sys.argv[2]))')
        process = subprocess.Popen([sys.executable, '-c', code, str(self.root), str(port)], cwd=ROOT,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            base = f'http://127.0.0.1:{port}'
            def get(path):
                with urllib.request.urlopen(base + path, timeout=5) as response:
                    return json.load(response)
            deadline = time.monotonic() + 8
            while True:
                try: state = get('/api/state'); break
                except urllib.error.URLError:
                    if time.monotonic() > deadline: raise
                    time.sleep(.05)
            actions = {'audit_selected_actor_events', 'replay_actor_events',
                       'audit_wait_markers', 'replay_wait_markers','audit_edge_flow','replay_edge_flow'}
            self.assertTrue(actions <= set(state['supported_actions']))
            def request(raw):
                req = urllib.request.Request(base + '/api/jobs', data=raw,
                    headers={'Content-Type': 'application/json', 'X-Lab-Token': state['csrf']})
                with urllib.request.urlopen(req, timeout=5) as response: return json.load(response)
            count = len(get('/api/state')['jobs'])
            for raw in (b'{"action":"audit_wait_markers","args":{},"args":{}}',
                        b'{"action":"audit_wait_markers","args":{"max_work":NaN}}',
                        b'{"action":"audit_wait_markers","args":{"max_work":1e999}}',
                        b'{"action":"audit_wait_markers","args":[]}',
                        b'{"action":"not-a-supported-action","args":{}}', b'[]'):
                with self.subTest(raw=raw), self.assertRaises(urllib.error.HTTPError) as caught:
                    request(raw)
                self.assertEqual(caught.exception.code, 400)
            self.assertEqual(len(get('/api/state')['jobs']), count)
            def submit(action, args):
                identity = request(json.dumps({'action': action, 'args': args}).encode())['job_id']
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    job = next(j for j in get('/api/state')['jobs'] if j['id'] == identity)
                    if job['status'] in ('completed', 'failed'): return job
                    time.sleep(.05)
                self.fail('Bounded indexed observation job did not finish')
            audit_job = submit('audit_selected_actor_events', {'index_id': index['id'],
                'selected_audit_id': self.selected['id'], 'index_version': 1, 'selected_audit_version': 1})
            self.assertEqual(audit_job['status'], 'completed', audit_job)
            actor_id = audit_job['payload']['result_ids']
            actor = get('/api/object/' + actor_id)
            self.assertEqual(actor['payload']['index_ref'], self.ref(index))
            proof_job = submit('replay_actor_events', {'audit_id': actor_id, 'version': 1})
            proof = get('/api/object/' + proof_job['payload']['result_ids'])
            self.assertTrue(proof['payload']['passed'])
            marker_job = submit('audit_wait_markers', {'actor_audit_id': actor_id, 'version': 1})
            self.assertEqual(marker_job['status'], 'completed', marker_job)
            marker_id = marker_job['payload']['result_ids']
            marker = get('/api/object/' + marker_id)
            self.assertEqual(marker['payload']['actor_audit_ref'], self.ref(actor))
            proof_job = submit('replay_wait_markers', {'alignment_id': marker_id, 'version': 1})
            self.assertTrue(get('/api/object/' + proof_job['payload']['result_ids'])['payload']['passed'])
            flow_job=submit('audit_edge_flow',{'temporal_audit_id':parent['id'],'version':1})
            self.assertEqual(flow_job['status'],'completed',flow_job)
            flow_id=flow_job['payload']['result_ids']
            proof_job=submit('replay_edge_flow',{'audit_id':flow_id,'version':1})
            self.assertTrue(get('/api/object/'+proof_job['payload']['result_ids'])['payload']['passed'])
            self.assertEqual(get('/api/state')['usage']['calls'], 0)
        finally:
            process.terminate(); process.wait(timeout=5)


if __name__ == '__main__': unittest.main()
