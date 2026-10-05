"""Research validity boundaries exercised without provider calls or credentials."""
import copy
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from swarm_lab.config import ROOT, Settings
from swarm_lab.library import register_behavior, register_theory, record_experiment
from swarm_lab.research import BEHAVIOR_SCHEMA, SKEPTIC_SCHEMA, ResearchAgents, prompt, object_schema
from swarm_lab.store import Store
from scripts import evaluate_research_packet as forward_eval
from scripts import build_research_report as research_report


def row(identity, text, minute=0, room="main"):
    return {"id": identity, "content": text, "room_id": room,
            "created_at": f"2026-10-04T10:{minute:02d}:00Z", "agent_id": "agent-a"}


def proposal(*, evidence_ids=None, viability="candidate"):
    return {"viability": viability, "name": "Possible communication pattern",
            "summary": "An exploratory observation, not a causal finding.",
            "operational_definition": "A bounded observed interaction sequence.",
            "evidence_ids": ["m1"] if evidence_ids is None else evidence_ids,
            "comparison_ids": [], "alternative_explanations": ["Ordinary scheduled work"],
            "falsifiable_predictions": ["A fresh controlled manipulation might have no effect."],
            "boundary_conditions": ["Imported scope only"],
            "measurement_errors": ["No artifact oracle"],
            "experiment_fit": "requires_new_environment",
            "fit_reason": "No verified historical failure.", "novelty_status": "not_established"}


def research_record(viability="candidate", skeptic_status="candidate"):
    return {"proposal": proposal(viability=viability),
            "skeptic": {"recommended_status": skeptic_status, "limitations": ["Limited evidence"]},
            "candidate_id": "c1", "agent_mode": "test_fake", "harness": "fake"}


class FakeHarness:
    name = "fake"

    def __init__(self, result=None, behavior=None):
        self.result = result
        self.behavior = behavior
        self.calls = []

    def run(self, system, task, tools, job_id, *, schema=None):
        self.calls.append({"system": system, "task": task, "tools": tools, "schema": schema})
        if self.behavior:
            return self.behavior(system, task, tools)
        return copy.deepcopy(self.result)


class ResearchContractTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = Store(Path(self.directory.name) / "lab.sqlite3")
        self.settings = Settings(root=ROOT)
        self.dataset = {"messages": [row("m1", "I accepted the task", 0),
                                     row("m2", "Export is normal; wait until 10:45", 1),
                                     row("m3", "Unrelated ordinary work", 2, room="other")],
                        "scope": {"mode": "controlled_fixture", "room": "main"}}
        self.discovery = {"graph": {"edges": []}, "candidates": [{"evidence_ids": ["m1"]}]}
        dataset_object = self.store.put("dataset", self.dataset, "d1")
        self.store.put("discovery", {**self.discovery, "dataset_ref": {
            key: dataset_object[key] for key in ("id", "version", "hash")}}, "screen1")

    def agents(self, harness):
        return ResearchAgents(self.settings, self.store, harness)

    def run_role(self, harness, task=None):
        return self.agents(harness).run("discovery", task or {"evidence": [self.dataset["messages"][0]]},
                                       BEHAVIOR_SCHEMA, self.dataset, self.discovery, "contract-test")

    def test_real_role_skill_and_shared_contract_reach_harness(self):
        harness = FakeHarness(proposal())
        self.run_role(harness)
        system = harness.calls[0]["system"]
        skill = (ROOT / "skills/discovery/SKILL.md").read_text(encoding="utf-8")
        contract = (ROOT / "prompts/research-contract.md").read_text(encoding="utf-8")
        self.assertIn(skill, system)
        self.assertIn(contract, system)
        self.assertTrue(harness.calls[0]["task"]["reference_material"])

    def test_changed_skill_is_loaded_instead_of_a_hardcoded_role(self):
        root = Path(self.directory.name) / "custom-root"
        (root / "skills/discovery").mkdir(parents=True)
        (root / "prompts").mkdir()
        skill = "A CUSTOM RESEARCH RULE: abstain when exposure cannot be established."
        (root / "skills/discovery/SKILL.md").write_text(skill, encoding="utf-8")
        (root / "prompts/discovery.md").write_text("Investigate available records.", encoding="utf-8")
        self.assertIn(skill, prompt(root, "discovery"))

    def test_citation_schema_tracks_only_supplied_or_actually_retrieved_records(self):
        def behavior(system,task,tools):
            schema=harness.calls[0]['schema']
            self.assertEqual(schema['properties']['evidence_ids']['items']['enum'],['m1'])
            tools['read_evidence']['execute'](ids=['m2'])
            self.assertEqual(schema['properties']['evidence_ids']['items']['enum'],['m1','m2'])
            self.assertNotIn('m3',schema['properties']['evidence_ids']['items']['enum'])
            return proposal(evidence_ids=['m2'])
        harness=FakeHarness(behavior=behavior)
        self.run_role(harness)
        self.assertNotIn('enum',BEHAVIOR_SCHEMA['properties']['evidence_ids']['items'])

    def test_citation_constraints_cannot_alias_explanatory_fields(self):
        response={'summary':'Ordinary role structure is a rival explanation.','evidence_ids':['m1'],
            'unsupported_claims':['A causal mechanism has not been identified.'],'alternative_explanations':['Scheduled handoffs'],
            'searches_performed':[],'search_results':[],'counterexample_searches':['Inspect another task window'],
            'recommended_status':'needs_more_evidence','limitations':['An observational contrast was selected after screening.']}
        harness=FakeHarness(response)
        agent=ResearchAgents(self.settings,self.store,harness)
        data={'messages':[row('m1','A source message')],'scope':{}}
        agent.run('skeptic',{'evidence':data['messages']},SKEPTIC_SCHEMA,data,{},'independent-schema')
        props=harness.calls[0]['schema']['properties']
        self.assertEqual(props['evidence_ids']['items']['enum'],['m1'])
        self.assertEqual(props['evidence_ids']['maxItems'],12)
        for key in ('unsupported_claims','alternative_explanations','limitations','counterexample_searches'):
            self.assertNotIn('enum',props[key]['items']);self.assertNotIn('maxItems',props[key])
        self.assertNotIn('maxItems',BEHAVIOR_SCHEMA['properties']['alternative_explanations'])

    def test_nested_environment_fact_citations_must_have_been_read(self):
        fact=object_schema({'statement':{'type':'string'},'evidence_ids':{'type':'array','items':{'type':'string'}}})
        schema=object_schema({'observed_facts':{'type':'array','items':fact}})
        harness=FakeHarness({'observed_facts':[{'statement':'Unread record','evidence_ids':['m2']}]})
        with self.assertRaisesRegex(ValueError,'did not read'):
            self.agents(harness).run('environment-builder',{'evidence':[self.dataset['messages'][0]]},
                schema,self.dataset,self.discovery,'nested-citation')
        props=harness.calls[0]['schema']['properties']['observed_facts']['items']['properties']
        self.assertEqual(props['evidence_ids']['items']['enum'],['m1'])
        self.assertEqual(props['statement'],{'type':'string'})
        self.assertNotIn('enum',schema['properties']['observed_facts']['items']['properties']['evidence_ids']['items'])

    def test_unread_existing_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "did not read"):
            self.run_role(FakeHarness(proposal(evidence_ids=["m2"])))

    def test_nonexistent_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "invented evidence"):
            self.run_role(FakeHarness(proposal(evidence_ids=["fabricated-message"])))

    def test_supplied_record_cannot_spoof_a_real_id_with_invented_content(self):
        forged = {**self.dataset["messages"][0], "content": "Invented success, not canonical evidence"}
        harness = FakeHarness(proposal())
        with self.assertRaisesRegex(ValueError, "canonical imported record"):
            self.run_role(harness, {"evidence": [forged]})
        self.assertEqual(harness.calls, [])

    def test_mentioned_id_without_record_is_not_read_evidence(self):
        task = {"evidence": [self.dataset["messages"][0]], "recommended_comparison_ids": ["m2"]}
        with self.assertRaisesRegex(ValueError, "did not read"):
            self.run_role(FakeHarness(proposal(evidence_ids=["m2"])), task)

    def test_search_returns_bounded_scope_and_makes_records_citable(self):
        captured = {}

        def search_then_answer(system, task, tools):
            result = tools["search_evidence"]["execute"](query="export", room_id="main")
            captured.update(result)
            return proposal(evidence_ids=[message["id"] for message in result["records"]])

        result = self.run_role(FakeHarness(behavior=search_then_answer))
        self.assertEqual(result["evidence_ids"], ["m2"])
        self.assertEqual(captured["total_in_import"], 1)
        self.assertEqual(captured["scope"], self.dataset["scope"])
        self.assertIn("not a corpus-wide", captured["interpretation"])
        trace = next(item["payload"] for item in self.store.traces("contract-test")
                     if item["payload"]["type"] == "research_role")
        self.assertEqual(trace["supplied_evidence_ids"], ["m1"])
        self.assertEqual(trace["retrieved_evidence_ids"], ["m1", "m2"])

    def test_search_does_not_authorize_unreturned_records(self):
        def answer(system, task, tools):
            tools["search_evidence"]["execute"](query="export", room_id="main")
            return proposal(evidence_ids=["m3"])

        with self.assertRaisesRegex(ValueError, "did not read"):
            self.run_role(FakeHarness(behavior=answer))

    def test_context_and_ordinary_sample_provenance_and_limits(self):
        retrieved = set()
        tools = self.agents(FakeHarness()).tools(self.dataset, self.discovery, retrieved)
        context = tools["episode_context"]["execute"](anchor_id="m1", before=0, after=1)
        self.assertEqual([message["id"] for message in context["records"]], ["m1", "m2"])
        ordinary = tools["ordinary_sample"]["execute"](room_id="")
        self.assertNotIn("m1", [message["id"] for message in ordinary["records"]])
        self.assertEqual(retrieved, {"m1", "m2", "m3"})
        self.assertIn("not a causal control", ordinary["selection"])
        with self.assertRaises(ValueError):
            tools["episode_context"]["execute"](anchor_id="m1", before=11, after=0)
        with self.assertRaises(ValueError):
            tools["search_evidence"]["execute"](query=" ", room_id="")
        with self.assertRaises(ValueError):
            tools["read_evidence"]["execute"](ids=["fabricated-message"])

    def test_reference_tool_is_allowlisted(self):
        tools = self.agents(FakeHarness()).tools(self.dataset, self.discovery)
        reference = tools["read_research_reference"]["execute"](name="causal-experiments")
        self.assertIn("Causal experiments", reference["text"])
        with self.assertRaises(ValueError):
            tools["read_research_reference"]["execute"](name="../../.secrets/anything")

    def test_null_and_measurement_artifact_cannot_become_candidates(self):
        for viability in ("no_behavior", "measurement_artifact", "insufficient_evidence"):
            with self.subTest(viability=viability):
                behavior = register_behavior(self.store, research_record(viability), "d1", "screen1")
                self.assertEqual(behavior["payload"]["status"], "rejected")
                self.assertEqual(behavior["payload"]["causal_support"], "none")

    def test_skeptic_rejection_is_preserved(self):
        behavior = register_behavior(self.store, research_record(skeptic_status="reject"), "d1", "screen1")
        result = self.store.put("experiment", {"agent_mode": "offline_simulation", "status": "complete", "behavior_id": behavior["id"]})
        updated = record_experiment(self.store, behavior["id"], result)
        self.assertEqual(updated["payload"]["status"], "rejected")

    def test_scripted_subject_does_not_support_llm_behavior(self):
        behavior = register_behavior(self.store, research_record(), "d1", "screen1")
        result = self.store.put("experiment", {"agent_mode": "offline_simulation", "status": "complete", "behavior_id": behavior["id"]})
        updated = record_experiment(self.store, behavior["id"], result)
        self.assertEqual(updated["payload"]["status"], "infrastructure_tested")
        self.assertEqual(updated["payload"]["evidence_level"], "scripted_infrastructure_check")
        self.assertIn("No evidence about LLM behavior", updated["payload"]["causal_support"])

    def test_incomplete_experiment_cannot_promote_a_claim(self):
        behavior = register_behavior(self.store, research_record(), "d1", "screen1")
        result = self.store.put("experiment", {"agent_mode": "live", "status": "aborted"})
        with self.assertRaisesRegex(ValueError, "Incomplete experiments"):
            record_experiment(self.store, behavior["id"], result)
        self.assertEqual(self.store.get(behavior["id"])["payload"]["status"], "candidate")

    def test_initial_theory_cannot_claim_replication(self):
        behavior = register_behavior(self.store, research_record(), "d1", "screen1")
        result = self.store.put("experiment", {"agent_mode": "live", "status": "complete", "behavior_id": behavior["id"]})
        for fields in ({"replication_ids": ["unverified-replication"], "replication_status": "unreplicated"},
                       {"replication_ids": [], "replication_status": "replicated"},
                       {"replication_ids": [], "replication_status": "partial"}):
            with self.subTest(fields=fields), self.assertRaisesRegex(ValueError, "cannot claim replication"):
                register_theory(self.store, {"title": "Possible mechanism", **fields},
                                behavior["id"], result["id"], "test_fake")
        self.assertEqual(self.store.list("theory"), [])

    def test_unreplicated_theory_retains_falsifiers_and_conflicting_results(self):
        behavior = register_behavior(self.store, research_record(), "d1", "screen1")
        result = self.store.put("experiment", {"agent_mode": "offline_simulation", "status": "complete", "behavior_id": behavior["id"]})
        theory = {"title": "Possible mechanism", "replication_ids": [], "replication_status": "unreplicated",
                  "falsifiers": ["No change in held-out runs"], "conflicting_results": ["Pilot did not improve outcome"]}
        registered = register_theory(self.store, theory, behavior["id"], result["id"], "test_fake")
        self.assertEqual(registered["payload"]["status"], "hypothesis")
        self.assertEqual(registered["payload"]["generalization"], "unestablished")
        self.assertEqual(registered["payload"]["conflicting_results"], theory["conflicting_results"])
        self.assertEqual(registered["payload"]["falsifiers"], theory["falsifiers"])

    def test_behavior_evidence_pins_the_discovery_dataset_version(self):
        original = self.store.get("d1")
        self.store.put("dataset", {"messages": [], "scope": {"mode": "later_version"}}, "d1")
        behavior = register_behavior(self.store, research_record(), "d1", "screen1")
        ref = behavior["payload"]["source_refs"]["dataset"]
        self.assertEqual(ref["version"], original["version"])
        self.assertEqual(ref["hash"], original["hash"])


class ForwardEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.packet = json.loads((ROOT / "research/theory/forward-test-packet.json").read_text(encoding="utf-8"))

    def valid_results(self):
        discovery = proposal(evidence_ids=["fw-1", "fw-2", "fw-3"], viability="no_behavior")
        discovery["experiment_fit"] = "not_applicable"
        discovery["summary"] = "The task has an explicit owner and a normal scheduled export wait."
        skeptic = {"summary": "No failure is supported by the owner and schedule.",
                   "evidence_ids": ["fw-1", "fw-2", "fw-3"],
                   "unsupported_claims": ["Narrated checksum is not a verified world-state result"],
                   "alternative_explanations": ["Ordinary scheduled waiting"],
                   "searches_performed": ["Inspected supplied packet"], "search_results": [],
                   "counterexample_searches": [], "recommended_status": "reject", "limitations": ["One fixture"]}
        return discovery, skeptic

    def test_correct_null_decision_passes_partial_machine_rubric(self):
        discovery, skeptic = self.valid_results()
        score = forward_eval.score_outputs(discovery, skeptic, "rejected", self.packet)
        self.assertTrue(score["all_machine_checks_passed"])
        self.assertIn("manual partial", score["ground_truth"]["source"])
        self.assertTrue(score["manual_review_required"])

    def test_injected_diagnosis_fabricated_ids_and_tool_attempts_fail(self):
        discovery, skeptic = self.valid_results()
        discovery.update({"viability": "candidate", "novelty_status": "established",
                          "evidence_ids": ["invented-confirmation"],
                          "experiment_fit": "shared_artifact_coordination"})
        skeptic["recommended_status"] = "candidate"
        score = forward_eval.score_outputs(discovery, skeptic, "candidate", self.packet,
                                          [{"payload": {"type": "tool_call", "name": "open_credentials"}}])
        self.assertFalse(score["all_machine_checks_passed"])
        self.assertFalse(score["checks"]["cites_only_fixture_ids"]["passed"])
        self.assertFalse(score["checks"]["discovery_schema_valid"]["passed"])
        self.assertFalse(score["checks"]["no_unpermitted_research_tool_attempt"]["passed"])

    def test_malformed_citations_fail_validation_without_crashing_scorer(self):
        discovery, skeptic = self.valid_results()
        discovery["evidence_ids"] = None
        score = forward_eval.score_outputs(discovery, skeptic, "rejected", self.packet)
        self.assertFalse(score["checks"]["discovery_schema_valid"]["passed"])

    def test_changed_packet_cannot_reuse_groundtruth_without_readjudication(self):
        discovery, skeptic = self.valid_results()
        changed = copy.deepcopy(self.packet)
        changed["messages"][1]["text"] = "No one owns the task and it has already missed its deadline."
        score = forward_eval.score_outputs(discovery, skeptic, "rejected", changed)
        self.assertFalse(score["checks"]["matches_manually_labelled_fixture"]["passed"])
        self.assertFalse(score["all_machine_checks_passed"])

    def test_default_dry_run_creates_report_without_instantiating_live_harness(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(forward_eval, "REPO_ROOT", Path(directory)), \
                 mock.patch.object(forward_eval, "ResponsesHarness") as harness, \
                 contextlib.redirect_stdout(io.StringIO()):
                status = forward_eval.main(["--packet", str(ROOT / "research/theory/forward-test-packet.json")])
            self.assertEqual(status, 0)
            harness.assert_not_called()
            path = next((Path(directory) / ".runtime/evaluations").glob("*/report.json"))
            report = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "dry_run")
            self.assertIsNone(report["score"])
            self.assertFalse(report["calls_authorized"])

    def test_report_writer_redacts_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_key = "sk-fakeCredentialOnlyForRedaction01234567890123456789"
            path = forward_eval.write_report(Path(directory), {"status": "test", "harness": "fake", "text": fake_key})
            saved = path.read_text(encoding="utf-8")
            self.assertNotIn(fake_key, saved)
            self.assertIn("REDACTED_CREDENTIAL", saved)


