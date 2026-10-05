import importlib.util
from pathlib import Path
import unittest
from swarm_lab.store import fingerprint
spec=importlib.util.spec_from_file_location('plot_script',Path(__file__).resolve().parents[1]/'scripts'/'build-experiment-plots.py')
plot=importlib.util.module_from_spec(spec);spec.loader.exec_module(plot)

class PlotExtractionTests(unittest.TestCase):
    def test_unknown_is_not_zero_and_no_context_is_exported(self):
        p={'status':'complete','runs':[{'run_id':'run-1','arm':'baseline','outcomes':{'success':0,'inspected_publication':None},'turns':[{'step':9,'action':{'action':'wait','secret':'excluded'},'request':{'secret':'excluded'}}]}]}
        r={'id':'experiment-fixture','version':1,'kind':'experiment','payload':p,'hash':fingerprint(p)}
        data=plot.extract(r)
        self.assertEqual(data['rows'][0]['metrics']['success'],0)
        self.assertIsNone(data['rows'][0]['metrics']['inspected_publication'])
        self.assertIsNone(data['effects'][0]['difference'])
        self.assertNotIn('secret',str(data))
        self.assertEqual(data['rows'][0]['actions'][0]['turn_index'],0)
        self.assertEqual(data['rows'][0]['actions'][0]['step'],9)
        r['hash']='a'*64
        with self.assertRaises(ValueError):plot.extract(r)

    def test_binary_types_and_nonfinite_unknown(self):
        for value in [None,True,False,'0',float('nan'),float('inf'),-1,2]: self.assertIsNone(plot.binary(value))
        self.assertEqual(plot.binary(0),0);self.assertEqual(plot.binary(1),1)
