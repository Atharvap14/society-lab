"""Product visibility separate from immutable scientific records.

Archiving removes old demonstrations from ordinary navigation. It does not
delete objects, rewrite their hashes or turn a new proxy study into history.
"""
import copy
import json

from .store import Store, now

VILLAGE_SOURCE = {'id': 'dataset-1ac43f5141de', 'version': 1,
    'hash': '16849167aecaa4815684f621d12940c905f18fa327e615778dae68362ee4883e'}
PROJECT_ID = 'project-ai-village'
CHAT_ID = 'chat-village-document-access'


def tables(c):
    c.executescript('''
      CREATE TABLE IF NOT EXISTS demo_hidden_objects(object_id TEXT,version INTEGER,archived_at TEXT,reason TEXT,PRIMARY KEY(object_id,version));
      CREATE TABLE IF NOT EXISTS demo_hidden_chats(chat_id TEXT PRIMARY KEY,archived_at TEXT,reason TEXT);
      CREATE TABLE IF NOT EXISTS demo_hidden_projects(project_id TEXT PRIMARY KEY,archived_at TEXT,reason TEXT);
      CREATE TABLE IF NOT EXISTS demo_hidden_jobs(job_id TEXT PRIMARY KEY,archived_at TEXT,reason TEXT);
      CREATE TABLE IF NOT EXISTS demo_visibility_settings(key TEXT PRIMARY KEY,value TEXT);
    ''')


def _exists(c, name):
    return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def state(c):
    """Read visibility metadata without initializing or mutating the registry."""
    settings = dict(c.execute('SELECT key,value FROM demo_visibility_settings')) if _exists(c, 'demo_visibility_settings') else {}
    return {'objects': {(r[0], r[1]) for r in c.execute('SELECT object_id,version FROM demo_hidden_objects')} if _exists(c, 'demo_hidden_objects') else set(),
        'chats': {r[0] for r in c.execute('SELECT chat_id FROM demo_hidden_chats')} if _exists(c, 'demo_hidden_chats') else set(),
        'projects': {r[0] for r in c.execute('SELECT project_id FROM demo_hidden_projects')} if _exists(c, 'demo_hidden_projects') else set(),
        'default_chat_id': settings.get('default_chat_id'), 'default_project_id': settings.get('default_project_id')}


def visible_inventory(lab, rows):
    if type(rows) is not list: raise ValueError('Inventory must be a list')
    with lab.store.connect() as c: hidden = state(c)['objects']
    return [copy.deepcopy(row) for row in rows if type(row) is dict and type(row.get('ref',row)) is dict and
        ((row.get('ref', row).get('id'), row.get('ref', row).get('version')) not in hidden)]


def visible_jobs(lab, rows):
    if type(rows) is not list: raise ValueError('Job inventory must be a list')
    with lab.store.connect() as c:
        hidden = {r[0] for r in c.execute('SELECT job_id FROM demo_hidden_jobs')} if _exists(c,'demo_hidden_jobs') else set()
    return [copy.deepcopy(row) for row in rows if type(row) is dict and row.get('id',row.get('job_id')) not in hidden]


def assert_visible_chat(c, chat_id):
    project = c.execute('SELECT project_id FROM workspace_chats WHERE id=?', (chat_id,)).fetchone()
    hidden_chat = _exists(c,'demo_hidden_chats') and c.execute('SELECT 1 FROM demo_hidden_chats WHERE chat_id=?',(chat_id,)).fetchone()
    hidden_project = project is not None and _exists(c,'demo_hidden_projects') and c.execute('SELECT 1 FROM demo_hidden_projects WHERE project_id=?',(project[0],)).fetchone()
    if hidden_chat or hidden_project:
        raise ValueError('This chat is archived from the active product workspace')


def assert_visible_object(c, reference):
    if _exists(c,'demo_hidden_objects') and c.execute('SELECT 1 FROM demo_hidden_objects WHERE object_id=? AND version=?',
        (reference['id'],reference['version'])).fetchone():
        raise ValueError('This saved item is archived from the active product workspace')


def _references(value, depth=0):
    if depth > 12: return []
    if type(value) is dict:
        if set(value) in ({'id','version','hash'}, {'kind','id','version','hash'}):
            return [{k:value[k] for k in ('id','version','hash')}]
        return [ref for child in value.values() for ref in _references(child, depth+1)]
    if type(value) is list: return [ref for child in value for ref in _references(child, depth+1)]
    return []


