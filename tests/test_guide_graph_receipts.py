"""Only source-bound bounded graphs may enter the actual tool receipt stream."""
import copy
import unittest
from swarm_lab.guide_assistant import _tool_result_projection

class GraphReceiptTests(unittest.TestCase):
    def receipt(self):
        ref={'id':'observability_run-test','version':1,'hash':'a'*64}
        graph={'graph_version':'event-evidence-neighborhood-v1','source_ref':ref,
            'nodes':[{'id':'event-1','kind':'tool.called'}],'edges':[],'diagnostics':[]}
        return {'status':'completed','tool':'event_neighborhood','summary':'Read actual source links.',
            'result_refs':[ref],'updated_context':{},'view':None,'event_graph':graph}

    def test_exact_graph_is_preserved_without_aliasing_tool_output(self):
        raw=self.receipt();shown=_tool_result_projection([raw])[0]
        self.assertEqual(shown['event_graph'],raw['event_graph'])
        shown['event_graph']['nodes'][0]['id']='other'
        self.assertEqual(raw['event_graph']['nodes'][0]['id'],'event-1')

    def test_mismatched_graph_source_or_excess_output_refuses_projection(self):
        for edit in ('hash','nodes','edges','diagnostics'):
            raw=self.receipt()
            if edit=='hash':raw['event_graph']['source_ref']={'id':'observability_run-test','version':1,'hash':'b'*64}
            else:raw['event_graph'][edit]=[{}]*(3 if edit=='diagnostics' else 9)
            with self.subTest(edit=edit),self.assertRaises(ValueError):_tool_result_projection([raw])

if __name__=='__main__':unittest.main()
