"""A bounded revision-capable relay world; no provider or historical replay.

A is a scripted source, B and C are model-subject roles. Delivery means local
recipient queue placement, not request invocation or provider consumption.
Ordinal scheduling is independent of subject actions. Invalid scheduled actions
consume one opportunity; only an explicit valid C final action is scored.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import random


INSTRUMENT_VERSION = 'revision-relay-environment-v1'
API_VERSION = '1.0'
SUBJECTS = ('B', 'C')
MODULUS = 97
TIMINGS = ('early', 'late')
BYPASSES = ('informative', 'sham')
SCHEDULE = (('B', 2), ('C', 3), ('B', 5), ('C', 7))
MAX_MESSAGE_CHARS = 256
MAX_CONTEXT_CHARS = 1024
MAX_CONTEXT_ENTRIES = 2
MAX_RETAINED_ACTION_BYTES = 4096
INVALID_RETAINED_ACTION = {'action_not_retained': 'unsupported_or_oversized_nonfinite_JSON'}


def fingerprint(value):
    """Compact sorted finite UTF-8 JSON identity; separate from Store hashes."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()


def _integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{name} must be an integer in [{low}, {high}]')
    return value


def _text(value, cap, *, nonempty=False):
    return (type(value) is str and len(value) <= cap and
            (not nonempty or bool(value.strip())) and
            not any(0xD800 <= ord(char) <= 0xDFFF for char in value))


def _bounded_json(value):
    """Check before copying/serializing: arbitrary invalid actions stay bounded."""
    nodes = 0

    def visit(item, depth):
        nonlocal nodes
        nodes += 1
        if depth > 8 or nodes > 128:
            raise ValueError('Action nesting/item bound exceeded')
        if item is None or type(item) is bool:
            return
        if type(item) is int:
            if abs(item) > 10 ** 100:
                raise ValueError('Action numeric bound exceeded')
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise ValueError('Action must be finite JSON')
            return
        if type(item) is str:
            if not _text(item, MAX_RETAINED_ACTION_BYTES):
                raise ValueError('Action string bound exceeded')
            return
        if type(item) is list:
            if len(item) > 16:
                raise ValueError('Action list bound exceeded')
            for child in item:
                visit(child, depth + 1)
            return
        if type(item) is dict:
            if len(item) > 32 or any(not _text(key, 128) for key in item):
                raise ValueError('Action object bound exceeded')
            for child in item.values():
                visit(child, depth + 1)
            return
        raise ValueError('Action must be ordinary finite JSON')

    visit(value, 0)
    if len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')) > MAX_RETAINED_ACTION_BYTES:
        raise ValueError('Retained action byte bound exceeded')


def _base_action_schema(role, *, final=False):
    if role == 'B':
        variants = [
            {'type': 'object', 'required': ['action', 'record_ids', 'message'],
             'properties': {'action': {'const': 'forward'},
                 'record_ids': {'type': 'array', 'maxItems': 1, 'uniqueItems': True,
                                'items': {'type': 'string', 'minLength': 1, 'maxLength': 64}},
                 'message': {'type': 'string', 'maxLength': MAX_MESSAGE_CHARS}},
             'additionalProperties': False},
            {'type': 'object', 'required': ['action'],
             'properties': {'action': {'const': 'wait'}}, 'additionalProperties': False}]
    else:
        name = 'revise' if final else 'draft'
        variants = [
            {'type': 'object', 'required': ['action', 'revision', 'total'],
             'properties': {'action': {'const': name},
                 'revision': {'type': 'integer', 'enum': [1, 2]},
                 'total': {'type': 'integer', 'minimum': 0, 'maximum': MODULUS - 1},
                 'rationale': {'type': 'string', 'maxLength': MAX_MESSAGE_CHARS}},
             'additionalProperties': False},
            {'type': 'object', 'required': ['action'],
             'properties': {'action': {'const': 'wait'}}, 'additionalProperties': False}]
        if final:
            variants.append({'type': 'object', 'required': ['action'],
                'properties': {'action': {'const': 'retain'}}, 'additionalProperties': False})
    return {'oneOf': variants}


