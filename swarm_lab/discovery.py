"""Inspectable behavioral signals and graph-guided discovery candidates.

Detectors identify text events, not mental states. Motifs propose incidents for
investigation; they do not certify novel behavior, task failure, or causation.
Optional Laya/Jev-style backends must satisfy the narrow typed-label contract.
"""
from __future__ import annotations

import hashlib
import re
from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any, Protocol

from .dataset import normalize_message, parse_time


DETECTOR_VERSION = "observable-signals-v1"
DETECTOR_DEFINITIONS = {
    "commitment": {"description": "Speaker explicitly accepts future work or ownership.", "non_examples": "A suggestion that someone else should do work; completion reports."},
    "completion_report": {"description": "Speaker reports work completed. This does not verify completion.", "non_examples": "Not yet done; if completed; another agent's quoted claim."},
    "evidence_request": {"description": "Speaker explicitly requests proof, a source, a check, or an artifact.", "non_examples": "A statement that evidence exists without requesting it."},
    "blocker_report": {"description": "Speaker explicitly reports inability to proceed or waiting on a dependency.", "non_examples": "Ordinary future work without a stated obstruction."},
    "correction": {"description": "Speaker explicitly corrects/retracts a claim or reports an error.", "non_examples": "Disagreement without a specified correction."},
    "human_help_request": {"description": "Speaker explicitly requests human approval, sign-in, or assistance.", "non_examples": "A generic request to another agent."},
    "acknowledgement": {"description": "Speaker explicitly acknowledges a message without necessarily taking ownership.", "non_examples": "Task acceptance is not inferred from acknowledgement alone."},
    "plan_change": {"description": "Speaker explicitly proposes changing, abandoning, or replacing a plan.", "non_examples": "Routine task progress."},
}

_PATTERNS = {
    "commitment": r"\b(?:I(?:'ll| will| am going to)|I(?:'m| am) taking|I'll take|I can take|taking ownership|my responsibility)\b",
    "completion_report": r"\b(?:I(?:'ve| have) (?:finished|completed|deployed|published|uploaded|submitted|verified)|I (?:finished|completed|deployed|published|uploaded|submitted|verified)|(?:task|website|deployment|upload|work|report|artifact|implementation) (?:is |has been )?(?:done|complete|completed|finished|ready)|done(?=[.!](?:\s|$)))\b",
    "evidence_request": r"\b(?:can (?:you|someone|anyone) (?:verify|check|confirm|show|share)|please (?:verify|check|confirm|show|share)|(?:what|where) (?:is|are) (?:the |your )?(?:evidence|source|proof|artifact)|(?:need|request|asking for) (?:a |the |your )?(?:source|evidence|proof|artifact)|show me (?:the |your )?(?:evidence|source|proof))\b",
    "blocker_report": r"\b(?:blocked|stuck|waiting (?:on|for)|can't (?:proceed|continue|access|finish)|cannot (?:proceed|continue|access|finish)|unable to (?:proceed|continue|access|finish)|permission denied|access denied)\b",
    "correction": r"\b(?:correction|I was wrong|I retract|retracting|that was incorrect|this was incorrect|previous (?:claim|statement|message) was (?:wrong|incorrect)|actually (?:failed|missing|incorrect)|there (?:is|was) an error)\b",
    "human_help_request": r"\b(?:human (?:help|approval|assistance)|need (?:you|a human|someone) to (?:sign in|approve|authorize)|please (?:sign in|approve|authorize)|request(?:ing)? (?:human|outreach) approval)\b",
    "acknowledgement": r"\b(?:acknowledged|got it|understood|thanks|thank you|sounds good|noted)\b",
    "plan_change": r"\b(?:change (?:the |our )?plan|switch (?:to|approach)|switching (?:to|approach)|abandon (?:the |our )?plan|instead we|let's instead|new plan|pivot)\b",
}
_COMPILED = {name: re.compile(pattern, re.I) for name, pattern in _PATTERNS.items()}
_NEGATIVE_COMPLETION = re.compile(r"\b(?:not|never|isn't|wasn't|hasn't|haven't|don't|didn't|yet to)\b", re.I)
_URL = re.compile(r"https?://[^\s<>\]\)\"']+", re.I)
_WORD = re.compile(r"[a-z0-9]+", re.I)
_STOP = frozenset("the a an and or to of for in on is are was be been this that it i you we our my your will have has with at as by from can please thanks thank done completed finished task work report evidence source ready now today tomorrow already also all need not".split())


