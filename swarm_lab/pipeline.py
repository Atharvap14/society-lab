"""Composable discovery → registration → controlled experiment → theory workflow."""
import concurrent.futures
import json
import uuid
import hashlib
from pathlib import Path
from .config import Settings
from .dataset import ingest_village
from .discovery import discover_cases
from .harness import ResponsesHarness, CodexHarness
from .library import register_behavior,record_experiment,register_theory,verify_protocol
from .research import ResearchAgents,offline_proposal,DESIGN_SCHEMA,THEORY_SCHEMA,EVALUATION_SCHEMA,object_schema,TEXT
from .store import Store,fingerprint,clean,now
from .reporting import quantitative_summary,numeric_free_commentary

class Lab:
    def __init__(self,settings=None):
        self.settings=settings or Settings()
        self.store=Store(self.settings.runtime/'lab.sqlite3')

    def harness(self,name):
        if name=='responses':return ResponsesHarness(self.settings,self.store)
        if name=='codex':return CodexHarness(self.settings,self.store)
        raise ValueError('Choose responses or codex for live research')

    def create_measurement_sample(self,dataset_ref,**kwargs):
        from .measurement_adjudication import create_sample
        return create_sample(self.store,dataset_ref,**kwargs)

    def record_measurement_judgment(self,sample_ref,**kwargs):
        from .measurement_adjudication import record_judgment
        return record_judgment(self.store,sample_ref,**kwargs)

    def research_harness(self,name,settings=None):
        settings=settings or self.settings
        if name=='responses':
            from .research_transport import ResearchResponsesHarness
            return ResearchResponsesHarness(settings,self.store)
        if name=='codex':return CodexHarness(settings,self.store)
        raise ValueError('Choose responses or codex for live research')

    def ingest(self,source=None,**scope):
        source=source or self.settings.root/'ai-village'
        dataset=ingest_village(source,**scope)
        from .provenance import source_revision
        dataset['provenance']={'source':dataset['source'],'scope':dataset['scope'],'fingerprint':dataset['fingerprint'],
             **source_revision(source),
             'license':'Read source dataset terms; analysis only, no model training authorized.'}
        return self.store.put('dataset',dataset)

    def observe(self,dataset_id,*,measurement_backend='regex',measurement_limit=32,live=False,job_id=None):
        registered_dataset=self.store.get(dataset_id);dataset=registered_dataset['payload']
        if registered_dataset['kind']!='dataset':raise ValueError('Observe requires a dataset object')
        if measurement_backend not in ('regex','laya','jev'):raise ValueError('Choose regex, laya or jev measurement backend')
        if measurement_backend!='regex' and not live:raise ValueError('Additional model measurements require explicit live mode')
        additional=None
        if measurement_backend!='regex':
            from .measurement_backends import BoundedMeasurement
            def on_status(status):
                if job_id:self.store.job(job_id,'running',{'action':'observe','dataset_id':dataset_id,'measurement_backend':measurement_backend,'measurement_status':status})
            additional=BoundedMeasurement(measurement_backend,dataset['messages'],self.settings.root,limit=measurement_limit,on_status=on_status)
        try:
            discovery=discover_cases(dataset['messages'],agents=dataset['agents'],events=dataset.get('events'),backend=additional)
            discovery['measurement_summary']=additional.summary() if additional else {'backend':'regex','motif_input':'deterministic_regex_only','paid_calls':0}
        finally:
            if additional:additional.close()
        discovery['dataset_id']=dataset_id
        discovery['dataset_ref']={k:registered_dataset[k] for k in ('id','version','hash')}
        try:
            from .network import analyze_network
            discovery['network']=analyze_network(dataset['messages'],dataset['agents'])
            from .spectral_observables import describe_observable_signals
            observable_signals=describe_observable_signals(discovery)
            for channel,signals in observable_signals.items():discovery['network']['projections'][channel]['observable_signals']=signals
        except ImportError:
            discovery['network']={'status':'unavailable','reason':'Network analysis extension not installed'}
        return self.store.put('discovery',discovery)

    def investigate(self,discovery_id,*,discovery_version=None,discovery_hash=None,candidate_ids=None,count=2,live=False,harness='responses',job_id=None):
        import re
        if (discovery_version is None)!=(discovery_hash is None):
            raise ValueError('Supply discovery version and hash together')
        if discovery_version is not None and (type(discovery_version) is not int or not 1<=discovery_version<=1000000000 or
            type(discovery_hash) is not str or not re.fullmatch(r'[0-9a-f]{64}',discovery_hash)):
            raise ValueError('Use a positive integer discovery version and exact SHA-256')
        job_id=job_id or 'research-'+uuid.uuid4().hex[:10]
        discovery_object=self.store.get(discovery_id,discovery_version);discovery=discovery_object['payload']
        if discovery_object['kind']!='discovery' or (discovery_hash is not None and discovery_object['hash']!=discovery_hash):
            raise ValueError('The exact discovery reference does not match')
        dataset_id=discovery['dataset_id'];declared=discovery.get('dataset_ref')
        if declared is not None:
            if (type(declared) is not dict or set(declared)!={'id','version','hash'} or declared['id']!=dataset_id or
                type(declared['version']) is not int or not 1<=declared['version']<=1000000000 or
                type(declared['hash']) is not str or not re.fullmatch(r'[0-9a-f]{64}',declared['hash'])):
                raise ValueError('Discovery must bind a typed exact dataset reference')
        registered_dataset=self.store.get(dataset_id,declared['version'] if declared else None)
        dataset_ref={k:registered_dataset[k] for k in ('id','version','hash')}
        if registered_dataset['kind']!='dataset' or (declared is not None and dataset_ref!=declared):
            raise ValueError('Discovery source dataset reference does not match')
        dataset=registered_dataset['payload']
        candidates=discovery['candidates']
        if candidate_ids:
            selected=[c for c in candidates if c['id'] in candidate_ids]
            if len(selected)!=len(set(candidate_ids)):raise ValueError('Unknown candidate ID')
        else:
            # Review higher-evidence motifs first; no novelty or causal ranking.
            selected=sorted(candidates,key=lambda c:(c['kind']!='completion_report_cluster',c.get('right_censored',False),-len(c['evidence_ids']),c['id']))[:count]
        if not selected:raise ValueError('No screened candidates in this import. Expand scope or define another detector.')
        worker=ResearchAgents(self.settings,self.store,self.research_harness(harness)) if live else None
        def investigate(c):
            refs={'discovery':{k:discovery_object[k] for k in ('id','version','hash')},'dataset':dataset_ref}
            research=worker.discover(c,dataset,discovery,job_id,source_refs=refs) if worker else offline_proposal(c)
            return register_behavior(self.store,research,dataset_id,discovery_id,source_refs=refs)
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(self.settings.max_workers,len(selected))) as pool:
            futures=[pool.submit(investigate,c) for c in selected]
            results=[f.result() for f in futures]
        return results

    def resume_investigation(self,attempt_id,*,live=False,harness='responses',job_id=None):
        from .research import SKEPTIC_SCHEMA
        from dataclasses import replace
        if not live:raise ValueError('Resuming a model review requires explicit live mode')
        attempt=self.store.get(attempt_id)
        if attempt['kind']!='research_attempt':raise ValueError('Resume requires a saved research attempt')
        p=attempt['payload']
        if p.get('behavior_id'):return self.store.get(p['behavior_id'])
        from .measurement_context import reference_matches
        from .library import validate_measurement_audit_refs
        refs=p['source_refs'];objects={}
        if type(refs) is not dict or set(refs)!={'dataset','discovery'}:
            raise ValueError('Saved research source reference mismatch')
        for kind in ('dataset','discovery'):
            ref=refs[kind]
            if (type(ref) is not dict or set(ref)!={'id','version','hash'} or
                type(ref.get('version')) is not int or ref['version']<1 or
                type(ref.get('id')) is not str or type(ref.get('hash')) is not str):
                raise ValueError('Saved research source reference mismatch')
            obj=self.store.get(ref['id'],ref['version'])
            if obj['kind']!=kind or not reference_matches(ref,obj):raise ValueError('Saved research source reference mismatch')
            objects[kind]=obj
        dataset=objects['dataset']['payload'];discovery=objects['discovery']['payload']
        if (('dataset_ref' in discovery and not reference_matches(discovery['dataset_ref'],objects['dataset'])) or
            ('dataset_id' in discovery and discovery['dataset_id']!=objects['dataset']['id'])):
            raise ValueError('Saved research paired-source reference mismatch')
        indexed={m['id']:m for m in dataset['messages']};proposal=p['proposal']
        ids=list(dict.fromkeys(p.get('initial_evidence_ids',[])+proposal.get('evidence_ids',[])+proposal.get('comparison_ids',[])))
        if set(ids)-set(indexed):raise ValueError('Saved proposal cites missing source records')
        bounded=replace(self.settings,max_tool_rounds=2,max_output_tokens=5000)
        job_id=job_id or 'resume-'+uuid.uuid4().hex[:10]
        measurement=p.get('measurement_context')
        if measurement is not None and type(measurement) is not dict:
            raise ValueError('Saved research measurement context is malformed')
        measurement=measurement or ResearchAgents(bounded,self.store,None).measurement_context(p['candidate']['id'],refs)
        if (type(measurement.get('audits')) is not list or
            any(type(entry) is not dict or 'ref' not in entry for entry in measurement['audits'])):
            raise ValueError('Saved research measurement context is malformed')
        validate_measurement_audit_refs(self.store,[entry['ref'] for entry in measurement['audits']],
            p['candidate']['id'],objects['dataset'],objects['discovery'])
        if not p.get('measurement_context'):
            # Legacy proposals need a saved snapshot of the context actually
            # passed to the resumed reviewer, before any model execution.
            attempt=self.store.put('research_attempt',{**p,'measurement_context':measurement,
                'resume_context_job_id':job_id},attempt_id)
            p=attempt['payload']
        agent=ResearchAgents(bounded,self.store,self.research_harness(harness,bounded))
        try:
            skeptic=agent.run('skeptic',{'task':'Resume skeptical adjudication of this saved proposal. The discovery output is unchanged; review exact source messages, ordinary alternatives and environment fit. A selected graph shift does not establish a psychological mechanism, failure, or novelty.',
                'candidate':p['candidate'],'proposal':proposal,'evidence':[indexed[i] for i in ids],
                'measurement_context':measurement,'output_schema':SKEPTIC_SCHEMA},SKEPTIC_SCHEMA,dataset,discovery,job_id)
        except Exception as error:
            self.store.put('research_attempt',{**p,'status':'skeptic_failed','resume_job_id':job_id,'error':str(error)},attempt_id);raise
        research={'proposal':proposal,'skeptic':skeptic,'candidate_id':p['candidate']['id'],'agent_mode':'live','harness':harness,'research_attempt_id':attempt_id,
            'research_attempt_ref':{key:attempt[key] for key in ('id','version','hash')},
            'measurement_audit_refs':[entry['ref'] for entry in measurement['audits']]}
        # Register against the exact source version, even if newer graph searches exist.
        behavior=register_behavior(self.store,research,refs['dataset']['id'],refs['discovery']['id'],source_refs=refs)
        self.store.put('research_attempt',{**p,'status':'adjudicated','research':research,'behavior_id':behavior['id'],'resume_job_id':job_id},attempt_id)
        return behavior

    def screen_graph(self,discovery_id,*,window_minutes=60,min_messages=12,min_edge_events=5,max_leads=12,max_windows=120):
        from .graph_discovery import discover_graph_leads
        registered=self.store.get(discovery_id)
        if registered['kind']!='discovery':raise ValueError('Graph screening requires a discovery object')
        discovery=registered['payload'];ref=discovery.get('dataset_ref',{})
        dataset_object=self.store.get(discovery['dataset_id'],ref.get('version'));dataset=dataset_object['payload']
        result=discover_graph_leads(dataset['messages'],dataset['agents'],window_minutes=window_minutes,
            min_messages=min_messages,min_edge_events=min_edge_events,max_leads=max_leads,max_windows=max_windows)
        windows={w['id']:w for w in result['windows']};indexed={m['id']:m for m in dataset['messages']}
        leads=[];controls=[]
        for lead in result['leads']:
            window=windows[lead['window_id']]
            leads.append({**lead,'start':window['start'],'end':window['end_exclusive'],
                'alternative_explanations':lead['alternatives'],'screening_regime':'exploratory_graph_search',
                'room_ids':[window['room_id']],'agent_ids':sorted({indexed[i].get('agent_id') for i in lead['evidence_ids'] if indexed[i].get('agent_id')}),
                'right_censored':True,'novelty':'not_established','causal_support':'none',
                'metrics':{'feature':lead['feature'],'difference':lead['difference'],'support':lead['support'],'robustness_status':lead['robustness_status']},
                'requires':['Adjudicate source messages and both comparison windows','Inspect task/role/membership changes','Use a separately registered experiment for causal claims']})
            controls.append({'for_candidate':lead['id'],'evidence_ids':lead['comparison_evidence_ids'],
                'window_id':lead['comparison_window_id'],'matching':lead['comparison_match'],
                'claim_type':'data_selected_observational_comparison','limitations':'Exploratory comparison chosen after graph search; unmeasured confounding remains.'})
        # A new version preserves the old prespecified screening artifact.
        old_candidates=[c for c in discovery['candidates'] if not c.get('id','').startswith('graph-lead-')]
        old_controls=[c for c in discovery.get('controls',[]) if not c.get('for_candidate','').startswith('graph-lead-')]
        discovery.update(graph_search=result,candidates=old_candidates+leads,anomalies=old_candidates+leads,controls=old_controls+controls,
            dataset_ref={k:dataset_object[k] for k in ('id','version','hash')})
        return self.store.put('discovery',discovery,discovery_id)

    def construct_environment(self,**kwargs):
        from .authoring_workflow import construct_environment
        return construct_environment(self,**kwargs)

    def project_observables(self,discovery_id):
        from .spectral_observables import describe_observable_signals
        obj=self.store.get(discovery_id)
        if obj['kind']!='discovery':raise ValueError('Observable graph signals require a discovery object')
        payload=obj['payload']
        if not payload.get('network',{}).get('projections'):raise ValueError('Discovery has no network projections')
        for channel,signals in describe_observable_signals(payload).items():payload['network']['projections'][channel]['observable_signals']=signals
        payload['graph_signal_derivation']={'source_discovery_ref':{k:obj[k] for k in ('id','version','hash')},
            'generated_at':now(),'model_calls':0,'scope':'Pure derivation from stored graph and regex measurements; no source reimport or missing-rate imputation.',
            'implementation_hashes':{name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ('spectral_observables.py','network.py','graph_discovery.py')}}
        return self.store.put('discovery',payload,discovery_id)

    def resume_environment_review(self,attempt_id,**kwargs):
        from .authoring_workflow import resume_environment_review
        return resume_environment_review(self,attempt_id,**kwargs)

    def register_blueprint(self,blueprint_id,**kwargs):
        from .experiment_authoring import register_blueprint
        return register_blueprint(self,blueprint_id,**kwargs)

    def audit_mentions(self,dataset_id,*,version=None,agent_authored_only=True):
        from .mention_sensitivity import audit_mention_sensitivity
        if type(agent_authored_only) is not bool:raise ValueError('agent_authored_only must be boolean')
        if version is not None and (type(version) is not int or version<1):raise ValueError('Use a positive source version')
        dataset=self.store.get(dataset_id,version)
        if dataset['kind']!='dataset':raise ValueError('Mention sensitivity requires a dataset')
        messages=dataset['payload']['messages']
        retained=[m for m in messages if m.get('speaker_type')=='agent'] if agent_authored_only else messages
        report=audit_mention_sensitivity(retained,dataset['payload']['agents'])
        report.update(dataset_id=dataset_id,dataset_ref={k:dataset[k] for k in ('id','version','hash')},
            agent_authored_only=agent_authored_only,
            input_selection='All retained agent-authored messages in this pinned import' if agent_authored_only else 'All retained messages in this pinned import',
            implementation_sha256=hashlib.sha256(Path(__file__).with_name('mention_sensitivity.py').read_bytes()).hexdigest(),
            paid_calls=0)
        return self.store.put('measurement_audit',report)

    def design_resource(self,**kwargs):
        from .resource_workflow import design_resource
        return design_resource(self,**kwargs)

    def audit_name_eligibility(self,dataset_id,*,version=None,short_name_allowlist=None,
            include_unicode_shadow=False,agent_authored_only=True):
        from .name_eligibility_sensitivity import audit_name_eligibility_sensitivity
        if type(agent_authored_only) is not bool:raise ValueError('agent_authored_only must be boolean')
        if version is not None and (type(version) is not int or version<1):raise ValueError('Use a positive source version')
        obj=self.store.get(dataset_id,version)
        if obj['kind']!='dataset':raise ValueError('Name eligibility sensitivity requires a dataset')
        messages=obj['payload']['messages']
        retained=[m for m in messages if m.get('speaker_type')=='agent'] if agent_authored_only else messages
        report=audit_name_eligibility_sensitivity(retained,obj['payload']['agents'],
            short_name_allowlist=short_name_allowlist,include_unicode_shadow=include_unicode_shadow)
        report.update(dataset_id=dataset_id,dataset_ref={k:obj[k] for k in ('id','version','hash')},
            agent_authored_only=agent_authored_only,
            input_selection='All retained agent-authored messages in this pinned import' if agent_authored_only else 'All retained messages in this pinned import',
            implementation_hashes={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                for name in ('name_eligibility_sensitivity.py','mention_sensitivity.py')},paid_calls=0)
        return self.store.put('name_eligibility_audit',report)

    def experiment_resource(self,protocol_id,**kwargs):
        from .resource_workflow import experiment_resource
        return experiment_resource(self,protocol_id,**kwargs)

    def design_timed_resource(self,**kwargs):
        from .timed_resource_workflow import design_timed_resource
        return design_timed_resource(self,**kwargs)

    def experiment_timed_resource(self,protocol_id,**kwargs):
        from .timed_resource_workflow import experiment_timed_resource
        return experiment_timed_resource(self,protocol_id,**kwargs)

    def design_revision_relay(self,**kwargs):
        from .revision_relay_workflow import design_revision_relay
        return design_revision_relay(self,**kwargs)

    def experiment_revision_relay(self,protocol_id,**kwargs):
        from .revision_relay_workflow import experiment_revision_relay
        return experiment_revision_relay(self,protocol_id,**kwargs)

    def audit_revision_relay(self,result_id,**kwargs):
        from .revision_relay_workflow import audit_revision_relay
        return audit_revision_relay(self,result_id,**kwargs)

    def compare_mention_graphs(self,eligibility_audit_id):
        from .mention_graph_sensitivity import compare_name_graphs
        obj=self.store.get(eligibility_audit_id)
        if obj['kind']!='name_eligibility_audit':raise ValueError('Use an explicit name-eligibility audit')
        if fingerprint(obj['payload'])!=obj['hash']:raise ValueError('Measurement audit payload hash mismatch')
        report=obj['payload'];ref=report['dataset_ref'];dataset=self.store.get(ref['id'],ref['version'])
        if dataset['kind']!='dataset' or dataset['hash']!=ref['hash'] or fingerprint(dataset['payload'])!=ref['hash']:
            raise ValueError('Pinned measurement source changed')
        messages=dataset['payload']['messages']
        if report['agent_authored_only']:messages=[m for m in messages if m.get('speaker_type')=='agent']
        comparison=compare_name_graphs(messages,report,agents=dataset['payload']['agents'])
        comparison.update(dataset_id=ref['id'],dataset_ref=ref,
            eligibility_audit_ref={k:obj[k] for k in ('id','version','hash')},paid_calls=0,
            graph_update_policy='Separate diagnostic derivation; existing discovery projections and library status are unchanged.')
        return self.store.put('graph_measurement_audit',comparison)

    def audit_selected_leads(self,discovery_id,*,version=None,selected_lead_ids=None,
            short_name_allowlist=None,include_unicode_shadow=False):
        from .selected_lead_sensitivity import audit_selected_lead_name_sensitivity
        if version is not None and (type(version) is not int or version<1):
            raise ValueError('Use a positive discovery source version')
        if type(include_unicode_shadow) is not bool:raise ValueError('include_unicode_shadow must be boolean')
        discovery=self.store.get(discovery_id,version)
        if discovery['kind']!='discovery' or fingerprint(discovery['payload'])!=discovery['hash']:
            raise ValueError('Use an unchanged pinned discovery object')
        payload=discovery['payload'];ref=payload.get('dataset_ref')
        if not ref or payload.get('dataset_id')!=ref['id']:
            raise ValueError('Selected-lead sensitivity requires an exact dataset reference')
        dataset=self.store.get(ref['id'],ref['version'])
        if dataset['kind']!='dataset' or dataset['hash']!=ref['hash'] or fingerprint(dataset['payload'])!=ref['hash']:
            raise ValueError('Pinned graph-search dataset changed')
        graph_search=payload.get('graph_search')
        if not graph_search:raise ValueError('Screen graph leads before auditing their measurement')
        ids=[lead['id'] for lead in graph_search['leads']] if selected_lead_ids is None else selected_lead_ids
        source_refs={'discovery':{k:discovery[k] for k in ('id','version','hash')},
            'dataset':{k:dataset[k] for k in ('id','version','hash')}}
        result=audit_selected_lead_name_sensitivity(dataset['payload']['messages'],dataset['payload']['agents'],
            graph_search,selected_lead_ids=ids,short_name_allowlist=short_name_allowlist,
            include_unicode_shadow=include_unicode_shadow,source_refs=source_refs)
        result.update(dataset_id=ref['id'],dataset_ref=source_refs['dataset'],discovery_ref=source_refs['discovery'],
            paid_calls=0,graph_update_policy='Separate conditional measurement audit; original selection, discovery and library status remain unchanged.')
        return self.store.put('selected_lead_audit',result)

    def audit_temporal_paths(self,selected_audit_id,*,version=None):
        from .temporal_workflow import audit_temporal_paths
        return audit_temporal_paths(self,selected_audit_id,version=version)

    def replay_temporal_paths(self,audit_id,*,version=None):
        from .temporal_workflow import replay_temporal_paths
        return replay_temporal_paths(self,audit_id,version=version)

    def scan_source_links(self,sources,*,expected_rows=None,rules_version='source-links-v1'):
        from .source_workflow import scan_source_links
        return scan_source_links(self,sources,expected_rows=expected_rows,rules_version=rules_version)

    def replay_source_links(self,audit_id,*,version=None):
        from .source_workflow import replay_source_links
        return replay_source_links(self,audit_id,version=version)

    def build_event_source_index(self,source_path,**kwargs):
        from .indexed_event_workflow import build_event_source_index
        return build_event_source_index(self,source_path,**kwargs)

    def audit_indexed_events(self,index_id,selected_audit_id,**kwargs):
        from .indexed_event_workflow import audit_indexed_events
        return audit_indexed_events(self,index_id,selected_audit_id,**kwargs)

    def replay_indexed_events(self,audit_id,*,version=None):
        from .indexed_event_workflow import replay_indexed_events
        return replay_indexed_events(self,audit_id,version=version)

    def audit_temporal_reference(self,temporal_audit_id,**kwargs):
        from .temporal_null_workflow import audit_temporal_reference
        return audit_temporal_reference(self,temporal_audit_id,**kwargs)

    def replay_temporal_reference(self,reference_id,*,version=None):
        from .temporal_null_workflow import replay_temporal_reference
        return replay_temporal_reference(self,reference_id,version=version)

    def audit_selected_actor_events(self,index_id,selected_audit_id,**kwargs):
        from .actor_event_workflow import audit_selected_actor_events
        return audit_selected_actor_events(self,index_id,selected_audit_id,**kwargs)

    def replay_actor_events(self,audit_id,*,version=None):
        from .actor_event_workflow import replay_actor_events
        return replay_actor_events(self,audit_id,version=version)

    def audit_wait_markers(self,actor_audit_id,**kwargs):
        from .wait_marker_workflow import audit_wait_markers
        return audit_wait_markers(self,actor_audit_id,**kwargs)

    def replay_wait_markers(self,alignment_id,*,version=None):
        from .wait_marker_workflow import replay_wait_markers
        return replay_wait_markers(self,alignment_id,version=version)

    def audit_edge_flow(self,temporal_audit_id,**kwargs):
        from .graph_hodge_workflow import audit_edge_flow
        return audit_edge_flow(self,temporal_audit_id,**kwargs)

    def replay_edge_flow(self,audit_id,*,version=None):
        from .graph_hodge_workflow import replay_edge_flow
        return replay_edge_flow(self,audit_id,version=version)

    def start_research_cycle(self,**kwargs):
        from .research_cycle import start_research_cycle
        return start_research_cycle(self,**kwargs)

    def resume_research_cycle(self,cycle_id):
        from .research_cycle import resume_research_cycle
        return resume_research_cycle(self,cycle_id)

    def design(self,behavior_id,*,trials_per_arm=3,seed=42,max_rounds=6,live=False,harness='responses',job_id=None,allow_abstract_pilot=False):
        from .experiments import create_protocol
        from .environments import validate_spec
        behavior=self.store.get(behavior_id)['payload']
        if behavior.get('research_quality_status') in ('schema_defect_requires_re_review','superseded_schema_defect_review'):
            raise ValueError('Use the corrected skeptical review before designing a study: '+str(behavior.get('corrected_review_behavior_id','review pending')))
        if behavior['status']=='rejected':raise ValueError('Rejected behavior cannot silently become a supported experiment')
        if behavior['experiment_fit']!='shared_artifact_coordination' and not allow_abstract_pilot:
            raise ValueError('This candidate is outside the initial shared-artifact route. Review another supported authoring family or a new capability through environment authoring or the research cycle; artifact compatibility alone would not establish mechanism fit')
        job_id=job_id or 'design-'+uuid.uuid4().hex[:10]
        incident={'id':behavior_id,'title':behavior['name'],'source_refs':behavior['evidence_ids']}
        backend={'harness':'responses' if live else 'scripted','model':self.settings.model if live else 'deterministic_offline_policy',
                 'generation':{'max_output_tokens':600,'temperature':'provider_default','sampling_seed':'not_set'}}
        override=None
        protocol=create_protocol(incident,trials_per_arm=trials_per_arm,seed=seed,max_rounds=max_rounds,subject_backend=backend)
        charter={'hypothesis':'Private evidence reminders may change independently verified publication outcomes in a synthetic handoff task.',
                 'primary_outcome_rationale':'Publication validity is checked by the environment oracle, independent of subject claims.',
                 'mechanism':'A message may prompt artifact inspection or coordination before publication.',
                 'identification_assumptions':['Independent reset swarm runs; frozen policy/model and environment across arms.'],
                 'confound_checks':['Keep assignment private; forbid historical future and treatment labels in subject inputs.'],
                 'falsifiers':['The reminder produces no improvement or worsens valid publication within the fixed action budget.'],
                 'transport_limitations':['An abstract task cannot identify the original historical incident mechanism.']}
        if live:
            discovery=self.store.get(behavior['discovery_id'],behavior.get('source_refs',{}).get('discovery',{}).get('version'))['payload'];dataset=self.store.get(behavior['dataset_id'],behavior.get('source_refs',{}).get('dataset',{}).get('version'))['payload']
            agent=ResearchAgents(self.settings,self.store,self.research_harness(harness))
            builder_schema=object_schema({'max_rounds':{'type':'integer','minimum':2,'maximum':12},'valid_probability':{'type':'number','minimum':0,'maximum':1},'completion_claim':TEXT,'abstraction_rationale':TEXT,'missing_capabilities':{'type':'array','items':TEXT}})
            built=agent.run('environment-builder',{'task':'Configure a supported shared_artifact_coordination environment for this hypothesis. Max_rounds 6 is the default; initial artifact valid_probability .25 is the default. This is an abstraction, not historical replay. Do not claim unsupported browser/memory/topology fidelity. Return only supported parameters and explicit omissions.','behavior':behavior,'supported_template':protocol['environment'],'output_schema':builder_schema},builder_schema,dataset,discovery,job_id)
            override={'max_rounds':built['max_rounds'],'initial_state_distribution':{'valid_probability':built['valid_probability'],'completion_claim':built['completion_claim']}}
            protocol=create_protocol(incident,trials_per_arm=trials_per_arm,seed=seed,max_rounds=max_rounds,environment_override=override,subject_backend=backend)
            charter=agent.run('causal-methodologist',{'task':'Critique and explain this fixed randomized protocol. No observational causal claim. You may propose future experiments but cannot change registered outcomes after results.','behavior':behavior,'protocol':protocol,'output_schema':DESIGN_SCHEMA},DESIGN_SCHEMA,dataset,discovery,job_id)
        # Frozen executable specification, before subject generation or outcomes.
        return self.store.put('protocol',{'protocol':protocol,'frozen_hash':fingerprint(protocol),'registered_at':now(),'status':'registered','agent_mode':'live' if live else 'offline_template',
            'research_charter':charter,'environment_builder':built if live else {'status':'fixed_offline_template'},
            'subject_adapter_hash':hashlib.sha256(Path(__file__).with_name('harness.py').read_bytes()).hexdigest() if live else None,
            'historical_mechanism_support':'unestablished','behavior_id':behavior_id,'abstract_pilot_override':allow_abstract_pilot})

    def experiment(self,protocol_id,*,live=False,harness='responses',job_id=None):
        from .experiments import run_experiment
        job_id=job_id or 'experiment-'+uuid.uuid4().hex[:10]
        registered=self.store.get(protocol_id)
        protocol=verify_protocol(registered)
        if live and harness!='responses':raise ValueError('Experimental subjects currently support Responses; Codex is supported for research roles')
        expected=protocol.get('subject_backend',{})
        actual_model=self.settings.model if live else 'deterministic_offline_policy'
        actual_backend={'harness':'responses' if live else 'scripted','model':actual_model,
                        'generation':{'max_output_tokens':600,'temperature':'provider_default','sampling_seed':'not_set'}}
        if expected!=actual_backend:raise ValueError('Subject backend differs from frozen registration; create a new protocol')
        if live and registered['payload'].get('subject_adapter_hash')!=hashlib.sha256(Path(__file__).with_name('harness.py').read_bytes()).hexdigest():
            raise ValueError('Subject adapter changed after registration; create a new protocol')
        if live:
            maximum=protocol['design']['trials_per_arm']*len(protocol['arms'])*protocol['environment']['max_rounds']*len(protocol['environment']['agents'])
            if self.store.usage()['calls']+maximum>self.settings.max_calls:raise ValueError(f'Worst-case {maximum} subject calls exceed remaining cap; register a smaller study or explicitly increase the cap before execution')
        runner=None
        if live:
            model=self.harness(harness)
            def runner(request):return model.subject({**request,'_job_id':job_id})
        outdir=self.settings.runtime/'runs'/job_id
        from .audit import snapshot_execution_code
        progress_state={'completed':0,'total':protocol['design']['trials_per_arm']*len(protocol['arms']),
            'arm':None,'run_id':None}
        def progress(value):
            progress_state.update({key:value[key] for key in ('completed','total','arm','run_id')})
            self.store.job(job_id,'running',{'stage':'experiment','protocol_id':protocol_id,
                'live':live,'progress':dict(progress_state)})
        self.store.job(job_id,'running',{'stage':'experiment','protocol_id':protocol_id,
            'live':live,'progress':dict(progress_state)})
        try:
            snapshot_execution_code(outdir)
            result=run_experiment(protocol,agent_runner=runner,output_dir=outdir,backend_metadata=actual_backend,on_progress=progress)
        except Exception as e:
            failure_path=outdir/'report.json'
            failure_id=None
            if failure_path.exists():
                incomplete=json.loads(failure_path.read_text(encoding='utf-8'))
                incomplete.update({'protocol_id':protocol_id,'behavior_id':registered['payload']['behavior_id'],'agent_mode':'live' if live else 'offline_simulation','artifact_directory':str(outdir),'research_job_id':job_id})
                failure_id=self.store.put('experiment',incomplete)['id']
            self.store.job(job_id,'failed',{'stage':'experiment','protocol_id':protocol_id,'live':live,
                'progress':dict(progress_state),'error':str(e),'artifact_directory':str(outdir),'incomplete_result_id':failure_id})
            self.store.trace(job_id,{'type':'experiment_failure','artifact_directory':str(outdir),'protocol_id':protocol_id,'analysis':'none; infrastructure failure is not behavioral exclusion'})
            raise
        internal_hash=result.pop('report_hash',None)
        result.update({'protocol_id':protocol_id,'registered_hash':registered['payload']['frozen_hash'],
             'behavior_id':registered['payload']['behavior_id'],'model':self.settings.model if live else 'deterministic_offline_policy',
             'research_job_id':job_id,'agent_mode':'live' if live else 'offline_simulation','artifact_directory':str(outdir),
             'canonical_execution_report_hash':internal_hash,'claim_scope':'Randomized effect of supplied context in this registered abstract environment. Historical causal identification and generalization are unestablished.'})
        from .measurement import inspect_trajectories
        result['trajectory_review']=inspect_trajectories(result)
        obj=self.store.put('experiment',result)
        if registered['payload'].get('behavior_id'):
            record_experiment(self.store,registered['payload']['behavior_id'],obj)
        return obj

    def theorize(self,result_id,*,live=False,harness='responses',job_id=None):
        job_id=job_id or 'theory-'+uuid.uuid4().hex[:10]
        result=self.store.get(result_id)['payload'];behavior=self.store.get(result['behavior_id'])['payload']
        theory={'title':'Evidence-grounded handoffs: an exploratory hypothesis','statement':'Communication and artifact verification may jointly determine whether a reported completion becomes a valid shared result.',
                'mechanism':'Subjects may act on status narration, inspect evidence, or request repair; these are distinct observable pathways.',
                'predictions':['Changing inspection access, communication topology, and claim reliability may change outcomes.'],
                'boundary_conditions':['A small abstract task with role-scoped observations and a fixed action budget.'],
                'rival_theories':['The reminder only increases generic caution.','Turn ordering or subject instruction compliance explains differences.'],
                'falsifiers':['Reminder harms or does not change validity when replicated with adequate precision.'],
                'supporting_results':[],'conflicting_results':[],'replication_ids':[],'replication_status':'unreplicated',
                'scope':'Synthetic role-scoped inventory handoff; not an identified historical mechanism.',
                'causal_assumptions':['Run-level state is independent; subject backend remains stable across randomized runs.'],
                'next_experiments':['Replicate with new seeds and models; contrast evidence-specific reminder with generic caution.'],
                'limitations':['This template is a hypothesis, not an empirical finding.','Use the numeric effect report; zero and negative effects are retained.']}
        if live:
            discovery=self.store.get(behavior['discovery_id'],behavior.get('source_refs',{}).get('discovery',{}).get('version'))['payload'];dataset=self.store.get(behavior['dataset_id'],behavior.get('source_refs',{}).get('dataset',{}).get('version'))['payload']
            agent=ResearchAgents(self.settings,self.store,self.research_harness(harness))
            # Keep the model's packet bounded; independently computed statistics are authoritative.
            packet={k:v for k,v in result.items() if k not in ('runs','traces','run_records')}
            theory=agent.run('theory-curator',{'task':'Form a cautious theory candidate from this observational behavior and controlled pilot. Preserve null/negative evidence and uncertainty. Do not claim historical mechanism or generalization.','behavior':behavior,'result':packet,'output_schema':THEORY_SCHEMA},THEORY_SCHEMA,dataset,discovery,job_id)
        theory['executed_quantitative_evidence']=quantitative_summary(result)
        return register_theory(self.store,theory,result['behavior_id'],result_id,'live' if live else 'offline_template')

    def evaluate(self,result_id,*,live=False,harness='responses',job_id=None):
        job_id=job_id or 'evaluation-'+uuid.uuid4().hex[:10]
        result=self.store.get(result_id)['payload'];behavior=self.store.get(result['behavior_id'])['payload']
        explanation={'summary':'Authoritative outcomes and uncertainty are computed in code; this offline review adds no empirical evidence.',
            'interpretation':result['claim_scope'],'negative_findings':['No historical causal identification or cross-environment generalization is established.'],
            'protocol_deviation_review':['Review full run traces and frozen protocol before interpreting findings.'],
            'measurement_limitations':['A small pilot may have ceiling/floor outcomes and wide uncertainty.'],
            'next_checks':['Use fresh-seed replication and inspect failed/incorrect trajectories.']}
        if live:
            discovery=self.store.get(behavior['discovery_id'],behavior.get('source_refs',{}).get('discovery',{}).get('version'))['payload'];dataset=self.store.get(behavior['dataset_id'],behavior.get('source_refs',{}).get('dataset',{}).get('version'))['payload']
            agent=ResearchAgents(self.settings,self.store,self.research_harness(harness))
            explanation=agent.run('evaluator',{'task':'Explain the numeric report qualitatively. Do not write numerical values, counts, rates, percentages, p values, or numeric confidence levels in any output field: the numeric scoreboard and plain-language quantities are generated separately by code. Do not turn a wide interval into proof of no effect. Preserve null/negative findings and uncertainty, and distinguish possible deviations from verified ones.',
                'report':{k:v for k,v in result.items() if k!='runs'},'output_schema':EVALUATION_SCHEMA},EVALUATION_SCHEMA,dataset,discovery,job_id)
        reviewed=numeric_free_commentary(explanation)
        return self.store.put('evaluation',{'experiment_id':result_id,'behavior_id':result['behavior_id'],'agent_mode':'live' if live else 'offline_template',
            'authoritative_analysis':result.get('analysis'),'quantitative_summary':quantitative_summary(result),
            'commentary_status':'qualitative_commentary' if reviewed else 'needs_numeric_review','explanation':explanation,
            'commentary_limitations':['The lexical gate rejects digits, but does not prove semantic consistency; agent commentary requires review.']})

    def audit(self,result_id):
        if self.store.get(result_id)['kind']=='timed_resource_experiment':
            from .timed_resource_workflow import audit_timed_resource
            return audit_timed_resource(self,result_id)
        if self.store.get(result_id)['kind']=='resource_experiment':
            from .resource_workflow import audit_resource
            return audit_resource(self,result_id)
        from .audit import replay_report,check_execution_archive
        registered_result=self.store.get(result_id);result=registered_result['payload']
        if registered_result['kind'] not in ('experiment','network_experiment','complementary_experiment'):raise ValueError('Audit requires an executed result')
        path=Path(result['artifact_directory'])/'report.json'
        raw=json.loads(path.read_text(encoding='utf-8'));verification=replay_report(raw)
        expected=verify_protocol(self.store.get(result['protocol_id']))
        consistency=all((raw['protocol']['protocol_hash']==expected['protocol_hash'],
             raw.get('report_hash')==result.get('canonical_execution_report_hash'),
             raw.get('analysis')==result.get('analysis'),raw.get('runs')==result.get('runs')))
        verification['checks'].append({'name':'registered_result_matches_canonical_report','passed':consistency})
        if raw.get('status')=='complete':
            if raw['protocol'].get('study_kind')=='complementary_information_factorial':
                from .complementary_experiments import analyze_complementary_runs
                recomputed=analyze_complementary_runs(raw['runs'],raw['protocol'])
            elif registered_result['kind']=='network_experiment':
                from .diffusion_experiments import analyze_diffusion_runs
                recomputed=analyze_diffusion_runs(raw['runs'],raw['protocol'])
            else:
                from .experiments import summarize_runs
                recomputed=summarize_runs(raw['runs'],raw['protocol'])
            verification['checks'].append({'name':'analysis_recomputed_from_recorded_outcomes','passed':recomputed==raw['analysis']})
        verification['passed']=verification['passed'] and all(c['passed'] for c in verification['checks'])
        verification['execution_archive']=check_execution_archive(path.parent)
        return self.store.put('verification',{'experiment_id':result_id,'result_kind':registered_result['kind'],
             'result_ref':{k:registered_result[k] for k in ('id','version','hash')},**verification})

    def evaluate_claims(self,result_id,*,live=False,harness='responses',job_id=None,fact_ids=None):
        if self.store.get(result_id)['kind']=='timed_resource_experiment':
            from .timed_resource_workflow import evaluate_timed_resource_claims
            return evaluate_timed_resource_claims(self,result_id,live=live,harness=harness,job_id=job_id,fact_ids=fact_ids)
        if self.store.get(result_id)['kind']=='resource_experiment':
            from .resource_workflow import evaluate_resource_claims
            return evaluate_resource_claims(self,result_id,live=live,harness=harness,job_id=job_id,fact_ids=fact_ids)
        from .claim_audit import build_fact_ledger,default_fact_ids,select_fact_packet,claims_schema_for_packet,audit_claims,make_claim
        from .audit import replay_report
        from dataclasses import replace
        registered=self.store.get(result_id)
        if registered['kind'] not in ('experiment','network_experiment','complementary_experiment'):raise ValueError('Claim evaluation requires an executed experiment')
        result=registered['payload'];path=Path(result['artifact_directory'])/'report.json'
        raw=json.loads(path.read_text(encoding='utf-8'))
        if raw.get('report_hash')!=result.get('canonical_execution_report_hash'):raise ValueError('Canonical report differs from the registered result')
        ledger=build_fact_ledger(raw,report_id=result_id,replay_check=replay_report)
        packet=select_fact_packet(ledger,fact_ids or default_fact_ids(ledger),max_facts=24)
        job_id=job_id or 'claim-audit-'+uuid.uuid4().hex[:10]
        if live:
            bounded=replace(self.settings,max_output_tokens=6000,max_tool_rounds=2)
            agent=ResearchAgents(bounded,self.store,self.research_harness(harness,bounded))
            behavior=self.store.get(result['behavior_id'])['payload'] if result.get('behavior_id') else None
            if behavior:
                discovery=self.store.get(behavior['discovery_id'],behavior.get('source_refs',{}).get('discovery',{}).get('version'))['payload']
                dataset=self.store.get(behavior['dataset_id'],behavior.get('source_refs',{}).get('dataset',{}).get('version'))['payload']
            else:dataset={'messages':[]};discovery={'graph':{'edges':[]},'candidates':[]}
            schema=claims_schema_for_packet(packet)
            response=agent.run('evaluator',{'task':'Perform post-execution aggregate fact interpretation. Arm labels are intentionally visible; this is not a blinded outcome judgment. Return one typed claim for each supplied fact. Copy its exact fact_id, kind, scope and value as expected, and the packet source_fingerprint. Use statement only to explain that fact briefly; mechanisms, historical claims and generalization cannot be established. Preserve the no-insertion baseline comparison and the distinction between any-agent and publisher/version inspection. Do not search unrelated source evidence or add claims outside this packet.',
                'fact_packet':packet,'output_schema':schema},schema,dataset,discovery,job_id)
            claims=response['claims']
        else:claims=[make_claim(ledger,identity,fact['value']) for identity,fact in packet['facts'].items()]
        audit=audit_claims(ledger,claims)
        return self.store.put('claim_audit',{'experiment_id':result_id,'result_kind':registered['kind'],
            'result_ref':{k:registered[k] for k in ('id','version','hash')},'canonical_execution_report_hash':raw.get('report_hash'),
            'agent_mode':'live' if live else 'offline_fact_reconstruction','fact_packet':packet,'claims':claims,'audit':audit,
            'status':'verified_facts_only' if audit['all_executable_claims_supported'] else 'claim_mismatches',
            'research_job_id':job_id,'prose_scope':'Only generated approved_fact_text is verified. Model-written statements, mechanisms, historical claims and generalizations remain unverified.'})

    def design_network(self,*,trials_per_cell=2,seed=43,max_rounds=3,topologies=None,contexts=None,live=False):
        from .diffusion_experiments import create_diffusion_protocol
        backend={'harness':'responses' if live else 'scripted','model':self.settings.model if live else 'deterministic_offline_policy',
                 'generation':{'max_output_tokens':600,'temperature':'provider_default','sampling_seed':'not_set'}}
        protocol=create_diffusion_protocol(trials_per_cell=trials_per_cell,seed=seed,max_rounds=max_rounds,
            topologies=topologies or ['ring','complete'],contexts=contexts or ['placebo','source_thought'],subject_backend=backend)
        return self.store.put('network_protocol',{'protocol':protocol,'frozen_hash':fingerprint(protocol),'registered_at':now(),'status':'registered',
            'agent_mode':'live' if live else 'offline_template','subject_adapter_hash':hashlib.sha256(Path(__file__).with_name('harness.py').read_bytes()).hexdigest() if live else None})

    def replicate(self,protocol_id,*,seed,trials_per_arm=None):
        from .experiments import create_replication_protocol
        original=self.store.get(protocol_id)
        if original['kind']!='protocol':raise ValueError('Use the study-specific replication constructor for a network study')
        protocol=create_replication_protocol(verify_protocol(original),new_seed=seed,trials_per_arm=trials_per_arm)
        p={**original['payload'],'protocol':protocol,'frozen_hash':fingerprint(protocol),'registered_at':now(),'replicates_protocol_id':protocol_id}
        p.pop('amends_protocol_id',None);p.pop('amendment_reason',None)
        return self.store.put('protocol',p)

    def design_complementary(self,*,behavior_id=None,trials_per_cell=2,seed=4411,max_rounds=3,topologies=None,contexts=None,live=False):
        from .complementary_experiments import create_complementary_protocol
        incident=None
        if behavior_id:
            obj=self.store.get(behavior_id)
            if obj['kind']!='behavior' or obj['payload'].get('status')=='rejected':raise ValueError('Use a non-rejected behavior object for an incident reference')
            if obj['payload'].get('research_quality_status') in ('schema_defect_requires_re_review','superseded_schema_defect_review'):raise ValueError('Use the corrected skeptical review for an incident reference')
            incident={'id':behavior_id,'title':obj['payload']['name'],'source_refs':obj['payload'].get('evidence_ids',[])}
        backend={'harness':'responses','model':self.settings.model,
            'generation':{'max_output_tokens':600,'temperature':'provider_default','sampling_seed':'not_set'}} if live else {
            'harness':'scripted','model':'deterministic_offline_policy','generation':{'policy':'offline_complementary_policy'}}
        protocol=create_complementary_protocol(trials_per_cell=trials_per_cell,seed=seed,max_rounds=max_rounds,
            topologies=topologies or ['ring','complete'],contexts=contexts or ['placebo','source_thought'],incident=incident,subject_backend=backend)
        return self.store.put('complementary_protocol',{'protocol':protocol,'frozen_hash':fingerprint(protocol),'registered_at':now(),'status':'registered',
            'agent_mode':'live' if live else 'offline_template','behavior_id':behavior_id,
            'historical_mechanism_support':'unestablished; incident references motivate this abstraction and do not establish environment fit',
            'subject_adapter_hash':hashlib.sha256(Path(__file__).with_name('harness.py').read_bytes()).hexdigest() if live else None})

    def experiment_complementary(self,protocol_id,*,live=False,job_id=None):
        from .complementary_experiments import run_complementary_experiment,validate_complementary_protocol
        job_id=job_id or 'complementary-experiment-'+uuid.uuid4().hex[:10]
        registration=self.store.get(protocol_id)
        if registration['kind']!='complementary_protocol':raise ValueError('Complementary execution requires its study-specific protocol')
        protocol=verify_protocol(registration);validate_complementary_protocol(protocol)
        actual_backend={'harness':'responses','model':self.settings.model,
            'generation':{'max_output_tokens':600,'temperature':'provider_default','sampling_seed':'not_set'}} if live else {
            'harness':'scripted','model':'deterministic_offline_policy','generation':{'policy':'offline_complementary_policy'}}
        if protocol['subject_backend']!=actual_backend:raise ValueError('Subject backend differs from frozen complementary registration')
        if live and registration['payload'].get('subject_adapter_hash')!=hashlib.sha256(Path(__file__).with_name('harness.py').read_bytes()).hexdigest():raise ValueError('Subject adapter changed after registration')
        if live:
            maximum=protocol['design']['maximum_subject_calls']
            if self.store.usage()['calls']+maximum>self.settings.max_calls:raise ValueError(f'Worst-case {maximum} subject calls exceed remaining cap; register a smaller study or explicitly increase the cap')
        runner=None
        if live:
            model=self.harness('responses')
            def runner(request):return model.subject({**request,'_job_id':job_id})
        directory=self.settings.runtime/'runs'/job_id
        def progress(value):self.store.job(job_id,'running',{'stage':'complementary_experiment','protocol_id':protocol_id,'progress':value,'live':live})
        self.store.job(job_id,'running',{'stage':'complementary_experiment','protocol_id':protocol_id,'live':live})
        try:
            result=run_complementary_experiment(protocol,agent_runner=runner,output_dir=directory,backend_metadata=actual_backend,on_progress=progress)
        except Exception as e:
            failure_id=None
            if (directory/'report.json').exists():
                failed=json.loads((directory/'report.json').read_text(encoding='utf-8'));failed.update({'protocol_id':protocol_id,
                    'behavior_id':registration['payload'].get('behavior_id'),'artifact_directory':str(directory),
                    'agent_mode':'live' if live else 'offline_simulation','research_job_id':job_id})
                failure_id=self.store.put('complementary_experiment',failed)['id']
            self.store.job(job_id,'failed',{'stage':'complementary_experiment','error':str(e),'incomplete_result_id':failure_id})
            self.store.trace(job_id,{'type':'experiment_failure','protocol_id':protocol_id,'artifact_directory':str(directory),
                'analysis':'none; infrastructure failure is not behavioral exclusion'})
            raise
        internal_hash=result.pop('report_hash',None)
        result.update({'protocol_id':protocol_id,'registered_hash':registration['payload']['frozen_hash'],
            'behavior_id':registration['payload'].get('behavior_id'),'agent_mode':'live' if live else 'offline_simulation',
            'model':actual_backend['model'],'artifact_directory':str(directory),'research_job_id':job_id,'canonical_execution_report_hash':internal_hash})
        obj=self.store.put('complementary_experiment',result)
        self.store.job(job_id,'completed',{'stage':'complementary_experiment','result_id':obj['id'],'protocol_id':protocol_id,'live':live})
        return obj

    def link_replication(self,original_result_id,replication_result_id,*,theory_id=None):
        from .library import link_replication
        return link_replication(self.store,original_result_id,replication_result_id,theory_id)

    def experiment_network(self,protocol_id,*,live=False,job_id=None):
        from .diffusion_experiments import run_diffusion_experiment
        from .audit import snapshot_execution_code
        job_id=job_id or 'network-experiment-'+uuid.uuid4().hex[:10]
        registration=self.store.get(protocol_id);protocol=verify_protocol(registration)
        actual_backend={'harness':'responses' if live else 'scripted','model':self.settings.model if live else 'deterministic_offline_policy',
                 'generation':{'max_output_tokens':600,'temperature':'provider_default','sampling_seed':'not_set'}}
        if protocol['subject_backend']!=actual_backend:raise ValueError('Subject backend differs from frozen network registration')
        if live and registration['payload'].get('subject_adapter_hash')!=hashlib.sha256(Path(__file__).with_name('harness.py').read_bytes()).hexdigest():raise ValueError('Subject adapter changed after registration')
        if live:
            maximum=protocol['design']['trials_per_cell']*len(protocol['design']['cells'])*max(s['max_rounds']*len(s['agents']) for s in protocol['environments'].values())
            if self.store.usage()['calls']+maximum>self.settings.max_calls:raise ValueError(f'Worst-case {maximum} subject calls exceed remaining cap; register a smaller study or explicitly increase the cap')
        runner=None
        if live:
            model=self.harness('responses')
            def runner(request):return model.subject({**request,'_job_id':job_id})
        directory=self.settings.runtime/'runs'/job_id;snapshot_execution_code(directory)
        def progress(value):self.store.job(job_id,'running',{'stage':'network_experiment','protocol_id':protocol_id,'progress':value,'live':live})
        try:
            result=run_diffusion_experiment(protocol,agent_runner=runner,output_dir=directory,backend_metadata=actual_backend,on_progress=progress)
        except Exception as e:
            failure_id=None
            if (directory/'report.json').exists():
                failed=json.loads((directory/'report.json').read_text(encoding='utf-8'));failed.update({'protocol_id':protocol_id,'artifact_directory':str(directory),'agent_mode':'live' if live else 'offline_simulation'})
                failure_id=self.store.put('network_experiment',failed)['id']
            self.store.job(job_id,'failed',{'stage':'network_experiment','error':str(e),'incomplete_result_id':failure_id});raise
        internal_hash=result.pop('report_hash',None)
        result.update({'protocol_id':protocol_id,'agent_mode':'live' if live else 'offline_simulation','model':actual_backend['model'],'artifact_directory':str(directory),'research_job_id':job_id,'canonical_execution_report_hash':internal_hash})
        obj=self.store.put('network_experiment',result)
        self.store.job(job_id,'completed',{'stage':'network_experiment','result_id':obj['id'],'protocol_id':protocol_id,'live':live})
        return obj

    def workflow(self,*,source=None,start=None,end=None,limit=2000,live=False,harness='responses',trials_per_arm=3,job_id=None):
        job_id=job_id or 'workflow-'+uuid.uuid4().hex[:10]
        outputs={}
        def stage(name,fn):
            self.store.job(job_id,'running',{'stage':name,'outputs':outputs,'live':live})
            obj=fn();outputs[name]=obj['id'];return obj
        try:
            dataset=stage('dataset',lambda:self.ingest(source,start=start,end=end,limit=limit))
            discovery=stage('discovery',lambda:self.observe(dataset['id']))
            behaviors=self.investigate(discovery['id'],count=2,live=live,harness=harness,job_id=job_id)
            outputs['behaviors']=[b['id'] for b in behaviors]
            chosen=next((b for b in behaviors if b['payload']['experiment_fit']=='shared_artifact_coordination' and b['payload']['status']!='rejected'),None)
            if not chosen:raise ValueError('No candidate fits the initial shared-artifact workflow. Discovery artifacts retained; review another supported world through environment authoring or the research cycle, or declare missing capabilities.')
            outputs['behavior']=chosen['id']
            protocol=stage('protocol',lambda:self.design(chosen['id'],trials_per_arm=trials_per_arm,live=live,harness=harness,job_id=job_id))
            result=stage('experiment',lambda:self.experiment(protocol['id'],live=live,job_id=job_id))
            stage('evaluation',lambda:self.evaluate(result['id'],live=live,harness=harness,job_id=job_id))
            stage('theory',lambda:self.theorize(result['id'],live=live,harness=harness,job_id=job_id))
            self.store.job(job_id,'completed',{'outputs':outputs,'live':live})
            return {'job_id':job_id,'outputs':outputs}
        except Exception as e:
            self.store.job(job_id,'failed',{'outputs':outputs,'error':str(e),'live':live})
            raise
