"""Save and reproduce the fixed retrospective literal wait/action instrument."""
import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab
from swarm_lab.wait_marker_workflow import audit_wait_markers, replay_wait_markers


def bounded_integer(ceiling):
    def convert(value):
        result = int(value)
        if not 1 <= result <= ceiling:
            raise argparse.ArgumentTypeError(f'Use an integer from 1 through {ceiling}')
        return result
    return convert


def job_identifier(value):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', value):
        raise argparse.ArgumentTypeError('Use a bounded durable job identifier')
    return value


def ref(obj):
    return {key: obj[key] for key in ('id', 'version', 'hash')}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--actor-audit-id', default='actor_event_audit-29756e356310')
    parser.add_argument('--version', type=bounded_integer(2**31-1), default=1)
    parser.add_argument('--max-controls', type=bounded_integer(64), default=32)
    parser.add_argument('--max-work', type=bounded_integer(2_000_000), default=1_000_000)
    parser.add_argument('--job-id', type=job_identifier, required=True)
    args = parser.parse_args(argv)
    lab = Lab(Settings(root=REPO_ROOT))
    request = {'action': 'audit_wait_markers', 'actor_audit_id': args.actor_audit_id,
               'version': args.version, 'max_controls': args.max_controls,
               'max_work': args.max_work, 'model_calls': 0}
    lab.store.start_job(args.job_id, request)
    retained = {}
    try:
        audit = audit_wait_markers(lab, args.actor_audit_id, version=args.version,
                                  max_controls=args.max_controls, max_work=args.max_work)
        retained['alignment_ref'] = ref(audit)
        lab.store.job(args.job_id, 'running', {**request, **retained})
        proof = replay_wait_markers(lab, audit['id'], version=audit['version'])
        retained.update(verification_ref=ref(proof), passed=proof['payload']['passed'])
        lab.store.job(args.job_id, 'completed' if retained['passed'] else 'failed', {**request, **retained})
        alignment = audit['payload']['alignment']
        print(json.dumps({'refs': retained, 'status': alignment['status'],
            'message_scope': alignment['message_scope'], 'summary': alignment['summary'],
            'bounds': alignment['bounds'], 'model_calls': 0,
            'scope': audit['payload']['scope']}, indent=2), flush=True)
        return 0 if retained['passed'] else 1
    except Exception as exc:
        lab.store.job(args.job_id, 'failed', {**request, **retained, 'error_type': type(exc).__name__})
        raise


if __name__ == '__main__':
    raise SystemExit(main())
