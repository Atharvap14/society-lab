"""A provenance-preserving information-diffusion environment.

Four subjects observe noisy binary reports. Distinct report IDs can share a single
original source and therefore share a measurement error. The environment enforces
communication topology, preserves evidence lineage, and evaluates final verdicts
against a truth that is never supplied to subjects. This is a synthetic experiment,
not a reconstruction of the AI Village's latent beliefs or historical outcomes.
"""
from __future__ import annotations

import copy
import hashlib
import json
import random
from typing import Any


DIFFUSION_ENVIRONMENT_VERSION = "1.0"
SUBJECTS = tuple(f"agent-{index}" for index in range(4))
TOPOLOGIES = ("ring", "star", "complete")
ACTION_SCHEMA = {
    "type": "object", "required": ["action"],
    "properties": {
        "action": {"type": "string", "enum": ["inspect_report", "send_message", "submit_verdict", "wait"]},
        "report_id": {"type": "string"},
        "recipient": {"type": "string", "enum": list(SUBJECTS)},
        "message": {"type": "string", "maxLength": 1500},
        "decision": {"type": "integer", "enum": [0, 1]},
        "rationale": {"type": "string", "maxLength": 1500},
    },
    "additionalProperties": False,
    "instructions": (
        "inspect_report requires your assigned report_id. send_message requires a "
        "permitted recipient and message; optional report_id attaches a report you "
        "have inspected or received with unchanged original source and lineage. "
        "submit_verdict requires decision 0 or 1; optional rationale explains it. "
        "Your first verdict is final. wait needs only action."
    ),
}
FIDELITY = {
    "interaction": "explicit_undirected_direct_message_graph",
    "world_execution": "seeded_noisy_measurements_and_state_machine",
    "information": "private_reports_and_recipient_scoped_messages",
    "incentives": "shared_mean_verdict_accuracy",
    "agent_continuity": "within_run_private_context_and_own_action_history",
}


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False).encode()).hexdigest()


def topology_edges(kind: str) -> list[list[str]]:
    if kind == "ring":
        return [[SUBJECTS[index], SUBJECTS[(index + 1) % len(SUBJECTS)]] for index in range(4)]
    if kind == "star":
        return [[SUBJECTS[0], peer] for peer in SUBJECTS[1:]]
    if kind == "complete":
        return [[SUBJECTS[left], SUBJECTS[right]] for left in range(4) for right in range(left + 1, 4)]
    raise ValueError("Unknown built-in topology")


def create_diffusion_spec(*, topology: str = "ring", max_rounds: int = 3,
                          source_reliability: float = .75,
                          custom_edges: list[list[str]] | None = None,
                          incident: dict[str, Any] | None = None) -> dict[str, Any]:
    if custom_edges is not None:
        topology, edges = "custom", copy.deepcopy(custom_edges)
    else:
        edges = topology_edges(topology)
    source = incident or {}
    spec = {
        "api_version": DIFFUSION_ENVIRONMENT_VERSION,
        "kind": "provenance_diffusion", "version": "1.0",
        "agents": list(SUBJECTS), "max_rounds": max_rounds,
        "max_messages_per_agent": max_rounds - 2,
        "topology": {"kind": topology, "directed": False, "edges": edges},
        "fidelity": copy.deepcopy(FIDELITY),
        "measurement_world": {
            "truth_prior": .5, "source_reliability": source_reliability,
            "independent_original_sources": 3,
            "source_copy_multiplicities": [2, 1, 1],
            "assignment": "seeded_random_permutation_of_report_holders",
            "errors": "independent_between_original_sources_shared_by_copies",
        },
        "scheduler": "seeded_shuffled_round_robin",
        "incident_provenance": {key: copy.deepcopy(source[key])
                                for key in ("id", "title", "source_refs") if key in source},
        "limitations": [
            "Synthetic binary sensors represent provenance dependence, not truth in a real historical episode.",
            "Different source IDs are genuinely independent by construction here; real-world distinct sources may remain dependent.",
            "Evidence attachments cannot forge a sensor reading, although free-text messages can contain unsupported claims.",
            "Topologies have different degree and path length; equal total action/message budgets do not equalize information access.",
            "Four participants, equal sensor reliability, no cost conflict, browser tools or persistent cross-run memory are modeled.",
        ],
    }
    validate_diffusion_spec(spec)
    return spec


