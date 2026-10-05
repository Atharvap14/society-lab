# A prospective correction-relay experiment

Design draft, 4 October 2026. No subjects have run, protocol has been registered,
or new environment implemented by this note. This is the smallest useful next
causal probe after the communication and graph instruments, rather than another
description of the same selected windows.

## The gap and a falsifiable claim

[Multiplex communication](multiplex-communication-experiments.md) distinguishes
emission, reference, exposure, artifact transition and outcome. The
[operator agenda](graph-operator-research-agenda.md) proposes timing perturbations;
[selected edge-flow results](selected-edge-flow-interpretation.md) explicitly
discard order and cannot establish information transfer. None specifies a
prospective correction experiment that distinguishes an assigned relay-dependent
timing effect from an assigned direct-delivery effect. This draft supplies that
design, not an identified historical mechanism.

**Prediction:** delivering an update after the relay agent's first scheduled
decision reduces final downstream correctness more when the downstream agent
depends on that relay than when it also receives the update directly. A null,
reversed, or sufficiently small interaction under a prospectively chosen
precision criterion weakens this particular prediction. The result cannot
establish that agents have a stable reluctance to communicate, or that a
reference-graph bridge is indispensable.

## Small world and assignment

There are three roles: a scripted source service A and two model subjects, relay
B and downstream worker C. This is a two-subject swarm with an explicit source
fixture. A creates revision 1 and revision 2 of one measurement; their residues
are independently uniform modulo 97. C holds an independent private residue.
The final task is to report revision 2 and the sum of its measurement and C's
residue modulo 97. Revision 1 alone contains no information about that target
under this declared generator; a guess can nevertheless be correct with
probability 1/97. Exact correctness is executed reporting, not proof of mental
knowledge or reading.
Correctness requires the declared revision number and modular value, without
an attachment, hidden source hash or receipt qualification. The intervention
changes observable correction availability; private-context reminder efficacy
would require a separate registration.

Use a whole-team 2×2 randomized assignment:

| Factor | Level 1 | Level 2 |
|---|---|---|
| Update timing to B | Before B's first scheduled decision | After that decision, before B's second |
| Corrective bypass to C | Direct revision-2 packet before C's final decision | Matched noncorrective packet in the same slot |

Freeze these boundaries before subject responses. A first decision that waits,
refuses, or is invalid still counts; timing never triggers on whether B actually
relays. Each independent seed block contains four separately reset teams, one
per cell. Share only the precomputed truth, role information, and exogenous
schedule within the block. Randomize cell-to-execution order before outcomes;
do not share subjects, tools, memories, mutable files, or previous arm outputs.
Provider sampling is fresh and not made identical by a world seed.
Subjects see role rules and factual packets, without assignment labels,
researcher hypotheses, outcome feedback or another team's transcript.

## Delivery and sham schedule

| Boundary | Operation, identical opportunities in every cell |
|---|---|
| 0 | B receives revision 1; C receives its own private residue and task |
| 1 | B receives revision 2 in early cells, a noncorrective packet in late cells |
| 2 | B's first decision can forward a known record or leave its outbox empty; dispatch the resulting B→C container |
| 3 | C creates a provisional, explicitly revisable answer; no correctness feedback |
| 4 | B receives the other boundary-1 packet: noncorrective in early cells, revision 2 in late cells |
| 5 | B's second decision can revise/forward; dispatch its B→C container |
| 6 | A dispatches the informative bypass or matched noncorrective packet to C |
| 7 | C's second decision revises or retains its answer; this is the final score |

The noncorrective packet has a fixed typed record layout and pertains to an
unrelated artifact; its value is independent of the target. Freeze packet
wording, field lengths, source attribution and tokenizer lengths. Matching
format or length does not guarantee semantic inertness. B receives the same
packet multiset in early/late cells, but different ordering and available
information at its first decision: that difference is the treatment package.

Source records carry immutable artifact, revision, value and origin IDs.
Forwarding can attach only records available to B. Free-text narration may be
allowed under a frozen limit, separately logged and never accepted as an
authenticated attachment. Invalid actions consume their scheduled opportunity
and remain outcomes. Empty outboxes dispatch explicit empty containers; no
missing conversation is filled with invented content.
Freeze the canonical attachment cap and exact free-text rendering before
validation. A valid explicit final `retain` scores C's recorded draft; an
invalid or absent final action scores zero, without automatic carry-forward.

The permitted channel graph and host dispatch slots are identical. The
informative payloads, subjects' chosen content, and realized reference graph can
differ. Do not claim that name mentions or realized communication are held fixed.
Both arms have a legal corrective route before the deadline; late failure is
not forced by making the task impossible. C can receive the same direct
revision-2 packet in both bypass cells, while other messages and its provisional
answer may differ.

## Interference, estimand and scoring

Within-team interference is intended: B's assignment can change C's input and
answer. No cross-team contact is permitted. Assigned exposure is the timing and
bypass policy; realized exposure records recipient-scoped packet construction
at the provisional and final boundaries, exact source IDs and delivery logs.
Construction of a provider request is not proof of provider consumption.
Historical timestamps or mention edges are not used to impute exposure.

The **primary outcome** is C's final exact revision-2 modular-answer correctness,
scored in code; an absent or invalid answer is zero. The **primary contrast** is
the interaction

`(late − early under no corrective bypass) − (late − early under bypass)`.

Estimate its block-average value with block-aware uncertainty under the frozen
assignment design. Predeclare a minimum meaningful negative interaction,
sample size, inference rule, and missing/transport policy before confirmatory
execution. Shuffling all four labels tests a sharp global no-policy-effect
null, not zero interaction with possible main effects. Defer formal interaction
testing until an appropriate method is frozen; two blocks give only a very
weak pilot estimate. A small operational pilot cannot establish equivalence. Never
count agents, packets or four cells within one paired block as independent
replicates for its variance. No mediator is identified by this contrast: it is
the change in an assigned timing-policy effect under assigned bypass.

First drafts, B's corrective forwarding, C's visible source inventory, final
revision selection, and repair after the draft are secondary descriptions.
Do not restrict analysis to teams that relayed or received the correction.
Direct-source authority, repetition, salience, context order and differing
drafts can also change the interaction. These are explicit treatment-package
limits, not confounds silently removed by an exposure regression.

## What exists and what must be built

Existing code supplies uniform-residue oracles, isolated subject observations,
canonical lineage, reset checks, bounded action budgets, timed interventions and
replay patterns. Existing complementary reports and final submissions are
immutable; they do **not** implement this experiment. A new revision-capable
adapter needs source updates, fixed delivery slots, provisional/final answers,
outboxes, clock-independent scheduling, matched shams, and a new registered
runner. No existing frozen producer should be amended to create this treatment.

Before model execution, scripted policies must demonstrate success in all four
cells, including late/no-bypass, and intentional failures. Independent tests
must check no source leakage, no fabricated attachment, revision replacement,
empty/invalid decisions, action-independent schedules, complete resets and
oracle replay. Four fixed subject decisions per team give a nominal 32-request
two-block operational pilot; provider/tool retries require a separately bounded
budget. Infrastructure-incomplete execution retains partial artifacts and
suppresses effect estimation.

This preserves communication, asymmetric information and revision opportunities
at state-machine fidelity. It does not reconstruct Village browser use,
historical roles, persistent memory, incentives, or unobserved exposure. Follow
[causal experiment requirements](causal-experiments.md) and the
[fidelity vector](environment-fidelity.md); a positive result supports this
assigned policy in this task/model, not historical causality or a general theory.
