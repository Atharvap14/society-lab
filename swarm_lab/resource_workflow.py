"""Optional resource study orchestration without altering earlier frozen audits."""
import hashlib
import json
import uuid
from pathlib import Path
from .library import verify_protocol
from .store import fingerprint, now


def resource_backend(lab,live):
    if type(live) is not bool:raise ValueError('live must be boolean')
    if not live:return {'harness':'scripted','model':'deterministic_offline_policy',
        'generation':{'policy':'offline_resource_policy'}}
    return {'harness':'responses','model':lab.settings.model,
        'generation':{'max_output_tokens':600,'temperature':'provider_default','sampling_seed':'not_set'},
        'harness_adapter_hash':hashlib.sha256(Path(__file__).with_name('harness.py').read_bytes()).hexdigest()}


def design_resource(lab,*,behavior_id=None,trials_per_cell=2,seed=137,max_rounds=6,
        release_rounds=(1,2),independent_work_steps=1,computer_work_steps=1,
        max_messages_per_agent=None,live=False):
    from .resource_experiments import create_resource_protocol
    incident=None;reference=None
    if behavior_id:
        obj=lab.store.get(behavior_id);p=obj['payload']
        if obj['kind']!='behavior' or p.get('status')=='rejected' or p.get('research_quality_status') in (
                'schema_defect_requires_re_review','superseded_schema_defect_review'):
            raise ValueError('Use a non-rejected behavior with a current skeptical review')
        reference={k:obj[k] for k in ('kind','id','version','hash')}
        incident={'id':behavior_id,'title':p['name'],'source_refs':p.get('source_refs',{})}
    backend=resource_backend(lab,live)
    protocol=create_resource_protocol(trials_per_cell=trials_per_cell,seed=seed,max_rounds=max_rounds,
        release_rounds=release_rounds,independent_work_steps=independent_work_steps,
        computer_work_steps=computer_work_steps,max_messages_per_agent=max_messages_per_agent,
        incident=incident,subject_backend=backend)
    return lab.store.put('resource_protocol',{'protocol':protocol,'frozen_hash':fingerprint(protocol),
        'registered_at':now(),'status':'registered','agent_mode':'live' if live else 'offline_template',
        'behavior_id':behavior_id,'behavior_ref':reference,
        'historical_mechanism_support':'unestablished; exclusive access, abstract tasks and costs are invented analogue assumptions',
        'subject_adapter_hash':backend.get('harness_adapter_hash')})


def experiment_resource(lab,protocol_id,*,live=False,job_id=None):
    from .resource_experiments import run_resource_experiment,validate_resource_protocol
    registration=lab.store.get(protocol_id)
    if registration['kind']!='resource_protocol':raise ValueError('Resource execution requires its study-specific protocol')
    protocol=verify_protocol(registration);validate_resource_protocol(protocol)
    backend=resource_backend(lab,live)
    if protocol['subject_backend']!=backend:raise ValueError('Subject backend differs from frozen resource registration')
    maximum=protocol['design']['maximum_subject_calls']
    if live and lab.store.usage()['calls']+maximum>lab.settings.max_calls:
        raise ValueError(f'Worst-case {maximum} subject calls exceed the remaining cap; explicitly increase the cap before running')
    job_id=job_id or 'resource-experiment-'+uuid.uuid4().hex[:10]
    directory=lab.settings.runtime/'runs'/job_id
    # Existing output is never reused, whether complete or interrupted.
    if directory.exists():raise ValueError('Execution directory already exists; preserve it and choose a fresh job identity')
    runner=None
    if live:
        model=lab.harness('responses')
        def runner(request):return model.subject({**request,'_job_id':job_id})
    def progress(value):lab.store.job(job_id,'running',{'stage':'resource_experiment','protocol_id':protocol_id,'progress':value,'live':live})
    lab.store.job(job_id,'running',{'stage':'resource_experiment','protocol_id':protocol_id,'live':live})
    try:
        result=run_resource_experiment(protocol,agent_runner=runner,output_dir=directory,backend_metadata=backend,on_progress=progress)
    except Exception as error:
        failed_id=None;path=directory/'report.json'
        if path.is_file():
            failed=json.loads(path.read_text(encoding='utf-8'));failed.update(protocol_id=protocol_id,
                behavior_id=registration['payload'].get('behavior_id'),artifact_directory=str(directory),
                agent_mode='live' if live else 'offline_simulation',research_job_id=job_id)
            failed_id=lab.store.put('resource_experiment',failed)['id']
        lab.store.job(job_id,'failed',{'stage':'resource_experiment','error':str(error),'incomplete_result_id':failed_id})
        lab.store.trace(job_id,{'type':'experiment_failure','protocol_id':protocol_id,'artifact_directory':str(directory),
            'analysis':'none; infrastructure failure is not a behavioral exclusion'})
        raise
    canonical_hash=result.pop('report_hash')
    result.update(protocol_id=protocol_id,registered_hash=registration['payload']['frozen_hash'],
        behavior_id=registration['payload'].get('behavior_id'),agent_mode='live' if live else 'offline_simulation',
        model=backend['model'],artifact_directory=str(directory),research_job_id=job_id,
        canonical_execution_report_hash=canonical_hash)
    obj=lab.store.put('resource_experiment',result)
    lab.store.job(job_id,'completed',{'stage':'resource_experiment','protocol_id':protocol_id,'result_id':obj['id'],'live':live})
    return obj


