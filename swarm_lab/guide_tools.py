"""Actual bounded operations callable by the navigation/planning agent.

The host supplies explicit intent authorization and the exact references the
agent has seen. Receipts describe operations, never hidden model reasoning or
scientific verification. Interrupted operations are not automatically retried.
"""
import copy
import json

from .lab_workspace import (_bounded, _identifier, _integer, _ref, _text,
    attach_returned, for_chat, mutate_workspace, validate_chat)
from .store import clean, fingerprint, now

TOOLS = frozenset(('connect_source','discover', 'save_plan', 'save_village_plan', 'save_village_recovery_plan', 'build_simulator', 'run_experiment',
    'reuse_artifact', 'copy_artifact', 'edit_copy', 'create_project', 'create_chat', 'fork_chat',
    'list_rubrics', 'save_rubric', 'measure_rubric', 'event_neighborhood'))
REF_SCHEMA = {'type': 'object', 'additionalProperties': False,
    'properties': {'id': {'type': 'string'}, 'version': {'type': 'integer', 'minimum': 1},
        'hash': {'type': 'string'}}, 'required': ['id', 'version', 'hash']}
TEXT = {'type': 'string'}
NULL_TEXT = {'type': ['string', 'null']}


def _schema(properties):
    return {'type': 'object', 'additionalProperties': False, 'properties': properties,
            'required': list(properties)}


def _nullable_integer(low, high):
    return {'type': ['integer', 'null'], 'minimum': low, 'maximum': high}