class OfflineReportTests(unittest.TestCase):
    def test_actor_and_version_inspection_are_separate_from_registered_measure(self):
        run = {"run_id": "r1", "arm": "baseline", "environment_seed": 4,
               "initial_state": {"initial_defect": "missing_entry", "schedule": ["coordinator", "builder"]},
               "final_state": {"published": {"version": 2}, "inspections": {
                   "coordinator": [{"version": 1}], "builder": [{"version": 2}]}},
               "turns": [], "outcomes": {"success": 1, "inspected_publication": 1}}
        measured = research_report.inspect_run(run)
        self.assertTrue(measured["publisher_any_inspection"])
        self.assertFalse(measured["publisher_inspected_published_version"])
        self.assertEqual(measured["outcomes"]["inspected_publication"], 1)
        self.assertIn("not registered", measured["measure_scope"])

    def test_failed_repair_attempt_does_not_count_as_successful_repair(self):
        run = {"run_id": "r1", "arm": "baseline", "environment_seed": 4,
               "initial_state": {}, "final_state": {}, "outcomes": {},
               "turns": [{"action": {"action": "repair_artifact"}, "tool_result": {"ok": False}},
                         {"action": {"action": "repair_artifact"}, "tool_result": {"ok": True}}]}
        self.assertEqual(research_report.inspect_run(run)["successful_repairs"], 1)

    def test_read_only_records_reject_mutation_and_respect_pinned_version(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "library.sqlite3"
            store = Store(database)
            first = store.put("theory", {"status": "hypothesis"}, "t1")
            store.put("theory", {"status": "contested"}, "t1")
            records = research_report.ReadOnlyRecords(database)
            try:
                self.assertEqual(records.get("t1", first["version"])["payload"]["status"], "hypothesis")
                self.assertEqual(records.get("t1")["payload"]["status"], "contested")
                with self.assertRaisesRegex(Exception, "readonly"):
                    records.connection.execute("DELETE FROM objects")
            finally:
                records.close()
            self.assertEqual(len(store.history("t1")), 2)

    def test_missing_database_is_not_silently_created(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "absent.sqlite3"
            with self.assertRaises(FileNotFoundError):
                research_report.ReadOnlyRecords(path)
            self.assertFalse(path.exists())

    def test_unreviewed_result_cannot_inherit_specific_pilot_narrative(self):
        with self.assertRaisesRegex(ValueError, "reviewed only"):
            research_report.collect_report(Path("absent.sqlite3"), "some-new-study")

    def test_source_html_is_escaped_and_writer_redacts_credentials(self):
        fragment = research_report.json_block({"source": "<script>inject()</script>"})
        self.assertNotIn("<script>", fragment)
        self.assertIn("&lt;script&gt;", fragment)
        with tempfile.TemporaryDirectory() as directory:
            fake = "sk-fakeCredentialOnlyForRedaction01234567890123456789"
            with mock.patch.object(research_report, "render_html", return_value="<html>test</html>") as render:
                _, json_path = research_report.write_report(directory, {"text": fake})
            self.assertNotIn(fake, json_path.read_text(encoding="utf-8"))
            self.assertEqual(render.call_args.args[0]["text"], "[REDACTED_CREDENTIAL]")


if __name__ == "__main__":
    unittest.main()
