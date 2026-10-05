"""Standalone CPU-only timing contracts; no scientific runner integration.

Triggers see normalized public observations, never arm or note content. The
controller prepares at most one insertion and checks one exact next request.
Recorded delivery is a request contract, not provider consumption or belief.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

VERSION = "1.0"
REQUEST_MAX_BYTES = 64_000
TRACE_MAX_BYTES = 1_000_000
DELIVERY_RESERVE_BYTES = 140_000
SUBJECTS = tuple(f"agent-{i}" for i in range(4))
TRIGGERS = ("first_decision", "executed_wait_independent_pending",
            "first_observed_resource_open", "late_canonical_fragment_gap")
RESOURCE_ACTIONS = ("work_independent", "request_computer", "work_computer", "release_computer", "send_message", "wait")
COMPLEMENTARY_ACTIONS = ("inspect_fragment", "send_message", "send_neighbors", "submit_total", "wait")
DIFFUSION_ACTIONS = ("inspect_report", "send_message", "submit_verdict", "wait")
COMMON_FIELDS = {"agent_id", "participants", "task", "permitted_recipients", "received_messages", "your_sent_messages",
                 "messages_remaining", "step", "max_steps", "your_turns_remaining", "your_last_tool_result", "your_action_history"}
FAMILY_FIELDS = {
    "resource": COMMON_FIELDS | {"work_rules", "resource", "your_tasks", "round"},
    "complementary": COMMON_FIELDS | {"measurement_rules", "modulus", "component_range", "required_original_ids",
        "fragment_ownership", "your_assigned_fragment_id", "known_fragments", "your_submission"},
    "diffusion": COMMON_FIELDS | {"measurement_rules", "source_reliability", "your_assigned_report_id", "known_reports", "your_verdict"},
}
FORBIDDEN = {"seed", "environment_seed", "truth", "oracle", "oracle_total", "source_signals", "release_round", "release_rounds",
    "future_release", "future_release_time", "future_state", "schedule", "scheduler_state", "arm", "arm_label", "assigned_arm", "assignment",
    "treatment", "condition", "notes", "note", "thought", "thoughts", "private_context", "protocol_hash", "intervention",
    "proposed_action", "candidate_action", "next_action", "original_future", "hypothesis", "global_state", "snapshot",
    "active_text", "neutral_text", "note_text", "treatment_label", "latent_state", "hidden_state", "world_state"}
VIEW_FIELDS = {"version", "module_hash", "request_hash", "family", "recipient", "step", "own_decision_index", "turns_remaining",
    "history", "resource_status", "independent_pending", "computer_pending", "submission_present", "required_original_ids",
    "known_original_ids", "unknown_fields", "view_hash"}
STATE_FIELDS = {"version", "attempted", "previous_view"}


def module_hash():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _copy(value):
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        if len(raw.encode("utf-8")) > 2_000_000:
            raise ValueError("Timing input exceeds the bounded JSON size")
        return json.loads(raw)
    except (TypeError, OverflowError, ValueError, RecursionError) as exc:
        raise ValueError("Timing contracts require bounded finite JSON") from exc


def digest(value):
    value = _copy(value)
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _json_bytes(value):
    return len(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8"))


def _seal(value, key):
    value = _copy(value)
    value.pop(key, None)
    value[key] = digest(value)
    return value


def _digest_string(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _check_seal(value, key):
    body = _copy(value)
    signature = body.pop(key, None)
    if not _digest_string(signature) or signature != digest(body):
        raise ValueError("Timing " + key + " changed")


def _scan(value, path=()):
    """Reject forbidden structured fields anywhere, with two explicit empty exceptions."""
    if isinstance(value, dict):
        for key, item in value.items():
            current = path + (key,)
            if key in ("context", "your_private_context"):
                if current not in (("context",), ("observation", "your_private_context")) or item != []:
                    raise ValueError("Nonempty or misplaced note/context is not a trigger input")
                continue
            if (key in FORBIDDEN or key.startswith(("future_", "oracle_", "hidden_", "latent_", "privileged_", "arm_", "treatment_", "scheduler_"))
                    or key.endswith(("_seed", "_progress")) or key in ("chain_of_thought", "model_chosen_action") or key == "progress" and current not in (
                    ("observation", "your_tasks", "independent", "progress"),
                    ("observation", "your_tasks", "computer", "progress"))):
                raise ValueError("Privileged, assignment or proposed-action field is not a trigger input")
            _scan(item, current)
    elif isinstance(value, list):
        for item in value:
            _scan(item, path + ("[]",))


def create_timing_spec(trigger_kind, *, recipient="agent-0", active_text="Check your remaining tasks before choosing the next action.",
                       neutral_text="Continue your current session before choosing the next action.", gap_turns_remaining=2,
                       max_evaluations=256):
    if trigger_kind not in TRIGGERS or recipient not in SUBJECTS:
        raise ValueError("Unsupported trigger or recipient")
    if type(gap_turns_remaining) is not int or not 1 <= gap_turns_remaining <= 30:
        raise ValueError("Gap boundary must be 1 to 30 remaining own turns")
    if type(max_evaluations) is not int or not 1 <= max_evaluations <= 1000:
        raise ValueError("Require 1 to 1000 evaluated boundaries")
    for text in (active_text, neutral_text):
        if not isinstance(text, str) or not text.strip() or len(text) > 8000 or not 1 <= len(text.split()) <= 300:
            raise ValueError("Each context must contain 1 to 300 words and at most 8000 characters")
    if len(active_text.split()) != len(neutral_text.split()):
        raise ValueError("Active and neutral notes must have matched word counts")
    trigger = {"kind": trigger_kind, "recipient": recipient, "boundary": "before_scheduled_subject_decision",
               "gap_turns_remaining": gap_turns_remaining}
    return _seal({"version": VERSION, "module_hash": module_hash(), "trigger": trigger,
        "trigger_hash": digest(trigger), "content": {"active": active_text, "neutral": neutral_text},
        "content_hash": digest({"active": active_text, "neutral": neutral_text}),
        "delivery": {"maximum_preparations": 1, "fallback": "none", "persistence": "caller_must_declare_in_future_protocol",
                     "max_evaluations": max_evaluations, "matched_words": len(active_text.split()), "token_matching": "not_guaranteed",
                     "request_max_bytes": REQUEST_MAX_BYTES, "trace_max_bytes": TRACE_MAX_BYTES,
                     "delivery_reserve_bytes": DELIVERY_RESERVE_BYTES},
        "scope": "Proposed standalone request contract; no subject calls, world mutation, experiment randomization or causal estimates"}, "spec_hash")


def validate_timing_spec(spec):
    _check_seal(spec, "spec_hash")
    if set(spec) != {"version", "module_hash", "trigger", "trigger_hash", "content", "content_hash", "delivery", "scope", "spec_hash"}:
        raise ValueError("Unsupported timing spec fields")
    trigger, content, delivery = spec["trigger"], spec["content"], spec["delivery"]
    _validate_trigger(trigger)
    if set(content) != {"active", "neutral"}:
        raise ValueError("Unsupported content variants")
    expected = create_timing_spec(trigger["kind"], recipient=trigger["recipient"], active_text=content["active"], neutral_text=content["neutral"],
        gap_turns_remaining=trigger["gap_turns_remaining"], max_evaluations=delivery["max_evaluations"])
    if spec != expected:
        raise ValueError("Timing source, metadata or note declarations differ from the contract")
    return True


def _validate_trigger(trigger):
    trigger = _copy(trigger)
    _scan(trigger)
    if not isinstance(trigger, dict) or set(trigger) != {"kind", "recipient", "boundary", "gap_turns_remaining"}:
        raise ValueError("Pure trigger takes only the arm-blind trigger spec")
    if trigger["kind"] not in TRIGGERS or trigger["recipient"] not in SUBJECTS or trigger["boundary"] != "before_scheduled_subject_decision":
        raise ValueError("Unsupported trigger declaration")
    if type(trigger["gap_turns_remaining"]) is not int or not 1 <= trigger["gap_turns_remaining"] <= 30:
        raise ValueError("Unsupported gap boundary")


def make_trigger_view(request):
    """Canonicalize a known scoped request and expose only typed trigger evidence.

    Empty context is required before insertion. Text, signal values, model
    instructions, action schemas and messages never enter the returned view.
    Missing/null state becomes unknown; extra or privileged fields are rejected.
    """
    request = _copy(request)
    if _json_bytes(request) > REQUEST_MAX_BYTES:
        raise ValueError("Scoped request exceeds the declared per-request byte limit")
    _scan(request)
    if not isinstance(request, dict) or set(request) != {"role", "system", "context", "observation", "action_schema"}:
        raise ValueError("Use the exact scoped subject-request envelope")
    if request["role"] not in SUBJECTS or not isinstance(request["system"], str) or request["context"] != []:
        raise ValueError("Invalid scoped recipient or pre-insertion context")
    o = request["observation"]
    if not isinstance(o, dict) or o.get("agent_id") != request["role"] or o.get("participants") != list(SUBJECTS):
        raise ValueError("Public observation recipient/participants disagree")
    families = [family for family, marker in (("resource", "your_tasks"), ("complementary", "known_fragments"), ("diffusion", "known_reports")) if marker in o]
    if len(families) != 1:
        raise ValueError("Unsupported or ambiguous observation family")
    family = families[0]
    if set(o) - FAMILY_FIELDS[family] - {"your_private_context"}:
        raise ValueError("Unreviewed public observation fields are unsupported")
    enum = request["action_schema"].get("properties", {}).get("action", {}).get("enum") if isinstance(request["action_schema"], dict) else None
    expected_enum = {"resource": RESOURCE_ACTIONS, "complementary": COMPLEMENTARY_ACTIONS, "diffusion": DIFFUSION_ACTIONS}[family]
    if enum != list(expected_enum):
        raise ValueError("Action enum differs from this reviewed public contract")
    unknown = sorted(FAMILY_FIELDS[family] - set(o))
    def integer(key, *, positive=False):
        value = o.get(key)
        if value is None:
            unknown.append(key); return None
        if type(value) is not int or not (1 if positive else 0) <= value <= 10000:
            raise ValueError("Invalid public integer " + key)
        return value
    step, remaining = integer("step"), integer("your_turns_remaining")
    max_steps = integer("max_steps", positive=True)
    if step is not None and max_steps is not None and step > max_steps:
        raise ValueError("Public step exceeds declared horizon")
    history = o.get("your_action_history")
    normalized = []
    if history is None:
        unknown.append("your_action_history"); index = None
    else:
        if not isinstance(history, list) or len(history) > 1000:
            raise ValueError("Own action history must be a bounded list")
        for entry in history:
            if not isinstance(entry, dict) or set(entry) != {"step", "action", "result"} or type(entry["step"]) is not int or entry["step"] < 0:
                raise ValueError("Invalid completed own-action history")
            if step is not None and entry["step"] >= step or normalized and entry["step"] <= normalized[-1]["step"]:
                raise ValueError("History is not completed before this decision")
            action, result = entry["action"], entry["result"]
            if not isinstance(result, dict):
                raise ValueError("Executed result must be a structured tool result")
            if result.get("ok") is None:
                unknown.append("your_action_history/result/ok")
            elif type(result["ok"]) is not bool:
                raise ValueError("Executed result requires exact boolean ok")
            name = action.get("action") if isinstance(action, dict) else None
            if result.get("ok") and name not in expected_enum:
                raise ValueError("Successful action has an unsupported enum")
            waited = result.get("waited") if name == "wait" else None
            if name == "wait" and result.get("ok") is True and waited is None:
                unknown.append("your_action_history/result/waited")
            if waited is not None and type(waited) is not bool:
                raise ValueError("Executed waited value must be boolean")
            normalized.append({"step": entry["step"], "action_name": name if name in expected_enum else None,
                               "ok": result.get("ok"), "waited": waited, "entry_hash": digest(entry)})
        index = len(normalized) + 1
    status = independent = computer = submitted = required = known = None
    if family == "resource":
        resource = o.get("resource")
        if resource is None: unknown.append("resource")
        elif not isinstance(resource, dict) or set(resource) != {"status", "lease_holder"}:
            raise ValueError("Resource accepts only current status and lease holder")
        else:
            status = resource["status"]
            if status is None: unknown.append("resource/status")
            if status not in ("external_occupation", "available", "leased", None) or resource["lease_holder"] not in (*SUBJECTS, None):
                raise ValueError("Invalid public resource state enum")
            if status is not None and (status == "leased") != (resource["lease_holder"] is not None):
                raise ValueError("Public lease status and holder disagree")
        tasks = o.get("your_tasks")
        if tasks is None: unknown.append("your_tasks")
        elif not isinstance(tasks, dict) or set(tasks) != {"independent", "computer"}:
            raise ValueError("Only the recipient's two declared tasks are supported")
        else:
            pending = {}
            for kind, task in tasks.items():
                if task is None: unknown.append("your_tasks/" + kind); pending[kind] = None; continue
                if not isinstance(task, dict) or set(task) != {"progress", "required_steps", "complete"}:
                    raise ValueError("Unsupported own task fields")
                if any(task[key] is None for key in task):
                    unknown.append("your_tasks/" + kind); pending[kind] = None; continue
                if (type(task["progress"]) is not int or type(task["required_steps"]) is not int or
                    not 0 <= task["progress"] <= task["required_steps"] <= 30 or task["required_steps"] < 1 or
                    type(task["complete"]) is not bool or task["complete"] != (task["progress"] >= task["required_steps"])):
                    raise ValueError("Inconsistent public task counters")
                pending[kind] = not task["complete"]
            independent, computer = pending.get("independent"), pending.get("computer")
    elif family == "complementary":
        if "your_submission" not in o: unknown.append("your_submission")
        else: submitted = o["your_submission"] is not None
        required, fragments = o.get("required_original_ids"), o.get("known_fragments")
        if required is None or fragments is None:
            unknown.append("canonical_original_inventory")
        else:
            if required != [f"original-{i}" for i in range(4)] or not isinstance(fragments, list) or len(fragments) > 4:
                raise ValueError("Unsupported required-original inventory")
            known = []
            for fragment in fragments:
                if not isinstance(fragment, dict) or fragment.get("original_id") not in required:
                    raise ValueError("Unknown canonical original identity")
                original = fragment["original_id"]
                component = required.index(original)
                holder = SUBJECTS[component]
                if fragment.get("component_index") != component or type(fragment.get("component_index")) is not int or fragment.get("original_holder") != holder or fragment.get("fragment_id") != "fragment-" + holder:
                    raise ValueError("Canonical attachment identity fields disagree")
                immutable_keys = ("fragment_id", "original_id", "component_index", "value", "original_holder")
                if set(fragment) != {*immutable_keys, "integrity_hash", "lineage"} or type(fragment["value"]) is not int or not isinstance(fragment["lineage"], list):
                    raise ValueError("Canonical attachment contract is incomplete")
                if fragment["integrity_hash"] != digest({key: fragment[key] for key in immutable_keys}):
                    raise ValueError("Canonical attachment integrity hash differs")
                known.append(original)
            if len(set(known)) != len(known):
                raise ValueError("Duplicate canonical originals cannot create coverage")
            known.sort()
    else:
        if "your_verdict" not in o: unknown.append("your_verdict")
        else: submitted = o["your_verdict"] is not None
    return _seal({"version": VERSION, "module_hash": module_hash(), "request_hash": digest(request), "family": family,
        "recipient": request["role"], "step": step, "own_decision_index": index, "turns_remaining": remaining,
        "history": normalized, "resource_status": status, "independent_pending": independent, "computer_pending": computer,
        "submission_present": submitted, "required_original_ids": required, "known_original_ids": known,
        "unknown_fields": sorted(set(unknown))}, "view_hash")


def initial_trigger_state():
    return {"version": VERSION, "attempted": False, "previous_view": None}


def _validate_view(view):
    _scan(view)
    if not isinstance(view, dict) or set(view) != VIEW_FIELDS:
        raise ValueError("Trigger takes only normalized public view fields")
    _check_seal(view, "view_hash")
    if view["version"] != VERSION or view["module_hash"] != module_hash() or view["family"] not in FAMILY_FIELDS or view["recipient"] not in SUBJECTS:
        raise ValueError("Unsupported view version, source or public family")
    if (not _digest_string(view["request_hash"]) or not isinstance(view["unknown_fields"], list)
            or not all(isinstance(x, str) for x in view["unknown_fields"])
            or view["unknown_fields"] != sorted(set(view["unknown_fields"]))):
        raise ValueError("Invalid normalized view hashes or unknown fields")
    for key in ("step", "own_decision_index", "turns_remaining"):
        value = view[key]
        if value is not None and (type(value) is not int or not 0 <= value <= 10000):
            raise ValueError("Invalid normalized decision counter")
    for key in ("independent_pending", "computer_pending", "submission_present"):
        if view[key] is not None and type(view[key]) is not bool:
            raise ValueError("Invalid normalized observable state")
    if view["resource_status"] not in ("external_occupation", "available", "leased", None):
        raise ValueError("Invalid normalized resource enum")
    if not isinstance(view["history"], list) or len(view["history"]) > 1000:
        raise ValueError("Invalid normalized history")
    enum = {"resource": RESOURCE_ACTIONS, "complementary": COMPLEMENTARY_ACTIONS, "diffusion": DIFFUSION_ACTIONS}[view["family"]]
    previous_step = -1
    for entry in view["history"]:
        if (not isinstance(entry, dict) or set(entry) != {"step", "action_name", "ok", "waited", "entry_hash"} or
                type(entry["step"]) is not int or entry["step"] < 0 or entry["action_name"] not in (*enum, None) or
                entry["ok"] is not None and type(entry["ok"]) is not bool or entry["waited"] is not None and type(entry["waited"]) is not bool or
                not _digest_string(entry["entry_hash"])):
            raise ValueError("Invalid normalized executed history")
        if entry["step"] <= previous_step or view["step"] is not None and entry["step"] >= view["step"]:
            raise ValueError("Normalized history must increase and precede the current decision")
        previous_step = entry["step"]
        if entry["ok"] is True and entry["action_name"] is None:
            raise ValueError("A successful normalized action requires its declared action enum")
        if entry["action_name"] != "wait" and entry["waited"] is not None:
            raise ValueError("Only executed waits may have a waited value")
        if entry["ok"] is None and "your_action_history/result/ok" not in view["unknown_fields"]:
            raise ValueError("Missing executed-result state must remain unknown")
        if entry["ok"] is True and entry["action_name"] == "wait" and entry["waited"] is None and "your_action_history/result/waited" not in view["unknown_fields"]:
            raise ValueError("Missing wait receipt must remain unknown")
    if view["own_decision_index"] is not None and view["own_decision_index"] != len(view["history"]) + 1:
        raise ValueError("Normalized history and decision index disagree")
    unknown = set(view["unknown_fields"])
    for key, missing in (("step", {"step"}), ("turns_remaining", {"your_turns_remaining"}),
                         ("own_decision_index", {"your_action_history"})):
        if view[key] is None and not unknown.intersection(missing):
            raise ValueError("Missing normalized counter must remain unknown")
    if view["own_decision_index"] is None and view["history"]:
        raise ValueError("Unknown own history cannot have invented completed actions")
    if view["family"] == "resource":
        for key, missing in (("resource_status", {"resource", "resource/status"}),
            ("independent_pending", {"your_tasks", "your_tasks/independent"}),
            ("computer_pending", {"your_tasks", "your_tasks/computer"})):
            if view[key] is None and not unknown.intersection(missing):
                raise ValueError("Missing normalized task/resource state must remain unknown")
        if any(view[key] is not None for key in ("submission_present", "required_original_ids", "known_original_ids")):
            raise ValueError("Resource view cannot carry a different family's state")
    else:
        if any(view[key] is not None for key in ("resource_status", "independent_pending", "computer_pending")):
            raise ValueError("Communication view cannot carry private resource/task state")
        submission_key = "your_submission" if view["family"] == "complementary" else "your_verdict"
        if view["submission_present"] is None and submission_key not in unknown:
            raise ValueError("Missing submission state must remain unknown")
        if view["family"] == "diffusion" and any(view[key] is not None for key in ("required_original_ids", "known_original_ids")):
            raise ValueError("Diffusion contract has no required-original inventory")
    if view["family"] == "complementary":
        required, known = view["required_original_ids"], view["known_original_ids"]
        if required is None or known is None:
            if "canonical_original_inventory" not in unknown:
                raise ValueError("Missing canonical inventory must remain unknown")
        elif (required != [f"original-{i}" for i in range(4)] or not isinstance(known, list)
                or not all(isinstance(x, str) for x in known) or known != sorted(set(known)) or not set(known) <= set(required)):
            raise ValueError("Invalid normalized canonical inventory")


def evaluate_timing_trigger(view, trigger_state, trigger_spec):
    """Pure arm-blind decision; input state is copied and never mutated."""
    view, state, trigger = _copy(view), _copy(trigger_state), _copy(trigger_spec)
    _validate_view(view); _validate_trigger(trigger); _scan(state)
    if not isinstance(state, dict) or set(state) != STATE_FIELDS or state["version"] != VERSION or type(state["attempted"]) is not bool:
        raise ValueError("Invalid arm-blind controller state")
    previous = state["previous_view"]
    if previous is not None:
        _validate_view(previous)
        if previous["recipient"] != trigger["recipient"]:
            raise ValueError("Controller state belongs to a different recipient")
        if (view["recipient"] == trigger["recipient"] and previous["step"] is not None
                and view["step"] is not None and view["step"] <= previous["step"]):
            raise ValueError("Focal decision boundaries must advance")
        if view["recipient"] == trigger["recipient"]:
            if previous["family"] != view["family"]:
                raise ValueError("Focal boundaries cannot switch public environment family")
            if previous["own_decision_index"] is not None and view["own_decision_index"] is not None:
                if (view["own_decision_index"] <= previous["own_decision_index"] or
                        view["history"][:len(previous["history"])] != previous["history"]):
                    raise ValueError("Known completed own history must advance without rewriting its saved prefix")
    evidence = []
    def result(eligible, reason):
        if view["recipient"] == trigger["recipient"]:
            state["previous_view"] = _copy(view)
        if eligible is True: state["attempted"] = True
        return {"eligible": eligible, "reason_code": reason, "evidence": evidence,
                "view_hash": view["view_hash"], "trigger_hash": digest(trigger), "next_state": state}
    def fact(path, value): evidence.append({"path": path, "value": _copy(value)})
    if view["recipient"] != trigger["recipient"]: return result(False, "different_recipient")
    if state["attempted"]: return result(False, "preparation_already_attempted")
    if view["unknown_fields"]: return result(None, "required_public_state_unknown")
    if view["turns_remaining"] == 0 or view["submission_present"] is True: return result(False, "no_remaining_decision_or_finalized")
    kind = trigger["kind"]
    if kind == "first_decision":
        fact("own_decision_index", view["own_decision_index"])
        return result(view["own_decision_index"] == 1, "first_decision" if view["own_decision_index"] == 1 else "first_decision_passed")
    expected_family = "complementary" if kind == "late_canonical_fragment_gap" else "resource"
    if view["family"] != expected_family: return result(None, "unsupported_trigger_public_family")
    if kind == "late_canonical_fragment_gap":
        fact("turns_remaining", view["turns_remaining"]); fact("known_original_ids", view["known_original_ids"])
        fact("required_original_ids", view["required_original_ids"])
        gap = len(view["known_original_ids"]) < len(view["required_original_ids"])
        return result(view["turns_remaining"] == trigger["gap_turns_remaining"] and gap,
                      "late_canonical_gap" if view["turns_remaining"] == trigger["gap_turns_remaining"] and gap else "late_gap_boundary_not_eligible")
    if previous is None or previous["family"] != "resource" or previous["unknown_fields"]:
        return result(None, "prior_scoped_boundary_unobserved")
    if len(view["history"]) != len(previous["history"]) + 1 or view["history"][:-1] != previous["history"] or view["history"][-1]["step"] != previous["step"]:
        return result(None, "prior_action_boundary_not_contiguous")
    if kind == "first_observed_resource_open":
        fact("previous/resource_status", previous["resource_status"]); fact("resource_status", view["resource_status"])
        fact("computer_pending", view["computer_pending"])
        eligible = previous["resource_status"] == "external_occupation" and view["resource_status"] == "available" and view["computer_pending"]
        return result(bool(eligible), "observed_resource_open" if eligible else "no_observed_reopening")
    last = view["history"][-1]
    fact("history/last", last); fact("previous/independent_pending", previous["independent_pending"])
    fact("independent_pending", view["independent_pending"])
    eligible = last["action_name"] == "wait" and last["ok"] is True and last["waited"] is True and previous["independent_pending"] is True and view["independent_pending"] is True
    return result(eligible, "executed_wait_with_independent_opportunity" if eligible else "no_executed_unused_opportunity")


class TimingController:
    """Local prepare/receipt protocol; never calls or alters an environment."""
    def __init__(self, spec, assignment="active"):
        validate_timing_spec(spec)
        if assignment not in ("active", "neutral"): raise ValueError("Preassign active or neutral content")
        self._spec, self._assignment = _copy(spec), assignment
        self.reset()

    def reset(self):
        self._check_source()
        self._state, self._events, self._pending, self._receipt, self._failure, self._final = initial_trigger_state(), [], None, None, None, None
        return self.snapshot()

    def _check_source(self):
        if self._spec["module_hash"] != module_hash():
            raise ValueError("Timing controller source differs from the pinned spec")

    def snapshot(self):
        return _copy({"trigger_state": self._state, "events": self._events, "pending": self._pending,
                      "receipt": self._receipt, "failure": self._failure, "finalized": self._final is not None})

    def prepare(self, request):
        self._check_source()
        if self._final is not None: raise ValueError("Timing contract already finalized")
        if self._pending is not None: raise ValueError("Record or fail the exact pending delivery before another boundary")
        if sum(event["type"] == "prepare" for event in self._events) >= self._spec["delivery"]["max_evaluations"]:
            raise ValueError("Declared evaluated-boundary cap exhausted")
        request = _copy(request); view = make_trigger_view(request)
        logical = (view["recipient"], view["step"])
        if any((event["view"]["recipient"], event["view"]["step"]) == logical for event in self._events if event["type"] == "prepare"):
            raise ValueError("Duplicate observed decision boundary")
        previous = self._state["previous_view"]
        if (previous is not None and view["recipient"] == self._spec["trigger"]["recipient"]
                and previous["step"] is not None and view["step"] is not None and view["step"] <= previous["step"]):
            raise ValueError("Focal decision boundaries must advance")
        decision = evaluate_timing_trigger(view, self._state, self._spec["trigger"])
        before_hash = digest(self._state); next_state = _copy(decision["next_state"])
        identity = digest({"spec_hash": self._spec["spec_hash"], "view_hash": view["view_hash"], "boundary": len(self._events)})
        text = self._spec["content"][self._assignment] if decision["eligible"] is True else None
        output = {"decision": decision, "opportunity_id": identity, "insertion_text": text,
                  "request_hash_before_insertion": view["request_hash"], "trigger_state_hash_before": before_hash,
                  "trigger_state_hash_after": digest(next_state)}
        event = {"type": "prepare", "request": request, "view": view, "output": _copy(output)}
        pending = {"opportunity_id": identity, "request": request, "text": text} if text is not None else None
        candidate = {"trigger_state": next_state, "events": self._events + [event], "pending": pending,
                     "receipt": self._receipt, "failure": self._failure, "finalized": False}
        if _json_bytes(candidate) > TRACE_MAX_BYTES - DELIVERY_RESERVE_BYTES:
            raise ValueError("Declared cumulative trace cap exhausted before mutation; finalize the retained partial trace")
        self._state, self._pending = next_state, pending
        self._events.append(event)
        return _copy(output)

    def fail_delivery(self, opportunity_id, *, reason="infrastructure_failure", failed_request_hash=None):
        self._check_source()
        if self._final is not None: raise ValueError("Timing contract already finalized")
        if self._pending is None or self._pending["opportunity_id"] != opportunity_id:
            raise ValueError("No matching pending delivery")
        if reason not in ("infrastructure_failure", "request_contract_mismatch") or failed_request_hash is not None and not _digest_string(failed_request_hash):
            raise ValueError("Unsupported delivery failure declaration")
        self._failure = {"opportunity_id": opportunity_id, "reason": reason, "failed_request_hash": failed_request_hash}
        self._events.append({"type": "delivery_failure", **_copy(self._failure)})
        self._pending = None
        return _copy(self._failure)

    def record_delivery(self, opportunity_id, actual_request):
        self._check_source()
        if self._final is not None: raise ValueError("Timing contract already finalized")
        if self._pending is None or self._pending["opportunity_id"] != opportunity_id:
            raise ValueError("No matching pending delivery")
        try:
            actual = _copy(actual_request)
        except ValueError:
            self.fail_delivery(opportunity_id, reason="request_contract_mismatch")
            raise
        expected = _copy(self._pending["request"]); expected["context"] = [self._pending["text"]]
        if digest(actual) != digest(expected):
            self.fail_delivery(opportunity_id, reason="request_contract_mismatch", failed_request_hash=digest(actual))
            raise ValueError("Delivery must be the exact next scoped request with one inserted note")
        self._receipt = {"opportunity_id": opportunity_id, "recipient": expected["role"], "note_hash": digest(self._pending["text"]),
            "request_hash_before_insertion": digest(self._pending["request"]), "actual_request_hash": digest(actual),
            "spec_hash": self._spec["spec_hash"], "module_hash": module_hash(),
            "scope": "Exact recorded request only; no provider consumption or mental-state attestation"}
        self._events.append({"type": "delivery", "actual_request": actual, "receipt": _copy(self._receipt)})
        self._pending = None
        return _copy(self._receipt)

    def finalize(self, outcome=None, *, reason="horizon_exhausted", execution_status="unknown"):
        """Seal local evidence; only declared completed execution retains an outcome.

        A complete contract with unresolved eligibility remains an unknown trigger
        measurement. Neither an outcome nor execution completion is independently
        verified here. Infra/delivery failures cannot become behavioral exclusions.
        """
        self._check_source()
        if self._final is not None: raise ValueError("Timing contract already finalized")
        if reason not in ("horizon_exhausted", "finalized_before_trigger", "infrastructure_failure"):
            raise ValueError("Unsupported finalization declaration")
        if execution_status not in ("unknown", "completed", "incomplete"):
            raise ValueError("Declare caller world execution completed, incomplete or unknown")
        if reason == "infrastructure_failure" and execution_status == "completed":
            raise ValueError("Infrastructure-aborted execution cannot be declared completed")
        if outcome is not None and (type(outcome) not in (int, float) or not 0 <= outcome <= 1):
            raise ValueError("Optional caller outcome must be a finite bounded number")
        incomplete = self._failure is not None or self._pending is not None or reason == "infrastructure_failure" or execution_status == "incomplete"
        status = "incomplete_delivery" if self._failure is not None or self._pending is not None else "incomplete_infrastructure_failure" if incomplete else "complete_contract"
        recorded_no_delivery = self._receipt is None
        focal = [e for e in self._events if e["type"] == "prepare" and e["view"]["recipient"] == self._spec["trigger"]["recipient"]]
        unknown = not focal or any(e["output"]["decision"]["eligible"] is None for e in focal)
        eligibility_status = "eligible_observed" if self._state["attempted"] else "eligibility_unresolved" if unknown else "known_never_eligible_at_recorded_boundaries"
        behavioral_nondelivery = (False if self._receipt is not None else True if not incomplete and not unknown and execution_status == "completed" else None)
        nondelivery_reason = ("eligibility_unresolved" if unknown else "execution_unresolved" if execution_status != "completed"
                             else reason) if recorded_no_delivery and not incomplete else None
        self._final = _seal({"version": VERSION, "module_hash": module_hash(), "spec_hash": self._spec["spec_hash"], "spec": self._spec,
            "assignment": self._assignment, "assignment_source": "caller_preassigned; this controller does not randomize",
            "execution_status": execution_status, "execution_status_source": "caller_declaration_only; world completion is not attested",
            "status": status, "finalization_reason": reason, "events": self._events, "trigger_state": self._state,
            "pending_delivery": self._pending, "delivery_receipt": self._receipt, "delivery_failure": self._failure,
            "policy_itt": {"unit": "whole_swarm_run", "retain_assigned_unit": True, "assigned_variant": self._assignment,
                "behavioral_nondelivery": behavioral_nondelivery, "nondelivery_reason": nondelivery_reason,
                "recorded_no_delivery": recorded_no_delivery, "eligibility_status": eligibility_status,
                "eligible_preparations": int(self._state["attempted"]), "recorded_deliveries": int(self._receipt is not None),
                "caller_supplied_outcome": outcome if not incomplete and execution_status == "completed" else None,
                "outcome_attestation": "not_performed"},
            "model_calls": 0, "causal_analysis_available": False,
            "limitations": ["Standalone CPU contract; no experiment/world integration or verified provider execution.",
                "A view hash checks its recorded bytes, not truthful provenance or historical fidelity.",
                "Observed waits and canonical inventory are process measures, not latent beliefs or identified mediation.",
                "Whole-policy ITT retains behavioral nondelivery; incomplete infrastructure is not a behavioral exclusion.",
                "Matched words do not guarantee matched tokens or an inert neutral note."]}, "report_hash")
        return _copy(self._final)


def replay_timing_report(report):
    """Reconstruct the local contract with no model calls; partial status stays partial."""
    try:
        _check_seal(report, "report_hash")
        validate_timing_spec(report["spec"])
        controller = TimingController(report["spec"], report["assignment"])
        for event in report["events"]:
            if event["type"] == "prepare":
                controller.prepare(event["request"])
            elif event["type"] == "delivery":
                controller.record_delivery(event["receipt"]["opportunity_id"], event["actual_request"])
            elif event["type"] == "delivery_failure":
                controller.fail_delivery(event["opportunity_id"], reason=event["reason"], failed_request_hash=event["failed_request_hash"])
            else: raise ValueError("Unsupported timing event")
            if controller.snapshot()["events"][-1] != event:
                raise ValueError("Recorded timing event differs from deterministic reconstruction")
        outcome = report["policy_itt"]["caller_supplied_outcome"]
        rebuilt = controller.finalize(outcome, reason=report["finalization_reason"], execution_status=report["execution_status"])
        consistent = digest(rebuilt) == digest(report)
        return {"passed": consistent and report["status"] == "complete_contract", "partial_trace_consistent": consistent,
                "model_calls": 0, "scope": "Recorded local preparation/request contract; no provider or causal-result attestation"}
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        return {"passed": False, "partial_trace_consistent": False, "error_type": type(exc).__name__, "model_calls": 0}
