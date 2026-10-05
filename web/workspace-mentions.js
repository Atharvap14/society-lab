/* Local mention selection. The host decides how exact context is used. */
(function(scope){
  'use strict';
  const VERSION='workspace-mentions-v1',LIMITS={items:100,query:200,label:240,value:200000};
  const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const copy=v=>JSON.parse(JSON.stringify(v));
  const identifier=s=>typeof s==='string'&&/^[A-Za-z0-9][A-Za-z0-9_.-]{0,199}$/.test(s);
  const ref=r=>r&&typeof r==='object'&&!Array.isArray(r)&&Object.keys(r).length===3&&identifier(r.id)&&Number.isSafeInteger(r.version)&&r.version>0&&typeof r.hash==='string'&&/^[a-f0-9]{64}$/.test(r.hash);
  const text=(v,max)=>typeof v==='string'&&v.trim().length>0&&v.length<=max;
  function item(raw){
    if(!raw||typeof raw!=='object'||Array.isArray(raw)||!['chat','artifact'].includes(raw.type)||!text(raw.label,LIMITS.label))return null;
    const out={type:raw.type,label:raw.label};
    for(const key of ['project_name','chat_name'])if(raw[key]!==undefined){if(typeof raw[key]!=='string'||raw[key].length>LIMITS.label)return null;out[key]=raw[key];}
    if(raw.type==='chat'){if(!identifier(raw.chat_id)||raw.ref!==undefined)return null;out.chat_id=raw.chat_id;}
    else{if(!ref(raw.ref))return null;out.ref={id:raw.ref.id,version:raw.ref.version,hash:raw.ref.hash};if(raw.chat_id!==undefined){if(!identifier(raw.chat_id))return null;out.chat_id=raw.chat_id;}}
    return out;
  }
  function normalize(packet){
    if(!packet||!Array.isArray(packet.items)||packet.items.length>LIMITS.items||!Number.isSafeInteger(packet.total)||packet.total<packet.items.length||typeof packet.truncated!=='boolean')return {available:false,reason:'Mention choices are unavailable.'};
    const items=[],seen=new Set();
    for(const raw of packet.items){const normalized=item(raw);if(!normalized)return {available:false,reason:'The saved context choices could not be checked.'};const key=normalized.type==='chat'?'chat:'+normalized.chat_id:'artifact:'+JSON.stringify(normalized.ref);if(seen.has(key))return {available:false,reason:'The saved context choices are ambiguous.'};seen.add(key);items.push(normalized);}
    return {available:true,items,total:packet.total,truncated:packet.truncated};
  }
  function token(textarea){
    const value=textarea.value,caret=textarea.selectionStart;
    if(typeof value!=='string'||value.length>LIMITS.value||!Number.isSafeInteger(caret)||caret<0||caret>value.length)return null;
    const before=value.slice(0,caret),start=before.lastIndexOf('@');
    if(start<0||(start>0&&!/[\s([{]/.test(before[start-1])))return null;
    const query=before.slice(start+1);if(query.length>LIMITS.query||/[\r\n@]/.test(query))return null;
    return {start,end:caret,query,value};
  }
  let serial=0;
  function attach(textarea,{search,onSelect,onChange,debounceMs=180}={}){
    if(!textarea||typeof textarea.addEventListener!=='function'||typeof search!=='function'||typeof onSelect!=='function'||!Number.isSafeInteger(debounceMs)||debounceMs<0||debounceMs>1000)throw new TypeError('Mention input needs a search function, selection callback and bounded debounce.');
    const document=textarea.ownerDocument||scope.document;
    if(!document?.body?.appendChild||typeof document.createElement!=='function')throw new TypeError('Mention input needs a browser document.');
    const popup=document.createElement('div'),id='workspace-mentions-'+(++serial),saved={};
    for(const key of ['role','aria-autocomplete','aria-controls','aria-expanded','aria-activedescendant'])saved[key]=textarea.getAttribute(key);
    popup.className='wm-popup';popup.id=id;popup.hidden=true;document.body.appendChild(popup);
    textarea.setAttribute('role','combobox');textarea.setAttribute('aria-autocomplete','list');textarea.setAttribute('aria-controls',id);textarea.setAttribute('aria-expanded','false');
    let alive=true,sequence=0,timer=null,current=null,items=[],selected=0,total=null,truncated=false,suppressed=null,selectedMention=null,loading=false;
    const matches=t=>t&&current&&t.start===current.start&&t.end===current.end&&t.query===current.query&&t.value===current.value;
    function position(){if(popup.hidden||!textarea.getBoundingClientRect)return;const r=textarea.getBoundingClientRect(),viewportWidth=scope.innerWidth||1000,viewportHeight=scope.innerHeight||800,width=Math.max(120,Math.min(Math.max(240,r.width||360),viewportWidth-24)),above=viewportHeight-r.bottom<180&&r.top>180;popup.style.left=Math.max(12,Math.min(r.left,viewportWidth-width-12))+'px';popup.style.top=above?'auto':(r.bottom+6)+'px';popup.style.bottom=above?(viewportHeight-r.top+6)+'px':'auto';popup.style.width=width+'px';popup.style.maxHeight=Math.max(80,Math.min(360,above?r.top-18:viewportHeight-r.bottom-18))+'px';}
    function close(){if(timer!==null)scope.clearTimeout(timer);timer=null;sequence++;current=null;items=[];total=null;truncated=false;loading=false;popup.hidden=true;popup.innerHTML='';textarea.setAttribute('aria-expanded','false');textarea.removeAttribute('aria-activedescendant');}
    function draw(message){
      if(!alive||!current)return;popup.hidden=false;textarea.setAttribute('aria-expanded','true');
      popup.innerHTML='<div class="wm-heading">Mention a chat or saved item</div>'+(message?'<p class="wm-status" role="status">'+esc(message)+'</p>':'<div class="wm-list" role="listbox" aria-label="Saved context choices">'+items.map((row,index)=>'<button type="button" tabindex="-1" role="option" id="'+id+'-'+index+'" data-wm-index="'+index+'" aria-selected="'+(index===selected)+'" class="wm-option '+(index===selected?'active':'')+'"><span class="wm-icon" aria-hidden="true">'+(row.type==='chat'?'◌':'▥')+'</span><span><strong>'+esc(row.label)+'</strong><small>'+esc([row.type==='chat'?'Chat':'Saved item',row.project_name,row.chat_name].filter(Boolean).join(' · '))+'</small></span></button>').join('')+'</div><p class="wm-foot">'+items.length+' shown'+(total!==null?' · '+total+' matches':'')+(truncated?' · Search to narrow the list':'')+' · ↑↓ choose · Enter mention</p>');
      if(items.length&&!message)textarea.setAttribute('aria-activedescendant',id+'-'+selected);else textarea.removeAttribute('aria-activedescendant');position();
    }
    async function load(request,t){
      if(!alive||request!==sequence||!matches(token(textarea)))return;loading=true;draw('Finding saved context…');
      try{const result=normalize(await search(t.query));if(!alive||request!==sequence||!matches(token(textarea)))return;loading=false;
        if(!result.available){items=[];draw(result.reason);return;}items=result.items;total=result.total;truncated=result.truncated;selected=0;draw(items.length?null:'No matching chats or saved items.');
      }catch(_){if(alive&&request===sequence&&matches(token(textarea))){loading=false;items=[];draw('Saved context is unavailable. Try another search.');}}
    }
    function changed(){
      if(!alive)return;const t=token(textarea),continuing=t&&selectedMention&&t.start>=selectedMention.start&&t.start<selectedMention.end&&t.end>=selectedMention.end&&t.value.slice(selectedMention.start,selectedMention.end)===selectedMention.text;
      if(!t||continuing||suppressed===t.value+'|'+t.end){close();return;}selectedMention=null;if(matches(t))return;
      close();current=t;const request=sequence;draw('Finding saved context…');timer=scope.setTimeout(()=>{timer=null;load(request,t);},debounceMs);
    }
    function choose(index){
      if(!alive||loading||!Number.isSafeInteger(index)||index<0||index>=items.length||!matches(token(textarea)))return;
      const chosen=copy(items[index]),t=current,insertion='@'+chosen.label+' ',next=t.value.slice(0,t.start)+insertion+t.value.slice(t.end);
      if(next.length>LIMITS.value)return;const caret=t.start+insertion.length;textarea.value=next;textarea.setSelectionRange?.(caret,caret);suppressed=next+'|'+caret;selectedMention={start:t.start,end:caret,text:insertion};close();textarea.focus();
      onChange?.(next);onSelect(chosen);
    }
    function keydown(event){
      if(!current||popup.hidden)return;
      if(event.key==='Escape'){event.preventDefault();suppressed=textarea.value+'|'+textarea.selectionStart;close();return;}
      if(event.key==='Tab'){close();return;}
      if(['ArrowDown','ArrowUp'].includes(event.key)&&items.length){event.preventDefault();selected=(selected+(event.key==='ArrowDown'?1:-1)+items.length)%items.length;draw();popup.querySelector('[aria-selected="true"]')?.scrollIntoView?.({block:'nearest'});}
      else if(event.key==='Enter'&&!event.isComposing&&items.length&&!loading){event.preventDefault();choose(selected);}
    }
    function clicked(event){const button=event.target?.closest?.('[data-wm-index]');if(!button||!popup.contains(button))return;event.preventDefault();choose(Number(button.dataset.wmIndex));}
    function mousedown(event){if(event.target?.closest?.('[data-wm-index]'))event.preventDefault();}
    for(const name of ['input','click','keyup'])textarea.addEventListener(name,changed);
    textarea.addEventListener('keydown',keydown);textarea.addEventListener('blur',close);popup.addEventListener('click',clicked);popup.addEventListener('mousedown',mousedown);
    scope.addEventListener?.('resize',position);scope.addEventListener?.('scroll',position,true);
    function cleanup(){if(!alive)return;close();alive=false;for(const name of ['input','click','keyup'])textarea.removeEventListener(name,changed);textarea.removeEventListener('keydown',keydown);textarea.removeEventListener('blur',close);popup.removeEventListener('click',clicked);popup.removeEventListener('mousedown',mousedown);scope.removeEventListener?.('resize',position);scope.removeEventListener?.('scroll',position,true);popup.remove();for(const[key,value]of Object.entries(saved))if(value===null)textarea.removeAttribute(key);else textarea.setAttribute(key,value);}
    cleanup.getState=()=>({version:VERSION,open:!popup.hidden,query:current?.query??null,loading,selected_index:items.length?selected:null,items:copy(items),total,truncated});
    return cleanup;
  }
  scope.WorkspaceMentions={version:VERSION,limits:Object.freeze({...LIMITS}),normalize,attach};
  if(typeof module!=='undefined')module.exports=scope.WorkspaceMentions;
})(typeof globalThis==='undefined'?window:globalThis);
