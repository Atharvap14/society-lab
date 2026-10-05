"""Bounded optional measurements kept separate from deterministic screening.

An operationally failed backend is attempted once, then records unknown labels
for the rest of the selected sample. No negative or regex fallback is implied.
"""
from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

from .classifiers import (BackendUnavailable, BackendProtocolError, JevHTTPBackend,
                         LayaProcessBackend, TypedDecisionBackend, LAYA_MODEL_REVISION, build_questions)


def capabilities(root: Path) -> dict:
    executable = root / '.runtime/laya-venv/Scripts/python.exe'
    return {
        'default': 'regex',
        'backends': [
            {'id': 'regex', 'status': 'available', 'scope': 'Deterministic text screening; no calibrated semantic accuracy.'},
            {'id': 'laya', 'status': 'runtime_installed' if executable.is_file() else 'runtime_missing',
             'model_revision': LAYA_MODEL_REVISION, 'minimum_available_ram_gib': 2.5,
             'scope': 'Optional local CPU measurements; resources/checkpoint are checked at execution.'},
            {'id': 'jev', 'status': 'credential_configured' if os.environ.get('JEV_API_KEY') or os.environ.get('TYPESAFE_API_KEY') else 'credential_missing',
             'scope': 'Separate provider-specific credential and bounded request sample required.'},
        ],
        'max_sample_messages': 250,
        'interpretation': 'Optional labels do not replace regex motifs or establish behavior/outcomes.',
    }


class BoundedMeasurement:
    """Adapter used by discovery; explicit budget and serializable diagnostics."""
    def __init__(self, backend_name, messages, root, *, limit=32, on_status=None, factory=None):
        if backend_name not in ('laya', 'jev'):
            raise ValueError('Choose laya or jev for additional measurements')
        if type(limit) is not int or not 1 <= limit <= 250:
            raise ValueError('Measurement sample limit must be an integer from 1 to 250')
        ordered = sorted(messages, key=lambda m: (m.get('timestamp', m.get('created_at', '')), m['id']))
        if len({m['id'] for m in ordered}) != len(ordered):
            raise ValueError('Measurement message IDs must be unique')
        count = min(limit, len(ordered))
        # Uniform chronological coverage, selected before any backend output.
        positions = [i * (len(ordered) - 1) // max(1, count - 1) for i in range(count)]
        self.selected_ids = {ordered[i]['id'] for i in positions}
        self.name = backend_name
        self.root = Path(root)
        self.limit = limit
        self.on_status = on_status
        self.factory = factory
        self.backend = None
        self.error = None
        self.records = []
        self.last_measurement = None
        self.attempts = 0
        self.base = TypedDecisionBackend()
        self.base.name = backend_name

    def _create(self):
        if self.factory:
            return self.factory()
        if self.name == 'jev':
            return JevHTTPBackend(timeout=30)
        executable = self.root / '.runtime/laya-venv/Scripts/python.exe'
        if not executable.is_file():
            raise BackendUnavailable('Laya isolated runtime is missing; no installation or fallback was performed')
        return LayaProcessBackend(executable, timeout=90,
            cache_directory=self.root / '.runtime/laya-cache', on_status=self.on_status,
            revision=LAYA_MODEL_REVISION, max_state_tokens=200, max_tokens=512)

    def classify(self, message, definitions):
        if message['id'] not in self.selected_ids:
            record = self.base._abstain(message, build_questions(definitions),
                                       'outside_prespecified_measurement_sample')
            record['status'] = 'not_sampled'
        elif self.error:
            record = self.base.failure_record(message, definitions, self.error)
            record['subsequent_attempt_suppressed'] = True
        else:
            try:
                if self.backend is None:
                    self.backend = self._create()
                self.attempts += 1
                record = self.backend.measure(message, definitions)
            except (BackendUnavailable, BackendProtocolError, ValueError) as error:
                self.error = error
                record = self.base.failure_record(message, definitions, error)
                if self.on_status:
                    self.on_status({'phase': 'unavailable', 'reason': record.get('error')})
        self.last_measurement = record
        if message['id'] in self.selected_ids:
            self.records.append(record)
        return record['labels']

    def summary(self):
        statuses = dict(Counter(r['status'] for r in self.records))
        return {'backend': self.name, 'sample_selection': 'evenly_spaced_chronological_indices_before_measurement',
                'requested_limit': self.limit, 'selected_message_ids': sorted(self.selected_ids),
                'selected_messages': len(self.selected_ids), 'backend_attempts': self.attempts,
                'statuses': statuses, 'operational_error': str(self.error) if self.error else None,
                'fallback': 'none', 'motif_input': 'deterministic_regex_only',
                'limitations': ['This descriptive subsample is not a representative calibrated corpus benchmark.',
                                'Unknown/abstained observations do not imply absent behavior.']}

    def close(self):
        if self.backend is not None and hasattr(self.backend, 'close'):
            self.backend.close()
