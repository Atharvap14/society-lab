"""Server-only cache of validated compact inventory, never scientific objects.

The host supplies its fixed SQLite path. One persistent read-only observer and
one lock gate cached summaries by data_version and fixed DB/WAL file signatures.
A cache miss decodes every selected row with the actual Store._decode method in
one read transaction. Jobs, usage, capabilities and exact object reads belong
outside this cache.

An ordinary concurrent WAL commit can leave the returned validated inventory
at an earlier snapshot, as Store.list already does. Such a snapshot is not
published under the newer cache gate. File replacement or read/validation
failure discards the cache and fails closed. The file signatures help detect
replacement/direct edits; they are not a cryptographic filesystem attestation.
"""
import copy
import sqlite3
import stat
import threading
from pathlib import Path

from swarm_lab.store import Store


LATEST_SQL = '''SELECT o.* FROM objects o JOIN
    (SELECT id,MAX(version) v FROM objects GROUP BY id) latest
    ON o.id=latest.id AND o.version=latest.v
    WHERE 1=1 ORDER BY o.created DESC LIMIT ?'''


class CompactObjectInventoryCache:
    def __init__(self, path, *, limit=200, timeout=30):
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError('Compact inventory limit must be 1–200')
        if type(timeout) not in (int, float) or not 0 < timeout <= 30:
            raise ValueError('Read timeout must be positive and at most 30 seconds')
        self.path = Path(path).absolute()
        self.limit, self.timeout = limit, timeout
        self._lock = threading.RLock()
        self._connection = None
        self._connection_identity = None
        self._cache = None
        self._cache_key = None
        self._counts = {key: 0 for key in ('hits', 'misses', 'payload_fetches',
            'validated_objects', 'publications', 'racing_commits_not_cached',
            'connections_opened', 'replacement_invalidations', 'failures')}

    @staticmethod
    def _file_signature(path, *, required):
        try:
            info = path.stat()
        except FileNotFoundError:
            if required:
                raise ValueError('Registry database is missing') from None
            return None
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('Registry database and WAL must be regular files')
        return (info.st_dev, info.st_ino, info.st_size,
                info.st_mtime_ns, info.st_ctime_ns)

    def _signature(self):
        return (self._file_signature(self.path, required=True),
                self._file_signature(Path(str(self.path) + '-wal'), required=False))

    @staticmethod
    def _identity(signature):
        # Size/timestamps can legitimately advance on a checkpoint. File identity
        # alone controls reconnection; the full signature still gates cache hits.
        return signature[0][:2]

    def _discard(self, *, close=False):
        self._cache = self._cache_key = None
        if close:
            if self._connection is not None:
                try:
                    self._connection.close()
                except sqlite3.Error:
                    pass
            self._connection = None
            self._connection_identity = None

    def _ensure_connection(self, signature):
        identity = self._identity(signature)
        if self._connection is not None and identity != self._connection_identity:
            self._counts['replacement_invalidations'] += 1
            self._discard(close=True)
        if self._connection is None:
            connection = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True,
                timeout=self.timeout, check_same_thread=False, isolation_level=None)
            try:
                connection.row_factory = sqlite3.Row
                connection.execute('PRAGMA query_only=ON')
                if self._identity(self._signature()) != identity:
                    raise ValueError('Registry database was replaced while opening')
            except Exception:
                connection.close()
                raise
            self._connection, self._connection_identity = connection, identity
            self._counts['connections_opened'] += 1

    def _token(self):
        return self._connection.execute('PRAGMA data_version').fetchone()[0]

    @staticmethod
    def _decode_row(row):
        return Store._decode(row)

    @staticmethod
    def _compact(obj):
        p = obj['payload']
        summary = {'name': p.get('name', p.get('title', obj['kind'])),
            'status': p.get('status'), 'agent_mode': p.get('agent_mode'),
            'messages': len(p.get('messages', [])),
            'candidates': len(p.get('candidates', [])),
            'dataset_id': p.get('dataset_id'), 'behavior_id': p.get('behavior_id'),
            'research_quality_status': p.get('research_quality_status'),
            'protocol_ref': p.get('protocol_ref'),
            'corrected_review_behavior_id': p.get('corrected_review_behavior_id')}
        return {key: value for key, value in obj.items() if key != 'payload'} | {
            'summary': summary}

    def get(self):
        with self._lock:
            try:
                signature = self._signature()
                self._ensure_connection(signature)
                token = self._token()
                # Opening the pager for data_version can create its own empty
                # WAL/SHM sidecars. Start the validation gate after that setup;
                # this does not bless a changed token or later file modification.
                signature = self._signature()
                if self._identity(signature) != self._connection_identity:
                    self._counts['replacement_invalidations'] += 1
                    raise ValueError('Registry database was replaced while initializing')
                if self._cache is not None and self._cache_key == (signature, token):
                    result = copy.deepcopy(self._cache)
                    end_signature, end_token = self._signature(), self._token()
                    if self._identity(end_signature) != self._connection_identity:
                        self._counts['replacement_invalidations'] += 1
                        raise ValueError('Registry database was replaced while reading')
                    if (end_signature, end_token) == (signature, token):
                        self._counts['hits'] += 1
                        return result
                    # A commit raced the cheap gate. Start a fresh read snapshot;
                    # this is at most one full-payload query per get call.
                    self._discard()
                    signature, token = end_signature, end_token

                self._counts['misses'] += 1
                self._connection.execute('BEGIN')
                try:
                    rows = self._connection.execute(LATEST_SQL, (self.limit,)).fetchall()
                    self._counts['payload_fetches'] += 1
                    compact = []
                    for row in rows:
                        obj = self._decode_row(row)
                        self._counts['validated_objects'] += 1
                        compact.append(self._compact(obj))
                    self._connection.execute('COMMIT')
                except Exception:
                    self._connection.execute('ROLLBACK')
                    raise

                end_signature, end_token = self._signature(), self._token()
                if self._identity(end_signature) != self._connection_identity:
                    self._counts['replacement_invalidations'] += 1
                    raise ValueError('Registry database was replaced during validation')
                if (end_signature, end_token) == (signature, token):
                    self._cache = copy.deepcopy(compact)
                    self._cache_key = (signature, token)
                    self._counts['publications'] += 1
                else:
                    self._discard()
                    self._counts['racing_commits_not_cached'] += 1
                return copy.deepcopy(compact)
            except Exception:
                self._counts['failures'] += 1
                self._discard(close=True)
                raise

    @property
    def diagnostics(self):
        with self._lock:
            return dict(self._counts)

    def close(self):
        """Evict summaries and release the observer; a later get reconnects."""
        with self._lock:
            self._discard(close=True)
