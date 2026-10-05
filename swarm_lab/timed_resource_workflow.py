"""Registration, durable execution and replay for the separate timing study."""
import copy
import json
import re
import uuid
from pathlib import Path

from .library import verify_protocol
from .resource_workflow import resource_backend
from .store import fingerprint, now


def timed_resource_backend(lab, live):
    if type(live) is not bool:
        raise ValueError('live must be boolean')
    if live:
        return resource_backend(lab, True)
    from .timed_resource_experiments import OFFLINE_BACKEND
    return copy.deepcopy(OFFLINE_BACKEND)


def design_timed_resource(lab, *, behavior_id=None, trials_per_cell=2, seed=149,
        trigger_kind='executed_wait_independent_pending', max_rounds=6,
        release_rounds=(1, 2), independent_work_steps=1, computer_work_steps=1,
        max_messages_per_agent=None, active_text=None, neutral_text=None,
        resamples=2000, live=False):
    from .timed_resource_experiments import create_timed_resource_protocol
    incident = None
    ref = None
    if behavior_id:
        obj = lab.store.get(behavior_id)
        p = obj['payload']
        if (obj['kind'] != 'behavior' or p.get('status') == 'rejected'
                or p.get('research_quality_status') in (
                    'schema_defect_requires_re_review', 'superseded_schema_defect_review')
                or fingerprint(p) != obj['hash']):
            raise ValueError('Use an unchanged non-rejected reviewed behavior')
        ref = {key: obj[key] for key in ('kind', 'id', 'version', 'hash')}
        incident = {'id': behavior_id, 'title': p['name'], 'source_refs': p.get('source_refs', {})}
    backend = timed_resource_backend(lab, live)
    notes = {}
    if active_text is not None:
        notes['active_text'] = active_text
    if neutral_text is not None:
        notes['neutral_text'] = neutral_text
    protocol = create_timed_resource_protocol(
        trials_per_cell=trials_per_cell, seed=seed, trigger_kind=trigger_kind,
        max_rounds=max_rounds, release_rounds=release_rounds,
        independent_work_steps=independent_work_steps, computer_work_steps=computer_work_steps,
        max_messages_per_agent=max_messages_per_agent, subject_backend=backend,
        incident=incident, resamples=resamples, **notes)
    return lab.store.put('timed_resource_protocol', {
        'protocol': protocol, 'frozen_hash': fingerprint(protocol),
        'registered_at': now(), 'status': 'registered',
        'agent_mode': 'live' if live else 'offline_template',
        'behavior_id': behavior_id, 'behavior_ref': ref,
        'historical_mechanism_support': 'Unestablished; globally exclusive resource access is an invented analogue.',
        'subject_adapter_hash': backend.get('harness_adapter_hash')})


def _stored_execution(lab, raw, registration, directory, job_id, live):
    result = copy.deepcopy(raw)
    canonical_hash = result.pop('report_hash')
    result.update(
        protocol_id=registration['id'],
        protocol_ref={key: registration[key] for key in ('id', 'version', 'hash')},
        registered_hash=registration['payload']['frozen_hash'],
        behavior_id=registration['payload'].get('behavior_id'),
        agent_mode='live' if live else 'offline_simulation',
        model=raw['protocol']['subject_backend']['model'],
        artifact_directory=str(directory), research_job_id=job_id,
        canonical_execution_report_hash=canonical_hash)
    return lab.store.put('timed_resource_experiment', result)