def create_revision_relay_spec():
    """Return the one implemented spec. Broader capabilities require a version."""
    return {'api_version': API_VERSION, 'instrument_version': INSTRUMENT_VERSION,
        'kind': 'revision_relay', 'subjects': list(SUBJECTS), 'source_fixture': 'A',
        'modulus': MODULUS, 'target_revision': 2,
        'measurement_distribution': 'independent_uniform_revision1_revision2_C_private_and_unrelated_residues',
        'source_id_policy': 'fixed_world_local_labels_independent_of_measurement_values',
        'invalid_output_policy': 'bounded_replayable_invalid_sentinel_original_unretained_content_unknown',
        'schedule': [{'agent_id': role, 'ordinal_boundary': boundary} for role, boundary in SCHEDULE],
        'source_dispatch_boundaries': [0, 1, 4, 6],
        'permitted_channels': [['A', 'B'], ['B', 'C'], ['A', 'C']],
        'assignment_factors': {'timing': list(TIMINGS), 'bypass': list(BYPASSES)},
        'caps': {'subject_decisions': 4, 'attachments_per_outbox': 1,
            'message_chars': MAX_MESSAGE_CHARS, 'context_chars_per_entry': MAX_CONTEXT_CHARS,
            'context_entries_per_subject': MAX_CONTEXT_ENTRIES,
            'retained_action_bytes': MAX_RETAINED_ACTION_BYTES,
            'deliveries': 6, 'canonical_source_records': 3},
        'action_schemas': {'B': _base_action_schema('B'),
                          'C_draft': _base_action_schema('C'),
                          'C_final': _base_action_schema('C', final=True)},
        'packet_text': 'Source record available. Resolve artifact and revision against your task.',
        'outcome': 'C_final_revision2_and_exact_modular_total_missing_invalid_wait_zero_explicit_retain_only',
        'fidelity': {'world': 'resettable_state_machine', 'time': 'action_independent_ordinal_boundaries',
            'continuity': 'recipient_scoped_records_context_and_own_action_history',
            'source_fixture': 'scripted_no_model_calls',
            'delivery': 'local_recipient_queue_placement_not_request_invocation_or_provider_consumption'},
        'limitations': ['Observable correction-availability timing and informative bypass are the assigned policies.',
            'Private reminders, latent thoughts, historical reconstruction and cross-model transport are untested.',
            'Same scheduled containers and B packet multiset do not imply equal model exposure.',
            'A runner must separately bind actual subject-request construction, invocation and returned provider metadata.',
            'Matched structured shams are not guaranteed semantically inert or tokenizer matched.',
            'Correct guesses score without a source attachment; source inventory is not mental knowledge.']}


def validate_revision_relay_spec(spec):
    if type(spec) is not dict:
        raise ValueError('Use the declared revision-relay spec')
    try:
        _bounded_json_spec(spec)
        if fingerprint(spec) != fingerprint(create_revision_relay_spec()):
            raise ValueError('Unsupported revision-relay spec or capability')
    except (TypeError, OverflowError, RecursionError) as error:
        raise ValueError('Use a bounded finite revision-relay spec') from error


def _bounded_json_spec(spec):
    # Exact template limits imply bounded accepted state; preflight arbitrary
    # caller objects before hashing rather than serializing enormous extras.
    nodes = 0

    def visit(item, depth):
        nonlocal nodes
        nodes += 1
        if depth > 12 or nodes > 1024:
            raise ValueError('Spec nesting/item bound exceeded')
        if item is None or type(item) is bool:
            return
        if type(item) is int:
            if abs(item) > 10 ** 10:
                raise ValueError('Spec numeric bound exceeded')
            return
        if type(item) is str:
            if not _text(item, 2000):
                raise ValueError('Spec string bound exceeded')
            return
        if type(item) is list:
            if len(item) > 32:
                raise ValueError('Spec list bound exceeded')
            for child in item:
                visit(child, depth + 1)
            return
        if type(item) is dict:
            if len(item) > 32 or any(not _text(key, 128) for key in item):
                raise ValueError('Spec object bound exceeded')
            for child in item.values():
                visit(child, depth + 1)
            return
        raise ValueError('Spec requires the finite declared JSON types')

    visit(spec, 0)