SPECS = {
    'connect_source': ('Connect one exact visible recorded message dataset to this working chat and create its observational brief. This does not run investigators, plan an experiment, build a world or execute subjects. Use available_dataset_sources; chat IDs are not source IDs.', {'source_ref': REF_SCHEMA}),
    'save_village_recovery_plan': ('Save a narrow source-grounded AI Village reference-recovery study: one correct original document and two roles, owner and auditor. The common task requires the auditor to actually open its current version. Broken reference recovery is tested; no four-document completion goal or historical reconstruction. Use an exact source, distinct equal-word-count notes. Defaults: 2 matched pairs, seed 42, 8 rounds, 64 subject opportunities. No subjects run at plan creation.',
        {'dataset_ref': REF_SCHEMA, 'behavior_ref': {'anyOf': [REF_SCHEMA, {'type':'null'}]},
         'question':TEXT,'control_text':TEXT,'treatment_text':TEXT,
         'trials_per_arm':_nullable_integer(2,8),'seed':_nullable_integer(0,2**53-1),
         'max_rounds':_nullable_integer(4,10)}),
    'save_village_plan': ('Save a source-grounded AI Village document-access study. Use the exact real message dataset and an optional source-matched behavior; a rejected candidate does not become established. Notes must be distinct with equal word counts. Null defaults: 2 matched pairs, seed 42, 8 rounds. This records a plan and incident packet; no subjects run.',
        {'dataset_ref': REF_SCHEMA, 'behavior_ref': {'anyOf': [REF_SCHEMA, {'type':'null'}]},
         'question':TEXT,'control_text':TEXT,'treatment_text':TEXT,
         'trials_per_arm':_nullable_integer(2,8),'seed':_nullable_integer(0,2**53-1),
         'max_rounds':_nullable_integer(6,10)}),
    'discover': ('Screen the exact saved message dataset, then queue real LLM investigators. Use only when the user explicitly asks to discover or investigate.',
        {'source_ref': REF_SCHEMA, 'count': _nullable_integer(1, 4)}),
    'save_plan': ('Save a new live shared-file experiment plan from the exact briefing. This records a plan; it does not run subjects. Null numeric values use stated defaults: 2 teams per condition, seed 42, 3 rounds, initial correct-file probability 0.5.',
        {'source_ref': REF_SCHEMA, 'question': TEXT, 'control_text': TEXT, 'treatment_text': TEXT,
         'trials_per_arm': _nullable_integer(2, 20), 'seed': _nullable_integer(0, 2**53 - 1),
         'max_rounds': _nullable_integer(2, 12), 'valid_probability': {'type': ['number', 'null'], 'minimum': 0, 'maximum': 1}}),
    'build_simulator': ('Invoke actual LLM environment-builder and causal reviewer for the exact source-grounded Village document-access plan. It checks the executable access world; it does not reconstruct historical Google state or identify a historical mechanism.',
        {'plan_ref': REF_SCHEMA}),
    'run_experiment': ('Run actual LLM subject teams in the exact saved simulator, followed by independent replay and checked result claims. Use only after an explicit execution request.',
        {'simulator_ref': REF_SCHEMA}),
    'reuse_artifact': ('Link this exact saved item from a seen origin chat to the active chat, without cloning an experiment or changing its provenance.',
        {'artifact_ref': REF_SCHEMA, 'origin_chat_id': TEXT}),
    'copy_artifact': ('Create an editable workspace draft in the active chat. It preserves the exact source and does not copy outcomes or verification as new empirical evidence.',
        {'artifact_ref': REF_SCHEMA, 'origin_chat_id': TEXT, 'name': NULL_TEXT}),
    'edit_copy': ('Save a new version of the active chat\'s own editable workspace draft. Null fields remain unchanged; do not edit frozen scientific records.',
        {'draft_ref': REF_SCHEMA, 'fields': _schema({key: NULL_TEXT for key in ('name', 'notes', 'question', 'control_text', 'treatment_text')})}),
    'create_project': ('Create a named local project when explicitly requested. This does not run research.', {'name': TEXT}),
    'create_chat': ('Create a new named chat in the exact existing project ID when explicitly requested.', {'project_id': TEXT, 'name': TEXT}),
    'fork_chat': ('Fork the seen discussion at its exact current revision into an editable chat, preserving origin and reusing exact artifacts. Null project_id retains the source project.',
        {'origin_chat_id': TEXT, 'expected_revision': {'type': 'integer', 'minimum': 1}, 'name': TEXT, 'project_id': NULL_TEXT}),
    'list_rubrics': ('Read the adapted unvalidated behavior rubric catalog and saved exact rubric references. This does not classify messages or approve a behavioral construct.', {}),
    'save_rubric': ('Save a prompt-defined rubric for an explicit text screen. Opportunity scoring remains unavailable; no behavior or social trait is validated.',
        {key: TEXT for key in ('title', 'question', 'opportunity', 'positive', 'negative', 'unknown', 'screen_prompt', 'non_examples')}),
    'measure_rubric': ('Run the exact saved rubric on a bounded exact message dataset through real local Laya. Runtime or RAM failure remains unknown with no regex fallback. This does not score opportunity episodes.',
        {'dataset_ref': REF_SCHEMA, 'rubric_ref': REF_SCHEMA, 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 32}}),
    'event_neighborhood': ('Read explicit field-reference neighbors of one captured event in an exact saved observability run. No private content or model reasoning is exported. These are declared source references, not causal influence, delivery or readership.',
        {'run_ref': REF_SCHEMA, 'event_id': {'type': 'string', 'maxLength': 128},
         'hops': {'type': 'integer', 'minimum': 0, 'maximum': 2}}),
}


def guide_tool_schemas(authorized_tools):
    names = _authorized(authorized_tools)
    return [{'type': 'function', 'name': name, 'description': SPECS[name][0],
             'parameters': _schema(copy.deepcopy(SPECS[name][1])), 'strict': True} for name in sorted(names)]


def _authorized(value):
    if type(value) not in (set, frozenset, list, tuple) or len(value) > len(TOOLS):
        raise ValueError('Guide tools require a bounded host authorization list')
    if any(type(name) is not str or name not in TOOLS for name in value):
        raise ValueError('Unsupported guide tool authorization')
    return set(value)


def _record(lab, reference, kind=None):
    reference = _ref(reference)
    from .demo_visibility import assert_visible_object
    with lab.store.connect() as c: assert_visible_object(c,reference)
    obj = lab.store.get(reference['id'], reference['version'])
    if {key: obj[key] for key in reference} != reference or (kind is not None and obj['kind'] != kind):
        raise ValueError('The exact guide source has a different version, hash or kind')
    return obj


