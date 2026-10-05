"""Actual journey UI, isolated transport fixtures; no providers or saved studies.

These tests execute the production browser modules in Node. Their API replies
are transport fixtures, not evidence of agent performance or scientific fit.
"""
import json
import pathlib
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const nodes=new Map(),memory=new Map();let networkCalls=0;
function element(){return {value:'',textContent:'',innerHTML:'',children:[],dataset:{},
 classList:{add(){},remove(){},toggle(){}},append(...a){this.children.push(...a);},
 setAttribute(){},addEventListener(){},focus(){},scrollTop:0,scrollHeight:0,
 querySelector(){return element();}};}
const context=vm.createContext({assert,
 document:{body:{dataset:{}},getElementById:id=>{if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);},
  createElement:()=>element(),querySelector:()=>null,querySelectorAll:()=>[]},
 sessionStorage:{getItem:k=>memory.get(k)||null,setItem:(k,v)=>memory.set(k,v),clear:()=>memory.clear()},
 fetch:()=>{networkCalls++;throw Error('Network forbidden in UI unit tests');},
 setTimeout:()=>{throw Error('No automatic timer expected');},clearTimeout(){},
 setInterval:()=>{throw Error('No automatic subject launch timer');},clearInterval(){},
 scrollTo(){},console
});context.window=context;
for(const file of ['research-journey.js','society-experience.js'])
 vm.runInContext(fs.readFileSync(process.argv[1]+'/'+file,'utf8'),context,{filename:file});
vm.runInContext(`
const clone=v=>JSON.parse(JSON.stringify(v));
const pin=r=>({id:r.id,version:r.version,hash:r.hash});
const P={
 dataset:{id:'dataset-ui-source',version:3,hash:'a'.repeat(64)},
 brief:{id:'observation-brief-ui',version:2,hash:'b'.repeat(64)},
 discovery:{id:'discovery-ui-source',version:4,hash:'c'.repeat(64)},
 plan:{id:'guided-plan-ui',version:2,hash:'d'.repeat(64)},
 simulator:{id:'guided-simulator-ui',version:1,hash:'e'.repeat(64)},
 execution:{id:'guided-result-ui',version:1,hash:'f'.repeat(64)},
 result:{id:'experiment-ui-live',version:1,hash:'1'.repeat(64)},
 proof:{id:'verification-ui',version:2,hash:'2'.repeat(64)},
 claims:{id:'claim-audit-ui',version:1,hash:'3'.repeat(64)}
};
function record(p,kind,payload,summary={}){return {...clone(p),kind,payload,summary};}
function defaults(){return [
 record(P.dataset,'dataset',{messages:[{id:'post-ui',content:'Check the file.',speaker_type:'agent'}],
  provenance:{origin:'imported'},source:'saved-original.jsonl'},{messages:1}),
 record(P.brief,'observation_brief',{counts:{agent_messages:1,known_agents:1,task_ids:0},signals:[],agents:[]}),
 record(P.discovery,'discovery',{dataset_ref:clone(P.dataset),dataset_id:P.dataset.id,candidates:[]}),
 record(P.plan,'guided_plan',{question:'Does checking improve correct publication?',
  control_text:'An ordinary neutral note.',treatment_text:'Inspect before publication.',trials_per_arm:2,max_rounds:6}),
 record(P.simulator,'guided_simulator',{plan_ref:clone(P.plan),boundary_checks:{passed:true},
  builder_proposal:{omitted_capabilities:[]},causal_review:{}}),
 record(P.execution,'guided_result',{result_ref:clone(P.result),plan_ref:clone(P.plan),
  simulator_ref:clone(P.simulator),source_brief_ref:clone(P.brief),
  verification_ref:clone(P.proof),claims_ref:clone(P.claims)}),
 record(P.result,'experiment',{agent_mode:'live',runs:[],analysis:{}},{agent_mode:'live'}),
 record(P.proof,'verification',{passed:true}),
 record(P.claims,'claim_audit',{audit:{all_executable_claims_supported:true}})
 ];}
function target(attrs={},value='',id=''){
 const dataset={};for(const [key,v]of Object.entries(attrs))if(key.startsWith('data-'))
  dataset[key.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=v;
 return {dataset,value,id,hasAttribute:k=>Object.hasOwn(attrs,k),getAttribute:k=>attrs[k]};
}
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
async function settle(){for(let i=0;i<12;i++)await Promise.resolve();}
function setup(options={}){
 sessionStorage.clear();const records=clone(options.records||defaults());
 const log={requests:[],jobs:[],renders:[],reads:[],opens:[],toasts:[],refreshes:0};
 const state={csrf:'fixture-token',jobs:[],objects:records.map(r=>clone(r)),usage:{calls:0,max_calls:400}};
 const app={view:'connect',live:false,state};
 const b={app,all:kind=>state.objects.filter(r=>r.kind===kind),
  object:async(id,version)=>{log.reads.push({id,version});const r=records.find(r=>r.id===id&&(version===undefined||r.version===version));if(!r)throw Error('Missing fixture source');return clone(r);},
  api:async(path,options={})=>{const body=options.body?JSON.parse(options.body):null;log.requests.push({path,body,method:options.method||'GET'});
   if(b.handle)return b.handle(path,body);
   if(path==='/api/observability/brief')return {brief_ref:clone(P.brief),dataset_ref:clone(P.dataset),discovery_ref:clone(P.discovery)};
   if(path==='/api/guided/plan')return {plan_ref:clone(P.plan)};
   if(path==='/api/guided/simulator')return {simulator_ref:clone(P.simulator)};
   if(path==='/api/guided/run')return {execution_ref:clone(P.execution),result_ref:clone(P.result)};
   if(path==='/api/guide/chat')return {answer_source:'ai',answer:'The source supports a question, not a mechanism.',actions:[],sources:[]};
   throw Error('Unexpected fixture route '+path);
  },
  submit:async(action,args)=>{log.jobs.push({action,args:clone(args)});return {job_id:'research-fixture-job'};},
  refresh:async()=>{log.refreshes++;},render:async()=>{log.renders.push(app.view);if(b.failRender)throw Error('Fixture render failure');},
  toast:(message,error)=>log.toasts.push({message,error}),openObject:async(id,version)=>log.opens.push({id,version})};
 const ui=SocietyExperience.create(b);return {b,ui,log,records};
}
async function connect(env){await env.ui.render('connect');await env.ui.click(target({'data-journey-connect':''}));await settle();}
function guided(log){return log.requests.filter(r=>r.path.startsWith('/api/guided/'));}
`,context);
(async()=>{await vm.runInContext('(async()=>{'+input.script+'})()',context,{timeout:10000});
 assert.equal(networkCalls,0);process.stdout.write('PASS');})().catch(error=>{console.error(error);process.exitCode=1;});
