"""A bounded, checkpointed bridge between existing research components.

Only host allowlisted methods are called. A saved execution is recovered, never
repeated, after an uncertain checkpoint. Curation saves a proposed mechanism as
an untested analogue hypothesis, rather than treating an effect as its proof.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import uuid
from dataclasses import replace
from pathlib import Path

from .store import StoreConflictError, clean, fingerprint, now

INSTRUMENT_VERSION = 'bounded-research-cycle-v1'
STAGES = ('construct', 'register', 'execute', 'audit', 'claims', 'curate')
STAGE_ARTIFACTS = dict(zip(STAGES, ('blueprint', 'protocol', 'result', 'verification', 'claim_audit', 'theory')))
DISPATCH = {
    'protocol': ('experiment', 'experiment'),
    'network_protocol': ('experiment_network', 'network_experiment'),
    'complementary_protocol': ('experiment_complementary', 'complementary_experiment'),
    'resource_protocol': ('experiment_resource', 'resource_experiment'),
}
MAX_SAFE_ATTEMPTS = 3
DEPENDENCIES = (
    'research_cycle.py', 'pipeline.py', 'store.py', 'config.py', 'library.py',
    'authoring_workflow.py', 'environment_authoring.py', 'environment_api.py',
    'experiment_authoring.py', 'resource_workflow.py', 'resource_claims.py',
    'claim_audit.py', 'audit.py', 'reporting.py', 'research.py',
    'research_transport.py', 'harness.py', 'experiments.py', 'environments.py',
    'diffusion_environment.py', 'diffusion_experiments.py',
    'complementary_environment.py', 'complementary_experiments.py',
    'resource_environment.py', 'resource_experiments.py',
)


class _Blocked(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _json(value, *, max_bytes=4 * 1024 * 1024, max_nodes=200000):
    """Canonical finite JSON, with type identity and a small input ceiling."""
    nodes = 0
    def visit(v, depth=0):
        nonlocal nodes
        nodes += 1
        if depth > 32 or nodes > max_nodes:
            raise ValueError('Cycle input exceeds its nesting/node bound')
        if v is None or type(v) in (bool, int):
            return
        if type(v) is float:
            if not math.isfinite(v):
                raise ValueError('Cycle input must be finite JSON')
            return
        if type(v) is str:
            v.encode('utf-8', errors='strict')
            return
        if type(v) is list:
            for item in v:
                visit(item, depth + 1)
            return
        if type(v) is dict and all(type(k) is str for k in v):
            for k, item in v.items():
                visit(k, depth + 1)
                visit(item, depth + 1)
            return
        raise ValueError('Cycle inputs must be declarative JSON, not callbacks or objects')
    visit(value)
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False,
                     separators=(',', ':'), allow_nan=False).encode('utf-8')
    if len(raw) > max_bytes:
        raise ValueError('Cycle JSON exceeds its declared byte bound')
    return raw


def _same(left, right):
    return _json(left) == _json(right)


def _digest(value):
    return hashlib.sha256(_json(value)).hexdigest()


def _integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{name} must be an integer between {low} and {high}')
    return value


def _requirements(value):
    if type(value) is not list or len(value) > 30 or any(
            type(x) is not str or not 1 <= len(x) <= 100 for x in value) or len(set(value)) != len(value):
        raise ValueError('Use distinct bounded capability names')
    return copy.deepcopy(value)


def _ref(obj):
    return {k: obj[k] for k in ('kind', 'id', 'version', 'hash')}


def _reference(value, kind=None):
    if type(value) is not dict or set(value) != {'kind', 'id', 'version', 'hash'}:
        raise ValueError('An exact reference requires kind, id, version and hash')
    if type(value['kind']) is not str or (kind is not None and value['kind'] != kind):
        raise ValueError('Reference kind mismatch')
    if type(value['id']) is not str or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,180}', value['id']):
        raise ValueError('Invalid reference ID')
    _integer(value['version'], 'Reference version', 1, 1000000000)
    if type(value['hash']) is not str or not re.fullmatch(r'[0-9a-f]{64}', value['hash']):
        raise ValueError('Invalid reference hash')
    return copy.deepcopy(value)


def _resolve(lab, ref, *, current=True):
    ref = _reference(ref)
    saved = lab.store.get(ref['id'], ref['version'])
    if not _same(_ref(saved), ref):
        raise _Blocked('reference_mismatch', 'Pinned object does not match its exact reference')
    if current and not _same(_ref(lab.store.get(ref['id'])), ref):
        raise _Blocked('version_drift', f"Latest {ref['kind']} changed; selected versions are not silently rebased")
    return saved


def _code_hashes():
    directory = Path(__file__).parent
    return {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
            for name in DEPENDENCIES}


def _sources(lab, behavior_ref, source_refs):
    behavior_ref = _reference(behavior_ref, 'behavior')
    if type(source_refs) is not dict or set(source_refs) != {'dataset', 'discovery'}:
        raise ValueError('Pin exactly the dataset and discovery source references')
    sources = {kind: _reference(source_refs[kind], kind) for kind in ('dataset', 'discovery')}
    behavior = _resolve(lab, behavior_ref)
    p = behavior['payload']
    from .library import STATUSES
    if p.get('status') not in STATUSES or p.get('status') == 'rejected' or p.get('research_quality_status') in (
            'schema_defect_requires_re_review', 'superseded_schema_defect_review'):
        raise ValueError('A non-rejected, current skeptical behavior review is required')
    for kind, ref in sources.items():
        source = _resolve(lab, ref)
        embedded = p.get('source_refs', {}).get(kind)
        if not _same(embedded, {k: ref[k] for k in ('id', 'version', 'hash')}):
            raise ValueError('Behavior and caller source pins differ')
        if p.get(kind + '_id', ref['id']) != ref['id']:
            raise ValueError('Behavior source ID fields contradict the selected pins')
        if kind == 'discovery' and source['payload'].get('dataset_ref') is not None:
            linked = source['payload']['dataset_ref']
            expected = sources['dataset'] if type(linked) is dict and 'kind' in linked else {
                k: sources['dataset'][k] for k in ('id', 'version', 'hash')}
            if not _same(linked, expected):
                raise ValueError('Discovery is bound to another dataset version')
    return behavior_ref, sources


def _completion_scope(plan):
    return ('Scripted infrastructure only' if not plan['execution']['subjects_live'] else
        'Registered synthetic world and requested model; historical mechanism and generalization unestablished')


def start_research_cycle(lab, *, behavior_ref, source_refs, proposal=None,
        fit_review=None, blueprint_ref=None, research_question='', required_capabilities=None,
        trials_per_cell=2, seed=4491, audit_seed=0, research_live=False,
        subjects_live=False, research_harness='responses', subject_harness='responses',
        max_new_model_calls=0, job_id=None):
    """Claim one identity, freeze its plan, and advance all safe stages.

    Runtime failures return a durable failed/blocked cycle. Invalid caller input
    raises before claiming a job. Resume never enlarges this absolute call cap.
    """
    if type(research_live) is not bool or type(subjects_live) is not bool:
        raise ValueError('research_live and subjects_live must be explicit booleans')
    if research_harness not in ('responses', 'codex') or subject_harness != 'responses':
        raise ValueError('Research supports responses/codex; subjects support responses only')
    _integer(trials_per_cell, 'trials_per_cell', 2, 32)
    _integer(seed, 'seed', 0, 2147483647)
    _integer(audit_seed, 'audit_seed', 0, 2147483647)
    _integer(max_new_model_calls, 'max_new_model_calls', 0, 100000)
    _integer(lab.settings.max_calls, 'global max_calls', 0, 100000)
    if (research_live or subjects_live) and max_new_model_calls == 0:
        raise ValueError('Live execution requires an explicit positive model-call ceiling')
    if not (research_live or subjects_live) and max_new_model_calls != 0:
        raise ValueError('Offline cycles must authorize zero model calls')
    if type(research_question) is not str or len(research_question) > 4000:
        raise ValueError('Use a bounded research question')
    requirements = _requirements([] if required_capabilities is None else required_capabilities)
    if blueprint_ref is not None:
        blueprint_ref = _reference(blueprint_ref, 'environment_blueprint')
        if proposal is not None or fit_review is not None or research_live:
            raise ValueError('An existing blueprint cannot be combined with authoring inputs/live authoring')
        mode = 'existing_blueprint'
    elif research_live:
        if proposal is not None or fit_review is not None:
            raise ValueError('Agentic construction cannot accept a supplied proposal or review')
        mode = 'agentic'
    else:
        if type(proposal) is not dict or (fit_review is not None and type(fit_review) is not dict):
            raise ValueError('Offline authoring needs a declarative proposal and optional declarative review')
        mode = 'supplied'
    behavior_ref, sources = _sources(lab, behavior_ref, source_refs)
    if blueprint_ref is not None:
        existing = _resolve(lab, blueprint_ref)
        if required_capabilities is None:
            requirements = _requirements(existing['payload'].get('trusted_required_capabilities'))
    used = _integer(lab.store.usage()['calls'], 'Current call usage', 0, 1000000000)
    job_id = job_id or 'research-cycle-' + uuid.uuid4().hex[:12]
    if (type(job_id) is not str or not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]{0,119}', job_id) or
            re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])', job_id.split('.')[0])):
        raise ValueError('Use a bounded stable job identity')
    plan = {'schema_version': '1.0', 'instrument_version': INSTRUMENT_VERSION,
        'behavior_ref': behavior_ref, 'source_refs': sources,
        'construction': {'mode': mode, 'proposal': proposal, 'fit_review': fit_review,
            'blueprint_ref': blueprint_ref, 'research_question': research_question,
            'required_capabilities': requirements, 'audit_seed': audit_seed},
        'design': {'trials_per_cell': trials_per_cell, 'seed': seed},
        'execution': {'research_live': research_live, 'subjects_live': subjects_live,
            'research_harness': research_harness, 'subject_harness': subject_harness,
            'requested_model': lab.settings.model},
        'budget': {'usage_calls_at_start': used, 'max_new_model_calls': max_new_model_calls,
            'global_cap_at_start': lab.settings.max_calls,
            'absolute_call_ceiling': min(lab.settings.max_calls, used + max_new_model_calls)},
        'code_hashes': _code_hashes(), 'safe_stage_attempt_limit': MAX_SAFE_ATTEMPTS,
        'curation': 'untested_blueprint_hypothesis_only'}
    _json(plan)
    if not _same(clean(plan), plan):
        raise ValueError('Plan persistence would redact its inputs; do not include credentials')
    plan_hash = _digest(plan)
    cycle_id = 'research_cycle-' + hashlib.sha256(job_id.encode()).hexdigest()[:20]
    if lab.store.history(cycle_id):
        raise ValueError('Cycle identity already exists; resume its exact saved plan')
    lab.store.start_job(job_id, {'stage': 'research_cycle', 'cycle_id': cycle_id, 'plan_hash': plan_hash})
    payload = {'instrument_version': INSTRUMENT_VERSION, 'job_id': job_id,
        'plan': copy.deepcopy(plan), 'plan_hash': plan_hash, 'status': 'running', 'phase': 'construct',
        'resume_count': 0, 'stages': {name: {'status': 'pending', 'attempts': 0,
            'job_id': None, 'artifact_ref': None} for name in STAGES},
        'artifacts': {}, 'construction_attempt_refs': [], 'authorized_behavior_append': None,
        'failures': [], 'extension_requirements': [],
        'completion_scope': _completion_scope(plan),
        'started_at': now()}
    saved = lab.store.put('research_cycle', payload, cycle_id)
    return _drive(lab, saved)


def resume_research_cycle(lab, cycle_id):
    """Resume the frozen plan; no caller flags, new seeds or expanded call cap."""
    obj = lab.store.get(cycle_id)
    if obj['kind'] != 'research_cycle':
        raise ValueError('Resume an existing research cycle')
    p = copy.deepcopy(obj['payload'])
    initial = lab.store.history(cycle_id)[0]['payload']
    if (p.get('instrument_version') != INSTRUMENT_VERSION or
            not _same(p.get('plan'), initial.get('plan')) or
            p.get('plan_hash') != _digest(p['plan'])):
        raise ValueError('The original cycle plan was changed')
    _checkpoint_bindings(lab, obj, historical=True)
    if p['status'] in ('completed', 'blocked', 'failed'):
        _terminal_closure(lab, obj)
    if p['status'] in ('completed', 'blocked'):
        return obj
    if p['status'] not in ('running', 'failed'):
        raise ValueError('Unsupported cycle state')
    number = _integer(p['resume_count'], 'resume_count', 0, 20) + 1
    invocation=f"{p['job_id']}.resume.{number}"
    lab.store.start_job(invocation,
        {'stage': 'cycle_resume', 'cycle_id': cycle_id, 'plan_hash': p['plan_hash']})
    identity={'stage':'cycle_resume','cycle_id':cycle_id,'plan_hash':p['plan_hash'],
        'requested_cycle_ref':_ref(obj),'resume_number':number,
        'authority':'Invocation record only; authoritative cycle and child jobs are unchanged by this closure.'}
    p.update(resume_count=number, status='running')
    try:
        try:
            returned=_drive(lab, _save(lab, obj, p))
        except StoreConflictError:
            returned=_conflict_checkpoint(lab, obj, p)
        status=returned['payload']['status']
        lab.store.job(invocation,'completed' if status=='completed' else 'failed',
            {**identity,'outcome':'returned_checkpoint','cycle_ref':_ref(returned),
             'cycle_status':status,'phase':returned['payload']['phase']})
        return returned
    except Exception as error:
        failed={**identity,'outcome':'exception','error_type':type(error).__name__,'error':str(error)[:2000]}
        try:
            retained=lab.store.get(cycle_id)
            failed.update(last_recorded_cycle_ref=_ref(retained),
                last_recorded_cycle_status=retained['payload'].get('status'))
        except Exception:
            # A known requested identity remains even if the Store is unavailable.
            pass
        try:
            lab.store.job(invocation,'failed',failed)
        except Exception as closure_error:
            error.add_note('Resume invocation closure could not be persisted ('+type(closure_error).__name__+').')
        raise


def _save(lab, obj, p):
    """CAS append and its authoritative changed-stage/root jobs atomically."""
    updates=[];phase=p.get('phase');state=p['stages'].get(phase,{})
    terminal=p.get('status') in ('completed','blocked','failed')
    prior=obj['payload']['stages'].get(phase,{})
    if state.get('status')=='completed' and prior.get('status')!='completed':
        updates.append({'id':state['job_id'],'status':'completed','preserve_completed':False,
            'payload':{'stage':phase,'cycle_id':obj['id'],'plan_hash':p['plan_hash'],'artifact_ref':state['artifact_ref']}})
    elif terminal and p['status']!='completed' and state.get('job_id'):
        child=lab.store.get_job(state['job_id'])
        retained=copy.deepcopy(child['payload']) if child else {}
        updates.append({'id':state['job_id'],'status':'failed','preserve_completed':True,
            'payload':{**retained,'stage':phase,'cycle_id':obj['id'],'plan_hash':p['plan_hash'],'error':state.get('error')}})
    if terminal:
        reference={'kind':'research_cycle','id':obj['id'],'version':obj['version']+1,'hash':fingerprint(clean(p))}
        closed={'stage':'research_cycle','cycle_id':obj['id'],'cycle_ref':reference,
            'plan_hash':p['plan_hash'],'artifacts':p['artifacts']}
        if p['status']!='completed':
            closed.update(phase=p['phase'],cycle_status=p['status'],error=p['stages'][p['phase']].get('error'))
        updates.append({'id':p['job_id'],'status':'completed' if p['status']=='completed' else 'failed',
                        'payload':closed,'preserve_completed':False})
    elif obj['payload'].get('status')=='failed' and p.get('status')=='running':
        updates.append({'id':p['job_id'],'status':'running','preserve_completed':False,
            'payload':{'stage':'research_cycle','cycle_id':obj['id'],'plan_hash':p['plan_hash']}})
    return lab.store.compare_and_put('research_cycle',p,obj['id'],
        expected_version=obj['version'],expected_hash=obj['hash'],job_updates=updates)


def _completed_binding(lab,p,stage,*,historical):
    state=p['stages'][stage]
    _integer(state.get('attempts'),'Completed stage attempts',1,MAX_SAFE_ATTEMPTS)
    if state.get('job_id')!=f"{p['job_id']}.{stage}.{state['attempts']}":
        raise ValueError('Completed stage identity differs from its declared attempt')
    reference=_reference(state.get('artifact_ref'))
    if not _same(p['artifacts'].get(STAGE_ARTIFACTS[stage]),reference):
        raise ValueError('Completed stage artifact and retained artifact reference differ')
    job=lab.store.get_job(state['job_id'])
    expected={'stage':stage,'cycle_id':p['cycle_id'],'plan_hash':p['plan_hash'],'artifact_ref':reference}
    if not job or job['status']!='completed' or not _same(job['payload'],expected):
        raise ValueError('Completed stage lacks its exact authoritative child-job binding')
    saved=_resolve(lab,reference,current=not historical)
    if not historical:
        _validate_output(lab,p,stage,saved)
    return saved


def _checkpoint_bindings(lab,obj,*,historical):
    p=copy.deepcopy(obj['payload']);p['cycle_id']=obj['id']
    initial=lab.store.get(obj['id'],1)['payload']
    if (type(p.get('job_id')) is not str or p['job_id']!=initial.get('job_id') or
            obj['id']!='research_cycle-'+hashlib.sha256(p['job_id'].encode('utf-8')).hexdigest()[:20] or
            not _same(p.get('plan'),initial.get('plan')) or p.get('plan_hash')!=initial.get('plan_hash')):
        raise ValueError('Checkpoint root/cycle identity or original immutable plan changed')
    if (type(p.get('stages')) is not dict or set(p['stages'])!=set(STAGES) or
            type(p.get('artifacts')) is not dict or p.get('completion_scope')!=_completion_scope(p['plan'])):
        raise ValueError('Checkpoint stage declarations or evidence scope are invalid')
    allowed_kinds={'construct':('environment_blueprint',),'register':tuple(DISPATCH),
        'execute':tuple(value[1] for value in DISPATCH.values()),'audit':('verification',),
        'claims':('claim_audit',),'curate':('theory',)}
    allowed_artifacts=set(STAGE_ARTIFACTS.values())|{'incomplete_result'}
    if not set(p['artifacts'])<=allowed_artifacts:
        raise ValueError('Unknown retained checkpoint artifact')
    for key,reference in p['artifacts'].items():
        checked=_reference(reference)
        stage=next((s for s,k in STAGE_ARTIFACTS.items() if k==key),'execute')
        if checked['kind'] not in allowed_kinds[stage]:
            raise ValueError('Retained artifact kind differs from its stage')
    complete=[];seen_incomplete=False
    for stage in STAGES:
        state=p['stages'][stage]
        if (type(state) is not dict or not {'status','attempts','job_id','artifact_ref'}<=set(state) or
                not set(state)<={'status','attempts','job_id','artifact_ref','error','failure_code'} or
                type(state.get('status')) is not str or
                state['status'] not in ('pending','running','completed','failed','blocked')):
            raise ValueError('Unknown checkpoint stage state')
        attempts=_integer(state['attempts'],'Stage attempts',0,MAX_SAFE_ATTEMPTS)
        if attempts==0:
            if state['job_id'] is not None or state['artifact_ref'] is not None or state['status'] in ('running','completed'):
                raise ValueError('Unclaimed stage cannot contain an execution identity or artifact')
        elif (type(state['job_id']) is not str or state['job_id']!=f"{p['job_id']}.{stage}.{attempts}" or
                state['status']=='pending'):
            raise ValueError('Claimed stage identity differs from its exact typed attempt')
        for key,limit in (('error',2000),('failure_code',100)):
            if key in state and (type(state[key]) is not str or len(state[key])>limit):
                raise ValueError('Invalid bounded stage failure metadata')
        if state['status'] in ('failed','blocked') and not {'error','failure_code'}<=set(state):
            raise ValueError('Failed stage lacks its retained failure metadata')
        retained=p['artifacts'].get(STAGE_ARTIFACTS[stage])
        if state['artifact_ref'] is not None:
            reference=_reference(state['artifact_ref'])
            if reference['kind'] not in allowed_kinds[stage] or not _same(reference,retained):
                raise ValueError('Stage artifact reference differs from its typed retained artifact')
        elif retained is not None:
            raise ValueError('Retained stage artifact lacks its stage reference')
        if seen_incomplete and state['status']!='pending':
            raise ValueError('A later stage cannot advance beyond an incomplete earlier stage')
        if state['status']!='completed':seen_incomplete=True
        complete.append(state['status']=='completed')
        if state['status']=='completed':
            _completed_binding(lab,p,stage,historical=historical)
    if p.get('status')=='completed':
        if p.get('phase')!='completed' or not all(complete):
            raise ValueError('Completed cycle lacks its entire completed stage graph')
        _theory(lab,p,_resolve(lab,p['artifacts']['theory'],current=not historical),historical=historical)
    elif p.get('status') in ('failed','blocked'):
        phase=p.get('phase')
        if phase not in STAGES or p['stages'][phase]['status']!=p['status']:
            raise ValueError('Failed/blocked checkpoint does not identify its incomplete phase')
        if all(complete):
            raise ValueError('Failed/blocked checkpoint cannot claim every stage completed')
    root=lab.store.get_job(p['job_id'])
    if p.get('status')!='completed' and root and root['status']=='completed':
        raise ValueError('Noncompleted checkpoint contradicts the authoritative completed root job')


def _terminal_closure(lab,obj):
    p=obj['payload'];job=lab.store.get_job(p['job_id'])
    expected={'stage':'research_cycle','cycle_id':obj['id'],'cycle_ref':_ref(obj),
              'plan_hash':p['plan_hash'],'artifacts':p['artifacts']}
    if p['status']!='completed':
        expected.update(phase=p['phase'],cycle_status=p['status'],error=p['stages'][p['phase']].get('error'))
    if not job or job['status']!=('completed' if p['status']=='completed' else 'failed') or not _same(job['payload'],expected):
        raise ValueError('Terminal checkpoint has no exact authoritative root-job closure; reconcile rather than reassert completion')


def _conflict_checkpoint(lab,obj,p):
    latest=lab.store.get(obj['id'])
    lab.store.trace(p['job_id'],{'type':'research_cycle_checkpoint_conflict','cycle_id':obj['id'],
        'expected_cycle_ref':_ref(obj),'latest_cycle_ref':_ref(latest),
        'active_phase':p.get('phase'),'known_artifact_refs':p.get('artifacts',{}),
        'scope':'Another writer advanced the checkpoint. These artifact identities are retained; no outcome or stage completion is invented.'})
    _checkpoint_bindings(lab,latest,historical=True)
    if latest['payload']['status'] in ('completed','blocked','failed'):
        _terminal_closure(lab,latest)
    return latest


def _guard(lab, p, *, pending_artifact_append=False):
    plan = p['plan']
    if p['plan_hash'] != _digest(plan) or not _same(plan['code_hashes'], _code_hashes()):
        raise _Blocked('implementation_drift', 'Cycle plan or implementing source hashes changed')
    if p.get('completion_scope')!=_completion_scope(plan):
        raise _Blocked('evidence_scope_changed','Checkpoint evidence scope contradicts its original execution mode')
    if lab.settings.model != plan['execution']['requested_model']:
        raise _Blocked('backend_drift', 'Requested model differs from the frozen cycle plan')
    _resolve(lab, p['authorized_behavior_append'] or plan['behavior_ref'],
             current=not pending_artifact_append)
    for ref in plan['source_refs'].values():
        _resolve(lab, ref)
    for ref in p['artifacts'].values():
        _resolve(lab, ref)
    if lab.store.usage()['calls'] > plan['budget']['absolute_call_ceiling']:
        raise _Blocked('budget_exhausted', 'Absolute cycle budget has already been exceeded by recorded calls')


def _limited_lab(lab, p):
    bounded = copy.copy(lab)
    bounded.settings = replace(lab.settings,
        max_calls=min(lab.settings.max_calls, p['plan']['budget']['absolute_call_ceiling']))
    return bounded


def _attempt_refs(lab, p, job_id):
    matches = [o for o in lab.store.list('environment_construction_attempt', limit=10000)
               if o['payload'].get('research_job_id') == job_id]
    if len(matches) > 1:
        raise _Blocked('ambiguous_construction', 'Several authoring attempts share this stage identity')
    if matches:
        p['construction_attempt_refs'] = [_ref(o) for o in lab.store.history(matches[0]['id'])]
    return matches


def _blueprint(lab, p, obj):
    if obj['kind'] != 'environment_blueprint':
        raise _Blocked('wrong_blueprint_kind', 'Construction did not return an environment blueprint')
    value = obj['payload']
    expected = [p['plan']['behavior_ref'], *p['plan']['source_refs'].values()]
    if value.get('behavior_id') != p['plan']['behavior_ref']['id'] or not _same(value.get('source_refs'), expected):
        raise _Blocked('blueprint_source_mismatch', 'Authored world is not bound to the exact selected behavior/sources')
    if value.get('construction_status') != 'compiled' or value.get('experiment_eligibility') != 'approved_analogue':
        raise _Blocked('construction_or_fit_blocked', 'Construction/semantic fit is unsupported, invalid or not approved')
    if not _same(value.get('trusted_required_capabilities'), p['plan']['construction']['required_capabilities']):
        raise _Blocked('capability_binding_mismatch', 'Trusted capabilities changed during construction')
    return obj


def _protocol(lab, p, obj):
    from .library import verify_protocol
    if obj['kind'] not in DISPATCH:
        raise _Blocked('unsupported_design', 'No allowlisted registered runner supports this protocol kind')
    blueprint = _resolve(lab, p['artifacts']['blueprint'])
    wrapper = obj['payload']
    if wrapper.get('behavior_id') != p['plan']['behavior_ref']['id'] or not _same(
            wrapper.get('environment_blueprint_ref'), _ref(blueprint)):
        raise _Blocked('registration_binding_mismatch', 'Registration does not bind the exact selected world/behavior')
    protocol = verify_protocol(obj)
    actual = protocol.get('environment')
    if actual is None:
        envs = protocol.get('environments', {})
        if len(envs) != 1:
            raise _Blocked('world_substitution', 'Authored registration must preserve exactly one authored topology')
        actual = next(iter(envs.values()))
    if not _same(actual, blueprint['payload']['spec']):
        raise _Blocked('world_substitution', 'Registered world differs from the approved authored spec')
    design = protocol['design']
    count = design.get('trials_per_cell', design.get('trials_per_arm'))
    if type(count) is not int or count != p['plan']['design']['trials_per_cell']:
        raise _Blocked('design_mismatch', 'Registered allocation differs from the frozen requested allocation')
    # Some runners call the allocation seed randomization_seed.
    seed = design.get('seed', design.get('randomization_seed'))
    if seed is not None and (type(seed) is not int or seed != p['plan']['design']['seed']):
        raise _Blocked('design_mismatch', 'Registered seed differs from the frozen cycle plan')
    expected_mode = 'live' if p['plan']['execution']['subjects_live'] else 'offline_template'
    if wrapper.get('agent_mode') != expected_mode:
        raise _Blocked('backend_mismatch', 'Registration live/offline mode differs from the frozen plan')
    return obj


def _result(lab, p, obj):
    registration = _resolve(lab, p['artifacts']['protocol'])
    expected_kind = DISPATCH[registration['kind']][1]
    payload = obj['payload']
    expected_mode = 'live' if p['plan']['execution']['subjects_live'] else 'offline_simulation'
    if obj['kind'] != expected_kind or payload.get('protocol_id') != registration['id']:
        raise _Blocked('result_binding_mismatch', 'Executed result does not belong to this exact registered design')
    if payload.get('agent_mode') != expected_mode or payload.get('model') != registration['payload']['protocol']['subject_backend']['model']:
        raise _Blocked('result_backend_mismatch', 'Executed backend differs from the registered backend')
    if payload.get('research_job_id') != p['stages']['execute']['job_id']:
        raise _Blocked('execution_identity_mismatch', 'Executed result has a different fixed job identity')
    if payload.get('status') != 'complete':
        raise _Blocked('incomplete_execution', 'Incomplete execution cannot supply outcome facts or a theory')
    digest = payload.get('canonical_execution_report_hash')
    if type(digest) is not str or not re.fullmatch(r'[0-9a-f]{64}', digest):
        raise _Blocked('report_binding_missing', 'Canonical execution report binding is absent')
    _read_report(lab, p, obj)
    return obj


def _read_report(lab, p, result):
    """Bind current local archive bytes; do not execute archived source."""
    directory = lab.settings.runtime / 'runs' / p['stages']['execute']['job_id']
    value = result['payload']
    if type(value.get('artifact_directory')) is not str or Path(value['artifact_directory']).resolve() != directory.resolve():
        raise _Blocked('archive_identity_mismatch', 'Execution directory differs from its fixed child job identity')
    path = directory / 'report.json'
    if not path.is_file() or path.stat().st_size > 32 * 1024 * 1024:
        raise _Blocked('archive_missing_or_oversize', 'A bounded canonical execution report is required')
    def unique(pairs):
        answer = {}
        for key, item in pairs:
            if key in answer:
                raise ValueError('Duplicate JSON keys in execution report')
            answer[key] = item
        return answer
    raw = json.loads(path.read_bytes().decode('utf-8'), object_pairs_hook=unique,
                     parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite execution JSON')))
    body = {k: v for k, v in raw.items() if k != 'report_hash'}
    encoded = _json(body, max_bytes=32 * 1024 * 1024, max_nodes=1000000)
    registered = _resolve(lab, p['artifacts']['protocol'])['payload']['protocol']
    exact = lambda a, b: _json(a, max_bytes=32 * 1024 * 1024, max_nodes=1000000) == _json(b, max_bytes=32 * 1024 * 1024, max_nodes=1000000)
    if (hashlib.sha256(encoded).hexdigest() != raw.get('report_hash') or
            raw.get('report_hash') != value['canonical_execution_report_hash'] or
            raw.get('status') != 'complete' or not _same(raw.get('protocol'), registered) or
            not exact(raw.get('analysis'), value.get('analysis')) or
            not exact(raw.get('runs'), value.get('runs'))):
        raise _Blocked('archive_report_mismatch', 'Current canonical archive, registered result and frozen protocol disagree')
    return raw


def _proof(lab, p, obj):
    result = _resolve(lab, p['artifacts']['result'])
    value = obj['payload']
    if obj['kind'] != 'verification' or value.get('experiment_id') != result['id'] or value.get('result_kind') != result['kind'] or not _same(
            value.get('result_ref'), {k: result[k] for k in ('id', 'version', 'hash')}):
        raise _Blocked('proof_binding_mismatch', 'Replay proof does not bind the exact retained result')
    if value.get('passed') is not True or type(value.get('model_calls')) is not int or value['model_calls'] != 0:
        raise _Blocked('independent_replay_failed', 'Independent CPU replay did not pass')
    checks = value.get('checks')
    if type(checks) is not list or not checks or any(c.get('passed') is not True for c in checks):
        raise _Blocked('independent_replay_failed', 'Replay checks are missing or not all passing')
    if value.get('execution_archive', {}).get('status') != 'verified':
        raise _Blocked('execution_archive_failed', 'Execution source archive bytes were not independently checked')
    directory = Path(result['payload']['artifact_directory']) / 'execution-code'
    manifest_path = directory / 'manifest.json'
    if not manifest_path.is_file() or manifest_path.stat().st_size > 1024 * 1024:
        raise _Blocked('execution_archive_failed', 'Source manifest is absent or oversized')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    expected = _resolve(lab, p['artifacts']['protocol'])['payload']['protocol']['execution_code_hashes']
    for name, digest in expected.items():
        source = directory / name
        if (Path(name).name != name or manifest.get('files', {}).get(name) != digest or
                not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != digest):
            raise _Blocked('execution_archive_failed', 'Archived reviewed source does not match the frozen protocol pins')
    return obj


def _claims(lab, p, obj):
    result = _resolve(lab, p['artifacts']['result'])
    value = obj['payload']
    if obj['kind'] != 'claim_audit' or value.get('experiment_id') != result['id'] or value.get('result_kind') != result['kind'] or not _same(
            value.get('result_ref'), {k: result[k] for k in ('id', 'version', 'hash')}):
        raise _Blocked('claim_binding_mismatch', 'Finite claims do not bind the exact retained result')
    if value.get('canonical_execution_report_hash') != result['payload']['canonical_execution_report_hash']:
        raise _Blocked('claim_report_mismatch', 'Finite claim report binding changed')
    if value.get('status') != 'verified_facts_only' or value.get('audit', {}).get('all_executable_claims_supported') is not True:
        raise _Blocked('finite_claims_unavailable', 'Finite fact checks did not all pass; no outcome curation is allowed')
    if value.get('agent_mode') != 'offline_fact_reconstruction' or not value.get('fact_packet', {}).get('facts'):
        raise _Blocked('finite_claims_unavailable', 'Cycle fact checking requires the deterministic nonempty fact packet')
    from .claim_audit import build_fact_ledger, select_fact_packet, audit_claims
    raw = _read_report(lab, p, result)
    if result['kind'] == 'resource_experiment':
        from .resource_claims import build_resource_fact_ledger
        ledger = build_resource_fact_ledger(raw, report_id=result['id'],
            source_ref={k: result[k] for k in ('id', 'version', 'hash')}, source_object=result)
    else:
        from .audit import replay_report
        ledger = build_fact_ledger(raw, report_id=result['id'], replay_check=replay_report)
    packet = select_fact_packet(ledger, list(value['fact_packet']['facts']), max_facts=24)
    recomputed = audit_claims(ledger, value.get('claims', []))
    if (not _same(packet, value['fact_packet']) or not _same(recomputed, value.get('audit')) or
            recomputed.get('all_executable_claims_supported') is not True or
            len(value.get('claims', [])) != len(packet['facts']) or
            set(recomputed.get('supported_fact_ids', [])) != set(packet['facts'])):
        raise _Blocked('finite_claims_recheck_failed', 'Exact finite packet and typed claims do not recompute from the retained replayable report')
    return obj


def _validate_output(lab, p, stage, obj):
    if type(obj) is not dict:
        raise _Blocked('missing_stage_artifact', 'Stage did not return a saved artifact')
    saved = _resolve(lab, _reference(_ref(obj)))
    validators = {'construct': _blueprint, 'register': _protocol,
                  'execute': _result, 'audit': _proof, 'claims': _claims}
    if stage in validators:
        return validators[stage](lab, p, saved)
    return _theory(lab,p,saved)


def _authorized_append(lab, p, result):
    """Recognize only the existing artifact runner's intentional library append."""
    original = _resolve(lab, p['plan']['behavior_ref'], current=False)
    current = lab.store.get(original['id'])
    if _same(_ref(current), _ref(original)):
        return
    if result['kind'] != 'experiment' or current['version'] != original['version'] + 1:
        raise _Blocked('version_drift', 'Behavior changed during execution outside the authorized artifact evidence append')
    old = original['payload']; new = current['payload']
    allowed = {'experiment_ids', 'status', 'evidence_level', 'causal_support'}
    if not _same({k: v for k, v in old.items() if k not in allowed},
                 {k: v for k, v in new.items() if k not in allowed}):
        raise _Blocked('version_drift', 'Behavior source/semantic fields changed during execution')
    expected_ids = list(dict.fromkeys(old.get('experiment_ids', []) + [result['id']]))
    if not _same(new.get('experiment_ids'), expected_ids):
        raise _Blocked('version_drift', 'Behavior evidence append has unexpected experiment IDs')
    live = result['payload']['agent_mode'] == 'live' or any(
        lab.store.get(i)['payload'].get('agent_mode') == 'live' for i in old.get('experiment_ids', []))
    expected_status = old.get('status') if old.get('status') in ('rejected', 'replication_tested') else ('pilot_tested' if live else 'infrastructure_tested')
    expected_level = old.get('evidence_level') if old.get('evidence_level') == 'controlled_abstraction_with_held_out_seed_test' else ('controlled_abstraction_pilot' if live else 'scripted_infrastructure_check')
    expected_support = ('Only the registered synthetic environment and tested subject model; historical causal support remains absent.' if live else
                        'No evidence about LLM behavior; deterministic policy tests infrastructure only.')
    if not _same([new.get('status'), new.get('evidence_level'), new.get('causal_support')],
                 [expected_status, expected_level, expected_support]):
        raise _Blocked('version_drift', 'Behavior append does not match the existing conservative library contract')
    p['authorized_behavior_append'] = _ref(current)


