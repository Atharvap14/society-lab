"""Independent, offline Node-VM probes of the optional relay UI boundary.

Only local source is executed with inert DOM/fetch/submit fixtures. Nothing is
sent to the server, providers or production registry.
"""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which('node')
SCRIPT = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const records=JSON.parse(fs.readFileSync(0,'utf8')),nodes=new Map(),listeners={},requests=[];
function node(id){if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',open:false,
 classList:{toggle(){},remove(){},add(){}},addEventListener(){},showModal(){this.open=true},
 close(){this.open=false},contains(){return false},querySelector(){return null}});return nodes.get(id)}
const latest=new Map(),byVersion=new Map();
for(const o of records){byVersion.set(o.id+'@'+o.version,o);if(!latest.has(o.id)||latest.get(o.id).version<o.version)latest.set(o.id,o)}
const c={console,records,nodes,Map,Set,Date,JSON,Math,Number,String,Array,Object,Promise,
 CSS:{escape:x=>x},setTimeout:()=>0,clearTimeout(){},setInterval:()=>0,
 window:{scrollTo(){}},document:{getElementById:node,querySelector:node,querySelectorAll:()=>[],
 activeElement:null,addEventListener:(event,f)=>{const previous=listeners[event];
   listeners[event]=previous?async e=>{await previous(e);await f(e)}:f}},
 fetch:async path=>{requests.push(path);const url=new URL(path,'http://fixture.invalid');
   const id=decodeURIComponent(url.pathname.split('/').pop()),v=url.searchParams.get('version');
   const record=v?byVersion.get(id+'@'+Number(v)):latest.get(id);
   if(!record)throw Error('Unexpected fixture fetch');return {ok:true,json:async()=>record}}};
vm.createContext(c);
const appSource=fs.readFileSync('web/app.js','utf8');
vm.runInContext(appSource.slice(0,appSource.lastIndexOf('\nrefresh(true);')),c);
vm.runInContext(fs.readFileSync('web/revision-relay.js','utf8'),c);
const run=s=>vm.runInContext(s,c),button=dataset=>({dataset,closest(){return this},hasAttribute(){return false}});
c.latestRecords=[...latest.values()];
run(`app.state={objects:latestRecords.map(o=>({id:o.id,kind:o.kind,version:o.version,hash:o.hash,
 summary:{name:o.kind,protocol_ref:o.payload.protocol_ref}})),jobs:[],usage:{calls:0,completed:0},
 max_calls:400,model:'fixture-model',supported_actions:['design_revision_relay','experiment_revision_relay','audit_revision_relay']};
 app.live=false;globalThis.protocol=records[0];globalThis.result=records[1];globalThis.proof=records[2];
 globalThis.sent=[];submit=async(action,args)=>{sent.push({action,args})};render=async()=>{};`);