"""


class ResearchJourneyUITests(unittest.TestCase):
    def test_new_world_receipt_keeps_frozen_plan_distinct_from_unsent_draft(self):
        self.node(r"""
const env=setup();env.b.app.view='plan';
env.ui.state.planRef=clone(P.plan);env.ui.state.draft.question='My separate unfinished question';
const before=JSON.stringify(env.ui.state.draft);
env.b.handle=()=>({answer_source:'ai',answer:'The world is ready.',
 updated_context:{simulator_ref:clone(P.simulator)},
 actions:[{type:'navigate',view:'plan'}],sources:[]});
await env.ui.ask('Build the simulator');
assert.equal(env.b.app.view,'plan');
assert.deepEqual(env.ui.state.savedStage.context.plan_ref,P.plan);
assert.deepEqual(env.ui.state.savedStage.context.simulator_ref,P.simulator);
const frozen=await env.ui.render('plan');
assert(frozen.includes('Does checking improve correct publication?'));
assert(!frozen.includes('My separate unfinished question'));
assert(!frozen.includes('data-journey-field'));
assert.equal(JSON.stringify(env.ui.state.draft),before);
env.b.handle=()=>({answer_source:'ai',answer:'A new plan is saved.',
 updated_context:{plan_ref:clone(P.plan)},actions:[],sources:[]});
await env.ui.ask('Save a new experiment plan');
assert.equal(env.ui.state.simulatorRef,null,'a new plan cannot retain the prior world as its current world');
assert(!env.ui.state.savedStage.context.simulator_ref);
assert.equal(env.log.jobs.length,0);
""");

    def node(self, script):
        result = subprocess.run(
            ["node", "-e", NODE, str(ROOT / "web")],
            input=json.dumps({"script": script}), text=True,
            capture_output=True, timeout=25, cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "PASS")

    def test_connect_starts_live_investigation_but_no_subject_study(self):
        self.node(r"""
