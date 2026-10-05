"""Separate paired-block resource/timing study; prior scientific modules stay frozen.

The default policy is a context-independent CPU integration fixture. A receipt
binds a constructed request before invocation; it never attests provider use.
"""
from __future__ import annotations

import copy
import hashlib
import itertools
import json
import math
import platform
import random
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from .intervention_timing import (TimingController, create_timing_spec, validate_timing_spec,
    make_trigger_view, replay_timing_report)
from .resource_environment import (SUBJECTS, fingerprint, create_resource_spec, validate_resource_spec,
    create_resource_environment, resource_subject_request, resource_environment_capabilities,
    check_resource_contract, offline_resource_policy)

API_VERSION = "1.0"
STUDY_KIND = "paired_resource_timing_policy"
CONTEXTS = ("neutral", "active")
SUPPORTED_TRIGGERS = ("first_decision", "executed_wait_independent_pending", "first_observed_resource_open")
ACTIVE_NOTE = "Check your remaining tasks before choosing the next action."
NEUTRAL_NOTE = "Continue your current session before choosing the next action."
OFFLINE_BACKEND = {"harness": "scripted", "model": "deterministic_cpu_fixture",
    "generation": {"policy": "timed_resource_infrastructure_policy", "notes_ignored": True}}
CODE_FILES = ("timed_resource_experiments.py", "intervention_timing.py", "resource_environment.py", "harness.py")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _json_copy(value):
    try:
        return json.loads(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ValueError("Finite JSON is required for execution evidence") from exc


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_copy(value), sort_keys=True, indent=2, ensure_ascii=False), encoding="utf-8")


def _seed(seed, *parts):
    return int(fingerprint([seed, *parts]), 16) % (2**63)


def _same(left, right):
    """Canonical finite JSON identity preserves bool/int/float distinctions."""
    return fingerprint(_json_copy(left)) == fingerprint(_json_copy(right))


def timed_resource_code_hashes():
    return {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in CODE_FILES}


def _seal(value, key="protocol_hash"):
    value = _json_copy(value); value.pop(key, None); value[key] = fingerprint(value)
    return value


def timed_resource_infrastructure_policy(request):
    """Legal wait once, then ordinary task work; ignores all inserted content.

    This deliberately exercises a possible timing boundary. It is a scripted
    mechanics witness, not a model of any observed agent or causal evidence.
    """
    if not request["observation"]["your_action_history"]:
        return {"action": "wait"}
    return offline_resource_policy(request)


