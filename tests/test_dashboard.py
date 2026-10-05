"""Read-only dashboard contract checks against executed local subject policies.

Node VM checks rendered content and event wiring. These are not browser pixel,
accessibility-tree, hosted-model, or network transport tests.
"""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from swarm_lab.complementary_experiments import create_complementary_protocol, run_complementary_experiment
from swarm_lab.environment_authoring import schema_for_capabilities


ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
VM_CHECK = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const records=JSON.parse(fs.readFileSync(0,'utf8')),elements=new Map(),listeners={},writes=[],reads=[];
function element(id){if(!elements.has(id))elements.set(id,{innerHTML:'',textContent:'',open:false,className:'',classList:{toggle(){},remove(){},add(){}},addEventListener(){},showModal(){this.open=true},close(){this.open=false},contains(){return false},querySelector(){return null},focus(){}});return elements.get(id)}
const byId=Object.fromEntries(records.map(o=>[o.id,o]));
const ctx={console,records,Map,Set,Date,JSON,Math,Number,String,Array,Object,Promise,URLSearchParams,window:{scrollTo(){}},CSS:{escape:x=>x},setTimeout:()=>0,clearTimeout(){},setInterval:()=>0,MouseEvent:function(){},document:{getElementById:element,querySelector:element,querySelectorAll:()=>[],activeElement:null,addEventListener:(type,fn)=>{const previous=listeners[type];listeners[type]=previous?async event=>{await previous(event);await fn(event)}:fn}},fetch:async(path,settings)=>{assert(!settings?.method,'VM never submits a real request');reads.push(path);const u=new URL(path,'http://vm.invalid'),o=byId[decodeURIComponent(u.pathname.split('/').pop())];return{ok:Boolean(o),json:async()=>u.pathname==='/api/environment-authoring' ? o?.payload : o||{error:'Fixture absent'}}}};
vm.createContext(ctx);
let source=fs.readFileSync('web/app.js','utf8');const bootstrap=source.lastIndexOf('\nrefresh(true);');assert(bootstrap>0);vm.runInContext(source.slice(0,bootstrap),ctx);
const run=x=>vm.runInContext(x,ctx),passed=[];
function check(name,condition){assert(condition,name);passed.push(name)}
run("app.state={objects:records.map(o=>({id:o.id,kind:o.kind,version:o.version,created:o.created,summary:{name:o.kind,status:o.payload.status}})),jobs:[],usage:{calls:0},model:'test-model',harnesses:[],csrf:'vm-no-post'};submit=async(action,args)=>{globalThis.lastSubmission={action,args};return{}};app.selected.behavior='behavior-ui';app.selected.complementary_protocol='complementary_protocol-ui';app.selected.complementary_experiment='complementary_experiment-ui'");
function button(data){return{dataset:data,hasAttribute(){return false},closest(s){return s==='button,[data-node]'?this:null}}}
(async()=>{
check('Separate study tabs',run("studyTabs().includes('Noisy source diffusion')&&studyTabs().includes('Complementary evidence')"));
check('Default whole-network budget',run('complementaryPlanBudget().runs===8&&complementaryPlanBudget().decisions===96'));
check('Default exact-test warning',run("complementaryBudgetContent().includes('p=2/36')&&complementaryBudgetContent().includes('after Holm')"));
const html=await run('complementaryExperiments()');
check('Own experiment design form',html.includes('id="complementary-design-form"'));
check('Own numeric control fields',html.includes('data-field="complementaryTrials"')&&html.includes('data-field="complementarySeed"')&&html.includes('data-field="complementaryRounds"'));
check('Correct default seed',html.includes('value="4411"'));
check('Frozen exact-test resolution visible',html.includes('Registered conditional assignments'));
check('Exact modular-total outcome',html.includes('Mean exact modular-total accuracy difference'));
check('No noisy verdict label on new outcome',!html.includes('Mean verdict accuracy difference'));
check('Dispatches and deliveries distinct',html.includes('DISPATCHES / DELIVERIES'));
check('Coverage anchored at submission',html.includes('ORIGINALS AT SUBMISSION')&&html.includes('Later deliveries cannot change'));
check('Canonical inventory is not latent knowledge',html.includes('does not measure latent knowledge'));
check('Scripted result not LLM finding',html.includes('does not establish LLM coordination'));
check('Run, replay, claim controls',html.includes('data-action="experiment-complementary"')&&html.includes('complementary replay audit')&&html.includes('data-action="evaluate-claims"'));
check('Per-run trace control',html.includes('data-complementary-run="run-0001"'));
run('app.live=true');const mismatch=await run('complementaryExperiments()');check('Frozen backend mismatch blocks execution',/data-action="experiment-complementary"[^>]*disabled/.test(mismatch));
run('app.live=false');await listeners.submit({target:{id:'complementary-design-form'},preventDefault(){}});
check('Design request API',ctx.lastSubmission.action==='design_complementary');
check('Design request controlled factors',ctx.lastSubmission.args.behavior_id==='behavior-ui'&&ctx.lastSubmission.args.trials_per_cell===2&&ctx.lastSubmission.args.seed===4411&&ctx.lastSubmission.args.max_rounds===3&&JSON.stringify(ctx.lastSubmission.args.topologies)==='["ring","complete"]'&&JSON.stringify(ctx.lastSubmission.args.contexts)==='["placebo","source_thought"]'&&ctx.lastSubmission.args.live===false);
await listeners.click({target:button({action:'experiment-complementary',id:'complementary_protocol-ui'})});check('Execute request API',ctx.lastSubmission.action==='experiment_complementary'&&ctx.lastSubmission.args.protocol_id==='complementary_protocol-ui'&&ctx.lastSubmission.args.live===false);
run("app.live=true;app.harness='codex'");await listeners.click({target:button({action:'evaluate-claims',id:'complementary_experiment-ui'})});check('Claim audit uses chosen research harness',ctx.lastSubmission.action==='evaluate_claims'&&ctx.lastSubmission.args.live===true&&ctx.lastSubmission.args.harness==='codex');
run('app.live=false');await listeners.click({target:button({action:'replay-audit',id:'complementary_experiment-ui'})});check('Replay action remains offline',ctx.lastSubmission.action==='audit'&&ctx.lastSubmission.args.result_id==='complementary_experiment-ui'&&!('live'in ctx.lastSubmission.args));
for(const id of ['complementary_protocol-ui','complementary_experiment-ui','verification-ui','claim_audit-ui']){await run('openObject('+JSON.stringify(id)+')');check('Complementary navigation '+id,run("app.view==='experiments'&&app.experimentStudy==='complementary'&&app.selected.complementary_protocol==='complementary_protocol-ui'"));}
check('New kinds discoverable in jobs',run("uniqueIds(['complementary_protocol-ui','complementary_experiment-ui']).length===2"));
await run("showComplementaryRun('complementary_experiment-ui','run-0001')");const dialog=element('dialog-body').innerHTML;check('Trace distinguishes privileged oracle',dialog.includes('Researcher-only recorded oracle total')&&dialog.includes('subjects received no target'));check('Trace canonical-lineage scope',dialog.includes('free-text claims unverified')&&dialog.includes('First valid submissions'));
check('Escapes free-text content',dialog.includes('&lt;script&gt;UI_INJECTION&lt;/script&gt;')&&!dialog.includes('<script>UI_INJECTION</script>'));
await listeners.input({target:{dataset:{field:'complementaryTrials'},value:'4'}});check('Changed budget updates',run('complementaryPlanBudget().runs===16&&complementaryPlanBudget().decisions===192')&&element('complementary-plan-budget').innerHTML.includes('192'));
const prior=run('app.networkTopologies.slice()');await listeners.change({target:{dataset:{complementaryTopology:'complete'},checked:false}});check('Independent topology settings',run("app.complementaryTopologies.length===1&&app.complementaryTopologies[0]==='ring'")&&JSON.stringify(run('app.networkTopologies'))===JSON.stringify(prior));
ctx.lastSubmission=null;run('app.complementaryTopologies=[]');await listeners.submit({target:{id:'complementary-design-form'},preventDefault(){}});check('No-topology design declined',ctx.lastSubmission===null);
check('Measurement and graph discovery preserved',run("measurementPanel({},'dataset-ui').includes('Laya')&&graphDiscoveryPanel({},'discovery-ui').includes('Search graph anomalies')"));
check('Noisy source effect retains verdict semantics',run("networkEffectCard({factor:'context'}).includes('Mean verdict accuracy difference')"));
check('Authoring has own tab',run("studyTabs().includes('Environment authoring')"));
const authoring=await run('environmentAuthoring()');
check('Direct authoring catalog endpoint',reads.includes('/api/environment-authoring')&&authoring.includes('Factory capability and parameter declaration'));
check('Three executable templates visible',authoring.includes('shared artifact coordination')&&authoring.includes('provenance diffusion')&&authoring.includes('complementary information'));
check('Offline authoring button disabled',/type="submit"[^>]*disabled/.test(authoring));
check('Question and exact capabilities are free fields',authoring.includes('data-field="authoringQuestion"')&&authoring.includes('data-field="authoringCapabilities"')&&run("app.authoringCapabilities===''"));
check('Unknown requirements remain open',authoring.includes('explicit extension requests')&&authoring.includes('not a closed ontology'));
check('Separate builder and methodologist explained',authoring.includes('Offline compilation requires an explicit proposal'));
ctx.lastSubmission=null;await listeners.submit({target:{id:'environment-authoring-form'},preventDefault(){}});check('Offline proposal-free action blocked',ctx.lastSubmission===null);
run("app.live=true;app.harness='codex';app.authoringQuestion='  Distinguish resource gating from social coordination  ';app.authoringCapabilities='browser_tools, Private_NEW\\n browser_tools';app.authoringBehavior=''");
const liveAuthoring=await run('environmentAuthoring()');check('Live authoring role costs declared',liveAuthoring.includes('environment-builder call')&&liveAuthoring.includes('separate causal-methodologist call')&&liveAuthoring.includes('launches no subject experiment'));
await listeners.submit({target:{id:'environment-authoring-form'},preventDefault(){}});check('Authoring action and harness',ctx.lastSubmission.action==='construct_environment'&&ctx.lastSubmission.args.live===true&&ctx.lastSubmission.args.harness==='codex');
check('Exact capabilities retain unknowns and case',JSON.stringify(ctx.lastSubmission.args.required_capabilities)==='["browser_tools","Private_NEW"]');check('Question trim and optional no-source',ctx.lastSubmission.args.research_question==='Distinguish resource gating from social coordination'&&ctx.lastSubmission.args.behavior_id===null);
await listeners.change({target:{dataset:{field:'authoringBehavior'},value:'behavior-ui'}});await listeners.submit({target:{id:'environment-authoring-form'},preventDefault(){}});check('Optional observation request',ctx.lastSubmission.args.behavior_id==='behavior-ui');
ctx.lastSubmission=null;run("app.authoringQuestion='  '");await listeners.submit({target:{id:'environment-authoring-form'},preventDefault(){}});check('Empty question blocked',ctx.lastSubmission===null);
const blueprint=run("blueprintInspection(records.find(o=>o.id==='environment_blueprint-ui'))");check('Blueprint construction and fit scope separate',blueprint.includes('Experiment eligibility')&&blueprint.includes('Historical fidelity')&&blueprint.includes('Reviewer independence')&&blueprint.includes('Original observation claims · not semantically verified'));
check('Blueprint has no experiment launch',!blueprint.includes('data-action="experiment')&&blueprint.includes('compatible frozen experimental protocol'));
const approved=run("blueprintInspection({id:'approved-ui',payload:{construction_status:'compiled',experiment_eligibility:'approved_analogue'}})");
check('Approval alone cannot register without exact preview',approved.includes('Registration compatibility unavailable')&&!approved.includes('data-blueprint-register=')&&!approved.includes('data-action="experiment'));
check('Unapproved blueprint cannot register',!blueprint.includes('data-blueprint-register=')&&!blueprint.includes('data-action="register-blueprint"'));
ctx.lastSubmission=null;await listeners.click({target:button({action:'register-blueprint',id:'approved-ui'})});check('Legacy ID-only registration route is unavailable',ctx.lastSubmission===null);
check('Observation claims escaped',blueprint.includes('&lt;script&gt;BLUEPRINT_INJECTION&lt;/script&gt;')&&!blueprint.includes('<script>BLUEPRINT_INJECTION</script>'));
run('app.live=false');await run("openObject('environment_blueprint-ui')");check('Blueprint navigation',run("app.experimentStudy==='authoring'&&app.view==='experiments'"));await run("openObject('environment_construction_attempt-ui')");check('Attempt navigation and failure interpretation',run("app.experimentStudy==='authoring'")&&element('main').innerHTML.includes('Failed procedure phase: reviewer')&&element('main').innerHTML.includes('not a behavioral result'));
check('Blueprint and attempt job IDs discoverable',run("uniqueIds(['environment_blueprint-ui','environment_construction_attempt-ui']).length===2"));
console.log(JSON.stringify({passed:passed.length,checks:passed,provider_calls:0}));
})().catch(error=>{console.error(error.message);process.exitCode=1});
"""


@unittest.skipUnless(NODE, "Node.js is required for dashboard VM checks")
class DashboardContractTests(unittest.TestCase):
    def test_javascript_syntax(self):
        result = subprocess.run([NODE, "--check", "web/app.js"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_complementary_controls_results_audits_and_boundaries(self):
        protocol = create_complementary_protocol(seed=4411)
        report = run_complementary_experiment(protocol, resamples=100)
        report["agent_mode"] = "offline_simulation"
        report["protocol_id"] = "complementary_protocol-ui"
        # This marker exercises source-content escaping only in the UI fixture.
        report = copy.deepcopy(report)
        report["runs"][0]["turns"][0]["action"]["message"] = "<script>UI_INJECTION</script>"
        def record(identity, kind, payload):
            return {"id": identity, "kind": kind, "version": 1, "created": "2026-10-04T00:00:00Z", "payload": payload}
        records = [record("behavior-ui", "behavior", {"name": "Motivating candidate"}),
                   record("complementary_protocol-ui", "complementary_protocol", {"protocol": protocol}),
                   record("complementary_experiment-ui", "complementary_experiment", report),
                   record("verification-ui", "verification", {"experiment_id": "complementary_experiment-ui", "result_kind": "complementary_experiment", "passed": True, "runs_checked": 8, "model_calls": 0}),
                   record("claim_audit-ui", "claim_audit", {"experiment_id": "complementary_experiment-ui", "result_kind": "complementary_experiment", "audit": {"claims": []}}),
                   record("environment-authoring", "catalog_fixture", schema_for_capabilities()),
                   record("environment_blueprint-ui", "environment_blueprint", {"construction_status":"invalid_blueprint", "experiment_eligibility":"blocked", "spec":None, "missing_capabilities":["browser_tools"], "original_observation_claims":["<script>BLUEPRINT_INJECTION</script>"], "analogue_inventions":["Synthetic test domain"], "historical_fidelity":"unestablished", "reviewer_independence":"No separate model independence claimed", "errors":["An unpinned source ID was rejected"]}),
                   record("environment_construction_attempt-ui", "environment_construction_attempt", {"status":"failed", "failed_phase":"reviewer", "error":"Tool rounds exhausted before a final answer", "research_question":"Synthetic fixture question"})]
        result = subprocess.run([NODE, "-e", VM_CHECK], cwd=ROOT, input=json.dumps(records), capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        checked = json.loads(result.stdout)
        self.assertGreaterEqual(checked["passed"], 30)
        self.assertEqual(checked["provider_calls"], 0)


if __name__ == "__main__":
    unittest.main()
