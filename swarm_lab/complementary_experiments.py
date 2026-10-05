"""Frozen whole-network experiments where observations are complementary.

Numerical factorial helpers are reused with their source hashes pinned. The
world, treatment and outcomes do not assign a predicted positive result. A
two-per-cell default is a mechanics/behavioral pilot with low exact-test power.
"""
from __future__ import annotations

import copy
import hashlib
import math
import platform
import random
from pathlib import Path
from statistics import mean

from .audit import snapshot_execution_code
from .complementary_environment import (SUBJECTS, TOPOLOGIES, fingerprint,
    create_complementary_spec, validate_complementary_spec,
    create_complementary_environment, complementary_subject_request,
    complementary_environment_capabilities, check_complementary_contract,
    offline_complementary_policy)
from .diffusion_experiments import (_now, _seed, _write, _holm,
                                    stratified_network_effect)

API_VERSION = '1.0'
STUDY_KIND = 'complementary_information_factorial'
CONTEXTS = ('baseline', 'placebo', 'source_thought')
SOURCE_THOUGHT = (
    'Before submitting a total, check which original IDs you have. Repeated relays '
    'are copies, not extra components. Share canonical originals with neighbors '
    'and consider which originals remain missing before calculating the modular '
    'total for your team.'
)
PLACEBO_THOUGHT = (
    'You are continuing the current team task in this environment. The task description '
    'and available actions remain available for your next decision. This private note '
    'marks the continuation of your session; proceed as you ordinarily would.'
)


def _code_hashes():
    names = ('complementary_environment.py', 'complementary_experiments.py',
             'diffusion_environment.py', 'diffusion_experiments.py', 'audit.py')
    return {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in names}


def _seal(body):
    p = copy.deepcopy(body);p.pop('protocol_hash', None)
    p['protocol_hash'] = fingerprint(p)
    return p


def _contrast_resolution(contrast, design):
    n = design['trials_per_cell']
    strata = len(design['factors'][contrast['stratify_by']])
    count = math.comb(2*n, n) ** strata
    return {**contrast, 'conditional_assignments': count,
        'minimum_two_sided_p': math.exp(math.log(2)-math.log(count)),
        'exact_minimum_fraction': f'2/{count}',
        'interpretation': 'Symmetric two-sided exact test, equal counts, no favorable ties; ties can only increase the attained p-value.'}


