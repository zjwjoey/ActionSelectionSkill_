"""Only boundary_learning_* tables may change; all rows are append-only."""
import json,sqlite3
from assortment import ROOT
import boundary_learning as b
DB=ROOT/'learning_data/action_selection.sqlite3'
SCHEMA='''CREATE TABLE IF NOT EXISTS boundary_learning_runs(run_id TEXT PRIMARY KEY,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS boundary_learning_results(run_id TEXT NOT NULL,stage TEXT NOT NULL,record_id TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(run_id,stage,record_id),FOREIGN KEY(run_id) REFERENCES boundary_learning_runs(run_id));
CREATE TABLE IF NOT EXISTS boundary_learning_ai_cache(cache_key TEXT PRIMARY KEY,run_id TEXT NOT NULL,payload TEXT NOT NULL,FOREIGN KEY(run_id) REFERENCES boundary_learning_runs(run_id));
CREATE TABLE IF NOT EXISTS boundary_learning_feedback(feedback_id TEXT PRIMARY KEY,record_id TEXT NOT NULL,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS boundary_learning_rule_candidates(rule_id TEXT NOT NULL,version TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(rule_id,version));
CREATE TABLE IF NOT EXISTS boundary_learning_rule_releases(release_id TEXT PRIMARY KEY,rule_id TEXT NOT NULL,version TEXT NOT NULL,payload TEXT NOT NULL);'''
def connect():
    c=sqlite3.connect(DB);c.execute('PRAGMA foreign_keys=ON');c.executescript(SCHEMA);return c
def exact(c,table,keys,data):
    columns=list(data);old=c.execute('SELECT '+','.join(columns)+' FROM '+table+' WHERE '+' AND '.join(k+'=?' for k in keys),[data[k] for k in keys]).fetchone()
    if old:
        if old!=tuple(data.values()):raise ValueError('IMMUTABLE_BOUNDARY_ROW_CONFLICT')
        return 0
    c.execute('INSERT INTO '+table+'('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',list(data.values()));return 1
def persist(runid,contract,stage,rows,caches=()):
    with connect() as c:
        count=exact(c,'boundary_learning_runs',['run_id'],{'run_id':runid,'payload':b.b24.p.canonical(contract)})
        for row in rows:count+=exact(c,'boundary_learning_results',['run_id','stage','record_id'],{'run_id':runid,'stage':stage,'record_id':row['record_id'],'payload':b.b24.p.canonical(row)})
        for a in caches:
            key=b.digest({'source_binding':a['source_binding'],'model':a['model'],'prompt':a['prompt_version'],'method':contract})
            count+=exact(c,'boundary_learning_ai_cache',['cache_key'],{'cache_key':key,'run_id':runid,'payload':b.b24.p.canonical(a)})
        c.commit()
    return count
