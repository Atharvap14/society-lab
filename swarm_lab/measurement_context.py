"""Bounded excerpts of registered measurement audits for prospective research.

These packets authenticate stored identities, not the semantics of reference
edges. Full independent numerical replay remains a separate host operation.
"""
import copy
import json


def reference_matches(ref, obj):
    return (isinstance(ref, dict) and type(ref.get('version')) is int
            and ref['version'] > 0 and isinstance(ref.get('id'), str)
            and isinstance(ref.get('hash'), str)
            and all(ref.get(key) == obj[key] for key in ('id', 'version', 'hash')))


def temporal_excerpt(payload, comparison):
    """Expose two original windows, four instruments and at most four witnesses."""
    windows = {}
    witnesses = []
    omitted = 0
    for window_id in dict.fromkeys((comparison['window_id'], comparison['comparison_window_id'])):
        row = payload['windows'][window_id]
        variants = {}
        for name, variant in row['variants'].items():
            if not variant.get('available'):
                variants[name] = {'available': False}
                continue
            variants[name] = {
                'available': True, 'node_ids': variant['node_ids'],
                'event_count': variant['event_count'],
                'static_pairs': variant['static']['reachable_pair_count'],
                'strict_temporal_pairs': variant['strict_temporal']['reachable_pair_count'],
                'static_only_pair_count': variant['static_only_pair_count'],
                'static_maximum_node_removal_loss': variant['static']['node_removal']['maximum_loss_fraction'],
                'strict_temporal_maximum_node_removal_loss': variant['strict_temporal']['node_removal']['maximum_loss_fraction']}
            pairs = variant.get('static_only_pairs', [])
            for pair in pairs:
                witness = variant['witnesses'][pair['witness_ref']]
                if len(witnesses) >= 4 or len(witness['steps']) > 4:
                    omitted += 1
                    continue
                witnesses.append({'window_id': window_id, 'instrument': name,
                    'path_ref': pair['witness_ref'], 'operator': 'static_only',
                    'strict_timestamp_order': witness['strict_timestamp_order'],
                    'steps': [{key: copy.deepcopy(step.get(key)) for key in (
                        'message_id', 'source_agent_id', 'target_agent_id', 'timestamp',
                        'room_id', 'normalized_record_hash', 'original_text_sha256', 'span')}
                        for step in witness['steps']]})
        windows[window_id] = {'scope': {key: row['scope'][key] for key in (
            'id', 'room_id', 'start', 'end_exclusive')}, 'variants': variants}
    result = {'registered_comparison': copy.deepcopy(comparison), 'windows': windows,
        'static_only_witness_excerpts': witnesses, 'omitted_static_only_witnesses': omitted,
        'bounds': 'Two original windows; at most four static-only paths of four steps; 16000 UTF-8 characters.',
        'source_replay_verdict_recorded': payload.get('source_audit_replay_passed'),
        'interpretation': ('Reference direction is author to matched name; delivery, reading and influence remain unknown. '
            'Per-window node universe differs from legacy native and pair-common universes. '
            'Path-order diagnostics do not re-estimate concentration or reciprocity, change selection or promote a candidate.')}
    while witnesses and len(json.dumps(result, ensure_ascii=False)) > 16000:
        witnesses.pop()
        result['omitted_static_only_witnesses'] += 1
    if len(json.dumps(result, ensure_ascii=False)) > 16000:
        raise ValueError('Temporal research excerpt exceeds the declared bound')
    return result
