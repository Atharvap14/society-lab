"""Finite quantitative facts for the optional resource study, with zero calls.

The registry checks the exact report, its frozen sources, all recorded actions,
and a fresh numerical analysis before exposing outcome/effect facts. It does not
execute subject callbacks, write a database, or verify model-written prose.
"""
from __future__ import annotations

import copy
import json
from statistics import mean

from .claim_audit import (audit_claims, claims_schema_for_packet, make_claim,
                          select_fact_packet)
from .resource_environment import (check_resource_contract, create_resource_environment,
                                   fingerprint as execution_fingerprint, resource_subject_request)
from .resource_experiments import (CONTEXTS, STUDY_KIND, analyze_resource_runs,
                                  randomize_resource_runs, replay_resource_report,
                                  validate_resource_protocol)
from .store import fingerprint


RESOURCE_METRIC_DEFINITIONS = {
    "task_completion_fraction": "Fraction of eight declared tasks completed by executed counters; unfinished tasks zero, chat claims ignored",
    "independent_completion_fraction": "Fraction of four independent tasks completed by executed counters",
    "computer_completion_fraction": "Fraction of four computer-gated tasks completed by executed counters",
    "focal_completion_fraction": "Fraction of the fixed recipient agent-0's two tasks completed by executed counters",
    "resource_access_grants": "Successful executed exclusive lease grants in the synthetic world; not historical computer access",
    "resource_access_denials": "Valid computer requests without a new grant, including redundant own-lease or already-completed-task requests; not exclusively blocked access",
    "computer_work_steps": "Successful computer-task counter increments under an actual synthetic lease",
    "independent_work_steps": "Successful independent-task counter increments; not measured work quality or clock time",
    "waits": "Executed legal wait actions; not inferred intent or a belief measure",
    "waits_while_independent_pending": "Executed waits with legal unfinished independent work; an unused opportunity, not a global-wait belief",
    "task_specific_blocked_waits": "Executed waits with independent work complete and unfinished computer work under external occupation or another lease; not measured motivation",
    "messages_sent": "Executed recipient-scoped message dispatches; free-text claims remain unverified",
    "steps_used": "Used decision slots in this whole-swarm run, including invalid actions; not elapsed clock time",
    "invalid_actions": "Malformed or illegal actions retained in the outcome and charged a decision slot",
}
RATE_METRICS = frozenset(("task_completion_fraction", "independent_completion_fraction",
                          "computer_completion_fraction", "focal_completion_fraction"))
PRIMARY_PAIR = "comparison/task_reminder/neutral/outcome/task_completion_fraction"
PRIMARY_INTERVAL = "interval/task_reminder_vs_neutral/task_completion_fraction"
PRIMARY_ANALYSIS = "analysis/primary"
LIMITATIONS = (
    "Only typed fact values and generated approved_fact_text are checked. Attached prose is never approved by this registry.",
    "Whole four-agent swarms are randomized trials. Tasks, turns, messages and agents do not increase the independent sample size.",
    "Outcome facts require complete assigned execution, current source-hash agreement, scoped action replay, and numerical recomputation. No failed unit is excluded or replaced.",
    "Replaying recorded actions does not attest their provider origin, archive bytes, absent cross-run memory, immutable model weights, or historical fidelity.",
    "This is a synthetic exclusive-resource analogue with abstract tasks and invented costs/leases; historical global computer exclusivity is unestablished.",
    "The contrast is the fixed recipient's reminder versus the declared neutral note, including any within-swarm interference. It is not an effect relative to receiving no note.",
    "Waiting, denied requests and messages are post-treatment process descriptions, not belief measurements, identified mediators, or evidence of optimal scheduling.",
    "Neutral text can have effects. Word matching does not guarantee matched tokens, inert content, or matched real computational costs.",
    "The randomization p-value tests the sharp no-effect null, not an exact weak zero-average null under heterogeneous effects. Monte Carlo tests have additional simulation resolution.",
    "The bounded interval assumes independent run outcomes and a stable backend. Bootstrap sensitivity may collapse at a floor or ceiling; equality in a tiny sample does not establish equivalence or no effect.",
    "At two runs per arm the smallest attainable two-sided exact p is 1/3. Tiny pilots cannot attain a 0.05 rejection and have wide uncertainty.",
    "Source references, when supplied, identify an exact read-only registered result version. They do not turn motivating chat reports into verified access or task execution.",
)


