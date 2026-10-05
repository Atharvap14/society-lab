# Graph mathematics for a research instrument

Methods review, 4 October 2026. This note describes the current implementation and research options; it does not select a universal representation of agent behavior. The user's “LBO” reference is interpreted provisionally as a graph-Laplacian basis. A continuous Laplace–Beltrami interpretation remains unestablished.

The useful scientific chain is **recorded relation → reproducible descriptive contrast → adjudicated behavioral hypothesis → deliberately varied environment → bounded causal conclusion**. A graph is an instrument in that chain. Neither an unusual spectrum nor an investigator's explanation establishes a network effect, novelty, or an agent's mental state.

## 1. What the implementation measures

Code reviewed: [`network.py`](../../swarm_lab/network.py), [`graph_discovery.py`](../../swarm_lab/graph_discovery.py), [`spectral_observables.py`](../../swarm_lab/spectral_observables.py), and the relation extractor in [`discovery.py`](../../swarm_lab/discovery.py). The network and window-search versions are `communication-networks-v1` and `windowed-network-leads-v1`. Preserve these versions with every result; this document describes their current semantics, not an API promise for future versions.

| Output | Implemented definition | Appropriate interpretation |
|---|---|---|
| `observed_mentions` | Author → agent whose exact roster display name appears in a message; one event per named recipient per message | Naming, with source-message evidence; delivery and reading unknown |
| `observed_replies` | Responder → parent-message author, from an explicit reply pointer | Recorded response relation; exporter frequently lacks these pointers |
| `inferred_proximity` | Previous → next different speaker in the same room, within five minutes | Sequential proximity; an opportunity hypothesis |
| `inferred_lexical` | The same adjacent cross-speaker pair, within five minutes, with at least three shared retained tokens and Jaccard overlap ≥ .35 | Lexical recurrence; neither semantic agreement nor adoption |
| Directed graph metrics | Event-count weights, directed density/reciprocity, degree/strength, concentration, components and unweighted shortest-path betweenness | Structure of the specified projection |
| `spectral` | Symmetric normalized Laplacian of each separately symmetrized projection | Descriptive basis for that chosen relation |
| `observable_signals` | Per-agent deterministic regex-positive messages / retained authored messages | Text-screening rates with evidence IDs and denominators |
| `leads` | Selected feature contrasts between nearby, nonoverlapping room windows | Ranked research questions requiring source adjudication |

The reply arrow is particularly consequential: it points toward the parent, whereas a parent-to-responder information-opportunity graph would reverse it. Mixing that orientation with proximity arrows can invert a transmission narrative. Future delivery, verified access, quotation, correction uptake, commitment and artifact-version relations should receive distinct types and directions. The present four channels must not be pooled under the label “influence.”

Every projection currently includes the same scope-specific node set: observed agent authors plus referenced targets. Human speakers are excluded from the agent projection. Exact-name extraction can miss aliases and can include a quoted name; no event establishes intentional address. A referenced nonauthor is not an observed silent participant, and an absent node is not proven absent from the society.

The existing extractor also excludes display names shorter than three characters, including `o1` and `o3`. Such agents can still enter the author node set, so an incoming mention count can be zero because of instrument eligibility rather than lack of recorded naming. The following-week audit independently reproduces 62 nonself graph-eligible exact pairs versus 143 in an all-length lexical diagnostic; 81 omitted pairs name `o3` or `o1`. A separate Unicode shadow adds nineteen pairs to either instrument. These are distinct sensitivity definitions; neither silently changes the graph or establishes intentional address. Short-name eligibility and Unicode aliases need explicit versions and source adjudication before centrality comparisons.

`bridge_dependence` is the largest fraction of *static directed reachable pairs* lost after deleting one node, excluding pairs having that node as an endpoint. It is bounded to 128 nodes. This is a deletion of a representation, not an intervention that removed an agent. Likewise betweenness counts unweighted directed shortest paths, not messages actually mediated.

## 2. The implemented operator and its interpretation

For one projection let $A_{ij}$ be the count of recorded events from $i$ to $j$, and $D=\operatorname{diag}(d_i)$. The code constructs

