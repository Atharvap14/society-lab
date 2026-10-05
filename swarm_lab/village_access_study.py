"""Source-pinned Village document-access studies; no generic-world substitution.

Fresh LLM teams act through the executable proxy tools. Historical chat reports
motivate the experiment, but never stand in for original Google state or outcomes.
"""
from __future__ import annotations
import copy
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import re
from statistics import mean
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from .guided_study import _record, _parse, _ref, _text, _int
from .store import fingerprint, now, clean

FAMILY = 'village_document_access_repair'
RESULT_KIND = 'village_access_experiment'
PRIMARY = 'verified_usable_project'
ARMS = ('neutral_note', 'canonical_check')


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(clean(value), indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def _grounding(lab, reference):
    dataset = _record(lab, reference, 'dataset')
    messages = dataset['payload'].get('messages', [])
    if type(messages) is not list or not messages:
        raise ValueError('Document-access research requires actual source messages')
    packet_path = lab.settings.runtime / 'village-access-grounding' / 'grounding-v1.json'
    packet = json.loads(packet_path.read_text(encoding='utf-8')) if packet_path.is_file() else None
    if packet and packet.get('source_ref') != reference:
        packet = None
    if packet is None:
        # A new checkout can ground the same capabilities in its own exact logs.
        # This selects reports for review; the live builder must approve fit.
        matches = [m for m in messages if re.search(r'404|page not found|permission|mistyp|incognito|sharing', m.get('content', ''), re.I)
                   and re.search(r'doc|sheet|form|url|drive', m.get('content', ''), re.I)]
        if len(matches) < 3:
            raise ValueError('No sufficient document-access incidents in this source; another environment is required')
        chosen = [matches[i] for i in sorted({round(i * (len(matches)-1) / min(23,len(matches)-1)) for i in range(min(24,len(matches)))})]
        packet = {'schema_version': 'village_access_grounding_v1', 'source_ref': reference,
            'evidence': [{'message_id': m['id'], 'text': m['content'], 'agent_name': m.get('agent_name'),
                'timestamp': m.get('timestamp'), 'content_hash': m.get('content_hash'), 'source': m.get('source'),
                'text_sha256': hashlib.sha256(m['content'].encode()).hexdigest(), 'claim_kind': 'source_chat_report'} for m in chosen],
            'incidents': [{'id': 'source-access-reports', 'name': 'Document-access reports to review',
                'evidence_ids': [m['id'] for m in chosen], 'observed_reports': ['Selected exact messages contain document-access reports.'],
                'mechanisms_needed': ['document identity', 'ACL', 'browser principal', 'copy lineage'],
                'rival_explanations': ['Reference error', 'Permissions', 'Session state', 'Unobserved service failure']}],
            'hypothesis': {'statement': 'Exact-reference and principal checks may change how teams respond to ambiguous document failures.',
                'source_evidence_ids': [m['id'] for m in chosen], 'alternative_explanations': ['Actual service failure', 'Reporting error']},
            'fidelity': {'represented': ['Identity, permissions, sessions and document copies'],
                'approximated': ['Browser and document-service tools'], 'omitted': ['Original model policies and Google backend'], 'historical_equivalence': False}}
    if packet.get('schema_version') != 'village_access_grounding_v1' or not 3 <= len(packet.get('evidence', [])) <= 64:
        raise ValueError('Use a bounded source-grounded incident packet')
    indexed = {m['id']: m for m in messages}
    seen = set()
    for evidence in packet['evidence']:
        identity = evidence.get('message_id'); m = indexed.get(identity)
        if m is None or identity in seen:
            raise ValueError('Incident evidence must identify distinct exact source messages')
        seen.add(identity)
        for key, source_key in [('text','content'), ('agent_name','agent_name'), ('timestamp','timestamp'), ('content_hash','content_hash'), ('source','source')]:
            if evidence.get(key) != m.get(source_key):
                raise ValueError('Incident evidence differs from its exact source: ' + key)
        if evidence.get('text_sha256') != hashlib.sha256(m['content'].encode()).hexdigest():
            raise ValueError('Incident excerpt fingerprint differs')
    for incident in packet.get('incidents', []):
        if not set(incident.get('evidence_ids', [])) <= seen:
            raise ValueError('An incident cites evidence absent from its grounded packet')
    packet = copy.deepcopy(packet)
    packet['source_refs'] = {'dataset_ref': reference}
    packet['historical_ground_truth'] = 'Chat reports only; no verified original browser, ACL, Google document or delivery state.'
    packet['status'] = 'source_reports_grounded_not_causal'
    return dataset, packet


def create_plan(lab, raw):
    body = _parse(raw, ('dataset_ref','behavior_ref','question','control_text','treatment_text','trials_per_arm','seed','max_rounds'))
    dataset, incident = _grounding(lab, body['dataset_ref'])
    behavior = None
    if body['behavior_ref'] is not None:
        behavior = _record(lab, body['behavior_ref'], 'behavior')
        if behavior['payload'].get('source_refs', {}).get('dataset') != body['dataset_ref']:
            raise ValueError('The behavior belongs to a different source')
    question = _text(body['question'], 'Source-derived question')
    control = _text(body['control_text'], 'Neutral context')
    treatment = _text(body['treatment_text'], 'Intervention context')
    if control == treatment or len(control.split()) != len(treatment.split()):
        raise ValueError('Use distinct control and intervention notes with equal word counts')
    trials = _int(body['trials_per_arm'], 2, 8, 'Matched world pairs')
    rounds = _int(body['max_rounds'], 6, 10, 'Rounds')
    seed = _int(body['seed'], 0, 2**53-1, 'Assignment seed')
    incident_record = lab.store.put('village_incident', incident)
    payload = {'schema_version':'village-access-plan-v1','status':'source_linked_pending_world_review',
        'family':FAMILY,'objective':PRIMARY,'question':question,'source_ref':None,
        'source_refs':{'dataset_ref':_ref(dataset),'incident_ref':_ref(incident_record),
            **({'behavior_ref':_ref(behavior)} if behavior else {})},
        'grounding_ref':_ref(incident_record),'hypothesis':{'statement':question,
            'source_evidence_ids':incident['hypothesis']['source_evidence_ids'],
            'alternative_explanations':incident['hypothesis'].get('alternative_explanations',[])},
        'control_text':control,'treatment_text':treatment,'note_length_words':{'control':len(control.split()),'intervention':len(treatment.split())},
        'trials_per_arm':trials,'seed':seed,'max_rounds':rounds,'primary_unit':'whole_team',
        'conditions':list(ARMS),'subject_mode':'live','created_at':now(),
        'design':'Matched initial worlds; fresh independent teams; random arm execution order within each pair.',
        'limitations':['Historical causes remain unknown.','Original model policies and hidden contexts are not reproduced.',
            'The contrast tests the context-note package; secondary process changes do not identify mediation.']}
    record = lab.store.put('guided_plan', payload)
    return {'plan_ref':_ref(record),'incident_ref':_ref(incident_record),'dataset_ref':_ref(dataset),'plan':payload,'paid_calls':0}


def _codes():
    root = Path(__file__).parent
    return {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in
        ('village_access_environment.py','village_access_study.py','harness.py','guided_study.py','store.py')}


def _canonical(value):
    """Finite JSON identity; Python's bool/int/float equality is not evidence identity."""
    def check(item, depth=0):
        if depth > 40: raise ValueError('Evidence JSON is too deeply nested')
        if item is None or type(item) in (bool, str): return
        if type(item) in (int, float):
            if not math.isfinite(item): raise ValueError('Finite evidence numbers required')
            return
        if type(item) is list:
            for child in item: check(child, depth+1)
            return
        if type(item) is dict and all(type(k) is str for k in item):
            for child in item.values(): check(child, depth+1)
            return
        raise ValueError('Ordinary JSON evidence required')
    check(value)
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def _same(a, b): return _canonical(a) == _canonical(b)


def _validate_protocol(protocol, *, check_code=True):
    from .village_access_environment import validate_village_access_spec, _ref as validate_ref
    _canonical(protocol)
    if protocol.get('family') != FAMILY or protocol.get('protocol_hash') != fingerprint({k:v for k,v in protocol.items() if k!='protocol_hash'}):
        raise ValueError('Frozen access protocol changed')
    validate_village_access_spec(protocol['environment'])
    if not _same(protocol.get('outcome_contract'),_outcome_contract(protocol['environment'])):
        raise ValueError('Registered operational outcome contract differs')
    design=protocol['design']
    _int(design['trials_per_arm'],2,8,'Matched world pairs')
    _int(design['seed'],0,2**53-1,'Assignment seed')
    _int(design['max_rounds'],6,10,'Rounds')
    if (set(design)!={'trials_per_arm','seed','unit','paired_worlds','max_rounds'} or
        design['unit']!='whole_team' or design['paired_worlds'] is not True or
        not _same(design['max_rounds'],protocol['environment']['max_rounds']) or
        protocol['primary_outcome']!=PRIMARY or protocol['schema_version']!='village-access-protocol-v1' or
        protocol.get('study_scope')!='exploratory_feasibility'):
        raise ValueError('Unsupported registered assignment or outcome design')
    if set(protocol['notes'])!=set(ARMS): raise ValueError('Both registered notes are required')
    notes=[_text(protocol['notes'][a],'Assigned note') for a in ARMS]
    if notes[0]==notes[1] or len(notes[0].split())!=len(notes[1].split()):
        raise ValueError('Assigned notes must be distinct and word-matched')
    sources=protocol['source_refs']
    if set(sources) not in ({'dataset_ref','incident_ref'},{'dataset_ref','incident_ref','behavior_ref'}):
        raise ValueError('Registered source fields differ')
    for reference in [protocol['plan_ref'],*sources.values()]: validate_ref(reference)
    grounding=protocol['grounding']; world=protocol['environment']['source_grounding']
    if (not _same(grounding['source_ref'],sources['dataset_ref']) or
        not _same(grounding['incident_ref'],sources['incident_ref']) or
        not _same(world['dataset_ref'],sources['dataset_ref']) or
        not set(world['message_ids'])<=set(grounding['evidence_ids'])):
        raise ValueError('Registered historical sources and world grounding disagree')
    backend=protocol['subject_backend']
    expected={'harness':'responses','model':backend.get('model'),'max_output_tokens':600,
        'temperature':'provider_default','sampling_seed':'not_set'}
    if not _same(backend,expected) or type(backend['model']) is not str or not 1<=len(backend['model'])<=200:
        raise ValueError('Unsupported frozen subject backend')
    if check_code and protocol.get('implementation_hashes') != _codes():
        raise ValueError('The executable implementation changed after registration; create a new study')


def validate_saved_world(lab, simulator):
    p = simulator['payload']; plan = _record(lab,p['plan_ref'],'guided_plan')
    registration = _record(lab,p['protocol_ref'],'protocol'); protocol = registration['payload']['protocol']
    _validate_protocol(protocol)
    if (p.get('status')!='ready' or p.get('family')!=FAMILY or
        p.get('builder_proposal',{}).get('fit')!='supported_with_limits' or
        p.get('causal_review',{}).get('decision') not in ('approve_with_limits','approve_exploratory') or
        plan['payload'].get('family') != FAMILY or registration['payload'].get('frozen_hash') != fingerprint(protocol)
        or protocol['plan_ref'] != _ref(plan) or p['environment'] != protocol['environment']
        or p.get('source_refs') != protocol['source_refs'] or protocol['source_refs'] != plan['payload']['source_refs']
        or protocol['question'] != plan['payload']['question']
        or protocol['notes'] != {'neutral_note':plan['payload']['control_text'],'canonical_check':plan['payload']['treatment_text']}
        or protocol['subject_backend']['model'] != lab.settings.model):
        raise ValueError('Access world, plan, source and registration must agree exactly')
    if (not _same(p['environment'],protocol['environment']) or
        not _same(p['source_refs'],protocol['source_refs']) or
        not _same(protocol['source_refs'],plan['payload']['source_refs'])):
        raise ValueError('Access world and source evidence types must agree exactly')
    _source_plan(lab,plan['payload'])
    return plan, registration


def _source_plan(lab, payload):
    dataset=_record(lab,payload['source_refs']['dataset_ref'],'dataset')
    incident=_record(lab,payload['grounding_ref'],'village_incident')
    packet=incident['payload']
    if (not _same(payload['grounding_ref'],payload['source_refs']['incident_ref']) or
        not _same(packet.get('source_ref'),_ref(dataset)) or
        not _same(packet.get('source_refs'),{'dataset_ref':_ref(dataset)})):
        raise ValueError('Plan and incident belong to different exact sources')
    indexed={m['id']:m for m in dataset['payload']['messages']};seen=set()
    if len(indexed)!=len(dataset['payload']['messages']):raise ValueError('Ambiguous source message IDs')
    for evidence in packet['evidence']:
        identity=evidence.get('message_id');message=indexed.get(identity)
        if message is None or identity in seen:raise ValueError('Grounded incident has missing or ambiguous evidence')
        seen.add(identity)
        for key,source in [('text','content'),('agent_name','agent_name'),('timestamp','timestamp'),('content_hash','content_hash'),('source','source')]:
            if not _same(evidence.get(key),message.get(source)):raise ValueError('Stored incident evidence differs from exact source')
        if evidence.get('text_sha256')!=hashlib.sha256(message['content'].encode()).hexdigest():
            raise ValueError('Stored incident excerpt fingerprint differs')
    if 'behavior_ref' in payload['source_refs']:
        behavior=_record(lab,payload['source_refs']['behavior_ref'],'behavior')
        if not _same(behavior['payload'].get('source_refs',{}).get('dataset'),_ref(dataset)):
            raise ValueError('Behavior belongs to a different exact source')
    return dataset,incident


def _outcome_contract(spec):
    return {'world':'NEW controlled executable proxy world; historical reports only motivate its mechanics',
        'unit':'whole fresh six-agent team','horizon_team_decisions':len(spec['agents'])*spec['max_rounds'],
        'primary_name':PRIMARY,'primary_type':'binary integer 0 or 1',
        'primary_rule':'At the final action budget, ALL FOUR ORIGINAL documents have exactly required content; each assigned auditor/integrator current browser profile is authorized; and each checker has executed a successful open receipt for that original final version. New copies do not replace originals.',
        'independent_checks':spec['task']['independent_checkers'],
        'oracle_usable_project':'State-only correct original content plus checker current-profile authorization; separate from the executed-open primary.',
        'inspection_coverage':'Final-version content-return receipts, separate secondary description; not comprehension or mediation.',
        'avoidable_recreations':'Number of new copy IDs created while the durable original persisted, measured from code genealogy; no motive or historical necessity inferred.',
        'private_context':'Exact note text is inserted into each first and subsequent recorded subject request; construction and provider invocation are distinct from attention, reading, or uptake.',
        'causal_scope':'Exploratory matched-pair randomized whole-team assigned-note PACKAGE contrast in this new world/model, not historical causal identification. Original URL, ACL and session states are unknown and are not required as proxy outcome receipts. Source-to-mechanics fit may still be rejected.',
        'limits':['Two pairs have minimum attainable two-sided exact sign-flip p=0.5.','No historical mechanism identification, mediation or original policy reproduction.','Equal words do not imply equivalent semantics or attentional disruption.']}


def create_simulator(lab, raw):
    from .village_access_environment import create_village_access_spec, VillageAccessEnvironment, ACTION_SCHEMA
    from .research import ResearchAgents, object_schema, TEXT, TEXTS
    plan = _record(lab,_parse(raw,('plan_ref',))['plan_ref'],'guided_plan'); p = plan['payload']
    if p.get('family') != FAMILY:
        raise ValueError('A source-linked document-access plan is required')
    dataset,incident = _source_plan(lab,p)
    identity = 'guided_simulator-access-'+plan['hash'][:16]
    try:
        saved = lab.store.get(identity); validate_saved_world(lab,saved)
        return {'simulator_ref':_ref(saved),'plan_ref':_ref(plan),'simulator':saved['payload'],'paid_calls':0}
    except KeyError:
        pass
    job = 'access-build-'+uuid.uuid4().hex[:12]; before=lab.store.usage()['calls']
    with lab.store.connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS village_constructions(plan_hash TEXT PRIMARY KEY,job_id TEXT,status TEXT)')
        c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT 1 FROM village_constructions WHERE plan_hash=?',(plan['hash'],)).fetchone():
            raise ValueError('This exact plan already has a construction request; inspect its retained attempt')
        c.execute('INSERT INTO village_constructions VALUES(?,?,?)',(plan['hash'],job,'running'))
    lab.store.job(job,'running',{'action':'village_access_world_builder','plan_ref':_ref(plan)})
    attempt=None
    try:
        evidence = incident['payload']['evidence']; indexed={m['id']:m for m in dataset['payload']['messages']}
        selected=[indexed[e['message_id']] for e in evidence[::max(1,len(evidence)//12)]][:12]
        grounding={'dataset_ref':p['source_refs']['dataset_ref'], 'message_ids':[m['id'] for m in selected],
            'evidence_status':'reported_chat_only_original_tool_state_and_audience_unknown',
            'motivating_mechanics':['Copied and typed URL identities can differ.', 'The same 404 report may reflect identity, permissions or browser principal.',
                'New copies have distinct identities and access state; successful independent access is a separate receipt.']}
        spec = create_village_access_spec(max_rounds=p['max_rounds'],source_grounding=grounding)
        outcome_contract=_outcome_contract(spec)
        env = VillageAccessEnvironment(spec,p['seed'])
        before_state = env.snapshot(); again = VillageAccessEnvironment(spec,p['seed']).snapshot()
        if before_state != again:
            raise ValueError('Independent equal-seed world reset differs')
        from .village_access_environment import village_access_subject_request
        before_requests=[village_access_subject_request(env,agent) for agent in env.agent_ids]
        if any(set(request) - {'role','system','context','observation','action_schema'} for request in before_requests):
            raise ValueError('Unexpected subject request fields at construction')
        worker=ResearchAgents(lab.settings,lab.store,lab.research_harness('responses'))
        built_schema=object_schema({'fit':{'type':'string','enum':['supported_with_limits','unsupported']},'evidence_ids':TEXTS,
            'mechanism_mapping':TEXT,'source_hypothesis_fit':TEXT,'omitted_capabilities':TEXTS,'falsifiers':TEXTS})
        built=worker.run('environment-builder',{'task':'Review this executable document-access world against the exact source incidents and proposed question. Approve only represented mechanisms; decline unrelated hypotheses. Identify source evidence for URL drift, ACL/session differences and copies. Do not claim Google or original policy equivalence. Do not confuse reported historical tools with verified original state.',
            'question':p['question'],'source_incidents':incident['payload']['incidents'], 'evidence':selected,
            'world_rules':spec,'tool_action_contract':ACTION_SCHEMA,'outcome_contract':outcome_contract,
            'primary_outcome':PRIMARY,'output_schema':built_schema},built_schema,dataset['payload'],{'candidates':[]},job)
        attempt_payload={'schema_version':'village-access-construction-attempt-v1','status':'builder_returned',
            'plan_ref':_ref(plan),'source_refs':p['source_refs'],'environment':spec,
            'outcome_contract':outcome_contract,'builder_proposal':built,'causal_review':None,
            'evidence_scope':'Bounded supplied reports and fresh proxy mechanics; no original browser state attestation.',
            'job_id':job,'created_at':now()}
        attempt=lab.store.put('village_access_construction_attempt',attempt_payload,'village-access-construction-'+job)
        if built['fit'] != 'supported_with_limits' or not built['evidence_ids']:
            raise ValueError('Environment builder declined this source-to-world fit')
        review_schema=object_schema({'decision':{'type':'string','enum':['approve_exploratory','approve_with_limits','requires_changes']},
            'hypothesis':TEXT,'evidence_ids':TEXTS,'identification_assumptions':TEXTS,'confound_checks':TEXTS,'falsifiers':TEXTS,'transport_limitations':TEXTS})
        review=worker.run('causal-methodologist',{'task':'Review permission for a NONCONFIRMATORY EXPLORATORY FEASIBILITY PILOT before any outcome calls, not endorsement of a stable treatment effect or a confirmatory study. approve_exploratory means mechanics, operational scoring and bounded assigned-policy design suffice to try this pilot while uncertainty and negative/null outcomes remain valid. Small sample size, wide uncertainty and absent historical transport must be reported as limits; they are not alone implementation blockers for this explicitly nonconfirmatory purpose. Decline actual source-to-mechanics/question mismatch, confounded assignment, unsupported tools or outcome problems; approval is never required. This question tests NEW controlled proxy-world teams, not an effect identifiable from historical chat. Source reports motivate mechanics only: original receipts and causes remain unknown. Check the legal action contract and operational code oracle supplied here. The whole-team note PACKAGE comparison uses matched identical seeded initial truth/ACL/reference/profile/scheduler, fresh independent model teams and random arm execution order. All arms have identical tools and budgets. Historical receipts are not needed to score fresh proxy transitions. Reading/uptake is unobserved even though note text is inserted into each request. Equal words do not equate semantics. No historical attribution, mediation or strong causal claim is sought. Do not approve merely because a proxy executes.',
            'plan':p,'world_rules':spec,'tool_action_contract':ACTION_SCHEMA,'outcome_contract':outcome_contract,
            'builder':built,'evidence':selected,'output_schema':review_schema},review_schema,dataset['payload'],{'candidates':[]},job)
        attempt_payload.update(status='reviewed_'+review['decision'],causal_review=review)
        attempt=lab.store.put('village_access_construction_attempt',attempt_payload,attempt['id'])
        if review['decision'] not in ('approve_exploratory','approve_with_limits'):
            raise ValueError('Causal reviewer requires a revised source-linked study')
        fidelity=copy.deepcopy(incident['payload']['fidelity'])
        fidelity['historical_equivalence']=False
        fidelity.setdefault('omitted',[]).extend(['Original Claude/Gemini/Grok/o3 policies: all fresh subjects use '+lab.settings.model,
            'Original Google backend, hidden browser cookies, original private thoughts and message exposure'])
        protocol={'schema_version':'village-access-protocol-v1','family':FAMILY,'study_scope':'exploratory_feasibility','question':p['question'],
            'plan_ref':_ref(plan),'source_refs':p['source_refs'],'hypothesis':p['hypothesis'],'fidelity':fidelity,
            'grounding':{'source_ref':p['source_refs']['dataset_ref'],'evidence_ids':[e['message_id'] for e in evidence],
                'incident_ref':p['source_refs']['incident_ref'],'evidence_status':grounding['evidence_status']},
            'environment':spec,'notes':{'neutral_note':p['control_text'],'canonical_check':p['treatment_text']},
            'design':{'trials_per_arm':p['trials_per_arm'],'seed':p['seed'],'unit':'whole_team','paired_worlds':True,'max_rounds':p['max_rounds']},
            'primary_outcome':PRIMARY,'outcome_contract':outcome_contract,'secondary_outcomes':['avoidable_recreations','access_failures','permission_failures','reference_failures','completed_tasks'],
            'intervention':{'timing':'Before each agent first action','recipient':'Every member of the assigned whole team','channel':'Visible private context note','hidden_state_edit':False},
            'subject_backend':{'harness':'responses','model':lab.settings.model,'max_output_tokens':600,'temperature':'provider_default','sampling_seed':'not_set'},
            'subject_system':'Work on the project using only your observation and legal proxy tools. Decide one action at a time. Reports do not by themselves change document state. Do not reveal your private context. Return one legal JSON action.',
            'inference':'Paired team differences; exact sign-flip test of sharp null; distribution-free Hoeffding interval across independent bounded pair differences. Small pilot, no historical causal transport.',
            'implementation_hashes':_codes(),'registered_at':now()}
        protocol['protocol_hash']=fingerprint(protocol)
        registration=lab.store.put('protocol',{'protocol':protocol,'frozen_hash':fingerprint(protocol),'status':'registered','agent_mode':'live','guided_plan_ref':_ref(plan),'source_refs':p['source_refs']})
        payload={'schema_version':'village-access-simulator-v1','status':'ready','family':FAMILY,'study_scope':'exploratory_feasibility','name':'AI Village document-access investigation',
            'plan_ref':_ref(plan),'protocol_ref':_ref(registration),'source_refs':p['source_refs'],'environment':spec,
            'hypothesis':p['hypothesis'],'fidelity':fidelity,'builder_proposal':built,'causal_review':review,
            'boundary_checks':{'passed':True,'equal_seed_reset':True,'bounded_subject_request_fields':True,
                'subject_context':'Requests use the tested observation API; private assignment and privileged snapshot/evaluate are not subject tools. Every executed request is independently replayed.'},
            'subject_mode':'live','model':lab.settings.model,'harness':'responses','teams':p['trials_per_arm']*2,
            'max_actions':p['trials_per_arm']*2*len(env.agent_ids)*p['max_rounds'],
            'maximum_subject_calls':p['trials_per_arm']*2*len(env.agent_ids)*p['max_rounds'],
            'limitations':p['limitations'],'paid_calls':lab.store.usage()['calls']-before}
        saved=lab.store.put('guided_simulator',payload,identity)
        with lab.store.connect() as c:c.execute('UPDATE village_constructions SET status=? WHERE plan_hash=?',('completed',plan['hash']))
        lab.store.job(job,'completed',{'action':'village_access_world_builder','result_ids':[saved['id'],registration['id']]})
        return {'simulator_ref':_ref(saved),'plan_ref':_ref(plan),'simulator':payload,'paid_calls':payload['paid_calls']}
    except Exception as exc:
        with lab.store.connect() as c:c.execute('UPDATE village_constructions SET status=? WHERE plan_hash=?',('failed',plan['hash']))
        lab.store.job(job,'failed',{'action':'village_access_world_builder','error_type':type(exc).__name__,'error':clean(str(exc))[:800],
            **({'attempt_ref':_ref(attempt)} if attempt is not None else {})})
        raise


def _assignments(protocol):
    rng=random.Random(protocol['design']['seed']); rows=[]
    for pair in range(protocol['design']['trials_per_arm']):
        seed=rng.randrange(2**53); order=list(ARMS);rng.shuffle(order)
        for arm in order: rows.append({'run_id':f'pair-{pair+1}-{arm}','pair_id':pair+1,'arm':arm,'environment_seed':seed})
    return rows


def _analysis(runs, protocol):
    n=protocol['design']['trials_per_arm']
    groups={a:[r for r in runs if r['arm']==a] for a in ARMS}
    if any(len(v)!=n for v in groups.values()):raise ValueError('All registered teams must complete before effects are estimated')
    if any(type(r['outcomes'].get(PRIMARY)) is not int or r['outcomes'][PRIMARY] not in (0,1) for r in runs):
        raise ValueError('The primary oracle must return explicit binary outcomes')
    diffs=[]
    for pair in range(1,n+1):
        d={r['arm']:r for r in runs if r['pair_id']==pair}
        if set(d)!=set(ARMS) or d[ARMS[0]]['environment_seed']!=d[ARMS[1]]['environment_seed']:
            raise ValueError('Pair assignments disagree')
        diffs.append(d['canonical_check']['outcomes'][PRIMARY]-d['neutral_note']['outcomes'][PRIMARY])
    difference=mean(diffs);radius=math.sqrt(2*math.log(40)/n)
    p=sum(abs(mean([v*s for v,s in zip(diffs,signs)]))+1e-12>=abs(difference)
          for signs in itertools.product((-1,1),repeat=n))/(2**n)
    measures=[PRIMARY,'avoidable_recreations','access_failures','permission_failures','reference_failures','completed_tasks']
    return {'status':'descriptive_paired_contrast','study_scope':'exploratory_feasibility',
        'arms':{a:{'n':n,'success':mean([r['outcomes'][PRIMARY] for r in rows]),
        **{m:mean([r['outcomes'][m] for r in rows]) for m in measures}} for a,rows in groups.items()},
        'primary_effect':{'mean_treatment':mean([r['outcomes'][PRIMARY] for r in groups['canonical_check']]),
            'mean_control':mean([r['outcomes'][PRIMARY] for r in groups['neutral_note']]),'difference':difference,
            'ci95':[max(-1,difference-radius),min(1,difference+radius)],'interval_method':'bounded_pair_Hoeffding_95',
            'p_two_sided':p,'test_method':'exact_paired_sign_flip_sharp_null','test_samples':2**n,'unit':'whole_team','n_pairs':n,'pair_differences':diffs},
        'warnings':['The small pilot estimates only this registered proxy world and model.','Historical state and original policies remain unobserved.',
            'Secondary outcomes are descriptive; no mediation or broad novelty claim.']}


def _run_team(protocol, assignment, runner, job):
    from .village_access_environment import VillageAccessEnvironment, village_access_subject_request
    env=None; initial=None; turns=[]; request=None
    try:
        env=VillageAccessEnvironment(protocol['environment'],assignment['environment_seed']);initial=env.snapshot()
        for agent in env.agent_ids:env.inject_context(agent,protocol['notes'][assignment['arm']])
        while not env.terminal:
            agent=env.next_agent;request=village_access_subject_request(env,agent)
            request['system']=protocol['subject_system']+'\n'+request.get('system','')
            request['_job_id']=job+'-'+assignment['run_id']
            action=runner(copy.deepcopy(request));receipt=env.step(agent,action)
            # The environment bounds/sanitizes invalid output. Retain the actual
            # executed value, never an unpersistable NaN or arbitrary raw object.
            retained=copy.deepcopy(env.events[-1]['action'])
            turns.append({'step':len(turns),'agent_id':agent,'request':request,'action':retained,'tool_result':receipt})
        return {**assignment,'status':'complete','initial_state':initial,'final_state':env.snapshot(),'turns':turns,
            'context_insertion_delivered':True,'outcomes':env.evaluate()}
    except Exception as exc:
        return {**assignment,'status':'incomplete_infrastructure_failure','initial_state':initial,
            'partial_state':env.snapshot() if env is not None else None,'turns':turns,
            'context_insertion_delivered':bool(env is not None and len(env.private_context)==len(env.agent_ids)),
            'failed_request':request,'failure':{'type':type(exc).__name__,'error':clean(str(exc))[:800]}}


def verify_replay(report, *, expected_source_refs=None):
    """Reconstruct code state, not provider consumption or historical Google state.

    A host may additionally bind source_refs to its authenticated exact objects.
    Current implementation hashes are required; no archived-code execution occurs.
    """
    from .village_access_environment import VillageAccessEnvironment, village_access_subject_request, _ref as validate_ref
    _canonical(report)
    if report.get('schema_version')!='village-access-result-v1' or report.get('status') not in ('complete','incomplete_infrastructure_failure'):
        raise ValueError('An explicit completed or retained incomplete report is required')
    protocol=report['protocol'];_validate_protocol(protocol);checks=[]
    assignments=_assignments(protocol)
    if not _same(report.get('assignments'),assignments):raise ValueError('Registered assignment grid differs')
    sources=report.get('source_refs')
    if type(sources) is not dict or set(sources)!=set(protocol['source_refs'])|{'plan_ref','simulator_ref'}:
        raise ValueError('Report source fields differ')
    for reference in sources.values():validate_ref(reference)
    if (not _same({k:sources[k] for k in protocol['source_refs']},protocol['source_refs']) or
        not _same(sources['plan_ref'],protocol['plan_ref']) or
        expected_source_refs is not None and not _same(sources,expected_source_refs)):
        raise ValueError('Report sources differ from frozen or host-authenticated references')
    if (report.get('protocol_hash')!=protocol['protocol_hash'] or
        report.get('model')!=protocol['subject_backend']['model'] or
        not _same(report.get('backend'),protocol['subject_backend']) or
        not _same(report.get('hypothesis'),protocol['hypothesis']) or
        not _same(report.get('fidelity'),protocol['fidelity']) or
        report.get('agent_mode') not in ('live','provided_runner')):
        raise ValueError('Report backend or protocol metadata differs')
    runs=report.get('runs')
    if type(runs) is not list or len(runs)!=len(assignments):raise ValueError('Retain the entire assigned run inventory')
    complete=report['status']=='complete'; pair_failed=set()
    for assignment,run in zip(assignments,runs):
        if not _same({k:run.get(k) for k in assignment},assignment):raise ValueError('Run assignment identity differs')
        status=run.get('status'); pair=assignment['pair_id']
        if status not in ('complete','not_started','incomplete_infrastructure_failure'):
            raise ValueError('Unknown run execution status')
        if pair in pair_failed and status!='not_started':raise ValueError('A pair executed after its infrastructure failure')
        if status=='not_started':
            if not _same(run,{**assignment,'status':'not_started','turns':[]}):
                raise ValueError('Unstarted assignments cannot contain execution evidence')
            pair_failed.add(pair)
            if complete:raise ValueError('Completed study contains an unstarted team')
            continue
        if status!='complete':pair_failed.add(pair)
        if complete and status!='complete':raise ValueError('Completed study contains incomplete teams')
        if run.get('initial_state') is None:
            if (status=='complete' or run.get('turns')!=[] or run.get('partial_state') is not None or
                run.get('failed_request') is not None or run.get('context_insertion_delivered') is not False or
                'outcomes' in run or 'final_state' in run):
                raise ValueError('Unmaterialized run has invented execution evidence')
            checks.append({'run_id':run['run_id'],'steps':0,'materialized':False});continue
        env=VillageAccessEnvironment(protocol['environment'],run['environment_seed'])
        if not _same(env.snapshot(),run['initial_state']):raise ValueError('Initial world replay differs')
        for agent in env.agent_ids:env.inject_context(agent,protocol['notes'][run['arm']])
        if run.get('context_insertion_delivered') is not True:raise ValueError('Recorded insertion receipt differs')
        if type(run.get('turns')) is not list:raise ValueError('Retained turn list required')
        for index,turn in enumerate(run['turns']):
            if type(turn.get('step')) is not int or turn['step']!=index:
                raise ValueError('Recorded turn index differs')
            if env.terminal or env.next_agent!=turn['agent_id']:raise ValueError('Recorded scheduler differs')
            request=village_access_subject_request(env,turn['agent_id'])
            request['system']=protocol['subject_system']+'\n'+request.get('system','')
            expected={k:v for k,v in turn['request'].items() if k!='_job_id'}
            if not _same(request,expected):raise ValueError('Subject observation or private context replay differs')
            result=env.step(turn['agent_id'],copy.deepcopy(turn['action']))
            if not _same(env.events[-1]['action'],turn['action']) or not _same(result,turn['tool_result']):
                raise ValueError('Recorded action or tool transition differs')
        if status=='complete':
            if not env.terminal or not _same(env.snapshot(),run['final_state']) or not _same(env.evaluate(),run['outcomes']):
                raise ValueError('Independent tool-state or outcome replay differs')
        else:
            if 'outcomes' in run or 'final_state' in run or not _same(env.snapshot(),run['partial_state']):
                raise ValueError('Incomplete team must retain partial state without a final outcome')
            if run.get('failed_request') is not None:
                if env.terminal:raise ValueError('Failure request occurs after the final decision')
                request=village_access_subject_request(env,env.next_agent)
                request['system']=protocol['subject_system']+'\n'+request.get('system','')
                recorded={k:v for k,v in run['failed_request'].items() if k!='_job_id'}
                if not _same(request,recorded):raise ValueError('Failed next request differs')
        checks.append({'run_id':run['run_id'],'steps':len(run['turns']),'passed':True,'execution_status':status})
    if complete:
        if not _same(_analysis(runs,protocol),report.get('analysis')):raise ValueError('Numerical reconstruction differs')
    elif 'analysis' in report:
        raise ValueError('Incomplete studies cannot report a completed causal estimate')
    return {'status':'passed' if complete else 'partial_trace_consistent','passed':complete,
        'quantitative_available':complete,'complete_execution':all(r['status']=='complete' for r in runs),
        'checks':checks,'analysis_recomputed':complete,'source_binding':
        'host_authenticated_exact_refs' if expected_source_refs is not None else 'protocol_and_declared_simulator_ref_only',
        'scope':'Fresh deterministic current-code replay of retained actions, observations and code outcomes; local request construction does not attest provider consumption or historical state equivalence.','paid_calls':0}


def execute_plan(lab, raw, *, runner=None, max_workers=2):
    if type(max_workers) is not int or not 1<=max_workers<=8:raise ValueError('Worker count must be an integer from 1 to 8')
    simulator=_record(lab,_parse(raw,('simulator_ref',))['simulator_ref'],'guided_simulator')
    plan,registration=validate_saved_world(lab,simulator);protocol=registration['payload']['protocol']
    with lab.store.connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS village_executions(simulator_hash TEXT PRIMARY KEY,job_id TEXT,status TEXT,result_ref TEXT)')
        c.execute('BEGIN IMMEDIATE');previous=c.execute('SELECT * FROM village_executions WHERE simulator_hash=?',(simulator['hash'],)).fetchone()
        if previous:
            if previous['status']=='completed':
                saved=_record(lab,json.loads(previous['result_ref']),'guided_result')
                return {'execution_ref':_ref(saved),**saved['payload'],'reused':True}
            raise ValueError('This exact world already has a running or failed execution; no automatic retry')
        job='village-access-'+uuid.uuid4().hex[:12]
        c.execute('INSERT INTO village_executions VALUES(?,?,?,?)',(simulator['hash'],job,'running',None))
    directory=lab.settings.runtime/'village-access-runs'/job
    assignments=_assignments(protocol)
    report={'schema_version':'village-access-result-v1','status':'running','agent_mode':'live' if runner is None else 'provided_runner',
        'model':lab.settings.model,'backend':protocol['subject_backend'],'protocol':protocol,'protocol_hash':protocol['protocol_hash'],
        'source_refs':{**protocol['source_refs'],'plan_ref':_ref(plan),'simulator_ref':_ref(simulator)},
        'hypothesis':protocol['hypothesis'],'fidelity':protocol['fidelity'],'assignments':assignments,
        'runs':[{**a,'status':'not_started','turns':[]} for a in assignments],
        'started_at':now(),'evidence_scope':'Controlled source-motivated proxy experiment, not replay of historical Google state or original model policies.'}
    before=lab.store.usage()['calls']
    lab.store.job(job,'running',{'action':'village_access_experiment','simulator_ref':_ref(simulator),'completed':0,'total':len(assignments)})
    try:
        _write(directory/'protocol.json',protocol);_write(directory/'assignment.json',assignments)
        subject=runner if runner is not None else lab.harness('responses').subject
        # Parallel pairs are independent. Each preregistered randomized arm
        # order is sequential inside its pair. Every submitted future is drained.
        def pair_run(pair):
            retained=[]; errors=[]
            for assignment in [a for a in assignments if a['pair_id']==pair]:
                run=_run_team(protocol,assignment,subject,job);retained.append(run)
                try:_write(directory/'runs'/(run['run_id']+'.json'),run)
                except Exception as exc:
                    errors.append({'type':type(exc).__name__,'error':clean(str(exc))[:800],'run_id':run['run_id'],'phase':'run_archive'})
                    break
                if run['status']!='complete':break
            return retained,errors
        archive_errors=[]
        with ThreadPoolExecutor(max_workers=min(max_workers,protocol['design']['trials_per_arm'])) as pool:
            futures=[pool.submit(pair_run,pair) for pair in range(1,protocol['design']['trials_per_arm']+1)]
            for future in as_completed(futures):
                try:retained,errors=future.result()
                except Exception as exc:
                    # Unexpected worker failure is still retained, and does not
                    # drop already submitted independent pair traces.
                    archive_errors.append({'type':type(exc).__name__,'error':clean(str(exc))[:800],'phase':'worker'})
                    continue
                archive_errors.extend(errors)
                for run in retained:
                    index=next(i for i,a in enumerate(assignments) if a['run_id']==run['run_id']);report['runs'][index]=run
                try:_write(directory/'progress.json',report)
                except Exception as exc:archive_errors.append({'type':type(exc).__name__,'error':clean(str(exc))[:800],'phase':'progress_archive'})
                lab.store.job(job,'running',{'action':'village_access_experiment','simulator_ref':_ref(simulator),
                    'completed':sum(r['status']=='complete' for r in report['runs']),'total':len(assignments)})
        failed=[r for r in report['runs'] if r['status']!='complete']
        if archive_errors:
            report['archive_failures']=archive_errors
            raise RuntimeError('Execution archive failed; retained whole assignment inventory requires review')
        if failed:raise RuntimeError('Subject infrastructure failed; partial requests, tool state and unstarted assignments retained')
        report['analysis']=_analysis(report['runs'],protocol);report['status']='complete';report['finished_at']=now()
        _write(directory/'report.json',report)
        proof=verify_replay(report,expected_source_refs=report['source_refs'])
        result=lab.store.put(RESULT_KIND,report)
        proof_record=lab.store.put('verification',{**proof,'experiment_ref':_ref(result),'source_refs':protocol['source_refs']})
        facts={'team_count':len(report['runs']),'subject_decisions':sum(len(r['turns']) for r in report['runs']),
            'primary_effect':report['analysis']['primary_effect'],'arm_counts':{a:len([r for r in report['runs'] if r['arm']==a]) for a in ARMS}}
        claims=lab.store.put('claim_audit',{'status':'passed','experiment_ref':_ref(result),'facts':facts,
            'scope':'Deterministically computed typed facts; no free-text LLM narrative is treated as verified.','paid_calls':0})
        payload={'status':'complete','agent_mode':report['agent_mode'],'family':FAMILY,'plan_ref':_ref(plan),'simulator_ref':_ref(simulator),
            'result_ref':_ref(result),'verification_ref':_ref(proof_record),'claims_ref':_ref(claims),
            'source_refs':protocol['source_refs'],'hypothesis':protocol['hypothesis'],'fidelity':protocol['fidelity'],
            'analysis':report['analysis'],'teams':len(report['runs']),'subject_decisions':facts['subject_decisions'],
            'paid_calls':lab.store.usage()['calls']-before,'job_id':job}
        saved=lab.store.put('guided_result',payload)
        with lab.store.connect() as c:c.execute('UPDATE village_executions SET status=?,result_ref=? WHERE simulator_hash=?',('completed',json.dumps(_ref(saved)),simulator['hash']))
        lab.store.job(job,'completed',{'action':'village_access_experiment','result_ids':[result['id'],saved['id'],proof_record['id'],claims['id']]})
        return {'execution_ref':_ref(saved),**payload,'reused':False}
    except Exception as exc:
        report.pop('analysis',None)
        report['status']='incomplete_infrastructure_failure';report['finished_at']=now();report['failure']={'type':type(exc).__name__,'error':clean(str(exc))[:800]}
        try:_write(directory/'partial-report.json',report)
        except Exception as archive_exc:
            report['failure_archive_error']={'type':type(archive_exc).__name__,'error':clean(str(archive_exc))[:800]}
        failure=lab.store.put('village_access_attempt',report)
        with lab.store.connect() as c:c.execute('UPDATE village_executions SET status=? WHERE simulator_hash=?',('failed',simulator['hash']))
        lab.store.job(job,'failed',{'action':'village_access_experiment','attempt_ref':_ref(failure),'error_type':type(exc).__name__})
        raise
