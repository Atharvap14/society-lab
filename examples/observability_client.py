"""Instrument your existing agents/tools; this file creates no demo agents.

Use SocietyEvents in your application, or run --file on an existing captured
societylab.events.v1 batch. The local server persists producer reports. Message
logging is not message delivery, and delivery is not proof of model reading.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import urllib.parse
import urllib.request
import uuid


class SocietyEvents:
    def __init__(self, source_id, source_name, run_id, *, harness=None, base_url='http://127.0.0.1:8765'):
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost') or parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
            raise ValueError('This SDK connects only to the local Society Lab server')
        self.base_url = base_url.rstrip('/')
        self.source = {'id': source_id, 'name': source_name, 'kind': 'telemetry'}
        if harness is not None: self.source['harness'] = harness
        self.run = {'id': run_id}
        self.events = []

    def emit(self, kind, data, *, actor_id=None, task_id=None, parent_task_id=None, recipient_ids=None):
        event = {'id': uuid.uuid4().hex, 'occurred_at': datetime.now(timezone.utc).isoformat(), 'kind': kind, 'data': data}
        for key, value in (('actor_id', actor_id), ('task_id', task_id), ('parent_task_id', parent_task_id), ('recipient_ids', recipient_ids)):
            if value is not None: event[key] = value
        self.events.append(event)
        return event['id']

    def register(self, actor_id, name, roles=None):
        return self.emit('agent.registered', {'name': name, **({'roles': roles} if roles is not None else {})}, actor_id=actor_id)

    def message_sent(self, actor_id, recipient_ids, content, *, task_id=None, channel_id=None, reply_to_message_id=None):
        # Call after your application's actual send operation. This method only logs.
        data = {'content': content}
        if channel_id is not None: data['channel_id'] = channel_id
        if reply_to_message_id is not None: data['reply_to_message_id'] = reply_to_message_id
        return self.emit('message.sent', data, actor_id=actor_id, task_id=task_id, recipient_ids=recipient_ids)

    def call_tool(self, actor_id, tool_name, arguments, function, *, task_id=None):
        """Wrap a real function; success means return without an exception.

        This operational transport result is not proof of semantic correctness.
        Emit tool.returned directly if your tool has a different success oracle.
        """
        call_id = uuid.uuid4().hex
        self.emit('tool.called', {'call_id': call_id, 'tool_name': tool_name, 'arguments': arguments}, actor_id=actor_id, task_id=task_id)
        try:
            output = function(**arguments)
        except Exception as error:
            self.emit('tool.returned', {'call_id': call_id, 'success': False, 'output': {'error_type': type(error).__name__}}, actor_id=actor_id, task_id=task_id)
            raise
        self.emit('tool.returned', {'call_id': call_id, 'success': True, 'output': output}, actor_id=actor_id, task_id=task_id)
        return output

    def flush(self):
        if not self.events: raise ValueError('No real events have been recorded')
        batch = {'schema_version': 'societylab.events.v1', 'source': self.source, 'run': self.run, 'events': self.events}
        result = post_batch(batch, self.base_url)
        self.events = []  # A failure preserves IDs/timestamps for exact retries.
        return result


def post_batch(batch, base_url='http://127.0.0.1:8765'):
    # Validate the local origin even for the command-line file uploader.
    client = SocietyEvents('validation-only', 'URL check', 'validation-only', base_url=base_url)
    with urllib.request.urlopen(client.base_url + '/api/state', timeout=30) as response:
        token = json.load(response)['csrf']
    encoded = json.dumps(batch, ensure_ascii=False, allow_nan=False).encode('utf-8')
    request = urllib.request.Request(client.base_url + '/api/observability/connect', data=encoded,
        headers={'Content-Type': 'application/json', 'X-Lab-Token': token})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Connect an existing swarm telemetry batch to local Society Lab')
    parser.add_argument('--file', required=True, type=Path, help='Your captured societylab.events.v1 JSON batch')
    parser.add_argument('--url', default='http://127.0.0.1:8765')
    args = parser.parse_args()
    if args.file.stat().st_size > 1048576: parser.error('The server accepts batches under1 MiB')
    def unique_keys(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('Duplicate captured JSON key')
            result[key] = value
        return result
    with args.file.open(encoding='utf-8') as stream: captured = json.load(stream, object_pairs_hook=unique_keys)
    print(json.dumps(post_batch(captured, args.url), indent=2))
