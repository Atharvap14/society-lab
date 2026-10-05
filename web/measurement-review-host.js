'use strict';
(() => {
  const ref = obj => ({id:obj.id,version:obj.version,hash:obj.hash});
  const same = (a,b) => a && b && Object.keys(a).length===3 && Object.keys(b).length===3 && a.id===b.id && a.version===b.version && a.hash===b.hash;
  const definitions = {
    blocker_report:['Does the speaker explicitly report inability to proceed or waiting on a dependency?','The speaker states a dependency or obstruction to proceeding.','Ordinary future work without a stated obstruction.'],
    completion_report:['Does the speaker report their own work completed?','An explicit first-person report of completed work. This does not verify completion.','Not yet done, conditional completion, or another agent’s quoted claim.'],
    correction:['Does the speaker explicitly correct a claim or report a specified error?','An explicit correction, retraction or specified error.','Disagreement without a specified correction.']
  };
  function state(b) {
    const a=b.app;
    if(!a.measurementReview) a.measurementReview={create:{dataset:'',detector:'blocker_report',question:definitions.blocker_report[0],positive:definitions.blocker_report[1],negative:definitions.blocker_report[2],exclusions:'',size:'16',seed:'42',neighbors:'1'},packet:null,report:null,expected:null,selectedId:null,drafts:{},showPredictions:false,pendingSave:null,pendingCreate:null};
    return a.measurementReview;
  }
  function pending(b,id) { return id && !['completed','failed'].includes(b.app.state.jobs.find(job=>job.id===id)?.status); }
  function queuedId(s,field,result) {
    if(typeof result?.job_id!=='string' || !/^job-[A-Za-z0-9._:-]{1,195}$/.test(result.job_id)) {
      s[field]='acknowledgement_unknown';
      throw new Error('Queue acknowledgement unavailable. Inspect Research audit before reloading; this form will not automatically repeat the write.');
    }
    return result.job_id;
  }
  function key(s,id=s.selectedId) { return `${s.packet?.sample_ref.id}@${s.packet?.sample_ref.version}:${id}`; }
  function draft(s) {
    const k=key(s),item=s.packet?.items.find(x=>x.message_id===s.selectedId);
    if(!s.drafts[k])s.drafts[k]={message_id:item?.message_id || s.selectedId,label:item?.current_judgment?.label || '',reason:item?.current_judgment?.reason || '',reviewer_id:item?.current_judgment?.reviewer_id || '',reviewer_mode:item?.current_judgment?.reviewer_mode || ''};
    return s.drafts[k];
  }
  async function load(b) {
    const s=state(b),id=b.selected('measurement_sample');
    if(!id){s.packet=null;s.report=null;s.expected=null;return;}
    const sample=await b.object(id);
    const review=await b.api(`/api/object/${encodeURIComponent(sample.payload.review_id)}`);
    if(sample.kind!=='measurement_sample' || review.kind!=='measurement_review')throw new Error('Measurement review source kinds differ.');
    const expected={sample_ref:ref(sample),review_ref:ref(review)};
    if(s.packet && same(s.expected?.sample_ref,expected.sample_ref) && same(s.expected?.review_ref,expected.review_ref) && s.packet.predictions_included===s.showPredictions)return;
    const q=new URLSearchParams({sample_id:sample.id,sample_version:String(sample.version),review_id:review.id,review_version:String(review.version),include_predictions:String(s.showPredictions)});
    const value=await b.api(`/api/measurement-review?${q}`);
    if(!same(value.packet?.sample_ref,expected.sample_ref) || !same(value.packet?.review_ref,expected.review_ref) || !same(value.report?.sample_ref,expected.sample_ref) || !same(value.report?.review_ref,expected.review_ref))throw new Error('Measurement packet/report do not match the exact requested sources.');
    if(!same(value.packet.dataset_ref,sample.payload.dataset_ref) || !same(value.report.dataset_ref,sample.payload.dataset_ref))throw new Error('Measurement dataset binding differs.');
    if(typeof MeasurementReview==='undefined' || !MeasurementReview.validatePacket(value.packet).valid)throw new Error('The measurement packet fails the presentation contract.');
    const newSample=!same(s.expected?.sample_ref,expected.sample_ref);
    s.packet=value.packet;s.report=value.report;s.expected=expected;
    if(newSample || !s.packet.items.some(x=>x.message_id===s.selectedId))s.selectedId=s.packet.items[0]?.message_id || null;
  }
  async function render(b) {
    const s=state(b),c=s.create,e=b.esc;
    for(const field of ['pendingSave','pendingCreate']) {
      const job=b.app.state.jobs.find(x=>x.id===s[field]);
      if(job && ['completed','failed'].includes(job.status)) {
        if(field==='pendingCreate' && job.status==='completed' && typeof job.payload?.result_ids==='string')b.app.selected.measurement_sample=job.payload.result_ids;
        s[field]=null;
      }
    }
    if(!b.all('dataset').some(x=>x.id===c.dataset))c.dataset=b.all('dataset')[0]?.id || '';
    await load(b);
    const datasetOptions=b.all('dataset').map(x=>`<option value="${e(x.id)}" ${x.id===c.dataset?'selected':''}>${e(x.id)} · v${x.version} · ${x.summary.messages} retained messages</option>`).join('');
    const detectorOptions=[['','Free binary question · no predictions'],['blocker_report','Dependency/blocker rule'],['completion_report','Completion-report rule'],['correction','Specified-correction rule']].map(([id,name])=>`<option value="${id}" ${id===c.detector?'selected':''}>${e(name)}</option>`).join('');
    const field=(id,label,max=2000)=>`<label class="small-label" for="review-create-${id}">${e(label)}</label><textarea class="control" id="review-create-${id}" data-review-create-field="${id}" maxlength="${max}">${e(c[id])}</textarea>`;
    const creating=!!pending(b,s.pendingCreate);
    const createLabel=s.pendingCreate==='acknowledgement_unknown' ? 'Submission status unknown · inspect Research audit' : creating ? 'Sample creation queued' : 'Freeze sample · zero model calls';
    const form=`<section class="panel"><div class="panel-heading"><div><h2>Freeze a review sample</h2><p>Draw from all retained messages in one exact dataset, including its declared speaker categories.</p></div></div><form id="measurement-sample-form" class="panel-body"><label class="small-label" for="review-create-dataset">Source dataset · current exact version</label><select class="control" id="review-create-dataset" data-review-create-field="dataset">${datasetOptions}</select><label class="small-label" for="review-create-detector">Optional existing instrument</label><select class="control" id="review-create-detector" data-review-create-field="detector">${detectorOptions}</select>${field('question','Binary operational question',4000)}${field('positive','Yes definition')}${field('negative','No definition')}${field('exclusions','Exclusions · one per line')}<div class="form-grid">${[['size','Sample messages',1,32],['seed','Sampling seed',0,Number.MAX_SAFE_INTEGER],['neighbors','Same-room neighbors per side',0,2]].map(([id,label,min,max])=>`<label class="small-label" for="review-create-${id}">${label}<input class="control" id="review-create-${id}" type="number" min="${min}" max="${max}" value="${e(c[id])}" data-review-create-field="${id}"></label>`).join('')}</div><p class="soft-text">A source sample freezes the construct and any regex predictions. It is not a representative independent adjudication or a claim of calibration. Local creation and review use no provider calls, regardless of the live-agent switch.</p><button class="button primary" type="submit" ${!c.dataset || creating?'disabled':''}>${createLabel}</button></form></section>`;
    const view=s.packet && typeof MeasurementReview!=='undefined' ? MeasurementReview.render(s.packet,s.report,{selectedId:s.selectedId,draft:draft(s),showPredictions:s.showPredictions,expected:s.expected,saving:s.pendingSave==='acknowledgement_unknown' ? 'unknown' : !!pending(b,s.pendingSave)}) : '<div class="note">Freeze a sample to begin. Missing judgments remain unknown.</div>';
    return b.header('MEASUREMENT REVIEW','Check the identifiers against records.','Keep operational definitions, source samples and reviewer declarations separate from behavioral findings.')+form+b.selector('measurement_sample')+'<p class="soft-text">The selected frozen sample opens its latest accepted review version. Research audit opens individual review objects as exact read-only records.</p>'+view;
  }
  function input(b,target) {
    const s=state(b);
    if(target.dataset.reviewCreateField!==undefined)s.create[target.dataset.reviewCreateField]=target.value;
    if(target.dataset.reviewField!==undefined && s.packet)draft(s)[target.dataset.reviewField]=target.value;
  }
  async function change(b,target) {
    input(b,target);
    if(target.dataset.reviewCreateField==='detector'){
      const values=definitions[target.value];if(values){const s=state(b);[s.create.question,s.create.positive,s.create.negative]=values;}
      await b.render();
    }
  }
  async function create(b) {
    const s=state(b),c={...s.create};
    if(pending(b,s.pendingCreate))throw new Error('The previous sample creation is still pending.');
    s.pendingCreate='submitting';
    try {
      const dataset=await b.object(c.dataset);
      if(!dataset || dataset.kind!=='dataset')throw new Error('Select an exact source dataset.');
      const args={dataset_ref:ref(dataset),question:c.question,positive_definition:c.positive,negative_definition:c.negative,exclusions:c.exclusions.split('\n').map(x=>x.trim()).filter(Boolean),sample_size:b.integer(c.size,'Sample size',1,32),seed:b.integer(c.seed,'Sampling seed',0,Number.MAX_SAFE_INTEGER),context_neighbors:b.integer(c.neighbors,'Context neighbors',0,2),detector_id:c.detector || null};
      const result=await b.enqueue('create_measurement_sample',args);s.pendingCreate=queuedId(s,'pendingCreate',result);
    }
    catch(error) { if(s.pendingCreate==='submitting')s.pendingCreate=null;throw error; }
    await b.render();
  }
  async function click(b,target) {
    const s=state(b);
    if(target.dataset.reviewMessage!==undefined){
      if(!s.packet?.items.some(x=>x.message_id===target.dataset.reviewMessage))throw new Error('Message is outside the frozen sample.');
      s.selectedId=target.dataset.reviewMessage;await b.render();return;
    }
    if(target.dataset.reviewPredictions!==undefined){s.showPredictions=!s.showPredictions;await b.render();return;}
    if(target.dataset.reviewSave!==undefined){
      if(pending(b,s.pendingSave))throw new Error('The previous judgment is still pending.');
      if(!s.packet || !same(s.packet.sample_ref,s.expected?.sample_ref) || !same(s.packet.review_ref,s.expected?.review_ref))throw new Error('Reload an exact review packet before saving.');
      if(typeof MeasurementReview==='undefined' || !MeasurementReview.validatePacket(s.packet).valid)throw new Error('The measurement packet fails the presentation contract.');
      if(target.dataset.reviewSave!==s.selectedId || target.dataset.sampleId!==s.packet.sample_ref.id || target.dataset.sampleVersion!==String(s.packet.sample_ref.version) || target.dataset.sampleHash!==s.packet.sample_ref.hash || target.dataset.reviewId!==s.packet.review_ref.id || target.dataset.reviewVersion!==String(s.packet.review_ref.version) || target.dataset.reviewHash!==s.packet.review_ref.hash || target.dataset.predictionsVisible!==String(s.showPredictions && s.packet.predictions_included))throw new Error('This save control belongs to a different review or visibility state; reload the exact packet.');
      const d=draft(s);
      if(!['yes','no','uncertain'].includes(d.label) || !['manual_operator','agent_assisted','synthetic_fixture'].includes(d.reviewer_mode) || !d.reason.trim() || d.reason.length>1000 || !d.reviewer_id.trim() || d.reviewer_id.length>80)throw new Error('Choose a label and declared reviewer mode, with a reason (≤1,000 characters) and reviewer identifier (≤80).');
      const args={sample_ref:s.packet.sample_ref,message_id:s.selectedId,label:d.label,reason:d.reason,reviewer_id:d.reviewer_id,reviewer_mode:d.reviewer_mode,expected_review_version:s.packet.review_ref.version,predictions_visible:s.showPredictions};
      s.pendingSave='submitting';
      try { const result=await b.enqueue('record_measurement_judgment',args);s.pendingSave=queuedId(s,'pendingSave',result); }
      catch(error) { if(s.pendingSave==='submitting')s.pendingSave=null;throw error; }
      await b.render();
    }
  }
  globalThis.MeasurementReviewHost={render,input,change,create,click,load};
})();