def create_complementary_protocol(trials_per_cell=2, seed=91, *, max_rounds=3,
        topologies=('ring','complete'), contexts=('placebo','source_thought'),
        recipients=('agent-0',), source_text=SOURCE_THOUGHT, placebo_text=PLACEBO_THOUGHT,
        modulus=97, incident=None, subject_backend=None):
    if type(trials_per_cell) is not int or not 2 <= trials_per_cell <= 1000:
        raise ValueError('trials_per_cell must be an integer between 2 and 1000')
    if type(seed) is not int:
        raise ValueError('seed must be an integer')
    if not topologies or len(set(topologies))!=len(topologies) or any(t not in TOPOLOGIES for t in topologies):
        raise ValueError('Choose unique implemented topologies')
    if len(contexts)<2 or len(set(contexts))!=len(contexts) or any(c not in CONTEXTS for c in contexts) or not {'placebo','source_thought'} <= set(contexts):
        raise ValueError('Use placebo and source_thought; baseline is optional')
    if list(recipients)!=['agent-0']:
        raise ValueError('This pilot fixes its private intervention recipient to agent-0')
    for text in (source_text, placebo_text):
        if not isinstance(text,str) or not text.strip() or len(text)>8000 or not 1 <= len(text.split()) <= 300:
            raise ValueError('Private notes require 1 to 300 words and at most 8000 characters')
    environments={t:create_complementary_spec(topology=t,max_rounds=max_rounds,modulus=modulus,incident=incident) for t in topologies}
    contrasts=[{'factor':'context','treatment':'source_thought','control':'placebo','stratify_by':'topology'}]
    if len(topologies)>1:
        control='ring' if 'ring' in topologies else topologies[0]
        treatment='complete' if 'complete' in topologies and control!='complete' else next(t for t in reversed(topologies) if t!=control)
        contrasts.append({'factor':'topology','treatment':treatment,'control':control,'stratify_by':'context'})
    design={'unit':'whole_network_run','allocation':'equal_counts_complete_randomization_of_factorial_cells',
        'trials_per_cell':trials_per_cell,'seed':seed,
        'factors':{'topology':list(topologies),'context':list(contexts)},
        'cells':[{'topology':t,'context':c} for t in topologies for c in contexts],
        'independent_environment_seed_per_run':True,
        'seed_plan':'Independent derived seed per network; measurement and scheduler use separate streams within that seed. No covert paired-seed design.',
        'maximum_subject_calls':trials_per_cell*len(topologies)*len(contexts)*len(SUBJECTS)*max_rounds,
        'matched':['four subjects','allocated turns','message-action cap','residue distribution','scheduler rule','model and harness'],
        'not_matched':['degree','multicast recipient deliveries','path lengths','relay opportunities','achieved canonical evidence','realized action count'],
        'stopping_rule':'All assigned networks. Each ends after all valid submissions or its fixed action budget.',
        'interference':'Allowed within a network; no shared state, tools or messages between networks.'}
    capabilities=complementary_environment_capabilities()
    return _seal({'api_version':API_VERSION,'study_kind':STUDY_KIND,'created_at':_now(),
        'status':'frozen_before_execution','phase':'small_behavioral_and_mechanics_pilot',
        'registration_scope':'local_frozen_protocol_not_public_preregistration',
        'research_question':'How do communication opportunities and a private provenance reminder affect exact answers when observations are complementary?',
        'environments':environments,'environment_hashes':{t:fingerprint(s) for t,s in environments.items()},
        'capabilities':capabilities,'capability_hash':fingerprint(capabilities),
        'subject_backend':copy.deepcopy(subject_backend or {'harness':'scripted','model':'deterministic_offline_policy','generation':{'policy':'offline_complementary_policy'}}),
        'contexts':{c:{'insertion':None if c=='baseline' else source_text if c=='source_thought' else placebo_text} for c in contexts},
        'intervention':{'channel':'private_observable_context','recipients':['agent-0'],'focal_agent':'agent-0',
            'timing':'Immediately before agent-0 first scheduled decision','persistence':'Retained in this subject context through this run; no cross-run retention',
            'interpretation':'Text insertion, not latent-thought measurement or editing',
            'context_lengths':{'source_words':len(source_text.split()),'placebo_words':len(placebo_text.split()),
                'source_characters':len(source_text),'placebo_characters':len(placebo_text),
                'token_matching':'Word lengths recorded; token lengths and neutral-note inertness are not guaranteed.'}},
        'design':design,
        'estimand':{'unit':'whole_network_run','primary_outcome':'mean_accuracy',
            'operational_definition':'Mean of four exact submitted-total modulo-q indicators; absent submissions contribute 0',
            'primary_contrasts':contrasts,'averaging':'Equal average over registered levels of the other factor',
            'direction':'two_sided; positive, negative and inconclusive outcomes retained',
            'population':'Independent four-agent networks in this declared complementary residue task'},
        'measurement':{'oracle':'Code equality to the independently generated sum modulo q; rationale is not scored',
            'primary_test':'Two-sided conditional randomization within the other factor; preserve factorial cell counts',
            'test_null':'Sharp no-effect null for the tested factor at each network, conditional on the other factor. This is not an exact weak zero-average test under heterogeneous effects.',
            'multiplicity':'Holm across the registered primary factor family; other contrasts descriptive',
            'primary_interval':'95% bounded independent-run Hoeffding interval; individual, not simultaneous',
            'sensitivity_interval':'Within-cell run bootstrap; small samples and ceilings may yield degenerate intervals',
            'missing_answers':'Intention-to-treat zeros; report completion separately',
            'invalid_actions':'Consume allocated decisions; retain assigned network outcomes',
            'exclusions':'None for behavioral outcomes. Infrastructure failure stops estimation and preserves partial execution.',
            'process_metrics':'Canonical attachment coverage frozen at submission, receipt and forwarding lineage, message actions and recipient deliveries are post-treatment descriptions, not identified mediation.'},
        'pre_execution_test_resolution':[_contrast_resolution(c,design) for c in contrasts],
        'limitations':['One network is one randomized trial; agents and messages are not independent samples.',
            'The default eight-run two-factor design has 36 conditional assignments per factor and minimum exact two-sided p=2/36; Holm cannot reach 0.05 in that pilot.',
            'Topology is an opportunity bundle including degree-dependent multicast fanout, not an isolated centrality effect.',
            'Canonical fragment coverage is tool-visible attachment inventory; free-text values and latent knowledge are not measured.',
            'Uniform subset uncertainty follows this synthetic generator; source IDs do not prove independence in real data.',
            'Environment seeds do not seed hosted-model sampling. Stable backend, provider sessions and no cross-run memory remain assumptions.',
            'Random execution order mitigates time drift without proving model stability; model aliases may drift.',
            'A neutral note controls some extra context; content and token-length effects remain possible.',
            'Historical mechanism, mediation, novelty and transfer remain unestablished.'],
        'execution_code_hashes':_code_hashes()})


