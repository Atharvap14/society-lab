"""Bounded declarative swarm telemetry with atomic, source-scoped append intake.

Source events are producer reports. Reference checks authenticate local field
consistency, not tool execution, message consumption, intent, or causal effects.
"""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from .store import Store, clean, fingerprint, now

VERSION = 'societylab.events.v1'
MAX_BYTES = 1048576
MAX_EVENTS = 2000
MAX_DEPTH = 12
DATA_FIELDS = {
    'agent.registered': ({'name'}, {'roles'}),
    'task.created': ({'title'}, {'description'}),
    'task.assigned': ({'assignee_ids'}, set()),
    'task.completed': ({'success'}, {'summary'}),
    'message.sent': ({'content'}, {'channel_id', 'channel_name', 'visibility', 'reply_to_message_id'}),
    'reasoning.recorded': ({'content'}, set()),
    'tool.called': ({'call_id', 'tool_name'}, {'arguments'}),
    'tool.returned': ({'call_id', 'success'}, {'output'}),
    'artifact.updated': ({'artifact_id', 'revision_id'}, {'change_summary', 'content_sha256'}),
    'intervention.delivered': ({'intervention_id', 'content'}, {'policy_id'}),
}
LIMITATIONS = [
    'Telemetry is producer-declared; intake does not independently verify the source.',
    'A sent or addressed message does not establish reading, exposure, agreement or influence.',
    'Tool and task success are explicit producer reports, not independent execution oracles.',
    'Input order is capture/append order. Producer timestamps can be skewed; they are not a shared causal clock.',
    'Missing references are unknown in this bounded run, not evidence of global absence.',
    'The dataset bridge contains only message.sent posts; it invents no chat, tool, or task actions.',
    'Visibility is an explicit producer declaration. Room recipients are addressed peers, not complete membership; broadcast does not mean everyone read the post.',
    'reasoning.recorded is an existing exposed rationale or private log supplied by its actor. Intake never obtains, reconstructs or invents hidden reasoning; it creates no communication edge.',
]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result: raise ValueError('Duplicate observability JSON key')
        result[key] = value
    return result


def _bad_constant(_):
    raise ValueError('Observability batches require finite JSON')


def _bounded(value, depth=0):
    if depth > MAX_DEPTH: raise ValueError('Observability JSON nesting exceeds 12 levels')
    if value is None or type(value) is bool: return
    if type(value) is str:
        if len(value) > 16000: raise ValueError('Observability text exceeds 16000 characters')
        value.encode('utf-8'); return
    if type(value) in (int, float):
        if not -9007199254740991 <= value <= 9007199254740991:
            raise ValueError('Observability numbers must be finite, safe JSON numbers')
        return
    if type(value) is list:
        if len(value) > MAX_EVENTS: raise ValueError('Observability list exceeds 2000 items')
        for item in value: _bounded(item, depth + 1)
        return
    if type(value) is dict:
        if len(value) > 256: raise ValueError('Observability object exceeds 256 fields')
        for key, item in value.items():
            if type(key) is not str or len(key) > 200: raise ValueError('Invalid observability field name')
            key.encode('utf-8'); _bounded(item, depth + 1)
        return
    raise ValueError('Observability data must be ordinary JSON')


def _object(value, required, optional=()):
    if type(value) is not dict or not set(required) <= set(value) or not set(value) <= set(required) | set(optional):
        raise ValueError('Missing or unsupported observability fields')


def _text(value, maximum=1000):
    if type(value) is not str or not value.strip() or len(value) > maximum:
        raise ValueError('Use bounded, nonblank observability text')


def _id(value):
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}', value) or clean(value) != value:
        raise ValueError('Use a short stable ID without credentials or spaces')


def _ids(values, minimum=0, maximum=64):
    if type(values) is not list or not minimum <= len(values) <= maximum:
        raise ValueError('Invalid observability ID list')
    for value in values: _id(value)
    if len(set(values)) != len(values): raise ValueError('Duplicate observability reference ID')


