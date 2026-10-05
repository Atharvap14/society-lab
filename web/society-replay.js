/* Saved-source presentation. No network, model invocation or scientific mutation. */
(function(global) {
  'use strict';
  const LIMITS={messages:10000,actors:64,textCharacters:4194304,messageCharacters:65536,runs:1000,turns:10000,artifactItems:128};
  const COLORS=['#218d89','#80629d','#c88656','#647ba4','#719461','#bb697c','#b49b4d','#4f91a4'];
  const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const masked=x=>String(x??'').replace(/(?:sk-proj-|sk-|hf_)[A-Za-z0-9_-]{15,}/g,'[credential-shaped text masked]');
  const clip=(x,n)=>x.length>n?x.slice(0,n)+'…':x;
  const bounded=(x,n)=>typeof x==='string'&&x.length>0&&x.length<=n;
  const validRef=r=>r&&bounded(r.id,200)&&Number.isSafeInteger(r.version)&&r.version>=1&&r.version<=1e9&&typeof r.hash==='string'&&/^[0-9a-f]{64}$/.test(r.hash);
  const sameRef=(a,b)=>a?.id===b?.id&&a?.version===b?.version&&a?.hash===b?.hash;
  const AUDIENCE_LABELS={all:'All recorded streams',private:'Private / local records',direct:'Addressed messages',room:'Room / broadcast posts',unknown:'Audience unknown',action:'Tools / task activity'};
  const audienceList=x=>Array.isArray(x)&&x.length<=LIMITS.actors&&x.every(id=>bounded(id,200))&&new Set(x).size===x.length;
  function audienceFor(row,{actor=null,recipients=[],room=null,kind='message',visibility,channelName=null}={}) {
    const descriptor=row?.audience,originalVisibility=visibility??row?.visibility,unknown=note=>({kind:'unknown',label:'Audience unknown',recipient_ids:[...recipients],member_ids:[],room_id:room,channel_name:channelName,basis:'unknown_or_conflicting_declaration',note});
    if(descriptor!==undefined&&(!descriptor||typeof descriptor!=='object'||Array.isArray(descriptor)))return unknown('The recorded audience descriptor is malformed.');
    if(descriptor?.recipient_ids!==undefined&&!audienceList(descriptor.recipient_ids)||descriptor?.member_ids!==undefined&&!audienceList(descriptor.member_ids))return unknown('The recorded audience IDs are malformed or exceed the display bound.');
    if(descriptor?.recipient_ids!==undefined&&recipients.length&&JSON.stringify(descriptor.recipient_ids)!==JSON.stringify(recipients))return unknown('Audience recipients conflict with recorded addressing.');
    const ids=descriptor?.recipient_ids??recipients,members=descriptor?.member_ids??[],declaredRoom=descriptor?.room_id??room;
    if(descriptor?.room_id!==undefined&&(!bounded(descriptor.room_id,200)||room&&descriptor.room_id!==room))return unknown('The audience room conflicts with the recorded channel.');
    if(descriptor?.owner_id!==undefined&&descriptor.owner_id!==actor)return unknown('The local record owner conflicts with its actor.');
    const alias=x=>x==='public'?'broadcast':x==='local'?'private':x;
    const declared=alias(originalVisibility??descriptor?.kind);
    if(originalVisibility!==undefined&&descriptor?.kind!==undefined&&alias(originalVisibility)!==alias(descriptor.kind))return unknown('Visibility and audience declarations conflict.');
    if(declared!==undefined&&!['private','direct','room','broadcast','unknown'].includes(declared))return unknown('The recorded visibility is not recognized.');
    const reasoning=kind==='reasoning.recorded'||row?.message_type==='private_thought'||row?.message_type==='recorded_reasoning';
    if(reasoning&&ids.length)return unknown('A recorded local reasoning item also addresses peers; it is not treated as private.');
    if(reasoning&&declared!==undefined&&declared!=='private'&&declared!=='unknown')return unknown('Reasoning and wider visibility declarations conflict.');
    let type=reasoning?'private':declared==='private'?'private':declared==='room'?'room':declared==='broadcast'?'room':ids.length?'direct':'unknown';
    if(type==='private'&&ids.some(id=>id!==actor))return unknown('A private declaration also names peer recipients; the audience is unresolved.');
    if(declared==='direct'&&!ids.some(id=>id!==actor))return unknown('Direct visibility was declared without a recorded peer recipient.');
    if(type==='room'&&declared==='room'&&!declaredRoom&&!channelName)return unknown('Room visibility has no recorded channel identity.');
    const label=reasoning?'Local recorded reasoning':type==='private'?'Private recorded item':type==='direct'?'Addressed message':type==='room'?(declared==='broadcast'?'Declared broadcast post':'Declared room post'):'Audience unknown';
    const note=reasoning?'Producer-recorded exposed rationale or local log; hidden model reasoning is not available.':type==='private'?'Explicit private/local declaration; no peer exposure is inferred.':type==='direct'?'Only the recorded addressed IDs are known; wider visibility and reading are not established.':type==='room'?(members.length?'Members are explicitly declared; receipt or reading is not established.':'Room membership and reading are not supplied. Broadcast does not identify its readers.'):'No private or broadcast audience is inferred from empty addressing or a room tag.';
    return {kind:type,label,recipient_ids:[...ids],member_ids:[...members],room_id:declaredRoom,channel_name:channelName,recorded_visibility:declared??null,basis:reasoning?'explicit_recorded_reasoning':declared?'explicit_visibility':ids.length?'explicit_recipient_ids':'unknown',note};
  }
  const audienceMatches=(event,state)=>state.audience==='all'||(event.audience?.kind||'unknown')===state.audience;
  const audienceTag=event=>`<span class="sr-audience-tag sr-audience-${event.audience?.kind||'unknown'}">${esc(event.audience?.label||'Audience unknown')}</span>`;
  function time(value) {
    if(typeof value!=='string'||value.length>64)return null;
    const match=value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})$/);
    if(!match)return null;
    const [year,month,day,hour,minute,second]=match.slice(1,7).map(Number);
    if(year<100||month<1||month>12||day<1||day>new Date(Date.UTC(year,month,0)).getUTCDate()||hour>23||minute>59||second>59)return null;
    if(match[8]!=='Z'&&(Number(match[8].slice(1,3))>23||Number(match[8].slice(4,6))>59))return null;
    const result=Date.parse(value);return Number.isFinite(result)?result:null;
  }
  function exactTimeKey(value,stamp) {
    if(stamp===null)return null;
    const fraction=(value.match(/\.(\d{1,6})/)?.[1]||'').padEnd(6,'0');
    const whole=Date.parse(value.replace(/\.\d{1,6}(?=Z|[+-]\d{2}:\d{2}$)/,''));
    return (BigInt(whole)*1000n+BigInt(fraction||'0')).toString();
  }
  function normalize(record,{runIndex=0}={}) {
    if(['experiment','village_access_experiment','village_recovery_experiment'].includes(record?.kind))return normalizeStudyRun(record,runIndex);
    if(record?.kind==='observability_run')return normalizeEventRun(record);
    const unavailable=reason=>({available:false,reason,limits:{...LIMITS}});
    if(!validRef(record)||(record.kind!==undefined&&record.kind!=='dataset'))return unavailable('An exact saved dataset identity is required.');
    const rows=record.payload?.messages;
    if(!Array.isArray(rows)||rows.length>LIMITS.messages)return unavailable('The supplied chat selection is missing or exceeds the replay bound.');
    const seen=new Set(),authors=new Map(),events=[],warnings=new Set();let totalText=0;
    for(let order=0;order<rows.length;order++) {
      const row=rows[order];
      if(!row||!bounded(row.id,200)||seen.has(row.id)||typeof row.content!=='string'||row.content.length>LIMITS.messageCharacters)return unavailable('Messages need unique source IDs and bounded text. No rows were silently omitted.');
      seen.add(row.id);totalText+=row.content.length;
      if(totalText>LIMITS.textCharacters)return unavailable('The supplied message text exceeds the replay memory bound.');
      const speaker=bounded(row.speaker_id,200)?row.speaker_id:null,type=['agent','user'].includes(row.speaker_type)?row.speaker_type:'unknown';
      const actorKey=speaker?type+':'+speaker:'unknown-author';
      let label=bounded(row.agent_name,300)?row.agent_name:speaker?clip(speaker,16):'Unknown author';
      if(!authors.has(actorKey))authors.set(actorKey,{key:actorKey,id:speaker,type,name:masked(label),mentionName:bounded(row.agent_name,300)&&row.agent_name!==speaker?row.agent_name:null});
      else if(authors.get(actorKey).name!==masked(label))warnings.add('One author has multiple saved display names; the first retained label is used.');
      const timestamp=row.timestamp??row.created_at??null,stamp=time(timestamp);
      if(stamp===null)warnings.add('Missing or invalid timestamps: untimed posts follow timed posts in source order. Their chronology is unknown.');
      if(!speaker)warnings.add('Some posts have no saved speaker identity; the unknown-author avatar is a display placeholder.');
      const room=bounded(row.room_id,200)?row.room_id:'[room unknown]';
      if(room==='[room unknown]')warnings.add('Some posts lack a room identity; no room membership is inferred.');
      if(row.recipient_ids!==undefined&&!audienceList(row.recipient_ids))return unavailable('Recorded recipients must be a bounded unique ID list.');
      const audience=audienceFor(row,{actor:speaker,recipients:row.recipient_ids||[],room:room==='[room unknown]'?null:room,channelName:bounded(row.channel_name,1000)?masked(row.channel_name):null});
      events.push({id:row.id,actor:actorKey,room,text:masked(row.content),timestamp,stamp,time_key:exactTimeKey(timestamp,stamp),sourceOrder:order,
        content_hash:typeof row.content_hash==='string'?clip(row.content_hash,128):null,
        reply_to:bounded(row.reply_to,200)?row.reply_to:null,mentions:[],reply:null,audience,addresses:[]});
    }
    if(authors.size>LIMITS.actors)return unavailable('The source contains more than 64 authors; choose a smaller explicit selection.');
    events.sort((a,b)=>a.stamp===null&&b.stamp===null?a.sourceOrder-b.sourceOrder:a.stamp===null?1:b.stamp===null?-1:a.time_key===b.time_key?a.sourceOrder-b.sourceOrder:BigInt(a.time_key)<BigInt(b.time_key)?-1:1);
    const actors=[...authors.values()].sort((a,b)=>a.key<b.key?-1:a.key>b.key?1:0),byId=new Map();
    let human=0;
    for(const actor of actors)if(actor.type==='user') {
      human++;
      if(actor.name===actor.id||/^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(actor.name)||!/[\p{L}]/u.test(actor.name)||actor.name.length>80||/[<>{}\r\n]/.test(actor.name)||/^https?:|^\[credential-shaped/i.test(actor.name))actor.name='Human participant '+human;
    }
    actors.forEach((actor,index)=>{actor.color=COLORS[index%COLORS.length];actor.index=index;});
    events.forEach((event,index)=>{event.index=index;byId.set(event.id,event);if(index&&event.time_key!==null&&event.time_key===events[index-1].time_key)warnings.add('Equal timestamps retain source order for display only; this does not order an interaction.');});
    const names=new Map();
    for(const actor of actors)if(actor.type==='agent'&&actor.mentionName&&actor.mentionName.length>=3){const key=actor.mentionName.toLowerCase();names.set(key,[...(names.get(key)||[]),actor]);}
    const patterns=[];
    for(const matches of names.values()) {
      if(matches.length>1){warnings.add('Ambiguous shared display names are excluded from mention lines.');continue;}
      const actor=matches[0],name=actor.mentionName.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
      patterns.push({actor,pattern:new RegExp('(^|[^\\p{L}\\p{N}_])'+name+'(?=$|[^\\p{L}\\p{N}_])','iu')});
    }
    for(const event of events) {
      event.addresses=event.audience.kind==='direct'||event.audience.kind==='room'?actors.filter(actor=>actor.id&&event.audience.recipient_ids.includes(actor.id)).map(actor=>actor.key):[];
      for(const {actor,pattern} of patterns) {
        if(actor.key!==event.actor&&pattern.test(event.text))event.mentions.push(actor.key);
      }
      if(event.reply_to) {
        const target=byId.get(event.reply_to);
        if(target&&target.room===event.room&&target.index<event.index)event.reply={actor:target.actor,message_id:target.id};
        else warnings.add('Some explicit reply fields have missing, later or other-room targets; no reply line is drawn for them.');
      }
    }
    const declaredExample=record.payload?.provenance?.synthetic===true||record.payload?.provenance?.kind==='synthetic_fixture';
    return {available:true,mode:'chat',ref:{id:record.id,version:record.version,hash:record.hash},actors,events,
      rooms:[...new Set(events.map(event=>event.room))].sort(),warnings:[...warnings],example:declaredExample,
      limits:{...LIMITS},scope:'Replay of saved chat. Posts do not prove who read them.',
      technical_scope:'Observed saved posts. Name references and explicit reply fields are not delivery, reading, handoff or causal influence.'};
  }
  function safeContents(value) {
    let count=0;
    function walk(v,depth) {
      if(++count>LIMITS.artifactItems||depth>8)throw new Error('Artifact display bound');
      if(v===null||typeof v==='boolean')return v;
      if(typeof v==='number'){if(!Number.isFinite(v))throw new Error('Nonfinite artifact');return v;}
      if(typeof v==='string'){if(v.length>LIMITS.messageCharacters)throw new Error('Artifact text bound');return masked(v);}
      if(Array.isArray(v))return v.map(item=>walk(item,depth+1));
      if(v&&typeof v==='object'&&Object.getPrototypeOf(v)===Object.prototype) {
        const result=Object.create(null);
        for(const key of Object.keys(v)){if(key.length>200)throw new Error('Artifact key bound');result[masked(key)]=/^(?:api[_-]?key|password|access[_-]?token|refresh[_-]?token|authorization|secret)$/i.test(key)?'[sensitive field masked]':walk(v[key],depth+1);}
        return result;
      }
      throw new Error('Unsupported artifact shape');
    }
    try {const copy=walk(value,0),text=JSON.stringify(copy);return text.length<=LIMITS.messageCharacters?text:null;}catch(_){return null;}
  }
  const binary=value=>value===true||value===1?1:value===false||value===0?0:null;
  function normalizeStudyRun(record,runIndex=0) {
    const unavailable=reason=>({available:false,reason,limits:{...LIMITS}});
    const recovery=record?.kind==='village_recovery_experiment',village=recovery||record?.kind==='village_access_experiment';
    if(!validRef(record)||!['experiment','village_access_experiment','village_recovery_experiment'].includes(record.kind))return unavailable('An exact saved experiment identity is required.');
    if(village&&(!sameRef(record.payload?.source_refs?.dataset_ref,record.payload?.protocol?.grounding?.source_ref)||record.payload?.protocol?.environment?.kind!==(recovery?'single_document_reference_repair':'village_document_access_repair')||!record.payload?.protocol?.grounding?.evidence_ids?.length))return unavailable('Village replay requires its exact incident source and registered world.');
    const runs=record.payload?.runs;
    if(!Array.isArray(runs)||runs.length>LIMITS.runs||!Number.isSafeInteger(runIndex)||runIndex<0||runIndex>=runs.length)return unavailable('Choose a recorded run within the bounded experiment.');
    const run=runs[runIndex],turns=run?.turns;
    if(!Array.isArray(turns)||turns.length>LIMITS.turns)return unavailable('This run has no bounded saved turn sequence.');
    const actors=new Map(),events=[],seen=new Set();let totalText=0;
    const actor=id=>{if(!actors.has(id))actors.set(id,{key:id,id,type:'agent',name:masked(recovery?({ethics_owner:'Document owner',auditor:'Teammate'}[id]||id.replace(/_/g,' ')):village?id.replace(/_/g,' '):id),mentionName:null});};
    for(let i=0;i<turns.length;i++) {
      const turn=turns[i];
      if(!turn||!bounded(turn.agent_id,200)||!Number.isSafeInteger(turn.step)||turn.step<0||seen.has(turn.step)||(i&&turn.step<=turns[i-1].step))return unavailable('Saved turn ordinals and roles must be unique, increasing and bounded.');
      seen.add(turn.step);actor(turn.agent_id);
      const action=turn.action&&typeof turn.action==='object'&&!Array.isArray(turn.action)?turn.action:{},result=turn.tool_result&&typeof turn.tool_result==='object'&&!Array.isArray(turn.tool_result)?turn.tool_result:{};
      const name=bounded(action.action,100)?action.action:'unknown_action',artifact=bounded(action.document_id,200)?masked(action.document_id):bounded(action.document_key,200)?masked(action.document_key):bounded(action.artifact_id,200)?masked(action.artifact_id):null;
      const ok=typeof result.ok==='boolean'?result.ok:null;
      const recipient=bounded(action.recipient,200)?action.recipient:null;
      if(name==='send_message'&&recipient&&recipient!=='all')actor(recipient);
      if(typeof action.message==='string'&&action.message.length>LIMITS.messageCharacters)return unavailable('A saved message exceeds the replay bound.');
      let contents=null;
      if(Object.prototype.hasOwnProperty.call(result,'contents')){contents=safeContents(result.contents);if(contents===null)return unavailable('Returned artifact contents exceed the finite display bound.');}
      if(village){contents=safeContents(result);if(contents===null)return unavailable('Returned proxy receipt exceeds the finite display bound.');}
      const message=name==='send_message'&&typeof action.message==='string'?masked(action.message):null;
      if(action.rationale!==undefined&&(typeof action.rationale!=='string'||action.rationale.length>LIMITS.messageCharacters))return unavailable('Recorded decision summaries must be bounded text.');
      const rationale=typeof action.rationale==='string'?masked(action.rationale):null;
      const title=({inspect_artifact:'Inspect artifact',repair_artifact:'Repair artifact',publish_artifact:'Publish artifact',send_message:'Send message',wait:'Wait',open_url:'Open document link',drive_search:'Find a document in Drive',inspect_document:'Read document contents',switch_session:'Change browser account',copy_current_url:'Copy the current link',request_access:'Ask the owner for access',grant_access:'Grant access',edit_document:'Edit document',copy_link:'Copy document link',recreate_document:'Create a document copy'})[name]||'Recorded action: '+masked(name.replace(/_/g,' '));
      const text=message||title+(artifact?' · '+artifact:'');
      totalText+=text.length+(contents?.length||0)+(rationale?.length||0);if(totalText>LIMITS.textCharacters)return unavailable('The recorded run exceeds the text display bound.');
      events.push({id:'turn-'+i,index:i,turn_index:i,step:turn.step,actor:turn.agent_id,room:village?'Document project':'Artifact workspace',text,timestamp:null,stamp:null,sourceOrder:i,
        content_hash:null,mentions:[],reply:null,kind:'action',action:name,title,artifact,recipient,ok,contents,
        artifact_version:Number.isSafeInteger(result.version)&&result.version>=0?result.version:null,
        tool_message_id:bounded(result.message_id,200)?result.message_id:null,
        error:bounded(result.error,1000)?masked(result.error):null,
        deliveries:name==='send_message'&&ok===true&&recipient?(village&&audienceList(result.delivered_recipient_ids)?result.delivered_recipient_ids:[recipient]):[],rationale,
        audience:name==='send_message'?(village&&recipient==='all'?{kind:'room',label:'Experimental team room',room_id:'village-access-room',member_ids:[...record.payload.protocol.environment.agents],recipient_ids:[],note:'Dispatch is recorded; reading and influence are not established.'}:audienceFor(action,{actor:turn.agent_id,recipients:recipient?[recipient]:[]})):{kind:'action',label:'Recorded tool / task action',note:'A tool action is not a chat message.'}});
    }
    if(actors.size>LIMITS.actors)return unavailable('The saved run exceeds the role display bound.');
    const roles=[...actors.values()].sort((a,b)=>a.key<b.key?-1:a.key>b.key?1:0);
    roles.forEach((role,i)=>{role.color=COLORS[i%COLORS.length];role.index=i;});
    const outcomes=run.outcomes&&typeof run.outcomes==='object'?run.outcomes:{};
    return {available:true,mode:'study',ref:{id:record.id,version:record.version,hash:record.hash},run_index:runIndex,run_id:bounded(run.run_id,200)?run.run_id:null,
      actors:roles,events,rooms:[village?'Document project':'Artifact workspace'],village,recovery,warnings:['Steps are recorded turn ordinals, not wall-clock time. Request construction and a successful send tool result do not establish provider consumption or recipient reading.'],
      example:record.payload?.agent_mode==='offline'||record.payload?.agent_mode==='scripted',limits:{...LIMITS},
      complete:record.payload?.status==='complete',outcomes:{success:binary(recovery?outcomes.verified_repaired_reference:village?outcomes.verified_usable_project:outcomes.success),published:binary(outcomes.published),incorrect_publication:binary(outcomes.incorrect_publication),avoidable_recreations:outcomes.avoidable_recreations},
      scope:'Replay of a saved test. Sending a message does not prove it was read.',
      technical_scope:village?'Fresh LLM document-project actions in the registered, source-motivated proxy world. Original Google state and historical model policies are not reproduced. Returned tools are executed and independently replayed; sends do not establish reading or influence.':'Recorded artifact-test actions and returned tool results. Tool-confirmed sends show dispatch in this environment; they do not establish reading, understanding or causal influence.'};
  }
  const EVENT_TITLES={'agent.registered':'Agent joins','task.created':'Task created','task.assigned':'Task assigned','task.completed':'Task completed',
    'message.sent':'Message sent','reasoning.recorded':'Local reasoning recorded','tool.called':'Tool called','tool.returned':'Tool returned','artifact.updated':'Artifact updated','intervention.delivered':'Intervention logged'};
  function normalizeEventRun(record) {
    const unavailable=reason=>({available:false,reason,limits:{...LIMITS}}),payload=record?.payload,source=payload?.source,run=payload?.run;
    if(!validRef(record)||record.kind!=='observability_run'||payload?.schema_version!=='societylab.events.v1'||!source||!bounded(source.id,200)||!bounded(source.name,300)||!['authored_example','telemetry'].includes(source.kind)||!run||!bounded(run.id,200))return unavailable('A saved event run with a supported source declaration is required.');
    const rows=payload.events;
    if(!Array.isArray(rows)||rows.length>LIMITS.messages)return unavailable('The saved event run is missing or exceeds the replay bound.');
    const events=[],ids=new Set(),authors=new Map();let totalText=0;
    const needId=x=>bounded(x,200),idList=x=>Array.isArray(x)&&x.length<=LIMITS.actors&&x.every(needId)&&new Set(x).size===x.length;
    const see=(id,index)=>{if(id&&!authors.has(id))authors.set(id,{key:id,id,name:'Participant '+(authors.size+1),type:'unknown',first_seen:index,name_event:null});};
    for(let i=0;i<rows.length;i++) {
      const row=rows[i],data=row?.data;
      if(!row||!needId(row.id)||ids.has(row.id)||!Object.prototype.hasOwnProperty.call(EVENT_TITLES,row.kind)||!data||typeof data!=='object'||Array.isArray(data)||time(row.occurred_at)===null)return unavailable('Event IDs, event types, timestamps and data must be valid. No event was silently omitted.');
      ids.add(row.id);const kind=row.kind,actor=row.actor_id??null,task=row.task_id??null;
      if(actor!==null&&!needId(actor)||task!==null&&!needId(task)||row.parent_task_id!==undefined&&!needId(row.parent_task_id))return unavailable('Event identities must be bounded strings.');
      if(['agent.registered','message.sent','reasoning.recorded','tool.called','tool.returned','artifact.updated','intervention.delivered'].includes(kind)&&!actor)return unavailable('This recorded event requires an explicit actor identity.');
      if(kind.startsWith('task.')&&!task)return unavailable('Task events require an explicit task identity.');
      if(row.recipient_ids!==undefined&&!idList(row.recipient_ids))return unavailable('Recipient identities must be an explicit bounded unique list.');
      if(['message.sent','intervention.delivered'].includes(kind)&&!idList(row.recipient_ids))return unavailable('Message and intervention events require a recorded recipient list. An empty list does not imply a broadcast.');
      if(kind==='reasoning.recorded'&&(!idList(row.recipient_ids)||row.recipient_ids.length))return unavailable('Recorded local reasoning requires an explicit empty recipient list; peer sends are separate events.');
      let text=EVENT_TITLES[kind],detail=null,name=null,success=null,title=null,assignees=[],artifact=null,revision=null,call=null,tool=null;
      if(kind==='agent.registered'){if(!bounded(data.name,300))return unavailable('Agent registrations require a bounded display name.');name=masked(data.name);text=name+' joins the run';}
      if(kind==='task.created'){if(!bounded(data.title,2000))return unavailable('Task creation requires a bounded title.');title=masked(data.title);text='New task: '+title;}
      if(kind==='task.assigned'){if(!idList(data.assignee_ids))return unavailable('Task assignments require a bounded unique assignee list.');assignees=[...data.assignee_ids];text='Task assigned to '+assignees.length+' participant'+(assignees.length===1?'':'s');}
      if(kind==='task.completed'){if(typeof data.success!=='boolean')return unavailable('Task completion requires an explicit boolean success declaration.');success=data.success;text=data.success?'Task completed successfully':'Task completed without success';}
      if(['message.sent','reasoning.recorded','intervention.delivered'].includes(kind)){if(typeof data.content!=='string'||data.content.length>LIMITS.messageCharacters)return unavailable('Recorded message text exceeds the replay bound.');text=masked(data.content);}
      if(data.channel_id!==undefined&&!needId(data.channel_id)||data.reply_to_message_id!==undefined&&!needId(data.reply_to_message_id))return unavailable('Channel and reply identities must be bounded strings when supplied.');
      if(kind==='intervention.delivered'&&!needId(data.intervention_id))return unavailable('An intervention needs its recorded identity.');
      if(['tool.called','tool.returned'].includes(kind)) {
        if(!needId(data.call_id))return unavailable('Tool events require a recorded call identity.');call=data.call_id;
        if(kind==='tool.called'){if(!bounded(data.tool_name,200))return unavailable('Tool calls require a bounded tool name.');tool=masked(data.tool_name);text='Calls '+tool;}
        else {if(typeof data.success!=='boolean')return unavailable('Tool returns require an explicit boolean success declaration.');success=data.success;text=success?'Tool reports success':'Tool reports failure';}
        const key=kind==='tool.called'?'arguments':'output';
        if(Object.prototype.hasOwnProperty.call(data,key)){detail=safeContents(data[key]);if(detail===null)return unavailable('Tool details exceed the finite display bound.');}
      }
      if(kind==='artifact.updated'){if(!needId(data.artifact_id)||!needId(data.revision_id))return unavailable('Artifact updates require explicit artifact and revision identities.');artifact=data.artifact_id;revision=data.revision_id;text=bounded(data.change_summary,2000)?masked(data.change_summary):'Artifact revision recorded';}
      if(data.channel_name!==undefined&&!bounded(data.channel_name,1000))return unavailable('Recorded channel names must be bounded text.');
      const messageLike=['message.sent','reasoning.recorded','intervention.delivered'].includes(kind),channel=needId(data.channel_id)?data.channel_id:null;
      const audience=messageLike?audienceFor({...row,...data},{actor,recipients:row.recipient_ids||[],room:channel,kind,visibility:data.visibility,channelName:data.channel_name?masked(data.channel_name):null}):{kind:'action',label:'Recorded tool / task activity',note:'This is not a chat message.'};
      totalText+=text.length+(detail?.length||0);if(totalText>LIMITS.textCharacters)return unavailable('The event run exceeds the text display bound.');
      events.push({id:row.id,index:i,actor,task_id:task,parent_task_id:row.parent_task_id??null,room:messageLike?(channel||data.channel_name||'[room unknown]'):'Event stream',text,timestamp:row.occurred_at,stamp:time(row.occurred_at),time_key:exactTimeKey(row.occurred_at,time(row.occurred_at)),sourceOrder:i,
        kind:'telemetry',event_kind:kind,title:EVENT_TITLES[kind],registered_name:name,task_title:title,success,assignees,artifact,revision,call_id:call,tool_name:tool,detail,
        channel,mentions:[],reply:null,reply_to:needId(data.reply_to_message_id)?data.reply_to_message_id:null,audience,
        addresses:['message.sent','intervention.delivered'].includes(kind)&&audience.kind!=='private'?[...row.recipient_ids]:[],content_hash:null});
    }
    events.sort((a,b)=>a.time_key===b.time_key?a.sourceOrder-b.sourceOrder:BigInt(a.time_key)<BigInt(b.time_key)?-1:1);
    const byId=new Map(),warnings=new Set();
    if(events.some((event,index)=>event.sourceOrder!==index))warnings.add('Events arrived out of timestamp order. This view sorts the recorded times and retains each original source position. Display order is not causal order.');
    events.forEach((event,i)=>{event.index=i;byId.set(event.id,event);see(event.actor,i);for(const id of [...event.addresses,...event.assignees])see(id,i);
      if(i&&event.time_key===events[i-1].time_key)warnings.add('Equal timestamps keep source order for display; they do not prove which event influenced another.');
      if(event.event_kind==='agent.registered'){const actor=authors.get(event.actor);if(actor.name_event===null){actor.name=event.registered_name;actor.name_event=i;}}
    });
    for(const event of events)if(event.reply_to) {
      const target=byId.get(event.reply_to);
      if(target&&target.event_kind==='message.sent'&&target.index<event.index&&target.channel===event.channel&&target.actor)event.reply={actor:target.actor,message_id:target.id};
      else warnings.add('Some reply fields do not resolve to an earlier message in the same declared channel.');
    }
    if(authors.size>LIMITS.actors)return unavailable('The event run exceeds the participant display bound.');
    if(new Set(events.filter(e=>e.task_id).map(e=>e.task_id)).size>256)return unavailable('The event run exceeds the task-board bound.');
    const actors=[...authors.values()];actors.forEach((actor,i)=>{actor.color=COLORS[i%COLORS.length];actor.index=i;});
    return {available:true,mode:'telemetry',ref:{id:record.id,version:record.version,hash:record.hash},actors,events,rooms:['[all channels]',...[...new Set(events.map(event=>event.room))].sort()],source:{id:source.id,name:masked(source.name),kind:source.kind},run:{id:run.id,name:bounded(run.name,300)?masked(run.name):null},
      warnings:[...warnings],example:source.kind==='authored_example',limits:{...LIMITS},scope:source.kind==='authored_example'?'Replay of example events. This demonstrates the interface, not observed agent behavior.':'Replay of recorded events. Logged recipients do not prove who read a message.',
      technical_scope:'Host-supplied societylab.events.v1 declarations. Event labels, task success, tool success and intervention delivery are recorded fields, not independently re-executed facts. No recipient consumption, mental state or causal mechanism is inferred.'};
  }
  function visibleActors(model,state) {
    if(model.mode!=='telemetry')return model.actors;
    return model.actors.filter(actor=>actor.first_seen<=state.cursor).map(actor=>({...actor,name:actor.name_event!==null&&actor.name_event<=state.cursor?actor.name:'Participant '+(actor.index+1),type:actor.name_event!==null&&actor.name_event<=state.cursor?'agent':'unknown'}));
  }
  function stateFor(model,initial={}) {
    const cursor=Number.isSafeInteger(initial.cursor)?Math.max(0,Math.min(model.events.length-1,initial.cursor)):0;
    return {cursor:model.events.length?cursor:-1,room:model.rooms.includes(initial.room)?initial.room:model.events[cursor]?.room||model.rooms[0]||'',
      actor:model.actors.some(actor=>actor.key===initial.actor&&(model.mode!=='telemetry'||actor.first_seen<=cursor))?initial.actor:null,speed:[0.5,1,2,4].includes(initial.speed)?initial.speed:1,playing:false,
      audience:Object.prototype.hasOwnProperty.call(AUDIENCE_LABELS,initial.audience)?initial.audience:'all',...(model.mode==='telemetry'&&!model.rooms.includes(initial.room)?{room:'[all channels]'}:{})};
  }
  const snapshot=state=>({cursor:state.cursor,room:state.room,actor:state.actor,speed:state.speed,playing:state.playing,audience:state.audience});
  const localClock=new Intl.DateTimeFormat('en-IN',{timeZone:'Asia/Kolkata',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'});
  const clock=event=>event?.kind==='action'?'Recorded step '+event.step:event?.stamp!==null&&event?.stamp!==undefined?localClock.format(new Date(event.stamp))+' IST':'Time unknown';
  const roomLabel=(model,room)=>room==='[all channels]'?'All recorded channels':room==='[room unknown]'?'Room unknown':model.mode==='study'?(model.village?'Document project':'Artifact workspace'):model.mode==='telemetry'?(room==='Event stream'?'Task / tool activity':'Recorded channel '+(model.rooms.indexOf(room)+1)):'Team room '+(model.rooms.indexOf(room)+1);
  function avatar(actor,x,y,current,selected,count) {
    const size=selected?1.2:1;
    return `<g class="sr-avatar ${current?'sr-avatar-current':''} ${selected?'sr-avatar-selected':''}" transform="translate(${x} ${y})" data-sr-actor="${esc(actor.key)}" role="button" tabindex="0" aria-label="Focus on ${esc(actor.name)}"><title>${esc(actor.name)} · ${actor.type==='agent'?'agent':actor.type==='user'?'human':'speaker type unknown'} · ${count} recorded events so far</title><g transform="scale(${size})"><ellipse class="sr-avatar-shadow" cx="0" cy="30" rx="22" ry="8"/><circle class="sr-avatar-aura" r="36" cy="5"/><path d="M-11 13L-13 32H-3L0 20L3 32H13L11 13Z" fill="${actor.color}"/><rect x="-15" y="-3" width="30" height="23" rx="9" fill="${actor.color}"/><circle cx="0" cy="-15" r="13" fill="#ead1b5"/><path d="M-13-16Q-10-35 9-26L14-14Q4-15-4-22L-13-16" fill="#334851"/><circle cx="-4" cy="-13" r="1.3" fill="#334851"/><circle cx="5" cy="-13" r="1.3" fill="#334851"/><path d="M-3-7Q0-5 3-7" fill="none" stroke="#8e6557" stroke-width="1.2"/><rect x="15" y="2" width="8" height="13" rx="2" fill="#e9eee7"/><path d="M18 5H21M18 8H21" stroke="${actor.color}" stroke-width="1"/></g><text class="sr-avatar-label" x="0" y="55" text-anchor="middle">${esc(clip(actor.name,22))}</text><text class="sr-avatar-count" x="0" y="70" text-anchor="middle">${count} event${count===1?'':'s'}</text></g>`;
  }
  function scene(model,state) {
    const event=model.events[state.cursor],positions=new Map(),counts=new Map(),actors=visibleActors(model,state);
    for(const post of model.events.slice(0,state.cursor+1))counts.set(post.actor,(counts.get(post.actor)||0)+1);
    const focus=actors.some(actor=>actor.key===state.actor)?state.actor:null,others=focus?actors.filter(actor=>actor.key!==focus):actors;
    others.forEach((actor,index)=>{const angle=-Math.PI/2+index*2*Math.PI/Math.max(1,others.length);positions.set(actor.key,{x:320+Math.cos(angle)*210,y:220+Math.sin(angle)*135});});
    if(focus)positions.set(focus,{x:320,y:215});
    let edges='';const from=event&&positions.get(event.actor);
    const showEvent=event&&audienceMatches(event,state),localSummary=event&&state.audience==='private'&&event.rationale;
    const refs=showEvent&&event.audience?.kind!=='private'?[...(event.deliveries||[]).map(actor=>({actor,label:'tool-confirmed send'})),...(model.mode==='study'?[]:event.addresses||[]).map(actor=>({actor,label:'logged recipient'}))]:[];
    for(const ref of refs) {
      const to=positions.get(ref.actor);if(!from||!to||ref.actor===event.actor)continue;
      edges+=`<g class="sr-reference-edge"><path d="M${from.x} ${from.y}Q320 190 ${to.x} ${to.y}"/><text x="${(from.x+to.x)/2}" y="${(from.y+to.y)/2-10}" text-anchor="middle">${ref.label}</text></g>`;
    }
    const figures=actors.map(actor=>{const p=positions.get(actor.key);return avatar(actor,Number(p.x.toFixed(2)),Number(p.y.toFixed(2)),event?.actor===actor.key,focus===actor.key,counts.get(actor.key)||0);}).join('');
    const current=actors.find(actor=>actor.key===event?.actor);
    const grid=Array.from({length:20},(_,i)=>`M${i*32} 0V450`).join('')+Array.from({length:15},(_,i)=>`M0 ${i*32}H640`).join('');
    return `<svg class="sr-world" viewBox="0 0 640 450" role="group" aria-label="Illustrative author scene; click an avatar to focus"><rect width="640" height="450" rx="18" fill="#eef3e8"/><path d="${grid}" fill="none" stroke="#dfe8df" stroke-width=".6"/><ellipse cx="320" cy="240" rx="265" ry="155" fill="#e7eddf"/><path class="sr-walkway" d="M70 260Q320 130 570 260"/><g class="sr-world-decoration"><path d="M55 360L75 348L96 360L75 372Z"/><path d="M530 90L552 77L575 90L552 103Z"/><circle cx="83" cy="88" r="17"/><circle cx="552" cy="360" r="22"/></g>${edges}${figures}</svg><div class="sr-post-bubble"><span class="sr-bubble-label">${localSummary?'Recorded decision summary':event?(model.mode==='telemetry'?esc(event.title):'Recorded '+(model.mode==='study'?'action':'post'))+' · '+esc(current?.name||'Run record'):'No recorded events'}</span><p>${esc(localSummary?clip(event.rationale,220):showEvent?clip(event.text,220):event?'Current event is outside this audience filter.':'This saved selection has no events.')}</p><span>${esc(clock(event))}${showEvent?' · '+esc(event.audience?.label||'Audience unknown'):''}</span></div>`;
  }
  function chat(model,state) {
    const actors=new Map(visibleActors(model,state).map(actor=>[actor.key,actor])),prefix=model.events.slice(0,state.cursor+1),items=[];
    for(const event of prefix) {
      if(model.mode!=='study'&&state.room!=='[all channels]'&&event.room!==state.room)continue;
      const focused=!state.actor||event.actor===state.actor||(event.audience?.kind!=='private'&&(event.addresses?.includes(state.actor)||event.deliveries?.includes(state.actor)));
      if(focused&&audienceMatches(event,state))items.push({event,local:false,type:event.audience?.kind||'unknown'});
      if(model.mode==='study'&&event.rationale!==null&&event.rationale!==undefined&&(!state.actor||event.actor===state.actor)&&['all','private'].includes(state.audience))items.push({event,local:true,type:'private'});
    }
    const recent=items.slice(-40),focused=actors.get(state.actor),lanes=['private','direct','room','unknown','action'].filter(type=>recent.some(item=>item.type===type));
    function card({event,local}) {
      const person=actors.get(event.actor),audience=local?{kind:'private',label:'Recorded decision summary',note:'Saved action rationale only; hidden model reasoning is not available.'}:event.audience;
      const display=local?event.rationale:event.text,study=model.mode==='study'&&!local;
      const ids=audience?.recipient_ids||[],address=ids.length?'Logged recipients: '+ids.map(id=>esc([...actors.values()].find(actor=>actor.id===id||actor.key===id)?.name||id)).join(', '):'No recipients recorded; broadcast is not inferred.';
      const location=audience?.channel_name||(audience?.room_id?roomLabel(model,audience.room_id):null);
      return `<article class="sr-message sr-stream-${audience?.kind||'unknown'} ${state.cursor===event.index?'sr-message-current':''} ${event.event_kind==='intervention.delivered'?'sr-intervention-message':''}" data-sr-message="${esc(event.id)}"><div class="sr-message-author"><span class="sr-dot" style="background:${person?.color||'#718185'}"></span>${esc(person?.name||'Run record')}${event.event_kind==='intervention.delivered'?'<span class="sr-intervention-tag">Intervention record</span>':''}</div><span class="sr-audience-tag sr-audience-${audience?.kind||'unknown'}">${esc(audience?.label||'Audience unknown')}</span>${study?`<span class="sr-action-status ${event.ok===true?'sr-status-confirmed':event.ok===false?'sr-status-failed':''}">${event.ok===true?'Tool accepted':event.ok===false?'Tool rejected':'Tool status unknown'}</span><h3>${esc(event.title)}</h3>`:''}<p>${esc(clip(display,1200)).replace(/\n/g,'<br>')}</p>${study&&event.artifact?`<p class="sr-artifact-name">${esc(event.artifact)}</p>`:''}${audience?.kind!=='action'?`<small class="sr-audience-scope">${local||audience?.kind==='private'?'Local record of this actor; no peer exposure is inferred.':address}${location?'<br>Recorded channel: '+esc(location):''}<br>${esc(audience?.note||'Audience is not supplied.')}</small>`:''}${study&&event.contents!==null?`<details><summary>Contents returned by this tool</summary><pre>${esc(event.contents)}</pre></details>`:''}${study&&event.error?`<p class="sr-tool-error">${esc(event.error)}</p>`:''}<footer><time>${esc(clock(event))}</time><button type="button" data-sr-inspect="${esc(event.id)}">${model.mode==='study'?'Turn source':model.mode==='telemetry'?'Event source':'Source'} ↗</button></footer>${display.length>1200?'<span class="sr-window-note">Excerpt; inspect the saved source for full text.</span>':''}</article>`;
    }
    return `<div class="sr-chat-heading"><div><strong>${focused?esc(focused.name)+' · recorded streams':'Recorded streams'}</strong><span>${esc(roomLabel(model,state.room))} · ${items.length} matching records so far${model.mode==='study'?' · summaries share their original turn':''}</span></div><span class="sr-chat-status">Read only</span></div><div class="sr-chat-messages sr-streams" role="log" aria-label="Audience-separated recorded streams">${items.length>40?'<p class="sr-window-note">Showing the latest 40 matching records. Earlier records remain on the timeline.</p>':''}${lanes.map(type=>`<section class="sr-stream-lane sr-lane-${type}" aria-label="${esc(AUDIENCE_LABELS[type])}"><h3>${esc(AUDIENCE_LABELS[type])}</h3>${recent.filter(item=>item.type===type).map(card).join('')}</section>`).join('')||'<p class="sr-window-note">No matching record has appeared by this playhead. Absence here is not inactivity.</p>'}</div><div class="sr-chat-footnote">Streams group explicit recorded audiences. The timeline keeps original event order. Tools and task records are separate from messages; local records do not establish hidden thoughts or peer exposure.</div>`;
  }
  function taskboard(model,state) {
    if(model.mode==='telemetry')return eventBoard(model,state);
    if(model.mode!=='study')return '';
    if(model.village){
      const reached=model.events.slice(0,state.cursor+1),finished=model.complete&&state.cursor===model.events.length-1;
      const count=(names,ok)=>reached.filter(e=>names.includes(e.action)&&(ok===undefined||e.ok===ok)).length;
      const verdict=!finished?'Outcome appears at the end of this recorded team.':model.recovery?(model.outcomes.success===1?'The teammate opened the original document using a working link.':'The teammate did not record verified access within the saved action budget.'):model.outcomes.success===1?'All four original documents passed the registered content and independent-access check.':'The team did not satisfy the complete-project check within its action budget.';
      const recent=reached.filter(e=>e.contents&&e.ok!==null).slice(-3);
      const counters=model.recovery?`<span><b>${count(['open_url','navigate'])}</b> access attempts</span><span><b>${count(['open_url','navigate'],false)}</b> failed access attempts</span><span><b>${count(['send_message'],true)}</b> messages sent</span>`:`<span><b>${count(['open_document','navigate','open_url','press_enter'])}</b> access attempts</span><span><b>${count(['share_document','grant_access','request_access','share','revoke_access'])}</b> permission actions</span><span><b>${count(['recreate_document'])}</b> copy attempts</span><span><b>${count(['send_message'],true)}</b> messages sent</span>`;
      return `<section class="sr-taskboard" aria-label="Recorded document project activity"><div class="sr-board-title"><strong>${model.recovery?'Repair one link':'Document project'}</strong><span>Executed proxy tools</span></div><div class="sr-task-counters">${counters}</div>${recent.map(e=>`<details><summary>${esc(e.title)} · ${e.ok?'accepted':'failed'}</summary><pre>${esc(e.contents)}</pre></details>`).join('')}<p class="sr-outcome">${esc(verdict)}</p>${finished&&!model.recovery?`<p>Copies made while originals persisted: ${esc(model.outcomes.avoidable_recreations)}. This is a proxy-world measure, not a claim about historical necessity.</p>`:''}</section>`;
    }
    const prefix=model.events.slice(0,state.cursor+1),counts={inspect_artifact:0,repair_artifact:0,publish_artifact:0,send_message:0},artifacts=new Map();
    for(const event of prefix) {
      if(event.ok===true&&Object.prototype.hasOwnProperty.call(counts,event.action))counts[event.action]++;
      if(event.contents!==null&&event.ok===true&&event.artifact)artifacts.set(event.artifact,{contents:event.contents,version:event.artifact_version});
    }
    const finished=model.complete&&model.events.length>0&&state.cursor===model.events.length-1,outcome=model.outcomes;
    const verdict=!finished?'Outcome hidden until the end of the saved complete run':outcome.success===1?'Saved outcome: task correct':outcome.success===0?'Saved outcome: task incorrect':'Saved outcome: correctness unknown';
    return `<section class="sr-taskboard" aria-label="Recorded artifact activity"><div class="sr-board-title"><strong>Artifact desk</strong><span>No hidden world state</span></div><div class="sr-task-counters"><span><b>${counts.inspect_artifact}</b> inspections</span><span><b>${counts.repair_artifact}</b> repairs accepted</span><span><b>${counts.send_message}</b> sends accepted</span><span><b>${counts.publish_artifact}</b> publications</span></div>${[...artifacts].map(([id,value])=>`<details><summary>${esc(id)} · last returned ${value.version===null?'version unknown':'version '+value.version}</summary><pre>${esc(value.contents)}</pre></details>`).join('')||'<p>Artifact contents have not been returned by a recorded tool.</p>'}<p class="sr-outcome ${finished&&outcome.success===0?'sr-outcome-failed':''}">${esc(verdict)}</p>${finished&&outcome.incorrect_publication===1?'<p class="sr-window-note">The saved environment score marks this publication incorrect. This view does not re-evaluate it.</p>':''}</section>`;
  }
  function eventBoard(model,state) {
    const prefix=model.events.slice(0,state.cursor+1),tasks=new Map(),tools=new Map(),artifacts=new Map();let interventions=0,toolCalls=0;
    for(const event of prefix) {
      if(event.event_kind.startsWith('task.')) {
        if(!tasks.has(event.task_id))tasks.set(event.task_id,{id:event.task_id,label:'Task '+(tasks.size+1),title:null,assignees:[],status:'Status not yet logged'});
        const task=tasks.get(event.task_id);
        if(event.event_kind==='task.created'){task.title=event.task_title;task.status='Created';}
        if(event.event_kind==='task.assigned'){task.assignees=event.assignees;task.status='Assigned';}
        if(event.event_kind==='task.completed')task.status=event.success?'Completed · success recorded':'Completed · marked unsuccessful';
      }
      if(event.event_kind==='tool.called'){toolCalls++;tools.set(event.call_id,{actor:event.actor,name:event.tool_name,status:'Awaiting return'});}
      if(event.event_kind==='tool.returned') {
        const call=tools.get(event.call_id);if(call&&call.actor===event.actor)call.status=event.success?'Success recorded':'Failure recorded';
      }
      if(event.event_kind==='artifact.updated')artifacts.set(event.artifact,{revision:event.revision,summary:event.text});
      if(event.event_kind==='intervention.delivered')interventions++;
    }
    const currentEvent=model.events[state.cursor];
    return `<section class="sr-taskboard sr-run-board" aria-label="Tasks and activity reached by the playhead"><div class="sr-board-title"><strong>Team task board</strong><span>Only events reached so far</span></div><div class="sr-task-counters"><span><b>${tasks.size}</b> tasks logged</span><span><b>${[...tasks.values()].filter(t=>t.status.startsWith('Completed')).length}</b> completions</span><span><b>${toolCalls}</b> tool calls</span><span><b>${interventions}</b> interventions</span></div>${[...tasks.values()].slice(-8).map(task=>`<div class="sr-task-card"><strong>${esc(task.title||task.label+' · title not yet logged')}</strong><span>${esc(task.status)}</span></div>`).join('')||'<p>No task has been logged yet.</p>'}${tasks.size>8?'<p class="sr-window-note">Showing the latest eight tasks; earlier events remain on the timeline.</p>':''}${[...tools.values()].slice(-4).map(tool=>`<div class="sr-tool-row"><span>${esc(tool.name)}</span><small>${esc(tool.status)}</small></div>`).join('')}${[...artifacts].slice(-4).map(([id,artifact])=>`<details><summary>Artifact update · ${esc(clip(id,40))}</summary><p>${esc(artifact.summary)}</p><code>Revision: ${esc(artifact.revision)}</code></details>`).join('')}${currentEvent?.detail!==null&&currentEvent?.detail!==undefined?`<details class="sr-current-detail"><summary>${currentEvent.event_kind==='tool.called'?'This call’s logged arguments':'This return’s logged output'}</summary><pre>${esc(currentEvent.detail)}</pre></details>`:''}${currentEvent?`<div class="sr-current-event"><span>${esc(currentEvent.title)}</span><button type="button" data-sr-inspect="${esc(currentEvent.id)}">Event source ↗</button></div>`:''}<p class="sr-window-note">These are recorded status declarations. No task or tool is being run here.</p></section>`;
  }
  function feed(model,state) {
    const actors=new Map(visibleActors(model,state).map(actor=>[actor.key,actor]));
    return model.events.slice(Math.max(0,state.cursor-7),state.cursor+1).reverse().map(event=>`<button type="button" class="sr-feed-row ${event.index===state.cursor?'sr-feed-current':''}" data-sr-seek="${event.index}"><time>${esc(clock(event))}</time><span style="color:${actors.get(event.actor)?.color||'#718185'}">${esc(actors.get(event.actor)?.name||'Run record')}</span>${audienceTag(event)}<small>${esc(audienceMatches(event,state)?clip(event.text,90):state.audience==='private'&&event.rationale?clip(event.rationale,90):'Outside this audience filter')}</small></button>`).join('');
  }
  function current(model,state) {
    const event=model.events[state.cursor];return event?`${state.cursor+1} / ${model.events.length} ${model.mode==='study'?'turns':model.mode==='telemetry'?'events':'posts'} · ${clock(event)}`:'No events in this selection';
  }
  function body(model,state,example) {
    const study=model.mode==='study',telemetry=model.mode==='telemetry',unit=study?'turn':telemetry?'event':'post',actors=visibleActors(model,state);
    return `<header class="sr-heading"><div><span class="sr-kicker">SOCIETY REPLAY · READ ONLY</span><h2>${study?'Watch the work unfold.':telemetry?'Inside the agent team.':'A room full of agents.'}</h2><p>${telemetry?esc(model.source.name)+' · '+(example?'Example events, not a live run.':'Recorded events, not a live run.'):study?(example?'Scripted saved test · demonstrates the harness, not model behavior.':'Recorded saved test turns · animated presentation, not a new experiment.'):(example?'Example source · illustration, not a model result.':'Recorded saved posts · animated presentation, not a simulation.')}</p></div><span class="sr-live-label">No live agents running</span></header>
      <div class="sr-scope">${esc(model.scope)}</div>
      ${model.warnings.length?`<details class="sr-warning"><summary>Ordering and source caveats · ${model.warnings.length}</summary><ul>${model.warnings.map(value=>`<li>${esc(value)}</li>`).join('')}</ul></details>`:''}
      <div class="sr-toolbar"><div class="sr-play-controls"><button type="button" data-sr-action="prev" aria-label="Previous recorded ${unit}">‹</button><button type="button" class="sr-play-button" data-sr-action="play" aria-label="Play recorded events">▶ Play</button><button type="button" data-sr-action="next" aria-label="Next recorded ${unit}">›</button><button type="button" data-sr-action="overview">Whole society</button></div>
        <label>Playback pace<select data-sr-speed aria-label="Playback pace">${[0.5,1,2,4].map(speed=>`<option value="${speed}" ${state.speed===speed?'selected':''}>${speed}×</option>`).join('')}</select></label>
        <label>Stream<select data-sr-audience aria-label="Recorded audience stream">${Object.entries(AUDIENCE_LABELS).map(([key,label])=>`<option value="${key}" ${state.audience===key?'selected':''}>${esc(label)}</option>`).join('')}</select></label>
        ${study||model.rooms.length<2?'':`<label>Room<select data-sr-room aria-label="Recorded room">${model.rooms.map(room=>`<option value="${esc(room)}" title="Exact room ID: ${esc(room)}" ${room===state.room?'selected':''}>${esc(roomLabel(model,room))}</option>`).join('')}</select></label>`}
        <label>Focus<select data-sr-focus aria-label="Author focus"><option value="">Whole society</option>${actors.map(actor=>`<option value="${esc(actor.key)}" ${state.actor===actor.key?'selected':''}>${esc(actor.name)}${actor.type==='user'?' · human':''}</option>`).join('')}</select></label></div>
      <div class="sr-layout"><div class="sr-scene-panel"><div class="sr-scene-title"><span data-sr-focus-label>${state.actor?'Person focus':'Society overview'}</span><small>${study||telemetry?'See who acted. Click a person to follow them.':'See who spoke. Click a person to follow them.'}</small></div><div class="sr-scene" data-sr-scene>${scene(model,state)}</div><div class="sr-legend"><span>● ${study||telemetry?'Acting participant':'Speaking participant'}</span><span>${study?'— tool-confirmed send':'— logged recipient'}</span><span>Only explicit addressing draws lines. Positions are for display.</span></div><div data-sr-board>${taskboard(model,state)}</div></div><aside class="sr-chat" data-sr-chat>${chat(model,state)}</aside></div>
      <div class="sr-timeline"><div class="sr-timeline-label"><strong data-sr-current aria-live="polite">${esc(current(model,state))}</strong><small>${study?'One saved turn per tick; no wall-clock time is invented.':telemetry?'One saved event per tick; source time is compressed.':'One recorded post per tick; source time is compressed.'}</small></div><input type="range" data-sr-scrub min="0" max="${Math.max(0,model.events.length-1)}" value="${Math.max(0,state.cursor)}" aria-label="Replay playhead" ${model.events.length?'':'disabled'}><div class="sr-feed" data-sr-feed>${feed(model,state)}</div></div>
      <details class="sr-ref"><summary>Advanced · exact sources and replay limits</summary><p>${esc(model.ref.id)} · version ${model.ref.version}${study?' · run index '+model.run_index:''}</p><code>${esc(model.ref.hash)}</code><p>${esc(model.technical_scope)}</p><p>Private/local lanes require explicit source declarations or a saved decision summary. Empty recipients and room tags do not establish an audience. Hidden model reasoning is unavailable. Mention and reply references are not communication edges.</p>${telemetry?`<p>Source: <code>${esc(model.source.id)}</code> · kind ${esc(model.source.kind)}<br>Run: <code>${esc(model.run.id)}</code></p>`:study?'':`<dl>${model.rooms.map(room=>`<dt>${esc(roomLabel(model,room))}</dt><dd><code>${esc(room)}</code></dd>`).join('')}${model.actors.filter(actor=>actor.type==='user').map(actor=>`<dt>${esc(actor.name)}</dt><dd><code>${esc(actor.id||'Identity unknown')}</code></dd>`).join('')}</dl>`}<p>The host supplies this identity; replay does not recompute its hash, reread sources or validate interpretations. Credential-shaped strings are masked in excerpts. ${study?'Only saved actions, optional action rationale summaries and selected returned tool fields are displayed. Hidden world state, assignment labels, request prompts and seeds are not shown. A decision summary shares its original turn and does not add a call. Task correctness is a saved outcome, revealed only at the end of a complete run.':telemetry?'Task and tool statuses update only when their events reach the playhead. Logged arguments and outputs are shown with sensitive fields masked. An intervention record is not proof of changed beliefs or treatment effect. Chat clocks use Asia/Kolkata (IST); original timestamps and source event IDs are retained.':'Room and participant labels are display names, not inferred roles. Chat clocks use Asia/Kolkata (IST); original timestamps are retained. A name reference or reply is not a delivery record; unknown targets stay unknown.'}</p></details>`;
  }
  function render({record,initialState,example,runIndex=0}={}) {
    const model=normalize(record,{runIndex});
    if(!model.available)return `<section class="sr-root sr-unavailable"><h2>Replay unavailable</h2><p>${esc(model.reason)}</p><p>No substitute source or invented events were selected.</p></section>`;
    return `<section class="sr-root" data-sr-id="${esc(model.ref.id)}" data-sr-version="${model.ref.version}" data-sr-hash="${model.ref.hash}" data-sr-mode="${model.mode}" data-sr-run="${model.mode==='study'?model.run_index:''}">${body(model,stateFor(model,initialState),example===true||model.example)}</section>`;
  }
  function peek(record,initialState,{runIndex=0}={}) {
    const model=normalize(record,{runIndex});if(!model.available)return model;
    const state=stateFor(model,initialState),event=model.events[state.cursor];
    if(model.mode==='study')return {available:true,record_ref:{...model.ref},run_index:model.run_index,state:snapshot(state),current_turn:event?{turn_index:event.turn_index,step:event.step,actor:event.actor,action:event.action,tool_ok:event.ok}:null,scope:model.scope,observed_turns:state.cursor+1,total_turns:model.events.length};
    if(model.mode==='telemetry')return {available:true,record_ref:{...model.ref},state:snapshot(state),current_event:event?{id:event.id,kind:event.event_kind,actor_id:event.actor,task_id:event.task_id,timestamp:event.timestamp}:null,scope:model.scope,observed_events:state.cursor+1,total_events:model.events.length};
    return {available:true,dataset_ref:{...model.ref},state:snapshot(state),current_message:event?{id:event.id,actor:event.actor,room_id:event.room,timestamp:event.timestamp,content_hash:event.content_hash,excerpt:clip(event.text,500)}:null,
      scope:model.scope,observed_posts:state.cursor+1,total_posts:model.events.length};
  }
  function attach(container,{record,initialState,onState,onInspect,example,runIndex=0}={}) {
    const model=normalize(record,{runIndex}),scope=container?.matches?.('.sr-root')?container:container?.querySelector?.('.sr-root');
    const empty=()=>{};empty.getState=()=>null;
    if(!scope||!model.available)return empty;
    if(scope.dataset?.srId!==model.ref.id||String(scope.dataset?.srVersion)!==String(model.ref.version)||scope.dataset?.srHash!==model.ref.hash||scope.dataset?.srMode!==model.mode||(model.mode==='study'&&scope.dataset?.srRun!==String(model.run_index)))return empty;
    let state=stateFor(model,initialState),timer=null,disposed=false;
    scope.innerHTML=body(model,state,example===true||model.example);
    const element=selector=>scope.querySelector(selector),notify=()=>{if(typeof onState==='function')onState(snapshot(state));};
    function paint() {
      if(disposed)return;
      if(model.mode==='telemetry'&&state.actor&&!visibleActors(model,state).some(actor=>actor.key===state.actor))state.actor=null;
      const put=(selector,html)=>{const node=element(selector);if(node)node.innerHTML=html;};
      put('[data-sr-scene]',scene(model,state));put('[data-sr-chat]',chat(model,state));put('[data-sr-feed]',feed(model,state));put('[data-sr-board]',taskboard(model,state));
      const log=element('.sr-chat-messages');if(log&&Number.isFinite(log.scrollHeight))log.scrollTop=log.scrollHeight;
      const label=element('[data-sr-current]');if(label)label.textContent=current(model,state);
      const focus=element('[data-sr-focus-label]');if(focus)focus.textContent=state.actor?'Person focus':'Society overview';
      const range=element('[data-sr-scrub]');if(range)range.value=String(Math.max(0,state.cursor));
      const select=element('[data-sr-focus]');if(select){if(model.mode==='telemetry')select.innerHTML='<option value="">Whole society</option>'+visibleActors(model,state).map(actor=>`<option value="${esc(actor.key)}">${esc(actor.name)}</option>`).join('');select.value=state.actor||'';}
      const room=element('[data-sr-room]');if(room)room.value=state.room;
      const speed=element('[data-sr-speed]');if(speed)speed.value=String(state.speed);
      const audience=element('[data-sr-audience]');if(audience)audience.value=state.audience;
      const button=element('[data-sr-action="play"]');if(button){button.textContent=state.playing?'Ⅱ Pause':'▶ Play';button.setAttribute('aria-label',state.playing?'Pause replay':'Play replay');}
      notify();
    }
    function pause(){state.playing=false;if(timer!==null){global.clearTimeout(timer);timer=null;}}
    function schedule(){if(disposed||!state.playing)return;timer=global.setTimeout(()=>{timer=null;if(disposed||!state.playing)return;if(state.cursor>=model.events.length-1){pause();paint();return;}state.cursor++;if(state.cursor===model.events.length-1)pause();paint();schedule();},1000/state.speed);}
    function seek(value){if(disposed||!Number.isSafeInteger(value)||value<0||value>=model.events.length)return;pause();state.cursor=value;paint();}
    function click(event) {
      const target=event.target?.closest?.('[data-sr-action],[data-sr-actor],[data-sr-inspect],[data-sr-seek]');if(!target||!scope.contains(target))return;
      const data=target.dataset;
      if(data.srInspect!==undefined){const found=model.events.find(row=>row.id===data.srInspect);if(found&&found.index<=state.cursor&&typeof onInspect==='function')onInspect(model.mode==='study'?{record_ref:{...model.ref},run_index:model.run_index,turn_index:found.turn_index,step:found.step}:model.mode==='telemetry'?{record_ref:{...model.ref},event_id:found.id}:{message_id:found.id,dataset_ref:{...model.ref}});return;}
      if(data.srSeek!==undefined){if(/^\d+$/.test(data.srSeek))seek(Number(data.srSeek));return;}
      if(data.srActor!==undefined){if(visibleActors(model,state).some(actor=>actor.key===data.srActor)){state.actor=data.srActor;paint();}return;}
      if(data.srAction==='play'){if(state.playing)pause();else if(model.events.length){if(state.cursor===model.events.length-1)state.cursor=0;state.playing=true;schedule();}paint();}
      if(data.srAction==='prev')seek(state.cursor-1);
      if(data.srAction==='next')seek(state.cursor+1);
      if(data.srAction==='overview'){state.actor=null;paint();}
    }
    function change(event) {
      const node=event.target;if(!scope.contains(node))return;
      if(node.matches?.('[data-sr-scrub]')){if(/^\d+$/.test(String(node.value)))seek(Number(node.value));}
      if(node.matches?.('[data-sr-speed]')){const speed=Number(node.value);if([0.5,1,2,4].includes(speed)){state.speed=speed;if(state.playing){global.clearTimeout(timer);timer=null;schedule();}paint();}}
      if(node.matches?.('[data-sr-room]')&&model.rooms.includes(node.value)){state.room=node.value;paint();}
      if(node.matches?.('[data-sr-audience]')&&Object.prototype.hasOwnProperty.call(AUDIENCE_LABELS,node.value)){state.audience=node.value;paint();}
      if(node.matches?.('[data-sr-focus]')&&(node.value===''||visibleActors(model,state).some(actor=>actor.key===node.value))){state.actor=node.value||null;paint();}
    }
    function keyboard(event){if((event.key==='Enter'||event.key===' ')&&event.target?.matches?.('[data-sr-actor]')){event.preventDefault();click(event);}}
    scope.addEventListener('click',click);scope.addEventListener('change',change);scope.addEventListener('input',change);scope.addEventListener('keydown',keyboard);paint();
    const cleanup=()=>{if(disposed)return;pause();disposed=true;scope.removeEventListener('click',click);scope.removeEventListener('change',change);scope.removeEventListener('input',change);scope.removeEventListener('keydown',keyboard);};
    cleanup.getState=()=>snapshot(state);cleanup.seek=seek;return cleanup;
  }
  global.SocietyReplay={normalize,normalizeStudyRun,normalizeEventRun,render,attach,peek,limits:{...LIMITS}};
})(typeof window==='object'?window:globalThis);
