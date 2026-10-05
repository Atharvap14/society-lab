"""Exact registration, bounded execution claims, and fresh zero-call replay.

Optional relay capability only. This host never promotes a behavior or adds a
generic research cycle. Scripted execution is default; live execution needs its
exact frozen Responses backend and the configured global call ceiling, currently
400. This host never raises that setting.
"""
from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import uuid

from swarm_lab.store import clean, fingerprint as store_fingerprint, now

INSTRUMENT_VERSION = 'revision-relay-host-workflow-v1'
_RUNNER = None
_REGISTRATION_KEYS = {'instrument_version', 'protocol', 'frozen_hash', 'protocol_hash',
    'registered_at', 'status', 'agent_mode', 'behavior_ref', 'host_source_hash', 'backend',
    'historical_mechanism_support', 'generic_cycle_support', 'status_promotion'}
_RESULT_KEYS = {'instrument_version', 'status', 'raw_report', 'analysis', 'protocol_ref',
    'behavior_ref', 'canonical_execution_report_hash', 'registered_protocol_hash',
    'artifact_root', 'artifact_directory', 'artifact_pins', 'host_source_hash',
    'research_job_id', 'study_claim_id', 'agent_mode', 'backend', 'host_failure_error_type',
    'status_promotion', 'generic_cycle_support', 'scope'}
_SCOPE = 'Exact synthetic assigned policies; queue placement and local requests do not attest provider consumption.'


def _runner():
    global _RUNNER
    if _RUNNER is None:
        if __package__:
            from . import revision_relay_experiments
            _RUNNER = revision_relay_experiments
        else:
            path = Path(__file__).with_name('revision_relay_experiments.py')
            spec = importlib.util.spec_from_file_location('_staged_relay_experiments_host', path)
            _RUNNER = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_RUNNER)
    return _RUNNER


def _sha(path):
    return hashlib.sha256(_read_bytes(Path(path), 1024 * 1024)).hexdigest()


def _read_bytes(path, maximum):
    # Physical reads stay bounded even if a file grows after a stat call.
    with path.open('rb') as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError('Artifact byte bound exceeded')
    return data


def _host_guard():
    if _sha(__file__) != _LOADED_HOST_SHA256:
        raise ValueError('Loaded relay host source changed')


def _same(left, right):
    return _runner()._same(left, right)


def _identity(value, cap=None):
    runner = _runner()
    runner._bounded(value, runner.MAX_REPORT_BYTES if cap is None else cap)
    if not _same(clean(value), value):
        raise ValueError('Sanitizer changes canonical relay evidence identity')


def _integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{name} must be integer in [{low},{high}]')
    return value


def _ref(obj):
    return {key: obj[key] for key in ('id', 'version', 'hash')}


def _resolve(lab, reference, kind):
    _runner()._reference(reference)
    obj = lab.store.get(reference['id'], reference['version'])
    if (obj['kind'] != kind or not _same(_ref(obj), reference) or
            store_fingerprint(obj['payload']) != obj['hash']):
        raise ValueError('Exact registered source reference mismatch')
    return obj


def _behavior(lab, reference):
    if reference is None:
        return None
    obj = _resolve(lab, reference, 'behavior')
    payload = obj['payload']
    if payload.get('status') == 'rejected' or payload.get('research_quality_status') in (
            'schema_defect_requires_re_review', 'superseded_schema_defect_review'):
        raise ValueError('Use a non-rejected exact behavior reference')
    return obj


def revision_relay_backend(lab, live):
    if type(live) is not bool:
        raise ValueError('live must be explicit boolean')
    runner = _runner()
    if not live:
        return copy.deepcopy(runner.OFFLINE_BACKEND)
    if type(lab.settings.model) is not str or not 1 <= len(lab.settings.model) <= 120:
        raise ValueError('Use a bounded model name')
    backend = {'harness': 'responses', 'model': lab.settings.model,
        'generation': {'max_output_tokens': 600, 'temperature': 'provider_default', 'sampling_seed': 'not_set'},
        'harness_adapter_hash': runner.revision_relay_code_hashes()['harness.py']}
    _identity(backend, 8192)
    runner._backend(backend)
    return backend


