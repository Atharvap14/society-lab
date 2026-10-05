"""Bounded static versus strictly time-ordered mention reference paths.

Edges are agent-author -> named roster target on a retained source message.
Neither their direction nor a valid temporal path identifies delivery, reading,
information transfer, behavioral influence, or a historical causal network.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from collections import Counter, defaultdict, deque
from datetime import timedelta
from itertools import groupby
from pathlib import Path

from .dataset import iso_time, normalize_message, parse_time
from .graph_discovery import _reachable, bridge_dependence
from .mention_graph_sensitivity import VARIANT_LABELS
from .name_eligibility_sensitivity import (
    NAME_ELIGIBILITY_SENSITIVITY_VERSION, audit_name_eligibility_sensitivity,
)
from .network import _aggregate


TEMPORAL_NETWORK_VERSION = "strict-temporal-mentions-v1"
MAX_NODES = 128
MAX_EVENTS_PER_WINDOW_VARIANT = 10000
MAX_WINDOWS = 24
MAX_PATH_WORK = 10000000
MAX_WITNESS_STEPS = 200000
MAX_UNIQUE_WITNESSES = 20000
MAX_PAIR_RECORDS = 200000
MAX_OUTPUT_BYTES = 16000000
MAX_INPUT_BYTES = 16000000
MAX_SOURCE_BYTES = 4096
MAX_MESSAGE_BYTES = 256000
MAX_WINDOW_METADATA_BYTES = 128000
MAX_SCOPE_METADATA_BYTES = 1000000
MAX_SOURCE_REFS_BYTES = 64000
MAX_ROSTER_BYTES = 1000000
MAX_EXTRACTION_CELLS = 50000


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise ValueError("Temporal analysis accepts finite JSON source data") from exc


def _digest(value):
    digest = hashlib.sha256()
    for piece in _encoder().iterencode(value):
        digest.update(piece.encode("utf-8"))
    return digest.hexdigest()


def _encoder():
    return json.JSONEncoder(sort_keys=True, ensure_ascii=False,
                            separators=(",", ":"), allow_nan=False)


def _validate_json(value, *, context, max_items=4096, max_string=200000, max_depth=8):
    """Validate shape before encoding, copying or retaining arbitrary metadata."""
    count, ancestors = 0, set()

    def visit(item, depth):
        nonlocal count
        count += 1
        if count > max_items or depth > max_depth:
            raise ValueError(f"{context} structure bound exceeded")
        if item is None or type(item) is bool:
            return
        if type(item) is str:
            if len(item) > max_string:
                raise ValueError(f"{context} string bound exceeded")
            return
        if type(item) is int:
            if item.bit_length() > 256:
                raise ValueError(f"{context} integer bound exceeded")
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise ValueError(f"{context} requires finite JSON")
            return
        if type(item) not in (dict, list):
            raise ValueError(f"{context} requires finite JSON objects and arrays")
        identity = id(item)
        if identity in ancestors:
            raise ValueError(f"{context} cannot contain cyclic data")
        ancestors.add(identity)
        if type(item) is dict:
            for key, child in item.items():
                if type(key) is not str:
                    raise ValueError(f"{context} JSON object keys must be strings")
                visit(key, depth + 1)
                visit(child, depth + 1)
        else:
            for child in item:
                visit(child, depth + 1)
        ancestors.remove(identity)

    visit(value, 0)


def _json_size(value, *, limit, context):
    """Stream encoded chunks; never serialize a whole unbounded tree first."""
    size = 0
    try:
        for piece in _encoder().iterencode(value):
            size += len(piece.encode("utf-8"))
            if size > limit:
                raise ValueError(f"{context} serialized byte bound exceeded")
    except (TypeError, OverflowError) as exc:
        raise ValueError(f"{context} requires finite JSON") from exc
    return size


def _reserve_output(budget, value, context):
    size = _json_size(value, limit=MAX_OUTPUT_BYTES - budget["reserved_output_bytes"] - 64,
                      context=context)
    # Fragment reservations deliberately include duplicated wrapper punctuation;
    # a final streamed check also enforces the exact complete-object byte limit.
    budget["reserved_output_bytes"] += size + 64
    return value


def _new_budget():
    return {"witness_steps": 0, "unique_witnesses": 0, "pair_records": 0,
            "reserved_output_bytes": 0}


def _code_hashes():
    directory = Path(__file__).resolve().parent
    return {
        name: {"sha256": hashlib.sha256((directory / name).read_bytes()).hexdigest(),
               "purpose": "Binary implementation identity, not a raw-source or JSON-record hash."}
        for name in ("temporal_network.py", "dataset.py", "graph_discovery.py", "network.py",
                     "mention_sensitivity.py", "name_eligibility_sensitivity.py",
                     "mention_graph_sensitivity.py")
    }


def _normalize_sources(messages):
    if not isinstance(messages, list) or len(messages) > 10000:
        raise ValueError("Provide at most 10000 bounded source messages")
    seen, ordered, raw, total_bytes = set(), [], {}, 0
    for row in messages:
        _validate_json(row, context="Source message")
        row_bytes = _json_size(row, limit=MAX_MESSAGE_BYTES, context="Source message")
        total_bytes += row_bytes
        if total_bytes > MAX_INPUT_BYTES:
            raise ValueError("Aggregate source-message byte bound exceeded")
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
            raise ValueError("Temporal witnesses require original nonempty string message IDs")
        if len(row["id"]) > 256:
            raise ValueError("Source message identity bound exceeded")
        source = row.get("source") or {}
        if not isinstance(source, dict):
            raise ValueError("Source provenance must be a bounded JSON object")
        _validate_json(source, context="Source provenance", max_items=128, max_string=4096)
        _json_size(source, limit=MAX_SOURCE_BYTES, context="Source provenance")
        if row["id"] in seen:
            raise ValueError("Repeated source message IDs are not allowed")
        seen.add(row["id"])
        supplied = []
        for key in ("created_at", "timestamp"):
            if row.get(key) not in (None, ""):
                if type(row[key]) is not str or len(row[key]) > 64:
                    raise ValueError("Source timestamps require bounded ISO strings")
                try:
                    instant = parse_time(row[key])
                except (ValueError, TypeError, OverflowError) as exc:
                    raise ValueError("Malformed source timestamp") from exc
                if instant is None:
                    raise ValueError("Missing source timestamp")
                supplied.append(instant)
        if not supplied:
            raise ValueError("Missing source timestamp")
        if any(instant != supplied[0] for instant in supplied):
            raise ValueError("Conflicting created_at and timestamp values")
        record = normalize_message(row)
        if record["agent_id"] is not None and (
                not isinstance(record["agent_id"], str) or not record["agent_id"]):
            raise ValueError("Agent source identity must be a nonempty string")
        if any(len(record[key]) > 256 for key in ("room_id", "speaker_id")) or (
                record["agent_id"] and len(record["agent_id"]) > 256):
            raise ValueError("Source room or speaker identity bound exceeded")
        ordered.append(record)
        raw[record["id"]] = row
    ordered.sort(key=lambda row: (row["timestamp"], row["id"]))
    return ordered, raw


def _window_scopes(ordered, windows):
    if windows is None:
        rooms = defaultdict(list)
        for row in ordered:
            rooms[row["room_id"]].append(row)
        if len(rooms) > MAX_WINDOWS:
            raise ValueError("Retained room scopes exceed the 24-window bound")
        result = []
        for room, rows in sorted(rooms.items()):
            try:
                end = iso_time(parse_time(rows[-1]["timestamp"]) + timedelta(microseconds=1))
            except OverflowError as exc:
                raise ValueError("Retained-span end cannot be padded; supply an explicitly supported window") from exc
            result.append({
                "id": "room-scope-" + _digest([room, rows[0]["timestamp"], rows[-1]["timestamp"]])[:16],
                "room_id": room, "start": rows[0]["timestamp"], "end_exclusive": end,
                "selection": "Full retained span for this room; no completeness or time-at-risk claim.",
                "end_padding_microseconds": 1,
            })
        return result
    if not isinstance(windows, list) or not 1 <= len(windows) <= MAX_WINDOWS:
        raise ValueError("Provide 1 to 24 explicit windows")
    result, seen, total_bytes = [], set(), 0
    for window in windows:
        _validate_json(window, context="Window metadata", max_items=16000, max_string=4096)
        total_bytes += _json_size(window, limit=MAX_WINDOW_METADATA_BYTES, context="Window metadata")
        if total_bytes > MAX_SCOPE_METADATA_BYTES:
            raise ValueError("Aggregate window-metadata byte bound exceeded")
        if not isinstance(window, dict) or any(
            not isinstance(window.get(key), str) or not window[key]
            for key in ("id", "room_id", "start", "end_exclusive")
        ):
            raise ValueError("Windows require id, room_id, start and end_exclusive strings")
        if window["id"] in seen:
            raise ValueError("Duplicate window IDs")
        if len(window["id"]) > 256 or len(window["room_id"]) > 256:
            raise ValueError("Window identity bound exceeded")
        seen.add(window["id"])
        try:
            start, end = parse_time(window["start"]), parse_time(window["end_exclusive"])
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError("Malformed window timestamp") from exc
        if start is None or end is None or start >= end:
            raise ValueError("Window start must precede end_exclusive")
        result.append({
            "id": window["id"], "room_id": window["room_id"],
            "start": iso_time(start), "end_exclusive": iso_time(end),
            "selection": "Caller-selected half-open room window; no rescan, ranking or matching.",
            "supplied_metadata": copy.deepcopy(window),
        })
    return sorted(result, key=lambda window: window["id"])


def _streams(audit):
    shadow = audit["unicode_shadow"]
    return {
        "baseline_exact": audit["baseline_exact_events"],
        "explicit_short_expanded_exact": audit["baseline_exact_events"] + audit["short_name_exact_events"],
        "unicode_baseline": shadow["baseline_shadow_events"] if shadow["enabled"] else None,
        "unicode_expanded": shadow["baseline_shadow_events"] + shadow["short_name_shadow_events"]
        if shadow["enabled"] else None,
    }


def _preflight_extraction(messages, agents):
    """Cap even the helper's potential events before it constructs event lists."""
    if agents is not None and not isinstance(agents, (list, dict)):
        raise ValueError("Roster must be a bounded list or dictionary")
    roster = agents.values() if isinstance(agents, dict) else agents or []
    identities = {str(agent["id"]) for agent in roster if isinstance(agent, dict) and agent.get("id")}
    for row in messages:
        message = normalize_message(row)
        if message["agent_id"]:
            identities.add(message["agent_id"])
    if len(messages) * len(identities) > MAX_EXTRACTION_CELLS:
        raise ValueError("Potential name-extraction event bound exceeded before extraction")