def _time(value):
    if type(value) is not str or len(value) > 40 or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|[+-]\d\d:\d\d)', value):
        raise ValueError('occurred_at requires an ISO timestamp with explicit timezone')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.utcoffset() is None: raise ValueError('Unknown producer timezone')
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError) as error:
        raise ValueError('Invalid observability timestamp') from error


def validate_batch(batch):
    _bounded(batch)
    if len(canonical(batch)) > MAX_BYTES: raise ValueError('Observability batch exceeds 1 MiB')
    _object(batch, {'schema_version', 'source', 'run', 'events'})
    if batch['schema_version'] != VERSION: raise ValueError('Unsupported observability schema version')
    _object(batch['source'], {'id', 'name', 'kind'}, {'harness'})
    _id(batch['source']['id']); _text(batch['source']['name'], 200)
    if batch['source']['kind'] not in ('authored_example', 'telemetry'): raise ValueError('Declare authored_example or telemetry source kind')
    if 'harness' in batch['source']: _text(batch['source']['harness'], 100)
    _object(batch['run'], {'id'}, {'name'})
    _id(batch['run']['id'])
    if 'name' in batch['run']: _text(batch['run']['name'], 200)
    events = batch['events']
    if type(events) is not list or not 1 <= len(events) <= MAX_EVENTS: raise ValueError('Send 1–2000 observability events')
    seen = set()
    for event in events:
        _object(event, {'id', 'occurred_at', 'kind', 'data'}, {'actor_id', 'task_id', 'parent_task_id', 'recipient_ids'})
        _id(event['id']); _time(event['occurred_at'])
        if event['id'] in seen: raise ValueError('Duplicate event ID in observability batch')
        seen.add(event['id'])
        kind = event['kind']
        if type(kind) is not str or kind not in DATA_FIELDS: raise ValueError('Unsupported observability event kind')
        for name in ('actor_id', 'task_id', 'parent_task_id'):
            if name in event: _id(event[name])
        if kind.startswith('task.') and 'task_id' not in event: raise ValueError('Task events require task_id')
        if not kind.startswith('task.') and 'actor_id' not in event: raise ValueError('This event requires actor_id')
        if 'parent_task_id' in event and (kind != 'task.created' or event['parent_task_id'] == event.get('task_id')):
            raise ValueError('Only task.created may declare a distinct parent_task_id')
        if kind in ('message.sent', 'intervention.delivered', 'reasoning.recorded'):
            if 'recipient_ids' not in event: raise ValueError('Message/intervention addressing must be explicit')
            _ids(event['recipient_ids'], minimum=1 if kind == 'intervention.delivered' else 0)
            if kind == 'reasoning.recorded' and event['recipient_ids']:
                raise ValueError('Recorded reasoning is scoped to its own actor and must have no recipients')
        elif 'recipient_ids' in event: raise ValueError('Recipients belong only to message/intervention/recorded-reasoning events')
        required, optional = DATA_FIELDS[kind]
        _object(event['data'], required, optional)
        data = event['data']
        for name in ('name', 'title', 'description', 'summary', 'content', 'tool_name', 'change_summary', 'channel_name'):
            if name in data: _text(data[name], 16000 if name == 'content' else 1000)
        for name in ('call_id', 'artifact_id', 'revision_id', 'intervention_id', 'policy_id', 'channel_id', 'reply_to_message_id'):
            if name in data: _id(data[name])
        if 'success' in data and type(data['success']) is not bool: raise ValueError('success must be an explicit Boolean')
        if 'assignee_ids' in data: _ids(data['assignee_ids'], minimum=1)
        if 'roles' in data:
            if type(data['roles']) is not list or len(data['roles']) > 32: raise ValueError('Agent roles must be a bounded text list')
            for role in data['roles']: _text(role, 100)
            if len(set(data['roles'])) != len(data['roles']): raise ValueError('Duplicate role label')
        if 'content_sha256' in data and (type(data['content_sha256']) is not str or not re.fullmatch(r'[0-9a-f]{64}', data['content_sha256'])):
            raise ValueError('Artifact content_sha256 must be SHA-256')
        for name in ('arguments', 'output'):
            if name in data and len(canonical(data[name])) > 65536: raise ValueError('Tool arguments/output exceed 64 KiB')
        if kind == 'message.sent' and 'visibility' in data:
            visibility = data['visibility']
            if type(visibility) is not str or visibility not in ('private', 'direct', 'room', 'broadcast', 'unknown'):
                raise ValueError('Use an explicit supported message visibility')
            recipients = event['recipient_ids']
            if visibility == 'private' and (recipients or 'channel_id' in data or 'channel_name' in data):
                raise ValueError('A private self record cannot address peers or a channel')
            if visibility == 'direct' and (not recipients or event['actor_id'] in recipients):
                raise ValueError('Direct messages require explicit peer recipients distinct from the actor')
            if visibility == 'room' and not ('channel_id' in data or 'channel_name' in data):
                raise ValueError('Room posts require a declared channel identity or name')
            if visibility == 'broadcast' and recipients:
                raise ValueError('Broadcast scope cannot be an enumerated direct-recipient list')
    return copy.deepcopy(batch)


