"""Saved-source replay: pure presentation, prefix honesty and scoped lifecycle."""
import json
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
JS = ROOT / "web" / "society-replay.js"

NODE = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
let calls=0,next=1;const pending=new Map();
const context=vm.createContext({assert,
  fetch:()=>{calls++;throw Error('No network allowed');},
  setTimeout:(fn,ms)=>{const id=next++;pending.set(id,{fn,ms});return id;},
  clearTimeout:id=>pending.delete(id),pending,
  tick:()=>{const entry=pending.entries().next().value;if(entry){pending.delete(entry[0]);entry[1].fn();}}
});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
vm.runInContext(`
const H='a'.repeat(64),ref={id:'dataset-test',version:2,hash:H};
function row(id,actor='a',name='Alpha',content='Hello',timestamp='2025-04-22T18:00:00Z',room='room') {
 return {id,speaker_id:actor,speaker_type:'agent',agent_name:name,content,timestamp,room_id:room,content_hash:'h-'+id};
}
function record(rows) {return {...ref,kind:'dataset',payload:{messages:rows}};}
function study(turns,outcomes={success:0,incorrect_publication:1}) {
 return {id:'experiment-test',version:3,hash:H,kind:'experiment',payload:{status:'complete',agent_mode:'live',runs:[{turns,outcomes}]}};
}
function turn(step,actor,action,result) {return {step,agent_id:actor,action,tool_result:result,request:{system:'HIDDEN PROMPT',context:'HIDDEN TREATMENT',observation:{secret:'HIDDEN PRIVATE STATE'}}};}
function eventRun(events,kind='authored_example') {return {id:'observability-run-test',version:4,hash:H,kind:'observability_run',payload:{schema_version:'societylab.events.v1',source:{id:'source-1',name:'Example team',kind},run:{id:'run-1'},events}};}
function event(id,kind,data,extra={}) {return {id,occurred_at:'2025-04-22T18:00:'+String(id.replace(/\\D/g,'')||0).padStart(2,'0')+'Z',kind,data,...extra};}
function dom(model) {
 const nodes=new Map(),listeners=new Map();
 const root={dataset:{srId:model.ref.id,srVersion:String(model.ref.version),srHash:model.ref.hash,srMode:model.mode,srRun:model.mode==='study'?String(model.run_index):''},innerHTML:'',
 matches:s=>s==='.sr-root',contains:n=>n&&n.outside!==true,
 querySelector:s=>{if(!nodes.has(s))nodes.set(s,{innerHTML:'',textContent:'',value:'',attributes:{},setAttribute(k,v){this.attributes[k]=v;}});return nodes.get(s);},
 addEventListener:(k,f)=>listeners.set(k,f),removeEventListener:(k,f)=>{if(listeners.get(k)===f)listeners.delete(k);}};
 function target(data={},selector='',value='') {return {dataset:data,value,matches:s=>s===selector,closest:()=>targetNode};}
 let targetNode;
 function fire(type,data={},selector='',value='') {targetNode=target(data,selector,value);const f=listeners.get(type);if(f)f({target:targetNode,key:'Enter',preventDefault(){}});}
 return {root,nodes,listeners,fire};
}
`,context);
vm.runInContext(input.script,context,{timeout:10000});
assert.equal(calls,0);
process.stdout.write('PASS');
"""


class SocietyReplayTests(unittest.TestCase):
    def node(self, script):
        result = subprocess.run(
            ["node", "-e", NODE, str(JS)], input=json.dumps({"script": script}),
            text=True, capture_output=True, timeout=20, cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "PASS")

    def test_normalized_chronology_and_missingness_are_not_invented(self):
        self.node(r"""
const source=record([row('late','b','Beta','late','2025-04-22T18:02:00Z'),
 row('tie2','a','Alpha','tie2','2025-04-22T23:30:00+05:30'),
 row('tie1','b','Beta','tie1','2025-04-22T18:00:00Z'),
 row('bad','u','Human','bad','2025-02-30T18:00:00Z'),row('missing','a','Alpha','missing',null)]);
