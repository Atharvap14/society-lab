"""Read-only, exact-version episode packets for the local research workspace.

This presentation joins recorded outputs. It never replays a source/operator,
chooses a new comparator, approves an experiment fit, or changes the library.
"""
from __future__ import annotations

import copy
import hashlib
import math
import re

from .research_observations import (
    _Reader, _bytes, _pin, _ref, _same, _utc, recorded_observation_context,
)
from .selected_lead_sensitivity import EQUALITY_TOLERANCE

VERSION = 'episode-workspace-v1'
VARIANTS = ('baseline_exact', 'explicit_short_expanded_exact',
            'unicode_baseline', 'unicode_expanded')
MAX_OUTPUT_BYTES = 64 * 1024
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,199}\Z')
_SCOPE = ('Exact original selected lead and comparator, with bounded recorded '
          'observations. Local registry/current producer/stored-proof checks '
          'are distinct from fresh source or operator verification. No reranking, '
          'new comparator, pooling, causal conclusion, environment-fit approval '
          'or status promotion. Draft transfer supplies a question only.')


def _identity(identity, version):
    if (type(identity) is not str or not _ID.fullmatch(identity) or
            type(version) is not int or not 1 <= version <= 10**9):
        raise ValueError('exact_episode_identity_required')


def _load(reader, identity, version, kind):
    _identity(identity, version)
    obj = reader.accept(reader.store.get(identity, version))
    if obj['id'] != identity or obj['version'] != version or obj['kind'] != kind:
        raise ValueError('episode_record_identity_mismatch')
    return obj


def _numeric(value, *, minimum=None, maximum=None, optional=False):
    if value is None and optional:
        return value
    if (type(value) not in (int, float) or not math.isfinite(value) or
            minimum is not None and value < minimum or maximum is not None and value > maximum):
        raise ValueError('invalid_recorded_episode_numeric')
    return value


def _project_metrics(row, feature):
    if type(row) is not dict or type(row.get('available')) is not bool or type(row.get('supported')) is not bool:
        raise ValueError('invalid_recorded_episode_metric_flags')
    if row.get('supported_under_original_minima') is not None and type(row['supported_under_original_minima']) is not bool:
        raise ValueError('invalid_recorded_episode_metric_flags')
    maximum = 1.0 + 1.1e-9 if feature in ('incoming_concentration', 'directed_reciprocity', 'bridge_dependence') else None
    if row['available']:
        left = _numeric(row.get('value'), minimum=0, maximum=maximum)
        right = _numeric(row.get('comparison_value'), minimum=0, maximum=maximum)
        delta = _numeric(row.get('difference'))
        if not math.isclose(delta, left-right, rel_tol=1e-9, abs_tol=1e-10):
            raise ValueError('inconsistent_recorded_episode_metric_delta')
        direction = 'zero' if abs(delta) <= EQUALITY_TOLERANCE else 'positive' if delta > 0 else 'negative'
        if row.get('direction') != direction:
            raise ValueError('inconsistent_recorded_episode_metric_direction')
    elif any(row.get(key) is not None for key in ('value', 'comparison_value', 'difference')):
        raise ValueError('unavailable_episode_metric_has_numeric_output')
    elif row.get('direction') != 'undefined':
        raise ValueError('inconsistent_recorded_episode_metric_direction')
    return {key: copy.deepcopy(row.get(key)) for key in
            ('available', 'value', 'comparison_value', 'difference',
             'direction', 'supported', 'supported_under_original_minima')}


def _temporal_window(window):
    nodes = window['node_universe']['ids']
    if (type(nodes) is not list or len(nodes) > 128 or len(set(nodes)) != len(nodes) or
            any(type(node) is not str or not _ID.fullmatch(node) for node in nodes)):
        raise ValueError('invalid_episode_temporal_node_universe')
    pair_limit = len(nodes) * (len(nodes)-1)
    variants = {}
    for name in VARIANTS:
        row = window['variants'][name]
        if type(row.get('available')) is not bool:
            raise ValueError('invalid_episode_temporal_availability')
        projected = {'available': row['available'], 'static': None,
                     'strict_temporal': None, 'static_only_pair_count': None}
        if row['available'] is True:
            for policy in ('static', 'strict_temporal'):
                saved = row[policy]
                count = saved['reachable_pair_count']
                if type(count) is not int or not 0 <= count <= pair_limit:
                    raise ValueError('invalid_episode_temporal_pair_count')
                _numeric(saved['node_removal']['maximum_loss_fraction'], minimum=0,
                         maximum=1.0 + 1.1e-9, optional=True)
                projected[policy] = {
                    'reachable_pair_count': saved['reachable_pair_count'],
                    'maximum_bridge_loss_fraction': saved['node_removal']['maximum_loss_fraction'],
                }
            projected['static_only_pair_count'] = row['static_only_pair_count']
            count = projected['static_only_pair_count']
            if (type(count) is not int or count < 0 or
                    count != projected['static']['reachable_pair_count'] - projected['strict_temporal']['reachable_pair_count']):
                raise ValueError('inconsistent_episode_static_only_count')
        variants[name] = projected
    return {'node_ids': copy.deepcopy(nodes),
            'variants': variants}


