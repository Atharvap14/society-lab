"""Unvalidated opportunity rubrics and exact-source, prompt-defined Laya screens.

A message-level classifier never supplies the exposure, authorization, closed
window or checked outcome needed to score an actor's opportunity episode.
"""
import copy
import hashlib
import json
import math
from pathlib import Path
import re

from .classifiers import (BackendProtocolError, BackendUnavailable, LayaProcessBackend,
                         LAYA_MODEL_REVISION, build_questions)
from .measurement_backends import BoundedMeasurement
from .store import clean, fingerprint, now

VERSION = 'prompt-defined-behavior-rubrics-v1'
FIELDS = ('title', 'question', 'opportunity', 'positive', 'negative', 'unknown', 'screen_prompt', 'non_examples')
PROVENANCE = {'kind': 'original_compact_adaptation',
    'source_url': 'https://github.com/gautamjajoo/kairosity-observatory/blob/codex/agent-observatory/research/behavioral-rubric.json',
    'git_blob_sha': 'ef2a5f56c4d736e9fc250dc0be8147fadabedf6f',
    'source_status': 'proposed_unvalidated_coding_instrument',
    'scope': 'Concepts adapted in original short wording; the private source instrument is not bundled.'}
LIMITS = ['Unvalidated candidate instrument; no calibrated semantic accuracy or social trait scale.',
    'Classifier labels describe explicit text only, not verified actions, receipt, eligibility or causal influence.',
    'Opportunity and assessment remain uncertain/not_assessable until separately validated episode evidence exists.',
    'Missing or abstained measurements are unknown, not negative. No regex fallback or composite score.',
    'A bounded chronological sample does not estimate population prevalence.']


def _entry(identity, title, question, opportunity, positive, negative, unknown, screen, excludes):
    return {'id': identity, 'title': title, 'question': question, 'opportunity': opportunity,
        'positive': positive, 'negative': negative, 'unknown': unknown,
        'screen_prompt': screen, 'non_examples': excludes, 'status': 'proposed_unvalidated'}


BUILTINS = (
    _entry('C1', 'Contributing to an agreed task', 'Was an agreed contribution actually delivered?',
        'A feasible authorized assignment, exposure and a checkable endpoint.',
        'The assigned output is confirmed within the specified window.',
        'Direct evidence contradicts an applicable accepted assignment.',
        'An intention, completion statement or silence cannot establish delivery.',
        'The author explicitly reports delivering a contribution to an identified shared task.',
        'Future intentions, quoted reports, general teamwork language, and independent proof of completion.'),
    _entry('C2', 'Sharing qualified information', 'Did required information retain important qualifications?',
        'A concrete handoff request with actor access and permission established.',
        'The handoff includes relevant content, source and material uncertainty.',
        'A checked source is materially contradicted or loses a decisive qualification.',
        'Analyst access does not establish actor access or recipient uptake.',
        'The author shares task-relevant information with an explicit source or uncertainty qualifier.',
        'Unqualified assertions, classifier instructions, and evidence that a recipient used the information.'),
    _entry('C3', 'Preserving handoff dependencies', 'Did a recorded next action respect an acknowledged dependency?',
        'Identifiable sender and recipient, explicit requirements, established receipt.',
        'The handoff and checked next action preserve ownership and prerequisites.',
        'A recorded action crosses a still-applicable acknowledged dependency.',
        'Parallel preparation and clarification alone do not show a violation.',
        'The author explicitly names a task dependency, owner or prerequisite in a handoff.',
        'Time proximity, a named mention alone, and proof that the dependency was respected.'),
    _entry('C4', 'Following through on commitments', 'Was a specific promise resolved in its agreed window?',
        'A stated deliverable and closure rule with actor attribution.',
        'The promised output is independently confirmed in the window.',
        'A closed, applicable opportunity has directly corroborated nonfulfillment.',
        'Open windows, renegotiation and self-reports do not establish breach.',
        'The author makes an explicit commitment to a specified deliverable or deadline.',
        'Vague wishes, quoted promises, superseded commitments, and verified follow-through.'),
    _entry('C5', 'Checking consequential advice', 'Was reliance appropriate to evidence available to the actor?',
        'A recommendation-linked decision with receipt and an independent evidence standard.',
        'The recorded decision checks uncertainty or respects established evidence.',
        'A checked action disregards an acknowledged failed prerequisite.',
        'Confidence words do not establish calibrated trust or evidence availability.',
        'The author explicitly says they will check, defer, accept or reject another actor\'s recommendation.',
        'An inferred belief, confidence alone, and evidence that the advice was correct.'),
    _entry('C6', 'Responding to a correction', 'Did subsequent behavior address a valid received correction?',
        'A specific applicable correction with independent validity and established exposure.',
        'A checked revision resolves the issue, or a supported check justifies retaining the position.',
        'A recorded later action repeats an acknowledged error without new evidence.',
        'Disagreement or an apology alone does not establish correct revision.',
        'The author explicitly acknowledges, disputes or proposes action on a specific correction.',
        'Generic apology, imagined receipt, and independent correctness of the correction.'),
    _entry('C7', 'Helping after prior assistance', 'Was help returned in a separately applicable opportunity?',
        'Checked prior assistance and a later feasible request involving the same actors.',
        'The requested later assistance is confirmed.',
        'A still-applicable accepted request is explicitly frustrated without a legitimate constraint.',
        'Missing follow-up is not refusal; motivation and reciprocity effects remain unknown.',
        'The author explicitly links a current offer or request of help to earlier assistance.',
        'Repeated mentions, politeness alone, and verified reciprocity or motivation.'),
    _entry('C8', 'Respecting shared-resource rules', 'Did an actual resource decision respect its applicable rule?',
        'A known quota or reservation, actor exposure and measured resource state.',
        'Recorded use follows the rule or obtains the required authorization.',
        'A checked action exceeds an acknowledged limit or unauthorized reservation.',
        'Long sessions or many messages alone establish no rule violation.',
        'The author explicitly discusses a shared-resource quota, reservation or permission boundary.',
        'Usage volume alone, classifier instructions, and proof that a violation occurred.'),
)


