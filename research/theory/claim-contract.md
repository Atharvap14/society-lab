# Executable claim contract

This contract checks finite assertions against an exact recorded experiment. It does **not** solve natural-language entailment, validate all experimental assumptions, prove that a hosted model actually generated a response, or establish a causal mechanism. The attached prose remains unverified even when its typed fact passes.

The motivating errors are concrete. The first live evaluator said active success was 2/3, although recorded outcomes were 3/3. Its replacement contained no digits but said active had more inspection before publication than neutral. The registered any-agent inspection flag was 3/3 in both arms. A digit filter caught neither the second error nor the actor/version ambiguity.

## Data flow and API

`swarm_lab.claim_audit` supplies these provider-free functions:

```python
ledger = build_fact_ledger(report, report_id=object_id, replay_check=replay_report)
packet = select_fact_packet(ledger, fact_ids, max_facts=50)
schema = claims_schema_for_packet(packet)
# A research agent may return {"claims": [...]} using this bounded schema.
audited = audit_claims(ledger, response["claims"])
```

`report` may be the executed shared-artifact report or the provenance-diffusion factorial report. `build_fact_ledger(report, *, report_id=None, replay_check=None)` returns computed/saved facts, input fingerprint, data issues, and limits. It never calls a model, edits the report, or updates library status. A replay check is optional and must be a trusted offline callable receiving the exact report and returning an explicit verdict with `model_calls=0` and the matching completed-unit count. A supplied replay verdict dictionary is rejected. No replay fact exists when replay was not performed or could not be completed.

`select_fact_packet(ledger, fact_ids, *, max_facts=50)` requires an explicit list. The cap must be 1–100; duplicate or unavailable IDs fail. The full ledger can be large, so keep it local and give the agent only relevant facts. `claims_schema_for_packet(packet)` returns a strict finite JSON schema whose allowed fact IDs and fingerprint are restricted to that packet. `CLAIM_SCHEMA` and `CLAIMS_SCHEMA` expose the universal syntax. `validate_claim(claim)` checks this syntax; `make_claim(ledger, fact_id, expected, *, claim_id=None, statement="")` is a convenience constructor, not approval.

For the current study families, `default_fact_ids(ledger)` selects at most 24 critical facts. The shared-artifact packet prioritizes all arm denominators/correct counts, primary versus baseline directions, primary versus baseline interval exclusion when available, primary control/unit identity, recorded backend, and any-agent versus exact-publisher-version inspection. A performed replay is included when available. The network packet prioritizes cell counts/accuracy, factor identities/stratification, marginal directions, intervals, and whole-network unit. This shortlist is a bounded default, not a claim that all relevant scientific details fit in one packet; use explicit IDs for other questions.

## Supported facts and exact meanings

| Kind | Example fact ID | What the check supports |
|---|---|---|
| `trial_count` | `trial_count/completed`, `trial_count/group/placebo` | Counts completed run records once per independent team/network |
| `arm_metric` | `arm_metric/evidence_thought/outcome/success/sum` | Sum or mean of a supported recorded outcome over all runs in that arm |
| `arm_metric` | `arm_metric/baseline/trajectory/publisher_inspected_published_version/sum` | Successful inspection by the actual publisher of the exact later published version, before publication; exploratory |
| `comparison_direction` | `comparison/evidence_thought/placebo/outcome/inspected_publication/mean_direction` | Observed arm mean is `higher`, `equal`, or `lower`; actor and metric are part of the ID |
| `comparison_difference` | `comparison/evidence_thought/placebo/outcome/success/mean_difference_percentage_points` | Explicit arithmetic contrast, with conversion to percentage points named in the ID |
| `interval_zero` | `interval/evidence_thought_vs_placebo/success/excludes_zero` | Saved internally consistent interval excludes zero; touching zero means false |
| `interval_bound` | `interval/evidence_thought_vs_placebo/success/lower` | A saved finite ordered interval bound |
| `analysis_value` | `interval/evidence_thought_vs_placebo/success/p_two_sided` | Saved finite p-value, explicitly not independently recalculated by this module |
| `comparison_identity` | `comparison_identity/primary/control`, `comparison_identity/unit` | Recorded primary control and independent trial unit |
| `completion` | `completion/status`, `completion/all_assigned_units_present` | Recorded status and whether every recorded assignment has a matching completed unit |
| `backend` | `backend/mode`, `backend/model` | Recorded backend metadata; not independent provider attestation |
| `replay` | `replay/recorded_actions/pass` | A trusted offline checker actually ran on this exact input |
| `proposed_mechanism`, `free_prose` | No fact ID | Always unverified; proposed mechanisms retain proposed status |

