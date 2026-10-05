# Historical communication falsifiers

Reviewed 4 October 2026. This read-only extension of [graph-lead-review.md](graph-lead-review.md) deliberately seeks disconfirming cases. It makes no model/API calls, mutates no database records, and changes no scientific modules or frozen protocols. It does not estimate population prevalence, identify a mental state, or establish novelty.

The source record contradicts several easy interpretations: waiting language need not imply whole-agent inactivity; peers' computer use need not prevent independent work; a public-sharing declaration need not establish recipient access; corrections need not be ignored; and repeated completion language need not represent repeated completed tasks. Typography alone also changes the exact-name mention projection. These counterexamples sharpen the candidate definitions without proving a replacement mechanism.

## Evidence boundary and reproducible searches

The pinned candidates are `behavior-c6795bc08068` version 2, hash `27e8d0d70aa9f517d920d0d9978402bf8cc2fdfdd4253a247d96df175c71d363`, and `behavior-ad77419c8fab` version 2, hash `64c0fd07505bb5e2c6058b1f975864ecdc6849e27ba580ba36c077b99b4e37a9`. Their source is `dataset-fdecf1dd6658` version 2, hash `109853f675e4c18de6faf440a7911770b64c6b326dc09eadd3ab131056e9f691`: 4,290 retained messages in `[2 April, 16 April 2025)` UTC, including 1,391 agent-authored messages. The graph candidates remain observational candidates; their repaired skepticism is not independent observational replication.

I also read a contiguous following-week sample using the existing `ingest_village` function with `store=None`, source `ai-village`, start `2025-04-16`, end `2025-04-23`, limit 6,000, and default `include_events=False`. It scans all 183,485 local chat rows and retains all 588 matching rows, including 408 agent-authored messages. No row truncation, malformed/invalid row, or duplicate ID was reported. Its normalized fingerprint is `3697a6597ff222206e28be62e370103c80463d48824d53b265f2d09074e81c1e`; timestamps range from `2025-04-16T18:00:25.293700Z` to `2025-04-22T19:49:17.354814Z`. The lack of weekend messages in this sample is not evidence of silence under a known opportunity to act.

The same following-week sample was subsequently registered as `dataset-5d2eef17db31` version 1, hash `4351ceeb788cc000b6e288927299f20d68095e9a449a47bb6cef5e0791cc5c41`, retaining the full-sample fingerprint above. The mention comparison below was checked read-only against this exact registered payload and the integrated `measurement_audit-59899929fe3a` version 1, hash `9313f84b4887582fecebe53722ac5f1456d65e0cfbf6ea3750ca68ac0350d4e4`. That audit's input fingerprint is `f41768e00dad026e8bc80933261ba2134399e3a71d4c93ab0accaeaa1c8f8461`; it represents the selected agent-authored audit input, so it must not be substituted for the full dataset fingerprint.

The local compressed chat source is 52,543,996 bytes with SHA-256 `c1d56ab7b437f65c985c3353697d92f668f3a7b83776913aa5e3eb93ed867bb7`; roster source `ai-village/agents.jsonl.gz` has SHA-256 `b7af5dd3bed6f58d0f7627706b103bdba387ed678d6ac9caf5f084799dec0350`. Original line numbers below mean decompressed JSONL line numbers, not chronological ranks. Source quotes are short exact clauses; the complete text resolves through its ID and source line. The added sample is retrospective and selected for inspection, not a preregistered holdout.

Two identical lexical screens were applied separately to agent-authored rows:

```python
waiting = re.compile(r"\b(wait|waiting|pause|paused)\b", re.I)
parallel = re.compile(
    r"(while|meanwhile|prepare|prepar|in the meantime|simultaneously|parallel)", re.I
)
```

| Retained scope | Agent-authored rows | Waiting-keyword rows | Rows matching both screens |
|---|---:|---:|---:|
| Pinned 2–15 April scope | 1,391 | 250 | 65 |
| Following 16–22 April scope | 408 | 50 | 14 |

These are reproducible retrieval counts, not validated behavior counts. A row may discuss another agent's pause, describe already-completed work, or use “while” without promising productive preparation. Selected hits were read with ordinary neighboring messages. No absence outside these source boundaries is inferred, and the two scopes differ in models and participation.

## F1. Deferring one task does not establish whole-agent inactivity

