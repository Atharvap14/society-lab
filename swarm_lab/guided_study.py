"""Reviewable plan -> executable simulator -> audited live LLM intervention study.

This first-use route compiles the existing shared-file world. It does not claim
mechanism-fit approval, invent a new capability, or spend the guide allowance on
experimental subjects. Scientific live authoring remains a separate workflow.
"""
import json
import hashlib
from pathlib import Path
import re
import uuid
import copy

from .environments import create_environment, check_environment_contract, validate_spec
from .experiments import create_protocol, EVIDENCE_THOUGHT, PLACEBO_THOUGHT
from .store import clean, fingerprint, now


class _PinnedStore:
    """Legacy ID-only components see the authenticated frozen protocol version."""
    def __init__(self, store, record):
        self._store, self._record = store, copy.deepcopy(record)

    def __getattr__(self, name):
        return getattr(self._store, name)

    def get(self, identity, version=None):
        if identity == self._record['id']:
            if version is not None and version != self._record['version']:
                raise ValueError('A component requested a different frozen protocol version')
            return copy.deepcopy(self._record)
        return self._store.get(identity, version)


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('A JSON field was repeated')
        result[key] = value
    return result


def _constant(value):
    raise ValueError('Use finite JSON values')


def _parse(raw, fields):
    if type(raw) is not bytes or not 0 < len(raw) <= 64000:
        raise ValueError('Use a small JSON study request')
    body = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
    if type(body) is not dict or set(body) != set(fields):
        raise ValueError('The study request fields do not match this step')
    json.dumps(body, allow_nan=False).encode('utf-8')
    return body


def _ref(record):
    return {key: record[key] for key in ('id', 'version', 'hash')}


def _record(lab, source, kind):
    if (type(source) is not dict or set(source) != {'id', 'version', 'hash'} or
        type(source['id']) is not str or not re.fullmatch(r'[A-Za-z0-9_.-]{1,200}', source['id']) or
        type(source['version']) is not int or not 1 <= source['version'] <= 10**9 or
        type(source['hash']) is not str or not re.fullmatch('[0-9a-f]{64}', source['hash'])):
        raise ValueError('Choose an exact saved source version')
    record = lab.store.get(source['id'], source['version'])
    if record['kind'] != kind or record['hash'] != source['hash'] or fingerprint(record['payload']) != source['hash']:
        raise ValueError('The saved source does not match this request')
    return record


def _text(value, label):
    if type(value) is not str or not 1 <= len(value.strip()) <= 2000:
        raise ValueError(label + ' needs 1–2,000 characters')
    return clean(value.strip())


def _int(value, lo, hi, label):
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError(f'{label} must be an integer from {lo} to {hi}')
    return value


def _source(lab, source):
    if source is None:
        return None
    brief = _record(lab, source, 'observation_brief')
    refs = brief['payload'].get('source_refs', {})
    for field, kind in (('run_ref', 'observability_run'), ('dataset_ref', 'dataset')):
        if refs.get(field) is not None:
            _record(lab, refs[field], kind)
    return brief


def create_plan(lab, raw):
    body = _parse(raw, ('source_ref', 'signal_code', 'question', 'family', 'objective',
                        'control_text', 'treatment_text', 'trials_per_arm', 'seed',
                        'max_rounds', 'valid_probability'))
    if body['family'] != 'shared_artifact_coordination' or body['objective'] != 'correct_published_file':
        raise ValueError('This guided simulator supports the shared-file world and correct publication. Use full authoring for another objective.')
    brief = _source(lab, body['source_ref'])
    signal = body['signal_code']
    if signal is not None:
        if type(signal) is not str or brief is None or not any(row.get('code') == signal for row in brief['payload'].get('signals', [])):
            raise ValueError('Choose a signal from the exact briefing')
    question = _text(body['question'], 'Research question')
    control, treatment = _text(body['control_text'], 'Control note'), _text(body['treatment_text'], 'Intervention note')
    if control == treatment:
        raise ValueError('The control and intervention notes must differ')
    trials = _int(body['trials_per_arm'], 2, 20, 'Teams per condition')
    seed = _int(body['seed'], 0, 2**53 - 1, 'Allocation seed')
    rounds = _int(body['max_rounds'], 2, 12, 'Rounds')
    valid = body['valid_probability']
    if type(valid) not in (int, float) or not 0 <= valid <= 1:
        raise ValueError('Initial correct-file probability must be from 0 to 1')
    payload = {'schema_version': 'guided-study-v1', 'status': 'reviewed_for_live_study',
               'created_at': now(), 'source_ref': body['source_ref'], 'signal_code': signal,
               'question': question, 'family': body['family'], 'objective': body['objective'],
               'control_text': control, 'treatment_text': treatment, 'trials_per_arm': trials,
               'note_length_words': {'control': len(control.split()), 'intervention': len(treatment.split())},
               'seed': seed, 'max_rounds': rounds, 'valid_probability': valid,
               'subject_mode': 'live', 'primary_unit': 'whole_team',
               'conditions': ['baseline', 'placebo', 'evidence_thought'],
               'limitations': ['An abstract shared-file world, not reconstruction of the source swarm.',
                               'Source signals are candidates, not mechanism-fit approval.',
                               'Real LLM agents act in a bounded executable task; transfer to other tasks is unestablished.',
                               'The primary comparison is intervention versus control; no-note is exploratory.']}
    if len(control.split()) != len(treatment.split()):
        payload['limitations'].append('The notes have different word counts; this contrast cannot separate content from note length.')
    record = lab.store.put('guided_plan', payload)
    return {'plan_ref': _ref(record), 'plan': payload, 'paid_calls': 0}