def _ensure_json_finite(value):
    """Reject non-JSON values and nonfinite floats before hashing or arithmetic."""
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Resource facts require finite JSON source data") from exc


def _equal(left, right):
    # Exact JSON equality also rejects bool/number and int/float substitution.
    return execution_fingerprint(left) == execution_fingerprint(right)


def _is_digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _verify_source_pin(report, report_id, source_ref, source_object):
    if source_ref is None and source_object is None:
        return None
    if not isinstance(source_ref, dict) or set(source_ref) != {"id", "version", "hash"}:
        raise ValueError("Source pin requires exactly id, version and hash")
    if (not isinstance(source_ref["id"], str) or not source_ref["id"] or
            type(source_ref["version"]) is not int or source_ref["version"] < 1 or
            not _is_digest(source_ref["hash"])):
        raise ValueError("Invalid resource source pin")
    if not isinstance(source_object, dict) or source_object.get("kind") != "resource_experiment":
        raise ValueError("Source pin must resolve to a resource_experiment object")
    if any(source_object.get(key) != source_ref[key] for key in source_ref):
        raise ValueError("Source object does not match its pinned version and hash")
    if type(source_object.get("version")) is not int:
        raise ValueError("Source object version must be an integer")
    payload = source_object.get("payload")
    if not isinstance(payload, dict) or fingerprint(payload) != source_ref["hash"]:
        raise ValueError("Pinned resource object payload hash is invalid")
    if report_id is not None and report_id != source_ref["id"]:
        raise ValueError("Report identity differs from the pinned object")
    if any(key not in payload or not _equal(payload[key], value)
           for key, value in report.items() if key != "report_hash"):
        raise ValueError("Pinned result differs from the canonical report")
    if report.get("report_hash") != payload.get("canonical_execution_report_hash"):
        raise ValueError("Pinned result canonical execution hash differs")
    if "registered_hash" in payload and payload["registered_hash"] != fingerprint(report.get("protocol")):
        raise ValueError("Registered protocol hash differs from the embedded frozen protocol")
    return copy.deepcopy(source_ref)


