"""Pinned measurement caveats reach both research roles without status promotion."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from swarm_lab.config import Settings
from swarm_lab.library import register_behavior
from swarm_lab.research import ResearchAgents
from swarm_lab.store import Store
from swarm_lab.temporal_network import analyze_temporal_mentions


class PacketHarness:
    name='packet_fixture'
    def __init__(self):self.tasks=[]
    def run(self,system,task,tools,job_id,*,schema=None):
        self.tasks.append(copy.deepcopy(task))
        if 'proposal' in task:
            return {'summary':'Ordinary coordination remains plausible.','evidence_ids':['m'],
                'recommended_status':'needs_more_evidence','limitations':['Measurement choices remain uncertain.']}
        return {'viability':'candidate','name':'Descriptive mention shift','summary':'Candidate only',
            'evidence_ids':['m'],'comparison_ids':[],'experiment_fit':'requires_new_environment'}


class ResearchMeasurementContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=Store(Path(self.tmp.name)/'lab.sqlite3')
        self.dataset={'messages':[{'id':'m','content':'A normal task handoff.','room_id':'r'}],'scope':{}}
        dataset=self.store.put('dataset',self.dataset)
        self.discovery={'dataset_id':dataset['id'],'dataset_ref':{k:dataset[k] for k in ('id','version','hash')},'candidates':[],'graph':{}}
        discovery=self.store.put('discovery',self.discovery)
        self.refs={kind:{k:obj[k] for k in ('id','version','hash')} for kind,obj in [('dataset',dataset),('discovery',discovery)]}
        self.audit=self.store.put('selected_lead_audit',{'analysis_version':'selected-lead-name-sensitivity-v1',
            'source_refs':self.refs,'per_lead':[{'lead_id':'lead','native':{'difference':-0.1},'fixed_pair':{'difference':0.2}}],
            'validation':{'baseline_replayed':True},'negative_control_checks':{'unchanged':True},
            'limitations':['Selected contrasts reuse evidence.']})
        self.harness=PacketHarness()
        self.agents=ResearchAgents(Settings(root=Path(self.tmp.name)),self.store,self.harness)

    def test_exact_versions_required_and_new_discovery_does_not_hide_old_binding(self):
        self.store.put('discovery',{**self.discovery,'later_search':True},self.refs['discovery']['id'])
        context=self.agents.measurement_context('lead',self.refs)
        self.assertTrue(context['available']);self.assertEqual(context['audits'][0]['ref']['hash'],self.audit['hash'])
        self.assertFalse(self.agents.measurement_context('another',self.refs)['available'])
        self.assertFalse(self.agents.measurement_context('lead')['available'])
        bad=copy.deepcopy(self.refs);bad['discovery']['hash']='0'*64
        with self.assertRaisesRegex(ValueError,'source mismatch'):self.agents.measurement_context('lead',bad)

    def test_both_roles_and_attempt_receive_audit_and_behavior_stays_candidate(self):
        candidate={'id':'lead','evidence_ids':['m'],'kind':'graph_incoming_concentration_shift'}
        research=self.agents.discover(candidate,self.dataset,self.discovery,'fixture',source_refs=self.refs)
        self.assertEqual(len(self.harness.tasks),2)
        for task in self.harness.tasks:self.assertEqual(task['measurement_context']['audits'][0]['ref']['id'],self.audit['id'])
        attempt=self.store.get(research['research_attempt_id'])
        self.assertTrue(attempt['payload']['measurement_context']['available'])
        behavior=register_behavior(self.store,research,self.refs['dataset']['id'],self.refs['discovery']['id'],self.refs)
        self.assertEqual(behavior['payload']['status'],'candidate')
        self.assertEqual(behavior['payload']['causal_support'],'none')
        self.assertEqual(behavior['payload']['measurement_audit_refs'],research['measurement_audit_refs'])
        self.assertEqual(self.store.usage()['calls'],0)

    def test_library_rejects_an_audit_of_another_lead(self):
        research={'proposal':{'viability':'candidate','evidence_ids':['m']},'skeptic':{'recommended_status':'candidate'},
            'candidate_id':'another','agent_mode':'fixture','harness':'none',
            'measurement_audit_refs':[{k:self.audit[k] for k in ('id','version','hash')}]}
        with self.assertRaisesRegex(ValueError,'another source or lead'):
            register_behavior(self.store,research,self.refs['dataset']['id'],self.refs['discovery']['id'],self.refs)
        self.assertEqual(self.store.list('behavior'),[])

    def test_long_reference_sections_keep_utf8_identity_and_declared_bounds(self):
        directory=Path(self.tmp.name)/'research'/'theory';directory.mkdir(parents=True)
        text='π observed-state methods\n'*1000
        target=directory/'intervention-timing.md';target.write_text(text,encoding='utf-8',newline='')
        read=self.agents.tools(self.dataset,self.discovery)['read_research_reference']['execute']
        first=read(name='intervention-timing',start_character=0,max_characters=16000)
        rest=read(name='intervention-timing',start_character=first['end_character_exclusive'],max_characters=16000)
        self.assertEqual(first['text']+rest['text'],text)
        self.assertTrue(first['has_after']);self.assertFalse(rest['has_after']);self.assertTrue(rest['has_before'])
        self.assertEqual(first['source_sha256'],hashlib.sha256(target.read_bytes()).hexdigest())
        self.assertEqual(first['source_sha256'],rest['source_sha256'])
        for kwargs in ({'start_character':True},{'start_character':len(text)+1},{'max_characters':16001},{'name':'../../.secrets/key'}):
            args={'name':'intervention-timing',**kwargs}
            with self.assertRaises(ValueError):read(**args)

    def _temporal(self):
        comparison={'id':'lead','feature':'bridge_dependence','window_id':'w1','comparison_window_id':'w2'}
        payload=copy.deepcopy(self.audit['payload']);payload['per_lead'][0]['registered']=comparison
        self.audit=self.store.put('selected_lead_audit',payload,self.audit['id'])
        messages=[{'id':'early','agent_id':'b','agent_name':'Bobby','content':'Carol, inspect.', 'room_id':'r','timestamp':'2025-04-18T10:00:00Z'},
            {'id':'late','agent_id':'a','agent_name':'Alice','content':'Bobby, inspect.','room_id':'r','timestamp':'2025-04-18T10:01:00Z'},
            {'id':'later','agent_id':'a','agent_name':'Alice','content':'Bobby, inspect.','room_id':'r','timestamp':'2025-04-18T11:00:00Z'}]
        windows=[{'id':f'w{i+1}','room_id':'r','start':f'2025-04-18T{10+i}:00:00Z','end_exclusive':f'2025-04-18T{11+i}:00:00Z'} for i in range(2)]
        parent={key:self.audit[key] for key in ('id','version','hash')}
        result=analyze_temporal_mentions(messages,[{'id':'a','name':'Alice'},{'id':'b','name':'Bobby'},{'id':'c','name':'Carol'}],windows=windows,
            source_refs={**self.refs,'selected_audit':parent})
        result.update(selected_audit_ref=parent,original_comparisons=[comparison],source_audit_replay_passed=True)
        return self.store.put('temporal_path_audit',result)

    def test_temporal_excerpts_reach_both_roles_and_register_exact_parent(self):
        temporal=self._temporal()
        candidate={'id':'lead','evidence_ids':['m'],'kind':'graph_bridge_shift'}
        research=self.agents.discover(candidate,self.dataset,self.discovery,'fixture',source_refs=self.refs)
        for task in self.harness.tasks:
            entries=task['measurement_context']['audits'];self.assertEqual(len(entries),2)
            excerpt=entries[1]['excerpt'];self.assertEqual(entries[1]['ref']['hash'],temporal['hash'])
            self.assertEqual(excerpt['windows']['w1']['variants']['baseline_exact']['static_pairs'],3)
            self.assertEqual(excerpt['windows']['w1']['variants']['baseline_exact']['strict_temporal_pairs'],2)
            self.assertFalse(excerpt['static_only_witness_excerpts'][0]['strict_timestamp_order'])
            self.assertLessEqual(len(__import__('json').dumps(excerpt,ensure_ascii=False)),16000)
        behavior=register_behavior(self.store,research,self.refs['dataset']['id'],self.refs['discovery']['id'],self.refs)
        self.assertEqual(behavior['payload']['status'],'candidate');self.assertEqual(behavior['payload']['causal_support'],'none')
        bad=copy.deepcopy(research);bad['measurement_audit_refs']=bad['measurement_audit_refs'][1:]
        with self.assertRaisesRegex(ValueError,'research attempt|another source or lead'):
            register_behavior(self.store,bad,self.refs['dataset']['id'],self.refs['discovery']['id'],self.refs)

    def test_temporal_wrong_comparator_and_noninteger_reference_are_rejected(self):
        temporal=self._temporal();p=copy.deepcopy(temporal['payload']);p['original_comparisons'][0]['comparison_window_id']='w1'
        self.store.put('temporal_path_audit',p,temporal['id'])
        with self.assertRaisesRegex(ValueError,'original selected comparison'):
            self.agents.measurement_context('lead',self.refs)
        for value in (True,1.0):
            refs=copy.deepcopy(self.refs);refs['dataset']['version']=value
            with self.assertRaisesRegex(ValueError,'source mismatch'):self.agents.measurement_context('lead',refs)


if __name__=='__main__':unittest.main()