def audit_resource(lab,result_id):
    from .resource_experiments import replay_resource_report
    from .audit import check_execution_archive
    obj=lab.store.get(result_id)
    if obj['kind']!='resource_experiment':raise ValueError('Use an executed resource result')
    result=obj['payload'];path=Path(result['artifact_directory'])/'report.json'
    raw=json.loads(path.read_text(encoding='utf-8'));verification=replay_resource_report(raw)
    expected=verify_protocol(lab.store.get(result['protocol_id']))
    checks=verification['checks']
    checks.append({'name':'registered_result_matches_canonical_report','passed':all((
        raw['protocol']==expected,raw.get('report_hash')==result.get('canonical_execution_report_hash'),
        raw.get('analysis')==result.get('analysis'),raw.get('runs')==result.get('runs')))})
    archive=check_execution_archive(path.parent)
    checks.append({'name':'execution_archive_bytes','passed':archive['status']=='verified'})
    manifest_path=path.parent/'execution-code'/'manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.is_file() else {}
    checks.append({'name':'execution_archive_matches_registered_sources',
        'passed':manifest.get('files')==expected['execution_code_hashes']})
    verification.update(passed=verification['passed'] and all(c['passed'] for c in checks),
        runs_checked=len(raw.get('runs',[])),report_status=raw.get('status'),execution_archive=archive)
    return lab.store.put('verification',{'experiment_id':result_id,'result_kind':obj['kind'],
        'result_ref':{k:obj[k] for k in ('id','version','hash')},**verification})


def evaluate_resource_claims(lab,result_id,*,live=False,harness='responses',job_id=None,fact_ids=None):
    from dataclasses import replace
    from .resource_claims import build_resource_fact_ledger,default_resource_fact_ids
    from .claim_audit import select_fact_packet,claims_schema_for_packet,make_claim,audit_claims
    from .research import ResearchAgents
    obj=lab.store.get(result_id)
    if obj['kind']!='resource_experiment':raise ValueError('Use a resource execution result')
    result=obj['payload'];raw=json.loads((Path(result['artifact_directory'])/'report.json').read_text(encoding='utf-8'))
    if raw.get('status')=='complete' and not audit_resource(lab,result_id)['payload']['passed']:
        raise ValueError('Resource replay or execution archive failed; quantitative claims are unavailable')
    ref={k:obj[k] for k in ('id','version','hash')}
    ledger=build_resource_fact_ledger(raw,report_id=result_id,source_ref=ref,source_object=obj)
    packet=select_fact_packet(ledger,fact_ids if fact_ids is not None else default_resource_fact_ids(ledger),max_facts=24)
    job_id=job_id or 'resource-claim-audit-'+uuid.uuid4().hex[:10]
    if live:
        bounded=replace(lab.settings,max_output_tokens=6000,max_tool_rounds=2)
        agent=ResearchAgents(bounded,lab.store,lab.research_harness(harness,bounded))
        schema=claims_schema_for_packet(packet)
        response=agent.run('evaluator',{'task':'Interpret only the supplied finite post-execution resource facts. This aggregate review shows arm labels and is not blinded. Return one typed claim per supplied fact, copying exact identity, value, kind, scope and source fingerprint. Whole swarms are samples; independent tasks and messages are not extra trials. Waiting is a process count, not a belief or mediator. Incomplete reports expose metadata only. No historical access, provider-origin, latent-state or generalization claim is verified. Attached prose remains unverified.',
            'fact_packet':packet,'output_schema':schema},schema,{'messages':[],'scope':{}},{'graph':{'edges':[]},'candidates':[]},job_id)
        claims=response['claims']
    else:claims=[make_claim(ledger,identity,fact['value']) for identity,fact in packet['facts'].items()]
    audit=audit_claims(ledger,claims)
    return lab.store.put('claim_audit',{'experiment_id':result_id,'result_kind':obj['kind'],'result_ref':ref,
        'canonical_execution_report_hash':raw.get('report_hash'),'agent_mode':'live' if live else 'offline_fact_reconstruction',
        'fact_packet':packet,'claims':claims,'audit':audit,'quantitative_facts_available':ledger['quantitative_facts_available'],
        'status':'metadata_only' if not ledger['quantitative_facts_available'] else 'verified_facts_only' if audit['all_executable_claims_supported'] else 'claim_mismatches',
        'verification_checks':ledger['verification_checks'],'issues':ledger['issues'],'research_job_id':job_id,
        'prose_scope':'Generated approved_fact_text alone is checked; model prose, beliefs, mediation and historical fidelity remain unverified.'})
