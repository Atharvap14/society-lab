"""Bounded registered live pilot; retain negative outcomes and failures."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from swarm_lab.pipeline import Lab

def main():
    lab=Lab();job='live-complementary-wind-tunnel-01'
    if lab.store.job_exists(job):raise ValueError('This pilot job has already been launched; inspect its record')
    if lab.store.usage()['calls']+96>lab.settings.max_calls:raise ValueError('Insufficient cap for the frozen worst-case pilot')
    lab.store.start_job(job,{'stage':'registration_before_live_execution'})
    protocol=lab.design_complementary(trials_per_cell=2,seed=4411,max_rounds=3,live=True)
    print(json.dumps({'registered_protocol_id':protocol['id'],'maximum_calls':96,'usage_before':lab.store.usage()}),flush=True)
    result=lab.experiment_complementary(protocol['id'],live=True,job_id=job)
    verification=lab.audit(result['id'])
    print(json.dumps({'result_id':result['id'],'verification_id':verification['id'],'replay_passed':verification['payload']['passed'],
        'cells':result['payload']['analysis']['cells'],'effects':result['payload']['analysis']['factor_effects'],
        'usage_after':lab.store.usage()},indent=2),flush=True)

if __name__=='__main__':main()
