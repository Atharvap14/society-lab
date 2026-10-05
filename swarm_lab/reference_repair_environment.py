"""One-document reference recovery over the frozen Village proxy mechanics.

Only new experimental owner/checker roles act. Initial URL fault, permissions,
content and profile conditions are declared experimental choices, not history.
"""
import copy
import json
import random

from .village_access_environment import (VillageAccessEnvironment, create_village_access_spec,
    validate_village_access_spec, ACTION_SCHEMA as BASE_ACTION_SCHEMA, ACTION_FIELDS, digest, _bounded, _ref)

KIND='single_document_reference_repair'
VERSION='reference-repair-v1'
AGENTS=['ethics_owner','auditor']
TARGET='irb-protocol'
PRIMARY='verified_repaired_reference'
TOOLS=['open_url','type_url','navigate','drive_search','copy_current_url','send_message',
    'switch_session','inspect_document','report_status','wait']
LIMITS=['A new two-role, one-document experiment; original six-model policies and audience are not reproduced.',
    'Original Google state, browser rendering/cookies and historical causes remain unverified.',
    'One seeded URL-reference fault is supplied while content, ACL and initial authenticated profiles are held fixed.',
    'Local deterministic proxy tools have real state transitions but do not emulate full Google or OS behavior.',
    'Queued messages and returned content do not prove attention, comprehension or causal mediation.']


def create_reference_repair_spec(*,max_rounds=8,source_grounding=None):
    base=create_village_access_spec(max_rounds=max_rounds,source_grounding=source_grounding,
        initial_conditions={'url_glitches':'clean','permissions':'team','sessions':'authenticated','content':'correct'})
    spec={'version':VERSION,'kind':KIND,'active_agents':list(AGENTS),'max_rounds':max_rounds,
        'target_document':TARGET,'base_environment':base,'agents':list(AGENTS),
        'agent_profiles':{role:copy.deepcopy(base['agent_profiles'][role]) for role in AGENTS},
        'initial_conditions':{'owner_reference':'canonical','checker_reference':'single_nonresolving_ID_substitution',
            'content':'correct_original','permissions':'owner_and_checker_viewer','sessions':'authenticated',
            'initial_failure':'exogenous_checker_navigation_probe_not_a_model_action'},
        'goal':'The auditor must execute a successful open of the CURRENT ORIGINAL IRB document within the fixed budget. An owner open, copy, message or success report alone does not complete this task.',
        'tools':list(TOOLS),'limitations':list(LIMITS)}
    validate_reference_repair_spec(spec);return spec


def validate_reference_repair_spec(spec):
    _bounded(spec)
    if type(spec) is not dict or set(spec)!={'version','kind','active_agents','max_rounds','target_document','base_environment','initial_conditions','goal','tools','limitations','agents','agent_profiles'}:
        raise ValueError('Exact supported one-document world specification required')
    validate_village_access_spec(spec['base_environment'])
    if type(spec['max_rounds']) is not int or not 4<=spec['max_rounds']<=10:
        raise ValueError('One-document rounds must be an integer from 4 to 10')
    expected=create_spec_without_validation(spec['max_rounds'],spec['base_environment'])
    if digest(spec)!=digest(expected):raise ValueError('Unsupported recovery-world rules')
    conditions=spec['base_environment']['initial_conditions']
    if conditions!={'url_glitches':'clean','permissions':'team','sessions':'authenticated','content':'correct','permission_failure_surface':'404'}:
        raise ValueError('Reference-repair controls must hold truth, ACL and initial principal fixed')
    if type(spec['base_environment']['max_rounds']) is not int or spec['base_environment']['max_rounds']!=spec['max_rounds']:
        raise ValueError('World budget differs')


def create_spec_without_validation(rounds,base):
    return {'version':VERSION,'kind':KIND,'active_agents':list(AGENTS),'max_rounds':rounds,
        'target_document':TARGET,'base_environment':copy.deepcopy(base),'agents':list(AGENTS),
        'agent_profiles':{role:copy.deepcopy(base['agent_profiles'][role]) for role in AGENTS},
        'initial_conditions':{'owner_reference':'canonical','checker_reference':'single_nonresolving_ID_substitution',
            'content':'correct_original','permissions':'owner_and_checker_viewer','sessions':'authenticated',
            'initial_failure':'exogenous_checker_navigation_probe_not_a_model_action'},
        'goal':'The auditor must execute a successful open of the CURRENT ORIGINAL IRB document within the fixed budget. An owner open, copy, message or success report alone does not complete this task.',
        'tools':list(TOOLS),'limitations':list(LIMITS)}


