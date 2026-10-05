"""Register an approved authored world only when an existing design preserves it.

Preparation is shared with the read-only preview. It constructs prospective
protocol declarations without registration, archives, subjects or call spending.
"""
import hashlib
import json
import re
from pathlib import Path
from . import environment_authoring
from .environment_authoring import compile_blueprint
from .store import fingerprint, now


class RegistrationPreparationError(ValueError):
    """Structured stage of a registration refusal; never an outcome finding."""
    def __init__(self, stage, code, message):
        super().__init__(message)
        self.stage = stage
        self.code = code


def validate_registration_plan(trials_per_cell, seed, live):
    if type(trials_per_cell) is not int or not 2 <= trials_per_cell <= 1000:
        raise ValueError('trials_per_cell must be an integer between 2 and 1000')
    if type(seed) is not int or not 0 <= seed < 2**63:
        raise ValueError('seed must be a nonnegative 63-bit integer')
    if type(live) is not bool:
        raise ValueError('live must be boolean')
    return {'trials_per_cell': trials_per_cell, 'seed': seed, 'live': live}


def _spec_identity(value):
    try:
        encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, RecursionError) as error:
        raise RegistrationPreparationError('source', 'invalid_saved_world_body',
            'Saved world must have finite canonical JSON identity') from error
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()


def selected_blueprint(lab, blueprint_id, *, blueprint_version=None, blueprint_hash=None):
    """ID-only callers select latest; a paired version/hash selects exactly."""
    if (blueprint_version is None) != (blueprint_hash is None):
        raise ValueError('Supply blueprint_version and blueprint_hash together')
    if blueprint_version is not None:
        if type(blueprint_version) is not int or not 1 <= blueprint_version <= 10**9:
            raise ValueError('Use a positive bounded blueprint_version integer')
        if type(blueprint_hash) is not str or not re.fullmatch('[0-9a-f]{64}', blueprint_hash):
            raise ValueError('Use an exact lowercase blueprint_hash')
    obj = lab.store.get(blueprint_id, blueprint_version)
    if blueprint_hash is not None and obj['hash'] != blueprint_hash:
        raise ValueError('Blueprint hash does not match the selected exact version')
    return obj


