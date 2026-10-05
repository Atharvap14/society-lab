"""Zero-call screening of source-pinned agent activity.

An observation here attests to a field in the retained record, not to a tool's
success, a message's reception, or an agent's intent. Candidates are prompts
for a subsequent investigation. No behavior/library status is changed.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import re

from .store import clean, fingerprint

BRIEF_VERSION = 'societylab.proactive-brief.v1'
SCREEN_VERSION = 'recorded-activity-screen-v1'
MAX_ROWS = 2000
MAX_INPUT_BYTES = 4 * 1024 * 1024
MAX_OUTPUT_BYTES = 192 * 1024
MAX_EVIDENCE = 20
TOOL_WINDOW_SECONDS = 300
CHAT_SCREEN_CHARACTERS = 16000
KINDS = frozenset(('agent.registered', 'task.created', 'task.assigned',
    'task.completed', 'message.sent', 'reasoning.recorded', 'tool.called', 'tool.returned',
    'artifact.updated', 'intervention.delivered'))
FAMILIES = frozenset(('shared_artifact_coordination', 'provenance_diffusion',
                     'complementary_information', 'exclusive_resource_tasks'))
_WAIT = re.compile(r"\b(?:waiting (?:on|for)|blocked|cannot (?:proceed|continue|access)|can't (?:proceed|continue|access))\b", re.I)
_CHECK = re.compile(r'\b(?:please (?:verify|check)|can (?:you|someone) (?:verify|check)|check (?:the |current )?(?:file|artifact|version))\b', re.I)
_CORRECTION = re.compile(r'\b(?:correction|I retract|I was wrong|previous (?:claim|statement) was (?:wrong|incorrect))\b', re.I)
_COMPLETION = re.compile(r"\b(?:I (?:have |'?ve )?(?:finished|completed)|(?:draft|task|report|artifact) (?:is )?(?:done|ready|complete))\b", re.I)
_CREDENTIAL = re.compile(r'(?:sk-proj-|sk-|hf_)[A-Za-z0-9_\-]{15,}')


def _bounded_json(value):
    """Bound accepted/retained JSON, not a Store.get decoder's allocations."""
    stack = [(value, 0)]
    nodes = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if depth > 12 or nodes > 2000000:
            raise ValueError('Brief input exceeds its JSON depth/node ceiling')
        if type(item) is dict:
            if len(item) > 256 or any(type(k) is not str for k in item):
                raise ValueError('Brief objects require bounded string keys')
            stack.extend((v, depth + 1) for v in item.values())
        elif type(item) is list:
            if len(item) > MAX_ROWS:
                raise ValueError('Brief input lists exceed 2,000 retained rows')
            stack.extend((v, depth + 1) for v in item)
        elif item is not None and type(item) not in (str, bool, int, float):
            raise ValueError('Brief input must be finite JSON')
        elif type(item) is float and not math.isfinite(item):
            raise ValueError('Brief input must be finite JSON')
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
    except (ValueError, RecursionError, OverflowError):
        raise ValueError('Brief input is not bounded finite JSON') from None
    if len(encoded) > MAX_INPUT_BYTES:
        raise ValueError('Brief input exceeds the 4 MiB accepted-body ceiling')


def _text(value, field, maximum=200, nullable=False):
    if nullable and value is None:
        return None
    if type(value) is not str or not 1 <= len(value) <= maximum or any(ord(c) < 32 for c in value):
        raise ValueError(f'{field} must be a bounded nonempty string')
    if _CREDENTIAL.search(value):
        raise ValueError(f'{field} cannot contain a credential-shaped identity')
    return value


def _label(value, field, maximum=1000):
    # Display labels, unlike IDs, can contain whitespace in the intake schema.
    if type(value) is not str or not value.strip() or len(value) > maximum:
        raise ValueError(f'{field} must be bounded nonblank display text')
    return value


