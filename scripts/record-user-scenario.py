"""Retain actual UI observations and independently check saved product state.

The browser steps are performed through computer use. This recorder does not
simulate them or turn its fixed observations into provider evidence.
"""
import json
from pathlib import Path
from urllib.request import urlopen
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]

def get(path):
    with urlopen('http://127.0.0.1:8765' + path, timeout=20) as response:
        return json.load(response)

def main():
    registration = json.loads((ROOT/'.runtime/user-scenario-preregistration-20261005.json').read_text())
    chat = get('/api/workspaces/chat?chat_id=chat-331466208ddb451eb228')
    other = get('/api/workspaces/chat?chat_id=chat-existing-research')
    branch = get('/api/workspaces/chat?chat_id=chat-eb8310422c534fbd83d7')
    pins = {
        'old_plan': ('guided_plan-296d42074791','93c2dd5ff602dce2c0be647f0c7303bcf1132ed07e7ae3ee30322721526a18f3'),
        'old_experiment': ('experiment-b62705a33765','360fc4c73fe7a339fade94973ec461618d95c62cbe399e3288f97d9ddce743f6'),
        'new_experiment': ('experiment-e022fb752a02','81a361fbc742a87ae28930009db1127bd2b24d8df192269400d4b319f76ffb48'),
    }
    checks = {key+'_unchanged': get('/api/object/'+value[0]+'?version=1')['hash']==value[1] for key,value in pins.items()}
    artifacts = chat['artifacts']; branch_artifacts = branch['artifacts']
    checks['old_plan_reused_exactly'] = any(a['ref']['id']==pins['old_plan'][0] and a['ref']['hash']==pins['old_plan'][1] for a in artifacts)
    checks['branch_keeps_new_result'] = any(a['ref']['id']==pins['new_experiment'][0] and a['ref']['hash']==pins['new_experiment'][1] for a in branch_artifacts)
    checks['other_chat_unsent_idea'] = other['state']['ui']['workspace']['compose']=='An independent, unsent question: could a bridge agent delay a correction? Keep this thought in Research workspace.'
    tools = [t for m in chat['messages'] for t in m.get('metadata',{}).get('guide_result',{}).get('tool_results',[])]
    for name in ['save_plan','build_simulator','run_experiment','reuse_artifact','fork_chat']:
        checks[name+'_completed_receipt'] = any(t.get('tool')==name and t.get('status')=='completed' for t in tools)
    observations = [
        ('mention_read','passed','Actual @ selection and Markdown heading/list; no scientific change.'),
        ('save_plan','passed_after_repair','First source_ref validation failed safely. Bounded correction and exact source binding repaired; new seed61006 plan saved.'),
        ('build_world','passed_after_repair','First natural command only opened plan. Imperative parsing repaired; actual builder/reviewer produced checked world. Read-only world receipt routing repaired separately.'),
        ('run_and_switch','passed_after_repair','First guide incorrectly required an execution result as an input. Prompt repaired; explicit run created51 subject decisions. Changed to another project while execution continued.'),
        ('return_and_results','passed','Returned to original chat; result receipt and embedded report preserved. Findings showed2/2,1/2,2/2 and interval crossing zero. Guide opened requested view but did not fully summarize counts in its first prose response.'),
        ('old_replay','passed_after_repair','Artifact ID was initially not searchable; search extended. Actual older saved experiment replay scrubbed End then Home; messages/tools separate and current plan preserved.'),
        ('reuse_and_branch','passed_after_repair','First guide claimed reuse with navigation only and no receipt. Explicit retry produced actual reuse and fork receipts. Added bounded corrective tool round and refusal to show unsupported mutation claims.'),
        ('reload_and_resume','passed_after_settling','First immediate reload after fork returned origin view. Explicitly selected and confirmed settled branch, then reload retained branch. Original chat/result/copy/citations accessible; separate unsent draft checked by DOM value and server state.'),
    ]
    packet={'schema_version':'observed-user-scenario-v1','observed_at':datetime.now(timezone.utc).isoformat(),
        'registration_hash':registration['registration_hash'],'preregistered_model':registration['model'],
        'scope':'One actual computer-use journey with real guide/subject calls. Final success after repairs is not first-pass success or empirical classifier accuracy.',
        'observations':[{'id':i,'outcome':o,'evidence':e} for i,o,e in observations],
        'saved_state_checks':checks,'saved_state_checks_passed':all(checks.values()),
        'original_chat_id':chat['id'],'branch_chat_id':branch['id'],
        'limitations':['Subjective preregistered probabilities are predictions, not observed probabilities.',
            'This is one observed route; authored transition fixtures cover other routes separately.',
            'The source records stay on the laptop; public write-ups include pins and summaries, not raw corpus.']}
    path=ROOT/'.runtime/user-scenario-results-20261005.json';path.write_text(json.dumps(packet,indent=2),encoding='utf-8')
    (ROOT/'docs/user-flow-preregistration.json').write_text(json.dumps(registration,indent=2),encoding='utf-8')
    (ROOT/'docs/user-flow-observations.json').write_text(json.dumps(packet,indent=2),encoding='utf-8')
    print(json.dumps({'saved_state_checks':checks,'passed':all(checks.values())}))

if __name__=='__main__':main()