def prepare_blueprint_registration(lab, obj, *, trials_per_cell=2, seed=4491, live=False):
    """Run the actual source/world checks, returning a prospective payload only."""
    validate_registration_plan(trials_per_cell, seed, live)
    if obj['kind'] != 'environment_blueprint':
        raise RegistrationPreparationError('selection', 'wrong_object_kind', 'Use an environment blueprint')
    saved = obj['payload']
    if saved.get('construction_status') != 'compiled' or saved.get('experiment_eligibility') != 'approved_analogue':
        raise RegistrationPreparationError('approval', 'construction_or_fit_unapproved',
            'World construction and a bound approving fit review are required before registration')
    try:
        fresh = compile_blueprint(saved['proposed_blueprint'], store=lab.store, fit_review=saved['fit_review'],
            audit_seed=saved['boundary_audit']['audit_seed'], required_capabilities=saved['trusted_required_capabilities'])
    except (KeyError, TypeError) as error:
        raise RegistrationPreparationError('shape', 'invalid_saved_blueprint_shape',
            'Saved blueprint cannot supply the required registration checks') from error
    except Exception as error:
        raise RegistrationPreparationError('source', 'current_recompilation_failed',
            'Current source and implementation checks could not complete') from error
    keys = ('construction_status', 'experiment_eligibility', 'blueprint_hash', 'spec_hash', 'catalog_hash', 'environment_code_hashes')
    if any(fresh.get(k) != saved.get(k) for k in keys) or _spec_identity(fresh.get('spec')) != _spec_identity(saved.get('spec')):
        raise RegistrationPreparationError('source', 'saved_source_or_implementation_changed',
            'Saved construction, source pins or implementation changed; construct and review a new blueprint')
    spec = fresh['spec']; kind = spec['kind']; incident = spec['incident_provenance']
    backend = {'harness': 'responses' if live else 'scripted', 'model': lab.settings.model if live else 'deterministic_offline_policy',
        'generation': {'max_output_tokens': 600, 'temperature': 'provider_default', 'sampling_seed': 'not_set'}}
    try:
        if kind == 'shared_artifact_coordination':
            from .experiments import create_protocol
            protocol = create_protocol(incident, trials_per_arm=trials_per_cell, seed=seed, max_rounds=spec['max_rounds'],
                environment_override={'initial_state_distribution': spec['initial_state_distribution']}, subject_backend=backend)
            actual = protocol['environment']; object_kind = 'protocol'
        elif kind == 'exclusive_resource_tasks':
            from .resource_experiments import create_resource_protocol
            from .resource_workflow import resource_backend
            backend = resource_backend(lab, live)
            protocol = create_resource_protocol(trials_per_cell=trials_per_cell, seed=seed, max_rounds=spec['max_rounds'],
                release_rounds=spec['resource_world']['release_rounds'],
                independent_work_steps=spec['task_world']['independent_work_steps'],
                computer_work_steps=spec['task_world']['computer_work_steps'],
                max_messages_per_agent=spec['max_messages_per_agent'], incident=incident, subject_backend=backend)
            actual = protocol['environment']; object_kind = 'resource_protocol'
        else:
            topology = spec['topology']['kind']
            if topology == 'custom':
                raise RegistrationPreparationError('design', 'custom_topology_not_registered',
                    'The world supports custom edges, but registered network designs do not; no graph substitution is permitted')
            if kind == 'provenance_diffusion':
                from .diffusion_experiments import create_diffusion_protocol
                protocol = create_diffusion_protocol(trials_per_cell=trials_per_cell, seed=seed, max_rounds=spec['max_rounds'],
                    topologies=[topology], contexts=['placebo', 'source_thought'],
                    source_reliability=spec['measurement_world']['source_reliability'], incident=incident, subject_backend=backend)
                object_kind = 'network_protocol'
            elif kind == 'complementary_information':
                from .complementary_experiments import create_complementary_protocol
                if not live: backend['generation'] = {'policy': 'offline_complementary_policy'}
                protocol = create_complementary_protocol(trials_per_cell=trials_per_cell, seed=seed, max_rounds=spec['max_rounds'],
                    topologies=[topology], contexts=['placebo', 'source_thought'],
                    modulus=spec['measurement_world']['modulus'], incident=incident, subject_backend=backend)
                object_kind = 'complementary_protocol'
            else:
                raise RegistrationPreparationError('design', 'no_registered_design', 'No registered design exists for this world')
            actual = protocol['environments'][topology]
    except RegistrationPreparationError:
        raise
    except (ValueError, TypeError, KeyError) as error:
        raise RegistrationPreparationError('design', 'constructor_rejected_parameters', str(error)) from error
    except Exception as error:
        raise RegistrationPreparationError('source', 'current_constructor_unavailable',
            'The registered constructor or its current source checks are unavailable') from error
    if actual != spec:
        raise RegistrationPreparationError('design', 'authored_world_not_preserved',
            'Existing design changes the authored world parameters; no silent weakening or substitution is permitted')
    reference = {k: obj[k] for k in ('kind', 'id', 'version', 'hash')}
    # Resolve the unchanged production adapter next to the compiler module. This
    # is also valid when this preparation module is imported from staged tests.
    adapter = Path(environment_authoring.__file__).with_name('harness.py')
    try:
        adapter_hash = hashlib.sha256(adapter.read_bytes()).hexdigest() if live else None
    except OSError as error:
        raise RegistrationPreparationError('source', 'current_adapter_unavailable',
            'The current subject-adapter source is unavailable') from error
    payload = {'protocol': protocol, 'frozen_hash': fingerprint(protocol),
        'registered_at': now(), 'status': 'registered', 'agent_mode': 'live' if live else 'offline_template',
        'behavior_id': saved.get('behavior_id'), 'environment_blueprint_ref': reference,
        'subject_adapter_hash': adapter_hash,
        'historical_mechanism_support': 'unestablished',
        'design_compatibility': {'world_equality': 'exact', 'registered_design': protocol.get('study_kind', 'shared_artifact_context'),
            'factor_scope': 'Fixed predefined private context contrast; authored world parameters remain constant across arms.',
            'hypothesis_scope': 'This design does not automatically operationalize every mechanism hypothesis in the blueprint.',
            'blueprint_mechanism_hypothesis': saved['proposed_blueprint']['mechanism_hypothesis'],
            'registered_research_question': protocol['research_question'],
            'fit_scope': 'Bound reviewer approval is a model/supplied judgment, not proof of mechanism fit or freedom from confounding.'}}
    return {'kind': object_kind, 'payload': payload, 'world_spec_hash': fresh['spec_hash']}


def register_blueprint(lab, blueprint_id, *, trials_per_cell=2, seed=4491, live=False,
        blueprint_version=None, blueprint_hash=None):
    obj = selected_blueprint(lab, blueprint_id, blueprint_version=blueprint_version, blueprint_hash=blueprint_hash)
    prepared = prepare_blueprint_registration(lab, obj, trials_per_cell=trials_per_cell, seed=seed, live=live)
    return lab.store.put(prepared['kind'], prepared['payload'])
