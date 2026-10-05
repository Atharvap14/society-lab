# Capability-driven environment authoring

The authoring API turns a structured agent proposal into a declarative specification for an existing executable world, or returns an explicit unsupported construction outcome. It currently exposes four compiler selections: `shared_artifact_coordination`, `provenance_diffusion`, `complementary_information`, and `exclusive_resource_tasks`. These are examples of available tools, not an exhaustive taxonomy of swarm behavior.

Triggered resource reminders use the same resource world through a separate paired timing protocol. Correction relay uses a fifth, separately implemented revision-capable world and its own four-cell protocol. Those two study interfaces are not compiler selections or generic-cycle dispatches. See [construct status](construct-status.md) for the distinction between six study interfaces, four compiler families and five worlds.

The compiler executes no generated code and calls no models. A research agent can propose a blueprint using the supplied schema; a separate world-fit reviewer can reject that blueprint. Compilation, evidence verification, mechanism fit, and experimental identification remain separate judgments.

## API

```python
from swarm_lab.environment_authoring import (
    capability_catalog, schema_for_capabilities, compile_blueprint,
    blueprint_fingerprint,
)

requirements = ["private_complementary_residues", "neighbor_multicast"]
packet = schema_for_capabilities(requirements)
# Supply packet["builder_schema"] and its catalog to the builder agent.
# Give the reviewer the exact materialized blueprint and its identity.
# Bind reviewer_schema.properties.reviewed_blueprint_hash.enum to this value.
review_input_hash = blueprint_fingerprint(proposal)
# Obtain a separate fit judgment using packet["reviewer_schema"].
result = compile_blueprint(
    proposal,
    store=store,
    fit_review=review,
    audit_seed=0,
    required_capabilities=requirements,
)
```

`capability_catalog()` returns each implementation's factory declaration, capability identifiers, parameter allowlist, default policy, and extension contract. `schema_for_capabilities()` also returns eligible implementations, unknown requirements, and a hash of the catalog. A caller's required capabilities must be passed again to `compile_blueprint`; the compiler unions these trusted requirements with the model's requirements and reports any omission. A builder cannot silently discard a browser, memory, or role requirement to make a simpler template fit.

Every blueprint property is required by the bounded schema. Unused arrays are empty; unused strings are empty. The selected implementation's parameter object must contain every allowlisted property. A null parameter selects the existing factory default. For example, a complementary-information parameter object is:

```json
{
  "topology": "ring",
  "max_rounds": 3,
  "modulus": 97,
  "max_messages_per_agent": null,
  "custom_edges": null
}
```

The compiler validates its complete bounded schema independently of any model provider's structured-output subset. A provider-facing schema clone may omit an unsupported presentation constraint such as `uniqueItems`; the compiler still rejects duplicates and forbidden properties. Schema adaptation must preserve the raw role output and cannot bypass compilation.

Arbitrary role names, browser tools, persistent memory across runs, generated source code, oracle answers, seeds, and treatment labels are unavailable authoring parameters. An unknown capability or parameter is reported explicitly. The `unsupported` selection uses an empty parameter object and records the missing capabilities and reason. Explicit graph edges require `topology: "custom"`; the compiler never replaces a named graph silently. A custom graph can be constructed without necessarily being supported by a particular registered factorial experiment.

## Evidence and invented assumptions

A blueprint separates `observed_facts` from `analogue_inventions`. Each source reference pins `{kind, id, version, hash}`. Each observational claim cites pinned source IDs and, for datasets, specific message evidence IDs. With a Store, the compiler retrieves the exact object version, checks its kind and payload hash, and verifies that cited message IDs belong to that version. Later imports or library revisions do not change the original source pins.

Object integrity and record membership do not establish that a claim correctly describes the cited text. They also do not demonstrate that an authoring agent actually read a record. Role integration must check nested `observed_facts[].evidence_ids` against the records supplied to or retrieved by that role. `ResearchAgents.run` traverses nested citation arrays and binds them to the role's supplied and retrieved IDs; integrations that bypass that guard must perform the same check. The world-fit review should assess semantic support separately.

A proposal with source pins and no Store can be schema-valid, but it remains `needs_source_verification` even if its reviewer approves it. A purely synthetic proposal can contain no source facts; this is recorded explicitly. The compiler always reports `historical_fidelity: "unestablished"`. It records the world's actual population, generator, and fidelity dimensions as synthetic construction assumptions, irrespective of the wording of the proposed mechanism. It never labels a selected world a historical reconstruction.

## Independent fit and execution gates

