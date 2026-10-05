"""Declared-reference graph fixtures establish neither delivery nor causality."""
import copy
import json
import unittest

from swarm_lab.event_evidence_graph import build_event_evidence_neighborhood as graph
from swarm_lab.store import fingerprint


def event(identity, kind, data, actor=None, task=None, recipients=None, **extra):
    row = {"id": identity, "kind": kind, "occurred_at": "2025-04-22T18:00:00Z", "data": data}
    if actor is not None: row["actor_id"] = actor
    if task is not None: row["task_id"] = task
    if recipients is not None: row["recipient_ids"] = recipients
    row.update(extra)
    return row


def record(events):
    payload = {"schema_version": "societylab.events.v1",
               "source": {"id": "unit-source", "name": "Authored graph fixture", "kind": "authored_example"},
               "run": {"id": "unit-run"}, "events": events}
    return {"id": "observability_run-unit", "version": 3, "kind": "observability_run",
            "hash": fingerprint(payload), "payload": payload}


def fixture():
    return record([
        event("register-a", "agent.registered", {"name": "A"}, actor="a"),
        event("register-b", "agent.registered", {"name": "B"}, actor="b"),
        event("task-root", "task.created", {"title": "Root task"}, task="root"),
        event("task-child", "task.created", {"title": "Child task"}, task="child", parent_task_id="root"),
        event("post", "message.sent", {"content": "A recorded post"}, actor="a", task="child", recipients=["b"]),
        event("reply", "message.sent", {"content": "Reply text", "reply_to_message_id": "post"}, actor="b", recipients=["a"]),
        event("call", "tool.called", {"call_id": "call-1", "tool_name": "read_file"}, actor="a", task="child"),
        event("return", "tool.returned", {"call_id": "call-1", "success": True}, actor="a", task="child"),
    ])


