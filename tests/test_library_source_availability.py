"""Actual library rendering retains records without inventing source availability."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which('node')

SCRIPT = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync(process.argv[1],'utf8'),scenario=process.argv[2],nodes=new Map(),requests=[];
function node(id){if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',open:false,classList:{toggle(){},remove(){}},addEventListener(){},contains(){return false},querySelector(){return null}});return nodes.get(id)}
const record={id:'behavior-retained',version:1,hash:'a'.repeat(64),kind:'behavior',summary:{status:'candidate'},payload:{
 name:'Retained candidate',summary:'Record remains readable',operational_definition:'Source interpretation remains unproved',
 status:'candidate',experiment_fit:'shared_artifact_coordination',fit_reason:'<script>unsafe-fit()</script>',
 skeptic:{summary:'Retained independent critique',recommended_status:'needs_more_evidence'},evidence_ids:['m1'],
 dataset_id:'dataset-original',candidate_id:'graph-lead-fixture',source_refs:{
 dataset:{id:'dataset-original',version:2,hash:'b'.repeat(64)},discovery:{id:'discovery-original',version:1,hash:'c'.repeat(64)}}}};
const dataset={id:'dataset-original',version:2,hash:'b'.repeat(64),kind:'dataset',payload:{messages:[
 {id:'m1',content:'Exact source text <img onerror="unsafe()">',room_id:'room',timestamp:'2025-04-18T18:00:00Z',agent_name:'A'}]}};
let returned=dataset,missing=false;
if(scenario==='missing_pin')delete record.payload.source_refs.dataset;
if(scenario==='missing_dataset')missing=true;
if(scenario==='unavailable_pinned_version')missing=true;
if(scenario==='undeclared'){delete record.payload.dataset_id;delete record.payload.source_refs.dataset;}
if(['declared_false','declared_zero','declared_blank'].includes(scenario)){delete record.payload.source_refs.dataset;record.payload.dataset_id=scenario==='declared_false'?false:scenario==='declared_zero'?0:'';}
if(scenario==='different_id')record.payload.dataset_id='dataset-other';
if(scenario==='wrong_hash')returned={...dataset,hash:'d'.repeat(64)};
if(scenario==='returned_latest')returned={...dataset,version:3};
if(scenario==='wrong_kind')returned={...dataset,kind:'discovery'};
if(scenario==='missing_record')returned={...dataset,payload:{messages:[]}};
if(scenario==='invalid_version')record.payload.source_refs.dataset.version=true;
if(scenario==='rejected_exact')record.payload.status='rejected';
const c={Map,Set,Date,JSON,Math,Number,String,Array,Object,Promise,CSS:{escape:x=>x},record,
 document:{getElementById:node,querySelector:node,querySelectorAll:()=>[],activeElement:null,addEventListener(){}},
 fetch:async path=>{requests.push(path);assert.equal(path,'/api/object/dataset-original?version=2','A latest or alternate dataset was requested');
   return {ok:!missing,status:missing?404:200,json:async()=>missing?{error:'<script>remote-secret-error()</script>'}:returned};},
 setTimeout(){throw Error('Unexpected timer')},clearTimeout(){},setInterval(){throw Error('Unexpected timer')}};
vm.createContext(c);const end=source.lastIndexOf('\nrefresh(true);');assert.ok(end>0);vm.runInContext(source.slice(0,end),c);
vm.runInContext("app.state={objects:[record],jobs:[],usage:{calls:400},max_calls:400};app.cache.set(record.id,record);app.selected.behavior=record.id;app.libraryKind='behavior';app.view='library';app.live=false;submit=()=>{throw Error('Unexpected job')};",c);
(async()=>{
 const before=JSON.stringify(record),stateBefore=vm.runInContext('JSON.stringify(app.state)',c),html=await vm.runInContext('library()',c);
 assert.ok(html.includes('Retained candidate'));assert.ok(html.includes('Retained independent critique'));
 assert.ok(html.includes('Artifact workflow screening'));assert.ok(html.includes('data-history="behavior-retained"'));
 assert.ok(html.includes('&lt;script&gt;unsafe-fit()&lt;/script&gt;'));assert.ok(!html.includes('<script>'));
 const button=html.match(/<button[^>]*data-design-behavior="behavior-retained"[^>]*>/);assert.ok(button);
 const available=['exact','rejected_exact'].includes(scenario);
 assert.equal(/\bdisabled\b/.test(button[0]),!available || scenario==='rejected_exact');
 assert.equal(html.includes('data-episode-lead='),available,'Source-dependent episode action did not follow availability');
 if(available){assert.ok(html.includes('Referenced dataset version 2 is available'));assert.ok(html.includes('Exact source text &lt;img onerror=&quot;unsafe()&quot;&gt;'));}
 else{assert.ok(html.includes(scenario==='undeclared'?'Source evidence unknown':'Source evidence unavailable'));
   assert.ok(!html.includes('Exact source text'));assert.ok(!html.includes('No source record IDs are cited'));
   assert.ok(html.includes('The behavior, critique and history remain readable'));
   assert.ok(!html.includes('remote-secret-error'),'Technical remote error was exposed');}
 const noRead=['missing_pin','undeclared','different_id','invalid_version','declared_false','declared_zero','declared_blank'].includes(scenario);
 assert.equal(requests.length,noRead?0:1);assert.equal(JSON.stringify(record),before);
 assert.equal(vm.runInContext('JSON.stringify(app.state)',c),stateBefore);assert.equal(vm.runInContext('app.live',c),false);
 process.stdout.write(JSON.stringify({passed:true,scenario,requests:requests.length}));
})().catch(error=>{console.error(error.stack);process.exitCode=1});
'''


@unittest.skipUnless(NODE, 'Node is required for actual library renderer checks')
class LibrarySourceAvailabilityTests(unittest.TestCase):
    def check(self, scenario):
        result = subprocess.run([NODE,'-e',SCRIPT,str(ROOT/'web'/'app.js'),scenario],
            capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(json.loads(result.stdout)['passed'])

    def test_absent_unavailable_and_undeclared_sources_retain_the_record_without_latest_fallback(self):
        for scenario in ('missing_pin','missing_dataset','unavailable_pinned_version','undeclared'):
            with self.subTest(scenario=scenario): self.check(scenario)

    def test_returned_identity_and_cited_membership_fail_closed_without_substitute_evidence(self):
        for scenario in ('different_id','wrong_hash','returned_latest','wrong_kind','missing_record','invalid_version','declared_false','declared_zero','declared_blank'):
            with self.subTest(scenario=scenario): self.check(scenario)

    def test_exact_source_renders_escaped_evidence_and_preserves_rejected_design_gate(self):
        for scenario in ('exact','rejected_exact'):
            with self.subTest(scenario=scenario): self.check(scenario)


if __name__=='__main__':
    unittest.main(verbosity=2)
