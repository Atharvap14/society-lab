"""Actual dashboard registration routes with inert API stubs and exact pins."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from tests.test_blueprint_registration_preview_independent import fixture

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which('node')

PRELUDE = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const packet=JSON.parse(fs.readFileSync(0,'utf8')),nodes=new Map(),listeners={},requests=[];
function node(id){if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',open:false,value:'',dataset:{},classList:{toggle(){},remove(){}},addEventListener(){},scrollIntoView(){},close(){this.open=false},contains(){return false},querySelector(){return null}});return nodes.get(id)}
const record={...packet.blueprint_ref,kind:'environment_blueprint',payload:{construction_status:'compiled',experiment_eligibility:'approved_analogue'}};
const other={...record,id:'environment_blueprint-other',hash:'c'.repeat(64)};
let renders=0,refreshes=0;
let fetchImpl=async(path,settings)=>{
 if(path.startsWith('/api/blueprint-registration-preview?'))return {ok:true,json:async()=>packet};
 if(path==='/api/jobs')return {ok:true,json:async()=>({job_id:'job-authored-registration'})};
 throw Error('Unexpected API request '+path);
};
const c={console,record,other,packet,Map,Set,Date,JSON,Math,Number,String,Array,Object,Promise,URLSearchParams,CSS:{escape:x=>x},setTimeout:()=>0,clearTimeout(){},setInterval:()=>0,
 document:{getElementById:node,querySelector:node,querySelectorAll:()=>[],activeElement:null,addEventListener:(event,fn)=>{const previous=listeners[event];listeners[event]=previous?async e=>{await previous(e);await fn(e)}:fn}},
 fetch:async(path,settings={})=>{requests.push({path,settings});return fetchImpl(path,settings)}};
vm.createContext(c);const appSource=fs.readFileSync('web/app.js','utf8');vm.runInContext(appSource.slice(0,appSource.lastIndexOf('\nrefresh(true);')),c);
vm.runInContext(fs.readFileSync('web/blueprint-registration-preview.js','utf8'),c);
const run=s=>vm.runInContext(s,c);
c.render=async()=>{renders++};c.refresh=async()=>{refreshes++};
run("app.state={objects:[record,other],jobs:[],usage:{calls:400},max_calls:400,csrf:'authored-csrf'};app.view='experiments';app.experimentStudy='authoring';app.selected.environment_blueprint=record.id;app.live=false;app.harness='codex'");
const button=(changes={})=>({disabled:false,dataset:{blueprintRegister:record.id,blueprintVersion:String(record.version),blueprintHash:record.hash,blueprintLive:'false',...changes},closest(){return this},hasAttribute(){return false}});
const click=target=>listeners.click({target});
const jobs=()=>requests.filter(r=>r.path==='/api/jobs');
const copy=x=>JSON.parse(JSON.stringify(x));
const settle=()=>new Promise(resolve=>setImmediate(resolve));
'''


@unittest.skipUnless(NODE, 'Node.js required for actual dashboard registration route checks')
class BlueprintRegistrationRouteTests(unittest.TestCase):
    def run_js(self, body):
        result = subprocess.run([NODE, '-e', PRELUDE+body], input=json.dumps(fixture()),
            text=True, capture_output=True, encoding='utf-8', cwd=ROOT, timeout=25)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)

    def test_exact_readonly_get_binds_source_and_plan_without_job_or_flag_change(self):
        self.run_js(r'''
(async()=>{
 const before=JSON.stringify(packet),loaded=await c.loadBlueprintRegistrationPreview(record);
 assert.equal(loaded.packet.preview_version,'registration-compatibility-preview-v1');assert.equal(requests.length,1);
 const q=new URL(requests[0].path,'http://localhost').searchParams;
 assert.equal(q.get('blueprint_id'),record.id);assert.equal(q.get('blueprint_version'),'3');assert.equal(q.get('blueprint_hash'),'a'.repeat(64));assert.equal(q.get('trials_per_cell'),'2');assert.equal(q.get('seed'),'4491');assert.equal(q.get('live'),'false');assert.equal([...q.keys()].length,6);
 assert.equal(requests[0].settings.method,undefined);assert.equal(jobs().length,0);assert.equal(run('app.registrationAttempts.size'),0);assert.equal(run('app.live'),false);assert.equal(run('app.harness'),'codex');assert.equal(JSON.stringify(packet),before);
})().catch(e=>{console.error(e.stack);process.exitCode=1});
''')

    def test_unapproved_and_design_blocked_preview_do_not_offer_or_queue_registration(self):
        self.run_js(r'''
(async()=>{
 const unapproved={...record,payload:{construction_status:'compiled',experiment_eligibility:'review_required'}};
 assert.equal(await c.loadBlueprintRegistrationPreview(unapproved),null);assert.equal(requests.length,0);assert.equal(run('app.registrationPreview'),null);
 packet.status='blocked';packet.design=null;packet.checks.design_compatible=false;packet.checks.exact_world_preserved=null;packet.reason={stage:'design',code:'custom_topology_not_registered',message:'Explicit custom graph has no registered design.'};
 const loaded=await c.loadBlueprintRegistrationPreview(record);assert.equal(loaded.packet.status,'blocked');
 const html=c.BlueprintRegistrationPreview.render(loaded.packet,loaded.expected);assert.ok(!html.includes('data-blueprint-register='));await click(button());assert.equal(jobs().length,0);assert.equal(run('app.registrationAttempts.size'),0);
})().catch(e=>{console.error(e.stack);process.exitCode=1});
''')

    def test_malformed_or_failed_get_discards_prior_preview_without_cached_fallback(self):
        self.run_js(r'''
(async()=>{
 await c.loadBlueprintRegistrationPreview(record);assert.ok(run('app.registrationPreview'));
 packet.design.maximum_units=999;const malformed=await c.loadBlueprintRegistrationPreview(record);assert.equal(malformed.packet,null);assert.equal(run('app.registrationPreview'),null);await click(button());assert.equal(jobs().length,0);
 packet.design.maximum_units=6;await c.loadBlueprintRegistrationPreview(record);assert.ok(run('app.registrationPreview'));
 fetchImpl=async()=>({ok:false,status:503,json:async()=>({error:'Current preview unavailable'})});
 const failed=await c.loadBlueprintRegistrationPreview(record);assert.equal(failed.packet,null);assert.ok(failed.error.includes('Current preview unavailable'));assert.equal(run('app.registrationPreview'),null);await click(button());assert.equal(jobs().length,0);
})().catch(e=>{console.error(e.stack);process.exitCode=1});
''')

    def test_exact_post_once_with_pending_and_queued_duplicate_guards(self):
        self.run_js(r'''
(async()=>{
 await c.loadBlueprintRegistrationPreview(record);let resolve;
 fetchImpl=async(path)=>{assert.equal(path,'/api/jobs');return new Promise(r=>{resolve=r})};
 const first=button(),waiting=click(first);await settle();assert.equal(jobs().length,1);assert.equal(first.disabled,true);assert.equal(run('[...app.registrationAttempts.values()][0].phase'),'pending');
 await click(button());assert.equal(jobs().length,1);
 const posted=JSON.parse(jobs()[0].settings.body);assert.equal(posted.action,'register_blueprint');assert.deepEqual(posted.args,{blueprint_id:record.id,blueprint_version:3,blueprint_hash:'a'.repeat(64),trials_per_cell:2,seed:4491,live:false});assert.equal(jobs()[0].settings.method,'POST');assert.equal(jobs()[0].settings.headers['X-Lab-Token'],'authored-csrf');
 resolve({ok:true,json:async()=>({job_id:'job-authored-registration'})});await waiting;
 assert.equal(run('[...app.registrationAttempts.values()][0].phase'),'queued');assert.equal(run('[...app.registrationAttempts.values()][0].job_id'),'job-authored-registration');await click(button());assert.equal(jobs().length,1);assert.equal(refreshes,1);
 const saved=run('app.registrationPreview'),attempt=run('[...app.registrationAttempts.values()][0]');assert.ok(!c.BlueprintRegistrationPreview.render(saved.packet,saved.expected,{registrationAttempt:attempt}).includes('data-blueprint-register='));
})().catch(e=>{console.error(e.stack);process.exitCode=1});
''')

    def test_stale_clicked_pins_current_mode_selection_and_view_reject_before_post(self):
        self.run_js(r'''
(async()=>{
 await c.loadBlueprintRegistrationPreview(record);
 for(const changed of [{blueprintRegister:other.id},{blueprintVersion:'4'},{blueprintHash:'c'.repeat(64)},{blueprintLive:'true'},{blueprintVersion:'3.0'}])await click(button(changed));
 run('app.live=true');await click(button());await click(button({blueprintLive:'true'}));run('app.live=false');
 run('app.selected.environment_blueprint=other.id');await click(button());run('app.selected.environment_blueprint=record.id;app.view="overview"');await click(button());
 assert.equal(jobs().length,0);assert.equal(run('app.registrationAttempts.size'),0);
})().catch(e=>{console.error(e.stack);process.exitCode=1});
''')

    def test_unknown_malformed_or_failed_acknowledgment_retains_no_retry_guard(self):
        self.run_js(r'''
(async()=>{
 for(const acknowledgement of [null,{}, {job_id:17},{job_id:'unsafe<script>'}]){
  run('app.registrationAttempts=new Map()');await c.loadBlueprintRegistrationPreview(record);const before=jobs().length;
  fetchImpl=async(path)=>{if(path.startsWith('/api/blueprint-registration-preview?'))return {ok:true,json:async()=>packet};assert.equal(path,'/api/jobs');return {ok:true,json:async()=>acknowledgement}};
  await click(button());assert.equal(jobs().length,before+1);assert.equal(run('[...app.registrationAttempts.values()][0].phase'),'unknown');await click(button());assert.equal(jobs().length,before+1);
  const saved=run('app.registrationPreview'),attempt=run('[...app.registrationAttempts.values()][0]'),html=c.BlueprintRegistrationPreview.render(saved.packet,saved.expected,{registrationAttempt:attempt});assert.ok(html.includes('Queue acknowledgment is unknown'));assert.ok(!html.includes('data-blueprint-register='));
 }
 run('app.registrationAttempts=new Map()');await c.loadBlueprintRegistrationPreview(record);const before=jobs().length;
 fetchImpl=async()=>{throw Error('Transport result unknown')};await click(button());assert.equal(run('[...app.registrationAttempts.values()][0].phase'),'unknown');await click(button());assert.equal(jobs().length,before+1);
})().catch(e=>{console.error(e.stack);process.exitCode=1});
''')

    def test_mode_change_during_get_withholds_publication_and_post(self):
        self.run_js(r'''
(async()=>{
 let resolve;fetchImpl=async()=>new Promise(r=>{resolve=r});const pending=c.loadBlueprintRegistrationPreview(record);await settle();
 run('app.live=true');resolve({ok:true,json:async()=>packet});const stale=await pending;assert.equal(stale.packet,null);assert.ok(stale.error.includes('changed while'));assert.equal(run('app.registrationPreview'),null);await click(button());assert.equal(jobs().length,0);
})().catch(e=>{console.error(e.stack);process.exitCode=1});
''')

    def test_selection_change_during_get_withholds_publication_and_post(self):
        self.run_js(r'''
(async()=>{
 let resolve;fetchImpl=async()=>new Promise(r=>{resolve=r});const pending=c.loadBlueprintRegistrationPreview(record);await settle();
 run('app.selected.environment_blueprint=other.id');resolve({ok:true,json:async()=>packet});const stale=await pending;assert.equal(stale.packet,null);assert.ok(stale.error.includes('changed while'));assert.equal(run('app.registrationPreview'),null);await click(button());assert.equal(jobs().length,0);
})().catch(e=>{console.error(e.stack);process.exitCode=1});
''')
