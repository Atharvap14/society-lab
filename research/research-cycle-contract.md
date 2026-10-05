# Checkpointed research cycle

This optional composition starts from an existing, exact-version, non-rejected behavior. It makes the current capability-driven environment authoring path executable as one research cycle. It does not replace discovery, define a closed ontology of behaviors, or claim that a successfully compiled environment captures a historical mechanism.

The implementation is [research_cycle.py](../swarm_lab/research_cycle.py). Its entry points are:

```python
start_research_cycle(
    lab,
    behavior_ref={"kind": "behavior", "id": "...", "version": 1, "hash": "..."},
    source_refs={"dataset": exact_dataset_ref, "discovery": exact_discovery_ref},
    proposal=declarative_blueprint, fit_review=bound_review,
    # Or blueprint_ref=an_exact_existing_environment_blueprint_ref.
    # Or research_live=True, with no supplied proposal/review.
    required_capabilities=[], trials_per_cell=2, seed=4491, audit_seed=0,
    research_live=False, subjects_live=False,
    research_harness="responses", subject_harness="responses",
    max_new_model_calls=0, job_id="a-stable-cycle-identity",
)

resume_research_cycle(lab, cycle_id)
```

Every reference has exactly `kind`, `id`, positive integer `version`, and a lowercase SHA-256 `hash`. Numeric booleans and floating-point versions are rejected. Source references must agree with the behavior's original dataset and discovery pins. Those source versions must still be current when a new stage calls an API that resolves latest versions. An older exact reference is not copied into a new object to disguise drift.

When selecting an exact existing blueprint, omitted `required_capabilities` inherits its pinned trusted list. An explicitly supplied different list blocks selection. Existing discovery-to-dataset pins, when present, must also agree with the selected dataset; unknown linkage is not invented.

Research-agent generation and experimental subjects have separate boolean flags. Research-live mode enables the existing builder and independent-role fit review; it does not enable model subjects. Subjects-live mode registers the requested Responses subject backend; it does not enable research generation. Offline construction uses a supplied proposal/review, or selects an exact existing blueprint. Offline subject execution uses the world's existing scripted policy and supports infrastructure claims only. Facts are reconstructed and checked in code in every mode. This cycle does not silently request a paid evaluator or curator.

## Stages and evidence boundaries

The allowlisted sequence is construction/selection, registration, execution, independent replay, finite claim checking, and guarded hypothesis curation. There is no function name, import path, generated code, or callback in its declarative plan.

Construction delegates to `Lab.construct_environment`. Host-supplied behavior/dataset/discovery references are attached to the proposal. A supplied fit review must bind the materialized proposal's exact blueprint hash, including these attached references. A compiler success alone cannot advance the cycle: the result must be compiled and have a bound `approved_analogue` fit review. Unsupported requirements, absent approval, and semantic blocking preserve the blueprint and all available construction-attempt versions. They produce a durable blocked cycle with extension requirements.

Registration delegates to `Lab.register_blueprint`. The selected world must remain canonically identical to the reviewed world. The bridge dispatches only `protocol`, `network_protocol`, `complementary_protocol`, and `resource_protocol`, to their corresponding existing runners. A supported custom graph that an existing registered design cannot preserve remains a design gap; the cycle does not substitute ring or complete topology. The registered study tests its existing predefined context contrast. It does not automatically operationalize every proposed mechanism in the blueprint.

Execution uses one fixed child-job identity. The result must bind that job, the exact registration, the expected result kind, model/backend mode, canonical execution report, and expected local archive directory. The entire predeclared worst-case allocation must fit the remaining authorized call ceiling before any live subjects start. Completed never-delivered units remain in each runner's registered intention-to-treat analysis. The cycle never creates estimates for incomplete execution or chooses only successful runs.

`Lab.audit` must return an independently computed zero-model-call replay proof for the exact result version/hash. All recorded checks must pass, and the execution source archive must match the protocol's pinned files. The cycle additionally rechecks canonical report bytes and typed identity of the frozen protocol, recorded runs, and saved analysis. Replay checks recorded requests, actions, transitions and oracle outcomes; it cannot attest a provider's internal consumption or turn a synthetic world into historical identification.

`Lab.evaluate_claims` runs in deterministic fact-reconstruction mode. The result must bind the exact executed result and report hash. The cycle rebuilds the finite ledger and selected packet, then recomputes typed claim checks. A saved `all_executable_claims_supported` flag, inconsistent packet, bool/number substitution, or unchecked model prose cannot authorize curation. The ledger's finite facts are the checked quantitative evidence. Free statements, mediation, historical claims and generalization remain outside that verification.

## Curation is a hypothesis, not a finding

The new local curation guard requires a completed exact result, matching blueprint/registration, independent passing proof, and recomputed all-supported finite claims. It then saves a `theory` object with `status="hypothesis"`. Its statement comes from the blueprint's proposed mechanism. It is explicitly labeled an untested analogue hypothesis; no effect direction is manufactured.

The packet includes its world/spec/backend scope, original behavior and source references, executed result/proof/claim references, rival explanations, falsifiers, unmodeled features, and `mechanism_support`/`generalization` set to `unestablished`. Replication is unperformed, supporting/conflicting result lists are empty, and curation does not change behavior status. The older artifact-only theory template is never applied to other worlds. A future typed live-curator adapter would require a separately explicit amendment; it is unavailable in this version.