def _execution_checks(report):
    """Additional type, receipt and backend checks around the frozen replay API."""
    p, runs = report["protocol"], report["runs"]
    checks = []
    def check(name, passed):
        checks.append({"name": name, "passed": bool(passed)})
    expected = randomize_resource_runs(p)
    check("all_assigned_units_present", len(runs) == len(expected) and
          all(_equal({key: run.get(key) for key in unit}, unit) for run, unit in zip(runs, expected)))
    check("exact_assignments", _equal(report.get("assignments"), expected))
    backend = report.get("backend", {})
    registered = p["subject_backend"]
    check("registered_backend_settings", isinstance(backend, dict) and
          _equal(backend.get("registered_spec"), registered) and _equal(backend.get("metadata"), registered))
    expected_mode = "scripted_offline_smoke_test" if registered["harness"] == "scripted" else "provided_agent_runner"
    check("recorded_backend_mode", isinstance(backend, dict) and backend.get("mode") == expected_mode)
    check("decision_budget", type(report.get("maximum_subject_calls")) is int and
          report["maximum_subject_calls"] == p["design"]["maximum_subject_calls"])
    check("precall_artifact_declaration", type(report.get("local_protocol_written_before_subject_calls")) is bool and
          (registered["harness"] != "responses" or report["local_protocol_written_before_subject_calls"]))
    for run in runs:
        name = run["run_id"]
        outcomes = run.get("outcomes", {})
        metric_types = isinstance(outcomes, dict) and all(
            ((type(outcomes.get(metric)) in (int, float) and 0 <= outcomes[metric] <= 1)
             if metric in RATE_METRICS else
             (type(outcomes.get(metric)) is int and outcomes[metric] >= 0))
            for metric in RESOURCE_METRIC_DEFINITIONS)
        check("finite_oracle_metric_types/" + name, metric_types)
        env = create_resource_environment(p["environment"], run["environment_seed"])
        check("environment_contract/" + name, _equal(run.get("environment_contract"), check_resource_contract(env)))
        check("context_receipts/" + name, _equal(run.get("actual_context_insertion_recipients"), ["agent-0"]))
        exact_trace = _equal(env.snapshot(), run.get("initial_state"))
        inserted = False
        for turn in run["turns"]:
            actor = env.next_agent
            if actor == "agent-0" and not inserted:
                env.inject_context(actor, p["contexts"][run["context"]]["insertion"])
                inserted = True
            exact_trace = exact_trace and type(turn.get("step")) is int and turn["step"] == env.step_count and actor == turn.get("agent_id")
            exact_trace = exact_trace and _equal(resource_subject_request(env, actor), turn.get("request"))
            actual = env.step(actor, copy.deepcopy(turn["action"]))
            exact_trace = exact_trace and _equal(actual, turn.get("tool_result"))
        check("exact_typed_state_and_oracle_replay/" + name, exact_trace and env.terminal and
              _equal(env.snapshot(), run.get("final_state")) and _equal(env.evaluate(), outcomes))
    return checks