def validate_diffusion_spec(spec: dict[str, Any]) -> None:
    if spec.get("api_version") != DIFFUSION_ENVIRONMENT_VERSION or spec.get("kind") != "provenance_diffusion":
        raise ValueError("Unsupported diffusion environment version or kind")
    if spec.get("agents") != list(SUBJECTS):
        raise ValueError("Diffusion environment requires exactly four declared subjects")
    rounds = spec.get("max_rounds")
    if not isinstance(rounds, int) or isinstance(rounds, bool) or not 3 <= rounds <= 30:
        raise ValueError("max_rounds must be an integer between 3 and 30")
    if spec.get("max_messages_per_agent") != rounds - 2:
        raise ValueError("Message cap is fixed across topology at max_rounds minus two")
    if spec.get("fidelity") != FIDELITY or spec.get("scheduler") != "seeded_shuffled_round_robin":
        raise ValueError("Unimplemented fidelity or scheduler")
    world = spec.get("measurement_world", {})
    reliability = world.get("source_reliability")
    if isinstance(reliability, bool) or not isinstance(reliability, (int, float)) or not .5 <= reliability <= 1:
        raise ValueError("Source reliability must be between .5 and 1")
    fixed = {"truth_prior": .5, "independent_original_sources": 3,
             "source_copy_multiplicities": [2, 1, 1],
             "assignment": "seeded_random_permutation_of_report_holders",
             "errors": "independent_between_original_sources_shared_by_copies"}
    if any(world.get(key) != value for key, value in fixed.items()) or set(world) != {*fixed, "source_reliability"}:
        raise ValueError("Unsupported source-generation parameters")
    graph = spec.get("topology", {})
    if graph.get("directed") is not False or graph.get("kind") not in (*TOPOLOGIES, "custom"):
        raise ValueError("Topology must be an implemented undirected graph")
    edges = graph.get("edges")
    if not isinstance(edges, list):
        raise ValueError("Topology edges must be a list")
    normalized = set()
    for edge in edges:
        if not isinstance(edge, list) or len(edge) != 2 or any(node not in SUBJECTS for node in edge) or edge[0] == edge[1]:
            raise ValueError("Invalid topology edge")
        pair = tuple(sorted(edge))
        if pair in normalized:
            raise ValueError("Duplicate topology edge")
        normalized.add(pair)
    if graph["kind"] in TOPOLOGIES:
        expected = {tuple(sorted(edge)) for edge in topology_edges(graph["kind"])}
        if normalized != expected:
            raise ValueError("Built-in topology edges must match the declared topology")


