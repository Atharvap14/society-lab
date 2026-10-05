import copy
import json
import math
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from swarm_lab.graph_discovery import bridge_dependence, discover_graph_leads, graph_signal_summary
from swarm_lab.network import spectral_basis


ROSTER=[{"id":"a","name":"Alice"},{"id":"b","name":"Bobby"},{"id":"c","name":"Carol"}]


def fixture():
    messages=[]
    for hour in (10,11):
        for i in range(12):
            actor=("a","b","c")[i % 3]
            if hour == 10:
                text="Bobby, inspect the telescope artifact." if actor != "b" else "My local note is ready for review."
            else:
                text="Alice, Bobby, Carol, inspect the telescope artifact together."
            stamp=datetime(2025,4,2,hour,21,tzinfo=timezone.utc)+timedelta(minutes=i)
            messages.append({"id":f"{hour}-{i}","agent_id":actor,"content":text,"room_id":"lab","timestamp":stamp.isoformat(),
                             "source":{"file":"authored_fixture.jsonl","line":len(messages)+1}})
    return messages


class GraphDiscoveryTests(unittest.TestCase):
    def test_node_removal_excludes_endpoint_loss_and_keeps_direction(self):
        projection={"nodes":[{"id":node} for node in ("a","b","c")],
                    "edges":[{"source":"a","target":"b"},{"source":"b","target":"c"}]}
        result=bridge_dependence(projection)
        self.assertEqual(result["focus_agent_id"],"b")
        self.assertEqual(result["maximum_loss_fraction"],1)
        b=next(row for row in result["nodes"] if row["agent_id"] == "b")
        self.assertEqual(b["eligible_reachable_pairs"],1)
        self.assertEqual(b["lost_pairs"],1)
        two=bridge_dependence({"nodes":[{"id":"a"},{"id":"b"}],"edges":[{"source":"a","target":"b"}]})
        self.assertIsNone(two["maximum_loss_fraction"])

    def test_matched_leads_have_source_ids_and_explicit_exploratory_selection(self):
        result=discover_graph_leads(fixture(),ROSTER)
        leads={lead["feature"]:lead for lead in result["leads"]}
        self.assertIn("incoming_concentration",leads)
        self.assertIn("directed_reciprocity",leads)
        lead=leads["incoming_concentration"]
        self.assertEqual(lead["support"]["messages"],12)
        self.assertEqual(lead["comparison_match"]["distance"],0)
        self.assertTrue(lead["comparison_match"]["nonoverlapping"])
        self.assertFalse(lead["comparison_match"]["causal_control"])
        self.assertFalse(lead["inferred"])
        self.assertEqual(lead["channel"],"observed_mentions")
        self.assertTrue(set(lead["evidence_ids"]) <= set(result["evidence_index"]))
        self.assertTrue(set(lead["comparison_evidence_ids"]) <= set(result["evidence_index"]))
        self.assertTrue(all(row["source"].get("line") for row in result["evidence_index"].values()))
        self.assertTrue(result["selection"]["multiple_search"])
        self.assertFalse(result["selection"]["confirmatory"])
        json.dumps(result,allow_nan=False)

    def test_widened_overlapping_sensitivity_windows_are_not_replications(self):
        result=discover_graph_leads(fixture(),ROSTER)
        lead=next(item for item in result["leads"] if item["feature"] == "incoming_concentration")
        self.assertEqual([row["window_minutes"] for row in lead["window_robustness"]],[30,60,120])
        widened=lead["window_robustness"][-1]
        self.assertTrue(widened["comparison_windows_overlap"])
        self.assertIsNone(widened["same_difference_direction"])
        self.assertEqual(lead["robustness_status"],"consistent_in_eligible_nonoverlapping_windows")

    def test_same_room_and_observed_volume_required_for_comparisons(self):
        messages=fixture()
        for message in messages[12:]:
            message["room_id"]="elsewhere"
        result=discover_graph_leads(messages,ROSTER)
        self.assertFalse(result["leads"])
        sparse=discover_graph_leads(fixture(),ROSTER,min_edge_events=100)
        self.assertFalse(sparse["leads"])
        self.assertEqual(sparse["selection"]["feature_window_comparisons_by_feature"].get("incoming_concentration",0),0)

    def test_missing_periods_not_created_as_zero_controls_and_censoring_visible(self):
        messages=fixture()
        for message in messages[12:]:
            message["timestamp"]=message["timestamp"].replace("2025-04-02","2025-04-06")
        result=discover_graph_leads(messages,ROSTER,max_windows=1)
        self.assertEqual(result["scope"]["candidate_windows"],2)
        self.assertEqual(result["scope"]["analyzed_windows"],1)
        self.assertTrue(result["scope"]["windows_truncated"])
        self.assertFalse(result["leads"])

    def test_basis_energy_invariant_to_rotation_of_repeated_eigenspaces(self):
        nodes=["a","b","c"]
        edges=[{"source":"a","target":"b","weight":1},{"source":"b","target":"c","weight":1},{"source":"c","target":"a","weight":1}]
        basis=spectral_basis(nodes,edges)
        if not basis["available"]:
            self.skipTest("Optional numpy unavailable")
        projection={"spectral":basis}
        signal={"a":2,"b":0,"c":-1}
        before=graph_signal_summary(projection,signal,cutoff=1.5)
        changed=copy.deepcopy(basis)
        first,second=changed["modes"][1],changed["modes"][2]
        original_first=dict(first["coefficients"])
        original_second=dict(second["coefficients"])
        for node in nodes:
            first["coefficients"][node]=(original_first[node]+original_second[node])/math.sqrt(2)
            second["coefficients"][node]=(original_first[node]-original_second[node])/math.sqrt(2)
        after=graph_signal_summary({"spectral":changed},signal,cutoff=1.5)
        self.assertAlmostEqual(before["rayleigh_smoothness"],after["rayleigh_smoothness"])
        self.assertAlmostEqual(before["eigenspace_energy"][1]["energy"],after["eigenspace_energy"][1]["energy"])
        self.assertEqual(before["eigenspace_energy"][1]["multiplicity"],2)
        self.assertAlmostEqual(before["low_positive_frequency_energy_fraction"],1)

    def test_graph_signal_missing_values_not_imputed_and_zero_energy_undefined(self):
        basis=spectral_basis(["a","b"],[{"source":"a","target":"b","weight":1}])
        if not basis["available"]:
            self.skipTest("Optional numpy unavailable")
        with self.assertRaises(ValueError):
            graph_signal_summary({"spectral":basis},{"a":1})
        zero=graph_signal_summary({"spectral":basis},{"a":0,"b":0})
        self.assertIsNone(zero["rayleigh_smoothness"])
        self.assertIsNone(zero["low_positive_frequency_energy_fraction"])
        json.dumps(zero,allow_nan=False)

    def test_exact_url_recurrence_is_citation_evidence_not_lineage(self):
        messages=fixture()
        for i,message in enumerate(messages[:12]):
            message["content"]="See https://example.org/telescope for the reference." if i < 6 else "My local note is ready."
        result=discover_graph_leads(messages,ROSTER,min_edge_events=3)
        feature=result["windows"][0]["features"]["shared_reference_rate"]
        self.assertEqual(feature["events"],6)
        self.assertEqual(len(feature["shared_resources"]),1)
        self.assertEqual(len(feature["shared_resources"][0]["author_ids"]),3)
        self.assertTrue(any("lineage is unobserved" in warning for warning in result["limitations"]))

    def test_bounded_real_village_window_and_empty_input_are_finite(self):
        root=Path(__file__).resolve().parents[1]
        data=json.loads((root/"examples/village-window.json").read_text(encoding="utf-8"))["dataset"]
        result=discover_graph_leads(data["messages"],data["agents"],min_edge_events=3)
        self.assertEqual(result["scope"]["message_count"],273)
        self.assertEqual(result["scope"]["room_count"],1)
        valid=set(result["evidence_index"])
        for lead in result["leads"]:
            self.assertTrue(set(lead["evidence_ids"]) <= valid)
        json.dumps(result,allow_nan=False)
        empty=discover_graph_leads([],ROSTER)
        self.assertEqual(empty["scope"]["analyzed_windows"],0)
        self.assertFalse(empty["leads"])

    def test_duplicate_ids_and_unbounded_configuration_rejected(self):
        messages=fixture()
        with self.assertRaises(ValueError):
            discover_graph_leads(messages+[messages[0]],ROSTER)
        for options in ({"window_minutes":1},{"stride_minutes":False},{"min_edge_events":0},{"max_windows":10000}):
            with self.assertRaises(ValueError):
                discover_graph_leads(messages,ROSTER,**options)


if __name__ == "__main__":
    unittest.main()