def _project(events, indexed, nonagents, evidence, budget):
    if events is None:
        return None, []
    projected, excluded, seen = [], [], set()
    for event in events:
        identity, target = event["message_id"], event["target_agent_id"]
        if identity not in indexed:
            raise ValueError("Name instrument returned an unknown source ID")
        if (identity, target) in seen:
            raise ValueError("Duplicate message/target extraction events")
        seen.add((identity, target))
        message = indexed[identity]
        reason = "human_source" if not message["agent_id"] else (
            "known_nonagent_target" if target in nonagents else None)
        if reason:
            excluded.append(_reserve_output(budget, {
                "event_id": event["event_id"], "message_id": identity,
                "target_id": target, "reason": reason}, "Excluded event output"))
            continue
        if not isinstance(target, str) or not target or target == message["agent_id"]:
            raise ValueError("Invalid or self reference target")
        if event["author_agent_id"] != message["agent_id"]:
            raise ValueError("Extraction/source author mismatch")
        binding = evidence[identity]
        value = {
            "event_id": event["event_id"], "message_id": identity,
            "source_agent_id": message["agent_id"], "target_agent_id": target,
            "timestamp": message["timestamp"], "room_id": message["room_id"],
            "source": message["source"],
            "normalized_record_hash": message["content_hash"],
            "original_text_sha256": binding["original_content_sha256"],
            "instrument": event["instrument"], "measurement_status": event["status"],
            "span": event["span"],
            "original_span_available": event["original_span_available"],
            "match_text": event["match_text"],
        }
        _reserve_output(budget, value, "Prepared event output")
        projected.append(copy.deepcopy(value))
    projected.sort(key=lambda event: (
        event["timestamp"], event["message_id"], event["source_agent_id"], event["target_agent_id"]))
    return projected, excluded