def experiment_timed_resource(lab, protocol_id, *, live=False, job_id=None):
    from .timed_resource_experiments import (
        run_timed_resource_experiment, validate_timed_resource_protocol)
    registration = lab.store.get(protocol_id)
    if registration['kind'] != 'timed_resource_protocol' or fingerprint(registration['payload']) != registration['hash']:
        raise ValueError('Use an unchanged timing-specific registered protocol')
    protocol = verify_protocol(registration)
    validate_timed_resource_protocol(protocol)
    backend = timed_resource_backend(lab, live)
    if fingerprint(protocol['subject_backend']) != fingerprint(backend):
        raise ValueError('Subject backend differs from the frozen timing registration')
    maximum = protocol['design']['maximum_subject_calls']
    if live and lab.store.usage()['calls'] + maximum > lab.settings.max_calls:
        raise ValueError(f'Worst-case {maximum} subject calls exceed the remaining cap; explicitly increase the cap before running')
    job_id = job_id or 'timed-resource-' + uuid.uuid4().hex[:12]
    if not isinstance(job_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', job_id):
        raise ValueError('Use a short execution identity without path separators')
    saved_job = lab.store.get_job(job_id)
    if saved_job and saved_job['status'] in ('completed', 'failed'):
        raise ValueError('This job was already launched; preserve its saved result')
    directory = lab.settings.runtime / 'runs' / job_id
    directory.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive mkdir is the execution claim; concurrent calls cannot share it.
    try:
        directory.mkdir()
    except FileExistsError:
        raise ValueError('Execution directory already exists; choose a fresh job identity') from None
    model = None
    runner = None
    if live:
        def runner(request):
            return model.subject({**request, '_job_id': job_id})
    def progress(value):
        lab.store.job(job_id, 'running', {
            'stage': 'timed_resource_experiment', 'protocol_id': protocol_id,
            'progress': value, 'live': live})
    lab.store.job(job_id, 'running', {
        'stage': 'timed_resource_experiment', 'protocol_id': protocol_id, 'live': live})
    try:
        if live:
            model = lab.harness('responses')
        raw = run_timed_resource_experiment(
            protocol, agent_runner=runner, output_dir=directory,
            backend_metadata=backend, on_progress=progress)
    except Exception as error:
        partial = getattr(error, 'partial_report', None)
        path = directory / 'report.json'
        if partial is None and path.is_file():
            partial = json.loads(path.read_text(encoding='utf-8'))
        incomplete = _stored_execution(lab, partial, registration, directory, job_id, live) if partial else None
        lab.store.job(job_id, 'failed', {
            'stage': 'timed_resource_experiment', 'protocol_id': protocol_id,
            'error': str(error), 'incomplete_result_id': incomplete['id'] if incomplete else None,
            'artifact_directory': str(directory), 'live': live})
        lab.store.trace(job_id, {'type': 'experiment_failure', 'protocol_id': protocol_id,
            'artifact_directory': str(directory),
            'analysis': 'None; all assignments and available partial evidence retained without behavioral exclusions.'})
        raise
    obj = _stored_execution(lab, raw, registration, directory, job_id, live)
    lab.store.job(job_id, 'completed', {
        'stage': 'timed_resource_experiment', 'protocol_id': protocol_id,
        'result_id': obj['id'], 'live': live})
    return obj


def audit_timed_resource(lab, result_id):
    from .timed_resource_experiments import replay_timed_resource_report
    from .audit import check_execution_archive
    obj = lab.store.get(result_id)
    if obj['kind'] != 'timed_resource_experiment' or fingerprint(obj['payload']) != obj['hash']:
        raise ValueError('Use an unchanged timing resource execution result')
    result = obj['payload']
    directory = Path(result['artifact_directory'])
    path = directory / 'report.json'
    if not path.is_file():
        return lab.store.put('verification', {
            'experiment_id': result_id, 'result_kind': obj['kind'],
            'result_ref': {key: obj[key] for key in ('id', 'version', 'hash')},
            'passed': False, 'model_calls': 0,
            'checks': [{'name': 'canonical_report_available', 'passed': False}],
            'scope': 'Retained incomplete evidence cannot replace an unavailable canonical execution archive.'})
    raw = json.loads(path.read_text(encoding='utf-8'))
    verification = replay_timed_resource_report(raw, output_dir=directory)
    ref = result['protocol_ref']
    if (not isinstance(ref, dict) or not isinstance(ref.get('id'), str)
            or type(ref.get('version')) is not int or ref['version'] < 1
            or not isinstance(ref.get('hash'), str)):
        raise ValueError('Use an exact positive-version timing registration reference')
    registration = lab.store.get(ref['id'], ref['version'])
    if (registration['kind'] != 'timed_resource_protocol' or registration['hash'] != ref['hash']
            or fingerprint(registration['payload']) != ref['hash']
            or fingerprint(ref) != fingerprint({key: registration[key] for key in ('id', 'version', 'hash')})):
        raise ValueError('Timing registration reference mismatch')
    expected = verify_protocol(registration)
    checks = verification['checks']
    raw_core = {key: value for key, value in raw.items() if key != 'report_hash'}
    stored_core = {key: result.get(key) for key in raw_core}
    backend = expected['subject_backend']
    binding = {
        'protocol_id': registration['id'],
        'registered_hash': registration['payload']['frozen_hash'],
        'behavior_id': registration['payload'].get('behavior_id'),
        'agent_mode': 'live' if backend['harness'] == 'responses' else 'offline_simulation',
        'model': backend['model']}
    checks.append({'name': 'stored_result_matches_canonical_execution', 'passed': all((
        set(raw_core).issubset(result), set(binding).issubset(result),
        fingerprint(raw['protocol']) == fingerprint(expected),
        raw.get('report_hash') == result.get('canonical_execution_report_hash'),
        fingerprint(raw_core) == fingerprint(stored_core),
        fingerprint(binding) == fingerprint({key: result.get(key) for key in binding})))})
    archive = check_execution_archive(directory)
    checks.append({'name': 'execution_archive_bytes', 'passed': archive['status'] == 'verified'})
    manifest_path = directory / 'execution-code' / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.is_file() else {}
    checks.append({'name': 'archive_matches_registered_sources',
        'passed': manifest.get('files') == expected['execution_code_hashes']})
    verification.update(
        passed=verification['passed'] and all(c['passed'] for c in checks),
        execution_archive=archive, report_status=raw.get('status'))
    return lab.store.put('verification', {
        'experiment_id': result_id, 'result_kind': obj['kind'],
        'result_ref': {key: obj[key] for key in ('id', 'version', 'hash')}, **verification})


def evaluate_timed_resource_claims(lab, result_id, *, live=False,
        harness='responses', job_id=None, fact_ids=None):
    """Interpret finite facts only after a separate pinned host/archive audit."""
    from dataclasses import replace
    from .timed_resource_claims import (build_timed_resource_fact_ledger,
        default_timed_resource_fact_ids, audit_timed_resource_claims)
    from .claim_audit import select_fact_packet, claims_schema_for_packet, make_claim
    from .research import ResearchAgents
    if type(live) is not bool:
        raise ValueError('live must be boolean')
    obj = lab.store.get(result_id)
    if obj['kind'] != 'timed_resource_experiment':
        raise ValueError('Use a timed resource execution result')
    result = obj['payload']
    raw = json.loads((Path(result['artifact_directory']) / 'report.json').read_text(encoding='utf-8'))
    verification = audit_timed_resource(lab, result_id)
    proof = verification['payload']
    if raw.get('status') == 'complete' and proof.get('passed') is not True:
        raise ValueError(f'Timing replay or source archive failed; quantitative facts unavailable. See {verification["id"]}')
    ref = {key: obj[key] for key in ('id', 'version', 'hash')}
    ledger = build_timed_resource_fact_ledger(raw, report_id=result_id,
        source_ref=ref, source_object=obj, replay_check=lambda report: proof)
    packet = select_fact_packet(ledger, fact_ids if fact_ids is not None else
        default_timed_resource_fact_ids(ledger, max_facts=24), max_facts=24)
    job_id = job_id or 'timed-claim-audit-' + uuid.uuid4().hex[:10]
    if live:
        bounded = replace(lab.settings, max_output_tokens=6000, max_tool_rounds=2)
        agent = ResearchAgents(bounded, lab.store, lab.research_harness(harness, bounded))
        schema = claims_schema_for_packet(packet)
        response = agent.run('evaluator', {'task': (
            'Interpret only this finite post-execution timing-policy packet. This aggregate review shows arm labels '
            'and is not blinded. Copy each supplied fact identity, value, kind, scope and source fingerprint. '
            'Independent seed blocks determine uncertainty; agents, turns, receipts and paired swarms are not extra samples. '
            'Keep every assigned completed swarm in the policy ITT, including nondelivery. Receipt and waiting counts '
            'are post-treatment descriptions, not identified mediators. Incomplete execution exposes metadata only. '
            'Approved fact text alone is verified; attached prose, provider consumption, latent thoughts, historical '
            'mechanisms and generalized effects remain unverified.'),
            'fact_packet': packet, 'output_schema': schema}, schema,
            {'messages': [], 'scope': {}}, {'graph': {'edges': []}, 'candidates': []}, job_id)
        claims = response['claims']
    else:
        claims = [make_claim(ledger, identity, fact['value']) for identity, fact in packet['facts'].items()]
    audit = audit_timed_resource_claims(ledger, claims)
    return lab.store.put('claim_audit', {
        'experiment_id': result_id, 'result_kind': obj['kind'], 'result_ref': ref,
        'verification_ref': {key: verification[key] for key in ('id', 'version', 'hash')},
        'canonical_execution_report_hash': raw.get('report_hash'),
        'agent_mode': 'live' if live else 'offline_fact_reconstruction',
        'fact_packet': packet, 'claims': claims, 'audit': audit,
        'quantitative_facts_available': ledger['quantitative_facts_available'],
        'status': 'metadata_only' if not ledger['quantitative_facts_available'] else
            'verified_facts_only' if audit['all_executable_claims_supported'] else 'claim_mismatches',
        'verification_checks': ledger['verification_checks'], 'issues': ledger['issues'],
        'research_job_id': job_id,
        'prose_scope': 'Generated approved_fact_text alone is checked; model prose, provider consumption, beliefs, mediation and historical fidelity remain unverified.'})
