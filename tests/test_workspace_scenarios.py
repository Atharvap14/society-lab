"""Predeclared long workspace transitions against temporary stores/API, no models.

The reference model tracks user-visible branch state, messages and exact links.
It does not reuse the implementation's validators or database revision logic.
All source rows and outcomes in these tests are authored software fixtures.
"""
import copy
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import tempfile
import threading
import time
import unittest
import urllib.error
from unittest.mock import patch

from swarm_lab.config import ROOT, Settings
from swarm_lab.lab_workspace import (DEFAULT_CHAT, DEFAULT_PROJECT, bootstrap_workspace,
    chat_snapshot, for_chat, mutate_workspace, read_context, workspace_index)
from swarm_lab.pipeline import Lab
from tests import test_lab_workspace as http_fixture


MANIFEST = ROOT / 'docs' / 'user-flow-scenarios.json'
REPORT = ROOT / '.runtime' / 'workspace-scenario-results.json'
RESULTS = {}


def exact(obj): return {key: obj[key] for key in ('id', 'version', 'hash')}
def marker(ref): return (ref['id'], ref['version'], ref['hash'])
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_report():
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    packet = {'schema_version': 'societylab.user-flow-results.v1',
        'preregistered_manifest_sha256': sha(MANIFEST),
        'implementation_sha256': sha(ROOT / 'swarm_lab' / 'lab_workspace.py'),
        'server_sha256': sha(ROOT / 'swarm_lab' / 'server.py'),
        'tests_sha256': sha(__file__), 'source_kind': 'authored_test_fixture',
        'scope': 'Temporary software state-transition validation; not model behavior, scientific replication, or upstream source verification.',
        'provider_calls': 0, 'production_registry_writes': 0,
        'prior_failure': {'copy_of_copy_content_loss': 'Reproduced before the narrow authorized correction; its regression remains in the preparation spine.'},
        'expected': json.loads(MANIFEST.read_text(encoding='utf-8'))['predeclared_invariants'],
        'observed': RESULTS}
    REPORT.write_text(json.dumps(packet, indent=2, sort_keys=True), encoding='utf-8')


def database_state(lab):
    """Exact rows, not newest-only objects, so a rejected request cannot hide writes."""
    with lab.store.connect() as connection:
        tables = ('objects', 'jobs', 'calls', 'traces', 'workspace_projects', 'workspace_chats',
            'workspace_chat_revisions', 'workspace_messages', 'workspace_artifacts', 'workspace_requests')
        return {table: sorted((tuple(row) for row in connection.execute('SELECT * FROM ' + table)), key=repr)
            for table in tables}


class ReferenceBranches:
    def __init__(self):
        self.chats = {}
        self.projects = {DEFAULT_PROJECT}
        self.objects = {}
        self.drafts = {}

    def add_chat(self, identity, project, *, state=None, messages=None, links=None, origin=None):
        self.chats[identity] = {'project_id': project, 'revision': 1,
            'state': copy.deepcopy(state or {}), 'messages': list(messages or []),
            'links': set(links or ()), 'origin': copy.deepcopy(origin)}

    def link(self, chat, reference):
        branch = self.chats[chat]; key = marker(reference)
        if key not in branch['links']:
            branch['links'].add(key); branch['revision'] += 1

    def assert_matches(self, test, lab):
        index = workspace_index(lab)
        test.assertEqual({item['id'] for item in index['projects']}, self.projects)
        test.assertEqual({chat['id'] for project in index['projects'] for chat in project['chats']}, set(self.chats))
        for identity, expected in self.chats.items():
            actual = chat_snapshot(lab, identity)
            test.assertEqual(actual['project_id'], expected['project_id'])
            test.assertEqual(actual['revision'], expected['revision'])
            test.assertEqual(actual['state'], expected['state'])
            test.assertEqual(actual['origin'], expected['origin'])
            test.assertEqual([(row['role'], row['content']) for row in actual['messages']], expected['messages'])
            test.assertEqual([row['sequence'] for row in actual['messages']], list(range(1, len(expected['messages']) + 1)))
            test.assertEqual({marker(row['ref']) for row in actual['artifacts']}, expected['links'])
        for (identity, version, digest), obj in self.objects.items():
            actual = lab.store.get(identity, version)
            test.assertEqual(actual, obj)
            test.assertEqual(actual['hash'], digest)