def _prepare(lab, name, args, allowed_refs, chats):
    if type(args) is not dict: raise ValueError('Guide tool arguments must be a JSON object')
    _bounded(args, 16000)
    expected = set(SPECS[name][1])
    required = {'discover': {'source_ref'}, 'save_plan': {'source_ref', 'question', 'control_text', 'treatment_text'},
        'save_village_plan': {'dataset_ref','question','control_text','treatment_text'},
        'save_village_recovery_plan': {'dataset_ref','question','control_text','treatment_text'},
        'copy_artifact': {'artifact_ref', 'origin_chat_id'}, 'fork_chat': {'origin_chat_id', 'expected_revision', 'name'}}.get(name, expected)
    if not required <= set(args) or not set(args) <= expected:
        raise ValueError('Guide tool argument fields do not match')
    args = copy.deepcopy(clean(args))
    if type(allowed_refs) not in (list, tuple) or len(allowed_refs) > 256:
        raise ValueError('Supply the bounded exact references actually shown to this agent')
    seen = {fingerprint(_ref(reference)) for reference in allowed_refs}
    kinds = {'connect_source':'dataset','discover': 'dataset', 'save_plan': 'observation_brief', 'build_simulator': 'guided_plan',
        'run_experiment': 'guided_simulator', 'edit_copy': 'workspace_draft'}
    for key in ('source_ref', 'plan_ref', 'simulator_ref', 'artifact_ref', 'draft_ref', 'dataset_ref', 'rubric_ref', 'run_ref', 'behavior_ref'):
        if key not in args: continue
        if key == 'behavior_ref' and args[key] is None: continue
        reference = _ref(args[key])
        if fingerprint(reference) not in seen: raise ValueError('Guide source was not in the authenticated context or tool receipts')
        kind = {'dataset_ref': 'dataset', 'rubric_ref': 'behavior_rubric', 'run_ref': 'observability_run','behavior_ref':'behavior'}.get(key, kinds.get(name))
        _record(lab, reference, kind); args[key] = reference
    if 'origin_chat_id' in args:
        identity = _identifier(args['origin_chat_id'], 'Origin chat ID')
        if identity not in chats: raise ValueError('Origin chat was not supplied in the authenticated chat catalog')
        validate_chat(lab, identity)
    for key in ('name', 'project_id'):
        if args.get(key) is not None:
            (_identifier(args[key], 'Project ID') if key == 'project_id' else _text(args[key], 120, 'Name'))
    if name == 'discover':
        args['count'] = 2 if args.get('count') is None else _integer(args['count'], 1, 4, 'Investigator case count')
    if name == 'save_plan':
        for key in ('question', 'control_text', 'treatment_text'): _text(args[key], 2000, 'Plan text')
        for key, default, low, high in (('trials_per_arm', 2, 2, 20), ('seed', 42, 0, 2**53 - 1), ('max_rounds', 3, 2, 12)):
            args[key] = default if args.get(key) is None else _integer(args[key], low, high, key)
        probability = .5 if args.get('valid_probability') is None else args['valid_probability']
        if type(probability) not in (int, float) or not 0 <= probability <= 1: raise ValueError('Use a finite initial validity probability from 0 to 1')
        args['valid_probability'] = probability
    if name in ('save_village_plan','save_village_recovery_plan'):
        import re
        for key in ('question','control_text','treatment_text'): _text(args[key],2000,'Village plan text')
        question = args['question']
        if not re.search(r'doc|sheet|form|url|browser|drive|acl|session|permission|reference|access', question,re.I):
            raise ValueError('This world requires a specific document-access question grounded in the selected Village reports')
        dataset = _record(lab,args['dataset_ref'],'dataset')
        provenance = dataset['payload'].get('provenance',{})
        if (type(provenance) is not dict or not re.fullmatch('[0-9a-f]{40}',str(provenance.get('revision','')))
            or not re.fullmatch('[0-9a-f]{64}',str(provenance.get('source_sha256','')))
            or provenance.get('source_sha256') != provenance.get('expected_sha256')):
            raise ValueError('Choose the preserved AI Village source with recorded snapshot and matching compressed-source provenance')
        if args['control_text'] == args['treatment_text'] or len(args['control_text'].split()) != len(args['treatment_text'].split()):
            raise ValueError('Use distinct Village notes with equal word counts')
        args['behavior_ref'] = args.get('behavior_ref')
        for key,default,low,high in (('trials_per_arm',2,2,8),('seed',42,0,2**53-1),('max_rounds',8,4 if name=='save_village_recovery_plan' else 6,10)):
            args[key] = default if args.get(key) is None else _integer(args[key],low,high,key)
        if args['behavior_ref'] is not None:
            behavior = _record(lab,args['behavior_ref'],'behavior')
            if behavior['payload'].get('source_refs',{}).get('dataset') != args['dataset_ref']:
                raise ValueError('The selected behavior belongs to a different exact dataset')
    if name == 'fork_chat': _integer(args['expected_revision'], 1, 10**9, 'Origin chat revision')
    if name == 'edit_copy':
        fields = args['fields']
        if type(fields) is not dict or not set(fields) <= set(SPECS[name][1]['fields']['properties']): raise ValueError('Use supported editable copy fields')
        fields = {key: value for key, value in fields.items() if value is not None}
        if not fields: raise ValueError('Specify at least one editable field')
        for key, value in fields.items(): _text(value, 120 if key == 'name' else 2000, 'Editable copy text', empty=key != 'name')
        args['fields'] = fields
    if name == 'save_rubric':
        from .behavior_rubrics import _spec
        args = _spec(args)
    if name == 'measure_rubric':
        from .behavior_rubrics import validate_rubric_record
        _integer(args['limit'], 1, 32, 'Rubric sample limit')
        validate_rubric_record(lab, args['rubric_ref'])
    if name == 'event_neighborhood':
        import re
        if type(args['event_id']) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}', args['event_id']):
            raise ValueError('Choose a strict captured event ID')
        _integer(args['hops'], 0, 2, 'Event-neighborhood hops')
        source = _record(lab, args['run_ref'], 'observability_run')
        if not any(row.get('id') == args['event_id'] for row in source['payload'].get('events', []) if type(row) is dict):
            raise ValueError('Selected event is absent from this exact captured run')
    return args


