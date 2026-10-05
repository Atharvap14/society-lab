"""Separate, bounded four-cell correction-availability experiment.

Local receipts and replay authenticate constructed inputs/actions, never provider
consumption, mental states or historical mechanisms. No registry/model calls.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import importlib.util
import json
import math
import platform
import random
from pathlib import Path

from swarm_lab import harness as subject_adapter
from swarm_lab import store as store_module

if __package__:
    from . import revision_relay_env as world
else:  # Design staging and independent CPU fixtures; fixed sibling only.
    _spec = importlib.util.spec_from_file_location(
        "_staged_relay_world", Path(__file__).with_name("revision_relay_env.py"))
    world = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(world)

API_VERSION = "1.0"
STUDY_KIND = "paired_revision_relay_factorial"
CELLS = (("early", "sham"), ("late", "sham"),
         ("early", "informative"), ("late", "informative"))
SYSTEM = "Act only on your role-scoped environment observation. Return one action as a JSON object."
OFFLINE_BACKEND = {"harness": "scripted", "model": "revision_relay_scoped_policy",
                   "generation": {"policy": "revision_relay_scoped_policy"}}
MAX_PROTOCOL_BYTES = 65536
MAX_REQUEST_BYTES = 65536
MAX_RUN_BYTES = 262144
MAX_REPORT_BYTES = 64 * 1024 * 1024
SOURCE_REF_NAMES = {"behavior", "dataset", "discovery", "selected_audit", "temporal_audit",
                    "actor_audit", "wait_audit", "hodge_audit"}
_PROJECT = Path(store_module.__file__).resolve().parents[1]
_CODE_PATHS = {"revision_relay_experiments.py": Path(__file__),
               "revision_relay_env.py": Path(world.__file__),
               "harness.py": Path(subject_adapter.__file__), "store.py": Path(store_module.__file__)}
_DOC_PATHS = {name: _PROJECT / "research" / "theory" / name for name in (
    "correction-relay-experiment-draft.md", "correction-relay-experiment-review.md")}


def _bounded(value, cap, *, depth=32, nodes=1000000):
    stack = [(value, 0)]; visited = 0; approximate = 0
    while stack:
        item, level = stack.pop(); visited += 1
        if level > depth or visited > nodes:
            raise ValueError("JSON nesting/item limit exceeded")
        kind = type(item)
        if item is None or kind is bool:
            approximate += 5
        elif kind is int:
            if abs(item) > 10 ** 100: raise ValueError("JSON integer bound exceeded")
            approximate += 102
        elif kind is float:
            if not math.isfinite(item): raise ValueError("JSON must be finite")
            approximate += 24
        elif kind is str:
            if len(item) > cap or any(0xD800 <= ord(c) <= 0xDFFF for c in item):
                raise ValueError("JSON string bound exceeded")
            approximate += len(item)
        elif kind is list:
            if len(item) > nodes: raise ValueError("JSON list bound exceeded")
            stack.extend((child, level + 1) for child in item)
        elif kind is dict:
            if len(item) > nodes or any(type(k) is not str for k in item):
                raise ValueError("JSON object shape invalid")
            stack.extend((child, level + 1) for pair in item.items() for child in pair)
        else: raise ValueError("Use ordinary finite JSON values")
        if approximate > cap * 4: raise ValueError("JSON accepted-size limit exceeded")
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    if len(text.encode("utf-8")) > cap: raise ValueError("JSON accepted-size limit exceeded")
    return text


def _hash(value):
    return hashlib.sha256(_bounded(value, MAX_REPORT_BYTES).encode("utf-8")).hexdigest()


def _same(left, right):
    return _bounded(left, MAX_REPORT_BYTES) == _bounded(right, MAX_REPORT_BYTES)


def _copy(value, cap=MAX_REPORT_BYTES):
    return json.loads(_bounded(value, cap))


def _now(): return dt.datetime.now(dt.timezone.utc).isoformat()


def _files(paths):
    return {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}


def revision_relay_code_hashes(): return _files(_CODE_PATHS)


def _guard():
    if not _same(revision_relay_code_hashes(), _LOADED_CODE):
        raise ValueError("Loaded revision-relay execution sources changed")


def _seal(body, key):
    body = _copy(body); body.pop(key, None)
    return {**body, key: _hash(body)}


def _integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be integer in [{low},{high}]")
    return value


def _reference(ref):
    if (type(ref) is not dict or set(ref) != {"id", "version", "hash"}
            or type(ref["id"]) is not str or not 1 <= len(ref["id"]) <= 200
            or type(ref["version"]) is not int or not 1 <= ref["version"] <= 10 ** 9
            or type(ref["hash"]) is not str or len(ref["hash"]) != 64
            or any(c not in "0123456789abcdef" for c in ref["hash"])):
        raise ValueError("Use an exact bounded source reference")


def _backend(value):
    _bounded(value, 8192, nodes=256)
    if _same(value, OFFLINE_BACKEND): return _copy(value)
    if (type(value) is not dict or value.get("harness") not in ("callback", "responses")
            or set(value) != ({"harness", "model", "generation", "harness_adapter_hash"}
                             if value.get("harness") == "responses" else {"harness", "model", "generation"})
            or type(value.get("model")) is not str or not 1 <= len(value["model"]) <= 120
            or not _same(value.get("generation"), {"max_output_tokens": 600,
                        "temperature": "provider_default", "sampling_seed": "not_set"})):
        raise ValueError("Declare the scripted, callback or pinned Responses backend")
    if value["harness"] == "responses" and value["harness_adapter_hash"] != revision_relay_code_hashes()["harness.py"]:
        raise ValueError("Responses subject adapter differs from pinned source")
    return _copy(value)


def _body(blocks, seed, backend, source_refs, assumptions, created_at, code, docs):
    _integer(blocks, 1, 64, "blocks"); _integer(seed, 0, 2 ** 63 - 1, "seed")
    backend = _backend(backend)
    if type(source_refs) is not dict or set(source_refs) - SOURCE_REF_NAMES:
        raise ValueError("Use the bounded source-reference names")
    for ref in source_refs.values(): _reference(ref)
    if (type(assumptions) is not dict or set(assumptions) != {
            "independent_blocks_declared", "stable_subject_backend_declared"}
            or any(type(v) is not bool for v in assumptions.values())):
        raise ValueError("Interval assumptions must be explicit booleans")
    if type(created_at) is not str or len(created_at) > 40:
        raise ValueError("Use the recorded local UTC registration time")
    stamp = dt.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    if stamp.utcoffset() != dt.timedelta(0): raise ValueError("Registration time must be UTC")
    spec = world.create_revision_relay_spec()
    return {"api_version": API_VERSION, "study_kind": STUDY_KIND,
        "created_at": created_at, "status": "frozen_before_execution",
        "registration_scope": "local_registration_not_external_timestamp_attestation",
        "phase": "mechanics_and_descriptive_pilot", "environment": spec,
        "environment_hash": _hash(spec), "subject_backend": backend, "source_refs": _copy(source_refs),
        "design": {"blocks": blocks, "seed": seed, "cells": [list(c) for c in CELLS],
            "unit": "whole_two_subject_team", "uncertainty_unit": "seed_block",
            "execution_order": "fixed_block_order_uniform_cell_shuffle_within_block",
            "exogenous_pairing": "source_records_C_private_oracle_seed_spec_schedule_only",
            "maximum_subject_calls": 16 * blocks, "maximum_teams": 4 * blocks,
            "scheduled_decisions": [{"agent_id": r, "ordinal_boundary": b} for r,b in world.SCHEDULE],
            "stopping": "all_four_opportunities_no_behavioral_exclusion_no_infrastructure_replacement"},
        "request_contract": {"system": SYSTEM, "scope": "recipient_only_no_assignment_seed_oracle_future",
            "private_context_insertion": False, "receipt": "local_construction_not_provider_consumption",
            "action_retention": "adapter_replayable_bounded_sentinel",
            "sanitization": "bounded_JSON_action_Store_clean_before_step_disclosed_hash_only_original"},
        "measurement": {"primary": "C_final_correct", "oracle": "revision2_exact_modular_total_explicit_final",
            "interaction": "(late_sham-early_sham)-(late_informative-early_informative)",
            "range": [-2,2], "p_value": None, "interaction_randomization_test": None,
            "interval": {"method": "conditional_independent_block_Hoeffding", "alpha": 0.05,
                "assumptions": _copy(assumptions), "attestation": "declared_not_verified"},
            "minimum_meaningful_effect": None, "incomplete_grid": "analysis_unavailable_no_subset_estimate"},
        "bounds": {"protocol_bytes": MAX_PROTOCOL_BYTES, "request_bytes": MAX_REQUEST_BYTES,
            "run_bytes": MAX_RUN_BYTES, "report_bytes": MAX_REPORT_BYTES, "json_depth": 32},
        "execution_code_hashes": code, "design_source_hashes": docs,
        "limitations": ["Assigned correction availability/bypass packages, not reminder efficacy or mental-state intervention.",
            "Within-team interference intended; source inventories are not mental knowledge.",
            "Fresh requests and randomized slots do not verify provider consumption, stability or block independence.",
            "No interaction p-value; conditional bounds fail under unaccounted shared provider drift.",
            "Scripted feasibility is infrastructure evidence only; no historical or model effect established."]}


def create_revision_relay_protocol(blocks=2, seed=173, *, subject_backend=None,
        source_refs=None, interval_assumptions=None, alpha=0.05):
    _guard()
    if type(alpha) is not float or alpha != 0.05: raise ValueError("Only preregistered alpha0.05 supported")
    result = _seal(_body(blocks, seed, OFFLINE_BACKEND if subject_backend is None else subject_backend,
        {} if source_refs is None else source_refs,
        {"independent_blocks_declared": False, "stable_subject_backend_declared": False}
            if interval_assumptions is None else interval_assumptions,
        _now(), revision_relay_code_hashes(), _files(_DOC_PATHS)), "protocol_hash")
    _bounded(result, MAX_PROTOCOL_BYTES)
    return result


def validate_revision_relay_protocol(protocol):
    _guard(); _bounded(protocol, MAX_PROTOCOL_BYTES)
    if type(protocol) is not dict: raise ValueError("Use a sealed revision-relay protocol")
    body = {k:v for k,v in protocol.items() if k != "protocol_hash"}
    if protocol.get("protocol_hash") != _hash(body): raise ValueError("Frozen protocol changed")
    try:
        expected = _body(body["design"]["blocks"], body["design"]["seed"], body["subject_backend"],
            body["source_refs"], body["measurement"]["interval"]["assumptions"], body["created_at"],
            revision_relay_code_hashes(), _files(_DOC_PATHS))
        if not _same(expected, body): raise ValueError("Unsupported declarations or changed pinned sources")
        world.validate_revision_relay_spec(body["environment"])
    except (KeyError, TypeError, OverflowError, RecursionError) as error:
        raise ValueError("Malformed revision-relay protocol") from error


def _seed(seed, namespace, index): return int(_hash([seed, namespace, index])[:15], 16)


def randomize_revision_relay_runs(protocol):
    validate_revision_relay_protocol(protocol); design = protocol["design"]; rows = []; seeds = set()
    for block in range(design["blocks"]):
        seed = _seed(design["seed"], "relay_exogenous", block)
        if seed in seeds: raise ValueError("Exogenous block seed collision")
        seeds.add(seed); cells = list(CELLS)
        random.Random(_seed(design["seed"], "relay_slot_assignment", block)).shuffle(cells)
        for slot, (timing, bypass) in enumerate(cells):
            rows.append({"run_id": f"relay-{block+1:04d}-{slot}", "block_id": f"block-{block+1:04d}",
                "block_index": block, "slot": slot, "execution_index": len(rows),
                "timing": timing, "bypass": bypass, "environment_seed": seed})
    return rows


def _environment(protocol, row):
    return world.create_revision_relay_environment(protocol["environment"], row["environment_seed"],
        timing=row["timing"], bypass=row["bypass"])


def _exogenous(snapshot):
    return {k:_copy(snapshot[k]) for k in ("source_records", "C_private_residue", "oracle_total", "seed", "spec_hash")} | {
        "schedule": [list(row) for row in world.SCHEDULE]}


def _request(env):
    if any(env.snapshot()["contexts"].values()): raise ValueError("This study forbids context insertion")
    request = {**world.revision_relay_subject_request(env, env.next_agent), "system": SYSTEM}
    _bounded(request, MAX_REQUEST_BYTES)
    if not _same(store_module.clean(request), request): raise ValueError("Request sanitizer identity changed")
    return request


def revision_relay_scoped_policy(request):
    observation = request["observation"]
    records = [r for r in observation["known_records"] if r["artifact_id"] == "artifact-main"]
    record = max(records, key=lambda r:r["revision"]) if records else None
    if request["agent_id"] == "B":
        return {"action": "forward", "record_ids": [record["record_id"]] if record else [],
                "message": "Canonical task record attached." if record else ""}
    if record is None: return {"action": "wait"}
    return {"action": "draft" if observation["decision_phase"] == "draft" else "revise",
        "revision": record["revision"], "total": (record["value"] + observation["your_private_residue"]) % world.MODULUS}


def _action(raw):
    try:
        world._bounded_json(raw)  # Exact released adapter cardinality/key/string contract.
        _bounded(raw, world.MAX_RETAINED_ACTION_BYTES, depth=8, nodes=128)
        digest = _hash(raw); clean = store_module.clean(raw)
        return clean, {"status": "sanitized_before_execution" if not _same(clean, raw) else "bounded_original",
                       "original_output_hash": digest}
    except (ValueError, TypeError, OverflowError, RecursionError):
        return _copy(world.INVALID_RETAINED_ACTION), {
            "status": "unbounded_or_nonfinite_original_unretained", "original_output_hash": None}


def _retention(action, record):
    if type(record) is not dict or set(record)!={"status","original_output_hash"}:
        raise ValueError("Action retention shape changed")
    status=record["status"]; digest=record["original_output_hash"]
    if status=="unbounded_or_nonfinite_original_unretained":
        if digest is not None or not _same(action,world.INVALID_RETAINED_ACTION):
            raise ValueError("Invalid sentinel retention changed")
    elif status in ("bounded_original","sanitized_before_execution"):
        if type(digest) is not str or len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Action output hash malformed")
        if status=="bounded_original" and digest!=_hash(action):
            raise ValueError("Retained action hash changed")
        if status=="sanitized_before_execution" and digest==_hash(action):
            raise ValueError("Sanitization claims an unchanged action identity")
    else: raise ValueError("Unsupported action retention status")
    world._bounded_json(action)
    _bounded(action,world.MAX_RETAINED_ACTION_BYTES,depth=8,nodes=128)
    if not _same(store_module.clean(action),action): raise ValueError("Executed action is not sanitizer-stable")


def _counts(row, scripted):
    return {"subject_call_attempts": sum(b["invocation_status"] != "not_attempted" for b in row["boundaries"]),
        "applied_actions": len(row["turns"]), "completed_opportunities": len(row["turns"]),
        "model_calls": 0 if scripted else None}


def _pair_checks(runs):
    checks = []
    for block in dict.fromkeys(r["block_id"] for r in runs):
        group = [r for r in runs if r["block_id"] == block]
        good = (len(group) == 4 and all(r["initial_state"] is not None for r in group)
            and all(_same(group[0]["exogenous_identity"], r["exogenous_identity"]) for r in group))
        checks.append({"block_id": block, "passed": good, "scope": "exogenous_projection_not_initial_inventory"})
    return checks


def analyze_revision_relay_runs(runs, protocol):
    assignments = randomize_revision_relay_runs(protocol)
    if len(runs) != len(assignments) or any(not _same({k:r.get(k) for k in u}, u) for r,u in zip(runs, assignments)):
        raise ValueError("Retain the complete registered grid in execution order")
    if not all(c["passed"] for c in _pair_checks(runs)): raise ValueError("Exogenous pairing failed")
    for row in runs:
        y = (row.get("outcomes") or {}).get("C_final_correct")
        if row["status"] != "complete" or type(y) is not int or y not in (0,1) or not row["outcomes"].get("terminal"):
            raise ValueError("Every assigned completed oracle outcome is required")
    differences = []; cells = {}
    for block in dict.fromkeys(r["block_id"] for r in runs):
        ys = {(r["timing"],r["bypass"]): r["outcomes"]["C_final_correct"] for r in runs if r["block_id"] == block}
        differences.append({"block_id": block, "difference": (ys["late","sham"]-ys["early","sham"])
            -(ys["late","informative"]-ys["early","informative"])})
    for timing,bypass in CELLS:
        group = [r for r in runs if (r["timing"],r["bypass"]) == (timing,bypass)]
        cells[timing+"_"+bypass] = {"teams": len(group), "correct": sum(r["outcomes"]["C_final_correct"] for r in group),
            "mean_correctness": sum(r["outcomes"]["C_final_correct"] for r in group)/len(group)}
    n = len(differences); estimate = sum(r["difference"] for r in differences)/n
    declared = protocol["measurement"]["interval"]["assumptions"]
    available = all(declared.values()); bounds = None
    if available:
        radius = 4*math.sqrt(math.log(2/0.05)/(2*n))
        bounds = [max(-2, estimate-radius), min(2, estimate+radius)]
    return {"cells": cells, "block_contrasts": differences, "mean_interaction": estimate,
        "independent_uncertainty_units": "seed_blocks", "n_blocks": n, "parameter_range": [-2,2],
        "p_value": None, "interaction_randomization_test": None,
        "interval": {"available": available, "bounds": bounds,
            "reason": None if available else "independence_and_stability_not_declared",
            "method": "conditional_independent_block_Hoeffding", "alpha": 0.05,
            "assumptions": declared, "assumptions_attested": False,
            "scope": "Not a validated confidence bound under unaccounted shared provider drift"},
        "scope": "Scripted mechanics only" if protocol["subject_backend"]["harness"] == "scripted" else
                 "Synthetic assigned policy interaction; callback/provider origin unattested"}


def _write(path, value):
    data = _bounded(value, MAX_REPORT_BYTES).encode("utf-8")
    temporary = path.with_name(path.name+".tmp"); temporary.write_bytes(data); temporary.replace(path)


def _archive(directory, protocol, assignments):
    if directory.exists() and any(directory.iterdir()): raise ValueError("Use a fresh execution directory")
    directory.mkdir(parents=True, exist_ok=True)
    _write(directory/"protocol.json", protocol); _write(directory/"assignment.json", assignments)
    for folder, paths, expected in (("execution-code", _CODE_PATHS, protocol["execution_code_hashes"]),
            ("design-source", _DOC_PATHS, protocol["design_source_hashes"])):
        (directory/folder).mkdir()
        for name,path in paths.items():
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != expected[name]: raise ValueError("Archive source differs from frozen pin")
            (directory/folder/name).write_bytes(data)
    _write(directory/"execution-code"/"manifest.json", {"execution_code_hashes": protocol["execution_code_hashes"],
        "design_source_hashes": protocol["design_source_hashes"], "timing": "before_subject_calls",
        "runtime": "recorded_unattested"})


class RevisionRelayExecutionError(RuntimeError):
    def __init__(self, message, partial_report):
        super().__init__(message); self.partial_report = partial_report


def run_revision_relay_experiment(protocol, agent_runner=None, output_dir=None, *, backend_metadata=None, on_progress=None):
    validate_revision_relay_protocol(protocol); p = _copy(protocol, MAX_PROTOCOL_BYTES)
    backend = p["subject_backend"]; scripted = backend["harness"] == "scripted"
    if not _same(backend_metadata if backend_metadata is not None else backend, backend): raise ValueError("Backend metadata mismatch")
    if scripted != (agent_runner is None): raise ValueError("Scripted/callback substitution is forbidden")
    if backend["harness"] == "responses" and output_dir is None: raise ValueError("Responses requires pre-subject archive")
    assignments = randomize_revision_relay_runs(p); directory = Path(output_dir) if output_dir is not None else None
    if directory is not None and directory.exists() and any(directory.iterdir()):
        raise ValueError("Use a fresh execution directory; preserve earlier artifacts")
    rows = [{**u, "status": "not_started", "initial_state": None, "exogenous_identity": None,
             "turns": [], "boundaries": [], "final_state": None, "outcomes": None,
             "counts": {"subject_call_attempts":0,"applied_actions":0,"completed_opportunities":0,"model_calls":0 if scripted else None}}
            for u in assignments]
    report = {"api_version": API_VERSION, "study_kind": STUDY_KIND, "protocol":p,
        "protocol_hash": p["protocol_hash"], "status":"running", "started_at":_now(), "finished_at":None,
        "assignments":assignments, "runs":rows, "pair_checks":[], "analysis":None,
        "backend": {"mode":"scripted" if scripted else "provided_callback", "registered_spec":backend,
            "metadata":_copy(backend_metadata if backend_metadata is not None else backend),
            "python":platform.python_version(), "runtime_provenance":"recorded_unattested",
            "provider_origin":"not_attested", "fresh_sessions":"caller_assumption"},
        "model_calls":0 if scripted else None, "maximum_subject_calls":16*p["design"]["blocks"],
        "local_artifacts_before_subject_calls":directory is not None,
        "evidence_scope":"Scripted infrastructure only" if scripted else "Recorded callback actions; provider origin/consumption unattested"}
    environments = {}; current = None; phase = "archive"; archive_owned=False
    runner = agent_runner or revision_relay_scoped_policy
    def save():
        if current is not None: _bounded(current, MAX_RUN_BYTES)
        sealed = _seal(report, "report_hash")
        if not _same(store_module.clean(sealed), sealed): raise ValueError("Report sanitizer identity changed")
        if directory is not None and archive_owned: _write(directory/"report.json", sealed)
        return sealed
    try:
        if directory is not None: _archive(directory, p, assignments); archive_owned=True
        phase = "materialize"
        for row in rows:
            current = row; env = _environment(p,row); environments[row["run_id"]] = env
            row["initial_state"] = env.snapshot(); row["exogenous_identity"] = _exogenous(row["initial_state"])
        report["pair_checks"] = _pair_checks(rows)
        if not all(c["passed"] for c in report["pair_checks"]): raise ValueError("Exogenous world pairing failed")
        current = None; phase="initial_report"; save()
        for row in rows:
            current = row; env = environments[row["run_id"]]; row["status"] = "running"
            for index,(role,boundary) in enumerate(world.SCHEDULE):
                phase = "request"; _guard(); request = _request(env)
                if request["agent_id"] != role: raise ValueError("Scheduled role mismatch")
                entry = {"decision_index": index, "ordinal_boundary":boundary, "agent_id":role,
                    "request":request, "request_hash":_hash(request), "construction_status":"complete",
                    "invocation_status":"not_attempted", "action_applied":False, "attempted_action":None,
                    "action_retention":None}
                row["boundaries"].append(entry); row["counts"] = _counts(row,scripted); phase="persist"; save()
                phase="invoke"; entry["invocation_status"]="attempted_unknown"; row["counts"]=_counts(row,scripted)
                raw=runner(_copy(request,MAX_REQUEST_BYTES)); action,retention=_action(raw)
                entry.update(invocation_status="returned",action_retention=retention,attempted_action=action)
                phase="step"; result=env.step(role,action); state=env.snapshot()
                action_event=next(event for event in reversed(state["events"]) if event["type"]=="action")
                retained=action_event["action"]; entry.update(action_applied=True,attempted_action=retained)
                row["turns"].append({"decision_index":index,"ordinal_boundary":boundary,"agent_id":role,
                    "request_hash":entry["request_hash"],"action":retained,"action_retention":retention,
                    "tool_result":result,"state_hash":_hash(state)})
                row["counts"]=_counts(row,scripted)
                if env.terminal:
                    phase="oracle"; row["final_state"]=env.snapshot(); row["outcomes"]=env.evaluate()
                    row["status"]="complete"
                phase="persist"; save()
            phase="oracle"; row["final_state"]=env.snapshot(); row["outcomes"]=env.evaluate()
            if not env.terminal: raise ValueError("Four scheduled decisions must finish the world")
            row["status"]="complete"; row["counts"]=_counts(row,scripted); phase="persist"; save()
            phase="progress"
            if on_progress is not None: on_progress({"completed_teams":sum(r["status"]=="complete" for r in rows),"assigned_teams":len(rows)})
        current=None; phase="analysis"; report["analysis"]=analyze_revision_relay_runs(rows,p)
        report.update(status="complete",finished_at=_now()); phase="final_report"; return save()
    except Exception as error:
        if current is not None and current["status"]!="complete":
            current["status"]="incomplete"
            env=environments.get(current["run_id"])
            current["final_state"]=env.snapshot() if env is not None else None
            current["counts"]=_counts(current,scripted)
        report.update(status="incomplete",analysis=None,finished_at=_now(),
            failure={"phase":phase,"run_id":current["run_id"] if current is not None else None,"error_type":type(error).__name__})
        partial=_seal(report,"report_hash")
        try: save()
        except Exception: pass  # Retain exception snapshot even when persistence itself failed.
        raise RevisionRelayExecutionError("Revision-relay execution incomplete: "+phase,partial) from error


def _read_binary(path, limit):
    with path.open("rb") as stream: data=stream.read(limit+1)
    if len(data)>limit: raise ValueError("Artifact input byte limit exceeded")
    return data


def _read_json(path, limit):
    data=_read_binary(path,limit)
    def pairs(values):
        result={}
        for key,value in values:
            if key in result: raise ValueError("Duplicate artifact JSON key")
            result[key]=value
        return result
    def nonfinite(value): raise ValueError("Nonfinite artifact JSON")
    return json.loads(data.decode("utf-8"),object_pairs_hook=pairs,parse_constant=nonfinite),hashlib.sha256(data).hexdigest()


def _archive_checks(directory, p, assignments, report):
    good=True
    for name,expected in (("protocol.json",p),("assignment.json",assignments)):
        path=directory/name
        if not path.is_file() or path.stat().st_size>MAX_REPORT_BYTES: return False
        value,_=_read_json(path,MAX_PROTOCOL_BYTES if name=="protocol.json" else MAX_REPORT_BYTES)
        good &= _same(value,expected)
    expected_manifest={"execution_code_hashes":p["execution_code_hashes"],"design_source_hashes":p["design_source_hashes"],
        "timing":"before_subject_calls","runtime":"recorded_unattested"}
    path=directory/"execution-code"/"manifest.json"
    if not path.is_file() or path.stat().st_size>MAX_PROTOCOL_BYTES: return False
    value,_=_read_json(path,MAX_PROTOCOL_BYTES);good &= _same(value,expected_manifest)
    for folder,pins in (("execution-code",p["execution_code_hashes"]),("design-source",p["design_source_hashes"])):
        for name,digest in pins.items():
            path=directory/folder/name
            good &= path.is_file() and hashlib.sha256(_read_binary(path,1024*1024)).hexdigest()==digest
    path=directory/"report.json"
    if not path.is_file(): return False
    archived,digest=_read_json(path,MAX_REPORT_BYTES)
    return digest if good and _same(archived,report) else False


def replay_revision_relay_report(report, *, output_dir=None):
    """Fresh local replay. Original data and code never changed; no model calls."""
    checks=[]
    try:
        _bounded(report,MAX_REPORT_BYTES); p=report["protocol"]; validate_revision_relay_protocol(p)
        expected_fields={"api_version","study_kind","protocol","protocol_hash","status","started_at","finished_at",
            "assignments","runs","pair_checks","analysis","backend","model_calls","maximum_subject_calls",
            "local_artifacts_before_subject_calls","evidence_scope","report_hash"}
        if report.get("status")=="incomplete": expected_fields.add("failure")
        if set(report)!=expected_fields: raise ValueError("Unsupported report evidence fields")
        for field in ("started_at","finished_at"):
            stamp=report[field]
            if type(stamp) is not str or len(stamp)>40 or dt.datetime.fromisoformat(stamp.replace("Z","+00:00")).utcoffset()!=dt.timedelta(0):
                raise ValueError("Execution timestamps must be recorded UTC strings")
        checks.append({"name":"current_source_and_protocol_pins","passed":True})
        assignments=randomize_revision_relay_runs(p); scripted=p["subject_backend"]["harness"]=="scripted"
        if not _same({k:v for k,v in report.items() if k!="report_hash"},
                     {k:v for k,v in _seal(report,"report_hash").items() if k!="report_hash"}) or report.get("report_hash")!=_seal(report,"report_hash")["report_hash"]:
            raise ValueError("Report hash mismatch")
        declarations={"api_version":API_VERSION,"study_kind":STUDY_KIND,"protocol_hash":p["protocol_hash"],
            "model_calls":0 if scripted else None,"maximum_subject_calls":16*p["design"]["blocks"],
            "evidence_scope":"Scripted infrastructure only" if scripted else "Recorded callback actions; provider origin/consumption unattested"}
        if any(not _same(report.get(k),v) for k,v in declarations.items()): raise ValueError("Report declarations mismatch")
        if type(report.get("local_artifacts_before_subject_calls")) is not bool: raise ValueError("Archive flag must be boolean")
        backend=report["backend"]
        if (set(backend)!={"mode","registered_spec","metadata","python","runtime_provenance","provider_origin","fresh_sessions"}
            or backend["mode"]!=("scripted" if scripted else "provided_callback")
            or not _same(backend["registered_spec"],p["subject_backend"]) or not _same(backend["metadata"],p["subject_backend"])
            or backend["runtime_provenance"]!="recorded_unattested" or backend["provider_origin"]!="not_attested"
            or backend["fresh_sessions"]!="caller_assumption" or type(backend["python"]) is not str):
            raise ValueError("Backend bindings changed")
        if not _same(report["assignments"],assignments) or len(report["runs"])!=len(assignments): raise ValueError("Assignment grid changed")
        if output_dir is not None:
            archive_digest=_archive_checks(Path(output_dir),p,assignments,report)
            if report["local_artifacts_before_subject_calls"] is not True or not archive_digest:
                raise ValueError("Execution archive mismatch")
            checks.append({"name":"source_assignment_and_report_archive","passed":True,"report_file_sha256":archive_digest})
        rows=report["runs"]; states=[r["status"] for r in rows]
        if report["status"]=="complete":
            if any(s!="complete" for s in states) or "failure" in report: raise ValueError("Completed report lacks full grid")
        elif report["status"]=="incomplete":
            if report["analysis"] is not None or "failure" not in report: raise ValueError("Incomplete report cannot estimate")
            failure=report["failure"]
            if type(failure) is not dict or set(failure)!={"phase","run_id","error_type"} or type(failure["error_type"]) is not str:
                raise ValueError("Failure shape malformed")
            phase=failure["phase"]
            if phase not in ("archive","materialize","initial_report","request","persist","invoke","step","oracle","progress","analysis","final_report"):
                raise ValueError("Unknown execution failure phase")
            prefix=0
            while prefix<len(states) and states[prefix]=="complete": prefix+=1
            if any(s not in ("not_started","incomplete") for s in states[prefix:]): raise ValueError("Invalid partial progression")
            partial=[i for i,s in enumerate(states) if s=="incomplete"]
            if len(partial)>1: raise ValueError("Too many failing units")
            if phase=="archive":
                if any(s!="not_started" for s in states) or failure["run_id"] is not None: raise ValueError("Invalid pre-subject archive failure")
            elif phase=="initial_report":
                if any(s!="not_started" for s in states) or failure["run_id"] is not None:
                    raise ValueError("Invalid initial report failure")
            elif phase=="materialize":
                if prefix or len(partial)!=1 or failure["run_id"]!=rows[partial[0]]["run_id"]:
                    raise ValueError("Invalid pre-subject materialization failure")
            elif partial:
                if partial[0]!=prefix or failure["run_id"]!=rows[prefix]["run_id"]:
                    raise ValueError("Failed unit does not precede suffix")
            elif phase in ("analysis","final_report"):
                if prefix!=len(states) or failure["run_id"] is not None: raise ValueError("Invalid final-stage failure")
            elif phase not in ("persist","progress") or not prefix or failure["run_id"]!=rows[prefix-1]["run_id"]:
                raise ValueError("Failure is not bound to a completed/partial unit")
            if phase=="archive":
                if any(r["initial_state"] is not None or r["exogenous_identity"] is not None for r in rows):
                    raise ValueError("Archive failure invents materialized worlds")
            elif phase=="materialize":
                failed_index=partial[0]
                if (any(r["initial_state"] is None for r in rows[:failed_index]) or
                    any(r["initial_state"] is not None or r["exogenous_identity"] is not None for r in rows[failed_index+1:])):
                    raise ValueError("Materialization failure changed the known initial prefix")
            elif any(r["initial_state"] is None for r in rows):
                raise ValueError("Post-materialization failure omits a registered initial world")
        else: raise ValueError("Only terminal reports can replay")
        for row,unit in zip(rows,assignments):
            _bounded(row,MAX_RUN_BYTES)
            if not _same({k:row.get(k) for k in unit},unit): raise ValueError("Run assignment changed")
            if set(row)!=set(unit)|{"status","initial_state","exogenous_identity","turns","boundaries","final_state","outcomes","counts"}:
                raise ValueError("Unsupported run evidence fields")
            env=_environment(p,unit)
            if row["initial_state"] is not None:
                if not _same(env.snapshot(),row["initial_state"]) or not _same(_exogenous(env.snapshot()),row["exogenous_identity"]):
                    raise ValueError("Initial world/exogenous projection changed")
            elif row["exogenous_identity"] is not None: raise ValueError("Unmaterialized unit has exogenous evidence")
            if (row["turns"] or row["boundaries"] or row["status"]=="complete") and row["initial_state"] is None:
                raise ValueError("Executed unit lacks initial state")
            if report["status"]=="incomplete" and report["failure"]["phase"] in ("archive","materialize"):
                if row["turns"] or row["boundaries"] or row["outcomes"] is not None:
                    raise ValueError("Pre-subject failure has execution evidence")
            if row["status"]=="not_started":
                if row["turns"] or row["boundaries"] or row["final_state"] is not None or row["outcomes"] is not None:
                    raise ValueError("Unstarted unit has execution evidence")
            if len(row["turns"])>4 or not len(row["turns"])<=len(row["boundaries"])<=min(4,len(row["turns"])+1):
                raise ValueError("Boundary/turn prefix invalid")
            for index,b in enumerate(row["boundaries"]):
                role,boundary=world.SCHEDULE[index]; request=_request(env)
                if (set(b)!={"decision_index","ordinal_boundary","agent_id","request","request_hash","construction_status",
                    "invocation_status","action_applied","attempted_action","action_retention"}
                    or not _same([b["decision_index"],b["ordinal_boundary"],b["agent_id"]],[index,boundary,role])
                    or not _same(b["request"],request) or b["request_hash"]!=_hash(request)
                    or b["construction_status"]!="complete" or type(b["action_applied"]) is not bool):
                    raise ValueError("Scoped request/construction receipt mismatch")
                if index<len(row["turns"]):
                    turn=row["turns"][index]
                    if set(turn)!={"decision_index","ordinal_boundary","agent_id","request_hash","action","action_retention","tool_result","state_hash"}:
                        raise ValueError("Unsupported turn fields")
                    if b["invocation_status"]!="returned" or b["action_applied"] is not True or not _same(b["attempted_action"],turn["action"]):
                        raise ValueError("Action invocation binding mismatch")
                    if not _same([turn["decision_index"],turn["ordinal_boundary"],turn["agent_id"]],[index,boundary,role]) or turn["request_hash"]!=b["request_hash"] or not _same(turn["action_retention"],b["action_retention"]):
                        raise ValueError("Turn boundary changed")
                    _retention(turn["action"],turn["action_retention"])
                    result=env.step(role,turn["action"])
                    if not _same(result,turn["tool_result"]) or _hash(env.snapshot())!=turn["state_hash"]:
                        raise ValueError("Action/attachment/dispatch replay mismatch")
                elif b["invocation_status"] not in ("not_attempted","attempted_unknown","returned") or b["action_applied"] is not False:
                    raise ValueError("Invalid partial invocation")
                elif b["invocation_status"]=="returned":
                    _retention(b["attempted_action"],b["action_retention"])
                elif b["attempted_action"] is not None or b["action_retention"] is not None:
                    raise ValueError("Unknown/unattempted invocation invents an output")
            if row["status"]=="complete":
                if len(row["turns"])!=4 or not env.terminal or not _same(row["final_state"],env.snapshot()) or not _same(row["outcomes"],env.evaluate()):
                    raise ValueError("Final oracle/state mismatch")
            elif row["outcomes"] is not None or (row["final_state"] is not None and not _same(row["final_state"],env.snapshot())):
                raise ValueError("Partial world/oracle invented")
            if not _same(row["counts"],_counts(row,scripted)): raise ValueError("Execution counts changed")
            checks.append({"name":"ordinal_request_action_oracle_replay","run_id":unit["run_id"],"passed":True})
        expected_pairs=[] if report["status"]=="incomplete" and report["failure"]["phase"] in ("archive","materialize") else _pair_checks(rows)
        if not _same(report["pair_checks"],expected_pairs): raise ValueError("Recorded pairing checks changed")
        if report["status"]=="complete":
            if not _same(report["analysis"],analyze_revision_relay_runs(rows,p)):
                raise ValueError("Pairing/interaction analysis changed")
        complete=report["status"]=="complete"
        checks.append({"name":"complete_grid_and_analysis" if complete else "partial_trace_consistent","passed":True})
        return {"passed":complete,"complete_execution":complete,"partial_trace_consistent":not complete,
            "quantitative_available":complete,"checks":checks,"model_calls":0,"report_hash":report["report_hash"],
            "scope":"Local source-bound requests/actions/oracle only; no provider consumption, replication or historical mechanism"}
    except Exception as error:
        checks.append({"name":"fresh_replay","passed":False,"error_type":type(error).__name__,"reason":str(error)[:200]})
        return {"passed":False,"checks":checks,"model_calls":0,"scope":"Quantitative authentication unavailable"}


_LOADED_CODE = revision_relay_code_hashes()