\[
S=(A+A^\top)/2,\qquad d_i=\sum_j S_{ij},\qquad
L=\operatorname{diag}(\mathbf 1[d_i>0])-D^{-1/2}SD^{-1/2},
\]

where the inverse square root is zero for zero degree and self-weights are removed. Thus isolates have **zero rows**, rather than a diagonal entry of one. The dense `numpy.linalg.eigh` calculation is available only with NumPy and at most 128 nodes; larger graphs retain directed metrics but have an explicitly unavailable basis.

On positive-degree nodes this is the conventional symmetric normalized graph Laplacian. Its nonnegative spectrum describes the chosen weighted graph, and component structure produces null directions. Normalization and graph construction change spectral interpretations; the classic tutorial explains these distinctions. [von Luxburg, *A Tutorial on Spectral Clustering*](https://arxiv.org/abs/0711.0189).

For a supplied real signal $x$, the implemented quadratic form has the identity

\[
x^\top Lx=\tfrac12\sum_{i,j:d_i d_j>0}
S_{ij}\left(\frac{x_i}{\sqrt{d_i}}-\frac{x_j}{\sqrt{d_j}}\right)^2.
\]

This makes the interpretation precise: smoothness concerns **degree-scaled signal differences**. An equal raw rate at every node need not be a null signal on an irregular graph. Within a nontrivial connected component the null direction is proportional to $\sqrt d$. If a future question concerns variation in a raw quantity $y_i$, analyzing $x_i=\sqrt{d_i}y_i$ would answer a different, explicit question; the current code does not apply that transform automatically.

For orthonormal eigenvectors $u_k$, coefficients $c_k=u_k^\top x$ decompose energy. Graph signal processing supplies this spectral language, without making the signal a latent trait. [Shuman et al., *The Emerging Field of Signal Processing on Graphs*](https://arxiv.org/abs/1211.0053v2).

`graph_signal_summary` currently exports:

- `signal_energy` $=\lVert x\rVert^2$;
- `eigenspace_energy`, sums of $c_k^2$ in eigenvalue groups;
- `rayleigh_smoothness`, the eigenvalue-weighted energy divided by total energy;
- `null_energy_fraction`, energy in eigenvalues ≤ $10^{-8}$ / total;
- `low_positive_frequency_energy_fraction`, energy in $10^{-8}<\lambda\le c$ / positive-frequency energy, with default cutoff $c=.5$.

Ratios are undefined where their denominator vanishes. The supplied signal must contain exactly one finite numeric value per basis node, without extras. A high null fraction can result from disconnected components, isolate values or signal level; it is not evidence of consensus. The field named `algebraic_connectivity` is the second ordered eigenvalue of this **normalized, symmetrized** operator, including the isolate convention. Do not compare it directly to a combinatorial-Laplacian statistic or call it communication efficiency.

No signal centering, residualization, diffusion fitting, spectral null test, community assignment or manifold estimation occurs here. Rates and edges may be constructed from the same text, so an association between them can be a measurement artifact.

### Repeated eigenvalues and comparable quantities

An eigenvector's sign is arbitrary. The current sign convention makes its largest absolute entry positive for display; it does not make a persistent behavioral coordinate. For an exactly repeated eigenvalue, any orthonormal rotation within the eigenspace is valid. If $U_E$ spans that space, use its projector and energy

\[
P_E=U_EU_E^\top,\qquad \mathcal E_E(x)=x^\top P_Ex=\lVert U_E^\top x\rVert^2.
\]

Replacing $U_E$ by $U_EQ$, where $Q^\top Q=I$, leaves $P_E$ and $E_E$ unchanged. Individual mode coefficients can change substantially without any change in the graph or signal.

The implementation groups eigenvalues within $10^{-8}$ and uses the first group eigenvalue when computing weighted energy. Group energy is invariant to choosing coordinates for that grouped subspace; treating slightly unequal eigenvalues as equal makes the weighted Rayleigh value a numerical approximation. Report tolerance and inspect eigenvalue gaps. A cutoff crossing can change a band fraction abruptly. Varying the cutoff is a sensitivity analysis, not another independent result.

### Directed operators and implemented temporal paths

Keep directed event tables for transmission hypotheses. An asymmetric adjacency or random-walk operator does not generally provide the same real orthogonal eigenbasis as the implemented symmetric $L$.

A future option is Chung's stationary-flow construction: for a specified row-stochastic transition matrix $P$, positive stationary distribution $\pi$, and $\Pi=\operatorname{diag}(\pi)$,

\[
L_C=I-\tfrac12(\Pi^{1/2}P\Pi^{-1/2}
+\Pi^{-1/2}P^\top\Pi^{1/2}).
\]

It uses directed transition structure and stationary flow while producing a symmetric operator; the resulting matrix does not retain every distinction in circulation or arrow direction. Keep the original transition/event representation for directional hypotheses. Its assumptions and choices matter: sinks, disconnected classes, periodicity, holding probabilities and teleportation need explicit handling. Artificial teleportation must not be described as a recorded communication channel. This is not implemented. [Chung, *Laplacians and the Cheeger Inequality for Directed Graphs*, original paper](https://people.cs.umass.edu/~mahadeva/cs791bb/reading/dichee.pdf).

Temporal event paths may be more relevant than any stationary operator. A static path $a\to b\to c$ cannot transmit a newly introduced item when $b\to c$ occurred before $a\to b$. Timing can alter reachability and dynamics even when the aggregate graph is unchanged. [Holme and Saramäki, *Temporal Networks*](https://arxiv.org/abs/1108.1780).

The separate [temporal reference-path instrument](../../swarm_lab/temporal_network.py) now computes static and strictly time-ordered reachability within fixed room windows, plus alternate-route node-deletion loss. Equal-time events cannot relay through each other. Original message IDs, timestamps, hashes, match coordinates and bounded path witnesses remain attached. Its universe is fixed per window across extraction variants and can differ from the legacy native and pair-common universes. The [saved six-window audit](temporal-path-interpretation.md) retains backward-time witnesses and unchanged windows. Direction remains author→matched name; this is not observed delivery or influence. Action, delivery and subsequent-use times require separate source channels, and a receipt proves neither reading nor belief.

### Why a graph basis is not yet an LBO basis

A continuous Laplace–Beltrami operator needs a geometric domain and metric. Graph-to-manifold convergence is a substantive modeling claim: the point sampling, neighborhood/kernel construction, scale sequence and density treatment must be justified. Belkin and Niyogi establish such convergence for specified point-cloud operators and manifold sampling assumptions. [Original NIPS 2006 paper](https://proceedings.neurips.cc/paper/2006/file/5848ad959570f87753a60ce8be1567f3-Paper.pdf). Recorded agent mention counts supply neither a sampled manifold nor a validated geometric distance. Even an embedding built from behavior vectors would need separate construct validation; it would not inherit these assumptions from its use of an eigensolver.

## 3. Nulls, denominators and missingness

The existing `null_reference` is a **room–UTC-hour author-slot permutation**. It keeps message content, target-name mentions, timestamps and rooms fixed, shuffles author labels within each stratum, and preserves each author's message count there. Sender-content association and original ties are destroyed. Newly created self-mentions are dropped, so total event count can change. It is not degree-preserving rewiring or a membership-aware null.

Its tail fractions and standardized differences are descriptive reference comparisons. Fixed roles, goals, models or unequal access can violate author exchangeability. Degenerate reference distributions are reported; they should not be converted into infinite anomaly scores. The current tails are not multiplicity-adjusted confirmatory p-values.

Different nulls ask different questions. Graph-space choices, including fixed degrees, allowed loops/multiple edges and labeling, change the reference distribution. [Fosdick et al., *Configuring Random Graph Models with Fixed Degree Sequences*](https://arxiv.org/abs/1608.00607).

| Research question | Candidate future reference | What must remain explicit |
|---|---|---|
| Do ties exceed ordinary naming under unequal activity? | Current author-slot null, plus sensitivity to strata and role restrictions | Content-role constraints; varying event totals |
| Is reciprocity more than in/out-degree structure predicts? | Directed fixed-degree rewiring restricted to permissible room/task contacts | Binary degree versus weighted strength; valid graph space and sampler |
| Are contacts unusually ordered for transmission? | Event-time permutation within known participation/task intervals | Burst structure, scheduler constraints and temporal boundaries preserved or destroyed |
| Do behavior rates cluster beyond task/model composition? | Label or residual permutation in justified strata, on a fixed graph | Label calibration, signal variance and exchangeability |
| Does apparent isolation exceed opportunity? | Membership/time-at-risk conditioned contact model | Actual membership and delivery eligibility required; coauthorship is insufficient |

These options are not current features. A null should be rejected if it creates impossible communications, even if it produces striking z-scores. A role-conditioned null may also condition away the mechanism of interest; state which variation the question intends to retain.

Authored-message normalization controls one kind of volume, not opportunity to receive information. `coactive_room_other_message_count` means that an agent authored at least once in a room and counts others' messages there during the imported scope. It does not measure membership duration, reads or scheduler availability. Rates per authored message can exceed one for multi-recipient mention events; regex-positive message proportions cannot.

Spectral observables require an authored-message denominator for every node. For a referenced nonauthor, `available=false` and `missing_signal_nodes` preserve the unknown value. The optional `induced_author_subgraph` recomputes the operator after excluding unmeasured nodes; it is a **different selected graph**, not an imputed full-graph result. Selection can remove the apparent bridge being investigated. Zero regex hits for an observed author means zero retained hits, not absence of the behavior. Calibration, false positives, quotations, boilerplate and unsampled model labels require separate evaluation; Laya/Jev judgments are not automatically included in these spectral signals.

## 4. Windows, changing populations and measurement comparisons

The window search currently considers nonempty UTC-aligned room windows, defaults to 60-minute width/stride, and analyzes the earliest windows up to its cap. `windows_truncated` and the scope record must accompany results. Empty export periods are not inserted as zero-behavior controls. Default support is at least 12 authored messages and five relevant events, with feature-specific author floors and observed-zero rate comparators allowed.

The five features are normalized incoming concentration, weighted directed reciprocity, static bridge dependence, adjacent lexical recurrence rate and exact shared-URL reference rate. Default absolute-difference thresholds are .15, .25, .15, .03 and .03 respectively. A shared URL establishes citation recurrence, not independent evidence or reading.

Comparators are nonoverlapping windows in the same room within 24 hours, selected by log message-count ratio, active-author count and author-identity overlap. Goals, models, roles, task difficulty, external events and membership are not matched. Ranking all scanned contrasts creates selection bias; scan counts are exported. Half/original/double-width checks reuse evidence, and widened overlaps are flagged. The resulting `robustness_status` is sensitivity evidence, not a replication or causal control.

Across time, first distinguish **the signal changed**, **the graph changed**, and **the measured population changed**. A spectrum can change because one quoted name introduced an extra node. Same agent IDs do not imply the same task or information opportunity. Compare raw counts and extraction failures before proposing a social transition.

For a future longitudinal analysis:

1. Freeze edge semantics, signal units, detector version, inclusion rule and windows before confirmatory measurement; preserve both full-scope and common-author results.
2. Analyze a fixed reference graph with changing measured signals when the question concerns signal movement. Analyze changing graphs with a fixed signal when the question concerns structure. Report the mixed comparison separately; it changes both operands of $x^\top Lx/\lVert x\rVert^2$.
3. Compare invariant subspace energies, projectors or smooth spectral filters rather than “mode 2 coordinates.” Small spectral gaps can make subspaces sensitive to perturbation. [von Luxburg, perturbation discussion](https://arxiv.org/abs/0711.0189).
4. Keep component-level and isolate summaries visible. Do not zero-pad missing outcomes merely to align matrices. Restricting to common authors changes the target population and can create survivor selection.
5. Choose candidate thresholds in discovery data, then test on independent tasks, time blocks or experiment networks. Construct every proposed online trigger from its available past; future-window edges would leak information.

The code does not currently implement this longitudinal pipeline. Eigenvalue distributions, heat traces or aligned projector comparisons would also require explicit population-size, isolate and graph-construction conventions; an attractive embedding is not sufficient validation.

## 5. Operational hypotheses worth testing

These are proposed discriminating predictions, not discoveries or claims of novelty. Source adjudication must establish a relevant incident before attaching one to a stored behavior. Each predicts observable actions and retains a competing explanation.

| Proposed mechanism | Prediction and discriminating experiment | What would weaken it |
|---|---|---|
| Temporal bottleneck limits correction spread | Hold aggregate contacts and evidence fixed, vary whether the cross-group relay occurs before or after downstream verdicts; measure eligible deliveries, correct subsequent use and final accuracy | Similar correction use despite removed time-respecting opportunity; improvement only from extra decision time |
| Coordination depends on an accountable owner rather than a central agent's name | Keep roster/task/information fixed; randomize an explicit acknowledgment-and-handoff obligation versus an equally salient neutral message, optionally randomize the owner | Naming frequency changes without obligation completion; tool availability explains completion |
| Source-preserving relay protects complementary evidence | With independently assigned private facts, vary a relay obligation or provenance-preserving tool affordance while holding source content and traffic budget fixed | More attachments but unchanged exact integration; free-text transmission already supplies the information |
| Shared task language mimics contagion | Compare source exposure with equal task context and a blinded semantic outcome; vary delivery while keeping shared prompts fixed | Lexical similarity persists without source opportunity and no source-specific use is observed |
| Apparently central nodes are replaceable under an alternative route | Randomize removal/reassignment of a prespecified relay role and presence of a feasible alternate route; score task outcomes plus realized eligible paths | Replacement succeeds without the predicted route, or only resource access explains failure |

A degree-balanced topology comparison can help distinguish route placement from total contact opportunity, but “degree-balanced” is not a complete intervention description. Tool fanout, recipient selection, latency, turn scheduling and token budgets also determine exposure. An unconstrained graph with more edges may not improve a task that rarely exchanges useful information. Conversely, high-frequency signal energy might mark an informed dissenter, not a fault to suppress.

The smallest useful next study should isolate one such distinction, use a task with verified information complementarity and a supported nonsaturated outcome, and predeclare the manipulation checks. Checks describe whether the proposed mechanism was engaged; do not exclude noncompliant networks from the primary randomized contrast. A failed manipulation is a result about this procedure's ability to induce exposure, not evidence against every form of the social theory.

## 6. Causal network estimands and fidelity

Let $G$ be an assigned interaction regime, $Z$ a vector of assigned private-context interventions, and $Y_i(G,Z)$ an agent outcome. Within-network interference is expected: another agent's intervention can change $Y_i$. Unit-level direct and spillover effects require a prespecified exposure mapping, assignment probabilities and contrasts with support. The general-interference framework separates these design, exposure and estimand commitments. [Aronow and Samii, *Estimating Average Causal Effects Under General Interference*](https://arxiv.org/abs/1305.6156v4).

For the current factorial wind tunnels, the simpler estimand is a **whole-network intention-to-treat effect** on the prespecified network outcome $\bar Y$. For example, with topology $g$ and focal context $z\in\{0,1\}$,

\[
\tau_Z=\tfrac12\sum_{g\in\{\mathrm{ring,complete}\}}
\big[E\bar Y(g,1)-E\bar Y(g,0)\big].
\]

The topology contrast averages over the two assigned contexts; a separate interaction contrast asks whether context effects differ by topology. This is a bundled topology regime effect, not an effect of “degree alone” or a Laplacian eigenvalue. One independent network is the replication unit. Four agents in one network do not supply four independent replications. Fresh seeds, isolated state and fixed protocols help define the experiment but do not guarantee exchangeability, stable backend behavior or transport to another harness/model.

Realized message counts, graph metrics and fragment delivery are post-assignment outcomes. Conditioning on them can select different kinds of networks across arms. A statement such as “the reminder helped by diffusion” needs more than favorable primary outcomes plus a changed graph. Prespecified mediator measurements and a discriminating manipulation, or stronger explicitly justified identification assumptions, are needed. A private prompt insertion is an assigned context change; its intended interpretation as a planted thought does not provide access to latent cognition.

Current live studies provide useful limits. The noisy-provenance task had sparse realized communication; the complementary-information pilot retained an all-zero accuracy outcome despite recorded unicast actions. Neither establishes a topology mechanism. Exact modular accuracy, valid submission, canonical attachment coverage, source-preserving relay and latent knowledge are different variables. Canonical coverage is an auditable host record; free text may convey facts without attachments, and receipt alone cannot establish integration. The existing [pilot audit](pilot-review.md) and retained research report contain the numerical results and replay evidence; their outcomes must not be redefined after seeing these floors.

An environment can faithfully implement assigned topology and action semantics while poorly recreating a historical episode's incentives, information, memories, tools or time pressure. Mechanistic analogues test whether a proposed process *can* occur under specified conditions; they do not retroactively identify why an AI Village episode happened. Preserve original observation claims, invented analogue elements, unavailable capabilities and rejected environment fits. Raise fidelity selectively around the mechanism being tested rather than assuming a larger simulator is more valid.

## 7. Research-agent contract for graph investigations

An investigator should return the source/window/projection IDs, observed feature and comparator, extraction version, denominators/missingness, plausible ordinary explanations, a proposed mechanism, observable prediction, falsifier, and minimum environment capabilities. A skeptic should inspect both selected and ordinary-window messages, verify the edge arrow, and actively seek activity, role, alias, task and temporal-order alternatives. A methodologist should refuse to convert selected graph contrasts or permutation tails into causal effect estimates.

Keep theory status separate from measurement status: `observational_candidate`, `experiment_proposed`, `bounded_experimental_support`, `conflicting_or_inconclusive`, and `replication_pending` express different evidence states. These labels are recommended semantics, not a new schema requirement. Record failed manipulation, floor/ceiling outcomes, unsupported capabilities and counterexamples alongside positive contrasts. Proposed spectral dimensions and future graph methods belong in the method library; verified source facts and executed randomized results belong in their own evidence records.

The current mathematical foundation supports transparent exploratory screening and inspectable signals. Directed temporal exposure models, calibrated semantic outcomes, participation-aware nulls, longitudinal invariants and identified mediation are future research choices. Their inclusion should follow the behaviors and measurement gaps we actually encounter.

## Primary references used

1. [von Luxburg (2007), *A Tutorial on Spectral Clustering*](https://arxiv.org/abs/0711.0189): graph operator conventions and spectral perturbation; Statistics and Computing 17(4).
2. [Shuman et al. (2013 version), *The Emerging Field of Signal Processing on Graphs*](https://arxiv.org/abs/1211.0053v2): graph spectral signal processing; related IEEE Signal Processing Magazine article.
3. [Chung (2005), *Laplacians and the Cheeger Inequality for Directed Graphs*](https://people.cs.umass.edu/~mahadeva/cs791bb/reading/dichee.pdf): original paper in an academic-hosted copy; directed stationary-flow operator.
4. [Belkin and Niyogi, *Convergence of Laplacian Eigenmaps*, NIPS 2006 proceedings](https://proceedings.neurips.cc/paper/2006/file/5848ad959570f87753a60ce8be1567f3-Paper.pdf): convergence concerns suitably constructed point-cloud operators under specified manifold, sampling and scaling assumptions. Agent mention counts supply none of those assumptions; a graph eigensolver alone does not establish an LBO approximation.
5. [Fosdick et al., *Configuring Random Graph Models with Fixed Degree Sequences*](https://arxiv.org/abs/1608.00607): explicit reference-graph space and sampling choices.
6. [Holme and Saramäki, *Temporal Networks*](https://arxiv.org/abs/1108.1780): time-respecting contacts and the limits of static aggregation.
7. [Aronow and Samii (2017; arXiv v4 2018), *Estimating Average Causal Effects Under General Interference*](https://arxiv.org/abs/1305.6156v4): assignment design, exposure mappings and network causal estimands; Annals of Applied Statistics 11(4).

Literature motivates available mathematics; it does not validate the lab's detector labels or empirical claims. Code descriptions above come from the named local modules. Hypotheses and proposed extensions are explicitly untested here.
