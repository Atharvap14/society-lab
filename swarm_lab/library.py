"""Versioned behavior/theory objects with conservative evidence gates."""
import copy
import hashlib
from .store import fingerprint, now
from .measurement_context import reference_matches

STATUSES=('candidate','hypothesis','infrastructure_tested','pilot_tested','replication_tested','rejected')

def validate_measurement_audit_refs(store,measurement_refs,candidate_id,dataset,discovery):
    """Read-only source/selection checks shared by registration and resume."""
    if type(measurement_refs) is not list or len(measurement_refs)>5:
        raise ValueError('Behavior measurement audit reference mismatch')
    bound={kind:{k:obj[k] for k in ('id','version','hash')}
           for kind,obj in (('dataset',dataset),('discovery',discovery))}
    for ref in measurement_refs:
        if (type(ref) is not dict or set(ref)!={'id','version','hash'} or
            type(ref.get('version')) is not int or ref['version']<1 or
            type(ref.get('id')) is not str or type(ref.get('hash')) is not str):
            raise ValueError('Behavior measurement audit reference mismatch')
        audit=store.get(ref['id'],ref['version'])
        if audit['kind'] not in ('selected_lead_audit','temporal_path_audit') or not reference_matches(ref,audit):
            raise ValueError('Behavior measurement audit reference mismatch')
        if audit['kind']=='selected_lead_audit':
            matched=(fingerprint(audit['payload'].get('source_refs'))==fingerprint(bound) and
                     candidate_id in [row.get('lead_id') for row in audit['payload'].get('per_lead',[])])
        else:
            parent=audit['payload'].get('selected_audit_ref',{})
            if (type(parent) is not dict or type(parent.get('version')) is not int or
                parent['version']<1 or type(parent.get('id')) is not str):
                raise ValueError('Behavior measurement audit reference mismatch')
            selected=store.get(parent['id'],parent['version'])
            original=next((row.get('registered',{}) for row in selected['payload'].get('per_lead',[]) if row.get('lead_id')==candidate_id),None)
            comparison=next((row for row in audit['payload'].get('original_comparisons',[]) if row.get('id')==candidate_id),None)
            matched=(selected['kind']=='selected_lead_audit' and reference_matches(parent,selected)
                and reference_matches(audit['payload'].get('source_refs',{}).get('selected_audit'),selected)
                and any(reference_matches(saved,selected) for saved in measurement_refs)
                and fingerprint(selected['payload'].get('source_refs'))==fingerprint(bound)
                and all(fingerprint(audit['payload'].get('source_refs',{}).get(kind))==fingerprint(bound[kind]) for kind in bound)
                and original is not None and comparison is not None
                and all(comparison.get(key)==original.get(key) for key in ('id','feature','window_id','comparison_window_id')))
        if not matched:
            raise ValueError('Behavior measurement audit belongs to another source or lead')