def parse_batch(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES: raise ValueError('Send an observability JSON batch under 1 MiB')
    try:
        parsed = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_bad_constant)
        return validate_batch(parsed)
    except (RecursionError, UnicodeError, OverflowError) as error:
        raise ValueError('Invalid bounded observability JSON') from error


def _ref(record):
    return {key: record[key] for key in ('id', 'version', 'hash')}


def _links(events):
    indexes = {'agent': {}, 'task': {}, 'message': {}, 'call': {}}
    for event in events:
        kind = event['kind']
        pair = ('agent', event.get('actor_id')) if kind == 'agent.registered' else (
            ('task', event.get('task_id')) if kind == 'task.created' else (
            ('message', event['id']) if kind == 'message.sent' else (
            ('call', event['data']['call_id']) if kind == 'tool.called' else (None, None))))
        if pair[0]: indexes[pair[0]].setdefault(pair[1], []).append(event)
    counts = {key: 0 for key in ('matching_declared_reference', 'unknown_in_captured_run', 'ambiguous_reference', 'actor_conflict')}
    checks = []
    for event in events:
        refs = []
        if event.get('actor_id'): refs.append(('actor', 'agent', event['actor_id']))
        if event.get('task_id') and event['kind'] != 'task.created': refs.append(('task', 'task', event['task_id']))
        if event.get('parent_task_id'): refs.append(('parent_task', 'task', event['parent_task_id']))
        for recipient in event.get('recipient_ids', []): refs.append(('addressed_recipient', 'agent', recipient))
        for assignee in event['data'].get('assignee_ids', []): refs.append(('task_assignee', 'agent', assignee))
        if event['kind'] == 'message.sent' and event['data'].get('reply_to_message_id'):
            refs.append(('reply_reference', 'message', event['data']['reply_to_message_id']))
        if event['kind'] == 'tool.returned': refs.append(('tool_call_reference', 'call', event['data']['call_id']))
        for relation, table, identity in refs:
            matches = indexes[table].get(identity, [])
            status = 'unknown_in_captured_run' if not matches else ('ambiguous_reference' if len(matches) > 1 else 'matching_declared_reference')
            if relation == 'tool_call_reference' and len(matches) == 1 and matches[0].get('actor_id') != event.get('actor_id'):
                status = 'actor_conflict'
            counts[status] += 1
            if len(checks) < 256:
                checks.append({'event_id': event['id'], 'relation': relation, 'reference_id': identity,
                               'status': status, 'matching_event_ids': [item['id'] for item in matches[:8]]})
    return {'counts': counts, 'checks': checks, 'checks_truncated': sum(counts.values()) > len(checks),
            'scope': 'Explicit field relationships only; not receipt, execution or causal verification'}


