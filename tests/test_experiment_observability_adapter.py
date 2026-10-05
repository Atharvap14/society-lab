"""Adapter checks on authored saved-turn fixtures, never subject simulation."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from swarm_lab.config import ROOT
from swarm_lab.observability_protocol import connect_observability, digest
from swarm_lab.store import fingerprint
from tests import test_lab_workspace as http_fixture

SPEC = importlib.util.spec_from_file_location('experiment_observability_adapter', ROOT / 'scripts' / 'experiment-observability.py')
adapter = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(adapter)


def authored_record():
    payload = {'source_kind': 'authored_test_fixture', 'agent_mode': 'live', 'status': 'complete',
        'started_at': '2026-01-01T00:00:00Z', 'backend': {'metadata': {'harness': 'responses'}},
        'protocol': {'environment': {'kind': 'shared_artifact_coordination', 'agents': ['coordinator', 'builder', 'verifier']}},
        'runs': [{'run_id': 'run-1', 'outcomes': {'success': 1}, 'turns': [
            {'agent_id': 'builder', 'step': 0, 'request': {'context': ['Do not emit private context']},
                'action': {'action': 'send_message', 'recipient': 'coordinator', 'message': 'Recorded fixture send', 'rationale': 'Never emit this rationale'},
                'tool_result': {'ok': True, 'message_id': 'm1'}},
            {'agent_id': 'builder', 'step': 1, 'action': {'action': 'repair_artifact', 'artifact_id': 'manifest', 'contents': {'a': 2}},
                'tool_result': {'ok': True, 'artifact_id': 'manifest', 'version': 2}},
            {'agent_id': 'coordinator', 'step': 2, 'action': {'action': 'wait'}, 'tool_result': {'ok': False, 'reason': 'Fixture explicit failed tool'}}]}]}
    return {'id': 'experiment-fixture', 'version': 1, 'kind': 'experiment', 'payload': payload, 'hash': fingerprint(payload)}


class AdapterTests(unittest.TestCase):
    def test_exact_original_sends_tools_clock_and_no_private_reasoning_or_seeded_message(self):
        record = authored_record(); saved = copy.deepcopy(record)
        value = adapter.adapt_experiment(record); batch = value['batch']
        self.assertEqual(batch['source']['kind'], 'authored_example')
        self.assertEqual([e['data']['content'] for e in batch['events'] if e['kind'] == 'message.sent'], ['Recorded fixture send'])
        returns = [e for e in batch['events'] if e['kind'] == 'tool.returned']
        self.assertEqual([e['data']['success'] for e in returns], [True, True, False])
        self.assertTrue(all(e['occurred_at'] == record['payload']['started_at'] for e in batch['events']))
        self.assertIn('individual event timestamps unavailable', value['provenance']['clock_basis'])
        text = json.dumps(value)
        self.assertNotIn('Never emit this rationale', text); self.assertNotIn('Do not emit private context', text)
        self.assertNotIn('previous_shift', text); self.assertEqual(record, saved)
        self.assertEqual(len(value['provenance']['event_sources']), len(batch['events']))
        self.assertEqual(value['provenance']['batch_sha256'], digest(batch))

    def test_distinct_team_actors_unknown_tool_success_and_unsupported_sources_fail_closed(self):
        record = authored_record(); p = record['payload']; run = copy.deepcopy(p['runs'][0]); run['run_id'] = 'run-2'
        run['turns'][0]['tool_result'] = {}; p['runs'].append(run); record['hash'] = fingerprint(p)
        value = adapter.adapt_experiment(record)
        registrations = [e['actor_id'] for e in value['batch']['events'] if e['kind'] == 'agent.registered']
        self.assertEqual(len(set(registrations)), 6)
        self.assertEqual(sum(e['kind'] == 'message.sent' for e in value['batch']['events']), 1)
        self.assertEqual(len(value['provenance']['omissions']), 1)
        for field, invalid in [('status', 'incomplete'), ('agent_mode', 'offline')]:
            changed = copy.deepcopy(record); changed['payload'][field] = invalid; changed['hash'] = fingerprint(changed['payload'])
            with self.assertRaises(ValueError): adapter.adapt_experiment(changed)
        with self.assertRaises(ValueError): adapter.adapt_experiment(record | {'hash': '0' * 64})

    def test_actual_loopback_intake_and_identical_retry_preserve_exact_links_without_provider(self):
        host = http_fixture.WorkspaceHttpTests(); self.addCleanup(host.doCleanups); host.setUp()
        value = adapter.adapt_experiment(authored_record())
        first = adapter.connect_batch(host.base, value['batch'])
        second = adapter.connect_batch(host.base, value['batch'])
        self.assertIs(second['idempotent'], True)
        self.assertEqual(first['run_ref'], second['run_ref'])
        run = host.lab.store.get(first['run_ref']['id'], first['run_ref']['version'])
        self.assertEqual(run['payload']['events'], value['batch']['events'])
        brief = host.lab.store.get(first['brief_ref']['id'])
        self.assertEqual(brief['payload']['source_refs']['run_ref'], first['run_ref'])
        self.assertEqual(host.lab.store.usage()['calls'], 0)
        with self.assertRaises(ValueError): adapter.connect_batch('https://outside.invalid', value['batch'])


if __name__ == '__main__': unittest.main()
