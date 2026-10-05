import copy
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from swarm_lab.graph_discovery import discover_graph_leads
from swarm_lab.selected_lead_sensitivity import (
    SELECTED_LEAD_SENSITIVITY_VERSION, _graph,
    audit_selected_lead_name_sensitivity,
)


ROSTER = [
    {"id": "a", "name": "Alice"}, {"id": "b", "name": "Bobby"},
    {"id": "c", "name": "Carol"}, {"id": "g", "name": "GPT-4.1"},
    {"id": "three", "name": "o3"}, {"id": "one", "name": "o1"},
    {"id": "human-only", "name": "HumanOnly"},
]


def fixture():
    messages = []
    for hour in (10, 11):
        for i in range(12):
            actor = ("a", "b", "c")[i % 3]
            if hour == 10:
                text = {"a": "Bobby inspect this shared telescope artifact.",
                        "b": "Carol inspect this shared telescope artifact.",
                        "c": "My local shared telescope artifact is ready."}[actor]
                text += " GPT\u20114.1 o3."
            else:
                text = "Alice Bobby Carol inspect this shared telescope artifact. GPT-4.1 o3."
            text += " https://example.org/one https://example.org/two"
            stamp = datetime(2025, 4, 2, hour, 21, tzinfo=timezone.utc) + timedelta(minutes=i)
            messages.append({"id": f"{hour}-{i}", "agent_id": actor, "content": text,
                             "room_id": "lab", "timestamp": stamp.isoformat(),
                             "source": {"file": "selected_fixture.jsonl", "line": len(messages) + 1}})
    # Between agent messages, this human row interrupts lexical adjacency.
    messages.append({"id": "human-between", "speaker_id": "human",
                     "speaker_type": "user", "room_id": "lab",
                     "timestamp": "2025-04-02T10:21:30Z",
                     "content": "HumanOnly o1 GPT\u20114.1 are mentioned in this human row.",
                     "source": {"file": "selected_fixture.jsonl", "line": 25}})
    return messages


def make_search(messages=None, roster=None):
    return discover_graph_leads(messages if messages is not None else fixture(),
                                roster if roster is not None else ROSTER)


def run_audit(messages=None, search=None, roster=None, **options):
    messages = fixture() if messages is None else messages
    roster = ROSTER if roster is None else roster
    search = make_search(messages, roster) if search is None else search
    ids = [row["id"] for row in search["leads"]]
    return audit_selected_lead_name_sensitivity(
        messages, roster, search,
        selected_lead_ids=options.pop("selected_lead_ids", ids), **options)


class SelectedLeadSensitivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.messages = fixture()
        cls.search = make_search(cls.messages)
        cls.ids = [row["id"] for row in cls.search["leads"]]
        cls.result = run_audit(
            cls.messages, cls.search, short_name_allowlist=["o1", "o3"],
            include_unicode_shadow=True,
            source_refs=[{"id": "dataset-fixture", "version": 1, "hash": "host-declared"}])

    def test_registered_replay_orientation_rank_and_matching_frozen(self):
        result = self.result
        self.assertEqual(result["analysis_version"], SELECTED_LEAD_SENSITIVITY_VERSION)
        self.assertTrue({"incoming_concentration", "directed_reciprocity", "bridge_dependence"}
                        <= {row["feature"] for row in result["per_lead"]})
        self.assertEqual(result["frozen_selection"]["lead_ids"], self.ids)
        self.assertEqual(result["frozen_selection"]["variant_searches_performed"], 0)
        self.assertFalse(result["frozen_selection"]["selection_or_matching_changed"])
        for index, lead in enumerate(self.search["leads"]):
            measured = result["per_lead"][index]
            self.assertEqual(measured["registered"], lead)
            self.assertEqual(measured["original_rank"], index + 1)
            baseline = measured["native"]["baseline_exact"]
            self.assertEqual(baseline["difference"], lead["difference"])
            self.assertEqual(baseline["value"], lead["value"])
            self.assertEqual(baseline["comparison_value"], lead["comparison_value"])
            self.assertEqual(baseline["change_from_baseline"], 0)
            self.assertEqual(baseline["difference"], baseline["value"] - baseline["comparison_value"])
            self.assertEqual(measured["window_id"], lead["window_id"])
            self.assertEqual(measured["comparison_window_id"], lead["comparison_window_id"])

    def test_native_and_fixed_universes_are_distinct_and_policy_baselines_explicit(self):
        incoming = next(row for row in self.result["per_lead"] if row["feature"] == "incoming_concentration")
        candidate = incoming["window_id"]
        native = self.result["window_measurements"][candidate]["variants"]["baseline_exact"]
        pair = self.result["pair_diagnostics"][incoming["pair_id"]]
        fixed = pair["window_variants"][candidate]["baseline_exact"]
        self.assertNotEqual(native["node_universe"], fixed["node_universe"])
        self.assertNotEqual(incoming["universe_only_change"]["candidate_value"], 0)
        common = pair["node_universe"]["ids"]
        self.assertNotIn("human-only", common)
        self.assertNotIn("one", common)  # Only the human source mentions o1.
        self.assertIn("three", common)
        for graphs in pair["window_variants"].values():
            for graph in graphs.values():
                self.assertEqual(graph["node_universe"], common)
        fixed_baseline = incoming["fixed_pair"]["baseline_exact"]["difference"]
        for variant in incoming["fixed_pair"].values():
            if variant["available"]:
                self.assertAlmostEqual(variant["change_from_baseline"],
                                       variant["difference"] - fixed_baseline)

    def test_human_rows_preserved_but_graph_events_and_human_only_targets_excluded(self):
        self.assertEqual(self.result["scope"]["source_message_count"], 25)
        self.assertEqual(self.result["scope"]["all_source_human_message_count"], 1)
        local = next(row for row in self.result["window_measurements"].values()
                     if "human-between" in row["original_window"]["evidence_ids"])
        self.assertEqual(local["human_rows_preserved"], 1)
        for variant in local["variants"].values():
            self.assertGreater(variant["counts"]["excluded_human_source_event_count"], 0)
            self.assertNotIn("human-only", variant["node_universe"])
            self.assertNotIn("one", variant["node_universe"])
            self.assertTrue(all("human-between" not in edge["evidence_ids"] for edge in variant["edges"]))
        control = local["original_window"]["features"]["lexical_recurrence_rate"]
        for variant in local["variants"].values():
            self.assertEqual(variant["features"]["lexical_recurrence_rate"], control)

    def test_lexical_and_multiresource_url_controls_are_original_text_invariants(self):
        for identity, checks in self.result["negative_control_checks"].items():
            original = self.result["window_measurements"][identity]["original_window"]["features"]
            self.assertEqual(original["shared_reference_rate"]["value"], 2.0)
            self.assertEqual(original["shared_reference_rate"]["events"], 24)
            for variant in checks.values():
                self.assertTrue(all(row["unchanged"] for row in variant.values()))
            for variant in self.result["window_measurements"][identity]["variants"].values():
                for name in ("lexical_recurrence_rate", "shared_reference_rate"):
                    self.assertEqual(variant["features"][name], original[name])

    def test_unicode_shadow_delta_has_truthful_coordinates_and_no_original_mapping(self):
        local = next(row for row in self.result["window_measurements"].values()
                     if row["original_window"]["start"].startswith("2025-04-02T10:"))
        added = local["agent_event_deltas"]["unicode_baseline"]["added"]
        self.assertEqual(len(added), 12)
        for event in added:
            self.assertEqual(event["target_agent_id"], "g")
            self.assertFalse(event["original_span_available"])
            self.assertEqual(event["span"]["coordinates"], "shadow_text_python_codepoints")
            source = local["eligibility_audit"]["evidence_index"][event["message_id"]]
            self.assertEqual(source["shadow_text"][event["span"]["start"]:event["span"]["end"]],
                             event["match_text"])

    def test_short_candidates_are_once_per_message_target_with_original_offsets(self):
        for local in self.result["window_measurements"].values():
            short = local["agent_event_deltas"]["explicit_short_expanded_exact"]["added"]
            self.assertEqual(len(short), 12)
            self.assertEqual({event["target_agent_id"] for event in short}, {"three"})
            for event in short:
                self.assertTrue(event["original_span_available"])
                self.assertEqual(event["status"], "explicit_short_name_match_candidate")
                self.assertEqual(event["span"]["coordinates"], "original_content_python_codepoints")
                source = local["eligibility_audit"]["evidence_index"][event["message_id"]]
                self.assertEqual(source["content"][event["span"]["start"]:event["span"]["end"]],
                                 event["match_text"])

    def test_reciprocity_decomposition_distinguishes_numerator_and_event_denominator(self):
        for local in self.result["window_measurements"].values():
            baseline = local["variants"]["baseline_exact"]["features"]["directed_reciprocity"]
            expanded = local["variants"]["explicit_short_expanded_exact"]["features"]["directed_reciprocity"]
            self.assertEqual(baseline["decomposition"]["reciprocal_numerator"],
                             expanded["decomposition"]["reciprocal_numerator"])
            self.assertGreater(expanded["decomposition"]["total_mention_events"],
                               baseline["decomposition"]["total_mention_events"])
            self.assertLessEqual(expanded["value"], baseline["value"])
        lead = next(row for row in self.result["per_lead"] if row["feature"] == "directed_reciprocity")
        self.assertNotEqual(lead["native"]["baseline_exact"]["difference"],
                            lead["native"]["explicit_short_expanded_exact"]["difference"])

    def test_unobserved_targets_have_unknown_outgoing_rates(self):
        pair = next(iter(self.result["pair_diagnostics"].values()))
        self.assertIn("three", pair["node_universe"]["target_ids_without_authored_messages_in_either_window"])
        for graphs in pair["window_variants"].values():
            for graph in graphs.values():
                target = next(row for row in graph["metrics"]["nodes"] if row["id"] == "three")
                self.assertEqual(target["authored_message_count"], 0)
                self.assertIsNone(target["outgoing_interactions_per_authored_message"])
                self.assertIsNone(target["incoming_interactions_per_coactive_message"])

    def test_default_allowlist_and_unrequested_shadow_do_not_widen_or_fabricate(self):
        result = run_audit(self.messages, self.search)
        self.assertEqual(result["configuration"]["short_name_allowlist"], [])
        for row in result["per_lead"]:
            self.assertEqual(row["native"]["baseline_exact"]["difference"],
                             row["native"]["explicit_short_expanded_exact"]["difference"])
            for name in ("unicode_baseline", "unicode_expanded"):
                self.assertFalse(row["native"][name]["available"])
                self.assertIsNone(row["native"][name]["difference"])
                self.assertFalse(row["fixed_pair"][name]["available"])

    def test_short_mentions_can_reverse_signed_contrast_without_relabeling(self):
        messages = fixture()
        messages = [row for row in messages if row.get("speaker_type") != "user"]
        for row in messages:
            actor = row["agent_id"]
            if row["id"].startswith("10-"):
                row["content"] = ("Bobby review the shared artifact." if actor != "b"
                                  else "My shared artifact is ready.") + " o1 o3"
            else:
                row["content"] = "Carol review the shared artifact." if actor == "b" else "Bobby review the shared artifact."
        search = make_search(messages)
        result = run_audit(messages, search, short_name_allowlist=["o1", "o3"])
        lead = next(row for row in result["per_lead"] if row["feature"] == "incoming_concentration")
        baseline = lead["native"]["baseline_exact"]
        expanded = lead["native"]["explicit_short_expanded_exact"]
        self.assertLess(baseline["difference"] * expanded["difference"], 0)
        self.assertNotEqual(baseline["direction"], expanded["direction"])
        self.assertFalse(expanded["same_difference_direction_as_policy_baseline"])
        self.assertEqual(lead["registered"]["status"], "exploratory_lead")
        self.assertFalse(result["frozen_selection"]["selection_or_matching_changed"])

    def test_short_events_outside_selected_windows_never_change_local_leads(self):
        messages = fixture()
        for row in messages:
            row["content"] = row["content"].replace("o3", "")
        messages.append({"id": "outside-selected", "agent_id": "a", "room_id": "unmatched-room",
                         "timestamp": "2025-04-03T10:10:00Z", "content": "o3"})
        search = make_search(messages)
        result = run_audit(messages, search, short_name_allowlist=["o3"])
        self.assertEqual(result["scope"]["selected_window_count"], 2)
        self.assertEqual(result["frozen_selection"]["original_source_scope"]["analyzed_windows"], 3)
        for row in result["per_lead"]:
            self.assertEqual(row["native"]["baseline_exact"]["difference"],
                             row["native"]["explicit_short_expanded_exact"]["difference"])
        for window in result["window_measurements"].values():
            self.assertFalse(window["agent_event_deltas"]["explicit_short_expanded_exact"]["added"])
            self.assertNotIn("three", window["variants"]["explicit_short_expanded_exact"]["node_universe"])

    def test_ambiguous_short_names_unknown_and_not_promoted_to_graphs(self):
        roster = ROSTER + [{"id": "other-three", "name": "O3"}]
        result = run_audit(roster=roster, short_name_allowlist=["o3"], include_unicode_shadow=True)
        for local in result["window_measurements"].values():
            self.assertGreater(local["eligibility_audit"]["summary"]["ambiguous_exact_event_count"], 0)
            for graph in local["variants"].values():
                self.assertNotIn("three", graph["node_universe"])
                self.assertNotIn("other-three", graph["node_universe"])

    def test_shadow_undefined_features_remain_none_and_support_does_not_rematch(self):
        messages = fixture()
        for row in messages:
            row["content"] = row["content"].replace("GPT-4.1", "").replace("GPT\u20114.1", "").replace("o3", "")
        roster = ROSTER + [{"id": "alias-a", "name": "\uff21lice"},
                           {"id": "alias-b", "name": "\uff22obby"},
                           {"id": "alias-c", "name": "\uff23arol"}]
        search = make_search(messages, roster)
        result = run_audit(messages, search, roster, include_unicode_shadow=True)
        for row in result["per_lead"]:
            self.assertEqual(row["registered"], next(lead for lead in search["leads"] if lead["id"] == row["lead_id"]))
            shadow = row["native"]["unicode_baseline"]
            if row["feature"] in ("lexical_recurrence_rate", "shared_reference_rate"):
                self.assertEqual(shadow["difference"], row["registered"]["difference"])
                continue
            self.assertFalse(shadow["available"])
            self.assertIsNone(shadow["difference"])
            self.assertFalse(shadow["supported"])
            self.assertEqual(shadow["direction"], "undefined")
        json.dumps(result, allow_nan=False)

    def test_half_open_boundaries_include_all_original_human_rows(self):
        messages = fixture() + [
            {"id": "boundary-end", "speaker_type": "user", "speaker_id": "human", "room_id": "lab",
             "timestamp": "2025-04-02T11:00:00Z", "content": "HumanOnly"},
            {"id": "boundary-before", "speaker_type": "user", "speaker_id": "human", "room_id": "lab",
             "timestamp": "2025-04-02T10:59:59.999999Z", "content": "HumanOnly"},
        ]
        result = run_audit(messages)
        for local in result["window_measurements"].values():
            ids = local["original_window"]["evidence_ids"]
            if local["original_window"]["start"].startswith("2025-04-02T10:"):
                self.assertIn("boundary-before", ids)
                self.assertNotIn("boundary-end", ids)
            else:
                self.assertIn("boundary-end", ids)
                self.assertNotIn("boundary-before", ids)

    def test_exact_replay_rejects_tampered_numbers_and_semantics_not_only_digits(self):
        for mutate in (
            lambda packet: packet["leads"][0].update(difference=999),
            lambda packet: packet["leads"][0]["comparison_match"].update(causal_control=True),
            lambda packet: packet["windows"][0]["features"]["incoming_concentration"].update(events=True),
            lambda packet: packet["leads"].reverse(),
            lambda packet: packet["selection"].update(confirmatory=True),
            lambda packet: packet["leads"][0].update(comparison_evidence_ids=["fabricated"]),
        ):
            packet = copy.deepcopy(self.search)
            mutate(packet)
            with self.subTest(mutation=mutate):
                with self.assertRaisesRegex(ValueError, "baseline_replay_mismatch"):
                    run_audit(self.messages, packet)

    def test_changed_source_context_roster_or_human_filter_fails_closed(self):
        for field, value in (("content", "different"), ("room_id", "elsewhere"),
                             ("timestamp", "2025-04-02T15:00:00Z"),
                             ("agent_id", "c"), ("source", {"file": "changed"})):
            messages = copy.deepcopy(self.messages)
            messages[0][field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "baseline_replay_mismatch"):
                    run_audit(messages, self.search)
        with self.assertRaisesRegex(ValueError, "baseline_replay_mismatch"):
            run_audit([row for row in self.messages if row.get("speaker_type") != "user"], self.search)
        with self.assertRaisesRegex(ValueError, "baseline_replay_mismatch"):
            run_audit(self.messages, self.search, [{**row, "name": "Changed"} if row["id"] == "b" else row
                                                   for row in ROSTER])

    def test_only_selected_leads_and_original_order_allowed(self):
        chosen = list(reversed(self.ids))
        result = run_audit(self.messages, self.search, selected_lead_ids=chosen)
        self.assertEqual(result["frozen_selection"]["requested_lead_ids"], chosen)
        self.assertEqual([row["lead_id"] for row in result["per_lead"]], self.ids)
        for ids in ([], [self.ids[0], self.ids[0]], ["unselected-id"], self.ids * 5, [False]):
            with self.subTest(ids=ids):
                with self.assertRaises(ValueError):
                    run_audit(self.messages, self.search, selected_lead_ids=ids)

    def test_invalid_finite_input_and_instrument_bounds_rejected(self):
        for field, value in (("analysis_version", "future-instrument"),):
            changed = {**self.search, field: value}
            with self.assertRaises(ValueError):
                run_audit(self.messages, changed)
        for field, value in (("max_windows", 121), ("max_leads", 13), ("seed", True)):
            changed = copy.deepcopy(self.search)
            changed["configuration"][field] = value
            with self.assertRaises(ValueError):
                run_audit(self.messages, changed)
        changed = copy.deepcopy(self.search)
        changed["configuration"]["features"]["incoming_concentration"]["minimum_delta"] = 0
        with self.assertRaisesRegex(ValueError, "feature definitions"):
            run_audit(self.messages, changed)
        changed = copy.deepcopy(self.search)
        changed["leads"][0]["value"] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite JSON"):
            run_audit(self.messages, changed)
        with self.assertRaises(ValueError):
            run_audit(self.messages, self.search, short_name_allowlist=["fuzzy-Alice"])
        with self.assertRaises(ValueError):
            run_audit(self.messages, self.search, include_unicode_shadow=1)

    def test_single_legacy_replay_no_variant_search_or_mutation(self):
        messages, roster, search = copy.deepcopy(self.messages), copy.deepcopy(ROSTER), copy.deepcopy(self.search)
        refs = [{"id": "declared-source", "version": 2, "hash": "opaque"}]
        originals = copy.deepcopy((messages, roster, search, refs))
        with patch("swarm_lab.selected_lead_sensitivity.discover_graph_leads",
                   wraps=discover_graph_leads) as replay:
            result = run_audit(messages, search, roster, short_name_allowlist=["o3"],
                               include_unicode_shadow=True, source_refs=refs)
        self.assertEqual(replay.call_count, 1)
        self.assertEqual((messages, roster, search, refs), originals)
        self.assertEqual(result["source_refs"], refs)
        self.assertFalse(result["source_binding"]["source_refs_external_authentication"])
        result["source_refs"][0]["hash"] = "edited-output"
        result["per_lead"][0]["registered"]["difference"] = 999
        self.assertEqual((messages, roster, search, refs), originals)
        self.assertEqual(result["model_calls"], 0)
        self.assertTrue(result["read_only"])
        json.dumps(result, allow_nan=False)

    def test_deterministic_for_reversed_source_and_roster_order(self):
        first = run_audit(self.messages, self.search, short_name_allowlist=["o3"], include_unicode_shadow=True)
        second = run_audit(list(reversed(self.messages)), self.search, list(reversed(ROSTER)),
                           short_name_allowlist=["o3"], include_unicode_shadow=True)
        self.assertEqual(first, second)

    def test_bridge_undefined_to_zero_isolate_change_explicit(self):
        original = {
            "authored_agent_message_count": 1, "agent_author_count": 1,
            "features": {"lexical_recurrence_rate": {"value": 0, "events": 0, "evidence_ids": []},
                         "shared_reference_rate": {"value": 0, "events": 0, "evidence_ids": []}},
        }
        message = {"id": "edge", "agent_id": "a", "room_id": "lab"}
        event = {"source": "a", "target": "b", "timestamp": "2025-04-02T10:00:00Z",
                 "evidence_ids": ["edge"], "measurement_event": {"status": "candidate"}}
        two = _graph([message], ["a", "b"], [event], original, variant="baseline_exact", excluded=[])
        three = _graph([message], ["a", "b", "c"], [event], original, variant="baseline_exact", excluded=[])
        self.assertIsNone(two["features"]["bridge_dependence"]["value"])
        self.assertEqual(three["features"]["bridge_dependence"]["value"], 0)
        self.assertEqual(two["features"]["directed_reciprocity"]["value"],
                         three["features"]["directed_reciprocity"]["value"])
        many = _graph([message], ["a", "b"] + [f"isolated-{i}" for i in range(127)], [event],
                      original, variant="baseline_exact", excluded=[])
        self.assertFalse(many["features"]["bridge_dependence"]["decomposition"]["operator_available"])
        self.assertIsNone(many["features"]["bridge_dependence"]["value"])


if __name__ == "__main__":
    unittest.main()
