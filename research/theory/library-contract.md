# Archiving behaviors, hypotheses, and experiments

This is a minimum scientific record, not a fixed ontology. Unknown fields remain unknown. Implementation may extend it as different mechanisms are discovered.

## Behavior record

Recommended keys:

`behavior_id`, `version`, `name`, `definition`, `unit`, `scope`, `observable_criteria`, `exclusions`, `measurement_version`, `evidence_ids`, `episode_ids`, `counterexample_ids`, `alternatives`, `novelty_status`, `status`, `theory_ids`, `experiment_ids`, `limitations`, `created_at`, `updated_at`, `change_reason`.

Definition should identify an observable sequence or relation. Scope identifies tasks, agents, information conditions, and harnesses where observations were gathered. An emotionally evocative name should not replace observable criteria. Status needs a review reason, not just a string.

## Theory record

Recommended keys:

`theory_id`, `version`, `proposition`, `variables`, `causal_model`, `assumptions`, `predictions`, `boundary_conditions`, `rival_theories`, `falsifiers`, `source_behavior_ids`, `supporting_experiment_ids`, `conflicting_experiment_ids`, `replication_ids`, `scope`, `status`, `limitations`, `change_reason`.

Example proposition: “With a fixed underlying evidence lineage, additional explicit peer repetition increases adoption of an unsupported completion claim.” This is a candidate. It can be false, or hold only under particular channel and role conditions. Its observation record and causal-test record should remain distinct.

## Experiment record

Recommended keys:

`experiment_id`, `protocol_version`, `registered_at`, `status`, `question`, `estimand`, `population`, `unit`, `environment_version`, `fidelity`, `harness_versions`, `model_versions`, `prompt_hashes`, `treatment`, `controls`, `assignment`, `eligibility`, `outcomes`, `analysis_plan`, `stopping_rule`, `budget`, `reset_checks`, `blinding`, `run_ids`, `deviations`, `effects`, `uncertainty`, `assumptions`, `limitations`.

Preregistration means protocol freezing before relevant confirmatory outcomes are available. A retrospective JSON file is not preregistration. Exploratory work may be valuable without that label.

## Evidence and integrity

Stable IDs should resolve to immutable original records, source versions, timestamps, and necessary context. Derived annotations should retain detector/model/prompt versions. Do not overwrite evidence with a revised interpretation. Maintain links rather than duplicating sensitive source text into every library entry.

Store null findings, conflicting outcomes, unsupported capabilities, failed resets, aborted runs, and incomplete reconstructions. A library that only retains successful mechanisms becomes a biased research record.

Candidate discoveries can be exported for inspection without promoting their evidence status. A live API result or scripted demonstration does not constitute replicated behavioral science. Results need a plain-language scope statement and links to the protocol and raw evidence.
