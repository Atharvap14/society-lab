"""Finite claims, evidence binding, and actor/version semantics without paid calls."""
import copy
import json
import unittest

from swarm_lab.claim_audit import (CLAIM_SCHEMA, CLAIMS_SCHEMA, audit_claims,
                                  build_fact_ledger, claims_schema_for_packet, default_fact_ids, make_claim,
                                  select_fact_packet, validate_claim)


def artifact_run(identity, arm, success, *, published_version=1, own_version=None,
                 peer_version=None, repaired=False):
    turns = []
    def turn(agent, action, result):
        turns.append({"step": len(turns), "agent_id": agent, "action": {"action": action}, "tool_result": result})
    if peer_version is not None:
        turn("builder", "inspect_artifact", {"ok": True, "version": peer_version})
    if own_version is not None:
        turn("coordinator", "inspect_artifact", {"ok": True, "version": own_version})
    if repaired:
        turn("builder", "repair_artifact", {"ok": True, "version": published_version})
    turn("coordinator", "publish_artifact", {"ok": True})
    inspected = int(own_version == published_version or peer_version == published_version)
    return {"run_id": identity, "arm": arm, "turns": turns,
            "final_state": {"published": {"version": published_version}},
            "outcomes": {"success": success, "inspected_publication": inspected,
                         "incorrect_publication": 1 - success, "steps_used": len(turns)}}


def pilot_fixture():
    runs = []
    for i in range(3):
        runs.append(artifact_run(f"b{i}", "baseline", 1, published_version=2, own_version=1, repaired=True))
        runs.append(artifact_run(f"p{i}", "placebo", int(i == 0), peer_version=1, own_version=1 if i == 0 else None))
        runs.append(artifact_run(f"a{i}", "evidence_thought", 1, own_version=1))
    return {"experiment_id": "controlled-fixture", "status": "complete", "runs": runs,
            "protocol": {"estimand": {"unit": "whole_swarm_run", "primary_outcome": "success",
                                      "primary_contrast": ["evidence_thought", "placebo"]}},
            "backend": {"mode": "provided_agent_runner", "metadata": {"model": "test-model", "harness": "fake"}},
            "analysis": {"effects": {"evidence_thought_vs_placebo": {"success": {
                "mean_treatment": 1, "mean_control": 1 / 3, "difference": 2 / 3,
                "n_treatment": 3, "n_control": 3, "unit": "whole_swarm_run",
                "ci95": [-0.05856874558467462, 0.9385080552796039]}}}}}


