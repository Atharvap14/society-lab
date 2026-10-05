# Society Lab

An agentic research instrument for computational social science over agent societies. Import an observed episode, inspect its communication graph, investigate behavioral hypotheses, create a bounded experiment, intervene through private context, and retain the resulting evidence and rival theories.

The system distinguishes source observations, screening candidates, controlled simulation results, and broader theory. A completion statement is not verified completion; network structure is not an identified network effect. Attention allocation is outside this project.

## Run locally

Run from a **complete source checkout**, with the working directory at this README. Python 3.11+ is required. Keep `swarm_lab/`, `web/`, `prompts/`, `skills/` and `research/` together: the current Python package configuration does not include these companion assets in an installed wheel, so wheel-only deployment is not supported.

The core uses the standard library. NumPy enables graph spectral analysis and Hodge decomposition; those features report unavailable if NumPy is absent. The full test suite requires NumPy and Node.js on `PATH` for its numerical and executable browser checks. No Node packages or external dashboard CDNs are required.

For the real AI guide, set `OPENAI_API_KEY` in your environment or create `.secrets/openai-api-key.txt` containing your key; keep credentials out of source control. A clean checkout also needs an explicit guide allowance. The example below authorizes a cumulative research cap of 400 calls and a separate guide allowance of 100; choose your own limits. The research cap must match both commands. Configuration makes no API calls and does not reset recorded usage. Without this file, the guide reports `not_authorized`.

```powershell
python scripts/configure-guide.py --research-calls 400 --guide-calls 100
python -m swarm_lab.cli --max-calls 400 serve --port 8765
```

