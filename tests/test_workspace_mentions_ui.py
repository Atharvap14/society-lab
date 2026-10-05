"""Local mention interaction against the actual module; no transport or jobs."""
import json
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const input=JSON.parse(fs.readFileSync(0,'utf8')),timers=new Map(),windowListeners=new Map();let timerId=0,networkCalls=0;
function element(){const attrs=new Map(),listeners=new Map();return {attrs,listeners,value:'',selectionStart:0,style:{},innerHTML:'',hidden:false,
 getAttribute:k=>attrs.has(k)?attrs.get(k):null,setAttribute:(k,v)=>attrs.set(k,String(v)),removeAttribute:k=>attrs.delete(k),
 addEventListener:(k,f)=>{if(!listeners.has(k))listeners.set(k,new Set());listeners.get(k).add(f);},
 removeEventListener:(k,f)=>listeners.get(k)?.delete(f),
 fire(k,extra={}){const event={key:'',target:this,preventDefault(){this.prevented=true;},...extra};for(const f of [...(listeners.get(k)||[])])f(event);return event;},
 setSelectionRange(a,b){this.selectionStart=a;this.selectionEnd=b;},focus(){this.focused=true;},
 getBoundingClientRect:()=>({left:25,top:100,bottom:170,width:450}),querySelector:()=>null,
 contains(n){return n.parent===this;},remove(){this.removed=true;},closest(){return this;}};}
const body={children:[],appendChild(e){this.children.push(e);}},document={body,createElement:element};
const context=vm.createContext({assert,document,innerWidth:800,innerHeight:700,
 fetch(){networkCalls++;throw Error('No transport');},
 setTimeout:(f,ms)=>{const id=++timerId;timers.set(id,{f,ms});return id;},clearTimeout:id=>timers.delete(id),
 addEventListener:(k,f)=>windowListeners.set(k,f),removeEventListener:(k,f)=>{if(windowListeners.get(k)===f)windowListeners.delete(k);}});
context.window=context;context.document=document;
vm.runInContext(fs.readFileSync(process.argv[1]+'/web/workspace-mentions.js','utf8'),context);
context.element=element;context.timers=timers;context.body=body;context.windowListeners=windowListeners;
vm.runInContext(`
const A={id:'dataset-source',version:2,hash:'a'.repeat(64)};
const B={id:'dataset-source',version:3,hash:'b'.repeat(64)};
const clone=x=>JSON.parse(JSON.stringify(x));
function choices(){return {items:[{type:'chat',label:'Research discussion',project_name:'Project A',chat_name:'Research discussion',chat_id:'chat-one'},
 {type:'artifact',label:'April observations',project_name:'Project B',chat_name:'Other discussion',ref:clone(A)}],total:2,truncated:false};}
function hold(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
async function settle(){for(let i=0;i<12;i++)await Promise.resolve();}
async function tick(){const pending=[...timers.entries()];timers.clear();for(const[id,row]of pending)row.f();await settle();}
function setup(search=async()=>choices()){
 timers.clear();body.children=[];const textarea=element();textarea.ownerDocument=document;const calls=[],selected=[],changed=[];
 const cleanup=WorkspaceMentions.attach(textarea,{search:q=>{calls.push(q);return search(q);},onSelect:r=>selected.push(r),onChange:v=>changed.push(v),debounceMs:20});
 return {textarea,popup:body.children.at(-1),calls,selected,changed,cleanup,
 type(value,caret=value.length){textarea.value=value;textarea.selectionStart=caret;textarea.fire('input');},
 key(key,extra={}){return textarea.fire('keydown',{key,...extra});},
 click(index){const target={parent:this.popup,dataset:{wmIndex:String(index)},closest(){return this;}};return this.popup.fire('click',{target});}};
}
`,context);
(async()=>{await vm.runInContext('(async()=>{'+input.script+'})()',context,{timeout:10000});assert.equal(networkCalls,0);process.stdout.write('PASS');})()
 .catch(error=>{console.error(error);process.exitCode=1;});
"""


class WorkspaceMentionsUITests(unittest.TestCase):
    def node(self, script):
        result = subprocess.run(["node", "-e", NODE, str(ROOT)], input=json.dumps({"script": script}),
                                text=True, encoding="utf-8", capture_output=True, timeout=25, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "PASS")

    def test_keyboard_selection_inserts_literal_name_and_cloned_exact_ref(self):
        self.node(r"""
