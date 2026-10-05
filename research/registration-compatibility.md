# Preview an authored world's registration compatibility

The dashboard's Environment authoring view can check whether one exact saved blueprint can become an existing study without changing its world. The preview creates no protocol, job, subject call, archive, budget reservation or library status change. Even `live=true` only declares a prospective Responses backend. Registration and execution remain separate actions.

This guide describes production [registration_preview.py](../swarm_lab/registration_preview.py) and its shared [registration preparation](../swarm_lab/experiment_authoring.py). For construction and reviewer scope, see [environment authoring](theory/environment-authoring.md).

## Read the gates separately

The packet version is `registration-compatibility-preview-v1`. A compatible result has all five checks true and a prospective `design`. A blocked result has `design: null` and a structured reason. A null check means **not checked**, not failed or passed; a refusal can leave later gates unknown.

| Check | What it establishes within this procedure |
| --- | --- |
| `construction_compiled` | The selected saved object declares successful construction. Current recompilation is checked separately. |
| `fit_approved_analogue` | A bound supplied/model review approved this proposal as an analogue. |
| `current_source_authorization` | Current local object/record membership and implementation checks complete; saved source/code/spec pins and the finite canonical world body agree with recompilation. |
| `design_compatible` | An existing registered constructor accepts the selected parameters and plan. |
| `exact_world_preserved` | That constructor preserves the recompiled authored specification. |

These checks do not establish semantic citation truth, historical fidelity, an identified causal mechanism, reviewer independence, upstream object freshness, Google Cloud permissions, user authorization to spend, or remaining budget. A synthetic proposal can have no observational sources. The fixed study question, treatment and outcome may be narrower than its mechanism hypothesis; the registered payload keeps those declarations separate and leaves historical mechanism support unestablished.

Preparation executes finite factory/boundary probes without subjects. It rereads pinned local registry objects and current implementation files, not original upstream source files. Actual registration repeats the checks; an earlier successful preview cannot authorize a changed blueprint or changed implementation.

## Supported registration paths

| Authored family | Result kind | Existing study contrast |
| --- | --- | --- |
| `shared_artifact_coordination` | `protocol` | Evidence-check private context versus neutral context; baseline also retained. |
| `provenance_diffusion` | `network_protocol` | Source-check context versus neutral context on one authored built-in graph. |
| `complementary_information` | `complementary_protocol` | The same predefined context contrast with the authored modular-information task. |
| `exclusive_resource_tasks` | `resource_protocol` | Independent-work reminder versus neutral context with authored costs, releases and budgets. |

Custom graphs and parameters a constructor cannot preserve remain blocked. For example, an unsupported message cap is not replaced by a default. Triggered resource timing and correction relay have separate study interfaces; they are not additional blueprint-registration families. See [construct status](theory/construct-status.md).

## Exact request and registration

The read-only endpoint accepts exactly these six query fields, once each:

```http
GET /api/blueprint-registration-preview?blueprint_id=environment_blueprint-EXAMPLE&blueprint_version=1&blueprint_hash=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&trials_per_cell=2&seed=4491&live=false
```

The ID, version and 64-character lowercase hash above are placeholders; replace them with one saved blueprint's exact reference. Versions are integers 1–1,000,000,000; trials are integers 2–1,000; seeds are nonnegative integers below 2^63. HTTP uses canonical decimal strings and literal `true`/`false`. Duplicate, extra, blank, noncanonical and mistyped fields are rejected. The dashboard currently requests two runs per condition and seed 4491, bound to its displayed blueprint and subject mode.

The CLI registration command **writes a new protocol**, but launches no subjects:

```powershell
python -m swarm_lab.cli register-blueprint environment_blueprint-EXAMPLE --blueprint-version 1 --blueprint-hash aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa --trials-per-cell 2 --seed 4491
```

Supply version and hash together to preserve the previewed identity. Omitting both selects latest and therefore does not bind registration to an earlier preview. Omitting `--live` declares scripted subjects; `--live` declares Responses subjects for later execution. The queued API action is `register_blueprint`, using the same bound arguments. The UI prevents automatic repeats for its pending, queued or unknown acknowledgment; inspect the registration job before requesting another.

`maximum_subject_calls` counts maximum subject decision requests/opportunities across all conditions. `maximum_hosted_subject_calls` is that bound for Responses and zero for scripted subjects. Neither is a performed-call count or a budget grant. Early completion can use fewer opportunities; execution needs its own mode/source checks and call-budget enforcement.

## Integrity correction and validation scope

An independent temporary-store probe found that a resealed blueprint could change its saved `spec` body while retaining the old scalar `spec_hash`: the earlier preview accepted a different recomputed world. Shared preparation now checks the saved and recomputed bodies through finite canonical JSON identity. Changed values, equal-valued integer/float substitutions, booleans, missing bodies, NaN and Infinity refuse before either compatibility or registration. This is an integrity fix, not a behavioral finding.

Recorded focused cohorts passed 19 production-import checks and 15 API/UI checks. They cover isolated registration/execution/replay, exact versions, source/body refusals, read-only preview, stale presentation, scoped outcomes and queued acknowledgment behavior. These overlapping cohorts are scoped validation, not an additive full-suite count or a scientific/provider attestation. See [backend tests](../tests/test_registration_preview.py), [interface tests](../tests/test_registration_preview_interfaces.py) and [independent renderer tests](../tests/test_blueprint_registration_preview_independent.py).
