# Graph operator research agenda

Read-only review, 4 October 2026. This agenda extends [graph-math-methods.md](graph-math-methods.md); it selects probes, not a universal model of agent society. “LBO” remains provisional shorthand for a graph-Laplacian basis. The recorded reference graph supplies no validated continuous manifold.

## Current guarantees and limits

`network.py` preserves four separate directed projections. Its spectral operator alone uses $S=(A+A^\top)/2$, deletes self-weights, and computes the symmetric normalized Laplacian with zero rows for isolates. Under the implemented positive event-count weights, the operator is coherent. NumPy availability and the 128-node dense limit are explicit. Directed betweenness, reciprocity and components answer different questions from this spectrum.

`spectral_observables.py` supplies deterministic regex-positive message proportions, with authored-message denominators and exact positive message IDs. Referenced nonauthors remain unmeasured; their induced-author alternative recomputes a different operator. These are uncalibrated text observables, not beliefs or coordination quality. The helper trusts its host-produced signal rows; it does not independently authenticate source scope, deduplicate arbitrary caller rows or calibrate labels. Network fingerprints cover message IDs and content hashes, not every actor/time/room/roster binding; full object/source pins remain necessary.

Repeated-mode energy is invariant to sign and rotations within an exactly repeated eigenspace. Individual coordinates are not. Approximate grouping uses a $10^{-8}$ eigenvalue tolerance; its representative eigenvalue makes the grouped Rayleigh calculation an approximation for merely nearby modes. Basis nullity snaps at $10^{-10}$, whereas signal summaries classify eigenvalues at most $10^{-8}$ as null and suppress positive-frequency ratios at or below an absolute $10^{-12}$ energy floor. Report these conventions; do not equate numerical nullity with exact connectivity in arbitrarily ill-conditioned inputs.

Independent bounded checks found no substantive defect on tested host-produced count graphs: 22 existing network/signal/discovery tests passed; an independent mutual-reachability oracle agreed on all 4,165 directed graphs through four nodes. Direction reversal retained the symmetric spectrum, an isolate-only signal had null fraction one, and a repeated-mode rotation changed grouped energy by less than $6\times10^{-17}$. These checks are finite validation, not proof of every input or historical claim.

## Priority 1: validate relations before extending operators

Freeze the selected windows, comparator orientation and explicit name-eligibility variants. Separate extracted naming, recorded reply pointers, source-linked tool actions, successful posting reports and verified subsequent use. A source join or later timestamp supplies neither a recipient acknowledgment nor reading. Retain missing channels and unknown targets rather than completing an apparent communication graph.

