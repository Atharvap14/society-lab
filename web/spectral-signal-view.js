'use strict';

// Presentation of saved graph-signal summaries only. No eigen-decomposition,
// source authentication, fetch, listeners, model calls or input mutation.
(() => {
  const LIMITS=Object.freeze({nodes:128,signals:32,positiveIds:20000,denominator:1000000});
  const EPS=1e-8;
  const object=x=>x!==null && typeof x==='object' && !Array.isArray(x);
  const text=(x,max)=>typeof x==='string' && x.length<=max*2 && Array.from(x).length<=max && x.trim().length>0;
  const integer=(x,min=0,max=Number.MAX_SAFE_INTEGER)=>Number.isSafeInteger(x) && x>=min && x<=max;
  const finite=x=>typeof x==='number' && Number.isFinite(x);
  const range=(x,min,max)=>finite(x) && x>=min-EPS && x<=max+EPS;
  const rate=x=>finite(x) && x>=0 && x<=1;
  const close=(a,b)=>finite(a) && finite(b) && Math.abs(a-b)<=1e-7*Math.max(1,Math.abs(a),Math.abs(b));
  const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const pretty=x=>x===null || !finite(x) ? 'Unknown' : x!==0 && Math.abs(x)<=1e-12 ? '≈ 0' : Number(x.toPrecision(6)).toString();
  const percent=x=>x===null || !finite(x) ? 'Unknown' : `${(x*100).toFixed(1)}%`;
  const exactKeys=(value,ids)=>object(value) && Object.keys(value).length===ids.length && ids.every(id=>Object.hasOwn(value,id));
  const sameIds=(a,b)=>Array.isArray(a) && a.length===b.length && new Set(a).size===a.length && a.every(x=>b.includes(x));

  // Reproduce the producer's saved-spectrum grouping, without computing any
  // eigenvalues or coefficients. The group anchor is its first eigenvalue,
  // not the previous member; the separate basis zero clipping is untouched.
  function savedSpectrumGroups(values) {
    if(!Array.isArray(values) || values.some((value,i)=>!range(value,0,2) || i>0 && value<values[i-1]))return null;
    const groups=[];
    for(let start=0;start<values.length;) {
      let stop=start+1;
      while(stop<values.length && Math.abs(values[stop]-values[start])<1e-8)stop++;
      groups.push({eigenvalue:values[start],multiplicity:stop-start});start=stop;
    }
    return groups;
  }

  function signalIds(projection) {
    if(!object(projection?.observable_signals))return [];
    const ids=Object.keys(projection.observable_signals);
    return ids.length<=LIMITS.signals && ids.every(id=>text(id,128)) ? ids : [];
  }
  function energyCheck(signal,ids,rates) {
    if(signal?.available!==true)return {available:false,reason:text(signal?.reason,1500) ? signal.reason : 'Saved spectral summary unavailable.'};
    if(signal.operator!=='normalized_graph_laplacian' || signal.symmetrization!=='(A+A.T)/2' || !range(signal.cutoff,0,2) ||
      !finite(signal.signal_energy) || signal.signal_energy<0 || !finite(signal.positive_frequency_energy) || signal.positive_frequency_energy<0 ||
      !Array.isArray(signal.eigenspace_energy) || signal.eigenspace_energy.length>LIMITS.nodes)return {available:false,reason:'Malformed saved spectral quantities; comparison withheld.'};
    const groups=signal.eigenspace_energy;
    if(groups.some((g,i)=>!object(g) || !range(g.eigenvalue,0,2) || !finite(g.energy) || g.energy<0 || !integer(g.multiplicity,1,LIMITS.nodes) ||
      i>0 && g.eigenvalue<groups[i-1].eigenvalue+1e-8) || groups.reduce((sum,g)=>sum+g.multiplicity,0)!==ids.length)return {available:false,reason:'Invalid grouped eigenspaces; comparison withheld.'};
    const energy=ids.reduce((sum,id)=>sum+rates[id]**2,0),groupEnergy=groups.reduce((sum,g)=>sum+g.energy,0);
    const positive=groups.filter(g=>g.eigenvalue>1e-8).reduce((sum,g)=>sum+g.energy,0);
    const low=groups.filter(g=>g.eigenvalue>1e-8 && g.eigenvalue<=signal.cutoff+1e-8).reduce((sum,g)=>sum+g.energy,0);
    const nullEnergy=groups.filter(g=>g.eigenvalue<=1e-8).reduce((sum,g)=>sum+g.energy,0);
    const rayleigh=energy ? groups.reduce((sum,g)=>sum+g.eigenvalue*g.energy,0)/energy : null;
    const lowFraction=positive>1e-12 ? low/positive : null,nullFraction=energy ? nullEnergy/energy : null;
    const nullable=(value,expected,max)=>expected===null ? value===null : range(value,0,max) && close(value,expected);
    if(!close(signal.signal_energy,energy) || !close(groupEnergy,energy) || !close(signal.positive_frequency_energy,positive) ||
      !nullable(signal.rayleigh_smoothness,rayleigh,2) || !nullable(signal.low_positive_frequency_energy_fraction,lowFraction,1) ||
      !nullable(signal.null_energy_fraction,nullFraction,1))return {available:false,reason:'Inconsistent saved energy/fraction denominators; comparison withheld.'};
    return {available:true,reason:null,summary:signal};
  }
  function validate(projection,{signalId=null}={}) {
    try {
      if(!object(projection) || !Array.isArray(projection.nodes) || projection.nodes.length>LIMITS.nodes)return {available:false,reason:'Bounded node measurements unavailable.'};
      const nodes=projection.nodes,ids=nodes.map(node=>node?.id),choices=signalIds(projection);
      if(nodes.some(node=>!object(node) || !text(node.id,200) || node.name!==undefined && node.name!==null && !text(node.name,1000)) || new Set(ids).size!==ids.length || !choices.length)return {available:false,reason:'Node identities or saved instruments are invalid or absent.'};
      const chosen=signalId===null ? choices[0] : signalId;
      if(!choices.includes(chosen))return {available:false,reason:'Requested saved instrument is unavailable; another instrument was not substituted.'};
      const signal=projection.observable_signals[chosen];
      if(!object(signal) || signal.observable!==chosen || signal.measurement!=='deterministic_regex_positive_messages_per_authored_message' ||
        typeof signal.available!=='boolean' || signal.detector_version!==null && !text(signal.detector_version,200) ||
        !exactKeys(signal.denominators,ids) || !exactKeys(signal.positive_message_ids,ids))return {available:false,reason:'Saved measurement metadata or node denominators are malformed.'};
      const missing=[],measured=[],seen=new Set();let positiveCount=0;
      for(const id of ids) {
        const denominator=signal.denominators[id],positives=signal.positive_message_ids[id];
        if(!integer(denominator,0,LIMITS.denominator) || !Array.isArray(positives) || positives.length>denominator || positives.length>LIMITS.positiveIds || (positiveCount+=positives.length)>LIMITS.positiveIds)return {available:false,reason:'Authored-message or positive-ID bounds are invalid.'};
        for(const mid of positives) {if(!text(mid,200) || seen.has(mid))return {available:false,reason:'Positive-message provenance is malformed or duplicated.'};seen.add(mid);}
        (denominator===0 ? missing:measured).push(id);
      }
      const rates={};
      if(missing.length) {
        if(signal.available!==false || !sameIds(signal.missing_signal_nodes,missing) || Object.hasOwn(signal,'rates'))return {available:false,reason:'Missing author denominators must remain unavailable, without zero imputation.'};
        for(const id of measured)rates[id]=signal.positive_message_ids[id].length/signal.denominators[id];
      } else {
        if(!exactKeys(signal.rates,ids) || ids.some(id=>!rate(signal.rates[id]) || !close(signal.rates[id],signal.positive_message_ids[id].length/signal.denominators[id])))return {available:false,reason:'Recorded rates do not match measured message denominators.'};
        Object.assign(rates,signal.rates);
      }
      const basis=projection.spectral;
      let full=energyCheck(signal,ids,rates),basisKnown=false;
      if(full.available) {
        const savedGroups=savedSpectrumGroups(basis?.eigenvalues);
        basisKnown=object(basis) && basis.available===true && basis.operator==='normalized_graph_laplacian' && sameIds(basis.node_order,ids) &&
          integer(basis.nullity,0,ids.length) && (basis.isolated_ids===undefined && ids.length===0 || Array.isArray(basis.isolated_ids) && new Set(basis.isolated_ids).size===basis.isolated_ids.length && basis.isolated_ids.every(id=>ids.includes(id))) &&
          savedGroups!==null && basis.eigenvalues.length===ids.length &&
          basis.nullity===basis.eigenvalues.filter(value=>value===0).length && (basis.isolated_ids || []).length<=basis.nullity;
        if(!basisKnown)full={available:false,reason:'Saved operator/node scope is missing or inconsistent; energy withheld.'};
        else if(savedGroups.length!==signal.eigenspace_energy.length || savedGroups.some((group,i)=>group.eigenvalue!==signal.eigenspace_energy[i].eigenvalue || group.multiplicity!==signal.eigenspace_energy[i].multiplicity))full={available:false,reason:'Saved eigenspace groups do not match the recorded operator spectrum; energy withheld.'};
      }
      let induced=null;
      if(Object.hasOwn(signal,'induced_author_subgraph')) {
        const value=signal.induced_author_subgraph;
        if(!missing.length || !measured.length || !object(value) || !sameIds(value.included_nodes,measured) || !sameIds(value.excluded_nodes,missing) ||
          !exactKeys(value.rates,measured) || measured.some(id=>!rate(value.rates[id]) || !close(value.rates[id],rates[id])))induced={available:false,reason:'Induced author subgraph scope is malformed; energy withheld.'};
        else induced=energyCheck(value,measured,value.rates);
      }
      return {available:true,reason:null,signalId:chosen,choices,nodes,signal,rates,measured,missing,full,induced,basisKnown,basis};
    } catch(_) {return {available:false,reason:'Malformed saved spectral measurement; comparison withheld.'};}
  }
  function energyTable(checked,title) {
    if(!checked?.available)return `<div class="detail-section"><h3>${esc(title)}</h3><p>${esc(checked?.reason || 'Unknown: no saved energy summary.')}</p></div>`;
    const s=checked.summary,rows=s.eigenspace_energy.map(group=>`<tr><td>${esc(pretty(group.eigenvalue))}</td><td>${group.multiplicity}</td><td>${esc(pretty(group.energy))}</td><td>${group.eigenvalue<=1e-8 ? 'Null/near-zero band' : group.eigenvalue<=s.cutoff+1e-8 ? 'Low positive frequency' : 'Other positive frequency'}</td></tr>`).join('');
    return `<div class="detail-section"><h3>${esc(title)}</h3><div class="table-wrap"><table><caption>Grouped eigenspace energy · squared raw-rate coordinates</caption><thead><tr><th>λ</th><th>MODES</th><th>ENERGY</th><th>RECORDED BAND</th></tr></thead><tbody>${rows || '<tr><td colspan="4">Empty node scope; no modes.</td></tr>'}</tbody></table></div><dl class="key-value"><dt>Signal squared energy</dt><dd>${esc(pretty(s.signal_energy))}</dd><dt>Positive-frequency energy</dt><dd>${esc(pretty(s.positive_frequency_energy))}</dd><dt>Null/near-zero / total energy</dt><dd>${esc(percent(s.null_energy_fraction))} · grouped λ ≤ 10⁻⁸</dd><dt>Low-positive / positive energy</dt><dd>${esc(percent(s.low_positive_frequency_energy_fraction))} · 10⁻⁸ &lt; λ ≤ ${esc(pretty(s.cutoff))}</dd><dt>Rayleigh ratio xᵀLx / xᵀx</dt><dd>${esc(pretty(s.rayleigh_smoothness))}</dd></dl><p class="field-help">Zero signal energy has unknown ratios. Positive-frequency fractions are unknown when positive energy ≤ 10⁻¹². Repeated modes are grouped; axis signs and coordinates are not compared.</p><details class="raw-detail"><summary>Original saved numeric quantities</summary><pre>${esc(JSON.stringify({signal_energy:s.signal_energy,positive_frequency_energy:s.positive_frequency_energy,rayleigh_smoothness:s.rayleigh_smoothness,null_energy_fraction:s.null_energy_fraction,low_positive_frequency_energy_fraction:s.low_positive_frequency_energy_fraction,cutoff:s.cutoff,eigenspace_energy:s.eigenspace_energy},null,2))}</pre></details></div>`;
  }
  function render(projection,options={}) {
    const checked=validate(projection,options);
    if(!checked.available)return `<div class="note">${esc(checked.reason)}</div>`;
    const {nodes,signal,rates,missing,measured}=checked;
    const select=`<label class="small-label">Recorded language instrument<select class="control" data-spectral-signal>${checked.choices.map(id=>`<option value="${esc(id)}" ${id===checked.signalId ? 'selected':''}>${esc(id.replace(/_/g,' '))}</option>`).join('')}</select></label>`;
    const rows=nodes.map(node=>{const n=signal.denominators[node.id];return `<tr><td title="${esc(node.id)}">${esc(node.name || node.id)}<br><small class="mono">${esc(node.id)}</small></td><td>${n}</td><td>${n ? signal.positive_message_ids[node.id].length:'Unknown'}</td><td>${n ? esc(percent(rates[node.id])):'Unknown · no authored denominator'}</td></tr>`;}).join('');
    const full=energyTable(checked.full,'Full saved graph');
    const induced=checked.induced ? `<p class="note">Induced author subgraph: ${measured.length} measured nodes, ${missing.length} excluded. Its operator is recomputed on a different graph; this does not fill the full graph’s missing rates. Component/isolate identities are not retained in this induced summary.</p>${energyTable(checked.induced,'Separate induced author subgraph')}`:'';
    const limits=checked.basisKnown ? `<p>${checked.basis.nullity} recorded null modes · ${(checked.basis.isolated_ids || []).length} isolate nodes. ${checked.basis.nullity===nodes.length && nodes.length ? 'All modes are null; there are no nontrivial graph frequencies in this operator.' : checked.basis.nullity>1 ? 'Disconnected components and isolates contribute separate null modes.' : ''}</p>`:'';
    return `<div class="spectral-signal-view">${select}<p class="section-caption">${measured.length} / ${nodes.length} node denominators observed · ${missing.length} missing. Instrument version: ${esc(signal.detector_version || 'Unknown')}.</p><div class="table-wrap"><table><caption>Node language signal · saved node order, not a ranking</caption><thead><tr><th>NODE</th><th>AUTHORED MESSAGES</th><th>POSITIVE MESSAGE IDS</th><th>HIT PROPORTION</th></tr></thead><tbody>${rows || '<tr><td colspan="4">Empty node scope.</td></tr>'}</tbody></table></div><p class="field-help">Counts use retained agent-authored messages. Zero hits means no regex match here; it does not establish absent behavior. Missing denominators stay unknown, including their hit proportions.</p>${full}${induced}${limits}<details class="raw-detail"><summary>Operator scaling and interpretation limits</summary><p>L = D⁻¹ᐟ²(D − S)D⁻¹ᐟ², S = (A + Aᵀ)/2. The producer projects raw hit proportions x, without centering or imputation. Normalized edge comparisons use xᵢ/√dᵢ; equal raw rates need not be a null signal when degrees differ. A connected non-isolate null vector scales with √degree. Isolates have zero Laplacian rows; null energy in disconnected components or isolates is not agreement. Basis eigenvalues with magnitude &lt; 10⁻¹⁰ are clipped to zero by the producer; grouped energy uses a separate 10⁻⁸ near-zero threshold.</p><p>Direction is symmetrized only for this operator. These are recorded graph coordinates, not consensus, influence, contagion, latent behavior or continuous-manifold Laplace–Beltrami measurements. Language labels are uncalibrated; shared tasks, quotations and window selection remain rival explanations. The view checks grouped eigenvalues and multiplicities against the saved sorted spectrum; it does not authenticate source bytes or rerun eigenvalues or coefficients.</p><p>Display uses six significant digits and one decimal for percentages; nonzero magnitudes ≤ 10⁻¹² show ≈ 0. Original numbers remain above without clipping. Energy/fraction consistency admits numerical roundoff within 10⁻⁸; node hit proportions must be within [0, 1]. No missing value becomes zero.</p></details></div>`;
  }
  globalThis.SpectralSignalView=Object.freeze({render,validate,signalIds,limits:LIMITS});
})();