def _tables(connection):
    connection.executescript('''
      CREATE TABLE IF NOT EXISTS guide_tool_requests(request_id TEXT PRIMARY KEY,chat_id TEXT,tool TEXT,request_hash TEXT,status TEXT,result TEXT,created TEXT,updated TEXT);
      CREATE TABLE IF NOT EXISTS guide_tool_events(id TEXT PRIMARY KEY,request_id TEXT,chat_id TEXT,tool TEXT,phase TEXT,summary TEXT,created TEXT,result_refs TEXT);
    ''')


def _event(connection, request_id, chat_id, name, phase, summary, refs):
    identity = 'guide-event-' + fingerprint({'request': request_id, 'phase': phase})[:24]
    event = {'id': identity, 'request_id': request_id, 'tool': name, 'phase': phase,
        'summary': clean(summary)[:240], 'created': now(), 'result_refs': copy.deepcopy(refs)}
    connection.execute('INSERT INTO guide_tool_events VALUES(?,?,?,?,?,?,?,?)',
        (identity, request_id, chat_id, name, phase, event['summary'], event['created'], json.dumps(refs)))
    return event


def _refs(value):
    return [copy.deepcopy(value[key]) for key in ('plan_ref', 'simulator_ref', 'execution_ref', 'result_ref', 'verification_ref',
        'claims_ref', 'brief_ref', 'discovery_ref', 'dataset_ref', 'incident_ref', 'artifact_ref', 'rubric_ref', 'measurement_ref') if type(value.get(key)) is dict]


