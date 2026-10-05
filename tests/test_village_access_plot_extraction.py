"""Derived figure contracts on explicitly authored unit fixtures; no model calls."""
import copy
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from swarm_lab.guide_reports import render_report
from swarm_lab.store import Store, fingerprint

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('village_plot_script', ROOT/'scripts/build-village-access-plots.py')
plot=importlib.util.module_from_spec(spec); spec.loader.exec_module(plot)


def fixture():
    source={'id':'dataset-plot-fixture','version':1,'hash':'a'*64}
    fidelity={'represented':['Reference and permission repair'], 'approximated':['Local tool state'],
        'omitted':['Historical Google state'], 'historical_equivalence':False}
    hypothesis={'statement':'Authored fixture: canonical checking versus a neutral note.'}
    protocol={'environment':{'kind':plot.FAMILY}, 'grounding':{'source_ref':source,'evidence_ids':['post-fixture']},
        'hypothesis':copy.deepcopy(hypothesis),'fidelity':copy.deepcopy(fidelity),
        'design':{'trials_per_arm':2},'primary_outcome':plot.PRIMARY}
    runs=[]
    for pair in (1,2):
        for arm in plot.ARMS:
            runs.append({'run_id':f'pair-{pair}-{arm}','pair_id':pair,'arm':arm,'environment_seed':100+pair,
                'status':'complete','turns':[{'step':0,'action':{'action':'open_url','url':'PRIVATE_UNEXPORTED'},
                    'request':{'private_content':'PRIVATE_UNEXPORTED'},'tool_result':{'ok':False,'provider':'PRIVATE_UNEXPORTED'}},
                    {'step':1,'action':{'action':'inspect_document'},'tool_result':{}}],
                'outcomes':{plot.PRIMARY:int(pair==1 and arm=='canonical_check'),
                    'avoidable_recreations':0,'access_failures':None,'completed_tasks':2}})
    payload={'agent_mode':'live','status':'complete','protocol':protocol,'source_refs':{'dataset_ref':source},
        'hypothesis':hypothesis,'fidelity':fidelity,'runs':runs,
        'analysis':{'arms':{'neutral_note':{'n':2,'success':0},'canonical_check':{'n':2,'success':.5}},
            'primary_effect':{'difference':.5,'mean_treatment':.5,'mean_control':0,'ci95':[-1,1],
                'interval_method':'bounded_pair_Hoeffding_95','unit':'whole_team','n_pairs':2,'pair_differences':[1,0]}}}
    return {'id':'village-access-plot-fixture','version':1,'kind':'village_access_experiment',
        'payload':payload,'hash':fingerprint(payload)}


def reseal(record):
    record['hash']=fingerprint(record['payload']); return record


