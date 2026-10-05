import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab
from swarm_lab.store import Store
from tests.test_research_contract import proposal


class SequenceHarness:
    name='fake'
    def __init__(self,answers):self.answers=list(answers);self.calls=[]
    def run(self,system,task,tools,job_id,*,schema=None):
        self.calls.append(task);answer=self.answers.pop(0)
        if isinstance(answer,Exception):raise answer
        return copy.deepcopy(answer)


class ResearchResumptionTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.lab=Lab(Settings(root=Path(self.directory.name)))
        self.dataset=self.lab.store.put('dataset',{'messages':[{'id':'m1','content':'Original handoff report','created_at':'2025-04-02T10:00:00Z','agent_id':'a','room_id':'r'}],'agents':[]},'dataset-source')
        self.candidate={'id':'c1','kind':'completion_report_cluster','title':'Handoff','description':'Observed report','evidence_ids':['m1'],'alternative_explanations':['Ordinary progress'],'right_censored':False}
        self.discovery=self.lab.store.put('discovery',{'dataset_id':self.dataset['id'],'dataset_ref':self.ref(self.dataset),'candidates':[self.candidate],'controls':[],'graph':{'edges':[]}},'discovery-source')
        self.refs={'dataset':self.ref(self.dataset),'discovery':self.ref(self.discovery)}
        self.skeptic={'summary':'Scope remains uncertain','evidence_ids':['m1'],'unsupported_claims':[],'alternative_explanations':['Ordinary progress'],'searches_performed':['Read supplied source'],'search_results':['Handoff reported'],'counterexample_searches':[],'recommended_status':'needs_more_evidence','limitations':['No oracle']}

    @staticmethod
    def ref(obj):return {key:obj[key] for key in ('id','version','hash')}

    def attempt(self):
        return self.lab.store.put('research_attempt',{'status':'skeptic_failed','source_refs':self.refs,'candidate':self.candidate,'proposal':proposal(),'initial_evidence_ids':['m1'],'job_id':'original','harness':'fake'})

    def test_skeptic_failure_saves_the_unchanged_proposal_without_registering_behavior(self):
        harness=SequenceHarness([proposal(),RuntimeError('deliberate rate failure')])
        with patch.object(self.lab,'research_harness',return_value=harness):
            with self.assertRaisesRegex(RuntimeError,'saved proposal'):
                self.lab.investigate(self.discovery['id'],live=True,count=1)
        attempts=self.lab.store.list('research_attempt')
        self.assertEqual(len(attempts),1);self.assertEqual(attempts[0]['payload']['status'],'skeptic_failed')
        self.assertEqual(attempts[0]['payload']['proposal'],proposal())
        self.assertEqual(self.lab.store.list('behavior'),[])

    def test_resume_uses_pinned_source_versions_and_does_not_repeat_discovery(self):
        attempt=self.attempt()
        changed=self.lab.store.put('dataset',{'messages':[{'id':'m1','content':'Later replacement'}],'agents':[]},self.dataset['id'])
        self.lab.store.put('discovery',{**self.discovery['payload'],'dataset_ref':self.ref(changed)},self.discovery['id'])
        harness=SequenceHarness([self.skeptic])
        with patch.object(self.lab,'research_harness',return_value=harness):
            behavior=self.lab.resume_investigation(attempt['id'],live=True)
            again=self.lab.resume_investigation(attempt['id'],live=True)
        self.assertEqual(len(harness.calls),1)
        self.assertEqual(harness.calls[0]['evidence'][0]['content'],'Original handoff report')
        self.assertEqual(behavior['payload']['source_refs'],self.refs)
        snapshot=self.lab.store.get(behavior['payload']['research_attempt_ref']['id'],
                                    behavior['payload']['research_attempt_ref']['version'])
        self.assertEqual(snapshot['hash'],behavior['payload']['research_attempt_ref']['hash'])
        self.assertIn('measurement_context',snapshot['payload'])
        self.assertEqual(snapshot['payload']['proposal'],proposal())
        self.assertEqual(again['id'],behavior['id'])
        self.assertEqual(self.lab.store.get(attempt['id'])['payload']['status'],'adjudicated')

    def test_bad_reference_or_missing_live_authorization_stops_before_harness_call(self):
        attempt=self.attempt()
        with self.assertRaisesRegex(ValueError,'explicit live mode'):
            self.lab.resume_investigation(attempt['id'])
        payload=attempt['payload'];payload['source_refs']['dataset']['hash']='0'*64
        self.lab.store.put('research_attempt',payload,attempt['id'])
        with patch.object(self.lab,'research_harness') as harness:
            with self.assertRaisesRegex(ValueError,'reference mismatch'):
                self.lab.resume_investigation(attempt['id'],live=True)
            harness.assert_not_called()

    def test_repeat_failure_preserves_prior_proposal_and_adds_a_visible_attempt_version(self):
        attempt=self.attempt()
        with patch.object(self.lab,'research_harness',return_value=SequenceHarness([RuntimeError('provider unavailable')])):
            with self.assertRaises(RuntimeError):self.lab.resume_investigation(attempt['id'],live=True)
        history=self.lab.store.history(attempt['id'])
        self.assertEqual(len(history),3);self.assertEqual(history[-1]['payload']['proposal'],proposal())
        self.assertIn('measurement_context',history[-2]['payload'])
        self.assertEqual(history[-2]['payload']['measurement_context'],history[-1]['payload']['measurement_context'])
        self.assertEqual(self.lab.store.list('behavior'),[])

    def test_invalid_saved_source_versions_and_contexts_stop_before_harness_construction(self):
        for change in ('boolean','float','extra_source_field','paired_dataset','context_list','audits_null','bad_audit_version'):
            with self.subTest(change=change):
                attempt=self.attempt();payload=copy.deepcopy(attempt['payload'])
                payload['measurement_context']={'available':False,'audits':[]}
                if change in ('boolean','float'):
                    payload['source_refs']['dataset']['version']=True if change=='boolean' else 1.0
                elif change=='extra_source_field':payload['source_refs']['dataset']['path']='not-allowed'
                elif change=='paired_dataset':
                    replacement=self.lab.store.put('dataset',copy.deepcopy(self.dataset['payload']))
                    payload['source_refs']['dataset']=self.ref(replacement)
                elif change=='context_list':payload['measurement_context']=[{'audits':[]}]
                elif change=='audits_null':payload['measurement_context']['audits']=None
                else:payload['measurement_context']['audits']=[{'ref':{**self.ref(self.dataset),'version':True}}]
                self.lab.store.put('research_attempt',payload,attempt['id'])
                before=len(self.lab.store.history(attempt['id']))
                with patch.object(self.lab,'research_harness') as harness:
                    with self.assertRaisesRegex(ValueError,'reference mismatch|measurement context'):
                        self.lab.resume_investigation(attempt['id'],live=True)
                    harness.assert_not_called()
                self.assertEqual(len(self.lab.store.history(attempt['id'])),before)
                self.assertEqual(self.lab.store.list('behavior'),[])


if __name__=='__main__':unittest.main()
