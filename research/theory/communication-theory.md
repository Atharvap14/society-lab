# Communication in agent societies: an operational research theory

Status: working research framework, 4 October 2026. These are measurement definitions and testable hypotheses, not findings about AI Village. The framework should change when observations contradict it. Attention allocation is outside the current scope.

The [construct-status key](construct-status.md) distinguishes implemented screening, source checks and experimental outcomes from proposed measures below. In particular, the grounding ledger, verified commitment discharge, repair success and memory/norm measures are research definitions; the existing regex/graph fields do not automatically populate them.

## Research object

An agent society is a population of situated agents interacting through messages, tools, shared artifacts, memory, resource rules, and an execution harness. The model alone is not the experimental subject: prompts, accessible context, tools, scheduler, memory policy, and communication channels are part of its effective policy.

A useful episode is a bounded sequence of interactions around a shared referent, goal, dependency, or conflict. Episode boundaries are analytical choices, not naturally occurring ground truth. Store the rule used to create them, their surrounding context, and the amount of missing activity. A conversation room may contain multiple episodes; one episode may span rooms and computer sessions.

The lab distinguishes five objects:

1. **Event:** an observed message, tool action, outcome, memory write, or scheduler transition.
2. **Annotation:** a fallible classification of an event or relationship, with the detector version and evidence.
3. **Pattern:** a repeated temporal or relational structure in annotated events.
4. **Mechanism hypothesis:** an explanation that predicts when the pattern will appear and how a manipulation should change it.
5. **Experimental result:** a comparison under a recorded assignment and measurement protocol.

An anomaly is a search lead. It is neither a diagnosis nor evidence of novelty. A new name is not a new behavioral mechanism.

## Theoretical commitments

### Communication is joint work

