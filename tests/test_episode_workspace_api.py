"""Actual loopback GET routing must remain exact, read-only, and unqueued."""
import concurrent.futures
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
from swarm_lab.episode_workspace import parse_episode_query
from swarm_lab.pipeline import Lab
from swarm_lab.server import LocalResearchServer, serve


class EpisodeQueryTests(unittest.TestCase):
    def test_canonical_versions_and_no_duplicate_extra_or_partial_behavior(self):
        base={'selected_audit_id':['selected-a'], 'selected_audit_version':['1'],
              'temporal_audit_id':['temporal-a'], 'temporal_audit_version':['1000'],
              'lead_id':['graph-lead-a']}
        self.assertEqual(parse_episode_query(base)['temporal_audit_version'],1000)
        for value in ('', '01', '1.0', '-1', '0', 'true', '1000000001'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_episode_query(base | {'selected_audit_version':[value]})
        for changed in ({'lead_id':['a','b']}, {'other':['x']}, {'behavior_id':['b']},
                        {'behavior_version':['1']}, {'lead_id':['../outside']}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                parse_episode_query(base | changed)

    def test_real_http_get_never_queues_or_calls_a_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            lab=Lab(Settings(root=Path(directory)))
            lab.harness=lambda *_: self.fail('A read-only episode route invoked a provider')
            before={'jobs':lab.store.jobs(),'objects':lab.store.list(),'usage':lab.store.usage()}
            with socket.socket() as handle:
                handle.bind(('127.0.0.1',0));port=handle.getsockname()[1]
            servers=[];executors=[]
            def capture_server(*args,**kwargs):
                value=LocalResearchServer(*args,**kwargs);servers.append(value);return value
            executor_type=concurrent.futures.ThreadPoolExecutor
            def capture_pool(*args,**kwargs):
                value=executor_type(*args,**kwargs);executors.append(value);return value
            def packet(store,**kwargs):
                self.assertIs(store,lab.store)
                return {'available':True,'exact_arguments':kwargs,'model_calls':0,'database_writes':0}
            with patch('swarm_lab.server.LocalResearchServer',side_effect=capture_server), \
                 patch('swarm_lab.server.concurrent.futures.ThreadPoolExecutor',side_effect=capture_pool), \
                 patch('swarm_lab.episode_workspace.episode_workspace_packet',side_effect=packet) as provider:
                worker=threading.Thread(target=serve,args=(lab,port),daemon=True);worker.start()
                base=f'http://127.0.0.1:{port}/api/episode-workspace?'
                query=urllib.parse.urlencode({'selected_audit_id':'selected-a','selected_audit_version':'1',
                    'temporal_audit_id':'temporal-a','temporal_audit_version':'1000','lead_id':'graph-lead-a'})
                try:
                    deadline=time.monotonic()+5
                    while True:
                        try:
                            with urllib.request.urlopen(base+query,timeout=3) as response:
                                result=json.load(response)
                            break
                        except urllib.error.URLError:
                            if time.monotonic()>deadline:raise
                            time.sleep(.02)
                    self.assertEqual(result['exact_arguments']['temporal_audit_version'],1000)
                    self.assertEqual(provider.call_count,1)
                    for tail in ('&lead_id=duplicate','&other=1','&behavior_id=',
                                 '&selected_audit_version=1','&behavior_version=1'):
                        with self.subTest(tail=tail), self.assertRaises(urllib.error.HTTPError) as error:
                            urllib.request.urlopen(base+query+tail,timeout=3)
                        self.assertEqual(error.exception.code,400)
                    self.assertEqual(provider.call_count,1)
                    self.assertEqual({'jobs':lab.store.jobs(),'objects':lab.store.list(),'usage':lab.store.usage()},before)
                finally:
                    for server in servers:server.shutdown()
                    worker.join(5)
                    for executor in executors:executor.shutdown(wait=True,cancel_futures=True)
                    self.assertFalse(worker.is_alive())
