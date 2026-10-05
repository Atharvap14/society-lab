"""Real loopback cache integration over isolated authored SQLite registries.

Transparent fixture subclasses only log diagnostics and retain the real server
for graceful shutdown. Routing, queue, cache validation and core stay unchanged.
No production roots, scientific studies or providers are used.
"""
import contextlib
import copy
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

from swarm_lab.config import Settings
from swarm_lab.dataset import normalize_message
from swarm_lab.pipeline import Lab
from swarm_lab.state_inventory_cache import CompactObjectInventoryCache
from swarm_lab.store import fingerprint


ROOT=Path(__file__).resolve().parents[1]
BOOTSTRAP=r'''
import json
from pathlib import Path
import sys
import threading
import time
from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab
from swarm_lab import state_inventory_cache as cache_module
from swarm_lab import server as server_module
root=Path(sys.argv[1]);instances=[]
def log(value):
    with (root/'cache-events.jsonl').open('a',encoding='utf-8') as handle:
        handle.write(json.dumps(value)+'\n')
class LoggedCache(cache_module.CompactObjectInventoryCache):
    def get(self):
        result=super().get()
        log({'event':'get','diagnostics':self.diagnostics,
             'objects':len(result),'contains_payload':any('payload' in row for row in result)})
        return result
    def close(self):
        super().close()
        log({'event':'close','diagnostics':self.diagnostics,
             'connection_closed':self._connection is None,'cache_evicted':self._cache is None})
cache_module.CompactObjectInventoryCache=LoggedCache
server_module.CompactObjectInventoryCache=LoggedCache
class RecordedServer(server_module.LocalResearchServer):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);instances.append(self)
server_module.LocalResearchServer=RecordedServer
def control():
    for line in sys.stdin:
        if line.strip()=='shutdown':
            while not instances:time.sleep(.01)
            instances[0].shutdown();return
threading.Thread(target=control,daemon=True).start()
server_module.serve(Lab(Settings(root=root,max_calls=0)),int(sys.argv[2]))
'''


def pin(obj):return {key:obj[key] for key in ('id','version','hash')}


class ActualCachedServer:
    def __init__(self,root):
        self.root=root
        with socket.socket() as handle:
            handle.bind(('127.0.0.1',0));port=handle.getsockname()[1]
        self.base=f'http://127.0.0.1:{port}'
        self.process=subprocess.Popen([sys.executable,'-c',BOOTSTRAP,str(root),str(port)],
            cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        deadline=time.monotonic()+15
        try:
            while True:
                if self.process.poll() is not None:raise AssertionError('Isolated server exited at startup')
                try:self.state=self.get('/api/state');break
                except urllib.error.URLError:
                    if time.monotonic()>deadline:raise
                    time.sleep(.03)
        except BaseException:self.close();raise

    def close(self):
        if self.process.poll() is None:
            try:
                self.process.stdin.write(b'shutdown\n');self.process.stdin.flush()
                self.process.wait(timeout=8)
            except (OSError,subprocess.TimeoutExpired):
                self.process.terminate();self.process.wait(timeout=5)
        if self.process.stdin:self.process.stdin.close()

    def get(self,path):
        with urllib.request.urlopen(self.base+path,timeout=5) as response:return json.load(response)

    def events(self):
        path=self.root/'cache-events.jsonl'
        return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]

    def latest_get(self):return next(row for row in reversed(self.events()) if row['event']=='get')

    def submit(self,action,args):
        request=urllib.request.Request(self.base+'/api/jobs',
            data=json.dumps({'action':action,'args':args}).encode(),
            headers={'Content-Type':'application/json','X-Lab-Token':self.state['csrf']})
        with urllib.request.urlopen(request,timeout=5) as response:
            if response.status!=202:raise AssertionError('No queued response')
            identity=json.load(response)['job_id']
        deadline=time.monotonic()+12
        while time.monotonic()<deadline:
            value=next(row for row in self.get('/api/state')['jobs'] if row['id']==identity)
            if value['status'] in ('completed','failed'):return value
            time.sleep(.03)
        raise AssertionError('Temporary local job never completed')


class StateInventoryInterfaceTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.lab=Lab(Settings(root=self.root,max_calls=0))
        messages=[normalize_message({'id':f'fixture-message-{i}','agent_speaker_id':'fixture-agent',
            'speaker_type':'agent','agent_name':'Fixture Agent','room_id':'fixture-room',
            'created_at':f'2025-04-22T18:{i:02d}:00Z',
            'content':'Waiting for the artifact.' if i%2 else 'Ordinary planned work.',
            'source':{'file':'authored-cache-fixture.jsonl','line':i+1,'table':'chat_messages'}})
            for i in range(8)]
        self.dataset=self.lab.store.put('dataset',{'name':'Authored fixture','messages':messages,
            'raw_not_in_inventory':'PAYLOAD_SENTINEL_NOT_FOR_INVENTORY'*2000},'fixture-dataset')
        self.behavior=self.lab.store.put('behavior',{'name':'Untested fixture','status':'candidate'},'fixture-behavior')

    def server(self):
        value=ActualCachedServer(self.root);self.addCleanup(value.close);return value

    def assert_no_providers(self):
        with self.lab.store.connect() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM traces').fetchone()[0],0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM calls WHERE status='completed'").fetchone()[0],0)
        self.assertEqual(self.lab.store.get(self.behavior['id'],1),self.behavior)
        self.assertFalse((self.root/'.runtime/runs').exists())

    def test_hot_state_keeps_compact_alias_free_inventory_without_another_payload_fetch(self):
        server=self.server();first=server.get('/api/state');before=server.latest_get()
        self.assertFalse(before['contains_payload'])
        self.assertTrue(all('payload' not in row for row in first['objects']))
        self.assertNotIn('PAYLOAD_SENTINEL_NOT_FOR_INVENTORY',json.dumps(first))
        first['objects'][0]['summary']['name']='Client-side mutation'
        second=server.get('/api/state');after=server.latest_get()
        self.assertEqual(after['diagnostics']['payload_fetches'],before['diagnostics']['payload_fetches'])
        self.assertGreater(after['diagnostics']['hits'],before['diagnostics']['hits'])
        self.assertNotIn('Client-side mutation',json.dumps(second['objects']))
        self.assertEqual(second['usage']['calls'],0)
        self.assert_no_providers()

    def test_jobs_and_usage_remain_fresh_despite_inventory_cache(self):
        server=self.server();server.get('/api/state')
        self.lab.store.job('external-fixture-job','running',{'action':'fixture-only','progress':1})
        # This is an explicit test-only reservation, never a provider invocation;
        # the running server itself retains the zero-call paid execution cap.
        reservation=self.lab.store.reserve_call(1)
        state=server.get('/api/state')
        self.assertEqual(state['max_calls'],0)
        self.assertEqual(state['usage']['calls'],1)
        self.assertEqual(next(row for row in state['jobs'] if row['id']=='external-fixture-job')['status'],'running')
        self.lab.store.finish_call(reservation,'failed',{'input_tokens':0,'output_tokens':0})
        self.lab.store.job('external-fixture-job','completed',{'action':'fixture-only','progress':2})
        state=server.get('/api/state')
        self.assertEqual(state['usage']['calls'],1)
        self.assertEqual(state['usage']['completed'],0)
        job=next(row for row in state['jobs'] if row['id']=='external-fixture-job')
        self.assertEqual(job['status'],'completed');self.assertEqual(job['payload']['progress'],2)
        before=server.latest_get()['diagnostics']['payload_fetches']
        server.get('/api/state')
        self.assertEqual(server.latest_get()['diagnostics']['payload_fetches'],before)
        self.assert_no_providers()

    def test_exact_object_is_uncached_and_rejects_same_hash_body_change_after_warm_state(self):
        server=self.server();server.get('/api/state');before_events=copy.deepcopy(server.events())
        exact=server.get('/api/object/fixture-dataset?version=1')
        self.assertEqual(exact,self.dataset)
        self.assertIn('raw_not_in_inventory',exact['payload'])
        self.assertEqual(server.events(),before_events)
        changed=copy.deepcopy(self.dataset['payload']);changed['name']='Unsealed tampered body'
        with contextlib.closing(sqlite3.connect(self.lab.store.path)) as connection:
            with connection:
                connection.execute('UPDATE objects SET payload=? WHERE id=? AND version=?',
                    (json.dumps(changed),self.dataset['id'],1))
        with self.assertRaises(urllib.error.HTTPError) as error:
            server.get('/api/object/fixture-dataset?version=1')
        self.assertEqual(error.exception.code,400)
        self.assertEqual(server.events(),before_events)
        with self.assertRaises(urllib.error.HTTPError) as error:server.get('/api/state')
        self.assertEqual(error.exception.code,400)
        # Repair is a newly hashed temporary input, not a favorable old fallback.
        with contextlib.closing(sqlite3.connect(self.lab.store.path)) as connection:
            with connection:
                connection.execute('UPDATE objects SET hash=? WHERE id=? AND version=?',
                    (fingerprint(changed),self.dataset['id'],1))
        state=server.get('/api/state')
        obj=next(row for row in state['objects'] if row['id']==self.dataset['id'])
        self.assertEqual(obj['summary']['name'],'Unsealed tampered body')
        self.assertEqual(obj['hash'],fingerprint(changed))
        self.assert_no_providers()

    def test_measurement_queue_result_refs_become_visible_then_inventory_warms(self):
        server=self.server();server.get('/api/state')
        job=server.submit('create_measurement_sample',{'dataset_ref':pin(self.dataset),
            'question':'Is an explicit wait reported?',
            'positive_definition':'The author explicitly reports waiting.',
            'negative_definition':'No explicit wait report appears.',
            'sample_size':4,'seed':42,'detector_id':'blocker_report','context_neighbors':1})
        self.assertEqual(job['status'],'completed',job)
        identity=job['payload']['result_ids'];sample=self.lab.store.get(identity,1)
        state=server.get('/api/state');entries={row['id']:row for row in state['objects']}
        self.assertEqual({key:entries[identity][key] for key in ('id','version','hash')},pin(sample))
        review=self.lab.store.get(sample['payload']['review_id'],1)
        self.assertEqual({key:entries[review['id']][key] for key in ('id','version','hash')},pin(review))
        self.assertEqual(next(row for row in state['jobs'] if row['id']==job['id'])['payload']['result_ids'],identity)
        self.assertTrue(all('payload' not in row for row in entries.values()))
        before=server.latest_get()['diagnostics']['payload_fetches'];server.get('/api/state')
        self.assertEqual(server.latest_get()['diagnostics']['payload_fetches'],before)
        self.assertEqual(self.lab.store.usage()['calls'],0)
        self.assert_no_providers()

    def test_graceful_public_server_shutdown_closes_the_observer_and_evicts_summaries(self):
        server=self.server();server.get('/api/state')
        self.assertTrue(any(row['event']=='get' for row in server.events()))
        server.close()
        self.assertEqual(server.process.returncode,0)
        closed=[row for row in server.events() if row['event']=='close']
        self.assertGreaterEqual(len(closed),1)
        self.assertTrue(all(row['connection_closed'] for row in closed))
        self.assertTrue(all(row['cache_evicted'] for row in closed))
        self.assert_no_providers()


if __name__=='__main__':unittest.main()
