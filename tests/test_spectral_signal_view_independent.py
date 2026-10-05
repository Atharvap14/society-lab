"""Independent saved-signal consistency and inert-rendering boundaries.

Tiny authored fixtures use the actual producer shape, without registry/source
reads. These checks do not reauthenticate or recompute production numerics.
"""
import json
from pathlib import Path
import subprocess
import unittest

from tests.test_spectral_signal_view import fixture, NODE

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const packet=JSON.parse(fs.readFileSync(0,'utf8')),clone=x=>JSON.parse(JSON.stringify(x));
let effects=0;const forbidden=()=>{effects++;throw new Error('Saved signal rendering must be inert')};
const app={live:false,jobs:[],calls:400},initialApp=JSON.stringify(app);
const c={app,fetch:forbidden,submit:forbidden,setTimeout:forbidden,setInterval:forbidden,
 XMLHttpRequest:forbidden,WebSocket:forbidden,document:{querySelector:forbidden}};
vm.createContext(c);vm.runInContext(fs.readFileSync('web/spectral-signal-view.js','utf8'),c);
const ui=c.SpectralSignalView,opt={signalId:'completion_report'},s=x=>x.observable_signals.completion_report;
const finish=()=>{assert.equal(effects,0);assert.equal(JSON.stringify(app),initialApp)};
'''


@unittest.skipUnless(NODE, 'Node.js required for independent saved-signal checks')
class SpectralSignalViewIndependentTests(unittest.TestCase):
    def run_js(self, assertions, *, missing=False, no_edges=False):
        projection = fixture(missing=missing, no_edges=no_edges)
        if projection['spectral'].get('available') is not True:
            self.skipTest('Optional numerical fixture backend unavailable')
        result = subprocess.run([NODE, '-e', SCRIPT + assertions], input=json.dumps(projection),
            cwd=ROOT, text=True, encoding='utf-8', capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_alternative_spectrum_cannot_borrow_saved_basis_scope(self):
        self.run_js(r'''
assert(ui.validate(packet,opt).full.available);
const x=clone(packet),v=s(x);
v.eigenspace_energy=[{eigenvalue:0,energy:.25,multiplicity:1},{eigenvalue:2,energy:0,multiplicity:2}];
v.signal_energy=.25;v.positive_frequency_energy=0;v.rayleigh_smoothness=0;
v.null_energy_fraction=1;v.low_positive_frequency_energy_fraction=null;
const checked=ui.validate(x,opt);assert.equal(checked.available,true);assert.equal(checked.full.available,false);
const html=ui.render(x,opt);assert(html.includes('50.0%'));assert(!html.includes('Grouped eigenspace energy'));
finish();
''')

    def test_node_rate_bounds_are_count_proportions_not_roundoff_tolerance(self):
        self.run_js(r'''
for(const value of [-1e-9,-Number.MIN_VALUE,1+1e-9]){
 const x=clone(packet);s(x).rates.b=value;
 assert.equal(ui.validate(x,opt).available,false);assert(!ui.render(x,opt).includes('<table>'));}
const missing=clone(packet);s(missing).rates.a=null;
assert.equal(ui.validate(missing,opt).available,false);finish();
''')

    def test_missing_denominator_is_unknown_even_with_zero_hits(self):
        self.run_js(r'''
const checked=ui.validate(packet,opt),html=ui.render(packet,opt);
assert.equal(checked.available,true);assert.equal(checked.full.available,false);
assert.equal(checked.induced.available,true);assert.deepEqual(Array.from(checked.measured),['a','b']);
assert.deepEqual(Array.from(checked.missing),['c']);assert.equal(s(packet).denominators.c,0);
assert.equal(s(packet).positive_message_ids.c.length,0);
assert(html.includes('Unknown · no authored denominator'));assert(html.includes('0.0%'));
for(const mutation of [x=>s(x).denominators.a=true,x=>s(x).denominators.a=2.5,
 x=>s(x).positive_message_ids.c=['unknown-positive'],x=>s(x).missing_signal_nodes=['a'],
 x=>s(x).positive_message_ids.b=['m1']]){
 const x=clone(packet);mutation(x);assert.equal(ui.validate(x,opt).available,false);}
finish();
''', missing=True)

    def test_induced_population_cannot_fill_full_graph_or_overlap_exclusions(self):
        self.run_js(r'''
for(const mutation of [x=>s(x).induced_author_subgraph.included_nodes=['a','c'],
 x=>s(x).induced_author_subgraph.excluded_nodes=['b'],
 x=>s(x).induced_author_subgraph.included_nodes=['a','b','c'],
 x=>s(x).induced_author_subgraph.excluded_nodes=['c','c'],
 x=>s(x).induced_author_subgraph.rates.b=-1e-9]){
 const x=clone(packet);mutation(x);const checked=ui.validate(x,opt);
 assert.equal(checked.available,true);assert.equal(checked.full.available,false);
 assert.equal(checked.induced.available,false);assert(!ui.render(x,opt).includes('Grouped eigenspace energy'));}
