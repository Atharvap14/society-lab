"""Save a concise continuation checkpoint from the actual local call/job ledger."""
import json
import argparse
import hashlib
import re
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from swarm_lab.pipeline import Lab
from swarm_lab.store import now

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tests',type=int)
    parser.add_argument('--test-log')
    parser.add_argument('--test-started')
    parser.add_argument('--regression-running',action='store_true')
    args=parser.parse_args()
    if args.tests is not None and args.tests<=0:parser.error('--tests must be positive')
    if args.tests and args.regression_running:parser.error('Choose completed tests or running regression')
    lab=Lab();path=lab.settings.root/'BUILD_STATE.json'
    state=json.loads(path.read_text(encoding='utf-8'))
    state.update(status='building',updated_utc=now())
    if args.tests:state['last_full_test']={'count':args.tests,'passed':True,'note':'Full repository suite passed; later integration changes require their own checks.'}
    state['completed']=[
        'Read-only GCS dataset mount and verified HF source provenance',
        'Bounded chronological ingestion with exact object/source versions',
        'Typed behavioral screening and graph evidence channels',
        'Directed network metrics, Laplacian basis, spectral observable rates with explicit missingness',
        'Temporal graph lead search with matched windows and sensitivity checks',
        'Six role prompts and actual validated SKILL.md files loaded into harnesses',
        'Responses and read-only Codex research harness adapters',
        'Append-only behavior/theory library with finite facts and independent-seed replication links',
        'Four compiler families with executable worlds; separate correction relay adds the fifth distinct world, each with scoped observations and independent oracles',
        'Whole-team/network randomization and private observable-context interventions',
        'Live original artifact pilot, held-out-seed artifact study, noisy-source study and complementary study',
        'All 37 completed live team/network units replayed; negative and inconclusive results retained',
        'Numerical/semantic evaluator errors preserved; finite result fact checks pass',
        'Corrected graph skeptical reviews retain descriptive candidates and ordinary rivals',
        'Capability-driven environment compiler rejects unsupported requirements and stale reviews',
        'Local dashboard workflow tested through actual browser and isolated loopback API',
        'Windows server timestamp/duplicate-listener bug fixed and restart verified',
        'Standalone audited report regenerated with byte-preserved earlier editions',
        'Actual agentic source-gating refusal and compiled-but-blocked world-fit review retained',
        'Approved blueprint bridge preserves exact worlds through registration, execution, replay and finite facts',
        'Research-only source inspection, literal multi-term searches and per-invocation retrieval logs',
        'Following-week588-message import and two parallel investigator/skeptic workflows',
        'Unicode sensitivity reproduces62 exact versus81 shadow nonself graph-eligible pairs',
        'Explicit short-name eligibility audit retains 81 o1/o3 candidate pairs without widening the original graph',
        'Four independently recomputed diagnostic graph variants on a fixed common node universe',
        'Optional resource workflow connected through compiler, registration, execution, replay and finite fact checks',
        'Saved four-swarm scripted resource study replayed and 24 typed facts checked without hosted calls',
        'Actual dashboard QA and saved proofs for resource outcomes and graph measurement sensitivity',
        'Primary-source graph-math methods,38-ID communication falsifiers and20-case short-name adjudication',
        'Selected11-lead audit replays all588 source rows and preserves six windows/four original ordered pairs',
        'Native/fixed-pair measurement sensitivity records one sign reversal without changing discovery or candidate status',
        'Exact selected-audit pins reach both prospective research roles and persist in library metadata',
        'Bounded paginated theory reference reads preserve raw UTF8 identity and explicit truncation',
        'Standalone arm-blind timing controller passed33 focused tests and29 independent adversarial checks',
        'Strict temporal reference-path audit of six original windows independently reproduced without model calls',
        'All262 temporal witnesses source-checked; backward-time paths retained as measurement diagnostics',
        'Bounded temporal measurement excerpts reach both prospective research roles with exact selected-parent pins',
        'New paired-world event-triggered reminder runner registered, executed through dashboard and replayed',
        'Four scripted timing swarms retain identical exogenous paths within each pair and all four boundary receipts',
        'Actual dashboard timing fact audit checked24 typed assertions with source/archive/action/numerical gates',
        'Dashboard contracts cover temporal/timing actions, partial outcomes, navigation and execution-mode guards',
        'Bounded explicit source-lineage scanner/join/wrapper passed64 focused adversarial and public CLI checks',
        'Narrow WinFsp1005 path fallback reads real file bytes with declared lexical-path scope',
        'Actual four-channel prefix probe checked8 original row pins and freshly reproduced131 retained rows/103 relation attempts',
        'Three field-checked exported links retained separately from93 scoped unresolved parents and7 absent keys',
        'Actual dashboard source reread job completed with exact audit version/hash and zero model calls',
        'Report source-lineage tables require current source/plan/code pins and independent bounded filesystem derivation',
        'Graph-operator agenda and multiplex causal experiment framework available through bounded research reference tools',
        'Complete mounted event-file index:381610 parsed rows, gzip integrity, declared object size and MD5 matched',
        'All250 selected agent chats corroborated by exact exported emission fields;99 user records retain separate unknown scope',
        'Authenticated local-index replay independently reproduces six original selected windows without full-source reread',
        'Conditional timestamp reference:24 graph cells,64 message-group draws per cell and fresh frozen-source replay',
        'Timestamp reference envelopes/ranks and indexed-event checks visible in dashboard with zero-call replay controls',
        'Checkpointed generic cycle composes four real CPU worlds with exact source/world/backend pins and guarded hypothesis curation',
        'Public cycle CLI/API preserve distinct stage identities, durable blocked outputs and no-repeat completed resume',
        'Live cycle preserves uncited-observation rejection and amended compiled proposal whose reviewer reached the400-request cap']
    state['completed'].append('Pinned actor/time workflow reproduces183 platform events omitted by room predicates:16WAIT/84START/83STOP, all room-missing')
    state['completed'].append('Fixed retrospective wait-word instrument freshly reproduces 34 marker messages, 32 comparison messages and 21 links to 14 WAIT records; no semantic accuracy or causal claim')
    state['completed'] += [
        'Atomic compare-and-put cycle checkpoints bind exact stage/root job closures and prevent stale concurrent overwrite or repeated execution',
        'Public actor/time, literal-marker and edge-flow CLI/API actions pass exact-version checks and strict finite HTTP envelope validation',
        'Optional source-bound Hodge workflow reproduces all24 original cells; gradient/circulation use declared net-reference counts while curl/harmonic remain unknown',
        'Actual dashboard actor/time, wait-marker and Hodge zero-call replay jobs passed; numerical values and unavailable quantities remain separate',
        'Independent supplied amendment review narrows the capped artifact proposal to implemented publication correctness without erasing its original failure',
        'Amended zero-call scripted cycle completed6 stages/6 swarms/24 finite facts and saved an untested analogue hypothesis; historical resume retained one result',
        'Research prompts and role skills preserve room missingness, literal-marker controls, graph operator conventions and distinct evidence gates']
    state['completed'] += [
        'Bounded recorded actor/wait/Hodge packets reach both prospective roles and saved attempts; all11 production comparisons checked read-only without new model calls',
        'Immutable context-bearing proposal snapshots persist in new library registrations and typed paired-source/context resume checks precede every reviewer harness',
        'Queue alone publishes terminal result links; nested failures preserve incomplete artifacts and shared store/CAS/call accounting semantics']
    state['completed'] += [
        'Separate reviewed revision-relay adapter/runner/host promoted unchanged with96 production-import focused checks',
        'Nine executable relay UI checks and45 public-interface/reference/queue checks passed; exact versions, full reserved-call cap and no-repeat study claims enforced',
        'Actual dashboard relay design/execute/replay completed8 scripted teams32 decisions; thirteen exact local checks passed, D0 and interval/p-value unavailable']
    state['completed'] += [
        'Read-only episode workspace binds exact original leads/comparators, rival hypotheses, bounded source excerpts and separate recorded measurement gates',
        'Actual browser episode-to-authoring question transfer preserved draft text, cleared observation/capability choices and launched no job',
        'Independent episode packet, loopback API, browser-render and host-route checks passed without model calls',
        'Experiment choice map available through the bounded reference reader; research traces hash the exact frozen invocation instructions']
    state['completed'] += [
        'Generic binary measurement adjudication with frozen canonical samples, uncertain/missing labels, declared reviewer history and exact-version concurrent saves',
        'Thirty core checks, public loopback/CLI workflows and actual renderer/host regressions pass without provider calls',
        'Actual browser froze16 of588 retained messages and saved one explicitly agent-assisted uncertain workflow declaration; independent16-gate production check passed',
        'Measurement output links distinguish latest accepted review presentation from exact read-only review snapshots; unknown acknowledgements block automatic repeats']
    state['completed'] += [
        'Compact dashboard inventory cache validates full registry fingerprints on rebuild and invalidates on observed database changes; exact scientific-object reads remain uncached',
        'Twenty-four cache checks, five public API checks and an overlapping69-check cache/role cohort passed without providers',
        'Actual browser rejected an incomplete judgment and preserved all unsaved fields across message navigation; three independent draft-binding regressions passed',
        'Discovery/skeptic skills route construct review through the measurement guide; both skill validations and research-contract checks passed']
    state['completed'] += [
        'Episode Study guide compares six supported assignments/outcomes/falsifiers and carries an unregistered exact-origin question across design controls without jobs or implicit sources',
        'Actual browser carried the original correction-routing question into the relay form with blocks2/seed173/Liveoff unchanged; guide and retained-draft screenshots inspected',
        'Saved Laplacian language-signal tables preserve node denominators, unknowns, full/induced populations, grouped energy and operator limits',
        'Two independent spectral display defects fixed before release: grouping must bind the saved spectrum and message-hit proportions cannot be negative',
        'Actual browser displayed completion-hit counts3/5/5/0 on93/164/91/60 authored messages and an all-null reply operator without inferring agreement',
        'New guide textarea and spectral selector regain focus after requested redraw; peer checks preserve exact caret, source pins and execution settings']
    state['completed'] += [
        'Fresh isolated complete-source copy finished the documented authored eight-message workflow, six scripted teams, replay and24 finite facts at zero calls',
        'Construct-status guide distinguishes implemented observable instruments from proposed grounding, discharge, repair, memory and latent-state measures',
        'Read-only exact blueprint compatibility shares actual registration preparation and preserves separate construction, review, current-source and design gates',
        'Independent resealed-world probe found and fixed contradictory saved-spec acceptance before preview or actual registration',
        'Paired CLI blueprint version/hash and dashboard exact-bound registration preserve the previewed world; decision opportunities remain separate from hosted calls']
    state['completed'] += [
        'Initial artifact-workflow screening distinguishes eligible, different-world, declined and unavailable recommendations without changing saved enum values or four-family dispatch',
        'Behavior-library source failures preserve the record, critique and history; exact dataset pins and cited membership are required for source-dependent navigation, with no latest substitution']
    state['in_progress']=[
        'Additional source-channel and construct validation while preserving missing rooms and unknown exposure',
        'Further calibration of graph signals, missingness, task/role baselines and directed-operator assumptions',
        'Empirical policy studies beyond first-decision notes, subject to configured request cap',
        'Further experimental identification, negative cases and theory/library refinement']
    state['in_progress'] += ['Frozen full repository regression after registration-preview integration',
                             'Behavioral-theory refinement and supported graph-to-experiment usability review',
                             'Final browser evidence checks and checkpoint refinement']
    state['artifacts'].update(
        graph_behavior_ids=['behavior-c6795bc08068','behavior-ad77419c8fab'],
        network_experiment_id='network_experiment-b215b2b47aef',
        replication_experiment_id='experiment-b46d02ce332c',replication_id='replication-cbab2c182ad8',
        complementary_protocol_id='complementary_protocol-0d57a2d8f2dc',
        complementary_experiment_id='complementary_experiment-95e2a6857435',
        complementary_verification_id='verification-834a56a6765a',
        complementary_claim_audit_id='claim_audit-54c25c5e4ba8',
        report='.runtime/reports/pilot-audit/research-report.html',
        source_review='research/theory/graph-lead-review.md',
        following_week_dataset_id='dataset-5d2eef17db31',following_week_discovery_id='discovery-3d29f6c7f419',
        following_week_behavior_ids=['behavior-4d47c2a27a29','behavior-e0e48fd6fd98'],
        mention_sensitivity_id='measurement_audit-59899929fe3a',
        name_eligibility_audit_id='name_eligibility_audit-efb71d2a7205',
        graph_measurement_audit_id='graph_measurement_audit-0304268ac6eb',
        selected_lead_audit_id='selected_lead_audit-cdb8875d4e64',
        temporal_path_audit_id='temporal_path_audit-1c08eba1b540',
        temporal_verification_id='verification-f50f5acd1792',
        timed_resource_protocol_id='timed_resource_protocol-0f7562f223af',
        timed_resource_experiment_id='timed_resource_experiment-0c252f3dbff8',
        timed_resource_verification_id='verification-642e686ee280',
        timed_resource_claim_audit_id='claim_audit-d6091f415f62',
        source_link_audit_id='source_link_audit-dcdbaca46070',
        source_link_verification_id='verification-3f359f39b5e7',
        source_link_dashboard_verification_id='verification-f33147822d2b',
        event_source_index_id='event_source_index-71b617501d7e',
        indexed_event_audit_id='indexed_event_audit-d83283eae5b3',
        indexed_event_verification_id='verification-eaa813f998dc',
        temporal_timestamp_reference_id='temporal_timestamp_reference-2982e3922a42',
        temporal_timestamp_verification_id='verification-fd8bb1e36ee1',
        indexed_event_dashboard_verification_id='verification-abaa46e22804',
        temporal_timestamp_dashboard_verification_id='verification-6314375cfb7a',
        actor_event_audit_id='actor_event_audit-29756e356310',
        actor_event_verification_id='verification-02300cf38ab3',
        wait_marker_alignment_id='wait_marker_alignment_audit-da8509c85911',
        wait_marker_verification_id='verification-bf9c71828932',
        actor_event_dashboard_verification_id='verification-333541a39ab1',
        wait_marker_dashboard_verification_id='verification-f6fe918d78b8',
        graph_hodge_audit_id='graph_hodge_audit-5e784a84b49e',
        graph_hodge_verification_id='verification-47e957b13efc',
        graph_hodge_dashboard_verification_id='verification-9e08158f16ea',
        completed_scripted_research_cycle_id='research_cycle-7583a43b6b7eae1b1d01',
        amended_cycle_blueprint_id='environment_blueprint-ad63fbe45bae',
        amended_cycle_protocol_id='protocol-527ea43c516d',
        amended_cycle_result_id='experiment-b76584574e67',
        amended_cycle_verification_id='verification-25937b68e045',
        amended_cycle_claim_audit_id='claim_audit-9185c19a8d2b',
        amended_cycle_theory_id='theory-cycle-e92173cd2a3b9668e602',
        blocked_research_cycle_id='research_cycle-8036534051434f0911d1',
        failed_research_cycle_id='research_cycle-911a9c351b21971338b3',
        compiled_cycle_attempt_id='environment_construction_attempt-3336f6d67891',
        resource_protocol_id='resource_protocol-bb372b23896c',resource_experiment_id='resource_experiment-9905757e6e68',
        resource_verification_id='verification-320ad7ccc5b6',resource_claim_audit_id='claim_audit-5efa478fa0e3',
        unsupported_blueprint_id='environment_blueprint-b95533102a5f',
        blocked_compiled_blueprint_id='environment_blueprint-e9516be18166',
        graph_methods='research/theory/graph-math-methods.md',
        communication_falsifiers='research/theory/communication-falsifiers.md',
        short_name_adjudication='research/theory/short-name-adjudication.md',
        resource_design='research/theory/resource-study-design.md',
        selected_lead_plan='research/theory/selected-lead-sensitivity-plan.md',
        intervention_timing='research/theory/intervention-timing.md',
        temporal_interpretation='research/theory/temporal-path-interpretation.md',
        source_triangulation='research/theory/source-triangulation-plan.md',
        source_probe_plan='.runtime/protocols/source-lineage-probe-20261004.json',
        multiplex_experiments='research/theory/multiplex-communication-experiments.md',
        graph_operator_agenda='research/theory/graph-operator-research-agenda.md',
        indexed_events_interpretation='research/theory/indexed-events-interpretation.md',
        temporal_null_methods='research/theory/temporal-null-methods.md',
        research_cycle_contract='research/research-cycle-contract.md',
        actor_time_contract='research/theory/actor-time-observation-contract.md',
        actor_window_interpretation='research/theory/actor-window-interpretation.md',
        wait_marker_plan='research/theory/wait-marker-alignment-plan.md',
        wait_marker_interpretation='research/theory/wait-marker-interpretation.md',
        graph_hodge_methods='research/theory/graph-hodge-methods.md',
        selected_edge_flow_plan='research/theory/selected-edge-flow-plan.md',
        selected_edge_flow_interpretation='research/theory/selected-edge-flow-interpretation.md',
        cycle_fit_review='research/cycle-fit-review-20261004.md',
        cycle_amendment='research/cycle-artifact-amendment-20261004.json',
        cycle_amendment_review='research/cycle-artifact-amendment-review-20261004.md',
        cycle_amendment_execution='research/cycle-artifact-amendment-execution-20261004.md',
        cycle_amendment_production_check='research/cycle-artifact-amendment-production-check-20261004.md',
        recorded_observation_contract='research/theory/recorded-observation-context.md',
        prospective_context_check='research/prospective-context-check-20261004.md',
        correction_relay_draft='research/theory/correction-relay-experiment-draft.md',
        correction_relay_review='research/theory/correction-relay-experiment-review.md',
        correction_relay_implementation='research/theory/correction-relay-implementation.md',
        correction_relay_production_check='research/correction-relay-production-check-20261004.md',
        correction_relay_protocol_id='revision_relay_protocol-0c41a067f805',
        correction_relay_result_id='revision_relay_experiment-ce1209221caa',
        correction_relay_verification_id='verification-8c2cca894899',
        correction_relay_screenshot='.runtime/screenshots/revision-relay-replay-proof.png',
        correction_relay_grid_screenshot='.runtime/screenshots/revision-relay-replayed.png',
        correction_relay_request_screenshot='.runtime/screenshots/revision-relay-request-trace.png',
        episode_workspace_guide='research/episode-workspace.md',
        episode_workspace_peer_check='research/episode-workspace-peer-check-20261004.md',
        episode_study_card='research/episode-to-study-card-20261004.md',
        experiment_choice_map='research/theory/experiment-choice-map.md',
        communication_model_comparison='research/theory/communication-model-comparison.md',
        measurement_review_guide='research/theory/measurement-adjudication.md',
        measurement_review_production_check='research/measurement-review-production-check-20261004.md',
        dashboard_state_cache_check='research/dashboard-state-cache-check-20261004.md',
        episode_study_guide_screenshot='.runtime/screenshots/episode-study-guide.png',
        episode_study_relay_screenshot='.runtime/screenshots/episode-study-relay-draft.png',
        spectral_language_screenshot='.runtime/screenshots/spectral-language-signals.png',
        spectral_reply_null_screenshot='.runtime/screenshots/spectral-reply-null-operator.png',
        measurement_sample_id='measurement_sample-4c473a7cfacd',
        measurement_review_id='measurement_review-4c473a7cfacd',
        measurement_review_screenshot='.runtime/screenshots/measurement-review-unknowns-final.png',
        measurement_sample_screenshot='.runtime/screenshots/measurement-review-source-pins.png',
        measurement_snapshot_screenshot='.runtime/screenshots/measurement-review-exact-snapshot.png',
        episode_overview_screenshot='.runtime/screenshots/episode-workspace-overview.png',
        episode_question_screenshot='.runtime/screenshots/episode-question-transfer.png',
        episode_actor_screenshot='.runtime/screenshots/episode-actor-observations.png',
        episode_edge_flow_screenshot='.runtime/screenshots/episode-static-edge-algebra.png',
        actor_event_screenshot='.runtime/screenshots/selected-actor-events.png',
        literal_wait_screenshot='.runtime/screenshots/literal-wait-proximity.png',
        edge_flow_screenshot='.runtime/screenshots/static-edge-count-algebra.png',
        restarted_edge_flow_screenshot='.runtime/screenshots/static-edge-count-after-restart.png',
        completed_cycle_screenshot='.runtime/screenshots/completed-amended-cycle.png',
        indexed_event_screenshot='.runtime/screenshots/indexed-selected-events.png',
        temporal_timestamp_screenshot='.runtime/screenshots/conditional-timestamp-reference.png',
        temporal_screenshot='.runtime/screenshots/temporal-reference-paths.png',
        timing_screenshot='.runtime/screenshots/triggered-reminder-replay.png',
        timing_facts_screenshot='.runtime/screenshots/triggered-reminder-facts.png',
        source_link_screenshot='.runtime/screenshots/source-lineage-replay.png',
        selected_lead_screenshot='.runtime/screenshots/selected-lead-sensitivity.png',
        graph_sensitivity_screenshot='.runtime/screenshots/graph-measurement-sensitivity.png',
        resource_screenshot='.runtime/screenshots/resource-smoke-test.png',
        authoring_screenshot='.runtime/screenshots/environment-fit-blocked.png')
    state['artifacts'].update(
        first_session_guide='research/first-session.md',
        first_session_isolated_proof='.runtime/first-session-isolated-smoke-20261004.json',
        demo_walkthrough='research/demo-walkthrough.md',
        construct_status='research/theory/construct-status.md',
        registration_compatibility_guide='research/registration-compatibility.md',
        registration_compatibility_read_proof='.runtime/registration-preview-production-read-20261004.json',
        registration_compatibility_screenshot='.runtime/screenshots/registration-compatibility-preview.png')
    state['budget']={**state['budget'],**{'openai_calls':lab.store.usage()['calls'],
        'openai_calls_completed':lab.store.usage()['completed'],'usage':lab.store.usage()}}
    state['active_jobs']=lab.store.jobs(statuses=['queued','running'])
    state['budget']['cap_question']='Optional request to raise400 to800/1200 is pending; continue under400 without an explicit answer.'
    state['scientific_scope']={
        'artifact_replication':'Reminder 4/4, neutral note0/4, ordinarycontext3/4; positive registered reminder-neutral contrast in this task/model, uncertain reminder-baseline comparison.',
        'complementary_pilot':'All8 networks0accuracy;46unicasts34waits16incorrectvalidsubmissions;floor-limited causal comparison, observed affordance uptake only.',
        'graph_candidates':'Descriptive task-specific waiting and role-structured coordination; psychological mechanism and literature novelty unestablished.',
        'cheap_measurement':'Laya gated by physical RAM, Jev credential absent; operational failures/unsampled remain unknown without fallback.',
        'graph_measurement':'Same fixed five-node diagnostic universe has baseline exact62 pairs/nullity3, expanded exact143/nullity1. Incoming o3 matches0 to77; measurement sensitivity, not behavior change or confirmed address.',
        'selected_lead_measurement':'Original11 leads/six windows/four comparisons retained. One concentration contrast changes +.335→-.114 with explicit short names; Unicode+short gives+.025. Same-record post-selection sensitivity, no behavior/status promotion.',
        'resource_smoke_test':'Four scripted swarms; context-independent policy, different schedules, no empirical reminder effect or LLM finding. Global exclusivity remains invented.',
        'temporal_paths':'Six original windows under fixed within-window node universes. Apr18 exact4→3 reachablepairs and1→0 maximumbridge loss under strict timestamps. Reference direction only; no delivery, influence, selection changes or candidate promotion.',
        'timing_smoke_test':'Two independent seed blocks/four scripted swarms with identical paired scheduler/resource paths; four receipts, all87.5% completion,ITT0 CI[-1,1]p1. Policy ignores text; no LLM effect.',
        'source_lineage':'Retrospective known-prefix probe: four partial scans,131 retained rows,103 explicit relation attempts,3 scoped field-checked matches,93 unresolved parents and7 missingFKs. Fresh files/row/line/prefix/plan/code replay passed. No prevalence/April-window corroboration, exposure, success or influence claims.',
        'indexed_selected_events':'Complete exported event-file index with381610 rows;250/250 selected agent emissions field-match,99 user records outsideAGENT_TALK. Room/time action counts cannot include missing-room events. Export-naive clocks assumedUTC, not calibrated; no exposure or causal inference.',
        'timestamp_reference':'24 selected graph cells,64 conditional edge-bearing-message timestamp permutations per cell. Apr18exact observed3 reachablepairs;49draws4 and15draws3. Envelopes/ranks descriptive; exchangeability, significance and independent replication unestablished.',
        'literal_wait_alignment':'34 of 250 agent messages contain the fixed words. Same-actor WAIT candidates occur near 6/34 at 30 seconds and 7/34 at 300 seconds; 5/32 nonmarker comparison messages also have candidates at 300 seconds. Clock policies, missing rooms, censoring, selection and reuse remain explicit; no semantic accuracy or causal effect.',
        'hodge_edge_signal':'All24 selected window/extraction cells passed source-bound replay. Static unweighted net reference-count energy, original4/5-node universes and reciprocal cancellation; no2-cell complex, curl/harmonic unknown. Fractions and absolute energies differ; no hierarchy, rumor, chronological relay, novelty or causal claim.',
        'amended_scripted_cycle':'Explicit new supplied-review blueprint, six default-scripted swarms and24 finite facts, all6 stages completed. Policy can react to note text; correct publication2/2 active,1/2 neutral,0/2 baseline is scripted output only. New theory stays hypothesis; original behavior3 retained with authorized infrastructure-only experiment append4. Original capped review remains failed.',
        'research_cycle':'Allfour CPUworlds and CLI/API end-to-end checks pass. Live attempt1 blocked unciteddatasetclaim; amendedbuilder compiled butreviewer cap exhausted. No live-cycle subjects or theory; failedattempts retained. Existing37livepilotunits remain separately scoped.',
        'actor_events':'Exact four selected chat authors/six original time windows, no room predicate:183 validated events,16WAIT/84START/83STOP, allroommissing. Original emission counts unchanged. No lease reconstruction, elapsed inactivity, receipt, graphmerge or status promotion.',
        'historical_transport':'Unestablished; no historical outcomes or mental states inferred from chat/synthetic worlds.'}
    state['scientific_scope']['recorded_research_context']='All11 original selected comparisons checked read-only; two-window actor/marker/algebra packets preserve exact refs, fixed current producer bytes and stored-proof gates. Fresh-source/operator attestations false. No new finding, citations, promotion or hosted calls.'
    state['scientific_scope']['correction_relay']='Reviewed early/late correction×informative/sham bypass study, actual8scripted teams/2blocks32decisions and13fresh local checks. Allteamscorrect/D0; interval/p-value unavailable. Scripted infrastructure only, no LLM finding, relay mediation/reminder efficacy/historical transport or status promotion.'
    state['scientific_scope']['episode_workspace']='One exact original Apr22 graph case and comparator viewed with recorded actor/marker/Hodge gates, matching behavior4 and rivals. Read-only presentation/question transfer, no new scientific replay, provider call, historical identification or status promotion.'
    state['scientific_scope']['measurement_review']='Frozen N588/k16 canonical message sample and one explicitly agent-assisted uncertain infrastructure declaration: known0/uncertain1/missing15, agreement/precision/recall null. Current pinned cheap regex consistency checked; historical execution, calibration, human truth, population accuracy and behavior/theory promotion remain unestablished.'
    state['scientific_scope']['registration_preview']='Read-only exact-ref/current-source/body/design compatibility for four existing families; no protocol/job/call/reservation/archive/status change. Fixed constructor outcome and context contrast need not identify the motivating mechanism. Local gates establish no cloud access, upstream freshness, semantic truth or budget grant.'
    state['scientific_scope']['first_session']='Fresh unmodified CLI in an isolated complete-source copy, authored8messages/six scripted teams/replay/24 facts at zero calls. Infrastructure reproduction only; no Village or live-model finding. Companion source assets are required; wheel-only deployment is unsupported.'
    state['scientific_scope']['artifact_route_screening']='The retained experiment_fit enum screens the initial shared-artifact workflow only. Different-world, declined and unavailable recommendations are distinct; approved-blueprint dispatch across four authoring families does not consume this enum. Screening does not grant study compatibility or establish a mechanism.'
    state['artifact_route_scope_release']={
        'sources':{p:hashlib.sha256((lab.settings.root/p).read_bytes()).hexdigest() for p in (
            'swarm_lab/research.py','swarm_lab/pipeline.py','web/app.js','web/episode-workspace.js',
            'tests/test_artifact_route_scope.py')},
        'integration':{'count':105,'passed':True,'log':'.runtime/artifact-route-scope-integration-final-20261004.log'},
        'scope':'Overlapping engineering cohort after a wording/schema-description correction. No stored enum, historical record, world or causal assignment changed; later library-source repair and final full regression have their own scope.'}
    state['library_source_availability_release']={
        'sources':{p:hashlib.sha256((lab.settings.root/p).read_bytes()).hexdigest() for p in (
            'web/app.js','tests/test_library_source_availability.py','tests/test_artifact_route_scope.py')},
        'integration':{'count':34,'passed':True,'log':'.runtime/library-source-availability-integration-final-20261004.log'},
        'scope':'Overlapping library/dashboard/episode/registration engineering checks, including three source-availability tests with fifteen renderer scenarios. Missing declarations, exact-version failures, mismatched identities and absent cited records remain unavailable. UI identity consistency is not a fresh source/operator replay or semantic evidence validation.',
        'model_calls':0,'production_writes':0}
    state['registration_preview_release']={
        'sources':{p:hashlib.sha256((lab.settings.root/p).read_bytes()).hexdigest() for p in (
            'swarm_lab/experiment_authoring.py','swarm_lab/registration_preview.py','swarm_lab/server.py',
            'swarm_lab/cli.py','web/blueprint-registration-preview.js','web/app.js','web/index.html')},
        'backend':{'count':19,'passed':True,'log':'.runtime/registration-preview-production-focused-final-20261004.log'},
        'api_ui':{'count':15,'passed':True,'log':'.runtime/registration-preview-api-ui-focused-20261004.log'},
        'actual_app_routes':{'count':8,'passed':True,'log':'.runtime/blueprint-registration-routes-independent-20261004.log'},
        'integration':{'count':92,'passed':True,'log':'.runtime/registration-preview-integration-final-20261004-revised.log'},
        'production_read':{'path':'.runtime/registration-preview-production-read-20261004.json',
            'scope':'Actual saved-demo offline/live prospective GETs;182 object versions/60jobs/400calls/549traces row hashes unchanged. No fresh source/operator replay or provider invocation.'},
        'guide':'research/registration-compatibility.md','model_calls':0,
        'scope':'Overlapping isolated engineering cohorts, not a summed repository count or scientific/provider attestation. UI host regression and final full-suite result are recorded separately.'}
    sample=lab.store.get('measurement_sample-4c473a7cfacd',1)
    review=lab.store.get('measurement_review-4c473a7cfacd',2)
    state['measurement_review_release']={
        'sources':{p:hashlib.sha256((lab.settings.root/p).read_bytes()).hexdigest() for p in (
            'swarm_lab/measurement_adjudication.py','swarm_lab/measurement_review_workflow.py',
            'web/measurement-review.js','web/measurement-review-host.js','web/app.js','web/style.css')},
        'sample_ref':{k:sample[k] for k in ('id','version','hash')},
        'review_ref':{k:review[k] for k in ('id','version','hash')},
        'dataset_ref':sample['payload']['dataset_ref'],
        'integration':{'count':55,'passed':True,'log':'.runtime/measurement-review-integration-final-20261004.log'},
        'independent_host_ui':{'count':12,'passed':True,'renderer_inner_checks':18,'log':'.runtime/independent-measurement-review-host-20261004.log'},
        'draft_binding_host_dashboard':{'count':18,'passed':True,'log':'.runtime/measurement-review-draft-binding-focused-20261004.log',
            'scope':'Later host14, renderer wrapper, dashboard2 and extension wrapper; three new draft scenarios were added after the0655 full suite began and are not claimed within that run.'},
        'production_check':{'count':16,'passed':True,'path':'research/measurement-review-production-check-20261004.md',
            'sha256':hashlib.sha256((lab.settings.root/'research/measurement-review-production-check-20261004.md').read_bytes()).hexdigest()},
        'model_calls':0,'scope':'Overlapping integration/component/UI checks, not a summed full-suite count or independent labels/experiments. One declared uncertain browser workflow check, no calibration or library promotion.'}
    state['dashboard_state_cache_release']={
        'sources':{p:hashlib.sha256((lab.settings.root/p).read_bytes()).hexdigest() for p in (
            'swarm_lab/state_inventory_cache.py','swarm_lab/server.py')},
        'owner_peer':{'count':24,'passed':True,'log':'.runtime/promoted-state-cache-20261004.log'},
        'public_api':{'count':5,'passed':True,'log':'.runtime/state-inventory-interfaces-20261004.log'},
        'cache_role_integration':{'count':69,'passed':True,'log':'.runtime/state-cache-role-integration-20261004.log'},
        'actual_api_profile':'.runtime/live-state-api-latency-20261004.json',
        'guide':'research/dashboard-state-cache-check-20261004.md',
        'guide_sha256':hashlib.sha256((lab.settings.root/'research/dashboard-state-cache-check-20261004.md').read_bytes()).hexdigest(),
        'model_calls':0,
        'scope':'Overlapping engineering checks. Validated compact inventory only; jobs/usage remain fresh and exact objects uncached. Timings are not a controlled before/after ratio or scientific evidence.'}
    state['study_guide_spectral_release']={
        'sources':{p:hashlib.sha256((lab.settings.root/p).read_bytes()).hexdigest() for p in (
            'web/study-guide.js','web/spectral-signal-view.js','web/app.js',
            'web/episode-workspace.js','web/index.html','web/style.css')},
        'study_routes_components':{'count':27,'passed':True,'log':'.runtime/study-guide-integration-final-20261004.log'},
        'study_independent_initial':{'count':22,'passed':True,'log':'.runtime/study-guide-independent-final-20261004.log'},
        'study_independent_focus':{'count':11,'passed':True,'log':'.runtime/study-guide-independent-focus-final-20261004.log'},
        'spectral_owner_routes':{'count':13,'passed':True,'log':'.runtime/spectral-signal-integration-20261004.log'},
        'spectral_independent':{'count':8,'passed':True,'source':'tests/test_spectral_signal_view_independent.py',
            'note':'Terminal peer18 total includes owner10; exact full-suite scope recorded separately.'},
        'saved_shape_check':{'count':32,'passed':True,'path':'.runtime/spectral-signal-view-production-shapes-revised-20261004.json',
            'scope':'Saved shape/number consistency only, not an independent source or operator authentication.'},
        'model_calls':0,
        'scope':'Overlapping engineering cohorts, not a summed full-suite count. Draft origins are motivation only; navigation supplies no fit approval, registered source, subject input or experiment. Saved signal summaries do not identify agreement/influence/manifold geometry.'}
    state['episode_workspace_release']={
        'backend':{'path':'swarm_lab/episode_workspace.py',
                   'sha256':hashlib.sha256((lab.settings.root/'swarm_lab/episode_workspace.py').read_bytes()).hexdigest()},
        'ui':{'path':'web/episode-workspace.js',
              'sha256':hashlib.sha256((lab.settings.root/'web/episode-workspace.js').read_bytes()).hexdigest()},
        'focused':{'count':27,'passed':True,'log':'.runtime/episode-focused-final-20261004.log'},
        'app_routes_queue':{'count':14,'passed':True,'log':'.runtime/episode-app-integration-20261004.log'},
        'scope':'Overlapping focused cohorts; terminal full-suite count remains separately recorded. Browser check does not reread source/index or rerun a scientific operator.'}
    state['episode_dashboard_input_fix']={
        'count':14,'passed':True,'log':'.runtime/episode-dashboard-input-fix-final-20261004.log',
        'scope':'Original dashboard/extension plus episode route/render checks after replacing the new input handler hasAttribute call with the existing dataset-field convention. The preceding1136-test full run had2 fixture failures; a later full run is still required.'}
    state['relay_adapter_release']={
        'path':'swarm_lab/revision_relay_env.py',
        'sha256':hashlib.sha256((lab.settings.root/'swarm_lab/revision_relay_env.py').read_bytes()).hexdigest(),
        'focused_checks':36,'passed':True,'log':'.runtime/promoted-relay-env-tests-20261004.log',
        'scope':'Adapter/reset/scoped observations/invalid sentinel and independent CPU attacks; promoted adapter is later than the998-test full suite.'}
    state['relay_integration_checks']={
        'promoted_components':{'count':96,'passed':True,'log':'.runtime/promoted-relay-focused-20261004.log'},
        'ui':{'count':9,'passed':True,'log':'.runtime/promoted-relay-ui-20261004.log'},
        'public_reference_queue':{'count':45,'passed':True,'log':'.runtime/relay-public-integration-20261004.log'},
        'scope':'Overlapping focused cohorts, not a summed full-suite count or independent behavioral experiments.'}
    relay_result=lab.store.get('revision_relay_experiment-ce1209221caa',1)
    relay_proof=lab.store.get('verification-8c2cca894899',1)
    state['relay_scripted_study']={
        'result_ref':{key:relay_result[key] for key in ('id','version','hash')},
        'protocol_ref':relay_result['payload']['protocol_ref'],
        'verification_ref':{key:relay_proof[key] for key in ('id','version','hash')},
        'recorded_verification_passed':relay_proof['payload']['passed'],
        'fresh_local_check_count':len(relay_proof['payload']['checks']),
        'status':relay_result['payload']['status'],'teams':8,'seed_blocks':2,'decisions':32,'model_calls':0,
        'analysis':relay_result['payload']['analysis'],
        'report_hash':relay_result['payload']['canonical_execution_report_hash'],
        'artifact_directory':relay_result['payload']['artifact_directory'],
        'independent_production_check':{
            'path':'research/correction-relay-production-check-20261004.md',
            'sha256':hashlib.sha256((lab.settings.root/'research/correction-relay-production-check-20261004.md').read_bytes()).hexdigest(),
            'scope':'Read-only exact registry/archive/source/request/oracle check and fresh pure replay; no database writes, subjects or provider calls.'},
        'report_inventory_note':'Separate saved relay JSON/dashboard study; not silently pooled into the earlier37-live-unit standalone report.'}
    state.setdefault('last_regression_attempt',{'log':'.runtime/full-tests-20261004-0426.log','count':973,'passed':False,
        'failure':'Queue component completion appeared before outer result_ids publication; fixed and independently reviewed with forced-boundary and nested-failure checks.'}
    )
    previous_regression=state.get('current_regression',{})
    state['current_regression']={'log':args.test_log or previous_regression.get('log') or '.runtime/full-tests-20261004-0454.log',
        'status':'completion not supplied in this invocation',
        'started_utc':args.test_started or previous_regression.get('started_utc') or '2026-10-04T04:52:15Z',
        'scope':'Repository regression at this checkpoint; later substantive changes require their own checks.'}
    if args.tests:
        state['current_regression'].update(status='completed',passed=True,count=args.tests,finished_utc=now())
    elif args.regression_running:
        state['current_regression'].update(status='running')
    elif previous_regression.get('log')==state['current_regression']['log'] and previous_regression.get('status') in ('running','completed'):
        state['current_regression']=previous_regression
    regression_path=lab.settings.root/state['current_regression']['log']
    if regression_path.is_file():
        terminal=regression_path.read_text(encoding='utf-8',errors='replace')[-32000:]
        counts=re.findall(r'Ran (\d+) tests in ([0-9.]+)s',terminal)
        endings=re.findall(r'(?m)^(OK|FAILED \([^\r\n]+\))\s*$',terminal)
        if counts and endings:
            count,duration=counts[-1];passed=endings[-1]=='OK'
            if args.tests and (not passed or int(count)!=args.tests):
                parser.error('--tests must match a passing terminal result in --test-log')
            state['current_regression'].update(status='completed' if passed else 'failed',
                passed=passed,count=int(count),duration_seconds=float(duration))
            if not passed:
                state['last_regression_attempt']={
                    'log':state['current_regression']['log'],'count':int(count),'passed':False,
                    'failure':('Repository discovery could not import the staged-path branch of the promoted relay host tests; production-only import fixed and omitted16-check cohort passed. A later full regression is still required.'
                               if state['current_regression']['log']=='.runtime/full-tests-20261004-0530.log'
                               else 'Two legacy Node dashboard fixtures lacked hasAttribute in the new episode input handler; dataset-field handling fixed and14 dashboard/episode checks passed. A later full regression is still required.'
                               if state['current_regression']['log']=='.runtime/full-tests-20261004-0556.log'
                               else 'See the retained terminal regression log; investigate before reporting a passing full suite.')}
        elif args.tests:
            parser.error('Completed tests require a terminal result in --test-log')
    elif args.tests:
        parser.error('Completed tests require an existing terminal test log')
    state['next']=[
        'Inspect active jobs before launching work; never repeat fixed job IDs',
        'Use the saved selected-lead audit and exact source versions; no repeat search or silent rematching',
        'Preserve source/measurement distinctions, ordinary alternatives and every negative/inconclusive result',
        'Inspect cap answer before any work requiring more than400 Responses requests',
        'Keep existing worlds/runners and saved timing source pins frozen; new mechanisms need separate validated versions',
        'Keep saved source-scanner/join/workflow pins frozen; new scan capabilities require a separate version',
        'Source-lineage examples are at other dates; do not attach them as evidence for April graph candidates',
        'Update full test/report/checkpoint after substantive integration',
        'Continue within10-hour window; do not mark goal complete merely because deadline or cap approaches']
    path.write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'updated_utc':state['updated_utc'],'calls':state['budget']['openai_calls'],'active_jobs':len(state['active_jobs'])}))

if __name__=='__main__':main()
