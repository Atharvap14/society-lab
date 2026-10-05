"""Bounded tool completion and rate-limit recovery for research roles.

Only explicit HTTP 429 responses are retried. Every attempt remains in the
shared call ledger. Unknown transport errors and successful outputs are never
repeated. The research run loop can transition once from tool use to a forced
final answer. Frozen subject execution code is unchanged. This is not a
guarantee of available provider throughput or a successful final answer.
Provider status, error, incomplete details and usage are archived separately
from the frozen base trace. Explicitly non-completed partial answers cannot be
promoted; unspecified provider causes remain unknown.
"""
import copy
import json
import re
import time
from .harness import ResponsesHarness
from .store import clean, fingerprint


class ResearchResponsesHarness(ResponsesHarness):
    def __init__(self,settings,store,*,max_rate_retries=2,sleeper=time.sleep):
        super().__init__(settings,store)
        if type(max_rate_retries) is not int or not 0<=max_rate_retries<=3:
            raise ValueError('Research rate retries must be an integer from zero to three')
        self.max_rate_retries=max_rate_retries;self.sleeper=sleeper

    def request(self,payload,job_id):
        for attempt in range(self.max_rate_retries+1):
            try:
                response=super().request(payload,job_id)
                metadata=self.response_metadata(response)
                self.store.trace(job_id,{'type':'research_response_metadata',
                    'response_id':metadata['id'],'provider_status':metadata['status'],
                    'attempt_number':attempt+1,'requested_model':payload.get('model'),
                    'request_hash':fingerprint(clean(payload)),'metadata':metadata,
                    'scope':'Reported provider metadata; received HTTP response does not imply a completed research result. Missing reasons remain unknown.'})
                return response
            except RuntimeError as error:
                if not str(error).startswith('OpenAI HTTP 429:') or attempt==self.max_rate_retries:raise
                match=re.search(r'try again in ([0-9.]+)s',str(error),re.I)
                delay=float(match.group(1))+.5 if match else 5*(attempt+1)
                if not 0<delay<=30:raise
                self.store.trace(job_id,{'type':'research_rate_limit_retry','retry_number':attempt+1,'delay_seconds':delay,
                     'scope':'Explicit 429 only; counted attempt, no successful output or subject action repeated.'})
                self.sleeper(delay)

    @staticmethod
    def response_metadata(response):
        """Retain reported fields without guessing the cause of missing output."""
        body=response if isinstance(response,dict) else {}
        metadata={key:body.get(key) for key in ('id','object','created_at','completed_at',
            'status','error','incomplete_details','usage','model','service_tier')}
        raw_output=body.get('output');output=raw_output if isinstance(raw_output,list) else []
        text_chars=sum(len(part['text']) for item in output if isinstance(item,dict)
            and item.get('type')=='message' for part in (item.get('content') or [])
            if isinstance(part,dict) and part.get('type')=='output_text' and isinstance(part.get('text'),str))
        metadata.update(output_count=len(output),
            output_types=[item.get('type') for item in output if isinstance(item,dict)],
            output_text_chars=text_chars,response_structure_type=type(response).__name__,
            output_structure_type=type(raw_output).__name__)
        return clean(metadata)

    def terminal_failure(self,response,job_id,reason):
        metadata=self.response_metadata(response)
        self.store.trace(job_id,{'type':'research_terminal_failure','reason':reason,
            'response_id':metadata['id'],'provider_status':metadata['status'],
            'metadata':metadata,'disposition':'Failed research role; no result promoted',
            'scope':'Partial output remains in model_response traces. Provider reasons are reported as supplied; absent reasons are not inferred. No further completion request.'})
        summary={key:metadata[key] for key in ('id','status','error','incomplete_details',
            'usage','output_count','output_text_chars')}
        detail=json.dumps(summary,ensure_ascii=False,separators=(',',':'))
        if len(detail)>1100:detail=detail[:1100]+' [full metadata retained in trace]'
        return RuntimeError('Research final answer unavailable ('+reason+'); '+detail+
            '. Inspect research_response_metadata trace; unspecified causes remain unknown.')

    def run(self,system,user,tools,job_id,*,schema=None):
        """Bound research tool use, then request one final answer with tools off.

        Schema is copied at each request, after completed retrieval wrappers may
        have refreshed citation enums. A text answer returns immediately. Empty
        tool-enabled output can transition once to a final-only request; it does
        not regenerate an executed action. Transport errors propagate without a
        continuation. Final-only output is never retried by this loop.
        """
        limit=self.settings.max_tool_rounds
        if type(limit) is not int or limit<0:
            raise ValueError('Research max_tool_rounds must be a nonnegative integer')
        items=[{'role':'user','content':json.dumps(clean(user),ensure_ascii=False)}]
        seen=set();completed_rounds=0

        def request(phase,round_number):
            payload={'model':self.settings.model,'instructions':system,
                'input':copy.deepcopy(items),'store':False,
                'max_output_tokens':self.settings.max_output_tokens}
            if tools:
                payload['tools']=[copy.deepcopy(t['definition']) for t in tools.values()]
                payload['parallel_tool_calls']=False
            if phase=='final':payload['tool_choice']='none'
            if schema is not None:
                payload['text']={'format':{'type':'json_schema','name':'research_result',
                    'strict':True,'schema':copy.deepcopy(schema)}}
            # Persist the exact cleaned payload, including the citation schema
            # at this boundary. Authorization headers remain in request() only.
            payload=clean(payload)
            self.store.trace(job_id,{'type':'research_request','phase':phase,
                'tool_round':round_number,'tool_round_limit':limit,
                'input_hash':fingerprint(payload),'payload':payload})
            return self.request(payload,job_id)

        def answer(response):
            text=self.text(response)
            if not text:return None
            if response.get('status') not in (None,'completed'):
                raise self.terminal_failure(response,job_id,
                    'provider explicitly reported a non-completed final answer')
            return json.loads(text) if schema is not None else text

        for round_number in range(limit if tools else 0):
            response=request('tools',round_number)
            completed_rounds=round_number+1
            output=response.get('output',[])
            calls=[item for item in output if item.get('type')=='function_call']
            if not calls:
                text=self.text(response)
                if text:return answer(response)
                items.extend(output)
                self.store.trace(job_id,{'type':'research_final_transition',
                    'reason':'Tool-enabled response contained neither a function call nor a final answer',
                    'response_id':response.get('id'),'provider_status':response.get('status')})
                break
            # Validate IDs before executing any call in this response. IDs are
            # operation identities; reuse must never execute the tool twice.
            ids=[call.get('call_id') for call in calls]
            if any(not isinstance(i,str) or not i for i in ids) or len(ids)!=len(set(ids)) or set(ids)&seen:
                self.store.trace(job_id,{'type':'research_tool_identity_error',
                    'call_ids':ids,'response_id':response.get('id'),
                    'reason':'Missing or duplicated call identity; no tool from this response executed'})
                raise RuntimeError('Research response reused or omitted a function call ID')
            seen.update(ids);items.extend(output)
            for index,call in enumerate(calls):
                name=call.get('name');arguments=None;executed=False
                if index:
                    result={'error':'Only one function call per tool round is permitted; this call was not executed'}
                else:
                    try:
                        arguments=json.loads(call.get('arguments',''))
                        if not isinstance(arguments,dict):raise ValueError('Tool arguments must be a JSON object')
                        if name not in tools:result={'error':'Tool not permitted for this role'}
                        else:
                            executed=True
                            result=tools[name]['execute'](**arguments)
                        # An unserializable tool return becomes one error result;
                        # it must not cause the successful tool to execute again.
                        json.dumps(clean(result),ensure_ascii=False)
                    except Exception as error:
                        result={'error':str(error)[:500],'type':type(error).__name__}
                self.store.trace(job_id,{'type':'tool_call','call_id':call['call_id'],
                    'name':name,'arguments':arguments,'raw_arguments':call.get('arguments'),
                    'executed':executed,'tool_round':round_number,'result':result})
                items.append({'type':'function_call_output','call_id':call['call_id'],
                    'output':json.dumps(clean(result),ensure_ascii=False)})

        items.append({'role':'user','content':'The research tool budget is closed. Return your final answer using the evidence already supplied or retrieved. Do not request further tools. State unresolved limits rather than inventing evidence.'})
        response=request('final',completed_rounds)
        if any(item.get('type')=='function_call' for item in response.get('output',[])):
            self.store.trace(job_id,{'type':'research_final_tool_violation','response_id':response.get('id'),
                'reason':'Function calls returned with tool_choice none; none executed'})
            raise self.terminal_failure(response,job_id,
                'final-only response requested a function call; no tool executed')
        text=self.text(response)
        if not text:
            raise self.terminal_failure(response,job_id,
                'no output_text in the bounded final-only response')
        return answer(response)
