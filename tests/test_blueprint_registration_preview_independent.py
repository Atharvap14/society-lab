"""Independent, inert UI checks; authored packets are not registry evidence."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
NODE = shutil.which('node')


def fixture(live=False):
    return {
        'preview_version': 'registration-compatibility-preview-v1',
        'blueprint_ref': {'id': 'environment_blueprint-authored', 'version': 3, 'hash': 'a'*64},
        'registration_plan': {'trials_per_cell': 2, 'seed': 4491, 'live': live},
        'status': 'compatible',
        'checks': {key: True for key in ('construction_compiled', 'fit_approved_analogue',
            'current_source_authorization', 'design_compatible', 'exact_world_preserved')},
        'reason': None,
        'design': {'object_kind': 'protocol', 'study_kind': 'shared_artifact_context',
            'research_question': 'Does the assigned private note change exact publication?',
            'experimental_unit': 'whole_swarm_run', 'primary_outcome': 'success',
            'primary_contrast': 'evidence_thought versus placebo',
            'conditions': ['baseline', 'placebo', 'evidence_thought'],
            'maximum_units': 6, 'maximum_subject_calls': 108,
            'maximum_hosted_subject_calls': 108 if live else 0,
            'subject_backend': {'harness': 'responses' if live else 'scripted',
                'model': 'declared-subject' if live else 'deterministic_offline_policy'},
            'world_spec_hash': 'b'*64},
        'registered': False, 'model_calls': 0, 'database_writes': 0,
        'raw_source_reread': False,
        'limits': ['Current local registry/implementation checks; no fresh-source attestation.',
            'Fixed study question is separate from the mechanism hypothesis.'],
    }


SCRIPT = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const [filename,scenario]=process.argv.slice(1),packet=JSON.parse(fs.readFileSync(0,'utf8'));
const context=vm.createContext({JSON,Math,Number,String,Array,Object,Set,Map,
 fetch(){throw Error('Unexpected network request')},setTimeout(){throw Error('Unexpected timer')}});
vm.runInContext(fs.readFileSync(filename,'utf8'),context,{filename});
const view=context.BlueprintRegistrationPreview,copy=x=>JSON.parse(JSON.stringify(x));
const expected={blueprint_ref:copy(packet.blueprint_ref),registration_plan:copy(packet.registration_plan)};
function withheld(p,e=expected){assert.throws(()=>view.launchArgs(p,e));assert.ok(!view.render(p,e).includes('data-blueprint-register='));}
if(scenario==='exact_identity'){
 const before=JSON.stringify(packet),expectedBefore=JSON.stringify(expected),args=view.launchArgs(packet,expected),html=view.render(packet,expected);
 assert.equal(args.blueprint_id,packet.blueprint_ref.id);assert.equal(args.blueprint_version,3);assert.equal(args.blueprint_hash,'a'.repeat(64));assert.equal(args.trials_per_cell,2);assert.equal(args.seed,4491);assert.equal(args.live,false);
 const displayed=html.replace(/<[^>]*>/g,'');assert.ok(displayed.includes(packet.blueprint_ref.id));assert.ok(displayed.includes('version 3'));assert.ok(displayed.includes('a'.repeat(64)),'Exact hash must be visible, not only hidden in launch attributes');
 assert.equal(JSON.stringify(packet),before);assert.equal(JSON.stringify(expected),expectedBefore);assert.ok(!html.includes('<form'));assert.ok(!html.includes('<script'));
}else if(scenario==='stale_identity'){
 for(const update of [p=>p.blueprint_ref.id+='-other',p=>p.blueprint_ref.version++,p=>p.blueprint_ref.hash='c'.repeat(64),p=>p.blueprint_ref.version=true,p=>p.blueprint_ref.hash=p.blueprint_ref.hash.toUpperCase(),p=>p.blueprint_ref.extra='ignored']){const p=copy(packet);update(p);withheld(p);}
 assert.throws(()=>view.expectation({kind:'behavior',...packet.blueprint_ref},false));assert.throws(()=>view.expectation({kind:'environment_blueprint',...packet.blueprint_ref},'false'));
}else if(scenario==='plan_binding'){
 for(const update of [p=>p.registration_plan.seed=4492,p=>p.registration_plan.trials_per_cell=3,p=>p.registration_plan.live=true,p=>p.registration_plan.live='false',p=>p.registration_plan.seed=true,p=>p.registration_plan.trials_per_cell=true,p=>p.registration_plan.future_setting=1]){const p=copy(packet);update(p);withheld(p);}
 const wrong=copy(expected);wrong.registration_plan.seed=4492;withheld(packet,wrong);
}else if(scenario==='blocked_no_launch'){
 packet.status='blocked';packet.design=null;packet.checks.design_compatible=false;packet.checks.exact_world_preserved=null;
 packet.reason={stage:'design',code:'custom_topology_not_registered',message:'Requires <script>other-world</script> & explicit extension.'};
 const html=view.render(packet,expected);assert.equal(view.validate(packet,expected).status,'blocked');assert.ok(html.includes('&lt;script&gt;other-world&lt;/script&gt; &amp;'));assert.ok(!html.includes('<script>'));assert.ok(html.includes('Not checked'));withheld(packet);
 const malformed=copy(packet);malformed.checks.design_compatible=true;withheld(malformed);
}else if(scenario==='zero_calls_and_unknown_gates'){
 for(const update of [p=>p.model_calls=1,p=>p.model_calls=false,p=>p.database_writes=1,p=>p.registered=true,p=>p.raw_source_reread=true,p=>p.checks.current_source_authorization=null,p=>p.checks.design_compatible='true',p=>p.preview_version='unrecognized']){const p=copy(packet);update(p);withheld(p);}
}else if(scenario==='allocation_counts'){
 for(const update of [p=>p.design.maximum_units=999,p=>p.design.maximum_units=true,p=>p.design.conditions[1]=p.design.conditions[0],p=>p.design.maximum_subject_calls=false,p=>p.design.maximum_hosted_subject_calls=1,p=>p.design.maximum_hosted_subject_calls=false,p=>p.design.subject_backend.harness='responses']){const p=copy(packet);update(p);withheld(p);}
 const html=view.render(packet,expected);assert.ok(html.includes('<dt>Study units</dt><dd>6</dd>'));assert.ok(html.includes('<dt>Maximum hosted subject calls</dt><dd>0</dd>'));assert.ok(html.includes('108'));assert.ok(html.includes('Registration launches no subjects'));
}else if(scenario==='live_explicit'){
 const expectedLive={blueprint_ref:copy(packet.blueprint_ref),registration_plan:copy(packet.registration_plan)};
 assert.equal(view.launchArgs(packet,expectedLive).live,true);const html=view.render(packet,expectedLive);assert.ok(html.includes('<dd>108</dd>'));assert.ok(html.includes('responses'));
 const bad=copy(packet);bad.design.subject_backend.harness='scripted';withheld(bad,expectedLive);
 const impossible=copy(packet);impossible.design.maximum_hosted_subject_calls=0;withheld(impossible,expectedLive);
}else if(scenario==='fixed_outcome_scope'){
 const p=copy(packet);p.design.research_question='Does the local question establish shared beliefs?';
 const html=view.render(p,expected);assert.ok(html.includes('<dt>Primary outcome</dt><dd>success</dd>'));assert.ok(html.includes('<dt>Randomization unit</dt><dd>whole_swarm_run</dd>'));assert.ok(html.includes('may be narrower'));
 for(const update of [p=>p.design.primary_outcome=null,p=>p.design.experimental_unit=null,p=>p.design.study_kind=null,p=>p.design.object_kind='unregistered_world']){const p=copy(packet);update(p);withheld(p);}
 const resource=copy(packet);resource.design.object_kind='resource_protocol';resource.design.study_kind='exclusive_resource_reminder';resource.design.experimental_unit='whole_swarm_run';resource.design.primary_outcome='task_completion_fraction';resource.design.conditions=['neutral','task_reminder'];resource.design.maximum_units=4;
 assert.equal(view.validate(resource,expected).status,'compatible');assert.ok(view.render(resource,expected).includes('task_completion_fraction'));
}else if(scenario==='escaping_and_bounds'){
 const p=copy(packet);p.design.research_question='😀 <img src=x onerror=alert(1)> & why?';p.design.primary_contrast='<svg onload=alert(1)>';p.limits=['<script>scope</script>'];p.design.subject_backend.model='model <script>unsafe</script>';
 const html=view.render(p,expected);assert.ok(html.includes('😀 &lt;img'));assert.ok(html.includes('&lt;svg'));assert.ok(html.includes('&lt;script&gt;scope'));assert.ok(!html.includes('<img'));assert.ok(!html.includes('<svg'));assert.ok(!html.includes('<script>'));
 for(const update of [p=>p.limits=Array(17).fill('limit'),p=>p.design.conditions=Array(17).fill('condition'),p=>p.design.research_question='x'.repeat(4001),p=>p.design.world_spec_hash='wrong']){const p=copy(packet);update(p);withheld(p);}
}else if(scenario==='pending_and_unknown'){
 const before=JSON.stringify(packet);
 for(const attempt of [{phase:'pending'},{phase:'queued',job_id:'job-authored-queue'},
   {phase:'acknowledgement_unknown'},{phase:'queued',job_id:'<script>fake-job</script>'}]){
  const html=view.render(packet,expected,{registrationAttempt:attempt});assert.ok(!html.includes('data-blueprint-register='));assert.ok(html.includes('disabled'));
  if(attempt.phase==='pending')assert.ok(html.includes('Waiting for the queue acknowledgment'));
  else if(attempt.job_id==='job-authored-queue')assert.ok(html.includes('data-trace="job-authored-queue"'));
  else {assert.ok(html.includes('Queue acknowledgment is unknown'));assert.ok(!html.includes('data-trace='));}
  assert.ok(!html.includes('<script>'));
 }
 assert.equal(JSON.stringify(packet),before);
}else throw Error('Unknown scenario');
process.stdout.write(JSON.stringify({passed:true,scenario}));
"""