source.payload.messages[3].speaker_type='user';
const before=JSON.stringify(source),m=SocietyReplay.normalize(source);
assert(m.available);assert.equal(m.events.map(e=>e.id).join(','),'tie2,tie1,late,bad,missing');
assert.equal(m.events[3].stamp,null);assert.equal(m.events[4].timestamp,null);
assert(m.warnings.some(x=>x.includes('Equal timestamps')));assert(m.warnings.some(x=>x.includes('chronology is unknown')));
assert.equal(m.actors.find(a=>a.id==='u').type,'user');assert.equal(JSON.stringify(source),before);
assert(!SocietyReplay.normalize({...source,version:true}).available);
assert(!SocietyReplay.normalize(record([row('dup'),row('dup')])).available);
assert(!SocietyReplay.normalize(record([row('oversized','a','Alpha','x'.repeat(65537))])).available);
assert.equal(SocietyReplay.normalize(record([])).events.length,0);
const micros=SocietyReplay.normalize(record([row('later','a','Alpha','later','2025-04-22T18:00:00.000009Z'),row('earlier','b','Beta','earlier','2025-04-22T18:00:00.000001Z')]));
assert.equal(micros.events[0].id,'earlier');assert(!micros.warnings.some(x=>x.includes('Equal timestamps')));
const far=SocietyReplay.normalize(record([row('later','a','Alpha','later','9999-12-31T18:00:00.000009Z'),row('earlier','b','Beta','earlier','9999-12-31T18:00:00.000001Z')]));
assert.equal(far.events[0].id,'earlier');assert.doesNotThrow(()=>JSON.stringify(far));
""")

    def test_reference_edges_are_explicit_and_ambiguity_is_retained(self):
        self.node(r"""
const r=record([row('m0','a','Alpha','Hello Beta and o3'),row('m1','b','Beta','Alpha says Beta'),
 row('m2','o3','o3','Alpha'),row('m3','a','Alpha','Beta','2025-04-22T18:01:00Z'),
 row('m4','b','Beta','Elsewhere','2025-04-22T18:02:00Z','other')]);
r.payload.messages[1].reply_to='m0';r.payload.messages[3].reply_to='m4';r.payload.messages[4].reply_to='m0';
const m=SocietyReplay.normalize(r);assert(m.available);
assert.equal(m.events[0].mentions.join(','),'agent:b');assert.equal(m.events[1].mentions.join(','),'agent:a');
assert.equal(m.events[1].reply.message_id,'m0');assert.equal(m.events[3].reply,null);assert.equal(m.events[4].reply,null);
assert(m.technical_scope.includes('not delivery'));assert(m.scope.includes('do not prove who read'));
const ambiguity=SocietyReplay.normalize(record([row('x','a','Shared','Shared'),row('y','b','Shared','Shared')]));
assert.equal(ambiguity.events[0].mentions.length,0);assert(ambiguity.warnings.some(x=>x.includes('Ambiguous')));
""")

    def test_render_escapes_text_masks_credentials_and_hides_future(self):
        self.node(r"""
const r=record([row('m0','a','<img src=x onerror=evil>','<script>evil()</script> hf_ABCDEFGHIJKLMNOPQRST'),
 row('m1','b','Beta','FUTURE-SECRET','2025-04-22T18:01:00Z')]);
const html=SocietyReplay.render({record:r});
assert(html.includes('&lt;script&gt;'));assert(!html.includes('<script>evil'));
assert(!html.includes('<img src=x'));assert(html.includes('[credential-shaped text masked]'));
assert(!html.includes('hf_ABCDEFGHIJKLMNOPQRST'));assert(!html.includes('FUTURE-SECRET'));
assert(html.includes('data-sr-hash="'+H+'"'));assert(!html.includes('<defs>'));
const end=SocietyReplay.render({record:r,initialState:{cursor:1}});assert(end.includes('FUTURE-SECRET'));
const peek=SocietyReplay.peek(r,{cursor:1,playing:true,speed:2});
assert.equal(peek.current_message.id,'m1');assert.equal(peek.state.playing,false);
assert.equal(peek.dataset_ref.version,2);assert.equal(peek.total_posts,2);
""")

    def test_friendly_labels_keep_source_identity_and_ist_clock(self):
        self.node(r"""
