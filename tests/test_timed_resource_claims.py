"""Finite facts cannot widen a timed pilot into prose or historical causality."""
import copy
import unittest
from unittest.mock import patch

from swarm_lab.claim_audit import make_claim, select_fact_packet, claims_schema_for_packet
from swarm_lab.timed_resource_claims import (build_timed_resource_fact_ledger, audit_timed_resource_claims,
    default_timed_resource_fact_ids, PRIMARY_PAIR, PRIMARY_INTERVAL, PRIMARY_ANALYSIS)
from swarm_lab.timed_resource_experiments import (create_timed_resource_protocol, run_timed_resource_experiment,
    replay_timed_resource_report, TimedResourceExecutionError, timed_resource_infrastructure_policy, ACTIVE_NOTE, _seal)
from swarm_lab.resource_environment import offline_resource_policy
from swarm_lab.store import fingerprint

BACKEND = {"harness":"test_callback","model":"cpu_fixture","generation":{"policy":"declared_test"}}


def trusted_gate(report):
    verdict = replay_timed_resource_report(report)
    return {**verdict,"report_hash":report["report_hash"],"protocol_hash":report["protocol_hash"]}


def source_object(report, *, version=1):
    payload = copy.deepcopy(report)
    payload["canonical_execution_report_hash"] = payload.pop("report_hash")
    payload.update(protocol_id="timed-protocol-fixture",registered_hash=fingerprint(report["protocol"]),
        artifact_directory="fixture-only",model=report["protocol"]["subject_backend"]["model"],agent_mode="offline_simulation")
    obj = {"id":"timed-result-fixture","version":version,"kind":"timed_resource_experiment","payload":payload,"hash":fingerprint(payload)}
    return {k:obj[k] for k in ("id","version","hash")},obj


class TimedResourceClaimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_timed_resource_experiment(create_timed_resource_protocol(resamples=100,max_rounds=3,release_rounds=(3,)))

    def ledger(self, report=None, **kwargs):
        return build_timed_resource_fact_ledger(self.report if report is None else report,replay_check=kwargs.pop("replay_check",trusted_gate),**kwargs)

    def test_valid_complete_ledger_is_pure_and_paired_units_are_explicit(self):
        before = copy.deepcopy(self.report)
        with patch("swarm_lab.store.Store.__init__",side_effect=AssertionError("No DB access")):
            ledger = self.ledger()
        self.assertEqual(self.report,before); self.assertEqual(ledger["model_calls"],0)
        self.assertTrue(ledger["quantitative_facts_available"]); self.assertFalse(ledger["issues"])
        self.assertTrue(all(c["passed"] is True for c in ledger["verification_checks"]))
        facts = ledger["facts"]
        self.assertEqual(facts["trial_count/completed"]["value"],4)
        self.assertEqual(facts["trial_count/seed_blocks/completed"]["value"],2)
        self.assertEqual(facts["comparison_identity/independent_uncertainty_units"]["value"],"seed_blocks")
        for context in ("active","neutral"):
            self.assertEqual(facts["trial_count/group/"+context]["value"],2)
            self.assertEqual(facts[f"arm_metric/{context}/task_inventory/tasks_assigned"]["value"],16)
            self.assertEqual(facts[f"arm_metric/{context}/task_inventory/executed_tasks_completed"]["value"],8)

    def test_missing_dictionary_unbound_or_failed_external_verdict_never_authorizes(self):
        self.assertFalse(self.ledger(replay_check=None)["quantitative_facts_available"])
        with self.assertRaises(ValueError): self.ledger(replay_check={"passed":True,"model_calls":0})
        verdicts = ({"passed":True,"model_calls":0},
            {"passed":True,"model_calls":False,"report_hash":self.report["report_hash"],"protocol_hash":self.report["protocol_hash"]},
            {"passed":1,"model_calls":0,"report_hash":self.report["report_hash"],"protocol_hash":self.report["protocol_hash"]},
            {"passed":False,"model_calls":0,"report_hash":self.report["report_hash"],"protocol_hash":self.report["protocol_hash"]},
            {"passed":True,"model_calls":0,"report_hash":"0"*64,"protocol_hash":self.report["protocol_hash"]})
        for verdict in verdicts:
            ledger = self.ledger(replay_check=lambda report,v=verdict:v)
            self.assertFalse(ledger["quantitative_facts_available"])
            self.assertNotIn(PRIMARY_PAIR+"/mean_difference",ledger["facts"])
            self.assertFalse(any(k.startswith("process/") for k in ledger["facts"]))

    def test_report_embedded_verification_cannot_replace_separate_gate(self):
        bad = copy.deepcopy(self.report); bad["verification"] = {"passed":True}; bad = _seal(bad,"report_hash")
        ledger = self.ledger(bad,replay_check=None)
        self.assertFalse(ledger["quantitative_facts_available"])
        self.assertFalse(ledger["facts"]["replay/external_authorization/pass"]["value"])

    def test_exact_source_pin_and_saved_verification_ref_authorize_current_version(self):
        ref,obj = source_object(self.report,version=4)
        gate = lambda report:{"passed":True,"model_calls":0,"result_ref":copy.deepcopy(ref)}
        ledger = self.ledger(report_id=ref["id"],source_ref=ref,source_object=obj,replay_check=gate)
        self.assertTrue(ledger["quantitative_facts_available"])
        self.assertEqual(ledger["source_ref"],ref)
        self.assertEqual(ledger["facts"]["source_pin/version"]["value"],4)
        self.assertEqual(ledger["external_authorization"]["binding"],"exact_result_pin")
        wrong = {**ref,"version":3}
        self.assertFalse(self.ledger(source_ref=ref,source_object=obj,replay_check=lambda report:{"passed":True,"model_calls":0,"result_ref":wrong})["quantitative_facts_available"])

    def test_pin_identity_version_hash_kind_payload_and_backend_contradictions_reject(self):
        for attack in ("version","boolean_version","float_version","kind","id","hash","core","canonical","registration","model","mode"):
            ref,obj = source_object(self.report); kwargs = {"source_ref":ref,"source_object":obj}
            if attack == "version": obj["version"] = 2
            elif attack == "boolean_version": ref["version"] = obj["version"] = True
            elif attack == "float_version": ref["version"] = obj["version"] = 1.0
            elif attack == "kind": obj["kind"] = "resource_experiment"
            elif attack == "id": kwargs["report_id"] = "other"
            elif attack == "hash": obj["payload"]["outside_wrapper"] = True
            elif attack == "core": obj["payload"]["runs"] = []
            elif attack == "canonical": obj["payload"]["canonical_execution_report_hash"] = "0"*64
            elif attack == "registration": obj["payload"]["registered_hash"] = "0"*64
            elif attack == "model": obj["payload"]["model"] = "other"
            else: obj["payload"]["agent_mode"] = "live"
            if attack in ("core","canonical","registration","model","mode"):
                obj["hash"] = ref["hash"] = fingerprint(obj["payload"])
            with self.subTest(attack=attack),self.assertRaises(ValueError): self.ledger(**kwargs)
        with self.assertRaises(ValueError): self.ledger(source_ref=source_object(self.report)[0])

    def test_primary_policy_itt_is_distinct_from_post_treatment_receipt_counts(self):
        facts = self.ledger()["facts"]
        self.assertEqual(facts[PRIMARY_PAIR+"/mean_difference"]["interpretation"],"policy_itt")
        receipt = facts["process/active/recorded_receipts"]
        self.assertEqual(receipt["value"],2); self.assertEqual(receipt["interpretation"],"post_treatment_description")
        self.assertIn("not provider consumption",receipt["definition"])
        self.assertEqual(facts["process/active/execution_status/completed"]["value"],2)
        self.assertFalse(any("belief" in identity or "mediation" in identity for identity in facts))

    def test_never_delivered_complete_swarms_are_in_itt_without_false_adoption(self):
        p = create_timed_resource_protocol(resamples=100,max_rounds=3,release_rounds=(3,),subject_backend=BACKEND)
        report = run_timed_resource_experiment(p,offline_resource_policy); ledger = self.ledger(report)
        self.assertTrue(ledger["quantitative_facts_available"])
        for context in ("active","neutral"):
            self.assertEqual(ledger["facts"][f"process/{context}/recorded_receipts"]["value"],0)
            self.assertEqual(ledger["facts"][f"process/{context}/never_delivered_completed_swarms"]["value"],2)
            self.assertEqual(ledger["facts"][f"process/{context}/eligibility_unresolved_completed_swarms"]["value"],2)
        self.assertEqual(ledger["facts"]["trial_count/completed"]["value"],4)
        self.assertEqual(ledger["facts"][PRIMARY_PAIR+"/mean_difference"]["value"],0.0)

    def test_n2_resolution_null_and_bootstrap_do_not_establish_equivalence(self):
        facts = self.ledger()["facts"]
        self.assertEqual(facts[PRIMARY_ANALYSIS+"/test_resolution/minimum_two_sided_p"]["value"],.5)
        self.assertEqual(facts[PRIMARY_ANALYSIS+"/test_resolution/exact_minimum_fraction"]["value"],"2/4")
        self.assertEqual(facts[PRIMARY_ANALYSIS+"/p_two_sided"]["value"],1.0)
        self.assertEqual(facts[PRIMARY_INTERVAL+"/lower"]["value"],-1)
        self.assertEqual(facts[PRIMARY_INTERVAL+"/upper"]["value"],1)
        self.assertFalse(facts[PRIMARY_INTERVAL+"/excludes_zero"]["value"])
        self.assertTrue(facts[PRIMARY_ANALYSIS+"/bootstrap_degenerate"]["value"])
        self.assertIn("does not establish equivalence",facts[PRIMARY_PAIR+"/mean_direction"]["definition"])

    def test_test_fixture_effect_is_percentage_points_not_relative_change(self):
        p = create_timed_resource_protocol(resamples=100,max_rounds=3,release_rounds=(3,),subject_backend=BACKEND)
        def policy(request):
            if request["role"] == "agent-0" and request["context"]:
                return {"action":"work_independent" if request["context"] == [ACTIVE_NOTE] else "wait"}
            return timed_resource_infrastructure_policy(request)
        facts = self.ledger(run_timed_resource_experiment(p,policy))["facts"]
        self.assertEqual(facts[PRIMARY_PAIR+"/mean_difference"]["value"],.125)
        self.assertEqual(facts[PRIMARY_PAIR+"/mean_difference_percentage_points"]["value"],12.5)
        self.assertEqual(facts[PRIMARY_PAIR+"/mean_difference_percentage_points"]["value_unit"],"percentage_points")
        self.assertEqual(facts[PRIMARY_ANALYSIS+"/p_two_sided"]["value"],.5)

    def test_incomplete_reports_have_assignments_and_statuses_but_no_quantities(self):
        p = create_timed_resource_protocol(resamples=100,max_rounds=2,subject_backend=BACKEND)
        with self.assertRaises(TimedResourceExecutionError) as caught:
            run_timed_resource_experiment(p,lambda request:(_ for _ in ()).throw(TimeoutError("Unknown consumption")))
        ledger = self.ledger(caught.exception.partial_report)
        self.assertFalse(ledger["quantitative_facts_available"])
        self.assertEqual(ledger["facts"]["trial_count/assigned"]["value"],4)
        self.assertEqual(ledger["facts"]["execution_units/status/incomplete"]["value"],1)
        self.assertEqual(ledger["facts"]["execution_units/status/not_started"]["value"],3)
        for prefix in ("arm_metric/","process/","paired_world/","comparison/","interval/"):
            self.assertFalse(any(k.startswith(prefix) for k in ledger["facts"]))
        self.assertNotIn(PRIMARY_ANALYSIS+"/p_two_sided",ledger["facts"])
        self.assertNotIn("trial_count/completed",ledger["facts"])

    def test_forged_intervals_schedules_or_typed_counts_block_even_permissive_gate(self):
        mutations = [lambda r:r["analysis"]["primary_effect"].update(ci95=[.1,.2]),
            lambda r:r["analysis"]["primary_effect"].update(p_two_sided=False),
            lambda r:r["analysis"]["primary_effect"].update(difference=0),
            lambda r:r["runs"][0]["counts"].update(recorded_receipts=True),
            lambda r:r["runs"][0]["initial_world_identity"]["schedule"].reverse(),
            lambda r:r.update(model_calls=False),lambda r:r["runs"][0]["outcomes"].update(task_completion_fraction=True)]
        permissive = lambda r:{"passed":True,"model_calls":0,"report_hash":r["report_hash"],"protocol_hash":r["protocol_hash"]}
        for mutate in mutations:
            bad = copy.deepcopy(self.report); mutate(bad); bad = _seal(bad,"report_hash")
            ledger = self.ledger(bad,replay_check=permissive)
            self.assertFalse(ledger["quantitative_facts_available"])
            self.assertNotIn(PRIMARY_PAIR+"/mean_difference",ledger["facts"])

    def test_input_null_nonfinite_status_or_duplicate_ids_cannot_become_valid_facts(self):
        for mutate in (lambda r:r.update(status=None),lambda r:r.update(status=True),
                       lambda r:r["runs"].append(copy.deepcopy(r["runs"][0])),
                       lambda r:r["analysis"]["primary_effect"].update(difference=float("nan"))):
            bad = copy.deepcopy(self.report); mutate(bad)
            with self.assertRaises(ValueError): self.ledger(bad)
        bad = copy.deepcopy(self.report); bad["analysis"]["primary_effect"]["ci95"] = None; bad = _seal(bad,"report_hash")
        self.assertFalse(self.ledger(bad)["quantitative_facts_available"])

    def test_claim_contradictions_bool_float_null_units_and_scopes_are_rejected(self):
        ledger = self.ledger()
        claims = [make_claim(ledger,"trial_count/completed",True,claim_id="boolean"),make_claim(ledger,"trial_count/completed",4.0,claim_id="float"),
                  make_claim(ledger,"trial_count/seed_blocks/completed",4),make_claim(ledger,PRIMARY_PAIR+"/mean_direction","higher")]
        result = audit_timed_resource_claims(ledger,claims)
        self.assertEqual([r["status"] for r in result["claims"]],["mismatch"]*4)
        claim = make_claim(ledger,PRIMARY_ANALYSIS+"/p_two_sided",None)
        self.assertEqual(audit_timed_resource_claims(ledger,[claim])["claims"][0]["status"],"invalid")
        claim = make_claim(ledger,"process/active/recorded_receipts",2); claim["scope"] = "historical"
        self.assertEqual(audit_timed_resource_claims(ledger,[claim])["claims"][0]["status"],"mismatch")

    def test_correct_number_never_approves_free_prose_or_general_causality(self):
        ledger = self.ledger()
        claim = make_claim(ledger,PRIMARY_PAIR+"/mean_direction","equal",statement="All agents are immune to private thoughts.")
        result = audit_timed_resource_claims(ledger,[claim]); row = result["claims"][0]
        self.assertEqual(row["status"],"supported"); self.assertEqual(row["prose_status"],"unverified")
        self.assertFalse(result["attached_prose_approved"]); self.assertTrue(result["review_required"])
        self.assertNotIn("immune",row["approved_fact_text"])

    def test_pair_schedule_hash_facts_are_exact_but_not_realized_access_identity(self):
        ledger = self.ledger(); facts = ledger["facts"]
        self.assertTrue(facts["paired_world/all_initial_states_identical"]["value"])
        self.assertTrue(facts["paired_world/all_fixed_schedules_identical"]["value"])
        self.assertIn("realized access may differ",facts["paired_world/all_fixed_schedules_identical"]["definition"])
        for run in self.report["runs"]:
            self.assertEqual(facts[f"paired_world/{run['block_id']}/schedule_hash"]["value"],run["initial_world_identity"]["schedule_hash"])

    def test_packet_bound_and_ledger_hash_prevent_silent_changes(self):
        ledger = self.ledger(); ids = default_timed_resource_fact_ids(ledger)
        packet = select_fact_packet(ledger,ids); schema = claims_schema_for_packet(packet)
        self.assertLessEqual(len(ids),28)
        self.assertEqual(schema["properties"]["claims"]["items"]["properties"]["source_fingerprint"]["enum"],[ledger["source_fingerprint"]])
        for maximum in (True,0,101):
            with self.assertRaises(ValueError): default_timed_resource_fact_ids(ledger,max_facts=maximum)
        changed = copy.deepcopy(ledger); changed["facts"][PRIMARY_PAIR+"/mean_difference"]["value"] = .9
        with self.assertRaises(ValueError): audit_timed_resource_claims(changed,[])


if __name__ == "__main__":
    unittest.main()