def _protocol_body(trials_per_cell, seed, *, created_at, trigger_kind, max_rounds, release_rounds,
        independent_work_steps, computer_work_steps, max_messages_per_agent, active_text, neutral_text,
        subject_backend, incident, code_hashes, resamples):
    if type(trials_per_cell) is not int or not 2 <= trials_per_cell <= 1000:
        raise ValueError("Require 2 to 1000 whole swarms per arm, forming independent seed blocks")
    if type(seed) is not int or trigger_kind not in SUPPORTED_TRIGGERS:
        raise ValueError("Unsupported resource trigger or seed namespace")
    if type(resamples) is not int or not 100 <= resamples <= 100000:
        raise ValueError("Preregister 100 to 100000 resamples")
    if not isinstance(created_at,str): raise ValueError("Registration timestamp must be an ISO string")
    try:
        timestamp = datetime.fromisoformat(created_at)
        if timestamp.tzinfo is None: raise ValueError("Registration timestamp requires a timezone")
    except ValueError as exc: raise ValueError("Invalid registration timestamp") from exc
    backend = _json_copy(subject_backend or OFFLINE_BACKEND)
    if (not isinstance(backend, dict) or not isinstance(backend.get("harness"), str) or not backend["harness"]
            or not isinstance(backend.get("model"), str) or not backend["model"] or not isinstance(backend.get("generation"), dict)):
        raise ValueError("Pin model, harness and generation metadata before execution")
    if backend["harness"] == "scripted" and not _same(backend,OFFLINE_BACKEND):
        raise ValueError("The built-in scripted backend must name its actual context-independent CPU fixture")
    spec = create_resource_spec(max_rounds=max_rounds, release_rounds=release_rounds,
        independent_work_steps=independent_work_steps, computer_work_steps=computer_work_steps,
        max_messages_per_agent=max_messages_per_agent, incident=incident)
    timing = create_timing_spec(trigger_kind, recipient="agent-0", active_text=active_text, neutral_text=neutral_text)
    cap = resource_environment_capabilities()
    count = 2**trials_per_cell
    return {"api_version": API_VERSION, "study_kind": STUDY_KIND, "created_at": created_at,
        "status": "frozen_before_execution", "phase": "bounded_timing_and_mechanics_pilot",
        "registration_scope": "Local frozen protocol; not public preregistration",
        "environment": spec, "environment_hash": fingerprint(spec), "capabilities": cap, "capability_hash": fingerprint(cap),
        "timing_spec": timing, "timing_spec_hash": timing["spec_hash"], "trigger_hash": timing["trigger_hash"],
        "subject_backend": backend,
        "design": {"unit": "whole_swarm_run", "allocation": "one_active_one_neutral_randomized_within_each_seed_block",
            "independent_seed_blocks": trials_per_cell, "trials_per_cell": trials_per_cell, "seed": seed,
            "contexts": list(CONTEXTS), "execution_order": "separately_seeded_shuffle_of_all_assigned_swarms",
            "world_pairing": "Separate fresh worlds with exact identical precomputed scheduler and release path within a block",
            "maximum_subject_calls": 2*trials_per_cell*len(SUBJECTS)*max_rounds,
            "maximum_preparations_per_swarm": 1,
            "stopping_rule": "All assigned swarms; stop each only on all code-scored completions or its allocated action horizon",
            "interference": "Allowed within a swarm; prohibited across reset swarms. Paired world seeds are intentional dependence.",
            "matched": ["initial world bytes", "full exogenous scheduler", "initial resource release", "task and message costs", "allocated action limits", "backend", "trigger definition"],
            "not_matched": ["chosen actions", "realized leases", "termination time", "used actions", "receipt occurrence", "hosted sampling"]},
        "intervention": {"focal_agent": "agent-0", "recipients": ["agent-0"], "channel": "private_observable_context",
            "timing": "Predeclared observed-state trigger before the next scheduled subject invocation",
            "persistence": "From the sole insertion until this reset world's terminal boundary",
            "receipt_scope": "Exact constructed request before invocation; no provider-consumption attestation",
            "after_receipt": "Log preparation_limit_consumed; do not strip persistent notes and re-evaluate eligibility"},
        "estimand": {"unit": "whole_swarm_run", "independent_uncertainty_units": "seed_blocks",
            "primary_outcome": "task_completion_fraction", "treatment": "active", "control": "neutral", "direction": "two_sided",
            "operational_definition": "Code-scored executed completions divided by eight assigned tasks; unfinished tasks zero",
            "population": "Independent seed blocks from this synthetic task and schedule generator with the pinned backend",
            "contrast": "Mean within-block active-minus-neutral whole-swarm outcome difference, including never-delivered assigned swarms"},
        "measurement": {"oracle": "Frozen resource execution counters; claims/messages do not complete tasks or grant access",
            "primary_test": "Two-sided within-block label-swap randomization test",
            "test_null": "Sharp no-effect null for the assigned timing-and-content policy at every swarm; not an exact weak-average-null test under heterogeneous effects",
            "primary_interval": "95% bounded independent-block Hoeffding interval for paired differences in [-1,1]",
            "secondary_interval": "Paired-block bootstrap sensitivity; can degenerate in small pilots",
            "resampling": {"resamples":resamples,"exact_label_swap_max_blocks":16,
                "larger_block_method":"Approximate Monte Carlo label-swap p=(extreme+1)/(resamples+1)",
                "seed_policy":"Deterministic independent namespaces from the preregistered design seed",
                "label_swap_namespace":"timed-label-swap","bootstrap_namespace":"timed-paired-bootstrap"},
            "multiplicity": "One primary contrast; task, wait, receipt and lease metrics descriptive only",
            "invalid_actions": "Serializable invalid actions consume their scheduled action allowance",
            "nondelivery": "Completed assigned swarms remain in policy ITT regardless of receipt or unresolved trigger ascertainment",
            "infrastructure_failure": "Retain entire assignment grid and partial evidence, abort all causal estimation; no replacement or success selection",
            "process_interpretation": "Executed waits, access and receipts describe post-treatment processes, not beliefs, mediation or principal strata"},
        "pre_execution_test_resolution": {"block_swap_assignments": count, "minimum_two_sided_p": math.ldexp(2.0, -trials_per_cell),
            "exact_minimum_fraction": f"2/{count}", "warning": "N=2 independent seed blocks has minimum attainable two-sided exact p=0.5; this is a mechanics pilot with wide intervals"},
        "limitations": ["Global exclusive computer access is an invented analogue; historical global exclusivity is unestablished.",
            "The world models abstract steps and one exogenous release, not real work quality, browser tasks or wall-clock latency.",
            "Equal exogenous paths do not equalize realized resource access or action-dependent stopping.",
            "Matching seed blocks changes the variance/design; it is explicit registration, not post-hoc selection or a claim of independent paired swarms.",
            "Content-and-timing policy ITT includes nondelivery; conditioning on receipt, waits or achieved access is not a causal comparison.",
            "Private context can spill over through later messages and actions inside a swarm; no mediator or latent belief is identified.",
            "A local request receipt does not prove provider invocation, consumption or semantic adoption.",
            "Subject callbacks must have fresh sessions without cross-swarm memory; this is a caller assumption.",
            "Matched words do not match tokens or make the neutral note inert; hosted sampling and provider stability remain assumptions.",
            "The built-in policy is CPU infrastructure evidence and does not demonstrate any model effect.",
            "Selected project sources are pinned; Python/stdlib runtime binaries are not archived, and the runtime version is recorded."],
        "execution_code_hashes": code_hashes}


def create_timed_resource_protocol(trials_per_cell=2, seed=149, *, trigger_kind="executed_wait_independent_pending",
        max_rounds=6, release_rounds=(1,2), independent_work_steps=1, computer_work_steps=1,
        max_messages_per_agent=None, active_text=ACTIVE_NOTE, neutral_text=NEUTRAL_NOTE,
        subject_backend=None, incident=None, resamples=2000):
    return _seal(_protocol_body(trials_per_cell, seed, created_at=_now(), trigger_kind=trigger_kind,
        max_rounds=max_rounds, release_rounds=release_rounds, independent_work_steps=independent_work_steps,
        computer_work_steps=computer_work_steps, max_messages_per_agent=max_messages_per_agent,
        active_text=active_text, neutral_text=neutral_text, subject_backend=subject_backend, incident=incident,
        code_hashes=timed_resource_code_hashes(),resamples=resamples))


