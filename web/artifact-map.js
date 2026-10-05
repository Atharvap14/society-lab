/* Exact saved-record navigation. Layout and provenance links imply no causal effect. */
(function(scope){
  'use strict';
  const VERSION='artifact-map-v1',RELATIONS=['created','reference','reused','copied'];
  const LIMITS=Object.freeze({artifacts:256,edges:1024,title:240,summary:1600,modelCharacters:800000});
  const ACTIONS=['open','replay','reuse','copy'],REPLAY=['dataset','village_access_experiment','village_recovery_experiment','observability_run'];
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const dict=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
  const exactKeys=(v,keys)=>dict(v)&&Object.keys(v).sort().join(',')===keys.slice().sort().join(',');
  const id=v=>typeof v==='string'&&/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$/.test(v);
  const text=(v,n)=>typeof v==='string'&&v.length<=n;
  const validRef=r=>exactKeys(r,['id','version','hash'])&&id(r.id)&&Number.isSafeInteger(r.version)&&r.version>0&&r.version<=1000000000&&typeof r.hash==='string'&&/^[0-9a-f]{64}$/.test(r.hash);
  const ref=r=>({id:r.id,version:r.version,hash:r.hash});
  const key=r=>r.id+'@'+r.version+':'+r.hash;
  const same=(a,b)=>validRef(a)&&validRef(b)&&key(a)===key(b);
  const unavailable=reason=>({available:false,reason,model_version:VERSION});
  function timestamp(v){
    if(v===null||v===undefined)return true;
    if(!text(v,64)||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})$/.test(v)||!Number.isFinite(Date.parse(v)))return false;
    const [y,m,d]=v.slice(0,10).split('-').map(Number),check=new Date(Date.UTC(y,m-1,d));
    return y>=100&&check.getUTCFullYear()===y&&check.getUTCMonth()===m-1&&check.getUTCDate()===d;
  }
  function normalize(packet){
    try{
      if(!dict(packet)||!Array.isArray(packet.artifacts)||!Array.isArray(packet.edges))return unavailable('Saved artifact descriptors and explicit provenance links are required.');
      if(packet.artifacts.length>LIMITS.artifacts||packet.edges.length>LIMITS.edges)return unavailable('This map exceeds its declared display bounds. Choose a smaller exact collection.');
      const seen=new Set(),artifacts=[];
      for(const a of packet.artifacts){
        if(!dict(a)||!validRef(a.ref)||!id(a.kind)||!text(a.title,LIMITS.title)||!a.title.trim()||!text(a.summary??'',LIMITS.summary)||!timestamp(a.created_at))return unavailable('An artifact descriptor is malformed. Exact saved versions have not been substituted.');
        const k=key(a.ref);if(seen.has(k))return unavailable('The same exact saved version is listed twice. Deduplicate its attachments before drawing a map.');seen.add(k);
        if(a.relation!==undefined&&a.relation!==null&&!RELATIONS.includes(a.relation))return unavailable('An artifact relationship label is unsupported.');
        let origin=null;
        if(a.origin!==undefined&&a.origin!==null){
          if(!dict(a.origin)||Object.keys(a.origin).some(k=>!['project_id','project_name','chat_id','chat_name'].includes(k)))return unavailable('A source project/chat declaration is malformed.');
          origin={};for(const k of Object.keys(a.origin)){
            const v=a.origin[k];if((k.endsWith('_id')?!id(v):!text(v,240)||!v.trim()))return unavailable('A source project/chat declaration is malformed.');origin[k]=v;
          }
        }
        const capabilities={open:true,replay:REPLAY.includes(a.kind),reuse:true,copy:true};
        if(a.capabilities!==undefined){if(!dict(a.capabilities)||Object.keys(a.capabilities).some(k=>!ACTIONS.includes(k))||Object.values(a.capabilities).some(v=>typeof v!=='boolean'))return unavailable('Artifact action availability must be explicitly typed.');Object.assign(capabilities,a.capabilities);}
        artifacts.push({ref:ref(a.ref),kind:a.kind,title:a.title,summary:a.summary??'',origin,
          relation:a.relation??null,created_at:a.created_at??null,capabilities});
      }
      const edgeKeys=new Set(),edges=[];
      for(const edge of packet.edges){
        if(!dict(edge)||!validRef(edge.from_ref)||!validRef(edge.to_ref)||!RELATIONS.includes(edge.relation)||!text(edge.label??'',240))return unavailable('An explicit provenance link is malformed.');
        if(!seen.has(key(edge.from_ref))||!seen.has(key(edge.to_ref)))return unavailable('A provenance link refers to a saved version outside this collection. No placeholder node was invented.');
        // Distinct saved fields may reference the same exact source. Preserve
        // those explicit paths; only an identical declared link is duplicated.
        const ek=JSON.stringify([key(edge.from_ref),key(edge.to_ref),edge.relation,edge.label??'']);
        if(edgeKeys.has(ek))return unavailable('An explicit provenance link is duplicated.');edgeKeys.add(ek);
        edges.push({from_ref:ref(edge.from_ref),to_ref:ref(edge.to_ref),relation:edge.relation,label:edge.label??''});
      }
      const selected=packet.selected_ref??null;
      if(selected!==null&&(!validRef(selected)||!seen.has(key(selected))))return unavailable('The selected exact version is outside this collection. No latest-version fallback was chosen.');
      return {available:true,model_version:VERSION,artifacts,edges,selected_ref:selected?ref(selected):null,limits:{...LIMITS},
        scope:'Workspace-declared saved-record provenance. Links do not describe communication, influence or causal effects.'};
    }catch(_){return unavailable('The bounded saved-artifact collection cannot be displayed.');}
  }
  function typeName(kind){return ({dataset:'Source data',discovery:'Discovery',behavior:'Behavior candidate',theory:'Theory',
    guided_plan:'Study plan',guided_simulator:'Simulator',guided_result:'Study result',village_access_experiment:'AI Village experiment',village_recovery_experiment:'AI Village link repair',village_incident:'Source incidents',
    observation_brief:'Source briefing',observability_run:'Recorded run',verification:'Replay check',claim_audit:'Checked claims',
    protocol:'Study protocol',environment_blueprint:'Environment blueprint'})[kind]||kind.replace(/_/g,' ');}
  function origin(a){if(!a.origin||!Object.keys(a.origin).length)return 'Origin not declared';return [a.origin.project_name||a.origin.project_id,a.origin.chat_name||a.origin.chat_id].filter(Boolean).join(' / ');}
  function selected(model,state){return model.artifacts.find(a=>same(a.ref,state.selected))||null;}
  function visible(model,state){const needle=state.search.trim().toLocaleLowerCase();return model.artifacts.map((a,index)=>({a,index})).filter(({a})=>(state.kind==='all'||a.kind===state.kind)&&(!needle||[a.title,a.summary,a.kind,a.ref.id,origin(a)].join(' ').toLocaleLowerCase().includes(needle)));}
  function layout(rows){const cols=Math.min(4,Math.max(1,rows.length)),width=Math.max(780,cols*248+80),height=Math.max(420,Math.ceil(rows.length/cols)*154+85);return {width,height,positions:new Map(rows.map(({index},i)=>[index,{x:46+(i%cols)*248,y:42+Math.floor(i/cols)*154}]))};}
  function graph(model,state){
    const rows=visible(model,state),l=layout(rows),indexes=new Map(model.artifacts.map((a,i)=>[key(a.ref),i]));
    const links=model.edges.map(edge=>{
      const from=l.positions.get(indexes.get(key(edge.from_ref))),to=l.positions.get(indexes.get(key(edge.to_ref)));if(!from||!to)return '';
      const x1=from.x+108,y1=from.y+53,x2=to.x+108,y2=to.y+53;
      if(same(edge.from_ref,edge.to_ref))return `<g><path class="am-edge am-${edge.relation}" d="M ${x1} ${y1-40} c 75 -75 95 75 0 55"/><title>${esc(edge.relation+': '+edge.label)}</title><text x="${x1+66}" y="${y1}">${esc(edge.relation)}</text></g>`;
      return `<g><path class="am-edge am-${edge.relation}" d="M ${x1} ${y1} L ${x2} ${y2}"/><title>${esc(edge.relation+': '+edge.label)}</title><text x="${(x1+x2)/2}" y="${(y1+y2)/2-7}">${esc(edge.relation)}</text></g>`;
    }).join('');
    const buttons=rows.map(({a,index})=>{const p=l.positions.get(index);return `<button type="button" class="am-node ${same(a.ref,state.selected)?'selected':''}" data-am-index="${index}" style="left:${p.x}px;top:${p.y}px" aria-pressed="${same(a.ref,state.selected)}" aria-label="${esc(a.title+'; '+typeName(a.kind)+'; saved version '+a.ref.version)}"><span class="am-node-kind">${esc(typeName(a.kind))}</span><strong>${esc(a.title)}</strong><span class="am-node-origin">${esc(origin(a))}</span><span class="am-node-version">v${a.ref.version}${a.relation?' · '+esc(a.relation):''}</span></button>`;}).join('');
    return `<div class="am-stage-size" style="width:${l.width*state.zoom}px;height:${l.height*state.zoom}px"><div class="am-scene" style="width:${l.width}px;height:${l.height}px;transform:scale(${state.zoom})"><svg class="am-lines" width="${l.width}" height="${l.height}" aria-label="Explicit saved-record provenance links" role="img">${links}</svg>${buttons}</div></div>`;
  }
  function list(model,state){return visible(model,state).map(({a,index})=>`<button type="button" class="am-list-item ${same(a.ref,state.selected)?'selected':''}" data-am-index="${index}" aria-pressed="${same(a.ref,state.selected)}"><span><span class="am-node-kind">${esc(typeName(a.kind))}</span><strong>${esc(a.title)}</strong><small>${esc(origin(a))}</small></span><span>v${a.ref.version}${a.relation?' · '+esc(a.relation):''}</span></button>`).join('')||'<p class="am-empty">No saved records match these filters.</p>';}
  function detail(model,state,handlers){
    const a=selected(model,state);if(!a)return '<h3>Choose a saved record.</h3><p>Select a card to inspect its exact version and available actions.</p>';
    const index=model.artifacts.indexOf(a),links=model.edges.filter(edge=>same(edge.from_ref,a.ref)||same(edge.to_ref,a.ref));
    const actions=ACTIONS.map(action=>{
      const available=a.capabilities[action]&&(!handlers||typeof handlers['on'+action[0].toUpperCase()+action.slice(1)]==='function');
      return `<button type="button" class="button ${action==='open'?'primary':''}" data-am-action="${action}" data-am-index="${index}" ${available?'':'disabled'}>${({open:'Open saved version',replay:'Replay',reuse:'Reuse link',copy:'Copy'})[action]}</button>`;
    }).join('');
    return `<span class="eyebrow">${esc(typeName(a.kind))} · SAVED VERSION ${a.ref.version}</span><h3>${esc(a.title)}</h3><p class="am-summary">${esc(a.summary||'No summary supplied.')}</p><p class="am-small">Workspace summary; model explanations may be unverified.</p><p>${esc(origin(a))}</p><p class="am-small">${esc(a.created_at?'Created '+a.created_at:'Creation time not declared')}</p><div class="action-row am-actions">${actions}</div><p class="am-small">Reuse keeps a link to this version. Copy asks the workspace to create a separate saved record; it does not change the original.</p><details><summary>Exact version and recorded links</summary><code>${esc(a.ref.id)} · v${a.ref.version}<br>${esc(a.ref.hash)}</code><p>These identifiers were supplied by the workspace. This view does not re-read or verify source bytes.</p>${links.length?`<ul>${links.map(edge=>`<li>${esc(edge.relation)}: ${esc(edge.from_ref.id)} v${edge.from_ref.version} → ${esc(edge.to_ref.id)} v${edge.to_ref.version}${edge.label?' · '+esc(edge.label):''}</li>`).join('')}</ul>`:'<p>No explicit links supplied for this record.</p>'}</details>`;
  }
  function stateFor(model){return {search:'',kind:'all',mode:'map',zoom:1,selected:model.selected_ref?ref(model.selected_ref):null};}
  function render(packet){
    const model=normalize(packet);if(!model.available)return `<section class="am-unavailable" role="status"><h2>Artifact map unavailable.</h2><p>${esc(model.reason)}</p></section>`;
    const state=stateFor(model),json=JSON.stringify({artifacts:model.artifacts,edges:model.edges,selected_ref:model.selected_ref}).replace(/</g,'\\u003c').replace(/>/g,'\\u003e').replace(/&/g,'\\u0026');
    if(json.length>LIMITS.modelCharacters)return `<section class="am-unavailable" role="status"><p>The saved descriptor packet exceeds the bounded display size.</p></section>`;
    return `<section class="am-root" data-am-version="${VERSION}" aria-label="Saved artifact map"><script type="application/json" class="am-model">${json}</script><div class="am-heading"><div><span class="eyebrow">YOUR SAVED RESEARCH</span><h2>Sources, ideas and experiments.</h2><p>Open any saved record. Lines show recorded reference, reuse or copy links—not communication or causal influence.</p></div><span class="am-total">${model.artifacts.length} saved versions</span></div><div class="am-toolbar"><label>Search saved records<input type="search" data-am-search placeholder="Title, type, project or chat" autocomplete="off"></label><label>Type<select data-am-kind><option value="all">All types</option>${[...new Set(model.artifacts.map(a=>a.kind))].sort().map(kind=>`<option value="${esc(kind)}">${esc(typeName(kind))}</option>`).join('')}</select></label><div class="am-mode" role="group" aria-label="Artifact layout"><button type="button" data-am-mode="map" aria-pressed="true">Map</button><button type="button" data-am-mode="list" aria-pressed="false">List</button></div><div class="am-zoom" role="group" aria-label="Map zoom"><button type="button" data-am-zoom="out" aria-label="Zoom out">−</button><span data-am-zoom-label>100%</span><button type="button" data-am-zoom="in" aria-label="Zoom in">+</button><button type="button" data-am-zoom="reset">Reset</button></div></div><p class="am-status" role="status" aria-live="polite">${model.artifacts.length} of ${model.artifacts.length} saved versions shown. Positions are for display.</p><div class="am-content"><div class="am-browse"><div class="am-viewport" tabindex="0" aria-label="Artifact map; drag empty space or use arrow keys to pan">${graph(model,state)}</div><div class="am-list" hidden>${list(model,state)}</div></div><aside class="am-detail" aria-label="Selected saved record">${detail(model,state)}</aside></div><p class="am-small">No new records or studies are created by filtering or moving this map. Source projects and chats are displayed only when declared.</p></section>`;
  }
  function attach(container,handlers={}){
    const root=container?.matches?.('.am-root')?container:container?.querySelector?.('.am-root');
    const noop=()=>{};noop.getState=()=>null;if(!root||root.dataset?.amVersion!==VERSION)return noop;
    const raw=root.querySelector('.am-model')?.textContent;if(typeof raw!=='string'||raw.length>LIMITS.modelCharacters)return noop;
    let model;try{model=normalize(JSON.parse(raw));}catch(_){return noop;}if(!model.available)return noop;
    const state=stateFor(model),viewport=root.querySelector('.am-viewport'),listBox=root.querySelector('.am-list'),detailBox=root.querySelector('.am-detail');
    if(!viewport||!listBox||!detailBox)return noop;
    let alive=true,drag=null;
    const contains=target=>root.contains?.(target)!==false;
    const changed=()=>{if(typeof handlers.onSelect==='function')handlers.onSelect(state.selected?ref(state.selected):null);};
    function paint(){if(!alive)return;viewport.innerHTML=graph(model,state);listBox.innerHTML=list(model,state);viewport.hidden=state.mode!=='map';listBox.hidden=state.mode!=='list';detailBox.innerHTML=detail(model,state,handlers);const status=root.querySelector('.am-status');if(status)status.textContent=visible(model,state).length+' of '+model.artifacts.length+' saved versions shown. Filters do not remove saved sources.';const zoom=root.querySelector('[data-am-zoom-label]');if(zoom)zoom.textContent=Math.round(state.zoom*100)+'%';for(const button of root.querySelectorAll?.('[data-am-mode]')||[])button.setAttribute('aria-pressed',String(button.dataset.amMode===state.mode));}
    const boundedIndex=v=>typeof v==='string'&&/^(0|[1-9]\d*)$/.test(v)&&Number(v)<model.artifacts.length?Number(v):null;
    function click(event){const t=event.target.closest?.('[data-am-action],[data-am-index],[data-am-mode],[data-am-zoom]');if(!t||!contains(t)||!alive)return;
      if(t.dataset.amAction){const action=t.dataset.amAction,index=boundedIndex(t.dataset.amIndex);if(!ACTIONS.includes(action)||index===null||t.disabled||!model.artifacts[index].capabilities[action])return;const callback=handlers['on'+action[0].toUpperCase()+action.slice(1)];if(typeof callback==='function')callback(ref(model.artifacts[index].ref));return;}
      if(t.dataset.amIndex!==undefined){const index=boundedIndex(t.dataset.amIndex);if(index!==null){state.selected=ref(model.artifacts[index].ref);paint();changed();}return;}
      if(t.dataset.amMode){if(['map','list'].includes(t.dataset.amMode)){state.mode=t.dataset.amMode;paint();}return;}
      if(t.dataset.amZoom){state.zoom=t.dataset.amZoom==='reset'?1:Math.min(1.6,Math.max(.55,state.zoom+(t.dataset.amZoom==='in'?.15:t.dataset.amZoom==='out'?-.15:0)));paint();}
    }
    function input(event){if(!alive||!contains(event.target))return;if(event.target.matches?.('[data-am-search]')){state.search=String(event.target.value).slice(0,2000);paint();}else if(event.target.matches?.('[data-am-kind]')){const kind=event.target.value;if(kind==='all'||model.artifacts.some(a=>a.kind===kind)){state.kind=kind;paint();}}}
    function down(event){if(!alive||event.button!==0||event.target.closest?.('[data-am-index],button,input,select'))return;if(event.target===viewport||viewport.contains?.(event.target)){drag={x:event.clientX,y:event.clientY,left:viewport.scrollLeft||0,top:viewport.scrollTop||0};viewport.classList?.add('am-panning');viewport.setPointerCapture?.(event.pointerId);}}
    function move(event){if(!drag||!alive)return;viewport.scrollLeft=drag.left+drag.x-event.clientX;viewport.scrollTop=drag.top+drag.y-event.clientY;}
    function up(){drag=null;viewport.classList?.remove('am-panning');}
    function keydown(event){if(!alive||event.target!==viewport)return;const delta={ArrowLeft:[-70,0],ArrowRight:[70,0],ArrowUp:[0,-70],ArrowDown:[0,70]}[event.key];if(delta){event.preventDefault();viewport.scrollLeft=(viewport.scrollLeft||0)+delta[0];viewport.scrollTop=(viewport.scrollTop||0)+delta[1];}}
    const listeners={click,input,change:input,pointerdown:down,pointermove:move,pointerup:up,pointercancel:up,keydown};
    for(const [name,listener]of Object.entries(listeners))root.addEventListener(name,listener);paint();
    function cleanup(){if(!alive)return;alive=false;up();for(const [name,listener]of Object.entries(listeners))root.removeEventListener(name,listener);}
    cleanup.getState=()=>({search:state.search,kind:state.kind,mode:state.mode,zoom:state.zoom,selected_ref:state.selected?ref(state.selected):null});
    return cleanup;
  }
  scope.ArtifactMap={normalize,render,attach,version:VERSION,limits:LIMITS};
  if(typeof module!=='undefined')module.exports=scope.ArtifactMap;
})(typeof globalThis==='undefined'?window:globalThis);