def _perform(lab, name, args, chat_id, request_id, queue_submit):
    from . import guided_study
    raw = lambda value: json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
    view, context, extra = 'workspace', {}, {}
    if name == 'connect_source':
        from .observability_protocol import brief_dataset
        value=brief_dataset(lab,raw({'dataset_ref':args['source_ref']}))
        context={key:value[key] for key in ('dataset_ref','brief_ref','discovery_ref') if value.get(key) is not None}
        view='brief';summary='Connected the exact recorded source and saved its observational brief. No investigators or experimental subjects ran.'
    elif name == 'discover':
        from .observability_protocol import brief_dataset
        if not callable(queue_submit): raise ValueError('Discovery requires the captured local job queue')
        value = brief_dataset(lab, raw({'dataset_ref': args['source_ref']}))
        if value.get('discovery_ref') is None: raise ValueError('This source has no available discovery screening; inspect its retained briefing')
        discovery = value['discovery_ref']
        queued = queue_submit('investigate', {'discovery_id': discovery['id'], 'discovery_version': discovery['version'],
            'discovery_hash': discovery['hash'], 'count': args['count'], 'live': True, 'harness': 'responses'}, chat_id)
        extra['job_id'] = _identifier(queued.get('job_id'), 'Queued job ID')
        extra['investigation_status'] = 'queued'
        context = {key: value[key] for key in ('dataset_ref', 'brief_ref', 'discovery_ref')}; view = 'brief'
        summary = 'Queued real LLM investigators for up to ' + str(args['count']) + ' source-bound cases; their findings are still pending.'
    elif name == 'save_plan':
        value = guided_study.create_plan(lab, raw({**args, 'signal_code': None,
            'family': 'shared_artifact_coordination', 'objective': 'correct_published_file'}))
        context = {'brief_ref': args['source_ref'], 'plan_ref': value['plan_ref']}; view = 'plan'
        summary = 'Saved the exact live experiment plan; subjects have not run.'
    elif name in ('save_village_plan','save_village_recovery_plan'):
        if name == 'save_village_recovery_plan':
            from .reference_repair_study import create_plan
        else:
            from .village_access_study import create_plan
        value = create_plan(lab,raw(args))
        context = {key:value[key] for key in ('dataset_ref','incident_ref','plan_ref')}; view = 'plan'
        summary = 'Saved the source-grounded document-access plan and exact incident evidence; historical causes remain unknown and subjects have not run.'
    elif name == 'build_simulator':
        plan = _record(lab,args['plan_ref'],'guided_plan')
        if plan['payload'].get('family') == 'single_document_reference_repair':
            from . import reference_repair_study
            value = reference_repair_study.create_simulator(lab,raw(args))
        elif plan['payload'].get('family') == 'village_document_access_repair':
            from . import village_access_study
            value = village_access_study.create_simulator(lab,raw(args))
        else: value = guided_study.create_simulator(lab, raw(args))
        context = {'plan_ref': args['plan_ref'], 'simulator_ref': value['simulator_ref']}; view = 'simulator'
        summary = 'The real builder and causal-reviewer operation returned an executable checked world; historical mechanism fit remains unestablished.'
    elif name == 'run_experiment':
        simulator = _record(lab,args['simulator_ref'],'guided_simulator')
        if simulator['payload'].get('family') == 'single_document_reference_repair':
            from . import reference_repair_study
            reference_repair_study.validate_saved_world(lab,simulator)
            value = reference_repair_study.execute_plan(lab,raw(args))
        elif simulator['payload'].get('family') == 'village_document_access_repair':
            from . import village_access_study
            village_access_study.validate_saved_world(lab,simulator)
            value = village_access_study.execute_plan(lab,raw(args))
        else: value = guided_study.execute_plan(lab, raw(args))
        context = {'simulator_ref': args['simulator_ref'], 'result_ref': value['result_ref'], 'plan_ref': value['plan_ref'], 'execution_ref': value['execution_ref']}; view = 'findings'
        summary = ('Returned the already completed recorded study; this request did not run new subjects.' if value.get('reused') is True else
            'The real LLM study returned completed units, a replay check and finite result claims. Read the recorded result for effects and uncertainty.')
        extra['execution_reused'] = value.get('reused') is True
    elif name == 'list_rubrics':
        from .behavior_rubrics import rubric_catalog
        value = rubric_catalog(lab); extra['rubrics'] = value; view = 'measurement'
        summary = 'Read eight adapted unvalidated rubric dimensions and a bounded saved-rubric catalog; no inference or opportunity scoring ran.'
    elif name == 'save_rubric':
        from .behavior_rubrics import save_rubric
        value = save_rubric(lab, raw(args)); context = {'rubric_ref': value['rubric_ref']}; view = 'measurement'
        summary = 'Saved the exact prompt-defined unvalidated rubric; no classifier inference or opportunity assessment ran.'
    elif name == 'measure_rubric':
        from .behavior_rubrics import measure_rubric
        value = measure_rubric(lab, raw(args)); context = {key: value[key] for key in ('dataset_ref', 'rubric_ref', 'measurement_ref')}; view = 'measurement'
        extra['measurement_status'] = value['status']; extra['measurement_summary'] = value['summary']
        summary = ('Local Laya was unavailable or returned an invalid record; unknown text measurements were retained with no fallback.'
            if value['status'] == 'operational_failure' else 'Recorded bounded Laya text measurements. Opportunity episodes remain not assessable and calibration is unestablished.')
    elif name == 'event_neighborhood':
        from .event_evidence_graph import build_event_evidence_neighborhood
        source = _record(lab, args['run_ref'], 'observability_run')
        graph = build_event_evidence_neighborhood(source, seed_event_id=args['event_id'], hops=args['hops'],
            max_nodes=8, max_edges=8, max_diagnostics=2)
        value = {'run_ref': args['run_ref']}; extra['event_graph'] = graph
        summary = 'Read the selected captured-event reference neighborhood. Explicit links do not establish influence, delivery or readership.'
        view = 'connect'
    else:
        mapping = {'reuse_artifact': 'reuse_artifact', 'copy_artifact': 'clone_artifact', 'edit_copy': 'update_draft',
            'create_project': 'create_project', 'create_chat': 'create_chat', 'fork_chat': 'fork_chat'}
        body = {'op': mapping[name], 'request_id': 'guide-operation-' + fingerprint(request_id)[:32], **{key: value for key, value in args.items() if value is not None}}
        if name in ('reuse_artifact', 'copy_artifact'): body['target_chat_id'] = chat_id
        if name == 'edit_copy': body['chat_id'] = chat_id
        value = mutate_workspace(lab, body)
        if value.get('chat'): extra['chat_id'] = value['chat']['id']
        if value.get('project'): extra['project_id'] = value['project']['id']
        if value.get('artifact_ref'): extra['artifact_ref'] = value['artifact_ref']
        view = 'workspace-copy' if name in ('copy_artifact', 'edit_copy') else 'projects' if name == 'create_project' else 'workspace'
        summary = {'reuse_artifact': 'Linked the exact saved artifact to this chat; no experiment was duplicated.',
            'copy_artifact': 'Created an editable draft with original provenance; it contains no new empirical outcomes or verification.',
            'edit_copy': 'Saved a new version of this chat\'s editable draft; its original source remains pinned.',
            'create_project': 'Created the requested project.', 'create_chat': 'Created the requested chat.',
            'fork_chat': 'Created a separate editable discussion branch preserving its original chat revision and exact artifact references.'}[name]
    refs = ([row['ref'] for row in value['saved']] if name == 'list_rubrics' else
            [args['run_ref']] if name == 'event_neighborhood' else _refs(value))
    for reference in refs: _record(lab, reference)
    if name not in ('list_rubrics', 'event_neighborhood'): attach_returned(lab, chat_id, value)
    return {'status': 'completed', 'tool': name, 'summary': summary, 'result_refs': refs,
        'updated_context': context, 'view': view, **extra,
        'scope': 'Operation receipt, not hidden reasoning, independent source attestation or a new mechanism claim.'}


