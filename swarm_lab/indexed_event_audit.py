"""Pure scoped comparisons of authenticated local-index event projections.

An accepted expected/read artifact hash binding is a caller/read-tool boundary.
This module never reads SQLite or raw events, and never authenticates original
payload bytes or registry objects. Matching projected fields against normalized
chat records is exported lineage evidence, not exposure or causal influence.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import PurePosixPath, PureWindowsPath

VERSION = "indexed-events-v1"
INDEX_INSTRUMENT = "bounded-event-source-index-v1"
MAX_ROWS = 15_000
MAX_INPUT_BYTES = 32 * 1024**2
MAX_OUTPUT_BYTES = 32 * 1024**2
MAX_WINDOWS = 24
MAX_DEPTH = 16
MAX_ITEMS = 2_000_000
MAX_STRING_BYTES = 1024**2
MAX_COMPARISONS = 100_000
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_OBJECT_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,255}\Z")
_ACTION = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
ACTIONS = ("AGENT_TALK", "USER_TALK", "START_USING_COMPUTER", "STOP_USING_COMPUTER", "CONSOLIDATE", "WAIT", "PAUSE", "SEARCH_HISTORY", "ENTER_ROOM", "REQUEST_HUMAN_HELPER", "CANCEL_REQUEST_FOR_HUMAN_HELPER", "STOP_HUMAN_USE_SESSION", "REQUEST_GOOGLE_SIGN_IN", "RESTARTING_AFTER_GOOGLE_SIGN_IN", "OUTREACH_APPROVAL_REQUEST", "OUTREACH_APPROVAL_RESPONSE", "USER_NAME_CHANGE")
COUNT_ACTIONS = ("WAIT", "PAUSE", "START_USING_COMPUTER", "STOP_USING_COMPUTER")
FIELD_KINDS = {"created_at":"timestamp", "event_index":"index", "data":"object",
    "data.actionType":"action", "data.messageId":"id", "data.chatMessageId":"id", "data.computerUseSessionId":"id",
    "data.speakerId":"id", "data.agentId":"id", "data.speakerType":"speaker", "data.roomId":"id", "data.content":"text",
    "data.sessionGoal":"text", "data.seconds":"seconds", "data.output":"provider_presence"}
PROJECTED_KEYS = {"id", "created_at", "time_valid", "event_index", "action_type", "actor_id", "actor_field", "actor_status",
    "room_id", "message_id", "chat_message_id", "computer_use_session_id", "speaker_id", "agent_id", "content_hash",
    "session_goal_hash", "seconds", "raw_provider_output_present", "fields"}
QUERY_COMBINATION = "(exact data.messageId/data.chatMessageId match OR valid room/UTC-window match); action_types filter applies globally; OR within each list"
LIMITATIONS = [
    "Matching fields concern an authenticated-local-index projection and pinned normalized chat, not fresh raw-parent/source rereads.",
    "Expected/read file hashes are accepted from a trusted host read-tool packet. This pure function cannot authenticate that tool, registry objects or original event bytes.",
    "Source record/raw-line hashes are original scan declarations bound inside the local artifact, not independently recomputed original-event evidence here.",
    "Explicit emission foreign keys and matching actor/room/content identify recorded lineage, not receipt, exposure, consumption or causal influence.",
    "Missing parents/children remain unknown within selected/query scope; prefix builds, filters and truncated queries never establish global absence or uniqueness.",
    "Original compound normalized content hashes differ from canonical JSON string-value hashes; both purposes are preserved without claiming raw-parent authenticity.",
    "Window counts require explicitly observed room and timestamp. Actor counts require an explicit source actor field; missing rooms are never inferred from actor or activity.",
    "WAIT/PAUSE/START/STOP are recorded choices and boundaries, not inactivity, successful access, an exclusive global lease or complete concurrent activity.",
    "Timestamp differences are recorded timing, never delivery latency. Overlapping original windows reuse evidence and are not independent samples.",
    "This audit does not merge mention graphs, rerank selected windows or promote a behavior/theory status.",
]


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode("utf-8")


def _hash(value): return hashlib.sha256(_canonical(value)).hexdigest()


def _finite_copy(value):
    stack=[(value,0)]; items=0; text_bytes=0
    while stack:
        item,depth=stack.pop(); items+=1
        if depth > MAX_DEPTH or items > MAX_ITEMS: raise ValueError("Indexed audit structure bound exceeded")
        if item is None or type(item) is bool: continue
        if type(item) is int:
            if abs(item)>2**63-1: raise ValueError("Indexed audit integer bound exceeded")
        elif type(item) is float:
            if not math.isfinite(item): raise ValueError("Indexed audit requires finite JSON")
        elif type(item) is str:
            try: size=len(item.encode("utf-8"))
            except UnicodeEncodeError as exc: raise ValueError("Indexed audit requires valid UTF-8") from exc
            text_bytes+=size
            if size>MAX_STRING_BYTES or text_bytes>MAX_INPUT_BYTES: raise ValueError("Indexed audit string bound exceeded")
        elif type(item) is list: stack.extend((v,depth+1) for v in item)
        elif type(item) is dict:
            if any(type(k) is not str for k in item): raise ValueError("Indexed audit JSON keys must be strings")
            stack.extend((v,depth+1) for pair in item.items() for v in pair)
        else: raise ValueError("Indexed audit accepts finite JSON only")
    data=_canonical(value)
    if len(data)>MAX_INPUT_BYTES: raise ValueError("Indexed audit exceeds input byte cap")
    return json.loads(data),len(data)


def _sha(value): return type(value) is str and _SHA.fullmatch(value) is not None
def _uuid(value): return type(value) is str and _UUID.fullmatch(value) is not None
def _integer(value): return type(value) is int and 0<=value<=2**63-1
def _absolute(value): return type(value) is str and len(value.encode("utf-8"))<=4096 and (PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute())


def _time(value, *, explicit=False):
    if type(value) is not str or len(value)>128: return None
    try:
        parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
        if parsed.tzinfo is None:
            if explicit: return None
            parsed=parsed.replace(tzinfo=timezone.utc)
        if explicit and parsed.utcoffset().total_seconds()!=0: return None
        return parsed.astimezone(timezone.utc)
    except (ValueError,OverflowError): return None


def _validate_refs(refs):
    if type(refs) is not dict or set(refs)!={"dataset","discovery","selected_audit"}:
        raise ValueError("Exact dataset/discovery/selected_audit version pins are required")
    for ref in refs.values():
        if (type(ref) is not dict or set(ref)!={"id","version","hash"} or type(ref["id"]) is not str
                or not _OBJECT_ID.fullmatch(ref["id"]) or type(ref["version"]) is not int or ref["version"]<1 or not _sha(ref["hash"])):
            raise ValueError("Source refs require exact identity/hash and positive integer version")


def _windows(values):
    if type(values) is not list or not 1<=len(values)<=MAX_WINDOWS: raise ValueError("Use 1 to 24 original windows")
    result=[]; seen=set()
    for window in values:
        if (type(window) is not dict or type(window.get("id")) is not str or not _OBJECT_ID.fullmatch(window["id"])
                or window["id"] in seen or not _uuid(window.get("room_id"))):
            raise ValueError("Original windows require unique bounded IDs and explicit room UUIDs")
        start,end=_time(window.get("start"),explicit=True),_time(window.get("end_exclusive"),explicit=True)
        if start is None or end is None or start>=end: raise ValueError("Original windows require ordered explicit UTC boundaries")
        seen.add(window["id"])
        result.append({"id":window["id"],"room_id":window["room_id"],"start":window["start"],"end_exclusive":window["end_exclusive"],
            "source_window_hash":_hash(window),"_start":start,"_end":end})
    return result


def _validate_field(field,kind):
    allowed={"presence","type_status"}|({"value"} if kind in ("id","index","seconds","speaker") else
        {"value","recognized"} if kind=="action" else {"value_hash"} if kind=="text" else
        {"value_hash","utc","timezone_policy"} if kind=="timestamp" else {"value_type"} if kind=="provider_presence" else set())
    if (type(field) is not dict or not set(field)<=allowed
            or field.get("presence") not in ("absent","null","value") or field.get("type_status") not in ("unknown","valid","invalid")):
        raise ValueError("Projected fields require bounded explicit presence/type diagnostics")
    if field["presence"] in ("absent","null") and field["type_status"]!="unknown": raise ValueError("Unknown field presence/type conflict")
    if "value_hash" in field and not _sha(field["value_hash"]): raise ValueError("Field value hash must be SHA256")
    if "timezone_policy" in field and field["timezone_policy"] not in ("export_naive_assumed_utc","explicit_offset_to_utc"):
        raise ValueError("Timestamp policy must be the declared finite vocabulary")
    if "value_type" in field and field["value_type"] not in ("null","object","array","string","boolean","number"): raise ValueError("Provider value-type diagnostic must be finite vocabulary")
    if "recognized" in field and (kind!="action" or type(field["recognized"]) is not bool): raise ValueError("Action recognition requires exact boolean diagnostic")
    if field["type_status"]!="valid":
        if "value" in field or "utc" in field: raise ValueError("Invalid/unknown projected fields cannot carry measured values")
        return
    if field["presence"]!="value": raise ValueError("Measured field requires original value presence")
    value=field.get("value")
    if kind=="id" and not _uuid(value): raise ValueError("Measured event IDs require exact UUID values")
    if kind=="index" and not _integer(value): raise ValueError("Measured event index requires integer")
    if kind=="seconds" and not (type(value) in (int,float) and 0<=value<=2**31-1): raise ValueError("Measured pause seconds require bounded nonboolean number")
    if kind=="action" and (type(value) is not str or not _ACTION.fullmatch(value) or field.get("recognized") is not (value in ACTIONS)): raise ValueError("Action token/recognition binding differs")
    if kind=="speaker" and (type(value) is not str or value not in ("agent","user")): raise ValueError("Measured speakerType requires declared agent/user enum")
    if kind=="text" and ("value" in field or not _sha(field.get("value_hash"))): raise ValueError("Projected text requires canonical value hash only")
    if kind=="timestamp" and ("value" in field or not _sha(field.get("value_hash")) or _time(field.get("utc"),explicit=True) is None
            or field.get("timezone_policy") not in ("export_naive_assumed_utc","explicit_offset_to_utc")):
        raise ValueError("Projected time requires original value hash and explicit normalized UTC")
    if kind in ("object","provider_presence") and ("value" in field or "value_hash" in field): raise ValueError("Raw data/provider payload may not occur in projections")


def _measure(fields,path):
    field=fields[path]
    if field["type_status"]!="valid": return None
    return field.get("value_hash") if FIELD_KINDS[path] in ("text","timestamp") else field.get("value")


def _validate_projection(record):
    if type(record) is not dict or set(record)!=PROJECTED_KEYS or not _uuid(record["id"]) or type(record["time_valid"]) is not bool:
        raise ValueError("Use exact bounded event-index projection schema")
    fields=record["fields"]
    if type(fields) is not dict or set(fields)!=set(FIELD_KINDS):
        raise ValueError("Projection must preserve exact source field paths")
    for path,field in fields.items(): _validate_field(field,FIELD_KINDS[path])
    mirrors={"event_index":"event_index","action_type":"data.actionType","room_id":"data.roomId","message_id":"data.messageId",
        "chat_message_id":"data.chatMessageId","computer_use_session_id":"data.computerUseSessionId","speaker_id":"data.speakerId",
        "agent_id":"data.agentId","content_hash":"data.content","session_goal_hash":"data.sessionGoal","seconds":"data.seconds"}
    for key,path in mirrors.items():
        if _hash(record[key])!=_hash(_measure(fields,path)): raise ValueError("Projection/source diagnostic value contradiction")
    time_field=fields["created_at"]; valid=time_field["type_status"]=="valid"
    if record["time_valid"] is not valid or record["created_at"]!=(time_field.get("utc") if valid else None):
        raise ValueError("Projected timestamp/time-valid binding differs")
    chosen="data.speakerId" if record["action_type"] in ("AGENT_TALK","USER_TALK") else "data.agentId"
    a,b=_measure(fields,"data.speakerId"),_measure(fields,"data.agentId")
    if a is not None and b is not None and a!=b: status,actor,actor_field="conflicting_fields",None,None
    elif record["action_type"] not in ACTIONS: status,actor,actor_field="unrecognized_action",None,None
    elif fields[chosen]["type_status"]=="valid": status,actor,actor_field="selected_valid",_measure(fields,chosen),chosen
    else: status,actor,actor_field=("invalid_field" if fields[chosen]["type_status"]=="invalid" else "unknown"),None,None
    if any(_hash(record[k])!=_hash(v) for k,v in (("actor_status",status),("actor_id",actor),("actor_field",actor_field))):
        raise ValueError("Projected actor selection contradicts explicit source fields")
    output=fields["data.output"]
    if type(record["raw_provider_output_present"]) is not bool or record["raw_provider_output_present"] is not (output["presence"]=="value"):
        raise ValueError("Provider presence binding differs")


def _packet(packet):
    if (type(packet) is not dict or packet.get("kind")!="indexed_event_source_query" or packet.get("instrument_version")!=INDEX_INSTRUMENT
            or packet.get("schema_version")!="1.0" or type(packet.get("records")) is not list
            or packet.get("read_only") is not True or type(packet.get("model_calls")) is not int or packet["model_calls"]!=0):
        raise ValueError("Use a released event-index query packet")
    index=packet.get("index"); coverage=packet.get("coverage"); query=packet.get("query")
    if (type(index) is not dict or not _absolute(index.get("path")) or index.get("file_hash_authenticated") is not True
            or not _sha(index.get("expected_file_sha256")) or not _sha(index.get("read_file_sha256")) or not _sha(index.get("post_query_file_sha256"))
            or index["expected_file_sha256"]!=index["read_file_sha256"] or index["read_file_sha256"]!=index["post_query_file_sha256"]):
        raise ValueError("Authenticated expected/read index-file SHA binding is required")
    if type(index.get("bytes")) is not int or not 1<=index["bytes"]<=2*1024**3: raise ValueError("Index artifact size requires bounded positive integer")
    if not _sha(index.get("internal_metadata_sha256")): raise ValueError("Index internal build metadata hash is required")
    implementations=index.get("implementation_hashes")
    if (type(implementations) is not dict or set(implementations)!={"event_source_index.py","source_scanner.py","source_links.py","source_workflow.py"}
            or any(not _sha(v) for v in implementations.values())):
        raise ValueError("Index implementation pins require filename/SHA256 pairs")
    if (type(coverage) is not dict or type(coverage.get("query_complete")) is not bool or type(coverage.get("truncated")) is not bool
            or not _integer(coverage.get("matched_rows")) or not _integer(coverage.get("returned_rows"))
            or coverage["returned_rows"]!=len(packet["records"]) or coverage["matched_rows"]<coverage["returned_rows"]
            or coverage["query_complete"] and (coverage["truncated"] or coverage["matched_rows"]!=coverage["returned_rows"])):
        raise ValueError("Query coverage counters/terminal statuses contradict retained projections")
    build=coverage.get("build_scan")
    if (type(build) is not dict or type(build.get("complete_scan")) is not bool or type(build.get("source_eof_observed")) is not bool
            or type(build.get("stop_reason")) is not str or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}",build["stop_reason"])
            or not _integer(build.get("physical_rows_seen")) or not _integer(build.get("indexed_rows"))
            or build["indexed_rows"]<coverage["matched_rows"] or build["physical_rows_seen"]<build["indexed_rows"]
            or build["complete_scan"] and (not build["source_eof_observed"] or build["stop_reason"]!="eof")):
        raise ValueError("Build coverage is separate and must remain truthful/typed")
    if (type(query) is not dict or set(query)!={"message_ids","windows","action_types","max_rows","combination"}
            or query.get("message_ids") is not None and (type(query["message_ids"]) is not list or not query["message_ids"]
                or any(not _uuid(v) for v in query["message_ids"]) or len(query["message_ids"])!=len(set(query["message_ids"])))
            or query.get("action_types") is not None and (type(query["action_types"]) is not list or not query["action_types"]
                or any(type(v) is not str or not _ACTION.fullmatch(v) for v in query["action_types"]) or len(query["action_types"])!=len(set(query["action_types"])))
            or type(query.get("max_rows")) is not int or not 1<=query["max_rows"]<=MAX_ROWS
            or coverage["returned_rows"]>query["max_rows"] or query.get("combination")!=QUERY_COMBINATION):
        raise ValueError("Explicit query filter contract is invalid")
    qwindows=query.get("windows")
    if qwindows is not None and (type(qwindows) is not list or not qwindows or len(qwindows)>64): raise ValueError("Query window cap exceeded")
    qwindows=qwindows or []
    for win in qwindows:
        if (type(win) is not dict or not {"room_id","start","end_exclusive"}<=set(win) or not set(win)<={"id","room_id","start","end_exclusive"}
                or not _uuid(win["room_id"]) or _time(win["start"],explicit=True) is None or _time(win["end_exclusive"],explicit=True) is None
                or _time(win["start"],explicit=True)>=_time(win["end_exclusive"],explicit=True)):
            raise ValueError("Query windows require exact explicit room/time filters")
    locations=set()
    for wrapper in packet["records"]:
        if type(wrapper) is not dict or set(wrapper)!={"record","source","projection_sha256"}: raise ValueError("Exact projection/source/hash envelope required")
        _validate_projection(wrapper["record"])
        if not _sha(wrapper["projection_sha256"]) or _hash(wrapper["record"])!=wrapper["projection_sha256"]: raise ValueError("Projection hash differs")
        source=wrapper["source"]
        if (type(source) is not dict or set(source)!={"path","table","line","record_sha256","raw_line_sha256"}
                or not _absolute(source["path"]) or source["table"]!="events" or type(source["line"]) is not int
                or not 1<=source["line"]<=build["physical_rows_seen"] or not _sha(source["record_sha256"]) or not _sha(source["raw_line_sha256"])):
            raise ValueError("Original event source declarations have invalid typed coordinates/hashes")
        location=(source["path"],source["line"])
        if location in locations: raise ValueError("Repeated physical event line in query")
        locations.add(location); record=wrapper["record"]
        if query["action_types"] and record["action_type"] not in query["action_types"]: raise ValueError("Returned projection violates action filter")
        stamp=_time(record["created_at"],explicit=True)
        message_match=any(record[key] in (query["message_ids"] or []) for key in ("message_id","chat_message_id"))
        window_match=any(record["room_id"]==w["room_id"] and stamp is not None and _time(w["start"],explicit=True)<=stamp<_time(w["end_exclusive"],explicit=True) for w in qwindows)
        if (query["message_ids"] or qwindows) and not (message_match or window_match): raise ValueError("Returned projection violates declared union selection")
    return index,coverage,query


def _chat_field(message,name,kind):
    if name not in message: return {"presence":"absent","type_status":"unknown"}
    value=message[name]
    if value is None: return {"presence":"null","type_status":"unknown"}
    valid=_uuid(value) if kind=="id" else type(value) is str if kind=="text" else type(value) is str and value in ("agent","user")
    result={"presence":"value","type_status":"valid" if valid else "invalid"}
    if valid: result["value_hash" if kind=="text" else "value"]=_hash(value) if kind=="text" else value
    return result


def _comparison(child_field,parent_field):
    if "invalid" in (child_field["type_status"],parent_field["type_status"]): return "invalid_field"
    if "unknown" in (child_field["type_status"],parent_field["type_status"]): return "unknown"
    a=child_field.get("value_hash",child_field.get("value")); b=parent_field.get("value_hash",parent_field.get("value"))
    return "matching" if _hash(a)==_hash(b) else "conflicting"


def audit_indexed_event_matches(event_packet,chat_messages,*,windows,source_refs,rules_version=VERSION):
    """Compare only original selected scopes; never treat absence as delivery."""
    if rules_version!=VERSION: raise ValueError("Unknown indexed audit rules; aliases require a new instrument")
    supplied,input_bytes=_finite_copy({"event_packet":event_packet,"chat_messages":chat_messages,"windows":windows,"source_refs":source_refs})
    event_packet=supplied["event_packet"]; messages=supplied["chat_messages"]; source_refs=supplied["source_refs"]
    _validate_refs(source_refs); scopes=_windows(supplied["windows"]); index,coverage,query=_packet(event_packet)
    if type(messages) is not list or len(messages)+len(event_packet["records"])>MAX_ROWS: raise ValueError("Use at most 15000 aggregate chat/event rows")
    parents={}; chats=[]; selected=[]
    for number,message in enumerate(messages):
        if type(message) is not dict or not _uuid(message.get("id")) or type(message.get("content")) is not str or not _sha(message.get("content_hash")):
            raise ValueError("Pinned normalized chats need exact ID, untrimmed content and compound hash")
        source=message.get("source")
        if (type(source) is not dict or source.get("table")!="chat_messages" or not _absolute(source.get("file"))
                or type(source.get("line")) is not int or source["line"]<1): raise ValueError("Normalized chats need exact original source coordinates")
        stamps=[_time(message[k]) for k in ("created_at","timestamp") if k in message and message[k] is not None]
        time_known=bool(stamps) and all(s is not None and s==stamps[0] for s in stamps)
        stamp=stamps[0] if time_known else None
        local=[s["id"] for s in scopes if _uuid(message.get("room_id")) and message["room_id"]==s["room_id"] and stamp is not None and s["_start"]<=stamp<s["_end"]]
        chat_ref=_hash({"input_row":number,"id":message["id"],"source":source,"normalized_record_hash":_hash(message)})
        summary={"chat_ref":chat_ref,"message_id":message["id"],"source":{"file":source["file"],"line":source["line"],"table":"chat_messages"},
            "normalized_record_hash":_hash(message),"normalized_compound_content_hash":message["content_hash"],"canonical_content_value_hash":_hash(message["content"]),
            "original_window_ids":local,"time_status":"consistent" if time_known else "unknown_or_conflicting","timestamp":stamp.isoformat(timespec="microseconds") if stamp is not None else None,
            "fields":{k:_chat_field(message,k,t) for k,t in (("agent_id","id"),("agent_speaker_id","id"),("room_id","id"),("speaker_type","speaker"),("content","text"))}}
        row={"raw":message,"summary":summary,"stamp":stamp}
        parents.setdefault(message["id"],[]).append(row); chats.append(summary)
        if local: selected.append(row)
    wrappers=event_packet["records"]; event_ids={}; children={}; event_rows=[]; matches=[]
    window_counts={s["id"]:{"platform_actions":{a:0 for a in COUNT_ACTIONS},"by_explicit_actor":{},"pause_seconds_valid_records":0,"pause_requested_seconds_sum":0} for s in scopes}
    for wrapper in wrappers:
        record=wrapper["record"]; ref=_hash({"source":wrapper["source"],"projection_sha256":wrapper["projection_sha256"]})
        event_ids.setdefault(record["id"],[]).append(ref)
        stamp=_time(record["created_at"],explicit=True) if record["time_valid"] else None
        local=[s["id"] for s in scopes if record["room_id"]==s["room_id"] and stamp is not None and s["_start"]<=stamp<s["_end"]]
        reasons=[]
        if record["room_id"] is None: reasons.append("room_unmeasured_no_inference")
        if stamp is None: reasons.append("time_invalid_or_unmeasured")
        if not local and not reasons: reasons.append("outside_original_selected_windows")
        row={"event_ref":ref,"event_id":record["id"],"source":wrapper["source"],"projection_sha256":wrapper["projection_sha256"],
            "raw_row_hash_scope":"original_scan_declaration_inside_authenticated_local_artifact",
            "created_at":record["created_at"],"time_valid":record["time_valid"],"event_index":record["event_index"],
            "action_type":record["action_type"],"actor_id":record["actor_id"],"actor_field":record["actor_field"],"actor_status":record["actor_status"],
            "room_id":record["room_id"],"original_window_ids":local,"unassigned_reasons":reasons,"field_diagnostics":record["fields"]}
        if record["action_type"]=="AGENT_TALK":
            row["message_fk_identity_check"]="not_asserted" if record["fields"]["data.chatMessageId"]["presence"]=="absent" else _comparison(record["fields"]["data.chatMessageId"],record["fields"]["data.messageId"])
        event_rows.append(row)
        for window_id in local:
            if record["action_type"] in COUNT_ACTIONS:
                count=window_counts[window_id]; count["platform_actions"][record["action_type"]]+=1
                if record["actor_status"]=="selected_valid":
                    actor=count["by_explicit_actor"].setdefault(record["actor_id"],{a:0 for a in COUNT_ACTIONS})
                    actor[record["action_type"]]+=1
                if record["action_type"]=="PAUSE" and record["seconds"] is not None:
                    count["pause_seconds_valid_records"]+=1; count["pause_requested_seconds_sum"]+=record["seconds"]
        if record["action_type"]=="AGENT_TALK": children.setdefault(record["message_id"],[]).append((wrapper,ref,stamp))
    comparison_work=0
    for parent in selected:
        message=parent["raw"]; summary=parent["summary"]; candidates=children.get(message["id"],[])
        result={"chat_ref":summary["chat_ref"],"message_id":message["id"],"original_window_ids":summary["original_window_ids"],
            "parent_speaker_category":message.get("speaker_type") if message.get("speaker_type") in ("agent","user") else "other",
            "emission_lookup_scope":"AGENT_TALK explicit messageId only; USER_TALK is not a missing-agent emission",
            "parent_source":summary["source"],"normalized_compound_content_hash":summary["normalized_compound_content_hash"],
            "canonical_content_value_hash":summary["canonical_content_value_hash"],"emission_status":"unknown","candidate_count":len(candidates),
            "parent_identity_count":len(parents[message["id"]]),"candidate_event_refs":[ref for _,ref,_ in candidates],
            "field_checks":[],"candidate_checks":[],"ambiguity_status":None,"timestamp_difference_ms":None,
            "receipt":"unestablished","exposure":"unestablished","consumption":"unestablished","causal_influence":"unestablished"}
        if len(parents[message["id"]])>1: result["ambiguity_status"]="duplicate_normalized_parent_id"
        elif len(candidates)>1: result["ambiguity_status"]="multiple_emission_records_for_message"
        for wrapper,ref,stamp in candidates:
            comparison_work+=1
            if comparison_work>MAX_COMPARISONS: raise ValueError("Ambiguous emission comparison budget exceeded; narrow source scope")
            record=wrapper["record"]; fields=record["fields"]
            if len(event_ids[record["id"]])>1 and result["ambiguity_status"] is None: result["ambiguity_status"]="duplicate_event_id"
            checks=[]
            for child_path,parent_name in (("data.speakerId","agent_id"),("data.roomId","room_id"),("data.content","content")):
                checks.append({"event_field":child_path,"parent_field":parent_name,"status":_comparison(fields[child_path],summary["fields"][parent_name])})
            if fields["data.chatMessageId"]["presence"]!="absent":
                checks.append({"event_field":"data.chatMessageId","parent_field":"event.data.messageId","status":_comparison(fields["data.chatMessageId"],fields["data.messageId"])})
            if "agent_speaker_id" in message:
                checks.append({"event_field":"normalized.agent_id","parent_field":"raw.agent_speaker_id","status":_comparison(summary["fields"]["agent_id"],summary["fields"]["agent_speaker_id"])})
            if fields["data.speakerType"]["presence"]!="absent":
                checks.append({"event_field":"data.speakerType","parent_field":"normalized.speaker_type","status":_comparison(fields["data.speakerType"],summary["fields"]["speaker_type"])})
            checks.append({"event_field":"event.actor_selection","parent_field":"explicit source actor fields","status":"conflicting" if record["actor_status"]=="conflicting_fields" else "matching" if record["actor_status"]=="selected_valid" else "unknown"})
            speaker=summary["fields"]["speaker_type"]
            checks.append({"event_field":"AGENT_TALK","parent_field":"normalized.speaker_type","status":"matching" if speaker.get("value")=="agent" else "conflicting" if speaker.get("value")=="user" else "unknown"})
            statuses=[c["status"] for c in checks]
            semantic="conflict" if "conflicting" in statuses else "matching" if all(s=="matching" for s in statuses) else "unknown"
            delta=(stamp-parent["stamp"]).total_seconds()*1000 if stamp is not None and parent["stamp"] is not None else None
            result["candidate_checks"].append({"event_ref":ref,"field_checks":checks,"semantic_status":semantic,"timestamp_difference_ms":delta,
                "timestamp_interpretation":"recorded_difference_not_delivery","event_time_status":"valid_recorded_utc" if record["time_valid"] else "event_time_unknown",
                "event_order_status":"recorded_index_valid" if fields["event_index"]["type_status"]=="valid" else "event_order_unknown",
                "event_window_corroboration":"same_explicit_room_time_window" if record["room_id"]==message.get("room_id") and stamp is not None and any(s["id"] in summary["original_window_ids"] and s["_start"]<=stamp<s["_end"] for s in scopes)
                    else "event_time_unknown" if stamp is None else "outside_parent_original_window",
                "unmeasured_optional_fields":["data.speakerType"] if fields["data.speakerType"]["presence"]=="absent" else []})
        result["semantic_conflict_present"]=any(c["semantic_status"]=="conflict" for c in result["candidate_checks"])
        if len(result["candidate_checks"])==1:
            one=result["candidate_checks"][0]; result["field_checks"]=one["field_checks"]; result["timestamp_difference_ms"]=one["timestamp_difference_ms"]
            if result["ambiguity_status"] is None:
                result["emission_status"]="matched" if one["semantic_status"]=="matching" else "conflict" if one["semantic_status"]=="conflict" else "unknown"
        result["match_label"]="indexed_emission_fields_matching_normalized_chat" if result["emission_status"]=="matched" else "indexed_emission_fields_unresolved_or_conflicting"
        matches.append(result)
    projected_parent_links=[]
    selected_parent_ids={parent["raw"]["id"] for parent in selected}
    for identity,candidates in children.items():
        for wrapper,ref,_ in candidates:
            statuses="unknown_foreign_key" if identity is None else "absent_parent_in_supplied_dataset" if identity not in parents else "outside_selected_chat_scope" if identity not in selected_parent_ids else "selected_parent_present"
            projected_parent_links.append({"event_ref":ref,"message_id":identity,"status":statuses,"parent_scope":"pinned_normalized_dataset_and_original_selected_windows",
                "optional_fk_agreement":"not_asserted" if wrapper["record"]["fields"]["data.chatMessageId"]["presence"]=="absent" else _comparison(wrapper["record"]["fields"]["data.chatMessageId"],wrapper["record"]["fields"]["data.messageId"])})
    out_windows=[]
    for scope in scopes:
        counts={status:sum(m["emission_status"]==status and scope["id"] in m["original_window_ids"] for m in matches) for status in ("matched","unknown","conflict")}
        out_windows.append({**{k:v for k,v in scope.items() if not k.startswith("_")},"selected_chat_records":sum(scope["id"] in p["summary"]["original_window_ids"] for p in selected),
            "emission_status_counts":counts,**window_counts[scope["id"]],"count_scope":"explicit event room/time within this original window; scoped recorded counts only"})
    result={"kind":"indexed_event_match_audit","rules_version":VERSION,"source_refs":source_refs,"source_refs_authentication":"host_required_not_performed_by_pure_audit",
        "input_packet_hash":_hash(event_packet),"chat_input_hash":_hash(messages),"windows_input_hash":_hash(supplied["windows"]),"input_canonical_bytes":input_bytes,
        "index_artifact_binding":{"path":index["path"],"expected_file_sha256":index["expected_file_sha256"],"read_file_sha256":index["read_file_sha256"],
            "post_query_file_sha256":index["post_query_file_sha256"],
            "internal_metadata_sha256":index["internal_metadata_sha256"],
            "matching_host_read_binding":True,"original_event_bytes_reread":False,"implementation_hashes":index["implementation_hashes"]},
        "query_plan_hash":_hash(query),"coverage":{"build_scan":{k:coverage["build_scan"][k] for k in ("complete_scan","stop_reason","source_eof_observed","physical_rows_seen","indexed_rows")},
            "query_complete":coverage["query_complete"],"truncated":coverage["truncated"],"matched_rows":coverage["matched_rows"],"returned_rows":coverage["returned_rows"],
            "global_absence":"unverified","global_uniqueness":"unverified"},
        "windows":out_windows,"normalized_chat_sources":chats,"events":event_rows,"emissions":matches,"projected_parent_links":projected_parent_links,
        "counts":{"supplied_chat_records":len(messages),"selected_chat_records":len(selected),"out_of_scope_or_time_unresolved_chat_records":len(messages)-len(selected),
            "selected_chat_by_speaker_type":{category:sum((p["raw"].get("speaker_type") if p["raw"].get("speaker_type") in ("agent","user") else "other")==category for p in selected) for category in ("agent","user","other")},
            "emission_statuses_by_speaker_type":{category:{status:sum(m["parent_speaker_category"]==category and m["emission_status"]==status for m in matches) for status in ("matched","unknown","conflict")} for category in ("agent","user","other")},
            "projected_event_records":len(wrappers),"emission_statuses":{status:sum(m["emission_status"]==status for m in matches) for status in ("matched","unknown","conflict")}},
        "limits":{"max_rows":MAX_ROWS,"max_input_bytes":MAX_INPUT_BYTES,"max_output_bytes":MAX_OUTPUT_BYTES,"max_depth":MAX_DEPTH,"max_comparisons":MAX_COMPARISONS},
        "comparison_work":comparison_work,"model_calls":0,"database_writes":0,"status_promotion":False,"limitations":list(LIMITATIONS)}
    if len(_canonical(result))>MAX_OUTPUT_BYTES: raise ValueError("Indexed audit output cap exceeded; narrow input scope")
    result["audit_hash"]=_hash(result)
    return result
