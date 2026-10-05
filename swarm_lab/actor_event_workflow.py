"""Registry-bound actor/time observations over frozen selected chat sources.

Actors come from explicit normalized agent-authorship fields. Original room
windows select those chat authors; the subsequent event predicate has no room
filter. Nothing assigns missing rooms, constructs leases, or promotes theories.
"""
from __future__ import annotations

import copy
import hashlib
import re
from collections import Counter
from pathlib import Path

from . import actor_event_queries as queries
from . import indexed_event_workflow as frozen
from .store import clean, fingerprint

WORKFLOW_VERSION = 'selected-actor-event-workflow-v1'
MAX_SOURCE_MESSAGES = 15000
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,255}\Z')


def implementation_hashes():
    return {**frozen.implementation_hashes(), **queries.implementation_hashes(),
            'actor_event_workflow.py': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def _reference(obj):
    return {key: obj[key] for key in ('id', 'version', 'hash')}


def _version(value):
    if value is not None and (type(value) is not int or value < 1):
        raise ValueError('Use an exact positive registry version')


def _identifier(value):
    if type(value) is not str or not _ID.fullmatch(value):
        raise ValueError('Use an exact bounded registry object identifier')


def _source_authors(messages, original_windows):
    if type(messages) is not list or not 1 <= len(messages) <= MAX_SOURCE_MESSAGES:
        raise ValueError('Actor selection requires bounded original selected chat records')
    actors, pins, seen = set(), [], set()
    categories = Counter()
    for message in messages:
        if type(message) is not dict:
            raise ValueError('Selected sources require normalized chat records')
        category = message.get('speaker_type')
        if type(category) is not str or len(category) > 64:
            raise ValueError('Selected source speaker type must be explicit')
        categories[category] += 1
        if category != 'agent':
            continue
        identity = message.get('agent_id')
        if type(identity) is not str or not queries.index._UUID.fullmatch(identity):
            raise ValueError('Agent-authored selected sources require exact normalized agent_id UUIDs')
        if message.get('speaker_id') != identity:
            raise ValueError('Normalized agent_id and speaker_id conflict; no author alias fallback')
        message_id = message.get('id')
        if type(message_id) is not str or not queries.index._UUID.fullmatch(message_id) or message_id in seen:
            raise ValueError('Selected author messages require unique exact source IDs')
        stamp = queries._utc(message.get('created_at'))
        if queries._utc(message.get('timestamp')) != stamp:
            raise ValueError('Normalized author timestamps disagree')
        room_id = message.get('room_id')
        if type(room_id) is not str or not queries.index._UUID.fullmatch(room_id):
            raise ValueError('Original selected chat rooms require exact source UUIDs')
        source = message.get('source')
        allowed = {'file', 'line', 'table', 'record_sha256', 'raw_line_sha256'}
        if (type(source) is not dict or not {'file', 'line', 'table'} <= set(source) or not set(source) <= allowed or
            type(source['file']) is not str or not Path(source['file']).is_absolute() or
            type(source['line']) is not int or source['line'] < 1 or source['table'] != 'chat_messages' or
            any(type(source[k]) is not str or not queries.index._SHA.fullmatch(source[k]) for k in set(source) & {'record_sha256', 'raw_line_sha256'})):
            raise ValueError('Selected author source coordinates must be explicit bounded chat provenance')
        content_hash = message.get('content_hash')
        if type(content_hash) is not str or not queries.index._SHA.fullmatch(content_hash):
            raise ValueError('Selected normalized chat requires its declared compound content hash')
        windows = [w['id'] for w in original_windows if room_id == w['room_id'] and
            queries._utc(w['start']) <= stamp < queries._utc(w['end_exclusive'])]
        if not windows:
            raise ValueError('Selected author message does not belong to an original room/time window')
        seen.add(message_id); actors.add(identity)
        pins.append({'message_id': message_id, 'agent_id': identity, 'speaker_id': identity,
            'speaker_type': 'agent', 'timestamp': stamp, 'room_id': room_id,
            'source': copy.deepcopy(source), 'original_window_ids': sorted(windows),
            'normalized_record_sha256': queries.index._hash(message),
            'declared_compound_content_hash': content_hash})
    if not 1 <= len(actors) <= queries.MAX_ACTORS:
        raise ValueError('Selected windows require at least one and at most 128 explicit agent authors')
    return sorted(actors), sorted(pins, key=lambda p: p['message_id']), {
        'selected_chat_records': len(messages), 'agent_authored_records': len(pins),
        'speaker_type_counts': dict(sorted(categories.items())), 'selected_actor_count': len(actors),
        'actor_selection': 'Exact normalized agent_id from agent-authored selected chats; speaker_id must agree. No roster, name, mention-target or event-based identity inference.',
        'excluded_sources': 'Nonagent chat records remain in frozen selection scope but do not contribute actor IDs.'}


def derive_selected_actor_events(lab, index_ref, selected_audit_ref, *,
                                  max_rows=15000, max_candidate_rows=15000,
                                  action_types=None):
    """Authenticate exact sources and return a reproducible payload, without put."""
    queries.index._bound(max_rows, 'max_rows', queries.MAX_ROWS)
    queries.index._bound(max_candidate_rows, 'max_candidate_rows', queries.MAX_CANDIDATES)
    actions = list(queries.COUNT_ACTIONS) if action_types is None else queries._typed_strings(
        action_types, queries.index._ACTION, 'action_types', 64)
    index_obj = frozen._pinned(lab, index_ref, 'event_source_index')
    selected_obj = frozen._pinned(lab, selected_audit_ref, 'selected_lead_audit')
    windows, messages, refs = frozen.selected_window_sources(
        lab, selected_obj['id'], version=selected_obj['version'])
    if refs.get('selected_audit') != selected_audit_ref:
        raise ValueError('Replayed selection differs from the exact requested reference')
    actors, author_pins, source_scope = _source_authors(messages, windows)
    time_windows = [{key: window[key] for key in ('id', 'start', 'end_exclusive')} for window in windows]
    metadata = index_obj['payload'].get('build_metadata')
    if type(metadata) is not dict or type(metadata.get('artifact')) is not dict:
        raise ValueError('Saved index requires its exact build metadata and artifact')
    artifact = metadata['artifact']
    packet = queries.read_actor_event_index(artifact['path'],
        expected_file_sha256=artifact['file_sha256'], actor_ids=actors,
        windows=time_windows, action_types=actions, max_rows=max_rows,
        max_candidate_rows=max_candidate_rows)
    metadata_hash = queries.index._hash({key: value for key, value in metadata.items() if key != 'artifact'})
    if (packet['index'].get('internal_metadata_sha256') != metadata_hash or
        type(artifact.get('bytes')) is not int or packet['index']['bytes'] != artifact['bytes']):
        raise ValueError('Registered build metadata differs from authenticated index metadata')
    summary = queries.summarize_actor_events(packet)
    policy_counts = Counter(entry['record']['fields']['created_at']['timezone_policy'] for entry in packet['records'])
    payload = {'name': 'Selected-author actor/time event observations',
        'workflow_version': WORKFLOW_VERSION, 'index_ref': _reference(index_obj),
        'selected_audit_ref': _reference(selected_obj), 'source_refs': refs,
        'original_windows': copy.deepcopy(windows), 'source_scope': source_scope,
        'author_source_pins': author_pins, 'query': copy.deepcopy(packet['query']),
        'actor_event_packet': packet, 'actor_event_summary': summary,
        'query_packet_hash': fingerprint(packet),
        'implementation_hashes': implementation_hashes(),
        'source_audit_replay_passed': True, 'model_calls': 0,
        'raw_content_persisted': False, 'status_promotion': False,
        'timestamp_policy_counts': dict(sorted(policy_counts.items())),
        'timestamp_policy_scope': 'Returned event records only; export_naive_assumed_utc is a declared export-clock convention, not verified clock synchronization.',
        'room_policy': 'Original room/time windows select chat authors. Event selection deliberately removes the room predicate; missing event rooms remain unassigned.',
        'scope': 'Pinned selected-source replay and authenticated local actor/time projections. Overlaps reuse records. No fresh raw event reread, room imputation, lease, receipt, exposure or causal attestation; no graph or library status changes.'}
    if clean(payload) != payload:
        raise ValueError('Do not persist credential-shaped query or source metadata')
    if len(queries.index._canonical(payload)) > queries.MAX_PACKET_BYTES:
        raise ValueError('Actor observation workflow payload exceeds byte bound')
    return payload


def audit_selected_actor_events(lab, index_id, selected_audit_id, *, index_version=None,
                                 selected_audit_version=None, max_rows=15000,
                                 max_candidate_rows=15000, action_types=None):
    _identifier(index_id); _identifier(selected_audit_id)
    _version(index_version); _version(selected_audit_version)
    index_obj = lab.store.get(index_id, index_version)
    selected = lab.store.get(selected_audit_id, selected_audit_version)
    payload = derive_selected_actor_events(lab, _reference(index_obj), _reference(selected),
        max_rows=max_rows, max_candidate_rows=max_candidate_rows, action_types=action_types)
    return lab.store.put('actor_event_audit', payload)


def replay_actor_events(lab, audit_id, *, version=None):
    _identifier(audit_id); _version(version)
    saved = lab.store.get(audit_id, version)
    if saved['kind'] != 'actor_event_audit' or fingerprint(saved['payload']) != saved['hash']:
        raise ValueError('Use an unchanged actor event audit')
    payload = saved['payload']
    proof = {'audit_ref': _reference(saved), 'result_kind': 'actor_event_audit',
        'passed': False, 'model_calls': 0, 'index_artifact_reread_attempted': False,
        'index_artifact_reread_completed': False, 'full_event_source_reread': False,
        'scope': 'Fresh local index-byte hash and query plus frozen selected-source replay. Original event object is not reread; no room, lease, receipt or causal attestation.'}
    if payload.get('implementation_hashes') != implementation_hashes():
        proof['reason'] = 'implementation_hash_mismatch'
    else:
        proof['index_artifact_reread_attempted'] = True
        try:
            query = payload['query']
            regenerated = derive_selected_actor_events(lab, payload['index_ref'], payload['selected_audit_ref'],
                max_rows=query['max_rows'], max_candidate_rows=query['max_candidate_rows'],
                action_types=query['action_types'])
        except (ValueError, OSError, TypeError, KeyError, UnicodeError) as exc:
            proof.update(reason='index_or_source_unavailable_or_invalid', error_type=type(exc).__name__)
        else:
            passed = fingerprint(regenerated) == saved['hash']
            proof.update(index_artifact_reread_completed=True, passed=passed,
                         reason='reproduced' if passed else 'source_or_derivation_mismatch')
    return lab.store.put('verification', proof)
