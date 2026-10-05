"""Real dashboard glue for saved language-signal presentation and selection."""
import json
import subprocess
import unittest

from tests.test_episode_workspace_routes import NODE, ROOT, PRELUDE
from tests.test_episode_workspace_ui import fixture as episode_fixture
from tests.test_spectral_signal_view import fixture as signal_fixture


@unittest.skipUnless(NODE, 'Node required for dashboard signal routes')
class SpectralSignalRouteTests(unittest.TestCase):
    def run_js(self, body):
        packet = episode_fixture()
        packet['projection'] = signal_fixture()
        setup = PRELUDE + r'''
vm.runInContext(fs.readFileSync('web/spectral-signal-view.js','utf8'),c);
const projection=f.projection;
let renders=0;c.render=async()=>{renders++};
'''
        result = subprocess.run([NODE, '-e', setup + body], input=json.dumps(packet),
                                text=True, capture_output=True, cwd=ROOT, timeout=25)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_real_panel_uses_saved_selection_keeps_raw_output_and_missing_instrument_unknown(self):
        self.run_js(r'''
run("app.spectralSignal='completion_report'");
const html=c.spectralObservablePanel(projection);
assert(html.includes('Node language signal'));assert(html.includes('50.0%'));
assert(html.includes('Observable language signals on this graph'));
assert(html.includes('data-spectral-signal'));assert(html.includes('value="completion_report" selected'));
run("app.spectralSignal='instrument-not-recorded'");
const unavailable=c.spectralObservablePanel(projection);
assert(unavailable.includes('not substituted'));assert(!unavailable.includes('Node language signal'));
assert.equal(requests.length,0);
''')

    def test_instrument_selection_and_scope_changes_render_without_calls_or_flag_changes(self):
        self.run_js(r'''
(async()=>{
run("app.live=true;app.harness='codex';app.selectedNode='old-node';app.spectralSignal=null");
await listeners.change({target:{dataset:{spectralSignal:''},value:'completion_report'}});
assert.equal(run('app.spectralSignal'),'completion_report');assert.equal(renders,1);
await listeners.change({target:{dataset:{},id:'projection',value:'observed_replies'}});
assert.equal(run('app.spectralSignal'),null);assert.equal(run('app.selectedNode'),null);
run("app.spectralSignal='correction'");
await listeners.change({target:{dataset:{select:'discovery'},value:'another-discovery'}});
assert.equal(run('app.spectralSignal'),null);assert.equal(run('app.selected.discovery'),'another-discovery');
assert.equal(run('app.live'),true);assert.equal(run('app.harness'),'codex');assert.equal(requests.length,0);
})().catch(e=>{console.error(e.stack);process.exitCode=1});
''')

    def test_saved_absent_and_malformed_channels_do_not_create_quantities(self):
        self.run_js(r'''
assert.equal(c.spectralObservablePanel({nodes:[]}), '');
const malformed={nodes:projection.nodes,observable_signals:{untyped:{}}};
assert(!c.spectralObservablePanel(malformed).includes('Node language signal'));
assert(!c.spectralObservablePanel(malformed).includes('Grouped eigenspace energy'));
assert.equal(requests.length,0);
''')
