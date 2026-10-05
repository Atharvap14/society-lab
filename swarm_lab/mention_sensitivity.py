"""Read-only sensitivity of exact-display-name mentions to Unicode formatting.

The legacy instrument is reproduced without changing graph extraction. The
shadow instrument is a measurement candidate, never a delivery/influence edge.
Shadow offsets index retained normalized text, not original-source characters.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata
from collections import Counter

from .dataset import normalize_message


MENTION_SENSITIVITY_VERSION = "exact-name-unicode-shadow-v1"
MAX_MESSAGES = 10000
MAX_AGENTS = 1000
MAX_TEXT_CHARACTERS = 20000000
MAX_PATTERN_WORK = 200000000
MAX_NAME_CHARACTERS = 256
# Finite formatting candidates. No arbitrary punctuation removal or fuzzy alias.
DASH_VARIANTS = (
    "\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2015",
    "\u2212", "\ufe58", "\ufe63", "\uff0d",
)
_DASH_TRANSLATION = str.maketrans({character: "-" for character in DASH_VARIANTS})


def normalize_shadow_text(text: str) -> str:
    """NFKC, enumerated dashes to ASCII hyphen, then Unicode whitespace collapse."""
    if not isinstance(text, str):
        raise ValueError("Shadow text must be a string")
    return " ".join(unicodedata.normalize("NFKC", text).translate(_DASH_TRANSLATION).split())


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _pattern(name: str):
    return re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)", re.I)


def _eligible(identity: str, name: str) -> bool:
    # Eligibility is defined on the original name for both instruments.
    return name != identity and len(name) >= 3


def _collisions(names: dict[str, str], normalized: dict[str, str]) -> list[dict]:
    """Exact re.IGNORECASE equivalence after normalization, not casefold guessing."""
    ids = sorted(names)
    roots = {identity: identity for identity in ids}

    def root(identity):
        while roots[identity] != identity:
            identity = roots[identity]
        return identity

    full_patterns = {identity: re.compile(re.escape(normalized[identity]), re.I)
                     for identity in ids}
    for position, left in enumerate(ids):
        for right in ids[position + 1:]:
            if len(normalized[left]) == len(normalized[right]) and full_patterns[left].fullmatch(normalized[right]):
                roots[root(right)] = root(left)
    groups = {}
    for identity in ids:
        groups.setdefault(root(identity), []).append(identity)
    result = []
    for members in groups.values():
        if len(members) < 2:
            continue
        entry = {
            "collision_id": "mention-collision-" + _digest(members)[:16],
            "agent_ids": members,
            "normalized_names": sorted({normalized[identity] for identity in members}),
            "roster_entries": [{"agent_id": identity, "display_name": names[identity],
                               "normalized_display_name": normalized[identity],
                               "original_name_eligible": _eligible(identity, names[identity])}
                              for identity in members],
            "status": "ambiguous_unknown_target",
            "exclusion": "No definitive shadow event for any member of this collision group.",
        }
        result.append(entry)
    return sorted(result, key=lambda group: group["agent_ids"])


def audit_mention_sensitivity(messages: list[dict], agents: list[dict] | dict | None = None) -> dict:
    """Compare exact mentions and conservative shadow matches on bounded inputs.

    One match per message/target, first regex occurrence, mirrors build_graph.
    Roster collisions exclude definitive shadow mapping globally. Exact output
    remains unchanged, even where the old instrument maps a colliding name.
    No file, database, network, model, graph, or source mutation occurs.
    """
    if not isinstance(messages, list) or len(messages) > MAX_MESSAGES:
        raise ValueError(f"Provide at most {MAX_MESSAGES} messages as a list")
    if agents is not None and not isinstance(agents, (list, dict)):
        raise ValueError("Roster must be a list or dictionary")
    roster = list(agents.values()) if isinstance(agents, dict) else list(agents or [])
    if len(roster) > MAX_AGENTS:
        raise ValueError(f"Provide at most {MAX_AGENTS} roster agents")
    if any(not isinstance(row, dict) for row in messages + roster):
        raise ValueError("Messages and roster entries must be dictionaries")
    total_characters = sum(len(row.get("content", "")) for row in messages
                           if isinstance(row.get("content", ""), str))
    if total_characters > MAX_TEXT_CHARACTERS:
        raise ValueError("Provided message text exceeds the bounded audit")

    names = {}
    for agent in roster:
        if agent.get("id"):
            identity = str(agent["id"])
            if identity in names:
                raise ValueError("Roster agent IDs must be unique")
            names[identity] = str(agent.get("name", agent["id"]))
    ordered = []
    provided_hashes = {}
    for row in messages:
        message = normalize_message(row)
        if message["agent_id"] is not None and not isinstance(message["agent_id"], str):
            raise ValueError("Agent speaker IDs must be strings")
        if message["id"] in provided_hashes:
            raise ValueError("Message IDs must be unique")
        provided_hashes[message["id"]] = copy.deepcopy(row.get("content_hash"))
        ordered.append(message)
    ordered.sort(key=lambda message: (message["timestamp"], message["id"]))
    for message in ordered:
        if message["agent_id"]:
            names.setdefault(message["agent_id"], message["agent_name"])
    if any(not isinstance(name, str) for name in names.values()):
        raise ValueError("Effective display names must be strings")
    if len(names) > MAX_AGENTS or any(len(name) > MAX_NAME_CHARACTERS for name in names.values()):
        raise ValueError("Effective roster or display-name length exceeds audit bounds")
    if total_characters * max(1, len(names)) > MAX_PATTERN_WORK:
        raise ValueError("Message-character times roster-size scan exceeds audit bounds")

    normalized_names = {identity: normalize_shadow_text(name) for identity, name in names.items()}
    collision_groups = _collisions(names, normalized_names)
    collision_ids = {identity for group in collision_groups for identity in group["agent_ids"]}
    exact_patterns = {identity: _pattern(name) for identity, name in names.items()
                      if _eligible(identity, name)}
    empty_names = {identity for identity, name in normalized_names.items() if not name}
    shadow_patterns = {identity: _pattern(normalized_names[identity])
                       for identity in exact_patterns if identity not in collision_ids and identity not in empty_names}
    collision_patterns = {group["collision_id"]: _pattern(group["normalized_names"][0])
                          for group in collision_groups if group["normalized_names"][0]}
    evidence_index, exact_events, shadow_events, ambiguous_events = {}, [], [], []

    def event(message, identity, match, instrument):
        shadow = instrument == "unicode_shadow"
        coordinates = "shadow_text_python_codepoints" if shadow else "original_content_python_codepoints"
        return {
            "event_id": "mention-" + instrument + "-" + _digest(
                [MENTION_SENSITIVITY_VERSION, message["id"], identity, match.start(), match.end()])[:20],
            "message_id": message["id"], "author_agent_id": message["agent_id"],
            "speaker_id": message["speaker_id"], "speaker_type": message["speaker_type"],
            "target_agent_id": identity, "evidence_ids": [message["id"]],
            "display_name": names[identity], "normalized_display_name": normalized_names[identity],
            "instrument": instrument, "match_text": match.group(),
            "span": {"start": match.start(), "end": match.end(), "coordinates": coordinates},
            "original_span_available": not shadow,
            "status": "formatting_match_candidate" if shadow else "recorded_name_match",
            "interpretation": "Name-pattern match only; target intent, delivery, reading and influence unknown.",
        }

    for message in ordered:
        identity = message["id"]
        original = message["content"]
        nfkc = unicodedata.normalize("NFKC", original)
        dashed = nfkc.translate(_DASH_TRANSLATION)
        shadow = normalize_shadow_text(original)
        provided = provided_hashes[identity]
        evidence_index[identity] = {
            "message_id": identity, "agent_id": message["agent_id"], "speaker_id": message["speaker_id"],
            "speaker_type": message["speaker_type"], "timestamp": message["timestamp"],
            "room_id": message["room_id"], "source": copy.deepcopy(message["source"]),
            "content": original, "shadow_text": shadow,
            "content_hash": provided if provided is not None else message["content_hash"],
            "content_hash_origin": "provided_unverified" if provided is not None else "computed_normalized_message_record",
            "computed_normalized_record_hash": message["content_hash"],
            "original_content_sha256": _text_hash(original), "shadow_text_sha256": _text_hash(shadow),
            "transformations_applied": {"nfkc_changed": nfkc != original,
                                        "dash_mapping_changed": dashed != nfkc,
                                        "whitespace_changed": shadow != dashed},
        }
        for target in sorted(exact_patterns):
            if target == message["agent_id"]:
                continue
            match = exact_patterns[target].search(original)
            if match:
                exact_events.append(event(message, target, match, "exact_display_name"))
        for target in sorted(shadow_patterns):
            if target == message["agent_id"]:
                continue
            match = shadow_patterns[target].search(shadow)
            if match:
                shadow_events.append(event(message, target, match, "unicode_shadow"))
        for group in collision_groups:
            if group["collision_id"] not in collision_patterns:
                continue
            eligible = [target for target in group["agent_ids"]
                        if target != message["agent_id"] and target in exact_patterns]
            if not eligible:
                continue
            match = collision_patterns[group["collision_id"]].search(shadow)
            if match:
                ambiguous_events.append({
                    "message_id": identity, "evidence_ids": [identity],
                    "collision_id": group["collision_id"], "target_agent_id": None,
                    "candidate_agent_ids": list(group["agent_ids"]),
                    "eligible_nonself_candidate_ids": eligible,
                    "status": "ambiguous_unknown_target", "instrument": "unicode_shadow",
                    "match_text": match.group(), "original_span_available": False,
                    "span": {"start": match.start(), "end": match.end(),
                             "coordinates": "shadow_text_python_codepoints"},
                })

    exact_keys = {(event["message_id"], event["target_agent_id"]) for event in exact_events}
    shadow_keys = {(event["message_id"], event["target_agent_id"]) for event in shadow_events}
    added = [copy.deepcopy(event) for event in shadow_events
             if (event["message_id"], event["target_agent_id"]) not in exact_keys]
    removed = [copy.deepcopy(event) for event in exact_events
               if (event["message_id"], event["target_agent_id"]) not in shadow_keys]
    return {
        "schema_version": "1.0", "analysis_version": MENTION_SENSITIVITY_VERSION,
        "kind": "mention_measurement_sensitivity", "read_only": True,
        "source_fingerprint": _digest([[message["id"], message["content_hash"], evidence_index[message["id"]]["original_content_sha256"],
                                      evidence_index[message["id"]]["content_hash"], message["source"]]
                                     for message in ordered]),
        "roster_fingerprint": _digest(sorted(names.items())),
        "bounds": {"max_messages": MAX_MESSAGES, "max_agents": MAX_AGENTS,
                   "max_original_text_characters": MAX_TEXT_CHARACTERS,
                   "max_character_roster_product": MAX_PATTERN_WORK,
                   "max_display_name_characters": MAX_NAME_CHARACTERS},
        "scope": {"message_count": len(ordered), "effective_roster_count": len(names),
                  "original_text_characters": total_characters,
                  "start": ordered[0]["timestamp"] if ordered else None,
                  "end": ordered[-1]["timestamp"] if ordered else None},
        "transformation_definitions": {
            "order": ["Unicode NFKC", "enumerated dash variants to U+002D", "Unicode whitespace collapse and trim"],
            "unicode_database_version": unicodedata.unidata_version,
            "dash_variants": [f"U+{ord(character):04X}" for character in DASH_VARIANTS],
            "whitespace": "Python str.split() recognizes Unicode whitespace; join with one ASCII space.",
            "case_matching": "Python re.IGNORECASE, same flag as the exact instrument.",
            "boundaries": "Python Unicode word boundaries: (?<!\\w) and (?!\\w).",
            "eligibility": "Original name != agent ID; original name length >= 3; self mentions excluded per message.",
            "collision_detection": "Full-string re.IGNORECASE equivalence after shadow normalization, across the effective roster.",
            "span_coordinates": "Half-open Python codepoint offsets into content for exact matches or shadow_text for shadow matches.",
            "original_offset_mapping": "Not computed; no original-source offsets are asserted for shadow matches.",
        },
        "summary": {
            "exact_event_count": len(exact_events), "shadow_event_count": len(shadow_events),
            "shadow_minus_exact_count": len(shadow_events) - len(exact_events),
            "common_message_target_count": len(exact_keys & shadow_keys),
            "shadow_only_event_count": len(added), "exact_only_event_count": len(removed),
            "ambiguous_shadow_event_count": len(ambiguous_events),
            "normalized_roster_collision_count": len(collision_groups),
            "collision_excluded_eligible_agent_count": len(collision_ids & set(exact_patterns)),
            "exact_events_by_target": dict(sorted(Counter(event["target_agent_id"] for event in exact_events).items())),
            "shadow_events_by_target": dict(sorted(Counter(event["target_agent_id"] for event in shadow_events).items())),
        },
        "exact_events": exact_events, "shadow_events": shadow_events,
        "delta_events": {"shadow_only": added, "exact_only": removed},
        "ambiguous_shadow_events": ambiguous_events,
        "normalized_roster_collisions": collision_groups,
        "shadow_roster_exclusions": [
            {"agent_id": identity, "reason": "normalized_name_collision" if identity in collision_ids else "normalized_name_empty"}
            for identity in sorted(set(exact_patterns) & (collision_ids | empty_names))
        ],
        "evidence_index": evidence_index,
        "limitations": [
            "Name matches do not establish intentional address, delivery, reading, agreement or influence.",
            "Shadow matches are candidate formatting aliases and require source adjudication.",
            "Normalization can merge distinct names; colliding shadow targets are unknown and excluded from definitive counts.",
            "No fuzzy, semantic, nickname, transliteration or zero-width-character alias resolution is applied.",
            "One first match per message/target mirrors the exact instrument; repeated occurrences do not add events.",
            "Case-insensitive word-boundary matching includes quotations and may miss aliases or unrecorded roster names.",
            "Counts describe only the provided bounded messages and effective roster, not complete participation or time at risk.",
            "Shadow offsets index normalized text only; provided content hashes are retained without assuming their hash scheme.",
            "NFKC includes compatibility transformations; a formatting difference is not proof that the name denotes the same agent.",
            "The existing extractor and inferred graph channels are unchanged; this audit creates no graph edges.",
        ],
    }