def _static_paths(nodes, events):
    representatives = {}
    for index, event in enumerate(events):
        representatives.setdefault((event["source_agent_id"], event["target_agent_id"]), index)
    adjacency = defaultdict(list)
    for (source, target), index in sorted(representatives.items()):
        adjacency[source].append((target, index))
    paths = {}
    for source in nodes:
        reached, pending = {source: ()}, deque([source])
        while pending:
            current = pending.popleft()
            for target, index in adjacency[current]:
                if target not in reached:
                    reached[target] = reached[current] + (index,)
                    pending.append(target)
        paths.update(((source, target), path) for target, path in reached.items() if target != source)
    return paths


def _temporal_paths(nodes, events, removed=None):
    groups = [(stamp, list(group)) for stamp, group in
              groupby(enumerate(events), key=lambda item: item[1]["timestamp"])]
    paths = {}
    for source in nodes:
        if source == removed:
            continue
        reached = {source: ()}
        for stamp, group in groups:
            # All paths in reached ended strictly before this timestamp batch.
            # Ties choose witnesses, never supply an order for chaining edges.
            additions = {}
            for index, event in group:
                origin, target = event["source_agent_id"], event["target_agent_id"]
                if origin == removed or target == removed or origin not in reached or target in reached:
                    continue
                path = reached[origin] + (index,)
                if target not in additions or path < additions[target]:
                    additions[target] = path
            reached.update(additions)
        paths.update(((source, target), path) for target, path in reached.items() if target != source)
    return paths


