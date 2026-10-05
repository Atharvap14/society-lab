"""Actual loopback report reads from authored temporary results; no providers."""
import json
import urllib.error
import urllib.parse
import urllib.request
import unittest

from tests import test_lab_workspace as fixture


class GuideReportApiTests(unittest.TestCase):
    def setUp(self):
        self.host = fixture.WorkspaceHttpTests()
        self.addCleanup(self.host.doCleanups)
        self.host.setUp()
        self.lab = self.host.lab
        static = self.lab.settings.root / 'web'; static.mkdir(exist_ok=True)
        (static / 'index.html').write_text('<p>Authored temporary host page</p>', encoding='utf-8')
        self.record = self.lab.store.put('experiment', {
            'source_kind': 'authored_test_fixture', 'status': 'complete',
            'analysis': {'arms': {'placebo': {'n': 2, 'success': .5}, 'evidence_thought': {'n': 2, 'success': 1}},
                'primary_effect': {'difference': .5, 'ci95': [-.2, .9], 'interval_method': 'Authored fixture only'},
                'warnings': ['<script>not executable</script>']}})
        self.query = {'object_id': self.record['id'], 'version': '1', 'hash': self.record['hash']}

    def url(self, values=None):
        return self.host.base + '/api/guide/report?' + urllib.parse.urlencode(values or self.query, doseq=True)

    def test_exact_old_html_read_is_script_free_and_other_report_routes_stay_isolated(self):
        self.lab.store.put('experiment', {'analysis': {}}, self.record['id'])
        before = (self.lab.store.history(self.record['id']), self.lab.store.jobs(), self.lab.store.usage())
        with urllib.request.urlopen(self.url(), timeout=8) as response:
            doc = response.read().decode('utf-8')
            self.assertEqual(response.headers['Content-Type'], 'text/html; charset=utf-8')
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
            self.assertEqual(response.headers['Content-Security-Policy'],
                "default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'self'")
        self.assertIn('50.0%', doc)
        self.assertIn(self.record['hash'], doc)
        self.assertIn('&lt;script&gt;', doc)
        self.assertNotIn('<script>', doc)
        with urllib.request.urlopen(self.host.base + '/', timeout=8) as response:
            self.assertIn("frame-src 'self'", response.headers['Content-Security-Policy'])
        root = self.lab.settings.runtime / 'reports'; root.mkdir(exist_ok=True)
        (root / 'authored.html').write_text('<p>Authored temporary file</p>', encoding='utf-8')
        with urllib.request.urlopen(self.host.base + '/reports/authored.html', timeout=8) as response:
            self.assertIn("frame-ancestors 'none'", response.headers['Content-Security-Policy'])
        self.assertEqual((self.lab.store.history(self.record['id']), self.lab.store.jobs(), self.lab.store.usage()), before)

    def test_query_and_fingerprint_fail_closed_without_writes_or_defaulting_to_latest(self):
        before = (self.lab.store.list(limit=1000), self.lab.store.jobs(), self.lab.store.usage())
        bad = [self.query | {'version': '01'}, self.query | {'version': '1.0'},
            self.query | {'version': ['1', '2']}, self.query | {'version': ''},
            self.query | {'hash': '0' * 64}, self.query | {'object_id': '../x'},
            self.query | {'url': 'https://outside.invalid'}, {'object_id': self.record['id'], 'version': '1'}]
        for values in bad:
            with self.subTest(values=values), self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(self.url(values), timeout=8)
            self.assertEqual(error.exception.code, 400)
            self.assertIn('error', json.loads(error.exception.read()))
        self.assertEqual((self.lab.store.list(limit=1000), self.lab.store.jobs(), self.lab.store.usage()), before)


if __name__ == '__main__': unittest.main()