def build_resource_fact_ledger(report, *, report_id=None, source_ref=None, source_object=None):
    """Build only allowlisted facts, bound to exact input and optional Store pin.

    source_ref is {id, version, hash}; source_object is an already retrieved,
    read-only resource_experiment object. No callbacks or database are used.
    Metadata can describe an incomplete report, but numeric outcome and effect
    facts are unavailable unless every execution/reanalysis check passes.
    """
    if not isinstance(report, dict) or report.get("study_kind") != STUDY_KIND:
        raise ValueError("Resource registry accepts only resource-study reports")
    if not isinstance(report.get("runs"), list) or not all(isinstance(run, dict) for run in report["runs"]):
        raise ValueError("Resource report requires a run list")
    _ensure_json_finite(report)
    if source_object is not None:
        _ensure_json_finite(source_object)
    source_pin = _verify_source_pin(report, report_id, source_ref, source_object)
    identities = [run.get("run_id") for run in report["runs"]]
    if any(not isinstance(identity, str) or not identity for identity in identities) or len(set(identities)) != len(identities):
        raise ValueError("Run identities must be present and unique; duplicated rows are not extra trials")
    source_fingerprint = fingerprint(report)
    facts, issues, checks = {}, [], []
    def add(identity, kind, value, scope, definition, *, basis="recorded_metadata", paths=None, metric=None, value_unit="recorded_metric_units"):
        facts[identity] = {"id": identity, "kind": kind, "value": value, "scope": scope,
            "definition": definition, "basis": basis, "source_paths": paths or [], "metric": metric,
            "unit": "whole_swarm_run", "value_unit": value_unit, "validity": "usable",
            "source_fingerprint": source_fingerprint, "rendered_fact": f"{definition}: {value}"}
    add("completion/status", "completion", str(report.get("status", "unknown")), "recorded_execution", "Recorded resource study status", paths=["status"])
    add("trial_count/completed", "trial_count", len(identities), "observed_sample", "Number of stored completed whole-swarm rows; not tasks or turns", paths=["runs"], value_unit="whole_swarms")
    add("completion/source_pin_checked", "completion", source_pin is not None, "recorded_execution", "Exact registered resource-result version and payload hash were checked", basis="read_only_object_pin_check")
    if source_pin:
        for key in ("id", "version", "hash"):
            add("source_pin/" + key, "comparison_identity", source_pin[key], "recorded_execution", "Pinned resource result " + key, basis="read_only_object_pin_check")
    p = report.get("protocol")
    try:
        validate_resource_protocol(p)
        checks.append({"name": "frozen_protocol_and_current_sources", "passed": True})
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        issues.append({"type": "frozen_protocol_or_sources_invalid", "error_type": type(exc).__name__})
        checks.append({"name": "frozen_protocol_and_current_sources", "passed": False})
        p = None
    if p:
        for key in ("unit", "primary_outcome", "operational_definition"):
            add("comparison_identity/" + key, "comparison_identity", p["estimand"][key], "recorded_design", "Frozen resource-study " + key, basis="validated_frozen_protocol", paths=["protocol/estimand/" + key])
        for key in ("treatment", "control"):
            add("comparison_identity/primary/" + key, "comparison_identity", p["estimand"][key], "recorded_design", "Frozen primary contrast " + key, basis="validated_frozen_protocol", paths=["protocol/estimand/" + key])
        add("comparison_identity/intervention/recipient", "comparison_identity", "agent-0", "recorded_design", "Fixed private-note recipient; peer outcomes can change through within-run interference", basis="validated_frozen_protocol", paths=["protocol/intervention/recipients"])
        resolution = p["pre_execution_test_resolution"]
        for key in ("minimum_two_sided_p", "exact_minimum_fraction"):
            add("analysis/primary/test_resolution/" + key, "analysis_value", resolution[key], "recorded_design", "Theoretical minimum two-sided exact randomization p: " + key + "; ties may make the attained minimum larger", basis="validated_balanced_assignment_count", paths=["protocol/pre_execution_test_resolution/" + key])
        add("analysis/primary/test_resolution/can_attain_p_below_0.05", "analysis_value", resolution["minimum_two_sided_p"] < .05, "recorded_design", "This balanced design can theoretically attain a two-sided exact p below 0.05; not a power calculation or observed rejection", basis="validated_balanced_assignment_count")
        backend = report.get("backend", {})
        for key, value in (("mode", backend.get("mode")), ("model", p["subject_backend"]["model"]), ("harness", p["subject_backend"]["harness"])):
            if isinstance(value, str):
                add("backend/" + key, "backend", value, "recorded_execution", "Recorded backend " + key + "; not independent provider attestation or immutable weights", paths=["backend", "protocol/subject_backend"])
        assignments = report.get("assignments")
        if isinstance(assignments, list):
            add("trial_count/assigned", "trial_count", len(assignments), "recorded_design", "Number of recorded assigned whole-swarm units", paths=["assignments"], value_unit="whole_swarms")
        if report.get("status") == "complete":
            try:
                replay = replay_resource_report(copy.deepcopy(report))
                checks.extend(replay["checks"])
                checks.extend(_execution_checks(report))
                # Independent recomputation additionally uses exact JSON types;
                # Python equality alone would accept True as a saved 1.0.
                recomputed = analyze_resource_runs(report["runs"], p, resamples=report["analysis"]["resamples"])
                checks.append({"name": "exact_numerical_recomputation", "passed": _equal(recomputed, report["analysis"])})
            except (KeyError, TypeError, ValueError, RuntimeError, AttributeError) as exc:
                issues.append({"type": "resource_replay_or_reanalysis_unavailable", "error_type": type(exc).__name__})
                checks.append({"name": "complete_replay_and_reanalysis", "passed": False})
            for check in checks:
                if check["passed"] is not True:
                    issues.append({"type": "resource_execution_check_failed", "check": check["name"], **({"run_id": check["run_id"]} if "run_id" in check else {})})
        else:
            issues.append({"type": "resource_report_incomplete", "status": report.get("status")})
    verified = bool(p and report.get("status") == "complete" and checks and all(c["passed"] is True for c in checks) and not issues)
    add("replay/recorded_actions/pass", "replay", verified, "recorded_execution", "Every recorded scoped action, oracle outcome, frozen source and fresh numerical analysis passed zero-call validation", basis="resource_recorded_action_replay_and_numeric_recomputation", paths=["runs", "protocol", "analysis"])
    all_present = next((c["passed"] for c in checks if c["name"] == "all_assigned_units_present"), False)
    add("completion/all_assigned_units_present", "completion", all_present, "recorded_execution", "Every frozen assigned whole-swarm unit has its matching complete run record", basis="exact_assignment_run_check", paths=["assignments", "runs"])
    if verified:
        _add_numeric_facts(add, report, recomputed)
    return {"schema_version": "1.0", "study_kind": STUDY_KIND, "source_fingerprint": source_fingerprint,
        "canonical_execution_report_hash": report.get("report_hash"), "source_ref": source_pin,
        "report_id": report_id or (source_pin or {}).get("id") or report.get("experiment_id"),
        "facts": facts, "issues": issues, "verification_checks": checks,
        "quantitative_facts_available": verified, "model_calls": 0, "prose_verification": "not_performed",
        "limitations": list(LIMITATIONS)}


