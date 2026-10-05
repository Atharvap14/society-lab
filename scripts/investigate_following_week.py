"""Two graph-guided investigator/skeptic workflows with explicit bounded calls."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab
from swarm_lab.research_transport import ResearchResponsesHarness

class BoundedResearchLab(Lab):
    def research_harness(self,name,settings=None):
        if name=='responses':return ResearchResponsesHarness(settings or self.settings,self.store,max_rate_retries=0)
        return super().research_harness(name,settings)

def main():
    lab=BoundedResearchLab(Settings(max_tool_rounds=2,max_output_tokens=5000))
    job='following-week-parallel-graph-investigation-01'
    if lab.store.job_exists(job):raise ValueError('This investigation was already launched; preserve its partial/complete results')
    if lab.settings.max_calls-lab.store.usage()['calls']<12:raise ValueError('At least twelve remaining requests required for this bounded forward batch')
    candidates=['graph-lead-b2c7d08d1c926822','graph-lead-c7af8e6e02732836']
    lab.store.start_job(job,{'stage':'parallel_graph_investigation','discovery_id':'discovery-3d29f6c7f419',
        'candidate_ids':candidates,'max_tool_rounds':2,'max_rate_retries':0,'maximum_role_requests_without_failure':12,
        'scope':'Retrospective data-selected graph leads; no novelty, significance or causal claim'})
    try:
        outputs=lab.investigate('discovery-3d29f6c7f419',candidate_ids=candidates,count=2,live=True,job_id=job)
        lab.store.job(job,'completed',{'stage':'parallel_graph_investigation','result_ids':[o['id'] for o in outputs]})
        print(json.dumps({'behaviors':[{'id':o['id'],'name':o['payload']['name'],'status':o['payload']['status'],
            'fit':o['payload']['experiment_fit'],'skeptic':o['payload']['skeptic']['recommended_status']} for o in outputs],
            'usage':lab.store.usage()},indent=2),flush=True)
    except Exception as error:
        lab.store.job(job,'failed',{'stage':'parallel_graph_investigation','error':str(error),
            'preservation':'Research attempts and any completed behaviors remain independently archived; no automatic regeneration.'});raise

if __name__=='__main__':main()
