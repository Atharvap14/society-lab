"""Durable local conversations and exact artifact references, separate from science.

Workspace revisions organize recorded discussion. They are not registrations,
source attestations or permission to run agents. An editable copy is always a
workspace_draft; cloning a report cannot create a new empirical result.
"""
import copy
from contextlib import contextmanager
import json
import math
import re
import uuid

from .store import Store, clean, fingerprint, now

SCHEMA = 'lab-workspaces-v1'
DEFAULT_PROJECT = 'project-existing-research'
DEFAULT_CHAT = 'chat-existing-research'
MAX_BODY = 131072
VIEWS = {'home', 'watch', 'findings', 'import', 'try', 'overview', 'observatory', 'experiments',
         'episode', 'library', 'audit', 'connect', 'brief', 'plan', 'simulator',
         'workspace', 'projects', 'artifacts', 'workspace-copy', 'measurement'}
CONTEXT_KINDS = {'dataset_ref': {'dataset'}, 'run_ref': {'observability_run'},
    'brief_ref': {'observation_brief'}, 'discovery_ref': {'discovery'}, 'plan_ref': {'guided_plan'},
    'simulator_ref': {'guided_simulator'}, 'result_ref': {'experiment', 'network_experiment',
        'complementary_experiment', 'resource_experiment', 'timed_resource_experiment',
        'revision_relay_experiment', 'guided_result'}, 'behavior_ref': {'behavior'},
    'rubric_ref': {'behavior_rubric'}, 'measurement_ref': {'rubric_measurement'}}
CONTEXT_KINDS['incident_ref'] = {'village_incident'}
CONTEXT_KINDS['result_ref'].update({'village_access_experiment','village_recovery_experiment'})
CONTEXT_KINDS['execution_ref'] = {'guided_result'}


class WorkspaceConflictError(ValueError):
    def __init__(self, latest_revision):
        self.latest_revision = latest_revision
        super().__init__('Workspace revision conflict; reload this chat before saving')


def _identifier(value, label='ID'):
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,199}', value):
        raise ValueError(label + ' must be a bounded stable identifier')
    return value


def _text(value, maximum, label, *, empty=False):
    if type(value) is not str or len(value) > maximum or (not empty and not value.strip()):
        raise ValueError(label + ' must be bounded plain text')
    value.encode('utf-8')
    return value


def _integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(label + ' must be a bounded integer')
    return value


def _bounded(value, maximum=MAX_BODY):
    nodes = 0
    def visit(item, depth=0):
        nonlocal nodes
        nodes += 1
        if nodes > 30000 or depth > 12:
            raise ValueError('Workspace JSON exceeds its structural bound')
        if item is None or type(item) is bool:
            return
        if type(item) in (int, float):
            if not math.isfinite(item) or abs(item) > 2**53 - 1:
                raise ValueError('Workspace numbers must be finite and safely bounded')
            return
        if type(item) is str:
            _text(item, 32768, 'JSON text', empty=True)
            return
        if type(item) is list:
            if len(item) > 2000:
                raise ValueError('Workspace list exceeds its bound')
            for child in item: visit(child, depth + 1)
            return
        if type(item) is dict:
            if len(item) > 128 or any(type(key) is not str or len(key) > 200 for key in item):
                raise ValueError('Workspace object exceeds its bound')
            for key, child in item.items():
                key.encode('utf-8'); visit(child, depth + 1)
            return
        raise ValueError('Workspace values must be finite JSON')
    try:
        visit(value)
        if len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')) > maximum:
            raise ValueError('Workspace JSON exceeds its byte bound')
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError('Invalid bounded workspace JSON') from error
    return value


def _pairs(entries):
    values = {}
    for key, value in entries:
        if key in values: raise ValueError('Duplicate workspace JSON key')
        values[key] = value
    return values