def execute_guide_tool(lab, name, args, *, chat_id, request_id, authorized_tools, allowed_refs,
                       allowed_chat_ids=None, queue_submit=None):
    if type(name) is not str or name not in TOOLS or name not in _authorized(authorized_tools):
        raise ValueError('This operation was not explicitly authorized for the current user request')
    _identifier(request_id, 'Guide operation request ID'); validate_chat(lab, chat_id)
    chats = {chat_id}
    if allowed_chat_ids is not None:
        if type(allowed_chat_ids) not in (list, tuple, set, frozenset) or len(allowed_chat_ids) > 1000: raise ValueError('Use the bounded authenticated chat catalog')
        chats.update(_identifier(identity, 'Catalog chat ID') for identity in allowed_chat_ids)
    args = _prepare(lab, name, args, allowed_refs, chats)
    signature = fingerprint({'tool': name, 'args': args, 'chat_id': chat_id})
    with lab.store.connect() as connection:
        _tables(connection); connection.execute('BEGIN IMMEDIATE')
        previous = connection.execute('SELECT * FROM guide_tool_requests WHERE request_id=?', (request_id,)).fetchone()
        if previous:
            if previous['request_hash'] != signature: raise ValueError('A guide operation request ID was reused with different input')
            if previous['result'] is not None: return json.loads(previous['result']) | {'reused': True}
            return {'status': 'pending_or_unknown', 'tool': name, 'summary': 'This exact operation already started; inspect its activity. It will not be repeated automatically.', 'result_refs': [], 'updated_context': {}, 'view': None, 'reused': True}
        timestamp = now()
        connection.execute('INSERT INTO guide_tool_requests VALUES(?,?,?,?,?,?,?,?)', (request_id, chat_id, name, signature, 'started', None, timestamp, timestamp))
        _event(connection, request_id, chat_id, name, 'started', 'Starting ' + name.replace('_', ' ') + '.', [])
    try:
        result = _perform(for_chat(lab, chat_id), name, args, chat_id, request_id, queue_submit)
    except Exception as error:
        result = {'status': 'failed', 'tool': name, 'summary': 'The operation failed; partial jobs and saved artifacts remain available. It was not retried.',
            'error_type': type(error).__name__, 'error': clean(str(error))[:500], 'result_refs': [], 'updated_context': {}, 'view': None}
    with lab.store.connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        event = _event(connection, request_id, chat_id, name, result['status'], result['summary'], result['result_refs'])
        result['event_id'] = event['id']; result['reused'] = False
        connection.execute('UPDATE guide_tool_requests SET status=?,result=?,updated=? WHERE request_id=?',
            (result['status'], json.dumps(result, ensure_ascii=False, allow_nan=False), now(), request_id))
    return result


