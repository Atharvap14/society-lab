"""Persistent local chat organization using authored temporary records, no providers."""
import concurrent.futures
import copy
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from unittest.mock import patch

from swarm_lab.config import ROOT, Settings
from swarm_lab.lab_workspace import (DEFAULT_CHAT, DEFAULT_PROJECT, WorkspaceConflictError,
    append_message, artifact_catalog, attach_returned, bootstrap_workspace, chat_snapshot,
    for_chat, mutate_workspace, parse_catalog_query, parse_chat_query, read_context,
    save_state, workspace_index)
from swarm_lab.pipeline import Lab
from swarm_lab.server import LocalResearchServer, serve
from swarm_lab.store import StoreConflictError


def ref(obj): return {key: obj[key] for key in ('id', 'version', 'hash')}


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.lab = Lab(Settings(root=Path(self.temp.name), max_calls=0))
        self.original = self.lab.store.put('experiment', {'status': 'complete', 'analysis': {'success': 1},
            'runs': [{'outcomes': {'success': 1}}], 'claim_scope': 'Authored temporary report fixture, no empirical result.'})
        bootstrap_workspace(self.lab)

    def new_chat(self, name='Another project task'):
        return mutate_workspace(self.lab, {'op': 'create_chat', 'project_id': DEFAULT_PROJECT,
            'name': name, 'request_id': 'create-' + name.replace(' ', '-')})['chat']

    def test_bootstrap_is_once_and_does_not_retarget_original_or_later_object_versions(self):
        initial = chat_snapshot(self.lab, DEFAULT_CHAT)
        self.lab.store.put('experiment', {**self.original['payload'], 'later': True}, self.original['id'])
        before = self.lab.store.usage()
        bootstrap_workspace(self.lab)
        after = chat_snapshot(self.lab, DEFAULT_CHAT)
        self.assertEqual(after, initial)
        self.assertEqual(after['artifacts'][0]['ref'], ref(self.original))
        self.assertEqual(after['artifacts'][0]['relation'], 'reference')
        self.assertEqual(self.lab.store.usage(), before)
        reopened = Lab(self.lab.settings)
        self.assertEqual(chat_snapshot(reopened, DEFAULT_CHAT), initial)

    def test_first_bootstrap_catalog_preserves_every_preexisting_original_version(self):
        with tempfile.TemporaryDirectory() as directory:
            lab = Lab(Settings(root=Path(directory), max_calls=0))
            first = lab.store.put('theory', {'status': 'hypothesis', 'statement': 'First authored fixture'})
            second = lab.store.put('theory', {'status': 'hypothesis', 'statement': 'Changed authored fixture'}, first['id'])
            before = lab.store.history(first['id'])
            bootstrap_workspace(lab)
            self.assertEqual({(row['ref']['id'], row['ref']['version'], row['ref']['hash']) for row in artifact_catalog(lab)['artifacts']},
                {(obj['id'], obj['version'], obj['hash']) for obj in (first, second)})
            self.assertEqual(lab.store.history(first['id']), before)
            self.assertEqual(chat_snapshot(lab, DEFAULT_CHAT)['state'], {})

    def test_idempotent_creation_and_append_claim_survive_reload_with_no_duplicate_writer(self):
        chat = self.new_chat(); body = {'op': 'create_chat', 'project_id': DEFAULT_PROJECT,
            'name': 'Another project task', 'request_id': 'create-Another-project-task'}
        self.assertIs(mutate_workspace(self.lab, body)['reused'], True)
        with self.assertRaises(ValueError): mutate_workspace(self.lab, body | {'name': 'Different body'})
        def claim(_): return append_message(self.lab, chat['id'], role='user', content='Inspect this saved experiment',
            metadata={'unverified': True}, request_id='turn-one.user')
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool: claims = list(pool.map(claim, range(6)))
        self.assertEqual(sum(not item['reused'] for item in claims), 1)
        self.assertEqual(len({item['message']['id'] for item in claims}), 1)
        snapshot = chat_snapshot(Lab(self.lab.settings), chat['id'])
        self.assertEqual(len(snapshot['messages']), 1)
        self.assertEqual(snapshot['messages'][0]['request_id'], 'turn-one.user')
        self.assertEqual(snapshot['messages'][0]['metadata'], {'unverified': True})
        with self.assertRaises(ValueError): append_message(self.lab, chat['id'], role='user', content='Different input', request_id='turn-one.user', metadata={'unverified': True})

    def test_state_compare_and_swap_preserves_winner_and_rejects_source_and_type_drift(self):
        chat = self.new_chat(); version = chat['revision']
        state = {'view': 'findings', 'context': {'result_ref': ref(self.original)},
                 'ui': {'journey': {'tab': 'results'}, 'replay': {'position': 2}}, 'plan_draft': {'question': '', 'control_text': '', 'treatment_text': ''}}
        saved = save_state(self.lab, chat['id'], expected_revision=version, state=state, request_id='state-one')
        self.assertEqual(saved['chat']['state'], state)
        with self.assertRaises(WorkspaceConflictError) as error:
            save_state(self.lab, chat['id'], expected_revision=version, state={'view': 'home'}, request_id='state-stale')
        self.assertEqual(error.exception.latest_revision, saved['chat']['revision'])
        for invalid in (True, 1.0):
            with self.assertRaises(ValueError): save_state(self.lab, chat['id'], expected_revision=invalid, state={}, request_id='bad-version-' + str(invalid))
        for invalid in ({'view': 'execute_code'}, {'context': {'result_ref': ref(self.original) | {'hash': '0' * 64}}}, {'context': {'dataset_ref': ref(self.original)}}, {'ui': {'number': float('nan')}}):
            with self.assertRaises(ValueError): save_state(self.lab, chat['id'], expected_revision=saved['chat']['revision'], state=invalid, request_id='invalid-state')
        self.assertEqual(chat_snapshot(self.lab, chat['id'])['state'], state)

    def test_concurrent_state_writers_have_one_winner_without_lost_update(self):
        chat = self.new_chat()
        def write(index):
            try: return save_state(self.lab, chat['id'], expected_revision=chat['revision'], state={'notes': str(index)}, request_id='concurrent-' + str(index))
            except WorkspaceConflictError: return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: rows = list(pool.map(write, range(4)))
        self.assertEqual(sum(row is not None for row in rows), 1)
        self.assertEqual(chat_snapshot(self.lab, chat['id'])['revision'], chat['revision'] + 1)

    def test_reuse_is_exact_reference_and_clone_cannot_create_empirical_or_verification_status(self):
        target = self.new_chat()
        reused = mutate_workspace(self.lab, {'op': 'reuse_artifact', 'request_id': 'reuse-one', 'origin_chat_id': DEFAULT_CHAT,
            'target_chat_id': target['id'], 'artifact_ref': ref(self.original)})
        self.assertEqual(reused['artifact_ref'], ref(self.original))
        self.assertEqual(len(self.lab.store.history(self.original['id'])), 1)
        self.assertEqual(reused['chat']['artifacts'][0]['relation'], 'reused')
        copied = mutate_workspace(self.lab, {'op': 'clone_artifact', 'request_id': 'copy-one', 'origin_chat_id': DEFAULT_CHAT,
            'target_chat_id': target['id'], 'artifact_ref': ref(self.original)})
        draft = self.lab.store.get(copied['artifact_ref']['id'])
        self.assertEqual(draft['kind'], 'workspace_draft')
        self.assertEqual(draft['payload']['status'], 'editable_draft')
        self.assertEqual(draft['payload']['original_source_ref'], ref(self.original))
        self.assertIs(draft['payload']['copied_empirical_outcomes'], False)
        self.assertFalse({'runs', 'analysis', 'outcomes', 'passed', 'verification'} & set(draft['payload']['editable_fields']))
        self.assertEqual(self.lab.store.get(self.original['id']), self.original)
        unlinked = self.new_chat('No original link')
        with self.assertRaises(ValueError): mutate_workspace(self.lab, {'op': 'reuse_artifact', 'request_id': 'false-origin',
            'origin_chat_id': unlinked['id'], 'target_chat_id': target['id'], 'artifact_ref': ref(self.original)})

    def test_guided_copy_can_edit_its_own_draft_but_not_the_frozen_source_or_another_chats_copy(self):
        source = for_chat(self.lab, DEFAULT_CHAT).store.put('guided_plan', {'question': 'Original question', 'control_text': 'Neutral note',
            'treatment_text': 'Inspect evidence', 'trials_per_arm': 2, 'max_rounds': 4, 'valid_probability': .25, 'seed': 77, 'source_ref': None,
            'status': 'reviewed_for_live_study'})
        target = self.new_chat()
        copied = mutate_workspace(self.lab, {'op': 'clone_artifact', 'request_id': 'copy-plan', 'origin_chat_id': DEFAULT_CHAT,
            'target_chat_id': target['id'], 'artifact_ref': ref(source)})
        draft = self.lab.store.get(copied['artifact_ref']['id'])
        self.assertEqual(draft['payload']['editable_fields']['seed'], 77)
        self.assertEqual(draft['payload']['editable_fields']['source_brief_ref'], None)
        update = {'op': 'update_draft', 'request_id': 'draft-update', 'chat_id': target['id'], 'draft_ref': ref(draft),
                  'fields': {'question': 'A new prospective question', 'control_text': 'New neutral note'}}
        result = mutate_workspace(self.lab, update)
        self.assertEqual(result['artifact_ref']['version'], 2)
        self.assertEqual(self.lab.store.get(draft['id'], 1), draft)
        self.assertEqual(self.lab.store.get(source['id']), source)
        self.assertEqual(self.lab.store.get(draft['id'], 2)['payload']['editable_fields']['question'], 'A new prospective question')
        with self.assertRaises(ValueError): mutate_workspace(self.lab, update | {'request_id': 'stale-draft-update'})
        with self.assertRaises(ValueError): mutate_workspace(self.lab, update | {'request_id': 'wrong-owner', 'chat_id': DEFAULT_CHAT, 'draft_ref': result['artifact_ref']})
        with self.assertRaises(ValueError): mutate_workspace(self.lab, update | {'request_id': 'status-inflation', 'draft_ref': result['artifact_ref'], 'fields': {'status': 'complete'}})

    def test_fork_preserves_exact_origin_history_but_edits_do_not_modify_original(self):
        append_message(self.lab, DEFAULT_CHAT, role='user', content='Original recorded question', request_id='source.user')
        original = chat_snapshot(self.lab, DEFAULT_CHAT)
        fork = mutate_workspace(self.lab, {'op': 'fork_chat', 'origin_chat_id': DEFAULT_CHAT, 'expected_revision': original['revision'],
            'name': 'A separate investigation', 'request_id': 'f' * 200})['chat']
        self.assertEqual(fork['origin'], {'chat_id': DEFAULT_CHAT, 'revision': original['revision'], 'snapshot_hash': original['snapshot_hash']})
        self.assertEqual(fork['messages'][0]['content'], original['messages'][0]['content'])
        self.assertEqual(fork['artifacts'][0]['ref'], original['artifacts'][0]['ref'])
        self.assertNotEqual(fork['messages'][0]['id'], original['messages'][0]['id'])
        self.assertLessEqual(len(fork['messages'][0]['request_id']), 200)
        save_state(self.lab, fork['id'], expected_revision=fork['revision'], state={'notes': 'Separate draft'}, request_id='fork-edit')
        self.assertEqual(chat_snapshot(self.lab, DEFAULT_CHAT), original)

    def test_context_is_bounded_readonly_and_historical_revision_does_not_include_future_posts(self):
        original = chat_snapshot(self.lab, DEFAULT_CHAT)
        for i in range(15): append_message(self.lab, DEFAULT_CHAT, role='assistant', content='x' * 2000, request_id='reply-' + str(i), metadata={'untrusted': 'Discussion only'})
        before = (self.lab.store.list(), self.lab.store.jobs(), self.lab.store.usage())
        context = read_context(self.lab, DEFAULT_CHAT)
        self.assertLessEqual(len(context['messages']), 12)
        self.assertLessEqual(sum(len(row['content']) for row in context['messages']), 6000)
        self.assertIs(context['messages_truncated'], True)
        self.assertTrue(all('metadata' not in row for row in context['messages']))
        self.assertEqual(read_context(self.lab, DEFAULT_CHAT, revision=original['revision'])['messages'], [])
        self.assertEqual((self.lab.store.list(), self.lab.store.jobs(), self.lab.store.usage()), before)

    def test_source_context_link_hash_and_revision_are_checked_and_saved_as_borrowed_context(self):
        source = chat_snapshot(self.lab, DEFAULT_CHAT); target = self.new_chat()
        link = {'chat_id': source['id'], 'revision': source['revision'], 'snapshot_hash': source['snapshot_hash']}
        saved = save_state(self.lab, target['id'], expected_revision=target['revision'], state={'context_links': [link]}, request_id='link-source')
        self.assertEqual(saved['chat']['context_links'], [link])
        with self.assertRaises(ValueError): save_state(self.lab, target['id'], expected_revision=saved['chat']['revision'], state={'context_links': [link | {'snapshot_hash': '0' * 64}]}, request_id='bad-link')

    def test_scoped_put_and_cas_keep_payloads_exact_and_preserve_atomic_job_semantics(self):
        target = self.new_chat(); scoped = for_chat(self.lab, target['id'])
        payload = {'question': 'An authored candidate, not scientific evidence'}
        original = scoped.store.put('behavior', payload)
        self.assertEqual(original['payload'], payload)
        updated = scoped.store.compare_and_put('behavior', {'question': 'Another authored candidate'}, original['id'],
            expected_version=original['version'], expected_hash=original['hash'],
            job_updates=[{'id': 'fixed-job', 'status': 'completed', 'payload': {'result_id': original['id']}, 'preserve_completed': False}])
        self.assertEqual(updated['version'], 2)
        self.assertEqual(self.lab.store.get_job('fixed-job')['payload']['origin_chat_id'], target['id'])
        with self.assertRaises(StoreConflictError): scoped.store.compare_and_put('behavior', payload, original['id'], expected_version=1, expected_hash=original['hash'])
        refs = [row['ref'] for row in chat_snapshot(self.lab, target['id'])['artifacts']]
        self.assertEqual(refs, [ref(original), ref(updated)])
        for invalid in (1, {}, 'bad'):
            with self.assertRaises(ValueError): scoped.store.compare_and_put('behavior', payload, original['id'],
                expected_version=updated['version'], expected_hash=updated['hash'], job_updates=invalid)
        self.assertEqual(len(self.lab.store.history(original['id'])), 2)
        self.assertEqual(self.lab.store.usage()['calls'], 0)

    def test_direct_sql_endpoint_outputs_link_exact_versions_and_catalog_deduplicates_nodes(self):
        target = self.new_chat(); linked = for_chat(self.lab, DEFAULT_CHAT).store.put('theory', {'name': 'Authored hypothesis', 'source_refs': {'result': ref(self.original)}})
        attach_returned(self.lab, target['id'], {'theory_ref': ref(linked)})
        catalog = artifact_catalog(self.lab)
        self.assertEqual(len({(row['ref']['id'], row['ref']['version']) for row in catalog['artifacts']}), len(catalog['artifacts']))
        node = next(row for row in catalog['artifacts'] if row['ref'] == ref(linked))
        self.assertEqual(len(node['origins']), 2)
        self.assertTrue(any(row['from_ref'] == ref(self.original) and row['to_ref'] == ref(linked) for row in catalog['edges']))
        bounded = artifact_catalog(self.lab, limit=1)
        self.assertIs(bounded['truncated'], True)
        self.assertEqual(bounded['next_cursor'], '1')
        self.assertEqual(bounded['edges'], [])

    def test_request_query_and_structure_boundaries_fail_before_mutation(self):
        invalid = [b'{"op":"create_project","op":"create_chat","request_id":"duplicate","name":"x"}',
            b'{"op":"create_project","request_id":"nan","name":"x","value":NaN}',
            json.dumps({'op': 'create_project', 'request_id': 'blank', 'name': ' '}).encode(),
            json.dumps({'op': 'fork_chat', 'origin_chat_id': DEFAULT_CHAT, 'expected_revision': True, 'name': 'Bad', 'request_id': 'bad-bool'}).encode(),
            json.dumps({'op': 'create_project', 'request_id': 'extra', 'name': 'x', 'execute': 'arbitrary'}).encode()]
        initial = workspace_index(self.lab)
        for raw in invalid:
            with self.subTest(raw=raw[:100]), self.assertRaises(ValueError): mutate_workspace(self.lab, raw)
        for query in ({'chat_id': ['']}, {'chat_id': [DEFAULT_CHAT, DEFAULT_CHAT]}, {'chat_id': [DEFAULT_CHAT], 'extra': ['1']}):
            with self.assertRaises(ValueError): parse_chat_query(query)
        self.assertEqual(parse_chat_query({'chat_id': [DEFAULT_CHAT], 'revision': ['1']}), {'chat_id': DEFAULT_CHAT, 'revision': 1})
        for version in ('01', '0', 'true', '1.0', '', '1000000001'):
            with self.assertRaises(ValueError): parse_chat_query({'chat_id': [DEFAULT_CHAT], 'revision': [version]})
        for query in ({'scope': ['all', 'chat']}, {'limit': ['01']}, {'extra': ['1']}):
            with self.assertRaises(ValueError): parse_catalog_query(query)
        self.assertEqual(workspace_index(self.lab), initial)


class WorkspaceHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.lab = Lab(Settings(root=Path(self.temp.name), max_calls=0))
        self.servers = []; self.executors = []
        with socket.socket() as handle: handle.bind(('127.0.0.1', 0)); self.port = handle.getsockname()[1]
        original_pool = concurrent.futures.ThreadPoolExecutor
        def server(*args, **kwargs):
            value = LocalResearchServer(*args, **kwargs); self.servers.append(value); return value
        def pool(*args, **kwargs):
            value = original_pool(*args, **kwargs); self.executors.append(value); return value
        self.patches = [patch('swarm_lab.server.LocalResearchServer', side_effect=server),
                        patch('swarm_lab.server.concurrent.futures.ThreadPoolExecutor', side_effect=pool)]
        for item in self.patches: item.start()
        self.thread = threading.Thread(target=serve, args=(self.lab, self.port), daemon=True); self.thread.start()
        self.addCleanup(self.shutdown)
        self.base = 'http://127.0.0.1:' + str(self.port)
        deadline = time.monotonic() + 8
        while True:
            try: self.csrf = self.get('/api/state')['csrf']; break
            except urllib.error.URLError:
                if time.monotonic() > deadline: raise
                time.sleep(.02)

    def shutdown(self):
        for server in self.servers: server.shutdown()
        self.thread.join(8)
        for pool in self.executors: pool.shutdown(wait=True, cancel_futures=True)
        for item in reversed(self.patches): item.stop()
        self.assertFalse(self.thread.is_alive())

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=8) as response: return json.load(response)

    def post(self, path, body, chat=None, token=True):
        headers = {'Content-Type': 'application/json'}
        if token: headers['X-Lab-Token'] = self.csrf
        if chat is not None: headers['X-Lab-Chat'] = chat
        request = urllib.request.Request(self.base + path, data=json.dumps(body).encode(), headers=headers)
        with urllib.request.urlopen(request, timeout=8) as response: return json.load(response)

    def test_actual_loopback_workspace_csrf_persistence_cas_and_uncached_exact_object_reads(self):
        index = self.get('/api/workspaces')
        self.assertEqual(index['default_chat_id'], DEFAULT_CHAT)
        body = {'op': 'create_chat', 'project_id': DEFAULT_PROJECT, 'name': 'HTTP authored task', 'request_id': 'http-create'}
        with self.assertRaises(urllib.error.HTTPError) as error: self.post('/api/workspaces', body, token=False)
        self.assertEqual(error.exception.code, 403)
        chat = self.post('/api/workspaces', body)['chat']
        saved = self.post('/api/workspaces', {'op': 'save_state', 'request_id': 'http-save', 'chat_id': chat['id'],
            'expected_revision': chat['revision'], 'state': {'view': 'watch', 'ui': {'journey': {'mode': 'discussion'}}}})['chat']
        self.assertEqual(self.get('/api/workspaces/chat?chat_id=' + chat['id']), saved)
        with self.assertRaises(urllib.error.HTTPError) as error: self.post('/api/workspaces', {'op': 'save_state',
            'request_id': 'http-stale', 'chat_id': chat['id'], 'expected_revision': chat['revision'], 'state': {}})
        self.assertEqual(error.exception.code, 409)
        self.assertEqual(self.get('/api/workspaces/context?chat_id=' + chat['id'])['revision'], saved['revision'])
        original_query = '?chat_id=' + chat['id'] + '&revision=' + str(chat['revision'])
        original = self.get('/api/workspaces/chat' + original_query)
        historical = self.get('/api/workspaces/context' + original_query)
        self.assertEqual(original, chat)
        self.assertEqual(historical['snapshot_hash'], chat['snapshot_hash'])
        self.assertEqual(historical['state'], {})
        for tail in ('&chat_id=x', '&extra=1'):
            with self.assertRaises(urllib.error.HTTPError): self.get('/api/workspaces/chat?chat_id=' + chat['id'] + tail)
        for tail in ('&revision=01', '&revision=1&revision=1'):
            with self.assertRaises(urllib.error.HTTPError): self.get('/api/workspaces/context?chat_id=' + chat['id'] + tail)
        self.assertEqual(self.lab.store.usage()['calls'], 0)

    def test_background_job_origin_remains_original_chat_while_other_chat_changes(self):
        origin = self.post('/api/workspaces', {'op': 'create_chat', 'project_id': DEFAULT_PROJECT, 'name': 'Original task', 'request_id': 'origin-create'})['chat']
        target = self.post('/api/workspaces', {'op': 'create_chat', 'project_id': DEFAULT_PROJECT, 'name': 'Another task', 'request_id': 'target-create'})['chat']
        started, release = threading.Event(), threading.Event()
        original_ingest = Lab.ingest
        def delayed(self_lab, *args, **kwargs):
            started.set()
            if not release.wait(8): raise RuntimeError('Authored fixture timed out')
            return original_ingest(self_lab, *args, **kwargs)
        with patch.object(Lab, 'ingest', delayed):
            result = self.post('/api/jobs', {'action': 'ingest', 'args': {'source': str(ROOT / 'examples' / 'coordination_fixture'), 'limit': 100}}, chat=origin['id'])
            self.assertTrue(started.wait(5))
            self.post('/api/workspaces', {'op': 'save_state', 'request_id': 'switch-task', 'chat_id': target['id'],
                'expected_revision': target['revision'], 'state': {'view': 'plan', 'notes': 'Different working context'}})
            release.set(); deadline = time.monotonic() + 8
            while True:
                job = self.lab.store.get_job(result['job_id'])
                if job['status'] in ('completed', 'failed'): break
                if time.monotonic() > deadline: self.fail('Background queue did not finish')
                time.sleep(.02)
        self.assertEqual(job['status'], 'completed')
        self.assertEqual(job['payload']['origin_chat_id'], origin['id'])
        artifacts = self.get('/api/workspaces/chat?chat_id=' + origin['id'])['artifacts']
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0]['kind'], 'dataset')
        self.assertEqual(self.get('/api/workspaces/chat?chat_id=' + target['id'])['artifacts'], [])
        self.assertEqual(self.lab.store.usage()['calls'], 0)

    def test_invalid_origin_refuses_before_queue_or_hosted_work_and_absent_header_stays_compatible(self):
        before = self.lab.store.jobs()
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.post('/api/jobs', {'action': 'observe', 'args': {'dataset_id': 'missing', 'live': True}}, chat='missing-chat')
        self.assertEqual(error.exception.code, 400)
        self.assertEqual(self.lab.store.jobs(), before)
        self.assertEqual(self.lab.store.usage()['calls'], 0)
        result = self.post('/api/jobs', {'action': 'ingest', 'args': {'source': str(ROOT / 'examples' / 'coordination_fixture'), 'limit': 100}})
        deadline = time.monotonic() + 8
        while self.lab.store.get_job(result['job_id'])['status'] not in ('completed', 'failed'):
            if time.monotonic() > deadline: self.fail('Legacy queue did not finish')
            time.sleep(.02)
        self.assertEqual(self.lab.store.get_job(result['job_id'])['status'], 'completed')
        self.assertNotIn('origin_chat_id', self.lab.store.get_job(result['job_id'])['payload'])

    def test_guide_header_and_active_chat_mismatch_refuses_before_any_model_or_operation(self):
        other = self.post('/api/workspaces', {'op': 'create_chat', 'project_id': DEFAULT_PROJECT,
            'name': 'Other guide origin', 'request_id': 'other-guide-create'})['chat']
        before = (self.lab.store.usage(), self.lab.store.jobs(), chat_snapshot(self.lab, DEFAULT_CHAT), chat_snapshot(self.lab, other['id']))
        with patch('swarm_lab.guide_assistant.guide_chat', side_effect=AssertionError('Must reject before guide work')):
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.post('/api/guide/chat', {'message': 'Create a project named Wrong Origin.',
                    'current_view': 'workspace', 'active_chat_id': other['id'], 'request_id': 'wrong-origin-turn'}, chat=DEFAULT_CHAT)
        self.assertEqual(error.exception.code, 400)
        self.assertEqual((self.lab.store.usage(), self.lab.store.jobs(), chat_snapshot(self.lab, DEFAULT_CHAT), chat_snapshot(self.lab, other['id'])), before)
        self.assertEqual(self.get('/api/guide/activity?chat_id=' + DEFAULT_CHAT)['events'], [])
        for tail in ('&revision=1', '&chat_id=' + DEFAULT_CHAT, '&extra=1'):
            with self.assertRaises(urllib.error.HTTPError): self.get('/api/guide/activity?chat_id=' + DEFAULT_CHAT + tail)


if __name__ == '__main__': unittest.main()
