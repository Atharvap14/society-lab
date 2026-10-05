"""Bounded, authored-label measurement check; no training or Village data.

Use the isolated Laya interpreter for --backend laya. The parent interpreter can
use --backend laya-process. Backend failures persist as failures, never regex.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swarm_lab.classifiers import (BackendUnavailable, JevHTTPBackend, LayaBackend, LayaProcessBackend,
                                   LAYA_MODEL_REVISION, evaluate_measurements)
from swarm_lab.discovery import DETECTOR_DEFINITIONS, DETECTOR_VERSION, detect_behaviors
from swarm_lab.store import clean, fingerprint


FIXTURE_VERSION = "authored-observable-check-v1"
FIXTURE = [
    ("commitment-positive", "I will upload the telescope calibration report.", ["commitment"]),
    ("completion-positive", "I have uploaded the telescope calibration report.", ["completion_report"]),
    ("evidence-positive", "Please show the artifact before I rely on the completion claim.", ["evidence_request"]),
    ("blocker-positive", "I cannot proceed with the deployment because access was denied.", ["blocker_report"]),
    ("correction-positive", "I was wrong. My previous claim was incorrect.", ["correction"]),
    ("human-help-positive", "I need human approval before contacting the customer.", ["human_help_request"]),
    ("acknowledgement-positive", "Understood, thanks for the update.", ["acknowledgement"]),
    ("plan-change-positive", "Let's instead switch to the offline plan.", ["plan_change"]),
    ("commitment-tentative-negative", "I might help later, but I am not accepting this task.", []),
    ("completion-negation-negative", "The deployment is not completed and the artifact is not ready.", []),
    ("completion-quotation-negative", "Bob said 'I have completed the task'. I do not know whether his claim is true.", []),
    ("ordinary-wait-negative", "The next round starts at noon. I am reading while waiting.", []),
    ("source-description-negative", "The report includes citations on each page.", []),
    ("other-agent-suggestion-negative", "Someone else should upload the report.", []),
    ("preference-negative", "I prefer the blue color scheme.", []),
    ("open-question-negative", "What should we work on today?", []),
]


def benchmark(backend, *, limit=16, names=None):
    names = names or list(DETECTOR_DEFINITIONS)
    if set(names) - set(DETECTOR_DEFINITIONS):
        raise ValueError("Unknown predefined observable")
    definitions = {name: DETECTOR_DEFINITIONS[name] for name in names}
    if not 1 <= limit <= len(FIXTURE):
        raise ValueError(f"limit must be 1–{len(FIXTURE)}")
    gold = [{"message_id": identity, "labels": {name: name in positive for name in names}} for identity, _, positive in FIXTURE[:limit]]
    report = {"fixture_version": FIXTURE_VERSION, "gold_defined_before_inference": True, "gold_fingerprint": fingerprint(gold),
              "gold_origin": "Independently authored synthetic text and explicit labels; no model-generated labels.",
              "status": "running", "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "backend": getattr(backend, "name", "deterministic_regex"),
              "definitions": definitions, "measurements": [], "gold": gold}
    if backend is not None:
        report["backend_metadata"] = backend.metadata()
    started = time.monotonic()
    try:
        for index, (identity, text, _) in enumerate(FIXTURE[:limit]):
            message = {"id": identity, "agent_id": "synthetic_subject", "content": text, "room_id": "authored_benchmark",
                       "timestamp": f"2025-04-02T10:{index:02}:00Z", "speaker_type": "agent"}
            if backend is None:
                observed = detect_behaviors([message])[0]
                result = {"message_id": identity, "backend": "deterministic_regex", "detector_version": DETECTOR_VERSION,
                          "labels": {name: name in observed["labels"] for name in names}, "probabilities": {name: None for name in names},
                          "abstention_reasons": {}, "interpretation": "independent_regex_measurement"}
            else:
                result = backend.measure(message, definitions)
            report["measurements"].append(result)
            print(json.dumps({"message_id": identity, "labels": result["labels"], "status": result.get("status", "measured")}), flush=True)
        report["evaluation"] = evaluate_measurements(report["measurements"], gold)
        report["status"] = "complete"
    except Exception as error:
        report["status"] = "operational_failure"
        report["error"] = str(error) if isinstance(error, (BackendUnavailable, ValueError)) else type(error).__name__
        report["interpretation"] = "No model quality claim; no regex fallback. Completed partial measurements remain visible."
    report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    report["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    report["limitations"] = ["This is a small authored diagnostic, not a Village benchmark or domain calibration.", "Only source-text observables are labeled; latent states and task success are outside the contract.", "Thresholds are fixed before execution; no training, fine-tuning, or probability recalibration."]
    return clean(report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["regex", "laya", "laya-process", "jev"], default="regex")
    parser.add_argument("--limit", type=int, default=16)
    parser.add_argument("--labels", default="")
    parser.add_argument("--output", type=Path, default=ROOT / ".runtime" / "classifier-benchmark.json")
    parser.add_argument("--python", type=Path, default=ROOT / ".runtime" / "laya-venv" / "Scripts" / "python.exe")
    parser.add_argument("--cache-dir", type=Path, default=ROOT / ".runtime" / "laya-cache")
    parser.add_argument("--model-path", default=None)
    parser.add_argument("--revision", default=LAYA_MODEL_REVISION)
    parser.add_argument("--low", type=float, default=.2)
    parser.add_argument("--high", type=float, default=.8)
    parser.add_argument("--timeout", type=float, default=90)
    args = parser.parse_args()
    os.environ["HF_HOME"] = str(args.cache_dir.resolve())
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    backend = None
    try:
        options = {"low": args.low, "high": args.high}
        if args.backend == "laya":
            backend = LayaBackend(revision=args.revision, model_path=args.model_path, **options)
        elif args.backend == "laya-process":
            backend = LayaProcessBackend(args.python, cache_directory=args.cache_dir, timeout=args.timeout, revision=args.revision, model_path=args.model_path,
                                         on_status=lambda status: print(json.dumps({"backend_status": status}), flush=True), **options)
        elif args.backend == "jev":
            backend = JevHTTPBackend(**options)
        report = benchmark(backend, limit=args.limit, names=args.labels.split(",") if args.labels else None)
    except Exception as error:
        report = {"backend": args.backend, "status": "operational_failure", "error": str(error) if isinstance(error, (BackendUnavailable, ValueError)) else type(error).__name__, "fallback": "none"}
    finally:
        if hasattr(backend, "close"):
            backend.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(clean(report), indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], "backend": report["backend"], "output": str(args.output.resolve()), "elapsed_seconds": report.get("elapsed_seconds")}))
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
