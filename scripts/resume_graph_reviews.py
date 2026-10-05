"""Resume stored skeptical reviews without regenerating discovery proposals."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from swarm_lab.pipeline import Lab

def main():
    lab=Lab();job='live-graph-skeptic-resume-03';outputs=[]
    attempts=('research_attempt-8e608e7d0d47','research_attempt-6eab712656b1')
    lab.store.job(job,'running',{'stage':'sequential_skeptic_resumption','attempt_ids':attempts})
    try:
        for identity in attempts:
            obj=lab.resume_investigation(identity,live=True,job_id=job)
            outputs.append(obj['id'])
            print(json.dumps({'behavior_id':obj['id'],'status':obj['payload']['status'],
                'name':obj['payload']['name'],'fit':obj['payload']['experiment_fit']}),flush=True)
        lab.store.job(job,'completed',{'stage':'sequential_skeptic_resumption','result_ids':outputs})
    except Exception as error:
        lab.store.job(job,'failed',{'stage':'sequential_skeptic_resumption','result_ids':outputs,'error':str(error)})
        raise

if __name__=='__main__':main()
