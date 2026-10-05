"""Actual UI/report gates; authored fixtures assert no empirical behavior."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from swarm_lab.guide_reports import render_report
from swarm_lab.store import Store

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('village_ui_fixture',ROOT/'tests/test_lab_workspace_ui.py')
FIXTURE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(FIXTURE)

def village_payload():
    source={'id':'dataset-village-fixture','version':2,'hash':'a'*64}
    fidelity={'represented':['Per-agent document access and canonical reference repair'], 'approximated':['Local tool state rather than cloud account services'], 'omitted':['Original hidden account history'], 'historical_equivalence':False}
    hypothesis={'statement':'Does a canonical access check reduce avoidable recreation?', 'source_evidence_ids':['post-fixture']}
    return {'agent_mode':'live','status':'complete','source_refs':{'dataset_ref':source},'hypothesis':hypothesis,'fidelity':fidelity,
        'protocol':{'environment':{'kind':'village_document_access_repair'},'grounding':{'source_ref':source,'evidence_ids':['post-fixture']},'hypothesis':hypothesis,'fidelity':fidelity},
        'runs':[{'run_id':'team-1','arm':'neutral_note','outcomes':{'verified_usable_project':0,'avoidable_recreations':2}}, {'run_id':'team-2','arm':'canonical_check','outcomes':{'verified_usable_project':1,'avoidable_recreations':0}}],
        'analysis':{'arms':{'neutral_note':{'n':1,'success':0},'canonical_check':{'n':1,'success':1}},'primary_effect':{'difference':1,'ci95':[0,1],'interval_method':'Authored test interval'}}}

JS=r"""
function village(){const source=clone(refs.source),hypothesis={statement:'Does canonical access checking reduce recreation?',source_evidence_ids:['post-unit']},fidelity={represented:['Per-agent access and reference repair'],approximated:['Local account state'],omitted:['Historical hidden account state'],historical_equivalence:false};return {id:'village-access-ui',version:1,hash:'9'.repeat(64),kind:'village_access_experiment',created:'2026-10-05T00:00:00Z',summary:{agent_mode:'live'},payload:{agent_mode:'live',status:'complete',source_refs:{dataset_ref:source},hypothesis,fidelity,protocol:{environment:{kind:'village_document_access_repair'},grounding:{source_ref:source,evidence_ids:['post-unit']},hypothesis:clone(hypothesis),fidelity:clone(fidelity)},runs:[{run_id:'team-a',arm:'neutral_note',outcomes:{verified_usable_project:0,avoidable_recreations:1}},{run_id:'team-b',arm:'canonical_check',outcomes:{verified_usable_project:1,avoidable_recreations:0}}],analysis:{arms:{neutral_note:{n:1},canonical_check:{n:1}},primary_effect:{difference:1,ci95:[0,1],interval_method:'Authored unit fixture'}}}};}
function add(env,r){env.records.push(clone(r));env.b.app.state.objects.push(clone(r));}
"""

class VillageProductGateTests(unittest.TestCase):
    def node(self,script):
        result=subprocess.run(['node','-e',FIXTURE.NODE,str(ROOT)],input=json.dumps({'script':JS+script}),text=True,encoding='utf-8',capture_output=True,timeout=30,cwd=ROOT)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_per_document_progress_preserves_unknown_and_source_privacy(self):
        self.node(r"""
