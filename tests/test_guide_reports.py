import tempfile
import unittest
from pathlib import Path
from swarm_lab.guide_reports import render_report, report_ref
from swarm_lab.store import Store


class GuideReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / 'lab.sqlite3')
        self.record = self.store.put('experiment', {'analysis': {'arms': {'baseline': {'n': 2, 'success': 0.5}, 'placebo': {'n': 2, 'success': 1}, 'evidence_thought': {'n': 2, 'success': 0.5}}, 'primary_effect': {'difference': -0.5, 'ci95': [-0.9, 0.27], 'interval_method': 'Newcombe_Wilson'}, 'warnings': ['<script>alert(1)</script>']}})
        self.ref = {k: self.record[k] for k in ('id', 'version', 'hash')}

    def test_exact_older_result_survives_newer_version(self):
        self.store.put('experiment', {'analysis': {}}, self.record['id'])
        doc = render_report(self.store, self.ref)
        self.assertIn('50.0%', doc)
        self.assertIn('-50.0 percentage points', doc)
        self.assertIn('-90.0 to +27.0 points', doc)
        self.assertIn('inconclusive', doc)
        self.assertIn(self.ref['hash'], doc)

    def test_no_active_content_or_wrong_fingerprint(self):
        doc = render_report(self.store, self.ref)
        self.assertNotIn('<script>', doc)
        self.assertIn('&lt;script&gt;', doc)
        self.assertNotIn('onload=', doc)
        with self.assertRaises(ValueError):
            render_report(self.store, {**self.ref, 'hash': 'f' * 64})

    def test_missing_rates_are_not_zero_and_non_results_refused(self):
        r = self.store.put('experiment', {'analysis': {'arms': {'x': {'n': 2, 'success': None}}}})
        doc = render_report(self.store, {k: r[k] for k in self.ref})
        self.assertIn('no compatible', doc)
        self.assertNotIn('0.0%', doc)
        draft = self.store.put('workspace_draft', {})
        with self.assertRaises(ValueError):
            render_report(self.store, {k: draft[k] for k in self.ref})

    def test_strict_query_rejects_duplicates_traversal_and_unknowns(self):
        query = {'object_id': [self.ref['id']], 'version': ['1'], 'hash': [self.ref['hash']]}
        self.assertEqual(report_ref(query), self.ref)
        for bad in [{**query, 'object_id': ['../x']}, {**query, 'version': ['1', '2']}, {**query, 'url': ['https://bad']}]:
            with self.assertRaises(ValueError):
                report_ref(bad)