class TypedBehaviorBackend(Protocol):
    """Adapter contract for a cheap classifier; no provider is called implicitly."""
    name: str

    def classify(self, message: dict, definitions: dict[str, dict]) -> dict[str, bool | None]:
        """Return true/false/abstain per predefined observable, not free text."""


def _messages(messages: list[dict]) -> list[dict]:
    result = [normalize_message(message) for message in messages]
    result.sort(key=lambda message: (message["timestamp"], message["id"]))
    seen = set()
    for message in result:
        if message["id"] in seen:
            raise ValueError(f"Duplicate message ID: {message['id']}")
        seen.add(message["id"])
    return result


def _tokens(content: str) -> set[str]:
    return {word for word in _WORD.findall(content.lower()) if word not in _STOP and len(word) > 2}


def _urls(content: str) -> list[str]:
    return sorted({url.rstrip(".,;:!?") for url in _URL.findall(content)})


def detect_behaviors(messages: list[dict], backend: TypedBehaviorBackend | Any | None = None) -> list[dict]:
    """Return narrow, versioned text observations with exact supporting spans.

    An optional classifier supplies separate measurements. Neither backend's
    judgment silently replaces deterministic observations. Abstentions persist.
    """
    observations = []
    for message in _messages(messages):
        content = message["content"].replace("\u2019", "'")
        found = []
        spans = {}
        for name, pattern in _COMPILED.items():
            matches = list(pattern.finditer(content))
            if name == "completion_report":
                matches = [match for match in matches if not _NEGATIVE_COMPLETION.search(content[max(0, match.start() - 25):match.start()])]
            if matches:
                found.append(name)
                spans[name] = [{"start": match.start(), "end": match.end(), "text": message["content"][match.start():match.end()]} for match in matches]
        record = {"message_id": message["id"], "agent_id": message["agent_id"], "speaker_type": message["speaker_type"], "timestamp": message["timestamp"], "room_id": message["room_id"], "labels": found, "spans": spans, "urls": _urls(content), "backend": "deterministic_regex", "detector_version": DETECTOR_VERSION, "interpretation": "text_observation", "limitations": ["No mental-state or task-outcome inference.", "Regex screening requires human/agent adjudication on representative samples."]}
        if backend is not None:
            classifier = backend.classify if hasattr(backend, "classify") else backend
            labels = classifier(message, DETECTOR_DEFINITIONS)
            if not isinstance(labels, dict) or set(labels) - set(DETECTOR_DEFINITIONS):
                raise ValueError("Classifier must return a dictionary of predefined observable labels")
            if any(value is not None and type(value) is not bool for value in labels.values()):
                raise ValueError("Classifier labels must be true, false, or null (abstention)")
            record["additional_measurement"] = {"backend": getattr(backend, "name", "configured_callable"), "labels": labels, "detector_version": DETECTOR_VERSION, "calibration": "not_established"}
            detail = getattr(backend, 'last_measurement', None)
            if detail:
                record['additional_measurement'].update(detail if detail.get('status') != 'not_sampled' else {'status': 'not_sampled', 'sampled': False})
        observations.append(record)
    return observations