Open [Society Lab](http://127.0.0.1:8765). On Windows, `scripts/Start-Lab.ps1 -MaxCalls 400` starts the server in a hidden background process with the same cap and saves logs under `.runtime/`.

Start with the [full Society Lab user guide](docs/user-guide.md), or read the [short workflow note](research/using-society-lab.md). Open a project and chat, then ask the guide what you want to study. The work can branch: discover a pattern, revisit an old result, copy a design, start another chat, or return to a pending experiment. Type `@` to search saved chats and artifacts across projects. The guide reads exact context and invokes real research tools; its working summaries, tool receipts and linked results remain in the chat. Saved work includes a Behaviour Library and Saved Experiments collections. Markdown answers can contain safe embedded analysis reports drawn from exact saved results. Replays separate local records, direct messages, shared-room posts, unknown audience and actions.

Portable review package: [project and tool documentation PDF](docs/assets/society-lab-project.pdf), [full user guide PDF](docs/assets/society-lab-user-guide.pdf), [real-results PDF](docs/assets/society-lab-real-results.pdf) and [recorded demo](docs/assets/society-lab-demo.mp4). These saved artifacts are separate from the private local runtime.

The current demonstration connects AI Village and investigates a source-linked document-access episode. Its reviewed world represents stable references, permission grants, authenticated/private profiles, committed navigation, versions and copies. The current narrow recovery study uses two fresh LLM roles through executed local tools; the historical account state and original model policies are omitted. The product accepts source-grounded Village plans and results, preserving their hypothesis and fidelity contract. Additional engineering adapters and developer fixtures remain in the repository; they are not substituted into this demonstration.

There are two starting points: **logs only**, as in the AI Village demo, or **logs plus an existing environment**. Logs support observation and hypothesis review. Experiments from logs require a separately reviewed world, with unavailable tools represented by disclosed proxies. An existing environment needs an adapter and a review of its tools and information boundaries before execution; arbitrary uploaded code is not automatically runnable.

The Behaviour Library retains source-linked candidates, rejected claims, prompt rubrics and text-screen results. Eight starter rubrics help define positive, negative and unknown evidence. Laya screens explicit text from a saved prompt; unavailable inference remains unknown. Neither a text label nor a graph link establishes a cause.

Native scientific figures use optional Matplotlib (`python -m pip install matplotlib`). `scripts/build-village-plots.py --help` describes exact-source activity and literal name co-occurrence plots; `scripts/build-village-access-plots.py --help` describes exact completed Village results: matched outcomes, the saved paired effect interval, secondary count scatter and executed action progression. Reports display verified, source-pinned plot caches when present. A clean checkout must import its own source and generate its figures; it does not include this laptop's saved database or raw dataset.

To connect your own swarm, use the [observability SDK](examples/observability-client.md) and `societylab.events.v1`. It preserves explicit agents, tasks, recipients, tool calls, artifacts and interventions. Stable event IDs support idempotent retries and new saved versions. Missing relationships remain unknown. The browser can follow new batches and replay the recorded events.

The [dashboard cache check](research/dashboard-state-cache-check-20261004.md) records the current inventory cache, integrity boundaries and actual local response times. Jobs, usage and exact scientific-object reads remain fresh.

```powershell
python -m pip install numpy
node --version
python -m unittest discover -s tests -v
```

The following commands use a separately acquired Village directory and launch model work only where `--live` is supplied. Source access, authorized credentials and sufficient remaining request budget are needed for that path.

```powershell
python -m swarm_lab.cli ingest --source ai-village --start 2025-04-02T00:00:00Z --end 2025-04-16T00:00:00Z --limit 6000
python -m swarm_lab.cli observe DATASET_ID
python -m swarm_lab.cli investigate DISCOVERY_ID --count 2 --live
python -m swarm_lab.cli design BEHAVIOR_ID --trials-per-arm 3 --live
python -m swarm_lab.cli experiment PROTOCOL_ID --live
python -m swarm_lab.cli evaluate EXPERIMENT_ID --live
python -m swarm_lab.cli theorize EXPERIMENT_ID --live
```

Without `--live`, research uses explicitly labeled templates and experimental subjects use a scripted smoke-test policy. Those runs test infrastructure; they are not evidence about language model behavior. A live registration pins the requested subject model, generation settings, environment code and subject adapter. Running a different backend requires a new registration.

`workflow` composes those stages for the initial shared-artifact study. It stops if no candidate supports that route, retaining discovery results. The saved `experiment_fit` field screens this artifact workflow; another current world may still fit after separate capability and mechanism review. The Research cycle uses approved blueprints to dispatch across the four authoring families. `show OBJECT_ID --history`, `list --kind behavior`, and `usage` inspect the library and call ledger. The dashboard runs jobs in the background and exposes their progress and failures.

## Dataset and scope

The source is [AI Village](https://huggingface.co/datasets/aidigestorg/ai-village), snapshot `838b4150303ca8228e8edb432d8b8ccae353d258`. The read-only GCS mount is `V:`; locally seeded chat and metadata files are in `ai-village/`. Importing from the mount is supported. Large computer-use tables and screenshots are not fetched by the chat importer.

Chat JSONL is not chronologically ordered. An import scans the source and retains the earliest chronological records inside its half-open UTC window. Limits constrain retained records, not the source scan. Diagnostics expose truncation, malformed rows and potential censoring. Every retained message keeps its source ID, file/line and content fingerprint. Human messages remain distinct from agent messages. The complete dataset is not assumed to be loaded just because a bounded window is present.

Follow the source dataset terms. This project performs analysis and inference; it does not train or fine-tune models on the export. Exact original prompts and all external world state are unavailable, so generated environments disclose their reconstruction limits.

## Research harnesses

The six roles are discovery, skeptic, environment builder, causal methodologist, evaluator and theory curator. They are responsibilities that can be assigned to different workers. Their prompts and actual `skills/*/SKILL.md` instructions are loaded into execution. Bounded tools retrieve exact messages, surrounding context, ordinary samples, substring counterexamples, typed graph neighborhoods and allowlisted theory references. Cited IDs must have been supplied or retrieved; invented or unread IDs are rejected. This verifies provenance, not whether a claim is semantically supported.

Responses supplies structured output and a function-tool loop. Codex CLI supplies an existing read-only harness over an isolated evidence packet with structured output. Its native file tools read that packet; the Python live tool registry is not attached. Codex mode is supported for research roles; experimental subject actions currently use Responses. CLI sandboxing plus a separate directory reduces access but is not presented as a general security guarantee.

Research calls archive exact request/schema snapshots and reported provider status, errors and incomplete details. Explicit non-completed partial answers cannot become completed results. The bounded research loop closes tools and requests one final answer; it does not regenerate successful actions or retry unknown transport failures. Failed stages retain saved proposals for a declared review resumption. Literal multi-term searches provide separate hit counts and host retrieval logs; concurrent role invocations keep independent evidence logs. Research roles can inspect exact allowlisted implementation sections by source hash, without exposing that privileged code to subjects.

Set `OPENAI_API_KEY` or put the key in `.secrets/openai-api-key.txt`. Keys are never passed to Codex evidence packets. API headers are not logged. Credential-shaped strings are redacted before external model inputs and persistence; this is a limited redactor, not a guarantee that the source contains no sensitive material. `.secrets/`, raw dataset files and `.runtime/` are ignored by Git. The default cumulative API cap is 400 calls, including failed/reserved calls. `--max-calls` changes that explicit cap; token usage is recorded, with no dollar-cost estimate implied.

## Measurements and experiments

The [measurement review workflow](research/theory/measurement-adjudication.md) freezes a generic binary question and a seeded sample from an exact retained dataset. Reviewers declare yes, no or uncertain labels, reasons and provenance; concurrent saves use exact-version checks and preserve earlier judgments. Optional regex predictions remain separate from the construct. The dashboard exposes source pins, bounded context, explicit prediction display and unknown comparison scores. Creation and review use zero model calls. The [actual production check](research/measurement-review-production-check-20261004.md) verified the 16-message sample and one explicitly agent-assisted uncertain declaration; this tests the workflow and establishes no calibration or human ground truth.

Screening rules identify commitments, completion reports, evidence requests, blockers, corrections, acknowledgements and plan changes. Optional typed classifiers can abstain. Their confidence is uncalibrated until evaluated on representative, independently adjudicated data. A rule firing is a search lead rather than a novel behavior.

Network projections keep explicit mentions/replies separate from inferred temporal proximity and lexical recurrence. Directed strength, reciprocity, concentration, components, brokerage and coactivity-normalized rates are accompanied by evidence IDs. A normalized graph Laplacian basis uses a disclosed symmetrization. It is not assumed to be a continuous Laplace–Beltrami model of agent society. Repeated eigenvalues, disconnected components and isolates limit basis interpretation. A room/hour author-label permutation provides a descriptive null comparison; it does not identify causal influence.

Observatory now shows saved node denominators, regex-hit proportions and grouped spectral energy in tables. It retains raw quantities, distinguishes full and induced-author graphs, checks group multiplicities against the saved spectrum, and explains degree scaling and isolate/null energy. These are consistency-checked recorded summaries, with unknown rates preserved; opening them does not rerun a graph operator or establish consensus or influence.

`screen-graph DISCOVERY_ID` adds an exploratory temporal search for concentration shifts, reciprocal mentions, reachability-sensitive bridge positions, lexical recurrence and shared URLs. Comparisons have activity, membership and time restrictions plus window-size sensitivity checks. These data-selected contrasts do not carry confirmatory p values. Per-agent observable rates can be projected onto Laplacian eigenspaces. Referenced agents with no authored records have unknown rates; they are not imputed as zero. An explicitly labeled author-only induced subgraph supplies a separate analysis when necessary.

`audit-mentions DATASET_ID --version SOURCE_VERSION` compares the existing exact-name instrument with a separate Unicode formatting shadow. It preserves exact source versions, flags normalized-name collisions as unknown, and gives normalized-coordinate spans without inventing original offsets. It changes no existing graph. `project-observables DISCOVERY_ID` derives graph signal summaries without another classifier/model call.

The [Episode workspace](research/episode-workspace.md) opens one original graph lead from Observatory or its matching behavior. It keeps exact windows, the original comparator, rival explanations, bounded source excerpts and recorded name/temporal/actor/marker/Hodge layers together. Gates distinguish recorded consistency from fresh source/operator replay. Its **Study guide** carries an editable question and exact origin across six supported design choices, showing assignments, outcomes, falsifiers and fit limits. Opening design controls leaves live mode and form sources unchanged; the local draft is not attached to a protocol or sent to subjects. The question can also transfer into Environment authoring, with any motivating observation selected explicitly there. These navigation actions make no model call or experiment.

The Behavior library keeps a record, its critique and its history readable when source evidence is unavailable. It resolves the exact declared dataset reference and checks returned identity and cited-record membership; it never substitutes the latest dataset. Missing or invalid source pins withhold source-dependent artifact design and episode navigation. Available source records still require interpretation and world-fit review.

`observe DATASET_ID --measurement-backend laya --measurement-limit 32 --live` runs a bounded additional measurement sample through the real Laya worker. `jev` uses the Typesafe API and requires its own `JEV_API_KEY` or `TYPESAFE_API_KEY`. The OpenAI key is not used for Jev. Operational failure and unsampled records remain unknown, without a classifier fallback. Deterministic screening remains separately identified. On this laptop, the Laya forward attempt stopped at the declared RAM gate; no model inference or corpus calibration succeeded. Jev has no configured credential. The authored fixture benchmark tests interfaces and known errors, not corpus accuracy.

The current Village world tests document access and repair. The new narrow reference-recovery world holds content, viewer access and starting profiles fixed. Its owner and teammate can search by title, navigate, inspect and message. Its primary oracle requires the auditor to actually open the current original. A canonical-access-check note and a neutral note are compared in matched starting worlds with fresh teams. Within-team effects are allowed; matched whole-team differences, rather than individual agents, enter the contrast. Secondary copies and failures remain descriptive.

Protocols freeze before subject calls. Runs retain assignment, information boundaries, action/result histories, independent seeds, objective outcomes and model traces. Malformed model actions consume the action budget. Infrastructure failures abort and save incomplete reports without estimating effects or promoting a behavior. Positive, null and negative results use the same reporting path. Small pilots have wide uncertainty and cannot establish a historical mechanism or generalization. Local freezing is not a public preregistration service.

Three other worlds are executable. **Noisy source diffusion** distributes correlated binary sensor reports and scores final verdicts. **Complementary information** gives four agents independent private uniform residues and scores the exact sum modulo q; any strict subset leaves the target uniformly uncertain. Both support graph-level interventions and whole-network factorial randomization. **Optional shared resource** gives four agents independent and computer-gated tasks under an invented exclusive lease and external release schedule. Independent work remains legal during contention. These low-level research APIs have distinct meanings and outcome definitions and are outside the current Village-only product demonstration.

```powershell
python -m swarm_lab.cli design-complementary --seed 4411 --trials-per-cell 2 --live
python -m swarm_lab.cli experiment-complementary COMPLEMENTARY_PROTOCOL_ID --live
python -m swarm_lab.cli audit RESULT_ID
python -m swarm_lab.cli evaluate-claims RESULT_ID
python -m swarm_lab.cli replicate ARTIFACT_PROTOCOL_ID --seed 4343 --trials-per-arm 4
python -m swarm_lab.cli link-replication ORIGINAL_RESULT_ID REPLICATION_RESULT_ID --theory-id THEORY_ID
python -m swarm_lab.cli resume-investigation RESEARCH_ATTEMPT_ID --live
```

The complementary default assigns eight networks and at most 96 subject calls. Its smallest possible exact two-sided p value is 2/36, so it cannot reach .05 after Holm correction even with perfect separation. Topology changes an opportunity bundle including multicast delivery counts. Canonical attachment coverage is a recorded inventory, not a measurement of latent knowledge; free text can transmit values too. Realized communication is a post-treatment description, not identified mediation.

```powershell
python -m swarm_lab.cli design-resource --seed 5371 --trials-per-cell 2
python -m swarm_lab.cli experiment-resource RESOURCE_PROTOCOL_ID
python -m swarm_lab.cli audit RESOURCE_RESULT_ID
python -m swarm_lab.cli evaluate-claims RESOURCE_RESULT_ID
```

The resource default assigns four whole swarms and at most 96 hosted decisions; its minimum exact two-sided p is 1/3. A private task reminder is compared with a word-matched neutral note at a fixed recipient. Completion is an executed counter, while waiting and access counts remain process descriptions. Global historical computer exclusivity is unestablished, and the source review reports concurrent sessions. The new world is an optional analogue, with alternatives and assumptions documented in [resource study design](research/theory/resource-study-design.md). Live execution requires its frozen adapter and enough remaining request budget. Independent replay also checks archive bytes against the protocol's pinned source hashes.

A separate **correction-relay** capability crosses early/late correction availability to a relay with an informative/sham direct information route. Two subject roles have four fixed decision opportunities; each seed block contains four fresh teams sharing the exogenous source values and schedule. The exact final revision and modular total are scored independently. Execution and audit require exact registered versions, and a fixed study cannot be repeated under a new job name. The complete grid is retained on failure, with no subset estimate. Its default interval and interaction p-value are unavailable; conditional bounds require explicit assumptions. See the [implementation and causal scope](research/theory/correction-relay-implementation.md).

```powershell
python -m swarm_lab.cli design-revision-relay --blocks 2 --seed 173
python -m swarm_lab.cli experiment-revision-relay REVISION_RELAY_PROTOCOL_ID --protocol-version 1
python -m swarm_lab.cli audit-revision-relay REVISION_RELAY_RESULT_ID --version 1
```

Correction relay is a separate engineering study API. The general environment compiler and cycle retain their four declared templates; the current Village demonstration has its own source-bound access adapter. Unsupported construction requirements remain unsupported. Software checks of these APIs do not supply empirical evidence for the Village hypothesis.

Claim audits check a finite typed fact ledger against the canonical report, including contrasts, counts, actor/version inspection distinctions and actual action replay. Only code-generated approved fact text is verified. Model-written sentences remain visible as unverified prose. Research inputs preserve prompt/task/schema hashes, and exact source versions bind investigations. A failed skeptical review can resume the saved proposal without rerunning discovery. Review amendments preserve prior outputs and reasons.

## Agentic environment authoring

The Wind tunnel's Environment authoring tab accepts a question, optional source-linked behavior, and exact required capability IDs. A live builder proposes a declarative world; a separate methodologist reviews the exact compiled blueprint. Unsupported requirements, failed role calls, source misstatements and uncertain mechanism fit remain recorded. The expandable capability inventory describes tools rather than a fixed behavior ontology. See [the authoring contract](research/theory/environment-authoring.md).

```powershell
python -m swarm_lab.cli construct-environment --research-question "Which world can test complementary information sharing?" --require private_complementary_residues --require neighbor_multicast --live
python -m swarm_lab.cli resume-environment-review CONSTRUCTION_ATTEMPT_ID --live
python -m swarm_lab.cli register-blueprint APPROVED_BLUEPRINT_ID --trials-per-cell 2 --seed 4491
```

Registration requires a bound approving review and current source/implementation checks. The bridge preserves the authored world exactly, including its graph and parameters, and blocks unsupported design combinations. The available designs test predefined private context contrasts; they do not automatically isolate every proposed mechanism. Registration launches no subjects. A later explicit execution uses its frozen backend; offline execution validates mechanics only.

The dashboard first shows a [read-only registration compatibility preview](research/registration-compatibility.md), bound to the displayed blueprint version, hash and subject mode. It separates construction and analogue approval from current source checks and design compatibility, and shows the fixed outcome, contrast, study units and future call bounds. Unsupported worlds stay blocked. The CLI can bind the same identity with paired `--blueprint-version` and `--blueprint-hash` options.

## Theory, evidence and extension

See [communication theory](research/theory/communication-theory.md), [causal experiments](research/theory/causal-experiments.md), [environment fidelity](research/theory/environment-fidelity.md), [measurement validation](research/theory/measurement-validation.md), and [network analysis](research/theory/graph-analysis.md). These define operational constructs, alternative explanations, fidelity dimensions, and research questions rather than declaring a universal theory.

The [construct-status map](research/theory/construct-status.md) separates implemented measurements from proposed grounding, discharge, repair, memory and latent-state constructs. It also distinguishes the six study interfaces, four environment-authoring families and five executable worlds.

The [experiment choice map](research/theory/experiment-choice-map.md) maps questions to executable assignments and outcomes, cheap falsifiers and reviewed extensions. It distinguishes independent draws from paired worlds, policy effects from mediation, and tiny-pilot inference limits across the six study interfaces. Research input and result traces hash the same frozen instruction text, even if prompt or skill files change during an invocation.

Communication models should compete on explicit source observations, alternative explanations and discriminating interventions. Artifact dependence, routing, task-specific waiting and version coordination are useful questions, not inferred causal facts. The current [Village story](docs/submission-writeup.md) and [evidence note](docs/real-results.md) retain the source-linked investigation and its unresolved alternatives.

The [graph mathematics methods note](research/theory/graph-math-methods.md) connects the implemented Laplacian operator, repeated eigenspaces, temporal graph comparisons, missingness, activity-conditioned nulls and causal interference to primary literature. The [historical communication falsifiers](research/theory/communication-falsifiers.md) retain exact source counterexamples and distinguish task-specific waiting from whole-agent inactivity.

The [graph-operator research agenda](research/theory/graph-operator-research-agenda.md) prioritizes degree scaling, missingness, fixed-population comparisons and justified null strata. Its later [Hodge instrument](research/theory/graph-hodge-methods.md) now decomposes declared oriented edge signals into gradient and circulation, with separately declared faces required for curl and harmonic components. The source-bound [selected-window plan](research/theory/selected-edge-flow-plan.md) uses net named-reference counts and retains balanced reciprocal edges and all original variants. It has replayed all 24 cells. Those algebraic components do not establish hierarchy, rumor, inconsistent reasoning or chronological relay. Directed stationary-flow remains a conditional extension; no continuum Laplace–Beltrami geometry is assumed. The [multiplex communication experiment framework](research/theory/multiplex-communication-experiments.md) distinguishes emission, reference, exposure, attempted action, artifact transition and outcome, with perturbations and falsifiers for relay, bottleneck, dependency, echo and convergence hypotheses.

SQLite stores append-only object versions, hashes, role/tool/model traces, jobs and a call ledger. Behavior records retain skeptical objections, evidence scope, experiment links and novelty status. Theory records retain rivals, falsifiers, conflicts, boundaries and replication status. Initial theories cannot claim replication. Scripted runs receive an infrastructure status; live bounded studies receive a pilot status. Neither automatically produces a general theory.

Environment creation is declarative and capability-checked. Each adapter accepts only its supported parameters. The Village adapter implements a narrow local account/navigation proxy, not arbitrary browser or Google-service fidelity. New mechanisms need reset, observe, step, inject_context, snapshot and independent evaluation, plus information-boundary and reset tests. Unsupported requirements remain visible; a proxy cannot silently claim to recreate the source incident.

## Executed evidence in this workspace

The actual Village import contains 4,290 chat records from 2–16 April 2025, pinned to the verified source snapshot. Twelve exploratory graph leads were retained. Corrected skeptical reviews preserve task-specific waiting and role-structured coordination as candidates; neither historical causation nor literature novelty is established. See [the exact-source review](research/theory/graph-lead-review.md).

A separate following-week import retains all 588 matching chat records, including 408 agent-authored messages, from 16–23 April. It yielded eleven data-selected graph leads across twelve windows. Two parallel investigator/skeptic workflows retained further handoff and task-owner request candidates with ordinary coordination rivals. The formatting audit on agent-authored records found 62 nonself exact mention pairs and 81 shadow pairs, including nineteen added formatting candidates. This is a descriptive instrument sensitivity, not independent causal replication or a novelty claim.

```powershell
python -m swarm_lab.cli audit-mentions DATASET_ID --version 1
python -m swarm_lab.cli audit-name-eligibility DATASET_ID --version 1 --short-name o1 --short-name o3 --unicode-shadow
python -m swarm_lab.cli compare-mention-graphs ELIGIBILITY_AUDIT_ID
python -m swarm_lab.cli audit-selected-leads DISCOVERY_ID --version 3 --short-name o1 --short-name o3 --unicode-shadow
```

Short names are excluded by the unchanged baseline instrument. The explicit o1/o3 candidate scan adds 81 exact pairs, giving 143 expanded exact and 162 expanded shadow candidates. A [bounded source adjudication](research/theory/short-name-adjudication.md) separates direct address from topic, ownership and quoted references without estimating corpus precision. On the same fixed five-node diagnostic universe, exact-baseline null modes are three and expanded-exact null modes one; o3 incoming matches move from zero to 77. These are measurement-dependent graph differences, not changed behavior, social isolation or causal influence. Diagnostics validate the pinned source/roster and recompute event streams; they never alter the original discovery graph or compare eigenvector coordinates across changed operators.

The separate [selected-episode audit](research/theory/selected-lead-sensitivity-plan.md) replays the original discovery before varying mention extraction. It preserves all 588 source rows, eleven selected leads, six windows and four ordered comparisons. Explicit short-name expansion reverses one concentration contrast from +0.335 to −0.114; adding the Unicode shadow gives +0.025, below the original descriptive screening threshold. Native and fixed-pair node policies remain separate, and the original candidates are unchanged. This sensitivity uses the same records after selection; it is neither independent replication nor an adjudication of addressing, reading or historical influence. The dashboard runs this audit without model calls and attaches exact source versions to future investigator/skeptic packets.

The [temporal reference-path interpretation](research/theory/temporal-path-interpretation.md) checks all six original selected windows without rematching. In the April 18, 18:00 UTC exact instrument, static reachable pairs change from four to three and maximum bridge loss from 1.0 to 0.0 when timestamps must increase. The removed path combines an 18:04 message with an 18:01 message. Four windows are unchanged across every instrument. These are reference-pattern diagnostics; correctly ordered mentions still do not establish message delivery or influence. Bounded exact-source temporal packets now accompany prospective investigator and skeptic work, without changing existing candidate statuses.

```powershell
python -m swarm_lab.cli audit-temporal-paths SELECTED_AUDIT_ID --version 1
python -m swarm_lab.cli replay-temporal-paths TEMPORAL_AUDIT_ID --version 1
```

The [source-lineage workflow](research/theory/source-triangulation-plan.md) separately scans bounded JSONL/gzip files and checks explicit exported message/session keys. Its repeated real-data prefix probe retained131 rows and reproduced three scoped links across four partial scans, preserving93 unresolved parents and seven absent keys. These known examples do not establish corpus prevalence, April-window corroboration, delivery or tool success. Raw provider payloads and transcript text are not persisted in these audits. A fresh replay rereads exact row/line/prefix bytes and independently recomputes the saved plan and source-linked diagnostics.

```powershell
python -m swarm_lab.cli scan-source-links --plan .runtime/protocols/source-lineage-probe-20261004.json
python -m swarm_lab.cli replay-source-links SOURCE_AUDIT_ID --version 1
```

The Research audit view displays scan coverage, field-checked examples, unresolved cases and exact replay bindings, with a zero-model-call reread button. The example plan uses this laptop's local chat file and read-only V: mount; other sources need an explicit bounded plan.

A separate event-index workflow scans a declared bounded source into an exclusive local SQLite artifact. It retains typed identities, timestamps, action fields and value hashes, with raw-row/line byte pins. It excludes transcript text and provider output. A query authenticates the closed index bytes before comparing its speech fields with the original selected chat windows. Complete file coverage, local artifact authentication and field consistency are separate checks; none establishes recipient exposure or influence. Replay reopens the local index and reproduces the frozen selected-source audit. It does not download or freshly reread the whole remote event object.

```powershell
python -m swarm_lab.cli build-event-index --plan EVENT_INDEX_PLAN.json
python -m swarm_lab.cli audit-indexed-events INDEX_ID SELECTED_AUDIT_ID --index-version 1 --selected-audit-version 1
python -m swarm_lab.cli replay-indexed-events INDEXED_AUDIT_ID --version 1
```

The JSON build plan requires `source_path` and permits explicit row, compressed-byte, expanded-byte, row-byte and wall-time caps plus declared source metadata. The host chooses an unused destination under the runtime directory. Partial scans retain their stop reason and cannot establish absence. Action counts require explicit room and time fields; an event lacking a room is never assigned to one from the agent's activity. Human messages have a separate denominator because the current emission check targets `AGENT_TALK` records. `scripts/index_selected_events.py` runs the mounted-source probe and can reuse its saved index with `--index-id`.

The completed mounted-source scan indexed all 381,610 exported events, passed gzip integrity, and matched the declared object's compressed size and MD5. The six selected chat windows contain 250 agent and 99 user messages. Every selected agent message has one matching exported emission with consistent actor, room and canonical content hash; the user records remain outside the AGENT_TALK provenance test. The [indexed-event interpretation](research/theory/indexed-events-interpretation.md) preserves exact source references and the export-naive UTC timestamp assumption. Complete exported-file coverage does not establish completeness of real activity or recipient knowledge.

The separate [actor/time observation](research/theory/actor-time-observation-contract.md) selects four exact authors from those agent chat records, then queries their original time windows without a room predicate. Its authenticated production audit retained 183 platform records: 16 WAIT, 84 START and 83 STOP, all with missing rooms. These were outside the earlier room-scoped action query. Their absence from that query therefore cannot establish inactivity. The new audit preserves actor and source pins, missing-room diagnostics and a fresh local-index replay; it constructs no room assignment, successful lease or delivery claim. `scripts/actor_selected_events_probe.py` reuses the existing index under a new durable job identity.

The [literal wait-marker instrument](research/theory/wait-marker-alignment-plan.md) retains exact UTF8 source identities and codepoint spans for eight fixed ASCII words, then compares recorded-coordinate proximity to same-actor platform WAIT/PAUSE events. Its [saved interpretation](research/theory/wait-marker-interpretation.md) reports 34 marker messages and 32 deterministically selected nonmarker comparisons. At 300 seconds, 7 marker messages and 5 comparison messages have candidate events. Missing rooms, unknown clock relationships, censoring and event reuse remain explicit. These counts are not semantic classifier accuracy, inactivity or a causal effect.

Public commands expose exact source versions and bounded work. Replays authenticate their saved upstream sources and current producer bytes, with no hosted model requests. Actor/time and marker replays reopen the authenticated local event index; they do not reread the complete remote event object. Edge-flow replay freshly reproduces its frozen temporal parent; it does not add verified contacts or a physical traffic model. The [selected edge-flow interpretation](research/theory/selected-edge-flow-interpretation.md) preserves natural energy units, all extraction variants and numerical limits.

Both prospective research roles now receive [bounded recorded observations](research/theory/recorded-observation-context.md) of their exact original comparison. Actor/time, marker/control proximity and all four edge-algebra variants retain separate stored-proof and current-producer gates. Fresh source attestation remains false during context reading. Newest failed or stale matching proofs withhold summaries. Observation IDs do not become eligible source-message citations, and candidates are not promoted. New library registrations retain the immutable context-bearing proposal snapshot through `research_attempt_ref`; resumed reviews validate source and measurement bindings before constructing the model harness.

```powershell
python -m swarm_lab.cli audit-actor-events INDEX_ID SELECTED_AUDIT_ID --index-version 1 --selected-audit-version 1
python -m swarm_lab.cli replay-actor-events ACTOR_AUDIT_ID --version 1
python -m swarm_lab.cli audit-wait-markers ACTOR_AUDIT_ID --version 1 --max-controls 32 --max-work 1000000
python -m swarm_lab.cli replay-wait-markers ALIGNMENT_ID --version 1
python -m swarm_lab.cli audit-edge-flow TEMPORAL_AUDIT_ID --version 1 --max-work 10000000 --max-memory-bytes 16777216
python -m swarm_lab.cli replay-edge-flow EDGE_FLOW_AUDIT_ID --version 1
```

The Research audit view displays these observations and exact-version replay controls. The standalone report includes them only after a fresh read-only derivation matches the saved payload and code pins. Its CLI includes the optional sections by default; `--no-actor-events`, `--no-wait-markers` and `--no-edge-flow` omit them explicitly. The Python collector defaults these potentially expensive sections off.

A separate [conditional timing reference](research/theory/temporal-null-methods.md) holds each selected graph fixed and permutes timestamps among edge-bearing message groups. The actual 24-cell, 64-draw reference reproduces from the frozen source extraction. The April 18 exact graph has three temporally reachable pairs; 49 of 64 permuted schedules have four, and 15 have three. These are descriptive rank counts under an unvalidated exchangeability assumption. The same selected data do not supply confirmatory significance or independent replication. The Research audit view displays the original metrics, envelopes, rank counts, undefined cases and a zero-call replay action.

```powershell
python -m swarm_lab.cli audit-temporal-reference TEMPORAL_AUDIT_ID --version 1 --resamples 64
python -m swarm_lab.cli replay-temporal-reference REFERENCE_ID --version 1
```

The [checkpointed research cycle](research/research-cycle-contract.md) composes the existing environment authoring, registration, four allowlisted runners, independent replay, finite fact checks and guarded hypothesis curation. Its declarative plan pins the exact behavior, dataset and discovery as `{kind,id,version,hash}` references. Choose a supplied proposal/review, an exact approved blueprint, or `research_live=true` for model authoring. `subjects_live` is a separate flag. Explicit `max_new_model_calls` sets an immutable ceiling within the global cap; offline cycles authorize zero. Unsupported capabilities and unapproved world fit remain durable blocked results rather than fallback worlds. This is an optional executable composition, not a fixed taxonomy of swarm behavior.

```powershell
python -m swarm_lab.cli start-research-cycle --plan CYCLE_PLAN.json
python -m swarm_lab.cli resume-research-cycle CYCLE_ID
```

Resume keeps saved flags, seeds and budget and recovers known completed executions without rerunning subjects. Uncertain completion requires reconciliation or an explicit amendment. Isolated software tests check these engineering contracts; they are not empirical evidence for the Village hypothesis. A curated theory remains scoped to its registered world and finite facts, with generalization unestablished.

Checkpoint updates use atomic compare-and-put with bound child/root job closures. Concurrent resumes cannot overwrite a later completed checkpoint or repeat an authenticated execution. A completed resume returns its exact checkpoint; it is not a new source attestation. A changed construct or world requires a new hash-bound review; missing review and execution remain unknown.

The [intervention timing methodology](research/theory/intervention-timing.md) specifies a single observable event-triggered note with abstention, one receipt, no fallback and nondelivery retained in the policy estimand. Its new registered resource runner compares active and neutral private notes in separately reset paired worlds, holding each pair's full scheduler and resource-release path fixed. Trigger choices are first decision, executed wait with independent work pending, and observed resource reopening. Context persists after delivery; constructed requests and source archives replay independently. Proposed-action interception and sequential randomization remain unsupported.

```powershell
python -m swarm_lab.cli design-timed-resource --trials-per-cell 2 --seed 6149 --trigger executed_wait_independent_pending
python -m swarm_lab.cli experiment-timed-resource TIMED_PROTOCOL_ID
python -m swarm_lab.cli audit TIMED_RESULT_ID
python -m swarm_lab.cli evaluate-claims TIMED_RESULT_ID
```

Finite fact checks require exact source/result versions, replay and numerical consistency. Failed runs expose registered assignments and execution metadata only. Reviews bind the current result version/hash; explanations and mechanism claims remain unverified.

The current source-linked access investigation retained 2,000 September AI Village messages and a skeptical rejection of a distinct-mechanism claim. Its new single-document reference-recovery test used four live two-role teams, two matched pairs and 64 real subject decisions. Both notes solved 2/2 verified repaired references; the paired estimate was zero with a saved 95% interval from −100 to +100 percentage points. Both conditions shared the clear goal that the auditor actually opens the current original; this demonstrates task feasibility, not note benefit. Fresh replay and deterministic fact checks passed. Benefit, equivalence, novelty and historical causality are not established. [Village evidence and results](docs/real-results.md) names the exact records and limits. Runtime evidence remains local and ignored by Git.

`BUILD_STATE.json` tracks the ten-hour build and the thread heartbeat. The scheduler wakes this chat every fifteen minutes to continue work, checking active jobs first to avoid duplicate experiments. It is not a detached worker that survives every machine or app shutdown.

## Submission and user-flow checks

The review plan is in [docs/delivery-plan-20261005.md](docs/delivery-plan-20261005.md). The [Village-only project write-up](docs/submission-writeup.md), [source-grounded demo script](docs/demo-script.md) and [Village evidence/results note](docs/real-results.md) explain the current product and scientific limits. Demo entry: open the connected AI Village source, inspect its real investigation, then open its exact reviewed access plan, world and completed result; pending outcomes remain unknown. Machine-readable predeclared scenarios exercise 180 backend and 192 browser-controller transitions with independent expected-state models; these isolated fixtures do not establish model behavior. The separate real-agent journey freezes subjective expectations before execution, records failures and repairs, and checks actual UI, tools and immutable result records. Secrets, local databases, source caches and dataset files are excluded from the code handoff.
