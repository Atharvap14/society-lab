"""Independent presentation boundaries; authored temporary sources only.

Fixture setup derives small operators before inspection. The workspace call is
then guarded against derivation, source/index reads, provider calls and writes.
Resealed copies challenge recorded-field consistency, not fresh science.
"""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from swarm_lab import episode_workspace as module
from swarm_lab import research_observations as recorded
from tests import test_research_observations as fixtures


class EpisodeWorkspaceIndependentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_wait_marker_report import prepared_fixture
        from swarm_lab import wait_marker_workflow as wait, graph_hodge_workflow as hodge
        f = prepared_fixture(); cls.fixture = f
        p = copy.deepcopy(f.discovery['payload'])
        p['candidates'] = [dict(copy.deepcopy(lead),
            alternative_explanations=copy.deepcopy(lead['alternatives']),
            right_censored=True, requires=['Source review remains required.'])
            for lead in p['graph_search']['leads']]
        f.discovery = f.lab.store.put('discovery', p, f.discovery['id'])
        f.selected = f.lab.audit_selected_leads(f.discovery['id'], version=f.discovery['version'],
            short_name_allowlist=['o3'], include_unicode_shadow=True)
        cls.actor = f.actor_audit()
        cls.actor_proof = f.lab.replay_actor_events(cls.actor['id'], version=cls.actor['version'])
        cls.wait = wait.audit_wait_markers(f.lab, cls.actor['id'])
        cls.wait_proof = wait.replay_wait_markers(f.lab, cls.wait['id'])
        cls.temporal = f.lab.audit_temporal_paths(f.selected['id'], version=f.selected['version'])
        cls.hodge = hodge.audit_edge_flow(f.lab, cls.temporal['id'])
        cls.hodge_proof = hodge.replay_edge_flow(f.lab, cls.hodge['id'])
        cls.comparison = cls.temporal['payload']['original_comparisons'][0]
        cls.args = dict(selected_audit_id=f.selected['id'], selected_audit_version=f.selected['version'],
            temporal_audit_id=cls.temporal['id'], temporal_audit_version=cls.temporal['version'],
            lead_id=cls.comparison['id'])
        with f.lab.store.connect() as connection:
            cls.rows = [f.lab.store._decode(row) for row in connection.execute('SELECT * FROM objects')]

    @classmethod
    def tearDownClass(cls):
        cls.fixture.doCleanups()

    def setUp(self):
        self.store = fixtures.MemoryRecords(self.rows)

    @staticmethod
    def ref(obj):
        return {key: obj[key] for key in ('id', 'version', 'hash')}

    def collect(self, args=None):
        return module.episode_workspace_packet(self.store, **(args or self.args))

    def withheld(self, packet):
        self.assertFalse(packet['available'], {'reason':packet['reason']})
        for key in ('source_refs', 'comparison', 'windows', 'lead', 'measurement',
                    'temporal', 'evidence', 'behavior', 'recorded_observations'):
            self.assertIsNone(packet[key], key)
        self.assertFalse(packet['fresh_source_attestation'])
        self.assertFalse(packet['operator_rerun'])
        self.assertEqual(type(packet['model_calls']), int)
        self.assertEqual(packet['model_calls'], 0)
        self.assertEqual(packet['database_writes'], 0)

    def behavior(self, **changes):
        payload = {'candidate_id': self.comparison['id'],
            'source_refs': {'dataset': self.ref(self.fixture.dataset),
                            'discovery': self.ref(self.fixture.discovery)},
            'name': 'Fixture hypothesis', 'status': 'candidate',
            'summary': 'An untested explanation, not a finding.',
            'operational_definition': 'Check source-linked predictions.',
            'alternative_explanations': ['Shared task and unobserved channel.'],
            'falsifiable_predictions': ['A proposed relay has a legal alternative route.'],
            'experiment_fit': 'requires_new_environment', 'fit_reason': 'Role interpretation is unknown.',
            'skeptic': {'summary': 'This is a bounded recorded critique.', 'evidence_ids': [],
                'unsupported_claims': ['No observed exposure or causal mechanism.'],
                'alternative_explanations': [], 'searches_performed': [], 'search_results': [],
                'counterexample_searches': [], 'recommended_status': 'needs_more_evidence',
                'limitations': ['Fixture, not empirical review.']}}
        payload.update(copy.deepcopy(changes))
        return self.store.append('behavior', payload)

    def bind_changed_sources(self, *, dataset_change=None, discovery_change=None,
                             selected_change=None, temporal_change=None):
        """New exact versions of base parents; original fixture stays immutable.

        Descendant observation/proof parents stay old and thus unavailable. This
        deliberately tests only the presentation's base recorded-field gate.
        """
        f = self.fixture
        dataset = copy.deepcopy(f.dataset)
        if dataset_change:
            p = copy.deepcopy(dataset['payload']); dataset_change(p)
            dataset = self.store.append('dataset', p, dataset['id'])
        discovery = copy.deepcopy(f.discovery)
        if dataset_change or discovery_change:
            p = copy.deepcopy(discovery['payload']); p['dataset_id'] = dataset['id']; p['dataset_ref'] = self.ref(dataset)
            if discovery_change: discovery_change(p)
            discovery = self.store.append('discovery', p, discovery['id'])
        p = copy.deepcopy(f.selected['payload'])
        p['source_refs'].update(dataset=self.ref(dataset), discovery=self.ref(discovery))
        if selected_change: selected_change(p)
        selected = self.store.append('selected_lead_audit', p, f.selected['id'])
        p = copy.deepcopy(self.temporal['payload'])
        p['source_refs'].update(dataset=self.ref(dataset), discovery=self.ref(discovery), selected_audit=self.ref(selected))
        p['selected_audit_ref'] = self.ref(selected)
        if temporal_change: temporal_change(p)
        temporal = self.store.append('temporal_path_audit', p, self.temporal['id'])
        return {**self.args, 'selected_audit_version': selected['version'],
                'temporal_audit_version': temporal['version']}

    def test_exact_historical_parents_no_writes_or_operator_source_work(self):
        for obj in (self.fixture.dataset, self.fixture.discovery, self.fixture.selected, self.temporal):
            self.store.append(obj['kind'], {'unrelated_new_version': True}, obj['id'])
        before = copy.deepcopy(self.store.rows)
        opened = []; read = Path.read_bytes
        def restricted_read(path):
            self.assertEqual(path.parent.resolve(), Path(recorded.__file__).resolve().parent)
            self.assertIn(path.name, recorded._FILES); opened.append(path.name)
            return read(path)
        with patch.object(Path, 'read_bytes', restricted_read), \
             patch('swarm_lab.actor_event_workflow.derive_selected_actor_events', side_effect=AssertionError('No index query')), \
             patch('swarm_lab.wait_marker_workflow.derive_wait_marker_alignment', side_effect=AssertionError('No alignment rerun')), \
             patch('swarm_lab.graph_hodge_workflow.derive_edge_flow', side_effect=AssertionError('No Hodge rerun')), \
             patch('swarm_lab.harness.ResponsesHarness.request', side_effect=AssertionError('No provider')):
            packet = self.collect()
        self.assertTrue(packet['available'], packet)
        self.assertEqual(self.store.rows, before)
        self.assertEqual(packet['source_refs']['discovery'], self.ref(self.fixture.discovery))
        self.assertEqual(packet['comparison'], self.comparison)
        self.assertEqual(set(packet['windows']), {self.comparison['window_id'], self.comparison['comparison_window_id']})
        self.assertEqual(set(opened), set(recorded._FILES))
        self.assertTrue(all(entry['available'] for entry in packet['recorded_observations']['observations'].values()))
        for ref in packet['source_refs'].values():
            self.assertIn((ref['id'], ref['version']), self.store.get_calls)
        encoded = module._bytes(packet)
        self.assertLessEqual(len(encoded), module.MAX_OUTPUT_BYTES)
        self.assertNotIn(b'PRIVATE_PROVIDER_SENTINEL', encoded)
        self.assertFalse(packet['fresh_source_attestation']); self.assertFalse(packet['operator_rerun'])

    def test_query_and_call_versions_are_strict_not_latest_aliases(self):
        query = {key: [str(value)] for key, value in self.args.items()}
        self.assertEqual(module.parse_episode_query(query), self.args)
        for value in ('0', '01', '1.0', 'true', '-1', ' 1', '1000000001'):
            with self.subTest(query_version=value):
                bad = copy.deepcopy(query); bad['selected_audit_version'] = [value]
                with self.assertRaises(ValueError): module.parse_episode_query(bad)
        for mutate in (lambda q:q.update(lead_id=['a', 'b']), lambda q:q.update(unexpected=['x']),
                       lambda q:q.update(behavior_id=['behavior-orphan']), lambda q:q.update(lead_id=['<script>'])):
            bad = copy.deepcopy(query); mutate(bad)
            with self.assertRaises(ValueError): module.parse_episode_query(bad)
        for key in ('selected_audit_version', 'temporal_audit_version'):
            for value in (True, False, 1.0, None, 0):
                with self.subTest(call_version=(key, value)):
                    self.withheld(self.collect({**self.args, key:value}))

    def test_wrong_candidate_or_window_is_not_a_new_comparator(self):
        self.withheld(self.collect({**self.args, 'lead_id':'graph-lead-absent'}))
        def change(p):
            candidate = next(c for c in p['candidates'] if c['id'] == self.comparison['id'])
            candidate['comparison_window_id'] = candidate['window_id']
        self.withheld(self.collect(self.bind_changed_sources(discovery_change=change)))

    def test_same_candidate_behavior_requires_exact_original_source_versions(self):
        behavior = self.behavior()
        args = {**self.args, 'behavior_id':behavior['id'], 'behavior_version':behavior['version']}
        packet = self.collect(args)
        self.assertTrue(packet['behavior']['available'])
        self.assertFalse(packet['behavior']['source_link_approval'])
        self.store.append('behavior', {'later': True}, behavior['id'])
        self.assertTrue(self.collect(args)['behavior']['available'])
        for changes in ({'candidate_id':'graph-lead-other'},
                        {'source_refs':{'dataset':self.ref(self.fixture.dataset),
                            'discovery':{**self.ref(self.fixture.discovery), 'hash':'f'*64}}}):
            wrong = self.behavior(**changes)
            packet = self.collect({**self.args, 'behavior_id':wrong['id'], 'behavior_version':wrong['version']})
            self.assertFalse(packet['behavior']['available'])
            self.assertIsNone(packet['behavior']['payload'])
        for version in (True, 1.0, None):
            self.withheld(self.collect({**args, 'behavior_version':version}))

    def test_authentic_latest_unrelated_audits_and_proofs_are_not_borrowed(self):
        originals = (self.actor, self.wait, self.hodge)
        for obj in originals:
            p = copy.deepcopy(obj['payload'])
            if obj['kind'] == 'graph_hodge_audit': p['temporal_audit_ref']['id'] = 'temporal-unrelated'
            elif obj['kind'] == 'actor_event_audit': p['selected_audit_ref']['id'] = 'selected-unrelated'
            else:
                p['source_refs']['selected_audit']['id'] = 'selected-unrelated'
                p['actor_audit_ref']['id'] = 'actor-unrelated'
            self.store.append(obj['kind'], p)
        for obj in (self.actor_proof, self.wait_proof, self.hodge_proof):
            p = copy.deepcopy(obj['payload'])
            p['alignment_ref' if obj == self.wait_proof else 'audit_ref']['id'] = 'audit-unrelated'
            self.store.append('verification', p)
        packet = self.collect(); self.assertTrue(packet['available'])
        entries = packet['recorded_observations']['observations']
        for key, obj in zip(('actor_events', 'wait_markers', 'edge_algebra'), originals):
            self.assertTrue(entries[key]['available'], entries[key])
            self.assertEqual(entries[key]['ref'], self.ref(obj))

    def test_missing_or_latest_failed_channel_stays_unknown_not_zero(self):
        kinds = {'actor_event_audit', 'wait_marker_alignment_audit', 'graph_hodge_audit', 'verification'}
        self.store = fixtures.MemoryRecords([r for r in self.rows if r['kind'] not in kinds])
        packet = self.collect(); self.assertTrue(packet['available'])
        for entry in packet['recorded_observations']['observations'].values():
            self.assertFalse(entry['available']); self.assertIsNone(entry['summary'])
        self.store = fixtures.MemoryRecords(self.rows)
        p = copy.deepcopy(self.hodge_proof['payload']); p['passed'] = False
        bad = self.store.append('verification', p)
        entry = self.collect()['recorded_observations']['observations']['edge_algebra']
        self.assertFalse(entry['available']); self.assertIsNone(entry['summary'])
        self.assertEqual(entry['stored_proof_ref'], self.ref(bad))

    def test_candidate_registered_numeric_and_evidence_core_cannot_disagree(self):
        for change in (lambda c:c.update(value=999.0), lambda c:c.update(difference=-1.0),
                       lambda c:c.update(evidence_ids=[]), lambda c:c.update(alternatives=['invented rival'])):
            with self.subTest(change=change):
                self.store = fixtures.MemoryRecords(self.rows)
                def mutate(p): change(next(c for c in p['candidates'] if c['id'] == self.comparison['id']))
                self.withheld(self.collect(self.bind_changed_sources(discovery_change=mutate)))

    def test_recorded_metric_and_temporal_types_ranges_cannot_be_presented(self):
        def metric(p):
            return next(row for row in p['per_lead'] if row['lead_id'] == self.comparison['id'])['native']['baseline_exact']
        for change in (lambda r:r.update(value=True), lambda r:r.update(supported=1),
                       lambda r:r.update(value=2.0), lambda r:r.update(available=False, value=0.0,
                           comparison_value=0.0, difference=0.0)):
            with self.subTest(metric=change):
                self.store = fixtures.MemoryRecords(self.rows)
                self.withheld(self.collect(self.bind_changed_sources(selected_change=lambda p:change(metric(p)))))
        wid = self.comparison['window_id']
        for change in (lambda r:r.update(available=1),
                       lambda r:r['static'].update(reachable_pair_count=True),
                       lambda r:r['static'].update(reachable_pair_count=999999),
                       lambda r:r['static']['node_removal'].update(maximum_loss_fraction=2.0),
                       lambda r:r.update(static_only_pair_count=-1)):
            with self.subTest(temporal=change):
                self.store = fixtures.MemoryRecords(self.rows)
                mutate = lambda p:change(p['windows'][wid]['variants']['baseline_exact'])
                self.withheld(self.collect(self.bind_changed_sources(temporal_change=mutate)))

    def test_evidence_provenance_extras_are_not_forwarded(self):
        sentinel = 'UNRELATED_PROVIDER_PRIVATE_SENTINEL'
        def inject(p):
            for message in p['messages']:
                message['source']['provider_payload'] = {'text':sentinel}
        args = self.bind_changed_sources(dataset_change=inject)
        packet = self.collect(args)
        self.assertTrue(packet['available'], packet)
        self.assertFalse(sentinel in json.dumps(packet), 'Evidence source forwarded an unrelated retained field')
        for group in ('focal', 'comparator'):
            self.assertTrue(all(set(row['source']) <= {'file', 'line', 'table'} for row in packet['evidence'][group]))
    def test_skeptic_extras_are_not_forwarded(self):
        sentinel = 'UNRELATED_PROVIDER_PRIVATE_SENTINEL'
        behavior = self.behavior(); p = copy.deepcopy(behavior['payload'])
        p['skeptic']['provider_payload'] = {'text':sentinel}
        behavior = self.store.append('behavior', p, behavior['id'])
        packet = self.collect({**self.args, 'behavior_id':behavior['id'], 'behavior_version':behavior['version']})
        self.assertTrue(packet['available']); self.assertTrue(packet['behavior']['available'])
        self.assertFalse(sentinel in json.dumps(packet), 'Critique forwarded an unrelated retained field')

    def test_public_critique_fields_cannot_be_nested_payload_containers(self):
        for changes in ({'summary':{'provider_payload':'not-public-critique'}},
                        {'unsupported_claims':[{'provider_payload':'not-public-critique'}]}):
            with self.subTest(changes=changes):
                self.store = fixtures.MemoryRecords(self.rows)
                behavior = self.behavior(); p = copy.deepcopy(behavior['payload'])
                p['skeptic'].update(changes)
                behavior = self.store.append('behavior', p, behavior['id'])
                self.withheld(self.collect({**self.args, 'behavior_id':behavior['id'],
                    'behavior_version':behavior['version']}))

    def test_direction_must_agree_with_recorded_delta_and_declared_zero_tolerance(self):
        for direction in ('negative', 'invented', True):
            with self.subTest(direction=direction):
                self.store = fixtures.MemoryRecords(self.rows)
                def mutate(p):
                    row = next(r for r in p['per_lead'] if r['lead_id'] == self.comparison['id'])
                    row['native']['baseline_exact']['direction'] = direction
                self.withheld(self.collect(self.bind_changed_sources(selected_change=mutate)))

    def test_valid_unavailable_shapes_retain_none_and_rates_have_no_invented_upper_bound(self):
        def undefined_metric(p):
            row = next(r for r in p['per_lead'] if r['lead_id'] == self.comparison['id'])
            row['native']['baseline_exact'] = {'available':False, 'reason':'variant_not_requested',
                'value':None, 'comparison_value':None, 'difference':None,
                'direction':'undefined', 'supported':False}
        def undefined_temporal(p):
            p['windows'][self.comparison['window_id']]['variants']['baseline_exact'] = {
                'available':False, 'reason':'variant_not_requested'}
        packet = self.collect(self.bind_changed_sources(selected_change=undefined_metric,
            temporal_change=undefined_temporal))
        self.assertTrue(packet['available'], packet['reason'])
        metric = packet['measurement']['native']['baseline_exact']
        self.assertFalse(metric['available'])
        self.assertTrue(all(metric[name] is None for name in ('value', 'comparison_value', 'difference',
            'supported_under_original_minima')))
        temporal = packet['temporal'][self.comparison['window_id']]['variants']['baseline_exact']
        self.assertFalse(temporal['available'])
        self.assertTrue(all(temporal[name] is None for name in ('static', 'strict_temporal', 'static_only_pair_count')))
        saved = {'available':True, 'value':2.5, 'comparison_value':1.0, 'difference':1.5,
                 'direction':'positive', 'supported':True, 'supported_under_original_minima':True}
        self.assertEqual(module._project_metrics(saved, 'shared_reference_rate')['value'], 2.5)
        saved.update(value=1.0, comparison_value=1.0-5e-13, difference=5e-13, direction='zero')
        self.assertEqual(module._project_metrics(saved, 'directed_reciprocity')['direction'], 'zero')

    def test_content_excerpt_hash_bound_and_all_original_ids_scope_checked(self):
        message = copy.deepcopy(self.fixture.dataset['payload']['messages'][0])
        message['content'] = 'α' * 1200 + 'NOT_IN_EXCERPT_SENTINEL'
        scope = next(w for w in self.temporal['payload']['windows'].values()
                     if w['scope']['start'] <= message['timestamp'] < w['scope']['end_exclusive'])['scope']
        shown, limits = module._evidence({message['id']:message}, [message['id']], scope)
        self.assertEqual(len(shown[0]['content']), 1000)
        self.assertTrue(shown[0]['content_truncated'])
        self.assertEqual(shown[0]['full_content_sha256'], hashlib.sha256(message['content'].encode('utf-8')).hexdigest())
        self.assertNotIn('NOT_IN_EXCERPT_SENTINEL', json.dumps(shown))
        messages = {}; identities = []
        for i in range(9):
            row = {**message, 'id':f'evidence-{i}'}
            if i == 8: row['room_id'] = 'wrong-room'
            identities.append(row['id']); messages[row['id']] = row
        with self.assertRaisesRegex(ValueError, 'scope_mismatch'):
            module._evidence(messages, identities, scope)
        shown, limits = module._evidence({}, ['absent'], scope)
        self.assertEqual(shown, []); self.assertEqual(limits['missing_ids'], ['absent'])
        self.assertEqual(limits['shown'], 0)

    def test_body_identity_depth_and_output_bounds_withhold_all_fields(self):
        ref = self.ref(self.fixture.discovery)
        self.store.rows[ref['id'], ref['version']]['payload']['unsealed_change'] = True
        self.withheld(self.collect())
        self.store = fixtures.MemoryRecords(self.rows)
        nested = 'deep'
        for _ in range(100): nested = [nested]
        self.withheld(self.collect(self.bind_changed_sources(discovery_change=lambda p:p.update(extra=nested))))
        self.store = fixtures.MemoryRecords(self.rows)
        behavior = self.behavior(summary='x' * module.MAX_OUTPUT_BYTES)
        packet = self.collect({**self.args, 'behavior_id':behavior['id'], 'behavior_version':behavior['version']})
        self.withheld(packet); self.assertLessEqual(len(module._bytes(packet)), module.MAX_OUTPUT_BYTES)


if __name__ == '__main__':
    unittest.main()
