"""Complementary-information network world, ready for causal protocol review.

Four private, exact integer residues jointly determine an exact modular total. The
subject interface has no oracle, seed, peer-inspection tool or global transcript.
Canonical attachments preserve original values and explicit forwarding lineage;
free text can contain unsupported claims. A topology manipulation changes an
information-opportunity bundle, not degree alone or an identified mechanism.
"""
from __future__ import annotations

import copy
import hashlib
import json
import random
from typing import Any


COMPLEMENTARY_ENVIRONMENT_VERSION = "1.0"
SUBJECTS = tuple(f"agent-{index}" for index in range(4))
TOPOLOGIES = ("ring", "star", "complete")
FIDELITY = {
    "interaction": "explicit_undirected_direct_message_graph",
    "world_execution": "seeded_exact_complementary_modular_integer_measurements",
    "information": "one_unique_private_original_per_subject_recipient_scoped_relays",
    "incentives": "whole_network_mean_exact_total_accuracy_missing_zero",
    "agent_continuity": "within_run_private_context_and_own_action_history",
}
ACTION_SCHEMA = {
    "type": "object", "required": ["action"],
    "properties": {
        "action": {"type": "string", "enum": ["inspect_fragment", "send_message", "send_neighbors", "submit_total", "wait"]},
        "fragment_id": {"type": "string"},
        "recipient": {"type": "string", "enum": list(SUBJECTS)},
        "fragment_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 4, "uniqueItems": True},
        "message": {"type": "string", "maxLength": 1500},
        "total": {"type": "integer", "minimum": 0, "maximum": 999999},
        "rationale": {"type": "string", "maxLength": 1500},
    },
    "additionalProperties": False,
    "instructions": (
        "Your own original is already privately visible. inspect_fragment requires your assigned fragment_id and reopens only your original. "
        "send_message requires a permitted recipient and message; optional fragment_ids attaches "
        "only originals you have inspected or received, with values and lineage supplied by the "
        "environment. send_neighbors requires message and optional fragment_ids and delivers the same bundle to every permitted neighbor, consuming one message action. You may relay several known fragments in one message. Free-text claims "
        "are not verified measurements. submit_total requires an integer total; optional rationale "
        "explains it. Your first valid total is final and cannot be changed. wait needs only action."
    ),
}


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _rng(seed, purpose):
    # Independent random streams prevent topology and scheduler edits from
    # silently changing measurements. The seed is privileged researcher state.
    return random.Random(int(fingerprint([seed, purpose]), 16))


def topology_edges(kind: str) -> list[list[str]]:
    if kind == "ring":
        return [[SUBJECTS[i], SUBJECTS[(i + 1) % 4]] for i in range(4)]
    if kind == "star":
        return [[SUBJECTS[0], other] for other in SUBJECTS[1:]]
    if kind == "complete":
        return [[SUBJECTS[left], SUBJECTS[right]] for left in range(4) for right in range(left + 1, 4)]
    raise ValueError("Unknown complementary-information topology")


