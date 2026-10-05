"""Focused staging fixtures: no registry or provider calls."""
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from swarm_lab import revision_relay_experiments as relay
CALLBACK={"harness":"callback","model":"fixture","generation":{
    "max_output_tokens":600,"temperature":"provider_default","sampling_seed":"not_set"}}


class RevisionRelayExperimentTests(unittest.TestCase):
    def protocol(self,**kwargs):return relay.create_revision_relay_protocol(**kwargs)
    def callback_protocol(self,**kwargs):return self.protocol(subject_backend=CALLBACK,**kwargs)
    def reseal(self,report):return relay._seal(report,"report_hash")

    def test_scripted_default_pairing_four_decisions_oracle_and_archive(self):
        p=self.protocol();report=relay.run_revision_relay_experiment(p)
        self.assertEqual(len(report['runs']),8)
        self.assertEqual(report['model_calls'],0)
        self.assertEqual(report['analysis']['mean_interaction'],0)
        self.assertIsNone(report['analysis']['p_value'])
        self.assertFalse(report['analysis']['interval']['available'])
        self.assertIsNone(report['analysis']['interval']['bounds'])
        for r in report['runs']:
            self.assertEqual(r['outcomes']['C_final_correct'],1)
            self.assertEqual([(t['agent_id'],t['ordinal_boundary']) for t in r['turns']],[('B',2),('C',3),('B',5),('C',7)])
            self.assertEqual(r['counts']['subject_call_attempts'],4)
            for b in r['boundaries']:
                req=b['request'];self.assertNotIn('assignment',req);self.assertNotIn('seed',req)
                self.assertNotIn('oracle_total',req['observation'])
                if req['agent_id']=='B':self.assertNotIn('your_private_residue',req['observation'])
        group=report['runs'][:4]
        self.assertEqual(len({relay._hash(r['exogenous_identity']) for r in group}),1)
        self.assertGreater(len({relay._hash(r['initial_state']) for r in group}),1)
        self.assertTrue(relay.replay_revision_relay_report(report)['passed'])
        with tempfile.TemporaryDirectory() as d:
            saved=relay.run_revision_relay_experiment(p,output_dir=Path(d)/'run')
            self.assertTrue(relay.replay_revision_relay_report(saved,output_dir=Path(d)/'run')['passed'])
            code=Path(d)/'run'/'execution-code'/'revision_relay_env.py'
            code.write_bytes(code.read_bytes()+b'\n# changed archive\n')
            self.assertFalse(relay.replay_revision_relay_report(saved,output_dir=Path(d)/'run')['passed'])

    def test_typed_protocol_false_defaults_and_resealed_generated_fields(self):
        for kwargs in ({'blocks':True},{'seed':1.0},{'source_refs':False},{'source_refs':[]},
                       {'subject_backend':{}},{'interval_assumptions':{}},{'alpha':True}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):self.protocol(**kwargs)
        p=self.protocol()
        for key,value in (('maximum_subject_calls',32.0),('maximum_teams',True)):
            changed=copy.deepcopy(p);changed['design'][key]=value;changed=relay._seal(changed,'protocol_hash')
            with self.assertRaises(ValueError):relay.validate_revision_relay_protocol(changed)
        changed=copy.deepcopy(p);changed['surprise']='metadata';changed=relay._seal(changed,'protocol_hash')
        with self.assertRaises(ValueError):relay.validate_revision_relay_protocol(changed)

    def test_backend_substitution_and_responses_archive_gate(self):
        with self.assertRaises(ValueError):relay.run_revision_relay_experiment(self.protocol(),agent_runner=lambda r:{'action':'wait'})
        with self.assertRaises(ValueError):relay.run_revision_relay_experiment(self.callback_protocol())
        backend={**CALLBACK,'harness':'responses','harness_adapter_hash':relay.revision_relay_code_hashes()['harness.py']}
        p=self.protocol(subject_backend=backend)
        with self.assertRaises(ValueError):relay.run_revision_relay_experiment(p,agent_runner=lambda r:{'action':'wait'})
        with self.assertRaises(ValueError):relay.run_revision_relay_experiment(self.callback_protocol(),agent_runner=lambda r:{'action':'wait'},backend_metadata=relay.OFFLINE_BACKEND)

    def test_scoped_draft_retention_policy_exercises_negative_interaction(self):
        def policy(request):
            o=request['observation']
            if request['agent_id']=='C' and o['decision_phase']=='final':
                direct=any(d['sender']=='A' and d['ordinal_boundary']==6 and
                           any(r['artifact_id']=='artifact-main' and r['revision']==2 for r in d['records'])
                           for d in o['received_deliveries'])
                if not direct:return {'action':'retain'}
            return relay.revision_relay_scoped_policy(request)
        report=relay.run_revision_relay_experiment(self.callback_protocol(),agent_runner=policy)
        self.assertEqual(report['analysis']['mean_interaction'],-1)
        self.assertTrue(all(b['difference']==-1 for b in report['analysis']['block_contrasts']))
        self.assertTrue(relay.replay_revision_relay_report(report)['passed'])
        self.assertIsNone(report['model_calls'])
        self.assertEqual(report['backend']['provider_origin'],'not_attested')

    def test_conditional_interval_wide_and_never_interaction_test(self):
        p=self.protocol(interval_assumptions={'independent_blocks_declared':True,'stable_subject_backend_declared':True})
        report=relay.run_revision_relay_experiment(p);a=report['analysis']
        self.assertEqual(a['interval']['bounds'],[-2,2]);self.assertFalse(a['interval']['assumptions_attested'])
        self.assertIsNone(a['interaction_randomization_test']);self.assertIsNone(a['p_value'])

    def test_invalid_nonfinite_and_oversized_outputs_are_bounded_replayable_behavior(self):
        for output in (float('nan'),{'action':'forward','record_ids':[],'message':'x'*50000},object(),
                       [None]*17,{str(i):None for i in range(33)}):
            def policy(request):
                if request['agent_id']=='B' and not request['observation']['your_action_history']:return output
                return relay.revision_relay_scoped_policy(request)
            with self.subTest(output=type(output).__name__):
                report=relay.run_revision_relay_experiment(self.callback_protocol(blocks=1),agent_runner=policy)
                self.assertEqual(report['status'],'complete')
                self.assertTrue(relay.replay_revision_relay_report(report)['passed'])
                self.assertEqual(report['runs'][0]['turns'][0]['action'],relay.world.INVALID_RETAINED_ACTION)
                self.assertIsNone(report['runs'][0]['turns'][0]['action_retention']['original_output_hash'])

    def test_deterministic_credential_sanitization_precedes_world_and_persistence(self):
        sentinel='sk-proj-'+'fictionalCredentialFixture'*3
        def policy(request):
            action=relay.revision_relay_scoped_policy(request)
            if request['agent_id']=='B':action['message']=sentinel
            return action
        report=relay.run_revision_relay_experiment(self.callback_protocol(blocks=1),agent_runner=policy)
        self.assertNotIn(sentinel,json.dumps(report));self.assertIn('[REDACTED_CREDENTIAL]',json.dumps(report))
        self.assertTrue(relay.replay_revision_relay_report(report)['passed'])
        self.assertEqual(report['runs'][0]['turns'][0]['action_retention']['status'],'sanitized_before_execution')

    def partial(self):
        calls=0
        def failure(request):
            nonlocal calls
            calls+=1
            if calls==3:raise RuntimeError('fixture transport failure')
            return relay.revision_relay_scoped_policy(request)
        with self.assertRaises(relay.RevisionRelayExecutionError) as caught:
            relay.run_revision_relay_experiment(self.callback_protocol(),agent_runner=failure)
        return caught.exception.partial_report

    def test_unknown_transport_retains_grid_without_estimate_or_complete_proof(self):
        report=self.partial();self.assertEqual(len(report['runs']),8);self.assertIsNone(report['analysis'])
        self.assertEqual(report['runs'][0]['status'],'incomplete')
        self.assertEqual(report['runs'][0]['boundaries'][-1]['invocation_status'],'attempted_unknown')
        self.assertTrue(all(r['status']=='not_started' for r in report['runs'][1:]))
        proof=relay.replay_revision_relay_report(report)
        self.assertFalse(proof['passed']);self.assertTrue(proof['partial_trace_consistent'])
        self.assertFalse(proof['quantitative_available'])

    def test_pre_subject_materialization_failure_after_initial_worlds_replays_known_prefix(self):
        original=relay._environment;calls=0
        def create(*args):
            nonlocal calls
            calls+=1
            if calls==3:raise RuntimeError('world fixture')
            return original(*args)
        with patch.object(relay,'_environment',side_effect=create),self.assertRaises(relay.RevisionRelayExecutionError) as caught:
            relay.run_revision_relay_experiment(self.protocol())
        report=caught.exception.partial_report
        self.assertEqual(report['failure']['phase'],'materialize')
        self.assertEqual(report['runs'][2]['status'],'incomplete')
        self.assertTrue(all(r['counts']['subject_call_attempts']==0 for r in report['runs']))
        self.assertTrue(relay.replay_revision_relay_report(report)['partial_trace_consistent'])

    def test_progress_failure_preserves_completed_world_but_no_study_estimate(self):
        with self.assertRaises(relay.RevisionRelayExecutionError) as caught:
            relay.run_revision_relay_experiment(self.protocol(),on_progress=lambda x:(_ for _ in ()).throw(RuntimeError('progress')))
        report=caught.exception.partial_report
        self.assertEqual(report['runs'][0]['status'],'complete');self.assertEqual(len(report['runs'][0]['turns']),4)
        self.assertIsNone(report['analysis']);self.assertTrue(relay.replay_revision_relay_report(report)['partial_trace_consistent'])

    def test_resealed_requests_lineage_counts_and_partial_evidence_cannot_pass(self):
        original=relay.run_revision_relay_experiment(self.protocol())
        changes=[]
        changed=copy.deepcopy(original);changed['runs'][0]['boundaries'][0]['request']['observation']['known_records'][0]['value']+=1;changes.append(changed)
        changed=copy.deepcopy(original);changed['runs'][0]['counts']['applied_actions']=4.0;changes.append(changed)
        changed=copy.deepcopy(original);changed['runs'][0]['outcomes']['C_final_correct']=True;changes.append(changed)
        changed=copy.deepcopy(original);changed['runs'][0]['turns'][0]['action']['record_ids']=['forged'];changes.append(changed)
        partial=self.partial();changed=copy.deepcopy(partial);changed['runs'][0]['initial_state']=None;changed['runs'][0]['exogenous_identity']=None;changes.append(changed)
        changed=copy.deepcopy(partial);changed['runs'][1]['boundaries']=[copy.deepcopy(partial['runs'][0]['boundaries'][0])];changes.append(changed)
        changed=copy.deepcopy(partial);changed['runs'][0]['boundaries'][-1]['attempted_action']={'action':'wait'};changes.append(changed)
        changed=copy.deepcopy(partial);changed['runs'][1]=copy.deepcopy(original['runs'][1]);changes.append(changed)
        for changed in changes:
            proof=relay.replay_revision_relay_report(self.reseal(changed))
            self.assertFalse(proof['passed']);self.assertFalse(proof.get('partial_trace_consistent',False),proof)

    def test_fresh_directory_current_source_pins_and_no_artifact_overwrite(self):
        p=self.protocol()
        with tempfile.TemporaryDirectory() as d:
            path=Path(d);old=path/'report.json';old.write_bytes(b'original')
            with self.assertRaises(ValueError):relay.run_revision_relay_experiment(p,output_dir=path)
            self.assertEqual(old.read_bytes(),b'original')
        with patch.object(relay,'revision_relay_code_hashes',return_value={**relay.revision_relay_code_hashes(),'revision_relay_env.py':'0'*64}):
            with self.assertRaises(ValueError):relay.run_revision_relay_experiment(p)

    def test_same_protocol_different_result_cannot_borrow_execution_archive(self):
        p=self.callback_protocol(blocks=1)
        with tempfile.TemporaryDirectory() as d:
            directory=Path(d)/'run'
            original=relay.run_revision_relay_experiment(p,agent_runner=relay.revision_relay_scoped_policy,output_dir=directory)
            other=relay.run_revision_relay_experiment(p,agent_runner=lambda r:{'action':'wait'})
            self.assertTrue(relay.replay_revision_relay_report(other)['passed'])
            other['local_artifacts_before_subject_calls']=True;other=self.reseal(other)
            self.assertTrue(relay.replay_revision_relay_report(original,output_dir=directory)['passed'])
            self.assertFalse(relay.replay_revision_relay_report(other,output_dir=directory)['passed'])

    def test_unknown_report_payload_and_false_sanitization_identity_are_rejected(self):
        report=relay.run_revision_relay_experiment(self.protocol(blocks=1))
        changed=copy.deepcopy(report);changed['raw_provider_payload']={'unknown':'unregistered'}
        self.assertFalse(relay.replay_revision_relay_report(self.reseal(changed))['passed'])
        changed=copy.deepcopy(report);b=changed['runs'][0]['boundaries'][0];t=changed['runs'][0]['turns'][0]
        b['action_retention']['status']='sanitized_before_execution';t['action_retention']['status']='sanitized_before_execution'
        self.assertFalse(relay.replay_revision_relay_report(self.reseal(changed))['passed'])

    def test_archive_binary_input_ceiling_reads_at_most_limit_plus_one(self):
        import io
        class Stream(io.BytesIO):
            def __init__(self):super().__init__(b'x'*200);self.requests=[]
            def read(self,size=-1):self.requests.append(size);return super().read(size)
        stream=Stream()
        class File:
            def open(self,mode):return stream
        with self.assertRaises(ValueError):relay._read_binary(File(),16)
        self.assertEqual(stream.requests,[17])


if __name__=='__main__':unittest.main(verbosity=2)
