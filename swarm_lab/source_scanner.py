"""Small bounded filesystem scanner; source records are inert data.

No model, network API, database, importer normalization, actor join, or payload
logging occurs here. A selected-ID or budget stop never proves global absence.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import math
import os
import zlib
from collections import Counter
from pathlib import Path


SOURCE_SCANNER_VERSION = "bounded-jsonl-source-scanner-v1"
TABLES = frozenset({"chat_messages", "events", "computer_use_sessions", "computer_use_turns"})
MAX_ROWS = 15000
MAX_COMPRESSED_BYTES = 64 * 1024**2
MAX_EXPANDED_BYTES = 128 * 1024**2
MAX_ROW_BYTES = 1024**2
MAX_RETAINED_BYTES = 8 * 1024**2
MAX_METADATA_BYTES = 64 * 1024
MAX_JSON_DEPTH = 16
MAX_ROW_JSON_ITEMS = 16384
MAX_RETAINED_JSON_ITEMS = 131072
READ_CHUNK_BYTES = 4096


def resolve_source_path(path):
    """WinFsp can read/stat a file while rejecting GetFinalPathNameByHandle.

    The narrow ERROR_UNRECOGNIZED_VOLUME fallback is a syntactic absolute path,
    explicitly declared in provenance. All other resolution errors propagate.
    This does not authenticate reparse targets or a mounted object's identity.
    """
    try:
        return Path(path).resolve(strict=True), 'filesystem_resolved'
    except OSError as exc:
        if getattr(exc, 'winerror', None) != 1005:
            raise
        return Path(os.path.abspath(path)), 'lexical_absolute_virtual_filesystem'


class _ScanStop(Exception):
    def __init__(self, reason):
        self.reason = reason


class _DuplicateKey(ValueError):
    pass


class _NonfiniteJSON(ValueError):
    pass


class _JSONShape(ValueError):
    pass


def _encoder():
    return json.JSONEncoder(sort_keys=True, ensure_ascii=False,
                            separators=(",", ":"), allow_nan=False)


def _hash_record(record):
    digest = hashlib.sha256()
    for chunk in _encoder().iterencode(record):
        digest.update(chunk.encode("utf-8"))
    return digest.hexdigest()


def _json_size(value):
    return sum(len(chunk.encode("utf-8")) for chunk in _encoder().iterencode(value))


def _object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey("Ambiguous duplicate JSON object key")
        result[key] = value
    return result


def _nonfinite_constant(value):
    raise _NonfiniteJSON("Nonfinite JSON constant")


def _validate_shape(value, *, max_depth=MAX_JSON_DEPTH, max_items=MAX_ROW_JSON_ITEMS,
                    max_string=MAX_ROW_BYTES):
    """Bound depth/items before hashing/copying. No source value is executed."""
    count = 0
    ancestors = set()

    def visit(item, depth):
        nonlocal count
        count += 1
        if count > max_items or depth > max_depth:
            raise _JSONShape("JSON structure bound exceeded")
        if item is None or type(item) is bool:
            return
        if type(item) is str:
            if len(item) > max_string:
                raise _JSONShape("JSON string bound exceeded")
            # UTF-8 encoding later must not fail on JSON escaped lone surrogates.
            try:
                item.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise _JSONShape("Invalid Unicode scalar") from exc
            return
        if type(item) is int:
            if item.bit_length() > 256:
                raise _JSONShape("JSON integer bound exceeded")
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise _NonfiniteJSON("Nonfinite JSON number")
            return
        if type(item) not in (list, dict):
            raise _JSONShape("JSON values required")
        if id(item) in ancestors:
            raise _JSONShape("Cyclic metadata")
        ancestors.add(id(item))
        if type(item) is dict:
            for key, child in item.items():
                if type(key) is not str:
                    raise _JSONShape("JSON object keys must be strings")
                visit(key, depth + 1)
                visit(child, depth + 1)
        else:
            for child in item:
                visit(child, depth + 1)
        ancestors.remove(id(item))

    visit(value, 0)
    return count


def _positive_bound(value, name, ceiling):
    if type(value) is not int or not 1 <= value <= ceiling:
        raise ValueError(f"{name} must be a positive integer at most {ceiling}")


class _BoundedPhysicalReader:
    """Unbuffered file reads; reaching a cap raises rather than fabricating EOF."""
    def __init__(self, handle, limit):
        self.handle = handle
        self.limit = limit
        self.bytes_read = 0
        self.eof_observed = False
        self.digest = hashlib.sha256()

    def read(self, size=-1):
        remaining = self.limit - self.bytes_read
        if remaining <= 0:
            raise _ScanStop("compressed_byte_limit")
        # Never pass an unbounded/oversized read to the underlying filesystem.
        request = min(READ_CHUNK_BYTES, remaining,
                      size if type(size) is int and size >= 0 else READ_CHUNK_BYTES)
        if request == 0:
            return b""
        data = self.handle.read(request)
        if not data:
            self.eof_observed = True
            return b""
        self.bytes_read += len(data)
        self.digest.update(data)
        return data

    def read1(self, size=-1):
        return self.read(size)


class _BoundedLines:
    def __init__(self, decoded, physical, expanded_limit, row_limit):
        self.decoded = decoded
        self.physical = physical
        self.expanded_limit = expanded_limit
        self.row_limit = row_limit
        self.expanded_bytes = 0
        self.buffer = bytearray()
        self.decoder_eof = False

    def next_line(self):
        while True:
            newline = self.buffer.find(b"\n")
            if newline >= 0:
                end = newline + 1
                if end > self.row_limit:
                    raise _ScanStop("row_byte_limit")
                result = bytes(self.buffer[:end])
                del self.buffer[:end]
                return result
            if self.decoder_eof:
                if self.buffer:
                    result = bytes(self.buffer)
                    self.buffer.clear()
                    return result
                return None
            if len(self.buffer) >= self.row_limit:
                # No extra-byte probe outside the row cap, even at possible EOF.
                raise _ScanStop("row_byte_limit")
            remaining = self.expanded_limit - self.expanded_bytes
            if remaining <= 0:
                raise _ScanStop("expanded_byte_limit")
            request = min(READ_CHUNK_BYTES, remaining, self.row_limit - len(self.buffer))
            data = self.decoded.read1(request)
            if not data:
                if not self.physical.eof_observed:
                    raise _ScanStop("unverified_decoder_eof")
                self.decoder_eof = True
            else:
                self.expanded_bytes += len(data)
                self.buffer.extend(data)


def scan_jsonl_source(
    path, *, table, max_rows=64, max_compressed_bytes=2 * 1024**2,
    max_expanded_bytes=8 * 1024**2, max_row_bytes=1024**2,
    select_ids=None, stop_when_all_ids_found=False, source_metadata=None,
):
    """Scan raw JSONL with truthful partial coverage and source-line hashes.

    max_rows counts complete physical rows, including filtered or invalid rows.
    Expanded bytes count data delivered by the decoder, including at most one
    small pending buffer beyond the last parsed row. No timestamp early stop.
    """
    if type(table) is not str or table not in TABLES:
        raise ValueError("Unsupported source table; use the exact exported table name")
    for value, name, ceiling in (
        (max_rows, "max_rows", MAX_ROWS),
        (max_compressed_bytes, "max_compressed_bytes", MAX_COMPRESSED_BYTES),
        (max_expanded_bytes, "max_expanded_bytes", MAX_EXPANDED_BYTES),
        (max_row_bytes, "max_row_bytes", MAX_ROW_BYTES),
    ):
        _positive_bound(value, name, ceiling)
    if type(stop_when_all_ids_found) is not bool:
        raise ValueError("stop_when_all_ids_found must be a boolean")
    if select_ids is None:
        selected = None
        duplicate_requests = []
    else:
        if not isinstance(select_ids, (list, tuple, set, frozenset)) or len(select_ids) > MAX_ROWS:
            raise ValueError("select_ids must be a bounded collection of exact string IDs")
        if any(type(identity) is not str or not identity or len(identity) > 256
               for identity in select_ids):
            raise ValueError("select_ids requires nonempty bounded string IDs")
        try:
            for identity in select_ids:
                identity.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError("select_ids requires valid Unicode scalar strings") from exc
        selected = set(select_ids)
        duplicate_requests = sorted(identity for identity, count in Counter(select_ids).items() if count > 1)
    if stop_when_all_ids_found and (selected is None or not selected):
        raise ValueError("Explicit early stopping requires a nonempty select_ids filter")
    _validate_shape(source_metadata, max_depth=8, max_items=1024, max_string=4096)
    if _json_size(source_metadata) > MAX_METADATA_BYTES:
        raise ValueError("Source metadata declaration exceeds byte bound")
    if not isinstance(path, (str, Path)):
        raise ValueError("path must be a filesystem path")
    source_path, path_resolution = resolve_source_path(path)
    if not source_path.is_file():
        raise ValueError("path must name an ordinary existing file")
    if len(str(source_path)) > 4096:
        raise ValueError("Source path length bound exceeded")
    try:
        str(source_path).encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("Source path must use valid Unicode scalar strings") from exc
    filename = source_path.name.lower()
    if filename.endswith(".jsonl.gz"):
        compressed = True
    elif filename.endswith(".jsonl"):
        compressed = False
    else:
        raise ValueError("Source must be .jsonl or .jsonl.gz")
    observed_size = source_path.stat().st_size
    counters = {
        "physical_rows_seen": 0, "parsed_rows": 0, "retained_rows": 0,
        "filtered_rows": 0, "malformed_rows": 0, "duplicate_ids": 0,
        "retained_bytes": 0, "retained_json_items": 0,
    }
    records, problems, seen, found = [], [], set(), set()
    stop_reason, complete = "not_started", False
    operational_error = None
    physical = None
    lines = None
    raw_line = None

    def problem(reason, *, line=None, error_type=None):
        nonlocal stop_reason, operational_error
        stop_reason = reason
        detail = {"kind": reason, "line": line}
        if raw_line is not None:
            detail["raw_line_sha256"] = hashlib.sha256(raw_line).hexdigest()
        if error_type:
            detail["error_type"] = error_type
        problems.append(detail)
        operational_error = {"kind": reason, "stage": "read_or_parse", "line": line,
                             "error_type": error_type}

    try:
        # buffering=0 prevents Python's file layer from reading beyond the cap.
        with source_path.open("rb", buffering=0) as handle:
            physical = _BoundedPhysicalReader(handle, max_compressed_bytes)
            decoded = gzip.GzipFile(fileobj=physical, mode="rb") if compressed else physical
            try:
                lines = _BoundedLines(decoded, physical, max_expanded_bytes, max_row_bytes)
                while counters["physical_rows_seen"] < max_rows:
                    raw_line = None
                    raw_line = lines.next_line()
                    if raw_line is None:
                        if compressed and physical.bytes_read == 0:
                            problem("invalid_gzip_header", error_type="EmptyGzipSource")
                        else:
                            stop_reason, complete = "eof", True
                        break
                    counters["physical_rows_seen"] += 1
                    line_number = counters["physical_rows_seen"]
                    try:
                        text = raw_line.decode("utf-8-sig" if line_number == 1 else "utf-8")
                        record = json.loads(text, object_pairs_hook=_object_pairs,
                                            parse_constant=_nonfinite_constant)
                        items = _validate_shape(record)
                        if type(record) is not dict or type(record.get("id")) is not str or (
                                not record["id"] or len(record["id"]) > 256):
                            raise _JSONShape("Original bounded string record ID required")
                    except UnicodeDecodeError:
                        counters["malformed_rows"] += 1
                        problem("invalid_utf8", line=line_number, error_type="UnicodeDecodeError")
                        break
                    except _DuplicateKey:
                        counters["malformed_rows"] += 1
                        problem("duplicate_json_key", line=line_number, error_type="DuplicateJSONObjectKey")
                        break
                    except _NonfiniteJSON:
                        counters["malformed_rows"] += 1
                        problem("nonfinite_json", line=line_number, error_type="NonfiniteJSON")
                        break
                    except (_JSONShape, RecursionError):
                        counters["malformed_rows"] += 1
                        problem("invalid_record_structure", line=line_number, error_type="JSONStructureLimitOrInvalidID")
                        break
                    except (json.JSONDecodeError, ValueError):
                        counters["malformed_rows"] += 1
                        problem("malformed_json", line=line_number, error_type="JSONDecodeError")
                        break
                    counters["parsed_rows"] += 1
                    identity = record["id"]
                    if identity in seen:
                        counters["duplicate_ids"] += 1
                        problem("duplicate_record_id", line=line_number, error_type="DuplicateRecordID")
                        break
                    seen.add(identity)
                    if selected is not None and identity not in selected:
                        counters["filtered_rows"] += 1
                        continue
                    entry = {
                        "record": record,
                        "source": {
                            "path": str(source_path), "table": table, "line": line_number,
                            "raw_line_sha256": hashlib.sha256(raw_line).hexdigest(),
                            "record_sha256": _hash_record(record),
                        },
                    }
                    # Count the full entry before appending; no payload copy/dump.
                    entry_bytes = _json_size(entry) + 64
                    if counters["retained_bytes"] + entry_bytes > MAX_RETAINED_BYTES:
                        problem("retained_byte_limit", line=line_number)
                        break
                    if counters["retained_json_items"] + items > MAX_RETAINED_JSON_ITEMS:
                        problem("retained_structure_limit", line=line_number)
                        break
                    counters["retained_bytes"] += entry_bytes
                    counters["retained_json_items"] += items
                    counters["retained_rows"] += 1
                    records.append(entry)
                    found.add(identity)
                    if stop_when_all_ids_found and found >= selected:
                        stop_reason = "selected_ids_found"
                        break
                else:
                    # Last unterminated row may already have required actual EOF.
                    if lines.decoder_eof and not lines.buffer:
                        stop_reason, complete = "eof", True
                    else:
                        stop_reason = "row_limit"
            finally:
                if compressed:
                    decoded.close()
    except _ScanStop as exc:
        problem(exc.reason, line=counters["physical_rows_seen"] + 1)
    except gzip.BadGzipFile:
        problem("corrupt_gzip", line=counters["physical_rows_seen"] + 1, error_type="BadGzipFile")
    except EOFError:
        problem("truncated_gzip", line=counters["physical_rows_seen"] + 1, error_type="EOFError")
    except zlib.error:
        problem("corrupt_gzip", line=counters["physical_rows_seen"] + 1, error_type="ZlibError")
    except OSError as exc:
        problem("io_error", line=counters["physical_rows_seen"] + 1, error_type=type(exc).__name__)

    source_eof = bool(physical and physical.eof_observed and lines and lines.decoder_eof)
    if complete and not source_eof:
        complete = False
        problem("unverified_eof")
    return {
        "schema_version": "1.0", "instrument_version": SOURCE_SCANNER_VERSION,
        "kind": "bounded_jsonl_source_scan", "table": table, "source_path": str(source_path),
        "read_only": True, "model_calls": 0, "records": records,
        "selection": {"select_ids": sorted(selected) if selected is not None else None,
                      "duplicate_requested_ids": duplicate_requests,
                      "stop_when_all_ids_found": stop_when_all_ids_found},
        "source_metadata_declaration": {"value": copy.deepcopy(source_metadata), "verified": False,
                                       "purpose": "Provided server MD5/size/generation metadata is an unverified declaration, not whole-object byte attestation."},
        "observed_source": {
            "path_resolution": path_resolution,
            "file_size_at_start": observed_size, "format": "gzip_jsonl" if compressed else "jsonl",
            "physical_prefix_sha256": physical.digest.hexdigest() if physical else None,
            "hash_scope": "Bytes actually returned by bounded unbuffered filesystem reads; may include small read-ahead beyond parsed rows.",
        },
        "limits": {
            "max_rows": max_rows, "max_compressed_bytes": max_compressed_bytes,
            "max_expanded_bytes": max_expanded_bytes, "max_row_bytes": max_row_bytes,
            "max_retained_bytes": MAX_RETAINED_BYTES, "max_json_depth": MAX_JSON_DEPTH,
            "max_row_json_items": MAX_ROW_JSON_ITEMS, "max_retained_json_items": MAX_RETAINED_JSON_ITEMS,
            "max_metadata_bytes": MAX_METADATA_BYTES, "max_filesystem_read_request": READ_CHUNK_BYTES,
        },
        "coverage": {
            **counters, "complete_scan": complete, "stop_reason": stop_reason,
            "source_eof_observed": source_eof,
            "compressed_bytes_read": physical.bytes_read if physical else 0,
            "expanded_bytes_read": lines.expanded_bytes if lines else 0,
            "pending_expanded_bytes": len(lines.buffer) if lines else 0,
            "missing_selected_ids": sorted(selected - found) if selected is not None else [],
            "missing_ids_scope": "Absent from retained/scanned scope only; global absence requires validated complete coverage.",
            "scanned_file_id_uniqueness_verified": complete,
            "global_database_id_uniqueness_verified": False,
            "physical_row_count_policy": "Complete physical row buffers, including filtered/invalid rows; an interrupted current row appears in diagnostics.",
        },
        "problems": problems, "operational_error": operational_error,
        "limitations": [
            "Physical row order is preserved; no timestamp early-stop or provider-schema normalization.",
            "A budget/selection/error stop is incomplete even if all desired IDs were found.",
            "Source metadata and raw payloads remain inert; no instructions are executed.",
            "No actor/session/recipient/semantic join, tool-success decision or causal claim is produced.",
            "Mounted filesystem prefetch may exceed logical reader bytes; remote wire traffic is not measured.",
        ],
    }