def _bounded(value, maximum=65536):
    nodes = 0
    def visit(item, depth=0):
        nonlocal nodes
        nodes += 1
        if nodes > 20000 or depth > 12: raise ValueError('Rubric JSON exceeds its structural bounds')
        if item is None or type(item) is bool: return
        if type(item) in (int, float):
            if not math.isfinite(item) or abs(item) > 2**53 - 1: raise ValueError('Use bounded finite rubric values')
        elif type(item) is str: item.encode('utf-8')
        elif type(item) is list:
            if len(item) > 10000: raise ValueError('Rubric lists are too large')
            for child in item: visit(child, depth + 1)
        elif type(item) is dict:
            if len(item) > 128 or any(type(key) is not str for key in item): raise ValueError('Use small string-keyed rubric objects')
            for key, child in item.items(): key.encode('utf-8'); visit(child, depth + 1)
        else: raise ValueError('Use finite rubric JSON')
    visit(value)
    if len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode()) > maximum: raise ValueError('Rubric JSON is too large')
    return copy.deepcopy(value)


def _parse(raw, keys):
    if type(raw) is not bytes or not 0 < len(raw) <= 16000: raise ValueError('Use a bounded rubric JSON request')
    def pairs(items):
        value = {}
        for key, child in items:
            if key in value: raise ValueError('Duplicate rubric JSON field')
            value[key] = child
        return value
    def constant(_): raise ValueError('Use finite JSON')
    try: value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (RecursionError, UnicodeError): raise ValueError('Malformed or deeply nested rubric JSON') from None
    _bounded(value, 16000)
    if type(value) is not dict or set(value) != set(keys): raise ValueError('Rubric request fields do not match')
    return value


def _ref(value):
    if (type(value) is not dict or set(value) != {'id', 'version', 'hash'} or
        type(value['id']) is not str or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,199}', value['id']) or
        type(value['version']) is not int or not 1 <= value['version'] <= 10**9 or
        type(value['hash']) is not str or not re.fullmatch('[a-f0-9]{64}', value['hash'])):
        raise ValueError('Use an exact typed rubric/source reference')
    return copy.deepcopy(value)


def _record(lab, reference, kind):
    reference = _ref(reference); obj = lab.store.get(reference['id'], reference['version'])
    if obj['kind'] != kind or {key: obj[key] for key in reference} != reference or fingerprint(obj['payload']) != reference['hash']:
        raise ValueError('The exact rubric/source record does not match')
    return obj


def _spec(value):
    if type(value) is not dict or set(value) != set(FIELDS): raise ValueError('Supply the eight prompt-defined rubric fields')
    value = clean(_bounded(value, 16000))
    for key in FIELDS:
        maximum = 160 if key == 'title' else 800 if key == 'screen_prompt' else 300 if key == 'non_examples' else 1000
        if type(value[key]) is not str or not value[key].strip() or len(value[key]) > maximum:
            raise ValueError('Rubric ' + key + ' needs bounded nonblank plain text')
        value[key] = value[key].strip()
    return value


def _definitions(spec): return {'explicit_signal': {'description': spec['screen_prompt'], 'non_examples': spec['non_examples']}}
def _questions(spec): return build_questions(_definitions(spec), neutral_labels=True)
def _code_hashes():
    directory = Path(__file__).parent
    return {name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in
        ('behavior_rubrics.py', 'classifiers.py', 'measurement_backends.py')}


