"""New forward check after tightening source object identity constraints."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from swarm_lab.pipeline import Lab

def main():
    lab=Lab();job='live-authoring-resource-gating-02'
    if lab.store.job_exists(job):raise ValueError('This amended forward check has already been launched')
    lab.store.start_job(job,{'stage':'source_gating_amendment',
        'amends':'environment_blueprint-8dbf5d805122','change':'Source object identity schema constrained; nested evidence citations constrained separately.'})
    try:
        result=lab.construct_environment(behavior_id='behavior-ad77419c8fab',
            research_question='Which world can test task-specific versus whole-agent deferral when another agent occupies a shared computer?',
            required_capabilities=['exclusive_shared_computer','recipient_scoped_messages'],live=True,job_id=job)
        p=result['payload']
        result=lab.store.put('environment_blueprint',{**p,'amends_blueprint_id':'environment_blueprint-8dbf5d805122',
            'amendment_reason':'Provider schema constrains source_ids to exact pinned object identities and evidence_ids to supplied/retrieved messages. Previous malformed references remain archived.'},result['id'])
        lab.store.job(job,'completed',{'stage':'source_gating_amendment','result_id':result['id']})
        print(json.dumps({'id':result['id'],'construction':p['construction_status'],'eligibility':p['experiment_eligibility'],
            'missing':p['missing_capabilities'],'errors':p.get('errors',[]),'usage':lab.store.usage()},indent=2),flush=True)
    except Exception as error:
        lab.store.job(job,'failed',{'stage':'source_gating_amendment','error':str(error)});raise

if __name__=='__main__':main()
