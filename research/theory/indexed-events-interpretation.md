# Interpreting the frozen indexed-event bridge

Reviewed October 4, 2026, through read-only registry queries. The bridge corroborates recorded emission lineage for every selected agent message. It supplies neither recipient receipt nor a historical causal network. This interpretation reread registered payloads and local code, not the original event object or the index artifact.

## Exact identity and integrity layers

Store hashes below were independently recomputed using sorted-key, default-separator UTF-8 JSON.

| Registered object | Version | Store SHA256 |
|---|---:|---|
| event_source_index-71b617501d7e | 1 | 4443a30f878e6614bfcaf253eb6715e901a9e311c4a1ae64db8850048797659d |
| indexed_event_audit-d83283eae5b3 | 1 | 5992170a108d2b62bdd7bf3ad2e3da85587b1583a50fc72f19f01b86c24200b9 |
| verification-eaa813f998dc | 1 | e7e0d56bff9a4707833ce6eb14931c9fbc373b020ee960cd55ef76fd4d5f88f3 |
| dataset-5d2eef17db31 | 1 | 4351ceeb788cc000b6e288927299f20d68095e9a449a47bb6cef5e0791cc5c41 |
| discovery-3d29f6c7f419 | 3 | 32a06644e6fc1d83c42141b5640a092ac8d9d09bb82df171d779318fd535d403 |
| selected_lead_audit-cdb8875d4e64 | 1 | 3309d1e6e8d174fe5b8919af3288812de65de1c3993b74ec6a9ff001578e11b0 |

The saved build reports all 381,610 rows of V:/events.jsonl.gz parsed/indexed, actual EOF and gzip CRC completion, zero malformed rows, duplicate IDs, or invalid timestamps. It observed 328,621,853 compressed bytes and 1,007,756,037 expanded bytes. Whole compressed-byte SHA256: 175e8dbfd50bc69b2688f28680758d47fd212dccb5c4d46075a3d1b575b6ef0f. Observed MD5 07d4e8f54e4ae8ab2a8df41fafa6ecaf and byte count match supplied declarations. This does not authenticate the supplied upstream revision, logging completeness, or global database uniqueness.

The saved verification passed a fresh local-index byte hash, query, and frozen-source replay; full_event_source_reread is false. The closed SQLite artifact, 1,603,403,776 bytes, has SHA256 d9298320924026727ec041fca1fb2fe2a4862cce827b89547d1a05eb2f69f099. The audit records identical expected, prequery, and postquery hashes and internal-metadata SHA256 88a30bbf454e20d759ffc01d90f42b2f8023cd6c77fc26ab5d5e4d9e7e06f049. These are saved host checks, not fresh authentication by this note.

All thirteen audit implementation pins match current files. Their compact sorted-key JSON manifest SHA256 is 605191e443c423f07b29ba2734885245bb0fcb4f6ed9902e4dbfe77539d95f29. Main binary pins:

| File | SHA256 |
|---|---|
| event_source_index.py | be894562af9a436297339ff682859f1c6258e81444e860370ea91d6e9cdf19c3 |
| indexed_event_audit.py | 45b8e9e5e70805aa26452bbec58c326962448b7841fd0ede8199d12403525d08 |
| indexed_event_workflow.py | 2b95bd88385ae0ccfd7a31f63129f243d39eca5b97decd0e4ccd1511bda39ccc |

## What matches, and the six preserved windows

The query unions exact messageId/chatMessageId requests with explicit room/time windows, then applies its action filter globally. It requested 349 chat IDs and AGENT_TALK, WAIT, PAUSE, START_USING_COMPUTER, STOP_USING_COMPUTER. All 250 returned projections are AGENT_TALK; coverage is complete for this filter, with no truncation. Every emission has one candidate matching explicit messageId, speakerId, roomId, speakerType, and canonical JSON content-value hash against pinned normalized chat. Compound normalized-record hashes have a different purpose.

The 99 user messages remain unknown under the deliberately agent-only emission lookup. They are not 99 failed agent emissions. Every returned event has an explicit valid room and falls inside its original window. All six are half-open UTC windows in room 18a3b2fb-9d2e-4ce7-b9b1-52e09c5408a8:

| 2025 UTC window | Frozen window ID | Chats | Matched agent emissions | User lookup unknown |
|---|---|---:|---:|---:|
| Apr17 18–19 | window-561db93d169c977d | 50 | 33 | 17 |
| Apr17 19–20 | window-46201f369829d997 | 81 | 42 | 39 |
| Apr18 18–19 | window-3a4dd0d6e2db6941 | 70 | 45 | 25 |
| Apr18 19–20 | window-c700fe3c721fd247 | 34 | 31 | 3 |
| Apr22 18–19 | window-4dd82e3ac3b0d6e4 | 52 | 43 | 9 |
| Apr22 19–20 | window-9e914aaef4dc1c17 | 62 | 56 | 6 |

Each window reports zero for all four platform actions. Those counts require an explicit matching room and time. They establish neither inactivity nor absence of actor activity outside that predicate; missing-room records cannot be assigned by guessing from the actor. No new global action inventory was performed here.

Across matched records, event timestamp minus chat timestamp ranges from 147.203 to 793.259 milliseconds. All 250 event times use the declared export_naive_assumed_utc policy. These differences describe recorded timestamps; they do not estimate delivery latency, clock synchronization, reading, or processing time.

## The reversed reference path survives emission corroboration

The [temporal interpretation](temporal-path-interpretation.md) identified Claude3.5→GPT-4.1→Claude3.7 as a backward static reference path. Its two chat records now have unique matching emission projections:

| Chat message ID | Emission event ID | Chat time UTC | Event time UTC | Event archive line/index |
|---|---|---|---|---|
| 585a9073-247b-484e-b5f6-e8888eebe2d2 | 2a7f529b-ed0f-4495-abba-54b56fcaf921 | 18:04:38.069866 | 18:04:38.235085 | 63498 / 15653 |
| 6a8397f3-9e33-4354-a564-0a7f3cc2d839 | 21fdfacd-d44f-4c4e-b20a-8b92d240715a | 18:01:17.314578 | 18:01:17.476177 | 50817 / 15642 |

Both are April18, 2025. For the first event, compact raw-record SHA256 is 60e241ea695e9819d28f1d3c1191a712d982f6b27b592aa28a6b8d796983c2e7; terminator-inclusive raw-line SHA256 is daf43cd9ec18ecca3e519e011be6e97a02d6015aa55b061a2f344e37bd7f0057. For the second they are b4b5205089fb16fff8050c8a075900b857885cac9300b3c9491bb9507833223b and 6435abb4cd625d9c256f5973d844b365b5a958445e04702fb78753a87d7b9722. These pins are original-scan declarations authenticated inside the saved index, not newly reread raw lines.

Emission chronology preserves the reversal. It corroborates the representation limit without identifying either participant's mental state. Author→mentioned-name direction can be opposite to information received earlier; shared instructions, task ownership, status narration, and unrelated work remain ordinary alternatives.

## Next discriminating scope

A separate actor/time query could retain explicitly attributed platform actions lacking room fields, mark them unassigned to rooms, and compare recorded boundaries with waiting claims. It would still not verify successful access or consumption. Receipt requires recipient exposure/context or acknowledgment evidence, and artifact transfer requires actual inspection/version evidence. Freeze these rules before held-out episodes or controlled delivery-order interventions. This is retrospective corroboration of selected records, not held-out replication, causal discovery, or automatic behavioral-candidate promotion.