def design_revision_relay(lab, *, blocks=2, seed=173, live=False,
        behavior_ref=None, interval_assumptions=None):
    _host_guard()
    runner = _runner()
    behavior = _behavior(lab, behavior_ref)
    if interval_assumptions is not None and (type(interval_assumptions) is not dict or
            set(interval_assumptions) != {'independent_blocks_declared', 'stable_subject_backend_declared'} or
            any(type(value) is not bool for value in interval_assumptions.values())):
        raise ValueError('Use explicit typed interval assumption declarations')
    backend = revision_relay_backend(lab, live)
    protocol = runner.create_revision_relay_protocol(blocks, seed,
        subject_backend=backend, source_refs={'behavior': _ref(behavior)} if behavior else {},
        interval_assumptions=interval_assumptions)
    runner.validate_revision_relay_protocol(protocol)
    payload = {'instrument_version': INSTRUMENT_VERSION, 'protocol': protocol,
        'frozen_hash': runner._hash(protocol), 'protocol_hash': protocol['protocol_hash'],
        'registered_at': now(), 'status': 'registered',
        'agent_mode': 'live_registered_not_executed' if live else 'scripted_registered_not_executed',
        'behavior_ref': _ref(behavior) if behavior else None,
        'host_source_hash': _LOADED_HOST_SHA256,
        'backend': backend, 'historical_mechanism_support': 'unestablished',
        'generic_cycle_support': False, 'status_promotion': False}
    _identity(payload)
    return lab.store.put('revision_relay_protocol', payload)


def _registration(lab, protocol_id, version):
    _integer(version, 1, 10 ** 9, 'protocol_version')
    if type(protocol_id) is not str or not 1 <= len(protocol_id) <= 200:
        raise ValueError('Use a bounded registered protocol ID')
    obj = lab.store.get(protocol_id, version)
    if obj['kind'] != 'revision_relay_protocol' or store_fingerprint(obj['payload']) != obj['hash']:
        raise ValueError('Use the exact revision-relay registration')
    payload = obj['payload']; runner = _runner()
    if (type(payload) is not dict or set(payload) != _REGISTRATION_KEYS or
            payload.get('instrument_version') != INSTRUMENT_VERSION or payload.get('status') != 'registered' or
            payload.get('host_source_hash') != _LOADED_HOST_SHA256 or
            payload.get('historical_mechanism_support') != 'unestablished' or
            payload.get('status_promotion') is not False or payload.get('generic_cycle_support') is not False or
            type(payload.get('registered_at')) is not str or not 1 <= len(payload['registered_at']) <= 50):
        raise ValueError('Host registration or source pin changed')
    protocol = payload['protocol']; runner.validate_revision_relay_protocol(protocol)
    if (payload.get('frozen_hash') != runner._hash(protocol) or
            payload.get('protocol_hash') != protocol['protocol_hash'] or
            not _same(payload.get('backend'), protocol['subject_backend']) or
            payload.get('agent_mode') != ('scripted_registered_not_executed'
                if protocol['subject_backend']['harness'] == 'scripted' else 'live_registered_not_executed')):
        raise ValueError('Registered protocol/backend identity changed')
    behavior = _behavior(lab, payload.get('behavior_ref'))
    expected_sources = {'behavior': _ref(behavior)} if behavior else {}
    if not _same(protocol['source_refs'], expected_sources):
        raise ValueError('Registered source bindings changed')
    _identity(payload)
    return obj


