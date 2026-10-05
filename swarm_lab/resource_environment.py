"""Optional exclusive-computer analogue with always-legal independent work.

Access and completion are executed state, never inferred from chat. A single
computer, action costs and external occupation are invented task assumptions;
the historical dataset does not establish globally exclusive computer access.
"""
from __future__ import annotations

import copy
import hashlib
import json
import random

API_VERSION='1.0'
SUBJECTS=tuple(f'agent-{i}' for i in range(4))
FIDELITY={'interaction':'recipient_scoped_complete_peer_messaging',
    'world_execution':'exclusive_lease_and_exogenous_initial_occupation',
    'information':'truthful_current_resource_state_private_own_task_progress',
    'incentives':'whole_swarm_executed_task_completion',
    'agent_continuity':'within_run_context_and_own_action_history'}
ACTION_SCHEMA={'type':'object','required':['action'],'additionalProperties':False,
    'properties':{'action':{'type':'string','enum':['work_independent','request_computer',
        'work_computer','release_computer','send_message','wait']},
        'recipient':{'type':'string','enum':list(SUBJECTS)},'message':{'type':'string','maxLength':1500}},
    'instructions':'Choose one action. work_independent performs one step of your independent task and is legal regardless of computer state. request_computer attempts an exclusive lease; work_computer performs one step only if you hold the lease. Completion releases the lease automatically. release_computer releases your own lease. send_message requires recipient and message and consumes a decision and a message allowance. wait consumes a decision. Messages are unverified claims and never grant access or complete tasks.'}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def _rng(seed,purpose):return random.Random(int(fingerprint([seed,purpose]),16))


def create_resource_spec(*,max_rounds=6,release_rounds=(1,2),independent_work_steps=1,
        computer_work_steps=1,max_messages_per_agent=None,incident=None):
    if not isinstance(release_rounds,(list,tuple)):raise ValueError('release_rounds requires an explicit list of choices')
    source=incident or {}
    spec={'api_version':API_VERSION,'version':API_VERSION,'kind':'exclusive_resource_tasks',
        'agents':list(SUBJECTS),'max_rounds':max_rounds,
        'max_messages_per_agent':max_rounds-1 if max_messages_per_agent is None else max_messages_per_agent,
        'scheduler':'seeded_shuffled_round_robin_independent_of_resource',
        'resource_world':{'resource_count':1,'allocation':'exclusive_first_request_lease',
            'external_occupation':'closed_prefix_then_open','release_rounds':list(release_rounds),
            'future_release_public':False,'release_on_computer_task_completion':True},
        'task_world':{'tasks_per_agent':2,'independent_work_steps':independent_work_steps,
            'computer_work_steps':computer_work_steps,'independent_work_legal_during_occupation':True,
            'peer_task_execution':False,'quality_model':'abstract_execution_counter_no_content_quality'},
        'fidelity':copy.deepcopy(FIDELITY),
        'incident_provenance':{k:copy.deepcopy(source[k]) for k in ('id','title','source_refs') if k in source},
        'limitations':['Exclusive shared-computer access is a synthetic assumption, not a historical access finding.',
            'One monotone external release and abstract action costs do not model real browser tools or clock time.',
            'Current computer status is truthfully public; future release and private peer task progress are hidden.',
            'Independent work is legal even while the computer is unavailable or leased; waiting does not reveal intent.']}
    validate_resource_spec(spec);return spec


