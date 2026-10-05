"""Execute the inert episode renderer with exact source/comparator fixtures.

Authored values test UI source boundaries, not empirical behavior or calibration.
No jobs, provider calls, local source rereads, or registry mutations occur.
"""
import copy
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which('node')
VARIANTS = ('baseline_exact', 'explicit_short_expanded_exact', 'unicode_baseline', 'unicode_expanded')


def fixture():
    def ref(identity, version=1):
        return {'id': identity, 'version': version, 'hash': 'a' * 64}

    sources = {kind: ref(kind + '-original', 2 if kind == 'dataset' else 3)
               for kind in ('dataset', 'discovery', 'selected_audit', 'temporal_audit')}
    comparison = {'id': 'graph-lead-original', 'feature': 'bridge_dependence',
                  'window_id': 'window-focal', 'comparison_window_id': 'window-ordinary'}
    windows = {identity: {'id': identity, 'room_id': 'room-original',
                         'start': '2025-04-18T18:00:00.000000Z' if identity.endswith('focal') else '2025-04-18T19:00:00.000000Z',
                         'end_exclusive': '2025-04-18T19:00:00.000000Z' if identity.endswith('focal') else '2025-04-18T20:00:00.000000Z'}
               for identity in ('window-focal', 'window-ordinary')}
    measurement = {policy: {variant: {'available': True, 'value': 1, 'comparison_value': 0,
                                     'difference': 1, 'direction': 'positive', 'supported': True}
                           for variant in VARIANTS} for policy in ('native', 'fixed_pair')}
    temporal = {identity: {'node_ids': ['A', 'B', 'C'], 'variants': {
        variant: {'available': True, 'static': {'reachable_pair_count': 4,
                                              'maximum_bridge_loss_fraction': 1},
                  'strict_temporal': {'reachable_pair_count': 3,
                                      'maximum_bridge_loss_fraction': 0},
                  'static_only_pair_count': 1} for variant in VARIANTS}}
        for identity in windows}
    gates = {key: True for key in ('local_registry_body_hash_verified', 'exact_source_parent_binding',
                                  'current_producer_byte_pins_match', 'stored_proof_binding_verified',
                                  'stored_proof_passed')}

    def entry(name, summary):
        return {'available': True, 'reason': None, 'summary': summary,
                'ref': ref(name + '-exact'), 'stored_proof_ref': ref('verification-' + name),
                'gates': copy.deepcopy(gates)}

    actors = {'measurement': 'Actor/time records', 'by_original_window': {
        identity: {'records': 1011, 'action_counts': {'WAIT': 2, 'PAUSE': 0,
                                                      'START_USING_COMPUTER': 505,
                                                      'STOP_USING_COMPUTER': 504},
                   'room_status_counts': {'missing': 1011, 'known': 0, 'invalid': 0}}
        for identity in windows}, 'room_relationship': 'ACTOR_SENTINEL: missing rooms remain unassigned.',
        'clock_scope': 'Recorded export-clock convention; not synchronized elapsed time.',
        'interpretation': 'Logged choices are not inactivity or successful leases.'}
    waits = {'measurement': 'Literal marker messages and fixed comparisons',
             'by_original_author_window': {identity: {group: {'messages': 239,
                 'by_horizon_seconds': {str(h): {'messages_with_candidate': 1,
                     'status_counts': {'candidate_observed': 1,
                                      'no_indexed_candidate_boundary_censored': 238}}
                     for h in (30, 60, 300)}} for group in ('marker', 'nonmarker_control')}
                 for identity in windows},
             'candidate_scope': 'WAIT_SENTINEL: retain original union-of-query-window censor flags.',
             'fixed_control_selection': 'Not negative semantic ground truth or a probability sample.',
             'clock_scope': 'Raw chat clock policies unavailable.',
             'room_relationship': 'Missing event rooms stay unassigned.',
             'interpretation': 'Nested horizons and windows reuse events; no detector accuracy.'}
    hodge = {'measurement': 'Static forward-minus-reverse named-reference counts',
             'by_original_window': {identity: {variant: {'node_count': 3, 'supported_edges': 3,
                 'balanced_supported_edges': 1, 'source_reference_events': 7,
                 'energies': {'signal': {'squared_norm': 497, 'fraction_of_signal': 1},
                              'gradient': {'squared_norm': 497 - 1e-16, 'fraction_of_signal': 1},
                              'circulation': {'squared_norm': 1e-16, 'fraction_of_signal': 1e-19}},
                 'curl': None, 'harmonic': None} for variant in VARIANTS} for identity in windows},
             'faces': None, 'interpretation': 'HODGE_SENTINEL: time order discarded; no hierarchy or physical traffic.'}
    observations = {'available': True, 'reason': None,
                    'source_refs': copy.deepcopy(sources), 'registered_comparison': copy.deepcopy(comparison),
                    'original_windows': copy.deepcopy(windows),
                    'base_context_gates': {key: True for key in ('local_registry_body_hashes_verified',
                        'current_producer_byte_pins_match', 'exact_original_comparison_verified')},
                    'observations': {'actor_events': entry('actor', actors),
                                     'wait_markers': entry('wait', waits),
                                     'edge_algebra': entry('hodge', hodge)},
                    'fresh_source_attestation': False, 'raw_or_index_reread': False,
                    'operator_rerun': False, 'model_calls': 0, 'database_writes': 0,
                    'search_scope': {'verification': {'limit': 64, 'possibly_truncated': True}},
                    'bounds': {'max_output_bytes': 24000}}
    evidence = {'id': 'message-source-original', 'timestamp': windows['window-focal']['start'],
                'agent_name': 'Original speaker', 'room_id': 'room-original',
                'content': 'Waiting for an explicit handoff; unrelated work remains possible.',
                'source': {'file': 'bounded-chat.jsonl.gz', 'line': 42},
                'full_content_sha256': 'b' * 64, 'content_truncated': True}
    behavior = {'available': True, 'reason': None, 'ref': ref('behavior-original', 4),
                'payload': {'name': 'Original reviewed hypothesis', 'status': 'candidate',
                    'summary': 'Task-specific dependency versus sparse-reference explanation.',
                    'operational_definition': 'Original source-linked hypothesis.',
                    'alternative_explanations': ['Ordinary efficient queueing.', 'Unobserved channel or name extraction.'],
                    'falsifiable_predictions': ['Independent work persists while artifact work waits.'],
                    'experiment_fit': 'requires_new_environment', 'fit_reason': 'Task dependency must be explicit.',
                    'skeptic': {'summary': 'Historical mechanism unestablished.', 'unsupported_claims': ['No mental-state claim.']}}}
    packet = {'workspace_version': 'episode-workspace-v1', 'available': True, 'reason': None,
              'source_refs': sources, 'comparison': comparison, 'windows': windows,
              'lead': {'id': comparison['id'], 'feature': comparison['feature'], 'title': 'Selected bridge lead',
                       'description': 'Original data-selected structural contrast.',
                       'value': 1, 'comparison_value': 0, 'difference': 1,
                       'alternative_explanations': ['Original lead rival.'], 'requires': [], 'right_censored': False},
              'measurement': measurement, 'temporal': temporal,
              'evidence': {'focal': [evidence], 'comparator': [copy.deepcopy(evidence)], 'limits': {'messages_per_group': 12}},
              'behavior': behavior, 'recorded_observations': observations,
              'model_calls': 0, 'database_writes': 0, 'fresh_source_attestation': False,
              'scope': 'Recorded source-bound exploration only; no status promotion.'}
    expected = {'source_refs': copy.deepcopy(sources), 'lead_id': comparison['id'],
                'comparison': copy.deepcopy(comparison), 'behavior_ref': copy.deepcopy(behavior['ref'])}
    return {'packet': packet, 'expected': expected}