def validate_timed_resource_protocol(protocol):
    p = _json_copy(protocol); signature = p.pop("protocol_hash", None)
    if signature != fingerprint(p): raise ValueError("Timed resource protocol changed after freezing")
    try:
        validate_resource_spec(p["environment"]); validate_timing_spec(p["timing_spec"])
        env, timing, design = p["environment"], p["timing_spec"], p["design"]
        expected = _protocol_body(design["trials_per_cell"], design["seed"], created_at=p["created_at"],
            trigger_kind=timing["trigger"]["kind"], max_rounds=env["max_rounds"],
            release_rounds=env["resource_world"]["release_rounds"], independent_work_steps=env["task_world"]["independent_work_steps"],
            computer_work_steps=env["task_world"]["computer_work_steps"], max_messages_per_agent=env["max_messages_per_agent"],
            active_text=timing["content"]["active"], neutral_text=timing["content"]["neutral"], subject_backend=p["subject_backend"],
            incident=env["incident_provenance"], code_hashes=timed_resource_code_hashes(),resamples=p["measurement"]["resampling"]["resamples"])
        if not _same(p,expected): raise ValueError("Timed resource declarations or pinned execution sources changed")
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("Malformed timed resource protocol") from exc
    return True


def randomize_timed_resource_runs(protocol):
    validate_timed_resource_protocol(protocol)
    n, seed = protocol["design"]["trials_per_cell"], protocol["design"]["seed"]
    allocation = random.Random(_seed(seed, "timed-allocation")); assignments = []
    seeds = [_seed(seed, "timed-world", i) for i in range(n)]
    if len(set(seeds)) != n: raise ValueError("Independent block seed collision")
    for block in range(n):
        contexts = list(CONTEXTS); allocation.shuffle(contexts)
        for slot, context in enumerate(contexts):
            assignments.append({"run_id": f"timed-run-{block+1:04d}-{slot}", "block_id": f"seed-block-{block+1:04d}",
                "block_index": block, "slot": slot, "context": context, "environment_seed": seeds[block]})
    random.Random(_seed(seed, "timed-execution-order")).shuffle(assignments)
    for index, unit in enumerate(assignments): unit["execution_index"] = index
    return assignments


def _world_identity(initial, protocol):
    return {"environment_hash": protocol["environment_hash"], "environment_seed": initial["seed"],
        "snapshot_hash": fingerprint(initial), "schedule": copy.deepcopy(initial["schedule"]),
        "schedule_hash": fingerprint(initial["schedule"]), "release_round": initial["release_round"]}


def _pair_world_checks(runs):
    blocks = sorted(set(r["block_id"] for r in runs)); checks = []
    for block in blocks:
        pair = [r for r in runs if r["block_id"] == block]
        checks.append({"block_id": block, "passed": len(pair) == 2 and pair[0]["initial_state"] is not None
            and _same(pair[0]["initial_state"],pair[1]["initial_state"])
            and _same(pair[0]["initial_world_identity"],pair[1]["initial_world_identity"]),
            "scope": "Exact initial world and full precomputed exogenous path; realized access can differ"})
    return checks


def _paired_effect(differences, *, seed, resamples):
    n = len(differences); difference = mean(differences); observed = abs(difference)
    if n <= 16:
        total = 2**n
        extreme = sum(abs(sum(sign*d for sign,d in zip(signs,differences))/n) >= observed-1e-12
                      for signs in itertools.product((-1,1), repeat=n))
        p = extreme/total; test = {"method": "exact_block_label_swap", "assignments": total}
    else:
        rng = random.Random(_seed(seed,"timed-label-swap"))
        extreme = sum(abs(sum(rng.choice((-1,1))*d for d in differences)/n) >= observed-1e-12 for _ in range(resamples))
        p = (extreme+1)/(resamples+1); test = {"method": "monte_carlo_block_label_swap_plus_one", "resamples": resamples}
    radius = math.sqrt(2*math.log(40)/n)
    rng = random.Random(_seed(seed,"timed-paired-bootstrap"))
    samples = sorted(mean(rng.choice(differences) for _ in range(n)) for _ in range(resamples))
    return {"difference": difference, "ci95": [max(-1,difference-radius),min(1,difference+radius)],
        "ci_method": "Independent-block bounded Hoeffding interval; paired differences in [-1,1]",
        "p_two_sided": p, "randomization_test": test,
        "paired_bootstrap_ci95_sensitivity": [samples[int(.025*(resamples-1))],samples[int(.975*(resamples-1))]],
        "paired_differences": differences, "unit": "whole_swarm_run", "independent_uncertainty_units": "seed_blocks",
        "n_seed_blocks": n, "n_treatment_swarms": n, "n_control_swarms": n,
        "outcome": "task_completion_fraction", "treatment": "active", "control": "neutral"}


def _registered_resamples(protocol, resamples):
    registered = protocol["measurement"]["resampling"]["resamples"]
    if resamples is not None and (type(resamples) is not int or resamples != registered):
        raise ValueError("Resampling count differs from frozen registration")
    return registered