def validate_resource_spec(spec):
    expected={'api_version','version','kind','agents','max_rounds','max_messages_per_agent','scheduler',
        'resource_world','task_world','fidelity','incident_provenance','limitations'}
    if not isinstance(spec,dict) or set(spec)!=expected or spec.get('kind')!='exclusive_resource_tasks' or spec.get('api_version')!=API_VERSION or spec.get('version')!=API_VERSION:
        raise ValueError('Unsupported resource specification')
    rounds=spec['max_rounds']
    if spec['agents']!=list(SUBJECTS) or type(rounds) is not int or not 2<=rounds<=30:
        raise ValueError('Require four fixed subjects and 2 to 30 allocated rounds')
    messages=spec['max_messages_per_agent']
    if type(messages) is not int or not 0<=messages<=rounds:
        raise ValueError('Invalid per-subject message cap')
    if spec['fidelity']!=FIDELITY or spec['scheduler']!='seeded_shuffled_round_robin_independent_of_resource':
        raise ValueError('Unsupported fidelity or scheduler')
    world=spec['resource_world'];fixed={'resource_count':1,'allocation':'exclusive_first_request_lease',
        'external_occupation':'closed_prefix_then_open','future_release_public':False,
        'release_on_computer_task_completion':True}
    if not isinstance(world,dict) or set(world)!={*fixed,'release_rounds'} or any(world.get(k)!=v for k,v in fixed.items()):
        raise ValueError('Unsupported resource dynamics')
    releases=world['release_rounds']
    if not isinstance(releases,list) or not releases or any(type(r) is not int or not 0<=r<=rounds for r in releases) or len(set(releases))!=len(releases):
        raise ValueError('Release rounds must be unique integers from zero to max_rounds; the last means never opens during allocated turns')
    tasks=spec['task_world'];fixed={'tasks_per_agent':2,'independent_work_legal_during_occupation':True,
        'peer_task_execution':False,'quality_model':'abstract_execution_counter_no_content_quality'}
    if not isinstance(tasks,dict) or set(tasks)!={*fixed,'independent_work_steps','computer_work_steps'} or any(tasks.get(k)!=v for k,v in fixed.items()):
        raise ValueError('Unsupported task dynamics')
    if any(type(tasks[k]) is not int or not 1<=tasks[k]<=rounds for k in ('independent_work_steps','computer_work_steps')):
        raise ValueError('Task costs must be integer decision steps within the horizon')
    if not isinstance(spec['incident_provenance'],dict) or set(spec['incident_provenance'])-{'id','title','source_refs'}:
        raise ValueError('Only bounded provenance enters the world')


