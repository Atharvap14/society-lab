# Selected-lead name-extraction sensitivity: bounded plan

Status: proposed implementation, not an executed sensitivity analysis. This document records read-only inspection of the current code and pinned discovery. It proposes no paid model calls, historical-record edits, new discovery selection, or behavioral relabeling.

## Question and fixed source

For an already selected graph lead, how much does its signed difference between the originally matched windows change when the mention instrument admits an explicit short-name allowlist and/or a conservative Unicode shadow?

The target is the selected contrast, not a whole-week graph statistic. A change in whole-week connectivity or reciprocity motivates this audit but cannot determine the direction, support, or interpretation of any local lead.

The inspected source is discovery-3d29f6c7f419, version 3, bound to dataset-5d2eef17db31, version 1. The discovery's graph_search uses windowed-network-leads-v1. Read-only SQLite inspection verified these registered object hashes using the Store JSON serializer, including UTF-8:

- Discovery: 32a06644e6fc1d83c42141b5640a092ac8d9d09bb82df171d779318fd535d403.
- Dataset: 4351ceeb788cc000b6e288927299f20d68095e9a449a47bb6cef5e0791cc5c41.
- Graph-search source fingerprint: 3f7818caa82afc324d777b2060672af21aa40a6ac56cba89f0cfbb7f834ddc75.

Object hashes, graph-search fingerprints, per-window network fingerprints, direct content hashes, and binary code hashes have different purposes and serializers. A future audit must label them separately and validate the appropriate one; it must not repair or reseal a mismatch.

The search used all 588 retained messages, one room, and 12 nonempty windows. It screened 39 feature-window comparisons, produced 16 screening candidates, and returned 11 deduplicated leads. The feature counts screened were incoming concentration 6, reciprocity 6, bridge dependence 6, lexical recurrence 11, and shared reference 10. All 11 retained leads depend on mention extraction: four incoming, three reciprocity, and four bridge leads. No lexical or URL lead was retained.

The 408-agent-authored-message whole-week sensitivity packet is a different input from this 588-message discovery. Human rows must remain in window reconstruction: they affect which messages are adjacent in the lexical instrument. The agent graph still excludes human-source interaction events.

## Actual feature contracts

These definitions come from [graph_discovery.py](../../swarm_lab/graph_discovery.py), [network.py](../../swarm_lab/network.py), and [discovery.py](../../swarm_lab/discovery.py).

| Feature | Current definition | Name sensitivity and required decomposition |
|---|---|---|
| Incoming concentration | With total mention events T, incoming strengths s_i, and n projection nodes: HHI = sum((s_i/T)^2); normalized concentration C = (HHI - 1/n)/(1 - 1/n). Undefined when T = 0 or n <= 1. | Directly sensitive to targets, event counts, and the node universe. Export T, n, raw HHI, each incoming strength, and C. |
| Directed reciprocity | Weighted reciprocity R = sum over directed edges of min(w_ij, w_ji) / T. Both orientations contribute to the numerator. Undefined when T = 0. | Directly sensitive. Export numerator, T, edge weights, and R. Do not substitute binary reciprocity. |
| Bridge dependence | Maximum over node removals of the fraction of previously reachable ordered pairs lost, excluding pairs containing the removed node as an endpoint. Directed, static, unweighted reachability; bounded to 128 nodes. | Directly sensitive. Export the original reachable-pair count and each node's eligible/lost counts and fraction. This is deletion from a representation, not intervention on an agent. |
| Lexical recurrence rate | Adjacent cross-agent lexical-recurrence event count divided by agent-authored message count. The previous message in the room matters; the heuristic uses the existing five-minute and token-overlap criteria. | Not sensitive to a name-only change. Use the unmodified original messages, speaker IDs, ordering, and token extraction as a negative control. |
| Shared reference rate | For each exact URL cited by at least two distinct agent authors, count its distinct citing message IDs; sum across qualifying URLs and divide by agent-authored message count. | Not sensitive to a name-only change. One message can contribute to multiple shared URLs, so the rate can exceed one. Do not replace the numerator with distinct URLs or deduplicated evidence IDs. |

The native network node universe is agent authors observed in that window plus accepted agent-source targets across the network's projections. Referenced targets need not be authors, present readers, or current members. Consequently, “inactive referenced target” means no authored message in this retained window; it does not establish inactivity or lack of exposure.

