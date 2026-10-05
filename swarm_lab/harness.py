"""Bounded Responses tool loop and a read-only Codex CLI adapter."""
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from .store import clean, fingerprint

class ResponsesHarness:
    name='responses'
    def __init__(self,settings,store):self.settings,self.store=settings,store

    def request(self,payload,job_id):
        call_id=self.store.reserve_call(self.settings.max_calls)
        payload=clean(payload)
        # API key is only placed in the outbound Authorization header, never traces.
        req=urllib.request.Request('https://api.openai.com/v1/responses',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+self.settings.api_key(),'Content-Type':'application/json'})
        started=time.monotonic()
        try:
            with urllib.request.urlopen(req,timeout=180) as r:response=json.load(r)
        except urllib.error.HTTPError as e:
            try:detail=json.loads(e.read()).get('error',{}).get('message','API request failed')
            except Exception:detail='API request failed'
            self.store.finish_call(call_id,'failed')
            self.store.trace(job_id,{'type':'api_error','status':e.code,'detail':detail})
            raise RuntimeError(f'OpenAI HTTP {e.code}: {clean(detail)}') from None
        except Exception as e:
            self.store.finish_call(call_id,'failed')
            raise RuntimeError(f'OpenAI transport error: {type(e).__name__}') from None
        self.store.finish_call(call_id,'completed',response.get('usage',{}))
        self.store.trace(job_id,{'type':'model_response','response_id':response.get('id'),'model':response.get('model'),'usage':response.get('usage',{}),'seconds':round(time.monotonic()-started,3),'input_hash':fingerprint(payload),'output':response.get('output',[])})
        return response

    @staticmethod
    def text(response):
        return '\n'.join(part['text'] for item in response.get('output',[]) if item.get('type')=='message' for part in item.get('content',[]) if part.get('type')=='output_text')

    def run(self,system,user,tools,job_id,*,schema=None):
        items=[{'role':'user','content':json.dumps(clean(user),ensure_ascii=False)}]
        for step in range(self.settings.max_tool_rounds+1):
            payload={'model':self.settings.model,'instructions':system,'input':items,'store':False,'max_output_tokens':self.settings.max_output_tokens}
            if tools:
                payload['tools']=[t['definition'] for t in tools.values()]
                payload['parallel_tool_calls']=False
                if step==self.settings.max_tool_rounds:payload['tool_choice']='none'
            if schema:payload['text']={'format':{'type':'json_schema','name':'research_result','strict':True,'schema':schema}}
            response=self.request(payload,job_id)
            calls=[x for x in response.get('output',[]) if x.get('type')=='function_call']
            if not calls:
                text=self.text(response)
                if not text:raise RuntimeError('Model returned no final answer; increase max_output_tokens or inspect trace')
                return json.loads(text) if schema else text
            items.extend(response['output'])
            for call in calls:
                name=call['name']
                if name not in tools:result={'error':'Tool not permitted for this role'}
                else:
                    try:result=tools[name]['execute'](**json.loads(call['arguments']))
                    except Exception as e:result={'error':str(e)[:500],'type':type(e).__name__}
                self.store.trace(job_id,{'type':'tool_call','name':name,'arguments':json.loads(call['arguments']),'result':result})
                items.append({'type':'function_call_output','call_id':call['call_id'],'output':json.dumps(clean(result),ensure_ascii=False)})
        raise RuntimeError('Research tool loop exhausted')

    def subject(self,request):
        job_id=request.get('_job_id','subjects')
        system=request.get('system','Act in the environment. Return only one legal action JSON object.')
        user={k:v for k,v in request.items() if k not in ('system','_job_id')}
        # Environment action schemas can be unions; JSON mode plus environment validation.
        payload={'model':self.settings.model,'instructions':system+' Return a JSON object for one action.','input':'Return one action as JSON.\n'+json.dumps(clean(user),ensure_ascii=False),'store':False,'max_output_tokens':600,'text':{'format':{'type':'json_object'}}}
        response=self.request(payload,job_id)
        try:
            action=json.loads(self.text(response))
            return action if isinstance(action,dict) else {'action':'invalid_model_output'}
        except (ValueError,TypeError):
            # Invalid model behavior consumes an action; transport errors still abort.
            return {'action':'invalid_model_output'}

class CodexHarness:
    name='codex'
    def __init__(self,settings,store,executable=None):
        self.settings,self.store=settings,store
        self.executable=executable or shutil.which('codex')
        if not self.executable:raise RuntimeError('Codex CLI is not installed')

    def run(self,system,user,tools,job_id,*,schema=None):
        # Provide a sanitized evidence packet in an isolated cwd. No key copied.
        with tempfile.TemporaryDirectory(prefix='swarm-research-') as d:
            work=Path(d);output=work/'answer.json'
            (work/'AGENTS.md').write_text(system,encoding='utf-8')
            (work/'evidence.json').write_text(json.dumps(clean(user),ensure_ascii=False),encoding='utf-8')
            args=[self.executable,'exec','--ephemeral','--sandbox','read-only','--skip-git-repo-check','--json','-o',str(output)]
            if schema:
                p=work/'schema.json';p.write_text(json.dumps(schema),encoding='utf-8');args+=['--output-schema',str(p)]
            args+=['-']
            proc=subprocess.run(args,input='Read AGENTS.md and evidence.json. Analyze only these evidence files. Do not access parent directories, credentials, other projects, or network services. Return the requested structured research answer.',cwd=work,text=True,encoding='utf-8',capture_output=True,timeout=300,shell=False)
            events=[]
            for line in proc.stdout.splitlines():
                try:events.append(json.loads(line))
                except json.JSONDecodeError:pass
            self.store.trace(job_id,{'type':'codex_run','returncode':proc.returncode,'events':clean(events),'packet_hash':fingerprint(user),'isolation':'read-only CLI sandbox + isolated cwd; not a general security boundary','live_tool_registry':False})
            if proc.returncode or not output.exists():raise RuntimeError(f'Codex failed ({proc.returncode}); inspect run trace')
            raw=output.read_text(encoding='utf-8')
            return json.loads(raw) if schema else raw

def harness_info():
    return [{'id':'responses','available':True,'capabilities':['research_function_tools','structured_output','context_insertion','subject_actions']},{'id':'codex','available':bool(shutil.which('codex')),'capabilities':['read_only_evidence_packet','structured_output','existing_cli_harness'],'limitations':['Live Python tool registry is not exposed; reads evidence packet via CLI file tools.']}]
