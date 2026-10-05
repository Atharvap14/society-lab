"""Append-only research objects, version history, traces, and atomic call budget."""
import datetime as dt
import hashlib
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def clean(value):
    # Redaction is applied on persistence and before external model input.
    raw = json.dumps(value, ensure_ascii=False)
    raw = re.sub(r"(?:sk-proj-|sk-|hf_)[A-Za-z0-9_\-]{15,}", "[REDACTED_CREDENTIAL]", raw)
    return json.loads(raw)

def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


class StoreConflictError(ValueError):
    """A compare-and-put expected a different immutable checkpoint version."""
    def __init__(self,object_id,expected_ref,latest_ref):
        super().__init__(f'Checkpoint conflict for {object_id}; another writer advanced the object')
        self.object_id=object_id
        self.expected_ref=expected_ref
        self.latest_ref=latest_ref


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS objects(id TEXT,version INTEGER,kind TEXT,created TEXT,payload TEXT,hash TEXT,PRIMARY KEY(id,version));
            CREATE TABLE IF NOT EXISTS traces(id TEXT PRIMARY KEY,job_id TEXT,created TEXT,payload TEXT);
            CREATE TABLE IF NOT EXISTS calls(id TEXT PRIMARY KEY,created TEXT,status TEXT,usage TEXT);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,status TEXT,created TEXT,updated TEXT,payload TEXT);
            ''')

    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.path,timeout=30)
        c.row_factory=sqlite3.Row
        c.execute('PRAGMA journal_mode=WAL')
        try:
            with c:yield c
        finally:c.close()

    def put(self,kind,payload,object_id=None):
        payload=clean(payload)
        object_id=object_id or f'{kind}-{uuid.uuid4().hex[:12]}'
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            existing=c.execute('SELECT kind FROM objects WHERE id=? LIMIT 1',(object_id,)).fetchone()
            if existing and existing['kind']!=kind:raise ValueError('An object ID cannot change kind across versions')
            version=c.execute('SELECT COALESCE(MAX(version),0)+1 FROM objects WHERE id=?',(object_id,)).fetchone()[0]
            c.execute('INSERT INTO objects VALUES(?,?,?,?,?,?)',(object_id,version,kind,now(),json.dumps(payload,ensure_ascii=False),fingerprint(payload)))
        return self.get(object_id)

    def get(self,object_id,version=None):
        with self.connect() as c:
            if version is None:
                r=c.execute('SELECT * FROM objects WHERE id=? ORDER BY version DESC LIMIT 1',(object_id,)).fetchone()
            else:
                r=c.execute('SELECT * FROM objects WHERE id=? AND version=?',(object_id,version)).fetchone()
        if r is None: raise KeyError(object_id)
        return self._decode(r)

    def compare_and_put(self,kind,payload,object_id,*,expected_version,expected_hash,job_updates=None):
        """Append only to the exact expected version and optionally publish jobs.

        At most two typed job updates are in the same transaction. A guarded
        failure update can preserve an already completed child's status. The
        returned object is the inserted version, never a racing latest read.
        """
        if type(kind) is not str or not 1<=len(kind)<=80 or type(object_id) is not str or not 1<=len(object_id)<=200:
            raise ValueError('Compare-and-put requires bounded kind and object ID strings')
        if type(expected_version) is not int or not 1<=expected_version<=1000000000:
            raise ValueError('Expected version must be a positive integer')
        if type(expected_hash) is not str or not re.fullmatch(r'[0-9a-f]{64}',expected_hash):
            raise ValueError('Expected hash must be a lowercase SHA-256')
        updates=[] if job_updates is None else job_updates
        if type(updates) is not list or len(updates)>2:
            raise ValueError('At most two typed job updates can accompany a checkpoint')
        prepared=[];identities=set()
        for update in updates:
            if type(update) is not dict or set(update)!={'id','status','payload','preserve_completed'}:
                raise ValueError('Job update requires id, status, payload and preserve_completed')
            identity=update['id']
            if type(identity) is not str or not 1<=len(identity)<=200 or identity in identities:
                raise ValueError('Job identities must be distinct bounded strings')
            if type(update['status']) is not str or update['status'] not in ('running','completed','failed') or type(update['preserve_completed']) is not bool or type(update['payload']) is not dict:
                raise ValueError('Invalid typed checkpoint job update')
            identities.add(identity)
            cleaned=clean(update['payload'])
            prepared.append({**update,'payload':json.dumps(cleaned,ensure_ascii=False,allow_nan=False)})
        payload=clean(payload)
        encoded=json.dumps(payload,ensure_ascii=False,allow_nan=False)
        digest=fingerprint(payload)
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            latest=c.execute('SELECT * FROM objects WHERE id=? ORDER BY version DESC LIMIT 1',(object_id,)).fetchone()
            latest_ref={key:latest[key] for key in ('kind','id','version','hash')} if latest else None
            expected_ref={'kind':kind,'id':object_id,'version':expected_version,'hash':expected_hash}
            if latest_ref!=expected_ref:
                raise StoreConflictError(object_id,expected_ref,latest_ref)
            # Validate bytes under the lock, just as get() validates a read.
            self._decode(latest)
            inserted_version=expected_version+1
            c.execute('INSERT INTO objects VALUES(?,?,?,?,?,?)',(object_id,inserted_version,kind,now(),encoded,digest))
            for update in prepared:
                prior=c.execute('SELECT status FROM jobs WHERE id=?',(update['id'],)).fetchone()
                if update['preserve_completed'] and prior and prior['status']=='completed':
                    continue
                c.execute('INSERT INTO jobs VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,updated=excluded.updated,payload=excluded.payload',
                    (update['id'],update['status'],now(),now(),update['payload']))
            inserted=c.execute('SELECT * FROM objects WHERE id=? AND version=?',(object_id,inserted_version)).fetchone()
            result=self._decode(inserted)
        return result

    @staticmethod
    def _decode(row):
        result={**dict(row),'payload':json.loads(row['payload'])}
        if fingerprint(result['payload'])!=result['hash']:raise ValueError('Stored object payload does not match its immutable hash')
        return result

    def list(self,kind=None,limit=100):
        where='AND o.kind=?' if kind else ''
        args=[kind,limit] if kind else [limit]
        with self.connect() as c:
            rows=c.execute(f'SELECT o.* FROM objects o JOIN (SELECT id,MAX(version) v FROM objects GROUP BY id) latest ON o.id=latest.id AND o.version=latest.v WHERE 1=1 {where} ORDER BY o.created DESC LIMIT ?',args).fetchall()
        return [self._decode(r) for r in rows]

    def history(self,object_id):
        with self.connect() as c: rows=c.execute('SELECT * FROM objects WHERE id=? ORDER BY version',(object_id,)).fetchall()
        return [self._decode(r) for r in rows]

    def trace(self,job_id,payload):
        with self.connect() as c:c.execute('INSERT INTO traces VALUES(?,?,?,?)',(uuid.uuid4().hex,job_id,now(),json.dumps(clean(payload),ensure_ascii=False)))

    def traces(self,job_id):
        with self.connect() as c:rows=c.execute('SELECT * FROM traces WHERE job_id=? ORDER BY created',(job_id,)).fetchall()
        return [{**dict(r),'payload':json.loads(r['payload'])} for r in rows]

    def reserve_call(self,max_calls):
        call_id=uuid.uuid4().hex
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            n=c.execute('SELECT COUNT(*) FROM calls').fetchone()[0]
            if n>=max_calls:raise RuntimeError(f'API call budget reached ({max_calls}); explicitly raise the cap to continue')
            c.execute('INSERT INTO calls VALUES(?,?,?,?)',(call_id,now(),'reserved','{}'))
        return call_id

    def finish_call(self,call_id,status,usage=None):
        with self.connect() as c:c.execute('UPDATE calls SET status=?,usage=? WHERE id=?',(status,json.dumps(usage or {}),call_id))

    def usage(self):
        with self.connect() as c:rows=c.execute('SELECT status,usage FROM calls').fetchall()
        usages=[json.loads(r['usage']) for r in rows]
        return {'calls':len(rows),'completed':sum(r['status']=='completed' for r in rows),'input_tokens':sum(x.get('input_tokens',0) for x in usages),'output_tokens':sum(x.get('output_tokens',0) for x in usages)}

    def job(self,job_id,status,payload):
        with self.connect() as c:
            c.execute('INSERT INTO jobs VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,updated=excluded.updated,payload=excluded.payload',(job_id,status,now(),now(),json.dumps(clean(payload))))

    def start_job(self,job_id,payload):
        """Claim a fixed execution identity atomically before any costly work."""
        with self.connect() as c:
            try:c.execute('INSERT INTO jobs VALUES(?,?,?,?,?)',(job_id,'running',now(),now(),json.dumps(clean(payload))))
            except sqlite3.IntegrityError:raise ValueError('This job was already launched; inspect its saved record') from None

    def job_exists(self,job_id):
        with self.connect() as c:return c.execute('SELECT 1 FROM jobs WHERE id=?',(job_id,)).fetchone() is not None

    def get_job(self,job_id):
        with self.connect() as c:row=c.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        return {**dict(row),'payload':json.loads(row['payload'])} if row else None

    def jobs(self,statuses=None,limit=30):
        if type(limit) is not int or not 1<=limit<=10000:raise ValueError('Job listing limit must be between 1 and 10000')
        if statuses is not None and (not isinstance(statuses,(list,tuple)) or not statuses or any(s not in ('queued','running','completed','failed') for s in statuses)):
            raise ValueError('Choose valid job statuses')
        where=' WHERE status IN ('+','.join('?' for _ in statuses)+')' if statuses else ''
        with self.connect() as c:rows=c.execute('SELECT * FROM jobs'+where+' ORDER BY created DESC LIMIT ?',(*(statuses or ()),limit)).fetchall()
        return [{**dict(r),'payload':json.loads(r['payload'])} for r in rows]
