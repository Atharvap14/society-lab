"""Pure artifact-map presentation and exact-ref callbacks, with no transport."""
import json
import pathlib
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const input=JSON.parse(fs.readFileSync(0,'utf8'));let calls=0;
const context=vm.createContext({assert,fetch(){calls++;throw Error('No network');},
 setTimeout(){throw Error('No timer jobs');},setInterval(){throw Error('No timer jobs');}});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
vm.runInContext(`
const clone=x=>JSON.parse(JSON.stringify(x));
const A={id:'dataset-source',version:2,hash:'a'.repeat(64)},B={id:'experiment-result',version:3,hash:'b'.repeat(64)},
 C={id:'workspace-draft-copy',version:1,hash:'c'.repeat(64)};
function item(ref,kind,title,extra={}){return {ref:clone(ref),kind,title,summary:'A declared summary.',
 origin:{project_id:'project-one',project_name:'Research project',chat_id:'chat-one',chat_name:'Source discussion'},
 created_at:'2026-10-05T10:00:00+05:30',...extra};}
function packet(){return {artifacts:[item(A,'dataset','Original observations'),
 item(B,'experiment','A completed test',{relation:'created'}),item(C,'workspace_draft','An editable copy',{relation:'copied'})],
 edges:[{from_ref:A,to_ref:B,relation:'reference',label:'Motivating source'},
 {from_ref:B,to_ref:C,relation:'copied',label:'An editable draft; no new empirical authority'}],selected_ref:clone(A)};}
function dom(p){
 const nodes=new Map(),listeners=new Map(),modes=[{dataset:{amMode:'map'},setAttribute(k,v){this[k]=v;}},
 {dataset:{amMode:'list'},setAttribute(k,v){this[k]=v;}}];
 const root={dataset:{amVersion:ArtifactMap.version},matches:s=>s==='.am-root',contains:n=>n?.outside!==true,
 querySelector:s=>nodes.get(s)||null,querySelectorAll:s=>s==='[data-am-mode]'?modes:[],
 addEventListener:(k,f)=>listeners.set(k,f),removeEventListener:(k,f)=>{if(listeners.get(k)===f)listeners.delete(k);}};
 for(const s of ['.am-model','.am-viewport','.am-list','.am-detail','.am-status','[data-am-zoom-label]'])nodes.set(s,
 {textContent:s==='.am-model'?JSON.stringify(p):'',innerHTML:'',hidden:false,scrollLeft:0,scrollTop:0,
 contains:n=>n?.viewportChild===true,classList:{add(){},remove(){}},setPointerCapture(){}});
 function target(data={},selector='',value='',extra={}){return {dataset:data,value,
 closest(){return this;},matches:s=>s===selector,...extra};}
 function fire(name,t,extra={}){const listener=listeners.get(name);if(listener)listener({target:t,preventDefault(){this.prevented=true;},...extra});}
 return {root,nodes,listeners,modes,target,fire};
}
`,context);
(async()=>{await vm.runInContext('(async()=>{'+input.script+'})()',context,{timeout:10000});assert.equal(calls,0);process.stdout.write('PASS');})()
 .catch(e=>{console.error(e);process.exitCode=1;});
"""


class ArtifactMapUITests(unittest.TestCase):
    def node(self, script):
        result = subprocess.run(
            ["node", "-e", NODE, str(ROOT / "web" / "artifact-map.js")],
            input=json.dumps({"script": script}), text=True,
            encoding="utf-8", capture_output=True, timeout=25, cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "PASS")

    def test_exact_versions_links_and_source_declarations_are_not_inferred(self):
        self.node(r"""
const p=packet(),before=JSON.stringify(p);p.artifacts.push(item({...A,version:3},'dataset','A newer saved source'));
const model=ArtifactMap.normalize(p);assert(model.available);assert.equal(model.artifacts.length,4);
assert.equal(model.edges.length,2);assert.equal(model.artifacts[3].ref.version,3);
assert.deepEqual(model.selected_ref,A);assert.equal(model.artifacts[2].capabilities.replay,false);
assert(model.scope.includes('do not describe communication'));
model.artifacts[0].ref.version=99;assert.equal(p.artifacts[0].ref.version,2);
const bare={artifacts:[item(A,'theory','An unreviewed theory',{origin:null,created_at:null,relation:null})],edges:[]};
const html=ArtifactMap.render(bare);assert(html.includes('Origin not declared'));assert(html.includes('0')||html.includes('1 saved versions'));
assert(!html.includes('Motivating source'));assert.equal(ArtifactMap.normalize(bare).edges.length,0);
""")

    def test_parallel_field_references_preserve_distinct_registry_paths(self):
        self.node(r"""
