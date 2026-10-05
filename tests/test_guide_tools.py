"""Actual temporary workflow operations; hosted transport is always fixture-only."""
import concurrent.futures
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from swarm_lab.config import Settings
from swarm_lab.guide_tools import execute_guide_tool, guide_activity, guide_tool_schemas, record_guide_activity
from swarm_lab.lab_workspace import DEFAULT_CHAT, DEFAULT_PROJECT, bootstrap_workspace, chat_snapshot, mutate_workspace
from swarm_lab.pipeline import Lab
from tests import test_guided_study as guided_fixture


def ref(obj): return {key: obj[key] for key in ('id', 'version', 'hash')}


class GuideToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.lab = Lab(Settings(root=Path(self.tmp.name), max_calls=100, model='unit-fixture-model'))
        self.dataset = self.lab.ingest(Path(__file__).resolve().parents[1] / 'examples' / 'coordination_fixture', limit=100)
        self.brief = self.lab.store.put('observation_brief', {'source_refs': {'dataset_ref': ref(self.dataset)}, 'signals': [],
            'scope': 'Authored temporary source fixture, not research evidence.'})
        bootstrap_workspace(self.lab)
        self.allowed = [ref(self.dataset), ref(self.brief)]

    def execute(self, name, args, request_id=None, **kwargs):
        return execute_guide_tool(self.lab, name, args, chat_id=DEFAULT_CHAT, request_id=request_id or 'tool-' + name,
            authorized_tools={name}, allowed_refs=self.allowed, **kwargs)

    def plan(self):
        value = self.execute('save_plan', {'source_ref': ref(self.brief), 'question': 'Does a file-check note change correct publication?',
            'control_text': 'Continue the assigned task with care.', 'treatment_text': 'Check the current file before publication.',
            'max_rounds': 2, 'valid_probability': 0})
        plan_ref = value['updated_context']['plan_ref']; self.allowed.append(plan_ref)
        return value, plan_ref

    def test_strict_schemas_expose_only_explicitly_authorized_operations_and_no_scripted_choice(self):
        self.assertEqual(guide_tool_schemas(set()), [])
        schemas = guide_tool_schemas({'run_experiment', 'create_project'})
        self.assertEqual({row['name'] for row in schemas}, {'run_experiment', 'create_project'})
        self.assertTrue(all(row['strict'] and row['parameters']['additionalProperties'] is False for row in schemas))
        self.assertNotIn('scripted', json.dumps(schemas).lower())
        with self.assertRaises(ValueError): guide_tool_schemas({'arbitrary_python'})

    def test_actual_read_activity_is_bounded_idempotent_and_does_not_claim_scientific_oracle(self):
        before = (self.lab.store.list(), self.lab.store.jobs(), self.lab.store.usage(), chat_snapshot(self.lab, DEFAULT_CHAT))
        with self.assertRaises(ValueError): record_guide_activity(self.lab, chat_id=DEFAULT_CHAT, request_id='read-one', phase='completed', summary='Read saved discussion.')
        start = record_guide_activity(self.lab, chat_id=DEFAULT_CHAT, request_id='read-one', phase='started', summary='Reading a saved discussion.')
        done = record_guide_activity(self.lab, chat_id=DEFAULT_CHAT, request_id='read-one', phase='completed', summary='Read saved discussion revision 1.', result_refs=[ref(self.brief)])
        again = record_guide_activity(self.lab, chat_id=DEFAULT_CHAT, request_id='read-one', phase='completed', summary='Read saved discussion revision 1.', result_refs=[ref(self.brief)])
        self.assertEqual(again, done)
        self.assertNotEqual(start['id'], done['id'])
        with self.assertRaises(ValueError): record_guide_activity(self.lab, chat_id=DEFAULT_CHAT, request_id='read-one', phase='failed', summary='Conflicting outcome.')
        with self.assertRaises(ValueError): record_guide_activity(self.lab, chat_id=DEFAULT_CHAT, request_id='fake-reasoning', tool='hidden_thought', phase='started', summary='Not an operation.')
        self.assertEqual(len(guide_activity(self.lab, DEFAULT_CHAT)['events']), 2)
        self.assertEqual((self.lab.store.list(), self.lab.store.jobs(), self.lab.store.usage(), chat_snapshot(self.lab, DEFAULT_CHAT)), before)

    def test_recorded_operation_order_survives_equal_or_reversed_wall_clock(self):
        with patch('swarm_lab.guide_tools.now', return_value='2026-10-05T12:00:00+00:00'):
            self.execute('create_project', {'name': 'Equal-clock test'}, 'equal-clock-1')
        self.assertEqual([row['phase'] for row in guide_activity(self.lab, DEFAULT_CHAT)['events']], ['started', 'completed'])
        with patch('swarm_lab.guide_tools.now', side_effect=['2026-10-05T14:00:00+00:00',
                '2026-10-05T14:00:00+00:00', '2026-10-05T13:00:00+00:00', '2026-10-05T13:00:00+00:00']):
            self.execute('create_project', {'name': 'Reversed-clock test'}, 'reversed-clock-1')
        self.assertEqual([row['phase'] for row in guide_activity(self.lab, DEFAULT_CHAT)['events']], ['started', 'completed', 'started', 'completed'])

    def test_generic_question_ungrounded_sources_and_invalid_types_cannot_start_operations(self):
        before = (self.lab.store.list(), self.lab.store.usage(), chat_snapshot(self.lab, DEFAULT_CHAT))
        with self.assertRaises(ValueError): execute_guide_tool(self.lab, 'build_simulator', {'plan_ref': ref(self.brief)},
            chat_id=DEFAULT_CHAT, request_id='generic-question', authorized_tools=set(), allowed_refs=self.allowed)
        for reference in (ref(self.dataset), ref(self.brief) | {'version': True}, ref(self.brief) | {'hash': '0' * 64}):
            with self.assertRaises(ValueError): self.execute('save_plan', {'source_ref': reference,
                'question': 'q', 'control_text': 'control', 'treatment_text': 'treatment'}, request_id='bad-source')
        self.assertEqual((self.lab.store.list(), self.lab.store.usage(), chat_snapshot(self.lab, DEFAULT_CHAT)), before)
        self.assertEqual(guide_activity(self.lab, DEFAULT_CHAT)['events'], [])

    def test_saved_plan_is_actual_exact_object_default_parameters_and_durable_receipt_not_execution(self):
        value, source = self.plan()
        plan = self.lab.store.get(source['id'], source['version'])
        self.assertEqual(ref(plan), source)
        self.assertEqual(plan['payload']['source_ref'], ref(self.brief))
        self.assertEqual(plan['payload']['trials_per_arm'], 2)
        self.assertEqual(plan['payload']['seed'], 42)
        self.assertEqual(plan['payload']['subject_mode'], 'live')
        self.assertEqual(self.lab.store.usage()['calls'], 0)
        self.assertEqual([row['phase'] for row in guide_activity(self.lab, DEFAULT_CHAT)['events']], ['started', 'completed'])
        self.assertIn(source, [row['ref'] for row in chat_snapshot(self.lab, DEFAULT_CHAT)['artifacts']])
        self.assertEqual(value['view'], 'plan')

    def test_discover_queues_real_mode_exact_source_and_captured_origin_not_a_model_finding(self):
        calls = []
        def queue(action, args, origin):
            calls.append((action, copy.deepcopy(args), origin)); return {'job_id': 'job-fixture-only'}
        result = self.execute('discover', {'source_ref': ref(self.dataset), 'count': 2}, queue_submit=queue)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['investigation_status'], 'queued')
        action, args, origin = calls[0]
        discovery_ref = result['updated_context']['discovery_ref']
        self.assertEqual((action, origin), ('investigate', DEFAULT_CHAT))
        self.assertEqual((args['discovery_id'], args['discovery_version'], args['discovery_hash']),
            (discovery_ref['id'], discovery_ref['version'], discovery_ref['hash']))
        self.assertIs(args['live'], True)
        self.assertEqual(args['harness'], 'responses')
        self.assertIn('pending', result['summary'])
        self.assertEqual(self.lab.store.usage()['calls'], 0)

    def test_workspace_project_chat_reuse_copy_edit_and_fork_are_real_local_operations(self):
        project = self.execute('create_project', {'name': 'Created by fixture command'})['project_id']
        created = self.execute('create_chat', {'project_id': project, 'name': 'A new discussion'})['chat_id']
        source = ref(self.brief)
        copied = self.execute('copy_artifact', {'artifact_ref': source, 'origin_chat_id': DEFAULT_CHAT, 'name': 'Editable proposal'})
        draft = self.lab.store.get(copied['artifact_ref']['id'])
        self.assertEqual(draft['kind'], 'workspace_draft')
        self.assertEqual(draft['payload']['original_source_ref'], source)
        self.assertIs(draft['payload']['copied_empirical_outcomes'], False)
        self.allowed.append(copied['artifact_ref'])
        edited = self.execute('edit_copy', {'draft_ref': copied['artifact_ref'], 'fields': {'notes': 'Review a different hypothesis.', 'name': None}})
        self.assertEqual(edited['artifact_ref']['version'], 2)
        self.assertEqual(self.lab.store.get(edited['artifact_ref']['id'])['payload']['editable_fields']['notes'], 'Review a different hypothesis.')
        current = chat_snapshot(self.lab, DEFAULT_CHAT)
        forked = self.execute('fork_chat', {'origin_chat_id': DEFAULT_CHAT, 'expected_revision': current['revision'], 'name': 'A branch', 'project_id': project})
        self.assertNotEqual(forked['chat_id'], DEFAULT_CHAT)
        self.assertEqual(chat_snapshot(self.lab, forked['chat_id'])['origin']['revision'], current['revision'])
        linked = execute_guide_tool(self.lab, 'reuse_artifact', {'artifact_ref': source, 'origin_chat_id': DEFAULT_CHAT},
            chat_id=created, request_id='reuse-to-new', authorized_tools={'reuse_artifact'}, allowed_refs=self.allowed, allowed_chat_ids=[DEFAULT_CHAT])
        self.assertEqual(linked['artifact_ref'], source)
        self.assertEqual(self.lab.store.usage()['calls'], 0)

    def test_repeated_request_and_concurrent_claim_never_create_duplicate_project(self):
        def invoke(_): return self.execute('create_project', {'name': 'Exactly once'}, request_id='same-project-request')
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool: responses = list(pool.map(invoke, range(6)))
        self.assertEqual(sum(row.get('reused') is False for row in responses), 1)
        completed = self.execute('create_project', {'name': 'Exactly once'}, request_id='same-project-request')
        self.assertIs(completed['reused'], True)
        with self.assertRaises(ValueError): self.execute('create_project', {'name': 'Different name'}, request_id='same-project-request')
        with self.lab.store.connect() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM workspace_projects WHERE name=?', ('Exactly once',)).fetchone()[0], 1)
        self.assertEqual(len(guide_activity(self.lab, DEFAULT_CHAT)['events']), 2)

    def test_actual_started_log_is_visible_during_blocking_operation_and_unknown_claim_is_not_replayed(self):
        entered, release = threading.Event(), threading.Event()
        def blocked(lab, raw):
            entered.set(); release.wait(5); raise OSError('Authored fixture failure')
        _, plan_ref = self.plan()
        with patch('swarm_lab.guided_study.create_simulator', blocked), concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.execute, 'build_simulator', {'plan_ref': plan_ref}, 'blocked-build')
            self.assertTrue(entered.wait(3))
            self.assertEqual(guide_activity(self.lab, DEFAULT_CHAT)['events'][-1]['phase'], 'started')
            duplicate = self.execute('build_simulator', {'plan_ref': plan_ref}, 'blocked-build')
            self.assertEqual(duplicate['status'], 'pending_or_unknown')
            release.set(); self.assertEqual(future.result(3)['status'], 'failed')
        repeated = self.execute('build_simulator', {'plan_ref': plan_ref}, 'blocked-build')
        self.assertEqual(repeated['status'], 'failed')
        self.assertIs(repeated['reused'], True)
        self.assertEqual(guide_activity(self.lab, DEFAULT_CHAT)['events'][-1]['phase'], 'failed')

    def test_actual_builder_subject_adapter_replay_and_claim_engine_are_used_with_fixture_transport_only(self):
        fixture = guided_fixture.GuidedStudyTests('test_actual_engine_live_transport_fixture_has_frozen_world_and_fresh_replay')
        fixture.setUp(); self.addCleanup(fixture.doCleanups)
        bootstrap_workspace(fixture.lab)
        allowed = [ref(fixture.brief)]
        def execute(name, args, request_id):
            result = execute_guide_tool(fixture.lab, name, args, chat_id=DEFAULT_CHAT, request_id=request_id,
                authorized_tools={name}, allowed_refs=allowed)
            allowed.extend(result['result_refs']); return result
        planned = execute('save_plan', {'source_ref': ref(fixture.brief), 'question': 'Does verification affect publication?',
            'control_text': 'Continue with the assigned task today.', 'treatment_text': 'Check the current file before publication.',
            'max_rounds': 2, 'valid_probability': 0}, 'real-host-plan')
        built = execute('build_simulator', {'plan_ref': planned['updated_context']['plan_ref']}, 'real-host-build')
        self.assertEqual(built['status'], 'completed')
        http = guided_fixture.FixtureHTTP()
        with patch.object(Settings, 'api_key', return_value='unit-test-key'), patch('swarm_lab.harness.urllib.request.urlopen', http):
            ran = execute('run_experiment', {'simulator_ref': built['updated_context']['simulator_ref']}, 'real-host-run')
            again = execute('run_experiment', {'simulator_ref': built['updated_context']['simulator_ref']}, 'new-request-same-world')
        self.assertEqual(ran['status'], 'completed')
        self.assertIs(again['execution_reused'], True)
        self.assertGreater(len(http.payloads), 0)
        self.assertEqual(fixture.lab.store.usage()['calls'], len(http.payloads))
        result_ref = ran['updated_context']['result_ref']
        self.assertTrue(ran['updated_context']['execution_ref']['id'].startswith('guided_result-'))
        result = fixture.lab.store.get(result_ref['id'], result_ref['version'])
        self.assertEqual(result['payload']['agent_mode'], 'live')
        self.assertEqual(len(result['payload']['runs']), 6)
        for reference in ran['result_refs']:
            record = fixture.lab.store.get(reference['id'], reference['version'])
            if record['kind'] == 'verification': self.assertIs(record['payload']['passed'], True)
        self.assertTrue(all(row['phase'] in ('started', 'completed') for row in guide_activity(fixture.lab, DEFAULT_CHAT)['events']))


if __name__ == '__main__': unittest.main()