const env=setup();env.type('Use @Apr');await tick();assert.deepEqual(env.calls,['Apr']);
assert.equal(env.textarea.getAttribute('role'),'combobox');assert.equal(env.textarea.getAttribute('aria-expanded'),'true');
assert(env.popup.innerHTML.includes('role="listbox"'));assert(env.key('ArrowDown').prevented);
assert.equal(env.cleanup.getState().selected_index,1);assert(env.key('Enter').prevented);
assert.equal(env.textarea.value,'Use @April observations ');assert.equal(env.textarea.selectionStart,24);
assert.deepEqual(env.selected[0].ref,A);assert.deepEqual(env.changed,[env.textarea.value]);
assert.equal(env.cleanup.getState().open,false);assert.equal(env.textarea.getAttribute('aria-expanded'),'false');
env.selected[0].ref.version=99;assert.equal(choices().items[1].ref.version,2);
env.textarea.fire('keyup');await tick();assert.equal(env.calls.length,1,'inserted mention must not reopen itself');
env.cleanup();
""")

    def test_click_selection_preserves_text_after_caret_and_search_has_no_mutations(self):
        self.node(r"""
const env=setup();env.type('Read @Res then compare.',9);await tick();
assert.equal(env.calls[0],'Res');const clicked=env.click(0);assert(clicked.prevented);
assert.equal(env.textarea.value,'Read @Research discussion  then compare.');
assert.deepEqual(env.selected,[{type:'chat',label:'Research discussion',project_name:'Project A',chat_name:'Research discussion',chat_id:'chat-one'}]);
assert.equal(env.textarea.focused,true);assert.equal(env.changed.length,1);env.cleanup();
""")

    def test_selected_literal_mention_stays_closed_during_continuation_but_new_at_queries(self):
        self.node(r"""
const env=setup();env.type('Please read @Res');await tick();env.key('Enter');
const selected=env.textarea.value;assert.equal(env.selected.length,1);
env.type(selected+'and explain the result');await tick();
assert.equal(env.cleanup.getState().open,false);assert.deepEqual(env.calls,['Res']);
env.type(selected+'and compare with @Apr');await tick();
assert.deepEqual(env.calls,['Res','Apr']);assert.equal(env.cleanup.getState().open,true);
env.key('ArrowDown');env.key('Enter');assert.equal(env.selected.length,2);assert.deepEqual(env.selected[1].ref,A);
env.type(env.textarea.value+'afterwards');await tick();assert.equal(env.calls.length,2);env.cleanup();
const nested=setup(async()=>({items:[{type:'artifact',label:'Notes @ tool use',ref:clone(A)}],total:1,truncated:false}));
nested.type('@Notes');await tick();nested.key('Enter');nested.type(nested.textarea.value+'continue normally');await tick();
assert.equal(nested.calls.length,1,'an @ inside the selected saved label is part of that literal mention');nested.cleanup();
""")

    def test_new_query_and_cleanup_withhold_stale_search_results(self):
        self.node(r"""
const older=hold(),newer=hold();const env=setup(q=>q==='old'?older.promise:newer.promise);
env.type('@old');await tick();env.type('@new');await tick();
older.resolve(choices());await settle();assert.equal(env.cleanup.getState().loading,true);
assert.equal(env.cleanup.getState().items.length,0);assert.equal(env.selected.length,0);
newer.resolve({items:[{type:'artifact',label:'Newer exact observations',ref:clone(B)}],total:1,truncated:false});
await settle();assert.equal(env.cleanup.getState().items[0].ref.version,3);
const late=hold(),other=setup(()=>late.promise);other.type('@x');await tick();other.cleanup();
late.resolve(choices());await settle();assert.equal(other.popup.hidden,true);assert.equal(other.popup.removed,true);
assert.equal(other.selected.length,0);assert.equal(other.popup.innerHTML,'');assert.equal(timers.size,0);env.cleanup();
""")

    def test_debounce_only_searches_last_query_and_email_or_long_query_does_not_open(self):
        self.node(r"""
const env=setup();env.type('@a');env.type('@ab');env.type('@abc');await tick();assert.deepEqual(env.calls,['abc']);
env.type('person@example.com');await tick();assert.equal(env.cleanup.getState().open,false);
env.type('@'+'x'.repeat(201));await tick();assert.equal(env.calls.length,1);assert.equal(env.cleanup.getState().open,false);
env.type('Prefix (@');await tick();assert.deepEqual(env.calls,['abc','']);
env.type('@first\nsecond');await tick();assert.equal(env.cleanup.getState().open,false);env.cleanup();
""")

    def test_escape_tab_blur_and_composition_never_select_or_send(self):
        self.node(r"""
