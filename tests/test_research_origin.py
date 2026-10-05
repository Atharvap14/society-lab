"""Scientific source pins stay distinct from presentation and subject mode."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from swarm_lab.research_origin import classify_record, _refs
from swarm_lab.store import Store


def ref(record):
    return {k: record[k] for k in ('id', 'version', 'hash')}


class ResearchOriginTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / 'lab.sqlite3')

    def classify(self, record):
        with self.store.connect() as c:
            return classify_record(c, record)

    def test_exact_old_fixture_not_replaced_by_new_real_source(self):
        old = self.store.put('dataset', {'source': 'examples/coordination_fixture'})
        self.store.put('dataset', {'source': 'real-import'}, old['id'])
        b = self.store.put('behavior', {'source_refs': {'dataset': ref(old)}})
        self.assertTrue(self.classify(b)['fixture'])
        self.assertEqual(self.store.get(old['id'], 1), old)

    def test_real_logs_remain_when_behavior_has_offline_infrastructure_check(self):
        source = self.store.put('dataset', {'source': 'actual-import'})
        b = self.store.put('behavior', {'agent_mode': 'offline_simulation', 'source_refs': {'dataset': ref(source)}})
        self.assertEqual(self.classify(b), {'source_class': 'imported_logs', 'fixture': False})

    def test_simulated_agents_are_excluded_even_with_real_motivating_source(self):
        source = self.store.put('dataset', {'source': 'actual-import'})
        experiment = self.store.put('experiment', {'agent_mode': 'offline_simulation', 'source_refs': {'dataset': ref(source)}})
        self.assertTrue(self.classify(experiment)['fixture'])

    def test_missing_explicit_fixture_and_legacy_versions_never_claim_historical_pin(self):
        b = self.store.put('behavior', {'dataset_id': 'controlled-forward-fixture'})
        self.assertEqual(self.classify(b)['source_class'], 'declared_fixture')
        source = self.store.put('dataset', {'source': 'actual-import'})
        b = self.store.put('behavior', {'dataset_id': source['id']})
        self.assertEqual(self.classify(b), {'source_class': 'unversioned_log_source', 'fixture': False})

    def test_bad_exact_hash_does_not_follow_latest(self):
        source = self.store.put('dataset', {'source': 'examples/coordination_fixture'})
        b = self.store.put('behavior', {'source_refs': {'dataset': {**ref(source), 'hash': '0' * 64}}})
        self.assertEqual(self.classify(b), {'source_class': 'unknown_origin', 'fixture': False})

    def test_cycle_and_mixed_sources_remain_bounded_and_uncertain(self):
        source = self.store.put('dataset', {'source': 'actual-import'})
        authored = self.store.put('dataset', {'provenance': {'origin': 'authored_example'}})
        b = self.store.put('behavior', {'source_refs': {'real': ref(source), 'authored': ref(authored)}})
        self.assertEqual(self.classify(b), {'source_class': 'mixed_or_uncertain_sources', 'fixture': False})
        # A self-referential identity cannot silently select a different version.
        b = self.store.put('behavior', {'source_refs': {'behavior': {'id': 'behavior-cycle', 'version': 1, 'hash': '0' * 64}}}, 'behavior-cycle')
        self.assertEqual(self.classify(b)['source_class'], 'unknown_origin')

    def test_raw_transcript_reference_does_not_become_origin_and_declared_dataset_wins(self):
        actual = self.store.put('dataset', {'source': 'actual-import'})
        authored = self.store.put('dataset', {'provenance': {'origin': 'authored_example'}})
        raw_only = self.store.put('behavior', {'messages': [{'metadata': {'source_ref': ref(authored)}}]})
        self.assertEqual(self.classify(raw_only)['source_class'], 'unknown_origin')
        declared = self.store.put('behavior', {'dataset_ref': ref(actual), 'messages': [{'source_ref':ref(authored)}]})
        self.assertEqual(self.classify(declared)['source_class'], 'imported_logs')
        self.assertEqual(_refs(declared['payload']), [ref(actual)])

    def test_non_source_payload_is_not_decoded_and_valid_source_hash_checked_once(self):
        actual = self.store.put('dataset', {'source':'actual-import'})
        other = self.store.put('experiment', {'runs':[{'turns':[{'messages':['irrelevant']}]}]})
        behavior = self.store.put('behavior', {'source_refs':{'dataset':ref(actual),'result':ref(other)}})
        original = Store._decode; decoded = []
        def tracked(row):
            decoded.append(row['id']); return original(row)
        with self.store.connect() as c, patch.object(Store,'_decode',side_effect=tracked):
            memo = {}
            for _ in range(4):
                self.assertEqual(classify_record(c,behavior,memo=memo)['source_class'],'imported_logs')
        self.assertEqual(decoded,[actual['id']])

    def test_memo_is_per_read_legacy_id_and_authored_protocol_are_explicit(self):
        source = self.store.put('dataset', {'source':'actual-import'})
        behaviors = [self.store.put('behavior',{'dataset_id':source['id']}) for _ in range(4)]
        original=Store._decode; decoded=[]
        def tracked(row):
            decoded.append(row['id']);return original(row)
        with self.store.connect() as c, patch.object(Store,'_decode',side_effect=tracked):
            memo={}
            for behavior in behaviors:
                self.assertEqual(classify_record(c,behavior,memo=memo)['source_class'],'unversioned_log_source')
        self.assertEqual(decoded,[source['id']])
        run=self.store.put('observability_run',{'source':{'kind':'authored_example'}})
        self.assertTrue(self.classify(run)['fixture'])

    def test_ref_types_bounds_and_source_payload_tampering_remain_fail_closed(self):
        source=self.store.put('dataset',{'source':'actual-import'})
        for invalid in [dict(ref(source),version=True),dict(ref(source),version=1.0),dict(ref(source),hash='invalid'),dict(ref(source),extra='not an exact ref')]:
            self.assertEqual(_refs({'source_refs':{'dataset':invalid}}),[])
        refs=[{'id':'dataset-'+str(i),'version':1,'hash':'a'*64} for i in range(100)]
        self.assertEqual(len(_refs({'source_refs':refs})),64)
        self.assertEqual(_refs({'source_refs':{'dataset':ref(source)},'dataset_ref':ref(source)}),[ref(source)])
        behavior=self.store.put('behavior',{'dataset_ref':ref(source)})
        with self.store.connect() as c:
            c.execute('UPDATE objects SET payload=? WHERE id=?', ('{"source":"tampered"}',source['id']))
        with self.assertRaises(ValueError):self.classify(behavior)


if __name__ == '__main__':
    unittest.main()
