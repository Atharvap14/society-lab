# Independent production check: scripted correction relay

4 October 2026. This read-only check passed for the exact saved study below. It establishes functioning local infrastructure and reproducible scripted outcomes. It does not establish a model effect, an absence of a model effect, a historical communication mechanism, or a private-thought intervention.

## Exact records

| Record | Version | Registry payload SHA-256 |
|---|---:|---|
| `revision_relay_protocol-0c41a067f805` | 1 | `6a6d3f3971b86c7d5f42f162d10d7445fe635a8bdbcd46c4c2210ae9f50283d1` |
| `revision_relay_experiment-ce1209221caa` | 1 | `083f1d464a796149e2e72fbb96a79fa5aaa89d1f783e0831699a8e0fba8cead6` |
| `verification-8c2cca894899` | 1 | `a204fb9998165093b108bd76b2619e3878bdc208947cb7e8d8667003e4650e6e` |

Each stored payload hash was independently recomputed using the registry's sorted JSON encoding. The protocol's body hash is `7d6110d520bbd331c6d61dfaf3c54a4f0ae2802c865a1dc488907bfe1d7a4f81`; its complete frozen-protocol hash is `d89225a53a0029e9d39360a1da460abfbdeb7a05a83719a5924c573b3f2ec6b1`. These identities use compact JSON and are distinct from the registry wrapper hash.

The canonical execution-report hash, excluding its own hash field, is `d3d2cf4a4f559755c666e7d51fbb7a05ff58f9a509c9c57e93a75576a5def144`. The archived report file SHA-256 is `9fdbd19f2e56b2cc21ac7afe4956f2683eed2b276298eb8abc0377faf88c7c52`.

## Checks performed

SQLite was opened with `mode=ro` and `query_only=1`. No Lab/Store constructor, execution method, provider harness, registration method, or persisting audit method was invoked. Fresh replay used the pure `replay_revision_relay_report` function and saved no additional verification.

The result's exact protocol reference, backend, full frozen protocol, canonical report, archived JSON and source pins agree. All 12 registered archive files have their recorded byte lengths and SHA-256 values. The host archive and current host source agree; the four execution sources and two design documents agree with the frozen protocol. The archive resides at `.runtime/runs/revision-relay-b97d9db37f394d6e8f4b62cb6f3dd7f0/`, with the pure-runner artifacts in `execution/`.

The current [adapter](../swarm_lab/revision_relay_env.py) hash is `260421911d1cbec63f6c5481036574be2b1d6c42d750bb1758597701403ac808`; the [runner](../swarm_lab/revision_relay_experiments.py) hash is `547d25a3c12f12070db640f7abb6c8b94b7f90781683dcf273fcb28a6aa30f0c`; the [host](../swarm_lab/revision_relay_workflow.py) hash is `8d9221c4bb331bbcb30099ecb3c1698bbb4ef39eb9a75e51a1d2572be07fe355`. The pinned [design draft](theory/correction-relay-experiment-draft.md) and [methodological review](theory/correction-relay-experiment-review.md) also match their registered hashes.

The registered assignment list was reconstructed without executing subjects. Each of two seed blocks contains exactly one fresh team in each of four cells: early/late correction availability to B crossed with informative/sham bypass to C. Within a block, the recorded seed, source records, C-private residue, oracle, spec and exogenous schedule agree. Treatment-specific initial inventories are not asserted identical.

All eight teams are complete. Each has the fixed four decisions B2/C3/B5/C7, four exact local request receipts and four applied actions: 32 scripted decisions in total. Every request hash was recomputed; private contexts remain empty, and B's request excludes C's private residue and draft. Each team records the same six scheduled contact containers, giving 48 local dispatch records. Final answers were checked directly against `(revision2_source_value + C_private_residue) mod97`, with no attachment-receipt eligibility gate.

The saved UI verification has 13 successful checks bound to this exact result. Fresh pure replay independently passes its 11 checks, including all eight request/action/oracle traces and the complete-grid analysis. Its completion and quantitative-availability flags are true. The execution queue job `job-8fb807a97318`, fixed study claim `relay-study-29431d7b8c29c71fb19d38b5`, and UI audit queue job `job-7bbba52d248a` are completed with the expected exact result/protocol or proof links. Registration precedes execution.

## Independent arithmetic

| Assigned cell | Correct final answers | Teams | Mean correctness |
|---|---:|---:|---:|
| Early, sham bypass | 2 | 2 | 1.0 |
| Late, sham bypass | 2 | 2 | 1.0 |
| Early, informative bypass | 2 | 2 | 1.0 |
| Late, informative bypass | 2 | 2 | 1.0 |

Using the final oracle outcomes rather than the saved analysis, each block gives

`D = (late_sham − early_sham) − (late_informative − early_informative) = (1 − 1) − (1 − 1) = 0`.

The two block contrasts are `[0, 0]`, and their mean is `0.0`, matching the saved analysis. Independence and backend stability were not declared for interval calculation: `interval.available=false`, `interval.bounds=null`, `p_value=null`, and `interaction_randomization_test=null`. The known contrast range is `[-2, 2]`; it is not a confidence interval. Zero here does not establish equivalence or justify a zero-width interval.

## Scope retained

The backend is the declared deterministic `revision_relay_scoped_policy`; these are eight scripted teams, not new model trials. The source fixture A is scripted, and B/C decisions come from the built-in scripted policy. The provider ledger has 400 prior entries (397 completed, three failed); none was created during this study's recorded execution interval, and the study job has no provider-response traces. The saved execution reports zero hosted calls.

This check does not rerun or pool the separate 37 completed live units recorded across the primary pilot (9), replication (12), network pilot (8), and complementary-information pilot (8). Those counts were inspected as registry metadata only; their numerical results were not reauthenticated here.

The relay protocol/result have no behavior reference and do not promote a behavior or theory. Source inventories, queue placement and exact local input construction remain process evidence, not proof of provider consumption, beliefs or mediation. No registry objects, jobs, source modules or prior failures were changed; this note is the sole saved output of the independent check.
