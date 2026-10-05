"""Actual workspace controller regressions with isolated discussion fixtures.

These tests use the persisted nested guide-result shape; no provider or registry
access establishes an experimental finding.
"""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
NODE = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const mode=process.argv[2],elements=new Map();
const node=()=>({innerHTML:'',querySelectorAll:()=>[],textContent:''});
const ctx=vm.createContext({assert,URLSearchParams,console,crypto:{randomUUID:()=> 'fixture-request'},
 document:{getElementById:id=>{if(!elements.has(id))elements.set(id,node());return elements.get(id);},querySelector:()=>null},
 localStorage:{getItem:()=> 'fixture-chat',setItem(){}},setTimeout:()=>1,clearTimeout(){}});
ctx.window=ctx;
for(const f of ['society-experience.js','guide-message.js','lab-workspace.js'])
 vm.runInContext(fs.readFileSync(process.argv[1]+'/web/'+f,'utf8'),ctx,{filename:f});
vm.runInContext(`
const clone=x=>JSON.parse(JSON.stringify(x)),ref={id:'village_recovery_experiment-fixture',version:1,hash:'a'.repeat(64)},
 source={id:'dataset-fixture',version:1,hash:'b'.repeat(64)},fidelity={represented:['One source-bound reference'],approximated:[],omitted:['Historical accounts'],historical_equivalence:false},
 hypothesis={statement:'A source-grounded fixture question'},record={...ref,kind:'village_recovery_experiment',payload:{agent_mode:'live',status:'complete',source_refs:{dataset_ref:source},hypothesis,fidelity,
 protocol:{environment:{kind:'single_document_reference_repair'},primary_outcome:'verified_repaired_reference',grounding:{source_ref:source,evidence_ids:['fixture-observation']},hypothesis,fidelity}}};
const message={id:'fixture-reply',role:'assistant',content:'Both conditions solved this isolated fixture. The effect remains uncertain.',
 metadata:{answer_source:'ai',guide_result:{sources:[{kind:'village_recovery_experiment',object_ref:ref}],updated_context:{},result_context_ref:ref,
 scientific_report:{available:true,source_ref:ref,via_execution_ref:null}}}};
let available=true,reads=0,chatReads=0;
const saved={id:'fixture-chat',project_id:'fixture-project',name:'Fixture discussion',revision:1,state:{},messages:[message],artifacts:[]},
 index={default_chat_id:saved.id,projects:[{id:'fixture-project',name:'Fixture',chats:[{id:saved.id,name:saved.name}]}]},
 app={state:{csrf:'fixture-only'},view:'workspace'},
 b={app,esc:s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),
 experience:{state:{guideBusy:false},restoreWorkspaceState(){},hydrateGuide(){}},
 api:async(path,options)=>{assert(!options?.method || options.method==='GET','Read-only navigation cannot submit work');
   if(path==='/api/workspaces')return clone(index);
   if(path.startsWith('/api/workspaces/chat')){chatReads++;return clone(saved);}
   if(path.startsWith('/api/workspaces/artifacts'))return {artifacts:[]};throw Error('Unexpected route');},
 object:async(id,version)=>{reads++;assert.equal(id,ref.id);assert.equal(version,1);if(!available)throw Error('Temporary exact-record read failure');return clone(record);},
 render(){},toast(){}};
const workspace=LabWorkspace.create(b);globalThis.fixture={workspace,record,saved,ref,setAvailable:v=>available=v,getReads:()=>reads,getChatReads:()=>chatReads};
`,ctx);
(async()=>{
 const f=ctx.fixture,w=f.workspace;await w.initialize();
 if(mode==='retry'){
  f.setAvailable(false);assert(!(await w.render('workspace')).includes('<iframe'));
  f.setAvailable(true);const html=await w.render('workspace');
  assert(html.includes('<iframe'));assert(html.includes('This experiment’s scientific results'));
  assert.equal(f.getReads(),2);assert.equal(w.state.reportCache.size,1);
 }else if(mode==='current-chat'){
  w.state.chat.messages=[];f.saved.revision=2;
  const handled=await w.click({hasAttribute:k=>k==='data-view',dataset:{view:'workspace'}});
  assert.equal(handled,false,'Generic navigation remains with the host');
  assert.equal(f.getChatReads(),2);assert.equal(w.state.chat.revision,2);
  const html=await w.render('workspace');assert(html.includes('<iframe'));assert(html.includes('fixture-reply')===false);
  assert.equal(w.state.chat.messages.at(-1).metadata.guide_result.result_context_ref.hash,f.ref.hash);
 }else if(mode==='mismatch'){
  f.record.hash='c'.repeat(64);assert(!(await w.render('workspace')).includes('<iframe'));
  assert.equal(w.state.reportEmbeds.size,0);assert.equal(w.state.reportCache.size,0);
  f.record.hash=f.ref.hash;f.record.payload.protocol.environment.kind='unrelated';
  assert(!(await w.render('workspace')).includes('<iframe'));assert.equal(w.state.reportEmbeds.size,0);
 }else throw Error('Unknown scenario');
 console.log(JSON.stringify({scenario:mode,passed:true}));
})().catch(error=>{console.error(error);process.exitCode=1;});
"""


class WorkspaceScientificReportTests(unittest.TestCase):
    def scenario(self, mode):
        result = subprocess.run(['node', '-e', NODE, str(ROOT), mode],
                                text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)['passed'])

    def test_transient_exact_read_does_not_poison_report_cache(self):
        self.scenario('retry')

    def test_return_to_current_chat_reads_latest_persisted_reply(self):
        self.scenario('current-chat')

    def test_wrong_hash_or_unrelated_world_withholds_report(self):
        self.scenario('mismatch')


if __name__ == '__main__':
    unittest.main()
