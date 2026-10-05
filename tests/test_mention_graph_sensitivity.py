import copy
import hashlib
import json
import unittest
from pathlib import Path

from swarm_lab.name_eligibility_sensitivity import audit_name_eligibility_sensitivity
from swarm_lab.mention_graph_sensitivity import (
    MENTION_GRAPH_SENSITIVITY_VERSION, compare_name_graphs,
)


ROSTER = [{"id": "a", "name": "Alice"}, {"id": "g", "name": "GPT-4.1"},
          {"id": "three", "name": "o3"}]


def row(identity, agent, text, minute=0, **extra):
    return {"id": identity, "agent_id": agent, "speaker_type": "agent",
            "content": text, "room_id": "lab", "timestamp": f"2025-04-20T10:{minute:02}:00Z",
            **extra}


def fixture():
    return [row("m1", "a", "o3, inspect", 0),
            row("m2", "three", "GPT-4.1, check", 1),
            row("m3", "g", "Alice, received", 2),
            row("m4", "a", "GPT\u20114.1, inspect", 3)]


def make_audit(messages, *, roster=ROSTER, shadow=True, allowlist=None):
    return audit_name_eligibility_sensitivity(messages, roster,
                                              short_name_allowlist=["o3"] if allowlist is None else allowlist,
                                              include_unicode_shadow=shadow)


def node_metric(report, variant, identity):
    return next(node for node in report["variants"][variant]["metrics"]["nodes"] if node["id"] == identity)


