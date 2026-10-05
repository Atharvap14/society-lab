"""Persist and freshly replay a pinned selected-author actor/time observation.

Reuses the existing authenticated index; never builds an index or scans raw
mounted events. This script writes research/job records, with zero model calls.
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from swarm_lab.actor_event_workflow import audit_selected_actor_events, replay_actor_events
from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab


def ref(obj):
    return {key: obj[key] for key in ('id', 'version', 'hash')}


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError('Use a positive integer')
    return number


def row_bound(value):
    number = positive(value)
    if number > 15000:
        raise argparse.ArgumentTypeError('Row bounds must not exceed 15000')
    return number


def job_identifier(value):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', value):
        raise argparse.ArgumentTypeError('Use a bounded durable job identifier')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index-id', default='event_source_index-71b617501d7e')
    parser.add_argument('--index-version', type=positive, default=1)
    parser.add_argument('--selected-audit-id', default='selected_lead_audit-cdb8875d4e64')
    parser.add_argument('--selected-audit-version', type=positive, default=1)
    parser.add_argument('--max-rows', type=row_bound, default=15000)
    parser.add_argument('--max-candidate-rows', type=row_bound, default=15000)
    parser.add_argument('--job-id', type=job_identifier, required=True)
    args = parser.parse_args(argv)
    lab = Lab(Settings(root=REPO_ROOT))
    request = {'action': 'audit_selected_actor_events', 'index_id': args.index_id,
        'index_version': args.index_version, 'selected_audit_id': args.selected_audit_id,
        'selected_audit_version': args.selected_audit_version,
        'max_rows': args.max_rows, 'max_candidate_rows': args.max_candidate_rows,
        'model_calls': 0}
    # An existing job refuses launch without overwriting its earlier state.
    lab.store.start_job(args.job_id, request)
    retained = {}
    try:
        audit = audit_selected_actor_events(lab, args.index_id, args.selected_audit_id,
            index_version=args.index_version, selected_audit_version=args.selected_audit_version,
            max_rows=args.max_rows, max_candidate_rows=args.max_candidate_rows)
        retained['audit_ref'] = ref(audit)
        lab.store.job(args.job_id, 'running', {**request, **retained})
        proof = replay_actor_events(lab, audit['id'], version=audit['version'])
        retained.update(verification_ref=ref(proof), passed=proof['payload']['passed'])
        lab.store.job(args.job_id, 'completed' if retained['passed'] else 'failed', {**request, **retained})
        payload = audit['payload']
        print(json.dumps({'refs': retained, 'source_scope': payload['source_scope'],
            'coverage': {key: payload['actor_event_packet']['coverage'][key] for key in
                ('candidate_rows', 'candidate_rows_validated', 'matched_rows', 'returned_rows', 'query_complete', 'truncated')},
            'summary_total': payload['actor_event_summary']['total'],
            'model_calls': 0,
            'scope': 'Pinned source-author selection and fresh local-index replay. Missing rooms remain unassigned; no raw event reread, lease, receipt or causal attestation.'}, indent=2), flush=True)
        return 0 if retained['passed'] else 1
    except Exception as exc:
        lab.store.job(args.job_id, 'failed', {**request, **retained,
                                            'error_type': type(exc).__name__})
        raise


if __name__ == '__main__':
    raise SystemExit(main())
