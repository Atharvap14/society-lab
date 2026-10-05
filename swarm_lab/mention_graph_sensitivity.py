"""CPU-only diagnostic mention graphs under declared measurement variants.

The audit is independently recomputed against supplied messages and the pinned
roster. Four projections share one disclosed node universe. No graph is written
to the main discovery system, and no behavioral or causal effect is inferred.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from .dataset import normalize_message
from .name_eligibility_sensitivity import (
    NAME_ELIGIBILITY_SENSITIVITY_VERSION, audit_name_eligibility_sensitivity,
)
from .network import NETWORK_VERSION, _aggregate, _metrics, spectral_basis


MENTION_GRAPH_SENSITIVITY_VERSION = "fixed-universe-mention-graphs-v1"
VARIANT_LABELS = {
    "baseline_exact": "Original minimum-three-character exact-display-name instrument",
    "explicit_short_expanded_exact": "Exact baseline plus explicitly allowlisted short-name candidates",
    "unicode_baseline": "Minimum-three-character Unicode shadow candidates",
    "unicode_expanded": "Unicode baseline plus explicitly allowlisted short-name shadow candidates",
}
GRAPH_FIELDS = (
    "node_count", "directed_edge_count", "interaction_count", "directed_density",
    "binary_reciprocity", "weighted_reciprocity", "incoming_concentration_hhi",
    "outgoing_concentration_hhi", "max_incoming_share",
)
NODE_FIELDS = (
    "in_degree", "out_degree", "in_strength", "out_strength",
    "authored_message_count", "outgoing_interactions_per_authored_message",
    "coactive_room_other_message_count", "incoming_interactions_per_coactive_message",
    "directed_unweighted_betweenness",
)


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Audit fields must be finite JSON data") from exc


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _difference(first, second):
    if type(first) not in (int, float) or type(second) not in (int, float):
        return None
    return second - first if math.isfinite(first) and math.isfinite(second) else None


def _variants(audit):
    shadow = audit["unicode_shadow"]
    return {
        "baseline_exact": audit["baseline_exact_events"],
        "explicit_short_expanded_exact": audit["baseline_exact_events"] + audit["short_name_exact_events"],
        "unicode_baseline": shadow["baseline_shadow_events"] if shadow["enabled"] else None,
        "unicode_expanded": shadow["baseline_shadow_events"] + shadow["short_name_shadow_events"] if shadow["enabled"] else None,
    }


def _code_hashes():
    directory = Path(__file__).resolve().parent
    return {
        name: {"sha256": hashlib.sha256((directory / filename).read_bytes()).hexdigest(),
               "hash_purpose": "Binary implementation-file identity; distinct from JSON audit/source fingerprints."}
        for name, filename in [
            ("dataset", "dataset.py"), ("network", "network.py"),
            ("mention_sensitivity", "mention_sensitivity.py"),
            ("name_eligibility_sensitivity", "name_eligibility_sensitivity.py"),
            ("mention_graph_sensitivity", "mention_graph_sensitivity.py"),
        ]
    }


def compare_name_graphs(messages: list[dict], eligibility_audit: dict, *, agents: list[dict] | dict | None = None) -> dict:
    """Compare diagnostic graph metrics, never coordinates across changed bases.

    Pass the exact pinned roster as agents when the audit used one. Omission is
    supported only when the audit's effective roster can be reproduced from the
    messages. Source/context, roster, event lists, policy and derived counts are
    independently recomputed. Missing optional shadow measurements remain
    explicitly unavailable; they are not fabricated or implicitly requested.
    """
    if not isinstance(eligibility_audit, dict):
        raise ValueError("Provide a name-eligibility audit payload")
    if eligibility_audit.get("analysis_version") != NAME_ELIGIBILITY_SENSITIVITY_VERSION:
        raise ValueError("Unsupported eligibility audit version")
    shadow = eligibility_audit.get("unicode_shadow")
    if not isinstance(shadow, dict) or type(shadow.get("enabled")) is not bool:
        raise ValueError("Audit requires an explicit Unicode-shadow enabled flag")
    requested = eligibility_audit.get("requested_names")
    if not isinstance(requested, list):
        raise ValueError("Audit requires its explicit requested-name allowlist")
    expected = audit_name_eligibility_sensitivity(
        messages, agents, short_name_allowlist=requested,
        include_unicode_shadow=shadow["enabled"])
    for field in ("source_fingerprint", "roster_fingerprint"):
        if eligibility_audit.get(field) != expected[field]:
            raise ValueError(f"Input {field} mismatch; supply the original messages and pinned roster")

    streams = _variants(expected)
    supplied_streams = None
    try:
        supplied_streams = _variants(eligibility_audit)
    except (KeyError, TypeError) as exc:
        raise ValueError("Audit is missing required event lists") from exc
    known_sources = set(expected["evidence_index"])
    known_targets = {event["target_agent_id"] for events in streams.values() if events is not None for event in events}
    for name, events in supplied_streams.items():
        if events is None:
            continue
        if not isinstance(events, list):
            raise ValueError("Variant event collections must be lists")
        seen = set()
        for event in events:
            if not isinstance(event, dict):
                raise ValueError("Mention events must be dictionaries")
            source, target = event.get("message_id"), event.get("target_agent_id")
            if not isinstance(source, str) or source not in known_sources:
                raise ValueError("Mention event has unknown source message ID")
            if not isinstance(target, str) or target not in known_targets:
                raise ValueError("Mention event has unknown or unmeasured target ID")
            key = source, target
            if key in seen:
                raise ValueError("Duplicate message/target event in a graph variant")
            seen.add(key)
    # Canonical comparison also distinguishes booleans from numeric span/counts.
    fields = (
        "schema_version", "kind", "analysis_version", "baseline_instrument_version",
        "scope", "bounds", "requested_names", "resolved_agent_ids", "allowlist_resolution",
        "normalization_policy", "eligibility_policy", "summary", "evidence_index",
        "baseline_exact_events", "short_name_exact_events", "ambiguous_exact_events",
        "original_roster_collisions", "unicode_shadow",
    )
    for field in fields:
        if field not in eligibility_audit or _canonical(eligibility_audit[field]) != _canonical(expected[field]):
            raise ValueError(f"Audit {field} does not match independently recomputed measurement")

    ordered = sorted((normalize_message(message) for message in messages),
                     key=lambda message: (message["timestamp"], message["id"]))
    indexed = {message["id"]: message for message in ordered}
    authors = {message["agent_id"] for message in ordered if message["agent_id"]}
    targets = {event["target_agent_id"] for events in streams.values() if events is not None for event in events}
    nodes = sorted(authors | targets)
    if len(nodes) > expected["bounds"]["max_agents"]:
        raise ValueError("Fixed node universe exceeds the audit's agent bound")
    roster = agents.values() if isinstance(agents, dict) else agents or []
    names = {str(agent["id"]): str(agent.get("name", agent["id"])) for agent in roster if agent.get("id")}
    for message in ordered:
        if message["agent_id"]:
            names.setdefault(message["agent_id"], message["agent_name"])
    graphs = {}
    for variant, events in streams.items():
        if events is None:
            graphs[variant] = {"available": False, "label": VARIANT_LABELS[variant],
                               "reason": "Unicode-shadow measurement was not requested in the input audit.",
                               "node_universe": list(nodes)}
            continue
        projected, excluded = [], []
        event_lookup = {}
        for event in events:
            message = indexed[event["message_id"]]
            if not message["agent_id"]:
                excluded.append(event["event_id"])
                continue
            projected.append({"source": message["agent_id"], "target": event["target_agent_id"],
                              "timestamp": message["timestamp"], "evidence_ids": [message["id"]],
                              "inferred": False})
            event_lookup[(message["id"], event["target_agent_id"])] = event
        edges = _aggregate(projected)
        for edge in edges:
            original_events = [event_lookup[(identity, edge["target"])] for identity in edge["evidence_ids"]]
            edge["measurement_event_ids"] = [event["event_id"] for event in original_events]
            edge["instrument_event_counts"] = dict(sorted(Counter(event["instrument"] for event in original_events).items()))
            edge["source_event_refs"] = [
                {"event_id": event["event_id"], "message_id": event["message_id"],
                 "instrument": event["instrument"], "measurement_status": event["status"],
                 "span": copy.deepcopy(event["span"])}
                for event in original_events
            ]
            edge["interpretation"] = "Diagnostic name-pattern relation, not verified address, delivery or causal influence."
        metrics = _metrics(nodes, edges, messages=ordered)
        basis = spectral_basis(nodes, edges)
        spectral = {key: copy.deepcopy(value) for key, value in basis.items() if key != "modes"}
        incident_nodes = {edge[key] for edge in edges for key in ("source", "target")}
        graphs[variant] = {
            "available": True, "label": VARIANT_LABELS[variant], "directed": True,
            "diagnostic_only": True, "nodes": [{"id": identity, "name": names.get(identity, identity),
                                              "observed_author_in_scope": identity in authors} for identity in nodes],
            "edges": edges, "metrics": metrics, "spectral": spectral,
            "counts": {
                "node_universe_count": len(nodes), "incident_node_count": len(incident_nodes),
                "isolate_count": len(metrics["graph"]["isolate_ids"]),
                "source_measurement_event_count": len(events),
                "projected_agent_event_count": len(projected),
                "excluded_human_source_event_count": len(excluded),
                "recorded_target_count": len({event["target_agent_id"] for event in events}),
                "projected_target_count": len({event["target"] for event in projected}),
            },
            "excluded_human_source_event_ids": excluded,
        }

    comparisons = []
    reference = graphs["baseline_exact"]
    reference_nodes = {node["id"]: node for node in reference["metrics"]["nodes"]}
    for variant in VARIANT_LABELS:
        if variant == "baseline_exact":
            continue
        compared = graphs[variant]
        if not compared["available"]:
            comparisons.append({"reference": "baseline_exact", "variant": variant,
                                "available": False, "reason": compared["reason"]})
            continue
        metric_changes = {field: {"reference": reference["metrics"]["graph"][field],
                                  "variant": compared["metrics"]["graph"][field],
                                  "difference": _difference(reference["metrics"]["graph"][field], compared["metrics"]["graph"][field])}
                          for field in GRAPH_FIELDS}
        compared_nodes = {node["id"]: node for node in compared["metrics"]["nodes"]}
        node_changes = [
            {"agent_id": identity, "metrics": {
                field: {"reference": reference_nodes[identity][field],
                        "variant": compared_nodes[identity][field],
                        "difference": _difference(reference_nodes[identity][field], compared_nodes[identity][field])}
                for field in NODE_FIELDS}}
            for identity in nodes
        ]
        first_basis, second_basis = reference["spectral"], compared["spectral"]
        if first_basis.get("available") and second_basis.get("available"):
            spectral_change = {
                "available": True, "operator": first_basis["operator"],
                "nullity_difference": second_basis["nullity"] - first_basis["nullity"],
                "reference_nullity": first_basis["nullity"], "variant_nullity": second_basis["nullity"],
                "ordered_eigenvalues": [
                    {"index": position, "reference": first, "variant": second, "difference": second - first}
                    for position, (first, second) in enumerate(zip(first_basis["eigenvalues"], second_basis["eigenvalues"]))],
                "algebraic_connectivity_difference": _difference(first_basis.get("algebraic_connectivity"),
                                                                 second_basis.get("algebraic_connectivity")),
                "interpretation": "Ordered spectral statistics of changed operators on a fixed universe; no persistent mode-coordinate correspondence.",
            }
        else:
            spectral_change = {"available": False, "reason": first_basis.get("reason") or second_basis.get("reason")}
        comparisons.append({
            "reference": "baseline_exact", "variant": variant, "available": True,
            "count_differences": {field: compared["counts"][field] - reference["counts"][field]
                                  for field in reference["counts"]},
            "graph_metrics": metric_changes, "node_metrics": node_changes,
            "spectral": spectral_change,
        })
    return {
        "schema_version": "1.0", "analysis_version": MENTION_GRAPH_SENSITIVITY_VERSION,
        "kind": "mention_graph_measurement_sensitivity", "read_only": True, "model_calls": 0,
        "network_metrics_version": NETWORK_VERSION, "eligibility_audit_version": expected["analysis_version"],
        "source_fingerprint": expected["source_fingerprint"], "roster_fingerprint": expected["roster_fingerprint"],
        "supplied_audit_fingerprint": _digest(eligibility_audit), "code_hashes": _code_hashes(),
        "validation": {"source_context_match": True, "roster_match": True,
                       "event_lists_and_summaries_recomputed": True, "bounds_match": True},
        "scope": copy.deepcopy(expected["scope"]), "bounds": copy.deepcopy(expected["bounds"]),
        "node_universe": {"ids": nodes, "agent_author_ids": sorted(authors),
                          "accepted_variant_target_ids": sorted(targets),
                          "target_ids_without_authored_messages": sorted(targets - authors),
                          "policy": "All supplied agent-authored IDs plus accepted targets across available variants; one fixed common universe.",
                          "dashboard_equivalence": "Not necessarily the original dashboard graph's scope-specific node universe.",
                          "human_policy": "Human-source events are validated and disclosed, then excluded from the agent graph; their accepted targets can remain in the common universe."},
        "variants": graphs, "comparisons": comparisons,
        "limitations": [
            "These are measurement-sensitivity graphs; candidate matches are not promoted to main discovery edges.",
            "Changes in centrality, concentration, reachability or spectrum may arise solely from extraction eligibility or formatting.",
            "Name matches do not prove intended address, delivery, reading, behavioral influence or a causal network effect.",
            "The fixed universe may include nodes isolated only under one measurement; it is not necessarily the existing dashboard universe.",
            "Referenced targets without authored messages have unknown outgoing rates/exposure; no zero imputation is performed.",
            "Coactive-message counts are existing room activity proxies, not membership, reading or time at risk.",
            "Spectra use the existing symmetrized normalized graph Laplacian, with zero isolate rows; direction is retained only in directed metrics.",
            "Eigenvector coordinates are excluded and never compared across changed operators; repeated eigenspaces do not define persistent agent traits.",
            "The audit compares the same records, not independent replications or calibrated proof of short-name identity.",
        ],
    }
