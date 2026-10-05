"""Exact local presentation of declared measurement judgments; no model calls."""
import re
import json
import math
from pathlib import Path

from .measurement_adjudication import sample_packet, review_report

MAX_PLAN_BYTES = 16 * 1024


def read_review_plan(path):
    with Path(path).open('rb') as handle:
        raw = handle.read(MAX_PLAN_BYTES + 1)
    if len(raw) > MAX_PLAN_BYTES:
        raise ValueError('Measurement review plan exceeds 16 KiB')
    def pairs(entries):
        values = {}
        for key, value in entries:
            if key in values:
                raise ValueError('Duplicate measurement review plan key')
            values[key] = value
        return values
    def constant(value):
        raise ValueError('Measurement review plans require finite JSON')
    def number(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError('Measurement review plans require finite JSON')
        return result
    result = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                        parse_constant=constant, parse_float=number)
    if type(result) is not dict:
        raise ValueError('Measurement review plan must be an object')
    return result


def parse_review_query(query):
    required = {'sample_id', 'sample_version', 'review_id', 'review_version'}
    allowed = required | {'include_predictions'}
    if type(query) is not dict or not required <= set(query) or not set(query) <= allowed:
        raise ValueError('Use exact sample and review identities and versions')
    values = {}
    for key, entries in query.items():
        if type(entries) is not list or len(entries) != 1 or type(entries[0]) is not str or not entries[0]:
            raise ValueError('Review query fields must be single nonempty values')
        values[key] = entries[0]
    for key in ('sample_id', 'review_id'):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,199}', values[key]):
            raise ValueError('Invalid review object identity')
    for key in ('sample_version', 'review_version'):
        if not re.fullmatch(r'[1-9][0-9]{0,9}', values[key]) or int(values[key]) > 1000000000:
            raise ValueError('Review versions must be canonical positive integers')
        values[key] = int(values[key])
    visibility = values.pop('include_predictions', 'false')
    if visibility not in ('true', 'false'):
        raise ValueError('include_predictions must be true or false')
    values['include_predictions'] = visibility == 'true'
    return values


def measurement_review_workspace(store, *, sample_id, sample_version,
                                 review_id, review_version, include_predictions=False):
    for identity in (sample_id, review_id):
        if type(identity) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,199}', identity):
            raise ValueError('Invalid review object identity')
    for version in (sample_version, review_version):
        if type(version) is not int or not 1 <= version <= 1000000000:
            raise ValueError('Review versions must be positive integer values')
    if type(include_predictions) is not bool:
        raise ValueError('Prediction visibility must be a boolean')
    sample = store.get(sample_id, sample_version)
    review = store.get(review_id, review_version)
    if sample['kind'] != 'measurement_sample' or review['kind'] != 'measurement_review':
        raise ValueError('Review source kinds do not match')
    sample_ref = {key: sample[key] for key in ('id', 'version', 'hash')}
    review_ref = {key: review[key] for key in ('id', 'version', 'hash')}
    packet = sample_packet(store, sample_ref, review_ref, include_predictions=include_predictions)
    report = review_report(store, sample_ref, review_ref)
    return {'packet': packet, 'report': report}
