"""Execute the production render function across a pending read and user edit."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), 'Node is required')
class RenderFocusRaceTests(unittest.TestCase):
    def test_pending_render_preserves_latest_text_and_caret(self):
        script = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('web/app.js','utf8');
const renderSource=source.slice(source.indexOf('async function render() {'), source.indexOf('async function refresh('));
let resolve;const pending=new Promise(r=>resolve=r);
const original={id:'ws-message',value:'ab',selectionStart:2,selectionEnd:2,dataset:{}};
const replacement={value:'stale generated value',focus(){},setSelectionRange(a,b){this.selectionStart=a;this.selectionEnd=b;}};
const main={contains:x=>x===original,innerHTML:'before',querySelector:()=>replacement};
const app={state:{},view:'workspace',activeChatId:'chat-a',rendering:false,pendingRender:false};
const document={activeElement:original,querySelectorAll:()=>[]};
const workspace={hasView:()=>true,render:()=>pending,dispose(){},mount(){}};
const experience={update(){},dispose(){},mount(){}};
const context=vm.createContext({app,main,document,workspace,experience,CSS:{escape:x=>x},header:()=>''});
vm.runInContext(renderSource,context);
(async()=>{
const active=context.render();
original.value='An independent unsent question.';
original.selectionStart=original.value.length;original.selectionEnd=original.value.length;
resolve('<textarea>stale generated value</textarea>');await active;
assert.equal(replacement.value,original.value);
assert.equal(replacement.selectionStart,original.value.length);
assert.equal(replacement.selectionEnd,original.value.length);
assert.equal(app.rendering,false);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
        result = subprocess.run(['node', '-e', script], cwd=ROOT, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