def _curation_payload(p,blueprint,registration,result):
    proposed = blueprint['payload']['proposed_blueprint']
    refs = {'behavior': p['plan']['behavior_ref'], **p['plan']['source_refs'],
            **{key: p['artifacts'][key] for key in ('blueprint', 'protocol', 'result', 'verification', 'claim_audit')}}
    payload = {'title': proposed['title'] + ': untested analogue hypothesis',
        'statement': proposed['mechanism_hypothesis'], 'mechanism': proposed['mechanism_hypothesis'],
        'status': 'hypothesis', 'agent_mode': 'offline_blueprint_curation',
        'research_cycle_id': p['cycle_id'], 'research_job_id': p['stages']['curate']['job_id'],
        'behavior_ids': [p['plan']['behavior_ref']['id']], 'experiment_ids': [result['id']],
        'source_refs': copy.deepcopy(refs), 'hypothesis_origin': 'Supplied or agent-authored blueprint; statement is not a verified finding',
        'mechanism_support': 'unestablished', 'generalization': 'unestablished',
        'historical_causal_support': 'none', 'replication_status': 'unreplicated', 'replication_ids': [],
        'supporting_results': [], 'conflicting_results': [],
        'scope': {'world_kind': blueprint['payload']['spec']['kind'], 'spec_hash': blueprint['payload']['spec_hash'],
            'subject_backend': registration['payload']['protocol']['subject_backend'],
            'evidence_scope': _completion_scope(p['plan']), 'historical_fidelity': 'unestablished'},
        'predictions': ['The proposed mechanism needs a separately operationalized, preregistered prediction; this completed predefined contrast does not supply one automatically.'],
        'rival_theories': ['Generic instruction following or note salience can explain a context contrast.',
            'Allocated action budgets, scheduling and message opportunity can explain task performance without the proposed social mechanism.'],
        'falsifiers': ['A predeclared mechanistic contrast fails its directional prediction under fresh seeds with adequate uncertainty resolution.',
            'Comparable task outcomes persist after removing the proposed capability while preserving task feasibility.'],
        'boundary_conditions': proposed['unmodeled_features'],
        'limitations': ['Finite facts and executed state transitions alone are checked; this mechanism statement remains untested.',
            'Scripted execution provides no evidence about LLM behavior.' if not p['plan']['execution']['subjects_live'] else
            'A synthetic model pilot does not identify a historical mechanism or population generalization.',
            'No mediator, institutional novelty, replication or freedom from confounding is established.'],
        'version_reason': 'Guarded cycle curation; behavior status is not changed'}
    return payload


