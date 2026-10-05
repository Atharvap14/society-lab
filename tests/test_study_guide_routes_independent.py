"""Exercise real host handlers/renderers with inert authored episode origins.

Only DOM/platform primitives are simulated. Registration handlers, rendering,
forms and route selection are the production JavaScript; any fetch is forbidden.
This is a client presentation check, not protocol execution or source rereading.
"""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from tests.test_episode_workspace_ui import fixture

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which('node')
PRELUDE = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const f=JSON.parse(fs.readFileSync(0,'utf8')),nodes=new Map(),listeners={},requests=[],scrolls=[];
const guideControls=['handoff','network','complementary','resource','timed_resource','revision_relay','guide']
 .map(id=>({dataset:{studyGuideOpen:id},disabled:false}));
function node(id){if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',open:false,
 classList:{toggle(){},remove(){}},addEventListener(){},scrollIntoView(){scrolls.push(id)},
 focus(){},close(){this.open=false},contains(){return false},querySelector(){return null}});return nodes.get(id)}
const c={console,Map,Set,Date,JSON,Math,Number,String,Array,Object,Promise,URLSearchParams,
 CSS:{escape:x=>x},setTimeout:()=>0,clearTimeout(){},setInterval:()=>0,
 document:{getElementById:node,querySelector:node,
 querySelectorAll:selector=>selector==='[data-study-guide-open]'?guideControls:[],activeElement:null,
 addEventListener:(name,fn)=>{const old=listeners[name];listeners[name]=old?async e=>{await old(e);await fn(e)}:fn}},
 fetch:async(path,options)=>{requests.push({path,options});throw Error('No fetch authorized by draft navigation')}};
vm.createContext(c);
for(const path of ['web/episode-workspace.js','web/study-guide.js','web/revision-relay.js'])
 vm.runInContext(fs.readFileSync(path,'utf8'),c,{filename:path});
const source=fs.readFileSync('web/app.js','utf8');
vm.runInContext(source.slice(0,source.lastIndexOf('\nrefresh(true);')),c,{filename:'web/app.js'});
const run=s=>vm.runInContext(s,c);
c.fixture=f;
run(`app.state={objects:[{id:'behavior-separate-selection',kind:'behavior',version:9,hash:'c'.repeat(64),
 summary:{name:'Independently selected hypothesis'}}],jobs:[],usage:{calls:400},max_calls:400,
 model:'unchanged-model',supported_actions:['design_revision_relay']};
 app.view='episode';app.episodePacket=fixture.packet;app.episodeExpected=fixture.expected;
 app.episodeQuestion='Which route-versus-dependency explanation can be falsified?';
 app.selected.behavior='behavior-separate-selection';app.live=true;app.harness='codex';
 app.trials=7;app.seed=902;app.rounds=8;app.networkTrials=3;app.networkSeed=903;
 app.resourceReleases='2,4';app.timedResamples=300;app.relayBlocks=3;app.relaySeed=907;
 app.authoringQuestion='An independent authoring draft';app.authoringBehavior='separate-selection';`);
const button=dataset=>({dataset,closest(){return this},hasAttribute(){return false}});
const click=dataset=>listeners.click({target:button(dataset)});
const settings=()=>run(`JSON.stringify({live:app.live,harness:app.harness,behavior:app.selected.behavior,
 trials:app.trials,seed:app.seed,rounds:app.rounds,networkTrials:app.networkTrials,
 networkSeed:app.networkSeed,resourceReleases:app.resourceReleases,timedResamples:app.timedResamples,
 relayBlocks:app.relayBlocks,relaySeed:app.relaySeed,authoringQuestion:app.authoringQuestion,
 authoringBehavior:app.authoringBehavior})`);
const finish=()=>assert.equal(requests.length,0);
'''


@unittest.skipUnless(NODE, 'Node required for real host rendering tests')
class StudyGuideRoutesIndependentTests(unittest.TestCase):
    def run_js(self, assertions, *, projection=None):
        payload = fixture()
        if projection is not None:
            payload['focus_projection'] = projection
        result = subprocess.run([NODE, '-e', PRELUDE + assertions],
                                input=json.dumps(payload), cwd=ROOT, text=True,
                                capture_output=True, timeout=25)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_real_six_forms_render_without_changing_execution_or_binding_origin(self):
        self.run_js(r'''