const env=setup();await connect(env);
assert.equal(env.b.app.live,false,'advanced mode must not silently select scripted discovery');
const req=env.log.requests.find(r=>r.path==='/api/observability/brief');
assert.deepEqual(req.body.dataset_ref,P.dataset);
assert.equal(env.log.jobs.length,1);const job=env.log.jobs[0];
assert.equal(job.action,'investigate');assert.equal(job.args.live,true);assert.equal(job.args.harness,'responses');
assert.equal(job.args.discovery_id,P.discovery.id);
assert.equal(job.args.discovery_version,P.discovery.version);assert.equal(job.args.discovery_hash,P.discovery.hash);
assert.deepEqual(env.ui.state.project,P.dataset);assert.deepEqual(env.ui.state.discoveryRef,P.discovery);
assert.equal(env.b.app.view,'brief');assert.equal(guided(env.log).length,0);
assert.equal(env.ui.state.planRef,null);assert.equal(env.ui.state.simulatorRef,null);assert.equal(env.ui.state.executionRef,null);
const guide=env.log.requests.find(r=>r.path==='/api/guide/chat');
assert.deepEqual(guide.body.current_context.brief_ref,P.brief);
assert(!env.log.jobs.some(j=>/experiment|cycle|execute/.test(j.action)));
""")

    def test_plan_build_and_run_are_three_distinct_explicit_actions(self):
        self.node(r"""
const env=setup();await connect(env);
await env.ui.render('plan');assert.equal(guided(env.log).length,0);
await env.ui.click(target({'data-journey-plan':''}));
assert.deepEqual(guided(env.log).map(r=>r.path),['/api/guided/plan']);
assert.deepEqual(guided(env.log)[0].body.source_ref,P.brief);
assert.equal(guided(env.log)[0].body.family,'shared_artifact_coordination');
assert.deepEqual(env.ui.state.planRef,P.plan);assert.equal(env.ui.state.simulatorRef,null);
await env.ui.render('simulator');assert.equal(guided(env.log).length,1);
await env.ui.click(target({'data-journey-build':''}));
assert.deepEqual(guided(env.log)[1].body,{plan_ref:P.plan});
assert.deepEqual(env.ui.state.simulatorRef,P.simulator);assert.equal(env.ui.state.executionRef,null);
await env.ui.render('simulator');assert.equal(guided(env.log).length,2);
await env.ui.click(target({'data-journey-run':''}));await settle();
assert.deepEqual(guided(env.log)[2].body,{simulator_ref:P.simulator});
assert.deepEqual(env.ui.state.executionRef,P.execution);assert.deepEqual(env.ui.state.study,P.result);
assert.equal(env.b.app.view,'findings');assert.equal(guided(env.log).length,3);
assert.equal(env.log.jobs.length,1,'only investigation uses the job launcher here');
""")

    def test_busy_guards_allow_only_one_pending_submission_per_stage(self):
        self.node(r"""
for(const [attr,path,field,reply]of [
 ['data-journey-connect','/api/observability/brief','connectBusy',{brief_ref:P.brief,dataset_ref:P.dataset,discovery_ref:P.discovery}],
 ['data-journey-plan','/api/guided/plan','planBusy',{plan_ref:P.plan}],
 ['data-journey-build','/api/guided/simulator','buildBusy',{simulator_ref:P.simulator}],
 ['data-journey-run','/api/guided/run','runBusy',{execution_ref:P.execution,result_ref:P.result}]
]){
 const env=setup(),hold=deferred();env.ui.state.connectSource=P.dataset.id;
 env.ui.state.briefRef=clone(P.brief);env.ui.state.planRef=clone(P.plan);env.ui.state.simulatorRef=clone(P.simulator);
 env.b.handle=(p)=>p===path?hold.promise:p==='/api/guide/chat'?{answer_source:'ai',answer:'Fixture',actions:[],sources:[]}:Promise.reject(Error('Unexpected route'));
 const first=env.ui.click(target({[attr]:''}));await settle();
 assert.equal(env.ui.state[field],true);await env.ui.click(target({[attr]:''}));
 assert.equal(env.log.requests.filter(r=>r.path===path).length,1);
 hold.resolve(clone(reply));await first;await settle();assert.equal(env.ui.state[field],false);
}
""")

    def test_draft_edits_invalidate_local_stage_refs_without_rewriting_sources(self):
        self.node(r"""
