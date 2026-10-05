"""Small local chat imports for the first-use UI; no model calls or remote upload."""
import json
import uuid
from pathlib import Path

from .dataset import ingest_village, iter_jsonl, normalize_message, parse_time
from .store import clean

MAX_BYTES = 1024 * 1024
MAX_ROWS = 2000


def _pairs(entries):
    result = {}
    for key, value in entries:
        if key in result:
            raise ValueError('Repeated JSON field: ' + key)
        result[key] = value
    return result


def _constant(value):
    raise ValueError('Use ordinary JSON values, without NaN or Infinity')


def parse_chat_import(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError('Choose a chat file under 1 MB')
    request = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=_pairs, parse_constant=_constant)
    if type(request) is not dict or set(request) != {'name', 'content'}:
        raise ValueError('Send a file name and JSONL chat content')
    name, content = request['name'], request['content']
    if type(name) is not str or not 1 <= len(name) <= 200 or type(content) is not str:
        raise ValueError('Use a short file name and text chat content')
    rows, identities = [], set()
    for number, line in enumerate(content.splitlines(), 1):
        if not line.strip():
            continue
        if len(rows) >= MAX_ROWS:
            raise ValueError('Start with at most 2,000 messages. Use Advanced tools for a larger source.')
        try:
            row = json.loads(line, object_pairs_hook=_pairs, parse_constant=_constant)
            if type(row) is not dict:
                raise ValueError('Each line must be one JSON message')
            if type(row.get('id')) is not str or not row['id'].strip() or len(row['id']) > 200:
                raise ValueError('Every message needs a short, unique id')
            if row['id'] in identities:
                raise ValueError('Message ids must be unique')
            if row.get('speaker_type') not in ('agent', 'user'):
                raise ValueError('speaker_type must be agent or user')
            speaker = (row.get('agent_speaker_id') or row.get('agent_id') or row.get('speaker_id')) if row['speaker_type'] == 'agent' else (row.get('user_speaker_id') or row.get('speaker_id'))
            if type(speaker) is not str or not speaker.strip() or len(speaker) > 200:
                raise ValueError('Every message needs a speaker id')
            if type(row.get('content')) is not str or not row['content'].strip():
                raise ValueError('Every message needs text content')
            time = row.get('created_at') or row.get('timestamp')
            if type(time) is not str or parse_time(time) is None:
                raise ValueError('Every message needs an ISO date and time')
            if type(row.get('room_id')) is not str or not row['room_id'].strip() or len(row['room_id']) > 200:
                raise ValueError('Every message needs a room_id')
            for field in ('agent_name', 'reply_to', 'reply_to_id'):
                if row.get(field) is not None and (type(row[field]) is not str or len(row[field]) > 200):
                    raise ValueError(field + ' must be short text')
            # Validate the same normalization that the research importer uses.
            normalize_message(row)
            identities.add(row['id'])
            rows.append(row)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError(f'Line {number}: {exc}') from exc
    if not rows:
        raise ValueError('This file has no messages. Try the example first.')
    sanitized = clean(rows)
    for original, filtered in zip(rows, sanitized):
        for field in ('id', 'agent_speaker_id', 'agent_id', 'speaker_id', 'user_speaker_id', 'room_id', 'reply_to', 'reply_to_id'):
            if original.get(field) != filtered.get(field):
                raise ValueError('A credential-like value was used as a message, speaker, room or reply id. Use ordinary ids instead.')
    # A client-supplied file name is a display label only, never a disk path.
    display_name = name.replace('\\', '/').rsplit('/', 1)[-1]
    if not display_name.strip() or any(ord(c) < 32 or ord(c) == 127 for c in display_name):
        raise ValueError('Use a readable chat file name without control characters')
    return display_name, sanitized, sanitized != rows


def import_chat(lab, raw):
    name, rows, redacted = parse_chat_import(raw)
    folder = lab.settings.runtime / 'imports' / uuid.uuid4().hex
    folder.mkdir(parents=True)
    source = folder / 'chat_messages.jsonl'
    source.write_text('\n'.join(json.dumps(row, ensure_ascii=False, allow_nan=False) for row in rows) + '\n', encoding='utf-8')
    payload = ingest_village(source, limit=MAX_ROWS)
    sample = lab.settings.root / 'examples' / 'getting-started' / 'sample-chat.jsonl'
    is_authored = sample.is_file() and rows == [row for _, row in iter_jsonl(sample)]
    origin = 'authored_example' if is_authored else 'user_import'
    payload['provenance'] = {'origin': origin, 'original_name': name,
                             'source': str(source.resolve()), 'scope': payload['scope'],
                             'fingerprint': payload['fingerprint'], 'redaction_applied': redacted}
    record = lab.store.put('dataset', payload)
    return {'dataset_ref': {key: record[key] for key in ('id', 'version', 'hash')},
            'messages': len(payload['messages']), 'source_kind': origin, 'redacted': redacted}
