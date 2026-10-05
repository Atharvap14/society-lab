"""Workspace/browser contracts with isolated API and discussion fixtures only.

No fixture reply establishes an agent result, source truth or copied authority.
The actual workspace, experience, journey and replay browser modules execute.
"""
import json
import pathlib
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const input=JSON.parse(fs.readFileSync(0,'utf8')),nodes=new Map(),memory=new Map(),timers=new Map();
let serial=0,transportCalls=0;
function node(){let html='';return {value:'',children:[],dataset:{},textContent:'',disabled:false,scrollHeight:0,
 get innerHTML(){return html;},set innerHTML(v){html=v;this.children=[];},
 classList:{add(){},remove(){},toggle(){}},append(...children){this.children.push(...children);},
 querySelector(s){return get('nested:'+s);},querySelectorAll(){return [];},setAttribute(){},addEventListener(){},
 focus(){},showModal(){this.open=true;},close(){this.open=false;}};}
function get(id){if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);}
const ctx=vm.createContext({assert,URLSearchParams,console,memory,nodes,timers,get,
 document:{body:{dataset:{}},getElementById:get,createElement:()=>node(),querySelector:s=>get('selector:'+s),querySelectorAll:()=>[]},
 sessionStorage:{getItem:k=>memory.get('session:'+k)||null,setItem:(k,v)=>memory.set('session:'+k,v),clear:()=>memory.clear()},
 localStorage:{getItem:k=>memory.get('local:'+k)||null,setItem:(k,v)=>memory.set('local:'+k,v)},
 crypto:{randomUUID:()=> 'request-'+String(++serial).padStart(6,'0')},
 setTimeout:(fn,ms)=>{const id=++serial;timers.set(id,{fn,ms});return id;},clearTimeout:id=>timers.delete(id),
 setInterval:()=>{throw Error('No automatic subject execution permitted');},clearInterval(){},
 fetch:()=>{transportCalls++;throw Error('No external network in workspace UI tests');},scrollTo(){}});
ctx.window=ctx;
for(const name of ['research-journey.js','society-replay.js','artifact-map.js','society-experience.js','lab-workspace.js'])
 vm.runInContext(fs.readFileSync(process.argv[1]+'/web/'+name,'utf8'),ctx,{filename:name});