class ProvenanceDiffusionEnvironment:
    def __init__(self, spec: dict[str, Any], seed: int):
        validate_diffusion_spec(spec)
        self.spec = copy.deepcopy(spec)
        self.seed = seed
        self.reset(seed)

    def reset(self, seed: int | None = None) -> dict[str, Any]:
        if seed is not None:
            self.seed = int(seed)
        rng = random.Random(self.seed)
        self.truth = rng.randrange(2)
        reliability = self.spec["measurement_world"]["source_reliability"]
        self.source_signals = {f"source-{index}": self.truth if rng.random() < reliability else 1 - self.truth
                               for index in range(3)}
        copies = ["source-0", "source-0", "source-1", "source-2"]
        rng.shuffle(copies)
        self.reports = {
            agent: {"report_id": f"report-{agent}", "source_id": source,
                    "signal": self.source_signals[source], "source_reliability": reliability,
                    "original_holder": agent, "lineage": [{"kind": "original_measurement", "source_id": source}]}
            for agent, source in zip(SUBJECTS, copies)
        }
        self.neighbors = {agent: [] for agent in SUBJECTS}
        for left, right in self.spec["topology"]["edges"]:
            self.neighbors[left].append(right)
            self.neighbors[right].append(left)
        for values in self.neighbors.values():
            values.sort()
        self.known_reports: dict[str, dict[str, dict[str, Any]]] = {agent: {} for agent in SUBJECTS}
        self.private_context: dict[str, list[str]] = {agent: [] for agent in SUBJECTS}
        self.messages: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.verdicts: dict[str, dict[str, Any]] = {}
        self.sent_count = {agent: 0 for agent in SUBJECTS}
        self.turn_count = {agent: 0 for agent in SUBJECTS}
        self.last_result = {agent: None for agent in SUBJECTS}
        self.step_count = 0
        self.schedule = []
        for _ in range(self.spec["max_rounds"]):
            order = list(SUBJECTS)
            rng.shuffle(order)
            self.schedule.extend(order)
        return self.snapshot()

    @property
    def terminal(self) -> bool:
        return len(self.verdicts) == len(SUBJECTS) or self.step_count >= len(self.schedule)

    @property
    def next_agent(self) -> str | None:
        return None if self.terminal else self.schedule[self.step_count]

    def _check_agent(self, agent_id: str) -> None:
        if agent_id not in SUBJECTS:
            raise ValueError("Unknown subject")

    def inject_context(self, agent_id: str, text: str) -> None:
        self._check_agent(agent_id)
        if self.terminal:
            raise RuntimeError("Cannot insert context after termination")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Private insertion requires text")
        self.private_context[agent_id].append(text)
        self.events.append({"type": "context_insertion", "agent_id": agent_id,
                            "step": self.step_count, "text": text})

    def observe(self, agent_id: str) -> dict[str, Any]:
        self._check_agent(agent_id)
        return copy.deepcopy({
            "agent_id": agent_id, "participants": list(SUBJECTS),
            "task": "Infer the hidden binary state and submit a final decision 0 or 1. Team performance is mean accuracy; a missing verdict counts as unsuccessful.",
            "measurement_rules": (
                "There are three original sensors with independent errors and equal known reliability. "
                "Four assigned report copies include one duplicated source. Reports with the same "
                "source_id describe the same measurement and share its error. Inspect your report "
                "to learn its source and signal; permitted messages can transmit evidence."
            ),
            "source_reliability": self.spec["measurement_world"]["source_reliability"],
            "your_assigned_report_id": self.reports[agent_id]["report_id"],
            "known_reports": list(self.known_reports[agent_id].values()),
            "permitted_recipients": self.neighbors[agent_id],
            "received_messages": [message for message in self.messages if message["recipient"] == agent_id],
            "your_sent_messages": [message for message in self.messages if message["sender"] == agent_id],
            "messages_remaining": self.spec["max_messages_per_agent"] - self.sent_count[agent_id],
            "your_verdict": self.verdicts.get(agent_id),
            "step": self.step_count, "max_steps": len(self.schedule),
            "your_turns_remaining": self.schedule[self.step_count:].count(agent_id),
            "your_private_context": self.private_context[agent_id],
            "your_last_tool_result": self.last_result[agent_id],
            "your_action_history": [{"step": event["step"], "action": event["action"], "result": event["result"]}
                                    for event in self.events if event["type"] == "action" and event["agent_id"] == agent_id],
        })

    def _finish(self, agent_id: str, action: Any, result: dict[str, Any]) -> dict[str, Any]:
        self.events.append({"type": "action", "step": self.step_count, "agent_id": agent_id,
                            "action": copy.deepcopy(action), "result": copy.deepcopy(result)})
        self.last_result[agent_id] = copy.deepcopy(result)
        self.step_count += 1
        self.turn_count[agent_id] += 1
        return copy.deepcopy(result)

    def step(self, agent_id: str, action: dict[str, Any]) -> dict[str, Any]:
        self._check_agent(agent_id)
        if self.terminal:
            raise RuntimeError("Environment is terminal")
        if agent_id != self.next_agent:
            raise ValueError("Action does not match declared scheduler")
        invalid = lambda reason: self._finish(agent_id, action, {"ok": False, "error": reason})
        if not isinstance(action, dict) or not isinstance(action.get("action"), str):
            return invalid("Return an action object")
        name = action["action"]
        fields = {"inspect_report": {"action", "report_id"},
                  "send_message": {"action", "recipient", "message", "report_id"},
                  "submit_verdict": {"action", "decision", "rationale"}, "wait": {"action"}}
        if name not in fields or set(action) - fields[name]:
            return invalid("Unknown action or unsupported fields")
        if name == "inspect_report":
            if action.get("report_id") != self.reports[agent_id]["report_id"]:
                return invalid("You can inspect only your assigned report")
            report = copy.deepcopy(self.reports[agent_id])
            report["lineage"].append({"kind": "inspection", "agent_id": agent_id, "step": self.step_count})
            self.known_reports[agent_id][report["report_id"]] = report
            result = {"ok": True, "report": report}
        elif name == "send_message":
            recipient, message = action.get("recipient"), action.get("message")
            if recipient not in self.neighbors[agent_id]:
                return invalid("Recipient is not connected to you")
            if self.sent_count[agent_id] >= self.spec["max_messages_per_agent"]:
                return invalid("Your declared message budget is exhausted")
            if not isinstance(message, str) or not message.strip() or len(message) > 1500:
                return invalid("message must contain at most 1500 characters")
            report_id = action.get("report_id")
            if report_id is not None and not isinstance(report_id, str):
                return invalid("report_id must be a string")
            if report_id is not None and report_id not in self.known_reports[agent_id]:
                return invalid("You can attach only a report you have inspected or received")
            message_id = f"message-{len(self.messages) + 1}"
            attached = None
            if report_id is not None:
                attached = copy.deepcopy(self.known_reports[agent_id][report_id])
                attached["lineage"].append({"kind": "message", "message_id": message_id,
                                           "sender": agent_id, "recipient": recipient, "step": self.step_count})
                self.known_reports[recipient][report_id] = copy.deepcopy(attached)
            sent = {"message_id": message_id, "step": self.step_count, "sender": agent_id,
                    "recipient": recipient, "message": message, "attached_report": attached}
            self.messages.append(sent)
            self.sent_count[agent_id] += 1
            result = {"ok": True, "message_id": message_id}
        elif name == "submit_verdict":
            decision, rationale = action.get("decision"), action.get("rationale", "")
            if not isinstance(decision, int) or isinstance(decision, bool) or decision not in (0, 1):
                return invalid("decision must be integer 0 or 1")
            if not isinstance(rationale, str) or len(rationale) > 1500:
                return invalid("rationale must be at most 1500 characters")
            if agent_id in self.verdicts:
                return invalid("Your submitted verdict is final")
            self.verdicts[agent_id] = {"decision": decision, "rationale": rationale,
                                       "step": self.step_count,
                                       "source_ids_available": sorted({report["source_id"] for report in self.known_reports[agent_id].values()}),
                                       "report_ids_available": sorted(self.known_reports[agent_id])}
            result = {"ok": True, "verdict_recorded": True}
        else:
            result = {"ok": True, "waited": True}
        return self._finish(agent_id, action, result)

    def evaluate(self, focal_agent: str = "agent-0") -> dict[str, Any]:
        self._check_agent(focal_agent)
        accurate = {agent: int(agent in self.verdicts and self.verdicts[agent]["decision"] == self.truth)
                    for agent in SUBJECTS}
        attached = [message["attached_report"] for message in self.messages if message["attached_report"]]
        duplicate_receptions = 0
        seen = {agent: set() for agent in SUBJECTS}
        for message in self.messages:
            report = message["attached_report"]
            if report:
                duplicate_receptions += report["source_id"] in seen[message["recipient"]]
                seen[message["recipient"]].add(report["source_id"])
        independent_counts = {agent: len({report["source_id"] for report in self.known_reports[agent].values()})
                              for agent in SUBJECTS}
        full_information = int(sum(self.source_signals.values()) >= 2)
        action_events = [event for event in self.events if event["type"] == "action"]
        return {
            "mean_accuracy": sum(accurate.values()) / len(SUBJECTS),
            "focal_accuracy": accurate[focal_agent],
            "completion_rate": len(self.verdicts) / len(SUBJECTS),
            "messages_sent": len(self.messages), "steps_used": self.step_count,
            "invalid_actions": sum(not event["result"]["ok"] for event in action_events),
            "mean_independent_sources_visible": sum(independent_counts.values()) / len(SUBJECTS),
            "mean_independent_sources_at_verdict": sum(len(verdict["source_ids_available"])
                                                      for verdict in self.verdicts.values()) / len(SUBJECTS),
            "duplicate_source_reception_fraction": duplicate_receptions / len(attached) if attached else 0,
            "full_information_majority_correct": int(full_information == self.truth),
            "per_agent_accuracy": accurate, "independent_sources_visible": independent_counts,
            "terminated_by": "all_verdicts" if len(self.verdicts) == len(SUBJECTS) else (
                "step_budget" if self.terminal else "not_terminal"),
        }

    def snapshot(self) -> dict[str, Any]:
        """Privileged research state includes oracle truth; never send to subjects."""
        return copy.deepcopy({
            "seed": self.seed, "spec_hash": fingerprint(self.spec), "truth": self.truth,
            "source_signals": self.source_signals, "reports": self.reports,
            "known_reports": self.known_reports, "neighbors": self.neighbors,
            "private_context": self.private_context, "messages": self.messages,
            "events": self.events, "verdicts": self.verdicts,
            "step_count": self.step_count, "schedule": self.schedule,
            "sent_count": self.sent_count, "turn_count": self.turn_count,
        })


