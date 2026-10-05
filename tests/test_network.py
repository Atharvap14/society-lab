import json
import math
import unittest
from pathlib import Path

from swarm_lab.dataset import ingest_village
from swarm_lab.network import analyze_network, spectral_basis


ROSTER = [{"id": "a", "name": "Alice"}, {"id": "b", "name": "Bobby"}, {"id": "c", "name": "Carol"}, {"id": "d", "name": "Delta"}]


def row(identity, agent, text, minute, *, room="lab", reply_to=None):
    return {"id": identity, "agent_id": agent, "speaker_type": "agent", "content": text, "room_id": room, "timestamp": f"2025-04-02T10:{minute:02}:00Z", "reply_to": reply_to}


class NetworkTests(unittest.TestCase):
    def test_directed_chain_metrics_and_exposure_denominators(self):
        result = analyze_network([row("m1", "a", "Bobby, inspect the artifact", 0), row("m2", "b", "Carol, inspect the artifact", 1), row("m3", "c", "The artifact is uploaded", 2)], ROSTER, null_replicates=0)
        projection = result["projections"]["observed_mentions"]
        metrics = projection["metrics"]["graph"]
        nodes = {node["id"]: node for node in projection["metrics"]["nodes"]}
        self.assertEqual(metrics["directed_edge_count"], 2)
        self.assertEqual(metrics["binary_reciprocity"], 0)
        self.assertEqual(nodes["b"]["in_degree"], 1)
        self.assertEqual(nodes["b"]["out_degree"], 1)
        self.assertAlmostEqual(nodes["b"]["directed_unweighted_betweenness"], 0.5)
        self.assertEqual(nodes["a"]["outgoing_interactions_per_authored_message"], 1)
        self.assertEqual(nodes["b"]["coactive_room_other_message_count"], 2)
        self.assertEqual(nodes["b"]["incoming_interactions_per_coactive_message"], 0.5)
        self.assertEqual(metrics["weak_components"], [["a", "b", "c"]])
        self.assertEqual(len(metrics["strong_components"]), 3)

    def test_weighted_reciprocity_keeps_direction_and_event_counts(self):
        messages = [row("m1", "a", "Bobby check one", 0), row("m2", "a", "Bobby check two", 1), row("m3", "b", "Alice reply", 2)]
        result = analyze_network(messages, ROSTER, null_replicates=0)
        graph = result["projections"]["observed_mentions"]["metrics"]["graph"]
        self.assertEqual(graph["binary_reciprocity"], 1)
        self.assertAlmostEqual(graph["weighted_reciprocity"], 2 / 3)
        self.assertEqual(graph["strong_components"], [["a", "b"]])

    def test_reply_proximity_and_mentions_not_pooled(self):
        messages = [row("m1", "a", "This is the draft", 0), row("m2", "b", "A revised draft", 1, reply_to="m1")]
        result = analyze_network(messages, ROSTER, null_replicates=0)
        projections = result["projections"]
        self.assertFalse(projections["observed_mentions"]["edges"])
        reply = projections["observed_replies"]["edges"][0]
        proximity = projections["inferred_proximity"]["edges"][0]
        self.assertEqual((reply["source"], reply["target"]), ("b", "a"))
        self.assertFalse(reply["inferred"])
        self.assertEqual((proximity["source"], proximity["target"]), ("a", "b"))
        self.assertTrue(proximity["inferred"])
        self.assertEqual(reply["evidence_ids"], ["m2", "m1"])

    def test_disjoint_rooms_do_not_imply_exposure_or_temporal_ties(self):
        result = analyze_network([row("m1", "a", "Bobby, I left a note", 0, room="room-a"), row("m2", "b", "I work elsewhere", 1, room="room-b")], ROSTER, null_replicates=0)
        metrics = result["projections"]["observed_mentions"]["metrics"]["nodes"]
        bob = next(node for node in metrics if node["id"] == "b")
        self.assertEqual(bob["in_strength"], 1)
        self.assertIsNone(bob["incoming_interactions_per_coactive_message"])
        self.assertFalse(result["projections"]["inferred_proximity"]["edges"])

    def test_laplacian_eigenvalues_and_basis_satisfy_operator(self):
        nodes = ["a", "b", "c", "d"]
        basis = spectral_basis(nodes, [{"source": "a", "target": "b", "weight": 1}, {"source": "b", "target": "c", "weight": 1}])
        if not basis["available"]:
            self.assertIn("numpy", basis["reason"])
            return
        self.assertEqual(basis["nullity"], 2)
        self.assertEqual(basis["isolated_ids"], ["d"])
        for got, expected in zip(basis["eigenvalues"], [0, 0, 1, 2]):
            self.assertAlmostEqual(got, expected)
        for left in basis["modes"]:
            for right in basis["modes"]:
                product = sum(left["coefficients"][node] * right["coefficients"][node] for node in nodes)
                self.assertAlmostEqual(product, 1 if left["index"] == right["index"] else 0)
            vector = [left["coefficients"][node] for node in nodes]
            product = [vector[0] - vector[1] / math.sqrt(2), vector[1] - (vector[0] + vector[2]) / math.sqrt(2), vector[2] - vector[1] / math.sqrt(2), 0]
            for index in range(4):
                self.assertAlmostEqual(product[index], left["eigenvalue"] * vector[index])
        self.assertTrue(any("manifold" in warning for warning in basis["warnings"]))

    def test_null_reference_reproducible_and_not_causal(self):
        messages = [row("m1", "a", "Bobby, check the task", 0), row("m2", "b", "Alice, acknowledged", 1), row("m3", "c", "Bobby, additional check", 2), row("m4", "a", "Carol, thank you", 3)]
        first = analyze_network(messages, ROSTER, seed=17, null_replicates=30)
        second = analyze_network(messages, ROSTER, seed=17, null_replicates=30)
        self.assertEqual(first["null_reference"], second["null_reference"])
        self.assertEqual(first["null_reference"]["exchangeable_strata"], 1)
        self.assertEqual(first["null_reference"]["replicates"], 30)
        self.assertTrue(any("not a randomized" in warning for warning in first["null_reference"]["limitations"]))
        json.dumps(first, allow_nan=False)

    def test_empty_and_single_actor_networks_are_finite(self):
        for messages in [[], [row("m1", "a", "Independent work", 0)]]:
            result = analyze_network(messages, ROSTER, null_replicates=10)
            json.dumps(result, allow_nan=False)
            graph = result["projections"]["observed_mentions"]["metrics"]["graph"]
            self.assertIsNone(graph["binary_reciprocity"])
            self.assertEqual(graph["directed_density"], 0)

    def test_self_mentions_excluded_and_unknown_evidence_not_created(self):
        result = analyze_network([row("m1", "a", "Alice will check this", 0)], ROSTER, null_replicates=0)
        self.assertFalse(result["projections"]["observed_mentions"]["edges"])
        with self.assertRaises(ValueError):
            analyze_network([row("m1", "a", "first", 0), row("m1", "b", "duplicate", 1)], ROSTER)

    def test_bounded_fixture_runs_without_external_api(self):
        fixture = Path(__file__).resolve().parents[1] / "examples" / "coordination_fixture"
        data = ingest_village(fixture, limit=20)
        result = analyze_network(data["messages"], data["agents"], null_replicates=20)
        self.assertEqual(result["scope"]["message_count"], 8)
        self.assertEqual(result["scope"]["agent_authors"], 3)
        self.assertTrue(result["projections"]["observed_mentions"]["edges"])
        evidence = {message["id"] for message in data["messages"]}
        for projection in result["projections"].values():
            for edge in projection["edges"]:
                self.assertTrue(set(edge["evidence_ids"]) <= evidence)


if __name__ == "__main__":
    unittest.main()
