"""Pinned exploratory timestamp references over frozen selected graph windows."""
import hashlib
from pathlib import Path

from .store import clean, fingerprint

WORKFLOW_VERSION = 'temporal-timestamp-reference-workflow-v1'
IMPLEMENTATIONS = ('temporal_null_models.py', 'temporal_null_workflow.py', 'temporal_network.py',
                   'temporal_workflow.py', 'selected_lead_sensitivity.py', 'dataset.py',
                   'discovery.py', 'network.py', 'graph_discovery.py', 'mention_sensitivity.py',
                   'name_eligibility_sensitivity.py', 'mention_graph_sensitivity.py')


def implementation_hashes():
    return {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in IMPLEMENTATIONS}


def _ref(obj):
    return {key: obj[key] for key in ('id', 'version', 'hash')}


def _version(value):
    if value is not None and (type(value) is not int or value < 1):
        raise ValueError('Use an exact positive temporal-source version')


def derive_temporal_reference(lab, temporal_audit_id, *, version=None, window_ids=None,
                              variants=None, seed=4411, resamples=64, max_work=10000000):
    from .temporal_workflow import _load_pinned, derive_temporal_paths
    from .temporal_null_models import timestamp_permutation_reference
    _version(version)
    source = lab.store.get(temporal_audit_id, version)
    if source['kind'] != 'temporal_path_audit' or fingerprint(source['payload']) != source['hash']:
        raise ValueError('Use an unchanged frozen temporal path audit')
    selected = _load_pinned(lab, source['payload'].get('selected_audit_ref'), 'selected_lead_audit')
    derived = derive_temporal_paths(lab, selected['id'], version=selected['version'])
    if fingerprint(derived) != source['hash']:
        raise ValueError('Original temporal audit does not reproduce from its frozen sources')
    refs = {**source['payload']['source_refs'], 'temporal_audit': _ref(source)}
    result = timestamp_permutation_reference(source['payload'], window_ids=window_ids,
        variants=variants, seed=seed, resamples=resamples, max_work=max_work, source_refs=refs)
    payload = {'name': 'Conditional temporal timestamp reference', 'workflow_version': WORKFLOW_VERSION,
               'temporal_audit_ref': _ref(source), 'source_refs': refs,
               'source_audit_replay_passed': True, 'implementation_hashes': implementation_hashes(),
               'configuration': {'window_ids': window_ids, 'variants': variants,
                                 'seed': seed, 'resamples': resamples, 'max_work': max_work},
               'timestamp_reference': result, 'model_calls': 0, 'status_promotion': False,
               'scope': 'Same selected reference events under conditional edge-bearing-message timestamp '
                        'permutations. Source extraction is reproduced; exchangeability, recipient exposure '
                        'and causal identification remain unestablished. Envelopes and ranks are descriptive.'}
    if clean(payload) != payload:
        raise ValueError('Do not persist credential-shaped temporal reference metadata')
    return payload


def audit_temporal_reference(lab, temporal_audit_id, **kwargs):
    return lab.store.put('temporal_timestamp_reference', derive_temporal_reference(lab, temporal_audit_id, **kwargs))


def replay_temporal_reference(lab, reference_id, *, version=None):
    _version(version)
    source = lab.store.get(reference_id, version)
    if source['kind'] != 'temporal_timestamp_reference' or fingerprint(source['payload']) != source['hash']:
        raise ValueError('Use an unchanged temporal timestamp reference')
    payload = source['payload']
    proof = {'reference_ref': _ref(source), 'result_kind': 'temporal_timestamp_reference',
             'passed': False, 'model_calls': 0, 'source_replay_attempted': False,
             'source_replay_completed': False,
             'scope': 'Frozen source extraction, original metric replay and deterministic conditional '
                      'reference regeneration; no exchangeability, significance, exposure or causal attestation.'}
    if payload.get('implementation_hashes') != implementation_hashes():
        proof['reason'] = 'implementation_hash_mismatch'
    else:
        proof['source_replay_attempted'] = True
        try:
            from .temporal_workflow import _load_pinned
            temporal = _load_pinned(lab, payload['temporal_audit_ref'], 'temporal_path_audit')
            derived = derive_temporal_reference(lab, temporal['id'], version=temporal['version'],
                                                **payload['configuration'])
        except (ValueError, OSError, TypeError, KeyError, UnicodeError) as exc:
            proof.update(reason='source_or_reference_unavailable_or_invalid', error_type=type(exc).__name__)
        else:
            passed = fingerprint(derived) == source['hash']
            proof.update(source_replay_completed=True, passed=passed,
                         reason='reproduced' if passed else 'source_or_derivation_mismatch')
    return lab.store.put('verification', proof)
