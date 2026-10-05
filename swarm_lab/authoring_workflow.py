"""Research-role orchestration over a bounded environment compiler."""
import copy
import re
import uuid
from dataclasses import replace
from .environment_authoring import schema_for_capabilities,compile_blueprint
from .research import ResearchAgents
from .store import now


def provider_schema(schema):
    """Keep uniqueness/length validation local; use the provider's schema subset.

    https://developers.openai.com/api/docs/guides/structured-outputs
    The authoritative compiler still checks the complete blueprint schema.
    """
    result=copy.deepcopy(schema)
    def visit(value):
        if isinstance(value,dict):
            for key in ('uniqueItems','minLength','maxLength'):value.pop(key,None)
            # An exact string enum already implies its matching pattern. Keep
            # one equivalent provider constraint; retain both in local checks.
            if 'pattern' in value and value.get('enum') and all(isinstance(x,str) and re.fullmatch(value['pattern'],x) for x in value['enum']):
                value.pop('pattern')
            for child in value.values():visit(child)
        elif isinstance(value,list):
            for child in value:visit(child)
    visit(result);return result


def construct_environment(lab,*,behavior_id=None,research_question='',required_capabilities=None,
        proposal=None,fit_review=None,live=False,harness='responses',job_id=None,audit_seed=0):
    requirements=required_capabilities or []
    packet=schema_for_capabilities(requirements)
    if not behavior_id and not research_question.strip() and proposal is None:
        raise ValueError('Provide a research question, behavior, or explicit blueprint')
    if not live and proposal is None:raise ValueError('Offline construction requires an explicit blueprint; live mode enables research agents')
    if live and (proposal is not None or fit_review is not None):raise ValueError('Live authoring generates both roles; compile a supplied blueprint in offline mode')
    refs=[];behavior=None;dataset={'messages':[]};discovery={'graph':{'edges':[]},'candidates':[]};evidence=[]
    if behavior_id:
        obj=lab.store.get(behavior_id);behavior=obj['payload']
        if obj['kind']!='behavior' or behavior.get('status')=='rejected':raise ValueError('Use a non-rejected behavior for authoring')
        if behavior.get('research_quality_status') in ('schema_defect_requires_re_review','superseded_schema_defect_review'):raise ValueError('Use the corrected skeptical review for authoring')
        refs.append({k:obj[k] for k in ('kind','id','version','hash')})
        for kind in ('dataset','discovery'):
            ref=behavior['source_refs'][kind];source=lab.store.get(ref['id'],ref['version'])
            if source['kind']!=kind or source['hash']!=ref['hash']:raise ValueError('Authoring source reference mismatch')
            refs.append({k:source[k] for k in ('kind','id','version','hash')})
            if kind=='dataset':dataset=source['payload']
            else:discovery=source['payload']
        indexed={m['id']:m for m in dataset['messages']}
        evidence=[indexed[i] for i in behavior.get('evidence_ids',[])[:18]]
    job_id=job_id or 'environment-authoring-'+uuid.uuid4().hex[:10]
    attempt=lab.store.put('environment_construction_attempt',{'status':'started','started_at':now(),
        'behavior_id':behavior_id,'source_refs':refs,'research_question':research_question,
        'trusted_required_capabilities':requirements,'catalog_hash':packet['catalog_hash'],
        'research_job_id':job_id,'audit_seed':audit_seed,'agent_mode':'live' if live else 'explicit_blueprint',
        'builder_harness':harness if live else 'supplied_blueprint'})
    phase='builder'
    try:
        raw_proposal=copy.deepcopy(proposal)
        if live:
            bounded=replace(lab.settings,max_tool_rounds=2,max_output_tokens=6000)
            agents=ResearchAgents(bounded,lab.store,lab.research_harness(harness,bounded))
            schema=provider_schema(packet['builder_schema']);schema['properties']['source_refs']['maxItems']=0
            if refs:
                schema['properties']['observed_facts']['items']['properties']['source_ids']['items']['enum']=[r['id'] for r in refs]
                # Each live observation must have a specific retrieved record.
                # Invented world details belong in analogue_inventions instead.
                schema['properties']['observed_facts']['items']['properties']['evidence_ids']['minItems']=1
            else:schema['properties']['observed_facts']['maxItems']=0
            raw_proposal=agents.run('environment-builder',{'task':'Author the smallest executable analogue for this question, or select unsupported when an essential feature is missing. Preserve the trusted required capabilities. These tools are an expandable inventory, not a taxonomy of behavior. Distinguish observed facts from invented analogue details. Return source_refs as an empty array: exact source pins are attached by the host after your output. Observed facts may cite only supplied/retrieved evidence IDs and the provided source object IDs. Do not infer historical fidelity, original future outcomes or a winning treatment.',
                'research_question':research_question,'behavior':behavior,'evidence':evidence,'trusted_source_refs':refs,
                'source_identity_rules':'source_ids contain object IDs from trusted_source_refs, not message UUIDs or packet nicknames. Each observed fact must cite at least one actual supplied or retrieved message UUID in evidence_ids. Chat facts also cite the dataset object ID in source_ids. Do not turn an uncited review summary into an observation. Omit an observation when no specific record supports it. Synthetic world rules go in analogue_inventions. A purely synthetic question has no observed_facts.',
                'capability_catalog':packet['catalog'],'trusted_required_capabilities':requirements,
                'eligible_templates':packet['eligible_templates'],'output_schema':schema},schema,dataset,discovery,job_id)
            if raw_proposal.get('source_refs'):raise ValueError('Live builder must leave authoritative source pins to the host')
        materialized=copy.deepcopy(raw_proposal)
        if behavior_id:
            if materialized.get('source_refs') and materialized['source_refs']!=refs:raise ValueError('Explicit blueprint sources differ from the incident pins')
            materialized['source_refs']=copy.deepcopy(refs)
        phase='compile';initial=compile_blueprint(materialized,store=lab.store,audit_seed=audit_seed,required_capabilities=requirements)
        lab.store.put('environment_construction_attempt',{**attempt['payload'],'status':'builder_completed',
            'raw_builder_output':raw_proposal,'materialized_proposal':materialized,'initial_compilation':initial,
            'host_materialization':'Exact incident/source references attached by host; no generated source hash gains authority.'},attempt['id'])
        if live and initial['construction_status']=='compiled':
            phase='reviewer';schema=provider_schema(packet['reviewer_schema'])
            schema['properties']['reviewed_blueprint_hash']['enum']=[initial['blueprint_hash']]
            schema=provider_schema(schema)
            fit_review=agents.run('causal-methodologist',{'task':'Independently review world fit and source support. A structurally valid compiler result does not establish semantic fit. Check whether this world preserves the suspected mechanism and every trusted capability; block or require revision if it cannot. Historical fidelity remains unestablished. Outcomes and expected winning arms are not supplied. Copy the exact reviewed_blueprint_hash. Do not adjudicate effect direction or claim public preregistration.',
                'reviewed_blueprint_hash':initial['blueprint_hash'],'research_question':research_question,
                'behavior':behavior,'evidence':evidence,'materialized_blueprint':materialized,
                'compiled_world':initial['spec'],'boundary_audit':initial['boundary_audit'],
                'trusted_capability_catalog':packet['catalog'],'world_implementation_hashes':initial['environment_code_hashes'],
                'review_evidence_scope':'Synthetic capability support is assessed from host factory declarations, code sections and executed boundary probes. Historical transcripts do not need to demonstrate a synthetic capability. These do not establish mechanism isolation.',
                'trusted_required_capabilities':requirements,'output_schema':schema},schema,dataset,discovery,job_id)
        phase='final_compile';final=compile_blueprint(materialized,store=lab.store,fit_review=fit_review,audit_seed=audit_seed,required_capabilities=requirements)
        final.update(behavior_id=behavior_id,source_refs=materialized.get('source_refs',[]),raw_builder_output=raw_proposal,
            research_job_id=job_id,construction_attempt_id=attempt['id'],agent_mode='live' if live else 'explicit_blueprint',
            builder_harness=harness if live else 'supplied_blueprint',reviewer_harness=harness if live and fit_review else 'supplied_review' if fit_review else None,
            reviewer_independence='Separate bounded role execution on the same selected harness/model; no institutional or model independence claimed.' if live else 'Supplied review; independence unverified')
        result=lab.store.put('environment_blueprint',final)
        lab.store.put('environment_construction_attempt',{**lab.store.get(attempt['id'])['payload'],'status':'completed','blueprint_id':result['id']},attempt['id'])
        return result
    except Exception as error:
        lab.store.put('environment_construction_attempt',{**lab.store.get(attempt['id'])['payload'],
            'status':'failed','failed_phase':phase,'error':str(error)},attempt['id']);raise