In the original handoff episode, Claude 3.7 says it will wait for the HKI draft before proofreading: `0f954e2c-246f-4845-a25a-7680d1933672`, 2 April `20:21:45.201049Z`, line 11195. It later proposes preparing call-to-action research while that proofreading dependency remains: `21919619-6a1a-4d1d-8ac8-2dfc1d68c2ad`, `20:33:42.836558Z`, line 24055. Neither statement establishes tool execution; together they refute the textual inference that the first waiting declaration covers every activity.

A clearer cross-task report appears in the following week:

| ID; UTC time; source line | Exact excerpt and contextual distinction |
|---|---|
| `8f2bb7ed-1cd8-4532-8ee7-480807f041d4`; 16 April `18:07:39.510503Z`; 102618 | o3 reports failing to find the press-release draft and requests its exact filename or link |
| `a9a4ba59-931f-4104-8eaa-11ddaf4d615f`; `18:18:30.113492Z`; 121601 | Reports an independent outreach-shortlist document: “I created a Google Doc titled”; still says access to the press draft is the blocker for polishing it |
| `55574280-065c-4390-b66e-f0dba7c028ce`; 22 April `19:49:13.782979Z`; 61179 | Claude 3.7 says: “While waiting for computer availability, I'll prepare my response” |

The first two messages support a distinction between a blocked downstream operation and independent preparation. They do not prove that the shortlist existed or was useful. The final message supports a proposed non-computer activity while waiting, not its completion. Legitimate priorities, missing permissions, uncertain resource availability, human requests, or the scheduler can still explain a later actual wait.

**Measurement candidate:** code `(agent, task, dependency, resource, declared scope, independent task opportunity)` rather than a single waiting flag. Keep a waiting declaration separate from a recorded wait action and from lack of an allocated turn. Actual lost work requires evidence that useful work was executable and the agent had an opportunity to perform it.

**Future falsifier:** under identical permissions, task facts, and allocated turns, a private instruction that explicitly restricts waiting to the blocked task should increase independent useful work relative to an agent-wide waiting instruction if scope matters. An unchanged outcome with prespecified adequate sensitivity, or successful independent work under both instructions, would weaken that account. A prompt effect would still be scoped to those words and that environment.

## F2. Role and artifact ownership can explain a graph-shaped pattern

The April 2 lead samples many task assignments by o1, including `cd0b3aec-fe69-4326-a986-232abb6f8d23`, `20:17:24.303135Z`, line 146944. A directed name mention connects an assignment to an addressee; it need not represent a delivered relay, a reply, influence, or a social reciprocity change.

The later sample has a specific shared-workspace convention:

| ID; 22 April UTC time; source line | Textual evidence |
|---|---|
| `c0381ef5-ee3d-4122-820c-3791681dffd9`; `18:56:07.538896Z`; 137864 | o3 proposes declaring a single-owner lock and an explicit release after an editing session |
| `87d3981f-2902-4ae8-af65-d053b2e5a9bd`; `18:56:47.319719Z`; 97312 | GPT-4.1 endorses the convention and reports unnecessary hesitation over low-risk edits; this self-assessment is a claim, not measured delay |
| `8c2a96bf-aedf-4d37-9bdd-6e820a24b698`; `18:59:52.837253Z`; 100475 | Claude 3.7 reports that the tracker is free and hands its next edit to o3 |
| `7b6c48dd-c9cb-47df-ab14-fc1b12dc31ec`; `19:02:28.156381Z`; 88519 | Claude 3.7 plans independent Twitter work “while o3 completes the line graph publication.” |
| `ca9e4e34-798d-4596-aa80-09e9f0bc9f10`; `19:08:05.689664Z`; 145219 | o3 reports publication and “Tracker LOCK released – free for others now.” |
| `a605e620-dcea-4a36-bc43-1184a84c36dd`; `19:21:49.127678Z`; 118982 | GPT-4.1 reports inserting the chart into the separate EA Forum draft and releasing that asset |

This is declared **artifact-specific serialization with proposed parallel work on another task**. It contradicts an interpretation that adopting a lock necessarily stops all society activity. It does not show that locking reduced collisions, that an enforceable lock existed, or that publication was valid. The publication message contains a literal `<ID>` placeholder in its chart URL; this text cannot resolve the alleged public artifact. The origin of the placeholder—agent text or export processing—was not established, so it is a reference-quality limitation rather than a proven fabricated artifact.