const human='d4437214-fc9e-4d51-b116-4e31de39cc41',roomId='945238af-41e2-4b27-8eae-d21ae1c0f911';
const message=row('m0',human,human,'hello','2025-04-22T18:00:00Z',roomId);message.speaker_type='user';
const source=record([message]),before=JSON.stringify(source),m=SocietyReplay.normalize(source);
assert.equal(m.actors[0].name,'Human participant 1');assert.equal(m.actors[0].id,human);
const html=SocietyReplay.render({record:source}),primary=html.split('<details class="sr-ref">')[0];
assert(primary.includes('Team room 1'));assert(!primary.includes('data-sr-room aria-label'));
assert(!primary.replace(/<[^>]*>/g,'').includes(roomId));assert(!primary.replace(/<[^>]*>/g,'').includes(human));
assert(primary.includes('23:30:00 IST'));assert(html.includes('<code>'+roomId+'</code>'));assert(html.includes('<code>'+human+'</code>'));
assert.equal(SocietyReplay.peek(source).current_message.timestamp,'2025-04-22T18:00:00Z');
assert.equal(JSON.stringify(source),before);assert(m.scope.includes('Posts do not prove who read'));
const multiple=record([message,row('m1','o3','o3','hello','2025-04-22T18:01:00Z','second-room')]);
const multipleHtml=SocietyReplay.render({record:multiple});assert(multipleHtml.includes('data-sr-room aria-label'));
assert(multipleHtml.includes('value="'+roomId+'"'));assert(multipleHtml.includes('Team room 2'));
assert.equal(SocietyReplay.normalize(multiple).actors.find(a=>a.id==='o3').name,'o3');
""")

    def test_scoped_play_pause_scrub_speed_focus_and_source_callback(self):
        self.node(r"""
const r=record([row('m0'),row('m1','b','Beta','second','2025-04-22T18:01:00Z'),row('m2','a','Alpha','third','2025-04-22T18:02:00Z','other')]);
const m=SocietyReplay.normalize(r),d=dom(m),states=[],inspected=[];
const cleanup=SocietyReplay.attach(d.root,{record:r,onState:s=>states.push(s),onInspect:x=>inspected.push(x)});
assert.equal(cleanup.getState().cursor,0);assert.equal(pending.size,0);assert(d.root.innerHTML.includes('Hello'));
d.root.querySelector('.sr-chat-messages').scrollHeight=1500;
d.fire('click',{srAction:'play'});assert.equal(pending.size,1);assert.equal(cleanup.getState().playing,true);
tick();assert.equal(cleanup.getState().cursor,1);assert(d.nodes.get('[data-sr-chat]').innerHTML.includes('second'));
assert.equal(d.nodes.get('.sr-chat-messages').scrollTop,1500);
d.fire('change',{},'[data-sr-speed]','4');assert.equal([...pending.values()][0].ms,250);
d.fire('click',{srAction:'play'});assert.equal(pending.size,0);assert.equal(cleanup.getState().playing,false);
d.fire('input',{},'[data-sr-scrub]','0');assert.equal(cleanup.getState().cursor,0);
d.fire('click',{srInspect:'m2'});assert.equal(inspected.length,0);
d.fire('click',{srInspect:'m0'});assert.equal(inspected[0].message_id,'m0');assert.equal(inspected[0].dataset_ref.hash,H);
d.fire('click',{srActor:'agent:b'});assert.equal(cleanup.getState().actor,'agent:b');
d.fire('click',{srAction:'overview'});assert.equal(cleanup.getState().actor,null);
d.fire('change',{},'[data-sr-room]','other');assert.equal(cleanup.getState().room,'other');
d.fire('click',{srAction:'next'});assert.equal(cleanup.getState().cursor,1);
d.fire('click',{srAction:'prev'});assert.equal(cleanup.getState().cursor,0);
const saved=cleanup.getState();cleanup();assert.equal(d.listeners.size,0);assert.equal(pending.size,0);
cleanup.seek(2);assert.equal(cleanup.getState().cursor,0);
const d2=dom(m),c2=SocietyReplay.attach(d2.root,{record:r,initialState:{...saved,playing:true}});
assert.equal(c2.getState().speed,4);assert.equal(c2.getState().room,'other');assert.equal(c2.getState().playing,false);c2();
assert(states.length>=8);
""")

    def test_mount_identity_and_lifecycle_fail_closed(self):
        self.node(r"""
const r=record([row('m0'),row('m1','b','Beta')]),m=SocietyReplay.normalize(r),d=dom(m);
d.root.dataset.srVersion='02';assert.equal(SocietyReplay.attach(d.root,{record:r}).getState(),null);
assert.equal(d.listeners.size,0);d.root.dataset.srVersion='2';d.root.dataset.srHash='b'.repeat(64);
assert.equal(SocietyReplay.attach(d.root,{record:r}).getState(),null);
d.root.dataset.srHash=H;const c=SocietyReplay.attach(d.root,{record:r});
d.fire('click',{srAction:'play'});c();assert.equal(pending.size,0);assert.equal(c.getState().playing,false);
const empty=record([]),ed=dom(SocietyReplay.normalize(empty)),ec=SocietyReplay.attach(ed.root,{record:empty});
assert.equal(ec.getState().cursor,-1);ed.fire('click',{srAction:'play'});assert.equal(pending.size,0);ec();
""")

    def test_study_mode_uses_returned_fields_and_final_outcome_only(self):
        self.node(r"""