class ResourceTaskEnvironment:
    def __init__(self,spec,seed):
        validate_resource_spec(spec);self.spec=copy.deepcopy(spec);self.reset(seed)

    def reset(self,seed=None):
        if seed is not None:
            if type(seed) is not int or not 0<=seed<2**63:raise ValueError('Require a nonnegative 63-bit seed')
            self.seed=seed
        self.release_round=_rng(self.seed,'external-resource').choice(self.spec['resource_world']['release_rounds'])
        scheduler=_rng(self.seed,'scheduler');self.schedule=[]
        for _ in range(self.spec['max_rounds']):
            order=list(SUBJECTS);scheduler.shuffle(order);self.schedule.extend(order)
        self.progress={a:{'independent':0,'computer':0} for a in SUBJECTS}
        self.owner=None;self.step_count=0;self.events=[];self.messages=[]
        self.private_context={a:[] for a in SUBJECTS};self.last_result={a:None for a in SUBJECTS}
        self.sent_count={a:0 for a in SUBJECTS};self.turn_count={a:0 for a in SUBJECTS}
        return self.snapshot()

    @property
    def round_index(self):return self.step_count//len(SUBJECTS)

    def _done(self,agent,kind):return self.progress[agent][kind]>=self.spec['task_world'][kind+'_work_steps']

    @property
    def terminal(self):return self.step_count>=len(self.schedule) or all(self._done(a,k) for a in SUBJECTS for k in ('independent','computer'))

    @property
    def next_agent(self):return None if self.terminal else self.schedule[self.step_count]

    def _check(self,agent):
        if agent not in SUBJECTS:raise ValueError('Unknown subject')

    def resource_state(self):
        return {'status':'external_occupation' if self.round_index<self.release_round else 'leased' if self.owner else 'available',
            'lease_holder':self.owner if self.round_index>=self.release_round else None}

    def inject_context(self,agent,text):
        self._check(agent)
        if self.terminal:raise RuntimeError('Cannot insert context after termination')
        if not isinstance(text,str) or not text.strip() or len(text)>8000:raise ValueError('Invalid private context')
        self.private_context[agent].append(text)
        self.events.append({'type':'context_insertion','agent_id':agent,'step':self.step_count,'text':text})

    def observe(self,agent):
        self._check(agent)
        return copy.deepcopy({'agent_id':agent,'participants':list(SUBJECTS),
            'task':'Complete your independent task and your computer task. Team score is executed completion across all eight tasks.',
            'work_rules':ACTION_SCHEMA['instructions'],'resource':self.resource_state(),
            'your_tasks':{k:{'progress':self.progress[agent][k],
                'required_steps':self.spec['task_world'][k+'_work_steps'],'complete':self._done(agent,k)} for k in ('independent','computer')},
            'permitted_recipients':[a for a in SUBJECTS if a!=agent],
            'received_messages':[m for m in self.messages if m['recipient']==agent],
            'your_sent_messages':[m for m in self.messages if m['sender']==agent],
            'messages_remaining':self.spec['max_messages_per_agent']-self.sent_count[agent],
            'step':self.step_count,'round':self.round_index,'max_steps':len(self.schedule),
            'your_turns_remaining':self.schedule[self.step_count:].count(agent),
            'your_private_context':self.private_context[agent],'your_last_tool_result':self.last_result[agent],
            'your_action_history':[{'step':e['step'],'action':e['action'],'result':e['result']} for e in self.events if e['type']=='action' and e['agent_id']==agent]})

    def _finish(self,agent,action,result,before):
        self.events.append({'type':'action','agent_id':agent,'step':self.step_count,
            'round':self.round_index,'action':copy.deepcopy(action),'result':copy.deepcopy(result),
            'action_name':action.get('action') if isinstance(action,dict) else None,
            'opportunity_before':before})
        self.last_result[agent]=copy.deepcopy(result);self.turn_count[agent]+=1;self.step_count+=1
        return copy.deepcopy(result)

    def step(self,agent,action):
        self._check(agent)
        if self.terminal:raise RuntimeError('Environment is terminal')
        if agent!=self.next_agent:raise ValueError('Action must follow the seeded scheduler')
        before={'independent_pending':not self._done(agent,'independent'),
            'computer_pending':not self._done(agent,'computer'),'resource':self.resource_state()}
        fields={k:{'action'} for k in ACTION_SCHEMA['properties']['action']['enum']}
        fields['send_message']={'action','recipient','message'}
        def invalid(reason):return self._finish(agent,action,{'ok':False,'error':reason},before)
        if not isinstance(action,dict) or not isinstance(action.get('action'),str) or action.get('action') not in fields or set(action)!=fields.get(action.get('action')):
            return invalid('Choose one action with exactly its declared fields')
        name=action['action']
        if name=='work_independent':
            worked=not self._done(agent,'independent')
            if worked:self.progress[agent]['independent']+=1
            result={'ok':True,'worked':worked,'task':'independent','complete':self._done(agent,'independent')}
        elif name=='request_computer':
            state=self.resource_state();granted=state['status']=='available' and not self._done(agent,'computer')
            if granted:self.owner=agent
            result={'ok':True,'granted':granted,'resource_before':state,
                'reason':'lease_granted' if granted else 'computer_task_complete' if self._done(agent,'computer') else state['status']}
        elif name=='work_computer':
            worked=self.owner==agent and self.round_index>=self.release_round and not self._done(agent,'computer')
            if worked:
                self.progress[agent]['computer']+=1
                if self._done(agent,'computer'):self.owner=None
            result={'ok':True,'worked':worked,'task':'computer','complete':self._done(agent,'computer'),
                'lease_released':worked and self._done(agent,'computer')}
        elif name=='release_computer':
            released=self.owner==agent
            if released:self.owner=None
            result={'ok':True,'released':released}
        elif name=='send_message':
            recipient,text=action['recipient'],action['message']
            if recipient not in SUBJECTS or recipient==agent or not isinstance(text,str) or not text.strip() or len(text)>1500:
                return invalid('Invalid recipient or message')
            if self.sent_count[agent]>=self.spec['max_messages_per_agent']:return invalid('Message allowance exhausted')
            pair_count=sum(m['sender']==agent and m['recipient']==recipient for m in self.messages)+1
            message={'message_id':f'message-{agent}-{recipient}-{pair_count}','step':self.step_count,
                'sender':agent,'recipient':recipient,'message':text,'claim_status':'unverified_free_text'}
            self.messages.append(message);self.sent_count[agent]+=1
            result={'ok':True,'message_id':message['message_id'],'delivered_to':recipient}
        else:result={'ok':True,'waited':True}
        return self._finish(agent,action,result,before)

    def evaluate(self,focal_agent='agent-0'):
        self._check(focal_agent);actions=[e for e in self.events if e['type']=='action']
        completed={a:{k:int(self._done(a,k)) for k in ('independent','computer')} for a in SUBJECTS}
        waits=[e for e in actions if e['action_name']=='wait' and e['result']['ok']]
        independent_waits=[e for e in waits if e['opportunity_before']['independent_pending']]
        task_waits=[e for e in waits if not e['opportunity_before']['independent_pending'] and e['opportunity_before']['computer_pending'] and
            (e['opportunity_before']['resource']['status']=='external_occupation' or
             e['opportunity_before']['resource']['status']=='leased' and e['opportunity_before']['resource']['lease_holder']!=e['agent_id'])]
        return {'task_completion_fraction':sum(sum(v.values()) for v in completed.values())/8,
            'independent_completion_fraction':sum(v['independent'] for v in completed.values())/4,
            'computer_completion_fraction':sum(v['computer'] for v in completed.values())/4,
            'focal_completion_fraction':sum(completed[focal_agent].values())/2,'per_agent_completed':completed,
            'resource_access_grants':sum(e['action_name']=='request_computer' and e['result'].get('granted',False) for e in actions),
            'resource_access_denials':sum(e['action_name']=='request_computer' and e['result'].get('ok') and not e['result'].get('granted',False) for e in actions),
            'computer_work_steps':sum(e['action_name']=='work_computer' and e['result'].get('worked',False) for e in actions),
            'independent_work_steps':sum(e['action_name']=='work_independent' and e['result'].get('worked',False) for e in actions),
            'waits':len(waits),'waits_while_independent_pending':len(independent_waits),'task_specific_blocked_waits':len(task_waits),
            'messages_sent':len(self.messages),'steps_used':self.step_count,
            'invalid_actions':sum(not e['result']['ok'] for e in actions),
            'budget_by_agent':{a:{'allocated_turns':self.spec['max_rounds'],'used_turns':self.turn_count[a],
                'allocated_messages':self.spec['max_messages_per_agent'],'used_messages':self.sent_count[a]} for a in SUBJECTS},
            'terminated_by':'all_tasks_completed' if all(self._done(a,k) for a in SUBJECTS for k in ('independent','computer')) else 'step_budget' if self.terminal else 'not_terminal',
            'measurement_definitions':{'task_completion_fraction':'Exactly executed task counters divided by eight; unfinished tasks zero, claims ignored.',
                'waits_while_independent_pending':'Wait actions while independent execution remained legal and unfinished; no inferred belief or intention.',
                'task_specific_blocked_waits':'Waits with independent task complete and computer task unfinished under external occupation or another lease.',
                'resource_access_grants':'Successful code-executed exclusive lease grants; not chat mentions or access in the original dataset.'}}

    def snapshot(self):
        return copy.deepcopy({'seed':self.seed,'spec_hash':fingerprint(self.spec),
            'release_round':self.release_round,'schedule':self.schedule,'progress':self.progress,
            'owner':self.owner,'step_count':self.step_count,'events':self.events,'messages':self.messages,
            'private_context':self.private_context,'last_result':self.last_result,
            'sent_count':self.sent_count,'turn_count':self.turn_count})