def _witness(pair, path, events, operator, window_id, variant, budget):
    if budget["unique_witnesses"] + 1 > MAX_UNIQUE_WITNESSES:
        raise ValueError("Aggregate unique-witness bound exceeded; no witness sampling")
    if budget["witness_steps"] + len(path) > MAX_WITNESS_STEPS:
        raise ValueError("Aggregate witness-step bound exceeded; no witness sampling")
    # References only until shape, path invariants and output reservation pass.
    # A rejected witness has not copied its potentially repeated source metadata.
    steps = [events[index] for index in path]
    if not steps or steps[0]["source_agent_id"] != pair[0] or steps[-1]["target_agent_id"] != pair[1]:
        raise ValueError("Invalid path witness endpoints")
    if any(first["target_agent_id"] != second["source_agent_id"]
           for first, second in zip(steps, steps[1:])):
        raise ValueError("Invalid path witness continuity")
    ordered = all(first["timestamp"] < second["timestamp"] for first, second in zip(steps, steps[1:]))
    if operator == "strict_temporal" and not ordered:
        raise ValueError("Temporal witness fails strict timestamp order")
    if len({step["room_id"] for step in steps}) != 1:
        raise ValueError("Witness crosses rooms")
    identity = "reference-path-" + _digest([window_id, variant, operator, pair])[:20]
    witness = {
        "operator": operator, "source_agent_id": pair[0], "target_agent_id": pair[1],
        "message_ids": [step["message_id"] for step in steps],
        "strict_timestamp_order": ordered, "steps": steps,
        "interpretation": "Reference-pattern path witness, not delivery or causal influence.",
    }
    _reserve_output(budget, {identity: witness}, "Path witness output")
    budget["unique_witnesses"] += 1
    budget["witness_steps"] += len(path)
    return identity, copy.deepcopy(witness)