def analyze_timed_resource_runs(runs, protocol, *, resamples=None):
    validate_timed_resource_protocol(protocol)
    resamples = _registered_resamples(protocol,resamples)
    expected = randomize_timed_resource_runs(protocol)
    if len(runs) != len(expected) or any(not _same({k:r.get(k) for k in unit},unit) for r,unit in zip(runs,expected)):
        raise ValueError("Retain every assigned swarm in its randomized execution order")
    if not all(c["passed"] for c in _pair_world_checks(runs)): raise ValueError("Paired exogenous worlds are not byte-identical")
    for run in runs:
        outcome = run.get("outcomes", {}).get("task_completion_fraction")
        if (run.get("status") != "complete" or type(outcome) not in (int,float) or not math.isfinite(outcome) or not 0 <= outcome <= 1
                or run["outcomes"].get("terminated_by") not in ("all_tasks_completed","step_budget")
                or run["timing_report"]["execution_status"] != "completed" or run["timing_report"]["status"] != "complete_contract"):
            raise ValueError("All complete assigned oracle outcomes are required; infrastructure failures cannot be excluded")
    differences = []
    for block in sorted(set(r["block_id"] for r in runs)):
        pair = {r["context"]:r for r in runs if r["block_id"] == block}
        differences.append(pair["active"]["outcomes"]["task_completion_fraction"]-pair["neutral"]["outcomes"]["task_completion_fraction"])
    metrics = ("task_completion_fraction","independent_completion_fraction","computer_completion_fraction","focal_completion_fraction",
        "resource_access_grants","resource_access_denials","waits","waits_while_independent_pending","task_specific_blocked_waits","messages_sent","steps_used","invalid_actions")
    cells = {}
    for context in CONTEXTS:
        group = [r for r in runs if r["context"] == context]
        cells[context] = {"n_swarms":len(group), **{m:mean(r["outcomes"][m] for r in group) for m in metrics},
            "recorded_receipts":sum(r["counts"]["recorded_receipts"] for r in group),
            "never_delivered_completed_swarms":sum(r["counts"]["recorded_receipts"] == 0 for r in group),
            "eligibility_unresolved_completed_swarms":sum(r["timing_report"]["policy_itt"]["eligibility_status"] == "eligibility_unresolved" for r in group)}
    return {"cells":cells,"primary_effect":_paired_effect(differences,seed=protocol["design"]["seed"],resamples=resamples),
        "primary_family_size":1,"test_null":protocol["measurement"]["test_null"],"resamples":resamples,
        "warnings":["N=2 seed blocks has minimum exact two-sided p=0.5 and a very wide bounded interval.",
            "All completed assigned swarms, including never delivered, remain in policy ITT.",
            "Individual turns/tasks and the two paired swarms are not independent uncertainty samples.",
            "Receipt, wait and lease counts are post-treatment descriptions; no conditional causal contrast or mediation.",
            "Scripted policies verify mechanics and cannot demonstrate a model effect."]}


class TimedResourceExecutionError(RuntimeError):
    def __init__(self, message, partial_report):
        super().__init__(message); self.partial_report = partial_report


class _BoundaryConstructionError(RuntimeError):
    def __init__(self, boundary, request, cause):
        super().__init__("Pre-subject timing/request construction failed")
        self.boundary, self.request, self.original_error_type = boundary, request, type(cause).__name__