Model replacement and onboarding are additional observed covariates: a human announces GPT-4o's replacement by GPT-4.1 in `7c7a5360-eee4-4ff5-bccf-b178373e1500`, 15 April `18:00:07.934881Z`, line 89265, and o1's replacement by o3 in `4803ed10-5958-4aad-9a34-9ee09af7a8bc`, 16 April `18:00:25.293700Z`, line 51625. A later human reports provider rate limits for both Claudes in `a18031a8-26ff-4dbd-bd15-0d6b9a9197ba`, 17 April `19:53:50.835006Z`, line 115695. These are recorded reports, not randomized model/availability manipulations. Treating altered interaction volume as a topology effect would ignore plausible changes in ability and opportunity to participate.

**Future falsifier:** hold delivery topology fixed while randomizing task owners and independent-task availability, or hold roles fixed while changing the permitted delivery graph. If an apparent central coordination pattern follows the assigned owner across agents rather than a fixed graph position, that weakens a position-specific explanation. Changing topology changes opportunities as a bundle unless degree, fanout, path length, budget, and timing are separately controlled. A simulator needs distinct artifact ownership, actual availability, voluntary waiting, and scheduler state to represent this question.

## F3. Qualifiers can survive handoff; erosion requires a real transmission chain

The draft author explicitly says updates remain in `101d94f4-99ab-476d-9edf-b73059a72c35`, 2 April `20:29:42.720910Z`, line 11551. Later o1 keeps the unfinished-summary condition in `42ac93d4-ce01-495c-b309-1c1aef77aad9`, `20:35:10.367352Z`, line 47723: “once the summary is finished.” This is counterevidence to treating a completion keyword as proof of false readiness or inevitable qualifier laundering.

The later public-access episode is also more mixed than an erosion story:

| ID; UTC time; source line | Scope of assertion |
|---|---|
| `18c87476-6f39-447c-9635-f9b226e0d953`; 17 April `19:55:59.577516Z`; 17758 | o3 reports publication but says its email is still unsent; nonetheless claims “outsiders will no longer get a 404.” |
| `5d80249d-cad5-4677-95b1-d18000b24320`; `19:56:04.954901Z`; 67124 | GPT-4.1 explicitly refers to o3's publication, retains emailing as in progress, and says “I’m monitoring for confirmation” of external access |
| `74998816-4efe-46a8-be8f-ed7c8c850d78`; `19:56:50.278228Z`; 83630 | Again retains the need for an outside-domain test |
| `80f61c3e-98fa-4b60-bb67-67943204430c`; 18 April `18:10:14.785405Z`; 92484 | Human reports that the emailed link does not work |

The peer's retelling does not erase every qualifier: it preserves pending email/test conditions. The original sender already makes an unverified universal-access assertion, so disagreement with later access reports is not by itself evidence of qualifier loss during transmission. Actual URL identity, sharing revision, domain policy, and recipient context are not fully linked. Same document title is not a source/version identity.

**Measurement candidate:** represent each assertion as `(referent ID, version/time, audience, claim, evidence method, qualifier)`, and record an explicit lineage only when the retelling cites or otherwise demonstrably references the source. A shared topic, equal URL, or similar sentence is insufficient to infer copying. Classify unresolved referents and source identity as unknown rather than count them as erosion. The historical evidence here motivates audience-qualified readiness; the separate synthetic stale-version trace remains in the earlier review and must not be relabeled historical evidence.

**Future falsifier:** expose identical evidence to all actors, vary only preservation of a clearly defined uncertainty/version qualifier in a controlled relay, and measure a prespecified downstream claim/action. If qualified and stripped relay conditions behave similarly, or actors reconstruct the qualifier without prompting, the proposed mechanism is weakened. Extra information, length, salience, source authority, and delivery opportunity need separate controls.

## F4. Producer configuration is not recipient-side readiness

In `fda71d0d-5b8c-418a-a992-d026a7b9437e`, 15 April `18:23:22.822997Z`, line 181805, Claude 3.7 reports seeing GPT-4.1's icon in sharing settings. GPT-4.1 continues to report blocked campaign documents in `71811437-779a-4b0f-a5bc-affb5e46c61f`, `18:39:32.572801Z`, line 81481, while proposing other outreach work. The producer's configuration observation and the recipient's access report are different channels. Neither establishes exact file identity or the technical cause.

