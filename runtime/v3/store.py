"""One portable shared SQLite state; immutable namespace for V3."""
import json,sqlite3
from pathlib import Path
from .core import canonical
class Store:
    def __init__(self,path):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists() and path.stat().st_size:
            probe=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
            try:
                if probe.execute('PRAGMA application_id').fetchone()[0]!=1095972403:raise ValueError('V3_DEDICATED_DATABASE_REQUIRED')
            finally:probe.close()
        self.db=sqlite3.connect(path,timeout=60);self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA application_id=1095972403')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS v3_runs(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS v3_sources(id TEXT NOT NULL,hash TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(id,hash));
        CREATE TABLE IF NOT EXISTS v3_analyses(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS v3_results(run_id TEXT NOT NULL,record_id TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(run_id,record_id),FOREIGN KEY(run_id) REFERENCES v3_runs(id));
        CREATE TABLE IF NOT EXISTS v3_feedback(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS v3_rule_candidates(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS v3_rule_validation(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS v3_rule_releases(id TEXT PRIMARY KEY,payload TEXT NOT NULL);''');self.db.commit()
    def exact(self,table,keys,payload):
        if table not in {'v3_runs','v3_sources','v3_analyses','v3_results','v3_feedback','v3_rule_candidates','v3_rule_validation','v3_rule_releases'}:raise ValueError('INVALID_TABLE')
        old=self.db.execute('SELECT payload FROM '+table+' WHERE '+' AND '.join(k+'=?' for k in keys),tuple(keys.values())).fetchone()
        body=canonical(payload)
        if old:
            if old[0]!=body:raise ValueError('IMMUTABLE_ROW_CONFLICT')
            return 0
        cols=list(keys)+['payload'];self.db.execute('INSERT INTO '+table+'('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',tuple(keys.values())+(body,));return 1
    def get(self,table,key):
        row=self.db.execute('SELECT payload FROM '+table+' WHERE id=?',(key,)).fetchone()
        return json.loads(row[0]) if row else None
    def all(self,table):return [json.loads(r[0]) for r in self.db.execute('SELECT payload FROM '+table+' ORDER BY id')]
    def check(self):
        return {'integrity':self.db.execute('PRAGMA integrity_check').fetchone()[0],'foreign_keys':len(self.db.execute('PRAGMA foreign_key_check').fetchall())}
    def close(self):self.db.close()
