"""Saved research collections exercise the actual browser controllers.

API replies and model replies are isolated fixtures. They attest no empirical
result or model behavior; these checks cover filtering, pins and UI routing.
"""
import importlib.util
import json
import pathlib
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "saved_research_workspace_fixture", ROOT / "tests/test_lab_workspace_ui.py"
)
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)
NODE = FIXTURE.NODE
CATALOG = r"""
const outcomes=['experiment','network_experiment','complementary_experiment','resource_experiment','timed_resource_experiment','revision_relay_experiment'];
const supportedOutcomes=['village_access_experiment','village_recovery_experiment'];
function saved(kind,index,extra={}){return {ref:{id:kind+'-'+index,version:1,hash:(index%10).toString().repeat(64)},
 kind,title:'Saved '+kind+' '+index,summary:'Descriptive saved work '+index,relation:'reference',
 origin:{project_id:'project-b',project_name:'Other project',chat_id:'chat-b',chat_name:'Other discussion'},...extra};}
function catalog(env,items,extra={}){env.b.handle=request=>request.path.startsWith('/api/workspaces/artifacts?')?
 {artifacts:clone(items),edges:[],total:items.length,truncated:false,...extra}:undefined;}
function cards(html){return [...html.matchAll(/<article class="ws-saved-card">([\s\S]*?)<\/article>/g)].map(m=>m[1]);}
function attrs(html){return [...html.matchAll(/data-ws-intent="(explain|replay)" data-ws-artifact-ref="([^"]+)" data-ws-version="(\d+)" data-ws-hash="([a-f0-9]+)"/g)]
 .map(m=>({intent:m[1],id:m[2],version:Number(m[3]),hash:m[4]}));}
function scientificWrites(env){return env.log.requests.filter(r=>r.method==='POST' && r.path!=='/api/guide/chat' && r.body?.op!=='save_state');}
"""