def register_behavior(store,research,dataset_id,discovery_id,source_refs=None):
    proposal=research['proposal']
    if not proposal.get('evidence_ids'):raise ValueError('Behavior requires source evidence')
    discovery=store.get(discovery_id,(source_refs or {}).get('discovery',{}).get('version'))
    dataset_ref=discovery['payload'].get('dataset_ref',{})
    dataset=store.get(dataset_id,dataset_ref.get('version') or (source_refs or {}).get('dataset',{}).get('version'))
    if discovery['kind']!='discovery' or dataset['kind']!='dataset':raise ValueError('Behavior source kinds do not match dataset/discovery')
    if dataset_ref and not reference_matches(dataset_ref,dataset):raise ValueError('Discovery is bound to a different dataset version')
    if source_refs:
        for kind,obj in (('discovery',discovery),('dataset',dataset)):
            if not reference_matches(source_refs[kind],obj):raise ValueError('Research source version/hash differs from registration')
    cited=set(proposal.get('evidence_ids',[])+proposal.get('comparison_ids',[])+research['skeptic'].get('evidence_ids',[]))
    if cited-{m['id'] for m in dataset['payload']['messages']}:raise ValueError('Behavior cites unknown records in its pinned dataset')
    measurement_refs=research.get('measurement_audit_refs',[])
    attempt_ref=research.get('research_attempt_ref')
    if attempt_ref is not None:
        if (type(attempt_ref) is not dict or set(attempt_ref)!={'id','version','hash'} or
            type(attempt_ref.get('version')) is not int or attempt_ref['version']<1 or
            type(attempt_ref.get('id')) is not str or type(attempt_ref.get('hash')) is not str):
            raise ValueError('Behavior research attempt requires an exact reference')
        attempt=store.get(attempt_ref['id'],attempt_ref['version']);saved=attempt['payload']
        expected_sources={kind:{key:obj[key] for key in ('id','version','hash')}
                          for kind,obj in (('dataset',dataset),('discovery',discovery))}
        saved_measurement=saved.get('measurement_context')
        if (attempt['kind']!='research_attempt' or not reference_matches(attempt_ref,attempt) or
            attempt_ref['id']!=research.get('research_attempt_id') or
            fingerprint(saved.get('source_refs'))!=fingerprint(expected_sources) or
            type(saved.get('candidate')) is not dict or saved['candidate'].get('id')!=research['candidate_id'] or
            fingerprint(saved.get('proposal'))!=fingerprint(proposal) or
            type(saved_measurement) is not dict or type(saved_measurement.get('audits')) is not list or
            fingerprint([entry.get('ref') for entry in saved_measurement['audits'] if type(entry) is dict])!=fingerprint(measurement_refs) or
            any(type(entry) is not dict for entry in saved_measurement['audits'])):
            raise ValueError('Behavior research attempt belongs to another source, proposal or context')
    validate_measurement_audit_refs(store,measurement_refs,research['candidate_id'],dataset,discovery)
    payload={**proposal,'status':'rejected' if research['skeptic']['recommended_status']=='reject' or proposal.get('viability')!='candidate' else 'candidate',
        'evidence_level':'observational_candidate','causal_support':'none','novelty_status':'not_established',
        'dataset_id':dataset_id,'discovery_id':discovery_id,'candidate_id':research['candidate_id'],
        'source_refs':{'dataset':{k:dataset[k] for k in ('id','version','hash')},'discovery':{k:discovery[k] for k in ('id','version','hash')}},
        'skeptic':research['skeptic'],'agent_mode':research['agent_mode'],'harness':research['harness'],
        'research_attempt_id':research.get('research_attempt_id'),
        'research_attempt_ref':copy.deepcopy(attempt_ref),
        'measurement_audit_refs':copy.deepcopy(measurement_refs),
        'experiment_ids':[],'theory_ids':[]}
    return store.put('behavior',payload)

def record_experiment(store,behavior_id,result_object):
    if result_object['payload'].get('status')!='complete':
        raise ValueError('Incomplete experiments cannot promote a behavioral claim')
    if result_object['kind']!='experiment' or result_object['payload'].get('behavior_id')!=behavior_id:
        raise ValueError('Experiment belongs to a different behavior')
    behavior=store.get(behavior_id)
    p=copy.deepcopy(behavior['payload'])
    p['experiment_ids']=list(dict.fromkeys(p.get('experiment_ids',[])+[result_object['id']]))
    live=result_object['payload'].get('agent_mode')=='live'
    has_live=live or any(store.get(oid)['payload'].get('agent_mode')=='live' for oid in p['experiment_ids'])
    if p['status'] not in ('rejected','replication_tested'):
        p['status']='pilot_tested' if has_live else 'infrastructure_tested'
    if p.get('evidence_level')!='controlled_abstraction_with_held_out_seed_test':
        p['evidence_level']='controlled_abstraction_pilot' if has_live else 'scripted_infrastructure_check'
    p['causal_support']='Only the registered synthetic environment and tested subject model; historical causal support remains absent.' if has_live else 'No evidence about LLM behavior; deterministic policy tests infrastructure only.'
    return store.put('behavior',p,behavior_id)