def create_simulator(lab, raw):
    plan = _record(lab, _parse(raw, ('plan_ref',))['plan_ref'], 'guided_plan')
    p = plan['payload']
    if p.get('family') == 'village_document_access_repair':
        from .village_access_study import create_simulator as create_access_simulator
        return create_access_simulator(lab, raw)
    if p.get('status') != 'reviewed_for_live_study' or p.get('subject_mode') != 'live':
        raise ValueError('Review the supported live plan before creating its world')
    brief = _source(lab, p['source_ref'])
    identity = 'guided_simulator-' + fingerprint(_ref(plan))[:16]
    try:
        saved = lab.store.get(identity)
    except KeyError:
        saved = None
    if saved:
        if saved['payload']['plan_ref'] != _ref(plan):
            raise ValueError('This simulator does not match its saved plan')
        _record(lab, saved['payload']['plan_ref'], 'guided_plan')
        _record(lab, saved['payload']['protocol_ref'], 'protocol')
        return {'simulator_ref': _ref(saved), 'simulator': saved['payload'], 'paid_calls': 0}
    # Building is a real agent job. Reserve the plan before model calls so two
    # browser submissions cannot quietly build two different worlds.
    with lab.store.connect() as connection:
        connection.execute('CREATE TABLE IF NOT EXISTS guided_constructions(plan_hash TEXT PRIMARY KEY, job_id TEXT, status TEXT)')
        connection.execute('BEGIN IMMEDIATE')
        if connection.execute('SELECT 1 FROM guided_constructions WHERE plan_hash=?', (plan['hash'],)).fetchone():
            raise ValueError('This plan already has a simulator construction request. Inspect its activity or create a new plan.')
        build_job = 'guided-build-' + uuid.uuid4().hex[:12]
        connection.execute('INSERT INTO guided_constructions VALUES(?,?,?)', (plan['hash'], build_job, 'running'))
    try:
        lab.store.job(build_job, 'running', {'action': 'guided_world_builder', 'plan_ref': _ref(plan)})
        return _build_simulator(lab, plan, brief, identity, build_job)
    except Exception as error:
        with lab.store.connect() as connection:
            connection.execute('UPDATE guided_constructions SET status=? WHERE plan_hash=?', ('failed', plan['hash']))
        lab.store.job(build_job, 'failed', {'action': 'guided_world_builder', 'plan_ref': _ref(plan), 'error': str(error)[:1000]})
        raise


