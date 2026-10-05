import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]

class MeasurementReviewUITests(unittest.TestCase):
    def test_pure_renderer_adversarial_checks_and_real_schema(self):
        node=shutil.which('node') or 'C:/Program Files/nodejs/node.exe'
        result=subprocess.run([node,str(ROOT/'tests/js/measurement-review-checks.js'),
                               str(ROOT/'web/measurement-review.js'),
                               str(ROOT/'tests/fixtures/measurement-review-schema.json')],
                              capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout)
        self.assertIs(report['passed'],True)
        self.assertEqual(report['checks'],18)
