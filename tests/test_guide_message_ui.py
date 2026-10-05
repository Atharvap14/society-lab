"""Safe recorded-guide presentation; fixture receipts are not empirical findings."""
import json
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');let effects=0;
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const context=vm.createContext({assert,URL,fetch(){effects++;throw Error('No transport');},
 document:{createElement(){effects++;throw Error('Pure render only');}},setTimeout(){effects++;throw Error('No effects');}});
vm.runInContext(fs.readFileSync(process.argv[1]+'/web/guide-message.js','utf8'),context);
vm.runInContext(String.raw`
const R={id:'experiment-source',version:3,hash:'a'.repeat(64)},clone=v=>JSON.parse(JSON.stringify(v));
function reply(){return {answer:'## A saved comparison\n\n**Inspect the report** before proposing a mechanism.',
 working_notes:[{kind:'task_summary',text:'Read the selected saved context.'},
 {kind:'operation_summary',tool:'create_simulator',status:'completed',text:'The construction operation returned.'}],
 tool_results:[{tool:'create_simulator',status:'completed',summary:'Saved a checked world; subjects have not run.',
 result_refs:[clone(R)],result_refs_truncated:false,job_id:'job-build'}],
 sources:[{kind:'experiment',object_ref:clone(R),label:'Exact saved report'}]};}
function saved(){return {role:'assistant',content:reply().answer,metadata:{answer_source:'ai',scientific_evidence:false,guide_result:reply()}};}
`,context);
(async()=>{await vm.runInContext('(async()=>{'+input.script+'})()',context,{timeout:10000});assert.equal(effects,0);process.stdout.write('PASS');})()
 .catch(error=>{console.error(error);process.exitCode=1;});
"""


class GuideMessageUITests(unittest.TestCase):
    def node(self, script):
        result = subprocess.run(["node", "-e", NODE, str(ROOT)], input=json.dumps({"script": script}),
                                text=True, encoding="utf-8", capture_output=True, timeout=25, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "PASS")

    def test_saved_nested_metadata_and_fresh_reply_render_same_recorded_operations(self):
        self.node(r"""
const a=GuideMessage.render(saved()),b=GuideMessage.render(reply());
assert(a.includes('<h2>A saved comparison</h2>'));assert(a.includes('<strong>Inspect the report</strong>'));
assert(a.includes('Working summary'));assert(a.includes('2 recorded notes'));assert(a.includes('Tool activity'));
assert(a.includes('Saved a checked world; subjects have not run.'));assert(a.includes('Operation receipts are separate from scientific verification'));
assert(a.includes('data-ws-artifact="experiment-source"'));assert(a.includes('data-ws-version="3"'));assert(a.includes('data-ws-hash="'+R.hash+'"'));
assert.equal(a,b);assert(!a.includes('open><summary>Working summary'),'working notes are collapsed by default');
""")

    def test_supported_markdown_and_code_tables_are_safe_structural_html(self):
        self.node(r"""
const markdown='# Heading\n\n- **First**\n- *Second* with `literal <tag>`\n\n1. Ordered\n2. Next\n\n```python\nprint("<script>unsafe</script>")\n```\n\n| Arm | Result |\n| --- | ---: |\n| A | Unknown |\n| B | 0 / 2 |\n\n> Quoted report';
const html=GuideMessage.markdown(markdown);
assert(html.includes('<h1>Heading</h1>'));assert(html.includes('<ul>'));assert(html.includes('<ol>'));
assert(html.includes('<code>literal &lt;tag&gt;</code>'));assert(html.includes('class="language-python"'));
assert(html.includes('&lt;script&gt;unsafe&lt;/script&gt;'));assert(!html.includes('<script>'));
assert(html.includes('<table>'));assert(html.includes('<th scope="col">Arm</th>'));assert(html.includes('<td>Unknown</td>'));
assert(html.includes('<blockquote>Quoted report</blockquote>'));
""")

    def test_identifier_underscores_remain_literal_across_words_links_and_tables(self):
        self.node(r"""
const text='Run the run_experiment tool with the guided_simulator-123 artifact. '+
 'The source_ref and current_context fields belong to revision_relay_experiment.';
const html=GuideMessage.markdown(text);assert.equal(html,'<p>'+text+'</p>');assert(!html.includes('<em>'));
const linked=GuideMessage.markdown('[run_experiment](https://example.com) and `source_ref`');
assert(linked.includes('>run_experiment</a>'));assert(linked.includes('<code>source_ref</code>'));assert(!linked.includes('<em>'));
const table=GuideMessage.markdown('| source_ref | tool_name |\n| --- | --- |\n| guided_simulator-123 | run_experiment |');
assert(table.includes('<th scope="col">source_ref</th>'));assert(table.includes('<td>run_experiment</td>'));
assert(!table.includes('<em>'));assert.equal(GuideMessage.markdown('α_beta_γ 食_run_experiment_名'),'<p>α_beta_γ 食_run_experiment_名</p>');
""")

    def test_bounded_underscore_emphasis_and_existing_asterisks_remain_supported(self):
        self.node(r"""
