"""Evidence-traceable network analysis of recorded agent communication.

Observed mention/reply networks are never pooled with inferred proximity and
lexical networks. Directed metrics retain direction. Only the spectral operator
explicitly symmetrizes. These descriptors identify questions, not causal effects.
"""
from __future__ import annotations

import math
import random
import statistics
from collections import Counter, defaultdict, deque
from typing import Any

from .dataset import normalize_message, parse_time
from .discovery import build_graph


NETWORK_VERSION = "communication-networks-v1"


def _aggregate(events: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str], dict] = {}
    for event in events:
        if event["source"] == event["target"]:
            continue
        key = event["source"], event["target"]
        if key not in grouped:
            grouped[key] = {"source": key[0], "target": key[1], "weight": 0, "evidence_ids": [], "events": [], "inferred": event.get("inferred", False)}
        edge = grouped[key]
        edge["weight"] += 1
        edge["events"].append({"timestamp": event.get("timestamp"), "evidence_ids": event.get("evidence_ids", [])})
        edge["evidence_ids"] = list(dict.fromkeys(edge["evidence_ids"] + event.get("evidence_ids", [])))
    return [grouped[key] for key in sorted(grouped)]


def _components(nodes: list[str], neighbors: dict[str, set[str]]) -> list[list[str]]:
    unvisited = set(nodes)
    result = []
    while unvisited:
        root = min(unvisited)
        queue, component = [root], []
        unvisited.remove(root)
        while queue:
            current = queue.pop()
            component.append(current)
            for neighbor in sorted(neighbors.get(current, set())):
                if neighbor in unvisited:
                    unvisited.remove(neighbor)
                    queue.append(neighbor)
        result.append(sorted(component))
    return sorted(result, key=lambda component: (-len(component), component))


def _strong_components(nodes: list[str], outgoing: dict[str, set[str]]) -> list[list[str]]:
    incoming = defaultdict(set)
    for source, targets in outgoing.items():
        for target in targets:
            incoming[target].add(source)
    # Iterative DFS avoids recursion depth dependence even for larger inputs.
    visited, finished = set(), []
    for root in nodes:
        if root in visited:
            continue
        stack = [(root, False)]
        while stack:
            current, expanded = stack.pop()
            if expanded:
                finished.append(current)
                continue
            if current in visited:
                continue
            visited.add(current)
            stack.append((current, True))
            for target in sorted(outgoing.get(current, set()), reverse=True):
                if target not in visited:
                    stack.append((target, False))
    unvisited = set(nodes)
    result = []
    for root in reversed(finished):
        if root not in unvisited:
            continue
        queue, component = [root], []
        unvisited.remove(root)
        while queue:
            current = queue.pop()
            component.append(current)
            for neighbor in sorted(incoming[current]):
                if neighbor in unvisited:
                    unvisited.remove(neighbor)
                    queue.append(neighbor)
        result.append(sorted(component))
    return sorted(result, key=lambda component: (-len(component), component))


def _betweenness(nodes: list[str], outgoing: dict[str, set[str]]) -> dict[str, float]:
    """Exact unweighted directed Brandes algorithm, excluding endpoints."""
    centrality = {node: 0.0 for node in nodes}
    for source in nodes:
        stack = []
        predecessors = {node: [] for node in nodes}
        paths = {node: 0 for node in nodes}
        distance = {node: -1 for node in nodes}
        paths[source], distance[source] = 1, 0
        queue = deque([source])
        while queue:
            current = queue.popleft()
            stack.append(current)
            for target in sorted(outgoing[current]):
                if distance[target] < 0:
                    queue.append(target)
                    distance[target] = distance[current] + 1
                if distance[target] == distance[current] + 1:
                    paths[target] += paths[current]
                    predecessors[target].append(current)
        dependency = {node: 0.0 for node in nodes}
        while stack:
            current = stack.pop()
            if paths[current]:
                factor = (1 + dependency[current]) / paths[current]
                for previous in predecessors[current]:
                    dependency[previous] += paths[previous] * factor
            if current != source:
                centrality[current] += dependency[current]
    denominator = (len(nodes) - 1) * (len(nodes) - 2)
    return {node: value / denominator if denominator > 0 else 0.0 for node, value in centrality.items()}


