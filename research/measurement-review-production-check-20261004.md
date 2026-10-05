# Independent production check: frozen measurement sample

4 October 2026. This read-only check passed for the exact saved browser workflow below. It validates local sampling, source consistency, versioned declarations and presentation. It does not establish an accurate behavioral label, independent human adjudication, classifier calibration, population accuracy or a causal finding.

## Exact records

| Record | Version | Registry payload SHA-256 |
|---|---:|---|
| `dataset-5d2eef17db31` | 1 | `4351ceeb788cc000b6e288927299f20d68095e9a449a47bb6cef5e0791cc5c41` |
| `measurement_sample-4c473a7cfacd` | 1 | `9b9995b3a44cfbd153bbf32d061fa6303a0b7abab7bf1fc45e352170524094e0` |
| `measurement_review-4c473a7cfacd` | 1 | `35e56ccf79bc269a97059b93eee9868b7fa20667789c796eea269d908e086bc0` |
| `measurement_review-4c473a7cfacd` | 2 | `9789885f99670f042815e09a70399fc52c2085bf81a151bf904d981a104d4c85` |
| `behavior-4d47c2a27a29` | 4 | `eaf6460cd251c6c640477d5f1c990da388333567f2de9c9e76560ae0afb59f21` |

Each payload hash was independently recomputed with the registry's sorted finite JSON encoding. SQLite was opened using `mode=ro`, `query_only=1` and a read transaction; no Lab/Store constructor or persisting method was invoked. A second read-only connection checked the final registry counts and behavior hash. The public pure workspace was called using an exact-version read-only adapter, and actual GET responses from the running loopback server were compared canonically with that output.

## Checks performed

The sample contains 16 messages drawn without replacement from the canonical sorted IDs of all 588 retained messages in the pinned dataset, using seed 42. The draw order, population-ID digest, inclusion probability, sample size and one-neighbor context setting agree. The optional instrument is the named `blocker_report` regex; sampling was not restricted to its positive hits.

For every selected message and its bounded same-room context, original record and provenance hashes were checked against the retained dataset. Context selection follows timestamp/ID order and includes at most one message before and after each target. Source coordinates, full-content UTF-8 hash, excerpt, length, truncation flag and declared compound message hash agree. These checks do not reread or independently authenticate the remote/raw export. A declared compound hash and a full-content hash remain distinct quantities.

Review v1 has no judgments. Review v2 adds exactly one declaration for `33d0ee32-3f3b-481f-bdac-68918e18e030`: label `uncertain`, mode `agent_assisted`, reviewer ID `society-lab-browser-workflow-check`, with `predictions_visible=false`. Both versions bind the original sample exactly. The reviewer identity/mode and hidden-display declaration are supplied provenance, not verified human identity, independence, blinding or semantic ground truth.

| Report quantity | Initial v1 | Current v2 |
|---|---:|---:|
| Sample size | 16 | 16 |
| Known yes/no labels | 0 | 0 |
| Uncertain labels | 0 | 1 |
| Missing labels | 16 | 15 |
| Available predictions | 16 | 16 |
| Compared messages | 0 | 0 |

Confusion, agreement, precision and recall are `null`, with availability false. Uncertainty and missingness are not negatives, and no zero-accuracy claim is generated. Initial GET hides predictions; current GET shows them. Both exact historical/current GET bodies match the pure read-only workspace.

The current pinned cheap regex was independently re-evaluated on the original full selected **registry** contents. Saved predictions match, and `prediction_attestation=matches_current_pinned_regex`. This is a current consistency check, not an attestation of historical execution: `historical_execution_attested=false`. The current core hash is `01d29582f1b7eeaf216202869c8f2fe8ef3b074ab674256330b2b862cadb2427`; the public workspace wrapper hash is `a465f508501e85843d24a0477313daa28f327b432b26088e649ca2e42ce334f4`.

The sample queue job `job-02f97da024c8` and judgment queue job `job-3afbff80a2ae` are completed with the expected result identities. The ledger remains 400 calls: 397 completed and three failed. There are zero queued/running jobs. Registry counts remain 182 object versions, 400 call entries, 549 traces and 60 jobs. The behavior's latest version remains v4 with the exact hash above; no label, behavior or theory was promoted by this check.

The optional local check artifact is `.runtime/measurement-review-production-check-20261004.json`, SHA-256 `05e69cf689973dcc47c4fdb6e164cd9677fd164f816ac94fef3c7b9bded93a69`. Its 16 checks passed. It is an unregistered inspection artifact, not a new registry verification, experiment or finding. No provider calls, raw-source reads, registry writes or scientific-module edits were made.
