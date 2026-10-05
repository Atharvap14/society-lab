import json
import math
import os
import unittest
from unittest.mock import patch

from swarm_lab.classifiers import (BackendProtocolError, BackendUnavailable, JevHTTPBackend, LayaBackend,
                                   LayaProcessBackend, TypedDecisionBackend, build_questions, evaluate_measurements)
from swarm_lab.discovery import DETECTOR_DEFINITIONS


class FakeDecision(TypedDecisionBackend):
    name = "test_fixture_transport"

    def __init__(self, response, **options):
        super().__init__(**options)
        self.response, self.calls = response, 0

    def _invoke(self, state, questions):
        self.calls += 1
        return self.response


DEFS = {name: DETECTOR_DEFINITIONS[name] for name in ("commitment", "completion_report", "blocker_report")}
MESSAGE = {"id": "m1", "content": "I will upload the artifact."}


class ClassifierTests(unittest.TestCase):
    def test_probabilities_thresholded_with_explicit_abstention(self):
        backend = FakeDecision({"model": "pinned-test", "answers": {"commitment": {"type": "noul", "noul": .8}, "completion_report": {"type": "noul", "noul": .2}, "blocker_report": {"type": "noul", "noul": .5}}})
        measurement = backend.measure(MESSAGE, DEFS)
        self.assertEqual(measurement["labels"], {"commitment": True, "completion_report": False, "blocker_report": None})
        self.assertEqual(measurement["probabilities"]["blocker_report"], .5)
        self.assertEqual(measurement["abstention_reasons"]["blocker_report"], "probability_inside_abstention_band")
        self.assertIn("not_established", measurement["calibration"])
        self.assertEqual(measurement["fallback"], "none")

    def test_failure_record_is_explicit_unknown_not_false_or_regex(self):
        backend=FakeDecision({"answers":{}})
        result=backend.failure_record(MESSAGE,DEFS,BackendUnavailable("No runtime"))
        self.assertEqual(result["status"],"operational_failure")
        self.assertTrue(all(label is None for label in result["labels"].values()))
        self.assertEqual(result["error"],"No runtime")
        self.assertEqual(result["fallback"],"none")
        self.assertEqual(backend.calls,0)

    def test_missing_malformed_and_provider_abstentions_are_not_false(self):
        backend = FakeDecision({"answers": {"commitment": {"type": "noul", "noul": float("nan")}, "completion_report": {"type": "noul", "noul": .99, "abstention": "abstained"}}})
        result = backend.measure(MESSAGE, DEFS)
        self.assertTrue(all(value is None for value in result["labels"].values()))
        self.assertIsNone(result["probabilities"]["commitment"])
        json.dumps(result, allow_nan=False)

    def test_unknown_labels_and_untyped_responses_rejected(self):
        for response in [{"answers": {"invented_behavior": {"type": "noul", "noul": 1}}}, {"prose": "yes"}]:
            with self.assertRaises(BackendProtocolError):
                FakeDecision(response).measure(MESSAGE, DEFS)
        for value in [True, "0.8", -1, 2, float("inf")]:
            result=FakeDecision({"answers": {"commitment": {"type": "noul", "noul": value}}}).measure(MESSAGE, {"commitment": DEFS["commitment"]})
            self.assertIsNone(result["labels"]["commitment"])

    def test_character_budget_abstains_before_provider_call(self):
        backend=FakeDecision({"answers": {}},max_chars=4)
        result=backend.measure(MESSAGE,DEFS)
        self.assertEqual(backend.calls,0)
        self.assertTrue(all(value is None for value in result["labels"].values()))
        self.assertIn("no_truncation",result["abstention_reasons"]["commitment"])

    def test_schema_records_neutral_label_variant_and_rejects_bad_definitions(self):
        normal=build_questions(DEFS)
        neutral=build_questions(DEFS,neutral_labels=True)
        self.assertNotIn("labels",normal["commitment"])
        self.assertEqual(neutral["commitment"]["labels"],{"true":"A","false":"B"})
        self.assertEqual(set(neutral["commitment"]["criteria"]),{"true","false"})
        for invalid in [{},{"bad identifier": DEFS["commitment"]},{"valid": {"description":""}}]:
            with self.assertRaises(ValueError):
                build_questions(invalid)

    def test_jev_wire_contract_and_no_key_leakage(self):
        captured={}
        def transport(payload,headers,timeout):
            captured.update(payload=payload,headers=headers)
            return {"model":"jev-test-version","model_version":"fixture-revision","answers": {name:{"type":"noul","noul":.95} for name in payload["questions"]},"usage":{"input_tokens":10,"output_tokens":2}}
        backend=JevHTTPBackend(api_key="provider-specific-test-key",transport=transport)
        measurement=backend.measure(MESSAGE,DEFS)
        self.assertEqual(set(captured["payload"]),{"state","model","questions"})
        self.assertEqual(captured["headers"]["Authorization"],"Bearer provider-specific-test-key")
        self.assertNotIn("provider-specific-test-key",json.dumps(measurement))
        self.assertEqual(measurement["returned_model_revision"],"fixture-revision")

    def test_missing_jev_key_and_inappropriate_credentials_fail_without_fallback(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaises(BackendUnavailable):
                JevHTTPBackend()
        with self.assertRaises(ValueError):
            JevHTTPBackend(api_key="sk-proj-example-only-not-a-real-key")
        with self.assertRaises(ValueError):
            JevHTTPBackend(endpoint="http://remote-provider.invalid/v1/systemone",api_key="provider-key")
        local=JevHTTPBackend(endpoint="http://127.0.0.1:9000/v1/systemone",allow_unauthenticated_local=True)
        self.assertIsNone(local._key)

    def test_laya_actual_router_signature_with_injected_fixture_router(self):
        class Router:
            def predict(self,state,questions,**options):
                self.seen=(state,questions,options)
                return {"model":"test-english","answers":{name:{"type":"noul","noul":.9} for name in questions},"routing":{"model":"english"}}
        router=Router()
        backend=LayaBackend(router=router)
        result=backend.measure(MESSAGE,DEFS)
        self.assertEqual(router.seen[2]["model"],"english")
        self.assertEqual(router.seen[2]["max_len"],512)
        self.assertTrue(result["labels"]["commitment"])
        self.assertEqual(result["device"],"cpu")
        unsupported=backend.measure({"id":"m2","content":"मुझे काम स्वीकार है"},DEFS)
        self.assertTrue(all(value is None for value in unsupported["labels"].values()))

    def test_laya_memory_gate_uses_available_physical_ram_and_surfaces_status(self):
        statuses=[]
        backend=LayaBackend(on_status=statuses.append)
        with patch("swarm_lab.classifiers.available_physical_memory_bytes",return_value=128 * 1024 ** 2):
            with self.assertRaisesRegex(BackendUnavailable,"free physical RAM"):
                backend.measure(MESSAGE,DEFS)
        self.assertIsNone(backend._router)
        self.assertEqual([status["phase"] for status in statuses],["checking_resources","unavailable"])
        self.assertEqual(statuses[-1]["available_physical_memory_bytes"],128 * 1024 ** 2)
        with patch("swarm_lab.classifiers.available_physical_memory_bytes",return_value=None):
            with self.assertRaisesRegex(BackendUnavailable,"could not be established"):
                backend.measure(MESSAGE,DEFS)

    def test_actual_tokenizer_limit_abstains_without_running_predict(self):
        class Tokenizer:
            def encode(self,text,**kwargs):
                return list(range(205))
        class Agent:
            tok=Tokenizer()
        class Router:
            def load(self,name):
                return Agent()
            def predict(self,*args,**kwargs):
                raise AssertionError("Oversized state must not reach inference")
        result=LayaBackend(router=Router()).measure(MESSAGE,DEFS)
        self.assertTrue(all(value is None for value in result["labels"].values()))
        self.assertEqual(result["input_state_tokens"],205)

    def test_laya_process_failure_streams_status_before_error(self):
        import sys
        import importlib.util
        if importlib.util.find_spec("laya") is not None:
            self.skipTest("Plain-interpreter worker failure check excludes an installed real model runtime")
        statuses=[]
        with LayaProcessBackend(sys.executable,on_status=statuses.append,timeout=10) as backend:
            # Real child protocol runs in the plain interpreter. It either lacks
            # runtime dependencies or refuses the resource gate before loading.
            with self.assertRaises(BackendUnavailable):
                backend.measure(MESSAGE,DEFS)
        self.assertTrue(statuses)
        self.assertEqual(statuses[0]["phase"],"checking_resources")
        self.assertIsNone(backend.process)

    def test_provider_truncation_abstains_and_nonfinite_usage_is_missing(self):
        response={"answers":{name:{"type":"noul","noul":.95} for name in DEFS},
                  "usage":{"truncated":True,"truncated_questions":["commitment"],"input_tokens":float("nan")}}
        measurement=FakeDecision(response).measure(MESSAGE,DEFS)
        self.assertIsNone(measurement["labels"]["commitment"])
        self.assertEqual(measurement["abstention_reasons"]["commitment"],"provider_input_truncated")
        self.assertTrue(measurement["labels"]["completion_report"])
        self.assertIsNone(measurement["usage"]["input_tokens"])
        json.dumps(measurement,allow_nan=False)

    def test_independent_gold_metrics_do_not_reward_abstentions(self):
        records=[{"message_id":"a","labels":{"commitment":True},"probabilities":{"commitment":.9}},
                 {"message_id":"b","labels":{"commitment":None},"probabilities":{"commitment":.5}},
                 {"message_id":"c","labels":{"commitment":False},"probabilities":{"commitment":.1}}]
        gold=[{"message_id":"a","labels":{"commitment":True}},{"message_id":"b","labels":{"commitment":True}},{"message_id":"c","labels":{"commitment":False}}]
        metrics=evaluate_measurements(records,gold)["per_observable"]["commitment"]
        self.assertEqual(metrics["precision"],1)
        self.assertEqual(metrics["selective_accuracy"],1)
        self.assertEqual(metrics["recall_including_abstentions"],.5)
        self.assertAlmostEqual(metrics["coverage"],2/3)
        self.assertAlmostEqual(metrics["brier_score"],.09)

    def test_bad_thresholds_and_unread_gold_rejected(self):
        for kwargs in [{"low":.9,"high":.2},{"low":float("nan")},{"high":float("inf")}]:
            with self.assertRaises(ValueError):
                FakeDecision({"answers":{}},**kwargs)
        with self.assertRaises(ValueError):
            evaluate_measurements([], [{"message_id":"imagined","labels":{"commitment":True}}])
        with self.assertRaises(ValueError):
            evaluate_measurements([{"message_id":"a","labels":{}}], [{"message_id":"a","labels":{}},{"message_id":"a","labels":{}}])


if __name__ == "__main__":
    unittest.main()