const html=ui.render(packet,opt);assert(html.includes('different graph'));
assert(html.includes('does not fill the full graph’s missing rates'));finish();
''', missing=True)

    def test_all_isolates_nonzero_signal_and_zero_signal_have_distinct_ratios(self):
        self.run_js(r'''
const v=ui.validate(packet,opt);assert(v.full.available);assert.equal(v.basis.nullity,3);
assert.equal(v.full.summary.signal_energy,.25);assert.equal(v.full.summary.null_energy_fraction,1);
assert.equal(v.full.summary.positive_frequency_energy,0);
assert.equal(v.full.summary.low_positive_frequency_energy_fraction,null);
const html=ui.render(packet,opt);assert(html.includes('All modes are null'));
assert(html.includes('Isolates have zero Laplacian rows'));assert(html.includes('is not agreement'));
const zero=ui.validate(packet,{signalId:'correction'});assert(zero.full.available);
assert.equal(zero.full.summary.signal_energy,0);assert.equal(zero.full.summary.null_energy_fraction,null);
assert.equal(zero.full.summary.rayleigh_smoothness,null);finish();
''', no_edges=True)

    def test_first_value_grouping_and_near_zero_band_do_not_change_basis_nullity(self):
        self.run_js(r'''
const x=clone(packet),v=s(x);
x.spectral.eigenvalues=[0,5e-9,1.1e-8];x.spectral.nullity=1;x.spectral.isolated_ids=[];
v.eigenspace_energy=[{eigenvalue:0,energy:.2,multiplicity:2},{eigenvalue:1.1e-8,energy:.05,multiplicity:1}];
v.signal_energy=.25;v.positive_frequency_energy=.05;v.rayleigh_smoothness=2.2e-9;
v.null_energy_fraction=.8;v.low_positive_frequency_energy_fraction=1;
assert(ui.validate(x,opt).full.available);
const html=ui.render(x,opt);assert(html.includes('1 recorded null modes'));
assert(html.includes('separate 10⁻⁸ near-zero threshold'));assert(html.includes('Basis eigenvalues'));
const boundary=clone(packet),b=s(boundary);
boundary.spectral.eigenvalues=[0,1e-8,2];boundary.spectral.nullity=1;boundary.spectral.isolated_ids=[];
b.eigenspace_energy=[{eigenvalue:0,energy:.15,multiplicity:1},
 {eigenvalue:1e-8,energy:.05,multiplicity:1},{eigenvalue:2,energy:.05,multiplicity:1}];
b.signal_energy=.25;b.positive_frequency_energy=.05;b.rayleigh_smoothness=.400000002;
b.null_energy_fraction=.8;b.low_positive_frequency_energy_fraction=0;
assert(ui.validate(boundary,opt).full.available);finish();
''')

    def test_untrusted_text_does_not_inject_options_or_operational_routes(self):
        self.run_js(r'''
const x=clone(packet),label='completion_report\" data-action=\"run\"><script>bad()</script>';
x.observable_signals[label]=clone(s(x));x.observable_signals[label].observable=label;
x.observable_signals[label].detector_version='</p><script>bad()</script>';
x.nodes[0].name='\" onmouseover=\"bad() <img src=x>';
x.provider_envelope='PRIVATE_PROVIDER_NOT_SHOWN';x.commands='PRIVATE_COMMAND_NOT_SHOWN';
const html=ui.render(x,{signalId:label});assert(!html.includes('<script>'));
assert(!html.includes('<img src=x>'));assert(html.includes('&lt;script&gt;'));
assert(html.includes('&quot;'));assert(!html.includes('PRIVATE_PROVIDER_NOT_SHOWN'));
assert(!html.includes('PRIVATE_COMMAND_NOT_SHOWN'));
assert(!/\sdata-action="/.test(html));finish();
''')

    def test_stale_instrument_is_unavailable_without_fallback_or_input_mutation(self):
        self.run_js(r'''
const before=JSON.stringify(packet),stale={signalId:'instrument-no-longer-saved'};
assert.equal(ui.validate(packet,stale).available,false);
const html=ui.render(packet,stale);assert(html.includes('not substituted'));
assert(!html.includes('<table>'));assert(!html.includes('<select'));
ui.render(packet,opt);ui.render(packet,{signalId:'correction'});
assert.equal(JSON.stringify(packet),before);finish();
''')


if __name__ == '__main__':
    unittest.main()
