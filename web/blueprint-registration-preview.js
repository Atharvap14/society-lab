/* Read-only registration compatibility presentation. No protocol construction. */
(function(root) {
  'use strict';
  const gates=['construction_compiled','fit_approved_analogue','current_source_authorization','design_compatible','exact_world_preserved'];
  const kinds=['protocol','network_protocol','complementary_protocol','resource_protocol'];
  const esc=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const object=value=>value!==null && typeof value==='object' && !Array.isArray(value);
  const text=(value,max)=>typeof value==='string' && value.trim().length>0 && value.length<=max;
  const integer=(value,min,max)=>Number.isSafeInteger(value) && value>=min && value<=max;
  function ref(value) {
    return object(value) && Object.keys(value).sort().join(',')==='hash,id,version' && text(value.id,200) && /^[A-Za-z0-9][A-Za-z0-9_.:-]*$/.test(value.id) && integer(value.version,1,1000000000) && typeof value.hash==='string' && /^[0-9a-f]{64}$/.test(value.hash);
  }
  function expectation(record,live) {
    if(!object(record) || record.kind!=='environment_blueprint' || typeof live!=='boolean')throw new Error('An exact environment blueprint and explicit subject mode are required.');
    const target={id:record.id,version:record.version,hash:record.hash};
    if(!ref(target))throw new Error('The displayed blueprint identity is unavailable.');
    return {blueprint_ref:target,registration_plan:{trials_per_cell:2,seed:4491,live}};
  }
  function validate(packet,expected) {
    if(!object(expected) || !ref(expected.blueprint_ref) || !object(expected.registration_plan) || expected.registration_plan.trials_per_cell!==2 || expected.registration_plan.seed!==4491 || typeof expected.registration_plan.live!=='boolean')throw new Error('Displayed registration settings are unavailable.');
    if(!object(packet) || packet.preview_version!=='registration-compatibility-preview-v1' || !ref(packet.blueprint_ref) || ['id','version','hash'].some(k=>packet.blueprint_ref[k]!==expected.blueprint_ref[k]))throw new Error('Compatibility preview does not match this exact blueprint.');
    const plan=packet.registration_plan;
    if(!object(plan) || Object.keys(plan).sort().join(',')!=='live,seed,trials_per_cell' || ['live','seed','trials_per_cell'].some(k=>plan[k]!==expected.registration_plan[k]))throw new Error('Compatibility preview does not match these registration settings.');
    if(packet.registered!==false || packet.model_calls!==0 || packet.database_writes!==0 || packet.raw_source_reread!==false)throw new Error('A read-only, zero-call preview is required.');
    if(!object(packet.checks) || Object.keys(packet.checks).sort().join(',')!==gates.slice().sort().join(',') || gates.some(k=>![true,false,null].includes(packet.checks[k])))throw new Error('Compatibility checks are malformed.');
    if(!Array.isArray(packet.limits) || packet.limits.length>16 || packet.limits.some(x=>!text(x,2000)))throw new Error('Compatibility limits are malformed.');
    if(packet.status==='blocked') {
      if(packet.design!==null || gates.every(k=>packet.checks[k]===true) || !object(packet.reason) || !text(packet.reason.stage,80) || !text(packet.reason.code,100) || !text(packet.reason.message,2000))throw new Error('Blocked compatibility preview is malformed.');
      return packet;
    }
    const d=packet.design;
    if(packet.status!=='compatible' || gates.some(k=>packet.checks[k]!==true) || packet.reason!==null || !object(d) || !kinds.includes(d.object_kind) || !text(d.study_kind,100) || !text(d.research_question,4000) || !text(d.experimental_unit,500) || !text(d.primary_outcome,2000) || !text(d.primary_contrast,2000) || !Array.isArray(d.conditions) || d.conditions.length<2 || d.conditions.length>16 || d.conditions.some(x=>!text(x,300)) || new Set(d.conditions).size!==d.conditions.length || !integer(d.maximum_units,1,1000000) || d.maximum_units!==plan.trials_per_cell*d.conditions.length || !integer(d.maximum_subject_calls,0,1000000000) || !integer(d.maximum_hosted_subject_calls,0,1000000000) || !object(d.subject_backend) || !text(d.subject_backend.harness,80) || !text(d.subject_backend.model,200) || typeof d.world_spec_hash!=='string' || !/^[0-9a-f]{64}$/.test(d.world_spec_hash))throw new Error('Compatible design declaration is malformed.');
    if(d.subject_backend.harness!==(plan.live ? 'responses' : 'scripted') || d.maximum_hosted_subject_calls!==(plan.live ? d.maximum_subject_calls : 0))throw new Error('Preview subject mode contradicts its allocation.');
    return packet;
  }
  function launchArgs(packet,expected) {
    const p=validate(packet,expected);
    if(p.status!=='compatible')throw new Error('No compatible registered design is available for this exact blueprint.');
    return {blueprint_id:p.blueprint_ref.id,blueprint_version:p.blueprint_ref.version,blueprint_hash:p.blueprint_ref.hash,trials_per_cell:p.registration_plan.trials_per_cell,seed:p.registration_plan.seed,live:p.registration_plan.live};
  }
  function render(packet,expected,options={}) {
    let p;try { p=validate(packet,expected); } catch(error) { return `<section class="panel"><div class="panel-heading"><h2>Registration compatibility unavailable</h2></div><div class="panel-body"><p>${esc(error.message)}</p><p>Construction approval does not establish that a study can preserve the world. Registration remains unavailable until an exact current preview can be checked.</p></div></section>`; }
    const labels={construction_compiled:'World compiled',fit_approved_analogue:'Bound analogue fit review',current_source_authorization:'Current source and implementation checks',design_compatible:'Available study design',exact_world_preserved:'Authored world preserved exactly'};
    const checks=`<dl class="key-value">${gates.map(k=>`<dt>${labels[k]}</dt><dd>${p.checks[k]===true ? 'Passed' : p.checks[k]===false ? 'Failed' : 'Not checked'}</dd>`).join('')}</dl>`;
    const limits=`<details class="commentary-detail"><summary>Compatibility scope</summary><ul>${p.limits.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></details>`;
    const boundary='<div class="note">This is an unregistered, read-only preview. It creates no protocol, job, subject call or library status change. Actual registration rechecks this exact blueprint and the current source/implementation. Design compatibility does not identify the proposed mechanism.</div>';
    let body;
    if(p.status==='blocked')body=`<p class="error-text">${esc(p.reason.message)}</p><p>${esc(p.reason.stage)} · ${esc(p.reason.code)}</p>${checks}`;
    else {
      const d=p.design,r=p.blueprint_ref;
      const attempt=options?.registrationAttempt;
      const action=attempt ? `<button class="button" disabled>Registration already requested</button><p>${attempt.phase==='queued' && typeof attempt.job_id==='string' && /^job-[A-Za-z0-9_.:-]{1,100}$/.test(attempt.job_id) ? `Job ${esc(attempt.job_id)} is queued. <button class="button-link" data-trace="${esc(attempt.job_id)}">Inspect registration job</button>` : attempt.phase==='pending' ? 'Waiting for the queue acknowledgment.' : 'Queue acknowledgment is unknown. Inspect Research audit before repeating; this view will not automatically retry.'}</p>` : `<button class="button" data-blueprint-register="${esc(r.id)}" data-blueprint-version="${r.version}" data-blueprint-hash="${r.hash}" data-blueprint-live="${p.registration_plan.live}">Register compatible context study</button>`;
      body=`<p>The following fixed study preserves this authored world. Its question and treatment may be narrower than the blueprint hypothesis.</p><dl class="key-value"><dt>Fixed study question</dt><dd>${esc(d.research_question)}</dd><dt>Randomization unit</dt><dd>${esc(d.experimental_unit)}</dd><dt>Primary outcome</dt><dd>${esc(d.primary_outcome)}</dd><dt>Primary contrast</dt><dd>${esc(d.primary_contrast)}</dd><dt>Conditions</dt><dd>${d.conditions.map(esc).join(' · ')}</dd><dt>Study units</dt><dd>${d.maximum_units}</dd><dt>Maximum subject decision requests</dt><dd>${d.maximum_subject_calls}</dd><dt>Maximum hosted subject calls</dt><dd>${d.maximum_hosted_subject_calls}</dd><dt>Subject backend</dt><dd>${esc(d.subject_backend.harness)} · ${esc(d.subject_backend.model)}</dd></dl><p>Two independent runs per condition; seed 4491. Registration launches no subjects.</p>${checks}${action}`;
    }
    return `<section class="panel"><div class="panel-heading"><h2>${p.status==='compatible' ? 'Register a compatible study' : 'This registered design is unavailable'}</h2></div><div class="panel-body"><p class="mono">${esc(p.blueprint_ref.id)} · version ${p.blueprint_ref.version}</p><details class="commentary-detail"><summary>Exact blueprint hash and registration settings</summary><p class="hash">${esc(p.blueprint_ref.hash)}</p><p>Runs per condition: ${p.registration_plan.trials_per_cell} · seed ${p.registration_plan.seed} · subjects ${p.registration_plan.live ? 'Responses' : 'scripted'}</p></details>${boundary}${body}${limits}</div></section>`;
  }
  root.BlueprintRegistrationPreview={expectation,validate,launchArgs,render};
})(typeof window==='object' ? window : globalThis);
