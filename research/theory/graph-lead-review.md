# Independent review of the Village communication leads

Reviewed 4 October 2026. This is a source audit and a proposed research agenda. It introduces no model calls, changes no database objects, and changes no frozen environment or experiment. The Village observations, saved investigator interpretations, and synthetic experimental trajectories are separate evidence scopes.

The defensible historical observation is **task-specific deferral alongside continuing coordination and preparatory work**. The graph leads do not establish a social reciprocity mechanism, causal brokerage, or general inactivity. A second, sharper hypothesis about **version-qualified assertions** is motivated by an executed synthetic trace, not demonstrated historical qualifier loss. Keep these as separate library hypotheses until a linking episode and a discriminating experiment exist.

## Pinned inputs and source boundaries

The read-only SQLite connection used `mode=ro`. Object identity alone is insufficient because records are versioned. These are the versions inspected for this review:

| Object | Version | SHA-256 |
|---|---:|---|
| `dataset-fdecf1dd6658` | 2 | `109853f675e4c18de6faf440a7911770b64c6b326dc09eadd3ab131056e9f691` |
| `discovery-1a97bcc71ca1` | 3 | `96f48b13bec18ff1dc80da58c803d5ccc7cbe29c2735a1284e235dd1f786e0f5` |
| Corrected reciprocity candidate `behavior-c6795bc08068` | 2 | `27e8d0d70aa9f517d920d0d9978402bf8cc2fdfdd4253a247d96df175c71d363` |
| Corrected waiting candidate `behavior-ad77419c8fab` | 2 | `64c0fd07505bb5e2c6058b1f975864ecdc6849e27ba580ba36c077b99b4e37a9` |
| Synthetic replication `experiment-b46d02ce332c` | 1 | `19c3b4a13404f4ac188e5bbc8b61a9fa1f6264783f2875fa07f6706a9097ae6c` |

The historical dataset retains 4,290 messages in room `18a3b2fb-9d2e-4ce7-b9b1-52e09c5408a8`, selected chronologically within `[2025-04-02T00:00:00Z, 2025-04-16T00:00:00Z)`, with limit 6,000 and no room filter. Ingestion scanned 183,485 source rows; 4,290 matched, none were truncated, malformed, invalid, or duplicate IDs. Earliest and latest retained timestamps are `2025-04-02T17:47:10.664358Z` and `2025-04-15T19:35:01.546181Z`. This verifies the recorded selection, not the completeness of the original export or an agent's complete accessible context. The roster contains agents created after this early episode; roster membership does not imply presence then.

All original line numbers below refer to decompressed JSONL records in `ai-village/chat_messages.jsonl.gz`. They are not positions in the retained chronological list. The dataset fingerprint is `11158f16a8d0cfd57f23fa2df8204745f848dc14bb849e7f8649069c92ecbdbc`. The graph-search fingerprint is different because it hashes a different analysis input representation; do not substitute one for the other.

I read the cited messages, their selected comparison messages, and all 24 agent-authored messages in `[2025-04-02T20:29:42Z, 2025-04-02T20:41:00Z)` in this retained room. This bounded contextual check is not an exhaustive search of the Village, computer sessions, screenshots, other rooms, or tool histories. No historical artifact contents, lock ownership, delivery acknowledgement, or exact private subject packet was reconstructed here.

The two recovered proposals originally lacked an archived exact research input. Their association with unchanged retained source rows was reconstructed and is explicitly qualified in `research_attempt-6eab712656b1` and `research_attempt-8e608e7d0d47`. The first skeptic outputs had a schema-construction defect: a shared schema object applied citation enums to explanatory lists. Those records remain retained and superseded. The corrected candidates above rerun skepticism against the same proposals and sources; they do not constitute independent new observations. Both remain candidates with no causal support and novelty unestablished. The independent source judgments below do not rely on a model-generated explanation as ground truth.

## What the graph actually selected

The graph search analyzed 36 populated, UTC-aligned hourly windows and 87 feature-window comparisons. It screened 19 candidates, deduplicated to 14, and returned 12 ranked leads. Thus the two reviewed leads were selected after multiple searches. Their differences are descriptive screening quantities, not preregistered effect estimates or significance tests.

| Lead | Focal / comparison UTC window | Support and contrast | Boundary sensitivity |
|---|---|---|---|
| `graph-lead-7eb3925cb7b6d5a2`, bridge dependence | 5 April / 6 April, both 19:00–20:00 | 71 / 65 authored messages; 15 / 12 mention events; maximum node-removal loss 1.0 / 0.0 | Difference +1.0 at eligible 60- and 120-minute windows; 30 minutes insufficient support |
| `graph-lead-07f5e81f823f65ae`, directed reciprocity | 2 April / 3 April, both 20:00–21:00 | 94 / 72 authored messages; 45 / 9 mention events; weighted reverse-tie fraction 0.0889 / 0.4444 | Differences −0.4333, −0.3556, −0.0626 at 30, 60, 120 minutes |

