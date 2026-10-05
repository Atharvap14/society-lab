"""Pure Node rendering checks using authored signals and actual producer schema.

No registry writes, source imports, provider calls, or behavioral claims occur.
Numerical fixtures describe the test graph, not an empirical agent society.
"""
import copy
import json
import shutil
import subprocess
import unittest
from pathlib import Path

from swarm_lab.network import spectral_basis
from swarm_lab.spectral_observables import describe_observable_signals

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which('node')


def fixture(*, missing=False, no_edges=False, empty=False):
    ids = [] if empty else ['a', 'b', 'c']
    nodes = [{'id': identity, 'name': 'Agent 😀 <script>escape-me</script>' if identity=='a' else identity}
             for identity in ids]
    edges = [] if no_edges or empty else [
        {'source':'a','target':'b','weight':1}, {'source':'b','target':'c','weight':1}]
    projection = {'nodes':nodes, 'edges':edges, 'spectral':spectral_basis(ids, edges)}
    signals = [] if empty else [
        {'agent_id':'a','speaker_type':'agent','message_id':'m1','labels':['completion_report']},
        {'agent_id':'a','speaker_type':'agent','message_id':'m2','labels':[]},
        {'agent_id':'b','speaker_type':'agent','message_id':'m3','labels':[]}]
    if not missing and not empty:
        signals.append({'agent_id':'c','speaker_type':'agent','message_id':'m4','labels':[]})
    discovery = {'signals':signals, 'detector_version':'authored-fixture-v1',
                 'network':{'projections':{'observed_mentions':projection}}}
    projection['observable_signals'] = describe_observable_signals(discovery)['observed_mentions']
    return projection