class VillageAccessPlotTests(unittest.TestCase):
    def test_pairing_primary_field_privacy_and_unknown_are_independent(self):
        record=fixture(); before=copy.deepcopy(record); data=plot.extract(record)
        self.assertEqual(data['team_count'],4);self.assertEqual(data['n_pairs'],2)
        self.assertEqual(data['subject_decisions'],8)
        self.assertEqual(data['pairs'][0]['difference'],1)
        self.assertEqual(data['primary_effect']['difference'],.5)
        self.assertEqual(data['rows'][0]['secondary']['avoidable_recreations'],0)
        self.assertIsNone(data['rows'][0]['secondary']['access_failures'])
        self.assertFalse(data['rows'][0]['actions'][0]['tool_ok'])
        self.assertIsNone(data['rows'][0]['actions'][1]['tool_ok'])
        self.assertNotIn('PRIVATE_UNEXPORTED',json.dumps(data));self.assertEqual(record,before)
        # An unrelated success alias must not substitute for the actual oracle.
        record['payload']['runs'][0]['outcomes']['success']=1
        self.assertEqual(plot.extract(reseal(record))['rows'][0]['primary'],0)

    def test_source_mode_kind_primary_and_pair_fail_closed(self):
        mutations=[lambda r:r.update(kind='experiment'),lambda r:r['payload'].update(agent_mode='provided_runner'),
            lambda r:r['payload'].update(status='incomplete_infrastructure_failure'),
            lambda r:r['payload']['runs'][0]['outcomes'].update(verified_usable_project=True),
            lambda r:r['payload']['runs'][0]['outcomes'].pop(plot.PRIMARY),
            lambda r:r['payload']['runs'][0].update(pair_id=True),
            lambda r:r['payload']['runs'][1].update(environment_seed=999),
            lambda r:r['payload']['runs'][1].update(arm='neutral_note'),
            lambda r:r['payload']['protocol']['grounding'].update(source_ref={'id':'dataset-other','version':1,'hash':'b'*64}),
            lambda r:r['payload']['runs'][0]['turns'][0].update(step=True)]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                r=fixture(); mutate(r)
                with self.assertRaises(ValueError):plot.extract(reseal(r))
        r=fixture();r['hash']='b'*64
        with self.assertRaises(ValueError):plot.extract(r)

    def test_saved_analysis_cannot_borrow_rates_counts_or_intervals(self):
        mutations=[lambda p:p['analysis']['arms']['neutral_note'].update(success=1),
            lambda p:p['analysis']['arms']['neutral_note'].update(n=True),
            lambda p:p['analysis']['primary_effect'].update(difference=0),
            lambda p:p['analysis']['primary_effect'].update(pair_differences=[True,0]),
            lambda p:p['analysis']['primary_effect'].update(ci95=[0,1]),
            lambda p:p['analysis']['primary_effect'].update(interval_method='other_interval')]
        for mutate in mutations:
            r=fixture();mutate(r['payload'])
            with self.subTest(mutation=mutate),self.assertRaises(ValueError):plot.extract(reseal(r))

    def test_secondary_unavailable_values_do_not_become_zero(self):
        for value in (None,True,False,1.0,'0',-1):
            r=fixture();r['payload']['runs'][0]['outcomes']['access_failures']=value
            self.assertIsNone(plot.extract(reseal(r))['rows'][0]['secondary']['access_failures'])
        r=fixture();r['payload']['runs'][0]['outcomes']['access_failures']=float('nan')
        with self.assertRaises(ValueError):plot.extract(reseal(r))

    def test_exact_historical_read_only_registry_version(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'lab.sqlite3';store=Store(path);old=fixture()
            saved=store.put(old['kind'],old['payload'],old['id'])
            changed=copy.deepcopy(old['payload']);changed['hypothesis']['statement']='New fixture question'
            changed['protocol']['hypothesis']['statement']='New fixture question'
            store.put(old['kind'],changed,old['id'])
            ref={key:saved[key] for key in ('id','version','hash')}
            with closing(sqlite3.connect(path)) as connection: before=connection.execute('SELECT COUNT(*) FROM objects').fetchone()[0]
            self.assertEqual(plot.read_record(path,ref)['payload'],old['payload'])
            wrong={**ref,'hash':'b'*64}
            with self.assertRaises(ValueError):plot.read_record(path,wrong)
            with closing(sqlite3.connect(path)) as connection: self.assertEqual(connection.execute('SELECT COUNT(*) FROM objects').fetchone()[0],before)

    def test_generated_cache_embeds_only_exact_village_result(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'lab.sqlite3'); r=fixture();saved=store.put(r['kind'],r['payload'],r['id'])
            ref={key:saved[key] for key in ('id','version','hash')}; data=plot.extract(saved)
            directory=Path(folder)/'plots'/saved['hash']; png=plot.draw(data,directory)
            self.assertLess(png.stat().st_size,800*1024)
            manifest=json.loads((directory/'source.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['source_ref'],ref);self.assertEqual(manifest['schema'],'societylab.experiment-plots.v1')
            self.assertNotIn('PRIVATE_UNEXPORTED',json.dumps(manifest))
            report=render_report(store,ref)
            self.assertIn('data:image/png;base64,',report)
            self.assertIn('bounded-pair Hoeffding',report)
            manifest['source_ref']['version']+=1
            (directory/'source.json').write_text(json.dumps(manifest),encoding='utf-8')
            self.assertNotIn('data:image/png;base64,',render_report(store,ref))


if __name__=='__main__':unittest.main()
