# Independent causal review: complementary information study

Review date: 2026-10-04. This is a design review, not a frozen protocol or an experimental result. No model calls or protocol registration were made by the reviewer.

## Current review decision

The revised world and its complementary experiment runner pass the reviewed information-boundary, oracle, three-round feasibility and execution requirements. They are **ready for locally frozen registration and a bounded eight-run pilot**. This is approval of the implemented mechanics and declared causal scope, not a prediction of a favorable result or confirmation of a theory.

The world received independent review before the reviewer was assigned to implement the experiment runner. Runner checks are engineering verification by that same contributor, supplemented by the separately maintained replay dispatcher; they are not an external independent audit.

The reviewed scientific source hashes are:

| Source | SHA-256 |
|---|---|
| `complementary_environment.py` | `f301434dbd763ed201696eec218a1182d9ceead57a79e4c2e6cd45b7bb9c442f` |
| `complementary_experiments.py` | `4f68d1f5447dffa57283559678484e8daf1d5df02df1c6b868887d1a168d9d08` |
| `diffusion_environment.py` | `ee5bea0eabf5ef2c5e2f844b269cc5f22a635b76e997327797da2cb693226049` |
| `diffusion_experiments.py` | `f5d8eaf479276e5ee1ebec3ad945fbef08116603bff21b9471818c7c4b7d922f` |
| `audit.py` | `782e15b8a1ae83eed2e01b153f7f31430d81f4d64fc37907e0d5073eca9d062e` |

The protocol pins these dependencies. Editing them requires a new registration. Pipeline, CLI and product interface integration can proceed without changing those scientific files.

The reason for the new world is explicit complementarity: the answer depends on several private observations, so information sharing can matter to the task. This tests a synthetic coordination problem inspired by an observational candidate. It does not validate the historical candidate, reproduce the historical tools, or establish why Village agents communicated little.

## Verified in the first environment implementation

- Four original measurements have distinct original IDs, fragment IDs and holders. The target is computed independently in code; agent explanations and agreement do not determine correctness.
- Subject requests expose only the selected subject's observations, direct received messages, own sent messages, private context and own action history. Oracle state, seeds and global transcripts remain privileged.
- Each subject initially sees only its own private original. Reinspection is own-only. Forwarding attaches only known canonical originals. Actions cannot manufacture fragment values, integrity hashes or transmission paths.
- Bundles preserve original values and relay lineage. Repeated receipt does not create a new component. Free-text claims remain possible and unverified.
- Submissions are irrevocable, with no correctness feedback. Canonical coverage is captured at the time of submission, so later relays cannot explain an earlier answer.
- Truth generation and scheduling use independent random streams. Changing topology at a fixed environment seed preserves the measurement values and schedule.
- Reset restores the original state and clears messages, submissions, contexts, acquired fragments and action history.

Canonical attachment coverage measures authenticated tool-visible evidence. It is not a measure of mental knowledge: agents may infer values from unverified free text. Report it under that restricted interpretation.

## Budget and feasibility findings

In the initial implementation, three turns commonly require inspect, one unicast send, and submit. A single send can relay a bundle, but each sender has only one delivery opportunity. This can create a structural dissemination ceiling. It is insufficient to describe an observed failure as a reluctance to collaborate without considering that ceiling.

A local scripted plumbing policy over twelve seeds produced mean network accuracy of approximately 0.27, 0.29 and 0.31 for ring, star and complete at three rounds. At eight rounds it obtained 1.0 in all three topologies. These are synthetic execution checks only; the policy ignores planted contexts and supplies no evidence about hosted models or treatment effects. The seed grid was chosen for feasibility checks and is not confirmatory data.

Eight networks with four agents and eight rounds require up to 256 subject calls. The proposed short study permits 96: eight networks × four agents × three turns. The new world must make those opportunities meaningful before freezing that budget.

A short-budget revision now makes each subject's own private fragment available in its initial observation and permits two communication turns plus submission. It adds `send_neighbors`, which multicasts a canonical bundle to all connected neighbors for one message-action unit. Each recipient delivery is separately logged with lineage. Bundled relay and neighbor multicast make all-gather possible in two complete rounds on all built-in graphs, whose diameter is at most two, regardless of within-round order. This feasibility witness supplies no oracle to the policy and does not force real subjects to use that strategy.

For a four-node star, a hub needs at least three outgoing unicast deliveries to distribute a full bundle separately to all leaves. The new neighbor multicast action removes that structural limitation by making several deliveries per action. This is a deliberate channel model, with degree-dependent fanout, not matched bandwidth. The smallest proposed pilot still uses ring and complete; the world also supports star and custom disconnected graphs.

The independent reviewer executed the revised scripted policy across 100 seeds for each ring, star and complete world. All 300 runs attained mean exact accuracy 1.0 and full canonical coverage at submission within twelve decisions. Average message actions were approximately 7.1, 6.9 and 7.0, while recipient deliveries were approximately 14.1, 10.5 and 21.0. The unequal fanout is visible and must be treated as part of the topology opportunity bundle. The fourteen environment tests also passed. Dynamic subject action schemas now restrict totals to the declared residue range.

## Exact complementarity option