def _time(value):
    _text(value, 'occurred_at', 80)
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError()
        return stamp.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise ValueError('Brief timestamps require explicit UTC or a UTC offset') from None


def _ref(record, kind):
    if type(record) is not dict or record.get('kind') != kind or type(record.get('payload')) is not dict:
        raise ValueError(f'Expected an exact {kind} registry object')
    _text(record.get('id'), 'record.id')
    if type(record.get('version')) is not int or not 1 <= record['version'] <= 10**9:
        raise ValueError('Record version must be a positive integer')
    if type(record.get('hash')) is not str or not re.fullmatch('[0-9a-f]{64}', record['hash']):
        raise ValueError('Record hash must be a lowercase SHA-256')
    _bounded_json(record['payload'])
    if fingerprint(record['payload']) != record['hash']:
        raise ValueError('Brief source body does not match its immutable registry hash')
    return {k: record[k] for k in ('id', 'version', 'hash')}


def _ids(values, field):
    if type(values) is not list or len(values) > 128:
        raise ValueError(f'{field} must be a bounded ID list')
    result = [_text(x, field) for x in values]
    if len(set(result)) != len(result):
        raise ValueError(f'{field} cannot repeat an ID')
    return result


def _events(payload):
    if payload.get('schema_version') != 'societylab.events.v1':
        raise ValueError('Unsupported observability event schema')
    rows = payload.get('events')
    if type(rows) is not list or len(rows) > MAX_ROWS:
        raise ValueError('Brief requires at most 2,000 retained events')
    ordered = []
    seen = set()
    required = {'id', 'occurred_at', 'kind', 'data'}
    for original in rows:
        if type(original) is not dict or not required <= set(original) or type(original['data']) is not dict:
            raise ValueError('Events require the typed societylab.events.v1 envelope')
        # Optional scope fields stay optional in the authoritative source. Only
        # this local screening view normalizes absent relationship fields.
        row = {**original, 'actor_id': original.get('actor_id'),
            'task_id': original.get('task_id'), 'parent_task_id': original.get('parent_task_id'),
            'recipient_ids': original.get('recipient_ids', [])}
        identity = _text(row['id'], 'event.id')
        if identity in seen:
            raise ValueError('Duplicate event IDs cannot be interpreted as retries')
        seen.add(identity)
        if type(row['kind']) is not str or row['kind'] not in KINDS:
            raise ValueError('Unsupported activity event kind')
        if row['kind'] in ('message.sent', 'reasoning.recorded', 'intervention.delivered') and 'recipient_ids' not in original:
            raise ValueError('Addressed message/intervention events require explicit recipient_ids')
        for key in ('actor_id', 'task_id', 'parent_task_id'):
            _text(row[key], key, nullable=True)
        _ids(row['recipient_ids'], 'recipient_ids')
        d = row['data']
        if row['kind'] == 'agent.registered' and row['actor_id'] is None:
            raise ValueError('Registration requires an actor ID')
        if row['kind'] == 'agent.registered':
            _label(d.get('name'), 'agent name')
        if row['kind'] in ('task.created', 'task.assigned', 'task.completed') and row['task_id'] is None:
            raise ValueError('Task events require a task ID')
        if row['kind'] == 'task.assigned':
            _ids(d.get('assignee_ids'), 'assignee_ids')
        if row['kind'] in ('tool.returned', 'task.completed') and type(d.get('success')) is not bool:
            raise ValueError('Reported completion/return success must be an exact boolean')
        if row['kind'] in ('tool.called', 'tool.returned'):
            _text(d.get('call_id'), 'call_id')
        if row['kind'] == 'tool.called':
            _label(d.get('tool_name'), 'tool_name')
        if row['kind'] in ('message.sent', 'reasoning.recorded') and (type(d.get('content')) is not str or len(d['content']) > CHAT_SCREEN_CHARACTERS):
            raise ValueError('Message content must be a string of at most 16,000 characters')
        if row['kind'] == 'reasoning.recorded' and (row['actor_id'] is None or row['recipient_ids'] or set(d) != {'content'}):
            raise ValueError('Recorded local reasoning requires its actor, empty recipients and content only')
        if row['kind'] == 'message.sent':
            _message_visibility(d, row['actor_id'], row['recipient_ids'])
        ordered.append((_time(row['occurred_at']), identity, row))
    ordered.sort(key=lambda x: (x[0], x[1]))
    return [x[2] for x in ordered]


