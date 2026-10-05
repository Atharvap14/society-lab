"""Execute the first-use renderer with source/API fixtures, without a browser."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which('node')
PRELUDE = r'''
const assert=require('assert');
const api=require('./web/society-experience.js');
const replayPackets=[],requests=[],actions=[];
global.SocietyReplay={render(packet){replayPackets.push(packet);return '<div class="mock-replay">Saved source replay</div>';}};
global.document={getElementById(){return {focus(){},classList:{add(){},remove(){}}};}};
global.window={scrollTo(){}};
function record(kind='experiment',mode='offline_simulation') {
 const rows=[];for(const [arm,scores] of Object.entries({baseline:[1,1],placebo:[0,0],evidence_thought:[1,1]}))for(const score of scores)rows.push({arm,outcomes:{success:score}});
 const analysis={arms:{baseline:{n:2},placebo:{n:2},evidence_thought:{n:2}},primary_effect:{ci95:[.1,1],confirmatory_primary:true}};
 const payload={agent_mode:mode,status:'complete',runs:rows,analysis};
 return {id:kind+'-fixture',version:1,hash:'a'.repeat(64),kind,created:'2026-10-05T00:00:00Z',summary:{agent_mode:mode,messages:2},payload};
}
function dataset(identity='dataset-fixture') {
 const payload={messages:[{id:'m-1',agent_id:'a',agent_name:'Alice',speaker_type:'agent',room_id:'team',timestamp:'2025-04-02T10:00:00Z',content:'A source message.'}],provenance:{origin:'user_import'},source:'/local/import/chat_messages.jsonl'};
 return {id:identity,version:2,hash:'c'.repeat(64),kind:'dataset',created:'2026-10-05T00:00:00Z',summary:{messages:1},payload};
}
function bridge(records) {
 const app={view:'watch',state:{objects:records,jobs:[],csrf:'fixture'}};
 return {app,all:kind=>records.filter(row=>row.kind===kind),
   object:async(id,version)=>{requests.push({id,version});const row=records.find(x=>x.id===id && x.version===version);if(!row)throw new Error('Missing exact saved source');return row;},
   api:async()=>{throw new Error('Rendering must not call an endpoint')},submit:async()=>{throw new Error('Rendering must not submit a job')},
   toast(){},render:async()=>{},refresh:async()=>{},openObject:async(...args)=>actions.push(args)};
}
const run=async(fn)=>{await fn();assert.equal(actions.length,0);};
'''


@unittest.skipUnless(NODE, 'Node is required for executable first-use UI tests')
class SocietyExperienceUITests(unittest.TestCase):
    def run_js(self, body):
        result = subprocess.run([NODE, '-e', PRELUDE + '\nrun(async()=>{' + body + '\n}).catch(error=>{console.error(error.stack);process.exitCode=1;});'],
                                cwd=ROOT, text=True, encoding='utf-8', capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_arm_counts_come_from_binary_team_outcomes(self):
        self.run_js(r'''
const r=record(),facts=api.armFacts(r);assert.deepEqual(facts.map(x=>[x.key,x.correct,x.n]),[['baseline',2,2],['placebo',0,2],['evidence_thought',2,2]]);
r.payload.runs.push({arm:'unregistered',outcomes:{success:1}});assert.equal(api.armFacts(r)[2].correct,2);
assert.equal(requests.length,0);
''')

    def test_unknown_or_wrongly_typed_scores_never_become_zero(self):
        self.run_js(r'''
for(const missing of [null,undefined,true,'1',NaN]){
 const r=record();r.payload.runs.find(x=>x.arm==='placebo').outcomes.success=missing;const fact=api.armFacts(r).find(x=>x.key==='placebo');assert.equal(fact.correct,null);assert.equal(fact.n,2);
}
const r=record();r.payload.analysis.arms.baseline.n=3;assert.equal(api.armFacts(r)[0].correct,null);
assert.deepEqual(api.armFacts({payload:{}}),[]);
''')

    def test_scripted_positive_interval_does_not_claim_a_live_reminder_effect(self):
        self.run_js(r'''
const r=record(),xp=api.create(bridge([r])),html=await xp.render('findings');assert.match(html,/Your first result will appear/);assert.doesNotMatch(html,/The reminder helped compared with this neutral note|exp-result-chart/);assert.equal(requests.length,0);
const live=record('experiment','live');live.id='experiment-live';const mixed=await api.create(bridge([r,live])).render('findings');assert.match(mixed,/experiment-live/);assert.doesNotMatch(mixed,/experiment-fixture/);
''')

    def test_live_complete_contrast_retains_narrow_comparison_and_unknown_generalization(self):
        self.run_js(r'''
const r=record('experiment','live'),html=await api.create(bridge([r])).render('findings');assert.match(html,/The reminder helped compared with this neutral note/);assert.match(html,/no-note group is a separate exploratory comparison|comparison with no added note remains uncertain/);assert.match(html,/not shown that checking more often explains/);assert.match(html,/does not explain why the April 22 team/);assert.match(html,/One separate study/);
''')

    def test_incomplete_or_unknown_counts_do_not_support_a_benefit_headline(self):
        self.run_js(r'''
for(const altered of ['incomplete','missing_score']){
 const r=record('experiment','live');if(altered==='incomplete')r.payload.status='incomplete';else delete r.payload.runs[2].outcomes.success;
 const html=await api.create(bridge([r])).render('findings');assert.doesNotMatch(html,/The reminder helped compared with this neutral note/);if(altered==='missing_score')assert.match(html,/Unknown/);
}
''')

    def test_resource_cells_are_not_presented_as_network_topologies(self):
        self.run_js(r'''
const r=record('resource_experiment','live');delete r.payload.analysis.arms;r.payload.analysis.cells={early:{release_round:0,context:'placebo',mean_accuracy:1,n_networks:2},late:{release_round:2,context:'source_thought',mean_accuracy:0,n_networks:2}};
const html=await api.create(bridge([r])).render('findings');assert.match(html,/Share a computer/);assert.doesNotMatch(html,/Everyone connected|Neighbors only|exp-cell-chart/);assert.match(html,/Open the saved report for the outcome counts/);
''')

    def test_valid_star_and_baseline_conditions_are_not_renamed_complete_and_neutral(self):
        self.run_js(r'''
const r=record('network_experiment','live');delete r.payload.analysis.arms;r.payload.analysis.cells={only:{topology:'star',context:'baseline',mean_accuracy:.5,n_networks:2}};
const html=await api.create(bridge([r])).render('findings');assert.doesNotMatch(html,/Everyone connected.*Neutral note/);assert.match(html,/No added note|No note/);assert.match(html,/Star|Hub|hub|One central agent/);
''')

    def test_watch_reads_the_selected_exact_version_and_escapes_source_labels(self):
        self.run_js(r'''
const r=dataset();r.payload.provenance.original_name='<img src=x onerror=alert(1)>';const newer={...r,version:3,hash:'d'.repeat(64)};const xp=api.create(bridge([newer,r]));xp.state.project={id:r.id,version:r.version,hash:r.hash};xp.state.window='all';
const html=await xp.render('watch');assert.deepEqual(requests,[{id:r.id,version:2}]);assert.equal(xp.state.record.version,2);assert.equal(replayPackets[0].record.version,2);assert.match(html,/&lt;img/);assert.doesNotMatch(html,/<img src=x/);assert.match(html,/Saved version 2/);
''')

    def test_wrong_hash_or_kind_cannot_open_watch_under_a_matching_identity(self):
        self.run_js(r'''
for(const defect of ['hash','kind','version']){
 const r=dataset(),xp=api.create(bridge([r]));xp.state.project={id:r.id,version:r.version,hash:r.hash};
 if(defect==='hash')xp.state.project.hash='f'.repeat(64);if(defect==='kind')r.kind='experiment';if(defect==='version')xp.state.project.version=1;
 await assert.rejects(()=>xp.render('watch'),/unavailable|Missing exact/);assert.equal(xp.state.record,null);
}
assert.equal(replayPackets.length,0);
''')

    def test_missing_project_offers_explicit_choice_without_fabricated_replay(self):
        self.run_js(r'''
const xp=api.create(bridge([])),html=await xp.render('watch');assert.match(html,/Connect your first team/);assert.match(html,/Connect agents/);assert.equal(requests.length,0);assert.equal(replayPackets.length,0);
const fallback=dataset(),second=api.create(bridge([fallback]));second.state.project={id:'dataset-missing',version:1,hash:'f'.repeat(64)};await assert.rejects(()=>second.render('watch'),/Missing exact/);assert.equal(second.state.project.id,'dataset-missing');assert.equal(replayPackets.length,0);
''')

    def test_saved_demo_window_excludes_boundary_other_room_and_other_time(self):
        self.run_js(r'''
const r={...dataset(),...api.DEMO};r.payload.messages=[
 {id:'inside',timestamp:'2025-04-22T18:05:00Z',room_id:'18a3b2fb-9d2e-4ce7-b9b1-52e09c5408a8'},
 {id:'boundary',timestamp:'2025-04-22T19:00:00Z',room_id:'18a3b2fb-9d2e-4ce7-b9b1-52e09c5408a8'},
 {id:'other-room',timestamp:'2025-04-22T18:05:00Z',room_id:'different-room'},
 {id:'earlier',timestamp:'2025-04-22T17:59:59Z',room_id:'18a3b2fb-9d2e-4ce7-b9b1-52e09c5408a8'}];
const html=await api.create(bridge([r])).render('watch');assert.deepEqual(replayPackets[0].record.payload.messages.map(x=>x.id),['inside']);assert.equal(r.payload.messages.length,4);assert.match(html,/1 messages/);
''')

    def test_import_flow_has_labels_local_storage_and_explicit_guide_scope(self):
        self.run_js(r'''
const html=await api.create(bridge([])).render('import');assert.match(html,/id="exp-chat-file"/);assert.match(html,/for="exp-chat-file"/);assert.match(html,/Paste messages instead/);assert.match(html,/configured OpenAI model for automatic AI discovery/);assert.match(html,/Connect your harness/);assert.equal(requests.length,0);
''')

    def test_message_count_alone_cannot_label_a_real_chat_authored(self):
        self.run_js(r'''
const r=dataset();r.summary.messages=8;r.payload.messages=Array.from({length:8},(_,i)=>({...r.payload.messages[0],id:'m'+i}));const xp=api.create(bridge([r]));xp.state.project={id:r.id,version:r.version,hash:r.hash};xp.state.window='all';const html=await xp.render('watch');assert.match(html,/Imported chat/);assert.doesNotMatch(html,/Authored practice chat|Authored example/);
''')


if __name__ == '__main__':
    unittest.main()
