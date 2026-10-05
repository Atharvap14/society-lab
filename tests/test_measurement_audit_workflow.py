"""Formatting diagnostics pin the selected source without changing its graph."""
import tempfile
import unittest
from pathlib import Path
from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab
from swarm_lab.dataset import normalize_message

class MeasurementAuditWorkflowTests(unittest.TestCase):
    def test_explicit_short_name_scan_has_empty_default_and_keeps_baseline_graph(self):
        with tempfile.TemporaryDirectory() as d:
            lab=Lab(Settings(root=Path(d)))
            rows=[normalize_message({'id':'a1','agent_id':'speaker','agent_name':'Writer','content':'o3, please check GPT-4.1.',
                'timestamp':'2025-04-22T18:00:00Z','room_id':'r'}),
                normalize_message({'id':'h1','speaker_type':'human','content':'o3','timestamp':'2025-04-22T18:01:00Z','room_id':'r'})]
            source=lab.store.put('dataset',{'messages':rows,'agents':[{'id':'o3-id','name':'o3'},{'id':'gpt','name':'GPT-4.1'}]})
            blank=lab.audit_name_eligibility(source['id'])['payload']
            self.assertEqual(blank['summary']['short_candidate_exact_event_count'],0)
            lab.store.put('dataset',{'messages':[],'agents':[]},source['id'])
            audit=lab.audit_name_eligibility(source['id'],version=1,short_name_allowlist=['o3'],include_unicode_shadow=True)
            report=audit['payload']
            self.assertEqual(report['dataset_ref']['hash'],source['hash'])
            self.assertEqual(report['summary']['baseline_exact_event_count'],1)
            self.assertEqual(report['summary']['short_candidate_exact_event_count'],1)
            event=report['short_name_exact_events'][0]
            span=event['span'];self.assertEqual(rows[0]['content'][span['start']:span['end']],'o3')
            self.assertEqual(report['scope']['message_count'],1)
            self.assertEqual(lab.store.get(source['id'],1),source)
            self.assertEqual(lab.store.list('discovery'),[])
            graphs=lab.compare_mention_graphs(audit['id'])['payload']
            self.assertEqual(graphs['eligibility_audit_ref']['hash'],audit['hash'])
            self.assertEqual(graphs['dataset_ref']['version'],1)
            self.assertEqual(graphs['variants']['baseline_exact']['counts']['projected_agent_event_count'],1)
            self.assertEqual(graphs['variants']['explicit_short_expanded_exact']['counts']['projected_agent_event_count'],2)
            self.assertEqual(lab.store.list('discovery'),[])
            self.assertEqual(lab.store.usage()['calls'],0)

    def test_pin_old_source_and_exclude_humans_without_mutating_import(self):
        with tempfile.TemporaryDirectory() as d:
            lab=Lab(Settings(root=Path(d)))
            messages=[normalize_message({'id':'m1','agent_id':'a','agent_name':'Agent A','content':'GPT\u20114.1, can you check?','timestamp':'2025-04-22T18:00:00Z','room_id':'r'}),
                normalize_message({'id':'h1','speaker_type':'human','content':'GPT-4.1?','timestamp':'2025-04-22T18:01:00Z','room_id':'r'})]
            source=lab.store.put('dataset',{'messages':messages,'agents':[{'id':'b','name':'GPT-4.1'}]})
            lab.store.put('dataset',{'messages':[],'agents':[]},source['id'])
            report=lab.audit_mentions(source['id'],version=1)['payload']
            self.assertEqual(report['dataset_ref']['hash'],source['hash'])
            self.assertEqual(report['summary']['exact_event_count'],0)
            self.assertEqual(report['summary']['shadow_only_event_count'],1)
            self.assertEqual(report['scope']['message_count'],1)
            self.assertEqual(lab.store.get(source['id'],1),source)
            self.assertEqual(lab.store.list('discovery'),[])
            self.assertEqual(lab.store.usage()['calls'],0)

if __name__=='__main__':unittest.main()
