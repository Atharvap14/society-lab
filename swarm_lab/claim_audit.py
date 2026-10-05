"""Finite, auditable claims about recorded experiments; no language entailment.

Only explicit fact references and typed expected values are checked. A supported
fact does not validate an accompanying model-written sentence or causal story.
This module never calls a provider, mutates a report, or promotes a theory.
"""
from __future__ import annotations

from collections import defaultdict
import copy
import math
from statistics import mean
from urllib.parse import quote

from .store import clean, fingerprint


CLAIM_KINDS = ("trial_count", "arm_metric", "comparison_direction", "comparison_difference",
               "interval_zero", "interval_bound", "analysis_value", "comparison_identity", "completion", "backend",
               "replay", "proposed_mechanism", "free_prose")
SCOPES = ("observed_sample", "recorded_design", "recorded_analysis", "recorded_execution",
          "proposed_mechanism", "registered_environment", "historical", "generalized")
CLAIM_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["id", "kind", "fact_id", "expected", "scope", "statement", "source_fingerprint"],
    "properties": {
        "id": {"type": "string", "minLength": 1, "maxLength": 200},
        "kind": {"type": "string", "enum": list(CLAIM_KINDS)},
        "fact_id": {"type": ["string", "null"], "maxLength": 600},
        "expected": {"type": ["number", "string", "boolean", "null"]},
        "scope": {"type": "string", "enum": list(SCOPES)},
        "statement": {"type": "string", "maxLength": 6000},
        "source_fingerprint": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
    },
}
CLAIMS_SCHEMA = {"type": "object", "properties": {
    "claims": {"type": "array", "items": CLAIM_SCHEMA, "maxItems": 100}},
    "required": ["claims"], "additionalProperties": False}

OUTCOME_DEFINITIONS = {
    "success": "Actual correct shared-artifact publication, scored by the recorded oracle",
    "incorrect_publication": "Actual incorrect shared-artifact publication",
    "published": "An artifact was actually published",
    "inspected_publication": "Any agent inspected the exact artifact version later published; not positive verification or publisher inspection",
    "steps_used": "Action slots used by the independent team/network",
    "inspections": "Successful inspection actions recorded by the environment",
    "messages_sent": "Messages sent by the team/network",
    "invalid_actions": "Invalid actions retained in the assigned outcome",
    "initial_valid": "Artifact initially matched the task requirements",
    "mean_accuracy": "Mean of four recorded verdict-correctness indicators within one network; the four agents are not independent trials",
    "focal_accuracy": "Correctness of the focal recipient verdict within one network",
    "completion_rate": "Fraction of network subjects submitting a verdict",
    "mean_independent_sources_at_verdict": "Mean distinct original source IDs available at network verdicts",
    "duplicate_source_reception_fraction": "Recorded fraction of duplicate-source reception",
}
TRACE_DEFINITIONS = {
    "publisher_inspected_any": "Publisher successfully inspected some artifact version before publication",
    "publisher_inspected_published_version": "Publisher successfully inspected the exact version later published",
    "any_agent_inspected_published_version": "Some agent successfully inspected the exact version later published",
    "repair_before_publication": "At least one permitted successful repair occurred before publication",
}
RATE_METRICS = {"success", "incorrect_publication", "published", "inspected_publication", "initial_valid",
                "mean_accuracy", "focal_accuracy", "completion_rate", "duplicate_source_reception_fraction",
                "all_originals_visible_fraction", "all_originals_at_submission_fraction"}