const r=study([turn(0,'coordinator',{action:'inspect_artifact',artifact_id:'manifest'},{ok:true,version:1,contents:{alpha:3}}),
 turn(1,'builder',{action:'send_message',recipient:'coordinator',message:'Missing beta'},{ok:true,message_id:'s1'}),
 turn(2,'coordinator',{action:'publish_artifact',artifact_id:'manifest'},{ok:true,version:1})]);
r.payload.runs[0].initial_state={secret:'HIDDEN TRUTH'};r.payload.runs[0].environment_seed=99;r.payload.runs[0].arm='secret-treatment';
const before=JSON.stringify(r),m=SocietyReplay.normalizeStudyRun(r,0);assert(m.available);assert.equal(m.mode,'study');
assert.equal(m.events[1].deliveries[0],'coordinator');assert.equal(m.events[0].stamp,null);
const start=SocietyReplay.render({record:r}),end=SocietyReplay.render({record:r,initialState:{cursor:2}});
assert(start.includes('Outcome hidden until'));assert(!start.includes('task incorrect'));assert(end.includes('task incorrect'));
assert(end.includes('saved environment score'));assert(!start.includes('Missing beta'));
assert(!end.includes('HIDDEN'));assert(!end.includes('secret-treatment'));assert(!end.includes('environment_seed'));
assert(end.includes('last returned version 1'));assert(end.includes('tool-confirmed send')||start.includes('tool-confirmed send'));
assert.equal(JSON.stringify(r),before);assert(m.technical_scope.includes('do not establish reading'));
const p=SocietyReplay.peek(r,{cursor:2});assert.equal(p.current_turn.step,2);assert.equal(p.current_turn.tool_ok,true);
assert.equal(p.current_message,undefined);
""")

    def test_study_rejections_unknowns_and_ordinal_source_inspection(self):
        self.node(r"""
const r=study([turn(4,'a',{action:'send_message',recipient:'b',message:'failed'},{ok:false,error:'denied'}),
 turn(5,'b',{action:'wait'},{}),turn(6,'a',{action:'repair_artifact',artifact_id:'x'},{ok:true})],{});
const m=SocietyReplay.normalize(r);assert.equal(m.events[0].deliveries.length,0);assert.equal(m.events[1].ok,null);
const d=dom(m),out=[];const c=SocietyReplay.attach(d.root,{record:r,onInspect:x=>out.push(x)});c.seek(2);
d.fire('click',{srInspect:'turn-2'});assert.equal(out[0].turn_index,2);assert.equal(out[0].step,6);assert.equal(out[0].run_index,0);
assert.equal(out[0].record_ref.id,'experiment-test');assert.equal(out[0].message_id,undefined);
assert(d.nodes.get('[data-sr-board]').innerHTML.includes('correctness unknown'));c();
const bad=study([turn(0,'a',{action:'wait'},{}),turn(0,'b',{action:'wait'}, {})]);assert(!SocietyReplay.normalize(bad).available);
assert(!SocietyReplay.normalizeStudyRun(r,true).available);assert(!SocietyReplay.normalizeStudyRun(r,9).available);
const nf=study([turn(0,'a',{action:'inspect_artifact'},{ok:true,contents:{bad:Infinity}})]);assert(!SocietyReplay.normalize(nf).available);
const incomplete=study([turn(0,'a',{action:'wait'},{ok:true})],{success:0});incomplete.payload.status='failed';
assert(SocietyReplay.render({record:incomplete}).includes('Outcome hidden until'));assert(!SocietyReplay.render({record:incomplete}).includes('task incorrect'));
""")

    def test_event_run_board_and_messages_are_prefix_only(self):
        self.node(r"""
