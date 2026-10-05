"""Local command-line entry point; live paid execution is opt-in."""
import argparse
import json
from pathlib import Path
from .config import Settings
from .pipeline import Lab

def read_source_plan(path):
    from .source_workflow import MAX_PLAN_BYTES
    with path.open('rb') as handle:raw=handle.read(MAX_PLAN_BYTES+1)
    if len(raw)>MAX_PLAN_BYTES:raise ValueError('Source-link plan exceeds its bounded file size')
    def pairs(entries):
        result={}
        for key,value in entries:
            if key in result:raise ValueError('Duplicate source plan JSON key')
            result[key]=value
        return result
    def constant(value):raise ValueError('Source plans require finite JSON')
    plan=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=constant)
    if type(plan) is not dict or not set(plan)<= {'sources','expected_rows','rules_version'} or 'sources' not in plan:
        raise ValueError('Source-link plan requires sources and supported optional fields')
    return plan

def read_event_index_plan(path):
    """A bounded declarative build plan; the host chooses the destination."""
    with path.open('rb') as handle:raw=handle.read(256*1024+1)
    if len(raw)>256*1024:raise ValueError('Event index plan exceeds its bounded file size')
    def pairs(entries):
        result={}
        for key,value in entries:
            if key in result:raise ValueError('Duplicate event index plan JSON key')
            result[key]=value
        return result
    def constant(value):raise ValueError('Event index plans require finite JSON')
    plan=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=constant)
    allowed={'source_path','max_rows','max_compressed_bytes','max_expanded_bytes',
             'max_row_bytes','max_seconds','source_metadata'}
    if type(plan) is not dict or 'source_path' not in plan or not set(plan)<=allowed:
        raise ValueError('Event index plans require source_path and supported bounded build options')
    return plan

def read_research_cycle_plan(path):
    """An exact-reference plan; callbacks, extra settings and duplicate keys are rejected."""
    with path.open('rb') as handle:raw=handle.read(1024*1024+1)
    if len(raw)>1024*1024:raise ValueError('Research cycle plan exceeds its bounded file size')
    def pairs(entries):
        result={}
        for key,value in entries:
            if key in result:raise ValueError('Duplicate research cycle plan JSON key')
            result[key]=value
        return result
    def constant(value):raise ValueError('Research cycle plans require finite JSON')
    plan=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=constant)
    allowed={'behavior_ref','source_refs','proposal','fit_review','blueprint_ref','research_question',
             'required_capabilities','trials_per_cell','seed','audit_seed','research_live','subjects_live',
             'research_harness','subject_harness','max_new_model_calls','job_id'}
    if type(plan) is not dict or not {'behavior_ref','source_refs'}<=set(plan) or not set(plan)<=allowed:
        raise ValueError('Research cycle plans require exact behavior/source refs and supported options')
    return plan

