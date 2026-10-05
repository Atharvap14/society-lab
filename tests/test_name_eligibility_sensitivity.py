import copy
import hashlib
import json
import unittest
from unittest.mock import patch

from swarm_lab.discovery import build_graph
from swarm_lab.mention_sensitivity import audit_mention_sensitivity
from swarm_lab.name_eligibility_sensitivity import (
    NAME_ELIGIBILITY_SENSITIVITY_VERSION, audit_name_eligibility_sensitivity,
)


ROSTER = [{"id": "a", "name": "Alice"}, {"id": "g", "name": "GPT-4.1"},
          {"id": "three", "name": "o3"}, {"id": "one", "name": "o1"}]


def row(identity, text, *, agent="a", minute=0, **extra):
    return {"id": identity, "agent_id": agent, "speaker_type": "agent",
            "content": text, "room_id": "lab", "timestamp": f"2025-04-20T10:{minute:02}:00Z",
            **extra}


def keys(events):
    return {(event["message_id"], event["target_agent_id"]) for event in events}


def fixture():
    return [row("m1", "GPT-4.1 o3 and o1"),
            row("m2", "GPT\u20114.1 o3", minute=1),
            row("m3", "o3 o1", agent="three", minute=2),
            row("m4", "xo3 o3x _o1 o1_ o33 o10", minute=3),
            row("m5", "o3 o3", minute=4),
            row("m6", "GPT-4.1", minute=5)]