def _message_visibility(data, actor, recipients):
    """Validate explicit declarations; a channel alone is not an audience."""
    visibility = data.get('visibility')
    if visibility is not None and (type(visibility) is not str or visibility not in ('private', 'direct', 'room', 'broadcast', 'unknown')):
        raise ValueError('Message visibility requires a supported explicit declaration')
    channel = data.get('channel_id')
    if channel is not None:
        _text(channel, 'channel_id')
    name = data.get('channel_name')
    if name is not None:
        _label(name, 'channel_name')
    if visibility == 'private' and (recipients or channel is not None or name is not None):
        raise ValueError('Private messages cannot declare recipients or a channel')
    if visibility == 'direct' and not any(r != actor for r in recipients):
        raise ValueError('Direct messages require an explicit peer recipient')
    if visibility == 'room' and channel is None and name is None:
        raise ValueError('Room messages require an explicit channel')
    if visibility == 'broadcast' and recipients:
        raise ValueError('Broadcast messages do not enumerate addressed recipients')


def _dataset(record):
    ref = _ref(record, 'dataset')
    for key in ('provenance', 'source_refs'):
        if key in record['payload'] and type(record['payload'][key]) is not dict:
            raise ValueError(f'Dataset {key} must be a typed object when supplied')
    origin = record['payload'].get('provenance', {}).get('origin')
    if origin is not None:
        _text(origin, 'dataset provenance.origin', 80)
    rows = record['payload'].get('messages')
    if type(rows) is not list or len(rows) > MAX_ROWS:
        raise ValueError('Chat brief requires at most 2,000 retained messages')
    seen = set()
    messages = []
    for row in rows:
        if type(row) is not dict:
            raise ValueError('Messages must be typed objects')
        identity = _text(row.get('id'), 'message.id')
        if identity in seen:
            raise ValueError('Duplicate original message IDs')
        seen.add(identity)
        if row.get('speaker_type') not in ('agent', 'user', 'human'):
            raise ValueError('Message speaker type must distinguish agents from users')
        if type(row.get('content')) is not str:
            raise ValueError('Message content must be a string')
        _time(row.get('timestamp') or row.get('created_at'))
        _text(row.get('room_id'), 'room_id', nullable=True)
        if row['speaker_type'] == 'agent':
            _text(row.get('agent_id'), 'agent_id')
            name = row.get('agent_name')
            if name is not None:
                _label(name, 'agent_name')
        elif row.get('agent_id') is not None:
            raise ValueError('Human messages cannot be assigned an agent identity')
        recipients = _ids(row.get('recipient_ids', []), 'recipient_ids')
        _message_visibility({k: row[k] for k in ('visibility', 'channel_name') if k in row} |
            ({'channel_id': row['room_id']} if row.get('room_id') is not None and row.get('visibility') == 'room' else {}),
            row.get('agent_id'), recipients)
        messages.append(row)
    return ref, sorted(messages, key=lambda x: (_time(x.get('timestamp') or x.get('created_at')), x['id']))


