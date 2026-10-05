import unittest
from swarm_lab.network import spectral_basis
from swarm_lab.spectral_observables import describe_observable_signals


class SpectralObservableTests(unittest.TestCase):
    def discovery(self,include_b=True):
        nodes=['a','b'];edges=[{'source':'a','target':'b','weight':1}]
        signals=[{'agent_id':'a','speaker_type':'agent','message_id':'m1','labels':['completion_report']},
                 {'agent_id':'a','speaker_type':'agent','message_id':'m2','labels':[]}]
        if include_b:signals.append({'agent_id':'b','speaker_type':'agent','message_id':'m3','labels':[]})
        signals.append({'agent_id':'a','speaker_type':'human','message_id':'human','labels':['completion_report']})
        return {'signals':signals,'detector_version':'test','network':{'projections':{'observed_mentions':{'nodes':[{'id':n} for n in nodes],'spectral':spectral_basis(nodes,edges)}}}}

    def test_rate_denominators_exclude_humans_and_preserve_exact_positive_ids(self):
        result=describe_observable_signals(self.discovery())['observed_mentions']['completion_report']
        self.assertTrue(result['available']);self.assertEqual(result['rates'],{'a':.5,'b':0})
        self.assertEqual(result['positive_message_ids'],{'a':['m1'],'b':[]})
        self.assertEqual(result['denominators'],{'a':2,'b':1})
        self.assertGreater(result['rayleigh_smoothness'],0)

    def test_referenced_nonauthor_is_unknown_not_an_imputed_silent_agent(self):
        result=describe_observable_signals(self.discovery(False))['observed_mentions']['completion_report']
        self.assertFalse(result['available']);self.assertEqual(result['missing_signal_nodes'],['b'])
        self.assertNotIn('rates',result)
        self.assertTrue(result['induced_author_subgraph']['available'])
        self.assertEqual(result['induced_author_subgraph']['excluded_nodes'],['b'])
        self.assertEqual(result['induced_author_subgraph']['rates'],{'a':.5})

    def test_zero_signal_has_undefined_frequency_fraction_instead_of_fake_consensus(self):
        result=describe_observable_signals(self.discovery())['observed_mentions']['correction']
        self.assertEqual(result['signal_energy'],0)
        self.assertIsNone(result['low_positive_frequency_energy_fraction'])
        self.assertIsNone(result['rayleigh_smoothness'])


if __name__=='__main__':unittest.main()
