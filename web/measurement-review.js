'use strict';

// Pure rendering only. Exact-source authentication and compare-and-swap belong to the host.
(function (root) {
  const MODES = ['manual_operator', 'agent_assisted', 'synthetic_fixture'];
  const LABELS = ['yes', 'no', 'uncertain'];
  const HASH = /^[a-f0-9]{64}$/;
  const IDENTITY = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$/;
  const limits = Object.freeze({items:32, population:10000, content:2000, context:2,
    judgments:256, reason:1000, reviewer:80, question:4000, definition:2000, exclusions:16});
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const obj = x => x !== null && typeof x === 'object' && !Array.isArray(x);
  const characters = s => Array.from(s).length; // Producer character counts use Unicode code points.
  const text = (x,max,empty=false) => typeof x==='string' && x.length<=max*2 && characters(x)<=max && (empty || x.trim().length>0);
  const integer = (x,min=0,max=Number.MAX_SAFE_INTEGER) => Number.isSafeInteger(x) && x>=min && x<=max;
  const refValid = r => obj(r) && Object.keys(r).sort().join(',')==='hash,id,version' && text(r.id,200) && IDENTITY.test(r.id) && integer(r.version,1,1000000000) && HASH.test(r.hash);
  const sameRef = (a,b) => refValid(a) && refValid(b) && a.id===b.id && a.version===b.version && a.hash===b.hash;
  const count = n => integer(n) ? String(n) : 'Unknown';
  const fraction = n => typeof n==='number' && Number.isFinite(n) && n>=0 && n<=1 ? `${(n*100).toFixed(1)}%` : 'Unknown';
  const panel = (title,subtitle,body) => `<section class="panel"><div class="panel-heading"><div><h2>${esc(title)}</h2><p>${esc(subtitle)}</p></div></div><div class="panel-body">${body}</div></section>`;
  const refHTML = r => `<span class="mono">${esc(r.id)} · v${r.version}</span><br><span class="hash">${esc(r.hash)}</span>`;
  const ATTESTATION_KEYS=['cheap_operator_check_performed','saved_predictions_match_current_operator','prediction_attestation','historical_execution_attested'];
  function operatorDeclarationValid(i) {
    if(!ATTESTATION_KEYS.some(k=>Object.hasOwn(i,k)))return true; // Older packet: no operator-attestation inference.
    if(typeof i.cheap_operator_check_performed!=='boolean' || i.historical_execution_attested!==false)return false;
    if(i.detector_id===null)return i.cheap_operator_check_performed===false && i.saved_predictions_match_current_operator===null && i.prediction_attestation==='not_applicable_no_instrument';
    return i.cheap_operator_check_performed ? i.current_code_matches===true && i.saved_predictions_match_current_operator===true && i.prediction_attestation==='matches_current_pinned_regex' :
      i.saved_predictions_match_current_operator===null && i.prediction_attestation==='historical_saved_predictions_unverified';
  }

  function sourceValid(s) {
    return obj(s) && text(s.id,200) && IDENTITY.test(s.id) && (s.timestamp===null || text(s.timestamp,128)) &&
      (s.room_id===null || text(s.room_id,200)) && (s.agent_name===null || text(s.agent_name,1000)) &&
      text(s.speaker_type,40) && obj(s.source) && text(s.source.file,1024) &&
      (!Object.hasOwn(s.source,'table') || text(s.source.table,100)) && integer(s.source.line,1,1000000000000) && HASH.test(s.source_sha256) && HASH.test(s.source_record_sha256) &&
      HASH.test(s.declared_message_content_hash) && HASH.test(s.full_content_utf8_sha256) &&
      text(s.content,limits.content,true) && integer(s.content_characters,0,256*1024) &&
      typeof s.content_truncated==='boolean' && s.content_characters>=characters(s.content) &&
      s.content_truncated===(s.content_characters>characters(s.content));
  }
  function judgmentValid(j,id) {
    return obj(j) && integer(j.sequence,1,limits.judgments) && j.message_id===id &&
      LABELS.includes(j.label) && MODES.includes(j.reviewer_mode) && text(j.reason,limits.reason) &&
      text(j.reviewer_id,limits.reviewer) && IDENTITY.test(j.reviewer_id) && text(j.recorded_at,128) && typeof j.predictions_visible==='boolean';
  }
  function predictionValid(p) {
    if(p===null)return true;
    if(!obj(p) || typeof p.available!=='boolean')return false;
    if(!p.available)return p.value===null && p.label===null;
    return typeof p.value==='boolean' && p.label===(p.value ? 'yes' : 'no') && Array.isArray(p.spans) &&
      p.spans.length<=128 && p.spans.every(s=>obj(s) && integer(s.start) && integer(s.end) && s.end>s.start && text(s.text,2000));
  }
  function validatePacket(p) {
    const errors=[];
    if(!obj(p) || p.packet_version!=='measurement-review-packet-v1')return {valid:false,errors:['Unsupported review packet.']};
    for(const key of ['sample_ref','review_ref','dataset_ref'])if(!refValid(p[key]))errors.push(`Invalid exact ${key}.`);
    const c=p.construct,d=p.design;
    if(!obj(c) || !text(c.question,limits.question) || !text(c.positive_definition,limits.definition) ||
      !text(c.negative_definition,limits.definition) || !Array.isArray(c.exclusions) || c.exclusions.length>limits.exclusions ||
      !c.exclusions.every(s=>text(s,500)))errors.push('Invalid frozen construct.');
    if(!obj(d) || !integer(d.population_size,1,limits.population) || !integer(d.sample_size,1,limits.items) ||
      d.sample_size>d.population_size || !integer(d.seed) || !text(d.sampling,256) || !HASH.test(d.population_ids_sha256) ||
      typeof d.inclusion_probability!=='number' || !Number.isFinite(d.inclusion_probability) ||
      Math.abs(d.inclusion_probability-d.sample_size/d.population_size)>1e-12)errors.push('Invalid bounded sample design.');
    if(!obj(p.instrument) || !(p.instrument.detector_id===null || text(p.instrument.detector_id,128)) ||
      (p.instrument.detector_id===null ? p.instrument.predictions_scope!=='unavailable_no_instrument' || p.instrument.current_code_matches!==null ||
        p.instrument.detector_version!==null || p.instrument.discovery_sha256!==null :
        p.instrument.predictions_scope!=='frozen_historical_regex' || typeof p.instrument.current_code_matches!=='boolean' ||
        !text(p.instrument.detector_version,256) || !HASH.test(p.instrument.discovery_sha256)) || !operatorDeclarationValid(p.instrument))errors.push('Invalid frozen instrument declaration.');
    if(typeof p.predictions_included!=='boolean' || p.blinding_authenticated!==false || p.model_calls!==0 || p.calibration_established!==false ||
      !Array.isArray(p.labels) || p.labels.join(',')!==LABELS.join(',') ||
      !Array.isArray(p.reviewer_modes) || p.reviewer_modes.join(',')!==MODES.join(','))errors.push('Invalid scope or prediction declaration.');
    const seen=new Set(),sequences=new Map();
    if(!Array.isArray(p.items) || p.items.length>limits.items || p.items.length!==d?.sample_size)errors.push('Invalid sample rows.');
    else for(const item of p.items) {
      if(!obj(item) || !text(item.message_id,200) || seen.has(item.message_id)) {errors.push('Duplicate or invalid message identity.');continue;}
      seen.add(item.message_id);
      if(!sourceValid(item.source_record) || item.source_record.id!==item.message_id)errors.push('Invalid exact source row.');
      if(!obj(item.context) || !['before','after'].every(k=>Array.isArray(item.context[k]) && item.context[k].length<=limits.context && item.context[k].every(sourceValid)))errors.push('Invalid bounded context.');
      else {
        const contextIds=new Set();
        for(const source of [...item.context.before,...item.context.after]) {
          if(contextIds.has(source.id) || source.id===item.message_id || source.room_id!==item.source_record?.room_id)errors.push('Context identity/room mismatch.');
          contextIds.add(source.id);
        }
      }
      if(!predictionValid(item.prediction) || !p.predictions_included && item.prediction!==null ||
        p.instrument?.detector_id===null && item.prediction?.available===true)errors.push('Invalid prediction declaration.');
      if(!Array.isArray(item.prior_judgments) || item.prior_judgments.length>limits.judgments ||
        item.current_judgment!==null && !judgmentValid(item.current_judgment,item.message_id) ||
        !item.prior_judgments?.every(j=>judgmentValid(j,item.message_id)))errors.push('Invalid declared judgment.');
      else {
        if(item.prior_judgments.length && (!item.current_judgment || item.prior_judgments.some(j=>j.sequence>=item.current_judgment.sequence)))errors.push('Current declaration is not the latest retained sequence.');
        for(const j of [...item.prior_judgments,...(item.current_judgment ? [item.current_judgment] : [])]) {
          if(sequences.has(j.sequence))errors.push('Duplicate judgment sequence.');
          sequences.set(j.sequence,JSON.stringify(j));
        }
      }
    }
    if(sequences.size>limits.judgments)errors.push('Judgment bound exceeded.');
    return {valid:errors.length===0,errors:[...new Set(errors)]};
  }

  function derivedTotals(packet) {
    const labels={yes:0,no:0,uncertain:0,missing:0};
    const modes=Object.fromEntries(MODES.map(m=>[m,{yes:0,no:0,uncertain:0}]));
    for(const item of packet.items) {
      const j=item.current_judgment;
      if(j){labels[j.label]++;modes[j.reviewer_mode][j.label]++;}else labels.missing++;
    }
    return {labels,modes};
  }
  function validateReport(packet,r) {
    if(!validatePacket(packet).valid)return {valid:false,reason:'Invalid packet: comparison withheld.'};
    if(!obj(r) || r.report_version!=='measurement-review-report-v1')return {valid:false,reason:'No current review report.'};
    if(!['sample_ref','review_ref','dataset_ref'].every(k=>sameRef(packet[k],r[k])))return {valid:false,reason:'Stale or mismatched exact report: metrics withheld.'};
    if(r.calibration_established!==false || r.model_calls!==0)return {valid:false,reason:'Unsupported calibration or call declaration: metrics withheld.'};
    if(!obj(r.instrument) || !['detector_id','detector_version','discovery_sha256','predictions_scope','current_code_matches',...ATTESTATION_KEYS].every(k=>r.instrument[k]===packet.instrument[k]))return {valid:false,reason:'Instrument identity mismatch: metrics withheld.'};
    const t=r.totals,derived=derivedTotals(packet),labels=r.current_label_counts;
    if(!obj(t) || !['sample_size','known_labels','uncertain_labels','missing_labels','available_predictions','unavailable_predictions','compared_messages'].every(k=>integer(t[k],0,limits.items)) ||
      t.sample_size!==packet.items.length || t.known_labels+t.uncertain_labels+t.missing_labels!==t.sample_size ||
      t.available_predictions+t.unavailable_predictions!==t.sample_size || t.compared_messages>Math.min(t.known_labels,t.available_predictions) ||
      !obj(labels) || !['yes','no','uncertain','missing'].every(k=>labels[k]===derived.labels[k]) ||
      t.known_labels!==labels.yes+labels.no || t.uncertain_labels!==labels.uncertain || t.missing_labels!==labels.missing ||
      !obj(r.current_labels_by_mode) || !MODES.every(m=>obj(r.current_labels_by_mode[m]) && LABELS.every(k=>r.current_labels_by_mode[m][k]===derived.modes[m][k])))return {valid:false,reason:'Inconsistent label totals: metrics withheld.'};
    if(packet.instrument.detector_id===null && (t.available_predictions!==0 || t.compared_messages!==0))return {valid:false,reason:'No-instrument report conflict: metrics withheld.'};
    const declarations=new Map(),current={visible:0,hidden:0},all={visible:0,hidden:0};
    for(const item of packet.items) {
      if(item.current_judgment)current[item.current_judgment.predictions_visible ? 'visible':'hidden']++;
      for(const j of [...item.prior_judgments,...(item.current_judgment ? [item.current_judgment]:[])])declarations.set(j.sequence,j);
    }
    for(const j of declarations.values())all[j.predictions_visible ? 'visible':'hidden']++;
    if(!obj(r.prediction_visibility) || !['visible','hidden'].every(k=>r.prediction_visibility.current_declarations?.[k]===current[k] &&
      r.prediction_visibility.all_declarations?.[k]===all[k]))return {valid:false,reason:'Declared prediction-visibility totals mismatch: metrics withheld.'};
    if(packet.predictions_included) {
      let available=0,compared=0;
      const expected={true_positive:0,false_positive:0,false_negative:0,true_negative:0};
      for(const item of packet.items) {
        if(item.prediction?.available!==true)continue;
        available++;
        if(!['yes','no'].includes(item.current_judgment?.label))continue;
        compared++;
        const yes=item.current_judgment.label==='yes',pred=item.prediction.value;
        expected[yes ? (pred ? 'true_positive':'false_negative') : (pred ? 'false_positive':'true_negative')]++;
      }
      if(t.available_predictions!==available || t.compared_messages!==compared ||
        compared>0 && !Object.keys(expected).every(k=>r.metrics?.confusion?.[k]===expected[k]))return {valid:false,reason:'Prediction/reference subset mismatch: metrics withheld.'};
    }
    const m=r.metrics;
    if(!obj(m) || typeof m.available!=='boolean')return {valid:false,reason:'Invalid metrics declaration: metrics withheld.'};
    if(!m.available) {
      if(m.confusion!==null || m.agreement!==null || m.precision!==null || m.recall!==null || t.compared_messages!==0)return {valid:false,reason:'Unavailable metrics must remain unknown.'};
    } else {
      const f=m.confusion,a=m.agreement;
      if(!obj(f) || Object.keys(f).sort().join(',')!=='false_negative,false_positive,true_negative,true_positive' || !['true_positive','false_positive','false_negative','true_negative'].every(k=>integer(f[k],0,limits.items)) ||
        !obj(a) || !integer(a.numerator,0,limits.items) || !integer(a.denominator,1,limits.items) ||
        a.denominator!==t.compared_messages || Object.values(f).reduce((x,y)=>x+y,0)!==a.denominator ||
        a.numerator!==f.true_positive+f.true_negative || typeof a.fraction!=='number' || !Number.isFinite(a.fraction) ||
        Math.abs(a.fraction-a.numerator/a.denominator)>1e-12)return {valid:false,reason:'Invalid comparison denominator: metrics withheld.'};
      for(const [key,num,den] of [['precision',f.true_positive,f.true_positive+f.false_positive],['recall',f.true_positive,f.true_positive+f.false_negative]]) {
        if(den===0 ? m[key]!==null : typeof m[key]!=='number' || !Number.isFinite(m[key]) || Math.abs(m[key]-num/den)>1e-12)return {valid:false,reason:'Invalid undefined metric: metrics withheld.'};
      }
    }
    return {valid:true,reason:null};
  }
  function historyRows(packet) {
    return MODES.map(mode=>{
      let declarations=0,messages=0,disagreements=0,visible=0,hidden=0;
      for(const item of packet.items) {
        const unique=new Map(item.prior_judgments.map(j=>[j.sequence,j]));
        const prior=[...unique.values()].filter(j=>j.reviewer_mode===mode && j.sequence!==item.current_judgment?.sequence);
        declarations+=prior.length;visible+=prior.filter(j=>j.predictions_visible).length;hidden+=prior.filter(j=>!j.predictions_visible).length;if(prior.length)messages++;
        if(item.current_judgment && prior.some(j=>j.label!==item.current_judgment.label))disagreements++;
      }
      return `<tr><td>${esc(mode)}</td><td>${declarations}</td><td>${messages}</td><td>${disagreements}</td><td>${visible} / ${hidden}</td></tr>`;
    }).join('');
  }
  function sourceHTML(s,title) {
    return `<div class="detail-section"><h3>${esc(title)}</h3><p class="evidence-meta">${esc(s.id)} · ${esc(s.timestamp ?? 'Time unknown')} · ${esc(s.agent_name ?? 'Name unknown')} · ${esc(s.speaker_type)}<br>${esc(s.source.table ?? 'Table unknown')} · line ${s.source.line} · ${esc(s.source.file)}</p><pre class="message-full">${esc(s.content)}</pre><p class="field-help">${s.content_truncated ? `Truncated excerpt: ${characters(s.content)} of ${s.content_characters} declared characters.` : `Full retained text: ${s.content_characters} declared characters.`} Source-coordinate SHA256: <span class="hash">${esc(s.source_sha256)}</span><br>Normalized-record SHA256: <span class="hash">${esc(s.source_record_sha256)}</span><br>Declared message content hash: <span class="hash">${esc(s.declared_message_content_hash)}</span><br>Full-text UTF-8 SHA256: <span class="hash">${esc(s.full_content_utf8_sha256)}</span></p></div>`;
  }
  function draftValid(d,item) {
    if(!obj(d) || d.message_id!==item.message_id)return null;
    return {label:LABELS.includes(d.label) ? d.label : '',reason:text(d.reason,limits.reason,true) ? d.reason : '',
      reviewer_id:text(d.reviewer_id,limits.reviewer,true) ? d.reviewer_id : '',reviewer_mode:MODES.includes(d.reviewer_mode) ? d.reviewer_mode : ''};
  }
  function render(packet,report,options={}) {
    const checked=validatePacket(packet);
    if(!checked.valid)return panel('Measurement review unavailable','No source rows were silently omitted.',`<div class="note orange">${checked.errors.map(esc).join(' ')}</div><p>Save is blocked. Retrieve a bounded, exact review packet.</p>`);
    if(!obj(options) || options.selectedId!=null && !packet.items.some(x=>x.message_id===options.selectedId))return panel('Selected source unavailable','The requested message is absent from this exact sample.','<p>Save is blocked. Select a retained sample row.</p>');
    if(Object.hasOwn(options,'expected') && (!obj(options.expected) || !sameRef(packet.sample_ref,options.expected.sample_ref) ||
      !sameRef(packet.review_ref,options.expected.review_ref) || Object.hasOwn(options.expected,'dataset_ref') && !sameRef(packet.dataset_ref,options.expected.dataset_ref)))return panel('Expected source mismatch','The loaded packet differs from the exact requested source.','<p>Save is blocked. Reload the expected sample and review snapshot.</p>');
    const item=packet.items.find(x=>x.message_id===options.selectedId) || packet.items[0];
    const activeDraft=draftValid(options.draft,item),j=activeDraft || item.current_judgment || {label:'',reason:'',reviewer_id:'',reviewer_mode:''};
    const reportCheck=validateReport(packet,report),totals=derivedTotals(packet);
    const show=options.showPredictions===true && packet.predictions_included===true;
    const saving=options.saving===true || options.saving==='unknown';
    const saveLabel=options.saving==='unknown' ? 'Save status unknown · inspect Research audit' : options.saving===true ? 'Declaration queued · saving' : 'Save exact declaration';
    const identities=`<dl class="key-value"><dt>Sample</dt><dd>${refHTML(packet.sample_ref)}</dd><dt>Review snapshot</dt><dd>${refHTML(packet.review_ref)}</dd><dt>Dataset</dt><dd>${refHTML(packet.dataset_ref)}</dd><dt>N / k / k-over-N</dt><dd>N=${packet.design.population_size} · k=${packet.design.sample_size} · k/N=${packet.design.sample_size}/${packet.design.population_size} = ${packet.design.sample_size/packet.design.population_size}</dd><dt>Selection</dt><dd>${esc(packet.design.sampling)} · seed ${packet.design.seed}</dd><dt>Population membership pin</dt><dd class="hash">${esc(packet.design.population_ids_sha256)}</dd></dl>`;
    const construct=`<h3>${esc(packet.construct.question)}</h3><dl class="key-value"><dt>Yes</dt><dd>${esc(packet.construct.positive_definition)}</dd><dt>No</dt><dd>${esc(packet.construct.negative_definition)}</dd></dl><ul class="tight-list">${packet.construct.exclusions.map(s=>`<li>${esc(s)}</li>`).join('')}</ul><p>One declaration labels one sampled message using bounded same-room context. It is not an episode label or a population behavior estimate. N is the retained dataset-message frame, not the full AI Village population.</p><p class="field-help">Source pins identify retained registry records. This renderer does not authenticate their bytes or reread raw source files.</p>`;
    const sidebar=packet.items.map(row=>`<button class="object-row ${row.message_id===item.message_id ? 'selected' : ''}" type="button" data-review-message="${esc(row.message_id)}"><span class="row-main"><strong class="mono">${esc(row.message_id)}</strong><small>${esc(row.source_record.agent_name ?? row.source_record.speaker_type)} · ${esc(row.current_judgment?.label ?? 'Missing')} · ${esc(row.current_judgment?.reviewer_mode ?? 'No declaration')}</small></span></button>`).join('');
    let metrics=`<p>${esc(reportCheck.reason ?? 'Comparison metrics hidden until predictions are requested.')}</p>`;
    if(reportCheck.valid) {
      const t=report.totals;
      metrics=`<dl class="key-value"><dt>Known yes/no</dt><dd>${count(t.known_labels)}</dd><dt>Uncertain / missing</dt><dd>${count(t.uncertain_labels)} / ${count(t.missing_labels)}</dd><dt>Available / unavailable predictions</dt><dd>${count(t.available_predictions)} / ${count(t.unavailable_predictions)}</dd></dl>`;
      metrics+=`<p>Current declarations with predictions declared visible / hidden: ${count(report.prediction_visibility.current_declarations.visible)} / ${count(report.prediction_visibility.current_declarations.hidden)}. This records declared UI exposure, not authenticated blinding.</p>`;
      if(show) {
        const m=report.metrics;
        metrics+=`<h3>Agreement against declared reference</h3><p>Known labels plus available-prediction subset only: ${m.available ? `${m.agreement.numerator} / ${m.agreement.denominator} · ${fraction(m.agreement.fraction)}` : 'Unknown'}. Uncertain, missing and unavailable predictions are excluded, not scored as negatives.</p><p>Positive predictive agreement: ${m.available ? fraction(m.precision) : 'Unknown'} · positive reference agreement: ${m.available ? fraction(m.recall) : 'Unknown'}.</p>`;
      } else metrics+='<p>Instrument comparison metrics are hidden until predictions are requested.</p>';
    }
    metrics+='<p class="field-help">The latest accepted declaration is the reference, not a consensus or authenticated human truth. Calibration established: false. No population accuracy, causal finding or behavior/theory promotion follows.</p>';
    const modeRows=MODES.map(m=>`<tr><td>${esc(m)}</td><td>${totals.modes[m].yes}</td><td>${totals.modes[m].no}</td><td>${totals.modes[m].uncertain}</td></tr>`).join('');
    const reportHTML=`<div class="metrics-row"><div class="metric"><span class="metric-value">${totals.labels.yes+totals.labels.no}</span><span class="metric-label">Known yes/no</span></div><div class="metric"><span class="metric-value">${totals.labels.uncertain}</span><span class="metric-label">Uncertain</span></div><div class="metric"><span class="metric-value">${totals.labels.missing}</span><span class="metric-label">Missing</span></div></div>${metrics}<div class="table-wrap"><table><caption>Current declarations by declared mode</caption><thead><tr><th>MODE</th><th>YES</th><th>NO</th><th>UNCERTAIN</th></tr></thead><tbody>${modeRows}</tbody></table></div><div class="table-wrap"><table><caption>Prior declarations; message-level disagreement with current label</caption><thead><tr><th>PRIOR MODE</th><th>DECLARATIONS</th><th>MESSAGES</th><th>DISAGREEING MESSAGES</th><th>DECLARED VISIBLE / HIDDEN</th></tr></thead><tbody>${historyRows(packet)}</tbody></table></div><p class="field-help">Retained history can reuse reviewers/messages. Differences are descriptive, not independent rater agreement or evidence that a declaration is wrong.</p>`;
    const prediction=item.prediction;
    const predictionHTML=show ? `<div class="note">Frozen historical regex prediction: ${prediction?.available===true ? esc(prediction.label) : 'Unknown'}. This does not resolve semantic intent.</div><p class="field-help">Instrument: ${esc(packet.instrument.detector_id ?? 'None')} · version ${esc(packet.instrument.detector_version ?? 'Unknown')} · current code match ${packet.instrument.current_code_matches===null ? 'Unknown' : packet.instrument.current_code_matches ? 'declared yes':'declared no'}. Declared prediction attestation: ${esc(packet.instrument.prediction_attestation ?? 'Unknown')}; historical execution is not attested. A current operator check does not authenticate raw source bytes or semantic labels. Coordinates are declared full-text offsets; an excerpt need not contain every span.</p>${prediction?.available ? `<ul class="tight-list">${prediction.spans.map(s=>`<li>${s.start}–${s.end}: <code>${esc(s.text)}</code></li>`).join('')}</ul>` : ''}` : '<p>Predictions are hidden in this view. This UI choice does not authenticate blinding; previous access is unknown.</p>';
    const form=`<form data-review-form="${esc(item.message_id)}"><div class="form-grid"><label class="field"><span>Declaration</span><select data-review-field="label" required><option value="">Choose a label</option>${LABELS.map(v=>`<option value="${v}" ${j.label===v ? 'selected' : ''}>${v}</option>`).join('')}</select></label><label class="field"><span>Declared reviewer mode</span><select data-review-field="reviewer_mode" required><option value="">Choose a mode</option>${MODES.map(v=>`<option value="${v}" ${j.reviewer_mode===v ? 'selected' : ''}>${v}</option>`).join('')}</select></label><label class="field full"><span>Reviewer ID · declaration only</span><input data-review-field="reviewer_id" maxlength="${limits.reviewer}" value="${esc(j.reviewer_id)}" required></label><label class="field full"><span>Reason, including ambiguity</span><textarea data-review-field="reason" maxlength="${limits.reason}" required>${esc(j.reason)}</textarea></label></div><p class="field-help">manual_operator, agent_assisted and synthetic_fixture are declared provenance modes. They do not authenticate a person, independence or label quality. Save makes zero model calls.</p><button class="button primary" type="button" data-review-save="${esc(item.message_id)}" data-sample-id="${esc(packet.sample_ref.id)}" data-sample-version="${packet.sample_ref.version}" data-sample-hash="${esc(packet.sample_ref.hash)}" data-review-id="${esc(packet.review_ref.id)}" data-review-version="${packet.review_ref.version}" data-review-hash="${esc(packet.review_ref.hash)}" data-predictions-visible="${show}" ${saving ? 'disabled aria-disabled="true"' : ''}>${saveLabel}</button></form>`;
    const prior=item.prior_judgments.length ? `<details class="commentary-detail"><summary>Prior declarations for this message</summary><div class="table-wrap"><table><thead><tr><th>SEQUENCE</th><th>REVIEWER / DECLARED MODE</th><th>LABEL</th><th>PREDICTIONS DECLARED VISIBLE</th><th>REASON</th></tr></thead><tbody>${item.prior_judgments.map(p=>`<tr><td>${p.sequence}</td><td>${esc(p.reviewer_id)} / ${esc(p.reviewer_mode)}</td><td>${esc(p.label)}</td><td>${p.predictions_visible ? 'yes':'no'}</td><td>${esc(p.reason)}</td></tr>`).join('')}</tbody></table></div></details>` : '<p class="field-help">No earlier declarations retained for this message.</p>';
    const context=[...item.context.before.map(s=>sourceHTML(s,'Before in bounded source context')),...item.context.after.map(s=>sourceHTML(s,'After in bounded source context'))].join('') || '<p>No context neighbors retained.</p>';
    const main=sourceHTML(item.source_record,'Sampled source message')+`<div class="action-row"><button class="button small" type="button" data-review-predictions="${show ? 'hide' : 'show'}">${show ? 'Hide' : 'Show'} frozen predictions</button></div>`+predictionHTML+form+prior+`<details class="raw-detail"><summary>Bounded same-room context · at most two before and two after</summary>${context}</details>`;
    return `<div class="measurement-review">${panel('Frozen measurement construct','Exact sample and source selection precede labels.',construct+identities)}<div class="grid-two section-gap">${panel('Sample rows','Every retained sampled message remains selectable.',`<div class="library-list">${sidebar}</div>`)}${panel('Declare a message-level judgment','Missing and uncertain remain separate.',main)}</div><div class="section-gap">${panel('Review coverage and instrument comparison','Agreement uses declared references; calibration remains unestablished.',reportHTML)}</div></div>`;
  }
  root.MeasurementReview=Object.freeze({render,validatePacket,validateReport,sameRef,limits});
})(globalThis);