const html=GuideMessage.markdown('_emphasis_ and __strong__ plus *stars* and **bold**.');
assert.equal(html,'<p><em>emphasis</em> and <strong>strong</strong> plus <em>stars</em> and <strong>bold</strong>.</p>');
assert.equal(GuideMessage.markdown('(_marked_) and _run_experiment_'),'<p>(<em>marked</em>) and <em>run_experiment</em></p>');
assert.equal(GuideMessage.markdown('_ spaced _ and run__experiment__tool'),'<p>_ spaced _ and run__experiment__tool</p>');
assert.equal(GuideMessage.markdown('a_b c_d and **run_experiment**'),'<p>a_b c_d and <strong>run_experiment</strong></p>');
""")

    def test_recorded_event_graph_keeps_direction_fields_caps_and_exact_source(self):
        self.node(r"""
const graph={graph_version:'event-evidence-neighborhood-v1',source_ref:clone(R),seed_event_id:'returned',truncated:true,
 nodes:[{id:'returned',kind:'tool.returned',actor_id:'actor-a'},{id:'called',kind:'tool.called',actor_id:'actor-a'}],
 edges:[{source:'returned',target:'called',relation:'tool_call_reference',field:'data.call_id',status:'matching_declared_reference',
 provenance:{event_id:'returned',field:'data.call_id',event_sha256:'c'.repeat(64)}}],diagnostics:[]};
const response={answer:'Source links only.',tool_results:[{tool:'event_neighborhood',status:'completed',summary:'Read exact source references.',result_refs:[clone(R)],event_graph:graph}]};
const before=JSON.stringify(response),fresh=GuideMessage.render(response),saved=GuideMessage.render({role:'assistant',content:response.answer,metadata:{guide_result:response}});
assert.equal(fresh,saved,'main/dock and persisted/fresh rows use the same pure renderer');assert(fresh.includes('aria-label="Recorded event reference graph"'));
assert(fresh.includes('<polygon points='));assert(fresh.includes('returned → called · tool_call_reference · data.call_id'));
assert(fresh.includes('do not show influence, reading or verified tool execution'));assert(fresh.includes('graph display is capped'));
assert(fresh.includes('Open the exact graph source'));assert.equal(JSON.stringify(response),before);
response.tool_results[0].status='failed';assert(!GuideMessage.render(response).includes('gm-event-graph'));
response.tool_results[0].status='completed';response.tool_results[0].tool='other_operation';assert(!GuideMessage.render(response).includes('gm-event-graph'));
""")

    def test_event_graph_malformed_identity_caps_and_markup_fail_closed(self):
        self.node(r"""
const graph={graph_version:'event-evidence-neighborhood-v1',source_ref:clone(R),seed_event_id:'post',truncated:false,
 nodes:[{id:'post',kind:'message.sent',actor_id:'actor'}],edges:[],diagnostics:[]};
const render=g=>GuideMessage.render({answer:'Graph receipt',tool_results:[{tool:'event_neighborhood',status:'completed',summary:'Read exact references.',event_graph:g}]});
for(const edit of [g=>g.source_ref.version=true,g=>g.nodes.push(clone(g.nodes[0])),g=>g.nodes[0].actor_id='<svg onload=attack()>',
 g=>g.nodes=Array.from({length:9},(_,i)=>({id:'n'+i,kind:'message.sent',actor_id:null})),g=>g.edges=Array(9).fill({}),
 g=>g.diagnostics=Array(3).fill({}),g=>g.seed_event_id='unknown',g=>g.nodes[0].kind='unknown']){
 const value=clone(graph);edit(value);const html=render(value);assert(html.includes('event graph is unavailable'));assert(!html.includes('gm-event-graph'));assert(!html.includes('<svg onload'));
}
const value=clone(graph);value.edges=[{source:'post',target:'post',relation:'reply_reference',field:'<img onerror=attack()>',status:'matching_declared_reference',
 provenance:{event_id:'post',field:'<img onerror=attack()>',event_sha256:'a'.repeat(64)}}];
const html=render(value);assert(html.includes('&lt;img onerror=attack()&gt;'));assert(!html.includes('<img'));assert(!html.includes('<script'));
value.private_extra=value;assert(render(value).includes('gm-event-graph'),'unselected circular extras are never copied or traversed');
""")

    def test_links_disallow_script_data_credentials_and_attribute_injection(self):
        self.node(r"""
