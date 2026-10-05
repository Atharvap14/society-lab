"""Actual search logs, counts and citation eligibility survive parallel roles."""
import concurrent.futures
import tempfile
from pathlib import Path
import unittest
from swarm_lab.config import Settings
from swarm_lab.research import ResearchAgents,object_schema
from swarm_lab.store import Store

class QueryHarness:
    name='test_query_harness'
    def run(self,system,task,tools,job_id,*,schema=None):
        found=tools['search_evidence_terms']['execute'](queries=[task['term']],room_id='')
        return {'evidence_ids':[m['id'] for m in found['records']]}

class ResearchSearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=Store(Path(self.tmp.name)/'lab.sqlite3')
        self.agents=ResearchAgents(Settings(root=Path(self.tmp.name)),self.store,QueryHarness())
        self.dataset={'messages':[{'id':'m1','content':'Waiting for the asset.','room_id':'r'},
            {'id':'m2','content':'Completed independent work.','room_id':'r'},
            {'id':'m3','content':'Waiting in another room.','room_id':'other'}],'scope':{}}
        self.discovery={'graph':{'edges':[]},'candidates':[]}

    def test_terms_have_separate_literal_counts_and_known_retrievals(self):
        retrieved=set();tools=self.agents.tools(self.dataset,self.discovery,retrieved)
        value=tools['search_evidence_terms']['execute'](queries=['Waiting','Completed'],room_id='r')
        self.assertEqual([q['total_in_import'] for q in value['queries']],[1,1])
        self.assertEqual(retrieved,{'m1','m2'})
        literal=tools['search_evidence']['execute'](query='Waiting|Completed',room_id='r')
        self.assertEqual(literal['total_in_import'],0)
        self.assertEqual(literal['literal_query'],'Waiting|Completed')

    def test_parallel_invocations_keep_query_logs_and_citations_separate(self):
        schema=object_schema({'evidence_ids':{'type':'array','items':{'type':'string'}}})
        def run(term):return self.agents.run('skeptic',{'term':term},schema,self.dataset,self.discovery,'parallel')
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            outputs=list(pool.map(run,['asset','independent']))
        self.assertEqual(outputs,[{'evidence_ids':['m1']},{'evidence_ids':['m2']}])
        traces=[t['payload'] for t in self.store.traces('parallel')]
        roles=[t for t in traces if t['type']=='research_role'];calls=[t for t in traces if t['type']=='research_retrieval']
        self.assertEqual(len({r['invocation_id'] for r in roles}),2)
        for role in roles:
            own=[c for c in calls if c['invocation_id']==role['invocation_id']]
            self.assertEqual([c['record'] for c in own],role['actual_tool_log'])
            self.assertEqual(role['retrieved_evidence_ids'],own[0]['record']['newly_retrieved_evidence_ids'])

    def test_invalid_term_budget_is_rejected(self):
        execute=self.agents.tools(self.dataset,self.discovery)['search_evidence_terms']['execute']
        for queries in ([],['same','same'],[''],['x']*7):
            with self.assertRaises(ValueError):execute(queries=queries,room_id='')

if __name__=='__main__':unittest.main()