class RevisionRelayEnvironment:
    def __init__(self, spec, seed, *, timing='early', bypass='sham'):
        validate_revision_relay_spec(spec)
        if type(timing) is not str or timing not in TIMINGS or type(bypass) is not str or bypass not in BYPASSES:
            raise ValueError('Use explicit early/late timing and informative/sham bypass')
        self._spec = copy.deepcopy(spec)
        self._timing, self._bypass = timing, bypass
        self._seed = _integer(seed, 0, 2 ** 63 - 1, 'seed')
        self.reset()

    @property
    def spec(self):
        return copy.deepcopy(self._spec)

    @property
    def terminal(self):
        return self._step_count == len(SCHEDULE)

    @property
    def next_agent(self):
        return None if self.terminal else SCHEDULE[self._step_count][0]

    def _subject(self, role):
        if type(role) is not str or role not in SUBJECTS:
            raise ValueError('Unknown model-subject role')

    def _residue(self, purpose):
        seed = int(fingerprint([self._seed, purpose]), 16)
        return random.Random(seed).randrange(MODULUS)

    def reset(self, seed=None):
        if seed is not None:
            self._seed = _integer(seed, 0, 2 ** 63 - 1, 'seed')
        self._records = {}
        for identity, artifact, revision, purpose in (
                ('source-record-01', 'artifact-main', 1, 'revision1'),
                ('source-record-02', 'artifact-main', 2, 'revision2'),
                ('source-record-03', 'artifact-auxx', 2, 'unrelated')):
            core = {'record_id': identity, 'artifact_id': artifact, 'revision': revision,
                    'value': self._residue(purpose), 'origin_id': 'origin-' + identity,
                    'source_role': 'A'}
            self._records[identity] = {**core, 'record_sha256': fingerprint(core), 'lineage': []}
        self._private_residue = self._residue('C-private')
        self._oracle_total = (self._records['source-record-02']['value'] + self._private_residue) % MODULUS
        self._known = {role: {} for role in SUBJECTS}
        self._contexts = {role: [] for role in SUBJECTS}
        self._turn_counts = {role: 0 for role in SUBJECTS}
        self._last_result = {role: None for role in SUBJECTS}
        self._deliveries, self._events = [], []
        self._draft, self._final = None, None
        self._step_count = 0
        self._deliver('A', 'B', 0, ['source-record-01'], self._spec['packet_text'])
        first = 'source-record-02' if self._timing == 'early' else 'source-record-03'
        self._deliver('A', 'B', 1, [first], self._spec['packet_text'])
        return self.snapshot()

    def _deliver(self, sender, recipient, boundary, identities, text):
        delivery_id = f'dispatch-{boundary:02d}-{sender}-{recipient}'
        records = []
        for identity in identities:
            record = copy.deepcopy(self._records[identity] if sender == 'A' else self._known[sender][identity])
            record['lineage'].append({'sender': sender, 'recipient': recipient,
                'ordinal_boundary': boundary, 'delivery_id': delivery_id})
            records.append(record)
            self._known[recipient].setdefault(identity, copy.deepcopy(record))
        delivery = {'delivery_id': delivery_id, 'sender': sender, 'recipient': recipient,
                    'ordinal_boundary': boundary, 'message': text,
                    'records': records, 'empty_outbox': not records and not text}
        self._deliveries.append(delivery)
        self._events.append({'type': 'dispatch', **copy.deepcopy(delivery)})

    def action_schema(self, role):
        self._subject(role)
        schema = _base_action_schema(role, final=self._turn_counts[role] >= 1)
        if role == 'B':
            schema['oneOf'][0]['properties']['record_ids']['items']['enum'] = sorted(self._known['B'])
        return schema

    def observe(self, role):
        self._subject(role)
        own_history = [event for event in self._events if event['type'] == 'action' and event['agent_id'] == role]
        result = {'agent_id': role, 'model_subjects': list(SUBJECTS), 'source_fixture': 'A',
            'task_artifact_id': 'artifact-main', 'target_revision': 2, 'modulus': MODULUS,
            'task': ('Forward task-relevant canonical source records to C; you cannot see C\'s private residue.'
                     if role == 'B' else
                     'Report revision 2 and (its source value + your private residue) modulo 97. '
                     'Your first answer is provisional; only your explicit valid final action is scored.'),
            'known_records': list(self._known[role].values()),
            'received_deliveries': [row for row in self._deliveries if row['recipient'] == role],
            'your_sent_deliveries': [row for row in self._deliveries if row['sender'] == role],
            'your_private_context': self._contexts[role], 'your_action_history': own_history,
            'your_last_tool_result': self._last_result[role],
            'your_decisions_remaining': 2 - self._turn_counts[role],
            'decision_phase': ('relay' if role == 'B' else
                               'draft' if self._turn_counts['C'] == 0 else 'final'),
            'rules': ['Source records are immutable; artifact and revision distinguish updates from unrelated records.',
                'Free text is unverified narration; only available canonical record IDs can be attached.',
                'An invalid or waiting decision consumes its fixed opportunity.',
                'No correctness feedback is provided.']}
        if role == 'C':
            result['your_private_residue'] = self._private_residue
            result['your_draft'] = self._draft
            result['your_final_answer'] = self._final
        return copy.deepcopy(result)

    def inject_context(self, role, text):
        """Optional capability outside the two-factor correction study."""
        self._subject(role)
        if self.terminal:
            raise RuntimeError('Cannot insert context after termination')
        if not _text(text, MAX_CONTEXT_CHARS, nonempty=True) or len(self._contexts[role]) >= MAX_CONTEXT_ENTRIES:
            raise ValueError('Private context exceeds declared nonempty text/entry bounds')
        self._contexts[role].append(text)
        self._events.append({'type': 'context_insertion', 'agent_id': role,
                             'decision_index': self._step_count, 'text': text})

    def _validate_action(self, role, action):
        if type(action) is dict and action == INVALID_RETAINED_ACTION:
            return 'Action is not bounded finite JSON'
        if type(action) is not dict or type(action.get('action')) is not str:
            return 'Return a supported action object'
        name = action['action']
        if name == 'wait' and set(action) == {'action'}:
            return None
        if role == 'B':
            if name != 'forward' or set(action) != {'action', 'record_ids', 'message'}:
                return 'B may forward known records or wait'
            identities = action['record_ids']
            if (type(identities) is not list or len(identities) > 1 or
                    any(type(item) is not str or item not in self._known['B'] for item in identities)):
                return 'Attach at most one currently available canonical record ID'
            if not _text(action['message'], MAX_MESSAGE_CHARS):
                return 'Message exceeds the declared text bound'
            return None
        final = self._turn_counts['C'] == 1
        if final and name == 'retain' and set(action) == {'action'}:
            return None if self._draft is not None else 'There is no valid draft to retain'
        expected_name = 'revise' if final else 'draft'
        if (name != expected_name or not {'action', 'revision', 'total'} <= set(action) or
                set(action) - {'action', 'revision', 'total', 'rationale'}):
            return 'Use the declared draft/final answer action or wait'
        if type(action['revision']) is not int or action['revision'] not in (1, 2):
            return 'Revision must be integer 1 or 2'
        if type(action['total']) is not int or not 0 <= action['total'] < MODULUS:
            return 'Total must be an integer residue in [0, 96]'
        if 'rationale' in action and not _text(action['rationale'], MAX_MESSAGE_CHARS):
            return 'Rationale exceeds the declared text bound'
        return None

    def step(self, role, action):
        self._subject(role)
        if self.terminal:
            raise RuntimeError('Environment is terminal')
        if role != self.next_agent:
            raise ValueError('Action does not match the fixed subject schedule')
        boundary = SCHEDULE[self._step_count][1]
        try:
            _bounded_json(action)
            retained = copy.deepcopy(action)
            error = self._validate_action(role, action)
        except (ValueError, TypeError, OverflowError, RecursionError):
            retained = copy.deepcopy(INVALID_RETAINED_ACTION)
            error = 'Action is not bounded finite JSON'
        result = {'ok': error is None}
        if error is not None:
            result['error'] = error
        elif role == 'B':
            result['outbox_recorded'] = True
        else:
            name = action['action']
            if name in ('draft', 'revise'):
                answer = {'revision': action['revision'], 'total': action['total']}
                if self._turn_counts['C'] == 0:
                    self._draft = answer
                    result['draft_recorded'] = True
                else:
                    self._final = answer
                    result['final_recorded'] = True
            elif name == 'retain':
                self._final = copy.deepcopy(self._draft)
                result['final_recorded'] = True
        self._events.append({'type': 'action', 'agent_id': role, 'ordinal_boundary': boundary,
                             'decision_index': self._step_count, 'action': retained, 'result': copy.deepcopy(result)})
        self._last_result[role] = copy.deepcopy(result)
        if role == 'B':
            forward = error is None and action['action'] == 'forward'
            self._deliver('B', 'C', boundary, action['record_ids'] if forward else [],
                          action['message'] if forward else '')
        self._turn_counts[role] += 1
        self._step_count += 1
        if self._step_count == 2:
            second = 'source-record-03' if self._timing == 'early' else 'source-record-02'
            self._deliver('A', 'B', 4, [second], self._spec['packet_text'])
        elif self._step_count == 3:
            bypass = 'source-record-02' if self._bypass == 'informative' else 'source-record-03'
            self._deliver('A', 'C', 6, [bypass], self._spec['packet_text'])
        return copy.deepcopy(result)

    def snapshot(self):
        """Privileged host state; never a subject request."""
        return copy.deepcopy({'instrument_version': INSTRUMENT_VERSION,
            'spec_hash': fingerprint(self._spec), 'seed': self._seed,
            'assignment': {'timing': self._timing, 'bypass': self._bypass},
            'source_records': self._records, 'C_private_residue': self._private_residue,
            'oracle_total': self._oracle_total, 'known_records': self._known,
            'contexts': self._contexts, 'turn_counts': self._turn_counts,
            'step_count': self._step_count, 'deliveries': self._deliveries,
            'events': self._events, 'draft': self._draft, 'final': self._final,
            'last_result': self._last_result, 'terminal': self.terminal})

    def evaluate(self):
        """Independent exact oracle; no attachment/receipt eligibility gate."""
        correct = (self._final is not None and self._final['revision'] == 2 and
                   self._final['total'] == self._oracle_total)
        return {'instrument_version': INSTRUMENT_VERSION, 'terminal': self.terminal,
            'C_final_correct': int(correct), 'C_final_answer_present': self._final is not None,
            'C_final_answer': copy.deepcopy(self._final), 'C_draft': copy.deepcopy(self._draft),
            'target_revision': 2, 'oracle_total': self._oracle_total,
            'missing_invalid_wait_final_score': 0,
            'canonical_revision2_visible_to_C': 'source-record-02' in self._known['C'],
            'correctness_requires_canonical_receipt': False,
            'delivery_scope': 'local_recipient_queue_placement_not_request_invocation_or_provider_consumption',
            'source_identity_scope': 'world_local_value_independent_labels_not_globally_unique',
            'adapter_model_calls': 0}


def create_revision_relay_environment(spec=None, seed=0, *, timing='early', bypass='sham'):
    return RevisionRelayEnvironment(create_revision_relay_spec() if spec is None else spec,
                                    seed, timing=timing, bypass=bypass)


def revision_relay_subject_request(environment, role):
    """Construct isolated subject data without seed, assignment, oracle or spec."""
    return {'agent_id': role, 'observation': environment.observe(role),
            'action_schema': environment.action_schema(role)}