def _pair_rows(pairs, refs, budget):
    if budget["pair_records"] + len(pairs) > MAX_PAIR_RECORDS:
        raise ValueError("Aggregate pair-record bound exceeded; no pair sampling")
    rows = []
    for first, second in sorted(pairs):
        row = {"source_agent_id": first, "target_agent_id": second,
               "witness_ref": refs[(first, second)]}
        rows.append(_reserve_output(budget, row, "Reachable pair output"))
    budget["pair_records"] += len(pairs)
    return rows


def _removal(nodes, original, remaining, refs, budget):
    rows = []
    for node in nodes:
        eligible = {pair for pair in original if node not in pair}
        lost = eligible - remaining(node)
        row = {
            "agent_id": node, "eligible_reachable_pairs": len(eligible),
            "lost_pairs": len(lost), "loss_fraction": len(lost) / len(eligible) if eligible else None,
        }
        _reserve_output(budget, row, "Node-removal summary")
        row["lost_pair_witness_refs"] = _pair_rows(lost, refs, budget)
        rows.append(row)
    valid = [row for row in rows if row["loss_fraction"] is not None]
    focus = max(valid, key=lambda row: (row["loss_fraction"], row["lost_pairs"], row["agent_id"])) if valid else None
    result = {
        "maximum_loss_fraction": focus["loss_fraction"] if focus else None,
        "focus_agent_id": focus["agent_id"] if focus and focus["loss_fraction"] > 0 else None,
        "endpoint_policy": "Pairs with removed node as either endpoint are excluded.",
        "interpretation": "Deletion from a reference representation; no agent intervention performed.",
    }
    _reserve_output(budget, result, "Node-removal wrapper")
    result["rows"] = rows
    return result


def _measure(nodes, events, window_id, variant, budget):
    static_paths = _static_paths(nodes, events)
    temporal_paths = _temporal_paths(nodes, events)
    if not set(temporal_paths) <= set(static_paths):
        raise ValueError("Temporal reachability is not a subset of static reachability")
    edge_events = [{
        "source": event["source_agent_id"], "target": event["target_agent_id"],
        "timestamp": event["timestamp"], "evidence_ids": [event["message_id"]],
    } for event in events]
    edges = _aggregate(edge_events)
    _reserve_output(budget, edges, "Aggregated edge output")
    if set(static_paths) != _reachable(nodes, edges):
        raise ValueError("Static path witness coverage differs from existing reachability")
    witnesses, refs = {}, {}
    for operator, paths in (("static", static_paths), ("strict_temporal", temporal_paths)):
        lookup = {}
        for pair, path in sorted(paths.items()):
            identity, witness = _witness(pair, path, events, operator, window_id, variant, budget)
            lookup[pair] = identity
            witnesses[identity] = witness
        refs[operator] = lookup
    static_loss = _removal(
        nodes, set(static_paths), lambda node: _reachable(nodes, edges, removed=node), refs["static"], budget)
    legacy_loss = bridge_dependence({"nodes": [{"id": node} for node in nodes], "edges": edges})
    if static_loss["maximum_loss_fraction"] != legacy_loss["maximum_loss_fraction"]:
        raise ValueError("Static removal definition differs from existing bridge instrument")
    temporal_loss = _removal(
        nodes, set(temporal_paths), lambda node: set(_temporal_paths(nodes, events, removed=node)),
        refs["strict_temporal"], budget)
    static_only = set(static_paths) - set(temporal_paths)
    result = {
        "available": True, "diagnostic_only": True, "node_ids": list(nodes),
        "static": {"reachable_pair_count": len(static_paths),
                   "reachable_pairs": _pair_rows(static_paths, refs["static"], budget),
                   "node_removal": static_loss},
        "strict_temporal": {"reachable_pair_count": len(temporal_paths),
                            "reachable_pairs": _pair_rows(temporal_paths, refs["strict_temporal"], budget),
                            "node_removal": temporal_loss},
        "static_only_pairs": _pair_rows(static_only, refs["static"], budget),
        "static_only_pair_count": len(static_only),
        "temporal_fraction_of_static_pairs": len(temporal_paths) / len(static_paths) if static_paths else None,
        "witnesses": witnesses,
        "witness_selection":
            "Static BFS uses the earliest event per tie; temporal paths retain earliest arrival with deterministic tie choice. Not every path is enumerated.",
    }
    _reserve_output(budget, {
        key: value for key, value in result.items()
        if key not in ("static", "strict_temporal", "static_only_pairs", "witnesses")
    }, "Variant summary")
    result["events"], result["directed_edges"] = events, edges
    return result


