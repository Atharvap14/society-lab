# Optional measurement instruments

The observatory keeps its deterministic phrase detectors as a separately named instrument. An optional typed model measures the same narrow, public-text observables; an unavailable model raises an operational error. It never silently becomes regex and never converts a missing answer into a negative label.

The implemented instruments are `LayaBackend` (in-process Python), `LayaProcessBackend` (persistent isolated Python worker), and `JevHTTPBackend` (TypeSafe-compatible HTTP). `measure(message, definitions)` returns scores, decisions, abstention reasons, schema/content hashes, model metadata, runtime and usage. `classify(message, definitions)` provides the bool/null adapter accepted by discovery. Inspect `last_measurement` or persist the rich result when using that adapter.

When a backend call fails, `measure()` raises. A caller that retains the communication graph can explicitly persist `backend.failure_record(message, definitions, error)`: every observable is null, with `status=operational_failure` and `fallback=none`. Those records are neither negative measurements nor regex results. A constructor failure, such as a missing Jev key, must be represented as the selected instrument's unavailable status before processing messages.

## What the instruments measure

Definitions are atomic source-text statements: task commitment, completion report, evidence request, blocker report, correction, human help request, acknowledgement, and plan change. They do not establish that work succeeded, that evidence exists, that a speaker is deceptive, or that another agent adopted a belief. Quoted claims are excluded from the author's own completion report. The definitions remain editable and versioned; this is a starting instrument set, not an ontology of agent society.

Every question supplies explicit true/false criteria. Probabilities at or below 0.2 become false; probabilities at or above 0.8 become true; intermediate scores abstain. These prespecified thresholds have **not** been calibrated on Village communication. Provider abstention overrides a threshold decision. Missing, malformed, non-finite and out-of-range probabilities abstain with a reason. Unrequested labels or an untyped response fail the contract.

Inputs over 2,000 characters abstain without truncation. Laya additionally checks a 200-token state budget with the actual checkpoint tokenizer and fixes the total budget to 512 tokens. The English checkpoint is fixed to bound downloads; unsupported scripts abstain. English-script text is not necessarily English, and no language-accuracy claim follows from this gate. A failure to load the checkpoint or tokenizer is an operational failure, not abstention due to ambiguous text.

## Laya

The integration uses the published `Router.predict(state, questions, model="english", max_len=512)` API on CPU. Only the English model is selected; multilingual routing and eager preload are disabled. The checkpoint is `convaiinnovations/laya` at revision `7b928d828b7b0e022f929d9bd2e44165aa270148`; the isolated package is `laya==0.3.26`. Package and dependency versions are operational metadata, not a claim of immutable base-tokenizer resolution. [Official Laya repository](https://github.com/NandhaKishorM/laya), [published package](https://pypi.org/project/laya/).

Upstream documents option-label bias in the English checkpoint. This adapter explicitly uses a neutral-label schema variant, `true: A, false: B`, while keeping the semantic criteria. The schema hash records that variant. It is not a fitted calibration or a promise of correctness. [Laya known limitations](https://github.com/NandhaKishorM/laya#known-limitations).

The worker confines dependencies to `.runtime/laya-venv`, uses `.runtime/laya-cache` for Hugging Face downloads, and removes OpenAI/Jev credentials from its environment. It limits CPU libraries to one thread, uses a 90-second startup/inference timeout, and checks available physical RAM before importing the model runtime. A conservative 2.5 GiB minimum is an operational estimate for the 421M-parameter checkpoint, not a measured peak guarantee. Windows availability is read from `GlobalMemoryStatusEx.ullAvailPhys`; pagefile capacity does not qualify as free physical RAM. Resource uncertainty, startup, timeout, worker exit and malformed protocol messages produce visible failures. `on_status` receives worker phases for prompt progress/error display. No model training, fine-tuning or corpus download occurs. Model weights use the Hugging Face downloader.

```powershell
python scripts/benchmark_classifiers.py --backend laya-process --limit 16 --output .runtime/laya-benchmark.json
```

## Jev-compatible HTTP

The verified primary contract is `POST https://api.typesafe.ai/v1/systemone`, bearer authentication, and a body containing `model`, `state`, and typed `questions`. The adapter requests `jev-1.13.0` and reads `answers[label].noul`. Returned model/version and usage remain recorded. The provider can change remote behavior even when a version name is requested. [TypeSafe API reference](https://docs.typesafe.ai/api), [noul primitive](https://docs.typesafe.ai/primitives/noul).

Supply `JEV_API_KEY` or `TYPESAFE_API_KEY`. An OpenAI project key or Hugging Face token is not accepted as a substitute. The adapter requires HTTPS for remote endpoints, does not forward bearer credentials through redirects, bounds responses to 1 MiB, and has no retry or alternate-provider fallback. An explicitly configured unauthenticated loopback endpoint can exercise the same wire contract locally. No Jev provider key was available during this implementation, so HTTP model quality remains untested.

```powershell
python scripts/benchmark_classifiers.py --backend jev --output .runtime/jev-benchmark.json
```

## Independent diagnostic

`scripts/benchmark_classifiers.py` contains 16 authored synthetic messages and boolean gold labels fixed before inference. It includes tentative commitments, negations, quoted completion claims and ordinary waiting. The fixture fingerprint, definitions, model probabilities, abstentions and partial operational failures are saved. Regex is explicitly selected with `--backend regex`; it is never the fallback for a failed model.

Per observable, the diagnostic reports true/false positives and negatives, coverage, precision, recall including abstained positives, selective accuracy, and Brier score when probabilities exist. An abstention is not counted as a correct negative. Tiny synthetic checks can expose contract mistakes and prompt sensitivity, but cannot establish corpus accuracy, field calibration, causal validity or superiority of one backend.

To evaluate on Village, freeze a sample and annotation policy before model execution, retain adjudicated disagreement, report performance by room/language/length/quoted speech, and keep detector errors in the uncertainty attached to candidate behaviors. Do not use the discovery model's own approval as independent measurement validation.

## Verification record

Fifteen unit tests verify typed response validation, threshold boundaries, invalid probabilities, explicit abstention, schema variants, credential separation, bounded inputs, actual `Agent.tok` token-budget use, physical-memory gating, subprocess status/error delivery, provider truncation and independent scoring. The regex diagnostic completed all 16 messages: completion-report precision was 0.5 (one true positive and one quoted-speech false positive), with full coverage. The other seven observables each had one authored positive and no observed errors on this tiny fixture; this is too little evidence to claim deployment accuracy.

The published Laya package installed successfully on Windows Python 3.12, with torch 2.14.1 and transformers 5.18.0. Runtime installation occupied about 0.80 GiB. The two-message real worker request returned `operational_failure` in 0.41 seconds because only 0.41 GiB of free physical memory was available. No checkpoint load or inference occurred. The owned checkpoint prefetch was stopped after approximately 3.43 MiB of tokenizer/config data; no full weights or Village data were downloaded. `.runtime/laya-benchmark.json` records the failed request and `.runtime/regex-benchmark.json` preserves all 16 original measurements. **Laya classification quality is untested on this machine**; do not infer successful inference or calibration from passing contract tests.

The pinned official model repository contains no ONNX or INT8 files. Community conversions were not substituted. Upstream's export guide warns that quantization can change decisions and probabilities, so a future quantized instrument requires its own provenance and validation. [Official quantized-export reference](https://github.com/NandhaKishorM/laya/blob/main/docs/reference/agent.md).
