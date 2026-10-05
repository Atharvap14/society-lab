"""Execute measurement host routes with local API stubs and the producer fixture.

No server jobs, model calls, registry mutations, or source-file reads occur.
The fixture is authored and tests source/route identity, not label quality.
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which('node')

SCRIPT = r"""
'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const [renderer,host,fixturePath,scenario,appPath]=process.argv.slice(1);
const fixture=JSON.parse(fs.readFileSync(fixturePath,'utf8'));
vm.runInThisContext(fs.readFileSync(renderer,'utf8'),{filename:renderer});
vm.runInThisContext(fs.readFileSync(host,'utf8'),{filename:host});
const copy=x=>JSON.parse(JSON.stringify(x));
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}};
const pin=x=>({id:x.id,version:x.version,hash:x.hash});
function environment(){
  const sample={...copy(fixture.packet.sample_ref),kind:'measurement_sample',payload:{review_id:fixture.packet.review_ref.id,dataset_ref:copy(fixture.packet.dataset_ref)}};
  const review={...copy(fixture.packet.review_ref),kind:'measurement_review',payload:{sample_ref:pin(sample)}};
  const dataset={...copy(fixture.packet.dataset_ref),kind:'dataset',summary:{messages:fixture.packet.design.population_size},payload:{}};
  const e={sample,review,dataset,gets:[],objects:[],queued:[],renderCount:0,workspaceMutation:null,sourceWait:null,enqueueWait:null};
  const app={state:{jobs:[],objects:[sample,review,dataset]},selected:{measurement_sample:sample.id}};
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  e.b={app,esc,all:kind=>app.state.objects.filter(x=>x.kind===kind),selected:kind=>app.selected[kind]||null,
    object:async id=>{e.objects.push(id);if(id===dataset.id && e.sourceWait)await e.sourceWait.promise;return copy(app.state.objects.find(x=>x.id===id));},
    api:async path=>{
      e.gets.push(path);
      if(path==='/api/object/'+encodeURIComponent(review.id))return copy(review);
      if(path.startsWith('/api/measurement-review?')){
        const q=new URLSearchParams(path.split('?')[1]),value=copy(fixture);
        value.packet.predictions_included=q.get('include_predictions')==='true';
        for(const item of value.packet.items)item.prediction=value.packet.predictions_included ? {available:true,value:item.message_id===value.packet.items[0].message_id,label:item.message_id===value.packet.items[0].message_id?'yes':'no',spans:[],reason:null}:null;
        if(e.workspaceMutation)e.workspaceMutation(value);
        return value;
      }
      throw new Error('Unexpected API read '+path);
    },
    integer:(value,name,min,max)=>{const n=Number(value);if(!Number.isSafeInteger(n)||n<min||n>max)throw new Error(name);return n;},
    enqueue:async(action,args)=>{e.queued.push({action,args:copy(args)});if(e.enqueueWait)return e.enqueueWait.promise;return {job_id:'job-fixture-'+e.queued.length};},
    render:async()=>{e.renderCount++;},header:()=>'',selector:()=>''};
  return e;
}
async function ready(e){await MeasurementReviewHost.render(e.b);const s=e.b.app.measurementReview;s.selectedId=s.packet.items[0].message_id;for(const [name,value] of Object.entries({label:'yes',reason:'Authored route fixture',reviewer_id:'fixture-reviewer',reviewer_mode:'synthetic_fixture'}))MeasurementReviewHost.input(e.b,{dataset:{reviewField:name},value});return s;}
function button(s){return {dataset:{reviewSave:s.selectedId,sampleId:s.packet.sample_ref.id,sampleVersion:String(s.packet.sample_ref.version),sampleHash:s.packet.sample_ref.hash,reviewId:s.packet.review_ref.id,reviewVersion:String(s.packet.review_ref.version),reviewHash:s.packet.review_ref.hash,predictionsVisible:String(s.showPredictions&&s.packet.predictions_included)}};}
function formFields(html,id){
  const form=html.match(new RegExp('<form data-review-form="'+id+'">([\\s\\S]*?)</form>'))?.[1];assert.ok(form,'Selected declaration form is visible');
  function selection(name){const select=form.match(new RegExp('<select data-review-field="'+name+'"[^>]*>([\\s\\S]*?)</select>'))?.[1];assert.ok(select);return select.match(/<option value="([^"]*)"[^>]*\sselected(?:\s|>)/)?.[1]||'';}
  return {label:selection('label'),reviewer_mode:selection('reviewer_mode'),reviewer_id:form.match(/<input data-review-field="reviewer_id"[^>]* value="([^"]*)"/)?.[1],reason:form.match(/<textarea data-review-field="reason"[^>]*>([\s\S]*?)<\/textarea>/)?.[1]};
}
function editFields(e,values){for(const [name,value] of Object.entries(values))MeasurementReviewHost.input(e.b,{dataset:{reviewField:name},value});}
function appEnvironment(){
  const nodes=new Map(),listeners={},requests=[];
  function node(key){if(!nodes.has(key))nodes.set(key,{innerHTML:'',textContent:'',className:'',open:false,dataset:{},classList:{toggle(){},add(){},remove(){}},addEventListener(){},contains(){return false},focus(){},scrollIntoView(){},close(){this.open=false},showModal(){this.open=true}});return nodes.get(key);}
  const context=vm.createContext({console,URLSearchParams,Set,Map,Date,JSON,Promise,setTimeout:()=>1,clearTimeout(){},setInterval:()=>1,CSS:{escape:s=>s},window:{scrollTo(){}},document:{activeElement:null,getElementById:node,querySelector:node,querySelectorAll:()=>[],addEventListener(type,handler){(listeners[type]??=[]).push(handler)}},fetch:async(path,settings={})=>{requests.push({path,settings});throw new Error('Unexpected request '+path)}});
  vm.runInContext(fs.readFileSync(renderer,'utf8'),context,{filename:renderer});vm.runInContext(fs.readFileSync(host,'utf8'),context,{filename:host});
  const actual=fs.readFileSync(appPath,'utf8');assert.ok(actual.includes('refresh(true);\nsetInterval(() => refresh(),4500);') || actual.includes('refresh(true);\r\nsetInterval(() => refresh(),4500);'));
  vm.runInContext(actual.replace(/refresh\(true\);\r?\nsetInterval\(\(\) => refresh\(\),4500\);\s*$/,''),context,{filename:appPath});
  const app=vm.runInContext('app',context);app.state={objects:[],jobs:[],usage:{calls:400},max_calls:400,csrf:'local-fixture',model:'Authored fixture'};
  // Navigation is exercised with the actual object/router functions. Rendering and
  // refresh are inert so the fixture cannot start unrelated panes or API reads.
  vm.runInContext('render=async()=>{};refresh=async()=>{};',context);
  return {context,app,nodes,listeners,requests,node};
}
async function run(){
  if(scenario==='exact_get'){
    const e=environment(),html=await MeasurementReviewHost.render(e.b),reads=e.gets.filter(p=>p.startsWith('/api/measurement-review?'));assert.equal(reads.length,1);
    const q=new URLSearchParams(reads[0].split('?')[1]);assert.deepEqual([...q.keys()].sort(),['include_predictions','review_id','review_version','sample_id','sample_version']);
    assert.equal(q.get('sample_id'),e.sample.id);assert.equal(q.get('sample_version'),String(e.sample.version));assert.equal(q.get('review_id'),e.review.id);assert.equal(q.get('review_version'),String(e.review.version));assert.equal(q.get('include_predictions'),'false');
    assert.equal(e.queued.length,0);assert.ok(html.includes('Predictions are hidden'));assert.ok(!html.includes('Frozen historical regex prediction:'));assert.ok(html.includes('N='+fixture.packet.design.population_size));assert.ok(html.includes('k='+fixture.packet.design.sample_size));
  }else if(scenario==='stale_buttons'){
    for(const field of ['reviewSave','sampleId','sampleVersion','sampleHash','reviewId','reviewVersion','reviewHash','predictionsVisible']){
      const e=environment(),s=await ready(e),target=button(s);target.dataset[field]+='-stale';await assert.rejects(MeasurementReviewHost.click(e.b,target),/different review|visibility/);assert.equal(e.queued.length,0,field);
    }
    const e=environment(),s=await ready(e),target=button(s);s.expected.sample_ref.hash='b'.repeat(64);await assert.rejects(MeasurementReviewHost.click(e.b,target),/exact review packet/);assert.equal(e.queued.length,0);
  }else if(scenario==='save_and_pending'){
    const e=environment(),s=await ready(e);e.enqueueWait=deferred();const target=button(s),first=MeasurementReviewHost.click(e.b,target);
    await assert.rejects(MeasurementReviewHost.click(e.b,target),/still pending/);assert.equal(e.queued.length,1);assert.equal(e.queued[0].action,'record_measurement_judgment');
    assert.deepEqual(e.queued[0].args.sample_ref,fixture.packet.sample_ref);assert.equal(e.queued[0].args.expected_review_version,fixture.packet.review_ref.version);assert.equal(e.queued[0].args.predictions_visible,false);assert.ok(!Object.hasOwn(e.queued[0].args,'live'));assert.ok(!Object.hasOwn(e.queued[0].args,'model'));
    e.enqueueWait.resolve({job_id:'job-delayed'});await first;await assert.rejects(MeasurementReviewHost.click(e.b,target),/still pending/);assert.equal(e.queued.length,1);
    e.b.app.state.jobs.push({id:'job-delayed',status:'failed',payload:{error:'Fixture CAS conflict'}});await MeasurementReviewHost.render(e.b);assert.equal(s.pendingSave,null);
  }else if(scenario==='create_race'){
    const e=environment(),s=await ready(e);e.sourceWait=deferred();const first=MeasurementReviewHost.create(e.b),second=MeasurementReviewHost.create(e.b);const observed=Promise.allSettled([first,second]);e.sourceWait.resolve();const outcomes=await observed;
    assert.equal(e.queued.length,1,'Only one source-sampling job may be queued while source lookup is pending');assert.equal(outcomes.filter(x=>x.status==='rejected').length,1);
    assert.equal(e.queued[0].action,'create_measurement_sample');assert.deepEqual(e.queued[0].args.dataset_ref,fixture.packet.dataset_ref);assert.ok(!Object.hasOwn(e.queued[0].args,'live'));assert.ok(!Object.hasOwn(e.queued[0].args,'model'));
  }else if(scenario==='create_snapshot'){
    const e=environment(),s=await ready(e),original=s.create.question;e.sourceWait=deferred();const first=MeasurementReviewHost.create(e.b);s.create.question='Changed during source lookup';s.create.size='1';e.sourceWait.resolve();await first;
    assert.equal(e.queued[0].args.question,original,'The queued construct must match the submitted form snapshot');assert.equal(e.queued[0].args.sample_size,16);
  }else if(scenario==='visibility'){
    const e=environment(),s=await ready(e);e.b.render=async()=>{e.renderCount++;return MeasurementReviewHost.render(e.b)};
    await MeasurementReviewHost.click(e.b,{dataset:{reviewPredictions:'show'}});assert.equal(s.showPredictions,true);assert.equal(s.packet.predictions_included,true);assert.equal(new URLSearchParams(e.gets.at(-1).split('?')[1]).get('include_predictions'),'true');assert.equal(e.queued.length,0);
    const stale=button(s);await MeasurementReviewHost.click(e.b,{dataset:{reviewPredictions:'hide'}});assert.equal(s.packet.predictions_included,false);assert.equal(s.showPredictions,false);assert.equal(new URLSearchParams(e.gets.at(-1).split('?')[1]).get('include_predictions'),'false');await assert.rejects(MeasurementReviewHost.click(e.b,stale),/visibility/);assert.equal(e.queued.length,0);
  }else if(scenario==='source_mismatch'){
    for(const which of ['packet','report'])for(const key of ['sample_ref','review_ref','dataset_ref']){
      const e=environment();e.workspaceMutation=value=>{value[which][key].hash='b'.repeat(64)};await assert.rejects(MeasurementReviewHost.load(e.b),/sources|binding/);assert.equal(e.queued.length,0);assert.equal(e.b.app.measurementReview.packet,null);
    }
  }else if(scenario==='edited_draft'){
    const e=environment();await MeasurementReviewHost.render(e.b);const s=e.b.app.measurementReview,id=s.selectedId,other=s.packet.items.find(x=>x.message_id!==id).message_id;
    const edits={label:'no',reviewer_mode:'agent_assisted',reviewer_id:'edited-reviewer',reason:'Edited <rival> & context, not the saved declaration.'};editFields(e,edits);
    const expected={...edits,reviewer_id:e.b.esc(edits.reviewer_id),reason:e.b.esc(edits.reason)};
    assert.deepEqual(formFields(await MeasurementReviewHost.render(e.b),id),expected);
    await MeasurementReviewHost.click(e.b,{dataset:{reviewMessage:other}});await MeasurementReviewHost.render(e.b);
    await MeasurementReviewHost.click(e.b,{dataset:{reviewMessage:id}});assert.deepEqual(formFields(await MeasurementReviewHost.render(e.b),id),expected);
    const previousReads=e.gets.filter(x=>x.startsWith('/api/measurement-review?')).length;
    s.packet=null;s.report=null;s.expected=null; // Re-fetch exact packet; preserve this page's local draft map.
    const reloaded=await MeasurementReviewHost.render(e.b);assert.equal(e.gets.filter(x=>x.startsWith('/api/measurement-review?')).length,previousReads+1);assert.deepEqual(formFields(reloaded,id),expected);
    assert.equal(s.packet.items.find(x=>x.message_id===id).current_judgment.label,fixture.packet.items.find(x=>x.message_id===id).current_judgment.label,'Local edits must not rewrite the accepted reference');
    await MeasurementReviewHost.click(e.b,button(s));assert.equal(e.queued.length,1);for(const [name,value] of Object.entries(edits))assert.equal(e.queued[0].args[name],value,name);assert.equal(e.queued[0].args.message_id,id);
  }else if(scenario==='unjudged_draft'){
    const e=environment();await MeasurementReviewHost.render(e.b);const s=e.b.app.measurementReview,id=s.packet.items.find(x=>x.current_judgment===null).message_id;
    await MeasurementReviewHost.click(e.b,{dataset:{reviewMessage:id}});const blank=formFields(await MeasurementReviewHost.render(e.b),id);assert.deepEqual(blank,{label:'',reviewer_mode:'',reviewer_id:'',reason:''});
    editFields(e,{reason:'A reason alone is not a label or provenance choice.',reviewer_id:'new-reviewer'});
    await assert.rejects(MeasurementReviewHost.click(e.b,button(s)),/Choose a label/);assert.equal(e.queued.length,0);
    editFields(e,{label:'uncertain'});await assert.rejects(MeasurementReviewHost.click(e.b,button(s)),/Choose a label/);assert.equal(e.queued.length,0);
    editFields(e,{reviewer_mode:'agent_assisted'});await MeasurementReviewHost.click(e.b,button(s));assert.equal(e.queued.length,1);assert.equal(e.queued[0].args.label,'uncertain');assert.equal(e.queued[0].args.reviewer_mode,'agent_assisted');assert.equal(e.queued[0].args.message_id,id);
  }else if(scenario==='current_provenance'){
    const e=environment(),html=await MeasurementReviewHost.render(e.b),s=e.b.app.measurementReview,current=s.packet.items.find(x=>x.message_id===s.selectedId).current_judgment;
    assert.ok(current);const expected=Object.fromEntries(['label','reviewer_mode','reviewer_id','reason'].map(key=>[key,e.b.esc(current[key])]));assert.deepEqual(formFields(html,s.selectedId),expected);
    const local=s.drafts[s.packet.sample_ref.id+'@'+s.packet.sample_ref.version+':'+s.selectedId];assert.equal(local.message_id,s.selectedId);for(const key of Object.keys(expected))assert.equal(local[key],current[key]);
    await MeasurementReviewHost.click(e.b,button(s));for(const key of Object.keys(expected))assert.equal(e.queued[0].args[key],current[key]);assert.equal(e.queued[0].args.expected_review_version,s.packet.review_ref.version);
  }else if(scenario==='bad_create_ack' || scenario==='bad_save_ack'){
    for(const ack of [undefined,null,{}, {job_id:''},{job_id:17},{job_id:'not-a-job'}, {job_id:'job-fixture',extra:true}]){
      // Extra fields are harmless if the exact job identity is valid; the final
      // case checks that the host does not require a brittle envelope equality.
      const e=environment(),s=await ready(e);e.b.enqueue=async(action,args)=>{e.queued.push({action,args:copy(args)});return ack};
      const action=scenario==='bad_create_ack' ? ()=>MeasurementReviewHost.create(e.b) : ()=>MeasurementReviewHost.click(e.b,button(s));
      if(ack?.job_id==='job-fixture')await action();else {
        await assert.rejects(action(),/job|acknowledg|queue/i);
        assert.equal(s[scenario==='bad_create_ack'?'pendingCreate':'pendingSave'],'acknowledgement_unknown');
        const html=await MeasurementReviewHost.render(e.b),label=scenario==='bad_create_ack' ? 'Submission status unknown · inspect Research audit' : 'Save status unknown · inspect Research audit';
        assert.ok(html.includes(label),'An unknown acknowledgement must not be presented as confirmed queueing');
        assert.ok(new RegExp('<button[^>]*disabled[^>]*>'+label.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'</button>').test(html),'Unknown-status write control stays disabled');
        assert.ok(!html.includes(scenario==='bad_create_ack' ? '>Sample creation queued</button>' : '>Declaration queued · saving</button>'));
        await assert.rejects(action(),/still pending/);
      }
      assert.equal(e.queued.length,1);
    }
  }else if(scenario==='native_form'){
    const e=appEnvironment();let prevented=0;const event={target:{id:'',dataset:{reviewForm:fixture.packet.items[0].message_id}},preventDefault(){prevented++}};
    for(const handler of e.listeners.submit)await handler(event);assert.equal(prevented,1,'Native declaration form submission must not navigate/reload');assert.equal(e.requests.length,0);
  }else if(scenario==='output_routing'){
    const e=appEnvironment(),sample={...copy(fixture.packet.sample_ref),kind:'measurement_sample',payload:{review_id:fixture.packet.review_ref.id,dataset_ref:copy(fixture.packet.dataset_ref)}};
    const review={...copy(fixture.packet.review_ref),kind:'measurement_review',payload:{sample_ref:copy(fixture.packet.sample_ref),events:[]}};
    e.app.state.objects=[sample,review];e.app.cache.set(sample.id,sample);e.app.cache.set(review.id,review);
    e.context.output_ids=[sample.id,review.id];const ids=vm.runInContext('uniqueIds(output_ids)',e.context);assert.deepEqual(Array.from(ids),[sample.id,review.id]);
    e.context.sample_id=sample.id;await vm.runInContext('openObject(sample_id)',e.context);assert.equal(e.app.view,'measurement');assert.equal(e.app.selected.measurement_sample,sample.id);
    // Ask for an older exact review while the inventory advertises a newer one.
    // The saved read-only object must not silently become the latest review.
    e.app.state.objects[1]={...review,version:review.version+1,hash:'c'.repeat(64)};e.app.cache.set(review.id+'@'+review.version,review);
    e.context.review_id=review.id;e.context.review_version=review.version;await vm.runInContext('openObject(review_id,review_version)',e.context);
    assert.equal(e.node('evidence-dialog').open,true);const body=e.node('dialog-body').innerHTML;
    assert.ok(body.includes(review.hash));assert.ok(!body.includes('c'.repeat(64)));assert.ok(body.includes(sample.hash));assert.ok(body.includes('read-only') || body.includes('read only') || body.includes('exact review version'));assert.ok(!body.includes('data-review-save='));assert.equal(e.requests.length,0);
  }else throw new Error('Unknown scenario');
  process.stdout.write(JSON.stringify({passed:true,scenario}));
}
run().catch(error=>{process.stderr.write(error.stack);process.exitCode=1});
"""


@unittest.skipUnless(NODE, 'Node.js is required for executable host-route checks')
class MeasurementReviewHostTests(unittest.TestCase):
    def check(self, scenario):
        result = subprocess.run(
            [NODE, '-e', SCRIPT, str(ROOT/'web/measurement-review.js'),
             str(ROOT/'web/measurement-review-host.js'),
             str(ROOT/'tests/fixtures/measurement-review-schema.json'), scenario,
             str(ROOT/'web/app.js')],
            capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIs(json.loads(result.stdout)['passed'], True)

    def test_exact_get_source_versions_counts_and_default_hidden_predictions(self):
        self.check('exact_get')

    def test_stale_clicked_save_control_cannot_queue_a_declaration(self):
        self.check('stale_buttons')

    def test_exact_save_and_unknown_pending_job_prevent_duplicate(self):
        self.check('save_and_pending')

    def test_concurrent_creation_reserves_guard_before_source_await(self):
        self.check('create_race')

    def test_creation_snapshots_the_construct_before_source_await(self):
        self.check('create_snapshot')

    def test_show_hide_fetch_exact_packets_without_jobs_or_stale_visibility_save(self):
        self.check('visibility')

    def test_mismatched_packet_report_or_dataset_sources_fail_closed(self):
        self.check('source_mismatch')

    def test_create_requires_a_valid_queue_job_acknowledgement(self):
        self.check('bad_create_ack')

    def test_save_requires_a_valid_queue_job_acknowledgement(self):
        self.check('bad_save_ack')

    def test_actual_app_intercepts_native_review_form_submission(self):
        self.check('native_form')

    def test_actual_app_routes_measurement_outputs_to_review_inspection(self):
        self.check('output_routing')

    def test_edited_draft_remains_displayed_after_navigation_and_exact_packet_reload(self):
        self.check('edited_draft')

    def test_unjudged_row_requires_explicit_label_and_reviewer_mode(self):
        self.check('unjudged_draft')

    def test_current_declaration_provenance_initializes_display_and_save_state(self):
        self.check('current_provenance')
