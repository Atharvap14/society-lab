"""Reproduce frozen sources and run a conditional temporal reference baseline."""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab


def ref(obj):
    return {key: obj[key] for key in ('id', 'version', 'hash')}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--temporal-audit-id', default='temporal_path_audit-1c08eba1b540')
    parser.add_argument('--version', type=int, default=1)
    parser.add_argument('--seed', type=int, default=4411)
    parser.add_argument('--resamples', type=int, default=64)
    parser.add_argument('--max-work', type=int, default=10000000)
    parser.add_argument('--job-id', required=True)
    args = parser.parse_args(argv)
    lab = Lab(Settings(root=REPO_ROOT))
    lab.store.start_job(args.job_id, {'action': 'temporal_reference', 'model_calls': 0,
        'temporal_audit_id': args.temporal_audit_id, 'temporal_audit_version': args.version,
        'seed': args.seed, 'resamples': args.resamples, 'max_work': args.max_work})
    retained = {}
    try:
        result = lab.audit_temporal_reference(args.temporal_audit_id, version=args.version,
            seed=args.seed, resamples=args.resamples, max_work=args.max_work)
        retained['reference_ref'] = ref(result)
        lab.store.job(args.job_id, 'running', {'action': 'temporal_reference', **retained, 'model_calls': 0})
        proof = lab.replay_temporal_reference(result['id'], version=result['version'])
        retained.update(verification_ref=ref(proof), passed=proof['payload']['passed'])
        lab.store.job(args.job_id, 'completed' if retained['passed'] else 'failed',
                      {'action': 'temporal_reference', **retained, 'model_calls': 0})
        reference = result['payload']['timestamp_reference']
        print(json.dumps({'refs': retained, 'status': reference['status'], 'bounds': reference['bounds'],
            'cells': [{'window_id': wid, 'variant': variant, 'status': cell['status'],
                       'original': None if cell['observed'] is None else {
                           key: cell['observed'][key] for key in ('reachable_pair_count', 'maximum_loss_fraction')},
                       'reference_metrics': None if cell['reference'] is None else cell['reference']['metrics']}
                      for wid, window in reference['windows'].items()
                      for variant, cell in window['variants'].items()],
            'scope': 'Conditional timestamp reference envelopes and rank counts; '
                     'not p-values, significance, causal effects, independent replication or delivery.'}, indent=2), flush=True)
        return 0 if retained['passed'] else 1
    except Exception as exc:
        lab.store.job(args.job_id, 'failed', {'action': 'temporal_reference', **retained,
                                            'error_type': type(exc).__name__, 'model_calls': 0})
        raise


if __name__ == '__main__':raise SystemExit(main())
