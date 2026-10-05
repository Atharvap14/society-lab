"""End-to-end scientific integration contracts without remote or paid calls."""
import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from swarm_lab.config import ROOT, Settings
from swarm_lab.experiments import (ExperimentExecutionError, create_protocol,
                                   validate_protocol)
from swarm_lab.harness import ResponsesHarness
from swarm_lab.library import record_experiment, register_theory, verify_protocol
from swarm_lab.pipeline import Lab
from swarm_lab.store import fingerprint


FIXTURE = ROOT / "examples" / "coordination_fixture"


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings = Settings(root=Path(self.directory.name))
        self.lab = Lab(self.settings)

    def test_store_connections_close_at_context_exit(self):
        with self.lab.store.connect() as connection:
            self.assertEqual(connection.execute("SELECT 1").fetchone()[0], 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

    def prepare_behavior(self):
        data = self.lab.ingest(FIXTURE, limit=100)
        discovery = self.lab.observe(data["id"])
        candidates = discovery["payload"]["candidates"]
        chosen = next(candidate for candidate in candidates
                      if candidate["kind"] == "completion_report_cluster")
        behavior = self.lab.investigate(discovery["id"], candidate_ids=[chosen["id"]])[0]
        return behavior

    def register_live_protocol_without_calls(self, behavior, *, backend=None):
        backend = backend or {
            "harness": "responses", "model": self.settings.model,
            "generation": {"max_output_tokens": 600, "temperature": "provider_default",
                           "sampling_seed": "not_set"},
        }
        protocol = create_protocol(
            {"id": behavior["id"], "source_refs": behavior["payload"]["evidence_ids"]},
            trials_per_arm=2, max_rounds=3, subject_backend=backend)
        return self.lab.store.put("protocol", {
            "protocol": protocol, "frozen_hash": fingerprint(protocol),
            "status": "registered", "behavior_id": behavior["id"], "agent_mode": "live",
            "subject_adapter_hash": hashlib.sha256((ROOT / 'swarm_lab' / 'harness.py').read_bytes()).hexdigest(),
        })

    def test_offline_full_workflow_preserves_evidence_scope_and_versions(self):
        workflow = self.lab.workflow(source=FIXTURE, limit=100, trials_per_arm=2,
                                     job_id="offline-integration")
        outputs = workflow["outputs"]
        self.assertTrue({"dataset", "discovery", "behavior", "protocol", "experiment", "theory"}.issubset(outputs))
        experiment = self.lab.store.get(outputs["experiment"])["payload"]
        self.assertEqual(experiment["status"], "complete")
        self.assertEqual(experiment["agent_mode"], "offline_simulation")
        self.assertEqual(experiment["backend"]["mode"], "scripted_offline_smoke_test")
        self.assertIn("not actual LLM behavior", experiment["evidence_scope"])
        self.assertEqual(len(experiment["runs"]), 6)
        behavior = self.lab.store.get(outputs["behavior"])["payload"]
        self.assertEqual(behavior["status"], "infrastructure_tested")
        self.assertEqual(behavior["novelty_status"], "not_established")
        self.assertIn("No evidence about LLM behavior", behavior["causal_support"])
        self.assertIn(outputs["experiment"], behavior["experiment_ids"])
        self.assertIn(outputs["theory"], behavior["theory_ids"])
        theory = self.lab.store.get(outputs["theory"])["payload"]
        self.assertEqual(theory["status"], "hypothesis")
        self.assertEqual(theory["replication_status"], "unreplicated")
        self.assertEqual(theory["generalization"], "unestablished")
        history = self.lab.store.history(outputs["behavior"])
        self.assertGreaterEqual(len(history), 3)
        self.assertEqual(history[0]["payload"]["status"], "candidate")
        self.assertEqual(history[0]["payload"]["experiment_ids"], [])
        self.assertEqual(self.lab.store.jobs()[0]["status"], "completed")
        self.assertEqual(self.lab.store.usage()["calls"], 0)
        source = self.lab.store.get(outputs["dataset"])["payload"]
        self.assertEqual(source["provenance"]["revision"], "fixture_or_user_source")
        self.assertEqual(len(source["messages"]), 8)
        self.assertTrue(all(row["source"]["line"] > 0 for row in source["messages"]))

    def test_canonical_execution_hash_and_frozen_protocol_are_preserved(self):
        behavior = self.prepare_behavior()
        registration = self.lab.design(behavior["id"], trials_per_arm=2)
        frozen = copy.deepcopy(registration["payload"]["protocol"])
        result = self.lab.experiment(registration["id"], job_id="hash-integration")
        payload = result["payload"]
        canonical = json.loads((Path(payload["artifact_directory"]) / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["canonical_execution_report_hash"], canonical["report_hash"])
        expected_hash = canonical.pop("report_hash")
        digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":"),
                                          ensure_ascii=False).encode("utf-8")).hexdigest()
        self.assertEqual(expected_hash, digest)
        self.assertNotIn("report_hash", payload)
        self.assertEqual(payload["protocol"], frozen)
        self.assertEqual(payload["protocol_hash"], frozen["protocol_hash"])
        self.assertEqual(verify_protocol(self.lab.store.get(registration["id"])), frozen)
        validate_protocol(frozen)

    def test_modified_registered_protocol_is_rejected_before_any_call(self):
        behavior = self.prepare_behavior()
        registration = self.lab.design(behavior["id"], trials_per_arm=2)
        changed = copy.deepcopy(registration["payload"])
        changed["protocol"]["arms"]["evidence_thought"]["insertion"] = "Post-registration change"
        self.lab.store.put("protocol", changed, registration["id"])
        with patch.object(self.lab, "harness") as backend:
            with self.assertRaises(ValueError):
                self.lab.experiment(registration["id"], live=True)
            backend.assert_not_called()

    def test_subject_model_mismatch_is_rejected_before_backend(self):
        behavior = self.prepare_behavior()
        registration = self.lab.design(behavior["id"], trials_per_arm=2)
        with patch.object(self.lab, "harness") as backend:
            with self.assertRaises(ValueError):
                self.lab.experiment(registration["id"], live=True)
            backend.assert_not_called()

    def test_subject_harness_mismatch_is_rejected_even_when_model_matches(self):
        behavior = self.prepare_behavior()
        registration = self.register_live_protocol_without_calls(behavior, backend={
            "harness": "codex", "model": self.settings.model,
            "generation": {"max_output_tokens": 600, "temperature": "provider_default",
                           "sampling_seed": "not_set"},
        })
        with patch.object(self.lab, "harness") as backend:
            with self.assertRaises(ValueError):
                self.lab.experiment(registration["id"], live=True)
            backend.assert_not_called()

    def test_subject_generation_mismatch_is_rejected_before_backend(self):
        behavior = self.prepare_behavior()
        registration = self.register_live_protocol_without_calls(behavior, backend={
            "harness": "responses", "model": self.settings.model,
            "generation": {"max_output_tokens": 50, "temperature": "provider_default",
                           "sampling_seed": "not_set"},
        })
        with patch.object(self.lab, "harness") as backend:
            with self.assertRaises(ValueError):
                self.lab.experiment(registration["id"], live=True)
            backend.assert_not_called()

    def test_environment_fit_and_rejected_behavior_are_gates(self):
        behavior = self.prepare_behavior()
        incompatible = copy.deepcopy(behavior["payload"])
        incompatible["experiment_fit"] = "requires_new_environment"
        self.lab.store.put("behavior", incompatible, behavior["id"])
        with self.assertRaises(ValueError):
            self.lab.design(behavior["id"], trials_per_arm=2)
        override = self.lab.design(behavior["id"], trials_per_arm=2, allow_abstract_pilot=True)
        self.assertTrue(override["payload"]["abstract_pilot_override"])
        self.assertEqual(override["payload"]["historical_mechanism_support"], "unestablished")
        incompatible["status"] = "rejected"
        self.lab.store.put("behavior", incompatible, behavior["id"])
        with self.assertRaises(ValueError):
            self.lab.design(behavior["id"], trials_per_arm=2, allow_abstract_pilot=True)

    def test_live_builder_output_is_validated_before_protocol_seal(self):
        behavior = self.prepare_behavior()
        built = {"max_rounds": 4, "valid_probability": .6,
                 "completion_claim": "The shared manifest is ready for delivery.",
                 "abstraction_rationale": "Executable handoff task tests acceptance of a status claim.",
                 "missing_capabilities": ["Original browser world is not reproduced."]}
        charter = {"hypothesis": "Reminder changes correctness.",
                   "primary_outcome_rationale": "Code checks actual manifest contents.",
                   "mechanism": "Inspection before consequential publication.",
                   "identification_assumptions": ["Independent swarm reset."],
                   "confound_checks": ["Assignment hidden from subjects."],
                   "falsifiers": ["Null or harmful result."],
                   "transport_limitations": ["Synthetic setting only."]}
        agent = Mock()
        agent.run.side_effect = [built, charter]
        with patch("swarm_lab.pipeline.ResearchAgents", return_value=agent):
            registered = self.lab.design(behavior["id"], trials_per_arm=2, live=True)
        protocol = registered["payload"]["protocol"]
        validate_protocol(protocol)
        self.assertEqual(protocol["environment"]["max_rounds"], 4)
        self.assertEqual(protocol["environment"]["initial_state_distribution"]["valid_probability"], .6)
        self.assertEqual(protocol["environment"]["initial_state_distribution"]["completion_claim"], built["completion_claim"])
        self.assertEqual(registered["payload"]["environment_builder"], built)
        self.assertEqual([call.args[0] for call in agent.run.call_args_list],
                         ["environment-builder", "causal-methodologist"])
        self.assertEqual(protocol["subject_backend"]["model"], self.settings.model)
        self.assertEqual(self.lab.store.usage()["calls"], 0)

    def test_transport_failure_preserves_artifact_without_promoting_behavior(self):
        behavior = self.prepare_behavior()
        registration = self.register_live_protocol_without_calls(behavior)
        backend = Mock()
        backend.subject.side_effect = RuntimeError("Simulated unavailable service")
        with patch.object(self.lab, "harness", return_value=backend):
            with self.assertRaises(ExperimentExecutionError):
                self.lab.experiment(registration["id"], live=True, job_id="failed-integration")
        state = self.lab.store.get(behavior["id"])["payload"]
        self.assertEqual(state["status"], "candidate")
        self.assertEqual(state["experiment_ids"], [])
        report_path = self.settings.runtime / "runs" / "failed-integration" / "report.json"
        self.assertTrue(report_path.exists())
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "incomplete_infrastructure_failure")
        self.assertNotIn("analysis", report)
        traces = self.lab.store.traces("failed-integration")
        self.assertTrue(any(row["payload"].get("type") == "experiment_failure" for row in traces))

    def test_library_does_not_promote_an_incomplete_live_result(self):
        behavior = self.prepare_behavior()
        incomplete = self.lab.store.put("experiment", {
            "status": "incomplete_infrastructure_failure", "agent_mode": "live",
            "behavior_id": behavior["id"], "failure": {"error_type": "RuntimeError"},
        })
        with self.assertRaises(ValueError):
            record_experiment(self.lab.store, behavior["id"], incomplete)
        after = self.lab.store.get(behavior["id"])["payload"]
        self.assertEqual(after["status"], "candidate")
        self.assertEqual(after["causal_support"], "none")
        self.assertEqual(after["experiment_ids"], [])

    def test_malformed_subject_output_counts_as_behavioral_outcome(self):
        behavior = self.prepare_behavior()
        registration = self.register_live_protocol_without_calls(behavior)
        backend = ResponsesHarness(self.settings, self.lab.store)
        invalid_response = {"output": [{"type": "message", "content": [
            {"type": "output_text", "text": "not a JSON action"}]}]}
        with patch.object(backend, "request", return_value=invalid_response):
            with patch.object(self.lab, "harness", return_value=backend):
                result = self.lab.experiment(registration["id"], live=True, job_id="invalid-output-integration")
        payload = result["payload"]
        self.assertEqual(payload["status"], "complete")
        self.assertEqual(len(payload["runs"]), 6)
        for run in payload["runs"]:
            self.assertEqual(run["outcomes"]["success"], 0)
            self.assertEqual(run["outcomes"]["invalid_actions"], 9)
            self.assertEqual(run["outcomes"]["terminated_by"], "step_budget")
        self.assertEqual(payload["analysis"]["primary_effect"]["difference"], 0)
        self.assertEqual(self.lab.store.get(behavior["id"])["payload"]["status"], "pilot_tested")

    def test_initial_theory_cannot_invent_replication(self):
        behavior = self.prepare_behavior()
        registration = self.lab.design(behavior["id"], trials_per_arm=2)
        result = self.lab.experiment(registration["id"])
        with self.assertRaises(ValueError):
            register_theory(self.lab.store, {"title": "Claim", "replication_status": "replicated",
                                            "replication_ids": ["invented-replication"]},
                            behavior["id"], result["id"], "live")


if __name__ == "__main__":
    unittest.main()