def validate_complementary_protocol(p, *, check_code=True):
    body=copy.deepcopy(p);signature=body.pop('protocol_hash',None)
    if not signature or fingerprint(body)!=signature:
        raise ValueError('Complementary protocol changed after freezing')
    if p.get('api_version')!=API_VERSION or p.get('study_kind')!=STUDY_KIND:
        raise ValueError('Unsupported complementary experiment')
    if p.get('capabilities')!=complementary_environment_capabilities() or p.get('capability_hash')!=fingerprint(p['capabilities']):
        raise ValueError('Environment capability mismatch')
    design=p['design'];factors=design['factors'];n=design['trials_per_cell']
    if design.get('unit')!='whole_network_run' or type(n) is not int or not 2<=n<=1000 or type(design.get('seed')) is not int:
        raise ValueError('Require balanced whole-network randomization')
    if set(factors)!= {'topology','context'} or not factors['topology'] or len(set(factors['topology']))!=len(factors['topology']) or any(t not in TOPOLOGIES for t in factors['topology']):
        raise ValueError('Invalid topology factors')
    if len(set(factors['context']))!=len(factors['context']) or not {'source_thought','placebo'}<=set(factors['context']) or any(c not in CONTEXTS for c in factors['context']):
        raise ValueError('Invalid context factors')
    cells=[{'topology':t,'context':c} for t in factors['topology'] for c in factors['context']]
    if design['cells']!=cells or set(p['contexts'])!=set(factors['context']) or set(p['environments'])!=set(factors['topology']):
        raise ValueError('Factorial cells and templates must match')
    if p['intervention'].get('recipients')!=['agent-0'] or p['intervention'].get('focal_agent')!='agent-0':
        raise ValueError('Recipient changed from fixed agent-0')
    for c,definition in p['contexts'].items():
        text=definition.get('insertion')
        if c=='baseline' and text is not None:raise ValueError('Baseline must have no insertion')
        if c!='baseline' and (not isinstance(text,str) or not text.strip() or len(text)>8000 or not 1<=len(text.split())<=300):
            raise ValueError('Invalid private context')
    templates=[]
    for t,spec in p['environments'].items():
        validate_complementary_spec(spec)
        if spec['topology']['kind']!=t or p['environment_hashes'].get(t)!=fingerprint(spec):
            raise ValueError('Environment template hash or topology mismatch')
        invariant=copy.deepcopy(spec);invariant.pop('topology');templates.append(invariant)
    if any(s!=templates[0] for s in templates[1:]):
        raise ValueError('Topologies must share measurement, schedule and budget specifications')
    maximum=n*len(cells)*len(SUBJECTS)*templates[0]['max_rounds']
    if design['maximum_subject_calls']!=maximum:
        raise ValueError('Declared subject-call budget is inconsistent')
    if p['estimand']['primary_outcome']!='mean_accuracy' or p['estimand'].get('unit')!='whole_network_run':
        raise ValueError('Outcome or unit mismatch')
    contrasts=[{'factor':'context','treatment':'source_thought','control':'placebo','stratify_by':'topology'}]
    if len(factors['topology'])>1:
        control='ring' if 'ring' in factors['topology'] else factors['topology'][0]
        treatment='complete' if 'complete' in factors['topology'] and control!='complete' else next(t for t in reversed(factors['topology']) if t!=control)
        contrasts.append({'factor':'topology','treatment':treatment,'control':control,'stratify_by':'context'})
    if p['estimand']['primary_contrasts']!=contrasts:
        raise ValueError('Unsupported primary contrast declarations')
    if p['pre_execution_test_resolution']!=[_contrast_resolution(c,design) for c in p['estimand']['primary_contrasts']]:
        raise ValueError('Exact-test resolution declaration mismatch')
    if check_code and p['execution_code_hashes']!=_code_hashes():
        raise ValueError('Scientific execution source changed since freezing')


def randomize_complementary_runs(p):
    validate_complementary_protocol(p)
    cells=[copy.deepcopy(c) for c in p['design']['cells'] for _ in range(p['design']['trials_per_cell'])]
    random.Random(_seed(p['design']['seed'],'complementary-allocation')).shuffle(cells)
    units=[{**c,'run_index':i,'run_id':f'run-{i+1:04d}',
        'environment_seed':_seed(p['design']['seed'],'complementary-environment',i)} for i,c in enumerate(cells)]
    if len({u['environment_seed'] for u in units})!=len(units):raise ValueError('Assigned environment seeds collide')
    return units


