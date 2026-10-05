"""Declarative plans and a real loopback cycle without hosted requests."""
import contextlib
import io
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
from unittest.mock import patch

from swarm_lab.cli import main, read_research_cycle_plan
from swarm_lab.config import ROOT, Settings
from swarm_lab.environment_authoring import blueprint_fingerprint
from swarm_lab.pipeline import Lab
from tests.test_environment_authoring import proposal, review


def ref(obj):
    return {key: obj[key] for key in ('kind', 'id', 'version', 'hash')}


def seed_cycle(root):
    lab = Lab(Settings(root=root))
    dataset = lab.store.put('dataset', {'messages': [], 'scope': {}})
    discovery = lab.store.put('discovery', {'graph': {'edges': []}, 'candidates': [],
        'dataset_ref': {key: dataset[key] for key in ('id', 'version', 'hash')}})
    sources = {'dataset': ref(dataset), 'discovery': ref(discovery)}
    behavior = lab.store.put('behavior', {'name': 'Interface fixture', 'status': 'candidate',
        'evidence_ids': [], 'dataset_id': dataset['id'], 'discovery_id': discovery['id'],
        'source_refs': {kind: {key: value[key] for key in ('id', 'version', 'hash')}
                        for kind, value in sources.items()}, 'experiment_ids': []})
    candidate = proposal('complementary_information')
    materialized = {**candidate, 'source_refs': [ref(behavior), *sources.values()]}
    blueprint = lab.construct_environment(behavior_id=behavior['id'], proposal=candidate,
        fit_review=review(reviewed_blueprint_hash=blueprint_fingerprint(materialized)))
    return lab, {'behavior_ref': ref(behavior), 'source_refs': sources, 'blueprint_ref': ref(blueprint)}


class ResearchCycleInterfaceTests(unittest.TestCase):
    def test_plan_rejects_duplicate_nonfinite_extra_missing_and_oversized_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'plan.json'
            for body in ('{"behavior_ref":{},"source_refs":{},"seed":1,"seed":2}',
                         '{"behavior_ref":{},"source_refs":{},"seed":NaN}',
                         '{"behavior_ref":{},"source_refs":{},"callback":"x"}',
                         '{"behavior_ref":{}}', '[]', ' ' * (1024 * 1024 + 1)):
                path.write_text(body, encoding='utf-8')
                with self.subTest(body=body[:90]), self.assertRaises(ValueError):
                    read_research_cycle_plan(path)
            path.write_text('{"behavior_ref":{},"source_refs":{},"subjects_live":false}', encoding='utf-8')
            self.assertIs(read_research_cycle_plan(path)['subjects_live'], False)

    def test_cli_exact_plan_runs_and_resume_does_not_repeat_subjects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lab, plan = seed_cycle(root)
            plan['job_id'] = 'cli-cycle-fixture'
            path = root / 'plan.json'
            path.write_text(json.dumps(plan), encoding='utf-8')
            with patch('swarm_lab.cli.Settings', return_value=lab.settings), contextlib.redirect_stdout(io.StringIO()) as output:
                main(['--runtime', str(lab.settings.runtime), 'start-research-cycle', '--plan', str(path)])
            cycle = lab.store.get(json.loads(output.getvalue())['id'])
            self.assertEqual(cycle['payload']['status'], 'completed', cycle['payload'].get('failures'))
            count = len(lab.store.list('complementary_experiment'))
            with patch('swarm_lab.cli.Settings', return_value=lab.settings), contextlib.redirect_stdout(io.StringIO()):
                main(['--runtime', str(lab.settings.runtime), 'resume-research-cycle', cycle['id']])
            self.assertEqual(len(lab.store.list('complementary_experiment')), count)
            self.assertEqual(lab.store.usage()['calls'], 0)

    def test_queue_claims_distinct_inner_identity_and_retains_blocked_cycle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lab, plan = seed_cycle(root)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
            code = ('from pathlib import Path; import sys; from swarm_lab.pipeline import Lab; '
                    'from swarm_lab.config import Settings; from swarm_lab.server import serve; '
                    'serve(Lab(Settings(root=Path(sys.argv[1]))),int(sys.argv[2]))')
            process = subprocess.Popen([sys.executable, '-c', code, directory, str(port)], cwd=ROOT,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                base = f'http://127.0.0.1:{port}'
                def get(path):
                    with urllib.request.urlopen(base + path, timeout=5) as response:
                        return json.load(response)
                deadline = time.monotonic() + 8
                while True:
                    try:
                        state = get('/api/state'); break
                    except urllib.error.URLError:
                        if time.monotonic() > deadline: raise
                        time.sleep(.05)
                self.assertIn('start_research_cycle', state['supported_actions'])
                self.assertIn('resume_research_cycle', state['supported_actions'])
                def submit(action, args):
                    request = urllib.request.Request(base + '/api/jobs',
                        data=json.dumps({'action': action, 'args': args}).encode(),
                        headers={'Content-Type': 'application/json', 'X-Lab-Token': state['csrf']})
                    with urllib.request.urlopen(request, timeout=5) as response:
                        identity = json.load(response)['job_id']
                    deadline = time.monotonic() + 30
                    while time.monotonic() < deadline:
                        job = next(j for j in get('/api/state')['jobs'] if j['id'] == identity)
                        if job['status'] in ('completed', 'failed'): return job
                        time.sleep(.05)
                    self.fail('Bounded CPU cycle did not finish')
                completed = submit('start_research_cycle', {**plan, 'job_id': 'caller-must-not-claim'})
                self.assertEqual(completed['status'], 'completed', completed['payload'])
                cycle = get('/api/object/' + completed['payload']['cycle_ref']['id'])
                self.assertEqual(cycle['payload']['job_id'], completed['id'] + '.cycle')
                self.assertEqual(cycle['payload']['status'], 'completed')
                resumed = submit('resume_research_cycle', {'cycle_id': cycle['id']})
                self.assertEqual(resumed['payload']['cycle_ref'], completed['payload']['cycle_ref'])
                blocked = submit('start_research_cycle', {**plan, 'required_capabilities': ['browser_tools']})
                self.assertEqual(blocked['status'], 'failed')
                self.assertEqual(blocked['payload']['cycle_status'], 'blocked')
                preserved = get('/api/object/' + blocked['payload']['cycle_ref']['id'])
                self.assertEqual(preserved['payload']['artifacts']['blueprint'], plan['blueprint_ref'])
                self.assertNotIn('result', preserved['payload']['artifacts'])
                self.assertEqual(get('/api/state')['usage']['calls'], 0)
            finally:
                process.terminate(); process.wait(timeout=5)


if __name__ == '__main__': unittest.main()