def _run_payload(batch, previous, input_sha, batch_sha, redacted):
    events = batch['events']
    times = [_time(event['occurred_at']) for event in events]
    return {**batch, 'previous_ref': previous, 'source_batch_sha256': batch_sha,
        'input_bytes_sha256': input_sha, 'stored_batch_sha256': digest(batch),
        'provenance': {'source_kind': batch['source']['kind'], 'origin': 'observability_telemetry',
            'producer_declared': True, 'independently_verified': False, 'redaction_applied': redacted},
        'reference_checks': _links(events), 'clock': {'policy': 'producer_declared_explicit_timezone',
            'capture_order_preserved': True, 'adjacent_timestamp_reversals': sum(a > b for a, b in zip(times, times[1:])),
            'shared_causal_clock_verified': False}, 'limitations': LIMITATIONS,
        'bounds': {'maximum_events': MAX_EVENTS, 'maximum_accumulated_batch_bytes': MAX_BYTES}}


def _dataset_payload(run_record):
    run = run_record['payload']
    names = {}
    for event in run['events']:
        if event['kind'] == 'agent.registered': names.setdefault(event['actor_id'], []).append(event['data']['name'])
    messages = []
    for index, event in enumerate(run['events']):
        if event['kind'] != 'message.sent': continue
        timestamp = _time(event['occurred_at']).isoformat(timespec='microseconds').replace('+00:00', 'Z')
        room = event['data'].get('channel_id')  # Unknown stays unknown; no invented shared room.
        stable = {'speaker': event['actor_id'], 'timestamp': timestamp, 'content': event['data']['content'], 'room_id': room}
        content_hash = hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()
        labels = names.get(event['actor_id'], [])
        messages.append({'id': event['id'], 'agent_id': event['actor_id'], 'speaker_id': event['actor_id'],
            'speaker_type': 'agent', 'agent_name': labels[0] if len(set(labels)) == 1 else event['actor_id'],
            'room_id': room, 'created_at': timestamp, 'timestamp': timestamp,
            'content': event['data']['content'], 'content_hash': content_hash,
            'recipient_ids': copy.deepcopy(event['recipient_ids']), 'reply_to': event['data'].get('reply_to_message_id'),
            'source': {'table': 'observability_events', 'line': index + 1, 'event_id': event['id'], 'run_ref': _ref(run_record)}})
        for name in ('visibility', 'channel_name'):
            if name in event['data']: messages[-1][name] = copy.deepcopy(event['data'][name])
    if not messages: return None
    return {'schema_version': '1.0', 'name': run['run'].get('name', run['run']['id']) + ' — reported messages',
        'source': 'observability:' + run_record['id'], 'source_refs': {'run_ref': _ref(run_record)},
        'scope': {'selection': 'all message.sent events in exact captured run version', 'limit': MAX_EVENTS, 'room': None},
        'messages': messages, 'agents': [{'id': identity, 'name': labels[0] if len(set(labels)) == 1 else identity} for identity, labels in names.items()],
        'events': [], 'goals': [], 'diagnostics': {'chat': {'retained_rows': len(messages), 'truncated': False}},
        'fingerprint': digest([{'id': message['id'], 'hash': message['content_hash']} for message in messages]),
        'provenance': {**run['provenance'], 'origin': 'observability_message_bridge', 'run_ref': _ref(run_record)},
        'limitations': LIMITATIONS + ['Unknown channel IDs remain null; no shared room or recipient reading is inferred.']}


def _latest(connection, identity):
    row = connection.execute('SELECT * FROM objects WHERE id=? ORDER BY version DESC LIMIT 1', (identity,)).fetchone()
    return Store._decode(row) if row else None


def _prospective(connection, kind, identity, payload):
    prior = _latest(connection, identity)
    if prior and prior['kind'] != kind: raise ValueError('Observability object identity has a conflicting kind')
    payload = clean(payload)
    return {'id': identity, 'kind': kind, 'version': prior['version'] + 1 if prior else 1,
            'created': now(), 'hash': fingerprint(payload), 'payload': payload}


def _insert(connection, record):
    connection.execute('INSERT INTO objects VALUES(?,?,?,?,?,?)',
        (record['id'], record['version'], record['kind'], record['created'],
         json.dumps(record['payload'], ensure_ascii=False, allow_nan=False), record['hash']))


