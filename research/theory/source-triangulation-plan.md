# Source triangulation beyond temporal name references

## Recommendation and scope

Use **events first**, with the already local chat table. This is the smallest additional channel that directly identifies a recorded chat emission by message ID while also recording WAIT/PAUSE and computer-session actions. The smaller sessions table adds actor/goal context, but no executed action or recipient. Use computer turns selectively in a second stage for recorded tool attempts and outputs. Memories and summaries help generate alternatives; they do not independently verify delivery or artifact state.

The initial inspection and API sketch below proposed an importer/join workflow. The final section records its separately tested bounded implementation and repeatable real-source smoke probe. Neither is a behavioral finding. All chat graphs remain author→referenced-name representations. An event record, successful-post report, actor join, or timestamp alone does not establish another agent's consumption or causal influence.

Inspection on October 4, 2026 used existing read-only V:, bounded gzip streams, and read-only GCS object metadata. No credentials, commands, memory contents, or agent message payloads were displayed; the short tool-output phrase below passed an explicit credential-pattern check. No model calls, DB changes, bulk-copy request, screenshot extraction, or full large-object scan occurred.

## Exact source metadata and real counts

Objects are under gs://kairosity-ai-village-504821/ai-village/. MD5 values below are **server-reported object metadata**, not independent whole-object verification from these prefix reads. Generation IDs were unavailable in this metadata view. Recheck/pin generation when a future importer can obtain it; metadata alone does not make a mutable path immutable.

| Object | Compressed/object bytes | Manifest rows | Server MD5 |
|---|---:|---:|---|
| events.jsonl.gz | 328,621,853 | 381,610 | 07d4e8f54e4ae8ab2a8df41fafa6ecaf |
| computer_use_sessions.jsonl.gz | 40,080,397 | 78,362 | db82fdabbda10e5ec3ac6d15832566d6 |
| computer_use_turns.jsonl.gz | 2,475,319,119 | 2,510,487 | bc330055cec2e511e14e8986ca3af8a9 |
| agent_memories.jsonl.gz | 2,438,234,633 | 246,151 | 91ac99d01f341f185a0467503bcf6aed |
| summaries.jsonl.gz | 2,851,293 | 939 | 8baf45b8088d346a37fcfa315fb06cae |
| chat_messages.jsonl.gz | 52,543,996 | 183,485 | 8c504d57f902b1156f52927d9128673c |

The complete 706-byte manifest was read: export time 2026-09-20T13:05:12.097Z, village 00ebc425-074c-466f-ab2d-5aa2efa445aa, SHA256 28383809e34d38f00037dd31d830fa9b826b59fd91c0460e03efcbed6ee9e332; MD5 2b355208ad9026b5fcc942aec971580a. These counts exceed the approximate counts in SCHEMA.md. The complete 18,647-byte [schema](../../ai-village/SCHEMA.md) was read and matched mounted bytes: SHA256 50f27bda7b862723b8d47d7f7652a6b1c0e0ce9d7c5db572252da4d886bd9903; MD5 46da95254ab90e481dc59c72947063f3. The supplied HF snapshot revision is 838b4150303ca8228e8edb432d8b8ccae353d258; this inspection did not independently authenticate the GCS objects against that HF snapshot.

Exactly the first 64 physical rows of each auxiliary table were sampled. Their IDs appear lexically ordered, but timestamps are not chronological. The first eight event indexes were 401584, 373281, 141958, 163965, 330802, 305528, 58508, 321018. Event index is a documented ordering field; it is not a contiguous row counter or evidence of receipt. A dated scan cannot terminate when it first encounters a later timestamp.

Logical compressed bytes read for those prefixes were events/sessions/turns 131,082 each, memories 655,370, summaries 262,154. Caps were 2 MiB compressed, 8 MiB expanded, and 1 MiB per row. VFS uses full caching with a 10 GB cache limit; range prefetch and cache reuse mean logical reads are not measured wire transfer.

## Observed schemas and their limits