COMPLEMENTARY_OUTCOME_DEFINITIONS = {
    "mean_accuracy": "Mean of four exact submitted modular-total correctness indicators within one network; missing submissions score zero and agents are not independent trials",
    "focal_accuracy": "Exact modular-total correctness of the focal recipient; missing submission scores zero",
    "completion_rate": "Fraction of four network subjects making a valid modular-total submission",
    "messages_sent": "Executed message dispatch actions; neighbor multicast consumes one action and may deliver to several recipients",
    "message_deliveries": "Executed recipient deliveries; several deliveries can originate from one multicast dispatch",
    "mean_unique_originals_visible": "Mean canonical original-fragment inventory at final state; not measured latent knowledge",
    "mean_unique_originals_at_submission": "Mean canonical original-fragment inventory at first valid submission; missing submissions contribute zero, and free-text information is not measured",
    "all_originals_visible_fraction": "Fraction of subjects with all four canonical original fragments in final inventory; not measured latent knowledge",
    "all_originals_at_submission_fraction": "Fraction of subjects with all four canonical originals at first valid submission; missing submissions contribute zero, not identified mediation",
    "relay_attachment_events": "Recorded forwarded canonical-attachment delivery events; not independent measurements or trials",
}


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_claim(claim):
    """Validate the finite syntax; report-specific support is checked separately."""
    if not isinstance(claim, dict) or set(claim) != set(CLAIM_SCHEMA["required"]):
        raise ValueError("Claim must contain exactly the finite schema fields")
    if not isinstance(claim["id"], str) or not 1 <= len(claim["id"]) <= 200:
        raise ValueError("Invalid claim id")
    if claim["kind"] not in CLAIM_KINDS or claim["scope"] not in SCOPES:
        raise ValueError("Unknown claim kind or scope")
    if not isinstance(claim["statement"], str) or len(claim["statement"]) > 6000:
        raise ValueError("Invalid statement")
    digest = claim["source_fingerprint"]
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("Invalid source fingerprint")
    if claim["kind"] in ("free_prose", "proposed_mechanism"):
        if claim["fact_id"] is not None or claim["expected"] is not None:
            raise ValueError("Unverified prose/mechanisms cannot masquerade as executable facts")
        if claim["kind"] == "proposed_mechanism" and claim["scope"] != "proposed_mechanism":
            raise ValueError("A proposed mechanism must keep its proposed scope")
    else:
        if not isinstance(claim["fact_id"], str) or not 1 <= len(claim["fact_id"]) <= 600:
            raise ValueError("Executable claim needs an explicit fact id")
        value = claim["expected"]
        if value is None or not (isinstance(value, (str, bool)) or finite_number(value)):
            raise ValueError("Executable claim needs a finite typed expected value")
    return True


def _component(value):
    return quote(str(value), safe="-_|.")


def _group(run):
    if "arm" in run:
        return str(run["arm"])
    if "topology" in run and "context" in run:
        return f'{run["topology"]}|{run["context"]}'
    raise ValueError("Run has no supported assigned arm or factorial cell")


def _trace_metrics(run):
    """Use successful executed tools and exact versions, not narrated claims."""
    if not isinstance(run.get("turns"), list) or not isinstance(run.get("final_state"), dict):
        return None
    published = run["final_state"].get("published")
    if published is None:
        # A network has verdicts rather than this artifact publication mechanism.
        if "published" not in run["final_state"]:
            return None
        return {key: 0 for key in TRACE_DEFINITIONS}
    publisher_turns = [t for t in run["turns"] if t.get("action", {}).get("action") == "publish_artifact"
                       and t.get("tool_result", {}).get("ok") is True]
    if len(publisher_turns) != 1 or not isinstance(published.get("version"), int):
        return None
    publisher = publisher_turns[0].get("agent_id")
    publication_step = publisher_turns[0].get("step")
    if not isinstance(publication_step, int):
        return None
    earlier = [t for t in run["turns"] if isinstance(t.get("step"), int) and t["step"] < publication_step]
    inspections = [t for t in earlier if t.get("action", {}).get("action") == "inspect_artifact"
                   and t.get("tool_result", {}).get("ok") is True]
    # The present tool contract returns version at the top level. A missing
    # version must not be turned into evidence of no current-version inspection.
    if any(not isinstance(t["tool_result"].get("version"), int) for t in inspections):
        return None
    own = [t for t in inspections if t.get("agent_id") == publisher]
    version = published["version"]
    return {"publisher_inspected_any": int(bool(own)),
            "publisher_inspected_published_version": int(any(t["tool_result"]["version"] == version for t in own)),
            "any_agent_inspected_published_version": int(any(t["tool_result"]["version"] == version for t in inspections)),
            "repair_before_publication": int(any(t.get("action", {}).get("action") == "repair_artifact" and
                                                 t.get("tool_result", {}).get("ok") is True for t in earlier))}


