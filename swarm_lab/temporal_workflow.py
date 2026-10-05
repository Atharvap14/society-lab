"""Pinned temporal derivation of already selected mention-graph windows.

The source audit is independently reproduced before its windows or instrument
configuration are used. No variant discovery, rematching or library promotion
occurs here. Temporal paths describe recorded reference opportunities.
"""
from .store import fingerprint


def _reference(obj):
    return {key: obj[key] for key in ('id', 'version', 'hash')}


def _load_pinned(lab, ref, kind):
    if (not isinstance(ref, dict) or not isinstance(ref.get('id'), str)
            or type(ref.get('version')) is not int or ref['version'] < 1
            or not isinstance(ref.get('hash'), str)):
        raise ValueError('Use an exact positive-version source reference')
    obj = lab.store.get(ref['id'], ref['version'])
    if (obj['kind'] != kind or obj['hash'] != ref['hash']
            or fingerprint(obj['payload']) != ref['hash']):
        raise ValueError(f'Pinned {kind} source mismatch')
    return obj


def selected_audit_sources(lab, selected_audit_id, *, version=None):
    """Authenticate registry pins and replay the original selected audit."""
    from .selected_lead_sensitivity import audit_selected_lead_name_sensitivity
    if version is not None and (type(version) is not int or version < 1):
        raise ValueError('Use a positive selected-audit version')
    audit = lab.store.get(selected_audit_id, version)
    if (audit['kind'] != 'selected_lead_audit'
            or fingerprint(audit['payload']) != audit['hash']):
        raise ValueError('Use an unchanged selected-lead measurement audit')
    p = audit['payload']
    refs = p.get('source_refs', {})
    dataset = _load_pinned(lab, refs.get('dataset'), 'dataset')
    discovery = _load_pinned(lab, refs.get('discovery'), 'discovery')
    d = discovery['payload']
    if (d.get('dataset_id') != dataset['id']
            or d.get('dataset_ref') != _reference(dataset)):
        raise ValueError('Discovery and selected audit refer to different datasets')
    config = p.get('configuration', {})
    original = audit_selected_lead_name_sensitivity(
        dataset['payload']['messages'], dataset['payload']['agents'],
        d.get('graph_search'),
        selected_lead_ids=p.get('frozen_selection', {}).get('requested_lead_ids'),
        short_name_allowlist=config.get('short_name_allowlist'),
        include_unicode_shadow=config.get('include_unicode_shadow'),
        source_refs=refs)
    saved_core = {key: p.get(key) for key in original}
    if fingerprint(original) != fingerprint(saved_core):
        raise ValueError('Selected audit does not reproduce from its pinned sources')
    return audit, dataset, discovery


def derive_temporal_paths(lab, selected_audit_id, *, version=None):
    """Read-only recomputation; the caller decides whether to persist it."""
    from .temporal_network import analyze_temporal_mentions
    audit, dataset, discovery = selected_audit_sources(
        lab, selected_audit_id, version=version)
    p = audit['payload']
    windows = [
        {key: row['original_window'][key]
         for key in ('id', 'room_id', 'start', 'end_exclusive')}
        for _, row in sorted(p['window_measurements'].items())]
    refs = {'selected_audit': _reference(audit),
            'dataset': _reference(dataset), 'discovery': _reference(discovery)}
    result = analyze_temporal_mentions(
        dataset['payload']['messages'], dataset['payload']['agents'],
        windows=windows,
        short_name_allowlist=p['configuration']['short_name_allowlist'],
        include_unicode_shadow=p['configuration']['include_unicode_shadow'],
        source_refs=refs)
    result.update(
        dataset_id=dataset['id'], dataset_ref=_reference(dataset),
        discovery_ref=_reference(discovery), selected_audit_ref=_reference(audit),
        source_audit_replay_passed=True, paid_calls=0,
        original_comparisons=[
            {key: row['registered'][key]
             for key in ('id', 'feature', 'window_id', 'comparison_window_id')}
            for row in p['per_lead']],
        graph_update_policy='Separate temporal reference-path derivation; no discovery, rematching or library status changes.')
    return result


def audit_temporal_paths(lab, selected_audit_id, *, version=None):
    result = derive_temporal_paths(lab, selected_audit_id, version=version)
    return lab.store.put('temporal_path_audit', result)


def replay_temporal_paths(lab, audit_id, *, version=None):
    if version is not None and (type(version) is not int or version < 1):
        raise ValueError('Use a positive temporal-audit version')
    saved = lab.store.get(audit_id, version)
    if saved['kind'] != 'temporal_path_audit' or fingerprint(saved['payload']) != saved['hash']:
        raise ValueError('Use an unchanged temporal path audit')
    ref = saved['payload'].get('selected_audit_ref')
    _load_pinned(lab, ref, 'selected_lead_audit')
    recomputed = derive_temporal_paths(lab, ref['id'], version=ref['version'])
    return lab.store.put('verification', {
        'audit_ref': _reference(saved), 'result_kind': 'temporal_path_audit',
        'passed': fingerprint(recomputed) == saved['hash'], 'model_calls': 0,
        'scope': 'Pinned source extraction and temporal representation; no delivery or causal attestation.'})
