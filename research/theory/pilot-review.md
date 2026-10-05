# Scientific audit of the first live handoff pilot

Reviewed 4 October 2026, Asia/Calcutta. This review uses executed local records, not new model calls. Primary object: `experiment-f8ebb002aa60`; raw report: `.runtime/runs/live-wind-tunnel-02/report.json`; frozen protocol: `protocol-7bd22e67fc4c`; observed behavior: `behavior-82e74a4b472a`.

## What the pilot establishes

Nine real model-driven swarm runs completed in a resettable synthetic inventory handoff world. Private context insertion, constrained actions, an exact publication oracle, run-level assignment, frozen outcome definitions, trace persistence, and effect calculation function end to end. Offline action replay reproduced all nine subject request packets, tool results, final states, and oracle outcomes. The canonical report hash passed, and independently recomputing the saved analysis from run outcomes returned the same analysis. This is evidence of execution integrity, not fresh model replication or historical fidelity.

Correct publication occurred in baseline 3/3, neutral note 1/3, and evidence reminder 3/3. The registered active-versus-neutral contrast is approximately +66.7 percentage points, with 95% Wilson/Newcombe interval approximately -5.9 to +93.9 percentage points and two-sided conditional randomization p=0.4. Each whole swarm run is one experimental unit. The primary result is inconclusive; a beneficial, null, or harmful effect remains compatible with the uncertainty. Active versus baseline showed no observed correctness difference.

Do not conclude that the reminder works, that neutral context causes harm, or that a social mechanism has been discovered. The point estimates and observed trajectories provide candidates for better controlled tests.

## Source observation and experiment fit

The four cited Village messages occur within one room on 2 April 2025 UTC:

| Source ID | Directly observable message content | What remains unverified |
|---|---|---|
| `e6053ef1-67fb-41fb-84ee-1c934bd2f5e9` | Reports checking document permissions, a CAPTCHA obstacle, and an alternative sharing document | Actual permissions, created document, and access outcome |
| `aa9edc51-19e5-4db9-8337-c03c1273fdd2` | Reports platform research and charity selection; identifies later messaging coordination | Research quality and subsequent coordination |
| `0f954e2c-246f-4845-a25a-7680d1933672` | States a plan to wait for a decision-summary draft and then proofread it | Whether the draft became available and proofreading occurred |
| `101d94f4-99ab-476d-9edf-b73059a72c35` | Reports an initial draft, explicitly says remaining updates need another session, and plans incorporation of another agent's work | Artifact edits and later incorporation |

These support explicit completion/pause narration and planned shared-artifact handoffs. They do not establish a false completion claim, erroneous artifact, blind reliance, failure, or novel behavior. In particular, the draft author explicitly qualifies completeness. A compact text screen can lose that qualification and turn routine staged work into an invented failure.

The pilot changes the scientific question. It tests a private verification reminder in a constructed world where an initial artifact may be defective and a prior-shift message says it is ready. It can identify an assigned-context effect in that environment under its assumptions. It does not test whether the original Village handoff occurred, succeeded, or was caused by the hypothesized mechanism. The source episode motivates an analogue; it does not validate it.

The linked theory remains `hypothesis`, with empty replication IDs and generalization unestablished. Calling the behavior `pilot_tested` must not promote the historical mechanism or novelty status. Observation and experiment support need separate scopes.

## What each arm actually did

| Runs | Recorded sequence | Scientific reading |
|---|---|---|
| Neutral `run-0001` | Initially correct artifact; coordinator inspected then published correctly | Successful execution without needing repair |
| Neutral `run-0002`, `run-0003` | Initially defective artifact; builder, and sometimes verifier, inspected; coordinator published at its first turn before repair | Premature publication despite another agent having inspection opportunity; publisher had not inspected |
| Active `run-0004` | Initially correct artifact; coordinator inspected then published | No repair mechanism demonstrated in this run |
| Active `run-0005`, `run-0009` | Coordinator inspected a defect, requested repair, builder repaired, coordinator inspected the new version, then published | An observed check–repair–recheck pathway, not yet an estimated mediator effect |
| Baseline `run-0006`–`run-0008` | Coordinator inspected the initial defect, builder repaired, coordinator later published correctly without inspecting the repaired version | Valid results can arise through delegated repair without final-version reinspection |

In baseline `run-0006`, the coordinator also attempted a repair forbidden to its role. The invalid action was retained, the environment enforced permissions, and the team later succeeded. Successful output does not imply flawless role compliance.

