"""Executable actor/time UI fixtures preserve scopes and exact zero-call replay."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
NODE=shutil.which('node')
SCRIPT=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const records=JSON.parse(fs.readFileSync(0,'utf8')),nodes=new Map(),listeners={},requests=[];
function node(id){if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',open:false,classList:{toggle(){},remove(){}},addEventListener(){},showModal(){this.open=true},close(){this.open=false},contains(){return false},querySelector(){return null}});return nodes.get(id)}
const map=Object.fromEntries(records.map(o=>[o.id,o]));
const c={console,records,Map,Set,Date,JSON,Math,Number,String,Array,Object,Promise,CSS:{escape:x=>x},setTimeout:()=>0,clearTimeout(){},setInterval:()=>0,document:{getElementById:node,querySelector:node,querySelectorAll:()=>[],activeElement:null,addEventListener:(event,f)=>{const old=listeners[event];listeners[event]=old?async e=>{await old(e);await f(e)}:f}},fetch:async path=>{requests.push(path);return {ok:true,json:async()=>map[path.split('/').pop().split('?')[0]]}}};
vm.createContext(c);const source=fs.readFileSync('web/app.js','utf8');vm.runInContext(source.slice(0,source.lastIndexOf('\nrefresh(true);')),c);
const run=s=>vm.runInContext(s,c),button=dataset=>({dataset,closest(){return this},hasAttribute(){return false}});
run("app.state={objects:records.map(o=>({id:o.id,kind:o.kind,version:o.version,hash:o.hash,summary:{name:o.kind}})),jobs:[],usage:{calls:400},max_calls:400,model:'test'};app.live=true;app.harness='codex';submit=async(action,args)=>{globalThis.sent={action,args}};globalThis.record=records[0];globalThis.proof=records[1];globalThis.room=records[2];");
(async()=>{
  let html=run('actorEventPanel(record,proof,room)');assert(html.includes('Recorded fresh actor/time replay: passed'));assert(html.includes('Known / missing / invalid room'));assert(html.includes('0 / 3 / 1') || html.includes('1 / 3 / 0'));
  assert(html.includes('Explicit room + time'));assert(html.includes('Selected actors + time; room omitted'));assert(html.includes('share exact index and selected-source pins'));
  assert(html.includes('A room/time zero is not evidence of absent activity'));assert(html.includes('not elapsed inactivity'));assert(html.includes('not verified exclusive leases'));assert(html.includes('not independent samples'));assert(html.includes('no original audit, graph, library status'));
  assert(html.includes('Complete within index'));assert(html.includes('No truncation'));assert(!html.includes('PRIVATE_PROVIDER_SENTINEL'));
  assert.equal(run('uniqueIds([record.id]).length'),1);
  for(const edit of ["proof.payload.audit_ref.version=true","proof.payload.audit_ref.hash='f'.repeat(64)","proof.payload.model_calls=false","proof.payload.full_event_source_reread=true","proof.payload.index_artifact_reread_completed=false","proof.payload.result_kind='indexed_event_audit'"]){
    const before=JSON.stringify(c.records[1].payload);run(edit);assert(!run('exactActorProof(record,proof)'));html=run('actorEventPanel(record,proof,room)');assert(!html.includes('Recorded fresh actor/time replay: passed'));assert(html.includes('Counts below are recorded audit output'));c.records[1].payload=JSON.parse(before);
  }
  const before=JSON.stringify(c.records[2].payload);run("room.payload.selected_audit_ref.hash='b'.repeat(64)");html=run('actorEventPanel(record,proof,room)');assert(!html.includes('Explicit room + time'));assert(html.includes('numerical cross-instrument comparison is omitted'));c.records[2].payload=JSON.parse(before);
  run("record.payload.name='<script>inert</script>'");html=run('actorEventPanel(record,proof,room)');assert(html.includes('&lt;script&gt;inert&lt;/script&gt;'));assert(!html.includes('<script>inert</script>'));
  await run('openObject(record.id,1)');assert(node('evidence-dialog').open);assert(node('dialog-body').innerHTML.includes('Exact actor-event audit identity'));
  await run('openObject(proof.id,1)');assert(node('dialog-body').innerHTML.includes('Exact actor/time replay identity and limitations'));
  await listeners.click({target:button({action:'replay-actor-events',id:c.records[0].id,version:'1'})});assert.equal(c.sent.action,'replay_actor_events');assert.equal(c.sent.args.audit_id,c.records[0].id);assert.equal(c.sent.args.version,1);assert.deepEqual(Object.keys(c.sent.args).sort(),['audit_id','version']);assert(!('live' in c.sent.args));assert(!('harness' in c.sent.args));
  for(const version of ['1.5','0','',true,'9007199254740992','2']){c.sent=null;await listeners.click({target:button({action:'replay-actor-events',id:c.records[0].id,version})});assert.equal(c.sent,null)}
  c.sent=null;await listeners.click({target:button({action:'replay-actor-events',id:c.records[2].id,version:'1'})});assert.equal(c.sent,null);
  html=await run('actorEventAuditSection()');assert(html.includes('Selected-author actor/time events'));assert(html.includes('data-select="actor_event_audit"'));
  const coverage=c.records[0].payload.actor_event_packet.coverage,old=JSON.stringify(coverage);coverage.query_complete=false;coverage.truncated=true;coverage.build_scan.complete_scan=false;html=run('actorEventPanel(record,proof,room)');assert(html.includes('Partial / not established'));assert(html.includes('Truncated'));assert(html.includes('truncated summaries describe retained records only'));c.records[0].payload.actor_event_packet.coverage=JSON.parse(old);
  console.log('Explicit actor/room scopes, inert source view, exact replay proof and cap-independent zero-call handler passed');
})().catch(error=>{console.error(error.stack);process.exitCode=1});
'''


@unittest.skipUnless(NODE,'Node required for executable UI contract')
class ActorEventUITests(unittest.TestCase):
    def test_scopes_coverage_proof_guards_and_exact_zero_call_replay(self):
        from tests.test_actor_event_workflow import ActorEventWorkflowTests
        from swarm_lab.actor_event_workflow import replay_actor_events
        f=ActorEventWorkflowTests('test_derivation_is_deterministic_without_audit_store_write')
        f.setUp();self.addCleanup(f.doCleanups);f.extra_events();index=f.build();actor=f.audit(index)
        proof=replay_actor_events(f.lab,actor['id'],version=1)
        room=f.lab.audit_indexed_events(index['id'],f.selected['id'])
        result=subprocess.run([NODE,'-e',SCRIPT],input=json.dumps([actor,proof,room]),text=True,capture_output=True,cwd=ROOT)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(f.lab.store.usage()['calls'],0)


if __name__=='__main__':
    unittest.main()