SCRIPT = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const [source,scenario]=process.argv.slice(1),packet=JSON.parse(fs.readFileSync(0,'utf8'));
const context=vm.createContext({console,JSON,Math,Number,String,Array,Object,Set,Map,fetch(){throw new Error('Rendering attempted network access')}});
vm.runInContext(fs.readFileSync(source,'utf8'),context,{filename:source});const view=context.SpectralSignalView;
const options={signalId:'completion_report'},copy=x=>JSON.parse(JSON.stringify(x));
const selected=p=>p.observable_signals.completion_report;
function unavailable(p,reason){const v=view.validate(p,options);assert.equal(v.available,false,reason);assert.ok(!view.render(p,options).includes('<table>'),reason);}
if(scenario==='normal'){
  const before=JSON.stringify(packet),v=view.validate(packet,options),html=view.render(packet,options);
  assert.equal(v.available,true);assert.equal(v.full.available,true);assert.ok(html.includes('Node language signal'));assert.ok(html.includes('50.0%'));assert.ok(html.includes('0.0%'));
  assert.ok(html.includes('Grouped eigenspace energy'));assert.ok(html.includes('squared raw-rate coordinates'));assert.ok(html.includes('Low-positive / positive energy'));assert.ok(html.includes('xᵢ/√dᵢ'));assert.ok(html.includes('equal raw rates need not be a null signal'));
  assert.ok(html.includes('Agent 😀 &lt;script&gt;escape-me&lt;/script&gt;'));assert.ok(!html.includes('<script>escape-me</script>'));assert.ok(html.includes('data-spectral-signal'));assert.equal(JSON.stringify(packet),before);
}else if(scenario==='missing'){
  const v=view.validate(packet,options),html=view.render(packet,options);assert.equal(v.available,true);assert.equal(v.full.available,false);assert.equal(v.induced.available,true);assert.deepEqual(Array.from(v.missing),['c']);
  assert.ok(html.includes('2 / 3 node denominators observed · 1 missing'));assert.ok(html.includes('Unknown · no authored denominator'));assert.ok(html.includes('Separate induced author subgraph'));assert.ok(html.includes('different graph'));assert.ok(!Object.hasOwn(selected(packet),'rates'));
  const forged=copy(packet);selected(forged).rates={a:.5,b:0,c:0};unavailable(forged,'A referenced nonauthor must not become a zero rate');
  const bad=copy(packet);selected(bad).induced_author_subgraph.excluded_nodes=[];assert.equal(view.validate(bad,options).induced.available,false);assert.ok(!view.render(bad,options).includes('Grouped eigenspace energy'));
}else if(scenario==='zero'){
  const v=view.validate(packet,{signalId:'correction'}),html=view.render(packet,{signalId:'correction'});assert.equal(v.full.available,true);assert.equal(v.full.summary.signal_energy,0);assert.equal(v.full.summary.rayleigh_smoothness,null);assert.equal(v.full.summary.null_energy_fraction,null);assert.equal(v.full.summary.low_positive_frequency_energy_fraction,null);
  assert.ok(html.includes('<dt>Rayleigh ratio xᵀLx / xᵀx</dt><dd>Unknown</dd>'));assert.ok(html.includes('<dt>Null/near-zero / total energy</dt><dd>Unknown'));assert.ok(html.includes('Zero signal energy has unknown ratios'));
}else if(scenario==='no_edges'){
  const v=view.validate(packet,options),html=view.render(packet,options);assert.equal(v.full.available,true);assert.equal(v.basis.nullity,3);assert.ok(html.includes('3 recorded null modes · 3 isolate nodes'));assert.ok(html.includes('All modes are null'));assert.ok(html.includes('is not agreement'));assert.ok(html.includes('Isolates have zero Laplacian rows'));
}else if(scenario==='malformed'){
  for(const change of [p=>selected(p).rates.a=null,p=>selected(p).rates.a=.9,p=>selected(p).denominators.a=true,p=>selected(p).positive_message_ids.a.push('m1'),p=>selected(p).measurement='model_guess',p=>selected(p).denominators.c=0,p=>p.nodes.push({id:'a'}),p=>delete selected(p).positive_message_ids.b]){const changed=copy(packet);change(changed);unavailable(changed,'Malformed node measurement must be withheld');}
  for(const change of [s=>s.signal_energy=null,s=>s.signal_energy=NaN,s=>s.null_energy_fraction=2,s=>s.positive_frequency_energy+=.1,s=>s.eigenspace_energy[0].multiplicity=true,s=>delete s.rayleigh_smoothness]){const changed=copy(packet);change(selected(changed));const v=view.validate(changed,options);assert.equal(v.available,true);assert.equal(v.full.available,false);assert.ok(!view.render(changed,options).includes('Grouped eigenspace energy'));}
  const basis=copy(packet);basis.spectral.node_order=['different'];assert.equal(view.validate(basis,options).full.available,false);
}else if(scenario==='bounds_scope'){
  const large=copy(packet);large.nodes=Array.from({length:129},(_,i)=>({id:'node'+i}));unavailable(large,'Node bound');
  const labels=copy(packet);labels.observable_signals=Object.fromEntries(Array.from({length:33},(_,i)=>['instrument'+i,{}]));unavailable(labels,'Instrument bound');
  const ids=copy(packet);selected(ids).positive_message_ids.a=Array(20001).fill('m');selected(ids).denominators.a=20001;unavailable(ids,'Positive ID bound');
  const missing=view.validate(packet,{signalId:'not-saved'});assert.equal(missing.available,false);assert.ok(view.render(packet,{signalId:'not-saved'}).includes('not substituted'));
  assert.equal(view.validate(null).available,false);assert.equal(view.signalIds({}).length,0);
}else if(scenario==='unavailable_backend'){
  packet.spectral={available:false,operator:'normalized_graph_laplacian',reason:'Optional backend unavailable'};
  const signal=selected(packet);signal.available=false;signal.reason='Optional backend unavailable';
  const v=view.validate(packet,options),html=view.render(packet,options);assert.equal(v.available,true);assert.equal(v.full.available,false);assert.ok(html.includes('50.0%'));assert.ok(html.includes('Optional backend unavailable'));assert.ok(!html.includes('Grouped eigenspace energy'));
}else if(scenario==='empty'){
  const v=view.validate(packet,options),html=view.render(packet,options);assert.equal(v.available,true);assert.equal(v.full.available,true);assert.ok(html.includes('Empty node scope'));assert.ok(html.includes('0 / 0 node denominators observed'));assert.ok(!html.includes('NaN'));assert.ok(!html.includes('Infinity'));
}else if(scenario==='near_zero_roundoff'){
  const s=selected(packet);packet.spectral.eigenvalues=[0,5e-9,2];packet.spectral.nullity=1;packet.spectral.isolated_ids=[];
  s.eigenspace_energy=[{eigenvalue:0,energy:.2,multiplicity:2},{eigenvalue:2,energy:.05,multiplicity:1}];s.signal_energy=.25;s.positive_frequency_energy=.05;s.rayleigh_smoothness=.4;s.null_energy_fraction=.8;s.low_positive_frequency_energy_fraction=0;
  const v=view.validate(packet,options),html=view.render(packet,options);assert.equal(v.full.available,true);assert.ok(html.includes('Null/near-zero band'));assert.ok(html.includes('1 recorded null modes'));assert.ok(html.includes('separate 10⁻⁸ near-zero threshold'));
  const normal=copy(packet);selected(normal).null_energy_fraction=1.0000000000000004;selected(normal).eigenspace_energy=[{eigenvalue:0,energy:.25,multiplicity:3}];selected(normal).positive_frequency_energy=0;selected(normal).rayleigh_smoothness=0;selected(normal).low_positive_frequency_energy_fraction=null;normal.spectral.eigenvalues=[0,0,0];normal.spectral.nullity=3;normal.spectral.isolated_ids=['a','b','c'];
  assert.equal(view.validate(normal,options).full.available,true);assert.ok(view.render(normal,options).includes('1.0000000000000004'));
}else if(scenario==='spectrum_binding'){
  // An energy summary can remain internally coherent while describing modes
  // inconsistent with the recorded full operator. Do not display that table.
  const resealed=copy(packet),s=selected(resealed);
  s.eigenspace_energy=[{eigenvalue:0,energy:.25,multiplicity:1},{eigenvalue:2,energy:0,multiplicity:2}];
  s.signal_energy=.25;s.positive_frequency_energy=0;s.rayleigh_smoothness=0;s.null_energy_fraction=1;s.low_positive_frequency_energy_fraction=null;
  assert.equal(view.validate(resealed,options).available,true);assert.equal(view.validate(resealed,options).full.available,false);
  assert.ok(view.render(resealed,options).includes('recorded operator spectrum'));assert.ok(!view.render(resealed,options).includes('Grouped eigenspace energy'));
  const borrowed=copy(packet);borrowed.spectral.eigenvalues=[0,.5,1.5];borrowed.spectral.nullity=1;borrowed.spectral.isolated_ids=[];
  assert.equal(view.validate(borrowed,options).full.available,false,'A summary must not borrow a different current spectrum');
  const unsorted=copy(packet);unsorted.spectral.eigenvalues.reverse();assert.equal(view.validate(unsorted,options).full.available,false,'A saved spectrum must already be sorted');
  const negative=copy(packet);selected(negative).rates.b=-1e-9;unavailable(negative,'A count proportion cannot be negative within roundoff tolerance');
}else throw new Error('Unknown scenario');
process.stdout.write(JSON.stringify({passed:true,scenario}));
"""


@unittest.skipUnless(NODE, 'Node.js is required for pure spectral presentation checks')
class SpectralSignalViewTests(unittest.TestCase):
    def check(self, scenario, projection=None):
        projection = projection if projection is not None else fixture()
        if projection['spectral'].get('available') is False:
            self.skipTest('Optional numerical producer backend is unavailable')
        result = subprocess.run([NODE, '-e', SCRIPT, str(ROOT/'web/spectral-signal-view.js'), scenario],
            input=json.dumps(projection), capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIs(json.loads(result.stdout)['passed'], True)

    def test_actual_producer_schema_rates_energy_scaling_escape_and_no_mutation(self):
        self.check('normal')

    def test_missing_nonauthor_and_separate_induced_graph_are_not_zero_imputed(self):
        self.check('missing', fixture(missing=True))

    def test_zero_signal_ratios_remain_unknown(self):
        self.check('zero')

    def test_no_edges_isolates_and_disconnected_nullity_do_not_imply_agreement(self):
        self.check('no_edges', fixture(no_edges=True))

    def test_malformed_counts_rates_and_energy_fail_closed_per_measurement(self):
        self.check('malformed')

    def test_bounds_absent_source_and_requested_instrument_do_not_fallback(self):
        self.check('bounds_scope')

    def test_unavailable_backend_keeps_measured_node_rates_without_fake_energy(self):
        self.check('unavailable_backend')

    def test_empty_scope_has_no_fake_ratios_or_nonfinite_display(self):
        self.check('empty', fixture(empty=True))

    def test_near_zero_grouping_is_distinct_from_basis_nullity_and_roundoff_unclipped(self):
        self.check('near_zero_roundoff')

    def test_coherent_resealed_summary_requires_matching_sorted_saved_spectrum(self):
        self.check('spectrum_binding')
