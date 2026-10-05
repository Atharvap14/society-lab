"""CPU contract tests using actual scoped requests; no hosted calls or DB writes."""
import copy
import json
import unittest
from unittest.mock import patch

from swarm_lab.intervention_timing import (TimingController, create_timing_spec, validate_timing_spec,
    make_trigger_view, initial_trigger_state, evaluate_timing_trigger, replay_timing_report, digest, _seal)
from swarm_lab.resource_environment import create_resource_spec, create_resource_environment, resource_subject_request
from swarm_lab.complementary_environment import create_complementary_spec, create_complementary_environment, complementary_subject_request
from swarm_lab.diffusion_environment import create_diffusion_environment, diffusion_subject_request


def next_focal(env, request_fn=resource_subject_request, focal="agent-0"):
    while not env.terminal and env.next_agent != focal:
        env.step(env.next_agent, {"action": "wait"})
    if env.terminal:
        raise AssertionError("Fixture exhausted before a focal boundary")
    return request_fn(env, focal)


def resource(*, release=3, rounds=3, seed=19):
    return create_resource_environment(create_resource_spec(max_rounds=rounds, release_rounds=(release,)), seed)


def delivered(controller, request):
    prepared = controller.prepare(request)
    packet = copy.deepcopy(request)
    packet["context"] = [prepared["insertion_text"]]
    return prepared, controller.record_delivery(prepared["opportunity_id"], packet)