class _SubjectTraceStore:
    """Forward atomic calls/jobs; keep metadata instead of provider envelopes."""
    def __init__(self, store):
        self._store = store

    def __getattr__(self, name):
        return getattr(self._store, name)

    def finish_call(self, call_id, status, usage=None):
        # Keep the same atomic reservation/status and available numeric token
        # metadata. Never persist an arbitrary provider usage envelope.
        safe = {}
        if type(usage) is dict:
            for key in ('input_tokens', 'output_tokens', 'total_tokens'):
                value = usage.get(key)
                if type(value) is int and 0 <= value <= 10 ** 9:
                    safe[key] = value
        return self._store.finish_call(call_id, status, safe)

    def trace(self, job_id, payload):
        if type(payload) is not dict:
            raise ValueError('Subject trace must be metadata')
        kind = payload.get('type')
        if kind == 'model_response':
            allowed = {'type': 'subject_response_metadata', 'provider_origin': 'metadata_not_attested',
                'response_id': None, 'model': None, 'input_hash': None, 'usage': None, 'seconds': None,
                'metadata_status': {key: 'unknown' for key in ('response_id', 'model', 'input_hash', 'usage', 'seconds')}}
            for key in ('response_id', 'model', 'input_hash'):
                value = payload.get(key)
                if type(value) is str and len(value) <= 200 and _same(clean(value), value):
                    allowed[key] = value
                    allowed['metadata_status'][key] = 'reported_unattested'
            usage = payload.get('usage')
            if type(usage) is dict:
                allowed['usage'] = {key: usage.get(key) if type(usage.get(key)) is int and
                    0 <= usage[key] <= 10 ** 9 else None for key in ('input_tokens', 'output_tokens', 'total_tokens')}
                allowed['metadata_status']['usage'] = 'reported_fields_with_unknowns_unattested'
            seconds = payload.get('seconds')
            if type(seconds) in (int, float) and math.isfinite(seconds) and 0 <= seconds <= 3600:
                allowed['seconds'] = seconds
                allowed['metadata_status']['seconds'] = 'reported_unattested'
            return self._store.trace(job_id, allowed)
        if kind == 'api_error':
            allowed = {'type': 'subject_transport_error_metadata'}
            if type(payload.get('status')) is int and 100 <= payload['status'] <= 599:
                allowed['http_status'] = payload['status']
            return self._store.trace(job_id, allowed)
        raise ValueError('Unexpected subject trace envelope')


def _host_archive(root):
    archive = root / 'host-code'
    archive.mkdir()
    data = _read_bytes(Path(__file__), 1024 * 1024)
    if hashlib.sha256(data).hexdigest() != _LOADED_HOST_SHA256:
        raise ValueError('Host source changed before archive')
    (archive / 'revision_relay_workflow.py').write_bytes(data)
    manifest = {'instrument_version': INSTRUMENT_VERSION,
        'files': {'revision_relay_workflow.py': _LOADED_HOST_SHA256},
        'timing': 'before_pure_runner_invocation', 'scope': 'source_bytes_not_runtime_execution_attestation'}
    (archive / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True), encoding='utf-8')


def _artifact_pins(root, protocol):
    expected = ['host-code/revision_relay_workflow.py', 'host-code/manifest.json',
        'execution/protocol.json', 'execution/assignment.json', 'execution/report.json',
        'execution/execution-code/manifest.json']
    expected += ['execution/execution-code/' + name for name in protocol['execution_code_hashes']]
    expected += ['execution/design-source/' + name for name in protocol['design_source_hashes']]
    pins = {}
    for relative in expected:
        path = root / relative
        if path.is_file():
            maximum = _runner().MAX_REPORT_BYTES if relative.endswith('report.json') else 1024 * 1024
            if (not path.resolve(strict=True).is_relative_to(root.resolve(strict=True)) or
                    any((root.joinpath(*path.relative_to(root).parts[:index])).is_symlink()
                        for index in range(1, len(path.relative_to(root).parts) + 1))):
                raise ValueError('Artifact link/path escape is unsupported')
            data = _read_bytes(path, maximum)
            pins[relative] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
        else:
            pins[relative] = None
    return pins