Common ground is operationally assessed through what participants have demonstrably established sufficiently for their task, rather than through inaccessible mental states. A successful acknowledgement might establish receipt without establishing referent resolution, acceptance of a proposal, or completion of an action. These distinctions follow the grounding perspective of [Clark and Brennan (1991)](https://web.stanford.edu/~clark/1990s/Clark%2C%20H.H.%20_%20Brennan%2C%20S.E.%20_Grounding%20in%20communication_%201991.pdf).

In this lab, maintain a provisional **grounding ledger**: referent, sender, intended recipients, presentation evidence, receipt evidence, interpretation evidence, agreement evidence, execution evidence. Entries may be unknown. Do not fill missing states from conversational politeness. A participant who did not see a message is not a noncompliant participant.

Hypothesis family: explicit referent checks and repair can improve execution when ambiguity is a binding constraint, but may consume resources or unnecessarily destabilize a settled plan. The outcome is task-sensitive, not universally improved by more conversation.

### A public commitment differs from an intention

Represent a practical commitment as a provisional relation `(debtor, creditor, antecedent, consequent, deadline, scope)`. A plan in private context is not a promise to another agent. A proposal is not an accepted obligation. Completion narration is not discharge without the protocol's required evidence. Social commitments and their maintenance have a formal multiagent foundation; our extraction is an empirical approximation, not an implementation of its full logic. [Telang, Singh, and Yorke-Smith (2021)](https://ojs.aaai.org/index.php/AAAI/article/view/17355).

Record creation, acceptance where relevant, reassignment, cancellation, dispute, deadline change, and verified discharge. Achievement commitments concern bringing about a condition; maintenance commitments concern keeping a condition true. A coordination system can satisfy the former while violating the latter, such as creating an artifact while losing its accessibility.

Hypothesis family: explicit ownership and evidence-backed discharge may reduce unresolved dependencies. It may also discourage flexible assistance or create false confidence in the ledger.

### Repair is a process with observable consequences

A repair episode has at least a trouble signal, a proposed repair, and evidence of subsequent resolution or persistence. Repeating a correction is not necessarily successful repair. Measure whether shared referents, plans, or actions actually changed.

The dynamic-grounding study of multiagent negotiation supplies a useful mechanism-level precedent: local competence can coexist with failed joint plan formation. Its task-specific failure analysis motivates tests of history loss, anchoring, reference tracking, and commitment repair; it does not establish these effects in the Village. [Yao, Zou, and Hawkins (2026)](https://arxiv.org/abs/2605.01750v2).

### Agreement and independent evidence are different quantities

Maintain an **evidence lineage** for a claim: artifact, source, observation method, timestamp, and explicit citation path. Multiple agreeing agents can share one source; different URLs can repeat one primary source. Similar wording does not establish transmission. An asserted link to an artifact does not establish that the agent opened it or that it supports the claim.

Useful states are assertion, reported observation, directly recorded observation, corroboration, contradiction, and unresolved. A consensus count is descriptive. Independent verification is a stronger claim requiring a defined standard and inspection.

### Topology shapes opportunities, not proven influence

Keep distinct graphs:

| Graph | Meaning of an edge | Main qualification |
|---|---|---|
| Delivery graph | A sender's message could reach a recipient under channel rules | Delivery may not imply reading or retention |
| Explicit-reference graph | An event explicitly names or cites another event, agent, or artifact | Citation may be inaccurate |
| Commitment graph | An extracted obligation or dependency connects entities | Extraction can misidentify acceptance or ownership |
| Artifact graph | Events create, read, modify, or verify a shared artifact | Access evidence depends on available tool logs |
| Semantic-similarity graph | Texts or extracted propositions are similar | Neither exposure nor causality is established |
| Candidate causal graph | Variables have hypothesized directed causal relationships | Requires assumptions and an identification strategy |

Network centrality describes position relative to the graph definition. It does not measure leadership, persuasion, or causal importance by itself. Temporal precedence plus similarity is insufficient for a causal edge. Shared goals, a common source, harness-wide prompts, deadlines, and tool failures can explain apparent contagion.

### Memory can transport and transform norms

Memory consolidation can preserve a helpful convention, omit a caveat, or make a temporary assumption look settled. Compare a memory statement with the information available when written and with later uses. Do not label an omission as forgetting if the full accessible memory is unknown.

Hypothesis family: procedural memory improves continuity while unqualified summaries can propagate outdated commitments or unsupported assumptions. Separate compression artifacts, retrieval failures, and agent response to correctly retrieved memory.

### Stability and adaptation can conflict

Plan switching can be productive after new evidence and wasteful without it. Report switching with its trigger and environment change, not only frequency. The group-binary-search study reports excessive switching in its controlled setting, including no direct communication; that motivates a stability hypothesis, not a direct diagnosis of chat-mediated swarm coordination. [Maini, Goldstone, and Tiganj (2026)](https://arxiv.org/abs/2604.02578v2).

### Behavior can be relational and context-dependent

Do not infer a fixed social personality from one episode. A model may coordinate well under one resource regime and poorly under another. Cooperative-profile research motivates asking whether small diagnostics predict later team performance, but our tests must separately establish predictive validity across tasks, models, and harnesses. [Kumar, Bharathwaj, and Jurgens (2026)](https://arxiv.org/abs/2604.20658).

## Measurement vocabulary

These are provisional measures. Each implementation must record its denominator, window, censoring, missingness, and extraction confidence. Empty denominators return unavailable, not zero.

| Construct | Observable measure | Necessary qualification |
|---|---|---|
| Commitment reliability | Verified discharges / evaluable accepted commitments | Define evaluable; report open and censored commitments separately |
| Commitment age | Time from acceptance to discharge or window end | A long commitment may be appropriate for its task |
| Ownership ambiguity | Requests with zero or conflicting extracted owners | Check whether task ownership was implicit elsewhere |
| Grounding gap | Acknowledged proposals without interpretation, agreement, or execution evidence | Missing evidence does not prove misunderstanding |
| Repair latency | Time from trouble signal to verified resolution | Unresolved cases are right-censored; distinguish scheduler wait |
| Repair success | Resolved trouble episodes / evaluable trouble episodes | Fix a resolution criterion before testing |
| Evidence concentration | Share of adopting events traceable to each lineage; effective lineage count `1 / sum(p_j^2)` | Untraced events are unknown, not independent sources |
| Adoption reach | Distinct agents explicitly adopting a proposition / agents exposed under the protocol | Exposure opportunity differs from actual reading |
| Coordination churn | Ownership or plan revisions per eligible decision opportunity | Separate revisions justified by new information |
| Duplicated effort | Multiple independently initiated actions on an overlapping artifact/task without a coordination record | Intentional redundancy can be useful |
| Dependency fragility | Task dependencies with one accessible owner or resource | Graph edges require validation; criticality is task-specific |
| Correction persistence | Later uses of a proposition after an exposed correction | Validate that the correction was accessible and relevant |
| Memory transformation | Changed qualifiers, evidence, or obligations across consolidation | Requires comparable source and memory scope |
| Contribution inequality | Concentration of verified useful actions across agents | Communication volume is not usefulness |

Classifiers should initially detect narrow acts: request, accept, evidence request, challenge, completion claim, ownership transfer, apology or correction, cancellation. Compound constructs require episode context and adjudication. A rule-based backend should identify itself as a baseline; it must not masquerade as Laya, Jev, or a validated learned instrument.

## Candidate hypotheses and falsification

| Candidate hypothesis | Discriminating manipulation | Predicted result | Important rival |
|---|---|---|---|
| Acknowledgement is mistaken for ownership | Hold task facts fixed; privately insert a request to identify owner and deadline | Fewer unresolved dependencies than neutral insertion | Extra context alone improves diligence |
| Repetition increases unsupported adoption | Vary number of repeating agents while holding underlying evidence fixed | Higher adoption with repetition | Additional senders genuinely supply new evidence |
| Reference drift prevents execution | Replace ambiguous artifact references with stable IDs | Fewer actions on the wrong artifact | Improved tool availability explains success |
| Over-repair creates plan churn | Insert a redundant check after a plan is already grounded | More revisions without better task outcomes | The prior plan was not actually grounded |
| A correction dissipates before reaching dependent agents | Vary correction delivery while keeping its factual content fixed | Downstream error depends on exposure paths | Agents saw it but rationally disagreed |
| Memory compression launders uncertainty | Compare qualified and compressed memories under equal task facts | More unsupported certainty or adoption in compressed condition | Length or readability, rather than qualifier loss |
| A nominal reviewer suppresses distributed checking | Add reviewer role; independently vary whether others retain verification responsibility | Less checking by others when responsibility is displaced | Reviewer actually performs efficient division of labor |
| Successful repair diffuses through a hub | Randomize recipient position in a fixed delivery topology | Group recovery differs by position | Centrality correlates with access or budget |

Each hypothesis needs a counterexample search and a condition under which the predicted effect would fail. Words like trust, conformity, culture, hierarchy, and belief should be grounded in defined behavior rather than anthropomorphic interpretation.

## Discovery workflow

1. Sample ordinary episodes alongside detector-triggered or graph-anomalous episodes. Record the selection mechanism. Population prevalence cannot be estimated from an anomaly-enriched sample without accounting for sampling.
2. Give investigators raw evidence and a bounded question. Keep their initial hypotheses independent. Some investigate mechanisms; others inspect logging artifacts, scheduler constraints, and counterexamples.
3. Require every candidate pattern to include exact event IDs, a temporal boundary, operational definition, alternatives, missing data, and a nearest-known-literature comparison.
4. Search for recurrence in different goals, time periods, agent rosters, and harness versions. Also search for near-matches that did not produce the proposed outcome.
5. Create held-out confirmatory data or fresh experiments. If definitions change after seeing those results, label the revised claim exploratory and create a new protocol version.
6. Store positive, null, inconsistent, and failed-reconstruction results. Independent investigators improve coverage; they do not make a conclusion independent if they share the same assumptions or evidence.

The behavior library should preserve hypotheses and disagreements. Progress means a sharper explanation with discriminating tests, not an ever-growing catalog of dramatic names.

## Theory record

A theory entry should contain its current proposition, operational variables, causal diagram or explicit verbal model, predicted direction, boundary conditions, alternatives, source episodes, experiment IDs, null and conflicting results, falsifiers, and transport limits. Useful statuses are candidate, observationally supported, experimentally supported in a named environment, replicated in a named scope, contested, and retired. Do not promote status automatically from a single significant comparison.

## Limits

Village records are naturally evolving observational data. Model updates, goals, access, incentives, prompts, scheduling, and memories can co-vary. Full individual contexts and exact hidden states may be unavailable. Dataset-wide descriptive analysis is valuable but does not identify the effects of interventions by itself. A reconstructed experiment identifies an effect in its constructed system; generalization to the original society remains a separate empirical question.

See [causal-experiments.md](causal-experiments.md) for intervention and inference requirements, [environment-fidelity.md](environment-fidelity.md) for reconstruction, [graph-analysis.md](graph-analysis.md) for spectral methods and null models, [library-contract.md](library-contract.md) for archival requirements, and [sources.md](sources.md) for verified literature status.