const cases={
 proof_boundary:async()=>{
   assert(run('exactRelayProof(result,proof)'));
   for(const edit of ["proof.payload.complete_execution=false","delete proof.payload.complete_execution",
     "proof.payload.quantitative_available=false","proof.payload.partial_trace_consistent=true",
     "proof.payload.result_ref.hash='0'.repeat(64)","proof.payload.result_ref.version=1001",
     "proof.payload.model_calls=false","proof.payload.passed=1","proof.payload.checks[0].passed='yes'"]){
      const before=JSON.stringify(c.records[2].payload);run(edit);
      assert(!run('exactRelayProof(result,proof)'),edit);
      assert(!run('relayResultPanel(result,proof)').includes('effect-number'),edit);
      c.records[2].payload=JSON.parse(before);
   }
 },
 machine_versions:async()=>{
   const html=run('relayResultPanel(result,proof)');
   assert(html.includes('data-relay-version="1000"'),'Run link must use canonical version, not locale grouping');
   assert(html.includes('data-version="1000"'),'Audit action must use canonical version');
   run("app.selected.revision_relay_protocol=protocol.id;app.relayProtocolVersion=1000;app.state.objects=app.state.objects.filter(o=>o.kind!=='revision_relay_experiment');app.state.jobs=[]");
   const view=await run('revisionRelayExperiments()');
   assert(view.includes('data-version="1000"'),'Execution action must use canonical version');
   assert(!view.includes('data-version="1,000"'));
 },
 historical_navigation:async()=>{
   await run('openObject(proof.id,proof.version)');
   assert.equal(run('app.relayResultVersion'),1000);
   assert.equal(run('app.relayProtocolVersion'),1000);
   assert.equal(run('app.experimentStudy'),'revision_relay');
   await run('showRevisionRelayRun(result.id,1000,"run-old")');
   assert(nodes.get('dialog-body').innerHTML.includes('run-old'));
   assert(!nodes.get('dialog-body').innerHTML.includes('run-new'));
   assert(requests.some(p=>p.includes('?version=1000')));
   assert.equal(await run('object(result.id,1000).then(o=>o.version)'),1000);
 },
 fetched_request_identity:async()=>{
   run("app.state.objects=[];app.state.jobs=[];object=async()=>({...protocol,version:1001})");
   await listeners.click({target:button({action:'experiment-revision-relay',id:c.records[0].id,version:'1000'})});
   assert.equal(run('sent.length'),0,'Wrong fetched version must fail before submission');
   run("object=async()=>({...protocol,id:'different-protocol'})");
   await listeners.click({target:button({action:'experiment-revision-relay',id:c.records[0].id,version:'1000'})});
   assert.equal(run('sent.length'),0,'Wrong fetched ID must fail before submission');
   run("object=async()=>({...result,id:'different-result'})");
   await listeners.click({target:button({action:'audit-revision-relay',id:c.records[1].id,version:'1000'})});
   assert.equal(run('sent.length'),0,'Wrong fetched result ID must fail before audit submission');
 },
 queued_study_and_call_budget:async()=>{
   run("app.state.objects=[];app.state.jobs=[{status:'queued',payload:{action:'experiment_revision_relay',args:{protocol_id:protocol.id,protocol_version:1000,live:false}}}]");
   assert.throws(()=>run('relayExecutionGuard(protocol)'),/already|launched|queued/i);
   run('app.state.jobs[0].payload.args.protocol_version=1001');
   assert.equal(run('relayExecutionGuard(protocol).protocol_version'),1000);
   run("app.state.jobs=[];app.live=true;protocol.payload.protocol.subject_backend={harness:'responses',model:'fixture-model'};app.state.usage={calls:385,completed:0}");
   assert.throws(()=>run('relayExecutionGuard(protocol)'),/cap/);
   run('app.state.usage.calls=384');assert(run('relayExecutionGuard(protocol).live'));
   run('app.live=false');assert.throws(()=>run('relayExecutionGuard(protocol)'),/mode/);
   run("app.live=true;protocol.payload.protocol.subject_backend.model='other-model'");
   assert.throws(()=>run('relayExecutionGuard(protocol)'),/model|mode/);
 },
 unknown_scores_and_inert_markup:async()=>{
   run("proof.payload.passed=false;proof.payload.complete_execution=false;proof.payload.quantitative_available=false;proof.payload.partial_trace_consistent=true;result.payload.status='incomplete';result.payload.raw_report.status='incomplete';result.payload.analysis=null;result.payload.raw_report.runs=[{run_id:'<img onerror=evil()>',block_id:'block-old',timing:'early',bypass:'sham',status:'incomplete',outcomes:null,counts:{subject_call_attempts:2}},{run_id:'known-zero',block_id:'block-old',timing:'late',bypass:'sham',status:'complete',outcomes:{C_final_correct:0},counts:{subject_call_attempts:4}},{run_id:'typed-unknown',block_id:'block-old',timing:'early',bypass:'informative',status:'incomplete',outcomes:{C_final_correct:false},counts:{subject_call_attempts:null}}]");
   const html=run('relayResultPanel(result,proof)');
   assert(!html.includes('effect-number'));assert(!html.includes('Fresh exact local replay: passed'));
   assert(html.includes('&lt;img onerror=evil()&gt;'));assert(!html.includes('<img onerror'));
   const rows=[...html.matchAll(/<tr><td><button[^]*?<\/tr>/g)].map(m=>m[0]);
   assert.equal(rows.length,3);assert(rows[0].includes('<td>Unknown</td>'));
   assert(rows[1].includes('<td>0</td>'));assert(rows[2].includes('<td>Unknown</td>'));
   assert(html.includes('Scripted infrastructure test'));
 },
 interval_scope_and_malformed_bounds:async()=>{
   let html=run('relayResultPanel(result,proof)');assert(html.includes('Interval unavailable'));
   assert(!html.includes('95%'));assert(html.includes('No interaction p-value is defined'));
   run("result.payload.analysis.interval={available:true,bounds:[-1,1],alpha:.05,method:'conditional_independent_block_Hoeffding',assumptions:{independent_blocks_declared:true,stable_subject_backend_declared:true},assumptions_attested:false}");
   html=run('relayResultPanel(result,proof)');assert(html.includes('Conditional bounds:'));
   assert(html.includes('declared assumptions, not verified'));assert(!html.includes('95%'));
   for(const bounds of [null,[false,1],['-1',1],[1,-1],[null,1],[Infinity,1]]){
     c.badBounds=bounds;run('result.payload.analysis.interval.bounds=badBounds');
     html=run('relayResultPanel(result,proof)');
     assert(!html.includes('Conditional bounds:'),'Malformed bounds cannot be advertised as an interval');
   }
 },
 form_numeric_and_mode_boundary:async()=>{
   for(const blocks of [true,false,null,'',0,65,2.1,Infinity,NaN,'<svg onload=evil()>']){
     c.badBlocks=blocks;run('app.relayBlocks=badBlocks;app.relaySeed=173;sent=[]');
     await listeners.submit({target:{id:'revision-relay-design-form'},preventDefault(){}});
     assert.equal(run('sent.length'),0,'Invalid blocks must not submit');
   }
   for(const seed of [true,null,'',-1,1.5,9007199254740992,Infinity]){
     c.badSeed=seed;run('app.relayBlocks=1;app.relaySeed=badSeed;sent=[]');
     await listeners.submit({target:{id:'revision-relay-design-form'},preventDefault(){}});
     assert.equal(run('sent.length'),0,'Invalid seed must not submit');
   }
   run("app.relayBlocks=1;app.relaySeed=0;app.live=false;sent=[]");
   await listeners.submit({target:{id:'revision-relay-design-form'},preventDefault(){}});
   assert.equal(run('sent.length'),1);assert.equal(run('sent[0].args.live'),false);
   assert.equal(run("'interval_assumptions' in sent[0].args"),false);
 }
};
(async()=>{const name=process.argv[1];await cases[name]();console.log(name+' passed');})()
 .catch(error=>{console.error(error.stack);process.exitCode=1});