def _store_result(lab, raw, registration, root, job_id, claim_id, live, *, error_type=None):
    if raw is not None:
        _identity(raw)
    payload = {'instrument_version': INSTRUMENT_VERSION,
        'status': raw['status'] if raw is not None else 'incomplete_host_failure',
        'raw_report': copy.deepcopy(raw), 'analysis': copy.deepcopy(raw.get('analysis')) if raw else None,
        'protocol_ref': _ref(registration), 'behavior_ref': registration['payload'].get('behavior_ref'),
        'canonical_execution_report_hash': raw.get('report_hash') if raw else None,
        'registered_protocol_hash': registration['payload']['frozen_hash'],
        'artifact_root': str(root), 'artifact_directory': str(root / 'execution'),
        'artifact_pins': _artifact_pins(root, registration['payload']['protocol']),
        'host_source_hash': _LOADED_HOST_SHA256, 'research_job_id': job_id, 'study_claim_id': claim_id,
        'agent_mode': 'live' if live else 'scripted_infrastructure',
        'backend': registration['payload']['backend'], 'host_failure_error_type': error_type,
        'status_promotion': False, 'generic_cycle_support': False,
        'scope': _SCOPE}
    _identity(payload)
    return lab.store.put('revision_relay_experiment', payload)


def _job_identity(lab, job_id, registration, live):
    if job_id is None:
        return 'relay-job-' + uuid.uuid4().hex[:16], False
    if type(job_id) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', job_id):
        raise ValueError('Use a bounded job identity without path syntax')
    _identity(job_id, 256)
    saved = lab.store.get_job(job_id)
    if saved is None:
        return job_id, False
    args = saved['payload'].get('args', {})
    if (saved['status'] not in ('queued', 'running') or
            saved['payload'].get('action') != 'experiment_revision_relay' or type(args) is not dict or
            args.get('protocol_id') != registration['id'] or
            not _same(args.get('protocol_version'), registration['version']) or
            not _same(args.get('live', False), live)):
        raise ValueError('Job identity was already used or does not match this queue request')
    return job_id, True


def experiment_revision_relay(lab, protocol_id, *, protocol_version, live=False, job_id=None):
    _host_guard(); runner = _runner()
    registration = _registration(lab, protocol_id, protocol_version)
    protocol = registration['payload']['protocol']
    backend = revision_relay_backend(lab, live)
    if not _same(protocol['subject_backend'], backend):
        raise ValueError('Execution mode/model/backend differs from frozen registration')
    cap = _integer(lab.settings.max_calls, 0, 100000, 'max_calls')
    usage = _integer(lab.store.usage()['calls'], 0, 10 ** 9, 'usage.calls')
    if live and usage + protocol['design']['maximum_subject_calls'] > cap:
        raise ValueError('Worst-case subject calls exceed the unchanged global/remaining cap')
    job_id, outer_claimed = _job_identity(lab, job_id, registration, live)
    claim_id = 'relay-study-' + runner._hash(_ref(registration))[:24]
    # A fixed registration/version is a study identity, independent of caller
    # job names. Claim before directories/harnesses: no repeated study/retry.
    lab.store.start_job(claim_id, {'stage': 'revision_relay_study_claim',
        'protocol_ref': _ref(registration), 'research_job_id': job_id})
    root = lab.settings.runtime / 'runs' / ('revision-relay-' + uuid.uuid4().hex)
    model = None
    raw = None
    result = None
    outer_started = outer_claimed
    def subject(request):
        nonlocal model
        _identity(request, runner.MAX_REQUEST_BYTES)
        if model is None:
            isolated = copy.copy(lab)
            isolated.settings = replace(lab.settings, max_calls=cap)
            isolated.store = _SubjectTraceStore(lab.store)
            model = isolated.harness('responses')
        output = model.subject({**request, '_job_id': job_id})
        # Unbounded/non-JSON behavior belongs to the adapter's explicit marker,
        # but bounded output must never silently change under Store redaction.
        try:
            runner._bounded(output, runner.world.MAX_RETAINED_ACTION_BYTES, depth=8, nodes=128)
        except (ValueError, TypeError, OverflowError, RecursionError):
            return output
        _identity(output, runner.world.MAX_RETAINED_ACTION_BYTES)
        return output
    def progress(value):
        lab.store.job(job_id, 'running', {'stage': 'revision_relay_experiment',
            'protocol_ref': _ref(registration), 'progress': value, 'live': live})
    try:
        if not outer_claimed:
            lab.store.start_job(job_id, {'stage': 'revision_relay_experiment', 'protocol_ref': _ref(registration)})
            outer_started = True
        root.parent.mkdir(parents=True, exist_ok=True)
        root.mkdir()  # Host-chosen exclusive root, never caller-supplied path.
        _host_archive(root)
        raw = runner.run_revision_relay_experiment(protocol,
            agent_runner=subject if live else None, output_dir=root / 'execution',
            backend_metadata=backend, on_progress=progress)
        result = _store_result(lab, raw, registration, root, job_id, claim_id, live)
        closure = {'stage': 'revision_relay_experiment', 'protocol_ref': _ref(registration),
            'result_id': result['id'], 'result_ref': _ref(result), 'artifact_directory': str(root / 'execution'), 'live': live}
        lab.store.job(claim_id, 'completed', closure)
        lab.store.job(job_id, 'completed', closure)
        return result
    except Exception as error:
        partial = getattr(error, 'partial_report', None) or raw
        try:
            # A publication failure must keep an already stored complete result;
            # it cannot replace finished science with a manufactured empty run.
            if result is None:
                result = _store_result(lab, partial, registration, root, job_id, claim_id, live,
                                       error_type=type(error).__name__)
        except Exception as retention_error:
            result = None
            error.add_note('Partial evidence persistence failed (' + type(retention_error).__name__ + ').')
        closure = {'stage': 'revision_relay_experiment', 'protocol_ref': _ref(registration),
            'error_type': type(error).__name__, 'error': 'Revision-relay execution incomplete',
            'incomplete_result_id': result['id'] if result else None,
            'execution_report_status': result['payload']['status'] if result else 'unavailable',
            'artifact_directory': str(root / 'execution'), 'live': live}
        for identity in (claim_id, job_id) if outer_started else (claim_id,):
            try:
                lab.store.job(identity, 'failed', closure)
            except Exception as publication_error:
                error.add_note('Failure job publication unavailable (' + type(publication_error).__name__ + ').')
        try:
            lab.store.trace(job_id, {'type': 'revision_relay_failure', 'protocol_ref': _ref(registration),
                'error_type': type(error).__name__, 'execution_report_status': closure['execution_report_status'],
                'scope': 'Retain grid and exact artifacts; operational failure does not exclude a behavior.'})
        except Exception as trace_error:
            error.add_note('Failure trace publication unavailable (' + type(trace_error).__name__ + ').')
        raise


