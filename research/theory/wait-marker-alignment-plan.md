# Retrospective literal-marker and recorded-action alignment plan

This plan fixes an exploratory measurement before computing production alignments. Selected graph windows and aggregate actor-event counts are already known; this is not prospective preregistration, independent replication, or a held-out validation. No production message/action alignment was inspected to choose these rules.

## Fixed measurement

Use eight case-insensitive ASCII tokens: wait, waits, waited, waiting, pause, pauses, paused, pausing. Require ASCII word boundaries; retain Python string code-point offsets in the original normalized content, with no text normalization or full-content export. Count each message once as a marker-containing message even if it contains several tokens. Negated, quoted, hypothetical, reported, and instructed waiting all remain literal hits with semantic meaning unknown. await, idle, holding, blocked, and other synonyms are outside this instrument.

Use fixed horizons of 30, 60, and 300 seconds. These represent immediate neighboring records, a short scheduling exchange, and a broader episode where task dependencies and unrelated artifact work are increasingly plausible. They are diagnostic scales, not inferred processing times or optimized thresholds. Never choose a horizon from observed alignment strength.

Compare each included message only with explicitly attributed same-actor WAIT or PAUSE records that share a declared query time-window ID. Report before (negative lag), tie (zero), and after (positive lag), with endpoints included at exactly the horizon. One event may appear near multiple messages and in multiple nested horizons. Reuse is reported; there is no unique message-to-action matching, inferred dependency, or significance calculation.

Original chat rooms select source authors upstream. The event packet has an actor/time predicate across rooms. Retain known-equal, known-different, missing, or invalid event-room diagnostics without assigning a room to an event. Shared time-window identity is a selection restriction, not shared-room evidence. Events outside a message's original time window cannot be imported by proximity across a boundary.

## Controls and unknowns

Select at most 32 ordinary agent-authored nonmarker messages by a deterministic SHA256 ranking of instrument version plus exact source message ID. This selection uses neither event outcomes nor marker/event lag. It is not a probability sample or task/actor matched control group. Human messages remain counted as excluded source rows. Referenced roster members do not become authors. Controls can describe waiting without these words; they are not negative ground truth.

Present up to eight deterministic examples of marker messages with no retained nearby candidate and of nonmarker controls with candidates. These are descriptive discordance examples, not false positives or false negatives. Do not compute detector precision, recall, sensitivity, specificity, model calibration, inactivity rates, or causal effects from this instrument.

Absent/invalid metadata, forged hashes/projections, identity conflicts, duplicate IDs, or malformed times reject input. Partial source builds, truncated event output, missing WAIT/PAUSE action-filter coverage, or unresolved candidate actor attribution make alignments unknown. No negative-looking prefix result is supplied. A message actor absent from the query, or a message outside its time windows, receives an explicit unknown status. Missing/invalid source timestamps remain unassigned and cannot establish absence in an actor/time band.

Even with otherwise complete indexed coverage, a horizon extending outside the message's containing query-window union is boundary-censored. A lack of candidates there is not a fully observed negative. Clock normalization conventions are recorded separately: normalized chats usually do not preserve the raw timestamp policy, so the default chat policy is unavailable. Optional host declarations remain unverified; equal conventions do not establish clock synchronization or physical latency. Ties supply no processing order.

## Pure bounded API and evidence

analyze_wait_marker_alignment accepts host-produced normalized messages and an authenticated actor query packet. It performs no model, network, file, or database access. Host registry/file authentication remains external. In-memory validation checks exact released query/index code pins, source/actor/projection/hash/time/window fields, coverage and room diagnostics. Preserve exact IDs, compact normalized-record fingerprints, existing compound content hashes, text hashes, source coordinates, and event raw-record/raw-line/projection pins with their distinct purposes.

Cap messages and events at 15,000 each, aggregate chat content at 32 MiB, individual content at 1 MiB, marker spans at 100,000 total, controls at 64, and candidate links at 20,000. Default aggregate work proxy budget is one million units, maximum two million. Finite input validation and literal scanning precede the proxy check; all planned message/event/horizon comparisons are checked before any candidate alignment. This is not a wall-clock guarantee. Over-budget output is explicitly unknown with no partial alignments or selectively retained ranks. Output is finite JSON, bounded to 16 MiB. Exceeding span/link/output bounds fails without sampling.

Tests must cover negation/quotation, ties, exact horizon endpoints, clock-policy differences/unknowns, human exclusion, cross-actor and cross-window cases, boundary censoring, identity/hash/source forgery, missing metadata, partial/truncated packets, incomplete action scopes, work bounds, privacy, input immutability, deterministic controls, and absence of file/model/database access. The [actor/time contract](actor-time-observation-contract.md) remains unchanged.

Any subsequent semantic validation needs blinded manual labels with a separate definition of reported waiting, scheduling choice, resource access, or verified inactivity, plus source completeness and clock evidence. A future intervention would require prospective assignment and verified outcomes. Neither nearby recorded actions nor missing nearby candidates identify a historical mental state or mechanism.