const body='[Safe](https://example.com/report?q=a&n=2) [HTTP](http://example.com) [Anchor](#report) '+
 '[Bad](javascript:alert(1)) [Data](data:text/html,unsafe) [Credentials](https://user:password@example.com) '+
 '[Encoded](java%73cript:bad) [Space](https://example.com/ bad) <img src=x onerror=run()> <iframe src=bad></iframe>';
const html=GuideMessage.markdown(body);assert.equal((html.match(/<a /g)||[]).length,3);
assert(html.includes('href="https://example.com/report?q=a&amp;n=2"'));assert(html.includes('rel="noopener noreferrer"'));
assert(!html.includes('href="javascript:'));assert(!html.includes('href="data:'));assert(!html.includes('<img'));
assert(!html.includes('<iframe'));assert(html.includes('&lt;img'));assert(html.includes('[Bad]'));
""")

    def test_no_hidden_reasoning_or_raw_provider_payload_is_rendered(self):
        self.node(r"""
const p=saved();p.metadata.provider_reply_excerpt='RAW PROVIDER BODY MUST NOT APPEAR';
p.metadata.guide_result.reasoning='PRIVATE REASONING MUST NOT APPEAR';p.metadata.guide_result.thinking='INVENTED THOUGHT';
p.metadata.guide_result.working_notes.push({kind:'hidden_chain_of_thought',text:'UNSUPPORTED NOTE'});
const html=GuideMessage.render(p);assert(!html.includes('RAW PROVIDER'));assert(!html.includes('PRIVATE REASONING'));
assert(!html.includes('INVENTED THOUGHT'));assert(!html.includes('UNSUPPORTED NOTE'));assert(html.includes('Visible task and operation summaries'));
const user={...p,role:'user'};assert(!GuideMessage.render(user).includes('Tool activity'));
assert(!GuideMessage.render(user).includes('Working summary'));
""")

    def test_failed_and_pending_operations_never_become_completed_and_refs_are_exact(self):
        self.node(r"""
const p=reply();p.tool_results=[{tool:'run_experiment',status:'pending_or_unknown',summary:'An earlier operation started.',result_refs:[]},
 {tool:'create_simulator',status:'failed',summary:'Partial artifacts remain available.',result_refs:[{...R,version:true}]},
 {tool:'discover',status:123,summary:'No supported status.',result_refs:[{...R,hash:'bad'}]}];
const html=GuideMessage.render(p);assert(html.includes('Pending or unknown'));assert(html.includes('data-gm-status="failed"'));
assert(html.includes('data-gm-status="unknown"'));assert(!html.includes('data-gm-status="completed"'));
assert.equal((html.match(/data-ws-artifact=/g)||[]).length,1,'only the separate valid citation remains');
p.sources=[];assert(!GuideMessage.render(p).includes('data-ws-artifact='));
""")

    def test_chat_citations_retain_exact_revision_and_hash_without_latest_substitution(self):
        self.node(r"""
const p=reply();p.sources=[{kind:'workspace_chat_context',chat_id:'chat-other',chat_revision:9,snapshot_hash:'b'.repeat(64),label:'Read selected discussion'}];
const before=JSON.stringify(p),html=GuideMessage.render(p);assert(html.includes('data-ws-citation="chat-other"'));
assert(html.includes('data-ws-revision="9"'));assert(html.includes('data-ws-snapshot="'+'b'.repeat(64)+'"'));
const model=GuideMessage.normalize(p);model.sources[0].chat_revision=99;assert.equal(p.sources[0].chat_revision,9);
assert.equal(JSON.stringify(p),before);p.sources[0].chat_revision=true;assert(!GuideMessage.render(p).includes('data-ws-citation='));
""")

    def test_live_activity_uses_supplied_events_not_model_statements(self):
        self.node(r"""
const p={answer:'I say the operation is complete.',tool_results:[],working_notes:[]};
const html=GuideMessage.render(p,{liveEvents:[{tool:'discover',phase:'started',summary:'Reading the selected sources.',result_refs:[]},
 {tool:'discover',phase:'failed',summary:'The operation stopped.',result_refs:[clone(R)]}]});
assert(html.includes('Recorded activity'));assert(html.includes('data-gm-status="started"'));assert(html.includes('data-gm-status="failed"'));
assert(!html.includes('data-gm-status="completed"'));assert(html.includes('data-ws-version="3"'));
assert(!GuideMessage.render(p).includes('Recorded activity'));
""")

    def test_host_embeds_only_and_unknown_chart_values_do_not_become_zero(self):
        self.node(r"""
