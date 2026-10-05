"""Registry-bound event projections for already selected historical windows.

The local index is authenticated before querying. Replay reopens that artifact
and reproduces the selected chat audit; it does not reread the complete remote
event object or attest message delivery, tool success, or causal influence.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path

from .store import clean, fingerprint


WORKFLOW_VERSION = 'indexed-event-workflow-v1'
ACTION_TYPES = ['AGENT_TALK', 'WAIT', 'PAUSE', 'START_USING_COMPUTER', 'STOP_USING_COMPUTER']
IMPLEMENTATIONS = ('event_source_index.py', 'indexed_event_audit.py', 'indexed_event_workflow.py',
                   'source_scanner.py', 'temporal_workflow.py', 'selected_lead_sensitivity.py',
                   'dataset.py', 'discovery.py', 'network.py', 'graph_discovery.py',
                   'mention_sensitivity.py', 'name_eligibility_sensitivity.py',
                   'mention_graph_sensitivity.py')
_SHA = re.compile(r'[0-9a-f]{64}\Z')


def implementation_hashes():
    return {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in IMPLEMENTATIONS}


def _reference(obj):
    return {key: obj[key] for key in ('id', 'version', 'hash')}


def _version(version):
    if version is not None and (type(version) is not int or version < 1):
        raise ValueError('Use an exact positive registry version')


def _pinned(lab, ref, kind):
    if (type(ref) is not dict or set(ref) != {'id', 'version', 'hash'}
            or type(ref['id']) is not str or not ref['id']
            or type(ref['version']) is not int or ref['version'] < 1
            or type(ref['hash']) is not str or not _SHA.fullmatch(ref['hash'])):
        raise ValueError('Use an exact typed registry source reference')
    obj = lab.store.get(ref['id'], ref['version'])
    if obj['kind'] != kind or obj['hash'] != ref['hash'] or fingerprint(obj['payload']) != ref['hash']:
        raise ValueError('Pinned registry source mismatch')
    return obj


def selected_window_sources(lab, selected_audit_id, *, version=None):
    """Replay the frozen selection before choosing any messages or events."""
    from .temporal_workflow import selected_audit_sources
    audit, dataset, discovery = selected_audit_sources(lab, selected_audit_id, version=version)
    windows = [{key: row['original_window'][key]
                for key in ('id', 'room_id', 'start', 'end_exclusive')}
               for _, row in sorted(audit['payload']['window_measurements'].items())]
    messages = [row for row in dataset['payload']['messages']
                if any(row.get('room_id') == window['room_id']
                       and window['start'] <= row.get('created_at', row.get('timestamp', '')) < window['end_exclusive']
                       for window in windows)]
    refs = {'dataset': _reference(dataset), 'discovery': _reference(discovery),
            'selected_audit': _reference(audit)}
    return windows, messages, refs


def build_event_source_index(lab, source_path, *, max_rows=400000,
                             max_compressed_bytes=340 * 1024**2,
                             max_expanded_bytes=2 * 1024**3, max_row_bytes=2 * 1024**2,
                             max_seconds=1800, source_metadata=None, on_progress=None):
    """Create an exclusive artifact and persist only its bounded build metadata."""
    from .event_source_index import build_event_index
    if on_progress is not None and not callable(on_progress):
        raise ValueError('Progress reporting requires a local callable')
    directory = lab.store.path.parent / 'source-indexes'
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / ('events-' + uuid.uuid4().hex + '.sqlite3')
    # Validation and exclusive creation belong to the builder. The destination
    # is selected by the host, never accepted from an API caller.
    metadata = build_event_index(source_path, destination, max_rows=max_rows,
                                 max_compressed_bytes=max_compressed_bytes,
                                 max_expanded_bytes=max_expanded_bytes,
                                 max_row_bytes=max_row_bytes, max_seconds=max_seconds,
                                 source_metadata=source_metadata, on_progress=on_progress)
    payload = {'name': 'Bounded event source index', 'workflow_version': WORKFLOW_VERSION,
               'build_metadata': metadata, 'model_calls': 0,
               'raw_content_persisted': False,
               'scope': 'Projected typed event fields and hashes. Build coverage and object-byte authentication '
                        'are separate from event semantics, delivery and influence.'}
    if clean(payload) != payload:
        raise ValueError('Index metadata contains credential-shaped values')
    return lab.store.put('event_source_index', payload)


def derive_indexed_event_audit(lab, index_ref, selected_audit_id, *, version=None,
                              max_query_rows=15000):
    """Authenticate a saved index and original sources, then derive a new audit."""
    from .event_source_index import read_event_index
    from .indexed_event_audit import audit_indexed_event_matches
    _version(version)
    if type(max_query_rows) is not int or not 1 <= max_query_rows <= 15000:
        raise ValueError('Query rows require a bounded positive integer')
    index = _pinned(lab, index_ref, 'event_source_index')
    metadata = index['payload'].get('build_metadata', {})
    windows, messages, refs = selected_window_sources(lab, selected_audit_id, version=version)
    artifact = metadata['artifact']
    packet = read_event_index(artifact['path'],
                              expected_file_sha256=artifact['file_sha256'],
                              message_ids=[message['id'] for message in messages],
                              windows=windows, action_types=ACTION_TYPES, max_rows=max_query_rows)
    metadata_hash = hashlib.sha256(json.dumps(
        {key: value for key, value in metadata.items() if key != 'artifact'},
        sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()
    if (packet['index'].get('internal_metadata_sha256') != metadata_hash
            or packet['index']['bytes'] != artifact.get('bytes')):
        raise ValueError('Registered build metadata differs from authenticated index metadata')
    audit = audit_indexed_event_matches(packet, messages, windows=windows, source_refs=refs)
    result = {'name': 'Selected-window indexed event corroboration',
              'workflow_version': WORKFLOW_VERSION, 'index_ref': _reference(index),
              'source_refs': refs, 'selected_audit_ref': refs['selected_audit'],
              'query': {'message_ids': sorted(message['id'] for message in messages),
                        'windows': windows, 'action_types': ACTION_TYPES,
                        'max_rows': max_query_rows},
              'query_packet_hash': fingerprint(packet),
              'implementation_hashes': implementation_hashes(),
              'indexed_event_audit': audit, 'source_audit_replay_passed': True,
              'model_calls': 0, 'raw_content_persisted': False,
              'scope': 'Authenticated local event projection and reproduced frozen normalized chat sources. '
                       'Raw event bytes are not reread during this query. No receipt, exposure, outcome, '
                       'causal influence, graph merge, or behavior status promotion.'}
    if clean(result) != result:
        raise ValueError('Do not persist credential-shaped query metadata')
    return result


def audit_indexed_events(lab, index_id, selected_audit_id, *, index_version=None,
                         selected_audit_version=None, max_query_rows=15000):
    _version(index_version)
    _version(selected_audit_version)
    index = lab.store.get(index_id, index_version)
    return lab.store.put('indexed_event_audit', derive_indexed_event_audit(
        lab, _reference(index), selected_audit_id, version=selected_audit_version,
        max_query_rows=max_query_rows))


def replay_indexed_events(lab, audit_id, *, version=None):
    _version(version)
    saved = lab.store.get(audit_id, version)
    if saved['kind'] != 'indexed_event_audit' or fingerprint(saved['payload']) != saved['hash']:
        raise ValueError('Use an unchanged indexed event audit')
    payload = saved['payload']
    proof = {'audit_ref': _reference(saved), 'result_kind': 'indexed_event_audit',
             'passed': False, 'model_calls': 0, 'index_artifact_reread_attempted': False,
             'index_artifact_reread_completed': False, 'full_event_source_reread': False,
             'scope': 'Fresh local index-byte hash, query and frozen selected-source replay. '
                      'No fresh original event-object reread or delivery/causal attestation.'}
    if payload.get('implementation_hashes') != implementation_hashes():
        proof['reason'] = 'implementation_hash_mismatch'
    else:
        proof['index_artifact_reread_attempted'] = True
        try:
            selected = payload['selected_audit_ref']
            _pinned(lab, selected, 'selected_lead_audit')
            derived = derive_indexed_event_audit(lab, payload['index_ref'], selected['id'],
                                                 version=selected['version'],
                                                 max_query_rows=payload['query']['max_rows'])
        except (ValueError, OSError, TypeError, KeyError, UnicodeError) as exc:
            proof.update(reason='index_or_source_unavailable_or_invalid', error_type=type(exc).__name__)
        else:
            passed = fingerprint(derived) == saved['hash']
            proof.update(index_artifact_reread_completed=True, passed=passed,
                         reason='reproduced' if passed else 'source_or_derivation_mismatch')
    return lab.store.put('verification', proof)
