"""Execute cycle controls against exact, actually compiled CPU-world fixtures.

Saved cycle status fixtures are authored UI examples, not experimental findings.
No hosted calls or production Store/job writes occur in these tests.
"""
import copy
import hashlib
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which('node')
PRELUDE = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const fixture=JSON.parse(fs.readFileSync(0,'utf8')),records=fixture.records,nodes=new Map(),listeners={},requests=[];
function node(id){if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',open:false,className:'',classList:{toggle(){},remove(){},add(){}},addEventListener(){},showModal(){this.open=true},close(){this.open=false},contains(){return false},querySelector(){return null},focus(){}});return nodes.get(id)}
const map=new Map(records.map(o=>[`${o.id}@${o.version}`,o]));
function latest(id){return records.filter(o=>o.id===id).sort((a,b)=>b.version-a.version)[0]}
const c={console,fixture,records,Map,Set,Date,JSON,Math,Number,String,Array,Object,Promise,CSS:{escape:x=>x},window:{scrollTo(){}},setTimeout:()=>0,clearTimeout(){},setInterval:()=>0,
document:{getElementById:node,querySelector:node,querySelectorAll:()=>[],activeElement:null,addEventListener:(event,f)=>{const old=listeners[event];listeners[event]=old?async e=>{await old(e);await f(e)}:f}},fetch:async path=>{requests.push(path);const url=new URL(path,'http://fixture'),id=decodeURIComponent(url.pathname.split('/').pop()),version=url.searchParams.get('version'),value=version ? map.get(`${id}@${version}`) : latest(id);return {ok:!!value,json:async()=>value || {error:'Exact object version not found'}}}};
vm.createContext(c);let source=fs.readFileSync('web/app.js','utf8');vm.runInContext(source.slice(0,source.lastIndexOf('\nrefresh(true);')),c);
const run=s=>vm.runInContext(s,c),button=dataset=>({dataset,closest(){return this},hasAttribute(){return false}}),fireSubmit=()=>listeners.submit({target:{id:'research-cycle-form'},preventDefault(){}});
run("app.state={objects:records.filter(o=>o.version===Math.max(...records.filter(x=>x.id===o.id).map(x=>x.version))).map(o=>({id:o.id,kind:o.kind,version:o.version,hash:o.hash,summary:{name:o.payload.name || o.kind,status:o.payload.status}})),jobs:[],usage:{calls:397},max_calls:400,model:'fixture'};app.live=true;app.harness='codex';app.cycleBehavior=fixture.behavior;app.cycleBlueprint=fixture.worlds.complementary_information;submit=async(action,args)=>{globalThis.sent={action,args}};");
const world=kind=>records.find(x=>x.id===fixture.worlds[kind]),behavior=records.find(x=>x.id===fixture.behavior);
const saved=id=>records.find(x=>x.id===id&&x.version===2);
function restore(object,value){for(const k of Object.keys(object))delete object[k];Object.assign(object,JSON.parse(value))}
'''

SELECTION = r'''
(async()=>{
  assert(run("studyTabs().includes('Research cycle')"));
  let html=await run('researchCycles()');assert(html.includes('research-cycle-form'));assert(html.includes('3 calls remain under the shared 400 cap'));
  assert(!/data-field="cycle(?:Research|Subjects)Live" checked/.test(html));assert(!/type="submit" disabled/.test(html));
  await fireSubmit();assert.equal(c.sent.action,'start_research_cycle');const args=c.sent.args;
  assert.deepEqual(args.behavior_ref,{kind:behavior.kind,id:behavior.id,version:behavior.version,hash:behavior.hash});
  for(const kind of ['dataset','discovery'])assert.deepEqual(args.source_refs[kind],{kind,...behavior.payload.source_refs[kind]});
  assert.equal(args.source_refs.dataset.version,2);assert.equal(args.source_refs.discovery.version,3);
  assert.deepEqual(args.blueprint_ref,{kind:world('complementary_information').kind,id:world('complementary_information').id,version:1,hash:world('complementary_information').hash});
  assert.equal(args.research_live,false);assert.equal(args.subjects_live,false);assert.equal(args.max_new_model_calls,0);assert.equal(args.subject_harness,'responses');assert.equal(args.research_harness,'responses');
  for(const key of ['live','harness','required_capabilities','proposal','fit_review','job_id'])assert(!(key in args));
  assert(requests.some(p=>p.includes(`/${args.source_refs.dataset.id}?version=2`)));assert(requests.some(p=>p.includes(`/${args.source_refs.discovery.id}?version=3`)));
  const p=behavior.payload,old=JSON.stringify(p);
  for(const status of ['rejected','approved_by_me',null]){p.status=status;c.sent=null;await fireSubmit();assert.equal(c.sent,null);assert(node('toast').textContent.includes('not eligible'));html=await run('researchCycles()');assert(html.includes('type="submit" disabled'))}restore(p,old);
  for(const status of ['schema_defect_requires_re_review','superseded_schema_defect_review']){p.research_quality_status=status;c.sent=null;await fireSubmit();assert.equal(c.sent,null)}restore(p,old);
  p.source_refs.dataset.version=true;c.sent=null;await fireSubmit();assert.equal(c.sent,null);restore(p,old);
  p.source_refs.dataset.hash='f'.repeat(64);c.sent=null;await fireSubmit();assert.equal(c.sent,null);assert(node('toast').textContent.includes('hash'));restore(p,old);
  p.source_refs.dataset.note='ignored?';c.sent=null;await fireSubmit();assert.equal(c.sent,null);restore(p,old);
  p.dataset_id='dataset-other';c.sent=null;await fireSubmit();assert.equal(c.sent,null);restore(p,old);
  const datasetMeta=run('app.state.objects.find(x=>x.kind==="dataset")'),before=JSON.stringify(datasetMeta);datasetMeta.version=3;c.sent=null;await fireSubmit();assert.equal(c.sent,null);assert(node('toast').textContent.includes('never rebased'));restore(datasetMeta,before);
  const discovery=records.find(x=>x.kind==='discovery'&&x.version===3),dp=JSON.stringify(discovery.payload);discovery.payload.dataset_ref={kind:'dataset',...p.source_refs.dataset,version:1};c.sent=null;await fireSubmit();assert.equal(c.sent,null);assert(node('toast').textContent.includes('different dataset'));restore(discovery.payload,dp);
  const bp=world('complementary_information').payload,bo=JSON.stringify(bp);
  const attacks=[()=>bp.experiment_eligibility='needs_review',()=>bp.construction_status='unsupported',()=>bp.experiment_eligibility='super_approved',()=>bp.fit_review.reviewed_blueprint_hash='e'.repeat(64),()=>bp.fit_review.required_changes=['Independent review required'],()=>bp.boundary_audit.passed=false,()=>bp.source_refs[1].version=1,()=>bp.source_refs[0].kind='dataset',()=>bp.spec.kind='future_world',()=>bp.spec.topology.kind='custom'];
  for(const mutate of attacks){mutate();c.sent=null;await fireSubmit();assert.equal(c.sent,null);html=await run('researchCycles()');assert(html.includes('type="submit" disabled'));restore(bp,bo)}
  run('app.cycleBudget=4;app.cycleSubjectsLive=true');c.sent=null;await fireSubmit();assert.equal(c.sent,null);assert(node('toast').textContent.includes('remaining shared cap'));
  run('app.cycleBudget=3');c.sent=null;await fireSubmit();assert.equal(c.sent,null);assert(node('toast').textContent.includes('full registered allocation'));
  run('app.state.usage.calls=0;app.cycleBudget=48');await fireSubmit();assert(c.sent.args.subjects_live);assert.equal(c.sent.args.research_live,false);assert.equal(c.sent.args.max_new_model_calls,48);
  run('app.cycleResearchLive=true');c.sent=null;await fireSubmit();assert.equal(c.sent,null);assert(node('toast').textContent.includes('does not rerun'));
  run("app.cycleMode='agentic';app.cycleSubjectsLive=false;app.cycleResearchLive=true;app.cycleBudget=2;app.cycleQuestion='Which communication mechanism is compatible with the source?';app.cycleCapabilities='resettable_state, custom_unimplemented';app.cycleHarness='codex'");await fireSubmit();assert.equal(c.sent.args.research_harness,'codex');assert.equal(c.sent.args.research_live,true);assert.equal(c.sent.args.subjects_live,false);assert(!('blueprint_ref' in c.sent.args));assert.deepEqual(Array.from(c.sent.args.required_capabilities),['resettable_state','custom_unimplemented']);assert(!('proposal' in c.sent.args));
  run('app.cycleResearchLive=false');c.sent=null;await fireSubmit();assert.equal(c.sent,null);
  run("app.cycleMode='existing_blueprint';app.cycleSubjectsLive=false;app.cycleBudget=0;app.state.usage.calls=400");await fireSubmit();assert.equal(c.sent.args.max_new_model_calls,0);
  run('app.cycleSubjectsLive=true;app.cycleBudget=1');c.sent=null;await fireSubmit();assert.equal(c.sent,null);
  console.log('Exact source refs, independent offline defaults, review/source/graph guards and shared-budget dispatch passed');
})().catch(e=>{console.error(e.stack);process.exitCode=1});
'''

RESUMPTION = r'''
(async()=>{
  const failed=saved('research_cycle-failed'),blocked=saved('research_cycle-blocked');
  let html=run('researchCyclePanel(records.find(x=>x.id==="research_cycle-failed"&&x.version===2))');assert(html.includes('Failed at independent replay'));assert(html.includes('Resume saved checkpoints'));assert(html.includes('cannot change flags'));
  run('app.cycleBudget=100000;app.cycleResearchLive=true;app.cycleSubjectsLive=true;app.seed=999;app.live=true');
  await listeners.click({target:button({action:'resume-research-cycle',id:failed.id})});assert.equal(c.sent.action,'resume_research_cycle');assert.deepEqual(Object.keys(c.sent.args),['cycle_id']);assert.equal(c.sent.args.cycle_id,failed.id);
  for(const status of ['blocked','completed','approved',null]){const old=failed.payload.status;failed.payload.status=status;c.sent=null;await listeners.click({target:button({action:'resume-research-cycle',id:failed.id})});assert.equal(c.sent,null);failed.payload.status=old}
  const instrument=failed.payload.instrument_version;failed.payload.instrument_version='future-contract';c.sent=null;await listeners.click({target:button({action:'resume-research-cycle',id:failed.id})});assert.equal(c.sent,null);failed.payload.instrument_version=instrument;
  run("app.state.jobs=[{id:'outer',status:'running',payload:{args:{cycle_id:'research_cycle-failed'}}}]");c.sent=null;await listeners.click({target:button({action:'resume-research-cycle',id:failed.id})});assert.equal(c.sent,null);assert(node('toast').textContent.includes('active job'));run('app.state.jobs=[]');
  assert(run('uniqueIds(["research_cycle-failed"]).length')===1);await run('openObject("research_cycle-failed",1)');assert(node('evidence-dialog').open);assert(node('dialog-body').innerHTML.includes('version 1'));
  failed.payload.status='blocked';c.sent=null;await listeners.click({target:button({action:'resume-research-cycle',id:failed.id})});assert.equal(c.sent,null);assert(node('toast').textContent.includes('reconciliation'));
  html=run('researchCyclePanel(records.find(x=>x.id==="research_cycle-blocked"&&x.version===2))');assert(html.includes('Blocked at world construction'));assert(html.includes('no implicit fallback'));assert(/data-action="resume-research-cycle"[^>]*disabled/.test(html));assert(html.includes('browser_tools_required'));assert(!html.includes('Grant approval'));
  blocked.payload.status='alien_status';html=run('researchCyclePanel(records.find(x=>x.id==="research_cycle-blocked"&&x.version===2))');assert(html.includes('Unknown cycle status'));assert(/data-action="resume-research-cycle"[^>]*disabled/.test(html));
  failed.payload.status='failed';failed.payload.failures.push({error:'<img src=x onerror="evil()">'});html=run('researchCyclePanel(records.find(x=>x.id==="research_cycle-failed"&&x.version===2))');assert(html.includes('&lt;img'));assert(!html.includes('<img src=x'));
  console.log('Saved-ID-only resume, terminal/unknown/active guards, exact historical modal and inert failures passed');
})().catch(e=>{console.error(e.stack);process.exitCode=1});
'''

WORLD_RENDERING = r'''
(async()=>{
  for(const [kind,ids] of Object.entries(fixture.worlds)){
    run(`app.cycleBlueprint=${JSON.stringify(ids)};app.cycleBlueprintVersion='';app.cycleBehaviorVersion='';`);await fireSubmit();assert.equal(c.sent.args.blueprint_ref.id,ids);assert(!('template' in c.sent.args));assert(!('world_kind' in c.sent.args));
    const cycle=records.find(o=>o.id===fixture.cycles[kind]);c.record=cycle;const html=run('researchCyclePanel(record)');const result=cycle.payload.artifacts.result;
    assert(html.includes(result.id));assert(html.includes(result.hash));assert(html.includes(`data-open-version="${result.version}"`));assert(html.includes(result.kind.replace(/_/g,' ')));
    assert(html.includes('Scripted infrastructure only'));assert(html.includes('untested analogue hypothesis'));assert(html.includes('does not promote a behavior'));
    if(kind!=='shared_artifact_coordination')assert(!html.includes('experiment-artifact-mock'));
  }
  run("app.cycleBlueprint=fixture.worlds.complementary_information;app.view='overview'");
  await listeners.change({target:{dataset:{field:'cycleSubjectsLive'},checked:true,value:'on'}});assert.equal(run('app.cycleSubjectsLive'),true);
  await listeners.change({target:{dataset:{field:'cycleSubjectsLive'},checked:false,value:'on'}});assert.equal(run('app.cycleSubjectsLive'),false);assert.equal(run('app.cycleBudget'),0);
  await listeners.change({target:{dataset:{field:'cycleMode'},value:'agentic'}});assert.equal(run('app.cycleResearchLive'),false);
  await listeners.change({target:{dataset:{field:'cycleResearchLive'},checked:true,value:'on'}});assert.equal(run('app.cycleResearchLive'),true);
  await listeners.change({target:{dataset:{field:'cycleMode'},value:'existing_blueprint'}});assert.equal(run('app.cycleResearchLive'),false);assert.equal(run('app.cycleBudget'),0);
  run("app.cycleBehaviorVersion='999'");let html=await run('researchCycles()');assert(html.includes('research-cycle-form'));assert(html.includes('Exact object version not found'));assert(html.includes('type="submit" disabled'));
  run("app.cycleBehaviorVersion='';app.cycleBlueprintVersion='1.5'");html=await run('researchCycles()');assert(html.includes('must be an integer'));assert(html.includes('type="submit" disabled'));
  run("app.cycleBlueprintVersion='';app.experimentStudy='cycle'");html=await run('experiments()');assert(html.includes('Run a reviewed research cycle'));assert(html.includes('Failed at independent replay'));assert(html.includes('Blocked at world construction'));
  console.log('Four distinct world/result kinds, immutable stage refs, explicit flags, missing versions and cycle navigation passed');
})().catch(e=>{console.error(e.stack);process.exitCode=1});
'''


@unittest.skipUnless(NODE, 'Node required for executable UI contract')
class ResearchCycleUITests(unittest.TestCase):
    def setUp(self):
        from tests.test_research_cycle import ResearchCycleTests, ref
        f = ResearchCycleTests('test_exact_existing_blueprint_uses_no_builder_or_reviewer')
        f.setUp(); self.addCleanup(f.doCleanups)
        # Nontrivial versions ensure the UI cannot hardcode v1 or resolve latest
        # instead of the reviewed source reference.
        f.dataset = f.lab.store.put('dataset', {**f.dataset['payload'], 'fixture_revision': 2}, f.dataset['id'])
        f.discovery = f.lab.store.put('discovery', {**f.discovery['payload'], 'fixture_revision': 2}, f.discovery['id'])
        f.discovery = f.lab.store.put('discovery', {**f.discovery['payload'], 'fixture_revision': 3, 'dataset_ref': ref(f.dataset)}, f.discovery['id'])
        f.sources = {'dataset': ref(f.dataset), 'discovery': ref(f.discovery)}
        p = copy.deepcopy(f.behavior['payload']);p['source_refs'] = {k: {a: v[a] for a in ('id','version','hash')} for k,v in f.sources.items()}
        f.behavior = f.lab.store.put('behavior', p, f.behavior['id'])
        records = [f.dataset, f.discovery, f.behavior];worlds = {};cycles = {}
        result_kinds = {'shared_artifact_coordination': ('protocol','experiment'), 'provenance_diffusion': ('network_protocol','network_experiment'), 'complementary_information': ('complementary_protocol','complementary_experiment'), 'exclusive_resource_tasks': ('resource_protocol','resource_experiment')}
        for kind, (protocol_kind, result_kind) in result_kinds.items():
            inputs = f.inputs(kind)
            obj = f.lab.construct_environment(behavior_id=f.behavior['id'], proposal=inputs['proposal'], fit_review=inputs['fit_review'])
            self.assertEqual(obj['payload']['experiment_eligibility'], 'approved_analogue')
            records.append(obj);worlds[kind] = obj['id']
            def mock_ref(k):
                return {'kind': k, 'id': k + '-fixture-' + kind, 'version': 3, 'hash': hashlib.sha256((k + kind).encode()).hexdigest()}
            plan = {'instrument_version':'bounded-research-cycle-v1','behavior_ref':ref(f.behavior),'source_refs':f.sources,
                    'construction': {'mode':'existing_blueprint','blueprint_ref':ref(obj)},
                    'execution': {'research_live':False,'subjects_live':False,'research_harness':'responses','subject_harness':'responses'},
                    'budget': {'usage_calls_at_start':397,'max_new_model_calls':0,'absolute_call_ceiling':397,'global_cap_at_start':400}}
            artifacts = {'blueprint':ref(obj),'protocol':mock_ref(protocol_kind),'result':mock_ref(result_kind)}
            payload = {'instrument_version':'bounded-research-cycle-v1','job_id':'cycle-fixture-' + kind,'plan':plan,'plan_hash':'a'*64,'status':'completed','phase':'completed','resume_count':0,'model_calls_at_checkpoint':397,
                       'stages': {stage: {'status':'completed','attempts':1,'artifact_ref':artifacts.get(stage),'job_id':None} for stage in ('construct','register','execute','audit','claims','curate')},
                       'artifacts':artifacts,'extension_requirements':[],'failures':[],'completion_scope':'Scripted infrastructure only'}
            obj = {'id':'research_cycle-fixture-' + kind,'kind':'research_cycle','version':2,'hash':hashlib.sha256(kind.encode()).hexdigest(),'payload':payload}
            records.append(obj);cycles[kind] = obj['id']
        for name, status, phase in [('failed','failed','audit'),('blocked','blocked','construct')]:
            obj = copy.deepcopy(records[-1]);obj.update(id='research_cycle-' + name,version=2)
            p = obj['payload'];p.update(status=status,phase=phase,job_id='root-' + name,completion_scope='Scripted infrastructure only')
            p['stages'][phase].update(status=status,error='Fixture checkpoint failure',failure_code='fixture_failure')
            if status == 'blocked':p['extension_requirements'] = [{'phase':phase,'code':'missing_capability','requirement':'browser_tools_required','implicit_fallback':False}]
            records.append(obj)
            old = copy.deepcopy(obj);old.update(version=1);old['payload'].update(status='running');records.append(old)
        self.fixture = {'records':records,'behavior':f.behavior['id'],'worlds':worlds,'cycles':cycles}
        self.assertEqual(f.lab.store.usage()['calls'], 0)

    def execute(self, script):
        result = subprocess.run([NODE, '-e', PRELUDE + script], input=json.dumps(self.fixture),text=True,capture_output=True,cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_exact_source_selection_review_guards_offline_defaults_and_live_budgets(self):
        self.execute(SELECTION)

    def test_saved_id_only_resumption_terminal_unknown_and_active_job_guards(self):
        self.execute(RESUMPTION)

    def test_world_specific_artifacts_stage_scope_versions_and_control_navigation(self):
        self.execute(WORLD_RENDERING)


if __name__ == '__main__':
    unittest.main()
