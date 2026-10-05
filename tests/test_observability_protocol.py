"""Authored temporary telemetry tests, not empirical swarm observations."""
import concurrent.futures
import copy
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from swarm_lab.config import Settings
from swarm_lab.observability_protocol import (brief_dataset, canonical, connect_observability,
    follow_observability, parse_follow_query, parse_batch, protocol_manifest, validate_batch)
from swarm_lab.pipeline import Lab
from swarm_lab.server import LocalResearchServer, serve


def raw(value): return json.dumps(value, ensure_ascii=False).encode()
def ref(record): return {key: record[key] for key in ('id', 'version', 'hash')}


class ObservabilityProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.lab = Lab(Settings(root=Path(self.temp.name), max_calls=0))
        self.example = protocol_manifest()['example']

    def exact(self, reference):
        result = self.lab.store.get(reference['id'], reference['version'])
        self.assertEqual(ref(result), reference)
        return result

    def test_explicit_authored_source_original_capture_order_and_zero_calls(self):
        connected = connect_observability(self.lab, raw(self.example))
        run = self.exact(connected['run_ref'])
        dataset = self.exact(connected['dataset_ref'])
        brief = self.exact(connected['brief_ref'])
        discovery = self.exact(connected['discovery_ref'])
        self.assertEqual(run['payload']['events'], self.example['events'])
        self.assertEqual(run['payload']['source']['kind'], 'authored_example')
        self.assertFalse(run['payload']['provenance']['independently_verified'])
        self.assertEqual(len(dataset['payload']['messages']), 3)
        self.assertEqual(dataset['payload']['events'], [])
        self.assertEqual(brief['payload']['source_refs'], {'run_ref': connected['run_ref'], 'dataset_ref': connected['dataset_ref']})
        self.assertEqual(discovery['payload']['dataset_ref'], connected['dataset_ref'])
        self.assertEqual(self.lab.store.usage()['calls'], 0)
        self.assertEqual(self.lab.store.jobs(), [])

    def test_delta_append_and_original_batch_retry_keep_exact_historical_references(self):
        first_batch = {**self.example, 'events': self.example['events'][:10]}
        delta = {**self.example, 'events': self.example['events'][10:]}
        first = connect_observability(self.lab, raw(first_batch))
        second = connect_observability(self.lab, raw(delta))
        self.assertEqual(second['run_ref']['id'], first['run_ref']['id'])
        self.assertEqual(second['run_ref']['version'], 2)
        self.assertEqual(self.exact(second['run_ref'])['payload']['previous_ref'], first['run_ref'])
        self.assertEqual(self.exact(second['run_ref'])['payload']['events'], self.example['events'])
        retried = connect_observability(self.lab, raw(first_batch))
        for key in ('run_ref', 'dataset_ref', 'brief_ref', 'discovery_ref'):
            self.assertEqual(retried[key], first[key])
        self.assertTrue(retried['idempotent'])
        self.assertEqual(retried['follow_ref'], second['run_ref'])
        self.assertEqual(len(self.lab.store.history(first['run_ref']['id'])), 2)
        self.assertEqual(self.exact(first['brief_ref'])['payload']['source_refs']['run_ref'], first['run_ref'])

    def test_conflicting_duplicate_event_or_changed_source_metadata_is_atomic_rejection(self):
        first = connect_observability(self.lab, raw(self.example))
        before = self.lab.store.list(limit=200)
        conflict = copy.deepcopy(self.example)
        conflict['events'][0]['data']['name'] = 'Changed actor identity label'
        changed = copy.deepcopy(self.example)
        changed['source']['kind'] = 'telemetry'
        for batch in (conflict, changed):
            with self.subTest(batch=batch['source']), self.assertRaises(ValueError):
                connect_observability(self.lab, raw(batch))
        self.assertEqual(self.lab.store.list(limit=200), before)
        self.assertEqual(len(self.lab.store.history(first['run_ref']['id'])), 1)

    def test_missing_endpoint_and_mismatched_tool_actor_remain_explicit_unknown_conflict(self):
        batch = copy.deepcopy(self.example)
        batch['events'][7]['recipient_ids'] = ['unknown-agent']
        batch['events'][9]['actor_id'] = 'different-agent'
        result = connect_observability(self.lab, raw(batch))
        counts = self.exact(result['run_ref'])['payload']['reference_checks']['counts']
        self.assertGreater(counts['unknown_in_captured_run'], 0)
        self.assertEqual(counts['actor_conflict'], 1)
        self.assertFalse(self.exact(result['run_ref'])['payload']['clock']['shared_causal_clock_verified'])

    def test_timestamp_reversal_is_measured_without_reordering_or_delivery_claim(self):
        batch = copy.deepcopy(self.example)
        batch['events'][7]['occurred_at'] = '2026-10-05T09:00:00Z'
        result = connect_observability(self.lab, raw(batch))
        payload = self.exact(result['run_ref'])['payload']
        self.assertEqual(payload['events'], batch['events'])
        self.assertEqual(payload['clock']['adjacent_timestamp_reversals'], 1)
        self.assertTrue(payload['clock']['capture_order_preserved'])

    def test_unknown_channel_stays_null_and_legacy_discovery_is_honestly_unavailable(self):
        batch = copy.deepcopy(self.example)
        for event in batch['events']:
            if event['kind'] == 'message.sent': event['data'].pop('channel_id')
        result = connect_observability(self.lab, raw(batch))
        messages = self.exact(result['dataset_ref'])['payload']['messages']
        self.assertTrue(all(message['room_id'] is None for message in messages))
        self.assertIsNone(result['discovery_ref'])
        self.assertEqual(result['discovery_status'], 'unavailable_channel_scope_not_declared')

    def test_task_only_capture_has_no_fabricated_chat_bridge(self):
        batch = {**self.example, 'events': [event for event in self.example['events'] if event['kind'] != 'message.sent']}
        result = connect_observability(self.lab, raw(batch))
        self.assertIsNone(result['dataset_ref'])
        self.assertIsNone(result['discovery_ref'])
        self.assertEqual(self.exact(result['brief_ref'])['payload']['source_refs'], {'run_ref': result['run_ref']})

    def test_malformed_shapes_types_unknown_fields_and_duplicate_json_fail_before_mutation(self):
        values = []
        for path, value in [(('source', 'kind'), 'empirical_truth'), (('source', 'harness'), 2),
                            (('events', 9, 'data', 'success'), 1), (('events', 0, 'occurred_at'), '2026-10-05T10:00:00'),
                            (('events', 0, 'actor_id'), False), (('events', 7, 'recipient_ids'), ['x', 'x']),
                            (('events', 0, 'data', 'extra'), 'unknown'), (('events', 0, 'kind'), 'agent.thought_read')]:
            batch = copy.deepcopy(self.example)
            target = batch
            for part in path[:-1]: target = target[part]
            target[path[-1]] = value
            values.append(raw(batch))
        duplicate = copy.deepcopy(self.example); duplicate['events'].append(duplicate['events'][0]); values.append(raw(duplicate))
        values.extend([b'{"schema_version":"a","schema_version":"b"}', b'{"value":NaN}', b'{"value":1e500}',
                       b'[' * 1000 + b']' * 1000, br'"\ud800"'])
        for value in values:
            with self.subTest(value=value[:120]), self.assertRaises((ValueError, KeyError)):
                connect_observability(self.lab, value)
        self.assertEqual(self.lab.store.list(), [])
        self.assertEqual(self.lab.store.usage()['calls'], 0)

    def test_2000_event_and_accumulated_byte_ceiling_never_silently_truncates(self):
        batch = copy.deepcopy(self.example)
        event = batch['events'][0]
        batch['events'] = [{**event, 'id': 'many-' + str(index)} for index in range(2001)]
        with self.assertRaises(ValueError): validate_batch(batch)
        batch = {**self.example, 'events': [copy.deepcopy(self.example['events'][7])]}
        batch['events'][0]['data']['content'] = 'x' * 16000
        batch['events'] = [{**batch['events'][0], 'id': 'long-' + str(index)} for index in range(50)]
        first = connect_observability(self.lab, raw(batch))
        delta = {**batch, 'events': [{**batch['events'][0], 'id': 'extra-' + str(index)} for index in range(30)]}
        with self.assertRaises(ValueError): connect_observability(self.lab, raw(delta))
        self.assertEqual(len(self.lab.store.history(first['run_ref']['id'])), 1)
        self.assertEqual(len(self.exact(first['run_ref'])['payload']['events']), 50)

    def test_atomic_brief_failure_retains_no_half_registered_run_or_bridge(self):
        with patch('swarm_lab.proactive_brief.build_brief', side_effect=ValueError('fixture blocked brief')):
            with self.assertRaises(ValueError): connect_observability(self.lab, raw(self.example))
        self.assertEqual(self.lab.store.list(), [])
        self.assertEqual(self.lab.store.jobs(), [])

    def test_concurrent_exact_retries_do_not_advance_run_or_repeat_screening(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            outputs = list(pool.map(lambda _: connect_observability(self.lab, raw(self.example)), range(4)))
        self.assertTrue(all(value['run_ref'] == outputs[0]['run_ref'] for value in outputs))
        self.assertEqual(len(self.lab.store.history(outputs[0]['run_ref']['id'])), 1)
        self.assertEqual(len(self.lab.store.list('discovery')), 1)
        settled = connect_observability(self.lab, raw(self.example))
        self.assertEqual(settled['discovery_status'], 'completed')
        self.assertIsNotNone(settled['discovery_ref'])

    def test_two_sources_with_same_run_label_do_not_merge(self):
        first = connect_observability(self.lab, raw(self.example))
        second_batch = copy.deepcopy(self.example); second_batch['source']['id'] = 'other-source'
        second = connect_observability(self.lab, raw(second_batch))
        self.assertNotEqual(first['run_ref']['id'], second['run_ref']['id'])

    def test_screening_failure_is_retained_without_retry_or_fabricated_discovery(self):
        with patch.object(Lab, 'observe', side_effect=RuntimeError('fixture screen failed')) as observe:
            first = connect_observability(self.lab, raw(self.example))
            second = connect_observability(self.lab, raw(self.example))
        self.assertEqual(observe.call_count, 1)
        self.assertEqual(first['discovery_status'], 'failed')
        self.assertEqual(second['discovery_status'], 'failed')
        self.assertIsNone(first['discovery_ref'])
        self.assertIsNotNone(first['brief_ref'])

    def test_exact_saved_chat_brief_stays_on_old_dataset_version_and_has_no_telemetry_run(self):
        connected = connect_observability(self.lab, raw(self.example))
        dataset = self.exact(connected['dataset_ref'])
        newer = self.lab.store.put('dataset', {**dataset['payload'], 'messages': []}, dataset['id'])
        result = brief_dataset(self.lab, raw({'dataset_ref': ref(dataset)}))
        self.assertIsNone(result['run_ref'])
        self.assertEqual(result['dataset_ref'], ref(dataset))
        self.assertNotEqual(result['dataset_ref'], ref(newer))
        self.assertEqual(self.exact(result['brief_ref'])['payload']['source_refs'], {'dataset_ref': ref(dataset)})
        self.assertEqual(self.exact(result['discovery_ref'])['payload']['dataset_ref'], ref(dataset))
        for reference in (ref(dataset) | {'version': True}, ref(dataset) | {'hash': '0' * 64}):
            with self.assertRaises(ValueError): brief_dataset(self.lab, raw({'dataset_ref': reference}))

    def test_credentials_redact_text_and_preserve_safe_identity_with_recorded_hash_distinction(self):
        batch = copy.deepcopy(self.example)
        batch['events'][7]['data']['content'] = 'Credential: hf_' + 'a' * 30
        result = connect_observability(self.lab, raw(batch))
        run = self.exact(result['run_ref'])['payload']
        self.assertTrue(run['provenance']['redaction_applied'])
        self.assertIn('[REDACTED_CREDENTIAL]', run['events'][7]['data']['content'])
        self.assertNotEqual(run['source_batch_sha256'], run['stored_batch_sha256'])
        bad = copy.deepcopy(self.example); bad['source']['id'] = 'hf_' + 'a' * 30
        with self.assertRaises(ValueError): connect_observability(self.lab, raw(bad))

    def test_follow_returns_current_exact_pins_and_never_mutates_old_analysis(self):
        first = connect_observability(self.lab, raw({**self.example, 'events': self.example['events'][:10]}))
        original = self.exact(first['brief_ref'])
        second = connect_observability(self.lab, raw({**self.example, 'events': self.example['events'][10:]}))
        before = self.lab.store.list(limit=200)
        followed = follow_observability(self.lab, first['run_ref']['id'])
        for key in ('run_ref', 'dataset_ref', 'brief_ref', 'discovery_ref'):
            self.assertEqual(followed[key], second[key])
        self.assertEqual(self.exact(first['brief_ref']), original)
        self.assertEqual(self.lab.store.list(limit=200), before)
        for query in ({'run_id': ['x']}, {'run_id': [first['run_ref']['id'], first['run_ref']['id']]},
                      {'run_id': [first['run_ref']['id']], 'extra': ['x']}, {'run_id': ['']}):
            with self.assertRaises(ValueError): parse_follow_query(query)

    def test_sdk_wraps_an_actual_tool_and_records_no_fake_agents_or_posts(self):
        from examples.observability_client import SocietyEvents
        client = SocietyEvents('test-instrument', 'Software test', 'actual-function-run')
        actual_calls = []
        def function(value): actual_calls.append(value); return {'result': value + 1}
        self.assertEqual(client.call_tool('actual-caller', 'actual_function', {'value': 4}, function), {'result': 5})
        self.assertEqual(actual_calls, [4])
        self.assertEqual([event['kind'] for event in client.events], ['tool.called', 'tool.returned'])
        self.assertEqual(client.events[0]['data']['call_id'], client.events[1]['data']['call_id'])
        self.assertTrue(client.events[1]['data']['success'])
        validate_batch({'schema_version': 'societylab.events.v1', 'source': client.source, 'run': client.run, 'events': client.events})
        with patch('examples.observability_client.post_batch', side_effect=ConnectionError('fixture local upload failure')):
            with self.assertRaises(ConnectionError): client.flush()
        self.assertEqual(len(client.events), 2)


class ObservabilityApiTests(unittest.TestCase):
    def test_actual_loopback_schema_connect_retry_and_exact_brief_with_csrf(self):
        with tempfile.TemporaryDirectory() as directory:
            lab = Lab(Settings(root=Path(directory), max_calls=0))
            servers = []
            with socket.socket() as handle:
                handle.bind(('127.0.0.1', 0)); port = handle.getsockname()[1]
            def capture(*args, **kwargs):
                value = LocalResearchServer(*args, **kwargs); servers.append(value); return value
            with patch('swarm_lab.server.LocalResearchServer', side_effect=capture):
                worker = threading.Thread(target=serve, args=(lab, port), daemon=True); worker.start()
                base = f'http://127.0.0.1:{port}'
                try:
                    deadline = time.monotonic() + 5
                    while True:
                        try:
                            with urllib.request.urlopen(base + '/api/state', timeout=5) as response: state = json.load(response)
                            break
                        except urllib.error.URLError:
                            if time.monotonic() > deadline: raise
                            time.sleep(.02)
                    with urllib.request.urlopen(base + '/api/observability/schema', timeout=5) as response: manifest = json.load(response)
                    self.assertEqual(manifest['schema_version'], 'societylab.events.v1')
                    def post(path, payload, token=True):
                        request = urllib.request.Request(base + path, data=raw(payload),
                            headers={'Content-Type': 'application/json', **({'X-Lab-Token': state['csrf']} if token else {})})
                        with urllib.request.urlopen(request, timeout=10) as response: return response.status, json.load(response)
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        post('/api/observability/connect', manifest['example'], token=False)
                    self.assertEqual(error.exception.code, 403)
                    status, first = post('/api/observability/connect', manifest['example'])
                    self.assertEqual(status, 201)
                    self.assertEqual(first['discovery_status'], 'completed')
                    _, repeated = post('/api/observability/connect', manifest['example'])
                    self.assertTrue(repeated['idempotent'])
                    self.assertEqual(repeated['run_ref'], first['run_ref'])
                    _, chat_brief = post('/api/observability/brief', {'dataset_ref': first['dataset_ref']})
                    self.assertIsNone(chat_brief['run_ref'])
                    self.assertEqual(chat_brief['dataset_ref'], first['dataset_ref'])
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        post('/api/observability/brief', {'dataset_ref': first['dataset_ref'], 'extra': True})
                    self.assertEqual(error.exception.code, 400)
                    with urllib.request.urlopen(base + '/api/state', timeout=5) as response: after = json.load(response)
                    self.assertEqual(after['usage']['calls'], 0)
                    self.assertEqual(after['jobs'], [])
                finally:
                    for server in servers: server.shutdown()
                    worker.join(5)
                    self.assertFalse(worker.is_alive())


if __name__ == '__main__': unittest.main()
