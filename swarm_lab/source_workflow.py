"""Bounded source lineage with independent filesystem reread verification.

Raw rows exist only in the local scanner/join invocation. The registry retains
source coordinates, hashes, typed field diagnostics, and the exact scan plan.
Replaying a saved audit rereads that plan; stored packet claims alone do not
attest original file bytes, global coverage, receipt, or causal influence.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .store import clean, fingerprint


WORKFLOW_VERSION = 'bounded-source-link-workflow-v1'
TABLES = ('events', 'chat_messages', 'computer_use_sessions', 'computer_use_turns')
IMPLEMENTATIONS = ('source_scanner.py', 'source_links.py', 'source_workflow.py')
MAX_PLAN_BYTES = 256 * 1024
MAX_INPUT_BYTES = 32 * 1024**2
_UUID = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z')
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_MD5 = re.compile(r'[0-9a-f]{32}\Z')


def implementation_hashes():
    return {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in IMPLEMENTATIONS}


def _json_digest_size(value):
    encoder = json.JSONEncoder(sort_keys=True, ensure_ascii=False,
                               separators=(',', ':'), allow_nan=False)
    size, digest = 0, hashlib.sha256()
    for fragment in encoder.iterencode(value):
        raw = fragment.encode('utf-8')
        size += len(raw)
        digest.update(raw)
    return digest.hexdigest(), size


def _metadata(value):
    if value is None:
        return None
    allowed = {'source_uri', 'object_bytes', 'server_md5', 'generation',
               'manifest_sha256', 'supplied_hf_revision'}
    if type(value) is not dict or not set(value) <= allowed:
        raise ValueError('Source metadata uses only declared object/provenance fields')
    for key, entry in value.items():
        if entry is None:
            continue
        if key == 'object_bytes':
            valid = type(entry) is int and 0 <= entry <= 2**63 - 1
        else:
            valid = type(entry) is str and 0 < len(entry) <= 4096
            if valid and key == 'source_uri':
                valid = re.fullmatch(r'gs://[a-z0-9][a-z0-9._-]{1,221}/[^\s?#\x00]+', entry) is not None
            elif valid and key == 'server_md5':
                valid = _MD5.fullmatch(entry) is not None
            elif valid and key == 'manifest_sha256':
                valid = _SHA.fullmatch(entry) is not None
            elif valid and key == 'supplied_hf_revision':
                valid = re.fullmatch(r'[0-9a-f]{40}', entry) is not None
            elif valid and key == 'generation':
                valid = entry.isascii() and entry.isdecimal()
        if not valid:
            raise ValueError('Invalid typed source metadata declaration')
    return dict(value)


def normalize_source_plan(sources, *, expected_rows=None, rules_version='source-links-v1'):
    """Validate every scan before reading any source, including aggregate caps."""
    from .source_scanner import MAX_ROWS, MAX_COMPRESSED_BYTES, MAX_EXPANDED_BYTES, MAX_ROW_BYTES, resolve_source_path
    if type(sources) is not dict or not sources or not set(sources) <= set(TABLES):
        raise ValueError('Use exact supported source table namespaces')
    if rules_version != 'source-links-v1':
        raise ValueError('Unknown source-link rules version')
    allowed = {'path', 'max_rows', 'max_compressed_bytes', 'max_expanded_bytes',
               'max_row_bytes', 'select_ids', 'stop_when_all_ids_found', 'source_metadata'}
    bounds = {'max_rows': (64, MAX_ROWS), 'max_compressed_bytes': (2 * 1024**2, MAX_COMPRESSED_BYTES),
              'max_expanded_bytes': (8 * 1024**2, MAX_EXPANDED_BYTES),
              'max_row_bytes': (1024**2, MAX_ROW_BYTES)}
    result = {}
    for table in TABLES:
        if table not in sources:
            continue
        source = sources[table]
        if type(source) is not dict or not set(source) <= allowed or 'path' not in source:
            raise ValueError('Source entries require a path and only supported scan options')
        if not isinstance(source['path'], (str, Path)):
            raise ValueError('Source paths must be ordinary filesystem paths')
        path, _ = resolve_source_path(source['path'])
        if (not path.is_file() or not path.name.lower().endswith(('.jsonl', '.jsonl.gz'))
                or len(str(path).encode('utf-8')) > 4096):
            raise ValueError('Source paths must be existing bounded JSONL files')
        row = {'path': str(path)}
        for key, (default, ceiling) in bounds.items():
            value = source.get(key, default)
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError(f'{key} requires a positive bounded integer')
            row[key] = value
        ids = source.get('select_ids')
        if ids is not None:
            if (type(ids) is not list or len(ids) > MAX_ROWS
                    or any(type(i) is not str or not _UUID.fullmatch(i) for i in ids)):
                raise ValueError('Source-link filters require bounded exact UUID lists')
            if len(ids) != len(set(ids)):
                raise ValueError('Duplicate requested IDs are ambiguous in a replay plan')
            ids = sorted(ids)
        stop = source.get('stop_when_all_ids_found', False)
        if type(stop) is not bool or stop and not ids:
            raise ValueError('Explicit ID early stopping requires nonempty exact filters')
        row.update(select_ids=ids, stop_when_all_ids_found=stop,
                   source_metadata=_metadata(source.get('source_metadata')))
        result[table] = row
    if sum(row['max_compressed_bytes'] for row in result.values()) > 128 * 1024**2:
        raise ValueError('Aggregate logical compressed scan budget exceeds 128 MiB')
    if sum(row['max_expanded_bytes'] for row in result.values()) > 256 * 1024**2:
        raise ValueError('Aggregate expanded scan budget exceeds 256 MiB')
    expected_rows = [] if expected_rows is None else expected_rows
    if type(expected_rows) is not list or len(expected_rows) > MAX_ROWS:
        raise ValueError('Expected source pins must be a bounded list')
    expected, seen = [], set()
    for pin in expected_rows:
        required = {'table', 'id', 'record_sha256'}
        if (type(pin) is not dict or not required <= set(pin)
                or not set(pin) <= required | {'line', 'raw_line_sha256'}
                or type(pin['table']) is not str or pin['table'] not in result
                or type(pin['id']) is not str or not _UUID.fullmatch(pin['id'])
                or type(pin['record_sha256']) is not str or not _SHA.fullmatch(pin['record_sha256'])):
            raise ValueError('Expected rows require exact table, UUID and canonical SHA256')
        if 'line' in pin and (type(pin['line']) is not int
                              or not 1 <= pin['line'] <= result[pin['table']]['max_rows']):
            raise ValueError('Expected source line must fall inside the declared scan bound')
        if 'raw_line_sha256' in pin and (type(pin['raw_line_sha256']) is not str
                                        or not _SHA.fullmatch(pin['raw_line_sha256'])):
            raise ValueError('Expected raw-line hashes require exact SHA256')
        key = (pin['table'], pin['id'])
        if key in seen:
            raise ValueError('Duplicate expected row pins')
        seen.add(key)
        expected.append(dict(pin))
    plan = {'workflow_version': WORKFLOW_VERSION, 'rules_version': rules_version,
            'sources': result, 'expected_rows': sorted(expected, key=lambda p: (p['table'], p['id']))}
    if _json_digest_size(plan)[1] > MAX_PLAN_BYTES:
        raise ValueError('Source scan plan exceeds 256 KiB')
    if clean(plan) != plan:
        raise ValueError('Do not persist credential-shaped source paths or metadata')
    return plan


def derive_source_links(plan):
    """Reread bounded sources; return only lineage diagnostics and byte pins."""
    from .source_scanner import scan_jsonl_source
    from .source_links import triangulate_source_links
    if (type(plan) is not dict or set(plan) != {'workflow_version', 'rules_version', 'sources', 'expected_rows'}
            or plan['workflow_version'] != WORKFLOW_VERSION):
        raise ValueError('Use the exact supported source scan plan')
    normalized = normalize_source_plan(plan['sources'], expected_rows=plan['expected_rows'],
                                       rules_version=plan['rules_version'])
    if normalized != plan:
        raise ValueError('Saved source scan plan is not in canonical form')
    packets, readset = {}, {}
    aggregate_bytes, retained_rows = 0, 0
    for table, source in normalized['sources'].items():
        packet = scan_jsonl_source(table=table, **source)
        packet_hash, packet_bytes = _json_digest_size(packet)
        aggregate_bytes += packet_bytes
        retained_rows += len(packet['records'])
        if aggregate_bytes > MAX_INPUT_BYTES or retained_rows > 15000:
            raise ValueError('Retained source packets exceed aggregate join bounds')
        packets[table] = packet
        readset[table] = {key: value for key, value in packet.items() if key != 'records'}
        readset[table].update(packet_sha256=packet_hash, packet_canonical_bytes=packet_bytes)
    for pin in normalized['expected_rows']:
        matches = [row for row in packets[pin['table']]['records'] if row['record']['id'] == pin['id']]
        if len(matches) != 1:
            raise ValueError('Expected source record is unresolved or ambiguous within bounded scan')
        source = matches[0]['source']
        if any(source[key] != pin[key] for key in ('record_sha256', 'line', 'raw_line_sha256') if key in pin):
            raise ValueError('Expected source row pin does not match actual filesystem bytes')
    audit = triangulate_source_links(packets, rules_version=normalized['rules_version'])
    return {'name': 'Bounded explicit source lineage', 'workflow_version': WORKFLOW_VERSION,
            'plan': normalized, 'plan_hash': fingerprint(normalized),
            'implementation_hashes': implementation_hashes(), 'source_readset': readset,
            'source_link_audit': audit, 'expected_row_pins_checked': len(normalized['expected_rows']),
            'model_calls': 0, 'raw_records_persisted': False,
            'scope': 'Filesystem bytes actually read and explicit exported lineage in retained rows. '
                     'A repeatable prefix is not authenticated whole-object coverage, delivery or influence.'}


def scan_source_links(lab, sources, *, expected_rows=None, rules_version='source-links-v1'):
    plan = normalize_source_plan(sources, expected_rows=expected_rows, rules_version=rules_version)
    return lab.store.put('source_link_audit', derive_source_links(plan))


def replay_source_links(lab, audit_id, *, version=None):
    if version is not None and (type(version) is not int or version < 1):
        raise ValueError('Use an exact positive source-audit version')
    saved = lab.store.get(audit_id, version)
    if saved['kind'] != 'source_link_audit' or fingerprint(saved['payload']) != saved['hash']:
        raise ValueError('Use an unchanged source-link audit')
    payload = saved['payload']
    verdict = {'audit_ref': {key: saved[key] for key in ('id', 'version', 'hash')},
               'result_kind': 'source_link_audit', 'model_calls': 0,
               'passed': False, 'filesystem_reread_attempted': False, 'filesystem_reread_completed': False,
               'scope': 'Fresh bounded filesystem scan, source row/line/prefix pins and explicit link recomputation; '
                        'no recipient exposure, historical path or causal attestation.'}
    if payload.get('implementation_hashes') != implementation_hashes():
        verdict['reason'] = 'implementation_hash_mismatch'
    elif fingerprint(payload.get('plan')) != payload.get('plan_hash'):
        verdict['reason'] = 'scan_plan_hash_mismatch'
    else:
        verdict['filesystem_reread_attempted'] = True
        try:
            derived = derive_source_links(payload['plan'])
        except (ValueError, OSError, TypeError, KeyError, UnicodeError) as exc:
            verdict.update(reason='filesystem_reread_unavailable_or_invalid', error_type=type(exc).__name__)
        else:
            verdict.update(filesystem_reread_completed=True,
                           passed=fingerprint(derived) == saved['hash'],
                           reason='reproduced' if fingerprint(derived) == saved['hash'] else 'source_or_derivation_mismatch')
    return lab.store.put('verification', verdict)