class NameEligibilitySensitivityTests(unittest.TestCase):
    def test_default_allowlist_never_widens_minimum_three_baseline(self):
        result = audit_name_eligibility_sensitivity(fixture(), ROSTER)
        self.assertEqual(result["summary"]["baseline_exact_event_count"], 2)
        self.assertEqual(result["summary"]["short_candidate_exact_event_count"], 0)
        self.assertEqual(result["summary"]["expanded_exact_candidate_event_count"], 2)
        self.assertFalse(result["requested_names"])
        self.assertFalse(result["resolved_agent_ids"])
        self.assertFalse(result["short_name_exact_events"])
        self.assertFalse(result["unicode_shadow"]["enabled"])
        self.assertFalse(result["eligibility_policy"]["default_widening"])
        self.assertFalse(result["eligibility_policy"]["graph_edges_created"])

    def test_explicit_o1_o3_exact_delta_preserves_baseline_and_self_exclusions(self):
        result = audit_name_eligibility_sensitivity(fixture(), ROSTER, short_name_allowlist=["o1", "o3"])
        self.assertEqual(result["summary"]["baseline_exact_event_count"], 2)
        self.assertEqual(result["summary"]["short_candidate_exact_event_count"], 5)
        self.assertEqual(result["summary"]["explicit_short_name_delta_count"], 5)
        self.assertEqual(result["summary"]["expanded_exact_candidate_event_count"], 7)
        self.assertEqual(result["resolved_agent_ids"], ["one", "three"])
        self.assertEqual(keys(result["short_name_exact_events"]),
                         {("m1", "one"), ("m1", "three"), ("m2", "three"), ("m3", "one"), ("m5", "three")})
        self.assertEqual(result["analysis_version"], NAME_ELIGIBILITY_SENSITIVITY_VERSION)
        self.assertTrue(all(event["status"] == "explicit_short_name_match_candidate"
                            for event in result["short_name_exact_events"]))
        self.assertNotIn("edges", result)

    def test_exact_baseline_is_identical_to_existing_graph_and_measurement_module(self):
        messages = fixture()
        result = audit_name_eligibility_sensitivity(messages, ROSTER, short_name_allowlist=["o3"])
        old = audit_mention_sensitivity(messages, ROSTER)
        self.assertEqual(result["baseline_exact_events"], old["exact_events"])
        graph_keys = {(edge["source"].removeprefix("message:"), edge["target"].removeprefix("speaker:"))
                      for edge in build_graph(messages, ROSTER)["edges"] if edge["kind"] == "mentions"}
        self.assertEqual(keys(result["baseline_exact_events"]), graph_keys)
        self.assertEqual(result["source_fingerprint"], old["source_fingerprint"])
        self.assertEqual(result["roster_fingerprint"], old["roster_fingerprint"])

    def test_optional_shadow_separates_name_length_and_unicode_deltas(self):
        result = audit_name_eligibility_sensitivity(fixture(), ROSTER,
                                                    short_name_allowlist=["o1", "o3"],
                                                    include_unicode_shadow=True)
        shadow = result["unicode_shadow"]
        self.assertEqual(shadow["summary"]["baseline_shadow_event_count"], 3)
        self.assertEqual(shadow["summary"]["short_candidate_shadow_event_count"], 5)
        self.assertEqual(shadow["summary"]["expanded_shadow_candidate_event_count"], 8)
        self.assertEqual(shadow["summary"]["expanded_shadow_minus_expanded_exact_count"], 1)
        self.assertEqual(shadow["summary"]["short_shadow_minus_short_exact_count"], 0)
        self.assertEqual(keys(shadow["baseline_delta_events"]["shadow_only"]), {("m2", "g")})
        self.assertFalse(shadow["short_name_delta_events"]["shadow_only"])
        self.assertTrue(result["normalization_policy"]["comparison_requested"])

    def test_fullwidth_short_source_is_only_an_optional_shadow_candidate(self):
        result = audit_name_eligibility_sensitivity([row("m1", "\uff4f\uff13")], ROSTER,
                                                    short_name_allowlist=["o3"], include_unicode_shadow=True)
        self.assertFalse(result["short_name_exact_events"])
        self.assertEqual(keys(result["unicode_shadow"]["short_name_shadow_events"]), {("m1", "three")})
        self.assertEqual(result["unicode_shadow"]["summary"]["short_shadow_minus_short_exact_count"], 1)
        self.assertEqual(keys(result["unicode_shadow"]["short_name_delta_events"]["shadow_only"]), {("m1", "three")})

    def test_original_and_normalized_span_coordinates_are_truthful(self):
        text = " \t\ufb03\n o3"
        result = audit_name_eligibility_sensitivity([row("m1", text)], ROSTER,
                                                    short_name_allowlist=["o3"], include_unicode_shadow=True)
        exact = result["short_name_exact_events"][0]
        shadow = result["unicode_shadow"]["short_name_shadow_events"][0]
        self.assertEqual(exact["span"]["coordinates"], "original_content_python_codepoints")
        self.assertEqual(exact["span"]["start"], text.index("o3"))
        self.assertTrue(exact["original_span_available"])
        self.assertEqual(shadow["span"]["coordinates"], "shadow_text_python_codepoints")
        self.assertEqual(shadow["span"]["start"], 4)
        self.assertFalse(shadow["original_span_available"])
        self.assertNotIn("original_span", shadow)
        for event, source_text in [(exact, text), (shadow, result["evidence_index"]["m1"]["shadow_text"])]:
            span = event["span"]
            self.assertEqual(source_text[span["start"]:span["end"]], event["match_text"])
        self.assertNotEqual(exact["span"]["start"], shadow["span"]["start"])

    def test_duplicate_requests_and_repeated_text_do_not_duplicate_events(self):
        result = audit_name_eligibility_sensitivity([row("m1", "O3 o3 o3")], ROSTER,
                                                    short_name_allowlist=["o3", "O3", "o3"])
        self.assertEqual(result["summary"]["short_candidate_exact_event_count"], 1)
        self.assertEqual(result["summary"]["duplicate_resolved_request_count"], 2)
        self.assertEqual(result["summary"]["requested_name_count"], 3)
        self.assertEqual(result["requested_names"], ["o3", "O3", "o3"])
        self.assertEqual(result["allowlist_resolution"][1]["duplicate_of_request_index"], 0)
        self.assertEqual(result["short_name_exact_events"][0]["span"]["start"], 0)

    def test_original_regex_collision_is_unknown_and_not_self_disambiguated(self):
        roster = [{"id": "x", "name": "o3"}, {"id": "y", "name": "O3"}]
        result = audit_name_eligibility_sensitivity([row("m1", "o3", agent="x")], roster,
                                                    short_name_allowlist=["o3", "O3"], include_unicode_shadow=True)
        self.assertFalse(result["resolved_agent_ids"])
        self.assertFalse(result["short_name_exact_events"])
        self.assertEqual(result["summary"]["ambiguous_exact_event_count"], 1)
        self.assertTrue(all(entry["status"] == "ambiguous_unknown_target" for entry in result["allowlist_resolution"]))
        unknown = result["ambiguous_exact_events"][0]
        self.assertIsNone(unknown["target_agent_id"])
        self.assertEqual(unknown["candidate_agent_ids"], ["x", "y"])
        self.assertEqual(unknown["eligible_nonself_candidate_ids"], ["y"])
        self.assertEqual(result["unicode_shadow"]["summary"]["ambiguous_short_shadow_event_count"], 1)
        self.assertFalse(result["unicode_shadow"]["short_name_shadow_events"])

    def test_shadow_collision_with_unrequested_roster_name_stays_unknown(self):
        roster = [{"id": "x", "name": "o3"}, {"id": "y", "name": "\uff4f\uff13"}]
        result = audit_name_eligibility_sensitivity([row("m1", "o3")], roster,
                                                    short_name_allowlist=["o3"], include_unicode_shadow=True)
        self.assertEqual(result["resolved_agent_ids"], ["x"])
        self.assertEqual(keys(result["short_name_exact_events"]), {("m1", "x")})
        self.assertFalse(result["unicode_shadow"]["short_name_shadow_events"])
        unknown = result["unicode_shadow"]["ambiguous_short_shadow_events"][0]
        self.assertEqual(unknown["candidate_agent_ids"], ["x", "y"])
        self.assertEqual(unknown["eligible_nonself_candidate_ids"], ["x"])
        self.assertIsNone(unknown["target_agent_id"])
        self.assertEqual(result["unicode_shadow"]["summary"]["short_shadow_minus_short_exact_count"], -1)

    def test_short_unicode_case_collisions_use_regex_equivalence(self):
        roster = [{"id": "x", "name": "i"}, {"id": "y", "name": "\u0131"}]
        result = audit_name_eligibility_sensitivity([row("m1", "i")], roster,
                                                    short_name_allowlist=["i"], include_unicode_shadow=True)
        self.assertFalse(result["resolved_agent_ids"])
        self.assertEqual(result["summary"]["ambiguous_exact_event_count"], 1)
        self.assertEqual(result["ambiguous_exact_events"][0]["candidate_agent_ids"], ["x", "y"])
        self.assertEqual(result["ambiguous_exact_events"][0]["span"],
                         {"start": 0, "end": 1, "coordinates": "original_content_python_codepoints"})
        result["allowlist_resolution"][0]["candidate_agent_ids"].append("changed")
        self.assertEqual(result["original_roster_collisions"][0]["candidate_agent_ids"], ["x", "y"])

    def test_short_casefold_expansion_does_not_create_false_regex_collision(self):
        roster = [{"id": "x", "name": "\u00df"}, {"id": "y", "name": "ss"}]
        result = audit_name_eligibility_sensitivity([row("m1", "\u00df ss")], roster,
                                                    short_name_allowlist=["\u00df", "ss"], include_unicode_shadow=True)
        self.assertEqual(result["resolved_agent_ids"], ["x", "y"])
        self.assertEqual(result["summary"]["short_candidate_exact_event_count"], 2)
        self.assertEqual(result["unicode_shadow"]["summary"]["short_candidate_shadow_event_count"], 2)
        self.assertFalse(result["original_roster_collisions"])

    def test_missing_id_name_and_nonrequested_names_never_silently_resolve(self):
        roster = [{"id": "o3", "name": "o3"}, {"id": "one", "name": "o1"}]
        result = audit_name_eligibility_sensitivity([row("m1", "o3 o1 o2")], roster,
                                                    short_name_allowlist=["o3", "o2"])
        self.assertFalse(result["short_name_exact_events"])
        self.assertEqual([entry["status"] for entry in result["allowlist_resolution"]],
                         ["excluded_display_name_equals_id", "not_found_in_original_roster_names"])
        self.assertFalse(result["resolved_agent_ids"])

    def test_no_fuzzy_semantic_or_zero_width_aliases(self):
        result = audit_name_eligibility_sensitivity(
            [row("m1", "OpenAI three o\u200b3 o-3 xo3 o3x _o1 o1_")], ROSTER,
            short_name_allowlist=["o1", "o3"], include_unicode_shadow=True)
        self.assertFalse(result["short_name_exact_events"])
        self.assertFalse(result["unicode_shadow"]["short_name_shadow_events"])
        # The allowlist itself is resolved against original names, not normalized aliases.
        missing = audit_name_eligibility_sensitivity([], ROSTER, short_name_allowlist=["\uff4f\uff13"])
        self.assertEqual(missing["allowlist_resolution"][0]["status"], "not_found_in_original_roster_names")

    def test_human_speaker_and_quoted_tokens_match_without_address_inference(self):
        result = audit_name_eligibility_sensitivity(
            [row("m1", '"o3" is a model label.', agent="human", speaker_type="user")], ROSTER,
            short_name_allowlist=["o3"])
        event = result["short_name_exact_events"][0]
        self.assertIsNone(event["author_agent_id"])
        self.assertEqual(event["speaker_type"], "user")
        self.assertEqual(event["status"], "explicit_short_name_match_candidate")
        self.assertIn("unverified", event["interpretation"])

    def test_observed_name_fallback_and_source_preservation_without_mutation(self):
        messages = [row("m1", "my o3 note", agent="q", agent_name="o3"),
                    row("m2", "o3 please inspect", minute=1, content_hash="opaque-original",
                        source={"file": "chat.jsonl", "line": 42, "nested": {"pin": "source-1"}})]
        before = copy.deepcopy(messages)
        result = audit_name_eligibility_sensitivity(messages, [{"id": "a", "name": "Alice"}],
                                                    short_name_allowlist=["o3"], include_unicode_shadow=True)
        self.assertEqual(result["resolved_agent_ids"], ["q"])
        self.assertEqual(keys(result["short_name_exact_events"]), {("m2", "q")})
        evidence = result["evidence_index"]["m2"]
        self.assertEqual(evidence["content"], messages[1]["content"])
        self.assertEqual(evidence["content_hash"], "opaque-original")
        self.assertEqual(evidence["content_hash_origin"], "provided_unverified")
        self.assertEqual(evidence["source"], messages[1]["source"])
        self.assertEqual(evidence["original_content_sha256"],
                         hashlib.sha256(messages[1]["content"].encode("utf-8")).hexdigest())
        self.assertEqual(messages, before)
        evidence["source"]["nested"]["pin"] = "changed"
        self.assertEqual(messages[1]["source"]["nested"]["pin"], "source-1")

    def test_determinism_empty_inputs_and_truthful_record_binding(self):
        first = audit_name_eligibility_sensitivity(fixture(), ROSTER,
                                                   short_name_allowlist=["o1", "o3"], include_unicode_shadow=True)
        second = audit_name_eligibility_sensitivity(list(reversed(fixture())), list(reversed(ROSTER)),
                                                    short_name_allowlist=["o1", "o3"], include_unicode_shadow=True)
        self.assertEqual(first, second)
        json.dumps(first, allow_nan=False)
        empty = audit_name_eligibility_sensitivity([], short_name_allowlist=["o3"])
        self.assertEqual(empty["summary"]["baseline_exact_event_count"], 0)
        self.assertFalse(empty["short_name_exact_events"])
        message = row("m1", "o3", content_hash="opaque-fixed")
        before = audit_name_eligibility_sensitivity([message], ROSTER, short_name_allowlist=["o3"])
        after = audit_name_eligibility_sensitivity([{**message, "agent_id": "one"}], ROSTER,
                                                    short_name_allowlist=["o3"])
        self.assertNotEqual(before["source_fingerprint"], after["source_fingerprint"])

    def test_invalid_allowlist_flags_and_inherited_bounds(self):
        for request in ["", "o 3", "o-", "GPT", "o3\n", "++", 123, None]:
            with self.subTest(request=request):
                with self.assertRaises(ValueError):
                    audit_name_eligibility_sensitivity([], short_name_allowlist=[request])
        with self.assertRaises(ValueError):
            audit_name_eligibility_sensitivity([], short_name_allowlist="o3")
        with self.assertRaises(ValueError):
            audit_name_eligibility_sensitivity([], include_unicode_shadow=1)
        with patch("swarm_lab.name_eligibility_sensitivity.MAX_ALLOWLIST_REQUESTS", 1):
            with self.assertRaises(ValueError):
                audit_name_eligibility_sensitivity([], short_name_allowlist=["o1", "o3"])
        with self.assertRaises(ValueError):
            audit_name_eligibility_sensitivity([row("m1", "one"), row("m1", "two")])
        with self.assertRaises(ValueError):
            audit_name_eligibility_sensitivity([], [{"id": "x", "name": "o1"}, {"id": "x", "name": "o3"}])


if __name__ == "__main__":
    unittest.main()
