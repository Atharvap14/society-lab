"""Authored temp-store/replay witnesses; real product executions use live harness."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab
from swarm_lab.store import fingerprint
from swarm_lab import reference_repair_study as study
from swarm_lab.reference_repair_environment import PRIMARY
from tests.test_village_access_study import dataset,raw,mocked_roles

CONTROL='Continue the shared document task using available tools, coordinate with your teammate, and report progress within the budget.'
ACTIVE='Before retrying a broken link, verify the document title, exact reference, and current browser account with your teammate.'


def prepare(lab):
    source=dataset(lab)
    plan=study.create_plan(lab,raw({'dataset_ref':study._ref(source),'behavior_ref':None,
        'question':'In a new one-document proxy, does the note package change actual checker access after a broken reference?',
        'control_text':CONTROL,'treatment_text':ACTIVE,'trials_per_arm':2,'seed':71231,'max_rounds':8}))
    def roles(role,packet,*args):
        result=mocked_roles(role,packet)
        if role=='causal-methodologist':result['decision']='approve_exploratory'
        return result
    with patch('swarm_lab.research.ResearchAgents.run',side_effect=roles):
        simulator=study.create_simulator(lab,raw({'plan_ref':plan['plan_ref']}))
    return source,plan,simulator


def fixture_policy(request):
    # A legal CPU-only witness of independent title search/access. No model claim.
    o=request['observation'];history=o['your_action_history']
    if not history:return {'action':'drive_search','query':o['target_document']['title']}
    if history[-1]['action']['action']=='drive_search':
        return {'action':'open_url','url':o['your_last_tool_result']['matches'][0]['view_url']}
    if history[-1]['action']['action']=='open_url':return {'action':'inspect_document'}
    return {'action':'wait'}


class RecoveryStudyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.lab=Lab(Settings(root=Path(self.temp.name),model='fixture-model',max_calls=0))

    def test_exact_source_equal_notes_two_role_budget_and_actual_review(self):
        source,plan,sim=prepare(self.lab)
        self.assertEqual(len(CONTROL.split()),len(ACTIVE.split()))
        self.assertEqual(plan['plan']['family'],'single_document_reference_repair')
        self.assertEqual(plan['plan']['source_refs']['dataset_ref'],study._ref(source))
        self.assertEqual(sim['simulator']['maximum_subject_calls'],64)
        self.assertEqual(sim['simulator']['causal_review']['decision'],'approve_exploratory')
        self.assertEqual(sim['simulator']['environment']['agents'],['ethics_owner','auditor'])
        self.assertEqual(self.lab.store.usage()['calls'],0)

    def test_full_cpu_execution_solves_real_tool_goal_and_replays(self):
        source,plan,sim=prepare(self.lab)
        executed=study.execute_plan(self.lab,raw({'simulator_ref':sim['simulator_ref']}),runner=fixture_policy)
        report=self.lab.store.get(executed['result_ref']['id'],1)['payload']
        self.assertEqual(executed['agent_mode'],'provided_runner')
        self.assertEqual(executed['subject_decisions'],64)
        self.assertEqual([r['outcomes'][PRIMARY] for r in report['runs']],[1]*4)
        self.assertTrue(study.verify_replay(report,expected_source_refs=report['source_refs'])['passed'])
        self.assertEqual(report['analysis']['primary_effect']['difference'],0)
        self.assertEqual(report['analysis']['primary_effect']['ci95'],[-1,1])
        self.assertEqual(report['analysis']['primary_effect']['p_two_sided'],1)
        for pair in (1,2):
            rows=[r for r in report['runs'] if r['pair_id']==pair]
            self.assertEqual(rows[0]['initial_state'],rows[1]['initial_state'])
        self.assertEqual(self.lab.store.usage()['calls'],0)
        with patch.object(self.lab,'harness') as harness:
            again=study.execute_plan(self.lab,raw({'simulator_ref':sim['simulator_ref']}),runner=lambda r:(_ for _ in ()).throw(AssertionError('must not repeat')))
        self.assertTrue(again['reused']);self.assertEqual(again['result_ref'],executed['result_ref']);harness.assert_not_called()

    def test_replay_rejects_grid_observation_oracle_types_and_source_tampering(self):
        _,_,sim=prepare(self.lab);execution=study.execute_plan(self.lab,raw({'simulator_ref':sim['simulator_ref']}),runner=fixture_policy)
        original=self.lab.store.get(execution['result_ref']['id'],1)['payload']
        attacks=[lambda r:r['runs'][0].update(pair_id=True),lambda r:r['assignments'][0].update(environment_seed=1),
            lambda r:r['runs'][0]['outcomes'].update(verified_repaired_reference=True),
            lambda r:r['runs'][0]['turns'][0]['request']['context'].clear(),
            lambda r:r['analysis']['primary_effect'].update(ci95=[0,0]),
            lambda r:r['backend'].update(max_output_tokens=600.0),lambda r:r['source_refs']['simulator_ref'].update(version=True),
            lambda r:r['source_refs']['dataset_ref'].update(hash='0'*64),lambda r:r['fidelity'].update(historical_equivalence=True)]
        for index,change in enumerate(attacks):
            report=copy.deepcopy(original);change(report)
            with self.subTest(attack=index),self.assertRaises(ValueError):study.verify_replay(report)

    def test_source_model_and_code_changes_fail_before_calling_subjects(self):
        source,plan,sim=prepare(self.lab)
        self.lab.settings.model='other-model'
        with self.assertRaises(ValueError):study.execute_plan(self.lab,raw({'simulator_ref':sim['simulator_ref']}),runner=fixture_policy)
        self.lab.settings.model='fixture-model'
        with patch.object(study,'_codes',return_value={'changed':'0'*64}),self.assertRaises(ValueError):
            study.execute_plan(self.lab,raw({'simulator_ref':sim['simulator_ref']}),runner=fixture_policy)
        for field,value in [('max_rounds',True),('seed',1.0),('treatment_text','unmatched')]:
            b={'dataset_ref':study._ref(source),'behavior_ref':None,'question':'New reference test','control_text':CONTROL,'treatment_text':ACTIVE,'trials_per_arm':2,'seed':1,'max_rounds':8};b[field]=value
            with self.assertRaises(ValueError):study.create_plan(self.lab,raw(b))
        with self.lab.store.connect() as c:
            self.assertIsNone(c.execute("SELECT name FROM sqlite_master WHERE name='reference_recovery_executions'").fetchone())

    def test_review_rejection_is_saved_and_cannot_be_silently_repeated(self):
        source=dataset(self.lab)
        plan=study.create_plan(self.lab,raw({'dataset_ref':study._ref(source),'behavior_ref':None,'question':'Bounded recovery question',
            'control_text':CONTROL,'treatment_text':ACTIVE,'trials_per_arm':2,'seed':1,'max_rounds':8}))
        def decline(role,packet,*args):
            answer=mocked_roles(role,packet)
            if role=='causal-methodologist':answer['decision']='requires_changes'
            return answer
        with patch('swarm_lab.research.ResearchAgents.run',side_effect=decline),self.assertRaises(ValueError):
            study.create_simulator(self.lab,raw({'plan_ref':plan['plan_ref']}))
        attempt=self.lab.store.list('village_recovery_construction_attempt')[0]
        self.assertEqual(attempt['payload']['causal_review']['decision'],'requires_changes')
        self.assertEqual(self.lab.store.jobs()[0]['status'],'failed')
        with patch('swarm_lab.research.ResearchAgents.run') as worker,self.assertRaises(ValueError):
            study.create_simulator(self.lab,raw({'plan_ref':plan['plan_ref']}))
        worker.assert_not_called()

    def test_partial_transport_and_archive_failures_preserve_inventory_without_estimate(self):
        _,_,sim=prepare(self.lab);invocations=[]
        def fault(request):
            invocations.append(1)
            if len(invocations)==3:raise OSError('Authored provider failure')
            return fixture_policy(request)
        with self.assertRaises(RuntimeError):study.execute_plan(self.lab,raw({'simulator_ref':sim['simulator_ref']}),runner=fault,max_workers=1)
        attempt=self.lab.store.list('village_recovery_attempt')[0]['payload']
        self.assertEqual([r['status'] for r in attempt['runs']],['incomplete_infrastructure_failure','not_started','complete','complete'])
        self.assertNotIn('analysis',attempt)
        proof=study.verify_replay(attempt);self.assertFalse(proof['passed']);self.assertFalse(proof['quantitative_available'])
        for index in (0,1):
            forged=copy.deepcopy(attempt);forged['runs'][index]['outcomes']={PRIMARY:1}
            with self.assertRaises(ValueError):study.verify_replay(forged)
        with self.assertRaises(ValueError):study.execute_plan(self.lab,raw({'simulator_ref':sim['simulator_ref']}),runner=fault)

    def test_source_grounding_remains_reported_and_note_not_seed_leaks(self):
        _,_,sim=prepare(self.lab);protocol=self.lab.store.get(sim['simulator']['protocol_ref']['id'],1)['payload']['protocol']
        for assignment in study._assignments(protocol):
            run=study._run_team(protocol,assignment,fixture_policy,'authored-job')
            for turn in run['turns']:
                request=turn['request'];self.assertEqual(request['context'],[protocol['notes'][assignment['arm']]])
                text=json.dumps({k:v for k,v in request.items() if k!='_job_id'})
                for forbidden in ('source_grounding','SOURCE-ONLY-MARKER','environment_seed','canonical_check','neutral_note'):
                    self.assertNotIn(forbidden,text)
            self.assertEqual(run['outcomes'][PRIMARY],1)

if __name__=='__main__':unittest.main()
