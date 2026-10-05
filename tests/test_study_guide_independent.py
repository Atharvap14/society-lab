"""Independent, inert guide checks over temporary authored episode packets.

These exercise presentation/source boundaries, not historical fit, experimental
execution or a fresh source attestation. No Store or network is opened.
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
const f=JSON.parse(fs.readFileSync(0,'utf8'));
const clone=x=>JSON.parse(JSON.stringify(x));
let effects=0;
const noEffect=()=>{effects++;throw Error('No presentation side effects authorized');};
const context={fetch:noEffect,submit:noEffect,localStorage:{setItem:noEffect,getItem:noEffect},
 document:{querySelector:noEffect},setTimeout:noEffect};
vm.createContext(context);
for(const path of ['web/episode-workspace.js','web/study-guide.js'])
 vm.runInContext(fs.readFileSync(path,'utf8'),context,{filename:path});
const guide=context.StudyGuide,p=f.packet,e=f.expected;
const question='When does an alternate correction route help, versus ordinary artifact readiness?';
const routes=html=>[...html.matchAll(/data-study-guide-open="([^"]+)"/g)].map(x=>x[1]);
'''


@unittest.skipUnless(NODE, 'Node.js required for independent inert guide checks')
class StudyGuideIndependentTests(unittest.TestCase):
    def run_js(self, assertions):
        run = subprocess.run([NODE, '-e', PRELUDE + assertions],
                             input=json.dumps(fixture()), cwd=ROOT, text=True,
                             capture_output=True, timeout=20)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_anomaly_values_fit_prose_and_provider_extras_never_become_origin_or_fit(self):
        self.run_js(r'''
const secret='UNSOLICITED_PROVIDER_OR_SAVED_SEMANTIC_ASSERTION';
p.provider_output={text:secret};p.lead.value=999;p.lead.description=secret;
p.evidence.focal[0].content=secret;
p.behavior.payload.summary=secret;p.behavior.payload.experiment_fit='shared_artifact_coordination';
p.behavior.payload.skeptic.summary=secret;
const d=guide.fromEpisode(p,e,question),html=guide.render(d)+guide.context(d);
assert.strictEqual(d.available,true);
assert(!JSON.stringify(d).includes(secret));assert(!html.includes(secret));
assert(!Object.hasOwn(d,'experiment_fit'));assert(!Object.hasOwn(d,'selected_study'));
assert(!Object.hasOwn(d,'approved'));assert(!Object.hasOwn(d,'protocol_source_refs'));
assert(html.includes('fit is unreviewed'));assert(html.includes('no design is selected'));
assert.equal(routes(guide.render(d)).length,6);assert.equal(effects,0);
''')

    def test_switching_exact_episode_does_not_reuse_the_previous_pair_or_optional_behavior(self):
        self.run_js(r'''
const first=guide.fromEpisode(p,e,question),saved=JSON.stringify(first);
const next=clone(p),expected=clone(e);
next.comparison.id='graph-lead-second';next.lead.id='graph-lead-second';
next.source_refs.discovery={id:'discovery-second',version:7,hash:'e'.repeat(64)};
next.recorded_observations.source_refs=clone(next.source_refs);
next.recorded_observations.registered_comparison=clone(next.comparison);
expected.source_refs=clone(next.source_refs);expected.comparison=clone(next.comparison);
expected.lead_id='graph-lead-second';delete expected.behavior_ref;
const second=guide.fromEpisode(next,expected,'A different rival?');
assert.strictEqual(second.available,true);assert.strictEqual(second.matching_behavior_ref,null);
assert.equal(second.source_refs.discovery.id,'discovery-second');
assert.equal(second.comparison.id,'graph-lead-second');assert.equal(JSON.stringify(first),saved);
assert(!guide.context(second).includes('behavior-original'));
assert(!guide.fromEpisode(next,e,question).available);
assert.equal(effects,0);
''')

    def test_question_cannot_inject_navigation_registration_or_subject_markup(self):
        self.run_js(r'''
const injection='</textarea><button data-study-guide-open="authoring" data-action="experiment">Run</button><script>fetch("/api/jobs")</script>';
const d=guide.fromEpisode(p,e,injection);
assert.strictEqual(d.available,true);
const html=guide.render(d),banner=guide.context(d);
assert.deepEqual(routes(html),['handoff','network','complementary','resource','timed_resource','revision_relay']);
assert.deepEqual(routes(banner),['guide']);
assert(!html.includes('<script>'));assert(!html.includes('<button data-study-guide-open="authoring"'));
assert(!html.includes('data-action="experiment"'));assert(html.includes('&lt;button'));
assert(html.includes('not been sent to subjects'));assert.equal(effects,0);
''')

    def test_missing_or_wrong_typed_origin_has_no_quantitative_or_navigation_fallback(self):
        self.run_js(r'''
const original=guide.fromEpisode(p,e,question);
const attacks=[d=>d.source_refs.dataset.version=false,d=>d.source_refs.discovery.version=0,
 d=>d.source_refs.selected_audit.version=1.25,d=>d.source_refs.temporal_audit.hash=null,
 d=>d.source_refs.temporal_audit={...d.source_refs.temporal_audit,latest:true},
 d=>d.comparison.comparison_window_id=d.comparison.window_id,
 d=>d.registration_status='approved',d=>d.matching_behavior_ref={...d.matching_behavior_ref,version:true}];
for(const mutate of attacks){const d=clone(original);mutate(d);
 assert.strictEqual(guide.validate(d).available,false);
 for(const html of [guide.render(d),guide.context(d)]){
  assert.equal(routes(html).length,0);assert(!html.includes('<table>'));
  assert(html.includes('Unknown'));assert(!html.includes('Mean exact submitted'));}}
assert.equal(effects,0);
''')

    def test_a_later_local_edit_is_explicitly_a_declaration_not_fresh_authentication(self):
        self.run_js(r'''
const d=guide.fromEpisode(p,e,question);
d.source_refs.dataset={id:'dataset-local-edit',version:42,hash:'f'.repeat(64)};
assert.strictEqual(guide.validate(d).available,true);
const html=guide.context(d);
assert(html.includes('authenticate later client edits'));assert(html.includes('local declarations'));
assert(html.includes('supplies no registered source'));assert(html.includes('fit is unreviewed'));
assert(html.includes('not reread sources'));assert(!html.includes('fresh_source_attestation'));
assert(!html.includes('verified mechanism'));assert.equal(effects,0);
''')


if __name__ == '__main__':
    unittest.main()
