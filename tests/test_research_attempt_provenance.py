"""A behavior retains the immutable source/context-bearing proposal snapshot."""
import copy
import tempfile
import unittest
from pathlib import Path

from swarm_lab.library import register_behavior
from swarm_lab.store import Store


class ResearchAttemptProvenanceTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.store=Store(Path(temporary.name)/'lab.sqlite3')
        self.dataset=self.store.put('dataset',{'messages':[{'id':'m','content':'Ordinary handoff.'}]})
        self.discovery=self.store.put('discovery',{'dataset_ref':self.ref(self.dataset)})
        self.refs={'dataset':self.ref(self.dataset),'discovery':self.ref(self.discovery)}
        self.proposal={'viability':'candidate','name':'Ordinary handoff','evidence_ids':['m']}
        self.context={'available':False,'audits':[],'recorded_observations':{'available':False,
                      'fresh_source_attestation':False,'reason':'No matching observation'}}
        self.attempt=self.store.put('research_attempt',{'status':'proposal_completed_pending_skeptic',
            'source_refs':self.refs,'candidate':{'id':'lead'},'proposal':self.proposal,
            'measurement_context':self.context})
        self.research={'candidate_id':'lead','proposal':self.proposal,
            'skeptic':{'recommended_status':'needs_more_evidence','evidence_ids':['m']},
            'agent_mode':'fixture','harness':'none','measurement_audit_refs':[],
            'research_attempt_id':self.attempt['id'],'research_attempt_ref':self.ref(self.attempt)}

    @staticmethod
    def ref(obj):return {key:obj[key] for key in ('id','version','hash')}

    def register(self,research):
        return register_behavior(self.store,research,self.dataset['id'],self.discovery['id'],self.refs)

    def test_later_attempt_version_cannot_replace_the_context_used_in_registration(self):
        self.store.put('research_attempt',{**self.attempt['payload'],'status':'adjudicated',
            'measurement_context':{'audits':[],'later_context':True}},self.attempt['id'])
        behavior=self.register(self.research)
        self.assertEqual(behavior['payload']['research_attempt_ref'],self.ref(self.attempt))
        snapshot=self.store.get(behavior['payload']['research_attempt_ref']['id'],1)
        self.assertEqual(snapshot['payload']['measurement_context'],self.context)
        self.assertEqual(behavior['payload']['status'],'candidate')
        self.assertEqual(behavior['payload']['causal_support'],'none')
        self.assertEqual(behavior['payload']['novelty_status'],'not_established')

    def test_wrong_pin_kind_source_candidate_proposal_and_context_stop_before_library_write(self):
        for change in ('boolean_version','wrong_hash','extra_ref_field','wrong_id','kind',
                       'source','candidate','proposal','missing_context','audit_refs','malformed_audit'):
            with self.subTest(change=change):
                research=copy.deepcopy(self.research)
                if change=='boolean_version':research['research_attempt_ref']['version']=True
                elif change=='wrong_hash':research['research_attempt_ref']['hash']='0'*64
                elif change=='extra_ref_field':research['research_attempt_ref']['path']='not-allowed'
                elif change=='wrong_id':research['research_attempt_id']='another'
                elif change=='kind':research['research_attempt_ref']=self.ref(self.dataset)
                else:
                    payload=copy.deepcopy(self.attempt['payload'])
                    if change=='source':payload['source_refs']['dataset']['hash']='0'*64
                    elif change=='candidate':payload['candidate']['id']='another'
                    elif change=='proposal':payload['proposal']['name']='Changed proposal'
                    elif change=='missing_context':payload.pop('measurement_context')
                    elif change=='audit_refs':payload['measurement_context']['audits']=[{'ref':self.ref(self.dataset)}]
                    elif change=='malformed_audit':payload['measurement_context']['audits']=[None]
                    snapshot=self.store.put('research_attempt',payload)
                    research['research_attempt_ref']=self.ref(snapshot);research['research_attempt_id']=snapshot['id']
                with self.assertRaisesRegex(ValueError,'research attempt'):
                    self.register(research)
                self.assertEqual(self.store.list('behavior'),[])
        self.assertEqual(self.store.usage()['calls'],0)


if __name__=='__main__':unittest.main()
