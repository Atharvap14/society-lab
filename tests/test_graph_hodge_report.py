"""Source/operator reproduction gates static algebra and unknown quantities."""
import copy
import inspect
import json
import sys
import unittest
from unittest.mock import patch

from scripts.build_research_report import (ReadOnlyRecords, collect_graph_hodge,
    collect_report, execution_inventory, hodge_display, render_graph_hodge_addition)
from swarm_lab import graph_hodge_workflow as workflow


def prepared_fixture():
    from tests.test_graph_hodge_workflow import GraphHodgeWorkflowTests
    f=GraphHodgeWorkflowTests('test_all_parent_cells_exact_old_versions_and_whole_payload_reproduce')
    f.setUp()
    parent=f.parent()
    return f,parent


class GraphHodgeReportTests(unittest.TestCase):
    def setUp(self):
        self.f,self.parent=prepared_fixture();self.addCleanup(self.f.doCleanups)
        self.audit=workflow.audit_edge_flow(self.f.lab,self.parent['id'],version=1)
        self.proof=workflow.replay_edge_flow(self.f.lab,self.audit['id'],version=1)
        self.records=ReadOnlyRecords(self.f.lab.store.path);self.addCleanup(self.records.close)

    @staticmethod
    def pin(obj):return {key:obj[key] for key in ('id','version','kind','hash')}

    def pins(self,audit=None,proof=None):
        return {'audit':self.pin(audit or self.audit),'verification':self.pin(proof or self.proof)}

    def collect(self,pins=None):return collect_graph_hodge(self.records,self.pins() if pins is None else pins)

    def forged_pair(self,payload):
        audit=self.f.lab.store.put('graph_hodge_audit',payload)
        proof={**copy.deepcopy(self.proof['payload']),'audit_ref':self.f.ref(audit)}
        return self.pins(audit,self.f.lab.store.put('verification',proof))

    def assert_withheld(self,addition):
        self.assertFalse(addition['proof']['passed']);self.assertIsNone(addition['quantities'])
        self.assertEqual(addition['cells'],[])
        html=render_graph_hodge_addition(addition)
        self.assertIn('withheld',html);self.assertNotIn('All fixed cells;',html)

    def test_fresh_exact_old_sources_preserve_balanced_support_zero_fraction_and_no_writes(self):
        for obj in (self.f.dataset,self.f.discovery,self.f.selected,self.parent):
            self.f.lab.store.put(obj['kind'],{'later':True},obj['id'])
        before=self.records.connection.execute('SELECT COUNT(*) FROM objects').fetchone()[0]
        self.f.source.unlink()  # Hodge sources are normalized registry rows, not the raw event file.
        addition=self.collect()
        self.assertTrue(addition['proof']['passed'],addition['proof'])
        self.assertTrue(addition['proof']['source_replay_completed'])
        self.assertFalse(addition['proof']['raw_upstream_source_reread'])
        self.assertEqual(self.records.connection.execute('SELECT COUNT(*) FROM objects').fetchone()[0],before)
        self.assertEqual(self.records.connection.total_changes,0)
        self.assertEqual(len(addition['cells']),self.audit['payload']['bounds']['cells'])
        balanced=[cell for cell in addition['cells'] if any(p['net_reference_events']==0 for p in cell['edge_source_pins'])]
        self.assertTrue(balanced)
        zero=[cell for cell in addition['cells'] if cell['decomposition']['diagnostics']['zero_input_signal']]
        self.assertTrue(zero)
        for cell in zero:
            self.assertEqual(cell['decomposition']['energies']['signal']['squared_norm'],0)
            self.assertIsNone(cell['decomposition']['energies']['gradient']['fraction_of_signal'])
        for cell in addition['cells']:
            self.assertIsNone(cell['decomposition']['canonical_input']['faces'])
            self.assertIsNone(cell['decomposition']['energies']['curl'])
            self.assertIsNone(cell['decomposition']['energies']['harmonic'])
            self.assertEqual(sum(p['forward_reference_events']+p['reverse_reference_events'] for p in cell['edge_source_pins']),cell['source_reference_event_count'])
        html=render_graph_hodge_addition(addition)
        self.assertIn('Unknown / Unknown',html)
        self.assertIn('curl and harmonic',html);self.assertIn('no ranking',html)
        self.assertIn('not a proportion of messages or agents',html)
        encoded=json.dumps(addition)
        self.assertNotIn(self.f.messages[0]['content'],encoded)
        self.assertNotIn('PRIVATE_PROVIDER_SENTINEL',encoded);self.assertNotIn('node_potential',encoded)
        self.assertEqual(self.f.lab.store.usage()['calls'],0)
        self.assertEqual(self.f.lab.store.list('behavior'),[]);self.assertEqual(self.f.lab.store.list('theory'),[])
        self.assertEqual(execution_inventory({'result':{},'runs':[1]*9}),execution_inventory({'result':{},'runs':[1]*9,'static_edge_count_decomposition':addition}))

    def test_resealed_energy_fraction_counts_signal_face_or_type_changes_fail(self):
        edits=[lambda p:p['cells'][0]['decomposition']['energies']['signal'].update(squared_norm=999),
               lambda p:p['cells'][0]['decomposition']['energies']['circulation'].update(fraction_of_signal=.99),
               lambda p:p['cells'][0].update(source_reference_event_count=True),
               lambda p:p['cells'][0].update(source_reference_event_count=float(p['cells'][0]['source_reference_event_count'])),
               lambda p:p['cells'][0]['edge_source_pins'][0].update(net_reference_events=999),
               lambda p:p['configuration'].update(faces=[]),
               lambda p:p['configuration'].update(max_work=10000000.0),
               lambda p:p['source_refs']['dataset'].update(version=True)]
        for edit in edits:
            with self.subTest(edit=edit):
                payload=copy.deepcopy(self.audit['payload']);edit(payload)
                self.assert_withheld(self.collect(self.forged_pair(payload)))

    def test_bad_proof_and_implementation_mismatch_avoid_source_replay(self):
        for update in ({'audit_ref':{**self.f.ref(self.audit),'version':True}}, {'passed':1},
                       {'model_calls':False},{'source_replay_attempted':False},{'source_replay_completed':False},
                       {'result_kind':'temporal_path_audit'}):
            proof=self.f.lab.store.put('verification',{**self.proof['payload'],**update})
            with patch('swarm_lab.graph_hodge_workflow.derive_edge_flow',side_effect=AssertionError('must not reread')):
                addition=self.collect(self.pins(proof=proof))
            self.assert_withheld(addition);self.assertFalse(addition['proof']['source_replay_attempted'])
        with patch('swarm_lab.graph_hodge_workflow.implementation_hashes',return_value={}), \
             patch('swarm_lab.graph_hodge_workflow.derive_edge_flow',side_effect=AssertionError('must not reread')):
            self.assert_withheld(self.collect())

    def test_forged_temporal_parent_or_bad_source_identity_withholds(self):
        payload=copy.deepcopy(self.parent['payload'])
        cell=next(iter(next(iter(payload['windows'].values()))['variants'].values()))
        cell['event_count']+=1
        parent=self.f.lab.store.put('temporal_path_audit',payload)
        payload=copy.deepcopy(self.audit['payload'])
        payload['temporal_audit_ref']=self.f.ref(parent);payload['source_refs']['temporal_audit']=self.f.ref(parent)
        self.assert_withheld(self.collect(self.forged_pair(payload)))
        payload=copy.deepcopy(self.audit['payload']);payload['source_refs']['dataset']['hash']='f'*64
        self.assert_withheld(self.collect(self.forged_pair(payload)))
        payload=copy.deepcopy(self.audit['payload']);payload['source_refs']['dataset']['extra']='not an exact ref'
        self.assert_withheld(self.collect(self.forged_pair(payload)))

    def test_budget_and_backend_unavailability_are_reproducible_unknown_not_zero(self):
        audit=workflow.audit_edge_flow(self.f.lab,self.parent['id'],max_work=1)
        proof=workflow.replay_edge_flow(self.f.lab,audit['id'])
        addition=self.collect(self.pins(audit,proof));self.assertTrue(addition['proof']['passed'],addition['proof'])
        self.assertEqual(addition['quantities']['available_cells'],0)
        self.assertTrue(all(cell['decomposition'] is None for cell in addition['cells']))
        html=render_graph_hodge_addition(addition)
        self.assertIn('aggregate_work_budget_exceeded',html)
        self.assertIn('Unknown / Unknown',html)
        with patch.dict(sys.modules,{'numpy':None}):
            audit=workflow.audit_edge_flow(self.f.lab,self.parent['id'])
            proof=workflow.replay_edge_flow(self.f.lab,audit['id'])
            addition=self.collect(self.pins(audit,proof))
        self.assertTrue(addition['proof']['passed'],addition['proof'])
        self.assertTrue(all(cell['decomposition']['energies'] is None for cell in addition['cells']))

    def test_unavailable_parent_cells_retain_none_quantities_without_substitution(self):
        selected=self.f.lab.audit_selected_leads(self.f.discovery['id'],short_name_allowlist=['o3'],include_unicode_shadow=False)
        parent=self.f.lab.audit_temporal_paths(selected['id'],version=selected['version'])
        audit=workflow.audit_edge_flow(self.f.lab,parent['id']);proof=workflow.replay_edge_flow(self.f.lab,audit['id'])
        addition=self.collect(self.pins(audit,proof));self.assertTrue(addition['proof']['passed'],addition['proof'])
        unavailable=[cell for cell in addition['cells'] if cell['source_reference_event_count'] is None]
        self.assertTrue(unavailable)
        for cell in unavailable:
            self.assertIsNone(cell['decomposition']);self.assertIsNone(cell['preflight']);self.assertIsNone(cell['edge_source_pins'])
        html=render_graph_hodge_addition(addition)
        self.assertIn('Unknown / Unknown / Unknown',html);self.assertIn('unavailable:',html)
        self.assertEqual(len(addition['cells']),audit['payload']['bounds']['cells'])

    def test_display_tolerance_preserves_originals_escape_metadata_and_default_off(self):
        self.assertEqual(hodge_display(1e-30,4),'≈ 0');self.assertEqual(hodge_display(0),'0')
        self.assertEqual(hodge_display(None),'Unknown');self.assertEqual(hodge_display(False),'Unknown')
        self.assertEqual(hodge_display(1e-5),'1e-05')
        addition=self.collect();before=json.dumps(addition,sort_keys=True)
        html=render_graph_hodge_addition(addition)
        self.assertEqual(json.dumps(addition,sort_keys=True),before)
        self.assertIn('10⁻¹²',html);self.assertIn('without clipping',html)
        addition['references']['audit']['id']='<script>inert</script>'
        html=render_graph_hodge_addition(addition)
        self.assertIn('&lt;script&gt;inert&lt;/script&gt;',html);self.assertNotIn('<script>inert</script>',html)
        self.assertFalse(inspect.signature(collect_report).parameters['include_graph_hodge'].default)
        self.assert_withheld(self.collect({}))


if __name__=='__main__':unittest.main()
