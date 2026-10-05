"""Save and reproduce all fixed parent graph cells without provider calls."""
import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO_ROOT))
from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab


def ref(obj):
    return {key:obj[key] for key in ('id','version','hash')}


def job_identifier(value):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}',value):
        raise argparse.ArgumentTypeError('Use a bounded durable job identifier')
    return value


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--temporal-audit-id',default='temporal_path_audit-1c08eba1b540')
    parser.add_argument('--version',type=int,default=1)
    parser.add_argument('--job-id',type=job_identifier,required=True)
    args=parser.parse_args(argv)
    lab=Lab(Settings(root=REPO_ROOT))
    request={'action':'audit_edge_flow','temporal_audit_id':args.temporal_audit_id,
             'version':args.version,'model_calls':0}
    lab.store.start_job(args.job_id,request);retained={}
    try:
        audit=lab.audit_edge_flow(args.temporal_audit_id,version=args.version)
        retained['audit_ref']=ref(audit)
        lab.store.job(args.job_id,'running',{**request,**retained})
        proof=lab.replay_edge_flow(audit['id'],version=audit['version'])
        retained.update(verification_ref=ref(proof),passed=proof['payload']['passed'])
        lab.store.job(args.job_id,'completed' if retained['passed'] else 'failed',{**request,**retained})
        cells=[]
        for cell in audit['payload']['cells']:
            d=cell['decomposition'] or {}
            energies=d.get('energies') or {}
            topology=d.get('topology') or {}
            cells.append({'window_id':cell['window_id'],'variant':cell['variant'],
                'available':d.get('available',False),'reference_events':cell['source_reference_event_count'],
                'gradient_dimension':topology.get('gradient_dimension_exact'),
                'circulation_dimension':topology.get('circulation_dimension_exact'),
                'signal_squared_norm':energies.get('signal',{}).get('squared_norm'),
                'circulation_energy_fraction':energies.get('circulation',{}).get('fraction_of_signal')})
        print(json.dumps({'refs':retained,'status':audit['payload']['status'],
            'bounds':audit['payload']['bounds'],'cells':cells,'model_calls':0,
            'scope':audit['payload']['scope']},indent=2),flush=True)
        return 0 if retained['passed'] else 1
    except Exception as exc:
        lab.store.job(args.job_id,'failed',{**request,**retained,'error_type':type(exc).__name__})
        raise


if __name__=='__main__':raise SystemExit(main())
