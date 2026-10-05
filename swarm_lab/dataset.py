"""Bounded, provenance-preserving imports of the AI Village JSONL export.

The export is not chronologically ordered.  Filtering must scan the source;
``limit`` constrains retained records rather than silently taking arbitrary UUID
order.  Large computer-use tables/screenshots are never opened by this module.
"""
from __future__ import annotations

import gzip
import hashlib
import heapq
import json
import copy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def parse_time(value: str | datetime | None) -> datetime | None:
    """Interpret naive export timestamps as UTC, as specified by SCHEMA.md."""
    if value is None or value == "":
        return None
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso_time(value: str | datetime | None) -> str | None:
    parsed = parse_time(value)
    # Fixed precision makes lexical ordering chronological even when one source
    # timestamp lacks a fractional component and another includes it.
    return parsed.isoformat(timespec="microseconds").replace("+00:00", "Z") if parsed else None


def iter_jsonl(path: Path | str, *, diagnostics: dict | None = None) -> Iterator[tuple[int, dict]]:
    """Stream one source; report malformed rows without inventing valid records."""
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, 1):
            if diagnostics is not None:
                diagnostics["rows_scanned"] = diagnostics.get("rows_scanned", 0) + 1
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError("Expected a JSON object")
            except (json.JSONDecodeError, ValueError) as exc:
                if diagnostics is None:
                    raise ValueError(f"Malformed JSONL row {line_number} in {path.name}") from exc
                diagnostics["malformed_rows"] = diagnostics.get("malformed_rows", 0) + 1
                if len(diagnostics.setdefault("warnings", [])) < 20:
                    diagnostics["warnings"].append({"row": line_number, "reason": "malformed_json_object"})
                continue
            yield line_number, row


def _table(root: Path, name: str) -> Path | None:
    for suffix in (".jsonl.gz", ".jsonl"):
        path = root / (name + suffix)
        if path.is_file():
            return path
    return None


def _small_table(root: Path, name: str, maximum: int = 5000) -> list[dict]:
    path = _table(root, name)
    if path is None:
        return []
    records = []
    for number, row in iter_jsonl(path):
        if len(records) >= maximum:
            raise ValueError(f"Metadata table {name} exceeds safety limit {maximum}; scope it explicitly")
        records.append({**row, "source": {"file": str(path.resolve()), "line": number, "table": name}})
    return records


def normalize_message(row: dict, *, source: Path | str | None = None, line: int | None = None, agents: dict | None = None) -> dict:
    """Retain source IDs and speaker type; user speakers are not agent identities."""
    identity = row.get("agent_speaker_id") or row.get("agent_id") or row.get("speaker_id")
    speaker_type = row.get("speaker_type", "agent" if identity else "user")
    if speaker_type != "agent":
        identity = None
    speaker = identity or row.get("user_speaker_id") or row.get("speaker_id") or "unidentified-human"
    timestamp = iso_time(row.get("created_at") or row.get("timestamp"))
    if timestamp is None:
        raise ValueError("Message requires created_at or timestamp")
    content = row.get("content", "")
    if not isinstance(content, str):
        raise ValueError("Chat content must be a string")
    original_source = row.get("source") or {}
    provenance = dict(original_source)
    if source is not None:
        provenance.update(file=str(Path(source).resolve()), line=line, table="chat_messages")
    stable = {"speaker": speaker, "timestamp": timestamp, "content": content, "room_id": row.get("room_id", "main")}
    digest = hashlib.sha256(json.dumps(stable, sort_keys=True).encode("utf-8")).hexdigest()
    result = {
        "id": str(row.get("id") or "derived-" + digest[:24]),
        "agent_id": identity,
        "speaker_id": str(speaker),
        "speaker_type": speaker_type,
        "agent_name": (agents or {}).get(identity, {}).get("name", row.get("agent_name") or str(speaker)),
        "room_id": str(row.get("room_id") or "main"),
        "created_at": timestamp,
        "timestamp": timestamp,
        "content": content,
        "source": provenance,
        "content_hash": digest,
        "reply_to": row.get("reply_to") or row.get("reply_to_id"),
    }
    result.update(explicit_communication_metadata(row, actor_id=str(speaker)))
    return result


def explicit_communication_metadata(row: dict, *, actor_id: str | None = None) -> dict:
    """Keep declared addressing/visibility; missing fields remain absent, not inferred.

    These labels describe producer-reported scope. They establish neither room
    membership nor actual message receipt. Private/local notes are distinct from
    a recipient's exposure; this function does not create reasoning records.
    """
    result = {}
    if "recipient_ids" in row:
        recipients = row["recipient_ids"]
        if type(recipients) is not list or len(recipients) > 64:
            raise ValueError("Explicit recipient_ids must be a bounded list")
        if any(type(item) is not str or not item.strip() or len(item) > 200 for item in recipients):
            raise ValueError("Explicit recipients must be bounded nonblank IDs")
        for item in recipients: item.encode("utf-8")
        if len(set(recipients)) != len(recipients): raise ValueError("Duplicate explicit recipient ID")
        result["recipient_ids"] = copy.deepcopy(recipients)
    if "channel_name" in row:
        value = row["channel_name"]
        if type(value) is not str or not value.strip() or len(value) > 1000:
            raise ValueError("Explicit channel_name must be bounded nonblank text")
        value.encode("utf-8"); result["channel_name"] = value
    if "visibility" in row:
        visibility = row["visibility"]
        if type(visibility) is not str or visibility not in ("private", "direct", "room", "broadcast", "unknown"):
            raise ValueError("Unsupported explicit message visibility")
        recipients = result.get("recipient_ids", [])
        if visibility == "private" and (recipients or "channel_name" in result):
            raise ValueError("Private self records cannot address peers or a channel")
        if visibility == "direct" and (not recipients or actor_id in recipients):
            raise ValueError("Direct messages require explicit peer recipients")
        if visibility == "room" and not result.get("channel_name"):
            room = row.get("room_id")
            if type(room) is not str or not room.strip() or len(room) > 200:
                raise ValueError("Room posts require an explicit typed room or channel label")
            room.encode("utf-8")
        if visibility == "broadcast" and recipients:
            raise ValueError("Broadcast cannot use an enumerated direct-recipient list")
        result["visibility"] = visibility
    return result