def _evidence(messages, identities, scope):
    if (type(identities) is not list or len(identities) > 256 or
            any(type(identity) is not str or not _ID.fullmatch(identity) for identity in identities) or
            len(set(identities)) != len(identities)):
        raise ValueError('invalid_original_episode_evidence_ids')
    output, missing = [], []
    for identity in identities:
        message = messages.get(identity)
        if message is None:
            missing.append(identity)
            continue
        if (message['room_id'] != scope['room_id'] or
                not _utc(scope['start']) <= _utc(message['timestamp']) < _utc(scope['end_exclusive'])):
            raise ValueError('original_episode_evidence_scope_mismatch')
        if len(output) >= 8:
            continue
        content = message['content']
        if type(content) is not str:
            raise ValueError('invalid_original_episode_content')
        source = message.get('source', {})
        if type(source) is not dict:
            raise ValueError('invalid_episode_evidence_provenance')
        for key, limit in (('file', 1024), ('table', 100)):
            if key in source and (type(source[key]) is not str or len(source[key]) > limit):
                raise ValueError('invalid_episode_evidence_provenance')
        if 'line' in source and (type(source['line']) is not int or not 1 <= source['line'] <= 10**12):
            raise ValueError('invalid_episode_evidence_provenance')
        output.append({key: copy.deepcopy(message.get(key)) for key in
                       ('id', 'timestamp', 'agent_name', 'agent_id', 'room_id')} | {
            'source': {key: copy.deepcopy(source[key]) for key in ('file', 'line', 'table') if key in source},
            'content': content[:1000], 'full_content_sha256': hashlib.sha256(content.encode('utf-8')).hexdigest(),
            'full_content_characters': len(content), 'content_truncated': len(content) > 1000,
        })
    return output, {'original_evidence_ids': len(identities), 'shown': len(output),
                    'missing_ids': missing, 'unshown': len(identities) - len(output) - len(missing)}


def _behavior(reader, identity, version, refs, lead_id):
    if identity is None and version is None:
        return {'available': False, 'reason': 'no_explicit_behavior_selected', 'ref': None, 'payload': None}
    if identity is None or version is None:
        raise ValueError('behavior_identity_and_version_required_together')
    obj = _load(reader, identity, version, 'behavior')
    p = obj['payload']
    matching = (p.get('candidate_id') == lead_id and
                type(p.get('source_refs')) is dict and
                all(_same(p['source_refs'][name], refs[name]) for name in ('dataset', 'discovery')))
    if not matching:
        return {'available': False, 'reason': 'behavior_exact_source_or_candidate_mismatch',
                'ref': _pin(obj), 'payload': None}
    critique = p.get('skeptic')
    if type(critique) is not dict:
        raise ValueError('invalid_episode_critique_shape')
    public_critique = {key: copy.deepcopy(critique.get(key)) for key in
                      ('summary', 'unsupported_claims', 'recommended_status')}
    if (type(public_critique['summary']) is not str or
            type(public_critique['recommended_status']) is not str or
            type(public_critique['unsupported_claims']) is not list or
            any(type(value) is not str for value in public_critique['unsupported_claims'])):
        raise ValueError('invalid_episode_public_critique_fields')
    return {'available': True, 'reason': None, 'ref': _pin(obj),
            'source_link_approval': False,
            'scope': 'Matching saved research hypothesis and critique; no semantic endorsement or new fit approval.',
            'payload': {key: copy.deepcopy(p.get(key)) for key in
                        ('name', 'status', 'summary', 'operational_definition', 'alternative_explanations',
                         'falsifiable_predictions', 'experiment_fit', 'fit_reason')} | {'skeptic': public_critique}}


