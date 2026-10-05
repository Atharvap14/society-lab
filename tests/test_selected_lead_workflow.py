"""Real selected-episode derivations keep source versions and original selection."""
import copy
import tempfile
import unittest
from pathlib import Path

from swarm_lab.config import Settings
from swarm_lab.dataset import normalize_message
from swarm_lab.graph_discovery import discover_graph_leads
from swarm_lab.pipeline import Lab


def fixture():
    roster=[{'id':'a','name':'Alice'},{'id':'b','name':'Bobby'},{'id':'c','name':'Carol'},
        {'id':'o','name':'o3'}]
    rows=[]
    for hour in (10,11):
        for i in range(12):
            actor=['a','b','c'][i%3]
            text=('Bobby, inspect the telescope artifact. o3 may know.' if actor!='b' else 'My local note is ready.') if hour==10 else 'Alice, Bobby, Carol, inspect the telescope artifact together.'
            rows.append(normalize_message({'id':f'{hour}-{i}','agent_id':actor,'agent_name':next(a['name'] for a in roster if a['id']==actor),
                'content':text,'room_id':'r','timestamp':f'2025-04-02T{hour}:00:{i:02d}Z','source':{'file':'fixture','line':len(rows)+1}}))
    rows.append(normalize_message({'id':'h','speaker_type':'human','content':'Quoted model o3 and Bobby.',
        'room_id':'r','timestamp':'2025-04-02T10:00:05.500Z','source':{'file':'fixture','line':25}}))
    return rows,roster


class SelectedLeadWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.lab=Lab(Settings(root=Path(self.tmp.name)))
        rows,roster=fixture();self.dataset=self.lab.store.put('dataset',{'messages':rows,'agents':roster})
        search=discover_graph_leads(rows,roster)
        self.assertTrue(search['leads'])
        self.discovery=self.lab.store.put('discovery',{'dataset_id':self.dataset['id'],
            'dataset_ref':{k:self.dataset[k] for k in ('id','version','hash')},'graph_search':search})

    def test_old_version_uses_all_rows_and_adds_a_separate_signed_audit(self):
        self.lab.store.put('dataset',{'messages':[],'agents':[]},self.dataset['id'])
        self.lab.store.put('discovery',{'later_unrelated':True},self.discovery['id'])
        result=self.lab.audit_selected_leads(self.discovery['id'],version=1,
            short_name_allowlist=['o3'],include_unicode_shadow=True)
        p=result['payload'];self.assertEqual(result['kind'],'selected_lead_audit')
        self.assertEqual(p['source_refs']['discovery']['hash'],self.discovery['hash'])
        self.assertEqual(p['source_refs']['dataset']['version'],1)
        self.assertEqual(p['scope']['source_message_count'],25)
        self.assertEqual(p['scope']['all_source_human_message_count'],1)
        self.assertFalse(p['frozen_selection']['selection_or_matching_changed'])
        self.assertEqual(p['frozen_selection']['variant_searches_performed'],0)
        for lead in p['per_lead']:
            self.assertEqual(lead['native']['baseline_exact']['difference'],lead['registered']['difference'])
            self.assertEqual(lead['native']['baseline_exact']['change_from_baseline'],0)
        self.assertEqual(self.lab.store.get(self.discovery['id'],1),self.discovery)
        self.assertEqual(self.lab.store.list('behavior'),[])
        self.assertEqual(self.lab.store.usage()['calls'],0)

    def test_malformed_selection_or_replay_fails_before_persistence(self):
        lead=self.discovery['payload']['graph_search']['leads'][0]['id']
        for kwargs in ({'selected_lead_ids':[lead,lead]},{'version':True},{'include_unicode_shadow':'true'}):
            with self.assertRaises(ValueError):self.lab.audit_selected_leads(self.discovery['id'],**kwargs)
        bad=copy.deepcopy(self.discovery['payload'])
        bad['graph_search']['leads'][0]['difference']+=0.01
        modified=self.lab.store.put('discovery',bad)
        with self.assertRaisesRegex(ValueError,'baseline_replay_mismatch'):
            self.lab.audit_selected_leads(modified['id'])
        self.assertEqual(self.lab.store.list('selected_lead_audit'),[])


if __name__=='__main__':unittest.main()