class WorkspaceScenarioTests(unittest.TestCase):
    def test_generated_sequences_match_predeclared_branch_and_provenance_invariants(self):
        specification = json.loads(MANIFEST.read_text(encoding='utf-8'))
        self.assertEqual(specification['generated_sequences']['seeds'], [7, 42, 2026])
        for seed in specification['generated_sequences']['seeds']:
            with self.subTest(seed=seed):
                result = {'expected_operations': 60, 'observed_operations': 0, 'status': 'started',
                    'source_scope': 'Authored isolated rows, no providers or production database.'}
                RESULTS['seed-' + str(seed)] = result
                try:
                    self.run_sequence(seed, specification, result)
                    result['status'] = 'passed'
                except Exception as error:
                    result['status'] = 'failed'; result['error_type'] = type(error).__name__
                    raise
                finally: write_report()

    def run_sequence(self, seed, specification, result):
        with tempfile.TemporaryDirectory() as directory:
            lab = Lab(Settings(root=Path(directory), max_calls=0))
            brief = lab.store.put('observation_brief', {'source_kind': 'authored_test_fixture', 'summary': 'Software fixture only'})
            plan = lab.store.put('guided_plan', {'question': 'Authored prospective question', 'control_text': 'Neutral fixture note',
                'treatment_text': 'Check fixture files', 'trials_per_arm': 2, 'max_rounds': 3,
                'valid_probability': .5, 'seed': seed, 'source_ref': exact(brief), 'status': 'authored_test_fixture'})
            report = lab.store.put('experiment', {'source_kind': 'authored_test_fixture', 'status': 'complete',
                'analysis': {'success': 1}, 'runs': [{'outcomes': {'success': 1}}],
                'claim_scope': 'Authored test result; no empirical finding.'})
            bootstrap_workspace(lab)
            model = ReferenceBranches()
            for obj in (brief, plan, report): model.objects[marker(exact(obj))] = copy.deepcopy(obj)
            model.add_chat(DEFAULT_CHAT, DEFAULT_PROJECT, links=[marker(exact(obj)) for obj in (brief, plan, report)])
            generator = random.Random(seed); requests = []; histories = []; counts = Counter(); serial = 0

            def request(body):
                nonlocal serial
                serial += 1
                body = {'request_id': 'scenario-' + str(seed) + '-' + str(serial), **copy.deepcopy(body)}
                value = mutate_workspace(lab, body)
                self.assertIs(value['reused'], False)
                requests.append((copy.deepcopy(body), copy.deepcopy(value)))
                return value

            def remember_obj(reference):
                obj = lab.store.get(reference['id'], reference['version'])
                self.assertEqual(exact(obj), reference)
                model.objects[marker(reference)] = copy.deepcopy(obj)
                return obj

            def new_chat(project):
                value = request({'op': 'create_chat', 'project_id': project, 'name': 'Authored branch ' + str(serial)})['chat']
                model.add_chat(value['id'], project)
                return value['id']

            def copy_artifact(origin, target, reference):
                source = model.objects[marker(reference)]
                value = request({'op': 'clone_artifact', 'origin_chat_id': origin, 'target_chat_id': target, 'artifact_ref': reference})
                obj = remember_obj(value['artifact_ref']); payload = obj['payload']
                if source['kind'] == 'workspace_draft':
                    expected_fields = copy.deepcopy(model.drafts[source['id']]['versions'][source['version']])
                elif source['kind'] == 'guided_plan':
                    expected_fields = {key: copy.deepcopy(source['payload'][key]) for key in
                        ('question', 'control_text', 'treatment_text', 'trials_per_arm', 'max_rounds', 'valid_probability', 'seed')}
                    expected_fields['source_brief_ref'] = exact(brief)
                elif source['kind'] == 'experiment':
                    expected_fields = {'question': '', 'notes': 'Authored test result; no empirical finding.'}
                else:
                    expected_fields = {'statement': source['payload']['statement']} if 'statement' in source['payload'] else {}
                self.assertEqual(payload['editable_fields'], expected_fields)
                self.assertEqual(payload['source_ref'], reference)
                self.assertEqual(payload['original_source_ref'], reference)
                self.assertEqual(payload['source_kind'], source['kind'])
                self.assertEqual(payload['owner_chat_id'], target)
                self.assertEqual(payload['status'], 'editable_draft')
                self.assertIs(payload['copied_empirical_outcomes'], False)
                self.assertFalse({'analysis', 'outcomes', 'runs', 'passed', 'verification', 'causal_support'} & set(payload['editable_fields']))
                model.drafts[obj['id']] = {'owner': target, 'latest': exact(obj), 'versions': {1: copy.deepcopy(expected_fields)}}
                model.link(target, exact(obj))
                return obj

            def edit(draft):
                item = model.drafts[draft['id']]; old = copy.deepcopy(item['versions'][item['latest']['version']])
                changes = {'question': 'Prospective edit ' + str(serial), 'notes': 'Working interpretation, unverified ' + str(seed)}
                value = request({'op': 'update_draft', 'chat_id': item['owner'], 'draft_ref': item['latest'], 'fields': changes})
                obj = remember_obj(value['artifact_ref']); expected = {**old, **changes}
                self.assertEqual(obj['payload']['editable_fields'], expected)
                self.assertEqual(obj['payload']['previous_ref'], item['latest'])
                self.assertEqual(obj['payload']['source_ref'], draft['payload']['source_ref'])
                item['latest'] = exact(obj); item['versions'][obj['version']] = copy.deepcopy(expected)
                model.link(item['owner'], exact(obj))
                return obj

            # Fixed preparation declares projects, own copies, retained copy content and a branch.
            project = request({'op': 'create_project', 'name': 'Authored project ' + str(seed)})['project']['id']
            model.projects.add(project)
            a, b = new_chat(project), new_chat(DEFAULT_PROJECT)
            draft = copy_artifact(DEFAULT_CHAT, a, exact(plan)); edited = edit(draft)
            second = copy_artifact(a, b, exact(edited))
            self.assertEqual(second['payload']['editable_fields']['source_brief_ref'], exact(brief))
            copy_artifact(DEFAULT_CHAT, b, exact(report))
            model.assert_matches(self, lab)

            # Rejected typed/ownership/identity transitions must roll back all tables.
            for invalid in (True, 1.0):
                before = database_state(lab)
                with self.assertRaises(ValueError): mutate_workspace(lab, {'op': 'save_state', 'request_id': 'bad-type-' + str(invalid),
                    'chat_id': a, 'expected_revision': invalid, 'state': {}})
                self.assertEqual(database_state(lab), before)
            before = database_state(lab)
            with self.assertRaises(ValueError): mutate_workspace(lab, {'op': 'update_draft', 'request_id': 'foreign-edit',
                'chat_id': a, 'draft_ref': exact(second), 'fields': {'notes': 'Forbidden foreign edit'}})
            with self.assertRaises(KeyError): mutate_workspace(lab, {'op': 'create_chat', 'request_id': 'invented-project',
                'project_id': 'project-nonexistent', 'name': 'Invalid branch'})
            self.assertEqual(database_state(lab), before)

            for index in range(60):
                operation = generator.choice(specification['generated_sequences']['operations'])
                counts[operation] += 1
                chosen = generator.choice(list(model.chats))
                old_snapshot = chat_snapshot(lab, chosen); histories.append(copy.deepcopy(old_snapshot))
                if operation == 'create_chat':
                    new_chat(generator.choice(sorted(model.projects)))
                elif operation == 'save_state':
                    state = {'view': generator.choice(['workspace', 'plan', 'watch', 'findings']), 'notes': 'Independent local note ' + str(index),
                        'context': {'result_ref': exact(report)}, 'ui': {'journey': {'marker': index}, 'replay': {'position': index % 4}}}
                    request({'op': 'save_state', 'chat_id': chosen, 'expected_revision': model.chats[chosen]['revision'], 'state': state})
                    model.chats[chosen]['state'] = copy.deepcopy(state); model.chats[chosen]['revision'] += 1
                elif operation == 'append_message':
                    role = generator.choice(['user', 'assistant']); content = 'Authored discussion ' + str(seed) + ':' + str(index)
                    request({'op': 'append_message', 'chat_id': chosen, 'role': role, 'content': content, 'metadata': {'unverified': True}})
                    model.chats[chosen]['messages'].append((role, content)); model.chats[chosen]['revision'] += 1
                elif operation in ('reuse_artifact', 'copy_artifact'):
                    origin = generator.choice([name for name, branch in model.chats.items() if branch['links']])
                    key = generator.choice(sorted(model.chats[origin]['links'])); reference = exact(model.objects[key])
                    if operation == 'copy_artifact': copy_artifact(origin, chosen, reference)
                    else:
                        value = request({'op': 'reuse_artifact', 'origin_chat_id': origin, 'target_chat_id': chosen, 'artifact_ref': reference})
                        self.assertEqual(value['artifact_ref'], reference); model.link(chosen, reference)
                elif operation == 'edit_copy':
                    identity = generator.choice(sorted(model.drafts)); item = model.drafts[identity]
                    edit(model.objects[marker(item['latest'])])
                elif operation == 'fork_chat':
                    original = model.chats[chosen]
                    value = request({'op': 'fork_chat', 'origin_chat_id': chosen, 'expected_revision': original['revision'], 'name': 'Authored fork ' + str(index)})['chat']
                    origin_pin = {'chat_id': chosen, 'revision': old_snapshot['revision'], 'snapshot_hash': old_snapshot['snapshot_hash']}
                    model.add_chat(value['id'], original['project_id'], state=original['state'], messages=original['messages'], links=original['links'], origin=origin_pin)
                elif operation == 'stale_cas':
                    if model.chats[chosen]['revision'] == 1:
                        request({'op': 'append_message', 'chat_id': chosen, 'role': 'user', 'content': 'Move branch beyond revision one'})
                        model.chats[chosen]['messages'].append(('user', 'Move branch beyond revision one')); model.chats[chosen]['revision'] += 1
                    before = database_state(lab)
                    with self.assertRaises(ValueError): mutate_workspace(lab, {'op': 'save_state', 'request_id': 'stale-' + str(seed) + '-' + str(index),
                        'chat_id': chosen, 'expected_revision': model.chats[chosen]['revision'] - 1, 'state': {'notes': 'Must not overwrite'}})
                    self.assertEqual(database_state(lab), before)
                elif operation == 'retry_request':
                    body, expected = generator.choice(requests); before = database_state(lab)
                    actual = mutate_workspace(lab, body)
                    self.assertEqual(actual, {**expected, 'reused': True})
                    with self.assertRaises(ValueError): mutate_workspace(lab, {'op': 'create_project', 'request_id': body['request_id'], 'name': 'Different operation/body'})
                    self.assertEqual(database_state(lab), before)
                elif operation == 'read_prior_context':
                    recorded = generator.choice(histories)
                    context = read_context(lab, recorded['id'], revision=recorded['revision'])
                    self.assertEqual(context['snapshot_hash'], recorded['snapshot_hash'])
                    self.assertEqual(context['state'], recorded['state'])
                    self.assertEqual(context['message_count'], len(recorded['messages']))
                    self.assertEqual(context['artifact_count'], len(recorded['artifacts']))
                    self.assertFalse(context['messages_truncated'])
                elif operation == 'origin_science':
                    captured = for_chat(lab, chosen)
                    # The surrounding active selection changes, but the captured facade does not.
                    active = generator.choice([name for name in model.chats if name != chosen])
                    self.assertNotEqual(active, chosen)
                    payload = {'statement': 'Authored source organization fixture ' + str(index), 'status': 'untested', 'source_ref': exact(plan)}
                    obj = captured.store.put('theory', payload)
                    self.assertEqual(obj['payload'], payload)
                    remember_obj(exact(obj)); model.link(chosen, exact(obj))
                    self.assertNotIn(marker(exact(obj)), model.chats[active]['links'])
                elif operation == 'invalid_source':
                    before = database_state(lab)
                    with self.assertRaises(ValueError): mutate_workspace(lab, {'op': 'reuse_artifact', 'request_id': 'invalid-' + str(seed) + '-' + str(index),
                        'origin_chat_id': DEFAULT_CHAT, 'target_chat_id': chosen, 'artifact_ref': exact(plan) | {'hash': '0' * 64}})
                    self.assertEqual(database_state(lab), before)
                else: self.fail('Unregistered scenario operation')
                self.assertEqual(chat_snapshot(lab, old_snapshot['id'], revision=old_snapshot['revision']), old_snapshot)
                model.assert_matches(self, lab)
                result['observed_operations'] += 1
            self.assertEqual(set(counts), set(specification['generated_sequences']['operations']))
            for snapshot in histories:
                self.assertEqual(chat_snapshot(Lab(lab.settings), snapshot['id'], revision=snapshot['revision']), snapshot)
            result.update(operation_counts=dict(sorted(counts.items())), branch_count=len(model.chats), project_count=len(model.projects),
                exact_objects_checked=len(model.objects), historical_snapshots_checked=len(histories),
                observed_provider_calls=lab.store.usage()['calls'], copy_of_copy_content_preserved=True,
                rejected_transitions_effects=0)
            self.assertEqual(result['observed_operations'], 60)
            self.assertEqual(lab.store.usage()['calls'], 0)


