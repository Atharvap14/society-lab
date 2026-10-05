# Conditional temporal reference baseline

This instrument asks a narrow question: **how do strict reference-path reachability and representation deletion change when the same edge-bearing messages occupy different retained time slots?** It complements the saved temporal source audit. It neither repairs its sources nor turns naming into delivery, influence or a causal network.

Randomized temporal references are defined by what their procedures preserve and destroy; those choices can change the interpretation of a comparison. That distinction motivates a separate, versioned baseline here. The implementation does not claim an exact microcanonical sampler or a valid hypothesis test for these records. [Gauvin et al., Randomized Reference Models for Temporal Networks, SIAM Review 64(4), 2022](https://epubs.siam.org/doi/10.1137/19M1242252), [author preprint](https://arxiv.org/abs/1806.04032).

## Unit, conditioning and preserved quantities

`timestamp_permutation_reference(temporal_audit, *, window_ids=None, variants=None, seed=4411, resamples=64, max_work=10_000_000, source_refs=None)` consumes already frozen `strict-temporal-mentions-v1` events. It does not import messages, infer aliases, expand windows, select new leads or rematch comparators. A caller may select existing window/variant IDs only. Each cell keeps its original fixed node universe, including referenced nonauthors and isolates.

Within one exact room/window/variant, let each distinct **edge-bearing source message** be a group. Every accepted target edge from that message remains together. The algorithm shuffles the list of these messages' original timestamps and assigns one shuffled timestamp to each message group. Equal timestamps remain equal-time slots; there is no artificial ID order within a tie. Messages with no accepted reference edges, including human context, are excluded from this conditional timestamp multiset. Shuffling every authored-message slot would define another reference model.

The procedure preserves source-message identities, author/target identities, per-message target batches, static weighted edges, degrees, source counts, and the **message-time multiset**. Assertions verify the graph and timestamp invariants at every draw. It need not preserve edge-time multiplicities: moving a two-target message into a one-target message's slot changes the number of edges at that timestamp. It also changes author-specific timing, order, inter-event gaps, burst associations, task chronology and apparent node lifetimes. Those changes are assumptions of this reference, not observed alternate histories.

No spectral comparison is needed: the static operator has not changed. Graph eigenvector rotations cannot explain a purely temporal contrast. The relevance of ordering, rather than only aggregate topology, is established in temporal-network mathematics; whether these particular reference arrows represent contacts remains a separate empirical question. [Holme and Saramäki, Temporal Networks](https://arxiv.org/abs/1108.1780).

## Metrics and undefined cases

For the original assignment and every draw, count distinct ordered pairs connected by an author-to-reference path with **strictly increasing UTC timestamps** within this room window. Single-edge paths are valid; simultaneous edges cannot relay through one another. The count-only batched algorithm retains no synthetic path witnesses and asserts temporal pairs remain a subset of the unchanged static reachability.

There is no additional processing latency, maximum inter-event gap or measured memory lifetime. Those would define another path instrument, rather than follow automatically from this temporal ordering rule.

For each fixed node, recompute all alternate time-respecting paths after deleting it. The loss denominator contains the assignment's initially reachable pairs excluding that node as either endpoint. Report the largest defined loss fraction over the original fixed universe. This matches the saved temporal instrument's metric. The maximizing node and eligible denominator can change across draws; it is not the effect of experimentally removing one prespecified agent.

An empty eligible denominator produces `None`, never zero. A two-node graph can have a valid direct reference and an undefined deletion statistic. An empty graph has zero represented reachable pairs but no measured absence of agent behavior. Envelopes exclude undefined values and disclose both defined and undefined draw counts. A constant metric is distinguished from a constant assignment: many different schedules can yield the same reachable-pair count. Zero or one edge-bearing message, or one distinct original timestamp, creates structural assignment degeneracy.

Before resampling, original static pair counts, temporal pair counts, maximum deletion loss and every node's deletion numerator/denominator are reproduced against the frozen audit. A mismatch, missing or invalid timestamp, inconsistent source binding, duplicate event, changed universe or malformed field fails closed. Unrequested Unicode variants remain unavailable rather than acquiring zero-valued outcomes.

## Output and provenance

`windows[window_id].variants[variant]` contains original event pins and message groups, static invariants, `observed_replay`, the reproduced observation, reference distributions and degeneracy diagnostics. Empirical envelopes expose minimum, quartiles, median, maximum and mean. Rank counts show draws below, equal to and above the observed statistic. The nominal rank grid is `1/(R+1)`; tied assignments and discrete metrics can make attainable distinctions much coarser. These are **reference descriptions**, not p-values, confidence intervals, significance decisions or calibrated anomaly probabilities.

Each cell derives its random stream from version, seed, window ID and variant, with canonical message ordering. Runtime Python version and the standard-library RNG backend accompany implementation pins; reproducibility should be checked on that runtime. Selecting another cell does not alter its draws. Separate streams do not make windows independent replications or make variant comparisons paired experiments. Each synthetic assignment has a reproducible fingerprint, explicitly labeled synthetic. Assigned times are never emitted as source timestamps or witnesses. Original IDs, hashes, instruments, measurement statuses and source coordinates remain unchanged.

Typed registry references preserve their Store hashes separately from the pure projected-input fingerprint. The pure function does not authenticate registry objects or reread source bytes; the host must verify the frozen temporal object, upstream pins and extraction replay. A source-linked posting event would still establish neither reading nor semantic adoption.

## Bounds and next uses

Limits are 24 windows, 128 nodes per window, 10,000 events per cell, 256 requested draws, and bounded finite JSON input/output. A conservative aggregate work proxy includes original replay, every draw and all fixed-node deletions. An over-budget request returns `not_computed_work_budget` for the entire requested computation: no partial draws, envelopes or rank counts are released. Explicitly reducing scope or resamples creates a new declared request; the function does not adapt them after inspecting results.

The pinned six-window source object `temporal_path_audit-1c08eba1b540` v1, Store SHA256 `4ef7a67531cb9a2db9a8f7ba8ab1bbc403549cbe08e806c2b00a2cfb106e6512`, was inspected read-only. Its 24 cells pass input preflight; default 64 draws have estimated work 2,632,760. A budget-one check executed zero draws and returned explicit unknown results. This note reports no historical permutation outcome.

The original windows were selected from the same source for earlier graph contrasts. Message-time exchangeability is unestablished: scheduling, role obligations, shared instructions and tasks may make most shuffled schedules impossible. A useful next probe is to adjudicate one proposed relay's address and chronology, then compare a preregistered held-out episode with an appropriately constrained reference. Author- or task-conditioned shuffles would answer different questions and may be entirely degenerate. A future randomized timing experiment needs actual recipient visibility and subsequent source-specific use, alongside task outcomes. These observational shuffles alone supply neither that intervention nor an automatic behavior/theory promotion.
