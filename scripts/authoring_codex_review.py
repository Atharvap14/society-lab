"""Review the unchanged saved world through a declared alternate research harness."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from swarm_lab.pipeline import Lab

def main():
    lab=Lab();job='live-authoring-review-codex-01'
    if lab.store.job_exists(job):raise ValueError('Review already launched; inspect saved evidence')
    lab.store.start_job(job,{'stage':'resume_world_fit','harness':'codex',
        'amendment':'Same saved proposal and world; prior Responses empty incomplete outputs retained. Research reviewer harness changed explicitly.'})
    try:
        result=lab.resume_environment_review('environment_construction_attempt-864275443475',live=True,harness='codex',job_id=job)
        lab.store.job(job,'completed',{'stage':'resume_world_fit','harness':'codex','result_id':result['id']})
        p=result['payload']
        print(json.dumps({'id':result['id'],'construction':p['construction_status'],'eligibility':p['experiment_eligibility'],
            'review':p.get('fit_review'),'usage':lab.store.usage()},indent=2),flush=True)
    except Exception as error:
        lab.store.job(job,'failed',{'stage':'resume_world_fit','harness':'codex','error':str(error)});raise

if __name__=='__main__':main()
