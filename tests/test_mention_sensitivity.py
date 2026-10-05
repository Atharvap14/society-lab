import copy
import hashlib
import json
import unittest
from unittest.mock import patch

from swarm_lab.discovery import build_graph
from swarm_lab.mention_sensitivity import (
    MENTION_SENSITIVITY_VERSION, audit_mention_sensitivity, normalize_shadow_text,
)


ROSTER = [
    {"id": "a", "name": "Alice"},
    {"id": "gpt", "name": "GPT-4.1"},
    {"id": "thinker", "name": "Deep Thinker"},
    {"id": "ab", "name": "AB"},
    {"id": "opaque-id", "name": "opaque-id"},
]


def row(identity, text, *, agent="a", minute=0, **extra):
    return {"id": identity, "agent_id": agent, "speaker_type": "agent",
            "content": text, "room_id": "lab", "timestamp": f"2025-04-20T10:{minute:02}:00Z",
            **extra}


def keys(events):
    return {(event["message_id"], event["target_agent_id"]) for event in events}


class MentionSensitivityTests(unittest.TestCase):
    def test_exact_instrument_matches_existing_graph_including_first_span(self):
        messages = [
            row("m1", "Alice, GPT-4.1 and gpt-4.1; Deep Thinker, AB, opaque-id."),
            row("m2", "xGPT-4.1 GPT-4.1x _GPT-4.1 GPT-4.1_"),
            row("m3", '"GPT-4.1" is a quotation.', agent="gpt"),
            row("m4", "GPT-4.1 has a note.", agent="human", speaker_type="user"),
        ]
        expected = [edge for edge in build_graph(messages, ROSTER)["edges"] if edge["kind"] == "mentions"]
        result = audit_mention_sensitivity(messages, ROSTER)
        got = {(event["message_id"], event["target_agent_id"]):
               (event["span"]["start"], event["span"]["end"]) for event in result["exact_events"]}
        want = {(edge["source"].removeprefix("message:"), edge["target"].removeprefix("speaker:")):
                (edge["span"]["start"], edge["span"]["end"]) for edge in expected}
        self.assertEqual(got, want)
        self.assertEqual(keys(result["exact_events"]), {("m1", "gpt"), ("m1", "thinker"), ("m4", "gpt")})
        human = next(event for event in result["exact_events"] if event["message_id"] == "m4")
        self.assertIsNone(human["author_agent_id"])
        self.assertEqual(human["speaker_type"], "user")

    def test_nonbreaking_hyphen_yields_separate_shadow_delta(self):
        result = audit_mention_sensitivity([row("m1", "GPT\u20114.1, can you inspect?")], ROSTER)
        self.assertEqual(result["summary"]["exact_event_count"], 0)
        self.assertEqual(result["summary"]["shadow_event_count"], 1)
        self.assertEqual(result["summary"]["shadow_minus_exact_count"], 1)
        self.assertEqual(keys(result["delta_events"]["shadow_only"]), {("m1", "gpt")})
        self.assertFalse(result["delta_events"]["exact_only"])
        self.assertEqual(result["analysis_version"], MENTION_SENSITIVITY_VERSION)
        event = result["shadow_events"][0]
        self.assertEqual(event["match_text"], "GPT-4.1")
        self.assertEqual(event["status"], "formatting_match_candidate")
        self.assertNotIn("edges", result)

    def test_nfkc_dash_and_whitespace_transformations_are_explicit(self):
        text = "  \uff27\uff30\uff34\uff0d\uff14\uff0e\uff11\nDeep\u00a0\tThinker "
        result = audit_mention_sensitivity([row("m1", text)], ROSTER)
        self.assertFalse(result["exact_events"])
        self.assertEqual(keys(result["shadow_events"]), {("m1", "gpt"), ("m1", "thinker")})
        entry = result["evidence_index"]["m1"]
        self.assertEqual(entry["shadow_text"], "GPT-4.1 Deep Thinker")
        self.assertEqual(entry["content"], text)
        self.assertTrue(entry["transformations_applied"]["nfkc_changed"])
        self.assertTrue(entry["transformations_applied"]["whitespace_changed"])
        self.assertIn("U+2011", result["transformation_definitions"]["dash_variants"])

    def test_shadow_spans_are_only_normalized_coordinates(self):
        text = " \t\ufb03\n GPT\u20114.1 "
        result = audit_mention_sensitivity([row("m1", text)], ROSTER)
        event = result["shadow_events"][0]
        shadow = result["evidence_index"]["m1"]["shadow_text"]
        self.assertEqual(shadow, "ffi GPT-4.1")
        self.assertEqual(event["span"], {"start": 4, "end": 11,
                                         "coordinates": "shadow_text_python_codepoints"})
        self.assertNotEqual(event["span"]["start"], text.index("GPT"))
        self.assertEqual(shadow[event["span"]["start"]:event["span"]["end"]], event["match_text"])
        self.assertFalse(event["original_span_available"])
        self.assertNotIn("original_span", event)

    def test_normalized_collision_is_unknown_and_exact_stays_intact(self):
        roster = [{"id": "x", "name": "GPT-4.1"}, {"id": "y", "name": "GPT\u20114.1"}]
        result = audit_mention_sensitivity([row("m1", "GPT-4.1 please check")], roster)
        self.assertEqual(keys(result["exact_events"]), {("m1", "x")})
        self.assertFalse(result["shadow_events"])
        self.assertEqual(result["summary"]["exact_only_event_count"], 1)
        self.assertEqual(result["summary"]["collision_excluded_eligible_agent_count"], 2)
        collision = result["normalized_roster_collisions"][0]
        self.assertEqual(collision["agent_ids"], ["x", "y"])
        ambiguity = result["ambiguous_shadow_events"][0]
        self.assertIsNone(ambiguity["target_agent_id"])
        self.assertEqual(ambiguity["candidate_agent_ids"], ["x", "y"])
        self.assertEqual(ambiguity["status"], "ambiguous_unknown_target")

    def test_collision_not_resolved_by_excluding_the_self_candidate(self):
        roster = [{"id": "x", "name": "GPT-4.1"}, {"id": "y", "name": "GPT\u20114.1"}]
        result = audit_mention_sensitivity([row("m1", "GPT\u20114.1", agent="x")], roster)
        self.assertEqual(keys(result["exact_events"]), {("m1", "y")})
        self.assertFalse(result["shadow_events"])
        ambiguity = result["ambiguous_shadow_events"][0]
        self.assertEqual(ambiguity["candidate_agent_ids"], ["x", "y"])
        self.assertEqual(ambiguity["eligible_nonself_candidate_ids"], ["y"])
        self.assertIsNone(ambiguity["target_agent_id"])

    def test_case_and_whitespace_collisions_follow_regex_not_casefold_expansion(self):
        roster = [{"id": "x", "name": "Deep   Thinker"}, {"id": "y", "name": "deep thinker"},
                  {"id": "s1", "name": "Stra\u00dfe"}, {"id": "s2", "name": "STRASSE"}]
        result = audit_mention_sensitivity([row("m1", "Deep Thinker STRASSE Stra\u00dfe")], roster)
        self.assertEqual(result["normalized_roster_collisions"][0]["agent_ids"], ["x", "y"])
        self.assertEqual(keys(result["shadow_events"]), {("m1", "s1"), ("m1", "s2")})
        self.assertEqual(result["summary"]["normalized_roster_collision_count"], 1)

    def test_unicode_regex_case_equivalence_collision_is_detected(self):
        roster = [{"id": "x", "name": "Iris"}, {"id": "y", "name": "\u0131ris"}]
        result = audit_mention_sensitivity([row("m1", "Iris")], roster)
        self.assertEqual(result["summary"]["exact_event_count"], 2)
        self.assertEqual(result["summary"]["shadow_event_count"], 0)
        self.assertEqual(result["normalized_roster_collisions"][0]["agent_ids"], ["x", "y"])

    def test_no_fuzzy_zero_width_or_semantic_aliases_and_word_boundaries(self):
        texts = ["GPT4.1", "GPT\u200b-4.1", "xGPT\u20114.1", "GPT\u20114.1x",
                 "_GPT\u20114.1", "GPT\u20114.1_", "ChatGPT", "DeepThinker"]
        result = audit_mention_sensitivity([row(f"m{i}", text) for i, text in enumerate(texts)], ROSTER)
        self.assertFalse(result["exact_events"])
        self.assertFalse(result["shadow_events"])
        self.assertFalse(result["ambiguous_shadow_events"])

    def test_self_short_name_id_name_exclusions_and_roster_fallback(self):
        messages = [row("m1", "GPT\u20114.1 GPT-4.1 AB opaque-id", agent="gpt"),
                    row("m2", "Carol, inspect", agent="c", agent_name="Carol"),
                    row("m3", "Carol, inspect", minute=1)]
        result = audit_mention_sensitivity(messages, ROSTER)
        self.assertEqual(keys(result["exact_events"]), {("m3", "c")})
        self.assertEqual(keys(result["shadow_events"]), {("m3", "c")})
        self.assertEqual(result["scope"]["effective_roster_count"], 6)

    def test_repeated_mentions_are_one_event_and_case_is_not_a_new_alias(self):
        result = audit_mention_sensitivity([row("m1", "gpt-4.1 GPT-4.1 GPT\u20114.1")], ROSTER)
        self.assertEqual(result["summary"]["exact_event_count"], 1)
        self.assertEqual(result["summary"]["shadow_event_count"], 1)
        self.assertEqual(result["summary"]["common_message_target_count"], 1)
        self.assertEqual(result["exact_events"][0]["span"]["start"], 0)
        self.assertEqual(result["shadow_events"][0]["span"]["start"], 0)
        self.assertFalse(result["delta_events"]["shadow_only"])

    def test_nfkc_can_remove_exact_match_by_changing_surrounding_boundary(self):
        result = audit_mention_sensitivity([row("m1", "\u2105GPT-4.1")], ROSTER)
        self.assertEqual(result["summary"]["exact_event_count"], 1)
        self.assertEqual(result["summary"]["shadow_event_count"], 0)
        self.assertEqual(result["summary"]["exact_only_event_count"], 1)
        self.assertEqual(result["summary"]["shadow_minus_exact_count"], -1)
        self.assertFalse(result["normalized_roster_collisions"])

    def test_empty_normalized_name_never_creates_zero_length_shadow_match(self):
        result = audit_mention_sensitivity([row("m1", "ordinary text")],
                                          [{"id": "x", "name": "   "}])
        self.assertFalse(result["shadow_events"])
        self.assertEqual(result["shadow_roster_exclusions"], [{"agent_id": "x", "reason": "normalized_name_empty"}])

    def test_original_text_source_and_provided_hash_preserved_without_mutation(self):
        messages = [row("m1", "GPT\u20114.1", content_hash="opaque-hash",
                        source={"file": "chat.jsonl", "line": 17, "nested": {"pin": "source-1"}})]
        before = copy.deepcopy(messages)
        roster = copy.deepcopy(ROSTER)
        result = audit_mention_sensitivity(messages, roster)
        self.assertEqual(messages, before)
        self.assertEqual(roster, ROSTER)
        evidence = result["evidence_index"]["m1"]
        self.assertEqual(evidence["content_hash"], "opaque-hash")
        self.assertEqual(evidence["content_hash_origin"], "provided_unverified")
        self.assertEqual(evidence["original_content_sha256"],
                         hashlib.sha256(messages[0]["content"].encode("utf-8")).hexdigest())
        self.assertEqual(evidence["source"], messages[0]["source"])
        evidence["source"]["nested"]["pin"] = "changed"
        self.assertEqual(messages[0]["source"]["nested"]["pin"], "source-1")
        result["delta_events"]["shadow_only"][0]["span"]["start"] = 999
        self.assertEqual(result["shadow_events"][0]["span"]["start"], 0)

    def test_deterministic_across_valid_input_order_and_dictionary_roster(self):
        messages = [row("later", "GPT\u20114.1", minute=2), row("early", "Deep Thinker", minute=1)]
        first = audit_mention_sensitivity(messages, ROSTER)
        second = audit_mention_sensitivity(list(reversed(messages)), list(reversed(ROSTER)))
        third = audit_mention_sensitivity(messages, {agent["id"]: agent for agent in ROSTER})
        self.assertEqual(first, second)
        self.assertEqual(first, third)
        self.assertEqual(list(first["evidence_index"]), ["early", "later"])
        json.dumps(first, allow_nan=False)

    def test_empty_inputs_and_computed_hash_origin(self):
        empty = audit_mention_sensitivity([])
        self.assertEqual(empty["summary"]["exact_event_count"], 0)
        self.assertIsNone(empty["scope"]["start"])
        result = audit_mention_sensitivity([row("m1", "plain text")], ROSTER)
        self.assertEqual(result["evidence_index"]["m1"]["content_hash_origin"], "computed_normalized_message_record")

    def test_source_fingerprint_binds_record_context_even_with_provided_hash(self):
        message = row("m1", "GPT-4.1", content_hash="opaque-fixed-hash")
        original = audit_mention_sensitivity([message], ROSTER)
        for field, value in (("agent_id", "thinker"), ("room_id", "elsewhere"),
                             ("timestamp", "2025-04-20T11:00:00Z")):
            changed = {**message, field: value}
            report = audit_mention_sensitivity([changed], ROSTER)
            self.assertNotEqual(original["source_fingerprint"], report["source_fingerprint"])
            self.assertEqual(report["evidence_index"]["m1"]["content_hash"], "opaque-fixed-hash")

    def test_duplicate_ids_invalid_records_and_explicit_bounds(self):
        with self.assertRaises(ValueError):
            audit_mention_sensitivity([row("m1", "one"), row("m1", "two")], ROSTER)
        with self.assertRaises(ValueError):
            audit_mention_sensitivity([], [{"id": "x", "name": "One"}, {"id": "x", "name": "Two"}])
        with self.assertRaises(ValueError):
            audit_mention_sensitivity([{"id": "missing-time", "content": "test"}])
        with self.assertRaises(ValueError):
            audit_mention_sensitivity([row("m1", "test", agent=4)])
        with self.assertRaises(ValueError):
            audit_mention_sensitivity([row("m1", 123)])
        with self.assertRaises(ValueError):
            audit_mention_sensitivity([None])
        with patch("swarm_lab.mention_sensitivity.MAX_MESSAGES", 1):
            with self.assertRaises(ValueError):
                audit_mention_sensitivity([row("m1", "one"), row("m2", "two")])
        with patch("swarm_lab.mention_sensitivity.MAX_AGENTS", 1):
            with self.assertRaises(ValueError):
                audit_mention_sensitivity([], ROSTER)
        with patch("swarm_lab.mention_sensitivity.MAX_TEXT_CHARACTERS", 1):
            with self.assertRaises(ValueError):
                audit_mention_sensitivity([row("m1", "abc")])
        with patch("swarm_lab.mention_sensitivity.MAX_PATTERN_WORK", 1):
            with self.assertRaises(ValueError):
                audit_mention_sensitivity([row("m1", "abc")], ROSTER)
        with self.assertRaises(ValueError):
            audit_mention_sensitivity([], [{"id": "x", "name": "n" * 257}])

    def test_shadow_normalizer_is_bounded_to_explicit_transformations(self):
        self.assertEqual(normalize_shadow_text(" GPT\u20114.1 "), "GPT-4.1")
        self.assertEqual(normalize_shadow_text("GPT\u200b-4.1"), "GPT\u200b-4.1")
        self.assertEqual(normalize_shadow_text("GPT4.1"), "GPT4.1")
        self.assertEqual(normalize_shadow_text("Caf\u00e9"), "Caf\u00e9")
        with self.assertRaises(ValueError):
            normalize_shadow_text(None)


if __name__ == "__main__":
    unittest.main()
