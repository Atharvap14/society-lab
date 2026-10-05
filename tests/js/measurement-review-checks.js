'use strict';
// Standalone Node checks: no server, browser actions, providers or production data.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const context={fetch(){throw new Error('Renderer attempted network access');},setTimeout(){throw new Error('Renderer attempted timer');},setInterval(){throw new Error('Renderer attempted timer');}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),context);
const ui=context.MeasurementReview,clone=x=>JSON.parse(JSON.stringify(x));
const H='a'.repeat(64),ref=id=>({id,version:1,hash:H});
function source(id,content='I am waiting for the shared artifact.') {
  return {id,timestamp:'2025-04-22T18:00:00Z',room_id:'room-1',agent_name:'Agent A',speaker_type:'agent',
    source:{file:'chat_messages.jsonl.gz',table:'chat_messages',line:1},source_sha256:H,source_record_sha256:H,
    declared_message_content_hash:H,full_content_utf8_sha256:H,content,
    content_characters:Array.from(content).length,content_truncated:false};
}
function judgment(sequence,message_id,label,reviewer_mode,reason='Declared interpretation') {
  return {sequence,message_id,label,reviewer_mode,reason,reviewer_id:'operator-1',recorded_at:'2026-10-04T06:00:00Z',predictions_visible:false};
}
function packet(included=false) {
  return {packet_version:'measurement-review-packet-v1',sample_ref:ref('sample-1'),review_ref:ref('review-1'),dataset_ref:ref('dataset-1'),
    construct:{question:'Does this message explicitly report waiting?',positive_definition:'Explicit report',negative_definition:'No explicit report',exclusions:['Quoted words alone are ambiguous.']},
    design:{population_size:20,sample_size:3,seed:11,inclusion_probability:3/20,sampling:'uniform_without_replacement',population_ids_sha256:H},
    instrument:{detector_id:'waiting',definition:'Literal marker',detector_version:'regex-v1',discovery_sha256:H,current_code_matches:true,predictions_scope:'frozen_historical_regex'},
    items:[
      {message_id:'m1',source_record:source('m1'),context:{before:[],after:[]},prediction:included ? {available:true,value:true,label:'yes',spans:[{start:5,end:12,text:'waiting'}]} : null,
        current_judgment:judgment(4,'m1','yes','manual_operator'),prior_judgments:[judgment(1,'m1','no','manual_operator')]},
      {message_id:'m2',source_record:source('m2','Do not wait; this is a quotation: "wait".'),context:{before:[],after:[]},prediction:included ? {available:true,value:false,label:'no',spans:[]} : null,
        current_judgment:judgment(3,'m2','uncertain','agent_assisted'),prior_judgments:[judgment(2,'m2','yes','synthetic_fixture')]},
      {message_id:'m3',source_record:source('m3','No declaration yet.'),context:{before:[],after:[]},prediction:included ? {available:false,value:null,label:null,spans:[]} : null,
        current_judgment:null,prior_judgments:[]}
    ],predictions_included:included,blinding_authenticated:false,calibration_established:false,
    labels:['yes','no','uncertain'],reviewer_modes:['manual_operator','agent_assisted','synthetic_fixture'],scope:'Message-level, bounded context',model_calls:0};
}
function report(p) {
  return {report_version:'measurement-review-report-v1',sample_ref:clone(p.sample_ref),review_ref:clone(p.review_ref),dataset_ref:clone(p.dataset_ref),
    totals:{sample_size:3,known_labels:1,uncertain_labels:1,missing_labels:1,available_predictions:2,unavailable_predictions:1,compared_messages:1},
    current_label_counts:{yes:1,no:0,uncertain:1,missing:1},
    current_labels_by_mode:{manual_operator:{yes:1,no:0,uncertain:0},agent_assisted:{yes:0,no:0,uncertain:1},synthetic_fixture:{yes:0,no:0,uncertain:0}},
    conflicting_declarations:[{message_id:'m1',labels:['yes','no'],reviewer_ids:['operator-1']}],
    metrics:{available:true,reason:null,confusion:{true_positive:1,false_positive:0,false_negative:0,true_negative:0},agreement:{numerator:1,denominator:1,fraction:1},precision:1,recall:1},
    instrument:clone(p.instrument),prediction_visibility:{current_declarations:{visible:0,hidden:2},all_declarations:{visible:0,hidden:4}},calibration_established:false,model_calls:0};
}
let checks=0;
function check(name,fn){fn();checks++;}

