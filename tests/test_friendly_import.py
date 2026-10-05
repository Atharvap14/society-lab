"""Strict first-use uploads, using authored rows and isolated temporary stores."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from swarm_lab.config import Settings
from swarm_lab.friendly_import import MAX_BYTES, MAX_ROWS, import_chat, parse_chat_import
from swarm_lab.pipeline import Lab
from swarm_lab.store import fingerprint


def message(identity='m-1', **updates):
    return {'id': identity, 'agent_speaker_id': 'alice', 'agent_name': 'Alice',
            'speaker_type': 'agent', 'room_id': 'team',
            'created_at': '2025-04-02T10:00:00Z', 'content': 'Bob, the draft needs your table.',
            **updates}


def request(rows, name='chat.jsonl'):
    content = '\n'.join(json.dumps(row, ensure_ascii=False) for row in rows)
    return json.dumps({'name': name, 'content': content}, ensure_ascii=False).encode('utf-8')


class FriendlyImportParsingTests(unittest.TestCase):
    def test_authored_sample_and_human_speaker_are_portable(self):
        sample = Path(__file__).resolve().parents[1] / 'examples/getting-started/sample-chat.jsonl'
        raw = json.dumps({'name': sample.name, 'content': sample.read_text(encoding='utf-8')}, ensure_ascii=False).encode('utf-8')
        name, rows, redacted = parse_chat_import(raw)
        self.assertEqual(name, 'sample-chat.jsonl')
        self.assertEqual(len(rows), 12)
        self.assertEqual({row['agent_speaker_id'] for row in rows}, {'alice', 'bob', 'carol'})
        self.assertFalse(redacted)
        human = message('human-1', speaker_type='user', user_speaker_id='operator')
        human.pop('agent_speaker_id')
        self.assertEqual(parse_chat_import(request([human]))[1][0]['speaker_type'], 'user')

    def test_bom_blank_lines_unicode_and_alias_timestamp(self):
        row = message(content='Bob, café and 雨 are literal text.')
        row['timestamp'] = row.pop('created_at')
        raw = b'\xef\xbb\xbf' + json.dumps({'name': '日本語.jsonl', 'content': '\n\n' + json.dumps(row, ensure_ascii=False) + '\n\n'}, ensure_ascii=False).encode('utf-8')
        name, rows, redacted = parse_chat_import(raw)
        self.assertEqual(name, '日本語.jsonl')
        self.assertEqual(rows, [row])
        self.assertFalse(redacted)

    def test_required_fields_have_strict_scalar_types_and_bounds(self):
        changes = ({'id': True}, {'id': ''}, {'id': 'x' * 201}, {'agent_speaker_id': 7},
                   {'agent_speaker_id': ' '}, {'speaker_type': 'human'}, {'speaker_type': True},
                   {'content': []}, {'content': '  '}, {'created_at': True},
                   {'created_at': 'not-a-time'}, {'room_id': None}, {'room_id': ' '},
                   {'room_id': 'r' * 201}, {'agent_name': False}, {'reply_to': 1},
                   {'reply_to_id': 'r' * 201})
        for changed in changes:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                parse_chat_import(request([message(**changed)]))

    def test_duplicate_message_ids_reject_whole_upload(self):
        with self.assertRaisesRegex(ValueError, 'Line 2'):
            parse_chat_import(request([message(), message(content='A different message')]))

    def test_redaction_cannot_collapse_distinct_message_ids(self):
        # Deliberately synthetic credential-shaped IDs; no real secret is used.
        first = message('sk-fixture_identifier_aaaaaaaaaaaaaaa')
        second = message('sk-fixture_identifier_bbbbbbbbbbbbbbb')
        with self.assertRaises(ValueError):
            parse_chat_import(request([first, second]))

    def test_redaction_cannot_silently_merge_speaker_or_room_identities(self):
        for field in ('agent_speaker_id', 'room_id'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                parse_chat_import(request([message(**{field: 'hf_fixture_structural_identity_aaaaaaaaa'})]))

    def test_duplicate_json_keys_reject_outer_and_inner_requests(self):
        inner = '{"id":"m-1","id":"m-2"}'
        examples = (b'{"name":"a","name":"b","content":""}',
                    json.dumps({'name': 'a', 'content': inner}).encode('utf-8'),
                    json.dumps({'name': 'a', 'content': json.dumps(message(source={'nested': 1})).replace('"nested": 1', '"nested": 1, "nested": 2')}).encode('utf-8'))
        for raw in examples:
            with self.subTest(raw_length=len(raw)), self.assertRaises(ValueError):
                parse_chat_import(raw)

    def test_malformed_nonobject_and_nonfinite_json_reject(self):
        for content in ('{', '[]', 'null', '{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}'):
            with self.subTest(content=content), self.assertRaises(ValueError):
                parse_chat_import(json.dumps({'name': 'chat.jsonl', 'content': content}).encode())
        for raw in (b'[]', b'{"name":"x","content":"","extra":1}', b'{"name":NaN,"content":"x"}', b'\xff'):
            with self.subTest(length=len(raw)), self.assertRaises((ValueError, UnicodeError)):
                parse_chat_import(raw)

    def test_request_byte_and_message_count_ceilings_are_enforced(self):
        for invalid in (b'', b'x' * (MAX_BYTES + 1), '', bytearray(b'{}')):
            with self.subTest(kind=type(invalid).__name__), self.assertRaises(ValueError):
                parse_chat_import(invalid)
        rows = [message('m-' + str(index)) for index in range(MAX_ROWS)]
        self.assertEqual(len(parse_chat_import(request(rows))[1]), MAX_ROWS)
        with self.assertRaises(ValueError):
            parse_chat_import(request(rows + [message('one-too-many')]))

    def test_empty_and_control_character_display_names_reject(self):
        for name in ('../../', '\\', 'chat\nname.jsonl', 'chat\x00name.jsonl'):
            with self.subTest(name=repr(name)), self.assertRaises(ValueError):
                parse_chat_import(request([message()], name))

class FriendlyImportIsolatedStoreTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.lab = Lab(Settings(root=self.root, max_calls=0))

    def test_import_keeps_agent_user_time_room_and_original_local_coordinates(self):
        human = {'id': 'operator-1', 'speaker_type': 'user', 'user_speaker_id': 'human',
                 'room_id': 'team', 'created_at': '2025-04-02T11:03:00+01:00', 'content': 'Please check the final version.'}
        rows = [message('late', created_at='2025-04-02T10:04:00Z', reply_to='early'),
                message('early', source={'file': 'https://untrusted.invalid/chat', 'line': 999, 'table': 'events'}), human]
        with patch.object(self.lab, 'harness', side_effect=AssertionError('No subject calls')), \
                patch.object(self.lab, 'research_harness', side_effect=AssertionError('No research calls')), \
                patch.object(self.lab.settings, 'api_key', side_effect=AssertionError('No credential access')):
            receipt = import_chat(self.lab, request(rows))
        obj = self.lab.store.get(receipt['dataset_ref']['id'], receipt['dataset_ref']['version'])
        self.assertEqual({key: obj[key] for key in ('id', 'version', 'hash')}, receipt['dataset_ref'])
        self.assertEqual(obj['kind'], 'dataset')
        self.assertEqual(obj['hash'], fingerprint(obj['payload']))
        messages = obj['payload']['messages']
        self.assertEqual([m['id'] for m in messages], ['early', 'operator-1', 'late'])
        self.assertEqual([m['source']['line'] for m in messages], [2, 3, 1])
        self.assertEqual(messages[1]['timestamp'], '2025-04-02T10:03:00.000000Z')
        self.assertIsNone(messages[1]['agent_id'])
        self.assertEqual(messages[1]['speaker_type'], 'user')
        self.assertEqual(messages[2]['reply_to'], 'early')
        source = Path(obj['payload']['provenance']['source'])
        self.assertTrue(source.resolve().is_relative_to(self.root.resolve()))
        self.assertEqual(source.name, 'chat_messages.jsonl')
        self.assertTrue(all(m['source']['file'] == str(source.resolve()) and m['source']['table'] == 'chat_messages' for m in messages))
        self.assertEqual(self.lab.store.usage()['calls'], 0)

    def test_display_paths_never_select_an_output_path_or_remote_source(self):
        for name, expected in (('../../outside.jsonl', 'outside.jsonl'),
                               ('C:\\private\\name.jsonl', 'name.jsonl'),
                               ('https://untrusted.invalid/name.jsonl', 'name.jsonl')):
            with self.subTest(name=name), patch('urllib.request.urlopen', side_effect=AssertionError('No remote fetch')):
                receipt = import_chat(self.lab, request([message()], name))
            obj = self.lab.store.get(receipt['dataset_ref']['id'])
            self.assertEqual(obj['payload']['provenance']['original_name'], expected)
            self.assertTrue(Path(obj['payload']['source']).is_relative_to(self.root))
        self.assertFalse((self.root / 'outside.jsonl').exists())
        self.assertEqual(self.lab.store.usage()['calls'], 0)

    def test_secrets_redacted_before_file_persistence_and_registry_versions_are_stable(self):
        secret = 'sk-fixture_secret_value_aaaaaaaaaaaaaaaaaaaa'
        upload = request([message(content='Example credential ' + secret + ' must be removed.')])
        first = import_chat(self.lab, upload)
        first_obj = self.lab.store.get(first['dataset_ref']['id'], 1)
        initial = copy.deepcopy(first_obj)
        self.assertTrue(first['redacted'])
        source = Path(first_obj['payload']['source'])
        self.assertNotIn(secret, source.read_text(encoding='utf-8'))
        self.assertNotIn(secret, json.dumps(first_obj, ensure_ascii=False))
        self.assertIn('[REDACTED_CREDENTIAL]', source.read_text(encoding='utf-8'))
        second = import_chat(self.lab, upload)
        self.assertNotEqual(first['dataset_ref']['id'], second['dataset_ref']['id'])
        self.assertEqual(self.lab.store.get(first['dataset_ref']['id'], 1), initial)
        self.assertEqual(first_obj['payload']['fingerprint'], self.lab.store.get(second['dataset_ref']['id'])['payload']['fingerprint'])
        self.assertEqual(self.lab.store.usage()['calls'], 0)

    def test_rejected_upload_creates_no_import_file_or_dataset(self):
        with self.assertRaises(ValueError):
            import_chat(self.lab, request([message(), message()]))
        self.assertFalse((self.root / '.runtime/imports').exists())
        self.assertEqual(self.lab.store.list(), [])
        self.assertEqual(self.lab.store.usage()['calls'], 0)


if __name__ == '__main__':
    unittest.main()
