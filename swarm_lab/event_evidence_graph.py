"""Bounded neighborhoods of declared event references, never influence graphs.

Every node is an actual event in one exact saved observability run. Unresolved,
ambiguous, or actor-conflicting references are diagnostics, not invented edges.
There is no model, database, network, or source-content export in this module.
"""
from collections import Counter, defaultdict, deque
import hashlib
import json
import math
from pathlib import Path
import re

from .observability_protocol import validate_batch
from .store import fingerprint


VERSION = "event-evidence-neighborhood-v1"
MAX_INPUT_BYTES = 2 * 1024**2
MAX_REFERENCE_CHECKS = 20000
MAX_DIAGNOSTIC_CANDIDATES = 8
STATUSES = ("matching_declared_reference", "unknown_in_captured_run",
            "ambiguous_reference", "actor_conflict")
LIMITATIONS = [
    "Edges record explicit source fields and local unique-reference matches; they are not causal edges.",
    "Agent registration is a producer declaration, not independent authentication of an actor.",
    "Addressing, reply references and tool-call IDs do not establish reading, delivery or independently verified execution.",
    "Missing targets are unknown within this exact captured run; no global absence is established.",
    "Selection traverses resolved relationships in either direction; returned edges retain source-field direction.",
    "Capture order and producer timestamps are retained without imposing a shared causal clock or parent-before-child order.",
    "Private rationale events may have actor/task source associations but create no recipient or communication edges.",
]


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _hash(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _bounded_json(value):
    pending = [(value, 0)]
    items = 0
    while pending:
        item, depth = pending.pop()
        items += 1
        if depth > 16 or items > 100000:
            raise ValueError("Event graph input exceeds its nesting/item bound")
        if item is None or type(item) is bool:
            continue
        if type(item) in (int, float):
            if abs(item) > 9007199254740991 or type(item) is float and not math.isfinite(item):
                raise ValueError("Event graph input requires finite safe JSON numbers")
        elif type(item) is str:
            if len(item) > 16000:
                raise ValueError("Event graph input text exceeds its bound")
            item.encode("utf-8")
        elif type(item) is list:
            if len(item) > 2000:
                raise ValueError("Event graph input lists exceed their bound")
            pending.extend((v, depth + 1) for v in item)
        elif type(item) is dict:
            if len(item) > 256 or any(type(k) is not str or len(k) > 200 for k in item):
                raise ValueError("Event graph input object exceeds its field bound")
            pending.extend((v, depth + 1) for v in item.values())
        else:
            raise ValueError("Event graph input requires ordinary JSON")
    if len(_canonical(value)) > MAX_INPUT_BYTES:
        raise ValueError("Event graph input exceeds 2 MiB")


def _positive(value, name, maximum, minimum=1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer from {minimum} to {maximum}")


def _identifier(value):
    return type(value) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}", value)


def _references(event):
    """Paths refer to original JSON fields; definition self-links are omitted."""
    kind, data = event["kind"], event["data"]
    if event.get("actor_id") and kind != "agent.registered":
        yield "actor", "agent", event["actor_id"], "actor_id"
    if event.get("task_id") and kind != "task.created":
        yield "task", "task", event["task_id"], "task_id"
    if event.get("parent_task_id"):
        yield "parent_task", "task", event["parent_task_id"], "parent_task_id"
    for i, target in enumerate(event.get("recipient_ids", [])):
        yield "addressed_recipient", "agent", target, f"recipient_ids[{i}]"
    for i, target in enumerate(data.get("assignee_ids", [])):
        yield "task_assignee", "agent", target, f"data.assignee_ids[{i}]"
    if kind == "message.sent" and data.get("reply_to_message_id"):
        yield "reply_reference", "message", data["reply_to_message_id"], "data.reply_to_message_id"
    if kind == "tool.returned":
        yield "tool_call_reference", "call", data["call_id"], "data.call_id"


def _definition(event):
    kind = event["kind"]
    if kind == "agent.registered":
        return "agent", event["actor_id"]
    if kind == "task.created":
        return "task", event["task_id"]
    if kind == "message.sent":
        return "message", event["id"]
    if kind == "tool.called":
        return "call", event["data"]["call_id"]
    return None


def _source_hashes():
    # Implementation-byte identities, not an upstream/source authentication.
    root = Path(__file__).parent
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in ("event_evidence_graph.py", "observability_protocol.py", "store.py")}


