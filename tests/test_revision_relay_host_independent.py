"""Independent host attacks using isolated registries and CPU subjects only."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab

from swarm_lab import revision_relay_workflow as host

class RelayHostIndependentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lab = Lab(Settings(root=Path(self.tmp.name), max_calls=400))

    def execute(self):
        registered = host.design_revision_relay(self.lab, blocks=1, seed=880)
        result = host.experiment_revision_relay(self.lab, registered['id'],
            protocol_version=registered['version'], job_id='independent-relay-once')
        return registered, result

    def test_exact_historical_version_and_no_cross_mode_execution(self):
        registered, result = self.execute()
        self.lab.store.put('revision_relay_protocol', {'changed': True}, registered['id'])
        self.assertTrue(host.audit_revision_relay(self.lab, result['id'], version=1)['payload']['passed'])
        before = len(self.lab.store.list('revision_relay_experiment'))
        with self.assertRaises(ValueError):
            host.experiment_revision_relay(self.lab, registered['id'], protocol_version=1,
                live=True, job_id='different-mode')
        self.assertEqual(before, len(self.lab.store.list('revision_relay_experiment')))
        self.assertEqual(self.lab.store.usage()['calls'], 0)

    def test_reserved_calls_count_toward_preflight_before_harness_or_claim(self):
        registered = host.design_revision_relay(self.lab, blocks=1, live=True)
        for _ in range(385):
            self.lab.store.reserve_call(400)
        self.assertEqual(self.lab.store.usage()['completed'], 0)
        with patch.object(Lab, 'harness', side_effect=AssertionError('No provider allowed')):
            with self.assertRaisesRegex(ValueError, 'cap'):
                host.experiment_revision_relay(self.lab, registered['id'], protocol_version=1,
                    live=True, job_id='blocked-before-harness')
        self.assertFalse(self.lab.store.get_job('blocked-before-harness'))
        self.assertEqual(self.lab.store.list('revision_relay_experiment'), [])
        self.assertEqual(self.lab.store.usage()['calls'], 385)

    def test_unknown_completion_never_retries_under_new_job_name(self):
        registered, result = self.execute()
        evidence = Path(result['payload']['artifact_directory']) / 'report.json'
        before = evidence.read_bytes()
        with self.assertRaises(ValueError):
            host.experiment_revision_relay(self.lab, registered['id'], protocol_version=1,
                job_id='fresh-name-same-study')
        self.assertEqual(before, evidence.read_bytes())
        self.assertEqual(len(self.lab.store.list('revision_relay_experiment')), 1)
        self.assertFalse(self.lab.store.get_job('fresh-name-same-study'))

    def test_resealed_wrapper_contradictions_cannot_authorize_quantitative_replay(self):
        _, result = self.execute()
        mutations = [('agent_mode', 'live'), ('study_claim_id', 'relay-study-' + '0' * 24),
                     ('research_job_id', '../escaped'), ('host_failure_error_type', 'RuntimeError'),
                     ('status_promotion', True), ('generic_cycle_support', True)]
        for key, value in mutations:
            with self.subTest(key=key):
                changed = copy.deepcopy(result['payload']); changed[key] = value
                forged = self.lab.store.put('revision_relay_experiment', changed)
                self.assertFalse(host.audit_revision_relay(self.lab, forged['id'], version=1)['payload']['passed'])
        self.assertEqual(self.lab.store.usage()['calls'], 0)

    def test_setup_failure_closes_claim_and_preserves_unknown_evidence(self):
        registered = host.design_revision_relay(self.lab, blocks=1)
        original = self.lab.store.start_job
        def start(identity, payload):
            if identity == 'outer-collision':
                raise RuntimeError('fixture setup failure')
            return original(identity, payload)
        with patch.object(self.lab.store, 'start_job', side_effect=start):
            with self.assertRaises(RuntimeError):
                host.experiment_revision_relay(self.lab, registered['id'], protocol_version=1,
                    job_id='outer-collision')
        claims = [j for j in self.lab.store.jobs() if j['id'].startswith('relay-study-')]
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]['status'], 'failed')
        self.assertEqual(self.lab.store.usage()['calls'], 0)
        saved = self.lab.store.list('revision_relay_experiment')
        self.assertEqual(len(saved), 1)
        self.assertIsNone(saved[0]['payload']['analysis'])

    def test_size_check_race_still_bounds_file_read_before_decoding(self):
        target = Path(self.tmp.name) / 'growing.json'
        target.write_text(json.dumps({'text': 'x' * 2048}), encoding='utf-8')
        actual = list(target.stat()); actual[6] = 1
        with patch.object(Path, 'stat', return_value=os.stat_result(actual)):
            with self.assertRaises(ValueError):
                host._read_json(target, 64)

    def test_subject_metadata_facade_preserves_atomic_budget_and_drops_envelope(self):
        facade = host._SubjectTraceStore(self.lab.store)
        call = facade.reserve_call(1)
        with self.assertRaises(RuntimeError):
            self.lab.store.reserve_call(1)
        facade.finish_call(call, 'completed', {'input_tokens': 7, 'output_tokens': True,
            'total_tokens': 11, 'provider_detail': 'unretained fixture'})
        facade.trace('fixture-metadata', {'type': 'model_response', 'response_id': 'fixture-id',
            'model': 'fixture-model', 'usage': {'input_tokens': 7},
            'response': {'arbitrary': 'raw-output-must-not-persist'}, 'seconds': float('nan')})
        facade.trace('fixture-metadata', {'type': 'api_error', 'status': 503,
            'error': 'raw-error-must-not-persist'})
        text = json.dumps(self.lab.store.traces('fixture-metadata'))
        self.assertNotIn('raw-output-must-not-persist', text)
        self.assertNotIn('raw-error-must-not-persist', text)
        self.assertEqual(self.lab.store.usage()['input_tokens'], 7)
        self.assertEqual(self.lab.store.usage()['output_tokens'], 0)
        row = self.lab.store.traces('fixture-metadata')[0]['payload']
        self.assertIsNone(row['seconds'])
        self.assertEqual(row['metadata_status']['seconds'], 'unknown')
        self.assertEqual(row['metadata_status']['response_id'], 'reported_unattested')


if __name__ == '__main__':
    unittest.main()
