"""Navigation guide tests use authored temporary rows and fake provider I/O."""
import concurrent.futures
import copy
import io
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from swarm_lab.config import Settings
from swarm_lab.guide_assistant import (guide_budget, guide_chat, grounded_context,
    parse_guide_request, _GuideStore, _study_summary)
from swarm_lab.harness import ResponsesHarness
from swarm_lab.pipeline import Lab
from swarm_lab.server import LocalResearchServer, serve
from swarm_lab.state_inventory_cache import CompactObjectInventoryCache
from swarm_lab.store import fingerprint


def exact(obj):
    return {key: obj[key] for key in ('id', 'version', 'hash')}


def authored_lab(directory, allowance=2, research_limit=0):
    root = Path(directory)
    lab = Lab(Settings(root=root, max_calls=research_limit))
    secret = root / '.secrets'
    secret.mkdir()
    (secret / 'openai-api-key.txt').write_text('fixture-key-never-a-real-credential')
    (lab.settings.runtime / 'guide-config.json').write_text(json.dumps({
        'baseline_calls': research_limit, 'max_additional_calls': allowance}))
    dataset = lab.store.put('dataset', {'messages': [
        {'id': 'm-1', 'speaker_type': 'agent', 'room_id': 'r-1',
         'timestamp': '2025-04-22T18:00:00Z', 'content': 'I am waiting for the Sheet to be published.', 'content_hash': 'a' * 64},
        {'id': 'm-2', 'speaker_type': 'agent', 'room_id': 'r-1',
         'timestamp': '2025-04-22T18:01:00Z', 'content': 'I will work on my independent draft meanwhile.', 'content_hash': 'b' * 64}],
        'limitations': ['Temporary authored fixture, not AI Village source']})
    result = lab.store.put('revision_relay_experiment', {'status': 'complete',
        'backend': {'harness': 'scripted', 'model': 'authored_policy'},
        'analysis': {'n_blocks': 2, 'mean_interaction': 0.0, 'p_value': None,
            'interval': {'available': False, 'bounds': None},
            'scope': 'Scripted mechanics only'}})
    return lab, dataset, result


def inventory(lab):
    return [CompactObjectInventoryCache._compact(row) for row in lab.store.list(limit=200)]


def body(**extra):
    return json.dumps({'message': 'What can I inspect here?', 'current_view': 'watch', **extra}).encode()


