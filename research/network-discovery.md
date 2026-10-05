# From graph patterns to research leads

`swarm_lab.graph_discovery.discover_graph_leads` screens room-scoped temporal windows and produces leads for an investigator to inspect. Each lead retains source message IDs, file/line provenance, a nearby comparison window, support counts, activity denominators, alternative explanations, and sensitivity to window width. It does not certify a new behavior, infer psychological properties, or identify a network effect.

```python
result = discover_graph_leads(
    messages, agents,
    window_minutes=60, stride_minutes=None,
    min_messages=12, min_edge_events=5,
    max_leads=12, seed=42, max_windows=120,
)
```

The return value contains `windows`, `leads`, `evidence_index`, `scope`, `configuration`, `selection`, and limitations. Inputs are limited to 10,000 scoped messages. The default stride is one window width; overlapping search windows can be explicitly requested. Nonempty windows align to UTC; unrecorded periods are not invented as zero-behavior controls. A window cap retains the earliest chronological windows and reports truncation.

## What is screened

| Feature | Instrument | Quantity and limitation |
| --- | --- | --- |
| Incoming concentration | Recorded exact-name mention events | Incoming HHI normalized to the number of agents present or referenced. Roles, alias matching and inactive referenced targets matter. |
| Reciprocity | Recorded directed mention events | Sum of reverse-tie minimum weights divided by event count. Reciprocal naming does not establish agreement or delivery. |
| Bridge dependence | Recorded directed mention graph | Maximum fraction of reachable ordered pairs lost after node removal, excluding pairs involving the removed node as an endpoint. This changes a representation, not an agent environment. |
| Lexical recurrence rate | Inferred adjacent cross-agent word overlap | Recurrence events per authored agent message. Shared tasks and boilerplate are alternatives to transmission. |
| Shared-reference rate | Recorded exact URL references | References to URLs used by at least two authors, per authored message. This proves citation only, not reading, copying, endorsement, or source-to-agent lineage. |

Observed reply-pointer edges remain available in window summaries, separately from mentions. The current export has few or no usable reply pointers. Inferred proximity is retained as its own descriptive channel; it is not pooled into a mention graph to fabricate density or reciprocity. Static path metrics can include a path whose edge order makes actual communication impossible. [Holme and Saramäki, *Temporal Networks*](https://arxiv.org/abs/1108.1780).

Source-lineage claims require additional observations: document versions, author/tool traces, delivery or read records, and resource content at the relevant time. The current graph cannot reconstruct those from equal URLs or lexical overlap.

## Support and comparison policy

The default minimum is 12 authored agent messages and five relevant relational events. Concentration and bridge features require at least three authors; other features require two. A genuine zero-event rate can supply a comparison when a populated window has enough observed message activity, but cannot itself become an event-supported lead. Bridge search is bounded to 128 nodes. None of these thresholds are calibrated error guarantees.

Comparisons must be in the same room, nonoverlapping, within 24 hours, and eligible for the feature. Matching minimizes the absolute log authored-message-count ratio, active-author-count difference, and agent identity mismatch. It uses no feature value to choose the comparison, avoiding an explicit search for the most extreme contrast. It still does not balance goals, models, roles, human prompts, external events, room membership, reading, or task difficulty. Call these **activity-matched comparison windows**, not causal controls or randomized counterfactuals.

Fixed minimum descriptive differences screen the five features; absolute differences rank leads. Reverse contrasts are deduplicated. Search counts are stored both overall and per feature. A lead's magnitude is selected from a search and is not an unbiased estimated effect; no p-value or false-discovery guarantee is produced. The investigator should inspect ordinary windows and all retained message IDs before proposing a mechanism.

## Window sensitivity

For each retained lead, centered windows of half, original, and double width are reanalyzed around both compared periods. Support, feature values, focus-agent consistency, evidence IDs, and difference direction are recorded. If widened windows overlap, their directional comparison is explicitly ineligible. Reused messages are sensitivity evidence, not independent replication. A consistency label needs at least two supported, nonoverlapping widths with the same direction; it cannot rescue a confounded comparison.

Boundary cuts can remove a reply or reverse tie, so an apparently changing network may be a window artifact. The module neither adjusts a hypothesis until it survives nor treats every retained motif as novelty. A genuinely new semantic behavior remains an open finding for the investigator and skeptic, supported by source text and adjudicated counterexamples.

## Optional graph-signal math

`graph_signal_summary(projection, signal, cutoff=.5)` accepts a separately measured finite signal on every node. Missing values are rejected; the function does not fill absent measurements with zeros or center the signal. It uses the normalized graph Laplacian of `S=(A+A.T)/2`; directed observability metrics remain directed.

For orthonormal modes `u_k` with eigenvalues `λ_k`, the coefficient is `u_k.T x`, energy is its square, and Rayleigh smoothness is `Σ λ_k (u_k.T x)^2 / ||x||²`. Energy is grouped by equal eigenvalues, so changing eigenvector signs or rotating a repeated eigenspace does not change the reported group energy. Positive low-frequency energy uses a fixed eigenvalue cutoff and excludes the null space. Zero or pure-null signals yield an undefined positive-frequency fraction. Disconnected components and isolates make null energy difficult to interpret. This implements graph-signal descriptors of supplied measurements, following the spectral construction described by [Shuman et al., *Signal Processing on Graphs*](https://arxiv.org/abs/1211.0053).

The user's intended meaning of LBO remains provisional. A finite graph-Laplacian basis has not been established as a continuous-manifold Laplace–Beltrami basis. Smoothness is not a mathematical identification of contagion, influence, shared beliefs, or psychology.

## Bounded Village check

The retained April 7, 2025 window contains 273 exported messages in one room, including many human messages. Three populated hourly windows contained 50, 51 and 20 authored agent messages and three, four and two mention events. The default five-event threshold returns no supported graph leads.

For an explicitly lower-support inspection with `min_edge_events=3`, 11 feature/window comparisons produced two deduplicated leads in about three seconds: incoming concentration differed by 0.389 and bridge dependence by −0.5. Both were marked **insufficient or window sensitive**: half-width windows lacked support, while double-width comparisons overlapped. These are sparse examples of why a scalar graph metric should not become a behavior claim.

The retained source IDs include `eea10452-d426-4417-a288-d74da2729fcb`, `3b313e2d-48b5-4cfc-8df7-ef40ca2160aa`, `4e58f17e-9bb7-4036-823d-b224bbe59d06`, and `8960562e-20d3-4f29-9c5b-531c77318f4c`; comparison evidence includes `280ee604-fcfc-41cd-8733-2200576d7997` and `3e71b080-e4c2-449d-bde0-c99c1d729cc2`. Inspection shows role/activity reports, suggestions to involve a paused participant, model-upgrade discussion, and document sharing. Human questions and changing task topics are plausible alternatives; none of these messages demonstrates information mediation, leadership, or a causal network effect.

The complete diagnostic is `.runtime/village-graph-leads.json`, with file/line references into the local gz source. Ten tests cover directed reachability, matched evidence, overlap warnings, sparse support, censoring, source-reference limitations, repeated-eigenspace invariance and the bounded real-data workflow. No paid calls, training, or additional corpus download were used.

## Handoff to causal research

An investigator should propose several semantic explanations and identify counterexamples in the source, while a separate skeptic checks detection artifacts and omitted contexts. If a defensible phenomenon remains, freeze its measurement and estimand before simulator runs. A topology manipulation, private thought/context intervention, delivery delay, resource-availability change, or task-role change can then be tested as a separate treatment, with whole-society replication units where agents interact. Graph selection and observational comparisons do not substitute for that experiment.
