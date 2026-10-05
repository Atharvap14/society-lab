"""Executable static algebra panel keeps unknowns, source pins and zero-call replay."""
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
run("app.state={objects:records.map(o=>({id:o.id,kind:o.kind,version:o.version,hash:o.hash,summary:{name:o.kind}})),jobs:[],usage:{calls:400},max_calls:400,model:'test'};app.live=true;app.harness='codex';submit=async(action,args)=>{globalThis.sent={action,args}};globalThis.record=records[0];globalThis.proof=records[1];globalThis.budget=records[2];globalThis.unavailable=records[3];");
(async()=>{
  const before=JSON.stringify(c.records[0]);let html=run('graphHodgePanel(record,proof)');
  assert(html.includes('Recorded fresh source/operator reproduction: passed'));assert(html.includes('fixed parent cells available'));
  assert(html.includes('GRADIENT ENERGY'));assert(html.includes('CIRCULATION ENERGY'));assert(html.includes('FRACTIONS GRADIENT / CIRCULATION'));
  assert(html.includes('Unknown / Unknown'));assert(html.includes('supported zero edges remain'));assert(html.includes('curl and harmonic components/energies remain unknown'));
  assert(html.includes('zero energy and undefined fractions'));assert(html.includes('without ranking or rematching'));assert(html.includes('Node universes can vary by window'));
  assert(html.includes('Time order is discarded'));assert(html.includes('physical traffic, hierarchy, rumor, chronological relay'));
  assert(html.includes('not proportions of messages or agents'));assert(html.includes('without clipping'));assert(html.includes('10⁻¹²'));
  assert(html.includes('&quot;faces&quot;: null'));assert(!html.includes('node_potential'));assert(!html.includes('PRIVATE_PROVIDER_SENTINEL'));
  assert(!html.includes('Bobby, inspect the telescope artifact'));assert.equal(JSON.stringify(c.records[0]),before);
  assert.equal(run('hodgeDisplay(1e-30,4)'),'≈ 0');assert.equal(run('hodgeDisplay(0)'),'0');assert.equal(run('hodgeDisplay(null)'),'Unknown');assert.equal(run('hodgeDisplay(false)'),'Unknown');assert.equal(run('hodgeDisplay(1e-5)'),'0.00001');
  for(const edit of ["proof.payload.audit_ref.version=true","proof.payload.audit_ref.hash='f'.repeat(64)","proof.payload.model_calls=false","proof.payload.source_replay_attempted=false","proof.payload.source_replay_completed=false","proof.payload.result_kind='temporal_path_audit'"]){
    const previous=JSON.stringify(c.records[1].payload);run(edit);assert(!run('exactHodgeProof(record,proof)'));html=run('graphHodgePanel(record,proof)');assert(!html.includes('Recorded fresh source/operator reproduction: passed'));assert(html.includes('displayed values are recorded output'));c.records[1].payload=JSON.parse(previous);
  }
  html=run('graphHodgePanel(budget)');assert(html.includes('aggregate_work_budget_exceeded'));assert(html.includes('Unknown / Unknown'));assert(html.includes('unavailable:'));
  html=run('graphHodgePanel(unavailable)');assert(html.includes('Unknown / Unknown / Unknown'));assert(html.includes('Unknown / Unknown'));assert(html.includes('unavailable:'));
  run("unavailable.payload.cells[0].source_scope.start='<script>inert</script>'");html=run('graphHodgePanel(unavailable)');assert(html.includes('&lt;script&gt;inert&lt;/script&gt;'));assert(!html.includes('<script>inert</script>'));
  assert.equal(run('uniqueIds([record.id]).length'),1);await run('openObject(record.id,1)');assert(node('evidence-dialog').open);assert(node('dialog-body').innerHTML.includes('Source-bound') || node('dialog-body').innerHTML.includes('Static edge-count algebra'));
  await run('openObject(proof.id,1)');assert(node('dialog-body').innerHTML.includes('Exact source/operator replay identity and limits'));
  await listeners.click({target:button({action:'replay-edge-flow',id:c.records[0].id,version:'1'})});assert.equal(c.sent.action,'replay_edge_flow');assert.equal(c.sent.args.audit_id,c.records[0].id);assert.equal(c.sent.args.version,1);assert.deepEqual(Object.keys(c.sent.args).sort(),['audit_id','version']);assert(!('live' in c.sent.args));assert(!('harness' in c.sent.args));
  for(const version of ['1.5','0','',true,'2']){c.sent=null;await listeners.click({target:button({action:'replay-edge-flow',id:c.records[0].id,version})});assert.equal(c.sent,null)}
  c.sent=null;await listeners.click({target:button({action:'replay-edge-flow',id:c.records[4].id,version:'1'})});assert.equal(c.sent,null);
  run('app.selected.graph_hodge_audit=record.id');html=await run('graphHodgeAuditSection()');assert(html.includes('data-select="graph_hodge_audit"'));assert(html.includes('Static edge-count algebra'));
  console.log('Source-bound algebra, zero versus unknown, nonclipping tolerance, inert metadata and exact zero-call replay passed');
})().catch(error=>{console.error(error.stack);process.exitCode=1});
'''


@unittest.skipUnless(NODE,'Node required for executable UI contract')
class GraphHodgeUITests(unittest.TestCase):
    def test_all_fixed_cells_unknown_energies_fractions_and_exact_zero_call_replay(self):
        from tests.test_graph_hodge_report import prepared_fixture
        from swarm_lab import graph_hodge_workflow as workflow
        f,parent=prepared_fixture();self.addCleanup(f.doCleanups)
        audit=workflow.audit_edge_flow(f.lab,parent['id']);proof=workflow.replay_edge_flow(f.lab,audit['id'])
        budget=workflow.audit_edge_flow(f.lab,parent['id'],max_work=1)
        selected=f.lab.audit_selected_leads(f.discovery['id'],short_name_allowlist=['o3'],include_unicode_shadow=False)
        other=f.lab.audit_temporal_paths(selected['id'],version=selected['version'])
        unavailable=workflow.audit_edge_flow(f.lab,other['id'])
        result=subprocess.run([NODE,'-e',SCRIPT],input=json.dumps([audit,proof,budget,unavailable,parent]),text=True,capture_output=True,cwd=ROOT)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(f.lab.store.usage()['calls'],0)


if __name__=='__main__':unittest.main()