class EventEvidenceGraphTests(unittest.TestCase):
    def test_unique_typed_relations_and_original_field_provenance(self):
        source = fixture()
        result = graph(source, seed_event_id="post", hops=2)
        observed = {(e["source"], e["relation"], e["target"]) for e in result["edges"]}
        self.assertIn(("reply", "reply_reference", "post"), observed)
        self.assertIn(("task-child", "parent_task", "task-root"), observed)
        self.assertIn(("return", "tool_call_reference", "call"), observed)
        self.assertIn(("post", "addressed_recipient", "register-b"), observed)
        target = next(e for e in result["edges"] if e["source"] == "post" and e["relation"] == "addressed_recipient")
        self.assertEqual(target["provenance"]["field"], "recipient_ids[0]")
        node = next(n for n in result["nodes"] if n["id"] == "post")
        self.assertEqual(target["provenance"]["event_sha256"], node["source_event_sha256"])
        self.assertEqual(node["capture_position"], 5)
        self.assertEqual(result["source_ref"], {k: source[k] for k in ("id", "version", "hash")})
        self.assertFalse(result["scope"]["causal_graph"])

    def test_unknown_ambiguous_and_actor_conflicting_parents_are_not_edges(self):
        source = record([
            event("register-a1", "agent.registered", {"name": "A"}, actor="a"),
            event("register-a2", "agent.registered", {"name": "A again"}, actor="a"),
            event("call", "tool.called", {"call_id": "call-1", "tool_name": "read"}, actor="a"),
            event("return", "tool.returned", {"call_id": "call-1", "success": True}, actor="b", task="missing-task"),
            event("post", "message.sent", {"content": "Unknown parent", "reply_to_message_id": "missing-message"}, actor="a", recipients=["c"]),
        ])
        result = graph(source, seed_event_id="return", hops=2)
        self.assertEqual([n["id"] for n in result["nodes"]], ["return"])
        self.assertEqual(result["edges"], [])
        self.assertEqual(next(d for d in result["diagnostics"] if d["relation"] == "tool_call_reference")["status"], "actor_conflict")
        self.assertEqual(result["coverage"]["selected_reference_counts"]["unknown_in_captured_run"], 2)
        post = graph(source, seed_event_id="post")
        ambiguous = next(d for d in post["diagnostics"] if d["relation"] == "actor")
        self.assertEqual(ambiguous["candidate_count"], 2)
        self.assertEqual(ambiguous["candidate_event_ids"], ["register-a1", "register-a2"])
        self.assertEqual(ambiguous["status"], "ambiguous_reference")
        self.assertFalse(any(n["id"] == "missing-message" for n in post["nodes"]))

    def test_private_rationale_exports_no_content_or_communication_edges(self):
        source = record([
            event("register", "agent.registered", {"name": "A"}, actor="a"),
            event("local", "reasoning.recorded", {"content": "PRIVATE-RATIONALE-DO-NOT-EXPORT"}, actor="a", recipients=[]),
            event("private", "message.sent", {"content": "PRIVATE-CONTENT-DO-NOT-EXPORT", "visibility": "private"}, actor="a", recipients=[]),
        ])
        result = graph(source, seed_event_id="local", hops=2)
        serialized = json.dumps(result)
        self.assertNotIn("PRIVATE-RATIONALE", serialized)
        self.assertNotIn("PRIVATE-CONTENT", serialized)
        self.assertTrue(all(e["relation"] == "actor" for e in result["edges"]))
        self.assertFalse(result["scope"]["raw_content_exported"])
        self.assertEqual((result["scope"]["provider_calls"], result["scope"]["database_writes"]), (0, 0))

    def test_cycles_future_parent_and_repeated_execution_are_deterministic(self):
        source = record([
            event("first", "task.created", {"title": "First"}, task="a", parent_task_id="b"),
            event("second", "task.created", {"title": "Second"}, task="b", parent_task_id="a", occurred_at="2025-04-22T17:00:00Z"),
        ])
        before = copy.deepcopy(source)
        result = graph(source, seed_event_id="first", hops=2)
        self.assertEqual(result, graph(source, seed_event_id="first", hops=2))
        self.assertEqual(source, before)
        self.assertEqual(len(result["edges"]), 2)
        self.assertEqual([n["capture_position"] for n in result["nodes"]], [1, 2])
        self.assertEqual(result["nodes"][1]["occurred_at"], "2025-04-22T17:00:00Z")
        result["source_ref"]["version"] = 999
        self.assertEqual(source["version"], 3)

    def test_hops_and_display_caps_keep_missingness_and_counts_explicit(self):
        source = fixture()
        zero = graph(source, seed_event_id="post", hops=0)
        self.assertEqual(len(zero["nodes"]), 1)
        self.assertFalse(zero["truncated"])
        self.assertTrue(zero["coverage"]["additional_resolved_neighbors_beyond_requested_hops"])
        nodes = graph(source, seed_event_id="post", hops=2, max_nodes=1)
        self.assertEqual(len(nodes["nodes"]), 1)
        self.assertTrue(nodes["coverage"]["node_limit_reached"])
        edges = graph(source, seed_event_id="post", hops=2, max_edges=1)
        self.assertEqual(len(edges["edges"]), 1)
        self.assertGreater(edges["coverage"]["induced_edges_before_display_cap"], 1)
        self.assertTrue(edges["truncated"])
        unknown = record([event("post", "message.sent", {"content": "No declarations", "reply_to_message_id": "other"}, actor="a", recipients=["b"])])
        diagnostic = graph(unknown, seed_event_id="post", max_diagnostics=1)
        self.assertEqual(len(diagnostic["diagnostics"]), 1)
        self.assertEqual(diagnostic["coverage"]["selected_diagnostics_before_display_cap"], 3)
        self.assertEqual(diagnostic["coverage"]["selected_reference_counts"]["unknown_in_captured_run"], 3)

    def test_strict_typed_bounds_schema_and_unknown_seed_fail_closed(self):
        source = fixture()
        for key in ("hops", "max_nodes", "max_edges", "max_diagnostics"):
            for value in (True, 1.0, -1, None):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    graph(source, seed_event_id="post", **{key: value})
        for seed in ("unknown", "", True):
            with self.assertRaises(ValueError): graph(source, seed_event_id=seed)
        for mutate in (lambda r: r.update(version=True),
                       lambda r: r.update(version=9007199254740992),
                       lambda r: r.update(kind="dataset"),
                       lambda r: r["payload"]["events"].append(copy.deepcopy(r["payload"]["events"][0])),
                       lambda r: r["payload"]["events"][0].pop("occurred_at"),
                       lambda r: r["payload"].update(number=float("nan")),
                       lambda r: r["payload"].update(number=10**1000),
                       lambda r: r["payload"].update(too_long="x" * 16001)):
            bad = copy.deepcopy(source); mutate(bad); bad["hash"] = fingerprint(bad["payload"])
            with self.assertRaises(ValueError): graph(bad, seed_event_id="post")

    def test_payload_tamper_rejected_and_exact_historical_version_preserved(self):
        source = fixture()
        bad = copy.deepcopy(source); bad["payload"]["events"][4]["recipient_ids"] = ["a"]
        with self.assertRaisesRegex(ValueError, "fingerprint"): graph(bad, seed_event_id="post")
        older = copy.deepcopy(source); older["version"] = 1
        result = graph(older, seed_event_id="post")
        self.assertEqual(result["source_ref"]["version"], 1)
        self.assertNotEqual(result["source_ref"], graph(source, seed_event_id="post")["source_ref"])
        self.assertEqual(result["implementation_hashes"].keys(), {"event_evidence_graph.py", "observability_protocol.py", "store.py"})

    def test_aggregate_reference_work_bound_is_enforced_before_partial_result(self):
        source = record([event(f"post-{i}", "message.sent", {"content": "x"}, actor="a", recipients=[f"b{j}" for j in range(14)]) for i in range(1501)])
        with self.assertRaisesRegex(ValueError, "reference-check work bound"):
            graph(source, seed_event_id="post-0")


if __name__ == "__main__":
    unittest.main()
