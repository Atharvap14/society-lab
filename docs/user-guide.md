# Society Lab user guide

**A working laboratory for the behavior of agent teams.**

Contributors: **Atharva Pandey** and **Gautam Jajoo**. AI Village source data is credited to AI Digest; adapted Observatory ideas and their limits are recorded separately.

Society Lab connects recorded agent activity to a research workspace. Its AI guide retrieves evidence, investigates competing explanations, helps design a controlled question, asks research agents to review an executable world, runs fresh LLM teams and explains source-bound results. Work can branch across projects and chats; it is not a mandatory linear wizard.

This guide describes the current local product and its evidence boundaries. The current demonstration uses real AI Village messages and a separately registered document-reference experiment. Historical observations and newly executed proxy-world outcomes remain distinct.

## 1. Start the local application

Use a complete source checkout with Python 3.11 or later. Keep `swarm_lab`, `web`, `prompts`, `skills` and `research` together. Run from the repository root; a Python wheel alone does not include the companion assets. The core uses the standard library. Install NumPy for spectral and Hodge analysis; Node.js is needed for executable browser tests. Matplotlib enables native scientific figures.

Supply `OPENAI_API_KEY` through your environment, or put the key in `.secrets/openai-api-key.txt`. Never put a credential in a study prompt, chat, import or committed file. Configure explicit request allowances before using the real guide:

```powershell
python -m pip install numpy matplotlib
python scripts/configure-guide.py --research-calls 400 --guide-calls 100
python -m swarm_lab.cli --max-calls 400 serve --port 8765
```

Open `http://127.0.0.1:8765`. The research cap must match the configuration command and server command. These are example limits, not the current laptop's remaining allowance. The call ledger persists across restarts and includes reserved or failed calls; configuration does not reset it. A request allowance is not a dollar-cost estimate. Without a guide configuration, the guide reports `not_authorized`.

On Windows, `scripts/Start-Lab.ps1 -MaxCalls 400` starts a hidden background server and saves local logs. The saved research database lives under `.runtime`; a clean checkout does not contain this laptop's private datasets or results. Import your own authorized source to reproduce a source-dependent workflow. Keep `.runtime` and `.secrets` outside source control.

## 2. Choose your starting point

**Logs only.** Connect chat records or typed events. This supports observation, screening and source-grounded hypothesis review. Original tool state, permissions, private context and recipient knowledge may be missing. A new experiment then needs a separately reviewed environment, with proxy semantics and invented state disclosed. This is the AI Village demonstration's entry mode.

**Logs plus an environment.** Supply the logs together with a task, files and an existing environment/tool contract. A reviewed adapter must expose legal actions, scoped observations, reset, state transitions and an outcome oracle. The current interface does not automatically execute arbitrary uploaded code or reproduce any supplied service. Unsupported capabilities remain a construction gap; the system should narrow the question or require an adapter instead of silently substituting another world.

To connect an existing swarm, use `societylab.events.v1` and the standard-library client in `examples/observability_client.py`. Emit actual actor registrations, task transitions, addressed sends, tool invocations and returns, artifact updates and interventions. `reasoning.recorded` is an explicitly supplied local note or recorded rationale; it is not fabricated hidden reasoning. Events retain stable IDs and producer timestamps. A declared success flag remains a producer report unless independently checked.

The accumulated run limit is 2,000 events and 1 MiB. Exact batch retries are idempotent; conflicting reused IDs reject the update. Further batches create new immutable versions. Rotate to a new run before exceeding the limit. The browser can follow current versions without rewriting analysis attached to an older version. `GET /api/observability/schema` provides the full field contract.

## 3. Projects, chats and saved work

A **project** groups research. A **working chat** is your conversation with the guide. It is distinct from an imported agent chat, which is source evidence. Each working chat keeps its history, draft, selected source and linked artifacts after reload. Start another chat to explore a rival question without replacing the first.

The artifact collection holds sources, briefs, candidates, rubrics, plans, worlds, protocols, results, replay checks and theories. Exact scientific references contain an ID, version and payload hash. A title or a latest record with the same ID cannot replace that exact reference. The artifact map draws saved provenance relationships; it is not a social or causal network.