The failed neutral-note teams terminated at publication after three actions. Inspecting observers had no later repair/communication opportunity before that consequence. This is a plausible publication-timing and communication mechanism. It is not evidence that they rationally chose to ignore already-received contradiction: the publisher had not inspected the artifact and may not have received a defect report.

## Inspection measurement needs actor and version

The registered `inspected_publication` flag means that **any agent previously inspected the version that was later published**. It does not require inspection by the coordinator, positive verification, a contradiction message, or the publisher reading such a message.

Registered values were active 3/3, neutral 3/3, baseline 0/3. Therefore an evaluator's statement that active had more registered inspection than neutral is unsupported. Correcting digits alone did not remove this semantic measurement error.

Exploratory trace-derived distinctions are:

- Coordinator inspected some artifact before publication: active 3/3, neutral 1/3, baseline 3/3.
- Coordinator inspected the actual published version: active 3/3, neutral 1/3, baseline 0/3.
- Any agent inspected the published version: active 3/3, neutral 3/3, baseline 0/3—the registered measure.

These distinctions explain why baseline success and a zero inspection flag can coexist: a repair creates a new version. They also explain why faulty publication can have a positive inspection flag: another agent inspected the faulty version. These new measures are post hoc descriptive observations, not preregistered outcomes or a causal mediation analysis.

## Design and scope concerns

The registered design randomizes complete independent swarm runs and resets state, which addresses within-run interference for the group estimand. Unequal initial defects and scheduler orders are chance imbalances in a very small randomization, not automatically systematic confounding. They can nevertheless increase uncertainty and make an apparent pathway depend on opportunity. Baseline has only initially defective worlds; active and neutral each have one initially correct world, while their remaining defect types differ.

Neutral failed runs share builder–verifier–coordinator ordering and publish on the coordinator's first opportunity. A baseline success has the same initial ordering, so order alone does not explain all results. Subsequent scheduling, context response, communication, and stochastic model decisions can jointly matter.

Run execution order was neutral, neutral, neutral, active, active, baseline, baseline, baseline, active under the realized randomized assignment. A single model name and fixed harness do not guarantee provider behavior is stationary over elapsed time; this pilot cannot estimate such drift. Fresh provider sampling seeds were not fixed. A shared environment seed fixes world/scheduler conditions, not model stochasticity.

The control note is a substantive context manipulation. Matching whitespace word count does not make it psychologically inert or tokenizer-equivalent. The primary causal estimand is active note versus this particular neutral note. No observed correctness gain over no insertion was present. Generic caution, recency, action delay, or wording effects remain rivals to evidence-specific steering.

Exact equality of an inventory manifest is a narrow, objectively checked outcome. Transport to document quality, research correctness, open-world tools, long-term memory, alternative models, or network structures is unestablished. The environment cannot reveal inaccessible beliefs or hidden reasoning.

## Failed attempts and amendments

The report generator retains linked incomplete attempts separately from completed behavioral runs. Infrastructure failures are not silently excluded observations or negative behavioral effects. A retry under a newly frozen protocol is a new attempt; it does not alter the completed protocol or its registered outcomes.

`evaluation-bf2fec96c9f4` originally said active had 2/3 correct publications while simultaneously reporting a mean of 1.0. Its original version is retained. A later version marks `numerical_inconsistency_detected`; `evaluation-cb71542a6914` separates code-generated quantities from qualitative commentary. The subsequent actor/version inspection audit shows that digit-free prose can still contradict metric semantics. Both issues belong in the research record.

No trial or outcome has been rewritten by this review. Any additional measurement is explicitly exploratory and trace-derived. The offline report generator should retain original result and object-version IDs and show raw evidence behind its conclusions.

## Separate network pilot

`network_experiment-b215b2b47aef` completed eight independent four-agent networks in a ring/complete × neutral/source-checking context factorial, with two networks per cell. No run ended through budget censoring. Its context contrast in mean network accuracy was -0.125, with conservative bounded 95% interval [-1, 0.835] and Holm-adjusted p≈0.667. Complete versus ring was -0.25, interval [-1, 0.710], Holm-adjusted p≈0.333. The four agents are not independent randomized trials, and the intervals are individual rather than simultaneous.

Focal accuracy was 1.0 in every cell. Realized exchange was sparse: mean sent messages ranged from 0.5 to 1 per network, and verdicts generally had about one independent source available. Assigned topology therefore did not expose a rich collaborative diffusion mechanism in these trajectories. The pilot establishes neither network harm nor a context benefit. Small-sample bootstrap intervals can collapse at ceilings; that is not evidence of precise effects. A useful next world should create real informational complementarity, such as independently held evidence required by the task, while preserving the possibility of failed exchange and negative results. Retain this pilot and its outcome semantics unchanged.

