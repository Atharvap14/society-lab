# Behavioral identifiers as scientific instruments

Cheap classifiers make broad screening possible, but their outputs are annotations rather than facts. This guide applies to lexical rules, Laya/Jev typed decisions, larger semantic judges, and graph-derived annotations.

## Define the construct before choosing a backend

Start with observable acts and their exclusions. “Accepts responsibility for exporting artifact A before deadline D” is narrower than “cooperative.” A completion claim is a statement; verified discharge requires separate task evidence. Document the event or episode unit, available context, permitted labels, abstention, and adjudication rule.

Store the raw record ID, context boundary, backend/model/router version, question text, label definitions, configuration, raw response, calibrated output if available, and detector version. A prompt change can alter the instrument even when the model is fixed. Scores from different backends need separate validation; their numerical similarity is not equivalence.

## Build a representative validation sample

Include ordinary activity, detector-triggered cases, hard negatives, ambiguous context, and multiple rooms/tasks/time periods. Record sampling weights. Do not validate solely on examples the detector already recognizes. Split by episode or task where adjacent messages share context, rather than randomly scattering correlated messages across train and test.

Use independently annotated samples and adjudicate disagreement with source evidence. Preserve ambiguous cases; forcing one label can hide construct uncertainty. A synthetic test set validates chosen cases, not population performance in natural traces.

## Measure what matters

Report precision, recall, abstention rate, and confusion counts on the stated unit; use appropriate uncertainty for the sample design. Rare-behavior screening is sensitive to false positives. A high overall accuracy can coexist with poor precision for the rare label. Validate confidence calibration before treating thresholds as probabilities. Fit thresholds on separate data and freeze them before confirmatory evaluation.

Measure each important slice: model family, task, room, time regime, language, context length, and available evidence. A detector can fail when a tool format changes. Temporal degradation is an instrument-maintenance problem, not automatically behavioral drift.

For compound motifs, validate the component acts and the linkage logic. A correctly labeled completion claim plus an incorrectly resolved artifact reference can create a false coordination failure. Report pipeline-level error as well as per-message accuracy.

## Separate screening from outcome measurement

Use a broad screen to retrieve candidates, then inspect exact evidence. Do not let the same detector both select an incident and serve as unquestioned proof of its existence. Confirmatory outcomes should use frozen criteria and, when feasible, independently checked or executable measurements.

When intervention wording changes how agents speak, a text-based metric may change without a corresponding change in action. Track world-state outcomes and behavioral annotations separately. Blinded evaluation helps but cannot eliminate all construct leakage.

## Publish uncertainty and failures

Keep false positives such as normal scheduled waiting, missed behaviors, ambiguous cases, and failed backend calls. Do not replace absent responses with negative labels. Budget exhaustion and unavailable tools are operational outcomes. Store unavailable measurement as unavailable, not zero.

A research agent may propose improving prompts or skills from a measured failure. Version the correction and retest on held-out cases. Avoid accumulating universal rules from one example or repeatedly tuning on the eventual confirmatory set.
