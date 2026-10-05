"""Temporary-only host registration, invocation, failure and replay checks."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from swarm_lab.config import Settings
from swarm_lab.store import Store
from swarm_lab.server import _QueuedStore

from swarm_lab import revision_relay_workflow as host


class FakeLab:
    def __init__(self, root, *, max_calls=400):
        self.settings = Settings(root=Path(root), max_calls=max_calls)
        self.store = Store(self.settings.runtime / 'lab.sqlite3')
        self.factories = []
        self.calls = []
        self.fail_after = None
        self.output = None

    def harness(self, name):
        if name != 'responses':
            raise AssertionError('Only pinned Responses construction is allowed')
        self.factories.append(name)
        return FakeSubject(self)


class FakeSubject:
    def __init__(self, lab):
        self.lab = lab

    def subject(self, request):
        call_id = self.lab.store.reserve_call(self.lab.settings.max_calls)
        self.lab.calls.append(copy.deepcopy(request))
        if self.lab.fail_after is not None and len(self.lab.calls) > self.lab.fail_after:
            self.lab.store.finish_call(call_id, 'failed')
            self.lab.store.trace(request['_job_id'], {'type': 'api_error', 'status': 503,
                'detail': 'Private provider envelope fixture is never retained'})
            raise RuntimeError('Deliberately unavailable test transport')
        self.lab.store.finish_call(call_id, 'completed', {'input_tokens': 2,
            'output_tokens': 1, 'provider_payload': {'unwanted': 'envelope'}})
        self.lab.store.trace(request['_job_id'], {'type': 'model_response',
            'output': [{'provider_payload': 'unwanted'}], 'usage': {'input_tokens': 2,
                'provider_payload': 'unwanted'}})
        if self.lab.output is not None:
            return copy.deepcopy(self.lab.output)
        return host._runner().revision_relay_scoped_policy(request)


class RevisionRelayHostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.lab = FakeLab(self.temp.name)

    def design(self, **kwargs):
        return host.design_revision_relay(self.lab, blocks=1, **kwargs)

    def execute(self, protocol, **kwargs):
        return host.experiment_revision_relay(self.lab, protocol['id'],
            protocol_version=protocol['version'], **kwargs)

    def audit(self, result):
        return host.audit_revision_relay(self.lab, result['id'], version=result['version'])

    def test_scripted_end_to_end_exact_archive_zero_calls(self):
        p = self.design()
        result = self.execute(p)
        payload = result['payload']
        self.assertEqual(payload['status'], 'complete')
        self.assertEqual(len(payload['raw_report']['runs']), 4)
        self.assertEqual(payload['protocol_ref'], host._ref(p))
        self.assertFalse(payload['status_promotion'])
        self.assertFalse(payload['generic_cycle_support'])
        self.assertTrue(all(pin for pin in payload['artifact_pins'].values()))
        proof = self.audit(result)['payload']
        self.assertTrue(proof['passed'], proof)
        self.assertTrue(proof['complete_execution'])
        self.assertTrue(proof['quantitative_available'])
        self.assertFalse(proof['partial_trace_consistent'])
        self.assertEqual(self.lab.store.usage()['calls'], 0)
        self.assertEqual(self.lab.factories, [])
        self.assertEqual(self.lab.store.get_job(payload['study_claim_id'])['status'], 'completed')

    def test_optional_behavior_historical_ref_never_promoted(self):
        behavior = self.lab.store.put('behavior', {'status': 'proposed', 'claim': 'fixture'})
        p = self.design(behavior_ref=host._ref(behavior))
        later = self.lab.store.put('behavior', {'status': 'rejected', 'claim': 'later review'}, behavior['id'])
        result = self.execute(p)
        self.assertEqual(result['payload']['behavior_ref'], host._ref(behavior))
        self.assertTrue(self.audit(result)['payload']['passed'])
        self.assertEqual(len(self.lab.store.history(behavior['id'])), 2)
        self.assertEqual(self.lab.store.get(behavior['id'])['hash'], later['hash'])

    def test_exact_protocol_version_and_repeated_claim_refusal(self):
        p = self.design()
        later_payload = copy.deepcopy(p['payload'])
        later_payload['status'] = 'retired'
        self.lab.store.put('revision_relay_protocol', later_payload, p['id'])
        result = self.execute(p, job_id='first-study')
        self.assertTrue(self.audit(result)['payload']['passed'])
        with self.assertRaises(ValueError):
            self.execute(p, job_id='second-study')
        self.assertEqual(len(self.lab.store.list('revision_relay_experiment')), 1)
        self.assertFalse(self.lab.store.job_exists('second-study'))

    def test_mode_model_source_and_spec_rejected_before_harness(self):
        offline = self.design()
        with self.assertRaises(ValueError): self.execute(offline, live=True)
        live = self.design(live=True)
        with self.assertRaises(ValueError): self.execute(live, live=False)
        self.lab.settings.model = 'different-frozen-model'
        with self.assertRaises(ValueError): self.execute(live, live=True)
        self.lab.settings.model = live['payload']['backend']['model']
        malformed = copy.deepcopy(live['payload'])
        malformed['protocol']['environment']['api_version'] = 'future-version'
        forged = self.lab.store.put('revision_relay_protocol', malformed)
        with self.assertRaises(ValueError): self.execute(forged, live=True)
        fake_ref = {'id': 'missing-behavior', 'version': 1, 'hash': '0' * 64}
        with self.assertRaises(KeyError): self.design(behavior_ref=fake_ref)
        self.assertEqual(self.lab.factories, [])
        self.assertEqual(self.lab.store.usage()['calls'], 0)
        self.assertEqual(self.lab.store.jobs(), [])

    def test_strict_input_bounds_and_assumption_declarations(self):
        for kwargs in ({'blocks': True}, {'seed': 1.0}, {'live': 1},
                {'interval_assumptions': []}, {'interval_assumptions': {}},
                {'interval_assumptions': {'independent_blocks_declared': 1,
                    'stable_subject_backend_declared': True}}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                host.design_revision_relay(self.lab, **kwargs)
        p = self.design()
        for version in (True, 1.0, 0):
            with self.assertRaises(ValueError):
                host.experiment_revision_relay(self.lab, p['id'], protocol_version=version)
        with self.assertRaises(ValueError): self.execute(p, job_id='../outside')
        with self.assertRaises(ValueError): self.execute(p, job_id='hf_' + 'x' * 30)
        self.assertEqual(self.lab.store.jobs(), [])

    def test_call_reservations_not_completed_control_preflight(self):
        self.lab.settings.max_calls = 16
        first = self.lab.store.reserve_call(16)
        self.lab.store.finish_call(first, 'failed')
        p = self.design(live=True)
        self.assertEqual(self.lab.store.usage()['completed'], 0)
        with self.assertRaises(ValueError): self.execute(p, live=True)
        self.assertEqual(self.lab.factories, [])
        self.assertEqual(self.lab.store.jobs(), [])
        self.assertEqual(self.lab.settings.max_calls, 16)

    def test_configured_cap_honored_without_raise_or_hardcoded_min(self):
        # Only this isolated fixture supplies 416: the host never changes it.
        self.lab.settings.max_calls = 416
        for _ in range(400): self.lab.store.reserve_call(416)
        p = self.design(live=True)
        result = self.execute(p, live=True)
        self.assertEqual(self.lab.settings.max_calls, 416)
        self.assertEqual(self.lab.store.usage()['calls'], 416)
        self.assertTrue(self.audit(result)['payload']['passed'])

    def test_fake_live_calls_traces_minimal_metadata_and_no_envelope(self):
        p = self.design(live=True)
        result = self.execute(p, live=True)
        self.assertEqual(self.lab.factories, ['responses'])
        self.assertEqual(self.lab.store.usage()['calls'], 16)
        self.assertEqual(self.lab.store.usage()['completed'], 16)
        traces = self.lab.store.traces(result['payload']['research_job_id'])
        self.assertEqual(len(traces), 16)
        for trace in traces:
            metadata = trace['payload']
            self.assertEqual(metadata['type'], 'subject_response_metadata')
            self.assertNotIn('output', metadata)
            self.assertNotIn('provider_payload', json.dumps(metadata))
            self.assertIsNone(metadata['response_id'])
            self.assertEqual(metadata['metadata_status']['response_id'], 'unknown')
            self.assertIsNone(metadata['usage']['output_tokens'])
            self.assertEqual(metadata['provider_origin'], 'metadata_not_attested')
        self.assertTrue(self.audit(result)['payload']['passed'])
        self.assertEqual(self.lab.store.usage()['calls'], 16)

    def test_transport_failure_durable_partial_and_no_retry(self):
        p = self.design(live=True)
        self.lab.fail_after = 2
        with self.assertRaises(host._runner().RevisionRelayExecutionError):
            self.execute(p, live=True, job_id='transport-failure')
        job = self.lab.store.get_job('transport-failure')
        self.assertEqual(job['status'], 'failed')
        result = self.lab.store.get(job['payload']['incomplete_result_id'])
        raw = result['payload']['raw_report']
        self.assertEqual(raw['status'], 'incomplete')
        self.assertIsNone(raw['analysis'])
        self.assertEqual(len(raw['assignments']), 4)
        boundaries = [boundary for row in raw['runs'] for boundary in row['boundaries']]
        self.assertEqual(boundaries[-1]['invocation_status'], 'attempted_unknown')
        self.assertFalse(boundaries[-1]['action_applied'])
        proof = self.audit(result)['payload']
        self.assertFalse(proof['passed'])
        self.assertTrue(proof['partial_trace_consistent'], proof)
        self.assertFalse(proof['quantitative_available'])
        self.assertEqual(self.lab.store.usage()['calls'], 3)
        with self.assertRaises(ValueError): self.execute(p, live=True, job_id='retry')
        self.assertEqual(self.lab.store.usage()['calls'], 3)
        self.assertFalse(self.lab.store.job_exists('retry'))

    def test_setup_failure_closes_fixed_claim_before_materialization(self):
        p = self.design()
        original = self.lab.store.start_job
        def fail_outer(identity, payload):
            if identity == 'outer-fails': raise RuntimeError('Temporary outer claim race')
            return original(identity, payload)
        with patch.object(self.lab.store, 'start_job', side_effect=fail_outer):
            with self.assertRaises(RuntimeError): self.execute(p, job_id='outer-fails')
        claim_id = 'relay-study-' + host._runner()._hash(host._ref(p))[:24]
        failed = self.lab.store.get_job(claim_id)
        self.assertEqual(failed['status'], 'failed')
        result = self.lab.store.get(failed['payload']['incomplete_result_id'])
        self.assertIsNone(result['payload']['raw_report'])
        self.assertEqual(result['payload']['status'], 'incomplete_host_failure')
        self.assertFalse(self.lab.store.job_exists('outer-fails'))
        self.assertFalse(self.audit(result)['payload']['passed'])
        self.assertEqual(self.lab.factories, [])

    def test_publication_failure_retains_complete_exact_result(self):
        p = self.design()
        original = self.lab.store.job
        fired = []
        def fail_publication(identity, status, payload):
            if identity == 'publish-fails' and status == 'completed' and not fired:
                fired.append(True); raise RuntimeError('Temporary publication failure')
            return original(identity, status, payload)
        with patch.object(self.lab.store, 'job', side_effect=fail_publication):
            with self.assertRaises(RuntimeError): self.execute(p, job_id='publish-fails')
        job = self.lab.store.get_job('publish-fails')
        result = self.lab.store.get(job['payload']['incomplete_result_id'])
        self.assertEqual(result['payload']['status'], 'complete')
        self.assertEqual(job['payload']['execution_report_status'], 'complete')
        self.assertEqual(len(self.lab.store.list('revision_relay_experiment')), 1)
        self.assertTrue(self.audit(result)['payload']['passed'])
        with self.assertRaises(ValueError): self.execute(p, job_id='new-publication')

    def test_queued_proxy_progress_and_component_completion(self):
        p = self.design(live=True)
        base = self.lab.store
        base.job('queued-relay', 'queued', {'action': 'experiment_revision_relay',
            'args': {'protocol_id': p['id'], 'protocol_version': p['version'], 'live': True}})
        self.lab.store = _QueuedStore(base, 'queued-relay', 'experiment_revision_relay')
        result = self.execute(p, live=True, job_id='queued-relay')
        self.assertEqual(base.get_job('queued-relay')['status'], 'running')
        self.assertEqual(base.get_job('queued-relay')['payload']['component_status'], 'completed')
        self.assertEqual(base.get_job(result['payload']['study_claim_id'])['status'], 'completed')
        self.assertEqual(base.usage()['calls'], 16)
        self.assertEqual(len(base.traces('queued-relay')), 16)
        self.assertTrue(self.audit(result)['payload']['passed'])

    def test_bounded_invalid_output_consumes_but_identity_change_aborts(self):
        p = self.design(live=True)
        self.lab.output = {'action': 'unsupported_action'}
        result = self.execute(p, live=True)
        self.assertEqual(result['payload']['status'], 'complete')
        self.assertTrue(all(row['outcomes']['C_final_correct'] == 0 for row in result['payload']['raw_report']['runs']))
        self.assertTrue(self.audit(result)['payload']['passed'])
        p2 = self.design(live=True, seed=174)
        self.lab.output = {'action': 'wait', 'reason': 'hf_' + 'x' * 30}
        with self.assertRaises(host._runner().RevisionRelayExecutionError): self.execute(p2, live=True)
        partial = self.lab.store.list('revision_relay_experiment')[0]
        self.assertEqual(partial['payload']['status'], 'incomplete')
        self.assertNotIn('[REDACTED_CREDENTIAL]', json.dumps(partial['payload']))
        self.assertIsNone(partial['payload']['raw_report']['analysis'])

    def test_resealed_wrapper_scalar_identity_changes_fail_audit(self):
        result = self.execute(self.design())
        for field, value in (('agent_mode', 'live'), ('study_claim_id', 'wrong-claim'),
                ('research_job_id', '../outside'), ('status_promotion', True),
                ('generic_cycle_support', True), ('host_failure_error_type', {'error': 'forged'})):
            payload = copy.deepcopy(result['payload']); payload[field] = value
            forged = self.lab.store.put('revision_relay_experiment', payload)
            with self.subTest(field=field): self.assertFalse(self.audit(forged)['payload']['passed'])
        payload = copy.deepcopy(result['payload']); payload['host_failure_error_type'] = 'RuntimeError'
        forged = self.lab.store.put('revision_relay_experiment', payload)
        self.assertFalse(self.audit(forged)['payload']['passed'])
        self.assertEqual(self.lab.factories, [])

    def test_registered_artifact_byte_change_and_concurrent_change_fail(self):
        result = self.execute(self.design())
        path = Path(result['payload']['artifact_directory']) / 'report.json'
        before = path.read_bytes()
        path.write_bytes(before + b' ')
        self.assertFalse(self.audit(result)['payload']['passed'])
        path.write_bytes(before)
        runner = host._runner(); original = runner.replay_revision_relay_report
        def mutate_after_replay(*args, **kwargs):
            replay = original(*args, **kwargs)
            path.write_bytes(before + b' ')
            return replay
        with patch.object(runner, 'replay_revision_relay_report', side_effect=mutate_after_replay):
            self.assertFalse(self.audit(result)['payload']['passed'])

    def test_physical_file_reads_capped_before_decode(self):
        class RecordingStream(io.BytesIO):
            def __init__(self, content): super().__init__(content); self.requests = []
            def read(self, size=-1): self.requests.append(size); return super().read(size)
        stream = RecordingStream(b'{}' + b' ' * 16)
        with patch.object(Path, 'open', return_value=stream):
            with self.assertRaises(ValueError): host._read_bytes(Path('fixture.json'), 8)
        self.assertEqual(stream.requests, [9])
        for data in (b'{"id":1,"id":2}', b'{"value":NaN}'):
            path = Path(self.temp.name) / 'bad.json'; path.write_bytes(data)
            with self.assertRaises(ValueError): host._read_json(path, 256)


if __name__ == '__main__': unittest.main()
