"""Inert local study-choice rendering from authored exact episode fixtures.

Runs actual EpisodeWorkspace gates in a Node VM, without jobs or retrieval.
These are presentation-contract checks, not empirical validation of a world.
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
const f=JSON.parse(fs.readFileSync(0,'utf8')),clone=x=>JSON.parse(JSON.stringify(x));
let effects=0;
const forbidden=()=>{effects++;throw new Error('Study guide must be inert');};
const app={live:false,state:{usage:{calls:400},jobs:[]}},beforeApp=JSON.stringify(app);
const c={app,fetch:forbidden,submit:forbidden,setTimeout:forbidden,setInterval:forbidden,
 XMLHttpRequest:forbidden,WebSocket:forbidden,document:{querySelector:forbidden},
 localStorage:{setItem:forbidden,getItem:forbidden}};
vm.createContext(c);vm.runInContext(fs.readFileSync('web/episode-workspace.js','utf8'),c);
const episode=c.EpisodeWorkspace;
let gateCalls=0,draftCalls=0;
c.EpisodeWorkspace={...episode,validate:(...args)=>{gateCalls++;return episode.validate(...args);},
 draft:(...args)=>{draftCalls++;return episode.draft(...args);}};
vm.runInContext(fs.readFileSync('web/study-guide.js','utf8'),c);
const ui=c.StudyGuide,p=f.packet,e=f.expected,question='What would contradict task-specific dependence?';
const draft=()=>ui.fromEpisode(p,e,question);
const routes=html=>[...html.matchAll(/data-study-guide-open="([^"]+)"/g)].map(x=>x[1]);
const finish=()=>{assert.equal(effects,0);assert.equal(JSON.stringify(app),beforeApp);};
'''


@unittest.skipUnless(NODE, 'Node.js required for isolated browser renderer checks')
class StudyGuideUITests(unittest.TestCase):
    def run_js(self, checks):
        run = subprocess.run([NODE, '-e', PRELUDE + checks], input=json.dumps(fixture()),
                             cwd=ROOT, text=True, capture_output=True, timeout=20)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_real_episode_validators_exact_cloned_origin_and_no_effects(self):
        self.run_js(r'''
const d=ui.fromEpisode(p,e,'  '+question+'  ');
assert.equal(gateCalls,1);assert.equal(draftCalls,1);assert(ui.validate(d).available);
assert.equal(d.research_question,question);assert.equal(d.registration_status,'unregistered_local_draft');
assert.deepEqual(JSON.parse(JSON.stringify(d.source_refs)),p.source_refs);
assert.deepEqual(JSON.parse(JSON.stringify(d.comparison)),p.comparison);
assert.deepEqual(JSON.parse(JSON.stringify(d.matching_behavior_ref)),e.behavior_ref);
const saved=JSON.stringify(d);
for(const name of Object.keys(p.source_refs)){p.source_refs[name].id='changed-'+name;e.source_refs[name].version=999;}
p.comparison.window_id='changed-window';p.behavior.ref.hash='f'.repeat(64);
assert.equal(JSON.stringify(d),saved);assert(!('content' in d));
assert.equal(Object.keys(d.source_refs).length,4);finish();
''')

    def test_tampered_episode_pin_comparison_and_source_gates_fail_closed(self):
        self.run_js(r'''
const attacks=[x=>x.source_refs.dataset.hash='f'.repeat(64),
 x=>x.source_refs.discovery.version=true,x=>x.source_refs.selected_audit.version=1.5,
 x=>x.source_refs.temporal_audit=null,x=>x.source_refs.extra=e.source_refs.dataset,
 x=>x.comparison.window_id=x.comparison.comparison_window_id,
 x=>x.comparison.feature='unrelated_feature',x=>x.comparison.extra='not exact',
 x=>x.recorded_observations.base_context_gates.current_producer_byte_pins_match=false,
 x=>x.fresh_source_attestation=true,x=>x.database_writes=1];
for(const attack of attacks){const x=clone(p);attack(x);const d=ui.fromEpisode(x,e,question);
 assert.strictEqual(d.available,false);assert.equal(routes(ui.render(d)).length,0);
 assert(!ui.render(d).includes('data-study-guide-question'));}
assert.equal(draftCalls,0);finish();
''')

    def test_absent_unrequested_or_mismatched_behavior_is_explicit_unknown(self):
        self.run_js(r'''
for(const expected of [(()=>{const x=clone(e);delete x.behavior_ref;return x;})(),
 {...clone(e),behavior_ref:{...clone(e.behavior_ref),hash:'f'.repeat(64)}}]){
 const d=ui.fromEpisode(p,expected,question);assert(ui.validate(d).available);
 assert.strictEqual(d.matching_behavior_ref,null);
 for(const html of [ui.render(d),ui.context(d)]){
  assert(html.includes('Matching behavior: Unknown'));assert(!html.includes('behavior-original'));
  assert(html.includes('Not registered or attached to protocols; form submission is separate.'));}}
finish();
''')

    def test_six_choices_whitelisted_separate_outcome_falsifier_and_scope(self):
        self.run_js(r'''
const d=draft(),html=ui.render(d);
assert.deepEqual(routes(html),['handoff','network','complementary','resource','timed_resource','revision_relay']);
assert.equal((html.match(/<dt>Assignment<\/dt>/g)||[]).length,6);
assert.equal((html.match(/<dt>Executed outcome<\/dt>/g)||[]).length,6);
assert.equal((html.match(/<dt>Cheapest falsifier<\/dt>/g)||[]).length,6);
assert.equal((html.match(/<dt>Fit and scope limits<\/dt>/g)||[]).length,6);
for(const text of ['not extra randomized replicates','not a behavioral or causal finding',
 'Copy multiplicity is fixed, not randomized','not different trigger timings',
 'No private thought insertion or interaction p-value','fit is unreviewed',
 'not been sent to subjects','no design is selected or judged to fit automatically'])assert(html.includes(text),text);
assert(!html.includes('<form'));assert(!html.includes('data-action='));assert(!html.includes('data-study="'));
assert(!html.includes('aria-selected="true"'));finish();
''')

    def test_transient_empty_question_keeps_origin_and_field_without_old_text(self):
        self.run_js(r'''
const d=draft(),pins=JSON.stringify(d.source_refs),comparison=JSON.stringify(d.comparison);
d.research_question='';assert.strictEqual(ui.validate(d).available,false);
let html=ui.render(d);assert(html.includes('data-study-guide-question></textarea>'));
assert(!html.includes(question));assert(html.includes('study navigation is disabled'));
assert.equal((html.match(/data-study-guide-open="[^"]+" disabled/g)||[]).length,6);
assert.equal(JSON.stringify(d.source_refs),pins);assert.equal(JSON.stringify(d.comparison),comparison);
assert(ui.context(d).includes('Question currently empty.'));
d.research_question='A revised falsifiable question?';assert(ui.validate(d).available);
html=ui.render(d);assert(!html.includes(' disabled'));assert(html.includes(d.research_question));
assert.equal(JSON.stringify(d.source_refs),pins);finish();
''')

    def test_question_types_bounds_and_escaping_never_become_markup(self):
        self.run_js(r'''
const attack='</textarea><script>submit("run")</script>&\"\'';
const d=ui.fromEpisode(p,e,attack);assert(ui.validate(d).available);
for(const html of [ui.render(d),ui.context(d)]){
 assert(!html.includes('<script>'));assert(html.includes('&lt;script&gt;'));
 assert(html.includes('&amp;'));assert(html.includes('&quot;'));assert(html.includes('&#39;'));}
for(const q of [null,17,true,{},[],'' ,' '.repeat(20),'x'.repeat(4001)]){
 const result=ui.fromEpisode(p,e,q);assert.strictEqual(result.available,false);
 const x=draft();x.research_question=q;assert.strictEqual(ui.validate(x).available,false);
 assert(!ui.render(x).includes('data-study-guide-open="handoff">'));}
assert(ui.fromEpisode(p,e,'x'.repeat(4000)).available);
const x=draft();x.research_question='q'.repeat(4001);const html=ui.render(x);
assert(html.includes('display is truncated'));assert.equal(x.research_question.length,4001);
assert(!html.includes('q'.repeat(4001)));finish();
''')

    def test_strict_local_origin_validation_and_unavailable_dependency(self):
        self.run_js(r'''
const attacks=[x=>x.source_refs.dataset.version=true,x=>x.source_refs.discovery.hash='not-a-hash',
 x=>x.source_refs.selected_audit.extra='ignored?',x=>delete x.source_refs.temporal_audit,
 x=>x.source_refs.dataset.id='<img src=x>',x=>x.comparison.extra=true,
 x=>x.comparison.comparison_window_id=x.comparison.window_id,
 x=>x.matching_behavior_ref.version='4',x=>x.matching_behavior_ref=null,
 x=>x.registration_status='registered',x=>x.available=1,x=>x.jobs=[]];
for(const [i,attack] of attacks.entries()){const x=draft();attack(x);
 if(i===8){assert(ui.validate(x).available);continue;}
 assert.strictEqual(ui.validate(x).available,false);
 assert.equal(routes(ui.render(x)).length,0);assert.equal(routes(ui.context(x)).length,0);}
c.EpisodeWorkspace=undefined;assert.strictEqual(ui.fromEpisode(p,e,question).available,false);finish();
''')

    def test_context_is_reusable_declared_origin_with_only_local_controls(self):
        self.run_js(r'''
const d=draft(),before=JSON.stringify(d);
for(const study of ['handoff','network','complementary','resource','timed_resource','revision_relay']){
 const html=ui.context(d);assert.deepEqual(routes(html),['guide']);
 assert(html.includes('data-study-guide-clear="true"'));assert(html.includes('data-view="episode"'));
 assert(html.includes('Not registered or attached to protocols; form submission is separate.'));
 assert(html.includes('Origin is motivation only; fit is unreviewed.'));
 assert(html.includes('pre-existing form behavior/source selection must be reviewed independently'));
 for(const ref of Object.values(d.source_refs)){
  assert(html.includes(ref.id));assert(html.includes(ref.hash));}
 assert(html.includes(d.comparison.id));assert(html.includes(d.comparison.window_id));
 assert(html.includes(d.comparison.comparison_window_id));assert(html.includes(question));
 assert(!html.includes('data-action='));}
assert.equal(JSON.stringify(d),before);assert.equal(app.live,false);assert.equal(app.state.usage.calls,400);finish();
''')


if __name__ == '__main__':
    unittest.main()