def create_resource_environment(spec=None,seed=0):return ResourceTaskEnvironment(spec or create_resource_spec(),seed)


def resource_subject_request(environment,agent):
    observation=environment.observe(agent)
    return {'role':agent,'system':'You are one of four agents completing task pairs in an abstract resource environment. Choose a legal action and coordinate as you judge useful. Return one JSON action object.',
        'context':observation.pop('your_private_context'),'observation':observation,'action_schema':copy.deepcopy(ACTION_SCHEMA)}


def resource_environment_capabilities():
    return {'api_version':API_VERSION,'implemented_kinds':['exclusive_resource_tasks'],
        'capability_ids':['exclusive_shared_computer','independent_parallel_work','exogenous_initial_occupation_release',
            'recipient_scoped_messages','private_context_insertion','executed_task_completion_oracle','resettable_state'],
        'fidelity':copy.deepcopy(FIDELITY),'factory_parameters':['max_rounds','release_rounds','independent_work_steps','computer_work_steps','max_messages_per_agent'],
        'operations':['construct','validate','reset','observe','step','inject_private_context','snapshot_for_researcher','evaluate'],
        'limitations':['Exactly four agents and one synthetic exclusive resource; no browser or arbitrary task code.',
            'No queue, reservation, repeated external occupation, task quality, wall-clock cost or access inference from chat.',
            'Independent work remains legal throughout. Historical global exclusivity is unestablished.']}


