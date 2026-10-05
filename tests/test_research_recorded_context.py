"""Actual source-bound observations reach research without becoming citations."""
import copy
import json
import unittest
from unittest.mock import patch

from swarm_lab.library import register_behavior
from swarm_lab.research import ResearchAgents


class RecordedPacketHarness:
    name='recorded_packet_fixture'
    def __init__(self,invalid_citation=None):
        self.tasks=[];self.invalid_citation=invalid_citation

    def run(self,system,task,tools,job_id,*,schema=None):
        self.tasks.append(copy.deepcopy(task))
        identity=self.invalid_citation or task['evidence'][0]['id']
        if 'proposal' in task:
            return {'summary':'Ordinary coordination remains plausible.','evidence_ids':[identity],
                    'recommended_status':'needs_more_evidence','limitations':['Recorded summaries are not fresh replay.']}
        return {'viability':'candidate','name':'Source-bound candidate','summary':'Descriptive only.',
                'evidence_ids':[identity],'comparison_ids':[],'experiment_fit':'requires_new_environment'}


class ResearchRecordedContextTests(unittest.TestCase):
    def setUp(self):
        from tests.test_wait_marker_report import prepared_fixture
        self.f=prepared_fixture();self.addCleanup(self.f.doCleanups)
        self.actor=self.f.actor_audit();self.f.lab.replay_actor_events(self.actor['id'],version=1)
        self.wait=self.f.lab.audit_wait_markers(self.actor['id'],version=1)
        self.f.lab.replay_wait_markers(self.wait['id'],version=1)
        self.temporal=self.f.lab.audit_temporal_paths(self.f.selected['id'],version=self.f.selected['version'])
        self.hodge=self.f.lab.audit_edge_flow(self.temporal['id'],version=1)
        self.proof=self.f.lab.replay_edge_flow(self.hodge['id'],version=1)
        self.comparison=self.temporal['payload']['original_comparisons'][0]
        self.refs={kind:self.f.ref(obj) for kind,obj in [('dataset',self.f.dataset),('discovery',self.f.discovery)]}
        self.harness=RecordedPacketHarness()
        self.agents=ResearchAgents(self.f.lab.settings,self.f.lab.store,self.harness)
        self.candidate={'id':self.comparison['id'],'kind':'graph_bridge_shift',
                        'evidence_ids':[self.f.messages[0]['id']]}

    def snapshot(self):
        with self.f.lab.store.connect() as connection:
            return list(connection.execute('SELECT id,version,hash FROM objects ORDER BY id,version')),self.f.lab.store.usage()

    def test_two_roles_and_saved_attempt_retain_exact_context_without_promoting_library(self):
        before=self.snapshot()
        context=self.agents.measurement_context(self.candidate['id'],self.refs)
        self.assertEqual(before,self.snapshot())
        recorded=context['recorded_observations']
        self.assertTrue(all(row['available'] for row in recorded['observations'].values()),recorded)
        self.assertEqual(recorded['registered_comparison'],self.comparison)
        self.assertEqual(recorded['source_refs']['selected_audit'],self.f.ref(self.f.selected))
        self.assertEqual(recorded['source_refs']['temporal_audit'],self.f.ref(self.temporal))
        self.assertFalse(recorded['fresh_source_attestation']);self.assertFalse(recorded['raw_or_index_reread'])
        self.assertFalse(recorded['operator_rerun'])
        with patch('swarm_lab.actor_event_workflow.derive_selected_actor_events',side_effect=AssertionError('No fresh replay')), \
             patch('swarm_lab.wait_marker_workflow.derive_wait_marker_alignment',side_effect=AssertionError('No fresh replay')), \
             patch('swarm_lab.graph_hodge_workflow.derive_edge_flow',side_effect=AssertionError('No fresh replay')):
            research=self.agents.discover(self.candidate,self.f.dataset['payload'],self.f.discovery['payload'],
                                          'recorded-context-fixture',source_refs=self.refs)
        self.assertEqual(len(self.harness.tasks),2)
        for task in self.harness.tasks:
            self.assertEqual(task['measurement_context']['recorded_observations'],recorded)
        attempt=self.f.lab.store.get(research['research_attempt_id'])
        self.assertEqual(attempt['payload']['measurement_context']['recorded_observations'],recorded)
        self.assertEqual(attempt['payload']['status'],'adjudicated')
        pinned=self.f.lab.store.get(research['research_attempt_ref']['id'],research['research_attempt_ref']['version'])
        self.assertEqual(pinned['hash'],research['research_attempt_ref']['hash'])
        self.assertEqual(pinned['payload']['status'],'proposal_completed_pending_skeptic')
        self.assertEqual(pinned['payload']['measurement_context']['recorded_observations'],recorded)
        behavior=register_behavior(self.f.lab.store,research,self.f.dataset['id'],self.f.discovery['id'],self.refs)
        self.assertEqual(behavior['payload']['status'],'candidate')
        self.assertEqual(behavior['payload']['causal_support'],'none')
        self.assertEqual(behavior['payload']['novelty_status'],'not_established')
        self.assertEqual(behavior['payload']['research_attempt_ref'],research['research_attempt_ref'])
        self.assertNotIn('PRIVATE_PROVIDER_SENTINEL',json.dumps(recorded))
        self.assertEqual(self.f.lab.store.usage()['calls'],0)

    def test_latest_failed_stored_proof_is_an_unknown_in_both_role_packets(self):
        self.f.lab.store.put('verification',{**self.proof['payload'],'passed':False})
        self.agents.discover(self.candidate,self.f.dataset['payload'],self.f.discovery['payload'],
                             'recorded-failed-proof-fixture',source_refs=self.refs)
        for task in self.harness.tasks:
            measured=task['measurement_context'];recorded=measured['recorded_observations']
            self.assertTrue(measured['available'])
            self.assertTrue(recorded['observations']['actor_events']['available'])
            edge=recorded['observations']['edge_algebra']
            self.assertFalse(edge['available']);self.assertIsNone(edge['summary'])
            self.assertEqual(edge['reason'],'newest_bound_stored_proof_failed_or_incomplete')
        self.assertEqual(self.f.lab.store.usage()['calls'],0)

    def test_unmatched_lead_does_not_search_or_choose_an_observation_parent(self):
        with patch('swarm_lab.research_observations.recorded_observation_context',side_effect=AssertionError('No fallback')):
            context=self.agents.measurement_context('unmatched-candidate',self.refs)
        self.assertFalse(context['available']);self.assertEqual(context['audits'],[])
        self.assertFalse(context['recorded_observations']['available'])

    def test_observation_identity_is_not_a_supplied_or_retrieved_message_citation(self):
        self.agents.harness=RecordedPacketHarness(invalid_citation=self.actor['id'])
        with self.assertRaisesRegex(ValueError,'evidence|citation|unknown|supplied'):
            self.agents.discover(self.candidate,self.f.dataset['payload'],self.f.discovery['payload'],
                                 'recorded-invalid-citation-fixture',source_refs=self.refs)
        self.assertEqual(self.f.lab.store.list('behavior'),[])
        self.assertEqual(self.f.lab.store.list('research_attempt'),[])
        self.assertEqual(self.f.lab.store.usage()['calls'],0)


if __name__=='__main__':unittest.main()
