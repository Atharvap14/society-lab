# Event evidence neighborhoods

Society Lab now has an optional read-only graph reader for one exact saved `observability_run`. It answers a narrow question: **which captured events are connected to this event through explicitly declared references?** It creates neither a behavior candidate nor a causal graph.

## What inspired the addition

The authenticated source review of [Kairosity Observatory](https://github.com/gautamjajoo/kairosity-observatory) on 4 October 2026 found a useful separation: its graphs connect original source records through typed fields, while its mention counts are a different descriptive measurement. Its backend retains missing and ambiguous parents; its graph component lets a reader inspect an edge's field provenance. The reviewed branch was `codex/agent-observatory`; GitHub reported these file blob identities:

| Primary implementation reviewed | GitHub blob SHA |
| --- | --- |
| [backend/store.py](https://github.com/gautamjajoo/kairosity-observatory/blob/codex/agent-observatory/backend/store.py), graph methods | `e09268d80f3493f76be875f3a5afb9185eb0c4e7` |
| [backend/API_CONTRACT.md](https://github.com/gautamjajoo/kairosity-observatory/blob/codex/agent-observatory/backend/API_CONTRACT.md) | `551d6b7adb7f5153b52471396ecacee5e67dd07e` |
| [product/components/observatory/evidence-graph.tsx](https://github.com/gautamjajoo/kairosity-observatory/blob/codex/agent-observatory/product/components/observatory/evidence-graph.tsx) | `b21d0ef63f3d45ff472f38f849447f0d958ff6f0` |

These are reported file-blob pins, not a deployment or repository-commit attestation. The new [reader](../swarm_lab/event_evidence_graph.py) is an original adaptation to Society Lab's existing events protocol. It does not copy the private service, index, credentials, dataset, frontend or ingestion architecture. It adds resolved-neighborhood traversal beyond Society's existing flat `reference_checks` and replay links.

## Python contract

```python
from swarm_lab.event_evidence_graph import build_event_evidence_neighborhood

packet = build_event_evidence_neighborhood(
    exact_saved_run_record,
    seed_event_id="actual-captured-event-id",
    hops=1,
    max_nodes=100,
    max_edges=256,
    max_diagnostics=64,
)
```

The host must retrieve the exact `{id, version, hash}` and authorize its read. The reader checks the declared Store payload fingerprint, finite bounded JSON and the frozen `societylab.events.v1` validator. Consistency with a local stored hash does not independently authenticate telemetry or its producer.

Every node is an actual captured event with its original ID, kind, timestamp, one-based capture position, explicit actor/task IDs, neighborhood distance and canonical event SHA-256. It exports no content, arguments, provider output or private rationale text. Source IDs do not acquire display-name aliases.

The supported relations are actor registration, task definition, parent-task definition, addressed recipient registration, assignee registration, reply-message reference and tool-call reference. Source fields, including exact recipient/assignee list coordinates, accompany each edge. Edges point from the referencing event to its unique matching definition event. Agent/task definition self-links are omitted; explicit self-replies can remain source references.

Repeated definitions yield `ambiguous_reference`; an absent definition yields `unknown_in_captured_run`; a tool return naming a uniquely matched call from a different actor yields `actor_conflict`. None becomes an edge or a fabricated node. Diagnostics preserve candidate counts and at most eight candidate event IDs. They concern references declared by retained nodes, not every reference in the global corpus.

Selection follows resolved adjacency in both directions for zero to two hops. Display edges are the induced resolved edges between selected event nodes and retain their original direction. This is an inspection policy, not an information-flow model. A later-captured parent, reversed timestamp, cycle or tied timestamp remains visible without inventing a shared causal clock.

## Bounds and unknowns

The reader accepts the protocol's maximum 2,000 events and 1 MiB batch, with at most 2 MiB for the entire saved payload. Nesting, item count and source text are separately bounded. More than 20,000 declared reference checks refuses the request before returning a partial graph. It uses no provider, database or network calls; it reads the three implementation files only to report their byte hashes.

Output limits are 200 nodes, 600 edges and 256 diagnostics. Default limits are smaller. `truncated` and separate node/edge/diagnostic cap flags disclose omitted display items; pre-cap quantities remain available. Neighbors beyond the requested hop count are a disclosed scope boundary rather than an incomplete execution. No absent-target diagnosis establishes corpus-wide absence.

An addressed recipient is a producer-declared address, not a receipt. A matching reply or call ID is a source-field match, not evidence that a person read a message or that a tool executed successfully. Private rationale can have actor/task provenance but contributes no communication edge. This layer remains separate from mention graphs, temporal reference paths, spectral operators and Hodge decompositions.

The [eight focused tests](../tests/test_event_evidence_graph.py) use authored fixtures to check exact pins, original field coordinates, forward/reverse traversal, missing/ambiguous/conflicting references, private-content exclusion, cycles, timestamps, deterministic replay, display/work bounds and malformed inputs. They establish software behavior, not accuracy or influence in a population of agents.

## Exact-source HTTP read

The loopback dashboard now exposes:

```text
GET /api/observability/graph?object_id=EXACT_RUN_ID&version=1&hash=EXACT_64_HEX_FINGERPRINT&event_id=CAPTURED_EVENT_ID&hops=1
```

All five parameters are required exactly once. Duplicate, unknown, blank or malformed values are rejected. Versions must be canonical positive safe integers; hops must be exactly `0`, `1` or `2`. The host reads that exact stored version and compares the requested ID, version and hash before invoking the reader. It never substitutes the latest run. Unknown stored versions return 404; invalid query/snapshot/event requests return 400. Responses use `Cache-Control: no-store` and launch no job.

The [actual loopback fixture test](../tests/test_event_evidence_graph_api.py) distinguishes original version 1 from changed version 2 and checks rejected requests, unavailable content export and unchanged stored objects, jobs, trace counts and call usage. It creates only an isolated authored source for the software check. This endpoint has not itself established a new production analysis, causal relationship or empirical result. Any browser link or guide read must preserve the exact run pin and original event ID.