def check_resource_contract(environment):
    seed=environment.seed;initial=environment.reset(seed);checks=[]
    packets=[resource_subject_request(environment,a) for a in SUBJECTS]
    checks.append({'name':'private_future_and_world_absent','passed':all(not ({'seed','release_round','schedule','progress','protocol_hash','arm','assigned_arm'}&set(p['observation'])) for p in packets)})
    marker='RESOURCE_PRIVATE_CONTEXT_MARKER';environment.inject_context('agent-0',marker)
    checks.append({'name':'private_context_recipient_only','passed':all((marker in json.dumps(resource_subject_request(environment,a)))==(a=='agent-0') for a in SUBJECTS)})
    environment.reset(seed);actor=environment.next_agent
    result=environment.step(actor,{'action':'work_independent'})
    checks.append({'name':'independent_work_legal_in_initial_resource_state','passed':result['ok'] and result['worked']})
    checks.append({'name':'reset_exact','passed':environment.reset(seed)==initial})
    return {'passed':all(c['passed'] for c in checks),'checks':checks,
        'scope':'One-seed structural smoke check plus exact reset; not historical fidelity or complete semantic leakage proof.'}


def offline_resource_policy(request):
    """Deterministic opportunistic script; context-independent infrastructure."""
    o=request['observation'];tasks=o['your_tasks'];state=o['resource']
    if state['lease_holder']==request['role'] and not tasks['computer']['complete']:return {'action':'work_computer'}
    if not tasks['independent']['complete']:return {'action':'work_independent'}
    if not tasks['computer']['complete'] and state['status']=='available':return {'action':'request_computer'}
    return {'action':'wait'}


def global_wait_policy(request):
    """Scripted global wait, not an inferred agent belief or empirical model."""
    if request['observation']['resource']['status']=='external_occupation':return {'action':'wait'}
    return offline_resource_policy(request)


def task_specific_wait_policy(request):
    """Independent work first; genuine gate/lease waits remain legal."""
    return offline_resource_policy(request)
