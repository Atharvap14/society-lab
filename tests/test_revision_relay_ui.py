"""Executable UI gates for exact versions, failures and declared uncertainty."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
NODE=shutil.which('node')
SCRIPT=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const records=JSON.parse(fs.readFileSync(0,'utf8')),nodes=new Map(),listeners={};
function node(id){if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',open:false,classList:{toggle(){},remove(){}},addEventListener(){},showModal(){this.open=true},close(){this.open=false},contains(){return false},querySelector(){return null}});return nodes.get(id)}
const map=Object.fromEntries(records.map(o=>[o.id,o]));
const c={console,records,Map,Set,Date,JSON,Math,Number,String,Array,Object,Promise,CSS:{escape:x=>x},setTimeout:()=>0,clearTimeout(){},setInterval:()=>0,document:{getElementById:node,querySelector:node,querySelectorAll:()=>[],activeElement:null,addEventListener:(event,f)=>{const old=listeners[event];listeners[event]=old?async e=>{await old(e);await f(e)}:f}},fetch:async path=>({ok:true,json:async()=>map[path.split('/').pop().split('?')[0]]})};
vm.createContext(c);let source=fs.readFileSync('web/app.js','utf8');vm.runInContext(source.slice(0,source.lastIndexOf('\nrefresh(true);')),c);vm.runInContext(fs.readFileSync('web/revision-relay.js','utf8'),c);
const run=s=>vm.runInContext(s,c),button=dataset=>({dataset,closest(){return this},hasAttribute(){return false}});
run("app.state={objects:records.map(o=>({id:o.id,kind:o.kind,version:o.version,hash:o.hash,summary:{name:o.kind,protocol_ref:o.payload.protocol_ref}})),jobs:[],usage:{calls:400,completed:397},max_calls:400,model:'fixture-model',supported_actions:['design_revision_relay','experiment_revision_relay','audit_revision_relay']};app.live=false;app.selected.revision_relay_protocol=records[0].id;app.selected.revision_relay_experiment=records[1].id;submit=async(action,args)=>{globalThis.sent={action,args}};globalThis.protocol=records[0];globalThis.result=records[1];globalThis.proof=records[2];");
(async()=>{
let html=run('relayResultPanel(result,proof)');assert(html.includes('Fresh exact local replay: passed'));assert(html.includes('Scripted infrastructure test'));assert(html.includes('Interval unavailable'));assert(html.includes('No interaction p-value is defined'));assert(!html.includes('95%'));
for(const edit of ["proof.payload.result_ref.version=2","proof.payload.model_calls=false","proof.payload.passed=1","proof.payload.report_status='incomplete'","proof.payload.checks[0].passed='yes'"]){const before=JSON.stringify(c.records[2].payload);run(edit);assert(!run('exactRelayProof(result,proof)'));html=run('relayResultPanel(result,proof)');assert(!html.includes('Fresh exact local replay: passed'));assert(!html.includes('effect-number'));c.records[2].payload=JSON.parse(before)}
run("result.payload.raw_report.runs[0].run_id='<img onerror=evil()>';result.payload.raw_report.runs[0].outcomes=null;result.payload.status='incomplete';proof.payload.passed=false");html=run('relayResultPanel(result,proof)');assert(html.includes('&lt;img onerror=evil()&gt;'));assert(!html.includes('<img onerror'));assert(html.includes('Unknown'));assert(!html.includes('effect-number'));
run("app.state.objects=app.state.objects.filter(o=>o.kind!=='revision_relay_experiment');app.state.jobs=[];app.live=true;protocol.payload.protocol.subject_backend={harness:'responses',model:'fixture-model'};sent=null");
assert.throws(()=>run('relayExecutionGuard(protocol)'),/cap/);
run("app.state.usage.calls=0;app.live=false");assert.throws(()=>run('relayExecutionGuard(protocol)'),/mode/);
run("app.live=true;protocol.payload.protocol.subject_backend.model='different-model'");assert.throws(()=>run('relayExecutionGuard(protocol)'),/mode/);
run("protocol.payload.protocol.subject_backend.model='fixture-model';app.state.jobs=[{payload:{protocol_ref:{id:protocol.id,version:protocol.version,hash:protocol.hash}}}]");assert.throws(()=>run('relayExecutionGuard(protocol)'),/already/);
run("app.state.jobs=[]");let args=run('relayExecutionGuard(protocol)');assert.equal(args.protocol_version,1);assert.equal(args.live,true);
await listeners.click({target:button({action:'experiment-revision-relay',id:c.records[0].id,version:'1'})});assert.equal(c.sent.action,'experiment_revision_relay');assert.equal(c.sent.args.protocol_version,1);
run('sent=null');await listeners.click({target:button({action:'audit-revision-relay',id:c.records[1].id,version:'1'})});assert.equal(c.sent.action,'audit_revision_relay');assert.equal(c.sent.args.version,1);assert(!('live' in c.sent.args));assert(!('harness' in c.sent.args));
run("sent=null;app.relayBlocks='65';app.relaySeed='173'");await listeners.submit({target:{id:'revision-relay-design-form'},preventDefault(){}});assert.equal(c.sent,null);
run("app.relayBlocks='2';app.relaySeed='9007199254740992'");await listeners.submit({target:{id:'revision-relay-design-form'},preventDefault(){}});assert.equal(c.sent,null);
run("app.relaySeed='173'");await listeners.submit({target:{id:'revision-relay-design-form'},preventDefault(){}});assert.equal(c.sent.action,'design_revision_relay');assert.equal(c.sent.args.blocks,2);assert(!('interval_assumptions' in c.sent.args));
run("sent=null;app.state.supported_actions=[]");await listeners.submit({target:{id:'revision-relay-design-form'},preventDefault(){}});assert.equal(c.sent,null);
console.log('Exact relay proof, incomplete unknowns, inert text, full-grid budget and bounded public actions passed');
})().catch(error=>{console.error(error.stack);process.exitCode=1});
'''


@unittest.skipUnless(NODE,'Node required for executable UI checks')
class RevisionRelayUITests(unittest.TestCase):
    def records(self):
        protocol={'id':'revision_relay_protocol-fixture','version':1,'hash':'a'*64,
            'kind':'revision_relay_protocol','payload':{'protocol':{
                'study_kind':'paired_revision_relay_factorial','design':{'blocks':2,'maximum_teams':8,'maximum_subject_calls':32},
                'subject_backend':{'harness':'scripted','model':'fixture-policy'}}}}
        result={'id':'revision_relay_experiment-fixture','version':1,'hash':'b'*64,
            'kind':'revision_relay_experiment','payload':{'status':'complete','agent_mode':'scripted_infrastructure',
                'analysis':{'mean_interaction':0,'p_value':None,'interaction_randomization_test':None,
                    'interval':{'available':False,'bounds':None,'alpha':0.05,
                        'method':'conditional_independent_block_Hoeffding','assumptions_attested':False,
                        'assumptions':{'independent_blocks_declared':False,'stable_subject_backend_declared':False}}},
                'raw_report':{'status':'complete','runs':[{'run_id':'relay-0001-0','block_id':'block-0001',
                    'timing':'early','bypass':'sham','status':'complete','outcomes':{'C_final_correct':1},
                    'counts':{'subject_call_attempts':4}}]},
                'protocol_ref':{k:protocol[k] for k in ('id','version','hash')}}}
        proof={'id':'verification-fixture','version':1,'hash':'c'*64,'kind':'verification','payload':{
            'result_kind':result['kind'],'result_ref':{k:result[k] for k in ('id','version','hash')},
            'passed':True,'model_calls':0,'report_status':'complete','complete_execution':True,
            'quantitative_available':True,'partial_trace_consistent':False,'checks':[{'name':'fresh','passed':True}]}}
        return [protocol,result,proof]

    def test_version_budget_missingness_and_action_handlers(self):
        process=subprocess.run([NODE,'-e',SCRIPT],input=json.dumps(self.records()),text=True,
            capture_output=True,cwd=ROOT)
        self.assertEqual(process.returncode,0,process.stderr)


if __name__=='__main__':unittest.main()