def _bounded_rows(path: Path, *, start: datetime | None, end: datetime | None, limit: int, room: str | None, agents: dict, kind: str) -> tuple[list[dict], dict]:
    diagnostics: dict[str, Any] = {"rows_scanned": 0, "matched_rows": 0, "malformed_rows": 0, "invalid_rows": 0, "duplicate_ids": 0, "warnings": []}
    retained: list[tuple[float, str, int, dict]] = []
    ids: set[str] = set()
    for number, row in iter_jsonl(path, diagnostics=diagnostics):
        try:
            timestamp = parse_time(row.get("created_at") or row.get("timestamp"))
            if timestamp is None:
                raise ValueError("missing timestamp")
            if (start and timestamp < start) or (end and timestamp >= end):
                continue
            data = row.get("data") or {}
            row_room = row.get("room_id") or (data.get("roomId") if isinstance(data, dict) else None)
            if room and row_room != room:
                continue
            record = normalize_message(row, source=path, line=number, agents=agents) if kind == "chat_messages" else {**row, "created_at": iso_time(timestamp), "source": {"file": str(path.resolve()), "line": number, "table": kind}}
        except (TypeError, ValueError):
            diagnostics["invalid_rows"] += 1
            if len(diagnostics["warnings"]) < 20:
                diagnostics["warnings"].append({"row": number, "reason": "invalid_timestamp_or_message"})
            continue
        diagnostics["matched_rows"] += 1
        identity = str(record.get("id", f"line-{number}"))
        # Duplicate IDs outside the retained scope do not warrant retaining an
        # unbounded set.  Count/exclude duplicates among the actual selection.
        if identity in ids:
            diagnostics["duplicate_ids"] += 1
            continue
        item = (-timestamp.timestamp(), "".join(chr(0x10FFFF - ord(c)) for c in identity), -number, record)
        if len(retained) < limit:
            heapq.heappush(retained, item)
            ids.add(identity)
        elif item[:3] > retained[0][:3]:
            removed = heapq.heapreplace(retained, item)
            ids.discard(str(removed[3].get("id", f"line-{-removed[2]}")))
            ids.add(identity)
    selected = sorted((item[3] for item in retained), key=lambda r: (r["created_at"], str(r.get("id", ""))))
    diagnostics["retained_rows"] = len(selected)
    diagnostics["truncated"] = diagnostics["matched_rows"] > len(selected)
    diagnostics["selection"] = "earliest chronological records within half-open UTC window"
    return selected, diagnostics


def ingest_village(source: Path | str, store: Any = None, *, start: str | datetime | None = None, end: str | datetime | None = None, limit: int = 2000, room: str | None = None, include_events: bool = False) -> dict:
    """Import a bounded UTC window from a directory or a chat JSONL file.

    ``store`` is an optional convenience hook: when it implements
    ``save_dataset(result)``, this function invokes it.  No store is needed for
    analysis. End is exclusive; limit applies independently to chat and events.
    """
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100000:
        raise ValueError("limit must be an integer between 1 and 100000")
    start_time, end_time = parse_time(start), parse_time(end)
    if start_time and end_time and start_time >= end_time:
        raise ValueError("start must precede end")
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"Dataset source does not exist: {source}")
    root = source if source.is_dir() else source.parent
    chat_path = _table(root, "chat_messages") if source.is_dir() else source
    if chat_path is None:
        raise FileNotFoundError(f"No chat_messages.jsonl(.gz) in {root}")
    agent_rows = _small_table(root, "agents")
    agents = {str(row["id"]): row for row in agent_rows if row.get("id")}
    messages, diagnostics = _bounded_rows(chat_path, start=start_time, end=end_time, limit=limit, room=room, agents=agents, kind="chat_messages")
    goals = []
    for table in ("village_goals", "agent_goals"):
        for goal in _small_table(root, table):
            left = parse_time(goal.get("start_time"))
            right = parse_time(goal.get("end_time"))
            if end_time and left and left >= end_time:
                continue
            if start_time and right and right <= start_time:
                continue
            goals.append({**goal, "goal_type": "village" if table == "village_goals" else "individual"})
    events, event_diagnostics = [], None
    if include_events:
        event_path = _table(root, "events")
        if event_path:
            events, event_diagnostics = _bounded_rows(event_path, start=start_time, end=end_time, limit=limit, room=room, agents=agents, kind="events")
    fingerprint = hashlib.sha256(json.dumps([{ "id": m["id"], "hash": m["content_hash"]} for m in messages], sort_keys=True).encode()).hexdigest()
    result = {
        "schema_version": "1.0",
        "source": str(source.resolve()),
        "scope": {"start": iso_time(start_time), "end_exclusive": iso_time(end_time), "limit": limit, "room": room},
        "messages": messages,
        "agents": agent_rows,
        "goals": goals,
        "events": events,
        "diagnostics": {"chat": diagnostics, "events": event_diagnostics},
        "fingerprint": fingerprint,
        "limitations": ["Chat statements are reported claims, not verified outcomes.", "Room visibility does not establish actual reading or causal influence.", "A row limit can right-censor later resolutions; imported scope is explicit."],
    }
    if store is not None and hasattr(store, "save_dataset"):
        store.save_dataset(result)
    return result