def _quick_metrics(nodes: list[str], edges: list[dict]) -> dict:
    pairs = {(edge["source"], edge["target"]): edge["weight"] for edge in edges}
    total = sum(pairs.values())
    incoming, outgoing = Counter(), Counter()
    for (source, target), weight in pairs.items():
        incoming[target] += weight
        outgoing[source] += weight
    n = len(nodes)
    return {
        "node_count": n,
        "directed_edge_count": len(pairs),
        "interaction_count": total,
        "directed_density": len(pairs) / (n * (n - 1)) if n > 1 else 0.0,
        "binary_reciprocity": sum((target, source) in pairs for source, target in pairs) / len(pairs) if pairs else None,
        "weighted_reciprocity": sum(min(weight, pairs.get((target, source), 0)) for (source, target), weight in pairs.items()) / total if total else None,
        "incoming_concentration_hhi": sum((incoming[node] / total) ** 2 for node in nodes) if total else None,
        "outgoing_concentration_hhi": sum((outgoing[node] / total) ** 2 for node in nodes) if total else None,
        "max_incoming_share": max(incoming.values(), default=0) / total if total else None,
    }


def _metrics(nodes: list[str], edges: list[dict], *, messages: list[dict]) -> dict:
    outgoing = {node: set() for node in nodes}
    incoming = {node: set() for node in nodes}
    weak = {node: set() for node in nodes}
    in_strength, out_strength = Counter(), Counter()
    authored = Counter(message["agent_id"] for message in messages if message["agent_id"])
    active_rooms = defaultdict(set)
    agent_messages = [message for message in messages if message["agent_id"]]
    for message in agent_messages:
        active_rooms[message["agent_id"]].add(message["room_id"])
    for edge in edges:
        source, target, weight = edge["source"], edge["target"], edge["weight"]
        outgoing[source].add(target)
        incoming[target].add(source)
        weak[source].add(target)
        weak[target].add(source)
        out_strength[source] += weight
        in_strength[target] += weight
    between = _betweenness(nodes, outgoing)
    node_metrics = []
    for node in nodes:
        coactive = sum(message["agent_id"] != node and message["room_id"] in active_rooms[node] for message in agent_messages)
        node_metrics.append({"id": node, "in_degree": len(incoming[node]), "out_degree": len(outgoing[node]), "in_strength": in_strength[node], "out_strength": out_strength[node], "authored_message_count": authored[node], "outgoing_interactions_per_authored_message": out_strength[node] / authored[node] if authored[node] else None, "coactive_room_other_message_count": coactive, "incoming_interactions_per_coactive_message": in_strength[node] / coactive if coactive else None, "directed_unweighted_betweenness": between[node], "isolate": not (incoming[node] or outgoing[node])})
    graph = _quick_metrics(nodes, edges)
    graph.update(weak_components=_components(nodes, weak), strong_components=_strong_components(nodes, outgoing), isolate_ids=[node for node in nodes if not weak[node]])
    return {"graph": graph, "nodes": node_metrics, "definitions": {"degree": "Number of distinct directed neighbors.", "strength": "Number of recorded relational events on directed ties.", "betweenness": "Unweighted directed shortest paths, excludes endpoints, divided by (n-1)(n-2); no claim of actual information mediation.", "exposure_proxy": "Coactivity means the target posted at least once in the same room in this imported window; membership, reading and time-at-risk are unknown.", "rate": "Events per message can exceed one because a message may mention several agents."}}