def build_graph(messages: list[dict], agents: list[dict] | dict | None = None, events: list[dict] | None = None, *, proximity_seconds: int = 300) -> dict:
    """Build a temporal evidence graph; explicit edges and inferences stay apart."""
    ordered = _messages(messages)
    roster = agents.values() if isinstance(agents, dict) else agents or []
    names = {str(agent["id"]): str(agent.get("name", agent["id"])) for agent in roster if agent.get("id")}
    for message in ordered:
        if message["agent_id"]:
            names.setdefault(message["agent_id"], message["agent_name"])
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    ids = {message["id"] for message in ordered}
    previous_by_room: dict[str, dict] = {}

    def node(identity: str, kind: str, **attributes: Any) -> None:
        nodes.setdefault(identity, {"id": identity, "kind": kind, **attributes})

    def edge(source: str, target: str, kind: str, message: dict, *, inferred: bool = False, **attributes: Any) -> None:
        edges.append({"source": source, "target": target, "kind": kind, "timestamp": message["timestamp"], "evidence_ids": [message["id"]], "inferred": inferred, "claim_type": "candidate_relation" if inferred else "recorded_relation", **attributes})

    for message in ordered:
        mid, sid, rid = "message:" + message["id"], "speaker:" + message["speaker_id"], "room:" + message["room_id"]
        node(mid, "message", timestamp=message["timestamp"], evidence_id=message["id"], speaker_type=message["speaker_type"], source=message["source"])
        node(sid, "agent" if message["speaker_type"] == "agent" else "human", name=names.get(message["speaker_id"], message["agent_name"]))
        node(rid, "room")
        edge(sid, mid, "authored", message)
        edge(mid, rid, "posted_in", message)
        for url in _urls(message["content"]):
            uid = "artifact:" + hashlib.sha256(url.encode()).hexdigest()[:24]
            node(uid, "artifact", url=url)
            edge(mid, uid, "references_url", message, interpretation="A URL reference is not verification of its contents.")
        for aid, name in names.items():
            if aid == message["agent_id"] or name == aid or len(name) < 3:
                continue
            # Matching an exact roster name is observable mention evidence.
            # It does not establish delivery, agreement, or influence.
            match = re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", message["content"], re.I)
            if match:
                node("speaker:" + aid, "agent", name=name)
                edge(mid, "speaker:" + aid, "mentions", message, span={"start": match.start(), "end": match.end()}, interpretation="Mention only; intent and actual reading are unknown.")
        parent = message.get("reply_to")
        if parent and parent in ids:
            edge(mid, "message:" + str(parent), "explicit_reply", message)
        previous = previous_by_room.get(message["room_id"])
        if previous and previous["speaker_id"] != message["speaker_id"]:
            elapsed = (parse_time(message["timestamp"]) - parse_time(previous["timestamp"])).total_seconds()
            if 0 <= elapsed <= proximity_seconds:
                edge("message:" + previous["id"], mid, "temporal_proximity", message, inferred=True, seconds=elapsed, evidence_ids_pair=[previous["id"], message["id"]], interpretation="Ordering/proximity, not a causal or response relation.")
                left, right = _tokens(previous["content"]), _tokens(message["content"])
                union = left | right
                overlap = len(left & right) / len(union) if union else 0
                if len(left & right) >= 3 and overlap >= 0.35:
                    edge("message:" + previous["id"], mid, "lexical_recurrence", message, inferred=True, overlap=round(overlap, 4), evidence_ids_pair=[previous["id"], message["id"]], interpretation="Similar content; common context may explain recurrence.")
        previous_by_room[message["room_id"]] = message
    for event in events or []:
        data = event.get("data", {})
        if not isinstance(data, dict):
            continue
        event_id = "event:" + str(event.get("id", "index-" + str(event.get("event_index"))))
        node(event_id, "event", action_type=data.get("actionType"), event_index=event.get("event_index"), timestamp=event.get("created_at"), source=event.get("source", {}))
        message_id = data.get("messageId")
        if message_id in ids:
            edges.append({"source": event_id, "target": "message:" + message_id, "kind": "records_message", "timestamp": event.get("created_at"), "evidence_ids": [message_id, event.get("id")], "inferred": False, "claim_type": "recorded_relation"})
    types = Counter(edge["kind"] for edge in edges)
    return {"schema_version": "1.0", "nodes": list(nodes.values()), "edges": edges, "summary": {"nodes": len(nodes), "edges": len(edges), "edge_counts": dict(types), "inferred_edges": sum(edge["inferred"] for edge in edges)}, "limitations": ["No edge establishes causal influence.", "An agent's opportunity to read a room is not observed reading.", "Mentions use exact display names and miss aliases."]}


def _candidate(kind: str, evidence: list[dict], *, description: str, alternatives: list[str], censored: bool = False, metrics: dict | None = None) -> dict:
    evidence = sorted(evidence, key=lambda message: (message["timestamp"], message["id"]))
    evidence_ids = list(dict.fromkeys(message["id"] for message in evidence))
    identity = hashlib.sha256((kind + "|" + "|".join(evidence_ids)).encode()).hexdigest()[:20]
    return {"id": "candidate-" + identity, "kind": kind, "title": kind.replace("_", " ").capitalize(), "status": "candidate", "claim_type": "observational_hypothesis", "description": description, "evidence_ids": evidence_ids, "start": evidence[0]["timestamp"], "end": evidence[-1]["timestamp"], "room_ids": sorted({message["room_id"] for message in evidence}), "agent_ids": sorted({message["agent_id"] for message in evidence if message["agent_id"]}), "metrics": metrics or {}, "alternative_explanations": alternatives, "right_censored": censored, "novelty": "not_established", "causal_support": "none", "requires": ["Review source evidence and detector mistakes", "Seek matched ordinary episodes and counterexamples", "Validate reconstructed environment before experimental claims"]}