def guide_activity(lab, chat_id):
    validate_chat(lab, chat_id)
    with lab.store.connect() as connection:
        exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='guide_tool_events'").fetchone()
        if not exists: return {'chat_id': chat_id, 'events': [], 'truncated': False, 'scope': 'Actual recorded guide operations; not hidden model reasoning.'}
        # SQLite insertion order is the recorded operation order. Wall-clock
        # ties or corrections must not place a completion before its start.
        rows = connection.execute('SELECT * FROM guide_tool_events WHERE chat_id=? ORDER BY rowid DESC LIMIT 41', (chat_id,)).fetchall()
    return {'chat_id': chat_id, 'events': [{key: row[key] for key in ('id', 'request_id', 'tool', 'phase', 'summary', 'created')} |
        {'result_refs': json.loads(row['result_refs'])} for row in reversed(rows[:40])], 'truncated': len(rows) > 40,
        'scope': 'Actual recorded guide operations; started is invocation, not success or hidden model reasoning.'}


def record_guide_activity(lab, *, chat_id, request_id, tool='read_chat_context', phase, summary, result_refs=None):
    """Log an actual bounded read invocation from the harness, not a model note.

    This trusted helper has no HTTP mutation route. The final read receipt still
    carries its exact chat revision/hash; the activity feed is an operation log.
    """
    validate_chat(lab, chat_id); _identifier(request_id, 'Read operation request ID')
    if tool != 'read_chat_context' or type(tool) is not str: raise ValueError('Only the actual chat-read tool uses this activity helper')
    if type(phase) is not str or phase not in ('started', 'completed', 'failed'): raise ValueError('Unsupported actual read phase')
    _text(summary, 240, 'Read activity summary')
    references = [] if result_refs is None else result_refs
    if type(references) is not list or len(references) > 16: raise ValueError('Use a bounded read artifact list')
    references = [_ref(reference) for reference in references]
    for reference in references: _record(lab, reference)
    identity = 'guide-event-' + fingerprint({'request': request_id, 'phase': phase})[:24]
    with lab.store.connect() as connection:
        _tables(connection); connection.execute('BEGIN IMMEDIATE')
        old = connection.execute('SELECT * FROM guide_tool_events WHERE id=?', (identity,)).fetchone()
        if old:
            if (old['chat_id'] != chat_id or old['tool'] != tool or old['summary'] != clean(summary) or
                    json.loads(old['result_refs']) != references):
                raise ValueError('A read activity ID was reused with different evidence')
            return {key: old[key] for key in ('id', 'request_id', 'tool', 'phase', 'summary', 'created')} | {'result_refs': references}
        if phase != 'started':
            beginning = connection.execute('SELECT * FROM guide_tool_events WHERE request_id=? AND phase=?', (request_id, 'started')).fetchone()
            if beginning is None or beginning['chat_id'] != chat_id or beginning['tool'] != tool:
                raise ValueError('A terminal read activity requires its actual recorded invocation')
            if connection.execute("SELECT 1 FROM guide_tool_events WHERE request_id=? AND phase IN ('completed','failed')", (request_id,)).fetchone():
                raise ValueError('An actual read invocation cannot have conflicting terminal phases')
        return _event(connection, request_id, chat_id, tool, phase, summary, references)
