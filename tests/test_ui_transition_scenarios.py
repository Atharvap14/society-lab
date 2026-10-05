"""Declared long controller sequences with an independent per-chat oracle.

These execute current browser modules against isolated API fixtures. They do
not run subjects, infer scientific results, or write the production registry.
"""
import hashlib
import json
import pathlib
import subprocess
import unittest

from tests.test_lab_workspace_ui import NODE as WORKSPACE_NODE

ROOT = pathlib.Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "docs" / "ui-transition-scenarios.json"
REPORT_PATH = ROOT / ".runtime" / "ui-transition-scenario-results.json"
MODULES = ["research-journey.js", "society-replay.js", "artifact-map.js", "society-experience.js", "lab-workspace.js"]

SCRIPT = r"""
const scenarioPlan=__PLAN__,scenario=__SCENARIO__,env=setup();
const alternateBrief={id:'observation-brief-alternate',version:1,hash:'4'.repeat(64)};
env.records.push({...clone(alternateBrief),kind:'observation_brief',payload:{summary:'Isolated source screen',signals:[]}});
env.snapshots['chat-a'].state.context.plan_ref=clone(refs.plan);
for(const id of ['chat-a','chat-b'])env.snapshots[id].state.ui.journey.draftSourceRef=clone(refs.brief);
const oracle={
 'chat-a':{question:'Question A',control_text:'Neutral Question A',treatment_text:'Intervention Question A',seed:700,
  source:clone(refs.source),plan:clone(refs.plan),draftSource:clone(refs.brief),study:null,copy:null,copyFields:{}},
 'chat-b':{question:'Question B',control_text:'Neutral Question B',treatment_text:'Intervention Question B',seed:700,
  source:clone(refs.newer),plan:null,draftSource:clone(refs.brief),study:null,copy:null,copyFields:{}}
};
let active='chat-a';const other=()=>active==='chat-a'?'chat-b':'chat-a';
const result={scenario_version:'ui-transition-scenarios-v1',scenario,classification:'isolated software fixtures; no real agent evidence',
 passed:false,moves:[],coverage:{},expected:null,observed:null,failure:null,unexpected_jobs:0};
const observed=()=>({active_chat:env.b.app.activeChatId,view:env.b.app.view,
 chats:Object.fromEntries(Object.entries(env.snapshots).map(([id,row])=>[id,{revision:row.revision,
 question:row.state.plan_draft?.question,control_text:row.state.plan_draft?.control_text,treatment_text:row.state.plan_draft?.treatment_text,
 seed:row.state.ui?.journey?.draft?.seed,source:row.state.context?.dataset_ref||null,plan:row.state.context?.plan_ref||null,
 draftSource:row.state.ui?.journey?.draftSourceRef||null,study:row.state.context?.result_ref||null,
 copy:row.state.ui?.workspace?.copy_ref||row.state.ui?.workspace?.preview_copy_ref||null,
 copyFields:row.state.ui?.workspace?.copy_fields||{}}]))});
async function check(label){
 await env.workspace.flush();assert.equal(env.b.app.activeChatId,active,label+': active chat');
 const expected=oracle[active],actual=env.experience.state;
 for(const key of ['question','control_text','treatment_text','seed'])assert.equal(actual.draft[key],expected[key],label+': active draft '+key);
 assert.deepEqual(actual.project,expected.source,label+': current source');assert.deepEqual(actual.planRef,expected.plan,label+': current plan');
 assert.deepEqual(actual.draftSourceRef,expected.draftSource,label+': motivating brief');assert.deepEqual(actual.study,expected.study,label+': selected result');
 assert.deepEqual(env.workspace.state.copy?pin(env.workspace.state.copy):null,expected.copy,label+': copied view');
 assert.deepEqual(env.workspace.state.copyFields,expected.copyFields,label+': local copy fields');
 for(const[id,model]of Object.entries(oracle)){
  const saved=env.snapshots[id].state;
  for(const key of ['question','control_text','treatment_text'])assert.equal(saved.plan_draft[key],model[key],label+': '+id+' persisted '+key);
  assert.equal(saved.ui.journey.draft.seed,model.seed,label+': '+id+' persisted seed');
  assert.deepEqual(saved.context.dataset_ref,model.source,label+': '+id+' persisted source');
  assert.deepEqual(saved.context.plan_ref||null,model.plan,label+': '+id+' persisted plan');
  assert.deepEqual(saved.ui.journey.draftSourceRef,model.draftSource,label+': '+id+' persisted motivating brief');
  assert.deepEqual(saved.context.result_ref||null,model.study,label+': '+id+' persisted result');
  assert.deepEqual(saved.ui.workspace?.copy_ref||saved.ui.workspace?.preview_copy_ref||null,model.copy,label+': '+id+' persisted copy');
  assert.deepEqual(saved.ui.workspace?.copy_fields||{},model.copyFields,label+': '+id+' persisted copy fields');
 }
 assert.equal(env.log.jobs.length,0,label+': no unexpected research job');
 assert(!env.log.requests.some(r=>r.path.startsWith('/api/guided/')||r.path==='/api/jobs'),label+': no subject/world execution');
}
function edit(key,value){env.experience.input(target({'data-journey-field':key},String(value),'journey-'+key));
 oracle[active][key]=value;oracle[active].plan=null;env.workspace.notify();}
async function switchChat(){const destination=other();await env.workspace.loadChat(destination);active=destination;}
async function action(name,index){
 const stamp=scenario.seed+'-'+index,original=active;
 if(name==='edit_question')edit('question','Question '+original+' '+stamp);
 else if(name==='edit_control')edit('control_text','Neutral '+original+' '+stamp);
 else if(name==='edit_numeric')edit('seed',scenario.seed*100+index);
 else if(name==='switch_chat')await switchChat();
 else if(name==='source_replay'){
  const before=clone(env.experience.state.draft),source=clone(oracle[active].source),reads=env.log.reads.length;
  await env.workspace.click(target({'data-ws-artifact':refs.old.id,'data-ws-version':'1','data-ws-hash':refs.old.hash}));
  const html=await env.experience.render('watch');assert(html.includes('Older exact source'));
  assert.deepEqual(env.experience.state.previewWatch,refs.old);assert.deepEqual(env.experience.state.draft,before);assert.deepEqual(env.experience.state.project,source);
  const newReads=env.log.reads.slice(reads).filter(r=>r.id===refs.old.id);assert(newReads.length);assert(newReads.every(r=>r.version===1));
 }
 else if(name==='result_replay'){
  const draft=clone(env.experience.state.draft);await env.experience.openSavedArtifact(env.records.find(r=>r.id===refs.result.id&&r.version===1),'replay');
  const html=await env.experience.render('watch');assert(html.includes('SAVED TEAM TEST'));
  assert.deepEqual(env.experience.state.watchStudy,refs.result);assert.deepEqual(env.experience.state.draft,draft);oracle[active].study=clone(refs.result);
 }
 else if(name==='saved_stage'){
  const draft=clone(env.experience.state.draft);await env.experience.openSavedArtifact(env.records.find(r=>r.id===refs.plan.id),'open');
  assert.deepEqual(env.experience.assistantContext().plan_ref,refs.plan);assert(!Object.hasOwn(env.experience.assistantContext(),'plan_draft'));
  await env.experience.click(target({'data-exp-current-draft':'true'}));assert.equal(env.experience.state.savedStage,null);
  assert.deepEqual(env.experience.state.draft,draft);assert.equal(env.b.app.view,'plan');
 }
 else if(name==='copy_fields'){
  await env.workspace.click(target({'data-ws-artifact':refs.copied.id,'data-ws-version':'1','data-ws-hash':refs.copied.hash}));
  oracle[active].copy=clone(refs.copied);oracle[active].copyFields={};
  if(active==='chat-a'){
   const question='Local copied question '+stamp,notes='Local copied notes <'+stamp+'>';
   env.workspace.input(target({},question,'ws-copy-question'));env.workspace.input(target({},notes,'ws-copy-notes'));
   oracle[active].copyFields={question,notes};env.workspace.notify();
   const html=await env.workspace.render('workspace-copy');assert(html.includes(question));assert(html.includes('&lt;'+stamp+'&gt;'));
  }else await env.workspace.render('workspace-copy');
  assert.equal(env.workspace.state.copy.payload.editable_fields.question,'A copied question');
  assert(!env.log.requests.some(r=>r.body?.op==='update_draft'),'local copy fields never mutate an original');
 }
 else if(name==='restore_exact'){
  const key=refs.old.id+'@'+refs.old.version+':'+refs.old.hash;
  env.experience.state.replayStates.set(key,{cursor:1,room:'team',actor:'a',speed:1});
  const saved=env.experience.exportWorkspaceState(),aliased=clone(saved);aliased.context.dataset_ref.version=99;
  assert.deepEqual(env.experience.state.project,oracle[active].source);
  env.experience.restoreWorkspaceState(saved);assert.deepEqual(env.experience.state.replayStates.get(key),{cursor:1,room:'team',actor:'a',speed:1});
  assert.deepEqual(env.experience.state.project,oracle[active].source);env.workspace.notify();
 }
 else if(name==='stale_guide'){
  const pending=hold();env.b.handle=req=>req.path==='/api/guide/chat'?pending.promise:undefined;
  const answering=env.experience.ask('Isolated delayed question '+stamp);await settle();
  const request=env.log.requests.filter(r=>r.path==='/api/guide/chat').at(-1);assert.equal(request.body.active_chat_id,original);assert.equal(request.headers['X-Lab-Chat'],original);
  await switchChat();const currentView=env.b.app.view;
  pending.resolve({answer_source:'ai',answer:'STALE '+stamp,plan_draft:{question:'MUST NOT OVERWRITE'},actions:[{id:'stale-nav',type:'navigate',view:'findings'}],sources:[]});
  const answer=await answering;assert.equal(answer.stale_context,true);assert.equal(env.b.app.view,currentView);
  assert(!env.experience.state.chat.some(row=>row.text?.includes('STALE '+stamp)));env.b.handle=null;
 }
 else if(name==='overlap_save'){
  const pending=hold();let first=true;env.b.handle=req=>{if(req.body?.op==='save_state'&&first){first=false;return pending.promise;}};
  edit('question','Pending first '+original+' '+stamp);const saving=env.workspace.flush();await settle();
  const req=env.log.requests.filter(r=>r.body?.op==='save_state').at(-1);assert.equal(req.body.chat_id,original);
  edit('question','Pending newer '+original+' '+stamp);const destination=other(),switching=env.workspace.loadChat(destination);await settle();
  assert.equal(env.b.app.activeChatId,original);assert.equal(env.workspace.state.saving,true);
  const row=env.snapshots[original];assert.equal(row.revision,req.body.expected_revision);row.state=clone(req.body.state);row.revision++;
  pending.resolve({chat:clone(row)});await Promise.all([saving,switching]);active=destination;env.b.handle=null;
 }
 else if(name==='connect_source'){
  const next=oracle[active].source.id===refs.source.id?refs.newer:refs.source,newBrief=next.id===refs.source.id?refs.brief:alternateBrief;
  env.experience.state.connectSource=next.id;const before=clone(env.experience.state.draft),plan=clone(oracle[active].plan);
  env.b.handle=req=>req.path==='/api/observability/brief'?{dataset_ref:clone(next),brief_ref:clone(newBrief),run_ref:null,discovery_ref:null,follow_ref:null}:
   req.path==='/api/guide/chat'?{answer_source:'ai',answer:'Isolated proactive summary',plan_draft:{question:'UNREQUESTED PROACTIVE DRAFT'},actions:[],sources:[]}:undefined;
  await env.experience.click(target({'data-journey-connect':'true'}));await settle();env.b.handle=null;
  oracle[active].source=clone(next);assert.deepEqual(env.experience.state.draft,before);assert.deepEqual(env.experience.state.planRef,plan);
  assert.deepEqual(env.experience.state.draftSourceRef,oracle[active].draftSource);
 }
 else throw new Error('Undeclared action '+name);
}
function sequences(){
 if(scenario.kind==='long_range_goal')return ['source_replay','result_replay','saved_stage','copy_fields','switch_chat','source_replay','saved_stage','switch_chat','connect_source','restore_exact','result_replay','saved_stage'];
 let state=scenario.seed>>>0;const random=()=>{state^=state<<13;state^=state>>>17;state^=state<<5;return (state>>>0)/4294967296;},out=[];
 for(let block=0;block<5;block++){const names=[...scenarioPlan.actions];for(let i=names.length-1;i>0;i--){const j=Math.floor(random()*(i+1));[names[i],names[j]]=[names[j],names[i]];}out.push(...names);}return out;
}
try{
 await env.workspace.initialize();await check('initial');
 const names=sequences();for(let i=0;i<names.length;i++){
  const row={ordinal:i+1,action:names[i],origin_chat:active};result.moves.push(row);result.coverage[names[i]]=(result.coverage[names[i]]||0)+1;
  await action(names[i],i+1);await check('move '+(i+1)+' '+names[i]);row.expected={active_chat:active,chats:clone(oracle)};row.observed=observed();row.passed=true;
 }
 result.passed=true;
}catch(error){result.failure={name:error.name,message:error.message,stack:String(error.stack).split('\n').slice(0,5).join('\n'),failing_prefix:result.moves.map(row=>row.action)};}
result.expected={active_chat:active,chats:clone(oracle)};result.observed=observed();result.unexpected_jobs=env.log.jobs.length;
result.exact_reads=env.log.reads;result.save_revisions=env.log.requests.filter(row=>row.body?.op==='save_state').map(row=>({chat_id:row.body.chat_id,expected_revision:row.body.expected_revision}));
globalThis.scenarioResult=result;
"""


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class UITransitionScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        cls.report = {"report_version": "ui-transition-scenario-results-v1", "plan_sha256": digest(PLAN_PATH),
                      "scope": cls.plan["limits"], "scenarios": []}

    def scenario(self, kind, seed):
        descriptor = {"kind": kind, "seed": seed}
        source_pins = {name: digest(ROOT / "web" / name) for name in MODULES}
        node = WORKSPACE_NODE.replace("process.stdout.write('PASS');", "process.stdout.write(JSON.stringify(ctx.scenarioResult));")
        script = SCRIPT.replace("__PLAN__", json.dumps(self.plan)).replace("__SCENARIO__", json.dumps(descriptor))
        process = subprocess.run(["node", "-e", node, str(ROOT)], input=json.dumps({"script": script}),
                                 text=True, encoding="utf-8", capture_output=True, timeout=60, cwd=ROOT)
        if process.returncode:
            outcome = {"scenario": descriptor, "passed": False,
                       "failure": {"name": "NodeFixtureError", "message": process.stderr[-4000:]}, "moves": []}
        else:
            outcome = json.loads(process.stdout)
        outcome["implementation_sha256"] = source_pins
        outcome["implementation_stable_during_run"] = source_pins == {name: digest(ROOT / "web" / name) for name in MODULES}
        if not outcome["implementation_stable_during_run"]:
            outcome["passed"] = False
            outcome["failure"] = {"name": "SourceDrift", "message": "Current browser bytes changed during the fixture run; rerun this scenario."}
        self.report["scenarios"].append(outcome)
        self.report["passed"] = all(row["passed"] for row in self.report["scenarios"])
        REPORT_PATH.parent.mkdir(exist_ok=True)
        REPORT_PATH.write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding="utf-8")
        return outcome

    def test_three_seeded_sixty_move_sequences(self):
        self.assertEqual(self.plan["moves_per_seed"], 60)
        for seed in self.plan["seeds"]:
            with self.subTest(seed=seed):
                outcome = self.scenario("seeded", seed)
                self.assertTrue(outcome["passed"], outcome.get("failure"))
                self.assertEqual(len(outcome["moves"]), 60)
                self.assertEqual(outcome["coverage"], {name: 5 for name in self.plan["actions"]})
                self.assertEqual(outcome["unexpected_jobs"], 0)

    def test_long_range_saved_draft_goal(self):
        outcome = self.scenario("long_range_goal", 173)
        self.assertTrue(outcome["passed"], outcome.get("failure"))
        self.assertEqual(outcome["expected"]["chats"]["chat-a"]["question"], "Question A")
        self.assertEqual(outcome["expected"]["chats"]["chat-a"]["plan"]["version"], 3)
        self.assertEqual(outcome["observed"]["chats"]["chat-a"]["plan"], outcome["expected"]["chats"]["chat-a"]["plan"])
        self.assertEqual(outcome["unexpected_jobs"], 0)


if __name__ == "__main__":
    unittest.main()