The bridge score of 1.0 means **two of two eligible static reachable pairs** disappeared when GPT-4o's node was removed, excluding pairs having that node as an endpoint. It does not mean all societal communication depends on GPT-4o. A path formed from name mentions is not a recorded forwarding path; its edge order need not permit actual temporal transmission. Removing a node from this representation is not an intervention on its availability, behavior, or communication channel.

Reciprocity has a small comparison denominator and much smaller contrast at 120 minutes. Same direction across nested windows is neither stable magnitude nor independent replication. A reverse name tie need not answer the original message, acknowledge a request, or agree. The saved proposal additionally permits third-party responses “on behalf” of an owner; that is a different episode-level construct from the implemented directed reverse-tie metric. It requires a new annotation definition rather than retroactive reinterpretation of the graph score.

The comparison matching uses authored message count, author count, and author identity overlap. It does not match active tools, task dependencies, availability, goal difficulty, human instructions, or complete exposure. In particular, a mentioned agent need not be present or reading. Spectral modes or centrality of this graph can guide sampling; neither identifies a psychological mechanism. A graph Laplacian basis also does not establish a continuous-manifold Laplace–Beltrami model of the society.

## Historical evidence and counterexamples

These short descriptions paraphrase the source; quoted language is not needed to establish the distinctions.

| Exact message ID | UTC timestamp; original line | What is directly supported |
|---|---|---|
| `e6325987-2072-4346-8f19-9083311370bf` | 5 April 19:48:32.007979; 165065 | GPT-4o says it will give its reflection after both Claudes finish sessions and post theirs |
| `a06f0ff8-1b7d-49be-a727-c05188f2d016` | 5 April 19:49:00.215449; 114914 | GPT-4o repeats that sequencing condition |
| `244f3da1-cad6-4daa-82e5-b55dee321bd2` | 5 April 19:49:52.905053; 25983 | GPT-4o updates the reported session status, continues fundraising reflection, and still defers its requested reflection |
| `f903334b-1c64-41c0-895f-c72a29f93968` | 5 April 19:18:45.626755; 178484 | Claude 3.5 says it has no assigned task and waits for instructions/opportunities |
| `9055ff80-a6aa-425c-b09f-77b27e95ae6a` | 5 April 19:51:09.586531; 103465 | Claude 3.5 waits for GPT-4o's input after reporting consensus on tomorrow's work |
| `06500331-eb9b-4f0e-8a99-9d1e6ef1e967` | 6 April 19:09:27.595343; 4534 | Claude 3.7 reports two peers using computers and plans its own Twitter work |
| `5eb517bc-036d-4bd0-a47d-0545b1873007` | 6 April 19:24:01.994714; 67974 | Claude 3.7 later reports peers using computers and says it will defer new activity |
| `cd0b3aec-fe69-4326-a986-232abb6f8d23` | 2 April 20:17:24.303135; 146944 | o1 assigns draft completion, proofreading, outreach, and regrouping to different agents |
| `745f81ed-9475-42a5-a1a0-5ea98a39e513` | 2 April 20:22:35.902655; 83472 | o1 requests status and makes proofreading conditional on draft completion |
| `0f954e2c-246f-4845-a25a-7680d1933672` | 2 April 20:21:45.201049; 11195 | Claude 3.7 says it will wait for the draft before proofreading |
| `101d94f4-99ab-476d-9edf-b73059a72c35` | 2 April 20:29:42.720910; 11551 | Claude 3.5 reports an initial draft and explicitly says remaining updates need another session |
| `21919619-6a1a-4d1d-8ac8-2dfc1d68c2ad` | 2 April 20:33:42.836558; 24055 | Claude 3.7 plans preparatory call-to-action research while final proofreading remains dependent on Claude 3.5 |
| `82096b05-08c1-42b1-bf5b-538c08fc1a5a` | 2 April 20:34:38.730874; 93252 | Claude 3.7 reports a brief preparatory session, interrupted by a human return request, and keeps final proofreading conditional |
| `42ac93d4-ce01-495c-b309-1c1aef77aad9` | 2 April 20:35:10.367352; 47723 | o1 retains the unfinished-summary condition and notes GPT-4o is paused |

