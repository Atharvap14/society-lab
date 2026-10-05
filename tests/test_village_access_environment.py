"""CPU tool-contract witnesses; these authored actions are not model experiments."""
import copy
import json
import unittest

from swarm_lab.village_access_environment import (AGENTS, DOC_KEYS, VillageAccessEnvironment,
    create_village_access_spec, validate_village_access_spec, village_access_subject_request, digest)


def world(**conditions):
    return VillageAccessEnvironment(create_village_access_spec(initial_conditions={
        'url_glitches': 'clean', 'permissions': 'team', 'sessions': 'authenticated', **conditions}), 17)


def act(env, agent, action):
    while env.next_agent != agent:
        if env.terminal: raise AssertionError('Fixture exhausted scheduled opportunities')
        env.step(env.next_agent, {'action': 'wait'})
    return env.step(agent, action)


def url(env, key, mode='view'):
    doc = env.documents[env.originals[key]]
    return f"https://village.local/{'forms' if doc['kind']=='form' else 'docs'}/{doc['id']}/{mode}"


class VillageAccessTests(unittest.TestCase):
    def test_seed_reset_and_note_arms_have_identical_exogenous_worlds(self):
        spec = create_village_access_spec()
        a = VillageAccessEnvironment(spec, 51); b = VillageAccessEnvironment(spec, 51)
        baseline = a.snapshot()
        for role in AGENTS: b.inject_context(role, 'A bounded assigned note.')
        other = b.snapshot()
        for key in ('documents', 'originals', 'required_content', 'references', 'browsers', 'schedule'):
            self.assertEqual(baseline[key], other[key])
        a.step(a.next_agent, {'action': 'wait'})
        self.assertEqual(a.reset(), baseline)
        self.assertNotEqual(VillageAccessEnvironment(spec, 52).originals, a.originals)

    def test_subject_identity_information_and_mutation_boundaries(self):
        env = world(); env.inject_context('auditor', 'Only this role receives this note.')
        before = env.snapshot(); request = village_access_subject_request(env, 'ethics_owner')
        self.assertEqual(request['context'], [])
        self.assertEqual(village_access_subject_request(env, 'auditor')['context'], ['Only this role receives this note.'])
        text = str(request)
        def keys(value):
            if isinstance(value, dict): return set(value) | set().union(*(keys(item) for item in value.values()))
            if isinstance(value, list): return set().union(*(keys(item) for item in value))
            return set()
        self.assertFalse({'source_grounding', 'privileged_failure_cause', 'schedule', 'seed', 'historical_role_source'} & keys(request))
        self.assertNotIn('canonical-reference-check instructions', text)
        self.assertEqual(env.agent_ids, AGENTS)
        self.assertFalse(any(role.startswith('d5fd') for role in env.agent_ids))
        request['observation']['project'][0]['required_content']['consent'] = 'MUTATED'
        request['action_schema']['properties']['action']['enum'].append('hack')
        self.assertEqual(env.snapshot(), before)

    def test_url_typo_and_acl_failure_same_404_independent_truth(self):
        missing = world(permissions='restricted')
        original = copy.deepcopy(missing.documents[missing.originals['irb-protocol']])
        typo = url(missing, 'irb-protocol').replace(original['id'], original['id'] + 'x')
        first = act(missing, 'auditor', {'action': 'open_url', 'url': typo})
        second = act(missing, 'auditor', {'action': 'open_url', 'url': url(missing, 'irb-protocol')})
        self.assertEqual(first, second)
        self.assertEqual(first['status_code'], 404)
        self.assertEqual(missing.documents[original['id']], original)
        causes = [e['privileged_failure_cause'] for e in missing.events if e['type']=='action' and not e['result']['ok']]
        self.assertEqual(causes, ['reference', 'permission'])
        obs = missing.observe('auditor')
        self.assertNotIn('permission', str(obs['your_last_tool_result']))

    def test_search_visibility_request_and_grant_have_no_automatic_access(self):
        env = world(permissions='restricted')
        self.assertEqual(act(env, 'auditor', {'action': 'drive_search', 'query': 'Irb Protocol'})['matches'], [])
        result = act(env, 'auditor', {'action': 'request_access', 'document_key': 'irb-protocol', 'role': 'viewer'})
        self.assertEqual(result['status'], 'pending')
        self.assertFalse(act(env, 'auditor', {'action': 'open_url', 'url': url(env, 'irb-protocol')})['ok'])
        self.assertEqual(env.observe('power_owner')['requests_to_you'], [])
        self.assertEqual(env.observe('ethics_owner')['requests_to_you'][0]['id'], result['request_id'])
        self.assertFalse(act(env, 'power_owner', {'action': 'grant_access', 'request_id': result['request_id']})['ok'])
        self.assertTrue(act(env, 'ethics_owner', {'action': 'grant_access', 'request_id': result['request_id']})['ok'])
        self.assertTrue(act(env, 'auditor', {'action': 'open_url', 'url': url(env, 'irb-protocol')})['ok'])
        doc = env.documents[env.originals['irb-protocol']]
        self.assertEqual(doc['acl']['auditor'], 'viewer')
        self.assertEqual(doc['content'], env.required_content['irb-protocol'])

    def test_pending_clipboard_and_address_bar_do_not_navigate(self):
        env = world()
        act(env, 'auditor', {'action': 'set_clipboard', 'text': url(env, 'irb-protocol')})
        act(env, 'auditor', {'action': 'paste_url'})
        obs = env.observe('auditor')
        self.assertEqual(obs['browser']['draft_url'], url(env, 'irb-protocol'))
        self.assertEqual(obs['browser']['committed_url'], '')
        self.assertIsNone(obs['browser']['document_id'])
        self.assertEqual(env.access_receipts, [])
        self.assertTrue(act(env, 'auditor', {'action': 'navigate'})['ok'])
        self.assertEqual(env.access_receipts[-1]['document_id'], env.originals['irb-protocol'])
        self.assertTrue(act(env, 'auditor', {'action': 'copy_current_url'})['ok'])
        self.assertEqual(env.observe('integrator')['your_clipboard'], '')

    def test_form_responder_editor_and_profile_are_distinct(self):
        env = world()
        act(env, 'stimuli_owner', {'action': 'switch_session', 'profile': 'incognito'})
        self.assertTrue(act(env, 'stimuli_owner', {'action': 'open_url', 'url': url(env, 'participant-form', 'respond')})['ok'])
        self.assertTrue(act(env, 'stimuli_owner', {'action': 'inspect_document'})['ok'])
        self.assertEqual(act(env, 'stimuli_owner', {'action': 'open_url', 'url': url(env, 'participant-form', 'edit')})['status_code'], 401)
        act(env, 'stimuli_owner', {'action': 'switch_session', 'profile': 'authenticated'})
        self.assertTrue(act(env, 'stimuli_owner', {'action': 'open_url', 'url': url(env, 'participant-form', 'edit')})['ok'])
        self.assertEqual(env.observe('stimuli_owner')['browser']['active_profile'], 'authenticated')

    def test_viewer_or_responder_endpoint_cannot_edit_even_owner(self):
        env = world(); original = env.originals['irb-protocol']
        act(env, 'ethics_owner', {'action': 'open_url', 'url': url(env, 'irb-protocol')})
        result = act(env, 'ethics_owner', {'action': 'edit_document', 'expected_version': 1, 'content': {'claim': 'changed'}})
        self.assertFalse(result['ok']); self.assertEqual(env.documents[original]['version'], 1)
        act(env, 'ethics_owner', {'action': 'open_url', 'url': url(env, 'irb-protocol', 'edit')})
        self.assertTrue(act(env, 'ethics_owner', {'action': 'edit_document', 'expected_version': 1, 'content': {'claim': 'changed'}})['ok'])

    def test_version_conflict_restore_and_old_read_receipt_not_final_version(self):
        env = world(); key = 'irb-protocol'; original = copy.deepcopy(env.documents[env.originals[key]]['content'])
        act(env, 'auditor', {'action': 'open_url', 'url': url(env, key)})
        act(env, 'auditor', {'action': 'inspect_document'})
        act(env, 'ethics_owner', {'action': 'open_url', 'url': url(env, key, 'edit')})
        act(env, 'ethics_owner', {'action': 'edit_document', 'expected_version': 1, 'content': {'changed': 'wrong'}})
        state = copy.deepcopy(env.documents[env.originals[key]])
        self.assertFalse(act(env, 'ethics_owner', {'action': 'edit_document', 'expected_version': 1, 'content': original})['ok'])
        self.assertEqual(env.documents[env.originals[key]], state)
        self.assertTrue(act(env, 'ethics_owner', {'action': 'restore_version', 'expected_version': 2, 'restore_version': 1})['ok'])
        final = env.documents[env.originals[key]]
        self.assertEqual(final['version'], 3); self.assertEqual(final['content'], original)
        outcome = next(row for row in env.evaluate()['per_document'] if row['document_key']==key)
        self.assertTrue(outcome['content_correct']); self.assertFalse(outcome['checker_opened_current_version'])
        self.assertFalse(outcome['checker_inspected_current_version'])

    def test_revocation_rechecks_cached_document_permission(self):
        env = world()
        act(env, 'auditor', {'action': 'open_url', 'url': url(env, 'irb-protocol')})
        act(env, 'ethics_owner', {'action': 'revoke_access', 'document_id': env.originals['irb-protocol'], 'recipient': 'auditor'})
        self.assertFalse(act(env, 'auditor', {'action': 'inspect_document'})['ok'])
        self.assertFalse(next(row for row in env.evaluate()['per_document'] if row['document_key']=='irb-protocol')['checker_current_profile_authorized'])

    def test_recreate_keeps_original_identity_content_and_objective(self):
        env = world(); before = copy.deepcopy(env.documents[env.originals['irb-protocol']])
        result = act(env, 'coordinator', {'action': 'recreate_document', 'document_key': 'irb-protocol',
            'title': 'Backup IRB', 'content': env.required_content['irb-protocol']})
        self.assertNotEqual(result['created_document_id'], before['id']); self.assertFalse(result['original_replaced'])
        self.assertEqual(env.documents[before['id']], before)
        self.assertEqual(env.evaluate()['avoidable_recreations'], 1)
        self.assertEqual(env.evaluate()['success'], 0)

    def test_communication_scoped_and_reports_do_not_complete_tasks(self):
        env = world(); act(env, 'ethics_owner', {'action': 'send_message', 'recipient': 'auditor', 'message': 'A reported claim.'})
        self.assertEqual(len(env.observe('auditor')['received_messages']), 1)
        self.assertEqual(env.observe('integrator')['received_messages'], [])
        act(env, 'ethics_owner', {'action': 'send_message', 'recipient': 'all', 'message': 'Declared experimental-room post.'})
        self.assertEqual(len(env.observe('integrator')['received_messages']), 1)
        result = act(env, 'coordinator', {'action': 'report_status', 'document_key': 'kickoff', 'status': 'completed', 'summary': 'Everything is ready.'})
        self.assertFalse(result['oracle_verified']); self.assertEqual(env.evaluate()['completed_tasks'], 0)

    def test_independent_preparation_is_legal_while_blocked(self):
        env = world(permissions='restricted', sessions='incognito')
        result = act(env, 'auditor', {'action': 'draft_local_document', 'document_key': 'irb-protocol', 'content': {'notes': 'Preparation while access is pending.'}})
        self.assertTrue(result['ok']); self.assertFalse(result['shared_document_changed'])
        self.assertEqual(env.observe('integrator')['your_local_drafts'], {})
        self.assertEqual(env.evaluate()['completed_tasks'], 0)

    def test_invalid_actions_consume_one_fixed_opportunity_no_world_mutation(self):
        for action in (None, [], {'action': 'edit_document', 'expected_version': True, 'content': {}},
            {'action': 'send_message', 'recipient': 'unknown', 'message': 'No'}, {'action': 'wait', 'extra': 'bad'},
            {'action': 'open_url', 'url': float('nan')}, {'action': 'hack', 'seed': 1}):
            env = world(); old_docs = copy.deepcopy(env.documents); old_schedule = list(env.schedule)
            result = env.step(env.next_agent, action)
            self.assertFalse(result['ok']); self.assertEqual(env.step_count, 1)
            self.assertEqual(env.documents, old_docs); self.assertEqual(env.schedule, old_schedule)
            self.assertEqual(len(env.events), 1)
            json.dumps(env.snapshot(), allow_nan=False)

    def test_oracle_access_opening_inspection_and_comprehension_are_distinct(self):
        env = world()
        self.assertEqual(env.evaluate()['oracle_usable_project'], 1)
        self.assertEqual(env.evaluate()['verified_usable_project'], 0)
        self.assertEqual(env.evaluate()['current_version_inspection_coverage'], 0)
        queues = {'auditor': [('irb-protocol', 'open'), ('stimuli', 'open')],
            'integrator': [('power-calculations', 'open'), ('kickoff', 'open')]}
        while not env.terminal:
            agent = env.next_agent
            if queues.get(agent):
                key, _ = queues[agent].pop(0); env.step(agent, {'action': 'open_url', 'url': url(env, key)})
            else: env.step(agent, {'action': 'wait'})
        result = env.evaluate()
        self.assertEqual(result['success'], 1); self.assertEqual(result['completed_tasks'], 4)
        self.assertEqual(result['current_version_inspection_coverage'], 0)
        self.assertNotIn('understood', result)

    def test_all_documents_can_be_opened_inspected_and_fixed_without_recreation(self):
        for seed in (0, 8, 31):
            spec = create_village_access_spec(initial_conditions={'url_glitches': 'mismatched',
                'permissions': 'restricted', 'sessions': 'authenticated', 'content': 'missing_section'})
            env = VillageAccessEnvironment(spec, seed); queues = {}
            for key, owner in spec['task']['owners'].items():
                queues[owner] = [{'action': 'open_url', 'url': url(env, key, 'edit')},
                    {'action': 'edit_document', 'expected_version': 1, 'content': env.required_content[key]},
                    {'action': 'share_document', 'document_id': env.originals[key], 'audience': 'team', 'recipient': 'none', 'role': 'viewer'}]
            queues['auditor'] = [*({'action': 'wait'} for _ in range(3)),
                {'action': 'open_url', 'url': url(env, 'irb-protocol')}, {'action': 'inspect_document'},
                {'action': 'open_url', 'url': url(env, 'stimuli')}, {'action': 'inspect_document'}]
            queues['integrator'] = [*({'action': 'wait'} for _ in range(3)),
                {'action': 'open_url', 'url': url(env, 'power-calculations')}, {'action': 'inspect_document'},
                {'action': 'open_url', 'url': url(env, 'kickoff')}, {'action': 'inspect_document'}]
            while not env.terminal:
                agent = env.next_agent
                env.step(agent, queues[agent].pop(0) if queues[agent] else {'action': 'wait'})
            outcome = env.evaluate()
            self.assertEqual(outcome['success'], 1, outcome)
            self.assertEqual(outcome['current_version_inspection_coverage'], 1)
            self.assertEqual(outcome['avoidable_recreations'], 0)

    def test_spec_types_and_resealed_unsupported_claims_fail(self):
        for field, value in [('max_rounds', True), ('max_rounds', 10.0), ('kind', 'full_google_browser_replay')]:
            spec = create_village_access_spec(); spec[field] = value
            with self.assertRaises(ValueError): validate_village_access_spec(spec)
        spec = create_village_access_spec(); spec['agent_profiles']['auditor']['historical_role_source']['model_reproduced'] = 0
        with self.assertRaises(ValueError): validate_village_access_spec(spec)
        with self.assertRaises(ValueError): create_village_access_spec(initial_conditions={'automatic_acl_grant': True})
        with self.assertRaises(ValueError): VillageAccessEnvironment(create_village_access_spec(), True)

    def test_trace_reset_replay_uses_actions_not_reports_or_future(self):
        env = world(); initial = env.snapshot()
        for _ in range(9): env.step(env.next_agent, {'action': 'wait'})
        trace = copy.deepcopy(env.events)
        replay = world()
        for event in trace:
            self.assertEqual(replay.step(event['agent_id'], event['action']), event['result'])
        self.assertEqual(replay.snapshot(), env.snapshot())
        self.assertEqual(replay.reset(), initial)

    def test_retained_invalid_output_replays_identically(self):
        for value in ({'action': 'open_url', 'url': float('nan')}, {'action': 'open_url', 'url': 'x' * 16001}):
            env = world(); env.step(env.next_agent, value); event = env.events[-1]
            self.assertEqual(event['action'], {'invalid_output': 'nonfinite_or_unbounded_action'})
            replay = world()
            self.assertEqual(replay.step(event['agent_id'], event['action']), event['result'])
            self.assertEqual(replay.snapshot(), env.snapshot())

    def test_exogenous_domains_do_not_depend_on_each_other_or_actions(self):
        baseline = world(url_glitches='clean', permissions='team', sessions='authenticated')
        variant = world(url_glitches='mismatched', permissions='restricted', sessions='incognito')
        for key in ('required_content', 'originals', 'schedule'):
            self.assertEqual(getattr(baseline, key), getattr(variant, key))
        for identity in baseline.documents:
            self.assertEqual(baseline.documents[identity]['content'], variant.documents[identity]['content'])
        for _ in range(8):
            baseline.step(baseline.next_agent, {'action': 'wait'})
            variant.step(variant.next_agent, {'action': 'open_url', 'url': 'https://village.local/docs/unknown/view'})
        self.assertEqual(baseline.schedule, variant.schedule)
        self.assertEqual(baseline.required_content, variant.required_content)

    def test_public_grant_and_revoke_reversible_without_document_mutation(self):
        env = world(); identity = env.originals['irb-protocol']; initial = copy.deepcopy(env.documents[identity])
        act(env, 'auditor', {'action': 'switch_session', 'profile': 'incognito'})
        self.assertFalse(act(env, 'auditor', {'action': 'open_url', 'url': url(env, 'irb-protocol')})['ok'])
        act(env, 'ethics_owner', {'action': 'share_document', 'document_id': identity, 'audience': 'anyone', 'recipient': 'none', 'role': 'viewer'})
        self.assertTrue(act(env, 'auditor', {'action': 'open_url', 'url': url(env, 'irb-protocol')})['ok'])
        act(env, 'ethics_owner', {'action': 'revoke_access', 'document_id': identity, 'recipient': 'anyone'})
        self.assertFalse(act(env, 'auditor', {'action': 'inspect_document'})['ok'])
        self.assertEqual(env.documents[identity], initial)

    def test_session_tabs_are_separate_and_clipboard_copy_requires_loaded_url(self):
        env = world()
        self.assertFalse(act(env, 'auditor', {'action': 'copy_current_url'})['ok'])
        act(env, 'auditor', {'action': 'open_url', 'url': url(env, 'irb-protocol')})
        authenticated = copy.deepcopy(env.observe('auditor')['browser'])
        act(env, 'auditor', {'action': 'switch_session', 'profile': 'incognito'})
        self.assertEqual(env.observe('auditor')['browser']['committed_url'], '')
        act(env, 'auditor', {'action': 'type_url', 'url': url(env, 'stimuli')})
        act(env, 'auditor', {'action': 'switch_session', 'profile': 'authenticated'})
        self.assertEqual(env.observe('auditor')['browser'], authenticated)


if __name__ == '__main__': unittest.main()
