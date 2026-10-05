"""Finite timed-resource facts: exact pins, independent gates and no prose proof.

This pure extractor never opens a database, invokes subjects or rewrites studies.
Caller replay authorization is separate from the report and does not replace
local frozen action/oracle replay or registered numerical recomputation.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from statistics import mean

from .claim_audit import (audit_claims, claims_schema_for_packet, make_claim, select_fact_packet)
from .store import fingerprint
from .resource_environment import fingerprint as execution_fingerprint
from .timed_resource_experiments import (CONTEXTS, STUDY_KIND, analyze_timed_resource_runs,
    randomize_timed_resource_runs, replay_timed_resource_report, validate_timed_resource_protocol)

VERSION = "1.0"
PRIMARY_PAIR = "comparison/active/neutral/outcome/task_completion_fraction"
PRIMARY_INTERVAL = "interval/active_vs_neutral/task_completion_fraction"
PRIMARY_ANALYSIS = "analysis/primary"
LIMITATIONS = [
    "Only finite typed facts are checked; attached prose, historical mechanisms and generalized causal stories remain unverified.",
    "Whole swarms are randomized units; independent seed blocks, not agents/tasks/turns or the two paired swarms, determine uncertainty.",
    "A paired timing-and-content policy ITT includes every completed assigned swarm, including never delivered; conditioning on receipt is not a causal comparison.",
    "Receipts attest constructed requests, not provider invocation, consumption, semantic adoption, latent beliefs or identified mediation.",
    "Exclusive computer access, abstract tasks and action costs are invented analogue assumptions; historical global exclusivity is unestablished.",
    "Matching initial schedules and releases does not match realized access, action-dependent stopping, clock time or work quality.",
    "Caller authorization and replay do not establish immutable model weights, absent cross-run memory or historical fidelity.",
    "N=2 independent seed blocks has minimum exact two-sided p=0.5 and wide bounded uncertainty. Zero contrast or collapsed bootstrap does not establish equivalence.",
    "The randomization test addresses a sharp no-effect policy null, not an exact heterogeneous weak-average null; larger designs use registered approximate Monte Carlo tests.",
    "Incomplete reports expose retained assignment/status metadata only, never outcome, receipt-process or estimation quantities.",
]


def _copy(value):
    try:
        return json.loads(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False))
    except (TypeError,ValueError,OverflowError,RecursionError) as exc:
        raise ValueError("Timed resource facts require finite JSON") from exc


def _same(left,right):
    return execution_fingerprint(_copy(left)) == execution_fingerprint(_copy(right))


def _digest(value):
    return isinstance(value,str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _pin(report,report_id,source_ref,source_object):
    if source_ref is None and source_object is None: return None
    if (not isinstance(source_ref,dict) or set(source_ref) != {"id","version","hash"}
            or not isinstance(source_ref["id"],str) or not source_ref["id"] or type(source_ref["version"]) is not int
            or source_ref["version"] < 1 or not _digest(source_ref["hash"])):
        raise ValueError("Use an exact positive-version timed result source pin")
    if (not isinstance(source_object,dict) or source_object.get("kind") != "timed_resource_experiment"
            or not _same({k:source_object.get(k) for k in source_ref},source_ref)):
        raise ValueError("Source object kind/version/identity differs from its pin")
    payload = source_object.get("payload")
    if not isinstance(payload,dict) or fingerprint(payload) != source_ref["hash"]:
        raise ValueError("Pinned timed result payload hash differs")
    if report_id is not None and report_id != source_ref["id"]: raise ValueError("Report identity differs from source pin")
    core = {k:v for k,v in report.items() if k != "report_hash"}
    if not set(core) <= set(payload) or not _same(core,{k:payload[k] for k in core}):
        raise ValueError("Pinned object differs from the canonical execution report")
    if payload.get("canonical_execution_report_hash") != report.get("report_hash"):
        raise ValueError("Canonical execution hash differs from pinned result")
    if payload.get("registered_hash") != fingerprint(report.get("protocol")):
        raise ValueError("Pinned registered protocol hash differs")
    backend = report.get("protocol",{}).get("subject_backend") if isinstance(report.get("protocol"),dict) else None
    if not isinstance(backend,dict) or not isinstance(backend.get("model"),str) or not isinstance(backend.get("harness"),str):
        raise ValueError("Pinned report has no typed backend registration")
    for key,value in (("model",backend["model"]),("agent_mode","live" if backend["harness"] == "responses" else "offline_simulation")):
        if key in payload and not _same(payload[key],value): raise ValueError("Result wrapper backend declaration contradicts the protocol")
    if "protocol_ref" in payload:
        ref = payload["protocol_ref"]
        if (not isinstance(ref,dict) or set(ref) != {"id","version","hash"} or ref["id"] != payload.get("protocol_id")
                or type(ref["version"]) is not int or ref["version"] < 1 or not _digest(ref["hash"])):
            raise ValueError("Malformed pinned registration reference")
    return copy.deepcopy(source_ref)


def _external_authorization(report,source_pin,replay_check):
    if replay_check is None: return {"passed":False,"reason":"separate_offline_replay_authorization_missing"}
    if not callable(replay_check): raise ValueError("Replay authorization must be a trusted offline callable, not a verdict object")
    try:
        verdict = _copy(replay_check(copy.deepcopy(report)))
    except Exception as exc:
        return {"passed":False,"reason":"external_replay_authorization_failed","error_type":type(exc).__name__}
    if not isinstance(verdict,dict): return {"passed":False,"reason":"external_verdict_not_structured"}
    exact_report = (verdict.get("report_hash") == report.get("report_hash") and
                    verdict.get("protocol_hash") == report.get("protocol_hash") and _digest(report.get("report_hash")))
    exact_pin = source_pin is not None and _same(verdict.get("result_ref"),source_pin)
    passed = (verdict.get("passed") is True and type(verdict.get("model_calls")) is int and verdict["model_calls"] == 0
              and (exact_report or exact_pin))
    return {"passed":passed,"reason":"bound_external_offline_verdict" if passed else "external_verdict_not_passed_or_bound",
        "binding":"canonical_report" if exact_report else "exact_result_pin" if exact_pin else "none"}


def build_timed_resource_fact_ledger(report, *, report_id=None, source_ref=None, source_object=None, replay_check=None):
    """Extract finite facts from a canonical report, never report-embedded audits.

    replay_check receives an exact copied report and returns a zero-call verdict
    with passed=True and either report_hash+protocol_hash or a matching result_ref.
    It must be a trusted host-owned offline function. No callable is supplied by
    a model or taken from report prose. Local replay remains a separate gate.
    """
    report = _copy(report)
    if (not isinstance(report,dict) or report.get("study_kind") != STUDY_KIND or not isinstance(report.get("runs"),list)
            or not all(isinstance(r,dict) for r in report["runs"])):
        raise ValueError("Use a timed-resource canonical execution report")
    if report.get("status") not in ("complete","incomplete_infrastructure_failure","incomplete_analysis_failure"):
        raise ValueError("Use a typed terminal timed-study status")
    if replay_check is not None and not callable(replay_check):
        raise ValueError("Replay authorization must be a trusted offline callable")
    ids = [r.get("run_id") for r in report["runs"]]
    if any(not isinstance(i,str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("Run identities must be present and unique")
    source_pin = _pin(report,report_id,source_ref,_copy(source_object) if source_object is not None else None)
    source_fingerprint = fingerprint(report); facts = {}; checks = []; issues = []
    def add(identity,kind,value,scope,definition,*,basis,paths=None,value_unit="recorded_metric_units",metric=None,
            interpretation="recorded_metadata",bounds=None):
        if type(value) not in (str,bool,int,float) or type(value) in (int,float) and not math.isfinite(value):
            raise ValueError("Finite facts require scalar non-null typed values")
        if bounds is not None and (type(value) not in (int,float) or not bounds["minimum"] <= value <= bounds["maximum"]):
            raise ValueError("Fact lies outside its operational bounds")
        facts[identity] = {"id":identity,"kind":kind,"value":value,"scope":scope,"definition":definition,"basis":basis,
            "source_paths":paths or [],"metric":metric,"unit":"whole_swarm_run","value_unit":value_unit,"validity":"usable",
            "value_type":"boolean" if type(value) is bool else "integer" if type(value) is int else "number" if type(value) is float else "string",
            "bounds":bounds,"interpretation":interpretation,"source_fingerprint":source_fingerprint,"rendered_fact":f"{definition}: {value}"}
    add("completion/status","completion",report["status"],"recorded_execution","Recorded timed study status; execution validity is checked separately",basis="recorded_metadata",paths=["status"])
    add("completion/source_pin_checked","completion",source_pin is not None,"recorded_execution","Exact read-only result version and payload hash checked",basis="exact_source_pin")
    if source_pin:
        for key in ("id","version","hash"):
            add("source_pin/"+key,"comparison_identity",source_pin[key],"recorded_execution","Pinned timed result "+key,basis="exact_source_pin")
    try:
        validate_timed_resource_protocol(report.get("protocol")); p = report["protocol"]
        checks.append({"name":"frozen_protocol_and_current_sources","passed":True})
    except (KeyError,TypeError,ValueError,AttributeError) as exc:
        p = None; checks.append({"name":"frozen_protocol_and_current_sources","passed":False})
        issues.append({"type":"frozen_protocol_or_sources_invalid","error_type":type(exc).__name__})
    local = {"passed":False,"partial_trace_consistent":False,"checks":[]}
    if p:
        local = replay_timed_resource_report(copy.deepcopy(report)); checks.extend(local.get("checks",[]))
        checks.append({"name":"local_complete_replay","passed":local.get("passed") is True})
        expected = randomize_timed_resource_runs(p)
        assignment_exact = _same(report.get("assignments"),expected) and len(report["runs"]) == len(expected)
        assignment_exact = assignment_exact and all(_same({k:r.get(k) for k in u},u) for r,u in zip(report["runs"],expected))
        add("completion/all_assigned_units_present","completion",assignment_exact,"recorded_execution","Entire frozen assignment grid is retained; this alone does not verify outcomes",basis="exact_assignment_identity",paths=["assignments","runs"])
        if assignment_exact:
            add("trial_count/assigned","trial_count",len(expected),"recorded_design","Assigned whole swarms; paired swarms are not independent uncertainty samples",basis="validated_registered_assignments",value_unit="whole_swarms",interpretation="registered_design")
            add("trial_count/seed_blocks/assigned","trial_count",p["design"]["independent_seed_blocks"],"recorded_design","Assigned independent seed blocks",basis="validated_registered_assignments",value_unit="seed_blocks",interpretation="registered_design")
        for key in ("unit","primary_outcome","operational_definition","independent_uncertainty_units"):
            add("comparison_identity/"+key,"comparison_identity",p["estimand"][key],"recorded_design","Registered timed study "+key,basis="validated_frozen_protocol",interpretation="registered_design")
        for key in ("treatment","control"):
            add("comparison_identity/primary/"+key,"comparison_identity",p["estimand"][key],"recorded_design","Registered primary "+key,basis="validated_frozen_protocol",interpretation="registered_design")
        for key in ("kind","recipient"):
            add("comparison_identity/trigger/"+key,"comparison_identity",p["timing_spec"]["trigger"][key],"recorded_design","Fixed arm-blind trigger "+key,basis="validated_frozen_protocol",interpretation="registered_design")
        add("comparison_identity/trigger/hash","comparison_identity",p["trigger_hash"],"recorded_design","Same declared trigger hash in both arms; note assignment is outside the pure evaluator",basis="validated_frozen_protocol",value_unit="sha256",interpretation="registered_design")
        resolution = p["pre_execution_test_resolution"]
        for key in ("minimum_two_sided_p","exact_minimum_fraction"):
            add(PRIMARY_ANALYSIS+"/test_resolution/"+key,"analysis_value",resolution[key],"recorded_design","Registered exact block-swap test resolution "+key+"; not a power calculation",basis="validated_frozen_protocol",interpretation="registered_design")
        add(PRIMARY_ANALYSIS+"/test_resolution/can_attain_p_below_0.05","analysis_value",resolution["minimum_two_sided_p"] < .05,"recorded_design","Registered exact design can theoretically attain p below 0.05; not observed rejection or power",basis="validated_frozen_protocol",interpretation="registered_design")
        for key in ("model","harness"):
            add("backend/"+key,"backend",p["subject_backend"][key],"recorded_design","Registered backend "+key+"; no independent provider/weight attestation",basis="validated_frozen_protocol",interpretation="registered_design")
        if local.get("partial_trace_consistent") is True:
            for status in ("complete","incomplete","not_started"):
                add("execution_units/status/"+status,"trial_count",sum(r["status"] == status for r in report["runs"]),"recorded_execution","Retained unit status "+status+"; not an outcome score",basis="validated_local_trace_statuses",value_unit="whole_swarms",bounds={"minimum":0,"maximum":len(expected)})
    authorization = _external_authorization(report,source_pin,replay_check)
    checks.append({"name":"separate_bound_offline_replay_authorization","passed":authorization["passed"]})
    recomputed = None
    if p and report.get("status") == "complete" and local.get("passed") is True:
        try:
            recomputed = analyze_timed_resource_runs(report["runs"],p)
            checks.append({"name":"exact_registered_numerical_recomputation","passed":_same(recomputed,report.get("analysis"))})
        except (KeyError,TypeError,ValueError,RuntimeError,AttributeError) as exc:
            checks.append({"name":"exact_registered_numerical_recomputation","passed":False})
            issues.append({"type":"numerical_recomputation_failed","error_type":type(exc).__name__})
    verified = bool(p and recomputed and report.get("status") == "complete" and local.get("passed") is True
                    and authorization["passed"] is True and all(c["passed"] is True for c in checks))
    if report.get("status") != "complete": issues.append({"type":"incomplete_timed_report","status":report.get("status")})
    elif not verified:
        issues.append({"type":"complete_timed_report_not_authorized","failed_checks":[c["name"] for c in checks if c["passed"] is not True]})
    add("replay/recorded_actions/pass","replay",verified,"recorded_execution","All complete source/action/oracle/numerical gates and separate bound caller authorization passed",basis="independent_finite_fact_gates")
    add("replay/external_authorization/pass","replay",authorization["passed"],"recorded_execution","Separate host-supplied zero-call verdict passed and was bound to this source",basis="separate_offline_caller_authorization")
    if verified: _numeric_facts(add,report,recomputed)
    ledger = {"registry":"timed_resource_finite_facts","version":VERSION,"report_id":report_id or (source_pin["id"] if source_pin else None),
        "source_fingerprint":source_fingerprint,"canonical_execution_report_hash":report.get("report_hash"),"source_ref":source_pin,
        "facts":facts,"quantitative_facts_available":verified,"issues":issues,"verification_checks":checks,
        "external_authorization":authorization,"local_partial_trace_consistent":local.get("partial_trace_consistent") is True,
        "model_calls":0,"prose_verification_available":False,"limitations":list(LIMITATIONS),
        "extractor_source_hash":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    ledger["ledger_hash"] = fingerprint(ledger)
    return ledger


def _numeric_facts(add,report,recomputed):
    n = report["protocol"]["design"]["independent_seed_blocks"]
    add("trial_count/completed","trial_count",len(report["runs"]),"observed_sample","Completed assigned whole swarms; not independent seed blocks",basis="validated_all_assigned_rows",value_unit="whole_swarms")
    add("trial_count/seed_blocks/completed","trial_count",n,"observed_sample","Completed independent paired seed blocks",basis="validated_all_assigned_rows",value_unit="seed_blocks")
    rates = {"task_completion_fraction":"Executed fraction of eight assigned tasks", "independent_completion_fraction":"Executed fraction of four independent tasks",
        "computer_completion_fraction":"Executed fraction of four computer-gated tasks","focal_completion_fraction":"Executed fraction of agent-0's two tasks"}
    for context in CONTEXTS:
        group = [r for r in report["runs"] if r["context"] == context]
        add("trial_count/group/"+context,"trial_count",len(group),"observed_sample","Completed assigned swarms in "+context,basis="validated_all_assigned_rows",value_unit="whole_swarms")
        for metric,definition in rates.items():
            add(f"arm_metric/{context}/outcome/{metric}/mean","arm_metric",mean(r["outcomes"][metric] for r in group),"observed_sample",context+": mean "+definition+"; code oracle, not completion claims",basis="replayed_synthetic_code_oracle",metric=metric,value_unit="completion_fraction",bounds={"minimum":0,"maximum":1},interpretation="synthetic_oracle_outcome")
        tasks = sum(sum(sum(v.values()) for v in r["outcomes"]["per_agent_completed"].values()) for r in group)
        for label,value in (("tasks_assigned",8*len(group)),("executed_tasks_completed",tasks)):
            add(f"arm_metric/{context}/task_inventory/{label}","arm_metric",value,"observed_sample",context+": "+label+"; tasks are outcomes, not independent trials",basis="replayed_synthetic_code_oracle",value_unit="declared_tasks",bounds={"minimum":0,"maximum":8*len(group)},interpretation="synthetic_oracle_outcome")
        values = [r["outcomes"]["task_completion_fraction"] for r in group]
        for label,value in (("all_at_floor",all(v == 0 for v in values)),("all_at_ceiling",all(v == 1 for v in values))):
            add(f"arm_metric/{context}/outcome/task_completion_fraction/{label}","arm_metric",value,"observed_sample",context+": sampled outcomes "+label+"; not general capability or equivalence",basis="replayed_synthetic_code_oracle",interpretation="synthetic_oracle_outcome")
        process = {"eligible_preparations":sum(r["counts"]["eligible_preparations"] for r in group),
            "recorded_receipts":sum(r["counts"]["recorded_receipts"] for r in group),
            "never_delivered_completed_swarms":sum(r["counts"]["recorded_receipts"] == 0 for r in group),
            "eligibility_unresolved_completed_swarms":sum(r["timing_report"]["policy_itt"]["eligibility_status"] == "eligibility_unresolved" for r in group),
            "execution_status/completed":sum(r["timing_report"]["execution_status"] == "completed" for r in group)}
        for label,value in process.items():
            add(f"process/{context}/{label}","arm_metric",value,"observed_sample",context+": "+label+"; post-treatment recorded process, not provider consumption, belief or mediation",basis="replayed_controller_and_world_status",value_unit="whole_swarms",bounds={"minimum":0,"maximum":len(group)},interpretation="post_treatment_description")
    effect = recomputed["primary_effect"]; difference = effect["difference"]
    for label,kind,value,unit in (("mean_difference","comparison_difference",difference,"completion_fraction"),
            ("mean_difference_percentage_points","comparison_difference",100*difference,"percentage_points"),
            ("mean_direction","comparison_direction","equal" if difference == 0 else "higher" if difference > 0 else "lower","direction")):
        add(PRIMARY_PAIR+"/"+label,kind,value,"observed_sample","Whole-policy ITT paired active-minus-neutral "+label+"; includes never delivered, equal does not establish equivalence",basis="registered_paired_policy_itt_recomputation",value_unit=unit,bounds={"minimum":-100,"maximum":100} if unit == "percentage_points" else {"minimum":-1,"maximum":1} if unit == "completion_fraction" else None,interpretation="policy_itt")
    interval = effect["ci95"]
    for label,value in zip(("lower","upper"),interval):
        add(PRIMARY_INTERVAL+"/"+label,"interval_bound",value,"recorded_analysis","Independent-block bounded 95% policy-ITT interval "+label,basis="registered_paired_numerical_recomputation",value_unit="completion_fraction",bounds={"minimum":-1,"maximum":1},interpretation="policy_itt")
    add(PRIMARY_INTERVAL+"/excludes_zero","interval_zero",interval[0] > 0 or interval[1] < 0,"recorded_analysis","Bounded policy-ITT interval excludes zero; inclusion does not establish no effect",basis="registered_paired_numerical_recomputation",interpretation="policy_itt")
    add(PRIMARY_ANALYSIS+"/p_two_sided","analysis_value",effect["p_two_sided"],"recorded_analysis","Registered sharp-null block label-swap p; no historical or mediated mechanism claim",basis="registered_paired_numerical_recomputation",value_unit="probability",bounds={"minimum":0,"maximum":1},interpretation="policy_itt")
    for key,value in effect["randomization_test"].items():
        add(PRIMARY_ANALYSIS+"/randomization_test/"+key,"analysis_value",value,"recorded_analysis","Registered block label-swap "+key,basis="registered_paired_numerical_recomputation",interpretation="policy_itt")
    bootstrap = effect["paired_bootstrap_ci95_sensitivity"]
    for label,value in zip(("lower","upper"),bootstrap):
        add("interval/paired_bootstrap_sensitivity/"+label,"interval_bound",value,"recorded_analysis","Paired bootstrap sensitivity "+label+"; can collapse, not the conservative primary interval",basis="registered_paired_numerical_recomputation",bounds={"minimum":-1,"maximum":1},interpretation="policy_itt")
    add(PRIMARY_ANALYSIS+"/bootstrap_degenerate","analysis_value",bootstrap[0] == bootstrap[1],"recorded_analysis","Paired bootstrap collapsed; does not establish certainty, equivalence or immunity",basis="registered_paired_numerical_recomputation",interpretation="policy_itt")
    add("paired_world/all_initial_states_identical","completion",True,"recorded_execution","Both reset worlds in each block have identical initial bytes; no shared mutable state",basis="full_frozen_world_replay",interpretation="paired_design_check")
    add("paired_world/all_fixed_schedules_identical","completion",True,"recorded_execution","Each pair has the same full precomputed exogenous scheduler/release path; realized access may differ",basis="full_frozen_world_replay",interpretation="paired_design_check")
    for block in sorted(set(r["block_id"] for r in report["runs"])):
        identity = next(r["initial_world_identity"] for r in report["runs"] if r["block_id"] == block)
        for key in ("snapshot_hash","schedule_hash"):
            add(f"paired_world/{block}/{key}","comparison_identity",identity[key],"recorded_execution","Replayed shared initial "+key+" for "+block,basis="full_frozen_world_replay",value_unit="sha256",interpretation="paired_design_check")


def default_timed_resource_fact_ids(ledger, *, max_facts=28):
    if type(max_facts) is not int or not 1 <= max_facts <= 100: raise ValueError("Use a fact cap from 1 to 100")
    ordered = ["completion/status","completion/source_pin_checked","replay/recorded_actions/pass","replay/external_authorization/pass",
        "trial_count/assigned","trial_count/completed","trial_count/seed_blocks/completed","comparison_identity/unit",
        "comparison_identity/independent_uncertainty_units","comparison_identity/primary/treatment","comparison_identity/primary/control",
        "arm_metric/active/outcome/task_completion_fraction/mean","arm_metric/neutral/outcome/task_completion_fraction/mean",
        PRIMARY_PAIR+"/mean_direction",PRIMARY_PAIR+"/mean_difference_percentage_points",PRIMARY_INTERVAL+"/lower",PRIMARY_INTERVAL+"/upper",
        PRIMARY_INTERVAL+"/excludes_zero",PRIMARY_ANALYSIS+"/p_two_sided",PRIMARY_ANALYSIS+"/test_resolution/minimum_two_sided_p",
        PRIMARY_ANALYSIS+"/bootstrap_degenerate","process/active/recorded_receipts","process/neutral/recorded_receipts",
        "process/active/never_delivered_completed_swarms","process/neutral/never_delivered_completed_swarms",
        "paired_world/all_fixed_schedules_identical","backend/model","backend/harness"]
    return [k for k in ordered if k in ledger["facts"]][:max_facts]


def audit_timed_resource_claims(ledger, claims):
    """Finite checker with exact JSON value types; prose stays unverified."""
    body = _copy(ledger); signature = body.pop("ledger_hash",None)
    if body.get("registry") != "timed_resource_finite_facts" or signature != fingerprint(body):
        raise ValueError("Use an unchanged timed resource fact ledger")
    result = audit_claims(ledger,claims)
    for row,claim in zip(result["claims"],claims):
        if row["status"] == "supported" and not _same(claim["expected"],ledger["facts"][claim["fact_id"]]["value"]):
            row.update(status="mismatch",reason="Expected canonical JSON type/value contradicts the finite fact",approved_fact_text=None)
    result["supported_fact_ids"] = [r["fact_id"] for r in result["claims"] if r["status"] == "supported"]
    result["all_executable_claims_supported"] = not ledger["issues"] and all(r["status"] in ("supported","unverified") for r in result["claims"])
    result["review_required"] = result["unverified_prose_present"] or not result["all_executable_claims_supported"]
    return result
