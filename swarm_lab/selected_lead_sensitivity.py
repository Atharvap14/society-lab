"""Read-only name-instrument sensitivity of already selected graph contrasts.

The legacy discovery is recomputed only as a fail-closed replay guard. Variants
never select, rank, or rematch leads. Native and fixed-pair universes are separate.
No database, network, filesystem mutation, or model invocation occurs.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

from .dataset import normalize_message, parse_time
from .graph_discovery import (
    FEATURES, GRAPH_DISCOVERY_VERSION, _supported, bridge_dependence,
    discover_graph_leads,
)
from .mention_graph_sensitivity import VARIANT_LABELS
from .name_eligibility_sensitivity import (
    NAME_ELIGIBILITY_SENSITIVITY_VERSION, audit_name_eligibility_sensitivity,
)
from .network import NETWORK_VERSION, _aggregate, _metrics


SELECTED_LEAD_SENSITIVITY_VERSION = "selected-lead-name-sensitivity-v1"
MAX_SELECTED_LEADS = 12
MAX_SELECTED_WINDOWS = 24
MAX_REPLAY_WINDOWS = 120
EQUALITY_TOLERANCE = 1e-12
_CONFIG_KEYS = (
    "window_minutes", "stride_minutes", "min_messages", "min_edge_events",
    "max_leads", "seed", "max_windows",
)
_INVARIANT_FEATURES = ("lexical_recurrence_rate", "shared_reference_rate")


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Inputs and outputs must contain finite JSON data") from exc


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _first_difference(first, second, path="graph_search"):
    if type(first) is not type(second):
        return path
    if isinstance(first, dict):
        if set(first) != set(second):
            return path + ".keys"
        for key in sorted(first):
            difference = _first_difference(first[key], second[key], path + "." + key)
            if difference:
                return difference
    elif isinstance(first, list):
        if len(first) != len(second):
            return path + ".length"
        for index, (left, right) in enumerate(zip(first, second)):
            difference = _first_difference(left, right, f"{path}[{index}]")
            if difference:
                return difference
    elif first != second:
        return path
    return None


def _code_hashes():
    directory = Path(__file__).resolve().parent
    return {
        filename: {
            "sha256": hashlib.sha256((directory / filename).read_bytes()).hexdigest(),
            "hash_purpose": "Binary implementation-file identity, not a source or JSON-object hash.",
        }
        for filename in (
            "dataset.py", "discovery.py", "network.py", "graph_discovery.py",
            "mention_sensitivity.py", "name_eligibility_sensitivity.py", "mention_graph_sensitivity.py",
            "selected_lead_sensitivity.py",
        )
    }


def _streams(audit):
    shadow = audit["unicode_shadow"]
    return {
        "baseline_exact": audit["baseline_exact_events"],
        "explicit_short_expanded_exact":
            audit["baseline_exact_events"] + audit["short_name_exact_events"],
        "unicode_baseline": shadow["baseline_shadow_events"] if shadow["enabled"] else None,
        "unicode_expanded":
            shadow["baseline_shadow_events"] + shadow["short_name_shadow_events"]
            if shadow["enabled"] else None,
    }


def _project(events, indexed):
    if events is None:
        return None, []
    projected, excluded, seen = [], [], set()
    for event in events:
        identity, target = event["message_id"], event["target_agent_id"]
        if identity not in indexed:
            raise ValueError("Extraction returned an unknown source message")
        key = identity, target
        if key in seen:
            raise ValueError("Extraction returned duplicate message/target events")
        seen.add(key)
        message = indexed[identity]
        if not message["agent_id"]:
            excluded.append(event["event_id"])
            continue
        if not target or target == message["agent_id"]:
            raise ValueError("Extraction returned an invalid or self target")
        if event["author_agent_id"] != message["agent_id"]:
            raise ValueError("Extraction author differs from source author")
        projected.append({
            "source": message["agent_id"], "target": target,
            "timestamp": message["timestamp"], "evidence_ids": [identity],
            "inferred": False, "measurement_event": copy.deepcopy(event),
        })
    return projected, excluded


def _delta_events(reference, variant):
    if variant is None:
        return {"available": False, "reason": "Unicode shadow was not requested."}
    baseline = {(row["evidence_ids"][0], row["target"]): row for row in reference}
    measured = {(row["evidence_ids"][0], row["target"]): row for row in variant}
    return {
        "available": True,
        "added": [copy.deepcopy(measured[key]["measurement_event"])
                  for key in sorted(set(measured) - set(baseline))],
        "removed": [copy.deepcopy(baseline[key]["measurement_event"])
                    for key in sorted(set(baseline) - set(measured))],
        "common_message_target_count": len(set(measured) & set(baseline)),
    }


def _graph(messages, node_ids, events, original_window, *, variant, excluded):
    if events is None:
        return {
            "available": False, "label": VARIANT_LABELS[variant],
            "reason": "Unicode-shadow extraction was not explicitly requested.",
            "node_universe": list(node_ids),
        }
    nodes = sorted(node_ids)
    if len(nodes) > 1000:
        raise ValueError("Diagnostic graph exceeds the existing 1000-agent bound")
    authors = {row["agent_id"] for row in messages if row["agent_id"]}
    edges = _aggregate(events)
    lookup = {(row["evidence_ids"][0], row["target"]): row["measurement_event"]
              for row in events}
    for edge in edges:
        edge["measurement_event_refs"] = [
            copy.deepcopy(lookup[(identity, edge["target"])])
            for identity in edge["evidence_ids"]
        ]
        edge["interpretation"] = "Diagnostic name-pattern candidates; address and delivery unverified."
    metrics = _metrics(nodes, edges, messages=messages)
    quick = metrics["graph"]
    total, n = quick["interaction_count"], len(nodes)
    hhi = quick["incoming_concentration_hhi"]
    concentration = (hhi - 1 / n) / (1 - 1 / n) if hhi is not None and n > 1 else None
    node_metrics = metrics["nodes"]
    incoming_max = max((row["in_strength"] for row in node_metrics), default=0)
    incoming_ties = sorted(row["id"] for row in node_metrics
                           if total and row["in_strength"] == incoming_max)
    incoming_focus = max(incoming_ties) if incoming_ties else None
    pairs = {(edge["source"], edge["target"]): edge["weight"] for edge in edges}
    reciprocal_numerator = sum(min(weight, pairs.get((target, source), 0))
                               for (source, target), weight in pairs.items())
    bridge = bridge_dependence({"nodes": [{"id": node} for node in nodes], "edges": edges})
    bridge_rows = bridge["nodes"]
    bridge_max = bridge["maximum_loss_fraction"]
    bridge_ties = sorted(row["agent_id"] for row in bridge_rows
                         if bridge_max is not None and row["loss_fraction"] == bridge_max)
    evidence = list(dict.fromkeys(identity for edge in edges for identity in edge["evidence_ids"]))
    features = {
        "incoming_concentration": {
            "value": concentration, "events": total, "evidence_ids": list(evidence),
            "focus_agent_id": incoming_focus, "tied_maximum_agent_ids": incoming_ties,
            "decomposition": {"total_mention_events": total, "node_count": n, "raw_hhi": hhi,
                              "incoming_strengths": {row["id"]: row["in_strength"] for row in node_metrics},
                              "normalization": "(HHI - 1/n) / (1 - 1/n)"},
        },
        "directed_reciprocity": {
            "value": quick["weighted_reciprocity"], "events": total, "evidence_ids": list(evidence),
            "decomposition": {"reciprocal_numerator": reciprocal_numerator,
                              "total_mention_events": total,
                              "both_directed_orientations_counted": True},
        },
        "bridge_dependence": {
            "value": bridge_max, "events": total, "evidence_ids": list(evidence),
            "focus_agent_id": bridge["focus_agent_id"], "tied_maximum_agent_ids": bridge_ties,
            "node_removal": bridge,
            "decomposition": {"operator_available": bridge.get("available", True),
                              "original_reachable_pairs": bridge["original_reachable_pairs"],
                              "node_removal_rows": copy.deepcopy(bridge_rows),
                              "denominator": "Reachable ordered pairs excluding the removed node's endpoints."},
        },
    }
    for name in _INVARIANT_FEATURES:
        features[name] = copy.deepcopy(original_window["features"][name])
    descriptor = {
        "available": True, "label": VARIANT_LABELS[variant], "diagnostic_only": True,
        "node_universe": nodes,
        "nodes": [{"id": node, "observed_author_in_window": node in authors} for node in nodes],
        "target_ids_without_authored_messages":
            sorted({event["target"] for event in events} - authors),
        "edges": edges, "metrics": metrics, "features": features,
        "counts": {"node_count": n, "projected_agent_event_count": len(events),
                   "excluded_human_source_event_count": len(excluded)},
        "excluded_human_source_event_ids": list(excluded),
        "authored_agent_message_count": original_window["authored_agent_message_count"],
        "agent_author_count": original_window["agent_author_count"],
        "invariant_measurements_policy":
            "Replayed original lexical/URL measurements reused on unchanged original text and ordering.",
    }
    return descriptor


def _direction(value):
    if value is None:
        return "undefined"
    if abs(value) <= EQUALITY_TOLERANCE:
        return "zero"
    return "positive" if value > 0 else "negative"


def _subtract(first, second):
    if first is None or second is None:
        return None
    return first - second


def _contrast(first, second, feature, config, baseline_delta):
    if not first["available"] or not second["available"]:
        return {
            "available": False, "reason": "One or both extraction variants are unavailable.",
            "value": None, "comparison_value": None, "difference": None,
            "change_from_baseline": None, "change_from_policy_baseline": None,
            "direction": "undefined", "supported": False,
            "support": {"candidate": False, "comparator": False},
        }
    left, right = first["features"][feature], second["features"][feature]
    value, other = left["value"], right["value"]
    difference = _subtract(value, other)
    support = {
        "candidate": _supported(first, feature, config["min_messages"], config["min_edge_events"]),
        "comparator": _supported(second, feature, config["min_messages"], config["min_edge_events"]),
    }
    eligible = all(support.values())
    return {
        "available": difference is not None, "value": value, "comparison_value": other,
        "difference": difference, "change_from_baseline": _subtract(difference, baseline_delta),
        "change_from_policy_baseline": _subtract(difference, baseline_delta),
        "direction": _direction(difference),
        "same_difference_direction_as_policy_baseline":
            difference * baseline_delta > 0 if difference is not None and baseline_delta is not None else None,
        "support": support, "supported": eligible, "supported_under_original_minima": eligible,
        "events": left["events"], "comparison_events": right["events"],
        "evidence_ids": copy.deepcopy(left["evidence_ids"]),
        "comparison_evidence_ids": copy.deepcopy(right["evidence_ids"]),
        "focus_agent_id": left.get("focus_agent_id"),
        "comparison_focus_agent_id": right.get("focus_agent_id"),
        "tied_maximum_agent_ids": copy.deepcopy(left.get("tied_maximum_agent_ids", [])),
        "comparison_tied_maximum_agent_ids": copy.deepcopy(right.get("tied_maximum_agent_ids", [])),
        "candidate_decomposition": copy.deepcopy(left.get("decomposition")),
        "comparator_decomposition": copy.deepcopy(right.get("decomposition")),
        "screening_threshold": FEATURES[feature]["minimum_delta"],
        "meets_frozen_descriptive_threshold":
            abs(difference) >= FEATURES[feature]["minimum_delta"] if difference is not None else None,
        "interpretation": "Frozen selected contrast; threshold status does not reselect a lead.",
    }


def audit_selected_lead_name_sensitivity(
    messages, agents, graph_search, *, selected_lead_ids,
    short_name_allowlist=None, include_unicode_shadow=False, source_refs=None,
):
    """Replay a pinned graph search and audit only its explicitly selected leads.

    source_refs are copied as declared host pins, never claimed externally
    authenticated. The host must bind them to its versioned source objects.
    A baseline replay mismatch raises ValueError without returning measurements.
    """
    if not isinstance(graph_search, dict):
        raise ValueError("Provide the original graph_search payload")
    _canonical(graph_search)
    _canonical(source_refs)
    if graph_search.get("analysis_version") != GRAPH_DISCOVERY_VERSION:
        raise ValueError("Unsupported graph-search instrument version")
    if not isinstance(selected_lead_ids, list) or not 1 <= len(selected_lead_ids) <= MAX_SELECTED_LEADS:
        raise ValueError("Request 1 to 12 explicitly selected lead IDs")
    if any(not isinstance(identity, str) for identity in selected_lead_ids):
        raise ValueError("Selected lead IDs must be strings")
    if len(set(selected_lead_ids)) != len(selected_lead_ids):
        raise ValueError("Duplicate selected lead IDs are not allowed")
    config = graph_search.get("configuration", {})
    if not isinstance(config, dict) or any(key not in config for key in _CONFIG_KEYS):
        raise ValueError("Missing original graph-search configuration")
    if _canonical(config.get("features")) != _canonical(FEATURES):
        raise ValueError("Unsupported feature definitions or thresholds")
    if type(config["seed"]) is not int:
        raise ValueError("Original seed must be an integer")
    if type(config["max_windows"]) is not int or not 1 <= config["max_windows"] <= MAX_REPLAY_WINDOWS:
        raise ValueError("Original replay is bounded to 120 windows")
    if type(config["max_leads"]) is not int or not 1 <= config["max_leads"] <= MAX_SELECTED_LEADS:
        raise ValueError("Original replay is bounded to 12 returned leads")
    original_leads = graph_search.get("leads")
    if not isinstance(original_leads, list):
        raise ValueError("Original graph search requires its selected lead list")
    if any(not isinstance(row, dict) or not isinstance(row.get("id"), str)
           or row.get("feature") not in FEATURES
           or not isinstance(row.get("window_id"), str)
           or not isinstance(row.get("comparison_window_id"), str) for row in original_leads):
        raise ValueError("Malformed original selected lead")
    known = {row["id"] for row in original_leads}
    if len(known) != len(original_leads):
        raise ValueError("Duplicate original selected lead IDs")
    if not set(selected_lead_ids) <= known:
        raise ValueError("Unknown or unselected lead ID")
    selected = [row for row in original_leads if row["id"] in set(selected_lead_ids)]
    wanted_windows = {row[key] for row in selected for key in ("window_id", "comparison_window_id")}
    if len(wanted_windows) > MAX_SELECTED_WINDOWS:
        raise ValueError("Selected-window count exceeds the 24-window bound")

    # This independent instrument validates bounded text, unique IDs, roster,
    # source contexts and requested names. It does not select graph leads.
    scope_audit = audit_name_eligibility_sensitivity(
        messages, agents, short_name_allowlist=short_name_allowlist,
        include_unicode_shadow=include_unicode_shadow,
    )
    # Re-executing the legacy source search is exclusively a replay guard:
    # variants below never call discover_graph_leads or change the selection.
    replay = discover_graph_leads(
        messages, agents, **{key: config[key] for key in _CONFIG_KEYS})
    mismatch = _first_difference(graph_search, replay)
    if mismatch:
        raise ValueError("baseline_replay_mismatch: " + mismatch)

    ordered = sorted((normalize_message(row) for row in messages),
                     key=lambda row: (row["timestamp"], row["id"]))
    raw_by_id = {normalize_message(row)["id"]: row for row in messages}
    windows = {row["id"]: row for row in replay["windows"]}
    cache, projected_cache, slices = {}, {}, {}
    negative_controls = {}
    for identity in sorted(wanted_windows):
        original = windows[identity]
        start, end = parse_time(original["start"]), parse_time(original["end_exclusive"])
        local = [row for row in ordered if row["room_id"] == original["room_id"]
                 and start <= parse_time(row["timestamp"]) < end]
        if [row["id"] for row in local] != original["evidence_ids"]:
            raise ValueError("baseline_replay_mismatch: window membership")
        audit = audit_name_eligibility_sensitivity(
            [raw_by_id[row["id"]] for row in local], agents,
            short_name_allowlist=short_name_allowlist,
            include_unicode_shadow=include_unicode_shadow,
        )
        indexed = {row["id"]: row for row in local}
        projected, exclusions, streams = {}, {}, _streams(audit)
        for variant, events in streams.items():
            projected[variant], exclusions[variant] = _project(events, indexed)
        # Other projections' target nodes are unchanged by a name-only audit.
        nonmention_nodes = {row["agent_id"] for row in local if row["agent_id"]}
        for channel, projection in original["projections"].items():
            if channel != "observed_mentions":
                nonmention_nodes.update(edge["target"] for edge in projection["edges"])
        graphs = {}
        for variant in VARIANT_LABELS:
            events = projected[variant]
            nodes = nonmention_nodes | {event["target"] for event in events or []}
            graphs[variant] = _graph(local, nodes, events, original, variant=variant,
                                     excluded=exclusions[variant])
        baseline = graphs["baseline_exact"]
        for name in FEATURES:
            for field in ("value", "events", "evidence_ids"):
                if _canonical(baseline["features"][name][field]) != _canonical(original["features"][name][field]):
                    raise ValueError(f"baseline_replay_mismatch: {identity}.{name}.{field}")
            if name in ("incoming_concentration", "bridge_dependence"):
                if baseline["features"][name]["focus_agent_id"] != original["features"][name]["focus_agent_id"]:
                    raise ValueError(f"baseline_replay_mismatch: {identity}.{name}.focus")
        negative_controls[identity] = {
            variant: {
                name: {"unchanged": _canonical(graph["features"][name]) ==
                                   _canonical(original["features"][name]),
                       "measurement_policy": "Original-text replay reused; no shadow text enters this instrument."}
                for name in _INVARIANT_FEATURES
            }
            for variant, graph in graphs.items() if graph["available"]
        }
        if not all(item["unchanged"] for row in negative_controls[identity].values()
                   for item in row.values()):
            raise ValueError("Negative-control invariant failed")
        cache[identity] = {
            "original_window": copy.deepcopy(original),
            "eligibility_audit": audit, "variants": graphs,
            "agent_event_deltas": {
                variant: _delta_events(projected["baseline_exact"], projected[variant])
                for variant in VARIANT_LABELS
            },
            "human_rows_preserved": sum(not row["agent_id"] for row in local),
            "native_universe_policy":
                "Window authors plus accepted agent-source targets; other projection targets retained.",
        }
        projected_cache[identity] = (projected, exclusions)
        slices[identity] = local

    pair_cache, per_lead = {}, []
    for lead in selected:
        candidate, comparator = lead["window_id"], lead["comparison_window_id"]
        pair_id = "pair-" + _digest([candidate, comparator])[:16]
        if pair_id not in pair_cache:
            authors = {row["agent_id"] for identity in (candidate, comparator)
                       for row in slices[identity] if row["agent_id"]}
            targets = {event["target"] for identity in (candidate, comparator)
                       for events in projected_cache[identity][0].values()
                       for event in events or []}
            nodes = sorted(authors | targets)
            fixed = {}
            for identity in (candidate, comparator):
                streams, exclusions = projected_cache[identity]
                fixed[identity] = {
                    variant: _graph(slices[identity], nodes, streams[variant], windows[identity],
                                    variant=variant, excluded=exclusions[variant])
                    for variant in VARIANT_LABELS
                }
            pair_cache[pair_id] = {
                "window_id": candidate, "comparison_window_id": comparator,
                "node_universe": {
                    "ids": nodes, "agent_author_ids": sorted(authors),
                    "accepted_agent_source_target_ids": sorted(targets),
                    "target_ids_without_authored_messages_in_either_window": sorted(targets - authors),
                    "policy": "Both-window authors plus accepted agent-source targets across requested variants.",
                    "human_policy": "Human rows retained; human-source targets do not enlarge this universe.",
                    "dashboard_equivalence": False,
                },
                "window_variants": fixed,
            }
        fixed = pair_cache[pair_id]["window_variants"]
        native = {}
        fixed_results = {}
        feature = lead["feature"]
        fixed_baseline_delta = _subtract(
            fixed[candidate]["baseline_exact"]["features"][feature]["value"],
            fixed[comparator]["baseline_exact"]["features"][feature]["value"])
        for variant in VARIANT_LABELS:
            native[variant] = _contrast(
                cache[candidate]["variants"][variant], cache[comparator]["variants"][variant],
                feature, config, lead["difference"])
            fixed_results[variant] = _contrast(
                fixed[candidate][variant], fixed[comparator][variant],
                feature, config, fixed_baseline_delta)
        per_lead.append({
            "lead_id": lead["id"], "feature": feature,
            "original_rank": next(index + 1 for index, row in enumerate(original_leads) if row["id"] == lead["id"]),
            "window_id": candidate, "comparison_window_id": comparator, "pair_id": pair_id,
            "registered": copy.deepcopy(lead),
            "native": native, "fixed_pair": fixed_results,
            "universe_only_change": {
                "difference": _subtract(fixed_baseline_delta, lead["difference"]),
                "candidate_value": _subtract(
                    fixed[candidate]["baseline_exact"]["features"][feature]["value"], lead["value"]),
                "comparator_value": _subtract(
                    fixed[comparator]["baseline_exact"]["features"][feature]["value"], lead["comparison_value"]),
            },
        })

    result = {
        "schema_version": "1.0", "analysis_version": SELECTED_LEAD_SENSITIVITY_VERSION,
        "kind": "selected_lead_name_sensitivity", "read_only": True, "model_calls": 0,
        "source_refs": copy.deepcopy(source_refs) if source_refs is not None else [],
        "source_binding": {
            "source_refs_external_authentication": False,
            "host_requirement": "Bind declared refs to exact versioned dataset/discovery objects before persistence.",
            "graph_search_payload_fingerprint": _digest(graph_search),
            "graph_search_source_fingerprint": replay["source_fingerprint"],
            "source_context_fingerprint": scope_audit["source_fingerprint"],
            "roster_fingerprint": scope_audit["roster_fingerprint"],
            "hash_policy": "Named fingerprints are compact finite-JSON SHA256 except legacy graph-search source fingerprint.",
        },
        "instrument_versions": {"graph_search": GRAPH_DISCOVERY_VERSION, "network": NETWORK_VERSION,
                                "name_eligibility": NAME_ELIGIBILITY_SENSITIVITY_VERSION},
        "code_hashes": _code_hashes(),
        "validation": {"full_legacy_source_replay": True, "window_membership_replayed": True,
                       "selected_features_replayed": True, "independent_extraction": True,
                       "human_rows_preserved": True, "negative_controls_unchanged": True},
        "scope": {
            "conditioning": "Original selected leads and original matched-window orientation.",
            "source_message_count": len(ordered),
            "selected_lead_count": len(selected), "selected_window_count": len(wanted_windows),
            "ordered_pair_count": len(pair_cache), "all_source_human_message_count":
                sum(not row["agent_id"] for row in ordered),
        },
        "bounds": {**scope_audit["bounds"], "max_selected_leads": MAX_SELECTED_LEADS,
                   "max_selected_windows": MAX_SELECTED_WINDOWS, "max_replay_windows": MAX_REPLAY_WINDOWS,
                   "bridge_node_limit": 128},
        "configuration": {
            "short_name_allowlist": copy.deepcopy(scope_audit["requested_names"]),
            "include_unicode_shadow": include_unicode_shadow,
            "equality_tolerance": EQUALITY_TOLERANCE,
            "original": copy.deepcopy(config),
        },
        "frozen_selection": {
            "lead_ids": [row["id"] for row in selected],
            "requested_lead_ids": list(selected_lead_ids),
            "original_order_selected_lead_ids": [row["id"] for row in selected],
            "original_selection": copy.deepcopy(replay["selection"]),
            "original_source_scope": copy.deepcopy(replay["scope"]),
            "selection_or_matching_changed": False,
            "variant_searches_performed": 0,
            "legacy_search_execution_purpose": "Fail-closed source replay only, not a variant discovery.",
        },
        "window_measurements": cache, "pair_diagnostics": pair_cache,
        "per_lead": per_lead, "negative_control_checks": negative_controls,
        "limitations": [
            "This is post-selection sensitivity on reused records, not independent replication or calibrated identification.",
            "Mention candidates do not establish address, delivery, reading, influence, psychological traits or causal effects.",
            "Variant support/threshold changes do not rematch, re-rank, relabel or reselect historical leads.",
            "Native and fixed-pair baselines have distinct node-universe denominators.",
            "Absent authors have unknown exposure; structural zero edges are not measured zero communication rates.",
            "Bridge deletion is static representation reachability, not intervention; undefined values remain None.",
            "Legacy exact collision semantics remain unchanged; ambiguous shadow/short targets are excluded as unknown.",
            "No eigenvectors, latent traits, automatic theory promotion or new window-width analysis is performed.",
            "Host source refs are declared pins; this pure module cannot authenticate a registry.",
        ],
    }
    _canonical(result)
    return result