def _theory(lab,p,obj,*,historical=False):
    identity='theory-cycle-'+hashlib.sha256(p['cycle_id'].encode()).hexdigest()[:20]
    if obj['kind']!='theory' or obj['id']!=identity or type(obj['version']) is not int or obj['version']!=1:
        raise _Blocked('curation_binding_mismatch','Curation identity/kind/version differs from its guarded initial hypothesis')
    blueprint=_resolve(lab,p['artifacts']['blueprint'],current=not historical)
    registration=_resolve(lab,p['artifacts']['protocol'],current=not historical)
    result=_resolve(lab,p['artifacts']['result'],current=not historical)
    expected=_curation_payload(p,blueprint,registration,result)
    if not _same(obj['payload'],expected):
        raise _Blocked('curation_binding_mismatch','Curation status, scope, pins or generated hypothesis fields changed')
    return obj


def _curate(lab, p):
    """Local guard for new kinds; never call the legacy artifact theory template."""
    result = _result(lab, p, _resolve(lab, p['artifacts']['result']))
    _proof(lab, p, _resolve(lab, p['artifacts']['verification']))
    _claims(lab, p, _resolve(lab, p['artifacts']['claim_audit']))
    blueprint = _blueprint(lab, p, _resolve(lab, p['artifacts']['blueprint']))
    registration = _protocol(lab, p, _resolve(lab, p['artifacts']['protocol']))
    payload=_curation_payload(p,blueprint,registration,result)
    identity = 'theory-cycle-' + hashlib.sha256(p['cycle_id'].encode()).hexdigest()[:20]
    history = lab.store.history(identity)
    if history:
        if len(history) != 1 or not _same(history[0]['payload'], payload):
            raise _Blocked('curation_identity_conflict', 'Existing cycle theory does not match the guarded packet')
        return history[0]
    return lab.store.put('theory', payload, identity)