const env=setup();await connect(env);
env.ui.state.planRef=clone(P.plan);env.ui.state.simulatorRef=clone(P.simulator);env.ui.state.executionRef=clone(P.execution);
const before=JSON.stringify(env.records),jobCount=env.log.jobs.length,reqCount=env.log.requests.length;
env.ui.input(target({'data-journey-field':'question'},'A changed question','journey-question'));
assert.equal(env.ui.state.draft.question,'A changed question');
for(const k of ['planRef','simulatorRef','executionRef'])assert.equal(env.ui.state[k],null);
assert.deepEqual(env.ui.state.project,P.dataset);assert.deepEqual(env.ui.state.briefRef,P.brief);
assert.deepEqual(env.ui.state.discoveryRef,P.discovery);assert.equal(JSON.stringify(env.records),before);
assert.equal(env.log.jobs.length,jobCount);assert.equal(env.log.requests.length,reqCount);
env.ui.input(target({'data-journey-field':'question'},'', 'journey-question'));
const html=await env.ui.render('plan');assert(html.includes('id="journey-question"'));
assert.equal(env.ui.state.draft.question,'','transient input must not silently reuse old question');
""")

    def test_proactive_guide_cannot_launch_jobs_or_navigate(self):
        self.node(r"""
const env=setup();env.b.app.view='brief';env.ui.state.briefRef=clone(P.brief);
env.ui.state.planRef=clone(P.plan);const before=JSON.stringify(env.records);
env.b.handle=()=>({answer_source:'ai',answer:'<img src=x onerror=alert(1)>',
 plan_draft:{question:'A proposed local question'},actions:[
 {type:'navigate',view:'findings'},{type:'open_object',object_ref:P.result},
 {type:'run_job',action:'experiment',args:{live:false}},
 {type:'guided_run',simulator_ref:P.simulator}],sources:[]});
await env.ui.ask('Suggest a question',{proactive:true});
assert.equal(env.b.app.view,'brief');assert.equal(env.log.jobs.length,0);assert.equal(guided(env.log).length,0);
assert.equal(env.log.opens.length,0);assert.equal(env.ui.state.guideOpen,false);
assert.equal(env.ui.state.draft.question,'A proposed local question');assert.equal(env.ui.state.planRef,null);
assert.equal(JSON.stringify(env.records),before);
env.b.handle=()=>({answer_source:'ai',answer:'Fixture',actions:[{type:'run_job',action:'experiment'},{type:'guided_run'}],sources:[]});
await env.ui.ask('Explain the task');assert.equal(env.log.jobs.length,0);assert.equal(guided(env.log).length,0);
""")

    def test_source_less_and_authored_sources_have_no_default_scripted_launch(self):
        self.node(r"""
const authored=record({id:'dataset-authored',version:1,hash:'9'.repeat(64)},'dataset',
 {messages:[],provenance:{origin:'authored_example'},source:'coordination_fixture.jsonl'},{messages:8});
for(const records of [[],[authored]]){
 const env=setup({records});const html=await env.ui.render('connect');
 assert(/data-journey-connect\s+disabled/.test(html));
 assert(!html.includes('data-exp-example'));assert(!html.includes('scripted'));
 const brief=await env.ui.render('brief'),world=await env.ui.render('simulator');
 assert(brief.includes('Connect a source first'));assert(world.includes('Save a plan first'));
 assert(!world.includes('data-journey-run'));assert(!world.includes('data-journey-build'));
 assert.equal(env.log.jobs.length,0);assert.equal(env.log.requests.length,0);
}
""")

    def test_exact_saved_plan_failure_is_withheld_without_latest_fallback(self):
        self.node(r"""
