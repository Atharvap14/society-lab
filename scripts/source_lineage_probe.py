"""Repeat known small real-source examples; no raw/provider payload output.

This is a retrospective instrument smoke test, not held-out behavior evidence.
Each auxiliary prefix is capped at 64 physical rows. Parent lookups stop after
explicit selected IDs are found, under independent logical byte/row budgets.
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab


PINS = [
    ('events', 59, '0009366f-7730-45e9-81b7-d0a646b55a34', '3f9f4b392c0d09514c11e799097a909fdea30e0d4d1660923bc5bae9cfbd5795'),
    ('chat_messages', 1835, '02887067-c736-41fa-8425-40c9794f4c23', 'b51a301b18bbcf5995bc1091cb6ee8269bbd8c51a2c3fe3a5e205140fb0778b5'),
    ('events', 37, '0005ca38-37e3-4837-bf1a-a61d782edc0d', 'fe9c1166b46d8a9b6fd5d1ebfb11f19452bff095bb83b0163f8fcff11f945548'),
    ('computer_use_sessions', 10013, '206eada5-1654-41d4-bd73-651ce2463f92', 'ee2e88c8926267ad405ad206bf220558c48d894f8c3b7f642fc6fdc0dc65c7fb'),
    ('computer_use_turns', 51, '00015a42-7383-47cd-a20b-1db40b93a280', 'b59c1521de97600e78f68cc2b13f1ad0aa16262e4001e2dcba1c434c19971734'),
    ('computer_use_sessions', 1266, '04309ce5-2d02-42e7-a97e-3968597d3495', '4c4e8e9a829ab0dc8605882224e5ccafcbf2b6d93212c4c9a3ee6190c4be0c9e'),
    ('events', 3, '000060db-534c-435a-a592-838ed9a83c00', '054db00a5af5c58680950d5a7a9e075d1ce0915e285bbddf28758e690182c41b'),
    ('computer_use_turns', 36, '0000ea8d-6cf9-44bc-921a-dbe8a6f5adb4', 'f4495c00d95966ea93b0a8d0011917119d0a69d82b9272dccfea6f41a39cd223'),
]
OBJECTS = {
    'events': (328621853, '07d4e8f54e4ae8ab2a8df41fafa6ecaf'),
    'chat_messages': (52543996, '8c504d57f902b1156f52927d9128673c'),
    'computer_use_sessions': (40080397, 'db82fdabbda10e5ec3ac6d15832566d6'),
    'computer_use_turns': (2475319119, 'bc330055cec2e511e14e8986ca3af8a9'),
}


def probe_plan(mounted_root, chat_path):
    sources = {}
    for table, (size, md5) in OBJECTS.items():
        sources[table] = {
            'path': str(chat_path if table == 'chat_messages' else mounted_root / (table + '.jsonl.gz')),
            'max_rows': 64, 'max_compressed_bytes': 2 * 1024**2,
            'max_expanded_bytes': 8 * 1024**2, 'max_row_bytes': 1024**2,
            'source_metadata': {
                'source_uri': 'gs://kairosity-ai-village-504821/ai-village/' + table + '.jsonl.gz',
                'object_bytes': size, 'server_md5': md5, 'generation': None,
                'manifest_sha256': '28383809e34d38f00037dd31d830fa9b826b59fd91c0460e03efcbed6ee9e332',
                'supplied_hf_revision': '838b4150303ca8228e8edb432d8b8ccae353d258'},
        }
    for table in ('chat_messages', 'computer_use_sessions'):
        sources[table].update(max_rows=15000, max_compressed_bytes=8 * 1024**2,
                              max_expanded_bytes=32 * 1024**2,
                              select_ids=[identity for t, _, identity, _ in PINS if t == table],
                              stop_when_all_ids_found=True)
    return {'sources': sources,
            'expected_rows': [{'table': table, 'line': line, 'id': identity, 'record_sha256': digest}
                              for table, line, identity, digest in PINS]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mounted-root', type=Path, default=Path('V:/'))
    parser.add_argument('--chat', type=Path, default=REPO_ROOT / 'ai-village/chat_messages.jsonl.gz')
    parser.add_argument('--runtime', type=Path)
    parser.add_argument('--write-plan', type=Path)
    args = parser.parse_args(argv)
    plan = probe_plan(args.mounted_root, args.chat)
    if args.write_plan:
        args.write_plan.parent.mkdir(parents=True, exist_ok=True)
        if args.write_plan.exists():
            raise ValueError('Keep prior probe plans; choose an unused output path')
        args.write_plan.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    lab = Lab(Settings(root=REPO_ROOT))
    if args.runtime:
        from swarm_lab.store import Store
        lab.store = Store(args.runtime / 'lab.sqlite3')
    audit = lab.scan_source_links(**plan)
    proof = lab.replay_source_links(audit['id'], version=audit['version'])
    links = audit['payload']['source_link_audit']
    print(json.dumps({
        'audit_ref': {key: audit[key] for key in ('id', 'version', 'hash')},
        'verification_ref': {key: proof[key] for key in ('id', 'version', 'hash')},
        'reread_passed': proof['payload']['passed'],
        'expected_row_pins_checked': audit['payload']['expected_row_pins_checked'],
        'counts': links['counts'],
        'coverage': {table: value['coverage'] for table, value in audit['payload']['source_readset'].items()},
        'new_model_calls': 0,
        'scope': 'Known retrospective prefix examples across different dates; no prevalence estimate, '
                 'April-window corroboration, global absence, delivery, or causal claim.'}, indent=2))
    return 0 if proof['payload']['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