ctx.APP_SOURCE=fs.readFileSync(process.argv[1]+'/web/app.js','utf8');
vm.runInContext(`
const clone=v=>JSON.parse(JSON.stringify(v)),pin=r=>({id:r.id,version:r.version,hash:r.hash});
const refs={source:{id:'dataset-current',version:1,hash:'a'.repeat(64)},
 old:{id:'dataset-old',version:1,hash:'b'.repeat(64)},newer:{id:'dataset-old',version:2,hash:'c'.repeat(64)},
 brief:{id:'observation-brief-current',version:1,hash:'d'.repeat(64)},
 plan:{id:'guided-plan-current',version:3,hash:'e'.repeat(64)},
 result:{id:'village_recovery_experiment-old',version:1,hash:'f'.repeat(64)},latest:{id:'village_recovery_experiment-old',version:2,hash:'1'.repeat(64)},
 copied:{id:'workspace_draft-copy',version:1,hash:'2'.repeat(64)},copiedNext:{id:'workspace_draft-copy',version:2,hash:'3'.repeat(64)}};
function data(r,content){return {...clone(r),kind:'dataset',created:'2026-10-05T00:00:00Z',summary:{messages:1},
 payload:{source:'isolated-unit-chat.jsonl',messages:[{id:'m-'+r.version,agent_id:'a',agent_name:'Actor',speaker_type:'agent',
 room_id:'team',timestamp:'2025-04-22T18:00:00Z',content,content_hash:'unit-declared-hash'}]}};}
function result(r){const source=clone(refs.old),hypothesis={statement:'Isolated source-grounded reference fixture'},
 fidelity={represented:['One original reference'],approximated:['Account navigation'],omitted:['Historical account state'],historical_equivalence:false};
 return {...clone(r),kind:'village_recovery_experiment',created:'2026-10-05T00:00:00Z',summary:{agent_mode:'live'},
 payload:{agent_mode:'live',status:'complete',source_refs:{dataset_ref:source},hypothesis,fidelity,
 protocol:{environment:{kind:'single_document_reference_repair',agents:['ethics_owner','auditor']},primary_outcome:'verified_repaired_reference',
 grounding:{source_ref:source,evidence_ids:['m-1']},hypothesis,fidelity},analysis:{},runs:[{run_id:'fixture-team',arm:'neutral_note',
 turns:[{step:1,agent_id:'ethics_owner',action:{action:'wait'},tool_result:{ok:true},request:{observation:{messages:[]}}}],
 outcomes:{verified_repaired_reference:0}}]}};}
function defaults(){return [data(refs.source,'Current source'),data(refs.old,'Older exact source'),data(refs.newer,'Latest source'),
 {...clone(refs.brief),kind:'observation_brief',payload:{}},
 {...clone(refs.plan),kind:'guided_plan',payload:{family:'single_document_reference_repair',source_refs:{dataset_ref:clone(refs.source)},question:'Registered question',trials_per_arm:2,max_rounds:8}},
 result(refs.result),result(refs.latest),
 {...clone(refs.copied),kind:'workspace_draft',payload:{name:'Separate editable copy',status:'editable_draft',owner_chat_id:'chat-a',
 copied_empirical_outcomes:false,source_ref:clone(refs.result),editable_fields:{question:'A copied question',notes:'Notes'}}},
 {...clone(refs.copiedNext),kind:'workspace_draft',payload:{name:'Renamed independent draft',status:'editable_draft',owner_chat_id:'chat-a',
 copied_empirical_outcomes:false,source_ref:clone(refs.result),editable_fields:{question:'A copied question',notes:'Updated notes'}}}];}
function working(question,source=refs.source){return {view:'plan',selections:{},context:{dataset_ref:clone(source),brief_ref:clone(refs.brief)},
 plan_draft:{question,control_text:'Neutral '+question,treatment_text:'Intervention '+question},
 ui:{journey:{draft:{question,control_text:'Neutral '+question,treatment_text:'Intervention '+question,
 trials_per_arm:3,max_rounds:4,valid_probability:.4,seed:700},openedStudies:[]},replay:[]}};}
function artifact(r=refs.old){return {ref:clone(r),kind:'dataset',title:'Older exact source',summary:'Saved source',
 relation:'reference',origin_chat_id:'chat-b',created:'2026-10-05T00:00:00Z'};}
function target(attrs={},value='',id=''){const dataset={};for(const[k,v]of Object.entries(attrs))if(k.startsWith('data-'))dataset[k.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=v;return {id,value,dataset,hasAttribute:k=>Object.hasOwn(attrs,k)};}
function hold(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
async function settle(){for(let i=0;i<15;i++)await Promise.resolve();}
function setup(){
 memory.clear();nodes.clear();timers.clear();const records=defaults(),log={requests:[],reads:[],opens:[],jobs:[],renders:[],toasts:[]};
 const snapshots={
 'chat-a':{id:'chat-a',project_id:'project-a',name:'First discussion',revision:4,state:working('Question A'),
 messages:[{id:'discussion-a',sequence:1,role:'user',content:'First chat history',metadata:{}}],artifacts:[artifact()]},
 'chat-b':{id:'chat-b',project_id:'project-b',name:'Second discussion',revision:7,state:working('Question B',refs.newer),
 messages:[{id:'discussion-b',sequence:1,role:'user',content:'Second chat history',metadata:{}}],artifacts:[artifact()]}};
 const index={default_chat_id:'chat-a',projects:[{id:'project-a',name:'First project',chats:[{id:'chat-a',name:'First discussion',revision:4}]},
 {id:'project-b',name:'Second project',chats:[{id:'chat-b',name:'Second discussion',revision:7}]}]};
 const app={view:'workspace',state:{csrf:'unit-csrf',jobs:[],objects:records.filter(r=>![refs.old,refs.result,refs.copied].some(p=>p.id===r.id&&p.version===r.version))},selected:{}};
 const b={app,esc:v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),
 all:kind=>app.state.objects.filter(r=>r.kind===kind),object:async(id,version)=>{log.reads.push({id,version});const r=records.find(r=>r.id===id&&r.version===version);if(!r)throw Error('Missing exact fixture');return clone(r);},
 render:async()=>log.renders.push({chat:app.activeChatId,view:app.view}),refresh:async()=>{},
 submit:async(action,args)=>{log.jobs.push({action,args});throw Error('No study jobs in workspace tests');},
 toast:(text,error)=>log.toasts.push({text,error}),openObject:async(id,version)=>log.opens.push({id,version}),
 api:async(path,options={})=>{const request={path,method:options.method||'GET',headers:clone(options.headers||{}),body:options.body?JSON.parse(options.body):null};log.requests.push(request);
  if(b.handle){const response=b.handle(request);if(response!==undefined)return response;}
  if(path==='/api/workspaces'&&request.method==='GET')return clone(index);
  if(path.startsWith('/api/workspaces/chat?'))return clone(snapshots[new URLSearchParams(path.split('?')[1]).get('chat_id')]);
  if(path.startsWith('/api/workspaces/context?')){const c=snapshots[new URLSearchParams(path.split('?')[1]).get('chat_id')];return {...clone(c),snapshot_hash:'8'.repeat(64),scope:'Bounded discussion, not experimental evidence'};}
  if(path.startsWith('/api/workspaces/artifacts?'))return {artifacts:[
   {...artifact(refs.old),origin_chat_id:undefined,origin:{project_id:'project-b',project_name:'Second project',chat_id:'chat-b',chat_name:'Second discussion'}},
   {...artifact(refs.result),kind:'village_recovery_experiment',title:'Older source-grounded test',origin_chat_id:undefined,origin:{project_id:'project-b',project_name:'Second project',chat_id:'chat-b',chat_name:'Second discussion'}}],
   edges:[{from_ref:clone(refs.old),to_ref:clone(refs.result),relation:'recorded_reference',label:'source_refs.dataset'}],total:2,truncated:false};
  if(path==='/api/workspaces'&&request.method==='POST'){
   const body=request.body;
   if(body.op==='save_state'){const s=snapshots[body.chat_id];if(s.revision!==body.expected_revision)throw Error('Fixture revision conflict');s.state=clone(body.state);s.revision++;return {chat:clone(s)};}
   if(body.op==='reuse_artifact')return {artifact_ref:clone(body.artifact_ref),chat:clone(snapshots[body.target_chat_id])};
   if(body.op==='clone_artifact')return {artifact_ref:clone(refs.copied),chat:clone(snapshots[body.target_chat_id])};
   if(body.op==='update_draft')return {artifact_ref:clone(refs.copiedNext),chat:clone(snapshots[body.chat_id])};
  }
  if(path==='/api/guide/chat')return {answer_source:'ai',answer:'Unit guide reply',actions:[],sources:[]};
  throw Error('Unexpected fixture route '+path);
 }};
 b.experience=SocietyExperience.create(b);const workspace=LabWorkspace.create(b);app.workspace=workspace;
 return {b,workspace,experience:b.experience,log,snapshots,records,index};
}
`,ctx);
(async()=>{await vm.runInContext('(async()=>{'+input.script+'})()',ctx,{timeout:10000});assert.equal(transportCalls,0);process.stdout.write('PASS');})()
 .catch(error=>{console.error(error);process.exitCode=1;});
