"""Real Responses tool envelopes with temporary workspaces and fake provider I/O."""
import io
import json
import tempfile
import unittest
from unittest.mock import patch

from swarm_lab.guide_assistant import guide_chat, parse_guide_request, _authorized_operations
from swarm_lab.lab_workspace import chat_snapshot, mutate_workspace, save_state, append_message
from tests.test_guide_workspace import working_lab, request, response
from tests.test_guide_assistant import exact, inventory


def call_response(payload, name, args, identity='operation-1'):
    return io.BytesIO(json.dumps({'id': 'fixture-tool', 'model': payload['model'], 'status': 'completed',
        'usage': {'input_tokens': 20, 'output_tokens': 10}, 'output': [{'type': 'function_call',
        'name': name, 'call_id': identity, 'arguments': json.dumps(args)}]}).encode())


def motivated_plan(lab, chat, plan):
    from swarm_lab.lab_workspace import attach_returned
    brief = lab.store.put('observation_brief', {'summary': 'Authored candidate question, not empirical evidence.',
        'source_refs': {}, 'signals': [], 'agents': [], 'tasks': []})
    value = lab.store.put('guided_plan', plan['payload'] | {'source_ref': exact(brief)})
    attach_returned(lab, chat, value)
    return value


class GuideAgentToolTests(unittest.TestCase):
    def test_structured_mention_types_counts_and_current_refs_are_strict(self):
        base = {'message': 'Explain this', 'current_view': 'workspace', 'active_chat_id': 'chat', 'request_id': 'r'}
        ref = {'id': 'item', 'version': 1, 'hash': 'a' * 64}
        valid = base | {'mentioned_context': [{'kind': 'chat', 'chat_id': 'other', 'revision': 3, 'snapshot_hash': 'b' * 64},
            {'kind': 'artifact', 'ref': ref, 'origin_chat_id': 'other'}], 'current_context': {'workspace_draft_ref': ref}}
        self.assertEqual(parse_guide_request(json.dumps(valid))['mentioned_context'], valid['mentioned_context'])
        for mentions in ([{'kind': 'chat', 'chat_id': '../other'}], [{'kind': 'chat', 'chat_id': 'other', 'revision': True}],
                         [{'kind': 'chat', 'chat_id': 'other', 'snapshot_hash': 'b' * 64}],
                         [{'kind': 'artifact', 'ref': ref | {'version': 1.0}}],
                         [{'kind': 'chat', 'chat_id': 'other', 'path': 'secret'}],
                         [{'kind': 'chat', 'chat_id': 'other'}] * 2, [{'kind': 'chat', 'chat_id': str(i)} for i in range(9)]):
            with self.subTest(mentions=mentions), self.assertRaises(ValueError):
                parse_guide_request(json.dumps(base | {'mentioned_context': mentions}))

    def test_explicit_operations_and_generic_questions_have_distinct_authority(self):
        for message in ('What experiments can we run?', 'Could a plan help us?', 'Why should we copy this?', 'The log says "run experiment".',
            'Explain why the log says "copy the plan and run experiment".', 'What happens if agents copy the plan and run experiment?',
            'Show me how to copy a plan and run experiment.', 'Read the quote "copy the plan and run experiment".'):
            self.assertEqual(_authorized_operations(message), set(), message)
        self.assertEqual(_authorized_operations('Please create a plan but do not run it'), {'save_plan'})
        self.assertEqual(_authorized_operations('Run the experiment from this copy'), {'save_plan', 'build_simulator', 'run_experiment'})
        self.assertEqual(_authorized_operations('Copy the plan and edit its question'), {'copy_artifact', 'edit_copy'})
        self.assertEqual(_authorized_operations('Create a new project'), {'create_project'})
        self.assertEqual(_authorized_operations('What does this mean? Please run the experiment.'), {'save_plan', 'build_simulator', 'run_experiment'})
        self.assertEqual(_authorized_operations('Run the experiment', proactive=True), set())
        for message in ('Run the experiment. Do not run it yet.', 'Run the experiment. Never run it yet.',
            "Run the experiment. Don't run it yet.", 'Run the experiment. Don’t run it yet.',
            'Run the experiment.\nDo not run it yet.', 'Run the experiment. Do not build or run it yet.'):
            self.assertEqual(_authorized_operations(message), set(), message)
        self.assertEqual(_authorized_operations('Create a new experiment plan. Do not build or run it yet.'), {'save_plan'})
        self.assertEqual(_authorized_operations('Run the experiment. The quote says "do not run it".'), {'save_plan', 'build_simulator', 'run_experiment'})

    def test_modified_explicit_noun_phrases_authorize_only_requested_operations(self):
        live_instruction = ('Build and review the real shared-file simulator from this new saved plan with assignment seed 61006. '
            'Use actual builder and reviewer agents. Show the environment and its rules. Do not run subjects yet.')
        self.assertEqual(_authorized_operations(live_instruction), {'build_simulator'})
        for message in ('Please build and validate the actual saved world.',
                        'Can you create and review the real shared file environment?'):
            self.assertEqual(_authorized_operations(message), {'build_simulator'}, message)
        for message in ('Save a new experiment plan from this copy.',
                        'Please create and review the exact saved study plan from the current copy.'):
            self.assertEqual(_authorized_operations(message), {'save_plan'}, message)
        self.assertEqual(_authorized_operations('Execute the actual preregistered study.'), {'save_plan', 'build_simulator', 'run_experiment'})
        for message in ('What experiments can we run with a real shared-file simulator?',
                        'Could we build and review the real simulator?',
                        'Show me how to build and review a simulator.',
                        'Create a note about whether a real simulator would help.',
                        'Read the example "build and review the real simulator".',
                        'Build and review the real simulator. Do not build it yet.',
                        'Build and review the real simulator. Never build it.'):
            self.assertEqual(_authorized_operations(message), set(), message)

    def test_rubric_authorization_requires_save_or_explicit_laya_measurement(self):
        for message in ('Create a prompt-defined classifier for explicit waiting language.',
                        'Save a new binary rubric for unsupported success claims.'):
            self.assertEqual(_authorized_operations(message), {'save_rubric'})
        for message in ('Measure this rubric using Laya.', 'Classify these saved messages with Laya.',
                        'Probe this dataset via Laya.', 'Use Laya to classify this exact sample.'):
            self.assertEqual(_authorized_operations(message), {'measure_rubric'})
        self.assertEqual(_authorized_operations('Save a new rubric and measure this dataset using Laya.'), {'save_rubric', 'measure_rubric'})
        for message in ('Could Laya classify this?', 'What rubrics can we measure using Laya?',
                        'Measure this rubric.', 'Classify these saved messages.',
                        'Read the example "measure this rubric using Laya".',
                        'Measure this rubric using Laya. Do not classify or measure it yet.',
                        'Create a new rubric. Never create it yet.'):
            self.assertEqual(_authorized_operations(message), set(), message)

    def test_mentioned_chat_is_exact_readonly_discussion_and_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, borrowed, _, _, _ = working_lab(directory)
            old = chat_snapshot(lab, borrowed)
            append_message(lab, borrowed, role='user', content='LATER DISCUSSION', request_id='later')
            before = chat_snapshot(lab, borrowed)
            seen = []
            def provider(req, timeout):
                payload = json.loads(req.data); seen.append(payload)
                value = json.loads(payload['input'][0]['content'])['saved_data']['mentioned_context'][0]
                self.assertEqual(value['source']['chat_revision'], old['revision'])
                self.assertEqual(value['source']['snapshot_hash'], old['snapshot_hash'])
                self.assertNotIn('LATER DISCUSSION', json.dumps(value))
                return response(payload, sources=[value['source']['id']])
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=provider):
                result = guide_chat(lab, request(active, 'Summarize the selected old discussion', mentioned_context=[{
                    'kind': 'chat', 'chat_id': borrowed, 'revision': old['revision'], 'snapshot_hash': old['snapshot_hash']}]), inventory=inventory(lab))
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(result['read_receipts'][0]['selection'], 'explicit_mention')
            self.assertEqual(result['sources'][0]['kind'], 'workspace_chat_context')
            self.assertEqual(chat_snapshot(lab, borrowed), before)
            self.assertEqual(chat_snapshot(lab, active)['artifacts'], [])
            self.assertEqual(len(seen), 1)

    def test_invalid_mentioned_sources_reject_before_provider_or_message_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, borrowed, _, plan, _ = working_lab(directory)
            before = chat_snapshot(lab, active)
            bad = [{'kind': 'chat', 'chat_id': 'invented'}, {'kind': 'chat', 'chat_id': borrowed, 'revision': 1, 'snapshot_hash': 'f' * 64},
                {'kind': 'artifact', 'ref': exact(plan) | {'hash': 'f' * 64}, 'origin_chat_id': borrowed}]
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=AssertionError('No call before source validation')):
                for i, item in enumerate(bad):
                    with self.assertRaises(ValueError):
                        guide_chat(lab, request(active, request_id='invalid-' + str(i), mentioned_context=[item]), inventory=inventory(lab))
            self.assertEqual(chat_snapshot(lab, active), before)
            self.assertEqual(lab.store.usage()['calls'], 0)

    def test_older_linked_artifact_mention_beyond48_is_not_silently_rebased(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, borrowed, _, plan, _ = working_lab(directory)
            for i in range(50):
                artifact = lab.store.put('theory', {'name': 'later-' + str(i)})
                origin = chat_snapshot(lab, borrowed)
                # The fixture attaches returned exact items, independent of model output.
                from swarm_lab.lab_workspace import attach_returned
                attach_returned(lab, borrowed, artifact)
            self.assertNotIn(exact(plan), [link['ref'] for link in chat_snapshot(lab, borrowed)['artifacts'][-48:]])
            def provider(req, timeout):
                payload = json.loads(req.data); data = json.loads(payload['input'][0]['content'])
                selected = data['saved_data']['mentioned_context'][0]
                self.assertEqual(selected['ref'], exact(plan)); self.assertEqual(selected['origin_chat_id'], borrowed)
                return response(payload, sources=[selected['source_id']])
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=provider):
                result = guide_chat(lab, request(active, mentioned_context=[{'kind': 'artifact', 'ref': exact(plan), 'origin_chat_id': borrowed}]), inventory=inventory(lab))
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(result['sources'][0]['object_ref'], exact(plan))
            self.assertEqual(chat_snapshot(lab, active)['artifacts'], [])

    def test_real_local_create_tool_is_invoked_once_then_receipt_restores(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, _, _, _, _ = working_lab(directory)
            seen = []
            def provider(req, timeout):
                payload = json.loads(req.data); seen.append(payload)
                if len(seen) == 1:
                    self.assertIn('create_project', [tool['name'] for tool in payload['tools']])
                    return call_response(payload, 'create_project', {'name': 'New project'})
                value = json.loads(next(row['output'] for row in payload['input'] if row.get('type') == 'function_call_output'))
                self.assertEqual(value['status'], 'completed')
                return response(payload, answer='Created the requested project.', actions=['nav:projects'])
            raw = request(active, 'Create a new project named New project')
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=provider):
                first = guide_chat(lab, raw, inventory=inventory(lab))
                second = guide_chat(lab, raw, inventory=inventory(lab))
            self.assertEqual(first['status'], 'ok'); self.assertTrue(second['reused'])
            self.assertEqual(first['tool_results'][0]['tool'], 'create_project')
            self.assertEqual(first['tool_results'][0]['status'], 'completed')
            self.assertEqual(len(seen), 2)
            from swarm_lab.guide_tools import guide_activity
            self.assertEqual([row['phase'] for row in guide_activity(lab, active)['events']], ['started', 'completed'])
            saved = chat_snapshot(lab, active)['messages'][-1]['metadata']['guide_result']
            self.assertEqual(saved['tool_results'], first['tool_results'])
            self.assertIn('not hidden model reasoning', first['working_notes_scope'])

    def test_generic_or_proactive_request_cannot_force_a_write_tool(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, _, _, _, _ = working_lab(directory)
            def provider(req, timeout):
                payload = json.loads(req.data)
                self.assertEqual([tool['name'] for tool in payload['tools']], ['read_chat_context', 'event_neighborhood', 'list_rubrics'])
                return call_response(payload, 'run_experiment', {'simulator_ref': {'id': 'invented', 'version': 1, 'hash': 'a' * 64}})
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=provider), \
                 patch('swarm_lab.guide_tools.execute_guide_tool', side_effect=AssertionError('No unauthorized dispatch')):
                result = guide_chat(lab, request(active, 'What experiments can we run?'), inventory=inventory(lab))
            self.assertEqual(result['status'], 'assistant_unavailable')
            self.assertEqual(result['tool_results'], [])
            self.assertEqual(lab.store.jobs(), [])

    def test_current_copy_source_brief_is_shown_and_allowed_for_actual_plan_tool(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, borrowed, _, plan, _ = working_lab(directory)
            plan = motivated_plan(lab, borrowed, plan)
            receipt = mutate_workspace(lab, {'op': 'clone_artifact', 'request_id': 'copy', 'artifact_ref': exact(plan),
                'origin_chat_id': borrowed, 'target_chat_id': active})
            draft = receipt['artifact_ref']; snapshot = chat_snapshot(lab, active)
            save_state(lab, active, expected_revision=snapshot['revision'], request_id='ui-copy',
                state={'view': 'workspace-copy', 'ui': {'workspace': {'copy_ref': draft}}})
            seen = []
            def provider(req, timeout):
                payload = json.loads(req.data); seen.append(payload)
                if len(seen) == 1:
                    data = json.loads(payload['input'][0]['content'])['saved_data']['current_editable_copy']
                    self.assertEqual(data['fields']['question'], plan['payload']['question'])
                    self.assertEqual(data['source_brief_ref'], plan['payload']['source_ref'])
                    self.assertIn(data['motivating_brief']['source_id'], payload['text']['format']['schema']['properties']['source_ids']['items']['enum'])
                    return call_response(payload, 'save_plan', {'source_ref': data['source_brief_ref'], 'question': 'Does a private check help?',
                        'control_text': 'Read the current note before deciding.', 'treatment_text': 'Check the current file before deciding.'})
                value = json.loads(next(row['output'] for row in payload['input'] if row.get('type') == 'function_call_output'))
                self.assertEqual(value['status'], 'completed')
                return response(payload, answer='Saved a new plan.', actions=['nav:plan'])
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=provider):
                result = guide_chat(lab, request(active, 'Save a plan from this copy', current_view='workspace-copy'), inventory=inventory(lab))
            self.assertEqual(result['status'], 'ok')
            self.assertIn('plan_ref', result['updated_context'])
            self.assertNotEqual(result['updated_context']['plan_ref'], exact(plan))
            self.assertEqual(lab.store.get(draft['id'], draft['version'])['payload']['source_ref'], exact(plan))

    def test_foreign_copy_is_readonly_context_not_owned_editable_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, borrowed, _, plan, _ = working_lab(directory)
            plan = motivated_plan(lab, borrowed, plan)
            origin = borrowed
            receipt = mutate_workspace(lab, {'op': 'clone_artifact', 'request_id': 'foreign-copy', 'artifact_ref': exact(plan),
                'origin_chat_id': origin, 'target_chat_id': borrowed})
            draft = receipt['artifact_ref']
            def provider(req, timeout):
                payload = json.loads(req.data); value = json.loads(payload['input'][0]['content'])['saved_data']['mentioned_context'][0]
                self.assertEqual(value['working_copy']['source_brief_ref'], plan['payload']['source_ref'])
                return response(payload, sources=[value['source_id']])
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=provider):
                result = guide_chat(lab, request(active, mentioned_context=[{'kind': 'artifact', 'ref': draft, 'origin_chat_id': borrowed}]), inventory=inventory(lab))
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(chat_snapshot(lab, active)['artifacts'], [])
            with self.assertRaisesRegex(ValueError, 'belong to this exact chat'):
                guide_chat(lab, request(active, request_id='foreign-active', current_context={'workspace_draft_ref': draft}), inventory=inventory(lab))

    def test_ready_simulator_without_execution_result_is_an_actual_run_input(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, _, _, plan, simulator = working_lab(directory)
            simulator = lab.store.put('guided_simulator', simulator['payload'] | {'status': 'ready'})
            seen = []
            def provider(req, timeout):
                payload = json.loads(req.data); seen.append(payload)
                if len(seen) == 1:
                    world = json.loads(payload['input'][0]['content'])['saved_data']['current_saved_world']
                    self.assertEqual(world['simulator_ref'], exact(simulator))
                    self.assertEqual(world['recorded_status'], 'ready')
                    self.assertNotIn('execution_ref', world)
                    self.assertNotIn('this chat does not run', world['scope'])
                    self.assertIn('Reading this saved executable-world description does not execute', world['scope'])
                    self.assertIn('execution_ref or result_ref is an OUTPUT', payload['instructions'])
                    tool = next(row for row in payload['tools'] if row['name'] == 'run_experiment')
                    self.assertIn('not required', tool['parameters']['properties']['simulator_ref']['description'])
                    return call_response(payload, 'run_experiment', {'simulator_ref': exact(simulator)})
                receipt = json.loads(next(row['output'] for row in payload['input'] if row.get('type') == 'function_call_output'))
                self.assertEqual(receipt['status'], 'completed')
                return response(payload, answer='The requested run returned its operation receipt.')
            receipt = {'status': 'completed', 'tool': 'run_experiment', 'summary': 'Fixture dispatch completed; no empirical subjects.',
                'result_refs': [], 'updated_context': {}, 'view': 'findings', 'reused': False}
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=provider), \
                 patch('swarm_lab.guide_tools.execute_guide_tool', return_value=receipt) as execute:
                result = guide_chat(lab, request(active, 'Run this new experiment with real LLM subject teams using the exact reviewed simulator.',
                    current_context={'plan_ref': exact(plan), 'simulator_ref': exact(simulator)}), inventory=inventory(lab))
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(execute.call_count, 1)
            self.assertEqual(execute.call_args.args[1:3], ('run_experiment', {'simulator_ref': exact(simulator)}))
            self.assertEqual(result['tool_results'][0]['status'], 'completed')

    def test_rubric_listing_reads_actual_catalog_without_scientific_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, _, _, _, _ = working_lab(directory); seen = []
            before = lab.store.list()
            def provider(req, timeout):
                payload = json.loads(req.data); seen.append(payload)
                if len(seen) == 1:
                    self.assertIn('list_rubrics', [row['name'] for row in payload['tools']])
                    self.assertNotIn('measure_rubric', [row['name'] for row in payload['tools']])
                    return call_response(payload, 'list_rubrics', {})
                receipt = json.loads(next(row['output'] for row in payload['input'] if row.get('type') == 'function_call_output'))
                self.assertEqual([row['id'] for row in receipt['rubrics']['catalog']], ['C' + str(i) for i in range(1, 9)])
                self.assertTrue(all(row['status'] == 'proposed_unvalidated' for row in receipt['rubrics']['catalog']))
                return response(payload, answer='These are proposed opportunity constructs, not validated scores.')
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=provider):
                result = guide_chat(lab, request(active, 'What behavior rubrics can we inspect?'), inventory=inventory(lab))
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(lab.store.list(), before)
            self.assertEqual(result['tool_results'][0]['tool'], 'list_rubrics')
            self.assertEqual(result['tool_results'][0]['result_refs'], [])

    def test_event_neighborhood_actual_read_keeps_exact_source_and_no_private_content(self):
        from tests.test_event_evidence_graph import fixture, event
        with tempfile.TemporaryDirectory() as directory:
            lab, active, _, _, _, _ = working_lab(directory)
            payload = fixture()['payload']
            payload['events'].append(event('private-note', 'reasoning.recorded', {'content': 'PRIVATE_BODY_NOT_FOR_GRAPH'}, actor='a', recipients=[]))
            run = lab.store.put('observability_run', payload); before = lab.store.list(); linked = chat_snapshot(lab, active)['artifacts']; seen = []
            def provider(req, timeout):
                value = json.loads(req.data); seen.append(value)
                if len(seen) == 1:
                    current = json.loads(value['input'][0]['content'])['saved_data']['connected_run']
                    self.assertEqual(current['selected_event']['id'], 'post')
                    self.assertNotIn('PRIVATE_BODY_NOT_FOR_GRAPH', json.dumps(current))
                    return call_response(value, 'event_neighborhood', {'run_ref': exact(run), 'event_id': 'post', 'hops': 2})
                receipt = json.loads(next(row['output'] for row in value['input'] if row.get('type') == 'function_call_output'))
                graph = receipt['event_graph']
                self.assertEqual(graph['source_ref'], exact(run))
                self.assertEqual(graph['seed_event_id'], 'post')
                self.assertFalse(graph['scope']['causal_graph'])
                self.assertFalse(graph['scope']['raw_content_exported'])
                self.assertTrue(any(row['relation'] == 'addressed_recipient' for row in graph['edges']))
                self.assertNotIn('PRIVATE_BODY_NOT_FOR_GRAPH', json.dumps(graph))
                return response(value, answer='These are captured field references; they do not establish readership.',
                    sources=['source:' + run['id'] + ':v' + str(run['version'])])
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=provider):
                result = guide_chat(lab, request(active, 'Inspect this captured event neighborhood.', current_context={
                    'run_ref': exact(run), 'selected_event_id': 'post'}), inventory=inventory(lab))
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(result['tool_results'][0]['tool'], 'event_neighborhood')
            self.assertEqual(result['tool_results'][0]['result_refs'], [exact(run)])
            self.assertEqual(lab.store.list(), before)
            self.assertEqual(chat_snapshot(lab, active)['artifacts'], linked)

    def test_event_read_invalid_source_seed_or_hops_refuses_before_operation_claim(self):
        from tests.test_event_evidence_graph import fixture
        from swarm_lab.guide_tools import execute_guide_tool
        with tempfile.TemporaryDirectory() as directory:
            lab, active, _, _, _, _ = working_lab(directory)
            run = lab.store.put('observability_run', fixture()['payload']); before = lab.store.list()
            good = {'run_ref': exact(run), 'event_id': 'post', 'hops': 1}
            for index, bad in enumerate((good | {'hops': True}, good | {'hops': 3}, good | {'event_id': 'invented'},
                good | {'run_ref': exact(run) | {'hash': 'f' * 64}})):
                with self.assertRaises(ValueError):
                    execute_guide_tool(lab, 'event_neighborhood', bad, chat_id=active, request_id='bad-event-' + str(index),
                        authorized_tools=['event_neighborhood'], allowed_refs=[exact(run)])
            self.assertEqual(lab.store.list(), before)
            snapshot = chat_snapshot(lab, active)
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=AssertionError('No provider for absent selected event')):
                with self.assertRaisesRegex(ValueError, 'Selected event is absent'):
                    guide_chat(lab, request(active, current_context={'run_ref': exact(run), 'selected_event_id': 'missing'}), inventory=inventory(lab))
            self.assertEqual(chat_snapshot(lab, active), snapshot)
            with self.assertRaises(ValueError):
                parse_guide_request(request(active, current_context={'selected_event_id': 'post'}))

    def test_saved_rubric_and_fake_laya_measurement_are_exact_atomic_text_context(self):
        from swarm_lab import behavior_rubrics
        from swarm_lab.classifiers import build_questions
        from swarm_lab.store import clean, fingerprint
        with tempfile.TemporaryDirectory() as directory:
            lab, active, _, dataset, _, _ = working_lab(directory); seen = []; measured = []
            spec = {key: behavior_rubrics.BUILTINS[0][key] for key in behavior_rubrics.FIELDS}
            original_measure = behavior_rubrics.measure_rubric
            class FakeLaya:
                def measure(self, message, definitions):
                    measured.append(message['id'])
                    label = True if message['id'] == 'm-1' else None
                    return {'message_id': message['id'], 'question_schema_hash': fingerprint(build_questions(definitions, neutral_labels=True)),
                        'source_content_hash': fingerprint(clean(message['content'])), 'labels': {'explicit_signal': label},
                        'probabilities': {'explicit_signal': .9 if label else .5},
                        'status': 'measured' if label else 'abstained'}
                def close(self): pass
            def provider(req, timeout):
                payload = json.loads(req.data); seen.append(payload)
                if len(seen) == 1:
                    tools = [row['name'] for row in payload['tools']]
                    self.assertIn('save_rubric', tools); self.assertIn('measure_rubric', tools)
                    self.assertIn('opportunity-coded behavior score', payload['instructions'])
                    return call_response(payload, 'save_rubric', spec, 'save-rubric')
                receipts = [json.loads(row['output']) for row in payload['input'] if row.get('type') == 'function_call_output']
                if len(seen) == 2:
                    rubric_ref = receipts[-1]['updated_context']['rubric_ref']
                    return call_response(payload, 'measure_rubric', {'rubric_ref': rubric_ref, 'dataset_ref': exact(dataset), 'limit': 2}, 'measure-rubric')
                measurement = receipts[-1]
                self.assertEqual(measurement['measurement_summary']['text_positive'], 1)
                self.assertEqual(measurement['measurement_summary']['text_unknown'], 1)
                self.assertEqual(measurement['measurement_summary']['assessable_opportunities'], 0)
                self.assertEqual(measurement['measurement_summary']['rubric_assessment'], 'not_assessable')
                ref = measurement['updated_context']['measurement_ref']
                return response(payload, answer='One candidate text signal and one unknown; opportunities are not assessable.',
                    sources=['source:' + ref['id'] + ':v' + str(ref['version'])])
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=provider), \
                 patch('swarm_lab.behavior_rubrics.measure_rubric', side_effect=lambda lab, raw: original_measure(lab, raw, backend_factory=FakeLaya)):
                result = guide_chat(lab, request(active, 'Save a new rubric and measure this dataset using Laya.',
                    current_context={'dataset_ref': exact(dataset)}), inventory=inventory(lab))
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(measured, ['m-1', 'm-2'])
            self.assertEqual([row['tool'] for row in result['tool_results']], ['save_rubric', 'measure_rubric'])
            measurement_ref = result['updated_context']['measurement_ref']
            obj = lab.store.get(measurement_ref['id'], measurement_ref['version'])
            self.assertTrue(all(row['opportunity'] == 'uncertain' and row['assessment'] == 'not_assessable' for row in obj['payload']['records']))
            from swarm_lab.guide_assistant import grounded_context
            selected = parse_guide_request(request(active, current_context={'measurement_ref': measurement_ref}))
            context, _, _ = grounded_context(lab, selected, inventory(lab))
            summary = context['current_rubric_measurement']
            self.assertEqual(summary['source_refs']['dataset_ref'], exact(dataset))
            self.assertEqual(summary['summary']['text_unknown'], 1)
            self.assertNotIn('records', summary)
            wrong = lab.store.put('dataset', {'messages': []})
            before = chat_snapshot(lab, active)
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=AssertionError('No call before parent validation')):
                with self.assertRaisesRegex(ValueError, 'selected sources disagree'):
                    guide_chat(lab, request(active, request_id='wrong-measurement-parent', current_context={
                        'measurement_ref': measurement_ref, 'dataset_ref': exact(wrong)}), inventory=inventory(lab))
            self.assertEqual(chat_snapshot(lab, active), before)

    def test_laya_runtime_unavailable_remains_unknown_in_actual_tool_receipt(self):
        from swarm_lab import behavior_rubrics
        with tempfile.TemporaryDirectory() as directory:
            lab, active, _, dataset, _, _ = working_lab(directory)
            spec = {key: behavior_rubrics.BUILTINS[1][key] for key in behavior_rubrics.FIELDS}
            rubric_ref = behavior_rubrics.save_rubric(lab, json.dumps(spec).encode())['rubric_ref']; seen = []
            def provider(req, timeout):
                payload = json.loads(req.data); seen.append(payload)
                if len(seen) == 1:
                    return call_response(payload, 'measure_rubric', {'rubric_ref': rubric_ref, 'dataset_ref': exact(dataset), 'limit': 2})
                receipt = json.loads(next(row['output'] for row in payload['input'] if row.get('type') == 'function_call_output'))
                self.assertEqual(receipt['status'], 'completed')
                self.assertEqual(receipt['measurement_status'], 'operational_failure')
                self.assertEqual(receipt['measurement_summary']['text_unknown'], 2)
                self.assertEqual(receipt['measurement_summary']['text_positive'], 0)
                self.assertEqual(receipt['measurement_summary']['fallback'], 'none')
                return response(payload, answer='Local Laya is unavailable; both sampled labels remain unknown.')
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=provider):
                result = guide_chat(lab, request(active, 'Measure this rubric using Laya.', current_context={
                    'dataset_ref': exact(dataset), 'rubric_ref': rubric_ref}), inventory=inventory(lab))
            self.assertEqual(result['status'], 'ok')
            self.assertIn('unknown', result['tool_results'][0]['summary'])
            obj = lab.store.get(result['updated_context']['measurement_ref']['id'])
            self.assertTrue(all(row['text_measurement']['labels']['explicit_signal'] is None for row in obj['payload']['records']))

    def test_current_chat_fork_uses_post_claim_revision_and_actual_new_navigation(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, _, _, _, _ = working_lab(directory)
            before = chat_snapshot(lab, active); seen = []
            def provider(req, timeout):
                payload = json.loads(req.data); seen.append(payload)
                if len(seen) == 1:
                    context = json.loads(payload['input'][0]['content'])['saved_data']
                    revision = context['current_operation_chat']['revision']
                    self.assertEqual(revision, before['revision'] + 1)
                    return call_response(payload, 'fork_chat', {'origin_chat_id': active,
                        'expected_revision': revision, 'name': 'Actual branch', 'project_id': None})
                value = json.loads(next(row['output'] for row in payload['input'] if row.get('type') == 'function_call_output'))
                self.assertEqual(value['status'], 'completed')
                self.assertNotEqual(value['chat_id'], active)
                choice = 'chat:open:' + value['chat_id']
                self.assertIn(choice, payload['text']['format']['schema']['properties']['action_ids']['items']['enum'])
                return response(payload, answer='Created the requested branch.', actions=[choice])
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=provider):
                result = guide_chat(lab, request(active, 'Fork this chat'), inventory=inventory(lab))
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(result['actions'][0]['type'], 'open_chat')
            branch = chat_snapshot(lab, result['actions'][0]['chat_id'])
            self.assertEqual(branch['origin']['revision'], before['revision'] + 1)
            self.assertEqual(len(result['tool_results']), 1)

    def test_exact_selected_old_replay_action_preserves_source(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, borrowed, dataset, _, _ = working_lab(directory)
            from swarm_lab.lab_workspace import attach_returned
            attach_returned(lab, borrowed, dataset)
            def provider(req, timeout):
                payload = json.loads(req.data)
                choice = 'replay:' + dataset['id'] + ':v' + str(dataset['version'])
                self.assertIn(choice, payload['text']['format']['schema']['properties']['action_ids']['items']['enum'])
                return response(payload, actions=[choice])
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=provider):
                result = guide_chat(lab, request(active, 'Replay this exact saved conversation', mentioned_context=[{
                    'kind': 'artifact', 'ref': exact(dataset), 'origin_chat_id': borrowed}]), inventory=inventory(lab))
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(result['actions'][0]['object_ref'], exact(dataset))
            self.assertEqual(result['actions'][0]['view'], 'watch')
            self.assertEqual(result['tool_results'], [])

    def test_connect_discover_in_new_chat_exposes_real_bounded_source_selector(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, _, dataset, _, _ = working_lab(directory)
            seen = []
            def provider(req, timeout):
                payload = json.loads(req.data); seen.append(payload)
                context = json.loads(payload['input'][0]['content'])['saved_data']
                self.assertEqual(context['inventory'], [])
                selector = context['available_dataset_sources']
                self.assertEqual(len(selector), 1)
                self.assertEqual(selector[0]['ref'], exact(dataset))
                self.assertIn('discover', [row['name'] for row in payload['tools']])
                return response(payload, answer='I can investigate that exact saved selection once selected.')
            before = chat_snapshot(lab, active)
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=provider):
                result = guide_chat(lab, request(active, 'Connect the data and discover patterns'), inventory=inventory(lab))
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(chat_snapshot(lab, active)['artifacts'], before['artifacts'])
            self.assertEqual(lab.store.jobs(), [])

    def test_read_tool_activity_is_actual_and_bounded_not_model_reasoning(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, borrowed, _, _, _ = working_lab(directory); seen = []
            def provider(req, timeout):
                payload = json.loads(req.data); seen.append(payload)
                if len(seen) == 1: return call_response(payload, 'read_chat_context', {'chat_id': borrowed})
                return response(payload, answer='Read the selected saved discussion.')
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=provider):
                result = guide_chat(lab, request(active, 'Read that discussion'), inventory=inventory(lab))
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(result['tool_results'][0]['tool'], 'read_chat_context')
            self.assertEqual(result['tool_results'][0]['status'], 'completed')
            from swarm_lab.guide_tools import guide_activity
            self.assertEqual([row['phase'] for row in guide_activity(lab, active)['events']], ['started', 'completed'])
            self.assertEqual(result['tool_results'][0]['result_refs'], [])
            self.assertNotIn('reasoning', json.dumps(result['working_notes']).lower())

    def test_actual_server_route_has_tools_without_client_mutation_proposals(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, borrowed, _, plan, _ = working_lab(directory); seen = []
            def provider(req, timeout):
                payload = json.loads(req.data); seen.append(payload)
                ids = payload['text']['format']['schema']['properties']['action_ids']['items']['enum']
                self.assertFalse(any(value.startswith(('chat:clone_artifact:', 'chat:reuse_artifact:', 'chat:fork:')) for value in ids))
                if len(seen) == 1:
                    self.assertIn('copy_artifact', [row['name'] for row in payload['tools']])
                    return call_response(payload, 'copy_artifact', {'artifact_ref': exact(plan), 'origin_chat_id': borrowed, 'name': None})
                receipt = json.loads(next(row['output'] for row in payload['input'] if row.get('type') == 'function_call_output'))
                self.assertEqual(receipt['status'], 'completed')
                ref = receipt['result_refs'][0]
                return response(payload, answer='Created an editable copy.', actions=['object:' + ref['id'] + ':v' + str(ref['version'])])
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=provider):
                result = guide_chat(lab, request(active, 'Copy this selected plan', mentioned_context=[{
                    'kind': 'artifact', 'ref': exact(plan), 'origin_chat_id': borrowed}]), inventory=inventory(lab),
                    queue_submit=lambda *args: self.fail('Copy does not queue research'))
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(result['tool_results'][0]['tool'], 'copy_artifact')
            self.assertEqual(result['actions'][0]['type'], 'open_object')
            self.assertEqual(lab.store.get(result['actions'][0]['object_ref']['id'])['kind'], 'workspace_draft')

    def test_missing_reuse_receipt_gets_one_corrective_tool_round_then_one_actual_link(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, borrowed, _, plan, _ = working_lab(directory); seen = []
            def provider(req, timeout):
                payload = json.loads(req.data); seen.append(payload)
                if len(seen) == 1:
                    return response(payload, answer='I linked the saved plan.', actions=['object:' + plan['id'] + ':v' + str(plan['version'])])
                if len(seen) == 2:
                    self.assertEqual(payload['tool_choice'], {'type': 'function', 'name': 'reuse_artifact'})
                    self.assertIn('has not been invoked', payload['input'][-1]['content'])
                    return call_response(payload, 'reuse_artifact', {'artifact_ref': exact(plan), 'origin_chat_id': borrowed}, 'actual-reuse')
                receipt = json.loads(next(row['output'] for row in payload['input'] if row.get('type') == 'function_call_output'))
                self.assertEqual(receipt['status'], 'completed')
                return response(payload, answer='The actual tool linked the saved plan.')
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=provider):
                result = guide_chat(lab, request(active, 'Reuse this exact saved plan in this chat.', mentioned_context=[{
                    'kind': 'artifact', 'ref': exact(plan), 'origin_chat_id': borrowed}]), inventory=inventory(lab),
                    queue_submit=lambda *args: self.fail('Reuse is not scientific execution'))
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(len(seen), 3)
            self.assertEqual([row['tool'] for row in result['tool_results']], ['reuse_artifact'])
            self.assertEqual([row['ref'] for row in chat_snapshot(lab, active)['artifacts']], [exact(plan)])

    def test_prose_only_workspace_success_is_suppressed_after_bounded_correction(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, borrowed, _, plan, _ = working_lab(directory); seen = []
            def provider(req, timeout):
                payload = json.loads(req.data); seen.append(payload)
                return response(payload, answer='Successfully copied and linked everything.',
                    actions=['object:' + plan['id'] + ':v' + str(plan['version'])])
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=provider), \
                 patch('swarm_lab.guide_tools.execute_guide_tool', side_effect=AssertionError('No function was returned')):
                result = guide_chat(lab, request(active, 'Copy this saved plan.', mentioned_context=[{
                    'kind': 'artifact', 'ref': exact(plan), 'origin_chat_id': borrowed}]), inventory=inventory(lab),
                    queue_submit=lambda *args: self.fail('No scientific job'))
            self.assertEqual(len(seen), 2)
            self.assertEqual(result['status'], 'workspace_operation_unconfirmed')
            self.assertEqual(result['answer_source'], 'system_notice')
            self.assertIn('was not performed', result['answer'])
            self.assertNotIn('Successfully', result['answer'])
            self.assertEqual(result['actions'], [])
            self.assertEqual(result['tool_results'], [])
            self.assertEqual(chat_snapshot(lab, active)['artifacts'], [])

    def test_wrong_copy_source_returns_feedback_then_correct_brief_saves_one_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, borrowed, _, plan, _ = working_lab(directory)
            plan = motivated_plan(lab, borrowed, plan)
            receipt = mutate_workspace(lab, {'op': 'clone_artifact', 'request_id': 'copy-feedback', 'artifact_ref': exact(plan),
                'origin_chat_id': borrowed, 'target_chat_id': active})
            draft = receipt['artifact_ref']; before = lab.store.list(kind='guided_plan'); seen = []
            args = {'question': 'Does checking the file improve correct publication?',
                'control_text': 'Read the current note before deciding.', 'treatment_text': 'Check the current file before deciding.'}
            def provider(req, timeout):
                payload = json.loads(req.data); seen.append(payload)
                if len(seen) == 1:
                    tool = next(row for row in payload['tools'] if row['name'] == 'save_plan')
                    self.assertIn('not a workspace_draft', tool['parameters']['properties']['source_ref']['description'])
                    return call_response(payload, 'save_plan', args | {'source_ref': draft}, 'refused-source')
                values = [json.loads(row['output']) for row in payload['input'] if row.get('type') == 'function_call_output']
                self.assertEqual(values[0]['status'], 'failed')
                self.assertTrue(values[0]['input_refused']); self.assertFalse(values[0]['operation_started'])
                self.assertIn('observation_brief', values[0]['error'])
                if len(seen) == 2:
                    return call_response(payload, 'save_plan', args | {'source_ref': plan['payload']['source_ref']}, 'corrected-source')
                self.assertEqual(values[1]['status'], 'completed')
                return response(payload, answer='Corrected the source and saved the plan.', actions=['nav:plan'])
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=provider):
                result = guide_chat(lab, request(active, 'Create a new experiment plan. Do not build or run it yet.',
                    current_context={'workspace_draft_ref': draft}), inventory=inventory(lab), queue_submit=lambda *args: self.fail('No jobs'))
            self.assertEqual(result['status'], 'ok'); self.assertEqual(len(seen), 3)
            self.assertEqual(len(lab.store.list(kind='guided_plan')), len(before) + 1)
            self.assertEqual([row['status'] for row in result['tool_results']], ['failed', 'completed'])
            self.assertFalse(result['tool_results'][0]['operation_started'])
            self.assertTrue(result['tool_results'][0]['input_refused'])
            refusal = [row['payload'] for row in lab.store.traces(result['request_id']) if row['payload'].get('type') == 'guide_tool_input_refused']
            self.assertEqual(len(refusal), 1); self.assertFalse(refusal[0]['operation_started'])
            with lab.store.connect() as connection:
                self.assertEqual(connection.execute('SELECT count(*) FROM guide_tool_requests').fetchone()[0], 1)
            saved = chat_snapshot(lab, active)['messages'][-1]['metadata']['guide_result']
            self.assertEqual(saved['tool_results'], result['tool_results'])

    def test_started_failure_does_not_enable_an_automatic_corrected_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            lab, active, _, _, _, _ = working_lab(directory); seen = []; dispatched = []
            def provider(req, timeout):
                payload = json.loads(req.data); seen.append(payload)
                if len(seen) == 1: return call_response(payload, 'create_project', {'name': 'Requested project'}, 'failed-operation')
                self.assertNotIn('create_project', [row['name'] for row in payload['tools']])
                return call_response(payload, 'create_project', {'name': 'Changed request'}, 'must-not-retry')
            def fail_dispatch(*args, **kwargs):
                dispatched.append(kwargs['request_id'])
                return {'status': 'failed', 'tool': 'create_project', 'summary': 'Operation failed after its durable invocation.',
                    'result_refs': [], 'updated_context': {}, 'view': None}
            with patch('swarm_lab.harness.urllib.request.urlopen', side_effect=provider), \
                 patch('swarm_lab.guide_tools.execute_guide_tool', side_effect=fail_dispatch):
                result = guide_chat(lab, request(active, 'Create a new project'), inventory=inventory(lab))
            self.assertEqual(result['status'], 'assistant_unavailable'); self.assertEqual(len(dispatched), 1)
            self.assertEqual(result['tool_results'][0]['status'], 'failed')
            self.assertNotIn('input_refused', result['tool_results'][0])


if __name__ == '__main__':
    unittest.main()
