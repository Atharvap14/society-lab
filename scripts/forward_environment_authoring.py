"""Forward authoring checks, including a valid construction refusal."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from swarm_lab.pipeline import Lab

def main():
    lab=Lab()
    cases=[('live-authoring-resource-gating-01',{'behavior_id':'behavior-ad77419c8fab',
        'research_question':'Which world can test task-specific versus whole-agent deferral when another agent occupies a shared computer?',
        'required_capabilities':['exclusive_shared_computer','recipient_scoped_messages']}),
        ('live-authoring-complementarity-01',{'research_question':'Construct an exploratory analogue for sharing private complementary information with canonical provenance. Conditional sharing is a possible hypothesis, not an established mechanism; declare if the existing generator cannot isolate it.',
            'required_capabilities':['private_complementary_residues','neighbor_multicast','canonical_provenance']})]
    for job,args in cases:
        if lab.store.job_exists(job):raise ValueError('Forward check already launched; inspect existing records')
        lab.store.start_job(job,{'stage':'agentic_environment_authoring','trusted_requirements':args['required_capabilities']})
        try:
            result=lab.construct_environment(**args,live=True,job_id=job)
            p=result['payload'];lab.store.job(job,'completed',{'stage':'agentic_environment_authoring','result_id':result['id']})
            print(json.dumps({'blueprint_id':result['id'],'status':p['construction_status'],
                'eligibility':p['experiment_eligibility'],'missing_capabilities':p['missing_capabilities'],
                'errors':p.get('errors',[]),'usage':lab.store.usage()},indent=2),flush=True)
        except Exception as error:
            lab.store.job(job,'failed',{'stage':'agentic_environment_authoring','error':str(error)});raise

if __name__=='__main__':main()
