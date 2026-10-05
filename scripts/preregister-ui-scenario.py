"""Ask a real LLM to predict a user journey before any of its actions run."""
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swarm_lab.config import Settings
from swarm_lab.harness import ResponsesHarness
from swarm_lab.store import Store, fingerprint


def main():
    path = ROOT / '.runtime' / 'user-scenario-preregistration-20261005.json'
    if path.exists():
        raise SystemExit('This preregistration is already frozen; use another identity for another scenario.')
    steps = [
        ('mention_read', 'In Coordination research / First conversation, use @ to read the saved File-check reminder replication draft v2. Ask for a Markdown summary without changing or running anything.'),
        ('save_plan', 'Ask the guide to create a new experiment plan from the editable copy: two teams per condition, six rounds, valid probability 0.35, assignment seed 61006. Do not build or run yet.'),
        ('build_world', 'Ask the guide to build and review a real shared-file simulator from the new exact plan, without running subjects.'),
        ('run_and_switch', 'Ask the guide to run the new experiment with real LLM subjects. Switch to another chat while it works, and keep a separate unsent question there.'),
        ('return_and_results', 'Return to First conversation. Ask for the new result in simple Markdown with charts. Check stored effects and uncertainty; do not assume the reminder helped.'),
        ('old_replay', 'Ask to replay the earlier experiment-b62705a33765 v1 from another project using @. Scrub backwards and forwards and return. The new plan and old immutable outcome should remain available.'),
        ('reuse_and_branch', 'Ask to reuse an exact older plan, then fork this chat to explore another idea. Keep original objects unchanged; branch history and future state must be independent.'),
        ('reload_and_resume', 'Reload the branch, switch back to First conversation and inspect its own saved state. Exact citations, the new experiment, original draft and guide operation receipts should remain accessible.'),
    ]
    schema = {'type': 'object', 'additionalProperties': False, 'required': ['goal', 'steps', 'limitations'], 'properties': {
        'goal': {'type': 'string'}, 'limitations': {'type': 'array', 'items': {'type': 'string'}},
        'steps': {'type': 'array', 'minItems': len(steps), 'maxItems': len(steps), 'items': {
            'type': 'object', 'additionalProperties': False, 'required': ['id', 'belief', 'probability', 'checks', 'failure_signals'], 'properties': {
                'id': {'type': 'string', 'enum': [row[0] for row in steps]}, 'belief': {'type': 'string'},
                'probability': {'type': 'number', 'minimum': 0, 'maximum': 1},
                'checks': {'type': 'array', 'items': {'type': 'string'}},
                'failure_signals': {'type': 'array', 'items': {'type': 'string'}}}}}}}
    store = Store(ROOT / '.runtime' / 'lab.sqlite3')
    harness = ResponsesHarness(Settings(root=ROOT, max_calls=2000, max_output_tokens=6500), store)
    payload = {'model': harness.settings.model, 'instructions': 'You are a product test agent. Pre-register your beliefs BEFORE this user journey runs. For each supplied action, predict observable functional outcomes, assign a subjective probability, and list independent checks and failure signals. Do not claim observed success, hidden reasoning, or any scientific treatment effect. Keep the exact step order and IDs. Distinguish UI testing from validation of a scientific theory.',
               'input': json.dumps({'known_state': 'A local Society Lab has persistent projects/chats, exact saved scientific artifacts and an editable replication draft. New guide operation tools and Markdown rendering have been implemented but this new journey has not run.', 'steps': [{'id': key, 'action': action} for key, action in steps]}),
               'store': False, 'max_output_tokens': 6500, 'text': {'format': {'type': 'json_schema', 'name': 'user_flow_preregistration', 'strict': True, 'schema': schema}}}
    reply = harness.request(payload, 'user-scenario-preregistration-20261005')
    predictions = json.loads(harness.text(reply))
    if [row['id'] for row in predictions['steps']] != [row[0] for row in steps]:
        raise ValueError('The agent reordered the frozen scenario.')
    packet = {'schema_version': 'user-scenario-preregistration-v1', 'registered_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'model': payload['model'], 'provider_response_id': reply.get('id'), 'actions': [{'id': key, 'action': action} for key, action in steps], 'predictions': predictions, 'scope': 'Functional product behavior; subjective agent predictions are not observed results.'}
    packet['registration_hash'] = fingerprint(packet)
    path.write_text(json.dumps(packet, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'saved': str(path), 'registration_hash': packet['registration_hash'], 'steps': len(steps)}))


if __name__ == '__main__':
    main()
