"""Tests of scientific validity boundaries, not just detector implementation."""
import gzip
import json
import tempfile
import unittest
from pathlib import Path

from swarm_lab.dataset import ingest_village, normalize_message, parse_time
from swarm_lab.discovery import build_graph, case_evidence, detect_behaviors, discover_cases


def message(identity, agent, text, minute, *, room="main", second=0):
    return {"id": identity, "agent_speaker_id": agent, "speaker_type": "agent", "room_id": room, "content": text, "created_at": f"2025-04-02 10:{minute:02}:{second:02}"}


class DatasetTests(unittest.TestCase):
    def test_unsorted_gzip_selects_chronological_scope_not_source_order(self):
        rows = [message("later", "a", "later", 30), message("outside", "a", "outside", 1), message("earlier", "a", "earlier", 10), message("middle", "a", "middle", 20)]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "chat_messages.jsonl.gz"
            with gzip.open(source, "wt", encoding="utf-8") as stream:
                for row in rows:
                    stream.write(json.dumps(row) + "\n")
            imported = ingest_village(source, start="2025-04-02T10:05:00Z", end="2025-04-02T10:30:00Z", limit=1)
        self.assertEqual([row["id"] for row in imported["messages"]], ["earlier"])
        self.assertEqual(imported["diagnostics"]["chat"]["matched_rows"], 2)
        self.assertEqual(imported["diagnostics"]["chat"]["rows_scanned"], 4)
        self.assertTrue(imported["diagnostics"]["chat"]["truncated"])
        self.assertEqual(imported["messages"][0]["source"]["line"], 3)

    def test_subsecond_and_timezone_ordering(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "chat_messages.jsonl"
            rows = [message("fraction", "a", "one", 0), message("exact", "a", "two", 0)]
            rows[0]["created_at"] = "2025-04-02T10:00:00.100Z"
            rows[1]["created_at"] = "2025-04-02T15:30:00+05:30"
            source.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            data = ingest_village(source, limit=2)
        self.assertEqual([row["id"] for row in data["messages"]], ["exact", "fraction"])
        self.assertEqual(parse_time("2025-04-02T15:30:00+05:30"), parse_time("2025-04-02T10:00:00Z"))

    def test_malformed_rows_visible_and_humans_remain_humans(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "chat_messages.jsonl"
            row = {"id": "h1", "speaker_type": "user", "user_speaker_id": "human", "agent_speaker_id": "bad-agent-field", "created_at": "2025-04-02T10:00:00Z", "content": "approve"}
            source.write_text("bad json\n" + json.dumps(row) + "\n", encoding="utf-8")
            data = ingest_village(source)
        self.assertEqual(data["diagnostics"]["chat"]["malformed_rows"], 1)
        self.assertEqual(data["messages"][0]["speaker_type"], "user")
        self.assertIsNone(data["messages"][0]["agent_id"])
        self.assertEqual(data["messages"][0]["speaker_id"], "human")

    def test_invalid_scope_rejected(self):
        with self.assertRaises(ValueError):
            ingest_village("missing", start="2025-04-03", end="2025-04-02")
        with self.assertRaises(ValueError):
            ingest_village("missing", limit=0)


class DiscoveryTests(unittest.TestCase):
    def test_claims_are_not_verified_and_negation_is_screened(self):
        observations = detect_behaviors([message("a", "alice", "I have completed the deployment.", 0), message("b", "alice", "The deployment is not done.", 1), message("c", "bob", "Done.", 2)])
        self.assertIn("completion_report", observations[0]["labels"])
        self.assertNotIn("completion_report", observations[1]["labels"])
        self.assertIn("completion_report", observations[2]["labels"])
        self.assertEqual(observations[0]["interpretation"], "text_observation")

    def test_graph_marks_inference_and_preserves_mentions_as_mentions(self):
        rows = [message("a", "alice", "Bob, can you verify https://example.com/report?", 0), message("b", "bob", "The task is done.", 1)]
        graph = build_graph(rows, agents=[{"id": "alice", "name": "Alice"}, {"id": "bob", "name": "Bob"}])
        proximity = [edge for edge in graph["edges"] if edge["kind"] == "temporal_proximity"]
        mentions = [edge for edge in graph["edges"] if edge["kind"] == "mentions"]
        self.assertTrue(proximity[0]["inferred"])
        self.assertFalse(mentions[0]["inferred"])
        self.assertNotIn("causes", {edge["kind"] for edge in graph["edges"]})
        self.assertEqual(proximity[0]["evidence_ids_pair"], ["a", "b"])

    def test_private_rooms_do_not_create_proximity_edges(self):
        rows = [message("a", "alice", "Private plan", 0, room="private-a"), message("b", "bob", "Private plan", 1, room="private-b")]
        graph = build_graph(rows)
        self.assertFalse(any(edge["kind"] == "temporal_proximity" for edge in graph["edges"]))

    def test_commitment_blocker_censoring_and_related_completion(self):
        rows = [message("a", "alice", "I will upload the telescope calibration.", 0), message("b", "bob", "I am waiting for the telescope calibration.", 1)]
        result = discover_cases(rows)
        case = next(candidate for candidate in result["anomalies"] if candidate["kind"] == "commitment_with_later_blocker")
        self.assertTrue(case["right_censored"])
        self.assertEqual(case["causal_support"], "none")
        self.assertEqual(case["novelty"], "not_established")
        rows.append(message("c", "alice", "I have uploaded the telescope calibration.", 2))
        updated = discover_cases(rows)
        self.assertFalse(any(candidate["kind"] == "commitment_with_later_blocker" for candidate in updated["anomalies"]))

    def test_nonanomalous_comparisons_not_called_causal_controls(self):
        rows = [message("a", "alice", "I am blocked on the telescope.", 0), message("b", "bob", "Thanks, noted.", 1), message("c", "carol", "Understood.", 2), message("d", "alice", "We measured humidity with a calibrated sensor.", 45)]
        result = discover_cases(rows)
        self.assertTrue(result["controls"])
        self.assertEqual(result["controls"][0]["claim_type"], "observational_comparison")
        self.assertIn("Not randomized", result["controls"][0]["limitations"])

    def test_missing_evidence_and_invalid_classifier_fail_closed(self):
        rows = [message("a", "alice", "I will build it.", 0)]
        with self.assertRaises(ValueError):
            case_evidence({"evidence_ids": ["imagined-id"]}, rows)
        with self.assertRaises(ValueError):
            detect_behaviors(rows, backend=lambda m, d: {"deception": True})
        with self.assertRaises(ValueError):
            detect_behaviors(rows, backend=lambda m, d: {"commitment": 0.9})
        records = detect_behaviors(rows, backend=lambda m, d: {"commitment": None})
        self.assertIsNone(records[0]["additional_measurement"]["labels"]["commitment"])

    def test_timestamped_event_links_use_foreign_key_not_text(self):
        rows = [message("a", "alice", "Hello", 0)]
        graph = build_graph(rows, events=[{"id": "event1", "event_index": 4, "created_at": "2025-04-02T10:00:00Z", "data": {"actionType": "AGENT_TALK", "messageId": "a"}}])
        link = next(edge for edge in graph["edges"] if edge["kind"] == "records_message")
        self.assertFalse(link["inferred"])
        self.assertEqual(link["evidence_ids"], ["a", "event1"])


if __name__ == "__main__":
    unittest.main()
