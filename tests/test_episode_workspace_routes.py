"""Execute the real app's episode retrieval and question-only navigation."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from tests.test_episode_workspace_ui import fixture

ROOT=Path(__file__).resolve().parents[1]
NODE=shutil.which('node')
PRELUDE=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const f=JSON.parse(fs.readFileSync(0,'utf8')),nodes=new Map(),listeners={},requests=[];
function node(id){if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',open:false,classList:{toggle(){},remove(){}},addEventListener(){},scrollIntoView(){},close(){this.open=false},contains(){return false},querySelector(){return null}});return nodes.get(id)}
const r=f.packet.source_refs,p=f.packet,records=[];
const wrap=(ref,kind,payload)=>({...ref,kind,payload});
records.push(wrap(r.discovery,'discovery',{dataset_ref:r.dataset,candidates:[{...p.lead,...p.comparison}]}));
records.push(wrap(r.selected_audit,'selected_lead_audit',{source_refs:{dataset:r.dataset,discovery:r.discovery}}));
records.push(wrap(r.temporal_audit,'temporal_path_audit',{selected_audit_ref:r.selected_audit}));
const c={console,records,Map,Set,Date,JSON,Math,Number,String,Array,Object,Promise,URLSearchParams,CSS:{escape:x=>x},setTimeout:()=>0,clearTimeout(){},setInterval:()=>0,document:{getElementById:node,querySelector:node,querySelectorAll:()=>[],activeElement:null,addEventListener:(event,fn)=>{const previous=listeners[event];listeners[event]=previous?async e=>{await previous(e);await fn(e)}:fn}},fetch:async path=>{requests.push(path);if(path.startsWith('/api/episode-workspace?'))return {ok:true,json:async()=>p};const u=new URL(path,'http://localhost'),id=decodeURIComponent(u.pathname.split('/').pop()),v=Number(u.searchParams.get('version'));const obj=records.find(row=>row.id===id && row.version===v);assert(obj,'Exact object missing '+path);return {ok:true,json:async()=>obj}}};
vm.createContext(c);let source=fs.readFileSync('web/app.js','utf8');vm.runInContext(source.slice(0,source.lastIndexOf('\nrefresh(true);')),c);vm.runInContext(fs.readFileSync('web/episode-workspace.js','utf8'),c);
const run=s=>vm.runInContext(s,c);
run("app.state={objects:records.map(o=>({...o,summary:{name:o.kind}})),jobs:[],usage:{calls:400},max_calls:400};render=async()=>{};submit=()=>{throw new Error('Question navigation must not submit a job')}");
const button=(dataset,attribute)=>({dataset,closest(){return this},hasAttribute(name){return name===attribute}});
'''


@unittest.skipUnless(NODE,'Node required for actual app route checks')
class EpisodeWorkspaceRouteTests(unittest.TestCase):
    def run_js(self,body):
        run=subprocess.run([NODE,'-e',PRELUDE+body],input=json.dumps(fixture()),
            text=True,capture_output=True,cwd=ROOT,timeout=20)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)

    def test_exact_historical_fetch_then_question_only_navigation_without_job(self):
        self.run_js(r'''
(async()=>{
records.push(wrap({...r.discovery,version:4,hash:'b'.repeat(64)},'discovery',{later:true}));
run("app.state.objects.unshift(records[records.length-1])");
await c.openEpisodeWorkspace(r.discovery,p.lead.id);
assert.equal(run('app.view'),'episode');assert.equal(run('app.episodeExpected.source_refs.discovery.version'),3);
const query=new URL(requests.find(x=>x.startsWith('/api/episode-workspace?')),'http://localhost').searchParams;
assert.equal(query.get('selected_audit_version'),'3');assert.equal(query.get('temporal_audit_version'),'3');assert(!query.has('behavior_id'));
run("app.episodeQuestion='  What observable would distinguish task scheduling from relay dependence?  ';app.authoringBehavior='previous-behavior';app.authoringCapabilities='previous-capability'");
const before=requests.length;
await listeners.click({target:button({},'data-episode-transfer-question')});
assert.equal(run('app.view'),'experiments');assert.equal(run('app.experimentStudy'),'authoring');
assert.equal(run('app.authoringQuestion'),'What observable would distinguish task scheduling from relay dependence?');
assert.equal(run('app.authoringBehavior'),'');assert.equal(run('app.authoringCapabilities'),'');assert.equal(requests.length,before);
assert(!requests.some(x=>x.startsWith('/api/jobs')));
})().catch(e=>{console.error(e.stack);process.exitCode=1});
''')

    def test_newest_relevant_wrong_hash_cannot_fallback_or_fetch_packet(self):
        self.run_js(r'''
(async()=>{
const bad=wrap({id:'selected-bad',version:1,hash:'b'.repeat(64)},'selected_lead_audit',{source_refs:{dataset:r.dataset,discovery:{...r.discovery,hash:'b'.repeat(64)}}});
records.push(bad);run("app.state.objects.unshift(records[records.length-1])");
await assert.rejects(()=>c.openEpisodeWorkspace(r.discovery,p.lead.id),/source binding/);
assert(!requests.some(x=>x.startsWith('/api/episode-workspace?')));assert.equal(run('app.episodePacket'),null);
})().catch(e=>{console.error(e.stack);process.exitCode=1});
''')

    def test_unavailable_packet_and_invalid_draft_do_not_transition_or_execute(self):
        self.run_js(r'''
(async()=>{
p.available=false;p.reason='source_unavailable';
await assert.rejects(()=>c.openEpisodeWorkspace(r.discovery,p.lead.id),/source_unavailable/);
assert.equal(run('app.episodePacket'),null);assert.equal(run('app.view'),'overview');
p.available=true;await c.openEpisodeWorkspace(r.discovery,p.lead.id);
run("app.episodeQuestion='';app.authoringQuestion='unchanged'");
await listeners.click({target:button({},'data-episode-transfer-question')});
assert.equal(run('app.view'),'episode');assert.equal(run('app.authoringQuestion'),'unchanged');
assert(!requests.some(x=>x.startsWith('/api/jobs')));
})().catch(e=>{console.error(e.stack);process.exitCode=1});
''')
