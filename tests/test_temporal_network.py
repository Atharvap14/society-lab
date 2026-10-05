"""Contract tests for the bounded temporal reference instrument."""
from __future__ import annotations

import copy
import hashlib
import json
import random
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from swarm_lab.dataset import normalize_message, parse_time
from swarm_lab.mention_sensitivity import normalize_shadow_text
from swarm_lab import temporal_network as temporal


ROSTER = [
    {"id": "a", "name": "Alice"},
    {"id": "b", "name": "Bobby"},
    {"id": "c", "name": "Carol"},
    {"id": "d", "name": "David"},
    {"id": "g", "name": "GPT-4.1"},
    {"id": "s", "name": "o3"},
]
BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def row(identity, author, content, second=0, *, room="room", stamp=None, human=False):
    value = {
        "id": identity, "agent_id": author, "agent_name": next(
            (entry["name"] for entry in ROSTER if entry["id"] == author), str(author)),
        "timestamp": stamp or (BASE + timedelta(seconds=second)).isoformat(),
        "room_id": room, "content": content,
        "source": {"file": "original/chat_messages.jsonl", "line": second + 1, "table": "chat_messages"},
    }
    if human:
        value.update(speaker_type="user", user_speaker_id=author)
    return value


def analyze(rows, **kwargs):
    return temporal.analyze_temporal_mentions(rows, ROSTER, **kwargs)


def first_window(result):
    return next(iter(result["windows"].values()))


def graph(result, variant="baseline_exact"):
    return first_window(result)["variants"][variant]


def pair_set(measure):
    return {(item["source_agent_id"], item["target_agent_id"]) for item in measure["reachable_pairs"]}


def loss_by_node(measure):
    return {item["agent_id"]: item for item in measure["node_removal"]["rows"]}


def explicit_window(identity="w", start=0, end=10, room="room"):
    return {"id": identity, "room_id": room,
            "start": (BASE + timedelta(seconds=start)).isoformat(),
            "end_exclusive": (BASE + timedelta(seconds=end)).isoformat()}


def oracle(events, nodes, *, strict, removed=None):
    """Independent simple-path DFS on concrete events, not production helpers."""
    reached = set()
    for source in nodes:
        if source == removed:
            continue

        def walk(current, visited, previous):
            for event in events:
                origin, target = event["source_agent_id"], event["target_agent_id"]
                instant = parse_time(event["timestamp"])
                if origin != current or target == removed or origin == removed or target in visited:
                    continue
                if strict and previous is not None and instant <= previous:
                    continue
                reached.add((source, target))
                walk(target, visited | {target}, instant if strict else None)

        walk(source, {source}, None)
    return reached


