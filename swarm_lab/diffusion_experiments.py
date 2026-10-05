"""Preregistered factorial experiments on provenance and communication topology.

The whole network is the unit: arbitrary spillovers within a network are allowed.
Primary effects average equally over the randomized second factor. Randomization
tests permute labels *within the other factor*, preserving the balanced factorial
design. A network's four verdicts are never treated as four independent trials.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import itertools
import json
import math
import platform
import random
from pathlib import Path
from statistics import mean
from typing import Any, Callable

from .diffusion_environment import (SUBJECTS, TOPOLOGIES, check_diffusion_contract, create_diffusion_environment,
                                    create_diffusion_spec, diffusion_subject_request,
                                    fingerprint, offline_diffusion_policy,
                                    validate_diffusion_spec)


DIFFUSION_EXPERIMENT_VERSION = "1.0"
CONTEXTS = ("baseline", "placebo", "source_thought")
SOURCE_THOUGHT = (
    "Before combining claims, check original source IDs. Repeated reports or messages "
    "from the same source duplicate one observation, not independent evidence. Consider "
    "which original measurements are available before choosing your verdict; communicate "
    "original provenance when useful."
)
PLACEBO_THOUGHT = (
    "You are continuing the current team task in this environment. The task description "
    "and available actions remain available for your next decision. This private note "
    "marks the continuation of your session; proceed as you ordinarily would."
)


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _seed(value: int, namespace: str, index: int = 0) -> int:
    return int(hashlib.sha256(f"{value}:{namespace}:{index}".encode()).hexdigest()[:15], 16)


def _code_hashes() -> dict[str, str]:
    folder = Path(__file__).parent
    return {name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
            for name in ("diffusion_environment.py", "diffusion_experiments.py")}


def _seal(body: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(body)
    result.pop("protocol_hash", None)
    result["protocol_hash"] = fingerprint(result)
    return result


def create_diffusion_protocol(trials_per_cell: int = 2, seed: int = 43, *,
                              max_rounds: int = 3,
                              topologies: list[str] | tuple[str, ...] = TOPOLOGIES,
                              contexts: list[str] | tuple[str, ...] = CONTEXTS,
                              source_reliability: float = .75,
                              recipients: list[str] | tuple[str, ...] = ("agent-0",),
                              source_text: str = SOURCE_THOUGHT,
                              placebo_text: str = PLACEBO_THOUGHT,
                              incident: dict[str, Any] | None = None,
                              subject_backend: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(trials_per_cell, int) or isinstance(trials_per_cell, bool) or not 2 <= trials_per_cell <= 1000:
        raise ValueError("trials_per_cell must be an integer between 2 and 1000")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed must be an integer")
    if not topologies or len(set(topologies)) != len(topologies) or any(kind not in TOPOLOGIES for kind in topologies):
        raise ValueError("Choose a nonempty unique list of implemented topologies")
    if len(contexts) < 2 or len(set(contexts)) != len(contexts) or any(kind not in CONTEXTS for kind in contexts):
        raise ValueError("At least two unique implemented contexts are required")
    if "source_thought" not in contexts:
        raise ValueError("Source-thought treatment is required for this study")
    if not recipients or len(set(recipients)) != len(recipients) or any(agent not in SUBJECTS for agent in recipients):
        raise ValueError("Choose fixed unique recipients from the four subjects")
    if not isinstance(source_text, str) or not source_text.strip() or not isinstance(placebo_text, str) or not placebo_text.strip():
        raise ValueError("Treatments need text")
    environment_templates = {
        topology: create_diffusion_spec(topology=topology, max_rounds=max_rounds,
                                       source_reliability=source_reliability, incident=incident)
        for topology in topologies
    }
    context_control = "placebo" if "placebo" in contexts else "baseline"
    primary_contrasts = [{"factor": "context", "treatment": "source_thought",
                          "control": context_control, "stratify_by": "topology"}]
    if len(topologies) > 1:
        network_control = "ring" if "ring" in topologies else topologies[0]
        network_treatment = "complete" if "complete" in topologies and network_control != "complete" else next(
            kind for kind in reversed(topologies) if kind != network_control)
        primary_contrasts.append({"factor": "topology", "treatment": network_treatment,
                                  "control": network_control, "stratify_by": "context"})
    body = {
        "api_version": DIFFUSION_EXPERIMENT_VERSION, "study_kind": "provenance_diffusion_factorial",
        "created_at": _now(), "status": "frozen_before_execution",
        "registration_scope": "local_frozen_protocol_not_public_preregistration",
        "research_question": "How do original-source dependence, communication topology and private provenance reminders change network verdict accuracy?",
        "environments": environment_templates,
        "environment_hashes": {kind: fingerprint(spec) for kind, spec in environment_templates.items()},
        "subject_backend": copy.deepcopy(subject_backend or {"status": "not_yet_pinned"}),
        "contexts": {kind: {"insertion": None if kind == "baseline" else (
            source_text if kind == "source_thought" else placebo_text)} for kind in contexts},
        "intervention": {
            "channel": "private_context", "recipients": list(recipients),
            "focal_agent": recipients[0],
            "timing": "Immediately before each specified recipient's first scheduled decision",
            "persistence": "Within that recipient's context until the end of this run; no cross-run memory",
            "interpretation": "Observable text assignment, not control or measurement of latent beliefs",
            "context_lengths": {"source_words": len(source_text.split()),
                                "placebo_words": len(placebo_text.split()),
                                "token_matching": "Word counts are recorded; tokenizer lengths and semantic inertness are not assumed equal."},
        },
        "design": {
            "unit": "whole_network_run", "allocation": "equal_counts_complete_randomization_of_factorial_cells",
            "trials_per_cell": trials_per_cell, "seed": seed,
            "factors": {"topology": list(topologies), "context": list(contexts)},
            "cells": [{"topology": topology, "context": context}
                      for topology in topologies for context in contexts],
            "independent_environment_seed_per_run": True,
            "matched": ["four subjects", "maximum total action budget", "per-subject message cap",
                        "sensor reliability and source-copy distribution", "scheduler rule", "model and harness configuration"],
            "not_matched": ["degree", "neighbor choices", "path lengths", "achieved information exposure", "realized action count"],
            "stopping_rule": "All registered runs; stop each run after all verdicts or its fixed action budget",
            "interference": "Within-network influence allowed. Networks have independently reset state; no cross-network communication.",
        },
        "estimand": {
            "primary_outcome": "mean_accuracy",
            "operational_definition": "Mean of four indicators of submitted verdict matching hidden truth; missing verdicts contribute 0",
            "direction": "two_sided; improvement, harm and null results retained",
            "primary_contrasts": primary_contrasts,
            "averaging": "Equal average over registered levels of the other factor",
            "population": "Four-subject synthetic noisy-sensor networks under this report-copy distribution",
        },
        "measurement": {
            "oracle": "Code comparison with seeded hidden truth; verdict rationale or agreement is not evidence of correctness",
            "primary_interval": "95% bounded Hoeffding interval assuming independent bounded run outcomes; conservative at pilot size",
            "sensitivity_interval": "Within-cell run-level percentile bootstrap; may degenerate at ceilings",
            "primary_test": "Two-sided randomization test conditional on the other factor, preserving cell counts",
            "multiplicity": "Holm-adjusted p-values across preregistered primary factor contrasts; other analyses descriptive",
            "missing_verdicts": "Remain intention-to-treat zeros; completion reported separately",
            "invalid_actions": "Consume action slots; no outcome-based exclusions",
            "infrastructure_failure": "Persist partial run and abort estimation; no silent replacement or deletion",
            "secondary_outcomes": ["focal_accuracy", "completion_rate", "mean_independent_sources_at_verdict",
                                   "duplicate_source_reception_fraction", "messages_sent", "steps_used"],
        },
        "causal_assumptions_and_limitations": [
            "Whole-network randomization identifies effects of assigned topology/context here, not historical influence or latent beliefs.",
            "A fixed focal recipient is the star hub; topology-context interactions can include recipient-position effects.",
            "Sensor holders are randomly permuted within each run; small samples can still show source-placement imbalance.",
            "Shared-source errors are dependent by construction; source IDs alone cannot establish independence in real corpora.",
            "Message and action budgets are fixed, but information opportunity differs by topology as part of the treatment.",
            "Submission freezes a verdict; later received evidence is not used to explain an earlier decision.",
            "Randomization/environment seeds do not seed hosted-model sampling, and model aliases may change.",
            "Stable backend and no cross-run memory are assumptions; random run order mitigates service time drift without proving its absence.",
            "The independent-run bounded interval and small-sample bootstrap have different assumptions; neither establishes transportability.",
            "Self-reported reasoning does not identify a mechanism; observed mediation needs additional randomized designs.",
        ],
        "execution_code_hashes": _code_hashes(),
    }
    return _seal(body)


def validate_diffusion_protocol(protocol: dict[str, Any], *, check_code: bool = True) -> None:
    body = copy.deepcopy(protocol)
    signature = body.pop("protocol_hash", None)
    if not signature or fingerprint(body) != signature:
        raise ValueError("Diffusion protocol changed after freezing")
    if body.get("api_version") != DIFFUSION_EXPERIMENT_VERSION or body.get("study_kind") != "provenance_diffusion_factorial":
        raise ValueError("Unsupported diffusion protocol")
    if body["design"]["unit"] != "whole_network_run":
        raise ValueError("Network interference requires network-level experimental units")
    for kind, spec in body["environments"].items():
        validate_diffusion_spec(spec)
        if spec["topology"]["kind"] != kind or fingerprint(spec) != body["environment_hashes"].get(kind):
            raise ValueError("Diffusion environment hash or topology mismatch")
    if check_code and _code_hashes() != body.get("execution_code_hashes"):
        raise ValueError("Diffusion execution code changed; freeze a new version before running")


def randomize_diffusion_runs(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    validate_diffusion_protocol(protocol)
    design = protocol["design"]
    cells = [copy.deepcopy(cell) for cell in design["cells"] for _ in range(design["trials_per_cell"])]
    random.Random(_seed(design["seed"], "factorial-allocation")).shuffle(cells)
    return [{"run_index": index, "run_id": f"network-{index + 1:04d}", **cell,
             "environment_seed": _seed(design["seed"], "network-world", index)}
            for index, cell in enumerate(cells)]


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lo, hi = math.floor(position), math.ceil(position)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)


def stratified_network_effect(strata: list[tuple[list[float], list[float]]], *,
                              seed: int = 0, resamples: int = 2000,
                              alpha: float = .05) -> dict[str, Any]:
    """Equal-stratum network effect with design-preserving uncertainty estimates."""
    if not strata or any(not a or not b for a, b in strata):
        raise ValueError("Every registered stratum needs both outcome arms")
    if any(not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1
           for a, b in strata for value in [*a, *b]):
        raise ValueError("Network outcomes must be bounded between zero and one")
    if resamples < 100 or not 0 < alpha < 1:
        raise ValueError("Invalid resample count or interval alpha")
    observed = mean([mean(a) - mean(b) for a, b in strata])
    rng = random.Random(seed)
    boot = [mean([mean(rng.choices(a, k=len(a))) - mean(rng.choices(b, k=len(b)))
                  for a, b in strata]) for _ in range(resamples)]
    number = math.prod(math.comb(len(a) + len(b), len(a)) for a, b in strata)
    extreme = 0
    if number <= 20000:
        possible = []
        for a, b in strata:
            pooled, n_a = [*a, *b], len(a)
            values = []
            for selected in itertools.combinations(range(len(pooled)), n_a):
                chosen = set(selected)
                values.append(mean([value for index, value in enumerate(pooled) if index in chosen]) - mean(
                    [value for index, value in enumerate(pooled) if index not in chosen]))
            possible.append(values)
        for assignment in itertools.product(*possible):
            extreme += abs(mean(assignment)) + 1e-12 >= abs(observed)
        p_value = extreme / number
        method, samples = "exact_randomization_within_other_factor", number
    else:
        for _ in range(resamples):
            differences = []
            for a, b in strata:
                shuffled = rng.sample([*a, *b], len(a) + len(b))
                differences.append(mean(shuffled[:len(a)]) - mean(shuffled[len(a):]))
            extreme += abs(mean(differences)) + 1e-12 >= abs(observed)
        p_value = (extreme + 1) / (resamples + 1)
        method, samples = "monte_carlo_randomization_within_other_factor_plus_one", resamples
    coefficient_range_squares = sum((1 / len(strata)) ** 2 * (1 / len(a) + 1 / len(b)) for a, b in strata)
    half = math.sqrt(.5 * coefficient_range_squares * math.log(2 / alpha))
    return {
        "difference": observed, "mean_treatment": mean([mean(a) for a, _ in strata]),
        "mean_control": mean([mean(b) for _, b in strata]),
        "n_treatment_networks": sum(len(a) for a, _ in strata),
        "n_control_networks": sum(len(b) for _, b in strata),
        "strata": len(strata), "unit": "whole_network_run",
        "ci95": [max(-1, observed - half), min(1, observed + half)],
        "interval_alpha": alpha, "interval_method": "bounded_independent_run_Hoeffding",
        "bootstrap_ci95": [_quantile(boot, .025), _quantile(boot, .975)],
        "bootstrap_resamples": resamples, "p_two_sided": p_value,
        "test_method": method, "test_samples": samples,
    }


def _holm(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    result, previous = [0.0] * len(values), 0.0
    for position, index in enumerate(order):
        previous = max(previous, min(1.0, (len(values) - position) * values[index]))
        result[index] = previous
    return result


def analyze_diffusion_runs(runs: list[dict[str, Any]], protocol: dict[str, Any], *,
                           resamples: int = 2000) -> dict[str, Any]:
    design = protocol["design"]
    cells = {}
    groups = {}
    descriptive = ("mean_accuracy", "focal_accuracy", "completion_rate", "messages_sent", "steps_used",
                   "mean_independent_sources_at_verdict", "duplicate_source_reception_fraction")
    for cell in design["cells"]:
        key = f"{cell['topology']}|{cell['context']}"
        group = [run for run in runs if run["topology"] == cell["topology"] and run["context"] == cell["context"]]
        if len(group) != design["trials_per_cell"]:
            raise ValueError("Incomplete factorial cells cannot be analyzed as a complete registered experiment")
        groups[(cell["topology"], cell["context"])] = group
        cells[key] = {"n_networks": len(group), **cell,
                      **{outcome: mean(run["outcomes"][outcome] for run in group) for outcome in descriptive},
                      "step_budget_terminations": sum(run["outcomes"]["terminated_by"] == "step_budget" for run in group),
                      "truth_one_count": sum(run["initial_state"]["truth"] for run in group),
                      "focal_duplicated_source_count": sum(
                          run["initial_state"]["reports"][protocol["intervention"]["focal_agent"]]["source_id"] == "source-0"
                          for run in group)}
    factor_effects = []
    for index, contrast in enumerate(protocol["estimand"]["primary_contrasts"]):
        strata = []
        for other_level in design["factors"][contrast["stratify_by"]]:
            if contrast["factor"] == "context":
                a = groups[(other_level, contrast["treatment"])]
                b = groups[(other_level, contrast["control"])]
            else:
                a = groups[(contrast["treatment"], other_level)]
                b = groups[(contrast["control"], other_level)]
            strata.append(([run["outcomes"]["mean_accuracy"] for run in a],
                           [run["outcomes"]["mean_accuracy"] for run in b]))
        effect = stratified_network_effect(strata, seed=_seed(design["seed"], "primary-effect", index),
                                           resamples=resamples)
        factor_effects.append({**contrast, "outcome": "mean_accuracy", **effect})
    adjusted = _holm([effect["p_two_sided"] for effect in factor_effects])
    for effect, p_adjusted in zip(factor_effects, adjusted):
        effect["p_holm_primary_family"] = p_adjusted
    context_by_topology = {}
    contrast = protocol["estimand"]["primary_contrasts"][0]
    for topology in design["factors"]["topology"]:
        a = [run["outcomes"]["mean_accuracy"] for run in groups[(topology, contrast["treatment"])]]
        b = [run["outcomes"]["mean_accuracy"] for run in groups[(topology, contrast["control"])]]
        context_by_topology[topology] = stratified_network_effect(
            [(a, b)], seed=_seed(design["seed"], f"exploratory-context:{topology}"), resamples=resamples)
        context_by_topology[topology]["status"] = "exploratory_heterogeneity_not_mediation"
    return {"cells": cells, "factor_effects": factor_effects,
            "primary_effect": factor_effects[0], "context_effect_by_topology": context_by_topology,
            "primary_family_size": len(factor_effects),
            "warnings": [
                "One network is one trial; four agents or many messages do not increase the randomized sample size.",
                "Primary tests preserve factorial cell counts by permuting within the other factor.",
                "Holm-adjusted p-values cover the primary contrast family; displayed intervals are individual, not simultaneous.",
                "Bounded intervals are conservative and assume independent run outcomes; bootstrap intervals may collapse at ceilings.",
                "Observed exposure is a post-treatment variable; these reports do not identify mediation or direct/indirect individual effects.",
                "Focal recipient position differs across topology; social mechanism and transportability need separate experiments.",
            ]}


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


class DiffusionExecutionError(RuntimeError):
    def __init__(self, message: str, partial_report: dict[str, Any]):
        super().__init__(message)
        self.partial_report = partial_report


def run_diffusion_experiment(protocol: dict[str, Any],
                             agent_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
                             output_dir: str | Path | None = None, *,
                             backend_metadata: dict[str, Any] | None = None,
                             on_progress: Callable[[dict[str, Any]], None] | None = None,
                             resamples: int = 2000) -> dict[str, Any]:
    validate_diffusion_protocol(protocol)
    protocol = copy.deepcopy(protocol)
    runner = agent_runner or offline_diffusion_policy
    assignments = randomize_diffusion_runs(protocol)
    output = Path(output_dir) if output_dir is not None else None
    report = {
        "api_version": DIFFUSION_EXPERIMENT_VERSION,
        "study_kind": "provenance_diffusion_factorial",
        "experiment_id": f"diffusion-{protocol['protocol_hash'][:16]}",
        "protocol_hash": protocol["protocol_hash"], "protocol": protocol,
        "status": "running", "started_at": _now(), "finished_at": None,
        "assignments": assignments, "runs": [],
        "backend": {"mode": "scripted_offline_smoke_test" if agent_runner is None else "provided_agent_runner",
                    "metadata": copy.deepcopy(backend_metadata or {}),
                    "registered_spec": copy.deepcopy(protocol["subject_backend"]),
                    "python": platform.python_version(),
                    "fresh_state_contract": "Callable has no persistent state between independent networks"},
        "evidence_scope": (
            "Scripted policy deduplication is an assumption; offline results validate infrastructure, not LLM behavior."
            if agent_runner is None else
            "Effects apply to supplied context and topology among tested subjects in a synthetic noisy-source setting; historical mechanisms remain unestablished."),
        "local_protocol_written_before_subject_calls": output is not None,
    }
    if output:
        if (output / "report.json").exists():
            raise ValueError("Output directory contains results; choose a fresh run directory")
        if (output / "protocol.json").exists() and json.loads((output / "protocol.json").read_text(encoding="utf-8")) != protocol:
            raise ValueError("Output directory contains a different frozen protocol")
        _write(output / "protocol.json", protocol)
        _write(output / "assignment.json", assignments)
        _write(output / "progress.json", report)
    for assignment in assignments:
        environment, initial_state, turns, delivered = None, None, [], set()
        try:
            environment = create_diffusion_environment(protocol["environments"][assignment["topology"]],
                                                       assignment["environment_seed"])
            initial_state = environment.snapshot()
            contract = check_diffusion_contract(environment)
            if not contract["passed"]:
                raise RuntimeError("Diffusion environment contract failed")
            while not environment.terminal:
                agent = environment.next_agent
                if agent in protocol["intervention"]["recipients"] and agent not in delivered:
                    text = protocol["contexts"][assignment["context"]]["insertion"]
                    if text is not None:
                        environment.inject_context(agent, text)
                    delivered.add(agent)
                request = diffusion_subject_request(environment, agent)
                action = runner(copy.deepcopy(request))
                result = environment.step(agent, action)
                turns.append({"step": environment.step_count - 1, "agent_id": agent,
                              "request": request, "action": copy.deepcopy(action), "tool_result": result})
        except Exception as exc:
            report["status"] = "incomplete_infrastructure_failure"
            report["finished_at"] = _now()
            report["failure"] = {"run_id": assignment["run_id"], "error_type": type(exc).__name__,
                                 "completed_steps": environment.step_count if environment is not None else 0}
            report["incomplete_run"] = {**copy.deepcopy(assignment), "turns": turns,
                                        "state": environment.snapshot() if environment is not None else None}
            if output:
                _write(output / "report.json", report)
            raise DiffusionExecutionError(
                f"Diffusion subject execution failed in {assignment['run_id']} ({type(exc).__name__}); effects not estimated", report) from exc
        run = {**copy.deepcopy(assignment), "initial_state": initial_state,
               "final_state": environment.snapshot(), "turns": turns,
               "insertion_boundary_reached_by": sorted(delivered),
               "actual_context_insertion_recipients": sorted({event["agent_id"] for event in environment.events
                                                               if event["type"] == "context_insertion"}),
               "environment_contract": contract,
               "outcomes": environment.evaluate(protocol["intervention"]["focal_agent"])}
        report["runs"].append(run)
        if output:
            _write(output / "runs" / f"{assignment['run_id']}.json", run)
            _write(output / "progress.json", report)
        if on_progress:
            try:
                on_progress({"completed": len(report["runs"]), "total": len(assignments),
                             "run_id": assignment["run_id"], "topology": assignment["topology"],
                             "context": assignment["context"], "outcomes": copy.deepcopy(run["outcomes"])})
            except Exception as exc:
                report.setdefault("reporting_warnings", []).append({"run_id": assignment["run_id"],
                                                                    "callback_error_type": type(exc).__name__})
    report["analysis"] = analyze_diffusion_runs(report["runs"], protocol, resamples=resamples)
    report["status"] = "complete"
    report["finished_at"] = _now()
    report["report_hash"] = fingerprint(report)
    if output:
        _write(output / "report.json", report)
        _write(output / "progress.json", report)
    return report


def create_diffusion_replication(original: dict[str, Any], new_seed: int,
                                 trials_per_cell: int | None = None) -> dict[str, Any]:
    validate_diffusion_protocol(original)
    if not isinstance(new_seed, int) or isinstance(new_seed, bool) or new_seed == original["design"]["seed"]:
        raise ValueError("Replication needs a different integer seed namespace")
    body = copy.deepcopy(original)
    body.pop("protocol_hash", None)
    body["created_at"] = _now()
    body["replicates_protocol_hash"] = original["protocol_hash"]
    body["replication_scope"] = "held_out_environment_seeds_not_cross_model_or_cross_task"
    body["design"]["seed"] = new_seed
    if trials_per_cell is not None:
        if not isinstance(trials_per_cell, int) or isinstance(trials_per_cell, bool) or not 2 <= trials_per_cell <= 1000:
            raise ValueError("Invalid replication sample size")
        body["design"]["trials_per_cell"] = trials_per_cell
    replication = _seal(body)
    original_seeds = {run["environment_seed"] for run in randomize_diffusion_runs(original)}
    if original_seeds & {run["environment_seed"] for run in randomize_diffusion_runs(replication)}:
        raise ValueError("Replication environment-seed overlap")
    return replication
