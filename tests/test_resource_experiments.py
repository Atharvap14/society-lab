import copy
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from swarm_lab.resource_environment import offline_resource_policy,fingerprint
from swarm_lab.resource_experiments import (TASK_REMINDER,NEUTRAL_NOTE,create_resource_protocol,
    validate_resource_protocol,randomize_resource_runs,run_resource_experiment,analyze_resource_runs,
    replay_resource_report,resource_code_hashes,ResourceExecutionError,_seal)


FAKE_BACKEND={'harness':'test_callback','model':'scripted_fixture','generation':{'policy':'declared_test'}}


class ResourceExperimentTests(unittest.TestCase):
    def test_balanced_assignments_independent_seeds_and_fixed_budget(self):
        p=create_resource_protocol(trials_per_cell=4,seed=51,max_rounds=5)
        units=randomize_resource_runs(p)
        self.assertEqual(Counter(u['context'] for u in units),{'neutral':4,'task_reminder':4})
        self.assertEqual(len({u['environment_seed'] for u in units}),8)
        self.assertEqual(units,randomize_resource_runs(p))
        self.assertEqual(p['design']['maximum_subject_calls'],160)
        other=randomize_resource_runs(create_resource_protocol(trials_per_cell=4,seed=52,max_rounds=5))
        self.assertFalse({u['environment_seed'] for u in units}&{u['environment_seed'] for u in other})

    def test_protocol_and_operational_declarations_are_frozen(self):
        p=create_resource_protocol();p['environment']['max_rounds']=10
        with self.assertRaisesRegex(ValueError,'freezing'):validate_resource_protocol(p)
        for section,key,value in (('intervention','recipients',['agent-1']),('intervention','timing','After outcomes'),
                ('design','allocation','unbalanced'),('estimand','primary_outcome','waits')):
            p=create_resource_protocol();p[section][key]=value;p=_seal(p)
            with self.subTest(section=section,key=key),self.assertRaises(ValueError):validate_resource_protocol(p)

    def test_source_changes_are_rejected_before_execution(self):
        p=create_resource_protocol();different=resource_code_hashes();different['resource_environment.py']='0'*64
        with patch('swarm_lab.resource_experiments.resource_code_hashes',return_value=different):
            with self.assertRaisesRegex(ValueError,'sources changed'):run_resource_experiment(p,resamples=100)

    def test_matched_neutral_boundary_and_private_scope_without_arm_leakage(self):
        p=create_resource_protocol(max_rounds=3,release_rounds=(3,));report=run_resource_experiment(p,resamples=100)
        self.assertEqual(len(TASK_REMINDER.split()),len(NEUTRAL_NOTE.split()))
        for run in report['runs']:
            self.assertEqual(run['actual_context_insertion_recipients'],['agent-0'])
            for turn in run['turns']:
                request=turn['request']
                self.assertEqual(bool(request['context']),turn['agent_id']=='agent-0')
                if turn['agent_id']=='agent-0':self.assertEqual(request['context'],[p['contexts'][run['context']]['insertion']])
                for key in ('context','assigned_arm','seed','release_round','protocol_hash'):
                    self.assertNotIn(key,request['observation'])
                self.assertEqual(set(request),{'role','system','context','observation','action_schema'})
        self.assertEqual(report['status'],'complete');self.assertIn('infrastructure',report['evidence_scope'])

    def test_scripted_null_run_has_code_oracle_outcomes_and_valid_replay(self):
        p=create_resource_protocol(max_rounds=3,release_rounds=(3,));report=run_resource_experiment(p,resamples=100)
        self.assertEqual(report['analysis']['primary_effect']['difference'],0)
        self.assertEqual(report['analysis']['primary_effect']['p_two_sided'],1)
        self.assertEqual(report['analysis']['primary_effect']['unit'],'whole_swarm_run')
        self.assertEqual(report['analysis']['primary_effect']['n_treatment_swarms'],2)
        self.assertEqual(report['analysis']['primary_effect']['n_control_swarms'],2)
        self.assertEqual(report['analysis']['primary_effect']['ci95'],[-1,1])
        for run in report['runs']:self.assertEqual(run['outcomes']['task_completion_fraction'],.5)
        self.assertTrue(replay_resource_report(report)['passed'])

    def test_negative_and_positive_fixture_effects_are_not_forced_to_expected_direction(self):
        p=create_resource_protocol(max_rounds=3,release_rounds=(3,),subject_backend=FAKE_BACKEND)
        for reverse in (False,True):
            def policy(request):
                is_reminder=TASK_REMINDER in request['context']
                if request['role']=='agent-0' and is_reminder!=reverse:return {'action':'wait'}
                return offline_resource_policy(request)
            with self.subTest(reverse=reverse):
                report=run_resource_experiment(p,policy,resamples=100)
                self.assertEqual(report['analysis']['primary_effect']['difference'],.125 if reverse else -.125)
                self.assertTrue(replay_resource_report(report)['passed'])

    def test_primary_minimum_attainable_p_is_declared_and_not_agent_pseudoreplication(self):
        p=create_resource_protocol()
        self.assertEqual(p['pre_execution_test_resolution']['balanced_assignments'],6)
        self.assertAlmostEqual(p['pre_execution_test_resolution']['minimum_two_sided_p'],1/3)
        self.assertEqual(p['pre_execution_test_resolution']['exact_minimum_fraction'],'2/6')
        self.assertIn('Whole swarms',p['limitations'][2])
        large=create_resource_protocol(trials_per_cell=1000)
        validate_resource_protocol(large)
        self.assertTrue(large['pre_execution_test_resolution']['exact_minimum_fraction'].startswith('2/'))

    def test_all_assigned_runs_and_invalid_actions_are_retained(self):
        p=create_resource_protocol(max_rounds=2,subject_backend=FAKE_BACKEND)
        report=run_resource_experiment(p,lambda _:None,resamples=100)
        self.assertEqual(len(report['runs']),4)
        for run in report['runs']:
            self.assertEqual(run['outcomes']['invalid_actions'],8)
            self.assertEqual(run['outcomes']['task_completion_fraction'],0)
        self.assertTrue(replay_resource_report(report)['passed'])
        with self.assertRaises(ValueError):analyze_resource_runs(report['runs'][:-1],p,resamples=100)
        with self.assertRaises(ValueError):analyze_resource_runs(list(reversed(report['runs'])),p,resamples=100)

    def test_pre_subject_artifacts_and_source_archives_exist_before_callback(self):
        p=create_resource_protocol(max_rounds=2,release_rounds=(2,),subject_backend=FAKE_BACKEND)
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory);calls=[]
            def policy(request):
                self.assertTrue((output/'protocol.json').exists());self.assertTrue((output/'assignment.json').exists())
                manifest=json.loads((output/'execution-code/manifest.json').read_text())
                self.assertEqual(manifest['files'],p['execution_code_hashes'])
                self.assertEqual(manifest['timing'],'before_subject_calls')
                self.assertGreater(len(list((output/'initial_states').glob('*.json'))),0)
                self.assertTrue((output/'pending_decision.json').exists());calls.append(request)
                return offline_resource_policy(request)
            report=run_resource_experiment(p,policy,output,resamples=100)
            self.assertEqual(len(calls),32);self.assertEqual(report['status'],'complete')
            saved=json.loads((output/'report.json').read_text());self.assertTrue(replay_resource_report(saved)['passed'])
            self.assertEqual(json.loads((output/'pending_decision.json').read_text())['status'],'applied')
            with self.assertRaises(ValueError):run_resource_experiment(p,policy,output,resamples=100)

    def test_transport_failure_preserves_pending_request_without_estimate_or_retry(self):
        p=create_resource_protocol(max_rounds=2,subject_backend=FAKE_BACKEND);calls=[]
        def fail(request):calls.append(request);raise TimeoutError('Unknown transport outcome')
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ResourceExecutionError) as error:run_resource_experiment(p,fail,directory,resamples=100)
            report=error.exception.partial_report;self.assertEqual(len(calls),1)
            self.assertEqual(report['status'],'incomplete_infrastructure_failure');self.assertNotIn('analysis',report)
            self.assertEqual(report['incomplete_run']['pending_subject_request'],calls[0])
            self.assertIsNone(report['incomplete_run']['attempted_action'])
            self.assertEqual(json.loads((Path(directory)/'report.json').read_text())['status'],report['status'])
            self.assertFalse(replay_resource_report(report)['passed'])

    def test_constructor_and_analysis_failures_have_incomplete_reports(self):
        p=create_resource_protocol(max_rounds=2)
        for target in ('create_resource_environment','analyze_resource_runs'):
            with self.subTest(target=target),patch('swarm_lab.resource_experiments.'+target,side_effect=RuntimeError('Fixture failure')):
                with self.assertRaises(ResourceExecutionError) as error:run_resource_experiment(p,resamples=100)
                report=error.exception.partial_report
                self.assertIn(report['status'],('incomplete_infrastructure_failure','incomplete_analysis_failure'))
                self.assertNotIn('analysis',report);self.assertFalse(replay_resource_report(report)['passed'])

    def test_backend_and_response_adapter_mismatch_block_before_subject_calls(self):
        p=create_resource_protocol(subject_backend=FAKE_BACKEND);calls=[]
        with self.assertRaises(ValueError):run_resource_experiment(p,lambda r:calls.append(r),backend_metadata={'harness':'different'},resamples=100)
        with self.assertRaises(ValueError):run_resource_experiment(p,resamples=100)
        self.assertEqual(calls,[])
        backend={'harness':'responses','model':'requested-model','generation':{},'harness_adapter_hash':'0'*64}
        p=create_resource_protocol(subject_backend=backend)
        with tempfile.TemporaryDirectory() as directory,self.assertRaisesRegex(ValueError,'adapter source'):
            run_resource_experiment(p,lambda r:calls.append(r),directory,resamples=100)
        self.assertEqual(calls,[])

    def test_tampered_outcome_and_analysis_fail_replay_even_if_report_hash_resealed(self):
        report=run_resource_experiment(create_resource_protocol(max_rounds=2,release_rounds=(2,)),resamples=100)
        for key in ('outcome','analysis','protocol_identity'):
            bad=copy.deepcopy(report)
            if key=='outcome':bad['runs'][0]['outcomes']['resource_access_grants']=17
            elif key=='analysis':bad['analysis']['primary_effect']['difference']=.9
            else:bad['protocol_hash']='0'*64
            bad.pop('report_hash');bad['report_hash']=fingerprint(bad)
            with self.subTest(key=key):self.assertFalse(replay_resource_report(bad)['passed'])

    def test_reporting_callback_failure_does_not_drop_or_replace_swarms(self):
        def callback(_):raise RuntimeError('Display-only failure')
        report=run_resource_experiment(create_resource_protocol(max_rounds=2),on_progress=callback,resamples=100)
        self.assertEqual(report['status'],'complete');self.assertEqual(len(report['runs']),4)
        self.assertEqual(len(report['reporting_warnings']),4)

    def test_note_and_simulation_parameter_boundaries_fail_explicitly(self):
        for args in ({'trials_per_cell':1},{'trials_per_cell':True},{'neutral_text':NEUTRAL_NOTE+' extra'},
                {'reminder_text':''},{'release_rounds':(50,)},{'computer_work_steps':0}):
            with self.subTest(args=args),self.assertRaises(ValueError):create_resource_protocol(**args)
        with self.assertRaises(ValueError):run_resource_experiment(create_resource_protocol(),resamples=0)


if __name__=='__main__':unittest.main()