const r=village();r.payload.runs[0].outcomes.per_document=Array.from({length:4},(_,i)=>({document_key:i===0?'<script>attack</script>':'document-'+i,content_correct:true,checker_current_profile_authorized:i<3,checker_opened_current_version:false}));
let html=SocietyExperience.documentProgress(r);assert(html.includes('4 / 4'));assert(html.includes('3 / 4'));assert(html.includes('0 / 4'));assert(html.includes('&lt;script&gt;'));assert(!html.includes('<script>'));assert(html.includes('Unknown'));
r.payload.runs[0].outcomes.per_document[1].checker_opened_current_version=null;html=SocietyExperience.documentProgress(r);assert(html.includes('Unknown'));
assert(!html.includes('required_content'));assert(!html.includes('private_context'));assert(!html.includes('data-action'));
""")

    def test_no_default_or_restored_legacy_result_is_presented_for_current_source(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();const fresh=village();add(env,fresh);
let html=await env.experience.render('findings');assert(html.includes('No experiment is selected'));assert(!html.includes('exp-result-chart'));
const before=JSON.stringify(env.experience.state.draft);
await assert.rejects(env.experience.openSavedArtifact(env.records.find(r=>r.id===refs.result.id&&r.version===1)));
assert.equal(env.log.opens.length,0);assert.equal(env.log.jobs.length,0);assert.equal(JSON.stringify(env.experience.state.draft),before);
env.experience.state.study=clone(refs.result);html=await env.experience.render('findings');assert(html.includes('unavailable'));assert(!html.includes('exp-result-chart'));
""")

    def test_village_result_has_access_outcome_source_and_fidelity_not_publication_metrics(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();const r=village();add(env,r);env.experience.state.study=pin(r);
const before=JSON.stringify(env.experience.state.draft),html=await env.experience.render('findings');
for(const phrase of ['verified usable project','avoidable recreations','dataset-current','post-unit','Per-agent access','Local account state','Historical hidden account state'])assert(html.includes(phrase),phrase);
assert(!html.includes('delivery list'));assert(!html.includes('published version'));assert(!html.includes('File-check reminder'));
assert(html.includes('historical explanation'));assert.equal(JSON.stringify(env.experience.state.draft),before);
r.payload.runs[0].outcomes.verified_usable_project=null;env.records[env.records.length-1]=clone(r);const unknown=await env.experience.render('findings');assert(unknown.includes('Unknown'));
""")

    def test_mismatched_or_absent_contract_is_withheld_and_markup_escaped(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();const r=village();
assert(SocietyExperience.validVillageStudy(r));
for(const mutate of [p=>p.source_refs.dataset_ref.version=true,p=>p.protocol.grounding.source_ref.hash='c'.repeat(64),p=>delete p.hypothesis,p=>p.fidelity.historical_equivalence=true,p=>p.protocol.fidelity.represented=['Another mechanism']]){const bad=clone(r);mutate(bad.payload);assert(!SocietyExperience.validVillageStudy(bad));await assert.rejects(env.experience.openSavedArtifact(bad));}
r.payload.hypothesis.statement=r.payload.protocol.hypothesis.statement='<img src=x onerror=attack()> question';add(env,r);env.experience.state.study=pin(r);const html=await env.experience.render('findings');assert(html.includes('&lt;img'));assert(!html.includes('<img src=x'));
""")

    def test_access_study_uses_dynamic_replay_and_keeps_current_draft(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();const r=village();
r.payload.protocol.environment.agents=['coordinator','auditor'];
for(const run of r.payload.runs)run.turns=[
 {step:0,agent_id:'coordinator',action:{action:'open_url',url:'https://local.example/doc'},tool_result:{ok:false,status_code:404},request:{private:'UNSHOWN_PRIVATE_REQUEST'}},
 {step:1,agent_id:'auditor',action:{action:'inspect_document'},tool_result:{ok:true,document_id:'original-doc',version:2},request:{private:'UNSHOWN_PRIVATE_REQUEST'}}];
add(env,r);const before=JSON.stringify(env.experience.state.draft);
const model=SocietyReplay.normalize(r,0);assert(model.available);assert.equal(model.mode,'study');
assert.equal(model.outcomes.success,0);assert.equal(model.events[0].action,'open_url');assert.equal(model.events[0].ok,false);
await env.experience.openSavedArtifact(r,'replay');const html=await env.experience.render('watch');
assert(html.includes('experience-replay'));assert(html.includes('sr-root'));assert(html.includes('Document project'));
assert(!html.includes('UNSHOWN_PRIVATE_REQUEST'));assert(!html.includes('publish_artifact'));
assert.equal(JSON.stringify(env.experience.state.draft),before);assert.equal(env.log.jobs.length,0);
const context=env.experience.assistantContext();assert.deepEqual(context.result_ref,pin(r));assert(!context.dataset_ref);
""")

    def test_new_finite_replay_schema_is_exact_linked_and_not_ai_evaluation(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();const r=village();
for(const run of r.payload.runs){run.status='complete';run.turns=[{step:0,agent_id:'coordinator',action:{action:'wait'},tool_result:{ok:true}}];}
const proof={id:'verification-village-unit',version:1,hash:'6'.repeat(64),kind:'verification',payload:{status:'passed',analysis_recomputed:true,paid_calls:0,experiment_ref:pin(r),checks:r.payload.runs.map(run=>({run_id:run.run_id,steps:1,passed:true}))}};
const claims={id:'claim-audit-village-unit',version:1,hash:'7'.repeat(64),kind:'claim_audit',payload:{status:'passed',paid_calls:0,experiment_ref:pin(r),facts:{team_count:2,subject_decisions:2,arm_counts:{neutral_note:1,canonical_check:1},primary_effect:clone(r.payload.analysis.primary_effect)}}};
assert(SocietyExperience.villageChecks(r,proof,claims));
for(const mutate of [p=>p.experiment_ref.hash='1'.repeat(64),p=>p.facts.subject_decisions=0,p=>p.facts.arm_counts.neutral_note=2,p=>p.facts.primary_effect.difference=0]){const bad=clone(claims);mutate(bad.payload);assert(!SocietyExperience.villageChecks(r,proof,bad));}
for(const mutate of [p=>p.status='running',p=>p.analysis_recomputed=false,p=>p.checks[0].steps=2,p=>p.checks[1].run_id=p.checks[0].run_id]){const bad=clone(proof);mutate(bad.payload);assert(!SocietyExperience.villageChecks(r,bad,claims));}
const execution={id:'guided-result-village-unit',version:1,hash:'8'.repeat(64),kind:'guided_result',payload:{result_ref:pin(r),verification_ref:pin(proof),claims_ref:pin(claims)}};
for(const record of [r,proof,claims,execution])add(env,record);
env.experience.state.study=pin(r);env.experience.state.viewedExecutionRef=pin(execution);
const html=await env.experience.render('findings');assert(html.includes('Replay and outcome checks passed.'));
assert(html.includes('deterministic counts'));assert(!html.includes('A real AI evaluator then'));
assert(html.includes('matched whole-team difference'));assert.equal(env.log.jobs.length,0);
""")

    def test_catalog_and_mention_search_exclude_legacy_results(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();const r=village(),items=[{ref:clone(refs.result),kind:'experiment',title:'Unrelated hidden test',summary:'legacy',origin:{chat_id:'chat-b'}},{ref:pin(r),kind:r.kind,title:'Village access result',summary:'source-grounded',origin:{chat_id:'chat-a'}},{ref:clone(refs.source),kind:'dataset',title:'Village source',summary:'observations',origin:{chat_id:'chat-a'}}];
env.b.handle=request=>request.path.startsWith('/api/workspaces/artifacts?')?{artifacts:clone(items),edges:[],total:3,truncated:false}:undefined;
let html=await env.workspace.render('experiments');assert(html.includes('Village access result'));assert(!html.includes('Unrelated hidden test'));assert(!html.includes('Village source'));
html=await env.workspace.render('artifacts');assert(!html.includes('Unrelated hidden test'));
assert.equal(env.log.jobs.length,0);
""")

    def test_new_plan_world_route_preserves_question_and_shows_omitted_state(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();const r=village(),plan=env.records.find(r=>r.id===refs.plan.id);plan.payload={family:'village_document_access_repair',question:'Source-linked access question',control_text:'Neutral',treatment_text:'Check canonical access',source_refs:r.payload.source_refs,hypothesis:r.payload.hypothesis,fidelity:r.payload.fidelity};
const before=JSON.stringify(env.experience.state.draft);await env.experience.openSavedArtifact(clone(plan));
const html=await env.experience.render('plan');assert(html.includes('source-grounded access plan'));assert(html.includes('Historical hidden account state'));assert(!html.includes('Delivery list'));assert.equal(JSON.stringify(env.experience.state.draft),before);
env.experience.state.savedStage=null;env.experience.state.planRef=null;const empty=await env.experience.render('plan');assert(empty.includes('No simulator is automatically selected'));assert(!empty.includes('data-journey-artifact-choice'));assert(!empty.includes('data-journey-plan'));
""")

    def test_legacy_build_click_is_blocked_before_subject_or_builder_api(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();env.experience.state.planRef=clone(refs.plan);
await assert.rejects(env.experience.click(target({'data-journey-build':''})));
assert(!env.log.requests.some(r=>r.path==='/api/guided/simulator'));assert.equal(env.log.jobs.length,0);
""")

    def test_observational_report_does_not_autoembed_an_unrelated_cited_result(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();const r=village();add(env,r);
env.workspace.state.chat.messages.push({id:'mixed-message',role:'assistant',content:'Observed pattern',metadata:{guide_result:{sources:[{object_ref:clone(refs.result)},{object_ref:pin(r)},{object_ref:clone(refs.source)}]}}});
await env.workspace.render('workspace');let embeds=env.workspace.state.reportEmbeds.get('mixed-message');assert.equal(embeds.length,1);assert.deepEqual(embeds[0].source_ref,refs.source);assert(embeds[0].title.includes('observational'));assert(embeds[0].scope.includes('not an experiment'));
env.workspace.state.chat.messages.push({id:'explicit-result',role:'assistant',content:'The exact executed Village result',metadata:{guide_result:{updated_context:{result_ref:pin(r)},sources:[{object_ref:clone(refs.source)}]}}});
await env.workspace.render('workspace');embeds=env.workspace.state.reportEmbeds.get('explicit-result');assert.equal(embeds.length,1);assert.deepEqual(embeds[0].source_ref,pin(r));assert(embeds[0].scope.includes('fidelity contract'));
assert.equal(env.log.jobs.length,0);
""")

    def test_new_empty_workspace_does_not_migrate_stale_browser_result_context(self):
        self.node(r"""
const env=setup();env.snapshots['chat-a'].state={};env.experience.state.study=clone(refs.result);env.experience.state.planRef=clone(refs.plan);
await env.workspace.initialize();assert.equal(env.experience.state.study,null);assert.equal(env.experience.state.planRef,null);
assert(!env.log.requests.some(r=>r.body?.op==='save_state'));
""")

    def test_reports_reject_independent_results_and_bind_new_source_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'lab.sqlite3')
            for kind in ('experiment','network_experiment','resource_experiment','revision_relay_experiment'):
                r=store.put(kind,{'analysis':{}})
                with self.assertRaises(ValueError):render_report(store,{k:r[k] for k in ('id','version','hash')})
            r=store.put('village_access_experiment',village_payload());ref={k:r[k] for k in ('id','version','hash')}
            html=render_report(store,ref)
            for text in ('Verified usable project','Canonical project check','post-fixture','Per-agent document access','Original hidden account history','Historical equivalence is unestablished'):self.assertIn(text,html)
            self.assertNotIn('delivery list',html)
            bad=village_payload();bad['protocol']['grounding']['source_ref']=dict(bad['source_refs']['dataset_ref'],hash='b'*64)
            r=store.put('village_access_experiment',bad)
            with self.assertRaises(ValueError):render_report(store,{k:r[k] for k in ('id','version','hash')})
            dataset=store.put('dataset',{'messages':[{'id':'message','content':'Observed'}]})
            self.assertIn('Observational analytics',render_report(store,{k:dataset[k] for k in ('id','version','hash')}))