def main(argv=None):
    parser=argparse.ArgumentParser(description='Swarm Research Lab: discover, preregister, experiment, theorize.')
    parser.add_argument('--runtime',type=Path,help='Alternate research database directory')
    parser.add_argument('--model',default='gpt-5.4-mini')
    parser.add_argument('--max-calls',type=int,default=400)
    subs=parser.add_subparsers(dest='command',required=True)
    for command in ('ingest','workflow'):
        p=subs.add_parser(command);p.add_argument('--source',type=Path);p.add_argument('--start');p.add_argument('--end');p.add_argument('--limit',type=int,default=2000)
        if command=='workflow':p.add_argument('--live',action='store_true');p.add_argument('--harness',choices=['responses','codex'],default='responses');p.add_argument('--trials-per-arm',type=int,default=3)
    p=subs.add_parser('observe');p.add_argument('dataset_id');p.add_argument('--measurement-backend',choices=['regex','laya','jev'],default='regex');p.add_argument('--measurement-limit',type=int,default=32);p.add_argument('--live',action='store_true')
    p=subs.add_parser('investigate');p.add_argument('discovery_id');p.add_argument('--count',type=int,default=2);p.add_argument('--candidate',action='append');p.add_argument('--live',action='store_true');p.add_argument('--harness',choices=['responses','codex'],default='responses')
    p=subs.add_parser('screen-graph');p.add_argument('discovery_id');p.add_argument('--window-minutes',type=int,default=60);p.add_argument('--min-edge-events',type=int,default=5);p.add_argument('--max-windows',type=int,default=120)
    p=subs.add_parser('project-observables');p.add_argument('discovery_id')
    p=subs.add_parser('audit-mentions');p.add_argument('dataset_id');p.add_argument('--version',type=int);p.add_argument('--include-human',action='store_true')
    p=subs.add_parser('resume-investigation');p.add_argument('attempt_id');p.add_argument('--live',action='store_true');p.add_argument('--harness',choices=['responses','codex'],default='responses')
    p=subs.add_parser('design');p.add_argument('behavior_id');p.add_argument('--trials-per-arm',type=int,default=3);p.add_argument('--seed',type=int,default=42);p.add_argument('--max-rounds',type=int,default=6);p.add_argument('--live',action='store_true');p.add_argument('--harness',choices=['responses','codex'],default='responses');p.add_argument('--allow-abstract-pilot',action='store_true')
    for command,arg in (('experiment','protocol_id'),('evaluate','result_id'),('theorize','result_id')):
        p=subs.add_parser(command);p.add_argument(arg);p.add_argument('--live',action='store_true');p.add_argument('--harness',choices=['responses','codex'],default='responses')
    p=subs.add_parser('list');p.add_argument('--kind');p.add_argument('--limit',type=int,default=30)
    p=subs.add_parser('show');p.add_argument('object_id');p.add_argument('--history',action='store_true')
    subs.add_parser('usage')
    p=subs.add_parser('create-measurement-sample');p.add_argument('--plan',type=Path,required=True)
    p=subs.add_parser('record-measurement-judgment');p.add_argument('--plan',type=Path,required=True)
    p=subs.add_parser('show-measurement-review');p.add_argument('sample_id');p.add_argument('--sample-version',type=int,required=True);p.add_argument('--review-id',required=True);p.add_argument('--review-version',type=int,required=True);p.add_argument('--show-predictions',action='store_true')
    p=subs.add_parser('audit');p.add_argument('result_id')
    p=subs.add_parser('evaluate-claims');p.add_argument('result_id');p.add_argument('--live',action='store_true');p.add_argument('--harness',choices=['responses','codex'],default='responses')
    p=subs.add_parser('replicate');p.add_argument('protocol_id');p.add_argument('--seed',type=int,required=True);p.add_argument('--trials-per-arm',type=int)
    p=subs.add_parser('link-replication');p.add_argument('original_result_id');p.add_argument('replication_result_id');p.add_argument('--theory-id')
    p=subs.add_parser('design-network');p.add_argument('--trials-per-cell',type=int,default=2);p.add_argument('--seed',type=int,default=43);p.add_argument('--max-rounds',type=int,default=3);p.add_argument('--topology',action='append',choices=['ring','star','complete']);p.add_argument('--context',action='append',choices=['baseline','placebo','source_thought']);p.add_argument('--live',action='store_true')
    p=subs.add_parser('experiment-network');p.add_argument('protocol_id');p.add_argument('--live',action='store_true')
    p=subs.add_parser('design-complementary');p.add_argument('--behavior-id');p.add_argument('--trials-per-cell',type=int,default=2);p.add_argument('--seed',type=int,default=4411);p.add_argument('--max-rounds',type=int,default=3);p.add_argument('--topology',action='append',choices=['ring','star','complete']);p.add_argument('--context',action='append',choices=['baseline','placebo','source_thought']);p.add_argument('--live',action='store_true')
    p=subs.add_parser('experiment-complementary');p.add_argument('protocol_id');p.add_argument('--live',action='store_true')
    p=subs.add_parser('design-resource');p.add_argument('--behavior-id');p.add_argument('--trials-per-cell',type=int,default=2);p.add_argument('--seed',type=int,default=137);p.add_argument('--max-rounds',type=int,default=6);p.add_argument('--release-round',action='append',type=int);p.add_argument('--independent-work-steps',type=int,default=1);p.add_argument('--computer-work-steps',type=int,default=1);p.add_argument('--max-messages-per-agent',type=int);p.add_argument('--live',action='store_true')
    p=subs.add_parser('experiment-resource');p.add_argument('protocol_id');p.add_argument('--live',action='store_true')
    p=subs.add_parser('design-timed-resource');p.add_argument('--behavior-id');p.add_argument('--trials-per-cell',type=int,default=2);p.add_argument('--seed',type=int,default=149);p.add_argument('--trigger',choices=['first_decision','executed_wait_independent_pending','first_observed_resource_open'],default='executed_wait_independent_pending');p.add_argument('--max-rounds',type=int,default=6);p.add_argument('--release-round',action='append',type=int);p.add_argument('--resamples',type=int,default=2000);p.add_argument('--live',action='store_true')
    p=subs.add_parser('experiment-timed-resource');p.add_argument('protocol_id');p.add_argument('--live',action='store_true')
    p=subs.add_parser('design-revision-relay');p.add_argument('--blocks',type=int,default=2);p.add_argument('--seed',type=int,default=173);p.add_argument('--live',action='store_true')
    p=subs.add_parser('experiment-revision-relay');p.add_argument('protocol_id');p.add_argument('--protocol-version',type=int,required=True);p.add_argument('--live',action='store_true')
    p=subs.add_parser('audit-revision-relay');p.add_argument('result_id');p.add_argument('--version',type=int,required=True)
    p=subs.add_parser('audit-name-eligibility');p.add_argument('dataset_id');p.add_argument('--version',type=int);p.add_argument('--short-name',action='append',default=[]);p.add_argument('--unicode-shadow',action='store_true');p.add_argument('--include-human',action='store_true')
    p=subs.add_parser('compare-mention-graphs');p.add_argument('eligibility_audit_id')
    p=subs.add_parser('audit-selected-leads');p.add_argument('discovery_id');p.add_argument('--version',type=int);p.add_argument('--lead',action='append');p.add_argument('--short-name',action='append',default=[]);p.add_argument('--unicode-shadow',action='store_true')
    p=subs.add_parser('audit-temporal-paths');p.add_argument('selected_audit_id');p.add_argument('--version',type=int)
    p=subs.add_parser('replay-temporal-paths');p.add_argument('audit_id');p.add_argument('--version',type=int)
    p=subs.add_parser('scan-source-links');p.add_argument('--plan',type=Path,required=True)
    p=subs.add_parser('replay-source-links');p.add_argument('audit_id');p.add_argument('--version',type=int)
    p=subs.add_parser('build-event-index');p.add_argument('--plan',type=Path,required=True)
    p=subs.add_parser('audit-indexed-events');p.add_argument('index_id');p.add_argument('selected_audit_id');p.add_argument('--index-version',type=int);p.add_argument('--selected-audit-version',type=int);p.add_argument('--max-query-rows',type=int,default=15000)
    p=subs.add_parser('replay-indexed-events');p.add_argument('audit_id');p.add_argument('--version',type=int)
    p=subs.add_parser('audit-temporal-reference');p.add_argument('temporal_audit_id');p.add_argument('--version',type=int);p.add_argument('--window',action='append');p.add_argument('--variant',action='append');p.add_argument('--seed',type=int,default=4411);p.add_argument('--resamples',type=int,default=64);p.add_argument('--max-work',type=int,default=10000000)
    p=subs.add_parser('replay-temporal-reference');p.add_argument('reference_id');p.add_argument('--version',type=int)
    p=subs.add_parser('audit-actor-events');p.add_argument('index_id');p.add_argument('selected_audit_id');p.add_argument('--index-version',type=int);p.add_argument('--selected-audit-version',type=int);p.add_argument('--max-rows',type=int,default=15000);p.add_argument('--max-candidate-rows',type=int,default=15000);p.add_argument('--action-type',action='append')
    p=subs.add_parser('replay-actor-events');p.add_argument('audit_id');p.add_argument('--version',type=int)
    p=subs.add_parser('audit-wait-markers');p.add_argument('actor_audit_id');p.add_argument('--version',type=int);p.add_argument('--max-controls',type=int,default=32);p.add_argument('--max-work',type=int,default=1000000)
    p=subs.add_parser('replay-wait-markers');p.add_argument('alignment_id');p.add_argument('--version',type=int)
    p=subs.add_parser('audit-edge-flow');p.add_argument('temporal_audit_id');p.add_argument('--version',type=int);p.add_argument('--max-work',type=int,default=10000000);p.add_argument('--max-memory-bytes',type=int,default=16*1024**2)
    p=subs.add_parser('replay-edge-flow');p.add_argument('audit_id');p.add_argument('--version',type=int)
    p=subs.add_parser('start-research-cycle');p.add_argument('--plan',type=Path,required=True)
    p=subs.add_parser('resume-research-cycle');p.add_argument('cycle_id')
    p=subs.add_parser('construct-environment');p.add_argument('--behavior-id');p.add_argument('--research-question',default='');p.add_argument('--require',action='append',default=[]);p.add_argument('--blueprint',type=Path);p.add_argument('--fit-review',type=Path);p.add_argument('--live',action='store_true');p.add_argument('--harness',choices=['responses','codex'],default='responses')
    p=subs.add_parser('resume-environment-review');p.add_argument('attempt_id');p.add_argument('--live',action='store_true');p.add_argument('--harness',choices=['responses','codex'],default='responses')
    p=subs.add_parser('register-blueprint');p.add_argument('blueprint_id');p.add_argument('--blueprint-version',type=int);p.add_argument('--blueprint-hash');p.add_argument('--trials-per-cell',type=int,default=2);p.add_argument('--seed',type=int,default=4491);p.add_argument('--live',action='store_true')
    subs.add_parser('environments')
    p=subs.add_parser('serve');p.add_argument('--port',type=int,default=8765)
    args=parser.parse_args(argv);settings=Settings(model=args.model,max_calls=args.max_calls)
    if args.runtime:
        # A configurable store path never changes prompt or credential lookup roots.
        lab=Lab(settings)
        from .store import Store
        lab.store=Store(args.runtime/'lab.sqlite3')
    else:lab=Lab(settings)
    command=args.command
    if command=='ingest':result=lab.ingest(args.source,start=args.start,end=args.end,limit=args.limit)
    elif command=='workflow':result=lab.workflow(source=args.source,start=args.start,end=args.end,limit=args.limit,live=args.live,harness=args.harness,trials_per_arm=args.trials_per_arm)
    elif command=='observe':result=lab.observe(args.dataset_id,measurement_backend=args.measurement_backend,measurement_limit=args.measurement_limit,live=args.live)
    elif command=='investigate':result=lab.investigate(args.discovery_id,count=args.count,candidate_ids=args.candidate,live=args.live,harness=args.harness)
    elif command=='screen-graph':result=lab.screen_graph(args.discovery_id,window_minutes=args.window_minutes,min_edge_events=args.min_edge_events,max_windows=args.max_windows)
    elif command=='project-observables':result=lab.project_observables(args.discovery_id)
    elif command=='audit-mentions':result=lab.audit_mentions(args.dataset_id,version=args.version,agent_authored_only=not args.include_human)
    elif command=='resume-investigation':result=lab.resume_investigation(args.attempt_id,live=args.live,harness=args.harness)
    elif command=='design':result=lab.design(args.behavior_id,trials_per_arm=args.trials_per_arm,seed=args.seed,max_rounds=args.max_rounds,live=args.live,harness=args.harness,allow_abstract_pilot=args.allow_abstract_pilot)
    elif command=='experiment':result=lab.experiment(args.protocol_id,live=args.live,harness=args.harness)
    elif command=='evaluate':result=lab.evaluate(args.result_id,live=args.live,harness=args.harness)
    elif command=='theorize':result=lab.theorize(args.result_id,live=args.live,harness=args.harness)
    elif command=='list':result=[{k:v for k,v in o.items() if k!='payload'}|{'name':o['payload'].get('name',o['payload'].get('title',o['kind']))} for o in lab.store.list(args.kind,args.limit)]
    elif command=='show':result=lab.store.history(args.object_id) if args.history else lab.store.get(args.object_id)
    elif command=='usage':result=lab.store.usage()
    elif command=='audit':result=lab.audit(args.result_id)
    elif command=='evaluate-claims':result=lab.evaluate_claims(args.result_id,live=args.live,harness=args.harness)
    elif command=='replicate':result=lab.replicate(args.protocol_id,seed=args.seed,trials_per_arm=args.trials_per_arm)
    elif command=='link-replication':result=lab.link_replication(args.original_result_id,args.replication_result_id,theory_id=args.theory_id)
    elif command=='design-network':result=lab.design_network(trials_per_cell=args.trials_per_cell,seed=args.seed,max_rounds=args.max_rounds,topologies=args.topology,contexts=args.context,live=args.live)
    elif command=='experiment-network':result=lab.experiment_network(args.protocol_id,live=args.live)
    elif command=='design-revision-relay':result=lab.design_revision_relay(blocks=args.blocks,seed=args.seed,live=args.live)
    elif command=='experiment-revision-relay':result=lab.experiment_revision_relay(args.protocol_id,protocol_version=args.protocol_version,live=args.live)
    elif command=='audit-revision-relay':result=lab.audit_revision_relay(args.result_id,version=args.version)
    elif command=='design-complementary':result=lab.design_complementary(behavior_id=args.behavior_id,trials_per_cell=args.trials_per_cell,seed=args.seed,max_rounds=args.max_rounds,topologies=args.topology,contexts=args.context,live=args.live)
    elif command=='experiment-complementary':result=lab.experiment_complementary(args.protocol_id,live=args.live)
    elif command=='design-resource':result=lab.design_resource(behavior_id=args.behavior_id,trials_per_cell=args.trials_per_cell,seed=args.seed,max_rounds=args.max_rounds,release_rounds=args.release_round if args.release_round is not None else [1,2],independent_work_steps=args.independent_work_steps,computer_work_steps=args.computer_work_steps,max_messages_per_agent=args.max_messages_per_agent,live=args.live)
    elif command=='experiment-resource':result=lab.experiment_resource(args.protocol_id,live=args.live)
    elif command=='design-timed-resource':result=lab.design_timed_resource(behavior_id=args.behavior_id,trials_per_cell=args.trials_per_cell,seed=args.seed,trigger_kind=args.trigger,max_rounds=args.max_rounds,release_rounds=args.release_round if args.release_round is not None else [1,2],resamples=args.resamples,live=args.live)
    elif command=='experiment-timed-resource':result=lab.experiment_timed_resource(args.protocol_id,live=args.live)
    elif command=='audit-name-eligibility':result=lab.audit_name_eligibility(args.dataset_id,version=args.version,short_name_allowlist=args.short_name,include_unicode_shadow=args.unicode_shadow,agent_authored_only=not args.include_human)
    elif command=='compare-mention-graphs':result=lab.compare_mention_graphs(args.eligibility_audit_id)
    elif command=='audit-selected-leads':result=lab.audit_selected_leads(args.discovery_id,version=args.version,selected_lead_ids=args.lead,short_name_allowlist=args.short_name,include_unicode_shadow=args.unicode_shadow)
    elif command=='audit-temporal-paths':result=lab.audit_temporal_paths(args.selected_audit_id,version=args.version)
    elif command=='replay-temporal-paths':result=lab.replay_temporal_paths(args.audit_id,version=args.version)
    elif command=='scan-source-links':result=lab.scan_source_links(**read_source_plan(args.plan))
    elif command=='replay-source-links':result=lab.replay_source_links(args.audit_id,version=args.version)
    elif command=='build-event-index':result=lab.build_event_source_index(**read_event_index_plan(args.plan))
    elif command=='audit-indexed-events':result=lab.audit_indexed_events(args.index_id,args.selected_audit_id,index_version=args.index_version,selected_audit_version=args.selected_audit_version,max_query_rows=args.max_query_rows)
    elif command=='replay-indexed-events':result=lab.replay_indexed_events(args.audit_id,version=args.version)
    elif command=='audit-temporal-reference':result=lab.audit_temporal_reference(args.temporal_audit_id,version=args.version,window_ids=args.window,variants=args.variant,seed=args.seed,resamples=args.resamples,max_work=args.max_work)
    elif command=='replay-temporal-reference':result=lab.replay_temporal_reference(args.reference_id,version=args.version)
    elif command=='audit-actor-events':result=lab.audit_selected_actor_events(args.index_id,args.selected_audit_id,index_version=args.index_version,selected_audit_version=args.selected_audit_version,max_rows=args.max_rows,max_candidate_rows=args.max_candidate_rows,action_types=args.action_type)
    elif command=='replay-actor-events':result=lab.replay_actor_events(args.audit_id,version=args.version)
    elif command=='audit-wait-markers':result=lab.audit_wait_markers(args.actor_audit_id,version=args.version,max_controls=args.max_controls,max_work=args.max_work)
    elif command=='replay-wait-markers':result=lab.replay_wait_markers(args.alignment_id,version=args.version)
    elif command=='audit-edge-flow':result=lab.audit_edge_flow(args.temporal_audit_id,version=args.version,max_work=args.max_work,max_memory_bytes=args.max_memory_bytes)
    elif command=='replay-edge-flow':result=lab.replay_edge_flow(args.audit_id,version=args.version)
    elif command=='start-research-cycle':result=lab.start_research_cycle(**read_research_cycle_plan(args.plan))
    elif command=='resume-research-cycle':result=lab.resume_research_cycle(args.cycle_id)
    elif command=='construct-environment':result=lab.construct_environment(behavior_id=args.behavior_id,research_question=args.research_question,
        required_capabilities=args.require,proposal=json.loads(args.blueprint.read_text(encoding='utf-8')) if args.blueprint else None,
        fit_review=json.loads(args.fit_review.read_text(encoding='utf-8')) if args.fit_review else None,live=args.live,harness=args.harness)
    elif command=='resume-environment-review':result=lab.resume_environment_review(args.attempt_id,live=args.live,harness=args.harness)
    elif command=='register-blueprint':result=lab.register_blueprint(args.blueprint_id,blueprint_version=args.blueprint_version,blueprint_hash=args.blueprint_hash,trials_per_cell=args.trials_per_cell,seed=args.seed,live=args.live)
    elif command in ('create-measurement-sample','record-measurement-judgment'):
        from .measurement_review_workflow import read_review_plan
        result=getattr(lab,command.replace('-','_'))(**read_review_plan(args.plan))
    elif command=='show-measurement-review':
        from .measurement_review_workflow import measurement_review_workspace
        result=measurement_review_workspace(lab.store,sample_id=args.sample_id,sample_version=args.sample_version,
            review_id=args.review_id,review_version=args.review_version,include_predictions=args.show_predictions)
    elif command=='environments':
        from .environment_api import capabilities
        result=capabilities()
    elif command=='serve':
        from .server import serve
        serve(lab,args.port);return
    else:parser.error('Unknown command')
    # Do not dump the entire raw dataset by default.
    if isinstance(result,dict) and 'payload' in result:
        result={k:v for k,v in result.items() if k!='payload'}|{'name':result['payload'].get('name',result['kind'])}
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