Type `@` in the guide to select a saved chat or item across projects. The selected chip carries identity; a name typed in prose is not an authenticated reference. Four operations have different meanings:

| Operation | What it does | What it does not do |
|---|---|---|
| Read another chat | Retrieves a bounded snapshot at an exact revision | Switch the active chat or turn discussion into empirical evidence |
| Reuse an artifact | Links the same exact version into this chat | Clone a result or create another observation |
| Make an editable copy | Creates a draft with an exact original reference | Copy outcomes or verification as fresh evidence |
| Fork a chat | Copies working state/history into a new branch, with origin | Launch new subject teams or claim replication |

Only owned drafts are edited; frozen scientific records remain unchanged. Editing a copy creates a new draft version. Saving a real new plan, simulator or execution produces distinct records. Background jobs capture their origin chat when launched. Switching chats does not redirect their outputs.

## 4. Work through the AI guide

The guide is present alongside the workspace. It can navigate views, explain exact saved evidence, read cross-chat context and invoke bounded tools when you explicitly request an operation. It uses the actual Responses harness and recorded request allowance. Deterministic quick actions are separately identified; they are not model answers.

Examples of concrete requests:

- "Connect this saved AI Village source."
- "Investigate these access reports and find ordinary counterexamples."
- "Using @this source, save a narrow plan to test whether a canonical-reference reminder changes peer opening. Keep both notes the same word count."
- "Build and review this exact simulator. Do not run subjects yet."
- "Run the reviewed simulator and explain its checked results."
- "Read @the earlier chat, then copy @its plan into this chat as an editable draft."

A generic discussion such as "what experiments could we run?" does not authorize paid subject execution. The guide operates only on authenticated references supplied in its context or actual tool receipts. Unknown references reject. Stable operation IDs prevent ordinary retries from creating duplicate effects; an interrupted or uncertain execution is not silently repeated.

The activity feed records actual started, completed, refused or failed operations and returned references. Working summaries describe the operation being performed. They do not expose hidden chain-of-thought, prove an agent's belief or manufacture intermediate research. Inspect the receipt when an answer says something was saved, built or run.

The callable tool families are source connection and discovery; source-grounded plan saving, simulator building and execution; project/chat creation, exact reuse, copying, editing and forking; rubric listing, saving and Laya measurement; bounded event neighborhoods; and exact cross-chat context reading. Their availability depends on explicit intent, visible references and the current product route. A tool catalog is not permission to run an arbitrary operation.

## 5. Connect and discover

Connecting creates a source-bound brief: agents and tasks when explicitly declared, recorded messages, addressing, tool reports and candidate signals. A cheap screen can identify a place to investigate, not establish a behavioral diagnosis. Text records are not silently converted into historical tool actions.

Real investigator agents retrieve exact messages, surrounding context, ordinary samples and counterexamples. They may inspect bounded typed event neighborhoods or recorded graph observations. The skeptic asks whether an ordinary task constraint, measurement artifact, missing opportunity or source limitation explains the pattern. Source citations must refer to supplied or actually retrieved evidence; this checks retrieval provenance, not semantic truth.

The research responsibilities are discovery, skeptic, environment builder, causal methodologist, evaluator and theory curator. Prompts, tools and skill files shape these harnesses. Responses provides structured outputs and function calls; a separate Codex research adapter can read an isolated evidence packet. Experimental subjects currently use Responses. Saved roles are responsibilities, not proof that every stage runs in parallel or independently reproduces a finding.

The current September source retained the earliest 2,000 posts inside a larger requested period. Later resolutions may be excluded. The access candidate was rejected as a distinct novel mechanism because ordinary URL transcription, browser/session friction and shared-document work remained sufficient explanations. A rejected candidate can still motivate a useful practical test; it cannot be presented as an established discovery.

## 6. From a question to an executable world

Start with a falsifiable question and rivals, not a fixed behavior ontology. Ask what could distinguish a reference problem from an ACL problem, a relay delay from an artifact prerequisite, or duplicated evidence from independent evidence. Graph anomalies can guide that question; they do not identify its mechanism.