The offline generator also replays all eight recorded network action sequences and recomputes their stored analysis. Both passed on the reviewed execution code. This checks trace integrity; it is not a fresh model replication.

## Fresh-seed shared-artifact replication

`experiment-b46d02ce332c`, registered as `protocol-fad376e6d378`, ran twelve fresh teams with seed namespace 4343 and four teams per arm. Its protocol links to `protocol-7bd22e67fc4c`; task, context wording, outcomes, subject model, and harness are held fixed. The report generator checks that its environment seeds do not overlap the initial pilot and separately replays the recorded actions and recomputes analysis. This is replication across world/scheduler seeds, not across models, tasks, historical episodes, or fixed provider sampling seeds.

Correct publication was active 4/4, neutral 0/4, baseline 3/4. The registered active-versus-neutral risk difference was +1.0, with 95% Wilson/Newcombe interval [0.307, 1.0] and exact two-sided conditional randomization p≈0.0286. This supports a positive effect of the assigned active note versus this particular neutral note in this synthetic setting under the registered assumptions. The original pilot remains inconclusive. The replication was planned after inspecting the initial result; present the studies separately rather than silently pooling them or treating the whole adaptive research program as one untouched test. A collapsed bootstrap interval [1, 1] at boundary outcomes is not certainty.

The exploratory active-versus-baseline difference was +0.25, interval [-0.281, 0.699], p=1.0. Thus improvement over no insertion remains unestablished. A generic-caution control and a neutral-note wording alternative would discriminate specific evidence-checking content from premature continuation/commitment effects more directly than another repetition of the same active-versus-neutral contrast.

All four neutral teams published at the coordinator's first scheduled opportunity without its inspection. All active worlds were initially defective and successfully repaired. Baseline had two initially valid worlds and two missing-entry worlds; one of the defective worlds succeeded after repair and the other failed. These pre-treatment differences are realized chance imbalance, not automatic systematic confounding, and make broad comparisons with baseline harder to interpret.

Registered any-agent inspection of the published version was active 2/4, neutral 2/4, baseline 4/4. Exploratory publisher inspection of any version was active 4/4, neutral 0/4, baseline 3/4; publisher inspection of the published version was active 2/4, neutral 0/4, baseline 3/4. The registered inspection flag is not an identified mediator. Successful active teams sometimes relied on delegated repair confirmation without final-version reinspection.

Baseline replication `run-0001` is different from the neutral first-turn failures: the coordinator had inspected the missing-entry artifact and its final decision packet contained an explicit builder message saying delta was missing and repair was needed, yet it published the uncorrected version. This is observable failure to act on accessible contradiction; it does not identify the latent reason. Active replication `run-0002` also shows stale-version communication after a repair: the coordinator and verifier requested repair based on earlier inspections while the actual artifact had already advanced to version 2. Correct final publication nevertheless followed a builder's confirmation. This suggests a new candidate distinction—version-qualified evidence versus cached inspection narration—but not a demonstrated cause of the treatment effect.

No historical mechanism or generalized social theory is established by this replication. The source pattern is planned handoff language; this synthetic experiment asks about manifest publication under context insertion. Replication can strengthen the latter effect without validating the former theory.

## Smallest discriminating next work

1. **Historical evidence check, no new model experiment:** retrieve the bounded computer sessions and later messages associated with the four source IDs. Establish whether shared-document handoffs and artifact edits actually occurred. If there is no false readiness claim or reliance failure, keep the original pattern as ordinary coordination.
2. **Measurement refinement, no new subjects:** preserve the registered flags, add actor/version-resolved exploratory inspection and defect-report delivery measures, and review the publication decision against the actual coordinator packet. Do not rename the existing metric retrospectively.
3. **Opportunity-controlled content test:** in a new protocol, use the same fixed defective artifact and scheduler block across baseline, current neutral note, evidence reminder, and a matched generic-caution note. Run independent fresh teams and predeclare first-turn publication, coordinator inspection, defect communication, repair opportunity, and final validity. This distinguishes specific checking content from generic delay/caution more directly than simply increasing the original sample.
4. **Claim-reliance test:** cross presence/absence of the prior-shift readiness claim with private evidence-reminder/neutral context in otherwise matched defective worlds. That tests whether the intervention counters a claim-reliance mechanism, rather than a generic inventory-solving effect. No factorial mechanism is identified by the current pilot.

Begin with one narrow comparison that separates the leading rivals; do not commit to a universal society simulator. Replication of the same intervention can improve precision but cannot repair a theory–experiment mismatch by itself. These are proposals, not authorized or already performed new model runs.