The result payload has kind `environment_blueprint`. Its main fields are:

| Field | Meaning |
| --- | --- |
| `construction_status` | `invalid_blueprint`, `unsupported`, `compiled`, or `boundary_check_failed` |
| `spec` and `spec_hash` | Declarative executable spec and its hash; null if construction is rejected |
| `experiment_eligibility` | `blocked`, `needs_review`, `needs_revision`, `needs_source_verification`, or `approved_analogue` |
| `missing_capabilities` | Requirements that the selected implementation cannot represent |
| `source_verification` | Exact object/record checks, with semantic limitations |
| `boundary_audit` | Factory contract, reset, subject-packet scope, and private-context checks |
| `environment_code_hashes` | Authoring adapter, dispatch API, and selected world source hashes |
| `original_observation_claims` / `analogue_inventions` | Separate retained claims and construction assumptions |

A successful factory call does not override the reviewer. A reviewer can block a claimed mechanism fit, identify source misstatements, require changes, or identify further missing capabilities while the construction remains valid. An undetermined mechanism fit stays `needs_review`, even if the review's decision field says approve. `approved_analogue` is a bounded world-fit disposition supplied by the reviewer. It is not authorization to infer a historical causal effect, proof of reviewer independence, or a preregistered experiment.

The review must include `reviewed_blueprint_hash` matching `blueprint_fingerprint(proposal)` (also returned as `blueprint_hash` after initial compilation). Changing parameters, source pins, facts, inventions, or other blueprint fields invalidates a previous approval. When a host supplies authoritative source pins, it should archive the raw model output and its explicit materialization operation, calculate the materialized proposal hash, and give that exact proposal to the reviewer. The reviewer schema can constrain the identity field to a single allowed hash. A copied judgment from a different proposal remains blocked.

The compiler runs the selected world's existing contract checker and additional information-boundary probes without subject calls. It checks fresh-state restoration, exact scoped packet keys, absence of known private state and treatment metadata in observations, private-marker visibility only to its recipient, and exact reset at one audit seed. Observed source statements, original future events, proposed mechanism text, and reviewer notes do not enter subject packets. The finite structural checks are a smoke test; they do not prove the absence of all semantic leakage or validate historical fidelity.

Before execution, the research system must register a compatible experiment with frozen source/backend settings, independent assignments, operational outcomes, and uncertainty analysis. A constructed world can be suitable for exploration while a particular experimental protocol is unavailable. No generated program, arbitrary import path, or evaluation expression is an extension route. Adding a new implementation requires code review, its own capability declaration, scoped observations, legal-action checks, reset tests, an independent oracle, and registration before any subject calls.

The integrated `construct-environment` workflow archives raw builder output, exact host source materialization, compilation and a separate reviewer call. Purely synthetic proposals have no observed source facts. `resume-environment-review` reviews an unchanged saved proposal/world; changing the harness is declared and earlier failures remain in history. A provider-facing exact hash enum can omit a redundant matching regex while the complete local schema still validates both. A successful later response does not prove which constraint caused an earlier provider failure.

`register-blueprint` bridges an approved world to one of the four current frozen study constructors, with exact specification equality checked before registration. Shared-artifact designs preserve the initial-state distribution. The two network designs preserve one authored built-in graph, generator and action budgets while varying their predefined private note. The resource bridge preserves the authored task costs, release rounds and action/message budgets for its fixed reminder/neutral contrast. Custom graphs and nondefault message caps unsupported by a constructor remain blocked; they are never replaced by defaults. The blueprint mechanism and registered question are recorded separately. A world-fit approval does not automatically prove that the fixed contrast isolates that mechanism. Registration is separate from execution and consumes no model calls.

A reviewer can use host capability declarations, finite boundary probes and allowlisted source sections to assess implemented synthetic features. Historical chat is relevant to observation claims, not a prerequisite for a synthetic factory's multicast capability. Source membership, code declarations, executed contracts, mechanism fit and causal identification remain different evidence types. A model reviewer can misunderstand these types; its prose is retained as a judgment rather than elevated to verified fact.

## Validation

`tests/test_environment_authoring.py` covers the original three factory selections, unknown requirements, trusted-requirement retention, parameter rejection, explicit custom graphs, exact source versions and records, separation of inventions and observations, reviewer blocking, failed boundary probes, reset, and private state/metadata isolation. Resource authoring/registration is additionally exercised in `tests/test_resource_workflow.py` and the four-family composition in `tests/test_research_cycle.py`. These tests use synthetic local fixtures and make no model calls. This guide records their scope, not a new test run or production attestation.
