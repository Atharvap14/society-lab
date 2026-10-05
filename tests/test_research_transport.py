import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from swarm_lab.config import Settings
from swarm_lab.harness import ResponsesHarness
from swarm_lab.research_transport import ResearchResponsesHarness
from swarm_lab.store import Store
from swarm_lab.store import fingerprint
from swarm_lab.research import ResearchAgents, object_schema


class ResearchTransportTests(unittest.TestCase):
    def test_explicit_rate_failure_retries_but_does_not_repeat_success(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'lab.sqlite3');delays=[]
            harness=ResearchResponsesHarness(Settings(),store,sleeper=delays.append)
            with patch.object(ResponsesHarness,'request',side_effect=[RuntimeError('OpenAI HTTP 429: Please try again in 3.132s.'),{'ok':True}]) as request:
                self.assertEqual(harness.request({},'job'),{'ok':True})
                self.assertEqual(request.call_count,2)
            self.assertEqual(delays,[3.632])
            traces=[t['payload'] for t in store.traces('job')]
            self.assertEqual([t['type'] for t in traces],['research_rate_limit_retry','research_response_metadata'])
            self.assertEqual(traces[-1]['attempt_number'],2)

    def test_transport_and_non_rate_errors_are_not_repeated(self):
        with tempfile.TemporaryDirectory() as directory:
            harness=ResearchResponsesHarness(Settings(),Store(Path(directory)/'lab.sqlite3'),sleeper=lambda _:self.fail('Unexpected wait'))
            for error in ('OpenAI HTTP 400: Bad schema','OpenAI transport error: TimeoutError','API call budget reached'):
                with patch.object(ResponsesHarness,'request',side_effect=RuntimeError(error)) as request:
                    with self.assertRaises(RuntimeError):harness.request({},'job')
                    self.assertEqual(request.call_count,1)

    def test_rate_failures_are_bounded_and_long_delays_are_not_hidden(self):
        with tempfile.TemporaryDirectory() as directory:
            waits=[];harness=ResearchResponsesHarness(Settings(),Store(Path(directory)/'lab.sqlite3'),sleeper=waits.append)
            with patch.object(ResponsesHarness,'request',side_effect=RuntimeError('OpenAI HTTP 429: rate limit')) as request:
                with self.assertRaises(RuntimeError):harness.request({},'job')
                self.assertEqual(request.call_count,3)
            self.assertEqual(waits,[5,10])
            with patch.object(ResponsesHarness,'request',side_effect=RuntimeError('OpenAI HTTP 429: try again in 61s.')) as request:
                with self.assertRaises(RuntimeError):harness.request({},'job')
                self.assertEqual(request.call_count,1)


def tool_response(call_id,record='m1'):
    return {'id':'response-'+call_id,'output':[{'type':'function_call','call_id':call_id,
        'name':'retrieve','arguments':json.dumps({'record':record})}]}


