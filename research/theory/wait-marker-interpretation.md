# Literal wait words and nearby recorded actions

Retrospective diagnostic, 4 October 2026. The
[fixed measurement plan](wait-marker-alignment-plan.md) was written before
production alignments, after the selected windows and aggregate actor counts
were known. This is same-source exploration, not a held-out test.

The authenticated frozen selection contains 349 chats: 250 agent messages and
99 user messages. The eight literal ASCII tokens identify 34 agent messages
with 41 token spans. The comparison set contains 32 nonmarker agent messages,
selected by a deterministic hash of the instrument version and message ID,
without using event outcomes. It is neither a probability sample nor negative
semantic ground truth.

| Recorded-coordinate horizon | Marker messages with a candidate / 34 | Nonmarker comparisons with a candidate / 32 |
| --- | ---: | ---: |
| 30 seconds | 6 | 1 |
| 60 seconds | 7 | 1 |
| 300 seconds | 7 | 5 |

A candidate is an explicitly attributed same-actor WAIT or PAUSE record in a
shared original query time window, within the inclusive horizon. This actor
packet contains WAIT records and zero PAUSE records. Candidate counts combine
before, tie and after relations; they do not require that a chat caused a later
action. All candidate events have missing rooms. The chat's room is not assigned
to an event.

At 30 seconds, two marker messages and one comparison message have censored
bands without candidates. At 60 seconds, one of the seven marker messages with
a candidate is boundary-censored; three further marker messages have censored
bands without candidates. At 300 seconds, three of the seven marker messages
with candidates and one of the five comparison messages with candidates are
boundary-censored; ten further marker messages and three comparison messages
have censored bands without candidates. A window-limited lack of a candidate
does not establish an observed negative outside the available band.

Across the largest horizon the instrument retains 21 message/event links to
14 distinct WAIT events. Several events are reused across messages. The nested
horizons, selected windows, source records and actor observations are also
dependent. Do not treat the table cells or links as independent samples.

Raw chat clock policies are unavailable in the frozen normalized records.
The candidate relations explicitly record that missing policy. Event timestamps
use the declared export-naive-assumed-UTC convention. Signed coordinate lags
are not synchronized physical delays or verified processing order.

The table demonstrates why literal text and recorded action channels should
remain separate. Negation, quotation, plans, instructions and reports still
produce literal hits. Nonmarker messages can also describe waiting. No
precision/recall, inactivity rate, lease history, exposure, novelty, causal
effect or library status promotion is computed. Subsequent semantic work needs
a separate blinded labeling definition and independently assessed source scope.

## Exact recorded evidence

- Actor parent: `actor_event_audit-29756e356310`, version 1, SHA256
  `9652a2145f359d3212747e372ed6e6f574aa5655362aa38ef1a74dc3609238bd`.
- Alignment: `wait_marker_alignment_audit-da8509c85911`, version 1, SHA256
  `50efc6daeac5f254f5af5380da92e3925fe4ac1ca2bf4249c6a1ed36d633fd1f`.
- Recorded fresh proof: `verification-bf9c71828932`, version 1, SHA256
  `bfdb6151db381f53845432ca5f226b332aea7189a1fe028a45b64aaed11e21d7`.
- Fixed plan file SHA256:
  `40ef1ae287c2648905793ef441d7f9f68ed1f6a05e17888fc5d1d5f94c08313e`.

The proof reauthenticates the local index bytes, reproduces the exact actor
observation and frozen chat selection, and regenerates the whole alignment
payload. The original mounted event object is not reread. The instrument's
embedded accepted packet pins are declarations validated in memory; independent
filesystem and registry authentication belongs to the host workflow. Six real
temporary-index host tests and the released pure instrument's 23 focused tests
passed before this production observation. No provider calls were made.
