"""Save a bounded exploratory authoring cycle from the actual reviewed candidate."""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from swarm_lab.pipeline import Lab


def main():
    lab = Lab()
    behavior = lab.store.get('behavior-4d47c2a27a29')
    sources = {}
    for kind, ref in behavior['payload']['source_refs'].items():
        obj = lab.store.get(ref['id'], ref['version'])
        if obj['hash'] != ref['hash'] or lab.store.get(obj['id'])['hash'] != obj['hash']:
            raise ValueError('Selected current source changed')
        sources[kind] = {key: obj[key] for key in ('kind', 'id', 'version', 'hash')}
    plan = {'behavior_ref': {key: behavior[key] for key in ('kind', 'id', 'version', 'hash')},
        'source_refs': sources,
        'research_question': (
            'Explore a deliberately narrow analogue motivated by the reviewed shared-artifact handoff '
            'candidate: does a private context reminder change independent task completion or artifact '
            'verification under a bounded coordination opportunity? Select the smallest supported world '
            'whose existing predefined contrast actually addresses that narrower question. Historical '
            'browser work, waiting duration, persistent memory, incoming mention concentration and '
            'network mediation are outside this cycle. Keep source facts separate from synthetic '
            'inventions; do not assert global historical computer exclusivity. The reviewer must decline '
            'approval if the authored world cannot preserve its proposed mechanism. This is exploratory '
            'capability/measurement testing with scripted subjects, not a claim about LLM behavior.'),
        'required_capabilities': ['resettable_state', 'role_scoped_observations',
                                  'private_context_insertion', 'independent_code_oracle'],
        'trials_per_cell': 2, 'seed': 7503, 'audit_seed': 0,
        'research_live': True, 'subjects_live': False, 'research_harness': 'responses',
        'max_new_model_calls': 3, 'job_id': 'handoff-research-cycle-20261004-0326'}
    destination = lab.settings.runtime / 'plans' / 'handoff-research-cycle-20261004-0326.json'
    destination.parent.mkdir(exist_ok=True, parents=True)
    with destination.open('x', encoding='utf-8') as handle:
        json.dump(plan, handle, ensure_ascii=False, indent=2)
    print(json.dumps({'plan_path': str(destination), 'model_calls_authorized': 3,
                     'global_call_cap': lab.settings.max_calls, 'current_calls': lab.store.usage()['calls']}))


if __name__ == '__main__': main()
