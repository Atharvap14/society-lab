"""Build a self-contained pilot audit from immutable local records, without model calls.

The database is opened read-only. Quantities come from executed run outcomes;
model commentary is retained as a reviewed artifact, never used as an oracle.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import datetime as dt
import hashlib
import html
import json
from pathlib import Path
import sqlite3
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from swarm_lab.store import clean, fingerprint
from swarm_lab.audit import replay_report, replay_network_report, check_execution_archive
from swarm_lab.experiments import summarize_runs
from swarm_lab.reporting import quantitative_summary
from swarm_lab.claim_audit import build_fact_ledger, audit_claims

COMPLEMENTARY_RESULT = "complementary_experiment-95e2a6857435"
COMPLEMENTARY_VERIFICATION = "verification-834a56a6765a"
COMPLEMENTARY_CLAIM_AUDIT = "claim_audit-54c25c5e4ba8"
GRAPH_REVIEW_PAIRS = (("behavior-c6795bc08068", "behavior-12a65d3fed40"),
                      ("behavior-ad77419c8fab", "behavior-982decd63735"))
MEASUREMENT_PINS = {
    "dataset": {"id": "dataset-5d2eef17db31", "version": 1, "kind": "dataset", "hash": "4351ceeb788cc000b6e288927299f20d68095e9a449a47bb6cef5e0791cc5c41"},
    "unicode": {"id": "measurement_audit-59899929fe3a", "version": 1, "kind": "measurement_audit", "hash": "9313f84b4887582fecebe53722ac5f1456d65e0cfbf6ea3750ca68ac0350d4e4"},
    "eligibility": {"id": "name_eligibility_audit-efb71d2a7205", "version": 1, "kind": "name_eligibility_audit", "hash": "cec10f05c63a30972ae16b248243a4a479dddd4f3c5e212e28f15d87ce27ca76"},
    "graphs": {"id": "graph_measurement_audit-0304268ac6eb", "version": 1, "kind": "graph_measurement_audit", "hash": "beed2c1a95fb002fcc2c56f597884ecba4c0f0675887eca23e1263bf4bcc1f88"},
}
RESOURCE_PINS = {
    "protocol": {"id": "resource_protocol-bb372b23896c", "version": 1, "kind": "resource_protocol", "hash": "7a3af4f93f12853fd759a9fdfbd040e2f256f8009a3d91fe3ca08cd8b80054a7"},
    "result": {"id": "resource_experiment-9905757e6e68", "version": 1, "kind": "resource_experiment", "hash": "d8974b1daf714577f6f1073917381b69993ec083945a0aa10692a1115f994a80"},
    "verification": {"id": "verification-320ad7ccc5b6", "version": 1, "kind": "verification", "hash": "0c6210e499b7ae87b62b3d60e55c676bc2fe7092baa0768b780a84b271c3f8e4"},
    "claims": {"id": "claim_audit-5efa478fa0e3", "version": 1, "kind": "claim_audit", "hash": "621f1bff4cb97ce4fd19c1955f886424a1567d48821b332fba67d1c2ad3690e8"},
}
SELECTED_LEAD_PIN = {'id':'selected_lead_audit-cdb8875d4e64','version':1,'kind':'selected_lead_audit',
                    'hash':'3309d1e6e8d174fe5b8919af3288812de65de1c3993b74ec6a9ff001578e11b0'}
TEMPORAL_PINS = {
    "audit": {"id": "temporal_path_audit-1c08eba1b540", "version": 1, "kind": "temporal_path_audit", "hash": "4ef7a67531cb9a2db9a8f7ba8ab1bbc403549cbe08e806c2b00a2cfb106e6512"},
    "verification": {"id": "verification-f50f5acd1792", "version": 1, "kind": "verification", "hash": "1aef1c8ef93eea6804a04ad234cb00280de9bf2b7e281e199697aab3135ddcdb"},
}
TIMED_RESOURCE_PINS = {
    "protocol": {"id": "timed_resource_protocol-0f7562f223af", "version": 1, "kind": "timed_resource_protocol", "hash": "3531e82869653baf17c22d95321ff9f2d25d5a71dc04cfd732db5adff3b3feee"},
    "result": {"id": "timed_resource_experiment-0c252f3dbff8", "version": 1, "kind": "timed_resource_experiment", "hash": "e1a2e11468f666fbffc929434bb4e7385d757dd015bdb8efe744c12908121a22"},
    "verification": {"id": "verification-642e686ee280", "version": 1, "kind": "verification", "hash": "5ebc7d0b33043383ad184943ef390d99f20673a637e647ec62fe72ba6582e7b0"},
    "claims": {"id": "claim_audit-d6091f415f62", "version": 1, "kind": "claim_audit", "hash": "6182031065de35181f5860895f02e96e77822addeec8586e98f6f86a62eea1b3"},
}
SOURCE_LINEAGE_PINS = {
    "audit": {"id": "source_link_audit-dcdbaca46070", "version": 1, "kind": "source_link_audit", "hash": "532924c84ea1142525dcee52d3437f6f5b9d2ce4850be117d4baadb2d02b9f44"},
    "verification": {"id": "verification-3f359f39b5e7", "version": 1, "kind": "verification", "hash": "cccafca0d35b4f140d2dd8b13cfe00c135ef5ed2e2ebdb3e02d7137da5d77d68"},
}
INDEXED_EVENT_PINS = {
    "audit": {"id": "indexed_event_audit-d83283eae5b3", "version": 1, "kind": "indexed_event_audit", "hash": "5992170a108d2b62bdd7bf3ad2e3da85587b1583a50fc72f19f01b86c24200b9"},
    "verification": {"id": "verification-eaa813f998dc", "version": 1, "kind": "verification", "hash": "e7e0d56bff9a4707833ce6eb14931c9fbc373b020ee960cd55ef76fd4d5f88f3"},
}
TEMPORAL_REFERENCE_PINS = {
    "reference": {"id": "temporal_timestamp_reference-2982e3922a42", "version": 1, "kind": "temporal_timestamp_reference", "hash": "c27faec81bb02f1bff6760dc07d126973b60e0b8e1eaf9551b501929be7c43ad"},
    "verification": {"id": "verification-fd8bb1e36ee1", "version": 1, "kind": "verification", "hash": "d89561d786dd6942ade02324c19a36e7a83153733cb51e256d0f073a9a588769"},
}
ACTOR_EVENT_PINS = {
    "audit": {"id": "actor_event_audit-29756e356310", "version": 1, "kind": "actor_event_audit", "hash": "9652a2145f359d3212747e372ed6e6f574aa5655362aa38ef1a74dc3609238bd"},
    "verification": {"id": "verification-02300cf38ab3", "version": 1, "kind": "verification", "hash": "3bc7b30c83d7dfc0872ec4bf086630ba883eea39589279cb5869cb949ff79048"},
}
WAIT_MARKER_PINS = {
    "audit": {"id": "wait_marker_alignment_audit-da8509c85911", "version": 1, "kind": "wait_marker_alignment_audit", "hash": "50efc6daeac5f254f5af5380da92e3925fe4ac1ca2bf4249c6a1ed36d633fd1f"},
    "verification": {"id": "verification-bf9c71828932", "version": 1, "kind": "verification", "hash": "bfdb6151db381f53845432ca5f226b332aea7189a1fe028a45b64aaed11e21d7"},
}
GRAPH_HODGE_PINS = {
    "audit": {"id": "graph_hodge_audit-5e784a84b49e", "version": 1, "kind": "graph_hodge_audit", "hash": "37374e0544b36c687c1c3f2b6ab304f1b034dfdc6636a8ea67d3f91b46b48d93"},
    "verification": {"id": "verification-47e957b13efc", "version": 1, "kind": "verification", "hash": "a4c472edc951cd24d31e934dcfb7d74f687fa423a78281b39afaacbc06bbd046"},
}
HODGE_DISPLAY_TOLERANCE = 1e-12


class ReadOnlyRecords:
    """Store-compatible reads without initialization, schema or journal writes."""
    def __init__(self, database: Path):
        database = database.resolve(strict=True)
        self.connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=30)
        self.connection.row_factory = sqlite3.Row

    @staticmethod
    def decode(row):
        return {**dict(row), "payload": json.loads(row["payload"])}

    def get(self, identity, version=None):
        query = "SELECT * FROM objects WHERE id=? ORDER BY version DESC LIMIT 1" if version is None else "SELECT * FROM objects WHERE id=? AND version=?"
        row = self.connection.execute(query, (identity,) if version is None else (identity, version)).fetchone()
        if row is None:
            raise KeyError(identity)
        return self.decode(row)

    def history(self, identity):
        rows = self.connection.execute("SELECT * FROM objects WHERE id=? ORDER BY version", (identity,)).fetchall()
        return [self.decode(row) for row in rows]

    def list(self, kind):
        rows = self.connection.execute("SELECT o.* FROM objects o JOIN (SELECT id, MAX(version) v FROM objects "
                                       "GROUP BY id) x ON o.id=x.id AND o.version=x.v WHERE o.kind=? "
                                       "ORDER BY o.created", (kind,)).fetchall()
        return [self.decode(row) for row in rows]

    def trace_summary(self, job_id):
        counts = {}
        if job_id:
            for row in self.connection.execute("SELECT payload FROM traces WHERE job_id=?", (job_id,)):
                kind = json.loads(row[0]).get("type", "unspecified")
                counts[kind] = counts.get(kind, 0) + 1
        return {"job_id": job_id, "recorded_trace_types": counts,
                "scope": "Trace type counts only; raw provider responses and credentials are not exported."}

    def close(self):
        self.connection.close()


def reference(record):
    return {key: record[key] for key in ("id", "version", "kind", "created", "hash")}


def inspect_run(run):
    """New descriptive actor/version measures; preserve original outcomes."""
    final = run["final_state"]
    published = final.get("published")
    version = published.get("version") if published else None
    own = final.get("inspections", {}).get("coordinator", [])
    turns = [{key: turn.get(key) for key in ("step", "agent_id", "action", "tool_result", "request")}
             for turn in run.get("turns", [])]
    return {"run_id": run["run_id"], "arm": run["arm"], "environment_seed": run["environment_seed"],
            "initial_defect": run["initial_state"].get("initial_defect"),
            "first_schedule": run["initial_state"].get("schedule", [])[:3],
            "outcomes": run["outcomes"], "published_version": version,
            "publisher_any_inspection": bool(published and own),
            "publisher_inspected_published_version": bool(published and any(x.get("version") == version for x in own)),
            "successful_repairs": sum(t.get("action", {}).get("action") == "repair_artifact" and
                                       t.get("tool_result", {}).get("ok") is True for t in turns),
            "context_delivered": run.get("context_insertion_delivered"), "turns": turns,
            "measure_scope": "Actor/version measures are exploratory trace-derived descriptions, not registered outcomes."}


def safe_check(function):
    try:
        return function()
    except Exception as exc:
        return {"passed": False, "error_type": type(exc).__name__, "error": str(exc),
                "scope": "Current code could not verify this artifact; retained records are not retroactively altered.",
                "model_calls": 0}


def replay_network(raw):
    """Offline replay of recorded network requests and actions, never fresh subjects."""
    from swarm_lab.diffusion_environment import create_diffusion_environment, diffusion_subject_request, fingerprint
    from swarm_lab.diffusion_experiments import validate_diffusion_protocol
    protocol = raw["protocol"]
    validate_diffusion_protocol(protocol)
    checks = [{"name": "canonical_report_hash", "passed": fingerprint({k: v for k, v in raw.items()
                                                                             if k != "report_hash"}) == raw.get("report_hash")}]
    for run in raw["runs"]:
        env = create_diffusion_environment(protocol["environments"][run["topology"]], run["environment_seed"])
        matches = {"initial_state_matches": env.snapshot() == run["initial_state"],
                   "subject_requests_match": True, "tool_results_match": True}
        delivered = set()
        for turn in run["turns"]:
            agent = env.next_agent
            if agent in protocol["intervention"]["recipients"] and agent not in delivered:
                insertion = protocol["contexts"][run["context"]]["insertion"]
                if insertion is not None:
                    env.inject_context(agent, insertion)
                delivered.add(agent)
            matches["subject_requests_match"] &= agent == turn["agent_id"] and diffusion_subject_request(env, agent) == turn["request"]
            matches["tool_results_match"] &= env.step(agent, copy.deepcopy(turn["action"])) == turn["tool_result"]
        matches["final_state_matches"] = env.snapshot() == run["final_state"]
        matches["oracle_outcomes_match"] = env.evaluate(protocol["intervention"]["focal_agent"]) == run["outcomes"]
        checks.append({"name": "recorded_network_action_replay", "run_id": run["run_id"],
                       "passed": all(matches.values()), **matches})
    return {"passed": all(x["passed"] for x in checks), "checks": checks, "runs_checked": len(raw["runs"]),
            "model_calls": 0, "scope": "Recorded-action replay validates execution; it is not new model replication."}


def load_raw(record):
    path = Path(record["payload"]["artifact_directory"]) / "report.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return path, raw


def complementary_quantities(raw):
    """Count executed records; do not infer success or knowledge from rationale."""
    runs = raw["runs"]
    successful = Counter(t["action"]["action"] for r in runs for t in r["turns"] if t["tool_result"].get("ok") is True)
    submitted = sum(len(r["final_state"]["submissions"]) for r in runs)
    correct_submissions = sum(s["total"] == r["final_state"]["oracle_total"] for r in runs
                              for s in r["final_state"]["submissions"].values())
    return {"independent_networks": len(runs), "declared_subject_slots": len(runs)*4,
            "networks_with_zero_accuracy": sum(r["outcomes"]["mean_accuracy"] == 0 for r in runs),
            "valid_submissions": submitted, "correct_submissions": correct_submissions,
            "absent_submissions": len(runs)*4-submitted,
            "successful_action_counts": {k: successful[k] for k in ("send_message", "send_neighbors", "inspect_fragment", "submit_total", "wait")},
            "valid_actions": sum(successful.values()),
            "message_dispatches": sum(r["outcomes"]["messages_sent"] for r in runs),
            "recipient_deliveries": sum(r["outcomes"]["message_deliveries"] for r in runs),
            "neighbor_multicast_actions": successful["send_neighbors"],
            "dispatches_with_canonical_attachments": sum(t["action"]["action"] in ("send_message", "send_neighbors") and
                t["tool_result"].get("ok") is True and bool(t["tool_result"].get("attached_original_ids")) for r in runs for t in r["turns"]),
            "all_subject_requests_advertise_neighbor_multicast": all("send_neighbors" in t["request"]["action_schema"]["properties"]["action"]["enum"] and
                "send_neighbors" in t["request"]["system"] for r in runs for t in r["turns"]),
            "recorded_relay_attachment_events": sum(r["outcomes"]["relay_attachment_events"] for r in runs),
            "actual_action_slots": sum(len(r["turns"]) for r in runs),
            "budget_terminations": sum(r["outcomes"]["terminated_by"] == "step_budget" for r in runs),
            "scope": "Descriptive record counts; canonical attachments do not measure mental knowledge or identify a mediator."}


def collect_complementary(records, identity):
    from swarm_lab.complementary_environment import fingerprint as scientific_fingerprint
    record = records.get(identity)
    path, raw = load_raw(record)
    if record["kind"] != "complementary_experiment" or raw.get("status") != "complete" or raw.get("study_kind") != "complementary_information_factorial":
        raise ValueError("The reviewed complementary pilot must be a complete complementary-information experiment")
    if raw.get("report_hash") != record["payload"].get("canonical_execution_report_hash") or scientific_fingerprint({k:v for k,v in raw.items() if k != "report_hash"}) != raw.get("report_hash"):
        raise ValueError("Complementary raw report no longer matches its registered canonical execution hash")
    verification = records.get(COMPLEMENTARY_VERIFICATION)
    claim_record = records.get(COMPLEMENTARY_CLAIM_AUDIT)
    protocol = records.get(record["payload"]["protocol_id"])
    expected = {k: record[k] for k in ("id", "version", "hash")}
    if any(x["payload"].get("result_ref") != expected for x in (verification, claim_record)):
        raise ValueError("Complementary replay or claim audit is bound to a different result version")
    from swarm_lab.complementary_experiments import analyze_complementary_runs
    ledger = build_fact_ledger(raw, report_id=identity, replay_check=replay_network_report)
    checked = audit_claims(ledger, claim_record["payload"]["claims"])
    return {"result": reference(record), "status": raw["status"], "agent_mode": record["payload"].get("agent_mode"),
            "raw_report_path": str(path), "raw_file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "canonical_execution_report_hash": raw.get("report_hash"),
            "hash_purposes": {
                "raw_file_sha256": "SHA256 over exact binary report.json bytes; no decoding or reserialization.",
                "canonical_execution_report_hash": "Scientific serializer: sorted compact JSON, UTF-8, ensure_ascii=False, excluding report_hash.",
                "stored_object_hash": "Store serializer over the persisted payload: sorted JSON with default separators, UTF-8, ensure_ascii=False. It is distinct from the scientific execution hash.",
                "scope": "Local integrity and version binding; hashes do not independently attest external timestamps or provider execution."},
            "protocol": {**reference(protocol), "definition": raw["protocol"]},
            "evidence_scope": raw["evidence_scope"], "quantities": complementary_quantities(raw),
            "analysis": raw["analysis"],
            "runs": [{k: r[k] for k in ("run_id", "topology", "context", "environment_seed", "outcomes", "turns", "final_state", "environment_contract")} for r in raw["runs"]],
            "proof": safe_check(lambda: replay_network_report(raw)),
            "analysis_recomputation": safe_check(lambda: {"passed": analyze_complementary_runs(raw["runs"],raw["protocol"]) == raw["analysis"], "model_calls": 0}),
            "execution_archive": check_execution_archive(path.parent),
            "object_payload_hash_checks": [{**reference(x), "passed": fingerprint(x["payload"]) == x["hash"]} for x in (record,protocol,verification,claim_record)],
            "stored_verification": {**reference(verification), "verification": verification["payload"]},
            "claim_audit": {**reference(claim_record), "recomputed": checked,
                            "source_fingerprint_matches": claim_record["payload"]["audit"]["source_fingerprint"] == ledger["source_fingerprint"],
                            "stored_agent_mode": claim_record["payload"]["agent_mode"],
                            "scope": "Finite assertions about this exact report only. Attached sentences and proposed mechanisms remain unverified."},
            "trace_summary": records.trace_summary(record["payload"].get("research_job_id")),
            "scope": "Separate live negative pilot; no pooled analysis, topology-performance conclusion, identified mediation, or historical mechanism."}


def collect_graph_reviews(records, pairs):
    group = []
    review_keys = {"skeptic", "research_attempt_id", "research_quality_status", "quality_limitation",
                   "supersedes_review_behavior_id", "corrected_review_behavior_id", "review_amendment_reason"}
    for current_id, previous_id in pairs:
        current, previous = records.get(current_id), records.get(previous_id)
        payload = current["payload"]
        if payload.get("supersedes_review_behavior_id") != previous_id:
            raise ValueError("Graph review is missing its explicit supersession link")
        source_refs = payload["source_refs"]
        source_objects = {k: records.get(v["id"], v["version"]) for k,v in source_refs.items()}
        if any(obj["hash"] != source_refs[k]["hash"] or fingerprint(obj["payload"]) != obj["hash"] for k,obj in source_objects.items()):
            raise ValueError("A pinned graph-review source version/hash does not match")
        messages = {m["id"]: m for m in source_objects["dataset"]["payload"]["messages"]}
        cited = list(dict.fromkeys(payload.get("evidence_ids", []) + payload.get("comparison_ids", []) + payload.get("skeptic", {}).get("evidence_ids", [])))
        if set(cited)-set(messages):
            raise ValueError("Graph-review evidence is missing from its pinned source")
        same = {k:v for k,v in payload.items() if k not in review_keys} == {k:v for k,v in previous["payload"].items() if k not in review_keys}
        if not same:
            raise ValueError("The graph-review proposal or source refs changed; the unchanged-proposal narrative requires a new review")
        attempt = records.get(payload["research_attempt_id"])
        selected_lead = next((x for x in source_objects["discovery"]["payload"].get("graph_search", {}).get("leads", []) if x["id"] == payload["candidate_id"]), None)
        group.append({"behavior": reference(current), "proposal_and_review": payload,
                      "superseded": {**reference(previous), "quality_status": previous["payload"].get("research_quality_status"),
                                     "quality_limitation": previous["payload"].get("quality_limitation")},
                      "unchanged_proposal_and_sources": same, "source_refs": source_refs,
                      "source_hash_checks": [{**reference(x), "passed": fingerprint(x["payload"]) == x["hash"]} for x in source_objects.values()],
                      "selected_graph_lead": selected_lead,
                      "source_evidence": [{"id": i, **{k:messages[i].get(k) for k in ("content", "agent_name", "timestamp", "source", "content_hash", "room_id")}} for i in cited],
                      "research_attempt": {**reference(attempt), "recovery_limitation": attempt["payload"].get("recovery_limitation"),
                                           "amendment_reason": attempt["payload"].get("amendment_reason"),
                                           "trace_summary": records.trace_summary(attempt["payload"].get("resume_job_id"))},
                      "scope": "Exploratory source interpretation only. Proposed mechanisms, novelty, actual inactivity and causal influence remain unestablished. Skeptic search narration is not proof of tool-performed search."})
    return {"group_kind": "separate_exploratory_graph_sources", "entries": group,
            "scope": "A schema repair re-adjudicated unchanged proposals against the same retained source versions. Superseded reviews remain in the registry; legacy source association was reconstructed, not a verified original input archive."}


def read_pinned(records, pin):
    if (not isinstance(pin, dict) or set(pin) != {"id", "version", "kind", "hash"}
            or type(pin.get("version")) is not int or pin["version"] < 1
            or any(not isinstance(pin.get(k), str) or not pin[k] for k in ("id", "kind", "hash"))):
        raise ValueError("Use exact positive-integer report pins with id, version, kind and hash")
    record = records.get(pin["id"], pin["version"])
    if fingerprint({key: record.get(key) for key in pin}) != fingerprint(pin) or fingerprint(record["payload"]) != pin["hash"]:
        raise ValueError("Pinned report addition version/hash/kind does not match: " + pin["id"])
    return record


def source_pin(record):
    return {key: record[key] for key in ("id", "version", "hash")}


def theory_documents(paths):
    documents = []
    for relative in paths:
        path = REPO_ROOT / relative
        data = path.read_bytes()
        documents.append({"repository_path": relative, "local_path": str(path.resolve()),
                          "local_uri": path.resolve().as_uri(), "sha256": hashlib.sha256(data).hexdigest(),
                          "snapshot": data.decode("utf-8"),
                          "scope": "Local theory-note snapshot at generation, not an immutable scientific object or calibrated adjudication."})
    return documents


def collect_measurement_sensitivity(records, pins=MEASUREMENT_PINS):
    from swarm_lab.name_eligibility_sensitivity import audit_name_eligibility_sensitivity
    from swarm_lab.mention_graph_sensitivity import compare_name_graphs
    objects = {name: read_pinned(records, pin) for name, pin in pins.items()}
    dataset = objects["dataset"]
    expected = source_pin(dataset)
    for name in ("unicode", "eligibility", "graphs"):
        if objects[name]["payload"].get("dataset_ref") != expected:
            raise ValueError("Measurement addition is bound to a different dataset version: " + name)
    unicode, eligibility, graphs = [objects[name]["payload"] for name in ("unicode", "eligibility", "graphs")]
    if graphs.get("eligibility_audit_ref") != source_pin(objects["eligibility"]):
        raise ValueError("Graph sensitivity is bound to a different eligibility audit version")
    if len({x["source_fingerprint"] for x in (unicode, eligibility, graphs)}) != 1 or len({x["roster_fingerprint"] for x in (unicode, eligibility, graphs)}) != 1:
        raise ValueError("Measurement source/roster fingerprints disagree")
    messages = [m for m in dataset["payload"]["messages"] if m.get("agent_id")]
    agents = dataset["payload"]["agents"]

    def recompute():
        fresh = audit_name_eligibility_sensitivity(messages, agents,
                    short_name_allowlist=eligibility["requested_names"], include_unicode_shadow=True)
        rebuilt = compare_name_graphs(messages, fresh, agents=agents)
        pairs = lambda events: {(e["message_id"], e["target_agent_id"]) for e in events}
        checks = {"source_and_roster_match": all(fresh[k] == eligibility[k] for k in ("source_fingerprint", "roster_fingerprint")),
                  "exact_baseline_pairs": pairs(fresh["baseline_exact_events"]) == pairs(unicode["exact_events"]),
                  "unicode_baseline_pairs": pairs(fresh["unicode_shadow"]["baseline_shadow_events"]) == pairs(unicode["shadow_events"]),
                  "short_candidate_pairs": pairs(fresh["short_name_exact_events"]) == pairs(eligibility["short_name_exact_events"]),
                  "eligibility_summary": fresh["summary"] == eligibility["summary"],
                  "common_node_universe": rebuilt["node_universe"] == graphs["node_universe"],
                  "variant_counts_and_directed_metrics": all(rebuilt["variants"][name][key] == variant[key]
                      for name, variant in graphs["variants"].items() for key in ("counts", "metrics")),
                  "spectral_statistics": all(rebuilt["variants"][name]["spectral"] == variant["spectral"]
                      for name, variant in graphs["variants"].items())}
        return {"passed": all(checks.values()), "checks": checks, "model_calls": 0,
                "scope": "Recomputed name-pattern candidates and diagnostic operators; address, delivery and influence remain unverified."}

    variants = {name: {key: copy.deepcopy(variant[key]) for key in ("available", "label", "counts", "metrics", "spectral")}
                for name, variant in graphs["variants"].items()}
    return {"references": {name: reference(obj) for name, obj in objects.items()},
            "dataset_fingerprint": dataset["payload"]["fingerprint"], "source_fingerprint": eligibility["source_fingerprint"],
            "roster_fingerprint": eligibility["roster_fingerprint"], "scope": eligibility["scope"],
            "analysis_versions": {name: objects[name]["payload"]["analysis_version"] for name in ("unicode", "eligibility", "graphs")},
            "eligibility_policy": eligibility["eligibility_policy"], "allowlist_resolution": eligibility["allowlist_resolution"],
            "unicode_summary": unicode["summary"], "eligibility_summary": eligibility["summary"],
            "node_universe": graphs["node_universe"], "variants": variants,
            "short_name_candidates": copy.deepcopy(eligibility["short_name_exact_events"]),
            "proof": safe_check(recompute), "stored_validation": graphs["validation"],
            "object_payload_hash_checks": [{**reference(obj), "passed": True} for obj in objects.values()],
            "theory_notes": theory_documents(("research/theory/graph-math-methods.md", "research/theory/communication-falsifiers.md", "research/theory/short-name-adjudication.md")),
            "scope_note": "Same source, different measurement rules on a fixed diagnostic universe; not new agents, behavioral change, confirmed address, a delivery hub or influence. Original graphs and analyses remain unchanged.",
            "model_calls": 0}


def collect_resource_workflow(records, pins=RESOURCE_PINS):
    from swarm_lab.resource_environment import fingerprint as execution_fingerprint, offline_resource_policy
    from swarm_lab.resource_experiments import replay_resource_report
    from swarm_lab.resource_claims import build_resource_fact_ledger
    objects = {name: read_pinned(records, pin) for name, pin in pins.items()}
    result, protocol = objects["result"], objects["protocol"]
    path, raw = load_raw(result)
    if raw.get("status") != "complete" or raw.get("study_kind") != "exclusive_resource_reminder" or raw.get("backend", {}).get("mode") != "scripted_offline_smoke_test":
        raise ValueError("The resource addition must be the reviewed complete scripted workflow, not live subject evidence")
    if raw.get("report_hash") != result["payload"].get("canonical_execution_report_hash") or execution_fingerprint({k:v for k,v in raw.items() if k != "report_hash"}) != raw["report_hash"]:
        raise ValueError("Resource raw report does not match its registered canonical execution hash")
    if result["payload"].get("protocol_id") != protocol["id"] or raw["protocol"] != protocol["payload"]["protocol"]:
        raise ValueError("Resource result is bound to a different frozen protocol")
    expected = source_pin(result)
    if any(objects[name]["payload"].get("result_ref") != expected for name in ("verification", "claims")):
        raise ValueError("Resource replay or claim audit is bound to a different result version")
    ledger = build_resource_fact_ledger(raw, report_id=result["id"], source_ref=expected, source_object=result)
    claim_payload = objects["claims"]["payload"]
    checked = audit_claims(ledger, claim_payload["claims"])
    runs = raw["runs"]
    quantities = {"scripted_swarms": len(runs), "declared_tasks": len(runs)*8,
                  "executed_completed_tasks": sum(sum(tasks.values()) for run in runs for tasks in run["outcomes"]["per_agent_completed"].values()),
                  "action_slots": sum(len(run["turns"]) for run in runs),
                  "all_actions_match_current_context_independent_policy": all(offline_resource_policy(turn["request"]) == turn["action"] for run in runs for turn in run["turns"]),
                  "policy_agreement_scope": "Current policy agrees with recorded actions; this does not independently attest their provider origin."}
    return {"references": {name: reference(obj) for name,obj in objects.items()},
            "raw_report_path": str(path), "raw_file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "canonical_execution_report_hash": raw["report_hash"], "backend": raw["backend"],
            "agent_mode": result["payload"]["agent_mode"], "evidence_scope": raw["evidence_scope"],
            "quantities": quantities, "analysis": raw["analysis"], "protocol": raw["protocol"],
            "runs": [{key: run[key] for key in ("run_id", "context", "environment_seed", "initial_state", "outcomes")} for run in runs],
            "proof": safe_check(lambda: replay_resource_report(raw)), "execution_archive": check_execution_archive(path.parent),
            "stored_verification": {**reference(objects["verification"]), "verification": objects["verification"]["payload"]},
            "claim_audit": {**reference(objects["claims"]), "recomputed": checked,
                            "source_fingerprint_matches": claim_payload["audit"]["source_fingerprint"] == ledger["source_fingerprint"],
                            "quantitative_facts_available": ledger["quantitative_facts_available"],
                            "scope": "Typed facts about this scripted execution only; prose, LLM effects and historical mechanisms remain unverified."},
            "object_payload_hash_checks": [{**reference(obj), "passed": True} for obj in objects.values()],
            "theory_notes": theory_documents(("research/theory/resource-study-design.md", "research/theory/communication-falsifiers.md")),
            "scope_note": "Four scripted infrastructure units are separate from every live unit. The policy ignores context; realized schedule differences cannot be empirical reminder effects. Exclusive global computer access, task costs and release dynamics are invented.",
            "model_calls": 0}


def collect_temporal_paths(records, pins=TEMPORAL_PINS):
    """Reproduce the pinned derivation without creating registry objects."""
    from types import SimpleNamespace
    from swarm_lab.temporal_workflow import derive_temporal_paths
    objects = {name: read_pinned(records, pin) for name, pin in pins.items()}
    audit = objects["audit"]
    payload = audit["payload"]
    verification = objects["verification"]["payload"]
    if (fingerprint(verification.get("audit_ref")) != fingerprint(source_pin(audit))
            or verification.get("result_kind") != "temporal_path_audit"):
        raise ValueError("Temporal verification is bound to a different audit version")
    sources = {}
    for name, kind in (("selected_audit", "selected_lead_audit"), ("dataset", "dataset"), ("discovery", "discovery")):
        ref = payload["source_refs"][name]
        sources[name] = read_pinned(records, {**ref, "kind": kind})
    checks = {
        "stored_verification_passed": verification.get("passed") is True,
        "stored_verification_zero_calls": type(verification.get("model_calls")) is int and verification["model_calls"] == 0,
        "exact_dataset_binding": fingerprint(payload.get("dataset_ref")) == fingerprint(source_pin(sources["dataset"])),
        "exact_discovery_binding": fingerprint(payload.get("discovery_ref")) == fingerprint(source_pin(sources["discovery"])),
        "exact_selected_audit_binding": fingerprint(payload.get("selected_audit_ref")) == fingerprint(source_pin(sources["selected_audit"])),
    }
    def recompute():
        ref = source_pin(sources["selected_audit"])
        rebuilt = derive_temporal_paths(SimpleNamespace(store=records), ref["id"], version=ref["version"])
        return {"passed": fingerprint(rebuilt) == audit["hash"], "model_calls": 0,
                "scope": "Pure pinned derivation; verification objects are not persisted by this report."}
    fresh = safe_check(recompute)
    checks["fresh_pinned_source_replay"] = fresh.get("passed") is True
    proof = {"passed": all(checks.values()), "checks": checks, "fresh_replay": fresh, "model_calls": 0,
             "scope": "Exact source audit and temporal derivation replay; no message delivery, influence or historical causal attestation."}
    windows, witnesses = [], []
    if proof["passed"]:
        indexed = {row["id"]: row for row in sources["dataset"]["payload"]["messages"]}
        for window_id, window in sorted(payload["windows"].items()):
            variants = {}
            for name, variant in window["variants"].items():
                if not variant["available"]:
                    variants[name] = {"available": False, "label": variant["label"]}
                    continue
                static_witnesses = [w for w in variant["witnesses"].values() if w["operator"] == "static"]
                reversed_count = sum(any(a["timestamp"] > b["timestamp"] for a, b in zip(w["steps"], w["steps"][1:])) for w in static_witnesses)
                tied_count = sum(any(a["timestamp"] == b["timestamp"] for a, b in zip(w["steps"], w["steps"][1:])) for w in static_witnesses)
                variants[name] = {
                    "available": True, "label": variant["label"], "event_count": variant["event_count"],
                    "static_reachable_pairs": variant["static"]["reachable_pair_count"],
                    "strict_temporal_reachable_pairs": variant["strict_temporal"]["reachable_pair_count"],
                    "static_only_pairs": variant["static_only_pair_count"],
                    "selected_static_witness_reversed_time_count": reversed_count,
                    "selected_static_witness_tied_time_count": tied_count,
                    "selected_static_witness_not_strict_count": sum(not w["strict_timestamp_order"] for w in static_witnesses),
                    "static_node_removal": copy.deepcopy(variant["static"]["node_removal"]),
                    "temporal_node_removal": copy.deepcopy(variant["strict_temporal"]["node_removal"]),
                }
                for pair in variant["static_only_pairs"]:
                    witness = copy.deepcopy(variant["witnesses"][pair["witness_ref"]])
                    evidence = [{key: indexed[identity].get(key) for key in
                                 ("id", "agent_id", "agent_name", "timestamp", "created_at", "room_id", "content", "content_hash", "source")}
                                for identity in dict.fromkeys(witness["message_ids"])]
                    witnesses.append({"window_id": window_id, "variant": name, "witness_ref": pair["witness_ref"],
                                      "witness": witness, "source_messages": evidence})
            windows.append({"window_id": window_id, "scope": copy.deepcopy(window["scope"]),
                            "message_count": window["message_count"], "human_message_count": window["human_message_count"],
                            "node_universe": copy.deepcopy(window["node_universe"]), "variants": variants})
    return {"references": {**{name: reference(obj) for name, obj in objects.items()},
                            **{name: reference(obj) for name, obj in sources.items()}},
            "proof": proof, "stored_verification": copy.deepcopy(verification),
            "scope": copy.deepcopy(payload["scope"]), "configuration": copy.deepcopy(payload["configuration"]),
            "source_binding": copy.deepcopy(payload["source_binding"]), "code_hashes": copy.deepcopy(payload["code_hashes"]),
            "original_comparisons": copy.deepcopy(payload["original_comparisons"]),
            "definitions": copy.deepcopy(payload["definitions"]), "limitations": copy.deepcopy(payload["limitations"]),
            "windows": windows, "static_only_witnesses": witnesses,
            "retained_unverified_windows": copy.deepcopy(payload["windows"]) if not proof["passed"] else {},
            "quantity_scope": "Pairs are ordered and room/window-specific, not independent units. Reversed/tied selected static witness counts can overlap and do not imply absence of alternate temporal paths; static-only counts recompute all routes.",
            "theory_notes": theory_documents(("research/theory/temporal-path-interpretation.md",)), "model_calls": 0}


def collect_timed_resource_workflow(records, pins=TIMED_RESOURCE_PINS):
    """Read and replay the separately registered scripted timing workflow."""
    from swarm_lab.timed_resource_experiments import OFFLINE_BACKEND, replay_timed_resource_report, timed_resource_infrastructure_policy
    from swarm_lab.resource_environment import fingerprint as execution_fingerprint
    objects = {name: read_pinned(records, pin) for name, pin in pins.items()}
    result, registration = objects["result"], objects["protocol"]
    stored = result["payload"]
    protocol = registration["payload"]["protocol"]
    verification = objects["verification"]["payload"]
    if (fingerprint(verification.get("result_ref")) != fingerprint(source_pin(result))
            or verification.get("result_kind") != "timed_resource_experiment"):
        raise ValueError("Timed verification is bound to a different result version")
    if fingerprint(protocol["subject_backend"]) != fingerprint(OFFLINE_BACKEND):
        raise ValueError("The timed resource addition must be the reviewed scripted workflow, not live subject evidence")
    path = Path(stored["artifact_directory"]) / "report.json"
    raw, raw_bytes, load_error = None, None, None
    try:
        raw_bytes = path.read_bytes()
        raw = json.loads(raw_bytes)
    except (OSError, ValueError) as exc:
        load_error = {"error_type": type(exc).__name__, "scope": "Canonical report unavailable; derived quantities withheld."}
    archive = safe_check(lambda: check_execution_archive(path.parent))
    fresh = safe_check(lambda: replay_timed_resource_report(raw, output_dir=path.parent)) if raw is not None else {"passed": False, **load_error}
    raw_core = {k: v for k, v in raw.items() if k != "report_hash"} if isinstance(raw, dict) else {}
    binding = {"protocol_id": registration["id"], "protocol_ref": source_pin(registration),
               "registered_hash": registration["payload"]["frozen_hash"],
               "behavior_id": registration["payload"].get("behavior_id"), "agent_mode": "offline_simulation", "model": OFFLINE_BACKEND["model"]}
    checks = {
        "canonical_report_loaded": isinstance(raw, dict),
        "registered_protocol_hash": fingerprint(protocol) == registration["payload"]["frozen_hash"],
        "stored_registration_bindings": set(binding).issubset(stored) and fingerprint({k: stored[k] for k in binding}) == fingerprint(binding),
        "stored_raw_core": bool(raw_core) and set(raw_core).issubset(stored) and fingerprint({k: stored[k] for k in raw_core}) == fingerprint(raw_core),
        "canonical_report_hash": isinstance(raw, dict) and raw.get("report_hash") == stored.get("canonical_execution_report_hash") and execution_fingerprint(raw_core) == raw.get("report_hash"),
        "exact_raw_protocol": isinstance(raw, dict) and fingerprint(raw.get("protocol")) == fingerprint(protocol),
        "stored_verification_passed": verification.get("passed") is True,
        "stored_verification_zero_calls": type(verification.get("model_calls")) is int and verification["model_calls"] == 0,
        "fresh_full_archive_replay": fresh.get("passed") is True,
        "fresh_source_archive_bytes": archive.get("status") == "verified",
    }
    proof = {"passed": all(checks.values()), "checks": checks, "fresh_replay": fresh, "model_calls": 0,
             "scope": "Pinned scripted world, timing boundaries, requests, oracle and archive; no provider consumption or empirical model-effect attestation."}
    general_execution_passed = proof["passed"]
    def verify_finite_claims():
        from swarm_lab.timed_resource_claims import build_timed_resource_fact_ledger, audit_timed_resource_claims
        from swarm_lab.claim_audit import select_fact_packet
        claim_record = objects["claims"]
        payload = claim_record["payload"]
        ref = source_pin(result)
        verification_ref = payload["verification_ref"]
        objects["claim_verification"] = read_pinned(records, {**verification_ref, "kind": "verification"})
        claim_verification = objects["claim_verification"]
        def trusted_host_gate(candidate):
            exact = fingerprint(candidate) == fingerprint(raw)
            return {"passed": general_execution_passed and exact, "model_calls": 0,
                    "result_ref": copy.deepcopy(ref), "report_hash": raw["report_hash"], "protocol_hash": raw["protocol_hash"]}
        ledger = build_timed_resource_fact_ledger(raw, report_id=result["id"], source_ref=ref,
                                                 source_object=result, replay_check=trusted_host_gate)
        checked = audit_timed_resource_claims(ledger, payload["claims"])
        rebuilt_packet = select_fact_packet(ledger, list(payload["fact_packet"]["facts"]), max_facts=24)
        claim_checks = {
            "exact_result_binding": fingerprint(payload.get("result_ref")) == fingerprint(ref) and payload.get("experiment_id") == result["id"] and payload.get("result_kind") == result["kind"],
            "exact_verification_binding": fingerprint(verification_ref) == fingerprint(source_pin(claim_verification)),
            "same_authenticated_verification_payload": fingerprint(claim_verification["payload"]) == fingerprint(verification),
            "canonical_report_binding": payload.get("canonical_execution_report_hash") == raw["report_hash"],
            "fresh_ledger_quantities_available": ledger["quantitative_facts_available"] is True,
            "stored_quantities_available": payload.get("quantitative_facts_available") is True,
            "source_fingerprint_binding": payload["audit"].get("source_fingerprint") == ledger["source_fingerprint"] and payload["fact_packet"].get("source_fingerprint") == ledger["source_fingerprint"],
            "exact_finite_fact_packet": fingerprint(rebuilt_packet) == fingerprint(payload["fact_packet"]),
            "strict_claim_recheck": checked["all_executable_claims_supported"] is True and bool(checked["supported_fact_ids"]),
            "stored_audit_matches_recheck": fingerprint(checked) == fingerprint(payload["audit"]),
        }
        return {"passed": all(claim_checks.values()), "checks": claim_checks, "quantitative_facts_available": ledger["quantitative_facts_available"],
                "source_fingerprint": ledger["source_fingerprint"], "ledger_hash": ledger["ledger_hash"],
                "extractor_source_hash": ledger["extractor_source_hash"], "recomputed": checked,
                "retained_claims": copy.deepcopy(payload["claims"]), "ledger_verification_checks": ledger["verification_checks"],
                "scope": "Approved finite fact text only. Attached model prose, mechanisms and historical or provider claims remain unverified.", "model_calls": 0}
    if "claims" not in objects:
        claim_check = {"passed": False, "reason": "Optional stored claim audit was not included; finite tables are withheld.", "model_calls": 0}
    elif not general_execution_passed:
        claim_check = {"passed": False, "reason": "General execution/source/archive proof failed before the finite-fact gate.", "model_calls": 0}
    else:
        claim_check = safe_check(verify_finite_claims)
    proof["general_execution_passed"] = general_execution_passed
    proof["checks"]["finite_claim_bindings_and_strict_recheck"] = claim_check.get("passed") is True
    proof["passed"] = general_execution_passed and claim_check.get("passed") is True
    quantities, analysis, runs = None, None, []
    if proof["passed"]:
        quantities = {"scripted_swarms": len(raw["runs"]), "independent_seed_blocks": len({r["block_id"] for r in raw["runs"]}),
            "declared_tasks": len(raw["runs"]) * 8,
            "executed_completed_tasks": sum(sum(tasks.values()) for run in raw["runs"] for tasks in run["outcomes"]["per_agent_completed"].values()),
            "eligible_preparations": sum(r["counts"]["eligible_preparations"] for r in raw["runs"]),
            "recorded_receipts": sum(r["counts"]["recorded_receipts"] for r in raw["runs"]),
            "subject_call_attempts": sum(r["counts"]["subject_call_attempts"] for r in raw["runs"]),
            "applied_actions": sum(r["counts"]["applied_actions"] for r in raw["runs"]),
            "never_delivered_completed_swarms": sum(r["counts"]["recorded_receipts"] == 0 for r in raw["runs"]),
            "all_actions_match_current_context_independent_policy": all(fingerprint(timed_resource_infrastructure_policy(t["request"])) == fingerprint(t["action"]) for r in raw["runs"] for t in r["turns"]),
            "policy_agreement_scope": "Recorded actions agree with the notes-ignored fixture; this does not authenticate provider use."}
        analysis = copy.deepcopy(raw["analysis"])
        for run in raw["runs"]:
            receipts = [{k: copy.deepcopy(boundary[k]) for k in ("step", "agent_id", "mode", "trigger_output", "local_receipt", "subject_request_hash")}
                        for boundary in run["boundaries"] if boundary["local_receipt"] is not None]
            runs.append({k: copy.deepcopy(run[k]) for k in ("run_id", "block_id", "context", "environment_seed", "initial_world_identity", "outcomes", "counts")})
            runs[-1]["receipt_boundaries"] = receipts
            runs[-1]["policy_itt"] = copy.deepcopy(run["timing_report"]["policy_itt"])
    return {"references": {name: reference(obj) for name, obj in objects.items()}, "proof": proof,
            "raw_report_path": str(path), "raw_file_sha256": hashlib.sha256(raw_bytes).hexdigest() if raw_bytes is not None else None,
            "canonical_execution_report_hash": stored["canonical_execution_report_hash"], "execution_archive": archive,
            "claim_audit": claim_check,
            "hash_purposes": {"raw_file_sha256": "Exact bytes of the report file read for this derivation.",
                              "canonical_execution_report_hash": "Compact finite JSON execution body, excluding report_hash; distinct from the registry's spaced JSON hash."},
            "stored_verification": copy.deepcopy(verification), "protocol": copy.deepcopy(protocol),
            "backend": copy.deepcopy(raw.get("backend")) if isinstance(raw, dict) else None,
            "quantities": quantities, "analysis": analysis, "runs": runs,
            "retained_unverified_recorded_analysis": copy.deepcopy(raw.get("analysis")) if isinstance(raw, dict) and not proof["passed"] else None,
            "scope_note": "Separate CPU infrastructure: notes are ignored. Four swarms form two independent paired seed blocks; neither agents, tasks, receipts nor turns add independent units. No empirical LLM reminder effect or pooling with prior studies.",
            "theory_notes": theory_documents(("research/theory/intervention-timing.md",)), "model_calls": 0}


def collect_source_lineage(records, pins=SOURCE_LINEAGE_PINS):
    """Pure bounded file reread; no saved coverage or verifier substitutes for it."""
    from swarm_lab.source_workflow import derive_source_links, implementation_hashes, WORKFLOW_VERSION
    requested = {name: {k: copy.deepcopy(pin[k]) for k in ("id", "version", "kind", "hash") if k in pin}
                 for name, pin in pins.items() if name in ("audit", "verification") and type(pin) is dict} if type(pins) is dict else {}
    addition = {"references": {}, "requested_pins": requested, "quantities": None,
                "coverage": [], "matched_coordinates": [], "scan_plan": None,
                "scope_note": "Retrospective known-prefix probe, with explicit parent-ID selection. Counts describe retained/scanned rows only. No prevalence estimate, April-window corroboration, receipt, tool success, causal finding or independent experimental units.",
                "model_calls": 0, "theory_notes": []}
    proof = {"passed": False, "checks": {}, "filesystem_reread_attempted": False,
             "filesystem_reread_completed": False, "model_calls": 0,
             "scope": "Exact versioned records, current implementation hashes and fresh bounded filesystem bytes; no provider-input, recipient-exposure or historical causal attestation."}
    addition["proof"] = proof
    try:
        if type(pins) is not dict or set(pins) != {"audit", "verification"}:
            raise ValueError("Source lineage requires exact audit and verification pins")
        objects = {name: read_pinned(records, pin) for name, pin in pins.items()}
    except (ValueError, KeyError, TypeError) as exc:
        proof.update(reason="source_record_pin_unavailable_or_invalid", error_type=type(exc).__name__)
        return addition
    addition["references"] = {name: reference(obj) for name, obj in objects.items()}
    audit, verification = objects["audit"], objects["verification"]["payload"]
    payload = audit["payload"]
    if type(payload) is not dict or type(verification) is not dict:
        proof["reason"] = "source_record_payload_shape_invalid"
        return addition
    try:
        current = implementation_hashes()
    except OSError as exc:
        proof.update(reason="source_implementation_unavailable", error_type=type(exc).__name__)
        return addition
    checks = {
        "exact_record_kinds": audit["kind"] == "source_link_audit" and objects["verification"]["kind"] == "verification",
        "exact_verification_binding": fingerprint(verification.get("audit_ref")) == fingerprint(source_pin(audit)) and verification.get("result_kind") == "source_link_audit",
        "stored_verification_passed": verification.get("passed") is True,
        "stored_verification_zero_calls": type(verification.get("model_calls")) is int and verification["model_calls"] == 0,
        "stored_reread_complete": verification.get("filesystem_reread_attempted") is True and verification.get("filesystem_reread_completed") is True,
        "exact_workflow_version": payload.get("workflow_version") == WORKFLOW_VERSION,
        "current_implementation_hashes": fingerprint(payload.get("implementation_hashes")) == fingerprint(current),
        "scan_plan_hash": fingerprint(payload.get("plan")) == payload.get("plan_hash"),
        "zero_model_calls": type(payload.get("model_calls")) is int and payload["model_calls"] == 0,
        "raw_rows_not_persisted": payload.get("raw_records_persisted") is False,
    }
    proof["checks"] = checks
    addition["implementation_hashes"] = copy.deepcopy(current)
    plan_hash = payload.get("plan_hash")
    addition["plan_hash"] = plan_hash if type(plan_hash) is str and len(plan_hash) == 64 else None
    if not all(checks.values()):
        proof["reason"] = "source_record_binding_plan_or_implementation_mismatch"
        return addition
    addition["stored_verification"] = {k: copy.deepcopy(verification[k]) for k in
        ("audit_ref", "result_kind", "passed", "model_calls", "filesystem_reread_attempted", "filesystem_reread_completed")}
    derived = None
    def reread():
        nonlocal derived
        derived = derive_source_links(payload["plan"])
        digest = fingerprint(derived)
        stable = fingerprint(derived.get("implementation_hashes")) == fingerprint(current) == fingerprint(implementation_hashes())
        return {"passed": digest == audit["hash"] and stable, "derived_payload_hash": digest,
                "implementation_hashes_stable": stable, "model_calls": 0}
    proof["filesystem_reread_attempted"] = True
    fresh = safe_check(reread)
    proof["fresh_derivation"] = fresh
    proof["filesystem_reread_completed"] = derived is not None
    checks["fresh_whole_payload_reproduced"] = fresh.get("passed") is True
    proof["passed"] = all(checks.values())
    proof["reason"] = "reproduced" if proof["passed"] else "fresh_source_or_derivation_unavailable_or_mismatched"
    if not proof["passed"]:
        return addition
    joined = derived["source_link_audit"]
    relations = joined["relations"]
    statuses = Counter(r["status"] for r in relations)
    matched = [r for r in relations if r["status"] in ("verified_platform_emission_record", "verified_exported_fk")]
    scans = derived["source_readset"]
    addition["quantities"] = {
        "retained_rows": sum(s["coverage"]["retained_rows"] for s in scans.values()),
        "explicit_relation_attempts": len(relations), "scoped_matches": len(matched),
        "matched_chat_emissions": sum(r["relation_kind"] == "event_message_fk" for r in matched),
        "matched_session_links": sum(r["relation_kind"] != "event_message_fk" for r in matched),
        "parents_unresolved_in_scanned_scope": statuses["missing_parent_in_scanned_scope"],
        "missing_foreign_keys": statuses["missing_foreign_key"], "relation_status_counts": dict(statuses),
        "scanned_tables": len(scans), "partial_tables": sum(not s["coverage"]["complete_scan"] for s in scans.values()),
    }
    addition["scan_plan"] = copy.deepcopy(derived["plan"])
    addition["expected_row_pins_checked"] = derived["expected_row_pins_checked"]
    addition["limitations"] = copy.deepcopy(joined["limitations"])
    addition["global_source_completeness"] = joined["global_source_completeness"]
    for name, scan in scans.items():
        addition["coverage"].append({"table": name, "source_path": scan["source_path"],
            "coverage": copy.deepcopy(scan["coverage"]), "limits": copy.deepcopy(scan["limits"]),
            "selection": copy.deepcopy(scan["selection"]), "observed_source": copy.deepcopy(scan["observed_source"]),
            "packet_sha256": scan["packet_sha256"],
            "source_metadata_verified": False,
            "metadata_declaration_hash": joined["source_scans"][name]["source_metadata_declaration_hash"]})
    addition["matched_coordinates"] = [{k: copy.deepcopy(r.get(k)) for k in
        ("relation_kind", "status", "child_source", "child_row_ref", "parent_source", "parent_row_ref",
         "foreign_key_field", "foreign_key", "child_identity_validation", "parent_group_record_id",
         "field_checks", "timestamp_difference_ms", "timestamp_validation", "endpoint_scope",
         "global_parent_uniqueness", "receipt", "consumption", "causal_influence")} for r in matched]
    return addition


def collect_indexed_events(records, pins=None):
    """Reopen the authenticated local index; never export a stale saved count."""
    from types import SimpleNamespace
    from swarm_lab.indexed_event_workflow import derive_indexed_event_audit, implementation_hashes, WORKFLOW_VERSION
    pins = INDEXED_EVENT_PINS if pins is None else pins
    addition = {"references": {}, "quantities": None, "windows": [], "emissions": [],
                "events": [], "coverage": None, "index_build": None, "query": None,
                "index_artifact_binding": None, "theory_notes": [], "model_calls": 0,
                "scope_note": "Original selected windows and explicit indexed event fields only. Local index replay does not reread the original event object. No recipient reception, reading, influence, tool success, graph merge, prevalence or library status promotion."}
    proof = {"passed": False, "checks": {}, "model_calls": 0,
             "index_artifact_reread_attempted": False, "index_artifact_reread_completed": False,
             "full_event_source_reread": False}
    addition["proof"] = proof
    try:
        if type(pins) is not dict or set(pins) != {"audit", "verification"}:
            raise ValueError("Exact indexed-event audit and verification pins required")
        objects = {name: read_pinned(records, pin) for name, pin in pins.items()}
        saved, verification = objects["audit"], objects["verification"]["payload"]
        payload = saved["payload"]
        if type(payload) is not dict or type(verification) is not dict:
            raise ValueError("Exact indexed-event payload shapes required")
        addition["references"] = {name: reference(obj) for name, obj in objects.items()}
        current = implementation_hashes()
        checks = {
            "exact_record_kinds": saved["kind"] == "indexed_event_audit" and objects["verification"]["kind"] == "verification",
            "exact_verification_binding": fingerprint(verification.get("audit_ref")) == fingerprint(source_pin(saved)) and verification.get("result_kind") == "indexed_event_audit",
            "stored_verification_passed": verification.get("passed") is True,
            "stored_local_index_reread_completed": verification.get("index_artifact_reread_attempted") is True and verification.get("index_artifact_reread_completed") is True,
            "no_full_source_reread_claim": verification.get("full_event_source_reread") is False,
            "stored_zero_model_calls": type(verification.get("model_calls")) is int and verification["model_calls"] == 0,
            "zero_model_calls": type(payload.get("model_calls")) is int and payload["model_calls"] == 0,
            "raw_content_not_persisted": payload.get("raw_content_persisted") is False,
            "exact_workflow_version": payload.get("workflow_version") == WORKFLOW_VERSION,
            "current_implementation_hashes": fingerprint(payload.get("implementation_hashes")) == fingerprint(current),
        }
        proof["checks"] = checks
        if not all(checks.values()):
            proof["reason"] = "indexed_record_binding_or_implementation_mismatch"
            return addition
        for name, kind, ref in (("index", "event_source_index", payload["index_ref"]),
                                ("selected", "selected_lead_audit", payload["selected_audit_ref"]),
                                ("dataset", "dataset", payload["source_refs"]["dataset"]),
                                ("discovery", "discovery", payload["source_refs"]["discovery"])):
            if type(ref) is not dict or set(ref) != {"id", "version", "hash"}:
                raise ValueError("Exact source reference shape required")
            objects[name] = read_pinned(records, {**ref, "kind": kind})
        checks["selected_source_binding"] = fingerprint(payload["source_refs"]["selected_audit"]) == fingerprint(payload["selected_audit_ref"])
        addition["references"] = {name: reference(obj) for name, obj in objects.items()}
        if not checks["selected_source_binding"]:
            proof["reason"] = "indexed_selected_source_binding_mismatch"
            return addition
        proof["index_artifact_reread_attempted"] = True
        fresh = derive_indexed_event_audit(SimpleNamespace(store=records), payload["index_ref"],
                    payload["selected_audit_ref"]["id"], version=payload["selected_audit_ref"]["version"],
                    max_query_rows=payload["query"]["max_rows"])
        proof["index_artifact_reread_completed"] = True
        checks["fresh_whole_payload_reproduced"] = fingerprint(fresh) == saved["hash"]
        checks["implementation_hashes_stable"] = fingerprint(fresh["implementation_hashes"]) == fingerprint(current) == fingerprint(implementation_hashes())
        proof["passed"] = all(checks.values())
        proof["reason"] = "reproduced" if proof["passed"] else "fresh_index_or_source_derivation_mismatch"
        if not proof["passed"]:
            return addition
        audit = fresh["indexed_event_audit"]
        addition.update(quantities=copy.deepcopy(audit["counts"]), windows=copy.deepcopy(audit["windows"]),
                        coverage=copy.deepcopy(audit["coverage"]), query=copy.deepcopy(fresh["query"]),
                        index_artifact_binding=copy.deepcopy(audit["index_artifact_binding"]),
                        implementation_hashes=copy.deepcopy(current), query_packet_hash=fresh["query_packet_hash"],
                        limitations=copy.deepcopy(audit["limitations"]))
        # Explicit export allowlists: neither provider payload nor chat text enters this section.
        addition["emissions"] = [{k: copy.deepcopy(row[k]) for k in
            ("message_id", "parent_source", "original_window_ids", "emission_status", "candidate_count",
             "ambiguity_status", "field_checks", "timestamp_difference_ms", "candidate_event_refs", "parent_speaker_category")}
            for row in audit["emissions"]]
        addition["events"] = [{k: copy.deepcopy(row[k]) for k in
            ("event_ref", "event_id", "source", "projection_sha256", "created_at", "action_type",
             "actor_id", "actor_field", "actor_status", "room_id", "original_window_ids", "unassigned_reasons")}
            for row in audit["events"]]
        metadata = objects["index"]["payload"]["build_metadata"]
        addition["index_build"] = {k: copy.deepcopy(metadata[k]) for k in
            ("coverage", "artifact", "observed_source", "declaration_comparison")}
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        proof.update(passed=False, reason="indexed_record_index_or_source_unavailable_or_invalid", error_type=type(exc).__name__)
        # A late failure must not retain a partly populated verified presentation.
        for key, empty in (("quantities", None), ("windows", []), ("emissions", []), ("events", []),
                           ("coverage", None), ("index_build", None), ("query", None), ("index_artifact_binding", None)):
            addition[key] = empty
    return addition


def collect_actor_events(records, pins=None):
    """Fresh exact-source actor/time derivation; no audit or proof is persisted."""
    from types import SimpleNamespace
    from swarm_lab.actor_event_workflow import derive_selected_actor_events, implementation_hashes, WORKFLOW_VERSION
    pins = ACTOR_EVENT_PINS if pins is None else pins
    addition = {"references": {}, "quantities": None, "by_actor": {}, "by_window": {},
                "coverage": None, "query": None, "original_windows": [], "source_scope": None,
                "record_pins": [], "author_source_pins": [], "index_binding": None,
                "timestamp_policy_counts": None, "timestamp_policy_scope": None,
                "theory_notes": [], "model_calls": 0,
                "scope_note": "Exact agent authors from original selected chats, then actor/time/action events without a room predicate. Missing rooms remain unassigned. No delivery, inactivity, lease, task success or causal behavior; no graph or library status changes and no independent experimental units."}
    proof = {"passed": False, "checks": {}, "model_calls": 0,
             "index_artifact_reread_attempted": False, "index_artifact_reread_completed": False,
             "full_event_source_reread": False}
    addition["proof"] = proof
    try:
        if type(pins) is not dict or set(pins) != {"audit", "verification"}:
            raise ValueError("Exact actor-event audit and verification pins required")
        objects = {name: read_pinned(records, pin) for name, pin in pins.items()}
        saved, verification = objects["audit"], objects["verification"]["payload"]
        payload = saved["payload"]
        if type(payload) is not dict or type(verification) is not dict:
            raise ValueError("Exact actor-event payload shapes required")
        addition["references"] = {name: reference(obj) for name, obj in objects.items()}
        current = implementation_hashes()
        checks = {
            "exact_record_kinds": saved["kind"] == "actor_event_audit" and objects["verification"]["kind"] == "verification",
            "exact_verification_binding": fingerprint(verification.get("audit_ref")) == fingerprint(source_pin(saved)) and verification.get("result_kind") == "actor_event_audit",
            "stored_verification_passed": verification.get("passed") is True,
            "stored_local_index_reread_completed": verification.get("index_artifact_reread_attempted") is True and verification.get("index_artifact_reread_completed") is True,
            "no_full_source_reread_claim": verification.get("full_event_source_reread") is False,
            "stored_zero_model_calls": type(verification.get("model_calls")) is int and verification["model_calls"] == 0,
            "zero_model_calls": type(payload.get("model_calls")) is int and payload["model_calls"] == 0,
            "raw_content_not_persisted": payload.get("raw_content_persisted") is False,
            "no_status_promotion": payload.get("status_promotion") is False,
            "source_audit_replay_passed": payload.get("source_audit_replay_passed") is True,
            "exact_workflow_version": payload.get("workflow_version") == WORKFLOW_VERSION,
            "current_implementation_hashes": fingerprint(payload.get("implementation_hashes")) == fingerprint(current),
        }
        proof["checks"] = checks
        if not all(checks.values()):
            proof["reason"] = "actor_record_binding_or_implementation_mismatch"
            return addition
        for name, kind, ref in (("index", "event_source_index", payload["index_ref"]),
                                ("selected", "selected_lead_audit", payload["selected_audit_ref"]),
                                ("dataset", "dataset", payload["source_refs"]["dataset"]),
                                ("discovery", "discovery", payload["source_refs"]["discovery"])):
            if type(ref) is not dict or set(ref) != {"id", "version", "hash"}:
                raise ValueError("Exact source reference shape required")
            objects[name] = read_pinned(records, {**ref, "kind": kind})
        checks["selected_source_binding"] = fingerprint(payload["source_refs"]["selected_audit"]) == fingerprint(payload["selected_audit_ref"])
        addition["references"] = {name: reference(obj) for name, obj in objects.items()}
        if not checks["selected_source_binding"]:
            proof["reason"] = "actor_selected_source_binding_mismatch"
            return addition
        proof["index_artifact_reread_attempted"] = True
        query = payload["query"]
        fresh = derive_selected_actor_events(SimpleNamespace(store=records), payload["index_ref"], payload["selected_audit_ref"],
                    max_rows=query["max_rows"], max_candidate_rows=query["max_candidate_rows"], action_types=query["action_types"])
        proof["index_artifact_reread_completed"] = True
        checks["fresh_whole_payload_reproduced"] = fingerprint(fresh) == saved["hash"]
        checks["implementation_hashes_stable"] = fingerprint(fresh["implementation_hashes"]) == fingerprint(current) == fingerprint(implementation_hashes())
        proof["passed"] = all(checks.values())
        proof["reason"] = "reproduced" if proof["passed"] else "fresh_actor_index_or_source_derivation_mismatch"
        if not proof["passed"]:
            return addition
        summary = fresh["actor_event_summary"]
        addition.update(quantities=copy.deepcopy(summary["total"]), by_actor=copy.deepcopy(summary["by_actor"]),
                        by_window=copy.deepcopy(summary["by_window"]), coverage=copy.deepcopy(summary["coverage"]),
                        query=copy.deepcopy(fresh["query"]), original_windows=copy.deepcopy(fresh["original_windows"]),
                        source_scope=copy.deepcopy(fresh["source_scope"]), index_binding=copy.deepcopy(summary["index_binding"]),
                        query_packet_hash=fresh["query_packet_hash"], implementation_hashes=copy.deepcopy(current),
                        timestamp_policy_counts=copy.deepcopy(fresh["timestamp_policy_counts"]),
                        timestamp_policy_scope=fresh["timestamp_policy_scope"], limitations=copy.deepcopy(summary["limitations"]))
        # Allowlisted identities/hashes only: no chat text or provider output is exported.
        addition["record_pins"] = [{k: copy.deepcopy(row[k]) for k in
            ("event_id", "source", "projection_sha256", "room_observation", "window_ids")}
            for row in summary["record_pins"]]
        addition["author_source_pins"] = [{k: copy.deepcopy(row[k]) for k in
            ("message_id", "agent_id", "speaker_id", "speaker_type", "timestamp", "room_id", "source",
             "original_window_ids", "normalized_record_sha256", "declared_compound_content_hash")}
            for row in fresh["author_source_pins"]]
        note = "research/theory/actor-time-observation-contract.md"
        if (REPO_ROOT / note).is_file():
            addition["theory_notes"] = theory_documents([note])
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        proof.update(passed=False, reason="actor_record_index_or_source_unavailable_or_invalid", error_type=type(exc).__name__)
        for key, empty in (("quantities", None), ("by_actor", {}), ("by_window", {}), ("coverage", None),
                           ("query", None), ("original_windows", []), ("source_scope", None), ("record_pins", []),
                           ("author_source_pins", []), ("index_binding", None), ("timestamp_policy_counts", None), ("timestamp_policy_scope", None)):
            addition[key] = empty
    return addition


def collect_graph_hodge(records, pins=None):
    """Fresh whole-payload source/operator reproduction before exposing quantities."""
    from types import SimpleNamespace
    from swarm_lab.graph_hodge_workflow import derive_edge_flow, implementation_hashes, WORKFLOW_VERSION
    pins = GRAPH_HODGE_PINS if pins is None else pins
    addition = {"references": {}, "quantities": None, "cells": [], "configuration": None,
                "theory_notes": [], "model_calls": 0,
                "display_tolerance": HODGE_DISPLAY_TOLERANCE,
                "scope_note": "Static net directional named-reference counts; all fixed parent cells, no ranking or independent units. Time order is discarded; unspecified faces leave curl and harmonic unknown. No physical traffic, hierarchy, rumor, chronological relay, continuum-LBO, novelty or causal attestation."}
    proof = {"passed": False, "checks": {}, "model_calls": 0,
             "source_replay_attempted": False, "source_replay_completed": False,
             "raw_upstream_source_reread": False}
    addition["proof"] = proof
    try:
        if type(pins) is not dict or set(pins) != {"audit", "verification"}:
            raise ValueError("Exact edge-flow audit and verification pins required")
        objects = {name: read_pinned(records, pin) for name, pin in pins.items()}
        saved, verification = objects["audit"], objects["verification"]["payload"]
        payload = saved["payload"]
        if type(payload) is not dict or type(verification) is not dict:
            raise ValueError("Exact edge-flow payload shapes required")
        addition["references"] = {name: reference(obj) for name, obj in objects.items()}
        current = implementation_hashes()
        checks = {
            "exact_record_kinds": saved["kind"] == "graph_hodge_audit" and objects["verification"]["kind"] == "verification",
            "exact_verification_binding": fingerprint(verification.get("audit_ref")) == fingerprint(source_pin(saved)) and verification.get("result_kind") == "graph_hodge_audit",
            "stored_verification_passed": verification.get("passed") is True,
            "stored_source_replay_completed": verification.get("source_replay_attempted") is True and verification.get("source_replay_completed") is True,
            "stored_zero_model_calls": type(verification.get("model_calls")) is int and verification["model_calls"] == 0,
            "zero_model_calls": type(payload.get("model_calls")) is int and payload["model_calls"] == 0,
            "raw_content_not_persisted": payload.get("raw_content_persisted") is False,
            "no_status_promotion": payload.get("status_promotion") is False,
            "source_audit_replay_passed": payload.get("source_audit_replay_passed") is True,
            "exact_workflow_version": payload.get("workflow_version") == WORKFLOW_VERSION,
            "current_implementation_hashes": fingerprint(payload.get("implementation_hashes")) == fingerprint(current),
        }
        proof["checks"] = checks
        if not all(checks.values()):
            proof["reason"] = "edge_flow_record_binding_or_implementation_mismatch"
            return addition
        for name, kind in (("temporal_audit", "temporal_path_audit"), ("selected_audit", "selected_lead_audit"),
                           ("dataset", "dataset"), ("discovery", "discovery")):
            ref = payload["source_refs"][name]
            if type(ref) is not dict or set(ref) != {"id", "version", "hash"}:
                raise ValueError("Exact upstream source reference shape required")
            objects[name] = read_pinned(records, {**ref, "kind": kind})
        checks["exact_temporal_parent_binding"] = fingerprint(payload["temporal_audit_ref"]) == fingerprint(source_pin(objects["temporal_audit"]))
        addition["references"] = {name: reference(obj) for name, obj in objects.items()}
        if not checks["exact_temporal_parent_binding"]:
            proof["reason"] = "edge_flow_parent_source_binding_mismatch"
            return addition
        proof["source_replay_attempted"] = True
        parent, config = payload["temporal_audit_ref"], payload["configuration"]
        fresh = derive_edge_flow(SimpleNamespace(store=records), parent["id"], version=parent["version"],
                                 max_work=config["max_work"], max_memory_bytes=config["max_memory_bytes"])
        proof["source_replay_completed"] = True
        checks["fresh_whole_payload_reproduced"] = fingerprint(fresh) == saved["hash"]
        checks["implementation_hashes_stable"] = fingerprint(fresh["implementation_hashes"]) == fingerprint(current) == fingerprint(implementation_hashes())
        proof["passed"] = all(checks.values())
        proof["reason"] = "reproduced" if proof["passed"] else "fresh_source_or_numerical_backend_mismatch"
        if not proof["passed"]:
            return addition
        addition["quantities"] = {"status": fresh["status"], "unknown_reasons": copy.deepcopy(fresh["unknown_reasons"]),
                                  "available_cells": fresh["available_cells"], "bounds": copy.deepcopy(fresh["bounds"])}
        addition["configuration"] = copy.deepcopy(fresh["configuration"])
        # Retain original numeric energies/checks and source cancellation evidence,
        # without exporting node potentials as ranks or full parent message text.
        for cell in fresh["cells"]:
            row = {key: copy.deepcopy(cell.get(key)) for key in ("window_id", "variant", "source_scope", "source_graph_sha256",
                   "source_reference_event_count", "edge_source_pins", "preflight", "source_unavailable_reason")}
            d = cell["decomposition"]
            row["decomposition"] = None if d is None else {key: copy.deepcopy(d.get(key)) for key in
                ("available", "status", "reason", "scope", "canonical_input", "energies", "backend", "configuration", "diagnostics", "input_fingerprint")}
            addition["cells"].append(row)
        notes = ["research/theory/selected-edge-flow-plan.md", "research/theory/graph-hodge-methods.md"]
        addition["theory_notes"] = theory_documents([note for note in notes if (REPO_ROOT / note).is_file()])
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        proof.update(passed=False, reason="edge_flow_source_or_operator_unavailable_or_invalid", error_type=type(exc).__name__)
        addition.update(quantities=None, cells=[], configuration=None, theory_notes=[])
    return addition


def collect_wait_markers(records, pins=None):
    """Reauthenticate the actor/index and chat sources before displaying alignment."""
    from types import SimpleNamespace
    from swarm_lab.wait_marker_workflow import derive_wait_marker_alignment, implementation_hashes, WORKFLOW_VERSION
    pins = WAIT_MARKER_PINS if pins is None else pins
    addition = {"references": {}, "summary": None, "message_scope": None, "status": None,
                "unknown_reasons": [], "configuration": None, "coverage": None, "bounds": None,
                "witnesses": [], "theory_notes": [], "model_calls": 0,
                "scope_note": "Retrospective literal tokens and same-actor recorded UTC-coordinate proximity over the same selected sources. No detector accuracy, semantic negatives, synchronized delay, room assignment, inactivity, exposure, novelty or causal interpretation."}
    proof = {"passed": False, "checks": {}, "model_calls": 0, "source_replay_attempted": False,
             "source_replay_completed": False, "index_artifact_reread_completed": False,
             "full_event_source_reread": False}
    addition["proof"] = proof
    try:
        if type(pins) is not dict or set(pins) != {"audit", "verification"}:
            raise ValueError("Exact wait-marker audit and verification pins required")
        objects = {name: read_pinned(records, pin) for name, pin in pins.items()}
        saved, verification = objects["audit"], objects["verification"]["payload"]
        payload = saved["payload"]
        if type(payload) is not dict or type(verification) is not dict:
            raise ValueError("Exact wait-marker payload shapes required")
        addition["references"] = {name: reference(obj) for name, obj in objects.items()}
        current = implementation_hashes()
        checks = {
            "exact_record_kinds": saved["kind"] == "wait_marker_alignment_audit" and objects["verification"]["kind"] == "verification",
            "exact_verification_binding": fingerprint(verification.get("alignment_ref")) == fingerprint(source_pin(saved)) and verification.get("result_kind") == "wait_marker_alignment_audit",
            "stored_verification_passed": verification.get("passed") is True,
            "stored_source_replay_completed": verification.get("source_replay_attempted") is True and verification.get("source_replay_completed") is True,
            "stored_index_reread_completed": verification.get("index_artifact_reread_completed") is True,
            "no_full_source_reread_claim": verification.get("full_event_source_reread") is False and payload.get("full_event_source_reread") is False,
            "stored_zero_model_calls": type(verification.get("model_calls")) is int and verification["model_calls"] == 0,
            "zero_model_calls": type(payload.get("model_calls")) is int and payload["model_calls"] == 0,
            "raw_content_not_persisted": payload.get("raw_content_persisted") is False,
            "no_status_promotion": payload.get("status_promotion") is False,
            "source_audit_replay_passed": payload.get("source_audit_replay_passed") is True and payload.get("index_artifact_reread_completed") is True,
            "exact_workflow_version": payload.get("workflow_version") == WORKFLOW_VERSION,
            "current_implementation_hashes": fingerprint(payload.get("implementation_hashes")) == fingerprint(current),
        }
        proof["checks"] = checks
        if not all(checks.values()):
            proof["reason"] = "wait_marker_record_binding_or_implementation_mismatch"
            return addition
        for name, kind in (("actor_audit", "actor_event_audit"), ("index", "event_source_index"),
                           ("selected_audit", "selected_lead_audit"), ("dataset", "dataset"), ("discovery", "discovery")):
            ref = payload["source_refs"][name]
            if type(ref) is not dict or set(ref) != {"id", "version", "hash"}:
                raise ValueError("Exact upstream source reference shape required")
            objects[name] = read_pinned(records, {**ref, "kind": kind})
        checks["exact_actor_parent_binding"] = fingerprint(payload["actor_audit_ref"]) == fingerprint(source_pin(objects["actor_audit"]))
        addition["references"] = {name: reference(obj) for name, obj in objects.items()}
        if not checks["exact_actor_parent_binding"]:
            proof["reason"] = "wait_marker_actor_source_binding_mismatch"
            return addition
        proof["source_replay_attempted"] = True
        actor = payload["actor_audit_ref"]
        fresh = derive_wait_marker_alignment(SimpleNamespace(store=records), actor["id"], version=actor["version"], **payload["configuration"])
        proof.update(source_replay_completed=True, index_artifact_reread_completed=True)
        checks["fresh_whole_payload_reproduced"] = fingerprint(fresh) == saved["hash"]
        checks["implementation_hashes_stable"] = fingerprint(fresh["implementation_hashes"]) == fingerprint(current) == fingerprint(implementation_hashes())
        proof["passed"] = all(checks.values())
        proof["reason"] = "reproduced" if proof["passed"] else "fresh_wait_marker_derivation_mismatch"
        if not proof["passed"]:
            return addition
        aligned = fresh["alignment"]
        addition.update(summary=copy.deepcopy(aligned["summary"]), status=aligned["status"],
                        message_scope=copy.deepcopy(aligned["message_scope"]), unknown_reasons=copy.deepcopy(aligned["unknown_reasons"]),
                        configuration=copy.deepcopy(aligned["configuration"]), coverage=copy.deepcopy(aligned["coverage"]),
                        bounds=copy.deepcopy(aligned["bounds"]), chat_clock_policy=fresh["chat_clock_policy"])
        if aligned["summary"] is not None:
            # A small presentation subset retains source IDs and coordinates,
            # never text/provider output or an outcome-selected analysis subset.
            pins_by_id = {row["message_id"]: row for row in aligned["message_pins"]}
            for row in [r for r in aligned["alignment_rows"] if r["candidates"]][:8]:
                pin = pins_by_id[row["message_id"]]
                addition["witnesses"].append({"message_id": row["message_id"], "analysis_group": row["analysis_group"],
                    "source": copy.deepcopy(pin["source"]), "normalized_record_sha256": pin["normalized_record_sha256"],
                    "marker_spans": copy.deepcopy(pin["marker_spans"]), "chat_clock_policy": pin["chat_clock_policy"],
                    "by_horizon_seconds": copy.deepcopy(row["by_horizon_seconds"]),
                    "first_candidates": copy.deepcopy(row["candidates"][:3]),
                    "presentation_scope": "First eight deterministic linked message rows; first three candidate IDs per row. Summary uses all retained alignments."})
        notes = ["research/theory/wait-marker-alignment-plan.md", "research/theory/wait-marker-interpretation.md"]
        addition["theory_notes"] = theory_documents([note for note in notes if (REPO_ROOT / note).is_file()])
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        proof.update(passed=False, reason="wait_marker_record_index_or_source_unavailable_or_invalid", error_type=type(exc).__name__)
        for key, empty in (("summary", None), ("message_scope", None), ("status", None), ("unknown_reasons", []),
                           ("configuration", None), ("coverage", None), ("bounds", None), ("witnesses", [])):
            addition[key] = empty
    return addition


def collect_temporal_reference(records, pins=None):
    """Reproduce frozen extraction and conditional draws, without persistence."""
    from types import SimpleNamespace
    from swarm_lab.temporal_null_workflow import derive_temporal_reference, implementation_hashes, WORKFLOW_VERSION
    pins = TEMPORAL_REFERENCE_PINS if pins is None else pins
    addition = {"references": {}, "quantities": None, "windows": {}, "configuration": None,
                "bounds": None, "limitations": [], "theory_notes": [], "model_calls": 0,
                "scope_note": "Exploratory timestamp references over the same frozen selected windows. Envelopes are not confidence intervals; ranks are not p-values. No exchangeability, exposure, influence, causal identification or independent replication is established."}
    proof = {"passed": False, "checks": {}, "source_replay_attempted": False,
             "source_replay_completed": False, "model_calls": 0}
    addition["proof"] = proof
    try:
        if type(pins) is not dict or set(pins) != {"reference", "verification"}:
            raise ValueError("Exact temporal-reference and verification pins required")
        objects = {name: read_pinned(records, pin) for name, pin in pins.items()}
        saved = objects["reference"]
        payload, verification = saved["payload"], objects["verification"]["payload"]
        if type(payload) is not dict or type(verification) is not dict:
            raise ValueError("Exact temporal-reference payload shapes required")
        addition["references"] = {name: reference(obj) for name, obj in objects.items()}
        current = implementation_hashes()
        checks = {
            "exact_record_kinds": saved["kind"] == "temporal_timestamp_reference" and objects["verification"]["kind"] == "verification",
            "exact_verification_binding": fingerprint(verification.get("reference_ref")) == fingerprint(source_pin(saved)) and verification.get("result_kind") == "temporal_timestamp_reference",
            "stored_verification_passed": verification.get("passed") is True,
            "stored_source_replay_completed": verification.get("source_replay_attempted") is True and verification.get("source_replay_completed") is True,
            "stored_zero_model_calls": type(verification.get("model_calls")) is int and verification["model_calls"] == 0,
            "zero_model_calls": type(payload.get("model_calls")) is int and payload["model_calls"] == 0,
            "no_status_promotion": payload.get("status_promotion") is False,
            "exact_workflow_version": payload.get("workflow_version") == WORKFLOW_VERSION,
            "current_implementation_hashes": fingerprint(payload.get("implementation_hashes")) == fingerprint(current),
        }
        proof["checks"] = checks
        if not all(checks.values()):
            proof["reason"] = "temporal_reference_binding_or_implementation_mismatch"
            return addition
        for name, kind in (("temporal_audit", "temporal_path_audit"), ("selected_audit", "selected_lead_audit"),
                           ("dataset", "dataset"), ("discovery", "discovery")):
            ref = payload["source_refs"][name]
            if type(ref) is not dict or set(ref) != {"id", "version", "hash"}:
                raise ValueError("Exact upstream source reference shape required")
            objects[name] = read_pinned(records, {**ref, "kind": kind})
        checks["exact_temporal_source_binding"] = fingerprint(payload["temporal_audit_ref"]) == fingerprint(source_pin(objects["temporal_audit"]))
        addition["references"] = {name: reference(obj) for name, obj in objects.items()}
        if not checks["exact_temporal_source_binding"]:
            proof["reason"] = "temporal_reference_source_binding_mismatch"
            return addition
        proof["source_replay_attempted"] = True
        ref = payload["temporal_audit_ref"]
        fresh = derive_temporal_reference(SimpleNamespace(store=records), ref["id"], version=ref["version"], **payload["configuration"])
        proof["source_replay_completed"] = True
        checks["fresh_whole_payload_reproduced"] = fingerprint(fresh) == saved["hash"]
        checks["implementation_hashes_stable"] = fingerprint(fresh["implementation_hashes"]) == fingerprint(current) == fingerprint(implementation_hashes())
        proof["passed"] = all(checks.values())
        proof["reason"] = "reproduced" if proof["passed"] else "fresh_temporal_reference_derivation_mismatch"
        if not proof["passed"]:
            return addition
        result = fresh["timestamp_reference"]
        cells = [v for w in result["windows"].values() for v in w["variants"].values()]
        addition["quantities"] = {"status": result["status"], "original_windows": len(result["windows"]),
            "requested_cells": len(cells), "computed_cells": sum(v["available"] is True for v in cells),
            "unavailable_cells": sum(v["available"] is not True for v in cells),
            "resamples_requested_per_cell": result["configuration"]["resamples_requested"]}
        addition["windows"] = copy.deepcopy(result["windows"])
        addition["configuration"] = copy.deepcopy(result["configuration"])
        addition["bounds"] = copy.deepcopy(result["bounds"])
        addition["limitations"] = copy.deepcopy(result["limitations"])
        addition["implementation_hashes"] = copy.deepcopy(current)
        addition["theory_notes"] = theory_documents(("research/theory/temporal-null-methods.md",))
    except (ValueError, TypeError, KeyError, OSError, UnicodeError) as exc:
        proof.update(passed=False, reason="temporal_reference_or_source_unavailable_or_invalid", error_type=type(exc).__name__)
        for key, empty in (("quantities", None), ("windows", {}), ("configuration", None), ("bounds", None), ("limitations", []), ("theory_notes", [])):
            addition[key] = empty
    return addition


def execution_inventory(report):
    groups = [{"label": "Initial artifact pilot", "reference": report["result"], "units": len(report["runs"]), "unit": "whole_team"}]
    for key,label,unit in (("replication", "Fresh-seed artifact replication", "whole_team"),
                           ("network_pilot", "Noisy-source network pilot", "whole_network"),
                           ("complementary_pilot", "Complementary-information pilot", "whole_network")):
        if key in report:
            groups.append({"label": label, "reference": report[key]["result"], "units": len(report[key]["runs"]), "unit": unit})
    scripted = report.get("scripted_resource_workflow", {}).get("quantities", {}).get("scripted_swarms", 0)
    timed = report.get("scripted_timed_resource_workflow", {}).get("quantities") or {}
    return {"live_groups": groups, "completed_live_units": sum(g["units"] for g in groups),
            "completed_scripted_resource_units": scripted,
            "completed_scripted_timed_resource_units": timed.get("scripted_swarms", 0),
            "scripted_timed_independent_seed_blocks": timed.get("independent_seed_blocks", 0),
            "unverified_scripted_sections": ["scripted_timed_resource_workflow"] if "scripted_timed_resource_workflow" in report and not report["scripted_timed_resource_workflow"]["proof"]["passed"] else [],
            "scope": "Live and scripted units are reported separately. Different tasks/studies are not pooled; tasks, agents, messages and turns do not multiply the independent unit count."}


def collect_selected_lead_sensitivity(records,pin=SELECTED_LEAD_PIN):
    from swarm_lab.selected_lead_sensitivity import audit_selected_lead_name_sensitivity
    audit=read_pinned(records,pin);payload=audit['payload'];refs=payload['source_refs']
    objects={kind:read_pinned(records,{**refs[kind],'kind':kind}) for kind in ('dataset','discovery')}
    dataset=objects['dataset']['payload'];discovery=objects['discovery']['payload']
    if discovery.get('dataset_ref')!=refs['dataset'] or discovery.get('dataset_id')!=refs['dataset']['id']:
        raise ValueError('Selected-lead discovery and dataset bindings disagree')
    def recompute():
        fresh=audit_selected_lead_name_sensitivity(dataset['messages'],dataset['agents'],discovery['graph_search'],
            selected_lead_ids=payload['frozen_selection']['requested_lead_ids'],
            short_name_allowlist=payload['configuration']['short_name_allowlist'],
            include_unicode_shadow=payload['configuration']['include_unicode_shadow'],source_refs=refs)
        canonical=lambda value:json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
        checks={key:canonical(payload.get(key))==canonical(value) for key,value in fresh.items()}
        return {'passed':all(checks.values()),'checks':checks,'model_calls':0,
            'scope':'Full source replay and conditional measurement derivation; no selection, causal estimate or behavioral relabeling.'}
    proof=safe_check(recompute)
    notes=['research/theory/selected-lead-sensitivity-plan.md']
    if (REPO_ROOT/'research/theory/selected-lead-interpretation.md').exists():notes.append('research/theory/selected-lead-interpretation.md')
    return {'references':{'audit':reference(audit),**{kind:reference(obj) for kind,obj in objects.items()}},
        'scope':payload['scope'],'configuration':payload['configuration'],'frozen_selection':payload['frozen_selection'],
        'per_lead':copy.deepcopy(payload['per_lead']) if proof['passed'] else [],
        'retained_unverified_per_lead':copy.deepcopy(payload['per_lead']) if not proof['passed'] else [],
        'proof':proof,'stored_validation':payload['validation'],'negative_control_checks':payload['negative_control_checks'],
        'source_binding':payload['source_binding'],'code_hashes':payload['code_hashes'],
        'limitations':payload['limitations'],'model_calls':0,'theory_notes':theory_documents(notes)}


def collect_report(database, result_id, network_id=None, replication_id="experiment-b46d02ce332c", complementary_id=COMPLEMENTARY_RESULT, graph_pairs=GRAPH_REVIEW_PAIRS, *, include_measurement=True, include_resource=True, include_selected_leads=False, include_temporal_paths=False, include_timed_resource=False, include_source_lineage=False, include_indexed_events=False, include_temporal_reference=False, include_actor_events=False, include_wait_markers=False, include_graph_hodge=False):
    if result_id != "experiment-f8ebb002aa60" or network_id not in (None, "network_experiment-b215b2b47aef") or replication_id not in (None, "experiment-b46d02ce332c"):
        raise ValueError("Scientific commentary is reviewed only for the named initial pilots; review a new study before reusing this narrative.")
    if complementary_id not in (None, COMPLEMENTARY_RESULT) or graph_pairs not in (None, GRAPH_REVIEW_PAIRS):
        raise ValueError("Additions are reviewed only for the named complementary pilot and graph-review pair")
    records = ReadOnlyRecords(Path(database))
    try:
        result = records.get(result_id)
        path, raw = load_raw(result)
        if result["kind"] != "experiment" or raw.get("status") != "complete":
            raise ValueError("A completed shared-artifact experiment is required; incomplete attempts cannot be estimated.")
        behavior = records.get(result["payload"]["behavior_id"])
        protocol = records.get(result["payload"]["protocol_id"])
        source_ref = behavior["payload"].get("source_refs", {}).get("dataset", {})
        dataset = records.get(behavior["payload"]["dataset_id"], source_ref.get("version"))
        by_id = {m["id"]: m for m in dataset["payload"]["messages"]}
        missing = set(behavior["payload"]["evidence_ids"]) - set(by_id)
        if missing:
            raise ValueError("Missing cited source records in the pinned dataset version: " + ", ".join(sorted(missing)))
        evidence = [{"id": identity, **{k: by_id[identity].get(k) for k in
                                      ("content", "agent_name", "room_id", "created_at", "source", "content_hash")}}
                    for identity in behavior["payload"]["evidence_ids"] if identity in by_id]
        evaluations = [x for x in records.list("evaluation") if x["payload"].get("experiment_id") == result_id]
        evaluation_versions = [{**reference(v), "commentary_status": v["payload"].get("commentary_status", "unreviewed"),
                                "explanation": v["payload"].get("explanation", {}),
                                "review_notes": v["payload"].get("review_notes", [])}
                               for x in evaluations for v in records.history(x["id"])]
        attempts = [{**reference(x), "status": x["payload"].get("status"),
                     "protocol_id": x["payload"].get("protocol_id"), "completed_runs": len(x["payload"].get("runs", [])),
                     "failure": x["payload"].get("failure"), "artifact_directory": x["payload"].get("artifact_directory")}
                    for x in records.list("experiment") if x["payload"].get("behavior_id") == behavior["id"]]
        theories = [{**reference(x), "theory": x["payload"]} for x in records.list("theory")
                    if behavior["id"] in x["payload"].get("behavior_ids", [])]
        recomputed = safe_check(lambda: {"passed": summarize_runs(raw["runs"], raw["protocol"]) == raw["analysis"],
                                         "name": "analysis_recomputed_from_executed_outcomes", "model_calls": 0})
        report = {"schema_version": "1.4", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                  "generation_mode": "offline_read_only", "new_model_calls": 0,
                  "result": reference(result), "raw_report_path": str(path),
                  "raw_file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "canonical_execution_report_hash": raw.get("report_hash"),
                  "protocol": {**reference(protocol), "definition": raw["protocol"],
                               "amends_protocol_id": protocol["payload"].get("amends_protocol_id"),
                               "amendment_reason": protocol["payload"].get("amendment_reason")},
                  "quantitative_summary": quantitative_summary(raw), "analysis": raw["analysis"],
                  "behavior": {**reference(behavior), "status": behavior["payload"].get("status"),
                               "novelty_status": behavior["payload"].get("novelty_status"),
                               "summary": behavior["payload"].get("summary"), "evidence_scope": "Explicit text only"},
                  "dataset": reference(dataset), "source_evidence": evidence,
                  "runs": [inspect_run(r) for r in raw["runs"]], "attempts": attempts,
                  "evaluation_history": evaluation_versions, "theories": theories,
                  "proof": {"current_action_replay": safe_check(lambda: replay_report(raw)),
                            "analysis_recomputation": recomputed,
                            "object_payload_hash_checks": [{"id": x["id"], "version": x["version"],
                                                            "passed": fingerprint(x["payload"]) == x["hash"]}
                                                           for x in (result, behavior, protocol, dataset)],
                            "stored_verifications": [{**reference(x), "verification": x["payload"]}
                                                     for x in records.list("verification") if x["payload"].get("experiment_id") == result_id]},
                  "trace_summary": records.trace_summary(result["payload"].get("research_job_id")),
                  "audit_scope": "Versioned review of separate live pilots, exploratory graph sources, graph/name instrument sensitivity, temporal reference paths, bounded explicit source lineage, indexed selected-window events, selected-author actor/time events and separate scripted resource/timing infrastructure when included; not pooled evidence, a validated historical mechanism or a general benchmark.",
                  "addition_notice": {"complementary_pilot": complementary_id, "exploratory_graph_reviews": [p[0] for p in (graph_pairs or ())],
                                      "graph_name_measurement_sensitivity": MEASUREMENT_PINS["graphs"] if include_measurement else None,
                                      "scripted_resource_workflow": RESOURCE_PINS["result"] if include_resource else None,
                                      "temporal_reference_paths": TEMPORAL_PINS["audit"] if include_temporal_paths else None,
                                      "scripted_timed_resource_workflow": TIMED_RESOURCE_PINS["result"] if include_timed_resource else None,
                                      "bounded_source_lineage": SOURCE_LINEAGE_PINS["audit"] if include_source_lineage else None,
                                      "indexed_selected_events": INDEXED_EVENT_PINS.get("audit") if include_indexed_events else None,
                                      "conditional_temporal_reference": TEMPORAL_REFERENCE_PINS["reference"] if include_temporal_reference else None,
                                      "selected_actor_events": ACTOR_EVENT_PINS["audit"] if include_actor_events else None,
                                      "literal_wait_marker_alignment": WAIT_MARKER_PINS["audit"] if include_wait_markers else None,
                                      "static_edge_count_decomposition": GRAPH_HODGE_PINS["audit"] if include_graph_hodge else None,
                                      "interpretation": "New sections explicitly extend the earlier pilot report. Older evidence and correction histories remain; estimates are not pooled."}}
        if network_id:
            network = records.get(network_id)
            net_path, net_raw = load_raw(network)
            if net_raw.get("status") != "complete":
                raise ValueError("The reviewed network pilot is incomplete; no effect narrative can be generated.")
            from swarm_lab.diffusion_experiments import analyze_diffusion_runs
            report["network_pilot"] = {"result": reference(network), "raw_report_path": str(net_path),
                                       "raw_file_sha256": hashlib.sha256(net_path.read_bytes()).hexdigest(),
                                       "status": net_raw["status"], "protocol": net_raw["protocol"],
                                       "analysis": net_raw.get("analysis"),
                                       "runs": [{k: r[k] for k in ("run_id", "topology", "context", "environment_seed", "outcomes")}
                                                for r in net_raw["runs"]],
                                       "proof": safe_check(lambda: replay_network(net_raw)),
                                       "analysis_recomputation": safe_check(lambda: {"passed": analyze_diffusion_runs(net_raw["runs"], net_raw["protocol"]) == net_raw["analysis"], "model_calls": 0})}
        if replication_id:
            replication = records.get(replication_id)
            rep_path, rep_raw = load_raw(replication)
            if rep_raw.get("status") != "complete":
                raise ValueError("The reviewed replication is incomplete; no effect narrative can be generated.")
            rep_protocol = records.get(replication["payload"]["protocol_id"])
            original_seeds = {r["environment_seed"] for r in raw["runs"]}
            report["replication"] = {"result": reference(replication), "raw_report_path": str(rep_path),
                                     "raw_file_sha256": hashlib.sha256(rep_path.read_bytes()).hexdigest(),
                                     "protocol": {**reference(rep_protocol), "definition": rep_raw["protocol"],
                                                  "replicates_protocol_id": rep_protocol["payload"].get("replicates_protocol_id")},
                                     "quantitative_summary": quantitative_summary(rep_raw), "analysis": rep_raw["analysis"],
                                     "runs": [inspect_run(r) for r in rep_raw["runs"]],
                                     "proof": safe_check(lambda: replay_report(rep_raw)),
                                     "analysis_recomputation": safe_check(lambda: {"passed": summarize_runs(rep_raw["runs"], rep_raw["protocol"]) == rep_raw["analysis"], "model_calls": 0}),
                                     "seed_overlap": sorted(original_seeds & {r["environment_seed"] for r in rep_raw["runs"]}),
                                     "scope": "Fresh environment/scheduler seeds with the same subject model, prompts, task, and outcomes. Not cross-model or historical replication."}
        if complementary_id:
            report["complementary_pilot"] = collect_complementary(records, complementary_id)
        if graph_pairs:
            report["exploratory_graph_reviews"] = collect_graph_reviews(records, graph_pairs)
        if include_measurement:
            report["graph_name_measurement_sensitivity"] = collect_measurement_sensitivity(records)
        if include_resource:
            report["scripted_resource_workflow"] = collect_resource_workflow(records)
        if include_selected_leads:
            report['selected_lead_measurement_sensitivity']=collect_selected_lead_sensitivity(records)
            report['addition_notice']['selected_lead_measurement_sensitivity']=SELECTED_LEAD_PIN
        if include_temporal_paths:
            report["temporal_reference_paths"] = collect_temporal_paths(records)
        if include_timed_resource:
            report["scripted_timed_resource_workflow"] = collect_timed_resource_workflow(records)
        if include_source_lineage:
            report["bounded_source_lineage"] = collect_source_lineage(records)
        if include_indexed_events:
            report["indexed_selected_events"] = collect_indexed_events(records)
        if include_temporal_reference:
            report["conditional_temporal_reference"] = collect_temporal_reference(records)
        if include_actor_events:
            report["selected_actor_events"] = collect_actor_events(records)
        if include_wait_markers:
            report["literal_wait_marker_alignment"] = collect_wait_markers(records)
        if include_graph_hodge:
            report["static_edge_count_decomposition"] = collect_graph_hodge(records)
        report["execution_inventory"] = execution_inventory(report)
        return clean(report)
    finally:
        records.close()


def esc(value):
    return html.escape(str(value), quote=True)


def json_block(value):
    return '<pre><code>' + esc(json.dumps(value, ensure_ascii=False, indent=2)) + '</code></pre>'


def table(caption, columns, rows):
    return '<div class="table-scroll"><table><caption>' + esc(caption) + '</caption><thead><tr>' + ''.join(
        '<th scope="col">' + esc(c) + '</th>' for c in columns) + '</tr></thead><tbody>' + ''.join(
        '<tr>' + ''.join('<td>' + esc(c) + '</td>' for c in row) + '</tr>' for row in rows) + '</tbody></table></div>'


ARM_LABELS = {"baseline": "Baseline", "placebo": "Neutral note", "evidence_thought": "Evidence reminder"}


def render_addition_sources(addition):
    references = addition["references"]
    page = table("Exact immutable object references", ["Role", "Object ID", "Version", "Payload SHA-256"],
                 [(name, ref["id"], ref["version"], ref["hash"]) for name, ref in references.items()])
    for note in addition["theory_notes"]:
        page += '<details><summary>Local theory note: ' + esc(note["repository_path"]) + '</summary><p class="meta">SHA-256 ' + esc(note["sha256"]) + '</p><p><a href="' + esc(note["local_uri"]) + '">Open local source</a> · ' + esc(note["scope"]) + '</p><pre>' + esc(note["snapshot"]) + '</pre></details>'
    return page


def render_temporal_addition(addition):
    parts = ['<section id="temporal-paths"><h2>Added temporal audit: static paths can run backward in time</h2><p>These are the original selected room windows and name instruments. A reference edge points from the message author to the matched roster name. A strict temporal path requires increasing UTC timestamps, remains within one room, and cannot relay through simultaneous events. Names and temporal order do not establish delivery, reading or influence.</p>']
    if addition["proof"]["passed"] is True:
        rows, removal_rows = [], []
        for window in addition["windows"]:
            for name, variant in window["variants"].items():
                if not variant["available"]:
                    continue
                rows.append((window["window_id"], name, variant["event_count"], variant["static_reachable_pairs"],
                             variant["strict_temporal_reachable_pairs"], variant["static_only_pairs"],
                             variant["selected_static_witness_reversed_time_count"], variant["selected_static_witness_tied_time_count"]))
                removal_rows.append((window["window_id"], name,
                    variant["static_node_removal"]["maximum_loss_fraction"], variant["static_node_removal"]["focus_agent_id"],
                    variant["temporal_node_removal"]["maximum_loss_fraction"], variant["temporal_node_removal"]["focus_agent_id"]))
        parts.append(table("Same room/window-specific ordered pairs; timestamp ties do not supply an order", ["Original window", "Instrument", "Events", "Static pairs", "Strict temporal pairs", "Static-only pairs", "Selected static witnesses with reversed time", "Selected static witnesses with ties"], rows))
        parts.append('<p class="note">Static-only pairs have no valid strict temporal route among these retained reference events. A reversed or tied selected static witness alone does not rule out a different valid route. The reversed/tied witness counts can overlap; ordered pairs across windows and variants are not independent samples. Referenced targets without authored messages are not observed readers.</p>')
        parts.append(table("Recompute all alternate routes after representation deletion; removed-node endpoints excluded", ["Original window", "Instrument", "Maximum static loss", "Static focus", "Maximum temporal loss", "Temporal focus"], removal_rows))
        for example in addition["static_only_witnesses"]:
            witness = example["witness"]
            parts.append('<details><summary>Static-only witness ' + esc(example["witness_ref"]) + ' · ' + esc(example["variant"]) + ' · ' + esc(witness["source_agent_id"]) + ' → ' + esc(witness["target_agent_id"]) + '</summary>')
            for source in example["source_messages"]:
                parts.append('<p class="meta">Source ' + esc(source["id"]) + ' · ' + esc(source.get("agent_name")) + ' · ' + esc(source.get("timestamp")) + '</p><blockquote>' + esc(source.get("content")) + '</blockquote>')
            parts.append(json_block(example) + '</details>')
    else:
        parts.append('<p class="alert">Current pinned-source replay failed. Temporal quantities, deletion statistics and witness tables are withheld; retained recorded derivations below remain unverified.</p>')
    parts.append('<p class="note">Deletion is a change to this reference representation, not an intervention on an agent. There is no processing-latency assumption or maximum gap within a window. Human context, missing channels, alias errors, unknown reading opportunities and the author-to-name direction limit interpretation. Original selection, comparisons, graphs and library statuses remain unchanged.</p>')
    parts.append(render_addition_sources(addition))
    parts.append('<details><summary>Exact source pins, fresh replay, temporal definitions and retained derivation</summary>' + json_block(addition) + '</details></section>')
    return ''.join(parts)


def render_timed_resource_addition(addition):
    parts = ['<section id="timed-resource"><h2>Added timing workflow: one exact private-boundary receipt</h2><p>This is a separate CPU scripted workflow. Active and neutral content were assigned within independent world-seed blocks, with separately reset swarms sharing the exact initial scheduler and release path within each pair. Trigger evaluation sees scoped pre-insertion state, without the arm or note content. A sole receipt binds the constructed next request; it does not attest provider consumption.</p>']
    if addition["proof"]["passed"] is True:
        quantities, analysis = addition["quantities"], addition["analysis"]
        effect = analysis["primary_effect"]
        parts.append('<p>' + esc(f'{quantities["scripted_swarms"]} scripted swarms form {quantities["independent_seed_blocks"]} independent paired seed blocks. They completed {quantities["executed_completed_tasks"]}/{quantities["declared_tasks"]} tasks, with {quantities["recorded_receipts"]} private-boundary receipts and {quantities["applied_actions"]} applied actions.') + '</p><p class="note">The deterministic policy ignores notes. This verifies timing, delivery and analysis machinery; it provides no empirical LLM reminder effect. Uncertainty uses independent seed blocks; paired swarms, tasks, receipts and individual turns do not add independent observations. Keep these units separate from the live studies and the earlier scripted resource workflow.</p>')
        parts.append(table("Assigned-policy ITT retains completed never-delivered swarms", ["Assigned content", "Scripted swarms", "Task completion", "Receipts", "Never-delivered complete swarms", "Unresolved eligibility"],
            [(name, cell["n_swarms"], f'{cell["task_completion_fraction"]*100:.1f}%', cell["recorded_receipts"], cell["never_delivered_completed_swarms"], cell["eligibility_unresolved_completed_swarms"]) for name, cell in analysis["cells"].items()]))
        parts.append('<p>' + esc(f'The recorded paired ITT difference is {effect["difference"]:+.3f}, with bounded 95% interval [{effect["ci95"][0]}, {effect["ci95"][1]}] and two-sided label-swap p={effect["p_two_sided"]:.3g}.') + ' This is a numerical mechanics result on a notes-ignored script. A zero difference and wide interval establish neither a model null effect nor equivalence. Receipt, waiting and access counts are post-treatment process descriptions; conditioning on them is not the registered causal comparison.</p>')
        parts.append(table("Each row is one reset swarm; block pairs share the full exogenous path", ["Run", "Seed block", "Assigned content", "Release round", "Completion", "Receipts", "Applied actions"],
            [(r["run_id"], r["block_id"], r["context"], r["initial_world_identity"]["release_round"], f'{r["outcomes"]["task_completion_fraction"]*100:.1f}%', r["counts"]["recorded_receipts"], r["counts"]["applied_actions"]) for r in addition["runs"]]))
        parts.append('<details><summary>Exact private boundary receipts and retained policy ITT evidence</summary>' + json_block(addition["runs"]) + '</details>')
        checked = addition["claim_audit"]["recomputed"]
        parts.append(table("Finite claim recheck; generated fact text alone is approved", ["Fact ID", "Approved finite fact text", "Attached prose"],
            [(row["fact_id"], row["approved_fact_text"], row["prose_status"]) for row in checked["claims"] if row["status"] == "supported"]))
        parts.append('<p class="note">The claim audit was rebuilt from the exact independently replayed report and source pin. Approved fact text is generated by the finite checker. Attached model prose remains unverified even when its neighboring typed value is supported.</p>')
    else:
        parts.append('<p class="alert">Current execution/source/archive or finite-claim verification failed. Timed-reminder quantities, outcome tables and effect statistics are withheld; retained recorded analysis below remains unverified.</p>')
    parts.append('<p class="note">An incomplete invocation or infrastructure failure retains the full assignment grid and prevents estimation. Complete never-delivered units remain in policy ITT. Source replay verifies code-scored actions and exact recorded requests; it neither repeats a hosted trial nor proves model uptake. Global resource exclusivity and abstract task costs remain invented analogues.</p>')
    parts.append(render_addition_sources(addition))
    parts.append('<details><summary>Exact registration/result pins, fresh archive replay and separate timing protocol</summary>' + json_block(addition) + '</details></section>')
    return ''.join(parts)


def render_source_lineage_addition(addition):
    parts = ['<section id="source-lineage"><h2>Added source lineage: a bounded prefix, reread from files</h2><p>This retrospective known-prefix probe uses explicit exported foreign keys across platform events, chat, computer sessions and computer turns. Parent IDs were selected after inspecting the prefix. A matched export is evidence of scoped logged lineage; it does not establish reading, delivery, tool success or causal influence.</p>']
    if addition["proof"]["passed"] is True:
        q = addition["quantities"]
        parts.append('<p>' + esc(f'{q["retained_rows"]} retained rows contain {q["explicit_relation_attempts"]} explicit relation attempts: {q["scoped_matches"]} scoped matches ({q["matched_chat_emissions"]} chat emission and {q["matched_session_links"]} session links), {q["parents_unresolved_in_scanned_scope"]} parents unresolved in scanned scope and {q["missing_foreign_keys"]} missing foreign keys.') + '</p>')
        parts.append('<p class="note">' + esc(f'{q["partial_tables"]} of {q["scanned_tables"]} scans are partial.') + ' These selected prefixes do not estimate prevalence or corroborate the earlier April room windows. Missing parents remain unresolved in scanned scope; they are not globally absent. Logged waits and requested pauses do not measure whole-agent inactivity or a global resource lock.</p>')
        parts.append(table("Each row is a bounded scan; coverage is not global completeness", ["Table", "Physical rows", "Retained", "Filtered", "Stop reason", "Complete scan", "Logical compressed bytes", "Expanded bytes"],
            [(s["table"], s["coverage"]["physical_rows_seen"], s["coverage"]["retained_rows"], s["coverage"]["filtered_rows"], s["coverage"]["stop_reason"], s["coverage"]["complete_scan"], s["coverage"]["compressed_bytes_read"], s["coverage"]["expanded_bytes_read"]) for s in addition["coverage"]]))
        parts.append(table("Explicit relation statuses in retained/scanned rows only", ["Exported-link status", "Attempts"], sorted(q["relation_status_counts"].items())))
        parts.append(table("Matched exported identities; source line numbers are physical coordinates", ["Relation", "Scoped status", "Child file / line", "Child row SHA256", "Parent file / line", "Parent row SHA256"],
            [(r["relation_kind"], r["status"], f'{r["child_source"]["path"]} / {r["child_source"]["line"]}', r["child_source"]["record_sha256"], f'{r["parent_source"]["path"]} / {r["parent_source"]["line"]}', r["parent_source"]["record_sha256"]) for r in addition["matched_coordinates"]]))
        parts.append('<details><summary>Exact child/parent raw-line hashes and field agreement diagnostics</summary>' + json_block(addition["matched_coordinates"]) + '</details>')
    else:
        parts.append('<p class="alert">Current record, implementation, scan plan or filesystem replay failed. Source-lineage counts, coverage and coordinate tables are withheld. A saved verification does not authenticate currently available file bytes.</p>')
    parts.append('<p class="note">Raw chat, tool arguments, outputs and provider message payloads are omitted. Text agreement uses hashes. Physical-prefix hashes cover logical bytes actually returned by the bounded reader; mounted filesystem prefetch and remote wire traffic are not measured. Source object metadata remains a declaration. These rows add no independent experimental units and are not pooled with any pilot.</p>')
    parts.append(render_addition_sources(addition))
    parts.append('<details><summary>Exact plan, implementation hashes and fresh pure read-only proof</summary>' + json_block(addition) + '</details></section>')
    return ''.join(parts)


def render_indexed_event_addition(addition):
    parts = ['<section id="indexed-events"><h2>Added selected-window events: field matches and logged actions</h2><p>This audit keeps the original selected room windows. Exported AGENT_TALK fields are compared with exact normalized chat sources; explicit WAIT, PAUSE, START_USING_COMPUTER and STOP_USING_COMPUTER events are counted separately. An emission field match does not establish recipient reception, reading, influence, tool success or whole-agent inactivity.</p>']
    if addition["proof"]["passed"] is True:
        q, coverage = addition["quantities"], addition["coverage"]
        statuses = q["emission_statuses"]
        parts.append('<p>' + esc(f'{q["selected_chat_records"]} selected chat records: {statuses["matched"]} field-matched emissions, {statuses["unknown"]} unknown and {statuses["conflict"]} conflicting. {q["projected_event_records"]} projected event records were returned by the declared query.') + '</p>')
        parts.append('<p class="note">Selected chat denominators can include human speakers. This AGENT_TALK query does not test human emissions. An unknown human record is not evidence of missing agent communication.</p>')
        if q.get("selected_chat_by_speaker_type"):
            parts.append(table("Speaker-specific chat denominators", ["Normalized speaker type", "Selected chats", "Matched", "Unknown", "Conflict"],
                [(speaker, count, q["emission_statuses_by_speaker_type"][speaker]["matched"], q["emission_statuses_by_speaker_type"][speaker]["unknown"], q["emission_statuses_by_speaker_type"][speaker]["conflict"])
                 for speaker, count in q["selected_chat_by_speaker_type"].items()]))
        else:
            parts.append('<p>No speaker-specific denominators were recorded by this audit version; no agent-only missingness rate is calculated.</p>')
        build = coverage["build_scan"]
        parts.append(table("Build and query coverage are separate", ["Build complete", "Build stop", "Physical rows scanned", "Indexed rows", "Query complete", "Query matched rows", "Returned rows", "Query truncated"],
            [(build["complete_scan"], build["stop_reason"], build["physical_rows_seen"], build["indexed_rows"], coverage["query_complete"], coverage["matched_rows"], coverage["returned_rows"], coverage["truncated"])]))
        parts.append('<p class="note">A complete query is complete only over this local index. A partial index build cannot establish global absence or uniqueness. The fresh check authenticates current local SQLite bytes and reproduces frozen selected chat sources; it does not reread the original event object.</p>')
        parts.append(table("Original room/time windows; explicit scoped event counts", ["Original window", "Room", "UTC start", "UTC end, exclusive", "Selected chats", "Matched", "Unknown", "Conflict", "WAIT", "PAUSE", "START", "STOP"],
            [(w["id"], w["room_id"], w["start"], w["end_exclusive"], w["selected_chat_records"],
              w["emission_status_counts"]["matched"], w["emission_status_counts"]["unknown"], w["emission_status_counts"]["conflict"],
              w["platform_actions"]["WAIT"], w["platform_actions"]["PAUSE"], w["platform_actions"]["START_USING_COMPUTER"], w["platform_actions"]["STOP_USING_COMPUTER"])
             for w in addition["windows"]]))
        parts.append(table("First twelve chat emission diagnostics; timestamps are recorded differences", ["Message ID", "Source line", "Speaker type", "Status", "Candidates", "Ambiguity", "Field checks", "Event minus chat, ms"],
            [(r["message_id"], r["parent_source"]["line"], r["parent_speaker_category"], r["emission_status"], r["candidate_count"], r["ambiguity_status"],
              '; '.join(c["event_field"] + ': ' + c["status"] for c in r["field_checks"]), r["timestamp_difference_ms"])
             for r in addition["emissions"][:12]]))
        parts.append('<details><summary>Source coordinates, projected event identities and build byte authentication</summary>' + json_block({k:addition[k] for k in ("index_build", "index_artifact_binding", "query", "query_packet_hash", "emissions", "events")}) + '</details>')
    else:
        parts.append('<p class="alert">Current exact-source/local-index replay failed or is unavailable. Event counts, chat diagnostics, window tables and coordinates are withheld. A stored verification alone cannot approve them.</p>')
    parts.append('<p class="note">Requested pauses are logged requests, not observed sleep durations. Room-less records remain unassigned; no room or actor is inferred from narrative. This source instrument does not alter mention graphs, original selection, causal protocols or behavior/theory statuses, and adds no independent experimental units.</p>')
    parts.append(render_addition_sources(addition))
    parts.append('<details><summary>Exact indexed-event source pins and fresh verification</summary>' + json_block(addition) + '</details></section>')
    return ''.join(parts)


def hodge_display(value, reference=1):
    """Presentation only: disclose small relative rounding; retain exact JSON."""
    if type(value) not in (int, float):
        return "Unknown"
    if value == 0:
        return "0"
    scale = max(1, abs(reference)) if type(reference) in (int, float) else 1
    if abs(value) <= HODGE_DISPLAY_TOLERANCE * scale:
        return "≈ 0"
    return f'{value:.6g}'


def render_graph_hodge_addition(addition):
    parts = ['<section id="edge-flow"><h2>Added static edge-count algebra: gradient and circulation</h2><p>For each supported unordered pair, lexical ID order sets the orientation; the signal is the forward named-reference count minus the reverse count. Balanced supported edges remain in the graph at zero. An unweighted least-squares gradient fit leaves an algebraic circulation residual. This description discards time order.</p>']
    if addition["proof"]["passed"] is True:
        q = addition["quantities"]
        parts.append('<p>' + esc(f'{q["available_cells"]} / {q["bounds"]["cells"]} fixed parent cells available; work proxy {q["bounds"]["estimated_total_work"]}. Status: {q["status"]}. Every original window and variant is retained without ranking or rematching.') + '</p>')
        rows = []
        for cell in addition["cells"]:
            d = cell["decomposition"]
            scope = (d or {}).get("scope") or (cell["preflight"] or {}).get("scope") or {}
            energies = d.get("energies") if d and d.get("available") is True else None
            energy = lambda key: (energies or {}).get(key)
            signal = (energy("signal") or {}).get("squared_norm")
            natural = lambda key: hodge_display((energy(key) or {}).get("squared_norm"), signal)
            fraction = lambda key: hodge_display((energy(key) or {}).get("fraction_of_signal"))
            balanced = None if cell["edge_source_pins"] is None else sum(p["net_reference_events"] == 0 for p in cell["edge_source_pins"])
            count = lambda value: str(value) if type(value) is int else 'Unknown'
            source = cell["source_scope"]
            label = f'{source.get("start", cell["window_id"])} → {source.get("end_exclusive", "unknown end")}'
            if not d or d.get("available") is not True:
                label += ' · unavailable: ' + str(cell.get("source_unavailable_reason") or (d or {}).get("reason") or ', '.join(q["unknown_reasons"]) or 'not computed')
            rows.append((label, cell["variant"],
                         f'{count(scope.get("node_count"))} / {count(scope.get("edge_count"))} / {count(balanced)}',
                         count(cell["source_reference_event_count"]), natural("signal"), natural("gradient"), natural("circulation"),
                         f'{fraction("gradient")} / {fraction("circulation")}'))
        parts.append(table("All fixed cells; squared net-count energies and separate dimensionless fractions", ["Original UTC window", "Variant", "Nodes / supported / balanced edges", "Reference events", "Signal energy", "Gradient energy", "Circulation energy", "Fractions gradient / circulation"], rows))
        parts.append('<p class="note">Unknown energy and unknown fraction are separate: a zero signal has zero energy but undefined fractions. An unavailable source, budget or backend is never a zero score. No face complex is specified (faces=None), so curl and harmonic energies/components remain unknown. Original node universes can differ across windows; variants and overlapping sources are dependent.</p>')
        parts.append('<details><summary>Original numeric energies, numerical checks, balanced directional counts and exact event pins</summary>' + json_block(addition["cells"]) + '</details>')
    else:
        parts.append('<p class="alert">Fresh exact-source/code/whole-payload numerical reproduction failed or is unavailable. Decomposition quantities and cell tables are withheld; a stored passing proof alone cannot authorize them.</p>')
    parts.append('<p class="note">Display only: nonzero magnitudes ≤ 10⁻¹² × max(1, signal squared energy) are shown as ≈ 0 for natural energies; fractions use absolute 10⁻¹². Other numbers use six significant digits. Original finite values remain in collapsed metadata without clipping, including rounding just above one. Squared energy is quadratic in net counts, not a proportion of messages or agents. Potentials are gauge-dependent coordinates, not ranks.</p><p class="note">Same selected references, not physical traffic, hierarchy, rumor, chronological relay, a continuum Laplace–Beltrami basis, novelty or causal evidence. This addition creates no independent experimental units and promotes no behavior/theory status.</p>')
    parts.append(render_addition_sources(addition))
    parts.append('<details><summary>Exact edge-flow pins, fresh proof, fixed bounds and scope</summary>' + json_block({key:addition[key] for key in ("references", "proof", "quantities", "configuration", "display_tolerance", "scope_note")}) + '</details></section>')
    return ''.join(parts)


def render_wait_marker_addition(addition):
    parts = ['<section id="wait-markers"><h2>Added literal wait/action proximity: small source-bound denominators</h2><p>Eight ASCII whole-word tokens select marker messages. Deterministic nonmarker comparisons are selected by source-ID hash, without event outcomes. They are neither a probability sample nor negative semantic ground truth. Candidates are same-actor WAIT/PAUSE records in a shared query time window, within inclusive absolute 30/60/300-second horizons; before, tie and after relations all count.</p>']
    if addition["proof"]["passed"] is True:
        scope, summary = addition["message_scope"], addition["summary"]
        parts.append('<p>' + esc(f'{scope["supplied_messages"]} selected chats, {scope["agent_authored_messages"]} agent-authored; excluded nonagent counts: {json.dumps(scope["excluded_nonagent_by_speaker_type"], sort_keys=True)}. {scope["literal_marker_spans"]} literal token spans.') + '</p>')
        if summary is None:
            parts.append('<p class="alert">Source reproduction passed, but candidate alignment remains unknown. No candidate table or negative-looking zero is supplied. Reasons: ' + esc(', '.join(addition["unknown_reasons"])) + '</p>')
        else:
            rows = []
            for h in addition["configuration"]["horizons_seconds"]:
                marker = summary["groups"]["marker"]["by_horizon_seconds"][str(h)]
                control = summary["groups"]["nonmarker_control"]["by_horizon_seconds"][str(h)]
                fraction = lambda count, denominator: f'{count} / {denominator}' if denominator else 'No messages'
                rows.append((h, fraction(marker["messages_with_candidate"], summary["marker_messages"]),
                             fraction(control["messages_with_candidate"], summary["nonmarker_control_messages"]),
                             f'{marker["status_counts"].get("candidate_observed_boundary_censored",0)} / {control["status_counts"].get("candidate_observed_boundary_censored",0)}',
                             f'{marker["status_counts"].get("no_indexed_candidate_boundary_censored",0)} / {control["status_counts"].get("no_indexed_candidate_boundary_censored",0)}'))
            parts.append(table("Recorded candidates: message numerators / group denominators; censored counts are marker / comparison", ["Inclusive horizon, s", "Marker messages with candidate", "Nonmarker comparisons with candidate", "Candidate with censored band", "No candidate in censored band"], rows))
            parts.append('<p>' + esc(f'{summary["candidate_links"]} message/event links refer to {summary["distinct_linked_events"]} distinct events. Events, nested horizons and overlapping windows are reused; rows and links are not independent samples.') + '</p>')
            parts.append('<details><summary>Small presentation-only evidence examples and exact count statuses</summary>' + json_block({"witnesses":addition["witnesses"],"summary":summary}) + '</details>')
        parts.append('<p class="note">A boundary-censored band is not an observed negative outside the available window. Event rooms can be missing; chat rooms are never assigned to them. Raw chat clock policies are unavailable; signed coordinate lags do not establish synchronized physical delays or processing order.</p>')
    else:
        parts.append('<p class="alert">Fresh exact-source/code reproduction failed or is unavailable. Marker/action counts, candidate tables and evidence examples are withheld. A stored passing proof alone cannot authorize them.</p>')
    parts.append('<p class="note">Same-source retrospective exploration only. Literal hits retain negations, quotes, plans and instructions with meaning unadjudicated. No detector accuracy, inactivity, lease, exposure, novelty or causal claim is computed. No independent experimental units or behavior/theory promotions are added.</p>')
    parts.append(render_addition_sources(addition))
    parts.append('<details><summary>Exact alignment pins, fresh proof, bounds and compact scope</summary>' + json_block({key:addition[key] for key in
        ("references", "proof", "status", "unknown_reasons", "configuration", "coverage", "bounds", "scope_note")}) + '</details></section>')
    return ''.join(parts)


def render_actor_event_addition(addition, room_addition=None):
    parts = ['<section id="actor-events"><h2>Added actor/time events: missing rooms remain unassigned</h2><p>Original selected room/time chat windows identify exact normalized agent authors. The event query then selects those explicit actor IDs and the union of their time windows, without a room predicate. Nonagent chats do not select actors. This is a complementary source instrument, not a revision of the earlier room/time counts.</p>']
    if addition["proof"]["passed"] is True:
        q, coverage, scope = addition["quantities"], addition["coverage"], addition["source_scope"]
        parts.append('<p>' + esc(f'{q["records"]} retained attributed records; {coverage["candidate_rows_validated"]}/{coverage["candidate_rows"]} time/action candidates validated; {coverage["returned_rows"]}/{coverage["matched_rows"]} matching records returned. Query complete: {coverage["query_complete"]}; truncated: {coverage["truncated"]}.') + '</p>')
        parts.append(table("Returned actor/time records; logged choices and boundaries only", ["WAIT", "PAUSE", "START", "STOP", "Known room", "Missing room", "Invalid room"],
            [(*[q["action_counts"][key] for key in ("WAIT", "PAUSE", "START_USING_COMPUTER", "STOP_USING_COMPUTER")], *[q["room_status_counts"][key] for key in ("known", "missing", "invalid")])]))
        room_verified = (type(room_addition) is dict and room_addition.get("proof", {}).get("passed") is True and
                         all(fingerprint(addition["references"].get(key)) == fingerprint(room_addition.get("references", {}).get(key))
                             for key in ("index", "selected", "dataset", "discovery")))
        if room_verified:
            actions = ("WAIT", "PAUSE", "START_USING_COMPUTER", "STOP_USING_COMPUTER")
            # Each window retains its own predicate. No aggregate sum over overlapping
            # windows is called a unique event count or an independent observation.
            parts.append(table("Same exact sources, different predicates; window counts may overlap", ["Original window", "Predicate", "WAIT", "PAUSE", "START", "STOP"],
                [(w["id"], "Explicit room + time", *[w["platform_actions"][key] for key in actions]) for w in room_addition["windows"]] +
                [(wid, "Selected actors + time; room omitted", *[counts["action_counts"][key] for key in actions]) for wid, counts in addition["by_window"].items()]))
        else:
            parts.append('<p>The separate room/time section has no fresh verified matching source pins here; numerical cross-instrument comparison is withheld.</p>')
        parts.append('<p class="note">A zero in a room/time query does not establish absence of actor activity. Missing rooms cannot satisfy that explicit room predicate; including them in an actor/time query still does not assign them to a room. These are different measurement scopes, not contradictory causal findings.</p>')
        parts.append(table("Selected chat author scope, without roster or mention-target inference", ["Selected chats", "Agent-authored source records", "Exact selected actors", "Speaker categories"],
            [(scope["selected_chat_records"], scope["agent_authored_records"], scope["selected_actor_count"], json.dumps(scope["speaker_type_counts"], sort_keys=True))]))
        parts.append(table("Actor partitions of retained records; no independent samples", ["Exact actor ID", "Records", "WAIT", "PAUSE", "START", "STOP", "Missing room"],
            [(actor, counts["records"], *[counts["action_counts"][key] for key in ("WAIT", "PAUSE", "START_USING_COMPUTER", "STOP_USING_COMPUTER")], counts["room_status_counts"]["missing"])
             for actor, counts in addition["by_actor"].items()]))
        parts.append(table("Build, candidate validation and retained output coverage", ["Build complete", "Build stop", "Indexed rows", "All candidate validation complete", "Query complete", "Truncated", "Other explicit actor rows"],
            [(coverage["build_scan"]["complete_scan"], coverage["build_scan"]["stop_reason"], coverage["build_scan"]["indexed_rows"], coverage["candidate_validation_complete"], coverage["query_complete"], coverage["truncated"], coverage["other_explicit_actor_rows"])]))
        parts.append('<p class="note">Partial builds cannot establish global absence; truncated summaries describe returned records only. Overlapping time windows reuse events. Requested PAUSE seconds are not elapsed inactivity. START/STOP boundaries do not verify an exclusive lease, successful access or a continuous-use interval.</p>')
        parts.append('<details><summary>Original chat-selection rooms, source coordinates, actor pins and index-byte authentication</summary>' + json_block({key: addition[key] for key in
            ("original_windows", "query", "query_packet_hash", "index_binding", "record_pins", "author_source_pins", "timestamp_policy_counts", "timestamp_policy_scope")}) + '</details>')
    else:
        parts.append('<p class="alert">Current exact-source/local-index reproduction failed or is unavailable. Actor counts, room missingness, partitions and source coordinates are withheld. A saved passing verification alone cannot approve them.</p>')
    parts.append('<p class="note">No room, recipient, delivery, exposure, inactivity, lease, task success or causal behavior is inferred. Export-clock conventions do not prove synchronized clocks. Original room/time audits, graphs, selected leads, library statuses and independent experimental-unit counts remain unchanged.</p>')
    parts.append(render_addition_sources(addition))
    parts.append('<details><summary>Exact actor-event source pins and fresh read-only reproduction</summary>' + json_block(addition) + '</details></section>')
    return ''.join(parts)


def render_temporal_reference_addition(addition):
    parts = ['<section id="timestamp-reference"><h2>Added timestamp reference: original counts versus conditional envelopes</h2><p>Within each original room/window/name instrument, timestamps are permuted among distinct edge-bearing source messages. All accepted target edges from a message move together. The static directed graph stays fixed. The message-time multiset and its ties are preserved; edge-time multiplicities can change when messages have different target batch sizes.</p><p class="note">This is a bounded descriptive reference. Envelopes are not confidence intervals and rank counts are not p-values or significance tests. Message-time exchangeability is unestablished. The same selected windows are reused, with no independent replication, recipient exposure or causal identification.</p>']
    if addition["proof"]["passed"] is True:
        q = addition["quantities"]
        parts.append('<p>' + esc(f'{q["original_windows"]} original windows, {q["computed_cells"]}/{q["requested_cells"]} computed instrument cells, {q["resamples_requested_per_cell"]} requested draws per cell. Status: {q["status"]}.') + '</p>')
        rows, unavailable = [], []
        labels = {"reachable_pair_count": "Strict temporal reachable pairs", "maximum_loss_fraction": "Maximum endpoint-excluded deletion loss"}
        value = lambda x: "Undefined" if x is None else f'{x:.4g}'
        for wid, window in addition["windows"].items():
            for name, cell in window["variants"].items():
                if cell["available"] is not True or cell["reference"] is None:
                    unavailable.append((wid, name, cell["status"], cell.get("reason", "Unavailable")))
                    continue
                for metric, label in labels.items():
                    summary = cell["reference"]["metrics"][metric]
                    env, ranks = summary["envelope"], summary["rank_counts"]
                    envelope = "Undefined" if env is None else ' / '.join(value(env[k]) for k in ("minimum", "q25", "median", "q75", "maximum"))
                    comparison = "Undefined" if ranks is None else f'{ranks["less_than_observed"]} / {ranks["equal_to_observed"]} / {ranks["greater_than_observed"]}'
                    rows.append((wid, name, label, value(cell["observed"][metric]), envelope, comparison,
                                 summary["defined_draws"], summary["undefined_draws"]))
        if rows:
            parts.append(table("Descriptive counts only; columns compare the same frozen representation", ["Original window", "Instrument", "Metric", "Original", "Reference min / Q25 / median / Q75 / max", "Draws less / equal / greater than original", "Defined draws", "Undefined draws"], rows))
        if unavailable:
            parts.append(table("Uncomputed cells are unknown, without partial samples or rank counts", ["Original window", "Instrument", "Status", "Reason"], unavailable))
        parts.append('<p class="note">Undefined deletion denominators remain undefined; they are not zero-filled. Maximizing nodes and eligible-pair denominators may differ across assignments. Rank counts can be tied or degenerate and do not imply an inferential probability. A constant metric is not proof that assignments are identical. Empty reference graphs are not observed absence of agent behavior.</p>')
        parts.append('<details><summary>Original event pins, unchanged static signatures and fingerprinted synthetic assignments</summary>' + json_block(addition["windows"]) + '</details>')
    else:
        parts.append('<p class="alert">Current exact-source/code replay failed or is unavailable. Timestamp reference metrics, envelopes, ranks and event pins are withheld. A stored passing proof alone cannot approve them.</p>')
    parts.append('<p class="note">The reference direction is author to named agent. Scheduling, roles, tasks, common instructions and bursts are ordinary rival explanations. Representation node deletion is not an intervention. Synthetic timestamps have no original-source witness; source pins and observed timestamps are preserved. Original graphs, selection, experimental unit counts and library statuses stay unchanged.</p>')
    parts.append(render_addition_sources(addition))
    parts.append('<details><summary>Exact source references, work limits and fresh conditional regeneration</summary>' + json_block(addition) + '</details></section>')
    return ''.join(parts)


def render_html(report):
    summary = report["quantitative_summary"]
    sections = []
    sections.append('<section id="outcome"><h2>What the handoff pilot found</h2><p>' + esc(summary["plain_language"]) + '</p>')
    arm_rows = []
    for arm in ("baseline", "placebo", "evidence_thought"):
        runs = [r for r in report["runs"] if r["arm"] == arm]
        values = summary["arms"][arm]
        arm_rows.append((ARM_LABELS[arm], f'{values["correct"]}/{values["total"]}',
                         sum(r["outcomes"]["inspected_publication"] for r in runs),
                         sum(r["publisher_any_inspection"] for r in runs),
                         sum(r["publisher_inspected_published_version"] for r in runs)))
    sections.append(table("Registered success and actor/version-resolved inspection", ["Assigned context", "Correct / teams", "Any agent inspected published version (registered)", "Publisher inspected any version (exploratory)", "Publisher inspected published version (exploratory)"], arm_rows))
    sections.append('<p class="note">The inspection oracle counts any agent inspecting the later published version. It does not establish publisher inspection, positive verification, or receipt of a contradiction. Exploratory measures above do not replace the registered outcome.</p></section>')

    if "replication" in report:
        replication = report["replication"]
        rep_summary = replication["quantitative_summary"]
        comparison = replication["analysis"]["effects"]["evidence_thought_vs_baseline"]["success"]
        sections.append('<section id="replication"><h2>Fresh-seed replication: positive against this neutral note</h2><p>' + esc(rep_summary["plain_language"]) + '</p><p>The original pilot remains inconclusive; this later, separately frozen study has four teams per arm and disjoint environment seeds. It supports a positive active-versus-neutral contrast in this synthetic task. The same model, prompts, and world family are reused; historical causation, transfer, and a specific mechanism remain unestablished.</p>')
        sections.append(table("Replication outcomes and exploratory actor/version measures", ["Context", "Correct / teams", "Any agent inspected published version", "Publisher inspected any version", "Publisher inspected published version"], [
            (ARM_LABELS[arm], f'{rep_summary["arms"][arm]["correct"]}/{rep_summary["arms"][arm]["total"]}',
             sum(r["outcomes"]["inspected_publication"] for r in replication["runs"] if r["arm"] == arm),
             sum(r["publisher_any_inspection"] for r in replication["runs"] if r["arm"] == arm),
             sum(r["publisher_inspected_published_version"] for r in replication["runs"] if r["arm"] == arm))
            for arm in ("baseline", "placebo", "evidence_thought")]))
        sections.append('<p>Reminder versus baseline was ' + esc(f'{comparison["difference"]*100:+.1f}') + ' percentage points, with 95% interval ' + esc(f'{comparison["ci95"][0]*100:+.1f} to {comparison["ci95"][1]*100:+.1f}') + ' (exploratory). This does not establish improvement over no insertion. All neutral teams published on the coordinator’s first turn without its inspection. All active worlds were defective and repaired; baseline had two initially valid worlds. The active–neutral contrast may reflect a control-note effect, a specific checking instruction, delayed commitment, or other wording responses.</p><p>Inspection of the exact published version occurred in half of active and half of neutral teams, so that registered measure does not explain the contrast. Baseline run-0001 published a known missing-entry version after an explicit repair-needed message. Active run-0002 also sent stale repair requests after the artifact had already been repaired; version-qualified communication is a candidate for study, not an identified mediator.</p>')
        sections.append(table("Replication: each row is one team", ["Run", "Context", "Initial defect", "First schedule", "Correct", "Published version", "Steps"], [(r["run_id"], ARM_LABELS[r["arm"]], r["initial_defect"], ' → '.join(r["first_schedule"]), r["outcomes"]["success"], r["published_version"], r["outcomes"]["steps_used"]) for r in replication["runs"]]))
        sections.append('<details><summary>Replication protocol, trace-derived measures, role packets, and execution checks</summary>' + json_block(replication) + '</details><p class="note">The boundary bootstrap interval collapses when every active team succeeds and every neutral team fails. Use the registered Wilson/Newcombe interval and exact randomization test; the collapsed bootstrap is not certainty. This replication was planned after seeing the first pilot, so it is reported separately rather than silently pooling studies or treating the whole program as a single untouched test.</p></section>')

    sections.append('<section id="fit"><h2>Observation and experiment answer different questions</h2><p>The source messages support planned document handoffs and completion/pause narration. They do not verify a false completion claim, a defective artifact, blind reliance, or coordination failure. One author explicitly says that an initial draft still needs later updates.</p><p>The pilot constructs an inventory world with possible defects and a prior-shift readiness claim. It tests assigned private context in that world. It does not establish the historical mechanism or novelty.</p>')
    for evidence in report["source_evidence"]:
        sections.append('<details><summary>Source ' + esc(evidence["id"]) + ' · ' + esc(evidence.get("agent_name")) + ' · ' + esc(evidence.get("created_at")) + '</summary><blockquote>' + esc(evidence.get("content")) + '</blockquote>' + json_block({k: v for k, v in evidence.items() if k != "content"}) + '</details>')
    for theory in report["theories"]:
        value = theory["theory"]
        sections.append('<details><summary>Theory ' + esc(theory["id"]) + ' · version ' + esc(theory["version"]) + ' · ' + esc(value.get("status")) + '</summary><p>' + esc(value.get("statement")) + '</p>' + json_block({k: value.get(k) for k in ("mechanism", "falsifiers", "conflicting_results", "replication_ids", "replication_status", "generalization", "scope")}) + '</details>')
    sections.append('</section>')

    sections.append('<section id="runs"><h2>Executed trajectories</h2>')
    sections.append(table("Each row is one independent randomized team", ["Run", "Context", "Initial defect", "First schedule", "Correct", "Published version", "Steps", "Invalid actions"], [
        (r["run_id"], ARM_LABELS[r["arm"]], r["initial_defect"], ' → '.join(r["first_schedule"]), r["outcomes"]["success"], r["published_version"], r["outcomes"]["steps_used"], r["outcomes"].get("invalid_actions", 0)) for r in report["runs"]]))
    sections.append('<p>Neutral-note failures published at the coordinator’s first turn before repair. Active defective runs followed inspect → request repair → repair → inspect new version → publish. Baseline teams succeeded after repair without inspecting the new version. These are descriptive pathways, not identified mediators.</p>')
    for run in report["runs"]:
        sections.append('<details><summary>' + esc(run["run_id"]) + ': recorded actions and subject packets</summary>')
        for turn in run["turns"]:
            sections.append('<details class="turn"><summary>Step ' + esc(turn["step"]) + ' · ' + esc(turn["agent_id"]) + ' · ' + esc(turn.get("action", {}).get("action")) + '</summary>' + json_block(turn) + '</details>')
        sections.append('</details>')
    sections.append('</section>')

    sections.append('<section id="scope"><h2>Design limits and competing explanations</h2><p>Three teams per arm give little precision. Initial defects and scheduler orders differ by chance; this is not automatically systematic confounding, but opportunity can shape the pathways. All baseline worlds started defective. The neutral failures shared builder–verifier–coordinator order, yet a baseline team with the same first order succeeded.</p><p>The neutral note is substantive, not demonstrably inert. Generic caution, wording, recency, delayed publication, repair opportunity, and stochastic subject decisions remain rivals. Environment seeds do not seed hosted-model sampling. A fixed model name does not prove service stationarity.</p><p>Exact manifest equality is a narrow oracle. Historical document quality, open-world tools, persistent memory, other models, latent thoughts, and general social mechanisms remain outside this evidence.</p></section>')

    sections.append('<section id="record"><h2>Failed attempt, amendment, and commentary corrections</h2>')
    sections.append(table("All linked attempts retained", ["Object ID / version", "Status", "Completed teams", "Failure"], [(x["id"] + ' / ' + str(x["version"]), x["status"], x["completed_runs"], json.dumps(x.get("failure"))) for x in report["attempts"]]))
    sections.append('<p>Protocol amendment: ' + esc(report["protocol"].get("amends_protocol_id")) + ' → ' + esc(report["protocol"]["id"]) + '. ' + esc(report["protocol"].get("amendment_reason")) + '</p><p class="alert">The original evaluator prose incorrectly said active success was 2/3 while its own mean was 1.0. Executed outcomes give 3/3. A later digit-free summary also said active had more inspection than neutral; the registered inspection flag is 3/3 in both. Actor-specific exploratory measures differ, but cannot repair the original statement retrospectively. Original versions and review flags remain visible.</p>')
    for evaluation in report["evaluation_history"]:
        sections.append('<details><summary>' + esc(evaluation["id"]) + ' · version ' + esc(evaluation["version"]) + ' · ' + esc(evaluation["commentary_status"]) + '</summary><p>Model prose is a reviewed artifact, not the source of quantities.</p>' + json_block(evaluation) + '</details>')
    sections.append('</section>')

    if "network_pilot" in report:
        network = report["network_pilot"]
        sections.append('<section id="network"><h2>Network pilot: sparse realized communication</h2><p>Eight independent four-agent networks were assigned ring/complete topology and neutral/source-checking context, with two networks per cell. The focal agent was correct in every cell. Most verdicts had about one independent source available; cells averaged only half to one sent message per network. Assigned topology did not produce rich observed diffusion.</p>')
        effects = network["analysis"]["factor_effects"]
        sections.append(table("Run-level primary contrasts; intervals are individual, p-values cover both primary tests", ["Factor", "Difference", "95% interval", "Holm p"], [(e["factor"], f'{e["difference"]:+.3f}', f'[{e["ci95"][0]:+.3f}, {e["ci95"][1]:+.3f}]', f'{e["p_holm_primary_family"]:.3g}') for e in effects]))
        sections.append(table("Two networks per cell; four agents are not four independent trials", ["Cell", "Mean accuracy", "Focal accuracy", "Mean sent messages", "Mean sources at verdict"], [(name, f'{v["mean_accuracy"]:.3f}', v["focal_accuracy"], v["messages_sent"], v["mean_independent_sources_at_verdict"]) for name, v in network["analysis"]["cells"].items()]))
        sections.append('<p class="note">This pilot establishes neither network harm nor planted-context benefit. Wide uncertainty and scarce exchange leave the mechanism unconstrained. Collapsed bootstrap intervals at ceilings are not proof of certainty. A next task should create genuine informational complementarity, such as independently held evidence needed for the task, while allowing negative results.</p><details><summary>Network run outcomes, protocol, and replay</summary>' + json_block(network) + '</details></section>')

    if "complementary_pilot" in report:
        complementary = report["complementary_pilot"]
        quantities = complementary["quantities"]
        sections.append('<section id="complementary"><h2>Added study: complementary-information pilot at an accuracy floor</h2><p>Four subjects privately held independent uniform residues whose exact sum modulo q was the task target. This was a separate live task, frozen after the noisy-source pilot suggested insufficient informational complementarity. Its primary outcome averages exact-total correctness over all four subjects, including zero for missing submissions.</p>')
        sections.append('<p>' + esc(f'{quantities["networks_with_zero_accuracy"]}/{quantities["independent_networks"]} networks had zero accuracy. {quantities["valid_submissions"]}/{quantities["declared_subject_slots"]} subjects made valid submissions, all {quantities["valid_submissions"]} were incorrect; {quantities["absent_submissions"]} subjects made no valid submission. All {quantities["budget_terminations"]} networks ended at their action budgets.') + ' This is a retained negative performance result; it is not proof of an absent treatment or topology effect.</p>')
        sections.append(table("Registered whole-network contrasts; neither factor has observed accuracy variation", ["Factor", "Difference", "95% bounded interval", "Holm p"], [(e["factor"],f'{e["difference"]:+.3f}',f'[{e["ci95"][0]:+.3f}, {e["ci95"][1]:+.3f}]',f'{e["p_holm_primary_family"]:.3g}') for e in complementary["analysis"]["factor_effects"]]))
        sections.append('<p class="note">The all-zero accuracy floor and wide bounded intervals leave the performance mechanism unconstrained. Collapsed [0,0] bootstrap sensitivity intervals reflect a constant small sample, not certainty about the population. The default two-per-cell design has 36 conditional assignments per factor and minimum exact two-sided p=2/36, so it cannot reach 0.05 after Holm even with separation. This pilot establishes neither network equivalence nor a reminder benefit.</p>')
        sections.append(table("Cell means; network sample counts are distinct from agent submissions", ["Cell", "Networks", "Exact accuracy", "Completion", "Canonical originals at submission", "Dispatches / deliveries", "Relay attachment events per network"], [(name,v["n_networks"],v["mean_accuracy"],f'{v["completion_rate"]:.3f}',v["mean_unique_originals_at_submission"],f'{v["messages_sent"]} / {v["message_deliveries"]}',v["relay_attachment_events"]) for name,v in complementary["analysis"]["cells"].items()]))
        sections.append(table("Study totals recomputed from successful actions and recorded outcomes", ["Quantity", "Recorded count"], [("Successful unicast dispatches",quantities["successful_action_counts"]["send_message"]),("Neighbor multicast actions",quantities["neighbor_multicast_actions"]),("Successful waits",quantities["successful_action_counts"]["wait"]),("Valid submit-total actions",quantities["successful_action_counts"]["submit_total"]),("Inspection actions",quantities["successful_action_counts"]["inspect_fragment"]),("Recipient deliveries",quantities["recipient_deliveries"]),("Dispatches carrying canonical attachments",quantities["dispatches_with_canonical_attachments"]),("Relay attachment delivery events across the entire study",quantities["recorded_relay_attachment_events"]),("Successful action slots",quantities["valid_actions"])]))
        sections.append('<p>' + esc(f'The {quantities["successful_action_counts"]["send_message"]} successful unicast message actions produced {quantities["recipient_deliveries"]} recipient deliveries. {quantities["dispatches_with_canonical_attachments"]} dispatches carried canonical attachments; the entire study recorded {quantities["recorded_relay_attachment_events"]} relay attachment events.') + ' A cell mean of one relay event per network is not the study total. Every recorded subject schema and system prompt advertised neighbor multicast, yet no send_neighbors action occurred. These are executed tool-choice counts; they do not reveal why subjects selected their actions.</p><p>Canonical coverage measures recipient-scoped attachment inventory at first valid submission, with missing submissions contributing zero. Free-text messages can convey values without canonical attachments. Low attachment coverage therefore does not prove absent knowledge or identify the cause of incorrect answers. Multicast opportunity differs by degree, but no multicast use plus a performance floor prevents an isolated topology-mechanism interpretation.</p>')
        sections.append(table("Each row is one retained network",["Run","Topology","Context","Accuracy","Valid submissions","Unicast actions","Deliveries","Originals at submission","Termination"],[(r["run_id"],r["topology"],r["context"],r["outcomes"]["mean_accuracy"],len(r["final_state"]["submissions"]),r["outcomes"]["messages_sent"],r["outcomes"]["message_deliveries"],r["outcomes"]["mean_unique_originals_at_submission"],r["outcomes"]["terminated_by"]) for r in complementary["runs"]]))
        sections.append('<details><summary>Recorded action replay, analysis recomputation, execution source archive and claim checks</summary>' + json_block({k:complementary[k] for k in ("result","protocol","raw_file_sha256","canonical_execution_report_hash","hash_purposes","proof","analysis_recomputation","execution_archive","object_payload_hash_checks","stored_verification","claim_audit")}) + '</details><details><summary>Recorded requests, actions, submissions and canonical forwarding lineage</summary>' + json_block(complementary["runs"]) + '</details><p class="note">The archived-source check verifies local bytes against a manifest recorded before execution. It does not provide an externally attested timestamp or execute the archived source. Replay uses current validated code and saved actions, with zero new subject calls. The stored finite-claim audit checks report facts; free prose remains unverified.</p></section>')

    if "exploratory_graph_reviews" in report:
        graph_reviews = report["exploratory_graph_reviews"]
        sections.append('<section id="graph-sources"><h2>Added source group: repaired graph-guided candidate reviews</h2><p>These source episodes form a separate exploratory observational group. A directed-reciprocity lead motivated task-role coordination, and a bridge-dependence lead motivated owner/resource-gated waiting. Neither graph position nor reported waiting establishes actual inactivity, psychological traits, novelty, or causal influence.</p><p>A citation-schema aliasing defect had constrained explanatory list fields to evidence IDs. The repaired schema re-adjudicated the same proposals and retained source versions. Older outputs remain explicitly superseded; the repair does not create new observed behavior or retrospectively validate the former explanatory fields.</p>')
        for entry in graph_reviews["entries"]:
            candidate = entry["proposal_and_review"]
            sections.append('<h3>' + esc(candidate["name"]) + '</h3><p class="meta">' + esc(entry["behavior"]["id"]) + ' · version ' + esc(entry["behavior"]["version"]) + ' supersedes ' + esc(entry["superseded"]["id"]) + ' · version ' + esc(entry["superseded"]["version"]) + '</p><p>Candidate status: ' + esc(candidate["status"]) + '; novelty ' + esc(candidate["novelty_status"]) + '; causal support ' + esc(candidate["causal_support"]) + '. Identical proposal and source references: ' + esc(entry["unchanged_proposal_and_sources"]) + '.</p><details><summary>Agent interpretation and independent skepticism · unverified prose</summary>' + json_block(candidate) + '</details>')
            sections.append('<details><summary>Exact cited source messages, pinned object versions and selected graph lead</summary>' + json_block({k:entry[k] for k in ("source_refs","source_hash_checks","selected_graph_lead","source_evidence")}) + '</details><details><summary>Superseded review, amendment and recovered-input limitations</summary>' + json_block({k:entry[k] for k in ("superseded","research_attempt","scope")}) + '</details>')
        sections.append('<p class="note">Legacy proposal/source association was reconstructed from retained rows; the original research input archive was unavailable. Corrected source versions and proposal equality can be checked now, but that does not erase the older provenance limit. A skeptic’s narrative about search is not evidence that search tools ran. Task mix, participant presence, boundary truncation, sparse mentions, aliases, missing channels and temporal ordering remain rival explanations.</p></section>')

    if "graph_name_measurement_sensitivity" in report:
        measurement = report["graph_name_measurement_sensitivity"]
        sections.append('<section id="measurement"><h2>Added measurement audit: names change the diagnostic graph</h2><p>' + esc(f'The same {measurement["scope"]["message_count"]} agent-authored messages and {measurement["scope"]["effective_roster_count"]}-entry roster were measured under four separately labeled instruments, using a fixed {len(measurement["node_universe"]["ids"])}-node diagnostic universe.') + ' These are alternative measurements of unchanged source text, not separate societies or temporal behavior changes. The original graph remains unchanged.</p>')
        o3_ids = [identity for entry in measurement["allowlist_resolution"] if entry["requested_name"].lower() == "o3" for identity in entry["resolved_agent_ids"]]
        rows = []
        for name, variant in measurement["variants"].items():
            node = next((n for n in variant["metrics"]["nodes"] if n["id"] in o3_ids), {})
            metrics, spectral = variant["metrics"]["graph"], variant["spectral"]
            rows.append((name, variant["counts"]["projected_agent_event_count"], metrics["directed_edge_count"],
                         f'{metrics["weighted_reciprocity"]:.3f}', node.get("in_strength", "unavailable"),
                         spectral.get("nullity", "unavailable")))
        sections.append(table("Same fixed node universe; counts are message/target name-pattern pairs", ["Instrument", "Pairs", "Directed ties", "Weighted reciprocity", "Incoming o3 pairs", "Laplacian nullity"], rows))
        sections.append('<p class="note">Baseline exact 62 and short-name-expanded exact 143 become Unicode baseline 81 and expanded 162. Incoming o3 name matches change from 0 to 77 solely through the eligibility policy. That does not establish an actual hub, confirmed addressing, delivery, reading, influence or new behavior. The short-name additions include task-owner reports, model comparisons, human-question retellings and historical references; the local adjudication is a bounded model review, not calibrated labels or representative prevalence.</p><p>The fixed universe includes o1 as a referenced entity despite no o1-authored row in this window. Isolates and incoming references therefore have measurement and opportunity explanations. Directed degree/reciprocity are preserved for relational metrics; only the spectral operator symmetrizes weights. A changed normalized graph Laplacian is not evidence of a continuous manifold Laplace–Beltrami basis. Disconnected graphs, repeated eigenspaces, absent channels, undefined exposure rates and lack of temporal path checks limit interpretation.</p>')
        sections.append(render_addition_sources(measurement))
        sections.append('<details><summary>Fingerprints, alias policy, diagnostic metrics and current zero-call recomputation</summary>' + json_block({k:measurement[k] for k in ("dataset_fingerprint", "source_fingerprint", "roster_fingerprint", "analysis_versions", "scope", "allowlist_resolution", "eligibility_policy", "unicode_summary", "eligibility_summary", "node_universe", "variants", "proof", "stored_validation", "object_payload_hash_checks", "scope_note")}) + '</details><details><summary>Separately retained short-name candidates; source spans and IDs, not approved edges</summary>' + json_block(measurement["short_name_candidates"]) + '</details></section>')

    if "scripted_resource_workflow" in report:
        resource = report["scripted_resource_workflow"]
        quantities = resource["quantities"]
        effect = resource["analysis"]["primary_effect"]
        sections.append('<section id="resource"><h2>Added infrastructure workflow: scripted resource contention</h2><p>' + esc(f'{quantities["scripted_swarms"]} four-agent scripted swarms executed {quantities["action_slots"]} action slots and completed {quantities["executed_completed_tasks"]}/{quantities["declared_tasks"]} abstract tasks.') + ' They are separate from the live studies. The saved protocol, action records, zero-call replay and finite fact audit exercise the research workflow; they are not hosted subject trials.</p><p class="note">The deterministic policy ignores private context. Differences between its note-labeled cells cannot be empirical reminder effects or LLM findings. Independently sampled schedules and release opportunities produce differing realized task completion under this fixed script. Global computer exclusivity, lease rules, task costs and release dynamics are invented; historical agents also report simultaneous computer sessions.</p>')
        sections.append(table("Scripted cell means; tasks and actions do not increase the swarm sample count", ["Assigned note", "Scripted swarms", "Task completion", "Independent completion", "Computer completion", "Waits with independent work pending", "Waits per swarm"], [(name, cell["n_swarms"], f'{cell["task_completion_fraction"]:.4f}', cell["independent_completion_fraction"], cell["computer_completion_fraction"], cell["waits_while_independent_pending"], cell["waits"]) for name, cell in resource["analysis"]["cells"].items()]))
        sections.append('<p>' + esc(f'The arithmetic difference in recorded completion means is {effect["difference"]*100:+.2f} percentage points (task-reminder label minus neutral label). The stored formal randomization calculation is p={effect["p_two_sided"]:.3g}, with bounded interval [{effect["ci95"][0]}, {effect["ci95"][1]}].') + ' These are checks of the registered numerical machinery on a script, not empirical evidence of a context response. Four swarms, rather than 32 tasks or 96 turns, are the assigned units. Waiting and resource grants are executed process counts, not beliefs or identified mediators.</p>')
        sections.append(table("Every retained scripted swarm; timing differences remain visible", ["Run", "Assigned note", "Seed", "Release round", "First actor", "Completion", "Waits", "Termination"], [(run["run_id"], run["context"], run["environment_seed"], run["initial_state"]["release_round"], run["initial_state"]["schedule"][0], run["outcomes"]["task_completion_fraction"], run["outcomes"]["waits"], run["outcomes"]["terminated_by"]) for run in resource["runs"]]))
        sections.append(render_addition_sources(resource))
        sections.append('<details><summary>Scripted backend, exact result hashes, replay, archive and finite fact checks</summary>' + json_block({k:resource[k] for k in ("backend", "agent_mode", "evidence_scope", "raw_report_path", "raw_file_sha256", "canonical_execution_report_hash", "quantities", "proof", "execution_archive", "stored_verification", "claim_audit", "object_payload_hash_checks", "scope_note")}) + '</details><details><summary>Separate frozen resource protocol and numerical analysis</summary>' + json_block({k:resource[k] for k in ("protocol", "analysis")}) + '</details></section>')

    if 'selected_lead_measurement_sensitivity' in report:
        selected=report['selected_lead_measurement_sensitivity'];scope=selected['scope']
        sections.append('<section id="selected-leads"><h2>Added episode audit: freeze the comparisons, vary the instrument</h2><p>'+esc(f'{scope["selected_lead_count"]} selected leads retain their original orientation across {scope["selected_window_count"]} windows and {scope["ordered_pair_count"]} ordered pairs. All {scope["source_message_count"]} source rows, including {scope["all_source_human_message_count"]} human rows, remain in baseline replay.')+'</p><p class="note">These are conditional comparisons of the same source records. Extraction and node-universe choices can change a signed graph contrast; they do not establish changed swarm behavior, a causal mechanism, corrected address labels or independent replication. The original discovery and library statuses remain unchanged.</p>')
        variants=('baseline_exact','explicit_short_expanded_exact','unicode_baseline','unicode_expanded')
        if selected['proof']['passed']:
            for policy,label in [('native','Native window node universes'),('fixed_pair','Fixed nodes within each original window pair')]:
                sections.append(table(label,['Lead / feature',*variants],[(lead['lead_id']+' / '+lead['feature'],
                    *[('undefined' if lead[policy][v]['difference'] is None else f'{lead[policy][v]["difference"]:+.6f}') for v in variants]) for lead in selected['per_lead']]))
        else:sections.append('<p class="note">Current recomputation failed; retained numerical claims are unverified and no derived contrast table is presented.</p>')
        sections.append(render_addition_sources(selected))
        sections.append('<details><summary>Replay, negative controls, original selection and signed decomposition</summary>'+json_block(selected)+'</details></section>')

    if "temporal_reference_paths" in report:
        sections.append(render_temporal_addition(report["temporal_reference_paths"]))
    if "scripted_timed_resource_workflow" in report:
        sections.append(render_timed_resource_addition(report["scripted_timed_resource_workflow"]))
    if "bounded_source_lineage" in report:
        sections.append(render_source_lineage_addition(report["bounded_source_lineage"]))
    if "indexed_selected_events" in report:
        sections.append(render_indexed_event_addition(report["indexed_selected_events"]))
    if "conditional_temporal_reference" in report:
        sections.append(render_temporal_reference_addition(report["conditional_temporal_reference"]))
    if "selected_actor_events" in report:
        sections.append(render_actor_event_addition(report["selected_actor_events"], report.get("indexed_selected_events")))
    if "literal_wait_marker_alignment" in report:
        sections.append(render_wait_marker_addition(report["literal_wait_marker_alignment"]))
    if "static_edge_count_decomposition" in report:
        sections.append(render_graph_hodge_addition(report["static_edge_count_decomposition"]))

    sections.append('<section id="proof"><h2>Execution proof and provenance</h2><p>Report generation uses read-only local records and zero new model calls. Action replay checks the saved initial state, subject packets, tool results, final state, and oracle. It validates recorded execution, not fresh model replication or historical fidelity. A code/hash mismatch is shown as an unresolved check.</p>' + json_block(report["proof"]) + '<details><summary>Frozen protocol and exact intervention texts</summary>' + json_block(report["protocol"]) + '</details><details><summary>Object IDs, hashes, and trace scope</summary>' + json_block({k: report[k] for k in ("result", "behavior", "dataset", "raw_report_path", "raw_file_sha256", "canonical_execution_report_hash", "trace_summary")}) + '</details></section>')
    network_next = ('In a separately frozen follow-up, distinguish interface/tool choice, available action budget, arithmetic accuracy and evidence exchange using declared process metrics. Validate that the task avoids a universal floor without selecting on realized outcomes or changing the retained pilot. Do not force a positive reminder or topology effect.' if "complementary_pilot" in report else 'For network behavior, require complementary evidence for task success and measure actual exchange without assuming topology alone creates diffusion.')
    sections.append('<section id="next"><h2>Smallest useful next tests</h2><ol><li>Retrieve bounded source sessions and follow-up messages to verify the historical artifact handoff before diagnosing failure.</li><li>Keep original outcomes and add actor/version-resolved inspection and message-delivery descriptions.</li><li>In a new frozen protocol, block on artifact and scheduler, comparing evidence reminder with neutral and generic caution. Predeclare publication timing, repair opportunity, and final validity.</li><li>Cross readiness-claim presence with reminder context to distinguish claim reliance from general task solving.</li><li>' + esc(network_next) + '</li><li>Manually reconstruct graph mention targets, availability and temporal handoffs, then expand windows and compare similarly task-heavy episodes before attributing graph changes to a social mechanism.</li></ol><p>These follow-ups are proposed. The complementary pilot, if included, is recorded separately above; this generator starts no experiments.</p></section>')
    style = """body{font:17px/1.6 system-ui,sans-serif;margin:0;background:#f3f5f7;color:#172331}main{max-width:1120px;margin:auto;padding:30px 22px 60px}h1{font-size:2.25rem;line-height:1.15}h2{font-size:1.45rem;line-height:1.3}header{padding:8px 0 22px}section{background:white;border:1px solid #dbe1e8;border-radius:12px;margin:20px 0;padding:22px}nav{display:flex;gap:16px;flex-wrap:wrap}a{color:#075da6;text-underline-offset:3px}a:focus,summary:focus{outline:3px solid #ecaf16;outline-offset:3px}.eyebrow{font-size:.85rem;letter-spacing:.08em;color:#485669;text-transform:uppercase}.lead{font-size:1.15rem;max-width:85ch}.badge{display:inline-block;background:#fff0c7;color:#5f4200;padding:6px 12px;border-radius:20px;font-weight:650}.table-scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.9rem;margin:18px 0}caption{text-align:left;font-weight:650;margin-bottom:9px}th,td{text-align:left;padding:10px;border-bottom:1px solid #dbe1e8;vertical-align:top}thead{background:#eff3f7}details{border:1px solid #dbe1e8;border-radius:7px;margin:10px 0;padding:10px 13px}summary{cursor:pointer;overflow-wrap:anywhere;font-weight:600}details.turn{margin-left:12px}pre{font-size:.78rem;background:#f0f3f7;padding:14px;white-space:pre-wrap;overflow-wrap:anywhere;max-height:550px;overflow:auto}blockquote{margin:15px 0;padding:12px 18px;border-left:4px solid #3684ad;white-space:pre-wrap}.note,.alert{padding:13px 16px;border-left:4px solid #e0a110;background:#fff7e4}.meta{font-size:.85rem;color:#485669;overflow-wrap:anywhere}@media(max-width:650px){main{padding:18px 12px}section{padding:16px}h1{font-size:1.85rem}body{font-size:16px}}@media print{body{background:white}section{break-inside:avoid}nav{display:none}pre{max-height:none}}"""
    lead = ('A fresh-seed replication supports better publication under the evidence reminder than under this neutral note in the synthetic task. Improvement over no insertion, the communication mechanism, historical causation, and generality remain unestablished.' if "replication" in report else 'The live pilots demonstrate a functioning research workflow. Their small samples and task limitations leave reminder effects, network effects, historical causation, and social mechanisms uncertain.')
    if "complementary_pilot" in report:
        lead += ' The added complementary-information pilot retained an all-zero accuracy result; its topology and context mechanisms remain unresolved.'
    replication_link = '<a href="#replication">Replication</a>' if "replication" in report else ''
    addition_links = ('<a href="#network">Noisy network</a>' if "network_pilot" in report else '') + ('<a href="#complementary">Complementary pilot</a>' if "complementary_pilot" in report else '') + ('<a href="#graph-sources">Graph source group</a>' if "exploratory_graph_reviews" in report else '') + ('<a href="#measurement">Measurement sensitivity</a>' if "graph_name_measurement_sensitivity" in report else '') + ('<a href="#resource">Scripted workflow</a>' if "scripted_resource_workflow" in report else '') + ('<a href="#selected-leads">Selected episodes</a>' if 'selected_lead_measurement_sensitivity' in report else '')
    addition_links += ('<a href="#temporal-paths">Temporal paths</a>' if "temporal_reference_paths" in report else '') + ('<a href="#timed-resource">Timed workflow</a>' if "scripted_timed_resource_workflow" in report else '')
    addition_links += '<a href="#source-lineage">Source lineage</a>' if "bounded_source_lineage" in report else ''
    addition_links += '<a href="#indexed-events">Selected-window events</a>' if "indexed_selected_events" in report else ''
    addition_links += '<a href="#timestamp-reference">Timestamp reference</a>' if "conditional_temporal_reference" in report else ''
    addition_links += '<a href="#actor-events">Actor/time events</a>' if "selected_actor_events" in report else ''
    addition_links += '<a href="#wait-markers">Literal wait/action proximity</a>' if "literal_wait_marker_alignment" in report else ''
    addition_links += '<a href="#edge-flow">Static edge-count algebra</a>' if "static_edge_count_decomposition" in report else ''
    inventory = report.get("execution_inventory")
    unit_notice = ('<p class="meta">' + esc(f'{inventory["completed_live_units"]} completed live team/network units · {inventory["completed_scripted_resource_units"]} separate scripted resource units') + '</p>' + table("Retained live studies; different tasks are not pooled", ["Study", "Units", "Unit definition"], [(group["label"],group["units"],group["unit"]) for group in inventory["live_groups"]]) if inventory else '')
    if inventory and "scripted_timed_resource_workflow" in report:
        unit_notice += ('<p class="meta">Timed-reminder counts withheld pending verification.</p>' if inventory["unverified_scripted_sections"] else
            '<p class="meta">' + esc(f'{inventory["completed_scripted_timed_resource_units"]} separate scripted timed-reminder units · {inventory["scripted_timed_independent_seed_blocks"]} independent paired seed blocks') + '</p>')
    notice = '<p class="note">This generated edition explicitly identifies added studies, graph-source reviews, measurement audits, bounded source lineage and scripted infrastructure when listed below. The original handoff, seed replication, noisy-network results and correction history retain their separate scopes. Estimates are not pooled.</p>' + unit_notice + '<details><summary>Edition scope, additions and prior report preservation</summary>' + json_block({k:report.get(k) for k in ("generated_at","audit_scope","addition_notice","execution_inventory","regeneration")}) + '</details>'
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>Swarm Research Lab — pilot audit</title><style>' + style + '</style></head><body><main><header><p class="eyebrow">Swarm Research Lab · computational social science</p><h1>Execution verified. Mechanisms remain open.</h1><p class="lead">' + lead + '</p><p><span class="badge">Initial handoff pilot: ' + esc(summary["primary_conclusion"]) + '</span></p><p class="meta">Generated ' + esc(report["generated_at"]) + ' · ' + esc(report["result"]["id"]) + ' · zero new model calls</p>' + notice + '<nav aria-label="Report sections"><a href="#outcome">Initial results</a>' + replication_link + addition_links + '<a href="#fit">Source fit</a><a href="#runs">Trajectories</a><a href="#scope">Scope</a><a href="#record">Corrections</a><a href="#proof">Proof</a><a href="#next">Next tests</a></nav></header>' + ''.join(sections) + '<footer class="meta">Self-contained HTML. All source content is escaped. No external scripts, network requests, or model calls are required to read this report.</footer></main></body></html>'


def write_report(output_dir, report):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    safe = clean(report)
    json_path = output / "research-report.json"
    html_path = output / "research-report.html"
    previous = {}
    if json_path.exists() or html_path.exists():
        history = output / "history"
        history.mkdir(parents=True, exist_ok=True)
        for path in (json_path,html_path):
            if not path.exists():
                continue
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            destination = history / ("research-report-" + digest[:16] + path.suffix)
            if destination.exists() and destination.read_bytes() != data:
                raise ValueError("Prior report preservation hash-prefix conflict")
            destination.write_bytes(data)
            previous["preserved_" + path.suffix[1:]] = {"path": str(destination), "sha256": digest}
            if path.suffix == ".json":
                try:
                    old = json.loads(data)
                    previous.update({"generated_at": old.get("generated_at"), "audit_scope": old.get("audit_scope"),
                                     "result_id": old.get("result", {}).get("id")})
                except (ValueError,TypeError):
                    previous["metadata_status"] = "Unparsed previous file retained byte-for-byte"
    safe["regeneration"] = {"previous_generation": previous or None,
                            "scope": "A prior local report edition is preserved byte-for-byte before replacement. Scientific source records are opened read-only, and new sections are explicitly identified."}
    json_path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(render_html(safe), encoding="utf-8")
    return html_path, json_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=REPO_ROOT / ".runtime/lab.sqlite3")
    parser.add_argument("--result", default="experiment-f8ebb002aa60")
    parser.add_argument("--network-result", default="network_experiment-b215b2b47aef")
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--replication-result", default="experiment-b46d02ce332c")
    parser.add_argument("--no-replication", action="store_true")
    parser.add_argument("--complementary-result", default=COMPLEMENTARY_RESULT)
    parser.add_argument("--no-complementary", action="store_true")
    parser.add_argument("--no-graph-reviews", action="store_true")
    parser.add_argument("--no-measurement", action="store_true")
    parser.add_argument("--no-resource", action="store_true")
    parser.add_argument('--no-selected-leads',action='store_true')
    parser.add_argument('--no-temporal-paths', action='store_true')
    parser.add_argument('--no-timed-resource', action='store_true')
    parser.add_argument('--no-source-lineage', action='store_true')
    parser.add_argument('--no-indexed-events', action='store_true')
    parser.add_argument('--no-temporal-reference', action='store_true')
    parser.add_argument('--no-actor-events', action='store_true')
    parser.add_argument('--no-wait-markers', action='store_true')
    parser.add_argument('--no-edge-flow', action='store_true')
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / ".runtime/reports/pilot-audit")
    args = parser.parse_args(argv)
    report = collect_report(args.database, args.result, None if args.no_network else args.network_result,
                            None if args.no_replication else args.replication_result,
                            None if args.no_complementary else args.complementary_result,
                            None if args.no_graph_reviews else GRAPH_REVIEW_PAIRS,
                            include_measurement=not args.no_measurement, include_resource=not args.no_resource,
                            include_selected_leads=not args.no_selected_leads,
                            include_temporal_paths=not args.no_temporal_paths,
                            include_timed_resource=not args.no_timed_resource,
                            include_source_lineage=not args.no_source_lineage,
                            include_indexed_events=not args.no_indexed_events,
                            include_temporal_reference=not args.no_temporal_reference,
                            include_actor_events=not args.no_actor_events,
                            include_wait_markers=not args.no_wait_markers,
                            include_graph_hodge=not args.no_edge_flow)
    html_path, json_path = write_report(args.out_dir, report)
    print(json.dumps({"html": str(html_path.resolve()), "json": str(json_path.resolve()), "new_model_calls": 0,
                      "handoff_replay_passed": report["proof"]["current_action_replay"]["passed"],
                      "analysis_recomputed": report["proof"]["analysis_recomputation"]["passed"],
                      "network_replay_passed": report.get("network_pilot", {}).get("proof", {}).get("passed"),
                      "replication_replay_passed": report.get("replication", {}).get("proof", {}).get("passed"),
                      "complementary_replay_passed": report.get("complementary_pilot", {}).get("proof", {}).get("passed"),
                      "graph_reviews": len(report.get("exploratory_graph_reviews", {}).get("entries", [])),
                      "measurement_recomputation_passed": report.get("graph_name_measurement_sensitivity", {}).get("proof", {}).get("passed"),
                      "resource_replay_passed": report.get("scripted_resource_workflow", {}).get("proof", {}).get("passed"),
                      'selected_lead_recomputation_passed':report.get('selected_lead_measurement_sensitivity',{}).get('proof',{}).get('passed'),
                      'temporal_path_replay_passed': report.get('temporal_reference_paths', {}).get('proof', {}).get('passed'),
                      'timed_resource_replay_passed': report.get('scripted_timed_resource_workflow', {}).get('proof', {}).get('passed'),
                      'source_lineage_reread_passed': report.get('bounded_source_lineage', {}).get('proof', {}).get('passed'),
                      'indexed_events_replay_passed': report.get('indexed_selected_events', {}).get('proof', {}).get('passed'),
                      'temporal_reference_replay_passed': report.get('conditional_temporal_reference', {}).get('proof', {}).get('passed'),
                      'actor_events_replay_passed': report.get('selected_actor_events', {}).get('proof', {}).get('passed'),
                      'wait_markers_replay_passed': report.get('literal_wait_marker_alignment', {}).get('proof', {}).get('passed'),
                      'edge_flow_replay_passed': report.get('static_edge_count_decomposition', {}).get('proof', {}).get('passed'),
                      "execution_inventory": report["execution_inventory"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