const r=eventRun([
 event('e0','agent.registered',{name:'Planner'},{actor_id:'a'}),
 event('e1','task.created',{title:'Design the experiment'},{task_id:'t1'}),
 event('e2','task.assigned',{assignee_ids:['a','b']},{task_id:'t1'}),
 event('e3','message.sent',{content:'Send the plan',channel_id:'team'},{actor_id:'a',recipient_ids:['b']}),
 event('e4','tool.called',{call_id:'call1',tool_name:'check_plan',arguments:{password:'short-secret',question:'ordinary'}},{actor_id:'a'}),
 event('e5','tool.returned',{call_id:'call1',success:true,output:{result:'<img src=x onerror=evil>'}},{actor_id:'a'}),
 event('e6','artifact.updated',{artifact_id:'plan',revision_id:'rev-final',change_summary:'FUTURE ARTIFACT'},{actor_id:'a'}),
 event('e7','intervention.delivered',{intervention_id:'i1',content:'Check the current version'},{actor_id:'a',recipient_ids:['b']}),
 event('e8','agent.registered',{name:'FutureReviewer'},{actor_id:'b'}),
 event('e9','task.completed',{success:true},{task_id:'t1'})
]);
const before=JSON.stringify(r),m=SocietyReplay.normalize(r);assert(m.available);assert.equal(m.mode,'telemetry');
assert(m.example);assert(m.scope.includes('example events'));assert.equal(m.events[3].addresses[0],'b');
const start=SocietyReplay.render({record:r,initialState:{cursor:1}});
assert(start.includes('Design the experiment'));assert(!start.includes('Completed · success recorded'));
assert(!start.includes('FutureReviewer'));assert(!start.includes('FUTURE ARTIFACT'));assert(!start.includes('Send the plan'));
const assigned=SocietyReplay.render({record:r,initialState:{cursor:2}});assert(assigned.includes('Assigned'));assert(assigned.includes('Participant 2'));assert(!assigned.includes('FutureReviewer'));
const call=SocietyReplay.render({record:r,initialState:{cursor:4}});assert(call.includes('[sensitive field masked]'));assert(!call.includes('short-secret'));
assert(call.includes('Awaiting return'));assert(!call.includes('Success recorded'));
const returned=SocietyReplay.render({record:r,initialState:{cursor:5}});assert(returned.includes('Success recorded'));assert(!returned.includes('<img src=x'));assert(returned.includes('&lt;img'));
const done=SocietyReplay.render({record:r,initialState:{cursor:9}});assert(done.includes('Completed · success recorded'));assert(done.includes('FutureReviewer'));assert(done.includes('Intervention'));
assert(done.includes('logged recipient'));assert(!done.includes('tool-confirmed send'));
assert(done.includes('No task or tool is being run here'));assert.equal(JSON.stringify(r),before);
const peek=SocietyReplay.peek(r,{cursor:7});assert.equal(peek.current_event.id,'e7');assert.equal(peek.current_event.kind,'intervention.delivered');
assert.equal(peek.record_ref.version,4);assert.equal(peek.current_message,undefined);
""")

    def test_event_run_schema_bounds_and_unknown_addressing_fail_honestly(self):
        self.node(r"""
const r=eventRun([event('e0','message.sent',{content:'No recipients recorded'},{actor_id:'unknown',recipient_ids:[]})],'telemetry');
const m=SocietyReplay.normalize(r),html=SocietyReplay.render({record:r});assert(m.available);assert(!m.example);
assert.equal(m.actors[0].type,'unknown');assert(html.includes('broadcast is not inferred'));assert(!html.includes('authored_example'));
assert(!SocietyReplay.normalize(eventRun([r.payload.events[0],r.payload.events[0]])).available);
assert(!SocietyReplay.normalize(eventRun([event('e0','message.sent',{content:'x'},{actor_id:'a'})])).available);
assert(!SocietyReplay.normalize(eventRun([event('e0','task.completed',{success:1},{task_id:'t'})])).available);
assert(!SocietyReplay.normalize(eventRun([event('e0','made.up',{}, {actor_id:'a'})])).available);
const missing=eventRun([event('e0','agent.registered',{name:'A'},{actor_id:'a'})]);missing.payload.events[0].occurred_at=null;
assert(!SocietyReplay.normalize(missing).available);
const nonfinite=eventRun([event('e0','tool.called',{call_id:'c',tool_name:'t',arguments:{bad:NaN}},{actor_id:'a'})]);assert(!SocietyReplay.normalize(nonfinite).available);
const duplicateRecipients=eventRun([event('e0','message.sent',{content:'x'},{actor_id:'a',recipient_ids:['b','b']})]);assert(!SocietyReplay.normalize(duplicateRecipients).available);
const wrongRevision=eventRun([event('e0','artifact.updated',{artifact_id:'a',revision_id:2},{actor_id:'b'})]);assert(!SocietyReplay.normalize(wrongRevision).available);
""")

    def test_event_run_playback_inspection_and_backward_seek_hide_later_state(self):
        self.node(r"""
