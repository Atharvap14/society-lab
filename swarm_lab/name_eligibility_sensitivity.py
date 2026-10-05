"""Explicit, read-only short-name eligibility sensitivity.

The existing minimum-three-character mention instrument is preserved. Only
explicitly allowlisted, unambiguous short roster display names are candidates;
neither exact nor optional normalized candidates become main-graph edges.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re

from .dataset import normalize_message
from .mention_sensitivity import audit_mention_sensitivity, normalize_shadow_text


NAME_ELIGIBILITY_SENSITIVITY_VERSION = "explicit-short-name-sensitivity-v1"
MAX_ALLOWLIST_REQUESTS = 1000


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _pattern(name):
    return re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)", re.I)


def _valid_short_name(name):
    return isinstance(name, str) and 1 <= len(name) < 3 and all(character.isalnum() for character in name)


def audit_name_eligibility_sensitivity(messages: list[dict], agents: list[dict] | dict | None = None,
                                      *, short_name_allowlist: list[str] | None = None,
                                      include_unicode_shadow: bool = False) -> dict:
    """Measure an explicit short-display-name allowlist without widening defaults.

    Requests must be original one/two-codepoint alphanumeric display names.
    Resolution uses literal full-name Python re.IGNORECASE equivalence. Missing,
    colliding and name-equals-ID roster entries do not silently resolve. Duplicate
    requests are retained in the resolution ledger but count each target once.
    Optional shadow measurement inherits the existing module's normalization,
    collision handling and normalized-coordinate policy without modifying it.
    """
    if short_name_allowlist is None:
        requested = []
    elif not isinstance(short_name_allowlist, list) or len(short_name_allowlist) > MAX_ALLOWLIST_REQUESTS:
        raise ValueError(f"Provide at most {MAX_ALLOWLIST_REQUESTS} explicit short display names as a list")
    else:
        requested = list(short_name_allowlist)
    if any(not _valid_short_name(name) for name in requested):
        raise ValueError("Requested short names must be one or two Unicode alphanumeric codepoints")
    if type(include_unicode_shadow) is not bool:
        raise ValueError("include_unicode_shadow must be a boolean")

    # Also validates bounded inputs, unique IDs, names and record provenance.
    baseline = audit_mention_sensitivity(messages, agents)
    roster = agents.values() if isinstance(agents, dict) else agents or []
    names = {str(agent["id"]): str(agent.get("name", agent["id"]))
             for agent in roster if agent.get("id")}
    ordered = sorted((normalize_message(row) for row in messages),
                     key=lambda message: (message["timestamp"], message["id"]))
    for message in ordered:
        if message["agent_id"]:
            names.setdefault(message["agent_id"], message["agent_name"])

    resolution, resolved, first_request, exact_collision_groups = [], set(), {}, {}
    requested_eligible_candidates = set()
    for position, request in enumerate(requested):
        matches = sorted(identity for identity, name in names.items()
                         if re.fullmatch(re.escape(request), name, re.I))
        entry = {"request_index": position, "requested_name": request,
                 "candidate_agent_ids": matches, "resolved_agent_ids": []}
        if not matches:
            entry["status"] = "not_found_in_original_roster_names"
        elif len(matches) > 1:
            entry["status"] = "ambiguous_unknown_target"
            key = tuple(matches)
            exact_collision_groups[key] = {
                "collision_id": "short-exact-collision-" + _digest(matches)[:16],
                "candidate_agent_ids": matches,
                "display_names": sorted({names[identity] for identity in matches}),
                "status": "ambiguous_unknown_target",
            }
        else:
            identity = matches[0]
            if names[identity] == identity:
                entry["status"] = "excluded_display_name_equals_id"
            elif not _valid_short_name(names[identity]):
                entry["status"] = "excluded_invalid_short_display_name"
            else:
                entry["resolved_agent_ids"] = [identity]
                if identity in resolved:
                    entry["status"] = "resolved_duplicate_request"
                    entry["duplicate_of_request_index"] = first_request[identity]
                else:
                    entry["status"] = "resolved_explicit_short_name"
                    resolved.add(identity)
                    first_request[identity] = position
        requested_eligible_candidates.update(identity for identity in matches
                                             if _valid_short_name(names[identity]) and names[identity] != identity)
        resolution.append(entry)

    exact_patterns = {identity: _pattern(names[identity]) for identity in sorted(resolved)}

    def candidate(message, identity, match, *, shadow=False):
        instrument = "explicit_short_name_unicode_shadow" if shadow else "explicit_short_name_exact"
        return {
            "event_id": "short-mention-" + _digest(
                [NAME_ELIGIBILITY_SENSITIVITY_VERSION, baseline["analysis_version"],
                 instrument, message["id"], identity, match.start(), match.end()])[:20],
            "message_id": message["id"], "evidence_ids": [message["id"]],
            "author_agent_id": message["agent_id"], "speaker_id": message["speaker_id"],
            "speaker_type": message["speaker_type"], "target_agent_id": identity,
            "display_name": names[identity], "normalized_display_name": normalize_shadow_text(names[identity]),
            "instrument": instrument, "status": "explicit_short_name_match_candidate",
            "match_text": match.group(), "original_span_available": not shadow,
            "span": {"start": match.start(), "end": match.end(),
                     "coordinates": "shadow_text_python_codepoints" if shadow else "original_content_python_codepoints"},
            "interpretation": "Allowlisted name-pattern candidate only; true address, delivery and influence unverified.",
        }

    def unknown(message, group, match, *, shadow=False):
        candidates = group.get("candidate_agent_ids", group.get("agent_ids", []))
        eligible = [identity for identity in candidates
                    if identity != message["agent_id"] and identity in requested_eligible_candidates]
        return {
            "message_id": message["id"], "evidence_ids": [message["id"]],
            "collision_id": group["collision_id"], "target_agent_id": None,
            "candidate_agent_ids": list(candidates), "eligible_nonself_candidate_ids": eligible,
            "instrument": "explicit_short_name_unicode_shadow" if shadow else "explicit_short_name_exact",
            "status": "ambiguous_unknown_target", "match_text": match.group(),
            "original_span_available": not shadow,
            "span": {"start": match.start(), "end": match.end(),
                     "coordinates": "shadow_text_python_codepoints" if shadow else "original_content_python_codepoints"},
        }

    short_exact, ambiguous_exact = [], []
    exact_groups = [exact_collision_groups[key] for key in sorted(exact_collision_groups)]
    for message in ordered:
        for identity, pattern in exact_patterns.items():
            if identity != message["agent_id"]:
                match = pattern.search(message["content"])
                if match:
                    short_exact.append(candidate(message, identity, match))
        for group in exact_groups:
            if not any(identity != message["agent_id"] and identity in requested_eligible_candidates
                       for identity in group["candidate_agent_ids"]):
                continue
            match = _pattern(group["display_names"][0]).search(message["content"])
            if match:
                ambiguous_exact.append(unknown(message, group, match))

    shadow_result = {"enabled": False, "reason": "Unicode shadow comparison was not requested"}
    if include_unicode_shadow:
        normalized_collisions = baseline["normalized_roster_collisions"]
        collision_ids = {identity for group in normalized_collisions for identity in group["agent_ids"]}
        normalized_patterns = {identity: _pattern(normalize_shadow_text(names[identity]))
                               for identity in sorted(resolved) if identity not in collision_ids}
        short_shadow, ambiguous_shadow = [], []
        for message in ordered:
            shadow_text = baseline["evidence_index"][message["id"]]["shadow_text"]
            for identity, pattern in normalized_patterns.items():
                if identity != message["agent_id"]:
                    match = pattern.search(shadow_text)
                    if match:
                        short_shadow.append(candidate(message, identity, match, shadow=True))
            for group in normalized_collisions:
                if not any(identity != message["agent_id"] and identity in requested_eligible_candidates
                           for identity in group["agent_ids"]):
                    continue
                match = _pattern(group["normalized_names"][0]).search(shadow_text)
                if match:
                    ambiguous_shadow.append(unknown(message, group, match, shadow=True))
        exact_keys = {(event["message_id"], event["target_agent_id"]) for event in short_exact}
        shadow_keys = {(event["message_id"], event["target_agent_id"]) for event in short_shadow}
        shadow_result = {
            "enabled": True, "baseline_instrument_version": baseline["analysis_version"],
            "normalization_policy": copy.deepcopy(baseline["transformation_definitions"]),
            "baseline_shadow_events": copy.deepcopy(baseline["shadow_events"]),
            "baseline_delta_events": copy.deepcopy(baseline["delta_events"]),
            "short_name_shadow_events": short_shadow,
            "short_name_delta_events": {
                "shadow_only": [copy.deepcopy(event) for event in short_shadow
                                if (event["message_id"], event["target_agent_id"]) not in exact_keys],
                "exact_only": [copy.deepcopy(event) for event in short_exact
                               if (event["message_id"], event["target_agent_id"]) not in shadow_keys],
            },
            "ambiguous_short_shadow_events": ambiguous_shadow,
            "normalized_roster_collisions": copy.deepcopy(normalized_collisions),
            "summary": {
                "baseline_shadow_event_count": len(baseline["shadow_events"]),
                "short_candidate_shadow_event_count": len(short_shadow),
                "expanded_shadow_candidate_event_count": len(baseline["shadow_events"]) + len(short_shadow),
                "expanded_shadow_minus_expanded_exact_count": len(baseline["shadow_events"]) + len(short_shadow)
                - len(baseline["exact_events"]) - len(short_exact),
                "short_shadow_minus_short_exact_count": len(short_shadow) - len(short_exact),
                "ambiguous_short_shadow_event_count": len(ambiguous_shadow),
            },
        }

    return {
        "schema_version": "1.0", "analysis_version": NAME_ELIGIBILITY_SENSITIVITY_VERSION,
        "kind": "name_eligibility_measurement_sensitivity", "read_only": True,
        "baseline_instrument_version": baseline["analysis_version"],
        "source_fingerprint": baseline["source_fingerprint"], "roster_fingerprint": baseline["roster_fingerprint"],
        "scope": copy.deepcopy(baseline["scope"]), "bounds": {**baseline["bounds"], "max_allowlist_requests": MAX_ALLOWLIST_REQUESTS},
        "requested_names": requested, "resolved_agent_ids": sorted(resolved),
        "normalization_policy": {"comparison_requested": include_unicode_shadow,
                                 **copy.deepcopy(baseline["transformation_definitions"])},
        "allowlist_resolution": resolution,
        "eligibility_policy": {
            "baseline": "Unchanged original display-name length >=3, name != ID, self excluded.",
            "allowlist": "Explicit original one/two-codepoint alphanumeric display names; literal re.IGNORECASE full-name resolution.",
            "duplicates": "Retained requests, one first occurrence per message/unique resolved target.",
            "boundaries": "Same Python Unicode (?<!\\w) and (?!\\w) regex boundaries as the baseline.",
            "collisions": "Original full-name regex collisions are unknown; optional shadow also excludes normalized roster collisions.",
            "default_widening": False, "graph_edges_created": False,
        },
        "summary": {
            "baseline_exact_event_count": len(baseline["exact_events"]),
            "short_candidate_exact_event_count": len(short_exact),
            "expanded_exact_candidate_event_count": len(baseline["exact_events"]) + len(short_exact),
            "explicit_short_name_delta_count": len(short_exact),
            "ambiguous_exact_event_count": len(ambiguous_exact),
            "requested_name_count": len(requested), "resolved_agent_count": len(resolved),
            "duplicate_resolved_request_count": sum(entry["status"] == "resolved_duplicate_request" for entry in resolution),
        },
        "baseline_exact_events": copy.deepcopy(baseline["exact_events"]),
        "short_name_exact_events": short_exact, "ambiguous_exact_events": ambiguous_exact,
        "original_roster_collisions": copy.deepcopy(exact_groups),
        "evidence_index": copy.deepcopy(baseline["evidence_index"]),
        "unicode_shadow": shadow_result,
        "limitations": [
            "Expanded counts combine baseline matches with separately labeled candidates; they are not main-graph counts.",
            "Short model names can occur in ordinary prose, quotations, filenames or comparisons without addressing an agent.",
            "Literal matches do not establish true address, delivery, reading, agreement or causal influence.",
            "Only explicit, uniquely resolved requests are counted; no default short-name widening or fuzzy/semantic aliases.",
            "An ambiguous roster target remains unknown even if another colliding candidate is the speaker.",
            "Shadow normalization may add or remove matches and merge names; source offsets are never inferred from normalized coordinates.",
            "Provided source hashes remain unverified; computed record context and original content hashes bind the supplied records.",
            "This sensitivity is not independent replication, a new behavioral discovery or validation of naming intent.",
        ],
    }