def create_complementary_spec(*, topology: str = "ring", max_rounds: int = 3,
                              max_messages_per_agent: int | None = None,
                              modulus: int = 97, component_min: int = 0, component_max: int | None = None,
                              custom_edges: list[list[str]] | None = None,
                              incident: dict | None = None) -> dict:
    if custom_edges is not None:
        topology, edges = "custom", copy.deepcopy(custom_edges)
    else:
        edges = topology_edges(topology)
    source = incident or {}
    spec = {"api_version": COMPLEMENTARY_ENVIRONMENT_VERSION, "kind": "complementary_information", "version": "1.0",
            "agents": list(SUBJECTS), "max_rounds": max_rounds,
            "max_messages_per_agent": max_rounds - 1 if max_messages_per_agent is None else max_messages_per_agent,
            "topology": {"kind": topology, "directed": False, "edges": edges},
            "measurement_world": {"originals": 4, "components_per_agent": 1, "component_min": component_min,
                                  "component_max": modulus - 1 if component_max is None else component_max,
                                  "modulus": modulus, "distribution": "independent_uniform_residue_modulo_modulus",
                                  "assignment": "one_unique_original_per_declared_agent", "target": "sum_of_four_original_values_modulo_modulus",
                                  "initial_visibility": "own_original_visible", "measurement_error": "none", "public_seed": False},
            "scheduler": "seeded_shuffled_round_robin_independent_of_measurements", "fidelity": copy.deepcopy(FIDELITY),
            "incident_provenance": {key: copy.deepcopy(source[key]) for key in ("id", "title", "source_refs") if key in source},
            "limitations": ["Synthetic modular integer aggregation is an information task, not reconstruction of a historical agent society.",
                            "Every strict subset of independent uniform residues leaves the total uniform over the modulus; chance accuracy is 1/modulus. A lucky guess can still be correct.",
                            "Topology changes neighbor choices, degree, path length, brokerage opportunity and achieved information; it does not isolate a fixed-degree network effect.",
                            "Equal allocated turns and message-action caps do not equalize recipient deliveries, timing or successful evidence access; neighbor multicast fanout varies with degree.",
                            "Canonical attachments preserve measurements; free text remains unverified and need not be truthful.",
                            "Four subjects, exact measurements, immediate delivery, no cost conflict or external tools are modeled."]}
    validate_complementary_spec(spec)
    return spec


def validate_complementary_spec(spec: dict) -> None:
    if not isinstance(spec, dict) or spec.get("api_version") != COMPLEMENTARY_ENVIRONMENT_VERSION or spec.get("kind") != "complementary_information" or spec.get("version") != "1.0":
        raise ValueError("Unsupported complementary-information version or kind")
    if spec.get("agents") != list(SUBJECTS):
        raise ValueError("Exactly four declared subjects are required")
    rounds, messages = spec.get("max_rounds"), spec.get("max_messages_per_agent")
    if type(rounds) is not int or not 3 <= rounds <= 30:
        raise ValueError("max_rounds must be an integer between 3 and 30")
    if type(messages) is not int or not 0 <= messages <= rounds - 1:
        raise ValueError("Per-agent message cap must be an integer between zero and max_rounds minus one")
    if spec.get("scheduler") != "seeded_shuffled_round_robin_independent_of_measurements" or spec.get("fidelity") != FIDELITY:
        raise ValueError("Unimplemented scheduler or fidelity")
    world = spec.get("measurement_world", {})
    expected = {"originals": 4, "components_per_agent": 1, "distribution": "independent_uniform_residue_modulo_modulus",
                "assignment": "one_unique_original_per_declared_agent", "target": "sum_of_four_original_values_modulo_modulus",
                "initial_visibility": "own_original_visible", "measurement_error": "none", "public_seed": False}
    if any(world.get(key) != value for key, value in expected.items()) or set(world) != {*expected, "component_min", "component_max", "modulus"}:
        raise ValueError("Unsupported measurement-world configuration")
    low, high = world["component_min"], world["component_max"]
    modulus = world["modulus"]
    if type(modulus) is not int or not 2 <= modulus <= 1000000 or type(low) is not int or type(high) is not int or low != 0 or high != modulus - 1:
        raise ValueError("Components must cover the complete nondegenerate residue range zero through modulus minus one")
    graph = spec.get("topology", {})
    if graph.get("kind") not in (*TOPOLOGIES, "custom") or graph.get("directed") is not False or not isinstance(graph.get("edges"), list):
        raise ValueError("Topology must declare an implemented undirected graph")
    normalized = set()
    for edge in graph["edges"]:
        if not isinstance(edge, list) or len(edge) != 2 or any(node not in SUBJECTS for node in edge) or edge[0] == edge[1]:
            raise ValueError("Invalid topology edge")
        pair = tuple(sorted(edge))
        if pair in normalized:
            raise ValueError("Duplicate topology edge")
        normalized.add(pair)
    if graph["kind"] in TOPOLOGIES and normalized != {tuple(sorted(edge)) for edge in topology_edges(graph["kind"])}:
        raise ValueError("Built-in edges do not match declared topology")


