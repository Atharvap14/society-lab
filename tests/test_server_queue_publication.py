"""A forced component/queue publication boundary, without hosted requests."""
import json
import concurrent.futures
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab
from swarm_lab.server import LocalResearchServer,serve


class PausedLab(Lab):
    def __init__(self,root,fail):
        super().__init__(Settings(root=root))
        self.entered=threading.Event()
        self.release=threading.Event()
        self.fail=fail

    def experiment_complementary(self,protocol_id,*,live=False,job_id=None):
        terminal='failed' if self.fail else 'completed'
        self.store.job(job_id,terminal,{'stage':'component','result_id':'early-link',
            'incomplete_result_id':'saved-partial' if self.fail else None})
        self.entered.set()
        if not self.release.wait(5):raise TimeoutError('Test did not release component')
        if self.fail:raise ValueError('Declared test failure')
        return self.store.put('complementary_experiment',{'status':'complete','fixture':True})


class QueuePublicationTests(unittest.TestCase):
    def check_boundary(self,fail):
        with tempfile.TemporaryDirectory() as directory:
            lab=PausedLab(Path(directory),fail)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            servers=[];executors=[]
            def capture(*args,**kwargs):
                server=LocalResearchServer(*args,**kwargs);servers.append(server);return server
            executor_class=concurrent.futures.ThreadPoolExecutor
            def capture_executor(*args,**kwargs):
                executor=executor_class(*args,**kwargs);executors.append(executor);return executor
            with patch('swarm_lab.server.LocalResearchServer',side_effect=capture), \
                 patch('swarm_lab.server.concurrent.futures.ThreadPoolExecutor',side_effect=capture_executor):
                worker=threading.Thread(target=serve,args=(lab,port),daemon=True)
                worker.start()
                base=f'http://127.0.0.1:{port}'
                def get():
                    with urllib.request.urlopen(base+'/api/state',timeout=5) as response:return json.load(response)
                try:
                    until=time.monotonic()+5
                    while True:
                        try:state=get();break
                        except urllib.error.URLError:
                            if time.monotonic()>until:raise
                            time.sleep(.02)
                    request=urllib.request.Request(base+'/api/jobs',
                        data=json.dumps({'action':'experiment_complementary','args':{'protocol_id':'fixture'}}).encode(),
                        headers={'Content-Type':'application/json','X-Lab-Token':state['csrf']})
                    with urllib.request.urlopen(request,timeout=5) as response:identity=json.load(response)['job_id']
                    self.assertTrue(lab.entered.wait(5))
                    def job():return next(j for j in get()['jobs'] if j['id']==identity)
                    pending=job()
                    self.assertEqual(pending['status'],'running')
                    self.assertEqual(pending['payload']['action'],'experiment_complementary')
                    self.assertEqual(pending['payload']['component_status'],'failed' if fail else 'completed')
                    self.assertNotIn('result_ids',pending['payload'])
                    self.assertEqual(lab.store.get_job(identity)['status'],'running')
                    lab.release.set()
                    until=time.monotonic()+5
                    while True:
                        done=job()
                        if done['status'] in ('completed','failed'):break
                        if time.monotonic()>until:self.fail('Queue did not publish terminal result')
                        time.sleep(.02)
                    if fail:
                        self.assertEqual(done['status'],'failed')
                        self.assertEqual(done['payload']['incomplete_result_id'],'saved-partial')
                        self.assertEqual(done['payload']['error'],'Declared test failure')
                    else:
                        self.assertEqual(done['status'],'completed')
                        result=lab.store.get(done['payload']['result_ids'])
                        self.assertEqual(result['kind'],'complementary_experiment')
                        self.assertEqual(result['payload']['status'],'complete')
                    self.assertEqual(lab.store.usage()['calls'],0)
                finally:
                    lab.release.set()
                    if servers:servers[0].shutdown()
                    worker.join(5)
                    for executor in executors:executor.shutdown(wait=True)
                    self.assertFalse(worker.is_alive())

    def test_component_completion_is_progress_until_result_link_publication(self):
        self.check_boundary(False)

    def test_component_failure_is_progress_until_exception_and_partial_link_publication(self):
        self.check_boundary(True)


if __name__=='__main__':unittest.main()
