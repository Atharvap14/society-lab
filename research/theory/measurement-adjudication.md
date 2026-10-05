# Reviewing a measurement against retained messages

Production interface guide, 4 October 2026. This workflow freezes a binary operational question, samples retained records, and compares an optional cheap identifier with declared labels. It makes **zero provider calls**, including when the dashboard's live-agent switch is enabled. Creating samples and saving judgments write local registry versions; reading packets does not launch agents. It never promotes a behavior or theory.

## Freeze the construct and sampling frame

Supply the exact dataset `{id, version, hash}` plus a question, positive/negative definitions and exclusions. A free binary construct uses `detector_id: null`; no prediction is then available. Alternatively, choose an existing named regex. Its definition remains separate from the authored construct: equivalence is not established. The dashboard offers blocker, completion-report and specified-correction rules. A changed construct requires a new sample.

The frame is **all retained messages in that exact dataset**, including its declared speaker categories, not only agent authors and not the complete Village export. Maximum N is 10,000; k is 1–32 and cannot exceed N. Canonical sorted message IDs are sampled without replacement using the registered integer seed (0 through 2^53−1). The sample records Python version, membership hash, draw order and inclusion probability k/N. Repeated creation with the same inputs reproduces the draw, not an independent sample.

Each sampled message retains original coordinates, normalized-record and content hashes. Excerpts are at most 2,000 Unicode characters, with full length/hash and explicit truncation. Context contains 0–2 same-room neighbors per side, ordered by timestamp then ID. It is bounded context, not a complete episode or evidence of consumption; timestamp ties do not establish causal order. Registry bodies and source bindings are checked, but raw export files are not reread.

## CLI example

Run from the project directory. Every `EXACT_*` identifier and zero hash below is a **placeholder**; replace it with the returned object's exact pin. These example plans are not production evidence. UTF-8 plan files are bounded to 16 KiB; duplicate keys and nonfinite JSON are rejected.

Save as `review-sample-plan.json`:

```json
{
  "dataset_ref": {
    "id": "dataset-EXACT_ID",
    "version": 1,
    "hash": "0000000000000000000000000000000000000000000000000000000000000000"
  },
  "question": "Does the speaker explicitly report a dependency preventing current work?",
  "positive_definition": "An explicit report of an obstruction or dependency blocking current work.",
  "negative_definition": "Future plans without a stated obstruction or dependency.",
  "exclusions": ["Quotation alone does not establish the speaker's own blocker."],
  "sample_size": 16,
  "seed": 42,
  "detector_id": "blocker_report",
  "context_neighbors": 1
}
```

```powershell
python -m swarm_lab.cli create-measurement-sample --plan review-sample-plan.json
python -m swarm_lab.cli show-measurement-review measurement_sample-EXACT_ID --sample-version 1 --review-id measurement_review-EXACT_ID --review-version 1
```

The creation response supplies sample metadata; its saved payload supplies `review_id`. Read exact objects with `GET /api/object/<id>?version=<version>`. The initial review is empty, version 1. Explicit CLI prediction display adds **`--show-predictions`** to the show command; without it, item predictions are omitted. CLI JSON still includes aggregate comparison metrics, so hiding individual predictions is not blinding.

Save a declaration plan as `review-judgment-plan.json`:

```json
{
  "sample_ref": {
    "id": "measurement_sample-EXACT_ID",
    "version": 1,
    "hash": "0000000000000000000000000000000000000000000000000000000000000000"
  },
  "message_id": "EXACT_SAMPLED_MESSAGE_ID",
  "label": "uncertain",
  "reason": "The statement may report a dependency, but attribution is ambiguous.",
  "reviewer_id": "operator-01",
  "reviewer_mode": "manual_operator",
  "expected_review_version": 1,
  "predictions_visible": false
}
```

```powershell
python -m swarm_lab.cli record-measurement-judgment --plan review-judgment-plan.json
```

Use the new exact review version for subsequent show/save requests. Labels are `yes`, `no`, or `uncertain`; missing means no accepted declaration. Reasons are required and at most 1,000 characters. Reviewer identifiers are at most 80 characters and match `[A-Za-z0-9][A-Za-z0-9._:-]*`.

## Review history, visibility and API

Reviewer modes are `manual_operator`, `agent_assisted`, and `synthetic_fixture`. They and reviewer identities are **declared, not authenticated**. This workflow does not generate agent-assisted labels itself. The latest accepted declaration per message supplies the reference; earlier judgments, disagreements and declared prediction visibility remain inspectable. There is no consensus or majority-vote truth. A review permits at most 256 judgment events.

Saving uses compare-and-swap against the expected review version and authenticated stored hash. A concurrent update rejects a stale save. Reload and inspect it before deciding whether to submit another declaration; do not silently overwrite or automatically retry an acknowledgment of unknown completion. The dashboard disables Save while its write is queued.

The exact read endpoint is:

```text
GET /api/measurement-review?sample_id=measurement_sample-EXACT_ID&sample_version=1&review_id=measurement_review-EXACT_ID&review_version=1&include_predictions=false
```

Use **`include_predictions=true`** to include frozen item predictions. All four identity/version parameters are required, unique and canonical; versions are positive integers. The response contains `packet` and `report`, each bound to exact sample, review and dataset references. Stale/mismatched reports withhold UI metrics. The dashboard's explicit Show command reveals item predictions and comparison metrics; initial hiding is only a UI choice. Prior access and independent blinding are unverified, even when `predictions_visible` is false.

Queued writes use `POST /api/jobs`, the current local `X-Lab-Token`, and `{"action": "…", "args": {…}}`. Action names are **`create_measurement_sample`** and **`record_measurement_judgment`**; arguments match the plans above. A 202/job ID acknowledges queuing, not completion. Inspect the terminal job and its result identity.

## Read the comparison conservatively

When saved, loaded and current detector pins agree, the core cheaply recomputes the selected named regex on original full retained registry rows and checks complete frozen predictions. Status becomes `matches_current_pinned_regex`. This checks operator consistency, not raw-byte authentication, historical execution or semantic correctness. A supported historical sample under code drift retains predictions with `historical_saved_predictions_unverified`; no replacement detector or archived code is executed. Unsupported contracts fail closed. With no instrument, status is `not_applicable_no_instrument`. `historical_execution_attested` and `calibration_established` remain false.

The comparison denominator includes only **latest known yes/no labels with available predictions**. Missing, uncertain and unavailable cases are separately counted, never negative labels. Agreement is (TP+TN)/denominator against the declared reference. Precision and recall likewise use that reference; zero denominators produce null/Unknown, not zero performance.

Seeded sampling addresses selection within the retained frame only. Retention, construct choice, incomplete/uncertain labeling, predictor visibility, repeated reviewers, shared context and nonrandom label availability can bias the compared subset. A message label does not establish episode prevalence, actual waiting, completed work, delivery or belief. These reports establish neither authenticated human truth, population accuracy, calibration, causal effects nor novelty.

Implementation: [core](../../swarm_lab/measurement_adjudication.py), [read workflow](../../swarm_lab/measurement_review_workflow.py), [CLI](../../swarm_lab/cli.py), [server queue/read routes](../../swarm_lab/server.py), [pure renderer](../../web/measurement-review.js), [dashboard controller](../../web/measurement-review-host.js).
