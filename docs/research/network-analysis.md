# Network analysis: observable relations before social explanations

The module `swarm_lab.network.analyze_network` computes reproducible descriptive networks from a bounded message window. It returns four projections, directional metrics, evidence IDs, a spectral operator, and a conditional permutation reference. These outputs guide incident investigation. They do not establish causal influence or psychological states.

## Relations and direction

An **observed mention** goes from the message author to an exactly named roster agent. One message can create several events, but mentioning a name more than once does not multiply that recipient's event. A **recorded reply** goes from the responder to the author of the referenced message. The Village export generally lacks reply pointers, so the reply graph may be empty.

An **inferred proximity** edge goes from the author of the previous message to the next author in the same room, within five minutes. An **inferred lexical** edge uses the same ordering and requires at least three shared non-stopwords and Jaccard overlap of at least 0.35. These thresholds are screening choices. Proximity is not a reply and lexical recurrence is not transmission. Each projection remains separate.

Every edge stores its source message IDs and temporal event list. Human speakers are excluded from the agent-only projections, though their messages remain in source data. Exact names miss aliases and may name an agent who did not participate in the imported window.

## Descriptive metrics

For directed weighted adjacency `A`, entry `A_ij` counts relation events from agent `i` to `j`. Degree counts distinct neighbors; strength counts events. Binary reciprocity is the fraction of directed ties with a reverse tie. Weighted reciprocity is `sum_ij min(A_ij,A_ji) / sum_ij A_ij`. Empty graphs have undefined reciprocity, reported as null, rather than a misleading zero. The binary definition follows the [NetworkX reciprocity documentation](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.reciprocity.reciprocity.html).

Incoming concentration is `sum_i p_i^2`, with `p_i` the share of all incoming events. Strong components retain directed reachability; weak components ignore direction only for connectivity. Exact unweighted directed betweenness uses Brandes' shortest-path algorithm, excludes endpoints, and divides by `(n-1)(n-2)`. Edge counts are not interpreted as distances. Its definition and normalization are documented in [NetworkX's betweenness reference](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.centrality.betweenness_centrality.html). A high value indicates brokerage potential in this projected graph; it does not prove actual mediation.

Raw interaction counts depend on activity. Outgoing counts are divided by authored messages. Incoming counts are divided by other-agent messages in rooms where the recipient posted at least once in the imported window. This **coactivity proxy** is deliberately labeled: room membership, actual reading, and time at risk are not known. Rates can exceed one because a message can mention multiple agents. Cross-window comparisons must hold scope rules constant and inspect roster, goals, model, tools, and scaffolding changes.

## A graph spectral basis; LBO interpretation remains open

Only the spectral operator uses `S=(A+A^T)/2`. With `D=diag(sum_j S_ij)`, the module diagonalizes the symmetric normalized graph Laplacian `L=D^(-1/2)(D-S)D^(-1/2)`. Zero-degree nodes have zero rows and contribute null modes. This convention matches the isolated-node handling described in [SciPy's Laplacian documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.csgraph.laplacian.html).

The resulting eigenvalues and orthonormal modes provide a basis for signals over agent nodes, such as blocker-report counts. Low-frequency components describe smooth variation relative to the selected graph. They are not automatically behavioral mechanisms. Symmetrization discards direction; disconnected components give multiple null modes. Repeated eigenvalues permit rotations of the eigenbasis, so individual coordinates should not be compared across runs. A connected graph's second eigenvalue has a conventional connectivity interpretation; disconnected graphs have zero algebraic connectivity. A static network can imply paths whose contacts occur in an impossible order. The importance of temporal ordering is reviewed in [Holme and Saramäki, Temporal Networks](https://arxiv.org/abs/1108.1780).

The user's intended meaning of “LBO basis” must be confirmed. This implementation supplies a **graph Laplacian spectral basis**, not a validated manifold Laplace–Beltrami operator. A manifold interpretation would require a declared geometry, sampling assumptions, and evidence that the chosen construction approximates its operator.

NumPy is optional. Without it, directed metrics and null comparisons remain available, and the spectral result explicitly reports unavailability. Dense eigen-decomposition is bounded to 128 agents; a future sparse adapter must make approximation choices explicit.

## Conditional descriptive null model

With a fixed seed, author labels are shuffled among agent-authored messages within each **room and UTC hour**. This preserves each agent's message count in each stratum, all timestamps, room slots, content, and explicit mention targets. It destroys the original association between authors and content, sender–target ties, and cross-agent ordering. Self-mentions created by a shuffle are excluded, so tie counts can change.

The reference reports mean, standard deviation, standardized difference when the reference variance is nonzero, and upper/lower empirical tail fractions. Zero-variance references are flagged. These are exploratory comparisons, not randomized treatments or confirmatory p-values. Speaker exchangeability is not guaranteed: different roles, models, goals, and opportunities can explain deviation. Multiple comparisons and selection of an interesting incident require held-out confirmation. The hour timescale is a chosen assumption; alternative stratifications require an explicit robustness analysis.

## What would identify a network effect?

A causal experiment must define the network intervention, the exposure mapping, and the outcome. Candidate interventions include varying who receives a privately planted context item, changing communication visibility, or moving a recipient's network position while holding task resources constant. Whole-swarm randomization avoids treating interacting agents as independent replicates. Experiments that estimate spillovers need controlled treatment saturation and explicit exposure assumptions. The historical network supplies candidate hypotheses and environment constraints; its structure alone does not identify these effects.