def _finish(events, source_refs, *, chat_messages=None, source_kind='telemetry'):
    messages = chat_messages or []
    agent_names = {}
    registrations = defaultdict(list)
    for e in events:
        if e['kind'] == 'agent.registered':
            aid = e['actor_id']
            name = e['data'].get('name', aid)
            name = name if type(name) is str and 0 < len(name) <= 1000 else aid
            agent_names.setdefault(aid, name)
            registrations[aid].append(e['id'])
    # The chat adapter's explicit agent rows establish its speaker inventory;
    # no role/registration event is invented from a name mention.
    for m in messages:
        if m['speaker_type'] == 'agent':
            agent_names.setdefault(m['agent_id'], m.get('agent_name') or m['agent_id'])
    known = set(agent_names)
    agent_posts = [e for e in events if e['kind'] == 'message.sent' and e['actor_id'] in known]
    private_posts = [e for e in agent_posts if e['data'].get('visibility') == 'private']
    local_reasoning = [e for e in events if e['kind'] == 'reasoning.recorded']
    sends = [e for e in agent_posts if e['data'].get('visibility') != 'private']
    unknown_actors = sorted({e['actor_id'] for e in events if e['actor_id'] is not None and e['actor_id'] not in known})
    tasks = {}
    for e in events:
        tid = e['task_id']
        if tid is None:
            continue
        task = tasks.setdefault(tid, {'id': tid, 'title': tid, 'creation_recorded': False,
            'parent_task_ids': [], 'assignee_ids': [], 'source_declared_status': 'unknown', 'evidence_event_ids': []})
        if e['kind'].startswith('task.'):
            task['evidence_event_ids'].append(e['id'])
        if e['parent_task_id'] and e['parent_task_id'] not in task['parent_task_ids']:
            task['parent_task_ids'].append(e['parent_task_id'])
        if e['kind'] == 'task.created':
            task['creation_recorded'] = True
            title = e['data'].get('title')
            if type(title) is str and title:
                task['title'] = title[:200]
            task['source_declared_status'] = 'created'
        elif e['kind'] == 'task.assigned':
            task['assignee_ids'] = e['data']['assignee_ids'][:]
            task['source_declared_status'] = 'assigned'
        elif e['kind'] == 'task.completed':
            task['source_declared_status'] = 'reported_complete' if e['data']['success'] else 'reported_unsuccessful'
    signals = []

    def signal(code, title, interpretation, severity, evidence, question, alternatives, family=None, **metrics):
        evidence = sorted({e['id']: e for e in evidence}.values(), key=lambda e: (_time(e['occurred_at']), e['id']))
        signal_row = {'code': code, 'title': title, 'interpretation': interpretation, 'severity': severity,
            'evidence_event_ids': [e['id'] for e in evidence[:MAX_EVIDENCE]],
            'evidence_message_ids': list(dict.fromkeys(e['_message_id'] for e in evidence if e.get('_message_id')))[:MAX_EVIDENCE],
            'evidence_count': len(evidence), 'evidence_truncated': len(evidence) > MAX_EVIDENCE,
            'question': question, 'alternative_explanations': alternatives, 'next_test_family': family,
            'metrics': metrics, 'claim_scope': 'retained_source_records_only'}
        signals.append(signal_row)

    failed = [e for e in events if e['kind'] == 'tool.returned' and e['data']['success'] is False]
    if failed:
        signal('reported_tool_error', 'A tool return reported an error', 'observed', 'needs_attention', failed,
            'Would verifying the tool result before a handoff reduce incorrect task completion?',
            ['The failure may be expected input validation.', 'The producer may report success or error incorrectly.', 'A later recovery may be outside this retained batch.'],
            'shared_artifact_coordination', reported_error_returns=len(failed))
    calls = [e for e in events if e['kind'] == 'tool.called' and e['actor_id'] in known]
    retries = defaultdict(list)
    groups = defaultdict(list)
    for e in calls:
        retries[(e['actor_id'], e['task_id'], e['data']['call_id'])].append(e)
        if e['task_id'] is not None:
            groups[(e['actor_id'], e['task_id'], e['data']['tool_name'])].append(e)
    repeat_ids = [g for g in retries.values() if len(g) >= 2]
    if repeat_ids:
        signal('same_call_id_repeated', 'The same tool call ID was submitted again', 'candidate', 'needs_attention',
            [e for g in repeat_ids for e in g], 'Does an explicit retry limit prevent repeated submissions without reducing successful recovery?',
            ['The sender may retransmit a recorded request.', 'The same ID may mean a resumed operation rather than a new attempt.', 'A reused ID can also be a logging defect.'],
            None, call_id_groups=len(repeat_ids))
    bursts = []
    for group in groups.values():
        left = 0
        for right, e in enumerate(group):
            while (_time(e['occurred_at']) - _time(group[left]['occurred_at'])).total_seconds() > TOOL_WINDOW_SECONDS:
                left += 1
            if right - left + 1 >= 3:
                bursts.extend(group[left:right + 1])
    if bursts:
        signal('tool_call_cluster', 'Several calls used the same tool for one task', 'candidate', 'unknown', bursts,
            'Are these calls useful incremental work, or would a shared progress check avoid redundant calls?',
            ['Polling, paging and incremental edits naturally require repeated calls.', 'Argument contents and verified results were not compared.', 'Concurrent tasks can share a tool without sharing a goal.'],
            'shared_artifact_coordination', minimum_calls=3, window_seconds=TOOL_WINDOW_SECONDS,
            grouping='exact_actor_task_tool_name; overlapping_windows_deduplicated')
    handoffs = []
    previous = {}
    for e in events:
        if e['kind'] != 'task.assigned':
            continue
        tid, assignees = e['task_id'], set(e['data']['assignee_ids'])
        old = previous.get(tid)
        if old and not old[2] and old[1] != assignees and _time(old[0]['occurred_at']) < _time(e['occurred_at']):
            handoffs.extend([old[0], e])
        ambiguous = bool(old and _time(old[0]['occurred_at']) == _time(e['occurred_at']) and (old[2] or old[1] != assignees))
        previous[tid] = (e, assignees, ambiguous)
    if handoffs:
        signal('declared_assignment_change', 'A task was assigned to a different set of agents', 'observed', 'unknown', handoffs,
            'Does passing the current artifact version with a task handoff reduce incorrect publication?',
            ['The change may reflect ordinary delegation or parallel ownership.', 'Assignments do not show acceptance, completion or an actual transfer.'],
            'shared_artifact_coordination')
    completions = [e for e in events if e['kind'] == 'task.completed' and e['data']['success'] is True]
    if completions:
        signal('reported_task_completion', 'The source reports completed tasks', 'observed', 'helpful', completions,
            'Would an independent artifact check distinguish a completion report from a correct final result?',
            ['These are producer-declared results.', 'The completion criterion may differ between tasks.'],
            'shared_artifact_coordination', reported_completed_tasks=len({e['task_id'] for e in completions}))
    updates = [e for e in events if e['kind'] == 'artifact.updated']
    if updates:
        signal('recorded_artifact_update', 'The source records changes to an artifact', 'observed', 'unknown', updates,
            'When an artifact changes, does a version-qualified handoff prevent teammates using an old copy?',
            ['An update does not show who later inspected the artifact.', 'The producer may use its own version or completion convention.'],
            'shared_artifact_coordination', artifact_update_records=len(updates), verified_inspection='unknown')
    edge_groups = defaultdict(list)
    unresolved = []
    for e in sends:
        for recipient in e['recipient_ids']:
            if recipient not in known:
                unresolved.append({'event_id': e['id'], 'recipient_id': recipient})
            elif recipient != e['actor_id']:
                edge_groups[(e['actor_id'], recipient)].append(e)
    if len(sends) >= 4 and edge_groups:
        outgoing = Counter()
        for (actor, _), group in edge_groups.items():
            outgoing[actor] += len(group)
        actor, count = sorted(outgoing.items(), key=lambda x: (-x[1], x[0]))[0]
        total = sum(outgoing.values())
        if count >= 3 and count / total >= .5:
            focal = [e for (a, _), group in edge_groups.items() if a == actor for e in group]
            signal('concentrated_recorded_sends', 'One agent accounts for many addressed sends', 'candidate', 'unknown', focal,
                'Does changing who can share evidence change team accuracy when every agent holds different information?',
                ['A coordinator role may legitimately send most messages.', 'Broadcast recipient counts create more edges per message.', 'Unaddressed room posts are not recipient deliveries.'],
                'complementary_information', actor_id=actor, addressed_recipient_entries=count,
                all_known_nonself_recipient_entries=total, share=count / total)
    patterns = [('waiting_language', _WAIT, 'Some agent messages use waiting language', 'needs_attention',
                 'Can agents complete independent work while one shared resource is unavailable?', 'exclusive_resource_tasks'),
                ('artifact_check_language', _CHECK, 'An agent asks for a check', 'helpful',
                 'Does a check-the-current-file reminder improve correct publication compared with a neutral note?', 'shared_artifact_coordination'),
                ('correction_language', _CORRECTION, 'An agent explicitly uses correction language', 'helpful',
                 'Do recipients use a corrected, source-qualified claim rather than an earlier claim?', 'provenance_diffusion'),
                ('completion_language', _COMPLETION, 'An agent says work is finished or ready', 'unknown',
                 'Do teammates verify the final artifact before treating a completion report as publication-ready?', 'shared_artifact_coordination')]
    text_censored = 0
    for code, regex, title, severity, question, family in patterns:
        matches = []
        spans = []
        for e in sends:
            content = e['data']['content']
            match = regex.search(content[:CHAT_SCREEN_CHARACTERS])
            if match:
                matches.append(e)
                if len(spans) < MAX_EVIDENCE:
                    spans.append({'event_id': e['id'], 'message_id': e.get('_message_id'),
                                  'start': match.start(), 'end': match.end(), 'text': match.group(0)})
        if matches:
            signal(code, title, 'candidate', severity, matches, question,
                ['The text can be quoted, hypothetical or about a different task.',
                 'A phrase does not measure actual waiting, checking, completion or beliefs.',
                 'This English-language screen has no established semantic accuracy.'], family,
                agent_message_denominator=len(sends), matched_agent_messages=len(matches), spans=spans,
                semantic_accuracy='not_established')
    for e in sends:
        if e.get('_content_truncated'):
            text_censored += 1
    agent_rows = []
    for aid in sorted(known):
        agent_rows.append({'id': aid, 'name': agent_names[aid][:200],
            'name_truncated': len(agent_names[aid]) > 200,
            'registered_event_ids': registrations[aid][:MAX_EVIDENCE],
            'message_count': sum(e['actor_id'] == aid for e in sends),
            'private_message_count': sum(e['actor_id'] == aid for e in private_posts),
            'recorded_local_reasoning_count': sum(e['actor_id'] == aid for e in local_reasoning),
            'tool_call_count': sum(e['actor_id'] == aid for e in calls),
            'declared_task_ids': sorted({e['task_id'] for e in events if e['task_id'] and
                (e['actor_id'] == aid or (e['kind'] == 'task.assigned' and aid in e['data']['assignee_ids']))})[:100],
            'inventory_basis': 'explicit_chat_agent_speaker' if not registrations[aid] else 'recorded_registration'})
    task_rows = [tasks[k] for k in sorted(tasks)]
    for task in task_rows:
        task['evidence_event_ids'] = task['evidence_event_ids'][:MAX_EVIDENCE]
        task['unknown_assignee_ids'] = [a for a in task['assignee_ids'] if a not in known]
        task['verified_completion'] = None
    task_limit = min(len(task_rows), 100)
    agent_limit = min(len(agent_rows), 128)
    summary = f"This log contains {len(known)} explicitly identified agent{'s' if len(known) != 1 else ''}, {len(agent_posts)} agent message{'s' if len(agent_posts) != 1 else ''}, and {len(tasks)} task ID{'s' if len(tasks) != 1 else ''}."
    if private_posts or local_reasoning:
        summary += f" {len(private_posts)} explicitly private agent post{'s' if len(private_posts) != 1 else ''} and {len(local_reasoning)} recorded local reasoning item{'s' if len(local_reasoning) != 1 else ''} are counted separately and excluded from communication and language screens."
    if signals:
        summary += ' Start with a recorded signal below, read its evidence, then choose a question to explore.'
    else:
        summary += ' None of the predefined screens matched; that does not establish an absence of interesting behavior.'
    clarifications = ['What outcome would count as success for this team?', 'Which task, agent or time span should we investigate first?']
    if not tasks:
        clarifications.append('Task IDs were not recorded. Which messages belong to the task you care about?')
    if any(s['code'] == 'waiting_language' for s in signals):
        clarifications.append('What was unavailable, and what other work could the waiting agent do?')
    result = {'brief_version': BRIEF_VERSION, 'screen_version': SCREEN_VERSION, 'available': True,
        'source_refs': source_refs, 'source_kind': source_kind, 'summary': summary,
        'agents': agent_rows[:agent_limit], 'tasks': task_rows[:task_limit], 'signals': signals,
        'clarifications': clarifications,
        'counts': {'retained_events': len(events), 'retained_messages': len(messages) if messages else sum(e['kind'] == 'message.sent' for e in events),
                   'agent_messages': len(sends), 'total_agent_messages': len(agent_posts), 'private_agent_messages': len(private_posts),
                   'recorded_local_reasoning': len(local_reasoning),
                   'nonagent_or_unregistered_messages': sum(e['kind'] == 'message.sent' for e in events) - len(agent_posts),
                   'known_agents': len(known), 'task_ids': len(tasks), 'signals': len(signals),
                   'known_nonself_addressed_entries': sum(len(g) for g in edge_groups.values()),
                   'unresolved_recipient_entries': len(unresolved), 'chat_contents_screened_partially': text_censored},
        'communication': {'edges': [{'source': a, 'target': b, 'recorded_send_count': len(group),
                                    'evidence_event_ids': [e['id'] for e in group[:MAX_EVIDENCE]]}
                                   for (a, b), group in sorted(edge_groups.items())][:256],
                          'edge_groups_total': len(edge_groups), 'edge_groups_truncated': len(edge_groups) > 256,
                          'unresolved_recipients': unresolved[:MAX_EVIDENCE],
                          'meaning': 'Explicit addressed sends only; reception and influence are unknown.'},
        'scope': {'accepted_input_json_bytes_max': MAX_INPUT_BYTES, 'accepted_rows_max': MAX_ROWS,
                  'same_tool_window_seconds': TOOL_WINDOW_SECONDS, 'same_tool_minimum_calls': 3,
                  'message_screen_characters_max': CHAT_SCREEN_CHARACTERS, 'evidence_per_signal_max': MAX_EVIDENCE,
                  'agents_total': len(agent_rows), 'agents_truncated': len(agent_rows) > agent_limit,
                  'tasks_total': len(task_rows), 'tasks_truncated': len(task_rows) > task_limit,
                  'unknown_actor_ids': unknown_actors[:MAX_EVIDENCE], 'unknown_actor_ids_total': len(unknown_actors),
                  'ordering': 'UTC timestamp then event ID; simultaneous assignment changes are not handoffs'},
        'limitations': ['This is deterministic screening, not an AI-generated explanation or a novel-behavior finding.',
            'Observed means an explicit retained record; producer reports are not independently verified.',
            'Missing events, outcomes, recipients and task boundaries remain unknown.',
            'Explicit private posts and recorded local reasoning are counted separately and excluded from communication and language screens. Hidden model reasoning is unavailable; missing visibility remains unknown.',
            'Helpful and needs-attention labels indicate a review opportunity; they do not establish good, harmful or malicious intent.',
            'A suggested test family requires environment-fit review and a frozen experiment plan before execution.',
            'Whole teams, not messages or agents within them, are the experimental units for a team intervention.'],
        'fresh_source_attestation': False, 'registry_body_hash_checked': True,
        'model_calls': 0, 'database_writes': 0, 'novelty_established': False,
        'source_truth_verified': False, 'status_changes': [], 'hypothesis_enrichment': 'not_run'}
    result = clean(result)
    if len(json.dumps(result, ensure_ascii=False, allow_nan=False).encode()) > MAX_OUTPUT_BYTES:
        raise ValueError('Brief exceeds its retained-output ceiling; reduce the source scope')
    return result


