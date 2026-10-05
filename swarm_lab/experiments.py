"""Run-level randomized experiments over resettable agent-society environments.

This subsystem owns execution mechanics and numerical outcomes. Research agents
may propose protocols, but treatments, randomization and estimators are inspectable
code. A frozen local protocol is written *before* subject calls when output_dir is
supplied. This is not a public registry or a guarantee against all confounding.
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

from .environments import (ACTION_SCHEMA, check_environment_contract,
                           create_environment, environment_spec, offline_policy,
                           subject_request, validate_spec)


EXPERIMENT_API_VERSION = "1.0"
EVIDENCE_THOUGHT = (
    "Before relying on a completion claim, inspect the current artifact and compare "
    "it with the task requirements. Ask for missing evidence or a repair when needed. "
    "A teammate's confident statement is a claim you can check."
)
PLACEBO_THOUGHT = (
    "You are continuing the current team task in this environment. The task description "
    "and available actions remain available for your next decision. This private note "
    "marks the continuation of your session; proceed as you ordinarily would."
)
ARMS = ("baseline", "placebo", "evidence_thought")
PRIMARY_OUTCOME = "success"
SECONDARY_OUTCOMES = ("incorrect_publication", "inspected_publication", "steps_used")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _module_hashes() -> dict[str, str]:
    directory = Path(__file__).parent
    return {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
            for name in ("environments.py", "experiments.py")}


def _derived_seed(seed: int, namespace: str, index: int = 0) -> int:
    return int(hashlib.sha256(f"{seed}:{namespace}:{index}".encode()).hexdigest()[:15], 16)


def _seal_protocol(body: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(body)
    result.pop("protocol_hash", None)
    result["protocol_hash"] = _hash(result)
    return result


def create_protocol(incident: dict[str, Any] | None = None, trials_per_arm: int = 4,
                    seed: int = 42, max_rounds: int = 6,
                    research_question: str | None = None,
                    evidence_text: str = EVIDENCE_THOUGHT,
                    placebo_text: str = PLACEBO_THOUGHT,
                    environment_override: dict[str, Any] | None = None,
                    subject_backend: dict[str, Any] | None = None) -> dict[str, Any]:
    """Construct a sealed, locally preregistered protocol before any subject call.

    The manipulated treatment is private textual context, not a claim to control
    latent thoughts. Every swarm run is one randomized experimental unit, thereby
    allowing arbitrary within-run interference between its three subjects.
    """
    if not isinstance(trials_per_arm, int) or isinstance(trials_per_arm, bool) or not 2 <= trials_per_arm <= 1000:
        raise ValueError("trials_per_arm must be an integer between 2 and 1000")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed must be an integer")
    if not evidence_text.strip() or not placebo_text.strip():
        raise ValueError("Both active and placebo context must contain text")
    spec = environment_spec(incident, max_rounds, environment_override)
    body = {
        "api_version": EXPERIMENT_API_VERSION,
        "created_at": _utc_now(),
        "status": "frozen_before_execution",
        "registration_scope": "local_frozen_protocol_not_public_preregistration",
        "phase": "confirmatory_protocol_with_pilot_sized_sample",
        "research_question": research_question or (
            "Does a private evidence-check reminder change correct shared-artifact "
            "publication compared with a neutral private-context insertion?"),
        "estimand": {
            "name": "intention_to_treat_risk_difference",
            "population": "Fresh three-agent teams in this synthetic inventory handoff distribution",
            "unit": "whole_swarm_run",
            "primary_contrast": ["evidence_thought", "placebo"],
            "primary_outcome": PRIMARY_OUTCOME,
            "operational_outcome_definition": "1 only if coordinator actually publishes a manifest whose contents exactly equal required task quantities; 0 for an incorrect publication or reaching the fixed action budget without publication",
            "prespecified_direction": "two_sided; an improvement, null effect or harm are all reportable",
            "interpretation": "Mean run-level correct-publication outcome under assigned contexts",
        },
        "environment": spec,
        "environment_hash": _hash(spec),
        "subject_backend": copy.deepcopy(subject_backend or {
            "status": "not_yet_pinned", "note": "Record concrete model, harness and generation settings before live execution; environment seeds do not control hosted-model randomness."}),
        "arms": {
            "baseline": {"insertion": None},
            "placebo": {"insertion": placebo_text},
            "evidence_thought": {"insertion": evidence_text},
        },
        "intervention": {
            "channel": "private_context_before_decision",
            "recipient": "coordinator",
            "timing": "immediately_before_recipient_first_scheduled_action",
            "persistence": "Retained in the recipient's private context for the remainder of that run; never across runs",
            "interpretation": "Assigned input text; no hidden reasoning editing or belief manipulation is assumed",
            "context_lengths": {
                "evidence_words": len(evidence_text.split()),
                "placebo_words": len(placebo_text.split()),
                "evidence_characters": len(evidence_text),
                "placebo_characters": len(placebo_text),
                "token_matching": "Default notes match whitespace word count; tokenizer-specific lengths and content effects may differ.",
            },
        },
        "design": {
            "allocation": "complete_randomization_equal_arm_counts",
            "trials_per_arm": trials_per_arm,
            "seed": seed,
            "independent_environment_seed_per_run": True,
            "scheduler": "seeded_shuffled_round_robin",
            "interference": "Allowed within a swarm; independent state across swarm runs",
            "randomization_unit": "whole_swarm_run",
            "stopping_rule": "All assigned runs; each ends at first publication or fixed action budget",
        },
        "measurement": {
            "primary": PRIMARY_OUTCOME,
            "secondary": list(SECONDARY_OUTCOMES),
            "oracle": "Exact equality of published inventory contents with task requirements",
            "evaluator": "Deterministic code, independent of treatment labels and agent success claims",
            "primary_interval": "Newcombe independent-proportions Wilson interval at 95%",
            "sensitivity_interval": "Within-arm run-level percentile bootstrap at 95%",
            "primary_test": "Two-sided conditional randomization test of active versus placebo",
            "secondary_test_policy": "Descriptive exploratory comparisons; no multiplicity-adjusted confirmatory claims",
            "infrastructure_failure_policy": "Stop and persist incomplete experiment; do not silently exclude or replace runs",
            "exclusion_policy": "No behavioral runs are excluded. Invalid actions, unsuccessful publications and step-budget terminations remain assigned outcomes. Infrastructure failures abort estimation rather than dropping runs.",
        },
        "leakage_controls": [
            "Only role-scoped observation and that subject's private context enter its request.",
            "Arm labels, oracle state, seeds, historical future and proposed causal explanations are withheld.",
            "Fresh subject requests and environment state are constructed for every independent run.",
            "Evaluation uses executed publication contents rather than narrative or LLM grading.",
        ],
        "assumptions_and_limitations": [
            "Causal effects apply to assigned text in this reconstructed setting, not directly to the historical Village.",
            "Within-run social spillovers are part of the run-level effect; individual direct and indirect effects are not identified.",
            "Treatment channels and baseline prompts are fixed, but wording and extra context may each affect behavior.",
            "A neutral insertion controls some context effects; it is not guaranteed psychologically inert.",
            "Sequential hosted-model calls can experience time drift; randomized run order mitigates but does not eliminate it.",
            "Model and harness stability, no persistent cross-run memory, and independent service sessions are execution assumptions.",
            "The allocation and environment seeds do not seed hosted-model sampling; repeated calls may differ and alias model versions may drift.",
            "Small-sample intervals and tests have limited power; a pilot does not establish generality or absence of confounding.",
        ],
        "execution_code_hashes": _module_hashes(),
    }
    return _seal_protocol(body)


def validate_protocol(protocol: dict[str, Any], check_code: bool = True) -> None:
    body = copy.deepcopy(protocol)
    signature = body.pop("protocol_hash", None)
    if not signature or _hash(body) != signature:
        raise ValueError("Frozen protocol has changed; create a new protocol instead of mutating it")
    if body.get("api_version") != EXPERIMENT_API_VERSION:
        raise ValueError("Unsupported experiment API version")
    if _hash(body["environment"]) != body.get("environment_hash"):
        raise ValueError("Environment hash mismatch")
    validate_spec(body["environment"])
    if set(body.get("arms", {})) != set(ARMS):
        raise ValueError("This protocol requires baseline, placebo and evidence_thought arms")
    if body.get("design", {}).get("randomization_unit") != "whole_swarm_run":
        raise ValueError("Within-run interference requires run-level randomization")
    if check_code and body.get("execution_code_hashes") != _module_hashes():
        raise ValueError("Execution code changed since the protocol was frozen; freeze a new version")


def randomize_runs(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    validate_protocol(protocol)
    design = protocol["design"]
    labels = [arm for arm in ARMS for _ in range(design["trials_per_arm"])]
    rng = random.Random(_derived_seed(design["seed"], "allocation"))
    rng.shuffle(labels)
    return [{"run_index": index, "run_id": f"run-{index + 1:04d}", "arm": arm,
             "environment_seed": _derived_seed(design["seed"], "environment", index)}
            for index, arm in enumerate(labels)]


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _wilson(values: list[float], z: float = 1.959963984540054) -> tuple[float, float]:
    n = len(values)
    p = mean(values)
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def newcombe_interval(a: list[float], b: list[float]) -> list[float]:
    """Difference of independent binary proportions; remains broad at ceilings."""
    if not a or not b or any(value not in (0, 1) for value in [*a, *b]):
        raise ValueError("Independent nonempty binary outcome samples required")
    pa, pb = mean(a), mean(b)
    lower_a, upper_a = _wilson(a)
    lower_b, upper_b = _wilson(b)
    difference = pa - pb
    return [max(-1.0, difference - math.sqrt((pa - lower_a) ** 2 + (upper_b - pb) ** 2)),
            min(1.0, difference + math.sqrt((upper_a - pa) ** 2 + (pb - lower_b) ** 2))]


def compare_outcomes(a: list[float], b: list[float], seed: int = 0,
                     resamples: int = 2000) -> dict[str, Any]:
    """Run-level mean difference, intervals, and conditional randomization test."""
    if not a or not b:
        raise ValueError("Both arms need outcomes")
    if any(not isinstance(value, (int, float)) or not math.isfinite(value)
           for value in [*a, *b]):
        raise ValueError("Outcome samples must contain finite numbers")
    if resamples < 100:
        raise ValueError("At least 100 resamples required")
    difference = mean(a) - mean(b)
    rng = random.Random(seed)
    boot = [mean(rng.choices(a, k=len(a))) - mean(rng.choices(b, k=len(b)))
            for _ in range(resamples)]
    pooled = list(a) + list(b)
    n_a = len(a)
    permutations = math.comb(len(pooled), n_a)
    extreme = 0
    epsilon = 1e-12
    if permutations <= 20000:
        for selected in itertools.combinations(range(len(pooled)), n_a):
            chosen = set(selected)
            delta = mean([value for index, value in enumerate(pooled) if index in chosen]) - mean(
                [value for index, value in enumerate(pooled) if index not in chosen])
            extreme += abs(delta) + epsilon >= abs(difference)
        p_value = extreme / permutations
        test_mode, test_samples = "exact_conditional_randomization", permutations
    else:
        for _ in range(resamples):
            shuffled = rng.sample(pooled, len(pooled))
            delta = mean(shuffled[:n_a]) - mean(shuffled[n_a:])
            extreme += abs(delta) + epsilon >= abs(difference)
        p_value = (extreme + 1) / (resamples + 1)
        test_mode, test_samples = "monte_carlo_conditional_randomization_plus_one", resamples
    bootstrap_ci = [_quantile(boot, .025), _quantile(boot, .975)]
    binary = all(value in (0, 1) for value in pooled)
    return {"n_treatment": len(a), "n_control": len(b),
            "mean_treatment": mean(a), "mean_control": mean(b),
            "difference": difference,
            "ci95": newcombe_interval(a, b) if binary else bootstrap_ci,
            "interval_method": "Newcombe_Wilson" if binary else "run_level_percentile_bootstrap",
            "bootstrap_ci95": bootstrap_ci, "bootstrap_resamples": resamples,
            "p_two_sided": p_value, "test_method": test_mode,
            "test_samples": test_samples,
            "unit": "whole_swarm_run"}


def summarize_runs(runs: list[dict[str, Any]], protocol: dict[str, Any],
                   resamples: int = 2000) -> dict[str, Any]:
    groups = {arm: [run for run in runs if run["arm"] == arm] for arm in ARMS}
    planned = protocol["design"]["trials_per_arm"]
    if any(len(values) != planned for values in groups.values()):
        raise ValueError("Cannot estimate confirmatory effects from incomplete assigned runs")
    outcomes = [PRIMARY_OUTCOME, *SECONDARY_OUTCOMES]
    summaries = {arm: {"n": len(group), **{
        outcome: mean([run["outcomes"][outcome] for run in group]) for outcome in outcomes}}
        for arm, group in groups.items()}
    contrasts = [("evidence_thought", "placebo"), ("evidence_thought", "baseline"),
                 ("placebo", "baseline")]
    effects = {}
    for treatment, control in contrasts:
        contrast = f"{treatment}_vs_{control}"
        effects[contrast] = {}
        for outcome in outcomes:
            a = [run["outcomes"][outcome] for run in groups[treatment]]
            b = [run["outcomes"][outcome] for run in groups[control]]
            effects[contrast][outcome] = compare_outcomes(
                a, b, _derived_seed(protocol["design"]["seed"], f"{contrast}:{outcome}"), resamples)
            effects[contrast][outcome]["confirmatory_primary"] = (
                contrast == "evidence_thought_vs_placebo" and outcome == PRIMARY_OUTCOME)
    return {"arms": summaries, "effects": effects,
            "primary_effect": effects["evidence_thought_vs_placebo"][PRIMARY_OUTCOME],
            "censoring": {arm: sum(run["outcomes"]["terminated_by"] == "step_budget"
                                   for run in groups[arm]) for arm in ARMS},
            "initial_state_balance": {arm: {
                "initial_valid_count": sum(run["outcomes"]["initial_valid"] for run in groups[arm]),
                "defect_modes": {mode: sum(run["outcomes"]["initial_defect"] == mode for run in groups[arm])
                                 for mode in ("none", "missing_entry", "wrong_quantity")},
            } for arm in ARMS},
            "warnings": [
                "Inference unit is the swarm run, not individual messages or agents.",
                "Only the active-versus-placebo success comparison is confirmatory; other comparisons are exploratory.",
                "Small pilot samples do not establish transportability across tasks, models, harnesses or network structures.",
                "Bootstrap intervals may degenerate at binary ceilings; the primary binary interval uses Wilson-based Newcombe bounds.",
            ]}


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


class ExperimentExecutionError(RuntimeError):
    """Preserves partial results without treating infrastructure attrition as data."""

    def __init__(self, message: str, partial_report: dict[str, Any]):
        super().__init__(message)
        self.partial_report = partial_report


def run_experiment(protocol: dict[str, Any],
                   agent_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
                   output_dir: str | Path | None = None,
                   on_progress: Callable[[dict[str, Any]], None] | None = None,
                   backend_metadata: dict[str, Any] | None = None,
                   resamples: int = 2000) -> dict[str, Any]:
    """Execute fresh state for each randomized run and save audit-ready artifacts.

    A real backend callable must provide a *fresh stateless subject decision* per
    request, or key persistent sessions by independent run and subject externally.
    It must not store cross-run conversational memory. This callable contract is an
    execution assumption recorded here, not an automatically enforced property of
    a remote service. Do not put API keys in backend_metadata.
    """
    validate_protocol(protocol)
    protocol = copy.deepcopy(protocol)
    runner = agent_runner or offline_policy
    output = Path(output_dir) if output_dir is not None else None
    assignments = randomize_runs(protocol)
    report = {
        "api_version": EXPERIMENT_API_VERSION,
        "experiment_id": f"experiment-{protocol['protocol_hash'][:16]}",
        "protocol_hash": protocol["protocol_hash"], "protocol": protocol,
        "started_at": _utc_now(), "finished_at": None,
        "status": "running", "assignments": assignments, "runs": [],
        "backend": {
            "mode": "scripted_offline_smoke_test" if agent_runner is None else "provided_agent_runner",
            "metadata": copy.deepcopy(backend_metadata or {}),
            "python": platform.python_version(),
            "fresh_state_contract": "No persistent subject state between independent swarm runs",
            "registered_spec": copy.deepcopy(protocol.get("subject_backend", {})),
        },
        "evidence_scope": (
            "Scripted subject response rules are simulation assumptions; this test demonstrates mechanics, not actual LLM behavior."
            if agent_runner is None else
            "Randomized comparison of the provided subjects in the specified synthetic environment; no historical causal claim."
        ),
        "local_protocol_written_before_subject_calls": output is not None,
    }
    if output:
        protocol_path = output / "protocol.json"
        if protocol_path.exists():
            previous = json.loads(protocol_path.read_text(encoding="utf-8"))
            if previous != protocol:
                raise ValueError("Output directory contains a different frozen protocol")
        if (output / "report.json").exists():
            raise ValueError("Output directory already contains results; choose a new run directory")
        _write_json(protocol_path, protocol)
        _write_json(output / "assignment.json", assignments)
        _write_json(output / "progress.json", report)
    if agent_runner is not None and protocol.get("subject_backend", {}).get("status") == "not_yet_pinned":
        report["execution_warning"] = "Subject model/harness were not pinned in the frozen protocol; backend metadata must be reviewed before interpreting effects."
    for assignment in assignments:
        environment = create_environment(protocol["environment"], assignment["environment_seed"])
        initial = environment.snapshot()
        turns = []
        insertion_delivered = False
        try:
            contract = check_environment_contract(environment)
            if not contract["passed"]:
                raise RuntimeError("Environment contract checks failed")
            while not environment.terminal:
                agent = environment.next_agent
                if agent == protocol["intervention"]["recipient"] and not insertion_delivered:
                    insertion = protocol["arms"][assignment["arm"]]["insertion"]
                    if insertion is not None:
                        environment.inject_context(agent, insertion)
                    insertion_delivered = True
                request = subject_request(environment, agent)
                action = runner(copy.deepcopy(request))
                result = environment.step(agent, action)
                turns.append({"step": environment.step_count - 1, "agent_id": agent,
                              "request": request, "action": copy.deepcopy(action),
                              "tool_result": result})
        except Exception as exc:
            report["status"] = "incomplete_infrastructure_failure"
            report["finished_at"] = _utc_now()
            # Exception text could contain provider secrets or raw prompts. Persist
            # only its class and the location; callers can inspect their own logs.
            report["failure"] = {"run_id": assignment["run_id"],
                                 "error_type": type(exc).__name__,
                                 "completed_steps": environment.step_count}
            report["incomplete_run"] = {**copy.deepcopy(assignment), "turns": turns,
                                        "state": environment.snapshot()}
            if output:
                _write_json(output / "report.json", report)
            raise ExperimentExecutionError(
                f"Subject execution failed in {assignment['run_id']} ({type(exc).__name__}); no effects estimated",
                report) from exc
        run = {**copy.deepcopy(assignment), "initial_state": initial,
               "final_state": environment.snapshot(), "turns": turns,
               "environment_contract": contract,
               "context_insertion_delivered": insertion_delivered,
               "outcomes": environment.evaluate()}
        report["runs"].append(run)
        if output:
            _write_json(output / "runs" / f"{assignment['run_id']}.json", run)
            _write_json(output / "progress.json", report)
        if on_progress:
            try:
                on_progress({"completed": len(report["runs"]), "total": len(assignments),
                             "run_id": assignment["run_id"], "arm": assignment["arm"],
                             "outcomes": copy.deepcopy(run["outcomes"])})
            except Exception as exc:
                # Reporting callbacks cannot silently remove experimental units.
                report.setdefault("reporting_warnings", []).append({
                    "run_id": assignment["run_id"], "callback_error_type": type(exc).__name__})
    report["analysis"] = summarize_runs(report["runs"], protocol, resamples)
    report["status"] = "complete"
    report["finished_at"] = _utc_now()
    report["report_hash"] = _hash(report)
    if output:
        _write_json(output / "report.json", report)
        _write_json(output / "progress.json", report)
    return report


def create_replication_protocol(original: dict[str, Any], new_seed: int,
                                trials_per_arm: int | None = None) -> dict[str, Any]:
    """Hold outcomes, wording and environment fixed; preregister fresh run seeds.

    This is a held-out *environment-seed replication*, not cross-task or cross-model
    validation. Claims of those broader replications require additional designs.
    """
    validate_protocol(original)
    if new_seed == original["design"]["seed"]:
        raise ValueError("Replication requires a different seed namespace")
    body = copy.deepcopy(original)
    body.pop("protocol_hash", None)
    body["created_at"] = _utc_now()
    body["phase"] = "held_out_environment_seed_replication"
    body["replicates_protocol_hash"] = original["protocol_hash"]
    body["design"]["seed"] = new_seed
    if trials_per_arm is not None:
        if not isinstance(trials_per_arm, int) or isinstance(trials_per_arm, bool) or not 2 <= trials_per_arm <= 1000:
            raise ValueError("Invalid replication sample size")
        body["design"]["trials_per_arm"] = trials_per_arm
    replication = _seal_protocol(body)
    old_seeds = {run["environment_seed"] for run in randomize_runs(original)}
    new_seeds = {run["environment_seed"] for run in randomize_runs(replication)}
    if old_seeds & new_seeds:
        raise ValueError("Replication seed overlap; choose another namespace")
    return replication


def protocol_plain_language(protocol: dict[str, Any]) -> str:
    validate_protocol(protocol, check_code=False)
    n = protocol["design"]["trials_per_arm"]
    return (
        f"Randomly assign {n * len(ARMS)} independent three-agent teams, {n} per arm, "
        "to ordinary context, a neutral private note, or an evidence-check reminder. "
        "Insert the note before the coordinator's first decision. The primary question "
        "is whether the reminder changes the proportion of correctly published manifests "
        "relative to the neutral note. Check actual contents in code. Treat the whole "
        "team as one sample because members can influence one another. Report uncertainty "
        "and test again on fresh seeds. This simplified task does not recreate the Village."
    )
