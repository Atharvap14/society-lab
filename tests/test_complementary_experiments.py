"""Executed complementary-world tests; all subjects are local test policies."""
import copy
import hashlib
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from swarm_lab.complementary_environment import offline_complementary_policy, fingerprint
from swarm_lab.audit import replay_report
from swarm_lab.complementary_experiments import (ComplementaryExecutionError,
    create_complementary_protocol, validate_complementary_protocol,
    randomize_complementary_runs, analyze_complementary_runs,
    run_complementary_experiment)


LOCAL_BACKEND={'harness':'local_test_double','model':'scripted_callable',
               'generation':{'policy':'offline_complementary_policy'}}


def local_protocol(**kwargs):
    return create_complementary_protocol(subject_backend=LOCAL_BACKEND,**kwargs)


def reseal(protocol):
    p=copy.deepcopy(protocol);p.pop('protocol_hash',None);p['protocol_hash']=fingerprint(p)
    return p


class ComplementaryExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_default_capability_contract_budget_and_pvalue_resolution(self):
        p=create_complementary_protocol();validate_complementary_protocol(p)
        self.assertEqual(p['design']['maximum_subject_calls'],96)
        self.assertEqual(p['design']['unit'],'whole_network_run')
        self.assertEqual(p['intervention']['recipients'],['agent-0'])
        self.assertEqual(p['capabilities']['initial_visibility'],'Each subject privately sees only its own original at reset; inspection is optional')
        for resolution in p['pre_execution_test_resolution']:
            self.assertEqual(resolution['conditional_assignments'],36)
            self.assertAlmostEqual(resolution['minimum_two_sided_p'],2/36)
        self.assertIn('diffusion_experiments.py',p['execution_code_hashes'])
        self.assertIn('complementary_environment.py',p['execution_code_hashes'])

    def test_balanced_shuffled_units_with_unique_independent_seeds(self):
        p=create_complementary_protocol();units=randomize_complementary_runs(p)
        self.assertEqual(Counter((u['topology'],u['context']) for u in units),
            Counter({('ring','placebo'):2,('ring','source_thought'):2,('complete','placebo'):2,('complete','source_thought'):2}))
        self.assertEqual(len({u['environment_seed'] for u in units}),8)
        self.assertEqual(units,randomize_complementary_runs(p))
        q=create_complementary_protocol(seed=92)
        self.assertFalse({u['environment_seed'] for u in units}&{u['environment_seed'] for u in randomize_complementary_runs(q)})
        self.assertNotEqual([u['topology'] for u in units],['ring']*4+['complete']*4)

    def test_offline_end_to_end_ignores_context_and_retains_bounded_uncertainty(self):
        p=create_complementary_protocol();report=run_complementary_experiment(p,output_dir=self.root,resamples=100)
        self.assertEqual(report['status'],'complete');self.assertEqual(len(report['runs']),8)
        self.assertEqual(report['backend']['mode'],'scripted_offline_smoke_test')
        self.assertIn('no empirical LLM evidence',report['evidence_scope'])
        self.assertTrue(all(r['outcomes']['mean_accuracy']==1 for r in report['runs']))
        for effect in report['analysis']['factor_effects']:
            self.assertEqual(effect['difference'],0);self.assertEqual(effect['p_holm_primary_family'],1)
            self.assertLess(effect['ci95'][0],0);self.assertGreater(effect['ci95'][1],0)
            self.assertEqual(effect['test_samples'],36)
        body={k:v for k,v in report.items() if k!='report_hash'}
        self.assertEqual(report['report_hash'],fingerprint(body))
        self.assertEqual(json.loads((self.root/'report.json').read_text()),report)

    def test_private_boundary_scoped_persistent_and_no_arm_oracle_leakage(self):
        p=create_complementary_protocol(contexts=('baseline','placebo','source_thought'))
        report=run_complementary_experiment(p,resamples=100)
        for run in report['runs']:
            expected=p['contexts'][run['context']]['insertion']
            first=next(t for t in run['turns'] if t['agent_id']=='agent-0')
            self.assertEqual(first['request']['context'],[] if expected is None else [expected])
            self.assertEqual(run['actual_context_insertion_recipients'],[] if expected is None else ['agent-0'])
            self.assertEqual(run['initial_state']['messages'],[])
            self.assertFalse(any(run['initial_state']['private_context'].values()))
            for turn in run['turns']:
                request=turn['request']
                self.assertEqual(set(request),{'role','system','context','observation','action_schema'})
                self.assertFalse({'oracle_total','seed','protocol_hash','source_thought','arm'}&set(request['observation']))
                self.assertNotIn('source_thought',json.dumps(request))
                if turn['agent_id']=='agent-0':
                    self.assertEqual(request['context'],[] if expected is None else [expected])
                else:self.assertEqual(request['context'],[])

    def test_pre_subject_artifacts_and_world_initial_snapshots_exist(self):
        p=local_protocol();calls=[]
        def runner(request):
            self.assertTrue((self.root/'protocol.json').is_file())
            self.assertTrue((self.root/'assignment.json').is_file())
            manifest=json.loads((self.root/'execution-code/manifest.json').read_text())
            for name,digest in p['execution_code_hashes'].items():
                self.assertEqual(manifest['files'][name],digest)
                self.assertEqual(hashlib.sha256((self.root/'execution-code'/name).read_bytes()).hexdigest(),digest)
            self.assertTrue(list((self.root/'initial_states').glob('*.json')))
            calls.append(1);return offline_complementary_policy(request)
        report=run_complementary_experiment(p,runner,self.root,resamples=100)
        self.assertLessEqual(len(calls),96)
        self.assertEqual(len(list((self.root/'initial_states').glob('*.json'))),8)
        self.assertEqual(len(list((self.root/'runs').glob('*.json'))),8)

    def test_adverse_context_policy_is_scored_as_harm_not_forced_benefit(self):
        p=local_protocol()
        def adverse(request):
            if request['role']=='agent-0' and any('original IDs' in t for t in request['context']):
                return {'action':'wait'}
            return offline_complementary_policy(request)
        report=run_complementary_experiment(p,adverse,resamples=100)
        self.assertLess(report['analysis']['primary_effect']['difference'],0)
        for run in report['runs']:
            if run['context']=='source_thought':
                self.assertEqual(run['outcomes']['per_agent_accuracy']['agent-0'],0)
                self.assertLess(run['outcomes']['completion_rate'],1)

    def test_invalid_model_actions_consume_budget_and_missing_answers_are_zeros(self):
        p=local_protocol();report=run_complementary_experiment(p,lambda r:{'action':'invalid_model_output'},resamples=100)
        self.assertEqual(report['status'],'complete')
        for run in report['runs']:
            self.assertEqual(run['outcomes']['mean_accuracy'],0)
            self.assertEqual(run['outcomes']['completion_rate'],0)
            self.assertEqual(run['outcomes']['invalid_actions'],12)
            self.assertEqual(run['outcomes']['steps_used'],12)

    def test_transport_failure_persists_partial_without_effects_or_secret_exception_text(self):
        p=local_protocol();count=0
        def fails(request):
            nonlocal count
            count+=1
            if count==14:raise ConnectionError('DO_NOT_PERSIST_EXCEPTION_CONTENT')
            return offline_complementary_policy(request)
        with self.assertRaises(ComplementaryExecutionError) as caught:
            run_complementary_experiment(p,fails,self.root,resamples=100)
        report=caught.exception.partial_report
        self.assertEqual(report['status'],'incomplete_infrastructure_failure')
        self.assertGreaterEqual(len(report['runs']),1)
        self.assertNotIn('analysis',report);self.assertNotIn('report_hash',report)
        raw=(self.root/'report.json').read_text();self.assertNotIn('DO_NOT_PERSIST_EXCEPTION_CONTENT',raw)
        self.assertEqual(json.loads(raw),report)

    def test_constructor_failure_has_a_report_and_no_estimation(self):
        p=create_complementary_protocol()
        with patch('swarm_lab.complementary_experiments.create_complementary_environment',side_effect=RuntimeError('Synthetic')):
            with self.assertRaises(ComplementaryExecutionError) as caught:
                run_complementary_experiment(p,output_dir=self.root,resamples=100)
        report=caught.exception.partial_report
        self.assertIsNone(report['incomplete_run']['state']);self.assertEqual(report['runs'],[])
        self.assertNotIn('analysis',report);self.assertTrue((self.root/'report.json').is_file())

    def test_analysis_failure_never_reports_complete_or_partial_effects(self):
        p=create_complementary_protocol()
        with patch('swarm_lab.complementary_experiments.analyze_complementary_runs',side_effect=RuntimeError('Synthetic')):
            with self.assertRaises(ComplementaryExecutionError) as caught:
                run_complementary_experiment(p,output_dir=self.root,resamples=100)
        report=caught.exception.partial_report
        self.assertEqual(report['status'],'incomplete_analysis_failure');self.assertEqual(len(report['runs']),8)
        self.assertNotIn('analysis',report);self.assertTrue((self.root/'report.json').is_file())

    def test_source_and_frozen_protocol_tamper_are_rejected_before_runner(self):
        p=local_protocol();p['design']['seed']=3
        with self.assertRaisesRegex(ValueError,'changed after freezing'):
            run_complementary_experiment(p,lambda r:self.fail('called before gate'))
        p=local_protocol();p['execution_code_hashes']['diffusion_experiments.py']='0'*64;p=reseal(p)
        with self.assertRaisesRegex(ValueError,'source changed'):
            validate_complementary_protocol(p)

    def test_capability_and_declared_budget_are_validated_even_if_resealed(self):
        p=create_complementary_protocol();p['capabilities']['initial_visibility']='all_fragments_visible';p=reseal(p)
        with self.assertRaisesRegex(ValueError,'capability mismatch'):validate_complementary_protocol(p)
        p=create_complementary_protocol();p['design']['maximum_subject_calls']=8;p=reseal(p)
        with self.assertRaisesRegex(ValueError,'budget is inconsistent'):validate_complementary_protocol(p)

    def test_topologies_cannot_smuggle_different_world_distribution(self):
        p=create_complementary_protocol();spec=p['environments']['complete']
        spec['measurement_world'].update(modulus=101,component_max=100)
        p['environment_hashes']['complete']=fingerprint(spec);p=reseal(p)
        with self.assertRaisesRegex(ValueError,'share measurement'):validate_complementary_protocol(p)

    def test_backend_mismatch_and_unpinned_runner_are_rejected_without_calls(self):
        p=local_protocol()
        with self.assertRaisesRegex(ValueError,'backend differs'):
            run_complementary_experiment(p,lambda r:self.fail('called'),backend_metadata={'model':'changed'})
        with self.assertRaisesRegex(ValueError,'pinned model'):
            run_complementary_experiment(create_complementary_protocol(),lambda r:self.fail('called'))
        with self.assertRaisesRegex(ValueError,'Scripted runner'):
            run_complementary_experiment(p)

    def test_ad_hoc_run_exclusion_reorder_and_duplicate_unit_cannot_be_analyzed(self):
        p=create_complementary_protocol();report=run_complementary_experiment(p,resamples=100)
        with self.assertRaisesRegex(ValueError,'All assigned networks'):
            analyze_complementary_runs(report['runs'][:-1],p,resamples=100)
        with self.assertRaisesRegex(ValueError,'All assigned networks'):
            analyze_complementary_runs(list(reversed(report['runs'])),p,resamples=100)
        altered=copy.deepcopy(report['runs']);altered[1]=copy.deepcopy(altered[0])
        with self.assertRaisesRegex(ValueError,'All assigned networks'):
            analyze_complementary_runs(altered,p,resamples=100)

    def test_optional_baseline_and_star_are_explicit_factorial_levels(self):
        p=create_complementary_protocol(topologies=('ring','star','complete'),contexts=('baseline','placebo','source_thought'))
        self.assertEqual(len(randomize_complementary_runs(p)),18)
        self.assertEqual(p['design']['maximum_subject_calls'],216)
        for resolution in p['pre_execution_test_resolution']:
            self.assertEqual(resolution['conditional_assignments'],216)
        report=run_complementary_experiment(p,resamples=100)
        self.assertEqual(len(report['analysis']['cells']),9)
        for run in report['runs']:
            if run['context']=='baseline':self.assertEqual(run['actual_context_insertion_recipients'],[])

    def test_observer_failure_cannot_remove_assigned_networks(self):
        p=create_complementary_protocol()
        def broken(progress):raise RuntimeError('Synthetic observer')
        report=run_complementary_experiment(p,on_progress=broken,resamples=100)
        self.assertEqual(report['status'],'complete');self.assertEqual(len(report['runs']),8)
        self.assertEqual(len(report['reporting_warnings']),8)

    def test_output_directory_cannot_overwrite_an_execution(self):
        p=create_complementary_protocol();run_complementary_experiment(p,output_dir=self.root,resamples=100)
        before=(self.root/'report.json').read_bytes()
        with self.assertRaisesRegex(ValueError,'already contains results'):
            run_complementary_experiment(p,output_dir=self.root,resamples=100)
        self.assertEqual(before,(self.root/'report.json').read_bytes())

    def test_canonical_action_replay_verifies_packets_and_rejects_forged_accuracy(self):
        p=create_complementary_protocol();report=run_complementary_experiment(p,output_dir=self.root,resamples=100)
        audit=replay_report(report)
        self.assertTrue(audit['passed']);self.assertEqual(audit['runs_checked'],8)
        self.assertEqual(audit['model_calls'],0)
        tampered=copy.deepcopy(report);tampered.pop('report_hash')
        tampered['runs'][0]['outcomes']['mean_accuracy']=0
        tampered['report_hash']=fingerprint(tampered)
        audit=replay_report(tampered)
        self.assertFalse(audit['passed'])
        self.assertFalse(next(c for c in audit['checks'] if c.get('run_id')==tampered['runs'][0]['run_id'])['oracle_outcomes_match'])


if __name__=='__main__':unittest.main()
