"""Register a following-week descriptive import without a model call."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from swarm_lab.pipeline import Lab

def main():
    lab=Lab();job='historical-following-week-observation-01'
    if lab.store.job_exists(job):raise ValueError('This source window has already been registered; inspect job/artifacts')
    lab.store.start_job(job,{'stage':'historical_observation','models':False})
    try:
        dataset=lab.ingest(start='2025-04-16',end='2025-04-23',limit=6000)
        discovery=lab.observe(dataset['id'])
        graph=lab.screen_graph(discovery['id'])
        spectral=lab.project_observables(graph['id'])
        p=spectral['payload'];lab.store.job(job,'completed',{'stage':'historical_observation',
            'dataset_id':dataset['id'],'discovery_id':spectral['id'],
            'scope':'Retrospective following-week descriptive sample, not a preregistered holdout or independent causal evidence'})
        print(json.dumps({'dataset_id':dataset['id'],'discovery_id':spectral['id'],'discovery_version':spectral['version'],
            'messages':len(dataset['payload']['messages']),'fingerprint':dataset['payload']['fingerprint'],
            'candidate_count':len(p['candidates']),'graph_lead_count':len(p.get('graph_search',{}).get('leads',[])),
            'usage':lab.store.usage()},indent=2),flush=True)
    except Exception as error:
        lab.store.job(job,'failed',{'stage':'historical_observation','error':str(error)});raise

if __name__=='__main__':main()