PRELUDE = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const fixture=JSON.parse(fs.readFileSync(0,'utf8')),c={};
let calls=0;
c.fetch=()=>{calls++;throw new Error('No retrieval allowed in renderer')};
c.submit=()=>{calls++;throw new Error('No job allowed in renderer')};
vm.createContext(c);vm.runInContext(fs.readFileSync('web/episode-workspace.js','utf8'),c);
const ui=c.EpisodeWorkspace,clone=x=>JSON.parse(JSON.stringify(x));
let p=fixture.packet,e=fixture.expected;
'''


@unittest.skipUnless(NODE, 'Node.js required for executable browser-component tests')
class EpisodeWorkspaceUITests(unittest.TestCase):
    def run_js(self, assertions):
        run = subprocess.run([NODE, '-e', PRELUDE + assertions], input=json.dumps(fixture()),
                             cwd=ROOT, text=True, capture_output=True, timeout=20)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_exact_original_sources_pair_and_scopes_render(self):
        self.run_js(r'''
assert(ui.validate(p,e).available);
const html=ui.render(p,e,'Which task-specific mechanism can be falsified?');
for(const key of ['Native window nodes','Fixed nodes within original pair','STATIC-ONLY PAIRS',
 '2025-04-18T18:00:00.000000Z','2025-04-18T19:00:00.000000Z','Original comparator',
 'window-focal','window-ordinary','room-original','bounded-chat.jsonl.gz','42',
 'ACTOR_SENTINEL','WAIT_SENTINEL','HODGE_SENTINEL','Ordinary efficient queueing.',
 'Independent work persists while artifact work waits.','data-open-version="4"',
 'Content excerpt truncated.','original union-of-query-window','No instrument is silently selected'])assert(html.includes(key),key);
