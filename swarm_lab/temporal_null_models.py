"""Conditional message-time permutation references, never inferential p-values.

Consumes frozen reference events. No extraction, source reads, database writes,
models, delivery claims, synthetic source witnesses, or candidate promotion.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import temporal_network as temporal
from .mention_graph_sensitivity import VARIANT_LABELS


REFERENCE_VERSION = 'message-time-permutation-v1'
MAX_WINDOWS = 24
MAX_NODES = 128
MAX_EVENTS = 10000
MAX_RESAMPLES = 256
MAX_WORK = 10_000_000
MAX_INPUT_BYTES = 16_000_000
MAX_OUTPUT_BYTES = 16_000_000
EVENT_KEYS = {'event_id', 'message_id', 'source_agent_id', 'target_agent_id', 'timestamp',
    'room_id', 'source', 'normalized_record_hash', 'original_text_sha256', 'instrument',
    'measurement_status', 'span', 'original_span_available', 'match_text'}
TOP_KEYS = {'schema_version', 'analysis_version', 'kind', 'read_only', 'model_calls', 'source_refs',
    'source_binding', 'code_hashes', 'name_instrument_version', 'configuration', 'scope', 'bounds',
    'definitions', 'limitations', 'windows', 'dataset_id', 'dataset_ref', 'discovery_ref',
    'selected_audit_ref', 'source_audit_replay_passed', 'paid_calls', 'original_comparisons', 'graph_update_policy'}
FORBIDDEN = {'content', 'shadow_text', 'provider_output', 'agent_messages', 'command',
    'password', 'token', 'api_key', 'output', 'error', 'system', 'messages', 'input', 'raw_payload'}
SOURCE_KEYS = {'file', 'path', 'line', 'table', 'raw_line_sha256', 'record_sha256'}
INSTRUMENTS = {'exact_display_name': 'recorded_name_match',
    'explicit_short_name_exact': 'explicit_short_name_match_candidate',
    'unicode_shadow': 'formatting_match_candidate',
    'explicit_short_name_unicode_shadow': 'explicit_short_name_match_candidate'}
VARIANT_INSTRUMENTS = {'baseline_exact': {'exact_display_name'},
    'explicit_short_expanded_exact': {'exact_display_name', 'explicit_short_name_exact'},
    'unicode_baseline': {'unicode_shadow'},
    'unicode_expanded': {'unicode_shadow', 'explicit_short_name_unicode_shadow'}}
REF_PREFIXES = {'temporal_audit': 'temporal_path_audit-', 'selected_audit': 'selected_lead_audit-',
                'dataset': 'dataset-', 'discovery': 'discovery-'}
METRICS = ('reachable_pair_count', 'maximum_loss_fraction')


def _hash(value):
    return temporal._digest(value)


def _bounded(value, *, context, byte_limit, items=600000, depth=24, strings=4096):
    temporal._validate_json(value, context=context, max_items=items, max_depth=depth, max_string=strings)
    temporal._json_size(value, limit=byte_limit, context=context)


def _private_guard(value):
    pending = [value]
    while pending:
        item = pending.pop()
        if type(item) is dict:
            if set(item) & FORBIDDEN:
                raise ValueError('Raw payload fields are unsupported by the temporal reference instrument')
            pending.extend(item.values())
        elif type(item) is list:
            pending.extend(item)


def _identity(value):
    return type(value) is str and 0 < len(value.encode('utf-8')) <= 256


def _sha(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _utc(value):
    if type(value) is not str or not 20 <= len(value) <= 40 or 'T' not in value:
        raise ValueError('Missing or invalid temporal reference timestamp; no imputation')
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0:
            raise ValueError('UTC timestamp required')
        result = stamp.astimezone(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')
    except (ValueError, OverflowError) as exc:
        raise ValueError('Missing or invalid temporal reference timestamp; no imputation') from exc
    return result


def _refs(value):
    if value in (None, []):
        return {}
    if type(value) is not dict or not set(value) <= set(REF_PREFIXES):
        raise ValueError('Use only typed temporal_audit/selected_audit/dataset/discovery references')
    result = {}
    for key, ref in value.items():
        if (type(ref) is not dict or set(ref) != {'id', 'version', 'hash'} or
            not _identity(ref['id']) or not ref['id'].startswith(REF_PREFIXES[key]) or
            type(ref['version']) is not int or not 1 <= ref['version'] <= 2**31 - 1 or not _sha(ref['hash'])):
            raise ValueError('Registry references require exact identity/positive version/SHA256')
        result[key] = dict(ref)
    return result


def _choices(values, available, name, cap):
    if values is None:
        return sorted(available)
    if type(values) is not list or not 1 <= len(values) <= cap or any(type(v) is not str or v not in available for v in values) or len(values) != len(set(values)):
        raise ValueError(name + ' must be unique known bounded identifiers')
    return sorted(values)


def _static_pairs(nodes, events):
    index = {node: i for i, node in enumerate(nodes)}
    rows = [1 << i for i in range(len(nodes))]
    for event in events:
        rows[index[event['source_agent_id']]] |= 1 << index[event['target_agent_id']]
    for k in range(len(nodes)):
        for i in range(len(nodes)):
            if rows[i] & (1 << k):
                rows[i] |= rows[k]
    return {(nodes[i], nodes[j]) for i, mask in enumerate(rows)
            for j in range(len(nodes)) if i != j and mask & (1 << j)}


def _temporal_pairs(nodes, groups, assignments, removed=None):
    """Count-only batched reachability; no synthetic path witness is created."""
    index = {node: i for i, node in enumerate(nodes)}
    reached = [0 if node == removed else 1 << i for i, node in enumerate(nodes)]
    batches = defaultdict(list)
    for message_id, group in groups.items():
        batches[assignments[message_id]].extend(group['edges'])
    for timestamp in sorted(batches):
        additions = [0] * len(nodes)
        for source, target in batches[timestamp]:
            if source == removed or target == removed:
                continue
            origin_bit, target_bit = 1 << index[source], 1 << index[target]
            for i in range(len(nodes)):
                if reached[i] & origin_bit:
                    additions[i] |= target_bit
        reached = [old | new for old, new in zip(reached, additions)]
    return {(nodes[i], nodes[j]) for i, mask in enumerate(reached)
            for j in range(len(nodes)) if i != j and mask & (1 << j)}


def _measure(nodes, groups, assignments):
    pairs = _temporal_pairs(nodes, groups, assignments)
    removal = []
    for node in nodes:
        eligible = {pair for pair in pairs if node not in pair}
        remaining = _temporal_pairs(nodes, groups, assignments, removed=node)
        lost = eligible - remaining
        removal.append({'agent_id': node, 'eligible_reachable_pairs': len(eligible),
            'lost_pairs': len(lost), 'loss_fraction': len(lost) / len(eligible) if eligible else None})
    valid = [row['loss_fraction'] for row in removal if row['loss_fraction'] is not None]
    return {'reachable_pair_count': len(pairs), 'maximum_loss_fraction': max(valid) if valid else None,
            'node_removal': removal}, pairs


def _static_signature(nodes, groups):
    pairs, authored, targets = Counter(), Counter(), Counter()
    for group in groups.values():
        authored[group['source_agent_id']] += 1
        for source, target in group['edges']:
            pairs[(source, target)] += 1; targets[target] += 1
    edges = [{'source_agent_id': a, 'target_agent_id': b, 'weight': count}
             for (a, b), count in sorted(pairs.items())]
    outgoing, indegree, outdegree = Counter(), Counter(), Counter()
    for (source, target), count in pairs.items():
        outgoing[source] += count; indegree[target] += 1; outdegree[source] += 1
    return {'node_ids': list(nodes), 'directed_weighted_edges': edges,
            'edge_count': len(pairs), 'event_count': sum(pairs.values()),
            'edge_bearing_messages_by_source': dict(sorted(authored.items())),
            'incoming_event_counts': {node: targets[node] for node in nodes},
            'outgoing_event_counts': {node: outgoing[node] for node in nodes},
            'in_degrees': {node: indegree[node] for node in nodes},
            'out_degrees': {node: outdegree[node] for node in nodes}}


def _prepare(audit, window_ids, variants):
    if (type(audit) is not dict or not set(audit) <= TOP_KEYS or audit.get('schema_version') != '1.0' or
        audit.get('analysis_version') != temporal.TEMPORAL_NETWORK_VERSION or audit.get('kind') != 'temporal_reference_paths' or
        audit.get('read_only') is not True or type(audit.get('model_calls')) is not int or audit.get('model_calls') != 0):
        raise ValueError('Use a frozen strict-temporal reference-path packet')
    _bounded(audit, context='Frozen temporal packet', byte_limit=MAX_INPUT_BYTES)
    _private_guard(audit)
    windows = audit.get('windows')
    if type(windows) is not dict or not 0 <= len(windows) <= MAX_WINDOWS:
        raise ValueError('Frozen temporal scopes exceed the window bound')
    selected = _choices(window_ids, windows, 'window_ids', MAX_WINDOWS)
    selected_variants = _choices(variants, VARIANT_LABELS, 'variants', len(VARIANT_LABELS))
    prepared = []
    for wid in selected:
        window = windows[wid]
        if type(window) is not dict:
            raise ValueError('Malformed frozen window')
        scope = window.get('scope', {})
        if not _identity(wid) or type(scope) is not dict or scope.get('id') != wid or not _identity(scope.get('room_id')):
            raise ValueError('Malformed frozen window identity/scope')
        start, end = _utc(scope.get('start')), _utc(scope.get('end_exclusive'))
        if start >= end:
            raise ValueError('Window must be a positive half-open UTC scope')
        universe, extraction, variant_map = window.get('node_universe'), window.get('extraction_review'), window.get('variants')
        if type(universe) is not dict or type(extraction) is not dict or type(variant_map) is not dict:
            raise ValueError('Malformed fixed-node/extraction/variant metadata')
        nodes = universe.get('ids')
        if type(nodes) is not list or len(nodes) > MAX_NODES or any(not _identity(node) for node in nodes) or len(nodes) != len(set(nodes)) or nodes != sorted(nodes):
            raise ValueError('Use the original sorted fixed node universe, at most 128 nodes')
        messages = window.get('message_ids')
        evidence = extraction.get('evidence_index')
        authors = universe.get('agent_author_ids')
        if (type(messages) is not list or any(not _identity(mid) for mid in messages) or len(messages) != len(set(messages)) or
            type(evidence) is not dict or set(messages) != set(evidence) or type(authors) is not list or not set(authors) <= set(nodes)):
            raise ValueError('Frozen scope/evidence/author membership mismatch')
        for variant in selected_variants:
            value = variant_map.get(variant)
            if type(value) is not dict or type(value.get('available')) is not bool or value.get('node_ids') != nodes:
                raise ValueError('Missing variant or changed fixed node universe')
            item = {'window_id': wid, 'variant': variant, 'scope': {'id': wid, 'room_id': scope['room_id'], 'start': start, 'end_exclusive': end},
                'nodes': list(nodes), 'source_fingerprint': window.get('source_fingerprint'), 'available': value['available'],
                'registered': value, 'groups': {}, 'events': [], 'pins': []}
            if not value['available']:
                if value.get('events') not in (None, []):
                    raise ValueError('Unavailable variant cannot carry extracted events')
                item['unavailable_reason'] = value.get('reason', 'Frozen instrument unavailable')
                prepared.append(item); continue
            events = value.get('events')
            if type(events) is not list or len(events) > MAX_EVENTS or type(value.get('event_count')) is not int or value['event_count'] != len(events):
                raise ValueError('Frozen event count/bound mismatch')
            ids, message_targets = set(), set()
            if any(type(event) is not dict or set(event) != EVENT_KEYS or
                   any(not _identity(event.get(k)) for k in ('message_id', 'target_agent_id', 'event_id')) for event in events):
                raise ValueError('Use exact typed frozen reference events')
            for event in sorted(events, key=lambda e: (e['message_id'], e['target_agent_id'], e['event_id'])):
                if type(event) is not dict or set(event) != EVENT_KEYS:
                    raise ValueError('Use exact frozen reference events, without raw payload fields')
                for key in ('event_id', 'message_id', 'source_agent_id', 'target_agent_id'):
                    if not _identity(event[key]):
                        raise ValueError('Invalid event/source identity')
                mid, source, target = event['message_id'], event['source_agent_id'], event['target_agent_id']
                stamp = _utc(event['timestamp'])
                if event['event_id'] in ids or (mid, target) in message_targets:
                    raise ValueError('Duplicate source event or message-target pair')
                ids.add(event['event_id']); message_targets.add((mid, target))
                if source == target or source not in authors or target not in nodes or event['room_id'] != scope['room_id'] or not start <= stamp < end or mid not in evidence:
                    raise ValueError('Event violates frozen author/target/room/window membership')
                binding = evidence[mid]
                if (type(binding) is not dict or binding.get('message_id') != mid or binding.get('agent_id') != source or binding.get('speaker_type') != 'agent' or
                    binding.get('room_id') != event['room_id'] or _utc(binding.get('timestamp')) != stamp or
                    binding.get('computed_normalized_record_hash') != event['normalized_record_hash'] or
                    binding.get('original_content_sha256') != event['original_text_sha256'] or binding.get('source') != event['source']):
                    raise ValueError('Event differs from frozen source evidence binding')
                if (not _sha(event['normalized_record_hash']) or not _sha(event['original_text_sha256']) or
                    type(event['instrument']) is not str or event['instrument'] not in VARIANT_INSTRUMENTS[variant] or
                    INSTRUMENTS.get(event['instrument']) != event['measurement_status'] or
                    type(event['original_span_available']) is not bool or not _identity(event['match_text'])):
                    raise ValueError('Invalid frozen hash/instrument/status')
                if event['original_span_available'] != (event['instrument'] in ('exact_display_name', 'explicit_short_name_exact')):
                    raise ValueError('Frozen match coordinate policy differs from instrument')
                provenance = event['source']
                if type(provenance) is not dict or not set(provenance) <= SOURCE_KEYS:
                    raise ValueError('Only typed file/path/table/line/hash source coordinates are supported')
                for key, val in provenance.items():
                    if key == 'line':
                        if type(val) is not int or val < 1:
                            raise ValueError('Invalid original source line')
                    elif key.endswith('sha256'):
                        if not _sha(val):
                            raise ValueError('Invalid original source hash')
                    elif type(val) is not str or not 0 < len(val.encode('utf-8')) <= 4096:
                        raise ValueError('Invalid original source coordinate')
                group = item['groups'].setdefault(mid, {'source_agent_id': source, 'original_timestamp': stamp, 'edges': []})
                if group['source_agent_id'] != source or group['original_timestamp'] != stamp:
                    raise ValueError('One message must have one author and one original timestamp')
                group['edges'].append((source, target))
                item['events'].append({'source_agent_id': source, 'target_agent_id': target})
                item['pins'].append({'event_id': event['event_id'], 'message_id': mid, 'source_agent_id': source,
                    'target_agent_id': target, 'original_timestamp': stamp, 'room_id': event['room_id'],
                    'instrument': event['instrument'], 'measurement_status': event['measurement_status'],
                    'normalized_record_hash': event['normalized_record_hash'], 'original_text_sha256': event['original_text_sha256'],
                    'original_event_sha256': _hash(event), 'source': copy.deepcopy(provenance),
                    'pin_scope': 'Original frozen event only; never a synthetic-time source witness.'})
            item['groups'] = dict(sorted(item['groups'].items()))
            item['static_signature'] = _static_signature(nodes, item['groups'])
            item['input_fingerprint'] = _hash({'scope': item['scope'], 'nodes': nodes, 'original_event_pins': item['pins']})
            prepared.append(item)
    return prepared, selected, selected_variants


def _envelope(values):
    if not values:
        return None
    ordered = sorted(values)
    def quantile(q):
        position = (len(ordered) - 1) * q
        lo = int(position); hi = math.ceil(position)
        return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)
    return {'minimum': ordered[0], 'q25': quantile(.25), 'median': statistics.median(ordered),
            'q75': quantile(.75), 'maximum': ordered[-1], 'mean': statistics.fmean(ordered),
            'interpretation': 'Empirical conditional reference distribution; not a confidence interval.'}


def _assignment_hash(item, assignment):
    return _hash({'version': REFERENCE_VERSION, 'window_id': item['window_id'], 'variant': item['variant'],
                  'message_time_assignments': sorted(assignment.items())})


def timestamp_permutation_reference(temporal_audit, *, window_ids=None, variants=None,
    seed=4411, resamples=64, max_work=MAX_WORK, source_refs=None):
    """Reference-only envelopes from edge-bearing message timestamp permutations.

    Over-budget requests return unknown without any partial samples or ranks.
    Invalid/missing timestamps and inconsistent original metrics fail closed.
    """
    if type(seed) is not int or not 0 <= seed <= 2**63 - 1:
        raise ValueError('seed requires a nonboolean nonnegative signed-64-bit integer')
    if type(resamples) is not int or not 1 <= resamples <= MAX_RESAMPLES:
        raise ValueError('resamples requires a nonboolean integer from 1 to 256')
    if type(max_work) is not int or not 1 <= max_work <= MAX_WORK:
        raise ValueError('max_work requires a positive nonboolean integer at most ten million')
    prepared, selected, selected_variants = _prepare(temporal_audit, window_ids, variants)
    refs = _refs(temporal_audit.get('source_refs') if source_refs is None else source_refs)
    source_binding = temporal_audit.get('source_binding')
    binding_keys = {'declared_refs_external_authentication', 'raw_rows_fingerprint',
                    'source_context_fingerprint', 'roster_fingerprint', 'hash_policy'}
    if type(source_binding) is not dict or set(source_binding) != binding_keys or source_binding['declared_refs_external_authentication'] is not False or any(not _sha(source_binding[k]) for k in ('raw_rows_fingerprint', 'source_context_fingerprint', 'roster_fingerprint')):
        raise ValueError('Invalid frozen source hash bindings')
    operator_pins = temporal_audit.get('code_hashes')
    if type(operator_pins) is not dict or set(operator_pins) != set(temporal._code_hashes()) or any(type(v) is not dict or not _sha(v.get('sha256')) for v in operator_pins.values()):
        raise ValueError('Invalid frozen operator implementation hash pins')
    work = sum(4 * (resamples + 1) * (len(i['nodes']) * (len(i['nodes']) + 1) *
                (len(i['events']) + len(i['nodes'])) + len(i['events']) + len(i['groups']) + 1)
               for i in prepared if i['available'])
    exceeded = work > max_work
    result = {'kind': 'temporal_timestamp_reference', 'schema_version': '1.0',
        'instrument_version': REFERENCE_VERSION, 'read_only': True, 'model_calls': 0,
        'status': 'not_computed_work_budget' if exceeded else 'complete_reference',
        'runtime': {'python_version': '.'.join(map(str, sys.version_info[:3])),
                    'rng_backend': 'stdlib random.Random.shuffle', 'numpy_required': False},
        'source_refs': refs, 'source_refs_authenticated': False,
        'source_audit_binding': {k: source_binding[k] for k in binding_keys if k != 'hash_policy'} | {
            'hash_policy': 'Original frozen compact finite UTF-8 JSON hash declarations; external refs remain separately typed and unauthenticated here.'},
        'input_projection_fingerprint': _hash([i.get('input_fingerprint', [i['window_id'], i['variant'], 'unavailable']) for i in prepared]),
        'configuration': {'seed': seed, 'resamples_requested': resamples,
            'window_ids': selected, 'variants': selected_variants, 'conditioning': 'Distinct edge-bearing source messages within each exact frozen room/window/variant.',
            'permutation_unit': 'All accepted target edges from a source message share its assigned time.',
            'no_edge_messages': 'Excluded from this conditional timestamp multiset; this is not a permutation of every authored or human message slot.'},
        'bounds': {'max_windows': MAX_WINDOWS, 'max_nodes': MAX_NODES, 'max_events_per_cell': MAX_EVENTS,
            'max_resamples': MAX_RESAMPLES, 'max_work': max_work, 'estimated_work': work,
            'formula': 'Sum available cells: 4*(R+1)*(n*(n+1)*(E+n)+E+edge_bearing_messages+1); includes observed replay and all fixed-node removals.',
            'max_input_bytes': MAX_INPUT_BYTES, 'max_output_bytes': MAX_OUTPUT_BYTES},
        'implementation_hashes': {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ('temporal_null_models.py', 'temporal_network.py', 'mention_graph_sensitivity.py')},
        'source_operator_hashes': {name: {'sha256': pin['sha256'], 'purpose': 'Binary source-operator identity retained from the frozen audit, not fresh source attestation.'} for name, pin in operator_pins.items()},
        'windows': {},
        'limitations': ['Conditional exploratory reference, not p-values, significance, causal identification, novelty or a status promotion.',
            'Message-time exchangeability is unestablished; roles, scheduling, bursts, common instructions and tasks can explain differences.',
            'Same selected windows are reused; there is no held-out replication or correction for original selection.',
            'Message-time multiset/ties are preserved, but edge-time multiplicities can change when message target batch sizes differ.',
            'Reference direction remains author to named agent, not observed delivery, reading or prior information flow.',
            'Representation node deletion is not intervention. Eligible-pair denominators and maximizing nodes may vary across synthetic assignments.',
            'Each cell uses a separately seeded stream; variants/windows are not paired null experiments or independent scientific replications.',
            'Synthetic assignments are fingerprinted only; original source timestamps/pins remain unchanged and no synthetic source witnesses are emitted.',
            'Coactivity, fixed-node inclusion and unmeasured authors do not establish membership or time at risk.',
            'Registry references/source pins are declarations here; the host must authenticate the frozen audit and its upstream source replay.']}
    for item in prepared:
        wid, variant, nodes, groups = item['window_id'], item['variant'], item['nodes'], item['groups']
        out = {'available': item['available'] and not exceeded,
            'status': 'frozen_variant_unavailable' if not item['available'] else 'not_computed_work_budget' if exceeded else 'complete_reference',
            'fixed_node_ids': list(nodes), 'input_fingerprint': item.get('input_fingerprint'),
            'original_event_pins': item['pins'], 'original_event_count': len(item['events']) if item['available'] else None,
            'message_groups': [{'message_id': mid, 'source_agent_id': g['source_agent_id'],
                'original_timestamp': g['original_timestamp'], 'target_edge_count': len(g['edges'])} for mid, g in groups.items()],
            'observed_replay': {'passed': None}, 'observed': None, 'static_invariants': item.get('static_signature'),
            'reference': None, 'degeneracy': None}
        result['windows'].setdefault(wid, {'scope': item['scope'], 'variants': {}})['variants'][variant] = out
        if not item['available'] or exceeded:
            out['reason'] = item.get('unavailable_reason', 'Aggregate work bound exceeded; no observed replay, samples, envelopes or rank counts computed.')
            continue
        original = {mid: g['original_timestamp'] for mid, g in groups.items()}
        observed, original_pairs = _measure(nodes, groups, original)
        static_pairs = _static_pairs(nodes, item['events'])
        registered = item['registered']
        registered_metrics = [registered['static']['reachable_pair_count'], registered['strict_temporal']['reachable_pair_count'], registered['strict_temporal']['node_removal']['maximum_loss_fraction']]
        if not original_pairs <= static_pairs or _hash([len(static_pairs), observed['reachable_pair_count'], observed['maximum_loss_fraction']]) != _hash(registered_metrics):
            raise ValueError('Original frozen temporal/static metric replay mismatch')
        registered_rows = [{key: row[key] for key in ('agent_id', 'eligible_reachable_pairs', 'lost_pairs', 'loss_fraction')}
                           for row in registered['strict_temporal']['node_removal']['rows']]
        if _hash(registered_rows) != _hash(observed['node_removal']):
            raise ValueError('Original endpoint-excluded deletion replay mismatch')
        out['observed_replay'] = {'passed': True, 'scope': 'Frozen reference events and original fixed-node metric definitions; not fresh source or delivery validation.'}
        out['observed'] = observed
        out['static_invariants'] = {**item['static_signature'], 'static_reachable_pair_count': len(static_pairs),
            'signature_sha256': _hash(item['static_signature']), 'asserted_each_draw': True,
            'operator_policy': 'Static edges/weights/degrees are unchanged; no new eigenvector comparison is warranted.'}
        rng = random.Random(int(_hash([REFERENCE_VERSION, seed, wid, variant])[:16], 16))
        times = [original[mid] for mid in groups]
        original_multiset = Counter(times)
        values = {metric: [] for metric in METRICS}
        draws = []
        original_assignment_hash = _assignment_hash(item, original)
        for draw in range(resamples):
            shuffled = list(times); rng.shuffle(shuffled)
            assignment = dict(zip(groups, shuffled))
            if set(assignment) != set(groups) or Counter(assignment.values()) != original_multiset or _static_signature(nodes, groups) != item['static_signature']:
                raise ValueError('Synthetic assignment violates fixed graph/message-time invariants')
            measured, pairs = _measure(nodes, groups, assignment)
            if not pairs <= static_pairs:
                raise ValueError('Synthetic temporal pairs are not a subset of the unchanged static graph')
            digest = _assignment_hash(item, assignment)
            draws.append({'resample_index': draw, 'synthetic_assignment_sha256': digest,
                          'synthetic': True, 'same_assignment_as_observed': digest == original_assignment_hash})
            for metric in METRICS:
                values[metric].append(measured[metric])
        summaries = {}
        for metric in METRICS:
            defined = [v for v in values[metric] if v is not None]
            actual = observed[metric]
            ranks = None if actual is None else {'less_than_observed': sum(v < actual for v in defined),
                'equal_to_observed': sum(v == actual for v in defined), 'greater_than_observed': sum(v > actual for v in defined),
                'comparable_draws': len(defined)}
            summaries[metric] = {'envelope': _envelope(defined), 'rank_counts': ranks,
                'defined_draws': len(defined), 'undefined_draws': resamples - len(defined),
                'observed_defined': actual is not None, 'constant_defined_values': len(set(defined)) <= 1 if defined else None}
        distinct = len(set(times)); unique_assignments = len({d['synthetic_assignment_sha256'] for d in draws})
        out['reference'] = {'resamples_requested': resamples, 'resamples_completed': resamples,
            'metrics': summaries, 'permutation_fingerprints': draws,
            'original_assignment_sha256': original_assignment_hash,
            'rank_grid_spacing_with_observed': 1 / (resamples + 1),
            'resolution_scope': 'Nominal Monte Carlo rank grid, not an exact permutation probability or significance threshold; ties/statistic discreteness can be much coarser.',
            'message_time_multiset_sha256': _hash(sorted(original_multiset.items())),
            'message_time_multiset_preserved': True,
            'edge_time_multiset_preserved': 'Not guaranteed: entire message batches move, and target counts differ.',
            'distribution_policy': 'None denotes an undefined loss denominator; no zero substitution. Envelopes exclude undefined draws and disclose their count.'}
        out['degeneracy'] = {'edge_bearing_message_count': len(groups), 'distinct_original_message_times': distinct,
            'assignment_structurally_degenerate': len(groups) < 2 or distinct < 2,
            'unique_sampled_assignments': unique_assignments,
            'all_draws_equal_observed_assignment': all(d['same_assignment_as_observed'] for d in draws),
            'metric_constancy_does_not_prove_assignment_constancy': True,
            'empty_scope_warning': 'An empty reference graph is not observed absence of agent behavior.' if not item['events'] else None}
    _bounded(result, context='Temporal reference output', byte_limit=MAX_OUTPUT_BYTES, items=600000)
    return result