def build_fact_ledger(report, *, report_id=None, replay_check=None):
    """Return facts bound to an exact input fingerprint, with zero provider calls.

    replay_check is an optional trusted *offline callable* receiving the exact
    report and returning a replay verdict. Do not pass model-written replay prose.
    Scope 'recorded_analysis' checks saved interval metadata and effect consistency;
    it does not independently prove statistical assumptions or recompute intervals.
    """
    if not isinstance(report, dict) or not isinstance(report.get("runs", []), list):
        raise ValueError("Report must be a dictionary with a run list")
    if replay_check is not None and not callable(replay_check):
        raise ValueError("Replay checks must be trusted offline callables, not supplied verdict objects")
    source_fingerprint = fingerprint(report)
    runs = report.get("runs", [])
    ids = [run.get("run_id") for run in runs]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("Run identities must be present and unique; repeated rows are not additional trials")
    complementary = report.get("study_kind") == "complementary_information_factorial"
    unit = "whole_network_run" if report.get("study_kind") in ("provenance_diffusion_factorial", "complementary_information_factorial") else report.get("protocol", {}).get("estimand", {}).get("unit", "whole_swarm_run")
    facts, issues, group_runs = {}, [], defaultdict(list)

    def add(identity, kind, value, scope, definition, *, basis, paths, metric=None, unit_label=None, validity="usable"):
        facts[identity] = {"id": identity, "kind": kind, "value": value, "scope": scope,
                           "definition": definition, "basis": basis, "source_paths": paths,
                           "metric": metric, "unit": unit, "value_unit": unit_label or "recorded_metric_units", "validity": validity,
                           "source_fingerprint": source_fingerprint,
                           "rendered_fact": f"{definition}: {value}"}

    add("completion/status", "completion", report.get("status", "unknown"), "recorded_execution",
        "Recorded experiment status", basis="recorded_metadata", paths=["status"])
    add("trial_count/completed", "trial_count", len(runs), "observed_sample",
        "Number of stored completed experimental units", basis="run_rows", paths=["runs"])
    if isinstance(report.get("assignments"), list):
        assignments = report["assignments"]
        by_id = {r["run_id"]: r for r in runs}
        assigned_ids = [a.get("run_id") for a in assignments if isinstance(a, dict)]
        all_present = (len(assigned_ids) == len(assignments) == len(runs)
                       and len(set(assigned_ids)) == len(assigned_ids)
                       and set(assigned_ids) == set(by_id)
                       and all(all(by_id[a["run_id"]].get(key) == value for key, value in a.items()) for a in assignments))
        add("completion/all_assigned_units_present", "completion", all_present, "recorded_execution",
            "All recorded assignments have matching completed run records", basis="assignment_run_identity_check",
            paths=["assignments", "runs"])
        if report.get("status") == "complete" and not all_present:
            issues.append({"type": "complete_status_with_missing_or_mismatched_assignments"})
    for run in runs:
        group_runs[_group(run)].append(run)
    for group, selected in sorted(group_runs.items()):
        add(f"trial_count/group/{_component(group)}", "trial_count", len(selected), "observed_sample",
            f"Stored experimental units in {group}", basis="run_rows", paths=[f"runs/{r['run_id']}" for r in selected])
    backend = report.get("backend", {})
    for key, value in (("mode", backend.get("mode")), ("model", backend.get("metadata", {}).get("model")),
                       ("harness", backend.get("metadata", {}).get("harness"))):
        if isinstance(value, str):
            add(f"backend/{key}", "backend", value, "recorded_execution", f"Recorded backend {key}",
                basis="recorded_metadata_not_independent_provider_attestation",
                paths=[f"backend/{key}" if key == "mode" else f"backend/metadata/{key}"])
    protocol = report.get("protocol", {})
    estimand = protocol.get("estimand", {})
    add("comparison_identity/unit", "comparison_identity", unit, "recorded_design",
        "Recorded independent experimental unit", basis="protocol", paths=["protocol/estimand"])
    for key in ("primary_outcome",):
        if isinstance(estimand.get(key), str):
            add(f"comparison_identity/{key}", "comparison_identity", estimand[key], "recorded_design",
                "Recorded primary outcome", basis="protocol", paths=[f"protocol/estimand/{key}"])
    if isinstance(estimand.get("operational_definition"), str):
        add("comparison_identity/operational_definition", "comparison_identity", estimand["operational_definition"],
            "recorded_design", "Recorded primary-outcome operational definition", basis="protocol",
            paths=["protocol/estimand/operational_definition"])
    contrast = estimand.get("primary_contrast")
    if isinstance(contrast, list) and len(contrast) == 2 and all(isinstance(x, str) for x in contrast):
        for key, value in zip(("treatment", "control"), contrast):
            add(f"comparison_identity/primary/{key}", "comparison_identity", value, "recorded_design",
                f"Recorded primary contrast {key}", basis="protocol", paths=["protocol/estimand/primary_contrast"])
    for contrast in estimand.get("primary_contrasts", []):
        if isinstance(contrast, dict) and isinstance(contrast.get("factor"), str):
            for key in ("treatment", "control", "stratify_by"):
                if isinstance(contrast.get(key), str):
                    add(f"comparison_identity/{_component(contrast['factor'])}/{key}", "comparison_identity", contrast[key],
                        "recorded_design", f"Recorded {contrast['factor']} contrast {key}", basis="protocol",
                        paths=["protocol/estimand/primary_contrasts"])

    measured = {}
    trace_rows = {r["run_id"]: _trace_metrics(r) for r in runs}
    outcome_definitions = {**OUTCOME_DEFINITIONS, **COMPLEMENTARY_OUTCOME_DEFINITIONS} if complementary else OUTCOME_DEFINITIONS
    for namespace, definitions in (("outcome", outcome_definitions), ("trajectory", TRACE_DEFINITIONS)):
        for metric, definition in definitions.items():
            for group, selected in sorted(group_runs.items()):
                values = [r.get("outcomes", {}).get(metric) if namespace == "outcome" else
                          (trace_rows[r["run_id"]] or {}).get(metric) for r in selected]
                if not all(finite_number(v) for v in values):
                    continue
                # Outcomes are not post-treatment exclusions: a partial metric
                # is unavailable for the whole group, not averaged selectively.
                stats = {"sum": sum(values), "mean": mean(values)}
                measured[(group, namespace, metric)] = stats
                paths = [f"runs/{r['run_id']}/" + (f"outcomes/{metric}" if namespace == "outcome" else "turns,final_state") for r in selected]
                validity = "usable"
                if namespace == "outcome" and metric == "inspected_publication":
                    conflicting = [r["run_id"] for r in selected if trace_rows[r["run_id"]] is not None and
                                   trace_rows[r["run_id"]]["any_agent_inspected_published_version"] != r["outcomes"][metric]]
                    if conflicting:
                        validity = "data_conflict"
                        issues.append({"type": "inspection_oracle_trace_conflict", "runs": conflicting})
                for statistic, value in stats.items():
                    add(f"arm_metric/{_component(group)}/{namespace}/{metric}/{statistic}", "arm_metric", value,
                        "observed_sample", f"{group}: {statistic} of {definition}", basis="executed_outcomes" if namespace == "outcome" else "successful_actor_version_tools_posthoc",
                        paths=paths, metric=metric, validity=validity)
    if report.get("status") == "complete":
        for (treatment, namespace, metric), stats in measured.items():
            for control in sorted(group_runs):
                if treatment == control or (control, namespace, metric) not in measured:
                    continue
                other = measured[(control, namespace, metric)]
                for statistic in ("mean", "sum"):
                    difference = stats[statistic] - other[statistic]
                    direction = "equal" if math.isclose(difference, 0, abs_tol=1e-12) else "higher" if difference > 0 else "lower"
                    path = f"comparison/{_component(treatment)}/{_component(control)}/{namespace}/{metric}/{statistic}"
                    origin = [f"arm_metric/{_component(g)}/{namespace}/{metric}/{statistic}" for g in (treatment, control)]
                    validity = "usable" if all(facts[x]["validity"] == "usable" for x in origin) else "data_conflict"
                    add(path + "_direction", "comparison_direction", direction, "observed_sample",
                        f"Observed {statistic} {namespace}/{metric} direction: {treatment} versus {control}",
                        basis="arithmetic_from_all_assigned_run_rows", paths=origin, metric=metric, validity=validity)
                    add(path + "_difference", "comparison_difference", difference, "observed_sample",
                        f"Observed {statistic} {namespace}/{metric} difference: {treatment} minus {control}",
                        basis="arithmetic_from_all_assigned_run_rows", paths=origin, metric=metric, validity=validity)
                    if statistic == "mean" and metric in RATE_METRICS:
                        add(path + "_difference_percentage_points", "comparison_difference", difference * 100,
                            "observed_sample", f"Observed {namespace}/{metric} difference in percentage points: {treatment} minus {control}",
                            basis="arithmetic_from_all_assigned_run_rows", paths=origin, metric=metric,
                            unit_label="percentage_points", validity=validity)

        for name, outcomes in report.get("analysis", {}).get("effects", {}).items():
            if "_vs_" not in name or not isinstance(outcomes, dict):
                continue
            treatment, control = name.split("_vs_", 1)
            for metric, effect in outcomes.items():
                if not isinstance(effect, dict):
                    continue
                pair = [(g, "outcome", metric) for g in (treatment, control)]
                if not all(key in measured for key in pair):
                    continue
                actual = [measured[key]["mean"] for key in pair]
                expected = [effect.get("mean_treatment"), effect.get("mean_control")]
                consistent = all(finite_number(v) for v in expected) and all(math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9) for a, b in zip(actual, expected))
                consistent &= finite_number(effect.get("difference")) and math.isclose(actual[0] - actual[1], effect["difference"], rel_tol=1e-9, abs_tol=1e-9)
                consistent &= effect.get("n_treatment") == len(group_runs[treatment]) and effect.get("n_control") == len(group_runs[control]) and effect.get("unit") == unit
                if not consistent:
                    issues.append({"type": "saved_effect_disagrees_with_run_rows", "effect": name, "metric": metric})
                    continue
                _interval_facts(add, effect, f"interval/{_component(name)}/{metric}", [f"analysis/effects/{name}/{metric}"], metric, issues)

        # Factorial analyses use whole networks. Validate their saved marginal
        # means against equal averaging across the observed other-factor cells.
        for effect in report.get("analysis", {}).get("factor_effects", []):
            if not isinstance(effect, dict):
                continue
            factor, other = effect.get("factor"), effect.get("stratify_by")
            if factor not in ("topology", "context") or other not in ("topology", "context") or factor == other:
                continue
            treatment, control, metric = effect.get("treatment"), effect.get("control"), effect.get("outcome")
            strata = sorted({r.get(other) for r in runs if isinstance(r.get(other), str)})
            marginal, counts = [], []
            for assigned in (treatment, control):
                cells = [[r.get("outcomes", {}).get(metric) for r in runs if r.get(factor) == assigned and r.get(other) == level] for level in strata]
                if not cells or any(not cell or not all(finite_number(x) for x in cell) for cell in cells):
                    break
                marginal.append(mean(mean(cell) for cell in cells))
                counts.append(sum(len(cell) for cell in cells))
            if len(marginal) != 2:
                continue
            consistent = all(finite_number(effect.get(k)) and math.isclose(effect[k], value, abs_tol=1e-9, rel_tol=1e-9) for k, value in zip(("mean_treatment", "mean_control", "difference"), (marginal[0], marginal[1], marginal[0] - marginal[1])))
            consistent &= effect.get("n_treatment_networks") == counts[0] and effect.get("n_control_networks") == counts[1] and effect.get("unit") == unit
            if not consistent:
                issues.append({"type": "saved_factor_effect_disagrees_with_run_rows", "factor": factor})
                continue
            _interval_facts(add, effect, f"interval/factor_{factor}/{_component(metric)}", ["analysis/factor_effects"], metric, issues)
            add(f"factor_direction/{factor}/{_component(metric)}", "comparison_direction",
                "equal" if math.isclose(marginal[0], marginal[1], abs_tol=1e-12) else "higher" if marginal[0] > marginal[1] else "lower",
                "observed_sample", f"Observed {metric} marginal direction: {treatment} versus {control}, equally averaging {other}",
                basis="equal_cell_average_of_executed_network_outcomes", paths=["runs"], metric=metric)

    if replay_check is not None:
        try:
            verdict = replay_check(copy.deepcopy(report))
            if not isinstance(verdict, dict) or not isinstance(verdict.get("passed"), bool) or verdict.get("model_calls") != 0:
                raise ValueError("Replay verdict must explicitly report a boolean pass and zero model calls")
            if verdict.get("runs_checked") != len(runs):
                raise ValueError("Replay unit count does not match this exact report")
            add("replay/recorded_actions/pass", "replay", verdict["passed"], "recorded_execution",
                "Trusted offline recorded-action replay passed for this exact input", basis="trusted_offline_callable",
                paths=["runs", "protocol"])
        except Exception as exc:
            issues.append({"type": "replay_unavailable", "error_type": type(exc).__name__})
    return clean({"schema_version": "1.0", "source_fingerprint": source_fingerprint,
                  "report_id": report_id or report.get("experiment_id"), "facts": facts, "issues": issues,
                  "model_calls": 0, "prose_verification": "not_performed",
                  "limitations": ["Supported refers to a typed fact against this recorded report, not entailment of any attached prose.",
                                  "Observed differences are not verified causal mechanisms or historical/generalized findings.",
                                  "Recorded backend labels are not independent attestation of provider execution.",
                                  "Saved interval bounds are checked for internal consistency; interval computation, randomization validity, and statistical assumptions require separate audit.",
                                  "Trajectory measures are exploratory, actor/version-resolved, and not identified mediators."]})