def _run_stage(lab, p, stage):
    c = p['plan']['construction']; e = p['plan']['execution']; job = p['stages'][stage]['job_id']
    if stage == 'construct':
        if c['mode'] == 'existing_blueprint':
            return _resolve(lab, c['blueprint_ref'])
        return lab.construct_environment(behavior_id=p['plan']['behavior_ref']['id'],
            research_question=c['research_question'], required_capabilities=c['required_capabilities'],
            proposal=c['proposal'], fit_review=c['fit_review'], live=e['research_live'],
            harness=e['research_harness'], job_id=job, audit_seed=c['audit_seed'])
    if stage == 'register':
        try:
            return lab.register_blueprint(p['artifacts']['blueprint']['id'],
                trials_per_cell=p['plan']['design']['trials_per_cell'],
                seed=p['plan']['design']['seed'], live=e['subjects_live'])
        except ValueError as error:
            raise _Blocked('design_incompatible', str(error)) from error
    if stage == 'execute':
        registered = _resolve(lab, p['artifacts']['protocol'])
        method = getattr(lab, DISPATCH[registered['kind']][0])
        kwargs = {'live': e['subjects_live'], 'job_id': job}
        if registered['kind'] == 'protocol':
            kwargs['harness'] = e['subject_harness']
        return method(registered['id'], **kwargs)
    if stage == 'audit':
        return lab.audit(p['artifacts']['result']['id'])
    if stage == 'claims':
        # Fact reconstruction and checking never imply a research/model call.
        return lab.evaluate_claims(p['artifacts']['result']['id'], live=False, job_id=job)
    return _curate(lab, p)


