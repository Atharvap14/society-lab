"""Bounded agent-authored blueprints over discoverable executable capabilities.

Capabilities describe current tools, not an ontology of agent behavior. Unknown
requirements remain explicit extension requests. No code from a blueprint is
evaluated, imported or executed; only allowlisted existing factories are called.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from pathlib import Path

from .environment_api import capabilities as factory_capabilities, create
from .store import fingerprint as object_hash, now

API_VERSION='1.0'
TEMPLATES=('shared_artifact_coordination','provenance_diffusion','complementary_information','exclusive_resource_tasks')
COMMON=('resettable_state','role_scoped_observations','private_context_insertion',
        'independent_code_oracle','within_run_action_history','bounded_action_budget',
        'recipient_scoped_messages')
TEMPLATE_FEATURES={
    'shared_artifact_coordination':(*COMMON,'three_fixed_roles','shared_artifact','artifact_repair','broadcast_chat'),
    'provenance_diffusion':(*COMMON,'four_fixed_agents','communication_topology','custom_undirected_graph',
        'canonical_provenance','private_noisy_binary_observations','correlated_source_copies'),
    'complementary_information':(*COMMON,'four_fixed_agents','communication_topology','custom_undirected_graph',
        'canonical_provenance','private_complementary_residues','neighbor_multicast'),
    'exclusive_resource_tasks':(*COMMON,'four_fixed_agents','exclusive_shared_computer','independent_parallel_work',
        'exogenous_initial_occupation_release','executed_task_completion_oracle'),
}
FEATURE_DESCRIPTIONS={
    'resettable_state':'Fresh deterministic state reset within the declared generator; not persistent subject memory.',
    'role_scoped_observations':'Only one subject observation/context/history is supplied to its request.',
    'private_context_insertion':'Observable private text insertion; no editing of latent thoughts.',
    'independent_code_oracle':'Executed outcomes scored in code; agent narrative is not correctness.',
    'within_run_action_history':'Own actions and tool results persist within the run.',
    'bounded_action_budget':'Allocated decisions and tool/message caps are enforced.',
    'recipient_scoped_messages':'Direct messages are visible to their intended recipients.',
    'three_fixed_roles':'Coordinator, builder and verifier; arbitrary role assignment is unsupported.',
    'shared_artifact':'Synthetic inventory manifest and task requirements.',
    'artifact_repair':'Only the fixed builder can repair the manifest.',
    'broadcast_chat':'Shared broadcast messages, with private direct messages also available.',
    'four_fixed_agents':'Exactly agent-0 through agent-3; arbitrary populations are unsupported.',
    'communication_topology':'Declared ring, star or complete undirected peer-message graph.',
    'custom_undirected_graph':'Four-node explicit edges, including disconnected test cases.',
    'canonical_provenance':'Canonical attachments retain original identity and relay lineage; free text remains unverified.',
    'private_noisy_binary_observations':'One private report per subject; three independently generated sources.',
    'correlated_source_copies':'Fixed report multiplicities 2,1,1 share their original-source error.',
    'private_complementary_residues':'Four private uniform residues jointly determine an exact modular answer.',
    'neighbor_multicast':'A single action can deliver a bundle to all connected neighbors; fanout depends on degree.',
    'exclusive_shared_computer':'One invented first-request exclusive lease; historical global exclusivity remains unestablished.',
    'independent_parallel_work':'An independent task is executable during occupation or another subject lease.',
    'exogenous_initial_occupation_release':'A hidden seeded closed prefix releases once; no queue, reservation or repeated external occupation.',
    'executed_task_completion_oracle':'Eight abstract task counters score completion; chat assertions do not complete work or confer access.',
}


def _object(properties):
    return {'type':'object','properties':copy.deepcopy(properties),'required':list(properties),'additionalProperties':False}


def _text(maximum=2000):return {'type':'string','maxLength':maximum}
def _texts(maximum=20):return {'type':'array','items':_text(600),'maxItems':maximum,'uniqueItems':True}
def _nullable(value):
    return {'anyOf':[value,{'type':'null'}]}


def _parameter_schemas():
    edges=_nullable({'type':'array','maxItems':6,'items':{'type':'array','minItems':2,'maxItems':2,
        'items':{'type':'string','enum':[f'agent-{i}' for i in range(4)]}}})
    topology=_nullable({'type':'string','enum':['ring','star','complete','custom']})
    rounds=lambda low,high:_nullable({'type':'integer','minimum':low,'maximum':high})
    return {
        'shared_artifact_coordination':_object({'max_rounds':rounds(2,100),
            'valid_probability':_nullable({'type':'number','minimum':0,'maximum':1}),
            'defect_modes':_nullable({'type':'array','minItems':1,'maxItems':2,'uniqueItems':True,
                'items':{'type':'string','enum':['missing_entry','wrong_quantity']}}),
            'completion_claim':_nullable(_text(2000))}),
        'provenance_diffusion':_object({'topology':topology,'max_rounds':rounds(3,30),
            'source_reliability':_nullable({'type':'number','minimum':.5,'maximum':1}),
            'custom_edges':edges}),
        'complementary_information':_object({'topology':topology,'max_rounds':rounds(3,30),
            'modulus':_nullable({'type':'integer','minimum':2,'maximum':1000000}),
            'max_messages_per_agent':_nullable({'type':'integer','minimum':0,'maximum':29}),
            'custom_edges':edges}),
        'exclusive_resource_tasks':_object({'max_rounds':rounds(2,30),
            'release_rounds':_nullable({'type':'array','minItems':1,'maxItems':31,'uniqueItems':True,
                'items':{'type':'integer','minimum':0,'maximum':30}}),
            'independent_work_steps':rounds(1,30),'computer_work_steps':rounds(1,30),
            'max_messages_per_agent':_nullable({'type':'integer','minimum':0,'maximum':30})}),
        'unsupported':_object({}),
    }


def _schemas():
    ref=_object({'kind':{'type':'string','minLength':1,'maxLength':80},
        'id':{'type':'string','minLength':1,'maxLength':200},'version':{'type':'integer','minimum':1},
        'hash':{'type':'string','pattern':'[0-9a-f]{64}'}})
    fact=_object({'statement':_text(),'source_ids':{'type':'array','items':_text(200),'minItems':1,'maxItems':12,'uniqueItems':True},
        'evidence_ids':{'type':'array','items':_text(200),'maxItems':20,'uniqueItems':True}})
    invention=_object({'name':_text(160),'description':_text(),'reason_for_invention':_text()})
    builder=_object({'schema_version':{'type':'string','enum':[API_VERSION]},'title':_text(160),
        'template':{'type':'string','enum':[*TEMPLATES,'unsupported']},
        'parameters':{'anyOf':list(_parameter_schemas().values())},
        'required_capabilities':_texts(30),'missing_capabilities':_texts(30),
        'source_refs':{'type':'array','items':ref,'maxItems':12},
        'observed_facts':{'type':'array','items':fact,'maxItems':20},
        'analogue_inventions':{'type':'array','items':invention,'maxItems':20},
        'mechanism_hypothesis':_text(),'fit_rationale':_text(),'unmodeled_features':_texts(),
        'unsupported_reason':_text(),'historical_fidelity':{'type':'string','enum':['unestablished']}})
    reviewer=_object({'reviewed_blueprint_hash':{'type':'string','pattern':'[0-9a-f]{64}'},
        'decision':{'type':'string','enum':['approve_analogue','revise','block']},
        'mechanism_fit':{'type':'string','enum':['plausible_analogue','undetermined','unsupported']},
        'rationale':_text(),'blocking_reasons':_texts(),'missing_capabilities':_texts(30),
        'source_misstatements':_texts(),'required_changes':_texts(),'limitations':_texts(),
        'historical_fidelity':{'type':'string','enum':['unestablished']}})
    return builder,reviewer


def capability_catalog():
    raw=factory_capabilities();parameters=_parameter_schemas()
    implementations={}
    for template in TEMPLATES:
        implementations[template]={'capability_ids':list(TEMPLATE_FEATURES[template]),
            'factory_declaration':raw['implementations'][template],
            'parameter_schema':parameters[template],
            'defaults_policy':'Null selects the existing factory default; unsupported parameters are never ignored.'}
    return {'api_version':API_VERSION,'implementations':implementations,
        'capability_definitions':copy.deepcopy(FEATURE_DESCRIPTIONS),
        'unsupported_examples':['browser_tools','persistent_cross_run_memory','custom_roles','arbitrary_population',
            'strategic_private_incentives','latent_thought_editing','generated_code_execution'],
        'ontology_policy':'This is a versioned inventory of executable tools, not a closed ontology of agent behaviors. New requirements remain explicit extension requests.',
        'fidelity_policy':raw['fidelity_policy'],'extension_contract':raw['extension_contract']}


def schema_for_capabilities(required_capabilities=()):
    if not isinstance(required_capabilities,(list,tuple)) or any(not isinstance(x,str) for x in required_capabilities):
        raise ValueError('Capabilities must be a list of exact string identifiers')
    required=list(dict.fromkeys(required_capabilities));catalog=capability_catalog()
    unknown=[c for c in required if c not in FEATURE_DESCRIPTIONS]
    eligible=[t for t in TEMPLATES if set(required)<=set(TEMPLATE_FEATURES[t])]
    builder,reviewer=_schemas()
    return {'catalog':catalog,'catalog_hash':_hash(catalog),'required_capabilities':required,
        'unknown_capabilities':unknown,'eligible_templates':eligible,
        'builder_schema':builder,'reviewer_schema':reviewer,
        'instructions':['Select an eligible executable template or unsupported. Never silently weaken a requirement.',
            'Mark all synthetic domain, roles, incentives, priors and dynamics as analogue inventions unless supported by pinned source facts.',
            'Citations pin source objects and records; they do not prove a statement or a historical causal mechanism.',
            'A world reviewer may block mechanism fit even when a factory and its boundary checks succeed.']}


def _hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def blueprint_fingerprint(proposal):
    """Canonical proposal identity used to bind a fit judgment to its input."""
    return _hash(proposal)


def _check(value,schema,path='$'):
    """Validate just the bounded JSON-Schema subset used by this compiler."""
    if 'anyOf' in schema:
        if not any(not _check(value,option,path) for option in schema['anyOf']):return [f'{path}: no allowed schema branch matches']
        return []
    typ=schema.get('type');ok={
        'object':isinstance(value,dict),'array':isinstance(value,list),'string':isinstance(value,str),
        'integer':type(value) is int,'number':type(value) is int or (type(value) is float and math.isfinite(value)),
        'null':value is None}.get(typ,False)
    if not ok:return [f'{path}: expected {typ}']
    errors=[]
    if 'enum' in schema and value not in schema['enum']:errors.append(f'{path}: unsupported value')
    if typ=='object':
        for key in schema.get('required',[]):
            if key not in value:errors.append(f'{path}.{key}: required')
        for key,item in value.items():
            if key not in schema.get('properties',{}):errors.append(f'{path}.{key}: additional property forbidden')
            else:errors.extend(_check(item,schema['properties'][key],f'{path}.{key}'))
    if typ=='array':
        if len(value)<schema.get('minItems',0) or len(value)>schema.get('maxItems',1000000):errors.append(f'{path}: invalid array length')
        if schema.get('uniqueItems') and len({_hash(v) for v in value})!=len(value):errors.append(f'{path}: duplicate values')
        for i,item in enumerate(value):errors.extend(_check(item,schema['items'],f'{path}[{i}]'))
    if typ=='string':
        if not schema.get('minLength',0)<=len(value)<=schema.get('maxLength',1000000):errors.append(f'{path}: invalid text length')
        if 'pattern' in schema and not re.fullmatch(schema['pattern'],value):errors.append(f'{path}: invalid format')
    if typ in ('number','integer') and not schema.get('minimum',-math.inf)<=value<=schema.get('maximum',math.inf):errors.append(f'{path}: numeric bound violated')
    return errors


def _source_verification(proposal,store):
    refs=proposal['source_refs'];ids=[r['id'] for r in refs]
    if len(ids)!=len(set(ids)):raise ValueError('A source ID must have one unambiguous pinned version')
    objects={}
    if store is not None:
        for ref in refs:
            obj=store.get(ref['id'],ref['version'])
            if obj['kind']!=ref['kind'] or obj['hash']!=ref['hash'] or object_hash(obj['payload'])!=ref['hash']:
                raise ValueError('Source kind, version or hash mismatch')
            objects[ref['id']]=obj
    for fact in proposal['observed_facts']:
        if set(fact['source_ids'])-set(ids):raise ValueError('An observed fact cites an unpinned source')
        referenced=[objects[i] for i in fact['source_ids'] if i in objects]
        datasets=[o for o in referenced if o['kind']=='dataset']
        if datasets and not fact['evidence_ids']:raise ValueError('Dataset observation claims require specific evidence record IDs')
        available={m['id'] for o in datasets for m in o['payload'].get('messages',[])}
        if store is not None and fact['evidence_ids'] and (not datasets or set(fact['evidence_ids'])-available):
            raise ValueError('Observed fact cites missing records in its pinned dataset source')
    return {'status':'verified_object_versions_and_record_membership' if store is not None and refs else
            'syntactic_pins_only_not_retrieved' if refs else 'pure_synthetic_no_source_facts',
        'verified_source_count':len(objects),'semantic_fact_truth':'not_certified',
        'source_refs':copy.deepcopy(refs),
        'limitation':'Pin and record-membership checks do not establish semantic truth, complete observation coverage, mechanism or historical fidelity.'}


def _build(proposal):
    template=proposal['template'];params={k:v for k,v in proposal['parameters'].items() if v is not None}
    incident={'title':proposal['title'],'source_refs':proposal['source_refs']}
    if template=='shared_artifact_coordination':
        from .environments import environment_spec
        distribution={k:params[k] for k in ('valid_probability','defect_modes','completion_claim') if k in params}
        spec=environment_spec(incident,max_rounds=params.get('max_rounds',6),
            overrides={'initial_state_distribution':distribution} if distribution else None)
    elif template=='exclusive_resource_tasks':
        from .resource_environment import create_resource_spec
        spec=create_resource_spec(incident=incident,**params)
    else:
        if params.get('topology')=='custom' and params.get('custom_edges') is None:raise ValueError('Custom topology requires explicit edges')
        if params.get('custom_edges') is not None and params.get('topology')!='custom':raise ValueError('Explicit edges require declaring topology custom, not silently changing a built-in graph')
        if params.get('topology')=='custom':params.pop('topology')
        if template=='provenance_diffusion':
            from .diffusion_environment import create_diffusion_spec
            spec=create_diffusion_spec(incident=incident,**params)
        else:
            from .complementary_environment import create_complementary_spec
            spec=create_complementary_spec(incident=incident,**params)
    return spec,{k:v for k,v in proposal['parameters'].items() if v is not None}


def _boundary_audit(spec,seed):
    if spec['kind']=='shared_artifact_coordination':
        from .environments import check_environment_contract as contract,subject_request as request
    elif spec['kind']=='provenance_diffusion':
        from .diffusion_environment import check_diffusion_contract as contract,diffusion_subject_request as request
    elif spec['kind']=='exclusive_resource_tasks':
        from .resource_environment import check_resource_contract as contract,resource_subject_request as request
    else:
        from .complementary_environment import check_complementary_contract as contract,complementary_subject_request as request
    env=create(spec,seed);before=env.snapshot();existing=contract(env)
    checks=[{'name':'factory_contract','passed':existing['passed']},
        {'name':'contract_restores_fresh_state','passed':env.snapshot()==before}]
    forbidden={'seed','environment_seed','oracle_total','truth','original_fragments','protocol_hash',
        'assigned_arm','treatment_label','arm','blueprint','fit_review','research_hypothesis',
        'release_round','schedule'}
    def keys(value):
        if isinstance(value,dict):return set(value)|set().union(*(keys(v) for v in value.values()))
        if isinstance(value,list):return set().union(*(keys(v) for v in value))
        return set()
    packets=[request(env,a) for a in spec['agents']]
    checks.append({'name':'subject_packet_keys_scoped','passed':all(set(r)=={'role','system','context','observation','action_schema'} for r in packets)})
    checks.append({'name':'private_world_and_control_metadata_absent','passed':all(not (keys(r['observation'])&forbidden) for r in packets)})
    marker='AUTHORING_PRIVATE_BOUNDARY_TOKEN';focal=spec['agents'][0]
    env.inject_context(focal,marker)
    checks.append({'name':'private_context_recipient_scope','passed':all((marker in json.dumps(request(env,a)))==(a==focal) for a in spec['agents'])})
    restored=env.reset(seed)
    checks.append({'name':'authoring_probe_reset','passed':restored==before})
    return {'passed':all(c['passed'] for c in checks),'checks':checks,'factory_checks':existing,
        'scope':'Structural scoped-packet, private-marker and reset checks on one audit seed; not proof against all semantic leakage or validation of historical fidelity.',
        'audit_seed':seed,'subject_count':len(spec['agents']),'model_calls':0}


def compile_blueprint(proposal,*,store=None,fit_review=None,audit_seed=0,required_capabilities=()):
    """Compile a bounded proposal, keeping construction and causal fit separate."""
    if type(audit_seed) is not int or not 0<=audit_seed<2**63:raise ValueError('audit_seed must be a nonnegative 63-bit integer')
    trusted=schema_for_capabilities(required_capabilities)['required_capabilities']
    catalog=capability_catalog();builder_schema,review_schema=_schemas()
    base={'schema_version':API_VERSION,'kind':'environment_blueprint','created_at':now(),
        'catalog_hash':_hash(catalog),'construction_status':'invalid_blueprint',
        'spec':None,'spec_hash':None,'compiled_parameters':None,'boundary_audit':None,
        'historical_fidelity':'unestablished','causal_identification':'not_established_by_compilation',
        'experiment_eligibility':'blocked','missing_capabilities':[],
        'trusted_required_capabilities':trusted,
        'observation_claims_status':'not_semantically_verified','proposed_blueprint':None,
        'errors':[],'limitations':['Compiled schema/factory validity does not imply mechanism fit or historical fidelity.',
            'New experiment registration, backend pinning, randomization and outcome measurements are separate requirements.']}
    if not isinstance(proposal,dict):base['errors']=['Blueprint must be a JSON object'];return base
    if proposal.get('template') not in (*TEMPLATES,'unsupported'):
        base.update(construction_status='unsupported',missing_capabilities=['template:'+str(proposal.get('template'))],errors=['No executable adapter exists for the requested template'])
        return base
    errors=_check(proposal,builder_schema)
    parameter_errors=_check(proposal.get('parameters'),_parameter_schemas()[proposal['template']], '$.parameters')
    if parameter_errors:errors.extend(parameter_errors)
    if errors:
        base['errors']=list(dict.fromkeys(errors))
        if isinstance(proposal.get('parameters'),dict):
            base['missing_capabilities']=['parameter:'+k for k in proposal['parameters'] if k not in _parameter_schemas()[proposal['template']]['properties']]
        return base
    base['proposed_blueprint']=copy.deepcopy(proposal);base['blueprint_hash']=_hash(proposal)
    base['original_observation_claims']=copy.deepcopy(proposal['observed_facts'])
    base['analogue_inventions']=copy.deepcopy(proposal['analogue_inventions'])
    try:base['source_verification']=_source_verification(proposal,store)
    except (KeyError,ValueError) as exc:base['errors']=[str(exc)];return base
    template=proposal['template']
    requested=list(dict.fromkeys(trusted+proposal['required_capabilities']));known=FEATURE_DESCRIPTIONS
    base['effective_required_capabilities']=requested
    base['requirements_omitted_by_builder']=[c for c in trusted if c not in proposal['required_capabilities']]
    missing=list(dict.fromkeys(proposal['missing_capabilities']+[c for c in requested if c not in known or c not in TEMPLATE_FEATURES.get(template,())]))
    if template=='unsupported' or missing:
        base.update(construction_status='unsupported',missing_capabilities=missing,
            errors=[proposal['unsupported_reason'] or 'The requested capabilities require a new validated environment implementation.'])
        return base
    if proposal['unsupported_reason']:
        base['errors']=['Supported selection contradicts its unsupported_reason'];return base
    if not proposal['analogue_inventions']:
        base['errors']=['Synthetic task assumptions must be declared as analogue inventions'];return base
    try:
        spec,compiled=_build(proposal);audit=_boundary_audit(spec,audit_seed)
    except (ValueError,TypeError,RuntimeError) as exc:
        base['errors']=['Factory/contract rejected proposal: '+type(exc).__name__+': '+str(exc)];return base
    base.update(construction_status='compiled' if audit['passed'] else 'boundary_check_failed',
        spec=spec,spec_hash=_hash(spec),compiled_parameters=compiled,boundary_audit=audit,
        executable_capabilities=list(TEMPLATE_FEATURES[template]),
        compiled_analogue_assumptions={
            'agents':copy.deepcopy(spec['agents']),'world_kind':spec['kind'],
            'fidelity':copy.deepcopy(spec['fidelity']),
            'initial_conditions':copy.deepcopy(spec.get('measurement_world',spec.get('initial_state_distribution',
                {'resource_world':spec.get('resource_world'),'task_world':spec.get('task_world')}))),
            'status':'Synthetic construction assumptions; compiler does not attribute these to original facts.'},
        environment_code_hashes={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ('environment_authoring.py','environment_api.py',
                {'shared_artifact_coordination':'environments.py','provenance_diffusion':'diffusion_environment.py','complementary_information':'complementary_environment.py','exclusive_resource_tasks':'resource_environment.py'}[template])})
    if not audit['passed']:base['errors']=['Execution information-boundary checks failed'];return base
    base['experiment_eligibility']='needs_review'
    base['fit_review']=copy.deepcopy(fit_review)
    if fit_review is None:return base
    review_errors=_check(fit_review,review_schema)
    if review_errors:base['errors']=review_errors;base['experiment_eligibility']='blocked';return base
    if fit_review['reviewed_blueprint_hash']!=base['blueprint_hash']:
        base['errors']=['World-fit review belongs to a different blueprint']
        base['experiment_eligibility']='blocked';return base
    blocked=(fit_review['decision']=='block' or fit_review['mechanism_fit']=='unsupported' or
        bool(fit_review['blocking_reasons'] or fit_review['missing_capabilities'] or fit_review['source_misstatements']))
    if blocked:
        base['experiment_eligibility']='blocked'
        base['missing_capabilities']=list(dict.fromkeys(base['missing_capabilities']+fit_review['missing_capabilities']))
    elif fit_review['decision']=='revise' or fit_review['required_changes']:
        base['experiment_eligibility']='needs_revision'
    elif fit_review['mechanism_fit']=='undetermined':
        base['experiment_eligibility']='needs_review'
    elif base['source_verification']['status']=='syntactic_pins_only_not_retrieved':
        base['experiment_eligibility']='needs_source_verification'
    else:base['experiment_eligibility']='approved_analogue'
    base['review_scope']='Provided world-fit judgment; reviewer independence and semantic truth are not certified by this compiler.'
    return base