for(const mutation of [{version:99},{hash:'0'.repeat(64)},{id:'guided-plan-other'}]){
 const env=setup();env.ui.state.planRef={...P.plan,...mutation};
 await assert.rejects(()=>env.ui.render('simulator'),/unavailable|Missing fixture source/);
 assert.equal(env.log.requests.length,0);assert.equal(env.log.jobs.length,0);
 assert.equal(env.log.reads.length,1);assert.equal(env.log.reads[0].version,env.ui.state.planRef.version);
}
""")

    def test_rejected_api_requests_release_submission_guards(self):
        self.node(r"""
for(const [attr,field]of [['data-journey-connect','connectBusy'],['data-journey-plan','planBusy'],
 ['data-journey-build','buildBusy'],['data-journey-run','runBusy']]){
 const env=setup();env.ui.state.connectSource=P.dataset.id;env.ui.state.briefRef=clone(P.brief);
 env.ui.state.planRef=clone(P.plan);env.ui.state.simulatorRef=clone(P.simulator);
 env.b.handle=()=>Promise.reject(Error('Fixture refusal'));
 await assert.rejects(()=>env.ui.click(target({[attr]:''})),/Fixture refusal/);
 assert.equal(env.ui.state[field],false);assert.equal(env.ui.state.executionRef,null);
}
""")

    def test_late_stage_responses_do_not_restore_superseded_draft_refs(self):
        self.node(r"""
for(const [attr,path,reply,field]of [
 ['data-journey-plan','/api/guided/plan',{plan_ref:P.plan},'planRef'],
 ['data-journey-build','/api/guided/simulator',{simulator_ref:P.simulator},'simulatorRef'],
 ['data-journey-run','/api/guided/run',{execution_ref:P.execution,result_ref:P.result},'executionRef']
]){
 const env=setup(),hold=deferred();env.ui.state.briefRef=clone(P.brief);
 env.ui.state.planRef=clone(P.plan);env.ui.state.simulatorRef=clone(P.simulator);
 env.b.handle=(p)=>p===path?hold.promise:Promise.reject(Error('No follow-up expected'));
 const before=JSON.stringify(env.records),pending=env.ui.click(target({[attr]:''}));await settle();
 const request=clone(env.log.requests.find(r=>r.path===path).body);
 env.ui.input(target({'data-journey-field':'question'},'The newer operator draft','journey-question'));
 hold.resolve(clone(reply));await pending;
 assert.equal(env.ui.state[field],null,'old result stays saved but cannot select the new draft');
 assert.equal(env.ui.state.draft.question,'The newer operator draft');
 assert.equal(env.b.app.view,'connect','superseded response cannot navigate to results');
 assert.equal(JSON.stringify(env.records),before);assert.equal(guided(env.log).length,1);
 if(path==='/api/guided/plan')assert.notEqual(request.question,env.ui.state.draft.question);
}
""")

    def test_initial_render_failure_does_not_permanently_lock_connect_or_execution(self):
        self.node(r"""
for(const [attr,field]of [['data-journey-connect','connectBusy'],
 ['data-journey-build','buildBusy'],['data-journey-run','runBusy']]){
 const env=setup();env.ui.state.connectSource=P.dataset.id;
 env.ui.state.planRef=clone(P.plan);env.ui.state.simulatorRef=clone(P.simulator);
 env.b.failRender=true;
 await assert.rejects(()=>env.ui.click(target({[attr]:''})),/Fixture render failure/);
 assert.equal(env.ui.state[field],false);assert.equal(env.log.requests.length,0);
 env.b.failRender=false;await env.ui.click(target({[attr]:''}));await settle();
 assert.equal(env.ui.state[field],false,'a deliberate retry after rendering recovers');
}
""")

    def test_old_source_or_old_draft_guide_reply_cannot_replace_current_plan_or_route(self):
        self.node(r"""
