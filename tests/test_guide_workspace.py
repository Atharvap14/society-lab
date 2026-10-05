"""Persistent guide and genuine function retrieval use temporary SQLite/fake I/O."""
import concurrent.futures
import copy
import io
import json
import tempfile
import threading
import unittest
from unittest.mock import patch

from swarm_lab.guide_assistant import guide_chat, parse_guide_request
from swarm_lab.lab_workspace import (append_message, bootstrap_workspace, chat_snapshot,
    mutate_workspace, save_state)
from tests.test_guide_assistant import authored_lab, exact, inventory, provider_response, saved_guided_world


def working_lab(directory, allowance=10):
    lab, dataset, _ = authored_lab(directory, allowance=allowance)
    plan, simulator, _ = saved_guided_world(lab)
    original = bootstrap_workspace(lab)['default_chat_id']
    project = chat_snapshot(lab, original)['project_id']
    active = mutate_workspace(lab, {'op': 'create_chat', 'request_id': 'create-active',
        'project_id': project, 'name': 'Current question'})['chat']['id']
    borrowed = mutate_workspace(lab, {'op': 'create_chat', 'request_id': 'create-borrowed',
        'project_id': project, 'name': 'Other discussion'})['chat']['id']
    mutate_workspace(lab, {'op': 'reuse_artifact', 'request_id': 'link-plan',
        'artifact_ref': exact(plan), 'origin_chat_id': original, 'target_chat_id': borrowed})
    append_message(lab, borrowed, role='user', content='Our question concerns checking the original shared file.', request_id='other-user')
    append_message(lab, borrowed, role='assistant', content='This is a discussion proposal, not a proven mechanism.', request_id='other-assistant', metadata={'status': 'ok'})
    lab.store.put('guided_plan', {**plan['payload'], 'question': 'A later unrelated plan version'}, plan['id'])
    return lab, active, borrowed, dataset, plan, simulator


def request(chat, message='Explain our discussion', request_id='turn-1', **extra):
    return json.dumps({'message': message, 'current_view': 'plan', 'active_chat_id': chat,
        'request_id': request_id, **extra}).encode()


def response(payload, *, answer='This is saved discussion, not scientific evidence.', actions=None, sources=None, draft=None):
    value = provider_response(payload)
    body = {'answer': answer, 'action_ids': actions or [], 'source_ids': sources or [], 'plan_draft': draft}
    value['output'][0]['content'][0]['text'] = json.dumps(body)
    return io.BytesIO(json.dumps(value).encode())


def function_response(payload, chat, *, tool='read_chat_context', arguments=None):
    return io.BytesIO(json.dumps({'id': 'fixture-read', 'model': payload['model'], 'status': 'completed',
        'usage': {'input_tokens': 20, 'output_tokens': 10}, 'output': [{'type': 'function_call',
        'name': tool, 'call_id': 'call-read-1', 'arguments': json.dumps(arguments or {'chat_id': chat})}]}).encode())


