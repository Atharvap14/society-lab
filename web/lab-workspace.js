/* Projects and conversations organize research; they do not change its evidence. */
(function(scope){
  'use strict';
  const clone=value=>JSON.parse(JSON.stringify(value));
  const exact=(a,b)=>a && b && a.id===b.id && a.version===b.version && a.hash===b.hash;
  const pin=r=>({id:r.id,version:r.version,hash:r.hash});
  const stable=value=>JSON.stringify(value,(_,v)=>v && !Array.isArray(v) && typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v);
  const uid=()=>typeof crypto!=='undefined' && crypto.randomUUID?crypto.randomUUID():'workspace-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);
    const restoreLabels=value=>Array.isArray(value)?Object.fromEntries(value.slice(-64).filter(row=>row && typeof row.key==='string' && typeof row.label==='string').map(row=>[row.key,row.label])):value || {};
  const RESULT_KINDS=['village_access_experiment','village_recovery_experiment'];
  const EXCLUDED_KINDS=['experiment','network_experiment','complementary_experiment','resource_experiment','timed_resource_experiment','revision_relay_experiment'];
  const researchItem=a=>a && a.fixture!==true && !EXCLUDED_KINDS.includes(a.kind);
  function create(b){
    const e=b.esc,btn=(text,attrs='',primary=false)=>`<button class="button ${primary?'primary':''}" ${attrs}>${e(text)}</button>`;
    const x={index:null,chat:null,catalog:[],catalogTotal:0,ready:false,loading:false,saving:false,dirty:false,timer:null,lastPoll:0,form:null,scope:'chat',search:'',collection:'all',copy:null,contextPreview:null,activeEpoch:0,board:null,conflict:false,savePromise:null,operation:false,compose:'',copyFields:{},activity:null,mentions:[],dockMentions:[],mentionCleanup:null,mentionCatalog:null,mentionLabels:{}};
    const post=body=>b.api('/api/workspaces',{method:'POST',headers:{'Content-Type':'application/json','X-Lab-Token':b.app.state.csrf},body:JSON.stringify({request_id:uid(),...body})});
    const project=()=>x.index?.projects.find(p=>p.id===x.chat?.project_id);
    const chats=()=>x.index?.projects.flatMap(p=>(p.chats || []).map(c=>({...c,project_id:p.id,project_name:p.name}))) || [];
    const chatName=id=>chats().find(c=>c.id===id)?.name || 'Saved conversation';
    const header=(tag,title,text)=>`<div class="exp-heading"><span class="eyebrow">${e(tag)}</span><h1>${e(title)}</h1><p>${e(text)}</p></div>`;
    async function readRecord(ref){const r=await b.object(ref.id,ref.version);if(!exact(r,ref))throw new Error('This exact saved record is unavailable.');if(EXCLUDED_KINDS.includes(r.kind))throw new Error('Choose a source-grounded AI Village item.');return r;}
    function state(){const saved=b.experience.exportWorkspaceState?b.experience.exportWorkspaceState():{view:b.app.view,context:{},ui:{}};saved.ui.workspace={scope:x.scope,search:x.search,collection:x.collection,compose:x.compose,mentions:x.mentions,mention_labels:Object.entries(x.mentionLabels).slice(-64).map(([key,label])=>({key,label})),...(x.copy?{[x.copy.payload?.owner_chat_id && x.copy.payload.owner_chat_id!==b.app.activeChatId?'preview_copy_ref':'copy_ref']:pin(x.copy),copy_fields:x.copyFields}:{})};return saved;}
    function notify(){if(!x.ready || x.loading)return;x.dirty=true;if(x.timer)clearTimeout(x.timer);x.timer=setTimeout(()=>{x.timer=null;flush().catch(err=>b.toast(err.message,true));},350);}
    async function flush(){
      if(x.savePromise){await x.savePromise;return flush();}
      if(!x.chat || x.loading || !x.dirty)return;
      x.savePromise=performSave();try{await x.savePromise;}finally{x.savePromise=null;}
      if(x.dirty && !x.conflict)await flush();
    }
    async function performSave(){
      x.saving=true;const id=x.chat.id,epoch=x.activeEpoch,desired=state(),base=clone(x.chat.state || {});x.dirty=false;
      try{
        let reply;
        try{reply=await post({op:'save_state',chat_id:id,expected_revision:x.chat.revision,state:desired});}
        catch(error){
          const fresh=await b.api('/api/workspaces/chat?chat_id='+encodeURIComponent(id));
          if(stable(fresh.state || {})!==stable(base)){x.conflict=true;x.dirty=true;throw new Error('This chat changed in another window. Your local draft is kept. Reload the chat before saving over those changes.');}
          reply=await post({op:'save_state',chat_id:id,expected_revision:fresh.revision,state:desired});
        }
        if(epoch===x.activeEpoch && x.chat.id===id){x.chat=reply.chat || reply.snapshot || {...x.chat,revision:reply.revision,state:desired};x.chat.state=reply.chat?.state || reply.snapshot?.state || desired;x.conflict=false;sidebar();}
      }finally{x.saving=false;if(x.dirty && !x.conflict && epoch===x.activeEpoch)notify();}
    }
    async function loadIndex(){x.index=await b.api('/api/workspaces');sidebar();return x.index;}
    async function loadChat(id,{view=null,skipSave=false}={}){
      if(x.loading)return;const priorEpoch=x.activeEpoch;if(!skipSave)await flush();if(priorEpoch!==x.activeEpoch)return;
      const epoch=++x.activeEpoch;x.loading=true;
      try{
        const snapshot=await b.api('/api/workspaces/chat?chat_id='+encodeURIComponent(id));if(epoch!==x.activeEpoch)return;
        x.chat=snapshot;b.app.activeChatId=id;
        try{localStorage.setItem('society-active-chat',id);}catch(_){}
        b.experience.restoreWorkspaceState?.(snapshot.state || {});x.compose='';
        b.experience.hydrateGuide?.(snapshot.messages || []);
        if(view)b.app.view=view;else b.app.view=snapshot.state?.view || 'workspace';
        const ui=snapshot.state?.ui?.workspace || {};x.scope=['chat','project','all'].includes(ui.scope)?ui.scope:'chat';x.search=ui.search || '';x.collection=['all','behaviours','experiments'].includes(ui.collection)?ui.collection:'all';x.compose=ui.compose || '';x.activity=null;x.mentions=(ui.mentions || []).slice(0,8);x.mentionLabels=restoreLabels(ui.mention_labels);x.dockMentions=[];x.contextPreview=null;x.copy=(ui.copy_ref || ui.preview_copy_ref)?await readRecord(ui.copy_ref || ui.preview_copy_ref):null;x.copyFields=ui.copy_fields || {};x.dirty=false;x.conflict=false;
        x.loading=false;sidebar();await b.render();
      }finally{x.loading=false;}
    }
    async function initialize(){
      if(x.ready || x.loading)return;x.loading=true;
      try{
        await loadIndex();let id;
        try{id=localStorage.getItem('society-active-chat');}catch(_){}
        if(!chats().some(c=>c.id===id))id=x.index.default_chat_id;
        const snapshot=await b.api('/api/workspaces/chat?chat_id='+encodeURIComponent(id));x.chat=snapshot;b.app.activeChatId=id;
        // A new Village workspace never imports unrelated browser/session
        // selections into its saved scientific context.
        b.experience.restoreWorkspaceState?.(snapshot.state || {});
        const ui=x.chat.state?.ui?.workspace || {};x.scope=['chat','project','all'].includes(ui.scope)?ui.scope:'chat';x.search=ui.search || '';x.collection=['all','behaviours','experiments'].includes(ui.collection)?ui.collection:'all';x.compose=ui.compose || '';x.mentions=(ui.mentions || []).slice(0,8);x.mentionLabels=restoreLabels(ui.mention_labels);x.dockMentions=[];x.copy=(ui.copy_ref || ui.preview_copy_ref)?await readRecord(ui.copy_ref || ui.preview_copy_ref):null;x.copyFields=ui.copy_fields || {};
        b.experience.hydrateGuide?.(snapshot.messages || []);b.experience.state.onWorkspaceSave=notify;x.ready=true;sidebar();
      }finally{x.loading=false;}
    }
    function sidebar(){
      const el=document.getElementById('workspace-projects');if(!el || !x.index)return;
      const openProjects=new Set(Array.from(el.querySelectorAll?.('details[open][data-ws-project-id]') || []).map(node=>node.dataset.wsProjectId));
      el.innerHTML=`<div class="ws-nav-heading"><span>PROJECTS</span>${btn('+','data-ws-new="project" aria-label="New project"')}</div>${x.index.projects.map(p=>`<details class="ws-project" data-ws-project-id="${e(p.id)}" ${p.id===x.chat?.project_id || openProjects.has(p.id)?'open':''}><summary>${e(p.name)}<small>${p.chats?.length || 0}</small></summary>${(p.chats || []).map(c=>`<button class="ws-chat-link ${c.id===x.chat?.id?'active':''}" data-ws-chat="${e(c.id)}"><span>◌</span>${e(c.name)}</button>`).join('')}${btn('+ New chat',`data-ws-new="chat" data-ws-project="${e(p.id)}"`)}</details>`).join('')}`;
      const location=document.getElementById('workspace-location');if(location && x.chat)location.textContent=`${project()?.name || 'Project'} / ${x.chat.name}`;
      const title=document.querySelector('#guide-dock .guide-head h2');if(title && x.chat)title.textContent=x.chat.name;
    }
    function messageHtml(message){
      const meta=message.metadata || {},who=message.role==='user'?'You':meta.answer_source==='ai'?'Society guide':'Workspace';
      if(typeof GuideMessage==='object')return `<article class="ws-message ${e(message.role)}"><strong class="ws-speaker">${e(who)}</strong>${GuideMessage.render(message,{hostEmbeds:x.reportEmbeds?.get(message.id) || []})}</article>`;
      return `<article class="ws-message ${e(message.role)}"><strong>${e(who)}</strong><p>${e(message.content)}</p>${(meta.sources || []).filter(s=>['chat_context','workspace_chat_context'].includes(s.kind)).map(s=>`<button class="button-link" data-ws-citation="${e(s.chat_id)}" data-ws-revision="${s.chat_revision ?? s.revision}" data-ws-snapshot="${e(s.snapshot_hash)}">Read ${e(s.label || chatName(s.chat_id))} · revision ${s.chat_revision ?? s.revision}</button>`).join('')}</article>`;
    }
    async function prepareReports(){
      x.reportCache ||= new Map();x.reportEmbeds=new Map();const chatId=x.chat.id,epoch=x.activeEpoch;
      for(const message of (x.chat.messages || []).filter(m=>m.role==='assistant').slice(-8)){
        const guide=message.metadata?.guide_result || message.metadata || {},explicit=guide.updated_context?.result_ref || guide.result_context_ref,refs=[explicit,...(guide.sources || []).map(s=>s.object_ref || s.ref)].filter(r=>r && /^[A-Za-z0-9_.-]{1,200}$/.test(r.id) && Number.isSafeInteger(r.version) && r.version>0 && /^[a-f0-9]{64}$/.test(r.hash));
        const checked=new Set();for(const reference of refs){
          const key=stable(reference);if(checked.has(key))continue;checked.add(key);if(!x.reportCache.get(key)){try{const record=await readRecord(reference),village=['village_access_experiment','village_recovery_experiment'].includes(record.kind) && typeof SocietyExperience?.validVillageStudy==='function' && SocietyExperience.validVillageStudy(record),embed=record.kind==='dataset'?{type:'html_report',source_ref:pin(record),title:'AI Village observational analytics',scope:'Observational description of the exact retained posts. It is not an experiment; audience, tool state, influence and historical cause remain unknown.'}:village?{type:'html_report',source_ref:pin(record),title:'This experiment’s scientific results',scope:'Assigned interventions in the saved access world. The source, hypothesis and fidelity contract are part of this report; historical equivalence remains unestablished.'}:null;if(embed)x.reportCache.set(key,embed);else x.reportCache.delete(key);}catch(_){x.reportCache.delete(key);}}
          if(epoch!==x.activeEpoch || chatId!==x.chat.id)return;
          const embed=x.reportCache.get(key);if(embed && (embed.title==='AI Village observational analytics' || exact(reference,explicit))){x.reportEmbeds.set(message.id,[embed]);break;}
        }
      }
    }
    function quickTools(){return `<div class="ws-prompt-ideas"><span>You can ask:</span>${['Connect the AI Village data and discover patterns.','Help me design a controlled experiment.','Show an old experiment and replay it.'].map(text=>`<button data-ws-prompt="${e(text)}">${e(text)}</button>`).join('')}</div>`;}
    function toolFeed(){
      const events=x.activity?.events || [];if(!events.length)return '';
      const operations=[...new Map(events.map(row=>[row.request_id,row])).values()];
      const step=row=>`<article class="ws-tool-step ${e(row.phase)}"><span class="ws-tool-phase">${row.phase==='started'?'◌':row.phase==='failed'?'!':'✓'}</span><div><strong>${e(String(row.tool || 'Workspace tool').replace(/_/g,' '))}</strong><p>${e(row.summary || '')}</p>${(row.result_refs || []).slice(0,4).map(ref=>`<button class="button-link" data-ws-artifact="${e(ref.id)}" data-ws-version="${ref.version}" data-ws-hash="${e(ref.hash)}">Open saved ${e(ref.id.split('-')[0].replace(/_/g,' '))}</button>`).join('')}</div><small>${e(row.phase)}</small></article>`;
      return `<section class="ws-tool-feed" aria-label="Guide tool activity"><div class="ws-tool-title"><strong>The guide’s work</strong><span>Working summaries · actual tool activity</span></div>${operations.slice(-3).map(step).join('')}${operations.length>3?`<details><summary>${operations.length-3} earlier operations</summary>${operations.slice(0,-3).map(step).join('')}</details>`:''}<p class="exp-small">Each item records a tool invocation and its saved result or failure.</p></section>`;
    }
    function mentionChips(){return `<div class="ws-mention-chips" aria-label="Selected saved context">${x.mentions.map((m,i)=>`<span>${e(m.kind==='chat'?chatName(m.chat_id):(x.mentionLabels[stable(m)] || 'Saved item'))}${m.ref?' · v'+m.ref.version:''}<button type="button" data-ws-remove-mention="${i}" aria-label="Remove selected context ${i+1}">×</button></span>`).join('')}</div>`;}
    function forms(){
      if(!x.form)return '';
      const isProject=x.form.type==='project';
      return `<section class="journey-card ws-create"><h2>${isProject?'Create a project':'Start another chat'}</h2><form id="ws-create-form"><label class="field"><span>${isProject?'Project name':'Chat name'}</span><input id="ws-create-name" maxlength="120" required placeholder="${isProject?'What are you studying?':'What would you like to explore?'}"></label>${!isProject?`<label class="field"><span>Project</span><select id="ws-create-project">${x.index.projects.map(p=>`<option value="${e(p.id)}" ${p.id===(x.form.projectId || x.chat?.project_id)?'selected':''}>${e(p.name)}</option>`).join('')}</select></label>`:''}<div class="action-row">${btn(isProject?'Create project':'Create chat','type="submit"',true)}${btn('Cancel','type="button" data-ws-cancel')}</div></form></section>`;
    }
    async function workspace(){
      if(!x.ready)return header('YOUR LAB','Opening your projects.','Conversations and saved research stay together.');
      await prepareReports();
      const linked=await b.api('/api/workspaces/artifacts?scope=chat&chat_id='+encodeURIComponent(x.chat.id));
      x.visibleChatArtifacts=(linked.artifacts || []).filter(researchItem).reverse();
      return header(project()?.name || 'YOUR PROJECT',x.chat.name,'Explore an idea, open saved work, or ask your guide to bring context from another conversation.')+`<div class="ws-chat-toolbar"><span>Saved on this laptop${x.saving?' · Saving…':''}${x.conflict?' · Changes need review':''}</span><div>${btn('New chat','data-ws-new="chat"')}${btn('Copy this chat','data-ws-fork')}${btn('Project artifacts','data-view="artifacts"')}</div></div>${forms()}${quickTools()}${toolFeed()}${b.experience.state.guideBusy?'<p class="ws-guide-pending" role="status">The guide is reading your question and saved context… You can open another tool or chat while it works.</p>':''}<section class="ws-conversation" aria-label="Project conversation"><div class="ws-message-list">${(x.chat.messages || []).map(messageHtml).join('') || `<div class="ws-welcome"><h2>What would you like to understand?</h2><p>You can begin with a question, a source, an old experiment or another chat. Research can branch and return to earlier ideas.</p></div>`}</div>${mentionChips()}<form id="ws-compose"><label class="sr-only" for="ws-message">Message your Society guide</label><textarea id="ws-message" rows="3" maxlength="1600" placeholder="Ask your guide. Type @ to find a chat or saved artifact…" required>${e(x.compose)}</textarea>${btn(b.experience.state.guideBusy?'Reading…':'Send',`type="submit" ${b.experience.state.guideBusy?'disabled':''}`,true)}</form></section><section class="journey-card"><h2>Work linked to this conversation</h2><p>Sources, plans, environments and results keep their own saved identities. Reuse an item to attach it here; make a copy when you want a separate draft.</p><div class="ws-mini-artifacts">${(x.visibleChatArtifacts || []).slice(-8).reverse().map(a=>`<button data-ws-artifact="${e(a.ref.id)}" data-ws-version="${a.ref.version}" data-ws-hash="${e(a.ref.hash)}"><span>${e(a.kind.replace(/_/g,' '))}</span><strong>${e(a.title || a.name || a.kind.replace(/_/g,' '))}</strong><small>${e(a.relation)} · version ${a.ref.version}</small></button>`).join('') || '<p>No work is attached yet. Connect a source or choose a saved item.</p>'}</div>${btn('Browse all saved work','data-view="artifacts"')}</section><details class="ws-start-guide"><summary>One way to begin your first study</summary><p>Connect a source → explore a pattern → plan a comparison → build a world → run agents. Use these tools in any order as your question changes.</p></details>`;
    }
    async function projects(){return header('YOUR RESEARCH','Projects and conversations.','Keep several ideas open. Each chat remembers its own draft, selected sources and saved work.')+forms()+`<div class="action-row">${btn('New project','data-ws-new="project"',true)}${btn('New chat','data-ws-new="chat"')}</div><div class="ws-project-grid">${(x.index?.projects || []).map(p=>`<section class="journey-card"><h2>${e(p.name)}</h2>${(p.chats || []).map(c=>`<div class="ws-project-chat">${btn(c.name,`data-ws-chat="${e(c.id)}"`)}${btn('Read context',`data-ws-read="${e(c.id)}"`)}</div>`).join('')}${btn('+ New chat',`data-ws-new="chat" data-ws-project="${e(p.id)}"`)}</section>`).join('')}</div>`;}
    async function loadCatalog(){
      const params=new URLSearchParams({scope:x.scope});if(x.scope==='chat')params.set('chat_id',x.chat.id);if(x.scope==='project')params.set('project_id',x.chat.project_id);
      const packet=await b.api('/api/workspaces/artifacts?'+params);x.catalog=(packet.artifacts || []).filter(researchItem);x.catalogTotal=x.catalog.length;return {...packet,artifacts:x.catalog,edges:(packet.edges || []).filter(edge=>x.catalog.some(a=>exact(a.ref,edge.from_ref)) && x.catalog.some(a=>exact(a.ref,edge.to_ref)))};
    }
    function descriptor(a){
      const origin=chats().find(c=>c.id===(a.origin_chat_id || a.origin?.chat_id)),summary=a.summary || {};
      return {ref:a.ref,kind:a.kind,title:String(a.title || summary.name || a.kind.replace(/_/g,' ')).slice(0,240),summary:(typeof summary==='string'?summary:summary.question || summary.status || '').slice(0,1600),created_at:a.created_at || a.created || null,relation:a.relation || 'reference',origin:a.origin || (origin?{project_id:origin.project_id,project_name:origin.project_name,chat_id:origin.id,chat_name:origin.name}:undefined),capabilities:{open:true,replay:['dataset','observability_run',...RESULT_KINDS].includes(a.kind),reuse:Boolean(a.origin_chat_id || a.origin?.chat_id),copy:Boolean(a.origin_chat_id || a.origin?.chat_id)}};
    }
    async function artifacts(){
      const packet=await loadCatalog(),filter=x.search.toLowerCase();const matching=x.catalog.filter(a=>(x.collection==='all' || x.collection==='behaviours' && ['behavior','theory','behavior_rubric','rubric_measurement'].includes(a.kind) || x.collection==='experiments' && RESULT_KINDS.includes(a.kind)) && (!filter || [a.title,a.kind,typeof a.summary==='string'?a.summary:a.summary?.name,a.origin?.chat_name].join(' ').toLowerCase().includes(filter)));
      let starters='';if(x.collection==='behaviours'){try{const rubrics=await b.api('/api/rubrics');starters=`<details class="ws-rubric-start"><summary>Starter rubrics and Laya identifiers</summary><h2>Start with a clear question.</h2><p>These eight starter rubrics help the guide look for specific behaviour. They are proposed measures, awaiting validation. A text label does not prove an action or a cause.</p><div class="ws-saved-grid">${(rubrics.catalog || []).filter(r=>!filter || [r.title,r.question].join(' ').toLowerCase().includes(filter)).map(r=>`<article class="ws-saved-card"><span>${e(r.id)} · Starter rubric</span><h3>${e(r.title)}</h3><p>${e(r.question)}</p><details><summary>What evidence is needed?</summary><p>${e(r.opportunity)}</p><p><strong>Unknown:</strong> ${e(r.unknown)}</p></details>${btn('Discuss this with the guide',`data-ws-prompt="${e('Explain starter rubric '+r.id+' ('+r.title+') and suggest how we could test it using Laya. Ask which source I wish to use. Do not save or measure anything yet.')}"`)}</article>`).join('')}</div><p>Laya screens explicit text using a saved prompt. Unavailable inference stays unknown. Graph links help find the source context; they do not supply proof of influence.</p>${btn('Create a behaviour identifier','data-ws-prompt="Help me define a new prompt-based behaviour identifier. Ask what behaviour and source I want, then propose the opportunity, positive, negative and unknown rules before saving anything."')}</details>`;}catch(_){starters='<p>Starter rubrics are unavailable. Your saved research remains accessible.</p>';}}
      const latest=new Map();for(const item of matching){const previous=latest.get(item.ref.id);if(!previous || item.ref.version>previous.ref.version)latest.set(item.ref.id,item);}const visible=x.collection==='behaviours' && !filter?[...latest.values()]:matching;const shown=visible.slice(0,120),keys=new Set(shown.map(a=>stable(a.ref))),edges=(packet.edges || []).filter(edge=>keys.has(stable(edge.from_ref)) && keys.has(stable(edge.to_ref))).map(edge=>({...edge,relation:edge.relation==='recorded_reference'?'reference':edge.relation})).slice(0,1024);
      const title=x.collection==='behaviours'?'Behaviour library.':x.collection==='experiments'?'Your saved experiments.':'Find an idea, source or experiment.';
      const help=x.collection==='behaviours'?'Research saves a candidate here with its source and evidence. Software examples are excluded. AI Village candidates retain their actual source episodes. Experiments must model the proposed mechanism and disclose approximated and omitted state. The newest version of each item is shown. Ask the guide for evidence that supports or challenges a pattern, or for a new test. Candidate behaviours are not proven causes. Rubrics define what to look for; explanations propose why it happens. Older versions remain in Saved work and @ search.':x.collection==='experiments'?'Only source-grounded AI Village studies appear here. Each result keeps its hypothesis, source episode, world fidelity contract, fresh team runs and recorded outcome. Ask to compare, replay or replicate. Replaying uses saved events; a replication creates fresh teams.':'Read old work, link it to this chat, or ask your guide to make a separate copy.';
      const tabs=`<div class="ws-collection-tabs">${[['all','All saved work'],['behaviours','Behaviours'],['experiments','Experiments']].map(([key,label])=>btn(label,`data-ws-collection="${key}" aria-pressed="${x.collection===key}"`)).join('')}</div><p class="ws-collection-help">${help}</p>`;
      const controls=`<div class="ws-artifact-controls"><label>Look in<select id="ws-artifact-scope"><option value="chat" ${x.scope==='chat'?'selected':''}>This chat</option><option value="project" ${x.scope==='project'?'selected':''}>This project</option><option value="all" ${x.scope==='all'?'selected':''}>All projects</option></select></label><label>Find saved work<input id="ws-artifact-search" value="${e(x.search)}" placeholder="Search a title or type"></label><span>${shown.length} matching saved items · ${x.catalogTotal} in this scope</span></div>`;
      const cards=x.collection==='all'?'':`<div class="ws-saved-grid">${shown.map(a=>`<article class="ws-saved-card"><span>${e(a.kind==='behavior'?'Behaviour':a.kind==='theory'?'Proposed explanation':a.kind==='behavior_rubric'?'Prompt rubric':a.kind==='rubric_measurement'?'Text screen · unknown until verified':'Experiment')} · v${a.ref.version}</span><h2>${e(a.title || a.kind)}</h2><p>${e(typeof a.summary==='string'?a.summary:'Saved research')}</p><small>${e(a.origin?.project_name || 'Saved research')} / ${e(a.origin?.chat_name || 'Source chat')}</small><div>${btn(a.kind==='behavior' || a.kind==='theory'?'Explain and show evidence':'Explain the results',`data-ws-intent="explain" data-ws-artifact-ref="${e(a.ref.id)}" data-ws-version="${a.ref.version}" data-ws-hash="${e(a.ref.hash)}"`)}${RESULT_KINDS.includes(a.kind)?btn('Replay this run',`data-ws-intent="replay" data-ws-artifact-ref="${e(a.ref.id)}" data-ws-version="${a.ref.version}" data-ws-hash="${e(a.ref.hash)}"`):''}</div></article>`).join('')}</div>`;
      const board=`<div id="workspace-artifact-board">${typeof ArtifactMap==='object'?ArtifactMap.render({artifacts:shown.map(descriptor),edges}):shown.map(a=>btn(a.title || a.kind,`data-ws-artifact="${e(a.ref.id)}" data-ws-version="${a.ref.version}" data-ws-hash="${e(a.ref.hash)}"`)).join('')}</div>`;
      return header('SAVED WORK',title,'Open an old run without leaving your current draft behind. Every item keeps its origin and saved version.')+tabs+controls+cards+starters+(x.collection==='all'?board:`<details class="ws-start-guide"><summary>See how saved items connect</summary>${board}</details>`)+(matching.length>120?'<p>Showing the first 120 matching versions. Narrow your search to find older work.</p>':'')+(packet.truncated?'<p>This catalog is bounded. Narrow the scope to find older work.</p>':'');
    }
    async function showContext(source){
      const id=typeof source==='string'?source:source.chat_id;
      const revision=typeof source==='object'?(source.chat_revision ?? source.revision):null;
      const packet=await b.api('/api/workspaces/context?chat_id='+encodeURIComponent(id)+(revision!==null?'&revision='+revision:''));if(typeof source==='object' && source.snapshot_hash && source.snapshot_hash!==packet.snapshot_hash)throw new Error('The saved conversation fingerprint does not match this citation.');x.contextPreview=packet;
      const d=document.getElementById('evidence-dialog');d.querySelector('h2').textContent=packet.name || chatName(id);d.querySelector('.eyebrow').textContent='READING ANOTHER CONVERSATION';
      const changed=typeof source==='object' && (source.snapshot_hash && source.snapshot_hash!==packet.snapshot_hash || (source.chat_revision ?? source.revision) && (source.chat_revision ?? source.revision)!==packet.revision);
      document.getElementById('dialog-body').innerHTML=`<p>Read-only context from ${e(packet.project_name || chats().find(c=>c.id===id)?.project_name || 'another project')} · revision ${packet.revision}. This discussion is context, not experimental evidence.</p>${changed?'<p>The conversation has changed since this citation. This is the current saved snapshot.</p>':''}<div class="ws-context-messages">${(packet.messages || []).map(messageHtml).join('')}</div><h3>Referenced work</h3>${(packet.artifacts || []).slice(-16).reverse().map(a=>`<div class="ws-project-chat"><strong>${e(a.title || a.kind)}</strong>${btn('Reuse here',`data-ws-reuse="${e(a.ref.id)}" data-ws-version="${a.ref.version}" data-ws-hash="${e(a.ref.hash)}" data-ws-origin="${e(id)}"`)}</div>`).join('')}<div class="action-row">${btn('Open this chat',`data-ws-chat="${e(id)}"`)}${btn('Copy this chat',`data-ws-fork="${e(id)}"`)}</div>`;d.showModal();
    }
    async function requestArtifactAction(mode,reference,originId=null){const item=x.catalog.find(a=>exact(a.ref,reference));await b.experience.ask(`${mode==='copy'?'Make a separate editable copy of':'Reuse the exact saved'} artifact mentioned here in this chat. ${mode==='copy'?'Keep the original unchanged and open the copy.':'Link it here and keep its original saved identity.'}`,{mentioned_context:[{kind:'artifact',ref:reference,...((originId || item?.origin?.chat_id)?{origin_chat_id:originId || item.origin.chat_id}:{})}]});}
    async function artifactAction(mode,ref,originId=null,requestId=null){
      if(x.operation)return;x.operation=true;try{return await performArtifactAction(mode,ref,originId,requestId);}finally{x.operation=false;}
    }
    async function performArtifactAction(mode,ref,originId=null,requestId=null){
      const artifact=x.catalog.find(a=>exact(a.ref,ref)) || x.chat.artifacts.find(a=>exact(a.ref,ref));const origin=originId || artifact?.origin_chat_id || artifact?.origin?.chat_id || x.chat.id;
      if(mode==='reuse' || mode==='copy'){
        const targetId=x.chat.id,epoch=x.activeEpoch;await flush();const reply=await post({op:mode==='reuse'?'reuse_artifact':'clone_artifact',artifact_ref:ref,origin_chat_id:origin,target_chat_id:targetId,...(requestId?{request_id:requestId}:{})});if(epoch!==x.activeEpoch)return reply;
        await refreshChat();b.toast(mode==='reuse'?'The exact saved item is linked to this chat.':'A separate editable copy is saved here. The original is unchanged.');
        if(mode==='copy'){const draftRef=reply.draft_ref || reply.artifact_ref || reply.ref;if(draftRef)await openArtifact(draftRef);}
        await b.render();return reply;
      }
      return openArtifact(ref,mode);
    }
    async function openArtifact(ref,mode='open',messageId=null){
      const record=await readRecord(ref);
      if(record.kind==='workspace_draft'){x.copy=record;x.copyFields={};b.app.view='workspace-copy';notify();await b.render();return;}
      if(b.experience.openSavedArtifact && (['dataset','observability_run','village_incident','guided_plan','guided_simulator','guided_result',...RESULT_KINDS].includes(record.kind))){await b.experience.openSavedArtifact(record,mode,messageId);notify();return;}
      await b.openObject(record.id,record.version);
    }
    async function copyView(){
      const r=x.copy,p=r?.payload;if(!p)return workspace();const fields={...(p.editable_fields || p.fields || {}),...x.copyFields};
      return header('EDITABLE COPY',p.name || 'A separate research draft','This is a new draft linked to its original saved item. It carries no new experimental outcome or verification.')+`<section class="journey-card"><div class="ws-copy-intro"><p>${e(fields.question || fields.notes || 'A separate working draft, ready for your guide.')}</p>${btn('Ask the guide to edit this draft','data-ws-prompt="Help me edit the current working copy. Ask what I would like to change. Do not run an experiment yet."',true)}${fields.control_text!==undefined?btn('Plan a new experiment from this copy','data-ws-prompt="Create a new experiment plan from this current working copy. Keep its question and notes, use two teams per condition, six rounds, valid probability 0.35, and assignment seed 61006. Keep the original unchanged. Save and show the new plan, but do not build or run it yet."'):''}</div><details class="ws-copy-fields"><summary>Inspect draft fields</summary><form id="ws-copy-form"><label class="field"><span>Draft name</span><input id="ws-copy-name" value="${e(x.copyFields.name ?? p.name ?? '')}" maxlength="120"></label><label class="field"><span>Your notes</span><textarea id="ws-copy-notes" rows="6" maxlength="2000">${e(fields.notes || p.notes || '')}</textarea></label>${fields.question!==undefined?`<label class="field"><span>Question</span><textarea id="ws-copy-question" maxlength="2000">${e(fields.question)}</textarea></label>`:''}${fields.control_text!==undefined?`<label class="field"><span>Neutral note</span><textarea id="ws-copy-control" maxlength="2000">${e(fields.control_text)}</textarea></label><label class="field"><span>Intervention note</span><textarea id="ws-copy-treatment" maxlength="2000">${e(fields.treatment_text || '')}</textarea></label>`:''}<div class="action-row">${btn('Save copy','type="submit"',true)}${fields.control_text!==undefined?btn('Use this as an experiment draft','type="button" data-ws-adopt-copy'):''}</div></form></details><details><summary>Where this copy came from</summary><p>${e((p.source_ref || p.original_source_ref)?.id || 'Exact source retained in the saved record')} · version ${(p.source_ref || p.original_source_ref)?.version || '?'}</p>${btn('Inspect the original','data-ws-original-copy')}</details></section>`;
    }
    async function refreshChat(){
      if(!x.chat)return;const id=x.chat.id,epoch=x.activeEpoch;
      const fresh=await b.api('/api/workspaces/chat?chat_id='+encodeURIComponent(id));
      if(epoch!==x.activeEpoch || id!==x.chat.id)return;
      if(!x.dirty && !x.saving)x.chat=fresh;else{x.chat.messages=fresh.messages;x.chat.artifacts=fresh.artifacts;}
      b.experience.hydrateGuide?.(fresh.messages || []);sidebar();
    }
    async function afterGuide(answer,originChat){if(originChat===x.chat?.id){await refreshChat();if(['workspace','home'].includes(b.app.view))await b.render();}await loadIndex();}
    async function applyGuideAction(action){
      if(action.type==='open_chat'){await loadChat(action.chat_id,{view:'workspace'});return true;}
      if(['reuse_artifact','clone_artifact'].includes(action.type)){if(action.target_chat_id!==x.chat?.id)throw new Error('The target conversation changed. Ask again in the intended chat.');await artifactAction(action.type==='reuse_artifact'?'reuse':'copy',action.artifact_ref || action.object_ref,action.origin_chat_id,action.workspace_request_id);return true;}
      if(action.type==='fork_chat'){await fork(action.origin_chat_id,action.expected_revision,action.project_id,action.workspace_request_id);return true;}
      return false;
    }
    async function fork(id=x.chat.id,revision=null,projectId=x.chat.project_id,requestId=null){
      await flush();const source=id===x.chat.id?x.chat:await b.api('/api/workspaces/chat?chat_id='+encodeURIComponent(id));
      const response=await post({op:'fork_chat',origin_chat_id:id,expected_revision:revision ?? source.revision,name:(source.name+' · copy').slice(0,120),project_id:projectId,...(requestId?{request_id:requestId}:{})});await loadIndex();await loadChat(response.chat_id || response.chat?.id || response.id,{view:'workspace',skipSave:true});b.toast('This chat is a separate branch. Its source references stay exact.');
    }
    async function click(target){
      if(target.hasAttribute('data-view') && ['workspace','home'].includes(target.dataset.view)){await refreshChat();return false;}
      if(target.hasAttribute('data-ws-collection')){x.collection=target.dataset.wsCollection;x.scope='all';x.search='';b.app.view='artifacts';notify();await b.render();return true;}
      if(target.hasAttribute('data-ws-intent')){const reference={id:target.dataset.wsArtifactRef,version:Number(target.dataset.wsVersion),hash:target.dataset.wsHash},item=x.catalog.find(a=>exact(a.ref,reference));await b.experience.ask(target.dataset.wsIntent==='replay'?'Replay the exact saved experiment mentioned here. Keep my current draft unchanged.':'Explain the saved item mentioned here in simple terms. Show its evidence and what remains uncertain. Do not run or change anything.',{mentioned_context:[{kind:'artifact',ref:reference,...(item?.origin?.chat_id?{origin_chat_id:item.origin.chat_id}:{})}]});return true;}
      if(target.hasAttribute('data-ws-remove-mention')){x.mentions.splice(Number(target.dataset.wsRemoveMention),1);notify();await b.render();return true;}
      if(target.hasAttribute('data-ws-prompt')){await b.experience.ask(target.dataset.wsPrompt);return true;}
      if(target.hasAttribute('data-ws-new')){x.form={type:target.dataset.wsNew,projectId:target.dataset.wsProject};b.app.view='projects';await b.render();return true;}
      if(target.hasAttribute('data-ws-cancel')){x.form=null;await b.render();return true;}
      if(target.hasAttribute('data-ws-chat')){document.getElementById('evidence-dialog')?.close();await loadChat(target.dataset.wsChat,{view:'workspace'});return true;}
      if(target.hasAttribute('data-ws-citation')){await showContext({chat_id:target.dataset.wsCitation,chat_revision:Number(target.dataset.wsRevision),snapshot_hash:target.dataset.wsSnapshot});return true;}
      if(target.hasAttribute('data-ws-read')){await showContext(target.dataset.wsRead);return true;}
      if(target.hasAttribute('data-ws-fork')){const sourceId=target.dataset.wsFork || x.chat.id;await flush();const source=await b.api('/api/workspaces/chat?chat_id='+encodeURIComponent(sourceId));document.getElementById('evidence-dialog')?.close();await b.experience.ask('Fork the mentioned chat into a separate discussion branch in my current project. Open the new branch and keep its original saved references. Do not run an experiment.',{mentioned_context:[{kind:'chat',chat_id:sourceId,revision:source.revision,snapshot_hash:source.snapshot_hash}]});return true;}
      const ref={id:target.dataset.wsArtifact || target.dataset.wsReuse,version:Number(target.dataset.wsVersion),hash:target.dataset.wsHash};
      if(target.hasAttribute('data-ws-artifact')){await openArtifact(ref,'open',target.dataset.wsMessage || null);return true;}
      if(target.hasAttribute('data-ws-reuse')){document.getElementById('evidence-dialog')?.close();await requestArtifactAction('reuse',ref,target.dataset.wsOrigin);return true;}
      if(target.hasAttribute('data-ws-adopt-copy')){if(x.operation)return true;x.operation=true;try{if(await saveCopy()){await b.experience.adoptWorkspaceDraft(x.copy);notify();await b.render();}}finally{x.operation=false;}return true;}
      if(target.hasAttribute('data-ws-original-copy')){await openArtifact(x.copy.payload.source_ref || x.copy.payload.original_source_ref);return true;}
      return false;
    }
    async function saveCopy(){
      const epoch=x.activeEpoch,chatId=x.chat.id,original=pin(x.copy);
      const fields={name:document.getElementById('ws-copy-name')?.value || x.copy.payload.name,notes:document.getElementById('ws-copy-notes')?.value || ''};
      for(const [id,key]of [['ws-copy-question','question'],['ws-copy-control','control_text'],['ws-copy-treatment','treatment_text']]){const el=document.getElementById(id);if(el)fields[key]=el.value;}
      const reply=await post({op:'update_draft',chat_id:chatId,draft_ref:original,fields});const saved=await readRecord(reply.draft_ref || reply.artifact_ref || reply.ref);if(epoch!==x.activeEpoch || chatId!==x.chat.id || !exact(original,x.copy))return false;x.copy=saved;x.copyFields={};notify();await refreshChat();b.toast('Your separate draft is saved.');return true;
    }
    async function submit(event){
      if(event.target.id==='ws-compose'){event.preventDefault();const el=document.getElementById('ws-message'),message=el.value.trim();if(!message)return true;el.value='';x.compose='';notify();await flush();const mentions=x.mentions.map(clone);x.mentions=[];await b.experience.ask(message,{mentioned_context:mentions});return true;}
      if(event.target.id==='ws-create-form'){
        event.preventDefault();if(x.operation)return true;x.operation=true;try{const name=document.getElementById('ws-create-name').value.trim();if(!name)return true;
        let projectId=document.getElementById('ws-create-project')?.value || x.chat?.project_id;
        if(x.form.type==='project'){const reply=await post({op:'create_project',name});projectId=reply.project_id || reply.project?.id || reply.id;}
        const reply=await post({op:'create_chat',project_id:projectId,name:x.form.type==='project'?'First conversation':name});x.form=null;await loadIndex();await loadChat(reply.chat_id || reply.chat?.id || reply.id,{view:'workspace'});return true;}finally{x.operation=false;}
      }
      if(event.target.id==='ws-copy-form'){event.preventDefault();if(x.operation)return true;x.operation=true;try{if(await saveCopy())await b.render();}finally{x.operation=false;}return true;}
      return false;
    }
    async function change(target){if(target.id==='ws-artifact-scope'){x.scope=target.value;await b.render();return true;}return false;}
    function input(target){if(target.id==='ws-message')x.compose=target.value;const copyKey=({'ws-copy-name':'name','ws-copy-notes':'notes','ws-copy-question':'question','ws-copy-control':'control_text','ws-copy-treatment':'treatment_text'})[target.id];if(copyKey)x.copyFields[copyKey]=target.value;if(target.id==='ws-artifact-search'){x.search=target.value;clearTimeout(x.searchTimer);x.searchTimer=setTimeout(()=>b.render(),200);return true;}return false;}
    async function searchMentions(query){
      if(!x.mentionCatalog || Date.now()-x.mentionCatalog.time>15000){const [index,catalog]=await Promise.all([b.api('/api/workspaces'),b.api('/api/workspaces/artifacts?scope=all')]);x.mentionCatalog={time:Date.now(),index,catalog};}
      const {index,catalog}=x.mentionCatalog,q=query.toLowerCase();const items=[];
      for(const p of index.projects)for(const c of p.chats || [])if([p.name,c.name].join(' ').toLowerCase().includes(q))items.push({type:'chat',label:c.name,project_name:p.name,chat_name:c.name,chat_id:c.id});
      for(const a of (catalog.artifacts || []).filter(researchItem))if([a.title,a.kind,a.ref?.id,a.origin?.project_name,a.origin?.chat_name].join(' ').toLowerCase().includes(q))items.push({type:'artifact',label:String(a.title || a.kind.replace(/_/g,' ')).slice(0,240),project_name:a.origin?.project_name || 'Saved research',chat_name:a.origin?.chat_name || 'Source chat',chat_id:a.origin?.chat_id,ref:a.ref});
      return {items:items.slice(0,20),total:items.length,truncated:items.length>20 || catalog.truncated};
    }
    function mount(view){
      sidebar();document.body.dataset.workspaceChat=['workspace','home'].includes(view)?'true':'false';
      const live=document.getElementById('guide-activity');if(live){const recent=[...new Map((x.activity?.events || []).map(row=>[row.request_id,row])).values()].slice(-3);live.innerHTML=typeof GuideMessage==='object' && !['workspace','home'].includes(view) && recent.length?GuideMessage.render('',{liveEvents:recent}):'';}
      if(['artifacts','library','experiments'].includes(view) && typeof ArtifactMap==='object')x.board=ArtifactMap.attach(document.getElementById('workspace-artifact-board'),{onOpen:r=>openArtifact(r),onReplay:r=>openArtifact(r,'replay'),onReuse:r=>requestArtifactAction('reuse',r),onCopy:r=>requestArtifactAction('copy',r)});
      if(typeof WorkspaceMentions==='object'){
        const input=document.getElementById('ws-message') || document.getElementById('guide-input');
        if(input)x.mentionCleanup=WorkspaceMentions.attach(input,{search:searchMentions,onSelect:item=>{
          const value=item.type==='chat'?{kind:'chat',chat_id:item.chat_id}:{kind:'artifact',ref:item.ref,...(item.chat_id?{origin_chat_id:item.chat_id}:{})};const selected=input.id==='ws-message'?x.mentions:x.dockMentions;
          if(selected.length<8 && !selected.some(m=>stable(m)===stable(value)))selected.push(value);x.mentionLabels[stable(value)]=item.label;
          if(input.id==='ws-message'){x.compose=input.value;notify();const holder=document.querySelector('.ws-mention-chips');if(holder)holder.outerHTML=mentionChips();}
        },onChange:value=>{if(input.id==='ws-message'){x.compose=value;notify();}}});
      }
    }
    function dispose(){x.board?.();x.board=null;x.mentionCleanup?.();x.mentionCleanup=null;}
    async function update(){if(!x.ready || x.loading || Date.now()-x.lastPoll<5000)return false;x.lastPoll=Date.now();const revision=x.chat?.revision,activityStamp=stable(x.activity),origin=x.chat.id,epoch=x.activeEpoch;await loadIndex();try{const packet=await b.api('/api/guide/activity?chat_id='+encodeURIComponent(origin));if(epoch===x.activeEpoch)x.activity=packet;}catch(_){}if(!x.dirty && !x.saving)await refreshChat();return revision!==x.chat?.revision || activityStamp!==stable(x.activity);}
    return {initialize,hasView:view=>['workspace','home','overview','projects','artifacts','library','experiments','workspace-copy'].includes(view),render:view=>({workspace,home:workspace,overview:workspace,projects,artifacts,library:()=>{if(x.collection!=='behaviours'){x.collection='behaviours';x.scope='all';x.search='';}return artifacts();},experiments:()=>{if(x.collection!=='experiments'){x.collection='experiments';x.scope='all';x.search='';}return artifacts();},'workspace-copy':copyView}[view])(),click,submit,change,input,mount,dispose,notify,flush,sidebar,update,loadChat,showContext,applyGuideAction,afterGuide,refreshChat,openArtifact,consumeDockMentions:()=>{const selected=clone(x.dockMentions);x.dockMentions=[];return selected;},mentionOpen:()=>x.mentionCleanup?.getState()?.open===true,state:x};
  }
  scope.LabWorkspace={create,exact};if(typeof module!=='undefined')module.exports=scope.LabWorkspace;
})(typeof globalThis==='undefined'?window:globalThis);
