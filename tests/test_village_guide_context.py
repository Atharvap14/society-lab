"""Authored exact Village cards must coexist in the bounded guide prompt."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab
from swarm_lab import village_access_study as study
from swarm_lab.guide_assistant import grounded_context,parse_guide_request,MAX_CONTEXT_CHARACTERS
from swarm_lab.state_inventory_cache import CompactObjectInventoryCache
from tests.test_village_access_study import dataset,body,raw,mocked_roles

class VillageGuideContextTests(unittest.TestCase):
    def test_exact_incident_world_and_result_survive_a_controlled_larger_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            lab=Lab(Settings(root=Path(directory),model='fixture-model',max_calls=0))
            source=dataset(lab);_,packet=study._grounding(lab,study._ref(source))
            packet['incidents']=[{'id':f'authored-incident-{i}','name':'Authored document access report',
                'evidence_ids':[m['id'] for m in source['payload']['messages']],
                'observed_reports':['Authored reported observation '+str(j)+' '+'x'*160 for j in range(4)],
                'mechanisms_needed':['Document identity/ACL/session analogue '+str(j)+' '+'y'*150 for j in range(4)],
                'rival_explanations':['Unverified original state '+str(j)+' '+'z'*155 for j in range(4)]} for i in range(5)]
            location=lab.settings.runtime/'village-access-grounding';location.mkdir()
            (location/'grounding-v1.json').write_text(json.dumps(packet),encoding='utf-8')
            plan=study.create_plan(lab,raw(body(source)))
            with patch('swarm_lab.research.ResearchAgents.run',side_effect=mocked_roles):
                world=study.create_simulator(lab,raw({'plan_ref':plan['plan_ref']}))
            execution=study.execute_plan(lab,raw({'simulator_ref':world['simulator_ref']}),runner=lambda request:{'action':'wait'})
            refs={'dataset_ref':study._ref(source),'incident_ref':plan['incident_ref'],'plan_ref':plan['plan_ref'],
                'simulator_ref':world['simulator_ref'],'result_ref':execution['result_ref'],'execution_ref':execution['execution_ref']}
            request=parse_guide_request(raw({'message':'Explain this exact result.','current_view':'workspace','current_context':refs}))
            inventory=[CompactObjectInventoryCache._compact(row) for row in lab.store.list(limit=200)]
            with patch('swarm_lab.guide_assistant.MAX_CONTEXT_CHARACTERS',16000),self.assertRaisesRegex(ValueError,'context exceeds'):
                grounded_context(lab,request,inventory)
            context,catalog,sources=grounded_context(lab,request,inventory)
            self.assertGreater(len(json.dumps(context,ensure_ascii=False)),16000)
            self.assertLessEqual(len(json.dumps(context,ensure_ascii=False)),MAX_CONTEXT_CHARACTERS)
            self.assertEqual(context['source_grounded_incidents']['ref'],refs['incident_ref'])
            self.assertEqual(context['current_saved_world']['simulator_ref'],refs['simulator_ref'])
            for key in ('dataset_ref','incident_ref','plan_ref','simulator_ref','result_ref','execution_ref'):
                self.assertIn('source:'+refs[key]['id']+':v1',sources)
            self.assertEqual(lab.store.usage()['calls'],0)

if __name__=='__main__':unittest.main()
