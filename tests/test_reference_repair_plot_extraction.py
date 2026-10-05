"""Public plotted measurements from authored temporary-store executions only."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab
from swarm_lab.store import fingerprint
from tests.test_reference_repair_study import prepare,fixture_policy
from swarm_lab import reference_repair_study as study

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('recovery_plot',ROOT/'scripts/build-village-recovery-plots.py')
PLOT=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(PLOT)


class RecoveryPlotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.lab=Lab(Settings(root=Path(self.temp.name),model='fixture-model',max_calls=0))
        _,_,world=prepare(self.lab)
        execution=study.execute_plan(self.lab,json.dumps({'simulator_ref':world['simulator_ref']}).encode(),runner=fixture_policy)
        self.record=self.lab.store.get(execution['result_ref']['id'],1)
        # Renderer shape fixture only: no provider invocation or production claim.
        self.record['payload']['agent_mode']='live';self.seal()

    def seal(self):self.record['hash']=fingerprint(self.record['payload'])

    def test_actual_narrow_oracle_pairs_and_public_only_projection(self):
        data=PLOT.extract(self.record)
        self.assertEqual(data['team_count'],4);self.assertEqual(data['n_pairs'],2)
        self.assertEqual(data['subject_decisions'],64)
        self.assertEqual([r['primary'] for r in data['rows']],[1]*4)
        self.assertEqual(data['primary_effect']['difference'],0)
        self.assertEqual(data['primary_effect']['ci95'],[-1,1])
        for row in data['rows']:
            self.assertEqual(set(row),{'run_id','pair_id','arm','environment_seed','primary','secondary','actions'})
            for action in row['actions']:self.assertEqual(set(action),{'turn_index','action','group','tool_ok'})
        self.assertEqual(self.lab.store.usage()['calls'],0)

    def test_unknown_secondary_count_is_not_zero_and_boolean_is_not_count(self):
        o=self.record['payload']['runs'][0]['outcomes'];o.pop('reference_failures');o['canonical_reference_queued_to_checker']=True;self.seal()
        data=PLOT.extract(self.record);row=next(r for r in data['rows'] if r['run_id']==self.record['payload']['runs'][0]['run_id'])
        self.assertIsNone(row['secondary']['reference_failures']);self.assertIsNone(row['secondary']['canonical_reference_queued_to_checker'])

    def test_old_kind_and_primary_or_pair_analysis_contradictions_refused(self):
        attacks=[lambda r:r.update(kind='village_access_experiment'),
            lambda r:r['payload']['runs'][0]['outcomes'].update(verified_repaired_reference=True),
            lambda r:r['payload']['analysis']['primary_effect'].update(difference=1),
            lambda r:r['payload']['runs'][0].update(environment_seed=1)]
        for change in attacks:
            r=copy.deepcopy(self.record);change(r);r['hash']=fingerprint(r['payload'])
            with self.assertRaises(ValueError):PLOT.extract(r)


if __name__=='__main__':unittest.main()