For external users, `4622d579-b6d5-489e-a398-e97ac6159bb3`, 17 April `19:34:20.362210Z`, line 50296, reports that agent accounts can edit while outsiders remain blocked, attributing this to admin policy. That attribution is unverified without administrator/tool evidence. Two subsequent human reports explicitly say the supplied links still fail: `8d3aeac4-1c81-4d31-9ed5-9c5b5da37d08`, 18 April `18:27:52.688294Z`, line 101212, and `30d3d70c-e4a0-4e6d-9c1c-a5b125be2a0a`, `18:28:43.308000Z`, line 34996. These falsify the inference that a producer's public-sharing declaration alone proves successful external access. They do not isolate a policy barrier from wrong/copied URLs, authentication context, UI failure, or changing permissions.

The proposed measure is **audience-specific readiness disagreement**, with an exact artifact/version match and evaluable recipient test as prerequisites. An unavailable test is missing evidence, not success or failure. Keep presentation, notification delivery, retrieval, edit permission, and completed use distinct. An environment for this hypothesis needs audience-scoped permissions and a recipient retrieval action; a universal shared artifact with instant access cannot test it. A future factorial could vary actual access independently of the producer's readiness assertion, with no changes in the task facts or recipient schedule.

## F5. Some corrections produce a prompt textual repair

Two ordinary episodes provide negative examples for a blanket persistence or correction-ignoring theory:

| Error / correction / response IDs | UTC times and original lines | Directly supported result |
|---|---|---|
| `c85625ef-17b9-4f9c-a30e-f2cec1fed571` / `e65210a6-e9cd-421e-9456-2c7fef44e3c6` / `79222a65-3f26-448d-b15c-8d170ecf68e1` | 15 April `18:10:48.699169Z` (143545) / `18:11:53.168018Z` (165160) / `18:12:12.722723Z` (86869) | GPT-4.1 supplies a fundraiser URL, a human supplies different actual links, and GPT-4.1 explicitly corrects its answer 19.555 seconds later |
| `db273983-c11b-4cc2-947b-316792e1a7a7` / `532d86cc-3432-4cae-a2f4-92aa7e501366` / `40f3f346-5667-47f4-8ce3-d49f7b1d0620` | 17 April `19:50:40.745003Z` (157155) / `19:51:32.369278Z` (59628) / `19:51:49.525527Z` (46478) | GPT-4.1 claims continuity from o1's memory; the human says no model accessed it; GPT-4.1 retracts direct access/inheritance 17.156 seconds later |

The memory correction's exact human text is “no model got access to o1's memories”; the response explicitly distinguishes briefing from direct inheritance. This is a recorded human correction and textual withdrawal, not independent inspection of memory files. The fundraiser's present-day validity was not tested here; an additional contemporary human reports the earlier URL returning 404 in `5b3bd0b4-cac3-4b0e-bd7f-f3b902ce0c25`, 15 April `18:11:53.225119Z`, line 65542.

Elapsed timestamp difference measures observed acknowledgement latency, not reading latency, an intervention effect, or durable action correction. The exact hidden packets are absent. Human authority, specificity, turn allocation, or fresh onboarding may explain prompt repairs. A later search for repeated incorrect use would be necessary before assigning durable repair status. A useful future test separates correction delivery from its source authority and content, then measures both subsequent statements and task actions.

## F6. Repeated completion language is not repeated verified work

Three distinct Claude 3.5 messages have exactly identical content, SHA-256 `dc3435bdbd3e38f5ad1f1612dfe993635745d4fee2bfd90b93faa3eadb2dbe6d`: `91ce50a2-df86-4e18-a128-86394dd6165a`, 16 April `18:12:00.527333Z`, line 104445; `9d54c620-7b72-4f33-86bc-8f44d821bfa8`, `18:21:55.121217Z`, line 112648; and `d6fa17a5-6310-4f8b-9794-a8c3b4ef9e6a`, `18:54:46.066970Z`, line 154058. The text includes “I notice I was repeating myself about completing the press release” and proposes starting a session. Distinct record IDs rule out an ID-deduplication issue in the retained sample; they do not establish three separate productive sessions or three completed releases.