Probe: adjudicate a bounded, deterministic sample of exact/short-name/Unicode-disputed edges plus ordinary negatives, blind to lead direction. Record quotation, task-owner reference and address separately. Prediction: a proposed relay motif should retain a feasible, independently supported contact sequence after these distinctions. A reversed sequence or purely third-person references weakens that specific interpretation. It does not establish that no unrecorded route existed. Time-respecting paths are the first directional check because aggregation can create impossible routes. [Holme and Saramäki, original temporal-network review](https://arxiv.org/abs/1108.1780).

## Priority 2: declare what the node signal means

For this normalized operator, smoothness compares $x_i/\sqrt{d_i}$, not raw rates. Equal rates on a three-node path produced Rayleigh .05719 in the review; a square-root-degree signal was numerically null. An isolate's entire signal enters null energy. Neither effect is disagreement or consensus. Operator choice and normalization define the question. [von Luxburg, original spectral-clustering tutorial](https://arxiv.org/abs/0711.0189).

Probe: preregister raw-rate and degree-adjusted-rate descriptions as separate estimands, disclose isolate/component contributions, and inspect label precision against source text. Test whether a candidate contrast survives equalized denominators and task/model strata on held-out windows. Failure would support activity or measurement alternatives. Zero hits remain observed zero hits; absent denominators remain unknown. Small denominators require uncertainty analysis with explicit dependence assumptions, not treating every agent's estimated rate as equally precise.

## Priority 3: compare invariant quantities on declared populations

Use one fixed node universe for each comparison and disclose how it differs from legacy native and pair-common graphs. Keep full-population and measured-author results separate. Adding an inactive referenced target can change density, nullity and normalized centrality without a changed agent action.

Probe: retain selection/matching, vary only extraction or population policy, and compare eigenvalues, grouped energy and component contributions. Include controls for reversed arrows, uniform weight rescaling and repeated-mode rotation. A valid symmetric operator must ignore reversal and common weight scale; directed reachability need not. Such invariance is a measurement check, not behavioral evidence. For longitudinal signals, first hold the graph fixed; separately hold the signal fixed while changing the graph. Avoid comparing “mode two” coordinates across changed operators or using future edges in a predictive trigger.

The existing room-hour author permutation preserves message slots, content and within-stratum activity, but excludes newly created self-mentions and assumes exchangeability that task roles can violate. Probe alternative, prespecified role/activity strata with unchanged windows; report degeneracy and varying event totals. Exploratory tails are neither causal tests nor corrected discovery-wide p-values.

## Priority 4: earn a directed or edge-flow extension

A directed stationary-flow Laplacian is useful only after defining a defensible transition process. Sparse reference DAGs have sinks and disconnected classes; stationarity, holding and teleportation require declared choices. Teleportation creates modeled opportunities. A directed operator may still use a symmetric stationary-flow construction and lose some circulation information. [Chung, original directed-Laplacian paper](https://people.cs.umass.edu/~mahadeva/cs791bb/reading/dichee.pdf).

First probe: compare strictly ordered reachability and finite-horizon transitions on recorded opportunities against the current symmetric description. Require a held-out prediction improved beyond activity, role and task baselines. If source-linked contacts remain too sparse or transition assumptions dominate, defer the stationary operator.

Hodge analysis instead addresses an oriented **edge signal**. A proposed net flow $f_{ij}=A_{ij}-A_{ji}$ could separate gradient and circulation components, but it cancels balanced reciprocal activity. Curl versus harmonic decomposition also requires a declared complex; filling every contact triangle chooses a mathematical 2-cell, not a recorded joint interaction. Ranking inconsistency mathematics does not establish inconsistent agents. [Jiang et al., original combinatorial-Hodge study](https://arxiv.org/abs/0811.1067).

Smallest probe: synthetic trees, triangles and unfilled cycles, followed by a source-adjudicated flow whose conserved units and meaning are explicit. Require orientation-invariant energy and known decomposition recovery. No current data justify calling mention circulation a rumor loop, organizational hierarchy or latent trait. Neither extension is implemented by this agenda.

## Decision boundary and review pins

Advance to a causal probe only after observed relations support a mechanism: keep aggregate contacts and task information fixed, randomize relay timing or a source-preserving affordance, and score eligible delivery, subsequent source-specific use and task accuracy separately. Failure to induce exposure is a procedural finding; floor outcomes do not identify topology effects. Whole-network assignment, interference and model/task scope must remain explicit. Prefer one discriminating intervention over additional spectral dashboards.

Binary SHA256 pins of reviewed files:

- `network.py`: `421b184c7b288598c6718a15d6a88d64ed491a5b2b4ca6f949567a8a0a7651c7`
- `spectral_observables.py`: `a0fbc96b818f04f5b8104c2272ebb7055c06c0ee63e31451da2fdca474fba464`
- `graph_discovery.py` (signal-summary dependency): `6ec021234d61fda3e3f8f8914fabbfc6eafc2ba804adcce79e0e31202a1b96ba`
- `graph-math-methods.md`: `fb98f5c32c4af28de16b328c8cefd7adeeb423583876e9d2c2b78e4de93a9ca5`

Only this new agenda was written. No implementation, tests, database, source scan or model execution changed.