def _interval_facts(add, effect, identity, paths, metric, issues):
    interval = effect.get("ci95")
    if not isinstance(interval, list) or len(interval) != 2 or not all(finite_number(x) for x in interval) or interval[0] > interval[1]:
        issues.append({"type": "invalid_saved_interval", "effect": identity})
        return
    add(identity + "/excludes_zero", "interval_zero", interval[0] > 0 or interval[1] < 0,
        "recorded_analysis", "Saved 95% interval excludes zero", basis="consistent_saved_analysis",
        paths=paths, metric=metric)
    for label, value in zip(("lower", "upper"), interval):
        add(identity + "/" + label, "interval_bound", value, "recorded_analysis", f"Saved 95% interval {label} bound",
            basis="consistent_saved_analysis", paths=paths, metric=metric)
    for label in ("p_two_sided", "p_holm_primary_family"):
        if finite_number(effect.get(label)) and 0 <= effect[label] <= 1:
            add(identity + "/" + label, "analysis_value", effect[label], "recorded_analysis",
                f"Saved {label}; not independently recalculated by this ledger", basis="consistent_saved_analysis",
                paths=paths, metric=metric)


def _same(expected, actual):
    if isinstance(expected, bool) or isinstance(actual, bool):
        return isinstance(expected, bool) and isinstance(actual, bool) and expected == actual
    if finite_number(expected) and finite_number(actual):
        return math.isclose(expected, actual, rel_tol=1e-9, abs_tol=1e-9)
    return type(expected) is type(actual) and expected == actual