def _add_numeric_facts(add, report, recomputed):
    groups = {context: [run for run in report["runs"] if run["context"] == context] for context in CONTEXTS}
    for context, group in groups.items():
        add("trial_count/group/" + context, "trial_count", len(group), "observed_sample", "Complete randomized whole-swarm units in " + context, basis="validated_assigned_run_rows", paths=["runs"], value_unit="whole_swarms")
        for metric, definition in RESOURCE_METRIC_DEFINITIONS.items():
            values = [run["outcomes"][metric] for run in group]
            for statistic, value in (("sum", sum(values)), ("mean", mean(values))):
                add(f"arm_metric/{context}/outcome/{metric}/{statistic}", "arm_metric", value, "observed_sample", f"{context}: {statistic} of whole-swarm {definition}" + ("; sum of run-level fractions is not a task count" if statistic == "sum" and metric in RATE_METRICS else ""), basis="replayed_code_oracle_outcomes", paths=["runs"], metric=metric)
        completed = sum(sum(sum(v.values()) for v in run["outcomes"]["per_agent_completed"].values()) for run in group)
        for label, value in (("tasks_assigned", 8 * len(group)), ("executed_tasks_completed", completed)):
            add(f"arm_metric/{context}/task_inventory/{label}", "arm_metric", value, "observed_sample", f"{context}: {label}; tasks are outcomes, not independent trials", basis="replayed_code_oracle_outcomes", paths=["runs/outcomes/per_agent_completed"], value_unit="declared_tasks")
        values = [run["outcomes"]["task_completion_fraction"] for run in group]
        for label, value in (("all_at_floor", all(v == 0 for v in values)), ("all_at_ceiling", all(v == 1 for v in values))):
            add(f"arm_metric/{context}/outcome/task_completion_fraction/{label}", "arm_metric", value, "observed_sample", f"{context}: sampled whole-swarm outcomes {label}; no general capability or equivalence claim", basis="replayed_code_oracle_outcomes", paths=["runs/outcomes/task_completion_fraction"])
    effect = recomputed["primary_effect"]
    difference = effect["difference"]
    for suffix, kind, value, definition, unit in (
        ("mean_direction", "comparison_direction", "equal" if difference == 0 else "higher" if difference > 0 else "lower", "Observed mean completion direction: task_reminder versus neutral; equal does not establish equivalence", "direction"),
        ("mean_difference", "comparison_difference", difference, "Observed whole-swarm mean completion difference: task_reminder minus neutral", "completion_fraction"),
        ("mean_difference_percentage_points", "comparison_difference", 100 * difference, "Observed completion difference in percentage points: task_reminder minus neutral; not a relative percentage change", "percentage_points")):
        add(PRIMARY_PAIR + "/" + suffix, kind, value, "observed_sample", definition, basis="recomputed_all_assigned_whole_swarm_means", paths=["runs"], metric="task_completion_fraction", value_unit=unit)
    interval = effect["ci95"]
    for label, value in zip(("lower", "upper"), interval):
        add(PRIMARY_INTERVAL + "/" + label, "interval_bound", value, "recorded_analysis", "Recomputed bounded independent-run 95% completion-effect interval " + label, basis="fresh_numerical_recomputation", paths=["analysis/primary_effect/ci95"], value_unit="completion_fraction")
    add(PRIMARY_INTERVAL + "/excludes_zero", "interval_zero", interval[0] > 0 or interval[1] < 0, "recorded_analysis", "Recomputed bounded 95% interval excludes zero; including zero does not establish no effect", basis="fresh_numerical_recomputation", paths=["analysis/primary_effect/ci95"])
    for key in ("p_two_sided", "test_method", "test_samples", "interval_method", "interval_alpha", "bootstrap_resamples"):
        add(PRIMARY_ANALYSIS + "/" + key, "analysis_value", effect[key], "recorded_analysis", "Recomputed registered primary " + key + "; sharp no-effect randomization null and independent-run interval assumptions remain", basis="fresh_numerical_recomputation", paths=["analysis/primary_effect/" + key])
    add(PRIMARY_ANALYSIS + "/family_size", "analysis_value", 1, "recorded_design", "One registered primary contrast; process metrics are descriptive", basis="validated_frozen_protocol")
    for label, value in zip(("lower", "upper"), effect["bootstrap_ci95"]):
        add("interval/bootstrap_sensitivity/task_completion_fraction/" + label, "interval_bound", value, "recorded_analysis", "Recomputed bootstrap sensitivity bound " + label + "; may collapse at floor/ceiling and is not the conservative primary interval", basis="fresh_numerical_recomputation", paths=["analysis/primary_effect/bootstrap_ci95"])
    add(PRIMARY_ANALYSIS + "/bootstrap_degenerate", "analysis_value", effect["bootstrap_ci95"][0] == effect["bootstrap_ci95"][1], "recorded_analysis", "Run bootstrap sensitivity interval collapsed to one value; does not establish equivalence or certainty", basis="fresh_numerical_recomputation", paths=["analysis/primary_effect/bootstrap_ci95"])


