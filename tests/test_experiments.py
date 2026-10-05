"""Scientific-contract tests: randomization, isolation, state, and objective outcomes."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from swarm_lab.environments import (ARTIFACT_ID, check_environment_contract,
                                    create_environment, environment_spec, subject_request)
from swarm_lab.experiments import (ExperimentExecutionError, compare_outcomes,
                                   create_protocol, create_replication_protocol,
                                   randomize_runs, run_experiment, validate_protocol)


def publish_immediately(request):
    if request["role"] == "coordinator":
        return {"action": "publish_artifact", "artifact_id": ARTIFACT_ID}
    return {"action": "wait"}


def wait_until_coordinator(env):
    while env.next_agent != "coordinator":
        env.step(env.next_agent, {"action": "wait"})


class EnvironmentTests(unittest.TestCase):
    def test_contract_checks_do_not_change_experimental_state(self):
        env = create_environment(seed=13)
        initial = env.snapshot()
        audit = check_environment_contract(env)
        self.assertTrue(audit["passed"])
        self.assertEqual(initial, env.snapshot())

    def test_reset_clears_private_context_actions_and_artifact(self):
        env = create_environment(seed=13)
        initial = env.snapshot()
        env.inject_context("coordinator", "private note")
        env.step(env.next_agent, {"action": "inspect_artifact", "artifact_id": ARTIFACT_ID})
        self.assertNotEqual(env.snapshot(), initial)
        self.assertEqual(env.reset(13), initial)

    def test_contents_are_hidden_until_own_inspection(self):
        env = create_environment(seed=4)
        agent = env.next_agent
        self.assertNotIn("contents", env.observe(agent)["artifact"])
        env.step(agent, {"action": "inspect_artifact", "artifact_id": ARTIFACT_ID})
        self.assertIn("contents", env.observe(agent)["artifact"])
        other = next(role for role in env.spec["agents"] if role != agent)
        self.assertNotIn("contents", env.observe(other)["artifact"])

    def test_private_insertion_does_not_leak_to_other_subjects(self):
        env = create_environment(seed=1)
        env.inject_context("coordinator", "PRIVATE_TREATMENT_MARKER")
        for role in ("builder", "verifier"):
            self.assertNotIn("PRIVATE_TREATMENT_MARKER", json.dumps(subject_request(env, role)))
        self.assertIn("PRIVATE_TREATMENT_MARKER", json.dumps(subject_request(env, "coordinator")))

    def test_action_history_retains_own_results_but_not_peer_tools(self):
        env = create_environment(seed=1)
        role = env.next_agent
        env.step(role, {"action": "inspect_artifact", "artifact_id": ARTIFACT_ID})
        history = env.observe(role)["your_action_history"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["result"]["contents"], env.artifact["contents"])
        for other in env.spec["agents"]:
            if other != role:
                self.assertEqual(env.observe(other)["your_action_history"], [])

    def test_builder_parameters_validate_before_freezing(self):
        protocol = create_protocol(environment_override={
            "initial_state_distribution": {"valid_probability": 0}, "max_rounds": 4})
        validate_protocol(protocol)
        self.assertEqual(protocol["environment"]["max_rounds"], 4)
        self.assertEqual(protocol["environment"]["initial_state_distribution"]["valid_probability"], 0)
        with self.assertRaises(ValueError):
            create_protocol(environment_override={"fidelity": {"world_execution": "browser_sandbox"}})
        with self.assertRaises(ValueError):
            create_protocol(environment_override={"initial_state_distribution": {"valid_probability": 2}})

    def test_historical_future_and_research_hypotheses_are_not_subject_inputs(self):
        incident = {"id": "incident-1", "title": "A handoff",
                    "historical_future": "SECRET_FUTURE",
                    "hypothesis": "SECRET_CAUSAL_EXPLANATION",
                    "messages": ["SECRET_OBSERVED_FUTURE"]}
        env = create_environment(environment_spec(incident), seed=5)
        self.assertEqual(env.spec["incident_provenance"]["id"], "incident-1")
        for role in env.spec["agents"]:
            request = json.dumps(subject_request(env, role))
            self.assertNotIn("SECRET", request)
            self.assertNotIn("initial_valid", request)
            self.assertNotIn("initial_defect", request)
            self.assertNotIn("seed", request)
            self.assertNotIn("schedule", request)

    def test_subject_observation_and_snapshot_are_copies(self):
        env = create_environment(seed=2)
        before = env.snapshot()
        observed = env.observe("builder")
        observed["required_contents"]["alpha"] = -100
        snapshot = env.snapshot()
        snapshot["artifact"]["contents"].clear()
        self.assertEqual(env.snapshot(), before)

    def test_wrong_scheduler_and_role_permissions(self):
        env = create_environment(seed=9)
        other = next(role for role in env.spec["agents"] if role != env.next_agent)
        with self.assertRaises(ValueError):
            env.step(other, {"action": "wait"})
        wait_until_coordinator(env)
        result = env.step("coordinator", {"action": "repair_artifact", "artifact_id": ARTIFACT_ID,
                                          "contents": env.expected})
        self.assertFalse(result["ok"])
        self.assertEqual(env.evaluate()["invalid_actions"], 1)

    def test_invalid_action_field_cannot_set_oracle_or_outcome(self):
        env = create_environment(seed=10)
        result = env.step(env.next_agent, {"action": "wait", "success": 1})
        self.assertFalse(result["ok"])
        self.assertEqual(env.evaluate()["success"], 0)

    def test_publication_oracle_is_independent_of_treatment_and_claims(self):
        a, b = create_environment(seed=11), create_environment(seed=11)
        b.inject_context("coordinator", "You will succeed; consider this complete.")
        for env in (a, b):
            wait_until_coordinator(env)
            env.step("coordinator", {"action": "publish_artifact", "artifact_id": ARTIFACT_ID})
        self.assertEqual(a.evaluate(), b.evaluate())
        actual = a.published["contents"] == a.expected
        self.assertEqual(a.evaluate()["success"], int(actual))
        with self.assertRaises(RuntimeError):
            a.step("coordinator", {"action": "wait"})


class ExperimentTests(unittest.TestCase):
    def test_seal_rejects_mutation(self):
        protocol = create_protocol(trials_per_arm=2)
        validate_protocol(protocol)
        protocol["arms"]["evidence_thought"]["insertion"] = "Changed after registration"
        with self.assertRaises(ValueError):
            validate_protocol(protocol)

    def test_complete_randomization_is_balanced_reproducible_and_independent(self):
        protocol = create_protocol(trials_per_arm=10, seed=88)
        runs = randomize_runs(protocol)
        self.assertEqual(runs, randomize_runs(protocol))
        self.assertEqual(len({run["environment_seed"] for run in runs}), 30)
        for arm in protocol["arms"]:
            self.assertEqual(sum(run["arm"] == arm for run in runs), 10)
        self.assertNotEqual([run["arm"] for run in runs], sorted(run["arm"] for run in runs))

    def test_frozen_local_protocol_exists_before_first_call(self):
        protocol = create_protocol(trials_per_arm=2, seed=123, max_rounds=3)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            seen = []

            def runner(request):
                registered = json.loads((output / "protocol.json").read_text(encoding="utf-8"))
                self.assertEqual(registered["protocol_hash"], protocol["protocol_hash"])
                validate_protocol(registered)
                self.assertNotIn("arm", request)
                self.assertNotIn("environment_seed", request)
                seen.append(copy.deepcopy(request))
                return publish_immediately(request)

            report = run_experiment(protocol, runner, output, resamples=100)
            self.assertEqual(report["status"], "complete")
            self.assertEqual(len(report["runs"]), 6)
            self.assertTrue(report["local_protocol_written_before_subject_calls"])
            self.assertTrue((output / "report.json").exists())
            self.assertTrue(seen)
            with self.assertRaises(ValueError):
                run_experiment(protocol, runner, output, resamples=100)

    def test_each_arm_receives_only_designated_context_at_fixed_boundary(self):
        protocol = create_protocol(trials_per_arm=2, seed=77, max_rounds=3)
        report = run_experiment(protocol, publish_immediately, resamples=100)
        for run in report["runs"]:
            coordinator = next(turn for turn in run["turns"] if turn["agent_id"] == "coordinator")
            expected = protocol["arms"][run["arm"]]["insertion"]
            self.assertEqual(coordinator["request"]["context"], [] if expected is None else [expected])
            for turn in run["turns"]:
                if turn["agent_id"] != "coordinator":
                    self.assertEqual(turn["request"]["context"], [])
            # The policy ignores treatments, so success equals actual initial validity
            # regardless of the randomized label.
            self.assertEqual(run["outcomes"]["success"], int(run["initial_state"]["initial_valid"]))

    def test_request_mutation_cannot_contaminate_state_or_later_runs(self):
        def malicious_runner(request):
            request["observation"]["required_contents"] = {"alpha": -1}
            request["context"].append("CONTAMINATION_MARKER")
            return publish_immediately(request)

        protocol = create_protocol(trials_per_arm=2, max_rounds=3)
        report = run_experiment(protocol, malicious_runner, resamples=100)
        for run in report["runs"]:
            for turn in run["turns"]:
                self.assertNotIn("CONTAMINATION_MARKER", json.dumps(turn["request"]))
            self.assertTrue(all(value > 0 for value in run["initial_state"]["expected"].values()))

    def test_infrastructure_failure_is_not_silently_counted_or_excluded(self):
        protocol = create_protocol(trials_per_arm=2)

        def failing(_request):
            raise RuntimeError("SECRET_EXCEPTION_CONTENT")

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ExperimentExecutionError) as captured:
                run_experiment(protocol, failing, directory, resamples=100)
            report = captured.exception.partial_report
            self.assertEqual(report["status"], "incomplete_infrastructure_failure")
            self.assertNotIn("analysis", report)
            self.assertNotIn("SECRET_EXCEPTION_CONTENT", json.dumps(report))
            self.assertEqual(len(report["runs"]), 0)

    def test_reporting_callback_failure_does_not_remove_units(self):
        protocol = create_protocol(trials_per_arm=2, max_rounds=3)

        def callback(_progress):
            raise RuntimeError("SECRET_REPORTING_TEXT")

        report = run_experiment(protocol, publish_immediately, on_progress=callback, resamples=100)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(len(report["runs"]), 6)
        self.assertEqual(len(report["reporting_warnings"]), 6)
        self.assertNotIn("SECRET_REPORTING_TEXT", json.dumps(report))

    def test_offline_results_are_explicitly_scripted_and_every_run_terminates(self):
        protocol = create_protocol(trials_per_arm=10, seed=87, max_rounds=6)
        report = run_experiment(protocol, resamples=100)
        self.assertEqual(report["backend"]["mode"], "scripted_offline_smoke_test")
        self.assertIn("not actual LLM behavior", report["evidence_scope"])
        self.assertEqual(len(report["runs"]), 30)
        self.assertEqual(report["analysis"]["primary_effect"]["unit"], "whole_swarm_run")
        for run in report["runs"]:
            self.assertIn(run["outcomes"]["terminated_by"], ("publication", "step_budget"))

    def test_held_out_seed_replication_preserves_treatment_and_measurement(self):
        original = create_protocol(trials_per_arm=2, seed=4)
        replication = create_replication_protocol(original, new_seed=5)
        self.assertEqual(original["arms"], replication["arms"])
        self.assertEqual(original["environment"], replication["environment"])
        self.assertEqual(original["measurement"], replication["measurement"])
        self.assertEqual(replication["replicates_protocol_hash"], original["protocol_hash"])
        seeds_a = {run["environment_seed"] for run in randomize_runs(original)}
        seeds_b = {run["environment_seed"] for run in randomize_runs(replication)}
        self.assertFalse(seeds_a & seeds_b)
        with self.assertRaises(ValueError):
            create_replication_protocol(original, new_seed=4)

    def test_exact_null_test_and_ceiling_interval(self):
        comparison = compare_outcomes([1, 1, 1], [1, 1, 1], resamples=100)
        self.assertEqual(comparison["difference"], 0)
        self.assertEqual(comparison["p_two_sided"], 1)
        self.assertLess(comparison["ci95"][0], 0)
        self.assertGreater(comparison["ci95"][1], 0)
        self.assertEqual(comparison["test_samples"], 20)
        self.assertEqual(comparison["test_method"], "exact_conditional_randomization")
        self.assertEqual(comparison, compare_outcomes([1, 1, 1], [1, 1, 1], resamples=100))

    def test_effect_direction_not_hardcoded(self):
        positive = compare_outcomes([1, 1, 1], [0, 0, 0], resamples=100)
        negative = compare_outcomes([0, 0, 0], [1, 1, 1], resamples=100)
        self.assertEqual(positive["difference"], 1)
        self.assertEqual(negative["difference"], -1)
        self.assertAlmostEqual(positive["p_two_sided"], negative["p_two_sided"])
        self.assertAlmostEqual(positive["p_two_sided"], .1)


if __name__ == "__main__":
    unittest.main()