Incoming and bridge focus IDs are deterministic maxima with ID-based tie resolution. A change in the displayed focus is not necessarily a change in the unique maximum, and is not a leadership finding. Record all tied maxima alongside the legacy focus ID.

## Freeze the selected windows and matching

Original configuration: width 60 minutes, stride 60 minutes, minimum 12 agent-authored messages, minimum 5 feature events, maximum 12 leads, maximum 120 windows, seed 42. Windows are room-scoped, UTC-epoch-aligned, half-open intervals [start, end), ordered chronologically. Only windows containing retained messages are generated; a missing export period is not an observed zero.

Support requires a numeric feature value, at least 12 agent-authored messages, and at least three authors for incoming/bridge or two for other features. Ordinary zero-event rate windows can be comparators, but an emitted candidate still needs five events.

The comparator is the supported window for that feature in the same room, nonoverlapping, with starts within 24 hours, minimizing:

    abs(log(M_candidate / M_comparator))
    + abs(N_candidate - N_comparator) / max(N_candidate, N_comparator)
    + 1 - Jaccard(active-author IDs)

Ties use comparator window ID. This matching does not control tasks, goals, models, roles, reading, difficulty, or external events. Selection then thresholds and ranks absolute differences, resolves reverse-pair duplicates, and retains the top leads.

The future sensitivity must preserve the selected IDs, their stored orientation, exact window membership, comparators, matching distances, original ranking, and original support. It must not rerun selection or seek a better comparator under an expanded instrument. A variant that would alter support is recorded as such; the original lead remains a historical selected lead.

The selected leads use six unique windows in room 18a3b2fb-9d2e-4ce7-b9b1-52e09c5408a8. All six contain the same four observed agent authors.

| Window ID | UTC interval, 2025 | All / agent-authored messages | Exact agent mention events |
|---|---|---:|---:|
| window-561db93d169c977d | April 17, 18:00–19:00 | 50 / 33 | 7 |
| window-46201f369829d997 | April 17, 19:00–20:00 | 81 / 42 | 10 |
| window-3a4dd0d6e2db6941 | April 18, 18:00–19:00 | 70 / 45 | 6 |
| window-c700fe3c721fd247 | April 18, 19:00–20:00 | 34 / 31 | 13 |
| window-4dd82e3ac3b0d6e4 | April 22, 18:00–19:00 | 52 / 43 | 10 |
| window-9e914aaef4dc1c17 | April 22, 19:00–20:00 | 62 / 56 | 7 |

The following table preserves candidate-minus-comparator orientation. Abbreviated window labels refer to the dates and hours above.

| Candidate → comparator | Feature and selected lead ID | Registered signed difference |
|---|---|---:|
| Apr 22 18h → Apr 22 19h | bridge; graph-lead-b2c7d08d1c926822 | +1.000000 |
| Same | incoming; graph-lead-9e40b45259d92f7b | +0.335238 |
| Same | reciprocity; graph-lead-4f426033358349af | -0.285714 |
| Apr 18 19h → Apr 17 19h | incoming; graph-lead-c7af8e6e02732836 | +0.637318 |
| Same | bridge; graph-lead-801fea2f65179e17 | -0.500000 |
| Same | reciprocity; graph-lead-80b5f9d23d651c4e | -0.446154 |
| Apr 17 18h → Apr 17 19h | incoming; graph-lead-c470fd489f83b71c | +0.500136 |
| Same | bridge; graph-lead-9936c86cea663602 | -0.500000 |
| Same | reciprocity; graph-lead-b8ea4052d8dee1d9 | -0.314286 |
| Apr 17 19h → Apr 18 18h | bridge; graph-lead-b6596ef27db8ec49 | -0.500000 |
| Same | incoming; graph-lead-c215bcb886221a38 | -0.234074 |

These values are recorded baselines, not newly computed sensitivity results. The three Apr 17 18h→19h leads have the original insufficient_or_window_sensitive robustness label; the others have consistent_in_eligible_nonoverlapping_windows. Preserve those labels. Existing half/original/double-width checks reuse messages and keep comparators fixed; they are not replications. Expanding that width-by-instrument analysis is a separate optional request, with overlapping comparisons explicitly unavailable for direction-consistency claims.

## Measurement variants and source validation

Use the existing [name_eligibility_sensitivity.py](../../swarm_lab/name_eligibility_sensitivity.py) to independently recompute each window's event streams against the pinned roster. Default allowlist is empty and Unicode shadow is disabled unless explicitly requested. The present research request can explicitly supply o1 and o3; neither becomes a default.