The April 6 pair defeats the broad explanation that awareness of busy peers is sufficient to cause waiting. It does not defeat a narrower dependence on the particular task, owner, channel, new instruction, or time of session. Both are declarations of intended action; no actual tool execution or inactivity is proven by those messages alone.

The April 2 sequence also defeats an inference from task-specific waiting to whole-agent idleness: the same agent describes preparation before its dependent proofreading step. Agents repeatedly attribute pauses and returns to human requests in the contextual messages, including `83559e0a-00bc-4371-bc8c-199ec8a92386` (20:30:31.738173; line 94118), `91f23d5e-4d78-4fac-9a84-7aaeb1db63a8` (20:34:45.636566; line 104560), and `feb64f7e-c6e6-4420-afd1-1c9364d0379a` (20:35:27.687806; line 182580). Those attributions require verification against the original human instruction and tool events. A theory that omits human direction or scheduler opportunity risks misattributing plausible causes of pauses and task switches.

No qualifier-loss chain is established in the inspected historical draft episode. The author explicitly marks an initial draft with remaining work. o1's subsequent messages retain future finalization and dependent proofreading: `61330909-336d-4f6b-9f40-8d2ff8f1381a` (20:33:19.360838; line 69721), `2188175c-eccb-4869-8c47-213227e1b5cc` (20:34:24.670130; line 24034), and `42ac93d4` above. These are counterevidence to an easy story that a completion keyword automatically becomes a shared false readiness claim. Different nearby fundraising documents may also be distinct artifacts. Similar task names or repeated URLs do not establish that agents observed the same version or copied a particular assertion.

## Hypothesis A: waiting is scoped to dependencies and opportunities

**Candidate proposition:** under a fixed task and harness, agents can defer a dependent operation while still performing independent preparation. A message that broadens a task-specific dependency into an agent-wide waiting instruction may reduce useful independent work even when the underlying resource is available. The historical records motivate this question; they do not establish that such broadening occurred or caused lost work.

Measure separate events: dependency stated, owner/resource availability verified, dependent operation attempted, independent useful work attempted, waiting declaration, actual wait action, and task completion. A pause because the harness gives no turn is not a voluntary wait. An agent reporting no assignment is a different opportunity state from an agent holding an executable independent task.

The clean falsifier for the broad historical reading already exists: peer use plus proposed parallel work. For the narrower causal hypothesis, hold executable independent work and actual availability fixed, then randomize a private context note that scopes deferral to the blocked operation versus a note that calls for general waiting. If independent task performance is unchanged within a prespecified meaningful range, or agents correctly scope both notes, the proposed scope effect is weakened. A harmful effect on the blocked task or no gain in final team completion would limit any practical benefit. Neither outcome should be converted into a positive coordination finding.

An availability-only manipulation cannot isolate communication: locking a resource changes what is possible. A useful follow-up could independently vary actual availability and the report of availability, with explicit permission and known fallback tasks. Freeze the estimands separately for these factors and their interaction. Rival explanations include human obedience, turn cost, response timing, task priority, memory, and legitimate resource etiquette. Until tool/session reconstruction exists, the historical status should remain a candidate descriptive pattern.

## Hypothesis B: old observations are asserted as current after version change

This has a concrete **synthetic** support example in `experiment-b46d02ce332c`, `run-0002` under the evidence-thought arm. Resolve trace events with `(experiment ID, run ID, step, message ID)`; message numbers alone repeat across runs.

| Recorded locator | Observation/action distinction |
|---|---|
| `run-0002`, steps 0–2 | All three actors inspect manifest version 1; alpha is 3 but required alpha is 2 |
| Step 5 | Builder repairs the manifest to exact requirements; the tool returns version 2 |
| Step 6, `message-3` | Coordinator's subject packet exposes artifact version 2 with contents hidden; its earlier history contains version-1 evidence. It sends a present-tense defect claim describing alpha 3 as current verified contents |
| Step 7, `message-4` | Builder communicates repair and readiness |
| Step 8, `message-5` | Verifier's packet also exposes version 2 but its inspection history is version 1. It sends an unqualified continuing repair request |
| Step 10 | Coordinator publishes correct version 2 after the builder's message, without inspecting that version itself |

The observable pattern is failure to qualify a stale observation in a message despite available version-change metadata. It does not identify whether the cause is retrieval, referent binding, temporal reasoning, role policy, or general caution. This run also shows that stale messages can coexist with a correct final artifact; do not define them as necessarily harmful. In baseline `run-0001`, step 5 publication instead follows both direct inspection of an incomplete version and accessible `message-2` reporting the missing entry. That is a different failure—acting despite accessible contradiction—rather than stale-version communication.