class SavedResearchUITests(unittest.TestCase):
    def test_legacy_overview_enters_chat_and_library_defaults_to_latest_versions(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();
assert(env.workspace.hasView('overview'));const front=await env.workspace.render('overview');
assert(front.includes('id="ws-compose"'));assert(!front.includes('Begin an investigation'));
assert(!front.includes('Research registry'));assert(!front.includes('Run full workflow'));
const old=saved('behavior',1,{title:'Older candidate',ref:{id:'behavior-same',version:1,hash:'a'.repeat(64)}});
const recent=saved('behavior',2,{title:'Revised candidate',ref:{id:'behavior-same',version:2,hash:'b'.repeat(64)}});
catalog(env,[recent,old]);let html=await env.workspace.render('library');
assert(html.includes('Revised candidate'));assert(!html.includes('Older candidate'));
env.workspace.input(target({},'Older candidate','ws-artifact-search'));
html=await env.workspace.render('library');assert(html.includes('Older candidate'));assert(!html.includes('Revised candidate'));
assert.equal(scientificWrites(env).length,0);
""")

    def test_long_exact_mention_identity_is_a_value_not_an_oversized_json_key(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();
const long={kind:'artifact',ref:{id:'observability_run-'+'x'.repeat(100),version:1,hash:'a'.repeat(64)},origin_chat_id:'chat-'+'z'.repeat(80)};
const key=JSON.stringify(long);assert(key.length>200);env.workspace.state.mentionLabels[key]='Actual captured run';
const exported=env.workspace;await exported.flush();
// state() is used by the actual save path; induce a dirty state and inspect that request.
exported.notify();await exported.flush();
const request=env.log.requests.filter(r=>r.body?.op==='save_state').at(-1);
assert(request);const labels=request.body.state.ui.workspace.mention_labels;
assert(Array.isArray(labels));assert(labels.some(row=>row.key===key && row.label==='Actual captured run'));
assert(labels.length<=64);assert(!Object.keys(labels[0]).some(k=>k.length>200));
""")

    def test_starter_rubrics_and_prompt_measurements_are_visible_without_execution(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();
const items=[saved('behavior_rubric',1),saved('rubric_measurement',2),saved('experiment',3)];
env.b.handle=request=>request.path==='/api/rubrics'?{catalog:[{id:'C6',title:'Responding <safely>',question:'Did a correction change an action?',opportunity:'Established receipt and valid correction.',unknown:'Missing receipt is unknown.'}]}:request.path.startsWith('/api/workspaces/artifacts?')?{artifacts:clone(items),edges:[],total:3}:undefined;
const html=await env.workspace.render('library');
assert(html.includes('Responding &lt;safely&gt;'));assert(html.includes('Missing receipt is unknown'));
assert(html.includes('Saved behavior_rubric 1'));assert(html.includes('Saved rubric_measurement 2'));
assert(!html.includes('Saved experiment 3'));assert(html.includes('Do not save or measure anything yet.'));
assert.equal(env.log.jobs.length,0);assert.equal(scientificWrites(env).length,0);
""")

    def node(self, script):
        result = subprocess.run(
            ["node", "-e", NODE, str(ROOT)],
            input=json.dumps({"script": CATALOG + script}),
            text=True, encoding="utf-8", capture_output=True, timeout=30, cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "PASS")

    def test_collections_include_only_scientific_record_types_and_search_precedes_cards(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();
const items=[saved('behavior',1),saved('theory',2),...outcomes.map((k,i)=>saved(k,i+3)),...supportedOutcomes.map((k,i)=>saved(k,i+16)),
 saved('guided_result',11),saved('guided_plan',12),saved('verification',13),saved('dataset',14),saved('claim_audit',15)];
catalog(env,items);
const library=await env.workspace.render('library'),experiments=await env.workspace.render('experiments');
assert.equal(cards(library).length,2);assert(cards(library).some(c=>c.includes('Saved behavior 1')));
assert(cards(library).some(c=>c.includes('Saved theory 2')));assert(!library.includes('Saved experiment 3'));
assert.equal(cards(experiments).length,2);for(const kind of supportedOutcomes)assert(cards(experiments).some(c=>c.includes('Saved '+kind+' ')));
for(const kind of outcomes)assert(!cards(experiments).some(c=>c.includes('Saved '+kind+' ')));
for(const kind of ['behavior','theory','guided_result','guided_plan','verification','dataset','claim_audit'])assert(!cards(experiments).some(c=>c.includes('Saved '+kind+' ')));
for(const html of [library,experiments])assert(html.indexOf('id="ws-artifact-search"')<html.indexOf('class="ws-saved-grid"'));
assert(library.includes('Candidate behaviours are not proven causes'));
assert(experiments.includes('Replaying uses saved events; a replication creates fresh teams'));
assert.equal(env.log.jobs.length,0);assert.equal(scientificWrites(env).length,0);
""")

    def test_search_filters_before_render_cap_and_preserves_exact_historical_versions(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();
const items=Array.from({length:125},(_,i)=>saved('village_recovery_experiment',i+20));
items.push(saved('village_recovery_experiment',170,{ref:clone(refs.result),title:'Needle old result'}));
catalog(env,items);let html=await env.workspace.render('experiments');
assert.equal(cards(html).length,120);assert(html.includes('first 120 matching versions'));assert(!html.includes('Needle old result'));
env.workspace.input(target({},'needle old','ws-artifact-search'));
html=await env.workspace.render('experiments');assert.equal(cards(html).length,1);assert(html.includes('Needle old result'));
assert(!html.includes('first 120 matching versions'));
assert.deepEqual(attrs(cards(html)[0]).map(a=>({id:a.id,version:a.version,hash:a.hash})),[refs.result,refs.result]);
assert.equal(env.log.reads.length,0);assert.equal(env.log.jobs.length,0);
""")

    def test_same_title_and_id_different_versions_keep_distinct_buttons_and_origin(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();
const old=saved('village_recovery_experiment',1,{ref:clone(refs.result),title:'Same saved title',
 origins:[{chat_id:'chat-a'},{chat_id:'chat-b'}]});
const newer=saved('village_recovery_experiment',2,{ref:clone(refs.latest),title:'Same saved title',
 origin:{project_id:'project-a',project_name:'First project',chat_id:'chat-a',chat_name:'First discussion'}});
catalog(env,[old,newer]);const html=await env.workspace.render('experiments');assert.equal(cards(html).length,2);
for(const reference of [refs.result,refs.latest])assert.equal(attrs(html).filter(a=>a.id===reference.id&&a.version===reference.version&&a.hash===reference.hash).length,2);
await env.workspace.click(target({'data-ws-intent':'explain','data-ws-artifact-ref':refs.result.id,'data-ws-version':'1','data-ws-hash':refs.result.hash}));
await env.workspace.click(target({'data-ws-intent':'explain','data-ws-artifact-ref':refs.latest.id,'data-ws-version':'2','data-ws-hash':refs.latest.hash}));
const calls=env.log.requests.filter(r=>r.path==='/api/guide/chat');assert.equal(calls.length,2);
assert.deepEqual(calls[0].body.mentioned_context,[{kind:'artifact',ref:refs.result,origin_chat_id:'chat-b'}]);
assert.deepEqual(calls[1].body.mentioned_context,[{kind:'artifact',ref:refs.latest,origin_chat_id:'chat-a'}]);
assert.equal(env.log.reads.length,0);assert.equal(scientificWrites(env).length,0);
""")

    def test_explain_and_replay_send_typed_mentions_without_direct_actions_or_draft_changes(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();env.experience.state.planRef=clone(refs.plan);
env.experience.input(target({'data-journey-field':'question'},'Keep this working question','journey-question'));
env.workspace.notify();const before=JSON.stringify(env.experience.state.draft),source=clone(env.experience.state.project),plan=clone(env.experience.state.planRef);
const behavior=saved('behavior',1);catalog(env,[behavior,saved('village_recovery_experiment',2,{ref:clone(refs.result)})]);
await env.workspace.render('library');await env.workspace.click(target({'data-ws-intent':'explain','data-ws-artifact-ref':behavior.ref.id,'data-ws-version':'1','data-ws-hash':behavior.ref.hash}));
await env.workspace.render('experiments');await env.workspace.click(target({'data-ws-intent':'replay','data-ws-artifact-ref':refs.result.id,'data-ws-version':'1','data-ws-hash':refs.result.hash}));
const calls=env.log.requests.filter(r=>r.path==='/api/guide/chat');assert.equal(calls.length,2);
assert.deepEqual(calls[0].body.mentioned_context,[{kind:'artifact',ref:behavior.ref,origin_chat_id:'chat-b'}]);
assert.deepEqual(calls[1].body.mentioned_context,[{kind:'artifact',ref:refs.result,origin_chat_id:'chat-b'}]);
assert(calls[0].body.message.includes('Do not run or change anything'));assert(calls[1].body.message.includes('Keep my current draft unchanged'));
for(const call of calls){assert.equal(call.headers['X-Lab-Chat'],'chat-a');assert.equal(call.headers['X-Lab-Token'],'unit-csrf');assert.equal(call.body.active_chat_id,'chat-a');}
assert.equal(JSON.stringify(env.experience.state.draft),before);assert.deepEqual(env.experience.state.project,source);assert.deepEqual(env.experience.state.planRef,plan);
assert.equal(env.log.reads.length,0);assert.equal(env.log.jobs.length,0);assert.equal(scientificWrites(env).length,0);
""")

    def test_view_changes_and_pending_guide_dont_replace_per_chat_drafts(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();catalog(env,[saved('village_recovery_experiment',1,{ref:clone(refs.result)}),saved('behavior',2)]);
env.experience.input(target({'data-journey-field':'question'},'Unfinished A','journey-question'));env.workspace.notify();
const pending=hold(),originalHandle=env.b.handle;env.b.handle=req=>req.path==='/api/guide/chat'?pending.promise:originalHandle(req);
await env.workspace.render('experiments');const operation=env.workspace.click(target({'data-ws-intent':'replay','data-ws-artifact-ref':refs.result.id,'data-ws-version':'1','data-ws-hash':refs.result.hash}));await settle();
await env.workspace.render('library');assert.equal(env.experience.state.draft.question,'Unfinished A');
await env.workspace.click(target({'data-ws-intent':'explain','data-ws-artifact-ref':'behavior-2','data-ws-version':'1','data-ws-hash':'2'.repeat(64)}));
assert.equal(env.log.requests.filter(r=>r.path==='/api/guide/chat').length,1,'busy guide does not duplicate request');
await env.workspace.loadChat('chat-b');assert.equal(env.experience.state.draft.question,'Question B');
pending.resolve({answer_source:'ai',answer:'Late fixture',plan_draft:{question:'Unwanted old edit'},actions:[],sources:[]});await operation;
assert.equal(env.experience.state.draft.question,'Question B');await env.workspace.loadChat('chat-a');
assert.equal(env.experience.state.draft.question,'Unfinished A');assert.equal(env.log.jobs.length,0);assert.equal(scientificWrites(env).length,0);
""")

    def test_untrusted_saved_titles_summaries_origins_and_search_are_escaped(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();catalog(env,[saved('behavior',1,{title:'<img src=x onerror=attack()>',
 summary:'</p><script>attack()</script>',origin:{project_name:'<svg onload=attack()>',chat_name:'" onclick="attack()'}})]);
const html=await env.workspace.render('library');assert(!html.includes('<img'));assert(!html.includes('<script>attack'));assert(!html.includes('<svg onload'));
assert(html.includes('&lt;img'));assert(html.includes('&lt;script&gt;'));assert(html.includes('&quot; onclick=&quot;'));
env.workspace.input(target({},'" autofocus onfocus="attack()','ws-artifact-search'));
const searched=await env.workspace.render('library');assert(searched.includes('value="&quot; autofocus onfocus=&quot;attack()"'));assert.equal(cards(searched).length,0);
assert.equal(env.log.jobs.length,0);assert.equal(scientificWrites(env).length,0);
""")


if __name__ == "__main__":
    unittest.main()
