"""Fresh LLM owner/checker note study over one source-motivated broken reference."""
import copy
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
from statistics import mean
from concurrent.futures import ThreadPoolExecutor,as_completed
import uuid

from .guided_study import _parse,_record,_ref,_text,_int
from .store import fingerprint,clean,now
from .village_access_study import _grounding,_source_plan,_canonical,_same
from .reference_repair_environment import (ReferenceRepairEnvironment,create_reference_repair_spec,
    validate_reference_repair_spec,reference_repair_subject_request,ACTION_SCHEMA,AGENTS,PRIMARY,KIND)

FAMILY=KIND
RESULT_KIND='village_recovery_experiment'
ARMS=('neutral_note','canonical_check')


def _codes():
    root=Path(__file__).parent
    names=('reference_repair_environment.py','reference_repair_study.py','village_access_environment.py',
        'village_access_study.py','guided_study.py','store.py','harness.py')
    return {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names}


def _write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(clean(value),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');temp.replace(path)


def create_plan(lab,raw):
    body=_parse(raw,('dataset_ref','behavior_ref','question','control_text','treatment_text','trials_per_arm','seed','max_rounds'))
    source,packet=_grounding(lab,body['dataset_ref']);behavior=None
    if body['behavior_ref'] is not None:
        behavior=_record(lab,body['behavior_ref'],'behavior')
        if not _same(behavior['payload'].get('source_refs',{}).get('dataset'),_ref(source)):
            raise ValueError('Behavior and recovery question belong to different exact source logs')
    question=_text(body['question'],'Source-motivated recovery question')
    control=_text(body['control_text'],'Neutral context');active=_text(body['treatment_text'],'Intervention context')
    if control==active or len(control.split())!=len(active.split()):raise ValueError('Use distinct word-matched private notes')
    trials=_int(body['trials_per_arm'],2,8,'Matched pairs');rounds=_int(body['max_rounds'],4,10,'Two-role rounds')
    seed=_int(body['seed'],0,2**53-1,'Assignment seed')
    incident=lab.store.put('village_incident',packet)
    payload={'schema_version':'reference-repair-plan-v1','status':'source_linked_pending_world_review','family':FAMILY,
        'objective':PRIMARY,'question':question,'grounding_ref':_ref(incident),
        'source_refs':{'dataset_ref':_ref(source),'incident_ref':_ref(incident),**({'behavior_ref':_ref(behavior)} if behavior else {})},
        'control_text':control,'treatment_text':active,'trials_per_arm':trials,'max_rounds':rounds,'seed':seed,
        'note_length_words':{'control':len(control.split()),'intervention':len(active.split())},
        'primary_unit':'whole_two_role_team','conditions':list(ARMS),'subject_mode':'live',
        'hypothesis':{'statement':question,'source_evidence_ids':packet['hypothesis']['source_evidence_ids'],
            'alternative_explanations':packet['hypothesis'].get('alternative_explanations',[])},
        'study_scope':'exploratory_feasibility','created_at':now(),
        'limitations':['Historical reports motivate reference mechanics; no historical cause or original policy is identified.',
            'Only one original and two fresh roles are active. Correct content, viewer ACL and authenticated initial profiles are held fixed.',
            'The shared goal and tool semantics are clarified identically in both arms; only the matched private note differs.',
            'The note package contrast is exploratory; model and provider timing/stability assumptions remain.']}
    saved=lab.store.put('guided_plan',payload)
    return {'plan_ref':_ref(saved),'incident_ref':_ref(incident),'dataset_ref':_ref(source),'plan':payload,'paid_calls':0}


def _contract(spec):
    return {'primary_outcome':PRIMARY,'unit':'whole_two_role_team','horizon_team_actions':2*spec['max_rounds'],
        'primary_rule':'At final budget, the CURRENT ORIGINAL IRB content is correct, auditor current profile is authorized, and the AUDITOR has an executed successful open receipt for that original final version. Owner access/messages/status reports alone do not score success.',
        'secondary_scope':'Actual reference failures, canonical text queued to peer, and returned current-content inspection are descriptive process measures, not mental states or causal mediators.',
        'assignment':'Whole-team context note, identical before-first-decision boundary and tools; fresh independent teams paired on complete exogenous starting state and schedule.',
        'fidelity':'New one-document reference fault; fixed correct content/team permissions/initial principal. Source reports are motivation, not latent historical truth.',
        'inference':'Paired difference with bounded Hoeffding interval and exact sign-flip sharp-null test; minimum two-pair pilot has minimum two-sided attainable p=0.5, no confirmatory endorsement.'}


def _validate_protocol(protocol):
    from .village_access_environment import _ref as validate_ref
    _canonical(protocol)
    if (protocol.get('family')!=FAMILY or protocol.get('schema_version')!='reference-repair-protocol-v1' or
        protocol.get('study_scope')!='exploratory_feasibility' or protocol.get('primary_outcome')!=PRIMARY or
        protocol.get('protocol_hash')!=fingerprint({k:v for k,v in protocol.items() if k!='protocol_hash'})):
        raise ValueError('Frozen reference-repair protocol differs')
    validate_reference_repair_spec(protocol['environment']);design=protocol['design']
    if set(protocol['source_refs']) not in ({'dataset_ref','incident_ref'},{'dataset_ref','incident_ref','behavior_ref'}):
        raise ValueError('Registered exact source fields differ')
    for reference in [protocol['plan_ref'],*protocol['source_refs'].values()]:validate_ref(reference)
    _int(design['trials_per_arm'],2,8,'Matched pairs');_int(design['seed'],0,2**53-1,'Assignment seed')
    _int(design['max_rounds'],4,10,'Rounds')
    if not _same(design,{'trials_per_arm':design['trials_per_arm'],'seed':design['seed'],'max_rounds':protocol['environment']['max_rounds'],'unit':'whole_two_role_team','paired_worlds':True}):
        raise ValueError('Typed assignment design differs')
    if set(protocol['notes'])!=set(ARMS):raise ValueError('Two registered notes required')
    notes=[_text(protocol['notes'][a],'Context note') for a in ARMS]
    if notes[0]==notes[1] or len(notes[0].split())!=len(notes[1].split()):raise ValueError('Private notes must be word-matched')
    if not _same(protocol['outcome_contract'],_contract(protocol['environment'])):raise ValueError('Operational oracle contract differs')
    backend=protocol['subject_backend'];expected={'harness':'responses','model':backend.get('model'),'max_output_tokens':600,'temperature':'provider_default','sampling_seed':'not_set'}
    if not _same(backend,expected) or type(backend['model']) is not str:raise ValueError('Frozen model/backend differs')
    if protocol['implementation_hashes']!=_codes():raise ValueError('Current implementation differs from frozen source pins')
    world=protocol['environment']['base_environment']['source_grounding']
    grounding=protocol['grounding']
    if (not _same(world['dataset_ref'],protocol['source_refs']['dataset_ref']) or
        not _same(grounding['source_ref'],protocol['source_refs']['dataset_ref']) or
        not _same(grounding['incident_ref'],protocol['source_refs']['incident_ref']) or
        not set(world['message_ids'])<=set(grounding['evidence_ids'])):
        raise ValueError('World and protocol grounding source differ')


def validate_saved_world(lab,simulator):
    payload=simulator['payload'];plan=_record(lab,payload['plan_ref'],'guided_plan')
    registration=_record(lab,payload['protocol_ref'],'protocol');protocol=registration['payload']['protocol']
    _validate_protocol(protocol);_source_plan(lab,plan['payload'])
    if (payload.get('family')!=FAMILY or payload.get('status')!='ready' or plan['payload'].get('family')!=FAMILY or
        payload.get('causal_review',{}).get('decision') not in ('approve_exploratory','approve_with_limits') or
        payload.get('builder_proposal',{}).get('fit')!='supported_with_limits' or
        registration['payload']['frozen_hash']!=fingerprint(protocol) or protocol['subject_backend']['model']!=lab.settings.model or
        not _same(protocol['plan_ref'],_ref(plan)) or not _same(payload['environment'],protocol['environment']) or
        not _same(payload['source_refs'],protocol['source_refs']) or not _same(protocol['source_refs'],plan['payload']['source_refs']) or
        protocol['question']!=plan['payload']['question'] or
        not _same(protocol['notes'],{'neutral_note':plan['payload']['control_text'],'canonical_check':plan['payload']['treatment_text']})):
        raise ValueError('Recovery source, plan, exact world and reviewer must agree')
    return plan,registration


def create_simulator(lab,raw):
    from .research import ResearchAgents,object_schema,TEXT,TEXTS
    plan=_record(lab,_parse(raw,('plan_ref',))['plan_ref'],'guided_plan');p=plan['payload']
    if p.get('family')!=FAMILY:raise ValueError('A source-grounded one-document plan is required')
    source,incident=_source_plan(lab,p);identity='guided_simulator-recovery-'+plan['hash'][:16]
    try:
        saved=lab.store.get(identity);validate_saved_world(lab,saved)
        return {'simulator_ref':_ref(saved),'plan_ref':_ref(plan),'simulator':saved['payload'],'paid_calls':0}
    except KeyError:pass
    job='recovery-build-'+uuid.uuid4().hex[:12];before=lab.store.usage()['calls'];attempt=None
    with lab.store.connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS reference_recovery_constructions(plan_hash TEXT PRIMARY KEY,job_id TEXT,status TEXT)')
        c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT 1 FROM reference_recovery_constructions WHERE plan_hash=?',(plan['hash'],)).fetchone():raise ValueError('Exact plan already has a construction attempt; do not silently repeat it')
        c.execute('INSERT INTO reference_recovery_constructions VALUES(?,?,?)',(plan['hash'],job,'running'))
    lab.store.job(job,'running',{'action':'reference_repair_world_builder','plan_ref':_ref(plan)})
    try:
        ids=[e['message_id'] for e in incident['payload']['evidence']][:12]
        indexed={m['id']:m for m in source['payload']['messages']};selected=[indexed[i] for i in ids]
        grounding={'dataset_ref':_ref(source),'message_ids':ids,'evidence_status':'reported_chat_only_original_tool_state_and_audience_unknown',
            'motivating_mechanics':['Reported copied/transcribed URL strings differ; new task tests a controlled reference fault.','Stable originals and actual independent peer opens are separate from owner assertions.']}
        spec=create_reference_repair_spec(max_rounds=p['max_rounds'],source_grounding=grounding)
        env=ReferenceRepairEnvironment(spec,p['seed']);contract=_contract(spec)
        if not _same(env.snapshot(),ReferenceRepairEnvironment(spec,p['seed']).snapshot()):raise ValueError('Equal-seed reset differs')
        worker=ResearchAgents(lab.settings,lab.store,lab.research_harness('responses'))
        bs=object_schema({'fit':{'type':'string','enum':['supported_with_limits','unsupported']},'evidence_ids':TEXTS,
            'mechanism_mapping':TEXT,'source_hypothesis_fit':TEXT,'omitted_capabilities':TEXTS,'falsifiers':TEXTS})
        built=worker.run('environment-builder',{'task':'Review this NEW narrow one-original-document reference-repair world against exact historical reports. Source motivates URL identity and independent-access mechanics, not recovered Google truth. Two fresh roles, fixed correct content/ACL/authenticated profiles, one exogenous broken checker reference. Check source/question/tools/oracle fit, reject unsupported claims. No original model policies or historical effect are reproduced.',
            'question':p['question'],'evidence':selected,'world_rules':spec,'tool_action_contract':ACTION_SCHEMA,'outcome_contract':contract,'output_schema':bs},bs,source['payload'],{'candidates':[]},job)
        ap={'schema_version':'reference-repair-construction-attempt-v1','status':'builder_returned','plan_ref':_ref(plan),'source_refs':p['source_refs'],
            'environment':spec,'outcome_contract':contract,'builder_proposal':built,'causal_review':None,'job_id':job}
        attempt=lab.store.put('village_recovery_construction_attempt',ap,'recovery-construction-'+job)
        if built['fit']!='supported_with_limits' or not built['evidence_ids']:raise ValueError('Builder declined reference-mechanics fit')
        rs=object_schema({'decision':{'type':'string','enum':['approve_exploratory','approve_with_limits','requires_changes']},'hypothesis':TEXT,
            'evidence_ids':TEXTS,'identification_assumptions':TEXTS,'confound_checks':TEXTS,'falsifiers':TEXTS,'transport_limitations':TEXTS})
        review=worker.run('causal-methodologist',{'task':'Review permission for NONCONFIRMATORY exploratory feasibility, not a stable-effect endorsement. All arms have identical one-doc goals, clarified TITLE-search semantics, roles, tools, horizon, fixed content/ACL/principal, initial broken checker URL and seeded schedule; only visible private note differs. Teams are fresh and paired on initial worlds; arm order random. The primary requires an actual AUDITOR open of the current original with correct content and authorization; messages or owner opens cannot score. Decline actual design/tool/oracle/source-fit issues; approval never required. Small N and unknown historical transport are reported limitations rather than sole blockers to a feasibility pilot. No reading, mediation, novelty or historical causal claim. Validate the legal independent-repair path without prescribing subject decisions.',
            'plan':p,'evidence':selected,'world_rules':spec,'tool_action_contract':ACTION_SCHEMA,'outcome_contract':contract,'builder':built,'output_schema':rs},rs,source['payload'],{'candidates':[]},job)
        ap.update(status='reviewed_'+review['decision'],causal_review=review);attempt=lab.store.put('village_recovery_construction_attempt',ap,attempt['id'])
        if review['decision'] not in ('approve_exploratory','approve_with_limits'):raise ValueError('Causal reviewer requires changes')
        protocol={'schema_version':'reference-repair-protocol-v1','family':FAMILY,'study_scope':'exploratory_feasibility','plan_ref':_ref(plan),
            'source_refs':p['source_refs'],'question':p['question'],'hypothesis':p['hypothesis'],'environment':spec,'outcome_contract':contract,
            'grounding':{'source_ref':_ref(source),'incident_ref':_ref(incident),
                'evidence_ids':[e['message_id'] for e in incident['payload']['evidence']],
                'evidence_status':'Reported source messages motivate a new controlled reference fault; historical tool truth and audience remain unknown.'},
            'design':{'trials_per_arm':p['trials_per_arm'],'seed':p['seed'],'max_rounds':p['max_rounds'],'unit':'whole_two_role_team','paired_worlds':True},
            'notes':{'neutral_note':p['control_text'],'canonical_check':p['treatment_text']},'primary_outcome':PRIMARY,
            'subject_backend':{'harness':'responses','model':lab.settings.model,'max_output_tokens':600,'temperature':'provider_default','sampling_seed':'not_set'},
            'fidelity':{'historical_equivalence':False,'represented':['Exact stable document reference, private address-bar/profile and content versions, direct queued messages, independent access oracle'],
                'held_fixed':['Correct original content','Owner/checker viewer ACL','Initial authenticated profile'],'approximated':['Deterministic local document/Drive/browser tools'],
                'omitted':['Original six model policies','Google service and OS','Historical permissions/audience/private context']},
            'implementation_hashes':_codes(),'registered_at':now()}
        protocol['protocol_hash']=fingerprint(protocol);_validate_protocol(protocol)
        registration=lab.store.put('protocol',{'protocol':protocol,'frozen_hash':fingerprint(protocol),'status':'registered','agent_mode':'live','source_refs':p['source_refs']})
        payload={'schema_version':'reference-repair-simulator-v1','status':'ready','family':FAMILY,'study_scope':'exploratory_feasibility',
            'name':'One document: owner-to-auditor reference recovery','plan_ref':_ref(plan),'protocol_ref':_ref(registration),
            'source_refs':p['source_refs'],'environment':spec,'hypothesis':p['hypothesis'],'fidelity':protocol['fidelity'],
            'builder_proposal':built,'causal_review':review,'subject_mode':'live','model':lab.settings.model,'harness':'responses',
            'teams':p['trials_per_arm']*2,'max_actions':p['trials_per_arm']*4*p['max_rounds'],'maximum_subject_calls':p['trials_per_arm']*4*p['max_rounds'],
            'boundary_checks':{'passed':True,'equal_seed_reset':True,'active_roles':list(AGENTS),'one_original_visible':True},
            'limitations':p['limitations'],'paid_calls':lab.store.usage()['calls']-before}
        saved=lab.store.put('guided_simulator',payload,identity)
        with lab.store.connect() as c:c.execute('UPDATE reference_recovery_constructions SET status=? WHERE plan_hash=?',('completed',plan['hash']))
        lab.store.job(job,'completed',{'action':'reference_repair_world_builder','result_ids':[saved['id'],registration['id'],attempt['id']]})
        return {'simulator_ref':_ref(saved),'plan_ref':_ref(plan),'simulator':payload,'paid_calls':payload['paid_calls']}
    except Exception as exc:
        with lab.store.connect() as c:c.execute('UPDATE reference_recovery_constructions SET status=? WHERE plan_hash=?',('failed',plan['hash']))
        lab.store.job(job,'failed',{'action':'reference_repair_world_builder','error_type':type(exc).__name__,**({'attempt_ref':_ref(attempt)} if attempt else {})});raise


def _assignments(protocol):
    rng=random.Random(protocol['design']['seed']);rows=[]
    for pair in range(1,protocol['design']['trials_per_arm']+1):
        seed=rng.randrange(2**53);arms=list(ARMS);rng.shuffle(arms)
        rows.extend({'run_id':f'pair-{pair}-{arm}','pair_id':pair,'arm':arm,'environment_seed':seed} for arm in arms)
    return rows


def _analysis(runs,protocol):
    n=protocol['design']['trials_per_arm']
    if len(runs)!=2*n or any(r['status']!='complete' or type(r['outcomes'][PRIMARY]) is not int or r['outcomes'][PRIMARY] not in (0,1) for r in runs):
        raise ValueError('All assigned completed teams with binary code outcomes are required')
    groups={a:[r for r in runs if r['arm']==a] for a in ARMS};diffs=[]
    if any(len(rows)!=n for rows in groups.values()):raise ValueError('Arm inventory differs')
    for pair in range(1,n+1):
        d={r['arm']:r for r in runs if r['pair_id']==pair}
        if set(d)!=set(ARMS) or not _same(d[ARMS[0]]['environment_seed'],d[ARMS[1]]['environment_seed']):raise ValueError('Paired worlds differ')
        diffs.append(d['canonical_check']['outcomes'][PRIMARY]-d['neutral_note']['outcomes'][PRIMARY])
    difference=mean(diffs);radius=math.sqrt(2*math.log(40)/n)
    p=sum(abs(mean([v*s for v,s in zip(diffs,signs)]))+1e-12>=abs(difference) for signs in itertools.product((-1,1),repeat=n))/(2**n)
    return {'status':'descriptive_paired_contrast','study_scope':'exploratory_feasibility',
        'arms':{a:{'n':n,'correct':sum(r['outcomes'][PRIMARY] for r in rows),'success_rate':mean(r['outcomes'][PRIMARY] for r in rows),
            'mean_reference_failures':mean(r['outcomes']['reference_failures'] for r in rows)} for a,rows in groups.items()},
        'primary_effect':{'mean_treatment':mean(r['outcomes'][PRIMARY] for r in groups['canonical_check']),
            'mean_control':mean(r['outcomes'][PRIMARY] for r in groups['neutral_note']),'difference':difference,
            'ci95':[max(-1,difference-radius),min(1,difference+radius)],'interval_method':'bounded_pair_Hoeffding_95',
            'p_two_sided':p,'test_method':'exact_paired_sign_flip_sharp_null','test_samples':2**n,'unit':'whole_two_role_team','n_pairs':n,'pair_differences':diffs},
        'warnings':['Small exploratory pilot; note-package and this task/model only.','A solved proxy task does not identify historical cause or novelty.','Process measures are descriptive, not causal mediators.']}


def _run_team(protocol,a,runner,job):
    env=None;initial=None;turns=[];request=None
    try:
        env=ReferenceRepairEnvironment(protocol['environment'],a['environment_seed']);initial=env.snapshot()
        for role in env.agent_ids:env.inject_context(role,protocol['notes'][a['arm']])
        while not env.terminal:
            role=env.next_agent;request=reference_repair_subject_request(env,role);request['_job_id']=job+'-'+a['run_id']
            action=runner(copy.deepcopy(request));result=env.step(role,action)
            turns.append({'step':len(turns),'agent_id':role,'request':request,'action':copy.deepcopy(env.events[-1]['action']),'tool_result':result})
        return {**a,'status':'complete','initial_state':initial,'final_state':env.snapshot(),'turns':turns,'outcomes':env.evaluate()}
    except Exception as exc:
        return {**a,'status':'incomplete_infrastructure_failure','initial_state':initial,'partial_state':env.snapshot() if env else None,
            'turns':turns,'failed_request':request,'failure':{'type':type(exc).__name__,'error':clean(str(exc))[:600]}}


def verify_replay(report,*,expected_source_refs=None):
    _canonical(report);protocol=report['protocol'];_validate_protocol(protocol)
    if report.get('status') not in ('complete','incomplete_infrastructure_failure') or report.get('schema_version')!='reference-repair-result-v1':raise ValueError('Explicit completed/partial recovery report required')
    assignments=_assignments(protocol)
    if not _same(report['assignments'],assignments) or len(report['runs'])!=len(assignments):raise ValueError('Registered full grid differs')
    if (report['model']!=protocol['subject_backend']['model'] or not _same(report['backend'],protocol['subject_backend']) or
        report['protocol_hash']!=protocol['protocol_hash'] or report['agent_mode'] not in ('live','provided_runner')):raise ValueError('Report backend binding differs')
    sources=report['source_refs']
    from .village_access_environment import _ref as validate_ref
    for reference in sources.values():validate_ref(reference)
    if set(sources)!=set(protocol['source_refs'])|{'plan_ref','simulator_ref'} or not _same({k:sources[k] for k in protocol['source_refs']},protocol['source_refs']) or not _same(sources['plan_ref'],protocol['plan_ref']):raise ValueError('Report source binding differs')
    if expected_source_refs is not None and not _same(sources,expected_source_refs):raise ValueError('Host-authenticated source refs differ')
    if not _same(report.get('hypothesis'),protocol['hypothesis']) or not _same(report.get('fidelity'),protocol['fidelity']):
        raise ValueError('Reported hypothesis or fidelity differs')
    complete=report['status']=='complete';failed=set();checks=[]
    for assignment,run in zip(assignments,report['runs']):
        if not _same({k:run.get(k) for k in assignment},assignment):raise ValueError('Run grid identity differs')
        status=run['status'];pair=run['pair_id']
        if status not in ('not_started','complete','incomplete_infrastructure_failure') or pair in failed and status!='not_started':raise ValueError('Invalid paired execution progression')
        if status=='not_started':
            if not _same(run,{**assignment,'status':'not_started','turns':[]}):raise ValueError('Unstarted run has invented evidence')
            if complete:raise ValueError('Completed report contains unstarted assignment')
            failed.add(pair);continue
        if status!='complete':failed.add(pair)
        if complete and status!='complete':raise ValueError('Incomplete unit in completed report')
        if run['initial_state'] is None:
            if status=='complete' or run['turns'] or run['partial_state'] is not None or run['failed_request'] is not None or 'outcomes' in run:raise ValueError('Unmaterialized run has invented evidence')
            continue
        env=ReferenceRepairEnvironment(protocol['environment'],run['environment_seed'])
        if not _same(env.snapshot(),run['initial_state']):raise ValueError('Initial world differs')
        for role in env.agent_ids:env.inject_context(role,protocol['notes'][run['arm']])
        for index,turn in enumerate(run['turns']):
            if type(turn['step']) is not int or turn['step']!=index or env.terminal or env.next_agent!=turn['agent_id']:raise ValueError('Recorded boundary differs')
            request=reference_repair_subject_request(env,turn['agent_id']);recorded={k:v for k,v in turn['request'].items() if k!='_job_id'}
            if not _same(request,recorded):raise ValueError('Actual request/note differs')
            result=env.step(turn['agent_id'],copy.deepcopy(turn['action']))
            if not _same(result,turn['tool_result']) or not _same(env.events[-1]['action'],turn['action']):raise ValueError('Actual tool transition differs')
        if status=='complete':
            if not env.terminal or not _same(env.snapshot(),run['final_state']) or not _same(env.evaluate(),run['outcomes']):raise ValueError('Terminal oracle/state differs')
        else:
            if 'outcomes' in run or not _same(env.snapshot(),run['partial_state']):raise ValueError('Partial run must have no outcome')
            if run['failed_request'] is not None:
                if env.terminal:raise ValueError('Failure request after final budget')
                request=reference_repair_subject_request(env,env.next_agent)
                if not _same(request,{k:v for k,v in run['failed_request'].items() if k!='_job_id'}):raise ValueError('Failed next request differs')
        checks.append({'run_id':run['run_id'],'steps':len(run['turns']),'execution_status':status,'passed':True})
    if complete:
        if not _same(_analysis(report['runs'],protocol),report['analysis']):raise ValueError('Numerical reconstruction differs')
    elif 'analysis' in report:raise ValueError('Incomplete reports cannot carry a causal estimate')
    return {'status':'passed' if complete else 'partial_trace_consistent','passed':complete,'checks':checks,'quantitative_available':complete,
        'analysis_recomputed':complete,'source_binding':'host_authenticated_exact_refs' if expected_source_refs else 'registered_sources_declared_simulator_ref',
        'scope':'Fresh deterministic replay of actual proxy requests/transitions/oracle. Does not attest hidden reading or historical Google state.','paid_calls':0}


def execute_plan(lab,raw,*,runner=None,max_workers=2):
    _int(max_workers,1,8,'Parallel pair workers')
    simulator=_record(lab,_parse(raw,('simulator_ref',))['simulator_ref'],'guided_simulator');plan,registration=validate_saved_world(lab,simulator)
    protocol=registration['payload']['protocol'];job='village-recovery-'+uuid.uuid4().hex[:12]
    with lab.store.connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS reference_recovery_executions(simulator_hash TEXT PRIMARY KEY,job_id TEXT,status TEXT,result_ref TEXT)');c.execute('BEGIN IMMEDIATE')
        previous=c.execute('SELECT * FROM reference_recovery_executions WHERE simulator_hash=?',(simulator['hash'],)).fetchone()
        if previous:
            if previous['status']=='completed':
                saved=_record(lab,json.loads(previous['result_ref']),'guided_result');return {'execution_ref':_ref(saved),**saved['payload'],'reused':True}
            raise ValueError('Exact simulator already has an execution attempt; no automatic rerun')
        c.execute('INSERT INTO reference_recovery_executions VALUES(?,?,?,?)',(simulator['hash'],job,'running',None))
    before=lab.store.usage()['calls'];assignments=_assignments(protocol);directory=lab.settings.runtime/'reference-repair-runs'/job
    report={'schema_version':'reference-repair-result-v1','status':'running','agent_mode':'live' if runner is None else 'provided_runner',
        'model':lab.settings.model,'backend':protocol['subject_backend'],'protocol':protocol,'protocol_hash':protocol['protocol_hash'],
        'source_refs':{**protocol['source_refs'],'plan_ref':_ref(plan),'simulator_ref':_ref(simulator)},'hypothesis':protocol['hypothesis'],'fidelity':protocol['fidelity'],
        'assignments':assignments,'runs':[{**a,'status':'not_started','turns':[]} for a in assignments],'started_at':now()}
    lab.store.job(job,'running',{'action':'village_recovery_experiment','simulator_ref':_ref(simulator),'completed':0,'total':len(assignments)})
    try:
        _write(directory/'protocol.json',protocol);_write(directory/'assignment.json',assignments)
        subject=runner if runner is not None else lab.harness('responses').subject
        def pair_run(pair):
            retained=[];errors=[]
            for a in [a for a in assignments if a['pair_id']==pair]:
                run=_run_team(protocol,a,subject,job);retained.append(run)
                try:_write(directory/'runs'/(run['run_id']+'.json'),run)
                except Exception as exc:errors.append(type(exc).__name__);break
                if run['status']!='complete':break
            return retained,errors
        errors=[]
        with ThreadPoolExecutor(max_workers=min(max_workers,protocol['design']['trials_per_arm'])) as pool:
            for future in as_completed([pool.submit(pair_run,pair) for pair in range(1,protocol['design']['trials_per_arm']+1)]):
                try:retained,bad=future.result()
                except Exception as exc:errors.append(type(exc).__name__);continue
                errors.extend(bad)
                for run in retained:report['runs'][next(i for i,a in enumerate(assignments) if a['run_id']==run['run_id'])]=run
                try:_write(directory/'progress.json',report)
                except Exception as exc:errors.append(type(exc).__name__)
                lab.store.job(job,'running',{'action':'village_recovery_experiment','simulator_ref':_ref(simulator),'completed':sum(r['status']=='complete' for r in report['runs']),'total':len(assignments)})
        if errors or any(r['status']!='complete' for r in report['runs']):
            report['archive_error_types']=errors;raise RuntimeError('Recovery study incomplete; all submitted pair traces retained')
        report['analysis']=_analysis(report['runs'],protocol);report['status']='complete';report['finished_at']=now();_write(directory/'report.json',report)
        proof=verify_replay(report,expected_source_refs=report['source_refs']);result=lab.store.put(RESULT_KIND,report)
        verification=lab.store.put('verification',{**proof,'experiment_ref':_ref(result),'source_refs':protocol['source_refs']})
        facts={'team_count':len(report['runs']),'subject_decisions':sum(len(r['turns']) for r in report['runs']),
            'arm_counts':{a:{'correct':report['analysis']['arms'][a]['correct'],'total':report['analysis']['arms'][a]['n']} for a in ARMS},'primary_effect':report['analysis']['primary_effect']}
        claims=lab.store.put('claim_audit',{'status':'passed','experiment_ref':_ref(result),'facts':facts,'scope':'Finite replay-bound code facts, no narrative semantic authority.','paid_calls':0})
        payload={'status':'complete','family':FAMILY,'agent_mode':report['agent_mode'],'study_scope':'exploratory_feasibility','plan_ref':_ref(plan),
            'simulator_ref':_ref(simulator),'result_ref':_ref(result),'verification_ref':_ref(verification),'claims_ref':_ref(claims),
            'source_refs':protocol['source_refs'],'hypothesis':protocol['hypothesis'],'fidelity':protocol['fidelity'],'analysis':report['analysis'],
            'teams':len(report['runs']),'subject_decisions':facts['subject_decisions'],'paid_calls':lab.store.usage()['calls']-before,'job_id':job}
        saved=lab.store.put('guided_result',payload)
        with lab.store.connect() as c:c.execute('UPDATE reference_recovery_executions SET status=?,result_ref=? WHERE simulator_hash=?',('completed',json.dumps(_ref(saved)),simulator['hash']))
        lab.store.job(job,'completed',{'action':'village_recovery_experiment','result_ids':[result['id'],saved['id'],verification['id'],claims['id']]})
        return {'execution_ref':_ref(saved),**payload,'reused':False}
    except Exception as exc:
        report.pop('analysis',None);report.update(status='incomplete_infrastructure_failure',finished_at=now(),failure={'type':type(exc).__name__,'error':clean(str(exc))[:600]})
        try:_write(directory/'partial-report.json',report)
        except Exception as archive:report['failure_archive_error']=type(archive).__name__
        attempt=lab.store.put('village_recovery_attempt',report)
        with lab.store.connect() as c:c.execute('UPDATE reference_recovery_executions SET status=? WHERE simulator_hash=?',('failed',simulator['hash']))
        lab.store.job(job,'failed',{'action':'village_recovery_experiment','attempt_ref':_ref(attempt),'error_type':type(exc).__name__});raise
