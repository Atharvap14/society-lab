"""Authored temporary communication records, never inferred model reasoning."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from swarm_lab.config import Settings
from swarm_lab.dataset import ingest_village, normalize_message
from swarm_lab.observability_protocol import (_dataset_payload, _links, connect_observability,
    protocol_manifest, validate_batch)
from swarm_lab.pipeline import Lab
from swarm_lab.store import fingerprint


def batch(events):
    return {'schema_version': 'societylab.events.v1',
        'source': {'id': 'communication-test', 'name': 'Authored communication contract fixture', 'kind': 'authored_example'},
        'run': {'id': 'fixture-only'}, 'events': events}


def message(identity='post', visibility=None, recipients=None, **fields):
    data = {'content': 'A producer-recorded message.'} | fields
    if visibility is not None: data['visibility'] = visibility
    return {'id': identity, 'kind': 'message.sent', 'actor_id': 'actor-a',
        'occurred_at': '2026-10-05T12:00:00Z', 'recipient_ids': [] if recipients is None else recipients, 'data': data}


def reasoning(identity='note'):
    return {'id': identity, 'kind': 'reasoning.recorded', 'actor_id': 'actor-a',
        'occurred_at': '2026-10-05T12:00:00Z', 'recipient_ids': [],
        'data': {'content': 'A recorded decision rationale supplied by the producer, not hidden thought.'}}


def chat(**fields):
    return {'id': 'chat-a', 'agent_id': 'actor-a', 'speaker_type': 'agent',
        'created_at': '2026-10-05T12:00:00Z', 'content': 'Exact original text.'} | fields


class CommunicationMetadataTests(unittest.TestCase):
    def test_legacy_events_and_absent_normalized_metadata_do_not_gain_scope_labels(self):
        original = protocol_manifest()['example']
        self.assertEqual(validate_batch(original), original)
        normalized = normalize_message(chat())
        self.assertTrue({'visibility', 'channel_name', 'recipient_ids'}.isdisjoint(normalized))

    def test_explicit_visibility_routes_preserve_exact_names_recipients_without_membership_inference(self):
        events = [message('private', 'private'), message('direct', 'direct', ['actor-b']),
            message('room', 'room', ['actor-b'], channel_id='room-one', channel_name='Research room'),
            message('broadcast', 'broadcast', channel_name='General'), message('unknown', 'unknown', ['actor-b'])]
        original = copy.deepcopy(events)
        self.assertEqual(validate_batch(batch(events))['events'], original)
        self.assertEqual(events, original)

    def test_inconsistent_or_unknown_visibility_and_recipient_shapes_fail_closed(self):
        invalid = [message(visibility='private', recipients=['actor-b']),
            message(visibility='private', channel_name='Public'), message(visibility='direct'),
            message(visibility='direct', recipients=['actor-a']), message(visibility='room'),
            message(visibility='broadcast', recipients=['actor-b']), message(visibility='everyone_read'),
            message(visibility='direct', recipients=['actor-b', 'actor-b']), message(visibility='unknown', recipients=[True])]
        for event in invalid:
            with self.subTest(event=event), self.assertRaises(ValueError): validate_batch(batch([event]))
        for value in (None, True, 0, [], {}):
            event = message(); event['data']['visibility'] = value
            with self.assertRaises(ValueError): validate_batch(batch([event]))

    def test_reasoning_is_an_explicit_actor_local_record_and_never_an_addressed_reference(self):
        note = reasoning()
        self.assertEqual(validate_batch(batch([note]))['events'], [note])
        links = _links([note])['checks']
        self.assertEqual([row['relation'] for row in links], ['actor'])
        for variant in ({**note, 'recipient_ids': ['actor-b']}, {key: value for key, value in note.items() if key != 'recipient_ids'},
            {key: value for key, value in note.items() if key != 'actor_id'}, {**note, 'data': {'content': 'x', 'visibility': 'private'}},
            {**note, 'data': {'content': 'x', 'hidden_thought': 'fabricated'}}):
            with self.assertRaises(ValueError): validate_batch(batch([variant]))

    def test_bridge_keeps_only_message_records_and_original_explicit_metadata(self):
        value = batch([reasoning(), message('direct', 'direct', ['actor-b'], channel_name='Peer thread'),
            message('room', 'room', ['actor-b'], channel_id='room-one'), message('unspecified')])
        record = {'id': 'observability_run-test', 'version': 1, 'kind': 'observability_run',
            'hash': fingerprint(value), 'payload': value | {'provenance': {'source_kind': 'authored_example'}}}
        bridged = _dataset_payload(record)
        self.assertEqual([row['id'] for row in bridged['messages']], ['direct', 'room', 'unspecified'])
        self.assertEqual(bridged['messages'][0]['visibility'], 'direct')
        self.assertEqual(bridged['messages'][0]['channel_name'], 'Peer thread')
        self.assertEqual(bridged['messages'][1]['recipient_ids'], ['actor-b'])
        self.assertIsNone(bridged['messages'][2]['room_id'])
        self.assertNotIn('visibility', bridged['messages'][2])
        self.assertEqual(bridged['events'], [])

    def test_source_chat_normalization_retains_explicit_metadata_without_changing_text_identity_hash(self):
        old = normalize_message(chat(room_id='room-one'))
        row = chat(room_id='room-one', visibility='room', channel_name='Exact room label', recipient_ids=['actor-b'])
        original = copy.deepcopy(row)
        normalized = normalize_message(row)
        self.assertEqual(normalized['content_hash'], old['content_hash'])
        for key in ('visibility', 'channel_name', 'recipient_ids'): self.assertEqual(normalized[key], row[key])
        normalized['recipient_ids'].append('actor-c')
        self.assertEqual(row, original)

    def test_malformed_source_metadata_does_not_turn_into_guessed_visibility_or_addressing(self):
        invalid = [chat(visibility='direct'), chat(visibility='private', recipient_ids=['actor-b']),
            chat(visibility='broadcast', recipient_ids=['actor-b']), chat(visibility='room'),
            chat(recipient_ids=['actor-b', 'actor-b']), chat(recipient_ids=None), chat(recipient_ids=[1]),
            chat(channel_name=None), chat(channel_name=''), chat(visibility=True),
            chat(visibility='room', room_id=True), chat(visibility='direct', recipient_ids=['actor-a']),
            chat(speaker_type='user', user_speaker_id='human-a', visibility='direct', recipient_ids=['human-a'])]
        for row in invalid:
            with self.subTest(row=row), self.assertRaises(ValueError): normalize_message(row)

    def test_invalid_source_row_is_counted_while_valid_optional_fields_survive_actual_ingest(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'chat_messages.jsonl'
            source.write_text('\n'.join(json.dumps(row) for row in [chat(visibility='direct'),
                chat(visibility='room', room_id='room-one', channel_name='Research', recipient_ids=['actor-b'])]), encoding='utf-8')
            result = ingest_village(source)
            self.assertEqual(result['diagnostics']['chat']['invalid_rows'], 1)
            self.assertEqual(len(result['messages']), 1)
            self.assertEqual(result['messages'][0]['visibility'], 'room')
            self.assertEqual(result['messages'][0]['source']['line'], 2)

    def test_actual_atomic_intake_brief_and_bridge_keep_private_rationale_distinct(self):
        registration = {'id': 'register-a', 'kind': 'agent.registered', 'actor_id': 'actor-a',
            'occurred_at': '2026-10-05T12:00:00Z', 'data': {'name': 'Authored actor'}}
        value = batch([registration, reasoning(), message(visibility='room', recipients=['actor-b'], channel_name='Research')])
        with tempfile.TemporaryDirectory() as directory:
            lab = Lab(Settings(root=Path(directory), max_calls=0))
            result = connect_observability(lab, json.dumps(value).encode())
            run = lab.store.get(result['run_ref']['id'], result['run_ref']['version'])
            dataset = lab.store.get(result['dataset_ref']['id'], result['dataset_ref']['version'])
            brief = lab.store.get(result['brief_ref']['id'], result['brief_ref']['version'])
            self.assertEqual(run['payload']['events'], value['events'])
            self.assertEqual(len(dataset['payload']['messages']), 1)
            self.assertEqual(dataset['payload']['messages'][0]['visibility'], 'room')
            self.assertEqual(brief['payload']['counts']['retained_events'], 3)
            self.assertEqual(brief['payload']['counts']['retained_messages'], 1)
            self.assertEqual(lab.store.usage()['calls'], 0)


if __name__ == '__main__': unittest.main()
