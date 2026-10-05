"""CPU end-to-end timing studies; callback fixtures never make hosted calls."""
import copy
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import swarm_lab.intervention_timing as timing
import swarm_lab.timed_resource_experiments as study
from swarm_lab.resource_environment import offline_resource_policy, fingerprint, ResourceTaskEnvironment

FAKE_BACKEND = {"harness":"test_callback","model":"cpu_fixture","generation":{"policy":"declared_test_fixture"}}


def protocol(**kwargs):
    return study.create_timed_resource_protocol(resamples=100,**kwargs)


class TimedResourceStudyTests(unittest.TestCase):
    def test_pair_randomization_and_full_exogenous_path_match(self):
        p = protocol(trials_per_cell=4,seed=51,max_rounds=5)
        units = study.randomize_timed_resource_runs(p)
        self.assertEqual(units,study.randomize_timed_resource_runs(p))
        self.assertEqual(Counter(u["context"] for u in units),{"active":4,"neutral":4})
        self.assertEqual(len(set(u["environment_seed"] for u in units)),4)
        for block in set(u["block_id"] for u in units):
            pair = [u for u in units if u["block_id"] == block]
            self.assertEqual({u["context"] for u in pair},{"active","neutral"})
            self.assertEqual(pair[0]["environment_seed"],pair[1]["environment_seed"])
        report = study.run_timed_resource_experiment(p)
        self.assertTrue(all(c["passed"] for c in report["paired_initial_world_checks"]))
        for block in set(u["block_id"] for u in units):
            pair = [r for r in report["runs"] if r["block_id"] == block]
            self.assertEqual(pair[0]["initial_state"],pair[1]["initial_state"])
            self.assertEqual(pair[0]["initial_world_identity"]["schedule"],pair[1]["initial_world_identity"]["schedule"])
            self.assertEqual(pair[0]["initial_world_identity"]["release_round"],pair[1]["initial_world_identity"]["release_round"])
        self.assertEqual(p["design"]["maximum_subject_calls"],160)

    def test_registered_inference_resolution_and_mismatch_fail_before_calls(self):
        p = protocol(subject_backend=FAKE_BACKEND)
        resolution = p["pre_execution_test_resolution"]
        self.assertEqual(resolution["block_swap_assignments"],4)
        self.assertEqual(resolution["minimum_two_sided_p"],.5)
        self.assertEqual(resolution["exact_minimum_fraction"],"2/4")
        calls = []
        with self.assertRaisesRegex(ValueError,"Resampling count"):
            study.run_timed_resource_experiment(p,lambda request:calls.append(request),resamples=2000)
        self.assertEqual(calls,[])
        for args in ({"trials_per_cell":1},{"resamples":99},{"trigger_kind":"late_canonical_fragment_gap"},{"active_text":"one"},{"seed":True}):
            with self.subTest(args=args),self.assertRaises(ValueError): study.create_timed_resource_protocol(**args)

    def test_protocol_semantics_and_source_pins_cannot_be_changed_by_resealing(self):
        for section,key,value in (("design","allocation","unblocked"),("intervention","recipients",["agent-1"]),
                ("estimand","primary_outcome","waits"),("measurement","infrastructure_failure","drop")):
            p = protocol(); p[section][key] = value; p = study._seal(p)
            with self.subTest(section=section,key=key),self.assertRaises(ValueError): study.validate_timed_resource_protocol(p)
        p = protocol(); p["measurement"]["resampling"]["exact_label_swap_max_blocks"] = 2; p = study._seal(p)
        with self.assertRaises(ValueError): study.validate_timed_resource_protocol(p)
        p = protocol(); p["execution_code_hashes"]["resource_environment.py"] = "0"*64; p = study._seal(p)
        with self.assertRaises(ValueError): study.run_timed_resource_experiment(p)

    def test_canonical_json_type_distinctions_are_not_python_numeric_equality(self):
        for section,key,value in (("design","maximum_subject_calls",96.0),("design","maximum_preparations_per_swarm",True),
                ("pre_execution_test_resolution","block_swap_assignments",4.0)):
            p = protocol(); p[section][key] = value; p = study._seal(p)
            with self.subTest(section=section,key=key),self.assertRaises(ValueError): study.validate_timed_resource_protocol(p)
        report = study.run_timed_resource_experiment(protocol(max_rounds=2))
        for mutate in (lambda r:r["runs"][0]["turns"][0].update(step=float(r["runs"][0]["turns"][0]["step"])),
                       lambda r:r["runs"][0]["counts"].update(terminal_completion=1),
                       lambda r:r["runs"][0]["boundaries"][0].update(subject_call_attempted=1)):
            bad = copy.deepcopy(report); mutate(bad); bad = study._seal(bad,"report_hash")
            self.assertFalse(study.replay_timed_resource_report(bad)["passed"])

    def test_top_level_generated_declarations_and_backend_are_bound_to_protocol(self):
        report = study.run_timed_resource_experiment(protocol(max_rounds=2))
        for mutate in (lambda r:r.update(api_version="other"),lambda r:r.update(experiment_id="other"),
                       lambda r:r.update(maximum_subject_calls=float(r["maximum_subject_calls"])),lambda r:r.update(model_calls=False),
                       lambda r:r["backend"]["metadata"].update(model="another"),lambda r:r["backend"].update(mode="provided_callback"),
                       lambda r:r["backend"]["registered_spec"]["generation"].update(notes_ignored=1),
                       lambda r:r.update(local_artifacts_before_subject_calls=0)):
            bad = copy.deepcopy(report); mutate(bad); bad = study._seal(bad,"report_hash")
            self.assertFalse(study.replay_timed_resource_report(bad)["passed"])

    def test_default_cpu_integration_is_exact_paired_null_with_real_receipts(self):
        report = study.run_timed_resource_experiment(protocol())
        self.assertEqual(report["status"],"complete")
        self.assertEqual(report["model_calls"],0)
        effect = report["analysis"]["primary_effect"]
        self.assertEqual(effect["difference"],0)
        self.assertEqual(effect["paired_differences"],[0,0])
        self.assertEqual(effect["p_two_sided"],1)
        self.assertEqual(effect["ci95"],[-1,1])
        self.assertEqual(effect["n_seed_blocks"],2)
        for run in report["runs"]:
            self.assertEqual(run["counts"]["eligible_preparations"],1)
            self.assertEqual(run["counts"]["recorded_receipts"],1)
            self.assertEqual(run["counts"]["subject_call_attempts"],len(run["turns"]))
            self.assertEqual(run["counts"]["applied_actions"],len(run["turns"]))
            self.assertTrue(run["counts"]["terminal_completion"])
        self.assertTrue(study.replay_timed_resource_report(report)["passed"])

    def test_scoped_private_persistence_and_no_trigger_evaluation_after_receipt(self):
        report = study.run_timed_resource_experiment(protocol(max_rounds=4,release_rounds=(4,)))
        p = report["protocol"]
        for run in report["runs"]:
            own_turn = 0
            for boundary,turn in zip(run["boundaries"],run["turns"]):
                request = turn["request"]
                self.assertEqual(set(request),{"role","system","context","observation","action_schema"})
                for key in ("arm","context","seed","release_round","protocol_hash"):
                    self.assertNotIn(key,request["observation"])
                if turn["agent_id"] != "agent-0":
                    self.assertEqual(request["context"],[])
                    self.assertEqual(boundary["mode"],"nonrecipient_no_trigger_evaluation")
                    continue
                own_turn += 1
                if own_turn == 1:
                    self.assertEqual(request["context"],[])
                    self.assertIsNone(boundary["trigger_output"]["decision"]["eligible"])
                else:
                    self.assertEqual(request["context"],[p["timing_spec"]["content"][run["context"]]])
                    if own_turn == 2:
                        self.assertTrue(boundary["trigger_output"]["decision"]["eligible"])
                        self.assertEqual(boundary["local_receipt"]["actual_request_hash"],fingerprint(request))
                    else:
                        self.assertEqual(boundary["mode"],"preparation_limit_consumed")
                        self.assertIsNone(boundary["trigger_output"])
            for event in run["timing_report"]["events"]:
                if event["type"] == "prepare":
                    self.assertEqual(event["request"]["context"],[])
                    self.assertEqual(event["output"]["decision"]["trigger_hash"],p["trigger_hash"])

    def test_test_only_context_sensitive_fixture_verifies_both_effect_directions(self):
        for reverse in (False,True):
            p = protocol(max_rounds=3,release_rounds=(3,),subject_backend=FAKE_BACKEND)
            observed = []
            def policy(request):
                observed.append(copy.deepcopy(request))
                if request["role"] == "agent-0" and request["context"]:
                    is_active = request["context"] == [study.ACTIVE_NOTE]
                    return {"action":"work_independent" if is_active != reverse else "wait"}
                return study.timed_resource_infrastructure_policy(request)
            report = study.run_timed_resource_experiment(p,policy)
            self.assertEqual(report["analysis"]["primary_effect"]["difference"],-.125 if reverse else .125)
            self.assertEqual(report["analysis"]["primary_effect"]["p_two_sided"],.5)
            first_inserted = next(r for r in observed if r["context"])
            self.assertEqual(len(first_inserted["observation"]["your_action_history"]),1)
            self.assertEqual(first_inserted["observation"]["your_action_history"][0]["action"],{"action":"wait"})
            self.assertTrue(study.replay_timed_resource_report(report)["passed"])

    def test_never_delivered_completed_swarms_remain_in_itt(self):
        p = protocol(max_rounds=3,release_rounds=(3,),subject_backend=FAKE_BACKEND)
        report = study.run_timed_resource_experiment(p,offline_resource_policy)
        self.assertEqual(len(report["runs"]),4)
        for run in report["runs"]:
            self.assertEqual(run["status"],"complete")
            self.assertEqual(run["counts"]["recorded_receipts"],0)
            self.assertEqual(run["timing_report"]["execution_status"],"completed")
            self.assertTrue(run["timing_report"]["policy_itt"]["retain_assigned_unit"])
        for cell in report["analysis"]["cells"].values():
            self.assertEqual(cell["n_swarms"],2); self.assertEqual(cell["never_delivered_completed_swarms"],2)
        self.assertEqual(report["analysis"]["primary_effect"]["difference"],0)
        self.assertTrue(study.replay_timed_resource_report(report)["passed"])
        with self.assertRaises(ValueError): study.analyze_timed_resource_runs(report["runs"][:-1],p)
        with self.assertRaises(ValueError): study.analyze_timed_resource_runs(list(reversed(report["runs"])),p)

    def test_exogenous_initial_path_mismatch_blocks_every_callback(self):
        p = protocol(subject_backend=FAKE_BACKEND); calls = []; actual_factory = study.create_resource_environment; constructions = []
        def mismatched(spec,seed):
            env = actual_factory(spec,seed); constructions.append(env)
            # Alter a later path slot rather than only the current actor.
            if len(constructions) == 2: env.schedule[-1],env.schedule[-2] = env.schedule[-2],env.schedule[-1]
            return env
        # The world contract restores state, so preserve our deliberate changed
        # schedule as the observed initial fixture through the contract check.
        with patch.object(study,"create_resource_environment",side_effect=mismatched),patch.object(study,"check_resource_contract",return_value={"passed":True}):
            with self.assertRaises(study.TimedResourceExecutionError) as error:
                study.run_timed_resource_experiment(p,lambda request:calls.append(request))
        self.assertEqual(calls,[]); self.assertNotIn("analysis",error.exception.partial_report)
        self.assertEqual(len(error.exception.partial_report["assignments"]),4)

    def test_all_initial_states_and_receipts_archived_before_callback(self):
        p = protocol(max_rounds=3,subject_backend=FAKE_BACKEND)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory); calls = []
            def policy(request):
                self.assertEqual(len(list((output/"initial_states").glob("*.json"))),4)
                self.assertEqual(json.loads((output/"execution-code/manifest.json").read_text())["files"],p["execution_code_hashes"])
                pending = json.loads((output/"pending_decision.json").read_text())
                self.assertEqual(pending["request"],request)
                self.assertFalse(pending["boundary"]["subject_call_attempted"])
                if request["context"] and len(request["observation"]["your_action_history"]) == 1:
                    self.assertEqual(pending["boundary"]["local_receipt"]["actual_request_hash"],fingerprint(request))
                calls.append(request); return study.timed_resource_infrastructure_policy(request)
            report = study.run_timed_resource_experiment(p,policy,output)
            self.assertEqual(len(calls),48)
            self.assertTrue(study.replay_timed_resource_report(report,output_dir=output)["passed"])
            with self.assertRaises(ValueError): study.run_timed_resource_experiment(p,policy,output)

    def test_transport_failure_after_receipt_retains_unknown_attempt_without_retry(self):
        p = protocol(trigger_kind="first_decision",subject_backend=FAKE_BACKEND); calls = []
        def fail_on_private(request):
            calls.append(request)
            if request["context"]: raise TimeoutError("Unknown provider consumption")
            return study.timed_resource_infrastructure_policy(request)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(study.TimedResourceExecutionError) as error: study.run_timed_resource_experiment(p,fail_on_private,directory)
            report = error.exception.partial_report; failed = next(r for r in report["runs"] if r["status"] == "incomplete")
            self.assertEqual(report["status"],"incomplete_infrastructure_failure"); self.assertNotIn("analysis",report)
            self.assertEqual(len(report["runs"]),4); self.assertEqual(Counter(r["status"] for r in report["runs"]),{"incomplete":1,"not_started":3})
            self.assertEqual(failed["counts"]["recorded_receipts"],1)
            self.assertEqual(failed["counts"]["subject_call_attempts"],failed["counts"]["applied_actions"]+1)
            self.assertEqual(failed["timing_report"]["execution_status"],"unknown")
            self.assertIsNone(failed["timing_report"]["policy_itt"]["caller_supplied_outcome"])
            self.assertEqual(sum(bool(r["context"]) for r in calls),1)
            replay = study.replay_timed_resource_report(report,output_dir=directory)
            self.assertFalse(replay["passed"]); self.assertTrue(replay["partial_trace_consistent"])

    def test_failure_after_a_completed_unit_keeps_complete_and_unstarted_units(self):
        p = protocol(max_rounds=2,release_rounds=(2,),subject_backend=FAKE_BACKEND); calls = []
        def fail_ninth(request):
            calls.append(request)
            if len(calls) == 9: raise TimeoutError("No automatic replacement")
            return study.timed_resource_infrastructure_policy(request)
        with self.assertRaises(study.TimedResourceExecutionError) as error: study.run_timed_resource_experiment(p,fail_ninth)
        report = error.exception.partial_report
        self.assertEqual([r["status"] for r in report["runs"]],["complete","incomplete","not_started","not_started"])
        self.assertEqual(report["runs"][0]["timing_report"]["execution_status"],"completed")
        self.assertNotIn("analysis",report)
        self.assertTrue(study.replay_timed_resource_report(report)["partial_trace_consistent"])

    def test_unmaterialized_and_unstarted_units_cannot_claim_receipts_or_outcomes(self):
        p = protocol()
        with patch.object(study,"create_resource_environment",side_effect=RuntimeError("No world created")):
            with self.assertRaises(study.TimedResourceExecutionError) as error: study.run_timed_resource_experiment(p)
        report = error.exception.partial_report
        self.assertTrue(study.replay_timed_resource_report(report)["partial_trace_consistent"])
        attacks = [lambda r:r["runs"][0]["counts"].update(recorded_receipts=1),
                   lambda r:r["runs"][0].update(timing_report={"invented_receipt":True}),
                   lambda r:r["runs"][1].update(outcomes={"task_completion_fraction":1.0}),
                   lambda r:r["runs"][1].update(final_state={"invented":True}),
                   lambda r:r["runs"][0].update(unfinalizable_timing_snapshot={"receipt":True})]
        for mutate in attacks:
            bad = copy.deepcopy(report); mutate(bad); bad = study._seal(bad,"report_hash")
            self.assertFalse(study.replay_timed_resource_report(bad)["partial_trace_consistent"])

    def test_post_failure_completed_counterpart_cannot_be_spliced_into_partial_trace(self):
        p = protocol(max_rounds=2,release_rounds=(2,),subject_backend=FAKE_BACKEND)
        full = study.run_timed_resource_experiment(p,study.timed_resource_infrastructure_policy)
        count = [0]
        def fail_ninth(request):
            count[0] += 1
            if count[0] == 9: raise TimeoutError("Abort")
            return study.timed_resource_infrastructure_policy(request)
        with self.assertRaises(study.TimedResourceExecutionError) as error: study.run_timed_resource_experiment(p,fail_ninth)
        partial = error.exception.partial_report
        self.assertTrue(study.replay_timed_resource_report(partial)["partial_trace_consistent"])
        self.assertEqual([r["status"] for r in partial["runs"]],["complete","incomplete","not_started","not_started"])
        bad = copy.deepcopy(partial); bad["runs"][2] = copy.deepcopy(full["runs"][2]); bad = study._seal(bad,"report_hash")
        self.assertFalse(study.replay_timed_resource_report(bad)["partial_trace_consistent"])
        p = protocol(subject_backend=FAKE_BACKEND)
        with self.assertRaises(study.TimedResourceExecutionError) as error:
            study.run_timed_resource_experiment(p,lambda request:(_ for _ in ()).throw(TimeoutError("Unknown")))
        materialized = error.exception.partial_report
        self.assertTrue(study.replay_timed_resource_report(materialized)["partial_trace_consistent"])
        for extra in ({"outcomes":{"task_completion_fraction":1}},{"final_state":{}},{"timing_report":{"invented":True}}):
            bad = copy.deepcopy(materialized); bad["runs"][1].update(extra); bad = study._seal(bad,"report_hash")
            self.assertFalse(study.replay_timed_resource_report(bad)["partial_trace_consistent"])

    def test_insertion_failure_preserves_eligible_boundary_without_subject_attempt(self):
        p = protocol(trigger_kind="first_decision",subject_backend=FAKE_BACKEND); calls = []
        actual_inject = ResourceTaskEnvironment.inject_context
        def fail_registered_note(env,actor,text):
            if text in (study.ACTIVE_NOTE,study.NEUTRAL_NOTE): raise OSError("Insertion unavailable")
            return actual_inject(env,actor,text)
        with patch.object(ResourceTaskEnvironment,"inject_context",new=fail_registered_note):
            with self.assertRaises(study.TimedResourceExecutionError) as error:
                study.run_timed_resource_experiment(p,lambda request:(calls.append(request),{"action":"wait"})[1])
        report = error.exception.partial_report; failed = report["runs"][0]
        self.assertEqual(failed["counts"]["eligible_preparations"],1)
        self.assertEqual(failed["counts"]["recorded_receipts"],0)
        self.assertEqual(failed["counts"]["subject_call_attempts"],len(calls))
        self.assertEqual(failed["boundaries"][-1]["construction_status"],"incomplete")
        self.assertFalse(failed["boundaries"][-1]["subject_call_attempted"])
        self.assertTrue(study.replay_timed_resource_report(report)["partial_trace_consistent"])

    def test_receipt_mismatch_never_invokes_the_altered_request(self):
        p = protocol(trigger_kind="first_decision",subject_backend=FAKE_BACKEND); calls = []; actual_request = study.resource_subject_request
        def changed_after_insertion(env,actor):
            request = actual_request(env,actor)
            if request["context"]: request["observation"]["task"] += " changed"
            return request
        with patch.object(study,"resource_subject_request",side_effect=changed_after_insertion):
            with self.assertRaises(study.TimedResourceExecutionError) as error:
                study.run_timed_resource_experiment(p,lambda request:(calls.append(request),{"action":"wait"})[1])
        report = error.exception.partial_report
        self.assertFalse(any(r["context"] for r in calls))
        failed = report["runs"][0]
        self.assertEqual(failed["timing_report"]["delivery_failure"]["reason"],"request_contract_mismatch")
        self.assertEqual(failed["counts"]["recorded_receipts"],0)
        self.assertTrue(study.replay_timed_resource_report(report)["partial_trace_consistent"])

    def test_source_drift_cannot_bypass_retained_incomplete_report(self):
        p = protocol(subject_backend=FAKE_BACKEND); changed = [False]; actual_hash = timing.module_hash; calls = []
        def hash_after_callback(): return "0"*64 if changed[0] else actual_hash()
        def policy(request):
            calls.append(request); changed[0] = True; return {"action":"wait"}
        with patch.object(timing,"module_hash",side_effect=hash_after_callback):
            with self.assertRaises(study.TimedResourceExecutionError) as error: study.run_timed_resource_experiment(p,policy)
        report = error.exception.partial_report
        self.assertEqual(len(report["assignments"]),4); self.assertNotIn("analysis",report)
        failed = report["runs"][0]
        self.assertIn("unfinalizable_timing_snapshot",failed)
        self.assertIn("timing_finalization_failure",failed)
        self.assertEqual(failed["counts"]["timing_counts_source"],"unsealed_controller_snapshot")
        self.assertFalse(study.replay_timed_resource_report(report)["passed"])

    def test_reporting_failure_preserves_terminal_world_outcome_without_estimate(self):
        p = protocol(max_rounds=2,release_rounds=(2,)); actual_write = study._write; failed_once = [False]
        def write_with_one_progress_error(path,value):
            if path.name == "progress.json" and any(r["status"] == "complete" for r in value.get("runs",[])) and not failed_once[0]:
                failed_once[0] = True; raise OSError("Progress archive failed")
            return actual_write(path,value)
        with tempfile.TemporaryDirectory() as directory,patch.object(study,"_write",side_effect=write_with_one_progress_error):
            with self.assertRaises(study.TimedResourceExecutionError) as error: study.run_timed_resource_experiment(p,output_dir=directory)
            report = error.exception.partial_report
            self.assertEqual([r["status"] for r in report["runs"]],["complete","not_started","not_started","not_started"])
            self.assertIn("outcomes",report["runs"][0]); self.assertNotIn("analysis",report)
            self.assertEqual(report["failure"]["phase"],"persist_completed_run")
            self.assertTrue(study.replay_timed_resource_report(report,output_dir=directory)["partial_trace_consistent"])

    def test_analysis_and_final_archive_failures_never_promote_estimates(self):
        p = protocol(max_rounds=2,release_rounds=(2,))
        with patch.object(study,"analyze_timed_resource_runs",side_effect=RuntimeError("Analysis unavailable")):
            with self.assertRaises(study.TimedResourceExecutionError) as error: study.run_timed_resource_experiment(p)
        report = error.exception.partial_report
        self.assertEqual(report["status"],"incomplete_analysis_failure"); self.assertNotIn("analysis",report)
        self.assertTrue(all(r["status"] == "complete" for r in report["runs"]))
        self.assertTrue(study.replay_timed_resource_report(report)["partial_trace_consistent"])
        actual_write = study._write
        def final_fail(path,value):
            if path.name == "report.json": raise OSError("Report cannot be archived")
            return actual_write(path,value)
        with tempfile.TemporaryDirectory() as directory,patch.object(study,"_write",side_effect=final_fail):
            with self.assertRaises(study.TimedResourceExecutionError) as error: study.run_timed_resource_experiment(p,output_dir=directory)
        self.assertNotIn("analysis",error.exception.partial_report)
        self.assertTrue(all(r["status"] == "complete" for r in error.exception.partial_report["runs"]))
        self.assertIn("failure_artifact_write_error",error.exception.partial_report)

    def test_invalid_actions_consume_budget_and_complete_zero_outcomes(self):
        p = protocol(max_rounds=2,release_rounds=(2,),subject_backend=FAKE_BACKEND)
        for action in (None,[],{"action":"invented"}):
            report = study.run_timed_resource_experiment(p,lambda request:copy.deepcopy(action))
            self.assertEqual(len(report["runs"]),4)
            for run in report["runs"]:
                self.assertEqual(run["outcomes"]["invalid_actions"],8)
                self.assertEqual(run["outcomes"]["task_completion_fraction"],0)
            self.assertTrue(study.replay_timed_resource_report(report)["passed"])

    def test_exact_and_approximate_label_swap_methods_match_registration(self):
        small = study.run_timed_resource_experiment(protocol(max_rounds=2))
        self.assertEqual(small["analysis"]["primary_effect"]["randomization_test"]["method"],"exact_block_label_swap")
        larger = study.run_timed_resource_experiment(protocol(trials_per_cell=17,max_rounds=2))
        test = larger["analysis"]["primary_effect"]["randomization_test"]
        self.assertEqual(test,{"method":"monte_carlo_block_label_swap_plus_one","resamples":100})
        self.assertEqual(larger["analysis"]["primary_effect"]["p_two_sided"],1)
        self.assertEqual(larger["analysis"]["primary_effect"]["independent_uncertainty_units"],"seed_blocks")

    def test_resigned_turn_receipt_world_and_analysis_tampering_fail_replay(self):
        report = study.run_timed_resource_experiment(protocol(max_rounds=3))
        mutations = [lambda r:r["runs"][0]["turns"][0].update(action={"action":"work_independent"}),
                     lambda r:r["runs"][0]["initial_world_identity"]["schedule"].reverse(),
                     lambda r:r["runs"][0]["outcomes"].update(task_completion_fraction=1),
                     lambda r:r["runs"][0]["counts"].update(recorded_receipts=0),
                     lambda r:r["analysis"]["primary_effect"].update(difference=.9),
                     lambda r:r["runs"][0]["timing_report"]["delivery_receipt"].update(actual_request_hash="0"*64)]
        for mutate in mutations:
            bad = copy.deepcopy(report); mutate(bad); bad = study._seal(bad,"report_hash")
            self.assertFalse(study.replay_timed_resource_report(bad)["passed"])

    def test_archive_bytes_and_manifest_are_checked_without_model_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory); report = study.run_timed_resource_experiment(protocol(max_rounds=2),output_dir=output)
            self.assertTrue(study.replay_timed_resource_report(report,output_dir=output)["passed"])
            target = output/"execution-code"/"intervention_timing.py"; target.write_bytes(target.read_bytes()+b"\n# changed\n")
            audit = study.replay_timed_resource_report(report,output_dir=output)
            self.assertFalse(audit["passed"]); self.assertEqual(audit["model_calls"],0)

    def test_backend_mismatch_and_bad_callback_registration_stop_before_calls(self):
        calls = []
        for p,kwargs in ((protocol(),{}),(protocol(subject_backend=FAKE_BACKEND),{"backend_metadata":{"harness":"other"}})):
            with self.assertRaises(ValueError): study.run_timed_resource_experiment(p,lambda request:calls.append(request),**kwargs)
        with self.assertRaises(ValueError): study.run_timed_resource_experiment(protocol(subject_backend=FAKE_BACKEND))
        self.assertEqual(calls,[])


if __name__ == "__main__":
    unittest.main()