def archive_for_village(lab, *, source_ref=None):
    """Explicit local cleanup: preserve bytes, select real source-bound work.

    All previous projects/chats are archived. Only observational records tied
    to this exact dataset and the new access family remain in the clean chat.
    New objects created after this operation are visible by default.
    """
    from .lab_workspace import bootstrap_workspace, _new_chat, _link, _object
    reference = VILLAGE_SOURCE if source_ref is None else source_ref
    from .lab_workspace import _ref
    reference = _ref(reference)
    bootstrap_workspace(lab)
    eligible = {'dataset','discovery','behavior','research_attempt','theory','observation_brief',
        'village_incident','graph_discovery','measurement_audit','selected_lead_audit','temporal_path_audit',
        'temporal_timestamp_reference','indexed_event_audit','actor_event_audit','wait_marker_alignment_audit',
        'graph_hodge_audit','guided_plan','guided_simulator','guided_result','village_access_experiment','village_recovery_experiment',
        'village_access_attempt','protocol','verification','claim_audit'}
    with lab.store.connect() as c:
        tables(c); c.execute('BEGIN IMMEDIATE')
        source = _object(c, reference)
        if source['kind'] != 'dataset' or not source['payload'].get('messages'):
            raise ValueError('A clean Village workspace requires an exact nonempty message dataset')
        all_rows = c.execute('SELECT id,version,kind,hash FROM objects ORDER BY id,version').fetchall()
        old_study_kinds = {'experiment','network_experiment','complementary_experiment','resource_experiment',
            'timed_resource_experiment','revision_relay_experiment','guided_protocol','network_protocol',
            'complementary_protocol','resource_protocol','timed_resource_protocol','revision_relay_protocol'}
        excluded_studies = {(r['id'],r['version']) for r in all_rows if r['kind'] in old_study_kinds}
        keep = {(source['id'], source['version'])}; objects = {tuple((source['id'], source['version'])): source}
        candidates = []
        for row in all_rows:
            if row['kind'] not in eligible or (row['id'],row['version']) in keep: continue
            obj = _object(c, {k:row[k] for k in ('id','version','hash')})
            p = obj['payload']
            if row['kind'] in {'guided_plan','guided_simulator','guided_result','protocol','verification','claim_audit'}:
                family = p.get('family', p.get('protocol', {}).get('family'))
                # Proofs can be admitted through an already retained access result.
                if row['kind'] not in {'verification','claim_audit'} and family not in {'village_document_access_repair','single_document_reference_repair'}:
                    excluded_studies.add((row['id'],row['version'])); continue
            candidates.append((obj, _references(p)))
        new_result_keys = {(o['id'],o['version']) for o,_ in candidates if o['kind'] in {'village_access_experiment','village_recovery_experiment'} or
            (o['kind']=='guided_result' and o['payload'].get('family') in {'village_document_access_repair','single_document_reference_repair'})}
        candidates = [(obj,refs) for obj,refs in candidates if
            not any((r['id'],r['version']) in excluded_studies for r in refs) and
            (obj['kind'] not in {'verification','claim_audit'} or any((r['id'],r['version']) in new_result_keys for r in refs))]
        changed = True
        while changed:
            changed = False
            exact = {(obj['id'],obj['version'],obj['hash']) for obj in objects.values()}
            for obj, refs in candidates:
                key = (obj['id'],obj['version'])
                if key not in keep and any((r['id'],r['version'],r['hash']) in exact for r in refs):
                    keep.add(key); objects[key] = obj; changed = True
        stamp = now(); reason = 'Archived independent pilot or prior workspace; original record preserved.'
        for row in all_rows:
            key = (row['id'],row['version'])
            if key in keep: c.execute('DELETE FROM demo_hidden_objects WHERE object_id=? AND version=?', key)
            else: c.execute('INSERT OR REPLACE INTO demo_hidden_objects VALUES(?,?,?,?)', (*key,stamp,reason))
        for row in c.execute('SELECT id FROM workspace_projects').fetchall():
            if row[0] != PROJECT_ID: c.execute('INSERT OR REPLACE INTO demo_hidden_projects VALUES(?,?,?)', (row[0],stamp,reason))
        for row in c.execute('SELECT id FROM workspace_chats').fetchall():
            if row[0] != CHAT_ID: c.execute('INSERT OR REPLACE INTO demo_hidden_chats VALUES(?,?,?)', (row[0],stamp,reason))
        for row in c.execute('SELECT id FROM jobs').fetchall():
            c.execute('INSERT OR IGNORE INTO demo_hidden_jobs VALUES(?,?,?)',(row[0],stamp,reason))
        c.execute('INSERT OR IGNORE INTO workspace_projects VALUES(?,?,?,?)', (PROJECT_ID,'AI Village',stamp,stamp))
        c.execute('DELETE FROM demo_hidden_projects WHERE project_id=?', (PROJECT_ID,))
        c.execute('DELETE FROM demo_hidden_chats WHERE chat_id=?', (CHAT_ID,))
        if c.execute('SELECT 1 FROM workspace_chats WHERE id=?', (CHAT_ID,)).fetchone() is None:
            _new_chat(c, PROJECT_ID, 'Document access investigation', identity=CHAT_ID,
                state={'view':'workspace','context':{'dataset_ref':reference}},
                origin={'kind':'source_bound_investigation','dataset_ref':reference})
        for obj in objects.values(): _link(c,CHAT_ID,obj,'reference')
        for key,value in (('default_project_id',PROJECT_ID),('default_chat_id',CHAT_ID)):
            c.execute('INSERT OR REPLACE INTO demo_visibility_settings VALUES(?,?)',(key,value))
    return {'default_project_id':PROJECT_ID,'default_chat_id':CHAT_ID,'source_ref':reference,
        'visible_object_count':len(keep),'archived_object_count':len(all_rows)-len(keep),
        'scope':'Visibility cleanup only; all original scientific objects, messages and hashes are retained.'}
