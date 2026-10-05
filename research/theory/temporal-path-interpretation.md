# Interpreting the saved temporal reference-path audit

The audit finds time-order sensitivity in two selected windows. It corrects a claim about a representation: a static name-reference path can require moving backward in time. It does not identify delivery, mediation, influence, beliefs, novel behavior, or a reason to demote a behavioral candidate.

## Identity and reproducibility

Reviewed October 4, 2026; registered objects read through read-only SQLite. Store hashes use sorted-key, default-separator JSON encoded as UTF-8. These differ from compact-JSON record hashes and binary file hashes.

| Exact object | Version | Store SHA256 |
|---|---:|---|
| temporal_path_audit-1c08eba1b540 | 1 | 4ef7a67531cb9a2db9a8f7ba8ab1bbc403549cbe08e806c2b00a2cfb106e6512 |
| selected_lead_audit-cdb8875d4e64 | 1 | 3309d1e6e8d174fe5b8919af3288812de65de1c3993b74ec6a9ff001578e11b0 |
| dataset-5d2eef17db31 | 1 | 4351ceeb788cc000b6e288927299f20d68095e9a449a47bb6cef5e0791cc5c41 |
| discovery-3d29f6c7f419 | 3 | 32a06644e6fc1d83c42141b5640a092ac8d9d09bb82df171d779318fd535d403 |

All four hashes and all seven saved implementation pins match. The host reports source-audit replay passed; the pure instrument does not authenticate externally declared references itself. Instrument: strict-temporal-mentions-v1; explicit o1/o3 allowlist plus Unicode shadow. No model calls or persisted changes were made for this interpretation.

Binary implementation pins:

| File | SHA256 |
|---|---|
| temporal_network.py | f3d67c3c99aefc00d26897f138009290e442211c6b377142b6a17dcd87b26861 |
| dataset.py | b3d44304e84890d92a85bee89979fd64cf19aca8a587fd0182b5a74eac822999 |
| graph_discovery.py | 6ec021234d61fda3e3f8f8914fabbfc6eafc2ba804adcce79e0e31202a1b96ba |
| network.py | 421b184c7b288598c6718a15d6a88d64ed491a5b2b4ca6f949567a8a0a7651c7 |
| mention_sensitivity.py | 41396caf8789039c97716b92a931476c9fe4fb05f7f6f02637287df56e2c8ae5 |
| name_eligibility_sensitivity.py | 166e194bd0e52adb75d966cd9ee02f1362a2917f7d2f88004ecb8f3b8f6654fa |
| mention_graph_sensitivity.py | 728c4d22b42a2b42fdb154a797d6bf667f84c050afe30fe6264f594e1f104e84 |

The gzip source, ai-village/chat_messages.jsonl.gz, is 52,543,996 bytes; binary SHA256 c1d56ab7b437f65c985c3353697d92f668f3a7b83776913aa5e3eb93ed867bb7. The five cited source rows below were reread at their exact archive lines and normalize identically to the registered records. All 262 saved witnesses were checked against registered IDs, authors, timestamps, provenance, record/text hashes, matched coordinates, continuity, and strict ordering where required. These checks establish reproducibility, not semantic validity.

## Measurement and all six windows

An edge runs from the message author to a matched roster name. A message about B creates A→B even when B previously informed A; a public reference need not be addressed to B. The temporal direction therefore remains **reference direction**, not identified information flow.

Temporal paths require strictly increasing canonical UTC timestamps within one half-open room window. Simultaneous edges cannot relay through each other. Single-edge paths are valid. There is no maximum gap or processing-latency model. Static and temporal node deletion both recompute alternate paths and exclude pairs having the deleted node as an endpoint.

The universe is fixed within each window across variants: agent authors plus accepted agent-source targets. Human rows remain in the source scope; their outgoing matches and known nonagent targets are excluded. This is neither the legacy native universe nor the selected audit's pair-common universe. April17 19h has five nodes because o1 is referenced under expansion but has no authored message; the others have four. Unknown authorship does not establish an inactive or informed recipient.

Each cell is reachable-pair count static→temporal, then maximum deletion-loss fraction static→temporal. E = exact eligible names; S = E plus explicit short names; U = Unicode shadow without short names; US = shadow plus short names.

| UTC window, 2025 | Messages | E | S | U | US |
|---|---:|---|---|---|---|
| Apr17 18–19, window-561db93d169c977d | 50 | 2→2; 0→0 | 4→4; 0→0 | 2→2; 0→0 | 4→4; 0→0 |
| Apr17 19–20, window-46201f369829d997 | 81 | 6→6; 1/2→1/2 | 12→12; 1/2→1/2 | 6→6; 1/2→1/2 | 12→12; 1/2→1/2 |
| Apr18 18–19, window-3a4dd0d6e2db6941 | 70 | 4→3; 1→0 | 7→5; 2/3→1/2 | 6→4; 1→0 | 9→6; 3/4→1/3 |
| Apr18 19–20, window-c700fe3c721fd247 | 34 | 2→2; 0→0 | 4→4; 0→0 | 2→2; 0→0 | 4→4; 0→0 |
| Apr22 18–19, window-4dd82e3ac3b0d6e4 | 52 | 3→3; 1→1 | 5→5; 1/2→1/2 | 5→4; 1→1 | 7→6; 2/3→1/2 |
| Apr22 19–20, window-9e914aaef4dc1c17 | 62 | 4→4; 0→0 | 7→7; 0→0 | 7→7; 2/3→2/3 | 12→12; 1/2→1/2 |