def _bound_record(connection, reference, kind):
    row = connection.execute('SELECT * FROM objects WHERE id=? AND version=?', (reference['id'], reference['version'])).fetchone()
    if row is None: raise ValueError('Saved observability receipt artifact is missing')
    record = Store._decode(row)
    if record['kind'] != kind or canonical(_ref(record)) != canonical(reference): raise ValueError('Saved observability receipt reference changed')
    return record


def _connect_atomic(lab, raw):
    original = parse_batch(raw)
    batch_sha = digest(original)
    submitted = clean(original)
    validate_batch(submitted)
    key = digest({'source_id': submitted['source']['id'], 'run_id': submitted['run']['id']})[:24]
    run_id, dataset_id, brief_id = 'observability_run-' + key, 'dataset-observability-' + key, 'observation_brief-' + key
    from .proactive_brief import build_brief
    with lab.store.connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        connection.execute('CREATE TABLE IF NOT EXISTS observability_batches(run_id TEXT,batch_hash TEXT,refs TEXT,PRIMARY KEY(run_id,batch_hash))')
        previous = _latest(connection, run_id)
        receipt = connection.execute('SELECT refs FROM observability_batches WHERE run_id=? AND batch_hash=?', (run_id, batch_sha)).fetchone()
        if receipt:
            refs = json.loads(receipt['refs'])
            saved_run = _bound_record(connection, refs['run_ref'], 'observability_run')
            saved_brief = _bound_record(connection, refs['brief_ref'], 'observation_brief')
            saved_dataset = _bound_record(connection, refs['dataset_ref'], 'dataset') if refs['dataset_ref'] is not None else None
            expected_sources = {'run_ref': _ref(saved_run)} | ({'dataset_ref': _ref(saved_dataset)} if saved_dataset else {})
            if canonical(saved_brief['payload'].get('source_refs')) != canonical(expected_sources):
                raise ValueError('Saved brief no longer binds the exact source run')
            if saved_dataset and canonical(saved_dataset['payload'].get('source_refs')) != canonical({'run_ref': _ref(saved_run)}):
                raise ValueError('Saved message bridge no longer binds its exact run')
            return {**refs, 'follow_ref': _ref(previous), 'idempotent': True}
        existing = []
        if previous:
            if previous['kind'] != 'observability_run' or previous['payload'].get('schema_version') != VERSION:
                raise ValueError('Saved observability run has an incompatible schema')
            if canonical(previous['payload']['source']) != canonical(submitted['source']) or canonical(previous['payload']['run']) != canonical(submitted['run']):
                raise ValueError('Source/run metadata must stay fixed; use a new run ID for a different source or run')
            existing = previous['payload']['events']
        by_id = {event['id']: event for event in existing}
        added = []
        for event in submitted['events']:
            if event['id'] in by_id:
                if canonical(by_id[event['id']]) != canonical(event): raise ValueError('Conflicting duplicate event ID; captured events cannot be rewritten')
            else: added.append(event)
        combined = {**submitted, 'events': existing + added}
        validate_batch(combined)
        if previous and not added:
            # A subset retry may be new, but it does not create a run version.
            brief = _latest(connection, brief_id)
            dataset = _latest(connection, dataset_id)
            expected_sources = {'run_ref': _ref(previous)} | ({'dataset_ref': _ref(dataset)} if dataset else {})
            if brief is None or canonical(brief['payload'].get('source_refs')) != canonical(expected_sources):
                raise ValueError('Current brief does not bind the current run and dataset')
            if dataset and canonical(dataset['payload'].get('source_refs')) != canonical({'run_ref': _ref(previous)}):
                raise ValueError('Current message dataset does not bind the current run')
            refs = {'run_ref': _ref(previous), 'dataset_ref': _ref(dataset) if dataset else None, 'brief_ref': _ref(brief)}
        else:
            payload = _run_payload(combined, _ref(previous) if previous else None,
                hashlib.sha256(raw).hexdigest(), batch_sha, original != submitted)
            run_record = _prospective(connection, 'observability_run', run_id, payload)
            dataset_payload = _dataset_payload(run_record)
            dataset_record = _prospective(connection, 'dataset', dataset_id, dataset_payload) if dataset_payload else None
            brief_payload = build_brief(run_record, dataset_record)
            expected_sources = {'run_ref': _ref(run_record)} | ({'dataset_ref': _ref(dataset_record)} if dataset_record else {})
            if type(brief_payload) is not dict or canonical(brief_payload.get('source_refs')) != canonical(expected_sources):
                raise ValueError('Automatic brief must bind the exact run and message dataset')
            brief_record = _prospective(connection, 'observation_brief', brief_id, brief_payload)
            for record in (run_record, dataset_record, brief_record):
                if record: _insert(connection, record)
            refs = {'run_ref': _ref(run_record), 'dataset_ref': _ref(dataset_record) if dataset_record else None, 'brief_ref': _ref(brief_record)}
        connection.execute('INSERT INTO observability_batches VALUES(?,?,?)', (run_id, batch_sha, json.dumps(refs, allow_nan=False)))
        return {**refs, 'follow_ref': refs['run_ref'], 'idempotent': False}