class TimingContractTests(unittest.TestCase):
    def test_actual_scoped_views_strip_text_values_context_and_assignment(self):
        env = resource()
        request = next_focal(env)
        request["system"] = "UNIQUE_SYSTEM_TEXT"
        request["observation"]["received_messages"] = [{"message": "UNIQUE_MESSAGE_TEXT arm neutral future release"}]
        request["observation"]["your_private_context"] = []
        view = make_trigger_view(request)
        self.assertEqual(view["family"], "resource")
        self.assertEqual(view["unknown_fields"], [])
        text = json.dumps(view)
        for value in ("UNIQUE_SYSTEM_TEXT", "UNIQUE_MESSAGE_TEXT", "action_schema", "context", "lease_holder"):
            self.assertNotIn(value, text)
        self.assertEqual(view["request_hash"], digest(request))
        comp = create_complementary_environment(seed=17)
        comp_view = make_trigger_view(next_focal(comp, complementary_subject_request))
        self.assertEqual(comp_view["known_original_ids"], ["original-0"])
        self.assertNotIn("value", comp_view)
        self.assertIsNone(comp_view["resource_status"])

    def test_recursive_privileged_fields_and_nonempty_context_fail_closed(self):
        request = next_focal(resource())
        for key in ("seed", "environment_seed", "future_release", "future_decision", "oracle_target", "arm", "assigned_arm",
                    "notes", "latent_state", "peer_progress", "proposed_action", "candidate_action", "chain_of_thought"):
            with self.subTest(key=key):
                bad = copy.deepcopy(request)
                bad["observation"]["received_messages"] = [{"message": "x", key: "do not use"}]
                with self.assertRaises(ValueError): make_trigger_view(bad)
        for location in ("context", "nested_context", "your_private_context"):
            bad = copy.deepcopy(request)
            if location == "context": bad["context"] = ["private note"]
            elif location == "your_private_context": bad["observation"][location] = ["private note"]
            else: bad["observation"]["received_messages"] = [{"context": []}]
            with self.assertRaises(ValueError): make_trigger_view(bad)

    def test_exact_envelope_and_enums_not_inferred_from_names(self):
        request = next_focal(resource())
        mutations = [lambda r: r.update(extra_public="x"),
                     lambda r: r["observation"].update(browser_state={}),
                     lambda r: r["observation"].update(agent_id="agent-1"),
                     lambda r: r["observation"].update(participants=["agent-0"]),
                     lambda r: r["action_schema"]["properties"]["action"].update(enum=["wait"])]
        for mutate in mutations:
            bad = copy.deepcopy(request); mutate(bad)
            with self.assertRaises(ValueError): make_trigger_view(bad)

    def test_note_counts_spec_hash_and_source_contract_are_frozen(self):
        spec = create_timing_spec("first_decision")
        self.assertTrue(validate_timing_spec(spec))
        self.assertEqual(len(spec["content"]["active"].split()), len(spec["content"]["neutral"].split()))
        self.assertEqual(spec["delivery"]["token_matching"], "not_guaranteed")
        for kwargs in ({"active_text": "two words", "neutral_text": "one"}, {"active_text": "", "neutral_text": ""},
                       {"max_evaluations": True}, {"gap_turns_remaining": 0}):
            with self.assertRaises(ValueError): create_timing_spec("first_decision", **kwargs)
        bad = copy.deepcopy(spec); bad["content"]["active"] += " changed"
        with self.assertRaises(ValueError): validate_timing_spec(bad)
        bad = copy.deepcopy(spec); bad["module_hash"] = "0" * 64; bad = _seal(bad, "spec_hash")
        with self.assertRaises(ValueError): validate_timing_spec(bad)

    def test_live_controller_rejects_source_drift_before_another_mutation(self):
        controller = TimingController(create_timing_spec("first_decision"))
        request = next_focal(resource()); before = controller.snapshot()
        with patch("swarm_lab.intervention_timing.module_hash", return_value="0" * 64):
            with self.assertRaises(ValueError): controller.prepare(request)
            with self.assertRaises(ValueError): controller.finalize()
            with self.assertRaises(ValueError): controller.reset()
        self.assertEqual(controller.snapshot(), before)

    def test_pure_trigger_only_takes_arm_blind_fields_and_copies_inputs(self):
        spec = create_timing_spec("first_decision")
        view = make_trigger_view(next_focal(resource()))
        state = initial_trigger_state()
        before = copy.deepcopy((view, state, spec["trigger"]))
        result = evaluate_timing_trigger(view, state, spec["trigger"])
        self.assertTrue(result["eligible"])
        self.assertEqual((view, state, spec["trigger"]), before)
        result["next_state"]["previous_view"]["history"].append({})
        self.assertEqual(view, before[0])
        with self.assertRaises(ValueError): evaluate_timing_trigger(view, state, spec)
        with self.assertRaises(ValueError): evaluate_timing_trigger(view, {**state, "arm": "active"}, spec["trigger"])
        with self.assertRaises(ValueError): evaluate_timing_trigger(_seal({**view, "truth": 1}, "view_hash"), state, spec["trigger"])

    def test_active_neutral_decisions_are_identical_before_text_delivery(self):
        spec = create_timing_spec("executed_wait_independent_pending")
        a, n = TimingController(spec, "active"), TimingController(spec, "neutral")
        env = resource()
        request = next_focal(env)
        first = [c.prepare(request) for c in (a, n)]
        self.assertEqual(first[0]["decision"], first[1]["decision"])
        self.assertIsNone(first[0]["decision"]["eligible"])
        env.step("agent-0", {"action": "wait"}); request = next_focal(env)
        second = [c.prepare(request) for c in (a, n)]
        self.assertEqual(second[0]["decision"], second[1]["decision"])
        self.assertEqual(second[0]["trigger_state_hash_after"], second[1]["trigger_state_hash_after"])
        self.assertNotEqual(second[0]["insertion_text"], second[1]["insertion_text"])
        self.assertEqual(a.snapshot()["trigger_state"], n.snapshot()["trigger_state"])

    def test_unknown_required_state_abstains_and_cannot_be_resealed_as_known(self):
        request = next_focal(resource())
        for path in ("step", "your_turns_remaining", "your_action_history", "resource", "your_tasks"):
            with self.subTest(path=path):
                bad = copy.deepcopy(request); bad["observation"][path] = None
                view = make_trigger_view(bad)
                result = evaluate_timing_trigger(view, initial_trigger_state(), create_timing_spec("first_decision")["trigger"])
                self.assertIsNone(result["eligible"])
                view["unknown_fields"] = []; view = _seal(view, "view_hash")
                with self.assertRaises(ValueError): evaluate_timing_trigger(view, initial_trigger_state(), create_timing_spec("first_decision")["trigger"])

    def test_constructor_and_pure_view_reject_future_or_reversed_completed_history(self):
        env = resource(rounds=4, release=4)
        for _ in range(2):
            next_focal(env); env.step("agent-0", {"action": "wait"})
        request = next_focal(env)
        for mutate in (lambda h, step: h.reverse(), lambda h, step: h[0].update(step=step),
                       lambda h, step: h[1].update(step=h[0]["step"])):
            bad = copy.deepcopy(request); mutate(bad["observation"]["your_action_history"], bad["observation"]["step"])
            with self.assertRaises(ValueError): make_trigger_view(bad)
            view = make_trigger_view(request); mutate(view["history"], view["step"]); view = _seal(view, "view_hash")
            with self.assertRaises(ValueError): evaluate_timing_trigger(view, initial_trigger_state(), create_timing_spec("first_decision")["trigger"])
        view = make_trigger_view(request); view["own_decision_index"] += 1; view = _seal(view, "view_hash")
        with self.assertRaises(ValueError): evaluate_timing_trigger(view, initial_trigger_state(), create_timing_spec("first_decision")["trigger"])

    def test_pure_view_disjoint_family_and_missing_result_guards(self):
        request = next_focal(resource())
        view = make_trigger_view(request); view["known_original_ids"] = ["original-0"]; view = _seal(view, "view_hash")
        with self.assertRaises(ValueError): evaluate_timing_trigger(view, initial_trigger_state(), create_timing_spec("first_decision")["trigger"])
        env = resource(); next_focal(env); env.step("agent-0", {"action": "wait"}); request = next_focal(env)
        request["observation"]["your_action_history"][-1]["result"].pop("waited")
        view = make_trigger_view(request)
        self.assertIn("your_action_history/result/waited", view["unknown_fields"])
        self.assertIsNone(evaluate_timing_trigger(view, initial_trigger_state(), create_timing_spec("executed_wait_independent_pending")["trigger"])["eligible"])

    def test_first_decision_fixed_recipient_no_late_fallback(self):
        env = resource()
        spec = create_timing_spec("first_decision")
        view = make_trigger_view(resource_subject_request(env, "agent-1"))
        decision = evaluate_timing_trigger(view, initial_trigger_state(), spec["trigger"])
        self.assertFalse(decision["eligible"]); self.assertIsNone(decision["next_state"]["previous_view"])
        next_focal(env); env.step("agent-0", {"action": "wait"})
        controller = TimingController(spec)
        output = controller.prepare(next_focal(env))
        self.assertFalse(output["decision"]["eligible"]); self.assertIsNone(output["insertion_text"])
        report = controller.finalize(.5, execution_status="completed")
        self.assertTrue(report["policy_itt"]["behavioral_nondelivery"])
        self.assertEqual(report["policy_itt"]["caller_supplied_outcome"], .5)

    def test_resource_wait_requires_saved_pre_action_independent_opportunity(self):
        env = resource(); controller = TimingController(create_timing_spec("executed_wait_independent_pending"))
        first = controller.prepare(next_focal(env))
        self.assertEqual(first["decision"]["reason_code"], "prior_scoped_boundary_unobserved")
        env.step("agent-0", {"action": "wait"}); request = next_focal(env)
        output = controller.prepare(request)
        self.assertTrue(output["decision"]["eligible"])
        self.assertEqual(output["decision"]["evidence"][-1], {"path": "independent_pending", "value": True})
        missed = TimingController(create_timing_spec("executed_wait_independent_pending")).prepare(request)
        self.assertIsNone(missed["decision"]["eligible"])

    def test_task_specific_wait_and_invalid_action_do_not_imply_unused_opportunity(self):
        for first_action in ({"action": "work_independent"}, {"action": "wait", "extra": "invalid"}):
            env = resource(); controller = TimingController(create_timing_spec("executed_wait_independent_pending"))
            controller.prepare(next_focal(env)); env.step("agent-0", first_action)
            self.assertFalse(controller.prepare(next_focal(env))["decision"]["eligible"])
            if first_action["action"] == "work_independent":
                env.step("agent-0", {"action": "wait"})
                self.assertFalse(controller.prepare(next_focal(env))["decision"]["eligible"])

    def test_skipped_prior_boundary_abstains_rather_than_reconstructing_opportunity(self):
        env = resource(rounds=4, release=4)
        controller = TimingController(create_timing_spec("executed_wait_independent_pending"))
        controller.prepare(next_focal(env)); env.step("agent-0", {"action": "wait"})
        next_focal(env); env.step("agent-0", {"action": "wait"})
        decision = controller.prepare(next_focal(env))["decision"]
        self.assertIsNone(decision["eligible"])
        self.assertEqual(decision["reason_code"], "prior_action_boundary_not_contiguous")

    def test_all_focal_triggers_reject_rewritten_or_truncated_saved_history(self):
        for kind in ("first_decision", "late_canonical_fragment_gap"):
            for mutation in ("action", "result", "hidden_result_detail", "truncate", "same_index"):
                with self.subTest(kind=kind, mutation=mutation):
                    env = create_complementary_environment(create_complementary_spec(max_rounds=4), seed=7)
                    controller = TimingController(create_timing_spec(kind))
                    first = next_focal(env, complementary_subject_request)
                    # For first-decision, consume the single allowed preparation
                    # so append-only validation still applies after insertion.
                    if kind == "first_decision":
                        delivered(controller, first)
                    else:
                        controller.prepare(first)
                    env.step("agent-0", {"action": "wait"})
                    second = next_focal(env, complementary_subject_request)
                    controller.prepare(second)
                    env.step("agent-0", {"action": "wait"})
                    third = next_focal(env, complementary_subject_request)
                    saved = controller.snapshot()
                    if mutation == "action":
                        third["observation"]["your_action_history"][0].update(action={"action": "inspect_fragment"}, result={"ok": True})
                    elif mutation == "result":
                        third["observation"]["your_action_history"][0]["result"]["waited"] = False
                    elif mutation == "hidden_result_detail":
                        third["observation"]["your_action_history"][0]["result"]["extra_public_detail"] = "changed"
                    elif mutation == "truncate":
                        third["observation"]["your_action_history"] = []
                    else:
                        third["observation"]["your_action_history"] = copy.deepcopy(second["observation"]["your_action_history"])
                    with self.assertRaises(ValueError): controller.prepare(third)
                    self.assertEqual(controller.snapshot(), saved)
                    forged_view = make_trigger_view(third)
                    with self.assertRaises(ValueError): evaluate_timing_trigger(forged_view, saved["trigger_state"], controller._spec["trigger"])

    def test_skipped_communication_boundaries_with_unchanged_prefix_remain_legal(self):
        env = create_complementary_environment(create_complementary_spec(max_rounds=4), seed=7)
        controller = TimingController(create_timing_spec("late_canonical_fragment_gap"))
        controller.prepare(next_focal(env, complementary_subject_request))
        env.step("agent-0", {"action": "wait"})
        next_focal(env, complementary_subject_request); env.step("agent-0", {"action": "wait"})
        output = controller.prepare(next_focal(env, complementary_subject_request))
        self.assertTrue(output["decision"]["eligible"])

    def test_observed_resource_reopening_uses_current_state_not_future_release(self):
        env = resource(rounds=4, release=1)
        controller = TimingController(create_timing_spec("first_observed_resource_open"))
        self.assertIsNone(controller.prepare(next_focal(env))["decision"]["eligible"])
        env.step("agent-0", {"action": "wait"})
        output = controller.prepare(next_focal(env))
        self.assertTrue(output["decision"]["eligible"])
        self.assertEqual(output["decision"]["reason_code"], "observed_resource_open")
        initial_open = resource(release=0)
        self.assertIsNone(TimingController(create_timing_spec("first_observed_resource_open")).prepare(next_focal(initial_open))["decision"]["eligible"])

    def test_resource_remains_closed_or_leased_not_observed_open(self):
        env = resource(); controller = TimingController(create_timing_spec("first_observed_resource_open"))
        controller.prepare(next_focal(env)); env.step("agent-0", {"action": "wait"})
        self.assertFalse(controller.prepare(next_focal(env))["decision"]["eligible"])
        env = resource(rounds=4, release=1); controller = TimingController(create_timing_spec("first_observed_resource_open"))
        controller.prepare(next_focal(env)); env.step("agent-0", {"action": "wait"})
        while env.next_agent != "agent-0":
            action = "request_computer" if env.resource_state()["status"] == "available" else "wait"
            env.step(env.next_agent, {"action": action})
        self.assertEqual(env.resource_state()["status"], "leased")
        self.assertFalse(controller.prepare(resource_subject_request(env, "agent-0"))["decision"]["eligible"])

    def test_complementary_late_gap_safe_and_diffusion_gap_unsupported(self):
        env = create_complementary_environment(seed=2)
        controller = TimingController(create_timing_spec("late_canonical_fragment_gap"))
        self.assertFalse(controller.prepare(next_focal(env, complementary_subject_request))["decision"]["eligible"])
        env.step("agent-0", {"action": "wait"})
        self.assertTrue(controller.prepare(next_focal(env, complementary_subject_request))["decision"]["eligible"])
        diffusion = create_diffusion_environment(seed=2)
        unsupported = TimingController(create_timing_spec("late_canonical_fragment_gap")).prepare(next_focal(diffusion, diffusion_subject_request))
        self.assertIsNone(unsupported["decision"]["eligible"])
        self.assertEqual(unsupported["decision"]["reason_code"], "unsupported_trigger_public_family")

    def test_full_inventory_and_final_submission_are_not_gaps(self):
        env = create_complementary_environment(create_complementary_spec(topology="complete"), seed=21)
        # All four legally multicast their initial inventory in the first round.
        for _ in range(4):
            actor = env.next_agent
            env.step(actor, {"action": "send_neighbors", "message": "canonical attachments", "fragment_ids": list(env.known_fragments[actor])})
        request = next_focal(env, complementary_subject_request)
        self.assertEqual(len(request["observation"]["known_fragments"]), 4)
        controller = TimingController(create_timing_spec("late_canonical_fragment_gap"))
        self.assertFalse(controller.prepare(request)["decision"]["eligible"])
        env.step("agent-0", {"action": "submit_total", "total": 0})
        request = next_focal(env, complementary_subject_request)
        output = controller.prepare(request)
        self.assertFalse(output["decision"]["eligible"])
        self.assertEqual(output["decision"]["reason_code"], "no_remaining_decision_or_finalized")

    def test_canonical_fragment_integrity_and_duplicates_are_checked_before_gap(self):
        request = next_focal(create_complementary_environment(), complementary_subject_request)
        for mutate in (lambda fs: fs.append(copy.deepcopy(fs[0])), lambda fs: fs[0].update(value=999),
                       lambda fs: fs[0].update(component_index=True), lambda fs: fs[0].update(original_holder="agent-1")):
            bad = copy.deepcopy(request); mutate(bad["observation"]["known_fragments"])
            with self.assertRaises(ValueError): make_trigger_view(bad)

    def test_logical_duplicate_ignores_system_text_and_boundary_order_cannot_reverse(self):
        env = resource(); controller = TimingController(create_timing_spec("late_canonical_fragment_gap"))
        request = next_focal(env); controller.prepare(request)
        duplicate = copy.deepcopy(request); duplicate["system"] += " Different text"
        with self.assertRaises(ValueError): controller.prepare(duplicate)
        env.step("agent-0", {"action": "wait"}); controller.prepare(next_focal(env))
        with self.assertRaises(ValueError): controller.prepare(request)
        view = make_trigger_view(request)
        with self.assertRaises(ValueError): evaluate_timing_trigger(view, controller.snapshot()["trigger_state"], create_timing_spec("late_canonical_fragment_gap")["trigger"])

    def test_many_noneligible_boundaries_one_eligible_preparation_then_no_fallback(self):
        env = resource(rounds=5, release=5)
        spec = create_timing_spec("executed_wait_independent_pending")
        controller = TimingController(spec)
        controller.prepare(next_focal(env))
        env.step("agent-0", {"action": "send_message", "recipient": "agent-1", "message": "hello"})
        self.assertFalse(controller.prepare(next_focal(env))["decision"]["eligible"])
        env.step("agent-0", {"action": "wait"})
        request = next_focal(env); opportunity = controller.prepare(request)
        self.assertTrue(opportunity["decision"]["eligible"])
        with self.assertRaises(ValueError): controller.prepare(request)
        controller.fail_delivery(opportunity["opportunity_id"])
        env.step("agent-0", {"action": "wait"})
        later = controller.prepare(next_focal(env))
        self.assertFalse(later["decision"]["eligible"])
        self.assertEqual(later["decision"]["reason_code"], "preparation_already_attempted")
        self.assertIsNone(later["insertion_text"])
        report = controller.finalize(.75, execution_status="completed")
        self.assertEqual(report["status"], "incomplete_delivery")
        self.assertEqual(report["policy_itt"]["eligible_preparations"], 1)
        self.assertIsNone(report["policy_itt"]["caller_supplied_outcome"])
        replay = replay_timing_report(report)
        self.assertFalse(replay["passed"]); self.assertTrue(replay["partial_trace_consistent"])

    def test_exact_next_request_receipt_and_hash_roles(self):
        request = next_focal(resource()); controller = TimingController(create_timing_spec("first_decision"))
        opportunity, receipt = delivered(controller, request)
        packet = copy.deepcopy(request); packet["context"] = [opportunity["insertion_text"]]
        self.assertEqual(receipt["actual_request_hash"], digest(packet))
        self.assertEqual(receipt["request_hash_before_insertion"], digest(request))
        self.assertEqual(receipt["note_hash"], digest(opportunity["insertion_text"]))
        hashes = {receipt["module_hash"], receipt["spec_hash"], receipt["actual_request_hash"], receipt["request_hash_before_insertion"], opportunity["decision"]["view_hash"]}
        self.assertEqual(len(hashes), 5)
        with self.assertRaises(ValueError): controller.record_delivery(opportunity["opportunity_id"], packet)
        self.assertTrue(replay_timing_report(controller.finalize(.5, execution_status="completed"))["passed"])

    def test_altered_recipient_observation_schema_or_double_context_fails_once(self):
        request = next_focal(resource())
        mutations = [lambda p: p.update(role="agent-1"), lambda p: p["observation"].update(step=999),
                     lambda p: p["action_schema"].update(description="changed"), lambda p: p["context"].append(p["context"][0]),
                     lambda p: p.update(context=[]), lambda p: p.update(context=["another note"])]
        for mutate in mutations:
            controller = TimingController(create_timing_spec("first_decision"))
            output = controller.prepare(request)
            packet = copy.deepcopy(request); packet["context"] = [output["insertion_text"]]; mutate(packet)
            with self.assertRaises(ValueError): controller.record_delivery(output["opportunity_id"], packet)
            snapshot = controller.snapshot()
            self.assertIsNone(snapshot["pending"]); self.assertIsNone(snapshot["receipt"])
            self.assertEqual(snapshot["failure"]["reason"], "request_contract_mismatch")
            correct = copy.deepcopy(request); correct["context"] = [output["insertion_text"]]
            with self.assertRaises(ValueError): controller.record_delivery(output["opportunity_id"], correct)
            self.assertEqual(controller.finalize()["status"], "incomplete_delivery")

    def test_invalid_nonfinite_delivery_records_failure_without_rerun(self):
        controller = TimingController(create_timing_spec("first_decision"))
        output = controller.prepare(next_focal(resource()))
        with self.assertRaises(ValueError): controller.record_delivery(output["opportunity_id"], {"invalid": float("nan")})
        report = controller.finalize()
        self.assertEqual(report["policy_itt"]["eligible_preparations"], 1)
        self.assertEqual(report["status"], "incomplete_delivery")
        self.assertTrue(replay_timing_report(report)["partial_trace_consistent"])

    def test_unknown_eligibility_is_not_behavioral_nondelivery_but_assignment_is_retained(self):
        controller = TimingController(create_timing_spec("executed_wait_independent_pending"), "neutral")
        controller.prepare(next_focal(resource()))
        report = controller.finalize(.25, execution_status="completed")
        self.assertEqual(report["status"], "complete_contract")
        self.assertTrue(report["policy_itt"]["recorded_no_delivery"])
        self.assertIsNone(report["policy_itt"]["behavioral_nondelivery"])
        self.assertEqual(report["policy_itt"]["eligibility_status"], "eligibility_unresolved")
        self.assertTrue(report["policy_itt"]["retain_assigned_unit"])
        self.assertEqual(report["policy_itt"]["assigned_variant"], "neutral")
        self.assertEqual(report["policy_itt"]["caller_supplied_outcome"], .25)
        self.assertTrue(replay_timing_report(report)["passed"])

    def test_execution_completion_is_explicit_and_outcome_is_not_inferred(self):
        for status in ("unknown", "completed", "incomplete"):
            controller = TimingController(create_timing_spec("first_decision"))
            delivered(controller, next_focal(resource()))
            report = controller.finalize(.75, execution_status=status)
            self.assertEqual(report["policy_itt"]["caller_supplied_outcome"], .75 if status == "completed" else None)
            self.assertEqual(report["status"], "incomplete_infrastructure_failure" if status == "incomplete" else "complete_contract")
            self.assertFalse(report["causal_analysis_available"])
            self.assertEqual(report["model_calls"], 0)
            self.assertIn("caller_declaration_only", report["execution_status_source"])
            self.assertTrue(replay_timing_report(report)["partial_trace_consistent"])
        with self.assertRaises(ValueError): TimingController(create_timing_spec("first_decision")).finalize(reason="infrastructure_failure", execution_status="completed")

    def test_pending_and_infrastructure_failures_are_partial_not_nondelivery(self):
        controller = TimingController(create_timing_spec("first_decision"))
        controller.prepare(next_focal(resource()))
        report = controller.finalize(.5, execution_status="incomplete")
        self.assertEqual(report["status"], "incomplete_delivery")
        self.assertIsNone(report["policy_itt"]["behavioral_nondelivery"])
        self.assertIsNone(report["policy_itt"]["caller_supplied_outcome"])
        replay = replay_timing_report(report)
        self.assertFalse(replay["passed"]); self.assertTrue(replay["partial_trace_consistent"])
        controller = TimingController(create_timing_spec("first_decision"))
        report = controller.finalize(reason="infrastructure_failure")
        self.assertEqual(report["status"], "incomplete_infrastructure_failure")
        self.assertIsNone(report["policy_itt"]["behavioral_nondelivery"])

    def test_finalize_is_immutable_then_explicit_reset_restores_fresh_state(self):
        controller = TimingController(create_timing_spec("first_decision"))
        fresh = controller.snapshot()
        request = next_focal(resource()); output = controller.prepare(request)
        report = controller.finalize()
        packet = copy.deepcopy(request); packet["context"] = [output["insertion_text"]]
        for fn in (lambda: controller.prepare(request), lambda: controller.record_delivery(output["opportunity_id"], packet),
                   lambda: controller.fail_delivery(output["opportunity_id"]), lambda: controller.finalize()):
            with self.assertRaises(ValueError): fn()
        report["events"].clear()
        self.assertTrue(controller.snapshot()["events"])
        self.assertEqual(controller.reset(), fresh)
        self.assertTrue(controller.prepare(request)["decision"]["eligible"])

    def test_max_evaluations_is_a_boundary_cap_not_an_insertion_cap(self):
        env = resource(); controller = TimingController(create_timing_spec("late_canonical_fragment_gap", max_evaluations=1))
        self.assertIsNone(controller.prepare(next_focal(env))["decision"]["eligible"])
        env.step("agent-0", {"action": "wait"})
        with self.assertRaises(ValueError): controller.prepare(next_focal(env))
        self.assertEqual(controller.snapshot()["trigger_state"]["attempted"], False)

    def test_request_and_cumulative_trace_caps_reject_before_state_mutation(self):
        env = resource(rounds=30, release=30)
        controller = TimingController(create_timing_spec("late_canonical_fragment_gap"))
        request = next_focal(env); request["system"] = "x" * 1_100_000
        before = controller.snapshot()
        with self.assertRaises(ValueError): controller.prepare(request)
        self.assertEqual(controller.snapshot(), before)
        # Each accepted large request fits its declared limit. The aggregate cap
        # must preserve an exportable retained trace when a later boundary fails.
        rejected = False
        for _ in range(30):
            request = next_focal(env); request["system"] = "x" * 59_000
            before = controller.snapshot()
            try:
                controller.prepare(request)
            except ValueError as exc:
                self.assertIn("cumulative trace cap", str(exc))
                self.assertEqual(controller.snapshot(), before)
                rejected = True
                break
            env.step("agent-0", {"action": "wait"})
        self.assertTrue(rejected)
        report = controller.finalize(reason="infrastructure_failure", execution_status="incomplete")
        self.assertEqual(report["status"], "incomplete_infrastructure_failure")
        self.assertTrue(replay_timing_report(report)["partial_trace_consistent"])

    def test_replay_detects_resigned_request_decision_receipt_and_source_tampering(self):
        controller = TimingController(create_timing_spec("first_decision"))
        delivered(controller, next_focal(resource()))
        report = controller.finalize(.5, execution_status="completed")
        self.assertTrue(replay_timing_report(report)["passed"])
        mutations = [lambda r: r["events"][0]["request"].update(system="changed"),
                     lambda r: r["events"][0]["output"]["decision"].update(eligible=False),
                     lambda r: r["events"][1]["actual_request"].update(context=[]),
                     lambda r: r["delivery_receipt"].update(actual_request_hash="0" * 64),
                     lambda r: r["trigger_state"].update(attempted=False),
                     lambda r: r.update(module_hash="0" * 64)]
        for mutate in mutations:
            bad = copy.deepcopy(report); mutate(bad); bad = _seal(bad, "report_hash")
            replay = replay_timing_report(bad)
            self.assertFalse(replay["passed"]); self.assertFalse(replay["partial_trace_consistent"])
        bad = copy.deepcopy(report); bad["status"] = "invented"
        self.assertFalse(replay_timing_report(bad)["passed"])


if __name__ == "__main__":
    unittest.main()
