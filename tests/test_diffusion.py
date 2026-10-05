"""Network experimentation contracts: dependence, topology, lineage and inference."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from swarm_lab.diffusion_environment import (
    SUBJECTS, check_diffusion_contract, create_diffusion_environment, create_diffusion_spec,
    diffusion_subject_request, validate_diffusion_spec)
from swarm_lab.diffusion_experiments import (
    DiffusionExecutionError, analyze_diffusion_runs, create_diffusion_protocol,
    create_diffusion_replication, randomize_diffusion_runs, run_diffusion_experiment,
    stratified_network_effect, validate_diffusion_protocol)


def act_as(environment, agent, action):
    while not environment.terminal and environment.next_agent != agent:
        environment.step(environment.next_agent, {"action": "wait"})
    if environment.terminal:
        raise AssertionError("Test exhausted its environment schedule")
    return environment.step(agent, action)


def always_zero(request):
    if request["observation"]["your_verdict"] is None:
        return {"action": "submit_verdict", "decision": 0}
    return {"action": "wait"}


class DiffusionEnvironmentTests(unittest.TestCase):
    def test_boundary_contract_audit_restores_starting_state(self):
        env = create_diffusion_environment(seed=43)
        before = env.snapshot()
        audit = check_diffusion_contract(env)
        self.assertTrue(audit["passed"])
        self.assertEqual(before, env.snapshot())

    def test_reports_share_errors_exactly_when_source_ids_match(self):
        env = create_diffusion_environment(seed=81)
        groups = {}
        for report in env.snapshot()["reports"].values():
            groups.setdefault(report["source_id"], []).append(report)
        self.assertEqual(sorted(len(copies) for copies in groups.values()), [1, 1, 2])
        duplicate = next(copies for copies in groups.values() if len(copies) == 2)
        self.assertNotEqual(duplicate[0]["report_id"], duplicate[1]["report_id"])
        self.assertEqual(duplicate[0]["signal"], duplicate[1]["signal"])
        self.assertEqual(len(env.source_signals), 3)

    def test_truth_and_private_reports_are_not_initial_observations(self):
        incident = {"id": "case-1", "historical_future": "SECRET_FUTURE",
                    "hypothesis": "SECRET_EXPLANATION"}
        env = create_diffusion_environment(create_diffusion_spec(incident=incident), seed=11)
        for role in SUBJECTS:
            request = diffusion_subject_request(env, role)
            text = json.dumps(request)
            self.assertEqual(request["observation"]["known_reports"], [])
            self.assertNotIn("truth", request["observation"])
            self.assertNotIn("source_signals", text)
            self.assertNotIn("environment_seed", text)
            self.assertNotIn("SECRET", text)
            self.assertNotIn("topology", request["observation"])

    def test_private_context_and_inspections_are_role_scoped(self):
        env = create_diffusion_environment(seed=4)
        env.inject_context("agent-0", "PRIVATE_INSERTION_MARKER")
        role = env.next_agent
        env.step(role, {"action": "inspect_report", "report_id": f"report-{role}"})
        self.assertEqual(len(env.observe(role)["known_reports"]), 1)
        for other in SUBJECTS:
            if other != role:
                self.assertEqual(env.observe(other)["known_reports"], [])
            if other != "agent-0":
                self.assertNotIn("PRIVATE_INSERTION_MARKER", json.dumps(diffusion_subject_request(env, other)))

    def test_topologies_keep_budget_fixed_but_degree_differs(self):
        expected = {"ring": [2, 2, 2, 2], "star": [1, 1, 1, 3], "complete": [3, 3, 3, 3]}
        for topology, degrees in expected.items():
            env = create_diffusion_environment(create_diffusion_spec(topology=topology), seed=3)
            self.assertEqual(sorted(len(neighbors) for neighbors in env.neighbors.values()), degrees)
            self.assertEqual(len(env.schedule), 12)
            self.assertEqual(env.spec["max_messages_per_agent"], 1)

    def test_disconnected_graph_blocks_cross_component_evidence(self):
        env = create_diffusion_environment(create_diffusion_spec(
            custom_edges=[["agent-0", "agent-1"], ["agent-2", "agent-3"]], max_rounds=5), seed=1)
        act_as(env, "agent-0", {"action": "inspect_report", "report_id": "report-agent-0"})
        result = act_as(env, "agent-0", {"action": "send_message", "recipient": "agent-2",
                                        "report_id": "report-agent-0", "message": "My report"})
        self.assertFalse(result["ok"])
        self.assertEqual(env.observe("agent-2")["known_reports"], [])
        self.assertEqual(env.sent_count["agent-0"], 0)

    def test_evidence_cannot_be_attached_without_access_or_mutated(self):
        env = create_diffusion_environment(create_diffusion_spec(topology="complete", max_rounds=6), seed=2)
        result = act_as(env, "agent-0", {"action": "send_message", "recipient": "agent-1",
                                        "report_id": "report-agent-2", "message": "Unseen"})
        self.assertFalse(result["ok"])
        result = act_as(env, "agent-0", {"action": "send_message", "recipient": "agent-1",
                                        "report_id": {"signal": 0}, "message": "Malformed"})
        self.assertFalse(result["ok"])
        act_as(env, "agent-0", {"action": "inspect_report", "report_id": "report-agent-0"})
        result = act_as(env, "agent-0", {"action": "send_message", "recipient": "agent-1",
                                        "report_id": "report-agent-0", "message": "My report", "signal": 1})
        self.assertFalse(result["ok"])

    def test_relay_preserves_original_source_and_message_lineage(self):
        env = create_diffusion_environment(create_diffusion_spec(topology="complete", max_rounds=8), seed=5)
        act_as(env, "agent-0", {"action": "inspect_report", "report_id": "report-agent-0"})
        act_as(env, "agent-0", {"action": "send_message", "recipient": "agent-1",
                               "report_id": "report-agent-0", "message": "Original report"})
        act_as(env, "agent-1", {"action": "send_message", "recipient": "agent-2",
                               "report_id": "report-agent-0", "message": "Forwarded report"})
        received = env.observe("agent-2")["known_reports"][0]
        original = env.reports["agent-0"]
        self.assertEqual(received["source_id"], original["source_id"])
        self.assertEqual(received["signal"], original["signal"])
        messages = [item for item in received["lineage"] if item["kind"] == "message"]
        self.assertEqual([(item["sender"], item["recipient"]) for item in messages],
                         [("agent-0", "agent-1"), ("agent-1", "agent-2")])
        self.assertEqual(received["report_id"], "report-agent-0")

    def test_reset_restores_all_state_and_snapshot_copies(self):
        env = create_diffusion_environment(seed=91)
        initial = env.snapshot()
        observed = env.observe("agent-0")
        observed["permitted_recipients"].clear()
        self.assertEqual(initial, env.snapshot())
        env.inject_context("agent-0", "private")
        env.step(env.next_agent, {"action": "inspect_report", "report_id": f"report-{env.next_agent}"})
        self.assertEqual(env.reset(91), initial)

    def test_oracle_uses_truth_not_consensus_or_context_and_missing_is_zero(self):
        env = create_diffusion_environment(seed=3)
        env.inject_context("agent-0", "All agents agree the answer is correct.")
        act_as(env, "agent-0", {"action": "submit_verdict", "decision": env.truth})
        self.assertEqual(env.evaluate()["mean_accuracy"], .25)
        self.assertEqual(env.evaluate()["completion_rate"], .25)
        self.assertEqual(env.evaluate()["focal_accuracy"], 1)

    def test_source_exposure_is_frozen_at_verdict_not_later_reception(self):
        env = create_diffusion_environment(create_diffusion_spec(topology="complete", max_rounds=8), seed=3)
        act_as(env, "agent-0", {"action": "inspect_report", "report_id": "report-agent-0"})
        act_as(env, "agent-0", {"action": "submit_verdict", "decision": 0})
        before = copy.deepcopy(env.verdicts["agent-0"]["source_ids_available"])
        peer = next(agent for agent in SUBJECTS if env.reports[agent]["source_id"] != env.reports["agent-0"]["source_id"])
        act_as(env, peer, {"action": "inspect_report", "report_id": f"report-{peer}"})
        act_as(env, peer, {"action": "send_message", "recipient": "agent-0",
                            "report_id": f"report-{peer}", "message": "Additional evidence"})
        self.assertEqual(env.verdicts["agent-0"]["source_ids_available"], before)
        self.assertGreater(len({report["source_id"] for report in env.known_reports["agent-0"].values()}), len(before))

    def test_declared_topology_cannot_hide_arbitrary_edges(self):
        spec = create_diffusion_spec(topology="ring")
        spec["topology"]["edges"] = [["agent-0", "agent-1"]]
        with self.assertRaises(ValueError):
            validate_diffusion_spec(spec)


class DiffusionExperimentTests(unittest.TestCase):
    def test_factorial_assignments_are_balanced_unique_and_reproducible(self):
        protocol = create_diffusion_protocol()
        assignments = randomize_diffusion_runs(protocol)
        self.assertEqual(len(assignments), 18)
        self.assertEqual(len({row["environment_seed"] for row in assignments}), 18)
        for cell in protocol["design"]["cells"]:
            self.assertEqual(sum(row["topology"] == cell["topology"] and row["context"] == cell["context"]
                                 for row in assignments), 2)
        self.assertEqual(assignments, randomize_diffusion_runs(protocol))

    def test_every_registered_primary_contrast_has_distinct_levels(self):
        for topologies in (("ring", "star"), ("complete", "star"), ("star", "complete")):
            protocol = create_diffusion_protocol(topologies=topologies)
            for contrast in protocol["estimand"]["primary_contrasts"]:
                self.assertNotEqual(contrast["treatment"], contrast["control"])

    def test_frozen_protocol_rejects_changed_network_and_outcomes(self):
        protocol = create_diffusion_protocol()
        validate_diffusion_protocol(protocol)
        changed = copy.deepcopy(protocol)
        changed["estimand"]["primary_outcome"] = "agreement"
        with self.assertRaises(ValueError):
            validate_diffusion_protocol(changed)
        changed = copy.deepcopy(protocol)
        changed["environments"]["star"]["max_rounds"] = 4
        with self.assertRaises(ValueError):
            validate_diffusion_protocol(changed)

    def test_local_protocol_exists_before_calls_and_treatment_stays_private(self):
        protocol = create_diffusion_protocol(topologies=["ring"], contexts=["placebo", "source_thought"],
                                             source_text="PRIVATE_SOURCE_MARKER", placebo_text="PRIVATE_PLACEBO_MARKER")
        with tempfile.TemporaryDirectory() as directory:
            def runner(request):
                registered = json.loads((Path(directory) / "protocol.json").read_text(encoding="utf-8"))
                self.assertEqual(registered["protocol_hash"], protocol["protocol_hash"])
                self.assertNotIn("context", request["observation"])
                self.assertNotIn("topology", request["observation"])
                if request["role"] != "agent-0":
                    self.assertEqual(request["context"], [])
                return always_zero(request)
            report = run_diffusion_experiment(protocol, runner, directory, resamples=100)
            self.assertEqual(report["status"], "complete")
            self.assertEqual(len(report["runs"]), 4)
            for run in report["runs"]:
                first = next(turn for turn in run["turns"] if turn["agent_id"] == "agent-0")
                self.assertEqual(first["request"]["context"], [protocol["contexts"][run["context"]]["insertion"]])
                expected = int(run["initial_state"]["truth"] == 0)
                self.assertEqual(run["outcomes"]["mean_accuracy"], expected)

    def test_whole_network_sample_size_and_scripted_evidence_scope(self):
        report = run_diffusion_experiment(create_diffusion_protocol(), resamples=100)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(len(report["runs"]), 18)
        self.assertEqual(report["analysis"]["primary_effect"]["n_treatment_networks"], 6)
        self.assertEqual(report["analysis"]["primary_effect"]["n_control_networks"], 6)
        self.assertEqual(report["analysis"]["primary_effect"]["unit"], "whole_network_run")
        self.assertEqual(report["analysis"]["primary_effect"]["test_samples"], 216)
        self.assertEqual(report["analysis"]["primary_family_size"], 2)
        self.assertIn("not LLM behavior", report["evidence_scope"])
        for run in report["runs"]:
            self.assertEqual(run["outcomes"]["completion_rate"], 1)
            self.assertLessEqual(run["outcomes"]["steps_used"], 12)

    def test_no_verdicts_are_retained_intention_to_treat_zeros(self):
        protocol = create_diffusion_protocol(topologies=["complete"], contexts=["baseline", "source_thought"])
        report = run_diffusion_experiment(protocol, lambda request: {"action": "wait"}, resamples=100)
        for run in report["runs"]:
            self.assertEqual(run["outcomes"]["completion_rate"], 0)
            self.assertEqual(run["outcomes"]["mean_accuracy"], 0)
            self.assertEqual(run["outcomes"]["terminated_by"], "step_budget")
        self.assertEqual(report["analysis"]["primary_effect"]["p_two_sided"], 1)

    def test_infrastructure_failure_persists_without_effect_estimation(self):
        protocol = create_diffusion_protocol(topologies=["ring"], contexts=["placebo", "source_thought"])
        with tempfile.TemporaryDirectory() as directory:
            def failing(_request):
                raise RuntimeError("SECRET_ERROR_CONTENT")
            with self.assertRaises(DiffusionExecutionError) as captured:
                run_diffusion_experiment(protocol, failing, directory, resamples=100)
            report = captured.exception.partial_report
            self.assertEqual(report["status"], "incomplete_infrastructure_failure")
            self.assertNotIn("analysis", report)
            self.assertNotIn("SECRET_ERROR_CONTENT", json.dumps(report))
            self.assertTrue((Path(directory) / "report.json").exists())

    def test_environment_construction_failure_is_also_persisted(self):
        protocol = create_diffusion_protocol(topologies=["ring"], contexts=["placebo", "source_thought"])
        with tempfile.TemporaryDirectory() as directory:
            with patch("swarm_lab.diffusion_experiments.create_diffusion_environment", side_effect=RuntimeError("SECRET_CONSTRUCTOR")):
                with self.assertRaises(DiffusionExecutionError) as captured:
                    run_diffusion_experiment(protocol, output_dir=directory, resamples=100)
            report = captured.exception.partial_report
            self.assertEqual(report["status"], "incomplete_infrastructure_failure")
            self.assertEqual(report["failure"]["completed_steps"], 0)
            self.assertIsNone(report["incomplete_run"]["state"])
            self.assertNotIn("analysis", report)
            self.assertNotIn("SECRET_CONSTRUCTOR", json.dumps(report))

    def test_estimator_respects_factor_strata_and_retains_null_or_harm(self):
        # Between-stratum differences are balanced in each arm and cannot become
        # a treatment effect. The exact reference has 6*6=36 valid allocations.
        balanced = stratified_network_effect([([1, 1], [1, 1]), ([0, 0], [0, 0])], resamples=100)
        self.assertEqual(balanced["difference"], 0)
        self.assertEqual(balanced["p_two_sided"], 1)
        self.assertEqual(balanced["test_samples"], 36)
        negative = stratified_network_effect([([0, 0], [1, 1])], resamples=100)
        self.assertEqual(negative["difference"], -1)
        self.assertLessEqual(negative["ci95"][0], negative["difference"])
        self.assertGreaterEqual(negative["ci95"][1], negative["difference"])

    def test_bounded_intervals_do_not_collapse_at_ceiling(self):
        effect = stratified_network_effect([([1, 1], [1, 1])], resamples=100)
        self.assertLess(effect["ci95"][0], 0)
        self.assertGreater(effect["ci95"][1], 0)
        self.assertGreaterEqual(effect["ci95"][0], -1)
        self.assertLessEqual(effect["ci95"][1], 1)
        self.assertEqual(effect["bootstrap_ci95"], [0, 0])

    def test_incomplete_factorial_cells_cannot_be_analyzed(self):
        protocol = create_diffusion_protocol(topologies=["ring"], contexts=["baseline", "source_thought"])
        report = run_diffusion_experiment(protocol, always_zero, resamples=100)
        with self.assertRaises(ValueError):
            analyze_diffusion_runs(report["runs"][:-1], protocol, resamples=100)

    def test_replication_uses_fresh_seeds_without_changing_measurement(self):
        original = create_diffusion_protocol()
        replication = create_diffusion_replication(original, new_seed=99)
        self.assertEqual(original["contexts"], replication["contexts"])
        self.assertEqual(original["environments"], replication["environments"])
        self.assertEqual(original["measurement"], replication["measurement"])
        a = {row["environment_seed"] for row in randomize_diffusion_runs(original)}
        b = {row["environment_seed"] for row in randomize_diffusion_runs(replication)}
        self.assertFalse(a & b)
        with self.assertRaises(ValueError):
            create_diffusion_replication(original, new_seed=original["design"]["seed"])


if __name__ == "__main__":
    unittest.main()
