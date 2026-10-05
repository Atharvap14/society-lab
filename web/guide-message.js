/* Bounded presentation of recorded replies. No hidden reasoning or model HTML. */
(function(scope){
  'use strict';
  const VERSION='guide-message-v1',LIMITS={content:12000,lines:400,notes:16,tools:6,events:40,sources:10,embeds:6,chartRows:16};
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const object=v=>v&&typeof v==='object'&&!Array.isArray(v);
  const identifier=v=>typeof v==='string'&&/^[A-Za-z0-9][A-Za-z0-9_.-]{0,199}$/.test(v);
  const exact=r=>object(r)&&Object.keys(r).length===3&&identifier(r.id)&&Number.isSafeInteger(r.version)&&r.version>0&&typeof r.hash==='string'&&/^[a-f0-9]{64}$/.test(r.hash);
  const pin=r=>({id:r.id,version:r.version,hash:r.hash});
  const text=(v,max)=>typeof v==='string'&&v.length<=max;
  const status=v=>({started:'Started',running:'Running',queued:'Queued',completed:'Completed',failed:'Failed',pending_or_unknown:'Pending or unknown',unknown:'Unknown'})[v]||'Unknown';
  function link(url){
    if(typeof url!=='string'||url.length>2048||/[\s\u0000-\u001f\u007f]/.test(url))return null;
    if(/^#[A-Za-z0-9_.-]{1,120}$/.test(url))return url;
    if(!/^https?:\/\//i.test(url))return null;
    try{const parsed=new URL(url);if(!['http:','https:'].includes(parsed.protocol)||parsed.username||parsed.password)return null;return parsed.href;}catch(_){return null;}
  }
  function underscoreDelimiter(source,index,width,opening){
    const before=source[index-1],after=source[index+width],space=c=>c===undefined||/\s/u.test(c),punct=c=>c!==undefined&&/[\p{P}\p{S}]/u.test(c);
    const left=!space(after)&&(!punct(after)||space(before)||punct(before));
    const right=!space(before)&&(!punct(before)||space(after)||punct(after));
    return opening?left&&(!right||punct(before)):right&&(!left||punct(after));
  }
  function inline(source,depth=0,allowLinks=true){
    let out='',i=0;
    while(i<source.length){
      if(source[i]==='`'){let n=1;while(source[i+n]==='`'&&n<4)n++;const delimiter='`'.repeat(n),end=source.indexOf(delimiter,i+n);if(n<=3&&end>=i+n){out+='<code>'+esc(source.slice(i+n,end))+'</code>';i=end+n;continue;}}
      if(allowLinks&&source[i]==='['){const match=source.slice(i).match(/^\[([^\]\n]{1,500})\]\(([^)\n]{1,2048})\)/);if(match){const safe=link(match[2]);out+=safe?'<a href="'+esc(safe)+'"'+(safe.startsWith('#')?'':' target="_blank" rel="noopener noreferrer"')+'>'+inline(match[1],depth+1,false)+'</a>':esc(match[0]);i+=match[0].length;continue;}}
      if(depth<3&&['*','_'].includes(source[i])){const doubled=source[i+1]===source[i],delimiter=source[i].repeat(doubled?2:1),underscore=source[i]==='_';let end=source.indexOf(delimiter,i+delimiter.length);
        if(underscore&&!underscoreDelimiter(source,i,delimiter.length,true)){out+=esc(delimiter);i+=delimiter.length;continue;}
        while(underscore&&end>=0&&!underscoreDelimiter(source,end,delimiter.length,false))end=source.indexOf(delimiter,end+delimiter.length);
        if(end>i+delimiter.length){const tag=doubled?'strong':'em';out+='<'+tag+'>'+inline(source.slice(i+delimiter.length,end),depth+1,allowLinks)+'</'+tag+'>';i=end+delimiter.length;continue;}}
      out+=esc(source[i++]);
    }
    return out;
  }
  const cells=line=>{let s=line.trim();if(s.startsWith('|'))s=s.slice(1);if(s.endsWith('|'))s=s.slice(0,-1);return s.split('|').map(v=>v.trim());};
  function markdown(value){
    if(!text(value,LIMITS.content))return '<p class="gm-unavailable">This message exceeds the display bound or has no valid text.</p>';
    const lines=value.replace(/\r\n?/g,'\n').split('\n');if(lines.length>LIMITS.lines)return '<pre class="gm-plain">'+esc(value)+'</pre>';
    let out='',i=0;
    const special=line=>/^\s*$|^\s*```|^#{1,6}\s|^\s*[-*+]\s|^\s*\d{1,6}[.)]\s|^>\s?/.test(line);
    while(i<lines.length){
      const line=lines[i];if(!line.trim()){i++;continue;}
      const fence=line.match(/^\s*```([A-Za-z0-9_.+-]{0,40})\s*$/);
      if(fence){const code=[];i++;while(i<lines.length&&!/^\s*```\s*$/.test(lines[i]))code.push(lines[i++]);if(i<lines.length)i++;out+='<pre><code'+(fence[1]?' class="language-'+esc(fence[1])+'"':'')+'>'+esc(code.join('\n'))+'</code></pre>';continue;}
      const heading=line.match(/^(#{1,6})\s+(.+)$/);if(heading){const n=heading[1].length;out+='<h'+n+'>'+inline(heading[2])+'</h'+n+'>';i++;continue;}
      if(i+1<lines.length&&line.includes('|')){const header=cells(line),separator=cells(lines[i+1]);
        if(header.length>=2&&header.length<=12&&separator.length===header.length&&separator.every(v=>/^:?-{3,}:?$/.test(v))){const rows=[];let end=i+2;while(end<lines.length&&lines[end].includes('|')&&lines[end].trim()){rows.push(cells(lines[end++]));}
          if(rows.length<=32&&rows.every(row=>row.length===header.length)){out+='<div class="gm-table"><table><thead><tr>'+header.map(cell=>'<th scope="col">'+inline(cell)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+row.map(cell=>'<td>'+inline(cell)+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';i=end;continue;}}
      }
      const unordered=/^\s*[-*+]\s+(.+)$/.exec(line),ordered=/^\s*\d{1,6}[.)]\s+(.+)$/.exec(line);
      if(unordered||ordered){const tag=ordered?'ol':'ul',pattern=ordered?/^\s*\d{1,6}[.)]\s+(.+)$/:/^\s*[-*+]\s+(.+)$/;out+='<'+tag+'>';let match;while(i<lines.length&&(match=pattern.exec(lines[i]))){out+='<li>'+inline(match[1])+'</li>';i++;}out+='</'+tag+'>';continue;}
      if(/^>\s?/.test(line)){const quote=[];while(i<lines.length&&/^>\s?/.test(lines[i]))quote.push(inline(lines[i++].replace(/^>\s?/,'')));out+='<blockquote>'+quote.join('<br>')+'</blockquote>';continue;}
      const paragraph=[inline(line)];i++;while(i<lines.length&&!special(lines[i])){if(i+1<lines.length&&lines[i].includes('|')&&cells(lines[i+1]).every(v=>/^:?-{3,}:?$/.test(v)))break;paragraph.push(inline(lines[i++]));}out+='<p>'+paragraph.join('<br>')+'</p>';
    }
    return out;
  }
  function refButton(reference,label='Open saved item',messageId=null){
    return exact(reference)?'<button type="button" class="gm-ref" data-ws-artifact="'+esc(reference.id)+'" data-ws-version="'+reference.version+'" data-ws-hash="'+reference.hash+'"'+(text(messageId,200)&&messageId?' data-ws-message="'+esc(messageId)+'"':'')+'>'+esc(label)+' <small>v'+reference.version+'</small></button>':'';
  }
  function sourceButton(row){
    if(!object(row))return '';
    if(['chat_context','workspace_chat_context'].includes(row.kind)){
      const version=row.chat_revision??row.revision;
      if(!identifier(row.chat_id)||!Number.isSafeInteger(version)||version<1||typeof row.snapshot_hash!=='string'||!/^[a-f0-9]{64}$/.test(row.snapshot_hash))return '';
      return '<button type="button" class="gm-ref" data-ws-citation="'+esc(row.chat_id)+'" data-ws-revision="'+version+'" data-ws-snapshot="'+row.snapshot_hash+'">'+esc(text(row.label,240)?row.label:'Read cited chat')+' <small>r'+version+'</small></button>';
    }
    return refButton(row.object_ref||row.ref,text(row.label,240)?row.label:row.kind==='chat_excerpt'?'Replay cited message':'Open cited '+(text(row.kind,80)?row.kind.replace(/_/g,' '):'saved item'),row.kind==='chat_excerpt'?row.message_id:null);
  }
  function eventGraph(graph){
    const unavailable='<p class="gm-unavailable">The recorded event graph is unavailable.</p>',relations=['actor','task','parent_task','addressed_recipient','task_assignee','reply_reference','tool_call_reference'];
    const eventId=v=>typeof v==='string'&&/^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$/.test(v);
    if(!object(graph)||graph.graph_version!=='event-evidence-neighborhood-v1'||!exact(graph.source_ref)||!Array.isArray(graph.nodes)||!graph.nodes.length||graph.nodes.length>8||!Array.isArray(graph.edges)||graph.edges.length>8||!Array.isArray(graph.diagnostics)||graph.diagnostics.length>2||typeof graph.truncated!=='boolean')return unavailable;
    const kinds=['agent.registered','task.created','task.assigned','task.completed','message.sent','reasoning.recorded','tool.called','tool.returned','artifact.updated','intervention.delivered'];
    if(!graph.nodes.every(n=>object(n)&&eventId(n.id)&&kinds.includes(n.kind)&&(n.actor_id===null||eventId(n.actor_id))))return unavailable;
    const ids=new Set(graph.nodes.map(n=>n.id));if(ids.size!==graph.nodes.length||!ids.has(graph.seed_event_id))return unavailable;
    if(!graph.edges.every(edge=>object(edge)&&ids.has(edge.source)&&ids.has(edge.target)&&relations.includes(edge.relation)&&edge.status==='matching_declared_reference'&&text(edge.field,200)&&object(edge.provenance)&&edge.provenance.event_id===edge.source&&edge.provenance.field===edge.field&&typeof edge.provenance.event_sha256==='string'&&/^[a-f0-9]{64}$/.test(edge.provenance.event_sha256)))return unavailable;
    if(!graph.diagnostics.every(row=>object(row)&&ids.has(row.event_id)&&relations.includes(row.relation)&&['unknown_in_captured_run','ambiguous_reference','actor_conflict'].includes(row.status)))return unavailable;
    const points=new Map(graph.nodes.map((node,i)=>[node.id,{x:80+(i%4)*160,y:graph.nodes.length>4?(i<4?55:170):65}]));
    const lines=graph.edges.map(edge=>{const a=points.get(edge.source),b=points.get(edge.target),dx=b.x-a.x,dy=b.y-a.y,len=Math.hypot(dx,dy);
      if(!len)return '<text x="'+(a.x+32)+'" y="'+(a.y-30)+'" font-size="10">'+esc(edge.relation.replace(/_/g,' '))+' (self reference)</text>';
      const ux=dx/len,uy=dy/len,sx=a.x+ux*25,sy=a.y+uy*25,tx=b.x-ux*25,ty=b.y-uy*25;
      return '<g><title>'+esc(edge.source+' → '+edge.target+' · '+edge.relation+' · '+edge.field)+'</title><line x1="'+sx+'" y1="'+sy+'" x2="'+tx+'" y2="'+ty+'" stroke="currentColor" stroke-width="1.4"/><polygon points="'+tx+','+ty+' '+(tx-ux*8-uy*4)+','+(ty-uy*8+ux*4)+' '+(tx-ux*8+uy*4)+','+(ty-uy*8-ux*4)+'" fill="currentColor"/></g>';}).join('');
    const nodes=graph.nodes.map(node=>{const p=points.get(node.id);return '<g><title>'+esc(node.id+(node.actor_id?' · actor '+node.actor_id:''))+'</title><circle cx="'+p.x+'" cy="'+p.y+'" r="24" fill="var(--surface,#fff)" stroke="currentColor" stroke-width="'+(node.id===graph.seed_event_id?2.5:1)+'"/><text x="'+p.x+'" y="'+(p.y+4)+'" text-anchor="middle" font-size="11">'+esc(node.kind.split('.')[0])+'</text><text x="'+p.x+'" y="'+(p.y+40)+'" text-anchor="middle" font-size="11">'+esc(node.kind.replace('.',' '))+'</text><text x="'+p.x+'" y="'+(p.y+55)+'" text-anchor="middle" font-size="10">'+esc((node.actor_id||node.id).slice(0,20))+'</text></g>';}).join('');
    return '<section class="gm-report-card gm-event-graph"><h3>Recorded event links</h3><p class="gm-scope">Arrows follow explicit source fields. They do not show influence, reading or verified tool execution.</p><svg viewBox="0 0 640 '+(graph.nodes.length>4?235:130)+'" role="img" aria-label="Recorded event reference graph" style="width:100%;height:auto">'+lines+nodes+'</svg><ul>'+graph.edges.map(edge=>'<li><code>'+esc(edge.source)+'</code> → <code>'+esc(edge.target)+'</code>: '+esc(edge.relation.replace(/_/g,' '))+' <small>('+esc(edge.field)+')</small></li>').join('')+'</ul>'+graph.diagnostics.map(row=>'<p class="gm-scope">'+esc(row.event_id+': '+row.relation.replace(/_/g,' ')+' — '+row.status.replace(/_/g,' '))+'</p>').join('')+(graph.truncated?'<p class="gm-scope">This graph display is capped. More source relationships or diagnostics may be retained in the receipt.</p>':'')+refButton(graph.source_ref,'Open the exact graph source')+'</section>';
  }
  function normalize(message){
    if(typeof message==='string')return {content:message,notes:[],tools:[],sources:[],recorded:false};
    if(!object(message))return {content:null,notes:[],tools:[],sources:[],recorded:false};
    const metadata=object(message.metadata)?message.metadata:{},result=object(metadata.guide_result)?metadata.guide_result:message;
    const content=typeof message.content==='string'?message.content:typeof result.answer==='string'?result.answer:null;
    const notes=[],tools=[],sources=[];
    if(message.role!=='user'){
      if(Array.isArray(result.working_notes)&&result.working_notes.length<=LIMITS.notes)for(const row of result.working_notes)if(object(row)&&['task_summary','operation_summary'].includes(row.kind)&&text(row.text,1000))notes.push({kind:row.kind,text:row.text});
      if(Array.isArray(result.tool_results)&&result.tool_results.length<=LIMITS.tools)for(const row of result.tool_results)if(object(row)&&text(row.tool,80)&&text(row.summary,1000)){
        const refs=Array.isArray(row.result_refs)&&row.result_refs.length<=8?row.result_refs.filter(exact).map(pin):[];
        tools.push({tool:row.tool,summary:row.summary,status:status(row.status),refs,truncated:row.result_refs_truncated===true,job_id:identifier(row.job_id)?row.job_id:null,
          graphHtml:row.tool==='event_neighborhood'&&row.status==='completed'&&object(row.event_graph)?eventGraph(row.event_graph):''});}
      const selectedSources=Array.isArray(result.sources)?result.sources:metadata.sources;
      if(Array.isArray(selectedSources)&&selectedSources.length<=LIMITS.sources)for(const row of selectedSources)if(sourceButton(row)){
        const declared={...(text(row.kind,80)?{kind:row.kind}:{}),...(text(row.label,240)?{label:row.label}:{})};
        if(['chat_context','workspace_chat_context'].includes(row.kind))Object.assign(declared,{chat_id:row.chat_id,chat_revision:row.chat_revision??row.revision,snapshot_hash:row.snapshot_hash});
        else {declared.object_ref=pin(row.object_ref||row.ref);if(row.kind==='chat_excerpt'&&text(row.message_id,200)&&row.message_id)declared.message_id=row.message_id;}sources.push(declared);
      }
    }
    return {content,notes,tools,sources,recorded:object(metadata.guide_result)};
  }
  function activities(rows){
    if(!Array.isArray(rows)||rows.length>LIMITS.events)return '';
    const events=rows.filter(row=>object(row)&&text(row.tool,80)&&text(row.summary,1000));if(!events.length)return '';
    return '<details class="gm-activity" open><summary>Recorded activity <small>'+events.length+'</small></summary><p class="gm-scope">Visible operations reported by the local activity log.</p>'+events.map(row=>'<div class="gm-event"><span class="gm-status" data-gm-status="'+esc(status(row.phase||row.status).toLowerCase().replace(/ /g,'-'))+'">'+esc(status(row.phase||row.status))+'</span><strong>'+esc(row.tool.replace(/_/g,' '))+'</strong><p>'+esc(row.summary)+'</p>'+((Array.isArray(row.result_refs)&&row.result_refs.length<=8)?row.result_refs.map(reference=>refButton(reference)).join(''):'')+'</div>').join('')+'</details>';
  }
  function embed(row){
    if(!object(row)||!['report_card','bar_chart','html_report'].includes(row.type)||!exact(row.source_ref)||!text(row.title,240)||!row.title.trim()||!text(row.scope,1000)||!row.scope.trim()||row.summary!==undefined&&!text(row.summary,1600))return '<p class="gm-unavailable">An embedded saved-report view is unavailable.</p>';
    const heading='<h3>'+esc(row.title)+'</h3>'+(row.summary?'<p>'+esc(row.summary)+'</p>':'');
    if(row.type==='report_card')return '<section class="gm-report-card">'+heading+refButton(row.source_ref,'Open the exact saved report')+'<p class="gm-scope">'+esc(row.scope)+'</p></section>';
    if(row.type==='html_report'){
      const url='/api/guide/report?object_id='+encodeURIComponent(row.source_ref.id)+'&version='+row.source_ref.version+'&hash='+row.source_ref.hash;
      return '<section class="gm-report-card gm-html-report">'+heading+'<iframe src="'+esc(url)+'" sandbox="" loading="lazy" referrerpolicy="no-referrer" title="'+esc(row.title)+'"></iframe><p class="gm-scope">'+esc(row.scope)+'</p>'+refButton(row.source_ref,'Open the exact saved report')+'</section>';
    }
    if(!Array.isArray(row.rows)||!row.rows.length||row.rows.length>LIMITS.chartRows||row.unit!==undefined&&!text(row.unit,80))return '<p class="gm-unavailable">An embedded saved-report chart is unavailable.</p>';
    const ratios=Object.hasOwn(row.rows[0]||{},'total');
    if(!row.rows.every(r=>object(r)&&text(r.label,160)&&r.label.trim()&&(r.value===null||typeof r.value==='number'&&Number.isFinite(r.value)&&Math.abs(r.value)<=1e9)&&Object.hasOwn(r,'total')===ratios&&(!ratios||r.total===null||Number.isSafeInteger(r.total)&&r.total>0&&r.total<=1e9)&&( !ratios||r.value===null||Number.isSafeInteger(r.value)&&r.value>=0&&(r.total===null||r.value<=r.total))))return '<p class="gm-unavailable">An embedded saved-report chart is unavailable.</p>';
    const values=row.rows.map(r=>r.value===null||ratios&&r.total===null?null:ratios?r.value/r.total:r.value),maximum=Math.max(...values.map(v=>v===null?0:Math.abs(v)),1e-12),signed=values.some(v=>v!==null&&v<0);
    const bars=row.rows.map((r,i)=>{const value=values[i],width=value===null?0:Math.abs(value)/(ratios?1:maximum)*(signed?50:100),left=signed?(value!==null&&value<0?50-width:50):0,display=r.value===null?'Unknown':ratios?String(r.value)+' / '+(r.total===null?'Unknown':r.total):String(r.value)+(row.unit?' '+row.unit:'');
      return '<div class="gm-chart-row"><span>'+esc(r.label)+'</span><div class="gm-bar-track" aria-hidden="true">'+(value===null?'<span class="gm-bar-unknown">Unknown</span>':'<i style="left:'+left+'%;width:'+width+'%" class="'+(value<0?'negative':'')+'"></i>')+'</div><strong>'+esc(display)+'</strong></div>';}).join('');
    return '<section class="gm-report-card gm-chart">'+heading+'<div class="gm-chart-rows" aria-label="Saved report values">'+bars+'</div><p class="gm-scope">'+esc(row.scope)+'</p>'+refButton(row.source_ref,'Open the exact saved report')+'</section>';
  }
  function render(message,{liveEvents=[],hostEmbeds=[]}={}){
    const value=normalize(message);
    const notes=value.notes.length?'<details class="gm-working"><summary>Working summary <small>'+value.notes.length+' recorded notes</small></summary><p class="gm-scope">Visible task and operation summaries; no hidden model reasoning.</p><ul>'+value.notes.map(row=>'<li>'+esc(row.text)+'</li>').join('')+'</ul></details>':'';
    const tools=value.tools.length?'<details class="gm-tools"><summary>Tool activity <small>'+value.tools.length+' recorded operations</small></summary><p class="gm-scope">Operation receipts are separate from scientific verification.</p>'+value.tools.map(row=>'<details class="gm-tool"><summary><span class="gm-status" data-gm-status="'+esc(row.status.toLowerCase().replace(/ /g,'-'))+'">'+esc(row.status)+'</span>'+esc(row.tool.replace(/_/g,' '))+'</summary><p>'+esc(row.summary)+'</p>'+row.refs.map(reference=>refButton(reference)).join('')+(row.truncated?'<p class="gm-scope">More reference links are retained in the saved receipt.</p>':'')+(row.job_id?'<p class="gm-scope">Recorded job: <code>'+esc(row.job_id)+'</code></p>':'')+'</details>').join('')+'</details>':'';
    const sources=value.sources.length?'<div class="gm-sources" aria-label="Cited saved context">'+value.sources.map(sourceButton).join('')+'</div>':'';
    const embeds=Array.isArray(hostEmbeds)&&hostEmbeds.length<=LIMITS.embeds?hostEmbeds.map(embed).join(''):'<p class="gm-unavailable">Embedded views exceed the display bound.</p>';
    const graphs=value.tools.map(row=>row.graphHtml).join('');
    return '<div class="gm-message" data-gm-version="'+VERSION+'"><div class="gm-markdown">'+markdown(value.content)+'</div>'+notes+tools+activities(liveEvents)+sources+embeds+graphs+'</div>';
  }
  scope.GuideMessage={version:VERSION,limits:Object.freeze({...LIMITS}),render,markdown,normalize};
  if(typeof module!=='undefined')module.exports=scope.GuideMessage;
})(typeof globalThis==='undefined'?window:globalThis);
