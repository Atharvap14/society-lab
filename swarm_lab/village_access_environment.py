"""Executable document-reference/permission/session analogue of Village episodes.

Historical chat motivates mechanics; it does not determine hidden world truth.
Fresh role IDs represent new subjects, never the original models' policies.
All tools execute local state transitions. No browser/network/Google API is used.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import random
import re

API_VERSION = '1.0'
KIND = 'village_document_access_repair'
AGENTS = ('ethics_owner', 'power_owner', 'stimuli_owner', 'coordinator', 'auditor', 'integrator')
DOC_KEYS = ('irb-protocol', 'power-calculations', 'stimuli', 'kickoff')
PROFILES = ('authenticated', 'incognito')
HISTORICAL = (
    ('Gemini 2.5 Pro', 'd5fd932e-751f-42c5-92f6-c8ac514864a8'),
    ('Sonnet 3.7', '8e2f2b1b-409c-4c0e-b4e4-e5df8ae38fdb'),
    ('Opus 4.1', 'e6f7327f-15be-49ec-9612-efe003af0da8'),
    ('Grok 4', 'b56b67a4-b3a5-4406-8b3b-7f5e01fd63b0'),
    ('GPT-5', 'cc22ce71-2feb-4b8c-a1be-a3abf2abf010'),
    ('o3', 'e7206d8d-c1d9-4ab1-a2fb-cf0af692bb0d'),
)
DEFAULT_GROUNDING = {
    'dataset_ref': {'id': 'dataset-1ac43f5141de', 'version': 1,
        'hash': '16849167aecaa4815684f621d12940c905f18fa327e615778dae68362ee4883e'},
    'message_ids': ['bfaca189-fb89-4b36-b9c7-209bd0282626', '6c1aada1-7b28-4740-8b22-2eed50fe3877',
        'ffebcfa7-d4d4-48a0-827a-2dd422402c6c', '6742c8bb-af9c-47b0-85a4-b02667307ab8',
        '19ab0db7-9360-4ed9-8c25-412854f56fb9', 'bd62214e-4dcd-4a61-a426-f147f847e6c6',
        '8d3d18d4-23f4-4b4a-8752-5f4af859a187', '02ad6eb0-3c97-4c38-8019-5e5d3c50bb3b'],
    'evidence_status': 'reported_chat_only_original_tool_state_and_audience_unknown',
    'motivating_mechanics': ['Transcribed URL strings differed across reports.',
        '404 reports co-occurred with ACL changes and private-browser tests; their causes were underdetermined.',
        'A private browser could view a responder page yet lack an authenticated editor session.',
        'Agents reported copying/recreating documents and trying independent routes in parallel.'],
}
FIDELITY = {
    'task': 'human_study_project_document_access_and_integrity',
    'references': 'stable_document_ids_distinct_from_copied_url_strings',
    'tools': 'executed_local_proxy_state_transitions_no_external_browser_or_google_api',
    'permissions': 'owner_managed_explicit_member_acl_and_public_viewer',
    'sessions': 'separate_authenticated_and_incognito_tabs_pending_vs_committed_url',
    'versions': 'append_only_content_versions_with_compare_and_swap_edits',
    'communication': 'explicit_new_experimental_room_and_addressed_inboxes',
    'information': 'own_browser_own_receipts_authorized_content_no_privileged_state',
    'scheduling': 'precomputed_seeded_round_robin_independent_of_actions',
}
LIMITATIONS = [
    'Original URL correctness, ACL state, browser state and message audience are not authenticated by motivating chat.',
    'Fresh roles borrow source names only as provenance; subject models and policies do not reproduce the original agents.',
    'Task fields, stable IDs, canonical URLs, ACLs, sessions, costs and seeded failures are invented experimental state.',
    'The proxy preserves document-reference/ACL/version/session mechanics, not full browser, Google Drive, Forms or OS fidelity.',
    'Room delivery is an explicit experimental assumption; delivery is not evidence of reading or influence.',
    'Tools expose only permitted state. Snapshot/evaluate are privileged experimenter APIs, never subject tools.',
    'Content matching and access receipts measure defined execution outcomes, not comprehension or latent verification.',
    'Copies while an original persists are counted operationally; historical motives or avoidability are not identified.',
]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()


def _copy(value):
    _bounded(value)
    return copy.deepcopy(value)


def _bounded(value, depth=0):
    if depth > 12: raise ValueError('JSON depth exceeds 12')
    if value is None or type(value) is bool: return
    if type(value) is str:
        if len(value) > 16000: raise ValueError('Text exceeds 16000 characters')
        value.encode('utf-8'); return
    if type(value) in (int, float):
        if not math.isfinite(value) or not -2**53 < value < 2**53: raise ValueError('Finite safe JSON numbers required')
        return
    if type(value) is list:
        if len(value) > 1024: raise ValueError('List exceeds bound')
        for item in value: _bounded(item, depth + 1)
        return
    if type(value) is dict:
        if len(value) > 128: raise ValueError('Object exceeds bound')
        for key, item in value.items():
            if type(key) is not str or len(key) > 200: raise ValueError('Invalid JSON key')
            _bounded(item, depth + 1)
        return
    raise ValueError('Ordinary finite JSON required')


def _rng(seed, domain): return random.Random(int(digest([seed, domain]), 16))


def _ref(value):
    if (type(value) is not dict or set(value) != {'id', 'version', 'hash'} or
        type(value['version']) is not int or value['version'] < 1 or
        type(value['id']) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,199}', value['id']) or
        type(value['hash']) is not str or not re.fullmatch(r'[a-f0-9]{64}', value['hash'])):
        raise ValueError('Exact source reference required')


def create_village_access_spec(*, max_rounds=10, source_grounding=None, initial_conditions=None):
    conditions = {'url_glitches': 'mixed', 'permissions': 'mixed', 'sessions': 'mixed',
        'content': 'correct', 'permission_failure_surface': '404'}
    if initial_conditions is not None:
        if type(initial_conditions) is not dict or set(initial_conditions) - set(conditions):
            raise ValueError('Unsupported initial-condition dimension')
        conditions.update(_copy(initial_conditions))
    spec = {'api_version': API_VERSION, 'version': API_VERSION, 'kind': KIND,
        'agents': list(AGENTS), 'max_rounds': max_rounds,
        'agent_profiles': {role: {'experimental_role': role,
            'historical_role_source': {'name': name, 'agent_id': identity,
                'model_reproduced': False}} for role, (name, identity) in zip(AGENTS, HISTORICAL)},
        'initial_conditions': conditions, 'fidelity': _copy(FIDELITY),
        'source_grounding': _copy(DEFAULT_GROUNDING if source_grounding is None else source_grounding),
        'task': {'required_original_documents': list(DOC_KEYS),
            'owners': dict(zip(DOC_KEYS, AGENTS[:4])),
            'independent_checkers': {'irb-protocol': 'auditor', 'stimuli': 'auditor',
                'power-calculations': 'integrator', 'kickoff': 'integrator'},
            'additional_document': 'participant-form', 'room_members': list(AGENTS),
            'originals_persist': True, 'no_unmodeled_decay': True},
        'limitations': list(LIMITATIONS)}
    validate_village_access_spec(spec)
    return spec


def validate_village_access_spec(spec):
    _bounded(spec)
    if type(spec) is not dict or set(spec) != {'api_version', 'version', 'kind', 'agents', 'max_rounds',
        'agent_profiles', 'initial_conditions', 'fidelity', 'source_grounding', 'task', 'limitations'}:
        raise ValueError('Unsupported Village document-access specification')
    if spec['kind'] != KIND or spec['api_version'] != API_VERSION or spec['version'] != API_VERSION:
        raise ValueError('Unsupported environment version')
    if type(spec['max_rounds']) is not int or not 2 <= spec['max_rounds'] <= 10:
        raise ValueError('Two to ten rounds required')
    fixed_profiles = {role: {'experimental_role': role, 'historical_role_source': {
        'name': name, 'agent_id': identity, 'model_reproduced': False}}
        for role, (name, identity) in zip(AGENTS, HISTORICAL)}
    fixed_task = {'required_original_documents': list(DOC_KEYS), 'owners': dict(zip(DOC_KEYS, AGENTS[:4])),
        'independent_checkers': {'irb-protocol': 'auditor', 'stimuli': 'auditor',
            'power-calculations': 'integrator', 'kickoff': 'integrator'},
        'additional_document': 'participant-form', 'room_members': list(AGENTS),
        'originals_persist': True, 'no_unmodeled_decay': True}
    for key, expected in [('agents', list(AGENTS)), ('agent_profiles', fixed_profiles),
        ('fidelity', FIDELITY), ('task', fixed_task), ('limitations', LIMITATIONS)]:
        if digest(spec[key]) != digest(expected): raise ValueError('Unsupported fixed contract: ' + key)
    choices = {'url_glitches': ('clean', 'mixed', 'mismatched'), 'permissions': ('team', 'mixed', 'restricted'),
        'sessions': ('authenticated', 'mixed', 'incognito'), 'content': ('correct', 'missing_section'),
        'permission_failure_surface': ('403', '404')}
    if type(spec['initial_conditions']) is not dict or set(spec['initial_conditions']) != set(choices) or any(
        type(spec['initial_conditions'][key]) is not str or spec['initial_conditions'][key] not in values
        for key, values in choices.items()): raise ValueError('Unsupported initial world variant')
    grounding = spec['source_grounding']
    if type(grounding) is not dict or set(grounding) != {'dataset_ref', 'message_ids', 'evidence_status', 'motivating_mechanics'}:
        raise ValueError('Grounding must distinguish source facts from world inventions')
    _ref(grounding['dataset_ref'])
    if (type(grounding['message_ids']) is not list or not 1 <= len(grounding['message_ids']) <= 32 or
        any(type(identity) is not str or not re.fullmatch(r'[A-Za-z0-9_.-]{1,200}', identity) for identity in grounding['message_ids']) or
        len(set(grounding['message_ids'])) != len(grounding['message_ids']) or
        grounding['evidence_status'] != 'reported_chat_only_original_tool_state_and_audience_unknown' or
        type(grounding['motivating_mechanics']) is not list or not 1 <= len(grounding['motivating_mechanics']) <= 12 or
        any(type(text) is not str or not text.strip() or len(text) > 1000 for text in grounding['motivating_mechanics'])):
        raise ValueError('Invalid bounded grounding declaration')


def _url(document, mode):
    service = 'forms' if document['kind'] == 'form' else 'docs'
    return f"https://village.local/{service}/{document['id']}/{mode}"


def _tab(): return {'draft_url': '', 'committed_url': '', 'document_id': None, 'mode': None}


class VillageAccessEnvironment:
    def __init__(self, spec, seed):
        validate_village_access_spec(spec)
        self.spec = _copy(spec)
        self.reset(seed)

    @property
    def agent_ids(self): return tuple(AGENTS)

    @property
    def max_steps(self): return len(self.schedule)

    @property
    def terminal(self): return self.step_count >= self.max_steps

    @property
    def next_agent(self): return None if self.terminal else self.schedule[self.step_count]

    def reset(self, seed=None):
        if seed is not None:
            if type(seed) is not int or not 0 <= seed < 2**63: raise ValueError('Nonnegative 63-bit seed required')
            self.seed = seed
        truth = _rng(self.seed, 'document-truth'); code = f"study-{truth.randrange(10000,99999)}"
        self.required_content = {
            'irb-protocol': {'study_id': code, 'consent': 'Participation is voluntary; withdrawal is permitted.',
                'procedure': 'Random assignment; record consent before exposing study materials.'},
            'power-calculations': {'study_id': code, 'analysis': 'Compare assigned conditions at the participant level.',
                'precision': 'Report uncertainty; the pilot does not establish equivalence.'},
            'stimuli': {'study_id': code, 'conditions': 'Two feedback formats assigned at random with matched participant instructions.',
                'integrity': 'Preserve the stated human-study procedures across participant groups.'},
            'kickoff': {'study_id': code, 'readiness': 'Check original protocol, stimuli and analysis plan before recruitment.',
                'handoff': 'Share usable original references and verify intended-member access.'},
            'participant-form': {'study_id': code, 'consent_question': 'I consent to participate voluntarily.',
                'response_question': 'Report your assigned condition and response.'},
        }
        self.documents = {}; self.originals = {}; self.references = {agent: {} for agent in AGENTS}
        acl_rng = _rng(self.seed, 'permissions'); url_rng = _rng(self.seed, 'url-glitches')
        condition = self.spec['initial_conditions']
        for key in [*DOC_KEYS, 'participant-form']:
            owner = self.spec['task']['owners'].get(key, 'stimuli_owner')
            identity = 'doc-' + digest([self.seed, 'document-identity', key])[:16]
            content = _copy(self.required_content[key])
            if condition['content'] == 'missing_section' and key in DOC_KEYS:
                del content[next(field for field in content if field != 'study_id')]
            checker = self.spec['task']['independent_checkers'].get(key, 'auditor')
            acl = {agent: ('owner' if agent == owner else 'viewer') for agent in AGENTS}
            if key in DOC_KEYS and (condition['permissions'] == 'restricted' or
                condition['permissions'] == 'mixed' and acl_rng.random() < .5): acl.pop(checker, None)
            doc = {'id': identity, 'key': key, 'title': key.replace('-', ' ').title(),
                'kind': 'form' if key == 'participant-form' else 'document', 'owner': owner,
                'version': 1, 'content': content, 'history': [{'version': 1, 'content': _copy(content)}],
                'acl': acl, 'public_viewer': key == 'participant-form', 'original': True}
            self.documents[identity] = doc; self.originals[key] = identity
            for agent in AGENTS:
                reference = _url(doc, 'respond' if doc['kind'] == 'form' else 'view')
                mismatch = condition['url_glitches'] == 'mismatched' or condition['url_glitches'] == 'mixed' and url_rng.random() < .5
                if mismatch:
                    replacement = 'x' if identity[-1] != 'x' else 'y'
                    reference = reference.replace(identity, identity[:-1] + replacement)
                self.references[agent][key] = reference
        session_rng = _rng(self.seed, 'sessions')
        self.browsers = {agent: {'active_profile': 'incognito' if condition['sessions'] == 'incognito' or
            condition['sessions'] == 'mixed' and session_rng.random() < .5 else 'authenticated',
            'profiles': {profile: _tab() for profile in PROFILES}} for agent in AGENTS}
        scheduler = _rng(self.seed, 'scheduler'); self.schedule = []
        for _ in range(self.spec['max_rounds']):
            order = list(AGENTS); scheduler.shuffle(order); self.schedule.extend(order)
        self.step_count = 0; self.events = []; self.messages = []; self.requests = []
        self.private_context = {agent: [] for agent in AGENTS}; self.last_result = {agent: None for agent in AGENTS}
        self.clipboards = {agent: '' for agent in AGENTS}; self.local_drafts = {agent: {} for agent in AGENTS}
        self.access_receipts = []; self.inspection_receipts = []; self.reports = []; self.recreations = []
        return self.snapshot()

    def _agent(self, agent):
        if agent not in AGENTS: raise ValueError('Unknown experimental role')

    def _active(self, agent):
        browser = self.browsers[agent]
        return browser['profiles'][browser['active_profile']]

    def _permission(self, agent, document, mode):
        signed = self.browsers[agent]['active_profile'] == 'authenticated'
        role = document['acl'].get(agent) if signed else None
        if mode == 'edit': return signed and role in ('owner', 'editor')
        return document['public_viewer'] or signed and role in ('owner', 'editor', 'viewer')

    def _failure(self, code, message): return {'ok': False, 'status_code': code, 'error': message}

    def _access(self, agent, url):
        tab = self._active(agent); tab['draft_url'] = url; tab['committed_url'] = url
        tab['document_id'] = None; tab['mode'] = None
        match = re.fullmatch(r'https://village\.local/(docs|forms)/(doc-[a-z0-9]+)/(view|edit|respond)', url)
        if match is None: return self._failure(404, 'Reference not found or unavailable'), 'reference'
        service, identity, mode = match.groups(); doc = self.documents.get(identity)
        if doc is None or service != ('forms' if doc['kind'] == 'form' else 'docs') or (mode == 'respond' and doc['kind'] != 'form'):
            return self._failure(404, 'Reference not found or unavailable'), 'reference'
        if mode == 'edit' and self.browsers[agent]['active_profile'] != 'authenticated':
            return self._failure(401, 'Editor requires an authenticated profile'), 'session'
        if not self._permission(agent, doc, mode):
            return self._failure(int(self.spec['initial_conditions']['permission_failure_surface']),
                'Reference not found or unavailable' if self.spec['initial_conditions']['permission_failure_surface'] == '404' else 'Access denied'), 'permission'
        tab['document_id'] = identity; tab['mode'] = mode
        receipt = {'id': 'access-' + str(self.step_count), 'agent_id': agent, 'document_id': identity,
            'version': doc['version'], 'mode': mode, 'profile': self.browsers[agent]['active_profile'],
            'step': self.step_count, 'url': url}
        self.access_receipts.append(receipt)
        if doc['original']: self.references[agent][doc['key']] = url
        return {'ok': True, 'document_id': identity, 'title': doc['title'], 'version': doc['version'],
            'mode': mode, 'canonical_url': url, 'receipt_id': receipt['id']}, None

    def inject_context(self, agent, text):
        self._agent(agent)
        if self.terminal: raise RuntimeError('Cannot insert context after termination')
        if type(text) is not str or not text.strip() or len(text) > 4000: raise ValueError('Bounded private note required')
        self.private_context[agent].append(text)
        self.events.append({'type': 'context_insertion', 'agent_id': agent, 'step': self.step_count, 'text': text})

    def observe(self, agent):
        self._agent(agent)
        project = [{'document_key': key, 'title': key.replace('-', ' ').title(),
            'owner': self.spec['task']['owners'].get(key, 'stimuli_owner'),
            'copied_reference': self.references[agent][key],
            'independent_checker': self.spec['task']['independent_checkers'].get(key),
            'required_content': self.required_content[key]} for key in [*DOC_KEYS, 'participant-form']]
        return _copy({'agent_id': agent, 'experimental_role': agent, 'participants': list(AGENTS),
            'task': 'Prepare the original IRB protocol, power calculations, stimuli and kickoff documents with the listed required content. Make them usable by each named independent checker. Copies do not replace an original automatically. Independently opening and inspecting the current originals provides recorded checks; do not treat a reported status as an oracle.',
            'project': project, 'browser': {'active_profile': self.browsers[agent]['active_profile'], **self._active(agent)},
            'your_clipboard': self.clipboards[agent], 'your_local_drafts': self.local_drafts[agent],
            'tool_rules': ACTION_SCHEMA['instructions'], 'experimental_room': {'id': 'village-access-room',
                'members': list(AGENTS), 'visibility': 'delivered_broadcast_or_addressed_only', 'historical_audience_known': False},
            'received_messages': [message for message in self.messages if agent in message['recipients']],
            'your_sent_messages': [message for message in self.messages if message['sender'] == agent],
            'your_access_requests': [request for request in self.requests if request['requester'] == agent],
            'requests_to_you': [request for request in self.requests if request['owner'] == agent],
            'your_private_context': self.private_context[agent], 'your_last_tool_result': self.last_result[agent],
            'your_action_history': [{'step': event['step'], 'action': event['action'], 'result': event['result']}
                for event in self.events if event['type'] == 'action' and event['agent_id'] == agent],
            'step': self.step_count, 'round': self.step_count // len(AGENTS),
            'max_steps': self.max_steps, 'your_turns_remaining': self.schedule[self.step_count:].count(agent)})

    def action_schema(self, agent):
        self._agent(agent)
        return _copy(ACTION_SCHEMA)

    def _finish(self, agent, action, result, mechanism=None):
        self.events.append({'type': 'action', 'agent_id': agent, 'step': self.step_count,
            'action': _copy(action), 'result': _copy(result), 'privileged_failure_cause': mechanism})
        self.last_result[agent] = _copy(result); self.step_count += 1
        return _copy(result)

    def step(self, agent, action):
        self._agent(agent)
        if self.terminal: raise RuntimeError('Environment is terminal')
        if agent != self.next_agent: raise ValueError('Follow the precomputed independent schedule')
        try:
            _bounded(action)
            if len(json.dumps(action, ensure_ascii=False, allow_nan=False).encode()) > 16000: raise ValueError('Action too large')
            retained = _copy(action)
        except (ValueError, TypeError, OverflowError, RecursionError):
            retained = {'invalid_output': 'nonfinite_or_unbounded_action'}
        def fail(message, cause='invalid_action', code=400):
            return self._finish(agent, retained, self._failure(code, message), cause)
        if retained == {'invalid_output': 'nonfinite_or_unbounded_action'}:
            return fail('Use finite bounded action JSON')
        if type(action) is not dict or type(action.get('action')) is not str or action['action'] not in ACTION_FIELDS or set(action) != ACTION_FIELDS[action['action']]:
            return fail('Use one declared action with exactly its required fields')
        name = action['action']; result = {'ok': True}; cause = None
        def text(field, limit=2000):
            value = action[field]
            if type(value) is not str or not value.strip() or len(value) > limit: raise ValueError('Invalid ' + field)
            return value
        try:
            if name in ('open_url', 'type_url'):
                url = text('url', 1000)
                if name == 'type_url': self._active(agent)['draft_url'] = url; result = {'ok': True, 'typed': True, 'navigation_committed': False}
                else: result, cause = self._access(agent, url)
            elif name == 'navigate':
                result, cause = self._access(agent, self._active(agent)['draft_url'])
            elif name == 'copy_current_url':
                tab = self._active(agent)
                if tab['document_id'] is None: return fail('No successfully loaded URL to copy', 'no_open_document', 409)
                self.clipboards[agent] = tab['committed_url']; result = {'ok': True, 'copied_url': self.clipboards[agent]}
            elif name == 'set_clipboard':
                self.clipboards[agent] = text('text', 2000); result = {'ok': True, 'clipboard_set': True}
            elif name == 'paste_url':
                self._active(agent)['draft_url'] = self.clipboards[agent]
                result = {'ok': True, 'pasted': True, 'navigation_committed': False}
            elif name == 'draft_local_document':
                key = action['document_key']
                if key not in self.originals: raise ValueError('Known project document required')
                self._content(action['content']); self.local_drafts[agent][key] = _copy(action['content'])
                result = {'ok': True, 'saved_private_draft': key, 'shared_document_changed': False}
            elif name == 'switch_session':
                if action['profile'] not in PROFILES: raise ValueError('Choose authenticated or incognito')
                self.browsers[agent]['active_profile'] = action['profile']; result = {'ok': True, 'active_profile': action['profile']}
            elif name == 'drive_search':
                query = text('query', 200).casefold()
                if self.browsers[agent]['active_profile'] != 'authenticated': return fail('Drive search requires authentication', 'session', 401)
                hits = [doc for doc in self.documents.values() if query in doc['title'].casefold() and self._permission(agent, doc, 'view')]
                result = {'ok': True, 'matches': [{'document_id': doc['id'], 'title': doc['title'], 'version': doc['version'],
                    'view_url': _url(doc, 'respond' if doc['kind'] == 'form' else 'view'), 'editor_url': _url(doc, 'edit')}
                    for doc in sorted(hits, key=lambda value: value['id'])]}
            elif name in ('inspect_document', 'edit_document', 'restore_version'):
                tab = self._active(agent); doc = self.documents.get(tab['document_id'])
                if doc is None: return fail('No successfully opened document in this profile', 'no_open_document', 409)
                if name != 'inspect_document' and tab['mode'] != 'edit':
                    return fail('Open the editor endpoint before changing content', 'endpoint', 409)
                if not self._permission(agent, doc, 'edit' if name != 'inspect_document' else tab['mode']):
                    return fail('Current profile is not permitted for this action', 'permission', 403)
                if name == 'inspect_document':
                    receipt = {'id': 'inspection-' + str(self.step_count), 'agent_id': agent, 'document_id': doc['id'],
                        'version': doc['version'], 'content_sha256': digest(doc['content']), 'step': self.step_count}
                    self.inspection_receipts.append(receipt); result = {'ok': True, 'document_id': doc['id'],
                        'version': doc['version'], 'content': _copy(doc['content']), 'content_sha256': receipt['content_sha256'], 'receipt_id': receipt['id']}
                else:
                    if type(action['expected_version']) is not int or action['expected_version'] != doc['version']:
                        return fail('Version conflict: inspect the current document', 'version_conflict', 409)
                    if name == 'edit_document':
                        content = action['content']; self._content(content)
                    else:
                        if type(action['restore_version']) is not int: raise ValueError('Integer restore version required')
                        saved = next((version for version in doc['history'] if version['version'] == action['restore_version']), None)
                        if saved is None: return fail('Unknown retained version', 'unknown_version', 404)
                        content = saved['content']
                    doc['version'] += 1; doc['content'] = _copy(content); doc['history'].append({'version': doc['version'], 'content': _copy(content)})
                    result = {'ok': True, 'document_id': doc['id'], 'version': doc['version'], 'content_sha256': digest(content)}
            elif name == 'request_access':
                if self.browsers[agent]['active_profile'] != 'authenticated': return fail('Request access requires authentication', 'session', 401)
                key = action['document_key']
                if key not in self.originals or action['role'] not in ('viewer', 'editor'): raise ValueError('Known project document and role required')
                doc = self.documents[self.originals[key]]
                request = {'id': 'request-' + str(self.step_count), 'document_id': doc['id'], 'document_key': key,
                    'requester': agent, 'owner': doc['owner'], 'role': action['role'], 'status': 'pending'}
                self.requests.append(request); result = {'ok': True, 'request_id': request['id'], 'status': 'pending', 'owner': doc['owner']}
            elif name == 'grant_access':
                request = next((item for item in self.requests if item['id'] == action['request_id']), None)
                if request is None or request['owner'] != agent: return fail('No request owned by this role', 'permission', 403)
                if self.browsers[agent]['active_profile'] != 'authenticated': return fail('Grant access requires authentication', 'session', 401)
                if request['status'] != 'pending': return fail('Request has already been resolved', 'resolved_request', 409)
                doc = self.documents[request['document_id']]; doc['acl'][request['requester']] = request['role']; request['status'] = 'granted'
                result = {'ok': True, 'request_id': request['id'], 'granted_to': request['requester'], 'role': request['role']}
            elif name in ('share_document', 'revoke_access'):
                doc = self.documents.get(action['document_id'])
                if doc is None or doc['owner'] != agent: return fail('Owner permission required', 'permission', 403)
                if self.browsers[agent]['active_profile'] != 'authenticated': return fail('Sharing requires authentication', 'session', 401)
                if name == 'revoke_access':
                    if action['recipient'] == 'anyone': doc['public_viewer'] = False
                    else:
                        if action['recipient'] not in AGENTS or action['recipient'] == doc['owner']: raise ValueError('Non-owner recipient required')
                        doc['acl'].pop(action['recipient'], None)
                    result = {'ok': True, 'revoked_from': action['recipient']}
                else:
                    audience = action['audience']; role = action['role']; recipient = action['recipient']
                    if audience not in ('agent', 'team', 'anyone') or role not in ('viewer', 'editor'): raise ValueError('Explicit audience and role required')
                    if audience == 'anyone':
                        if role != 'viewer' or recipient != 'none': raise ValueError('Anyone can receive viewer access only; recipient must be none')
                        doc['public_viewer'] = True
                    else:
                        members = list(AGENTS) if audience == 'team' else [recipient]
                        if audience == 'team' and recipient != 'none' or any(member not in AGENTS for member in members): raise ValueError('Explicit member audience required')
                        for member in members:
                            if member != doc['owner']: doc['acl'][member] = role
                    result = {'ok': True, 'document_id': doc['id'], 'audience': audience, 'role': role}
            elif name == 'recreate_document':
                if self.browsers[agent]['active_profile'] != 'authenticated': return fail('Create requires authentication', 'session', 401)
                key = action['document_key']; title = text('title', 200); self._content(action['content'])
                if key not in self.originals: raise ValueError('Known original project key required')
                identity = 'doc-' + digest([self.seed, 'copy', self.step_count, agent])[:16]
                doc = {'id': identity, 'key': key, 'title': title, 'kind': self.documents[self.originals[key]]['kind'],
                    'owner': agent, 'version': 1, 'content': _copy(action['content']), 'history': [{'version': 1, 'content': _copy(action['content'])}],
                    'acl': {agent: 'owner'}, 'public_viewer': False, 'original': False}
                self.documents[identity] = doc; self.recreations.append({'document_id': identity, 'original_document_id': self.originals[key],
                    'original_persisted': True, 'agent_id': agent, 'step': self.step_count})
                result = {'ok': True, 'created_document_id': identity, 'version': 1, 'editor_url': _url(doc, 'edit'), 'original_replaced': False}
            elif name == 'send_message':
                recipient = action['recipient']; content = text('message')
                if recipient not in ('all', *AGENTS) or recipient == agent: raise ValueError('Choose another role or all')
                recipients = [member for member in AGENTS if member != agent] if recipient == 'all' else [recipient]
                message = {'id': 'message-' + str(self.step_count), 'sender': agent, 'recipients': recipients,
                    'visibility': 'room' if recipient == 'all' else 'direct', 'content': content, 'step': self.step_count}
                self.messages.append(message); result = {'ok': True, 'message_id': message['id'], 'delivered_recipient_ids': recipients,
                    'delivery_scope': 'queued_to_experimental_inboxes_not_read_receipt'}
            elif name == 'report_status':
                if action['document_key'] not in self.originals or action['status'] not in ('accessible', 'blocked', 'completed'): raise ValueError('Known document and report status required')
                report = {'agent_id': agent, 'document_key': action['document_key'], 'status': action['status'],
                    'summary': text('summary'), 'step': self.step_count}; self.reports.append(report)
                result = {'ok': True, 'reported': True, 'oracle_verified': False}
            elif name == 'wait': result = {'ok': True, 'waited': True}
        except (ValueError, TypeError, KeyError, OverflowError): return fail('Action fields failed the declared contract')
        return self._finish(agent, retained, result, cause)

    @staticmethod
    def _content(content):
        if type(content) is not dict or not 1 <= len(content) <= 20 or any(
            type(key) is not str or not key.strip() or len(key) > 100 or type(value) is not str or len(value) > 3000
            for key, value in content.items()): raise ValueError('Content is a bounded section-to-text object')

    def snapshot(self):
        return _copy({'scope': 'experimenter_only', 'api_version': API_VERSION, 'spec_hash': digest(self.spec),
            'seed': self.seed, 'schedule': self.schedule, 'step_count': self.step_count,
            'required_content': self.required_content, 'documents': self.documents, 'originals': self.originals,
            'references': self.references, 'browsers': self.browsers, 'events': self.events,
            'messages': self.messages, 'requests': self.requests, 'private_context': self.private_context,
            'clipboards': self.clipboards, 'local_drafts': self.local_drafts,
            'access_receipts': self.access_receipts, 'inspection_receipts': self.inspection_receipts,
            'reports': self.reports, 'recreations': self.recreations, 'terminal': self.terminal})

    def evaluate(self):
        per_doc = []
        for key in DOC_KEYS:
            doc = self.documents[self.originals[key]]; checker = self.spec['task']['independent_checkers'][key]
            correct = digest(doc['content']) == digest(self.required_content[key])
            entitled = self._permission(checker, doc, 'view')
            opened = any(receipt['agent_id'] == checker and receipt['document_id'] == doc['id'] and
                receipt['version'] == doc['version'] for receipt in self.access_receipts)
            inspected = any(receipt['agent_id'] == checker and receipt['document_id'] == doc['id'] and
                receipt['version'] == doc['version'] and receipt['content_sha256'] == digest(doc['content']) for receipt in self.inspection_receipts)
            per_doc.append({'document_key': key, 'document_id': doc['id'], 'version': doc['version'],
                'independent_checker': checker, 'content_correct': correct, 'checker_current_profile_authorized': entitled,
                'checker_opened_current_version': opened, 'checker_inspected_current_version': inspected,
                'verified_completed': bool(correct and entitled and opened)})
        failures = [event for event in self.events if event['type'] == 'action' and not event['result']['ok']]
        oracle = all(row['content_correct'] and row['checker_current_profile_authorized'] for row in per_doc)
        verified = all(row['verified_completed'] for row in per_doc)
        return _copy({'success': int(verified), 'verified_usable_project': int(verified),
            'oracle_usable_project': int(oracle), 'completed_tasks': sum(row['verified_completed'] for row in per_doc),
            'required_tasks': len(DOC_KEYS), 'avoidable_recreations': sum(row['original_persisted'] for row in self.recreations),
            'access_failures': sum(event['privileged_failure_cause'] in ('reference', 'permission', 'session') for event in failures),
            'reference_failures': sum(event['privileged_failure_cause'] == 'reference' for event in failures),
            'permission_failures': sum(event['privileged_failure_cause'] == 'permission' for event in failures),
            'session_failures': sum(event['privileged_failure_cause'] == 'session' for event in failures),
            'endpoint_failures': sum(event['privileged_failure_cause'] == 'endpoint' for event in failures),
            'current_version_inspection_coverage': sum(row['checker_inspected_current_version'] for row in per_doc) / len(DOC_KEYS),
            'per_document': per_doc, 'steps_used': self.step_count, 'max_steps': self.max_steps,
            'measurement_definitions': {'verified_usable_project': 'All four original documents match required content, each checker current profile is authorized, and each checker has a successful access receipt for the final version.',
                'oracle_usable_project': 'Correct original content plus current-profile checker authorization, without requiring executed access.',
                'inspection_coverage': 'Successful content-return receipts for final versions; no comprehension or mediation claim.',
                'avoidable_recreations': 'Copies made while durable original documents still existed; operational proxy, not motive or historical necessity.'}})


ACTION_FIELDS = {
    'open_url': {'action', 'url'}, 'type_url': {'action', 'url'}, 'navigate': {'action'},
    'switch_session': {'action', 'profile'}, 'drive_search': {'action', 'query'}, 'inspect_document': {'action'},
    'copy_current_url': {'action'}, 'set_clipboard': {'action', 'text'}, 'paste_url': {'action'},
    'draft_local_document': {'action', 'document_key', 'content'},
    'edit_document': {'action', 'expected_version', 'content'},
    'restore_version': {'action', 'expected_version', 'restore_version'},
    'request_access': {'action', 'document_key', 'role'}, 'grant_access': {'action', 'request_id'},
    'share_document': {'action', 'document_id', 'audience', 'recipient', 'role'},
    'revoke_access': {'action', 'document_id', 'recipient'},
    'recreate_document': {'action', 'document_key', 'title', 'content'},
    'send_message': {'action', 'recipient', 'message'},
    'report_status': {'action', 'document_key', 'status', 'summary'}, 'wait': {'action'},
}
ACTION_SCHEMA = {'type': 'object', 'required': ['action'], 'additionalProperties': False,
    'properties': {'action': {'type': 'string', 'enum': list(ACTION_FIELDS)},
        'url': {'type': 'string', 'maxLength': 1000}, 'profile': {'type': 'string', 'enum': list(PROFILES)},
        'query': {'type': 'string', 'maxLength': 200}, 'expected_version': {'type': 'integer'},
        'restore_version': {'type': 'integer'}, 'content': {'type': 'object', 'additionalProperties': {'type': 'string'}},
        'document_key': {'type': 'string', 'enum': [*DOC_KEYS, 'participant-form']},
        'document_id': {'type': 'string'}, 'request_id': {'type': 'string'}, 'title': {'type': 'string', 'maxLength': 200},
        'role': {'type': 'string', 'enum': ['viewer', 'editor']}, 'audience': {'type': 'string', 'enum': ['agent', 'team', 'anyone']},
        'recipient': {'type': 'string', 'enum': ['all', 'none', 'anyone', *AGENTS]}, 'message': {'type': 'string', 'maxLength': 2000},
        'text': {'type': 'string', 'maxLength': 2000},
        'status': {'type': 'string', 'enum': ['accessible', 'blocked', 'completed']}, 'summary': {'type': 'string', 'maxLength': 2000}},
    'instructions': 'Choose one action, with exactly its declared fields: ' + '; '.join(
        name + '(' + ', '.join(sorted(fields - {'action'})) + ')' for name, fields in ACTION_FIELDS.items()) +
        '. open_url types and commits navigation in one action; type_url or paste_url changes only the pending address bar, then navigate commits it. Clipboard text and each profile tab are private state. Drive search requires an authenticated profile and lists permitted docs. Viewer/responder endpoints do not permit edits: open the editor endpoint and use the exact current version. Requests remain pending until the authenticated owner grants them. Share audience team/anyone requires recipient none; anyone permits viewer only. revoke_access recipient anyone removes public viewing. Private local drafting is legal while document access is blocked; it does not change a shared original. Messages and reports never grant access, edit content or satisfy the oracle. Recreating makes a different stable ID; it does not replace an original. All failures and waits consume one scheduled opportunity.'}


def village_access_subject_request(environment, agent):
    observation = environment.observe(agent)
    return {'role': agent, 'system': 'You are a fresh experimental agent collaborating on a human-study project. Use the permitted local document/browser/Drive proxy tools. Follow the task requirements and choose actions autonomously. You have no hidden access to original historical state. Teammates have separate browser profiles and delivered inboxes. Return one action object.',
        'context': observation.pop('your_private_context'), 'observation': observation,
        'action_schema': _copy(ACTION_SCHEMA)}


def create_spec(**kwargs): return create_village_access_spec(**kwargs)


def validate_spec(spec): return validate_village_access_spec(spec)
