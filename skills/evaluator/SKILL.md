---
name: evaluator
description: Judge recorded agent behavior against frozen criteria using executable checks and evidence-backed semantic annotations with blinding.
---

# Behavioral evaluation

Read [evaluator prompt](../../prompts/evaluator.md). For detector calibration and measurement drift, read [measurement validation](../../research/theory/measurement-validation.md). Use only the assigned trace, world checks, and rubric. Keep per-run judgments separate from aggregate causal analysis.

Prefer executable outcomes. Semantic judgments need supporting and contradicting event IDs plus an abstention option. Do not treat self-reported completion as actual success, acknowledgement as acceptance, or absence of evidence as disproval unless the rubric justifies it.

Preserve rubric version and detector/backend version. Treat Laya/Jev confidence as uncalibrated until held-out domain validation; thresholds do not automatically transfer across backend, language, question type, or option count. Rule-based or scripted substitutes must identify themselves.

Remain blind to arm labels and expected directions where feasible. Report compromised blinding when labels, filenames, or insertion content reveal assignment. Do not tune judgments after seeing which arm performs better. Report missing evidence, judge disagreement, and measurement limits.

Interpret each metric according to its actor, artifact version, and outcome condition. Inspecting a wrong artifact is not verification, and another agent's inspection is not the publisher's inspection. Removing digits from prose does not ensure consistency: check qualitative claims such as “more,” “less,” or “improved” against computed outcomes and operational definitions. Retain a superseded interpretation with its correction reason.

For the [relay oracle](../../research/theory/correction-relay-implementation.md), a correct final revision/modular answer can score without a canonical receipt; do not add an attachment or inspection gate. Explicit retain commits a draft; final waiting/invalid output scores zero, while interrupted infrastructure stays unknown. Availability, request construction, reported reasoning and correctness do not establish semantic uptake. Apply the supplied rubric rather than inventing a mechanism score.