for(const change of ['source','draft']){
 const env=setup(),hold=deferred();env.b.app.view='brief';env.ui.state.briefRef=clone(P.brief);
 env.ui.state.project=clone(P.dataset);env.ui.state.draft.question='Original operator question';
 env.b.handle=(path)=>path==='/api/guide/chat'?hold.promise:Promise.reject(Error('No other route expected'));
 const pending=env.ui.ask('Help explain this exact source');await settle();
 const request=env.log.requests.find(r=>r.path==='/api/guide/chat');
 assert.deepEqual(request.body.current_context.brief_ref,P.brief);
 if(change==='source')env.ui.state.briefRef={...P.brief,version:3,hash:'8'.repeat(64)};
 else env.ui.input(target({'data-journey-field':'question'},'New operator draft','journey-question'));
 const currentQuestion=env.ui.state.draft.question;
 hold.resolve({answer_source:'ai',answer:'The previous source answer',
  plan_draft:{question:'Stale AI proposal'},actions:[{type:'navigate',view:'findings'},
  {type:'open_object',object_ref:P.result}],sources:[]});
 const answer=await pending;
 assert.equal(answer.stale_context,true);assert.equal(env.ui.state.draft.question,currentQuestion);
 assert.equal(env.b.app.view,'brief');assert.equal(env.log.opens.length,0);
 assert.equal(env.log.jobs.length,0);assert.equal(guided(env.log).length,0);
 assert.equal(env.ui.state.guideBusy,false);
}
""")

    def test_discovery_failure_keeps_screen_but_never_falls_back_to_scripted_agents(self):
        self.node(r"""
const env=setup();env.b.submit=async(action,args)=>{
 env.log.jobs.push({action,args:clone(args)});throw Error('Fixture provider unavailable');};
await connect(env);
assert.equal(env.log.jobs.length,1);assert.equal(env.log.jobs[0].args.live,true);
assert.equal(env.ui.state.discoveryJob,null);assert.deepEqual(env.ui.state.briefRef,P.brief);
assert.equal(env.b.app.view,'brief');assert.equal(guided(env.log).length,0);
assert(env.log.toasts.some(t=>t.error&&t.message.includes('could not start')));
assert(!env.log.jobs.some(j=>j.args.live===false));assert.equal(env.ui.state.connectBusy,false);
""")

    def test_findings_guide_context_uses_exact_completed_result_chain_only(self):
        self.node(r"""
const historyPin={id:'experiment-ui-history',version:5,hash:'4'.repeat(64)};
const rows=defaults();rows.push(record(historyPin,'experiment',
 {agent_mode:'live',runs:[],analysis:{}},{agent_mode:'live'}));
const env=setup({records:rows});env.b.app.view='findings';
env.ui.state.study=clone(P.result);env.ui.state.executionRef=clone(P.execution);
env.ui.state.briefRef={id:'observation-brief-unrelated',version:9,hash:'5'.repeat(64)};
env.ui.state.watchRunRef={id:'observability-run-unrelated',version:1,hash:'6'.repeat(64)};
env.ui.state.planRef={id:'guided-plan-current-draft',version:7,hash:'7'.repeat(64)};
env.ui.state.simulatorRef={id:'guided-simulator-current-draft',version:7,hash:'8'.repeat(64)};
const immutable=JSON.stringify(env.records);
await env.ui.render('findings');
const expected={result_ref:P.result,plan_ref:P.plan,simulator_ref:P.simulator,brief_ref:P.brief};
assert.deepEqual(env.ui.assistantContext(),expected);
await env.ui.ask('Explain this completed experiment',{proactive:true});
const sent=env.log.requests.find(r=>r.path==='/api/guide/chat');
assert.deepEqual(sent.body.current_context,expected);
assert(!Object.hasOwn(sent.body.current_context,'run_ref'));
assert(!Object.hasOwn(sent.body.current_context,'plan_draft'));
assert.equal(guided(env.log).length,0);assert.equal(env.log.jobs.length,0);
assert.equal(JSON.stringify(env.records),immutable);
assert(env.log.reads.some(r=>r.id===P.execution.id&&r.version===P.execution.version));
assert(env.log.reads.some(r=>r.id===P.proof.id&&r.version===P.proof.version));
assert(env.log.reads.some(r=>r.id===P.claims.id&&r.version===P.claims.version));
await env.ui.change(target({},historyPin.id,'exp-study'));
let switched=env.ui.assistantContext();
assert.deepEqual(switched.result_ref,historyPin);
assert(!Object.hasOwn(switched,'plan_ref'));assert(!Object.hasOwn(switched,'simulator_ref'));
assert(!Object.hasOwn(switched,'brief_ref'));assert(!Object.hasOwn(switched,'run_ref'));
await env.ui.render('findings');switched=env.ui.assistantContext();
assert.equal(env.ui.state.resultGuideContext,null);
assert(!Object.hasOwn(switched,'plan_ref'));assert(!Object.hasOwn(switched,'simulator_ref'));
assert(!Object.hasOwn(switched,'brief_ref'));assert(!Object.hasOwn(switched,'run_ref'));
assert.deepEqual(switched.result_ref,historyPin);
for(const different of [{version:2},{hash:'0'.repeat(64)}]){
 const changed=defaults();const execution=changed.find(r=>r.id===P.execution.id);
 execution.payload.result_ref={...P.result,...different};
 const other=setup({records:changed});other.b.app.view='findings';
 other.ui.state.study=clone(P.result);other.ui.state.executionRef=clone(P.execution);
 await other.ui.render('findings');const context=other.ui.assistantContext();
 assert.equal(other.ui.state.resultGuideContext,null);
 assert(!Object.hasOwn(context,'plan_ref'));assert(!Object.hasOwn(context,'simulator_ref'));
 assert(!other.log.reads.some(r=>r.id===P.proof.id),'a mismatched execution does not attest selected result');
}
""")

    def test_saved_result_stage_navigation_preserves_current_editable_draft(self):
        self.node(r"""