The revised world uses four independently uniform residues, with the target equal to their sum modulo 97 by default. Given any strict subset of originals, the unobserved residue sum remains uniform modulo 97. Thus the target cannot be identified from that subset, and an answer can still be lucky with probability 1/97. Observing all originals determines the answer. This argument also holds for the supported composite moduli because it uses the finite additive group, not division. The reviewer checked the conditional distributions exhaustively for moduli 2, 3 and 5. This proof depends on the declared generator and cannot be transferred to real-world source labels.

The initial integer-sum implementation also had complementary information, but a partial sum changed the prior distribution of the target. Claims that partial observations contained no target information would have been false there. The modular revision updates its task text, action bounds, oracle, offline policy, capabilities and fidelity descriptors together. Absolute error between integer representatives is declared representation-dependent and descriptive; exact accuracy remains primary.

## Smallest proposed online design

The proposal is eight independently reset networks, balanced across ring/complete topology and neutral/provenance private context, two runs per cell. One fixed subject receives its assigned context immediately before its first decision, retained only in that run. Other subjects may be affected through communication; that spillover belongs to the network-level effect.

The experimental unit is the entire interacting network. Four subjects or twelve actions are not four or twelve randomized samples. The primary outcome should be mean exact-answer accuracy across all four subjects, with absent submissions scored zero. Report completion separately. Partial-answer error, canonical coverage, messages and invalid actions are secondary process descriptions.

Define two primary contrasts before execution: reminder versus neutral context averaged equally across topology, and complete versus ring averaged equally across context. Conditional randomization tests preserve counts within the other factor and test sharp no-effect nulls: each network's outcome would be unchanged by the tested factor, holding the other factor fixed. They are not exact weak-null tests of zero average effect under heterogeneous network effects. Holm correction covers the declared primary family. Individual intervals remain nonsimultaneous. Interaction estimates and individual-cell comparisons are exploratory at this size.

With two runs per factorial cell, each factor's conditional assignment space has `choose(4,2)^2 = 36` possibilities. A symmetric two-sided exact test has a minimum attainable p-value of `2/36 ≈ 0.0556`; Holm adjustment across two primary comparisons cannot produce a value below 0.05. This pilot can demonstrate execution, reveal behavior and estimate effects with substantial uncertainty. It cannot deliver conventional confirmatory significance, even with perfect separation. A null or negative estimate must remain visible, and a wide interval does not establish no effect.

## Causal scope and controls required before execution

Randomize whole-network cells and execution order. Use independent environment seeds for every run, stateless subject requests and fresh environment state. Hold model, harness, generation settings, task distribution, scheduling rule, message cap and allocated turns fixed across cells. Record the source hashes of the new modules and every reused scientific helper before subject execution.

Equal budgets do not hold information opportunity fixed. Topology changes neighbor choices, path length, relay burden and degree; that bundle is the assigned treatment. Achieved message count, canonical exposure and completion are post-treatment variables. Conditioning on them is not a valid shortcut to isolating mediation or removing confounding.

The reminder changes observable input text. It does not directly edit latent thoughts. A neutral note is a partial control for extra context and is not guaranteed psychologically inert; word count is not tokenizer-level length matching. Fix the recipient, wording, timing and persistence before execution. Label assignment, oracle values, original future events and researcher hypotheses must not enter the subject packet.

Source IDs establish component identity by construction. They do not imply general statistical independence, historical honesty or trustworthy reporting outside this world. No score may be assigned from the treatment label, intended hypothesis or narrative success claim. The offline policy should ignore treatment context; live nulls and harms are valid outcomes.

Invalid model actions consume scheduled budget and remain outcomes. Infrastructure failures must preserve a partial report and stop estimation; do not replace failures or drop incomplete networks to retain favorable results. Independent environment seeds do not control hosted-model sampling or guarantee provider stability. Frozen local registration is auditable, but is not a public preregistration registry.

## Completed runner verification

- Protocol and capability hashes, backend pinning, hidden arm labels, balanced whole-network assignments and the default 96-call bound pass.
- The assigned networks have distinct environment seeds. Truth and scheduler use separate within-network streams; no covert paired-seed design is introduced. Initial truth/fragment balance is descriptive and is not used to exclude networks.
- Private context arrives before the fixed focal subject's first action and persists only within its run. Default reminder and neutral notes both have 36 whitespace words; character and tokenizer lengths differ or remain unverified.
- Independent deterministic scoring, submission-time canonical coverage, exact conditional tests, Holm correction and bounded run-level uncertainty pass. A deliberately adverse local context-response policy produces a negative effect; there is no forced treatment benefit.
- Protocol, assignments, execution-code snapshots and each privileged initial state exist before subject decisions. Reports retain scoped requests, actions, tool results, receipts and forwarding lineage.
- Missing answers remain zeros; invalid actions consume budget. Constructor and transport failures persist incomplete execution without estimates. Analysis failure also remains incomplete. Reporting-callback failures cannot delete networks. Exclusions, reordered or duplicate units are rejected.
- Fresh offline execution passes the new replay dispatcher across all eight networks, with zero model calls. Re-signed false accuracy fails oracle replay. This replay establishes recorded transition and packet consistency, not new model behavior or historical fidelity.

The 33 combined world and experiment tests pass. The full repository suite passed 243 tests before the final replay-specific test was added. No online subject calls or live protocol registration were performed by this contributor; integration owns those steps and must freeze the requested backend before execution.