class PersistentGuideTests(unittest.TestCase):
    def test_strict_chat_request_ids_modes_and_absent_chat_legacy_contract(self):
        base = {'message': 'Hi', 'current_view': 'watch'}
        for fields in ({'active_chat_id': '../chat', 'request_id': 'turn'},
                       {'active_chat_id': 'chat'}, {'request_id': 'turn'},
                       {'active_chat_id': 'chat', 'request_id': 'x' * 191},
                       {'active_chat_id': 'chat', 'request_id': 'turn', 'proactive': 1}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                parse_guide_request(json.dumps(base | fields))
        self.assertNotIn('active_chat_id', parse_guide_request(json.dumps(base)))

    def test_active_history_comes_from_server_and_empty_chat_does_not_borrow_global_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, borrowed, _, _, _ = working_lab(directory)
            append_message(lab, active, role='user', content='SERVER SAVED QUESTION', request_id='saved-user')
            append_message(lab, active, role='assistant', content='SERVER SAVED ANSWER', request_id='saved-assistant', metadata={'status': 'ok'})
            seen = []
            def fake_open(req, timeout):
                payload = json.loads(req.data); seen.append(payload)
                data = json.loads(payload['input'][0]['content'])
                self.assertEqual([row['content'] for row in data['conversation_history']], ['SERVER SAVED QUESTION', 'SERVER SAVED ANSWER'])
                self.assertNotIn('CLIENT INVENTION', json.dumps(data))
                self.assertEqual(data['saved_data']['excerpts'], [])
                self.assertEqual(data['saved_data']['inventory'], [])
                self.assertIn(borrowed, payload['tools'][0]['parameters']['properties']['chat_id']['enum'])
                return response(payload, answer='Your saved question is about the current discussion.')
            before = lab.store.list()
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=fake_open):
                result = guide_chat(lab, request(active, history=[{'role': 'assistant', 'content': 'CLIENT INVENTION'}]), inventory=inventory(lab))
            self.assertEqual(result['status'], 'ok')
            saved = chat_snapshot(lab, active)
            self.assertEqual(len(saved['messages']), 4)
            self.assertEqual(saved['messages'][-1]['content'], result['answer'])
            self.assertEqual(saved['messages'][-1]['metadata']['status'], 'ok')
            self.assertEqual(saved['messages'][-1]['metadata']['provider_status'], 'completed')
            self.assertEqual(saved['messages'][-1]['metadata']['provider_response_id'], 'fixture-response')
            self.assertEqual(lab.store.list(), before)
            self.assertEqual(lab.store.jobs(), [])
            self.assertEqual(len(seen), 1)

    def test_real_read_tool_then_exact_reuse_catalog_and_context_citation_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, borrowed, _, plan, _ = working_lab(directory)
            initial = chat_snapshot(lab, borrowed)
            seen = []
            def fake_open(req, timeout):
                payload = json.loads(req.data); seen.append(payload)
                if len(seen) == 1:
                    self.assertEqual(payload['tools'][0]['name'], 'read_chat_context')
                    return function_response(payload, borrowed)
                read = next(item for item in payload['input'] if item.get('type') == 'function_call_output')
                context = json.loads(read['output'])
                self.assertEqual(context['source']['chat_revision'], initial['revision'])
                self.assertEqual(context['source']['snapshot_hash'], initial['snapshot_hash'])
                self.assertFalse(context['fresh_scientific_attestation'])
                self.assertEqual(context['exact_saved_items'][0]['ref'], exact(plan))
                self.assertIn('not a proven mechanism', context['messages'][-1]['content'])
                actions = payload['text']['format']['schema']['properties']['action_ids']['items']['enum']
                choice = next(item for item in actions if item.startswith('chat:reuse_artifact:'))
                source = context['source']['id']
                self.assertIn(source, payload['text']['format']['schema']['properties']['source_ids']['items']['enum'])
                return response(payload, actions=[choice], sources=[source])
            before = lab.store.list()
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=fake_open):
                result = guide_chat(lab, request(active, 'Read the other discussion and reuse its saved plan here.'), inventory=inventory(lab))
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(result['actions'][0]['type'], 'reuse_artifact')
            self.assertEqual(result['actions'][0]['artifact_ref'], exact(plan))
            self.assertEqual(result['actions'][0]['origin_chat_id'], borrowed)
            self.assertEqual(result['actions'][0]['target_chat_id'], active)
            self.assertEqual(result['sources'][0]['kind'], 'workspace_chat_context')
            self.assertIsNone(result['sources'][0]['object_ref'])
            self.assertEqual(len(result['read_receipts']), 1)
            self.assertEqual(chat_snapshot(lab, borrowed), initial)
            self.assertEqual(chat_snapshot(lab, active)['artifacts'], [])
            self.assertEqual(lab.store.list(), before)
            self.assertEqual(lab.store.usage()['calls'], 2)
            self.assertEqual(lab.store.jobs(), [])

    def test_request_replay_restores_saved_answer_without_new_calls_and_conflicting_input_rejects(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, _, _, _, _ = working_lab(directory)
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=lambda req, timeout: response(json.loads(req.data), answer='A retained actual provider reply.')):
                first = guide_chat(lab, request(active), inventory=inventory(lab))
            with patch('swarm_lab.guide_assistant.ResponsesHarness.request', side_effect=AssertionError('No duplicate call')):
                second = guide_chat(lab, request(active, history=[{'role': 'user', 'content': 'ignored changed browser history'}]), inventory=inventory(lab))
                with self.assertRaises(ValueError):
                    guide_chat(lab, request(active, 'A different question'), inventory=inventory(lab))
            self.assertTrue(second['reused'])
            self.assertEqual(second['answer'], first['answer'])
            self.assertEqual(second['message_ids'], first['message_ids'])
            self.assertEqual(lab.store.usage()['calls'], 1)
            self.assertEqual(len(chat_snapshot(lab, active)['messages']), 2)

    def test_concurrent_duplicate_user_claim_permits_one_provider_call(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, _, _, _, _ = working_lab(directory)
            entered, release = threading.Event(), threading.Event()
            def fake_open(req, timeout):
                entered.set(); self.assertTrue(release.wait(5))
                return response(json.loads(req.data))
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=fake_open), concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(guide_chat, lab, request(active), inventory=inventory(lab))
                self.assertTrue(entered.wait(5))
                second = pool.submit(guide_chat, lab, request(active), inventory=inventory(lab)).result(timeout=5)
                self.assertEqual(second['status'], 'guide_turn_pending')
                release.set(); self.assertEqual(first.result(timeout=5)['status'], 'ok')
            self.assertEqual(lab.store.usage()['calls'], 1)
            self.assertEqual(len(chat_snapshot(lab, active)['messages']), 2)

    def test_proactive_output_cannot_navigate_clone_fork_or_edit_draft(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, _, _, _, _ = working_lab(directory)
            proposal = {'question': 'Unsupported unsolicited question', 'control_text': 'Control', 'treatment_text': 'Treatment'}
            def fake_open(req, timeout):
                payload = json.loads(req.data)
                choices = payload['text']['format']['schema']['properties']['action_ids']['items']['enum']
                return response(payload, actions=[next(x for x in choices if x.startswith('chat:fork:'))], draft=proposal)
            before = lab.store.list()
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=fake_open):
                result = guide_chat(lab, request(active, 'Automatically explain this source', proactive=True), inventory=inventory(lab))
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(result['actions'], [])
            self.assertIsNone(result['plan_draft'])
            self.assertEqual(chat_snapshot(lab, active)['messages'][-1]['metadata']['actions'], [])
            self.assertEqual(lab.store.list(), before)

    def test_unknown_chat_or_tool_is_unavailable_without_second_call_and_keeps_status(self):
        for tool, selected in [('execute_code', 'known'), ('read_chat_context', 'not-in-catalog')]:
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as directory:
                lab, active, borrowed, _, _, _ = working_lab(directory)
                def fake_open(req, timeout):
                    payload = json.loads(req.data)
                    return function_response(payload, borrowed if selected == 'known' else selected, tool=tool)
                with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=fake_open):
                    result = guide_chat(lab, request(active, 'Read another chat'), inventory=inventory(lab))
                self.assertEqual(result['status'], 'assistant_unavailable')
                self.assertEqual(result['actions'], [])
                self.assertEqual(lab.store.usage()['calls'], 1)
                self.assertEqual(chat_snapshot(lab, active)['messages'][-1]['metadata']['provider_status'], 'completed')

    def test_partial_provider_reply_is_saved_as_unvalidated_excerpt_not_an_action(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, _, _, _, _ = working_lab(directory)
            def fake_open(req, timeout):
                payload = json.loads(req.data); value = provider_response(payload, status='incomplete')
                value['output'][0]['content'][0]['text'] = 'Partial actual reply, not a completed claim.'
                return io.BytesIO(json.dumps(value).encode())
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=fake_open):
                result = guide_chat(lab, request(active), inventory=inventory(lab))
            self.assertEqual(result['status'], 'assistant_unavailable')
            saved = chat_snapshot(lab, active)['messages'][-1]['metadata']
            self.assertEqual(saved['provider_status'], 'incomplete')
            self.assertEqual(saved['provider_reply_excerpt'], 'Partial actual reply, not a completed claim.')
            self.assertEqual(saved['provider_reply_saved_as'], 'unvalidated_bounded_excerpt')
            self.assertEqual(saved['actions'], [])

    def test_saved_exact_context_and_current_fork_revision_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, _, _, plan, simulator = working_lab(directory)
            snapshot = chat_snapshot(lab, active)
            save_state(lab, active, expected_revision=snapshot['revision'], request_id='save-reviewed',
                state={'context': {'plan_ref': exact(plan), 'simulator_ref': exact(simulator)}})
            def fake_open(req, timeout):
                payload = json.loads(req.data); data = json.loads(payload['input'][0]['content'])
                self.assertEqual(data['saved_data']['current_reviewed_plan']['reviewed_plan']['question'], plan['payload']['question'])
                return response(payload, actions=['chat:fork:' + active])
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=fake_open):
                result = guide_chat(lab, request(active, 'Fork this discussion'), inventory=inventory(lab))
            current = chat_snapshot(lab, active)
            self.assertEqual(result['actions'][0]['expected_revision'], current['revision'])
            self.assertEqual(current['messages'][-1]['metadata']['actions'], result['actions'])
            self.assertEqual(result['chat_revision'], current['revision'])

    def test_catalogued_chat_revision_is_read_even_if_another_writer_appends_during_request(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, borrowed, _, _, _ = working_lab(directory)
            before = chat_snapshot(lab, borrowed)
            calls = []
            def fake_open(req, timeout):
                payload = json.loads(req.data); calls.append(payload)
                if len(calls) == 1:
                    append_message(lab, borrowed, role='user', content='LATER UNSEEN CHANGE', request_id='later-update')
                    return function_response(payload, borrowed)
                context = json.loads(next(x['output'] for x in payload['input'] if x.get('type') == 'function_call_output'))
                self.assertEqual(context['source']['chat_revision'], before['revision'])
                self.assertEqual(context['source']['snapshot_hash'], before['snapshot_hash'])
                self.assertNotIn('LATER UNSEEN CHANGE', json.dumps(context))
                return response(payload, sources=[context['source']['id']])
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=fake_open):
                result = guide_chat(lab, request(active, 'Read the other saved discussion'), inventory=inventory(lab))
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(result['read_receipts'][0]['chat_revision'], before['revision'])
            self.assertGreater(chat_snapshot(lab, borrowed)['revision'], before['revision'])

    def test_editable_copy_is_only_a_catalogued_proposal_with_exact_source_not_a_new_result(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, borrowed, _, plan, _ = working_lab(directory)
            calls = []
            def fake_open(req, timeout):
                payload = json.loads(req.data); calls.append(payload)
                if len(calls) == 1:
                    return function_response(payload, borrowed)
                updated = json.loads(payload['input'][-1]['content'])['updated_action_catalog']
                choice = next(row for row in updated if row['type'] == 'clone_artifact')
                self.assertEqual(choice['artifact_ref'], exact(plan))
                self.assertIn('not', choice['purpose'])
                return response(payload, actions=[choice['id']])
            before = lab.store.list()
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=fake_open):
                result = guide_chat(lab, request(active, 'Make an editable copy of that plan here'), inventory=inventory(lab))
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(result['actions'][0]['type'], 'clone_artifact')
            self.assertEqual(result['actions'][0]['artifact_ref'], exact(plan))
            self.assertEqual(lab.store.list(), before)
            self.assertEqual(chat_snapshot(lab, active)['artifacts'], [])

    def test_budget_notice_is_persistent_without_provider_or_ledger_call(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, _, _, _, _ = working_lab(directory, allowance=0)
            with patch('swarm_lab.guide_assistant.ResponsesHarness.request', side_effect=AssertionError('No authorized call')):
                result = guide_chat(lab, request(active), inventory=inventory(lab))
                replayed = guide_chat(lab, request(active), inventory=inventory(lab))
            self.assertEqual(result['status'], 'budget_unavailable')
            self.assertTrue(replayed['reused'])
            self.assertEqual(lab.store.usage()['calls'], 0)
            saved = chat_snapshot(lab, active)['messages']
            self.assertEqual(len(saved), 2)
            self.assertEqual(saved[-1]['metadata']['status'], 'budget_unavailable')
            self.assertIsNone(saved[-1]['metadata']['provider_status'])

    def test_retrieval_has_two_read_limit_and_no_fallback_to_unknown_tool_or_new_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, borrowed, _, _, _ = working_lab(directory)
            calls = []
            def fake_open(req, timeout):
                payload = json.loads(req.data); calls.append(payload)
                if len(calls) == 3:
                    self.assertEqual(payload['tool_choice'], 'none')
                return function_response(payload, borrowed)
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=fake_open):
                result = guide_chat(lab, request(active, 'Read both saved contexts'), inventory=inventory(lab))
            self.assertEqual(result['status'], 'assistant_unavailable')
            self.assertEqual(result['actions'], [])
            self.assertEqual(lab.store.usage()['calls'], 3)
            self.assertEqual(len(result['read_receipts']), 2)

    def test_malformed_final_workspace_action_cannot_change_source_or_open_invented_target(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, _, _, _, _ = working_lab(directory)
            before = lab.store.list()
            def fake_open(req, timeout):
                return response(json.loads(req.data), actions=['chat:open:invented'])
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=fake_open):
                result = guide_chat(lab, request(active, 'Open the other chat'), inventory=inventory(lab))
            self.assertEqual(result['status'], 'assistant_unavailable')
            self.assertEqual(result['actions'], [])
            self.assertEqual(lab.store.list(), before)
            self.assertEqual(lab.store.jobs(), [])


if __name__ == '__main__':
    unittest.main()