def make_claim(ledger, fact_id, expected, *, claim_id=None, statement=""):
    """Convenience for tests/explicit UI claims; it does not approve a value."""
    fact = ledger["facts"][fact_id]
    return {"id": claim_id or fact_id, "kind": fact["kind"], "fact_id": fact_id, "expected": expected,
            "scope": fact["scope"], "statement": statement, "source_fingerprint": ledger["source_fingerprint"]}


def select_fact_packet(ledger, fact_ids, *, max_facts=50):
    """Bound the facts supplied to a research agent; full ledger remains local."""
    if not isinstance(max_facts, int) or isinstance(max_facts, bool) or not 1 <= max_facts <= 100:
        raise ValueError("Fact packet cap must be an integer from 1 to 100")
    if not isinstance(fact_ids, list) or not 1 <= len(fact_ids) <= max_facts or not all(isinstance(i, str) for i in fact_ids):
        raise ValueError("Provide an explicit nonempty fact-id list within the packet cap")
    if len(set(fact_ids)) != len(fact_ids):
        raise ValueError("Duplicate fact ids in packet")
    missing = set(fact_ids) - set(ledger["facts"])
    if missing:
        raise ValueError("Unavailable facts requested: " + ", ".join(sorted(missing)))
    return copy.deepcopy({"source_fingerprint": ledger["source_fingerprint"], "report_id": ledger.get("report_id"),
                          "facts": {identity: ledger["facts"][identity] for identity in fact_ids},
                          "issues": ledger.get("issues", []), "limitations": ledger["limitations"],
                          "prose_verification": "not_performed"})


