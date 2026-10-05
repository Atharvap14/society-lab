"""CPU contract checks of the optional relay world, not a subject experiment."""
import copy
import json
import unittest


from swarm_lab import revision_relay_env as relay


class IndependentRevisionRelayTests(unittest.TestCase):
    def world(self, seed=31, timing='late', bypass='sham'):
        return relay.create_revision_relay_environment(seed=seed, timing=timing, bypass=bypass)

    def advance_to_final(self, env, draft=None):
        env.step('B', {'action': 'wait'})
        env.step('C', draft or {'action': 'wait'})
        env.step('B', {'action': 'wait'})
        self.assertEqual(env.next_agent, 'C')

    def finish_waiting(self, env):
        while not env.terminal:
            env.step(env.next_agent, {'action': 'wait'})

    def test_paired_truth_contacts_and_final_B_inventory_are_action_independent(self):
        contacts = [('A', 'B', 0), ('A', 'B', 1), ('B', 'C', 2),
                    ('A', 'B', 4), ('B', 'C', 5), ('A', 'C', 6)]
        for seed in range(12):
            truths = []
            for timing in relay.TIMINGS:
                for bypass in relay.BYPASSES:
                    env = self.world(seed, timing, bypass)
                    initial = env.snapshot()
                    truths.append((initial['source_records'], initial['C_private_residue'],
                                   initial['oracle_total']))
                    env.step('B', None)  # Invalid behavior still dispatches the empty B slot.
                    env.step('C', {'action': 'wait'})
                    self.assertEqual({row['record_id'] for row in env.observe('B')['known_records']},
                                     {'source-record-01', 'source-record-02', 'source-record-03'})
                    env.step('B', {'action': 'wait'})
                    env.step('C', {'action': 'wait'})
                    final = env.snapshot()
                    self.assertEqual([(row['sender'], row['recipient'], row['ordinal_boundary'])
                                      for row in final['deliveries']], contacts)
                    self.assertEqual(final['turn_counts'], {'B': 2, 'C': 2})
                    self.assertEqual(final['step_count'], 4)
                    self.assertEqual(final['source_records'], initial['source_records'])
            self.assertTrue(all(truth == truths[0] for truth in truths))

    def test_malformed_B_actions_consume_one_turn_and_no_partial_forward(self):
        attacks = [None, {}, {'action': 'unknown'},
                   {'action': 'forward', 'record_ids': ['source-record-02'], 'message': 'future'},
                   {'action': 'forward', 'record_ids': [], 'message': 'x' * 257},
                   {'action': 'forward', 'record_ids': ['source-record-01'], 'message': '', 'recipient': 'C'},
                   {'action': 'forward', 'record_ids': ['source-record-01', 'source-record-03'], 'message': ''},
                   {'action': 'forward', 'record_ids': [], 'message': float('nan')}]
        nested = 'x'
        for _ in range(20):
            nested = [nested]
        attacks.append(nested)
        for action in attacks:
            with self.subTest(action_type=type(action).__name__):
                env = self.world()
                before = env.snapshot()['source_records']
                result = env.step('B', action)
                self.assertIs(result['ok'], False)
                self.assertEqual(env.next_agent, 'C')
                self.assertEqual(env.snapshot()['step_count'], 1)
                delivery = env.snapshot()['deliveries'][-1]
                self.assertEqual(delivery['ordinal_boundary'], 2)
                self.assertEqual(delivery['records'], [])
                self.assertEqual(delivery['message'], '')
                self.assertTrue(delivery['empty_outbox'])
                self.assertEqual(env.snapshot()['source_records'], before)

    def test_unretained_invalid_output_replays_exact_result_and_complete_state(self):
        cyclic = []
        cyclic.append(cyclic)
        attacks = [float('nan'), float('inf'), object(), '\ud800', cyclic,
                   {'action': 'forward', 'record_ids': [], 'message': '\u03bb' * 3000}]
        for timing in relay.TIMINGS:
            for bypass in relay.BYPASSES:
                for bad_action in attacks:
                    env = self.world(timing=timing, bypass=bypass)
                    result = env.step('B', bad_action)
                    self.assertEqual(result, {'ok': False, 'error': 'Action is not bounded finite JSON'})
                    env.step('C', {'action': 'draft', 'revision': 1, 'total': 0})
                    env.step('B', {'action': 'wait'})
                    env.step('C', {'action': 'retain'})
                    saved = env.snapshot()
                    events = [event for event in saved['events'] if event['type'] == 'action']
                    self.assertEqual(events[0]['action'], relay.INVALID_RETAINED_ACTION)
                    # Retained sentinel establishes invalid-output equivalence; original bytes are unknown.
                    json.dumps(saved, allow_nan=False)
                    replayed = self.world(timing=timing, bypass=bypass)
                    for event in events:
                        self.assertEqual(replayed.step(event['agent_id'], event['action']), event['result'])
                    self.assertEqual(relay.fingerprint(replayed.snapshot()), relay.fingerprint(saved))
                    self.assertEqual(replayed.evaluate(), env.evaluate())

    def test_wrong_host_role_and_post_terminal_calls_do_not_mutate(self):
        env = self.world()
        before = env.snapshot()
        for role in ('A', 'C', None, True):
            with self.assertRaises(ValueError):
                env.step(role, {'action': 'wait'})
            self.assertEqual(env.snapshot(), before)
        self.finish_waiting(env)
        terminal = env.snapshot()
        with self.assertRaises(RuntimeError):
            env.step('C', {'action': 'wait'})
        self.assertEqual(env.snapshot(), terminal)

    def test_source_only_script_has_legal_success_route_in_all_four_cells(self):
        for seed in range(20):
            for timing in relay.TIMINGS:
                for bypass in relay.BYPASSES:
                    env = self.world(seed, timing, bypass)
                    while not env.terminal:
                        role = env.next_agent
                        observation = env.observe(role)
                        if role == 'B':
                            latest = [row for row in observation['known_records']
                                      if row['artifact_id'] == 'artifact-main' and row['revision'] == 2]
                            action = {'action': 'forward',
                                      'record_ids': [latest[0]['record_id']] if latest else [],
                                      'message': ''}
                        elif observation['decision_phase'] == 'draft':
                            action = {'action': 'wait'}
                        else:
                            latest = next(row for row in observation['known_records']
                                          if row['artifact_id'] == 'artifact-main' and row['revision'] == 2)
                            action = {'action': 'revise', 'revision': 2,
                                      'total': (latest['value'] + observation['your_private_residue']) % 97}
                        self.assertTrue(env.step(role, action)['ok'])
                    self.assertEqual(env.evaluate()['C_final_correct'], 1)

    def test_correct_guess_scores_without_revision2_receipt(self):
        env = self.world()
        self.advance_to_final(env)
        request = relay.revision_relay_subject_request(env, 'C')
        self.assertNotIn('source-record-02',
                         {row['record_id'] for row in request['observation']['known_records']})
        # Privileged host oracle constructs a logical scoring witness, not an agent policy.
        guess = env.snapshot()['oracle_total']
        self.assertTrue(env.step('C', {'action': 'revise', 'revision': 2, 'total': guess})['ok'])
        outcome = env.evaluate()
        self.assertEqual(outcome['C_final_correct'], 1)
        self.assertFalse(outcome['canonical_revision2_visible_to_C'])
        self.assertFalse(outcome['correctness_requires_canonical_receipt'])

    def test_invalid_or_waiting_final_never_silently_carries_correct_draft(self):
        for final in ({'action': 'wait'}, None, {'action': 'draft', 'revision': 2, 'total': 0},
                      {'action': 'revise', 'revision': True, 'total': 0},
                      {'action': 'revise', 'revision': 2, 'total': 0.0}):
            env = self.world()
            correct = env.snapshot()['oracle_total']
            self.advance_to_final(env, {'action': 'draft', 'revision': 2, 'total': correct})
            env.step('C', final)
            self.assertIsNone(env.evaluate()['C_final_answer'])
            self.assertEqual(env.evaluate()['C_final_correct'], 0)
        env = self.world()
        correct = env.snapshot()['oracle_total']
        self.advance_to_final(env, {'action': 'draft', 'revision': 2, 'total': correct})
        self.assertTrue(env.step('C', {'action': 'retain'})['ok'])
        self.assertEqual(env.evaluate()['C_final_correct'], 1)

    def test_wrong_revision_is_valid_report_with_zero_score_and_no_feedback(self):
        env = self.world()
        self.advance_to_final(env)
        total = env.snapshot()['oracle_total']
        result = env.step('C', {'action': 'revise', 'revision': 1, 'total': total})
        self.assertEqual(result, {'ok': True, 'final_recorded': True})
        self.assertEqual(env.evaluate()['C_final_correct'], 0)
        self.assertTrue(env.evaluate()['C_final_answer_present'])

    def test_canonical_hash_and_hop_lineage_do_not_mutate_original_record(self):
        env = self.world(timing='early', bypass='informative')
        initial = env.snapshot()['source_records']['source-record-02']
        env.step('B', {'action': 'forward', 'record_ids': ['source-record-02'], 'message': ''})
        record = env.observe('C')['known_records'][0]
        core = {key: record[key] for key in
                ('record_id', 'artifact_id', 'revision', 'value', 'origin_id', 'source_role')}
        self.assertEqual(record['record_sha256'], relay.fingerprint(core))
        self.assertEqual([(hop['sender'], hop['recipient'], hop['ordinal_boundary'])
                          for hop in record['lineage']], [('A', 'B', 1), ('B', 'C', 2)])
        env.step('C', {'action': 'wait'})
        env.step('B', {'action': 'forward', 'record_ids': ['source-record-02'], 'message': ''})
        copies = [record for delivery in env.observe('C')['received_deliveries']
                  for record in delivery['records'] if record['record_id'] == 'source-record-02']
        self.assertEqual(len(copies), 3)
        self.assertEqual(copies[-1]['lineage'][0]['sender'], 'A')
        self.assertEqual(copies[-1]['lineage'][0]['recipient'], 'C')
        self.assertEqual(env.snapshot()['source_records']['source-record-02'], initial)

    def test_public_packets_and_external_objects_are_defensive_copies(self):
        spec = relay.create_revision_relay_spec()
        env = relay.create_revision_relay_environment(spec=spec)
        baseline = env.snapshot()
        spec['caps']['subject_decisions'] = 999
        copied_spec = env.spec
        copied_spec['modulus'] = 2
        observation = env.observe('B')
        observation['known_records'][0]['value'] = 1234
        observation['received_deliveries'].clear()
        snapshot = env.snapshot()
        snapshot['source_records'].clear()
        request = relay.revision_relay_subject_request(env, 'B')
        request['observation']['known_records'].clear()
        request['action_schema']['oneOf'].clear()
        self.assertEqual(env.snapshot(), baseline)
        action = {'action': 'forward', 'record_ids': [], 'message': 'original'}
        result = env.step('B', action)
        action['message'] = 'mutated'
        result['ok'] = False
        self.assertTrue(env.observe('B')['your_last_tool_result']['ok'])
        self.assertEqual(env.snapshot()['deliveries'][-1]['message'], 'original')

    def test_private_C_fields_and_context_never_reach_B(self):
        env = self.world()
        env.inject_context('C', 'PRIVATE_C_TEST_SENTINEL')
        self.assertNotIn('PRIVATE_C_TEST_SENTINEL', json.dumps(env.observe('B')))
        self.assertNotIn('your_private_residue', env.observe('B'))
        self.assertNotIn('your_draft', env.observe('B'))
        self.assertNotIn('your_final_answer', env.observe('B'))
        env.step('B', {'action': 'wait'})
        env.step('C', {'action': 'draft', 'revision': 1, 'total': 0,
                       'rationale': 'PRIVATE_C_TEST_SENTINEL'})
        self.assertNotIn('PRIVATE_C_TEST_SENTINEL', json.dumps(env.observe('B')))

    def test_requests_withhold_privileged_control_and_future_hashes(self):
        env = self.world()
        future_hash = env.snapshot()['source_records']['source-record-02']['record_sha256']
        request = relay.revision_relay_subject_request(env, 'B')
        self.assertNotIn(future_hash, json.dumps(request))
        self.assertEqual({record['record_id'] for record in request['observation']['known_records']},
                         {'source-record-01', 'source-record-03'})
        self.assertEqual(set(request), {'agent_id', 'observation', 'action_schema'})
        forbidden = {'seed', 'assignment', 'timing', 'bypass', 'oracle_total',
                     'C_private_residue', 'source_records', 'spec_hash'}
        def check(value):
            if isinstance(value, dict):
                self.assertFalse(set(value) & forbidden)
                for child in value.values():
                    check(child)
            elif isinstance(value, list):
                for child in value:
                    check(child)
        while not env.terminal:
            check(relay.revision_relay_subject_request(env, env.next_agent))
            env.step(env.next_agent, {'action': 'wait'})

    def test_context_bounds_reset_and_strict_spec_identity(self):
        env = self.world()
        initial = env.snapshot()
        env.inject_context('B', 'one')
        env.inject_context('B', 'two')
        with self.assertRaises(ValueError):
            env.inject_context('B', 'three')
        self.assertEqual(env.observe('C')['your_private_context'], [])
        self.assertEqual(env.reset(), initial)
        self.finish_waiting(env)
        with self.assertRaises(RuntimeError):
            env.inject_context('B', 'after terminal')
        self.assertEqual(env.reset(), initial)
        for seed in (True, 0.0, -1):
            with self.assertRaises(ValueError):
                self.world(seed)
        for value in (True, 'unknown'):
            with self.assertRaises(ValueError):
                self.world(timing=value)
            with self.assertRaises(ValueError):
                self.world(bypass=value)
        altered = relay.create_revision_relay_spec()
        altered['caps']['subject_decisions'] = 4.0
        with self.assertRaises(ValueError):
            relay.validate_revision_relay_spec(altered)


if __name__ == '__main__':
    unittest.main()