const env=setup();env.type('@');await tick();assert.equal(env.key('Enter',{isComposing:true}).prevented,undefined);
assert.equal(env.selected.length,0);assert(env.key('Escape').prevented);env.textarea.fire('keyup');await tick();
assert.equal(env.cleanup.getState().open,false);assert.equal(env.calls.length,1);
env.type('@different');await tick();assert.equal(env.key('Tab').prevented,undefined);assert.equal(env.selected.length,0);
env.type('@again');await tick();env.textarea.fire('blur');assert.equal(env.cleanup.getState().open,false);
assert.equal(env.key('Enter').prevented,undefined,'plain Enter outside menu belongs to the host');env.cleanup();
""")

    def test_invalid_ambiguous_or_oversized_packets_withhold_choices(self):
        self.node(r"""
const bad=[];let p=choices();p.items[1].ref.version=true;bad.push(p);
p=choices();p.items[1].ref.hash='missing';bad.push(p);
p=choices();p.items[0].chat_id='../chat';bad.push(p);
p=choices();p.items[0].label='x'.repeat(241);bad.push(p);
p=choices();p.total=true;bad.push(p);p=choices();p.truncated=1;bad.push(p);
p=choices();p.items=Array(101).fill(p.items[0]);p.total=101;bad.push(p);
p=choices();p.items.push({type:'artifact',label:'Same exact identity',ref:{hash:A.hash,version:A.version,id:A.id}});p.total=3;bad.push(p);
for(const packet of bad){const before=JSON.stringify(packet);const env=setup(async()=>packet);env.type('@');await tick();
 assert.equal(env.cleanup.getState().items.length,0);assert(!env.popup.innerHTML.includes('role="option"'));
 env.key('Enter');assert.equal(env.selected.length,0);assert.equal(JSON.stringify(packet),before);env.cleanup();}
assert.equal(WorkspaceMentions.normalize({items:[],total:0,truncated:false}).available,true);
""")

    def test_escaped_labels_do_not_create_markup_or_implicit_provenance(self):
        self.node(r"""
const packet={items:[{type:'artifact',label:'<img src=x onerror="run()">',project_name:'<script>project</script>',ref:clone(A)}],total:8,truncated:true};
const env=setup(async()=>packet);env.type('@');await tick();
assert(!env.popup.innerHTML.includes('<img'));assert(!env.popup.innerHTML.includes('<script>'));
assert(env.popup.innerHTML.includes('&lt;img'));assert(env.popup.innerHTML.includes('8 matches'));
assert(env.popup.innerHTML.includes('Search to narrow'));env.click(0);
assert.equal(env.textarea.value,'@<img src=x onerror="run()"> ');assert.deepEqual(env.selected[0].ref,A);
assert.equal(env.selected[0].chat_id,undefined,'a saved item without origin must not invent a chat');env.cleanup();
""")

    def test_search_failure_is_unknown_and_later_valid_query_recovers(self):
        self.node(r"""
const env=setup(q=>q==='fail'?Promise.reject(new Error('<credential-shaped diagnostic omitted>')):Promise.resolve(choices()));
env.type('@fail');await tick();assert(env.popup.innerHTML.includes('Saved context is unavailable'));
assert(!env.popup.innerHTML.includes('credential-shaped'));assert.equal(env.cleanup.getState().total,null);
env.type('@success');await tick();assert.equal(env.cleanup.getState().items.length,2);
const state=env.cleanup.getState();state.items[0].chat_id='changed';assert.equal(env.cleanup.getState().items[0].chat_id,'chat-one');env.cleanup();
""")

    def test_cleanup_restores_accessibility_and_caret_change_cannot_select_old_token(self):
        self.node(r"""
const textarea=element();textarea.ownerDocument=document;textarea.setAttribute('role','textbox');textarea.setAttribute('aria-controls','prior-control');
const selected=[];const cleanup=WorkspaceMentions.attach(textarea,{search:async()=>choices(),onSelect:r=>selected.push(r),debounceMs:0});
textarea.value='@x tail';textarea.selectionStart=2;textarea.fire('input');await tick();
textarea.selectionStart=7;textarea.fire('keydown',{key:'Enter'});assert.equal(selected.length,0,'old token coordinates cannot select after caret moves');
cleanup();cleanup();assert.equal(textarea.getAttribute('role'),'textbox');assert.equal(textarea.getAttribute('aria-controls'),'prior-control');
assert.equal(textarea.getAttribute('aria-autocomplete'),null);assert.equal(textarea.getAttribute('aria-expanded'),null);
assert([...textarea.listeners.values()].every(s=>s.size===0));assert.equal(windowListeners.size,0);
""")

    def test_styles_have_scoped_responsive_and_accessible_controls(self):
        css = (ROOT / "web" / "workspace-mentions.css").read_text(encoding="utf-8")
        self.assertIn(".wm-popup[hidden]", css)
        self.assertIn(":focus-visible", css)
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn("max-width:560px", css)
        self.assertNotIn("@import", css)


if __name__ == "__main__":
    unittest.main()