class ComplementaryInformationEnvironment:
    def __init__(self, spec: dict, seed: int):
        validate_complementary_spec(spec)
        self.spec = copy.deepcopy(spec)
        self.seed = seed
        self.reset(seed)

    def reset(self, seed: int | None = None) -> dict:
        if seed is not None:
            if type(seed) is not int or not 0 <= seed <= 2 ** 63 - 1:
                raise ValueError("seed must be a nonnegative integer below 2**63")
            self.seed = seed
        world, measurements = self.spec["measurement_world"], _rng(self.seed, "measurements")
        self.original_fragments = {}
        for i, agent in enumerate(SUBJECTS):
            original = {"fragment_id": f"fragment-{agent}", "original_id": f"original-{i}",
                        "component_index": i, "value": measurements.randint(world["component_min"], world["component_max"]),
                        "original_holder": agent}
            original["integrity_hash"] = fingerprint(original)
            original["lineage"] = [{"kind": "original_measurement", "original_id": original["original_id"], "holder": agent}]
            self.original_fragments[original["fragment_id"]] = original
        self.oracle_total = sum(fragment["value"] for fragment in self.original_fragments.values()) % world["modulus"]
        self.neighbors = {agent: [] for agent in SUBJECTS}
        for left, right in self.spec["topology"]["edges"]:
            self.neighbors[left].append(right)
            self.neighbors[right].append(left)
        for values in self.neighbors.values():
            values.sort()
        self.known_fragments = {agent: {} for agent in SUBJECTS}
        for agent in SUBJECTS:
            fragment = copy.deepcopy(self.original_fragments[f"fragment-{agent}"])
            fragment["lineage"].append({"kind": "initial_private_assignment", "agent_id": agent, "step": 0})
            self.known_fragments[agent][fragment["fragment_id"]] = fragment
        self.private_context = {agent: [] for agent in SUBJECTS}
        self.messages, self.events = [], []
        self.submissions = {}
        self.sent_count = {agent: 0 for agent in SUBJECTS}
        self.turn_count = {agent: 0 for agent in SUBJECTS}
        self.last_result = {agent: None for agent in SUBJECTS}
        self.step_count, self.dispatch_count, self.schedule = 0, 0, []
        scheduler = _rng(self.seed, "scheduler")
        for _ in range(self.spec["max_rounds"]):
            order = list(SUBJECTS)
            scheduler.shuffle(order)
            self.schedule.extend(order)
        return self.snapshot()

    @property
    def terminal(self) -> bool:
        return len(self.submissions) == 4 or self.step_count >= len(self.schedule)

    @property
    def next_agent(self) -> str | None:
        return None if self.terminal else self.schedule[self.step_count]

    def _check_agent(self, agent):
        if agent not in SUBJECTS:
            raise ValueError("Unknown subject")

    def inject_context(self, agent_id: str, text: str) -> None:
        self._check_agent(agent_id)
        if self.terminal:
            raise RuntimeError("Cannot insert private context after termination")
        if not isinstance(text, str) or not text.strip() or len(text) > 8000:
            raise ValueError("Private context must contain at most 8000 characters")
        self.private_context[agent_id].append(text)
        self.events.append({"type": "context_insertion", "agent_id": agent_id, "step": self.step_count, "text": text})

    def observe(self, agent_id: str) -> dict:
        self._check_agent(agent_id)
        world = self.spec["measurement_world"]
        return copy.deepcopy({"agent_id": agent_id, "participants": list(SUBJECTS),
            "task": "Every agent must submit the exact sum of all four original integer values modulo the declared modulus. Team performance is mean exact accuracy across all four agents; a missing submission counts as zero.",
            "measurement_rules": "Each participant uniquely holds one error-free original integer, already privately visible. The four originals are independently uniform residues modulo the declared modulus. Reinspect only your own fragment; obtain peer originals through permitted messages. Count each original_id once; a relay or duplicate reception does not create a new component. Free-text claims do not authenticate a measurement.",
            "modulus": world["modulus"],
            "component_range": {"minimum": world["component_min"], "maximum": world["component_max"]},
            "required_original_ids": [f"original-{i}" for i in range(4)],
            "fragment_ownership": {agent: f"fragment-{agent}" for agent in SUBJECTS},
            "your_assigned_fragment_id": f"fragment-{agent_id}",
            "known_fragments": list(self.known_fragments[agent_id].values()),
            "permitted_recipients": self.neighbors[agent_id],
            "received_messages": [message for message in self.messages if message["recipient"] == agent_id],
            "your_sent_messages": [message for message in self.messages if message["sender"] == agent_id],
            "messages_remaining": self.spec["max_messages_per_agent"] - self.sent_count[agent_id],
            "your_submission": self.submissions.get(agent_id),
            "step": self.step_count, "max_steps": len(self.schedule),
            "your_turns_remaining": self.schedule[self.step_count:].count(agent_id),
            "your_private_context": self.private_context[agent_id], "your_last_tool_result": self.last_result[agent_id],
            "your_action_history": [{"step": event["step"], "action": event["action"], "result": event["result"]}
                                    for event in self.events if event["type"] == "action" and event["agent_id"] == agent_id]})

    def _finish(self, agent, action, result):
        self.events.append({"type": "action", "step": self.step_count, "agent_id": agent,
                            "action": copy.deepcopy(action), "result": copy.deepcopy(result)})
        self.last_result[agent] = copy.deepcopy(result)
        self.step_count += 1
        self.turn_count[agent] += 1
        return copy.deepcopy(result)

    def step(self, agent_id: str, action: dict) -> dict:
        self._check_agent(agent_id)
        if self.terminal:
            raise RuntimeError("Environment is terminal")
        if agent_id != self.next_agent:
            raise ValueError("Action does not match the seeded scheduler")
        invalid = lambda reason: self._finish(agent_id, action, {"ok": False, "error": reason})
        fields = {"inspect_fragment": {"action", "fragment_id"}, "send_message": {"action", "recipient", "message", "fragment_ids"},
                  "send_neighbors": {"action", "message", "fragment_ids"},
                  "submit_total": {"action", "total", "rationale"}, "wait": {"action"}}
        if not isinstance(action, dict) or not isinstance(action.get("action"), str) or action["action"] not in fields or set(action) - fields[action["action"]]:
            return invalid("Return one supported action object with only its declared fields")
        name = action["action"]
        if name == "inspect_fragment":
            identity = f"fragment-{agent_id}"
            if action.get("fragment_id") != identity:
                return invalid("You can inspect only your assigned fragment")
            fragment = copy.deepcopy(self.original_fragments[identity])
            fragment["lineage"].append({"kind": "inspection", "agent_id": agent_id, "step": self.step_count})
            self.known_fragments[agent_id].setdefault(identity, fragment)
            result = {"ok": True, "fragment": copy.deepcopy(self.known_fragments[agent_id][identity])}
        elif name in ("send_message", "send_neighbors"):
            recipient, text, identities = action.get("recipient"), action.get("message"), action.get("fragment_ids", [])
            if name == "send_message" and recipient not in self.neighbors[agent_id]:
                return invalid("Recipient is not connected to you")
            recipients = list(self.neighbors[agent_id]) if name == "send_neighbors" else [recipient]
            if not recipients:
                return invalid("There are no connected recipients")
            if self.sent_count[agent_id] >= self.spec["max_messages_per_agent"]:
                return invalid("Your declared message budget is exhausted")
            if not isinstance(text, str) or not text.strip() or len(text) > 1500:
                return invalid("message must contain at most 1500 characters")
            if not isinstance(identities, list) or len(identities) > 4 or any(not isinstance(identity, str) for identity in identities) or len(set(identities)) != len(identities):
                return invalid("fragment_ids must be at most four unique strings")
            if any(identity not in self.known_fragments[agent_id] for identity in identities):
                return invalid("Attach only originals you have inspected or received")
            # Check the canonical immutable fields before any delivery. Incoming
            # actions cannot supply values, signatures, raw attachments or paths.
            immutable = ("fragment_id", "original_id", "component_index", "value", "original_holder", "integrity_hash")
            if any(any(self.known_fragments[agent_id][identity].get(key) != self.original_fragments[identity][key] for key in immutable) for identity in identities):
                return invalid("Known-fragment integrity failed; no attachments delivered")
            dispatch_id = f"dispatch-{self.dispatch_count + 1}"
            message_ids = []
            for recipient in recipients:
                message_id = f"message-{len(self.messages) + 1}"
                message_ids.append(message_id)
                attached = []
                for identity in identities:
                    fragment = copy.deepcopy(self.known_fragments[agent_id][identity])
                    fragment["lineage"].append({"kind": "message", "message_id": message_id, "dispatch_id": dispatch_id,
                                                "sender": agent_id, "recipient": recipient, "step": self.step_count})
                    attached.append(fragment)
                message = {"message_id": message_id, "dispatch_id": dispatch_id, "delivery_mode": "neighbors" if name == "send_neighbors" else "unicast",
                           "step": self.step_count, "sender": agent_id, "recipient": recipient,
                           "message": text, "claim_status": "unverified_free_text", "attached_fragments": attached}
                self.messages.append(message)
                for fragment in attached:
                    self.known_fragments[recipient].setdefault(fragment["fragment_id"], copy.deepcopy(fragment))
            self.sent_count[agent_id] += 1
            self.dispatch_count += 1
            result = {"ok": True, "dispatch_id": dispatch_id, "message_ids": message_ids, "recipients": recipients,
                      "message_actions_used": 1, "recipient_deliveries": len(recipients),
                      "attached_original_ids": [self.known_fragments[agent_id][identity]["original_id"] for identity in identities]}
        elif name == "submit_total":
            total, rationale = action.get("total"), action.get("rationale", "")
            if type(total) is not int or not 0 <= total < self.spec["measurement_world"]["modulus"]:
                return invalid("total must be an integer residue zero through modulus minus one")
            if not isinstance(rationale, str) or len(rationale) > 1500:
                return invalid("rationale must be at most 1500 characters")
            if agent_id in self.submissions:
                return invalid("Your first valid total is final")
            self.submissions[agent_id] = {"total": total, "rationale": rationale, "step": self.step_count,
                                          "original_ids_available": sorted({fragment["original_id"] for fragment in self.known_fragments[agent_id].values()})}
            # Immediate correctness feedback could reveal the target to peers.
            result = {"ok": True, "submission_recorded": True}
        else:
            result = {"ok": True, "waited": True}
        return self._finish(agent_id, action, result)

    def evaluate(self, focal_agent: str = "agent-0") -> dict:
        """Privileged research evaluation, never supplied to a subject tool."""
        self._check_agent(focal_agent)
        accurate = {agent: int(agent in self.submissions and self.submissions[agent]["total"] == self.oracle_total) for agent in SUBJECTS}
        visible = {agent: len({fragment["original_id"] for fragment in self.known_fragments[agent].values()}) for agent in SUBJECTS}
        at_submit = {agent: len(self.submissions[agent]["original_ids_available"]) if agent in self.submissions else 0 for agent in SUBJECTS}
        errors = [abs(submission["total"] - self.oracle_total) for submission in self.submissions.values()]
        action_events = [event for event in self.events if event["type"] == "action"]
        relays = sum(any(hop.get("kind") == "message" for hop in fragment["lineage"][:-1])
                     for message in self.messages for fragment in message["attached_fragments"])
        return {"mean_accuracy": sum(accurate.values()) / 4, "focal_accuracy": accurate[focal_agent],
                "completion_rate": len(self.submissions) / 4, "per_agent_accuracy": accurate, "missing_submission_score": 0,
                "messages_sent": self.dispatch_count, "message_deliveries": len(self.messages), "steps_used": self.step_count,
                "invalid_actions": sum(not event["result"]["ok"] for event in action_events),
                "unique_originals_visible": visible, "mean_unique_originals_visible": sum(visible.values()) / 4,
                "unique_originals_at_submission": at_submit, "mean_unique_originals_at_submission": sum(at_submit.values()) / 4,
                "all_originals_visible_fraction": sum(count == 4 for count in visible.values()) / 4,
                "all_originals_at_submission_fraction": sum(count == 4 for count in at_submit.values()) / 4,
                "measurement_definitions": {
                    "originals_visible": "Canonical fragments in the recipient-scoped attachment inventory; not measured mental knowledge. Free-text claims may convey values without canonical attachments.",
                    "originals_at_submission": "Canonical attachment inventory frozen at the first valid submission; later messages cannot change this coverage.",
                    "messages_sent": "One dispatch/message action per unicast or neighbor multicast; recipient deliveries are counted separately.",
                    "mean_accuracy": "Exact modular residue match, averaged over all four declared subjects; missing submissions score zero.",
                    "absolute_error": "Ordinary absolute distance between residues, only among submitted answers; not circular distance or the primary outcome."},
                "mean_absolute_error_among_submitted": sum(errors) / len(errors) if errors else None,
                "relay_attachment_events": relays, "budget_by_agent": {agent: {"allocated_turns": self.spec["max_rounds"],
                    "allocated_messages": self.spec["max_messages_per_agent"], "used_turns": self.turn_count[agent], "sent_messages": self.sent_count[agent]} for agent in SUBJECTS},
                "terminated_by": "all_submissions" if len(self.submissions) == 4 else "step_budget" if self.terminal else "not_terminal"}

    def snapshot(self) -> dict:
        """Complete privileged state for reproducibility, including the oracle."""
        return copy.deepcopy({"seed": self.seed, "spec_hash": fingerprint(self.spec), "oracle_total": self.oracle_total,
            "original_fragments": self.original_fragments, "known_fragments": self.known_fragments, "neighbors": self.neighbors,
            "private_context": self.private_context, "messages": self.messages, "events": self.events, "submissions": self.submissions,
            "sent_count": self.sent_count, "turn_count": self.turn_count, "last_result": self.last_result,
            "step_count": self.step_count, "dispatch_count": self.dispatch_count, "schedule": self.schedule})


