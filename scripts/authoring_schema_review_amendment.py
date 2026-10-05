"""One unchanged-world review after an equivalent provider grammar simplification."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from swarm_lab.pipeline import Lab

def main():
    lab=Lab();job='live-authoring-review-schema-amendment-01'
    if lab.store.job_exists(job):raise ValueError('This schema amendment was already launched')
    lab.store.start_job(job,{'stage':'resume_world_fit','harness':'responses',
        'amendment':'Only a provider-facing regex implied by an exact enum is removed; local full validation and saved proposal/world remain unchanged. Grammar failure is a hypothesis, not established.'})
    try:
        result=lab.resume_environment_review('environment_construction_attempt-864275443475',live=True,job_id=job)
        lab.store.job(job,'completed',{'stage':'resume_world_fit','result_id':result['id']})
        p=result['payload'];print(json.dumps({'id':result['id'],'construction':p['construction_status'],
            'eligibility':p['experiment_eligibility'],'review':p.get('fit_review'),'usage':lab.store.usage()},indent=2),flush=True)
    except Exception as error:
        lab.store.job(job,'failed',{'stage':'resume_world_fit','error':str(error)});raise

if __name__=='__main__':main()
