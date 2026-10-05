"""Presentation-only origin labels; never upgrade evidence or resolve to latest."""
import re
from .store import Store

SOURCE_KINDS = {'dataset', 'observability_run', 'discovery', 'observation_brief', 'behavior'}
# Explicit provenance slots only. Never interpret references embedded in raw
# message contents, trajectories, model output or arbitrary nested metadata.
REF_FIELDS = ('dataset_ref', 'run_ref', 'source_ref', 'source_brief_ref', 'brief_ref',
              'behavior_ref', 'discovery_ref', 'selected_audit_ref', 'temporal_audit_ref',
              'actor_audit_ref', 'wait_audit_ref', 'hodge_audit_ref', 'plan_ref',
              'simulator_ref', 'protocol_ref', 'result_ref', 'experiment_ref',
              'parent_ref', 'previous_ref')


def _typed_ref(value):
    if not isinstance(value, dict) or set(value) != {'id', 'version', 'hash'}:
        return None
    if type(value['id']) is not str or not re.fullmatch(r'[A-Za-z0-9_.-]{1,200}', value['id']) or type(value['version']) is not int or not 1 <= value['version'] <= 10**9 or type(value['hash']) is not str or not re.fullmatch(r'[a-f0-9]{64}', value['hash']):
        return None
    return {key: value[key] for key in ('id', 'version', 'hash')}


def _authored(payload):
    declared_source = payload.get('source')
    if isinstance(declared_source, dict) and declared_source.get('kind') == 'authored_example':
        return True
    source = declared_source.replace('\\', '/').lower() if type(declared_source) is str else ''
    provenance = payload.get('provenance')
    origin = str(provenance.get('origin') or '') if isinstance(provenance, dict) else ''
    return (origin in {'authored_example', 'authored_test_fixture', 'synthetic'}
            or '/fixtures/' in source or '/examples/' in source
            or 'coordination_fixture' in source or source.startswith('synthetic'))


def _refs(payload):
    found = []; seen = set()
    def add(value):
        ref = _typed_ref(value)
        if ref is None or len(found) >= 64:
            return
        key = (ref['id'], ref['version'], ref['hash'])
        if key not in seen:
            seen.add(key); found.append(ref)
    # Prefer declared exact dataset origins, then the remaining typed slots.
    add(payload.get('dataset_ref'))
    declared = payload.get('source_refs')
    if isinstance(declared, dict):
        add(declared.get('dataset')); add(declared.get('dataset_ref'))
        for _, value in zip(range(64), declared.values()):
            add(value)
    elif isinstance(declared, list):
        for value in declared[:64]:
            add(value)
    for field in REF_FIELDS:
        add(payload.get(field))
    return found


def classify_record(connection, record, *, depth=0, seen=frozenset(), memo=None):
    # One catalog can have many references to the same large source. Decode
    # and classify a source once per read transaction, never recursively fan
    # out again for every referencing artifact.
    if memo is None:
        memo = {}
    key = (record['id'], record['version'], record['hash'])
    if key in memo:
        return dict(memo[key])
    if depth > 5 or key in seen:
        return {'source_class': 'unknown_origin', 'fixture': False}
    result = _classify_record(connection, record, depth=depth, seen=seen, memo=memo)
    # Unknowns from a cycle/depth-limited traversal are context dependent;
    # avoid publishing them as a later root traversal's resolved origin.
    if result['source_class'] != 'unknown_origin':
        memo[key] = result
    return dict(result)


def _classify_record(connection, record, *, depth, seen, memo):
    """Exact source references take precedence over subject/execution mode.

    Legacy unversioned dataset IDs never become an exact historical pin. We
    may exclude an explicitly named fixture, or an ID whose *every* stored
    version is authored, without substituting a latest empirical version.
    """
    key = (record['id'], record['version'], record['hash'])
    if depth > 5 or key in seen:
        return {'source_class': 'unknown_origin', 'fixture': False}
    p = record['payload']; kind = record['kind']
    if _authored(p):
        return {'source_class': 'software_fixture', 'fixture': True}
    mode = str(p.get('agent_mode') or p.get('subject_mode') or '')
    if kind.endswith('experiment') and (mode.startswith('offline') or mode == 'scripted'):
        return {'source_class': 'software_fixture', 'fixture': True}
    if kind == 'dataset':
        if isinstance(p.get('provenance'), dict) and p['provenance'].get('origin') == 'observability_events':
            return {'source_class': 'recorded_telemetry', 'fixture': False}
        return {'source_class': 'imported_logs', 'fixture': False}
    if kind == 'observability_run':
        return {'source_class': 'recorded_telemetry', 'fixture': False}
    refs = _refs(p); origins = []
    for ref in refs:
        source_key = (ref['id'], ref['version'], ref['hash'])
        if source_key in memo:
            origins.append(dict(memo[source_key]))
            continue
        header_key = ('source_header', *source_key)
        if header_key not in memo:
            header = connection.execute('SELECT kind,hash FROM objects WHERE id=? AND version=?', (ref['id'], ref['version'])).fetchone()
            memo[header_key] = header is not None and header['hash'] == ref['hash'] and header['kind'] in SOURCE_KINDS
        if memo[header_key] is not True:
            continue
        row = connection.execute('SELECT * FROM objects WHERE id=? AND version=?', (ref['id'], ref['version'])).fetchone()
        if row is None: continue
        # Store._decode already performs the immutable payload hash check.
        obj = Store._decode(row)
        if obj['hash'] != ref['hash']:
            continue
        if obj['kind'] in SOURCE_KINDS:
            origins.append(classify_record(connection, obj, depth=depth + 1, seen=seen | {key}, memo=memo))
    if origins:
        classes = {o['source_class'] for o in origins}
        if all(o['fixture'] for o in origins):
            return {'source_class': 'software_fixture', 'fixture': True}
        if len(classes) == 1:
            return {'source_class': next(iter(classes)), 'fixture': False}
        return {'source_class': 'mixed_or_uncertain_sources', 'fixture': False}
    identity = p.get('dataset_id')
    if type(identity) is str:
        if 'fixture' in identity.lower():
            return {'source_class': 'declared_fixture', 'fixture': True}
        legacy_key = ('legacy_dataset_id', identity)
        if legacy_key not in memo:
            rows = connection.execute('SELECT * FROM objects WHERE id=? AND kind=? ORDER BY version', (identity, 'dataset')).fetchall()
            if rows:
                # The first non-authored version is sufficient to disprove
                # the all-authored exclusion. No version is selected as pin.
                authored = all(_authored(Store._decode(row)['payload']) for row in rows)
                memo[legacy_key] = {'source_class': 'software_fixture' if authored else 'unversioned_log_source', 'fixture': authored}
            else:
                memo[legacy_key] = None
        if memo[legacy_key] is not None:
            return dict(memo[legacy_key])
    if kind != 'behavior' and (mode.startswith('offline') or mode == 'scripted'):
        return {'source_class': 'software_fixture', 'fixture': True}
    return {'source_class': 'unknown_origin', 'fixture': False}