class WorkspacePublicScenarioTests(unittest.TestCase):
    def setUp(self):
        self.host = http_fixture.WorkspaceHttpTests()
        self.addCleanup(self.host.doCleanups); self.host.setUp()

    def test_public_exact_context_retries_and_background_origin_survive_branch_switch(self):
        result = {'status': 'started', 'expected': 'Fixed origin, historical context, idempotent operations, zero calls'}
        RESULTS['public-background-and-context'] = result
        try:
            host = self.host
            a = host.post('/api/workspaces', {'op': 'create_chat', 'project_id': DEFAULT_PROJECT, 'name': 'Authored task A', 'request_id': 'api-a'})['chat']
            body = {'op': 'create_chat', 'project_id': DEFAULT_PROJECT, 'name': 'Authored task B', 'request_id': 'api-b'}
            b = host.post('/api/workspaces', body)['chat']
            self.assertIs(host.post('/api/workspaces', body)['reused'], True)
            old = host.get('/api/workspaces/context?chat_id=' + a['id'] + '&revision=1')
            started, release = threading.Event(), threading.Event()
            original = Lab.ingest
            def delayed(bound_lab, *args, **kwargs):
                started.set()
                if not release.wait(8): raise RuntimeError('Authored fixture wait expired')
                return original(bound_lab, *args, **kwargs)
            with patch.object(Lab, 'ingest', delayed):
                queued = host.post('/api/jobs', {'action': 'ingest', 'args': {'source': str(ROOT / 'examples' / 'coordination_fixture'), 'limit': 100}}, chat=a['id'])
                self.assertTrue(started.wait(5))
                host.post('/api/workspaces', {'op': 'append_message', 'request_id': 'api-b.user', 'chat_id': b['id'],
                    'role': 'user', 'content': 'Different task while original background task continues'})
                fresh_b = host.get('/api/workspaces/chat?chat_id=' + b['id'])
                host.post('/api/workspaces', {'op': 'save_state', 'request_id': 'api-b-state', 'chat_id': b['id'],
                    'expected_revision': fresh_b['revision'], 'state': {'view': 'workspace', 'notes': 'Current selected task B'}})
                release.set(); deadline = time.monotonic() + 8
                while host.lab.store.get_job(queued['job_id'])['status'] not in ('completed', 'failed'):
                    if time.monotonic() > deadline: self.fail('Background job did not terminate')
                    time.sleep(.02)
            job = host.lab.store.get_job(queued['job_id'])
            self.assertEqual(job['status'], 'completed'); self.assertEqual(job['payload']['origin_chat_id'], a['id'])
            current_a = host.get('/api/workspaces/chat?chat_id=' + a['id'])
            self.assertEqual(len(current_a['artifacts']), 1); self.assertEqual(current_a['artifacts'][0]['kind'], 'dataset')
            self.assertEqual(host.get('/api/workspaces/chat?chat_id=' + b['id'])['artifacts'], [])
            self.assertEqual(host.get('/api/workspaces/context?chat_id=' + a['id'] + '&revision=1'), old)
            ref = current_a['artifacts'][0]['ref']; self.assertEqual(exact(host.lab.store.get(ref['id'], ref['version'])), ref)
            self.assertEqual(host.lab.store.usage()['calls'], 0)
            result.update(status='passed', exact_origin_preserved=True, historical_context_preserved=True,
                observed_provider_calls=0, queued_terminal_status=job['status'])
        except Exception as error:
            result.update(status='failed', error_type=type(error).__name__); raise
        finally: write_report()

    def test_invalid_origin_and_changed_retry_are_rejected_before_provider_or_state_effects(self):
        result = {'status': 'started', 'expected': 'Rejected transitions have zero effects and explicit retry can recover'}
        RESULTS['public-negative-and-recovery'] = result
        try:
            host = self.host
            body = {'op': 'create_chat', 'project_id': DEFAULT_PROJECT, 'name': 'Authored alternative', 'request_id': 'api-other'}
            other = host.post('/api/workspaces', body)['chat']
            before = database_state(host.lab)
            with self.assertRaises(urllib.error.HTTPError) as error:
                host.post('/api/workspaces', body | {'name': 'Changed reused request'})
            self.assertEqual(error.exception.code, 400)
            with self.assertRaises(urllib.error.HTTPError) as error:
                host.post('/api/guide/chat', {'message': 'Create a project named Wrong Origin.', 'current_view': 'workspace',
                    'active_chat_id': other['id'], 'request_id': 'guide-origin-mismatch'}, chat=DEFAULT_CHAT)
            self.assertEqual(error.exception.code, 400)
            self.assertEqual(database_state(host.lab), before)
            state_body = {'op': 'save_state', 'request_id': 'recover-good', 'chat_id': other['id'],
                'expected_revision': 1, 'state': {'view': 'workspace', 'notes': 'Explicit valid recovery'}}
            winner = host.post('/api/workspaces', state_body)['chat']; before = database_state(host.lab)
            with self.assertRaises(urllib.error.HTTPError) as error:
                host.post('/api/workspaces', state_body | {'request_id': 'stale-recovery', 'state': {'notes': 'Stale'}})
            self.assertEqual(error.exception.code, 409)
            self.assertEqual(database_state(host.lab), before)
            self.assertEqual(host.get('/api/workspaces/chat?chat_id=' + other['id']), winner)
            self.assertEqual(host.lab.store.usage()['calls'], 0)
            result.update(status='passed', observed_provider_calls=0, rejected_transition_effects=0, valid_recovery_revision=2)
        except Exception as error:
            result.update(status='failed', error_type=type(error).__name__); raise
        finally: write_report()


if __name__ == '__main__': unittest.main()
