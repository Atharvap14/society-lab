"""Independent local-state, typed-evidence and concurrency challenges.

All registry/filesystem changes are in temporary fixtures. Hosted providers are
never called. These tests do not independently prove reviewer semantics.
"""
import concurrent.futures
import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab
from swarm_lab.environment_authoring import blueprint_fingerprint
from swarm_lab.research_cycle import start_research_cycle, resume_research_cycle
from swarm_lab.store import StoreConflictError
from tests.test_environment_authoring import proposal, review


def ref(obj):
    return {k: obj[k] for k in ('kind', 'id', 'version', 'hash')}


class IndependentCycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.lab = Lab(Settings(root=Path(self.tmp.name)))
        self.dataset = self.lab.store.put('dataset', {'messages': [
            {'id': 'm1', 'content': 'A peer reported waiting.', 'room_id': 'room'},
            {'id': 'm2', 'content': 'A peer reported independent work.', 'room_id': 'room'}], 'scope': {}})
        self.discovery = self.lab.store.put('discovery', {'graph': {'edges': []}, 'candidates': [],
            'dataset_ref': {k: self.dataset[k] for k in ('id', 'version', 'hash')}})
        self.sources = {'dataset': ref(self.dataset), 'discovery': ref(self.discovery)}
        self.behavior = self.lab.store.put('behavior', {'name': 'Independent fixture', 'status': 'candidate',
            'evidence_ids': ['m1'], 'dataset_id': self.dataset['id'], 'discovery_id': self.discovery['id'],
            'source_refs': {kind: {k: value[k] for k in ('id', 'version', 'hash')}
                            for kind, value in self.sources.items()}, 'experiment_ids': [], 'theory_ids': []})
        p = proposal()
        materialized = {**p, 'source_refs': [ref(self.behavior), *self.sources.values()]}
        self.blueprint = self.lab.construct_environment(behavior_id=self.behavior['id'], proposal=p,
            fit_review=review(reviewed_blueprint_hash=blueprint_fingerprint(materialized)))
        self.plan = {'behavior_ref': ref(self.behavior), 'source_refs': self.sources,
                     'blueprint_ref': ref(self.blueprint)}

    def cycle(self, identity='independent-cycle', **fields):
        return start_research_cycle(self.lab, **{**self.plan, 'job_id': identity, **fields})

    def test_appended_failed_to_completed_checkpoint_cannot_fake_closure(self):
        with patch.object(self.lab, 'register_blueprint', side_effect=RuntimeError('fixture registration interruption')):
            cycle = self.cycle()
        self.assertEqual(cycle['payload']['status'], 'failed')
        altered = copy.deepcopy(cycle['payload'])
        altered.update(status='completed', phase='completed')
        self.lab.store.put('research_cycle', altered, cycle['id'])
        with self.assertRaises(ValueError):
            resume_research_cycle(self.lab, cycle['id'])

    def test_concurrent_late_writer_cannot_regress_recovered_complete_checkpoint(self):
        completed_subjects = threading.Event(); release_original = threading.Event()
        original = self.lab.experiment_complementary
        calls = []
        def wait_after_persistence(*args, **kwargs):
            calls.append(kwargs['job_id'])
            result = original(*args, **kwargs)
            completed_subjects.set()
            if not release_original.wait(20):
                raise RuntimeError('test coordinator timeout')
            return result
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            with patch.object(self.lab, 'experiment_complementary', side_effect=wait_after_persistence):
                first = executor.submit(self.cycle)
                try:
                    self.assertTrue(completed_subjects.wait(20))
                    cycle_id = self.lab.store.list('research_cycle')[0]['id']
                    recovered = resume_research_cycle(self.lab, cycle_id)
                    self.assertEqual(recovered['payload']['status'], 'completed', recovered['payload']['failures'])
                finally:
                    release_original.set()
                first.result(timeout=20)
        latest = self.lab.store.get(cycle_id)
        self.assertEqual(len(calls), 1)
        self.assertEqual(latest['payload']['status'], 'completed', latest['payload']['failures'])
        self.assertEqual(latest['payload']['artifacts'], recovered['payload']['artifacts'])
        self.assertEqual(self.lab.store.get_job(latest['payload']['job_id'])['status'], 'completed')
        conflicts=[row for row in self.lab.store.traces(latest['payload']['job_id'])
                   if row['payload'].get('type')=='research_cycle_checkpoint_conflict']
        self.assertTrue(conflicts)
        self.assertEqual(conflicts[-1]['payload']['known_artifact_refs']['result'], recovered['payload']['artifacts']['result'])

    def test_completed_return_is_historical_not_a_fresh_raw_archive_attestation(self):
        cycle = self.cycle()
        self.assertEqual(cycle['payload']['status'], 'completed')
        result = self.lab.store.get(cycle['payload']['artifacts']['result']['id'])
        archive = Path(result['payload']['artifact_directory']) / 'report.json'
        archive.write_text('{"corrupted_after_completion":true}', encoding='utf-8')
        with patch.object(self.lab, 'audit', side_effect=AssertionError('resume must not claim fresh replay')):
            returned = resume_research_cycle(self.lab, cycle['id'])
        self.assertEqual(ref(returned), ref(cycle))
        self.assertNotIn('fresh_replay_passed', returned['payload'])

    def test_atomic_shared_ledger_caps_reservations_under_competing_callers(self):
        barrier = threading.Barrier(8)
        def contender(_):
            barrier.wait(timeout=5)
            try:
                return self.lab.store.reserve_call(3)
            except RuntimeError:
                return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            reservations = list(executor.map(contender, range(8)))
        self.assertEqual(sum(r is not None for r in reservations), 3)
        self.assertEqual(self.lab.store.usage()['calls'], 3)
        self.assertEqual(self.lab.store.usage()['completed'], 0)

    def test_cas_conflict_changes_neither_history_nor_jobs(self):
        original=self.lab.store.put('fixture',{'value':1})
        current=self.lab.store.compare_and_put('fixture',{'value':2},original['id'],
            expected_version=original['version'],expected_hash=original['hash'],
            job_updates=[{'id':'cas-root','status':'completed','preserve_completed':False,'payload':{'value':2}}])
        with self.assertRaises(StoreConflictError) as caught:
            self.lab.store.compare_and_put('fixture',{'value':3},original['id'],
                expected_version=original['version'],expected_hash=original['hash'],
                job_updates=[{'id':'cas-root','status':'failed','preserve_completed':False,'payload':{'value':3}}])
        self.assertEqual(caught.exception.latest_ref,ref(current))
        self.assertEqual(len(self.lab.store.history(original['id'])),2)
        self.assertEqual(self.lab.store.get_job('cas-root')['status'],'completed')
        self.assertEqual(self.lab.store.get_job('cas-root')['payload'],{'value':2})

    def test_cas_returns_inserted_version_and_failure_update_preserves_completed_child(self):
        original=self.lab.store.put('fixture',{'value':1})
        self.lab.store.job('child','completed',{'artifact':'saved'})
        inserted=self.lab.store.compare_and_put('fixture',{'value':2},original['id'],
            expected_version=original['version'],expected_hash=original['hash'],job_updates=[
                {'id':'root','status':'failed','preserve_completed':False,'payload':{'checkpoint_version':2}},
                {'id':'child','status':'failed','preserve_completed':True,'payload':{'artifact':'discarded'}}])
        self.lab.store.put('fixture',{'value':3},original['id'])
        self.assertEqual(inserted['version'],2)
        self.assertEqual(inserted['payload'],{'value':2})
        self.assertEqual(self.lab.store.get_job('root')['payload'],{'checkpoint_version':2})
        self.assertEqual(self.lab.store.get_job('child')['status'],'completed')
        self.assertEqual(self.lab.store.get_job('child')['payload'],{'artifact':'saved'})

    def test_cas_rejects_bool_float_bad_hash_and_duplicate_job_updates_before_mutation(self):
        original=self.lab.store.put('fixture',{'value':1})
        for fields in ({'expected_version':True},{'expected_version':1.0},{'expected_hash':'0'},
                       {'job_updates':[{'id':'x','status':'failed','preserve_completed':1,'payload':{}}]},
                       {'job_updates':[{'id':'x','status':'failed','preserve_completed':False,'payload':{}}]*2}):
            args={'expected_version':1,'expected_hash':original['hash']};args.update(fields)
            with self.subTest(fields=fields),self.assertRaises(ValueError):
                self.lab.store.compare_and_put('fixture',{'value':2},original['id'],**args)
            self.assertEqual(len(self.lab.store.history(original['id'])),1)
            self.assertIsNone(self.lab.store.get_job('x'))

    def test_terminal_blocked_returns_only_its_exact_authoritative_closure(self):
        cycle=self.cycle(required_capabilities=['browser_tools'])
        self.assertEqual(cycle['payload']['status'],'blocked')
        self.assertEqual(ref(resume_research_cycle(self.lab,cycle['id'])),ref(cycle))
        altered=copy.deepcopy(cycle['payload']);altered['extension_requirements']=[]
        self.lab.store.put('research_cycle',altered,cycle['id'])
        with self.assertRaises(ValueError):resume_research_cycle(self.lab,cycle['id'])

    def test_rehashed_completed_claim_and_scope_metadata_cannot_replace_terminal_closure(self):
        cycle=self.cycle()
        altered=copy.deepcopy(cycle['payload'])
        altered['artifacts']['claim_audit']['version']=float(altered['artifacts']['claim_audit']['version'])
        self.lab.store.put('research_cycle',altered,cycle['id'])
        with self.assertRaises(ValueError):resume_research_cycle(self.lab,cycle['id'])

    def test_forced_failed_or_running_all_completed_stages_cannot_create_fresh_closure(self):
        for status in ('failed','running'):
            with self.subTest(status=status):
                cycle=self.cycle('forced-'+status)
                altered=copy.deepcopy(cycle['payload']);altered.update(status=status,phase='curate')
                self.lab.store.put('research_cycle',altered,cycle['id'])
                with self.assertRaises(ValueError):resume_research_cycle(self.lab,cycle['id'])

    def test_theory_status_inflation_cannot_authorize_curation(self):
        import swarm_lab.research_cycle as module
        actual=module._curate
        def inflated(lab,p):
            saved=actual(lab,p);altered=copy.deepcopy(saved['payload'])
            altered.update(status='established',mechanism_support='proven')
            return lab.store.put('theory',altered,saved['id'])
        with patch('swarm_lab.research_cycle._curate',side_effect=inflated):cycle=self.cycle()
        self.assertEqual(cycle['payload']['status'],'blocked')
        self.assertEqual(cycle['payload']['phase'],'curate')
        self.assertEqual(cycle['payload']['stages']['curate']['failure_code'],'curation_binding_mismatch')

    def test_exhausted_live_call_ceiling_does_not_prevent_completed_result_recovery(self):
        from swarm_lab.complementary_environment import offline_complementary_policy
        actual=self.lab.experiment_complementary
        counter=[]
        class FakeSubject:
            def subject(_self,request):
                self.lab.store.reserve_call(48);counter.append(request['role'])
                return offline_complementary_policy(request)
        def interruption(*args,**kwargs):
            actual(*args,**kwargs)
            raise RuntimeError('interruption after all fake-provider calls completed')
        with patch.object(self.lab,'harness',return_value=FakeSubject()),patch.object(self.lab,'experiment_complementary',side_effect=interruption):
            cycle=self.cycle(subjects_live=True,max_new_model_calls=48)
            self.assertEqual(cycle['payload']['status'],'failed',cycle['payload']['failures'])
            used=self.lab.store.usage()['calls']
            self.assertEqual(used,48)
            recovered=resume_research_cycle(self.lab,cycle['id'])
        self.assertEqual(recovered['payload']['status'],'completed',recovered['payload']['failures'])
        self.assertEqual(len(counter),48)
        self.assertEqual(self.lab.store.usage()['calls'],48)

    def test_known_but_unretrieved_fact_id_cannot_advance_live_authoring(self):
        candidate=proposal()
        candidate['observed_facts']=[{'statement':'A peer reported independent work.',
            'source_ids':[self.dataset['id']],'evidence_ids':['m2']}]
        class FakeResearch:
            name='cpu-fake-research'
            def run(_self,system,task,tools,job_id,*,schema):
                field=schema['properties']['observed_facts']['items']['properties']['evidence_ids']
                self.assertEqual(field['items']['enum'],['m1'])
                return copy.deepcopy(candidate)
        with patch.object(self.lab,'research_harness',return_value=FakeResearch()):
            cycle=start_research_cycle(self.lab,behavior_ref=ref(self.behavior),source_refs=self.sources,
                research_live=True,max_new_model_calls=2,job_id='unretrieved-cycle')
        self.assertEqual(cycle['payload']['status'],'failed')
        self.assertEqual(cycle['payload']['phase'],'construct')
        self.assertIn('did not read',cycle['payload']['failures'][-1]['error'])
        self.assertNotIn('protocol',cycle['payload']['artifacts'])
        self.assertEqual(self.lab.store.usage()['calls'],0)

    def test_actual_retrieval_refreshes_nested_schema_and_authoring_source_binding(self):
        candidate=proposal()
        candidate['observed_facts']=[{'statement':'A peer reported independent work.',
            'source_ids':[self.dataset['id']],'evidence_ids':['m2']}]
        seen=[]
        class FakeResearch:
            name='cpu-fake-research'
            def run(_self,system,task,tools,job_id,*,schema):
                if 'observed_facts' in schema['properties']:
                    field=schema['properties']['observed_facts']['items']['properties']['evidence_ids']
                    self.assertEqual(field['items']['enum'],['m1'])
                    retrieved=tools['read_evidence']['execute'](ids=['m2'])
                    self.assertEqual(retrieved,[self.dataset['payload']['messages'][1]])
                    self.assertEqual(field['items']['enum'],['m1','m2'])
                    seen.append('builder')
                    return copy.deepcopy(candidate)
                seen.append('reviewer')
                return review(reviewed_blueprint_hash=task['reviewed_blueprint_hash'])
        with patch.object(self.lab,'research_harness',return_value=FakeResearch()):
            cycle=start_research_cycle(self.lab,behavior_ref=ref(self.behavior),source_refs=self.sources,
                research_live=True,max_new_model_calls=2,job_id='retrieved-cycle')
        self.assertEqual(cycle['payload']['status'],'completed',cycle['payload']['failures'])
        self.assertEqual(seen,['builder','reviewer'])
        blueprint=self.lab.store.get(cycle['payload']['artifacts']['blueprint']['id'])
        self.assertEqual(blueprint['payload']['source_verification']['status'],
            'verified_object_versions_and_record_membership')
        self.assertEqual(blueprint['payload']['proposed_blueprint']['observed_facts'],candidate['observed_facts'])
        self.assertEqual(self.lab.store.usage()['calls'],0)

    def test_rehashed_failed_stage_float_attempt_count_rejects_before_safe_relaunch(self):
        with patch.object(self.lab,'audit',side_effect=RuntimeError('CPU fixture interruption')):
            cycle=self.cycle('attempt-type-fixture')
        altered=copy.deepcopy(cycle['payload'])
        altered['stages']['audit']['attempts']=1.0
        self.lab.store.put('research_cycle',altered,cycle['id'])
        with patch.object(self.lab,'audit',side_effect=AssertionError('tampered stage must not execute')):
            with self.assertRaises(ValueError):
                resume_research_cycle(self.lab,cycle['id'])

    def test_running_checkpoint_stage_counts_id_refs_and_order_are_typed_before_recovery(self):
        with patch.object(self.lab,'audit',side_effect=RuntimeError('CPU fixture interruption')):
            cycle=self.cycle('running-shape-fixture')
        modifications=[lambda p:p['stages']['audit'].update(attempts=True),
            lambda p:p['stages']['audit'].update(attempts=1.0),
            lambda p:p['stages']['audit'].update(job_id=p['job_id']+'.audit.2'),
            lambda p:p['stages']['audit'].update(artifact_ref=p['artifacts']['blueprint']),
            lambda p:p['stages']['claims'].update(status='running',attempts=1,
                job_id=p['job_id']+'.claims.1')]
        for index,modify in enumerate(modifications):
            with self.subTest(index=index):
                altered=copy.deepcopy(cycle['payload']);altered['status']='running';modify(altered)
                self.lab.store.put('research_cycle',altered,cycle['id'])
                self.lab.store.job(altered['job_id'],'running',{'stage':'research_cycle',
                    'cycle_id':cycle['id'],'plan_hash':altered['plan_hash']})
                with patch.object(self.lab,'audit',side_effect=AssertionError('invalid checkpoint must not execute')):
                    with self.assertRaises(ValueError):resume_research_cycle(self.lab,cycle['id'])
        self.assertEqual(len(self.lab.store.list('complementary_experiment')),1)
        self.assertEqual(self.lab.store.usage()['calls'],0)

    def test_failed_resume_requires_retained_root_closure_without_rewriting_it(self):
        with patch.object(self.lab,'audit',side_effect=RuntimeError('CPU fixture interruption')):
            cycle=self.cycle('failed-root-fixture')
        root=self.lab.store.get_job(cycle['payload']['job_id'])
        self.lab.store.job(root['id'],'running',root['payload'])
        before=self.lab.store.get_job(root['id'])
        with patch.object(self.lab,'audit',side_effect=AssertionError('authority gap must not execute')):
            with self.assertRaises(ValueError):resume_research_cycle(self.lab,cycle['id'])
        self.assertEqual(self.lab.store.get_job(root['id']),before)
        self.assertEqual(ref(self.lab.store.get(cycle['id'])),ref(cycle))

    def test_completed_resume_closes_its_invocation_claim_to_exact_returned_ref(self):
        with patch.object(self.lab,'audit',side_effect=RuntimeError('CPU fixture interruption')):
            cycle=self.cycle('resume-invocation-fixture')
        returned=resume_research_cycle(self.lab,cycle['id'])
        self.assertEqual(returned['payload']['status'],'completed')
        invocation=self.lab.store.get_job(cycle['payload']['job_id']+'.resume.1')
        self.assertEqual(invocation['status'],'completed')
        self.assertEqual(invocation['payload']['cycle_ref'],ref(returned))
        self.assertEqual(invocation['payload']['cycle_status'],'completed')

    def test_failed_resume_closes_invocation_without_altering_failed_cycle_identity(self):
        with patch.object(self.lab,'audit',side_effect=RuntimeError('CPU fixture interruption')):
            cycle=self.cycle('failed-resume-invocation-fixture')
            returned=resume_research_cycle(self.lab,cycle['id'])
        self.assertEqual(returned['payload']['status'],'failed')
        invocation=self.lab.store.get_job(cycle['payload']['job_id']+'.resume.1')
        self.assertEqual(invocation['status'],'failed')
        self.assertEqual(invocation['payload']['cycle_ref'],ref(returned))
        self.assertEqual(invocation['payload']['cycle_status'],'failed')
        root=self.lab.store.get_job(cycle['payload']['job_id'])
        self.assertEqual(root['payload']['cycle_ref'],ref(returned))

    def test_resume_invocation_exception_retains_identity_without_failing_authoritative_root(self):
        with patch.object(self.lab,'audit',side_effect=RuntimeError('CPU fixture interruption')):
            cycle=self.cycle('exception-resume-invocation-fixture')
        with patch('swarm_lab.research_cycle._drive',side_effect=RuntimeError('injected invocation CPU failure')):
            with self.assertRaisesRegex(RuntimeError,'injected invocation'):
                resume_research_cycle(self.lab,cycle['id'])
        invocation=self.lab.store.get_job(cycle['payload']['job_id']+'.resume.1')
        latest=self.lab.store.get(cycle['id'])
        self.assertEqual(invocation['status'],'failed')
        self.assertEqual(invocation['payload']['requested_cycle_ref'],ref(cycle))
        self.assertEqual(invocation['payload']['last_recorded_cycle_ref'],ref(latest))
        self.assertEqual(invocation['payload']['outcome'],'exception')
        self.assertNotIn('cycle_ref',invocation['payload'])
        self.assertEqual(self.lab.store.get_job(cycle['payload']['job_id'])['status'],'running')
        self.assertEqual(latest['payload']['status'],'running')
        self.assertEqual(len(self.lab.store.list('complementary_experiment')),1)

    def test_conflicted_resume_closes_invocation_to_latest_without_failing_active_root(self):
        import swarm_lab.research_cycle as module
        with patch.object(self.lab,'audit',side_effect=RuntimeError('CPU fixture interruption')):
            cycle=self.cycle('conflicted-resume-invocation-fixture')
        actual=module._save
        def advance_then_conflict(lab,obj,payload):
            actual(lab,obj,payload)
            return actual(lab,obj,payload)  # Real stale expected-version CAS failure.
        with patch('swarm_lab.research_cycle._save',side_effect=advance_then_conflict),\
                patch.object(self.lab,'audit',side_effect=AssertionError('conflict must not execute another stage')):
            returned=resume_research_cycle(self.lab,cycle['id'])
        invocation=self.lab.store.get_job(cycle['payload']['job_id']+'.resume.1')
        self.assertEqual(returned['payload']['status'],'running')
        self.assertEqual(invocation['status'],'failed')
        self.assertEqual(invocation['payload']['cycle_ref'],ref(returned))
        self.assertEqual(invocation['payload']['cycle_status'],'running')
        self.assertEqual(self.lab.store.get_job(cycle['payload']['job_id'])['status'],'running')
        self.assertEqual(ref(self.lab.store.get(cycle['id'])),ref(returned))
        self.assertEqual(len(self.lab.store.list('complementary_experiment')),1)

    def test_rehashed_initial_snapshot_cannot_change_root_identity_to_relaunch_subjects(self):
        with patch.object(self.lab,'audit',side_effect=RuntimeError('CPU fixture interruption')):
            cycle=self.cycle('immutable-root-fixture')
        altered=copy.deepcopy(self.lab.store.history(cycle['id'])[0]['payload'])
        altered['job_id']='replacement-root-fixture'
        self.lab.store.put('research_cycle',altered,cycle['id'])
        with self.assertRaises(ValueError):resume_research_cycle(self.lab,cycle['id'])
        self.assertEqual(len(self.lab.store.list('complementary_experiment')),1)


if __name__ == '__main__':
    unittest.main()
