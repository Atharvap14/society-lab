"""Real CPU world execution plus checkpoint and scientific-binding failures."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from swarm_lab.config import Settings
from swarm_lab.environment_authoring import blueprint_fingerprint
from swarm_lab.pipeline import Lab
from swarm_lab.research_cycle import start_research_cycle, resume_research_cycle
from tests.test_environment_authoring import proposal, review


def ref(obj):
    return {k: obj[k] for k in ('kind', 'id', 'version', 'hash')}


class ResearchCycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.lab = Lab(Settings(root=Path(self.temp.name)))
        self.dataset = self.lab.store.put('dataset', {'messages': [{'id': 'm1', 'content': 'A recorded coordination question.'}], 'scope': {}})
        self.discovery = self.lab.store.put('discovery', {'graph': {'edges': []}, 'candidates': []})
        self.sources = {kind: ref(obj) for kind, obj in (('dataset', self.dataset), ('discovery', self.discovery))}
        self.behavior = self.lab.store.put('behavior', {'name': 'Candidate coordination question', 'status': 'candidate',
            'evidence_ids': ['m1'], 'dataset_id': self.dataset['id'], 'discovery_id': self.discovery['id'],
            'source_refs': {kind: {k: o[k] for k in ('id', 'version', 'hash')} for kind, o in self.sources.items()},
            'experiment_ids': [], 'theory_ids': []})

    def inputs(self, template='complementary_information', **changes):
        p = proposal(template)
        if template == 'exclusive_resource_tasks':
            p['parameters'].update(max_rounds=4, release_rounds=[1, 2], independent_work_steps=1, computer_work_steps=1)
            p['mechanism_hypothesis'] = 'Task-specific reminders may alter allocation between independent and resource-gated work.'
        materialized = copy.deepcopy(p)
        materialized['source_refs'] = [ref(self.behavior), *self.sources.values()]
        kwargs = {'behavior_ref': ref(self.behavior), 'source_refs': self.sources, 'proposal': p,
            'fit_review': review(reviewed_blueprint_hash=blueprint_fingerprint(materialized)),
            'seed': 7501, 'job_id': 'cycle-test'}
        kwargs.update(changes)
        return kwargs

    def start(self, template='complementary_information', **changes):
        return start_research_cycle(self.lab, **self.inputs(template, **changes))

    def test_complementary_real_world_compile_register_execute_replay_facts_and_scoped_library(self):
        cycle = self.start()
        self.assertEqual(cycle['payload']['status'], 'completed', cycle['payload'].get('failures'))
        p = cycle['payload']; a = p['artifacts']
        protocol = self.lab.store.get(a['protocol']['id'])
        result = self.lab.store.get(a['result']['id'])
        blueprint = self.lab.store.get(a['blueprint']['id'])
        self.assertEqual(protocol['kind'], 'complementary_protocol')
        self.assertEqual(next(iter(protocol['payload']['protocol']['environments'].values())), blueprint['payload']['spec'])
        self.assertEqual(result['payload']['status'], 'complete')
        self.assertTrue(self.lab.store.get(a['verification']['id'])['payload']['passed'])
        self.assertTrue(self.lab.store.get(a['claim_audit']['id'])['payload']['audit']['all_executable_claims_supported'])
        theory = self.lab.store.get(a['theory']['id'])
        self.assertEqual(theory['kind'], 'theory')
        self.assertEqual(theory['payload']['status'], 'hypothesis')
        self.assertEqual(theory['payload']['statement'], blueprint['payload']['proposed_blueprint']['mechanism_hypothesis'])
        self.assertEqual(theory['payload']['supporting_results'], [])
        self.assertEqual(theory['payload']['mechanism_support'], 'unestablished')
        self.assertEqual(theory['payload']['source_refs']['behavior'], ref(self.behavior))
        self.assertEqual(ref(self.lab.store.get(self.behavior['id'])), ref(self.behavior))
        self.assertEqual(self.lab.store.usage()['calls'], 0)

    def test_resource_real_world_dispatch_and_process_facts_do_not_become_beliefs(self):
        cycle = self.start('exclusive_resource_tasks')
        self.assertEqual(cycle['payload']['status'], 'completed', cycle['payload'].get('failures'))
        a = cycle['payload']['artifacts']
        result = self.lab.store.get(a['result']['id'])
        self.assertEqual(result['kind'], 'resource_experiment')
        raw = json.loads((Path(result['payload']['artifact_directory']) / 'report.json').read_text(encoding='utf-8'))
        self.assertEqual(len(raw['runs']), 4)
        self.assertTrue(self.lab.audit(result['id'])['payload']['passed'])
        claims = self.lab.store.get(a['claim_audit']['id'])['payload']
        self.assertTrue(claims['quantitative_facts_available'])
        theory = self.lab.store.get(a['theory']['id'])['payload']
        self.assertEqual(theory['scope']['world_kind'], 'exclusive_resource_tasks')
        self.assertIn('Scripted execution provides no evidence about LLM behavior.', theory['limitations'])
        self.assertEqual(self.lab.store.usage()['calls'], 0)

    def test_other_allowlisted_kinds_execute_without_world_substitution(self):
        for template, kind in (('shared_artifact_coordination', 'experiment'), ('provenance_diffusion', 'network_experiment')):
            with self.subTest(template=template):
                # Artifact execution deliberately appends a conservative behavior version.
                self.behavior = self.lab.store.get(self.behavior['id'])
                cycle = self.start(template, job_id='cycle-' + template)
                self.assertEqual(cycle['payload']['status'], 'completed', cycle['payload']['failures'])
                self.assertEqual(cycle['payload']['artifacts']['result']['kind'], kind)
                if template == 'shared_artifact_coordination':
                    self.assertEqual(cycle['payload']['plan']['behavior_ref']['version'], 1)
                    self.assertEqual(cycle['payload']['authorized_behavior_append']['version'], 2)
        self.assertEqual(self.lab.store.usage()['calls'], 0)

    def test_exact_existing_blueprint_uses_no_builder_or_reviewer(self):
        inputs = self.inputs()
        world = self.lab.construct_environment(behavior_id=self.behavior['id'], proposal=inputs['proposal'], fit_review=inputs['fit_review'])
        with patch.object(self.lab, 'construct_environment', side_effect=AssertionError('must not construct')):
            cycle = start_research_cycle(self.lab, behavior_ref=ref(self.behavior), source_refs=self.sources,
                blueprint_ref=ref(world), job_id='existing-world')
        self.assertEqual(cycle['payload']['status'], 'completed', cycle['payload']['failures'])
        self.assertEqual(cycle['payload']['artifacts']['blueprint'], ref(world))

    def test_exact_blueprint_inherits_pinned_capabilities_when_caller_omits_them(self):
        inputs = self.inputs('exclusive_resource_tasks')
        required = ['exclusive_shared_computer', 'independent_parallel_work']
        world = self.lab.construct_environment(behavior_id=self.behavior['id'], proposal=inputs['proposal'],
            fit_review=inputs['fit_review'], required_capabilities=required)
        cycle = start_research_cycle(self.lab, behavior_ref=ref(self.behavior), source_refs=self.sources,
            blueprint_ref=ref(world), job_id='inherit-world')
        self.assertEqual(cycle['payload']['status'], 'completed', cycle['payload']['failures'])
        self.assertEqual(cycle['payload']['plan']['construction']['required_capabilities'], required)
        self.assertEqual(cycle['payload']['artifacts']['blueprint'], ref(world))
        changed = start_research_cycle(self.lab, behavior_ref=ref(self.behavior), source_refs=self.sources,
            blueprint_ref=ref(world), required_capabilities=[], job_id='changed-world-requirements')
        self.assertEqual(changed['payload']['status'], 'blocked')
        self.assertEqual(changed['payload']['stages']['construct']['failure_code'], 'capability_binding_mismatch')

    def test_discovery_dataset_contradiction_and_unsafe_job_identity_fail_before_claim(self):
        for identity in ('../outside', 'CON', 'a:b'):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                self.start(job_id=identity)
            self.assertFalse(self.lab.store.job_exists(identity))
        discovery = self.lab.store.put('discovery', {'dataset_ref': {'id': self.dataset['id'], 'version': 2, 'hash': '0' * 64}})
        sources = {**self.sources, 'discovery': ref(discovery)}
        p = copy.deepcopy(self.behavior['payload']); p['discovery_id'] = discovery['id']
        p['source_refs']['discovery'] = {k: discovery[k] for k in ('id', 'version', 'hash')}
        behavior = self.lab.store.put('behavior', p)
        kwargs = self.inputs(behavior_ref=ref(behavior), source_refs=sources, job_id='contradictory-discovery')
        with self.assertRaisesRegex(ValueError, 'another dataset'):
            start_research_cycle(self.lab, **kwargs)
        self.assertFalse(self.lab.store.job_exists('contradictory-discovery'))

    def test_fit_rejection_retains_attempt_phase_blueprint_and_no_protocol(self):
        kwargs = self.inputs(); kwargs['fit_review']['decision'] = 'block'
        kwargs['fit_review']['blocking_reasons'] = ['The proposed analogue misses the required mechanism.']
        cycle = start_research_cycle(self.lab, **kwargs)
        self.assertEqual(cycle['payload']['status'], 'blocked')
        self.assertEqual(cycle['payload']['phase'], 'construct')
        self.assertIn('blueprint', cycle['payload']['artifacts'])
        self.assertTrue(cycle['payload']['construction_attempt_refs'])
        self.assertEqual(self.lab.store.list('complementary_protocol'), [])
        self.assertEqual(self.lab.store.list('theory'), [])
        self.assertEqual(resume_research_cycle(self.lab, cycle['id'])['version'], cycle['version'])

    def test_required_unsupported_capability_is_durable_not_weakened(self):
        cycle = self.start(required_capabilities=['browser_tools'])
        self.assertEqual(cycle['payload']['status'], 'blocked')
        world = self.lab.store.get(cycle['payload']['artifacts']['blueprint']['id'])
        self.assertEqual(world['payload']['construction_status'], 'unsupported')
        self.assertIn('browser_tools', world['payload']['missing_capabilities'])
        self.assertEqual(self.lab.store.list('complementary_protocol'), [])

    def test_custom_graph_design_gap_retains_approved_world_without_graph_replacement(self):
        kwargs = self.inputs(); kwargs['proposal']['parameters'].update(topology='custom', custom_edges=[['agent-0', 'agent-1']])
        materialized = copy.deepcopy(kwargs['proposal']); materialized['source_refs'] = [ref(self.behavior), *self.sources.values()]
        kwargs['fit_review'] = review(reviewed_blueprint_hash=blueprint_fingerprint(materialized))
        cycle = start_research_cycle(self.lab, **kwargs)
        self.assertEqual(cycle['payload']['status'], 'blocked')
        self.assertEqual(cycle['payload']['phase'], 'register')
        self.assertEqual(cycle['payload']['stages']['register']['failure_code'], 'design_incompatible')
        self.assertEqual(self.lab.store.list('complementary_protocol'), [])
        world = self.lab.store.get(cycle['payload']['artifacts']['blueprint']['id'])
        self.assertEqual(world['payload']['spec']['topology']['kind'], 'custom')

    def test_audit_failure_resume_reuses_subject_result_and_claims_are_not_fabricated(self):
        execute = self.lab.experiment_complementary
        with patch.object(self.lab, 'experiment_complementary', wraps=execute) as runner:
            with patch.object(self.lab, 'audit', side_effect=RuntimeError('CPU audit unavailable')):
                cycle = self.start()
            self.assertEqual(cycle['payload']['status'], 'failed')
            self.assertEqual(cycle['payload']['phase'], 'audit')
            self.assertIn('result', cycle['payload']['artifacts'])
            self.assertNotIn('claim_audit', cycle['payload']['artifacts'])
            self.assertEqual(self.lab.store.list('theory'), [])
            again = resume_research_cycle(self.lab, cycle['id'])
            self.assertEqual(again['payload']['status'], 'completed', again['payload']['failures'])
            self.assertEqual(runner.call_count, 1)
            self.assertEqual(again['payload']['artifacts']['result'], cycle['payload']['artifacts']['result'])
        completed = resume_research_cycle(self.lab, cycle['id'])
        self.assertEqual(completed['version'], again['version'])

    def test_recovery_after_execution_returns_but_checkpoint_fails_does_not_repeat(self):
        import swarm_lab.research_cycle as module
        save = module._save
        tripped = False
        def interrupted(lab, obj, payload):
            nonlocal tripped
            if payload['stages']['execute']['status'] == 'completed' and not tripped:
                tripped = True; raise RuntimeError('checkpoint interruption after subjects finished')
            return save(lab, obj, payload)
        with patch.object(self.lab, 'experiment_complementary', wraps=self.lab.experiment_complementary) as runner:
            with patch('swarm_lab.research_cycle._save', side_effect=interrupted):
                cycle = self.start()
            self.assertEqual(cycle['payload']['status'], 'failed')
            self.assertEqual(cycle['payload']['phase'], 'execute')
            again = resume_research_cycle(self.lab, cycle['id'])
            self.assertEqual(again['payload']['status'], 'completed', again['payload']['failures'])
            self.assertEqual(runner.call_count, 1)

    def test_primary_result_recovery_validates_its_intended_behavior_append(self):
        execute = self.lab.experiment
        def return_interruption(*args, **kwargs):
            execute(*args, **kwargs)
            raise RuntimeError('interrupted after result persistence and library append')
        with patch.object(self.lab, 'experiment', side_effect=return_interruption) as runner:
            cycle = self.start('shared_artifact_coordination')
            self.assertEqual(cycle['payload']['status'], 'failed')
            self.assertEqual(self.lab.store.get(self.behavior['id'])['version'], 2)
            again = resume_research_cycle(self.lab, cycle['id'])
            self.assertEqual(again['payload']['status'], 'completed', again['payload']['failures'])
            self.assertEqual(runner.call_count, 1)
            self.assertEqual(again['payload']['authorized_behavior_append']['version'], 2)

    def test_unknown_execution_failure_is_not_relaunched_or_success_selected(self):
        with patch.object(self.lab, 'experiment_complementary', side_effect=RuntimeError('unknown completion')) as runner:
            cycle = self.start()
            self.assertEqual(cycle['payload']['status'], 'failed')
            again = resume_research_cycle(self.lab, cycle['id'])
            self.assertEqual(again['payload']['status'], 'blocked')
            self.assertEqual(again['payload']['stages']['execute']['failure_code'], 'uncertain_stage_completion')
            self.assertEqual(runner.call_count, 1)
            self.assertNotIn('result', again['payload']['artifacts'])
        self.assertEqual(self.lab.store.list('theory'), [])

    def test_changed_selected_source_on_resume_blocks_before_new_work(self):
        with patch.object(self.lab, 'audit', side_effect=RuntimeError('pause before audit')):
            cycle = self.start()
        changed = copy.deepcopy(self.dataset['payload']); changed['messages'][0]['content'] = 'Changed source.'
        self.lab.store.put('dataset', changed, self.dataset['id'])
        with patch.object(self.lab, 'audit', side_effect=AssertionError('must not audit drifted inputs')):
            again = resume_research_cycle(self.lab, cycle['id'])
        self.assertEqual(again['payload']['status'], 'blocked')
        self.assertEqual(again['payload']['stages']['audit']['failure_code'], 'version_drift')
        self.assertEqual(again['payload']['plan']['source_refs']['dataset'], ref(self.dataset))

    def test_rejected_stale_bad_hash_and_numeric_reference_inputs_fail_before_job(self):
        for mutation in ('rejected', 'stale', 'hash', 'bool', 'float'):
            with self.subTest(mutation=mutation):
                kwargs = self.inputs(job_id='invalid-' + mutation)
                if mutation == 'rejected':
                    p = copy.deepcopy(self.behavior['payload']); p['status'] = 'rejected'
                    bad = self.lab.store.put('behavior', p)
                    kwargs['behavior_ref'] = ref(bad)
                elif mutation == 'stale':
                    self.lab.store.put('discovery', copy.deepcopy(self.discovery['payload']), self.discovery['id'])
                elif mutation == 'hash': kwargs['source_refs'] = copy.deepcopy(self.sources); kwargs['source_refs']['dataset']['hash'] = '0' * 64
                else: kwargs['behavior_ref']['version'] = True if mutation == 'bool' else 1.0
                with self.assertRaises((ValueError, KeyError)):
                    start_research_cycle(self.lab, **kwargs)
                self.assertFalse(self.lab.store.job_exists(kwargs['job_id']))
                if mutation == 'stale':
                    # Restore fixture with freshly pinned source versions for later variants.
                    self.discovery = self.lab.store.get(self.discovery['id']); self.sources['discovery'] = ref(self.discovery)
                    p = copy.deepcopy(self.behavior['payload']); p['source_refs']['discovery'] = {k: self.discovery[k] for k in ('id', 'version', 'hash')}
                    self.behavior = self.lab.store.put('behavior', p, self.behavior['id'])

    def test_flags_backends_budgets_and_callbacks_are_strict_and_no_implicit_calls(self):
        variations = [{'research_live': 1}, {'subjects_live': 'false'}, {'trials_per_cell': True},
            {'seed': 1.0}, {'max_new_model_calls': False}, {'research_harness': 'arbitrary'},
            {'subject_harness': 'codex'}, {'max_new_model_calls': 1},
            {'subjects_live': True}, {'research_live': True, 'max_new_model_calls': 2},
            {'proposal': lambda: None}, {'required_capabilities': ['resettable_state'] * 2}]
        for index, fields in enumerate(variations):
            kwargs = self.inputs(job_id=f'invalid-flags-{index}'); kwargs.update(fields)
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                start_research_cycle(self.lab, **kwargs)
        self.assertEqual(self.lab.store.usage()['calls'], 0)
        self.assertEqual(self.lab.store.list('research_cycle'), [])

    def test_subjects_live_budget_gate_registers_mode_then_stops_before_any_call(self):
        with patch.object(self.lab, 'experiment_complementary', side_effect=AssertionError('must not call subjects')):
            cycle = self.start(subjects_live=True, max_new_model_calls=1)
        self.assertEqual(cycle['payload']['status'], 'blocked')
        self.assertEqual(cycle['payload']['phase'], 'execute')
        self.assertEqual(cycle['payload']['stages']['execute']['failure_code'], 'subject_budget_insufficient')
        self.assertEqual(self.lab.store.get(cycle['payload']['artifacts']['protocol']['id'])['payload']['agent_mode'], 'live')
        self.assertEqual(self.lab.store.usage()['calls'], 0)

    def test_agentic_research_flag_can_be_separate_from_scripted_subjects(self):
        p = proposal()
        def role(name, task, schema, *args):
            if name == 'environment-builder': return copy.deepcopy(p)
            return review(reviewed_blueprint_hash=task['reviewed_blueprint_hash'])
        agent = Mock(); agent.run.side_effect = role
        with patch('swarm_lab.authoring_workflow.ResearchAgents', return_value=agent):
            cycle = start_research_cycle(self.lab, behavior_ref=ref(self.behavior), source_refs=self.sources,
                research_live=True, subjects_live=False, max_new_model_calls=2, job_id='mocked-agentic')
        self.assertEqual(cycle['payload']['status'], 'completed', cycle['payload']['failures'])
        self.assertEqual(agent.run.call_count, 2)
        self.assertEqual(self.lab.store.get(cycle['payload']['artifacts']['result']['id'])['payload']['agent_mode'], 'offline_simulation')
        self.assertEqual(self.lab.settings.max_calls, 400)

    def test_call_ceiling_is_original_absolute_value_not_reset_by_resume(self):
        with patch.object(self.lab, 'audit', side_effect=RuntimeError('audit interrupted')):
            cycle = self.start()
        self.lab.store.reserve_call(400)
        again = resume_research_cycle(self.lab, cycle['id'])
        self.assertEqual(again['payload']['status'], 'blocked')
        self.assertEqual(again['payload']['plan']['budget']['absolute_call_ceiling'], 0)
        self.assertEqual(again['payload']['stages']['audit']['failure_code'], 'budget_exhausted')

    def test_job_duplicate_and_rehashed_plan_amendment_are_rejected(self):
        with patch.object(self.lab, 'audit', side_effect=RuntimeError('audit interrupted')):
            cycle = self.start()
        with self.assertRaises(ValueError): self.start()
        modified = copy.deepcopy(cycle['payload']); modified['plan']['design']['seed'] += 1
        from swarm_lab.research_cycle import _digest
        modified['plan_hash'] = _digest(modified['plan'])
        self.lab.store.put('research_cycle', modified, cycle['id'])
        with self.assertRaisesRegex(ValueError, 'original cycle plan'):
            resume_research_cycle(self.lab, cycle['id'])

    def test_failed_replay_and_finite_mismatch_cannot_curate(self):
        actual = self.lab.audit
        def failed(result_id):
            obj = actual(result_id); value = obj['payload']; value['passed'] = False
            return self.lab.store.put('verification', value)
        with patch.object(self.lab, 'audit', side_effect=failed): cycle = self.start()
        self.assertEqual(cycle['payload']['status'], 'blocked')
        self.assertEqual(cycle['payload']['phase'], 'audit')
        self.assertEqual(self.lab.store.list('claim_audit'), [])
        self.assertEqual(self.lab.store.list('theory'), [])

    def test_finite_typed_claim_forgery_cannot_pass_reported_success_flag(self):
        actual = self.lab.evaluate_claims
        def forged(result_id, **kwargs):
            obj = actual(result_id, **kwargs); value = copy.deepcopy(obj['payload'])
            # Deliberately retain the old all-supported flag after altering a typed value.
            self.assertTrue(value['claims'])
            value['claims'][0]['expected'] = not value['claims'][0]['expected'] if type(value['claims'][0]['expected']) is bool else 999999
            return self.lab.store.put('claim_audit', value)
        with patch.object(self.lab, 'evaluate_claims', side_effect=forged):
            cycle = self.start()
        self.assertEqual(cycle['payload']['status'], 'blocked')
        self.assertEqual(cycle['payload']['phase'], 'claims')
        self.assertEqual(cycle['payload']['stages']['claims']['failure_code'], 'finite_claims_recheck_failed')
        self.assertIn('claim_audit', cycle['payload']['artifacts'])
        self.assertEqual(self.lab.store.list('theory'), [])

    def test_blueprint_bound_review_hash_cannot_be_copied_from_another_proposal(self):
        kwargs = self.inputs(); kwargs['fit_review']['reviewed_blueprint_hash'] = '0' * 64
        cycle = start_research_cycle(self.lab, **kwargs)
        self.assertEqual(cycle['payload']['status'], 'blocked')
        self.assertEqual(cycle['payload']['phase'], 'construct')
        self.assertEqual(self.lab.store.list('complementary_protocol'), [])

    def test_proof_binding_forgery_and_numeric_bool_attestation_do_not_curate(self):
        actual = self.lab.audit
        for name in ('result_ref', 'model_calls'):
            def forged(result_id):
                obj = actual(result_id); value = copy.deepcopy(obj['payload'])
                if name == 'result_ref': value['result_ref']['hash'] = '0' * 64
                else: value['model_calls'] = False
                return self.lab.store.put('verification', value)
            with self.subTest(name=name), patch.object(self.lab, 'audit', side_effect=forged):
                cycle = self.start(job_id='proof-' + name)
            self.assertEqual(cycle['payload']['status'], 'blocked')
            self.assertEqual(cycle['payload']['phase'], 'audit')
        self.assertEqual(self.lab.store.list('theory'), [])

    def test_bound_archive_mutation_after_independent_proof_blocks_curation(self):
        actual = self.lab.evaluate_claims
        def corrupt_after_facts(result_id, **kwargs):
            obj = actual(result_id, **kwargs)
            result = self.lab.store.get(result_id)
            path = Path(result['payload']['artifact_directory']) / 'report.json'
            raw = json.loads(path.read_text(encoding='utf-8'))
            raw['runs'][0]['outcomes']['forged_measurement'] = True
            path.write_text(json.dumps(raw), encoding='utf-8')
            return obj
        with patch.object(self.lab, 'evaluate_claims', side_effect=corrupt_after_facts):
            cycle = self.start()
        self.assertEqual(cycle['payload']['status'], 'blocked')
        self.assertEqual(cycle['payload']['phase'], 'claims')
        self.assertEqual(cycle['payload']['stages']['claims']['failure_code'], 'archive_report_mismatch')
        self.assertEqual(self.lab.store.list('theory'), [])

    def test_backend_drift_after_saved_execution_prevents_new_stage_calls(self):
        with patch.object(self.lab, 'audit', side_effect=RuntimeError('audit interrupted')):
            cycle = self.start()
        self.lab.settings.model = 'another-requested-model'
        with patch.object(self.lab, 'audit', side_effect=AssertionError('no drifted audit')):
            again = resume_research_cycle(self.lab, cycle['id'])
        self.assertEqual(again['payload']['status'], 'blocked')
        self.assertEqual(again['payload']['stages']['audit']['failure_code'], 'backend_drift')

    def test_construct_failure_preserves_saved_builder_and_does_not_repeat_live_roles(self):
        agent = Mock(); agent.run.side_effect = [proposal(), RuntimeError('review transport failed')]
        with patch('swarm_lab.authoring_workflow.ResearchAgents', return_value=agent):
            cycle = start_research_cycle(self.lab, behavior_ref=ref(self.behavior), source_refs=self.sources,
                research_live=True, max_new_model_calls=2, job_id='saved-review-failure')
            again = resume_research_cycle(self.lab, cycle['id'])
        self.assertEqual(cycle['payload']['status'], 'failed')
        self.assertEqual(cycle['payload']['phase'], 'construct')
        saved = self.lab.store.get(cycle['payload']['construction_attempt_refs'][-1]['id'])
        self.assertEqual(saved['payload']['failed_phase'], 'reviewer')
        self.assertIn('materialized_proposal', saved['payload'])
        self.assertEqual(agent.run.call_count, 2)
        self.assertEqual(again['payload']['status'], 'blocked')
        self.assertEqual(again['payload']['stages']['construct']['failure_code'], 'uncertain_stage_completion')

    def test_safe_stage_retry_bound_stops_without_subject_relaunch(self):
        with patch.object(self.lab, 'experiment_complementary', wraps=self.lab.experiment_complementary) as runner:
            with patch.object(self.lab, 'audit', side_effect=RuntimeError('CPU failure')):
                cycle = self.start()
                for _ in range(3): cycle = resume_research_cycle(self.lab, cycle['id'])
            self.assertEqual(runner.call_count, 1)
        self.assertEqual(cycle['payload']['status'], 'blocked')
        self.assertEqual(cycle['payload']['stages']['audit']['attempts'], 3)
        self.assertEqual(cycle['payload']['stages']['audit']['failure_code'], 'retry_limit')

    def test_known_incomplete_result_retained_with_no_estimation_or_theory(self):
        # Test-only failure of the scripted policy: no hosted provider is invoked.
        with patch('swarm_lab.complementary_experiments.offline_complementary_policy', side_effect=RuntimeError('simulated scripted execution failure')):
            cycle = self.start()
        self.assertEqual(cycle['payload']['status'], 'failed')
        incomplete = cycle['payload']['artifacts']['incomplete_result']
        saved = self.lab.store.get(incomplete['id'])
        self.assertNotEqual(saved['payload']['status'], 'complete')
        self.assertIsNone(saved['payload'].get('analysis'))
        again = resume_research_cycle(self.lab, cycle['id'])
        self.assertEqual(again['payload']['status'], 'blocked')
        self.assertEqual(again['payload']['stages']['execute']['failure_code'], 'incomplete_execution')
        self.assertNotIn('claim_audit', again['payload']['artifacts'])
        self.assertEqual(self.lab.store.list('theory'), [])


if __name__ == '__main__':
    unittest.main()
