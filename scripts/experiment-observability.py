"""Adapt exact saved shared-file execution traces, not invented agent messages.

No per-turn timestamps exist in these reports. occurred_at therefore carries
the report-start anchor; the companion provenance states that event time is
unknown. Stable event order follows saved turn order within separate teams.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from swarm_lab.observability_protocol import canonical, digest, validate_batch
from swarm_lab.store import fingerprint

ADAPTER_VERSION = 'saved-shared-artifact-observability-v1'
ACTION_FIELDS = {'send_message': {'action', 'recipient', 'message'},
    'inspect_artifact': {'action', 'artifact_id'}, 'repair_artifact': {'action', 'artifact_id', 'contents'},
    'publish_artifact': {'action', 'artifact_id'}, 'wait': {'action'}}
RESULT_FIELDS = {'ok', 'message_id', 'contents', 'id', 'version', 'artifact_id',
    'published_artifact_id', 'waited', 'error', 'reason'}


def exact(obj): return {key: obj[key] for key in ('id', 'version', 'hash')}


def validate_ref(reference):
    if (type(reference) is not dict or set(reference) != {'id', 'version', 'hash'} or
        type(reference['id']) is not str or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,199}', reference['id']) or
        type(reference['version']) is not int or not 1 <= reference['version'] <= 10**9 or
        type(reference['hash']) is not str or not re.fullmatch('[a-f0-9]{64}', reference['hash'])):
        raise ValueError('Choose an exact saved execution reference')
    return copy.deepcopy(reference)


def load_record(database, reference):
    reference = validate_ref(reference)
    path = Path(database).resolve()
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute('SELECT * FROM objects WHERE id=? AND version=?',
            (reference['id'], reference['version'])).fetchone()
        if row is None: raise ValueError('The exact saved execution is unavailable')
        def finite(_): raise ValueError('Nonfinite execution record')
        record = dict(row); record['payload'] = json.loads(record['payload'], parse_constant=finite)
        if exact(record) != reference or fingerprint(record['payload']) != reference['hash']:
            raise ValueError('Saved execution fingerprint mismatch')
        return record
    finally: connection.close()


def adapt_experiment(record):
    reference = validate_ref(exact(record)); p = record['payload']
    if record.get('kind') != 'experiment' or fingerprint(p) != reference['hash'] or p.get('status') != 'complete':
        raise ValueError('Use a complete exact shared-artifact execution, not an incomplete report')
    environment = p.get('protocol', {}).get('environment', {})
    roles = environment.get('agents')
    if environment.get('kind') != 'shared_artifact_coordination' or type(roles) is not list or not roles or len(set(roles)) != len(roles):
        raise ValueError('This adapter supports the explicit shared-artifact roles only')
    if p.get('agent_mode') != 'live' or p.get('backend', {}).get('metadata', {}).get('harness') != 'responses':
        raise ValueError('Use an execution declaring live Responses subjects; offline policies are not live telemetry')
    clock = p.get('started_at'); runs = p.get('runs')
    if type(runs) is not list or not runs: raise ValueError('No recorded experimental teams')
    prefix = 'exec-' + reference['hash'][:16]
    batch = {'schema_version': 'societylab.events.v1',
        'source': {'id': prefix, 'name': 'Recorded live execution; report-start clock anchor',
            'kind': 'authored_example' if p.get('source_kind') == 'authored_test_fixture' else 'telemetry', 'harness': 'responses'},
        'run': {'id': record['id'] + '-v' + str(record['version']), 'name': 'Separate teams from a saved shared-file experiment'}, 'events': []}
    provenance = {'adapter_version': ADAPTER_VERSION, 'source_ref': reference,
        'source_kind': 'authored_test_fixture' if p.get('source_kind') == 'authored_test_fixture' else 'saved_actual_execution_record',
        'clock_basis': 'report_start_anchor; individual event timestamps unavailable',
        'limits': ['Adapter reads a pinned local report, not a new subject experiment or independent provider attestation.',
            'Role and trial declarations are derived metadata, not newly observed registration or assignment actions.',
            'Each team has separate actor identities; the batch does not imply interaction between trials.',
            'Events are grouped in retained team/turn order; this is not a shared wall-clock chronology.',
            'Successful message tools record queued/addressed content, not recipient reading or influence.',
            'Private model rationale, prompts, hidden reasoning, seeded previous-shift messages and assigned notes are excluded.',
            'Artifact/task statuses derive from saved tool returns and the original oracle, not fresh filesystem reads.'],
        'event_sources': {}, 'omissions': []}
    run_ids = set()

    def event(identity, kind, data, *, actor=None, task=None, recipients=None, pointer=None):
        value = {'id': prefix + '-' + identity, 'occurred_at': clock, 'kind': kind, 'data': data}
        if actor is not None: value['actor_id'] = actor
        if task is not None: value['task_id'] = task
        if recipients is not None: value['recipient_ids'] = recipients
        batch['events'].append(value)
        provenance['event_sources'][value['id']] = {'source_ref': reference, 'field': pointer,
            'clock_basis': provenance['clock_basis']}
        return value

    for run_index, run in enumerate(runs):
        run_id = run.get('run_id')
        if type(run_id) is not str or run_id in run_ids: raise ValueError('Unique recorded team IDs are required')
        run_ids.add(run_id); task = prefix + '-' + run_id
        actors = {role: task + '-' + role for role in roles}
        base = 'payload.runs[' + str(run_index) + ']'
        for role in roles:
            event(run_id + '-register-' + role, 'agent.registered', {'name': run_id + ' / ' + role, 'roles': [role]},
                actor=actors[role], pointer='payload.protocol.environment.agents')
        event(run_id + '-task', 'task.created', {'title': 'Recorded shared-manifest task ' + run_id,
            'description': 'Derived trial declaration; task and event-time boundaries are in the companion provenance.'}, task=task, pointer=base)
        turns = run.get('turns')
        if type(turns) is not list: raise ValueError('Recorded turns are required')
        for turn_index, turn in enumerate(turns):
            role = turn.get('agent_id'); action = turn.get('action'); result = turn.get('tool_result')
            if role not in actors or type(action) is not dict or type(result) is not dict:
                raise ValueError('Each retained turn requires an explicit role, action and tool result')
            name = action.get('action'); fields = ACTION_FIELDS.get(name)
            if fields is None: raise ValueError('Unsupported action; do not invent a tool or expose raw model output')
            safe_action = {key: copy.deepcopy(value) for key, value in action.items() if key in fields}
            safe_result = {key: copy.deepcopy(value) for key, value in result.items() if key in RESULT_FIELDS}
            turn_pointer = base + '.turns[' + str(turn_index) + ']'
            call_id = task + '-turn-' + str(turn_index)
            source = {'source_ref': reference, 'run_id': run_id, 'turn_index': turn_index,
                'step': turn.get('step'), 'original_turn_sha256': fingerprint(turn),
                'clock_basis': provenance['clock_basis']}
            event(run_id + '-call-' + str(turn_index), 'tool.called',
                {'call_id': call_id, 'tool_name': name, 'arguments': {'recorded_action': safe_action, 'source': source}},
                actor=actors[role], task=task, pointer=turn_pointer + '.action')
            if type(result.get('ok')) is not bool:
                provenance['omissions'].append({'field': turn_pointer + '.tool_result', 'reason': 'No explicit Boolean ok; return success remains unknown'})
                continue
            event(run_id + '-return-' + str(turn_index), 'tool.returned',
                {'call_id': call_id, 'success': result['ok'], 'output': {'recorded_tool_result': safe_result, 'source': source}},
                actor=actors[role], task=task, pointer=turn_pointer + '.tool_result')
            if name == 'send_message' and result['ok']:
                target = action.get('recipient')
                if target == 'all':
                    recipients = []; data = {'content': action['message'], 'visibility': 'broadcast', 'channel_id': task}
                elif target in actors and target != role:
                    recipients = [actors[target]]; data = {'content': action['message'], 'visibility': 'direct'}
                else: raise ValueError('Successful addressed send has an unresolved recipient; cannot infer delivery scope')
                sent = event(run_id + '-message-' + str(turn_index), 'message.sent', data,
                    actor=actors[role], task=task, recipients=recipients, pointer=turn_pointer + '.action.message')
                provenance['event_sources'][sent['id']]['recorded_message_id'] = result.get('message_id')
            if name == 'repair_artifact' and result['ok']:
                if type(result.get('version')) is not int: raise ValueError('Successful repair needs a recorded version')
                event(run_id + '-artifact-' + str(turn_index), 'artifact.updated',
                    {'artifact_id': task + '-' + action['artifact_id'], 'revision_id': 'version-' + str(result['version']),
                        'change_summary': 'Recorded successful repair returned this version; no new filesystem check.',
                        'content_sha256': digest(action['contents'])}, actor=actors[role], task=task, pointer=turn_pointer + '.tool_result')
        success = run.get('outcomes', {}).get('success')
        if type(success) is int and success in (0, 1):
            event(run_id + '-completion', 'task.completed', {'success': bool(success), 'summary': 'Original saved publication oracle outcome.'},
                task=task, pointer=base + '.outcomes.success')
        else: provenance['omissions'].append({'field': base + '.outcomes.success', 'reason': 'No typed binary oracle outcome'})
    validate_batch(batch)
    provenance['batch_sha256'] = digest(batch)
    provenance['adapter_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    provenance['counts'] = {name: sum(e['kind'] == name for e in batch['events']) for name in sorted({e['kind'] for e in batch['events']})}
    return {'batch': batch, 'provenance': provenance}


def connect_batch(base_url, batch, *, chat_id=None):
    url = urllib.parse.urlsplit(base_url)
    if url.scheme != 'http' or url.hostname not in ('127.0.0.1', 'localhost', '::1') or url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
        raise ValueError('Connect only to a clean local Society Lab root URL')
    base_url = base_url.rstrip('/')
    with urllib.request.urlopen(base_url + '/api/state', timeout=30) as response: state = json.load(response)
    headers = {'Content-Type': 'application/json', 'X-Lab-Token': state['csrf']}
    if chat_id is not None: headers['X-Lab-Chat'] = chat_id
    request = urllib.request.Request(base_url + '/api/observability/connect', data=canonical(batch), headers=headers, method='POST')
    with urllib.request.urlopen(request, timeout=60) as response: return json.load(response)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--object-id', required=True); parser.add_argument('--version', required=True, type=int)
    parser.add_argument('--hash', required=True); parser.add_argument('--database', type=Path, default=ROOT / '.runtime' / 'lab.sqlite3')
    parser.add_argument('--output', type=Path, required=True); parser.add_argument('--connect-url'); parser.add_argument('--chat-id')
    args = parser.parse_args(argv)
    reference = {'id': args.object_id, 'version': args.version, 'hash': args.hash}
    adapted = adapt_experiment(load_record(args.database, reference))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(adapted['batch']))
    companion = args.output.with_suffix('.source.json')
    companion.write_text(json.dumps(adapted['provenance'], indent=2), encoding='utf-8')
    if args.connect_url:
        receipt = connect_batch(args.connect_url, adapted['batch'], chat_id=args.chat_id)
        args.output.with_suffix('.receipt.json').write_text(json.dumps({'source_ref': reference,
            'batch_sha256': adapted['provenance']['batch_sha256'], 'receipt': receipt}, indent=2), encoding='utf-8')
        print(json.dumps({'run_ref': receipt['run_ref'], 'dataset_ref': receipt.get('dataset_ref'),
            'brief_ref': receipt['brief_ref'], 'idempotent': receipt.get('idempotent')}, indent=2))
    else: print('Saved a validated batch and provenance; no intake or model calls were made.')
    return 0


if __name__ == '__main__': raise SystemExit(main())