def default_resource_fact_ids(ledger, *, max_facts=24):
    """Select a bounded interpretation packet without converting tasks to trials."""
    if type(max_facts) is not int or not 1 <= max_facts <= 100:
        raise ValueError("Fact cap must be an integer from 1 to 100")
    ordered = ["completion/status", "trial_count/completed", "comparison_identity/unit", "backend/mode",
        "replay/recorded_actions/pass", "completion/all_assigned_units_present", "completion/source_pin_checked",
        "comparison_identity/primary_outcome", "comparison_identity/primary/treatment", "comparison_identity/primary/control",
        "trial_count/group/task_reminder", "trial_count/group/neutral",
        "arm_metric/task_reminder/outcome/task_completion_fraction/mean", "arm_metric/neutral/outcome/task_completion_fraction/mean",
        PRIMARY_PAIR + "/mean_direction", PRIMARY_PAIR + "/mean_difference_percentage_points",
        PRIMARY_INTERVAL + "/lower", PRIMARY_INTERVAL + "/upper", PRIMARY_INTERVAL + "/excludes_zero",
        PRIMARY_ANALYSIS + "/p_two_sided", "analysis/primary/test_resolution/minimum_two_sided_p",
        "analysis/primary/test_resolution/can_attain_p_below_0.05", PRIMARY_ANALYSIS + "/bootstrap_degenerate", "backend/model"]
    return [identity for identity in ordered if identity in ledger["facts"]][:max_facts]