(async()=>{
const before=settings();await click({episodeStudyGuide:''});
assert(node('main').innerHTML.includes('Choose a falsifiable study'));
const draft=JSON.stringify(run('app.studyGuideDraft'));
const routes={handoff:'design-form',network:'network-design-form',
 complementary:'complementary-design-form',resource:'resource-design-form',
 timed_resource:'timed-resource-design-form',revision_relay:'revision-relay-design-form'};
for(const [study,form] of Object.entries(routes)){
 await click({studyGuideOpen:study});const html=node('main').innerHTML;
 assert.equal(run('app.experimentStudy'),study);assert(html.includes('id="'+form+'"'),study);
 assert(html.includes('Retained local question'));assert(html.includes('dataset-original'));
 assert(html.includes('supplies no registered source'));assert(html.includes('fit is unreviewed'));
 assert.equal(scrolls.at(-1),form);assert.equal(settings(),before);
 assert.equal(JSON.stringify(run('app.studyGuideDraft')),draft);
 assert.equal(run('app.selected.behavior'),'behavior-separate-selection');}
finish();
})().catch(e=>{console.error(e.stack);process.exitCode=1});
''')

    def test_real_empty_question_route_is_local_invalid_and_later_edit_retains_exact_origin(self):
        self.run_js(r'''
(async()=>{
await click({episodeStudyGuide:''});const before=settings(),pins=JSON.stringify(run('app.studyGuideDraft.source_refs'));
await listeners.input({target:{dataset:{studyGuideQuestion:''},value:''}});
await click({studyGuideOpen:'revision_relay'});
assert.equal(run('app.experimentStudy'),'guide');assert.equal(run('app.studyGuideDraft.research_question'),'');
await run('render()');assert(node('main').innerHTML.includes('data-study-guide-open="revision_relay" disabled'));
await listeners.input({target:{dataset:{studyGuideQuestion:''},value:'Could fixed readiness explain the contrast?'}});
await click({studyGuideOpen:'revision_relay'});
assert.equal(run('app.experimentStudy'),'revision_relay');assert(node('main').innerHTML.includes('id="revision-relay-design-form"'));
assert(node('main').innerHTML.includes('Could fixed readiness explain the contrast?'));
assert.equal(JSON.stringify(run('app.studyGuideDraft.source_refs')),pins);assert.equal(settings(),before);finish();
})().catch(e=>{console.error(e.stack);process.exitCode=1});
''')

    def test_real_invalid_new_episode_cannot_replace_retained_origin_or_launch_fallback(self):
        self.run_js(r'''
(async()=>{
await click({episodeStudyGuide:''});const saved=JSON.stringify(run('app.studyGuideDraft')),before=settings();
run("app.view='episode';app.episodePacket.source_refs.discovery.hash='f'.repeat(64)");
await click({episodeStudyGuide:''});assert.equal(run('app.view'),'episode');
assert.equal(JSON.stringify(run('app.studyGuideDraft')),saved);
run("app.view='experiments';app.experimentStudy='guide'");
for(const study of ['authoring','cycle','__proto__','experiment_revision_relay','']){
 await click({studyGuideOpen:study});assert.equal(run('app.experimentStudy'),'guide');
 assert.equal(JSON.stringify(run('app.studyGuideDraft')),saved);}
await click({studyGuideClear:''});assert.strictEqual(run('app.studyGuideDraft'),null);
assert(node('main').innerHTML.includes('Open an exact case in Episode workspace'));
assert.equal(settings(),before);finish();
})().catch(e=>{console.error(e.stack);process.exitCode=1});
''')

    def test_live_question_validity_disables_and_recovers_choices_without_rerender_or_pin_changes(self):
        self.run_js(r'''
(async()=>{
await click({episodeStudyGuide:''});const before=settings(),html=node('main').innerHTML;
const pins=JSON.stringify(run('app.studyGuideDraft.source_refs'));
const pair=JSON.stringify(run('app.studyGuideDraft.comparison'));
await listeners.input({target:{dataset:{studyGuideQuestion:''},value:'   '}});
assert.equal(run('app.studyGuideDraft.research_question'),'   ');
assert(guideControls.filter(x=>x.dataset.studyGuideOpen!=='guide').every(x=>x.disabled===true));
assert.equal(guideControls.find(x=>x.dataset.studyGuideOpen==='guide').disabled,false);
assert.equal(node('main').innerHTML,html);
await listeners.input({target:{dataset:{studyGuideQuestion:''},value:'A changed, still unregistered question?'}});
assert(guideControls.every(x=>x.disabled===false));assert.equal(node('main').innerHTML,html);
assert.equal(JSON.stringify(run('app.studyGuideDraft.source_refs')),pins);
assert.equal(JSON.stringify(run('app.studyGuideDraft.comparison')),pair);
assert.equal(settings(),before);assert.equal(run('app.studyGuideDraft.registration_status'),'unregistered_local_draft');
finish();
})().catch(e=>{console.error(e.stack);process.exitCode=1});
''')

    def test_real_guide_rerender_restores_new_textarea_focus_and_exact_caret_without_mutating_draft(self):
        self.run_js(r'''
