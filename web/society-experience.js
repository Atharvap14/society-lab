/* The approachable front door. Existing research tools remain available below it. */
(function(scope) {
  'use strict';
  const escape = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const DEMO = Object.freeze({id:'dataset-5d2eef17db31',version:1,hash:'4351ceeb788cc000b6e288927299f20d68095e9a449a47bb6cef5e0791cc5c41'});
  const PRIMARY = ['home','workspace','projects','artifacts','workspace-copy','connect','brief','plan','simulator','watch','try','findings','import'];
  const STUDIES = ['village_access_experiment','village_recovery_experiment'];
  const EXCLUDED_STUDIES = ['experiment','network_experiment','complementary_experiment','resource_experiment','timed_resource_experiment','revision_relay_experiment'];
  function sameRef(record,ref) { return record && record.id===ref?.id && record.version===ref.version && record.hash===ref.hash; }
  function ref(record) { return {id:record.id,version:record.version,hash:record.hash}; }
  function short(text,n=160) { text=String(text || ''); return text.length>n ? text.slice(0,n)+'…' : text; }
  function studyName(kind) { return kind==='village_recovery_experiment'?'Single-document reference recovery':kind==='village_access_experiment'?'Document access and repair':'Source-grounded team test'; }
  function isRecovery(record){return record?.kind==='village_recovery_experiment' || record?.payload?.family==='single_document_reference_repair';}
  function primaryKey(record){return isRecovery(record)?'verified_repaired_reference':'verified_usable_project';}
  function validVillageStudy(record){
    const p=record?.payload,protocol=p?.protocol,source=p?.source_refs?.dataset_ref,ground=protocol?.grounding,f=p?.fidelity,h=p?.hypothesis;
    const exactRef=r=>r && Object.keys(r).length===3 && typeof r.id==='string' && /^[A-Za-z0-9_.-]{1,200}$/.test(r.id) && Number.isSafeInteger(r.version) && r.version>0 && typeof r.hash==='string' && /^[a-f0-9]{64}$/.test(r.hash);
    const list=v=>Array.isArray(v) && v.length<=64 && v.every(x=>typeof x==='string' && x.length>0 && x.length<=4000);
    return Boolean(STUDIES.includes(record?.kind) && p?.agent_mode==='live' && protocol?.environment?.kind===(isRecovery(record)?'single_document_reference_repair':'village_document_access_repair') && (!isRecovery(record) || protocol?.primary_outcome==='verified_repaired_reference') && exactRef(source) && exactRef(ground?.source_ref) && sameRef(source,ground.source_ref) && list(ground?.evidence_ids) && ground.evidence_ids.length>0 && typeof h?.statement==='string' && h.statement.trim() && h.statement.length<=4000 && protocol?.hypothesis?.statement===h.statement && f?.historical_equivalence===false && protocol?.fidelity?.historical_equivalence===false && ['represented','approximated','omitted'].every(k=>list(f[k]) && JSON.stringify(f[k])===JSON.stringify(protocol.fidelity[k])) && f.represented.length>0);
  }
  function studyContract(record) {
    const p=record?.payload || {}, protocol=p.protocol || {}, fidelity=p.fidelity || protocol.fidelity || {};
    const source=p.source_refs?.dataset_ref || protocol.grounding?.source_ref || null;
    const hypothesis=p.hypothesis || protocol.hypothesis || {};
    const words=value=>Array.isArray(value)?value.filter(v=>typeof v==='string').slice(0,24).map(v=>v.slice(0,1000)):[];
    const evidence=protocol.grounding?.evidence_ids || hypothesis.source_evidence_ids;
    return {source_ref:source,hypothesis:typeof hypothesis.statement==='string'?hypothesis.statement:protocol.research_question || p.question || 'No source-linked hypothesis was recorded.',
      evidence_ids:Array.isArray(evidence)?evidence.filter(v=>typeof v==='string').slice(0,64):[],
      represented:words(fidelity.represented),approximated:words(fidelity.approximated),omitted:words(fidelity.omitted),
      objective:p.objective || protocol.objective || (isRecovery(record)?'Verified peer access to the original':'Verified usable project'),
      historical_equivalence:false};
  }
  function armFacts(record) {
    const p=record?.payload || {}, arms=p.analysis?.arms;
    if(!STUDIES.includes(record?.kind) || !arms || !Array.isArray(p.runs))return [];
    const keys=['neutral_note','canonical_check'];
    return keys.filter(k=>arms[k]).map(k=>{
      const runs=p.runs.filter(r=>r.arm===k), scores=runs.map(r=>r.outcomes?.[primaryKey(record)]);
      const valid=scores.every(n=>n===0 || n===1) && scores.length===arms[k].n && scores.length>0;
      return {key:k,label:({neutral_note:'Neutral note',canonical_check:isRecovery(record)?'Check the canonical reference':'Check canonical project access'})[k],n:runs.length,correct:valid?scores.reduce((a,b)=>a+b,0):null};
    });
  }
  function documentProgress(record) {
    if(!STUDIES.includes(record?.kind) || !Array.isArray(record.payload?.runs))return '';
    const total=isRecovery(record)?1:4;
    const fields=['content_correct','checker_current_profile_authorized','checker_opened_current_version'];
    const rows=record.payload.runs.slice(0,100).map((run,i)=>{
      const docs=run.outcomes?.per_document,valid=Array.isArray(docs) && docs.length===total && docs.every(d=>d && typeof d.document_key==='string') && new Set(docs.map(d=>d.document_key)).size===total;
      const count=key=>valid && docs.every(d=>typeof d[key]==='boolean')?`${docs.filter(d=>d[key]).length} / ${total}`:'Unknown';
      const cell=value=>typeof value==='boolean'?(value?'Yes':'No'):'Unknown';
      const detail=valid?`<details><summary>Each document</summary><table><thead><tr><th>Original document</th><th>Correct content</th><th>Checker has access</th><th>Checker opened final version</th></tr></thead><tbody>${docs.map(d=>`<tr><td>${escape(d.document_key)}</td>${fields.map(k=>`<td>${cell(d[k])}</td>`).join('')}</tr>`).join('')}</tbody></table></details>`:'Per-document checks are unavailable.';
      return `<tr><td>Team ${i+1} · ${escape(({neutral_note:'Neutral',canonical_check:'Canonical check'})[run.arm] || run.arm)}</td>${fields.map(k=>`<td>${count(k)}</td>`).join('')}<td>${detail}</td></tr>`;
    }).join('');
    return `<section class="journey-card"><h3>What progress did the teams make?</h3><p>These saved per-document measures explain the strict goal. Correct content and permissions are separate from an executed final-version open. They do not prove reading or comprehension.</p><div style="overflow-x:auto"><table><thead><tr><th>Team</th><th>Correct originals</th><th>Checker access</th><th>Checker opened final version</th><th>Details</th></tr></thead><tbody>${rows}</tbody></table></div><p class="exp-small">No new run or outcome definition is created by this view. Missing checks stay Unknown.</p></section>`;
  }
  function villageChecks(record,proof,claims) {
    const p=record?.payload, replay=proof?.payload, checked=claims?.payload, runs=p?.runs, facts=checked?.facts;
    if(!validVillageStudy(record) || p.status!=='complete' || !Array.isArray(runs) || !runs.length
      || replay?.status!=='passed' || replay.analysis_recomputed!==true || replay.paid_calls!==0
      || !sameRef(record,replay.experiment_ref) || checked?.status!=='passed' || checked.paid_calls!==0
      || !sameRef(record,checked.experiment_ref) || !Array.isArray(replay.checks) || replay.checks.length!==runs.length
      || !facts || facts.team_count!==runs.length)return false;
    const ids=new Set(),checks=new Map();let decisions=0;
    for(const row of replay.checks){if(!row || typeof row.run_id!=='string' || checks.has(row.run_id) || row.passed!==true || !Number.isSafeInteger(row.steps) || row.steps<0)return false;checks.set(row.run_id,row);}
    for(const run of runs){if(typeof run.run_id!=='string' || ids.has(run.run_id) || run.status!=='complete' || !Array.isArray(run.turns) || checks.get(run.run_id)?.steps!==run.turns.length)return false;ids.add(run.run_id);decisions+=run.turns.length;}
    return p.analysis?.primary_effect && typeof p.analysis.primary_effect==='object' && facts.primary_effect && typeof facts.primary_effect==='object'
      && facts.subject_decisions===decisions && ['neutral_note','canonical_check'].every(arm=>{
        const selected=runs.filter(r=>r.arm===arm);
        if(!isRecovery(record))return facts.arm_counts?.[arm]===selected.length;
        const saved=facts.arm_counts?.[arm],scores=selected.map(r=>r.outcomes?.verified_repaired_reference);
        return saved && Object.keys(saved).length===2 && Number.isSafeInteger(saved.total) && saved.total===selected.length && Number.isSafeInteger(saved.correct) && scores.every(n=>Number.isSafeInteger(n) && (n===0 || n===1)) && saved.correct===scores.reduce((a,b)=>a+b,0);
      })
      && JSON.stringify(facts.primary_effect)===JSON.stringify(p.analysis?.primary_effect);
  }
  function create(b) {
    const x={project:null,window:'demo',record:null,replayRecord:null,replayStates:new Map(),replayKey:'',guided:false,tour:0,study:null,
      tryKind:'artifact',practiceJob:null,practiceResult:null,importName:'my-team.jsonl',importContent:'',importBusy:false,exampleBusy:false,practiceBusy:false,guideBusy:false,
      chat:[],guideMounted:false,guideOpen:false,guideHistory:[],guideBudget:null,guideRequest:0,runIndex:0,watchStudy:null,resultGuideContext:null};
    let cleanup=null;
    const e=b.esc || escape;
    const button=(text,attrs='',primary=false)=>`<button class="button ${primary?'primary':''}" ${attrs}>${e(text)}</button>`;
    const hasDemo=()=>b.app.state?.objects.some(r=>sameRef(r,DEMO));
    const datasets=()=>b.all('dataset');
    const openedStudies=new Map();
    const studies=()=>[...new Map([...b.app.state.objects.filter(r=>STUDIES.includes(r.kind) && r.summary?.agent_mode==='live'),...openedStudies.values()].map(r=>[`${r.id}@${r.version}:${r.hash}`,r])).values()];
    const projectName=r=>r?.payload?.provenance?.original_name || (r?.id===DEMO.id?'AI Village · Saved week':r?.payload?.provenance?.origin==='authored_example'?'Authored practice chat':'Saved team chat');
    const stepPath=active=>`<div class="exp-path" aria-label="Your research journey">${[['connect','Connect'],['brief','Discover'],['plan','Plan'],['simulator','Simulate'],['findings','Results']].map(([v,label],i)=>`<button data-view="${v}" class="${active===v?'current':''}"><span>${i+1}</span>${label}</button>${i<4?'<span class="exp-path-arrow" aria-hidden="true">→</span>':''}`).join('')}</div>`;
    const heading=(tag,title,text,active)=>`${active?stepPath(active):''}<div class="exp-heading"><span class="eyebrow">${e(tag)}</span><h1>${e(title)}</h1><p>${e(text)}</p></div>`;
    async function read(source,kind) {
      if(!source)throw new Error('Choose a saved source first.');
      const record=await b.object(source.id,source.version);
      if(!sameRef(record,source) || (kind && record.kind!==kind))throw new Error('This saved version is unavailable. Please choose another source.');
      return record;
    }
    function sourceDetails(record,text='Source details') {
      return `<details class="exp-source"><summary>${e(text)}</summary><p>Saved version ${record.version}. Opening this view does not change it.</p><code>${e(record.id)} · ${e(record.hash)}</code>${button('Inspect saved record',`data-exp-inspect="${e(record.id)}" data-exp-version="${record.version}"`)}</details>`;
    }
    function contractPanel(record){
      const c=studyContract(record),active=x.project,matched=sameRef(c.source_ref,active),list=values=>values.length?`<ul>${values.map(v=>`<li>${e(v)}</li>`).join('')}</ul>`:'<p>Not recorded. Do not assume this state is represented.</p>';
      const relationship=c.source_ref?(active && !matched?'This Village study uses a different saved source episode.':'Source-grounded task analogue. Historical equivalence remains unestablished.'):'The source relationship was not recorded. Do not treat this as a result for the selected observation.';
      return `<section class="journey-card"><span class="eyebrow">SOURCE-GROUNDED FEASIBILITY TEST</span><h3>${isRecovery(record)?'Can an exact reference help the peer open the original?':'Can a canonical access check help the team finish?'}</h3><p>${isRecovery(record)?'We measure whether the assigned peer actually opens the one current original. Both conditions have the same clear goal.':'We measure verified usable projects under the saved tool and action budget.'} The original hidden account state is not recreated.</p><p><strong>Source:</strong> ${c.source_ref?`${e(c.source_ref.id)} · version ${e(c.source_ref.version)} ${button('Open this source',`data-exp-inspect="${e(c.source_ref.id)}" data-exp-version="${e(c.source_ref.version)}"`)}`:'No exact source episode pin was recorded.'}</p><details><summary>How this world connects to AI Village</summary><p>${e(relationship)}</p><h3>Exact saved research question</h3><p>${e(c.hypothesis)}</p><p><strong>Saved objective:</strong> ${e(c.objective)}</p>${c.evidence_ids.length?`<details><summary>Cited source records</summary><p>${c.evidence_ids.map(e).join(' · ')}</p></details>`:''}<div class="journey-comparison"><article><h3>What the world represents</h3>${list(c.represented)}</article><article><h3>What it approximates</h3>${list(c.approximated)}</article><article><h3>What it leaves out</h3>${list(c.omitted)}</article></div><p class="exp-small">A replay or outcome check validates this execution record. It does not validate the historical explanation or simulator fidelity.</p></details></section>`;
    }
    function tourPanel(active) {
      if(!x.guided)return '';
      const steps=[['Watch the team','Press Play, or move the timeline. Click an agent to focus on their messages.'],['Test a question','A chat can raise a question. A fresh team test helps us check one possible explanation.'],['Read the result','Count teams that finished correctly. Keep the result tied to this task and these agents.']];
      const index=({watch:0,try:1,findings:2})[active] ?? x.tour;
      const [title,text]=steps[index];
      return `<section class="exp-tour" aria-label="Guided demo"><div class="exp-tour-count">${index+1}<small>of 3</small></div><div><span class="eyebrow">YOUR THREE-MINUTE DEMO</span><h2>${e(title)}</h2><p>${e(text)}</p></div><div class="exp-tour-actions">${index?button('Back',`data-exp-tour="${index-1}"`):''}${button(index===2?'Finish demo':'Next →',`data-exp-tour="${index+1}"`,true)}${button('Exit walkthrough','data-exp-exit')}</div></section>`;
    }
    function previewScene(record) {
      const messages=Array.isArray(record?.payload?.messages)?record.payload.messages:[],names=[...new Set(messages.filter(m=>m.speaker_type==='agent' && typeof m.agent_name==='string').map(m=>m.agent_name))].slice(0,8);
      return `<section class="exp-project-summary"><span class="eyebrow">RECORDED AI VILLAGE SOURCE</span><h2>Begin with the actual agent society.</h2>${names.length?`<p>${names.map(e).join(' · ')}</p><p>${messages.length} retained posts. Tasks, account history and reading remain unknown unless separately recorded.</p>`:'<p>Connect the retained Village source to see its recorded participants.</p>'}</section>`;
    }
    async function home() {
      const source=hasDemo()?await read(DEMO,'dataset'):null;
      const steps=[['connect','01','Connect','Bring saved chats or live harness events.','+'],['brief','02','Discover','See what the agents are doing and which patterns need a closer look.','◎'],['plan','03','Plan','Agree on the question, the outcome and what changes.','↔'],['simulator','04','Simulate','Build a real task world. Run fresh LLM teams in it.','◇'],['findings','05','See results','Read the counts, uncertainty and replayable examples.','▥']];
      return `<div class="exp-home"><section class="exp-hero"><div class="exp-hero-copy"><span class="eyebrow">A LAB FOR TEAMS OF AI AGENTS</span><h1>Watch. Discover.<br>Test what changes.</h1><p>Connect your agents. We find questions.<br>You shape the experiment. Real agents run it.</p><div class="action-row">${button('Start with AI Village →','data-exp-demo',true)}${button('Connect your own swarm','data-view="connect"')}</div><div class="exp-ready"><span></span>${hasDemo()?'Real AI Village chat is ready on this laptop.':'Connect saved chat or your running harness.'}</div></div>${previewScene(source)}</section><div class="exp-section-title"><h2>One workspace. A clear path.</h2><p>Your guide explains what you see and opens the right view.</p></div><div class="exp-step-cards journey-five">${steps.map(([v,n,title,text,symbol])=>`<button class="exp-step-card" data-view="${v}"><span class="exp-card-top"><span>${n}</span><i>${symbol}</i></span><h3>${title}</h3><p>${text}</p><span class="exp-card-link">Open ${title.toLowerCase()} →</span></button>`).join('')}</div><section class="exp-project-summary"><div><span class="eyebrow">YOUR WORKSPACE</span><h2>Sources, questions, tests and results stay together.</h2><p>The main path uses real LLM agents and recorded actions. A source observation motivates a question; a fresh controlled test measures that question in a defined task.</p></div>${button('Replay the saved chat','data-view="watch"')}</section></div>`;
    }
    async function watch() {
      if(x.previewWatch){const record=await read(x.previewWatch);x.record=record;x.replayRecord=record;x.replayKey=`${record.id}@${record.version}:saved`;return heading('SAVED SOURCE','Replay the saved source.','Your current source and experiment draft stay as you left them.')+`<div id="experience-replay">${SocietyReplay.render({record,initialState:x.replayStates.get(x.replayKey)})}</div>`+sourceDetails(record);}
      if(x.watchRunRef && !x.watchStudy){const record=await read(x.watchRunRef,'observability_run');x.record=record;x.replayRecord=record;x.replayKey=`${record.id}@${record.version}:events`;return heading('CONNECTED SWARM','Watch logged actions and messages.','Scrub the timeline. Tasks and actions appear when the source records them.','brief')+`<div id="experience-replay">${SocietyReplay.render({record,initialState:x.replayStates.get(x.replayKey)})}</div>`+sourceDetails(record);}
      if(x.watchStudy) {
        const record=await read(x.watchStudy);if(!validVillageStudy(record))throw new Error('Choose a source-grounded Village experiment.');x.record=record;x.replayRecord=record;
        const runs=record.payload.runs || [];x.runIndex=Math.max(0,Math.min(runs.length-1,x.runIndex));
        x.replayKey=`${record.id}@${record.version}:run${x.runIndex}`;
        return heading('SAVED TEAM TEST','Watch the team work.','These are logged actions from a fresh test. The task is a small simulated world.','watch')+tourPanel('watch')+contractPanel(record)+`<div class="exp-watch-controls"><label>Team run<select id="exp-run">${runs.map((r,i)=>`<option value="${i}" ${i===x.runIndex?'selected':''}>Team ${i+1} · ${e(({neutral_note:'Neutral note',canonical_check:'Canonical project check'})[r.arm] || r.context || '')}</option>`).join('')}</select></label>${button('Back to the saved chat','data-exp-chat')}</div><div id="experience-replay">${typeof SocietyReplay==='object'?SocietyReplay.render({record,runIndex:x.runIndex,initialState:x.replayStates.get(x.replayKey)}):'<p>Reload to open the replay.</p>'}</div>${sourceDetails(record)}`;
      }
      if(!x.project && !b.app.workspace)x.project=hasDemo()?DEMO:(datasets()[0]?ref(datasets()[0]):null);
      if(!x.project)return heading('WATCH AGENTS','Connect your first team.','Bring a saved chat or events from your running harness.','brief')+button('Connect agents','data-view="connect"',true);
      const record=await read(x.project,'dataset');x.record=record;
      const isDemo=sameRef(record,DEMO), messages=record.payload.messages || [];
      let rows=messages;
      if(x.evidenceIds?.length)rows=messages.filter(m=>x.evidenceIds.includes(m.id));
      else if(isDemo && x.window==='demo')rows=messages.filter(m=>{const t=Date.parse(m.timestamp || m.created_at);return t>=Date.parse('2025-04-22T18:00:00Z') && t<Date.parse('2025-04-22T19:00:00Z') && m.room_id==='18a3b2fb-9d2e-4ce7-b9b1-52e09c5408a8';});
      const replayRecord={...record,payload:{...record.payload,messages:rows}};x.replayRecord=replayRecord;
      x.replayKey=`${record.id}@${record.version}:${x.window}`;
      return heading('WATCH AGENTS',isDemo?'A draft is done. A teammate is waiting.':'Watch the conversation unfold.','Observational replay: these posts do not establish who read them or why agents acted.','watch')+tourPanel('watch')+`<div class="exp-watch-controls"><label>Saved chat<select id="exp-project">${datasets().map(r=>`<option value="${e(r.id)}" ${r.id===record.id?'selected':''}>${e(projectName(r))} · ${r.summary.messages} messages</option>`).join('')}</select></label>${isDemo?`<label>Moment<select id="exp-window"><option value="demo" ${x.window==='demo'?'selected':''}>The draft handoff · 22 Apr, 23:30 IST</option><option value="all" ${x.window==='all'?'selected':''}>All saved messages in this week</option></select></label>`:''}<span class="exp-kind">${isDemo?'Recorded AI Village chat':record.payload.provenance?.origin==='authored_example' || record.payload.source?.includes('coordination_fixture')?'Authored example':'Imported chat'} · ${rows.length} messages</span></div><div id="experience-replay">${typeof SocietyReplay==='object'?SocietyReplay.render({record:replayRecord,initialState:x.replayStates.get(x.replayKey)}):'<p>Replay is loading. Reload this view.</p>'}</div><section class="exp-next"><div><h3>What should we test?</h3><p>First identify the episode, competing explanations and the tools or state an experiment would need. A message pattern does not select a simulator.</p></div>${button('Discuss the source and needed world','data-journey-help',true)}</section>${sourceDetails(record,'Where did this chat come from?')}`;
    }
    async function tryChange() {return heading('PLAN A TEST','Open the live research path.','Connect a source, plan a comparison, and run real agents.','plan')+button('Connect a swarm','data-view="connect"',true);}
    async function savedStage() {
      const {view,context}=x.savedStage;
      const plan=await read(context.plan_ref,'guided_plan'),p=plan.payload;
      if(['village_document_access_repair','single_document_reference_repair'].includes(p.family)){
        await read(p.source_refs?.dataset_ref,'dataset');
        const world=view==='simulator'?await read(context.simulator_ref,'guided_simulator'):null;
        if(world && !sameRef(plan,world.payload.plan_ref))throw new Error('This saved world and plan do not match.');
        if(world && (world.payload.family!==p.family || world.payload.environment?.kind!==p.family || !sameRef(p.source_refs.dataset_ref,world.payload.source_refs?.dataset_ref)))throw new Error('This saved world has a different family or exact source.');
        const saved=world || plan,agents=world?.payload.environment?.agents || world?.payload.environment?.roster || [];
        const people=Array.isArray(agents)?agents.slice(0,12).map(a=>typeof a==='string'?a:a.name || a.id).filter(v=>typeof v==='string').map(a=>isRecovery(plan)?({ethics_owner:'Document owner',auditor:'Teammate'})[a] || a:a):[];
        return heading('SAVED '+(world?'WORLD':'PLAN'),world?'The document-access world behind this result.':'The source-grounded access plan.','These exact saved rules stay separate from your current draft.',view)+`<section class="journey-card"><h2>${isRecovery(plan)?'Can two agents repair a broken link?':e(p.question)}</h2>${isRecovery(plan)?`<details><summary>Exact saved plan</summary><p>${e(p.question)}</p></details>`:''}<p>${isRecovery(plan)?'The owner and auditor must recover access to one correct original document; the auditor must actually open its current version.':'The team must produce a project that remains usable to its intended collaborators.'} The experiment represents document references, access checks and repair choices; it does not recreate the original account services.</p><div class="journey-comparison"><article><h3>Neutral note</h3><p>${e(p.control_text || 'Not recorded')}</p></article><article><h3>Canonical project check</h3><p>${e(p.treatment_text || 'Not recorded')}</p></article></div>${people.length?`<p>Declared roster: ${people.map(e).join(' · ')}</p>`:''}${contractPanel({...saved,kind:isRecovery(saved)?'village_recovery_experiment':'village_access_experiment'})}${world?sourceDetails(world,'Exact saved environment'):sourceDetails(plan,'Exact saved plan')}</section><div class="action-row">${context.result_ref?button('Back to results','data-view="findings"'):button('Discuss the next step','data-journey-help')}${button('Open current draft','data-exp-current-draft')}</div>`;
      }
      return heading('AI VILLAGE STUDY','Choose a source-grounded plan.','This saved item is not part of the current AI Village workflow.',view)+button('Explore the Village source','data-view="brief"');
    }

    async function openResultStage(view,context=x.resultGuideContext){
      if(!context?.plan_ref || (view==='simulator' && !context.simulator_ref))throw new Error('This result has no linked saved '+view+'.');
      x.savedStage={view,context:JSON.parse(JSON.stringify(context))};await navigate(view);
    }
    async function findings() {
      x.resultGuideContext=null;
      const available=studies();
      if(x.study && !available.some(r=>sameRef(r,x.study)))return heading('SEE FINDINGS','This saved result is unavailable.','Its exact version is not in the current workspace. Choose an available test; your source selection has not changed.','findings')+button('Open the current plan','data-view="plan"');
      if(!x.study)return heading('SEE FINDINGS','No experiment is selected for this question.','Source observations do not become experimental results. Build and run a reviewed Village-grounded study to measure this question.','findings')+button('Browse Village studies','data-view="experiments"')+button('Discuss the current source','data-view="brief"');
      const record=await read(x.study);const p=record.payload;const facts=armFacts(record),live=p.agent_mode==='live',n=p.runs?.length;
      const decisions=Array.isArray(p.runs) && p.runs.every(r=>Array.isArray(r.turns))?p.runs.reduce((sum,r)=>sum+r.turns.length,0):null;
      if(!validVillageStudy(record))return heading('AI VILLAGE STUDY','The source and fidelity contract needs review.','A result must retain an exact Village source, hypothesis and represented/omitted state before it is shown as a study of that episode.','findings')+button('Discuss the selected source','data-view="brief"');
      const result=`<div class="exp-result-chart" aria-label="Teams meeting the saved access goal">${facts.map(f=>`<div class="exp-result-row"><span>${e(f.label)}</span><div class="exp-result-blocks">${Array.from({length:Math.min(100,f.n)},(_,i)=>`<i class="${f.correct!==null && i<f.correct?'good':''}" aria-hidden="true"></i>`).join('')}</div><strong>${f.correct===null?'Unknown':`${f.correct} / ${f.n}`}</strong></div>`).join('')}<p>Each block is one whole team. ${isRecovery(record)?'Filled blocks mean the auditor successfully opened the current original.':'Filled blocks produced a verified usable project.'}</p><p><strong>What counts as finishing?</strong> ${isRecovery(record)?'One correct original must remain authorized, and its assigned auditor must actually open the current version. The goal and starting state are the same in both conditions.':'Four original documents must be correct, each assigned checker must have access, and those checkers must actually open the current final versions.'} A zero means this complete goal was not met; it does not mean the team made no progress.</p></div>`;
      const secondary=facts.map(f=>{const values=p.runs.filter(r=>r.arm===f.key).map(r=>r.outcomes?.[isRecovery(record)?'canonical_reference_queued_to_checker':'avoidable_recreations']);return {...f,recreations:values.length===f.n && values.length && values.every(Number.isSafeInteger) && values.every(v=>v>=0)?values.reduce((a,z)=>a+z,0):null};});
      const interpretation=`<div class="exp-takeaway"><span class="eyebrow">THIS SOURCE-GROUNDED TASK</span><h2>${isRecovery(record)?'One original, one peer access goal.':'Document access and repair in the saved world.'}</h2><p>${isRecovery(record)?'The primary outcome is an executed auditor open of the current original.':'The primary outcome is a usable project.'} ${isRecovery(record)?'Queued references are a separate process measure; they do not prove the teammate read a message.':'Avoidable recreations are a separate process measure.'} Neither score establishes why the original Village agents acted.</p>${secondary.map(f=>`<p>${e(f.label)}: ${f.recreations===null?'Unknown':f.recreations} ${isRecovery(record)?'teams queued a canonical reference':'recorded avoidable recreations'} across ${f.n} teams.</p>`).join('')}</div>`;
      const primaryEffect=p.analysis?.primary_effect,point=value=>Math.max(0,Math.min(100,(value+1)*50));
      const interval=primaryEffect && Number.isFinite(primaryEffect.difference) && Array.isArray(primaryEffect.ci95) && primaryEffect.ci95.length===2 && primaryEffect.ci95.every(Number.isFinite) && -1<=primaryEffect.ci95[0] && primaryEffect.ci95[0]<=primaryEffect.difference && primaryEffect.difference<=primaryEffect.ci95[1] && primaryEffect.ci95[1]<=1?`<section class="journey-interval"><h3>How large could the change be?</h3><p>Canonical access check minus neutral note: <strong>${Math.round(primaryEffect.difference*100)} percentage points</strong>.</p><div class="journey-effect-axis" role="img" aria-label="Estimated change ${Math.round(primaryEffect.difference*100)} percentage points, saved 95 percent interval ${Math.round(primaryEffect.ci95[0]*100)} to ${Math.round(primaryEffect.ci95[1]*100)}"><i class="zero"></i><span class="range" style="left:${point(primaryEffect.ci95[0])}%;width:${point(primaryEffect.ci95[1])-point(primaryEffect.ci95[0])}%"></span><i class="point" style="left:${point(primaryEffect.difference)}%"></i></div><div class="journey-axis-labels"><span>−100 points</span><span>No change</span><span>+100 points</span></div><p class="exp-small">The saved 95% interval runs from ${Math.round(primaryEffect.ci95[0]*100)} to ${Math.round(primaryEffect.ci95[1]*100)} points.${primaryEffect.ci95[0]<=0 && primaryEffect.ci95[1]>=0?' It includes no change; the effect remains uncertain.':''} Unit: matched whole-team difference. Saved method: ${e(primaryEffect.interval_method || 'Not recorded')}.</p></section>`:'';
      let verification='';
      if(x.viewedExecutionRef || x.executionRef){const execution=await read(x.viewedExecutionRef || x.executionRef,'guided_result');if(sameRef(record,execution.payload.result_ref)){x.resultGuideContext={result_ref:ref(record)};for(const key of ['plan_ref','simulator_ref'])if(execution.payload[key])x.resultGuideContext[key]=execution.payload[key];if(execution.payload.source_brief_ref)x.resultGuideContext.brief_ref=execution.payload.source_brief_ref;const proof=await read(execution.payload.verification_ref,'verification'),claims=await read(execution.payload.claims_ref,'claim_audit');verification=`<section class="journey-card"><span class="eyebrow">CHECKED AGAINST THE RECORDED RUNS</span><h2>${villageChecks(record,proof,claims)?'Replay and outcome checks passed.':'This result needs a review.'}</h2><p>The saved replay record checks the executed actions, observations and outcomes. The finite fact record contains deterministic counts and the saved matched-team effect; these are not an AI evaluator’s explanation.</p><div class="action-row">${button('Inspect replay checks',`data-exp-inspect="${e(proof.id)}" data-exp-version="${proof.version}"`)}${button('Inspect checked facts',`data-exp-inspect="${e(claims.id)}" data-exp-version="${claims.version}"`)}${button('Open our plan','data-exp-result-stage="plan"')}${button('Open this world','data-exp-result-stage="simulator"')}</div><p class="exp-small">The checks are linked to this exact result. They do not verify the historical mechanism, simulator fidelity or an AI’s free-text interpretation.</p></section>`;}}
      return heading('AI VILLAGE RESULTS','Did the canonical access check help?','These outcomes belong to the cited source hypothesis and saved access world.','findings')+contractPanel(record)+`<section class="exp-finding-panel"><div class="exp-finding-head"><div><span class="eyebrow">SAVED SOURCE-GROUNDED AI TEST</span><h2>${isRecovery(record)?'Single-document reference recovery':'Document access and repair'}</h2><p>${Number.isInteger(n)?n:'Unknown'} whole teams · ${decisions===null?'Unknown decision count':decisions+' real LLM decisions'} · ${e(p.status || 'Unknown completion status')}</p></div>${button('Watch the recorded team actions',`data-exp-watch-result="${e(record.id)}"`)}${button('Inspect exact result',`data-exp-inspect="${e(record.id)}" data-exp-version="${record.version}"`)}</div>${result}${documentProgress(record)}${interval}${interpretation}</section>${verification}<section class="journey-card"><h3>What remains unresolved?</h3><p>The original account services, hidden histories and historical explanation were not recreated. Outcome and replay checks validate this recorded execution, not a claim about why the source episode happened.</p></section>${sourceDetails(record,'Saved result and source contract')}`;
    }

    async function importer() {
      return heading('BRING YOUR CHAT','Start small. See your team.','You only need messages: who spoke, when, in which room, and what they said.')+`<div class="exp-import-grid"><section class="exp-import-panel"><span class="eyebrow">RUNNING AGENTS</span><h2>Use structured events.</h2><p>If your harness records tasks and tool actions, connect those too. You can see more than conversation alone.</p>${button('Connect your harness →','data-view="connect"',true)}<a href="/api/observability/schema" target="_blank" rel="noopener" class="button">See the event format ↗</a></section><section class="exp-import-panel"><span class="eyebrow">OPTION 2 · YOUR TEAM</span><h2>Add a small chat file.</h2><p>Choose a JSONL file under 1 MB, with up to 2,000 messages. It stays on this laptop. Selected chat excerpts are sent to the configured OpenAI model for automatic AI discovery and when you ask the guide a question.</p><label class="exp-file-drop" for="exp-chat-file"><span>↑</span><strong>Choose a .jsonl chat file</strong><small>or drop it here</small><input type="file" id="exp-chat-file" accept=".jsonl,.ndjson,text/plain,application/x-ndjson"></label><form id="exp-import-form"><label class="field"><span>Chat name</span><input id="exp-import-name" value="${e(x.importName)}" maxlength="200" required></label><details class="exp-paste" ${x.importContent?'open':''}><summary>Paste messages instead</summary><label class="field"><span>One JSON message per line</span><textarea id="exp-import-content" rows="6" placeholder='{"id":"m1","agent_speaker_id":"builder","agent_name":"Builder","speaker_type":"agent","room_id":"team","created_at":"2026-10-05T10:00:00Z","content":"The draft is ready."}'>${e(x.importContent)}</textarea></label></details><p id="exp-import-status" role="status">${x.importContent?`${x.importContent.split('\n').filter(s=>s.trim()).length} lines ready to check.`:'Choose a file or paste a few messages.'}</p>${button(x.importBusy?'Checking…':'Import and discover →',`type="submit" ${x.importBusy?'disabled':''}`,true)}</form></section></div><details class="exp-source"><summary>What format do I need?</summary><p>JSONL means one JSON message per line. Each line needs <code>id</code>, <code>agent_speaker_id</code> (or <code>speaker_id</code>), <code>speaker_type</code> (agent or user), <code>room_id</code>, <code>created_at</code>, and <code>content</code>. Add <code>agent_name</code> for readable names. Times use ISO format; include Z for UTC.</p><p>For a larger JSONL.gz file or the mounted AI Village folder, use the local source importer.</p>${button('Open local source importer','data-view="overview"')}</details>`;
    }
    async function navigate(view) {
      if(!PRIMARY.includes(view) && !['overview','observatory','episode','measurement','library','experiments','audit'].includes(view))throw new Error('This view is unavailable.');
      b.app.view=view;x.onWorkspaceSave?.();await b.render();document.getElementById('main')?.focus({preventScroll:true});
      window.scrollTo({top:0,behavior:'instant'});
    }
    async function loadExample() {
      if(x.exampleBusy)return;x.exampleBusy=true;try { const response=await fetch('/sample-chat.jsonl');if(!response.ok)throw new Error('The example is unavailable.');
      const result=await b.api('/api/guide/import',{method:'POST',headers:{'Content-Type':'application/json','X-Lab-Token':b.app.state.csrf},body:JSON.stringify({name:'Authored example · Draft handoff',content:await response.text()})});
      x.project=result.dataset_ref;x.window='all';x.watchStudy=null;await b.refresh();await navigate('watch'); } finally{x.exampleBusy=false;}
    }
    async function click(target) {
      if(target.hasAttribute('data-exp-result-stage')){await openResultStage(target.dataset.expResultStage);return true;}
      if(target.hasAttribute('data-exp-current-draft')){x.savedStage=null;await navigate('plan');return true;}
      if(target.hasAttribute('data-view')){x.savedStage=null;if(target.dataset.view==='watch')x.previewWatch=null;}
      if(journey && await journey.click(target))return true;
      if(target.hasAttribute('data-exp-demo')){await navigate('connect');return true;}
      if(target.hasAttribute('data-exp-example')){await loadExample();return true;}
      if(target.hasAttribute('data-exp-exit')){x.guided=false;await b.render();return true;}
      if(target.hasAttribute('data-exp-tour')){x.tour=Number(target.dataset.expTour);if(x.tour>=3){x.guided=false;await navigate('home');b.toast('Demo complete. Explore freely, or ask the guide.');}else await navigate(['watch','try','findings'][x.tour]);return true;}
      if(target.hasAttribute('data-exp-chat')){x.watchStudy=null;await navigate('watch');return true;}
      if(target.hasAttribute('data-exp-scenario')){x.tryKind=target.dataset.expScenario;await b.render();return true;}

      if(target.hasAttribute('data-exp-watch-result')){x.previewWatch=null;x.watchStudy=x.savedStage?.context?.result_ref || x.study;x.runIndex=0;await navigate('watch');return true;}
      if(target.hasAttribute('data-exp-setup')){b.app.experimentStudy=({artifact:'handoff',network:'network',resource:'resource'})[target.dataset.expSetup];await navigate('experiments');return true;}

      if(target.hasAttribute('data-exp-inspect')){await b.openObject(target.dataset.expInspect,Number(target.dataset.expVersion));return true;}
      if(target.hasAttribute('data-exp-inspect-job')){b.app.traceJob=target.dataset.expInspectJob;await navigate('audit');return true;}
      return false;
    }
    async function change(target) {
      if(journey && await journey.change(target))return true;
      if(target.id==='exp-project'){const r=datasets().find(r=>r.id===target.value);if(r){x.project=ref(r);x.window=r.id===DEMO.id?'demo':'all';x.watchStudy=null;await b.render();}return true;}
      if(target.id==='exp-window'){x.window=target.value;await b.render();return true;}
      if(target.id==='exp-study'){x.viewedExecutionRef=null;const r=studies().find(r=>r.id===target.value);if(r){x.study=ref(r);await b.render();}return true;}
      if(target.id==='exp-run'){x.runIndex=Number(target.value);await b.render();return true;}
      if(target.id==='exp-chat-file'){await file(target.files?.[0]);return true;}
      return false;
    }
    function input(target) {
      journey?.input(target);
      if(target.id==='exp-import-name')x.importName=target.value;
      if(target.id==='exp-import-content'){x.importContent=target.value;const s=document.getElementById('exp-import-status');if(s)s.textContent=`${x.importContent.split('\n').filter(s=>s.trim()).length} lines ready to check.`;}
    }
    async function file(selected) {
      if(!selected)return;if(selected.size>900000)throw new Error('Start with a file under 900 KB, so it fits the 1 MB import request.');
      if(!/\.(jsonl|ndjson)$/i.test(selected.name))throw new Error('Choose a JSONL chat file. You can download the example to see the format.');
      x.importContent=await selected.text();x.importName=selected.name;await b.render();
    }
    async function submit(event) {
      if(event.target.id!=='exp-import-form')return false;
      event.preventDefault();if(x.importBusy)return true;x.importBusy=true;
      const button=event.target.querySelector('[type="submit"]');if(button){button.disabled=true;button.textContent='Checking…';}
      try{const result=await b.api('/api/guide/import',{method:'POST',headers:{'Content-Type':'application/json','X-Lab-Token':b.app.state.csrf},body:JSON.stringify({name:x.importName,content:x.importContent})});x.project=result.dataset_ref;x.window='all';x.watchStudy=null;x.importContent='';await b.refresh();const packet=await b.api('/api/observability/brief',{method:'POST',headers:{'Content-Type':'application/json','X-Lab-Token':b.app.state.csrf},body:JSON.stringify({dataset_ref:result.dataset_ref})});await journey.accept(packet);b.toast(`${result.messages} messages imported.${result.redacted?' Credential-like text was removed.':''}`);}
      catch(error){b.toast(error.message,true);const status=document.getElementById('exp-import-status');if(status)status.textContent=error.message;}
      finally{x.importBusy=false;if(button?.isConnected){button.disabled=false;button.textContent='Import and discover →';}}return true;
    }
    function update() {
      journey?.update();
      if(x.practiceJob && !x.practiceResult){const job=b.app.state.jobs.find(j=>j.id===x.practiceJob);if(job?.status==='completed'){
        const ids=Array.isArray(job.payload.result_ids)?job.payload.result_ids:[],id=ids.find(id=>String(id).startsWith('experiment-'));
        const r=b.app.state.objects.find(r=>r.id===id && r.kind==='experiment');if(r)x.practiceResult=ref(r);
      }}
      const advanced=document.getElementById('advanced-navigation');
      if(advanced && !PRIMARY.includes(b.app.view))advanced.open=true;
      document.body.dataset.labView=b.app.view;
      const labels={home:'Start here',connect:'Connect',brief:'Discover',plan:'Plan an experiment',simulator:'Create and run',watch:'Watch agents',try:'Plan an experiment',findings:'See results',import:'Bring a chat',overview:'Local source importer',observatory:'Network details',episode:'Episode details',measurement:'Check labels',library:'Saved explanations',experiments:'Test setup',audit:'Activity log'};
      const location=document.getElementById('workspace-location');if(location)location.textContent=`Your workspace / ${labels[b.app.view] || 'Research tools'}`;
      if(typeof history!=='undefined')history.replaceState(null,'',`#${b.app.view}`);
      if(x.guideMounted)guideStatus();
    }
    function dispose(){if(cleanup){cleanup();cleanup=null;}}
    function mount(view) {
      if(view==='watch' && x.record && typeof SocietyReplay==='object'){
        let record=x.replayRecord || x.record;
        cleanup=SocietyReplay.attach(document.getElementById('experience-replay'),{record,runIndex:x.runIndex,initialState:x.replayStates.get(x.replayKey),onState:s=>{x.replayStates.set(x.replayKey,s);x.onWorkspaceSave?.();},onInspect:async packet=>{
          if(packet.message_id){const m=x.record.payload.messages.find(m=>m.id===packet.message_id);if(m){const d=document.getElementById('evidence-dialog');d.querySelector('h2').textContent='Original message';d.querySelector('.eyebrow').textContent='SAVED SOURCE';document.getElementById('dialog-body').innerHTML=`<p><strong>${e(m.agent_name)}</strong> · ${e(m.timestamp)}</p><div class="message-full">${e(m.content)}</div><p class="exp-small">${e(m.id)} · saved chat version ${x.record.version}</p>`;d.showModal();}}
          else if(packet.event_id){const record=await read(packet.record_ref,'observability_run');const ev=record.payload.events.find(ev=>ev.id===packet.event_id);if(!ev)throw new Error('The logged event is unavailable.');const d=document.getElementById('evidence-dialog');d.querySelector('h2').textContent='Original recorded event';document.getElementById('dialog-body').innerHTML=`<pre class="message-full">${e(JSON.stringify(ev,null,2))}</pre><p>Source version ${record.version}. A logged action is not proof of hidden intent.</p>`;d.showModal();}
          else {const record=await read(packet.record_ref);const turn=record.payload.runs?.[packet.run_index]?.turns?.[packet.turn_index];if(!turn)throw new Error('This logged action is unavailable.');const d=document.getElementById('evidence-dialog');d.querySelector('h2').textContent='What the agent did';d.querySelector('.eyebrow').textContent='SAVED TEST ACTION';document.getElementById('dialog-body').innerHTML=`<p><strong>${e(turn.agent_id)}</strong> · turn ${packet.turn_index+1}</p><h3>Chosen action</h3><pre class="message-full">${e(JSON.stringify(turn.action,null,2))}</pre><h3>What the tool returned</h3><pre class="message-full">${e(JSON.stringify(turn.tool_result,null,2))}</pre><p class="exp-small">${e(record.id)} · saved version ${record.version} · team ${packet.run_index+1}</p>`;d.showModal();}
        }});
      }
      if(view==='import'){const drop=document.querySelector('.exp-file-drop');drop?.addEventListener('dragover',evt=>{evt.preventDefault();drop.classList.add('dragging');});drop?.addEventListener('dragleave',()=>drop.classList.remove('dragging'));drop?.addEventListener('drop',evt=>{evt.preventDefault();file(evt.dataTransfer.files?.[0]).catch(error=>b.toast(error.message,true));});}
    }
    // The guide lives outside the rerendered main pane, so its conversation stays put.
    function guideStatus(){const el=document.getElementById('guide-budget');if(el)el.textContent=x.guideBusy?'Reading the current view…':x.guideBudget?.remaining===0?'AI guide unavailable · shortcuts ready':'AI guide ready';}
    function chatLine(role,text,source,metadata={}){x.chat.push({role,text,source});const log=document.getElementById('guide-messages');if(!log)return;const row=document.createElement('article');row.className=`guide-message ${role}`;const message={role,content:text,metadata:{...metadata,answer_source:source}},label='<strong>'+e(role==='user'?'You':source==='ai'?'Society guide':'Workspace guide')+'</strong>';if(typeof GuideMessage==='object')row.innerHTML=label+GuideMessage.render(message);else{const who=document.createElement('strong');who.textContent=role==='user'?'You':source==='ai'?'Society guide':'Workspace guide';const p=document.createElement('p');p.textContent=text;row.append(who,p);}log.append(row);log.scrollTop=log.scrollHeight;
      const guide=metadata.guide_result || metadata,reference=guide.updated_context?.result_ref || guide.result_context_ref;
      if(role==='assistant' && typeof GuideMessage==='object' && validRef(reference) && (guide.sources || []).some(s=>sameRef(s.object_ref || s.ref,reference)))read(reference).then(record=>{if(row.isConnected===false || !validVillageStudy(record))return;row.innerHTML=label+GuideMessage.render(message,{hostEmbeds:[{type:'html_report',source_ref:ref(record),title:'This experiment’s scientific results',scope:'Exact saved source-grounded task, matched outcomes and uncertainty. A zero estimate with a wide interval does not establish no benefit or equivalence.'}]});log.scrollTop=log.scrollHeight;}).catch(()=>{});
    }
    function showGuide(){x.guideOpen=true;document.getElementById('guide-dock')?.classList.add('open');document.getElementById('guide-toggle')?.setAttribute('aria-expanded','true');}
    async function applyAction(action){
      if(b.app.workspace && await b.app.workspace.applyGuideAction(action))return;
      if(action.type==='navigate'){const context=x.savedStage?.context || (b.app.view==='findings' && sameRef(x.study,x.resultGuideContext?.result_ref)?x.resultGuideContext:null);if(['plan','simulator'].includes(action.view) && context?.plan_ref){await openResultStage(action.view,context);return;}x.savedStage=null;if(action.view==='watch'){x.watchStudy=null;x.previewWatch=null;}await navigate(action.view);}
      else if(action.type==='open_object' && action.object_ref){const r=await read(action.object_ref);if(b.app.workspace)await b.app.workspace.openArtifact(ref(r),action.view==='watch'?'replay':'open');else if(r.kind==='dataset'){x.project=ref(r);x.window=r.id===DEMO.id?'demo':'all';x.watchStudy=null;await navigate('watch');}else if(STUDIES.includes(r.kind)){x.study=ref(r);await navigate('findings');}else await b.openObject(r.id,r.version);}
    }
    function assistantContext(){if(x.savedStage?.view===b.app.view){const saved=JSON.parse(JSON.stringify(x.savedStage.context));if(validRef(x.rubricRef))saved.rubric_ref=copy(x.rubricRef);if(validRef(x.measurementRef))saved.measurement_ref=copy(x.measurementRef);return saved;}const context={};if(b.app.workspace?.state.copy && b.app.workspace.state.copy.payload?.owner_chat_id===b.app.activeChatId && ['workspace','home','workspace-copy'].includes(b.app.view))context.workspace_draft_ref=ref(b.app.workspace.state.copy);if(x.briefRef)context.brief_ref=['plan','simulator'].includes(b.app.view)?(x.draftSourceRef || x.briefRef):x.briefRef;if(x.watchRunRef)context.run_ref=x.watchRunRef;if(x.planRef && ['plan','simulator'].includes(b.app.view))context.plan_ref=x.planRef;if(x.simulatorRef && b.app.view==='simulator')context.simulator_ref=x.simulatorRef;if(['plan','simulator','brief'].includes(b.app.view))context.plan_draft={question:x.draft?.question,control_text:x.draft?.control_text,treatment_text:x.draft?.treatment_text};if(b.app.view==='watch' && x.record?.kind==='dataset'){delete context.brief_ref;delete context.run_ref;context.dataset_ref=ref(x.record);const s=x.replayStates.get(x.replayKey);const peek=typeof SocietyReplay==='object'?SocietyReplay.peek(x.replayRecord || x.record,s):null;const msg=peek?.current_message;if(msg?.id)context.selected_message_id=msg.id;}if(b.app.view==='watch' && x.watchStudy){delete context.brief_ref;delete context.run_ref;context.result_ref=x.watchStudy;}if(b.app.view==='watch' && x.previewWatch && x.record?.kind==='observability_run'){delete context.brief_ref;context.run_ref=x.previewWatch;}if(b.app.view==='findings' && x.study){delete context.brief_ref;delete context.run_ref;context.result_ref=x.study;if(sameRef(x.study,x.resultGuideContext?.result_ref)){delete context.brief_ref;delete context.run_ref;Object.assign(context,x.resultGuideContext);}}if(validRef(x.rubricRef))context.rubric_ref=copy(x.rubricRef);if(validRef(x.measurementRef))context.measurement_ref=copy(x.measurementRef);return context;}
    function guideHistory(){let chars=0;const rows=[];for(const row of x.guideHistory.slice(-8).reverse()){const content=row.content.slice(0,2000);if(chars+content.length>4000)break;chars+=content.length;rows.unshift({role:row.role,content});}return rows;}
    const copy=value=>JSON.parse(JSON.stringify(value));
    const validRef=r=>r && typeof r.id==='string' && /^[A-Za-z0-9_.-]{1,200}$/.test(r.id) && Number.isSafeInteger(r.version) && r.version>0 && /^[a-f0-9]{64}$/.test(r.hash);
    const draftDefaults=()=>({question:'',control_text:'',treatment_text:'',trials_per_arm:2,max_rounds:6,valid_probability:0.35,seed:61005});
    function exportWorkspaceState(){
      const context={};for(const [key,name]of [['project','dataset_ref'],['watchRunRef','run_ref'],['briefRef','brief_ref'],['discoveryRef','discovery_ref'],['planRef','plan_ref'],['simulatorRef','simulator_ref'],['study','result_ref'],['rubricRef','rubric_ref'],['measurementRef','measurement_ref']])if(validRef(x[key]))context[name]=copy(x[key]);
      const selections={};for(const [kind,id]of Object.entries(b.app.selected || {})){const r=b.app.state?.objects.find(r=>r.id===id && r.kind===kind);if(r)selections[kind]=ref(r);}
      const journey={};for(const key of ['executionRef','viewedExecutionRef','draftSourceRef','watchStudy','previewWatch','followRun','discoveryJob','signalCode','window','aiBrief','runIndex','savedStage','sourceCopyRef'])if(x[key]!==undefined && x[key]!==null)journey[key]=copy(x[key]);
      journey.draft=copy(x.draft || draftDefaults());journey.openedStudies=[...openedStudies.values()].map(ref);
      return {view:b.app.view,selections,context,plan_draft:Object.fromEntries(['question','control_text','treatment_text'].map(k=>[k,String(x.draft?.[k] || '')])),ui:{journey,replay:[...x.replayStates.entries()].slice(-24)}};
    }
    function restoreWorkspaceState(saved={}){
      dispose();x.flowEpoch=(x.flowEpoch || 0)+1;x.guideRequest++;x.guideBusy=false;
      Object.assign(x,{project:null,watchRunRef:null,briefRef:null,discoveryRef:null,planRef:null,simulatorRef:null,executionRef:null,viewedExecutionRef:null,draftSourceRef:null,study:null,watchStudy:null,previewWatch:null,savedStage:null,resultGuideContext:null,record:null,replayRecord:null,replayKey:'',followRun:null,discoveryJob:null,signalCode:null,aiBrief:null,sourceCopyRef:null,runIndex:0,window:'all',discoveryRecords:[],discoveryLoaded:false,evidenceIds:null,evidenceEventIds:null,planBusy:false,buildBusy:false,runBusy:false,connectBusy:false,importBusy:false,telemetryContent:'',connectSource:'',importContent:'',draft:draftDefaults()});
      openedStudies.clear();b.app.selected={};
      x.rubricRef=null;x.measurementRef=null;
      for(const [name,key]of [['dataset_ref','project'],['run_ref','watchRunRef'],['brief_ref','briefRef'],['discovery_ref','discoveryRef'],['plan_ref','planRef'],['simulator_ref','simulatorRef'],['result_ref','study'],['rubric_ref','rubricRef'],['measurement_ref','measurementRef']])if(validRef(saved.context?.[name]))x[key]=copy(saved.context[name]);
      const ui=saved.ui?.journey || {};for(const key of ['executionRef','viewedExecutionRef','draftSourceRef','watchStudy','previewWatch','sourceCopyRef'])if(validRef(ui[key]))x[key]=copy(ui[key]);
      for(const key of ['followRun','discoveryJob','signalCode','window','aiBrief'])if(typeof ui[key]==='string' && ui[key].length<=6000)x[key]=ui[key];
      if(Number.isSafeInteger(ui.runIndex) && ui.runIndex>=0)x.runIndex=ui.runIndex;
      if(ui.savedStage && ['plan','simulator'].includes(ui.savedStage.view) && validRef(ui.savedStage.context?.plan_ref))x.savedStage=copy(ui.savedStage);
      const draft=ui.draft || saved.plan_draft || {};for(const key of ['question','control_text','treatment_text'])if(typeof draft[key]==='string' && draft[key].length<=2000)x.draft[key]=draft[key];
      for(const [key,lo,hi]of [['trials_per_arm',2,20],['max_rounds',2,12],['valid_probability',0,1],['seed',0,9007199254740991]])if(Number.isFinite(draft[key]) && draft[key]>=lo && draft[key]<=hi && (key==='valid_probability' || Number.isSafeInteger(draft[key])))x.draft[key]=draft[key];
      x.replayStates=new Map((saved.ui?.replay || []).filter(row=>Array.isArray(row) && row.length===2 && typeof row[0]==='string').slice(-24));
      for(const [kind,r]of Object.entries(saved.selections || {}))if(validRef(r))b.app.selected[kind]=r.id;
      for(const r of ui.openedStudies || [])if(validRef(r))openedStudies.set(`${r.id}@${r.version}:${r.hash}`,{...r,kind:r.id.split('-')[0],summary:{agent_mode:'live'}});
      const send=document.querySelector('#guide-form button');if(send)send.disabled=false;guideStatus();
    }
    function addSources(sources,log){
      for(const src of sources || []){
        const r=src.object_ref || src.ref;if(!['chat_context','workspace_chat_context'].includes(src.kind) && !validRef(r))continue;
        const el=document.createElement('button');el.className='guide-source button-link';el.textContent=src.label || (['chat_context','workspace_chat_context'].includes(src.kind)?'Read cited conversation':src.message_id?'Read the cited message':'Open cited source');
        el.addEventListener('click',async()=>{try{if(['chat_context','workspace_chat_context'].includes(src.kind))return await b.app.workspace?.showContext(src);const record=await read(r);if(src.message_id && record.kind==='dataset'){const m=record.payload.messages.find(m=>m.id===src.message_id);if(!m)throw new Error('The cited message is unavailable.');const d=document.getElementById('evidence-dialog');d.querySelector('h2').textContent='Cited source message';d.querySelector('.eyebrow').textContent='SAVED SOURCE';document.getElementById('dialog-body').innerHTML=`<p><strong>${e(m.agent_name)}</strong> · ${e(m.timestamp)}</p><div class="message-full">${e(m.content)}</div>`;d.showModal();}else await b.openObject(record.id,record.version);}catch(err){b.toast(err.message,true);}});log?.append(el);
      }
    }
    function hydrateGuide(messages){
      if(x.guideBusy)return;x.chat=[];x.guideHistory=[];const log=document.getElementById('guide-messages');if(log)log.innerHTML='';
      for(const row of messages.slice(-60)){chatLine(row.role,row.content,row.metadata?.answer_source,row.metadata);if(['user','assistant'].includes(row.role))x.guideHistory.push({role:row.role,content:row.content});if(typeof GuideMessage!=='object')addSources(row.metadata?.sources,log);}
      x.guideHistory=x.guideHistory.slice(-16);guideStatus();
    }
    async function openSavedArtifact(record,mode='open',messageId=null){
      if(EXCLUDED_STUDIES.includes(record.kind))throw new Error('Choose a source-grounded AI Village study.');
      if(STUDIES.includes(record.kind) && !validVillageStudy(record))throw new Error('This Village result has no complete source, hypothesis and fidelity contract.');
      if(!validRef(record))throw new Error('Use an exact saved record.');
      if(record.kind==='village_incident'){const source=await read(record.payload.source_ref,'dataset'),first=record.payload.evidence?.[0];if(!first || typeof first.message_id!=='string')throw new Error('This incident has no exact source message.');return openSavedArtifact(source,'replay',first.message_id);}
      if(record.kind==='guided_result'){const result=await read(record.payload.result_ref);await openSavedArtifact(result,mode);x.viewedExecutionRef=ref(record);x.onWorkspaceSave?.();return;}
      if(['dataset','observability_run'].includes(record.kind)){if(messageId!==null){if(record.kind!=='dataset' || typeof messageId!=='string' || messageId.length>200)throw new Error('This citation needs its exact saved chat source.');const model=SocietyReplay.normalize(record);const event=model.available?model.events.find(row=>row.id===messageId):null;if(!event)throw new Error('This cited message is unavailable in the exact saved source.');x.replayStates.set(`${record.id}@${record.version}:saved`,{cursor:event.index,room:event.room,actor:null,speed:1,audience:'all',playing:false});}x.previewWatch=ref(record);x.watchStudy=null;x.window='all';await navigate('watch');return;}
      if(STUDIES.includes(record.kind)){if(record.payload?.agent_mode!=='live')return b.openObject(record.id,record.version);openedStudies.set(`${record.id}@${record.version}:${record.hash}`,record);x.study=ref(record);x.viewedExecutionRef=null;if(b.app.workspace){const packet=await b.api('/api/workspaces/artifacts?scope=all');const linked=packet.artifacts.find(a=>a.kind==='guided_result' && a.source_refs?.some(s=>sameRef(s.ref,record)));if(linked)x.viewedExecutionRef=linked.ref;}x.previewWatch=null;x.savedStage=null;x.watchStudy=mode==='replay'?ref(record):null;x.runIndex=0;await navigate(mode==='replay'?'watch':'findings');return;}
      if(record.kind==='guided_plan'){if(!['village_document_access_repair','single_document_reference_repair'].includes(record.payload.family))throw new Error('Choose a source-grounded Village plan.');await read(record.payload.source_refs?.dataset_ref,'dataset');x.savedStage={view:'plan',context:{plan_ref:ref(record),dataset_ref:record.payload.source_refs.dataset_ref,...(record.payload.grounding_ref?{incident_ref:record.payload.grounding_ref}:{})}};await navigate('plan');return;}
      if(record.kind==='guided_simulator'){const linked=await read(record.payload.plan_ref,'guided_plan');if(!['village_document_access_repair','single_document_reference_repair'].includes(linked.payload.family) || record.payload.family!==linked.payload.family || record.payload.environment?.kind!==linked.payload.family || !sameRef(linked.payload.source_refs?.dataset_ref,record.payload.source_refs?.dataset_ref))throw new Error('Choose a source-grounded Village world with this exact plan and source.');await read(linked.payload.source_refs?.dataset_ref,'dataset');x.savedStage={view:'simulator',context:{plan_ref:record.payload.plan_ref,simulator_ref:ref(record),dataset_ref:linked.payload.source_refs.dataset_ref,...(linked.payload.grounding_ref?{incident_ref:linked.payload.grounding_ref}:{})}};await navigate('simulator');return;}
      return b.openObject(record.id,record.version);
    }
    async function adoptWorkspaceDraft(record){
      if(record.kind!=='workspace_draft' || record.payload?.copied_empirical_outcomes!==false)throw new Error('Choose an editable research copy.');
      const fields=record.payload.editable_fields || {};if(!validRef(fields.source_brief_ref))throw new Error('This draft has no saved observation brief. Connect a source before planning.');
      await read(fields.source_brief_ref,'observation_brief');x.briefRef=copy(fields.source_brief_ref);x.draftSourceRef=copy(fields.source_brief_ref);x.draft={...draftDefaults(),...Object.fromEntries(Object.entries(fields).filter(([k])=>Object.hasOwn(draftDefaults(),k)))};x.signalCode=fields.signal_code || null;x.sourceCopyRef=ref(record);x.savedStage=null;x.flowEpoch++;x.planRef=null;x.simulatorRef=null;x.executionRef=null;journey?.save();await navigate('plan');
    }
    async function ask(message,options={}){
      if(x.guideBusy || !message.trim())return;
      await b.app.workspace?.flush();if(x.guideBusy)return;
      const originChat=b.app.activeChatId || null,request=++x.guideRequest,epoch=x.flowEpoch,context=assistantContext(),sourceStamp=JSON.stringify([x.briefRef,x.watchRunRef,x.project,x.study]),draftStamp=JSON.stringify(x.draft);
      const isActive=()=>request===x.guideRequest && originChat===(b.app.activeChatId || null);
      x.guideBusy=true;if(!options.proactive){showGuide();chatLine('user',message);}guideStatus();
      const send=document.querySelector('#guide-form button');if(send)send.disabled=true;
      const requestId=typeof crypto!=='undefined' && crypto.randomUUID?crypto.randomUUID():'guide-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);
      try{
        const body={message:message.trim(),current_view:b.app.view,history:guideHistory(),current_context:context};
        const shownCopy=b.app.workspace?.state.copy;if(originChat && shownCopy?.payload?.owner_chat_id && shownCopy.payload.owner_chat_id!==originChat && b.app.view==='workspace-copy'){options.mentioned_context=[...(options.mentioned_context || []),{kind:'artifact',ref:ref(shownCopy),origin_chat_id:shownCopy.payload.owner_chat_id}].slice(0,8);}
        if(originChat)Object.assign(body,{active_chat_id:originChat,request_id:requestId,proactive:Boolean(options.proactive),...(options.mentioned_context?.length?{mentioned_context:options.mentioned_context}:{})});
        const answer=await b.api('/api/guide/chat',{method:'POST',headers:{'Content-Type':'application/json','X-Lab-Token':b.app.state.csrf,...(originChat?{'X-Lab-Chat':originChat}:{})},body:JSON.stringify(body)});
        if(!isActive()){answer.stale_context=true;await b.app.workspace?.afterGuide(answer,originChat);return answer;}
        chatLine('assistant',answer.answer,answer.answer_source,{guide_result:answer});x.guideHistory.push({role:'user',content:message},{role:'assistant',content:answer.answer});x.guideHistory=x.guideHistory.slice(-16);
        const current=epoch===x.flowEpoch && sourceStamp===JSON.stringify([x.briefRef,x.watchRunRef,x.project,x.study]) && draftStamp===JSON.stringify(x.draft);
        if(answer.answer_source==='ai' && current && !answer.reused){
          const updated=answer.updated_context || {};if(validRef(updated.rubric_ref) && !validRef(updated.measurement_ref))x.measurementRef=null;for(const [field,key]of [['brief_ref','briefRef'],['dataset_ref','project'],['run_ref','watchRunRef'],['discovery_ref','discoveryRef'],['plan_ref','planRef'],['simulator_ref','simulatorRef'],['execution_ref','executionRef'],['result_ref','study'],['rubric_ref','rubricRef'],['measurement_ref','measurementRef']])if(validRef(updated[field]))x[key]=copy(updated[field]);if(validRef(updated.plan_ref) || (validRef(updated.simulator_ref) && validRef(x.planRef))){if(validRef(updated.plan_ref) && !validRef(updated.simulator_ref))x.simulatorRef=null;x.draftSourceRef=updated.brief_ref || x.draftSourceRef;x.savedStage=!updated.result_ref?{view:updated.simulator_ref?'simulator':'plan',context:{plan_ref:copy(updated.plan_ref || x.planRef),...(updated.brief_ref?{brief_ref:copy(updated.brief_ref)}:{}),...(updated.simulator_ref?{simulator_ref:copy(updated.simulator_ref)}:{})}}:null;}for(const receipt of answer.tool_results || [])if(receipt.tool==='discover' && receipt.job_id){x.discoveryJob=receipt.job_id;x.discoveryLoaded=false;x.discoveryRecords=[];}if(Object.keys(updated).length)x.onWorkspaceSave?.();
          if(answer.plan_draft && context.plan_draft && (!options.proactive || !originChat))journey?.applyDraft(answer.plan_draft);
          if(!options.proactive)for(const [index,action]of (answer.actions || []).entries()){if(!isActive())break;await applyAction({...action,workspace_request_id:requestId+'-action-'+index});}
        }
        if(!current)answer.stale_context=true;
        if(isActive()){addSources(answer.sources,document.getElementById('guide-messages'));x.guideBudget=answer.budget || x.guideBudget;}
        await b.app.workspace?.afterGuide(answer,originChat);await b.refresh();return answer;
      }catch(error){if(isActive())chatLine('assistant',`I could not answer that yet: ${error.message}. Your saved work is still available.`,'system_notice');}
      finally{if(isActive()){x.guideBusy=false;if(send)send.disabled=false;guideStatus();await b.app.workspace?.refreshChat();if(['workspace','home'].includes(b.app.view))await b.render();}}
    }
    function initGuide(){
      if(x.guideMounted)return;x.guideMounted=true;
      const form=document.getElementById('guide-form');form?.addEventListener('submit',event=>{event.preventDefault();const input=document.getElementById('guide-input');const message=input.value;input.value='';ask(message,{mentioned_context:b.app.workspace?.consumeDockMentions() || []});});
      document.getElementById('guide-toggle')?.addEventListener('click',()=>{x.guideOpen=!x.guideOpen;document.getElementById('guide-dock')?.classList.toggle('open',x.guideOpen);document.getElementById('guide-toggle').setAttribute('aria-expanded',String(x.guideOpen));});
      document.getElementById('guide-close')?.addEventListener('click',()=>{x.guideOpen=false;document.getElementById('guide-dock')?.classList.remove('open');document.getElementById('guide-toggle')?.setAttribute('aria-expanded','false');});
      document.querySelectorAll('[data-guide-prompt]').forEach(el=>el.addEventListener('click',()=>ask(el.dataset.guidePrompt)));
      document.querySelectorAll('[data-guide-shortcut]').forEach(el=>el.addEventListener('click',async()=>{const v=el.dataset.guideShortcut;chatLine('assistant',`Opening ${({watch:'the conversation replay',findings:'saved findings',import:'the chat importer',try:'a simple test world'})[v]}.`,'shortcut');try{if(v==='watch')x.watchStudy=null;await navigate(v);}catch(error){b.toast(error.message,true);}}));
      chatLine('assistant','Welcome. Ask me to open a conversation, explain a result, or help you choose a test. I can show the view here.','system_notice');guideStatus();b.api('/api/guide/status').then(packet=>{x.guideBudget=packet.budget;guideStatus();}).catch(()=>{});
    }
    const journey=typeof ResearchJourney==='object'?ResearchJourney.create(b,x,{e,button,heading,read,ref,navigate,sourceDetails,ask}):null;
    const views={home,watch,try:journey?journey.views.plan:tryChange,findings,import:importer,...(journey?.views || {})};
    return {render:view=>x.savedStage?.view===view?savedStage():views[view](),hasView:view=>Boolean(views[view]),mount,dispose,click,change,input,submit,update,initGuide,ask,state:x,assistantContext,exportWorkspaceState,restoreWorkspaceState,hydrateGuide,openSavedArtifact,adoptWorkspaceDraft};
  }
  scope.SocietyExperience={create,armFacts,studyContract,isRecovery,primaryKey,validVillageStudy,villageChecks,documentProgress,sameRef,DEMO};
  if(typeof module!=='undefined')module.exports=scope.SocietyExperience;
})(typeof globalThis==='undefined'?window:globalThis);



