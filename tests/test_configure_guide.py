"""Explicit fresh-checkout allowance configuration; temporary roots, no providers."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from swarm_lab.config import ROOT, Settings
from swarm_lab.guide_assistant import guide_budget
from swarm_lab.pipeline import Lab


SPEC = importlib.util.spec_from_file_location('societylab_configure_guide', ROOT / 'scripts' / 'configure-guide.py')
configure = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(configure)


class ConfigureGuideTests(unittest.TestCase):
    def test_real_configuration_matches_guide_reader_and_mismatched_server_cap_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            lab = Lab(Settings(root=Path(directory), max_calls=400))
            self.assertEqual(guide_budget(lab)['configuration_status'], 'not_authorized')
            before = lab.store.usage()
            target = configure.configure_guide(directory, research_calls=400, guide_calls=100)
            self.assertEqual(target.read_bytes()[:1], b'{')  # UTF-8 without BOM.
            self.assertEqual(json.loads(target.read_text(encoding='utf-8')),
                {'baseline_calls': 400, 'max_additional_calls': 100})
            actual = guide_budget(lab)
            self.assertEqual((actual['configuration_status'], actual['research_limit'], actual['guide_limit'], actual['remaining']),
                ('configured', 400, 100, 100))
            lab.settings.max_calls = 399
            mismatch = guide_budget(lab)
            self.assertEqual((mismatch['configuration_status'], mismatch['remaining']), ('invalid_configuration', 0))
            self.assertEqual(lab.store.usage(), before)

    def test_explicit_reconfiguration_preserves_existing_usage_credentials_and_other_runtime_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            lab = Lab(Settings(root=Path(directory), max_calls=400))
            call_id = lab.store.reserve_call(400); lab.store.finish_call(call_id, 'complete', {'fixture': True})
            marker = lab.settings.runtime / 'saved-proof.json'; marker.write_bytes(b'unchanged authored proof fixture')
            secret_dir = Path(directory) / '.secrets'; secret_dir.mkdir()
            secret = secret_dir / 'openai-api-key.txt'; secret.write_bytes(b'not a real credential; must not be read')
            with lab.store.connect() as connection:
                original_calls = [tuple(row) for row in connection.execute('SELECT * FROM calls')]
            configure.configure_guide(directory, research_calls=400, guide_calls=2)
            configure.configure_guide(directory, research_calls=400, guide_calls=0)
            self.assertEqual(guide_budget(lab)['remaining'], 0)
            self.assertEqual(guide_budget(lab)['guide_limit'], 0)
            with lab.store.connect() as connection:
                self.assertEqual([tuple(row) for row in connection.execute('SELECT * FROM calls')], original_calls)
            self.assertEqual(marker.read_bytes(), b'unchanged authored proof fixture')
            self.assertEqual(secret.read_bytes(), b'not a real credential; must not be read')
            self.assertFalse(list(lab.settings.runtime.glob('guide-config-*.tmp')))

    def test_typed_budget_bounds_reject_before_creating_or_changing_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for value in (True, 1.0, '400', None, -1, 100001):
                for key in ('research_calls', 'guide_calls'):
                    kwargs = {'research_calls': 400, 'guide_calls': 100}; kwargs[key] = value
                    with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                        configure.configure_guide(root, **kwargs)
                    self.assertFalse((root / '.runtime').exists())
            configure.configure_guide(root, research_calls=100000, guide_calls=100000)
            saved = (root / '.runtime' / 'guide-config.json').read_bytes()
            with self.assertRaises(ValueError): configure.configure_guide(root, research_calls=0, guide_calls=float('nan'))
            self.assertEqual((root / '.runtime' / 'guide-config.json').read_bytes(), saved)

    def test_cli_requires_both_canonical_explicit_allowances_and_rejects_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            cases = [[], ['--research-calls', '400'], ['--guide-calls', '100'],
                ['--research-calls', '400', '--guide-calls', '01'],
                ['--research-calls', '400', '--guide-calls', '+1'],
                ['--research-calls', '400', '--guide-calls', '1.0'],
                ['--research-calls', '400', '--guide-calls', '100001'],
                ['--research-calls', '400', '--guide-calls', '10', '--guide-calls', '20']]
            for args in cases:
                with self.subTest(args=args), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as error: configure.main(args + ['--root', directory])
                    self.assertEqual(error.exception.code, 2)
                self.assertFalse((Path(directory) / '.runtime').exists())

    def test_actual_script_from_other_directory_saves_only_requested_config_without_key_output(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as working:
            result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'configure-guide.py'),
                '--root', root, '--research-calls', '400', '--guide-calls', '100'], cwd=working,
                env={**os.environ, 'OPENAI_API_KEY': 'authored-test-value-never-print'},
                capture_output=True, text=True, timeout=8)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('--max-calls 400 serve', result.stdout)
            self.assertIn('No API calls were made', result.stdout)
            self.assertNotIn('authored-test-value-never-print', result.stdout + result.stderr)
            files = sorted(path.relative_to(root).as_posix() for path in Path(root).rglob('*') if path.is_file())
            self.assertEqual(files, ['.runtime/guide-config.json'])


if __name__ == '__main__': unittest.main()