The existing artifact runner intentionally appends experiment evidence to its behavior. The cycle validates exactly the limited existing library change, records the new behavior reference separately, and keeps the original selected behavior/source references immutable. Unexpected semantic or source changes block advancement. The other three runners do not receive a fabricated behavior alias when their result wrappers omit a top-level behavior ID: linkage comes through the exact registered protocol and authored incident/world.

## Budget, checkpoints and resumption

The cycle atomically claims its root job and every stage attempt before invoking a component. A server that already claims an outer job should supply a distinct deterministic inner identity such as `outer-job.cycle`. Duplicate cycle identities are rejected. The original checkpoint binds the immutable plan, root job ID and deterministic cycle ID; resume and conflict-return validation cannot select replacement root/child identities from a rehashed old snapshot. Checkpoints append immutable versions with stage states, retained artifact references, construction-attempt versions, failure phase, and extension requirements. A compare-and-put transaction requires the exact previous checkpoint version/hash, returns the exact inserted version, and publishes at most the changed child job and root job in that same transaction. A stale writer cannot overwrite a newer checkpoint or regress its completed job; a conflict trace retains artifact identities already known to that writer, without inventing their outcomes.

The call ceiling is an absolute Store count calculated once as the smaller of the global cap and starting usage plus explicitly authorized new calls. A shallow Lab copy supplies that bounded cap to existing harnesses; the original settings are unchanged. Resume never resets the starting usage, increases the ceiling, changes flags or seeds, or substitutes a backend. Other jobs consuming the shared Store budget can reduce available capacity. A per-stage research-role request may consume multiple calls; an authorized ceiling does not guarantee that every live stage will finish before it is exhausted. This is a shared accounting ceiling, not a reservation of unused calls for the cycle. The source/budget guard conservatively blocks continuation if later shared usage exceeds the original absolute ceiling, including a free replay or curation stage. Such a block does not mean those CPU stages require a model call; a separately explicit reconciliation or amendment is needed, rather than silently increasing authorization.

A terminal completed or blocked cycle is returned unchanged only when its exact current version/hash, plan hash, retained artifacts, and terminal state agree with the authoritative root-job closure. Completed stages also require exact child-job/artifact bindings. Appending a rehashed status flag cannot manufacture completion, remove a blocked requirement, or promote a saved hypothesis. This return is a historical result: it does not perform a fresh source-file or execution-archive audit, and does not claim that those bytes remain unchanged after completion. Request a new independent audit when a current attestation is needed.

A known completed child execution can be recovered from its exact retained job/result identity if a later checkpoint or CPU stage failed. The new-work allocation check runs after this recovery, so verification at the original ceiling does not demand another worst-case subject allocation. Subjects are never replayed to obtain a cleaner result. Before a resumed nonterminal cycle advances, its cached completed stages are revalidated against executable output contracts, current versions, report bytes, finite claims and the typed hypothesis packet. Audit, deterministic fact reconstruction and pure curation can have at most three safe attempts; completed artifacts are reused when available.

A separately claimed resume invocation job closes to the exact returned cycle reference/status, or records a failure with the requested and last observed cycle identities when the invocation raises. Its completion is an invocation record, not authoritative experiment or cycle completion. It cannot regress the root or child jobs. A process killed before it can publish that invocation closure remains an unresolved running claim; this local contract does not infer that it finished.

Checkpoint and terminal root-job publication are atomic for new executions. Failed checkpoints require their exact authoritative root-job closure before becoming resumable. Every stage state uses a strict integer attempt count, the exact corresponding child-job identity, typed retained artifact references and sequential stage ordering. Numeric booleans/floats, invented later-stage progress and mismatched job/ref fields are rejected before a safe retry can claim work. A legacy or externally written terminal checkpoint lacking its exact authoritative closure requires explicit reconciliation; resume does not rewrite jobs merely to assert that an incomplete authority record was complete. A worker killed before any authoritative artifact exists remains uncertain. A worker killed after a subject result was saved can recover that exact result without replaying subjects.

A claimed construction, registration or execution stage without authoritative completion is not relaunched automatically. The blocked cycle preserves partial evidence and calls for explicit reconciliation or a separately amended cycle. In particular, a failed reviewer can preserve a materialized builder proposal; an operator may explicitly resume that existing review with the separate authoring API and start a new cycle selecting its exact resulting blueprint. The builder is not repeated by this cycle. An incomplete execution remains an incomplete artifact with no downstream outcome claims or theory.

These checkpoints are local execution evidence, not an external preregistration timestamp or a general distributed lease service. Resume identities prevent duplicate stage claims; they do not establish that a provider response was consumed or that a killed process can safely be restarted mid-action. Source reference and retrieval checks establish exact imported-record membership and access, not semantic entailment of a generated statement. A fit review remains a supplied or separately executed role judgment, not a code-verifiable proof of historical mechanism fit. Tests use temporary stores and real small CPU worlds; no hosted calls or production registry writes are needed to verify this contract.