def create_complementary_environment(spec: dict | None = None, seed: int = 0) -> ComplementaryInformationEnvironment:
    return ComplementaryInformationEnvironment(spec or create_complementary_spec(), seed)


def complementary_subject_request(environment: ComplementaryInformationEnvironment, agent_id: str) -> dict:
    observation = environment.observe(agent_id)
    schema = copy.deepcopy(ACTION_SCHEMA)
    schema["properties"]["total"]["maximum"] = observation["modulus"] - 1
    return {"role": agent_id, "system": "You are one of four agents solving an exact complementary-information task. Choose one legal action at a time and communicate as you judge useful. Return exactly one JSON action object. " + ACTION_SCHEMA["instructions"],
            "context": observation.pop("your_private_context"), "observation": observation, "action_schema": schema}


def complementary_environment_capabilities() -> dict:
    return {"api_version": COMPLEMENTARY_ENVIRONMENT_VERSION, "implemented_kinds": ["complementary_information"],
            "topologies": [*TOPOLOGIES, "custom"], "fidelity": copy.deepcopy(FIDELITY),
            "factory_parameters": ["topology", "max_rounds", "max_messages_per_agent", "modulus", "component_min", "component_max", "custom_edges"],
            "operations": ["construct", "validate", "reset", "observe", "step", "inject_private_context", "snapshot_for_researcher", "evaluate"],
            "primary_outcome": "Whole-network mean exact modular-total accuracy across four subjects; missing submissions score zero",
            "information_bound": "For independent uniform residues, any strict subset leaves the target uniform modulo q; chance exact accuracy is 1/q",
            "initial_visibility": "Each subject privately sees only its own original at reset; inspection is optional",
            "communication_actions": "Unicast or neighbor multicast of canonical bundles; either consumes one per-agent message-action unit",
            "three_round_feasibility": "Two neighbor-multicast rounds can spread every original within connected built-in graphs of diameter at most two, followed by final submission",
            "unit_of_replication": "Whole interacting four-agent society, not messages or individual verdicts",
            "matched_by_seed": "Private original measurements and seeded schedule are independent random streams, unchanged by topology",
            "matched_budgets": "Same allocated per-agent turns and message-action cap across topology; delivery itself is immediate and free",
            "not_matched": "Degree, multicast recipient deliveries, path length, relaying burden, neighbor choices and achieved information access",
            "causal_readiness": "Executable world contract only; treatments, hypotheses, outcomes and analysis require separate frozen registration"}