class _PinnedDatasetStore:
    def __init__(self, store, dataset):
        self._store, self._dataset = store, copy.deepcopy(dataset)

    def __getattr__(self, name):
        return getattr(self._store, name)

    def get(self, identity, version=None):
        if identity == self._dataset['id']:
            if version is not None and version != self._dataset['version']:
                raise ValueError('Automatic screening cannot change its source version')
            current = self._store.get(identity, self._dataset['version'])
            if canonical(_ref(current)) != canonical(_ref(self._dataset)):
                raise ValueError('Automatic screening source changed')
            return copy.deepcopy(self._dataset)
        return self._store.get(identity, version)


def _screen_dataset(lab, dataset_ref):
    """Cheap actual observe call, pinned even though the legacy method uses IDs.

    A local claim records an incomplete/failed screen rather than silently
    repeating it. This is a local intake checkpoint, not a distributed lease.
    """
    if dataset_ref is None:
        return {'discovery_ref': None, 'discovery_status': 'unavailable_no_reported_messages'}
    dataset = lab.store.get(dataset_ref['id'], dataset_ref['version'])
    if dataset['kind'] != 'dataset' or canonical(_ref(dataset)) != canonical(dataset_ref):
        raise ValueError('Screening requires its exact dataset')
    if any(type(message.get('room_id')) is not str or not message['room_id'] for message in dataset['payload']['messages']):
        return {'discovery_ref': None, 'discovery_status': 'unavailable_channel_scope_not_declared'}
    key = tuple(dataset_ref[name] for name in ('id', 'version', 'hash'))
    with lab.store.connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        connection.execute('CREATE TABLE IF NOT EXISTS observability_discoveries(dataset_id TEXT,dataset_version INTEGER,dataset_hash TEXT,status TEXT,discovery_ref TEXT,error_type TEXT,PRIMARY KEY(dataset_id,dataset_version,dataset_hash))')
        saved = connection.execute('SELECT * FROM observability_discoveries WHERE dataset_id=? AND dataset_version=? AND dataset_hash=?', key).fetchone()
        if saved:
            reference = json.loads(saved['discovery_ref']) if saved['discovery_ref'] else None
            if saved['status'] == 'completed':
                discovery = _bound_record(connection, reference, 'discovery')
                if canonical(discovery['payload'].get('dataset_ref')) != canonical(dataset_ref):
                    raise ValueError('Saved screening does not bind its exact dataset')
            return {'discovery_ref': reference, 'discovery_status': saved['status']}
        connection.execute('INSERT INTO observability_discoveries VALUES(?,?,?,?,?,?)', (*key, 'in_progress', None, None))
    try:
        pinned_lab = copy.copy(lab)
        pinned_lab.store = _PinnedDatasetStore(lab.store, dataset)
        discovery = pinned_lab.observe(dataset['id'], live=False)
        if (type(discovery) is not dict or discovery.get('kind') != 'discovery' or
            canonical(discovery['payload'].get('dataset_ref')) != canonical(dataset_ref)):
            raise ValueError('Automatic screening returned mismatched source evidence')
        reference = _ref(discovery)
        with lab.store.connect() as connection:
            connection.execute('UPDATE observability_discoveries SET status=?,discovery_ref=? WHERE dataset_id=? AND dataset_version=? AND dataset_hash=?',
                ('completed', json.dumps(reference), *key))
        return {'discovery_ref': reference, 'discovery_status': 'completed'}
    except Exception as error:
        with lab.store.connect() as connection:
            connection.execute('UPDATE observability_discoveries SET status=?,error_type=? WHERE dataset_id=? AND dataset_version=? AND dataset_hash=?',
                ('failed', type(error).__name__, *key))
        return {'discovery_ref': None, 'discovery_status': 'failed', 'screening_error_type': type(error).__name__}


