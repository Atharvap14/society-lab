"""Archive a schema defect and re-review unchanged saved proposals."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from swarm_lab.pipeline import Lab

REASON=('Citation-schema aliasing constrained explanatory list fields to evidence IDs. '
        'The schema constructor now copies properties independently. Re-review the same '
        'proposal against the same source versions; prior output remains archived.')

def main():
    lab=Lab();job='live-graph-schema-repair-01';outputs=[]
    if lab.store.job_exists(job):raise ValueError('Repair already launched; inspect saved artifacts')
    lab.store.start_job(job,{'stage':'schema_defect_review_repair','reason':REASON})
    try:
        for old_id in ('research_attempt-8e608e7d0d47','research_attempt-6eab712656b1'):
            old=lab.store.get(old_id);p=old['payload'];behavior_id=p['behavior_id']
            behavior=lab.store.get(behavior_id);b=behavior['payload']
            lab.store.put('behavior',{**b,'research_quality_status':'schema_defect_requires_re_review',
                'quality_limitation':REASON},behavior_id)
            amendment=lab.store.put('research_attempt',{**{k:v for k,v in p.items() if k not in ('behavior_id','research','error','resume_job_id')},
                'status':'proposal_completed_pending_skeptic','amends_research_attempt':old_id,
                'supersedes_behavior_id':behavior_id,'amendment_reason':REASON})
            corrected=lab.resume_investigation(amendment['id'],live=True,job_id=job)
            outputs.append(corrected['id'])
            cb=corrected['payload']
            lab.store.put('behavior',{**cb,'research_quality_status':'corrected_schema_review',
                'supersedes_review_behavior_id':behavior_id,'review_amendment_reason':REASON},corrected['id'])
            lab.store.put('behavior',{**lab.store.get(behavior_id)['payload'],'research_quality_status':'superseded_schema_defect_review',
                'corrected_review_behavior_id':corrected['id']},behavior_id)
            print(json.dumps({'corrected_behavior_id':corrected['id'],'supersedes':behavior_id,'status':cb['status'],
                'skeptic_summary':cb['skeptic']['summary']}),flush=True)
        lab.store.job(job,'completed',{'stage':'schema_defect_review_repair','result_ids':outputs,'reason':REASON})
    except Exception as error:
        lab.store.job(job,'failed',{'stage':'schema_defect_review_repair','result_ids':outputs,'error':str(error),'reason':REASON})
        raise

if __name__=='__main__':main()
