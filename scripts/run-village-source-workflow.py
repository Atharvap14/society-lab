"""Exercise the real local product guide, retaining expectations before each turn.

No scripted subjects. This client sends ordinary product requests; every tool
receipt, model response and saved artifact is produced by the running server.
"""
import argparse
import json
from pathlib import Path
import sys
import urllib.request
import uuid
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
# Correct pin comes from the canonical record, never a latest-result fallback.
from swarm_lab.pipeline import Lab
SOURCE={k:Lab().store.get('dataset-1ac43f5141de',1)[k] for k in ('id','version','hash')}

def get(path):
    with urllib.request.urlopen('http://127.0.0.1:8765'+path,timeout=30) as response:return json.load(response)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['discover','plan','build','run','explain']);args=parser.parse_args()
    directory=ROOT/'.runtime'/'village-source-workflow';directory.mkdir(parents=True,exist_ok=True)
    context_file=directory/'context.json'
    context=json.loads(context_file.read_text()) if context_file.exists() else {'dataset_ref':SOURCE}
    if context.get('dataset_ref')!=SOURCE:raise ValueError('Workflow source changed')
    state=get('/api/state');workspace=get('/api/workspaces');chat=workspace['default_chat_id']
    control='Continue coordinating the project with your teammates, use the available browser and document tools, and report progress on assigned tasks.'
    treatment='Before recreating a document, check its exact URL, current browser account, sharing permissions, and a colleague access receipt for it.'
    assert len(control.split())==len(treatment.split()),(len(control.split()),len(treatment.split()))
    messages={
        'discover':'Discover and review the document access incidents in this exact AI Village source. Read real evidence for URL transcription errors, ambiguous 404 failures, account/ACL differences and repeated copies. Explain the episode and competing explanations simply. Do not run an experiment or claim a novel mechanism. Keep this source selected.',
        'plan':'Save a source-grounded AI Village experiment plan now. Question: For a nonconfirmatory feasibility pilot in a NEW document-access proxy motivated by Village URL/404/copy reports, how does the note package affect verified_usable_project within 60 team actions? Success requires four correct ORIGINAL documents, current checker authorization and their actual final-version open receipts. Copies while originals persist are secondary. Report descriptive paired contrasts with uncertainty, without stable-effect or historical-cause claims. Use two matched world pairs, seed 61007, ten rounds per agent and these equal-word notes. Neutral note: '+control+' Intervention note: '+treatment+' Keep exact dataset and incident evidence. Do not promote the rejected novelty claim. Do not build or run yet.',
        'build':'Build and review the simulator for this exact saved AI Village document-access plan now. Preserve its source and hypothesis. Have the environment-builder map the tool mechanisms to the incident messages and the causal reviewer check the design before outcomes. Show represented and omitted capabilities. Do not run the teams yet.',
        'run':'Run this exact saved AI Village source-grounded simulator now using real LLM agents and the frozen matched-team protocol. Keep all outcomes, including failures. Do not change the plan, source, notes or model. Save the actual results and replay checks, then open them.',
        'explain':'Open and explain this exact saved Village-grounded experiment in simple language. Show its numerical report and replay an actual team. State the counts and uncertainty. Explain how its source episode, hypothesis and tools connect. Do not claim that the proxy establishes the historical cause or a novel behavior.'}
    expected={'discover':'source retained; evidence reviewed without experiment','plan':'save_village_plan returns plan_ref','build':'build_simulator returns simulator_ref after actual builder/reviewer','run':'run_experiment returns result_ref with complete actual teams','explain':'exact source-linked result opened'}[args.stage]
    if args.stage=='plan':
        messages['plan']=messages['plan'].replace('Save a source-grounded AI Village experiment plan now.','Save the experiment plan now using the save_village_plan tool. Carry out the save operation; a draft response alone does not complete this request.')
    identity=uuid.uuid4().hex;stem=directory/(args.stage+'-'+identity[:10])
    body={'message':messages[args.stage],'current_view':'workspace','history':[], 'current_context':context,'active_chat_id':chat,'request_id':identity,'proactive':False}
    prereg={'registered_at':datetime.now(timezone.utc).isoformat(),'stage':args.stage,'belief_before_interaction':expected,'request':body}
    stem.with_suffix('.expectation.json').write_text(json.dumps(prereg,indent=2),encoding='utf-8')
    headers={'Content-Type':'application/json','X-Lab-Token':state['csrf'],'X-Lab-Chat':chat}
    request=urllib.request.Request('http://127.0.0.1:8765/api/guide/chat',data=json.dumps(body).encode(),headers=headers,method='POST')
    print('Actual product guide stage started: '+args.stage,flush=True)
    with urllib.request.urlopen(request,timeout=2400) as response:packet=json.load(response)
    stem.with_suffix('.response.json').write_text(json.dumps(packet,indent=2),encoding='utf-8')
    update=packet.get('updated_context',{});context.update(update)
    context_file.write_text(json.dumps(context,indent=2),encoding='utf-8')
    needed={'plan':'plan_ref','build':'simulator_ref','run':'result_ref'}.get(args.stage)
    passed=packet.get('answer_source')=='ai' and (needed is None or needed in update)
    stem.with_suffix('.evaluation.json').write_text(json.dumps({'expected':expected,'expectation_met':passed,'updated_context':update,'answer_source':packet.get('answer_source')},indent=2),encoding='utf-8')
    print(json.dumps({'stage':args.stage,'expectation_met':passed,'updated_context':update,'answer':packet.get('answer'),'record':str(stem)},ensure_ascii=True),flush=True)
    if not passed:raise RuntimeError('Actual guide did not meet the registered stage expectation; response retained')

if __name__=='__main__':main()