def default_fact_ids(ledger):
    """At most 24 facts protecting the most material interpretation boundaries.

    This shortlist is for the current artifact and network study families. It
    does not claim that every relevant scientific fact fits into the packet.
    Explicit caller selection remains available for other evaluation questions.
    """
    facts, chosen = ledger["facts"], []
    def choose(identity):
        if identity in facts and identity not in chosen and len(chosen) < 24:
            chosen.append(identity)
    def value(identity, default=None):
        return facts.get(identity, {}).get("value", default)
    for identity in ("completion/status", "trial_count/completed", "comparison_identity/unit", "backend/mode"):
        choose(identity)
    outcome = value("comparison_identity/primary_outcome", "success")
    group_prefix = "trial_count/group/"
    groups = sorted(identity[len(group_prefix):] for identity in facts if identity.startswith(group_prefix))
    if value("comparison_identity/unit") == "whole_network_run":
        choose("comparison_identity/primary_outcome")
        for group in groups[:4]:
            choose(group_prefix + group)
        for group in groups[:4]:
            choose(f"arm_metric/{group}/outcome/{_component(outcome)}/mean")
        for factor in ("context", "topology"):
            for key in ("treatment", "control", "stratify_by"):
                choose(f"comparison_identity/{factor}/{key}")
            choose(f"factor_direction/{factor}/{_component(outcome)}")
            choose(f"interval/factor_{factor}/{_component(outcome)}/excludes_zero")
        choose("replay/recorded_actions/pass")
        choose("backend/model")
    else:
        treatment = value("comparison_identity/primary/treatment")
        control = value("comparison_identity/primary/control")
        choose("comparison_identity/primary/treatment")
        choose("comparison_identity/primary/control")
        prioritized = []
        for group in (treatment, control, "baseline"):
            if isinstance(group, str) and _component(group) in groups and _component(group) not in prioritized:
                prioritized.append(_component(group))
        prioritized.extend(group for group in groups if group not in prioritized)
        for group in prioritized[:3]:
            choose(group_prefix + group)
        for group in prioritized[:3]:
            choose(f"arm_metric/{group}/outcome/{_component(outcome)}/sum")
        if isinstance(treatment, str) and isinstance(control, str):
            pair = f"comparison/{_component(treatment)}/{_component(control)}"
            choose(f"{pair}/outcome/{_component(outcome)}/mean_direction")
            choose(f"comparison/{_component(treatment)}/baseline/outcome/{_component(outcome)}/mean_direction")
            choose(f"{pair}/outcome/{_component(outcome)}/mean_difference_percentage_points")
            choose(f"interval/{_component(treatment + '_vs_' + control)}/{_component(outcome)}/excludes_zero")
            for group in (treatment, control):
                choose(f"arm_metric/{_component(group)}/outcome/inspected_publication/mean")
            for group in (treatment, control):
                choose(f"arm_metric/{_component(group)}/trajectory/publisher_inspected_published_version/mean")
            choose(f"{pair}/outcome/inspected_publication/mean_direction")
            choose(f"{pair}/trajectory/publisher_inspected_published_version/mean_direction")
        choose("replay/recorded_actions/pass")
        if isinstance(treatment, str):
            choose(f"interval/{_component(treatment + '_vs_baseline')}/{_component(outcome)}/excludes_zero")
        choose("backend/model")
        choose("comparison_identity/primary_outcome")
    choose("completion/all_assigned_units_present")
    return chosen