const r=eventRun([event('e0','agent.registered',{name:'A'},{actor_id:'a'}),
 event('e1','task.created',{title:'First task'},{task_id:'t'}),
 event('e2','agent.registered',{name:'B'},{actor_id:'b'}),
 event('e3','task.completed',{success:false},{task_id:'t'})]);
const d=dom(SocietyReplay.normalize(r)),inspected=[],c=SocietyReplay.attach(d.root,{record:r,onInspect:x=>inspected.push(x)});
assert(!d.nodes.get('[data-sr-focus]').innerHTML.includes('>B<'));
d.fire('click',{srActor:'b'});assert.equal(c.getState().actor,null);
d.fire('click',{srInspect:'e3'});assert.equal(inspected.length,0);
c.seek(3);assert(d.nodes.get('[data-sr-board]').innerHTML.includes('marked unsuccessful'));
d.fire('click',{srInspect:'e3'});assert.equal(inspected[0].event_id,'e3');assert.equal(inspected[0].record_ref.id,r.id);assert.equal(inspected[0].dataset_ref,undefined);
d.fire('click',{srActor:'b'});assert.equal(c.getState().actor,'b');c.seek(0);assert.equal(c.getState().actor,null);
assert(!d.nodes.get('[data-sr-board]').innerHTML.includes('marked unsuccessful'));assert(!d.nodes.get('[data-sr-board]').innerHTML.includes('First task'));
d.fire('click',{srAction:'play'});tick();assert.equal(c.getState().cursor,1);assert(d.nodes.get('[data-sr-board]').innerHTML.includes('First task'));
c();assert.equal(pending.size,0);
""")

    def test_event_run_ties_reply_fields_and_temporal_order_remain_declarations(self):
        self.node(r"""
const r=eventRun([event('e2','message.sent',{content:'reply',channel_id:'team',reply_to_message_id:'e1'},{actor_id:'b',recipient_ids:['a']}),
 event('e1','message.sent',{content:'first',channel_id:'team'},{actor_id:'a',recipient_ids:['b']}),
 event('e3','message.sent',{content:'other channel',channel_id:'other',reply_to_message_id:'e1'},{actor_id:'a',recipient_ids:[]})]);
const m=SocietyReplay.normalize(r);assert.equal(m.events[0].id,'e1');assert.equal(m.events[1].reply.message_id,'e1');assert.equal(m.events[2].reply,null);
assert(m.warnings.some(x=>x.includes('arrived out of timestamp order')));assert.equal(m.events[0].sourceOrder,1);
const tied=eventRun([event('e0','task.created',{title:'One'},{task_id:'t'}),event('e1','task.completed',{success:true},{task_id:'t'})]);
tied.payload.events[1].occurred_at=tied.payload.events[0].occurred_at;
const tm=SocietyReplay.normalize(tied);assert(tm.warnings.some(x=>x.includes('Equal timestamps')));assert.equal(tm.events[0].id,'e0');
assert(tm.technical_scope.includes('No recipient consumption'));assert(tm.technical_scope.includes('causal mechanism'));
""")

    def test_responsive_reduced_motion_and_scoped_stylesheet(self):
        css = (ROOT / "web" / "society-replay.css").read_text(encoding="utf-8")
        self.assertIn("@media(prefers-reduced-motion:reduce)", css)
        self.assertIn("animation:none!important", css)
        self.assertIn("@media(max-width:720px)", css)
        self.assertNotIn("body{", css)
        self.assertNotIn("@import", css)
        self.assertIn(".sr-message p{font-size:12px", css)
        self.assertIn(".sr-avatar-label{font-size:13px", css)
        def luminance(color):
            values = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            rgb = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
            return .2126 * rgb[0] + .7152 * rgb[1] + .0722 * rgb[2]
        for foreground, background in [
            ("#263d40", "#fffef8"), ("#526568", "#f0f3ec"),
            ("#304743", "#e7eddf"), ("#ffffff", "#1b7470"),
        ]:
            a, b = sorted([luminance(foreground), luminance(background)], reverse=True)
            self.assertGreaterEqual((a + .05) / (b + .05), 4.5)


if __name__ == "__main__":
    unittest.main()