def spectral_basis(nodes: list[str], edges: list[dict]) -> dict:
    """Normalized graph-Laplacian basis, explicitly distinct from a manifold LBO."""
    try:
        import numpy as np
    except ImportError:
        return {"available": False, "reason": "Install optional numpy dependency for eigen-decomposition; directed network metrics remain available.", "operator": "normalized_graph_laplacian"}
    if len(nodes) > 128:
        return {"available": False, "reason": "Dense eigensolver bounded to 128 nodes; use an explicit sparse adapter for larger networks.", "operator": "normalized_graph_laplacian"}
    n = len(nodes)
    if not n:
        return {"available": True, "operator": "normalized_graph_laplacian", "node_order": [], "eigenvalues": [], "modes": [], "nullity": 0, "warnings": ["Empty graph."]}
    index = {node: position for position, node in enumerate(nodes)}
    directed = np.zeros((n, n), dtype=float)
    for edge in edges:
        directed[index[edge["source"]], index[edge["target"]]] += float(edge["weight"])
    symmetric = (directed + directed.T) / 2
    np.fill_diagonal(symmetric, 0)
    degree = symmetric.sum(axis=1)
    inverse = np.zeros(n, dtype=float)
    inverse[degree > 0] = 1 / np.sqrt(degree[degree > 0])
    laplacian = np.diag((degree > 0).astype(float)) - inverse[:, None] * symmetric * inverse[None, :]
    eigenvalues, eigenvectors = np.linalg.eigh(laplacian)
    eigenvalues[np.abs(eigenvalues) < 1e-10] = 0
    nullity = int(np.count_nonzero(eigenvalues == 0))
    isolated = [nodes[i] for i, value in enumerate(degree) if value == 0]
    degeneracies = []
    start = 0
    while start < n:
        stop = start + 1
        while stop < n and abs(eigenvalues[stop] - eigenvalues[start]) < 1e-8:
            stop += 1
        if stop - start > 1:
            degeneracies.append({"start_mode": start, "end_mode_inclusive": stop - 1, "eigenvalue": float(eigenvalues[start])})
        start = stop
    modes = []
    for mode in range(n):
        vector = eigenvectors[:, mode]
        pivot = int(np.argmax(np.abs(vector)))
        if vector[pivot] < 0:
            vector *= -1
        modes.append({"index": mode, "eigenvalue": float(eigenvalues[mode]), "coefficients": {node: float(vector[index[node]]) for node in nodes}, "null_mode": bool(eigenvalues[mode] == 0)})
    warnings = ["A graph spectral basis is not established as a manifold Laplace–Beltrami basis.", "Symmetrization discards direction for this operator only.", "Eigenvector signs and bases within repeated eigenspaces are not identifiable across runs.", "Static shortest paths and spectra ignore whether paths respect temporal order."]
    if nullity > 1:
        warnings.append("Disconnected graph: multiple null modes; a unique Fiedler/community axis is not defined.")
    if isolated:
        warnings.append("Isolates use zero Laplacian rows and contribute null modes; silence is not social isolation.")
    return {"available": True, "backend": "numpy.linalg.eigh", "operator": "normalized_graph_laplacian", "formula": "L = D^(-1/2)(D-S)D^(-1/2), S=(A+A^T)/2; isolates have zero rows", "node_order": nodes, "eigenvalues": [float(value) for value in eigenvalues], "modes": modes, "nullity": nullity, "isolated_ids": isolated, "repeated_eigenspaces": degeneracies, "algebraic_connectivity": float(eigenvalues[1]) if n >= 2 else None, "warnings": warnings}


def _null_reference(messages: list[dict], mention_events: list[dict], nodes: list[str], *, seed: int, replicates: int) -> dict:
    """Conditional descriptive reference: permute authors within room-hour slots."""
    if replicates == 0:
        return {"enabled": False, "reason": "null_replicates=0"}
    indexed = {message["id"]: message for message in messages}
    strata: dict[str, list[str]] = defaultdict(list)
    for message in messages:
        if message["agent_id"]:
            hour = parse_time(message["timestamp"]).strftime("%Y-%m-%dT%H")
            strata[message["room_id"] + "|" + hour].append(message["id"])
    rng = random.Random(seed)
    observed = _quick_metrics(nodes, _aggregate(mention_events))
    sampled: dict[str, list[float]] = defaultdict(list)
    for _ in range(replicates):
        assigned = {}
        for slots in strata.values():
            labels = [indexed[identity]["agent_id"] for identity in slots]
            rng.shuffle(labels)
            assigned.update(zip(slots, labels))
        randomized = []
        for event in mention_events:
            mid = event["evidence_ids"][0]
            source = assigned.get(mid)
            if source and source != event["target"]:
                randomized.append({**event, "source": source})
        values = _quick_metrics(nodes, _aggregate(randomized))
        for key in ("binary_reciprocity", "weighted_reciprocity", "directed_density", "incoming_concentration_hhi", "outgoing_concentration_hhi", "max_incoming_share"):
            if values[key] is not None:
                sampled[key].append(values[key])
    comparisons = {}
    for key, values in sampled.items():
        actual = observed[key]
        mean = statistics.fmean(values)
        deviation = statistics.pstdev(values)
        comparisons[key] = {"observed": actual, "reference_mean": mean, "reference_sd": deviation, "standardized_difference": (actual - mean) / deviation if actual is not None and deviation > 0 else None, "upper_reference_tail_fraction": (1 + sum(value >= actual for value in values)) / (len(values) + 1) if actual is not None else None, "lower_reference_tail_fraction": (1 + sum(value <= actual for value in values)) / (len(values) + 1) if actual is not None else None, "valid_replicates": len(values), "degenerate_reference": deviation == 0}
    return {"enabled": True, "model": "author_labels_permuted_within_room_UTC_hour", "seed": seed, "replicates": replicates, "strata": len(strata), "exchangeable_strata": sum(len({indexed[identity]["agent_id"] for identity in slots}) > 1 for slots in strata.values()), "comparisons": comparisons, "preserves": ["Message timestamps and room slots", "Each agent's authored message count within each room-hour", "Content and explicit mention targets"], "destroys": ["Association between author and message content", "Cross-agent ordering within room-hour", "Original sender–target ties"], "limitations": ["Descriptive permutation reference, not a randomized treatment or causal test.", "Speaker exchangeability is not guaranteed; roles, goals, models and activity may confound comparison.", "Self-mentions created by permutation are excluded, so interaction counts may vary.", "Tail fractions are exploratory, not multiplicity-adjusted confirmatory p-values.", "Hour stratification is a chosen timescale; robustness to other strata requires a separate analysis."]}