def build_brief(run_record, dataset_record=None):
    """Screen one exact observability_run, optionally binding its chat bridge."""
    run_ref = _ref(run_record, 'observability_run')
    events = _events(run_record['payload'])
    refs = {'run_ref': run_ref}
    messages = []
    if dataset_record is not None:
        dataset_ref, messages = _dataset(dataset_record)
        declared = dataset_record['payload'].get('source_refs', {})
        bridge_ref = declared.get('run_ref') or declared.get('observability_run_ref')
        if bridge_ref != run_ref or type(bridge_ref) is not dict or set(bridge_ref) != {'id', 'version', 'hash'} or type(bridge_ref.get('version')) is not int:
            raise ValueError('The chat bridge must bind the exact observability run')
        source_messages = {e['id']: e for e in events if e['kind'] == 'message.sent'}
        if set(source_messages) != {m['id'] for m in messages}:
            raise ValueError('The chat bridge must retain every recorded message event exactly once')
        for message in messages:
            event = source_messages.get(message['id'])
            if (event is None or message['content'] != event['data']['content'] or message['agent_id'] != event['actor_id']
                or _time(message.get('timestamp') or message.get('created_at')) != _time(event['occurred_at'])
                or message.get('recipient_ids', []) != event['recipient_ids']
                or any(message.get(k) != event['data'].get(k) for k in ('visibility', 'channel_name'))):
                raise ValueError('Chat bridge messages must exactly match recorded message events')
        refs['dataset_ref'] = dataset_ref
    copied = [dict(e, data=dict(e['data']), _message_id=e['id'] if e['kind'] == 'message.sent' and messages else None) for e in events]
    source = run_record['payload'].get('source', {})
    if type(source) is not dict or source.get('kind') not in ('telemetry', 'authored_example'):
        raise ValueError('Run source must declare telemetry or authored_example origin')
    return _finish(copied, refs, chat_messages=messages,
        source_kind=source['kind'])


