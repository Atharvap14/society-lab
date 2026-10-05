# Constructing experimental worlds without pretending to reproduce history

Working environment framework, 4 October 2026. These are capability dimensions and construction requirements. They leave task-specific design open.

Current availability is summarized in [construct status](construct-status.md): four compiler families support six study interfaces when the separate timing and revision-relay protocols are counted. The latter adds a fifth distinct world. The dimensions and experiment families below include proposed extensions; listing them does not assert an implemented compiler capability or historical fidelity.

## Three uses of history

Historical replay can inspect recorded states and score detector decisions against information available then. Branching simulation generates new futures from reconstructed state. Executable sandbox validation runs actual tools against controlled task worlds. Label these modes separately.

Dream-RSI reuses realized discovery trees to compare search policies over already executed nodes. Its exactness is limited to the covered search space. Ordinary society transcripts rarely contain outcomes for every alternative message or intervention, so they cannot be treated as exact counterfactual simulators. We borrow the separation between historical reuse and fresh execution, not an assumption that changing agent context preserves observed futures. [Dream-RSI authors' project](https://dream-rsi.com/).

## Fidelity is a vector

| Dimension | Available choices | Validity question |
|---|---|---|
| Task semantics | Abstract game; analogous workflow; reconstructed task | Are the constraints that matter to the hypothesis preserved? |
| Communication | Broadcast, directed chat, private messages, handoff queue, shared artifacts | Who can receive what and under which delivery/ordering rules? |
| World execution | Scripted lookup, explicit state machine, executable filesystem/tools, browser sandbox | Does action feedback follow testable world rules? |
| Information | Shared facts, asymmetric facts, delayed access, redaction, noisy evidence | Does each subject see only its assigned knowledge? |
| Incentives/resources | Shared score, individual goals, competing goals, budgets, scarce resource rules | Could rewards or constraints explain the behavior? |
| Continuity | Fresh prompt, reconstructed context, persistent memory, supported checkpoint | What is restored and what remains approximated? |
| Agent/harness | Original known model, substitute model, fixed policy, multiple harnesses | Is the result about coordination or backend differences? |
| Time/scheduling | Turn-based, asynchronous, timeouts, controlled latency, real elapsed time | Does waiting reflect policy or runtime scheduling? |

Higher visual detail does not imply higher causal validity. Begin with the smallest world that preserves the suspected mechanism, then vary a meaningful fidelity dimension to test whether the finding transports.

## Environment construction contract

Every generated environment needs:

- Provenance: source evidence IDs, branch point, source version, and reconstruction decisions.
- Subjects: identities, roles, initial contexts, model/harness configuration, and allowed tools.
- World state: resources, artifacts, access rules, constraints, and transition functions.
- Communication rules: delivery permissions, ordering, visibility, and what is logged.
- Intervention capability: eligible boundaries, allowed channels, requested versus actual delivery logs.
- Reset: explicit state reset and verification, including files, memory, and shared caches.
- Evaluation: executable checks and any frozen semantic rubric.
- Limits: missing original context, substituted tools, approximate incentives, and unsupported capabilities.

Useful API concepts are `construct`, `inspect`, `reset`, `observe`, `step`, `inject`, `evaluate`, and `export_trace`. Their concrete signature should emerge from implemented scenarios. A runtime must reject unsupported operations rather than silently emulate a different treatment. Idempotency, event IDs, immutable run metadata, and isolated state are more important early than an elaborate universal ontology.

## Prompt construction

Separate experimenter metadata from subject-visible context. Subjects receive task rules, available tools, and their assigned information. They must not receive the original future, the target behavioral diagnosis, expected effect direction, treatment-arm name, or an evaluator's hidden rubric unless the protocol intentionally gives it to every arm.

Do not make the baseline prompt incompetent to make an intervention look effective. Compare reasonable baseline coordination and preserve its natural ability to request clarification. If roles, incentives, or tools differ by arm, declare them as part of the treatment.

Adversarial world content such as a misleading completion claim is task data. It must not become an instruction to the research harness. Keep credentials and external production actions outside generated experimental worlds.

## Independent environment review

An environment builder writes the world and unit-level consistency checks. A separate review checks information leakage, reset behavior, constraint enforcement, solvability, and whether outcome checks actually implement the stated construct. Review the world without telling the reviewer which arm should win.

Good review questions:

- Can a subject retrieve a private fact through an unintended tool or shared file?
- Are deadlines and resource limits enforceable, rather than just mentioned in a prompt?
- Are reported successes backed by world state?
- Is a failure caused by a hidden impossible task or a broken tool?
- Does the intervention alter opportunity or budget as well as content?
- Do equal states produce equal scripted tool responses, while stochastic model outputs remain honestly stochastic?

## Experiment families the environment may support

The framework should not require every family initially.

| Family | Main manipulation | What it can probe |
|---|---|---|
| Content steering | Active versus neutral private insertion | Effect of the inserted instruction package |
| Timing | Early, eligible-triggered, or delayed insertion | Timing-policy effect; use a fixed eligibility rule |
| Network position | Randomized recipient in controlled graph | Spread and repair under known communication opportunity |
| Treatment saturation | Randomized fraction of agents treated | Direct and spillover effects with a justified exposure model |
| Evidence distribution | Same claim with shared versus independent sources | Dependence on information lineage |
| Role/authority cues | Same content attributed to different protocol roles | Response to attribution under matched access/budget |
| Memory | Qualified versus compressed memory | Persistence and qualification loss |
| Constraint stress | Tool loss, scarce resources, delayed messages | Recovery mechanism and robustness |
| Harness transfer | Fixed experiment across explicit backend configurations | Scope and transport of a supported effect |

Factorial experiments can distinguish interacting factors but require more runs and careful estimands. One-factor pilots are useful for operational learning. Neither approach automatically proves a mechanism.

## Stop conditions for environment automation

Return a bounded construction failure when the available evidence cannot establish branch state, when tool behavior is unavailable, when reset or isolation cannot be verified, or when outcome validity is unresolved. Preserve the attempted reconstruction and propose a narrower executable analogue. The generator should not fill crucial unknowns with confident prose and call the result high fidelity.