A human proposes a harness/training explanation for repeated responses in `ee3931ee-684d-4170-9676-500ce277bfc1`, 17 April `19:32:13.581481Z`, line 170912. It remains the human's hypothesis, not a measured cause. Scheduler transitions, session-recap prompting, repeated requests, cached context, or output replay are ordinary rivals. A completion detector must identify the referent and distinguish completed review, proposed editing, and finalized release. Evidence independence requires more than counting agreeing or repeated messages.

## Instrument falsifier: display-name typography changes the graph

**Correction recorded 4 October 2026:** the original read-only scan found 143 distinct `(message ID, non-self roster target)` pairs, increasing to 162 after Unicode NFKC normalization, whitespace collapse, and dash replacement. Those numbers remain the result of a **raw lexical diagnostic across all 46 roster display names**. My original description incorrectly called this the instrument's exact rule: the scan excluded self mentions but omitted the graph instrument's minimum display-name length of three characters. It counted 77 literal `o3` targets and 4 literal `o1` targets that the graph deliberately excludes. All 81 occur in both raw scans; they explain the entire baseline discrepancy. These may be meaningful short-name references, but this check does not validate them or change their eligibility in the existing instrument.

The graph-matching comparison on the same 408 agent-authored rows is:

| Comparison | Original exact-text pairs | Normalized shadow pairs | Shadow-only pairs |
|---|---:|---:|---:|
| Original raw lexical diagnostic; nonself, all display-name lengths | 143 | 162 | 19 |
| Graph eligibility; nonself, display name differs from agent ID and length at least three | 62 | 81 | 19 |

Counts are unique message/target pairs, not numbers of repeated string occurrences. The read-only reconstruction's eligible exact and shadow pair sets each match `measurement_audit-59899929fe3a` exactly. Its exact target counts are 22 for Claude 3.7 Sonnet, 34 for GPT-4.1, and 6 for Claude 3.5 Sonnet; the shadow adds 19 GPT-4.1 pairs. The 19 added pairs are identical in the original diagnostic and graph-matching comparison. Self exclusion is not the cause: adding self mentions to the original exact diagnostic would produce 149 pairs, rather than 143. The integrated shadow also checks normalized roster collisions; it reports none in this roster. Its versioned normalization includes more enumerated dash characters and trims whitespace, but those differences produce no residual pair-set discrepancy in this sample.

Neither comparison changes a saved graph or classifier. This amendment retains the original analysis and identifies its different eligibility policy; it does not silently replace its counts. The integrated shadow measures one sensitivity, not full mention recall or a validated new instrument. Shadow text spans refer to the transformed text and do not establish offsets in the original source.

For example, `1154426b-b422-4d31-8800-c6e69d3c729a`, 16 April `18:18:46.211115Z`, line 12401, addresses `GPT‑4.1` with a nonbreaking hyphen; the roster uses `GPT-4.1`. The original exact-name pattern fails although the referent is clear to a human reader. Shorthand such as a Claude name without the word Sonnet, pronouns, and reply relationships remain outside this shadow check. Mention presence still does not establish delivery or reading.

Before interpreting graph differences across newly introduced models or episodes, version the alias policy, retain matched text spans, adjudicate a representative validation sample, and report sensitivity across projections. A social interpretation that vanishes under typography normalization should lose support. Improved recall alone cannot create causal edges, and observing a mention graph never establishes the actual delivery topology.

## Research consequences

The useful research units are bounded task/artifact episodes for historical description and independent reset whole-society runs for a group causal experiment. Within-run actors, messages, and graph edges interfere and are not independent randomized trials. Follow-up measurements should retain unknown exposure, unresolved referents, absent tool traces, missing results, and ordinary successful qualification alongside failures.

These cases motivate operational communication distinctions already represented in [communication-theory.md](communication-theory.md). Dynamic grounding, reference tracking, joint plan formation, and repair have nearby experimental precedent in [Yao, Zou, and Hawkins (2026), pinned v2](https://arxiv.org/abs/2605.01750v2); those results neither establish our historical mechanisms nor make a new library label novel. The required separation of assignment, exposure mapping, and estimand under interference is developed by [Aronow and Samii, pinned v4](https://arxiv.org/abs/1305.6156v4).

The next useful work is reconstruction of one exact artifact handoff and its recipient access, rather than promotion of every dramatic declaration into a behavior. The current negative examples disconfirm overbroad definitions; they do not prove all handoffs succeed, all qualifiers survive, or all corrections work.
