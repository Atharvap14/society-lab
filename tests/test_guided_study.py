"""Guided host contracts using isolated stores and fixture-only LLM transport.

The HTTP outputs below are unit-test fixtures, never evidence of model behavior.
The actual frozen environment, Responses adapter, call ledger and replay run.
"""
import copy
import io
import json
import pathlib
import tempfile
import threading
import concurrent.futures
import unittest
from unittest import mock

from swarm_lab import guided_study
from swarm_lab.config import Settings
from swarm_lab.experiments import _seal_protocol
from swarm_lab.pipeline import Lab
from swarm_lab.store import fingerprint
from swarm_lab.claim_audit import make_claim


def ref(record):
    return {key: record[key] for key in ("id", "version", "hash")}


def raw(body):
    return json.dumps(body, allow_nan=False).encode("utf-8")


class FixtureHTTP:
    """Exercises real HTTP serialization and action validation without a network."""
    def __init__(self, fail_at=None):
        self.payloads = []
        self.fail_at = fail_at

    def __call__(self, request, timeout):
        payload = json.loads(request.data)
        self.payloads.append(payload)
        if len(self.payloads) == self.fail_at:
            raise OSError("Fixture transport failure")
        user = json.loads(payload["input"].split("\n", 1)[1])
        observation = user["observation"]
        role = observation["agent_id"]
        artifact = observation["artifact"]["id"]
        if role == "builder":
            action = {"action": "repair_artifact", "artifact_id": artifact,
                      "contents": observation["required_contents"]}
        elif role == "coordinator" and observation["your_action_history"]:
            action = {"action": "publish_artifact", "artifact_id": artifact}
        else:
            action = {"action": "inspect_artifact", "artifact_id": artifact}
        response = {"id": "unit-fixture-response-" + str(len(self.payloads)),
                    "model": payload["model"], "usage": {"input_tokens": 1, "output_tokens": 1},
                    "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(action)}]}]}
        return io.BytesIO(json.dumps(response).encode("utf-8"))


class GuidedStudyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lab = Lab(Settings(root=pathlib.Path(self.tmp.name), model="unit-fixture-model", max_calls=100))
        self.worker_packets = []
        self.worker_patch = mock.patch("swarm_lab.research.ResearchAgents.run", self.worker)
        self.worker_patch.start()
        self.addCleanup(self.worker_patch.stop)
        dataset = self.lab.store.put("dataset", {
            "messages": [{"id": "history-1", "agent_id": "historical-agent", "speaker_id": "historical-agent",
                          "speaker_type": "agent", "agent_name": "Historical agent", "room_id": "historical-room",
                          "timestamp": "2025-04-22T18:00:00Z", "created_at": "2025-04-22T18:00:00Z",
                          "content": "HISTORICAL-FUTURE-ONLY", "source": {"file": "fixture.jsonl", "line": 1}}],
            "agents": [{"id": "historical-agent", "name": "Historical agent"}], "scope": {}, "provenance": {"kind": "test_fixture"}})
        self.brief = self.lab.store.put("observation_brief", {
            "source_refs": {"dataset_ref": ref(dataset)}, "signals": [{"code": "candidate_reference"}],
            "scope": "Unit fixture, not research evidence"})

    def worker(self, role, packet, schema, dataset, discovery, job_id):
        self.worker_packets.append((role, copy.deepcopy(packet)))
        if role == "environment-builder":
            return {"completion_claim": "The delivery manifest is finished and ready to publish.",
                    "abstraction_rationale": "A bounded test fixture of the host compiler.",
                    "omitted_capabilities": ["Historical tool reconstruction"]}
        if role == "evaluator":
            if getattr(self, "evaluator_error", False):
                raise RuntimeError("Unit fixture evaluator failure")
            facts = packet["fact_packet"]
            claims = [make_claim(facts, identity, fact["value"], statement="Unit fixture statement; unverified prose.")
                      for identity, fact in facts["facts"].items()]
            if getattr(self, "evaluator_mismatch", False):
                claims[0]["scope"] = "unit_fixture_wrong_scope"
            return {"claims": claims}
        self.assertEqual(role, "causal-methodologist")
        return {"hypothesis": "A supplied note may change publication validity.",
                "primary_outcome_rationale": "The environment compares the published manifest with its objective requirements.",
                "mechanism": "Proposed, not identified.", "identification_assumptions": ["Independent team resets"],
                "confound_checks": ["Fixed world and action budget"], "falsifiers": ["No reproducible improvement"],
                "transport_limitations": ["This fixture is not model behavior or historical evidence."]}

    def plan(self, **changes):
        body = {"source_ref": ref(self.brief), "signal_code": "candidate_reference",
                "question": "Does a version-check note change correct publication?",
                "family": "shared_artifact_coordination", "objective": "correct_published_file",
                "control_text": "CONTROL-CONTEXT-TOKEN: continue the assigned task.",
                "treatment_text": "TREATMENT-CONTEXT-TOKEN: check the file before publication.",
                "trials_per_arm": 2, "seed": 37, "max_rounds": 2, "valid_probability": 0}
        body.update(changes)
        return guided_study.create_plan(self.lab, raw(body))

    def simulator(self):
        plan = self.plan()
        simulator = guided_study.create_simulator(self.lab, raw({"plan_ref": plan["plan_ref"]}))
        return plan, simulator

    def execute(self, simulator, http=None):
        http = http or FixtureHTTP()
        with mock.patch.object(Settings, "api_key", return_value="unit-test-key"), \
             mock.patch("swarm_lab.harness.urllib.request.urlopen", http):
            return guided_study.execute_plan(self.lab, raw({"simulator_ref": simulator["simulator_ref"]})), http

    def test_actual_engine_live_transport_fixture_has_frozen_world_and_fresh_replay(self):
        plan, simulator = self.simulator()
        registration = self.lab.store.get(simulator["simulator"]["protocol_ref"]["id"], simulator["simulator"]["protocol_ref"]["version"])
        spec = registration["payload"]["protocol"]["environment"]
        self.assertEqual(spec, simulator["simulator"]["environment"])
        self.assertEqual(spec["initial_state_distribution"]["valid_probability"], 0)
        self.assertEqual(spec["max_rounds"], 2)
        self.assertTrue(simulator["simulator"]["boundary_checks"]["passed"])
        executed, http = self.execute(simulator)
        result = self.lab.store.get(executed["result_ref"]["id"], executed["result_ref"]["version"])
        proof = self.lab.store.get(executed["verification_ref"]["id"], executed["verification_ref"]["version"])
        claims = self.lab.store.get(executed["claims_ref"]["id"], executed["claims_ref"]["version"])
        self.assertEqual(result["payload"]["agent_mode"], "live")
        self.assertEqual(result["payload"]["status"], "complete")
        self.assertEqual(result["payload"]["protocol"]["environment"], spec)
        self.assertEqual(len(result["payload"]["runs"]), 6)
        self.assertTrue(proof["payload"]["passed"])
        self.assertTrue(claims["payload"]["audit"]["all_executable_claims_supported"])
        self.assertEqual(executed["paid_calls"], len(http.payloads))
        self.assertEqual(self.lab.store.usage()["calls"], len(http.payloads))
        serialized = json.dumps(http.payloads)
        self.assertNotIn("HISTORICAL-FUTURE-ONLY", serialized)
        self.assertNotIn('"evidence_thought"', serialized)
        self.assertTrue(any(t["action"]["action"] == "repair_artifact" and t["tool_result"]["ok"] for r in result["payload"]["runs"] for t in r["turns"]))
        reused, second_http = self.execute(simulator)
        self.assertTrue(reused["reused"])
        self.assertEqual(reused["execution_ref"], executed["execution_ref"])
        self.assertEqual(second_http.payloads, [])

    def test_exact_old_protocol_pin_is_used_even_when_newer_version_exists(self):
        _, simulator = self.simulator()
        pinned = simulator["simulator"]["protocol_ref"]
        previous = self.lab.store.get(pinned["id"], pinned["version"])
        newer = copy.deepcopy(previous["payload"])
        newer["protocol"]["subject_backend"]["model"] = "different-model"
        newer["protocol"] = _seal_protocol(newer["protocol"])
        newer["frozen_hash"] = fingerprint(newer["protocol"])
        latest = self.lab.store.put("protocol", newer, pinned["id"])
        self.assertGreater(latest["version"], pinned["version"])
        executed, http = self.execute(simulator)
        result = self.lab.store.get(executed["result_ref"]["id"], executed["result_ref"]["version"])
        self.assertEqual(result["payload"]["registered_hash"], previous["payload"]["frozen_hash"])
        self.assertTrue(self.lab.store.get(executed["verification_ref"]["id"])["payload"]["passed"])
        self.assertGreater(len(http.payloads), 0)

    def test_builder_packet_omits_unneeded_allocation_and_insertion_details(self):
        self.simulator()
        packet = next(packet for role, packet in self.worker_packets if role == "environment-builder")
        reviewed = packet["reviewed_plan"]
        self.assertNotIn("seed", reviewed)
        self.assertNotIn("control_text", reviewed)
        self.assertNotIn("treatment_text", reviewed)
        self.assertNotIn("conditions", reviewed)
        self.assertNotIn("CONTROL-CONTEXT-TOKEN", json.dumps(packet))
        self.assertNotIn("TREATMENT-CONTEXT-TOKEN", json.dumps(packet))

    def test_failed_transport_retains_partial_result_and_prevents_retry(self):
        _, simulator = self.simulator()
        http = FixtureHTTP(fail_at=2)
        with self.assertRaisesRegex(RuntimeError, "no effects estimated"):
            self.execute(simulator, http)
        partial = self.lab.store.list("experiment")
        self.assertEqual(len(partial), 1)
        self.assertNotEqual(partial[0]["payload"]["status"], "complete")
        with self.lab.store.connect() as connection:
            execution = connection.execute("SELECT * FROM guided_executions").fetchone()
        self.assertEqual(execution["status"], "failed")
        job = self.lab.store.get_job(execution["job_id"])
        self.assertEqual(job["status"], "failed")
        self.assertIn(partial[0]["id"], json.dumps(job["payload"]))
        self.assertEqual(job["payload"]["artifact_directory"], partial[0]["payload"]["artifact_directory"])
        with self.assertRaisesRegex(ValueError, "running or failed"):
            self.execute(simulator)
        self.assertEqual(self.lab.store.usage()["calls"], 2)

    def test_post_execution_evaluator_failure_retains_completed_subject_and_proof_refs(self):
        _, simulator = self.simulator()
        self.evaluator_error = True
        with self.assertRaisesRegex(RuntimeError, "Unit fixture evaluator failure"):
            self.execute(simulator)
        result = self.lab.store.list("experiment")[0]
        proof = self.lab.store.list("verification")[0]
        self.assertEqual(result["payload"]["status"], "complete")
        self.assertTrue(proof["payload"]["passed"])
        with self.lab.store.connect() as connection:
            execution = connection.execute("SELECT * FROM guided_executions").fetchone()
        self.assertEqual(execution["status"], "failed")
        job = self.lab.store.get_job(execution["job_id"])
        retained = json.dumps(job["payload"])
        self.assertIn(result["id"], retained)
        self.assertIn(result["hash"], retained)
        self.assertIn(proof["id"], retained)
        self.assertEqual(self.lab.store.list("guided_result"), [])
        with self.assertRaisesRegex(ValueError, "running or failed"):
            self.execute(simulator)

    def test_failed_replay_and_inconsistent_claims_withhold_completed_journey(self):
        _, simulator = self.simulator()
        def false_proof(result_id):
            result = self.lab.store.get(result_id)
            return self.lab.store.put("verification", {"passed": False, "result_ref": ref(result),
                                                       "scope": "Forced unit fixture integrity refusal"})
        with mock.patch.object(Lab, "audit", side_effect=false_proof):
            with self.assertRaisesRegex((RuntimeError, ValueError), "replay|verification|audit"):
                self.execute(simulator)
        self.assertFalse(any(role == "evaluator" for role, _ in self.worker_packets))
        self.assertEqual(self.lab.store.list("guided_result"), [])
        _, second = self.simulator()
        self.evaluator_mismatch = True
        with self.assertRaisesRegex((RuntimeError, ValueError), "claim|fact"):
            self.execute(second)
        self.assertEqual(self.lab.store.list("guided_result"), [])
        claim = self.lab.store.list("claim_audit")[0]
        self.assertFalse(claim["payload"]["audit"]["all_executable_claims_supported"])
        with self.lab.store.connect() as connection:
            execution = connection.execute("SELECT * FROM guided_executions WHERE simulator_id=?", (second["simulator_ref"]["id"],)).fetchone()
        self.assertIn(claim["id"], json.dumps(self.lab.store.get_job(execution["job_id"])["payload"]))

    def test_job_setup_failures_close_construction_and_execution_claims(self):
        plan = self.plan()
        original = self.lab.store.job
        def fail_running(job_id, status, payload):
            if status == "running":
                raise RuntimeError("Fixture setup failure")
            return original(job_id, status, payload)
        with mock.patch.object(self.lab.store, "job", fail_running):
            with self.assertRaisesRegex(RuntimeError, "Fixture setup failure"):
                guided_study.create_simulator(self.lab, raw({"plan_ref": plan["plan_ref"]}))
        with self.lab.store.connect() as connection:
            construction = connection.execute("SELECT * FROM guided_constructions").fetchone()
        self.assertEqual(construction["status"], "failed")
        self.assertEqual(self.lab.store.get_job(construction["job_id"])["status"], "failed")
        self.assertEqual(self.worker_packets, [])
        _, simulator = self.simulator()
        with mock.patch.object(self.lab.store, "job", fail_running):
            with self.assertRaisesRegex(RuntimeError, "Fixture setup failure"):
                guided_study.execute_plan(self.lab, raw({"simulator_ref": simulator["simulator_ref"]}))
        with self.lab.store.connect() as connection:
            execution = connection.execute("SELECT * FROM guided_executions").fetchone()
        self.assertEqual(execution["status"], "failed")
        self.assertEqual(self.lab.store.get_job(execution["job_id"])["status"], "failed")
        self.assertEqual(self.lab.store.usage()["calls"], 0)

    def test_budget_guard_uses_reserved_calls_before_subject_harness_creation(self):
        _, simulator = self.simulator()
        self.lab.settings.max_calls = 36
        self.lab.store.reserve_call(36)
        with mock.patch.object(self.lab, "harness") as harness:
            with self.assertRaisesRegex(ValueError, "remaining cap"):
                guided_study.execute_plan(self.lab, raw({"simulator_ref": simulator["simulator_ref"]}))
        harness.assert_not_called()
        self.assertEqual(self.lab.store.usage()["calls"], 1)
        self.assertEqual(self.lab.store.usage()["completed"], 0)

    def test_stale_source_pin_and_bad_request_fail_before_builder_or_execution(self):
        with self.assertRaises(ValueError):
            self.plan(source_ref={**ref(self.brief), "hash": "0" * 64})
        with self.assertRaises(ValueError):
            self.plan(trials_per_arm=True)
        with self.assertRaises(ValueError):
            self.plan(valid_probability=True)
        with self.assertRaises(ValueError):
            guided_study.create_plan(self.lab, b'{"source_ref":null,"source_ref":null}')
        self.assertEqual(self.worker_packets, [])
        self.assertEqual(self.lab.store.list("guided_plan"), [])
        self.assertEqual(self.lab.store.usage()["calls"], 0)

    def test_concurrent_construction_and_execution_have_one_claim_without_extra_calls(self):
        plan = self.plan()
        entered, release = threading.Event(), threading.Event()
        original_worker = self.worker
        def blocked_worker(role, *args):
            if role == "environment-builder":
                entered.set()
                if not release.wait(10):
                    raise RuntimeError("Unit fixture barrier timed out")
            return original_worker(role, *args)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            with mock.patch("swarm_lab.research.ResearchAgents.run", mock.Mock(side_effect=blocked_worker)):
                first = executor.submit(guided_study.create_simulator, self.lab, raw({"plan_ref": plan["plan_ref"]}))
                self.assertTrue(entered.wait(5))
                try:
                    with self.assertRaisesRegex(ValueError, "construction request"):
                        guided_study.create_simulator(self.lab, raw({"plan_ref": plan["plan_ref"]}))
                finally:
                    release.set()
                simulator = first.result(timeout=10)
        self.assertEqual(len(self.lab.store.list("guided_simulator")), 1)
        self.assertEqual(len(self.lab.store.list("protocol")), 1)
        self.assertEqual(sum(role == "environment-builder" for role, _ in self.worker_packets), 1)
        entered.clear()
        release.clear()
        http = FixtureHTTP()
        def blocked_http(request, timeout):
            if not http.payloads:
                entered.set()
                if not release.wait(10):
                    raise RuntimeError("Unit fixture barrier timed out")
            return http(request, timeout)
        with mock.patch.object(Settings, "api_key", return_value="unit-test-key"), \
             mock.patch("swarm_lab.harness.urllib.request.urlopen", blocked_http), \
             concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            first = executor.submit(guided_study.execute_plan, self.lab, raw({"simulator_ref": simulator["simulator_ref"]}))
            self.assertTrue(entered.wait(5))
            try:
                with self.assertRaisesRegex(ValueError, "running or failed"):
                    guided_study.execute_plan(self.lab, raw({"simulator_ref": simulator["simulator_ref"]}))
            finally:
                release.set()
            executed = first.result(timeout=10)
        self.assertEqual(executed["status"], "completed")
        self.assertEqual(len(self.lab.store.list("guided_result")), 1)
        self.assertEqual(len(self.lab.store.list("experiment")), 1)
        self.assertEqual(self.lab.store.usage()["calls"], len(http.payloads))


if __name__ == "__main__":
    unittest.main()