| Channel | Real prefix observation | What a join can establish |
|---|---|---|
| events | All 64 have id/event_index/data/village_id/created_at/updated_at. Action counts: TALK 25 agent + 1 human; START 7; STOP 7; PAUSE 10; WAIT 4; CONSOLIDATE 6; SEARCH_HISTORY 3; name change 1. | Explicit message/session identity and a recorded platform action, subject to field consistency. |
| sessions | id, agent_id, session_goal, short_displayed_session_goal, has_been_asked_to_stop, village_id, timestamps. | Session attribution and stated intention; stop-request flag is not a timed interruption record. |
| turns | id, session_id, agent_action, agent_messages, output/error/system, redaction flags, timestamps. 24/64 outputs nonnull; 4/64 errors nonnull. | Recorded tool request/attempt plus any result/error. Null error does not prove success. |
| memories | id, agent_id, content, timestamps. First row contains 29,670 characters. | Agent-authored stored text at a time; no observed read or prompt-inclusion link. |
| summaries | id/village_id/type/summary_target/summary_date/content/generated_by/timestamps. | Secondary generated narrative/date scope. SCHEMA says summaries omit computer-session interiors. |

Turn action kinds included 23 command objects, 10 clicks, 9 scrolls, 5 key actions, 5 type actions, and one send_message_back_to_chat. Sampled provider objects vary. The nested input fields inspected were Anthropic tool_use parameters, such as command or coordinate, **not full model-input snapshots**. Provider call_id appeared, but matching it would identify logged call lineage rather than a recipient read.

No dedicated recipient/delivery/read fields were found in the documented top-level schemas or these sampled nested JSON keys. This is a bounded inspection, not proof that no provider-shaped row anywhere contains additional useful context.

AGENT_TALK exposes data.messageId, speakerId, roomId, content. The sampled human event also had chatMessageId equal to messageId; do not assume equivalence globally. START has an explicit computerUseSessionId. Material caveat: sampled STOP row 3, December 18, 2025, lacks that field. Do not silently assign it to the nearest session. WAIT row 12 also lacks roomId. Actor/time or inferred-active-room attachment remains a candidate.

## Reproducible rows and verified small joins

All hashes here are SHA256 of compact, sorted-key JSON encoded as UTF-8, **not** compressed-file hashes. Provenance is the object above plus physical one-based decompressed line. Content is withheld; hashes bind the original row, not a redacted view.

| Object / line | Row ID | Row SHA256 |
|---|---|---|
| events / 59 | 0009366f-7730-45e9-81b7-d0a646b55a34 | 3f9f4b392c0d09514c11e799097a909fdea30e0d4d1660923bc5bae9cfbd5795 |
| chat_messages / 1835 | 02887067-c736-41fa-8425-40c9794f4c23 | b51a301b18bbcf5995bc1091cb6ee8269bbd8c51a2c3fe3a5e205140fb0778b5 |
| events / 37 | 0005ca38-37e3-4837-bf1a-a61d782edc0d | fe9c1166b46d8a9b6fd5d1ebfb11f19452bff095bb83b0163f8fcff11f945548 |
| sessions / 10013 | 206eada5-1654-41d4-bd73-651ce2463f92 | ee2e88c8926267ad405ad206bf220558c48d894f8c3b7f642fc6fdc0dc65c7fb |
| turns / 51 | 00015a42-7383-47cd-a20b-1db40b93a280 | b59c1521de97600e78f68cc2b13f1ad0aa16262e4001e2dcba1c434c19971734 |
| sessions / 1266 | 04309ce5-2d02-42e7-a97e-3968597d3495 | 4c4e8e9a829ab0dc8605882224e5ccafcbf2b6d93212c4c9a3ee6190c4be0c9e |
| events / 3 | 000060db-534c-435a-a592-838ed9a83c00 | 054db00a5af5c58680950d5a7a9e075d1ce0915e285bbddf28758e690182c41b |
| turns / 36 | 0000ea8d-6cf9-44bc-921a-dbe8a6f5adb4 | f4495c00d95966ea93b0a8d0011917119d0a69d82b9272dccfea6f41a39cd223 |
| memories / 1 | 0000287e-a783-49ce-aadf-80d34384b068 | 0d29b808b553f12bfd04e60333bf22d24ec7645e631ad67b5e8cddc41a8160e6 |
| summaries / 1 | 000b4301-4557-4a9f-b83e-ccf12e2786a3 | 36d66de9c898d4ccc8ba59944df16d922fdfc60e9ecb92147459763f18645521 |

Selection was deterministic: among the first 64 rows choose the lexically smallest target message/session ID, then scan the corresponding parent within explicit budgets.