def register_theory(store,theory,behavior_id,result_id,agent_mode):
    behavior=store.get(behavior_id);result=store.get(result_id)
    if theory.get('replication_ids') or theory.get('replication_status','unreplicated')!='unreplicated':
        raise ValueError('Initial theory cannot claim replication; register independent replication evidence first')
    if result['kind']!='experiment' or result['payload'].get('behavior_id')!=behavior_id or result['payload'].get('status')!='complete':
        raise ValueError('Initial theory requires a completed experiment for this behavior')
    payload={**theory,'status':'hypothesis','behavior_ids':[behavior_id],'experiment_ids':[result_id],
        'source_refs':{'behavior':{k:behavior[k] for k in ('id','version','hash')},'experiment':{k:result[k] for k in ('id','version','hash')}},
        'agent_mode':agent_mode,'generalization':'unestablished','version_reason':'Initial theory linked to an exploratory pilot; independent replication is required.'}
    obj=store.put('theory',payload)
    behavior=store.get(behavior_id);p=behavior['payload'];p['theory_ids']=list(dict.fromkeys(p.get('theory_ids',[])+[obj['id']]))
    store.put('behavior',p,behavior_id)
    return obj

def verify_protocol(protocol_object):
    p=protocol_object['payload'];protocol=p['protocol']
    if fingerprint(protocol)!=p['frozen_hash']:raise ValueError('Protocol changed after registration')
    return protocol


def _append_once(values,value):
    return list(dict.fromkeys([*values,value]))


def _record_quantitative_evidence(payload,records):
    """Retain agent narratives separately from code-verified directional evidence."""
    registry=copy.deepcopy(payload.get('quantitative_evidence',[]))
    by_id={row['experiment']['id']:row for row in registry}
    for record in records:
        obj=record['object']; summary=record['summary']
        if summary is None:continue
        ref={k:obj[k] for k in ('id','version','hash')}
        entry={'experiment':ref,'agent_mode':obj['payload']['agent_mode'],
               'quantitative_summary':summary,
               'classification_scope':'Sign and uncertainty of the registered reminder-versus-neutral-note contrast; this does not adjudicate the broader theory.'}
        if obj['id'] not in by_id:
            registry.append(entry);by_id[obj['id']]=entry
    payload['quantitative_evidence']=registry
    # Supporting/conflicting mean a directional claim about THIS contrast only.
    # A wide interval is retained as inconclusive, never recoded as a null result.
    directional={'supporting_positive_contrast':[], 'conflicting_negative_contrast':[],
                 'inconclusive_contrast':[], 'scripted_infrastructure_only':[]}
    for row in registry:
        if row['agent_mode']!='live':bucket='scripted_infrastructure_only'
        else:
            q=row['quantitative_summary'];low,high=q['ci95'];p=q['p_two_sided']
            bucket=('supporting_positive_contrast' if low>0 and p<.05 else
                    'conflicting_negative_contrast' if high<0 and p<.05 else 'inconclusive_contrast')
        directional[bucket].append(row['experiment']['id'])
    payload['directional_evidence_registry']={
        'target':'A positive effect of the registered context on correct publication in this synthetic task.',
        'interpretation':'Descriptive, nominal per-study classification; no pooled test, mediation or generalization claim.',
        **{k:list(dict.fromkeys(v)) for k,v in directional.items()}}


def _replication_history(store,payload,latest_status):
    statuses=[store.get(oid)['payload']['status'] for oid in payload['replication_ids']]
    counts={status:statuses.count(status) for status in dict.fromkeys(statuses)}
    strongest=('completed_live_seed_replication' if 'completed_live_seed_replication' in statuses else
               'completed_scripted_infrastructure_replication' if 'completed_scripted_infrastructure_replication' in statuses else
               'incomplete_infrastructure_attempt')
    payload['replication_status']=strongest
    payload['replication_summary']={'attempt_count':len(statuses),'status_counts':counts,
        'latest_attempt_status':latest_status,'pooled_analysis':'not_computed'}