def analyze_complementary_runs(runs,p,*,resamples=2000):
    expected=randomize_complementary_runs(p)
    if len(runs)!=len(expected) or any(any(r.get(k)!=v for k,v in unit.items()) for r,unit in zip(runs,expected)):
        raise ValueError('All assigned networks must be analyzed in their original order')
    groups={};cells={}
    metrics=('mean_accuracy','focal_accuracy','completion_rate','messages_sent','message_deliveries','steps_used',
        'invalid_actions','mean_unique_originals_at_submission','all_originals_at_submission_fraction','relay_attachment_events')
    for cell in p['design']['cells']:
        group=[r for r in runs if r['topology']==cell['topology'] and r['context']==cell['context']]
        if len(group)!=p['design']['trials_per_cell']:raise ValueError('Incomplete factorial cell')
        groups[(cell['topology'],cell['context'])]=group
        cells[f"{cell['topology']}|{cell['context']}"]={'n_networks':len(group),**cell,
            **{m:mean(r['outcomes'][m] for r in group) for m in metrics},
            'initial_state_balance':{'oracle_residues':[r['initial_state']['oracle_total'] for r in group],
                'focal_original_values':[r['initial_state']['original_fragments']['fragment-agent-0']['value'] for r in group]},
            'step_budget_terminations':sum(r['outcomes']['terminated_by']=='step_budget' for r in group)}
    effects=[]
    for index,c in enumerate(p['estimand']['primary_contrasts']):
        strata=[]
        for other in p['design']['factors'][c['stratify_by']]:
            a=groups[(other,c['treatment'])] if c['factor']=='context' else groups[(c['treatment'],other)]
            b=groups[(other,c['control'])] if c['factor']=='context' else groups[(c['control'],other)]
            strata.append(([r['outcomes']['mean_accuracy'] for r in a],[r['outcomes']['mean_accuracy'] for r in b]))
        effects.append({**c,'outcome':'mean_accuracy',**stratified_network_effect(strata,
            seed=_seed(p['design']['seed'],'complementary-primary',index),resamples=resamples)})
    for e,adjusted in zip(effects,_holm([e['p_two_sided'] for e in effects])):e['p_holm_primary_family']=adjusted
    return {'cells':cells,'factor_effects':effects,'primary_effect':effects[0],'primary_family_size':len(effects),
        'test_null':p['measurement']['test_null'],
        'initial_balance_interpretation':'Describe randomized initial values; do not select/exclude runs or adjust post hoc from this tiny sample.',
        'warnings':[ 'Whole networks are the trials; within-network agents/messages are not independent samples.',
            'Conditional tests preserve the other factor and balanced cell counts; Holm covers the primary family.',
            'Permutation p-values refer to sharp no-effect nulls; heterogeneous zero-average effects are not an exact weak-null interpretation.',
            'Intervals are individual bounded independent-run intervals, not simultaneous; bootstrap can collapse at ceilings.',
            'The default eight-run two-factor design cannot obtain an exact factor p<0.05 even with perfect separation.',
            'Coverage, receipts, dispatches and lineage are post-treatment descriptions, not identified mediation.',
            'Topology includes degree-dependent multicast fanout; task/model generalization and historical causation are unestablished.']}


class ComplementaryExecutionError(RuntimeError):
    def __init__(self,message,partial_report):
        super().__init__(message);self.partial_report=partial_report


