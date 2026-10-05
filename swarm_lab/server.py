"""Local dashboard API and background job queue. Binds loopback only."""
import concurrent.futures
import copy
import json
import math
import mimetypes
import re
import secrets
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from .harness import harness_info
from .store import clean
from .state_inventory_cache import CompactObjectInventoryCache

class LocalResearchServer(ThreadingHTTPServer):
    # Windows SO_REUSEADDR can admit two listeners, serving stale code at random.
    allow_reuse_address=False


class _QueuedStore:
    """Keep the queue's terminal publication separate from component progress.

    Existing components may publish their own completed/failed job before they
    return. The queue alone closes its outer identity with the public result
    link or exception. Traces, call accounting and other job identities retain
    their original Store behavior.
    """
    def __init__(self,store,job_id,action):
        self._store,self._job_id,self._action=store,job_id,action
        self.failures=[]

    def __getattr__(self,name):
        return getattr(self._store,name)

    def job(self,job_id,status,payload):
        if job_id==self._job_id:
            if status=='failed':
                self.failures.append(copy.deepcopy({key:value for key,value in payload.items()
                    if key!='component_failures'}))
            payload={**payload,'action':self._action}
            if self.failures:
                payload['component_failures']=copy.deepcopy(self.failures)
                for key in ('incomplete_result_id','artifact_directory'):
                    if key not in payload:
                        previous=next((row[key] for row in reversed(self.failures)
                            if type(row.get(key)) is str and row[key]),None)
                        if previous is not None:payload[key]=previous
            if status in ('completed','failed'):
                payload['component_status']=status
                status='running'
        return self._store.job(job_id,status,payload)

def parse_job_request(raw,supported_actions):
    """Match the strict declarative CLI envelope before a job is queued."""
    def pairs(entries):
        values={}
        for key,value in entries:
            if key in values:raise ValueError('Duplicate API JSON key')
            values[key]=value
        return values
    def constant(value):raise ValueError('API jobs require finite JSON')
    def number(value):
        result=float(value)
        if not math.isfinite(result):raise ValueError('API jobs require finite JSON numbers')
        return result
    body=json.loads(raw,object_pairs_hook=pairs,parse_constant=constant,parse_float=number)
    if (type(body) is not dict or 'action' not in body or not set(body)<={'action','args'} or
        type(body['action']) is not str or body['action'] not in supported_actions or
        type(body.get('args',{})) is not dict):
        raise ValueError('Use a supported action and an object of arguments')
    return body['action'],body.get('args',{})

def parse_event_graph_query(query):
    """Require an exact saved source and a bounded event-neighborhood scope."""
    keys={'object_id','version','hash','event_id','hops'}
    if (type(query) is not dict or set(query)!=keys or
        any(type(values) is not list or len(values)!=1 or type(values[0]) is not str or not values[0]
            for values in query.values())):
        raise ValueError('Supply each exact event graph parameter once')
    values={key:entries[0] for key,entries in query.items()}
    for key in ('object_id','event_id'):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}',values[key]):
            raise ValueError('Use bounded stable object and event IDs')
    if not re.fullmatch(r'[1-9][0-9]{0,15}',values['version']):
        raise ValueError('Use a canonical positive integer source version')
    version=int(values['version'])
    if version>9007199254740991:raise ValueError('Source version exceeds the safe integer bound')
    if not re.fullmatch(r'[a-f0-9]{64}',values['hash']):
        raise ValueError('Supply the exact lowercase source fingerprint')
    if values['hops'] not in ('0','1','2'):raise ValueError('Event graph hops must be 0, 1 or 2')
    return {**values,'version':version,'hops':int(values['hops'])}

