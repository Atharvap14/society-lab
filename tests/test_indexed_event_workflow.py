"""Public registry-bound indexed event audit, with small complete raw fixtures."""
import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from swarm_lab.cli import main, read_event_index_plan
from swarm_lab.config import Settings
from swarm_lab.dataset import normalize_message
from swarm_lab.graph_discovery import discover_graph_leads
from swarm_lab.pipeline import Lab


def uid(n):
    return f'00000000-0000-0000-0000-{n:012d}'


class IndexedEventWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.lab = Lab(Settings(root=self.root))
        names = ['Alice', 'Bobby', 'Carol', 'o3']
        self.roster = [{'id': uid(i + 1), 'name': name} for i, name in enumerate(names)]
        self.messages = []
        self.events = []
        for hour in (10, 11):
            for i in range(12):
                actor = self.roster[i % 3]
                text = ('Bobby, inspect the telescope artifact. o3 may know.'
                        if actor['name'] != 'Bobby' else 'My local note is ready.') if hour == 10 else \
                       'Alice, Bobby, Carol, inspect the telescope artifact together.'
                timestamp = f'2025-04-02T{hour}:00:{i:02d}Z'
                message = normalize_message({'id': uid(100 + len(self.messages)),
                    'agent_id': actor['id'], 'agent_name': actor['name'], 'content': text,
                    'room_id': uid(50), 'timestamp': timestamp,
                    'source': {'file': 'fixture-chat', 'line': len(self.messages) + 1}},
                    source=str(self.root / 'chat_messages.jsonl'), line=len(self.messages) + 1)
                self.messages.append(message)
                self.events.append({'id': uid(1000 + len(self.events)), 'created_at': timestamp,
                    'event_index': len(self.events), 'data': {'actionType': 'AGENT_TALK',
                    'messageId': message['id'], 'speakerId': actor['id'],
                    'speakerType': 'agent', 'roomId': uid(50), 'content': text,
                    'output': 'PRIVATE_PROVIDER_SENTINEL'}})
        self.events.append({'id': uid(2000), 'created_at': '2025-04-02T10:02:00Z',
                            'event_index': 50, 'data': {'actionType': 'WAIT', 'agentId': uid(1),
                            'roomId': uid(50), 'duration': 30, 'output': 'PRIVATE_PROVIDER_SENTINEL'}})
        self.dataset = self.lab.store.put('dataset', {'messages': self.messages, 'agents': self.roster})
        self.discovery = self.lab.store.put('discovery', {'dataset_id': self.dataset['id'],
            'dataset_ref': self.ref(self.dataset), 'graph_search': discover_graph_leads(self.messages, self.roster)})
        self.selected = self.lab.audit_selected_leads(self.discovery['id'],
            short_name_allowlist=['o3'], include_unicode_shadow=True)
        self.source = self.root / 'events.jsonl'
        self.source.write_text(''.join(json.dumps(row) + '\n' for row in self.events), encoding='utf-8')

    @staticmethod
    def ref(obj):
        return {key: obj[key] for key in ('id', 'version', 'hash')}

    def build(self):
        return self.lab.build_event_source_index(self.source)

    def audit(self, index):
        return self.lab.audit_indexed_events(index['id'], self.selected['id'],
                    index_version=index['version'], selected_audit_version=self.selected['version'])

    def test_build_audit_and_fresh_local_index_replay_use_exact_older_versions(self):
        index = self.build()
        self.lab.store.put('dataset', {'later': True}, self.dataset['id'])
        self.lab.store.put('discovery', {'later': True}, self.discovery['id'])
        self.lab.store.put('selected_lead_audit', {'later': True}, self.selected['id'])
        self.lab.store.put('event_source_index', {'later': True}, index['id'])
        result = self.audit(index)
        proof = self.lab.replay_indexed_events(result['id'], version=1)['payload']
        self.assertTrue(proof['passed'])
        self.assertTrue(proof['index_artifact_reread_completed'])
        self.assertFalse(proof['full_event_source_reread'])
        self.assertEqual(result['payload']['source_refs']['dataset'], self.ref(self.dataset))
        self.assertEqual(result['payload']['index_ref'], self.ref(index))
        saved = json.dumps(result['payload']) + json.dumps(index['payload'])
        self.assertNotIn('PRIVATE_PROVIDER_SENTINEL', saved)
        self.assertNotIn(self.messages[0]['content'], saved)
        self.assertEqual(self.lab.store.list('behavior'), [])
        self.assertEqual(self.lab.store.usage()['calls'], 0)

    def test_changed_index_bytes_fail_replay_without_claiming_fresh_raw_source(self):
        index = self.build()
        result = self.audit(index)
        artifact = Path(index['payload']['build_metadata']['artifact']['path'])
        with artifact.open('ab') as handle:handle.write(b'changed')
        proof = self.lab.replay_indexed_events(result['id'])['payload']
        self.assertFalse(proof['passed'])
        self.assertTrue(proof['index_artifact_reread_attempted'])
        self.assertFalse(proof['index_artifact_reread_completed'])
        self.assertFalse(proof['full_event_source_reread'])

    def test_forged_selected_source_rejected_and_no_new_audit_persisted(self):
        index = self.build()
        forged = copy.deepcopy(self.selected['payload'])
        next(iter(forged['window_measurements'].values()))['original_window']['end_exclusive'] = '2025-04-02T13:00:00Z'
        selected = self.lab.store.put('selected_lead_audit', forged)
        with self.assertRaises(ValueError):self.lab.audit_indexed_events(index['id'], selected['id'])
        self.assertEqual(self.lab.store.list('indexed_event_audit'), [])

    def test_outer_registry_metadata_cannot_forge_coverage_of_same_index_bytes(self):
        index = self.build()
        forged = copy.deepcopy(index['payload'])
        forged['build_metadata']['coverage']['physical_rows_seen'] += 1
        bad = self.lab.store.put('event_source_index', forged)
        with self.assertRaisesRegex(ValueError, 'Registered build metadata'):
            self.audit(bad)
        self.assertEqual(self.lab.store.list('indexed_event_audit'), [])

    def test_forged_audit_changes_do_not_pass_replay(self):
        index = self.build()
        result = self.audit(index)
        modified = copy.deepcopy(result['payload'])
        modified['query']['message_ids'] = []
        forged = self.lab.store.put('indexed_event_audit', modified)
        self.assertFalse(self.lab.replay_indexed_events(forged['id'])['payload']['passed'])
        with patch('swarm_lab.indexed_event_workflow.implementation_hashes', return_value={}):
            proof = self.lab.replay_indexed_events(result['id'])['payload']
        self.assertEqual(proof['reason'], 'implementation_hash_mismatch')
        self.assertFalse(proof['index_artifact_reread_attempted'])

    def test_bool_versions_and_query_bounds_are_refused(self):
        index = self.build()
        for kwargs in ({'index_version': True}, {'selected_audit_version': True},
                       {'max_query_rows': True}, {'max_query_rows': 15001}, {'max_query_rows': 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.lab.audit_indexed_events(index['id'], self.selected['id'], **kwargs)

    def test_deleted_raw_source_does_not_mislabel_local_projection_replay(self):
        index = self.build()
        result = self.audit(index)
        self.source.unlink()
        proof = self.lab.replay_indexed_events(result['id'])['payload']
        self.assertTrue(proof['passed'])
        self.assertFalse(proof['full_event_source_reread'])

    def test_public_cli_plan_is_bounded_and_cannot_choose_destination_or_callbacks(self):
        plan = self.root / 'plan.json'
        invalid = [b' ' * (256*1024+1), b'{"source_path":"x","source_path":"y"}',
                   b'{"source_path":"x","max_rows":NaN}', b'{"source_path":"x","destination_path":"x"}',
                   b'{"source_path":"x","on_progress":"x"}']
        for value in invalid:
            plan.write_bytes(value)
            with self.assertRaises(ValueError):read_event_index_plan(plan)
        plan.write_text(json.dumps({'source_path': str(self.source)}), encoding='utf-8')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            main(['--runtime', str(self.root / '.runtime'), 'build-event-index', '--plan', str(plan)])
        result = json.loads(output.getvalue())
        self.assertEqual(result['kind'], 'event_source_index')
        self.assertNotIn('payload', result)


if __name__ == '__main__':unittest.main()
