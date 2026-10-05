"""Public CLI/Lab registry integration, using small temporary source files."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from swarm_lab.cli import main, read_source_plan
from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab
from swarm_lab.source_workflow import MAX_PLAN_BYTES


class SourceWorkflowIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.runtime = self.root / '.runtime'
        self.lab = Lab(Settings(root=self.root))
        self.source = self.root / 'events.jsonl'
        self.source.write_text(json.dumps({'id': '00000000-0000-0000-0000-000000000001',
                                          'data': {'actionType': 'WAIT'}}) + '\n', encoding='utf-8')
        self.plan = self.root / 'plan.json'
        self.plan.write_text(json.dumps({'sources': {'events': {'path': str(self.source)}}}), encoding='utf-8')

    def invoke(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            main(['--runtime', str(self.runtime), *args])
        return json.loads(output.getvalue())

    def test_cli_scan_and_exact_version_replay_are_persisted_without_raw_payload(self):
        created = self.invoke('scan-source-links', '--plan', str(self.plan))
        record = self.lab.store.get(created['id'], created['version'])
        self.assertEqual(created['kind'], 'source_link_audit')
        self.assertNotIn('payload', created)
        self.assertFalse(record['payload']['raw_records_persisted'])
        self.assertEqual(record['payload']['source_link_audit']['counts']['platform_actions']['WAIT'], 1)
        self.lab.store.put('source_link_audit', {'later': True}, record['id'])
        checked = self.invoke('replay-source-links', record['id'], '--version', '1')
        proof = self.lab.store.get(checked['id'])['payload']
        self.assertTrue(proof['passed'])
        self.assertTrue(proof['filesystem_reread_attempted'])
        self.assertTrue(proof['filesystem_reread_completed'])
        self.assertEqual(proof['audit_ref']['hash'], record['hash'])
        self.assertEqual(self.lab.store.usage()['calls'], 0)
        self.assertEqual(self.lab.store.list('behavior'), [])

    def test_cli_refuses_oversized_duplicate_nonfinite_and_unknown_plan_fields(self):
        invalid = [b' ' * (MAX_PLAN_BYTES + 1), b'{"sources":{},"sources":{}}',
                   b'{"sources":{},"extra":true}', b'{"sources":{},"expected_rows":NaN}']
        for value in invalid:
            with self.subTest(size=len(value)):
                self.plan.write_bytes(value)
                with self.assertRaises(ValueError):read_source_plan(self.plan)
        self.assertEqual(self.lab.store.list('source_link_audit'), [])


if __name__ == '__main__':
    unittest.main()
