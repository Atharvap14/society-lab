"""Independent CPU-only checks of the staged relay runner; no registry/model calls."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


from swarm_lab import revision_relay_experiments as runner
MODULE_PATH=Path(runner.__file__)
CALLBACK = {'harness': 'callback', 'model': 'fixture', 'generation': {
    'max_output_tokens': 600, 'temperature': 'provider_default', 'sampling_seed': 'not_set'}}


class IndependentRelayRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = runner.create_revision_relay_protocol(blocks=2, seed=241)
        cls.report = runner.run_revision_relay_experiment(cls.protocol)

    def reseal(self, body, key='report_hash'):
        return runner._seal(body, key)

    def rejects_report(self, modified):
        proof = runner.replay_revision_relay_report(self.reseal(modified))
        self.assertIs(proof['passed'], False, proof)
        return proof

    def partial(self, fail_on_call=5):
        protocol = runner.create_revision_relay_protocol(blocks=2, seed=319, subject_backend=CALLBACK)
        calls = 0
        def policy(request):
            nonlocal calls
            calls += 1
            if calls == fail_on_call:
                raise RuntimeError('test-only invocation failure')
            return runner.revision_relay_scoped_policy(request)
        with self.assertRaises(runner.RevisionRelayExecutionError) as caught:
            runner.run_revision_relay_experiment(protocol, policy)
        return protocol, caught.exception.partial_report, calls

    def test_complete_pilot_grid_pairing_and_unavailable_inference(self):
        report = self.report
        self.assertEqual(len(report['runs']), 8)
        self.assertTrue(all(row['status'] == 'complete' for row in report['runs']))
        self.assertEqual(sum(row['counts']['applied_actions'] for row in report['runs']), 32)
        self.assertEqual(report['model_calls'], 0)
        for block in ('block-0001', 'block-0002'):
            rows = [row for row in report['runs'] if row['block_id'] == block]
            self.assertEqual({(row['timing'], row['bypass']) for row in rows}, set(runner.CELLS))
            self.assertEqual(len({row['environment_seed'] for row in rows}), 1)
            self.assertTrue(all(row['exogenous_identity'] == rows[0]['exogenous_identity'] for row in rows))
        analysis = report['analysis']
        self.assertEqual(analysis['mean_interaction'], 0)
        self.assertEqual([row['difference'] for row in analysis['block_contrasts']], [0, 0])
        self.assertIsNone(analysis['p_value'])
        self.assertIsNone(analysis['interaction_randomization_test'])
        self.assertIs(analysis['interval']['available'], False)
        self.assertIsNone(analysis['interval']['bounds'])
        self.assertEqual(analysis['parameter_range'], [-2, 2])
        self.assertIs(runner.replay_revision_relay_report(report)['passed'], True)

    def test_exact_requests_empty_context_and_fixed_contacts(self):
        contacts = [('A', 'B', 0), ('A', 'B', 1), ('B', 'C', 2),
                    ('A', 'B', 4), ('B', 'C', 5), ('A', 'C', 6)]
        forbidden = {'seed', 'assignment', 'timing', 'bypass', 'oracle_total', 'source_records', 'spec_hash'}
        def scoped(value):
            if type(value) is dict:
                self.assertFalse(set(value) & forbidden)
                for child in value.values():
                    scoped(child)
            elif type(value) is list:
                for child in value:
                    scoped(child)
        for row in self.report['runs']:
            self.assertEqual([(event['sender'], event['recipient'], event['ordinal_boundary'])
                              for event in row['final_state']['deliveries']], contacts)
            self.assertEqual(row['final_state']['contexts'], {'B': [], 'C': []})
            for receipt, turn in zip(row['boundaries'], row['turns']):
                self.assertEqual(receipt['request_hash'], runner._hash(receipt['request']))
                self.assertEqual(turn['request_hash'], receipt['request_hash'])
                self.assertEqual(receipt['invocation_status'], 'returned')
                self.assertIs(receipt['action_applied'], True)
                self.assertEqual(receipt['request']['observation']['your_private_context'], [])
                scoped(receipt['request'])

    def test_guessed_exact_answer_without_receipt_is_complete_scored_outcome(self):
        protocol = runner.create_revision_relay_protocol(blocks=1, seed=257, subject_backend=CALLBACK)
        assignments = runner.randomize_revision_relay_runs(protocol)
        calls = 0
        def logical_oracle_witness(request):
            nonlocal calls
            unit = assignments[calls // 4]
            calls += 1
            if request['agent_id'] == 'B' or request['observation']['decision_phase'] == 'draft':
                return {'action': 'wait'}
            # Host knowledge deliberately builds a scoring witness, never an empirical subject policy.
            oracle = runner._environment(protocol, unit).snapshot()['oracle_total']
            return {'action': 'revise', 'revision': 2, 'total': oracle}
        report = runner.run_revision_relay_experiment(protocol, logical_oracle_witness)
        self.assertEqual(calls, 16)
        for row in report['runs']:
            self.assertEqual(row['outcomes']['C_final_correct'], 1)
            if row['bypass'] == 'sham':
                self.assertIs(row['outcomes']['canonical_revision2_visible_to_C'], False)
        self.assertIs(runner.replay_revision_relay_report(report)['passed'], True)

    def test_nonfinite_callbacks_consume_opportunities_and_replay_retained_marker(self):
        protocol = runner.create_revision_relay_protocol(blocks=1, seed=261, subject_backend=CALLBACK)
        def policy(request):
            return float('nan') if request['agent_id'] == 'B' else {'action': 'wait'}
        report = runner.run_revision_relay_experiment(protocol, policy)
        for row in report['runs']:
            self.assertEqual(row['counts']['applied_actions'], 4)
            self.assertEqual(row['outcomes']['C_final_correct'], 0)
            for turn in row['turns'][::2]:
                self.assertEqual(turn['action'], runner.world.INVALID_RETAINED_ACTION)
                self.assertIs(turn['tool_result']['ok'], False)
                self.assertIsNone(turn['action_retention']['original_output_hash'])
        json.dumps(report, allow_nan=False)
        self.assertIs(runner.replay_revision_relay_report(report)['passed'], True)

    def test_backend_substitutions_fail_before_invocation(self):
        calls = []
        def policy(request):
            calls.append(request)
            return {'action': 'wait'}
        with self.assertRaises(ValueError):
            runner.run_revision_relay_experiment(self.protocol, policy)
        callback_protocol = runner.create_revision_relay_protocol(subject_backend=CALLBACK)
        with self.assertRaises(ValueError):
            runner.run_revision_relay_experiment(callback_protocol)
        wrong = copy.deepcopy(CALLBACK)
        wrong['model'] = 'changed'
        with self.assertRaises(ValueError):
            runner.run_revision_relay_experiment(callback_protocol, policy, backend_metadata=wrong)
        responses = {**CALLBACK, 'harness': 'responses',
                     'harness_adapter_hash': runner.revision_relay_code_hashes()['harness.py']}
        live_protocol = runner.create_revision_relay_protocol(subject_backend=responses)
        with self.assertRaises(ValueError):
            runner.run_revision_relay_experiment(live_protocol, policy)
        self.assertEqual(calls, [])

    def test_factory_defaults_do_not_accept_false_or_empty_typed_flags(self):
        for argument, value in [('subject_backend', False), ('subject_backend', {}),
                                ('source_refs', False), ('source_refs', []),
                                ('interval_assumptions', False), ('interval_assumptions', {})]:
            with self.subTest(argument=argument, value=value), self.assertRaises(ValueError):
                runner.create_revision_relay_protocol(**{argument: value})
        for bad_version in (True, 1.0, 0, None):
            with self.assertRaises(ValueError):
                runner.create_revision_relay_protocol(source_refs={'dataset': {
                    'id': 'fixture', 'version': bad_version, 'hash': 'a' * 64}})

    def test_resealed_generated_protocol_types_cannot_change(self):
        changes = [('design', 'maximum_subject_calls', 32.0), ('design', 'maximum_teams', 8.0),
                   ('design', 'blocks', True), ('design', 'seed', 241.0),
                   ('request_contract', 'private_context_insertion', 0),
                   ('bounds', 'json_depth', 32.0), ('measurement', 'range', [-2.0, 2])]
        for section, key, value in changes:
            modified = copy.deepcopy(self.protocol)
            modified[section][key] = value
            with self.subTest(section=section, key=key), self.assertRaises(ValueError):
                runner.validate_revision_relay_protocol(self.reseal(modified, 'protocol_hash'))

    def test_current_code_guard_prevents_work_and_fresh_replay(self):
        wrong = runner.revision_relay_code_hashes()
        wrong['revision_relay_env.py'] = '0' * 64
        with patch.object(runner, 'revision_relay_code_hashes', return_value=wrong):
            with self.assertRaises(ValueError):
                runner.run_revision_relay_experiment(self.protocol)
            self.assertIs(runner.replay_revision_relay_report(self.report)['passed'], False)

    def test_resealed_top_level_declarations_and_backend_cannot_change(self):
        for key, value in [('api_version', 'future'), ('study_kind', 'other'),
                           ('model_calls', False), ('maximum_subject_calls', 32.0),
                           ('local_artifacts_before_subject_calls', 0)]:
            modified = copy.deepcopy(self.report)
            modified[key] = value
            with self.subTest(key=key):
                self.rejects_report(modified)
        modified = copy.deepcopy(self.report)
        modified['backend']['metadata']['model'] = 'other'
        self.rejects_report(modified)

    def test_completed_world_cannot_drop_initial_materialization(self):
        modified = copy.deepcopy(self.report)
        modified['runs'][0]['initial_state'] = None
        modified['runs'][0]['exogenous_identity'] = None
        self.rejects_report(modified)

    def test_scoped_receipts_retention_or_oracle_tampering_rejects(self):
        variants = []
        modified = copy.deepcopy(self.report)
        modified['runs'][0]['boundaries'][0]['request']['observation']['your_private_context'] = ['injected']
        variants.append(modified)
        modified = copy.deepcopy(self.report)
        modified['runs'][0]['turns'][0]['action_retention']['status'] = 'invented'
        modified['runs'][0]['boundaries'][0]['action_retention']['status'] = 'invented'
        variants.append(modified)
        modified = copy.deepcopy(self.report)
        for trace in ('turns', 'boundaries'):
            modified['runs'][0][trace][0]['action_retention']['original_output_hash'] = False
        variants.append(modified)
        modified = copy.deepcopy(self.report)
        for trace in ('turns', 'boundaries'):
            modified['runs'][0][trace][0]['action_retention']['original_output_hash'] = '0' * 64
        variants.append(modified)
        modified = copy.deepcopy(self.report)
        modified['runs'][0]['outcomes']['C_final_correct'] = True
        variants.append(modified)
        modified = copy.deepcopy(self.report)
        modified['runs'][0]['outcomes']['oracle_total'] = (modified['runs'][0]['outcomes']['oracle_total'] + 1) % 97
        variants.append(modified)
        for modified in variants:
            self.rejects_report(modified)

    def test_assignment_pairing_and_analysis_cannot_be_resealed_to_other_evidence(self):
        modified = copy.deepcopy(self.report)
        modified['assignments'][0]['slot'] = 0.0
        modified['runs'][0]['slot'] = 0.0
        self.rejects_report(modified)
        modified = copy.deepcopy(self.report)
        modified['runs'][0]['exogenous_identity']['oracle_total'] = (modified['runs'][0]['exogenous_identity']['oracle_total'] + 1) % 97
        self.rejects_report(modified)
        for key, value in [('mean_interaction', 1.0), ('p_value', 0.01), ('block_contrasts', []),
                           ('interval', {'available': True, 'bounds': [0, 0]})]:
            modified = copy.deepcopy(self.report)
            modified['analysis'][key] = value
            self.rejects_report(modified)

    def test_interval_is_predeclared_conditional_and_wide_for_two_blocks(self):
        protocol = runner.create_revision_relay_protocol(blocks=2, seed=241, interval_assumptions={
            'independent_blocks_declared': True, 'stable_subject_backend_declared': True})
        report = runner.run_revision_relay_experiment(protocol)
        self.assertIs(report['analysis']['interval']['available'], True)
        self.assertEqual(report['analysis']['interval']['bounds'], [-2, 2])
        self.assertIs(report['analysis']['interval']['assumptions_attested'], False)
        self.assertIsNone(report['analysis']['p_value'])
        self.assertIs(runner.replay_revision_relay_report(report)['passed'], True)

    def test_honest_partial_grid_has_no_estimate_and_no_completed_proof(self):
        protocol, report, calls = self.partial()
        self.assertEqual(calls, 5)
        self.assertEqual([row['status'] for row in report['runs']],
                         ['complete', 'incomplete'] + ['not_started'] * 6)
        self.assertIsNone(report['analysis'])
        self.assertIsNone(report['runs'][1]['outcomes'])
        self.assertEqual(report['runs'][1]['counts']['applied_actions'], 0)
        self.assertEqual(report['runs'][1]['counts']['subject_call_attempts'], 1)
        proof = runner.replay_revision_relay_report(report)
        self.assertIs(proof['passed'], False)
        self.assertIs(proof['partial_trace_consistent'], True)
        with self.assertRaises(ValueError):
            runner.analyze_revision_relay_runs(report['runs'], protocol)

    def test_pre_subject_materialization_failure_retains_truthful_grid(self):
        original = runner._environment
        calls = 0
        def fail_second(protocol, row):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError('test-only materialization failure')
            return original(protocol, row)
        with patch.object(runner, '_environment', side_effect=fail_second):
            with self.assertRaises(runner.RevisionRelayExecutionError) as caught:
                runner.run_revision_relay_experiment(self.protocol)
        report = caught.exception.partial_report
        self.assertEqual(report['failure']['phase'], 'materialize')
        self.assertEqual(sum(row['counts']['subject_call_attempts'] for row in report['runs']), 0)
        self.assertTrue(all(not row['turns'] and not row['boundaries'] for row in report['runs']))
        proof = runner.replay_revision_relay_report(report)
        self.assertIs(proof['passed'], False)
        self.assertIs(proof['partial_trace_consistent'], True)

    def test_reporting_failure_does_not_change_completed_world_or_estimate_subset(self):
        def fail_progress(_):
            raise RuntimeError('test-only progress failure')
        with self.assertRaises(runner.RevisionRelayExecutionError) as caught:
            runner.run_revision_relay_experiment(self.protocol, on_progress=fail_progress)
        report = caught.exception.partial_report
        self.assertEqual(report['runs'][0]['status'], 'complete')
        self.assertIsNotNone(report['runs'][0]['outcomes'])
        self.assertTrue(all(row['status'] == 'not_started' for row in report['runs'][1:]))
        self.assertIsNone(report['analysis'])
        proof = runner.replay_revision_relay_report(report)
        self.assertIs(proof['passed'], False)
        self.assertIs(proof['partial_trace_consistent'], True)

    def test_invented_unstarted_or_post_abort_world_evidence_rejects(self):
        protocol, partial, _ = self.partial()
        variants = []
        for field, value in [('outcomes', {'C_final_correct': 1}),
                             ('counts', {'subject_call_attempts': 1, 'applied_actions': 0,
                                         'completed_opportunities': 0, 'model_calls': None}),
                             ('boundaries', [copy.deepcopy(partial['runs'][1]['boundaries'][0])])]:
            modified = copy.deepcopy(partial)
            modified['runs'][2][field] = value
            variants.append(modified)
        complete = runner.run_revision_relay_experiment(protocol, runner.revision_relay_scoped_policy)
        modified = copy.deepcopy(partial)
        modified['runs'][2] = copy.deepcopy(complete['runs'][2])
        variants.append(modified)
        for modified in variants:
            proof = self.rejects_report(modified)
            self.assertIs(proof.get('partial_trace_consistent', False), False)

    def test_unapplied_boundary_cannot_invent_action_or_retention(self):
        _, partial, _ = self.partial()
        for key, value in [('attempted_action', {'action': 'wait'}),
                           ('action_retention', {'status': 'bounded_original', 'original_output_hash': 'a' * 64}),
                           ('action_applied', 0)]:
            modified = copy.deepcopy(partial)
            modified['runs'][1]['boundaries'][0][key] = value
            self.rejects_report(modified)

    def test_execution_archive_checks_source_bytes_manifest_and_report_bindings(self):
        protocol = runner.create_revision_relay_protocol(blocks=1, seed=293)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'execution'
            report = runner.run_revision_relay_experiment(protocol, output_dir=directory)
            self.assertIs(runner.replay_revision_relay_report(report, output_dir=directory)['passed'], True)
            path = directory / 'execution-code' / 'revision_relay_env.py'
            original = path.read_bytes()
            path.write_bytes(original + b'\n# altered archive\n')
            self.assertIs(runner.replay_revision_relay_report(report, output_dir=directory)['passed'], False)
            path.write_bytes(original)
            path = directory / 'execution-code' / 'manifest.json'
            original = path.read_bytes()
            manifest = json.loads(original)
            manifest['timing'] = 'after_subject_calls'
            path.write_text(json.dumps(manifest), encoding='utf-8')
            self.assertIs(runner.replay_revision_relay_report(report, output_dir=directory)['passed'], False)
            path.write_bytes(original)
            altered = copy.deepcopy(report)
            altered['local_artifacts_before_subject_calls'] = False
            self.assertIs(runner.replay_revision_relay_report(self.reseal(altered), output_dir=directory)['passed'], False)


class IndependentRelayActionRetentionTests(unittest.TestCase):
    def test_world_cardinality_bounds_use_replayable_retention_metadata(self):
        attacks = [list(range(17)), {'action': 'unsupported', **{f'key-{i}': i for i in range(32)}}]
        for raw in attacks:
            with self.subTest(kind=type(raw).__name__):
                env = runner.world.create_revision_relay_environment(seed=317)
                action, retention = runner._action(raw)
                result = env.step('B', action)
                self.assertIs(result['ok'], False)
                executed = next(event for event in reversed(env.snapshot()['events']) if event['type'] == 'action')
                self.assertEqual(executed['action'], runner.world.INVALID_RETAINED_ACTION)
                runner._retention(executed['action'], retention)

    def test_pre_subject_failure_cannot_invent_later_materialization(self):
        protocol = runner.create_revision_relay_protocol(blocks=1, seed=337)
        original = runner._environment
        materializations = 0
        def fail_second(protocol, row):
            nonlocal materializations
            materializations += 1
            if materializations == 2:
                raise RuntimeError('test-only materialization failure')
            return original(protocol, row)
        with patch.object(runner, '_environment', side_effect=fail_second):
            with self.assertRaises(runner.RevisionRelayExecutionError) as caught:
                runner.run_revision_relay_experiment(protocol)
        modified = copy.deepcopy(caught.exception.partial_report)
        later = modified['runs'][2]
        later['initial_state'] = original(protocol, later).snapshot()
        later['exogenous_identity'] = runner._exogenous(later['initial_state'])
        proof = runner.replay_revision_relay_report(runner._seal(modified, 'report_hash'))
        with self.subTest(phase='materialize'):
            self.assertIs(proof.get('partial_trace_consistent', False), False, proof)

        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'execution'
            with patch.object(runner, '_archive', side_effect=RuntimeError('test-only archive failure')):
                with self.assertRaises(runner.RevisionRelayExecutionError) as caught:
                    runner.run_revision_relay_experiment(protocol, output_dir=directory)
        modified = copy.deepcopy(caught.exception.partial_report)
        self.assertEqual(modified['failure']['phase'], 'archive')
        row = modified['runs'][0]
        row['initial_state'] = original(protocol, row).snapshot()
        row['exogenous_identity'] = runner._exogenous(row['initial_state'])
        proof = runner.replay_revision_relay_report(runner._seal(modified, 'report_hash'))
        with self.subTest(phase='archive'):
            self.assertIs(proof.get('partial_trace_consistent', False), False, proof)


if __name__ == '__main__':
    unittest.main()