def _recover(lab, p, stage):
    """Return only artifacts that have an exact retained stage identity."""
    state = p['stages'][stage]; job = lab.store.get_job(state['job_id'])
    if job and job['payload'].get('artifact_ref'):
        return _resolve(lab, job['payload']['artifact_ref'])
    if stage == 'execute':
        if job and job['payload'].get('result_id'):
            return lab.store.get(job['payload']['result_id'])
        if job and job['payload'].get('incomplete_result_id'):
            failed = lab.store.get(job['payload']['incomplete_result_id'])
            p['artifacts']['incomplete_result'] = _ref(failed)
            raise _Blocked('incomplete_execution', 'Execution failed; retained incomplete result cannot be rerun under this identity')
        registered = _resolve(lab, p['artifacts']['protocol'])
        candidates = [o for o in lab.store.list(DISPATCH[registered['kind']][1], limit=10000)
            if o['payload'].get('research_job_id') == state['job_id'] and o['payload'].get('protocol_id') == registered['id']]
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            raise _Blocked('ambiguous_execution', 'Multiple results share one execution identity')
    if stage == 'construct':
        attempts = _attempt_refs(lab, p, state['job_id'])
        if attempts and attempts[0]['payload'].get('blueprint_id'):
            return lab.store.get(attempts[0]['payload']['blueprint_id'])
    if stage == 'curate':
        identity = 'theory-cycle-' + hashlib.sha256(p['cycle_id'].encode()).hexdigest()[:20]
        history = lab.store.history(identity)
        if history:
            return _curate(lab, p)
    if stage in ('construct', 'register', 'execute'):
        raise _Blocked('uncertain_stage_completion',
            'This claimed stage has no authoritative completed artifact; it is not automatically relaunched. Inspect retained job/attempt/archive evidence or create an explicitly amended cycle.')
    return None