For factorial networks, groups are explicit cells such as `ring|placebo`. Marginal factor direction uses equal cell averaging over the other assigned factor, not an unqualified pooled comparison. Network factor intervals use IDs such as `interval/factor_context/mean_accuracy/excludes_zero`. The independent unit remains the whole network, even though the outcome averages several subject verdicts.

Three inspection measures remain separate: any publisher inspection, publisher inspection of the published version, and any-agent inspection of the published version. An inspection may find a defect. It is not positive validation, evidence delivery, acknowledgement, or a hidden belief. Successful repair and final correctness also remain distinct. Actor/version values are reconstructed from permitted successful actions and tool results; narrated claims are not inspection evidence. Missing tool versions make that trajectory measure unavailable rather than false.

## Claim shape and rendering rule

Every claim contains exactly `id`, `kind`, `fact_id`, `expected`, `scope`, `statement`, and `source_fingerprint`. `expected` is a finite number, string, boolean, or null for unverified prose. Booleans cannot silently match integers. Executable claims must use the exact fact kind and scope; a sample statistic cannot be relabeled historical or generalized. Numeric comparison allows only small floating-point representation tolerance, not informal rounding or hidden unit conversion.

The source fingerprint binds claims to the full exact input report. Changing outcomes, metadata, or protocol requires a new ledger and adjudication. Record the immutable object ID/version/hash beside the audit when persisting it; a fingerprint alone does not establish where a report came from.

Audited statuses are `supported`, `mismatch`, `unavailable`, `invalid`, or `unverified`. For a supported explicit assertion, render `approved_fact_text`, which is generated from the fact definition and value. Do **not** render an attached `statement` as verified: a claim can correctly request a count of three while its sentence falsely says something about all agents being honest. This module deliberately does not decide that sentence's entailment.

`attached_prose_approved` is always false. `unverified_prose_present` and `review_required` make the limitation explicit. `all_executable_claims_supported` covers only finite facts and recorded data issues; it can be vacuously true when there are only unverified prose claims. It is not an approval gate for a natural-language evaluation. Proposed mechanisms should be stored and shown as hypotheses with falsifiers, rival explanations, and separate support scopes.

## Integrity checks and remaining limits

Duplicate run IDs are rejected. A missing arm metric is not averaged over the surviving subset. Incomplete infrastructure attempts get recorded counts/status but no arm effect or interval facts. A completed label with missing or mismatched assignments is flagged. When inspection oracle values conflict with successful-tool reconstruction, affected outcome/comparison facts are unavailable and the data issue remains visible.

Before exposing shared-artifact uncertainty facts, the ledger compares saved treatment/control means, difference, sample counts, and unit with executed run rows. Factorial uncertainty metadata is similarly compared with equal cell averages and network counts. Invalid bounds or inconsistent effects do not produce uncertainty facts. The ledger does not independently recalculate intervals, p-values, randomization validity, reset correctness, provider stationarity, measurement validity, or causal identification; use the experiment/replay/statistical audit for those checks. A numerically self-consistent interval can still use an inappropriate statistical method.

Replay validates recorded transitions and packets, not fresh subject behavior. Backend labels and stored status describe the record, not external authenticity. Results in the registered synthetic setting cannot establish the historical Village mechanism, hidden cognition, cross-task generality, or mediation merely by passing this contract. These distinctions are intentional and must survive presentation and library promotion.

## Verified regression cases

The offline tests use controlled manual fixtures for the original numeric mistake, digit-free wrong inspection direction, actor/version separation, primary control identity, uncertainty crossing/touching zero, report-version binding, missing metrics, duplicate units, conflicting oracle traces, incomplete attempts, backend metadata, and bounded packets. The same ledger was also run against the three executed reports: initial handoff, fresh-seed handoff replication, and network pilot. Each built without internal data issues; the two original evaluator claims were rejected on the actual initial report. This is a finite-contract evaluation, not a general natural-language evaluation benchmark.
