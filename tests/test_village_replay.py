import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(shutil.which('node'),'Node is required for the actual renderer')
class VillageReplayTests(unittest.TestCase):
    def test_single_link_repair_uses_its_own_goal_and_two_roles(self):
        script=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
vm.runInThisContext(fs.readFileSync('web/society-replay.js','utf8'));
const source={id:'dataset-exact',version:1,hash:'a'.repeat(64)};
const record={id:'recovery-result',version:1,hash:'b'.repeat(64),kind:'village_recovery_experiment',payload:{status:'complete',agent_mode:'live',source_refs:{dataset_ref:source},protocol:{grounding:{source_ref:source,evidence_ids:['real-404-message']},environment:{kind:'single_document_reference_repair',agents:['ethics_owner','auditor']}},runs:[{run_id:'pair-1-repair',outcomes:{verified_repaired_reference:1},turns:[
{step:0,agent_id:'ethics_owner',action:{action:'send_message',recipient:'auditor',message:'Here is the original document link.'},tool_result:{ok:true,delivered_recipient_ids:['auditor']}},
{step:1,agent_id:'auditor',action:{action:'open_url',url:'https://docs.test/canonical'},tool_result:{ok:true,content:'Original document'}}]}]}};
const model=SocietyReplay.normalize(record);assert.equal(model.available,true);assert.equal(model.recovery,true);
assert.deepEqual(model.actors.map(a=>a.name).sort(),['Document owner','Teammate']);
assert.equal(model.events[0].audience.kind,'direct');assert.deepEqual(model.events[0].deliveries,['auditor']);
const beginning=SocietyReplay.render({record,initialState:{cursor:0}});assert(beginning.includes('Outcome appears at the end'));assert(!beginning.includes('teammate opened the original'));
const end=SocietyReplay.render({record,initialState:{cursor:1}});assert(end.includes('Repair one link'));assert(end.includes('The teammate opened the original document'));assert(!end.includes('All four original'));assert(!end.includes('Copies made while'));
const wrong=structuredClone(record);wrong.payload.protocol.environment.kind='village_document_access_repair';assert.equal(SocietyReplay.normalize(wrong).available,false);
const failed=structuredClone(record);failed.payload.runs[0].outcomes.verified_repaired_reference=0;assert(SocietyReplay.render({record:failed,initialState:{cursor:1}}).includes('did not record verified access'));
'''
        result=subprocess.run(['node','-e',script],cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_source_bound_executed_tools_and_audiences(self):
        script=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
vm.runInThisContext(fs.readFileSync('web/society-replay.js','utf8'));
const source={id:'dataset-exact',version:1,hash:'a'.repeat(64)};
const actors=['ethics_owner','power_owner','stimuli_owner','coordinator','auditor','integrator'];
const record={id:'access-result',version:1,hash:'b'.repeat(64),kind:'village_access_experiment',payload:{status:'complete',agent_mode:'live',source_refs:{dataset_ref:source},protocol:{grounding:{source_ref:source,evidence_ids:['source-message']},environment:{kind:'village_document_access_repair',agents:actors}},runs:[{run_id:'pair-1-canonical_check',outcomes:{verified_usable_project:0,avoidable_recreations:1},turns:[
{step:0,agent_id:'ethics_owner',action:{action:'send_message',recipient:'all',message:'Use this canonical link.'},tool_result:{ok:true,delivered_recipient_ids:actors.slice(1)}},
{step:1,agent_id:'auditor',action:{action:'open_document',document_id:'original-irb'},tool_result:{ok:false,status_code:404,error:'Page not found'}},
{step:2,agent_id:'auditor',action:{action:'send_message',recipient:'ethics_owner',message:'Please grant viewer access.'},tool_result:{ok:true,delivered_recipient_ids:['ethics_owner']}}]}]}};
const model=SocietyReplay.normalize(record);assert.equal(model.available,true);assert.equal(model.village,true);
assert(!model.actors.some(a=>a.id==='all'));
assert.equal(model.events[0].audience.kind,'room');assert.equal(model.events[0].deliveries.length,5);
assert.equal(model.events[1].audience.kind,'action');assert.equal(model.events[1].ok,false);assert(model.events[1].contents.includes('404'));
assert.equal(model.events[2].audience.kind,'direct');assert.deepEqual(model.events[2].deliveries,['ethics_owner']);
let beginning=SocietyReplay.render({record,initialState:{cursor:0}});assert(beginning.includes('Outcome appears at the end'));assert(!beginning.includes('Copies made while originals persisted: 1'));
let end=SocietyReplay.render({record,initialState:{cursor:2}});assert(end.includes('did not satisfy the complete-project check'));assert(end.includes('Copies made while originals persisted: 1'));assert(!end.includes('publications</span>'));
const wrong=structuredClone(record);wrong.payload.protocol.grounding.source_ref={...source,hash:'c'.repeat(64)};assert.equal(SocietyReplay.normalize(wrong).available,false);
const missing=structuredClone(record);missing.payload.protocol.grounding.evidence_ids=[];assert.equal(SocietyReplay.normalize(missing).available,false);
const duplicate=structuredClone(record);duplicate.payload.runs[0].turns[2].step=1;assert.equal(SocietyReplay.normalize(duplicate).available,false);
const invalid=structuredClone(record);invalid.payload.runs[0].turns[0].tool_result.values=NaN;assert.equal(SocietyReplay.normalize(invalid).available,false);
console.log('Village replay source, audiences, receipts, outcome timing and malformed-state probes passed');
'''
        result=subprocess.run(['node','-e',script],cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

if __name__=='__main__':unittest.main()