def resume_environment_review(lab,attempt_id,*,live=False,harness='responses',job_id=None):
    if not live:raise ValueError('Resuming a model world-fit review requires explicit live mode')
    obj=lab.store.get(attempt_id)
    if obj['kind']!='environment_construction_attempt':raise ValueError('Use a saved environment construction attempt')
    p=obj['payload']
    if p.get('blueprint_id'):return lab.store.get(p['blueprint_id'])
    if p.get('initial_compilation',{}).get('construction_status')!='compiled':raise ValueError('Resume requires a saved compiled blueprint; a failed builder needs an explicit amended authoring attempt')
    requirements=p['trusted_required_capabilities'];proposal=p['materialized_proposal']
    compiled=compile_blueprint(proposal,store=lab.store,required_capabilities=requirements,audit_seed=p.get('audit_seed',0))
    if compiled['construction_status']!='compiled' or any(compiled[k]!=p['initial_compilation'][k] for k in ('blueprint_hash','spec_hash')):
        raise ValueError('Saved blueprint or compiled world differs from its preserved construction')
    dataset={'messages':[]};discovery={'graph':{'edges':[]},'candidates':[]};behavior=None
    for ref in proposal['source_refs']:
        source=lab.store.get(ref['id'],ref['version'])
        if source['kind']!=ref['kind'] or source['hash']!=ref['hash']:raise ValueError('Saved authoring source reference differs')
        if ref['kind']=='dataset':dataset=source['payload']
        elif ref['kind']=='discovery':discovery=source['payload']
        elif ref['kind']=='behavior':behavior=source['payload']
    ids=list(dict.fromkeys([i for f in proposal['observed_facts'] for i in f['evidence_ids']]+(behavior or {}).get('evidence_ids',[])[:18]))
    indexed={m['id']:m for m in dataset['messages']};evidence=[indexed[i] for i in ids]
    bounded=replace(lab.settings,max_tool_rounds=2,max_output_tokens=6000)
    agents=ResearchAgents(bounded,lab.store,lab.research_harness(harness,bounded))
    schema=provider_schema(schema_for_capabilities(requirements)['reviewer_schema'])
    schema['properties']['reviewed_blueprint_hash']['enum']=[compiled['blueprint_hash']]
    schema=provider_schema(schema)
    job_id=job_id or 'resume-environment-review-'+uuid.uuid4().hex[:10]
    try:
        review=agents.run('causal-methodologist',{'task':'Resume world-fit adjudication of this exact saved proposal. No builder or subject is rerun. Structural validity does not establish mechanism fit. Check source support and trusted capabilities, and block or require revision when necessary. Do not infer historical fidelity or a winning arm. Copy the exact reviewed_blueprint_hash.',
            'reviewed_blueprint_hash':compiled['blueprint_hash'],'research_question':p['research_question'],
            'behavior':behavior,'evidence':evidence,'materialized_blueprint':proposal,
            'compiled_world':compiled['spec'],'boundary_audit':compiled['boundary_audit'],
            'trusted_capability_catalog':schema_for_capabilities(requirements)['catalog'],
            'world_implementation_hashes':compiled['environment_code_hashes'],
            'review_evidence_scope':'Separate code-backed synthetic capability support from historical observation claims and experimental identification. Source code can be inspected through the allowlisted research-only tool.',
            'trusted_required_capabilities':requirements,'output_schema':schema},schema,dataset,discovery,job_id)
        final=compile_blueprint(proposal,store=lab.store,fit_review=review,required_capabilities=requirements,audit_seed=p.get('audit_seed',0))
        final.update(behavior_id=p.get('behavior_id'),source_refs=proposal['source_refs'],
            raw_builder_output=p['raw_builder_output'],research_job_id=job_id,construction_attempt_id=attempt_id,agent_mode='live',
            builder_harness=p.get('builder_harness','legacy_not_recorded'),reviewer_harness=harness,
            reviewer_independence='Separate bounded role execution on the selected harness/model; model or institutional independence is unverified.',
            resume_scope='Unchanged saved proposal/world; previous failed review retained in attempt history.')
        result=lab.store.put('environment_blueprint',final)
        finished={k:v for k,v in p.items() if k not in ('error','failed_phase')}
        finished.update(status='completed',blueprint_id=result['id'],resume_job_id=job_id,
            prior_failure={'phase':p.get('failed_phase'),'error':p.get('error')})
        lab.store.put('environment_construction_attempt',finished,attempt_id)
        return result
    except Exception as error:
        lab.store.put('environment_construction_attempt',{**p,'status':'failed','failed_phase':'reviewer',
            'error':str(error),'resume_job_id':job_id},attempt_id);raise