def episode_workspace_packet(store, *, selected_audit_id, selected_audit_version,
                             temporal_audit_id, temporal_audit_version, lead_id,
                             behavior_id=None, behavior_version=None):
    """Load supplied exact parents; an unavailable channel is never a zero.

    Accepted JSON is bounded after Store decoding. No filesystem evidence is
    reread. Producer files are inspected by the existing recorded-context helper.
    The 8 MiB presentation reader and 16 MiB context reader have separate budgets.
    """
    result = {'workspace_version': VERSION, 'available': False, 'reason': None,
              'source_refs': None, 'comparison': None, 'windows': None, 'lead': None,
              'measurement': None, 'temporal': None, 'evidence': None, 'behavior': None,
              'recorded_observations': None, 'model_calls': 0, 'database_writes': 0,
              'fresh_source_attestation': False, 'operator_rerun': False, 'scope': _SCOPE,
              'bounds': {'max_output_bytes': MAX_OUTPUT_BYTES, 'max_evidence_per_group': 8,
                         'max_content_characters': 1000, 'accepted_presentation_registry_bytes': 8*1024**2,
                         'accepted_context_registry_bytes': 16*1024**2,
                         'store_decoding_allocations_bounded': False}}
    try:
        if type(lead_id) is not str or not _ID.fullmatch(lead_id):
            raise ValueError('exact_original_lead_required')
        reader = _Reader(store, {'max_registry_body_bytes': 4*1024**2,
                                'max_total_registry_bytes': 8*1024**2})
        selected = _load(reader, selected_audit_id, selected_audit_version, 'selected_lead_audit')
        temporal = _load(reader, temporal_audit_id, temporal_audit_version, 'temporal_path_audit')
        refs = {name: copy.deepcopy(selected['payload']['source_refs'][name])
                for name in ('dataset', 'discovery')}
        refs.update(selected_audit=_pin(selected), temporal_audit=_pin(temporal))
        for ref in refs.values():
            _ref(ref)
        entries = [row for row in selected['payload']['per_lead'] if row['lead_id'] == lead_id]
        if len(entries) != 1:
            raise ValueError('original_selected_lead_missing_or_duplicate')
        saved = entries[0]
        comparison = {key: saved['registered'][key] for key in
                      ('id', 'feature', 'window_id', 'comparison_window_id')}
        context = recorded_observation_context(store, refs, comparison)
        if not all(value is True for value in context['base_context_gates'].values()) or context['source_refs'] is None:
            raise ValueError('episode_base_context_unavailable')
        dataset = reader.load(refs['dataset'], 'dataset')['payload']
        discovery = reader.load(refs['discovery'], 'discovery')['payload']
        candidates = [row for row in discovery['candidates'] if row['id'] == lead_id]
        if len(candidates) != 1 or any(candidates[0].get(key) != value for key, value in comparison.items()):
            raise ValueError('original_discovery_candidate_mismatch')
        candidate = candidates[0]
        if any(key not in candidate or _bytes(candidate[key]) != _bytes(value)
               for key, value in saved['registered'].items()):
            raise ValueError('original_candidate_registered_core_mismatch')
        if _bytes(candidate.get('alternative_explanations')) != _bytes(saved['registered'].get('alternatives')):
            raise ValueError('original_candidate_alternative_explanations_mismatch')
        messages = {row['id']: row for row in dataset['messages']}
        if len(messages) != len(dataset['messages']):
            raise ValueError('duplicate_source_message_identity')
        focal, comparator = comparison['window_id'], comparison['comparison_window_id']
        windows = copy.deepcopy(context['original_windows'])
        evidence, evidence_limits = {}, {}
        for name, ids, wid in (('focal', candidate['evidence_ids'], focal),
                               ('comparator', candidate['comparison_evidence_ids'], comparator)):
            evidence[name], evidence_limits[name] = _evidence(messages, ids, windows[wid])
        evidence['limits'] = evidence_limits
        result.update(available=True, source_refs=refs, comparison=comparison, windows=windows,
                      lead={key: copy.deepcopy(candidate.get(key)) for key in
                            ('id', 'title', 'description', 'feature', 'value', 'comparison_value', 'difference',
                             'alternative_explanations', 'requires', 'right_censored')},
                      measurement={policy: {variant: _project_metrics(saved[policy][variant], comparison['feature']) for variant in VARIANTS}
                                   for policy in ('native', 'fixed_pair')},
                      temporal={wid: _temporal_window(temporal['payload']['windows'][wid]) for wid in windows},
                      evidence=evidence, behavior=_behavior(reader, behavior_id, behavior_version, refs, lead_id),
                      recorded_observations=context)
        result['bounds']['accepted_presentation_json_bytes'] = reader.used
        if len(_bytes(result)) > MAX_OUTPUT_BYTES:
            raise ValueError('episode_output_bound_exceeded')
    except (ValueError, KeyError, TypeError, OSError, StopIteration, OverflowError, RecursionError) as exc:
        reason = str(exc) if type(exc) is ValueError and re.fullmatch(r'[a-z_]+', str(exc)) else 'episode_source_or_contract_unavailable'
        for key in ('source_refs', 'comparison', 'windows', 'lead', 'measurement', 'temporal',
                    'evidence', 'behavior', 'recorded_observations'):
            result[key] = None
        result.update(available=False, reason=reason)
    return result


def parse_episode_query(query):
    """Strict GET query parser, including duplicate and noncanonical versions."""
    required = {'selected_audit_id', 'selected_audit_version', 'temporal_audit_id',
                'temporal_audit_version', 'lead_id'}
    optional = {'behavior_id', 'behavior_version'}
    if (type(query) is not dict or not required <= set(query) or
            not set(query) <= required | optional or
            any(type(values) is not list or len(values) != 1 or type(values[0]) is not str
                for values in query.values()) or
            bool('behavior_id' in query) != bool('behavior_version' in query)):
        raise ValueError('invalid_episode_query')
    args = {key: values[0] for key, values in query.items()}
    for key in ('selected_audit_version', 'temporal_audit_version', 'behavior_version'):
        if key in args:
            if not re.fullmatch(r'[1-9][0-9]{0,9}', args[key]) or int(args[key]) > 10**9:
                raise ValueError('canonical_exact_episode_version_required')
            args[key] = int(args[key])
    for key in ('selected_audit_id', 'temporal_audit_id', 'lead_id', 'behavior_id'):
        if key in args and not _ID.fullmatch(args[key]):
            raise ValueError('invalid_episode_query_identity')
    return args