def _archive(output, protocol, assignments):
    if output.exists() and any(output.iterdir()): raise ValueError("Use a fresh output directory; automatic execution resumption is unsupported")
    output.mkdir(parents=True,exist_ok=True)
    _write(output/"protocol.json",protocol); _write(output/"assignment.json",assignments)
    for name,expected in protocol["execution_code_hashes"].items():
        data = Path(__file__).with_name(name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected: raise ValueError("Archived source differs from frozen registration")
        target = output/"execution-code"/name; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(data)
    _write(output/"execution-code"/"manifest.json",{"files":protocol["execution_code_hashes"],"timing":"before_subject_calls",
        "scope":"Selected frozen execution sources only; file contents do not authenticate invocation timing"})


def _boundary(env, controller, protocol):
    actor = env.next_agent; request = resource_subject_request(env,actor); output = receipt = None
    mode = "nonrecipient_no_trigger_evaluation" if actor != "agent-0" else "preparation_limit_consumed" if controller.snapshot()["receipt"] is not None else "arm_blind_pre_insertion_evaluation"
    boundary = {"step":env.step_count,"agent_id":actor,"mode":mode,"trigger_output":None,"local_receipt":None,
        "subject_request_hash":fingerprint(request),"subject_call_attempted":False,"applied_action":False,"construction_status":"complete"}
    stage = "controller_prepare"
    try:
        if mode == "arm_blind_pre_insertion_evaluation":
            output = controller.prepare(request); boundary["trigger_output"] = output
            if output["decision"]["eligible"] is True:
                stage = "context_injection"; env.inject_context(actor,output["insertion_text"])
                stage = "request_after_injection"; request = resource_subject_request(env,actor)
                boundary["subject_request_hash"] = fingerprint(request)
                stage = "receipt_validation"; receipt = controller.record_delivery(output["opportunity_id"],request)
                boundary["local_receipt"] = receipt
    except Exception as exc:
        boundary.update(construction_status="incomplete",failure_stage=stage,error_type=type(exc).__name__)
        raise _BoundaryConstructionError(boundary,request,exc) from exc
    return request,boundary


def _counts(run):
    timing = run.get("timing_report")
    raw = run.get("unfinalizable_timing_snapshot")
    return {"eligible_preparations":timing["policy_itt"]["eligible_preparations"] if timing else int(raw["trigger_state"]["attempted"]) if raw else 0,
        "recorded_receipts":timing["policy_itt"]["recorded_deliveries"] if timing else int(raw["receipt"] is not None) if raw else 0,
        "timing_counts_source":"sealed_controller_report" if timing else "unsealed_controller_snapshot" if raw else "not_initialized",
        "subject_call_attempts":sum(b["subject_call_attempted"] for b in run["boundaries"]),
        "applied_actions":len(run["turns"]),"terminal_completion":run["status"] == "complete"}


def _report_declarations(protocol):
    scripted = _same(protocol["subject_backend"],OFFLINE_BACKEND)
    return {"api_version":API_VERSION,"study_kind":STUDY_KIND,
        "experiment_id":"timed-resource-"+protocol["protocol_hash"][:16],"protocol_hash":protocol["protocol_hash"],
        "maximum_subject_calls":protocol["design"]["maximum_subject_calls"],"model_calls":0 if scripted else None,
        "evidence_scope":"CPU scripted mechanics only; no empirical model effect" if scripted else
            "Recorded callback actions in a synthetic resource analogue; invocation origin/consumption is not attested by replay"}


def _zero_counts():
    return {"eligible_preparations":0,"recorded_receipts":0,"timing_counts_source":"not_initialized",
        "subject_call_attempts":0,"applied_actions":0,"terminal_completion":False}


def _unit_base_fields(unit):
    return set(unit) | {"status","initial_state","initial_world_identity","turns","boundaries","timing_report","counts"}


def _unstarted_shape(run, unit, *, materialized=False):
    fields = _unit_base_fields(unit)
    if run["status"] == "incomplete":
        fields |= {"pending_subject_request","attempted_action"}
        if materialized: fields.add("final_state")
        if run.get("pending_subject_request") is not None or run.get("attempted_action") is not None: return False
    elif run["status"] != "not_started": return False
    return (set(run) == fields and run["turns"] == [] and run["boundaries"] == [] and run["timing_report"] is None
        and _same(run["counts"],_zero_counts())
        and (materialized or run["initial_world_identity"] is None)
        and (not materialized or run["status"] != "incomplete" or _same(run["final_state"],run["initial_state"])))


def _execution_progression(report):
    states = [r["status"] for r in report["runs"]]
    if report["status"] == "complete": return bool(states) and all(s == "complete" for s in states) and "failure" not in report
    failure = report.get("failure",{}); phase = failure.get("phase")
    if report["status"] == "incomplete_analysis_failure": return phase == "analysis" and all(s == "complete" for s in states)
    if report["status"] != "incomplete_infrastructure_failure": return False
    if phase == "pre_subject_archive": return all(s == "not_started" for s in states) and failure.get("run_id") is None
    if phase == "initial_worlds":
        failed = [r for r in report["runs"] if r["status"] == "incomplete"]
        return (len(failed) == 1 and failure.get("run_id") == failed[0]["run_id"] and
            all(r["status"] in ("not_started","incomplete") and _same(r["counts"],_zero_counts()) for r in report["runs"]))
    if phase == "final_report_archive": return all(s == "complete" for s in states)
    prefix = 0
    while prefix < len(states) and states[prefix] == "complete": prefix += 1
    if phase == "persist_completed_run":
        return prefix >= 1 and all(s == "not_started" for s in states[prefix:]) and failure.get("run_id") == report["runs"][prefix-1]["run_id"]
    if phase not in ("timing_and_request","subject_invocation","world_step","oracle_and_finalization"): return False
    return (prefix < len(states) and states[prefix] == "incomplete" and all(s == "not_started" for s in states[prefix+1:])
        and failure.get("run_id") == report["runs"][prefix]["run_id"])


def run_timed_resource_experiment(protocol, agent_runner=None, output_dir=None, *, backend_metadata=None,
        on_progress=None, resamples=None):
    validate_timed_resource_protocol(protocol)
    resamples = _registered_resamples(protocol,resamples)
    p = _json_copy(protocol); registered = p["subject_backend"]
    actual = _json_copy(backend_metadata if backend_metadata is not None else registered)
    if not _same(actual,registered): raise ValueError("Backend differs from frozen registration")
    if agent_runner is None and not _same(registered,OFFLINE_BACKEND): raise ValueError("The CPU fixture cannot replace a registered callback backend")
    if agent_runner is not None and registered["harness"] == "scripted": raise ValueError("Declare a separate backend for a supplied callback")
    if registered["harness"] == "responses" and (output_dir is None or registered.get("harness_adapter_hash") != p["execution_code_hashes"]["harness.py"]):
        raise ValueError("Responses execution requires pre-subject archives and the pinned adapter source")
    assignments = randomize_timed_resource_runs(p); output = Path(output_dir) if output_dir is not None else None
    if output is not None and output.exists() and any(output.iterdir()):
        raise ValueError("Use a fresh output directory; automatic execution resumption is unsupported")
    report = {**_report_declarations(p),"protocol":p,"status":"running","started_at":_now(),"finished_at":None,
        "assignments":assignments,"runs":[{**copy.deepcopy(u),"status":"not_started","initial_state":None,"initial_world_identity":None,
            "turns":[],"boundaries":[],"timing_report":None,"counts":_zero_counts()}
            for u in assignments],"maximum_subject_calls":p["design"]["maximum_subject_calls"],
        "local_artifacts_before_subject_calls":output is not None,
        "backend":{"mode":"scripted_offline_smoke_test" if agent_runner is None else "provided_callback",
            "registered_spec":registered,"metadata":actual,"python":platform.python_version(),"fresh_sessions":"caller_assumption",
            "runtime_provenance":"recorded_unattested; runtime binaries are not archived"}}
    runner = agent_runner or timed_resource_infrastructure_policy; worlds = {}; run = None; controller = None
    request = action = None; phase = "pre_subject_archive"; invocation_unknown = False
    try:
        if output is not None: _archive(output,p,assignments)
        phase = "initial_worlds"
        # Materialize and match ALL initial worlds before the first invocation.
        for run in report["runs"]:
            env = create_resource_environment(p["environment"],run["environment_seed"])
            initial = env.snapshot(); contract = check_resource_contract(env)
            if contract["passed"] is not True or not _same(env.snapshot(),initial): raise RuntimeError("Resource reset contract failed")
            run["initial_state"],run["initial_world_identity"] = initial,_world_identity(initial,p)
            worlds[run["run_id"]] = env
            if output is not None: _write(output/"initial_states"/(run["run_id"]+".json"),initial)
        report["paired_initial_world_checks"] = _pair_world_checks(report["runs"])
        if not all(c["passed"] for c in report["paired_initial_world_checks"]): raise RuntimeError("Exact paired world paths differ before subjects")
        if output is not None: _write(output/"progress.json",report)
        for run in report["runs"]:
            env = worlds[run["run_id"]]; run["status"] = "running"
            controller = TimingController(p["timing_spec"],run["context"])
            while not env.terminal:
                request = action = None; phase = "timing_and_request"; invocation_unknown = False
                request,boundary = _boundary(env,controller,p); run["boundaries"].append(boundary)
                if output is not None:
                    _write(output/"timing_before_subject"/f"{run['run_id']}-{len(run['boundaries']):04d}.json",
                        {"boundary":boundary,"controller":controller.snapshot(),"request":request,"receipt_scope":"request construction only"})
                if output is not None: _write(output/"pending_decision.json",{"status":"awaiting_subject","run_id":run["run_id"],"request":request,"boundary":boundary})
                phase = "subject_invocation"; boundary["subject_call_attempted"] = True; invocation_unknown = True
                action = _json_copy(runner(copy.deepcopy(request))); invocation_unknown = False; phase = "world_step"
                tool_result = env.step(env.next_agent,copy.deepcopy(action)); boundary["applied_action"] = True
                run["turns"].append({"step":boundary["step"],"agent_id":boundary["agent_id"],"request":request,
                    "request_hash":fingerprint(request),"action":action,"tool_result":tool_result})
                if output is not None: _write(output/"pending_decision.json",{"status":"applied","run_id":run["run_id"],"turn":run["turns"][-1]})
            phase = "oracle_and_finalization"
            run["outcomes"],run["final_state"] = env.evaluate(),env.snapshot()
            run["timing_report"] = controller.finalize(run["outcomes"]["task_completion_fraction"],execution_status="completed")
            run["status"] = "complete"; run["counts"] = _counts(run); controller = None
            phase = "persist_completed_run"
            if output is not None: _write(output/"progress.json",report)
            if on_progress is not None:
                try: on_progress({"completed":sum(r["status"] == "complete" for r in report["runs"]),"total":len(assignments),"run_id":run["run_id"],"context":run["context"]})
                except Exception as exc: report.setdefault("reporting_warnings",[]).append({"run_id":run["run_id"],"error_type":type(exc).__name__})
    except Exception as exc:
        if run is not None and run["status"] != "complete":
            run["status"] = "incomplete"; env = worlds.get(run["run_id"])
            if env is not None: run["final_state"] = env.snapshot()
            if isinstance(exc,_BoundaryConstructionError):
                request = exc.request; run["boundaries"].append(exc.boundary)
            run["pending_subject_request"] = request; run["attempted_action"] = action
            if controller is not None:
                try:
                    pending = controller.snapshot()["pending"]
                    if pending is not None: controller.fail_delivery(pending["opportunity_id"],reason="infrastructure_failure")
                    run["timing_report"] = controller.finalize(reason="infrastructure_failure",execution_status="unknown" if invocation_unknown else "incomplete")
                except Exception as timing_error:
                    run["unfinalizable_timing_snapshot"] = controller.snapshot()
                    run["timing_finalization_failure"] = {"error_type":type(timing_error).__name__,"scope":"No completed timing contract could be sealed"}
            run["counts"] = _counts(run)
        report.update(status="incomplete_infrastructure_failure",finished_at=_now(),failure={"phase":phase,"error_type":type(exc).__name__,
            "run_id":run["run_id"] if run else None,"subject_consumption":"unknown" if invocation_unknown else "not_attested",
            "original_error_type":exc.original_error_type if isinstance(exc,_BoundaryConstructionError) else type(exc).__name__})
        report = _seal(report,"report_hash")
        if output is not None:
            try: _write(output/"report.json",report); _write(output/"progress.json",report)
            except Exception as save_error:
                report["failure_artifact_write_error"] = {"error_type":type(save_error).__name__,"partial_report_retained_in_exception":True}
                report = _seal(report,"report_hash")
        raise TimedResourceExecutionError("Timed resource execution failed; complete assignment and partial evidence retained, no effects estimated",report) from exc
    try:
        report["analysis"] = analyze_timed_resource_runs(report["runs"],p,resamples=resamples)
    except Exception as exc:
        report.update(status="incomplete_analysis_failure",finished_at=_now(),failure={"phase":"analysis","error_type":type(exc).__name__})
        report = _seal(report,"report_hash")
        if output is not None:
            try: _write(output/"report.json",report); _write(output/"progress.json",report)
            except Exception as save_error:
                report["failure_artifact_write_error"] = {"error_type":type(save_error).__name__,"partial_report_retained_in_exception":True}
                report = _seal(report,"report_hash")
        raise TimedResourceExecutionError("Timed resource analysis failed; no effects estimated",report) from exc
    report.update(status="complete",finished_at=_now()); report = _seal(report,"report_hash")
    if output is not None:
        try: _write(output/"report.json",report); _write(output/"progress.json",report)
        except Exception as save_error:
            report.pop("analysis",None)
            report.update(status="incomplete_infrastructure_failure",finished_at=_now(),failure={"phase":"final_report_archive","error_type":type(save_error).__name__,"subject_consumption":"not_attested"})
            report = _seal(report,"report_hash")
            try: _write(output/"report.json",report); _write(output/"progress.json",report)
            except Exception as final_error:
                report["failure_artifact_write_error"] = {"error_type":type(final_error).__name__,"partial_report_retained_in_exception":True}
                report = _seal(report,"report_hash")
            raise TimedResourceExecutionError("Final report archive failed; completed swarms retained without promoted estimates",report) from save_error
    return report


def _replay_boundary_failure(env, controller, run, boundary):
    """Reproduce only the known prefix of a failed construction, never retry it."""
    request = resource_subject_request(env,env.next_agent)
    expected = {"step":env.step_count,"agent_id":env.next_agent,"mode":"arm_blind_pre_insertion_evaluation",
        "trigger_output":None,"local_receipt":None,"subject_request_hash":fingerprint(request),
        "subject_call_attempted":False,"applied_action":False,"construction_status":"incomplete",
        "failure_stage":boundary["failure_stage"],"error_type":boundary["error_type"]}
    stage = boundary["failure_stage"]
    if stage != "controller_prepare":
        output = controller.prepare(request); expected["trigger_output"] = output
        if output["decision"]["eligible"] is not True: raise ValueError("Failed insertion lacked an eligible preparation")
        if stage != "context_injection":
            env.inject_context(env.next_agent,output["insertion_text"])
        if stage == "receipt_validation":
            request = run["pending_subject_request"]; expected["subject_request_hash"] = fingerprint(request)
            try: controller.record_delivery(output["opportunity_id"],request)
            except ValueError: pass
            else: raise ValueError("Recorded failed receipt would satisfy the exact request contract")
        elif stage not in ("context_injection","request_after_injection"):
            raise ValueError("Unknown failed request-construction stage")
    return request,expected


def replay_timed_resource_report(report, *, output_dir=None):
    """Replay saved actions, exact timing/request receipts and the code oracle.

    Partial traces may be consistent but never pass complete-result validation.
    No subject callback is called and no provider consumption is established.
    """
    checks = []
    try:
        p = report["protocol"]; validate_timed_resource_protocol(p)
        body = _json_copy(report); signature = body.pop("report_hash",None)
        checks.extend([{"name":"report_hash","passed":signature == fingerprint(body)},
            {"name":"protocol_identity","passed":report["protocol_hash"] == p["protocol_hash"] and report["study_kind"] == STUDY_KIND},
            {"name":"assignments","passed":_same(report["assignments"],randomize_timed_resource_runs(p))},
            {"name":"assigned_grid_retained","passed":len(report["runs"]) == len(report["assignments"]) and all(
                _same({k:run.get(k) for k in unit},unit) for run,unit in zip(report["runs"],report["assignments"]))}])
        declared = _report_declarations(p)
        backend = report["backend"]
        core_backend = {"mode":"scripted_offline_smoke_test" if _same(p["subject_backend"],OFFLINE_BACKEND) else "provided_callback",
            "registered_spec":p["subject_backend"],"metadata":p["subject_backend"],"fresh_sessions":"caller_assumption",
            "runtime_provenance":"recorded_unattested; runtime binaries are not archived"}
        checks.append({"name":"generated_report_and_backend_declarations","passed":_same({k:report.get(k) for k in declared},declared)
            and isinstance(backend,dict) and set(backend) == {*core_backend,"python"}
            and _same({k:backend.get(k) for k in core_backend},core_backend)
            and isinstance(backend["python"],str) and bool(backend["python"])
            and type(report["local_artifacts_before_subject_calls"]) is bool
            and (output_dir is None or report["local_artifacts_before_subject_calls"] is True)
            and report["status"] in ("complete","incomplete_infrastructure_failure","incomplete_analysis_failure")})
        checks.append({"name":"abort_order_and_execution_progression","passed":_execution_progression(report)})
        if output_dir is not None:
            output = Path(output_dir); manifest = json.loads((output/"execution-code"/"manifest.json").read_text(encoding="utf-8"))
            valid = manifest["files"] == p["execution_code_hashes"] and manifest["timing"] == "before_subject_calls"
            valid = valid and all(hashlib.sha256((output/"execution-code"/name).read_bytes()).hexdigest() == digest for name,digest in p["execution_code_hashes"].items())
            valid = valid and _same(json.loads((output/"protocol.json").read_text(encoding="utf-8")),p)
            valid = valid and _same(json.loads((output/"assignment.json").read_text(encoding="utf-8")),report["assignments"])
            valid = valid and _same(json.loads((output/"report.json").read_text(encoding="utf-8")),report)
            checks.append({"name":"archive_bytes_and_manifest","passed":valid})
        for run,unit in zip(report["runs"],report["assignments"]):
            env = create_resource_environment(p["environment"],run["environment_seed"]); initial = env.snapshot()
            if run["initial_state"] is None:
                checks.append({"name":"unmaterialized_unit","run_id":run["run_id"],"passed":_unstarted_shape(run,unit)})
                continue
            valid = _same(initial,run["initial_state"]) and _same(_world_identity(initial,p),run["initial_world_identity"])
            if output_dir is not None:
                valid = valid and _same(json.loads((Path(output_dir)/"initial_states"/(run["run_id"]+".json")).read_text(encoding="utf-8")),initial)
            if run["status"] == "not_started":
                checks.append({"name":"unstarted_fresh_unit","run_id":run["run_id"],"passed":valid and _unstarted_shape(run,unit,materialized=True)})
                continue
            if run["status"] == "incomplete" and run["timing_report"] is None and "unfinalizable_timing_snapshot" not in run:
                checks.append({"name":"fresh_world_failed_before_controller","run_id":run["run_id"],"passed":valid and _unstarted_shape(run,unit,materialized=True)})
                continue
            expected_fields = _unit_base_fields(unit) | {"final_state","outcomes"} if run["status"] == "complete" else _unit_base_fields(unit) | {"final_state","pending_subject_request","attempted_action"}
            if "unfinalizable_timing_snapshot" in run: expected_fields |= {"unfinalizable_timing_snapshot","timing_finalization_failure"}
            valid = valid and set(run) == expected_fields
            controller = TimingController(p["timing_spec"],run["context"])
            for index,boundary in enumerate(run["boundaries"]):
                if type(boundary["subject_call_attempted"]) is not bool or type(boundary["applied_action"]) is not bool:
                    raise ValueError("Boundary execution indicators require exact booleans")
                if boundary.get("construction_status") == "incomplete":
                    request, expected = _replay_boundary_failure(env,controller,run,boundary)
                else:
                    request, expected = _boundary(env,controller,p)
                expected["subject_call_attempted"] = boundary["subject_call_attempted"]
                expected["applied_action"] = boundary["applied_action"]
                valid = valid and _same(expected,boundary)
                if index < len(run["turns"]):
                    turn = run["turns"][index]
                    valid = valid and turn["agent_id"] == env.next_agent and _same(turn["step"],env.step_count)
                    valid = valid and _same(turn["request"],request) and turn["request_hash"] == fingerprint(request)
                    valid = valid and boundary["subject_call_attempted"] is True and boundary["applied_action"] is True
                    result = env.step(env.next_agent,copy.deepcopy(turn["action"])); valid = valid and _same(result,turn["tool_result"])
                else:
                    valid = valid and index == len(run["turns"]) and index == len(run["boundaries"])-1 and boundary["applied_action"] is False
                    valid = valid and run["status"] == "incomplete" and _same(run["pending_subject_request"],request)
            valid = valid and _same(run["counts"],_counts(run))
            if run["status"] == "complete":
                timing = controller.finalize(env.evaluate()["task_completion_fraction"],execution_status="completed")
                valid = valid and len(run["boundaries"]) == len(run["turns"]) and env.terminal
                valid = valid and _same(env.evaluate(),run["outcomes"]) and _same(env.snapshot(),run["final_state"])
            else:
                if run["timing_report"] is None:
                    checks.append({"name":"unfinalizable_controller","run_id":run["run_id"],"passed":False})
                    continue
                pending = controller.snapshot()["pending"]
                if pending is not None: controller.fail_delivery(pending["opportunity_id"],reason="infrastructure_failure")
                timing = controller.finalize(reason="infrastructure_failure",execution_status=run["timing_report"]["execution_status"])
                valid = valid and _same(env.snapshot(),run["final_state"]) and "outcomes" not in run
            valid = valid and _same(timing,run["timing_report"]) and replay_timing_report(timing)["partial_trace_consistent"]
            checks.append({"name":"world_timing_action_and_oracle_replay","run_id":run["run_id"],"passed":valid})
        if "paired_initial_world_checks" in report:
            checks.append({"name":"paired_initial_world_paths","passed":_same(report["paired_initial_world_checks"],_pair_world_checks(report["runs"])) and all(c["passed"] is True for c in report["paired_initial_world_checks"])})
        if report["status"] == "complete":
            checks.append({"name":"authoritative_paired_reanalysis","passed":_same(report["analysis"],analyze_timed_resource_runs(report["runs"],p,resamples=report["analysis"]["resamples"]))})
        else:
            checks.append({"name":"incomplete_has_no_estimate","passed":"analysis" not in report})
        consistent = all(c["passed"] for c in checks)
        return {"passed":consistent and report["status"] == "complete","partial_trace_consistent":consistent,"checks":checks,
            "model_calls":0,"scope":"Replays this synthetic code oracle and constructed requests; no provider origin, consumption or historical-mechanism attestation"}
    except (KeyError, ValueError, TypeError, AttributeError, RuntimeError, OSError) as exc:
        return {"passed":False,"partial_trace_consistent":False,"checks":checks,"error_type":type(exc).__name__,"model_calls":0}