def discover_cases(messages: list[dict], *, agents: list[dict] | dict | None = None, backend: TypedBehaviorBackend | Any | None = None, window_seconds: int = 1800, events: list[dict] | None = None) -> dict:
    """Identify inspectable motifs and representative observational controls.

    Windows align to UTC epoch and room, making comparisons reproducible. A
    missing observed resolution is explicitly scoped and never called failure.
    """
    if not isinstance(window_seconds, int) or window_seconds < 60:
        raise ValueError("window_seconds must be an integer >= 60")
    ordered = _messages(messages)
    signals = detect_behaviors(ordered, backend=backend)
    signals_by_id = {record["message_id"]: record for record in signals}
    windows: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for message in ordered:
        tick = int(parse_time(message["timestamp"]).timestamp()) // window_seconds
        windows[(message["room_id"], tick)].append(message)
    candidates: list[dict] = []
    metrics = []
    for (room, tick), items in sorted(windows.items()):
        labels = Counter(label for message in items for label in signals_by_id[message["id"]]["labels"])
        actors = {message["agent_id"] for message in items if message["agent_id"]}
        urls = Counter(url for message in items for url in signals_by_id[message["id"]]["urls"])
        record = {"window_id": f"{room}:{tick}", "room_id": room, "start": items[0]["timestamp"], "end": items[-1]["timestamp"], "message_count": len(items), "agent_count": len(actors), "signal_counts": dict(labels), "distinct_referenced_urls": len(urls), "max_url_reference_count": max(urls.values(), default=0), "evidence_ids": [message["id"] for message in items]}
        metrics.append(record)
        completion_items = [message for message in items if "completion_report" in signals_by_id[message["id"]]["labels"]]
        if len(completion_items) >= 3 and len({message["agent_id"] for message in completion_items if message["agent_id"]}) >= 2:
            candidates.append(_candidate("completion_report_cluster", completion_items, description="Multiple agents report completions in one window; inspect whether reports concern independent work, a shared artifact, or repeated status.", alternatives=["Independent tasks completed normally", "A planned milestone or celebration", "Regex/quotation mistakes", "Common instruction produced similar updates"], metrics={"completion_reports": len(completion_items), "supporting_url_references_in_window": len(urls)}))
        corrections = [message for message in items if "correction" in signals_by_id[message["id"]]["labels"]]
        if len(corrections) >= 2:
            candidates.append(_candidate("correction_cluster", corrections, description="Multiple explicit corrections occur close together; investigate error repair, error propagation, or unrelated corrections.", alternatives=["Independent errors", "A scheduled review", "Repeated correction of one issue", "Detector false positives"], metrics={"corrections": len(corrections)}))
        acknowledgements = [message for message in items if "acknowledgement" in signals_by_id[message["id"]]["labels"]]
        blockers = [message for message in items if "blocker_report" in signals_by_id[message["id"]]["labels"]]
        if len(acknowledgements) >= 2 and blockers and labels["commitment"] == 0:
            candidates.append(_candidate("acknowledgement_without_observed_commitment", blockers + acknowledgements, description="Blocker reports receive acknowledgements while no explicit ownership is detected in this window.", alternatives=["Ownership exists outside the imported window", "Ownership was implicit or assigned through tools", "Acknowledgements concern different issues", "Detector misses a commitment"], censored=True, metrics={"acknowledgements": len(acknowledgements), "blockers": len(blockers)}))
        plans = [message for message in items if "plan_change" in signals_by_id[message["id"]]["labels"]]
        if len(plans) >= 3:
            candidates.append(_candidate("plan_change_cluster", plans, description="Several explicit plan-change statements occur; test whether adaptation is productive or constitutes coordination churn.", alternatives=["New information justifies changes", "Independent agents changing independent plans", "A brainstorming session", "Scaffolding changes"], metrics={"plan_changes": len(plans)}))
        repeated = [url for url, count in urls.items() if count >= 3]
        for url in repeated:
            references = [message for message in items if url in signals_by_id[message["id"]]["urls"]]
            if len({message["agent_id"] for message in references if message["agent_id"]}) >= 2:
                candidates.append(_candidate("shared_artifact_reference_cluster", references, description="Several agents reference the same URL. Inspect its role before interpreting shared references as evidence concentration.", alternatives=["Shared deliverable appropriately referenced", "Common primary source", "Repeated marketing message", "Underlying sources differ within the referenced artifact"], metrics={"url": url, "reference_count": len(references)}))
    # Follow explicit commitments within the same room; later self-reported
    # completion with shared task words is a possible resolution, not verification.
    room_messages: dict[str, list[dict]] = defaultdict(list)
    for message in ordered:
        room_messages[message["room_id"]].append(message)
    room_times = {room: [parse_time(message["timestamp"]).timestamp() for message in items] for room, items in room_messages.items()}
    room_indices = {message["id"]: index for items in room_messages.values() for index, message in enumerate(items)}
    for message in ordered:
        signal = signals_by_id[message["id"]]
        if "commitment" not in signal["labels"] or message["speaker_type"] != "agent":
            continue
        start = parse_time(message["timestamp"])
        horizon = start + timedelta(seconds=window_seconds)
        room_items = room_messages[message["room_id"]]
        stop_index = bisect_right(room_times[message["room_id"]], horizon.timestamp())
        following = room_items[room_indices[message["id"]] + 1:stop_index]
        task_words = _tokens(message["content"])
        matching_reports = [item for item in following if item["agent_id"] == message["agent_id"] and "completion_report" in signals_by_id[item["id"]]["labels"] and task_words & _tokens(item["content"])]
        blockers = [item for item in following if "blocker_report" in signals_by_id[item["id"]]["labels"] and task_words & _tokens(item["content"])]
        if blockers and not matching_reports:
            room_end = parse_time(room_items[-1]["timestamp"])
            candidates.append(_candidate("commitment_with_later_blocker", [message] + blockers, description="A commitment is followed by a lexically related blocker; no related self-reported completion is detected within the observation horizon.", alternatives=["Resolution occurs outside the observed horizon", "Completion occurred privately or through tools", "Lexically related statements concern different tasks", "The commitment was intentionally superseded"], censored=room_end < horizon, metrics={"horizon_seconds": window_seconds, "matching_completion_reports": 0, "lexical_matching": "shared non-stopword; requires adjudication"}))
    unique = {candidate["id"]: candidate for candidate in candidates}
    candidates = sorted(unique.values(), key=lambda candidate: (candidate["start"], candidate["id"]))
    affected = {identity for candidate in candidates for identity in candidate["evidence_ids"]}
    controls = []
    for candidate in candidates:
        eligible = [record for record in metrics if record["room_id"] in candidate["room_ids"] and not set(record["evidence_ids"]) & affected]
        if eligible:
            chosen = min(eligible, key=lambda record: (abs(record["message_count"] - len(candidate["evidence_ids"])), abs((parse_time(record["start"]) - parse_time(candidate["start"])).total_seconds()), record["window_id"]))
            controls.append({"for_candidate": candidate["id"], "window_id": chosen["window_id"], "evidence_ids": chosen["evidence_ids"], "matching": "same room; closest message count then time; no detected candidate evidence", "claim_type": "observational_comparison", "limitations": "Not randomized; confounding and missed behaviors remain possible."})
    return {"schema_version": "1.0", "detector_version": DETECTOR_VERSION, "detector_definitions": DETECTOR_DEFINITIONS, "signals": signals, "graph": build_graph(ordered, agents=agents, events=events), "window_metrics": metrics, "anomalies": candidates, "candidates": candidates, "controls": controls, "limitations": ["These are prespecified screening motifs, not established novel discoveries.", "Missing observations do not prove absent behavior.", "No historical comparison identifies an intervention effect.", "Imported scope, room, task, model, and scaffolding changes may confound comparisons."]}


def case_evidence(case: dict, messages: list[dict]) -> list[dict]:
    """Resolve every cited ID or fail; fabricated/missing evidence stays visible."""
    indexed = {message["id"]: message for message in _messages(messages)}
    missing = [identity for identity in case.get("evidence_ids", []) if identity not in indexed]
    if missing:
        raise ValueError("Case cites unknown evidence IDs: " + ", ".join(missing))
    return [indexed[identity] for identity in case.get("evidence_ids", [])]
