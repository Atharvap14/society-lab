"""Independent byte/provenance attacks on the bounded source workflow.

Only synthetic temporary JSONL and an in-memory registry are used.  Expected
scientific boundaries are checked directly rather than borrowing saved verdicts.
"""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

from swarm_lab.source_workflow import (derive_source_links, normalize_source_plan,
    replay_source_links, scan_source_links)
from swarm_lab.source_scanner import scan_jsonl_source
from swarm_lab.store import clean, fingerprint


def identity(number):
    return str(uuid.UUID(int=number))


def canonical_sha(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def write_rows(path, rows, *, spaced=False):
    separators = (", ", ": ") if spaced else (",", ":")
    path.write_bytes(b"".join((json.dumps(row, sort_keys=not spaced, separators=separators,
                        ensure_ascii=False) + "\n").encode() for row in rows))


class MemoryStore:
    """Use production redaction/hash semantics, without opening a database."""
    def __init__(self):
        self.objects = {}
        self.puts = []
        self.gets = []
        self.put("behavior", {"status": "candidate"}, "protected-behavior")
        self.put("theory", {"status": "unestablished"}, "protected-theory")
        self.puts.clear()

    def put(self, kind, payload, object_id=None):
        key = object_id or kind + "-" + str(len(self.objects) + 1)
        versions = self.objects.setdefault(key, [])
        record = {"id": key, "kind": kind, "version": len(versions) + 1,
                  "payload": clean(copy.deepcopy(payload))}
        record["hash"] = fingerprint(record["payload"])
        versions.append(record)
        self.puts.append(kind)
        return copy.deepcopy(record)

    def get(self, key, version=None):
        self.gets.append((key, version))
        return copy.deepcopy(self.objects[key][-1 if version is None else version - 1])

    def reserve_call(self, *args, **kwargs):
        raise AssertionError("Source lineage must not reserve a model call")

    def trace(self, *args, **kwargs):
        raise AssertionError("Source lineage must not write research role traces")


def fixture(directory):
    agent, room, message, session = (identity(i) for i in range(1, 5))
    markers = {"chat": "PRIVATE_CHAT_ONLY_MARKER", "provider": "PROVIDER_PAYLOAD_ONLY_MARKER",
               "tool": "TOOL_PASSWORD_ONLY_MARKER", "output": "TOOL_OUTPUT_ONLY_MARKER",
               "token": "hf_SYNTHETIC_ONLY_TOKEN_0123456789012345"}
    content = markers["chat"] + " " + markers["token"]
    stamp = "2025-04-01T00:00:00Z"
    rows = {
        "events": [
            {"id": identity(11), "created_at": stamp, "event_index": 1,
             "data": {"actionType": "AGENT_TALK", "speakerId": agent, "roomId": room,
                      "messageId": message, "chatMessageId": message, "content": content,
                      "output": {"provider": markers["provider"]}}},
            {"id": identity(12), "created_at": stamp, "event_index": 2,
             "data": {"actionType": "START_USING_COMPUTER", "agentId": agent,
                      "computerUseSessionId": session, "sessionGoal": "Synthetic goal"}},
            {"id": identity(13), "created_at": stamp, "event_index": 3,
             "data": {"actionType": "STOP_USING_COMPUTER", "agentId": agent,
                      "computerUseSessionId": session, "summary": markers["provider"]}},
        ],
        "chat_messages": [{"id": message, "created_at": stamp, "agent_speaker_id": agent,
                           "room_id": room, "speaker_type": "agent", "content": content}],
        "computer_use_sessions": [{"id": session, "created_at": stamp, "agent_id": agent,
                                    "session_goal": "Synthetic goal"}],
        "computer_use_turns": [{"id": identity(14), "created_at": stamp, "agent_id": agent,
              "session_id": session, "agent_action": {"action": "type", "text": markers["tool"]},
              "output": markers["output"], "error": None,
              "agent_messages": [{"role": "assistant", "content": markers["provider"]}]}],
    }
    sources = {}
    for table, items in rows.items():
        path = directory / (table + ".jsonl")
        write_rows(path, items)
        sources[table] = {"path": str(path), "max_rows": 16, "max_compressed_bytes": 65536,
                          "max_expanded_bytes": 65536, "max_row_bytes": 16384,
                          "source_metadata": {"source_uri": "gs://synthetic-bucket/" + table + ".jsonl",
                                              "generation": "123", "object_bytes": path.stat().st_size}}
    return SimpleNamespace(store=MemoryStore()), sources, rows, markers


class SourceWorkflowIndependentTests(unittest.TestCase):
    def test_four_table_emission_and_session_lineage_retains_only_pins(self):
        with tempfile.TemporaryDirectory() as folder:
            lab, sources, rows, markers = fixture(Path(folder))
            protected = {k: copy.deepcopy(v) for k, v in lab.store.objects.items()}
            audit = scan_source_links(lab, sources)
            payload = audit["payload"]
            self.assertEqual(payload["model_calls"], 0)
            self.assertIs(payload["raw_records_persisted"], False)
            encoded = json.dumps(payload)
            for marker in markers.values():
                self.assertNotIn(marker, encoded)
            self.assertNotIn("REDACTED_CREDENTIAL", encoded)
            self.assertTrue(all("records" not in packet for packet in payload["source_readset"].values()))
            relations = payload["source_link_audit"]["relations"]
            self.assertEqual({r["relation_kind"]: r["status"] for r in relations}, {
                "event_message_fk": "verified_platform_emission_record", "start_session_fk": "verified_exported_fk",
                "stop_session_fk": "verified_exported_fk", "turn_session_fk": "verified_exported_fk"})
            talk = next(r for r in relations if r["relation_kind"] == "event_message_fk")
            self.assertIn(("speakerId", "agent_speaker_id", "matching"),
                          [(c["child_field"], c["parent_field"], c["status"]) for c in talk["field_checks"]])
            for relation in relations:
                self.assertEqual((relation["receipt"], relation["consumption"], relation["causal_influence"]),
                                 ("unestablished", "unestablished", "unestablished"))
            verdict = replay_source_links(lab, audit["id"], version=1)["payload"]
            self.assertTrue(verdict["passed"], verdict)
            self.assertTrue(verdict["filesystem_reread_attempted"])
            self.assertTrue(verdict["filesystem_reread_completed"])
            self.assertEqual(verdict["audit_ref"]["hash"], audit["hash"])
            self.assertEqual(lab.store.puts, ["source_link_audit", "verification"])
            for key, value in protected.items():
                self.assertEqual(lab.store.objects[key], value)

    def test_resealed_result_cannot_replace_fresh_source_reconstruction(self):
        for mutation in ("false_relation", "bool_zero_calls"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                lab, sources, _, _ = fixture(Path(folder))
                audit = scan_source_links(lab, sources)
                payload = copy.deepcopy(audit["payload"])
                if mutation == "false_relation":
                    payload["source_link_audit"]["relations"][0]["receipt"] = "verified"
                else:
                    payload["model_calls"] = False
                resealed = lab.store.put("source_link_audit", payload, audit["id"])
                self.assertNotEqual(resealed["hash"], audit["hash"])
                verdict = replay_source_links(lab, audit["id"], version=2)["payload"]
                self.assertFalse(verdict["passed"])
                self.assertTrue(verdict["filesystem_reread_completed"])
                self.assertEqual(verdict["reason"], "source_or_derivation_mismatch")

    def test_exact_old_version_replay_does_not_read_latest_version(self):
        with tempfile.TemporaryDirectory() as folder:
            lab, sources, _, _ = fixture(Path(folder))
            old = scan_source_links(lab, sources)
            changed = copy.deepcopy(old["payload"])
            changed["raw_records_persisted"] = True
            latest = lab.store.put("source_link_audit", changed, old["id"])
            verdict = replay_source_links(lab, old["id"], version=1)["payload"]
            self.assertTrue(verdict["passed"])
            self.assertEqual(verdict["audit_ref"], {k: old[k] for k in ("id", "version", "hash")})
            self.assertEqual(lab.store.gets[-1], (old["id"], 1))
            self.assertNotEqual(verdict["audit_ref"]["hash"], latest["hash"])
            for version in (True, 1.0, 0, -1):
                before = list(lab.store.gets)
                with self.subTest(version=version), self.assertRaises(ValueError):
                    replay_source_links(lab, old["id"], version=version)
                self.assertEqual(lab.store.gets, before)

    def test_same_canonical_row_different_whitespace_is_a_file_byte_change(self):
        with tempfile.TemporaryDirectory() as folder:
            lab, sources, rows, _ = fixture(Path(folder))
            table = "chat_messages"
            expected = {"table": table, "id": rows[table][0]["id"], "record_sha256": canonical_sha(rows[table][0])}
            audit = scan_source_links(lab, sources, expected_rows=[expected])
            prior = audit["payload"]["source_link_audit"]["rows"][table][0]["source"]
            write_rows(Path(sources[table]["path"]), rows[table], spaced=True)
            rebuilt = derive_source_links(audit["payload"]["plan"])
            actual = rebuilt["source_link_audit"]["rows"][table][0]["source"]
            self.assertEqual(actual["record_sha256"], prior["record_sha256"])
            self.assertNotEqual(actual["raw_line_sha256"], prior["raw_line_sha256"])
            verdict = replay_source_links(lab, audit["id"])["payload"]
            self.assertFalse(verdict["passed"])
            self.assertTrue(verdict["filesystem_reread_completed"])
            self.assertEqual(verdict["reason"], "source_or_derivation_mismatch")

    def test_expected_row_mismatch_distinguishes_attempt_from_completed_reread(self):
        with tempfile.TemporaryDirectory() as folder:
            lab, sources, rows, _ = fixture(Path(folder))
            table = "chat_messages"
            expected = {"table": table, "id": rows[table][0]["id"], "record_sha256": canonical_sha(rows[table][0])}
            audit = scan_source_links(lab, sources, expected_rows=[expected])
            rows[table][0]["content"] = "Changed original source row"
            write_rows(Path(sources[table]["path"]), rows[table])
            with patch("swarm_lab.source_scanner.scan_jsonl_source", wraps=scan_jsonl_source) as scanner:
                verdict = replay_source_links(lab, audit["id"])["payload"]
            self.assertEqual(scanner.call_count, 4)
            self.assertTrue(verdict["filesystem_reread_attempted"])
            self.assertFalse(verdict["filesystem_reread_completed"])
            self.assertFalse(verdict["passed"])
            self.assertEqual(verdict["reason"], "filesystem_reread_unavailable_or_invalid")
            self.assertNotIn("Changed original source row", json.dumps(verdict))

    def test_implementation_or_plan_hash_mismatch_avoids_source_reread(self):
        for mutation in ("implementation", "plan"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                lab, sources, _, _ = fixture(Path(folder))
                audit = scan_source_links(lab, sources)
                payload = copy.deepcopy(audit["payload"])
                if mutation == "implementation":
                    payload["implementation_hashes"]["source_links.py"] = "0" * 64
                else:
                    payload["plan"]["sources"]["events"]["max_rows"] += 1
                changed = lab.store.put("source_link_audit", payload, audit["id"])
                with patch("swarm_lab.source_workflow.derive_source_links", side_effect=AssertionError("Must not read")) as derive:
                    verdict = replay_source_links(lab, audit["id"], version=changed["version"])["payload"]
                derive.assert_not_called()
                self.assertFalse(verdict["filesystem_reread_attempted"])
                self.assertFalse(verdict["filesystem_reread_completed"])
                self.assertFalse(verdict["passed"])
                self.assertEqual(verdict["reason"], "implementation_hash_mismatch" if mutation == "implementation" else "scan_plan_hash_mismatch")

    def test_missing_file_does_not_turn_old_saved_coverage_into_new_verification(self):
        with tempfile.TemporaryDirectory() as folder:
            lab, sources, _, _ = fixture(Path(folder))
            audit = scan_source_links(lab, sources)
            Path(sources["computer_use_turns"]["path"]).unlink()
            with patch("swarm_lab.source_scanner.scan_jsonl_source", side_effect=AssertionError("Validate all paths first")) as scanner:
                verdict = replay_source_links(lab, audit["id"])["payload"]
            scanner.assert_not_called()
            self.assertFalse(verdict["passed"])
            self.assertTrue(verdict["filesystem_reread_attempted"])
            self.assertFalse(verdict["filesystem_reread_completed"])
            self.assertEqual(verdict["error_type"], "FileNotFoundError")

    def test_bounded_missing_parent_and_unscanned_parent_never_imply_global_absence(self):
        with tempfile.TemporaryDirectory() as folder:
            lab, sources, rows, _ = fixture(Path(folder))
            chat = rows["chat_messages"][0]
            rows["chat_messages"] = [{**chat, "id": identity(80)}, chat]
            write_rows(Path(sources["chat_messages"]["path"]), rows["chat_messages"])
            sources["chat_messages"]["max_rows"] = 1
            audit = scan_source_links(lab, sources)["payload"]
            link = next(r for r in audit["source_link_audit"]["relations"] if r["relation_kind"] == "event_message_fk")
            self.assertEqual(link["status"], "missing_parent_in_scanned_scope")
            self.assertIs(link["parent_scan_complete"], False)
            self.assertEqual(audit["source_readset"]["chat_messages"]["coverage"]["stop_reason"], "row_limit")
            self.assertEqual(audit["source_link_audit"]["global_source_completeness"], "unverified")
            verdict = replay_source_links(lab, lab.store.put("source_link_audit", audit)["id"])["payload"]
            self.assertTrue(verdict["passed"])
            del sources["chat_messages"]
            omitted = scan_source_links(lab, sources)["payload"]["source_link_audit"]
            link = next(r for r in omitted["relations"] if r["relation_kind"] == "event_message_fk")
            self.assertEqual(link["status"], "unscanned_parent")
            self.assertIsNone(link["parent_scan_complete"])
            self.assertEqual(link["global_parent_uniqueness"], "unverified")

    def test_explicit_id_early_stop_can_be_repeatable_without_complete_coverage(self):
        with tempfile.TemporaryDirectory() as folder:
            lab, sources, rows, _ = fixture(Path(folder))
            source = sources["chat_messages"]
            source.update(select_ids=[rows["chat_messages"][0]["id"]], stop_when_all_ids_found=True)
            audit = scan_source_links(lab, sources)
            coverage = audit["payload"]["source_readset"]["chat_messages"]["coverage"]
            self.assertEqual(coverage["stop_reason"], "selected_ids_found")
            self.assertIs(coverage["complete_scan"], False)
            self.assertEqual(coverage["missing_selected_ids"], [])
            self.assertTrue(replay_source_links(lab, audit["id"])["payload"]["passed"])

    def test_typed_bounds_and_unknown_metadata_reject_before_scanning_or_persistence(self):
        from swarm_lab.source_scanner import MAX_COMPRESSED_BYTES, MAX_EXPANDED_BYTES, MAX_ROW_BYTES, MAX_ROWS
        mutations = [(key, value) for key, limit in (("max_rows", MAX_ROWS), ("max_compressed_bytes", MAX_COMPRESSED_BYTES),
                     ("max_expanded_bytes", MAX_EXPANDED_BYTES), ("max_row_bytes", MAX_ROW_BYTES))
                     for value in (True, 1.0, 0, -1, limit + 1)]
        mutations += [("stop_when_all_ids_found", 1), ("select_ids", [identity(4), identity(4)]),
                      ("unexpected_option", "ignored"), ("source_metadata", {"password": "SYNTHETIC_ONLY"}),
                      ("source_metadata", {"object_bytes": True}), ("source_metadata", {"generation": 123})]
        with tempfile.TemporaryDirectory() as folder:
            lab, sources, _, _ = fixture(Path(folder))
            for key, value in mutations:
                with self.subTest(key=key, value=value):
                    modified = copy.deepcopy(sources)
                    modified["events"][key] = value
                    with patch("swarm_lab.source_scanner.scan_jsonl_source", side_effect=AssertionError("Invalid plan must not scan")) as scanner:
                        with self.assertRaises(ValueError):
                            scan_source_links(lab, modified)
                    scanner.assert_not_called()
                    self.assertEqual(lab.store.puts, [])

    def test_credential_shaped_plan_paths_or_metadata_cannot_be_silently_redacted(self):
        with tempfile.TemporaryDirectory() as folder:
            lab, sources, rows, _ = fixture(Path(folder))
            token = "hf_SYNTHETIC_ONLY_TOKEN_0123456789012345"
            bad_uris = ("gs://synthetic-bucket/file?access_token=SYNTHETIC_ONLY",
                        "gs://user:SYNTHETIC_ONLY@synthetic-bucket/file", "gs://synthetic-bucket/file#secret",
                        "gs://synthetic-bucket/" + token)
            for uri in bad_uris:
                with self.subTest(uri=uri):
                    modified = copy.deepcopy(sources)
                    modified["events"]["source_metadata"]["source_uri"] = uri
                    with patch("swarm_lab.source_scanner.scan_jsonl_source", side_effect=AssertionError("Credential plan must not scan")) as scanner:
                        with self.assertRaises(ValueError):
                            scan_source_links(lab, modified)
                    scanner.assert_not_called()
            private_path = Path(folder) / (token + ".jsonl")
            write_rows(private_path, rows["events"])
            modified = copy.deepcopy(sources)
            modified["events"]["path"] = str(private_path)
            with self.assertRaisesRegex(ValueError, "credential-shaped"):
                normalize_source_plan(modified)
            self.assertEqual(lab.store.puts, [])


if __name__ == "__main__":
    unittest.main()
