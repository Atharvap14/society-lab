"""Execute resource/sensitivity views and event handlers against real reports."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path
from swarm_lab.resource_experiments import create_resource_protocol,run_resource_experiment
from swarm_lab.dataset import normalize_message
from swarm_lab.name_eligibility_sensitivity import audit_name_eligibility_sensitivity
from swarm_lab.mention_graph_sensitivity import compare_name_graphs
from swarm_lab.graph_discovery import discover_graph_leads
from swarm_lab.selected_lead_sensitivity import audit_selected_lead_name_sensitivity
from swarm_lab.temporal_network import analyze_temporal_mentions
from swarm_lab.timed_resource_experiments import create_timed_resource_protocol,run_timed_resource_experiment,replay_timed_resource_report

ROOT=Path(__file__).resolve().parents[1]
NODE=shutil.which('node')
SCRIPT=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const records=JSON.parse(fs.readFileSync(0,'utf8')),nodes=new Map(),listeners={};
function node(id){if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',open:false,className:'',classList:{toggle(){},remove(){},add(){}},addEventListener(){},showModal(){this.open=true},close(){this.open=false},contains(){return false},querySelector(){return null},focus(){}});return nodes.get(id)}
const map=Object.fromEntries(records.map(o=>[o.id,o]));
const c={console,records,Map,Set,Date,JSON,Math,Number,String,Array,Object,Promise,window:{scrollTo(){}},CSS:{escape:x=>x},setTimeout:()=>0,clearTimeout(){},setInterval:()=>0,document:{getElementById:node,querySelector:node,querySelectorAll:()=>[],activeElement:null,addEventListener:(x,f)=>{const previous=listeners[x];listeners[x]=previous?async event=>{await previous(event);await f(event)}:f}},fetch:async path=>({ok:true,json:async()=>map[path.split('/').pop()]})};
vm.createContext(c);let s=fs.readFileSync('web/app.js','utf8');vm.runInContext(s.slice(0,s.lastIndexOf('\nrefresh(true);')),c);
const run=s=>vm.runInContext(s,c);
run("app.live=false;app.state={objects:records.map(o=>({id:o.id,kind:o.kind,version:o.version,summary:{name:o.kind,...(o.summary||{})}})),jobs:[],usage:{calls:397},max_calls:400,model:'test'};app.selected.resource_protocol='resource_protocol-test';app.selected.resource_experiment='resource_experiment-test';submit=async(action,args)=>{globalThis.sent={action,args}};");
const button=data=>({dataset:data,hasAttribute(){return false},closest(){return this}});
(async()=>{
assert(run("studyTabs().includes('Shared resource')"));assert.equal(run('resourcePlanBudget().decisions'),96);
let html=await run('resourceExperiments()');assert(html.includes('resource-design-form'));assert(html.includes('Historical evidence reports concurrent computer sessions'));assert(html.includes('p=1/3'));assert(html.includes('WAIT / INDEPENDENT PENDING'));assert(html.includes('Scripted infrastructure only'));
await listeners.submit({target:{id:'resource-design-form'},preventDefault(){}});assert.equal(c.sent.action,'design_resource');assert.deepEqual(c.sent.args.release_rounds,[1,2]);assert.equal(c.sent.args.live,false);
await listeners.click({target:button({action:'experiment-resource',id:'resource_protocol-test'})});assert.equal(c.sent.action,'experiment_resource');assert.equal(c.sent.args.protocol_id,'resource_protocol-test');
await run("showResourceRun('resource_experiment-test','run-0001')");assert(node('dialog-body').innerHTML.includes('EXECUTED RESULT'));assert(node('dialog-body').innerHTML.includes('Researcher-only trace'));
await run("openObject('resource_experiment-test')");assert(run("app.view==='experiments'&&app.experimentStudy==='resource'"));
run("app.live=true");html=await run('resourceExperiments()');assert(/data-action="experiment-resource"[^>]*disabled/.test(html));
run("app.shortNames='o1, o3'");await listeners.click({target:button({action:'audit-name-eligibility',id:'dataset-test',version:'1'})});assert.equal(c.sent.action,'audit_name_eligibility');assert.deepEqual(c.sent.args.short_name_allowlist,['o1','o3']);assert(c.sent.args.include_unicode_shadow);assert(!('live' in c.sent.args));
let p=run("eligibilityAuditPanel({payload:{summary:{baseline_exact_event_count:62,short_candidate_exact_event_count:81,expanded_exact_candidate_event_count:143,ambiguous_exact_event_count:0},unicode_shadow:{summary:{expanded_shadow_candidate_event_count:162}},requested_names:['o1','o3'],allowlist_resolution:[],short_name_exact_events:[]}},'dataset-test',1)");assert(p.includes('not graph counts'));assert(p.includes('143'));assert(p.includes('162'));
const graph=await run("object('graph_measurement_audit-test')");c.graphRecord=graph;let plot=run('graphMeasurementPanel(graphRecord)');assert(plot.includes('NULL MODES'));assert(plot.includes('not changed swarm behavior'));assert(plot.includes('no shared eigenvector coordinates'));assert(plot.includes('GPT-4.1'));assert(plot.includes('o3'));
await listeners.click({target:button({action:'compare-mention-graphs',id:'name_eligibility_audit-test'})});assert.equal(c.sent.action,'compare_mention_graphs');assert.equal(c.sent.args.eligibility_audit_id,'name_eligibility_audit-test');
assert.equal(run("uniqueIds(['resource_protocol-test','resource_experiment-test','name_eligibility_audit-test']).length"),3);
const leadRecord=await run("object('selected_lead_audit-test')");c.leadRecord=leadRecord;
let leadHtml=run("selectedLeadAuditPanel(leadRecord,{id:'discovery-test',version:3,payload:{graph_search:{leads:[{}]}}})");
assert(leadHtml.includes('Native window node universes'));assert(leadHtml.includes('Fixed nodes within each original window pair'));assert(leadHtml.includes('candidate minus original comparator'));assert(leadHtml.includes('data-version="3"'));
await listeners.input({target:{dataset:{field:'leadUnicodeShadow'},value:'on'}});assert.strictEqual(run('app.leadUnicodeShadow'),true);
await listeners.change({target:{dataset:{field:'leadUnicodeShadow'},checked:false}});assert.strictEqual(run('app.leadUnicodeShadow'),false);
run("app.leadShortNames='o1, o3'");await listeners.click({target:button({action:'audit-selected-leads',id:'discovery-test',version:'3'})});
assert.equal(c.sent.action,'audit_selected_leads');assert.equal(c.sent.args.version,3);assert.strictEqual(c.sent.args.include_unicode_shadow,false);assert.deepEqual(c.sent.args.short_name_allowlist,['o1','o3']);assert(!('live' in c.sent.args));
await run("openObject('selected_lead_audit-test')");assert(node('dialog-body').innerHTML.includes('Exact audit identity and source references'));
assert.equal(run("uniqueIds(['selected_lead_audit-test']).length"),1);
let linked=run("measurementReviewPanel({measurement_sensitivity_reviews:[{audit_ref:{id:'selected_lead_audit-test',version:1},native_contrasts:{baseline_exact:1,unicode_expanded:0.166666},scope:'Original selected contrast'}]})");
assert(linked.includes('data-open-version="1"'));assert(linked.includes('+0.167'));
const temporalRecord=await run("object('temporal_path_audit-test')");c.temporalRecord=temporalRecord;
let temporalHtml=run('temporalAuditPanel(temporalRecord,leadRecord)');
assert(temporalHtml.includes('STATIC → TEMPORAL'));assert(temporalHtml.includes('BRIDGE LOSS'));assert(temporalHtml.includes('reference direction'));
await listeners.click({target:button({action:'audit-temporal-paths',id:'selected_lead_audit-test',version:'1'})});
assert.equal(c.sent.action,'audit_temporal_paths');assert.equal(c.sent.args.selected_audit_id,'selected_lead_audit-test');assert.equal(c.sent.args.version,1);assert(!('live' in c.sent.args));
await listeners.click({target:button({action:'replay-temporal-paths',id:'temporal_path_audit-test',version:'1'})});assert.equal(c.sent.action,'replay_temporal_paths');
await run("openObject('temporal_path_audit-test')");assert(node('dialog-body').innerHTML.includes('Exact temporal audit identity'));
run("app.live=false;app.selected.timed_resource_protocol='timed_resource_protocol-test';app.selected.timed_resource_experiment='timed_resource_experiment-test';app.timedSeed=6149");
let timedHtml=await run('timedResourceExperiments()');assert(timedHtml.includes('policy ignores note content'));assert(timedHtml.includes('4 run traces checked'));assert(timedHtml.includes('seed-block-0001'));
c.timingProof=map['verification-timed-test'];c.timingProof.payload.result_ref.version=2;timedHtml=await run('timedResourceExperiments()');assert(!timedHtml.includes('4 run traces checked'));c.timingProof.payload.result_ref.version=1;
await listeners.submit({target:{id:'timed-resource-design-form'},preventDefault(){}});assert.equal(c.sent.action,'design_timed_resource');assert.equal(c.sent.args.seed,6149);assert.equal(c.sent.args.resamples,2000);assert.strictEqual(c.sent.args.live,false);
await listeners.input({target:{dataset:{field:'timedTrials'},value:'3'}});assert(node('timed-plan-budget').textContent.includes('144 maximum'));run('app.timedTrials=2');
await listeners.click({target:button({action:'experiment-timed-resource',id:'timed_resource_protocol-test'})});assert.equal(c.sent.action,'experiment_timed_resource');assert.equal(c.sent.args.protocol_id,'timed_resource_protocol-test');
await run("showTimedRun('timed_resource_experiment-test','timed-run-0001-1')");assert(node('dialog-body').innerHTML.includes('Pre-subject request construction boundaries'));
await run("openObject('timed_resource_experiment-test')");assert(run("app.view==='experiments'&&app.experimentStudy==='timed_resource'"));
run('app.live=true');timedHtml=await run('timedResourceExperiments()');assert(/data-action="experiment-timed-resource"[^>]*disabled/.test(timedHtml));run('app.live=false');
c.partialRecord=map['timed_resource_experiment-test'];c.completePayload=c.partialRecord.payload;c.partialRecord.payload={...c.completePayload,status:'incomplete_infrastructure_failure',analysis:null,runs:[{run_id:'partial',block_id:'seed-block-0001',context:'active',status:'incomplete',counts:{recorded_receipts:0}}]};
timedHtml=await run('timedResourceExperiments()');assert(timedHtml.includes('No effect estimate'));assert(!timedHtml.includes('0 pp'));c.partialRecord.payload=c.completePayload;
console.log('Resource and eligibility controls, navigation, traces and mode guard passed; provider calls=0');
})().catch(e=>{console.error(e.stack);process.exitCode=1});
'''

@unittest.skipUnless(NODE,'Node is required for browser-independent UI contract tests')
class DashboardExtensionTests(unittest.TestCase):
    def test_resource_and_measurement_views(self):
        protocol=create_resource_protocol();result=run_resource_experiment(protocol)
        result['protocol_id']='resource_protocol-test'
        records=[{'id':'resource_protocol-test','kind':'resource_protocol','version':1,'payload':{'protocol':protocol}},
            {'id':'resource_experiment-test','kind':'resource_experiment','version':1,'payload':result}]
        messages=[normalize_message({'id':'m','agent_id':'writer','agent_name':'Writer','content':'o3, check GPT-4.1.',
            'timestamp':'2025-04-20T12:00:00Z','room_id':'r'})]
        roster=[{'id':'o','name':'o3'},{'id':'g','name':'GPT-4.1'}]
        audit=audit_name_eligibility_sensitivity(messages,roster,short_name_allowlist=['o3'],include_unicode_shadow=True)
        graph=compare_name_graphs(messages,audit,agents=roster)
        records.append({'id':'graph_measurement_audit-test','kind':'graph_measurement_audit','version':1,'payload':graph})
        people=[{'id':'a','name':'Alice'},{'id':'b','name':'Bobby'},{'id':'c','name':'Carol'},{'id':'o','name':'o3'}]
        windows=[]
        for hour in (10,11):
            for i in range(12):
                actor=['a','b','c'][i%3]
                text=('Bobby, inspect the telescope. o3 may know.' if actor!='b' else 'Ready.') if hour==10 else 'Alice, Bobby, Carol, inspect the telescope together.'
                windows.append({'id':f'{hour}-{i}','agent_id':actor,'content':text,'room_id':'r','timestamp':f'2025-04-02T{hour}:00:{i:02d}Z'})
        search=discover_graph_leads(windows,people)
        leadAudit=audit_selected_lead_name_sensitivity(windows,people,search,
            selected_lead_ids=[l['id'] for l in search['leads']],short_name_allowlist=['o3'],include_unicode_shadow=True)
        records.append({'id':'selected_lead_audit-test','kind':'selected_lead_audit','version':1,'payload':leadAudit})
        temporal=analyze_temporal_mentions(windows,people,short_name_allowlist=['o3'],include_unicode_shadow=True)
        records.append({'id':'temporal_path_audit-test','kind':'temporal_path_audit','version':1,'payload':temporal})
        timed=create_timed_resource_protocol(seed=6149)
        timing=run_timed_resource_experiment(timed)
        timing['protocol_id']='timed_resource_protocol-test';timing['agent_mode']='offline_simulation'
        proof=replay_timed_resource_report(timing)
        records.extend([{'id':'timed_resource_protocol-test','kind':'timed_resource_protocol','version':1,'payload':{'protocol':timed,'agent_mode':'offline_template'}},
            {'id':'timed_resource_experiment-test','kind':'timed_resource_experiment','version':1,'hash':'f'*64,'payload':timing},
            {'id':'verification-timed-test','kind':'verification','version':1,'summary':{'experiment_id':'timed_resource_experiment-test'},'payload':{**proof,'result_kind':'timed_resource_experiment','experiment_id':'timed_resource_experiment-test','result_ref':{'id':'timed_resource_experiment-test','version':1,'hash':'f'*64}}}])
        completed=subprocess.run([NODE,'-e',SCRIPT],input=json.dumps(records),capture_output=True,text=True,cwd=ROOT)
        self.assertEqual(completed.returncode,0,completed.stderr)

if __name__=='__main__':unittest.main()
