"""Prospective recorded context: no scientific replay or favorable fallback."""
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from swarm_lab import research_observations as module
from swarm_lab.store import fingerprint


class MemoryRecords:
    def __init__(self, rows):
        self.rows={(row['id'],row['version']):copy.deepcopy(row) for row in rows}
        self.list_calls=[];self.get_calls=[]

    def get(self, identity, version=None):
        self.get_calls.append((identity,version))
        if version is None:version=max(ver for name,ver in self.rows if name==identity)
        return copy.deepcopy(self.rows[identity,version])

    def list(self, kind, limit=100):
        self.list_calls.append((kind,limit));latest={}
        for row in self.rows.values():
            if row['kind']==kind and row['version']>latest.get(row['id'],{}).get('version',0):latest[row['id']]=row
        rows=sorted(latest.values(),key=lambda row:(row['created'],row['id'],row['version']),reverse=True)
        return copy.deepcopy(rows[:limit])

    def append(self, kind, payload, identity=None):
        identity=identity or kind+'-'+str(len(self.rows))
        version=max((ver for name,ver in self.rows if name==identity),default=0)+1
        row={'id':identity,'version':version,'kind':kind,'payload':copy.deepcopy(payload),'hash':fingerprint(payload),
             'created':(dt.datetime(2030,1,1,tzinfo=dt.timezone.utc)+dt.timedelta(seconds=len(self.rows))).isoformat()}
        self.rows[identity,version]=row
        return copy.deepcopy(row)

    def put(self,*args,**kwargs):raise AssertionError('Context must not persist anything')


class ResearchObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_wait_marker_report import prepared_fixture
        from swarm_lab import wait_marker_workflow as wait,graph_hodge_workflow as hodge
        f=prepared_fixture();cls.fixture=f
        cls.actor=f.actor_audit();cls.actor_proof=f.lab.replay_actor_events(cls.actor['id'],version=1)
        cls.wait=wait.audit_wait_markers(f.lab,cls.actor['id']);cls.wait_proof=wait.replay_wait_markers(f.lab,cls.wait['id'])
        cls.temporal=f.lab.audit_temporal_paths(f.selected['id'],version=f.selected['version'])
        cls.hodge=hodge.audit_edge_flow(f.lab,cls.temporal['id']);cls.hodge_proof=hodge.replay_edge_flow(f.lab,cls.hodge['id'])
        cls.refs={**cls.temporal['payload']['source_refs'],'temporal_audit':f.ref(cls.temporal)}
        cls.comparison=cls.temporal['payload']['original_comparisons'][0]
        with f.lab.store.connect() as conn:
            cls.records=[f.lab.store._decode(row) for row in conn.execute('SELECT * FROM objects')]
        cls.index_path=Path(cls.actor['payload']['actor_event_packet']['index']['path'])

    @classmethod
    def tearDownClass(cls):cls.fixture.doCleanups()

    def setUp(self):self.store=MemoryRecords(self.records)

    def collect(self,**options):return module.recorded_observation_context(self.store,self.refs,self.comparison,**options)

    def rebound(self, name, payload, proof_update=None):
        old={'actor_events':self.actor,'wait_markers':self.wait,'edge_algebra':self.hodge}[name]
        proof={'actor_events':self.actor_proof,'wait_markers':self.wait_proof,'edge_algebra':self.hodge_proof}[name]
        obj=self.store.append(old['kind'],payload)
        pp=copy.deepcopy(proof['payload']);pp['alignment_ref' if name=='wait_markers' else 'audit_ref']={key:obj[key] for key in ('id','version','hash')}
        pp.update(proof_update or {})
        self.store.append('verification',pp)
        return obj

    def assert_unavailable(self, result, name):
        self.assertFalse(result['observations'][name]['available'],result['observations'][name])
        self.assertIsNone(result['observations'][name]['summary'])

    def test_exact_old_sources_two_window_summaries_and_no_models_replay_or_content(self):
        for name,ref in self.refs.items():
            original=self.store.get(ref['id'],ref['version']);self.store.append(original['kind'],{'later':True},original['id'])
        before=copy.deepcopy(self.store.rows)
        with patch('swarm_lab.actor_event_workflow.derive_selected_actor_events',side_effect=AssertionError('No index query')), \
             patch('swarm_lab.wait_marker_workflow.derive_wait_marker_alignment',side_effect=AssertionError('No marker rerun')), \
             patch('swarm_lab.graph_hodge_workflow.derive_edge_flow',side_effect=AssertionError('No operator rerun')):
            result=self.collect()
        self.assertTrue(result['available'],result)
        self.assertEqual(self.store.rows,before)
        self.assertTrue(all(row['available'] for row in result['observations'].values()),result['observations'])
        expected={self.comparison['window_id'],self.comparison['comparison_window_id']}
        self.assertEqual(set(result['original_windows']),expected)
        actor=result['observations']['actor_events']['summary'];wait=result['observations']['wait_markers']['summary'];hodge=result['observations']['edge_algebra']['summary']
        self.assertEqual(set(actor['by_original_window']),expected)
        self.assertEqual(set(wait['by_original_author_window']),expected)
        self.assertEqual(set(hodge['by_original_window']),expected)
        self.assertTrue(any(row['room_status_counts']['missing'] for row in actor['by_original_window'].values()))
        self.assertEqual(sum(row['marker']['messages'] for row in wait['by_original_author_window'].values()),1)
        self.assertEqual(sum(row['nonmarker_control']['messages'] for row in wait['by_original_author_window'].values()),23)
        self.assertIn('not recomputed',wait['candidate_scope'])
        self.assertIn('not synchronized physical delay',wait['clock_scope'])
        for window in hodge['by_original_window'].values():
            self.assertEqual(set(window),set(module._VARIANTS))
            for cell in window.values():self.assertIsNone(cell['curl']);self.assertIsNone(cell['harmonic'])
        self.assertTrue(any(cell['energies']['signal']['squared_norm']==0 and cell['energies']['gradient']['fraction_of_signal'] is None for w in hodge['by_original_window'].values() for cell in w.values()))
        for row in result['observations'].values():
            self.assertTrue(row['gates']['local_registry_body_hash_verified']);self.assertTrue(row['gates']['stored_proof_binding_verified'])
            self.assertFalse(row['gates']['fresh_source_attestation'])
        self.assertFalse(result['fresh_source_attestation']);self.assertFalse(result['raw_or_index_reread']);self.assertFalse(result['operator_rerun'])
        encoded=json.dumps(result)
        self.assertNotIn('PRIVATE_PROVIDER_SENTINEL',encoded);self.assertNotIn('Bobby, I am not waiting',encoded)
        self.assertNotIn('node_potential',encoded);self.assertNotIn(str(self.index_path),encoded)
        self.assertLessEqual(len(module._bytes(result)),24000)
        self.assertEqual(self.store.list_calls,[('verification',64),('actor_event_audit',8),('wait_marker_alignment_audit',8),('graph_hodge_audit',8)])

    def test_current_code_uses_only_fixed_files_and_never_index_or_raw_paths(self):
        read=Path.read_bytes;opened=[]
        def restricted(path):
            self.assertEqual(path.parent.resolve(),Path(module.__file__).resolve().parent)
            self.assertIn(path.name,module._FILES);opened.append(path.name);return read(path)
        with patch.object(Path,'read_bytes',restricted):result=self.collect()
        self.assertTrue(all(row['available'] for row in result['observations'].values()),result)
        self.assertEqual(set(opened),set(module._FILES))
        self.assertEqual(result['model_calls'],0);self.assertEqual(result['database_writes'],0)

    def test_latest_stale_or_malformed_matching_observation_blocks_favorable_fallback(self):
        for name in module._KINDS:
            with self.subTest(name=name):
                self.store=MemoryRecords(self.records)
                original={'actor_events':self.actor,'wait_markers':self.wait,'edge_algebra':self.hodge}[name]
                p=copy.deepcopy(original['payload']);p['implementation_hashes']['../arbitrary-file']='0'*64
                latest=self.rebound(name,p);result=self.collect()
                self.assert_unavailable(result,name)
                self.assertEqual(result['observations'][name]['ref']['id'],latest['id'])
                self.assertEqual(result['observations'][name]['reason'],'observation_current_code_mismatch')
        self.store=MemoryRecords(self.records)
        p=copy.deepcopy(self.actor['payload']);p['actor_event_summary']['by_window'][self.comparison['window_id']]['records']=True
        self.rebound('actor_events',p);result=self.collect();self.assert_unavailable(result,'actor_events');self.assert_unavailable(result,'wait_markers')
        self.assertTrue(result['observations']['edge_algebra']['available'])

    def test_newest_failed_or_bad_typed_bound_proof_is_not_skipped(self):
        for update in ({'passed':False},{'model_calls':False},{'source_replay_completed':False},
                       {'audit_ref':{**self.fixture.ref(self.hodge),'version':True}}, {'result_kind':'actor_event_audit'}):
            with self.subTest(update=update):
                self.store=MemoryRecords(self.records)
                self.store.append('verification',{**copy.deepcopy(self.hodge_proof['payload']),**update})
                result=self.collect();self.assert_unavailable(result,'edge_algebra')
        result=self.collect(max_proof_objects=1)
        self.assertTrue(result['search_scope']['verification']['possibly_truncated'])
        self.assertIn('not global absence',result['search_scope']['verification']['interpretation'])
        self.assertTrue(any(not row['available'] for row in result['observations'].values()))

    def test_exact_source_comparison_parent_and_body_hash_fail_closed(self):
        for change in ('source_type','source_hash','comparison','body'):
            self.store=MemoryRecords(self.records);refs=copy.deepcopy(self.refs);comparison=copy.deepcopy(self.comparison)
            if change=='source_type':refs['dataset']['version']=True
            elif change=='source_hash':refs['discovery']['hash']='f'*64
            elif change=='comparison':comparison['comparison_window_id']=comparison['window_id']
            else:self.store.rows[refs['dataset']['id'],refs['dataset']['version']]['payload']['unsealed_change']=True
            result=module.recorded_observation_context(self.store,refs,comparison)
            self.assertFalse(result['available']);self.assertTrue(all(row['summary'] is None for row in result['observations'].values()))
        self.store=MemoryRecords(self.records)
        p=copy.deepcopy(self.wait['payload']);p['actor_audit_ref']['hash']='f'*64
        self.rebound('wait_markers',p);self.assert_unavailable(self.collect(),'wait_markers')
        self.store=MemoryRecords(self.records)
        p=copy.deepcopy(self.hodge['payload']);p['source_refs']['dataset']['version']=False
        self.rebound('edge_algebra',p);self.assert_unavailable(self.collect(),'edge_algebra')

    def test_incomplete_budget_unknown_author_partition_and_raw_payload_are_safe(self):
        self.store=MemoryRecords(self.records)
        p=copy.deepcopy(self.actor['payload']);p['actor_event_packet']['coverage']['query_complete']=False
        self.rebound('actor_events',p);self.assert_unavailable(self.collect(),'actor_events')
        self.store=MemoryRecords(self.records)
        p=copy.deepcopy(self.actor['payload']);p['author_source_pins'][0]['original_window_ids']=[self.comparison['window_id']]
        # Ensure a different membership, independent of source-message order.
        p['author_source_pins'][0]['original_window_ids']=['window-invented']
        self.rebound('actor_events',p);self.assert_unavailable(self.collect(),'actor_events')
        self.store=MemoryRecords(self.records)
        p=copy.deepcopy(self.wait['payload']);p['alignment']['summary']=None;p['alignment']['status']='unknown_alignment_scope'
        self.rebound('wait_markers',p);self.assert_unavailable(self.collect(),'wait_markers')
        self.store=MemoryRecords(self.records)
        p=copy.deepcopy(self.hodge['payload']);p['status']='unknown_budget_scope';p['unknown_reasons']=['aggregate_work_budget_exceeded']
        self.rebound('edge_algebra',p);self.assert_unavailable(self.collect(),'edge_algebra')
        self.store=MemoryRecords(self.records)
        p=copy.deepcopy(self.hodge['payload']);p['unused_provider_payload']={'content':'PRIVATE_PROVIDER_SENTINEL','credential':'not-for-models'}
        self.rebound('edge_algebra',p);result=self.collect()
        self.assertTrue(result['observations']['edge_algebra']['available']);self.assertNotIn('PRIVATE_PROVIDER_SENTINEL',json.dumps(result))

    def test_count_and_byte_budgets_withhold_whole_context_without_truncating_scores(self):
        for options in ({'max_objects_per_kind':True},{'max_proof_objects':0},{'max_registry_body_bytes':256},
                        {'max_total_registry_bytes':256},{'max_output_bytes':2048}):
            with self.subTest(options=options):
                result=self.collect(**options);self.assertFalse(result['available'])
                self.assertTrue(all(row['summary'] is None for row in result['observations'].values()))
                if options.get('max_output_bytes'):self.assertLessEqual(len(module._bytes(result)),2048)
        p=copy.deepcopy(self.hodge['payload']);p['huge_unused_field']='x'*(4*1024**2)
        self.rebound('edge_algebra',p);result=self.collect()
        self.assertFalse(result['available']);self.assertTrue(all(row['summary'] is None for row in result['observations'].values()))


if __name__=='__main__':unittest.main()