const p=packet();p.edges.push({from_ref:A,to_ref:B,relation:'reference',label:'protocol.source_refs.dataset'});
const model=ArtifactMap.normalize(p);assert(model.available);assert.equal(model.edges.length,3);
assert.deepEqual(model.edges.filter(e=>e.relation==='reference').map(e=>e.label),
 ['Motivating source','protocol.source_refs.dataset']);
p.selected_ref=clone(B);const html=ArtifactMap.render(p);
assert(html.includes('Motivating source'));assert(html.includes('protocol.source_refs.dataset'));
assert.equal(model.artifacts.length,3,'parallel reference fields do not invent extra records');
""")

    def test_malformed_duplicate_or_orphan_data_cannot_create_phantom_map_nodes(self):
        self.node(r"""
const bad=[];
for(const change of [{version:true},{version:2.5},{version:0},{hash:'no-hash'},{id:'../source'}]){
 const p=packet();Object.assign(p.artifacts[0].ref,change);bad.push(p);
}
let p=packet();p.artifacts.push(clone(p.artifacts[0]));bad.push(p);
p=packet();p.edges[0].to_ref={...B,version:4};bad.push(p);
p=packet();p.edges.push(clone(p.edges[0]));bad.push(p);
p=packet();p.selected_ref={...A,hash:'9'.repeat(64)};bad.push(p);
p=packet();p.edges[0].relation='causes';bad.push(p);
p=packet();p.artifacts[0].capabilities={replay:'true'};bad.push(p);
p=packet();p.artifacts[0].created_at='2026-02-30T10:00:00Z';bad.push(p);
p=packet();p.artifacts[0].created_at='2026-10-05T10:00:00';bad.push(p);
p=packet();p.artifacts[0].origin={project_id:'p',unknown_sender:'imagined'};bad.push(p);
p=packet();p.artifacts=Array(ArtifactMap.limits.artifacts+1).fill(p.artifacts[0]);bad.push(p);
p=packet();p.edges=Array(ArtifactMap.limits.edges+1).fill(p.edges[0]);bad.push(p);
for(const q of bad){const before=JSON.stringify(q);assert.equal(ArtifactMap.normalize(q).available,false);
 const html=ArtifactMap.render(q);assert(!html.includes('data-am-index'));assert(!html.includes('am-model'));
 assert.equal(JSON.stringify(q),before);}
""")

    def test_titles_summaries_names_and_embedded_json_cannot_escape_markup(self):
        self.node(r"""
const p=packet();p.artifacts[0].title='</script><img src=x onerror=alert(1)>';
p.artifacts[0].summary='<svg onload=alert(2)>Unverified model prose & "quotation"';
p.artifacts[0].origin.chat_name='<button data-am-action="copy">Bad</button>';
p.edges[0].label='<script>forged()</script>';
const html=ArtifactMap.render(p);assert(html.includes('&lt;img'));assert(html.includes('&lt;svg'));
assert(!html.includes('<img'));assert(!html.includes('<script>forged'));
assert.equal((html.match(/<\/script>/g)||[]).length,1);
const embedded=html.match(/<script type="application\/json" class="am-model">([\s\S]*?)<\/script>/)[1];
const decoded=JSON.parse(embedded);assert.equal(decoded.artifacts[0].title,p.artifacts[0].title);
assert(embedded.includes('\\u003c'));assert(html.includes('not communication or causal influence'));
""")

    def test_action_callbacks_receive_cloned_exact_refs_and_no_implicit_jobs(self):
        self.node(r"""
const p=packet(),before=JSON.stringify(p),d=dom(p),seen=[];
const cleanup=ArtifactMap.attach(d.root,{
 onOpen:r=>{seen.push({action:'open',ref:clone(r)});r.version=99;},
 onReplay:r=>seen.push({action:'replay',ref:r}),onReuse:r=>seen.push({action:'reuse',ref:r}),
 onCopy:r=>seen.push({action:'copy',ref:r})});
assert.equal(seen.length,0,'mounting never starts an operation');
for(const action of ['open','replay','reuse','copy'])d.fire('click',d.target({amAction:action,amIndex:'0'}));
assert.deepEqual(seen.map(s=>s.action),['open','replay','reuse','copy']);
for(const entry of seen)assert.deepEqual(entry.ref,A);
assert.equal(cleanup.getState().selected_ref.version,2);assert.equal(JSON.stringify(p),before);
for(const data of [{amAction:'copy',amIndex:'01'},{amAction:'copy',amIndex:'-1'},
 {amAction:'launch',amIndex:'0'},{amAction:'copy',amIndex:'3'}])d.fire('click',d.target(data));
d.fire('click',d.target({amAction:'copy',amIndex:'0'},'','',{outside:true}));
assert.equal(seen.length,4);cleanup();
""")

    def test_missing_handlers_and_declared_capabilities_withhold_actions(self):
        self.node(r"""
