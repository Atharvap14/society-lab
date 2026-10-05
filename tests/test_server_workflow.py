"""Actual loopback API execution in an isolated store, with no credentials."""
import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from swarm_lab.config import ROOT


class ServerWorkflowTests(unittest.TestCase):
    def test_complementary_and_resource_queue_execute_replay_and_claims(self):
        with tempfile.TemporaryDirectory() as directory:
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            code='from pathlib import Path; import sys; from swarm_lab.pipeline import Lab; from swarm_lab.config import Settings; from swarm_lab.server import serve; serve(Lab(Settings(root=Path(sys.argv[1]))),int(sys.argv[2]))'
            process=subprocess.Popen([sys.executable,'-c',code,directory,str(port)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                base=f'http://127.0.0.1:{port}'
                def get(path):
                    with urllib.request.urlopen(base+path,timeout=5) as response:return json.load(response)
                deadline=time.monotonic()+8
                while True:
                    try:state=get('/api/state');break
                    except urllib.error.URLError:
                        if time.monotonic()>deadline:raise
                        time.sleep(.05)
                self.assertEqual(state['service_version'],'complementary-1')
                self.assertIn('design_complementary',state['supported_actions'])
                self.assertIn('design_resource',state['supported_actions'])
                self.assertIn('audit_name_eligibility',state['supported_actions'])
                def submit(action,args):
                    request=urllib.request.Request(base+'/api/jobs',data=json.dumps({'action':action,'args':args}).encode(),
                        headers={'Content-Type':'application/json','X-Lab-Token':state['csrf']})
                    with urllib.request.urlopen(request,timeout=5) as response:job=json.load(response)['job_id']
                    until=time.monotonic()+15
                    while time.monotonic()<until:
                        current=next(j for j in get('/api/state')['jobs'] if j['id']==job)
                        if current['status'] in ('failed','completed'):
                            self.assertEqual(current['status'],'completed',current['payload']);return current['payload']['result_ids']
                        time.sleep(.05)
                    self.fail('Local scripted job did not finish')
                denied=urllib.request.Request(base+'/api/jobs',data=b'{"action":"design_complementary"}',headers={'Content-Type':'application/json'})
                with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(denied,timeout=5)
                self.assertEqual(error.exception.code,403)
                protocol=submit('design_complementary',{'seed':901})
                result=submit('experiment_complementary',{'protocol_id':protocol})
                verification=submit('audit',{'result_id':result})
                self.assertTrue(get('/api/object/'+verification)['payload']['passed'])
                claims=submit('evaluate_claims',{'result_id':result})
                self.assertTrue(get('/api/object/'+claims)['payload']['audit']['all_executable_claims_supported'])
                resource=submit('design_resource',{'seed':932,'release_rounds':[0,2,6]})
                executed=submit('experiment_resource',{'protocol_id':resource})
                replay=submit('audit',{'result_id':executed})
                self.assertTrue(get('/api/object/'+replay)['payload']['passed'])
                facts=submit('evaluate_claims',{'result_id':executed})
                self.assertTrue(get('/api/object/'+facts)['payload']['quantitative_facts_available'])
                self.assertTrue(get('/api/object/'+facts)['payload']['audit']['all_executable_claims_supported'])
                self.assertEqual(get('/api/state')['usage']['calls'],0)
            finally:
                process.terminate();process.wait(timeout=5)


if __name__=='__main__':unittest.main()