def _action_schema():
    schema=copy.deepcopy(BASE_ACTION_SCHEMA)
    schema['properties']['action']['enum']=list(TOOLS)
    allowed=set().union(*(ACTION_FIELDS[name] for name in TOOLS))
    schema['properties']={k:v for k,v in schema['properties'].items() if k in allowed}
    schema['properties']['recipient']['enum']=list(AGENTS)
    schema['properties']['document_key']['enum']=[TARGET]
    schema['instructions']='Choose one exact action: '+'; '.join(name+'('+', '.join(sorted(ACTION_FIELDS[name]-{'action'}))+')' for name in TOOLS)+'. Drive search matches document TITLE text, not an opaque ID. open_url commits navigation; type_url only drafts then navigate commits. Read actual tool results and delivered peer messages. send_message must address the other named role. Reports/owner opens/messages do not satisfy the auditor-open goal. All failed actions and waits consume an opportunity. No tool sequence is prescribed.'
    return schema


ACTION_SCHEMA=_action_schema()


class ReferenceRepairEnvironment:
    def __init__(self,spec,seed):
        validate_reference_repair_spec(spec)
        self.spec=copy.deepcopy(spec);self.reset(seed)

    @property
    def agent_ids(self):return list(AGENTS)
    @property
    def max_steps(self):return len(AGENTS)*self.spec['max_rounds']
    @property
    def step_count(self):return self.base.step_count
    @property
    def terminal(self):return self.base.terminal
    @property
    def next_agent(self):return self.base.next_agent
    @property
    def events(self):return self.base.events
    @property
    def private_context(self):return self.base.private_context

    def reset(self,seed=None):
        if seed is None:seed=self.seed
        if type(seed) is not int or not 0<=seed<2**53:raise ValueError('An independent safe integer world seed is required')
        self.seed=seed;self.base=VillageAccessEnvironment(self.spec['base_environment'],seed)
        e=self.base;original=e.documents[e.originals[TARGET]]
        original['acl']={'ethics_owner':'owner','auditor':'viewer'}
        e.documents={original['id']:original};e.originals={TARGET:original['id']}
        e.required_content={TARGET:e.required_content[TARGET]}
        for field in ('browsers','private_context','last_result','clipboards','local_drafts'):
            setattr(e,field,{role:getattr(e,field)[role] for role in AGENTS})
        canonical=f"https://village.local/docs/{original['id']}/view"
        bad=canonical.replace(original['id'],original['id'][:-1]+('x' if original['id'][-1]!='x' else 'y'))
        e.references={'ethics_owner':{TARGET:canonical},'auditor':{TARGET:bad}}
        scheduler=random.Random(int(digest([seed,'reference_repair_schedule']),16));e.schedule=[]
        for _ in range(self.spec['max_rounds']):
            order=list(AGENTS);scheduler.shuffle(order);e.schedule.extend(order)
        # A code-generated pre-treatment probe, explicitly not an LLM decision
        # or historical agent emission. Both arms start with the same receipt.
        result,cause=e._access('auditor',bad);e.last_result['auditor']=copy.deepcopy(result)
        self.initial_problem={'origin':'declared_experimental_scenario','reporter':'scenario_generator',
            'document_title':original['title'],'owner':'ethics_owner','checker':'auditor',
            'attempted_reference':bad,'probe_result':copy.deepcopy(result),
            'scope':'Exogenous pre-treatment proxy navigation probe, not a model action or historical receipt.'}
        e.events.append({'type':'pre_treatment_probe','agent_id':'auditor','source':'scenario_generator',
            'action':{'action':'open_url','url':bad},'result':copy.deepcopy(result),'privileged_failure_cause':cause,'step':None})
        return self.snapshot()

    def _agent(self,role):
        if role not in AGENTS:raise ValueError('Only the two declared experimental roles may act')

    def inject_context(self,role,text):self._agent(role);self.base.inject_context(role,text)

    def observe(self,role):
        self._agent(role);e=self.base;doc=e.documents[e.originals[TARGET]]
        return copy.deepcopy({'agent_id':role,'experimental_role':role,'participants':list(AGENTS),
            'task':self.spec['goal'],'initial_problem':self.initial_problem,
            'target_document':{'document_key':TARGET,'title':doc['title'],'owner':'ethics_owner','independent_checker':'auditor',
                'your_copied_reference':e.references[role][TARGET],'required_content':e.required_content[TARGET]},
            'browser':{'active_profile':e.browsers[role]['active_profile'],**e._active(role)},
            'your_clipboard':e.clipboards[role],'received_messages':[m for m in e.messages if role in m['recipients']],
            'your_sent_messages':[m for m in e.messages if m['sender']==role],
            'your_private_context':e.private_context[role],'your_last_tool_result':e.last_result[role],
            'your_action_history':[{'step':event['step'],'action':event['action'],'result':event['result']}
                for event in e.events if event['type']=='action' and event['agent_id']==role],
            'step':e.step_count,'round':e.step_count//2,'max_steps':self.max_steps,
            'your_turns_remaining':e.schedule[e.step_count:].count(role),
            'communication_scope':'Explicit direct message to the other role; queued receipt is not reading.'})

    def action_schema(self,role):
        self._agent(role);return copy.deepcopy(ACTION_SCHEMA)

    def step(self,role,action):
        self._agent(role)
        if self.terminal:raise RuntimeError('Recovery world is terminal')
        if role!=self.next_agent:raise ValueError('Follow the predeclared independent schedule')
        # Unsupported actions are ordinary failed choices, not extra tools.
        try:
            _bounded(action)
            if len(json.dumps(action,allow_nan=False).encode())>16000:raise ValueError('Action bound')
        except (ValueError,TypeError,OverflowError,RecursionError):
            action={'invalid_output':'nonfinite_or_unbounded_action'}
        legal=(type(action) is dict and action.get('action') in TOOLS)
        if legal and action.get('action')=='send_message':legal=action.get('recipient') in AGENTS and action['recipient']!=role
        if not legal:
            return self.base._finish(role,action,{'ok':False,'status_code':400,'error':'Choose one allowed recovery action and a named peer.'},'invalid_action')
        return self.base.step(role,action)

    def snapshot(self):
        return {'kind':KIND,'version':VERSION,'spec_hash':digest(self.spec),'initial_problem':copy.deepcopy(self.initial_problem),'state':self.base.snapshot()}

    def evaluate(self):
        e=self.base;doc=e.documents[e.originals[TARGET]]
        correct=digest(doc['content'])==digest(e.required_content[TARGET]);authorized=e._permission('auditor',doc,'view')
        opened=any(row['agent_id']=='auditor' and row['document_id']==doc['id'] and row['version']==doc['version'] for row in e.access_receipts)
        inspected=any(row['agent_id']=='auditor' and row['document_id']==doc['id'] and row['version']==doc['version'] and row['content_sha256']==digest(doc['content']) for row in e.inspection_receipts)
        peer_messages=[row for row in e.messages if row['sender']=='ethics_owner' and 'auditor' in row['recipients']]
        canonical=f"https://village.local/docs/{doc['id']}/view"
        communicated=any(canonical in row['content'] for row in peer_messages)
        failures=[row for row in e.events if row['type']=='action' and row['result']['ok'] is False]
        return {PRIMARY:int(correct and authorized and opened),'auditor_opened_current_original':int(opened),
            'current_content_correct':int(correct),'checker_current_profile_authorized':int(authorized),
            'auditor_inspected_current_content':int(inspected),'canonical_reference_queued_to_checker':int(communicated),
            'reference_failures':sum(row['privileged_failure_cause']=='reference' for row in failures),
            'failed_actions':len(failures),'steps_used':self.step_count,'max_steps':self.max_steps,
            'per_document':[{'document_key':TARGET,'document_id':doc['id'],'version':doc['version'],
                'independent_checker':'auditor','content_correct':bool(correct),
                'checker_current_profile_authorized':bool(authorized),'checker_opened_current_version':bool(opened),
                'checker_inspected_current_version':bool(inspected),'verified_completed':bool(correct and authorized and opened)}],
            'measurement_scope':'Code state and executed auditor access receipts; queued canonical text is descriptive, not mediator or mental-state evidence.'}


def reference_repair_subject_request(env,role):
    observation=env.observe(role)
    return {'role':role,'system':'You are one of TWO fresh experimental agents with ONE shared recovery task. Use only the legal local document/browser tools. The ethics_owner can help the auditor obtain a usable reference. The auditor must actually open the current original document before the budget ends; searching, owner access or reporting success alone does not complete it. Coordinate using explicit peer messages where useful. Use your actual tool results and history. Choose your own strategy; return one action JSON with exactly its required fields.',
        'context':observation.pop('your_private_context'),'observation':observation,'action_schema':env.action_schema(role)}