Four diagnostic variants are available:

1. Baseline exact: the original minimum-three-character, name-not-ID, case-insensitive boundary regex, self exclusion, one event per message/target.
2. Expanded exact: baseline plus separately labeled, explicitly allowlisted one/two-character roster-name candidates.
3. Unicode baseline: the existing conservative shadow using NFKC, enumerated dash replacements, and whitespace collapse, with original length eligibility retained.
4. Unicode expanded: shadow baseline plus allowlisted short-name shadow candidates.

Do not normalize the text supplied to lexical or URL measurements. Exact events retain original codepoint spans. Shadow events carry normalized-text codepoint spans and explicitly lack an original-offset mapping. Source original text and direct content hash remain available.

Legacy exact collision behavior must replay unchanged. New short-name resolution and shadow collisions remain unknown rather than selecting an identity, including when one colliding roster entry is the author. No fuzzy aliases, semantic name inference, adjudicated identity promotion, or human-source edges enter these graphs. Quotation, model comparison, or historical recollection can match an allowlisted name without addressing that agent.

For each window, verify the full message-ID sequence, record contexts, content/source hashes, room, timestamps, roster fingerprint, and stream summaries. Recompute supplied events rather than trusting appended metadata. Reject unknown IDs, duplicate message/target events, invented spans, and altered source bindings. Preserve explicit source-coordinate policies and candidate statuses.

## Native replay versus fixed-pair control

Two different universe policies are needed and must have separate output fields.

**Registered/native replay.** First reconstruct each original window and run the legacy definition. Require its feature values, support, focus, event evidence, and source fingerprint to agree with the registered descriptor. Failure stops the affected comparison as replay_mismatch; it does not authorize changing a historical record. Then calculate each variant with its declared native per-window universe: observed agent authors plus accepted agent-source targets. Baseline must reproduce the original.

**Fixed-pair diagnostic.** For each of the four frozen ordered pairs, form one common universe from agent authors in either window plus accepted agent-source target IDs across all requested variants in both windows. Keep this universe constant across the eight window/variant graphs in that pair. Avoid importing unrelated whole-week or full-roster nodes. A target observed only in the other paired window may be an isolate in this one; disclose it and its unknown exposure.

This proposed pair policy deliberately excludes human-only target additions. The released [mention_graph_sensitivity.py](../../swarm_lab/mention_graph_sensitivity.py) uses a different, disclosed convention: human-source events are excluded at the graph stage, but their accepted targets can remain in its fixed universe. Reuse its validation and metric concepts, not an undeclared equivalence between these two scopes. Any alternative choice must be a separately named universe policy.

Fixed-universe baseline values may differ from native baseline values. Export that universe-only difference before attributing further differences to event extraction:

- Normalized HHI changes when n changes, even with unchanged strengths and raw HHI. For example, HHI 0.5 gives C = 1/3 at n = 4 and C = 0.375 at n = 5. A shared n controls this mechanical effect within a pair; it does not reproduce the original definition automatically.
- Weighted reciprocity does not change merely by adding isolates. New one-way target events can increase T while leaving the reciprocal numerator unchanged, lowering R without deleting any prior reciprocal interaction.
- Bridge denominators are eligible reachable pairs for each removed node, not all n(n−1) possible pairs. New edges can create eligible pairs and alternate routes. An isolated added node can change availability: two nodes with one directed edge give no eligible endpoint-excluded pairs for either removal, whereas adding a third isolated node makes a valid zero-loss removal available. Preserve undefined versus zero.
- Absent authors have no measured outgoing activity/exposure. Structural zero edges are graph representation zeros; do not turn them into measured zero communication rates or knowledge.

No eigenvector-coordinate comparison, spectral trait interpretation, or replacement of bridge dependence with centrality belongs in this minimal audit. Optional spectrum statistics require their own declared operator and scope; see [graph-math-methods.md](graph-math-methods.md).

## Signed comparison and bounded API proposal

For each lead, feature f, and variant v, report:

    delta_v = f_v(candidate window) - f_v(original comparator)
    change_v = delta_v - delta_baseline

Calculate these separately under native and fixed-pair policies. Include both window levels, counts, decomposition, original support, variant support, evidence-event additions/removals, ambiguity exclusions, and direction categories positive/negative/zero/undefined. Retain full precision; use rounding only for display. Declare a small numerical tolerance for equality separately from the configured screening threshold.