class ClaimAuditTests(unittest.TestCase):
    def setUp(self):
        self.report = pilot_fixture()
        self.ledger = build_fact_ledger(self.report)

    def audit(self, fact_id, expected, **kwargs):
        claim = make_claim(self.ledger, fact_id, expected, **kwargs)
        return audit_claims(self.ledger, [claim])["claims"][0]

    def test_known_original_numeric_error_is_rejected(self):
        fact = "arm_metric/evidence_thought/outcome/success/sum"
        reviewed = self.audit(fact, 2, statement="Active had two correct publications out of three")
        self.assertEqual(reviewed["status"], "mismatch")
        self.assertEqual(reviewed["actual"], 3)

    def test_known_digit_free_wrong_inspection_direction_is_rejected(self):
        fact = "comparison/evidence_thought/placebo/outcome/inspected_publication/mean_direction"
        reviewed = self.audit(fact, "higher", statement="The reminder group showed more inspection before publication")
        self.assertEqual(reviewed["status"], "mismatch")
        self.assertEqual(reviewed["actual"], "equal")

    def test_actor_version_distinctions_have_separate_fact_ids(self):
        any_agent = "arm_metric/baseline/trajectory/any_agent_inspected_published_version/sum"
        any_publisher = "arm_metric/baseline/trajectory/publisher_inspected_any/sum"
        published_publisher = "arm_metric/baseline/trajectory/publisher_inspected_published_version/sum"
        self.assertEqual(self.ledger["facts"][any_agent]["value"], 0)
        self.assertEqual(self.ledger["facts"][any_publisher]["value"], 3)
        self.assertEqual(self.ledger["facts"][published_publisher]["value"], 0)
        self.assertIn("not positive verification", self.ledger["facts"]["arm_metric/placebo/outcome/inspected_publication/mean"]["definition"])

    def test_correct_explicit_difference_and_count_pass_but_prose_does_not(self):
        claim = make_claim(self.ledger, "arm_metric/evidence_thought/outcome/success/sum", 3,
                           statement="This somehow proves every agent is honest forever")
        audit = audit_claims(self.ledger, [claim])
        self.assertEqual(audit["claims"][0]["status"], "supported")
        self.assertEqual(audit["claims"][0]["prose_status"], "unverified")
        self.assertTrue(audit["unverified_prose_present"])
        self.assertNotIn("honest", audit["claims"][0]["approved_fact_text"])
        reviewed = self.audit("comparison/evidence_thought/placebo/outcome/success/mean_difference_percentage_points", 100 * 2 / 3)
        self.assertEqual(reviewed["status"], "supported")

    def test_trial_unit_is_whole_team_and_agents_are_not_extra_trials(self):
        self.assertEqual(self.audit("trial_count/completed", 27)["status"], "mismatch")
        self.assertEqual(self.audit("trial_count/completed", 9)["status"], "supported")
        self.assertEqual(self.audit("comparison_identity/unit", "individual_agent")["status"], "mismatch")

    def test_complete_label_cannot_hide_missing_assignments(self):
        report = copy.deepcopy(self.report)
        report["assignments"] = [{"run_id": r["run_id"], "arm": r["arm"]} for r in report["runs"]] + [
            {"run_id": "missing-assigned-unit", "arm": "placebo"}]
        ledger = build_fact_ledger(report)
        self.assertFalse(ledger["facts"]["completion/all_assigned_units_present"]["value"])
        self.assertEqual(ledger["issues"][0]["type"], "complete_status_with_missing_or_mismatched_assignments")

    def test_agent_fact_packet_is_explicit_bounded_and_schema_pins_ids(self):
        ids = ["trial_count/completed", "comparison_identity/primary/control"]
        packet = select_fact_packet(self.ledger, ids, max_facts=2)
        schema = claims_schema_for_packet(packet)
        properties = schema["properties"]["claims"]["items"]["properties"]
        self.assertEqual(properties["fact_id"]["enum"], ids + [None])
        self.assertEqual(properties["source_fingerprint"]["enum"], [self.ledger["source_fingerprint"]])
        packet["facts"][ids[0]]["value"] = 1000
        self.assertEqual(self.ledger["facts"][ids[0]]["value"], 9)
        for bad in (ids + ["backend/mode"], ["missing-fact"], [ids[0], ids[0]]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                select_fact_packet(self.ledger, bad, max_facts=2)

    def test_default_shortlist_protects_counts_control_scope_and_actor_boundaries(self):
        ids = default_fact_ids(self.ledger)
        self.assertLessEqual(len(ids), 24)
        self.assertEqual(len(ids), len(set(ids)))
        for identity in ("trial_count/group/evidence_thought", "trial_count/group/placebo", "trial_count/group/baseline",
                         "arm_metric/evidence_thought/outcome/success/sum", "arm_metric/placebo/outcome/success/sum", "arm_metric/baseline/outcome/success/sum",
                         "comparison_identity/primary/control", "comparison_identity/unit", "backend/mode",
                         "interval/evidence_thought_vs_placebo/success/excludes_zero",
                         "comparison/evidence_thought/placebo/outcome/inspected_publication/mean_direction",
                         "comparison/evidence_thought/placebo/trajectory/publisher_inspected_published_version/mean_direction"):
            self.assertIn(identity, ids)
        packet = select_fact_packet(self.ledger, ids, max_facts=24)
        self.assertEqual(packet["facts"]["comparison_identity/primary/control"]["value"], "placebo")

    def test_default_shortlist_includes_performed_replay_within_cap(self):
        ledger = build_fact_ledger(self.report, replay_check=lambda report: {"passed": True, "runs_checked": len(report["runs"]), "model_calls": 0})
        ids = default_fact_ids(ledger)
        self.assertLessEqual(len(ids), 24)
        self.assertIn("replay/recorded_actions/pass", ids)

    def test_primary_contrast_cannot_silently_become_baseline(self):
        reviewed = self.audit("comparison_identity/primary/control", "baseline")
        self.assertEqual(reviewed["status"], "mismatch")
        self.assertEqual(reviewed["actual"], "placebo")

    def test_interval_including_zero_does_not_support_exclusion(self):
        self.assertEqual(self.audit("interval/evidence_thought_vs_placebo/success/excludes_zero", True)["status"], "mismatch")
        self.assertEqual(self.audit("interval/evidence_thought_vs_placebo/success/excludes_zero", False)["status"], "supported")

    def test_interval_touching_zero_does_not_exclude_it(self):
        report = copy.deepcopy(self.report)
        report["analysis"]["effects"]["evidence_thought_vs_placebo"]["success"]["ci95"] = [0, 1]
        ledger = build_fact_ledger(report)
        self.assertFalse(ledger["facts"]["interval/evidence_thought_vs_placebo/success/excludes_zero"]["value"])

    def test_inconsistent_saved_analysis_is_not_laundered_into_uncertainty_fact(self):
        report = copy.deepcopy(self.report)
        report["analysis"]["effects"]["evidence_thought_vs_placebo"]["success"]["mean_treatment"] = 2 / 3
        ledger = build_fact_ledger(report)
        self.assertNotIn("interval/evidence_thought_vs_placebo/success/excludes_zero", ledger["facts"])
        self.assertEqual(ledger["issues"][0]["type"], "saved_effect_disagrees_with_run_rows")

    def test_generalized_scope_cannot_inherit_a_sample_fact(self):
        claim = make_claim(self.ledger, "arm_metric/evidence_thought/outcome/success/sum", 3)
        claim["scope"] = "generalized"
        self.assertEqual(audit_claims(self.ledger, [claim])["claims"][0]["status"], "mismatch")

    def test_report_modification_invalidates_old_claim_binding(self):
        claim = make_claim(self.ledger, "trial_count/completed", 9)
        changed = copy.deepcopy(self.report)
        changed["runs"][0]["outcomes"]["success"] = 0
        audit = audit_claims(build_fact_ledger(changed), [claim])
        self.assertEqual(audit["claims"][0]["status"], "mismatch")
        self.assertIn("fingerprint", audit["claims"][0]["reason"])

    def test_proposed_mechanism_and_free_prose_remain_unverified(self):
        for kind, scope in (("proposed_mechanism", "proposed_mechanism"), ("free_prose", "historical")):
            claim = {"id": kind, "kind": kind, "fact_id": None, "expected": None, "scope": scope,
                     "statement": "Grounding norms caused this historical event", "source_fingerprint": self.ledger["source_fingerprint"]}
            row = audit_claims(self.ledger, [claim])["claims"][0]
            self.assertEqual(row["status"], "unverified")
            self.assertIsNone(row["approved_fact_text"])

    def test_boolean_integer_confusion_does_not_pass(self):
        self.assertEqual(self.audit("interval/evidence_thought_vs_placebo/success/excludes_zero", 0)["status"], "mismatch")

    def test_missing_trace_version_is_unavailable_not_false(self):
        report = copy.deepcopy(self.report)
        report["runs"][0]["turns"][0]["tool_result"].pop("version")
        ledger = build_fact_ledger(report)
        self.assertNotIn("arm_metric/baseline/trajectory/publisher_inspected_published_version/sum", ledger["facts"])
        self.assertIn("arm_metric/baseline/outcome/success/sum", ledger["facts"])

    def test_conflicting_inspection_oracle_is_flagged_not_silently_replaced(self):
        report = copy.deepcopy(self.report)
        report["runs"][0]["outcomes"]["inspected_publication"] = 1
        ledger = build_fact_ledger(report)
        claim = make_claim(ledger, "arm_metric/baseline/outcome/inspected_publication/sum", 1)
        audit = audit_claims(ledger, [claim])
        self.assertEqual(audit["claims"][0]["status"], "unavailable")
        self.assertFalse(audit["all_executable_claims_supported"])
        self.assertTrue(ledger["issues"])

    def test_duplicate_rows_are_not_extra_independent_trials(self):
        report = copy.deepcopy(self.report)
        report["runs"].append(copy.deepcopy(report["runs"][0]))
        with self.assertRaisesRegex(ValueError, "unique"):
            build_fact_ledger(report)

    def test_missing_metric_is_not_selectively_averaged(self):
        report = copy.deepcopy(self.report)
        report["runs"][0]["outcomes"].pop("success")
        ledger = build_fact_ledger(report)
        self.assertNotIn("arm_metric/baseline/outcome/success/mean", ledger["facts"])

    def test_incomplete_study_has_no_effect_or_interval_facts(self):
        report = copy.deepcopy(self.report)
        report["status"] = "incomplete_infrastructure_failure"
        ledger = build_fact_ledger(report)
        self.assertFalse(any(f["kind"] in ("comparison_direction", "interval_zero", "comparison_difference") for f in ledger["facts"].values()))
        self.assertEqual(ledger["facts"]["completion/status"]["value"], report["status"])

    def test_replay_is_unavailable_without_actual_trusted_offline_check(self):
        self.assertNotIn("replay/recorded_actions/pass", self.ledger["facts"])
        with self.assertRaisesRegex(ValueError, "callables"):
            build_fact_ledger(self.report, replay_check={"passed": True})

    def test_offline_replay_callable_is_bound_to_exact_report(self):
        received = []
        def check(report):
            received.append(report)
            return {"passed": True, "runs_checked": len(report["runs"]), "model_calls": 0}
        ledger = build_fact_ledger(self.report, replay_check=check)
        self.assertEqual(received[0], self.report)
        self.assertEqual(ledger["facts"]["replay/recorded_actions/pass"]["value"], True)
        self.assertIsNot(received[0], self.report)

    def test_replay_wrong_unit_count_does_not_create_pass_fact(self):
        ledger = build_fact_ledger(self.report, replay_check=lambda _: {"passed": True, "runs_checked": 1, "model_calls": 0})
        self.assertNotIn("replay/recorded_actions/pass", ledger["facts"])
        self.assertTrue(ledger["issues"])

    def test_backend_label_is_recorded_metadata_not_provider_attestation(self):
        fact = self.ledger["facts"]["backend/mode"]
        self.assertIn("not_independent_provider_attestation", fact["basis"])
        self.assertEqual(self.audit("backend/mode", "scripted_offline_smoke_test")["status"], "mismatch")

    def test_schema_is_finite_and_forbids_extra_keys_nan_and_duplicate_claims(self):
        claim = make_claim(self.ledger, "trial_count/completed", 9)
        self.assertTrue(validate_claim(claim))
        for invalid in ({**claim, "unexpected": True}, {**claim, "expected": float("nan")}, {**claim, "kind": "hidden_thought_verified"}):
            with self.assertRaises(ValueError):
                validate_claim(invalid)
        audit = audit_claims(self.ledger, [claim, claim])
        self.assertEqual(audit["claims"][1]["status"], "invalid")
        self.assertFalse(CLAIM_SCHEMA["additionalProperties"])
        self.assertFalse(CLAIMS_SCHEMA["additionalProperties"])
        json.dumps(CLAIMS_SCHEMA, allow_nan=False)


class NetworkClaimAuditTests(unittest.TestCase):
    def test_factorial_means_use_networks_and_equal_cell_averaging(self):
        runs = []
        rates = {("ring", "placebo"): [1, 1], ("ring", "source_thought"): [1, 1],
                 ("complete", "placebo"): [1, 0.75], ("complete", "source_thought"): [0.5, 0.75]}
        for (topology, context), values in rates.items():
            for i, rate in enumerate(values):
                runs.append({"run_id": f"{topology}-{context}-{i}", "topology": topology,
                             "context": context, "outcomes": {"mean_accuracy": rate}})
        effect = {"factor": "context", "treatment": "source_thought", "control": "placebo", "stratify_by": "topology", "outcome": "mean_accuracy", "mean_treatment": 0.8125, "mean_control": 0.9375, "difference": -0.125,
                  "n_treatment_networks": 4, "n_control_networks": 4, "unit": "whole_network_run", "ci95": [-1, 0.835]}
        report = {"status": "complete", "study_kind": "provenance_diffusion_factorial", "runs": runs,
                  "protocol": {"estimand": {"primary_outcome": "mean_accuracy", "primary_contrasts": [{k: effect[k] for k in ("factor", "treatment", "control", "stratify_by")}] }},
                  "analysis": {"factor_effects": [effect]}}
        ledger = build_fact_ledger(report)
        self.assertEqual(ledger["facts"]["trial_count/completed"]["value"], 8)
        self.assertEqual(ledger["facts"]["comparison_identity/unit"]["value"], "whole_network_run")
        self.assertEqual(ledger["facts"]["factor_direction/context/mean_accuracy"]["value"], "lower")
        self.assertFalse(ledger["facts"]["interval/factor_context/mean_accuracy/excludes_zero"]["value"])
        self.assertFalse(ledger["issues"])
        ids = default_fact_ids(ledger)
        self.assertLessEqual(len(ids), 24)
        self.assertIn("factor_direction/context/mean_accuracy", ids)
        self.assertIn("comparison_identity/context/stratify_by", ids)


class ComplementaryClaimAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from swarm_lab.complementary_experiments import create_complementary_protocol, run_complementary_experiment
        cls.report = run_complementary_experiment(create_complementary_protocol(seed=4411), resamples=100)

    def test_executed_complementary_outcome_semantics_and_network_unit(self):
        ledger = build_fact_ledger(self.report)
        self.assertFalse(ledger["issues"])
        self.assertEqual(ledger["facts"]["comparison_identity/unit"]["value"], "whole_network_run")
        self.assertEqual(ledger["facts"]["trial_count/completed"]["value"], 8)
        fact = ledger["facts"]["arm_metric/ring|placebo/outcome/mean_accuracy/mean"]
        self.assertIn("modular-total", fact["definition"])
        self.assertIn("missing submissions score zero", fact["definition"])
        self.assertNotIn("verdict", fact["definition"])
        completion = ledger["facts"]["arm_metric/ring|placebo/outcome/completion_rate/mean"]
        self.assertIn("valid modular-total submission", completion["definition"])
        definition = ledger["facts"]["comparison_identity/operational_definition"]["value"]
        self.assertEqual(definition, self.report["protocol"]["estimand"]["operational_definition"])

    def test_coverage_and_multicast_delivery_facts_do_not_claim_knowledge(self):
        ledger = build_fact_ledger(self.report)
        prefix = "arm_metric/complete|placebo/outcome/"
        coverage = ledger["facts"][prefix + "mean_unique_originals_at_submission/mean"]
        self.assertIn("free-text information is not measured", coverage["definition"])
        self.assertEqual(coverage["value"], 4)
        dispatches = ledger["facts"][prefix + "messages_sent/mean"]
        deliveries = ledger["facts"][prefix + "message_deliveries/mean"]
        self.assertGreater(deliveries["value"], dispatches["value"])
        self.assertIn("one action", dispatches["definition"])
        wrong = make_claim(ledger, deliveries["id"], dispatches["value"], statement="A dispatch and a delivery are interchangeable")
        self.assertEqual(audit_claims(ledger, [wrong])["claims"][0]["status"], "mismatch")

    def test_default_packet_preserves_primary_boundaries_and_replay(self):
        from swarm_lab.audit import replay_report
        ledger = build_fact_ledger(self.report, replay_check=replay_report)
        self.assertFalse(ledger["issues"])
        ids = default_fact_ids(ledger)
        self.assertLessEqual(len(ids), 24)
        for identity in ("comparison_identity/unit", "comparison_identity/primary_outcome",
                         "factor_direction/context/mean_accuracy", "factor_direction/topology/mean_accuracy",
                         "interval/factor_context/mean_accuracy/excludes_zero", "replay/recorded_actions/pass"):
            self.assertIn(identity, ids)
        claims = [make_claim(ledger, identity, ledger["facts"][identity]["value"]) for identity in ids]
        self.assertTrue(audit_claims(ledger, claims)["all_executable_claims_supported"])

    def test_missing_submission_is_not_dropped_from_accuracy_or_coverage(self):
        report = copy.deepcopy(self.report)
        report.pop("analysis")
        first = next(r for r in report["runs"] if r["topology"] == "ring" and r["context"] == "placebo")
        # Recorded outcome fixture: one of four subjects lacks a submission.
        first["outcomes"]["mean_accuracy"] = 0.75
        first["outcomes"]["completion_rate"] = 0.75
        first["outcomes"]["mean_unique_originals_at_submission"] = 3
        ledger = build_fact_ledger(report)
        self.assertEqual(ledger["facts"]["arm_metric/ring|placebo/outcome/mean_accuracy/mean"]["value"], 0.875)
        self.assertEqual(ledger["facts"]["arm_metric/ring|placebo/outcome/mean_unique_originals_at_submission/mean"]["value"], 3.5)
        self.assertEqual(ledger["facts"]["trial_count/group/ring|placebo"]["value"], 2)
        self.assertIn("not_performed", ledger["prose_verification"])


if __name__ == "__main__":
    unittest.main()