def _preflight(lab, p, stage):
    if stage == 'construct' and p['plan']['execution']['research_live']:
        if lab.store.usage()['calls'] >= lab.settings.max_calls:
            raise _Blocked('budget_exhausted', 'No authorized research calls remain')
    if stage == 'execute':
        registration = _resolve(lab, p['artifacts']['protocol'])
        if not p['plan']['execution']['subjects_live']:
            return
        protocol = registration['payload']['protocol']
        if 'maximum_subject_calls' in protocol['design']:
            maximum = protocol['design']['maximum_subject_calls']
        elif 'environment' in protocol:
            maximum = protocol['design']['trials_per_arm'] * len(protocol['arms']) * protocol['environment']['max_rounds'] * len(protocol['environment']['agents'])
        else:
            maximum = protocol['design']['trials_per_cell'] * len(protocol['design']['cells']) * max(
                s['max_rounds'] * len(s['agents']) for s in protocol['environments'].values())
        if type(maximum) is not int or lab.store.usage()['calls'] + maximum > lab.settings.max_calls:
            raise _Blocked('subject_budget_insufficient', 'Entire registered worst-case subject allocation must fit the original absolute cycle/global call ceiling')


def _drive(original_lab, obj):
    p = copy.deepcopy(obj['payload']); p['cycle_id'] = obj['id']
    lab = _limited_lab(original_lab, p)
    phase = p.get('phase', 'construct')
    try:
        for stage in STAGES:
            state = p['stages'][stage]
            if state['status'] == 'completed':
                # Before new work, cached completion must retain exact child
                # authority and executable evidence, not a stage-status flag.
                _completed_binding(lab,p,stage,historical=False)
                continue
            phase = stage; p['phase'] = stage
            pending_append = (stage == 'execute' and state['status'] in ('running', 'failed') and
                p['artifacts'].get('protocol', {}).get('kind') == 'protocol' and
                p['authorized_behavior_append'] is None)
            # A completed artifact runner may have appended library evidence
            # before its return/checkpoint was interrupted. Recover its exact
            # result first, then validate the limited change; never relaunch it.
            _guard(lab, p, pending_artifact_append=pending_append)
            recovered = None
            if state['status'] in ('running', 'failed') and state['job_id'] is not None:
                recovered = _recover(lab, p, stage)
            if recovered is None:
                # A retained authoritative artifact needs verification, not a
                # second reservation for the already executed subject budget.
                # Apply new-work quota checks only when work will be launched.
                _preflight(lab, p, stage)
                if state['attempts'] >= MAX_SAFE_ATTEMPTS:
                    raise _Blocked('retry_limit', 'Bounded safe-stage attempts exhausted; subjects were not relaunched')
                state['attempts'] += 1
                state['job_id'] = f"{p['job_id']}.{stage}.{state['attempts']}"
                lab.store.start_job(state['job_id'], {'stage': stage, 'cycle_id': obj['id'], 'plan_hash': p['plan_hash']})
                state['status'] = 'running'; state.pop('error', None)
                obj = _save(lab, obj, p)
                recovered = _run_stage(lab, p, stage)
            # Retain a returned artifact before rejecting semantic eligibility.
            state['artifact_ref'] = _ref(recovered)
            key = STAGE_ARTIFACTS[stage]
            p['artifacts'][key] = _ref(recovered)
            if stage == 'construct':
                _attempt_refs(lab, p, state['job_id'])
            validated = _validate_output(lab, p, stage, recovered)
            if stage == 'execute':
                _authorized_append(lab, p, validated)
            state.update(status='completed', artifact_ref=_ref(validated))
            obj = _save(lab, obj, p)
        p.update(status='completed', phase='completed', completed_at=now(),
            model_calls_at_checkpoint=lab.store.usage()['calls'])
        obj = _save(lab, obj, p)
        return obj
    except StoreConflictError:
        return _conflict_checkpoint(lab,obj,p)
    except Exception as error:
        if phase == 'construct' and p['stages'][phase].get('job_id'):
            try:
                _attempt_refs(lab, p, p['stages'][phase]['job_id'])
            except Exception:
                pass
        state = p['stages'][phase]
        failed_job = lab.store.get_job(state['job_id']) if state.get('job_id') else None
        if failed_job and failed_job['payload'].get('incomplete_result_id'):
            failure = lab.store.get(failed_job['payload']['incomplete_result_id'])
            p['artifacts']['incomplete_result'] = _ref(failure)
        blocked = isinstance(error, _Blocked)
        code = error.code if blocked else 'stage_failure'
        state.update(status='blocked' if blocked else 'failed', error=str(error)[:2000], failure_code=code)
        p.update(status='blocked' if blocked else 'failed', phase=phase,
                 model_calls_at_checkpoint=lab.store.usage()['calls'])
        p['failures'].append({'phase': phase, 'code': code, 'error': str(error)[:2000],
                              'job_id': state.get('job_id'), 'recorded_at': now()})
        if blocked:
            p['extension_requirements'].append({'phase': phase, 'code': code,
                'requirement': str(error)[:2000], 'implicit_fallback': False})
        try:
            obj = _save(lab, obj, p)
        except StoreConflictError:
            return _conflict_checkpoint(lab,obj,p)
        return obj