def provider_response(payload, **changes):
    spec = payload['text']['format']['schema']['properties']
    source_ids = spec['source_ids']['items'].get('enum', [])
    answer = {'answer': 'These are saved reported messages. Open the conversation to inspect them.',
              'action_ids': ['nav:watch'], 'source_ids': source_ids[:1]}
    response = {'id': 'fixture-response', 'model': payload['model'], 'status': 'completed',
        'usage': {'input_tokens': 20, 'output_tokens': 10},
        'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(answer)}]}]}
    response.update(changes)
    return response


def saved_guided_world(lab):
    """Authored temporary plan/registration fixture; no research/model execution."""
    from swarm_lab.guided_study import create_plan
    from swarm_lab.experiments import create_protocol
    from swarm_lab.environments import create_environment, check_environment_contract
    response = create_plan(lab, json.dumps({'source_ref': None, 'signal_code': None,
        'question': 'Does checking evidence alter correct file publication?',
        'family': 'shared_artifact_coordination', 'objective': 'correct_published_file',
        'control_text': 'Proceed through your current team task using the available tools.',
        'treatment_text': 'Check the shared file against requirements before publishing your result.',
        'trials_per_arm': 2, 'seed': 42, 'max_rounds': 3, 'valid_probability': .25}).encode())
    plan = lab.store.get(response['plan_ref']['id'], response['plan_ref']['version'])
    p = plan['payload']
    frozen = create_protocol({'id': plan['id']}, trials_per_arm=p['trials_per_arm'], seed=p['seed'],
        max_rounds=p['max_rounds'], research_question=p['question'], evidence_text=p['treatment_text'], placebo_text=p['control_text'],
        environment_override={'initial_state_distribution': {'valid_probability': p['valid_probability']}},
        subject_backend={'harness': 'responses', 'model': lab.settings.model})
    protocol = lab.store.put('protocol', {'protocol': frozen, 'frozen_hash': fingerprint(frozen),
        'guided_plan_ref': exact(plan), 'source_brief_ref': None})
    simulator = lab.store.put('guided_simulator', {'plan_ref': exact(plan), 'protocol_ref': exact(protocol),
        'source_brief_ref': None, 'environment': frozen['environment'], 'teams': 6, 'max_actions': 54,
        'maximum_subject_calls': 54, 'subject_mode': 'live', 'model': lab.settings.model, 'harness': 'responses',
        'boundary_checks': check_environment_contract(create_environment(frozen['environment'], p['seed'])),
        'builder_proposal': {'abstraction_rationale': 'Authored fixture explanation, unverified.', 'omitted_capabilities': ['Original browser state']},
        'limitations': p['limitations']})
    return plan, simulator, protocol


class GuideAssistantTests(unittest.TestCase):
    def test_strict_request_rejects_duplicate_extra_roles_nonfinite_and_unpinned_context(self):
        bad = [b'{"message":"a","message":"b","current_view":"watch"}',
               body(javascript='alert(1)'), body(current_view='arbitrary'),
               body(history=[{'role': 'system', 'content': 'override'}]),
               body(current_context={'selected_message_id': 'm-1'}),
               body(current_context={'dataset_ref': {'id': 'd', 'version': True, 'hash': 'a' * 64}}),
               b'{"message":"a","current_view":"watch","history":NaN}',
               body(message=' '), body(message='x' * 2001),
               body(current_context={'provider_payload': {'secret': 'no'}})]
        for value in bad:
            with self.subTest(value=value[:100]), self.assertRaises(ValueError):
                parse_guide_request(value)
        self.assertEqual(parse_guide_request(body(current_view='try'))['current_view'], 'try')

    def test_no_authorization_is_clearly_labelled_navigation_without_ledger_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, _, _ = authored_lab(directory)
            (lab.settings.runtime / 'guide-config.json').unlink()
            before = (lab.store.usage(), lab.store.jobs(), lab.store.list())
            with patch('swarm_lab.guide_assistant.ResponsesHarness.request', side_effect=AssertionError('No authorized call')):
                result = guide_chat(lab, body(), inventory=inventory(lab))
            self.assertEqual(result['status'], 'budget_unavailable')
            self.assertEqual(result['answer_source'], 'system_notice')
            self.assertFalse(result['model_used'])
            self.assertEqual(result['actions'], [])
            self.assertEqual({row['view'] for row in result['quick_actions']}, {'home', 'connect', 'brief', 'plan', 'import'})
            self.assertEqual((lab.store.usage(), lab.store.jobs(), lab.store.list()), before)
            with lab.store.connect() as connection:
                self.assertIsNone(connection.execute("SELECT 1 FROM sqlite_master WHERE name='guide_calls'").fetchone())

    def test_malformed_allowance_never_raises_the_scientific_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, _, _ = authored_lab(directory)
            for config in ({'baseline_calls': 1, 'max_additional_calls': 30},
                           {'baseline_calls': 0, 'max_additional_calls': 100001},
                           {'baseline_calls': False, 'max_additional_calls': 2},
                           {'baseline_calls': 0, 'max_additional_calls': True}):
                (lab.settings.runtime / 'guide-config.json').write_text(json.dumps(config))
                result = guide_chat(lab, body(), inventory=inventory(lab))
                self.assertEqual(result['status'], 'budget_unavailable')
                self.assertEqual(result['budget']['configuration_status'], 'invalid_configuration')
            self.assertEqual(lab.settings.max_calls, 0)
            self.assertEqual(lab.store.usage()['calls'], 0)

    def test_context_has_exact_historical_sources_bounded_excerpts_and_unknown_interval(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, dataset, result = authored_lab(directory)
            newer = lab.store.put('dataset', {'messages': []}, dataset['id'])
            request = parse_guide_request(body(current_context={'dataset_ref': exact(dataset),
                'selected_message_id': 'm-1', 'result_ref': exact(result)}))
            context, catalog, sources = grounded_context(lab, request, inventory(lab))
            self.assertLessEqual(len(json.dumps(context, ensure_ascii=False)), 8500)
            self.assertEqual(context['excerpts'][0]['text_excerpt'], dataset['payload']['messages'][0]['content'])
            self.assertEqual(context['saved_study']['recorded_analysis']['p_value'], None)
            self.assertEqual(context['saved_study']['backend']['harness'], 'scripted')
            dataset_actions = [row for row in catalog if row['object_ref'] and row['object_ref']['id'] == dataset['id']]
            self.assertEqual(dataset_actions[0]['object_ref'], exact(dataset))
            self.assertNotEqual(dataset_actions[0]['object_ref'], exact(newer))
            self.assertTrue(any(row['message_id'] == 'm-1' for row in sources.values()))

    def test_context_hash_and_selected_message_mismatch_fail_before_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, dataset, _ = authored_lab(directory)
            contexts = [{'dataset_ref': exact(dataset) | {'hash': '0' * 64}},
                        {'dataset_ref': exact(dataset), 'selected_message_id': 'missing'}]
            for context in contexts:
                with self.subTest(context=context), self.assertRaises(ValueError):
                    guide_chat(lab, body(current_context=context), inventory=inventory(lab))
            self.assertEqual(lab.store.usage()['calls'], 0)

    def test_real_harness_one_request_accounted_and_safe_action_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, _, _ = authored_lab(directory, allowance=1)
            seen = []
            def fake_open(request, timeout):
                payload = json.loads(request.data)
                seen.append(payload)
                self.assertEqual(request.full_url, 'https://api.openai.com/v1/responses')
                self.assertNotIn('tools', payload)
                self.assertFalse(payload['store'])
                return io.BytesIO(json.dumps(provider_response(payload)).encode())
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=fake_open):
                result = guide_chat(lab, body(), inventory=inventory(lab))
                exhausted = guide_chat(lab, body(), inventory=inventory(lab))
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(result['answer_source'], 'ai')
            self.assertEqual(result['actions'][0]['view'], 'watch')
            self.assertEqual(len(seen), 1)
            self.assertEqual(exhausted['status'], 'budget_unavailable')
            self.assertEqual(lab.store.usage()['calls'], 1)
            self.assertEqual(lab.store.usage()['completed'], 1)
            self.assertEqual(guide_budget(lab)['guide_used'], 1)
            self.assertEqual(lab.store.jobs(), [])
            with self.assertRaises(RuntimeError):
                ResponsesHarness(lab.settings, lab.store).request({}, 'scientific-call-blocked')

    def test_partial_refusal_and_invented_actions_are_not_displayed_or_retried(self):
        for variant in ('partial', 'refusal', 'action', 'tool', 'excessive', 'extra'):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as directory:
                lab, _, _ = authored_lab(directory, allowance=1)
                def fake_open(request, timeout):
                    payload = json.loads(request.data)
                    response = provider_response(payload)
                    if variant == 'partial':
                        response['status'] = 'incomplete'
                    elif variant == 'refusal':
                        response['output'][0]['content'] = [{'type': 'refusal', 'refusal': 'No'}]
                    elif variant == 'tool':
                        response['output'] = [{'type': 'function_call', 'name': 'experiment', 'arguments': '{}'}]
                    else:
                        answer = json.loads(response['output'][0]['content'][0]['text'])
                        if variant == 'action': answer['action_ids'] = ['execute:research']
                        if variant == 'excessive': answer['action_ids'] = ['nav:home','nav:watch','nav:brief','nav:audit','nav:plan','nav:connect','nav:import']
                        if variant == 'extra': answer['javascript'] = 'alert(1)'
                        response['output'][0]['content'][0]['text'] = json.dumps(answer)
                    return io.BytesIO(json.dumps(response).encode())
                with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=fake_open) as provider:
                    result = guide_chat(lab, body(), inventory=inventory(lab))
                self.assertEqual(provider.call_count, 1)
                self.assertEqual(result['status'], 'assistant_unavailable')
                self.assertEqual(result['answer_source'], 'system_notice')
                self.assertEqual(result['actions'], [])
                self.assertEqual(result['sources'], [])
                self.assertEqual(lab.store.usage()['calls'], 1)
                self.assertEqual(lab.store.jobs(), [])

    def test_transport_failure_retains_reserved_call_without_provider_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, _, _ = authored_lab(directory, allowance=1)
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=TimeoutError('fixture')) as provider:
                result = guide_chat(lab, body(), inventory=inventory(lab))
            self.assertEqual(provider.call_count, 1)
            self.assertEqual(result['status'], 'assistant_unavailable')
            self.assertEqual(guide_budget(lab)['remaining'], 0)
            self.assertEqual(lab.store.usage()['completed'], 0)

    def test_repeated_valid_citation_is_deduped_but_unknown_reference_still_rejects(self):
        for unknown in (False, True):
            with self.subTest(unknown=unknown), tempfile.TemporaryDirectory() as directory:
                lab, _, _ = authored_lab(directory, allowance=1)
                def fake_open(request, timeout):
                    payload = json.loads(request.data)
                    response = provider_response(payload)
                    answer = json.loads(response['output'][0]['content'][0]['text'])
                    known = payload['text']['format']['schema']['properties']['source_ids']['items']['enum'][0]
                    answer['source_ids'] = [known, known] + (['source:invented:v1'] if unknown else [])
                    response['output'][0]['content'][0]['text'] = json.dumps(answer)
                    return io.BytesIO(json.dumps(response).encode())
                with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=fake_open) as provider:
                    result = guide_chat(lab, body(), inventory=inventory(lab))
                self.assertEqual(provider.call_count, 1)
                self.assertEqual(result['status'], 'assistant_unavailable' if unknown else 'ok')
                self.assertEqual(len(result['sources']), 0 if unknown else 1)
                if unknown:
                    traces = lab.store.traces(result['request_id'])
                    self.assertIn('unknown', traces[-1]['payload']['validation_reason'])

    def test_provider_limits_and_duplicate_known_actions_do_not_disable_a_valid_answer(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, _, _ = authored_lab(directory, allowance=1)
            def fake_open(request, timeout):
                payload = json.loads(request.data)
                schema = payload['text']['format']['schema']['properties']
                self.assertEqual(schema['action_ids']['maxItems'], 1)
                self.assertEqual(schema['source_ids']['maxItems'], 10)
                response = provider_response(payload)
                answer = json.loads(response['output'][0]['content'][0]['text'])
                answer['action_ids'] = ['nav:watch', 'nav:watch', 'nav:plan']
                response['output'][0]['content'][0]['text'] = json.dumps(answer)
                return io.BytesIO(json.dumps(response).encode())
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=fake_open) as provider:
                result = guide_chat(lab, body(), inventory=inventory(lab))
            self.assertEqual(result['status'], 'ok')
            self.assertEqual([row['id'] for row in result['actions']], ['nav:watch', 'nav:plan'])
            self.assertEqual(provider.call_count, 1)

    def test_guide_and_global_reservations_share_atomic_concurrent_ceiling(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, _, _ = authored_lab(directory, allowance=3)
            proxy = _GuideStore(lab.store, {'baseline_calls': 0, 'max_additional_calls': 3})
            def reserve(_):
                try: return proxy.reserve_call(3)
                except RuntimeError: return None
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(reserve, range(12)))
            accepted = [value for value in results if value]
            self.assertEqual(len(accepted), 3)
            self.assertEqual(len(set(accepted)), 3)
            self.assertEqual(guide_budget(lab)['guide_used'], 3)
            self.assertEqual(lab.store.usage()['calls'], 3)
            self.assertEqual(lab.settings.max_calls, 0)

    def test_guide_count_cannot_reset_by_later_baseline_reconfiguration(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, _, _ = authored_lab(directory, allowance=1)
            _GuideStore(lab.store, {'baseline_calls': 0, 'max_additional_calls': 1}).reserve_call(1)
            lab.settings.max_calls = 1
            (lab.settings.runtime / 'guide-config.json').write_text(json.dumps({'baseline_calls': 1, 'max_additional_calls': 1}))
            self.assertEqual(guide_budget(lab)['remaining'], 0)
            with self.assertRaises(RuntimeError):
                _GuideStore(lab.store, {'baseline_calls': 1, 'max_additional_calls': 1}).reserve_call(2)

    def test_expanded_authorization_keeps_historical_guide_count_and_research_cap_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, _, _ = authored_lab(directory, allowance=1)
            _GuideStore(lab.store, {'baseline_calls': 0, 'max_additional_calls': 1}).reserve_call(1)
            (lab.settings.runtime / 'guide-config.json').write_text(json.dumps({'baseline_calls': 0, 'max_additional_calls': 500}))
            budget = guide_budget(lab)
            self.assertEqual(budget['guide_used'], 1)
            self.assertEqual(budget['remaining'], 499)
            self.assertEqual(lab.settings.max_calls, 0)

    def test_live_proposal_is_only_bounded_unregistered_text_and_no_study_executes(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, _, _ = authored_lab(directory, allowance=1)
            proposal = {'question': 'Does a private evidence-check reminder alter publication accuracy?',
                'control_text': 'Continue carefully through the current task before submitting your final result.',
                'treatment_text': 'Check original evidence for this task before submitting your final result.'}
            def fake_open(request, timeout):
                payload = json.loads(request.data)
                self.assertIn('plan_draft', payload['text']['format']['schema']['required'])
                response = provider_response(payload)
                answer = json.loads(response['output'][0]['content'][0]['text'])
                answer['plan_draft'] = proposal
                answer['action_ids'] = ['nav:plan']
                response['output'][0]['content'][0]['text'] = json.dumps(answer)
                return io.BytesIO(json.dumps(response).encode())
            before = lab.store.list()
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=fake_open):
                result = guide_chat(lab, body(current_view='plan', message='Help me design a test'), inventory=inventory(lab))
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(result['plan_draft'], proposal)
            self.assertEqual(result['actions'][0]['view'], 'plan')
            self.assertEqual(lab.store.list(), before)
            self.assertEqual(lab.store.jobs(), [])

    def test_current_brief_and_run_are_exact_and_mismatched_sources_fail_before_call(self):
        from swarm_lab.observability_protocol import connect_observability, protocol_manifest
        with tempfile.TemporaryDirectory() as directory:
            lab, _, _ = authored_lab(directory, allowance=1)
            connection = connect_observability(lab, json.dumps(protocol_manifest()['example']).encode())
            selected = {'brief_ref': connection['brief_ref'], 'run_ref': connection['run_ref'], 'dataset_ref': connection['dataset_ref']}
            context, _, sources = grounded_context(lab, parse_guide_request(body(current_view='brief', current_context=selected)), inventory(lab))
            self.assertEqual(context['automatic_brief']['source_refs'], {'run_ref': connection['run_ref'], 'dataset_ref': connection['dataset_ref']})
            self.assertEqual(context['connected_run']['source']['kind'], 'authored_example')
            self.assertTrue(any(row['object_ref'] == connection['brief_ref'] for row in sources.values()))
            unrelated = lab.store.put('observation_brief', {'source_refs': {'dataset_ref': exact(lab.store.put('dataset', {'messages': []}))}})
            unrelated_behavior = lab.store.put('behavior', {'source_refs': {'dataset': exact(lab.store.put('dataset', {'messages': []}))}})
            _, _, selected_sources = grounded_context(lab, parse_guide_request(body(current_view='brief', current_context=selected)), inventory(lab))
            self.assertFalse(any(row['object_ref']['id'] in (unrelated['id'], unrelated_behavior['id']) for row in selected_sources.values()))
            other = lab.store.put('dataset', {'messages': []})
            with self.assertRaises(ValueError):
                guide_chat(lab, body(current_view='brief', current_context=selected | {'dataset_ref': exact(other)}), inventory=inventory(lab))
            self.assertEqual(lab.store.usage()['calls'], 0)

    def test_exact_plan_world_context_uses_reviewed_text_roles_and_fixed_budgets(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, _, _ = authored_lab(directory, allowance=1)
            plan, simulator, _ = saved_guided_world(lab)
            lab.store.put('guided_plan', {**plan['payload'], 'question': 'An unrelated later edit'}, plan['id'])
            lab.store.put('guided_simulator', {**simulator['payload'], 'name': 'Later world name'}, simulator['id'])
            selected = {'plan_ref': exact(plan), 'simulator_ref': exact(simulator)}
            context, catalog, sources = grounded_context(lab, parse_guide_request(body(current_view='simulator', current_context=selected)), inventory(lab))
            reviewed, world = context['current_reviewed_plan'], context['current_saved_world']
            self.assertEqual(reviewed['reviewed_plan']['question'], plan['payload']['question'])
            self.assertEqual(reviewed['reviewed_plan']['control_text'], plan['payload']['control_text'])
            self.assertEqual(world['roles'], ['coordinator', 'builder', 'verifier'])
            self.assertEqual(world['recorded_world']['teams'], 6)
            self.assertEqual(world['recorded_world']['max_actions'], 54)
            self.assertIn('inspect_artifact', world['tools'])
            self.assertIn('unverified prose', world['scope'])
            self.assertEqual(context['saved_study'], None)
            self.assertEqual(context['excerpts'], [])
            self.assertTrue(any(row['id'] == 'nav:simulator' for row in catalog))
            self.assertTrue(any(row['object_ref'] == exact(simulator) for row in sources.values()))
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=lambda request, timeout:
                       io.BytesIO(json.dumps(provider_response(json.loads(request.data))).encode())):
                self.assertEqual(guide_chat(lab, body(current_view='simulator', current_context=selected), inventory=inventory(lab))['status'], 'ok')
            self.assertEqual(lab.store.usage()['calls'], 1)
            self.assertEqual(lab.store.jobs(), [])

    def test_wrong_plan_source_world_or_typed_reference_cannot_reach_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, _, _ = authored_lab(directory, allowance=1)
            plan, simulator, _ = saved_guided_world(lab)
            other_plan = lab.store.put('guided_plan', {**plan['payload'], 'question': 'Another reviewed question'})
            bad_world = copy.deepcopy(simulator['payload'])
            bad_world['environment']['max_rounds'] = 4
            forged_world = lab.store.put('guided_simulator', bad_world)
            cases = [{'plan_ref': exact(other_plan), 'simulator_ref': exact(simulator)},
                {'simulator_ref': exact(forged_world)},
                {'plan_ref': exact(plan) | {'version': True}},
                {'simulator_ref': exact(simulator) | {'hash': '0' * 64}}]
            with patch('swarm_lab.guide_assistant.ResponsesHarness.request', side_effect=AssertionError('No provider for mismatched source')):
                for selected in cases:
                    with self.subTest(selected=selected), self.assertRaises(ValueError):
                        guide_chat(lab, body(current_view='simulator', current_context=selected), inventory=inventory(lab))
            self.assertEqual(lab.store.usage()['calls'], 0)

    def test_explicit_plan_navigation_has_an_action_contract_without_edit_or_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, _, _ = authored_lab(directory, allowance=2)
            plan, simulator, _ = saved_guided_world(lab)
            seen = []
            def fake_open(request, timeout):
                payload = json.loads(request.data); seen.append(payload)
                prompt = payload['instructions']; model_input = json.loads(payload['input'])
                self.assertIn('The host executes validated navigation', prompt)
                self.assertIn('return its matching nav action now', prompt)
                self.assertIn('Return no action for an automatic proactive brief', prompt)
                self.assertIn('plan_draft:null for navigation', prompt)
                choices = {row['id']: row for row in model_input['navigation_catalog']}
                self.assertIn('control and reminder text', choices['nav:plan']['purpose'])
                self.assertIn('does not execute', choices['nav:plan']['purpose'])
                self.assertIn('one matching nav ID', payload['text']['format']['schema']['properties']['action_ids']['description'])
                response = provider_response(payload)
                answer = json.loads(response['output'][0]['content'][0]['text'])
                automatic = model_input['question'].startswith('Automatically')
                answer.update(answer='Here is a source-bound summary.' if automatic else 'Opening your reviewed plan with the control and reminder.',
                              action_ids=[] if automatic else ['nav:plan'], plan_draft=None)
                response['output'][0]['content'][0]['text'] = json.dumps(answer)
                return io.BytesIO(json.dumps(response).encode())
            before = lab.store.list()
            selected = {'plan_ref': exact(plan), 'simulator_ref': exact(simulator)}
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=fake_open):
                explicit = guide_chat(lab, body(current_view='findings', current_context=selected,
                    message='Open our reviewed experiment plan here so I can see the control and reminder.'), inventory=inventory(lab))
                automatic = guide_chat(lab, body(current_view='brief', current_context=selected,
                    message='Automatically explain the current briefing.'), inventory=inventory(lab))
            self.assertEqual(explicit['status'], 'ok')
            self.assertEqual([row['view'] for row in explicit['actions']], ['plan'])
            self.assertIsNone(explicit['plan_draft'])
            self.assertEqual(set(explicit['actions'][0]), {'id', 'type', 'label', 'view', 'object_ref'})
            self.assertEqual(automatic['actions'], [])
            self.assertEqual(lab.store.list(), before)
            self.assertEqual(lab.store.jobs(), [])
            self.assertEqual(len(seen), 2)

    def test_actual_retained_team_counts_are_distinct_from_success_rates_and_primary_interval(self):
        from swarm_lab.experiments import create_protocol, run_experiment
        frozen = create_protocol(trials_per_arm=2, max_rounds=3,
            environment_override={'initial_state_distribution': {'valid_probability': 1}})
        report = run_experiment(frozen, resamples=100)
        record = {'id': 'authored-cpu-result', 'version': 1, 'kind': 'experiment', 'payload': report}
        summary = _study_summary(record)
        counted = summary['whole_team_success_counts']
        self.assertIs(counted['available'], True)
        self.assertEqual(counted['arm_counts'], {arm: {'correct': 2, 'total': 2} for arm in frozen['arms']})
        self.assertIn('intervention: 2 of 2 whole teams', counted['factual_sentence'])
        self.assertIn('control: 2 of 2 whole teams', counted['factual_sentence'])
        self.assertIn('no-note: 2 of 2 whole teams', counted['factual_sentence'])
        primary = summary['recorded_analysis']['primary_effect']
        self.assertEqual(primary['success_rate_treatment'], 1)
        self.assertEqual(primary['success_rate_control'], 1)
        self.assertNotIn('mean_treatment', primary)
        self.assertNotIn('bootstrap_ci95', primary)
        self.assertEqual(primary['ci95'], report['analysis']['primary_effect']['ci95'])
        self.assertLess(primary['ci95'][0], 0)
        self.assertGreater(primary['ci95'][1], 0)
        for mutation in ('bool_success', 'float_count', 'null_success', 'wrong_rate', 'missing_run', 'incomplete'):
            changed = copy.deepcopy(report)
            if mutation == 'bool_success': changed['runs'][0]['outcomes']['success'] = True
            if mutation == 'float_count': changed['analysis']['arms']['placebo']['n'] = 2.0
            if mutation == 'null_success': changed['runs'][0]['outcomes']['success'] = None
            if mutation == 'wrong_rate': changed['analysis']['primary_effect']['mean_treatment'] = .5
            if mutation == 'missing_run': changed['runs'].pop()
            if mutation == 'incomplete': changed['status'] = 'incomplete_infrastructure_failure'
            with self.subTest(mutation=mutation):
                bad = _study_summary({**record, 'payload': changed})
                self.assertIs(bad['whole_team_success_counts']['available'], False)
                self.assertIsNone(bad['whole_team_success_counts']['arm_counts'])
                self.assertIsNone(bad['recorded_analysis']['primary_effect'])


