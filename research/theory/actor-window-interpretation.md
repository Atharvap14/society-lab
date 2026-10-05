# Actor/time observations and missing rooms

Retrospective source interpretation, 4 October 2026. This note records a change
in the observation predicate, not a discovered causal mechanism.

The fixed selected-lead audit contains six room/hour windows from 17, 18 and
22 April 2025. Its 349 chat records include 250 agent-authored messages and
99 user messages. The actor instrument selects four actors solely from explicit
agent-authorship IDs in those chats. Roster membership, mention targets and
user-authored text do not add actors. It preserves the original time windows
and removes the room requirement from the platform-event predicate.

The authenticated index query validated and retained all 183 candidate records
in this bounded predicate, with complete output and no truncation: 16 WAIT,
zero PAUSE, 84 START_USING_COMPUTER and 83 STOP_USING_COMPUTER records. All 183
records have missing rooms. Missing rooms remain missing; neither shared actor
identity nor a timestamp places an event in the selected chat conversation.

| Original date/hour in UTC coordinates | WAIT | START | STOP | Total |
| --- | ---: | ---: | ---: | ---: |
| 17 April, 18:00–19:00 | 1 | 14 | 14 | 29 |
| 17 April, 19:00–20:00 | 0 | 15 | 14 | 29 |
| 18 April, 18:00–19:00 | 4 | 18 | 17 | 39 |
| 18 April, 19:00–20:00 | 0 | 14 | 14 | 28 |
| 22 April, 18:00–19:00 | 3 | 15 | 17 | 35 |
| 22 April, 19:00–20:00 | 8 | 8 | 7 | 23 |

The earlier explicit room/time query returned zero records of these four action
types. Its zero describes that predicate: room-missing events cannot satisfy
an explicit room match. The actor query supplies a useful missing-channel
diagnostic, not a correction that imputes rooms into the earlier graph.
No activity contrast or behavioral change follows merely from the two queries.

START/STOP counts are exported action records. They do not establish exclusive
computer possession, successful access, elapsed work, or a complete lease
history. WAIT records do not establish inactivity or explain why an agent
waited. No PAUSE in this complete indexed predicate is a scoped zero, while
upstream logging completeness and global absence remain unverified. Requested
pause seconds, when available in other observations, would not be elapsed
inactivity.

All returned event timestamps use the declared export-naive-assumed-UTC policy.
This is an export normalization convention. It supplies no independent clock
synchronization, processing latency or recipient exposure evidence. The
literal wait/action alignment plan compares recorded coordinates while keeping
the normalized chats' unavailable raw clock policies explicit. Nearby actions,
missing candidates and nonmarker comparison messages supply no semantic
detector ground truth or causal identification.

## Exact recorded evidence

- `selected_lead_audit-cdb8875d4e64`, version 1, SHA256
  `3309d1e6e8d174fe5b8919af3288812de65de1c3993b74ec6a9ff001578e11b0`.
- `event_source_index-71b617501d7e`, version 1, SHA256
  `4443a30f878e6614bfcaf253eb6715e901a9e311c4a1ae64db8850048797659d`.
- `actor_event_audit-29756e356310`, version 1, SHA256
  `9652a2145f359d3212747e372ed6e6f574aa5655362aa38ef1a74dc3609238bd`.
- `verification-02300cf38ab3`, version 1, SHA256
  `3bc7b30c83d7dfc0872ec4bf086630ba883eea39589279cb5869cb949ff79048`.

The recorded proof freshly hashes and rereads the local index and reproduces
the exact frozen chat selection and whole actor-audit payload. It does not
reread the original mounted event object. Code/source pins and coverage remain
part of the proof; the identifier alone is insufficient.

The [actor/time contract](actor-time-observation-contract.md) and
[literal-marker plan](wait-marker-alignment-plan.md) keep this observation
separate from future blinded semantic labels, verified resource outcomes and
prospectively assigned interventions.