def connect_observability(lab, raw):
    result = _connect_atomic(lab, raw)
    return {**result, **_screen_dataset(lab, result['dataset_ref'])}


def parse_follow_query(query):
    if type(query) is not dict or set(query) != {'run_id'} or type(query['run_id']) is not list or len(query['run_id']) != 1:
        raise ValueError('Follow requires one exact run_id')
    identity = query['run_id'][0]
    if type(identity) is not str or not re.fullmatch(r'observability_run-[0-9a-f]{24}', identity):
        raise ValueError('Follow requires a registered observability_run ID')
    return identity


def follow_observability(lab, run_id):
    identity = parse_follow_query({'run_id': [run_id]})
    suffix = identity.removeprefix('observability_run-')
    with lab.store.connect() as connection:
        run = _latest(connection, identity)
        if run is None: raise KeyError(identity)
        if run['kind'] != 'observability_run' or run['payload'].get('schema_version') != VERSION:
            raise ValueError('Follow source has an incompatible kind/schema')
        dataset = _latest(connection, 'dataset-observability-' + suffix)
        brief = _latest(connection, 'observation_brief-' + suffix)
        if brief is None: raise ValueError('Follow has no completed source-bound brief')
        refs = {'run_ref': _ref(run)} | ({'dataset_ref': _ref(dataset)} if dataset else {})
        if canonical(brief['payload'].get('source_refs')) != canonical(refs):
            raise ValueError('Follow brief does not bind the current exact source')
        if dataset and canonical(dataset['payload'].get('source_refs')) != canonical({'run_ref': _ref(run)}):
            raise ValueError('Follow message bridge does not bind its exact run')
        discovery_ref = None
        status = 'unavailable_no_reported_messages' if dataset is None else 'screening_not_recorded'
        exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='observability_discoveries'").fetchone()
        if dataset and exists:
            saved = connection.execute('SELECT * FROM observability_discoveries WHERE dataset_id=? AND dataset_version=? AND dataset_hash=?',
                tuple(dataset[key] for key in ('id', 'version', 'hash'))).fetchone()
            if saved:
                status = saved['status']
                if status == 'completed':
                    discovery_ref = json.loads(saved['discovery_ref'])
                    discovery = _bound_record(connection, discovery_ref, 'discovery')
                    if canonical(discovery['payload'].get('dataset_ref')) != canonical(_ref(dataset)):
                        raise ValueError('Follow screening does not bind the exact current dataset')
        return {'run_ref': _ref(run), 'follow_ref': _ref(run), 'dataset_ref': _ref(dataset) if dataset else None,
                'brief_ref': _ref(brief), 'discovery_ref': discovery_ref, 'discovery_status': status}


