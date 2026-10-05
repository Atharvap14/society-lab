"""Real public measurement workflow over temporary authored registry rows.

The loopback process and CLI call actual Lab/core methods. No providers, raw
dataset files, production SQLite, library promotion or scientific studies are
used; only declared sample judgments are written to isolated temporary roots.
"""
import contextlib
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from unittest.mock import patch

from swarm_lab import cli
from swarm_lab.config import Settings
from swarm_lab.dataset import normalize_message
from swarm_lab.measurement_review_workflow import parse_review_query, read_review_plan, MAX_PLAN_BYTES
from swarm_lab.pipeline import Lab


ROOT = Path(__file__).resolve().parents[1]

BOOTSTRAP = r'''
import json
from pathlib import Path
import sys
from swarm_lab.config import Settings
from swarm_lab.pipeline import Lab
from swarm_lab.server import serve
from swarm_lab.store import Store
root=Path(sys.argv[1])
class RecordedStore(Store):
    def job(self, identity, status, payload):
        with (root/'job-publications.jsonl').open('a',encoding='utf-8') as handle:
            handle.write(json.dumps({'id':identity,'status':status,'payload':payload})+'\n')
        return super().job(identity,status,payload)
lab=Lab(Settings(root=root,max_calls=0))
lab.store=RecordedStore(lab.settings.runtime/'lab.sqlite3')
serve(lab,int(sys.argv[2]))
'''


def pin(row):
    return {key: row[key] for key in ('id','version','hash')}


def authored_dataset(lab):
    messages=[normalize_message({'id':f'fixture-message-{index:02d}',
        'speaker_type':'agent' if index%2 else 'user',
        'agent_speaker_id':'fixture-agent' if index%2 else None,
        'user_speaker_id':None if index%2 else 'fixture-user',
        'agent_name':'Fixture Agent' if index%2 else 'Fixture User',
        'room_id':'fixture-room-a' if index<7 else 'fixture-room-b',
        'created_at':f'2025-04-22T18:{index:02d}:00Z',
        'content':'I am waiting for a named draft.' if index%3==0 else 'Ordinary planned work.',
        'source':{'file':'authored-local-fixture.jsonl','line':index+1,'table':'chat_messages'}})
        for index in range(10)]
    return lab.store.put('dataset',{'messages':messages,'scope':'Temporary authored rows only.'},'fixture-dataset')


def sample_plan(dataset):
    return {'dataset_ref':pin(dataset),'question':'Does this message explicitly report waiting?',
        'positive_definition':'The author explicitly reports waiting on a named dependency.',
        'negative_definition':'No such explicit reported act appears in this message.',
        'exclusions':['Reported waiting does not establish actual inactivity.'],
        'sample_size':4,'seed':173,'detector_id':'blocker_report','context_neighbors':1}


def judgment_plan(sample, message_id, *, version=1, label='uncertain', mode='agent_assisted'):
    return {'sample_ref':pin(sample),'message_id':message_id,'label':label,
        'reason':'Declared fixture annotation; not a human calibration reference.',
        'reviewer_id':'fixture-reviewer','reviewer_mode':mode,
        'expected_review_version':version,'predictions_visible':False}


def protected_state(lab):
    with lab.store.connect() as connection:
        provider_rows={table:[tuple(row) for row in connection.execute(f'SELECT * FROM {table} ORDER BY id')]
                       for table in ('calls','traces')}
        library_rows=[tuple(row) for row in connection.execute(
            "SELECT * FROM objects WHERE kind IN ('behavior','theory','replication') ORDER BY id,version")]
    return {'usage':lab.store.usage(),'provider_rows':provider_rows,'library_rows':library_rows}


