/* Read-only, exact-source episode view. Host owns retrieval and navigation. */
(function (host) {
  'use strict';
  const KINDS = ['dataset', 'discovery', 'selected_audit', 'temporal_audit'];
  const VARIANTS = ['baseline_exact', 'explicit_short_expanded_exact', 'unicode_baseline', 'unicode_expanded'];
  const REF_KEYS = ['hash', 'id', 'version'];
  const COMPARISON_KEYS = ['comparison_window_id', 'feature', 'id', 'window_id'];
  const UNKNOWN = 'Unknown';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const plain = value => typeof value === 'string' ? value : '';
  const title = value => plain(value).replace(/_/g, ' ');
  const clip = (value, limit=1000) => { const text=plain(value); return text.length>limit ? text.slice(0,limit)+'…' : text; };
  const dict = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const keys = (value, expected) => dict(value) && Object.keys(value).sort().join(',') === expected.slice().sort().join(',');
  const textId = value => typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$/.test(value);
  const refValid = value => keys(value, REF_KEYS) && textId(value.id) && Number.isSafeInteger(value.version) && value.version>0 && typeof value.hash === 'string' && /^[0-9a-f]{64}$/.test(value.hash);
  const sameRef = (a,b) => refValid(a) && refValid(b) && REF_KEYS.every(key => a[key]===b[key]);
  const comparisonValid = value => keys(value,COMPARISON_KEYS) && COMPARISON_KEYS.every(key => textId(value[key])) && value.window_id!==value.comparison_window_id;
  const sameComparison = (a,b) => comparisonValid(a) && comparisonValid(b) && COMPARISON_KEYS.every(key => a[key]===b[key]);
  const sourcesValid = value => keys(value,KINDS) && KINDS.every(key => refValid(value[key]));
  const sameSources = (a,b) => sourcesValid(a) && sourcesValid(b) && KINDS.every(key => sameRef(a[key],b[key]));
  const finite = value => typeof value==='number' && Number.isFinite(value);
  const count = value => Number.isSafeInteger(value) && value>=0 ? String(value) : UNKNOWN;
  const numeric = value => finite(value) ? (value===0 ? '0' : Number(value.toPrecision(6)).toString()) : UNKNOWN;
  const fraction = value => finite(value) && value>=0 && value<=1+1.1e-9 ? numeric(value) : UNKNOWN;
  const list = value => Array.isArray(value) ? value.filter(x=>typeof x==='string').slice(0,8) : [];
  const bullets = value => { const entries=list(value); return entries.length ? '<ul>'+entries.map(x=>'<li>'+esc(clip(x,1600))+'</li>').join('')+'</ul>' : '<p class="soft-text">No entry recorded.</p>'; };
  const table = (labels,rows) => '<div class="table-wrap"><table><thead><tr>'+labels.map(x=>'<th>'+esc(x)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+row.map(x=>'<td>'+esc(x)+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';
  const section = (heading,body) => '<div class="detail-section"><h3>'+esc(heading)+'</h3>'+body+'</div>';
  const folded = (heading,body) => '<details class="raw-detail"><summary>'+esc(heading)+'</summary>'+body+'</details>';
  const note = text => '<div class="note">'+esc(text)+'</div>';
  const unknown = reason => '<p class="soft-text">Unknown — '+esc(clip(reason || 'No source-bound output is available.',800))+'</p>';
  const refHTML = (name,ref) => refValid(ref) ? '<p><strong>'+esc(title(name))+'</strong> <button class="button-link mono" data-open="'+esc(ref.id)+'" data-open-version="'+ref.version+'">'+esc(ref.id)+' · v'+ref.version+' ↗</button><br><span class="hash">'+esc(ref.hash)+'</span></p>' : unknown('Exact '+title(name)+' reference unavailable.');
  function recordedBaseValid(packet) {
    const context=packet.recorded_observations,base=context?.base_context_gates;
    return dict(context) && context.fresh_source_attestation===false && context.raw_or_index_reread===false && context.operator_rerun===false && context.model_calls===0 && context.database_writes===0 && sameSources(context.source_refs,packet.source_refs) && sameComparison(context.registered_comparison,packet.comparison) && keys(context.original_windows,Object.keys(packet.windows || {})) && Object.keys(packet.windows || {}).every(id=>['id','room_id','start','end_exclusive'].every(key=>context.original_windows[id]?.[key]===packet.windows[id][key])) && dict(base) && ['local_registry_body_hashes_verified','current_producer_byte_pins_match','exact_original_comparison_verified'].every(key=>base[key]===true);
  }
  function validate(packet, expected) {
    if (!dict(packet) || packet.workspace_version!=='episode-workspace-v1') return {available:false, reason:'Unsupported or absent episode workspace packet.'};
    if (packet.available!==true) return {available:false,reason:plain(packet.reason) || 'Episode source gates are unavailable.'};
    if (!dict(expected) || !textId(expected.lead_id) || !sameSources(packet.source_refs,expected.source_refs)) return {available:false,reason:'Exact source references do not match the requested episode.'};
    if (!sameComparison(packet.comparison,expected.comparison) || packet.comparison.id!==expected.lead_id || packet.lead?.id!==expected.lead_id || packet.lead?.feature!==packet.comparison.feature) return {available:false,reason:'Original selected lead or comparator does not match the requested episode.'};
    const ids=[packet.comparison.window_id,packet.comparison.comparison_window_id];
    if (!keys(packet.windows,ids) || ids.some(id=>!dict(packet.windows[id]) || packet.windows[id].id!==id || typeof packet.windows[id].room_id!=='string' || typeof packet.windows[id].start!=='string' || typeof packet.windows[id].end_exclusive!=='string')) return {available:false,reason:'Original source window scopes are unavailable or inconsistent.'};
    if (packet.model_calls!==0 || packet.database_writes!==0 || packet.fresh_source_attestation!==false) return {available:false,reason:'This view requires zero-call, read-only recorded evidence with no fresh-source attestation.'};
    if (!recordedBaseValid(packet)) return {available:false,reason:'Recorded-context base gates do not bind the exact sources, original comparison and window scopes.'};
    const requested=Object.prototype.hasOwnProperty.call(expected,'behavior_ref');
    const behavior_available=requested && sameRef(expected.behavior_ref,packet.behavior?.ref) && packet.behavior?.available===true && dict(packet.behavior.payload);
    const behavior_reason=behavior_available ? null : requested ? 'Requested exact behavior pin is unavailable or does not match this episode packet.' : 'No behavior was explicitly requested; unsolicited hypotheses are not displayed.';
    return {available:true,reason:null,behavior_available,behavior_reason};
  }
  function measurement(packet) {
    const rows=[];
    for (const policy of ['native','fixed_pair']) for (const variant of VARIANTS) {
      const value=packet.measurement?.[policy]?.[variant], available=value?.available===true;
      rows.push([policy==='native' ? 'Native window nodes' : 'Fixed nodes within original pair',title(variant),available ? numeric(value.value) : UNKNOWN,available ? numeric(value.comparison_value) : UNKNOWN,available ? numeric(value.difference) : UNKNOWN,available && typeof value.direction==='string' ? title(value.direction) : UNKNOWN,available && typeof value.supported==='boolean' ? (value.supported ? 'Meets descriptive support' : 'Below descriptive support') : UNKNOWN]);
    }
    return section('Same records, different name instruments',table(['NODE POLICY','VARIANT','FOCAL','COMPARATOR','SAVED DELTA','DIRECTION','SUPPORT'],rows)+note('Original saved values and candidate-minus-comparator orientation are shown. Native and fixed-pair universes are separate instruments; variants are not independent replications. No instrument is silently selected as correct.'));
  }
  function temporal(packet) {
    const rows=[];
    for (const id of [packet.comparison.window_id,packet.comparison.comparison_window_id]) for (const variant of VARIANTS) {
      const cell=packet.temporal?.[id]?.variants?.[variant], ok=cell?.available===true;
      rows.push([id===packet.comparison.window_id ? 'Focal' : 'Comparator',title(variant),ok ? count(cell.static?.reachable_pair_count) : UNKNOWN,ok ? count(cell.strict_temporal?.reachable_pair_count) : UNKNOWN,ok ? fraction(cell.static?.maximum_bridge_loss_fraction) : UNKNOWN,ok ? fraction(cell.strict_temporal?.maximum_bridge_loss_fraction) : UNKNOWN,ok ? count(cell.static_only_pair_count) : UNKNOWN]);
    }
    return section('Static references versus strict timestamp order',table(['ORIGINAL WINDOW','VARIANT','STATIC PAIRS','STRICT-TIME PAIRS','STATIC MAX LOSS','STRICT-TIME MAX LOSS','STATIC-ONLY PAIRS'],rows)+note('Saved source direction and strict increasing timestamps stay intact. Reference paths do not establish delivery or influence. Missing or undefined quantities remain unknown; counts are not new calculations in this view.'));
  }
  function recordedEntry(packet,name) {
    const context=packet.recorded_observations, entry=context?.observations?.[name];
    if (!recordedBaseValid(packet)) return {available:false,reason:'Recorded-context base gates do not bind the exact sources, original comparison and window scopes.'};
    const gates=entry?.gates;
    if (entry?.available!==true || !dict(entry.summary) || !refValid(entry.ref) || !refValid(entry.stored_proof_ref) || !dict(gates) || !['local_registry_body_hash_verified','exact_source_parent_binding','current_producer_byte_pins_match','stored_proof_binding_verified','stored_proof_passed'].every(key=>gates[key]===true)) return {available:false,reason:entry?.reason || 'No passing recorded observation in the bounded source-matching scope.'};
    return entry;
  }
  function observationScope(entry) {
    return '<p class="field-help">'+esc(clip(entry.summary?.measurement,900))+'</p>'+refHTML('Recorded observation',entry.ref)+refHTML('Stored replay proof',entry.stored_proof_ref)+note('Local registry/body, current producer bytes and stored-proof binding passed. This view does not reread raw/index bytes, rerun an operator, or perform fresh scientific reauthentication.');
  }
  function actors(packet) {
    const entry=recordedEntry(packet,'actor_events');
    if (!entry.available) return section('Actor/time records',unknown(entry.reason));
    const rows=[packet.comparison.window_id,packet.comparison.comparison_window_id].map((id,index)=>{const r=entry.summary.by_original_window?.[id];return [index===0?'Focal':'Comparator',count(r?.records),...['WAIT','PAUSE','START_USING_COMPUTER','STOP_USING_COMPUTER'].map(key=>count(r?.action_counts?.[key])),count(r?.room_status_counts?.missing),count(r?.room_status_counts?.known)];});
    return section('Actor/time records',observationScope(entry)+table(['ORIGINAL WINDOW','RECORDS','WAIT','PAUSE','START','STOP','MISSING ROOM','KNOWN ROOM'],rows)+note(plain(entry.summary.room_relationship) || 'Event rooms remain missing or observed; no original chat room is assigned.')+ '<p class="field-help">'+esc(clip(entry.summary.clock_scope,900))+' '+esc(clip(entry.summary.interpretation,1400))+'</p>');
  }
  function waits(packet) {
    const entry=recordedEntry(packet,'wait_markers');
    if (!entry.available) return section('Literal words near recorded actions',unknown(entry.reason));
    const rows=[];
    for (const [index,id] of [packet.comparison.window_id,packet.comparison.comparison_window_id].entries()) for (const group of ['marker','nonmarker_control']) for (const horizon of ['30','60','300']) {
      const g=entry.summary.by_original_author_window?.[id]?.[group],h=g?.by_horizon_seconds?.[horizon], statuses=h?.status_counts;
      rows.push([index===0?'Focal':'Comparator',group==='marker'?'Literal markers':'Fixed nonmarker comparisons',horizon+' s',count(h?.messages_with_candidate)+' / '+count(g?.messages),count(statuses?.candidate_observed_boundary_censored ?? (dict(statuses) ? 0 : null)),count(statuses?.no_indexed_candidate_boundary_censored ?? (dict(statuses) ? 0 : null))]);
    }
    return section('Literal words near recorded actions',observationScope(entry)+table(['AUTHOR WINDOW','SAVED GROUP','INCLUSIVE HORIZON','CANDIDATES / MESSAGES','CANDIDATE + CENSORED','NO CANDIDATE + CENSORED'],rows)+'<p class="field-help">'+esc(clip(entry.summary.candidate_scope,1600))+' '+esc(clip(entry.summary.fixed_control_selection,1300))+'</p>'+note(plain(entry.summary.room_relationship))+ '<p class="field-help">'+esc(clip(entry.summary.clock_scope,1000))+' '+esc(clip(entry.summary.interpretation,1500))+'</p>');
  }
  function energy(value,signal=1) {
    if (!finite(value) || value<0) return UNKNOWN;
    return value!==0 && value<=1e-12*Math.max(1,finite(signal)?Math.abs(signal):1) ? '≈ 0' : numeric(value);
  }
  function hodge(packet) {
    const entry=recordedEntry(packet,'edge_algebra');
    if (!entry.available) return section('Static edge-count algebra',unknown(entry.reason));
    const rows=[];
    for (const [index,id] of [packet.comparison.window_id,packet.comparison.comparison_window_id].entries()) for (const variant of VARIANTS) {
      const cell=entry.summary.by_original_window?.[id]?.[variant],e=cell?.energies,signal=e?.signal?.squared_norm;
      rows.push([index===0?'Focal':'Comparator',title(variant),count(cell?.node_count)+' / '+count(cell?.supported_edges)+' / '+count(cell?.balanced_supported_edges),count(cell?.source_reference_events),energy(signal,signal),energy(e?.gradient?.squared_norm,signal),energy(e?.circulation?.squared_norm,signal),fraction(e?.gradient?.fraction_of_signal)+' / '+fraction(e?.circulation?.fraction_of_signal),UNKNOWN+' / '+UNKNOWN]);
    }
    return section('Static edge-count algebra',observationScope(entry)+table(['ORIGINAL WINDOW','VARIANT','NODES / EDGES / BALANCED','REFERENCES','SIGNAL ENERGY','GRADIENT ENERGY','CIRCULATION ENERGY','G / C FRACTIONS','CURL / HARMONIC'],rows)+note(plain(entry.summary.interpretation))+ '<p class="field-help">Display only: nonzero energy ≤ 10⁻¹² × max(1, signal energy) appears as ≈ 0. Original recorded numeric values are unchanged. Fractions are dimensionless, not message proportions. An unspecified face complex leaves curl and harmonic unknown.</p>');
  }
  function evidence(packet,group) {
    const values=Array.isArray(packet.evidence?.[group]) ? packet.evidence[group].slice(0,12) : [];
    if (!values.length) return unknown('No retained source messages in this bounded evidence excerpt.');
    return values.map(message=>'<details class="raw-detail"><summary>'+esc(clip(message.agent_name,100))+' · '+esc(clip(message.timestamp,100))+' · '+esc(clip(message.id,200))+'</summary><p class="mono">Room '+esc(clip(message.room_id,200))+'</p><div class="message-full">'+esc(clip(message.content,12000))+'</div><p class="hash">Original full-content SHA-256 '+esc(clip(message.full_content_sha256,64))+'</p><p class="field-help">'+(message.content_truncated===true?'Content excerpt truncated. Original full content is not fetched by this view.':'Retained bounded content excerpt.')+'</p><pre>'+esc(JSON.stringify(dict(message.source)?message.source:{},null,2).slice(0,6000))+'</pre></details>').join('');
  }
  function draft(question) {
    if (typeof question!=='string' || !question.trim() || question.trim().length>4000) throw new Error('Enter a research question of 1–4000 characters.');
    return {research_question:question.trim(),behavior_id:null};
  }
  function render(packet,expected,question='') {
    const gate=validate(packet,expected);
    if (!gate.available) return '<section class="panel episode-workspace"><div class="panel-heading"><h2>Episode workspace</h2></div><div class="panel-body">'+unknown(gate.reason)+note('No quantitative channel tables are shown when exact episode source gates are unavailable.')+'</div></section>';
    const c=packet.comparison,scopes=[c.window_id,c.comparison_window_id].map((id,index)=>{const w=packet.windows[id];return [index===0?'Focal':'Original comparator',id,w.start,w.end_exclusive,w.room_id];});
    const behavior=packet.behavior, bp=gate.behavior_available?behavior.payload:null;
    const alternatives=bp?.alternative_explanations || packet.lead.alternative_explanations;
    const questions=section('Turn an explanation into a question','<p>The question remains a local draft. Compare at least one rival explanation and specify what observation could contradict the proposed mechanism.</p><label class="field full"><span>Editable experiment question</span><textarea rows="4" maxlength="4000" data-episode-question>'+esc(clip(question,4000))+'</textarea></label><div class="action-row"><button class="button" type="button" data-episode-study-guide>Compare supported study designs →</button><button class="button" type="button" data-episode-transfer-question>Use question in Environment authoring →</button></div>'+note('Copies this question into Environment authoring. The study guide separately retains the unregistered question and its exact origin while you compare existing designs. Select any motivating observation explicitly; neither action registers a protocol or approves mechanism fit. New capabilities remain explicit requirements.'));
    const review=bp?folded('Exact matching behavior and independent critique',refHTML('Behavior',behavior.ref)+'<p><strong>'+esc(clip(bp.name,700))+'</strong> · '+esc(title(bp.status))+'</p><p>'+esc(clip(bp.summary,2000))+'</p><p>'+esc(clip(bp.operational_definition,2000))+'</p><p>Artifact workflow screening: '+esc(title(bp.experiment_fit))+' · '+esc(clip(bp.fit_reason,2000))+'</p><p>'+esc(clip(bp.skeptic?.summary,2000))+'</p>'+bullets(bp.skeptic?.unsupported_claims)):section('Behavior source boundary',unknown(gate.behavior_reason)+(typeof behavior?.reason==='string'?'<p class="field-help">'+esc(clip(behavior.reason,1000))+'</p>':''));
    const channels=section('Inspect the recorded measurement layers',folded('Name sensitivity · native and fixed-pair measurements',measurement(packet))+folded('Strict temporal reference paths',temporal(packet))+folded('Actor/time observations · room remains unassigned',actors(packet))+folded('Literal wait/action candidates and original comparisons',waits(packet))+folded('Static gradient/circulation · time discarded',hodge(packet)));
    return '<section class="panel episode-workspace"><div class="panel-heading"><div><h2>'+esc(clip(packet.lead.title,500) || 'Selected graph episode')+'</h2><p>One original selected lead and its comparator, across distinct recorded instruments.</p></div></div><div class="panel-body"><p>'+esc(clip(packet.lead.description,3000))+'</p><p class="mono">'+esc(c.id)+' · '+esc(title(c.feature))+'</p>'+table(['ROLE','EXACT WINDOW','SAVED UTC START','SAVED UTC END EXCLUSIVE','ORIGINAL CHAT ROOM'],scopes)+note('These windows and contrasts were selected from the same source data. Descriptive differences are not independent replication or causal effects; no candidate, behavior or theory status changes here.')+section('Original saved graph quantities',table(['FEATURE','FOCAL','COMPARATOR','SAVED DELTA','CENSORING'],[[title(c.feature),numeric(packet.lead.value),numeric(packet.lead.comparison_value),numeric(packet.lead.difference),packet.lead.right_censored===true?'Right censored':packet.lead.right_censored===false?'No right-censor flag recorded':UNKNOWN]]))+section('Competing explanations',bullets(alternatives))+section('Predictions that can be wrong',bp ? bullets(bp.falsifiable_predictions) : unknown('No exact matching reviewed behavior was selected. Drafting a question does not create a behavior record.'))+review+questions+channels+folded('Focal source excerpt',evidence(packet,'focal'))+folded('Comparator source excerpt',evidence(packet,'comparator'))+'<details class="raw-detail"><summary>Exact source pins and recorded gate scope</summary>'+KINDS.map(name=>refHTML(name,packet.source_refs[name])).join('')+'<p>'+esc(clip(packet.scope,3000))+'</p><p>Fresh source attestation: false. Model calls: 0. Database writes: 0. Recorded proof and current-code gates are distinct from fresh-source verification.</p><pre>'+esc(JSON.stringify({search_scope:packet.recorded_observations?.search_scope || {},bounds:packet.recorded_observations?.bounds || {},evidence_limits:packet.evidence?.limits || {}},null,2).slice(0,8000))+'</pre></details></div></section>';
  }
  host.EpisodeWorkspace=Object.freeze({validate,render,draft});
})(globalThis);