def protocol_manifest():
    example_path = Path(__file__).resolve().parents[1] / 'examples' / 'observability-demo.json'
    example = parse_batch(example_path.read_bytes())
    return {'schema_version': VERSION, 'title': 'Society Lab swarm event batches',
        'maximum_bytes': MAX_BYTES, 'maximum_events_per_accumulated_run': MAX_EVENTS,
        'maximum_json_depth': MAX_DEPTH, 'source_kinds': ['telemetry', 'authored_example'],
        'envelope_required': ['schema_version', 'source', 'run', 'events'],
        'source_required': ['id', 'name', 'kind'], 'source_optional': ['harness'],
        'run_required': ['id'], 'run_optional': ['name'],
        'event_required': ['id', 'occurred_at', 'kind', 'data'],
        'event_optional': ['actor_id', 'task_id', 'parent_task_id', 'recipient_ids'],
        'kinds': {kind: {'data_required': sorted(required), 'data_optional': sorted(optional)} for kind, (required, optional) in DATA_FIELDS.items()},
        'field_rules': ['Task events require task_id; other events require actor_id.',
            'Message/intervention recipient_ids are explicit; absent visibility and empty message addressing leave audience scope unknown.',
            'reasoning.recorded requires actor_id, recipient_ids:[] and data.content: an existing recorded rationale or local note, never fabricated hidden thoughts.',
            'Optional message.sent data.visibility is private/direct/room/broadcast/unknown. Private is self-only with no channel; direct has explicit peer recipients; room names a channel and may address peers; broadcast has empty recipients. These are producer labels, not receipt or membership proofs.',
            'Optional message.sent data.channel_name is a nonblank display label of at most 1000 characters; channel_id remains its separate stable identity.',
            'Only task.created may declare parent_task_id; timestamps require explicit timezone.',
            'success is Boolean, IDs are stable bounded strings, arguments/output are bounded finite JSON.',
            'Unknown fields and conflicting duplicate event IDs reject before any persisted update.'],
        'append_contract': {'identity': 'source.id + run.id', 'fixed_metadata': 'source and run labels/metadata',
            'events': 'append-only captured order, at most 2000 total and 1 MiB accumulated batch',
            'exact_retry': 'original exact run/dataset/brief refs; follow_ref is the separately identified current run',
            'overflow': 'reject, then rotate to a new run ID; no silent truncation'},
        'post_endpoint': '/api/observability/connect', 'session_header': 'X-Lab-Token from /api/state',
        'follow_endpoint': '/api/observability/follow?run_id=<registered observability_run ID>',
        'model_calls': 0, 'example': example, 'limitations': LIMITATIONS,
        'python_client_example': "import json, urllib.request\nbase='http://127.0.0.1:8765'\nstate=json.load(urllib.request.urlopen(base+'/api/state'))\nbatch=json.load(open('my-swarm-events.json',encoding='utf-8'))\nrequest=urllib.request.Request(base+'/api/observability/connect',data=json.dumps(batch).encode(),headers={'Content-Type':'application/json','X-Lab-Token':state['csrf']})\nprint(json.load(urllib.request.urlopen(request)))\n"}


def brief_dataset(lab, raw):
    if type(raw) is not bytes or not 0 < len(raw) <= 16000:
        raise ValueError('Send a bounded exact dataset reference')
    try:
        body = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_bad_constant)
        _bounded(body)
    except (RecursionError, UnicodeError, OverflowError) as error:
        raise ValueError('Invalid dataset brief request') from error
    _object(body, {'dataset_ref'})
    reference = body['dataset_ref']
    _object(reference, {'id', 'version', 'hash'})
    _id(reference['id'])
    if type(reference['version']) is not int or not 1 <= reference['version'] <= 1000000000:
        raise ValueError('Dataset version must be a positive integer')
    if type(reference['hash']) is not str or not re.fullmatch(r'[0-9a-f]{64}', reference['hash']):
        raise ValueError('Dataset reference needs its exact SHA-256')
    dataset = lab.store.get(reference['id'], reference['version'])
    if dataset['kind'] != 'dataset' or canonical(_ref(dataset)) != canonical(reference):
        raise ValueError('The exact dataset reference does not match')
    from .proactive_brief import build_chat_brief
    payload = build_chat_brief(dataset)
    if type(payload) is not dict or canonical(payload.get('source_refs')) != canonical({'dataset_ref': reference}):
        raise ValueError('Chat brief must bind its exact original dataset')
    brief = lab.store.put('observation_brief', payload)
    return {'run_ref': None, 'dataset_ref': _ref(dataset), 'brief_ref': _ref(brief),
            **_screen_dataset(lab, _ref(dataset))}