check('default hidden, exact source and sampling scope',()=>{
  const p=packet(),r=report(p),html=ui.render(p,r,{});
  assert(ui.validatePacket(p).valid);assert(ui.validateReport(p,r).valid);
  assert(html.includes('N=20 · k=3 · k/N=3/20 = 0.15'));assert(html.includes(H));assert(html.includes('data-review-message="m3"'));
  assert(html.includes('episode label'));assert(html.includes('Calibration established: false'));
  assert(!html.includes('Frozen historical regex prediction:'));assert(!html.includes('1 / 1 · 100.0%'));
  assert(html.includes('UI choice does not authenticate blinding'));
});
check('revealing requires explicit command AND included predictions',()=>{
  const hidden=packet(),p=packet(true);
  assert(!ui.render(hidden,report(hidden),{showPredictions:true}).includes('Frozen historical regex prediction:'));
  assert(!ui.render(p,report(p),{}).includes('Frozen historical regex prediction:'));
  const html=ui.render(p,report(p),{showPredictions:true});
  assert(html.includes('Frozen historical regex prediction: yes'));assert(html.includes('1 / 1 · 100.0%'));
  assert(html.includes('Known labels plus available-prediction subset only'));assert(html.includes('data-review-predictions="hide"'));
});
check('source, construct, history, context and draft escaping',()=>{
  const p=packet(),malicious='</pre><img src=x onerror=evil()><script>evil()</script>';
  p.items[0].source_record=source('m1',malicious);p.construct.question=malicious;p.items[0].context.before=[source('context',malicious)];
  p.items[0].source_record.source.file='"><img onerror=evil()>';
  const html=ui.render(p,report(p),{selectedId:'m1',draft:{message_id:'m1',label:'no',reason:'</textarea><script>evil()</script>',reviewer_id:'"><svg/onload=evil()>',reviewer_mode:'manual_operator'}});
  assert(ui.validatePacket(p).valid);assert(!html.includes('<img'));assert(!html.includes('<script>'));assert(!html.includes('<svg'));
  assert(html.includes('&lt;img'));assert(html.includes('&lt;/textarea&gt;'));assert(html.includes('data-review-save="m1"'));
});
check('unknown no-instrument quantities are not fabricated zeros',()=>{
  const p=packet(true);p.instrument.detector_id=null;p.instrument.detector_version=null;p.instrument.discovery_sha256=null;p.instrument.current_code_matches=null;p.instrument.predictions_scope='unavailable_no_instrument';
  for(const i of p.items){i.current_judgment=null;i.prior_judgments=[];i.prediction={available:false,value:null,label:null};}
  const r=report(p);r.totals={sample_size:3,known_labels:0,uncertain_labels:0,missing_labels:3,available_predictions:0,unavailable_predictions:3,compared_messages:0};
  r.current_label_counts={yes:0,no:0,uncertain:0,missing:3};for(const m of Object.values(r.current_labels_by_mode))Object.assign(m,{yes:0,no:0,uncertain:0});
  r.metrics={available:false,reason:'no instrument',confusion:null,agreement:null,precision:null,recall:null};r.prediction_visibility={current_declarations:{visible:0,hidden:0},all_declarations:{visible:0,hidden:0}};
  assert(ui.validateReport(p,r).valid);const html=ui.render(p,r,{showPredictions:true});
  assert(html.includes('subset only: Unknown'));assert(html.includes('agreement: Unknown'));assert(!html.includes('subset only: 0'));
});
check('all three exact refs block stale reports and metrics only',()=>{
  for(const refKey of ['sample_ref','review_ref','dataset_ref'])for(const field of ['id','version','hash']) {
    const p=packet(true),r=report(p);r[refKey][field]=field==='version' ? 2 : field==='hash' ? 'b'.repeat(64) : 'another-id';
    assert(!ui.validateReport(p,r).valid);const html=ui.render(p,r,{showPredictions:true});
    assert(html.includes('Stale or mismatched exact report'));assert(!html.includes('1 / 1 · 100.0%'));assert(html.includes('data-review-save="m1"'));
  }
});
check('mixed provenance remains declared, with retained prior disagreement',()=>{
  const p=packet(),html=ui.render(p,report(p),{});
  assert(html.includes('manual_operator'));assert(html.includes('agent_assisted'));assert(html.includes('synthetic_fixture'));
  assert(html.includes('do not authenticate a person'));assert(html.includes('<td>manual_operator</td><td>1</td><td>1</td><td>1</td>'));
  assert(html.includes('<td>synthetic_fixture</td><td>1</td><td>1</td><td>1</td>'));
});
check('save binds exact CAS source and stale drafts cannot label another message',()=>{
  const p=packet();p.review_ref.version=17;const html=ui.render(p,report(p),{selectedId:'m3',draft:{message_id:'m1',label:'yes',reason:'Wrong row',reviewer_id:'x',reviewer_mode:'manual_operator'}});
  assert(html.includes('data-review-save="m3"'));assert(html.includes('data-review-version="17"'));
  assert(html.includes('data-sample-hash="'+H+'"'));assert(!html.includes('Wrong row'));
  assert(!ui.render(p,report(p),{selectedId:'outside-sample'}).includes('data-review-save='));
});
check('invalid records fail closed, without truncating sample',()=>{
  const mutations=[p=>p.items.push(clone(p.items[0])),p=>p.items[0].source_record=null,
    p=>p.items[0].source_record.id='different-source',p=>p.items[0].context.before=[source('ctx')],
    p=>p.items[0].source_record.content='x'.repeat(2001),p=>p.design.sample_size=true,p=>p.design.population_size=20.5,
    p=>p.design.inclusion_probability=.5,p=>p.blinding_authenticated=true,p=>p.model_calls=false];
  // Context in a different room is not silently reinterpreted.
  mutations[3]=p=>{p.items[0].context.before=[source('ctx')];p.items[0].context.before[0].room_id='other-room';};
  for(const mutate of mutations){const p=packet();mutate(p);assert(!ui.validatePacket(p).valid);const html=ui.render(p,null,{});assert(!html.includes('data-review-save='));assert(html.includes('blocked'));}
});
check('Unicode source character counts and truncation are preserved',()=>{
  const p=packet();p.items[0].source_record=source('m1','😀 "wait"');
  assert(ui.validatePacket(p).valid);let html=ui.render(p,report(p),{});assert(html.includes('😀'));assert(html.includes('Full retained text: 8 declared characters'));
  p.items[0].source_record.content_characters=2005;p.items[0].source_record.content_truncated=true;
  html=ui.render(p,report(p),{});assert(html.includes('Truncated excerpt: 8 of 2005 declared characters'));
});
check('inconsistent and forged metric counts are withheld',()=>{
  const mutations=[r=>r.metrics.agreement.denominator=2,r=>r.metrics.agreement.fraction=0,r=>r.metrics.precision=NaN,
    r=>r.totals.known_labels=true,r=>r.calibration_established=true,r=>r.current_labels_by_mode.agent_assisted.uncertain=0,
    r=>r.metrics.confusion.false_positive=1,r=>r.totals.available_predictions=3];
  for(const mutate of mutations){const p=packet(true),r=report(p);mutate(r);assert(!ui.validateReport(p,r).valid);assert(!ui.render(p,r,{showPredictions:true}).includes('1 / 1 · 100.0%'));}
});
check('unavailable metrics cannot use zero to masquerade as known',()=>{
  const p=packet(),r=report(p);r.totals.compared_messages=0;r.metrics={available:false,reason:'unknown',confusion:null,agreement:null,precision:0,recall:null};
  assert(!ui.validateReport(p,r).valid);
});
check('input immutable, deterministic and no network/DOM dependencies',()=>{
  const p=packet(true),r=report(p),options={selectedId:'m2',showPredictions:true};const before=JSON.stringify([p,r,options]);
  const first=ui.render(p,r,options),second=ui.render(p,r,options);assert.strictEqual(first,second);assert.strictEqual(JSON.stringify([p,r,options]),before);
  assert(ui.sameRef(p.sample_ref,clone(p.sample_ref)));assert(!ui.sameRef(p.sample_ref,{...p.sample_ref,version:1.5}));
});
check('real producer schema fixture renders without field aliases',()=>{
  const f=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
  assert(ui.validatePacket(f.packet).valid,JSON.stringify(ui.validatePacket(f.packet)));
  assert(ui.validateReport(f.packet,f.report).valid,JSON.stringify(ui.validateReport(f.packet,f.report)));
  const html=ui.render(f.packet,f.report,{});assert(html.includes('data-review-save='));assert(!html.includes('Frozen historical regex prediction:'));
});
check('declared visibility retained and save matches actual displayed mode',()=>{
  const p=packet(true);p.items[0].current_judgment.predictions_visible=true;const r=report(p);
  r.prediction_visibility={current_declarations:{visible:1,hidden:1},all_declarations:{visible:1,hidden:3}};
  assert(ui.validateReport(p,r).valid);const html=ui.render(p,r,{showPredictions:true});
  assert(html.includes('data-predictions-visible="true"'));assert(html.includes('declared visible / hidden: 1 / 1'));
  const hidden=ui.render(p,r,{});assert(hidden.includes('data-predictions-visible="false"'));
  r.prediction_visibility.current_declarations.visible=0;assert(!ui.validateReport(p,r).valid);
});
check('known zero agreement stays zero while undefined positive recall stays unknown',()=>{
  const p=packet(true);p.items[0].current_judgment.label='no';const r=report(p);
  r.current_label_counts={yes:0,no:1,uncertain:1,missing:1};r.current_labels_by_mode.manual_operator={yes:0,no:1,uncertain:0};
  r.metrics={available:true,reason:null,confusion:{true_positive:0,false_positive:1,false_negative:0,true_negative:0},agreement:{numerator:0,denominator:1,fraction:0},precision:0,recall:null};
  assert(ui.validateReport(p,r).valid);const html=ui.render(p,r,{showPredictions:true});
  assert(html.includes('subset only: 0 / 1 · 0.0%'));assert(html.includes('predictive agreement: 0.0%'));assert(html.includes('reference agreement: Unknown'));
});
check('sequence, prediction, null code and strict bounds adversarial cases',()=>{
  const edits=[p=>p.items[0].prior_judgments[0].sequence=5,p=>p.items[0].current_judgment.predictions_visible='false',
    p=>p.items[0].source_record.source_record_sha256='bad',p=>p.items[0].current_judgment.reviewer_id='x'.repeat(81),
    p=>p.items[0].prediction={available:false,value:false,label:'no'},p=>p.items[1].current_judgment.sequence=4,
    p=>p.design.seed=Number.MAX_SAFE_INTEGER+1,p=>p.items[0].current_judgment.reason='   '];
  for(const edit of edits){const p=packet(true);edit(p);assert(!ui.validatePacket(p).valid);assert(!ui.render(p,null,{}).includes('data-review-save='));}
  const p=packet(),r=report(p);delete p.items[0].source_record.source.table;assert(ui.validatePacket(p).valid);assert(ui.render(p,r,{}).includes('Table unknown'));
});
check('queued readonly render disables save synchronously with exact expected identities',()=>{
  const p=packet(),r=report(p),expected={sample_ref:clone(p.sample_ref),review_ref:clone(p.review_ref)};
  const html=ui.render(p,r,{expected,saving:true});
  assert(/data-review-save="m1"[^>]*disabled aria-disabled="true"/.test(html));assert(html.includes('Declaration queued · saving'));
  assert(!ui.render(p,r,{expected,saving:false}).includes('aria-disabled="true"'));
  expected.review_ref.version=2;const wrong=ui.render(p,r,{expected,saving:false});assert(wrong.includes('Expected source mismatch'));assert(!wrong.includes('data-review-save='));
});
check('cheap operator declarations do not attest historical execution or semantic truth',()=>{
  const p=packet(true);Object.assign(p.instrument,{cheap_operator_check_performed:true,saved_predictions_match_current_operator:true,prediction_attestation:'matches_current_pinned_regex',historical_execution_attested:false});
  let r=report(p);assert(ui.validatePacket(p).valid);assert(ui.validateReport(p,r).valid);
  let html=ui.render(p,r,{showPredictions:true});assert(html.includes('historical execution is not attested'));assert(html.includes('does not authenticate raw source bytes or semantic labels'));
  Object.assign(p.instrument,{current_code_matches:false,cheap_operator_check_performed:false,saved_predictions_match_current_operator:null,prediction_attestation:'historical_saved_predictions_unverified'});
  r=report(p);assert(ui.validatePacket(p).valid);assert(ui.validateReport(p,r).valid);html=ui.render(p,r,{showPredictions:true});assert(html.includes('historical_saved_predictions_unverified'));
  p.instrument.saved_predictions_match_current_operator=true;assert(!ui.validatePacket(p).valid);
});
console.log(JSON.stringify({passed:true,checks,scope:'pure staged rendering; zero network/model/production actions'}));