def _build_simulator(lab, plan, brief, identity, build_job):
    from .research import ResearchAgents, object_schema, TEXT, TEXTS, DESIGN_SCHEMA
    from .discovery import discover_cases
    p = plan['payload']
    dataset_ref = (brief or {}).get('payload', {}).get('source_refs', {}).get('dataset_ref')
    dataset = _record(lab, dataset_ref, 'dataset')['payload'] if dataset_ref else {'messages': [], 'agents': [], 'scope': {}, 'provenance': {'origin': 'manual_question'}}
    discovery = discover_cases(dataset['messages'], agents=dataset.get('agents', []))
    worker = ResearchAgents(lab.settings, lab.store, lab.research_harness('responses'))
    before_calls = lab.store.usage()['calls']
    built = worker.run('environment-builder', {
        'task': 'Build an executable shared-file handoff world from this reviewed plan using the supported template. Return one short declarative completion claim, an abstraction rationale and omitted capabilities. Do not put the allocation seed, treatment labels, historical future or task answer in the claim. Do not change the reviewed conditions, roles, budgets, objective or initial correct-file probability. The host compiles and checks the supported world.',
        'reviewed_plan': {key: p[key] for key in ('question', 'family', 'objective', 'max_rounds', 'valid_probability')},
        'source_brief': brief['payload'] if brief else None,
        'output_schema': object_schema({'completion_claim': TEXT, 'abstraction_rationale': TEXT, 'omitted_capabilities': TEXTS})},
        object_schema({'completion_claim': TEXT, 'abstraction_rationale': TEXT, 'omitted_capabilities': TEXTS}),
        dataset, discovery, build_job)
    claim = _text(built.get('completion_claim'), 'The environment agent completion claim')
    if re.search(r'\b(?:baseline|placebo|evidence_thought|allocation|treatment|control group|seed)\b', claim, re.I):
        raise ValueError('The environment claim reveals study labels or allocation information. Review a new plan.')
    backend = {'harness': 'responses', 'model': lab.settings.model,
               'generation': {'max_output_tokens': 600, 'temperature': 'provider_default', 'sampling_seed': 'not_set'}}
    protocol = create_protocol({'id': plan['id'], 'title': p['question'], 'source_refs': []},
                               trials_per_arm=p['trials_per_arm'], seed=p['seed'], max_rounds=p['max_rounds'],
                               research_question=p['question'], evidence_text=p['treatment_text'], placebo_text=p['control_text'],
                               environment_override={'initial_state_distribution': {'valid_probability': p['valid_probability'], 'completion_claim': claim}},
                               subject_backend=backend)
    validate_spec(protocol['environment'])
    checks = check_environment_contract(create_environment(protocol['environment'], p['seed']))
    if not checks.get('passed'):
        raise ValueError('The simulator failed its information-boundary checks')
    charter = worker.run('causal-methodologist', {
        'task': 'Review this fixed randomized live-agent protocol before execution. Explain its hypothesis, outcome oracle, confound checks, alternatives and limits. The host owns randomization and executable rules. Do not claim historical causation, eliminate all confounding, or change the frozen objective or conditions. Keep language simple.',
        'reviewed_plan': p, 'protocol': protocol, 'source_brief': brief['payload'] if brief else None, 'output_schema': DESIGN_SCHEMA},
        DESIGN_SCHEMA, dataset, discovery, build_job)
    registration = lab.store.put('protocol', {'protocol': protocol, 'frozen_hash': fingerprint(protocol),
        'registered_at': now(), 'status': 'registered', 'agent_mode': 'live',
        'subject_adapter_hash': hashlib.sha256(Path(__file__).with_name('harness.py').read_bytes()).hexdigest(),
        'behavior_id': None, 'guided_plan_ref': _ref(plan), 'source_brief_ref': p['source_ref'],
        'historical_mechanism_support': 'unestablished', 'abstract_pilot_override': True,
        'research_charter': charter,
        'environment_builder': {'status': 'agent_built_and_host_validated', 'proposal': built, 'boundary_checks': checks}})
    payload = {'schema_version': 'guided-simulator-v1', 'status': 'ready', 'name': 'Shared-file handoff world',
               'plan_ref': _ref(plan), 'protocol_ref': _ref(registration), 'source_brief_ref': p['source_ref'],
               'environment': protocol['environment'], 'boundary_checks': checks,
               'teams': p['trials_per_arm'] * 3, 'max_actions': p['trials_per_arm'] * 3 * 3 * p['max_rounds'],
               'subject_mode': 'live', 'model': lab.settings.model, 'harness': 'responses',
               'maximum_subject_calls': p['trials_per_arm'] * 3 * 3 * p['max_rounds'],
               'builder_proposal': built, 'causal_review': charter,
               'paid_calls': lab.store.usage()['calls'] - before_calls, 'limitations': p['limitations']}
    saved = lab.store.put('guided_simulator', payload, identity)
    with lab.store.connect() as connection:
        connection.execute('UPDATE guided_constructions SET status=? WHERE plan_hash=?', ('completed', plan['hash']))
    lab.store.job(build_job, 'completed', {'action': 'guided_world_builder', 'result_ids': [saved['id'], registration['id']]})
    return {'simulator_ref': _ref(saved), 'simulator': payload, 'paid_calls': payload['paid_calls']}


