"""Replay recorded actions against the oracle; never calls a model."""
import copy
import hashlib
import json
from pathlib import Path
from .store import now

def snapshot_execution_code(output_dir,*,timing='before_subject_execution'):
    directory=Path(output_dir)/'execution-code';directory.mkdir(parents=True,exist_ok=True)
    package=Path(__file__).parent
    hashes={}
    for file in package.glob('*.py'):
        data=file.read_bytes();(directory/file.name).write_bytes(data);hashes[file.name]=hashlib.sha256(data).hexdigest()
    manifest={'created_at':now(),'timing':timing,'files':hashes,'scope':'Source code only; no credentials, database, transcripts or dataset copied.'}
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest

def replay_report(report):
    if 'environments' in report['protocol']:
        return replay_network_report(report)
    from .environments import create_environment,subject_request
    from .experiments import validate_protocol
    protocol=report['protocol'];validate_protocol(protocol)
    checks=[]
    if report.get('report_hash'):
        body={k:v for k,v in report.items() if k!='report_hash'}
        digest=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        checks.append({'name':'canonical_report_hash','passed':digest==report['report_hash']})
    for run in report.get('runs',[]):
        env=create_environment(protocol['environment'],run['environment_seed']);inserted=False
        initial_ok=env.snapshot()==run['initial_state'];request_ok=True;results_ok=True
        for turn in run['turns']:
            agent=env.next_agent
            if agent==protocol['intervention']['recipient'] and not inserted:
                text=protocol['arms'][run['arm']]['insertion']
                if text is not None:env.inject_context(agent,text)
                inserted=True
            if agent!=turn['agent_id']:request_ok=False;break
            request_ok=request_ok and subject_request(env,agent)==turn['request']
            observed=env.step(agent,copy.deepcopy(turn['action']))
            results_ok=results_ok and observed==turn['tool_result']
        checks.append({'name':'recorded_action_replay','run_id':run['run_id'],'passed':all((initial_ok,request_ok,results_ok,env.snapshot()==run['final_state'],env.evaluate()==run['outcomes'])),
            'initial_state_matches':initial_ok,'subject_requests_match':request_ok,'tool_results_match':results_ok,'final_state_matches':env.snapshot()==run['final_state'],'oracle_outcomes_match':env.evaluate()==run['outcomes']})
    return {'passed':bool(report.get('runs')) and all(c['passed'] for c in checks),'checks':checks,'runs_checked':len(report.get('runs',[])),
        'report_status':report.get('status'),'model_calls':0,'scope':'Re-execution of recorded actions validates state transitions, information packets and oracle outcomes. It is not a fresh model replication or proof of historical fidelity.'}


def replay_network_report(report):
    from .diffusion_environment import fingerprint
    protocol=report['protocol']
    if protocol.get('study_kind')=='complementary_information_factorial':
        from .complementary_environment import create_complementary_environment as create_network_environment,complementary_subject_request as network_subject_request
        from .complementary_experiments import validate_complementary_protocol
        validate_complementary_protocol(protocol)
    else:
        from .diffusion_environment import create_diffusion_environment as create_network_environment,diffusion_subject_request as network_subject_request
        from .diffusion_experiments import validate_diffusion_protocol
        validate_diffusion_protocol(protocol)
    checks=[{'name':'canonical_report_hash','passed':fingerprint({k:v for k,v in report.items() if k!='report_hash'})==report.get('report_hash')}]
    for run in report.get('runs',[]):
        env=create_network_environment(protocol['environments'][run['topology']],run['environment_seed'])
        matches={'initial_state_matches':env.snapshot()==run['initial_state'],'subject_requests_match':True,'tool_results_match':True}
        delivered=set()
        for turn in run['turns']:
            agent=env.next_agent
            if agent in protocol['intervention']['recipients'] and agent not in delivered:
                insertion=protocol['contexts'][run['context']]['insertion']
                if insertion is not None:env.inject_context(agent,insertion)
                delivered.add(agent)
            if agent!=turn['agent_id']:
                matches['subject_requests_match']=False;break
            matches['subject_requests_match'] &= network_subject_request(env,agent)==turn['request']
            matches['tool_results_match'] &= env.step(agent,copy.deepcopy(turn['action']))==turn['tool_result']
        matches['final_state_matches']=env.snapshot()==run['final_state']
        matches['oracle_outcomes_match']=env.evaluate(protocol['intervention'].get('focal_agent','agent-0'))==run['outcomes']
        checks.append({'name':'recorded_network_action_replay','run_id':run['run_id'],'passed':all(matches.values()),**matches})
    return {'passed':bool(report.get('runs')) and all(x['passed'] for x in checks),'checks':checks,'runs_checked':len(report.get('runs',[])),
            'report_status':report.get('status'),'model_calls':0,'scope':'Recorded network requests, actions and oracle replay; no new model replication or historical fidelity established.'}


def check_execution_archive(directory):
    archive=Path(directory)/'execution-code';manifest_path=archive/'manifest.json'
    if not manifest_path.is_file():return {'status':'missing','scope':'Historical execution source archive is unavailable; current action replay is a separate check.'}
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'));checks=[]
    for name,expected in manifest.get('files',{}).items():
        file=archive/name
        safe=Path(name).name==name and file.suffix=='.py'
        checks.append({'file':name,'passed':bool(safe and file.is_file() and hashlib.sha256(file.read_bytes()).hexdigest()==expected)})
    return {'status':'verified' if checks and all(c['passed'] for c in checks) else 'mismatch','timing':manifest.get('timing'),
            'checks':checks,'scope':'Checks archive bytes against its local manifest; no external timestamp attestation or execution of archived source.'}
