"""Executable compact literal/action view; no semantic labels or live defaults."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
NODE=shutil.which('node')
SCRIPT=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const records=JSON.parse(fs.readFileSync(0,'utf8')),nodes=new Map(),listeners={};
function node(id){if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',open:false,classList:{toggle(){},remove(){}},addEventListener(){},showModal(){this.open=true},close(){this.open=false},contains(){return false},querySelector(){return null}});return nodes.get(id)}
const map=Object.fromEntries(records.map(o=>[o.id,o]));
const c={console,records,Map,Set,Date,JSON,Math,Number,String,Array,Object,Promise,CSS:{escape:x=>x},setTimeout:()=>0,clearTimeout(){},setInterval:()=>0,document:{getElementById:node,querySelector:node,querySelectorAll:()=>[],activeElement:null,addEventListener:(event,f)=>{const old=listeners[event];listeners[event]=old?async e=>{await old(e);await f(e)}:f}},fetch:async path=>({ok:true,json:async()=>map[path.split('/').pop().split('?')[0]]})};
vm.createContext(c);const source=fs.readFileSync('web/app.js','utf8');vm.runInContext(source.slice(0,source.lastIndexOf('\nrefresh(true);')),c);
const run=s=>vm.runInContext(s,c),button=dataset=>({dataset,closest(){return this},hasAttribute(){return false}});
run("app.state={objects:records.map(o=>({id:o.id,kind:o.kind,version:o.version,hash:o.hash,summary:{name:o.kind}})),jobs:[],usage:{calls:400},max_calls:400,model:'test'};app.live=true;app.harness='codex';submit=async(action,args)=>{globalThis.sent={action,args}};globalThis.record=records[0];globalThis.proof=records[1];globalThis.unknown=records[2];");
(async()=>{
  let html=run('waitMarkerPanel(record,proof)');assert(html.includes('Recorded fresh source/action reproduction: passed'));assert(html.includes('25 selected chats'));assert(html.includes('24 agent-authored'));assert(html.includes('2 literal spans in 1 marker messages; 23 deterministic nonmarker comparisons'));
  assert(html.includes('1 / 1'));assert(html.includes('CANDIDATE + CENSORED BAND'));assert(html.includes('NO CANDIDATE + CENSORED BAND'));assert(html.includes('before, tie and after all count'));
  assert(html.includes('neither probability samples nor negative semantic ground truth'));assert(html.includes('Negations, quotations, plans and instructions'));assert(html.includes('Missing rooms remain unassigned'));assert(html.includes('raw chat clock policies are unavailable'));assert(html.includes('does not add independent samples'));
  assert(!html.includes('PRIVATE_PROVIDER_SENTINEL'));assert(!html.includes('Bobby, I am not waiting; someone said pause.'));
  assert(!html.includes('true positive'));assert(!html.includes('false negative'));assert(!/p\s*=\s*[\d.]+/.test(html));
  for(const edit of ["proof.payload.alignment_ref.version=true","proof.payload.alignment_ref.hash='f'.repeat(64)","proof.payload.model_calls=false","proof.payload.source_replay_attempted=false","proof.payload.index_artifact_reread_completed=false","proof.payload.full_event_source_reread=true","proof.payload.result_kind='actor_event_audit'"]){
    const before=JSON.stringify(c.records[1].payload);run(edit);assert(!run('exactWaitMarkerProof(record,proof)'));html=run('waitMarkerPanel(record,proof)');assert(!html.includes('Recorded fresh source/action reproduction: passed'));assert(html.includes('displayed values are recorded output'));c.records[1].payload=JSON.parse(before);
  }
  html=run('waitMarkerPanel(unknown)');assert(html.includes('Candidate alignment is unknown'));assert(html.includes('aggregate_work_budget_exceeded'));assert(!html.includes('<th>INCLUSIVE HORIZON</th>'));assert(!html.includes('0 / 0'));
  run("unknown.payload.alignment.unknown_reasons.push('<script>inert</script>')");html=run('waitMarkerPanel(unknown)');assert(html.includes('&lt;script&gt;inert&lt;/script&gt;'));assert(!html.includes('<script>inert</script>'));
  assert.equal(run('uniqueIds([record.id]).length'),1);await run('openObject(record.id,1)');assert(node('evidence-dialog').open);assert(node('dialog-body').innerHTML.includes('Full recorded alignment evidence'));
  await run('openObject(proof.id,1)');assert(node('dialog-body').innerHTML.includes('Exact literal-marker replay identity and limits'));
  await listeners.click({target:button({action:'replay-wait-markers',id:c.records[0].id,version:'1'})});assert.equal(c.sent.action,'replay_wait_markers');assert.equal(c.sent.args.alignment_id,c.records[0].id);assert.equal(c.sent.args.version,1);assert.deepEqual(Object.keys(c.sent.args).sort(),['alignment_id','version']);assert(!('live' in c.sent.args));assert(!('harness' in c.sent.args));
  for(const version of ['1.5','0','',true,'2']){c.sent=null;await listeners.click({target:button({action:'replay-wait-markers',id:c.records[0].id,version})});assert.equal(c.sent,null)}
  c.sent=null;await listeners.click({target:button({action:'replay-wait-markers',id:c.records[3].id,version:'1'})});assert.equal(c.sent,null);
  run('app.selected.wait_marker_alignment_audit=record.id');html=await run('waitMarkerAuditSection()');assert(html.includes('data-select="wait_marker_alignment_audit"'));assert(html.includes('Literal wait/action proximity'));
  console.log('Compact denominators/censoring, semantic limits, null unknowns, inert metadata and zero-call exact replay passed');
})().catch(error=>{console.error(error.stack);process.exitCode=1});
'''


@unittest.skipUnless(NODE,'Node required for executable UI contract')
class WaitMarkerUITests(unittest.TestCase):
    def test_compact_denominators_censored_bands_unknowns_and_exact_zero_call_replay(self):
        from tests.test_wait_marker_report import prepared_fixture
        from swarm_lab import wait_marker_workflow as workflow
        f=prepared_fixture();self.addCleanup(f.doCleanups);actor=f.actor_audit()
        audit=workflow.audit_wait_markers(f.lab,actor['id']);proof=workflow.replay_wait_markers(f.lab,audit['id'])
        unknown=workflow.audit_wait_markers(f.lab,actor['id'],max_work=1)
        result=subprocess.run([NODE,'-e',SCRIPT],input=json.dumps([audit,proof,unknown,actor]),text=True,capture_output=True,cwd=ROOT)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(f.lab.store.usage()['calls'],0)


if __name__=='__main__':unittest.main()