(async()=>{
await click({episodeStudyGuide:''});
const text='Which observed correction timing and rival readiness explanation could be falsified?';
const old={dataset:{studyGuideQuestion:''},value:text,selectionStart:15,selectionEnd:29};
await listeners.input({target:old});const saved=JSON.stringify(run('app.studyGuideDraft')),before=settings();
const queries=[],focusCalls=[],ranges=[];
const replacement={focus(options){focusCalls.push(options);c.document.activeElement=this},
 setSelectionRange(a,b){ranges.push([a,b])}};
c.document.activeElement=old;node('main').contains=value=>value===old;
node('main').querySelector=selector=>{queries.push(selector);return selector==='[data-study-guide-question]'?replacement:null};
await run('render()');
assert(node('main').innerHTML.includes(text));assert.deepEqual(queries,['[data-study-guide-question]']);
assert.deepEqual(JSON.parse(JSON.stringify(focusCalls)),[{preventScroll:true}]);
assert.deepEqual(ranges,[[15,29]]);assert.strictEqual(c.document.activeElement,replacement);
assert.equal(JSON.stringify(run('app.studyGuideDraft')),saved);assert.equal(settings(),before);finish();
})().catch(e=>{console.error(e.stack);process.exitCode=1});
''')

    def test_real_observatory_select_rerender_restores_focus_without_textarea_caret_operation(self):
        from tests.test_spectral_signal_view import fixture as spectral_fixture

        self.run_js(r'''
(async()=>{
vm.runInContext(fs.readFileSync('web/spectral-signal-view.js','utf8'),c,{filename:'web/spectral-signal-view.js'});
const projection=f.focus_projection;
for(const edge of projection.edges)edge.evidence_ids=[];
projection.metrics={graph:{},nodes:[]};c.projection=projection;
run(`const dataset={id:'dataset-focus',kind:'dataset',version:1,hash:'d'.repeat(64),payload:{
 messages:[],agents:[],goals:[],source:'Authored focus fixture',scope:{},diagnostics:{chat:{}}}};
 const discovery={id:'discovery-focus',kind:'discovery',version:1,hash:'e'.repeat(64),payload:{
 dataset_id:dataset.id,dataset_ref:{id:dataset.id,version:1,hash:dataset.hash},candidates:[],signals:[],
 network:{projections:{observed_mentions:projection}}}};
 app.state.objects.push({...dataset,summary:{name:'Authored dataset'}},{...discovery,summary:{dataset_id:dataset.id,name:'Authored discovery'}});
 app.cache.set(dataset.id+'@1',dataset);app.cache.set(discovery.id,discovery);
 app.view='observatory';app.selected.dataset=dataset.id;app.selected.discovery=discovery.id;
 app.projection='observed_mentions';app.spectralSignal='completion_report';`);
await run('render()');assert(node('main').innerHTML.includes('data-spectral-signal'));
const before=settings(),old={dataset:{spectralSignal:''},value:'correction'},queries=[],focusCalls=[];
const replacement={focus(options){focusCalls.push(options);c.document.activeElement=this},
 setSelectionRange(){throw Error('Select has no text-selection operation')}};
c.document.activeElement=old;node('main').contains=value=>value===old;
node('main').querySelector=selector=>{queries.push(selector);return selector==='[data-spectral-signal]'?replacement:null};
await listeners.change({target:old});
assert(node('main').innerHTML.includes('data-spectral-signal'));assert.equal(run('app.spectralSignal'),'correction');
assert.deepEqual(queries,['[data-spectral-signal]']);
assert.deepEqual(JSON.parse(JSON.stringify(focusCalls)),[{preventScroll:true}]);
assert.strictEqual(c.document.activeElement,replacement);assert.equal(settings(),before);finish();
})().catch(e=>{console.error(e.stack);process.exitCode=1});
''', projection=spectral_fixture())


if __name__ == '__main__':
    unittest.main()