"""


class LabWorkspaceUITests(unittest.TestCase):
    def node(self, script):
        result = subprocess.run(
            ["node", "-e", NODE, str(ROOT)], input=json.dumps({"script": script}),
            text=True, encoding="utf-8", capture_output=True, timeout=25, cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "PASS")

    def test_chat_drafts_and_source_pins_roundtrip_without_aliases(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();assert.equal(env.b.app.activeChatId,'chat-a');
assert.equal(env.experience.state.draft.question,'Question A');
env.experience.input(target({'data-journey-field':'question'},'Edited question A','journey-question'));
env.workspace.notify();await env.workspace.flush();
assert.equal(env.snapshots['chat-a'].state.plan_draft.question,'Edited question A');
assert.equal(env.snapshots['chat-a'].state.ui.journey.draft.seed,700);
const exported=env.experience.exportWorkspaceState();exported.context.dataset_ref.version=99;
assert.deepEqual(env.experience.state.project,refs.source);
await env.workspace.loadChat('chat-b');assert.equal(env.b.app.activeChatId,'chat-b');
assert.equal(env.experience.state.draft.question,'Question B');assert.deepEqual(env.experience.state.project,refs.newer);
env.experience.input(target({'data-journey-field':'question'},'Edited question B','journey-question'));
env.workspace.notify();await env.workspace.flush();await env.workspace.loadChat('chat-a');
assert.equal(env.experience.state.draft.question,'Edited question A');assert.deepEqual(env.experience.state.project,refs.source);
assert.equal(env.snapshots['chat-b'].state.plan_draft.question,'Edited question B');
assert.equal(env.log.jobs.length,0);assert(!env.log.requests.some(r=>r.path.startsWith('/api/guided/')));
""")

    def test_old_exact_source_and_result_replays_do_not_overwrite_draft_or_connected_source(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();
env.experience.state.planRef=clone(refs.plan);const draft=JSON.stringify(env.experience.state.draft),source=clone(env.experience.state.project);
await env.workspace.click(target({'data-ws-artifact':refs.old.id,'data-ws-version':String(refs.old.version),'data-ws-hash':refs.old.hash}));
let html=await env.experience.render('watch');assert(html.includes('Older exact source'));
assert.deepEqual(env.experience.state.previewWatch,refs.old);assert.deepEqual(env.experience.state.project,source);
assert.equal(JSON.stringify(env.experience.state.draft),draft);assert.deepEqual(env.experience.state.planRef,refs.plan);
assert(env.log.reads.some(r=>r.id===refs.old.id&&r.version===1));assert(!env.log.reads.some(r=>r.id===refs.old.id&&r.version===2));
await env.experience.openSavedArtifact(env.records.find(r=>r.id===refs.result.id&&r.version===1),'replay');
html=await env.experience.render('watch');assert(html.includes('SAVED TEAM TEST'));
assert.deepEqual(env.experience.state.watchStudy,refs.result);assert.equal(JSON.stringify(env.experience.state.draft),draft);
assert.deepEqual(env.experience.state.project,source);assert.deepEqual(env.experience.state.planRef,refs.plan);
assert(env.log.reads.some(r=>r.id===refs.result.id&&r.version===1));assert.equal(env.log.jobs.length,0);
const unrelated={...clone(refs.result),id:'experiment-independent-fixture',kind:'experiment',payload:{agent_mode:'live',status:'complete'}};
await assert.rejects(()=>env.experience.openSavedArtifact(unrelated,'replay'),/source-grounded AI Village/);
assert.deepEqual(env.experience.state.watchStudy,refs.result);assert.equal(JSON.stringify(env.experience.state.draft),draft);
""")

    def test_cross_chat_read_does_not_switch_active_chat_and_reuse_is_exact(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();const before=env.experience.exportWorkspaceState();
await env.workspace.showContext('chat-b');
assert.equal(env.b.app.activeChatId,'chat-a');assert.equal(env.workspace.state.chat.id,'chat-a');
assert.deepEqual(env.experience.exportWorkspaceState(),before);
assert.equal(env.workspace.state.contextPreview.id,'chat-b');
const guideRequests=[];env.experience.ask=async(message,options)=>guideRequests.push({message,options});
await env.workspace.click(target({'data-ws-reuse':refs.old.id,'data-ws-version':'1','data-ws-hash':refs.old.hash,'data-ws-origin':'chat-b'}));
assert.equal(guideRequests.length,1);assert(guideRequests[0].message.startsWith('Reuse'));
assert.deepEqual(guideRequests[0].options.mentioned_context,[{kind:'artifact',ref:refs.old,origin_chat_id:'chat-b'}]);
assert(!env.log.requests.some(r=>r.body?.op==='reuse_artifact'),'human intent must go to the agent before mutation');
assert.equal(env.b.app.activeChatId,'chat-a');assert.deepEqual(env.experience.state.project,refs.source);
assert.equal(env.log.jobs.length,0);
""")

    def test_copy_is_a_separate_editable_record_and_save_uses_returned_exact_version(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();const source=clone(env.experience.state.project),draft=JSON.stringify(env.experience.state.draft);
await env.workspace.applyGuideAction({type:'clone_artifact',artifact_ref:refs.result,origin_chat_id:'chat-b',target_chat_id:'chat-a'});
const req=env.log.requests.find(r=>r.body?.op==='clone_artifact');assert.deepEqual(req.body.artifact_ref,refs.result);
assert.equal(req.body.origin_chat_id,'chat-b');assert.equal(req.body.target_chat_id,'chat-a');
assert.deepEqual(pin(env.workspace.state.copy),refs.copied);assert.equal(env.b.app.view,'workspace-copy');
assert.equal(env.workspace.state.copy.kind,'workspace_draft');assert.equal(env.workspace.state.copy.payload.copied_empirical_outcomes,false);
assert.equal(JSON.stringify(env.experience.state.draft),draft);assert.deepEqual(env.experience.state.project,source);
get('ws-copy-name').value='Renamed independent draft';get('ws-copy-notes').value='Updated notes';
get('ws-copy-question').value='A copied question';get('ws-copy-control').value='Neutral';get('ws-copy-treatment').value='Intervention';
await env.workspace.submit({target:{id:'ws-copy-form'},preventDefault(){}});
assert.deepEqual(pin(env.workspace.state.copy),refs.copiedNext);
const saved=env.log.requests.find(r=>r.body?.op==='update_draft');assert.deepEqual(saved.body.draft_ref,refs.copied);
assert.equal(saved.body.chat_id,'chat-a');assert.equal(env.log.jobs.length,0);
""")

    def test_cas_conflict_keeps_local_draft_and_does_not_overwrite_remote_work(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();
env.experience.input(target({'data-journey-field':'question'},'Uncommitted local edit','journey-question'));
env.workspace.notify();env.snapshots['chat-a'].revision=8;
env.snapshots['chat-a'].state=working('Other window question');
await assert.rejects(()=>env.workspace.flush(),/changed in another window/);
assert.equal(env.experience.state.draft.question,'Uncommitted local edit');
assert.equal(env.snapshots['chat-a'].state.plan_draft.question,'Other window question');
assert.equal(env.workspace.state.conflict,true);assert.equal(env.workspace.state.dirty,true);
assert.equal(env.log.requests.filter(r=>r.body?.op==='save_state').length,1);
assert.equal(env.log.requests.find(r=>r.body?.op==='save_state').body.expected_revision,4);
assert.equal(env.log.jobs.length,0);
""")

    def test_chat_switch_rejects_late_guide_reply_and_preserves_new_pending_request(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();const old=hold(),current=hold();
env.b.handle=req=>req.path==='/api/guide/chat'?(req.body.active_chat_id==='chat-a'?old.promise:current.promise):undefined;
const oldReply=env.experience.ask('An old question');await settle();
const req=env.log.requests.find(r=>r.path==='/api/guide/chat');
assert.equal(req.headers['X-Lab-Chat'],'chat-a');assert.equal(req.body.active_chat_id,'chat-a');
assert.equal(typeof req.body.request_id,'string');
await env.workspace.loadChat('chat-b');assert.equal(env.experience.state.guideBusy,false);
const newReply=env.experience.ask('Current question');await settle();
assert.equal(env.experience.state.guideBusy,true);
old.resolve({answer_source:'ai',answer:'OLD REPLY MUST NOT PAINT',plan_draft:{question:'OLD MUTATION'},
 actions:[{id:'nav',type:'navigate',view:'findings'}],sources:[]});
const answer=await oldReply;assert.equal(answer.stale_context,true);
assert.equal(env.experience.state.guideBusy,true,'old finally must not unlock the newer request');
assert.equal(env.b.app.activeChatId,'chat-b');assert.equal(env.experience.state.draft.question,'Question B');
assert(!env.experience.state.chat.some(r=>r.text?.includes('OLD REPLY')));
assert(!env.experience.state.guideHistory.some(r=>r.content.includes('OLD REPLY')));
current.resolve({answer_source:'ai',answer:'CURRENT REPLY',actions:[],sources:[]});await newReply;
assert.equal(env.experience.state.guideBusy,false);assert.equal(env.b.app.activeChatId,'chat-b');assert.equal(env.log.jobs.length,0);
""")

    def test_production_api_captures_origin_header_before_async_completion(self):
        self.node(r"""
const match=APP_SOURCE.match(/^async function api\(path, settings=\{\}\).*$/m);
assert(match,'capture the production api definition, not a reimplemented shim');
const app={activeChatId:'chat-a'},pending=hold(),sent=[];
const response={ok:true,json:async()=>({ok:true})};
const fetch=(path,options)=>{sent.push({path,options:clone(options)});return pending.promise;};
const actual=Function('app','fetch',match[0]+'; return api;')(app,fetch);
const caller={method:'POST',headers:{'Content-Type':'application/json','X-Lab-Token':'fixture-csrf'},body:'{}'};
const result=actual('/api/jobs',caller);app.activeChatId='chat-b';pending.resolve(response);await result;
assert.equal(sent[0].options.headers['X-Lab-Chat'],'chat-a');assert.equal(caller.headers['X-Lab-Chat'],undefined);
await actual('/api/workspaces',{method:'POST',headers:{'X-Lab-Chat':'chat-a'},body:'{}'});
assert.equal(sent[1].options.headers['X-Lab-Chat'],'chat-a','explicit captured origin wins over current UI chat');
""")

    def test_pending_save_finishes_newer_local_edit_before_switching_chat(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();const pending=hold();let first=true;
env.b.handle=req=>{
 if(req.body?.op==='save_state'&&first){first=false;return pending.promise;}
};
env.experience.input(target({'data-journey-field':'question'},'First pending edit','journey-question'));
env.workspace.notify();const saving=env.workspace.flush();await settle();
assert.equal(env.workspace.state.saving,true);
env.experience.input(target({'data-journey-field':'question'},'Newer edit during pending save','journey-question'));
env.workspace.notify();const switching=env.workspace.loadChat('chat-b');await settle();
assert.equal(env.b.app.activeChatId,'chat-a','switch must await prior chat state publication');
assert(!env.log.requests.some(r=>r.path.includes('/chat?chat_id=chat-b')));
const req=env.log.requests.find(r=>r.body?.op==='save_state');
env.snapshots['chat-a'].state=clone(req.body.state);env.snapshots['chat-a'].revision++;
pending.resolve({chat:clone(env.snapshots['chat-a'])});await Promise.all([saving,switching]);
assert.equal(env.b.app.activeChatId,'chat-b');assert.equal(env.experience.state.draft.question,'Question B');
assert.equal(env.snapshots['chat-a'].state.plan_draft.question,'Newer edit during pending save');
const requests=env.log.requests.filter(r=>r.body?.op==='save_state');
assert.equal(requests.length,2);assert.deepEqual(requests.map(r=>r.body.chat_id),['chat-a','chat-a']);
assert.deepEqual(requests.map(r=>r.body.expected_revision),[4,5]);assert.equal(env.workspace.state.dirty,false);
assert.equal(env.log.jobs.length,0);
""")

    def test_pending_copy_keeps_captured_target_and_cannot_open_in_another_chat(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();const pending=hold();
env.b.handle=req=>req.body?.op==='clone_artifact'?pending.promise:undefined;
const action={type:'clone_artifact',artifact_ref:refs.result,origin_chat_id:'chat-b',target_chat_id:'chat-a'};
const copying=env.workspace.applyGuideAction(action);await settle();
assert.equal(env.workspace.state.operation,true);await env.workspace.applyGuideAction(action);
assert.equal(env.log.requests.filter(r=>r.body?.op==='clone_artifact').length,1,'pending clone must not repeat');
await env.workspace.loadChat('chat-b');const draft=JSON.stringify(env.experience.state.draft);
const renders=env.log.renders.length;pending.resolve({artifact_ref:clone(refs.copied),chat:clone(env.snapshots['chat-a'])});await copying;
const req=env.log.requests.find(r=>r.body?.op==='clone_artifact');
assert.equal(req.body.target_chat_id,'chat-a');assert.equal(req.body.origin_chat_id,'chat-b');
assert.deepEqual(req.body.artifact_ref,refs.result);
assert.equal(env.b.app.activeChatId,'chat-b');assert.equal(env.workspace.state.copy,null);
assert.notEqual(env.b.app.view,'workspace-copy');assert.equal(env.log.renders.length,renders);
assert.equal(JSON.stringify(env.experience.state.draft),draft);assert.equal(env.workspace.state.operation,false);
assert.equal(env.log.jobs.length,0);
""")

    def test_catalog_origin_and_registry_edge_shape_enable_exact_actions_without_new_records(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();env.workspace.state.scope='all';
const original=env.b.api;env.b.handle=request=>request.path.startsWith('/api/workspaces/artifacts?')?{artifacts:[
 {...artifact(refs.old),origin:{chat_id:'chat-b',chat_name:'Second discussion',project_id:'project-b',project_name:'Second project'}},
 {...artifact(refs.result),kind:'village_recovery_experiment',title:'Source-grounded result',origin:{chat_id:'chat-b',chat_name:'Second discussion',project_id:'project-b',project_name:'Second project'}},
 {...artifact({id:'experiment-independent-fixture',version:1,hash:'9'.repeat(64)}),kind:'experiment',title:'Unrelated independent test'}],
 edges:[{from_ref:refs.old,to_ref:refs.result,relation:'recorded_reference',label:'source_refs.dataset'},
 {from_ref:refs.old,to_ref:{id:'experiment-independent-fixture',version:1,hash:'9'.repeat(64)},relation:'recorded_reference',label:'unrelated'}]}:undefined;
const html=await env.workspace.render('artifacts');
const embedded=html.match(/<script type="application\/json" class="am-model">([\s\S]*?)<\/script>/);
assert(embedded,'actual catalog packet should render the map, not an unavailable fallback');
const p=JSON.parse(embedded[1]);assert.equal(p.artifacts.length,2);assert.equal(p.edges.length,1);
assert.deepEqual(p.artifacts[0].ref,refs.old);assert.equal(p.artifacts[0].origin.chat_id,'chat-b');
assert.equal(p.artifacts[0].capabilities.reuse,true);assert.equal(p.artifacts[0].capabilities.copy,true);
assert.equal(p.edges[0].relation,'reference');assert.equal(p.edges[0].label,'source_refs.dataset');
assert.deepEqual(p.edges[0].from_ref,refs.old);assert.deepEqual(p.edges[0].to_ref,refs.result);
assert(!html.includes('Unrelated independent test'));assert(!p.artifacts.some(a=>a.kind==='experiment'));
assert(!env.log.requests.some(r=>r.method==='POST'));assert.equal(env.log.jobs.length,0);
""")

    def test_exact_chat_citation_requests_saved_revision_and_rejects_fingerprint_mismatch(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();const before=env.experience.exportWorkspaceState();
await env.workspace.showContext({chat_id:'chat-b',chat_revision:7,snapshot_hash:'8'.repeat(64)});
const requested=env.log.requests.find(r=>r.path.startsWith('/api/workspaces/context?'));
const params=new URLSearchParams(requested.path.split('?')[1]);assert.equal(params.get('chat_id'),'chat-b');
assert.equal(params.get('revision'),'7');const previous=clone(env.workspace.state.contextPreview);
await assert.rejects(()=>env.workspace.showContext({chat_id:'chat-b',chat_revision:6,snapshot_hash:'9'.repeat(64)}),/fingerprint/);
assert.deepEqual(env.workspace.state.contextPreview,previous);
assert.deepEqual(env.experience.exportWorkspaceState(),before);assert.equal(env.b.app.activeChatId,'chat-a');
assert(!env.log.requests.some(r=>r.method==='POST'));assert.equal(env.log.jobs.length,0);
""")

    def test_guide_artifact_mutation_uses_backend_compatible_idempotency_identifier(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();
env.b.handle=req=>req.path==='/api/guide/chat'?{
 answer_source:'ai',answer:'Reusing the requested exact source.',sources:[],actions:[
 {id:'reuse-source',type:'reuse_artifact',artifact_ref:refs.old,origin_chat_id:'chat-b',target_chat_id:'chat-a'}]}:undefined;
await env.experience.ask('Reuse the older source from the second discussion here.');
const guide=env.log.requests.find(r=>r.path==='/api/guide/chat');
const mutation=env.log.requests.find(r=>r.body?.op==='reuse_artifact');assert(mutation);
assert(/^[A-Za-z0-9][A-Za-z0-9_.-]{0,199}$/.test(mutation.body.request_id),
 'workspace backend rejects colon and overlong request IDs');
assert.notEqual(mutation.body.request_id,guide.body.request_id,'action has distinct deterministic request identity');
assert.equal(mutation.body.target_chat_id,'chat-a');assert.deepEqual(mutation.body.artifact_ref,refs.old);
assert.equal(env.log.requests.filter(r=>r.body?.op==='reuse_artifact').length,1);assert.equal(env.log.jobs.length,0);
""")

    def test_unsaved_copy_input_survives_refresh_render_and_chat_roundtrip_without_authority_change(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();
await env.workspace.click(target({'data-ws-artifact':refs.copied.id,'data-ws-version':'1','data-ws-hash':refs.copied.hash}));
env.workspace.input(target({},'Unsaved copy name','ws-copy-name'));
env.workspace.input(target({},'Unsaved <private> notes','ws-copy-notes'));
env.workspace.input(target({},'Unsaved copy question','ws-copy-question'));
await env.workspace.refreshChat();let html=await env.workspace.render('workspace-copy');
assert(html.includes('value="Unsaved copy name"'));assert(html.includes('Unsaved &lt;private&gt; notes'));
assert(html.includes('Unsaved copy question'));assert.deepEqual(pin(env.workspace.state.copy),refs.copied);
assert.equal(env.workspace.state.copy.payload.editable_fields.question,'A copied question','editing does not mutate saved scientific authority');
env.workspace.notify();await env.workspace.flush();await env.workspace.loadChat('chat-b');await env.workspace.loadChat('chat-a');
html=await env.workspace.render('workspace-copy');assert(html.includes('Unsaved copy question'));
assert(html.includes('Unsaved &lt;private&gt; notes'));assert.deepEqual(pin(env.workspace.state.copy),refs.copied);
env.workspace.input(target({},'','ws-copy-question'));env.workspace.input(target({},'','ws-copy-notes'));
html=await env.workspace.render('workspace-copy');
assert(/id="ws-copy-question"[^>]*><\/textarea>/.test(html),'blank editing must retain the recoverable question control');
assert(/id="ws-copy-notes"[^>]*><\/textarea>/.test(html));assert(!html.includes('Unsaved copy question'));
assert(!env.log.requests.some(r=>r.body?.op==='update_draft'));assert.equal(env.log.jobs.length,0);
""")

    def test_pending_copy_save_does_not_overwrite_other_chat_copy_or_view(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();
await env.workspace.click(target({'data-ws-artifact':refs.copied.id,'data-ws-version':'1','data-ws-hash':refs.copied.hash}));
get('ws-copy-name').value='Renamed independent draft';get('ws-copy-notes').value='Updated notes';
get('ws-copy-question').value='A copied question';const pending=hold();
env.b.handle=req=>req.body?.op==='update_draft'?pending.promise:undefined;
const saving=env.workspace.submit({target:{id:'ws-copy-form'},preventDefault(){}});await settle();
await env.workspace.loadChat('chat-b');const renders=env.log.renders.length;
pending.resolve({artifact_ref:clone(refs.copiedNext),chat:clone(env.snapshots['chat-a'])});await saving;
const req=env.log.requests.find(r=>r.body?.op==='update_draft');assert.equal(req.body.chat_id,'chat-a');
assert.deepEqual(req.body.draft_ref,refs.copied);assert.equal(env.b.app.activeChatId,'chat-b');
assert.equal(env.workspace.state.copy,null);assert.notEqual(env.b.app.view,'workspace-copy');
assert.equal(env.log.renders.length,renders,'old mutation completion should not redraw the new chat');
assert.equal(env.experience.state.draft.question,'Question B');assert.equal(env.log.jobs.length,0);
""")


    def test_fixture_entries_and_their_edges_are_excluded_without_hiding_log_candidates(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();env.workspace.state.scope='all';
const example={...artifact(refs.result),kind:'behavior',title:'Authored toy example',fixture:true};
const actual={...artifact(refs.old),kind:'behavior',title:'Source-linked candidate',fixture:false};
env.b.handle=req=>req.path.startsWith('/api/workspaces/artifacts?')?{artifacts:[example,actual],edges:[
 {from_ref:refs.old,to_ref:refs.result,relation:'recorded_reference',label:'excluded fixture edge'}],total:2,truncated:false}:undefined;
const before=JSON.stringify(env.experience.state.draft),html=await env.workspace.render('artifacts');
const embedded=html.match(/<script type="application\/json" class="am-model">([\s\S]*?)<\/script>/);
assert(embedded);const packet=JSON.parse(embedded[1]);assert.equal(packet.artifacts.length,1);
assert.equal(packet.artifacts[0].title,'Source-linked candidate');assert.deepEqual(packet.artifacts[0].ref,refs.old);
assert.equal(packet.edges.length,0);assert(!html.includes('Authored toy example'));
assert.equal(JSON.stringify(env.experience.state.draft),before);
assert(!env.log.requests.some(r=>r.method==='POST'));assert.equal(env.log.jobs.length,0);
""")

    def test_cited_message_opens_its_exact_moment_without_retargeting_draft(self):
        self.node(r"""
const env=setup();await env.workspace.initialize();
const before=JSON.stringify(env.experience.state.draft),source=clone(env.experience.state.project);
await env.workspace.click(target({'data-ws-artifact':refs.old.id,'data-ws-version':'1','data-ws-hash':refs.old.hash,'data-ws-message':'m-1'}));
assert.equal(env.b.app.view,'watch');assert.deepEqual(env.experience.state.previewWatch,refs.old);
const html=await env.experience.render('watch');assert(html.includes('Older exact source'));
assert.equal(SocietyReplay.peek(env.experience.state.replayRecord,env.experience.state.replayStates.get(env.experience.state.replayKey)).current_message.id,'m-1');
assert.equal(JSON.stringify(env.experience.state.draft),before);assert.deepEqual(env.experience.state.project,source);
await assert.rejects(()=>env.experience.openSavedArtifact(env.records.find(r=>r.id===refs.old.id&&r.version===1),'open','absent-message'),/unavailable/);
assert.equal(env.log.jobs.length,0);
""")

if __name__ == "__main__":
    unittest.main()
