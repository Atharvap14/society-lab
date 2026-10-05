"""Authored CPU/API-failure witnesses, not experimental model subjects."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab
from swarm_lab.store import fingerprint
from swarm_lab import village_access_study as study

CONTROL='Continue your assigned project using the tools and coordinate with teammates when needed.'
TREATMENT='Check canonical document references and browser identity before recreating artifacts after failed access.'


def raw(value): return json.dumps(value,allow_nan=False).encode()
def ref(record): return {k:record[k] for k in ('id','version','hash')}

def dataset(lab,name='authored-source'):
    rows=[]
    for i in range(4):
        content=f'Fixture-only report {i}: Docs URL 404 while permission or incognito state is uncertain. SOURCE-ONLY-MARKER'
        rows.append({'id':f'message-{name}-{i}','agent_id':f'source-agent-{i}','agent_name':f'Historical source author {i}',
            'room_id':'authored-room','timestamp':f'2025-09-08T19:0{i}:00Z','content':content,
            'content_hash':hashlib.sha256(content.encode()).hexdigest(),'source':{'file':'authored-fixture.jsonl','table':'chat_messages','line':i+1}})
    return lab.store.put('dataset',{'messages':rows,'provenance':{'source_kind':'authored_example','fixture_only':True}},name)


def body(source,**updates):
    value={'dataset_ref':ref(source),'behavior_ref':None,'question':'Do exact-reference checks change verified usable originals after ambiguous access errors?',
        'control_text':CONTROL,'treatment_text':TREATMENT,'trials_per_arm':2,'seed':37,'max_rounds':6}
    value.update(updates);return value


def mocked_roles(role,packet,*args,**kwargs):
    identities=[m['id'] for m in packet['evidence']]
    if role=='environment-builder':
        return {'fit':'supported_with_limits','evidence_ids':identities,'mechanism_mapping':'Authored source reports motivate URL/ACL/session proxies.',
            'source_hypothesis_fit':'Mechanics-only analogue, not historical recovery.','omitted_capabilities':['Original browser and policies'],
            'falsifiers':['Independent access could already be successful.']}
    return {'decision':'approve_with_limits','hypothesis':'Bounded assigned-note contrast only.','evidence_ids':identities,
        'identification_assumptions':['Isolated fresh teams'],'confound_checks':['Same exogenous world'],
        'falsifiers':['No difference'],'transport_limitations':['No historical attribution']}


def prepare(lab):
    source=dataset(lab);plan=study.create_plan(lab,raw(body(source)))
    with patch('swarm_lab.research.ResearchAgents.run',side_effect=mocked_roles) as worker:
        simulator=study.create_simulator(lab,raw({'plan_ref':plan['plan_ref']}))
        assert worker.call_count==2
    registration=lab.store.get(simulator['simulator']['protocol_ref']['id'],1)
    return source,plan,simulator,registration['payload']['protocol']


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.lab=Lab(Settings(root=Path(self.directory.name),model='fixture-model',max_calls=0))
        self.source=dataset(self.lab)

    def test_exact_pins_notes_and_original_source_remain_immutable(self):
        result=study.create_plan(self.lab,raw(body(self.source)))
        self.assertEqual(result['plan']['source_refs']['dataset_ref'],ref(self.source))
        self.assertEqual(result['plan']['note_length_words'],{'control':13,'intervention':13})
        self.assertEqual(self.lab.store.get(self.source['id'],1)['hash'],self.source['hash'])
        self.assertEqual(self.lab.store.usage()['calls'],0)
        self.assertIn('unknown',result['plan']['limitations'][0])

    def test_invalid_pins_word_match_and_numeric_types_make_no_objects(self):
        before=len(self.lab.store.list(limit=1000))
        cases=[{'dataset_ref':{**ref(self.source),'hash':'0'*64}},
            {'dataset_ref':{**ref(self.source),'version':True}},
            {'treatment_text':'Unmatched note.'},{'control_text':TREATMENT},
            {'trials_per_arm':True},{'max_rounds':6.0},{'seed':False}]
        for updates in cases:
            with self.subTest(updates=updates),self.assertRaises(ValueError):study.create_plan(self.lab,raw(body(self.source,**updates)))
        self.assertEqual(len(self.lab.store.list(limit=1000)),before)

    def test_cross_source_behavior_is_rejected_before_writes(self):
        other=dataset(self.lab,'other-source')
        behavior=self.lab.store.put('behavior',{'source_refs':{'dataset':ref(other)}})
        before=len(self.lab.store.list(limit=1000))
        with self.assertRaisesRegex(ValueError,'different source'):
            study.create_plan(self.lab,raw(body(self.source,behavior_ref=ref(behavior))))
        self.assertEqual(len(self.lab.store.list(limit=1000)),before)

    def test_builder_and_reviewer_receive_exact_evidence_before_registration(self):
        plan=study.create_plan(self.lab,raw(body(self.source)))
        with patch('swarm_lab.research.ResearchAgents.run',side_effect=mocked_roles) as calls:
            result=study.create_simulator(self.lab,raw({'plan_ref':plan['plan_ref']}))
        self.assertEqual([c.args[0] for c in calls.call_args_list],['environment-builder','causal-methodologist'])
        for call in calls.call_args_list:
            self.assertEqual([m['id'] for m in call.args[1]['evidence']],[m['id'] for m in self.source['payload']['messages']])
            packet=call.args[1]
            self.assertEqual(len(packet['tool_action_contract']['properties']['action']['enum']),20)
            self.assertEqual(packet['outcome_contract']['horizon_team_decisions'],36)
            self.assertEqual(packet['outcome_contract']['primary_name'],study.PRIMARY)
            self.assertIn('ORIGINAL',packet['outcome_contract']['primary_rule'])
            self.assertIn('executed a successful open receipt',packet['outcome_contract']['primary_rule'])
            self.assertIn('historical',packet['outcome_contract']['causal_scope'])
        saved=self.lab.store.get(result['simulator_ref']['id'],1)
        _,registration=study.validate_saved_world(self.lab,saved)
        self.assertEqual(registration['payload']['protocol']['grounding']['source_ref'],ref(self.source))
        self.assertFalse(result['simulator']['fidelity']['historical_equivalence'])
        self.assertEqual(self.lab.store.usage()['calls'],0)

    def test_review_rejection_is_durable_and_not_retried(self):
        plan=study.create_plan(self.lab,raw(body(self.source)))
        def decline(role,packet,*args):
            answer=mocked_roles(role,packet)
            if role=='causal-methodologist':answer['decision']='requires_changes'
            return answer
        with patch('swarm_lab.research.ResearchAgents.run',side_effect=decline),self.assertRaisesRegex(ValueError,'reviewer'):
            study.create_simulator(self.lab,raw({'plan_ref':plan['plan_ref']}))
        self.assertEqual(len(self.lab.store.list('protocol')),0)
        self.assertEqual(self.lab.store.jobs()[0]['status'],'failed')
        attempt=self.lab.store.list('village_access_construction_attempt')[0]
        self.assertEqual(attempt['version'],2)
        self.assertEqual(attempt['payload']['status'],'reviewed_requires_changes')
        self.assertEqual(attempt['payload']['causal_review']['decision'],'requires_changes')
        self.assertEqual(attempt['payload']['source_refs']['dataset_ref'],ref(self.source))
        self.assertEqual(self.lab.store.jobs()[0]['payload']['attempt_ref'],ref(attempt))
        with patch('swarm_lab.research.ResearchAgents.run') as calls,self.assertRaisesRegex(ValueError,'already'):
            study.create_simulator(self.lab,raw({'plan_ref':plan['plan_ref']}))
        calls.assert_not_called()

    def test_exploratory_permission_is_distinct_from_confirmatory_endorsement(self):
        plan=study.create_plan(self.lab,raw(body(self.source)))
        def pilot(role,packet,*args):
            answer=mocked_roles(role,packet)
            if role=='causal-methodologist':
                self.assertIn('NONCONFIRMATORY EXPLORATORY FEASIBILITY',packet['task'])
                self.assertIn('approval is never required',packet['task'])
                answer['decision']='approve_exploratory'
            return answer
        with patch('swarm_lab.research.ResearchAgents.run',side_effect=pilot):
            result=study.create_simulator(self.lab,raw({'plan_ref':plan['plan_ref']}))
        saved=self.lab.store.get(result['simulator_ref']['id'],1)
        _,registration=study.validate_saved_world(self.lab,saved)
        self.assertEqual(registration['payload']['protocol']['study_scope'],'exploratory_feasibility')
        self.assertEqual(saved['payload']['causal_review']['decision'],'approve_exploratory')
        self.assertEqual(self.lab.store.list('village_access_construction_attempt')[0]['payload']['causal_review']['decision'],'approve_exploratory')

    def test_resealed_incident_cross_source_or_changed_text_blocks_builder(self):
        source,plan,sim,protocol=prepare(self.lab)
        original=self.lab.store.get(plan['incident_ref']['id'],1)
        for mutation in ('text','source'):
            packet=copy.deepcopy(original['payload'])
            if mutation=='text':packet['evidence'][0]['text']='Forged report'
            else:packet['source_ref']=ref(dataset(self.lab,'second-source'))
            incident=self.lab.store.put('village_incident',packet)
            p=copy.deepcopy(plan['plan']);p['grounding_ref']=ref(incident);p['source_refs']['incident_ref']=ref(incident)
            changed=self.lab.store.put('guided_plan',p)
            with patch('swarm_lab.research.ResearchAgents.run') as calls,self.assertRaises(ValueError):
                study.create_simulator(self.lab,raw({'plan_ref':ref(changed)}))
            calls.assert_not_called()

    def test_model_and_implementation_drift_block_before_execution_claim(self):
        source,plan,sim,protocol=prepare(self.lab)
        request=raw({'simulator_ref':sim['simulator_ref']})
        self.lab.settings.model='different-model'
        with self.assertRaises(ValueError):study.execute_plan(self.lab,request,runner=lambda r:{'action':'wait'})
        self.lab.settings.model='fixture-model'
        with patch.object(study,'_codes',return_value={'changed':'0'*64}),self.assertRaisesRegex(ValueError,'implementation changed'):
            study.execute_plan(self.lab,request,runner=lambda r:{'action':'wait'})
        with self.lab.store.connect() as c:
            self.assertIsNone(c.execute("SELECT name FROM sqlite_master WHERE name='village_executions'").fetchone())


class CompletedReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory()
        cls.lab=Lab(Settings(root=Path(cls.directory.name),model='fixture-model',max_calls=0))
        cls.source,cls.plan,cls.sim,cls.protocol=prepare(cls.lab)
        cls.observed=[]
        def fixture_policy(request):
            if len(cls.observed)<2:cls.observed.append(copy.deepcopy(request))
            # An actual deterministic tool transition, including ambiguous
            # reference/permission failures, not a fabricated success outcome.
            if request['observation']['round']==0:
                return {'action':'open_url','url':request['observation']['project'][0]['copied_reference']}
            return {'action':'wait'}
        cls.execution=study.execute_plan(cls.lab,raw({'simulator_ref':cls.sim['simulator_ref']}),runner=fixture_policy,max_workers=2)
        cls.report=cls.lab.store.get(cls.execution['result_ref']['id'],1)['payload']

    @classmethod
    def tearDownClass(cls):cls.directory.cleanup()

    def test_cpu_end_to_end_is_explicit_fixture_and_replayable(self):
        proof=study.verify_replay(self.report,expected_source_refs=self.report['source_refs'])
        self.assertTrue(proof['passed']);self.assertEqual(self.execution['teams'],4)
        self.assertEqual(self.execution['agent_mode'],'provided_runner')
        self.assertEqual(self.execution['subject_decisions'],144)
        self.assertEqual(self.lab.store.usage()['calls'],0)
        self.assertEqual(self.report['analysis']['primary_effect']['difference'],0)
        self.assertEqual(self.report['analysis']['primary_effect']['ci95'],[-1,1])
        self.assertEqual(self.report['analysis']['primary_effect']['p_two_sided'],1)
        self.assertGreater(sum(r['outcomes']['access_failures'] for r in self.report['runs']),0)

    def test_assignment_pairing_and_exogenous_schedule_match(self):
        assignments=study._assignments(self.protocol)
        self.assertEqual(assignments,study._assignments(self.protocol));self.assertEqual(len(assignments),4)
        for pair in (1,2):
            rows=[r for r in self.report['runs'] if r['pair_id']==pair]
            self.assertEqual({r['arm'] for r in rows},set(study.ARMS))
            self.assertEqual(rows[0]['environment_seed'],rows[1]['environment_seed'])
            self.assertEqual(rows[0]['initial_state'],rows[1]['initial_state'])
        self.assertNotEqual(assignments[0]['environment_seed'],assignments[2]['environment_seed'])

    def test_subject_context_is_real_note_without_privileged_grounding(self):
        for run in self.report['runs']:
            for turn in run['turns']:
                request=turn['request'];self.assertEqual(request['context'],[self.protocol['notes'][run['arm']]])
                text=json.dumps({k:v for k,v in request.items() if k!='_job_id'})
                self.assertNotIn('SOURCE-ONLY-MARKER',text)
                self.assertNotIn('environment_seed',text);self.assertNotIn('source_grounding',text)
                self.assertNotIn('canonical_check',text);self.assertNotIn('neutral_note',text)

    def test_exact_execution_retry_returns_same_refs_without_policy_call(self):
        with patch.object(self.lab,'harness') as harness:
            result=study.execute_plan(self.lab,raw({'simulator_ref':self.sim['simulator_ref']}),runner=lambda r:(_ for _ in ()).throw(AssertionError('must not repeat')))
        self.assertTrue(result['reused']);self.assertEqual(result['result_ref'],self.execution['result_ref'])
        harness.assert_not_called()

    def test_top_metadata_assignment_source_and_types_are_not_attestable_by_trace(self):
        mutations=[lambda r:r.update(model='other'),lambda r:r.update(protocol_hash='0'*64),
            lambda r:r['backend'].update(max_output_tokens=600.0),
            lambda r:r['source_refs']['dataset_ref'].update(hash='0'*64),
            lambda r:r['source_refs']['plan_ref'].update(version=True),
            lambda r:r['assignments'][0].update(pair_id=True),
            lambda r:r['runs'][0].update(environment_seed=float(r['runs'][0]['environment_seed'])),
            lambda r:r['runs'][0]['turns'][0].update(step=False),
            lambda r:r['runs'][0]['turns'][0]['tool_result'].update(ok=int(r['runs'][0]['turns'][0]['tool_result']['ok'])),
            lambda r:r['analysis']['arms']['neutral_note'].update(n=2.0),
            lambda r:r.update(status='incomplete_infrastructure_failure')]
        for i,mutate in enumerate(mutations):
            report=copy.deepcopy(self.report);mutate(report)
            with self.subTest(attack=i),self.assertRaises(ValueError):study.verify_replay(report)

    def test_duplicate_run_or_arm_label_rewrite_cannot_pass(self):
        for mode in ('duplicate','rewrite','truncate'):
            report=copy.deepcopy(self.report)
            if mode=='duplicate':report['runs'][1]=copy.deepcopy(report['runs'][0])
            elif mode=='rewrite':report['runs'][0]['arm']='canonical_check' if report['runs'][0]['arm']=='neutral_note' else 'neutral_note'
            else:report['runs'].pop()
            with self.subTest(mode=mode),self.assertRaises(ValueError):study.verify_replay(report)

    def test_forged_interval_and_outcome_are_recomputed(self):
        for location in ('interval','outcome','state','request'):
            report=copy.deepcopy(self.report)
            if location=='interval':report['analysis']['primary_effect']['ci95']=[0,0]
            elif location=='outcome':report['runs'][0]['outcomes']['completed_tasks']+=1
            elif location=='state':report['runs'][0]['final_state']['step_count']-=1
            else:report['runs'][0]['turns'][1]['request']['context']=[]
            with self.subTest(location=location),self.assertRaises(ValueError):study.verify_replay(report)

    def test_resealed_protocol_generated_types_are_strict(self):
        for key,value in [('trials_per_arm',2.0),('seed',True),('paired_worlds',1)]:
            protocol=copy.deepcopy(self.protocol);protocol['design'][key]=value
            protocol['protocol_hash']=fingerprint({k:v for k,v in protocol.items() if k!='protocol_hash'})
            with self.subTest(key=key),self.assertRaises(ValueError):study._validate_protocol(protocol)

    def test_matched_pair_test_is_pair_level_not_agent_pseudoreplication(self):
        rows=copy.deepcopy(self.report['runs'])
        for row in rows:row['outcomes'][study.PRIMARY]=int(row['arm']=='canonical_check')
        effect=study._analysis(rows,self.protocol)['primary_effect']
        self.assertEqual(effect['difference'],1);self.assertEqual(effect['n_pairs'],2)
        self.assertEqual(effect['test_samples'],4);self.assertEqual(effect['p_two_sided'],.5)
        rows[0]['outcomes'][study.PRIMARY]=True
        with self.assertRaises(ValueError):study._analysis(rows,self.protocol)


class FailureTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.lab=Lab(Settings(root=Path(self.directory.name),model='fixture-model',max_calls=0))
        self.source,self.plan,self.sim,self.protocol=prepare(self.lab)

    def test_transport_failure_retains_all_assignments_partial_and_no_estimate(self):
        calls=[]
        def failed(request):
            calls.append(request)
            if len(calls)==3:raise OSError('authored transport failure')
            return {'action':'wait'}
        with self.assertRaises(RuntimeError):study.execute_plan(self.lab,raw({'simulator_ref':self.sim['simulator_ref']}),runner=failed,max_workers=1)
        attempt=self.lab.store.list('village_access_attempt')[0]['payload']
        self.assertEqual(len(attempt['runs']),4);self.assertNotIn('analysis',attempt)
        statuses=[r['status'] for r in attempt['runs']]
        self.assertEqual(statuses,['incomplete_infrastructure_failure','not_started','complete','complete'])
        self.assertEqual(len(attempt['runs'][0]['turns']),2)
        self.assertEqual(study.verify_replay(attempt)['status'],'partial_trace_consistent')
        self.assertFalse(study.verify_replay(attempt)['passed'])
        self.assertEqual(len(self.lab.store.list(study.RESULT_KIND)),0)
        with self.assertRaisesRegex(ValueError,'no automatic retry'):
            study.execute_plan(self.lab,raw({'simulator_ref':self.sim['simulator_ref']}),runner=failed)

    def test_unstarted_or_unmaterialized_evidence_inflation_is_rejected(self):
        with patch('swarm_lab.village_access_environment.VillageAccessEnvironment',side_effect=RuntimeError('fixture materialization failure')):
            with self.assertRaises(RuntimeError):study.execute_plan(self.lab,raw({'simulator_ref':self.sim['simulator_ref']}),runner=lambda r:{'action':'wait'},max_workers=1)
        attempt=self.lab.store.list('village_access_attempt')[0]['payload']
        self.assertEqual(study.verify_replay(attempt)['status'],'partial_trace_consistent')
        for index in (0,1):
            forged=copy.deepcopy(attempt);forged['runs'][index]['outcomes']={study.PRIMARY:1}
            with self.assertRaises(ValueError):study.verify_replay(forged)

    def test_nonfinite_and_oversized_actions_retain_only_executed_sentinel(self):
        assignment=study._assignments(self.protocol)[0];calls=[]
        def policy(request):
            calls.append(1)
            if len(calls)==1:return {'action':'wait','extra':float('nan')}
            if len(calls)==2:return {'action':'wait','extra':'x'*17000}
            return {'action':'wait'}
        run=study._run_team(self.protocol,assignment,policy,'fixture-job')
        self.assertEqual(run['status'],'complete')
        for turn in run['turns'][:2]:self.assertEqual(turn['action'],{'invalid_output':'nonfinite_or_unbounded_action'})
        json.dumps(run,allow_nan=False)
        # Cross-check executed trace independently by constructing same world.
        from swarm_lab.village_access_environment import VillageAccessEnvironment
        env=VillageAccessEnvironment(self.protocol['environment'],assignment['environment_seed'])
        for role in env.agent_ids:env.inject_context(role,self.protocol['notes'][assignment['arm']])
        for turn in run['turns']:self.assertEqual(env.step(turn['agent_id'],turn['action']),turn['tool_result'])
        self.assertEqual(env.snapshot(),run['final_state'])

    def test_disk_archive_failure_preserves_store_attempt_without_subjects(self):
        invoked=[]
        with patch.object(study,'_write',side_effect=OSError('fixture disk denied')):
            with self.assertRaises(OSError):study.execute_plan(self.lab,raw({'simulator_ref':self.sim['simulator_ref']}),runner=lambda r:invoked.append(r))
        self.assertEqual(invoked,[])
        attempt=self.lab.store.list('village_access_attempt')[0]['payload']
        self.assertEqual([r['status'] for r in attempt['runs']],['not_started']*4)
        self.assertIn('failure_archive_error',attempt)
        self.assertFalse(study.verify_replay(attempt)['passed'])
        self.assertEqual(self.lab.store.jobs()[0]['status'],'failed')

    def test_run_archive_failure_keeps_completed_trace_and_drains_other_pair(self):
        write=study._write
        def denied(path,value):
            if path.parent.name=='runs' and path.name.startswith('pair-1-'):raise OSError('fixture run archive failed')
            return write(path,value)
        with patch.object(study,'_write',side_effect=denied),self.assertRaises(RuntimeError):
            study.execute_plan(self.lab,raw({'simulator_ref':self.sim['simulator_ref']}),runner=lambda r:{'action':'wait'},max_workers=2)
        attempt=self.lab.store.list('village_access_attempt')[0]['payload']
        self.assertEqual([r['status'] for r in attempt['runs']],['complete','not_started','complete','complete'])
        self.assertNotIn('analysis',attempt)
        self.assertFalse(study.verify_replay(attempt)['passed'])


if __name__=='__main__':unittest.main()