'''


@unittest.skipUnless(NODE, 'Node required for independent local UI probes')
class RevisionRelayUIIndependentTests(unittest.TestCase):
    def records(self):
        p = {'id': 'revision_relay_protocol-fixture', 'version': 1000, 'hash': 'a' * 64,
            'kind': 'revision_relay_protocol', 'payload': {'protocol': {
                'study_kind': 'paired_revision_relay_factorial',
                'design': {'blocks': 1, 'maximum_teams': 4, 'maximum_subject_calls': 16},
                'subject_backend': {'harness': 'scripted', 'model': 'fixture-policy'}}}}
        r = {'id': 'revision_relay_experiment-fixture', 'version': 1000, 'hash': 'b' * 64,
            'kind': 'revision_relay_experiment', 'payload': {'status': 'complete',
                'agent_mode': 'scripted_infrastructure', 'protocol_ref': {k: p[k] for k in ('id', 'version', 'hash')},
                'analysis': {'mean_interaction': 0, 'p_value': None, 'interaction_randomization_test': None,
                    'interval': {'available': False, 'bounds': None, 'alpha': .05,
                        'method': 'conditional_independent_block_Hoeffding', 'assumptions_attested': False,
                        'assumptions': {'independent_blocks_declared': False, 'stable_subject_backend_declared': False}}},
                'raw_report': {'status': 'complete', 'runs': [{'run_id': 'run-old',
                    'block_id': 'block-old', 'timing': 'early', 'bypass': 'sham', 'status': 'complete',
                    'outcomes': {'C_final_correct': 0}, 'counts': {'subject_call_attempts': 4}}]}}}
        proof = {'id': 'verification-old', 'version': 1, 'hash': 'c' * 64, 'kind': 'verification',
            'payload': {'result_kind': r['kind'], 'result_ref': {k: r[k] for k in ('id', 'version', 'hash')},
                'passed': True, 'model_calls': 0, 'report_status': 'complete', 'complete_execution': True,
                'quantitative_available': True, 'partial_trace_consistent': False,
                'checks': [{'name': 'exact', 'passed': True}]}}
        p_new, r_new, proof_new = copy.deepcopy([p, r, proof])
        p_new.update(version=1001, hash='d' * 64)
        r_new.update(version=1001, hash='e' * 64)
        r_new['payload']['protocol_ref'] = {k: p_new[k] for k in ('id', 'version', 'hash')}
        r_new['payload']['analysis']['mean_interaction'] = 1
        r_new['payload']['raw_report']['runs'][0].update(run_id='run-new', block_id='block-new')
        proof_new.update(id='verification-new', hash='f' * 64)
        proof_new['payload']['result_ref'] = {k: r_new[k] for k in ('id', 'version', 'hash')}
        return [p, r, proof, p_new, r_new, proof_new]

    def probe(self, name):
        result = subprocess.run([NODE, '-e', SCRIPT, name], input=json.dumps(self.records()),
            cwd=ROOT, text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_proof_boundary(self): self.probe('proof_boundary')
    def test_machine_versions(self): self.probe('machine_versions')
    def test_historical_navigation(self): self.probe('historical_navigation')
    def test_fetched_request_identity(self): self.probe('fetched_request_identity')
    def test_queued_study_and_call_budget(self): self.probe('queued_study_and_call_budget')
    def test_unknown_scores_and_inert_markup(self): self.probe('unknown_scores_and_inert_markup')
    def test_interval_scope_and_malformed_bounds(self): self.probe('interval_scope_and_malformed_bounds')
    def test_form_numeric_and_mode_boundary(self): self.probe('form_numeric_and_mode_boundary')


if __name__ == '__main__': unittest.main()
