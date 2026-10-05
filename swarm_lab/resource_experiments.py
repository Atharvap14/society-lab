"""Frozen whole-swarm reminder experiments in an optional resource analogue."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import platform
import random
from pathlib import Path
from statistics import mean

from .resource_environment import (SUBJECTS,fingerprint,create_resource_spec,validate_resource_spec,
    create_resource_environment,resource_subject_request,resource_environment_capabilities,
    check_resource_contract,offline_resource_policy)
from .diffusion_experiments import _now,_seed,_write,stratified_network_effect

API_VERSION='1.0'
STUDY_KIND='exclusive_resource_reminder'
CONTEXTS=('neutral','task_reminder')
TASK_REMINDER="Before choosing to wait, check which of your tasks actually requires the shared computer. Work on an independent task when feasible. Messages can coordinate access, while the computer's external occupation schedule still remains outside your control."
NEUTRAL_NOTE='You are continuing the current team task in this environment. The task description and available actions remain available for your next decision. This private note marks the continuation of your session; proceed as you ordinarily would.'


def resource_code_hashes():
    return {name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in
        ('resource_environment.py','resource_experiments.py','diffusion_experiments.py','diffusion_environment.py','harness.py')}


def _seal(body):
    p=copy.deepcopy(body);p.pop('protocol_hash',None);p['protocol_hash']=fingerprint(p);return p


def _validate_notes(reminder,neutral):
    if any(not isinstance(t,str) or not t.strip() or len(t)>8000 or not 1<=len(t.split())<=300 for t in (reminder,neutral)):
        raise ValueError('Private notes require 1 to 300 words and at most 8000 characters')
    if len(reminder.split())!=len(neutral.split()):raise ValueError('This pilot requires matched note word counts')


def create_resource_protocol(trials_per_cell=2,seed=137,*,max_rounds=6,release_rounds=(1,2),
        independent_work_steps=1,computer_work_steps=1,max_messages_per_agent=None,
        reminder_text=TASK_REMINDER,neutral_text=NEUTRAL_NOTE,incident=None,subject_backend=None):
    if type(trials_per_cell) is not int or not 2<=trials_per_cell<=1000:raise ValueError('Require 2 to 1000 whole-swarm runs per arm')
    if type(seed) is not int:raise ValueError('Seed namespace must be an integer')
    _validate_notes(reminder_text,neutral_text)
    spec=create_resource_spec(max_rounds=max_rounds,release_rounds=release_rounds,
        independent_work_steps=independent_work_steps,computer_work_steps=computer_work_steps,
        max_messages_per_agent=max_messages_per_agent,incident=incident)
    capabilities=resource_environment_capabilities();count=math.comb(2*trials_per_cell,trials_per_cell)
    return _seal({'api_version':API_VERSION,'study_kind':STUDY_KIND,'created_at':_now(),
        'status':'frozen_before_execution','phase':'small_behavioral_and_mechanics_pilot',
        'registration_scope':'local_frozen_protocol_not_public_preregistration',
        'research_question':'Does a task-specific private reminder change executed completion when independent work is legal despite shared-computer contention?',
        'environment':spec,'environment_hash':fingerprint(spec),'capabilities':capabilities,'capability_hash':fingerprint(capabilities),
        'subject_backend':copy.deepcopy(subject_backend or {'harness':'scripted','model':'deterministic_offline_policy','generation':{'policy':'offline_resource_policy'}}),
        'contexts':{'neutral':{'insertion':neutral_text},'task_reminder':{'insertion':reminder_text}},
        'intervention':{'channel':'private_observable_context','recipients':['agent-0'],'focal_agent':'agent-0',
            'timing':'Immediately before agent-0 first scheduled decision','persistence':'Within this run only',
            'context_lengths':{'reminder_words':len(reminder_text.split()),'neutral_words':len(neutral_text.split()),
                'reminder_characters':len(reminder_text),'neutral_characters':len(neutral_text),
                'token_matching':'Matched words do not guarantee matched tokens or inert neutral content.'}},
        'design':{'unit':'whole_swarm_run','allocation':'equal_counts_complete_randomization',
            'trials_per_cell':trials_per_cell,'seed':seed,'contexts':list(CONTEXTS),
            'independent_environment_seed_per_run':True,
            'maximum_subject_calls':2*trials_per_cell*len(SUBJECTS)*max_rounds,
            'matched':['task costs','resource distribution','allocated decisions','message allowance','scheduler rule','backend'],
            'not_matched':['realized release round','realized actor order','lease opportunities','achieved completion','used decisions'],
            'stopping_rule':'All assigned swarms; each stops on all executed task completions or its allocated horizon.',
            'interference':'Allowed within the four-agent run; no state or message sharing between runs.'},
        'estimand':{'unit':'whole_swarm_run','primary_outcome':'task_completion_fraction',
            'treatment':'task_reminder','control':'neutral','direction':'two_sided',
            'operational_definition':'Executed completions divided by eight declared tasks; unfinished tasks zero, chat claims ignored',
            'population':'Independent draws from this synthetic task/resource/scheduler generator with the registered subject backend'},
        'measurement':{'oracle':'Code execution counters, not completion reports or inferred resource access',
            'test_null':'Sharp no-effect null for the assigned private note at every swarm; not an exact weak zero-average test under heterogeneous effects.',
            'primary_test':'Two-sided balanced whole-swarm randomization test',
            'primary_interval':'95% bounded independent-run Hoeffding interval; bootstrap sensitivity may degenerate',
            'multiplicity':'One registered primary contrast; secondary task/wait/access metrics descriptive',
            'missing_and_invalid':'Unfinished tasks score zero; invalid subject actions consume decisions; no behavioral exclusions',
            'infrastructure_failure':'Abort estimation, retain all partial execution; never silently drop or replace an assigned run',
            'process_metrics':'Wait/resource/message counts are post-treatment descriptions, not identified mediation or mental-state measures'},
        'pre_execution_test_resolution':{'balanced_assignments':count,'minimum_two_sided_p':math.exp(math.log(2)-math.log(count)),
            'exact_minimum_fraction':f'2/{count}','smallest_sample_warning':'At two trials per arm, the minimum two-sided exact p is 1/3; this cannot establish a 0.05 rejection.'},
        'limitations':['Historical global computer exclusivity is unestablished; the source audit reports simultaneous computer sessions and task-specific preparation.',
            'This is one optional contention analogue; synthetic tasks, costs, leases and release times are invented.',
            'Whole swarms are trials; individual tasks, messages and agent turns are not independent randomized samples.',
            'A note effect does not identify a latent global-wait belief, mediation, strategic patience or a historical mechanism.',
            'Truthful current availability removes uncertainty about resource state; no browser, actual work quality or wall-clock effort is modeled.',
            'Acquisition, work and messages consume decisions; realized lease opportunities and timing can differ across independently seeded arms.',
            'Neutral text may have effects and matched words do not match tokenizer length.',
            'Hosted model sampling is not seeded by environment seeds; stable backend and absence of cross-run memory remain assumptions.',
            'Independent run outcomes and backend/caller fidelity are assumptions, not guarantees of this runner.',
            'Positive, negative, null and inconclusive outcomes remain eligible for reporting.'],
        'execution_code_hashes':resource_code_hashes()})


def validate_resource_protocol(p,*,check_code=True):
    body=copy.deepcopy(p);signature=body.pop('protocol_hash',None)
    if not signature or fingerprint(body)!=signature:raise ValueError('Resource protocol changed after freezing')
    if p.get('api_version')!=API_VERSION or p.get('study_kind')!=STUDY_KIND:raise ValueError('Unsupported resource experiment')
    validate_resource_spec(p['environment'])
    if p['environment_hash']!=fingerprint(p['environment']):raise ValueError('Environment hash mismatch')
    cap=resource_environment_capabilities()
    if p['capabilities']!=cap or p['capability_hash']!=fingerprint(cap):raise ValueError('Capability mismatch')
    d=p['design'];n=d['trials_per_cell']
    if d['unit']!='whole_swarm_run' or d['contexts']!=list(CONTEXTS) or type(n) is not int or not 2<=n<=1000 or type(d['seed']) is not int:
        raise ValueError('Require the registered balanced whole-swarm design')
    if d['maximum_subject_calls']!=2*n*len(SUBJECTS)*p['environment']['max_rounds']:raise ValueError('Subject-call budget mismatch')
    if d.get('allocation')!='equal_counts_complete_randomization' or d.get('independent_environment_seed_per_run') is not True:
        raise ValueError('Allocation or reset design changed')
    if p['intervention']['recipients']!=['agent-0'] or p['intervention']['focal_agent']!='agent-0':raise ValueError('Recipient must remain fixed agent-0')
    if any(p['intervention'].get(k)!=v for k,v in {'channel':'private_observable_context',
            'timing':'Immediately before agent-0 first scheduled decision','persistence':'Within this run only'}.items()):
        raise ValueError('Unsupported intervention boundary')
    if set(p['contexts'])!=set(CONTEXTS):raise ValueError('Context arms changed')
    reminder=p['contexts']['task_reminder']['insertion'];neutral=p['contexts']['neutral']['insertion'];_validate_notes(reminder,neutral)
    lengths=p['intervention']['context_lengths']
    if any(lengths.get(k)!=v for k,v in {'reminder_words':len(reminder.split()),'neutral_words':len(neutral.split()),
            'reminder_characters':len(reminder),'neutral_characters':len(neutral)}.items()):raise ValueError('Note-length declaration mismatch')
    if p['estimand']['unit']!='whole_swarm_run' or p['estimand']['primary_outcome']!='task_completion_fraction' or p['estimand']['treatment']!='task_reminder' or p['estimand']['control']!='neutral' or p['estimand'].get('direction')!='two_sided':raise ValueError('Outcome or contrast changed')
    backend=p['subject_backend']
    if not isinstance(backend,dict) or not backend.get('harness') or not backend.get('model') or not isinstance(backend.get('generation'),dict):raise ValueError('Backend settings must be pinned before execution')
    if backend['harness']=='scripted' and backend!={'harness':'scripted','model':'deterministic_offline_policy','generation':{'policy':'offline_resource_policy'}}:
        raise ValueError('The default scripted registration must name the actual infrastructure policy')
    count=math.comb(2*n,n);resolution=p['pre_execution_test_resolution']
    if resolution['balanced_assignments']!=count or resolution['minimum_two_sided_p']!=math.exp(math.log(2)-math.log(count)) or resolution['exact_minimum_fraction']!=f'2/{count}':raise ValueError('Test-resolution declaration mismatch')
    if check_code and p['execution_code_hashes']!=resource_code_hashes():raise ValueError('Execution sources changed since registration')


def randomize_resource_runs(p):
    validate_resource_protocol(p)
    contexts=[c for c in CONTEXTS for _ in range(p['design']['trials_per_cell'])]
    random.Random(_seed(p['design']['seed'],'resource-allocation')).shuffle(contexts)
    assignments=[{'run_id':f'run-{i+1:04d}','run_index':i,'context':c,
        'environment_seed':_seed(p['design']['seed'],'resource-environment',i)} for i,c in enumerate(contexts)]
    if len({a['environment_seed'] for a in assignments})!=len(assignments):raise ValueError('Seed collision')
    return assignments


def analyze_resource_runs(runs,p,*,resamples=2000):
    if type(resamples) is not int or not 100<=resamples<=100000:raise ValueError('Require 100 to 100000 resamples')
    expected=randomize_resource_runs(p)
    if len(runs)!=len(expected) or any(any(r.get(k)!=v for k,v in a.items()) for r,a in zip(runs,expected)):
        raise ValueError('All assigned swarms must remain in their original execution order')
    if any(r['outcomes']['terminated_by'] not in ('all_tasks_completed','step_budget') or
            not isinstance(r['outcomes']['task_completion_fraction'],(int,float)) or
            not math.isfinite(r['outcomes']['task_completion_fraction']) or not 0<=r['outcomes']['task_completion_fraction']<=1 for r in runs):
        raise ValueError('Only complete bounded oracle outcomes can be estimated')
    metrics=('task_completion_fraction','independent_completion_fraction','computer_completion_fraction',
        'focal_completion_fraction','resource_access_grants','resource_access_denials','computer_work_steps',
        'independent_work_steps','waits','waits_while_independent_pending','task_specific_blocked_waits','messages_sent','steps_used','invalid_actions')
    cells={}
    for c in CONTEXTS:
        group=[r for r in runs if r['context']==c]
        cells[c]={'context':c,'n_swarms':len(group),**{m:mean(r['outcomes'][m] for r in group) for m in metrics},
            'initial_release_rounds':[r['initial_state']['release_round'] for r in group],
            'initial_first_actor':[r['initial_state']['schedule'][0] for r in group]}
    a=[r['outcomes']['task_completion_fraction'] for r in runs if r['context']=='task_reminder']
    b=[r['outcomes']['task_completion_fraction'] for r in runs if r['context']=='neutral']
    effect=stratified_network_effect([(a,b)],seed=_seed(p['design']['seed'],'resource-effect'),resamples=resamples)
    effect.update(unit='whole_swarm_run',outcome='task_completion_fraction',treatment='task_reminder',control='neutral',
        n_treatment_swarms=effect.pop('n_treatment_networks'),n_control_swarms=effect.pop('n_control_networks'))
    return {'cells':cells,'primary_effect':effect,'primary_family_size':1,
        'test_null':p['measurement']['test_null'],'resamples':resamples,
        'initial_balance_interpretation':'Descriptive pre-treatment timing balance, not a reason for selecting or excluding swarms.',
        'warnings':['The entire four-agent swarm is the randomized unit; individual tasks are not independent samples.',
            'Tiny pilots have wide intervals and cannot establish historical, cognitive or mediated mechanisms.',
            'Waiting/access/communication are post-treatment descriptions; no latent-state inference or mediation is identified.',
            'Realized release and lease opportunities differ across independent draws; clock time and work quality are unmodeled.',
            'The default two-per-arm exact test cannot attain p<0.05, and bootstrap sensitivity can degenerate.']}


class ResourceExecutionError(RuntimeError):
    def __init__(self,message,partial_report):super().__init__(message);self.partial_report=partial_report


def _archive_sources(output,p):
    directory=output/'execution-code';directory.mkdir(parents=True,exist_ok=True)
    hashes={}
    for name,expected in p['execution_code_hashes'].items():
        data=Path(__file__).with_name(name).read_bytes();actual=hashlib.sha256(data).hexdigest()
        if actual!=expected:raise ValueError('Execution archive differs from frozen protocol')
        (directory/name).write_bytes(data);hashes[name]=actual
    _write(directory/'manifest.json',{'files':hashes,'timing':'before_subject_calls','scope':'Selected execution sources only; no credentials or database.'})


def run_resource_experiment(protocol,agent_runner=None,output_dir=None,*,backend_metadata=None,on_progress=None,resamples=2000):
    validate_resource_protocol(protocol)
    if type(resamples) is not int or not 100<=resamples<=100000:raise ValueError('Require 100 to 100000 resamples')
    p=copy.deepcopy(protocol);registered=p['subject_backend'];actual=copy.deepcopy(backend_metadata if backend_metadata is not None else registered)
    if actual!=registered:raise ValueError('Backend differs from frozen registration')
    if agent_runner is None and registered.get('harness')!='scripted':raise ValueError('Scripted policy cannot stand in for registered live subjects')
    if agent_runner is not None and (registered.get('harness') in (None,'scripted') or not registered.get('model') or not isinstance(registered.get('generation'),dict)):
        raise ValueError('Provided runner requires declared model, harness and generation settings')
    if registered.get('harness')=='responses':
        if output_dir is None:raise ValueError('Hosted execution requires pre-subject local artifacts')
        if registered.get('harness_adapter_hash')!=p['execution_code_hashes']['harness.py']:raise ValueError('Responses adapter source must be pinned')
    assignments=randomize_resource_runs(p);output=Path(output_dir) if output_dir is not None else None
    if output:
        if (output/'report.json').exists():raise ValueError('Output already contains results')
        if (output/'protocol.json').exists() and json.loads((output/'protocol.json').read_text(encoding='utf-8'))!=p:raise ValueError('Output contains a different protocol')
        _write(output/'protocol.json',p);_write(output/'assignment.json',assignments);_archive_sources(output,p)
    report={'api_version':API_VERSION,'study_kind':STUDY_KIND,'experiment_id':f"resource-{p['protocol_hash'][:16]}",
        'protocol_hash':p['protocol_hash'],'protocol':p,'status':'running','started_at':_now(),'finished_at':None,
        'assignments':assignments,'runs':[],'maximum_subject_calls':p['design']['maximum_subject_calls'],
        'local_protocol_written_before_subject_calls':output is not None,
        'backend':{'mode':'scripted_offline_smoke_test' if agent_runner is None else 'provided_agent_runner',
            'registered_spec':registered,'metadata':actual,'python':platform.python_version(),
            'fresh_state_contract':'Stateless decisions without cross-swarm sessions or shared subject memory; caller assumption'},
        'evidence_scope':'Scripted infrastructure only; no empirical LLM evidence.' if agent_runner is None else
            'Assigned private-note effect in this synthetic resource/task generator; no historical global exclusivity or mental-state mechanism.'}
    if output:_write(output/'progress.json',report)
    runner=agent_runner or offline_resource_policy
    for unit in assignments:
        env=None;turns=[];delivered=set();request=None;action=None
        try:
            env=create_resource_environment(p['environment'],unit['environment_seed']);initial=env.snapshot()
            if output:_write(output/'initial_states'/f"{unit['run_id']}.json",initial)
            contract=check_resource_contract(env)
            if not contract['passed']:raise RuntimeError('Resource environment contract failed')
            while not env.terminal:
                actor=env.next_agent
                if actor=='agent-0' and actor not in delivered:
                    env.inject_context(actor,p['contexts'][unit['context']]['insertion']);delivered.add(actor)
                request=resource_subject_request(env,actor);action=None
                if output:_write(output/'pending_decision.json',{'status':'awaiting_model','run_id':unit['run_id'],'agent_id':actor,'request':request})
                action=runner(copy.deepcopy(request));result=env.step(actor,action)
                turns.append({'step':env.step_count-1,'agent_id':actor,'request':request,'action':copy.deepcopy(action),'tool_result':result})
                if output:_write(output/'pending_decision.json',{'status':'applied','run_id':unit['run_id'],'agent_id':actor,'request':request,'action':action,'tool_result':result})
            run={**copy.deepcopy(unit),'initial_state':initial,'final_state':env.snapshot(),'turns':turns,
                'environment_contract':contract,'actual_context_insertion_recipients':sorted({e['agent_id'] for e in env.events if e['type']=='context_insertion'}),
                'outcomes':env.evaluate('agent-0')}
            report['runs'].append(run)
            if output:_write(output/'runs'/f"{unit['run_id']}.json",run);_write(output/'progress.json',report)
        except Exception as exc:
            report.update(status='incomplete_infrastructure_failure',finished_at=_now(),
                failure={'run_id':unit['run_id'],'error_type':type(exc).__name__,'completed_steps':env.step_count if env else 0},
                incomplete_run={**copy.deepcopy(unit),'turns':turns,'state':env.snapshot() if env else None,
                    'pending_subject_request':request,'attempted_action':copy.deepcopy(action)})
            if output:_write(output/'report.json',report);_write(output/'progress.json',report)
            raise ResourceExecutionError(f"Resource execution failed in {unit['run_id']} ({type(exc).__name__}); effects not estimated",report) from exc
        if on_progress:
            try:on_progress({'completed':len(report['runs']),'total':len(assignments),'run_id':unit['run_id'],'context':unit['context'],'outcomes':copy.deepcopy(run['outcomes'])})
            except Exception as exc:report.setdefault('reporting_warnings',[]).append({'run_id':unit['run_id'],'callback_error_type':type(exc).__name__})
    try:report['analysis']=analyze_resource_runs(report['runs'],p,resamples=resamples)
    except Exception as exc:
        report.update(status='incomplete_analysis_failure',finished_at=_now(),failure={'phase':'analysis','error_type':type(exc).__name__})
        if output:_write(output/'report.json',report);_write(output/'progress.json',report)
        raise ResourceExecutionError('Resource analysis failed; effects not estimated',report) from exc
    report.update(status='complete',finished_at=_now());report['report_hash']=fingerprint(report)
    if output:_write(output/'report.json',report);_write(output/'progress.json',report)
    return report


def replay_resource_report(report,*,check_code=True):
    p=report['protocol'];validate_resource_protocol(p,check_code=check_code)
    if report.get('status')!='complete':return {'passed':False,'reason':'Incomplete reports cannot validate complete effects','checks':[]}
    body=copy.deepcopy(report);signature=body.pop('report_hash',None)
    checks=[{'name':'report_hash','passed':signature==fingerprint(body)},
        {'name':'assignments','passed':report['assignments']==randomize_resource_runs(p)},
        {'name':'protocol_identity','passed':report.get('protocol_hash')==p['protocol_hash'] and report.get('study_kind')==STUDY_KIND}]
    for run in report['runs']:
        try:
            env=create_resource_environment(p['environment'],run['environment_seed']);initial=env.snapshot();inserted=False;valid=True
            for turn in run['turns']:
                actor=env.next_agent
                if actor=='agent-0' and not inserted:
                    env.inject_context(actor,p['contexts'][run['context']]['insertion']);inserted=True
                if actor!=turn['agent_id']:valid=False;break
                valid=valid and resource_subject_request(env,actor)==turn['request']
                result=env.step(actor,copy.deepcopy(turn['action']));valid=valid and result==turn['tool_result']
            checks.append({'name':'recorded_action_replay','run_id':run['run_id'],
                'passed':valid and env.terminal and initial==run['initial_state'] and env.snapshot()==run['final_state'] and env.evaluate()==run['outcomes']})
        except (ValueError,RuntimeError,KeyError,TypeError) as exc:
            checks.append({'name':'recorded_action_replay','run_id':run.get('run_id'),'passed':False,'error_type':type(exc).__name__})
    try:analysis_ok=analyze_resource_runs(report['runs'],p,resamples=report['analysis']['resamples'])==report['analysis']
    except (KeyError,ValueError,TypeError):analysis_ok=False
    checks.append({'name':'authoritative_numerical_reanalysis','passed':analysis_ok})
    return {'passed':all(c['passed'] for c in checks),'checks':checks,'model_calls':0,
        'scope':'Replays this synthetic code oracle; does not certify the origin of subject actions or a historical mechanism.'}