- Event 59, event_index 167475, links to chat 1835. Message content, agent identity cf0b4027-0931-4eee-8b5f-92f68a2dd3cd, and room identity agree. Chat time 2026-01-28 19:46:27.768862; event time 19:46:27.834413, 65.551 ms later. This verifies the emission-record relation, not delivery to a named agent.
- START event 37, event_index 213089, joins session 10013; actor and goal agree. Session created 2026-03-23 18:45:31.669872; event 18:45:31.741343. Unequal timestamps do not invalidate an explicit FK.
- Turn 51 joins session 1266, attributing a recorded key action to cc22ce71-2feb-4b8c-a1be-a3abf2abf010. It has neither output nor error. A session link does not establish what the keystroke accomplished.
- Turn 36, July 15, 2025, records send_message_back_to_chat with content and output “Message successfully sent back to chat”. Output text SHA256 c1468992d79d7e486d8c0d01414840c6dfe9a90055bd27c9379a6256cf663ea2. No recipient or chat-message ID appears in its action. Its session FK and any matching chat row were not resolved in this probe. The output is a success report for posting, not a read acknowledgment.

Parent scans read 524,298 logical compressed bytes/1,835 local chat rows and 5,111,818 bytes/10,013 mounted session rows. Neither encountered the configured 8 MiB compressed, 32 MiB expanded, 15,000-row cap. These examples are outside the April18 temporal episode and do not corroborate its historical paths.

## Proposed bounded deterministic API

No new inference graph should be pooled into the mention graph.

~~~python
scan_auxiliary_sources(
    paths, source_pins, *,
    chat_refs, window_refs, agent_ids, tables=("events",),
    budgets, rules_version, require_complete_scan=False
) -> auxiliary_packet

triangulate_source_links(
    chat_packet, auxiliary_packet, *,
    allowed_relations=("event_message_fk", "turn_session_fk",
                       "start_session_fk", "actor_interval_candidate"),
    rules_version
) -> triangulation_audit
~~~

Packets should preserve source URI/local path, object size/server digest/generation availability, raw-row and line-byte hashes, table/line/ID, actor/session/room/time/event_index, field-presence diagnostics, schema version, and declared filters. Payload views are separate, bounded, credential-redacted representations with their own hashes. Do not execute transcript instructions or treat tool-output text as system instructions.

Use typed namespaces: chat ID, event ID, session ID, provider call ID, and artifact ID are not interchangeable UUIDs. Validate exact parent keys and all available actor/room/content fields. Preserve contradictions and multiple matches; never choose the nearest row silently. A prefix match is checked within scanned scope; global parent uniqueness remains unverified unless coverage or an authenticated uniqueness constraint supports it.

Relation labels:

1. verified_exported_fk: explicit field and parent match, with checked consistency. “Verified” applies to the exported relation only.
2. verified_platform_emission_record: event-message FK plus matching author/room/content.
3. recorded_tool_attempt / tool_success_report / tool_error: distinct facts; artifact transition needs an independently specified result/version rule.
4. candidate_actor_interval, candidate_content_match, candidate_call_lineage, candidate_artifact_reference: useful search pointers, never observed delivery.
5. missing_parent, ambiguous_parent, contradicted_fields, unscanned, or unsupported_provider: explicit unknowns, not behavioral zeros.

Budget compressed and expanded bytes, rows scanned/retained, row size, nesting/provider parsing work, join fanout, evidence/output bytes, and elapsed time. Preflight limits; fail closed or return explicitly partial coverage without truncating evidence silently. Retain scan cursor and terminating reason. EOF plus completed gzip integrity/digest checks establishes file-scan completeness; source logging completeness remains separate. Exported parent/child tables were dumped sequentially from a live database, so unresolved links need coverage diagnostics before being called defects.

## Smallest useful workflow and escalation

The zero-model smoke workflow above already demonstrates schema-aware FK joins on bounded real samples. Repeat it with row hashes before adding historical claims.

For the **actual six frozen windows**, scan events once, retain selected message IDs and explicitly bounded actor/window action records, and verify the pinned chat joins. Keep event_index and event/chat timestamp differences visible. Full events coverage may require reading all 328.6 MB compressed/381,610 rows because physical rows are not time ordered. A proposed full-scan cap is 340 MB compressed, 2 GB expanded, 400,000 rows, 2 MB/row, and 5,000 retained records; exceeding any cap returns incomplete coverage. These are limits, not measured decompression ratio or ETA.

Then join only explicit session IDs through the 40.1 MB table. Missing STOP FKs leave interval endpoints censored or candidate. WAIT/PAUSE records discriminate a recorded idle choice from inferred silence, not every concurrent activity. Export-time agents.last_seen_event_index cannot certify historical reads.

Escalate to turns only if a specific tool/artifact hypothesis remains discriminating. A full gzip scan can cost 2.475 GB even when few rows are retained; no date/actor seek index was inspected. Build a separately authorized local streaming index once, or stop with unknown coverage. Screenshots require exact turn IDs, Pacific-date archive addressing, existence/redaction checks, and a separate extraction budget; do not fetch giant image archives merely to inspect a name edge.