def offline_complementary_policy(request: dict) -> dict:
    """Deterministic plumbing policy, with no planted-context treatment response.

    It shares newly known canonical fragments and finally sums visible originals.
    Missing originals are not filled from oracle or private unverified claims.
    Results test tools and information feasibility, not agent behavior or effects.
    """
    observed = request["observation"]
    if observed["your_submission"] is not None:
        return {"action": "wait"}
    own = observed["your_assigned_fragment_id"]
    known = {fragment["fragment_id"]: fragment for fragment in observed["known_fragments"]}
    if own not in known:
        return {"action": "inspect_fragment", "fragment_id": own}
    if observed["your_turns_remaining"] > 1 and observed["messages_remaining"]:
        sent = defaultdict_set(observed["your_sent_messages"])
        choices = [(len(set(known) - sent.get(recipient, set())), recipient) for recipient in observed["permitted_recipients"]]
        if choices:
            missing, recipient = max(choices, key=lambda item: (item[0], item[1]))
            if missing:
                return {"action": "send_neighbors", "fragment_ids": sorted(known),
                        "message": "Sharing canonical originals currently visible to me; attachments retain their source lineage."}
    if observed["your_turns_remaining"] > 1 and len(known) < 4:
        return {"action": "wait"}
    originals = {fragment["original_id"]: fragment for fragment in known.values()}
    return {"action": "submit_total", "total": sum(fragment["value"] for fragment in originals.values()) % observed["modulus"],
            "rationale": f"Scripted sum of {len(originals)} visible originals. Plumbing check only; missing originals remain unknown."}


