"""Execute descriptive-reference controls, null rendering and exact replay links."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which('node')
SCRIPT = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const records=JSON.parse(fs.readFileSync(0,'utf8')),nodes=new Map(),listeners={};
function node(id){if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',open:false,classList:{toggle(){},remove(){}},addEventListener(){},showModal(){this.open=true},close(){this.open=false},contains(){return false},querySelector(){return null}});return nodes.get(id)}
const map=Object.fromEntries(records.map(o=>[o.id,o]));
const c={console,records,Map,Set,Date,JSON,Math,Number,String,Array,Object,Promise,CSS:{escape:x=>x},setTimeout:()=>0,clearTimeout(){},setInterval:()=>0,document:{getElementById:node,querySelector:node,querySelectorAll:()=>[],activeElement:null,addEventListener:(event,f)=>{const old=listeners[event];listeners[event]=old?async e=>{await old(e);await f(e)}:f}},fetch:async path=>({ok:true,json:async()=>map[path.split('/').pop().split('?')[0]]})};
vm.createContext(c);let source=fs.readFileSync('web/app.js','utf8');vm.runInContext(source.slice(0,source.lastIndexOf('\nrefresh(true);')),c);
const run=s=>vm.runInContext(s,c),button=dataset=>({dataset,closest(){return this},hasAttribute(){return false}});
run("app.state={objects:records.map(o=>({id:o.id,kind:o.kind,version:o.version,hash:o.hash,summary:{name:o.kind}})),jobs:[],usage:{calls:397},max_calls:400,model:'test'};app.live=true;submit=async(action,args)=>{globalThis.sent={action,args}};globalThis.record=records[0];globalThis.proof=records[1];globalThis.temporal=records[2];");
(async()=>{
let html=run('temporalReferencePanel(record,temporal,proof)');
assert(html.includes('Recorded pinned-source replay: passed'));assert(html.includes('REFERENCE MIN / Q25 / MEDIAN / Q75 / MAX'));assert(html.includes('DRAWS LESS / EQUAL / GREATER'));
assert(html.includes('edge-time multiplicities can change'));assert(html.includes('not p-values or significance tests'));assert(html.includes('not independent replication'));assert(html.includes('Original event pins'));
assert(!/\bp\s*=\s*\d/.test(html));
for(const edit of ["proof.payload.reference_ref.version=2","proof.payload.model_calls=false","proof.payload.source_replay_completed=false","proof.payload.reference_ref.hash='a'.repeat(64)"]){
 const before=JSON.stringify(c.records[1].payload);run(edit);assert(!run('exactTemporalReferenceProof(record,proof)'));assert(!run('temporalReferencePanel(record,temporal,proof)').includes('Recorded pinned-source replay: passed'));c.records[1].payload=JSON.parse(before);
}
run("record.payload.name='<script>inert</script>'");html=run('temporalReferencePanel(record,temporal)');assert(html.includes('&lt;script&gt;inert&lt;/script&gt;'));assert(!html.includes('<script>inert</script>'));
assert.equal(run('uniqueIds([record.id]).length'),1);
await run('openObject(record.id)');assert(node('evidence-dialog').open);assert(node('dialog-body').innerHTML.includes('Original counts and reference') || node('dialog-body').innerHTML.includes('Exact conditional reference'));
await run('openObject(proof.id)');assert(node('dialog-body').innerHTML.includes('Exact conditional reference replay'));
await listeners.click({target:button({action:'replay-temporal-reference',id:c.records[0].id,version:'1'})});assert.equal(c.sent.action,'replay_temporal_reference');assert.equal(c.sent.args.reference_id,c.records[0].id);assert.equal(c.sent.args.version,1);assert(!('live' in c.sent.args));
run("app.temporalRefSeed='4411';app.temporalRefDraws='4'");await listeners.click({target:button({action:'audit-temporal-reference',id:c.records[2].id,version:'1'})});assert.equal(c.sent.action,'audit_temporal_reference');assert.equal(c.sent.args.temporal_audit_id,c.records[2].id);assert.equal(c.sent.args.version,1);assert.equal(c.sent.args.seed,4411);assert.equal(c.sent.args.resamples,4);assert.equal(c.sent.args.max_work,10000000);assert(!('live' in c.sent.args));assert(!('harness' in c.sent.args));
run("sent=null;app.temporalRefDraws='257'");await listeners.click({target:button({action:'audit-temporal-reference',id:c.records[2].id,version:'1'})});assert.equal(c.sent,null);assert(node('toast').textContent.includes('1–256'));
run("app.temporalRefDraws='4';app.temporalRefSeed='9007199254740992';sent=null");await listeners.click({target:button({action:'audit-temporal-reference',id:c.records[2].id,version:'1'})});assert.equal(c.sent,null);
c.budget=records[3];html=run('temporalReferencePanel(budget,temporal)');assert(html.includes('not computed work budget'));assert(html.includes('no observed replay, samples, envelopes or rank counts computed'));assert(!html.includes('<td>0 / 0 / 0</td>'));
const cell=Object.values(Object.values(c.records[0].payload.timestamp_reference.windows)[0].variants)[0];cell.observed.maximum_loss_fraction=null;cell.reference.metrics.maximum_loss_fraction={envelope:null,rank_counts:null,defined_draws:0,undefined_draws:4};html=run('temporalReferencePanel(record,temporal)');assert(html.includes('Undefined'));assert(html.includes('0 / 4'));
console.log('Descriptive temporal envelopes, exact source proof, inert rendering and zero-call bounded actions passed');
})().catch(error=>{console.error(error.stack);process.exitCode=1});
'''


@unittest.skipUnless(NODE, 'Node required for executable UI contract')
class TemporalReferenceUITests(unittest.TestCase):
    def test_actual_fixture_reference_views_proof_bounds_and_zero_call_handlers(self):
        from tests.test_temporal_null_workflow import TemporalNullWorkflowTests
        f = TemporalNullWorkflowTests('test_bool_versions_and_unsafe_parameters_refused')
        f.setUp()
        self.addCleanup(f.doCleanups)
        reference = f.derive()
        proof = f.lab.replay_temporal_reference(reference['id'])
        budget = f.derive(max_work=1)
        result = subprocess.run([NODE, '-e', SCRIPT],
            input=json.dumps([reference,proof,f.temporal,budget]), text=True,capture_output=True,cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