def final_response(value):
    return {'id':'final-response','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(value)}]}]}


class ResearchToolLoopTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)/'lab.sqlite3')
        self.settings=Settings(max_tool_rounds=2)
        self.harness=ResearchResponsesHarness(self.settings,self.store,sleeper=lambda _:self.fail('Unexpected retry'))
        self.executed=[];self.payloads=[]
        self.schema={'type':'object','properties':{'evidence_ids':{'type':'array','maxItems':0,'items':{'type':'string'}}},
            'required':['evidence_ids'],'additionalProperties':False}
        def execute(record):
            self.executed.append(record)
            field=self.schema['properties']['evidence_ids']
            field['items']={'type':'string','enum':sorted(set(self.executed))};field['maxItems']=10
            return {'id':record,'content':'Retrieved exact content for '+record}
        self.tools={'retrieve':{'definition':{'type':'function','name':'retrieve',
            'parameters':{'type':'object','properties':{'record':{'type':'string'}},
                'required':['record'],'additionalProperties':False}},'execute':execute}}

    def fake(self,responses):
        responses=iter(responses)
        def request(payload,job_id):
            self.payloads.append(copy.deepcopy(payload))
            response=next(responses)
            if isinstance(response,Exception):raise response
            return response
        return patch.object(ResponsesHarness,'request',side_effect=request)

    def run_role(self):
        return self.harness.run('Use only retrieved records.',{'task':'Research'},self.tools,'job',schema=self.schema)

    def test_boundary_tool_calls_then_forced_final_uses_latest_schema_and_exact_trace(self):
        with self.fake([tool_response('call1','m1'),tool_response('call2','m2'),final_response({'evidence_ids':['m1','m2']})]) as request:
            result=self.run_role()
        self.assertEqual(result,{'evidence_ids':['m1','m2']})
        self.assertEqual(self.executed,['m1','m2']);self.assertEqual(request.call_count,3)
        self.assertNotIn('tool_choice',self.payloads[0]);self.assertNotIn('tool_choice',self.payloads[1])
        self.assertEqual(self.payloads[2]['tool_choice'],'none')
        fields=[p['text']['format']['schema']['properties']['evidence_ids'] for p in self.payloads]
        self.assertEqual(fields[0]['maxItems'],0)
        self.assertEqual(fields[1]['items']['enum'],['m1'])
        self.assertEqual(fields[2]['items']['enum'],['m1','m2'])
        outputs=[item for item in self.payloads[2]['input'] if item.get('type')=='function_call_output']
        self.assertEqual([o['call_id'] for o in outputs],['call1','call2'])
        self.assertEqual([json.loads(o['output'])['id'] for o in outputs],['m1','m2'])
        traces=[t['payload'] for t in self.store.traces('job') if t['payload']['type']=='research_request']
        self.assertEqual([t['payload'] for t in traces],self.payloads)
        self.assertEqual([t['phase'] for t in traces],['tools','tools','final'])
        self.assertEqual([t['tool_round'] for t in traces],[0,1,2])
        self.assertTrue(all(t['input_hash']==fingerprint(t['payload']) for t in traces))

    def test_calls_on_final_only_response_are_never_executed_or_retried(self):
        with self.fake([tool_response('call1','m1'),tool_response('call2','m2'),tool_response('forbidden','m3')]) as request:
            with self.assertRaisesRegex(RuntimeError,'final-only response requested'):self.run_role()
        self.assertEqual(self.executed,['m1','m2']);self.assertEqual(request.call_count,3)
        self.assertEqual(self.payloads[-1]['tool_choice'],'none')
        self.assertTrue(any(t['payload']['type']=='research_final_tool_violation' for t in self.store.traces('job')))

    def test_empty_tool_response_transitions_once_to_final_answer(self):
        empty={'id':'reasoning-only','status':'incomplete','output':[{'type':'reasoning','summary':[]}]}
        with self.fake([empty,final_response({'evidence_ids':[]})]) as request:
            self.assertEqual(self.run_role(),{'evidence_ids':[]})
        self.assertEqual(request.call_count,2);self.assertEqual(self.executed,[])
        self.assertEqual(self.payloads[-1]['tool_choice'],'none')
        self.assertIn(empty['output'][0],self.payloads[-1]['input'])

    def test_successful_final_answer_is_returned_without_regeneration(self):
        with self.fake([final_response({'evidence_ids':[]})]) as request:
            self.assertEqual(self.run_role(),{'evidence_ids':[]})
        self.assertEqual(request.call_count,1);self.assertEqual(self.executed,[])

    def test_unknown_transport_failure_after_successful_tool_is_not_repeated(self):
        with self.fake([tool_response('call1'),RuntimeError('OpenAI transport error: TimeoutError')]) as request:
            with self.assertRaisesRegex(RuntimeError,'transport error'):self.run_role()
        self.assertEqual(request.call_count,2);self.assertEqual(self.executed,['m1'])
        self.assertFalse(any(p.get('tool_choice')=='none' for p in self.payloads))

    def test_empty_or_invalid_final_answer_is_not_requested_again(self):
        self.settings.max_tool_rounds=0
        invalid={'id':'invalid','output':[{'type':'message','content':[{'type':'output_text','text':'not JSON'}]}]}
        for response,error in (({'output':[]},RuntimeError),(invalid,json.JSONDecodeError)):
            with self.subTest(error=error),self.fake([response]) as request:
                with self.assertRaises(error):self.run_role()
                self.assertEqual(request.call_count,1)
        self.assertEqual(self.executed,[])

    def test_duplicate_function_identity_never_executes_twice(self):
        with self.fake([tool_response('same','m1'),tool_response('same','m1')]) as request:
            with self.assertRaisesRegex(RuntimeError,'function call ID'):self.run_role()
        self.assertEqual(self.executed,['m1']);self.assertEqual(request.call_count,2)
        self.executed.clear();self.payloads.clear()
        duplicate=tool_response('same','m1');duplicate['output']+=tool_response('same','m2')['output']
        with self.fake([duplicate]) as request:
            with self.assertRaisesRegex(RuntimeError,'function call ID'):self.run_role()
        self.assertEqual(self.executed,[]);self.assertEqual(request.call_count,1)

    def test_unexpected_multiple_calls_get_one_execution_and_explicit_declined_outputs(self):
        self.settings.max_tool_rounds=1
        parallel=tool_response('first','m1');parallel['output']+=tool_response('second','m2')['output']
        with self.fake([parallel,final_response({'evidence_ids':['m1']})]) as request:
            self.assertEqual(self.run_role(),{'evidence_ids':['m1']})
        self.assertEqual(request.call_count,2);self.assertEqual(self.executed,['m1'])
        outputs=[json.loads(i['output']) for i in self.payloads[-1]['input'] if i.get('type')=='function_call_output']
        self.assertEqual(outputs[0]['id'],'m1');self.assertIn('not executed',outputs[1]['error'])
        self.assertEqual(self.payloads[-1]['text']['format']['schema']['properties']['evidence_ids']['items']['enum'],['m1'])

    def test_no_tools_has_one_final_only_request(self):
        with self.fake([final_response({'evidence_ids':[]})]) as request:
            result=self.harness.run('Answer.',{}, {},'job',schema=self.schema)
        self.assertEqual(result,{'evidence_ids':[]});self.assertEqual(request.call_count,1)
        self.assertEqual(self.payloads[0]['tool_choice'],'none')

    def test_final_answer_consumes_existing_call_cap_without_reexecuting_tool(self):
        self.settings.max_calls=1
        response=tool_response('call1','m1');response['usage']={'input_tokens':8,'output_tokens':3}
        with patch.object(Settings,'api_key',return_value='fake-test-key'),patch('urllib.request.urlopen',return_value=io.StringIO(json.dumps(response))) as transport:
            with self.assertRaisesRegex(RuntimeError,'API call budget reached'):self.run_role()
        self.assertEqual(transport.call_count,1);self.assertEqual(self.executed,['m1'])
        self.assertEqual(self.store.usage()['calls'],1);self.assertEqual(self.store.usage()['completed'],1)
        self.assertEqual(self.store.usage()['input_tokens'],8)

    def test_actual_research_retrieval_refreshes_nested_citations_before_forced_final(self):
        self.settings.max_tool_rounds=1
        records=[{'id':i,'content':'Exact source '+i,'room_id':'main','agent_id':'a',
            'created_at':'2026-10-04T10:00:00Z'} for i in ('m1','m2','m3')]
        fact=object_schema({'statement':{'type':'string'},'evidence_ids':{'type':'array','items':{'type':'string'}}})
        schema=object_schema({'observed_facts':{'type':'array','items':fact}})
        call={'id':'read-response','output':[{'type':'function_call','call_id':'read-id',
            'name':'read_evidence','arguments':json.dumps({'ids':['m2']})}]}
        value={'observed_facts':[{'statement':'A retrieved observation.','evidence_ids':['m2']}]}
        agents=ResearchAgents(self.settings,self.store,self.harness)
        with self.fake([call,final_response(value)]) as request:
            result=agents.run('environment-builder',{'evidence':[records[0]]},schema,
                {'messages':records},{},'job')
        self.assertEqual(result,value);self.assertEqual(request.call_count,2)
        citation=lambda p:p['text']['format']['schema']['properties']['observed_facts']['items']['properties']['evidence_ids']['items']['enum']
        self.assertEqual(citation(self.payloads[0]),['m1']);self.assertEqual(citation(self.payloads[1]),['m1','m2'])
        outputs=[json.loads(i['output']) for i in self.payloads[-1]['input'] if i.get('type')=='function_call_output']
        self.assertIn('Exact source m2',json.dumps(outputs));self.assertNotIn('Exact source m3',json.dumps(outputs))
        trace=next(t['payload'] for t in self.store.traces('job') if t['payload']['type']=='research_role')
        self.assertEqual(trace['retrieved_evidence_ids'],['m1','m2'])

    def test_received_empty_incomplete_metadata_is_archived_without_request_retry(self):
        response={'id':'empty-provider','status':'incomplete','output':[],
            'usage':{'input_tokens':0,'output_tokens':0},'error':None,'incomplete_details':None,
            'model':'reported-model'}
        with self.fake([response]) as request:
            self.assertEqual(self.harness.request({'model':'requested-alias'},'job'),response)
        self.assertEqual(request.call_count,1)
        trace=next(t['payload'] for t in self.store.traces('job') if t['payload']['type']=='research_response_metadata')
        self.assertEqual(trace['requested_model'],'requested-alias')
        self.assertEqual(trace['provider_status'],'incomplete');self.assertEqual(trace['metadata']['model'],'reported-model')
        self.assertEqual(trace['metadata']['usage'],{'input_tokens':0,'output_tokens':0})
        self.assertIsNone(trace['metadata']['error']);self.assertIsNone(trace['metadata']['incomplete_details'])
        self.assertEqual(trace['metadata']['output_count'],0)

    def test_two_empty_incomplete_responses_fail_with_reported_metadata_and_no_third_call(self):
        response={'id':'empty-provider','status':'incomplete','output':[],
            'usage':{'input_tokens':0,'output_tokens':0},'error':None,'incomplete_details':None}
        with self.fake([response,response]) as request:
            with self.assertRaises(RuntimeError) as failure:self.run_role()
        self.assertEqual(request.call_count,2);self.assertEqual(self.executed,[])
        message=str(failure.exception)
        self.assertIn('"status":"incomplete"',message);self.assertIn('"input_tokens":0',message)
        self.assertIn('"incomplete_details":null',message);self.assertIn('unspecified causes remain unknown',message)
        self.assertNotIn('max_output_tokens',message);self.assertNotIn('tool loop exhausted',message)
        traces=[t['payload'] for t in self.store.traces('job')]
        self.assertEqual(sum(t['type']=='research_response_metadata' for t in traces),2)
        terminal=next(t for t in traces if t['type']=='research_terminal_failure')
        self.assertEqual(terminal['metadata']['usage']['output_tokens'],0)
        self.assertEqual(self.payloads[-1]['tool_choice'],'none')

    def test_provider_reported_reason_and_error_are_retained_and_sanitized(self):
        self.settings.max_tool_rounds=0
        fake_credential='sk-proj-'+'x'*30
        response={'id':'provider-reason','status':'incomplete','output':[],
            'incomplete_details':{'reason':'max_output_tokens'},
            'error':{'code':'provider_reported_code','message':'Reported detail '+fake_credential},
            'usage':{'input_tokens':20,'output_tokens':6000}}
        with self.fake([response]) as request:
            with self.assertRaises(RuntimeError) as failure:self.run_role()
        self.assertEqual(request.call_count,1)
        self.assertIn('max_output_tokens',str(failure.exception));self.assertIn('provider_reported_code',str(failure.exception))
        self.assertNotIn(fake_credential,str(failure.exception))
        traces=[t['payload'] for t in self.store.traces('job')]
        metadata=next(t['metadata'] for t in traces if t['type']=='research_response_metadata')
        self.assertEqual(metadata['incomplete_details'],{'reason':'max_output_tokens'})
        self.assertEqual(metadata['error']['code'],'provider_reported_code')
        self.assertIn('[REDACTED_CREDENTIAL]',metadata['error']['message'])
        self.assertNotIn(fake_credential,json.dumps(traces))

    def test_parseable_partial_answer_is_archived_but_not_promoted(self):
        self.settings.max_tool_rounds=0
        response=final_response({'evidence_ids':[]})
        response.update(status='incomplete',incomplete_details={'reason':'reported_boundary'},
            error=None,usage={'input_tokens':30,'output_tokens':10},model='reported-model')
        with patch.object(Settings,'api_key',return_value='fake-test-key'),patch('urllib.request.urlopen',return_value=io.StringIO(json.dumps(response))) as transport:
            with self.assertRaisesRegex(RuntimeError,'non-completed final answer'):self.run_role()
        self.assertEqual(transport.call_count,1);self.assertEqual(self.executed,[])
        traces=[t['payload'] for t in self.store.traces('job')]
        original=next(t for t in traces if t['type']=='model_response')
        self.assertEqual(original['output'],response['output'])
        metadata=next(t['metadata'] for t in traces if t['type']=='research_response_metadata')
        self.assertEqual(metadata['status'],'incomplete')
        self.assertEqual(metadata['incomplete_details'],{'reason':'reported_boundary'})
        self.assertGreater(metadata['output_text_chars'],0)
        self.assertTrue(any(t['type']=='research_terminal_failure' for t in traces))
        self.assertEqual(self.store.usage()['calls'],1)

    def test_completed_provider_status_accepts_final_and_missing_legacy_status_remains_explicit(self):
        self.settings.max_tool_rounds=0
        response=final_response({'evidence_ids':[]});response.update(status='completed',error=None,incomplete_details=None)
        for value in (response,final_response({'evidence_ids':[]})):
            with self.subTest(status=value.get('status')),self.fake([value]) as request:
                self.assertEqual(self.run_role(),{'evidence_ids':[]});self.assertEqual(request.call_count,1)
        metadata=[t['payload']['metadata'] for t in self.store.traces('job') if t['payload']['type']=='research_response_metadata']
        self.assertEqual([m['status'] for m in metadata],['completed',None])

    def test_explicit_noncompleted_text_on_first_tool_response_fails_without_a_final_regeneration(self):
        for status in ('incomplete','failed','cancelled','in_progress','queued'):
            response=final_response({'evidence_ids':[]});response.update(status=status,error={'code':'reported_code'})
            with self.subTest(status=status),self.fake([response]) as request:
                with self.assertRaisesRegex(RuntimeError,'non-completed final answer'):self.run_role()
                self.assertEqual(request.call_count,1)
        self.assertEqual(self.executed,[])


if __name__=='__main__':unittest.main()