def defaultdict_set(messages):
    sent = {}
    for message in messages:
        sent.setdefault(message["recipient"], set()).update(fragment["fragment_id"] for fragment in message["attached_fragments"])
    return sent


def check_complementary_contract(environment: ComplementaryInformationEnvironment) -> dict:
    if environment.step_count or any(environment.private_context.values()):
        raise ValueError("Contract checks require a fresh environment")
    before, checks = environment.snapshot(), []
    try:
        requests = [complementary_subject_request(environment, agent) for agent in SUBJECTS]
        checks.append({"name": "initial_private_fragment_only_own_visible", "passed": all(len(request["observation"]["known_fragments"]) == 1 and request["observation"]["known_fragments"][0]["original_holder"] == request["role"] for request in requests)})
        checks.append({"name": "oracle_and_seed_absent_from_subject_request", "passed": all(not ({"seed", "oracle_total", "original_fragments"} & set(request["observation"])) for request in requests)})
        checks.append({"name": "four_unique_originals", "passed": len({fragment["original_id"] for fragment in environment.original_fragments.values()}) == 4})
        environment.inject_context("agent-0", "CONTRACT_PRIVATE_MARKER")
        checks.append({"name": "private_context_isolation", "passed": all("CONTRACT_PRIVATE_MARKER" not in json.dumps(complementary_subject_request(environment, agent)) for agent in SUBJECTS if agent != "agent-0")})
        actor = environment.next_agent
        environment.step(actor, {"action": "inspect_fragment", "fragment_id": f"fragment-{actor}"})
        checks.append({"name": "own_inspection_scope", "passed": all(len(environment.known_fragments[other]) == 1 and next(iter(environment.known_fragments[other].values()))["original_holder"] == other for other in SUBJECTS)})
    finally:
        restored = environment.reset(before["seed"])
    checks.append({"name": "exact_reset", "passed": restored == before})
    return {"passed": all(check["passed"] for check in checks), "checks": checks,
            "scope": "Executable information-boundary smoke check; not social-fidelity validation or identification of a causal mechanism"}
