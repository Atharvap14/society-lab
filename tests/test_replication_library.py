"""Library integration gates, using executed synthetic policies and no API calls.

The 'live' fixture exercises metadata gates with a local callable. It supplies
no empirical evidence about any hosted model and never touches an API key.
"""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from swarm_lab.audit import snapshot_execution_code
from swarm_lab.environments import ARTIFACT_ID
from swarm_lab.experiments import (ExperimentExecutionError, create_protocol,
    create_replication_protocol, run_experiment)
from swarm_lab.library import link_replication, record_experiment, register_theory
from swarm_lab.replication import behavior_provenance, validate_replication_pair
from swarm_lab.store import Store, fingerprint, now


def local_subject(positive=True):
    def runner(request):
        obs=request['observation'];role=request['role']
        if role=='builder':
            if any(m['message']=='Please repair the manifest.' for m in obs['messages']):
                return {'action':'repair_artifact','artifact_id':ARTIFACT_ID,'contents':obs['required_contents']}
            return {'action':'wait'}
        if role!='coordinator':return {'action':'wait'}
        active='inspect' in ' '.join(request['context']).lower()
        cautious=active if positive else bool(request['context']) and not active
        if cautious and not obs['your_action_history']:
            return {'action':'send_message','recipient':'builder','message':'Please repair the manifest.'}
        if cautious and len(obs['your_action_history'])==1:
            return {'action':'inspect_artifact','artifact_id':ARTIFACT_ID}
        return {'action':'publish_artifact','artifact_id':ARTIFACT_ID}
    return runner


class ReplicationLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.store=Store(self.root/'lab.sqlite3')
        self.dataset=self.store.put('dataset',{'scope':'synthetic fixture'})
        self.discovery=self.store.put('discovery',{'dataset_id':self.dataset['id']})
        self.behavior=self.store.put('behavior',{'title':'Fixture handoff','status':'candidate',
            'dataset_id':self.dataset['id'],'discovery_id':self.discovery['id'],
            'source_refs':{k:{f:v[f] for f in ('id','version','hash')} for k,v in (('dataset',self.dataset),('discovery',self.discovery))},
            'experiment_ids':[],'theory_ids':[]})
        self.counter=0

    def backend(self,live):
        return {'harness':'responses' if live else 'scripted',
            'model':'local_test_double' if live else 'deterministic_offline_policy',
            'generation':{'max_output_tokens':600,'temperature':'provider_default','sampling_seed':'not_set'}}

    def protocol(self,live=True,seed=42):
        p=create_protocol(trials_per_arm=4,seed=seed,max_rounds=3,
            environment_override={'initial_state_distribution':{'valid_probability':0}},
            subject_backend=self.backend(live))
        return self.register(p,live)

    def register(self,p,live=True,original_id=None):
        payload={'protocol':p,'frozen_hash':fingerprint(p),'behavior_id':self.behavior['id'],
            'registered_at':now(),'status':'registered','agent_mode':'live' if live else 'offline_template',
            'subject_adapter_hash':hashlib.sha256(Path('swarm_lab/harness.py').read_bytes()).hexdigest() if live else None}
        if original_id:payload['replicates_protocol_id']=original_id
        return self.store.put('protocol',payload)

    def execute(self,registration,live=True,runner=None,fail=False,archive=True):
        self.counter+=1;directory=self.root/f'run-{self.counter}'
        if archive:snapshot_execution_code(directory)
        protocol=registration['payload']['protocol']
        if fail:
            def transport(request):raise ConnectionError('Synthetic transport failure')
            runner=transport
        try:
            report=run_experiment(protocol,agent_runner=(runner or local_subject()) if live else None,
                backend_metadata=protocol['subject_backend'],output_dir=directory,resamples=100)
        except ExperimentExecutionError as exc:report=exc.partial_report
        signature=report.pop('report_hash',None)
        report.update({'protocol_id':registration['id'],'registered_hash':registration['payload']['frozen_hash'],
            'behavior_id':registration['payload']['behavior_id'],'model':protocol['subject_backend']['model'],
            'agent_mode':'live' if live else 'offline_simulation','artifact_directory':str(directory),
            'canonical_execution_report_hash':signature})
        return self.store.put('experiment',report)

    def pair(self,live=True,positive_original=True,positive_replication=True,rep_fail=False,archive=True):
        original_protocol=self.protocol(live)
        original=self.execute(original_protocol,live,local_subject(positive_original),archive=archive)
        record_experiment(self.store,self.behavior['id'],original)
        replication_protocol=self.register(create_replication_protocol(original_protocol['payload']['protocol'],71),live,original_protocol['id'])
        replication=self.execute(replication_protocol,live,local_subject(positive_replication),fail=rep_fail)
        if not rep_fail:record_experiment(self.store,self.behavior['id'],replication)
        return original,replication,original_protocol,replication_protocol

    def theory(self,original):
        return register_theory(self.store,{'title':'Fixture hypothesis','statement':'A possible mechanism.',
            'supporting_results':['Original observational evidence.'],'conflicting_results':['A recorded rival explanation.'],
            'replication_status':'unreplicated'},self.behavior['id'],original['id'],'offline_template')

    def rewrite_report(self,obj,change):
        payload=copy.deepcopy(obj['payload']);path=Path(payload['artifact_directory'])/'report.json'
        report=json.loads(path.read_text());change(report)
        report.pop('report_hash',None)
        if report['status']=='complete':
            report['report_hash']=hashlib.sha256(json.dumps(report,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        path.write_text(json.dumps(report))
        payload.update({k:v for k,v in report.items() if k!='report_hash'})
        payload['canonical_execution_report_hash']=report.get('report_hash')
        return self.store.put('experiment',payload,obj['id'])

    def test_completed_live_replication_retains_earlier_versions_and_bounds_claim(self):
        original,replication,_,_=self.pair();theory=self.theory(original)
        prior=self.store.get(theory['id']);record=link_replication(self.store,original['id'],replication['id'],theory['id'])
        self.assertEqual(record['payload']['status'],'completed_live_seed_replication')
        behavior=self.store.get(self.behavior['id'])['payload'];after=self.store.get(theory['id'])['payload']
        self.assertEqual(behavior['status'],'replication_tested');self.assertEqual(after['status'],'hypothesis')
        self.assertEqual(after['generalization'],'unestablished');self.assertEqual(after['mechanism_status'],'unestablished')
        self.assertEqual(after['supporting_results'],prior['payload']['supporting_results'])
        self.assertEqual(after['conflicting_results'],prior['payload']['conflicting_results'])
        self.assertEqual(self.store.get(theory['id'],prior['version']),prior)
        self.assertEqual(len(after['quantitative_evidence']),2)
        self.assertEqual(record['payload']['verification']['independence']['environment_seed_overlap'],0)
        self.assertEqual(record['payload']['verification']['original']['source_archive'],'verified_pre_execution_archive')

    def test_opposing_completed_result_is_preserved_as_conflicting_not_filtered(self):
        original,replication,_,_=self.pair(positive_replication=False)
        theory=self.theory(original);link_replication(self.store,original['id'],replication['id'],theory['id'])
        p=self.store.get(theory['id'])['payload'];directional=p['directional_evidence_registry']
        self.assertEqual(directional['supporting_positive_contrast'],[original['id']])
        self.assertEqual(directional['conflicting_negative_contrast'],[replication['id']])
        self.assertEqual(p['status'],'hypothesis')

    def test_scripted_replication_never_becomes_empirical_llm_support(self):
        original,replication,_,_=self.pair(live=False)
        record=link_replication(self.store,original['id'],replication['id']);p=self.store.get(self.behavior['id'])['payload']
        self.assertEqual(record['payload']['status'],'completed_scripted_infrastructure_replication')
        self.assertEqual(p['status'],'infrastructure_tested')
        self.assertEqual(set(p['directional_evidence_registry']['scripted_infrastructure_only']),{original['id'],replication['id']})
        self.assertIn('No empirical LLM',p['causal_support'])

    def test_incomplete_attempt_remains_visible_without_effect_or_promotion(self):
        original,replication,_,_=self.pair(rep_fail=True);theory=self.theory(original)
        record=link_replication(self.store,original['id'],replication['id'],theory['id'])
        self.assertEqual(record['payload']['status'],'incomplete_infrastructure_attempt')
        self.assertIsNone(record['payload']['replication_quantitative_summary'])
        p=self.store.get(self.behavior['id'])['payload'];self.assertEqual(p['status'],'pilot_tested')
        self.assertNotIn(replication['id'],p['experiment_ids']);self.assertIn(replication['id'],p['replication_attempt_ids'])
        self.assertEqual(len(self.store.get(theory['id'])['payload']['quantitative_evidence']),1)

    def test_idempotence_deduplicates_without_new_library_versions(self):
        original,replication,_,_=self.pair();theory=self.theory(original)
        a=link_replication(self.store,original['id'],replication['id'],theory['id'])
        counts=(len(self.store.history(self.behavior['id'])),len(self.store.history(theory['id'])))
        b=link_replication(self.store,original['id'],replication['id'],theory['id'])
        self.assertEqual(a,b);self.assertEqual(counts,(len(self.store.history(self.behavior['id'])),len(self.store.history(theory['id']))))
        self.assertEqual(self.store.get(self.behavior['id'])['payload']['replication_ids'],[a['id']])

    def test_later_incomplete_attempt_does_not_erase_completed_replication(self):
        original,replication,op,_=self.pair();theory=self.theory(original)
        link_replication(self.store,original['id'],replication['id'],theory['id'])
        later_protocol=self.register(create_replication_protocol(op['payload']['protocol'],97),original_id=op['id'])
        later=self.execute(later_protocol,fail=True)
        link_replication(self.store,original['id'],later['id'],theory['id'])
        tp=self.store.get(theory['id'])['payload'];bp=self.store.get(self.behavior['id'])['payload']
        self.assertEqual(tp['replication_status'],'completed_live_seed_replication')
        self.assertEqual(tp['replication_summary']['attempt_count'],2)
        self.assertEqual(tp['replication_summary']['latest_attempt_status'],'incomplete_infrastructure_attempt')
        self.assertEqual(bp['status'],'replication_tested')
        self.assertEqual(set(tp['experiment_ids']),{original['id'],replication['id']})
        self.assertEqual(set(tp['replication_attempt_ids']),{replication['id'],later['id']})

    def test_later_dataset_import_does_not_replace_strict_source_version(self):
        original,replication,_,_=self.pair();self.store.put('dataset',{'scope':'new import'},self.dataset['id'])
        record=link_replication(self.store,original['id'],replication['id'])
        self.assertEqual(record['payload']['source_refs']['dataset']['version'],1)

    def test_legacy_sources_are_pinned_as_of_first_registration_and_marked(self):
        legacy=self.store.put('behavior',{'status':'candidate','dataset_id':self.dataset['id'],
            'discovery_id':self.discovery['id'],'experiment_ids':[],'theory_ids':[]})
        self.store.put('dataset',{'scope':'new import'},self.dataset['id'])
        provenance=behavior_provenance(self.store,legacy)
        self.assertEqual(provenance['source_refs']['dataset']['version'],1)
        self.assertEqual(provenance['resolution'],'legacy_registration_time_reconstruction')

    def test_absent_original_archive_is_visible_limitation_not_fabricated_check(self):
        original,replication,_,_=self.pair(archive=False)
        record=link_replication(self.store,original['id'],replication['id'])
        self.assertEqual(record['payload']['verification']['original']['source_archive'],'not_archived')
        self.assertTrue(any('historical source capture is unavailable' in x for x in record['payload']['limitations']))

    def test_wrong_behavior_protocol_or_theory_link_is_rejected_before_writes(self):
        original,replication,_,rp=self.pair()
        payload=copy.deepcopy(rp['payload']);payload['behavior_id']='other-behavior';self.store.put('protocol',payload,rp['id'])
        with self.assertRaisesRegex(ValueError,'different behaviors'):
            link_replication(self.store,original['id'],replication['id'])
        self.assertEqual(self.store.list('replication'),[])

    def test_unrelated_theory_is_not_rewritten(self):
        original,replication,_,_=self.pair();theory=self.store.put('theory',{'behavior_ids':['other'],'experiment_ids':[original['id']]})
        with self.assertRaisesRegex(ValueError,'Theory is not linked'):
            link_replication(self.store,original['id'],replication['id'],theory['id'])
        self.assertEqual(theory,self.store.get(theory['id']));self.assertEqual(self.store.list('replication'),[])

    def test_changed_frozen_protocol_is_rejected(self):
        original,replication,_,rp=self.pair();p=copy.deepcopy(rp['payload']);p['protocol']['design']['seed']=99
        self.store.put('protocol',p,rp['id'])
        with self.assertRaisesRegex(ValueError,'changed after registration'):
            link_replication(self.store,original['id'],replication['id'])

    def test_reused_seed_namespace_even_resealed_is_rejected(self):
        original,_,op,_=self.pair();p=copy.deepcopy(op['payload']['protocol'])
        p.pop('protocol_hash');p['created_at']=now();p['phase']='held_out_environment_seed_replication'
        p['replicates_protocol_hash']=op['payload']['protocol']['protocol_hash']
        p['protocol_hash']=hashlib.sha256(json.dumps(p,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        rp=self.register(p,original_id=op['id']);replication=self.execute(rp)
        with self.assertRaisesRegex(ValueError,'reuses assigned environment seeds'):
            link_replication(self.store,original['id'],replication['id'])

    def test_assignments_and_oracle_outcomes_cannot_be_rewritten_even_with_new_hash(self):
        original,replication,_,_=self.pair()
        changed=self.rewrite_report(replication,lambda r:r['assignments'][0].update(environment_seed=0))
        with self.assertRaisesRegex(ValueError,'assignments'):
            link_replication(self.store,original['id'],changed['id'])

    def test_oracle_replay_rejects_forged_success(self):
        original,replication,_,_=self.pair()
        def forge(report):report['runs'][0]['outcomes']['success']=1-report['runs'][0]['outcomes']['success']
        changed=self.rewrite_report(replication,forge)
        with self.assertRaisesRegex(ValueError,'oracle outcomes failed replay'):
            link_replication(self.store,original['id'],changed['id'])

    def test_forged_numerical_analysis_is_rejected(self):
        original,replication,_,_=self.pair()
        def forge(report):report['analysis']['primary_effect']['p_two_sided']=0
        changed=self.rewrite_report(replication,forge)
        with self.assertRaisesRegex(ValueError,'numerical effect'):
            link_replication(self.store,original['id'],changed['id'])

    def test_backend_metadata_and_archived_source_hash_are_enforced(self):
        original,replication,_,_=self.pair()
        changed=self.rewrite_report(replication,lambda r:r['backend']['metadata'].update(model='changed'))
        with self.assertRaisesRegex(ValueError,'backend metadata'):
            link_replication(self.store,original['id'],changed['id'])

    def test_separately_pinned_different_model_is_not_comparable_seed_replication(self):
        op=self.protocol();original=self.execute(op)
        p=create_replication_protocol(op['payload']['protocol'],85);p.pop('protocol_hash')
        p['subject_backend']['model']='different_test_double'
        p['protocol_hash']=hashlib.sha256(json.dumps(p,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        rp=self.register(p,original_id=op['id']);replication=self.execute(rp)
        with self.assertRaisesRegex(ValueError,'not a held-out seed replication'):
            link_replication(self.store,original['id'],replication['id'])

    def test_incomplete_report_with_estimated_effect_is_rejected(self):
        original,replication,_,_=self.pair(rep_fail=True)
        changed=self.rewrite_report(replication,lambda r:r.update(analysis={'primary_effect':{'difference':1}}))
        with self.assertRaisesRegex(ValueError,'must not contain estimated effects'):
            link_replication(self.store,original['id'],changed['id'])

    def test_archive_bytes_must_match_registered_hashes(self):
        original,replication,_,_=self.pair();directory=Path(replication['payload']['artifact_directory'])/'execution-code'
        (directory/'environments.py').write_text('changed code')
        with self.assertRaisesRegex(ValueError,'Archived execution source hash'):
            link_replication(self.store,original['id'],replication['id'])

    def test_self_replication_is_rejected(self):
        op=self.protocol();original=self.execute(op)
        with self.assertRaisesRegex(ValueError,'replicate itself'):
            validate_replication_pair(self.store,original['id'],original['id'])


if __name__=='__main__':unittest.main()