@unittest.skipUnless(NODE, 'Node.js required for independent inert registration preview checks')
class IndependentRegistrationPreviewTests(unittest.TestCase):
    def check(self, scenario, live=False):
        result = subprocess.run([NODE, '-e', SCRIPT, str(ROOT/'web'/'blueprint-registration-preview.js'), scenario],
            input=json.dumps(fixture(live)), capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIs(json.loads(result.stdout)['passed'], True)

    def test_exact_visible_identity_bound_args_and_inert_immutable_render(self): self.check('exact_identity')
    def test_stale_and_malformed_exact_pins_withhold_launch(self): self.check('stale_identity')
    def test_settings_match_two_trials_seed4491_and_explicit_boolean_mode(self): self.check('plan_binding')
    def test_blocked_preview_retains_unknown_checks_and_no_launch(self): self.check('blocked_no_launch')
    def test_claimed_writes_calls_registration_or_unknown_gates_withhold(self): self.check('zero_calls_and_unknown_gates')
    def test_allocation_count_and_offline_hosted_calls_are_truthful(self): self.check('allocation_counts')
    def test_live_declared_backend_requires_positive_hosted_cap(self): self.check('live_explicit', True)
    def test_fixed_outcome_and_whole_team_unit_do_not_become_proposed_belief_metric(self): self.check('fixed_outcome_scope')
    def test_escaping_bounded_shapes_and_no_external_content(self): self.check('escaping_and_bounds')
    def test_pending_queued_and_unknown_ack_withhold_registration_without_retry(self): self.check('pending_and_unknown')

    def test_actual_backend_compatible_and_blocked_fixture_shapes(self):
        script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const [source,compatiblePath,blockedPath]=process.argv.slice(1),c=vm.createContext({JSON,Math,Number,String,Array,Object,Set,Map,
fetch(){throw Error('Unexpected network access')}});vm.runInContext(fs.readFileSync(source,'utf8'),c);
for(const [path,status]of [[compatiblePath,'compatible'],[blockedPath,'blocked']]){
 const wrapper=JSON.parse(fs.readFileSync(path,'utf8')),p=wrapper.packet,e={blueprint_ref:wrapper.expected_ref,registration_plan:wrapper.expected_plan};
 const before=JSON.stringify(wrapper),html=c.BlueprintRegistrationPreview.render(p,e);assert.equal(c.BlueprintRegistrationPreview.validate(p,e).status,status);
 if(status==='compatible'){
  const args=c.BlueprintRegistrationPreview.launchArgs(p,e);assert.equal(args.blueprint_hash,e.blueprint_ref.hash);assert.equal(args.blueprint_version,e.blueprint_ref.version);assert.equal(args.live,false);assert.equal(args.seed,4491);assert.equal(args.trials_per_cell,2);
  assert.equal(p.design.maximum_units,4);assert.equal(p.design.maximum_subject_calls,48);assert.equal(p.design.maximum_hosted_subject_calls,0);assert.ok(html.includes('mean_accuracy'));assert.ok(html.includes('whole_network_run'));assert.ok(html.includes('<dd>48</dd>'));assert.ok(html.includes('<dd>0</dd>'));
 }else{assert.throws(()=>c.BlueprintRegistrationPreview.launchArgs(p,e));assert.ok(!html.includes('data-blueprint-register='));}
 assert.equal(JSON.stringify(wrapper),before);
}process.stdout.write(JSON.stringify({passed:true}));
"""
        result = subprocess.run([NODE, '-e', script, str(ROOT/'web'/'blueprint-registration-preview.js'),
            str(HERE/'fixtures'/'registration-preview-compatible.json'), str(HERE/'fixtures'/'registration-preview-blocked.json')],
            capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIs(json.loads(result.stdout)['passed'], True)


if __name__=='__main__': unittest.main(verbosity=2)