def rubric_catalog(lab):
    objects = lab.store.list('behavior_rubric', limit=7)
    saved = [{'ref': {key: obj[key] for key in ('id', 'version', 'hash')},
        'title': obj['payload']['spec']['title'][:120], 'question': obj['payload']['spec']['question'][:220],
        'text_truncated': len(obj['payload']['spec']['title']) > 120 or len(obj['payload']['spec']['question']) > 220,
        'status': 'proposed_unvalidated'} for obj in objects[:6]]
    return {'schema_version': VERSION, 'catalog': copy.deepcopy(list(BUILTINS)), 'saved': saved,
        'saved_truncated': len(objects) > 6, 'provenance': copy.deepcopy(PROVENANCE), 'limits': list(LIMITS),
        'laya': {'model_revision': LAYA_MODEL_REVISION, 'local_cpu': True, 'inference_available': 'checked_at_execution',
            'max_sample_messages': 32, 'fallback': 'none'}}


def save_rubric(lab, raw):
    spec = _spec(_parse(raw, FIELDS)); questions = _questions(spec)
    payload = {'schema_version': VERSION, 'status': 'proposed_unvalidated', 'created_at': now(),
        'spec': spec, 'prompt_hash': fingerprint(_definitions(spec)), 'question_schema': questions,
        'question_schema_hash': fingerprint(questions), 'implementation_hashes': _code_hashes(),
        'origin': 'user_or_agent_supplied_prompt', 'unit': 'single_record_explicit_text_screen',
        'episode_unit': 'actor_by_bounded_opportunity_requires_separate_validation',
        'assessment_default': 'not_assessable', 'opportunity_default': 'uncertain',
        'thresholds': {'false_at_or_below': .2, 'true_at_or_above': .8, 'otherwise': 'unknown'},
        'model_revision': LAYA_MODEL_REVISION, 'calibration': 'unestablished', 'limits': list(LIMITS)}
    obj = lab.store.put('behavior_rubric', payload)
    return {'rubric_ref': {key: obj[key] for key in ('id', 'version', 'hash')}, 'status': 'proposed_unvalidated'}


def validate_rubric_record(lab, reference):
    obj = _record(lab, reference, 'behavior_rubric'); p = obj['payload']; spec = _spec(p.get('spec'))
    questions = _questions(spec)
    if (p.get('schema_version') != VERSION or p.get('status') != 'proposed_unvalidated' or
        p.get('prompt_hash') != fingerprint(_definitions(spec)) or p.get('question_schema_hash') != fingerprint(questions) or
        fingerprint(p.get('question_schema')) != fingerprint(questions) or p.get('model_revision') != LAYA_MODEL_REVISION or
        fingerprint(p.get('implementation_hashes')) != fingerprint(_code_hashes()) or
        fingerprint(p.get('thresholds')) != fingerprint({'false_at_or_below': .2, 'true_at_or_above': .8, 'otherwise': 'unknown'}) or
        p.get('assessment_default') != 'not_assessable' or p.get('opportunity_default') != 'uncertain'):
        raise ValueError('Rubric prompt/schema/code or measurement boundaries changed; save a new rubric')
    return obj


def _messages(dataset):
    values = dataset['payload'].get('messages')
    if type(values) is not list or not 1 <= len(values) <= 10000: raise ValueError('Choose a bounded nonempty retained message dataset')
    identities = set(); result = []
    for message in values:
        if type(message) is not dict or type(message.get('id')) is not str or not message['id'] or len(message['id']) > 200:
            raise ValueError('Retained message identities must be bounded strings')
        if message['id'] in identities: raise ValueError('Retained message IDs must be unique')
        identities.add(message['id'])
        if type(message.get('content')) is not str or len(message['content']) > 64000: raise ValueError('Retained messages need bounded plain content')
        timestamp = message.get('timestamp', message.get('created_at'))
        if type(timestamp) is not str or not 1 <= len(timestamp) <= 100: raise ValueError('Retained messages require a declared timestamp')
        source = message.get('source', {})
        if type(source) is not dict: raise ValueError('Retained source provenance must be an object')
        for key in ('file', 'table'):
            if key in source and (type(source[key]) is not str or not 1 <= len(source[key]) <= 1000):
                raise ValueError('Retained source names must be bounded strings')
        if 'line' in source and (type(source['line']) is not int or not 1 <= source['line'] <= 2**53 - 1):
            raise ValueError('Retained source lines must be positive typed integers')
        content_hash = message.get('content_hash')
        if content_hash is not None and (type(content_hash) is not str or not re.fullmatch('[a-f0-9]{64}', content_hash)):
            raise ValueError('Declared retained content hash must be SHA-256 or unknown')
        result.append({'id': message['id'], 'content': message['content'], 'timestamp': timestamp,
            'source': {key: source[key] for key in ('file', 'line', 'table') if key in source},
            'declared_content_hash': content_hash})
    return result


