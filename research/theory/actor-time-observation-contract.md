# Explicit actor/time observations

Instrument: actor-time-event-query-v1. This independent extension reads the existing bounded-event-source-index-v1 artifact. It changes no index schema, historical emission audit, room assignment, graph, or behavioral status. A room/time query can report zero platform actions while relevant actor-attributed events lack roomId; this instrument exposes that distinction without imputing a room.

## Query and summary API

```python
packet = read_actor_event_index(
    index_path,
    expected_file_sha256=trusted_artifact_sha256,
    actor_ids=[exact_uuid],
    windows=[{
        "id": "original-window",
        "start": "2025-04-18T18:00:00Z",
        "end_exclusive": "2025-04-18T19:00:00Z",
    }],
    action_types=["WAIT", "PAUSE", "START_USING_COMPUTER", "STOP_USING_COMPUTER"],
    max_rows=256,
    max_candidate_rows=15000,
)
summary = summarize_actor_events(packet)
```

actor_ids are 1–128 unique exact UUID strings. They are source identifiers, not inferred membership or agent roles. windows are 1–24 distinct half-open spans with explicit UTC offsets; labels are optional. Room fields, actor aliases, and arbitrary query syntax are rejected. Nonzero-offset and naive query times are rejected. Overlaps are allowed and explicitly reuse records. action_types may be omitted for all actions, or supplied as at most 64 exact action tokens. Unknown action tokens are preserved by the index, but its actor attribution for unrecognized actions remains unknown.

Both row bounds require strict positive nonboolean integers at most 15,000. There is no hidden sampling, nearest-time match, chronological early stop, or actor-field fallback. The frozen index's attribution selects speakerId for recorded talk and agentId for recognized other actions; conflicts between explicit IDs remain unassigned. The extension reuses that instrument unchanged.

## Authentication and bounded computation

The expected binary SHA256 must originate from a trusted host pin. The reader hashes the complete local artifact before opening read-only SQLite and again after closing it. It checks the exact frozen SQL schema, finalized metadata, current helper-code hashes, declared source fingerprint, metadata-to-row-count consistency, and finite typed coverage. Each time/action candidate undergoes the frozen projection validator, compact projection-hash recomputation, source-coordinate/hash checks, and SQL-column/projection agreement.

The artifact has no actor-selection column. The reader therefore counts the union of time/action candidates without a room predicate, then validates every candidate before filtering exact attributed actor IDs in Python. All candidates must fit max_candidate_rows. Exceeding that bound raises an actionable error before candidate parsing; it produces no prefix summary or apparent absence. Corruption in another actor's candidate or beyond the retained-output limit also rejects the query. No raw source object is reread. Original record/raw-line hashes remain scan declarations authenticated inside the index, not independently refreshed evidence.

The existing artifact ceiling is 2 GiB. Candidate projection size is bounded by the frozen 8 KiB limit; retained query and summary packets are each bounded to 64 MiB. The summary accepts only finite bounded input, exact known envelope keys, reproducible projections/scope, consistent coverage, and matching accepted host hash bindings. It does not independently reopen or authenticate the producer. File hashing and SQLite operations are synchronous bounded-size work, without a promised wall-clock deadline.

## Output and missingness

The query kind is actor_event_source_query. Each retained entry preserves record, source path/table/physical line/raw-line SHA256/raw-record SHA256, and projection_sha256. It adds window_ids and room_observation:

- known: valid explicit UUID, with its source room_id;
- missing: absent or null, preserving that presence distinction;
- invalid: supplied value failed the frozen ID validator, without exporting its raw value.

inferred is always false. Missing timestamps cannot enter a time predicate. Their total build count is disclosed, but is not assigned to requested actors or windows. Candidate actor-status counts describe all time/action candidates, including other actors and unresolved attribution. They are not counts of uncertainty about a particular requested actor.

Coverage distinguishes complete candidate validation, total attributed matches, retained matches, output truncation, and source-build completeness. A complete query over a partial source build remains a partial-source observation. The pure summary kind is actor_time_observation_summary; its action counts, room-status counts, actor/window partitions, and valid requested PAUSE seconds describe retained records only. A truncated packet cannot supply a complete behavioral histogram. Even with complete output, a zero means no matching attributed indexed record under this predicate, not global inactivity or upstream logging completeness.

## Permitted interpretation and tests

WAIT and PAUSE identify recorded choices. Requested PAUSE seconds are not measured elapsed inactivity. START and STOP identify recorded boundaries; neither successful access nor an exclusive lease or continuous-use interval is constructed. Equal timestamps retain physical-line order only for deterministic presentation. Actor/time overlap does not establish a room, recipient, delivery, exposure, acknowledgment, artifact inspection, or causal influence.

Focused tests cover missing/null/invalid rooms, old-query exclusion versus actor-query inclusion, attribution conflicts, invalid times, ties, half-open boundaries, overlapping windows, exact IDs, strict bounds, candidate exhaustion, truncation, partial builds, malformed and forged metadata/projections/code pins, pre/post hashes, privacy, immutable files/inputs, and retained-only summaries. The [indexed-event interpretation](indexed-events-interpretation.md) motivates this separate scope; it is not automatically revised by producing an actor query. Any future causal or activity claim requires additional source adjudication and a predeclared measurement contract.