const currentPlan={id:'guided-plan-current-draft',version:7,hash:'7'.repeat(64)};
const currentWorld={id:'guided-simulator-current-draft',version:8,hash:'8'.repeat(64)};
const rows=defaults();rows.push(record(currentPlan,'guided_plan',
 {question:'An unrelated current plan',trials_per_arm:3,max_rounds:4}));
rows.push(record(currentWorld,'guided_simulator',{plan_ref:currentPlan,boundary_checks:{passed:true}}));
const env=setup({records:rows});env.b.app.view='findings';
env.ui.state.study=clone(P.result);env.ui.state.executionRef=clone(P.execution);
env.ui.state.planRef=clone(currentPlan);env.ui.state.simulatorRef=clone(currentWorld);
env.ui.state.draft.question='An unfinished operator draft';
const beforeDraft=JSON.stringify(env.ui.state.draft),beforeRecords=JSON.stringify(env.records);
const html=await env.ui.render('findings');
assert(html.includes('data-exp-result-stage="plan"'));assert(html.includes('data-exp-result-stage="simulator"'));
env.b.handle=()=>({answer_source:'ai',answer:'Opening the saved plan.',
 plan_draft:{question:'Unsolicited Findings draft must not replace operator edit'},
 actions:[{type:'navigate',view:'plan'}],sources:[]});
await env.ui.ask('Open the plan behind this result');
assert.equal(env.b.app.view,'plan');assert.deepEqual(env.ui.state.savedStage.context.plan_ref,P.plan);
assert.equal(JSON.stringify(env.ui.state.draft),beforeDraft);assert.deepEqual(env.ui.state.planRef,currentPlan);
assert.deepEqual(env.log.requests[0].body.current_context,
 {result_ref:P.result,plan_ref:P.plan,simulator_ref:P.simulator,brief_ref:P.brief});
await env.ui.click(target({'data-view':'findings'}));env.b.app.view='findings';
assert.equal(env.ui.state.savedStage,null);await env.ui.render('findings');
await env.ui.click(target({'data-exp-result-stage':'plan'}));
assert.equal(env.b.app.view,'plan');
let saved=await env.ui.render('plan');
assert(saved.includes('The plan behind this result'));assert(saved.includes(P.plan.id));
assert(!saved.includes('data-journey-field'));assert(!saved.includes('data-journey-plan'));
assert(!saved.includes('data-journey-run'));assert(!saved.includes('data-journey-build'));
assert.equal(JSON.stringify(env.ui.state.draft),beforeDraft);
assert.deepEqual(env.ui.state.planRef,currentPlan);assert.deepEqual(env.ui.state.simulatorRef,currentWorld);
const exact={result_ref:P.result,plan_ref:P.plan,simulator_ref:P.simulator,brief_ref:P.brief};
assert.deepEqual(env.ui.assistantContext(),exact);
const alias=env.ui.assistantContext();alias.plan_ref.version=99;
assert.equal(env.ui.assistantContext().plan_ref.version,P.plan.version,'returned context cannot mutate retained pins');
env.b.handle=()=>({answer_source:'ai',answer:'Opening the saved world.',
 plan_draft:{question:'Unsolicited historical draft must not replace operator edit'},
 actions:[{type:'navigate',view:'simulator'}],sources:[]});