class TemporalReferenceTests(unittest.TestCase):
    def test_forward_chain_and_bound_source_witness(self):
        rows = [row("ab", "a", "Bobby", 1), row("bc", "b", "Carol", 2)]
        result = analyze(rows)
        value = graph(result)
        self.assertEqual(value["static"]["reachable_pair_count"], 3)
        self.assertEqual(value["strict_temporal"]["reachable_pair_count"], 3)
        pair = next(item for item in value["strict_temporal"]["reachable_pairs"]
                    if item["source_agent_id"] == "a" and item["target_agent_id"] == "c")
        witness = value["witnesses"][pair["witness_ref"]]
        self.assertEqual(witness["message_ids"], ["ab", "bc"])
        self.assertTrue(witness["strict_timestamp_order"])
        self.assertEqual(witness["steps"][0]["source"], rows[0]["source"])
        self.assertEqual(witness["steps"][0]["original_text_sha256"],
                         hashlib.sha256(b"Bobby").hexdigest())
        self.assertIn("not delivery", witness["interpretation"])
        for evidence in first_window(result)["extraction_review"]["evidence_index"].values():
            self.assertNotIn("content", evidence)
            self.assertNotIn("shadow_text", evidence)

    def test_reverse_chain_static_only_has_explicit_invalid_time_order(self):
        value = graph(analyze([row("bc", "b", "Carol", 1), row("ab", "a", "Bobby", 2)]))
        self.assertEqual(value["static"]["reachable_pair_count"], 3)
        self.assertEqual(value["strict_temporal"]["reachable_pair_count"], 2)
        self.assertEqual(value["static_only_pair_count"], 1)
        pair = value["static_only_pairs"][0]
        self.assertEqual((pair["source_agent_id"], pair["target_agent_id"]), ("a", "c"))
        witness = value["witnesses"][pair["witness_ref"]]
        self.assertEqual(witness["message_ids"], ["ab", "bc"])
        self.assertFalse(witness["strict_timestamp_order"])

    def test_ties_never_chain_and_id_order_is_not_time_order(self):
        rows = [row("z", "a", "Bobby", 1), row("a", "b", "Carol", 1)]
        value = graph(analyze(rows))
        self.assertEqual(value["static"]["reachable_pair_count"], 3)
        self.assertEqual(value["strict_temporal"]["reachable_pair_count"], 2)
        self.assertEqual(analyze(rows), analyze(list(reversed(rows))))
        for witness in value["witnesses"].values():
            if witness["operator"] == "strict_temporal":
                self.assertEqual(len(witness["steps"]), 1)

    def test_offset_equivalent_times_share_one_batch(self):
        value = graph(analyze([
            row("ab", "a", "Bobby", stamp="2026-01-01T05:30:01+05:30"),
            row("bc", "b", "Carol", stamp="2026-01-01T00:00:01Z"),
        ]))
        self.assertEqual(value["strict_temporal"]["reachable_pair_count"], 2)
        self.assertEqual(len({event["timestamp"] for event in value["events"]}), 1)

    def test_microsecond_order_is_preserved(self):
        value = graph(analyze([
            row("ab", "a", "Bobby", stamp="2026-01-01T00:00:00.000001Z"),
            row("bc", "b", "Carol", stamp="2026-01-01T00:00:00.000002Z"),
        ]))
        self.assertEqual(value["strict_temporal"]["reachable_pair_count"], 3)

    def test_naive_times_are_canonical_utc(self):
        value = graph(analyze([
            row("ab", "a", "Bobby", stamp="2026-01-01T00:00:01"),
            row("bc", "b", "Carol", stamp="2026-01-01T00:00:02Z"),
        ]))
        self.assertEqual(value["strict_temporal"]["reachable_pair_count"], 3)
        self.assertTrue(all(event["timestamp"].endswith("Z") for event in value["events"]))

    def test_cycle_distinct_pairs_and_no_self_paths(self):
        value = graph(analyze([
            row("ab", "a", "Bobby", 1), row("bc", "b", "Carol", 2),
            row("ca", "c", "Alice", 3),
        ]))
        self.assertEqual(value["static"]["reachable_pair_count"], 6)
        self.assertEqual(value["strict_temporal"]["reachable_pair_count"], 5)
        self.assertNotIn(("c", "b"), pair_set(value["strict_temporal"]))
        self.assertTrue(all(first != second for first, second in pair_set(value["static"])))

    def test_node_removal_endpoint_exclusion(self):
        value = graph(analyze([row("ab", "a", "Bobby", 1), row("bc", "b", "Carol", 2)]))
        losses = loss_by_node(value["strict_temporal"])
        self.assertEqual(losses["b"]["eligible_reachable_pairs"], 1)
        self.assertEqual(losses["b"]["lost_pairs"], 1)
        self.assertEqual(losses["b"]["loss_fraction"], 1)
        self.assertEqual(losses["a"]["eligible_reachable_pairs"], 1)
        self.assertEqual(losses["a"]["lost_pairs"], 0)
        self.assertEqual(losses["c"]["lost_pairs"], 0)

    def test_removal_recomputes_alternate_routes_not_only_selected_witness(self):
        value = graph(analyze([
            row("bc", "b", "Carol", 1), row("ab", "a", "Bobby", 2),
            row("ad", "a", "David", 1), row("dc", "d", "Carol", 2),
        ]))
        temporal_losses = loss_by_node(value["strict_temporal"])
        static_losses = loss_by_node(value["static"])
        self.assertNotIn(("a", "c"), {
            (item["source_agent_id"], item["target_agent_id"])
            for item in temporal_losses["b"]["lost_pair_witness_refs"]})
        self.assertIn(("a", "c"), {
            (item["source_agent_id"], item["target_agent_id"])
            for item in temporal_losses["d"]["lost_pair_witness_refs"]})
        self.assertNotIn(("a", "c"), {
            (item["source_agent_id"], item["target_agent_id"])
            for item in static_losses["d"]["lost_pair_witness_refs"]})

    def test_same_room_author_target_identity_does_not_chain_across_rooms(self):
        result = analyze([row("ab", "a", "Bobby", 1, room="first"),
                          row("bc", "b", "Carol", 2, room="second")])
        self.assertEqual(len(result["windows"]), 2)
        for window in result["windows"].values():
            self.assertEqual(window["variants"]["baseline_exact"]["static"]["reachable_pair_count"], 1)
            self.assertEqual(window["variants"]["baseline_exact"]["strict_temporal"]["reachable_pair_count"], 1)

    def test_explicit_window_lower_inclusive_upper_exclusive_and_original_membership(self):
        rows = [row("before", "a", "Bobby", 0), row("lower", "a", "Bobby", 1),
                row("middle", "b", "Carol", 2), row("upper", "c", "Alice", 3)]
        window = explicit_window(start=1, end=3)
        selected = sorted([normalize_message(rows[1]), normalize_message(rows[2])],
                          key=lambda item: (item["timestamp"], item["id"]))
        window["evidence_ids"] = ["lower", "middle"]
        window["source_fingerprint"] = hashlib.sha256(
            "|".join(item["id"] + ":" + item["content_hash"] for item in selected).encode("utf-8")).hexdigest()
        result = analyze(rows, windows=[window])
        self.assertEqual(result["windows"]["w"]["message_ids"], ["lower", "middle"])
        self.assertEqual(graph(result)["strict_temporal"]["reachable_pair_count"], 3)
        bad = {**window, "evidence_ids": ["middle", "lower"]}
        with self.assertRaisesRegex(ValueError, "membership mismatch"):
            analyze(rows, windows=[bad])
        with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
            analyze(rows, windows=[{**window, "source_fingerprint": "bad"}])

    def test_human_context_retained_but_human_edges_and_known_human_targets_excluded(self):
        rows = [row("human", "h", "Alice Bobby", 0, human=True),
                row("agent", "a", "Human Bobby", 1)]
        roster = ROSTER + [{"id": "h", "name": "Human", "speaker_type": "user"}]
        result = temporal.analyze_temporal_mentions(rows, roster)
        window = first_window(result)
        self.assertEqual(window["human_message_count"], 1)
        self.assertEqual(window["message_count"], 2)
        self.assertEqual(window["node_universe"]["ids"], ["a", "b"])
        reasons = {item["reason"] for item in graph(result)["excluded_events"]}
        self.assertEqual(reasons, {"human_source", "known_nonagent_target"})
        self.assertEqual(graph(result)["event_count"], 1)

    def test_conflicting_agent_human_identity_is_rejected(self):
        rows = [row("human", "a", "Bobby", 0, human=True),
                row("agent", "a", "Bobby", 1)]
        with self.assertRaisesRegex(ValueError, "Conflicting agent"):
            analyze(rows)

    def test_unobserved_target_is_not_an_observed_reader(self):
        result = analyze([row("ab", "a", "Bobby", 1)])
        self.assertEqual(first_window(result)["node_universe"]["targets_without_authored_messages"], ["b"])
        self.assertEqual(graph(result)["strict_temporal"]["reachable_pair_count"], 1)
        self.assertIsNone(graph(result)["strict_temporal"]["node_removal"]["maximum_loss_fraction"])
        self.assertIn("reading", " ".join(result["limitations"]))

    def test_all_variant_universes_fixed_and_shadow_coordinate_honesty(self):
        rows = [row("a", "a", "  o3   GPT\u20114.1", 1)]
        result = analyze(rows, short_name_allowlist=["o3"], include_unicode_shadow=True)
        values = first_window(result)["variants"]
        self.assertEqual({tuple(value["node_ids"]) for value in values.values()}, {("a", "g", "s")})
        self.assertEqual(values["baseline_exact"]["event_count"], 0)
        self.assertEqual(values["explicit_short_expanded_exact"]["event_count"], 1)
        self.assertEqual(values["unicode_baseline"]["event_count"], 1)
        self.assertEqual(values["unicode_expanded"]["event_count"], 2)
        for name, value in values.items():
            for event in value["events"]:
                span = event["span"]
                text = normalize_shadow_text(rows[0]["content"]) if name.startswith("unicode") else rows[0]["content"]
                self.assertEqual(text[span["start"]:span["end"]], event["match_text"])
                self.assertEqual(event["original_span_available"], not name.startswith("unicode"))
                self.assertIn("shadow_text" if name.startswith("unicode") else "original_content",
                              span["coordinates"])
        self.assertEqual(result["model_calls"], 0)

    def test_short_name_collision_unknown_not_silent_target(self):
        roster = ROSTER + [{"id": "s2", "name": "O3"}]
        result = temporal.analyze_temporal_mentions([row("a", "a", "o3", 1)], roster,
                                                   short_name_allowlist=["o3"], include_unicode_shadow=True)
        for value in first_window(result)["variants"].values():
            self.assertEqual(value["event_count"], 0)
        resolution = first_window(result)["extraction_review"]["allowlist_resolution"][0]
        self.assertEqual(resolution["status"], "ambiguous_unknown_target")

    def test_unicode_collision_excludes_shadow_only(self):
        roster = ROSTER + [{"id": "g2", "name": "GPT\u20114.1"}]
        result = temporal.analyze_temporal_mentions([row("a", "a", "GPT-4.1", 1)], roster,
                                                   include_unicode_shadow=True)
        self.assertEqual(graph(result)["event_count"], 1)
        self.assertEqual(graph(result, "unicode_baseline")["event_count"], 0)
        self.assertTrue(first_window(result)["extraction_review"]["unicode_shadow"]["normalized_roster_collisions"])

    def test_default_extraction_is_not_widened(self):
        result = analyze([row("a", "a", "o3 GPT\u20114.1", 1)])
        self.assertEqual(graph(result)["event_count"], 0)
        self.assertFalse(graph(result, "unicode_baseline")["available"])
        self.assertEqual(result["configuration"]["short_name_allowlist"], [])

    def test_missing_malformed_conflicting_or_nonstring_timestamp_fail_closed(self):
        valid = row("a", "a", "Bobby", 1)
        for change, fragment in [
            ({"timestamp": None}, "Missing source"),
            ({"timestamp": "not-a-date"}, "Malformed source"),
            ({"timestamp": 20260101}, "ISO strings"),
            ({"created_at": "2026-01-02T00:00:01Z"}, "Conflicting created_at"),
        ]:
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, fragment):
                analyze([{**valid, **change}])

    def test_original_ids_required_and_duplicate_rows_never_repaired(self):
        valid = row("a", "a", "Bobby", 1)
        for identity in (None, "", 1):
            with self.subTest(identity=identity), self.assertRaisesRegex(ValueError, "original nonempty"):
                analyze([{**valid, "id": identity}])
        with self.assertRaisesRegex(ValueError, "Repeated source"):
            analyze([valid, {**valid, "content": "Carol"}])

    def test_year_9999_default_end_requires_supported_explicit_scope(self):
        rows = [row("last", "a", "Bobby", stamp="9999-12-31T23:59:59.999999Z")]
        with self.assertRaisesRegex(ValueError, "Retained-span end cannot be padded"):
            analyze(rows)
        window = {"id": "bounded", "room_id": "room", "start": "9999-12-31T23:59:59Z",
                  "end_exclusive": "9999-12-31T23:59:59.999999Z"}
        result = analyze(rows, windows=[window])
        self.assertEqual(result["windows"]["bounded"]["message_count"], 0)

    def test_empty_scope_finite_and_missing_period_not_behavioral_zero(self):
        result = analyze([])
        self.assertEqual(result["windows"], {})
        result = analyze([], windows=[explicit_window()])
        value = graph(result)
        self.assertEqual(value["static"]["reachable_pair_count"], 0)
        self.assertIsNone(value["temporal_fraction_of_static_pairs"])
        self.assertIsNone(value["strict_temporal"]["node_removal"]["maximum_loss_fraction"])
        self.assertIn("not observed behavioral zeros", first_window(result)["coverage_status"])
        json.dumps(result, allow_nan=False)

    def test_raw_rows_roster_refs_immutability_and_determinism(self):
        rows = [row("ab", "a", "Bobby", 1), row("bc", "b", "Carol", 2)]
        roster, refs = copy.deepcopy(ROSTER), [{"id": "dataset", "version": 1, "hash": "declared"}]
        initial = copy.deepcopy([rows, roster, refs])
        first = temporal.analyze_temporal_mentions(rows, roster, source_refs=refs)
        second = temporal.analyze_temporal_mentions(list(reversed(rows)), list(reversed(roster)), source_refs=refs)
        self.assertEqual(first, second)
        self.assertEqual([rows, roster, refs], initial)
        self.assertFalse(first["source_binding"]["declared_refs_external_authentication"])
        first["source_refs"][0]["id"] = "changed"
        self.assertEqual(refs, initial[2])

    def test_all_witness_steps_bind_exact_source_and_same_room(self):
        rows = [row("ab", "a", "Bobby Carol", 1), row("bc", "b", "Carol Alice", 2),
                row("cd", "c", "David", 3), row("da", "d", "Alice", 4)]
        originals = {item["id"]: item for item in rows}
        result = analyze(rows, include_unicode_shadow=True)
        for value in first_window(result)["variants"].values():
            accepted = {item["event_id"]: item for item in value["events"]}
            for witness in value["witnesses"].values():
                self.assertEqual(witness["message_ids"], [step["message_id"] for step in witness["steps"]])
                self.assertEqual(witness["source_agent_id"], witness["steps"][0]["source_agent_id"])
                self.assertEqual(witness["target_agent_id"], witness["steps"][-1]["target_agent_id"])
                self.assertEqual(len({step["room_id"] for step in witness["steps"]}), 1)
                for step in witness["steps"]:
                    self.assertEqual(step, accepted[step["event_id"]])
                    raw = originals[step["message_id"]]
                    self.assertEqual(raw["agent_id"], step["source_agent_id"])
                    self.assertEqual(raw["source"], step["source"])
                for left, right in zip(witness["steps"], witness["steps"][1:]):
                    self.assertEqual(left["target_agent_id"], right["source_agent_id"])
                    if witness["operator"] == "strict_temporal":
                        self.assertLess(parse_time(left["timestamp"]), parse_time(right["timestamp"]))

    def test_random_small_graphs_against_independent_dfs(self):
        generator = random.Random(4514)
        names = {item["id"]: item["name"] for item in ROSTER}
        for sample in range(20):
            rows = []
            for step in range(7):
                source, target = generator.sample(["a", "b", "c", "d"], 2)
                rows.append(row(f"m{step}", source, names[target], generator.randrange(4)))
            value = graph(analyze(rows))
            for name, strict in (("static", False), ("strict_temporal", True)):
                actual = pair_set(value[name])
                expected = oracle(value["events"], value["node_ids"], strict=strict)
                self.assertEqual(actual, expected, (sample, name))
                for node, removal in loss_by_node(value[name]).items():
                    eligible = {pair for pair in expected if node not in pair}
                    remaining = oracle(value["events"], value["node_ids"], strict=strict, removed=node)
                    self.assertEqual(removal["eligible_reachable_pairs"], len(eligible))
                    self.assertEqual(removal["lost_pairs"], len(eligible - remaining))

    def test_node_event_window_and_aggregate_work_bounds(self):
        rows = [row("ab", "a", "Bobby", 1), row("bc", "b", "Carol", 2)]
        for constant, value, fragment in [
            ("MAX_NODES", 2, "128 nodes"),
            ("MAX_EVENTS_PER_WINDOW_VARIANT", 1, "10000 events"),
            ("MAX_PATH_WORK", 300, "all-variant/removal"),
            ("MAX_EXTRACTION_CELLS", 2, "before extraction"),
        ]:
            with self.subTest(bound=constant), patch.object(temporal, constant, value):
                with self.assertRaisesRegex(ValueError, fragment):
                    analyze(rows)
        with self.assertRaisesRegex(ValueError, "at most 10000"):
            analyze([rows[0]] * 10001)
        with self.assertRaisesRegex(ValueError, "1 to 24"):
            analyze(rows, windows=[explicit_window(str(index)) for index in range(25)])
        with self.assertRaisesRegex(ValueError, "Duplicate window"):
            analyze(rows, windows=[explicit_window(), explicit_window()])
        with self.assertRaisesRegex(ValueError, "must precede"):
            analyze(rows, windows=[explicit_window(start=3, end=3)])

    def test_metadata_shape_bytes_and_finite_bounds(self):
        valid = row("a", "a", "Bobby", 1)
        huge_source = {"file": "a" * 4096, "line": 1}
        with self.assertRaisesRegex(ValueError, "Source provenance serialized"):
            analyze([{**valid, "source": huge_source}])
        nested = {}
        current = nested
        for _ in range(9):
            current["nested"] = {}
            current = current["nested"]
        with self.assertRaisesRegex(ValueError, "structure bound"):
            analyze([{**valid, "source": nested}])
        with self.assertRaisesRegex(ValueError, "finite JSON"):
            analyze([{**valid, "metadata": float("nan")}])
        cyclic = {"cycle": None}
        cyclic["cycle"] = cyclic
        with self.assertRaisesRegex(ValueError, "cyclic"):
            analyze([{**valid, "metadata": cyclic}])
        with patch.object(temporal, "MAX_INPUT_BYTES", 10):
            with self.assertRaisesRegex(ValueError, "Aggregate source-message"):
                analyze([valid])
        with patch.object(temporal, "MAX_SOURCE_REFS_BYTES", 10):
            with self.assertRaisesRegex(ValueError, "Source references serialized"):
                analyze([valid], source_refs=[{"id": "source-is-long"}])
        with patch.object(temporal, "MAX_WINDOW_METADATA_BYTES", 10):
            with self.assertRaisesRegex(ValueError, "Window metadata serialized"):
                analyze([valid], windows=[explicit_window()])

    def test_witness_pair_and_byte_limits_before_materializing_large_output(self):
        rows = [row("ab", "a", "Bobby", 1), row("bc", "b", "Carol", 2)]
        for constant, value, fragment in [
            ("MAX_UNIQUE_WITNESSES", 1, "unique-witness"),
            ("MAX_WITNESS_STEPS", 1, "witness-step"),
            ("MAX_PAIR_RECORDS", 1, "pair-record"),
            ("MAX_OUTPUT_BYTES", 2000, "serialized byte"),
        ]:
            with self.subTest(bound=constant), patch.object(temporal, constant, value):
                with self.assertRaisesRegex(ValueError, fragment):
                    analyze(rows)
        # The witness guard occurs before copying event/source trees.
        value = graph(analyze(rows))
        event = value["events"][0]
        for constant, count, fragment in [
            ("MAX_UNIQUE_WITNESSES", "unique_witnesses", "unique-witness"),
            ("MAX_WITNESS_STEPS", "witness_steps", "witness-step"),
        ]:
            budget = temporal._new_budget()
            budget[count] = getattr(temporal, constant)
            with patch.object(temporal.copy, "deepcopy", side_effect=AssertionError("copied before bound")):
                with self.assertRaisesRegex(ValueError, fragment):
                    temporal._witness(("a", "b"), (0,), [event], "strict_temporal", "w", "baseline_exact", budget)
        budget = temporal._new_budget()
        with patch.object(temporal, "MAX_OUTPUT_BYTES", 1), \
                patch.object(temporal.copy, "deepcopy", side_effect=AssertionError("copied before byte bound")):
            with self.assertRaisesRegex(ValueError, "Path witness output serialized byte"):
                temporal._witness(("a", "b"), (0,), [event], "strict_temporal", "w", "baseline_exact", budget)

    def test_reported_serialized_size_and_fragment_reservations(self):
        result = analyze([row("ab", "a", "Bobby", 1), row("bc", "b", "Carol", 2)])
        size = len(json.dumps(result, sort_keys=True, ensure_ascii=False,
                              separators=(",", ":"), allow_nan=False).encode("utf-8"))
        self.assertEqual(size, result["bounds"]["serialized_output_bytes"])
        self.assertLessEqual(size, result["bounds"]["reserved_output_bytes"])
        self.assertLessEqual(size, result["bounds"]["max_output_bytes"])
        actual_witnesses = [witness for window in result["windows"].values()
                            for value in window["variants"].values()
                            for witness in value.get("witnesses", {}).values()]
        self.assertEqual(result["bounds"]["emitted_unique_witnesses"], len(actual_witnesses))
        self.assertEqual(result["bounds"]["emitted_witness_steps"],
                         sum(len(witness["steps"]) for witness in actual_witnesses))


if __name__ == "__main__":
    unittest.main()
