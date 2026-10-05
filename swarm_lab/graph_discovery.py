"""Graph-guided exploratory leads with source evidence and comparison windows.

This is a search instrument, not a detector of influence or agent psychology.
Its window/feature comparisons are selected from observed data and are unsuitable
as confirmatory tests. Observed mentions/replies and inferred recurrence remain
separate throughout.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta, timezone

from .dataset import iso_time, normalize_message, parse_time
from .discovery import build_graph
from .network import analyze_network


GRAPH_DISCOVERY_VERSION = "windowed-network-leads-v1"
FEATURES = {
    "incoming_concentration": {"channel": "observed_mentions", "minimum_delta": .15,
        "description": "Change in normalized incoming event concentration among the agents present or referenced in the window.",
        "alternatives": ["One agent's name may be used more often than others' aliases.", "A central task role or turn-taking convention can concentrate mentions.", "Referenced targets need not be reading or active."]},
    "directed_reciprocity": {"channel": "observed_mentions", "minimum_delta": .25,
        "description": "Change in the fraction of mention events with a reverse directed tie, weighted by the smaller event count.",
        "alternatives": ["A question-answer format produces reciprocal names without agreement.", "Missing reply pointers and alias matching change apparent reciprocity.", "Boundary cuts can remove the reverse part of a conversation."]},
    "bridge_dependence": {"channel": "observed_mentions", "minimum_delta": .15,
        "description": "Change in the maximum fraction of directed reachable pairs lost when a single node is removed, excluding pairs with that node as an endpoint.",
        "alternatives": ["Sparse name mentions create a fragile topology without actual mediation.", "Static paths can violate message time order.", "Unrecorded channels or a different room can supply other routes."]},
    "lexical_recurrence_rate": {"channel": "inferred_lexical", "minimum_delta": .03,
        "description": "Change in adjacent cross-agent lexical recurrence events per authored agent message.",
        "alternatives": ["A shared task or copied boilerplate can create similar wording.", "Lexical overlap is a heuristic and does not establish semantic adoption.", "Adjacent-message ordering misses long-range and cross-room relations."]},
    "shared_reference_rate": {"channel": "observed_url_references", "minimum_delta": .03,
        "description": "Change in exact URL references shared by at least two agent authors, per authored agent message.",
        "alternatives": ["Agents can independently encounter the same public resource.", "Equal URLs do not prove reading, copying, endorsement, or shared knowledge.", "Different URLs may identify the same resource and an equal URL can change content."]},
}


def _fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _reachable(nodes, edges, removed=None):
    adjacency = {node: set() for node in nodes if node != removed}
    for edge in edges:
        if edge["source"] != removed and edge["target"] != removed:
            adjacency[edge["source"]].add(edge["target"])
    pairs = set()
    for source in adjacency:
        seen, pending = {source}, deque([source])
        while pending:
            for target in adjacency[pending.popleft()]:
                if target not in seen:
                    seen.add(target)
                    pending.append(target)
        pairs.update((source, target) for target in seen if source != target)
    return pairs


def bridge_dependence(projection: dict) -> dict:
    """Directed node-removal reachability loss; endpoint loss is excluded."""
    nodes = [node["id"] for node in projection["nodes"]]
    if len(nodes) > 128:
        return {"maximum_loss_fraction": None, "focus_agent_id": None, "nodes": [], "original_reachable_pairs": None,
                "available": False, "reason": "Dense node-removal search is bounded to 128 agents"}
    edges = projection["edges"]
    original = _reachable(nodes, edges)
    rows = []
    for node in nodes:
        eligible = {pair for pair in original if node not in pair}
        remaining = _reachable(nodes, edges, removed=node)
        lost = eligible - remaining
        rows.append({"agent_id": node, "eligible_reachable_pairs": len(eligible), "lost_pairs": len(lost),
                     "loss_fraction": len(lost) / len(eligible) if eligible else None})
    valid = [row for row in rows if row["loss_fraction"] is not None]
    selected = max(valid, key=lambda row: (row["loss_fraction"], row["lost_pairs"], row["agent_id"])) if valid else None
    return {"maximum_loss_fraction": selected["loss_fraction"] if selected else None,
            "focus_agent_id": selected["agent_id"] if selected and selected["loss_fraction"] > 0 else None, "nodes": rows,
            "original_reachable_pairs": len(original),
            "interpretation": "A counterfactual on a static graph representation, not an intervention on agents or a measured communication effect."}


def graph_signal_summary(projection: dict, signal: dict[str, float], *, cutoff: float = .5) -> dict:
    """Basis-invariant energy in graph eigenspaces for an explicitly supplied signal.

    Require all nodes to be measured; missing values are not silent zeros. The
    spectrum is the normalized graph Laplacian after explicit symmetrization.
    Group energy is invariant to sign and rotations of repeated eigenvectors.
    """
    if type(cutoff) not in (int, float) or not math.isfinite(cutoff) or not 0 <= cutoff <= 2:
        raise ValueError("cutoff must be finite and between 0 and 2")
    basis = projection.get("spectral", {})
    if not basis.get("available"):
        return {"available": False, "reason": basis.get("reason", "Spectral basis unavailable")}
    nodes = basis.get("node_order", [])
    if set(signal) != set(nodes) or any(type(value) not in (int, float) or not math.isfinite(value) for value in signal.values()):
        raise ValueError("Supply one finite measured signal value for every node, without extras")
    energy = sum(float(signal[node]) ** 2 for node in nodes)
    groups = []
    for mode in basis.get("modes", []):
        eigenvalue = mode["eigenvalue"]
        coefficient = sum(float(signal[node]) * mode["coefficients"][node] for node in nodes)
        if groups and abs(groups[-1]["eigenvalue"] - eigenvalue) < 1e-8:
            groups[-1]["energy"] += coefficient ** 2
            groups[-1]["multiplicity"] += 1
        else:
            groups.append({"eigenvalue": eigenvalue, "energy": coefficient ** 2, "multiplicity": 1})
    positive = sum(group["energy"] for group in groups if group["eigenvalue"] > 1e-8)
    low = sum(group["energy"] for group in groups if 1e-8 < group["eigenvalue"] <= cutoff + 1e-8)
    return {"available": True, "operator": "normalized_graph_laplacian", "symmetrization": "(A+A.T)/2",
            "signal_energy": energy, "rayleigh_smoothness": sum(group["eigenvalue"] * group["energy"] for group in groups) / energy if energy else None,
            "eigenspace_energy": groups, "positive_frequency_energy": positive, "cutoff": float(cutoff),
            "low_positive_frequency_energy_fraction": low / positive if positive > 1e-12 else None,
            "null_energy_fraction": sum(group["energy"] for group in groups if group["eigenvalue"] <= 1e-8) / energy if energy else None,
            "warnings": ["No signal centering or imputation was applied; interpretation depends on the supplied units and level.",
                         "Grouping repeated eigenvalues removes arbitrary within-eigenspace axis choices.",
                         "Disconnected-component and isolate null energy is not evidence of agreement.",
                         "This graph operator is not established as a continuous-manifold Laplace–Beltrami operator.",
                         "Spectral smoothness does not identify influence, contagion, beliefs, or psychology."]}


def _url_recurrence(messages, agents):
    indexed = {message["id"]: message for message in messages}
    graph = build_graph(messages, agents=agents)
    resources = defaultdict(list)
    for edge in graph["edges"]:
        if edge["kind"] == "references_url":
            mid = edge["source"][len("message:"):]
            if indexed[mid]["agent_id"]:
                resources[edge["target"]].append(mid)
    shared = []
    for resource, mids in resources.items():
        authors = sorted({indexed[mid]["agent_id"] for mid in mids})
        if len(authors) >= 2:
            shared.append({"resource_node_id": resource, "author_ids": authors, "evidence_ids": list(dict.fromkeys(mids))})
    return {"shared_resources": shared, "event_count": sum(len(resource["evidence_ids"]) for resource in shared),
            "evidence_ids": list(dict.fromkeys(mid for resource in shared for mid in resource["evidence_ids"]))}


def _summarize(messages, agents, room, start, width, seed):
    network = analyze_network(messages, agents, seed=seed, null_replicates=0)
    authored = [message for message in messages if message["agent_id"]]
    counts = Counter(message["agent_id"] for message in authored)
    projections = network["projections"]
    mention = projections["observed_mentions"]
    metrics = mention["metrics"]["graph"]
    n = len(mention["nodes"])
    hhi = metrics["incoming_concentration_hhi"]
    concentrated = (hhi - 1 / n) / (1 - 1 / n) if hhi is not None and n > 1 else None
    strength = mention["metrics"]["nodes"]
    focus = max(strength, key=lambda node: (node["in_strength"], node["id"]))["id"] if metrics["interaction_count"] else None
    bridge = bridge_dependence(mention)
    resources = _url_recurrence(messages, agents)
    lexical = projections["inferred_lexical"]
    descriptor = {"id": "window-" + _fingerprint([room, iso_time(start), width])[:16], "room_id": room,
                  "start": iso_time(start), "end_exclusive": iso_time(start + timedelta(minutes=width)), "window_minutes": width,
                  "message_count": len(messages), "authored_agent_message_count": len(authored), "agent_author_count": len(counts),
                  "active_agent_ids": sorted(counts), "authored_messages_by_agent": dict(sorted(counts.items())),
                  "evidence_ids": [message["id"] for message in messages], "source_fingerprint": network["source_fingerprint"],
                  "features": {
                    "incoming_concentration": {"value": concentrated, "focus_agent_id": focus, "events": metrics["interaction_count"], "evidence_ids": list(dict.fromkeys(mid for edge in mention["edges"] for mid in edge["evidence_ids"]))},
                    "directed_reciprocity": {"value": metrics["weighted_reciprocity"], "events": metrics["interaction_count"], "evidence_ids": list(dict.fromkeys(mid for edge in mention["edges"] for mid in edge["evidence_ids"]))},
                    "bridge_dependence": {"value": bridge["maximum_loss_fraction"], "focus_agent_id": bridge["focus_agent_id"], "events": metrics["interaction_count"], "evidence_ids": list(dict.fromkeys(mid for edge in mention["edges"] for mid in edge["evidence_ids"])), "node_removal": bridge},
                    "lexical_recurrence_rate": {"value": lexical["metrics"]["graph"]["interaction_count"] / len(authored) if authored else None,
                        "events": lexical["metrics"]["graph"]["interaction_count"], "evidence_ids": list(dict.fromkeys(mid for edge in lexical["edges"] for mid in edge["evidence_ids"]))},
                    "shared_reference_rate": {"value": resources["event_count"] / len(authored) if authored else None,
                        "events": resources["event_count"], "evidence_ids": resources["evidence_ids"], "shared_resources": resources["shared_resources"]}},
                  "projections": {name: {"inferred": projection["inferred"], "edges": projection["edges"], "metrics": projection["metrics"]} for name, projection in projections.items()}}
    return descriptor


def _supported(window, name, min_messages, min_events):
    feature = window["features"][name]
    if window["authored_agent_message_count"] < min_messages:
        return False
    if window["agent_author_count"] < (3 if name in ("bridge_dependence", "incoming_concentration") else 2):
        return False
    # Rate comparisons admit a genuine observed zero as an ordinary comparator.
    return feature["value"] is not None and (feature["events"] >= min_events or name.endswith("_rate") and feature["events"] == 0)


def _matching_distance(first, second):
    a, b = set(first["active_agent_ids"]), set(second["active_agent_ids"])
    return abs(math.log(first["authored_agent_message_count"] / second["authored_agent_message_count"])) + abs(len(a) - len(b)) / max(len(a), len(b)) + 1 - len(a & b) / len(a | b)


def _nonoverlap(first, second):
    return first["end_exclusive"] <= second["start"] or second["end_exclusive"] <= first["start"]


def discover_graph_leads(messages: list[dict], agents=None, *, window_minutes: int = 60,
                         stride_minutes: int | None = None, min_messages: int = 12,
                         min_edge_events: int = 5, max_leads: int = 12, seed: int = 42,
                         max_windows: int = 120) -> dict:
    """Screen room-scoped windows and export graph leads for agent investigation.

    Comparisons are nearby, nonoverlapping windows matched on recorded message
    volume, active-author count and identity overlap. They are not causal controls.
    Robustness uses centered half/double-width windows and the same comparison.
    """
    stride_minutes = window_minutes if stride_minutes is None else stride_minutes
    for name, value, low, high in [("window_minutes", window_minutes, 10, 1440), ("stride_minutes", stride_minutes, 5, 1440),
                                  ("min_messages", min_messages, 2, 10000), ("min_edge_events", min_edge_events, 1, 10000),
                                  ("max_leads", max_leads, 1, 100), ("max_windows", max_windows, 1, 500)]:
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"{name} must be an integer from {low} to {high}")
    if len(messages) > 10000:
        raise ValueError("Graph discovery accepts at most 10000 scoped messages; import a bounded window")
    ordered = sorted((normalize_message(message) for message in messages), key=lambda message: (message["timestamp"], message["id"]))
    if len({message["id"] for message in ordered}) != len(ordered):
        raise ValueError("Message IDs must be unique")
    by_room = defaultdict(list)
    slots = set()
    step, width = stride_minutes * 60, window_minutes * 60
    for message in ordered:
        by_room[message["room_id"]].append(message)
        stamp = parse_time(message["timestamp"]).timestamp()
        anchor = math.floor(stamp / step) * step
        # Only windows containing source messages are considered; an absent
        # export period is not silently a zero-behavior control window.
        for offset in range(math.ceil(width / step)):
            start = anchor - offset * step
            if start <= stamp < start + width:
                slots.add((start, message["room_id"]))
    all_slots = sorted(slots)
    windows = []
    for stamp, room in all_slots[:max_windows]:
        start = datetime.fromtimestamp(stamp, timezone.utc)
        end = start + timedelta(minutes=window_minutes)
        selected = [message for message in by_room[room] if start <= parse_time(message["timestamp"]) < end]
        windows.append(_summarize(selected, agents, room, start, window_minutes, seed))
    leads = []
    tested = 0
    tested_by_feature = Counter()
    for window in windows:
        for name, definition in FEATURES.items():
            if not _supported(window, name, min_messages, min_edge_events):
                continue
            possible = [other for other in windows if other["room_id"] == window["room_id"] and _nonoverlap(window, other)
                        and abs((parse_time(window["start"]) - parse_time(other["start"])).total_seconds()) <= 86400
                        and _supported(other, name, min_messages, min_edge_events)]
            if not possible:
                continue
            comparison = min(possible, key=lambda other: (_matching_distance(window, other), other["id"]))
            tested += 1
            tested_by_feature[name] += 1
            value = window["features"][name]["value"]
            ordinary = comparison["features"][name]["value"]
            delta = value - ordinary
            if abs(delta) < definition["minimum_delta"] or window["features"][name]["events"] < min_edge_events:
                continue
            identity = "graph-lead-" + _fingerprint([GRAPH_DISCOVERY_VERSION, window["id"], comparison["id"], name])[:16]
            leads.append({"id": identity, "kind": "graph_" + name + "_shift", "title": name.replace("_", " ").capitalize() + " shifts across observed windows",
                          "status": "exploratory_lead", "channel": definition["channel"], "inferred": definition["channel"].startswith("inferred"),
                          "feature": name, "description": definition["description"], "value": value, "comparison_value": ordinary,
                          "difference": delta, "screening_score": abs(delta), "window_id": window["id"], "comparison_window_id": comparison["id"],
                          "focus_agent_id": window["features"][name].get("focus_agent_id"),
                          "comparison_focus_agent_id": comparison["features"][name].get("focus_agent_id"),
                          "evidence_ids": window["features"][name]["evidence_ids"], "comparison_evidence_ids": comparison["features"][name]["evidence_ids"],
                          "comparison_all_message_ids": comparison["evidence_ids"],
                          "support": {"events": window["features"][name]["events"], "comparison_events": comparison["features"][name]["events"],
                                      "messages": window["authored_agent_message_count"], "comparison_messages": comparison["authored_agent_message_count"]},
                          "comparison_match": {"distance": _matching_distance(window, comparison), "dimensions": ["log authored-message-count ratio", "active-author-count difference", "active-author identity overlap"],
                                               "nonoverlapping": True, "same_room": True, "causal_control": False},
                          "alternatives": definition["alternatives"], "interpretation": "Selected descriptive contrast for investigation; not evidence of novelty, causal influence or psychology."})
    # Reverse duplicates do not supply two independent discoveries. Keep one
    # orientation deterministically, prioritizing larger feature support.
    leads.sort(key=lambda lead: (-lead["screening_score"], -lead["support"]["events"], lead["id"]))
    unique, seen = [], set()
    for lead in leads:
        key = lead["feature"], tuple(sorted((lead["window_id"], lead["comparison_window_id"])))
        if key not in seen:
            seen.add(key)
            unique.append(lead)
    indexed_windows = {window["id"]: window for window in windows}
    for lead in unique[:max_leads]:
        selected, comparison = indexed_windows[lead["window_id"]], indexed_windows[lead["comparison_window_id"]]
        robustness = []
        for factor in (.5, 1.0, 2.0):
            new_width = max(5, round(window_minutes * factor))
            summaries = []
            for previous in (selected, comparison):
                center = parse_time(previous["start"]) + timedelta(minutes=window_minutes / 2)
                start = center - timedelta(minutes=new_width / 2)
                end = start + timedelta(minutes=new_width)
                slice_ = [message for message in by_room[previous["room_id"]] if start <= parse_time(message["timestamp"]) < end]
                summaries.append(_summarize(slice_, agents, previous["room_id"], start, new_width, seed))
            first, second = summaries
            supported = all(_supported(item, lead["feature"], min_messages, min_edge_events) for item in summaries)
            overlapping = not _nonoverlap(first, second)
            difference = first["features"][lead["feature"]]["value"] - second["features"][lead["feature"]]["value"] if supported else None
            robustness.append({"window_minutes": new_width, "supported": supported, "comparison_windows_overlap": overlapping,
                               "value": first["features"][lead["feature"]]["value"], "comparison_value": second["features"][lead["feature"]]["value"],
                               "difference": difference, "same_difference_direction": difference * lead["difference"] > 0 if difference is not None and not overlapping else None,
                               "focus_agent_id": first["features"][lead["feature"]].get("focus_agent_id"),
                               "focus_consistent": first["features"][lead["feature"]].get("focus_agent_id") == lead["focus_agent_id"] if lead["focus_agent_id"] else None,
                               "message_counts": [item["authored_agent_message_count"] for item in summaries],
                               "evidence_ids": first["features"][lead["feature"]]["evidence_ids"], "comparison_evidence_ids": second["features"][lead["feature"]]["evidence_ids"]})
        lead["window_robustness"] = robustness
        valid = [row for row in robustness if row["same_difference_direction"] is not None]
        lead["robustness_status"] = "consistent_in_eligible_nonoverlapping_windows" if valid and all(row["same_difference_direction"] for row in valid) and len(valid) >= 2 else "insufficient_or_window_sensitive"
    evidence = {message["id"]: {"id": message["id"], "timestamp": message["timestamp"], "agent_id": message["agent_id"],
                                "room_id": message["room_id"], "source": message["source"], "content_hash": message["content_hash"]} for message in ordered}
    return {"schema_version": "1.0", "analysis_version": GRAPH_DISCOVERY_VERSION,
            "source_fingerprint": _fingerprint([(message["id"], message["content_hash"]) for message in ordered]),
            "configuration": {"window_minutes": window_minutes, "stride_minutes": stride_minutes, "min_messages": min_messages, "min_edge_events": min_edge_events,
                              "max_leads": max_leads, "seed": seed, "max_windows": max_windows, "features": FEATURES},
            "scope": {"message_count": len(ordered), "room_count": len(by_room), "candidate_windows": len(all_slots), "analyzed_windows": len(windows),
                      "windows_truncated": len(all_slots) > max_windows, "window_selection": "Earliest chronological nonempty UTC-aligned room windows",
                      "retained_first_message": ordered[0]["timestamp"] if ordered else None, "retained_last_message": ordered[-1]["timestamp"] if ordered else None,
                      "coverage_status": "Retained-message timestamps do not establish complete export coverage or time at risk."},
            "windows": windows, "leads": unique[:max_leads], "evidence_index": evidence,
            "selection": {"feature_window_comparisons": tested, "feature_window_comparisons_by_feature": dict(tested_by_feature), "screening_candidates": len(leads), "deduplicated_leads": len(unique),
                          "returned_leads": min(len(unique), max_leads), "multiple_search": True, "confirmatory": False,
                          "warning": "Windows, features and comparisons were screened and ranked; no causal effect, significance or novelty is established."},
            "limitations": ["Observed mentions, observed reply pointers, inferred lexical recurrence and exact resource references are separate instruments.",
                            "Comparisons match recorded activity proxies, not goals, model, roles, membership, reading, task difficulty or external events.",
                            "Activity/membership censoring and incomplete export periods can create apparent changes.",
                            "A shared resource is provenance evidence of citation only; source-to-agent information lineage is unobserved.",
                            "Robustness windows reuse evidence and are sensitivity checks, not independent replications; overlapping widened comparisons are flagged.",
                            "Descriptive graph leads must be adjudicated against source messages before experimental hypotheses are frozen.",
                            "Graph-Laplacian math is not a continuous-manifold LBO or a detector of psychological properties."]}