class Loopback:
    def __init__(self, root):
        self.root=root
        with socket.socket() as handle:
            handle.bind(('127.0.0.1',0)); port=handle.getsockname()[1]
        self.base=f'http://127.0.0.1:{port}'
        self.process=subprocess.Popen([sys.executable,'-c',BOOTSTRAP,str(root),str(port)],
            cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        deadline=time.monotonic()+15
        try:
            while True:
                if self.process.poll() is not None:
                    raise AssertionError('Temporary loopback server exited at startup')
                try:
                    self.state=self.get('/api/state');break
                except urllib.error.URLError:
                    if time.monotonic()>deadline:raise
                    time.sleep(.03)
        except BaseException:
            self.close();raise

    def close(self):
        if self.process.poll() is None:self.process.terminate()
        self.process.wait(timeout=10)

    def get(self,path):
        with urllib.request.urlopen(self.base+path,timeout=5) as response:
            return json.load(response)

    def post_raw(self,raw,*,token=True):
        headers={'Content-Type':'application/json'}
        if token:headers['X-Lab-Token']=self.state['csrf']
        request=urllib.request.Request(self.base+'/api/jobs',data=raw,headers=headers)
        with urllib.request.urlopen(request,timeout=5) as response:
            return response.status,json.load(response)

    def submit(self,action,args):
        status,result=self.post_raw(json.dumps({'action':action,'args':args}).encode())
        if status!=202:raise AssertionError('Job was not queued')
        identity=result['job_id'];deadline=time.monotonic()+12
        while time.monotonic()<deadline:
            job=next(row for row in self.get('/api/state')['jobs'] if row['id']==identity)
            if job['status'] in ('completed','failed'):return job
            time.sleep(.03)
        raise AssertionError('Temporary zero-call job did not reach terminal status')

    def review(self,sample,version=1,*,shown=False,extra=''):
        query=urllib.parse.urlencode({'sample_id':sample['id'],'sample_version':sample['version'],
            'review_id':sample['payload']['review_id'],'review_version':version,
            'include_predictions':'true' if shown else 'false'})
        return self.get('/api/measurement-review?'+query+extra)

    def publications(self,identity):
        path=self.root/'job-publications.jsonl'
        return [row for row in map(json.loads,path.read_text(encoding='utf-8').splitlines()) if row['id']==identity]


class MeasurementReviewInterfaceTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.lab=Lab(Settings(root=self.root,max_calls=0))
        self.dataset=authored_dataset(self.lab)
        self.lab.store.put('behavior',{'name':'Existing untested fixture','status':'candidate'},'fixture-behavior')
        self.protected_before=protected_state(self.lab)

    def server(self):
        server=Loopback(self.root);self.addCleanup(server.close);return server

    def sample_from_job(self,job):
        self.assertEqual(job['status'],'completed',job)
        identity=job['payload']['result_ids']
        self.assertIsInstance(identity,str)
        return self.lab.store.get(identity,1)

    def assert_single_terminal(self,server,job):
        publications=server.publications(job['id'])
        self.assertEqual([row['status'] for row in publications],['queued','running',job['status']])
        self.assertEqual(sum(row['status'] in ('completed','failed') for row in publications),1)

    def assert_protected(self):
        self.assertEqual(protected_state(self.lab),self.protected_before)
        self.assertEqual(self.lab.store.usage()['calls'],0)
        self.assertFalse((self.root/'.runtime/runs').exists())

    def cli_call(self,*argv):
        # --runtime alone still initializes the default Lab root. Replace only
        # that constructor's destination; all public methods/core remain real.
        def isolated_factory(settings):
            return Lab(Settings(root=self.root,model=settings.model,max_calls=settings.max_calls))
        with patch('swarm_lab.cli.Lab',side_effect=isolated_factory), \
             contextlib.redirect_stdout(io.StringIO()) as stream:
            cli.main(['--runtime',str(self.root/'.runtime'),'--max-calls','0',*argv])
        return json.loads(stream.getvalue())

    def plan_file(self,name,plan):
        path=self.root/name;path.write_text(json.dumps(plan),encoding='utf-8');return path

    def test_loopback_freeze_declared_judgment_exact_historical_get_and_stale_cas(self):
        server=self.server()
        self.assertEqual(server.state['max_calls'],0)
        self.assertIn('create_measurement_sample',server.state['supported_actions'])
        create=server.submit('create_measurement_sample',sample_plan(self.dataset))
        sample=self.sample_from_job(create);self.assert_single_terminal(server,create)
        hidden=server.review(sample)
        self.assertTrue(all(item['prediction'] is None for item in hidden['packet']['items']))
        self.assertEqual(hidden['report']['totals']['missing_labels'],4)
        self.assertIsNone(hidden['report']['metrics']['agreement'])
        identity=hidden['packet']['items'][0]['message_id']
        judgment=server.submit('record_measurement_judgment',judgment_plan(sample,identity))
        self.assertEqual(judgment['status'],'completed',judgment)
        self.assert_single_terminal(server,judgment)
        current=self.lab.store.get(sample['payload']['review_id'],2)
        self.assertEqual(len(current['payload']['judgments']),1)
        before_get={'jobs':self.lab.store.jobs(),'sample_history':self.lab.store.history(sample['id']),
                    'review_history':self.lab.store.history(current['id'])}
        shown=server.review(sample,2,shown=True)
        old=server.review(sample,1)
        self.assertEqual(shown['packet']['review_ref'],pin(current))
        self.assertTrue(all(item['prediction']['available'] for item in shown['packet']['items']))
        self.assertEqual(shown['report']['totals']['uncertain_labels'],1)
        self.assertEqual(shown['report']['totals']['known_labels'],0)
        self.assertEqual(shown['report']['totals']['compared_messages'],0)
        self.assertFalse(shown['report']['calibration_established'])
        self.assertEqual(old,hidden)
        self.assertEqual({'jobs':self.lab.store.jobs(),'sample_history':self.lab.store.history(sample['id']),
                         'review_history':self.lab.store.history(current['id'])},before_get)
        stale=server.submit('record_measurement_judgment',judgment_plan(sample,identity,label='no'))
        self.assertEqual(stale['status'],'failed',stale)
        self.assert_single_terminal(server,stale)
        self.assertNotIn('result_ids',stale['payload'])
        self.assertEqual(self.lab.store.get(current['id']),current)
        self.assert_protected()

    def test_loopback_rejects_duplicate_blank_extra_and_noncanonical_query_without_queueing(self):
        server=self.server();sample=self.sample_from_job(server.submit('create_measurement_sample',sample_plan(self.dataset)))
        before={'jobs':self.lab.store.jobs(),'review':self.lab.store.get(sample['payload']['review_id'])}
        query=urllib.parse.urlencode({'sample_id':sample['id'],'sample_version':'1',
            'review_id':sample['payload']['review_id'],'review_version':'1'})
        invalid=(query+'&review_version=1',query+'&include_predictions=',query+'&extra=x',
                 query.replace('sample_version=1','sample_version=01'),
                 query.replace('sample_version=1','sample_version=1.0'),
                 query.replace('review_version=1','review_version=true'),
                 query.replace('sample_id='+sample['id'],'sample_id='),
                 query.rsplit('&review_version=1',1)[0],
                 query+'&include_predictions=true&include_predictions=false')
        for text in invalid:
            with self.subTest(query=text),self.assertRaises(urllib.error.HTTPError) as error:
                server.get('/api/measurement-review?'+text)
            self.assertEqual(error.exception.code,400)
        self.assertEqual({'jobs':self.lab.store.jobs(),'review':self.lab.store.get(sample['payload']['review_id'])},before)
        self.assert_protected()

    def test_loopback_bad_envelopes_fail_before_job_and_bad_typed_plan_has_only_failed_job(self):
        server=self.server();before=self.lab.store.jobs()
        invalid=(b'{"action":"create_measurement_sample","action":"record_measurement_judgment","args":{}}',
            b'{"action":"create_measurement_sample","args":{},"extra":1}',
            b'{"action":"create_measurement_sample","args":{"seed":NaN}}',
            b'{"action":"create_measurement_sample","args":{"seed":1e400}}',
            b'{"action":"create_measurement_sample","args":{"seed":1,"seed":2}}',
            b'x'*64001)
        for raw in invalid:
            with self.subTest(raw=raw[:80]),self.assertRaises(urllib.error.HTTPError) as error:
                server.post_raw(raw)
            self.assertEqual(error.exception.code,400)
        with self.assertRaises(urllib.error.HTTPError) as error:
            server.post_raw(b'{"action":"create_measurement_sample","args":{}}',token=False)
        self.assertEqual(error.exception.code,403)
        self.assertEqual(self.lab.store.jobs(),before)
        for changes in ({'sample_size':True},{'seed':173.0},{'question':''},{'extra':'unknown'},
                        {'dataset_ref':{**pin(self.dataset),'version':True}}):
            job=server.submit('create_measurement_sample',sample_plan(self.dataset)|changes)
            self.assertEqual(job['status'],'failed',job)
            self.assertNotIn('result_ids',job['payload'])
            self.assert_single_terminal(server,job)
        self.assertEqual(self.lab.store.list('measurement_sample'),[])
        self.assertEqual(self.lab.store.list('measurement_review'),[])
        self.assert_protected()

    def test_loopback_cross_sample_binding_and_invalid_judgments_preserve_accepted_event(self):
        server=self.server()
        sample=self.sample_from_job(server.submit('create_measurement_sample',sample_plan(self.dataset)))
        other=self.sample_from_job(server.submit('create_measurement_sample',sample_plan(self.dataset)|{'seed':174}))
        identity=sample['payload']['design']['draw_order'][0]
        accepted=server.submit('record_measurement_judgment',judgment_plan(sample,identity,label='yes'))
        self.assertEqual(accepted['status'],'completed',accepted)
        review=self.lab.store.get(sample['payload']['review_id'],2)
        wrong=urllib.parse.urlencode({'sample_id':sample['id'],'sample_version':'1',
            'review_id':other['payload']['review_id'],'review_version':'1'})
        before_jobs=self.lab.store.jobs()
        with self.assertRaises(urllib.error.HTTPError) as error:
            server.get('/api/measurement-review?'+wrong)
        self.assertEqual(error.exception.code,400)
        self.assertEqual(self.lab.store.jobs(),before_jobs)
        base=judgment_plan(sample,identity,version=2,label='no')
        for changes in ({'expected_review_version':True},{'expected_review_version':2.0},
                        {'label':'missing'},{'label':False},{'reviewer_mode':'verified_human'},
                        {'predictions_visible':1},{'extra':'unknown'},
                        {'sample_ref':{**pin(sample),'hash':'0'*64}}):
            job=server.submit('record_measurement_judgment',base|changes)
            self.assertEqual(job['status'],'failed',job)
            self.assert_single_terminal(server,job)
            self.assertNotIn('result_ids',job['payload'])
            self.assertEqual(self.lab.store.get(review['id']),review)
        self.assertEqual(len(self.lab.store.history(review['id'])),2)
        self.assert_protected()

    def test_cli_plan_create_judge_and_exact_old_show_remain_local_and_zero_call(self):
        create_plan=self.plan_file('create.json',sample_plan(self.dataset))
        created=self.cli_call('create-measurement-sample','--plan',str(create_plan))
        self.assertEqual(created['kind'],'measurement_sample')
        sample=self.lab.store.get(created['id'],created['version'])
        self.assertEqual(pin(sample),{key:created[key] for key in ('id','version','hash')})
        identity=sample['payload']['design']['draw_order'][0]
        path=self.plan_file('judge.json',judgment_plan(sample,identity,label='no',mode='synthetic_fixture'))
        recorded=self.cli_call('record-measurement-judgment','--plan',str(path))
        self.assertEqual(recorded['version'],2)
        arguments=('show-measurement-review',sample['id'],'--sample-version','1',
                   '--review-id',sample['payload']['review_id'],'--review-version')
        before={'jobs':self.lab.store.jobs(),'reviews':self.lab.store.history(recorded['id'])}
        old=self.cli_call(*arguments,'1')
        current=self.cli_call(*arguments,'2','--show-predictions')
        self.assertEqual(old['report']['totals']['known_labels'],0)
        self.assertEqual(old['report']['totals']['missing_labels'],4)
        self.assertEqual(current['report']['totals']['known_labels'],1)
        self.assertEqual(current['report']['current_labels_by_mode']['synthetic_fixture']['no'],1)
        self.assertTrue(all(item['prediction'] is None for item in old['packet']['items']))
        self.assertTrue(current['packet']['predictions_included'])
        self.assertEqual(current['packet']['review_ref']['version'],2)
        with self.assertRaises(ValueError):
            self.cli_call('record-measurement-judgment','--plan',str(path))
        self.assertEqual({'jobs':self.lab.store.jobs(),'reviews':self.lab.store.history(recorded['id'])},before)
        self.assert_protected()

    def test_cli_plan_duplicate_extra_nonfinite_size_and_typed_versions_fail_without_artifacts(self):
        raw_plans=['{"dataset_ref":{},"dataset_ref":{}}','{"seed":NaN}',
                   '{"seed":Infinity}','{"seed":1e400}','[]','{}'+' '*(MAX_PLAN_BYTES+1)]
        for index,raw in enumerate(raw_plans):
            path=self.root/f'bad-{index}.json';path.write_text(raw,encoding='utf-8')
            with self.subTest(index=index),self.assertRaises(ValueError):
                self.cli_call('create-measurement-sample','--plan',str(path))
        for index,changes in enumerate(({'extra':'unknown'},{'question':''},
                {'dataset_ref':{**pin(self.dataset),'version':1.0}},
                {'dataset_ref':{**pin(self.dataset),'version':'01'}})):
            path=self.plan_file(f'bad-typed-{index}.json',sample_plan(self.dataset)|changes)
            with self.subTest(changes=changes),self.assertRaises((TypeError,ValueError)):
                self.cli_call('create-measurement-sample','--plan',str(path))
        self.assertEqual(self.lab.store.list('measurement_sample'),[])
        self.assertEqual(self.lab.store.jobs(),[])
        self.assert_protected()

    def test_reader_and_query_contract_reject_cross_format_ambiguity(self):
        valid={'sample_id':['sample-a'],'sample_version':['1'],'review_id':['review-a'],'review_version':['2']}
        parsed=parse_review_query(valid)
        self.assertEqual(parsed['review_version'],2)
        self.assertFalse(parsed['include_predictions'])
        for changes in ({'review_id':['a','b']},{'sample_version':['01']},{'sample_version':['1.0']},
                {'sample_version':['0']},{'sample_version':['1000000001']},{'review_version':[True]},
                {'sample_id':['../outside']},{'include_predictions':['TRUE']},{'extra':['x']}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                parse_review_query(valid|changes)
        for name,raw in (('duplicate-nested.json','{"dataset_ref":{"version":1,"version":2}}'),
                         ('nonfinite-nested.json','{"dataset_ref":{"version":1e999}}'),
                         ('invalid-utf8.json',None)):
            path=self.root/name
            if raw is None:path.write_bytes(b'\xff')
            else:path.write_text(raw,encoding='utf-8')
            with self.subTest(name=name),self.assertRaises(ValueError):read_review_plan(path)


if __name__=='__main__':unittest.main()