def analyze_temporal_mentions(
    messages, agents=None, *, windows=None, short_name_allowlist=None,
    include_unicode_shadow=False, source_refs=None,
):
    """Measure room-local reference paths in bounded, explicitly scoped records."""
    ordered, raw = _normalize_sources(messages)
    _validate_json(source_refs, context="Source references", max_string=4096)
    _json_size(source_refs, limit=MAX_SOURCE_REFS_BYTES, context="Source references")
    _validate_json(agents, context="Roster metadata", max_items=64000, max_string=4096)
    _json_size(agents, limit=MAX_ROSTER_BYTES, context="Roster metadata")
    _preflight_extraction(messages, agents)
    scopes = _window_scopes(ordered, windows)
    scope_audit = audit_name_eligibility_sensitivity(
        messages, agents, short_name_allowlist=short_name_allowlist,
        include_unicode_shadow=include_unicode_shadow)
    # The helper verifies raw and normalized text, including shadow coordinates.
    # Retain only source binding/configuration; no duplicate transcript in output.
    scope_audit = {key: scope_audit[key] for key in (
        "source_fingerprint", "roster_fingerprint", "requested_names")}
    authors = {row["agent_id"] for row in ordered if row["agent_id"]}
    humans = {row["speaker_id"] for row in ordered if not row["agent_id"]}
    roster = agents.values() if isinstance(agents, dict) else agents or []
    declared_nonagents = {str(agent["id"]) for agent in roster if agent.get("id") and
                          (agent.get("speaker_type") not in (None, "agent") or
                           agent.get("kind") in ("human", "user"))}
    if authors & (humans | declared_nonagents):
        raise ValueError("Conflicting agent and nonagent identity declarations")
    nonagents = humans | declared_nonagents
    prepared, total_work, budget = [], 0, _new_budget()
    for window in scopes:
        local = [row for row in ordered if row["room_id"] == window["room_id"]
                 and window["start"] <= row["timestamp"] < window["end_exclusive"]]
        supplied = window.get("supplied_metadata", {})
        membership = [row["id"] for row in local]
        if "evidence_ids" in supplied and _canonical(supplied["evidence_ids"]) != _canonical(membership):
            raise ValueError("Supplied window evidence membership mismatch")
        legacy_fingerprint = hashlib.sha256(
            "|".join(row["id"] + ":" + row["content_hash"] for row in local).encode("utf-8")).hexdigest()
        if "source_fingerprint" in supplied and supplied["source_fingerprint"] != legacy_fingerprint:
            raise ValueError("Supplied window source fingerprint mismatch")
        audit = audit_name_eligibility_sensitivity(
            [raw[row["id"]] for row in local], agents,
            short_name_allowlist=short_name_allowlist,
            include_unicode_shadow=include_unicode_shadow)
        projected, exclusions = {}, {}
        indexed = {row["id"]: row for row in local}
        for variant, events in _streams(audit).items():
            projected[variant], exclusions[variant] = _project(
                events, indexed, nonagents, audit["evidence_index"], budget)
        audit = {
            key: audit[key] for key in ("source_fingerprint", "roster_fingerprint",
                                      "allowlist_resolution", "original_roster_collisions")
        } | {
            "unicode_shadow": {
                "enabled": include_unicode_shadow,
                "normalized_roster_collisions": audit["unicode_shadow"].get(
                    "normalized_roster_collisions", []),
            },
            "evidence_index": {
                identity: {key: value for key, value in record.items()
                           if key not in ("content", "shadow_text")}
                for identity, record in audit["evidence_index"].items()
            },
        }
        _reserve_output(budget, audit, "Scoped extraction provenance")
        local_authors = {row["agent_id"] for row in local if row["agent_id"]}
        targets = {event["target_agent_id"] for events in projected.values() for event in events or []}
        nodes = sorted(local_authors | targets)
        if len(nodes) > MAX_NODES:
            raise ValueError("Temporal node-removal analysis is bounded to 128 nodes")
        for events in projected.values():
            if events is None:
                continue
            if len(events) > MAX_EVENTS_PER_WINDOW_VARIANT:
                raise ValueError("Temporal analysis is bounded to 10000 events per window/variant")
            # Includes temporal all-source scans after every removal and the
            # existing static bridge plus static loss/witness checks. This is a
            # conservative work guard, not an elapsed-time prediction.
            total_work += 4 * len(nodes) * (len(nodes) + 1) * (len(events) + len(nodes))
        prepared.append((window, local, audit, projected, exclusions, nodes, targets, legacy_fingerprint))
    if total_work > MAX_PATH_WORK:
        raise ValueError("Aggregate all-variant/removal path-work budget exceeded; no sampling")

    measured = {}
    for window, local, audit, projected, exclusions, nodes, targets, legacy_fingerprint in prepared:
        variants = {}
        for variant, events in projected.items():
            if events is not None:
                result = _measure(nodes, events, window["id"], variant, budget)
            else:
                result = {"available": False, "reason": "Unicode shadow was not requested.",
                          "node_ids": list(nodes)}
                _reserve_output(budget, result, "Unavailable variant")
            additions = {
                "label": VARIANT_LABELS[variant],
                "event_count": len(events) if events is not None else None,
                "instrument_status_counts": dict(sorted(Counter(
                    event["measurement_status"] for event in events or []).items())),
            }
            _reserve_output(budget, additions, "Variant labels")
            result.update(additions)
            result["excluded_events"] = exclusions[variant]
            variants[variant] = result
        local_authors = {row["agent_id"] for row in local if row["agent_id"]}
        metadata = {
            "scope": window, "message_ids": [row["id"] for row in local],
            "message_count": len(local), "agent_authored_message_count": sum(bool(row["agent_id"]) for row in local),
            "human_message_count": sum(not row["agent_id"] for row in local),
            "coverage_status": "Retained source scope; empty/missing periods are not observed behavioral zeros.",
            "source_fingerprint": audit["source_fingerprint"],
            "legacy_network_source_fingerprint": legacy_fingerprint,
            "roster_fingerprint": audit["roster_fingerprint"],
            "node_universe": {
                "ids": nodes, "agent_author_ids": sorted(local_authors),
                "accepted_agent_source_target_ids": sorted(targets),
                "targets_without_authored_messages": sorted(targets - local_authors),
                "policy": "Fixed within this window across requested variants; authors plus accepted agent-target references.",
                "equivalence": "Not necessarily legacy-native or selected-audit pair-common universe.",
            },
        }
        _reserve_output(budget, {window["id"]: metadata}, "Window summary")
        metadata["extraction_review"], metadata["variants"] = audit, variants
        measured[window["id"]] = metadata
    result = {
        "schema_version": "1.0", "analysis_version": TEMPORAL_NETWORK_VERSION,
        "kind": "temporal_reference_paths", "read_only": True, "model_calls": 0,
        "source_refs": copy.deepcopy(source_refs) if source_refs is not None else [],
        "source_binding": {
            "declared_refs_external_authentication": False,
            "raw_rows_fingerprint": _digest([raw[row["id"]] for row in ordered]),
            "source_context_fingerprint": scope_audit["source_fingerprint"],
            "roster_fingerprint": scope_audit["roster_fingerprint"],
            "hash_policy": "Compact finite UTF-8 JSON hashes except explicitly named legacy network fingerprint.",
        },
        "code_hashes": _code_hashes(), "name_instrument_version": NAME_ELIGIBILITY_SENSITIVITY_VERSION,
        "configuration": {"short_name_allowlist": copy.deepcopy(scope_audit["requested_names"]),
                          "include_unicode_shadow": include_unicode_shadow},
        "scope": {"source_message_count": len(ordered), "window_count": len(measured),
                  "window_selection": "Explicit scopes or per-room retained spans; no discovery rescan or ranking.",
                  "known_nonagent_ids": sorted(nonagents)},
        "bounds": {"max_nodes_per_window": MAX_NODES, "max_events_per_window_variant": MAX_EVENTS_PER_WINDOW_VARIANT,
                   "max_windows": MAX_WINDOWS, "max_path_work": MAX_PATH_WORK,
                   "estimated_path_work": total_work, "path_work_formula":
                       "Sum over available window/variants: 4*n*(n+1)*(events+n), includes all removals.",
                   "max_witness_steps": MAX_WITNESS_STEPS, "max_pair_records": MAX_PAIR_RECORDS,
                   "max_unique_witnesses": MAX_UNIQUE_WITNESSES, "max_output_bytes": MAX_OUTPUT_BYTES,
                   "max_source_message_bytes": MAX_MESSAGE_BYTES, "max_source_provenance_bytes": MAX_SOURCE_BYTES,
                   "max_aggregate_source_message_bytes": MAX_INPUT_BYTES,
                   "max_source_refs_bytes": MAX_SOURCE_REFS_BYTES, "max_roster_bytes": MAX_ROSTER_BYTES,
                   "max_window_metadata_bytes": MAX_WINDOW_METADATA_BYTES,
                   "max_aggregate_window_metadata_bytes": MAX_SCOPE_METADATA_BYTES,
                   "max_potential_name_extraction_cells": MAX_EXTRACTION_CELLS,
                   "emitted_witness_steps": budget["witness_steps"],
                   "emitted_unique_witnesses": budget["unique_witnesses"],
                   "emitted_pair_records": budget["pair_records"],
                   "output_policy": "Pre-copy/pre-append serialized fragment reservations plus 64 bytes per fragment; final exact streamed byte check. No truncation.",
                   "raw_metadata_policy": "Finite JSON; maximum nesting 8, message 4096 items, provenance 128 items, bounded strings and identities.",
                   "evidence_text_policy": "Original/shadow text is hashed but not duplicated in the output evidence index."},
        "definitions": {
            "direction": "Source message's agent author -> matched roster target, not direction of prior influence.",
            "static_pair": "Distinct ordered agent pair reachable ignoring event timestamps in the same scoped room.",
            "temporal_pair": "Distinct ordered agent pair with an author-to-target path of strictly increasing UTC timestamps.",
            "ties": "Single-edge paths valid; simultaneous events cannot be chained. IDs choose witnesses only.",
            "node_removal": "Recompute all alternate paths after deleting the node; exclude its endpoint pairs from loss denominator.",
            "path_horizon": "No maximum inter-event gap within the declared window; no assumed processing latency.",
        },
        "limitations": [
            "A time-respecting reference path is not message delivery, reading, semantic adoption or causal influence.",
            "The author-to-reference direction may differ from historical information flow.",
            "Static removal and temporal removal are representation deletions, not interventions on agents.",
            "Retained timestamps, coactivity and missing authors do not establish exposure, membership or time at risk.",
            "Exact names exclude short names; expanded/shadow matches remain candidates and ambiguous targets remain unknown.",
            "Human-source events and known nonagent targets are excluded and disclosed; human context can still affect agent activity.",
            "Windows are not rematched and counts are not automatically replay of historical graph contrasts under different node policies.",
            "Witnesses are representative valid paths, not all paths, transcripts, acknowledgments or proof of artifact transfer.",
            "No causal estimate, null p-value, theory promotion, pooled cross-room path or discovery re-ranking is produced.",
        ],
    }
    _reserve_output(budget, result, "Analysis metadata")
    result["bounds"]["reserved_output_bytes"] = budget["reserved_output_bytes"]
    result["windows"] = measured
    # Chunked exact serialized size; all large subtrees were reserved beforehand.
    result["bounds"]["serialized_output_bytes"] = 0
    for _ in range(3):
        size = _json_size(result, limit=MAX_OUTPUT_BYTES, context="Complete analysis output")
        if result["bounds"]["serialized_output_bytes"] == size:
            break
        result["bounds"]["serialized_output_bytes"] = size
    return result