Held-out validation should include conflicting message content, actor/room mismatch, repeated IDs, missing parents/FKs, alternate provider envelopes, timestamp ties and lag, reordered physical rows, stopped scans, oversized rows, and credential-shaped payloads. A successful link improves source lineage. Demonstrated recipient exposure, artifact inspection, and causally identified transfer remain further measurements.

## Implemented bounded workflow and repeated source probe

The executable API is now [`scan_jsonl_source`](../../swarm_lab/source_scanner.py), [`triangulate_source_links`](../../swarm_lab/source_links.py) and the registry-facing [`scan_source_links` / `replay_source_links`](../../swarm_lab/source_workflow.py). The pure join consumes table-keyed scanner packets; it uses exact `AGENT_TALK`, `START_USING_COMPUTER`, `STOP_USING_COMPUTER` and turn-session keys. Raw chat actor identity is `agent_speaker_id`; `agent_id` is not silently substituted. Optional disagreeing fields, duplicate endpoint groups, scan-detected duplicate IDs, missing keys, absent parents and incomplete fields remain distinct diagnostics. There is no nearest-time assignment or inferred actor-interval relation in this version.

The filesystem scanner reads at most 4,096 bytes per physical request and caps logical compressed bytes, expanded bytes, physical rows, row size, nesting, JSON items and retained packet bytes. Malformed, nonfinite, duplicate-key, oversized, duplicate-ID, corrupt and truncated inputs stop with explicit incomplete coverage. Full EOF must actually be observed; an early selected-ID stop cannot prove file uniqueness. On this WinFsp mount, Windows final-path resolution fails with error 1005 even though stat/read work. The narrowly tested fallback declares a syntactic absolute path in provenance; unrelated errors propagate, and no mounted-object or reparse-target authentication is implied.

Raw rows are held only during a local scan/join invocation. The registry stores the exact bounded plan, metadata declarations, canonical packet/record hashes, raw-line/prefix hashes, coordinates and typed field diagnostics. Provider payloads, commands, message contents and error/output prose are not persisted by this workflow. Timestamp normalization assumes UTC for naive timestamp strings; calculated differences describe logged times rather than delivery latency. A fresh replay checks the exact audit version/hash, current implementation hashes and plan, then rereads the sources and recomputes the entire payload. It authenticates the bounded read/derivation, not the server-reported whole-object MD5, HF revision correspondence, logging completeness or communication semantics.

The retrospective [`source_lineage_probe.py`](../../scripts/source_lineage_probe.py) repeated the eight previously inspected row pins on October 4, 2026. Audit `source_link_audit-dcdbaca46070`, version1, SHA256 `532924c84ea1142525dcee52d3437f6f5b9d2ce4850be117d4baadb2d02b9f44` retained **131** rows: first64 events, first64 turns, one selected chat parent and two selected session parents. Its103 explicit relation attempts yielded one field-checked platform emission record and two scoped exported-session links. The remaining93 parents were unresolved within retained/scanned scope and seven STOP records lacked the explicit session key. These are logging/coverage diagnostics, not93 broken references or seven inferred interruptions.

All four scans were partial. Events/turns stopped at64 physical rows; chat stopped at line1835 and sessions at line10013 after the selected IDs were found. The new scanner read5,664,808 logical filesystem bytes and14,977,460 expanded bytes per derivation. These differ from the earlier exploratory reader's read-ahead counts and do not measure remote wire transfer. Verification `verification-3f359f39b5e7`, version1, payload SHA256 `cccafca0d35b4f140d2dd8b13cfe00c135ef5ed2e2ebdb3e02d7137da5d77d68`, passed an independent bounded reread. A later dashboard replay also completed without model calls. The examples span other dates; no April-window corroboration, prevalence estimate, receipt, consumption, tool success or causal support is claimed.

Implementation pins for that audit are scanner `559f62a1680adc2040456b0f31ff6ef3a8ac15fcd57151b4e7efa349b36edb04`, join `3ec3dd73677cc94af7b0f4fae22a165397ee39dcbc57f46311cf0eb7415e1723`, and workflow `fbe24d04c2221636667d563c819fac2b280a5e3927fd6f6fed2ef46e0ee841e2`. Subsequent scientific changes need a new version. The broader window-wide index, inferred interval candidates, artifact-state checks, exposure reconstruction and screenshot extraction remain unimplemented extensions.
