"""Read-only compatibility of one exact blueprint with existing registration.

Preparation shares the actual registration source, constructors and world gate.
A result is neither a frozen protocol nor authority to spend or run subjects.
"""
import copy
import re
from .experiment_authoring import (RegistrationPreparationError,
    prepare_blueprint_registration, selected_blueprint, validate_registration_plan)

PREVIEW_VERSION = 'registration-compatibility-preview-v1'
LIMITS = [
    'Unregistered point-in-time preview; actual registration repeats every gate for its selected exact blueprint and subject mode.',
    'current_source_authorization means local registry/record membership and current implementation checks only; not user authorization, cloud permissions, remaining budget or upstream freshness.',
    'fit_approved_analogue is a bound supplied/model review disposition; semantic citation truth, historical fidelity and causal mechanism identification remain unestablished.',
    'Preparation runs finite factory/boundary probes and constructs prospective protocol declarations; it calls no subjects, archives no runs and reserves no budget.',
    'Fixed registered contrasts do not automatically operationalize the blueprint mechanism or the local study-guide question.',
]


def _ref(value):
    if type(value) is not dict or set(value) != {'id', 'version', 'hash'}:
        raise ValueError('Use an exact blueprint reference with id, version and hash')
    if type(value['id']) is not str or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._:-]{0,199}', value['id']):
        raise ValueError('Use a bounded blueprint ID')
    if type(value['version']) is not int or not 1 <= value['version'] <= 10**9:
        raise ValueError('Use a positive bounded blueprint version integer')
    if type(value['hash']) is not str or not re.fullmatch('[0-9a-f]{64}', value['hash']):
        raise ValueError('Use an exact lowercase blueprint hash')
    return copy.deepcopy(value)


def _plan(trials, seed, live):
    return validate_registration_plan(trials, seed, live)


def _design(prepared):
    p = prepared['payload']['protocol']; design = p['design']; estimand = p['estimand']
    if 'arms' in p:
        conditions = list(p['arms']); maximum_units = design['trials_per_arm'] * len(conditions)
        environment = p['environment']; maximum_calls = maximum_units * len(environment['agents']) * environment['max_rounds']
        contrast = ' versus '.join(estimand['primary_contrast'])
    elif 'cells' in design:
        conditions = [cell['topology'] + ' / ' + cell['context'] for cell in design['cells']]
        maximum_units = design['trials_per_cell'] * len(conditions)
        environment = next(iter(p['environments'].values()))
        maximum_calls = maximum_units * len(environment['agents']) * environment['max_rounds']
        contrast = '; '.join(c['factor'] + ': ' + c['treatment'] + ' versus ' + c['control']
            + ' (stratified by ' + c['stratify_by'] + ')' for c in estimand['primary_contrasts'])
    else:
        conditions = list(p['contexts']); maximum_units = design['trials_per_cell'] * len(conditions)
        maximum_calls = design['maximum_subject_calls']; contrast = estimand['treatment'] + ' versus ' + estimand['control']
    return {'object_kind': prepared['kind'], 'study_kind': p.get('study_kind', 'shared_artifact_context'),
        'research_question': p['research_question'],
        'experimental_unit': estimand.get('unit', design.get('unit', design.get('randomization_unit'))),
        'primary_outcome': estimand['primary_outcome'], 'primary_contrast': contrast,
        'conditions': conditions, 'maximum_units': maximum_units, 'maximum_subject_calls': maximum_calls,
        'maximum_hosted_subject_calls': maximum_calls if p['subject_backend']['harness'] == 'responses' else 0,
        'subject_backend': copy.deepcopy(p['subject_backend']), 'world_spec_hash': prepared['world_spec_hash']}


def parse_registration_preview_query(query):
    """Strict parsed-query boundary before any registry access.

    The caller supplies urllib.parse.parse_qs(..., keep_blank_values=True).
    Reject duplicate, extra, blank, noncanonical or unbounded values here.
    """
    keys = {'blueprint_id', 'blueprint_version', 'blueprint_hash', 'trials_per_cell', 'seed', 'live'}
    if type(query) is not dict or set(query) != keys:
        raise ValueError('Supply exactly the six registration-preview query fields')
    values = {}
    maxima = {'blueprint_id': 200, 'blueprint_version': 10, 'blueprint_hash': 64,
              'trials_per_cell': 4, 'seed': 19, 'live': 5}
    for key in keys:
        entries = query[key]
        if type(entries) is not list or len(entries) != 1 or type(entries[0]) is not str or not 0 < len(entries[0]) <= maxima[key]:
            raise ValueError('Registration-preview fields must be single, nonblank bounded strings')
        values[key] = entries[0]
    for key in ('blueprint_version', 'trials_per_cell'):
        if not re.fullmatch('[1-9][0-9]*', values[key]):
            raise ValueError('Use canonical positive integer registration-preview fields')
    if not re.fullmatch('0|[1-9][0-9]*', values['seed']):
        raise ValueError('Use a canonical nonnegative seed')
    if values['live'] not in ('true', 'false'):
        raise ValueError('live must be literal true or false')
    reference = _ref({'id': values['blueprint_id'], 'version': int(values['blueprint_version']), 'hash': values['blueprint_hash']})
    plan = _plan(int(values['trials_per_cell']), int(values['seed']), values['live'] == 'true')
    return {'blueprint_ref': reference, **plan}


def preview_blueprint_registration(lab, blueprint_ref, *, trials_per_cell=2, seed=4491, live=False):
    ref = _ref(blueprint_ref); plan = _plan(trials_per_cell, seed, live)
    obj = selected_blueprint(lab, ref['id'], blueprint_version=ref['version'], blueprint_hash=ref['hash'])
    saved = obj['payload']
    checks = {'construction_compiled': saved.get('construction_status') == 'compiled',
        'fit_approved_analogue': saved.get('experiment_eligibility') == 'approved_analogue',
        'current_source_authorization': None, 'design_compatible': None, 'exact_world_preserved': None}
    packet = {'preview_version': PREVIEW_VERSION, 'blueprint_ref': ref, 'registration_plan': plan,
        'status': 'blocked', 'checks': checks, 'reason': None, 'design': None,
        'registered': False, 'model_calls': 0, 'database_writes': 0, 'raw_source_reread': False,
        'limits': list(LIMITS)}
    try:
        prepared = prepare_blueprint_registration(lab, obj, **plan)
    except RegistrationPreparationError as error:
        message = ('The existing registered constructor does not accept this specification or registration plan.'
            if error.code == 'constructor_rejected_parameters' else str(error)[:1000])
        packet['reason'] = {'stage': error.stage, 'code': error.code, 'message': message}
        if error.stage == 'source': checks['current_source_authorization'] = False
        if error.stage == 'design':
            checks.update(current_source_authorization=True, design_compatible=False)
            if error.code == 'authored_world_not_preserved': checks['exact_world_preserved'] = False
        return packet
    checks.update(current_source_authorization=True, design_compatible=True, exact_world_preserved=True)
    packet.update(status='compatible', design=_design(prepared))
    return packet
