"""Actual renderer and captured role packets; no providers or production Store.

Production imports and web paths; fixtures retain the existing design gates.
"""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from swarm_lab import research
from swarm_lab.config import Settings
from swarm_lab.store import Store

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which('node')



LIBRARY_VM = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const sourcePath=process.argv[1],nodes=new Map(),effects={fetch:0,jobs:0,timers:0};
function node(id){if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',open:false,
 classList:{toggle(){},remove(){}},addEventListener(){},contains(){return false},querySelector(){return null}});return nodes.get(id)}
const c={Map,Set,Date,JSON,Math,Number,String,Array,Object,Promise,CSS:{escape:x=>x},
 document:{getElementById:node,querySelector:node,querySelectorAll:()=>[],activeElement:null,addEventListener(){}},
 fetch(){effects.fetch++;throw Error('Rendering attempted network access')},
 setTimeout(){effects.timers++;throw Error('Rendering attempted timer')},clearTimeout(){},
 setInterval(){effects.timers++;throw Error('Rendering attempted timer')}};
vm.createContext(c);
const source=fs.readFileSync(sourcePath,'utf8'),end=source.lastIndexOf('\nrefresh(true);');
assert.ok(end>0);vm.runInContext(source.slice(0,end),c);
vm.runInContext("submit=()=>{throw Error('Rendering attempted job submission')}",c);
const run=script=>vm.runInContext(script,c),payload={name:'Observed candidate',summary:'Unproved interpretation',
 operational_definition:'Inspect the event',status:'candidate',agent_mode:'offline_template',
 evidence_ids:[],dataset_id:'dataset-route-fixture',source_refs:{dataset:{id:'dataset-route-fixture',version:2,hash:'b'.repeat(64)}},alternative_explanations:[],falsifiable_predictions:[],candidate_id:'ordinary-lead',
 fit_reason:'<script>unsafe-fit()</script> & <img onerror="unsafe()">',skeptic:{recommended_status:'needs_more_evidence'}};
const dataset={id:'dataset-route-fixture',kind:'dataset',version:2,hash:'b'.repeat(64),payload:{messages:[]}};
const states=[['shared_artifact_coordination','Candidate for an artifact study.',false],
 ['requires_new_environment','Another existing authoring family may fit',true],
 ['not_applicable','No study is proposed',true],
 ['<svg onload="unsafe()">','No artifact workflow recommendation is available.',true]];
c.dataset=dataset;
(async()=>{
 for(const [fit,copy,disabled] of states){
  c.record={id:'behavior-render-fixture',kind:'behavior',version:1,hash:'a'.repeat(64),
   payload:{...payload,experiment_fit:fit},summary:{name:'Observed candidate',status:'candidate'}};
  run("app.state={objects:[record],jobs:[],usage:{calls:400},max_calls:400};app.libraryKind='behavior';app.selected.behavior=record.id;app.cache.set(record.id,record);app.cache.set('dataset-route-fixture@2',dataset);app.live=false;app.view='library';");
  const before=JSON.stringify(c.record),stateBefore=run('JSON.stringify(app.state)'),html=await run('library()');
  assert.ok(html.includes('Artifact workflow screening'));assert.ok(html.includes(copy));
  assert.ok(html.includes('This recommendation concerns the initial artifact workflow'));
  assert.ok(html.includes('&lt;script&gt;unsafe-fit()&lt;/script&gt; &amp; &lt;img onerror=&quot;unsafe()&quot;&gt;'));
  assert.ok(!html.includes('<script>unsafe-fit()'));assert.ok(!html.includes('<img onerror='));assert.ok(!html.includes('<svg onload='));
  assert.ok(!html.includes('A new environment is required to test this mechanism.'));
  const button=html.match(/<button[^>]*data-design-behavior="behavior-render-fixture"[^>]*>/);
  assert.ok(button);assert.equal(/\bdisabled\b/.test(button[0]),disabled,'Artifact screening availability changed with exact source');
  assert.equal(JSON.stringify(c.record),before);assert.equal(run('JSON.stringify(app.state)'),stateBefore);
  assert.equal(run('app.live'),false);assert.equal(run('app.view'),'library');
 }
 c.record.payload.experiment_fit='shared_artifact_coordination';c.record.payload.status='rejected';
 const html=await run('library()');assert.ok(/data-design-behavior="behavior-render-fixture"[^>]*\bdisabled\b/.test(html));
 assert.deepEqual(effects,{fetch:0,jobs:0,timers:0});
 process.stdout.write(JSON.stringify({passed:true,states:4,rejectedArtifactDisabled:true}));
})().catch(error=>{console.error(error.stack);process.exitCode=1});
'''


class ArtifactRouteScopeTests(unittest.TestCase):
    @unittest.skipUnless(NODE, 'Node is required for actual library rendering')
    def test_actual_library_states_keep_artifact_gates_with_exact_source_and_escape_without_effects(self):
        source = ROOT / 'web' / 'app.js'
        result = subprocess.run([NODE, '-e', LIBRARY_VM, str(source)], cwd=ROOT,
            capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['passed'])

    def test_actual_discovery_packet_scopes_route_without_expanding_schema_or_provider_calls(self):
        candidate = {'id':'candidate-route-fixture','kind':'waiting_cluster','title':'Ordinary waiting',
            'description':'A source question, not an established failure.','evidence_ids':['m1'],
            'alternative_explanations':['Scheduled task dependency']}
        dataset = {'messages':[{'id':'m1','room_id':'room-fixture','content':'I will wait for the owner.',
            'timestamp':'2025-04-18T18:00:00Z'}], 'scope':{'bounded':True}}
        discovery = {'candidates':[candidate], 'controls':[], 'graph':{'edges':[]}}
        response = research.offline_proposal(candidate)
        packets = []

        class CapturingHarness:
            name = 'isolated_fake_provider'

            def run(self, system, packet, toolset, job_id, schema=None):
                packets.append({'task':copy.deepcopy(packet),'schema':copy.deepcopy(schema)})
                return copy.deepcopy(response['proposal'] if len(packets)==1 else response['skeptic'])

        before = copy.deepcopy((candidate,dataset,discovery))
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(root=Path(directory),max_calls=0)
            store = Store(Path(directory)/'isolated.sqlite3')
            agents = research.ResearchAgents(settings,store,CapturingHarness())
            result = agents.discover(candidate,dataset,discovery,'isolated-route-scope')
            self.assertEqual(len(packets),2)
            task = packets[0]['task']['task']
            self.assertIn('initial shared-artifact',task)
            self.assertIn('another existing authoring family',task.lower())
            self.assertIn('declined lead',task)
            self.assertIn('Do not infer global support or select a world',task)
            expected = ['shared_artifact_coordination','requires_new_environment','not_applicable']
            field = packets[0]['schema']['properties']['experiment_fit']
            self.assertEqual(field['enum'],expected)
            self.assertIn('not global compiler or mechanism fit',field['description'])
            self.assertEqual(packets[0]['task']['output_schema']['properties']['experiment_fit']['enum'],expected)
            self.assertEqual(result['proposal']['experiment_fit'],'requires_new_environment')
            self.assertEqual(store.usage()['calls'],0)
            self.assertEqual(store.list('environment_blueprint'),[])
            self.assertEqual(store.list('protocol'),[])
            self.assertEqual(store.list('network_protocol'),[])
            self.assertEqual(store.list('complementary_protocol'),[])
            self.assertEqual(store.list('resource_protocol'),[])
        self.assertEqual((candidate,dataset,discovery),before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
