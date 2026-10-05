"""Offline report provenance, descriptive counts, and preserved-edition checks."""
import copy
import contextlib
import hashlib
import inspect
import io
from html.parser import HTMLParser
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from scripts.build_research_report import (ReadOnlyRecords, GRAPH_REVIEW_PAIRS,
    collect_graph_reviews, collect_report, complementary_quantities, render_html,
    write_report, read_pinned, collect_resource_workflow, execution_inventory,
    render_addition_sources, MEASUREMENT_PINS, RESOURCE_PINS, SELECTED_LEAD_PIN)
from scripts.build_research_report import (collect_temporal_paths, collect_timed_resource_workflow,
    render_temporal_addition, render_timed_resource_addition, TEMPORAL_PINS, TIMED_RESOURCE_PINS, main)
from scripts.build_research_report import (collect_source_lineage, render_source_lineage_addition, SOURCE_LINEAGE_PINS)
from swarm_lab.complementary_experiments import create_complementary_protocol, run_complementary_experiment
from swarm_lab.store import fingerprint
from swarm_lab.timed_resource_experiments import create_timed_resource_protocol, run_timed_resource_experiment, OFFLINE_BACKEND


ROOT = Path(__file__).resolve().parents[1]


def fixture_record(identity, kind, payload):
    return {"id": identity, "kind": kind, "version": 1, "created": "2026-10-04T00:00:00Z",
            "payload": payload, "hash": fingerprint(payload)}


class FakeRecords:
    def __init__(self):
        dataset = fixture_record("dataset-test", "dataset", {"messages": [{"id": "m1", "content": "waiting for a shared tool"}, {"id": "m2", "content": "ordinary comparison"}]})
        discovery = fixture_record("discovery-test", "discovery", {"graph_search": {"leads": [{"id": "lead-test", "interpretation": "exploratory"}]}})
        refs = {kind: {k:obj[k] for k in ("id", "version", "hash")} for kind,obj in (("dataset",dataset),("discovery",discovery))}
        proposal = {"summary": "A candidate", "candidate_id": "lead-test", "source_refs": refs,
                    "evidence_ids": ["m1"], "comparison_ids": ["m2"]}
        old = fixture_record("behavior-old", "behavior", {**copy.deepcopy(proposal), "skeptic": {"evidence_ids": ["m1"], "limitations": ["m1"]}, "research_quality_status": "superseded_schema_defect_review"})
        new = fixture_record("behavior-new", "behavior", {**copy.deepcopy(proposal), "skeptic": {"evidence_ids": ["m1"], "limitations": ["Observed waiting does not prove actual inactivity"]}, "research_attempt_id": "research_attempt-test", "supersedes_review_behavior_id": old["id"], "research_quality_status": "corrected_schema_review"})
        attempt = fixture_record("research_attempt-test", "research_attempt", {"resume_job_id": "job-test", "recovery_limitation": "Legacy original input unavailable"})
        self.objects = {obj["id"]:obj for obj in (dataset,discovery,old,new,attempt)}

    def get(self,identity,version=None):
        obj = self.objects[identity]
        if version is not None and version != obj["version"]:
            raise KeyError((identity,version))
        return copy.deepcopy(obj)

    def trace_summary(self,job_id):
        return {"job_id":job_id,"recorded_trace_types":{},"scope":"Counts only"}


def timed_fixture(directory):
    from swarm_lab.timed_resource_claims import build_timed_resource_fact_ledger, default_timed_resource_fact_ids, audit_timed_resource_claims
    from swarm_lab.claim_audit import select_fact_packet, make_claim
    protocol = create_timed_resource_protocol(max_rounds=2, resamples=100)
    raw = run_timed_resource_experiment(protocol, output_dir=directory)
    registration = fixture_record("timed-protocol-test", "timed_resource_protocol",
        {"protocol": protocol, "frozen_hash": fingerprint(protocol), "behavior_id": None})
    ref = {k: registration[k] for k in ("id", "version", "hash")}
    result_payload = {k: copy.deepcopy(v) for k, v in raw.items() if k != "report_hash"}
    result_payload.update(protocol_id=registration["id"], protocol_ref=ref,
        registered_hash=registration["payload"]["frozen_hash"], behavior_id=None,
        agent_mode="offline_simulation", model=OFFLINE_BACKEND["model"], artifact_directory=str(directory),
        canonical_execution_report_hash=raw["report_hash"])
    result = fixture_record("timed-result-test", "timed_resource_experiment", result_payload)
    verification = fixture_record("timed-verification-test", "verification",
        {"result_kind": "timed_resource_experiment", "result_ref": {k: result[k] for k in ("id", "version", "hash")},
         "passed": True, "model_calls": 0})
    result_ref = {k: result[k] for k in ("id", "version", "hash")}
    ledger = build_timed_resource_fact_ledger(raw, report_id=result["id"], source_ref=result_ref, source_object=result,
        replay_check=lambda candidate: {"passed": fingerprint(candidate) == fingerprint(raw), "model_calls": 0,
                                       "result_ref": result_ref, "report_hash": raw["report_hash"], "protocol_hash": raw["protocol_hash"]})
    packet = select_fact_packet(ledger, default_timed_resource_fact_ids(ledger, max_facts=24), max_facts=24)
    claims = [make_claim(ledger, identity, fact["value"]) for identity, fact in packet["facts"].items()]
    claim_record = fixture_record("timed-claims-test", "claim_audit", {
        "experiment_id": result["id"], "result_kind": result["kind"], "result_ref": result_ref,
        "verification_ref": {k: verification[k] for k in ("id", "version", "hash")},
        "canonical_execution_report_hash": raw["report_hash"], "fact_packet": packet, "claims": claims,
        "audit": audit_timed_resource_claims(ledger, claims), "quantitative_facts_available": ledger["quantitative_facts_available"]})
    objects = {"protocol": registration, "result": result, "verification": verification, "claims": claim_record}
    records = FakeRecords()
    records.timed_ledger = ledger
    records.objects.update({obj["id"]: obj for obj in objects.values()})
    pins = {name: {k: obj[k] for k in ("id", "version", "kind", "hash")} for name, obj in objects.items()}
    return records, pins, raw


