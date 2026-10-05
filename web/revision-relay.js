'use strict';

// Optional study UI. The server's exact-version host remains the authority.
function relayProtocolGuard(record) {
  const p=record?.payload?.protocol;
  if(record?.kind!=='revision_relay_protocol' || !Number.isInteger(record.version) || record.version<1 ||
     typeof record.hash!=='string' || !/^[a-f0-9]{64}$/.test(record.hash) ||
     !p || p.study_kind!=='paired_revision_relay_factorial' ||
     !Number.isInteger(p.design?.blocks) || p.design.blocks<1 || p.design.blocks>64 ||
     p.design.maximum_teams!==p.design.blocks*4 || p.design.maximum_subject_calls!==p.design.blocks*16 ||
     !['scripted','responses'].includes(p.subject_backend?.harness)) {
    throw new Error('Choose a valid exact revision-relay registration.');
  }
  return p;
}
function relayWasLaunched(record) {
  const sameRef=ref=>ref?.id===record.id && ref.version===record.version && ref.hash===record.hash;
  return (app.state?.jobs || []).some(j=>sameRef(j.payload?.protocol_ref) ||
    ['queued','running'].includes(j.status) && j.payload?.action==='experiment_revision_relay' &&
    j.payload.args?.protocol_id===record.id && j.payload.args.protocol_version===record.version) ||
    all('revision_relay_experiment').some(o=>sameRef(o.summary?.protocol_ref) || sameRef(o.payload?.protocol_ref));
}
function relayExecutionGuard(record) {
  const p=relayProtocolGuard(record),live=p.subject_backend.harness==='responses';
  if(!(app.state?.supported_actions || []).includes('experiment_revision_relay'))throw new Error('Relay execution is unavailable on this server.');
  if(relayWasLaunched(record))throw new Error('This exact study was already launched. Inspect its retained result; register a new study for another execution.');
  if(live!==app.live || live && p.subject_backend.model!==app.state?.model)throw new Error('Match the execution mode and model to the frozen registration.');
  if(live) {
    const calls=app.state?.usage?.calls,cap=app.state?.max_calls;
    if(!Number.isInteger(calls) || calls<0 || !Number.isInteger(cap) || cap<0 ||
       calls+p.design.maximum_subject_calls>cap)throw new Error('The full registered subject grid exceeds the remaining call cap.');
  }
  return {protocol_id:record.id,protocol_version:record.version,live};
}
function exactRelayProof(result,proof) {
  const p=proof?.payload,r=p?.result_ref;
  return proof?.kind==='verification' && p?.result_kind==='revision_relay_experiment' &&
    p.passed===true && p.model_calls===0 && p.report_status==='complete' &&
    p.complete_execution===true && p.quantitative_available===true && p.partial_trace_consistent===false &&
    result?.payload?.status==='complete' && result.payload.raw_report?.status==='complete' &&
    r?.id===result?.id && r.version===result.version && r.hash===result.hash &&
    Array.isArray(p.checks) && p.checks.length>0 && p.checks.every(c=>c.passed===true);
}
function relayAnalysisRenderable(a) {
  const i=a?.interval,s=i?.assumptions;
  if(!Number.isFinite(a?.mean_interaction) || Math.abs(a.mean_interaction)>2 ||
     a.p_value!==null || a.interaction_randomization_test!==null ||
     typeof i?.available!=='boolean' || i.alpha!==0.05 ||
     i.method!=='conditional_independent_block_Hoeffding' || i.assumptions_attested!==false ||
     typeof s?.independent_blocks_declared!=='boolean' || typeof s.stable_subject_backend_declared!=='boolean' ||
     i.available!==(s.independent_blocks_declared && s.stable_subject_backend_declared))return false;
  if(!i.available)return i.bounds===null;
  return Array.isArray(i.bounds) && i.bounds.length===2 && i.bounds.every(x=>typeof x==='number' && Number.isFinite(x) && x>=-2 && x<=2) &&
    i.bounds[0]<=a.mean_interaction && a.mean_interaction<=i.bounds[1];
}
function relayResultPanel(record,proof) {
  const r=record.payload,report=r.raw_report,a=r.analysis,checked=exactRelayProof(record,proof);
  const rows=(report?.runs || []).map(run=>`<tr><td><button class="button-link mono" data-relay-run="${esc(run.run_id)}" data-relay-result="${esc(record.id)}" data-relay-version="${esc(String(record.version))}">${esc(run.run_id)} ↗</button></td><td>${esc(run.block_id)}</td><td>${esc(human(run.timing))}</td><td>${esc(human(run.bypass))}</td><td>${esc(run.status)}</td><td>${run.outcomes?.C_final_correct===0 || run.outcomes?.C_final_correct===1 ? number(run.outcomes.C_final_correct) : 'Unknown'}</td><td>${number(run.counts?.subject_call_attempts)}</td></tr>`).join('');
  let quantitative='<p>Quantitative replay is unavailable. Recorded grid and raw analysis remain inspectable; no completed effect is authorized.</p>';
  if(checked && relayAnalysisRenderable(a)) {
    const interval=a.interval;
    quantitative=`<div class="effect-card"><span class="caps">TIMING × INFORMATION AVAILABILITY</span><div class="effect-number">${signed(a.mean_interaction)}</div><p>D = (late sham − early sham) − (late informative − early informative). Range −2 to 2.</p><p>${interval?.available===true ? `Conditional bounds: ${signed(interval.bounds?.[0])} to ${signed(interval.bounds?.[1])}. Independence and stable backend are declared assumptions, not verified.` : 'Interval unavailable: required independence and stability assumptions were not both declared.'} No interaction p-value is defined.</p></div>${raw(a,'Replayed block contrasts, cell means and inference declarations')}`;
  }
  return panel('Recorded correction-relay execution','Four fresh teams per seed block; exact final revision and modular total.',`${badge(r.status)} ${badge(r.agent_mode)}<div class="note ${r.agent_mode==='scripted_infrastructure' ? 'orange' : ''}">${r.agent_mode==='scripted_infrastructure' ? 'Scripted infrastructure test. These scores establish no LLM behavioral effect.' : 'Synthetic assigned timing and bypass policies. Historical mechanisms, provider consumption and mediation remain unestablished.'}</div>${checked ? '<div class="note cyan">Fresh exact local replay: passed.</div>' : '<div class="note orange">Completed quantitative replay has not passed for this exact result version.</div>'}${quantitative}<div class="table-wrap"><table><thead><tr><th>RUN TRACE</th><th>BLOCK</th><th>B CORRECTION</th><th>A → C BYPASS</th><th>STATUS</th><th>C FINAL CORRECT</th><th>DECISION ATTEMPTS</th></tr></thead><tbody>${rows || '<tr><td colspan="7">Execution did not materialize a subject grid.</td></tr>'}</tbody></table></div><p class="field-help">Each team has B2 / C3 / B5 / C7 opportunities. Waiting or an invalid final action scores zero; interrupted infrastructure remains unknown. Turns are not independent experimental units.</p><div class="action-row"><button class="button" data-action="audit-revision-relay" data-id="${esc(record.id)}" data-version="${esc(String(record.version))}">Replay exact relay result · zero model calls</button></div>${raw({result_ref:{id:record.id,version:record.version,hash:record.hash},protocol_ref:r.protocol_ref,backend:r.backend,report_status:report?.status,failure:report?.failure,recorded_analysis:checked && relayAnalysisRenderable(a) ? undefined : a,artifact_pins:r.artifact_pins,scope:r.scope},'Exact identities, retained failure and source/archive pins')}`);
}
async function revisionRelayExperiments() {
  const protocolId=selected('revision_relay_protocol'),resultId=selected('revision_relay_experiment');
  const [registration,result]=await Promise.all([protocolId ? object(protocolId,app.relayProtocolVersion) : null,resultId ? object(resultId,app.relayResultVersion) : null]);
  const available=(app.state?.supported_actions || []).includes('design_revision_relay');
  const form=`<form id="revision-relay-design-form"><div class="form-grid"><label class="field"><span>Independent seed blocks</span><input type="number" min="1" max="64" data-field="relayBlocks" value="${esc(app.relayBlocks ?? 2)}" required></label><label class="field"><span>Allocation seed</span><input type="number" min="0" max="9007199254740991" data-field="relaySeed" value="${esc(app.relaySeed ?? 173)}" required></label></div><p>Four teams and sixteen subject decisions per block. The default interval stays unavailable; no unverified independence assumption is enabled here.</p><div class="action-row"><button class="button primary" type="submit" ${available ? '' : 'disabled'}>Freeze ${app.live ? 'live' : 'scripted'} relay protocol</button></div>${executionNote()}</form>`;
  const premise='<p>Source A creates an original and a correction. B may relay a canonical record to C. C combines it with a private residue, then explicitly commits its final answer.</p><p>Cross early / late correction availability to B with an informative / sham direct bypass to C. All four teams share the same exogenous source values and fixed schedule within a block, with fresh subject requests and randomized cell order.</p><p>The estimand compares assigned availability packages. Visible inventory does not prove reading or belief; it does not identify relay mediation. This study adds no private context note.</p>';
  let registered='';
  if(registration) {
    let p=null,blocked='';try {p=relayProtocolGuard(registration);relayExecutionGuard(registration);}catch(e){blocked=e.message;}
    registered=`<div class="section-gap">${selector('revision_relay_protocol')}${panel('Frozen relay study','Exact version, full grid, backend and oracle precede the first decision.',`${p ? `<dl class="key-value"><dt>Blocks / assigned teams</dt><dd>${number(p.design.blocks)} / ${number(p.design.maximum_teams)}</dd><dt>Maximum subject decisions</dt><dd>${number(p.design.maximum_subject_calls)}</dd><dt>Frozen backend</dt><dd>${esc(p.subject_backend.model)}</dd><dt>Registration version</dt><dd>${number(registration.version)}</dd></dl>` : ''}${blocked ? `<p>${esc(blocked)}</p>` : ''}<button class="button primary" data-action="experiment-revision-relay" data-id="${esc(registration.id)}" data-version="${esc(String(registration.version))}" ${blocked ? 'disabled' : ''}>Run this exact relay study</button>${raw(p || registration.payload,'Frozen world, assignment, request and analysis contract')}`)}</div>`;
  }
  let executed='';
  if(result) {
    const proof=await relatedRecord('verification',result.id,result);
    executed=`<div class="section-gap">${selector('revision_relay_experiment')}${relayResultPanel(result,proof)}</div>`;
  }
  return `<div class="grid-equal">${panel('Design a correction-relay study','Separate timing from an alternate information route.',form)}${panel('Revision-capable relay world','A controlled communication test with an independent oracle.',premise)}</div>`+registered+executed;
}
async function showRevisionRelayRun(resultId,version,runId) {
  const record=await object(resultId,version);
  if(record?.kind!=='revision_relay_experiment' || record.id!==resultId || record.version!==version)throw new Error('Select the exact saved relay result version.');
  const run=record.payload.raw_report?.runs?.find(r=>r.run_id===runId);
  if(!run)throw new Error('Run identity is absent from this exact result.');
  document.querySelector('#evidence-dialog .eyebrow').textContent='RECORDED RELAY EXECUTION';
  document.querySelector('#evidence-dialog .dialog-heading h2').textContent='Correction-relay run inspection';
  document.getElementById('dialog-body').innerHTML=`<h2>${esc(runId)}</h2><p>${esc(run.block_id)} · ${esc(run.timing)} / ${esc(run.bypass)} · ${esc(run.status)}</p><p>Request construction and canonical forwarding are local evidence. Provider consumption and mental knowledge remain unknown.</p>${raw(run.exogenous_identity,'Paired exogenous source and schedule')}${raw(run.boundaries,'Exact scoped requests and invocation states')}${raw(run.turns,'Retained actions, dispatches and tool results')}${raw(run.outcomes,'Independent final oracle; null means unresolved execution')}`;
  document.getElementById('evidence-dialog').showModal();
}