Four windows are unchanged by time ordering within every instrument. That negative result does not establish observed relays: correctly ordered references may concern unrelated tasks.

## The reversed witness and ordinary alternatives

The Apr18 exact static-only path is Claude3.5→GPT-4.1→Claude3.7:

1. 585a9073-247b-484e-b5f6-e8888eebe2d2, **18:04:38.069866 UTC**, Claude3.5. It describes failed browser restoration and waiting to avoid adding system load while other agents use computers.
2. 6a8397f3-9e33-4354-a564-0a7f3cc2d839, **18:01:17.314578 UTC**, GPT-4.1. It describes waiting for Claude3.7's reply about priorities.

The second event predates the first. Thus this reference path cannot be a forward relay under this instrument. Neither message verifies receipt or browser state.

Apr18's additional shadow path uses c32455a6-dedf-4908-9276-21ff443fb9f7 at 18:15:06.248414: o3 reports a human reassignment to GPT‑4.1. That is compatible with common instructions and task ownership, rather than interpersonal transmission through the earlier waiting message.

Apr22's shadow-only invalid route likewise combines c20353f3-939f-42b1-81c1-23f45ad3d51c at **18:48:35.098990** (o3's unfinished chart-publication report) with 3e384c47-2340-4fd4-9e00-678981ef8677 at **18:20:45.000748** (GPT-4.1's unfinished document-sharing report). Different artifacts and reverse chronology both limit a relay interpretation.

| Source ID | Archive line | Normalized record SHA256 | Original text SHA256 |
|---|---:|---|---|
| 585a9073-247b-484e-b5f6-e8888eebe2d2 | 63410 | c9f1d9b249dbd98e09e78bcae10d1782bc004ab579b874a76826c6f7ffc65f58 | 6f0559a4a73ac0db71d587ba1e9145d5757cfa9348f8f8ea5886c476b3a22e07 |
| 6a8397f3-9e33-4354-a564-0a7f3cc2d839 | 76384 | 4fdba346cd15dfb3dc32378b4f0455018eee9d305bbec51a49dc9a4d91db70f5 | 987d2f84c571513deaaa9b2b4b98ba9da1a87b0f00eb39536cbf4579324e1264 |
| c32455a6-dedf-4908-9276-21ff443fb9f7 | 139908 | 03dd62a494b613341379b5efe9f1c52e90aea2facf90cda1a05a54257f9b2a61 | 083c2e20d7ede8fcc6bce931337342eba7ed0ea470533b458369df2f091afa67 |
| c20353f3-939f-42b1-81c1-23f45ad3d51c | 139136 | def43b1ae3df527af23db8abcded45fd24f4706816c04e55fa5940faacd28a5a | 74754a89a189164aca74dbb4b4077d24ebafd7fc6df1b463b1b89a1a9dd368d2 |
| 3e384c47-2340-4fd4-9e00-678981ef8677 | 44458 | 7757ccdbc2262026d220db0de24fc8080772f5dc76f41894cf36817319583054 | 8f32e8170e2270e02a7d703086e6ab12c5fd2d17c3852d8101edc0fba08e077d |

## Relation to the frozen leads

The six windows support eleven previously selected contrasts. Preserve their orientation, selection, and rank.

- graph-lead-b6596ef27db8ec49 compares Apr17 19h minus Apr18 18h. Under this audit's exact universe, deletion difference changes from −1/2 static to +1/2 temporal; US changes −1/4 to +1/6.
- graph-lead-b2c7d08d1c926822 compares Apr22 18h minus 19h. Exact difference remains +1; US changes +1/6 to 0.
- graph-lead-801fea2f65179e17 and graph-lead-9936c86cea663602 retain −1/2 in both exact and US diagnostics.
- Concentration and reciprocity leads are not recomputed or falsified by a path-order instrument.

The earlier [source interpretation](selected-lead-interpretation.md) distinguishes explicit wait/update language from graph mediation. Those reports survive. The owner candidate concerns an incoming-concentration contrast, which temporal reachability does not test. Neither candidate is automatically demoted or promoted.

## Discriminating validation and interventions

First adjudicate direct address, attribution, status narration, and common instruction independently of graph score. Verify artifact versions, actual inspection, recipient exposure, and acknowledgment before assigning transfer. Audit other rooms and window boundaries; missing periods remain unknown.

A prospective relay test should distribute private evidence that genuinely requires exchange. Randomize delivery order or a relay's availability while holding content, access, scheduling, and task difficulty fixed; log sender, recipient, visible payload, and consumption. Predeclare outcomes and network-level assignment/interference. Capability checks must establish solvability and realized exchange first. Success before the alleged relay or verified success through other channels challenges its proposed necessity; joint failure or weak precision remains inconclusive. Representation deletion itself supplies no intervention.

A separate thought-insertion experiment can randomize a source-check prompt against matched neutral context at an identical logged predecision gate. Its outcome must concern verified inspection or grounded decisions, not a name-reference score. Test manipulation uptake and environment fidelity; a behavioral effect would not retrospectively identify these historical paths.

This is same-source, post-selection sensitivity: eleven leads arose from 39 feature-window comparisons. No new search, independent replication, null p-value, or novelty claim follows. Freeze instruments and hypotheses before held-out episodes. Temporal aggregation limits motivate this check, as in [Holme and Saramäki, Temporal Networks](https://arxiv.org/abs/1108.1780); their contact-network framework does not establish that these mentions are contacts. See [graph methods](graph-math-methods.md) for the broader operator distinctions.