def claims_schema_for_packet(packet):
    """Return the finite output schema with explicit allowed packet references."""
    identities = list(packet.get("facts", {}))
    if not identities or len(identities) > 100:
        raise ValueError("Schema needs a bounded selected fact packet")
    schema = copy.deepcopy(CLAIMS_SCHEMA)
    schema["properties"]["claims"]["items"]["properties"]["fact_id"]["enum"] = identities + [None]
    schema["properties"]["claims"]["items"]["properties"]["source_fingerprint"]["enum"] = [packet["source_fingerprint"]]
    return schema


def audit_claims(ledger, claims):
    """Audit a finite claim list against a previously built, fingerprint-bound ledger."""
    if not isinstance(claims, list) or len(claims) > 100:
        raise ValueError("Claims must be a list of at most 100 entries")
    rows, seen = [], set()
    for claim in claims:
        row = {"id": claim.get("id") if isinstance(claim, dict) else None, "status": "invalid",
               "prose_status": "unverified", "approved_fact_text": None}
        try:
            validate_claim(claim)
            if claim["id"] in seen:
                raise ValueError("Duplicate claim identity")
            seen.add(claim["id"])
            if claim["source_fingerprint"] != ledger["source_fingerprint"]:
                row.update(status="mismatch", reason="Claim is bound to a different report fingerprint")
            elif claim["kind"] in ("free_prose", "proposed_mechanism"):
                row.update(status="unverified", reason="No executable language entailment or mechanism verification is performed")
            elif claim["fact_id"] not in ledger["facts"]:
                row.update(status="unavailable", reason="No fact with this metric, actor, version, or comparison exists")
            else:
                fact = ledger["facts"][claim["fact_id"]]
                row["actual"] = fact["value"]
                row["fact_id"] = fact["id"]
                if fact["validity"] != "usable":
                    row.update(status="unavailable", reason="The recorded measure conflicts with its trace reconstruction")
                elif claim["kind"] != fact["kind"] or claim["scope"] != fact["scope"]:
                    row.update(status="mismatch", reason="Claim kind/scope does not match the executable fact")
                elif not _same(claim["expected"], fact["value"]):
                    row.update(status="mismatch", reason="Expected typed value contradicts the executable fact")
                else:
                    row.update(status="supported", reason="Typed fact matches this recorded report; attached prose remains unverified",
                               approved_fact_text=fact["rendered_fact"])
        except ValueError as exc:
            row["reason"] = str(exc)
        rows.append(row)
    prose_present = any(r["status"] == "unverified" for r in rows) or any(c.get("statement") for c in claims if isinstance(c, dict))
    executable_supported = all(r["status"] in ("supported", "unverified") for r in rows) and not ledger.get("issues")
    return clean({"source_fingerprint": ledger["source_fingerprint"], "claims": rows,
                  "all_executable_claims_supported": all(r["status"] in ("supported", "unverified") for r in rows)
                      and not ledger.get("issues"),
                  "unverified_prose_present": prose_present, "review_required": prose_present or not executable_supported,
                  "supported_fact_ids": [r["fact_id"] for r in rows if r["status"] == "supported"],
                  "attached_prose_approved": False,
                  "ledger_issues": ledger.get("issues", []), "model_calls": 0,
                  "scope": "Finite typed assertions only; this audit does not approve prose, mechanisms, historical findings, or generality."})