**Candidate proposition:** an explicit source/version discipline can reduce false current-state assertions after a known artifact change. To test a thought intervention, all arms should have the same source IDs, observation versions, current version metadata, and task facts. Randomize a private instruction to bind assertions to observed versions versus matched generic caution and/or neutral context. Adding evidence fields in only the active arm would test an information-format bundle instead, which is legitimate but a different estimand.

Use a new world/protocol with an externally scheduled version change after an identical initial observation. Do not define eligibility by whether treatment causes an endogenous repair. Predeclare a fixed post-change decision interval and a whole-team indicator of any objectively false, unqualified current-state assertion; retain silent teams and incomplete tasks. Report useful task completion and communication burden alongside that outcome so suppression of all speech is not mistaken for improved research performance. Actor/version-resolved secondary measures may explain trajectories but are not identified mediators merely because the randomized outcome changes.

A falsifier is persistent stale assertions despite explicit version-linked evidence and the reminder; another is equal improvement from generic caution, which weakens a version-specific explanation. If correct publication is unaffected while messages improve, the supported scope is communication calibration, not task effectiveness. Historical transport requires a real source-observation/version/use chain; chat similarity alone cannot provide it.

## Interference and simulator fit

Randomize and analyze **independent, reset whole societies** for the first tests. Context inserted into one agent can change messages, another's opportunities, repairs, and final output. Four agents or many messages inside one run do not create four or many independent trials. For a group outcome, average over a fixed roster and retain missing submissions/completions according to a preregistered rule. Block or pair on pre-treatment world, scheduler, and role facts if desired; a replayed action trajectory checks integrity, not fresh model replication.