const p=packet();p.artifacts[0].capabilities={copy:false,replay:false};const d=dom(p);let opens=0,copies=0;
const cleanup=ArtifactMap.attach(d.root,{onOpen:()=>opens++,onCopy:()=>copies++});
const detail=d.nodes.get('.am-detail').innerHTML;
assert(/data-am-action="reuse"[^>]*disabled/.test(detail));
assert(/data-am-action="copy"[^>]*disabled/.test(detail));
assert(/data-am-action="replay"[^>]*disabled/.test(detail));
d.fire('click',d.target({amAction:'copy',amIndex:'0'}));assert.equal(copies,0);
d.fire('click',d.target({amAction:'open',amIndex:'0'}));assert.equal(opens,1);
cleanup();
""")

    def test_filters_list_selection_and_zoom_are_local_and_keep_hidden_sources(self):
        self.node(r"""
const p=packet(),before=JSON.stringify(p),d=dom(p),selections=[];
const cleanup=ArtifactMap.attach(d.root,{onSelect:r=>selections.push(r)});
d.fire('input',d.target({},'[data-am-search]','editable copy'));
assert(d.nodes.get('.am-status').textContent.startsWith('1 of 3'));
assert(!d.nodes.get('.am-viewport').innerHTML.includes('Original observations'));
assert.deepEqual(cleanup.getState().selected_ref,A,'filtering does not retarget the saved selection');
d.fire('click',d.target({amMode:'list'}));assert.equal(d.nodes.get('.am-list').hidden,false);
assert.equal(d.nodes.get('.am-viewport').hidden,true);
d.fire('click',d.target({amIndex:'2'}));assert.deepEqual(selections[0],C);
d.fire('input',d.target({},'[data-am-search]',''));
d.fire('change',d.target({},'[data-am-kind]','experiment'));
assert(d.nodes.get('.am-status').textContent.startsWith('1 of 3'));
d.fire('change',d.target({},'[data-am-kind]','unsupported_type'));
assert.equal(cleanup.getState().kind,'experiment');
for(let i=0;i<40;i++)d.fire('click',d.target({amZoom:'in'}));assert.equal(cleanup.getState().zoom,1.6);
for(let i=0;i<40;i++)d.fire('click',d.target({amZoom:'out'}));assert.equal(cleanup.getState().zoom,.55);
d.fire('click',d.target({amZoom:'reset'}));assert.equal(cleanup.getState().zoom,1);
assert.equal(JSON.stringify(p),before);cleanup();
""")

    def test_pan_keyboard_and_teardown_have_bounded_local_lifecycle(self):
        self.node(r"""
const d=dom(packet()),cleanup=ArtifactMap.attach(d.root),viewport=d.nodes.get('.am-viewport');
d.fire('pointerdown',viewport,{button:0,clientX:100,clientY:100,pointerId:1});
d.fire('pointermove',viewport,{clientX:50,clientY:60});assert.equal(viewport.scrollLeft,50);assert.equal(viewport.scrollTop,40);
d.fire('pointerup',viewport);d.fire('pointermove',viewport,{clientX:0,clientY:0});assert.equal(viewport.scrollLeft,50);
d.fire('keydown',viewport,{key:'ArrowRight'});assert.equal(viewport.scrollLeft,120);
const before=cleanup.getState();cleanup();cleanup();assert.equal(d.listeners.size,0);
d.fire('click',d.target({amIndex:'1'}));assert.deepEqual(cleanup.getState(),before);
const invalid=dom(packet());invalid.root.dataset.amVersion='a-different-renderer';
assert.equal(ArtifactMap.attach(invalid.root).getState(),null);assert.equal(invalid.listeners.size,0);
""")

    def test_empty_collection_and_responsive_accessible_fallback_are_explicit(self):
        self.node(r"""
const html=ArtifactMap.render({artifacts:[],edges:[]});
assert(html.includes('0 saved versions'));assert(html.includes('No saved records match'));
assert(!html.includes('data-am-index'));assert(html.includes('type="search"'));assert(html.includes('aria-live="polite"'));
assert(html.includes('tabindex="0"'));assert(html.includes('data-am-mode="list"'));
const d=dom({artifacts:[],edges:[]}),cleanup=ArtifactMap.attach(d.root);assert.equal(cleanup.getState().selected_ref,null);cleanup();
""")
        css = (ROOT / "web" / "artifact-map.css").read_text(encoding="utf-8")
        self.assertIn("@media(max-width:760px)", css)
        self.assertIn("prefers-reduced-motion:reduce", css)
        self.assertIn(":focus-visible", css)
        self.assertIn(".am-root [hidden]", css)


if __name__ == "__main__":
    unittest.main()
