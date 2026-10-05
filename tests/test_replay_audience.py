"""Explicit audience streams, not inferred private thought or recipient exposure."""
import json
import subprocess
import unittest

from tests.test_society_replay_ui import ROOT, JS, NODE


class ReplayAudienceTests(unittest.TestCase):
    def node(self, script):
        result = subprocess.run(['node', '-e', NODE, str(JS)], input=json.dumps({'script': script}),
            text=True, encoding='utf-8', capture_output=True, timeout=20, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, 'PASS')

    def test_explicit_streams_stay_distinct_without_mutating_source(self):
        self.node(r"""
const rows=[row('p','a','Alpha','PRIVATE'),row('d','a','Alpha','DIRECT'),row('r','a','Alpha','ROOM'),row('b','a','Alpha','BROADCAST'),row('u','b','Beta','UNKNOWN')];
rows[0].visibility='private';rows[0].room_id=null;rows[1].visibility='direct';rows[1].recipient_ids=['b'];rows[2].visibility='room';rows[3].visibility='broadcast';
const r=record(rows),before=JSON.stringify(r),m=SocietyReplay.normalize(r);assert(m.available);
assert.equal(m.events.map(e=>e.audience.kind).join(','),'private,direct,room,room,unknown');assert.equal(JSON.stringify(r),before);
const html=SocietyReplay.render({record:r,initialState:{cursor:4,room:'room'}});assert(html.includes('sr-lane-direct'));assert(html.includes('sr-lane-room'));assert(html.includes('sr-lane-unknown'));
assert(html.includes('Room membership and reading are not supplied'));assert(!html.includes('sr-lane-private'));
const priv=SocietyReplay.render({record:r,initialState:{cursor:4,room:'[room unknown]',audience:'private'}});assert(priv.includes('PRIVATE'));assert(!priv.includes('DIRECT'));assert(priv.includes('sr-lane-private'));
""")

    def test_legacy_empty_address_and_channel_tags_are_unknown(self):
        self.node(r"""
const r=record([row('x')]);r.payload.messages[0].recipient_ids=[];
const m=SocietyReplay.normalize(r);assert.equal(m.events[0].audience.kind,'unknown');assert.equal(m.events[0].addresses.length,0);
const html=SocietyReplay.render({record:r});assert(html.includes('Audience unknown'));assert(html.includes('broadcast is not inferred'));assert(!html.includes('sr-lane-private'));
const data=eventRun([{id:'x',kind:'message.sent',occurred_at:'2025-04-22T18:00:00Z',actor_id:'a',recipient_ids:[],data:{content:'Tagged room',channel_id:'room'}}]);
assert.equal(SocietyReplay.normalize(data).events[0].audience.kind,'unknown');
""")

    def test_recorded_reasoning_is_local_and_never_bridged_to_peer_arrows(self):
        self.node(r"""
const r=eventRun([{id:'r',kind:'reasoning.recorded',occurred_at:'2025-04-22T18:00:00Z',actor_id:'a',recipient_ids:[],data:{content:'LOCAL-ONLY'}}]);
const m=SocietyReplay.normalize(r);assert(m.available);assert.equal(m.events[0].audience.kind,'private');assert.equal(m.events[0].addresses.length,0);
const h=SocietyReplay.render({record:r});assert(h.includes('Local recorded reasoning'));assert(h.includes('hidden model reasoning is not available'));assert(!h.includes('<g class="sr-reference-edge">'));
const outside=SocietyReplay.render({record:r,initialState:{audience:'room'}});assert(!outside.includes('LOCAL-ONLY'));
for(const recipients of [['b'],null,undefined]){const bad=JSON.parse(JSON.stringify(r));bad.payload.events[0].recipient_ids=recipients;assert(!SocietyReplay.normalize(bad).available);}
""")

    def test_mentions_and_reply_text_are_not_scene_communication(self):
        self.node(r"""
const r=record([row('0','b','Beta','hello'),row('1','a','Alpha','Beta please check','2025-04-22T18:01:00Z')]);r.payload.messages[1].reply_to='0';
const m=SocietyReplay.normalize(r);assert.equal(m.events[1].mentions.length,1);assert(m.events[1].reply);
const h=SocietyReplay.render({record:r,initialState:{cursor:1}});assert(!h.includes('<g class="sr-reference-edge">'));
r.payload.messages[1].recipient_ids=['b','not-in-source'];const addressed=SocietyReplay.normalize(r);assert.equal(addressed.actors.length,2);assert.equal(addressed.events[1].addresses.join(','),'agent:b');
assert(SocietyReplay.render({record:r,initialState:{cursor:1}}).includes('<g class="sr-reference-edge">'));
""")

    def test_conflicting_or_malformed_audience_does_not_invent_scope(self):
        self.node(r"""
const r=record([row('x')]);r.payload.messages[0].visibility='private';r.payload.messages[0].recipient_ids=['b'];
let m=SocietyReplay.normalize(r);assert.equal(m.events[0].audience.kind,'unknown');assert.equal(m.events[0].addresses.length,0);
r.payload.messages[0].recipient_ids=[];r.payload.messages[0].audience={kind:'room'};m=SocietyReplay.normalize(r);assert.equal(m.events[0].audience.kind,'unknown');
r.payload.messages[0].audience={kind:'private',member_ids:['b','b']};assert.equal(SocietyReplay.normalize(r).events[0].audience.kind,'unknown');
r.payload.messages[0].audience={kind:'private',owner_id:'other'};assert.equal(SocietyReplay.normalize(r).events[0].audience.kind,'unknown');
r.payload.messages[0].recipient_ids=['b','b'];assert(!SocietyReplay.normalize(r).available);
""")

    def test_private_filter_and_prefix_lifecycle_do_not_expose_future_text(self):
        self.node(r"""
const rows=[row('0','a','Alpha','LOCAL-NOW'),row('1','b','Beta','ROOM-NOW','2025-04-22T18:01:00Z'),row('2','a','Alpha','LOCAL-FUTURE','2025-04-22T18:02:00Z')];
rows[0].visibility='private';rows[1].visibility='room';rows[2].visibility='private';const r=record(rows),m=SocietyReplay.normalize(r),d=dom(m),states=[];
const stop=SocietyReplay.attach(d.root,{record:r,onState:s=>states.push(s)});d.fire('change',{},'[data-sr-audience]','private');
assert.equal(stop.getState().audience,'private');assert(d.nodes.get('[data-sr-chat]').innerHTML.includes('LOCAL-NOW'));assert(!d.nodes.get('[data-sr-chat]').innerHTML.includes('LOCAL-FUTURE'));
stop.seek(1);assert(!d.nodes.get('[data-sr-feed]').innerHTML.includes('ROOM-NOW'));assert(!d.nodes.get('[data-sr-scene]').innerHTML.includes('ROOM-NOW'));
d.fire('change',{},'[data-sr-audience]','room');assert(!d.nodes.get('[data-sr-chat]').innerHTML.includes('LOCAL-NOW'));assert(d.nodes.get('[data-sr-chat]').innerHTML.includes('ROOM-NOW'));
d.fire('change',{},'[data-sr-audience]','bogus');assert.equal(stop.getState().audience,'room');stop();assert.equal(d.listeners.size,0);
""")

    def test_action_rationale_is_one_optional_local_record_not_extra_turn(self):
        self.node(r"""
const r=study([turn(0,'a',{action:'inspect_artifact',artifact_id:'f',rationale:'EXPOSED-SUMMARY'},{ok:true,contents:{ready:true}}),turn(1,'a',{action:'send_message',recipient:'b',message:'PUBLIC-SEND'},{ok:true})]);
const m=SocietyReplay.normalize(r);assert(m.available);assert.equal(m.events.length,2);assert.equal(m.events[0].audience.kind,'action');
const h=SocietyReplay.render({record:r,initialState:{cursor:1}});assert(h.includes('sr-lane-private'));assert(h.includes('Recorded decision summary'));assert(!h.includes('HIDDEN PRIVATE STATE'));assert(!h.includes('HIDDEN PROMPT'));
const local=SocietyReplay.render({record:r,initialState:{cursor:1,audience:'private'}});assert(local.includes('EXPOSED-SUMMARY'));assert(!local.includes('PUBLIC-SEND'));assert(!local.includes('<g class="sr-reference-edge">'));
assert.equal(SocietyReplay.peek(r,{cursor:1,audience:'private'}).total_turns,2);assert(h.includes('tool-confirmed send'));assert(h.includes('Contents returned by this tool'));
r.payload.runs[0].turns[0].action.rationale={private:'fake'};assert(!SocietyReplay.normalize(r).available);
""")

    def test_tools_channels_and_interventions_keep_separate_types(self):
        self.node(r"""
const r=eventRun([{id:'c',kind:'tool.called',occurred_at:'2025-04-22T18:00:00Z',actor_id:'a',data:{call_id:'c',tool_name:'search',arguments:{q:'x'}}},
{id:'m',kind:'message.sent',occurred_at:'2025-04-22T18:00:01Z',actor_id:'a',recipient_ids:['b'],data:{content:'ROOMPOST',channel_id:'team',visibility:'room'}},
{id:'i',kind:'intervention.delivered',occurred_at:'2025-04-22T18:00:02Z',actor_id:'a',recipient_ids:['b'],data:{content:'NOTE',intervention_id:'n'}}]);
const m=SocietyReplay.normalize(r);assert(m.available);assert.equal(m.events[0].audience.kind,'action');assert.equal(m.events[1].audience.kind,'room');assert(m.rooms.includes('team'));
const h=SocietyReplay.render({record:r,initialState:{cursor:2}});assert(h.includes('sr-lane-action'));assert(h.includes('sr-lane-room'));assert(h.includes('Intervention record'));assert(h.includes('logged recipient'));
assert(h.includes('Room membership and reading are not supplied'));assert(!h.includes('everyone read'));
""")

    def test_html_escaping_and_member_lists_do_not_create_recipients(self):
        self.node(r"""
const r=record([row('x','a','<svg onload=evil>','<script>local</script>')]);r.payload.messages[0].visibility='room';r.payload.messages[0].channel_name='<img onerror=evil>';r.payload.messages[0].audience={kind:'room',member_ids:['b']};
const m=SocietyReplay.normalize(r);assert(m.available);assert.equal(m.events[0].addresses.length,0);assert.equal(m.actors.length,1);
const h=SocietyReplay.render({record:r});assert(h.includes('&lt;script&gt;local'));assert(h.includes('&lt;img onerror'));assert(!h.includes('<img onerror'));assert(!h.includes('<svg onload'));assert(h.includes('Members are explicitly declared'));
""")


if __name__ == '__main__':
    unittest.main()