def build_event_evidence_neighborhood(record, *, seed_event_id, hops=1,
                                      max_nodes=100, max_edges=256,
                                      max_diagnostics=64):
    """Return a deterministic induced graph on a capped resolved neighborhood.

    The caller authenticates registry access. This function additionally checks
    the saved payload against its exact declared Store fingerprint, then checks
    the actual batch schema. It neither creates nor updates scientific objects.
    """
    _positive(hops, "hops", 2, minimum=0)
    _positive(max_nodes, "max_nodes", 200)
    _positive(max_edges, "max_edges", 600)
    _positive(max_diagnostics, "max_diagnostics", 256)
    if not _identifier(seed_event_id):
        raise ValueError("Use an exact bounded event ID")
    if type(record) is not dict or record.get("kind") != "observability_run":
        raise ValueError("Select an exact saved observability run")
    if (not _identifier(record.get("id")) or type(record.get("version")) is not int
            or not 1 <= record["version"] <= 9007199254740991 or type(record.get("hash")) is not str
            or not re.fullmatch(r"[a-f0-9]{64}", record["hash"])):
        raise ValueError("An exact typed run reference is required")
    payload = record.get("payload")
    if type(payload) is not dict:
        raise ValueError("The saved observability payload is unavailable")
    _bounded_json(payload)
    if fingerprint(payload) != record["hash"]:
        raise ValueError("The saved run payload does not match its exact fingerprint")
    try:
        batch = validate_batch({k: payload[k] for k in ("schema_version", "source", "run", "events")})
    except KeyError as error:
        raise ValueError("The saved observability batch is incomplete") from error
    events = batch["events"]
    by_id = {event["id"]: event for event in events}
    if seed_event_id not in by_id:
        raise ValueError("The requested event is unknown in this exact run")
    positions = {event["id"]: index + 1 for index, event in enumerate(events)}
    event_hashes = {event["id"]: _hash(event) for event in events}
    definitions = defaultdict(list)
    for event in events:
        if (key := _definition(event)) is not None:
            definitions[key].append(event["id"])
    checks, edges, adjacent = [], [], defaultdict(list)
    for event in events:
        for relation, target_kind, reference_id, field in _references(event):
            if len(checks) >= MAX_REFERENCE_CHECKS:
                raise ValueError("The captured run exceeds the 20000 reference-check work bound")
            candidates = definitions.get((target_kind, reference_id), [])
            state = ("unknown_in_captured_run" if not candidates else
                     "ambiguous_reference" if len(candidates) != 1 else "matching_declared_reference")
            if (state == "matching_declared_reference" and relation == "tool_call_reference"
                    and by_id[candidates[0]]["actor_id"] != event["actor_id"]):
                state = "actor_conflict"
            check = {"event_id": event["id"], "relation": relation,
                     "reference_kind": target_kind, "reference_id": reference_id,
                     "field": field, "status": state, "candidate_count": len(candidates),
                     "candidate_event_ids": candidates[:MAX_DIAGNOSTIC_CANDIDATES],
                     "candidates_truncated": len(candidates) > MAX_DIAGNOSTIC_CANDIDATES,
                     "source_event_sha256": event_hashes[event["id"]]}
            checks.append(check)
            if state != "matching_declared_reference":
                continue
            target = candidates[0]
            identity = {"source": event["id"], "target": target,
                        "relation": relation, "field": field}
            edge = {"id": _hash(identity), **identity,
                    "status": state, "reference_id": reference_id,
                    "reference_kind": target_kind,
                    "provenance": {"event_id": event["id"], "field": field,
                                   "event_sha256": event_hashes[event["id"]]},
                    "target_event_sha256": event_hashes[target]}
            edges.append(edge)
            adjacent[event["id"]].append(target)
            adjacent[target].append(event["id"])
    selected, queue = {seed_event_id: 0}, deque([seed_event_id])
    node_cap, hop_boundary = False, False
    while queue:
        current = queue.popleft()
        distance = selected[current]
        for other in sorted(set(adjacent[current])):
            if other in selected:
                continue
            if distance == hops:
                hop_boundary = True
                continue
            if len(selected) == max_nodes:
                node_cap = True
                continue
            selected[other] = distance + 1
            queue.append(other)
    induced = sorted((edge for edge in edges if edge["source"] in selected and edge["target"] in selected),
                     key=lambda edge: (edge["source"], edge["relation"], edge["field"], edge["target"]))
    scoped_checks = [check for check in checks if check["event_id"] in selected]
    diagnostic_rows = [check for check in scoped_checks if check["status"] != "matching_declared_reference"]
    nodes = [{"id": identity, "kind": by_id[identity]["kind"],
              "occurred_at": by_id[identity]["occurred_at"], "capture_position": positions[identity],
              "actor_id": by_id[identity].get("actor_id"), "task_id": by_id[identity].get("task_id"),
              "distance": selected[identity], "source_event_sha256": event_hashes[identity]}
             for identity in sorted(selected, key=positions.get)]
    counts = Counter(check["status"] for check in scoped_checks)
    return {"graph_version": VERSION, "kind": "event_evidence_neighborhood",
            "source_ref": {k: record[k] for k in ("id", "version", "hash")},
            "batch_sha256": _hash(batch), "seed_event_id": seed_event_id,
            "nodes": nodes, "edges": induced[:max_edges],
            "diagnostics": diagnostic_rows[:max_diagnostics],
            "coverage": {"captured_events": len(events), "declared_reference_checks": len(checks),
                         "selected_nodes": len(nodes), "induced_edges_before_display_cap": len(induced),
                         "selected_reference_counts": {key: counts[key] for key in STATUSES},
                         "selected_diagnostics_before_display_cap": len(diagnostic_rows),
                         "node_limit_reached": node_cap, "edge_limit_reached": len(induced) > max_edges,
                         "diagnostic_limit_reached": len(diagnostic_rows) > max_diagnostics,
                         "additional_resolved_neighbors_beyond_requested_hops": hop_boundary,
                         "upstream_completeness": "unverified"},
            "truncated": node_cap or len(induced) > max_edges or len(diagnostic_rows) > max_diagnostics,
            "limits": {"hops": hops, "nodes": max_nodes, "edges": max_edges,
                       "diagnostics": max_diagnostics, "diagnostic_candidates": MAX_DIAGNOSTIC_CANDIDATES,
                       "maximum_input_bytes": MAX_INPUT_BYTES, "maximum_reference_checks": MAX_REFERENCE_CHECKS},
            "scope": {"node_unit": "captured_event", "selection": "undirected_resolved_reference_hops",
                      "edge_direction": "referencing_event_to_unique_definition_event",
                      "diagnostics": "references_declared_by_selected_events",
                      "self_definition_links": "omitted", "causal_graph": False,
                      "raw_content_exported": False, "provider_calls": 0, "database_writes": 0},
            "implementation_hashes": _source_hashes(), "limitations": list(LIMITATIONS)}