assert(html.includes('≈ 0'));assert(html.includes('Unknown / Unknown'));
assert(!html.includes('data-action='));assert.equal(calls,0);
''')

    def test_ref_type_hash_and_original_comparison_tampering_fail_closed(self):
        self.run_js(r'''
const attacks=[x=>x.source_refs.dataset.version=true,x=>x.source_refs.dataset.version=2.0+0.5,
 x=>x.source_refs.dataset.hash='f'.repeat(64),x=>x.source_refs.discovery.id='discovery-latest',
 x=>x.source_refs.selected_audit.kind='selected_lead_audit',x=>x.source_refs.temporal_audit=null,
 x=>x.comparison.comparison_window_id='window-new-matched',x=>x.comparison.feature='incoming_concentration',
 x=>x.comparison.extra='ignored?',x=>x.lead.id='graph-lead-other',x=>x.windows['window-focal'].id='window-other',
 x=>x.windows['window-latest']=x.windows['window-focal'],x=>x.model_calls=false,
 x=>x.database_writes=true,x=>x.fresh_source_attestation=true];
for(const attack of attacks){const x=clone(p);attack(x);assert(!ui.validate(x,e).available);
 const html=ui.render(x,e);assert(!html.includes('<table>'));assert(!html.includes('ACTOR_SENTINEL'));
 assert(html.includes('No quantitative channel tables'));}
const bad=clone(e);bad.lead_id='graph-lead-other';assert(!ui.validate(p,bad).available);
assert(!ui.validate(p,null).available);assert.equal(calls,0);
''')

    def test_unavailable_base_and_per_channel_gates_do_not_publish_tables(self):
        self.run_js(r'''
for(const key of ['actor_events','wait_markers','edge_algebra']){
 const x=clone(p),entry=x.recorded_observations.observations[key],sentinel={actor_events:'ACTOR_SENTINEL',wait_markers:'WAIT_SENTINEL',edge_algebra:'HODGE_SENTINEL'}[key];
 for(const gate of Object.keys(entry.gates)){const y=clone(x);y.recorded_observations.observations[key].gates[gate]=false;
  const html=ui.render(y,e);assert(!html.includes(sentinel));assert(html.includes('Unknown —'));}
 entry.available=false;entry.reason='No matching source in bounded newest scope';entry.summary=null;
 const html=ui.render(x,e);assert(!html.includes(sentinel));assert(html.includes(entry.reason));
}
const x=clone(p);x.recorded_observations.base_context_gates.exact_original_comparison_verified=false;
let html=ui.render(x,e);for(const s of ['ACTOR_SENTINEL','WAIT_SENTINEL','HODGE_SENTINEL','1011','239','497'])assert(!html.includes(s));assert(!html.includes('<table>'));
const y=clone(p);y.recorded_observations.source_refs.dataset.hash='c'.repeat(64);
html=ui.render(y,e);assert(!html.includes('ACTOR_SENTINEL'));assert(!html.includes('<table>'));assert(html.includes('exact sources, original comparison'));
const z=clone(p);z.available=false;z.reason='Current source/code gates unavailable';
html=ui.render(z,e);assert(!html.includes('<table>'));assert(html.includes(z.reason));
assert.equal(calls,0);
''')

    def test_all_quantitative_layers_require_exact_recorded_base_gates(self):
        self.run_js(r'''
const attacks=[x=>x.recorded_observations=null,
 x=>x.recorded_observations.source_refs.temporal_audit.version=4,
 x=>x.recorded_observations.registered_comparison.comparison_window_id='window-other',
 x=>x.recorded_observations.original_windows['window-focal'].start='2025-04-18T17:59:00.000000Z',
 x=>x.recorded_observations.original_windows['window-ordinary'].room_id='room-guessed',
 x=>x.recorded_observations.original_windows['window-extra']=x.recorded_observations.original_windows['window-focal'],
 x=>x.recorded_observations.model_calls=false,x=>x.recorded_observations.operator_rerun=true,
 x=>x.recorded_observations.raw_or_index_reread=true];
