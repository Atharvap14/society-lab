"""Resume one saved review and repeat one explicitly amended authoring check."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from swarm_lab.pipeline import Lab

def main():
    lab=Lab()
    cases=[('live-authoring-review-resume-01',lambda job:lab.resume_environment_review(
        'environment_construction_attempt-864275443475',live=True,job_id=job)),
        ('live-authoring-resource-gating-02',lambda job:lab.construct_environment(
            behavior_id='behavior-ad77419c8fab',research_question='Which world can test task-specific versus whole-agent deferral when another agent occupies a shared computer?',
            required_capabilities=['exclusive_shared_computer','recipient_scoped_messages'],live=True,job_id=job))]
    for job,action in cases:
        if lab.store.job_exists(job):raise ValueError('This fixed forward check was already launched')
        lab.store.start_job(job,{'stage':'environment_authoring_forward_repair'})
        try:
            result=action(job);p=result['payload']
            if job.endswith('gating-02'):
                result=lab.store.put('environment_blueprint',{**p,'amends_blueprint_id':'environment_blueprint-8dbf5d805122',
                    'amendment_reason':'Provider schema now constrains source_ids to exact pinned object identities. Prior malformed source references remain archived.'},result['id']);p=result['payload']
            lab.store.job(job,'completed',{'stage':'environment_authoring_forward_repair','result_id':result['id']})
            print(json.dumps({'blueprint_id':result['id'],'status':p['construction_status'],
                'eligibility':p['experiment_eligibility'],'missing':p['missing_capabilities'],
                'errors':p.get('errors',[]),'usage':lab.store.usage()},indent=2),flush=True)
        except Exception as error:
            lab.store.job(job,'failed',{'stage':'environment_authoring_forward_repair','error':str(error)});raise

if __name__=='__main__':main()