def reseal_timed_claims(records, pins):
    """Make a changed fixture an honestly pinned record, not a payload-hash attack."""
    record = records.objects[pins["claims"]["id"]]
    record["hash"] = fingerprint(record["payload"])
    pins["claims"]["hash"] = record["hash"]


def source_lineage_fixture(directory):
    from tests.test_source_workflow_independent import fixture
    from swarm_lab.source_workflow import normalize_source_plan, derive_source_links
    _, sources, rows, markers = fixture(directory)
    payload = derive_source_links(normalize_source_plan(sources))
    audit = fixture_record("source_link_audit-report-test", "source_link_audit", payload)
    verification = fixture_record("verification-source-report-test", "verification", {
        "audit_ref": {k: audit[k] for k in ("id", "version", "hash")}, "result_kind": audit["kind"],
        "passed": True, "model_calls": 0, "filesystem_reread_attempted": True,
        "filesystem_reread_completed": True, "reason": "reproduced"})
    records = FakeRecords()
    objects = {"audit": audit, "verification": verification}
    records.objects.update({obj["id"]: obj for obj in objects.values()})
    pins = {name: {k: obj[k] for k in ("id", "version", "kind", "hash")} for name, obj in objects.items()}
    return records, pins, sources, rows, markers


def reseal_source_audit(records, pins):
    record = records.objects[pins["audit"]["id"]]
    record["hash"] = fingerprint(record["payload"])
    pins["audit"]["hash"] = record["hash"]
    verification = records.objects[pins["verification"]["id"]]
    verification["payload"]["audit_ref"] = {k: record[k] for k in ("id", "version", "hash")}
    verification["hash"] = fingerprint(verification["payload"])
    pins["verification"]["hash"] = verification["hash"]