def measure_rubric(lab, raw, *, backend_factory=None):
    """Run the actual local adapter; callback injection exists only for CPU tests."""
    request = _parse(raw, ('dataset_ref', 'rubric_ref', 'limit'))
    if type(request['limit']) is not int or not 1 <= request['limit'] <= 32: raise ValueError('Use 1–32 rubric measurement records')
    rubric = validate_rubric_record(lab, request['rubric_ref']); dataset = _record(lab, request['dataset_ref'], 'dataset')
    messages = _messages(dataset); spec = rubric['payload']['spec']; schema_hash = rubric['payload']['question_schema_hash']
    definitions = _definitions(spec)

    class PinnedBackend:
        def __init__(self, inner): self.inner = inner
        def measure(self, message, selected_definitions):
            value = _bounded(self.inner.measure(message, selected_definitions), 65536)
            if (type(value) is not dict or value.get('message_id') != message['id'] or value.get('question_schema_hash') != schema_hash or
                value.get('source_content_hash') != fingerprint(clean(message['content'])) or
                type(value.get('labels')) is not dict or set(value['labels']) != {'explicit_signal'} or
                type(value.get('probabilities')) is not dict or set(value['probabilities']) != {'explicit_signal'} or
                value.get('status') not in ('measured', 'partial_or_abstained', 'abstained')):
                raise BackendProtocolError('Laya record does not match the pinned rubric/source schema')
            label = value['labels']['explicit_signal']; probability = value['probabilities']['explicit_signal']
            if (label is not None and type(label) is not bool) or (probability is not None and
                (type(probability) not in (int, float) or not math.isfinite(probability) or not 0 <= probability <= 1)):
                raise BackendProtocolError('Laya must return typed labels and finite probabilities')
            if label is True and (probability is None or probability < .8) or label is False and (probability is None or probability > .2):
                raise BackendProtocolError('Laya label contradicts the pinned decision threshold')
            return value
        def close(self):
            if hasattr(self.inner, 'close'): self.inner.close()

    def factory():
        if backend_factory is not None: return PinnedBackend(backend_factory())
        executable = lab.settings.root / '.runtime' / 'laya-venv' / 'Scripts' / 'python.exe'
        if not executable.is_file(): raise BackendUnavailable('Laya isolated runtime is missing; no install or fallback was performed')
        return PinnedBackend(LayaProcessBackend(executable, timeout=90,
            cache_directory=lab.settings.root / '.runtime' / 'laya-cache', revision=LAYA_MODEL_REVISION,
            max_state_tokens=200, max_tokens=512))

    bounded = BoundedMeasurement('laya', messages, lab.settings.root, limit=request['limit'], factory=factory)
    bounded.base.neutral_labels = True  # Failure schemas must use the same pinned A/B variant.
    records = []
    try:
        for message in sorted(messages, key=lambda row: (row['timestamp'], row['id'])):
            if message['id'] not in bounded.selected_ids: continue
            bounded.classify(message, definitions); measured = bounded.last_measurement
            records.append({'message_id': message['id'], 'source': message['source'],
                'original_content_sha256': fingerprint(message['content']),
                'declared_compound_content_hash': message['declared_content_hash'],
                'text_measurement': measured, 'opportunity': 'uncertain', 'observability': 'partial',
                'assessment': 'not_assessable', 'reason': 'Single-message text inference does not validate an opportunity episode.'})
    finally: bounded.close()
    summary = bounded.summary(); summary['unit'] = 'single_record_explicit_text_screen'
    summary['motif_input'] = 'prompt_defined_laya_text_screen_only'
    labels = [row['text_measurement']['labels']['explicit_signal'] for row in records]
    summary.update(text_positive=sum(value is True for value in labels), text_negative=sum(value is False for value in labels),
        text_unknown=sum(value is None for value in labels), assessable_opportunities=0,
        rubric_assessment='not_assessable', all_records_retained=len(records))
    status = 'operational_failure' if bounded.error is not None else 'measured_text_only'
    payload = {'schema_version': VERSION, 'status': status, 'created_at': now(),
        'source_refs': {'dataset_ref': request['dataset_ref'], 'rubric_ref': request['rubric_ref']},
        'prompt_hash': rubric['payload']['prompt_hash'], 'question_schema_hash': schema_hash,
        'implementation_hashes': _code_hashes(), 'summary': summary, 'records': records,
        'calibration': 'unestablished', 'episode_assessment_available': False, 'limits': list(LIMITS)}
    obj = lab.store.put('rubric_measurement', payload)
    return {'measurement_ref': {key: obj[key] for key in ('id', 'version', 'hash')},
        'rubric_ref': request['rubric_ref'], 'dataset_ref': request['dataset_ref'], 'status': status, 'summary': summary}
