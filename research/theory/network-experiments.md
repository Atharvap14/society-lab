# Causal experiments on communicating agent societies

The second executable environment asks how agents combine evidence whose apparent multiplicity exceeds its original-source multiplicity. Four agents receive four report IDs backed by three independently sampled binary sensors. Two report IDs are copies of one measurement, with the same error. Sensor holders are randomly permuted, and the hidden truth is scored in code. Real-world distinct sources may remain correlated; independence in this environment is an explicit generation rule rather than a general inference from source IDs.

## What the experiment identifies

Randomize entire networks to crossed communication topologies and context treatments. The first implementation supports ring, star and complete undirected direct-message graphs, plus custom graphs for environment checks. Context conditions are no insertion, a neutral note, and a private reminder to check original source IDs and avoid treating duplicate reports as independent observations. The focal recipient is fixed before execution. In a star this recipient is the hub, so an interaction may concern recipient position as well as communication structure.

The unit is one independently reset network run. Four agents, twelve decisions or many exchanged messages do not constitute four or twelve randomized samples. Within-network interference is expected and included in the network-level intention-to-treat effect. Cross-network sharing, persistent memory or shared mutable tools would violate the execution assumptions.

The primary outcome is mean verdict accuracy against the hidden truth. An absent verdict contributes zero, and completion is also reported separately. Agreement, persuasive rationale and a high confidence statement are not correctness. Final verdicts cannot be revised. Evidence exposure is captured at submission; information received later cannot explain the earlier decision.

With the default factors, the preregistered comparisons are a source reminder versus placebo, averaged equally over topology, and complete versus ring communication, averaged equally over context. They are two-sided: null effects and harm remain valid results. Holm-adjusted p-values control the primary contrast family. Conditional randomization tests permute context labels within topology, or topology labels within context, retaining factorial cell counts. Permuting all labels indiscriminately would fail to preserve this design. Within-topology contrasts are exploratory heterogeneity analyses, not evidence of mediation.

## What is controlled and what is allowed to change

All topologies have the same subjects, scheduler rule, maximal total action budget and per-subject message cap. Source noise, report-copy multiplicity and the assignment distribution are fixed. Ring, star and complete graphs necessarily differ in degree, neighbor choices and path length. These differences change information opportunity and are part of the topology treatment, not a nuisance that can be removed by asserting equal budgets. Realized message count and evidence exposure are post-treatment variables; conditioning on them can remove pathways or introduce selection bias.

Report inspection reveals only the subject's assigned report. Agents can pass a report they have seen to a permitted neighbor. The attachment preserves the original source ID, signal and transmission lineage, including repeated relay paths. Unsupported free-text claims are possible, but the tool cannot manufacture a sensor report. This is a boundary condition: the task does not evaluate forgery-resistant provenance in an adversarial environment.

Private thought planting means adding supported text to a specified recipient's observable context before its first decision, then retaining it within that run. It does not assert access to hidden reasoning or changes to an inaccessible belief. A neutral note helps control for additional context but is not guaranteed inert. Word counts are recorded; equal whitespace length would not ensure equal model token count or semantic load.

## Uncertainty and replication

The main interval is a conservative bounded Hoeffding interval for independent run-level outcomes. A within-cell percentile bootstrap is also reported, with the warning that small samples and ceilings can collapse bootstrap intervals. Intervals describe the stated assumptions; they do not prove model stability, eliminate every confound or validate transport to the Village.

The environment seed controls sensors, holder permutation and scheduling. It does not control stochastic hosted-model sampling. Pin requested model, harness version and generation settings, record response metadata, and randomize run order to mitigate time drift. Frozen local protocol and code fingerprints are inspectable registration artifacts, not a public preregistration registry. Transport failures stop estimation and preserve incomplete records. Invalid model actions consume budget and remain behavioral outcomes.

Replications can hold the protocol fixed and generate disjoint environment seeds. Cross-model, cross-harness, cross-task and larger-network studies require explicitly different protocols. Selecting a favorable wording or topology after a pilot requires fresh confirmatory data. A scripted policy's deduplication response is a simulation assumption; offline tests validate execution mechanics and cannot establish how LLM agents behave.

## Further questions the framework leaves open

- Randomize source-copy multiplicity while holding original information fixed to estimate an evidence-repetition effect.
- Randomize the treated recipient or treatment saturation to distinguish hub-specific, direct and spillover effects under a defined exposure mapping.
- Cross message delays and bandwidth with topology to distinguish communication bottlenecks from degree effects.
- Randomize generic caution versus a provenance-specific reminder to separate content-specific effects from increased deliberation.
- Introduce strategic reporting, conflicting incentives or fallible provenance metadata in new validated environments.
- Compare observations with graph-based exposure predictions on held-out incidents, then test those predictions with prospective randomized runs.

These are proposed designs, not implemented capabilities or observed discoveries. The API should grow when a behavior requires one of them, with independent environment validation and a new frozen protocol.