A plan must state the source, hypothesis, target outcome, subjects, assigned conditions, timing, action budget, reset, analysis and incompleteness rules. A private context intervention inserts visible text into the actual subject request. It does not edit latent thoughts. Both arms need the same tools and delivery opportunity; equal word counts alone do not remove semantic differences.

The builder maps the question to supported capabilities. A causal reviewer can decline a world whose tools, information boundary or oracle do not support it. Small exploratory studies remain labeled as such. A compiled schema and a fit-approved analogue are different gates; neither establishes historical equivalence. Actual registration freezes world/code, model settings, notes and protocol before outcomes.

Inspect the fidelity card:

| Dimension | Questions to check |
|---|---|
| Task and tools | Which services are original, approximated or omitted? What does each action actually change? |
| Information | What is private, addressed, public or unknown? Are hidden truth and original future absent? |
| Timing and cost | What schedule, contacts, action limits and stopping rules are fixed? |
| Outcome | Is completion checked by an independent code oracle or merely asserted? |
| Subjects | Which fresh model/harness acts? Are original policies actually reproduced? |
| Transport | What limits prevent generalizing to the source setting or other models? |

Developer experiments also cover artifact verification, correlated-source diffusion, complementary information, exclusive-resource work, context timing and correction routing. They have separate capabilities and estimands; they are not interchangeable replacements for an episode. The current front-door demonstration uses the source-grounded single-document recovery world. A supplied environment requires its own reviewed adapter.

## 7. Run, evaluate and replay

An explicit run request starts fresh LLM subjects in the exact reviewed world. Subjects choose actions through the harness; deterministic proxy tools execute those choices. A deterministic environment does not imply scripted agents. Scripted callbacks used in software tests are infrastructure fixtures and are not the current product's subjects.

Each matched pair uses the same generated starting state and predeclared schedule, with isolated teams and randomized arm order. Assignment is at whole-team level; messages within a team are part of its treatment package. Agents are not independent statistical replicates. Failed choices consume the registered opportunities. Infrastructure failures retain assigned grids and partial traces; incomplete execution does not become a favorable complete analysis.

Result views separate success counts, rates, assigned teams, primary contrasts, uncertainty and descriptive process measures. An effect mean of 1 is a 100% rate, not one successful team. A narrow interval computed by an unsuitable method should not replace the registered interval. Post-treatment message volume, centrality or information coverage does not automatically identify a causal mediator.

Replay shows recorded posts or actual executed decisions and tool receipts. Its playhead displays prefix state, not knowledge of later events. It distinguishes local/private records, direct addressed messages, room posts, declared broadcasts and unknown audience. A declared recipient, shared room or mention is not proof of reading. A retained rationale is a decision summary, not hidden thought. Result HTML reports are rendered from exact saved facts, not arbitrary model HTML.

Fresh deterministic replay checks requests, scoped context, tool transitions and outcome reconstruction against pinned code. Finite claim checks authorize named numerical facts; they do not verify all narrative interpretation, provider consumption or historical service state. Replaying a saved result makes no new subject calls and is not an independent model replication.

## 8. What the current real run establishes

The new reference-recovery study ran four fresh two-role teams with 64 distinct actual model responses. One correct original, viewer permissions and initial authenticated profiles were fixed. The auditor's copied reference started broken. Both conditions shared the clear goal that the auditor actually opens the current original within 16 team actions.

The neutral note solved 2/2 teams; the canonical-check note solved 2/2. All four owners queued canonical references and all four auditors successfully opened the current original. Independent search was legal, so a queued handoff is not proven necessary. Only one team had a separate current-content inspection receipt. The primary checks executed opening, code-correct content and authorization, not comprehension.

The paired difference was zero, with a registered 95% bounded interval from -100 to +100 percentage points and sharp-null paired p = 1. This demonstrates feasibility, not reminder benefit, equivalence, historical causation or confirmed novelty. Two invalid-output choices were retained within the 64 opportunities. The earlier six-role/four-document pilot's 0/2 strict successes in each arm remain separate negative evidence. The task redesign itself was not randomized against that earlier study.

Exact result: `village_recovery_experiment-63d316aa7898`, version 1. Replay `verification-43d7bf1ace43` and finite facts `claim_audit-5362cc6f27dc` bind it. See the exact-result notes for hashes and limits.