def analyze_network(messages: list[dict], agents: list[dict] | dict | None = None, *, seed: int = 42, null_replicates: int = 100) -> dict:
    """Analyze four explicitly distinct projections with provenance and caveats."""
    if not isinstance(null_replicates, int) or isinstance(null_replicates, bool) or not 0 <= null_replicates <= 1000:
        raise ValueError("null_replicates must be an integer from 0 to 1000")
    ordered = sorted([normalize_message(message) for message in messages], key=lambda message: (message["timestamp"], message["id"]))
    indexed = {message["id"]: message for message in ordered}
    if len(indexed) != len(ordered):
        raise ValueError("Message IDs must be unique")
    graph = build_graph(ordered, agents=agents)
    names = {node["id"][len("speaker:"):]: node.get("name", node["id"]) for node in graph["nodes"] if node["kind"] == "agent"}
    active = {message["agent_id"] for message in ordered if message["agent_id"]}
    channels: dict[str, list[dict]] = {"observed_mentions": [], "observed_replies": [], "inferred_proximity": [], "inferred_lexical": []}
    for edge in graph["edges"]:
        if edge["kind"] == "mentions":
            mid = edge["source"][len("message:"):]
            source = indexed[mid]["agent_id"]
            target = edge["target"][len("speaker:"):]
            channel = "observed_mentions"
            evidence = [mid]
        elif edge["kind"] in ("explicit_reply", "temporal_proximity", "lexical_recurrence"):
            first = edge["source"][len("message:"):]
            last = edge["target"][len("message:"):]
            if first not in indexed or last not in indexed:
                continue
            source, target = indexed[first]["agent_id"], indexed[last]["agent_id"]
            channel = {"explicit_reply": "observed_replies", "temporal_proximity": "inferred_proximity", "lexical_recurrence": "inferred_lexical"}[edge["kind"]]
            evidence = [first, last]
        else:
            continue
        if source and target and source != target:
            channels[channel].append({"source": source, "target": target, "timestamp": edge["timestamp"], "evidence_ids": evidence, "inferred": edge["inferred"]})
    nodes = sorted(active | {event["target"] for events in channels.values() for event in events})
    if len(nodes) > 1000:
        raise ValueError("Analysis limited to 1000 agents; partition or supply a sparse adapter")
    projections = {}
    descriptions = {"observed_mentions": "Speaker explicitly names another roster agent; one tie event per named recipient per message. No inference of delivery or agreement.", "observed_replies": "Recorded reply pointer, responder to parent-message author. The export usually has no reply pointers.", "inferred_proximity": "Previous to next cross-speaker message within five minutes in the same room; possible interaction only.", "inferred_lexical": "Previous to next cross-speaker message with overlapping words; shared context can explain similarity."}
    for channel, events in channels.items():
        edges = _aggregate(events)
        projections[channel] = {"description": descriptions[channel], "directed": True, "inferred": channel.startswith("inferred"), "nodes": [{"id": node, "name": names.get(node, node), "observed_author_in_scope": node in active} for node in nodes], "edges": edges, "metrics": _metrics(nodes, edges, messages=ordered), "spectral": spectral_basis(nodes, edges)}
    fingerprint_data = "|".join(message["id"] + ":" + message["content_hash"] for message in ordered)
    import hashlib
    return {"schema_version": "1.0", "analysis_version": NETWORK_VERSION, "source_fingerprint": hashlib.sha256(fingerprint_data.encode()).hexdigest(), "scope": {"message_count": len(ordered), "agent_authors": len(active), "start": ordered[0]["timestamp"] if ordered else None, "end": ordered[-1]["timestamp"] if ordered else None}, "projections": projections, "null_reference": _null_reference(ordered, channels["observed_mentions"], nodes, seed=seed, replicates=null_replicates), "limitations": ["Descriptive network structure is not an identified network effect.", "Recorded coactivity is only an exposure proxy; reading and causal transmission are unobserved.", "Active nodes are scope-specific; referenced agents may not have authored messages in scope.", "The network excludes human speakers and exact-name matching misses aliases.", "Static paths can include contacts in an impossible temporal order.", "Graph Laplacian basis is provisional; the user's intended meaning of LBO must be confirmed."]}
