"""Source-bound retrospective literal wait/action proximity observations.

The host authenticates the actor index and frozen chat selection before the
pure instrument runs. Recorded coordinate proximity is not semantic ground
truth, physical waiting, synchronized clocks, or a causal finding.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from . import actor_event_workflow as actors
from . import wait_marker_alignment as instrument
from .store import clean, fingerprint

WORKFLOW_VERSION = 'selected-wait-marker-workflow-v1'


def implementation_hashes():
    return {**actors.implementation_hashes(),
            'wait_marker_alignment.py': hashlib.sha256(Path(instrument.__file__).read_bytes()).hexdigest(),
            'wait_marker_workflow.py': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def _ref(obj):
    return {key: obj[key] for key in ('id', 'version', 'hash')}


def derive_wait_marker_alignment(lab, actor_audit_id, *, version=None,
                                 max_controls=32, max_work=1_000_000):
    """Freshly authenticate both sources; derive without a registry write."""
    actors._identifier(actor_audit_id)
    actors._version(version)
    instrument.queries.index._bound(max_controls, 'max_controls', instrument.MAX_CONTROLS)
    instrument.queries.index._bound(max_work, 'max_work', instrument.MAX_WORK)
    source = lab.store.get(actor_audit_id, version)
    if source['kind'] != 'actor_event_audit' or fingerprint(source['payload']) != source['hash']:
        raise ValueError('Use an unchanged exact actor event audit')
    saved = source['payload']
    if saved.get('implementation_hashes') != actors.implementation_hashes():
        raise ValueError('Actor observation implementation pins changed')
    query = saved['query']
    reproduced = actors.derive_selected_actor_events(lab, saved['index_ref'], saved['selected_audit_ref'],
        max_rows=query['max_rows'], max_candidate_rows=query['max_candidate_rows'],
        action_types=query['action_types'])
    if fingerprint(reproduced) != source['hash']:
        raise ValueError('Actor observation does not reproduce from its frozen sources')
    selected_ref = saved['selected_audit_ref']
    _, messages, refs = actors.frozen.selected_window_sources(
        lab, selected_ref['id'], version=selected_ref['version'])
    if refs != saved['source_refs']:
        raise ValueError('Selected chat source pins differ from the authenticated actor observation')
    refs = {**refs, 'index': saved['index_ref'], 'actor_audit': _ref(source)}
    alignment = instrument.analyze_wait_marker_alignment(messages, reproduced['actor_event_packet'],
        max_controls=max_controls, max_work=max_work, source_refs=refs)
    payload = {'name': 'Retrospective literal wait/action proximity',
        'workflow_version': WORKFLOW_VERSION, 'actor_audit_ref': _ref(source), 'source_refs': refs,
        'configuration': {'max_controls': max_controls, 'max_work': max_work},
        'implementation_hashes': implementation_hashes(), 'alignment': alignment,
        'source_audit_replay_passed': True, 'index_artifact_reread_completed': True,
        'full_event_source_reread': False, 'model_calls': 0, 'raw_content_persisted': False,
        'status_promotion': False,
        'chat_clock_policy': 'Raw chat clock policies are unavailable in the frozen normalized source; no host clock declaration is supplied.',
        'scope': 'Retrospective selected-source literal tokens and nearby same-actor recorded UTC coordinates. '
                 'Exact local index bytes and chat selection are freshly authenticated. No semantic detector '
                 'accuracy, room assignment, inactivity, lease, exposure, clock synchronization, novelty or causal attestation.'}
    if clean(payload) != payload:
        raise ValueError('Do not persist credential-shaped observation metadata')
    if len(instrument.queries.index._canonical(payload)) > instrument.MAX_OUTPUT_BYTES:
        raise ValueError('Wait-marker workflow exceeds its output byte bound')
    return payload


def audit_wait_markers(lab, actor_audit_id, **kwargs):
    return lab.store.put('wait_marker_alignment_audit',
                         derive_wait_marker_alignment(lab, actor_audit_id, **kwargs))


def replay_wait_markers(lab, alignment_id, *, version=None):
    actors._identifier(alignment_id)
    actors._version(version)
    source = lab.store.get(alignment_id, version)
    if source['kind'] != 'wait_marker_alignment_audit' or fingerprint(source['payload']) != source['hash']:
        raise ValueError('Use an unchanged exact wait-marker alignment audit')
    payload = source['payload']
    proof = {'alignment_ref': _ref(source), 'result_kind': 'wait_marker_alignment_audit',
        'passed': False, 'source_replay_attempted': False, 'source_replay_completed': False,
        'index_artifact_reread_completed': False, 'full_event_source_reread': False, 'model_calls': 0,
        'scope': 'Fresh local index-byte authentication, actor observation and selected chat replay, '
                 'then deterministic literal-token proximity regeneration. No semantic or causal attestation.'}
    if payload.get('implementation_hashes') != implementation_hashes():
        proof['reason'] = 'implementation_hash_mismatch'
    else:
        proof['source_replay_attempted'] = True
        try:
            pinned = actors.frozen._pinned(lab, payload['actor_audit_ref'], 'actor_event_audit')
            regenerated = derive_wait_marker_alignment(lab, pinned['id'], version=pinned['version'],
                                                       **payload['configuration'])
        except (ValueError, OSError, TypeError, KeyError, UnicodeError) as exc:
            proof.update(reason='index_or_source_unavailable_or_invalid', error_type=type(exc).__name__)
        else:
            passed = fingerprint(regenerated) == source['hash']
            proof.update(passed=passed, source_replay_completed=True,
                         index_artifact_reread_completed=True,
                         reason='reproduced' if passed else 'source_or_derivation_mismatch')
    return lab.store.put('verification', proof)
