"""Immutable experimental namespace in the existing shared V3 learning store."""
import json
from runtime.v3.core import canonical,digest
from runtime.v3.store import Store

class State:
    def __init__(self,path):
        self.store=Store(path);self.db=self.store.db
        self.db.execute('CREATE TABLE IF NOT EXISTS v31_events(id TEXT PRIMARY KEY,kind TEXT NOT NULL,payload TEXT NOT NULL)')
        self.db.execute('CREATE INDEX IF NOT EXISTS v31_events_kind ON v31_events(kind)');self.db.commit()
    def put(self,kind,payload):
        key=kind+'-'+digest(payload)[:24];body=canonical(payload)
        old=self.db.execute('SELECT kind,payload FROM v31_events WHERE id=?',(key,)).fetchone()
        if old and old!=(kind,body):raise ValueError('IMMUTABLE_EXPERIMENT_CONFLICT')
        self.db.execute('INSERT OR IGNORE INTO v31_events VALUES(?,?,?)',(key,kind,body));self.db.commit();return key
    def get(self,key,kind=None):
        r=self.db.execute('SELECT kind,payload FROM v31_events WHERE id=?',(key,)).fetchone()
        if not r or (kind and r[0]!=kind):raise ValueError('EXPERIMENT_EVENT_NOT_FOUND')
        payload=json.loads(r[1])
        if key!=r[0]+'-'+digest(payload)[:24]:raise ValueError('EXPERIMENT_EVENT_HASH_MISMATCH')
        return payload
    def all(self,kind):
        result=[]
        for key,body in self.db.execute('SELECT id,payload FROM v31_events WHERE kind=? ORDER BY id',(kind,)):
            payload=json.loads(body)
            if key!=kind+'-'+digest(payload)[:24]:raise ValueError('EXPERIMENT_EVENT_HASH_MISMATCH')
            result.append((key,payload))
        return result
    def close(self):self.store.close()