def run_complementary_experiment(protocol,agent_runner=None,output_dir=None,*,backend_metadata=None,on_progress=None,resamples=2000):
    validate_complementary_protocol(protocol)
    if type(resamples) is not int or not 100<=resamples<=100000:
        raise ValueError('Require 100 to 100000 resamples')
    p=copy.deepcopy(protocol);registered=p['subject_backend']
    actual=copy.deepcopy(backend_metadata if backend_metadata is not None else registered)
    if actual!=registered:raise ValueError('Subject backend differs from frozen registration')
    if agent_runner is None and registered.get('harness')!='scripted':raise ValueError('Scripted runner cannot execute a live backend registration')
    if agent_runner is not None and (registered.get('harness') in (None,'scripted') or not registered.get('model') or not isinstance(registered.get('generation'),dict)):
        raise ValueError('Provided runner requires pinned model, harness and generation settings')
    if agent_runner is not None and registered.get('harness')=='responses' and output_dir is None:
        raise ValueError('Hosted subject execution requires pre-subject local artifacts')
    units=randomize_complementary_runs(p);output=Path(output_dir) if output_dir is not None else None
    if output:
        import json
        if (output/'report.json').exists():raise ValueError('Output directory already contains results')
        if (output/'protocol.json').exists() and json.loads((output/'protocol.json').read_text(encoding='utf-8'))!=p:raise ValueError('Output directory contains a different protocol')
        _write(output/'protocol.json',p);_write(output/'assignment.json',units)
        manifest=snapshot_execution_code(output)
        if any(manifest['files'].get(k)!=v for k,v in p['execution_code_hashes'].items()):raise ValueError('Archived source differs from protocol')
    report={'api_version':API_VERSION,'study_kind':STUDY_KIND,'experiment_id':f"complementary-{p['protocol_hash'][:16]}",
        'protocol_hash':p['protocol_hash'],'protocol':p,'started_at':_now(),'finished_at':None,
        'status':'running','assignments':units,'runs':[],
        'backend':{'mode':'scripted_offline_smoke_test' if agent_runner is None else 'provided_agent_runner',
            'metadata':actual,'registered_spec':registered,'python':platform.python_version(),
            'fresh_state_contract':'Stateless callable per subject decision; no cross-network sessions or mutable state'},
        'evidence_scope':'Scripted policies validate mechanics only; no empirical LLM evidence.' if agent_runner is None else 'Assigned text/topology effects among provided subjects in a synthetic complementary-information task; no historical causal mechanism.',
        'local_protocol_written_before_subject_calls':output is not None,'maximum_subject_calls':p['design']['maximum_subject_calls']}
    if output:_write(output/'progress.json',report)
    runner=agent_runner or offline_complementary_policy
    for unit in units:
        env=None;turns=[];delivered=set()
        try:
            env=create_complementary_environment(p['environments'][unit['topology']],unit['environment_seed'])
            initial=env.snapshot()
            if output:_write(output/'initial_states'/f"{unit['run_id']}.json",initial)
            contract=check_complementary_contract(env)
            if not contract['passed']:raise RuntimeError('Complementary environment contract failed')
            while not env.terminal:
                actor=env.next_agent
                if actor=='agent-0' and actor not in delivered:
                    text=p['contexts'][unit['context']]['insertion']
                    if text is not None:env.inject_context(actor,text)
                    delivered.add(actor)
                request=complementary_subject_request(env,actor)
                action=runner(copy.deepcopy(request));result=env.step(actor,action)
                turns.append({'step':env.step_count-1,'agent_id':actor,'request':request,'action':copy.deepcopy(action),'tool_result':result})
            run={**copy.deepcopy(unit),'initial_state':initial,'final_state':env.snapshot(),'turns':turns,
                'insertion_boundary_reached_by':sorted(delivered),
                'actual_context_insertion_recipients':sorted({e['agent_id'] for e in env.events if e['type']=='context_insertion'}),
                'environment_contract':contract,'outcomes':env.evaluate('agent-0')}
            report['runs'].append(run)
            if output:_write(output/'runs'/f"{unit['run_id']}.json",run);_write(output/'progress.json',report)
        except Exception as exc:
            report['status']='incomplete_infrastructure_failure';report['finished_at']=_now()
            report['failure']={'run_id':unit['run_id'],'error_type':type(exc).__name__,'completed_steps':env.step_count if env is not None else 0}
            report['incomplete_run']={**copy.deepcopy(unit),'turns':turns,'state':env.snapshot() if env is not None else None}
            if output:_write(output/'report.json',report)
            raise ComplementaryExecutionError(f"Complementary execution failed in {unit['run_id']} ({type(exc).__name__}); no effects estimated",report) from exc
        if on_progress:
            try:on_progress({'completed':len(report['runs']),'total':len(units),'run_id':unit['run_id'],
                'topology':unit['topology'],'context':unit['context'],'outcomes':copy.deepcopy(run['outcomes'])})
            except Exception as exc:report.setdefault('reporting_warnings',[]).append({'run_id':unit['run_id'],'callback_error_type':type(exc).__name__})
    try:report['analysis']=analyze_complementary_runs(report['runs'],p,resamples=resamples)
    except Exception as exc:
        report['status']='incomplete_analysis_failure';report['finished_at']=_now()
        report['failure']={'phase':'analysis','error_type':type(exc).__name__}
        if output:_write(output/'report.json',report)
        raise ComplementaryExecutionError('Complementary analysis failed; no effects estimated',report) from exc
    report['status']='complete';report['finished_at']=_now();report['report_hash']=fingerprint(report)
    if output:_write(output/'report.json',report);_write(output/'progress.json',report)
    return report
