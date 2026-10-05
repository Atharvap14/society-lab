"""Actual constructed instructions remain authoritative during file edits.

Temporary registries and an inert harness only; no provider or production data.
"""
import hashlib
from pathlib import Path
import tempfile
import unittest

from swarm_lab.config import ROOT, Settings
from swarm_lab.research import ResearchAgents, TEXT, object_schema, prompt
from swarm_lab.store import Store, fingerprint


class ResearchPromptProvenanceTests(unittest.TestCase):
    def test_result_trace_keeps_executed_input_when_instruction_files_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'prompts').mkdir()
            (root / 'skills' / 'evaluator').mkdir(parents=True)
            files = [root / 'prompts' / 'research-contract.md',
                root / 'prompts' / 'evaluator.md', root / 'skills' / 'evaluator' / 'SKILL.md']
            original = ['Original shared contract.', 'Original evaluator prompt.', 'Original role skill.']
            for path, body in zip(files, original): path.write_text(body, encoding='utf-8')

            class MutatingFakeHarness:
                name = 'temporary_fake_no_provider'
                def run(self, system, task, tools, job_id, *, schema=None):
                    self.actual_input = system
                    for path in files: path.write_text('Revised after input construction.', encoding='utf-8')
                    return {'summary': 'Recorded inert fixture output.'}

            settings = Settings(root=root)
            store = Store(settings.runtime / 'lab.sqlite3')
            harness = MutatingFakeHarness()
            before = prompt(root, 'evaluator')
            result = ResearchAgents(settings, store, harness).run('evaluator', {'task': 'Inspect provenance.'},
                object_schema({'summary': TEXT}), {'messages': [], 'agents': []},
                {'graph': {'edges': []}, 'candidates': []}, 'temporary-prompt-provenance')
            traces = [row['payload'] for row in store.traces('temporary-prompt-provenance')]
            input_trace = next(row for row in traces if row['type'] == 'research_input')
            role_trace = next(row for row in traces if row['type'] == 'research_role')
            self.assertEqual(harness.actual_input, before)
            self.assertTrue(all(body in harness.actual_input for body in original))
            self.assertNotEqual(before, prompt(root, 'evaluator'))
            self.assertEqual(input_trace['system_prompt'], harness.actual_input)
            self.assertEqual(input_trace['prompt_hash'], fingerprint(harness.actual_input))
            self.assertEqual(role_trace['prompt_hash'], input_trace['prompt_hash'])
            self.assertNotEqual(role_trace['prompt_hash'], fingerprint(prompt(root, 'evaluator')))
            self.assertEqual(role_trace['invocation_id'], input_trace['invocation_id'])
            self.assertEqual(role_trace['result'], result)
            self.assertEqual(store.usage()['calls'], 0)

    def test_experiment_choice_map_is_available_through_bounded_reference_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'lab.sqlite3')
            agents = ResearchAgents(Settings(root=ROOT), store, None)
            tools = agents.tools({'messages': [], 'agents': []},
                {'graph': {'edges': []}, 'candidates': []})
            definition = tools['read_research_reference']['definition']
            self.assertIn('experiment-choice-map', definition['parameters']['properties']['name']['enum'])
            target = ROOT / 'research' / 'theory' / 'experiment-choice-map.md'
            raw = target.read_bytes()
            expected = raw.decode('utf-8')
            expected_hash = hashlib.sha256(raw).hexdigest()
            read = tools['read_research_reference']['execute']
            offset, pieces = 0, []
            while True:
                page = read(name='experiment-choice-map', start_character=offset, max_characters=1024)
                self.assertTrue(page['available'])
                self.assertEqual(page['source_sha256'], expected_hash)
                self.assertEqual(page['total_characters'], len(expected))
                self.assertEqual(page['start_character'], offset)
                self.assertEqual(page['text'], expected[offset:page['end_character_exclusive']])
                self.assertLessEqual(len(page['text']), 1024)
                self.assertEqual(page['has_before'], offset > 0)
                self.assertEqual(page['has_after'], page['end_character_exclusive'] < len(expected))
                self.assertEqual(page['truncated'], page['has_before'] or page['has_after'])
                self.assertGreater(page['end_character_exclusive'], offset)
                pieces.append(page['text']); offset = page['end_character_exclusive']
                if not page['has_after']: break
            self.assertEqual(''.join(pieces), expected)
            self.assertGreater(len(pieces), 1)
            self.assertEqual(store.usage()['calls'], 0)


if __name__ == '__main__': unittest.main()