class ReportSourceTests(unittest.TestCase):
    def test_review_repair_does_not_create_new_proposal_or_source(self):
        fake = FakeRecords()
        before = copy.deepcopy(fake.objects)
        group = collect_graph_reviews(fake, (("behavior-new","behavior-old"),))
        entry = group["entries"][0]
        self.assertTrue(entry["unchanged_proposal_and_sources"])
        self.assertEqual({x["id"] for x in entry["source_evidence"]}, {"m1","m2"})
        self.assertEqual(entry["superseded"]["quality_status"], "superseded_schema_defect_review")
        self.assertIn("not proof of tool-performed search", entry["scope"])
        self.assertIn("original input archive", group["scope"])
        self.assertEqual(fake.objects,before)

    def test_repair_cannot_silently_change_proposal(self):
        fake = FakeRecords()
        fake.objects["behavior-new"]["payload"]["summary"] = "A different claim"
        with self.assertRaisesRegex(ValueError,"proposal or source refs changed"):
            collect_graph_reviews(fake, (("behavior-new","behavior-old"),))

    def test_source_hash_and_citation_fail_closed(self):
        fake = FakeRecords()
        fake.objects["behavior-new"]["payload"]["source_refs"]["dataset"]["hash"] = "0"*64
        with self.assertRaisesRegex(ValueError,"source version/hash"):
            collect_graph_reviews(fake, (("behavior-new","behavior-old"),))
        fake = FakeRecords()
        fake.objects["behavior-new"]["payload"]["evidence_ids"].append("unread-fabricated")
        with self.assertRaisesRegex(ValueError,"evidence is missing"):
            collect_graph_reviews(fake, (("behavior-new","behavior-old"),))

    def test_record_connection_rejects_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"fixture.sqlite"
            conn=sqlite3.connect(path)
            conn.execute("CREATE TABLE protected (value INTEGER)")
            conn.execute("INSERT INTO protected VALUES (1)")
            conn.commit();conn.close()
            reader=ReadOnlyRecords(path)
            try:
                with self.assertRaises(sqlite3.OperationalError):
                    reader.connection.execute("UPDATE protected SET value=2")
                self.assertEqual(reader.connection.execute("SELECT value FROM protected").fetchone()[0],1)
            finally:
                reader.close()

    def test_previous_report_edition_is_preserved_before_replacement(self):
        with tempfile.TemporaryDirectory() as folder:
            old={"generated_at":"2026-10-03T20:00:00Z","audit_scope":"Earlier scope","result":{"id":"old"}}
            old_json=json.dumps(old).encode()
            old_html=b"<html>Original interpretation retained</html>"
            path=Path(folder)
            (path/"research-report.json").write_bytes(old_json)
            (path/"research-report.html").write_bytes(old_html)
            current={"generated_at":"2026-10-04T02:00:00Z","addition_notice":{"complementary_pilot":"new"}}
            with patch("scripts.build_research_report.render_html",return_value="<html>Explicit extended edition</html>"):
                _,new_json=write_report(path,current)
            saved=json.loads(new_json.read_text())
            previous=saved["regeneration"]["previous_generation"]
            self.assertEqual(Path(previous["preserved_json"]["path"]).read_bytes(),old_json)
            self.assertEqual(Path(previous["preserved_html"]["path"]).read_bytes(),old_html)
            self.assertEqual(previous["generated_at"],old["generated_at"])
            self.assertEqual(previous["preserved_json"]["sha256"],hashlib.sha256(old_json).hexdigest())
            self.assertNotIn("regeneration",current)

    def test_action_counts_do_not_treat_multicast_as_multiple_dispatches(self):
        raw=run_complementary_experiment(create_complementary_protocol(),resamples=100)
        q=complementary_quantities(raw)
        self.assertEqual(q["valid_submissions"],32)
        self.assertEqual(q["correct_submissions"],32)
        self.assertEqual(q["absent_submissions"],0)
        self.assertGreater(q["neighbor_multicast_actions"],0)
        self.assertGreater(q["recipient_deliveries"],q["message_dispatches"])
        self.assertTrue(q["all_subject_requests_advertise_neighbor_multicast"])
        self.assertIn("do not measure mental knowledge",q["scope"])

    def test_added_source_pin_rejects_valid_identity_with_mutated_payload(self):
        fake=FakeRecords()
        record=fake.objects["dataset-test"]
        pin={k:record[k] for k in ("id","version","kind","hash")}
        self.assertEqual(read_pinned(fake,pin),record)
        fake.objects[record["id"]]["payload"]["messages"][0]["content"]="changed source"
        with self.assertRaisesRegex(ValueError,"version/hash/kind"):
            read_pinned(fake,pin)

    def test_resource_workflow_refuses_to_promote_live_backend_as_scripted(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            (path/"report.json").write_text(json.dumps({"status":"complete",
                "study_kind":"exclusive_resource_reminder","backend":{"mode":"responses"}}))
            fake=FakeRecords()
            objects={name:fixture_record("resource-"+name,kind, {"artifact_directory":str(path)} if name=="result" else {})
                for name,kind in (("result","resource_experiment"),("protocol","resource_protocol"),
                                  ("verification","verification"),("claims","claim_audit"))}
            fake.objects.update({record["id"]:record for record in objects.values()})
            pins={name:{k:record[k] for k in ("id","version","kind","hash")} for name,record in objects.items()}
            with self.assertRaisesRegex(ValueError,"scripted workflow, not live subject evidence"):
                collect_resource_workflow(fake,pins)

    def test_local_theory_snapshot_and_reference_fields_are_escaped(self):
        addition={"references":{"unsafe":dict(id='<script>alert(1)</script>',version=1,hash='"quoted"')},
                  "theory_notes":[{"repository_path":"note<script>.md","sha256":"digest",
                    "local_uri":"file:///safe?x=\"onclick=\"bad","scope":"snapshot",
                    "snapshot":"</pre><script>alert(1)</script>"}]}
        page=render_addition_sources(addition)
        parser=Structure();parser.feed(page)
        self.assertEqual(parser.scripts,0)
        self.assertIn("&lt;script&gt;",page)
        self.assertIn("&quot;onclick=&quot;bad",page)

    def test_report_pins_reject_boolean_and_float_versions(self):
        records = FakeRecords()
        record = records.objects["dataset-test"]
        pin = {k: record[k] for k in ("id", "version", "kind", "hash")}
        for version in (True, 1.0):
            with self.subTest(version=version), self.assertRaises(ValueError):
                read_pinned(records, {**pin, "version": version})

    def test_temporal_failed_pure_derivation_retains_sources_without_derived_tables(self):
        from swarm_lab.temporal_network import analyze_temporal_mentions
        records = FakeRecords()
        rows = [{"id": "t1", "agent_id": "a", "agent_name": "Alice", "timestamp": "2025-04-01T00:00:02Z", "content": "Bob", "room_id": "r"},
                {"id": "t2", "agent_id": "b", "agent_name": "Bob", "timestamp": "2025-04-01T00:00:01Z", "content": "Cara", "room_id": "r"}]
        agents = [{"id": "a", "name": "Alice"}, {"id": "b", "name": "Bob"}, {"id": "c", "name": "Cara"}]
        dataset = fixture_record("temporal-dataset-test", "dataset", {"messages": rows, "agents": agents})
        discovery = fixture_record("temporal-discovery-test", "discovery", {})
        selected = fixture_record("temporal-selected-test", "selected_lead_audit", {})
        refs = {name: {k: obj[k] for k in ("id", "version", "hash")} for name, obj in
                (("dataset", dataset), ("discovery", discovery), ("selected_audit", selected))}
        payload = analyze_temporal_mentions(rows, agents, source_refs=refs)
        payload.update(dataset_ref=refs["dataset"], discovery_ref=refs["discovery"], selected_audit_ref=refs["selected_audit"], original_comparisons=[])
        audit = fixture_record("temporal-audit-test", "temporal_path_audit", payload)
        verification = fixture_record("temporal-verification-test", "verification", {
            "audit_ref": {k: audit[k] for k in ("id", "version", "hash")}, "result_kind": "temporal_path_audit", "passed": True, "model_calls": 0})
        records.objects.update({obj["id"]: obj for obj in (dataset, discovery, selected, audit, verification)})
        pins = {name: {k: obj[k] for k in ("id", "version", "kind", "hash")} for name, obj in (("audit", audit), ("verification", verification))}
        before = copy.deepcopy(records.objects)
        with patch("swarm_lab.temporal_workflow.derive_temporal_paths", return_value={"changed_derivation": True}) as derive:
            addition = collect_temporal_paths(records, pins)
        self.assertFalse(addition["proof"]["passed"])
        self.assertEqual(derive.call_args.kwargs, {"version": 1})
        self.assertIs(derive.call_args.args[0].store, records)
        self.assertEqual(addition["windows"], [])
        self.assertEqual(addition["static_only_witnesses"], [])
        self.assertTrue(addition["retained_unverified_windows"])
        self.assertEqual(records.objects, before)
        page = render_temporal_addition(addition)
        self.assertIn("witness tables are withheld", page)
        self.assertNotIn("<caption>Same room/window-specific", page)
        self.assertNotIn("<caption>Recompute all alternate", page)

    def test_timed_fixture_archive_replay_is_readonly_and_context_independent(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            records, pins, raw = timed_fixture(directory)
            before = copy.deepcopy(records.objects)
            original = (directory / "report.json").read_bytes()
            addition = collect_timed_resource_workflow(records, pins)
            self.assertTrue(addition["proof"]["passed"], addition["proof"])
            self.assertTrue(addition["proof"]["general_execution_passed"])
            self.assertTrue(addition["claim_audit"]["passed"], addition["claim_audit"])
            self.assertEqual(len(addition["claim_audit"]["recomputed"]["supported_fact_ids"]), 24)
            self.assertIs(addition["claim_audit"]["recomputed"]["attached_prose_approved"], False)
            self.assertEqual(addition["quantities"]["independent_seed_blocks"], 2)
            self.assertEqual(addition["quantities"]["scripted_swarms"], 4)
            self.assertTrue(addition["quantities"]["all_actions_match_current_context_independent_policy"])
            self.assertEqual(addition["analysis"]["primary_effect"]["difference"], 0)
            self.assertEqual(addition["model_calls"], 0)
            self.assertEqual(records.objects, before)
            self.assertEqual((directory / "report.json").read_bytes(), original)
            self.assertEqual(addition["raw_file_sha256"], hashlib.sha256(original).hexdigest())
            self.assertEqual(addition["canonical_execution_report_hash"], raw["report_hash"])

    def test_timed_finite_gate_rejects_forged_counts_effect_direction_and_numeric_type(self):
        mutations = (("trial_count/completed", 5),
                     ("comparison/active/neutral/outcome/task_completion_fraction/mean_direction", "higher"),
                     ("interval/active_vs_neutral/task_completion_fraction/lower", 1),
                     ("trial_count/completed", 4.0))
        for fact_id, asserted in mutations:
            with self.subTest(fact_id=fact_id, asserted=asserted), tempfile.TemporaryDirectory() as folder:
                records, pins, _ = timed_fixture(Path(folder))
                payload = records.objects[pins["claims"]["id"]]["payload"]
                claim = next(c for c in payload["claims"] if c["fact_id"] == fact_id)
                claim["expected"] = asserted
                # Retain the forged record's own recomputed audit: rejection must
                # come from the fresh executable fact, not stale saved verdicts.
                from swarm_lab.timed_resource_claims import audit_timed_resource_claims
                payload["audit"] = audit_timed_resource_claims(records.timed_ledger, payload["claims"])
                reseal_timed_claims(records, pins)
                before = copy.deepcopy(records.objects)
                addition = collect_timed_resource_workflow(records, pins)
                self.assertTrue(addition["proof"]["general_execution_passed"])
                self.assertFalse(addition["proof"]["passed"])
                self.assertFalse(addition["claim_audit"]["checks"]["strict_claim_recheck"])
                self.assertTrue(addition["claim_audit"]["checks"]["stored_audit_matches_recheck"])
                adjudicated = next(c for c in addition["claim_audit"]["recomputed"]["claims"] if c["id"] == claim["id"])
                self.assertEqual(adjudicated["status"], "mismatch")
                self.assertIsNone(adjudicated["approved_fact_text"])
                self.assertIsNone(addition["quantities"])
                self.assertIsNone(addition["analysis"])
                self.assertEqual(addition["runs"], [])
                self.assertEqual(records.objects, before)
                page = render_timed_resource_addition(addition)
                self.assertIn("effect statistics are withheld", page)
                self.assertNotIn("<caption>Assigned-policy ITT", page)
                self.assertNotIn("<caption>Finite claim recheck", page)

    def test_timed_claim_source_bindings_fail_even_when_execution_replays(self):
        mutations = (("result_ref", "hash", "0" * 64, "exact_result_binding"),
                     ("fact_packet", "source_fingerprint", "0" * 64, "source_fingerprint_binding"),
                     (None, "canonical_execution_report_hash", "0" * 64, "canonical_report_binding"))
        for parent_key, field, value, check in mutations:
            with self.subTest(check=check), tempfile.TemporaryDirectory() as folder:
                records, pins, _ = timed_fixture(Path(folder))
                payload = records.objects[pins["claims"]["id"]]["payload"]
                target = payload if parent_key is None else payload[parent_key]
                target[field] = value
                reseal_timed_claims(records, pins)
                addition = collect_timed_resource_workflow(records, pins)
                self.assertTrue(addition["proof"]["general_execution_passed"])
                self.assertFalse(addition["proof"]["passed"])
                self.assertFalse(addition["claim_audit"]["checks"][check])
                self.assertTrue(addition["claim_audit"]["checks"]["strict_claim_recheck"])
                self.assertIsNone(addition["quantities"])
                self.assertIsNone(addition["analysis"])

    def test_missing_optional_timed_claims_does_not_authorize_finite_tables(self):
        with tempfile.TemporaryDirectory() as folder:
            records, pins, _ = timed_fixture(Path(folder))
            del pins["claims"]
            addition = collect_timed_resource_workflow(records, pins)
            self.assertTrue(addition["proof"]["general_execution_passed"])
            self.assertFalse(addition["proof"]["passed"])
            self.assertFalse(addition["claim_audit"]["passed"])
            self.assertIn("Optional stored claim audit was not included", addition["claim_audit"]["reason"])
            self.assertIsNone(addition["quantities"])
            self.assertEqual(addition["runs"], [])

    def test_timed_supported_fact_does_not_approve_attached_model_prose(self):
        from swarm_lab.timed_resource_claims import audit_timed_resource_claims
        with tempfile.TemporaryDirectory() as folder:
            records, pins, _ = timed_fixture(Path(folder))
            payload = records.objects[pins["claims"]["id"]]["payload"]
            prose = "<script>invented mechanism</script> Every model became persuaded by the reminder."
            payload["claims"][0]["statement"] = prose
            payload["audit"] = audit_timed_resource_claims(records.timed_ledger, payload["claims"])
            reseal_timed_claims(records, pins)
            addition = collect_timed_resource_workflow(records, pins)
            self.assertTrue(addition["proof"]["passed"], addition["claim_audit"])
            checked = addition["claim_audit"]["recomputed"]
            self.assertTrue(checked["all_executable_claims_supported"])
            self.assertTrue(checked["unverified_prose_present"])
            self.assertIs(checked["attached_prose_approved"], False)
            self.assertTrue(all(row["prose_status"] == "unverified" for row in checked["claims"]))
            self.assertTrue(all(prose not in row["approved_fact_text"] for row in checked["claims"]))
            page = render_timed_resource_addition(addition)
            parsed = Structure(); parsed.feed(page)
            self.assertEqual(parsed.scripts, 0)
            self.assertIn("&lt;script&gt;invented mechanism&lt;/script&gt;", page)
            self.assertIn("Finite claim recheck; generated fact text alone is approved", page)
            self.assertIn("Attached model prose remains unverified", page)

    def test_failed_timed_report_or_archive_proof_withholds_outcome_tables(self):
        for failure in ("missing_report", "archive_changed", "raw_changed"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as folder:
                directory = Path(folder)
                records, pins, _ = timed_fixture(directory)
                if failure == "missing_report":
                    (directory / "report.json").unlink()
                elif failure == "archive_changed":
                    source = directory / "execution-code" / "intervention_timing.py"
                    source.write_bytes(source.read_bytes() + b"\n# changed fixture\n")
                else:
                    path = directory / "report.json"
                    raw = json.loads(path.read_text())
                    raw["backend"]["metadata"]["model"] = "unregistered-model"
                    path.write_text(json.dumps(raw))
                addition = collect_timed_resource_workflow(records, pins)
                self.assertFalse(addition["proof"]["passed"])
                self.assertIsNone(addition["quantities"])
                self.assertIsNone(addition["analysis"])
                self.assertEqual(addition["runs"], [])
                page = render_timed_resource_addition(addition)
                self.assertIn("effect statistics are withheld", page)
                self.assertNotIn("<caption>Assigned-policy ITT", page)
                self.assertNotIn("The recorded paired ITT difference", page)

    def test_new_report_args_preserve_library_defaults_but_cli_includes_additions(self):
        signature = inspect.signature(collect_report)
        self.assertIs(signature.parameters["include_temporal_paths"].default, False)
        self.assertIs(signature.parameters["include_timed_resource"].default, False)
        self.assertIs(signature.parameters["include_source_lineage"].default, False)
        report = {"proof": {"current_action_replay": {"passed": True}, "analysis_recomputation": {"passed": True}}, "execution_inventory": {}}
        for args, expected in (([], True), (["--no-temporal-paths", "--no-timed-resource", "--no-source-lineage"], False)):
            with patch("scripts.build_research_report.collect_report", return_value=report) as collect, \
                 patch("scripts.build_research_report.write_report", return_value=(Path("fixture.html"), Path("fixture.json"))), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(args), 0)
            self.assertIs(collect.call_args.kwargs["include_temporal_paths"], expected)
            self.assertIs(collect.call_args.kwargs["include_timed_resource"], expected)
            self.assertIs(collect.call_args.kwargs["include_source_lineage"], expected)

    def test_source_lineage_report_rereads_files_and_omits_raw_provider_rows(self):
        from swarm_lab.source_workflow import derive_source_links
        with tempfile.TemporaryDirectory() as folder:
            records, pins, sources, _, markers = source_lineage_fixture(Path(folder))
            before = copy.deepcopy(records.objects)
            file_bytes = {t: Path(s["path"]).read_bytes() for t, s in sources.items()}
            with patch("swarm_lab.source_workflow.derive_source_links", wraps=derive_source_links) as derive:
                addition = collect_source_lineage(records, pins)
            derive.assert_called_once_with(records.objects[pins["audit"]["id"]]["payload"]["plan"])
            self.assertTrue(addition["proof"]["passed"], addition["proof"])
            self.assertTrue(addition["proof"]["filesystem_reread_attempted"])
            self.assertTrue(addition["proof"]["filesystem_reread_completed"])
            q = addition["quantities"]
            self.assertEqual((q["retained_rows"], q["explicit_relation_attempts"], q["scoped_matches"]), (6, 4, 4))
            self.assertEqual((q["matched_chat_emissions"], q["matched_session_links"]), (1, 3))
            self.assertEqual(addition["model_calls"], 0)
            self.assertEqual(records.objects, before)
            self.assertEqual({t: Path(s["path"]).read_bytes() for t, s in sources.items()}, file_bytes)
            page = render_source_lineage_addition(addition)
            for marker in markers.values():
                self.assertNotIn(marker, json.dumps(addition))
                self.assertNotIn(marker, page)
            self.assertNotIn('"agent_messages"', json.dumps(addition))
            for match in addition["matched_coordinates"]:
                self.assertIn(match["child_source"]["record_sha256"], page)
                self.assertIn(match["parent_source"]["raw_line_sha256"], page)
            self.assertIn("Retrospective known-prefix probe", page)
            self.assertIn("do not estimate prevalence", page)
            self.assertIn("no independent experimental units", page)

    def test_resealed_source_counts_types_coverage_and_plan_do_not_replace_fresh_proof(self):
        for mutation in ("count", "float_count", "coverage", "bool_budget", "unknown_metadata", "raw_provider"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                records, pins, _, _, _ = source_lineage_fixture(Path(folder))
                payload = records.objects[pins["audit"]["id"]]["payload"]
                if mutation == "count":
                    payload["source_link_audit"]["counts"]["retained_rows"] = 7
                elif mutation == "float_count":
                    payload["source_link_audit"]["counts"]["retained_rows"] = 6.0
                elif mutation == "coverage":
                    payload["source_readset"]["chat_messages"]["coverage"]["complete_scan"] = False
                elif mutation == "raw_provider":
                    payload["source_link_audit"]["raw_provider"] = "UNTRUSTED_PROVIDER_ONLY_MARKER"
                else:
                    source = payload["plan"]["sources"]["events"]
                    if mutation == "bool_budget":
                        source["max_rows"] = True
                    else:
                        source["source_metadata"]["unknown_provider_payload"] = "UNTRUSTED_PROVIDER_ONLY_MARKER"
                    payload["plan_hash"] = fingerprint(payload["plan"])
                reseal_source_audit(records, pins)
                addition = collect_source_lineage(records, pins)
                self.assertFalse(addition["proof"]["passed"])
                self.assertTrue(addition["proof"]["filesystem_reread_attempted"])
                self.assertIsNone(addition["quantities"])
                self.assertIsNone(addition["scan_plan"])
                self.assertEqual(addition["coverage"], [])
                self.assertEqual(addition["matched_coordinates"], [])
                page = render_source_lineage_addition(addition)
                self.assertIn("coordinate tables are withheld", page)
                self.assertNotIn("<caption>Explicit relation statuses", page)
                self.assertNotIn("UNTRUSTED_PROVIDER_ONLY_MARKER", page)

    def test_source_lineage_implementation_and_identity_failure_avoid_reread(self):
        for mutation in ("implementation", "verification_identity", "bool_zero", "pin_hash", "pin_version", "missing_pin", "wrong_kind", "wrong_shape"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                records, pins, _, _, _ = source_lineage_fixture(Path(folder))
                payload = records.objects[pins["audit"]["id"]]["payload"]
                if mutation == "implementation":
                    payload["implementation_hashes"]["source_scanner.py"] = "0" * 64
                    reseal_source_audit(records, pins)
                elif mutation == "bool_zero":
                    payload["model_calls"] = False
                    reseal_source_audit(records, pins)
                elif mutation == "verification_identity":
                    record = records.objects[pins["verification"]["id"]]
                    record["payload"]["audit_ref"]["version"] = True
                    record["hash"] = fingerprint(record["payload"])
                    pins["verification"]["hash"] = record["hash"]
                elif mutation == "pin_hash":
                    pins["audit"]["hash"] = "0" * 64
                elif mutation == "pin_version":
                    pins["audit"]["version"] = 1.0
                elif mutation == "missing_pin":
                    del pins["verification"]
                elif mutation == "wrong_kind":
                    records.objects[pins["audit"]["id"]]["kind"] = "dataset"
                    pins["audit"]["kind"] = "dataset"
                else:
                    records.objects[pins["audit"]["id"]]["payload"] = []
                    reseal_source_audit(records, pins)
                with patch("swarm_lab.source_workflow.derive_source_links", side_effect=AssertionError("Must not read")) as derive:
                    addition = collect_source_lineage(records, pins)
                derive.assert_not_called()
                self.assertFalse(addition["proof"]["passed"])
                self.assertFalse(addition["proof"]["filesystem_reread_attempted"])
                self.assertIsNone(addition["quantities"])

    def test_source_lineage_missing_implementation_file_is_a_failed_proof(self):
        with tempfile.TemporaryDirectory() as folder:
            records, pins, _, _, _ = source_lineage_fixture(Path(folder))
            with patch("swarm_lab.source_workflow.implementation_hashes", side_effect=FileNotFoundError("Missing pinned module")), \
                 patch("swarm_lab.source_workflow.derive_source_links", side_effect=AssertionError("Must not read")) as derive:
                addition = collect_source_lineage(records, pins)
            derive.assert_not_called()
            self.assertFalse(addition["proof"]["passed"])
            self.assertEqual(addition["proof"]["reason"], "source_implementation_unavailable")
            self.assertIsNone(addition["quantities"])

    def test_source_lineage_changed_file_or_missing_file_withholds_coverage_and_counts(self):
        from tests.test_source_workflow_independent import write_rows
        for mutation in ("whitespace", "missing"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                records, pins, sources, rows, _ = source_lineage_fixture(Path(folder))
                path = Path(sources["chat_messages"]["path"])
                if mutation == "whitespace":
                    write_rows(path, rows["chat_messages"], spaced=True)
                else:
                    path.unlink()
                addition = collect_source_lineage(records, pins)
                self.assertFalse(addition["proof"]["passed"])
                self.assertTrue(addition["proof"]["filesystem_reread_attempted"])
                self.assertIsNone(addition["quantities"])
                self.assertEqual(addition["coverage"], [])

    def test_source_coordinate_and_pin_text_is_escaped_in_self_contained_html(self):
        with tempfile.TemporaryDirectory() as folder:
            records, pins, _, _, _ = source_lineage_fixture(Path(folder))
            addition = collect_source_lineage(records, pins)
            addition["matched_coordinates"][0]["child_source"]["path"] = '</td><script>unsafe coordinate</script>'
            addition["references"]["audit"]["id"] = '<script>unsafe pin</script>'
            page = render_source_lineage_addition(addition)
            parser = Structure(); parser.feed(page)
            self.assertEqual(parser.scripts, 0)
            self.assertFalse(parser.external)
            self.assertIn("&lt;script&gt;unsafe coordinate&lt;/script&gt;", page)
            self.assertIn("&lt;script&gt;unsafe pin&lt;/script&gt;", page)


class Structure(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=[];self.fragments=[];self.scripts=0;self.external=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if "id" in attrs:self.ids.append(attrs["id"])
        if tag=="script":self.scripts+=1
        for key in ("href","src"):
            value=attrs.get(key,"")
            if value.startswith("#"):self.fragments.append(value[1:])
            if value.startswith(("http:","https:")):self.external.append(value)


@unittest.skipUnless((ROOT/".runtime/lab.sqlite3").exists(), "Reviewed local pilot records are not shipped with source tests")
class ReviewedPilotReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=collect_report(ROOT/".runtime/lab.sqlite3","experiment-f8ebb002aa60","network_experiment-b215b2b47aef",include_selected_leads=True,
                                  include_temporal_paths=True, include_timed_resource=True, include_source_lineage=True)

    def test_source_lineage_known_prefix_has_fresh_filesystem_proof_and_scoped_counts(self):
        source = self.report["bounded_source_lineage"]
        self.assertTrue(source["proof"]["passed"], source["proof"])
        self.assertTrue(all(source["proof"]["checks"].values()))
        self.assertTrue(source["proof"]["filesystem_reread_attempted"])
        self.assertTrue(source["proof"]["filesystem_reread_completed"])
        q = source["quantities"]
        self.assertEqual((q["retained_rows"], q["explicit_relation_attempts"], q["scoped_matches"]), (131, 103, 3))
        self.assertEqual((q["matched_chat_emissions"], q["matched_session_links"], q["parents_unresolved_in_scanned_scope"], q["missing_foreign_keys"]), (1, 2, 93, 7))
        self.assertEqual((q["scanned_tables"], q["partial_tables"]), (4, 4))
        self.assertEqual({c["table"]: c["coverage"]["stop_reason"] for c in source["coverage"]}, {
            "events": "row_limit", "chat_messages": "selected_ids_found", "computer_use_sessions": "selected_ids_found", "computer_use_turns": "row_limit"})
        self.assertEqual(len(source["matched_coordinates"]), 3)
        self.assertEqual({r["child_source"]["line"] for r in source["matched_coordinates"]}, {37, 59, 51})
        self.assertEqual({r["parent_source"]["line"] for r in source["matched_coordinates"]}, {10013, 1835, 1266})
        self.assertTrue(all(r["receipt"] == "unestablished" for r in source["matched_coordinates"]))
        self.assertEqual(source["global_source_completeness"], "unverified")
        self.assertEqual(source["model_calls"], 0)
        for name, pin in SOURCE_LINEAGE_PINS.items():
            self.assertTrue(all(source["references"][name][k] == v for k, v in pin.items()))
        without_source = {k: v for k, v in self.report.items() if k != "bounded_source_lineage"}
        self.assertEqual(execution_inventory(without_source), self.report["execution_inventory"])

    def test_temporal_paths_replay_original_windows_and_source_witnesses(self):
        temporal = self.report["temporal_reference_paths"]
        selected = self.report['selected_lead_measurement_sensitivity']
        if selected['proof'].get('checks', {}).get('code_hashes') is False:
            # An old saved audit cannot become a fresh proof under changed code.
            self.assertFalse(temporal['proof']['passed'])
            self.assertFalse(temporal['proof']['checks']['fresh_pinned_source_replay'])
            self.assertTrue(all(value for key, value in temporal['proof']['checks'].items()
                                if key != 'fresh_pinned_source_replay'))
            self.assertEqual(temporal['windows'], [])
            self.assertEqual(temporal['static_only_witnesses'], [])
            self.assertIn('does not reproduce', temporal['proof']['fresh_replay']['error'])
            self.assertEqual(temporal['model_calls'], 0)
            return
        self.assertTrue(temporal["proof"]["passed"], temporal["proof"])
        self.assertEqual(len(temporal["windows"]), 6)
        names = ("baseline_exact", "explicit_short_expanded_exact", "unicode_baseline", "unicode_expanded")
        totals = {name: sum(w["variants"][name]["static_only_pairs"] for w in temporal["windows"]) for name in names}
        self.assertEqual(totals, {"baseline_exact": 1, "explicit_short_expanded_exact": 2, "unicode_baseline": 3, "unicode_expanded": 4})
        self.assertEqual(len(temporal["static_only_witnesses"]), sum(totals.values()))
        for example in temporal["static_only_witnesses"]:
            self.assertFalse(example["witness"]["strict_timestamp_order"])
            self.assertEqual(set(example["witness"]["message_ids"]), {m["id"] for m in example["source_messages"]})
            sources = {m["id"]: m for m in example["source_messages"]}
            for step in example["witness"]["steps"]:
                self.assertEqual(step["room_id"], sources[step["message_id"]]["room_id"])
        for name, pin in TEMPORAL_PINS.items():
            self.assertTrue(all(temporal["references"][name][k] == v for k, v in pin.items()))
        self.assertEqual(temporal["model_calls"], 0)

    def test_scripted_timing_is_two_blocks_four_swarms_with_no_empirical_effect(self):
        timed = self.report["scripted_timed_resource_workflow"]
        self.assertTrue(timed["proof"]["passed"], timed["proof"])
        self.assertTrue(timed["proof"]["general_execution_passed"])
        claims = timed["claim_audit"]
        self.assertTrue(claims["passed"], claims)
        self.assertTrue(claims["quantitative_facts_available"])
        self.assertTrue(all(claims["checks"].values()))
        self.assertEqual(len(claims["recomputed"]["supported_fact_ids"]), 24)
        self.assertIs(claims["recomputed"]["attached_prose_approved"], False)
        self.assertEqual(timed["references"]["claim_verification"]["id"], "verification-06cac4a0efaa")
        self.assertEqual(timed["references"]["claim_verification"]["hash"], TIMED_RESOURCE_PINS["verification"]["hash"])
        q = timed["quantities"]
        self.assertEqual((q["scripted_swarms"], q["independent_seed_blocks"], q["declared_tasks"], q["executed_completed_tasks"]), (4, 2, 32, 28))
        self.assertEqual((q["eligible_preparations"], q["recorded_receipts"], q["applied_actions"], q["never_delivered_completed_swarms"]), (4, 4, 96, 0))
        self.assertTrue(q["all_actions_match_current_context_independent_policy"])
        effect = timed["analysis"]["primary_effect"]
        self.assertEqual((effect["difference"], effect["ci95"], effect["p_two_sided"]), (0, [-1, 1], 1))
        self.assertTrue(all(r["outcomes"]["task_completion_fraction"] == .875 for r in timed["runs"]))
        self.assertEqual(sum(len(r["receipt_boundaries"]) for r in timed["runs"]), 4)
        inventory = self.report["execution_inventory"]
        self.assertEqual((inventory["completed_live_units"], inventory["completed_scripted_resource_units"], inventory["completed_scripted_timed_resource_units"]), (37, 4, 4))
        self.assertEqual(inventory["scripted_timed_independent_seed_blocks"], 2)
        self.assertFalse(inventory["unverified_scripted_sections"])
        for name, pin in TIMED_RESOURCE_PINS.items():
            self.assertTrue(all(timed["references"][name][k] == v for k, v in pin.items()))

    def test_selected_episode_replay_retains_signed_reversal_and_all_source_rows(self):
        selected=self.report['selected_lead_measurement_sensitivity']
        if selected['proof'].get('checks', {}).get('code_hashes') is False:
            self.assertFalse(selected['proof']['passed'])
            self.assertTrue(all(value for key, value in selected['proof']['checks'].items()
                                if key != 'code_hashes'))
            self.assertEqual(selected['per_lead'], [])
            self.assertGreater(len(selected['retained_unverified_per_lead']), 0)
            self.assertEqual(selected['references']['audit']['hash'], SELECTED_LEAD_PIN['hash'])
            self.assertEqual(selected['model_calls'], 0)
            return
        self.assertTrue(selected['proof']['passed'],selected['proof'])
        self.assertEqual(selected['references']['audit']['hash'],SELECTED_LEAD_PIN['hash'])
        self.assertEqual(selected['scope']['source_message_count'],588)
        self.assertEqual(selected['scope']['all_source_human_message_count'],180)
        self.assertFalse(selected['frozen_selection']['selection_or_matching_changed'])
        lead=next(l for l in selected['per_lead'] if l['lead_id']=='graph-lead-9e40b45259d92f7b')
        self.assertGreater(lead['native']['baseline_exact']['difference'],0)
        self.assertLess(lead['native']['explicit_short_expanded_exact']['difference'],0)
        self.assertEqual(selected['model_calls'],0)

    def test_negative_pilot_and_actual_process_counts_retained(self):
        pilot=self.report["complementary_pilot"]
        q=pilot["quantities"]
        self.assertEqual(q["independent_networks"],8)
        self.assertEqual(q["networks_with_zero_accuracy"],8)
        self.assertEqual(q["valid_submissions"],16)
        self.assertEqual(q["correct_submissions"],0)
        self.assertEqual(q["absent_submissions"],16)
        self.assertEqual(q["successful_action_counts"],{"send_message":46,"send_neighbors":0,"inspect_fragment":0,"submit_total":16,"wait":34})
        self.assertEqual(q["dispatches_with_canonical_attachments"],13)
        self.assertEqual(q["recorded_relay_attachment_events"],2)
        self.assertTrue(pilot["proof"]["passed"])
        self.assertTrue(pilot["analysis_recomputation"]["passed"])
        self.assertEqual(pilot["execution_archive"]["status"],"verified")
        self.assertTrue(pilot["claim_audit"]["recomputed"]["all_executable_claims_supported"])
        self.assertTrue(pilot["claim_audit"]["source_fingerprint_matches"])
        self.assertEqual(self.report["new_model_calls"],0)

    def test_graph_sources_explicitly_supersede_without_promoting_mechanism(self):
        entries=self.report["exploratory_graph_reviews"]["entries"]
        self.assertEqual([(e["behavior"]["id"],e["superseded"]["id"]) for e in entries],list(GRAPH_REVIEW_PAIRS))
        self.assertTrue(all(e["unchanged_proposal_and_sources"] for e in entries))
        self.assertTrue(all(e["proposal_and_review"]["causal_support"]=="none" for e in entries))

    def test_four_measurement_variants_change_operator_not_source_or_society(self):
        measurement=self.report["graph_name_measurement_sensitivity"]
        self.assertEqual(len(measurement["node_universe"]["ids"]),5)
        variants=measurement["variants"]
        self.assertEqual({name:v["counts"]["projected_agent_event_count"] for name,v in variants.items()},
            {"baseline_exact":62,"explicit_short_expanded_exact":143,"unicode_baseline":81,"unicode_expanded":162})
        self.assertTrue(all(v["counts"]["node_universe_count"]==5 for v in variants.values()))
        o3="e7206d8d-c1d9-4ab1-a2fb-cf0af692bb0d"
        incoming=lambda name:next(n["in_strength"] for n in variants[name]["metrics"]["nodes"] if n["id"]==o3)
        self.assertEqual((incoming("baseline_exact"),incoming("explicit_short_expanded_exact")),(0,77))
        self.assertEqual((variants["baseline_exact"]["spectral"]["nullity"],variants["explicit_short_expanded_exact"]["spectral"]["nullity"]),(3,1))
        self.assertTrue(measurement["proof"]["passed"],measurement["proof"])
        self.assertEqual(measurement["model_calls"],0)
        for name,pin in MEASUREMENT_PINS.items():
            self.assertTrue(all(measurement["references"][name][k]==v for k,v in pin.items()))
        self.assertIn("delivery hub or influence",measurement["scope_note"])

    def test_scripted_resource_units_and_numerical_differences_are_separate(self):
        resource=self.report["scripted_resource_workflow"]
        quantities=resource["quantities"]
        self.assertEqual((quantities["scripted_swarms"],quantities["declared_tasks"],quantities["executed_completed_tasks"],quantities["action_slots"]),(4,32,25,96))
        self.assertTrue(quantities["all_actions_match_current_context_independent_policy"])
        self.assertEqual(resource["backend"]["mode"],"scripted_offline_smoke_test")
        self.assertTrue(resource["proof"]["passed"])
        self.assertTrue(resource["claim_audit"]["quantitative_facts_available"])
        self.assertTrue(resource["claim_audit"]["recomputed"]["all_executable_claims_supported"])
        self.assertTrue(resource["claim_audit"]["source_fingerprint_matches"])
        self.assertEqual(resource["execution_archive"]["status"],"verified")
        for name,pin in RESOURCE_PINS.items():
            self.assertTrue(all(resource["references"][name][k]==v for k,v in pin.items()))
        inventory=self.report["execution_inventory"]
        self.assertEqual((inventory["completed_live_units"],inventory["completed_scripted_resource_units"]),(37,4))
        self.assertEqual(sum(x["units"] for x in inventory["live_groups"]),37)
        self.assertIn("not pooled",inventory["scope"])
        self.assertIn("cannot be empirical reminder effects",resource["scope_note"])

    def test_self_contained_html_scope_additions_and_navigation(self):
        page=render_html(self.report)
        parsed=Structure();parsed.feed(page)
        self.assertEqual(parsed.scripts,0)
        self.assertFalse(parsed.external)
        self.assertEqual(len(set(parsed.ids)),len(parsed.ids))
        self.assertFalse(set(parsed.fragments)-set(parsed.ids))
        for phrase in ("Added study:","Added source group:","not proof of an absent treatment or topology effect", "free prose remains unverified", "not prove absent knowledge", "Estimates are not pooled", "Added measurement audit:", "Added infrastructure workflow:", "37 completed live team/network units", "4 separate scripted resource units", "cannot be empirical reminder effects or LLM findings", "does not establish an actual hub", "Added temporal audit:", "Added timing workflow:", "4 separate scripted timed-reminder units", "2 independent paired seed blocks", "no empirical LLM reminder effect", "87.5%"):
            self.assertIn(phrase,page)
        for pin in list(MEASUREMENT_PINS.values())+list(RESOURCE_PINS.values())+list(TEMPORAL_PINS.values())+list(TIMED_RESOURCE_PINS.values()):
            self.assertIn(pin["id"],page)
            self.assertIn(pin["hash"],page)
        for path in ("graph-math-methods.md","short-name-adjudication.md","communication-falsifiers.md","resource-study-design.md", "temporal-path-interpretation.md", "intervention-timing.md"):
            self.assertIn(path,page)
        self.assertIn("Finite claim recheck; generated fact text alone is approved", page)
        self.assertIn("Attached model prose remains unverified", page)
        self.assertIn("verification-06cac4a0efaa", page)
        self.assertIn("Added source lineage:", page)
        self.assertIn("4 of 4 scans are partial", page)
        self.assertIn("do not estimate prevalence", page)
        self.assertIn("no independent experimental units", page)
        for pin in SOURCE_LINEAGE_PINS.values():
            self.assertIn(pin["id"], page)
            self.assertIn(pin["hash"], page)


if __name__ == "__main__":
    unittest.main()
