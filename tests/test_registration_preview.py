"""Real constructors and temporary registry fixtures for a read-only preview.

Production imports only. No provider, subject run, production registry,
archive or raw source read is used. Supplied reviews are declarations, not fit
ground truth. Exact registration itself is tested only in isolated temp Stores.
"""
import copy
from contextlib import ExitStack
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode

from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab
from swarm_lab import experiment_authoring as AUTH
from swarm_lab import registration_preview as PREVIEW
from tests.test_environment_authoring import proposal, review


def ref(obj):
    return {key: obj[key] for key in ('id', 'version', 'hash')}


class RegistrationPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lab = Lab(Settings(root=self.root, max_calls=0, model='fixture-subject-model'))

    def blueprint(self, kind='complementary_information', changes=None, fit=True):
        p = proposal(kind)
        if changes: p['parameters'].update(changes)
        return self.lab.construct_environment(proposal=p, fit_review=review(p) if fit else None)

    def state(self):
        with self.lab.store.connect() as connection:
            rows = {table: tuple(tuple(row) for row in connection.execute('SELECT * FROM ' + table + ' ORDER BY 1,2'))
                    for table in ('objects', 'jobs', 'calls', 'traces')}
        files = sorted(str(path.relative_to(self.root)) for path in self.root.rglob('*')
                       if 'runs' in path.parts or 'execution-code' in path.parts)
        return rows, files

    def inert(self, function):
        with ExitStack() as stack:
            for name in ('put', 'compare_and_put', 'trace', 'reserve_call', 'finish_call', 'job', 'start_job'):
                stack.enter_context(patch.object(self.lab.store, name,
                    side_effect=AssertionError('Preview attempted a Store mutation: ' + name)))
            stack.enter_context(patch.object(self.lab, 'harness', side_effect=AssertionError('Preview called a harness')))
            return function()

    def test_four_real_factory_constructors_preview_the_exact_world_and_matching_registration(self):
        expected = {'shared_artifact_coordination': 'protocol', 'provenance_diffusion': 'network_protocol',
                    'complementary_information': 'complementary_protocol', 'exclusive_resource_tasks': 'resource_protocol'}
        for kind, result_kind in expected.items():
            with self.subTest(kind=kind):
                obj = self.blueprint(kind); before = self.state()
                packet = self.inert(lambda: PREVIEW.preview_blueprint_registration(self.lab, ref(obj)))
                self.assertEqual(self.state(), before)
                self.assertEqual(packet['status'], 'compatible'); self.assertIsNone(packet['reason'])
                self.assertTrue(all(value is True for value in packet['checks'].values()))
                self.assertEqual(packet['design']['object_kind'], result_kind)
                self.assertEqual(packet['design']['world_spec_hash'], obj['payload']['spec_hash'])
                self.assertEqual(packet['model_calls'], 0); self.assertFalse(packet['registered'])
                self.assertEqual(packet['database_writes'], 0); self.assertFalse(packet['raw_source_reread'])
                result = AUTH.register_blueprint(self.lab, obj['id'], blueprint_version=obj['version'], blueprint_hash=obj['hash'])
                p = result['payload']['protocol']
                actual = p.get('environment') or next(iter(p['environments'].values()))
                self.assertEqual(actual, obj['payload']['spec'])
                self.assertEqual(result['kind'], packet['design']['object_kind'])
                self.assertEqual(p['research_question'], packet['design']['research_question'])
                self.assertEqual(p['subject_backend'], packet['design']['subject_backend'])
                self.assertEqual(result['payload']['environment_blueprint_ref'], {**ref(obj), 'kind': 'environment_blueprint'})
                self.assertEqual(self.lab.store.usage()['calls'], 0)

    def test_live_preview_at_zero_cap_never_calls_harness_or_spends_or_saves(self):
        obj = self.blueprint('exclusive_resource_tasks'); before = self.state()
        packet = self.inert(lambda: PREVIEW.preview_blueprint_registration(self.lab, ref(obj), live=True))
        self.assertEqual(packet['status'], 'compatible'); self.assertEqual(self.state(), before)
        self.assertEqual(packet['registration_plan']['live'], True)
        self.assertEqual(packet['design']['subject_backend']['harness'], 'responses')
        self.assertEqual(packet['design']['subject_backend']['model'], 'fixture-subject-model')
        self.assertEqual(packet['design']['maximum_subject_calls'], 96)
        self.assertEqual(packet['design']['maximum_hosted_subject_calls'], 96)
        self.assertEqual(packet['model_calls'], 0)
        self.assertTrue(any('remaining budget' in value for value in packet['limits']))
        self.assertTrue(any('semantic citation truth' in value for value in packet['limits']))

    def test_custom_graph_construction_approval_does_not_imply_registered_design_compatibility(self):
        for kind in ('provenance_diffusion', 'complementary_information'):
            with self.subTest(kind=kind):
                obj = self.blueprint(kind, {'topology': 'custom', 'custom_edges': [['agent-0', 'agent-1']]})
                self.assertEqual(obj['payload']['experiment_eligibility'], 'approved_analogue')
                before = self.state(); packet = self.inert(lambda: PREVIEW.preview_blueprint_registration(self.lab, ref(obj)))
                self.assertEqual(self.state(), before); self.assertIsNone(packet['design'])
                self.assertEqual(packet['reason']['code'], 'custom_topology_not_registered')
                self.assertTrue(packet['checks']['current_source_authorization'])
                self.assertFalse(packet['checks']['design_compatible']); self.assertIsNone(packet['checks']['exact_world_preserved'])
                with self.assertRaisesRegex(ValueError, 'no graph substitution'):
                    AUTH.register_blueprint(self.lab, obj['id'], blueprint_version=obj['version'], blueprint_hash=obj['hash'])
                self.assertEqual(self.state(), before)

    def test_nondefault_complementary_cap_is_not_substituted_but_resource_cap_is_preserved(self):
        obj = self.blueprint(changes={'max_messages_per_agent': 0}); before = self.state()
        packet = PREVIEW.preview_blueprint_registration(self.lab, ref(obj))
        self.assertEqual(packet['reason']['code'], 'authored_world_not_preserved')
        self.assertFalse(packet['checks']['exact_world_preserved']); self.assertEqual(self.state(), before)
        self.assertEqual(obj['payload']['spec']['max_messages_per_agent'], 0)
        resource = self.blueprint('exclusive_resource_tasks', {'max_messages_per_agent': 0})
        packet = PREVIEW.preview_blueprint_registration(self.lab, ref(resource))
        self.assertEqual(packet['status'], 'compatible')
        result = AUTH.register_blueprint(self.lab, resource['id'])
        self.assertEqual(result['payload']['protocol']['environment']['max_messages_per_agent'], 0)

    def test_unapproved_review_stops_before_source_or_design_checks(self):
        obj = self.blueprint(fit=False); before = self.state()
        with patch.object(AUTH, 'compile_blueprint', side_effect=AssertionError('Unapproved world was recompiled')):
            packet = self.inert(lambda: PREVIEW.preview_blueprint_registration(self.lab, ref(obj)))
        self.assertEqual(self.state(), before); self.assertEqual(packet['reason']['stage'], 'approval')
        self.assertTrue(packet['checks']['construction_compiled']); self.assertFalse(packet['checks']['fit_approved_analogue'])
        for key in ('current_source_authorization', 'design_compatible', 'exact_world_preserved'):
            self.assertIsNone(packet['checks'][key])

    def test_changed_code_pin_blocks_current_source_gate_with_no_design_or_protocol(self):
        obj = self.blueprint(); changed = copy.deepcopy(obj['payload'])
        changed['environment_code_hashes']['environment_authoring.py'] = '0' * 64
        obj = self.lab.store.put('environment_blueprint', changed, obj['id']); before = self.state()
        packet = self.inert(lambda: PREVIEW.preview_blueprint_registration(self.lab, ref(obj)))
        self.assertEqual(self.state(), before); self.assertEqual(packet['reason']['stage'], 'source')
        self.assertFalse(packet['checks']['current_source_authorization'])
        self.assertIsNone(packet['checks']['design_compatible']); self.assertIsNone(packet['design'])

    def test_exact_reference_and_plan_reject_bool_float_extra_hash_and_partial_pairs_without_writes(self):
        obj = self.blueprint(); original = ref(obj); before = self.state()
        bad_refs = [{**original, 'version': value} for value in (True, 1.0, 0, -1, '1')]
        bad_refs += [{**original, 'hash': 'f' * 64}, {**original, 'hash': obj['hash'].upper()},
                     {**original, 'latest': True}, {'id': obj['id'], 'version': 1}, {**original, 'id': '../object'}]
        for value in bad_refs:
            with self.assertRaises((ValueError, KeyError)):
                PREVIEW.preview_blueprint_registration(self.lab, value)
            self.assertEqual(self.state(), before)
        bad_plans = [{'live': value} for value in ('false', 0, 1, None)]
        bad_plans += [{'trials_per_cell': value} for value in (True, 2.0, 1, 1001)]
        bad_plans += [{'seed': value} for value in (False, 1.0, -1, 2**63)]
        for plan in bad_plans:
            for function in (lambda: PREVIEW.preview_blueprint_registration(self.lab, original, **plan),
                             lambda: AUTH.register_blueprint(self.lab, obj['id'], **plan)):
                with self.assertRaises(ValueError): function()
                self.assertEqual(self.state(), before)
        for kwargs in ({'blueprint_version': 1}, {'blueprint_hash': obj['hash']},
                       {'blueprint_version': True, 'blueprint_hash': obj['hash']},
                       {'blueprint_version': 1.0, 'blueprint_hash': obj['hash']},
                       {'blueprint_version': 1, 'blueprint_hash': 'f' * 64}):
            with self.assertRaises(ValueError): AUTH.register_blueprint(self.lab, obj['id'], **kwargs)
            self.assertEqual(self.state(), before)

    def test_preview_and_exact_registration_do_not_alias_a_later_blueprint_version(self):
        old = self.blueprint(changes={'modulus': 31})
        p = proposal(); p['parameters']['modulus'] = 43
        new_world = self.lab.construct_environment(proposal=p, fit_review=review(p))
        latest = self.lab.store.put('environment_blueprint', new_world['payload'], old['id'])
        before = self.state(); packet = PREVIEW.preview_blueprint_registration(self.lab, ref(old))
        self.assertEqual(packet['blueprint_ref'], ref(old)); self.assertEqual(self.state(), before)
        pinned = AUTH.register_blueprint(self.lab, old['id'], blueprint_version=old['version'], blueprint_hash=old['hash'])
        latest_selection = AUTH.register_blueprint(self.lab, old['id'])
        self.assertEqual(pinned['payload']['protocol']['environments']['ring']['measurement_world']['modulus'], 31)
        self.assertEqual(latest_selection['payload']['protocol']['environments']['ring']['measurement_world']['modulus'], 43)
        self.assertEqual(pinned['payload']['environment_blueprint_ref']['version'], old['version'])
        self.assertEqual(latest_selection['payload']['environment_blueprint_ref']['version'], latest['version'])

    def test_registration_repeats_source_checks_after_a_successful_preview(self):
        obj = self.blueprint(); packet = PREVIEW.preview_blueprint_registration(self.lab, ref(obj))
        self.assertEqual(packet['status'], 'compatible'); before = self.state()
        real_compile = AUTH.compile_blueprint
        def drift(*args, **kwargs):
            value = real_compile(*args, **kwargs); value['catalog_hash'] = '0' * 64
            return value
        with patch.object(AUTH, 'compile_blueprint', side_effect=drift):
            with self.assertRaisesRegex(ValueError, 'implementation changed'):
                AUTH.register_blueprint(self.lab, obj['id'], blueprint_version=obj['version'], blueprint_hash=obj['hash'])
        self.assertEqual(self.state(), before)

    def test_resealed_saved_world_body_cannot_claim_exact_preservation_from_stale_spec_hash(self):
        obj = self.blueprint(); original_modulus = obj['payload']['spec']['measurement_world']['modulus']
        for value in (43, float(original_modulus), True, float('nan'), float('inf')):
            with self.subTest(value=value):
                payload = copy.deepcopy(obj['payload'])
                payload['spec']['measurement_world']['modulus'] = value
                forged = self.lab.store.put('environment_blueprint', payload, obj['id'])
                before = self.state()
                packet = self.inert(lambda: PREVIEW.preview_blueprint_registration(self.lab, ref(forged)))
                self.assertEqual(packet['status'], 'blocked')
                self.assertEqual(packet['reason']['stage'], 'source')
                self.assertFalse(packet['checks']['current_source_authorization'])
                self.assertIsNone(packet['checks']['design_compatible']); self.assertIsNone(packet['design'])
                with self.assertRaises(ValueError):
                    AUTH.register_blueprint(self.lab, forged['id'], blueprint_version=forged['version'], blueprint_hash=forged['hash'])
                self.assertEqual(self.state(), before)

    def test_returned_plan_and_design_are_finite_bounded_declarations_without_mutable_source_aliases(self):
        obj = self.blueprint(); exact = ref(obj); before = self.state()
        packet = PREVIEW.preview_blueprint_registration(self.lab, exact)
        encoded = json.dumps(packet, allow_nan=False)
        self.assertLess(len(encoded), 12000)
        for key in ('research_question', 'experimental_unit', 'primary_outcome', 'primary_contrast'):
            self.assertIs(type(packet['design'][key]), str); self.assertLess(len(packet['design'][key]), 2000)
        self.assertEqual(packet['design']['maximum_units'], 4); self.assertEqual(packet['design']['maximum_subject_calls'], 48)
        self.assertEqual(packet['design']['maximum_hosted_subject_calls'], 0)
        packet['blueprint_ref']['version'] = 999; packet['design']['conditions'].clear()
        packet['design']['subject_backend']['generation']['policy'] = 'changed-local-only'
        self.assertEqual(exact, ref(obj)); self.assertEqual(self.state(), before)
        again = PREVIEW.preview_blueprint_registration(self.lab, exact)
        self.assertEqual(len(again['design']['conditions']), 2)
        self.assertEqual(again['design']['subject_backend']['generation']['policy'], 'offline_complementary_policy')

    def test_malformed_saved_shape_and_wrong_object_kind_do_not_become_compatibility(self):
        obj = self.blueprint(); changed = copy.deepcopy(obj['payload']); del changed['boundary_audit']
        bad = self.lab.store.put('environment_blueprint', changed, obj['id'])
        packet = PREVIEW.preview_blueprint_registration(self.lab, ref(bad))
        self.assertEqual(packet['reason']['stage'], 'shape'); self.assertIsNone(packet['design'])
        self.assertIsNone(packet['checks']['current_source_authorization'])
        dataset = self.lab.store.put('dataset', {'messages': []})
        packet = PREVIEW.preview_blueprint_registration(self.lab, ref(dataset))
        self.assertEqual(packet['reason']['stage'], 'selection'); self.assertIsNone(packet['design'])

    def test_strict_query_parser_rejects_duplicate_blank_extra_noncanonical_before_any_store(self):
        values = {'blueprint_id': 'environment_blueprint-authored', 'blueprint_version': '1',
                  'blueprint_hash': 'a' * 64, 'trials_per_cell': '2', 'seed': '4491', 'live': 'false'}
        expected = {'blueprint_ref': {'id': values['blueprint_id'], 'version': 1, 'hash': 'a' * 64},
                    'trials_per_cell': 2, 'seed': 4491, 'live': False}
        with patch.object(self.lab.store, 'get', side_effect=AssertionError('Query parsing accessed registry')):
            self.assertEqual(PREVIEW.parse_registration_preview_query(parse_qs(urlencode(values), keep_blank_values=True)), expected)
            bad = []
            for key in values:
                query = {k: [v] for k, v in values.items()}; query[key].append(values[key]); bad.append(query)
                query = {k: [v] for k, v in values.items()}; query[key] = ['']; bad.append(query)
            for key, samples in {'blueprint_version': ['01', '1.0', '+1', ' 1', '0', '1000000001'],
                    'trials_per_cell': ['02', '2.0', '1', '1001'], 'seed': ['04491', '-1', '1e3', '9223372036854775808'],
                    'live': ['False', '0', 'true '], 'blueprint_hash': ['A' * 64, 'x'],
                    'blueprint_id': [' ../thing', 'x' * 201]}.items():
                for value in samples:
                    query = {k: [v] for k, v in values.items()}; query[key] = [value]; bad.append(query)
            bad += [{**{k: [v] for k, v in values.items()}, 'extra': ['ignored']},
                    {k: [v] for k, v in values.items() if k != 'seed'},
                    {**{k: [v] for k, v in values.items()}, 'seed': [True]},
                    {**{k: [v] for k, v in values.items()}, 'live': 'false'}]
            for query in bad:
                with self.assertRaises(ValueError): PREVIEW.parse_registration_preview_query(query)

    def test_actual_cli_registers_the_displayed_version_and_partial_or_stale_pairs_save_nothing(self):
        from swarm_lab.cli import main
        original = self.blueprint(changes={'modulus': 31})
        later = self.blueprint(changes={'modulus': 43})
        self.lab.store.put('environment_blueprint', later['payload'], original['id'])
        def invoke(*arguments):
            output = io.StringIO()
            with patch('swarm_lab.cli.Lab', return_value=self.lab), contextlib.redirect_stdout(output):
                main(['register-blueprint', original['id'], *arguments])
            declared = json.loads(output.getvalue())
            saved = self.lab.store.get(declared['id'], declared['version'])
            self.assertEqual(saved['hash'], declared['hash'])
            return saved
        result = invoke('--blueprint-version', '1', '--blueprint-hash', original['hash'])
        self.assertEqual(result['payload']['environment_blueprint_ref']['version'], 1)
        self.assertEqual(result['payload']['environment_blueprint_ref']['hash'], original['hash'])
        self.assertEqual(result['payload']['protocol']['environments']['ring']['measurement_world']['modulus'], 31)
        before = self.state()
        for args in (('--blueprint-version', '1'), ('--blueprint-hash', original['hash']),
                     ('--blueprint-version', '2', '--blueprint-hash', original['hash'])):
            with self.subTest(args=args), self.assertRaises(ValueError): invoke(*args)
            self.assertEqual(self.state(), before)
        latest = invoke()
        self.assertEqual(latest['payload']['environment_blueprint_ref']['version'], 2)
        self.assertEqual(latest['payload']['protocol']['environments']['ring']['measurement_world']['modulus'], 43)
        self.assertEqual(self.lab.store.usage()['calls'], 0); self.assertEqual(self.lab.store.jobs(), [])


if __name__ == '__main__':
    unittest.main()
