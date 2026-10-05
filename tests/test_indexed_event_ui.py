"""Execute inert indexed-event views and exact-version job handlers in Node."""
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
run("app.state={objects:records.map(o=>({id:o.id,kind:o.kind,version:o.version,hash:o.hash,summary:{name:o.kind}})),jobs:[],usage:{calls:397},max_calls:400,model:'test'};app.live=true;submit=async(action,args)=>{globalThis.sent={action,args}};globalThis.record=records[0];globalThis.proof=records[1];globalThis.index=records[2];globalThis.selection=records[3];");
(async()=>{
let html=run('indexedEventPanel(record,proof)');
assert(html.includes('Counts below are recorded audit output'));assert(!html.includes('Recorded fresh local-index replay: passed'));
assert(html.includes('human speakers'));assert(html.includes('human emissions'));assert(html.includes('Partial'));assert(html.includes('Complete within index'));
assert(html.includes('WAIT'));assert(html.includes('PAUSE'));assert(html.includes('START'));assert(html.includes('STOP'));
assert(html.includes('&lt;script&gt;inert&lt;/script&gt;'));assert(!html.includes('<script>inert</script>'));
run('proof.payload.audit_ref.version=record.version');html=run('indexedEventPanel(record,proof)');assert(html.includes('Recorded fresh local-index replay: passed'));
for(const change of ["proof.payload.model_calls=false","proof.payload.full_event_source_reread=true","proof.payload.index_artifact_reread_completed=false","proof.payload.audit_ref.hash='b'.repeat(64)"]){
 const before=JSON.stringify(c.records[1].payload);run(change);assert(!run('exactIndexedProof(record,proof)'));c.records[1].payload=JSON.parse(before);
}
assert.equal(run("uniqueIds(['event_source_index-test','indexed_event_audit-test']).length"),2);
assert(run('indexInspectionPanel(index)').includes('Partial'));assert(run('coherentIndexedSelection(index,selection)'));
await run("openObject('event_source_index-test')");assert(node('evidence-dialog').open);assert(node('dialog-body').innerHTML.includes('Exact index registry identity'));
await run("openObject('indexed_event_audit-test')");assert(node('dialog-body').innerHTML.includes('Exact indexed audit registry identity'));
await run("openObject('verification-indexed-test')");assert(node('dialog-body').innerHTML.includes('Exact local-index replay identity and limits'));
await listeners.click({target:button({action:'replay-indexed-events',id:c.records[0].id,version:'1'})});
assert.equal(c.sent.action,'replay_indexed_events');assert.equal(c.sent.args.audit_id,c.records[0].id);assert.equal(c.sent.args.version,1);assert(!('live' in c.sent.args));assert(!('harness' in c.sent.args));
run("app.selected.event_source_index=index.id;app.selected.selected_lead_audit=selection.id;app.indexVersion='2';app.indexSelectedVersion='3';app.indexQueryRows='15000';");
await listeners.submit({target:{id:'indexed-event-audit-form'},preventDefault(){}});
assert.equal(c.sent.action,'audit_indexed_events');assert.equal(c.sent.args.index_version,2);assert.equal(c.sent.args.selected_audit_version,3);assert.equal(c.sent.args.index_id,c.records[2].id);assert.equal(c.sent.args.selected_audit_id,c.records[3].id);assert.equal(c.sent.args.max_query_rows,15000);assert(!('live' in c.sent.args));
run("sent=null;app.indexQueryRows='15001'");await listeners.submit({target:{id:'indexed-event-audit-form'},preventDefault(){}});assert.equal(c.sent,null);assert(node('toast').textContent.includes('positive integer'));
run("app.indexQueryRows=2;selection.payload.source_refs.dataset.hash='bad';sent=null");await listeners.submit({target:{id:'indexed-event-audit-form'},preventDefault(){}});assert.equal(c.sent,null);assert(node('toast').textContent.includes('coherent selected-audit'));
run("selection.payload.source_refs.dataset.hash='d'.repeat(64)");html=await run('indexedEventAuditSection()');assert(html.includes('indexed-event-audit-form'));assert(html.includes('does not scan') || html.includes('No remote full-source scan'));
run("app.indexVersion='1.5'");html=await run('indexedEventAuditSection()');assert(html.includes('indexed-event-audit-form'));assert(html.includes('Correct the version above'));assert(/type="submit" disabled/.test(html));
console.log('Indexed event counts/coverage, strict bound proof, inert views and zero-call versioned handlers passed');
})().catch(error=>{console.error(error.stack);process.exitCode=1});
'''


@unittest.skipUnless(NODE, 'Node required for executable UI contracts')
class IndexedEventUITests(unittest.TestCase):
    def test_exact_proof_partial_coverage_escaping_and_existing_index_actions(self):
        record = {'id':'indexed_event_audit-test', 'kind':'indexed_event_audit', 'version':1, 'hash':'a'*64,
                  'payload':{'index_ref':{'id':'event_source_index-test','version':2,'hash':'c'*64},
                    'indexed_event_audit':{'counts':{'selected_chat_records':3,'projected_event_records':2,
                      'emission_statuses':{'matched':1,'unknown':2,'conflict':0},
                      'selected_chat_by_speaker_type':{'agent':2,'user':1},
                      'emission_statuses_by_speaker_type':{'agent':{'matched':1,'unknown':1,'conflict':0},'user':{'matched':0,'unknown':1,'conflict':0}}},
                      'coverage':{'build_scan':{'complete_scan':False,'stop_reason':'row_limit','indexed_rows':5},
                        'query_complete':True,'returned_rows':2,'matched_rows':2,'truncated':False},
                      'windows':[{'id':'window-test','start':'2025-04-02T10:00:00Z','end_exclusive':'2025-04-02T11:00:00Z',
                        'selected_chat_records':3,'emission_status_counts':{'matched':1,'unknown':2,'conflict':0},
                        'platform_actions':{'WAIT':1,'PAUSE':0,'START_USING_COMPUTER':1,'STOP_USING_COMPUTER':0}}],
                      'emissions':[{'message_id':'message-test','parent_source':{'line':7},'emission_status':'matched',
                        'candidate_count':1,'field_checks':[{'event_field':'<script>inert</script>','status':'matching'}]}]}}}
        proof = {'id':'verification-indexed-test','kind':'verification','version':1,'payload':{
            'audit_ref':{'id':record['id'],'version':2,'hash':record['hash']},'result_kind':'indexed_event_audit',
            'passed':True,'model_calls':0,'index_artifact_reread_attempted':True,
            'index_artifact_reread_completed':True,'full_event_source_reread':False}}
        index = {'id':'event_source_index-test','kind':'event_source_index','version':2,'hash':'c'*64,
                 'payload':{'build_metadata':{'artifact':{'file_sha256':'e'*64,'bytes':4096},
                   'coverage':{'complete_scan':False,'stop_reason':'row_limit','indexed_rows':5,'physical_rows_seen':5}}}}
        selection = {'id':'selected_lead_audit-test','kind':'selected_lead_audit','version':3,'hash':'f'*64,
                     'payload':{'source_refs':{'dataset':{'id':'dataset-test','version':1,'hash':'d'*64},
                      'discovery':{'id':'discovery-test','version':2,'hash':'e'*64}},'window_measurements':{'w':{}}}}
        result = subprocess.run([NODE,'-e',SCRIPT],input=json.dumps([record,proof,index,selection]),
                                text=True,capture_output=True,cwd=ROOT)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__ == '__main__':
    unittest.main()