def create_diffusion_environment(spec: dict[str, Any] | None = None,
                                 seed: int = 0) -> ProvenanceDiffusionEnvironment:
    return ProvenanceDiffusionEnvironment(spec or create_diffusion_spec(), seed)


def diffusion_subject_request(environment: ProvenanceDiffusionEnvironment,
                              agent_id: str) -> dict[str, Any]:
    observation = environment.observe(agent_id)
    return {
        "role": agent_id,
        "system": ("You are a member of a four-agent team inferring a hidden binary state. "
                   "Take one legal action at a time, use your available evidence and communicate "
                   "as you judge useful. Return exactly one JSON action object. " + ACTION_SCHEMA["instructions"]),
        "context": observation.pop("your_private_context"),
        "observation": observation, "action_schema": copy.deepcopy(ACTION_SCHEMA),
    }


def diffusion_environment_capabilities() -> dict[str, Any]:
    return {"api_version": DIFFUSION_ENVIRONMENT_VERSION,
            "implemented_kinds": ["provenance_diffusion"], "topologies": [*TOPOLOGIES, "custom"],
            "fidelity": copy.deepcopy(FIDELITY),
            "factory_parameters": ["topology", "max_rounds", "source_reliability", "custom_edges"],
            "operations": ["construct", "validate", "reset", "observe", "step",
                           "inject_private_context", "snapshot_for_researcher", "evaluate"],
            "matched_budgets": "Four subjects, same round count and per-subject message cap across topology",
            "not_matched": "Neighbor choices, degree, shortest path length and achieved evidence access"}


