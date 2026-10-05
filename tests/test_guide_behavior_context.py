"""Saved behavior explanations preserve rejection and exact source excerpts."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from swarm_lab.guide_assistant import _behavior_review_context
from swarm_lab.store import Store


def ref(o): return {k: o[k] for k in ('id', 'version', 'hash')}


class GuideBehaviorContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.lab = SimpleNamespace(store=Store(Path(self.tmp.name)/'lab.sqlite3'))

    def test_rejected_review_reads_exact_old_source_and_preserves_comparison(self):
        source = self.lab.store.put('dataset', {'messages': [
            {'id':'support','content':'Reported a blocked URL','timestamp':'2025-09-08T18:00:00Z'},
            {'id':'against','content':'Reported a copied URL error and a working replacement','timestamp':'2025-09-08T18:10:00Z'}]})
        self.lab.store.put('dataset', {'messages':[{'id':'against','content':'Unrelated newer version'}]},source['id'])
        b = self.lab.store.put('behavior', {'status':'rejected','novelty_status':'rejected',
            'operational_definition':'A proposed access-repair pattern','source_refs':{'dataset':ref(source)},
            'evidence_ids':['support'],'comparison_ids':['against'],'skeptic':{'summary':'Ordinary copying error remains sufficient.','recommended_status':'rejected'}})
        sources={}; context=_behavior_review_context(self.lab,b,sources)
        self.assertEqual(context['status'],'rejected'); self.assertEqual(context['dataset_ref'],ref(source))
        self.assertEqual([m['role'] for m in context['cited_messages']],['supporting_record','comparison_record'])
        self.assertIn('working replacement',context['cited_messages'][1]['content_excerpt'])
        self.assertNotIn('Unrelated',str(context)); self.assertEqual(len(sources),2)
        self.assertEqual(self.lab.store.get(source['id'],1),source)

    def test_missing_pin_stays_unknown_and_bad_pin_is_refused(self):
        b = self.lab.store.put('behavior', {'status':'candidate','dataset_id':'legacy-no-version'})
        c=_behavior_review_context(self.lab,b,{})
        self.assertEqual(c['cited_messages'],[]); self.assertIn('No exact',c['source_status'])
        source = self.lab.store.put('dataset',{'messages':[]})
        b = self.lab.store.put('behavior',{'source_refs':{'dataset':{**ref(source),'hash':'0'*64}}})
        with self.assertRaises(ValueError): _behavior_review_context(self.lab,b,{})


if __name__ == '__main__': unittest.main()