def parse_request(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BODY:
        raise ValueError('Use a bounded JSON workspace request')
    def constant(_): raise ValueError('Workspace values must be finite JSON')
    try:
        return _bounded(json.loads(raw, object_pairs_hook=_pairs, parse_constant=constant))
    except (RecursionError, UnicodeError) as error:
        raise ValueError('Invalid bounded workspace JSON') from error


def _ref(value):
    if type(value) is not dict or set(value) != {'id', 'version', 'hash'}:
        raise ValueError('Use an exact artifact reference')
    _identifier(value['id'], 'Artifact ID')
    _integer(value['version'], 1, 10**9, 'Artifact version')
    if type(value['hash']) is not str or not re.fullmatch('[0-9a-f]{64}', value['hash']):
        raise ValueError('Artifact hash must be a lowercase SHA-256')
    return copy.deepcopy(value)


def _object(c, reference):
    reference = _ref(reference)
    row = c.execute('SELECT * FROM objects WHERE id=? AND version=?', (reference['id'], reference['version'])).fetchone()
    if row is None: raise KeyError(reference['id'])
    obj = Store._decode(row)
    if obj['hash'] != reference['hash']:
        raise ValueError('Artifact source reference does not match')
    return obj


def _chat(c, identity):
    _identifier(identity, 'Chat ID')
    row = c.execute('SELECT * FROM workspace_chats WHERE id=?', (identity,)).fetchone()
    if row is None: raise KeyError(identity)
    from .demo_visibility import assert_visible_chat
    assert_visible_chat(c,identity)
    return row


def validate_chat(lab, chat_id):
    with lab.store.connect() as c:
        row = _chat(c, chat_id)
    return {'id': row['id'], 'project_id': row['project_id'], 'revision': row['revision']}


def _source_refs(payload):
    refs = []; seen = set()
    def walk(value, path, depth=0):
        if depth > 6 or len(refs) >= 64: return
        if type(value) is dict:
            if set(value) in ({'id', 'version', 'hash'}, {'kind', 'id', 'version', 'hash'}):
                try: ref = _ref({key: value[key] for key in ('id', 'version', 'hash')})
                except ValueError: return
                marker = (ref['id'], ref['version'], ref['hash'], path)
                if marker not in seen:
                    refs.append({'ref': ref, 'field': path}); seen.add(marker)
                return
            for key, child in list(value.items())[:128]:
                if key.endswith('_ref') or key.endswith('_refs') or key == 'source_refs' or depth:
                    walk(child, path + '.' + key if path else key, depth + 1)
        elif type(value) is list:
            for index, child in enumerate(value[:64]): walk(child, path + '[' + str(index) + ']', depth + 1)
    if type(payload) is dict: walk(payload, '')
    return refs


def _descriptor(obj):
    p = obj['payload']; inner = p.get('protocol', {}) if type(p) is dict else {}
    candidates = [p.get(key) for key in ('name', 'title', 'question', 'statement')] if type(p) is dict else []
    if obj['kind'] == 'behavior_rubric' and type(p.get('spec')) is dict:
        candidates.insert(0, p['spec'].get('title'))
    if type(inner) is dict: candidates.append(inner.get('research_question'))
    title = next((value.strip()[:200] for value in candidates if type(value) is str and value.strip()), obj['kind'].replace('_', ' '))
    labels = [p.get(key) for key in ('status', 'agent_mode', 'subject_mode')] if type(p) is dict else []
    summary = ' · '.join([obj['kind'].replace('_', ' '), *(value[:100] for value in labels if type(value) is str)])
    if obj['kind']=='dataset' and obj.get('id')=='dataset-1ac43f5141de' and obj.get('version')==1 and obj.get('hash')=='16849167aecaa4815684f621d12940c905f18fa327e615778dae68362ee4883e':
        title='AI Village · September agent logs'
        summary='2,000 retained September source posts · observed reports, not authenticated tool or account state.'
    if obj['kind'] == 'village_incident':
        title = 'AI Village document-access incidents'
        incidents = p.get('incidents',[]); evidence = p.get('evidence',[])
        if type(incidents) is list and type(evidence) is list:
            count = len({row['message_id'] for row in evidence if type(row) is dict and type(row.get('message_id')) is str})
            summary = str(len(incidents))+' episodes · '+str(count)+' exact source messages · chat reports only; original tool state unverified.'
    elif p.get('family') in {'village_document_access_repair','single_document_reference_repair'}:
        titles = {'guided_plan':'Document access — matched-team plan','guided_simulator':'AI Village access world',
            'village_access_experiment':'Document-access experiment results'}
        title = titles.get(obj['kind'],title)
        if obj['kind'] == 'guided_plan' and type(p.get('question')) is str:
            summary = p['question']+' · Source-grounded proxy; subjects have not run from this plan description.'
    if obj['kind'] in {'village_access_experiment','village_recovery_experiment'}:
        title = 'Single-document reference recovery results' if obj['kind']=='village_recovery_experiment' else 'Document-access experiment results'
        summary += ' · Controlled access-world outcomes; historical causes remain unknown.'
    return {'title': clean(title), 'summary': clean(summary), 'source_refs': _source_refs(p)}


def _link(c, chat_id, obj, relation, origin_chat_id=None, *, bump=True):
    row = _chat(c, chat_id)
    ref = {key: obj[key] for key in ('id', 'version', 'hash')}
    prior = c.execute('SELECT hash FROM workspace_artifacts WHERE chat_id=? AND object_id=? AND version=?', (chat_id, obj['id'], obj['version'])).fetchone()
    if prior:
        if prior['hash'] != obj['hash']: raise ValueError('Linked artifact hash changed')
        return False
    revision = row['revision'] + 1 if bump else row['revision']
    c.execute('INSERT INTO workspace_artifacts VALUES(?,?,?,?,?,?,?,?,?,?)',
        (chat_id, obj['id'], obj['version'], obj['hash'], obj['kind'], relation, origin_chat_id,
         obj.get('created', now()), revision, json.dumps(_descriptor(obj), ensure_ascii=False)))
    if bump: _bump(c, chat_id)
    return True


def _bump(c, chat_id):
    c.execute('UPDATE workspace_chats SET revision=revision+1,updated=? WHERE id=?', (now(), chat_id))
    row = _chat(c, chat_id)
    c.execute('INSERT INTO workspace_chat_revisions VALUES(?,?,?,?,?,?,?,?)',
        (row['id'], row['revision'], row['project_id'], row['name'], row['state'], row['origin'], row['created'], row['updated']))
    return row['revision']


def _new_chat(c, project_id, name, *, identity=None, state=None, origin=None):
    if c.execute('SELECT 1 FROM workspace_projects WHERE id=?', (project_id,)).fetchone() is None: raise KeyError(project_id)
    identity = identity or 'chat-' + uuid.uuid4().hex[:20]
    created = now()
    c.execute('INSERT INTO workspace_chats VALUES(?,?,?,?,?,?,?,?)',
        (identity, project_id, name, 0, json.dumps(state or {}, ensure_ascii=False),
         json.dumps(origin, ensure_ascii=False), created, created))
    _bump(c, identity)
    return identity


def bootstrap_workspace(lab):
    """Idempotently organize existing latest records once, without cloning them."""
    with lab.store.connect() as c:
        c.executescript('''
          CREATE TABLE IF NOT EXISTS workspace_projects(id TEXT PRIMARY KEY,name TEXT,created TEXT,updated TEXT);
          CREATE TABLE IF NOT EXISTS workspace_chats(id TEXT PRIMARY KEY,project_id TEXT,name TEXT,revision INTEGER,state TEXT,origin TEXT,created TEXT,updated TEXT);
          CREATE TABLE IF NOT EXISTS workspace_chat_revisions(chat_id TEXT,revision INTEGER,project_id TEXT,name TEXT,state TEXT,origin TEXT,created TEXT,updated TEXT,PRIMARY KEY(chat_id,revision));
          CREATE TABLE IF NOT EXISTS workspace_messages(chat_id TEXT,sequence INTEGER,id TEXT,request_id TEXT,role TEXT,content TEXT,metadata TEXT,created TEXT,added_revision INTEGER,PRIMARY KEY(chat_id,sequence));
          CREATE TABLE IF NOT EXISTS workspace_artifacts(chat_id TEXT,object_id TEXT,version INTEGER,hash TEXT,kind TEXT,relation TEXT,origin_chat_id TEXT,created TEXT,added_revision INTEGER,descriptor TEXT,PRIMARY KEY(chat_id,object_id,version));
          CREATE TABLE IF NOT EXISTS workspace_requests(request_id TEXT PRIMARY KEY,request_hash TEXT,result TEXT);
        ''')
        c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT 1 FROM workspace_chats WHERE id=?', (DEFAULT_CHAT,)).fetchone() is None:
            created = now()
            c.execute('INSERT OR IGNORE INTO workspace_projects VALUES(?,?,?,?)', (DEFAULT_PROJECT, 'Existing research', created, created))
            _new_chat(c, DEFAULT_PROJECT, 'Research workspace', identity=DEFAULT_CHAT)
            # Exact registry metadata, no latest substitutions after this snapshot.
            rows = c.execute('SELECT * FROM objects ORDER BY created,id,version').fetchall()
            for row in rows:
                obj = Store._decode(row)
                _link(c, DEFAULT_CHAT, obj, 'reference', bump=False)
    return {'default_project_id': DEFAULT_PROJECT, 'default_chat_id': DEFAULT_CHAT}


def _snapshot(c, chat_id, revision=None):
    current = _chat(c, chat_id)
    revision = current['revision'] if revision is None else _integer(revision, 1, 10**9, 'Chat revision')
    row = c.execute('SELECT * FROM workspace_chat_revisions WHERE chat_id=? AND revision=?', (chat_id, revision)).fetchone()
    if row is None: raise ValueError('The exact chat revision is unavailable')
    messages = c.execute('SELECT * FROM workspace_messages WHERE chat_id=? AND added_revision<=? ORDER BY sequence', (chat_id, revision)).fetchall()
    artifacts = c.execute('SELECT * FROM workspace_artifacts WHERE chat_id=? AND added_revision<=? ORDER BY created,object_id,version', (chat_id, revision)).fetchall()
    state = json.loads(row['state'])
    packet = {'schema_version': SCHEMA, 'id': chat_id, 'project_id': row['project_id'], 'name': row['name'],
        'revision': revision, 'state': state, 'origin': json.loads(row['origin']), 'created': row['created'], 'updated': row['updated'],
        'messages': [{key: item[key] for key in ('id', 'sequence', 'request_id', 'role', 'content', 'created')} |
                     {'metadata': json.loads(item['metadata'])} for item in messages],
        'artifacts': [{'ref': {'id': item['object_id'], 'version': item['version'], 'hash': item['hash']},
            'kind': item['kind'], 'relation': item['relation'], 'origin_chat_id': item['origin_chat_id'], 'created': item['created'],
            **json.loads(item['descriptor'])} for item in artifacts],
        'context_links': state.get('context_links', []),
        'scope': 'Recorded workspace organization and discussion, not new scientific evidence or source attestation.'}
    packet['snapshot_hash'] = fingerprint(packet)
    return packet


def chat_snapshot(lab, chat_id, *, revision=None):
    with lab.store.connect() as c:
        c.execute('BEGIN')
        return _snapshot(c, chat_id, revision)


def workspace_index(lab):
    with lab.store.connect() as c:
        c.execute('BEGIN')
        from .demo_visibility import state
        visibility = state(c)
        projects = [dict(row) for row in c.execute('SELECT * FROM workspace_projects ORDER BY created,id') if row['id'] not in visibility['projects']]
        for project in projects:
            project['chats'] = [dict(row) for row in c.execute('SELECT id,name,revision,updated FROM workspace_chats WHERE project_id=? ORDER BY created,id', (project['id'],)) if row['id'] not in visibility['chats']]
    return {'schema_version': SCHEMA, 'default_project_id': visibility['default_project_id'] or DEFAULT_PROJECT,
        'default_chat_id': visibility['default_chat_id'] or DEFAULT_CHAT, 'projects': projects}


def read_context(lab, chat_id, *, revision=None):
    packet = chat_snapshot(lab, chat_id, revision=revision)
    messages = []; remaining = 6000
    for row in reversed(packet['messages'][-12:]):
        content = row['content'][-min(remaining, 2000):] if remaining else ''
        if not content: break
        remaining -= len(content)
        messages.append({key: row[key] for key in ('id', 'sequence', 'role', 'request_id')} |
                        {'content': content, 'truncated': len(content) != len(row['content'])})
    return {key: packet[key] for key in ('schema_version', 'id', 'project_id', 'name', 'revision', 'snapshot_hash', 'origin')} | {
        'state': packet['state'], 'messages': list(reversed(messages)), 'artifacts': packet['artifacts'][-48:],
        'message_count': len(packet['messages']), 'messages_truncated': len(messages) != len(packet['messages']) or any(row['truncated'] for row in messages),
        'artifact_count': len(packet['artifacts']), 'artifacts_truncated': len(packet['artifacts']) > 48,
        'scope': 'Bounded borrowed discussion from this exact chat revision. Message statements and workspace metadata are unverified; this is not scientific source evidence, replay or permission to act.'}


def _state(c, value):
    if type(value) is not dict or not set(value) <= {'view', 'selections', 'context', 'plan_draft', 'notes', 'context_links', 'ui'}:
        raise ValueError('Use supported typed working-state fields')
    _bounded(value, 65536)
    if 'view' in value and (type(value['view']) is not str or value['view'] not in VIEWS): raise ValueError('Unknown workspace view')
    if 'notes' in value: _text(value['notes'], 8000, 'Working notes', empty=True)
    if 'ui' in value and type(value['ui']) is not dict: raise ValueError('Working UI state must be a JSON object')
    if 'plan_draft' in value:
        draft = value['plan_draft']
        if type(draft) is not dict or set(draft) != {'question', 'control_text', 'treatment_text'}: raise ValueError('Use the three editable plan fields')
        for item in draft.values(): _text(item, 2000, 'Draft text', empty=True)
    for key in ('selections', 'context'):
        if key not in value: continue
        if type(value[key]) is not dict or len(value[key]) > 64: raise ValueError('Working references must be a small object')
        for name, reference in value[key].items():
            if key == 'context' and name not in CONTEXT_KINDS: raise ValueError('Unknown working context reference')
            _identifier(name, 'Selection name')
            obj = _object(c, reference)
            if key == 'context' and obj['kind'] not in CONTEXT_KINDS[name]: raise ValueError('Working source kind does not match')
    links = value.get('context_links', [])
    if type(links) is not list or len(links) > 16: raise ValueError('Use at most sixteen exact chat context links')
    seen = set()
    for link in links:
        if type(link) is not dict or set(link) != {'chat_id', 'revision', 'snapshot_hash'}: raise ValueError('Use an exact chat revision link')
        identity = _identifier(link['chat_id'], 'Context chat ID'); version = _integer(link['revision'], 1, 10**9, 'Context revision')
        if (identity, version) in seen: raise ValueError('Duplicate chat context link')
        seen.add((identity, version))
        if _snapshot(c, identity, version)['snapshot_hash'] != link['snapshot_hash']: raise ValueError('Chat context link fingerprint does not match')
    return clean(copy.deepcopy(value))


def _mutation(lab, body, work):
    _bounded(body)
    request_id = _identifier(body.get('request_id'), 'Workspace request ID')
    digest = fingerprint(body)
    with lab.store.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        prior = c.execute('SELECT * FROM workspace_requests WHERE request_id=?', (request_id,)).fetchone()
        if prior:
            if prior['request_hash'] != digest: raise ValueError('Workspace request ID was reused with different input')
            return {**json.loads(prior['result']), 'reused': True}
        result = clean(work(c)) | {'reused': False}
        c.execute('INSERT INTO workspace_requests VALUES(?,?,?)', (request_id, digest, json.dumps(result, ensure_ascii=False)))
        return result


def save_state(lab, chat_id, *, expected_revision, state, request_id):
    body = {'op': 'save_state', 'request_id': request_id, 'chat_id': chat_id, 'expected_revision': expected_revision, 'state': state}
    _integer(expected_revision, 1, 10**9, 'Expected revision')
    def work(c):
        row = _chat(c, chat_id)
        if row['revision'] != expected_revision: raise WorkspaceConflictError(row['revision'])
        prepared = _state(c, state)
        c.execute('UPDATE workspace_chats SET state=? WHERE id=?', (json.dumps(prepared, ensure_ascii=False), chat_id))
        _bump(c, chat_id)
        return {'chat': _snapshot(c, chat_id)}
    return _mutation(lab, body, work)


def append_message(lab, chat_id, *, role, content, request_id, expected_revision=None, metadata=None):
    if type(role) is not str or role not in ('user', 'assistant'): raise ValueError('Conversation roles are user or assistant')
    _text(content, 12000, 'Conversation message')
    metadata = {} if metadata is None else metadata
    if type(metadata) is not dict: raise ValueError('Message metadata must be a JSON object')
    _bounded(metadata, 32768)
    if expected_revision is not None: _integer(expected_revision, 1, 10**9, 'Expected revision')
    body = {'op': 'append_message', 'request_id': request_id, 'chat_id': chat_id, 'role': role, 'content': content, 'metadata': metadata, 'expected_revision': expected_revision}
    def work(c):
        row = _chat(c, chat_id)
        if expected_revision is not None and row['revision'] != expected_revision: raise WorkspaceConflictError(row['revision'])
        sequence = c.execute('SELECT COALESCE(MAX(sequence),0)+1 FROM workspace_messages WHERE chat_id=?', (chat_id,)).fetchone()[0]
        if sequence > 2000: raise ValueError('This chat reached its message bound; start another chat. Existing messages remain saved.')
        message = {'id': 'message-' + uuid.uuid4().hex[:20], 'sequence': sequence, 'request_id': request_id,
            'role': role, 'content': clean(content), 'metadata': clean(metadata), 'created': now()}
        c.execute('INSERT INTO workspace_messages VALUES(?,?,?,?,?,?,?,?,?)',
            (chat_id, sequence, message['id'], request_id, role, message['content'], json.dumps(message['metadata'], ensure_ascii=False), message['created'], row['revision'] + 1))
        revision = _bump(c, chat_id)
        return {'chat_id': chat_id, 'chat_revision': revision, 'message': message}
    return _mutation(lab, body, work)


def _copy_payload(obj, name):
    p = obj['payload']
    fields = ('question', 'control_text', 'treatment_text', 'family', 'objective', 'trials_per_arm', 'max_rounds',
              'valid_probability', 'seed', 'hypothesis', 'statement', 'predictions', 'rival_theories', 'falsifiers', 'limitations')
    editable = {key: copy.deepcopy(p[key]) for key in fields if type(p) is dict and key in p}
    if obj['kind'] == 'workspace_draft':
        saved = p.get('editable_fields')
        if type(saved) is not dict or not set(saved) <= set(fields) | {'notes', 'source_brief_ref','source_dataset_ref','source_incident_ref'}:
            raise ValueError('The source draft has unsupported editable fields')
        for key in ('question', 'control_text', 'treatment_text', 'family', 'objective', 'hypothesis', 'statement', 'notes'):
            if key in saved and type(saved[key]) is not str: raise ValueError('Source draft text fields must be plain text')
        for key in ('trials_per_arm', 'max_rounds', 'seed'):
            if key in saved and type(saved[key]) is not int: raise ValueError('Source draft integer fields must remain typed integers')
        if 'valid_probability' in saved and type(saved['valid_probability']) not in (int, float):
            raise ValueError('Source draft probability must remain numeric')
        for key in ('predictions', 'rival_theories', 'falsifiers', 'limitations'):
            if key in saved and type(saved[key]) is not list: raise ValueError('Source draft list fields must remain typed lists')
        if saved.get('source_brief_ref') is not None: _ref(saved['source_brief_ref'])
        for key in ('source_dataset_ref','source_incident_ref'):
            if saved.get(key) is not None: _ref(saved[key])
        editable = copy.deepcopy(saved)
    if obj['kind'].endswith('experiment') or obj['kind'] == 'verification':
        frozen = p.get('protocol', {})
        editable = {'question': frozen.get('research_question', '') if type(frozen) is dict else '',
                    'notes': p.get('claim_scope', p.get('scope', '')) if type(p.get('claim_scope', p.get('scope', ''))) is str else ''}
    if obj['kind'] == 'guided_plan':
        if p.get('family') in {'village_document_access_repair','single_document_reference_repair'}:
            editable['source_dataset_ref'] = copy.deepcopy(p.get('source_refs',{}).get('dataset_ref'))
            editable['source_incident_ref'] = copy.deepcopy(p.get('source_refs',{}).get('incident_ref'))
        else: editable['source_brief_ref'] = copy.deepcopy(p.get('source_ref'))
    # Entire reports/proofs, outcomes and established-status fields never copy.
    _bounded(editable, 65536)
    return {'schema_version': 'workspace-draft-v1', 'status': 'editable_draft', 'name': name,
        'source_ref': {key: obj[key] for key in ('id', 'version', 'hash')}, 'source_kind': obj['kind'],
        'original_source_ref': {key: obj[key] for key in ('id', 'version', 'hash')},
        'editable_fields': clean(editable), 'copied_empirical_outcomes': False,
        'scope': 'Editable working copy with exact original provenance. It is unregistered and has no new outcomes, verification, mechanism-fit approval or causal status.'}


def mutate_workspace(lab, raw):
    body = parse_request(raw) if type(raw) is bytes else _bounded(raw)
    if type(body) is not dict or type(body.get('op')) is not str: raise ValueError('Use a workspace operation')
    op = body['op']
    allowed = {'create_project': ({'op', 'request_id', 'name'}, set()),
        'create_chat': ({'op', 'request_id', 'project_id', 'name'}, set()),
        'save_state': ({'op', 'request_id', 'chat_id', 'expected_revision', 'state'}, set()),
        'append_message': ({'op', 'request_id', 'chat_id', 'role', 'content'}, {'metadata', 'expected_revision'}),
        'reuse_artifact': ({'op', 'request_id', 'artifact_ref', 'origin_chat_id', 'target_chat_id'}, set()),
        'clone_artifact': ({'op', 'request_id', 'artifact_ref', 'origin_chat_id', 'target_chat_id'}, {'name'}),
        'update_draft': ({'op', 'request_id', 'chat_id', 'draft_ref', 'fields'}, set()),
        'fork_chat': ({'op', 'request_id', 'origin_chat_id', 'expected_revision', 'name'}, {'project_id'})}
    if op not in allowed or not allowed[op][0] <= set(body) or not set(body) <= allowed[op][0] | allowed[op][1]: raise ValueError('Workspace operation fields do not match')
    if op == 'save_state': return save_state(lab, **{key: value for key, value in body.items() if key != 'op'})
    if op == 'append_message': return append_message(lab, **{key: value for key, value in body.items() if key != 'op'})
    if 'name' in body: _text(body['name'], 120, 'Workspace name')
    def work(c):
        if op == 'create_project':
            identity = 'project-' + uuid.uuid4().hex[:20]; created = now()
            c.execute('INSERT INTO workspace_projects VALUES(?,?,?,?)', (identity, clean(body['name']), created, created))
            return {'project': {'id': identity, 'name': clean(body['name']), 'created': created}}
        if op == 'create_chat':
            _identifier(body['project_id'], 'Project ID')
            identity = _new_chat(c, body['project_id'], clean(body['name']))
            return {'chat': _snapshot(c, identity)}
        if op == 'update_draft':
            target = _chat(c, body['chat_id']); obj = _object(c, body['draft_ref'])
            latest = c.execute('SELECT MAX(version) FROM objects WHERE id=?', (obj['id'],)).fetchone()[0]
            if latest != obj['version']: raise ValueError('Editable draft version conflict; reload the exact latest draft before updating')
            linked = c.execute('SELECT 1 FROM workspace_artifacts WHERE chat_id=? AND object_id=? AND version=? AND hash=?',
                               (target['id'], obj['id'], obj['version'], obj['hash'])).fetchone()
            if obj['kind'] != 'workspace_draft' or obj['payload'].get('owner_chat_id') != target['id'] or linked is None:
                raise ValueError('Only this chat\'s own editable draft can be updated')
            fields = body['fields']
            if type(fields) is not dict or not fields or not set(fields) <= {'name', 'notes', 'question', 'control_text', 'treatment_text'}:
                raise ValueError('Use supported editable draft fields')
            for key, value in fields.items(): _text(value, 120 if key == 'name' else 2000, 'Editable draft text', empty=key != 'name')
            payload = copy.deepcopy(obj['payload'])
            if 'name' in fields: payload['name'] = clean(fields['name'])
            payload['editable_fields'].update(clean({key: value for key, value in fields.items() if key != 'name'}))
            payload['previous_ref'] = body['draft_ref']
            version, created, digest = latest + 1, now(), fingerprint(payload)
            c.execute('INSERT INTO objects VALUES(?,?,?,?,?,?)', (obj['id'], version, obj['kind'], created, json.dumps(payload, ensure_ascii=False), digest))
            saved = {**obj, 'version': version, 'payload': payload, 'hash': digest, 'created': created}
            _link(c, target['id'], saved, 'created', target['id'])
            return {'artifact_ref': {key: saved[key] for key in ('id', 'version', 'hash')}, 'chat': _snapshot(c, target['id'])}
        origin = _chat(c, body['origin_chat_id'])
        if op == 'fork_chat':
            _integer(body['expected_revision'], 1, 10**9, 'Expected revision')
            if origin['revision'] != body['expected_revision']: raise WorkspaceConflictError(origin['revision'])
            source = _snapshot(c, origin['id'])
            project = body.get('project_id', origin['project_id']); _identifier(project, 'Project ID')
            identity = _new_chat(c, project, clean(body['name']), state=source['state'],
                origin={'chat_id': origin['id'], 'revision': origin['revision'], 'snapshot_hash': source['snapshot_hash']})
            for message in source['messages']:
                c.execute('INSERT INTO workspace_messages VALUES(?,?,?,?,?,?,?,?,?)', (identity, message['sequence'],
                    'message-' + uuid.uuid4().hex[:20], 'fork-' + fingerprint({'request_id': body['request_id'], 'sequence': message['sequence']}),
                    message['role'], message['content'], json.dumps({**message['metadata'], 'copied_from_message_id': message['id']}, ensure_ascii=False), message['created'], 1))
            for link in source['artifacts']:
                obj = _object(c, link['ref']); _link(c, identity, obj, 'reused', origin['id'], bump=False)
            return {'chat': _snapshot(c, identity)}
        target = _chat(c, body['target_chat_id']); obj = _object(c, body['artifact_ref'])
        source_link = c.execute('SELECT hash FROM workspace_artifacts WHERE chat_id=? AND object_id=? AND version=?',
            (origin['id'], obj['id'], obj['version'])).fetchone()
        if source_link is None or source_link['hash'] != obj['hash']: raise ValueError('The exact artifact is not linked to its declared origin chat')
        if op == 'reuse_artifact':
            _link(c, target['id'], obj, 'reused', origin['id'])
            return {'artifact_ref': body['artifact_ref'], 'chat': _snapshot(c, target['id'])}
        payload = _copy_payload(obj, clean(body.get('name', 'Working copy of ' + _descriptor(obj)['title']))[:120])
        payload['origin_chat_ref'] = {'id': origin['id'], 'revision': origin['revision']}
        payload['owner_chat_id'] = target['id']
        identity = 'workspace_draft-' + uuid.uuid4().hex[:12]; created = now(); digest = fingerprint(payload)
        c.execute('INSERT INTO objects VALUES(?,?,?,?,?,?)', (identity, 1, 'workspace_draft', created, json.dumps(payload, ensure_ascii=False), digest))
        draft = {'id': identity, 'version': 1, 'kind': 'workspace_draft', 'hash': digest, 'payload': payload, 'created': created}
        _link(c, target['id'], draft, 'copied', origin['id'])
        return {'artifact_ref': {key: draft[key] for key in ('id', 'version', 'hash')}, 'chat': _snapshot(c, target['id'])}
    return _mutation(lab, body, work)


def parse_chat_query(query):
    if type(query) is not dict or 'chat_id' not in query or not set(query) <= {'chat_id', 'revision'}:
        raise ValueError('Use chat_id and an optional exact revision')
    if any(type(value) is not list or len(value) != 1 or type(value[0]) is not str or not value[0] for value in query.values()):
        raise ValueError('Use single nonblank chat query parameters')
    result = {'chat_id': _identifier(query['chat_id'][0], 'Chat ID')}
    if 'revision' in query:
        value = query['revision'][0]
        if not re.fullmatch(r'[1-9][0-9]{0,9}', value): raise ValueError('Use a canonical positive chat revision')
        result['revision'] = _integer(int(value), 1, 10**9, 'Chat revision')
    return result


def artifact_catalog(lab, *, scope='all', project_id=None, chat_id=None, limit=2000, cursor=None):
    if type(scope) is not str or scope not in ('all', 'project', 'chat'): raise ValueError('Choose all, project or chat artifact scope')
    _integer(limit, 1, 2000, 'Catalog limit')
    if (scope == 'all' and (project_id is not None or chat_id is not None)) or (scope == 'project' and (project_id is None or chat_id is not None)) or (scope == 'chat' and (chat_id is None or project_id is not None)):
        raise ValueError('Artifact scope and identifiers disagree')
    offset = 0
    if cursor is not None:
        if type(cursor) is not str or not re.fullmatch(r'0|[1-9][0-9]{0,6}', cursor): raise ValueError('Use a canonical catalog cursor')
        offset = int(cursor)
    with lab.store.connect() as c:
        c.execute('BEGIN')
        from .demo_visibility import state
        visibility = state(c)
        where, args = '', []
        if scope == 'chat': _chat(c, chat_id); where, args = ' WHERE a.chat_id=?', [chat_id]
        if scope == 'project':
            _identifier(project_id, 'Project ID')
            if c.execute('SELECT 1 FROM workspace_projects WHERE id=?', (project_id,)).fetchone() is None: raise KeyError(project_id)
            where, args = ' WHERE ch.project_id=?', [project_id]
        rows = c.execute('SELECT a.*,ch.name chat_name,ch.project_id,p.name project_name FROM workspace_artifacts a JOIN workspace_chats ch ON ch.id=a.chat_id JOIN workspace_projects p ON p.id=ch.project_id' + where + ' ORDER BY a.created DESC,a.object_id,a.version,a.chat_id', args).fetchall()
        grouped = {}; origin_memo = {}
        for row in rows:
            key = (row['object_id'], row['version'], row['hash'])
            if row['chat_id'] in visibility['chats'] or row['project_id'] in visibility['projects'] or key[:2] in visibility['objects']: continue
            origin = {'project_id': row['project_id'], 'project_name': row['project_name'], 'chat_id': row['chat_id'], 'chat_name': row['chat_name']}
            if key not in grouped:
                from .research_origin import classify_record
                obj = _object(c, {'id': key[0], 'version': key[1], 'hash': key[2]})
                grouped[key] = {'ref': {'id': key[0], 'version': key[1], 'hash': key[2]}, 'kind': row['kind'],
                    **_descriptor(obj), **classify_record(c, obj, memo=origin_memo), 'created_at': row['created'], 'relation': row['relation'], 'origin': origin, 'origins': [origin]}
            elif origin not in grouped[key]['origins']:
                grouped[key]['origins'].append(origin)
                if row['relation'] == 'created': grouped[key].update(origin=origin, relation='created')
        all_rows = list(grouped.values()); selected = all_rows[offset:offset + limit]
    visible = {(item['ref']['id'], item['ref']['version'], item['ref']['hash']) for item in selected}
    edges = [{'from_ref': source['ref'], 'to_ref': item['ref'], 'relation': 'recorded_reference', 'label': source['field']}
        for item in selected for source in item['source_refs'] if (source['ref']['id'], source['ref']['version'], source['ref']['hash']) in visible]
    return {'schema_version': SCHEMA, 'scope': scope, 'artifacts': selected, 'edges': edges,
        'total': len(all_rows), 'truncated': offset + len(selected) < len(all_rows),
        'next_cursor': str(offset + len(selected)) if offset + len(selected) < len(all_rows) else None,
        'limits': 'Live offset catalog; new links may shift pages. Reference edges are saved provenance, not causal or communication edges.'}


def parse_catalog_query(query):
    if type(query) is not dict or not set(query) <= {'scope', 'project_id', 'chat_id', 'limit', 'cursor'}:
        raise ValueError('Unknown artifact catalog parameter')
    if any(type(value) is not list or len(value) != 1 or not value[0] for value in query.values()): raise ValueError('Use single nonblank catalog parameters')
    result = {key: value[0] for key, value in query.items()}
    if 'limit' in result:
        if not re.fullmatch('[1-9][0-9]{0,3}', result['limit']): raise ValueError('Use a canonical positive catalog limit')
        result['limit'] = int(result['limit'])
    return result


class _ChatStore:
    """Capture creation origin without altering frozen scientific payloads."""
    def __init__(self, store, chat_id): self._store, self.chat_id = store, chat_id
    def __getattr__(self, name): return getattr(self._store, name)

    def put(self, kind, payload, object_id=None):
        payload = clean(payload); identity = object_id or kind + '-' + uuid.uuid4().hex[:12]
        encoded, digest, created = json.dumps(payload, ensure_ascii=False), fingerprint(payload), now()
        with self._store.connect() as c:
            c.execute('BEGIN IMMEDIATE'); _chat(c, self.chat_id)
            previous = c.execute('SELECT kind FROM objects WHERE id=? LIMIT 1', (identity,)).fetchone()
            if previous and previous['kind'] != kind: raise ValueError('An object ID cannot change kind across versions')
            version = c.execute('SELECT COALESCE(MAX(version),0)+1 FROM objects WHERE id=?', (identity,)).fetchone()[0]
            c.execute('INSERT INTO objects VALUES(?,?,?,?,?,?)', (identity, version, kind, created, encoded, digest))
            obj = {'id': identity, 'version': version, 'kind': kind, 'created': created, 'payload': payload, 'hash': digest}
            _link(c, self.chat_id, obj, 'created', self.chat_id)
        return copy.deepcopy(obj)

    def compare_and_put(self, kind, payload, object_id, *, expected_version, expected_hash, job_updates=None):
        underlying, chat_id = self._store, self.chat_id
        # Run the existing Store CAS implementation unchanged. Its connection
        # also captures origin before the same transaction commits, including
        # checkpoint/job atomicity and the exact inserted-version return.
        class OriginTransaction:
            _decode = staticmethod(Store._decode)
            @contextmanager
            def connect(self):
                with underlying.connect() as c:
                    _chat(c, chat_id)
                    yield c
                    row = c.execute('SELECT * FROM objects WHERE id=? AND version=?', (object_id, expected_version + 1)).fetchone()
                    _link(c, chat_id, Store._decode(row), 'created', chat_id)
        updates = [{**update, 'payload': {**update['payload'], 'origin_chat_id': chat_id}}
            if type(update) is dict and type(update.get('payload')) is dict else update for update in job_updates] if type(job_updates) is list else job_updates
        return Store.compare_and_put(OriginTransaction(), kind, payload, object_id,
            expected_version=expected_version, expected_hash=expected_hash, job_updates=updates)

    def job(self, job_id, status, payload):
        return self._store.job(job_id, status, {**payload, 'origin_chat_id': self.chat_id})

    def start_job(self, job_id, payload):
        return self._store.start_job(job_id, {**payload, 'origin_chat_id': self.chat_id})


def for_chat(lab, chat_id):
    validate_chat(lab, chat_id)
    scoped = copy.copy(lab); scoped.store = _ChatStore(lab.store, chat_id)
    return scoped


def attach_returned(lab, chat_id, value):
    """Link exact direct-SQL endpoint outputs omitted by Store.put interception."""
    references = []; seen = set()
    def collect(item, depth=0):
        if depth > 8 or len(references) >= 128: return
        if type(item) is dict:
            if {'id', 'version', 'hash'} <= set(item):
                try: ref = _ref({key: item[key] for key in ('id', 'version', 'hash')})
                except ValueError: return
                marker = (ref['id'], ref['version'], ref['hash'])
                if marker not in seen: seen.add(marker); references.append(ref)
                return
            for key, child in list(item.items())[:128]:
                if key.endswith('_ref') or key in ('outputs', 'result', 'references'): collect(child, depth + 1)
        elif type(item) is list:
            for child in item[:128]: collect(child, depth + 1)
    collect(value)
    with lab.store.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        for reference in references:
            obj = _object(c, reference)
            # A reused, older source is a reference, never a newly created output.
            _link(c, chat_id, obj, 'reference', bump=True)
