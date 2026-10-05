"""Exact audit-version binding, inert rendering and zero-call replay action."""
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
const run=s=>vm.runInContext(s,c);
run("app.state={objects:records.map(o=>({id:o.id,kind:o.kind,version:o.version,hash:o.hash,summary:{name:o.kind}})),jobs:[],usage:{calls:397},max_calls:400,model:'test'};app.live=true;submit=async(action,args)=>{globalThis.sent={action,args}};globalThis.record=records[0];globalThis.proof=records[1];");
(async()=>{
let html=run('sourceLineagePanel(record,proof)');
assert(html.includes('No replay record selected'));assert(!html.includes('Recorded fresh filesystem replay: passed'));
assert(html.includes('Partial'));assert(html.includes('cannot estimate prevalence'));assert(html.includes('consumption'));
assert(html.includes('&lt;script&gt;inert&lt;/script&gt;'));assert(!html.includes('<script>inert</script>'));
assert.equal(run("uniqueIds(['source_link_audit-test']).length"),1);
run('proof.payload.audit_ref.version=1');html=run('sourceLineagePanel(record,proof)');assert(html.includes('Recorded fresh filesystem replay: passed'));
run("proof.payload.audit_ref.hash='b'.repeat(64)");html=run('sourceLineagePanel(record,proof)');assert(!html.includes('Recorded fresh filesystem replay: passed'));
await run("openObject('source_link_audit-test')");assert(node('evidence-dialog').open);assert(node('dialog-body').innerHTML.includes('Exact audit identity and scan plan'));
const target={dataset:{action:'replay-source-links',id:'source_link_audit-test',version:'1'},closest(){return this},hasAttribute(){return false}};
await listeners.click({target});assert.equal(c.sent.action,'replay_source_links');assert.equal(c.sent.args.audit_id,'source_link_audit-test');assert.equal(c.sent.args.version,1);assert(!('live' in c.sent.args));
console.log('Exact source replay binding, inert source rendering and zero-call action passed');
})().catch(error=>{console.error(error.stack);process.exitCode=1});
'''


@unittest.skipUnless(NODE, 'Node required for UI contracts')
class SourceDashboardTests(unittest.TestCase):
    def test_exact_binding_escaping_and_mode_independent_replay(self):
        record = {'id': 'source_link_audit-test', 'version': 1, 'kind': 'source_link_audit', 'hash': 'a'*64,
                  'payload': {'source_link_audit': {'counts': {'retained_rows': 2, 'relations': 1,
                      'relation_statuses': {'verified_exported_fk': 1}}, 'relations': [{
                      'relation_kind': 'turn_session_fk', 'status': 'verified_exported_fk',
                      'child_source': {'table': 'computer_use_turns', 'line': 3},
                      'parent_source': {'table': 'computer_use_sessions', 'line': 5},
                      'field_checks': [{'child_field': '<script>inert</script>', 'status': 'matching'}]}]},
                      'source_readset': {'computer_use_turns': {'coverage': {'physical_rows_seen': 3,
                          'retained_rows': 1, 'complete_scan': False, 'stop_reason': 'row_limit'}}}}}
        proof = {'id': 'verification-test', 'version': 1, 'kind': 'verification', 'payload': {
            'audit_ref': {'id': record['id'], 'version': 2, 'hash': record['hash']},
            'result_kind': 'source_link_audit', 'passed': True, 'reason': 'reproduced', 'scope': 'Bounded bytes only'}}
        result = subprocess.run([NODE, '-e', SCRIPT], input=json.dumps([record, proof]),
                                text=True, capture_output=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
