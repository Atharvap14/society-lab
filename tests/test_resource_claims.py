"""Resource quantities are reconstructed, pinned, finite and interpretation-bounded."""
import copy
import unittest
from unittest.mock import patch

from swarm_lab.claim_audit import audit_claims, claims_schema_for_packet, make_claim, select_fact_packet
from swarm_lab.resource_claims import (PRIMARY_ANALYSIS, PRIMARY_INTERVAL, PRIMARY_PAIR,
    build_resource_fact_ledger, default_resource_fact_ids)
from swarm_lab.resource_environment import fingerprint as execution_fingerprint, offline_resource_policy
from swarm_lab.resource_experiments import (TASK_REMINDER, ResourceExecutionError,
    create_resource_protocol, run_resource_experiment)
from swarm_lab.store import fingerprint


FAKE_BACKEND = {"harness": "test_callback", "model": "scripted_fixture",
                "generation": {"policy": "declared_test"}}


def seal_report(report):
    report.pop("report_hash", None)
    report["report_hash"] = execution_fingerprint(report)
    return report


def pinned_result(report, *, identity="resource-result-fixture", version=1):
    payload = copy.deepcopy(report)
    if "report_hash" in payload:
        payload["canonical_execution_report_hash"] = payload.pop("report_hash")
    payload.update(protocol_id="resource-protocol-fixture", artifact_directory="fixture-only",
                   registered_hash=fingerprint(report["protocol"]))
    obj = {"id": identity, "version": version, "hash": fingerprint(payload),
           "kind": "resource_experiment", "payload": payload}
    return {key: obj[key] for key in ("id", "version", "hash")}, obj


class ResourceClaimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_resource_experiment(create_resource_protocol(
            max_rounds=3, release_rounds=(3,)), resamples=100)

    def ledger(self, report=None, **kwargs):
        return build_resource_fact_ledger(copy.deepcopy(report or self.report), **kwargs)

    def test_valid_report_recomputes_every_unit_without_mutation_calls_or_database(self):
        original = copy.deepcopy(self.report)
        with patch("swarm_lab.store.Store.__init__", side_effect=AssertionError("No DB access")):
            ledger = build_resource_fact_ledger(self.report)
        self.assertEqual(self.report, original)
        self.assertEqual(ledger["model_calls"], 0)
        self.assertTrue(ledger["quantitative_facts_available"])
        self.assertFalse(ledger["issues"])
        self.assertTrue(all(check["passed"] for check in ledger["verification_checks"]))
        checks = [check for check in ledger["verification_checks"]
                  if check["name"].startswith("exact_typed_state_and_oracle_replay/")]
        self.assertEqual(len(checks), 4)
        self.assertEqual(ledger["source_fingerprint"], fingerprint(self.report))
        self.assertEqual(ledger["facts"][PRIMARY_ANALYSIS + "/p_two_sided"]["basis"], "fresh_numerical_recomputation")

    def test_exact_registered_object_pin_matches_canonical_report(self):
        ref, obj = pinned_result(self.report, version=4)
        ledger = self.ledger(report_id=ref["id"], source_ref=ref, source_object=obj)
        self.assertEqual(ledger["source_ref"], ref)
        self.assertEqual(ledger["facts"]["source_pin/version"]["value"], 4)
        self.assertTrue(ledger["facts"]["completion/source_pin_checked"]["value"])
        self.assertTrue(ledger["quantitative_facts_available"])
        self.assertFalse(self.ledger()["facts"]["completion/source_pin_checked"]["value"])

    def test_source_pin_version_hash_kind_and_canonical_mismatches_fail(self):
        ref, obj = pinned_result(self.report)
        for category in ("missing_object", "missing_ref", "version", "kind", "bad_hash", "canonical", "rows", "registered_protocol", "identity", "boolean_version"):
            bad_ref, bad_obj = copy.deepcopy(ref), copy.deepcopy(obj)
            kwargs = {"source_ref": bad_ref, "source_object": bad_obj}
            if category == "missing_object": kwargs["source_object"] = None
            elif category == "missing_ref": kwargs["source_ref"] = None
            elif category == "version": bad_obj["version"] = 2
            elif category == "kind": bad_obj["kind"] = "network_experiment"
            elif category == "bad_hash": bad_obj["payload"]["host_metadata"] = "Changed without new hash"
            elif category == "canonical": bad_obj["payload"]["canonical_execution_report_hash"] = "0" * 64
            elif category == "rows": bad_obj["payload"]["runs"] = []
            elif category == "registered_protocol": bad_obj["payload"]["registered_hash"] = "0" * 64
            elif category == "identity": kwargs["report_id"] = "different-result"
            elif category == "boolean_version": bad_ref["version"] = True; bad_obj["version"] = True
            if category in ("canonical", "rows", "registered_protocol"):
                bad_obj["hash"] = bad_ref["hash"] = fingerprint(bad_obj["payload"])
            with self.subTest(category=category), self.assertRaises(ValueError):
                self.ledger(**kwargs)

    def test_eight_tasks_per_unit_are_outcomes_not_pseudoreplicated_trials(self):
        ledger = self.ledger()
        facts = ledger["facts"]
        self.assertEqual(facts["trial_count/completed"]["value"], 4)
        for context in ("neutral", "task_reminder"):
            self.assertEqual(facts["trial_count/group/" + context]["value"], 2)
            self.assertEqual(facts[f"arm_metric/{context}/task_inventory/tasks_assigned"]["value"], 16)
            self.assertEqual(facts[f"arm_metric/{context}/task_inventory/executed_tasks_completed"]["value"], 8)
            summed = facts[f"arm_metric/{context}/outcome/task_completion_fraction/sum"]
            self.assertEqual(summed["value"], 1)
            self.assertIn("not a task count", summed["definition"])
        claims = [make_claim(ledger, "trial_count/completed", 32),
                  make_claim(ledger, "comparison_identity/unit", "individual_agent")]
        self.assertEqual([row["status"] for row in audit_claims(ledger, claims)["claims"]], ["mismatch", "mismatch"])

    def test_numeric_difference_is_percentage_points_not_relative_percent_change(self):
        protocol = create_resource_protocol(max_rounds=3, release_rounds=(3,), subject_backend=FAKE_BACKEND)
        def policy(request):
            if request["role"] == "agent-0" and TASK_REMINDER not in request["context"]:
                return {"action": "wait"}
            return offline_resource_policy(request)
        report = run_resource_experiment(protocol, policy, resamples=100)
        ledger = self.ledger(report)
        self.assertEqual(ledger["facts"][PRIMARY_PAIR + "/mean_difference"]["value"], .125)
        fact = ledger["facts"][PRIMARY_PAIR + "/mean_difference_percentage_points"]
        self.assertEqual(fact["value"], 12.5)
        self.assertEqual(fact["value_unit"], "percentage_points")
        self.assertIn("not a relative percentage change", fact["definition"])
        self.assertAlmostEqual(ledger["facts"][PRIMARY_ANALYSIS + "/p_two_sided"]["value"], 1/3)

    def test_small_sample_resolution_is_design_bound_and_null_is_not_equivalence(self):
        ledger = self.ledger()
        facts = ledger["facts"]
        self.assertEqual(facts["analysis/primary/test_resolution/exact_minimum_fraction"]["value"], "2/6")
        self.assertFalse(facts["analysis/primary/test_resolution/can_attain_p_below_0.05"]["value"])
        self.assertAlmostEqual(facts["analysis/primary/test_resolution/minimum_two_sided_p"]["value"], 1/3)
        self.assertEqual(facts[PRIMARY_PAIR + "/mean_direction"]["value"], "equal")
        self.assertIn("does not establish equivalence", facts[PRIMARY_PAIR + "/mean_direction"]["definition"])
        self.assertEqual(facts[PRIMARY_INTERVAL + "/lower"]["value"], -1)
        self.assertEqual(facts[PRIMARY_INTERVAL + "/upper"]["value"], 1)
        self.assertFalse(facts[PRIMARY_INTERVAL + "/excludes_zero"]["value"])
        self.assertTrue(facts[PRIMARY_ANALYSIS + "/bootstrap_degenerate"]["value"])

    def test_floor_and_ceiling_bootstrap_collapse_preserves_conservative_interval(self):
        fixtures = (
            run_resource_experiment(create_resource_protocol(max_rounds=2, release_rounds=(2,),
                subject_backend=FAKE_BACKEND), lambda _: {"action": "wait"}, resamples=100),
            run_resource_experiment(create_resource_protocol(max_rounds=12, release_rounds=(0,)), resamples=100))
        for label, report in zip(("floor", "ceiling"), fixtures):
            ledger = self.ledger(report)
            with self.subTest(label=label):
                self.assertTrue(ledger["quantitative_facts_available"])
                for context in ("neutral", "task_reminder"):
                    self.assertTrue(ledger["facts"][f"arm_metric/{context}/outcome/task_completion_fraction/all_at_{label}"]["value"])
                self.assertTrue(ledger["facts"][PRIMARY_ANALYSIS + "/bootstrap_degenerate"]["value"])
                self.assertEqual(ledger["facts"][PRIMARY_INTERVAL + "/lower"]["value"], -1)
                self.assertEqual(ledger["facts"][PRIMARY_INTERVAL + "/upper"]["value"], 1)

    def test_process_metrics_never_create_belief_mediation_or_historical_facts(self):
        ledger = self.ledger()
        wait = ledger["facts"]["arm_metric/neutral/outcome/waits_while_independent_pending/mean"]
        self.assertIn("not a global-wait belief", wait["definition"])
        denial = ledger["facts"]["arm_metric/neutral/outcome/resource_access_denials/mean"]
        self.assertIn("not exclusively blocked access", denial["definition"])
        claim = make_claim(ledger, wait["id"], wait["value"])
        claim["scope"] = "historical"
        self.assertEqual(audit_claims(ledger, [claim])["claims"][0]["status"], "mismatch")
        claim["scope"] = "proposed_mechanism"
        self.assertEqual(audit_claims(ledger, [claim])["claims"][0]["status"], "mismatch")
        self.assertFalse(any("belief" in identity or "mediation" in identity for identity in ledger["facts"]))

    def test_known_good_numbers_do_not_approve_attached_bad_prose(self):
        ledger = self.ledger()
        claim = make_claim(ledger, PRIMARY_PAIR + "/mean_direction", "equal",
                           statement="The agents are universally immune to reminders.")
        reviewed = audit_claims(ledger, [claim])
        self.assertEqual(reviewed["claims"][0]["status"], "supported")
        self.assertEqual(reviewed["claims"][0]["prose_status"], "unverified")
        self.assertFalse(reviewed["attached_prose_approved"])
        self.assertTrue(reviewed["review_required"])
        self.assertNotIn("immune", reviewed["claims"][0]["approved_fact_text"])

    def test_incomplete_report_retains_failure_metadata_without_effect_estimate(self):
        p = create_resource_protocol(max_rounds=2, subject_backend=FAKE_BACKEND)
        def fail(_): raise TimeoutError("Fixture only")
        with self.assertRaises(ResourceExecutionError) as caught:
            run_resource_experiment(p, fail, resamples=100)
        partial = caught.exception.partial_report
        ref, obj = pinned_result(partial)
        ledger = self.ledger(partial, source_ref=ref, source_object=obj)
        self.assertFalse(ledger["quantitative_facts_available"])
        self.assertEqual(ledger["facts"]["trial_count/completed"]["value"], 0)
        self.assertEqual(ledger["facts"]["completion/status"]["value"], "incomplete_infrastructure_failure")
        self.assertNotIn(PRIMARY_PAIR + "/mean_difference", ledger["facts"])
        self.assertNotIn(PRIMARY_ANALYSIS + "/p_two_sided", ledger["facts"])
        self.assertFalse(audit_claims(ledger, [make_claim(ledger, "completion/status", "incomplete_infrastructure_failure")])["all_executable_claims_supported"])

    def test_resealed_analysis_tampering_fails_numeric_recomputation(self):
        for category in ("difference", "p", "ci", "process_mean", "bootstrap", "bool_analysis"):
            bad = copy.deepcopy(self.report)
            effect = bad["analysis"]["primary_effect"]
            if category == "difference": effect["difference"] = .9
            elif category == "p": effect["p_two_sided"] = .001
            elif category == "ci": effect["ci95"] = [.8, .9]
            elif category == "process_mean": bad["analysis"]["cells"]["neutral"]["waits"] = 300
            elif category == "bootstrap": effect["bootstrap_ci95"] = [.5, .5]
            else: effect["p_two_sided"] = True
            ledger = self.ledger(seal_report(bad))
            with self.subTest(category=category):
                self.assertFalse(ledger["quantitative_facts_available"])
                self.assertTrue(ledger["issues"])
                self.assertNotIn(PRIMARY_ANALYSIS + "/p_two_sided", ledger["facts"])

    def test_resealed_trace_outcome_backend_and_receipt_changes_withhold_outcome_facts(self):
        for category in ("oracle", "typed_state", "typed_step", "receipt", "contract", "backend", "mode", "missing_unit", "order", "protocol_identity", "bool_outcome"):
            bad = copy.deepcopy(self.report)
            if category == "oracle": bad["runs"][0]["outcomes"]["waits"] += 1
            elif category == "typed_state": bad["runs"][0]["initial_state"]["step_count"] = False
            elif category == "typed_step": bad["runs"][0]["turns"][0]["step"] = False
            elif category == "receipt": bad["runs"][0]["actual_context_insertion_recipients"] = ["agent-1"]
            elif category == "contract": bad["runs"][0]["environment_contract"]["passed"] = False
            elif category == "backend": bad["backend"]["metadata"]["model"] = "different-model"
            elif category == "mode": bad["backend"]["mode"] = "provided_agent_runner"
            elif category == "missing_unit": bad["runs"].pop()
            elif category == "order": bad["runs"].reverse()
            elif category == "protocol_identity": bad["protocol_hash"] = "0" * 64
            elif category == "bool_outcome": bad["runs"][0]["outcomes"]["resource_access_grants"] = False
            ledger = self.ledger(seal_report(bad))
            with self.subTest(category=category):
                self.assertFalse(ledger["quantitative_facts_available"])
                self.assertNotIn("arm_metric/neutral/outcome/task_completion_fraction/mean", ledger["facts"])

    def test_nonfinite_duplicate_or_wrong_study_source_data_is_rejected(self):
        for category in ("nan", "inf", "duplicate", "study"):
            bad = copy.deepcopy(self.report)
            if category == "nan": bad["analysis"]["primary_effect"]["p_two_sided"] = float("nan")
            elif category == "inf": bad["runs"][0]["outcomes"]["task_completion_fraction"] = float("inf")
            elif category == "duplicate": bad["runs"][1]["run_id"] = bad["runs"][0]["run_id"]
            else: bad["study_kind"] = "provenance_diffusion_factorial"
            with self.subTest(category=category), self.assertRaises(ValueError): self.ledger(bad)

    def test_changed_sources_and_unsealed_report_have_no_quantitative_facts(self):
        bad = copy.deepcopy(self.report); bad["report_hash"] = "0" * 64
        self.assertFalse(self.ledger(bad)["quantitative_facts_available"])
        with patch("swarm_lab.resource_experiments.resource_code_hashes", return_value={}):
            ledger = self.ledger()
        self.assertFalse(ledger["quantitative_facts_available"])
        self.assertTrue(any(issue["type"] == "frozen_protocol_or_sources_invalid" for issue in ledger["issues"]))

    def test_explicit_packet_is_bounded_and_schema_pins_exact_source_and_fact_ids(self):
        ledger = self.ledger()
        identities = default_resource_fact_ids(ledger)
        self.assertEqual(len(identities), 24)
        self.assertEqual(len(set(identities)), 24)
        packet = select_fact_packet(ledger, identities, max_facts=24)
        props = claims_schema_for_packet(packet)["properties"]["claims"]["items"]["properties"]
        self.assertEqual(props["fact_id"]["enum"], identities + [None])
        self.assertEqual(props["source_fingerprint"]["enum"], [fingerprint(self.report)])
        self.assertEqual(len(default_resource_fact_ids(ledger, max_facts=3)), 3)
        for cap in (0, True, 101):
            with self.subTest(cap=cap), self.assertRaises(ValueError): default_resource_fact_ids(ledger, max_facts=cap)
        claim = make_claim(ledger, PRIMARY_ANALYSIS + "/p_two_sided", 1)
        claim["source_fingerprint"] = "0" * 64
        self.assertEqual(audit_claims(ledger, [claim])["claims"][0]["status"], "mismatch")


if __name__ == "__main__": unittest.main()
