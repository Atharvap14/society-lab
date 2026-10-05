"""Exercise the actual episode-to-study navigation without registration or calls."""
import json
import subprocess
import unittest

from tests.test_episode_workspace_routes import NODE, ROOT, PRELUDE
from tests.test_episode_workspace_ui import fixture


@unittest.skipUnless(NODE, 'Node required for actual dashboard routes')
class StudyGuideRouteTests(unittest.TestCase):
    def run_js(self, body):
        setup = PRELUDE + r'''
vm.runInContext(fs.readFileSync('web/study-guide.js','utf8'),c);
const focused=[],scrolled=[];
node('main').focus=()=>focused.push('main');
for(const id of ['main','design-form','network-design-form','complementary-design-form','resource-design-form','timed-resource-design-form','revision-relay-design-form'])node(id).scrollIntoView=()=>scrolled.push(id);
run("app.live=true;app.harness='codex';app.selected.behavior='separate-existing-selection';app.authoringQuestion='separate authoring draft';app.authoringCapabilities='separate-capability';app.authoringBehavior='separate-behavior';app.relayBlocks=7;app.relaySeed=123;");
const click=dataset=>listeners.click({target:button(dataset)});
const snapshot=()=>run("JSON.stringify({live:app.live,harness:app.harness,selected:app.selected,authoringQuestion:app.authoringQuestion,authoringCapabilities:app.authoringCapabilities,authoringBehavior:app.authoringBehavior,relayBlocks:app.relayBlocks,relaySeed:app.relaySeed})");
async function openDraft(){await c.openEpisodeWorkspace(r.discovery,p.lead.id);run("app.episodeQuestion='Which assigned timing and alternate route would distinguish two explanations?'");await click({episodeStudyGuide:''});}
'''
        result = subprocess.run([NODE, '-e', setup + body], input=json.dumps(fixture()),
                                text=True, capture_output=True, cwd=ROOT, timeout=25)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_exact_episode_question_retains_origin_without_selecting_or_registering(self):
        self.run_js(r'''
(async()=>{
const before=snapshot();await openDraft();
assert.equal(run('app.view'),'experiments');assert.equal(run('app.experimentStudy'),'guide');
assert.equal(snapshot(),before);const d=run('app.studyGuideDraft');
assert.deepEqual(JSON.parse(JSON.stringify(d.source_refs)),p.source_refs);
assert.deepEqual(JSON.parse(JSON.stringify(d.comparison)),p.comparison);
assert.equal(d.matching_behavior_ref,null);assert.equal(d.registration_status,'unregistered_local_draft');
assert.equal(c.StudyGuide.validate(d).available,true);
const saved=d.source_refs.discovery.hash;p.source_refs.discovery.hash='b'.repeat(64);assert.equal(d.source_refs.discovery.hash,saved);
assert(!requests.some(x=>x.startsWith('/api/jobs')));
})().catch(e=>{console.error(e.stack);process.exitCode=1});
''')

    def test_six_design_routes_focus_existing_controls_preserve_flags_and_fields(self):
        self.run_js(r'''
(async()=>{
await openDraft();const before=snapshot(),requestCount=requests.length;
const routes={handoff:'design-form',network:'network-design-form',complementary:'complementary-design-form',resource:'resource-design-form',timed_resource:'timed-resource-design-form',revision_relay:'revision-relay-design-form'};
for(const [study,form] of Object.entries(routes)){
await click({studyGuideOpen:study});assert.equal(run('app.experimentStudy'),study);
assert.equal(scrolled.at(-1),form);assert.equal(focused.at(-1),'main');assert.equal(snapshot(),before);
assert(c.StudyGuide.context(run('app.studyGuideDraft')).includes('Not registered or attached to protocols; form submission is separate.'));
}
assert.equal(requests.length,requestCount);assert(!requests.some(x=>x.startsWith('/api/jobs')));
})().catch(e=>{console.error(e.stack);process.exitCode=1});
''')

    def test_blank_question_blocks_route_but_can_be_edited_without_losing_origin(self):
        self.run_js(r'''
(async()=>{
await openDraft();const source=JSON.stringify(run('app.studyGuideDraft.source_refs'));
await listeners.input({target:{dataset:{studyGuideQuestion:''},value:''}});
assert.equal(run('app.studyGuideDraft.research_question'),'');
assert.equal(c.StudyGuide.validate(run('app.studyGuideDraft')).available,false);
await click({studyGuideOpen:'resource'});assert.equal(run('app.experimentStudy'),'guide');
assert(c.StudyGuide.render(run('app.studyGuideDraft')).includes('data-study-guide-question'));
await listeners.input({target:{dataset:{studyGuideQuestion:''},value:'A revised falsifiable question?'}});
assert.equal(c.StudyGuide.validate(run('app.studyGuideDraft')).available,true);
assert.equal(JSON.stringify(run('app.studyGuideDraft.source_refs')),source);
await click({studyGuideOpen:'resource'});assert.equal(run('app.experimentStudy'),'resource');
assert(!requests.some(x=>x.startsWith('/api/jobs')));
})().catch(e=>{console.error(e.stack);process.exitCode=1});
''')

    def test_unsupported_route_invalid_origin_and_clear_are_local_only(self):
        self.run_js(r'''
(async()=>{
await openDraft();const count=requests.length;
await click({studyGuideOpen:'execute_everything'});assert.equal(run('app.experimentStudy'),'guide');
run("app.studyGuideDraft.source_refs.dataset.version=true");
await click({studyGuideOpen:'revision_relay'});assert.equal(run('app.experimentStudy'),'guide');
await click({studyGuideClear:''});assert.equal(run('app.studyGuideDraft'),null);
assert.equal(requests.length,count);assert.equal(run('app.live'),true);
})().catch(e=>{console.error(e.stack);process.exitCode=1});
''')

    def test_unavailable_episode_or_empty_question_cannot_create_draft(self):
        self.run_js(r'''
(async()=>{
await c.openEpisodeWorkspace(r.discovery,p.lead.id);run("app.episodeQuestion=''");
await click({episodeStudyGuide:''});assert.equal(run('app.view'),'episode');assert.equal(run('app.studyGuideDraft'),null);
run("app.episodeQuestion='Valid question?';app.episodePacket.available=false");
await click({episodeStudyGuide:''});assert.equal(run('app.view'),'episode');assert.equal(run('app.studyGuideDraft'),null);
assert(!requests.some(x=>x.startsWith('/api/jobs')));
})().catch(e=>{console.error(e.stack);process.exitCode=1});
''')
