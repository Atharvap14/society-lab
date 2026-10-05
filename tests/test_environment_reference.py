"""Research-only source inspection is bounded, exact and pinned."""
import hashlib
from pathlib import Path
import unittest
from swarm_lab.environment_reference import TARGETS,SECTIONS,read_environment_source


class EnvironmentReferenceTests(unittest.TestCase):
    def test_all_declared_sections_return_exact_source_and_hashes(self):
        base=Path(__file__).resolve().parents[1]/'swarm_lab'
        for template,(filename,_) in TARGETS.items():
            raw=(base/filename).read_bytes();digest=hashlib.sha256(raw).hexdigest();lines=raw.decode('utf-8').splitlines()
            for section in SECTIONS:
                with self.subTest(template=template,section=section):
                    result=read_environment_source(template,section,digest)
                    expected='\n'.join(lines[result['line_start']-1:result['line_end']])
                    self.assertEqual(result['text'],expected[:16000]);self.assertEqual(result['source_sha256'],digest)
                    self.assertLessEqual(len(result['text']),16000)

    def test_stale_source_pin_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'hash differs'):read_environment_source('complementary_information','actions','0'*64)

    def test_arbitrary_file_and_symbol_requests_are_rejected(self):
        for template,section in [('../../.secrets/key','factory'),('complementary_information','__init__')]:
            with self.assertRaisesRegex(ValueError,'allowlisted'):read_environment_source(template,section)

if __name__=='__main__':unittest.main()
