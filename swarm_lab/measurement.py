"""Metric definitions and exploratory actor/version-resolved trajectory checks."""
METRICS={
    'success':{'label':'Correct publication','unit':'whole_swarm_run','definition':'One if actual published contents equal requirements; zero for incorrect or absent publication.','status':'registered_primary'},
    'inspected_publication':{'label':'Published version previously inspected by any agent','unit':'whole_swarm_run','definition':'One if at least one agent inspected the exact artifact version later published. An inspection may reveal an error; this does not imply validation or publisher inspection.','status':'registered_secondary'},
    'coordinator_inspected_any':{'label':'Publisher inspected any artifact version','unit':'whole_swarm_run','definition':'At least one successful inspection action by the coordinator before terminal publication or budget.','status':'posthoc_descriptive'},
    'coordinator_inspected_published_version':{'label':'Publisher inspected the published artifact version','unit':'whole_swarm_run','definition':'Coordinator inspected the exact version ultimately published, before publication.','status':'posthoc_descriptive'},
    'repair_before_publication':{'label':'Successful repair before publication','unit':'whole_swarm_run','definition':'At least one permitted successful repair action before a terminal publication.','status':'posthoc_descriptive'},
}

def inspect_trajectories(result):
    rows=[]
    for run in result.get('runs',[]):
        published=run['final_state'].get('published')
        version=published.get('version') if published else None
        inspections=[t for t in run['turns'] if t['action'].get('action')=='inspect_artifact' and t['tool_result'].get('ok')]
        own=[t for t in inspections if t['agent_id']=='coordinator']
        any_current=bool(published and any(t['tool_result'].get('version')==version for t in inspections))
        rows.append({'run_id':run['run_id'],'arm':run['arm'],'success':run['outcomes']['success'],
            'published_version':version,'coordinator_inspected_any':int(bool(own)),
            'coordinator_inspected_published_version':int(bool(published and any(t['tool_result'].get('version')==version for t in own))),
            'any_agent_inspected_published_version':int(any_current),'registered_metric_matches':int(any_current)==run['outcomes']['inspected_publication'],
            'repair_before_publication':int(bool(published and any(t['action'].get('action')=='repair_artifact' and t['tool_result'].get('ok') for t in run['turns']))),
            'initial_defect':run['initial_state'].get('initial_defect'),'action_sequence':[{'agent':t['agent_id'],'action':t['action'].get('action'),'ok':t['tool_result'].get('ok')} for t in run['turns']]})
    arms={}
    for arm in {r['arm'] for r in rows}:
        group=[r for r in rows if r['arm']==arm]
        arms[arm]={'n':len(group),**{key:sum(r[key] for r in group) for key in ('coordinator_inspected_any','coordinator_inspected_published_version','any_agent_inspected_published_version','repair_before_publication')}}
    return {'metric_definitions':METRICS,'runs':rows,'arms':arms,'all_registered_inspection_metrics_match':all(r['registered_metric_matches'] for r in rows),
        'scope':'Posthoc descriptive trajectory decomposition. These pathways are not randomized mediators and do not identify a mediated causal effect.'}