def _read_json(path, maximum):
    if not path.is_file():
        raise ValueError('Missing execution artifact')
    def pairs(entries):
        out = {}
        for key, value in entries:
            if key in out:
                raise ValueError('Duplicate artifact JSON key')
            out[key] = value
        return out
    def constant(_):
        raise ValueError('Finite artifact JSON required')
    return json.loads(_read_bytes(path, maximum).decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)


def audit_revision_relay(lab, result_id, *, version):
    _host_guard(); runner = _runner(); _integer(version, 1, 10 ** 9, 'version')
    obj = lab.store.get(result_id, version)
    if obj['kind'] != 'revision_relay_experiment' or store_fingerprint(obj['payload']) != obj['hash']:
        raise ValueError('Use the exact revision-relay result')
    payload = obj['payload']; checks = []
    complete_execution = False
    partial_trace_consistent = False
    quantitative_available = False
    try:
        _identity(payload)
        if (type(payload) is not dict or set(payload) != _RESULT_KEYS or
                payload.get('instrument_version') != INSTRUMENT_VERSION or
                payload.get('status_promotion') is not False or payload.get('generic_cycle_support') is not False or
                payload.get('scope') != _SCOPE or type(payload.get('research_job_id')) is not str or
                not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', payload['research_job_id']) or
                (payload.get('host_failure_error_type') is not None and (type(payload['host_failure_error_type']) is not str or
                    not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,119}', payload['host_failure_error_type'])))):
            raise ValueError('Invalid host result envelope')
        registration = _registration(lab, payload['protocol_ref']['id'], payload['protocol_ref']['version'])
        if (not _same(payload['protocol_ref'], _ref(registration)) or
                payload.get('study_claim_id') != 'relay-study-' + runner._hash(_ref(registration))[:24] or
                payload.get('agent_mode') != ('scripted_infrastructure'
                    if registration['payload']['backend']['harness'] == 'scripted' else 'live')):
            raise ValueError('Saved exact protocol reference differs')
        root = Path(payload['artifact_root']).resolve(strict=True)
        expected_parent = (lab.settings.runtime / 'runs').resolve(strict=True)
        if root.parent != expected_parent or not re.fullmatch(r'revision-relay-[0-9a-f]{32}', root.name):
            raise ValueError('Execution artifact root is outside this host runtime')
        directory = root / 'execution'
        if (Path(payload['artifact_directory']).resolve(strict=True) != directory.resolve(strict=True) or
                payload.get('host_source_hash') != _LOADED_HOST_SHA256):
            raise ValueError('Host artifact/source binding differs')
        current_pins = _artifact_pins(root, registration['payload']['protocol'])
        if not _same(current_pins, payload['artifact_pins']) or any(value is None for value in current_pins.values()):
            raise ValueError('Registered artifact bytes missing or changed')
        manifest = _read_json(root / 'host-code' / 'manifest.json', 8192)
        expected_manifest = {'instrument_version': INSTRUMENT_VERSION,
            'files': {'revision_relay_workflow.py': _LOADED_HOST_SHA256},
            'timing': 'before_pure_runner_invocation', 'scope': 'source_bytes_not_runtime_execution_attestation'}
        if (not _same(manifest, expected_manifest) or
                _sha(root / 'host-code' / 'revision_relay_workflow.py') != _LOADED_HOST_SHA256):
            raise ValueError('Host source archive mismatch')
        raw = _read_json(directory / 'report.json', runner.MAX_REPORT_BYTES)
        _identity(raw)
        if (not _same(raw, payload['raw_report']) or
                not _same(raw['protocol'], registration['payload']['protocol']) or
                raw.get('report_hash') != payload['canonical_execution_report_hash'] or
                not _same(payload.get('analysis'), raw.get('analysis')) or
                payload.get('registered_protocol_hash') != registration['payload']['frozen_hash'] or
                not _same(payload.get('backend'), registration['payload']['backend']) or
                payload.get('status') != raw.get('status') or
                (raw.get('status') == 'complete' and payload.get('host_failure_error_type') is not None) or
                (raw.get('status') == 'incomplete' and payload.get('host_failure_error_type') != 'RevisionRelayExecutionError') or
                not _same(payload.get('behavior_ref'), registration['payload'].get('behavior_ref'))):
            raise ValueError('Registered report/ref/analysis differs from canonical artifact')
        verification = runner.replay_revision_relay_report(raw, output_dir=directory)
        # Recheck bytes after replay to reject concurrently changed archives.
        if not _same(_artifact_pins(root, registration['payload']['protocol']), current_pins):
            raise ValueError('Execution artifact bytes changed during replay')
        checks.extend(verification['checks'])
        checks += [{'name': 'exact_registered_report_and_protocol', 'passed': True},
                   {'name': 'registered_binary_artifacts_and_host_sources', 'passed': True}]
        passed = verification['passed'] and all(check['passed'] for check in checks)
        complete_execution = verification.get('complete_execution') is True
        partial_trace_consistent = verification.get('partial_trace_consistent') is True
        quantitative_available = verification.get('quantitative_available') is True
    except Exception as error:
        passed = False
        checks.append({'name': 'host_source_report_artifact_binding', 'passed': False, 'error_type': type(error).__name__})
    result = {'experiment_id': result_id, 'result_kind': obj['kind'], 'result_ref': _ref(obj),
        'instrument_version': INSTRUMENT_VERSION, 'passed': bool(passed), 'checks': checks,
        'model_calls': 0, 'report_status': payload.get('status'), 'status_promotion': False,
        'complete_execution': complete_execution, 'partial_trace_consistent': partial_trace_consistent,
        'quantitative_available': quantitative_available,
        'scope': 'Fresh exact local replay/bytes, no provider invocation or consumption, new subjects, historical fidelity or mediation.'}
    _identity(result)
    return lab.store.put('verification', result)


_LOADED_HOST_SHA256 = _sha(__file__)