await env.ui.ask('Open the world behind this result');
assert.equal(env.b.app.view,'simulator');saved=await env.ui.render('simulator');
assert(saved.includes('The world behind this result'));assert(saved.includes(P.simulator.id));
assert(!saved.includes('data-journey-run'));assert(!saved.includes('data-journey-build'));
assert.deepEqual(env.ui.assistantContext(),exact);
assert.equal(JSON.stringify(env.ui.state.draft),beforeDraft);
assert.deepEqual(env.ui.state.planRef,currentPlan);assert.deepEqual(env.ui.state.simulatorRef,currentWorld);
assert.equal(JSON.stringify(env.records),beforeRecords);
assert.equal(env.log.jobs.length,0);assert.equal(guided(env.log).length,0);
await env.ui.click(target({'data-exp-current-draft':''}));
assert.equal(env.ui.state.savedStage,null);assert.equal(env.b.app.view,'plan');
const editable=await env.ui.render('plan');assert(editable.includes('data-journey-field="question"'));
assert(editable.includes('An unfinished operator draft'));
assert.deepEqual(env.ui.assistantContext().plan_ref,currentPlan);
assert.equal(JSON.stringify(env.ui.state.draft),beforeDraft);
""")

    def test_saved_stage_version_or_world_link_mismatch_is_not_replaced_by_current_draft(self):
        self.node(r"""
for(const change of ['plan_version','plan_hash','world_plan_link']){
 const rows=defaults();const execution=rows.find(r=>r.id===P.execution.id);
 if(change==='plan_version')execution.payload.plan_ref.version=99;
 if(change==='plan_hash')execution.payload.plan_ref.hash='0'.repeat(64);
 if(change==='world_plan_link')rows.find(r=>r.id===P.simulator.id).payload.plan_ref.version=99;
 const env=setup({records:rows});env.b.app.view='findings';
 env.ui.state.study=clone(P.result);env.ui.state.executionRef=clone(P.execution);
 env.ui.state.planRef=clone(P.plan);env.ui.state.simulatorRef=clone(P.simulator);
 const before=JSON.stringify(env.ui.state.draft);
 await env.ui.render('findings');
 const stage=change==='world_plan_link'?'simulator':'plan';
 await env.ui.click(target({'data-exp-result-stage':stage}));
 await assert.rejects(()=>env.ui.render(stage),/Missing fixture source|unavailable|do not match/);
 assert.equal(JSON.stringify(env.ui.state.draft),before);
 assert.deepEqual(env.ui.state.planRef,P.plan);assert.deepEqual(env.ui.state.simulatorRef,P.simulator);
 assert.equal(env.log.requests.length,0);assert.equal(env.log.jobs.length,0);
}
""")

    def test_missing_explicit_result_has_no_historical_fallback_or_draft_side_effect(self):
        self.node(r"""
const env=setup();env.b.app.view='findings';
env.ui.state.study={...P.result,version:99};env.ui.state.executionRef=clone(P.execution);
env.ui.state.planRef=clone(P.plan);env.ui.state.draft.question='Preserve this current edit';
const selected=clone(env.ui.state.study),before=JSON.stringify(env.ui.state.draft);
const html=await env.ui.render('findings');
assert(html.includes('This saved result is unavailable'));assert.deepEqual(env.ui.state.study,selected);
assert.equal(env.ui.state.resultGuideContext,null);assert.equal(env.log.reads.length,0);
env.b.handle=()=>({answer_source:'ai',answer:'A historical explanation.',
 plan_draft:{question:'Do not apply this answer as a local edit'},actions:[],sources:[]});
await env.ui.ask('Explain this exact result',{proactive:true});
assert.equal(JSON.stringify(env.ui.state.draft),before);assert.deepEqual(env.ui.state.planRef,P.plan);
assert.deepEqual(env.log.requests[0].body.current_context,{result_ref:selected});
assert.equal(env.log.jobs.length,0);assert.equal(guided(env.log).length,0);
""")


if __name__ == "__main__":
    unittest.main()