## 9. Behavior library and measurement

The library retains source-linked proposals, evidence and counterexamples, alternative explanations, falsifiers, review decisions and linked tests. Theory records retain their scope and unresolved generalization. Candidate, rejected, hypothesis, infrastructure-tested, pilot-tested and replication-tested describe different stages; completion does not automatically make a mechanism established. Novelty and causal support are separate fields. Keep supporting and conflicting results rather than selecting a winner.

Eight adapted starter rubrics cover contributions, qualified information, dependencies, commitments, consequential advice, correction, returned help and shared-resource rules. You can save a custom prompt with positive, negative, unknown and non-example rules. The saved rubric and exact dataset are version-pinned before bounded screening.

Laya is a configured local prompt-defined text-screen interface. Missing runtime, RAM limits, inference failure or abstention remain unknown; no regex fallback supplies a score. On this laptop the memory guard blocked actual Laya inference, so no accuracy, throughput or calibration claim is available. Optional Jev-like/provider adapters are interfaces, not validated verifier performance. A message label cannot establish a whole opportunity episode, recipient exposure, task success or motivation; episode assessment stays not assessable unless its separate requirements are satisfied.

The measurement-review workflow freezes a seeded sample and operational binary question. Reviewers declare yes, no or uncertain labels, reasons and provenance. Uncertain and missing labels stay outside known-label confusion counts. Agent-assisted or synthetic declarations are not human ground truth; sample agreement is not population accuracy.

## 10. Graphs and advanced instruments

Communication/addressing graphs, temporal paths, spectral/Laplacian signals and Hodge decomposition are available as scoped measurement tools. The event evidence neighborhood traverses explicit saved references; the artifact map traverses research provenance. Keep these graph meanings separate. No centrality, circulation, bridge loss or name co-occurrence proves exposure, consensus or influence.

Short-name, Unicode, window and extraction choices can change a graph. Inspect the operator, node universe, source pins, missingness and sensitivity before interpretation. Unknown denominators stay unknown. Advanced source audits distinguish local saved-proof identity from a fresh source reread. A local authenticated event index is not a fresh download of all upstream data.

## 11. API and operational boundaries

The local server uses strict bounded JSON, exact references, CSRF protection and loopback-origin checks. Mutation requests capture an optional `X-Lab-Chat` origin. The standard client obtains the session token locally. Do not publish a session token or expose the local server as an authenticated multi-user cloud service.

| Route group | Purpose |
|---|---|
| `/api/workspaces` | Projects, chats, state, messages, exact reuse and editable drafts |
| `/api/guide/chat`, `/api/guide/activity` | Actual guide conversation and operation receipts |
| `/api/observability/connect`, `/brief`, `/follow`, `/graph` | Typed intake, source briefs, saved-version following and explicit event references |
| `/api/village-recovery/plan`, `/api/guided/simulator`, `/run` | Source-bound plan, actual model review and fresh execution |
| `/api/rubrics`, `/save`, `/measure` | Proposed instruments and bounded local text screens |
| `/api/object`, `/api/traces`, `/api/guide/report` | Exact saved objects, archived operations and safe fact-based reports |

Use the CLI for developer imports, exact-object inspection and advanced experiments. Some older offline commands deliberately use templates or scripted smoke policies; those outputs test infrastructure and are not evidence about LLM behavior. Current chat tools use real research/subject harnesses. Arbitrary JavaScript, generated code or unreviewed uploaded environments are not executed by the guide.

If an operation fails, inspect its receipt and retained artifact before retrying. A budget-unavailable response needs an explicit allowance change, not a hidden fallback. A stale edit needs a fresh exact revision. A source-fit refusal needs a narrower question or new reviewed world. Missing source access needs an authorized import; a saved display is not a fresh source attestation.

## Further reading

[Project write-up](submission-writeup.md) · [Current real results](SUBMISSION_REAL_RESULTS.md) · [Detailed source/results record](real-results.md) · [World fidelity](observed-and-experimental-worlds.md) · [Graph and Laya architecture](graph-and-laya-architecture.md) · [Question-to-design map](../research/theory/experiment-choice-map.md) · [Observability client](../examples/observability-client.md).
