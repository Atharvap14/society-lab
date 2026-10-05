"""Index bounded event fields and corroborate the existing frozen selection.

No raw content/provider output is printed or retained in the index. Reuse a
saved index with --index-id; this avoids repeatedly scanning the mounted source.
The subsequent replay authenticates local projection bytes, not fresh GCS bytes.
"""
import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab
from swarm_lab.store import now


def ref(obj):
    return {key: obj[key] for key in ('id', 'version', 'hash')}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('V:/events.jsonl.gz'))
    parser.add_argument('--selected-audit-id', default='selected_lead_audit-cdb8875d4e64')
    parser.add_argument('--selected-audit-version', type=int, default=1)
    parser.add_argument('--index-id')
    parser.add_argument('--index-version', type=int, default=1)
    parser.add_argument('--job-id', required=True)
    args = parser.parse_args(argv)
    lab = Lab(Settings(root=REPO_ROOT))
    lab.store.start_job(args.job_id, {'action': 'index_selected_events', 'started': now(),
                                    'selected_audit_id': args.selected_audit_id,
                                    'selected_audit_version': args.selected_audit_version,
                                    'index_id': args.index_id, 'model_calls': 0})
    retained = {}
    last = [0.0]
    def progress(packet):
        if time.monotonic() - last[0] >= 15:
            last[0] = time.monotonic()
            # Allowlist numerical/status summaries even if a future callback
            # grows fields. No raw event values enter output or the registry.
            safe = {key: value for key, value in packet.items()
                    if key in {'physical_rows_seen', 'indexed_rows', 'compressed_bytes_read',
                               'expanded_bytes_read', 'elapsed_seconds', 'complete_scan', 'state', 'stop_reason'}
                    and (type(value) in (int, float, bool) or
                         type(value) is str and value in {'running', 'complete', 'partial'})}
            print(json.dumps({'event_index_progress': safe}), flush=True)
    try:
        if args.index_id:
            index = lab.store.get(args.index_id, args.index_version)
        else:
            index = lab.build_event_source_index(args.source, on_progress=progress,
                source_metadata={
                    'source_uri': 'gs://kairosity-ai-village-504821/ai-village/events.jsonl.gz',
                    'object_bytes': 328621853, 'server_md5': '07d4e8f54e4ae8ab2a8df41fafa6ecaf',
                    'generation': None,
                    'manifest_sha256': '28383809e34d38f00037dd31d830fa9b826b59fd91c0460e03efcbed6ee9e332',
                    'supplied_hf_revision': '838b4150303ca8228e8edb432d8b8ccae353d258'})
        retained['index_ref'] = ref(index)
        print(json.dumps({'event_index_saved': ref(index),
                          'coverage': index['payload']['build_metadata'].get('coverage'),
                          'declaration_comparison': index['payload']['build_metadata'].get('declaration_comparison')}),
              flush=True)
        lab.store.job(args.job_id, 'running', {'action': 'index_selected_events', **retained,
                                             'model_calls': 0})
        audit = lab.audit_indexed_events(index['id'], args.selected_audit_id,
                                         index_version=index['version'],
                                         selected_audit_version=args.selected_audit_version)
        retained['audit_ref'] = ref(audit)
        proof = lab.replay_indexed_events(audit['id'], version=audit['version'])
        retained['verification_ref'] = ref(proof)
        retained['passed'] = proof['payload']['passed']
        lab.store.job(args.job_id, 'completed' if retained['passed'] else 'failed',
                      {'action': 'index_selected_events', **retained, 'model_calls': 0})
        print(json.dumps({'selected_event_audit': retained,
                          'audit_summary': audit['payload']['indexed_event_audit'].get('counts'),
                          'model_calls': 0,
                          'scope': 'Typed local projection matches in original selected windows. '
                                   'No receipt, exposure, outcome or causal attestation.'}), flush=True)
        return 0 if retained['passed'] else 1
    except Exception as exc:
        lab.store.job(args.job_id, 'failed', {'action': 'index_selected_events', **retained,
                                             'error_type': type(exc).__name__, 'model_calls': 0})
        raise


if __name__ == '__main__':raise SystemExit(main())
