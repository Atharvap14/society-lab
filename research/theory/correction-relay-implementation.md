# Correction-relay capability and evidence contract

4 October 2026. This separate capability implements the reviewed [design](correction-relay-experiment-draft.md) and [causal review](correction-relay-experiment-review.md). It extends the laboratory's available experiments without changing the four existing worlds or their saved studies. It is not yet a generic environment-authoring or research-cycle template. Scripted execution validates the machinery; a model effect requires a separately registered live execution.

## World and scientific question

Source A is an executable fixture. Subjects B and C have four fixed opportunities: B2, C3, B5, C7. A generates independent, uniform residues for original revision 1, corrected revision 2, an unrelated sham and C's private information. Records have fixed world-local IDs, canonical content hashes and checked forwarding lineage. C must explicitly commit revision 2 and its exact modular sum with the private residue. Final waiting or an invalid action scores zero; a valid `retain` commits an existing draft. An interrupted infrastructure run has an unknown outcome. No score is supplied to subjects during execution.

The four cells cross early/late availability of the correction to B with an informative/sham A-to-C bypass. Within each seed block, four fresh teams share source values, private residue and the entire exogenous schedule. Their cell execution order is randomized. Treatment intentionally changes scoped inventories and delivery content: complete initial snapshots are not identical. Exogenous pairing is a separately named, replayed projection.

For block b, the registered contrast is

`D_b = (Y_late,sham − Y_early,sham) − (Y_late,informative − Y_early,informative)`.

Each Y is binary; D lies in −2…2. The report retains every block contrast and cell mean. The estimand concerns assigned correction-availability packages. Context order, salience, draft history and direct-route content are parts of those packages. It does not identify relay mediation, a stable social role, thought insertion efficacy or a historical Village mechanism. Correct guessing can score; canonical inventory is not a reading or belief measure. Free narration is not authenticated source lineage.

The runner requires a complete assigned grid before estimating. An interrupted grid cannot substitute its successful subset or silently replace a team. Interaction p-values are unavailable. Default interval bounds are also unavailable. An explicitly declared independent-block/stable-backend assumption can enable a conditional Hoeffding bound, clipped to the known parameter range; the declaration does not verify either assumption or protect against unaccounted shared provider drift. Small pilots cannot establish equivalence.

## Interfaces

Pure, bounded API in `swarm_lab/revision_relay_experiments.py`:

```python
create_revision_relay_protocol(blocks=2, seed=173, *, subject_backend=None,
    source_refs=None, interval_assumptions=None, alpha=0.05)
run_revision_relay_experiment(protocol, agent_runner=None, output_dir=None, *,
    backend_metadata=None, on_progress=None)
replay_revision_relay_report(report, *, output_dir=None)
```

The default backend is the recipient-scoped scripted policy. A callback requires a distinct, matching backend declaration. A callback's origin is not attested as a provider. The pure API calls no registry or model on its own. Its optional output directory must be new; it archives the frozen protocol, assignment, fixed source files and design documents before subject decisions.

Host API in `swarm_lab/revision_relay_workflow.py`, also exposed through `Lab` and the loopback job queue:

```python
lab.design_revision_relay(blocks=2, seed=173, live=False,
    behavior_ref=None, interval_assumptions=None)
lab.experiment_revision_relay(protocol_id, protocol_version=1, live=False)
lab.audit_revision_relay(result_id, version=1)
```

Execution and audit require exact versions. A behavior reference, if supplied, has exact id/version/hash semantics and is an observation linkage, not automatic mechanism-fit approval. The host saves `revision_relay_protocol`, `revision_relay_experiment` and `verification` objects. It adds no behavior/theory status promotion. A completed or uncertain execution cannot be repeated under another job name: the execution claim binds the exact registration, independent of queue identity. A new registered study is required for another execution.

Equivalent CLI entry points:

```text
python -m swarm_lab.cli design-revision-relay --blocks 2 --seed 173
python -m swarm_lab.cli experiment-revision-relay PROTOCOL_ID --protocol-version 1
python -m swarm_lab.cli audit-revision-relay RESULT_ID --version 1
```

These examples use scripted subjects. Live mode must match the frozen Responses backend/model. Preflight counts every reserved request against the unchanged configured cap, then the shared Store reserves each actual request atomically. No model fallback or automatic retry follows an unknown transport outcome.

## Observable receipts and durable failure

Every boundary saves the exact recipient-scoped request before invocation, invocation state, available canonical records and lineage. After an action, it retains the adapter's bounded action, result and resulting state. Seed, assignment, privileged oracle, future records and the other role's private information remain outside subject requests. The optional adapter context-insertion method is forbidden in this two-factor protocol.

A request receipt proves local construction. Provider metadata is explicitly unattested and missing fields remain unknown. The host preserves response identity/model/usage/hash/status metadata when supplied, while omitting raw provider envelopes and error bodies. Deterministic sanitizer behavior is pinned; a silent change to canonical persisted evidence cannot pass identity checks. Oversized, nonfinite or world-cardinality-invalid outputs normalize to the adapter's replayable invalid sentinel without retaining or hashing an unbounded original.

Before execution, the report has the complete assignment grid. Failure retains a completed prefix, at most one interrupted current unit and an unstarted suffix. It distinguishes pre-subject materialization, invocation, action, oracle and finalization failures. Later initial worlds cannot be invented in a pre-materialization failure. The report keeps `analysis=None`; fresh replay can confirm a retained partial trace while `passed`, `complete_execution` and `quantitative_available` remain false. A publication failure preserves an already stored complete result and separately records the operational job failure.

Accepted ceilings are explicit: 1–64 blocks, protocol/request64KiB, team trace256KiB, report64MiB, fixed decision/contact counts and bounded JSON depth/cardinality. Binary reads are bounded before decoding or archive hashing. These are retained-input limits; they do not bound allocations already made inside Store decoding or a provider adapter. The host chooses the archive root, binds known filenames and checks exact archived bytes against registered/current source pins. A source upgrade fails closed for this instrument; historical artifacts remain inspectable.

## Review record and future extensions

Released adapter SHA256: `260421911d1cbec63f6c5481036574be2b1d6c42d750bb1758597701403ac808`.

Released runner SHA256: `547d25a3c12f12070db640f7abb6c8b94b7f90781683dcf273fcb28a6aa30f0c`.

Released host SHA256: `8d9221c4bb331bbcb30099ecb3c1698bbb4ef39eb9a75e51a1d2572be07fe355`.

Independent staged reviews passed 21 runner checks and seven additional host checks; the owner host cohort passed16. The adapter's 36 promoted focused checks and nine UI checks are separate evidence. The full promoted integration cohort and an actual saved dashboard execution have their own checkpoint records. Test fixtures are not independent behavioral experiments.

The [independent production check](../correction-relay-production-check-20261004.md) binds the actual saved protocol, result and 13-check UI proof to their exact versions and hashes. Fresh pure replay independently checks the eight scripted teams, 32 request/action receipts and archived files. All four cells score 2/2, giving block contrasts `[0, 0]`; no confidence interval or p-value is available under the saved declarations. These results validate the local instrument and remain separate from the earlier live pilots.

A further study can cross reminder timing, selective forwarding, repetition, source authority or alternative routes, but each needs a new reviewed contract, frozen estimand and validated adapter/runner. Persistent subjects, incentives, browser actions and historically calibrated transport remain construction requirements. This capability provides one discriminating experiment, not a universal model of communication.