def serve(lab,port=8765):
    from .lab_workspace import bootstrap_workspace,for_chat,attach_returned
    bootstrap_workspace(lab)
    pool=concurrent.futures.ThreadPoolExecutor(max_workers=1)
    csrf=secrets.token_urlsafe(32)
    static=lab.settings.root/'web'
    inventory=CompactObjectInventoryCache(lab.store.path)
    methods={'ingest':lab.ingest,'observe':lab.observe,'screen_graph':lab.screen_graph,'replicate':lab.replicate,'link_replication':lab.link_replication,'investigate':lab.investigate,'resume_investigation':lab.resume_investigation,'design':lab.design,'experiment':lab.experiment,'evaluate':lab.evaluate,'evaluate_claims':lab.evaluate_claims,'audit':lab.audit,'theorize':lab.theorize,'workflow':lab.workflow,'design_network':lab.design_network,'experiment_network':lab.experiment_network,'design_complementary':lab.design_complementary,'experiment_complementary':lab.experiment_complementary}
    methods['construct_environment']=lab.construct_environment
    methods['resume_environment_review']=lab.resume_environment_review
    methods['project_observables']=lab.project_observables
    methods['register_blueprint']=lab.register_blueprint
    methods['audit_mentions']=lab.audit_mentions
    methods['audit_name_eligibility']=lab.audit_name_eligibility
    methods['compare_mention_graphs']=lab.compare_mention_graphs
    methods['audit_selected_leads']=lab.audit_selected_leads
    methods['audit_temporal_paths']=lab.audit_temporal_paths
    methods['replay_temporal_paths']=lab.replay_temporal_paths
    methods['scan_source_links']=lab.scan_source_links
    methods['replay_source_links']=lab.replay_source_links
    methods['build_event_source_index']=lab.build_event_source_index
    methods['audit_indexed_events']=lab.audit_indexed_events
    methods['replay_indexed_events']=lab.replay_indexed_events
    methods['audit_temporal_reference']=lab.audit_temporal_reference
    methods['replay_temporal_reference']=lab.replay_temporal_reference
    methods['audit_selected_actor_events']=lab.audit_selected_actor_events
    methods['replay_actor_events']=lab.replay_actor_events
    methods['audit_wait_markers']=lab.audit_wait_markers
    methods['replay_wait_markers']=lab.replay_wait_markers
    methods['audit_edge_flow']=lab.audit_edge_flow
    methods['replay_edge_flow']=lab.replay_edge_flow
    methods['start_research_cycle']=lab.start_research_cycle
    methods['resume_research_cycle']=lab.resume_research_cycle
    methods['design_resource']=lab.design_resource
    methods['experiment_resource']=lab.experiment_resource
    methods['design_timed_resource']=lab.design_timed_resource
    methods['experiment_timed_resource']=lab.experiment_timed_resource
    methods['design_revision_relay']=lab.design_revision_relay
    methods['experiment_revision_relay']=lab.experiment_revision_relay
    methods['audit_revision_relay']=lab.audit_revision_relay
    methods['create_measurement_sample']=lab.create_measurement_sample
    methods['record_measurement_judgment']=lab.record_measurement_judgment
    def submit(action,args,origin_chat_id=None):
        origin_lab=for_chat(lab,origin_chat_id) if origin_chat_id is not None else lab
        job_id='job-'+uuid.uuid4().hex[:12]
        origin_lab.store.job(job_id,'queued',{'action':action,'args':args})
        def work():
            origin_lab.store.job(job_id,'running',{'action':action,'args':args})
            queued_store=None
            try:
                if action not in methods:raise ValueError('Unknown action')
                if action=='start_research_cycle':args['job_id']=job_id+'.cycle'
                if action in ('observe','investigate','resume_investigation','design','experiment','evaluate','evaluate_claims','theorize','workflow','experiment_network','experiment_complementary','experiment_resource','experiment_timed_resource','experiment_revision_relay','construct_environment','resume_environment_review'):args['job_id']=job_id
                queued_lab=copy.copy(origin_lab)
                queued_store=_QueuedStore(origin_lab.store,job_id,action)
                queued_lab.store=queued_store
                result=getattr(queued_lab,action)(**args)
                if origin_chat_id is not None:attach_returned(lab,origin_chat_id,result)
                ids=[o['id'] for o in result] if isinstance(result,list) else result.get('id',result.get('outputs'))
                if action in ('start_research_cycle','resume_research_cycle'):
                    cycle_status=result['payload']['status']
                    origin_lab.store.job(job_id,'completed' if cycle_status=='completed' else 'failed',
                        {'action':action,'result_ids':ids,'cycle_ref':{k:result[k] for k in ('kind','id','version','hash')},
                         'cycle_status':cycle_status,'phase':result['payload']['phase']})
                    return
                closure={'action':action,'result_ids':ids}
                if queued_store.failures:closure['component_failures']=queued_store.failures
                origin_lab.store.job(job_id,'completed',closure)
            except Exception as e:
                saved=lab.store.get_job(job_id)
                retained=saved['payload'] if saved and (saved['status']=='failed' or
                    saved['payload'].get('component_status')=='failed' or saved['payload'].get('component_failures')) else {}
                closure={**retained,'action':action,'error':str(e)[:1000]}
                if queued_store and queued_store.failures:
                    closure['component_failures']=queued_store.failures
                    partial_ids=list(dict.fromkeys(row['incomplete_result_id'] for row in queued_store.failures
                        if type(row.get('incomplete_result_id')) is str and row['incomplete_result_id']))
                    if partial_ids:closure['result_ids']=partial_ids
                origin_lab.store.job(job_id,'failed',closure)
        pool.submit(work)
        return {'job_id':job_id}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,value,status=200):
            raw=json.dumps(clean(value),ensure_ascii=False,allow_nan=False).encode()
            self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            path=urllib.parse.urlparse(self.path);q=urllib.parse.parse_qs(path.query)
            try:
                if path.path=='/api/state':
                    from .demo_visibility import visible_inventory, visible_jobs
                    compact=visible_inventory(lab,inventory.get())
                    self.send({'objects':compact,'jobs':visible_jobs(lab,lab.store.jobs()),'usage':lab.store.usage(),'harnesses':harness_info(),'csrf':csrf,'model':lab.settings.model,'max_calls':lab.settings.max_calls,'service_version':'village-source-linked-1','supported_actions':sorted(methods)});return
                if path.path=='/api/guide/status':
                    from .guide_assistant import guide_status
                    if path.query:raise ValueError('Guide status takes no query parameters')
                    self.send(guide_status(lab));return
                if path.path=='/api/rubrics':
                    from .behavior_rubrics import rubric_catalog
                    if path.query:raise ValueError('Rubric catalog takes no query parameters')
                    self.send(rubric_catalog(lab));return
                if path.path=='/api/guide/activity':
                    from .guide_tools import guide_activity
                    from .lab_workspace import parse_chat_query
                    query=parse_chat_query(urllib.parse.parse_qs(path.query,keep_blank_values=True))
                    if 'revision' in query:raise ValueError('Activity is the current operation log; exact discussion revisions use the context endpoint')
                    self.send(guide_activity(lab,query['chat_id']));return
                if path.path=='/api/guide/report':
                    from .guide_reports import render_report,report_ref
                    query=urllib.parse.parse_qs(path.query,keep_blank_values=True)
                    reference=report_ref(query)
                    raw=render_report(lab.store,reference).encode('utf-8')
                    self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store')
                    self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'self'")
                    self.end_headers();self.wfile.write(raw);return
                if path.path=='/api/workspaces':
                    from .lab_workspace import workspace_index
                    if path.query:raise ValueError('Workspace index takes no query parameters')
                    self.send(workspace_index(lab));return
                if path.path in ('/api/workspaces/chat','/api/workspaces/context'):
                    from .lab_workspace import chat_snapshot,read_context,parse_chat_query
                    query=parse_chat_query(urllib.parse.parse_qs(path.query,keep_blank_values=True))
                    method=chat_snapshot if path.path.endswith('/chat') else read_context
                    self.send(method(lab,**query));return
                if path.path=='/api/workspaces/artifacts':
                    from .lab_workspace import artifact_catalog,parse_catalog_query
                    self.send(artifact_catalog(lab,**parse_catalog_query(urllib.parse.parse_qs(path.query,keep_blank_values=True))));return
                if path.path=='/api/observability/schema':
                    from .observability_protocol import protocol_manifest
                    if path.query:raise ValueError('Observability schema takes no query parameters')
                    self.send(protocol_manifest());return
                if path.path=='/api/observability/follow':
                    from .observability_protocol import follow_observability,parse_follow_query
                    follow_query=urllib.parse.parse_qs(path.query,keep_blank_values=True)
                    self.send(follow_observability(lab,parse_follow_query(follow_query)));return
                if path.path=='/api/observability/graph':
                    from .event_evidence_graph import build_event_evidence_neighborhood
                    graph_query=parse_event_graph_query(urllib.parse.parse_qs(path.query,keep_blank_values=True,
                        strict_parsing=True,max_num_fields=5))
                    record=lab.store.get(graph_query['object_id'],graph_query['version'])
                    if any(record[key]!=graph_query[name] for key,name in
                           (('id','object_id'),('version','version'),('hash','hash'))):
                        raise ValueError('The requested exact graph source does not match the saved run')
                    self.send(build_event_evidence_neighborhood(record,seed_event_id=graph_query['event_id'],
                        hops=graph_query['hops']));return
                if path.path.startswith('/api/object/'):
                    identity=urllib.parse.unquote(path.path.rsplit('/',1)[-1]);version=int(q['version'][0]) if 'version' in q else None
                    self.send(lab.store.history(identity) if 'history' in q else lab.store.get(identity,version));return
                if path.path.startswith('/api/traces/'):
                    self.send(lab.store.traces(path.path.rsplit('/',1)[-1]));return
                if path.path=='/api/environments':
                    from .environment_api import capabilities
                    self.send(capabilities());return
                if path.path=='/api/environment-authoring':
                    from .environment_authoring import schema_for_capabilities
                    self.send(schema_for_capabilities());return
                if path.path=='/api/measurements':
                    from .measurement_backends import capabilities
                    self.send(capabilities(lab.settings.root));return
                if path.path=='/api/episode-workspace':
                    from .episode_workspace import episode_workspace_packet,parse_episode_query
                    episode_query=urllib.parse.parse_qs(path.query,keep_blank_values=True)
                    self.send(episode_workspace_packet(lab.store,**parse_episode_query(episode_query)));return
                if path.path=='/api/measurement-review':
                    from .measurement_review_workflow import measurement_review_workspace,parse_review_query
                    review_query=urllib.parse.parse_qs(path.query,keep_blank_values=True)
                    self.send(measurement_review_workspace(lab.store,**parse_review_query(review_query)));return
                if path.path=='/api/blueprint-registration-preview':
                    from .registration_preview import preview_blueprint_registration,parse_registration_preview_query
                    preview_query=urllib.parse.parse_qs(path.query,keep_blank_values=True)
                    self.send(preview_blueprint_registration(lab,**parse_registration_preview_query(preview_query)));return
                if path.path.startswith('/reports/'):
                    report_root=(lab.settings.runtime/'reports').resolve()
                    target=(report_root/urllib.parse.unquote(path.path[len('/reports/'):])).resolve()
                    if not target.is_relative_to(report_root) or not target.is_file():self.send({'error':'Report not found'},404);return
                    if target.suffix.lower() not in ('.html','.json','.md'):self.send({'error':'Unsupported report type'},404);return
                    raw=target.read_bytes();self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(target)[0] or 'text/plain');self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'none'");self.end_headers();self.wfile.write(raw);return
                name='index.html' if path.path=='/' else path.path.lstrip('/')
                target=(static/name).resolve()
                if not target.is_relative_to(static.resolve()) or not target.is_file():self.send({'error':'Not found'},404);return
                raw=target.read_bytes();self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(target)[0] or 'application/octet-stream');self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; img-src 'self' data:; frame-src 'self'; frame-ancestors 'none'");self.end_headers();self.wfile.write(raw)
            except KeyError:self.send({'error':'Object not found'},404)
            except Exception as e:self.send({'error':str(e)[:1000]},400)
        def do_POST(self):
            # A local webpage cannot launch paid work through cross-site requests.
            if self.headers.get('X-Lab-Token')!=csrf:self.send({'error':'Missing local session token'},403);return
            try:
                length=int(self.headers.get('Content-Length','0'))
                chat_headers=self.headers.get_all('X-Lab-Chat',[])
                if len(chat_headers)>1:raise ValueError('Supply at most one origin chat header')
                origin_chat_id=chat_headers[0] if chat_headers else None
                request_lab=for_chat(lab,origin_chat_id) if origin_chat_id is not None else lab
                def publish(value,status=201):
                    if origin_chat_id is not None:attach_returned(lab,origin_chat_id,value)
                    self.send(value,status)
                if self.path=='/api/workspaces':
                    from .lab_workspace import mutate_workspace,MAX_BODY
                    if not 0<length<=MAX_BODY:raise ValueError('Invalid workspace request length')
                    self.send(mutate_workspace(lab,self.rfile.read(length)),201);return
                if self.path in ('/api/rubrics/save','/api/rubrics/measure'):
                    from .behavior_rubrics import save_rubric,measure_rubric
                    if not 0<length<=16000:raise ValueError('Invalid rubric request length')
                    method=save_rubric if self.path.endswith('/save') else measure_rubric
                    publish(method(request_lab,self.rfile.read(length)));return
                if self.path=='/api/observability/connect':
                    from .observability_protocol import connect_observability,MAX_BYTES
                    if not 0<length<=MAX_BYTES:raise ValueError('Invalid observability batch length')
                    publish(connect_observability(request_lab,self.rfile.read(length)));return
                if self.path=='/api/observability/brief':
                    from .observability_protocol import brief_dataset
                    if not 0<length<=16000:raise ValueError('Invalid dataset brief request length')
                    publish(brief_dataset(request_lab,self.rfile.read(length)));return
                if self.path in ('/api/guided/plan','/api/village-recovery/plan','/api/guided/simulator','/api/guided/run'):
                    if not 0<length<=64000:raise ValueError('Invalid guided study request length')
                    raw=self.rfile.read(length)
                    from . import village_access_study
                    if self.path=='/api/village-recovery/plan':
                        from . import reference_repair_study
                        method=reference_repair_study.create_plan
                    elif self.path=='/api/guided/plan':method=village_access_study.create_plan
                    else:
                        from .guided_study import _parse,_record
                        key='plan_ref' if self.path.endswith('/simulator') else 'simulator_ref'
                        body=_parse(raw,(key,))
                        source=_record(request_lab,body[key],'guided_plan' if key=='plan_ref' else 'guided_simulator')
                        family=source['payload'].get('family')
                        if family=='single_document_reference_repair':
                            from . import reference_repair_study
                            producer=reference_repair_study
                        elif family=='village_document_access_repair':producer=village_access_study
                        else:raise ValueError('Select an exact source-grounded Village plan or simulator; no fallback world is allowed')
                        method=producer.create_simulator if key=='plan_ref' else producer.execute_plan
                    publish(method(request_lab,raw));return
                if self.path=='/api/guide/chat':
                    from .demo_visibility import visible_inventory
                    from .guide_assistant import guide_chat,parse_guide_request,MAX_BODY_BYTES
                    if not 0<length<=MAX_BODY_BYTES:raise ValueError('Invalid guide request length')
                    guide_raw=self.rfile.read(length)
                    guide_request=parse_guide_request(guide_raw)
                    if origin_chat_id is not None and guide_request.get('active_chat_id') is not None and guide_request['active_chat_id']!=origin_chat_id:
                        raise ValueError('The active guide chat must match the captured origin chat header')
                    self.send(guide_chat(request_lab,guide_raw,inventory=visible_inventory(lab,inventory.get()),queue_submit=submit));return
                if self.path=='/api/guide/import':
                    from .friendly_import import import_chat
                    if not 0<length<=1048576:raise ValueError('Invalid import request length')
                    publish(import_chat(request_lab,self.rfile.read(length)));return
                if self.path!='/api/jobs':raise ValueError('Unknown API endpoint')
                if not 0<length<=64000:raise ValueError('Invalid request length')
                action,args=parse_job_request(self.rfile.read(length),methods)
                self.send(submit(action,args,origin_chat_id),202)
            except Exception as e:
                from .lab_workspace import WorkspaceConflictError
                if isinstance(e,WorkspaceConflictError):self.send({'error':str(e),'code':'revision_conflict','latest_revision':e.latest_revision},409)
                else:self.send({'error':str(e)[:1000]},400)
    server=LocalResearchServer(('127.0.0.1',port),Handler)
    print(f'Swarm Research Lab http://127.0.0.1:{port}',flush=True)
    try:server.serve_forever()
    finally:server.server_close();inventory.close();pool.shutdown(wait=False,cancel_futures=True)