for(const key of Object.keys(p.recorded_observations.base_context_gates)){
 attacks.push(x=>x.recorded_observations.base_context_gates[key]=false);
 attacks.push(x=>x.recorded_observations.base_context_gates[key]=1);
}
for(const attack of attacks){const x=clone(p);attack(x);assert.strictEqual(ui.validate(x,e).available,false);
 const html=ui.render(x,e);assert(!html.includes('<table>'));assert(!html.includes('Original saved graph quantities'));
 assert(!html.includes('SAVED DELTA'));assert(!html.includes('STATIC PAIRS'));assert.equal(calls,0);}
''')

    def test_behavior_requires_requested_exact_pin_without_substitution(self):
        self.run_js(r'''
const without=clone(e);delete without.behavior_ref;
let gate=ui.validate(p,without),html=ui.render(p,without);
assert.strictEqual(gate.available,true);assert.strictEqual(gate.behavior_available,false);
assert(!html.includes('Original reviewed hypothesis'));assert(!html.includes('Ordinary efficient queueing.'));
assert(html.includes('Original lead rival.'));assert(html.includes('No behavior was explicitly requested'));
for(const attack of [x=>x.version=5,x=>x.hash='f'.repeat(64),x=>x.id='behavior-unsolicited',x=>x.version=true,x=>x.kind='behavior']){
 const expected=clone(e);attack(expected.behavior_ref);gate=ui.validate(p,expected);assert(gate.available);assert(!gate.behavior_available);
 html=ui.render(p,expected);assert(!html.includes('Original reviewed hypothesis'));assert(!html.includes('Ordinary efficient queueing.'));
 assert(html.includes('Requested exact behavior pin'));assert(html.includes('<table>'));
}
const good=ui.render(p,e);assert(good.includes('Original reviewed hypothesis'));assert(good.includes('Ordinary efficient queueing.'));
assert.equal(calls,0);
''')

    def test_unknown_numeric_channels_are_not_coerced_to_zero(self):
        self.run_js(r'''
const x=clone(p);
x.lead.value=null;x.lead.difference='0';x.measurement.native.baseline_exact.available=false;
x.temporal['window-focal'].variants.baseline_exact.available=false;
x.recorded_observations.observations.actor_events.summary.by_original_window['window-focal'].records=null;
x.recorded_observations.observations.edge_algebra.summary.by_original_window['window-focal'].baseline_exact.energies.gradient.squared_norm=null;
const html=ui.render(x,e);assert(html.includes('Unknown'));assert(!html.includes('>NaN<'));assert(!html.includes('>undefined<'));
assert(html.includes('Missing event rooms stay unassigned.'));
assert(html.includes('Raw chat clock policies unavailable.'));
assert(html.includes('Curl and harmonic') || html.includes('curl and harmonic'));
assert.equal(calls,0);
''')

    def test_unmatched_behavior_has_no_rivals_from_another_episode(self):
        self.run_js(r'''
const x=clone(p);x.behavior={available:false,reason:'Behavior belongs to a different original discovery version',ref:null,payload:null};
const html=ui.render(x,e);assert(!html.includes('Ordinary efficient queueing.'));
assert(html.includes('Original lead rival.'));assert(html.includes(x.behavior.reason));
assert(html.includes('No exact matching reviewed behavior was selected'));
assert(!html.includes('data-open-version="4"'));assert.equal(calls,0);
''')

    def test_untrusted_text_is_escaped_and_question_transfer_is_inert(self):
        self.run_js(r'''
const x=clone(p),evil='<img src=x onerror="evil()">';
x.lead.title=evil;x.lead.description=evil;x.behavior.payload.alternative_explanations=[evil];
x.evidence.focal[0].content=evil;x.evidence.focal[0].source.file=evil;
const html=ui.render(x,e,'</textarea><script>evil()</script>');
assert(!html.includes('<img src=x'));assert(!html.includes('<script>'));assert(html.includes('&lt;img'));
assert(html.includes('&lt;/textarea&gt;'));assert(html.includes('data-episode-question'));
assert(html.includes('type="button" data-episode-transfer-question'));assert(html.includes('Copies this question into Environment authoring.'));
const draft=ui.draft('  Does task-specific waiting preserve independent work?  ');
assert.equal(draft.research_question,'Does task-specific waiting preserve independent work?');
assert.strictEqual(draft.behavior_id,null);assert.deepEqual(Object.keys(draft).sort(),['behavior_id','research_question']);
for(const value of [null,false,'',' '.repeat(8),'x'.repeat(4001)])assert.throws(()=>ui.draft(value));
assert.equal(calls,0);
''')


if __name__ == '__main__':
    unittest.main()
