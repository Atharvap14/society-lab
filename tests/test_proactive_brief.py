"""Source-bound automatic screening; fixtures are declarations, not findings."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from swarm_lab.proactive_brief import build_brief, build_chat_brief, FAMILIES
from swarm_lab.store import Store, fingerprint

ROOT = Path(__file__).resolve().parents[1]


def record(kind, payload, identity=None, version=1):
    return {'id': identity or kind + '-fixture', 'version': version, 'hash': fingerprint(payload),
            'kind': kind, 'payload': payload}


def event(identity, kind, *, actor='a', task=None, second=0, recipients=None, **data):
    return {'id': identity, 'occurred_at': f'2026-10-05T10:{second // 60:02d}:{second % 60:02d}Z',
            'kind': kind, 'actor_id': actor, 'task_id': task, 'parent_task_id': None,
            'recipient_ids': recipients or [], 'data': data}


def run(events):
    return record('observability_run', {'schema_version': 'societylab.events.v1',
        'source': {'id': 'source-fixture', 'name': 'Authored fixture', 'kind': 'authored_example'},
        'run': {'id': 'run-fixture'}, 'events': events,
        'source_batch_sha256': '0' * 64,
        'provenance': {'declared_not_independently_verified': True}})


def registered():
    return [event('reg-a', 'agent.registered', name='Alice'),
            event('reg-b', 'agent.registered', actor='b', name='Bob')]


def message(identity, *, actor='a', content='A message.', speaker_type='agent', second=0, recipients=None):
    return {'id': identity, 'timestamp': f'2026-10-05T10:{second // 60:02d}:{second % 60:02d}Z',
        'agent_id': actor if speaker_type == 'agent' else None, 'speaker_type': speaker_type,
        'agent_name': actor, 'speaker_id': actor, 'room_id': 'team', 'content': content,
        'recipient_ids': recipients or [], 'source': {'file': 'authored.jsonl', 'line': 1, 'table': 'chat_messages'}}


def signals(brief):
    return {s['code']: s for s in brief['signals']}


class ProactiveBriefTests(unittest.TestCase):
    def test_private_and_local_records_do_not_become_public_language_signals(self):
        rows = registered() + [event('private', 'message.sent', visibility='private',
            content='Waiting for access. Please check the file. Task is complete.'),
            event('local', 'reasoning.recorded', content='Waiting for Bob; correction: I was wrong.'),
            event('room', 'message.sent', recipients=['b'], visibility='room', channel_id='team', content='Hello.')]
        original = run(rows); before = copy.deepcopy(original)
        brief = build_brief(original)
        self.assertEqual(brief['signals'], [])
        self.assertEqual(brief['counts']['retained_messages'], 2)
        self.assertEqual(brief['counts']['agent_messages'], 1)
        self.assertEqual(brief['counts']['total_agent_messages'], 2)
        self.assertEqual(brief['counts']['private_agent_messages'], 1)
        self.assertEqual(brief['counts']['recorded_local_reasoning'], 1)
        self.assertEqual(brief['counts']['nonagent_or_unregistered_messages'], 0)
        self.assertEqual(brief['communication']['edges'][0]['evidence_event_ids'], ['room'])
        self.assertEqual(original, before)

    def test_local_reasoning_requires_actor_empty_recipients_and_content_only(self):
        for changes in ({'actor_id': None}, {'recipient_ids': ['b']}, {'data': {'content': 'local', 'visibility': 'private'}}):
            row = event('local', 'reasoning.recorded', content='Local log')
            row.update(changes)
            with self.assertRaisesRegex(ValueError, 'local reasoning'):
                build_brief(run(registered() + [row]))
        row = event('local', 'reasoning.recorded', content='Local log'); del row['recipient_ids']
        with self.assertRaisesRegex(ValueError, 'explicit recipient_ids'):
            build_brief(run(registered() + [row]))

    def test_private_chat_bridge_preserves_source_while_excluding_screen(self):
        r = run(registered() + [event('p', 'message.sent', visibility='private', content='Waiting for access.'),
            event('local', 'reasoning.recorded', content='Please check the file.')])
        m = message('p', content='Waiting for access.'); m['visibility'] = 'private'; m['room_id'] = None
        d = record('dataset', {'messages': [m], 'source_refs': {'run_ref': {k: r[k] for k in ('id', 'version', 'hash')}}})
        brief = build_brief(r, d)
        self.assertEqual(brief['signals'], [])
        self.assertIn('1 agent message', brief['summary'])
        self.assertIn('1 explicitly private agent post', brief['summary'])
        self.assertEqual(brief['counts']['total_agent_messages'], 1)
        self.assertEqual(brief['counts']['private_agent_messages'], 1)
        self.assertEqual(brief['counts']['recorded_local_reasoning'], 1)
        bad = copy.deepcopy(d['payload']); del bad['messages'][0]['visibility']
        with self.assertRaisesRegex(ValueError, 'exactly match'):
            build_brief(r, record('dataset', bad))
        self.assertEqual(build_chat_brief(d)['counts']['agent_messages'], 0)

    def test_unknown_visibility_is_not_private_and_explicit_channel_is_not_membership(self):
        rows = registered() + [event('m', 'message.sent', channel_id='team', content='Waiting for access.')]
        brief = build_brief(run(rows))
        self.assertEqual(brief['counts']['agent_messages'], 1)
        self.assertIn('waiting_language', signals(brief))
        self.assertEqual(brief['communication']['edges'], [])
        for data in ({'visibility': 'private', 'channel_id': 'room'}, {'visibility': 'direct'}, {'visibility': 'broadcast'}, {'visibility': 'bogus'}):
            recipients = ['b'] if data.get('visibility') == 'broadcast' else []
            with self.assertRaises(ValueError):
                build_brief(run(registered() + [event('bad', 'message.sent', recipients=recipients, content='Hello', **data)]))

    def test_valid_intake_display_labels_and_bounded_outputs_are_accepted(self):
        long_name = 'Alice\n' + 'x' * 300
        rows = [event('reg', 'agent.registered', name=long_name),
                event('call', 'tool.called', tool_name='search\n' + 'x' * 300, call_id='c')]
        # Each output is under64KiB, the full batch under1MiB. More than100k
        # primitive nodes must not spuriously invalidate a valid source batch.
        output = [[0] * 2000 for _ in range(14)]
        rows.extend(event('r' + str(i), 'tool.returned', call_id='c', success=True, output=output)
                    for i in range(4))
        brief = build_brief(run(rows))
        self.assertTrue(brief['agents'][0]['name_truncated'])
        self.assertEqual(brief['agents'][0]['name'], long_name[:200])
        self.assertEqual(brief['agents'][0]['tool_call_count'], 1)
        r = run(rows); ref = {k: r[k] for k in ('id', 'version', 'hash')}
        m = message('m'); m['agent_name'] = long_name
        d = record('dataset', {'messages': [m]})
        self.assertTrue(build_chat_brief(d)['agents'][0]['name_truncated'])

    def test_optional_relationships_normalize_only_in_screening_copy(self):
        rows = [{'id': 'reg', 'occurred_at': '2026-10-05T10:00:00Z',
                 'kind': 'agent.registered', 'actor_id': 'a', 'data': {'name': 'Alice'}},
                {'id': 'task', 'occurred_at': '2026-10-05T10:00:01Z',
                 'kind': 'task.created', 'task_id': 't', 'data': {'title': 'A task'}}]
        r = run(rows); original = copy.deepcopy(r)
        brief = build_brief(r)
        self.assertEqual(brief['counts']['known_agents'], 1)
        self.assertEqual(brief['tasks'][0]['id'], 't')
        self.assertEqual(r, original)
        malformed = {'id': 'm', 'occurred_at': '2026-10-05T10:00:00Z',
                     'kind': 'message.sent', 'actor_id': 'a', 'data': {'content': 'Hi'}}
        with self.assertRaisesRegex(ValueError, 'explicit recipient_ids'):
            build_brief(run(rows + [malformed]))

    def test_explicit_reports_and_questions_do_not_assert_verified_results(self):
        r = run(registered() + [event('task', 'task.created', task='t', title='Publish the delivery list'),
            event('assign', 'task.assigned', task='t', second=1, assignee_ids=['a']),
            event('call', 'tool.called', task='t', second=2, tool_name='publish', call_id='c'),
            event('return', 'tool.returned', task='t', second=3, call_id='c', success=False),
            event('done', 'task.completed', task='t', second=4, success=True)])
        brief = build_brief(r)
        s = signals(brief)
        self.assertEqual(s['reported_tool_error']['interpretation'], 'observed')
        self.assertEqual(s['reported_tool_error']['evidence_event_ids'], ['return'])
        self.assertEqual(brief['tasks'][0]['source_declared_status'], 'reported_complete')
        self.assertIsNone(brief['tasks'][0]['verified_completion'])
        self.assertFalse(brief['source_truth_verified'])
        self.assertFalse(brief['fresh_source_attestation'])
        self.assertEqual(brief['source_refs']['run_ref']['hash'], r['hash'])
        self.assertEqual(brief['model_calls'], 0)
        self.assertEqual(brief['database_writes'], 0)
        self.assertFalse(brief['novelty_established'])
        self.assertEqual(brief['status_changes'], [])

    def test_exact_call_id_repetition_is_candidate_not_duplicate_event_retry(self):
        rows = registered() + [event('c1', 'tool.called', task='t', tool_name='search', call_id='same'),
            event('c2', 'tool.called', task='t', second=1, tool_name='search', call_id='same')]
        s = signals(build_brief(run(rows)))['same_call_id_repeated']
        self.assertEqual(s['interpretation'], 'candidate')
        self.assertIsNone(s['next_test_family'])
        self.assertEqual(s['metrics']['call_id_groups'], 1)
        with self.assertRaisesRegex(ValueError, 'Duplicate event'):
            build_brief(run(rows + [copy.deepcopy(rows[-1])]))

    def test_tool_clusters_are_exact_task_actor_tool_and_bounded_time(self):
        def calls(times, **changes):
            return [event('c' + str(i), 'tool.called', task=changes.get('task', 't'),
                actor=changes.get('actor', 'a'), second=t, tool_name=changes.get('tool', 'search'), call_id=str(i))
                for i, t in enumerate(times)]
        s = signals(build_brief(run(registered() + calls([0, 150, 300]))))
        self.assertEqual(s['tool_call_cluster']['metrics']['window_seconds'], 300)
        self.assertEqual(s['tool_call_cluster']['severity'], 'unknown')
        self.assertNotIn('tool_call_cluster', signals(build_brief(run(registered() + calls([0, 150, 301])))))
        rows = calls([0, 1, 2]); rows[1]['task_id'] = 'other'; rows[2]['data']['tool_name'] = 'edit'
        self.assertNotIn('tool_call_cluster', signals(build_brief(run(registered() + rows))))
        self.assertNotIn('tool_call_cluster', signals(build_brief(run(registered() + calls([0, 1, 2], actor='unknown')))))

    def test_handoffs_require_changed_assignee_set_and_strict_time(self):
        rows = registered() + [event('a1', 'task.assigned', task='t', assignee_ids=['a']),
            event('a2', 'task.assigned', task='t', second=1, assignee_ids=['b'])]
        self.assertIn('declared_assignment_change', signals(build_brief(run(rows))))
        rows[3]['occurred_at'] = rows[2]['occurred_at']
        self.assertNotIn('declared_assignment_change', signals(build_brief(run(rows))))
        rows.append(event('a3', 'task.assigned', task='t', second=2, assignee_ids=['a', 'b']))
        self.assertNotIn('declared_assignment_change', signals(build_brief(run(rows))))

    def test_unknown_recipients_are_not_edges_and_self_send_is_not_a_peer_tie(self):
        rows = registered() + [event('m1', 'message.sent', recipients=['b', 'missing', 'a'], content='Hello')]
        brief = build_brief(run(rows))
        self.assertEqual(brief['communication']['edges'], [{'source': 'a', 'target': 'b',
            'recorded_send_count': 1, 'evidence_event_ids': ['m1']}])
        self.assertEqual(brief['counts']['unresolved_recipient_entries'], 1)
        self.assertEqual(brief['communication']['unresolved_recipients'][0]['recipient_id'], 'missing')

    def test_addressed_hotspot_keeps_message_and_recipient_denominators_distinct(self):
        rows = registered() + [event('m' + str(i), 'message.sent', second=i, recipients=['b'], content='A request.') for i in range(4)]
        brief = build_brief(run(rows)); s = signals(brief)['concentrated_recorded_sends']
        self.assertEqual(s['metrics']['all_known_nonself_recipient_entries'], 4)
        self.assertEqual(s['metrics']['share'], 1)
        self.assertEqual(s['interpretation'], 'candidate')
        self.assertEqual(s['next_test_family'], 'complementary_information')

    def test_chat_posts_do_not_invent_tasks_tools_or_recipient_edges(self):
        d = record('dataset', {'messages': [message('m1', content='Bob: I completed the task; waiting for access.'),
            message('m2', actor='b', content='Please check the file.')], 'provenance': {'origin': 'user_import'}})
        brief = build_chat_brief(d)
        self.assertEqual(brief['tasks'], [])
        self.assertEqual(brief['communication']['edges'], [])
        self.assertEqual(brief['source_refs'], {'dataset_ref': {k: d[k] for k in ('id', 'version', 'hash')}})
        self.assertEqual(signals(brief)['waiting_language']['evidence_message_ids'], ['m1'])
        self.assertNotIn('reported_task_completion', signals(brief))
        self.assertNotIn('reported_tool_error', signals(brief))
        self.assertTrue(brief['scope']['derived_chat_event_ids'])

    def test_human_text_does_not_become_agent_screen_positive(self):
        d = record('dataset', {'messages': [message('human', actor='human', speaker_type='user', content='Waiting for access; please check the file.'),
            message('agent', content='Hello.')]})
        brief = build_chat_brief(d)
        self.assertEqual(brief['counts']['agent_messages'], 1)
        self.assertEqual(brief['counts']['nonagent_or_unregistered_messages'], 1)
        self.assertEqual(brief['signals'], [])
        self.assertEqual(len(brief['agents']), 1)

    def test_long_chat_screening_is_explicitly_partial_not_global_absence(self):
        d = record('dataset', {'messages': [message('m', content='x' * 16000 + ' waiting for access')]})
        brief = build_chat_brief(d)
        self.assertEqual(brief['counts']['chat_contents_screened_partially'], 1)
        self.assertNotIn('waiting_language', signals(brief))
        self.assertIn('does not establish an absence', brief['summary'])

    def test_original_evidence_is_bounded_with_total_count(self):
        d = record('dataset', {'messages': [message('m' + str(i), content='Waiting for access.', second=i) for i in range(30)]})
        s = signals(build_chat_brief(d))['waiting_language']
        self.assertEqual(s['evidence_count'], 30)
        self.assertEqual(len(s['evidence_message_ids']), 20)
        self.assertTrue(s['evidence_truncated'])
        self.assertEqual(s['metrics']['agent_message_denominator'], 30)

    def test_bridge_exact_sources_contents_times_recipients_and_unknown_room(self):
        r = run(registered() + [event('m', 'message.sent', recipients=['b'], content='Please check the file.')])
        refs = {'run_ref': {k: r[k] for k in ('id', 'version', 'hash')}}
        m = message('m', content='Please check the file.', recipients=['b']); m['room_id'] = None
        d = record('dataset', {'messages': [m], 'source_refs': refs})
        brief = build_brief(r, d)
        self.assertEqual(signals(brief)['artifact_check_language']['evidence_message_ids'], ['m'])
        self.assertEqual(brief['source_refs']['dataset_ref']['hash'], d['hash'])
        for field, value in [('content', 'changed'), ('agent_id', 'b'), ('timestamp', '2026-10-05T10:00:01Z'), ('recipient_ids', [])]:
            bad = copy.deepcopy(d['payload']); bad['messages'][0][field] = value
            with self.assertRaisesRegex(ValueError, 'exactly match'):
                build_brief(r, record('dataset', bad))
        for missing in [[], [message('extra')]]:
            with self.assertRaisesRegex(ValueError, 'every recorded message'):
                build_brief(r, record('dataset', {'messages': missing, 'source_refs': refs}))

    def test_bridge_ref_cannot_rebase_or_coerce_bool_version(self):
        r = run(registered())
        for version in [True, 2]:
            refs = {'run_ref': {k: r[k] for k in ('id', 'version', 'hash')}}; refs['run_ref']['version'] = version
            with self.assertRaisesRegex(ValueError, 'exact observability'):
                build_brief(r, record('dataset', {'messages': [], 'source_refs': refs}))

    def test_registry_and_typed_schema_gates_reject_invented_sources(self):
        r = run(registered())
        for change in [('hash', 'f' * 64), ('version', True), ('kind', 'dataset')]:
            bad = copy.deepcopy(r); bad[change[0]] = change[1]
            with self.assertRaises(ValueError): build_brief(bad)
        for value in [1, None, 'false', []]:
            with self.assertRaisesRegex(ValueError, 'boolean'):
                build_brief(run(registered() + [event('return', 'tool.returned', call_id='c', success=value)]))
        for kind in [[], 'unsupported']:
            with self.assertRaises(ValueError): build_brief(run([event('e', kind)]))

    def test_malformed_recognized_dataset_metadata_is_explicit_value_error(self):
        for field in ('provenance', 'source_refs'):
            for value in ([], None, True, 'metadata'):
                with self.assertRaisesRegex(ValueError, field):
                    build_chat_brief(record('dataset', {'messages': [], field: value}))
        with self.assertRaisesRegex(ValueError, 'provenance.origin'):
            build_chat_brief(record('dataset', {'messages': [], 'provenance': {'origin': []}}))

    def test_naive_invalid_or_nonfinite_json_rejects_before_scoring(self):
        for stamp in ['2026-10-05T10:00:00', 'yesterday']:
            rows = registered(); rows[0]['occurred_at'] = stamp
            with self.assertRaises(ValueError): build_brief(run(rows))
        with self.assertRaisesRegex(ValueError, 'finite JSON'):
            build_brief(run([event('e', 'artifact.updated', output=float('nan'))]))
        d = {'messages': []}; x = d
        for _ in range(20): x['nested'] = {}; x = x['nested']
        with self.assertRaisesRegex(ValueError, 'depth'):
            build_chat_brief(record('dataset', d))

    def test_no_mutation_or_implicit_operator_model_store_calls(self):
        r = run(registered() + [event('m', 'message.sent', content='Waiting for access.')])
        original = copy.deepcopy(r)
        with patch('swarm_lab.discovery.detect_behaviors', side_effect=AssertionError('no implicit detector/backend')), \
             patch.object(Store, 'put', side_effect=AssertionError('no persistence')):
            build_brief(r)
        self.assertEqual(r, original)

    def test_outputs_do_not_forward_provider_arguments_results_or_credentials(self):
        synthetic = 'sk-' + 'x' * 30
        r = run(registered() + [event('c', 'tool.called', tool_name='search', call_id='c', arguments={'credential': synthetic}),
            event('r', 'tool.returned', call_id='c', success=False, output={'provider_raw': synthetic}),
            event('t', 'task.created', task='t', title='Task ' + synthetic)])
        encoded = json.dumps(build_brief(r))
        self.assertNotIn(synthetic, encoded)
        self.assertNotIn('provider_raw', encoded)
        self.assertNotIn('arguments', encoded)

    def test_empty_source_is_useful_unknown_and_family_hints_are_real(self):
        brief = build_brief(run([]))
        self.assertEqual(brief['signals'], [])
        self.assertEqual(brief['counts']['known_agents'], 0)
        self.assertIn('does not establish an absence', brief['summary'])
        from swarm_lab.environment_authoring import TEMPLATES
        self.assertEqual(FAMILIES, frozenset(TEMPLATES))

    def test_isolated_authored_import_to_brief_to_exact_saved_record_zero_calls(self):
        from swarm_lab.config import Settings
        from swarm_lab.pipeline import Lab
        from swarm_lab.friendly_import import import_chat
        with tempfile.TemporaryDirectory() as directory:
            lab = Lab(Settings(root=Path(directory), max_calls=0))
            content = (ROOT / 'examples/getting-started/sample-chat.jsonl').read_text(encoding='utf-8')
            receipt = import_chat(lab, json.dumps({'name': 'Authored tutorial', 'content': content}).encode())
            d = lab.store.get(receipt['dataset_ref']['id'], receipt['dataset_ref']['version'])
            brief = build_chat_brief(d)
            saved = lab.store.put('research_brief', brief)
            exact = lab.store.get(saved['id'], saved['version'])
            self.assertEqual(exact['hash'], fingerprint(brief))
            self.assertEqual(brief['counts']['retained_messages'], 12)
            self.assertEqual(brief['counts']['known_agents'], 3)
            self.assertIn('waiting_language', signals(brief))
            self.assertIn('artifact_check_language', signals(brief))
            self.assertEqual(brief['source_refs']['dataset_ref'], receipt['dataset_ref'])
            self.assertEqual(lab.store.usage()['calls'], 0)


if __name__ == '__main__':
    unittest.main()