class GuideLoopbackTests(unittest.TestCase):
    def test_actual_csrf_http_guide_path_and_live_ledger_without_research_jobs(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, _, _ = authored_lab(directory, allowance=1)
            with socket.socket() as handle:
                handle.bind(('127.0.0.1', 0)); port = handle.getsockname()[1]
            servers = []
            real_open = urllib.request.urlopen
            def capture(*args, **kwargs):
                value = LocalResearchServer(*args, **kwargs); servers.append(value); return value
            provider_requests = []
            def intercept(request, *args, **kwargs):
                if isinstance(request, urllib.request.Request) and request.full_url == 'https://api.openai.com/v1/responses':
                    payload = json.loads(request.data); provider_requests.append(payload)
                    return io.BytesIO(json.dumps(provider_response(payload)).encode())
                return real_open(request, *args, **kwargs)
            with patch('swarm_lab.server.LocalResearchServer', side_effect=capture), \
                 patch('swarm_lab.harness.urllib.request.urlopen', side_effect=intercept):
                thread = threading.Thread(target=serve, args=(lab, port), daemon=True); thread.start()
                base = f'http://127.0.0.1:{port}'
                try:
                    deadline = time.monotonic() + 5
                    while True:
                        try:
                            with real_open(base + '/api/state', timeout=3) as response: state = json.load(response)
                            break
                        except urllib.error.URLError:
                            if time.monotonic() > deadline: raise
                            time.sleep(.02)
                    def post(raw, token=None):
                        request = urllib.request.Request(base + '/api/guide/chat', data=raw,
                            headers={'Content-Type': 'application/json', **({'X-Lab-Token': token} if token else {})})
                        with real_open(request, timeout=5) as response: return json.load(response)
                    with self.assertRaises(urllib.error.HTTPError) as error: post(body())
                    self.assertEqual(error.exception.code, 403)
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        post(b'{"message":"a","message":"b","current_view":"watch"}', state['csrf'])
                    self.assertEqual(error.exception.code, 400)
                    result = post(body(), state['csrf'])
                    self.assertEqual(result['status'], 'ok')
                    self.assertEqual(result['actions'][0]['type'], 'navigate')
                    self.assertEqual(post(body(), state['csrf'])['status'], 'budget_unavailable')
                    self.assertEqual(len(provider_requests), 1)
                    with real_open(base + '/api/state', timeout=3) as response: after = json.load(response)
                    self.assertEqual(after['max_calls'], 0)
                    self.assertEqual(after['usage']['calls'], 1)
                    self.assertEqual(after['jobs'], [])
                    self.assertEqual(after['objects'], state['objects'])
                finally:
                    for server in servers: server.shutdown()
                    thread.join(5)
                    self.assertFalse(thread.is_alive())


if __name__ == '__main__':
    unittest.main()
