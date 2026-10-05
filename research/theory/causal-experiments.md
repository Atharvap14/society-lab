# Causal experiments for agent societies

Working protocol guidance, 4 October 2026. This document sets requirements for interpretable experiments. It does not guarantee removal of unmeasured confounding or external validity.

## Define what is being estimated

Specify the population of environments and agent configurations, treatment assignment, outcome, horizon, experimental unit, and estimand before a confirmatory run. For swarm-level randomization, a simple target is `E[Y_run(treatment) - Y_run(control)]` over the stated distribution of resets and configurations. A model call, message, and agent are usually not independent replicates of a swarm-level intervention.

The initial causal question should be narrow. Example: does a private context insertion asking one agent to verify a completion claim change unsupported group adoption within a fixed horizon? This does not ask whether thought planting generally improves cooperation.

Specify whether treatment includes timing policy, recipient selection, text content, delivery channel, and token cost. If they differ jointly, the estimate concerns the whole package. To isolate content, compare no insertion, a neutral insertion, and the active insertion using a stated length-matching rule and delivery process. Exact length equality is not sufficient to equate semantic disruption.

## Thought insertion as a manipulation

InterWhen monitors intermediate states and applies verifier feedback during a trajectory. It is a reference for timing and feedback, not proof that a arbitrary harness exposes internal reasoning or that feedback identifies a causal mechanism. [InterWhen v3](https://arxiv.org/abs/2602.11202v3).

Our supported manipulation must be stated as an observable operation: insert text into a private message, memory, peer message, tool observation, or supported intermediate inference channel at a defined decision boundary. These are different treatment versions. Record the role assigned to the inserted text; a system message and peer suggestion differ in apparent authority.

Log the requested and actual trigger, eligible state, recipient, text hash, channel, delivery acknowledgement, and timing. If a model ignores the insertion, estimate intention-to-treat first; excluding ignoring agents can create post-treatment selection bias. Compliance is an outcome, not grounds for silently removing a run.

Do not claim to modify an inaccessible latent belief or hidden chain of thought. If a backend cannot perform the requested operation, return an unsupported-capability result. A boundary-level prompt insertion can test context steering without being identical to intervention during token generation.

## Pre-treatment state and causal graph

Enumerate pre-treatment variables: model/version, task, accessible information, memory, role, topology, budgets, tool state, scheduler state, and environmental difficulty. Record common causes that could affect both natural intervention timing and outcomes.

Natural interventions often happen precisely because trouble has begun. Comparing intervened and non-intervened historical episodes is therefore confounded by indication. Replay can assess whether a trigger would have fired; it cannot recover the unobserved untreated future. For causal testing, randomize eligible runs or decision boundaries under a fixed policy.

Mark variables as pre-treatment, mediator, outcome, or measurement artifact. Do not adjust for post-treatment communication volume, tool use, or survival when estimating the total effect unless the estimand explicitly requires it and identification is justified. Do not use the realized future to choose a favorable insertion time.

A graph built from messages is an observed relational graph. A directed acyclic causal graph is a separate hypothesis about variables. Dynamic feedback requires time-indexed variables or another appropriate model; a cyclic message graph is not a causal DAG.

## Randomization, resets, and replication

Randomization should be executable code with recorded allocation probabilities, seed, and assignment artifact. The research agent must not pick an arm after observing an outcome. Choose experimental units large enough to avoid untreated peers silently receiving the treatment through another agent.

Start with independent swarm runs randomized between arms. Block by initial task/configuration where useful. Matched runs from the same initial state may improve precision, but a shared seed does not guarantee identical stochastic LLM trajectories or identical provider behavior.

Reset shared files, tools, calendars, messages, caches, memory, and world state between runs. Separate experiment directories and subject credentials. Verify reset using state hashes or explicit assertions. A transcript checkpoint alone does not recreate an entire model inference or browser state.

Record task variants, random seeds, model snapshot, harness commit, prompt/skill hashes, detector version, environment version, generation settings, token/tool budgets, order and concurrency, timeouts, exclusions, and raw event traces. If exact provider reproducibility is unavailable, say so.

## Interference is part of the question

An insertion delivered to one agent can alter the outcome of other agents. Define the treatment vector `Z` and, when studying agent-level effects, a justified exposure mapping `g_i(Z, network, time)`. Direct, spillover, and group effects are different estimands. [Hudgens and Halloran (2008)](https://pmc.ncbi.nlm.nih.gov/articles/PMC2600548/) and [Aronow and Samii](https://arxiv.org/abs/1305.6156) provide primary foundations for experiments under interference.

Do not assume network exposure depends only on the number of treated neighbors. The relevant route might be a shared artifact, a private channel, a memory, or an asynchronously forwarded message. Estimate whole-run effects when exposure mapping is too uncertain. Randomizing treated proportion or recipient position can probe network mechanisms, but only if assignment probabilities and topology are controlled and recorded.

Runs must not communicate across arms through shared world state. An intervention can itself alter the network. Conditioning on the post-treatment network changes the question and may bias a total-effect estimate.

## Outcomes and evaluators

Prefer executable outcomes: correct artifact, successful state transition, completed dependency, violated resource constraint, or unsupported adoption under a fixed definition. Use LLM judges for constructs requiring semantic interpretation, with a frozen rubric, evidence IDs, abstention, and manually checked calibration samples.

Keep evaluators blind to assignment and expected direction where feasible. Remove treatment labels and arm-specific filenames from evaluator input. A treatment's wording can reveal its arm; record imperfect blinding rather than claim success. The evaluator should not receive the discovery agent's conclusion as ground truth.

Measure behavioral outcomes and task outcomes separately. More evidence requests can be an intervention effect without improving correctness. More cautious language can coexist with unchanged actions. Latency includes harness and scheduling time; distinguish computational cost from behavioral delay.

## Effect estimation and uncertainty

For independently randomized swarm runs, report arm sample sizes, the difference in run-level means, absolute outcomes, and an interval appropriate to the design. Bootstrap entire independent runs or matched blocks, not messages. Randomization-based tests can be useful when assignment is known. Binary outcomes with few observations need appropriately conservative uncertainty; zero observed failures is not zero risk.

A deterministic scripted subject tests instrumentation, treatment delivery, and evaluator plumbing. It does not establish LLM behavior or justify statistical inference merely by changing run IDs. Label it an infrastructure validation. Repeated identical deterministic traces supply no new independent evidence.

Report missing, aborted, and budget-exhausted runs by arm. Use prespecified timeout and failure policies, and intention-to-treat reporting. Arbitrary retries until a preferred effect appears undermine the experiment. Report the minimum practically relevant effect and avoid reading a pilot as a definitive null result.

Multiple hypotheses, outcomes, variants, timings, and recipients create multiple comparisons. Separate exploratory ranking from confirmation; use a declared correction or hierarchical testing strategy when claiming a family of discoveries. Adaptive searches require held-out confirmation or a sequential-valid inference plan. A conventional fixed-sample p-value is not valid simply because the experiment was generated by an agent.

## Automated protocol review

The causal agent should produce a protocol with treatment, controls, estimand, randomization, outcomes, exclusions, budget, falsifiers, assumptions, and sensitivity plan. An independent reviewer should ask whether observed differences could be caused by inconsistent tools, role text, budgets, leaked future facts, unequal resets, evaluator hints, or unrecorded treatment versions.

The machine can reject incomplete protocols and prevent certain known errors. It cannot certify the absence of every confound. Report what is controlled, what is measured, what is assumed, and what is unresolved.

## Minimal confirmatory workflow

1. Freeze the candidate mechanism and extraction rubric after exploratory work.
2. Construct a resettable environment with explicit information boundaries and executable outcome checks.
3. Write and freeze the protocol before arm results are available.
4. Validate instrumentation using deterministic subjects without treating that validation as behavioral evidence.
5. Run a bounded pilot for operational failures; record any resulting protocol changes.
6. Run randomized independent fresh subjects under the revised frozen protocol.
7. Evaluate with assignment masked where feasible; compute results with design-aware code.
8. Inspect failures, sensitivity variants, and contradictory evidence; store all results in the behavior library.

## Scope statement for every result

Use this form: “Under environment/version E, harness/model configuration H, assignment design D, treatment T changed outcome O by estimate X with uncertainty U. This supports claim C within scope S, assuming A; limitations L remain.” Avoid replacing it with “the theory is proven.”
