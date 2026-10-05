"""Actual loopback exact-source reads; authored fixture, no provider work."""
import copy
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from unittest.mock import patch

from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab
from swarm_lab.server import LocalResearchServer, parse_event_graph_query, serve


class EventEvidenceGraphApiTests(unittest.TestCase):
    def test_parser_refuses_duplicate_unknown_blank_noncanonical_or_oversized_parameters(self):
        valid = {'object_id': ['observability_run-unit'], 'version': ['1'],
                 'hash': ['a' * 64], 'event_id': ['post'], 'hops': ['1']}
        self.assertEqual(parse_event_graph_query(valid)['version'], 1)
        variants = []
        for key in valid:
            for values in ([], [''], ['x', 'y']):
                item = copy.deepcopy(valid); item[key] = values; variants.append(item)
        for key, values in [('version', ['01']), ('version', ['1.0']), ('version', ['9007199254740992']),
                            ('version', [True]), ('hops', ['3']), ('hops', ['true']),
                            ('object_id', [' source']), ('event_id', ['x' * 129]), ('hash', ['A' * 64])]:
            item = copy.deepcopy(valid); item[key] = values; variants.append(item)
        variants.extend([{**valid, 'extra': ['x']}, {k: v for k, v in valid.items() if k != 'hash'}])
        for query in variants:
            with self.subTest(query_keys=list(query)), self.assertRaises(ValueError):
                parse_event_graph_query(query)

    def test_loopback_old_exact_version_and_source_graph_reads_have_no_mutations_or_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            lab = Lab(Settings(root=Path(directory), max_calls=0))
            payload = {'schema_version': 'societylab.events.v1',
                'source': {'id': 'unit-source', 'name': 'Authored API fixture', 'kind': 'authored_example'},
                'run': {'id': 'unit-run'}, 'events': [
                    {'id': 'register', 'occurred_at': '2025-04-22T18:00:00Z', 'kind': 'agent.registered', 'actor_id': 'a', 'data': {'name': 'A'}},
                    {'id': 'post', 'occurred_at': '2025-04-22T18:00:01Z', 'kind': 'message.sent', 'actor_id': 'a', 'recipient_ids': [], 'data': {'content': 'Older original post'}}]}
            old = lab.store.put('observability_run', payload, 'observability_run-unit')
            changed = copy.deepcopy(payload); changed['events'][1]['data']['content'] = 'Newer source'
            new = lab.store.put('observability_run', changed, old['id'])
            servers = []
            with socket.socket() as handle:
                handle.bind(('127.0.0.1', 0)); port = handle.getsockname()[1]
            def capture(*args, **kwargs):
                server = LocalResearchServer(*args, **kwargs); servers.append(server); return server
            with patch('swarm_lab.server.LocalResearchServer', side_effect=capture):
                worker = threading.Thread(target=serve, args=(lab, port), daemon=True); worker.start()
                base = f'http://127.0.0.1:{port}'
                try:
                    deadline = time.monotonic() + 5
                    while True:
                        try:
                            with urllib.request.urlopen(base + '/api/state', timeout=5) as response: json.load(response)
                            break
                        except urllib.error.URLError:
                            if time.monotonic() > deadline: raise
                            time.sleep(.02)
                    def saved_state():
                        with lab.store.connect() as connection:
                            traces = connection.execute('SELECT COUNT(*) FROM traces').fetchone()[0]
                        return lab.store.list(limit=1000), lab.store.jobs(), lab.store.usage(), traces
                    before = saved_state()
                    query = {'object_id': old['id'], 'version': '1', 'hash': old['hash'], 'event_id': 'post', 'hops': '1'}
                    def read(query_string):
                        with urllib.request.urlopen(base + '/api/observability/graph?' + query_string, timeout=5) as response:
                            self.assertEqual(response.headers['Cache-Control'], 'no-store')
                            return json.load(response)
                    original = read(urllib.parse.urlencode(query))
                    self.assertEqual(original['source_ref'], {k: old[k] for k in ('id', 'version', 'hash')})
                    self.assertEqual({n['id'] for n in original['nodes']}, {'register', 'post'})
                    self.assertEqual(original['edges'][0]['relation'], 'actor')
                    self.assertNotIn('Older original post', json.dumps(original))
                    latest_query = {**query, 'version': '2', 'hash': new['hash']}
                    current = read(urllib.parse.urlencode(latest_query))
                    self.assertEqual(current['source_ref']['version'], 2)
                    self.assertNotEqual(current['batch_sha256'], original['batch_sha256'])
                    bad_queries = [urllib.parse.urlencode({**query, 'hash': new['hash']}),
                        urllib.parse.urlencode({**query, 'event_id': 'missing'}),
                        urllib.parse.urlencode(query) + '&hops=1', urllib.parse.urlencode(query) + '&extra=x',
                        urllib.parse.urlencode({**query, 'version': '01'}),
                        urllib.parse.urlencode({**query, 'event_id': ''}),
                        urllib.parse.urlencode({**query, 'hops': '3'})]
                    for bad in bad_queries:
                        with self.subTest(query_length=len(bad)), self.assertRaises(urllib.error.HTTPError) as error:
                            read(bad)
                        self.assertEqual(error.exception.code, 400)
                    after = saved_state()
                    self.assertEqual(after, before)
                    self.assertEqual(after[2]['calls'], 0)
                finally:
                    for server in servers: server.shutdown()
                    worker.join(5)
                    self.assertFalse(worker.is_alive())


if __name__ == '__main__': unittest.main()
