"""Investigation ingress pins exact source versions before any model work."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from swarm_lab.config import ROOT, Settings
from swarm_lab.pipeline import Lab


def ref(value): return {key: value[key] for key in ('id', 'version', 'hash')}


class InvestigationPinsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.lab = Lab(Settings(root=Path(self.temp.name), max_calls=0))
        self.dataset = self.lab.ingest(ROOT / 'examples' / 'coordination_fixture', limit=100)
        self.discovery = self.lab.observe(self.dataset['id'])
        self.candidate = next(candidate for candidate in self.discovery['payload']['candidates'] if candidate['kind'] == 'completion_report_cluster')

    def test_exact_old_discovery_and_dataset_used_after_new_versions_arrive(self):
        later = self.lab.store.put('discovery', {**self.discovery['payload'], 'candidates': []}, self.discovery['id'])
        self.lab.store.put('dataset', {**self.dataset['payload'], 'messages': []}, self.dataset['id'])
        behavior = self.lab.investigate(self.discovery['id'], discovery_version=self.discovery['version'],
            discovery_hash=self.discovery['hash'], candidate_ids=[self.candidate['id']])[0]
        self.assertEqual(behavior['payload']['source_refs']['discovery'], ref(self.discovery))
        self.assertEqual(behavior['payload']['source_refs']['dataset'], ref(self.dataset))
        self.assertNotEqual(behavior['payload']['source_refs']['discovery'], ref(later))
        self.assertEqual(self.lab.store.usage()['calls'], 0)

    def test_pairs_types_and_hash_drift_fail_before_harness_or_library_write(self):
        invalid = [dict(discovery_version=1), dict(discovery_hash=self.discovery['hash']),
            dict(discovery_version=True, discovery_hash=self.discovery['hash']),
            dict(discovery_version=1.0, discovery_hash=self.discovery['hash']),
            dict(discovery_version=0, discovery_hash=self.discovery['hash']),
            dict(discovery_version=1, discovery_hash='0' * 64)]
        before = self.lab.store.list(limit=200)
        with patch.object(self.lab, 'research_harness', side_effect=AssertionError('Wrong source cannot spend a call')):
            for kwargs in invalid:
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    self.lab.investigate(self.discovery['id'], live=True, **kwargs)
        self.assertEqual(self.lab.store.list(limit=200), before)
        self.assertEqual(self.lab.store.usage()['calls'], 0)

    def test_resealed_discovery_with_inconsistent_dataset_hash_fails_before_model(self):
        wrong = copy.deepcopy(self.discovery['payload'])
        wrong['dataset_ref']['hash'] = '0' * 64
        corrupted = self.lab.store.put('discovery', wrong)
        with patch.object(self.lab, 'research_harness', side_effect=AssertionError('No provider')):
            with self.assertRaises(ValueError):
                self.lab.investigate(corrupted['id'], discovery_version=corrupted['version'], discovery_hash=corrupted['hash'], live=True)
        self.assertEqual(self.lab.store.list('behavior'), [])

    def test_legacy_id_only_still_uses_current_discovery_and_authenticates_dataset(self):
        behavior = self.lab.investigate(self.discovery['id'], candidate_ids=[self.candidate['id']])[0]
        self.assertEqual(behavior['payload']['source_refs']['discovery'], ref(self.discovery))
        self.assertEqual(behavior['payload']['source_refs']['dataset'], ref(self.dataset))


if __name__ == '__main__': unittest.main()