def execute_plan(lab, raw):
    simulator = _record(lab, _parse(raw, ('simulator_ref',))['simulator_ref'], 'guided_simulator')
    p = simulator['payload']
    if p.get('family') == 'village_document_access_repair':
        from .village_access_study import execute_plan as execute_access_plan
        return execute_access_plan(lab, raw)
    plan = _record(lab, p['plan_ref'], 'guided_plan')
    _source(lab, plan['payload']['source_ref'])
    registration = _record(lab, p['protocol_ref'], 'protocol')
    if p['environment'] != registration['payload']['protocol']['environment'] or p['subject_mode'] != 'live':
        raise ValueError('The executable world does not match its frozen registration')
    with lab.store.connect() as connection:
        connection.execute('CREATE TABLE IF NOT EXISTS guided_executions(simulator_id TEXT PRIMARY KEY, simulator_hash TEXT, job_id TEXT, status TEXT, result_ref TEXT)')
        connection.execute('BEGIN IMMEDIATE')
        previous = connection.execute('SELECT * FROM guided_executions WHERE simulator_id=?', (simulator['id'],)).fetchone()
        if previous:
            if previous['simulator_hash'] != simulator['hash']:
                raise ValueError('This simulator was changed after an execution request')
            if previous['status'] == 'completed':
                saved = _record(lab, json.loads(previous['result_ref']), 'guided_result')
                return {'execution_ref': _ref(saved), **saved['payload'], 'reused': True}
            raise ValueError('This simulator already has a running or failed execution. Inspect its log; create a new plan for a new study.')
        job_id = 'guided-' + uuid.uuid4().hex[:12]
        connection.execute('INSERT INTO guided_executions VALUES(?,?,?,?,?)', (simulator['id'], simulator['hash'], job_id, 'running', None))
    retained_stages = {}
    try:
        lab.store.job(job_id, 'running', {'action': 'guided_intervention', 'simulator_ref': _ref(simulator)})
        before_calls = lab.store.usage()['calls']
        runner_lab = copy.copy(lab)
        runner_lab.store = _PinnedStore(lab.store, registration)
        result = runner_lab.experiment(registration['id'], live=True, harness='responses', job_id=job_id)
        retained_stages['result_ref'] = _ref(result)
        proof = runner_lab.audit(result['id'])
        retained_stages['verification_ref'] = _ref(proof)
        if proof['payload'].get('passed') is not True:
            raise ValueError('The recorded experiment failed replay verification. Its result and checks are retained for review.')
        claims = runner_lab.evaluate_claims(result['id'], live=True, harness='responses', job_id=job_id+'.claims')
        retained_stages['claims_ref'] = _ref(claims)
        if claims['payload'].get('audit', {}).get('all_executable_claims_supported') is not True:
            raise ValueError('The AI result claims failed their finite checks. The result, replay proof and claims are retained for review.')
        payload = {'status': 'completed', 'job_id': job_id, 'simulator_ref': _ref(simulator),
                   'plan_ref': _ref(plan), 'source_brief_ref': plan['payload']['source_ref'],
                   'result_ref': _ref(result), 'verification_ref': _ref(proof), 'claims_ref': _ref(claims),
                   'paid_calls': lab.store.usage()['calls'] - before_calls, 'subject_mode': 'live', 'scope': plan['payload']['limitations']}
        saved = lab.store.put('guided_result', payload)
        with lab.store.connect() as connection:
            connection.execute('UPDATE guided_executions SET status=?,result_ref=? WHERE simulator_id=?', ('completed', json.dumps(_ref(saved)), simulator['id']))
        lab.store.job(job_id, 'completed', {'action': 'guided_intervention', 'result_ids': [result['id'], proof['id'], claims['id'], saved['id']]})
        return {'execution_ref': _ref(saved), **payload, 'reused': False}
    except Exception as error:
        with lab.store.connect() as connection:
            connection.execute('UPDATE guided_executions SET status=? WHERE simulator_id=?', ('failed', simulator['id']))
        previous_job = next((row for row in lab.store.jobs(limit=1000) if row['id'] == job_id), None)
        failure = dict((previous_job or {}).get('payload') or {})
        failure.update(retained_stages)
        failure.update({'action': 'guided_intervention', 'simulator_ref': _ref(simulator), 'error': str(error)[:1000]})
        lab.store.job(job_id, 'failed', failure)
        raise