The original thresholds (.15 incoming/bridge, .25 reciprocity, .03 rates) can be displayed as frozen descriptive thresholds. A variant passing one is not automatically “selected,” significant, robust, or a new behavior. Do not take absolute differences before comparison: a sign reversal must remain visible. A difference is unavailable when either window's required feature is undefined; do not impute zero.

A CPU-only pure function is sufficient:

    audit_selected_lead_name_sensitivity(
        messages, agents, graph_search,
        *,
        selected_lead_ids,
        short_name_allowlist=None,
        include_unicode_shadow=False,
        source_refs
    )

The future host wrapper should validate versioned dataset/discovery object hashes before calling it. The function validates the selected IDs, original membership/source fingerprints, instrument/configuration versions, replay, events, and bounds. Suggested output:

- version, read_only, model_calls = 0, exact source pins and code hashes;
- frozen_selection with original lead IDs, orientation, matching and screening metadata;
- window_measurements cached by window ID and variant;
- per_lead registered baseline, native results, fixed-pair results, signed changes, support and availability;
- negative_control_checks, collision/exposure warnings, and unsupported_requests.

Cache the six unique windows: at most 24 requested variant-window event measurements for this source. Native metrics use those 24 graphs; the four fixed-pair controls require at most 32 additional window/variant graph summaries with cached events. These are bounded CPU calculations, not fresh extraction searches. A general first version can cap input at 12 selected leads and 24 unique original windows while honoring the existing message/roster/scan bounds. Keep bridge's 128-node bound; mark it unavailable rather than sampling nodes. If persistence is later added, append a separate sensitivity object referencing exact versions; do not overwrite discovery, promote candidate edges, or revise behavior/theory status.

## Adversarial acceptance tests

1. Replay all registered baseline values, source/evidence IDs, support and focus; altered dataset version, room, timestamp, content, roster, or claimed hash fails binding.
2. Keep candidate-minus-comparator orientation. Equal shifts in both windows leave the contrast unchanged; a one-sided shift and sign reversal remain visible. Whole-week changes with unchanged local contrasts never relabel local leads.
3. Include an end-boundary timestamp only in the following half-open window. Insert a human message between two agent messages: name-graph human events stay excluded while lexical adjacency reflects the original human row.
4. Empty allowlist reproduces exact baseline; duplicate requests/events do not double count. Self names, name-equals-ID, substrings, quotations and historical mentions exercise exclusions or explicitly unverified candidate status.
5. Unicode normalization changes coordinates honestly; normalized roster collisions stay unknown. A fabricated original offset for a shadow event is rejected.
6. Adding an unobserved target changes n but not raw HHI when ties are unchanged; fixed-pair baseline and native baseline remain distinct. Unknown outgoing exposure never becomes a zero rate.
7. Add one-way target events with unchanged reciprocal numerator; separately test the bridge undefined-to-zero isolate case and altered eligible-pair denominators.
8. Variant support below five events or undefined values is retained as unavailable/unsupported without rematching. A changed candidate pool cannot replace the frozen comparator.
9. Lexical and URL negative controls remain exact invariants, including two shared URLs in one message and a rate above one. A name-shadow text accidentally entering either instrument fails the control.
10. Shared windows cached for several leads do not mutate evidence or conflate those dependent leads. Oversized requests fail or return explicit unavailable fields; no silent subsampling.

## Limits and unsupported requests

This is conditional analysis of leads selected from 39 dependent screened comparisons. Reused windows, shared comparators, ranked absolute differences, source adjudication, and instrument choices made after viewing data limit interpretation. Sensitivity is not independent replication, a calibrated mention detector, a confirmatory significance test, or evidence of novelty. A surviving contrast can justify a separately frozen hypothesis on held-out data or a purpose-built experiment; it cannot identify delivery, influence, psychology, or the historical causal mechanism.

New candidate-window searches, re-ranking/rematching, goal matching, alternate width scans, fuzzy identity resolution, inferred reading/exposure, spectral latent traits, and causal effect estimation are outside this minimal API. Record unsupported requests explicitly. A source mismatch, unknown selected ID, missing roster, unsupported instrument version, ambiguous required target, or undefined feature is a reason for a bounded failure or unavailable measurement, not a positive or null behavioral finding.
