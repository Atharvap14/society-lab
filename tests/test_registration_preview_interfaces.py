"""Real loopback compatibility GET and exact queued registration in temp Stores."""
import concurrent.futures
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
from swarm_lab.server import LocalResearchServer, serve
from tests.test_environment_authoring import proposal, review


class RegistrationPreviewInterfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.lab=Lab(Settings(root=Path(self.temp.name),max_calls=0))
        self.lab.harness=lambda *_: self.fail('Compatibility invoked a research/subject harness')
        self.servers=[];self.executors=[]
        with socket.socket() as handle:
            handle.bind(('127.0.0.1',0));port=handle.getsockname()[1]
        self.base=f'http://127.0.0.1:{port}'
        server_type=LocalResearchServer;pool_type=concurrent.futures.ThreadPoolExecutor
        def capture_server(*args,**kwargs):
            value=server_type(*args,**kwargs);self.servers.append(value);return value
        def capture_pool(*args,**kwargs):
            value=pool_type(*args,**kwargs);self.executors.append(value);return value
        self.server_patch=patch('swarm_lab.server.LocalResearchServer',side_effect=capture_server)
        self.pool_patch=patch('swarm_lab.server.concurrent.futures.ThreadPoolExecutor',side_effect=capture_pool)
        self.server_patch.start();self.pool_patch.start()
        self.addCleanup(self.stop)
        self.worker=threading.Thread(target=serve,args=(self.lab,port),daemon=True);self.worker.start()
        deadline=time.monotonic()+5
        while True:
            try:self.state=self.get('/api/state');break
            except urllib.error.URLError:
                if time.monotonic()>deadline:raise
                time.sleep(.02)

    def stop(self):
        for server in self.servers:server.shutdown()
        self.worker.join(5)
        for pool in self.executors:pool.shutdown(wait=True,cancel_futures=True)
        self.pool_patch.stop();self.server_patch.stop()
        self.assertFalse(self.worker.is_alive())

    def get(self,path):
        with urllib.request.urlopen(self.base+path,timeout=5) as response:return json.load(response)

    def blueprint(self,kind='complementary_information',changes=None):
        p=proposal(kind)
        if changes:p['parameters'].update(changes)
        return self.lab.construct_environment(proposal=p,fit_review=review(p))

    def query(self,obj,live=False):
        return urllib.parse.urlencode({'blueprint_id':obj['id'],'blueprint_version':str(obj['version']),
            'blueprint_hash':obj['hash'],'trials_per_cell':'2','seed':'4491','live':str(live).lower()})

    def rows(self):
        with self.lab.store.connect() as connection:
            return {table:[tuple(row) for row in connection.execute('SELECT * FROM '+table+' ORDER BY 1,2')]
                for table in ('objects','jobs','calls','traces')}

    def test_real_get_binds_exact_world_and_preserves_all_rows_without_provider_or_job(self):
        obj=self.blueprint();before=self.rows()
        value=self.get('/api/blueprint-registration-preview?'+self.query(obj))
        self.assertEqual(value['status'],'compatible')
        self.assertEqual(value['blueprint_ref'],{k:obj[k] for k in ('id','version','hash')})
        self.assertEqual(value['registration_plan'],{'trials_per_cell':2,'seed':4491,'live':False})
        self.assertEqual(value['design']['maximum_units'],4)
        self.assertEqual(value['design']['maximum_subject_calls'],48)
        self.assertEqual(value['design']['maximum_hosted_subject_calls'],0)
        self.assertFalse(value['registered']);self.assertEqual(value['model_calls'],0)
        self.assertEqual(value['database_writes'],0);self.assertEqual(self.rows(),before)
        live=self.get('/api/blueprint-registration-preview?'+self.query(obj,True))
        self.assertEqual(live['design']['subject_backend']['harness'],'responses')
        self.assertEqual(live['design']['maximum_hosted_subject_calls'],48)
        self.assertEqual(self.rows(),before)

    def test_malformed_queries_and_wrong_hash_are_refused_without_mutation(self):
        obj=self.blueprint();query=self.query(obj);before=self.rows()
        tails=['&blueprint_id=duplicate','&unexpected=1','&live=false','&seed=0']
        queries=[query+tail for tail in tails]
        values=dict(urllib.parse.parse_qsl(query))
        for key,value in [('blueprint_version','01'),('trials_per_cell','2.0'),('seed','-1'),
                          ('live','False'),('live','1'),('blueprint_hash','a'*64),('blueprint_id','')]:
            queries.append(urllib.parse.urlencode(values|{key:value}))
        for key in values:
            queries.append(urllib.parse.urlencode({k:v for k,v in values.items() if k!=key}))
        for candidate in queries:
            with self.subTest(candidate=candidate),self.assertRaises(urllib.error.HTTPError) as error:
                self.get('/api/blueprint-registration-preview?'+candidate)
            self.assertEqual(error.exception.code,400)
        self.assertEqual(self.rows(),before)

    def test_approved_custom_world_and_resealed_body_stay_blocked_read_only(self):
        obj=self.blueprint(changes={'topology':'custom','custom_edges':[['agent-0','agent-1']]})
        before=self.rows();value=self.get('/api/blueprint-registration-preview?'+self.query(obj))
        self.assertEqual(value['status'],'blocked');self.assertIsNone(value['design'])
        self.assertTrue(value['checks']['fit_approved_analogue'])
        self.assertTrue(value['checks']['current_source_authorization'])
        self.assertFalse(value['checks']['design_compatible'])
        self.assertEqual(value['reason']['code'],'custom_topology_not_registered')
        self.assertEqual(self.rows(),before)
        valid=self.blueprint();changed=copy.deepcopy(valid['payload'])
        changed['spec']['measurement_world']['modulus']=43
        forged=self.lab.store.put('environment_blueprint',changed,valid['id'])
        before=self.rows();value=self.get('/api/blueprint-registration-preview?'+self.query(forged))
        self.assertEqual(value['status'],'blocked');self.assertFalse(value['checks']['current_source_authorization'])
        self.assertIsNone(value['design']);self.assertEqual(self.rows(),before)

    def test_get_then_actual_queued_registration_retains_displayed_version_and_zero_subjects(self):
        obj=self.blueprint();preview=self.get('/api/blueprint-registration-preview?'+self.query(obj))
        self.assertEqual(preview['status'],'compatible')
        # A later incompatible snapshot must not replace the displayed exact one.
        changed=copy.deepcopy(obj['payload']);changed['experiment_eligibility']='blocked'
        newer=self.lab.store.put('environment_blueprint',changed,obj['id'])
        self.assertGreater(newer['version'],obj['version'])
        args={'blueprint_id':obj['id'],'blueprint_version':obj['version'],'blueprint_hash':obj['hash'],
            'trials_per_cell':2,'seed':4491,'live':False}
        request=urllib.request.Request(self.base+'/api/jobs',method='POST',
            data=json.dumps({'action':'register_blueprint','args':args}).encode(),
            headers={'Content-Type':'application/json','X-Lab-Token':self.state['csrf']})
        with urllib.request.urlopen(request,timeout=5) as response:ack=json.load(response)
        deadline=time.monotonic()+5
        while True:
            job=self.lab.store.get_job(ack['job_id'])
            if job and job['status'] in ('completed','failed'):break
            if time.monotonic()>deadline:self.fail('Queued exact registration did not finish')
            time.sleep(.01)
        self.assertEqual(job['status'],'completed',job)
        result=self.lab.store.get(job['payload']['result_ids'])
        self.assertEqual(result['kind'],'complementary_protocol')
        self.assertEqual(result['payload']['environment_blueprint_ref'],{**preview['blueprint_ref'],'kind':'environment_blueprint'})
        self.assertEqual(result['payload']['protocol']['environments']['ring'],obj['payload']['spec'])
        self.assertEqual(self.lab.store.usage()['calls'],0)
        self.assertFalse(any(o['kind']=='complementary_experiment' for o in self.lab.store.list()))