def check_diffusion_contract(environment: ProvenanceDiffusionEnvironment) -> dict[str, Any]:
    """Check executable boundaries, preserving exactly the fresh starting state."""
    if environment.step_count or any(environment.private_context.values()):
        raise ValueError("Diffusion contract checks require a fresh environment")
    before = environment.snapshot()
    checks = []
    try:
        checks.append({"name": "initial_private_reports_hidden", "passed": all(
            not environment.observe(agent)["known_reports"] for agent in SUBJECTS)})
        checks.append({"name": "oracle_not_in_subject_observation", "passed": all(
            "truth" not in environment.observe(agent) and "source_signals" not in environment.observe(agent)
            for agent in SUBJECTS)})
        consistent = all(report["signal"] == environment.source_signals[report["source_id"]]
                         for report in environment.reports.values())
        checks.append({"name": "shared_source_copy_consistency", "passed": consistent})
        environment.inject_context("agent-0", "CONTRACT_PRIVATE_MARKER")
        checks.append({"name": "private_context_isolation", "passed": all(
            "CONTRACT_PRIVATE_MARKER" not in json.dumps(diffusion_subject_request(environment, agent))
            for agent in SUBJECTS if agent != "agent-0")})
        agent = environment.next_agent
        environment.step(agent, {"action": "inspect_report", "report_id": f"report-{agent}"})
        checks.append({"name": "inspection_access_scope", "passed": bool(environment.known_reports[agent]) and all(
            not environment.known_reports[other] for other in SUBJECTS if other != agent)})
    finally:
        reset = environment.reset(before["seed"])
    checks.append({"name": "exact_reset", "passed": reset == before})
    return {"passed": all(check["passed"] for check in checks), "checks": checks,
            "scope": "Boundary smoke checks; not proof of social fidelity, source independence in real data, or absence of every confound"}


def offline_diffusion_policy(request: dict[str, Any]) -> dict[str, Any]:
    """Scripted test policy; reminder-induced deduplication is an assumption."""
    observation = request["observation"]
    own_report = observation["your_assigned_report_id"]
    if observation["your_verdict"] is not None:
        return {"action": "wait"}
    if own_report not in {report["report_id"] for report in observation["known_reports"]}:
        return {"action": "inspect_report", "report_id": own_report}
    if observation["your_turns_remaining"] > 1 and observation["messages_remaining"]:
        previous = {(message["recipient"], message["attached_report"]["report_id"])
                    for message in observation["your_sent_messages"] if message["attached_report"]}
        for recipient in observation["permitted_recipients"]:
            for report in observation["known_reports"]:
                if (recipient, report["report_id"]) not in previous:
                    return {"action": "send_message", "recipient": recipient,
                            "report_id": report["report_id"],
                            "message": f"Report {report['report_id']} from original {report['source_id']} says {report['signal']}."}
    reports = list(observation["known_reports"])
    private_text = " ".join(request.get("context", [])).lower()
    if "source" in private_text and "duplicat" in private_text:
        reports = list({report["source_id"]: report for report in reports}.values())
    positives = sum(report["signal"] for report in reports)
    if positives * 2 == len(reports):
        decision = next(report["signal"] for report in observation["known_reports"] if report["report_id"] == own_report)
    else:
        decision = int(positives * 2 > len(reports))
    return {"action": "submit_verdict", "decision": decision,
            "rationale": "Scripted majority of visible reports; ties use my assigned signal."}
