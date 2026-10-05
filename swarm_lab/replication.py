"""Verify held-out seed replications without turning them into broad theories.

This registry describes separate experiments. It neither pools them into a
meta-analysis nor identifies a mediation pathway or historical mechanism.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
from pathlib import Path

from .audit import replay_report
from .experiments import (compare_outcomes, randomize_runs, validate_protocol,
                          _derived_seed)
from .reporting import quantitative_summary
from .store import fingerprint


def object_ref(obj):
    return {key: obj[key] for key in ('id', 'version', 'hash')}


def _checked_object(store, object_id, kind, version=None):
    obj = store.get(object_id, version)
    if obj['kind'] != kind or fingerprint(obj['payload']) != obj['hash']:
        raise ValueError(f'Invalid {kind} object or object hash')
    return obj


def _timestamp(value):
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00'))


def behavior_provenance(store, behavior):
    """Keep exact references; reconstruct legacy refs only as of registration.

    A later dataset import must not silently become the source of an earlier
    behavior. Reconstruction is marked as such, not claimed to be an original
    preregistered reference.
    """
    first = _checked_object(store, behavior['id'], 'behavior', 1)
    p = behavior['payload']
    refs = p.get('source_refs', {})
    first_refs = first['payload'].get('source_refs', {})
    resolved = {}
    reconstructed = []
    for kind, field in (('dataset', 'dataset_id'), ('discovery', 'discovery_id')):
        source_id = p.get(field)
        if not source_id or source_id != first['payload'].get(field):
            raise ValueError('Behavior source identity changed after registration')
        reference = refs.get(kind) or first_refs.get(kind)
        if first_refs.get(kind) and reference != first_refs[kind]:
            raise ValueError('Behavior source reference changed after registration')
        if reference:
            if reference.get('id') != source_id or not reference.get('version'):
                raise ValueError('Invalid behavior source reference')
            source = _checked_object(store, source_id, kind, reference['version'])
            if source['hash'] != reference.get('hash'):
                raise ValueError('Behavior source hash mismatch')
            if _timestamp(source['created']) > _timestamp(first['created']):
                raise ValueError('Behavior source version did not exist at registration')
            if not first_refs.get(kind):
                reconstructed.append(kind)
        else:
            candidates = [v for v in store.history(source_id)
                          if _timestamp(v['created']) <= _timestamp(first['created'])]
            if not candidates:
                raise ValueError('No source version existed when behavior was registered')
            source = _checked_object(store, source_id, kind, candidates[-1]['version'])
            reconstructed.append(kind)
        resolved[kind] = object_ref(source)
    discovery = _checked_object(store, resolved['discovery']['id'], 'discovery',
                                resolved['discovery']['version'])
    declared_dataset = discovery['payload'].get('dataset_id')
    if declared_dataset and declared_dataset != resolved['dataset']['id']:
        raise ValueError('Discovery belongs to a different dataset')
    dataset_ref = discovery['payload'].get('dataset_ref')
    if dataset_ref and any(dataset_ref.get(k) != resolved['dataset'].get(k)
                           for k in ('id', 'version', 'hash')):
        raise ValueError('Discovery and behavior dataset versions differ')
    return {'source_refs': resolved,
            'resolution': 'legacy_registration_time_reconstruction' if reconstructed else 'exact_registered_references',
            'reconstructed_fields': reconstructed,
            'limitation': ('Legacy source references were reconstructed from versions existing at first behavior registration; they were not originally pinned.'
                           if reconstructed else None)}


def _canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False).encode()).hexdigest()


def _validate_result(store, result):
    p = result['payload']
    if result['kind'] != 'experiment' or fingerprint(p) != result['hash']:
        raise ValueError('Replication requires intact primary experiment objects')
    registration = _checked_object(store, p['protocol_id'], 'protocol')
    rp = registration['payload']
    protocol = rp['protocol']
    if fingerprint(protocol) != rp.get('frozen_hash'):
        raise ValueError('Protocol changed after registration')
    validate_protocol(protocol)
    if p.get('registered_hash') != rp['frozen_hash'] or p.get('protocol') != protocol:
        raise ValueError('Experiment does not match its frozen registration')
    if p.get('protocol_hash') != protocol['protocol_hash']:
        raise ValueError('Experiment protocol hash mismatch')
    if rp.get('behavior_id') != p.get('behavior_id'):
        raise ValueError('Experiment and protocol belong to different behaviors')
    if p.get('status') not in ('complete', 'incomplete_infrastructure_failure'):
        raise ValueError('Only completed or explicitly incomplete execution attempts can be linked')
    if rp.get('registered_at') and _timestamp(rp['registered_at']) > _timestamp(p['started_at']):
        raise ValueError('Protocol registration occurred after subject execution began')
    directory = Path(p.get('artifact_directory', ''))
    path = directory / 'report.json'
    if not path.is_file():
        raise ValueError('Canonical execution report is required for replication linkage')
    report = json.loads(path.read_text(encoding='utf-8'))
    for key, value in report.items():
        if key != 'report_hash' and p.get(key) != value:
            raise ValueError('Stored experiment differs from canonical execution report')
    signature = report.get('report_hash')
    if p['status'] == 'complete':
        if not signature or _canonical_hash({k: v for k, v in report.items() if k != 'report_hash'}) != signature:
            raise ValueError('Canonical execution report hash mismatch')
        if p.get('canonical_execution_report_hash') != signature:
            raise ValueError('Stored canonical execution report hash mismatch')
    elif p.get('analysis') is not None or report.get('analysis') is not None:
        raise ValueError('Incomplete infrastructure execution must not contain estimated effects')
    planned = randomize_runs(protocol)
    if p.get('assignments') != planned:
        raise ValueError('Recorded assignments do not match registered randomization')
    seeds = [unit['environment_seed'] for unit in planned]
    if len(seeds) != len(set(seeds)):
        raise ValueError('Repeated environment seed within an experiment')
    runs = p.get('runs', [])
    if len(runs) > len(planned) or (p['status'] == 'complete' and len(runs) != len(planned)):
        raise ValueError('Completed results must include every assigned run without exclusions')
    for run, assignment in zip(runs, planned):
        if any(run.get(k) != v for k, v in assignment.items()):
            raise ValueError('Run identities, order or assigned treatment changed')
    if p['status'] != 'complete' and p.get('incomplete_run'):
        if len(runs) >= len(planned) or any(p['incomplete_run'].get(k) != v
                                           for k, v in planned[len(runs)].items()):
            raise ValueError('Incomplete run does not match the next assigned unit')
    backend = p.get('backend', {})
    if backend.get('registered_spec') != protocol.get('subject_backend'):
        raise ValueError('Executed backend differs from frozen subject backend')
    if backend.get('metadata') != protocol['subject_backend']:
        raise ValueError('Execution backend metadata must match the frozen specification')
    live = p.get('agent_mode') == 'live'
    if live != (backend.get('mode') == 'provided_agent_runner'):
        raise ValueError('Live/scripted evidence labels disagree with subject execution mode')
    if live and p.get('model') != protocol['subject_backend'].get('model'):
        raise ValueError('Executed subject model differs from registered model')
    if not live and backend.get('mode') != 'scripted_offline_smoke_test':
        raise ValueError('Unknown subject execution evidence mode')
    hashes = protocol['execution_code_hashes']
    adapter_hash = rp.get('subject_adapter_hash')
    if live:
        current_adapter = hashlib.sha256(Path(__file__).with_name('harness.py').read_bytes()).hexdigest()
        if not adapter_hash or adapter_hash != current_adapter:
            raise ValueError('Registered subject adapter source hash changed or is missing')
        hashes = {**hashes, 'harness.py': adapter_hash}
    archive = directory / 'execution-code' / 'manifest.json'
    archive_check = 'not_archived'
    if archive.is_file():
        manifest = json.loads(archive.read_text(encoding='utf-8'))
        if manifest.get('timing') != 'before_subject_execution':
            raise ValueError('Execution source archive was not captured before subject execution')
        if _timestamp(manifest['created_at']) > _timestamp(p['started_at']):
            raise ValueError('Execution source archive timestamp is after execution began')
        for name, digest in hashes.items():
            archived_file = archive.parent / name
            if manifest.get('files', {}).get(name) != digest or not archived_file.is_file() or hashlib.sha256(archived_file.read_bytes()).hexdigest() != digest:
                raise ValueError('Archived execution source hash mismatch')
        archive_check = 'verified_pre_execution_archive'
    replay = replay_report(report)
    if runs and not replay['passed']:
        raise ValueError('Recorded actions, subject observations or oracle outcomes failed replay')
    summary = None
    if p['status'] == 'complete':
        active = [int(r['outcomes']['success']) for r in runs if r['arm'] == 'evidence_thought']
        placebo = [int(r['outcomes']['success']) for r in runs if r['arm'] == 'placebo']
        stored_effect = p['analysis']['primary_effect']
        resamples = stored_effect.get('bootstrap_resamples', 2000)
        if not isinstance(resamples, int) or not 100 <= resamples <= 100000:
            raise ValueError('Unsupported resampling count in recorded analysis')
        recomputed = compare_outcomes(active, placebo,
            _derived_seed(protocol['design']['seed'], 'evidence_thought_vs_placebo:success'), resamples)
        recomputed['confirmatory_primary'] = True
        if recomputed != stored_effect:
            raise ValueError('Primary numerical effect does not match executed run outcomes')
        summary = quantitative_summary(p)
    return {'object': result, 'registration': registration, 'protocol': protocol,
            'summary': summary, 'live': live,
            'verification': {'source_hashes': copy.deepcopy(hashes),
                'source_archive': archive_check, 'canonical_report_hash': signature,
                'executed_assignments_checked': len(planned), 'completed_runs_replayed': len(runs),
                'primary_effect_recomputed': summary is not None}}


def validate_replication_pair(store, original_result_id, replication_result_id, theory_id=None):
    """Read-only verification of a declared seed replication and its provenance."""
    if original_result_id == replication_result_id:
        raise ValueError('An experiment cannot replicate itself')
    original = _validate_result(store, _checked_object(store, original_result_id, 'experiment'))
    replication = _validate_result(store, _checked_object(store, replication_result_id, 'experiment'))
    if original['object']['payload']['status'] != 'complete':
        raise ValueError('Replication must refer to a completed original experiment')
    behavior_id = original['object']['payload']['behavior_id']
    if not behavior_id or replication['object']['payload'].get('behavior_id') != behavior_id:
        raise ValueError('Original and replication belong to different behaviors')
    behavior = _checked_object(store, behavior_id, 'behavior')
    provenance = behavior_provenance(store, behavior)
    op, rp = original['protocol'], replication['protocol']
    if replication['registration']['payload'].get('replicates_protocol_id') != original['registration']['id'] or rp.get('replicates_protocol_hash') != op['protocol_hash']:
        raise ValueError('Replication does not explicitly reference the original frozen protocol')
    if original['registration']['id'] == replication['registration']['id']:
        raise ValueError('Replication needs a separately registered protocol')
    if rp.get('phase') != 'held_out_environment_seed_replication':
        raise ValueError('Replication phase was not declared before execution')
    # Only sample count, seed namespace and registration fields may differ in
    # this kind of replication. Other designs need their own comparison contract.
    def invariant(protocol):
        body = copy.deepcopy(protocol)
        for key in ('created_at', 'protocol_hash', 'phase', 'replicates_protocol_hash'):
            body.pop(key, None)
        body['design'].pop('seed', None)
        body['design'].pop('trials_per_arm', None)
        return body
    if invariant(op) != invariant(rp):
        raise ValueError('Environment, wording, estimand, measurement, code or backend differs; not a held-out seed replication')
    if original['live'] != replication['live']:
        raise ValueError('Live and scripted subjects cannot be treated as comparable replication evidence')
    if original['verification']['source_hashes'] != replication['verification']['source_hashes']:
        raise ValueError('Subject/source code differs between experiments')
    old_seeds = {u['environment_seed'] for u in original['object']['payload']['assignments']}
    new_seeds = {u['environment_seed'] for u in replication['object']['payload']['assignments']}
    if op['design']['seed'] == rp['design']['seed'] or old_seeds & new_seeds:
        raise ValueError('Replication reuses assigned environment seeds')
    theory = None
    if theory_id:
        theory = _checked_object(store, theory_id, 'theory')
        tp = theory['payload']
        if behavior_id not in tp.get('behavior_ids', []) or original_result_id not in tp.get('experiment_ids', []):
            raise ValueError('Theory is not linked to this behavior and original experiment')
        for kind in ('dataset', 'discovery'):
            if tp.get('source_refs', {}).get(kind) and tp['source_refs'][kind] != provenance['source_refs'][kind]:
                raise ValueError('Theory and behavior source provenance differ')
    complete = replication['object']['payload']['status'] == 'complete'
    status = ('completed_live_seed_replication' if original['live'] else 'completed_scripted_infrastructure_replication') if complete else 'incomplete_infrastructure_attempt'
    warnings = [
        'Separate experiments are retained; no pooled effect or implicit meta-analysis is computed.',
        'Evidence is bounded to this synthetic task distribution, registered text, subject model and harness.',
        'Disjoint environment seeds verify state separation; they do not seed hosted-model sampling or prove independence of provider sessions.',
        'Backend equality uses recorded settings and aliases; hosted model version drift and time effects remain possible.',
        'A nominal directional result is not an established theory, identified mediation pathway, historical causal mechanism, or evidence of transfer.',
    ]
    if provenance['limitation']:
        warnings.append(provenance['limitation'])
    if any(v['verification']['source_archive'] == 'not_archived' for v in (original, replication)):
        warnings.append('At least one experiment has no pre-execution source archive. Frozen hashes match current code and recorded-action replay passed, but historical source capture is unavailable.')
    return {'status': status, 'behavior': behavior, 'theory': theory,
            'original': original, 'replication': replication, 'provenance': provenance,
            'independence': {'original_assigned_runs': len(old_seeds),
                'replication_assigned_runs': len(new_seeds), 'environment_seed_overlap': 0,
                'randomization_unit': 'whole_swarm_run',
                'unit_id_namespace': 'experiment_id plus run_id; local run labels may repeat across separate experiments'},
            'limitations': warnings}
