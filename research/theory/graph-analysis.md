# Graph analysis as a behavioral search instrument

Working analytical options, 4 October 2026. The user's “LBO basis” reference remains ambiguous. This document describes graph-Laplacian options without deciding that a Laplace–Beltrami construction is the required representation.

## Specify the graph before computing it

Graph nodes may be agents, messages, commitments, tasks, artifacts, or episodes. Edges may be authorship, observed mentions, explicit references, verified artifact access, delivery opportunity, or inferred temporal proximity. Keep edge types, timestamps, confidence, and evidence IDs. A mention is observed text; the interpretation that it caused a response is inferred.

Do not collapse all relations into one undifferentiated weight unless the analytical question justifies the weighting and its sensitivity is checked. A large communication graph can principally represent how often agents are active, which rooms they can access, and how many tasks they receive.

Task scope, participation windows, room membership, scheduler constraints, and roster changes define exposure opportunity. Normalize relative to a stated opportunity or compare like-for-like populations. Raw degree can be driven by logging density rather than social influence.

## A graph spectral basis

For a nonnegative symmetric weighted adjacency `W`, degree matrix `D`, and combinatorial Laplacian `L = D - W`, an eigenbasis can decompose a signal attached to nodes. The symmetric normalized Laplacian is commonly `L_sym = I - D^(-1/2) W D^(-1/2)`, with an explicitly chosen convention for isolated nodes. This is a mathematical transform of the specified graph, not evidence of hidden psychological dimensions.

Low-eigenvalue components vary smoothly across strongly connected nodes. Higher components can expose local differences in a chosen node signal, such as unresolved commitments or correction uptake. Signal-processing operations on graphs and alternative spectral definitions are explained by [Shuman et al.](https://arxiv.org/abs/1211.0053v2). Whether smoothness is desirable depends on the question; a genuinely distinct agent may look like a high-frequency anomaly.

The Laplacian basis changes when edges, weights, or population change. Disconnected components give multiple zero modes. Eigenvector sign is arbitrary, and repeated or near-repeated eigenvalues allow rotations or unstable coordinates. Compare aligned subspaces, spectra, or invariant quantities where appropriate; do not read coordinate flips as behavioral change. Clustering also depends on normalization and construction choices. [von Luxburg](https://arxiv.org/abs/0711.0189).

Directed temporal communication cannot simply be plugged into a symmetric spectral interpretation. Symmetrizing discards direction. Preserve the directed graph for transmission hypotheses and explicitly label the undirected projection used for visualization or spectral screening.

## Graph Laplacian and Laplace–Beltrami are different commitments

The continuous Laplace–Beltrami operator acts on a manifold. A graph operator can approximate such an operator under particular sampling, kernel, density normalization, and geometric assumptions. A swarm communication graph does not automatically satisfy those assumptions. Calling a graph spectral embedding an “LBO basis” does not establish a latent social manifold.

If manifold-based analysis is pursued, specify what points are sampled, what distance represents, how neighborhoods and density are handled, and why the geometry is scientifically meaningful. Compare simpler graph statistics and temporal motifs first. The lab should preserve this as a selectable research method, not the universal representation of behavior.

## Candidate anomaly searches

| Search lead | Candidate representation | Main alternative explanation |
|---|---|---|
| Sudden structural bottleneck | Delivery/dependency graph and articulation-like structure | A task legitimately changed scope or required a scarce tool |
| Reciprocal acknowledgements without action | Typed temporal motif | Work happened in an unlogged tool or separate room |
| High adoption with low independent evidence | Claim-lineage subgraph | Multiple sources share a genuine correct primary fact |
| Persistent disagreement along a cluster boundary | Graph signal and community comparison | Clusters have different information or goals |
| Rapid ownership changes | Commitment transition motif | New deadlines or external constraints require adaptation |
| Correction reaches one subgroup only | Exposure path and later explicit use | Missing delivery/read data or justified rejection |
| Memory carries an assumption across episodes | Memory/event lineage | The assumption remained correct in the new task |

Detectors should return ranked search leads, not causal labels. An investigator must inspect the underlying evidence. Use several representations when they answer distinct questions; representation disagreement can itself reveal measurement limits.

## Null models and sensitivity

Every graph anomaly score needs a baseline appropriate to its construct. Useful candidates include degree-preserving rewiring within a task, shuffling event times within activity windows, shuffling labels within agent/task strata, and comparing ordinary episodes matched on roster, room access, density, and resource regime. Each null preserves some structure and destroys another; say which hypothesis it tests.

Unrestricted rewiring can create impossible communications. Time shuffling can destroy real task boundaries. Agent-label permutation may violate fixed roles or unequal access. Validate the null against world constraints rather than choosing it because it yields dramatic z-scores.

Check sensitivity to edge extraction, threshold, temporal window, graph normalization, isolated-node handling, detector errors, and missing records. Resample whole episodes or independent task blocks where appropriate. Overlapping windows are dependent; treating them as independent observations understates uncertainty. Track the number of scanned patterns and separate exploratory rankings from confirmatory tests.

Use training windows to choose weights and thresholds, then evaluate on held-out time or tasks. Do not use future edges to judge whether a detector could have acted at an earlier decision point. Dynamic graphs should log the graph snapshot available at every proposed trigger.

## Graph output contract

Preserve node/edge schema, construction version, eligibility rules, evidence IDs, observed versus inferred status, time window, missingness, weights, normalization, projection rules, and any null-model parameters. Spectral outputs additionally need eigenvalue ordering, chosen dimension, numerical tolerance, disconnected-component treatment, and sensitivity results.

The researcher-facing explanation should say: “This episode differs from its comparison set on this specified statistic.” It should not say: “The graph proves this agent led the group.” Causal interpretation belongs to a designed experiment or a defensible identification analysis.
