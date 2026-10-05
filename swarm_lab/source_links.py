"""Bounded explicit-export foreign keys, with scoped uncertainty and no reads.

Consumes scanner packets, never transcripts as instructions.  Content and raw
provider messages are only hashed; no provider reasoning is returned.  Verified
labels refer to a checked exported identity, never receipt or causal influence.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import PurePosixPath, PureWindowsPath

TABLES = ("events", "chat_messages", "computer_use_sessions", "computer_use_turns")
INSTRUMENT = "bounded-jsonl-source-scanner-v1"
SCANNER_SCHEMA_VERSION = "1.0"
SCAN_STOP_REASONS = ("not_started", "eof", "row_limit", "selected_ids_found", "compressed_byte_limit",
    "expanded_byte_limit", "row_byte_limit", "retained_byte_limit", "retained_structure_limit",
    "invalid_gzip_header", "invalid_utf8", "duplicate_json_key", "nonfinite_json", "invalid_record_structure",
    "malformed_json", "duplicate_record_id", "corrupt_gzip", "truncated_gzip", "io_error", "unverified_eof", "unverified_decoder_eof")
MAX_ROWS = 15_000
MAX_INPUT_BYTES = 32 * 1024 * 1024
MAX_OUTPUT_BYTES = 32 * 1024 * 1024
MAX_DEPTH = 32
MAX_NODES = 1_000_000
MAX_ID_BYTES = 36
MAX_TEXT_BYTES = 1024 * 1024
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
ACTION_TYPES = (
    "AGENT_TALK", "USER_TALK", "START_USING_COMPUTER", "STOP_USING_COMPUTER",
    "CONSOLIDATE", "WAIT", "PAUSE", "SEARCH_HISTORY", "ENTER_ROOM",
    "REQUEST_HUMAN_HELPER", "CANCEL_REQUEST_FOR_HUMAN_HELPER", "STOP_HUMAN_USE_SESSION",
    "REQUEST_GOOGLE_SIGN_IN", "RESTARTING_AFTER_GOOGLE_SIGN_IN",
    "OUTREACH_APPROVAL_REQUEST", "OUTREACH_APPROVAL_RESPONSE", "USER_NAME_CHANGE",
)
RULES = {
    "version": "source-links-v1", "tables": list(TABLES), "action_types": list(ACTION_TYPES),
    "scanner_schema_version":SCANNER_SCHEMA_VERSION, "scanner_stop_reasons":list(SCAN_STOP_REASONS),
    "hashes": {"canonical":"SHA256 of compact sorted-key finite JSON encoded UTF-8; string value hashes include JSON quoting",
        "raw_line":"Declared scanner SHA256 of original physical line bytes including any terminator; not independently recomputed here"},
    "aliases": {}, "identifiers": "exact UUID strings; no normalized or inferred aliases",
    "relations": {
        "event_message_fk": {"action": "AGENT_TALK", "fk": "data.messageId", "parent": "chat_messages.id",
            "optional_agreement": "data.chatMessageId", "checks": ["speakerId/agent_speaker_id", "roomId/room_id", "content/content"]},
        "start_session_fk": {"action": "START_USING_COMPUTER", "fk": "data.computerUseSessionId", "parent": "computer_use_sessions.id",
            "checks": ["agentId/agent_id", "sessionGoal/session_goal"]},
        "stop_session_fk": {"action": "STOP_USING_COMPUTER", "fk": "data.computerUseSessionId", "parent": "computer_use_sessions.id",
            "checks": ["agentId/agent_id"], "summary_is_not_session_goal": True},
        "turn_session_fk": {"fk": "session_id", "parent": "computer_use_sessions.id",
            "optional_checks": ["agent_id/agent_id"]},
    },
    "bounds": {"rows": MAX_ROWS, "input_bytes": MAX_INPUT_BYTES, "output_bytes": MAX_OUTPUT_BYTES,
        "depth": MAX_DEPTH, "nodes": MAX_NODES, "text_bytes": MAX_TEXT_BYTES},
}
LIMITATIONS = [
    "Explicit exported foreign keys and matching fields identify logged lineage; none measure recipient exposure, consumption or causal influence.",
    "All endpoint uniqueness checks are within supplied scanned rows. File EOF does not authenticate global database uniqueness or source logging completeness.",
    "Missing parents are unresolved in scanned scope. Prefixes, filters, bounded early stops and sequential live exports can leave legitimate links unresolved.",
    "Packet/record canonical hashes are recomputed. Raw-line hashes, absolute paths and source metadata are retained declarations, not independent file-byte or whole-object attestations.",
    "Matching actor, room, content, goal or temporal proximity can share a common cause; they do not identify a communication mechanism.",
    "WAIT/PAUSE counts describe recorded platform actions, not every concurrent activity, inactivity duration or a global resource lock.",
    "Tool requests, outputs and errors are separately recorded; a null error or output text does not establish successful execution or artifact state.",
    "No nearest-time session assignment, provider-input reconstruction, agent-memory read, mention-graph merge or behavior promotion is performed.",
    "A scanner duplicate-ID diagnostic can omit the offending row; unique retained matches then remain compatible with unresolved parent-scan ambiguity.",
]


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _hash(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _bounded_copy(value):
    """Iterative preflight before JSON recursion, including raw provider payloads."""
    stack = [(value, 0)]; nodes = 0; string_bytes = 0
    while stack:
        node, depth = stack.pop(); nodes += 1
        if depth > MAX_DEPTH or nodes > MAX_NODES:
            raise ValueError("Source packets exceed nesting or node bounds")
        if node is None or type(node) is bool:
            continue
        if type(node) is int:
            if abs(node) > 2**63 - 1: raise ValueError("Source integers exceed signed 64-bit bounds")
        elif type(node) is float:
            if not math.isfinite(node): raise ValueError("Source packets require finite JSON")
        elif type(node) is str:
            try: size = len(node.encode("utf-8"))
            except UnicodeEncodeError as exc: raise ValueError("Source strings require valid UTF-8") from exc
            string_bytes += size
            if size > MAX_TEXT_BYTES or string_bytes > MAX_INPUT_BYTES:
                raise ValueError("Source strings exceed input bounds")
        elif type(node) is list:
            stack.extend((item, depth + 1) for item in node)
        elif type(node) is dict:
            if not all(type(key) is str for key in node): raise ValueError("JSON keys must be strings")
            stack.extend((item, depth + 1) for pair in node.items() for item in pair)
        else:
            raise ValueError("Source packets require JSON values only")
    try: encoded = _canonical(value)
    except (ValueError, TypeError, RecursionError, OverflowError) as exc: raise ValueError("Invalid bounded source JSON") from exc
    if len(encoded) > MAX_INPUT_BYTES: raise ValueError("Source packets exceed canonical byte cap")
    return json.loads(encoded), len(encoded)


def _absolute(path):
    return type(path) is str and 0 < len(path.encode("utf-8")) <= 4096 and (
        PurePosixPath(path).is_absolute() or PureWindowsPath(path).is_absolute())


def _field(record, name, kind):
    if name not in record: return {"presence": "absent", "type_status": "unknown"}
    value = record[name]
    if value is None: return {"presence": "null", "type_status": "unknown"}
    valid = (type(value) is str and _UUID.fullmatch(value) is not None if kind == "id" else
        type(value) is str if kind == "text" else type(value) is int and 0 <= value <= 2**63 - 1 if kind == "index" else
        type(value) in (int, float) and 0 <= value <= 2**31 - 1 if kind == "seconds" else
        type(value) is str and value in ACTION_TYPES if kind == "action" else
        type(value) is dict if kind == "object" else type(value) is str and value in ("agent", "user") if kind == "speaker" else False)
    result = {"presence": "value", "type_status": "valid" if valid else "invalid"}
    if valid:
        if kind in ("id", "index", "seconds", "action", "speaker"): result["value"] = value
        else: result["value_hash"] = _hash(value)
    return result


def _compare(left, left_name, right, right_name, kind):
    a, b = _field(left, left_name, kind), _field(right, right_name, kind)
    if "invalid" in (a["type_status"], b["type_status"]): status = "invalid_field"
    elif "unknown" in (a["type_status"], b["type_status"]): status = "unknown"
    else: status = "matching" if _hash(left[left_name]) == _hash(right[right_name]) else "conflicting"
    return {"child_field": left_name, "parent_field": right_name, "status": status, "child": a, "parent": b}


def _timestamp(record):
    field = _field(record, "created_at", "text")
    result = {"presence": field["presence"], "type_status": field["type_status"]}
    if field["type_status"] != "valid": return result, None
    try:
        stamp = datetime.fromisoformat(record["created_at"].replace("Z", "+00:00"))
        if stamp.tzinfo is None: stamp = stamp.replace(tzinfo=timezone.utc)
        stamp = stamp.astimezone(timezone.utc)
    except (ValueError, OverflowError): return {**result, "type_status": "invalid"}, None
    return {**result, "utc": stamp.isoformat(timespec="microseconds")}, stamp


def _validate_packets(packets):
    packets, canonical_bytes = _bounded_copy(packets)
    if type(packets) is not dict or not packets or not set(packets) <= set(TABLES):
        raise ValueError("Use exact supported table namespaces")
    total = 0; rows = {}; scans = {}; packet_pins = {}
    for table, packet in packets.items():
        if (type(packet) is not dict or packet.get("kind") != "bounded_jsonl_source_scan"
                or packet.get("instrument_version") != INSTRUMENT or packet.get("table") != table
                or packet.get("schema_version") != SCANNER_SCHEMA_VERSION
                or not _absolute(packet.get("source_path")) or type(packet.get("records")) is not list):
            raise ValueError("Malformed or unsupported scanner packet")
        coverage = packet.get("coverage")
        if (type(coverage) is not dict or type(coverage.get("complete_scan")) is not bool
                or type(coverage.get("stop_reason")) is not str or coverage["stop_reason"] not in SCAN_STOP_REASONS):
            raise ValueError("Scanner coverage requires typed completeness and stop reason")
        counters = ("physical_rows_seen", "parsed_rows", "retained_rows", "filtered_rows", "malformed_rows", "duplicate_ids")
        if any(type(coverage.get(k)) is not int or not 0 <= coverage[k] <= 2**63 - 1 for k in counters):
            raise ValueError("Scanner counters require bounded integers")
        if (coverage["retained_rows"] != len(packet["records"]) or coverage["physical_rows_seen"] < coverage["parsed_rows"] + coverage["malformed_rows"]
                or coverage["parsed_rows"] < coverage["retained_rows"] + coverage["filtered_rows"]):
            raise ValueError("Scanner counters contradict retained rows")
        if coverage["complete_scan"] and (coverage["stop_reason"] != "eof" or coverage["malformed_rows"] or coverage["duplicate_ids"]):
            raise ValueError("Complete coverage requires observed EOF")
        if "source_eof_observed" in coverage and (type(coverage["source_eof_observed"]) is not bool or coverage["complete_scan"] and not coverage["source_eof_observed"]):
            raise ValueError("Complete coverage contradicts scanner EOF observation")
        for k in ("compressed_bytes_read", "expanded_bytes_read"):
            if k in coverage and (type(coverage[k]) is not int or not 0 <= coverage[k] <= 2**63 - 1):
                raise ValueError("Scanner byte counters require bounded integers")
        metadata = packet.get("source_metadata_declaration")
        if type(metadata) is not dict or metadata.get("verified") is not False:
            raise ValueError("Source metadata must remain an unverified declaration")
        selection = packet.get("selection")
        if selection is not None and (type(selection) is not dict
                or type(selection.get("stop_when_all_ids_found")) is not bool
                or type(selection.get("duplicate_requested_ids")) is not list or any(type(i) is not str for i in selection["duplicate_requested_ids"])
                or selection.get("select_ids") is not None and (type(selection["select_ids"]) is not list
                    or any(type(i) is not str for i in selection["select_ids"]))):
            raise ValueError("Scanner selection requires typed declarative filters")
        missing = coverage.get("missing_selected_ids", [])
        if type(missing) is not list or any(type(i) is not str for i in missing):
            raise ValueError("Missing selected IDs require a bounded declared list")
        total += len(packet["records"])
        if total > MAX_ROWS: raise ValueError("Source links exceed 15000 total retained rows")
        packet_pins[table] = _hash(packet)
        scans[table] = {"packet_fingerprint": packet_pins[table], "source_path": packet["source_path"],
            "schema_version": packet["schema_version"], "instrument_version": packet["instrument_version"],
            "coverage": {k: coverage[k] for k in ("complete_scan", "stop_reason", *counters) if k in coverage},
            "source_metadata_declaration_hash": _hash(metadata), "source_metadata_verified": False,
            "global_uniqueness": "unverified", "logging_completeness": "unverified"}
        scans[table]["declared_selection"] = {"hash":_hash(selection),
            "filter_applied": selection is not None and selection.get("select_ids") is not None,
            "selected_ids_count":len(selection["select_ids"]) if selection is not None and selection.get("select_ids") is not None else None,
            "duplicate_requested_ids_count":len(selection["duplicate_requested_ids"]) if selection is not None else 0,
            "stop_when_all_ids_found":selection["stop_when_all_ids_found"] if selection is not None else None,
            "missing_selected_ids_count":len(missing),"missing_selected_ids_hash":_hash(missing),
            "interpretation":"inert_scanner_declaration_not_global_absence"}
        for k in ("compressed_bytes_read", "expanded_bytes_read", "source_eof_observed"):
            if k in coverage: scans[table]["coverage"][k] = coverage[k]
        rows[table] = []; seen_locations = set()
        for wrapper in packet["records"]:
            if type(wrapper) is not dict or set(wrapper) != {"record", "source"} or type(wrapper["record"]) is not dict:
                raise ValueError("Scanner records require exact record/source envelopes")
            source = wrapper["source"]
            if (type(source) is not dict or set(source) != {"path", "table", "line", "raw_line_sha256", "record_sha256"}
                    or source["path"] != packet["source_path"] or source["table"] != table
                    or type(source["line"]) is not int or not 1 <= source["line"] <= coverage["physical_rows_seen"]
                    or any(type(source[k]) is not str or not _DIGEST.fullmatch(source[k]) for k in ("raw_line_sha256", "record_sha256"))):
                raise ValueError("Source row pins require exact table/path, integer line and SHA256 declarations")
            if source["line"] in seen_locations: raise ValueError("Duplicate physical source line in packet")
            seen_locations.add(source["line"])
            if _hash(wrapper["record"]) != source["record_sha256"]: raise ValueError("Canonical record hash differs from source pin")
            rows[table].append({"raw": wrapper["record"], "source": source, "row_ref": _hash(source)})
    return rows, scans, packet_pins, canonical_bytes


def _row_summary(table, entry):
    raw = entry["raw"]; timestamp, _ = _timestamp(raw)
    summary = {"row_ref": entry["row_ref"], "source": dict(entry["source"]), "record_identity": _field(raw, "id", "id"),
        "created_at": timestamp, "namespace": table}
    if table == "events":
        data = raw.get("data") if type(raw.get("data")) is dict else {}
        action = _field(data, "actionType", "action")
        summary.update(event_index=_field(raw, "event_index", "index"), data_type_status="valid" if type(raw.get("data")) is dict else "invalid",
            action_type=action, platform_fields={k: _field(data, k, t) for k,t in (
                ("speakerId", "id"), ("agentId", "id"), ("roomId", "id"), ("messageId", "id"),
                ("chatMessageId", "id"), ("computerUseSessionId", "id"), ("content", "text"), ("sessionGoal", "text"), ("seconds", "seconds"))},
            provider_output_presence="absent" if "output" not in data else "null" if data["output"] is None else "recorded_not_emitted")
        if "actionType" in data and action["type_status"] == "invalid": summary["unknown_action_hash"] = _hash(data["actionType"])
    elif table == "chat_messages":
        summary["fields"] = {k: _field(raw,k,t) for k,t in (("agent_speaker_id","id"),("agent_id","id"),("room_id","id"),("content","text"),("speaker_type","speaker"))}
    elif table == "computer_use_sessions":
        summary["fields"] = {k: _field(raw,k,t) for k,t in (("agent_id","id"),("session_goal","text"))}
    else:
        action = raw.get("agent_action"); action_state = "absent" if "agent_action" not in raw else "null" if action is None else "object" if type(action) is dict else "invalid"
        kind = "command" if type(action) is dict and "command" in action else "object_other" if type(action) is dict else "none"
        if type(action) is dict and action.get("action") in ("left_click", "right_click", "double_click", "scroll", "key", "type", "send_message_back_to_chat"):
            kind = action["action"]
        summary.update(session_id=_field(raw,"session_id","id"),
            tool={"request_presence": action_state, "request_hash": _hash(action) if action_state == "object" else None,
                "action_kind": kind, "recorded_tool_attempt": action_state == "object" and bool(action),
                "output": _field(raw,"output","text"), "error": _field(raw,"error","text"),
                "null_error_does_not_prove_success": True, "execution_success": "unestablished",
                "provider_messages_presence": "absent" if "agent_messages" not in raw else "null" if raw["agent_messages"] is None else "recorded_not_emitted"})
    return summary


def triangulate_source_links(packets, *, rules_version="source-links-v1"):
    """Pure bounded audit: exact table/action names only, no latent inference."""
    if rules_version != RULES["version"]: raise ValueError("Unknown source-link rules version; aliases require a new explicit instrument")
    rows, scans, pins, input_bytes = _validate_packets(packets)
    summaries = {table: [_row_summary(table,e) for e in entries] for table,entries in rows.items()}
    indexes = {}
    for table, entries in rows.items():
        index = {}
        for entry in entries:
            identity = _field(entry["raw"],"id","id")
            if identity["type_status"] == "valid": index.setdefault(identity["value"],[]).append(entry)
        indexes[table] = index
    endpoint_groups = {table: [{"record_id": identity, "row_refs": [e["row_ref"] for e in group],
        "candidate_count": len(group), "uniqueness_scope": "scanned_rows_only"} for identity,group in sorted(index.items())]
        for table,index in indexes.items()}
    relations = []; action_counts = {action:0 for action in ACTION_TYPES}; unknown_actions = 0; pauses = []
    def relation(entry,kind,child,field,parent_table,checks):
        fk = _field(child,field,"id")
        link = {"relation_kind":kind,"child_row_ref":entry["row_ref"],"child_source":dict(entry["source"]),
            "foreign_key_field":field,"foreign_key":fk,"parent_table":parent_table,"endpoint_scope":"scanned_rows_only",
            "global_parent_uniqueness":"unverified","receipt":"unestablished","consumption":"unestablished","causal_influence":"unestablished",
            "field_checks":[],"child_identity_validation":_field(entry["raw"],"id","id"),"timestamp_difference_ms":None}
        if kind == "event_message_fk":
            if "chatMessageId" in child:
                link["field_checks"].append(_compare(child,"chatMessageId",child,"messageId","id"))
        if fk["type_status"] != "valid":
            link.update(status="missing_foreign_key" if fk["type_status"] == "unknown" else "invalid_foreign_key", candidate_count=0)
            link["parent_resolution"] = link["status"]
            relations.append(link); return
        candidates = indexes.get(parent_table,{}).get(fk["value"],[])
        link.update(parent_group_record_id=fk["value"],candidate_count=len(candidates),
            parent_scan_complete=scans.get(parent_table,{}).get("coverage",{}).get("complete_scan"))
        if parent_table not in rows: link["status"] = "unscanned_parent"
        elif not candidates: link["status"] = "missing_parent_in_scanned_scope"
        elif len(candidates) > 1: link["status"] = "ambiguous_parent"
        else:
            parent = candidates[0]; raw = parent["raw"]
            link["parent_row_ref"] = parent["row_ref"]; link["parent_source"] = dict(parent["source"])
            link["field_checks"].extend(_compare(child,c,raw,p,t) for c,p,t in checks)
            if kind == "event_message_fk":
                if "agent_id" in raw:
                    link["field_checks"].append(_compare(raw,"agent_id",raw,"agent_speaker_id","id"))
                speaker = _field(raw,"speaker_type","speaker")
                link["field_checks"].append({"child_field":"actionType","parent_field":"speaker_type","status":
                    "unknown" if speaker["type_status"] == "unknown" else "invalid_field" if speaker["type_status"] == "invalid" else
                    "matching" if speaker["value"] == "agent" else "conflicting", "parent":speaker})
            statuses = [check["status"] for check in link["field_checks"]]
            link["status"] = ("contradicted_fields" if "conflicting" in statuses else "invalid_fields" if "invalid_field" in statuses else
                "exported_fk_with_unknown_fields" if "unknown" in statuses else "verified_platform_emission_record" if kind == "event_message_fk" else "verified_exported_fk")
            a,at = _timestamp(entry["raw"]); b,bt = _timestamp(raw)
            link["timestamp_validation"] = {"child":a,"parent":b,"interpretation":"recorded_timestamp_difference_not_delivery"}
            if at is not None and bt is not None: link["timestamp_difference_ms"] = (at-bt).total_seconds()*1000
        link["parent_resolution"] = "unique_parent" if len(candidates) == 1 else link["status"]
        # Optional explicit IDs must agree even when the parent is not scanned.
        identity_statuses = [v["status"] for v in link["field_checks"]]
        if "conflicting" in identity_statuses: link["status"] = "contradicted_fields"
        elif link["child_identity_validation"]["type_status"] != "valid": link["status"] = "invalid_child_identity"
        elif "invalid_field" in identity_statuses: link["status"] = "invalid_fields"
        elif len(candidates) == 1 and scans[parent_table]["coverage"]["duplicate_ids"]:
            link["status"] = "exported_fk_with_parent_scan_ambiguity"
        relations.append(link)
    for entry in rows.get("events",[]):
        raw = entry["raw"]; data = raw.get("data") if type(raw.get("data")) is dict else {}
        action = _field(data,"actionType","action")
        if action["type_status"] != "valid": unknown_actions += 1; continue
        action = action["value"]; action_counts[action] += 1
        if action == "PAUSE":
            duration = _field(data,"seconds","seconds")
            if duration["type_status"] == "valid": pauses.append(duration["value"])
        if action == "AGENT_TALK": relation(entry,"event_message_fk",data,"messageId","chat_messages",[("speakerId","agent_speaker_id","id"),("roomId","room_id","id"),("content","content","text")])
        elif action in ("START_USING_COMPUTER","STOP_USING_COMPUTER"):
            fields = [("agentId","agent_id","id")]
            if action == "START_USING_COMPUTER": fields.append(("sessionGoal","session_goal","text"))
            relation(entry,"start_session_fk" if action == "START_USING_COMPUTER" else "stop_session_fk",data,"computerUseSessionId","computer_use_sessions",fields)
    for entry in rows.get("computer_use_turns",[]):
        raw = entry["raw"]
        relation(entry,"turn_session_fk",raw,"session_id","computer_use_sessions",[("agent_id","agent_id","id")] if "agent_id" in raw else [])
    status_counts = {}
    for link in relations: status_counts[link["status"]] = status_counts.get(link["status"],0)+1
    result = {"kind":"source_link_triangulation_audit","rules_version":rules_version,"rules_hash":_hash(RULES),
        "input_packet_fingerprints":pins,"input_canonical_bytes":input_bytes,"limits":dict(RULES["bounds"]),
        "source_scans":scans,"rows":summaries,"endpoint_groups":endpoint_groups,"relations":relations,
        "counts":{"retained_rows":sum(len(v) for v in rows.values()),"relations":len(relations),"relation_statuses":status_counts,
            "platform_actions":action_counts,"unknown_action_types":unknown_actions,
            "pause_duration_valid_records":len(pauses),"pause_duration_seconds_sum":sum(pauses),
            "pause_duration_interpretation":"recorded_requested_duration_only_not_inactivity_or_elapsed_clock_time"},
        "complete_scanned_inputs":all(v["coverage"]["complete_scan"] for v in scans.values()),
        "global_source_completeness":"unverified","evidence_scope":"supplied_scanned_rows_only",
        "model_calls":0,"database_writes":0,"limitations":list(LIMITATIONS)}
    if len(_canonical(result)) > MAX_OUTPUT_BYTES: raise ValueError("Source-link audit exceeds output byte cap; narrow declared scans")
    result["audit_hash"] = _hash(result)
    return result