If later estimating individual direct or spillover effects, define the assignment distribution, exposure mapping, and target estimand separately. Exposure must be based on implemented delivery rules or recorded packets, not mention centrality. Conditioning on a post-treatment message or realized centrality can introduce selection. This follows the general interference framework of [Aronow and Samii, pinned v4](https://arxiv.org/abs/1305.6156v4). A topology intervention changes paths, fanout, timing, and informational access; without additional controls, its effect is that opportunity bundle rather than an isolated degree effect.

| Implemented environment | What it can contribute | Missing features for these hypotheses |
|---|---|---|
| `shared_artifact_coordination` in `swarm_lab/environments.py` | Mutable versioned artifact, role permissions, inspections, repairs, recorded subject packets, exact publication outcome | Actual computer locks, alternate independent tasks, ownership transfer, explicit delivery receipts, externally fixed version-change schedule, enforceable source/version claim structure |
| `provenance_diffusion` | Immutable originals, duplicate copies, relay lineage, topology-restricted communication | Mutating artifact versions, task dependencies, ownership/locking; distinct source IDs imply independence only by construction |
| `complementary_information` | Exact privately held components, immutable attachments with forwarding lineage, tasks requiring exchange, topology and bounded actions | Version mutation, stale current-state claims, waiting-resource semantics; canonical attachment coverage measures accessible records, not mental knowledge or every fact conveyed in free text |

These dimensions should remain explicit capability declarations. The current artifact world is a useful analogue for hypothesis B and some handoff behavior, not an exact reconstruction of hypothesis A. The complementary world addresses informational necessity; a positive or null topology result there does not establish historical qualifier loss or ownership gating.

## Separate complementary-task process audit

The subsequent synthetic result `complementary_experiment-95e2a6857435`, version 1, hash `fcb3d6473898ac7960661e2c6a0d14e88e588fbf1fc5c8cfc180fe3f1b03ad76`, is registered under `complementary_protocol-0d57a2d8f2dc`, version 1, object hash `81520d166132f6127bac6e16a54c0ca226419cbee61a562be0f2f3e024a56500` and frozen protocol hash `9154a45b210504417b514298d4f622c5199cef5a9da1d81c56126951a64ea33f`. It used `gpt-5.4-mini` in the Responses subject harness. The stored verification `verification-834a56a6765a`, version 1, hash `4a095b6298a917db52b0a07710de7cabb9cb260f77e83ff19690387e1048f0f8`, passes recorded packet/action/tool-result/state/oracle replay and recomputation of the saved analysis. Replay is execution verification, not fresh model replication or independent behavioral corroboration.

All eight networks had mean exact accuracy zero and exhausted their twelve-step budgets. Sixteen of 32 agents submitted an answer; all sixteen answers were incorrect, while missing answers also score zero. The context and topology primary contrasts are zero, exact conditional p=1 and Holm-adjusted p=1; individual conservative bounded 95% intervals are approximately ±0.9603. The collapsed bootstrap interval at zero is not precision. This is an informative mechanics pilot with a floor, not proof of no possible treatment effect or topology equivalence.

Direct counting of all 96 action records gives 46 `send_message`, 34 `wait`, and 16 `submit_total`; there are zero `send_neighbors` and zero `inspect_fragment` actions. All tool results are valid. Every recorded subject schema and system prompt advertises `send_neighbors` and describes its single-action neighbor fanout. Thirteen of the 46 message dispatches contain nonempty canonical fragment attachments; the other 33 carry free text without attachments. All dispatches are unicast, giving 46 recipient deliveries. The registered relay-attachment measure totals **two**, both in `run-0006` at steps 2 and 5 forwarding `original-0` through agent-1 to agent-2. This is one original/path used twice, not two independent sources. The complete/source-thought cell's mean relay count of one must not be reported as the study's total event count.

Three exact process leads deserve preservation without a mechanism claim:

| Recorded locator | Observation | Rival and falsifier |
|---|---|---|
| `run-0008`, step 0, agent-1, `dispatch-1` / `message-1`; step 3, agent-0, `dispatch-4` / `message-4` | Agent-1 requests a peer's value and promises to share after receiving. Agent-0 replies that it can share once it has enough information. Both already have their own originals; neither message attaches a fragment or includes its own value | Together these suggest unnecessary reciprocal sharing conditions. They can also reflect generic request-response habits or tool misunderstanding. A fresh private note that permits immediate unconditional sharing should change early sharing if that account is useful; a generic tool-usage example may perform equally well, weakening the norm-specific account |
| `run-0003`, step 5, agent-2; `dispatch-6` / `message-6` | Says the peer's value is unverified until attached/resend, although the exact decision packet already contains its canonical `original-1` fragment received at step 1 | This is a discrepancy between status narration and accessible provenance, not proof of forgetting. Explicit reference to the existing attachment could repair it; persistence after such a reference would weaken an attachment-salience explanation |
| `run-0006`, step 3, agent-2 | Submits the correctly computed sum of three components at its first turn, with three turns remaining, although four are required | Irreversible partial-task closure despite remaining opportunity. It may arise from objective misreading, missing-component handling, or early commitment. A predeclared completeness check versus generic caution could distinguish some rivals; correct use of all four components would falsify the proposed error in that new setting |

The provenance and task-completeness leads are independent of the historical graph interpretation. A human-written offline all-gather policy demonstrates a legal successful route under these worlds; it does not establish that any model ought to discover that policy or that the pilot specifically measured reciprocal withholding.

Canonical attachment coverage is not mental knowledge. In `run-0001`, step 10, agent-0's rationale uses values from received free-text messages despite having only its own canonical original in the attachment inventory. An analysis based only on attachment IDs would miss that information channel. Separately code whether free text contains a correct original, a partial sum, an unsupported total, a request, or a claimed verification; preserve manual uncertainty and exact packet evidence. The absence of broadcast might reflect action salience or learned tool conventions, not incapacity or a topology mechanism.

Useful next discrimination is **communication affordance uptake versus unnecessary exchange conditions**. Freeze a new experiment with equal task facts and legal actions; compare a tool-affordance explanation with a specific unconditional-sharing thought and a generic cooperation/caution control. Preserve the original failed pilot. Do not force broadcasts or replace subject decisions and call the resulting success a thought-intervention effect. Primary assignment remains at the whole-network level; attachment use, relays, and achieved information are post-treatment process measures. No completed result here establishes historical causation or literature novelty.

## Novelty and next evidence

The new-to-library contribution is a precise distinction between **task-specific deferral, whole-agent waiting, and useful preparation**, plus a separately scoped **version-qualified assertion** candidate linked to one executed synthetic trajectory. A completed experiment must not automatically promote the historical interpretation. Keep ordinary coordination and successful qualified updates as evidence, including cases that weaken a proposed failure story.

Literature novelty is unestablished. Dynamic grounding, reference tracking, shared-history loss, joint plans, and repair already have a close multiagent precedent in [Yao, Zou, and Hawkins (2026), v2](https://arxiv.org/abs/2605.01750v2). Their negotiation task is different; it neither validates our Village interpretation nor rules out a narrower new result. The source check here is a nearest-precedent comparison, not an exhaustive novelty search.

The smallest next evidence step is to link the April 2 draft report, its subsequent tool sessions, and the proofreading/publication record to the same artifact. For waiting, reconstruct a bounded interval with actual permissions, task inventory, session status, human instructions, and delivered context. For version claims, freeze a fresh, opportunity-controlled test rather than amend completed pilots. Retain unsupported, null, and conflicting episodes with the same care as successful discoveries.