class MentionGraphSensitivityTests(unittest.TestCase):
    def test_four_variants_use_same_disclosed_fixed_universe(self):
        messages = fixture()
        result = compare_name_graphs(messages, make_audit(messages), agents=ROSTER)
        self.assertEqual(result["analysis_version"], MENTION_GRAPH_SENSITIVITY_VERSION)
        self.assertEqual(result["model_calls"], 0)
        self.assertTrue(result["read_only"])
        self.assertEqual(set(result["variants"]), {"baseline_exact", "explicit_short_expanded_exact",
                                                 "unicode_baseline", "unicode_expanded"})
        self.assertEqual(result["node_universe"]["ids"], ["a", "g", "three"])
        for graph in result["variants"].values():
            self.assertTrue(graph["available"])
            self.assertEqual([node["id"] for node in graph["nodes"]], result["node_universe"]["ids"])
            self.assertEqual(graph["counts"]["node_universe_count"], 3)
            self.assertTrue(graph["diagnostic_only"])
        for comparison in result["comparisons"]:
            self.assertEqual(comparison["count_differences"]["node_universe_count"], 0)
            self.assertEqual(comparison["graph_metrics"]["node_count"]["difference"], 0)
        self.assertIn("Not necessarily", result["node_universe"]["dashboard_equivalence"])

    def test_omitted_short_target_changes_apparent_centrality_without_behavior_claim(self):
        messages = fixture()
        result = compare_name_graphs(messages, make_audit(messages), agents=ROSTER)
        baseline = node_metric(result, "baseline_exact", "three")
        expanded = node_metric(result, "explicit_short_expanded_exact", "three")
        self.assertEqual(baseline["in_strength"], 0)
        self.assertEqual(expanded["in_strength"], 1)
        self.assertEqual(baseline["directed_unweighted_betweenness"], 0)
        self.assertAlmostEqual(expanded["directed_unweighted_betweenness"], .5)
        counts = {name: graph["counts"]["projected_agent_event_count"] for name, graph in result["variants"].items()}
        self.assertEqual(counts, {"baseline_exact": 2, "explicit_short_expanded_exact": 3,
                                 "unicode_baseline": 3, "unicode_expanded": 4})
        self.assertTrue(any("solely from extraction" in text for text in result["limitations"]))

    def test_fixed_referenced_nodes_unknown_author_rates_and_nullity(self):
        messages = [row("m1", "a", "o3 and GPT\u20114.1")]
        result = compare_name_graphs(messages, make_audit(messages), agents=ROSTER)
        self.assertEqual(result["node_universe"]["target_ids_without_authored_messages"], ["g", "three"])
        for name, graph in result["variants"].items():
            for target in ("g", "three"):
                metrics = node_metric(result, name, target)
                self.assertEqual(metrics["authored_message_count"], 0)
                self.assertIsNone(metrics["outgoing_interactions_per_authored_message"])
                self.assertIsNone(metrics["incoming_interactions_per_coactive_message"])
            self.assertFalse(next(node for node in graph["nodes"] if node["id"] == "g")["observed_author_in_scope"])
        baseline = result["variants"]["baseline_exact"]
        expanded = result["variants"]["unicode_expanded"]
        self.assertEqual(baseline["counts"]["isolate_count"], 3)
        self.assertEqual(expanded["counts"]["isolate_count"], 0)
        if baseline["spectral"]["available"]:
            self.assertEqual(baseline["spectral"]["nullity"], 3)
            self.assertEqual(expanded["spectral"]["nullity"], 1)
            comparison = next(row for row in result["comparisons"] if row["variant"] == "unicode_expanded")
            self.assertEqual(comparison["spectral"]["nullity_difference"], -2)
        self.assertIsNone(next(row for row in result["comparisons"] if row["variant"] == "unicode_expanded")
                          ["node_metrics"][1]["metrics"]["outgoing_interactions_per_authored_message"]["difference"])

    def test_aggregate_one_message_target_preserves_exact_evidence_and_instruments(self):
        messages = [row("m1", "a", "o3 o3 o3"), row("m2", "a", "o3", 1)]
        result = compare_name_graphs(messages, make_audit(messages), agents=ROSTER)
        graph = result["variants"]["explicit_short_expanded_exact"]
        self.assertEqual(len(graph["edges"]), 1)
        edge = graph["edges"][0]
        self.assertEqual((edge["source"], edge["target"], edge["weight"]), ("a", "three", 2))
        self.assertEqual(edge["evidence_ids"], ["m1", "m2"])
        self.assertEqual(edge["instrument_event_counts"], {"explicit_short_name_exact": 2})
        self.assertEqual([ref["message_id"] for ref in edge["source_event_refs"]], ["m1", "m2"])
        self.assertEqual(edge["source_event_refs"][0]["span"]["coordinates"], "original_content_python_codepoints")

    def test_human_source_matches_are_validated_but_disclosed_and_excluded(self):
        messages = [row("m1", "human", "o3 GPT-4.1", speaker_type="user")]
        result = compare_name_graphs(messages, make_audit(messages), agents=ROSTER)
        graph = result["variants"]["explicit_short_expanded_exact"]
        self.assertEqual(graph["counts"]["source_measurement_event_count"], 2)
        self.assertEqual(graph["counts"]["excluded_human_source_event_count"], 2)
        self.assertEqual(graph["counts"]["projected_agent_event_count"], 0)
        self.assertFalse(graph["edges"])
        self.assertEqual(result["node_universe"]["agent_author_ids"], [])
        self.assertEqual(result["node_universe"]["ids"], ["g", "three"])
        self.assertTrue(all(not node["observed_author_in_scope"] for node in graph["nodes"]))

    def test_spectral_statistics_exported_without_eigenvector_coordinates(self):
        messages = fixture()
        result = compare_name_graphs(messages, make_audit(messages), agents=ROSTER)
        for graph in result["variants"].values():
            self.assertNotIn("modes", graph["spectral"])
            self.assertNotIn("coefficients", graph["spectral"])
        for comparison in result["comparisons"]:
            if comparison["spectral"]["available"]:
                rows = comparison["spectral"]["ordered_eigenvalues"]
                self.assertEqual(len(rows), 3)
                for row in rows:
                    self.assertAlmostEqual(row["difference"], row["variant"] - row["reference"])
                self.assertIn("no persistent mode", comparison["spectral"]["interpretation"])
        self.assertTrue(all(result["validation"].values()))

    def test_no_mutation_and_code_hashes_have_binary_file_purpose(self):
        messages = fixture()
        audit = make_audit(messages)
        before_messages, before_audit, before_roster = copy.deepcopy(messages), copy.deepcopy(audit), copy.deepcopy(ROSTER)
        result = compare_name_graphs(messages, audit, agents=ROSTER)
        self.assertEqual(messages, before_messages)
        self.assertEqual(audit, before_audit)
        self.assertEqual(ROSTER, before_roster)
        network_file = Path(__file__).resolve().parents[1] / "swarm_lab" / "network.py"
        self.assertEqual(result["code_hashes"]["network"]["sha256"],
                         hashlib.sha256(network_file.read_bytes()).hexdigest())
        self.assertEqual(set(result["code_hashes"]), {"dataset", "network", "mention_sensitivity",
                                                     "name_eligibility_sensitivity", "mention_graph_sensitivity"})
        result["variants"]["explicit_short_expanded_exact"]["edges"][0]["source_event_refs"][0]["span"]["start"] = 999
        self.assertEqual(audit, before_audit)
        json.dumps(result, allow_nan=False)

    def test_deterministic_with_same_pinned_inputs(self):
        messages = fixture()
        audit = make_audit(messages)
        first = compare_name_graphs(messages, audit, agents=ROSTER)
        second = compare_name_graphs(list(reversed(messages)), audit, agents=list(reversed(ROSTER)))
        self.assertEqual(first, second)

    def test_mismatched_source_context_and_roster_rejected(self):
        messages = fixture()
        audit = make_audit(messages)
        for field, value in (("content", "changed text"), ("agent_id", "g"),
                             ("timestamp", "2025-04-21T10:00:00Z"), ("room_id", "other"),
                             ("source", {"file": "changed", "line": 1})):
            changed = copy.deepcopy(messages)
            changed[0][field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "source_fingerprint"):
                    compare_name_graphs(changed, audit, agents=ROSTER)
        with self.assertRaisesRegex(ValueError, "roster_fingerprint"):
            compare_name_graphs(messages, audit)
        with self.assertRaisesRegex(ValueError, "roster_fingerprint"):
            compare_name_graphs(messages, audit, agents=[{**agent, "name": agent["name"] + "x"} for agent in ROSTER])

    def test_duplicate_unknown_source_and_target_events_rejected(self):
        messages = fixture()
        audit = make_audit(messages)
        duplicate = copy.deepcopy(audit)
        duplicate["short_name_exact_events"].append(copy.deepcopy(duplicate["short_name_exact_events"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            compare_name_graphs(messages, duplicate, agents=ROSTER)
        source = copy.deepcopy(audit)
        source["short_name_exact_events"][0]["message_id"] = "invented-source"
        with self.assertRaisesRegex(ValueError, "unknown source"):
            compare_name_graphs(messages, source, agents=ROSTER)
        target = copy.deepcopy(audit)
        target["short_name_exact_events"][0]["target_agent_id"] = "invented-target"
        with self.assertRaisesRegex(ValueError, "unknown or unmeasured target"):
            compare_name_graphs(messages, target, agents=ROSTER)

    def test_fabricated_known_target_span_count_and_bounds_rejected(self):
        messages = fixture()
        audit = make_audit(messages)
        target = copy.deepcopy(audit)
        target["short_name_exact_events"][0]["target_agent_id"] = "g"
        with self.assertRaisesRegex(ValueError, "short_name_exact_events"):
            compare_name_graphs(messages, target, agents=ROSTER)
        span = copy.deepcopy(audit)
        span["baseline_exact_events"][0]["span"]["start"] = False
        with self.assertRaisesRegex(ValueError, "baseline_exact_events"):
            compare_name_graphs(messages, span, agents=ROSTER)
        count = copy.deepcopy(audit)
        count["summary"]["baseline_exact_event_count"] += 1
        with self.assertRaisesRegex(ValueError, "summary"):
            compare_name_graphs(messages, count, agents=ROSTER)
        bounds = copy.deepcopy(audit)
        bounds["bounds"]["max_agents"] += 1
        with self.assertRaisesRegex(ValueError, "bounds"):
            compare_name_graphs(messages, bounds, agents=ROSTER)

    def test_unknown_collision_events_are_not_promoted_to_edges(self):
        roster = ROSTER + [{"id": "other-three", "name": "O3"}]
        messages = [row("m1", "a", "o3 GPT-4.1")]
        audit = make_audit(messages, roster=roster)
        self.assertEqual(audit["summary"]["ambiguous_exact_event_count"], 1)
        result = compare_name_graphs(messages, audit, agents=roster)
        for graph in result["variants"].values():
            self.assertEqual(graph["counts"]["projected_agent_event_count"], 1)
            self.assertTrue(all(edge["target"] == "g" for edge in graph["edges"]))
        self.assertNotIn("other-three", result["node_universe"]["ids"])
        self.assertNotIn("three", result["node_universe"]["ids"])

    def test_unrequested_shadow_stays_unavailable_and_empty_data_are_valid(self):
        messages = fixture()
        result = compare_name_graphs(messages, make_audit(messages, shadow=False), agents=ROSTER)
        self.assertFalse(result["variants"]["unicode_baseline"]["available"])
        self.assertFalse(result["variants"]["unicode_expanded"]["available"])
        self.assertTrue(result["variants"]["baseline_exact"]["available"])
        self.assertTrue(result["variants"]["explicit_short_expanded_exact"]["available"])
        empty = compare_name_graphs([], make_audit([], roster=[], allowlist=[]), agents=[])
        self.assertFalse(empty["node_universe"]["ids"])
        self.assertEqual(empty["variants"]["baseline_exact"]["metrics"]["graph"]["node_count"], 0)
        json.dumps(empty, allow_nan=False)

    def test_invalid_payload_missing_lists_and_version_rejected(self):
        messages = fixture()
        audit = make_audit(messages)
        with self.assertRaises(ValueError):
            compare_name_graphs(messages, None, agents=ROSTER)
        wrong_version = {**audit, "analysis_version": "unrecognized-version"}
        with self.assertRaisesRegex(ValueError, "version"):
            compare_name_graphs(messages, wrong_version, agents=ROSTER)
        missing = copy.deepcopy(audit)
        del missing["baseline_exact_events"]
        with self.assertRaisesRegex(ValueError, "missing required event"):
            compare_name_graphs(messages, missing, agents=ROSTER)
        wrong_flag = copy.deepcopy(audit)
        wrong_flag["unicode_shadow"]["enabled"] = 1
        with self.assertRaisesRegex(ValueError, "enabled flag"):
            compare_name_graphs(messages, wrong_flag, agents=ROSTER)


if __name__ == "__main__":
    unittest.main()