def build_chat_brief(dataset_record):
    """Screen imported chat posts without inventing telemetry/task outcomes."""
    dataset_ref, messages = _dataset(dataset_record)
    events = []
    for m in messages:
        # Every stable derived event retains an original message ID. Human rows
        # stay in the denominator but cannot register an agent or produce leads.
        events.append({'id': 'chat-' + hashlib.sha256(m['id'].encode()).hexdigest()[:24],
            'occurred_at': m.get('timestamp') or m['created_at'], 'kind': 'message.sent',
            'actor_id': m['agent_id'] if m['speaker_type'] == 'agent' else None,
            'task_id': None, 'parent_task_id': None,
            'recipient_ids': _ids(m.get('recipient_ids', []), 'recipient_ids'),
            'data': {'content': m['content'][:CHAT_SCREEN_CHARACTERS],
                **{k: m[k] for k in ('visibility', 'channel_name') if k in m}},
            '_message_id': m['id'], '_content_truncated': len(m['content']) > CHAT_SCREEN_CHARACTERS})
    result = _finish(events, {'dataset_ref': dataset_ref}, chat_messages=messages,
        source_kind=dataset_record['payload'].get('provenance', {}).get('origin', 'imported_chat'))
    result['limitations'].append('Chat posts supply no tool results, task lifecycle or resource-availability telemetry; words are not actions.')
    result['scope']['derived_chat_event_ids'] = True
    return result