const p=reply();p.hostEmbeds=[{type:'html_report',source_ref:R,title:'MODEL EMBED',scope:'not authorized'}];
p.metadata={hostEmbeds:p.hostEmbeds};assert(!GuideMessage.render(p).includes('MODEL EMBED'));
const descriptor={type:'bar_chart',source_ref:R,title:'Saved team outcomes',scope:'This one task; no general effect.',
 rows:[{label:'Intervention',value:3,total:4},{label:'Unknown arm',value:null,total:4},{label:'Missing total',value:2,total:null}]};
const before=JSON.stringify(descriptor),html=GuideMessage.render(p,{hostEmbeds:[descriptor]});
assert(html.includes('3 / 4'));assert(html.includes('2 / Unknown'));assert(html.includes('gm-bar-unknown'));
assert(html.includes('width:75%'));assert(html.includes('This one task'));assert.equal(JSON.stringify(descriptor),before);
assert.equal((html.match(/<i style=/g)||[]).length,1,'unknown value/denominator has no quantitative bar');
descriptor.rows[0].value=true;const bad=GuideMessage.render(p,{hostEmbeds:[descriptor]});assert(bad.includes('chart is unavailable'));assert(!bad.includes('gm-chart-rows'));
""")

    def test_iframe_url_is_host_constructed_exact_and_script_free_sandboxed(self):
        self.node(r"""
const descriptor={type:'html_report',source_ref:clone(R),title:'A real saved report',scope:'Bounded saved study.',
 url:'javascript:ignored',html:'<script>IGNORED MODEL HTML</script>'};
const html=GuideMessage.render(reply(),{hostEmbeds:[descriptor]});
assert(html.includes('<iframe src="/api/guide/report?object_id=experiment-source&amp;version=3&amp;hash='+R.hash+'"'));
assert(html.includes('sandbox=""'));assert(html.includes('loading="lazy"'));assert(html.includes('referrerpolicy="no-referrer"'));
assert(!html.includes('allow-scripts'));assert(!html.includes('allow-same-origin'));assert(!html.includes('javascript:ignored'));
assert(!html.includes('IGNORED MODEL HTML'));descriptor.source_ref.hash='x';
assert(!GuideMessage.render(reply(),{hostEmbeds:[descriptor]}).includes('<iframe'));
descriptor.source_ref=clone(R);descriptor.source_ref.version=3.5;assert(!GuideMessage.render(reply(),{hostEmbeds:[descriptor]}).includes('<iframe'));
""")

    def test_negative_values_and_zero_count_remain_distinct_from_unknown(self):
        self.node(r"""
const rows=[{label:'A',value:-.25},{label:'B',value:0},{label:'C',value:null}];
const html=GuideMessage.render(reply(),{hostEmbeds:[{type:'bar_chart',source_ref:R,title:'Declared report estimates',scope:'Descriptive only.',rows}]});
assert(html.includes('class="negative"'));assert(html.includes('<strong>-0.25</strong>'));
assert(html.includes('<strong>0</strong>'));assert(html.includes('<strong>Unknown</strong>'));
const p={type:'bar_chart',source_ref:R,title:'Wrong count',scope:'Invalid.',rows:[{label:'A',value:5,total:4}]};
assert(!GuideMessage.render(reply(),{hostEmbeds:[p]}).includes('gm-chart-rows'));
""")

    def test_bounds_are_explicit_and_render_has_no_input_mutation(self):
        self.node(r"""
const p=saved(),before=JSON.stringify(p);GuideMessage.render(p);assert.equal(JSON.stringify(p),before);
const model=GuideMessage.normalize(p);model.tools[0].refs[0].version=99;model.sources[0].object_ref.hash='x';
assert.equal(JSON.stringify(p),before);
assert(GuideMessage.markdown('x'.repeat(12001)).includes('exceeds the display bound'));
const many=GuideMessage.render(reply(),{hostEmbeds:Array(7).fill({})});assert(many.includes('Embedded views exceed'));
const output=GuideMessage.markdown(Array(401).fill('<script>x</script>').join('\n'));
assert(output.includes('gm-plain'));assert(!output.includes('<script>'));assert(!output.includes('<table>'));
""")

    def test_styles_are_scoped_responsive_and_accessible(self):
        css = (ROOT / "web" / "guide-message.css").read_text(encoding="utf-8")
        self.assertIn(".gm-html-report iframe", css)
        self.assertIn("@media(max-width:600px)", css)
        self.assertIn("focus-visible", css)
        self.assertIn("prefers-reduced-motion", css)
        self.assertNotIn("@import", css)


if __name__ == "__main__":
    unittest.main()