def link_replication(store,original_result_id,replication_result_id,theory_id=None):
    """Append verified replication evidence and conservative library versions.

    Idempotent for a pair of execution objects. All validation happens before
    writes. Completed, incomplete and scripted attempts remain visible, including
    uncertainty and opposing effects. Existing supporting/conflicting prose and
    all earlier immutable versions are retained.
    """
    from .replication import validate_replication_pair,object_ref
    verified=validate_replication_pair(store,original_result_id,replication_result_id,theory_id)
    original=verified['original']; replication=verified['replication']
    behavior=verified['behavior']; theory=verified['theory']
    record_id='replication-'+hashlib.sha256(f'{original_result_id}:{replication_result_id}'.encode()).hexdigest()[:12]
    sources={'behavior':object_ref(behavior),
        'original_experiment':object_ref(original['object']),
        'replication_experiment':object_ref(replication['object']),
        'original_protocol':object_ref(original['registration']),
        'replication_protocol':object_ref(replication['registration']),
        **verified['provenance']['source_refs']}
    payload={'schema_version':'1.0','registered_at':now(),'status':verified['status'],
        'behavior_id':behavior['id'],'original_result_id':original_result_id,
        'replication_result_id':replication_result_id,'source_refs':sources,
        'provenance_resolution':verified['provenance']['resolution'],
        'original_quantitative_summary':original['summary'],
        'replication_quantitative_summary':replication['summary'],
        'verification':{'original':original['verification'],'replication':replication['verification'],
                        'independence':verified['independence']},
        'scope':'Held-out environment-seed test with fixed task, text, outcomes, model and harness. No pooled analysis.',
        'historical_causal_support':'unestablished','mechanism_status':'unestablished',
        'generalization':'unestablished','limitations':verified['limitations']}
    try:
        obj=store.get(record_id)
        if obj['kind']!='replication' or obj['payload']['status']!=payload['status'] or any(
                obj['payload']['verification'][name]['canonical_report_hash']!=payload['verification'][name]['canonical_report_hash']
                for name in ('original','replication')):
            raise ValueError('A different execution is already registered under this replication pair')
    except KeyError:
        obj=store.put('replication',payload,record_id)
    if obj['id'] not in behavior['payload'].get('replication_ids',[]):
        bp=copy.deepcopy(behavior['payload'])
        bp['replication_ids']=_append_once(bp.get('replication_ids',[]),obj['id'])
        bp['replication_attempt_ids']=_append_once(bp.get('replication_attempt_ids',[]),replication_result_id)
        for record in (original,replication):
            if record['object']['payload']['status']=='complete':
                bp['experiment_ids']=_append_once(bp.get('experiment_ids',[]),record['object']['id'])
        bp['source_refs']={**bp.get('source_refs',{}),**verified['provenance']['source_refs']}
        bp['provenance_resolution']=verified['provenance']['resolution']
        _replication_history(store,bp,verified['status'])
        if verified['status']=='completed_live_seed_replication' and bp.get('status')!='rejected':
            bp['status']='replication_tested'
            bp['evidence_level']='controlled_abstraction_with_held_out_seed_test'
        elif verified['status']=='completed_scripted_infrastructure_replication' and bp.get('status') not in ('rejected','pilot_tested','replication_tested'):
            bp['status']='infrastructure_tested'
        _record_quantitative_evidence(bp,(original,replication))
        has_live=any(row['agent_mode']=='live' for row in bp['quantitative_evidence'])
        bp['causal_support']=('Separate randomized studies of assigned text in the registered synthetic task and subject model; historical causation, mediation and transfer remain unestablished.'
                             if has_live else 'No empirical LLM behavioral support; scripted subjects test research infrastructure only.')
        bp['replication_limitations']=verified['limitations']
        bp['version_reason']='Append verified held-out seed replication attempt; preserve all directional and inconclusive evidence.'
        store.put('behavior',bp,behavior['id'])
    if theory and obj['id'] not in theory['payload'].get('replication_ids',[]):
        tp=copy.deepcopy(theory['payload'])
        tp['replication_ids']=_append_once(tp.get('replication_ids',[]),obj['id'])
        tp['replication_attempt_ids']=_append_once(tp.get('replication_attempt_ids',[]),replication_result_id)
        for record in (original,replication):
            if record['object']['payload']['status']=='complete':
                tp['experiment_ids']=_append_once(tp.get('experiment_ids',[]),record['object']['id'])
        _replication_history(store,tp,verified['status'])
        tp['source_refs']={**tp.get('source_refs',{}),**verified['provenance']['source_refs']}
        tp['replication_source_refs']={**tp.get('replication_source_refs',{}),obj['id']:object_ref(obj)}
        _record_quantitative_evidence(tp,(original,replication))
        if tp.get('status')!='rejected':tp['status']='hypothesis'
        tp['historical_causal_support']='unestablished';tp['mechanism_status']='unestablished';tp['generalization']='unestablished'
        tp['replication_limitations']=verified['limitations']
        tp['version_reason']='Append independently seeded registered experiment; preserve supporting and conflicting narratives and code-derived uncertainty without promoting a broad theory.'
        store.put('theory',tp,theory['id'])
    return obj
