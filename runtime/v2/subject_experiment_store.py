"""Immutable versioned subject experiments in the existing learning DB."""
import sqlite3
from assortment import ROOT
import boundary_v24 as b24

def persist(out,run_id,contract,stages):
 db=ROOT/'learning_data/action_selection.sqlite3';backup=out/'learning_before.sqlite3'
 if not backup.exists():
  with sqlite3.connect(db) as src,sqlite3.connect(backup) as dst:src.backup(dst)
 with sqlite3.connect(backup) as c:
  if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or c.execute('PRAGMA foreign_key_check').fetchall():raise RuntimeError('BACKUP_INVALID')
 with sqlite3.connect(db) as c:
  c.execute('PRAGMA foreign_keys=ON');c.executescript('CREATE TABLE IF NOT EXISTS assortment_subject_experiment_runs(run_id TEXT PRIMARY KEY,payload TEXT NOT NULL); CREATE TABLE IF NOT EXISTS assortment_subject_experiment_results(run_id TEXT NOT NULL,stage TEXT NOT NULL,record_id TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(run_id,stage,record_id),FOREIGN KEY(run_id) REFERENCES assortment_subject_experiment_runs(run_id));')
  def exact(table,keys,data):
   cols=list(data);old=c.execute('SELECT '+','.join(cols)+' FROM '+table+' WHERE '+' AND '.join(k+'=?' for k in keys),[data[k] for k in keys]).fetchone()
   if old is not None:
    if tuple(old)!=tuple(data.values()):raise RuntimeError('IMMUTABLE_ROW_CONFLICT')
    return 0
   c.execute('INSERT INTO '+table+'('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',list(data.values()));return 1
  added=exact('assortment_subject_experiment_runs',['run_id'],{'run_id':run_id,'payload':b24.p.canonical(contract)})
  for stage,rows in stages.items():
   for r in rows:added+=exact('assortment_subject_experiment_results',['run_id','stage','record_id'],{'run_id':run_id,'stage':stage,'record_id':r['record_id'],'payload':b24.p.canonical(r)})
  c.commit();integrity=c.execute('PRAGMA integrity_check').fetchone()[0];fk=c.execute('PRAGMA foreign_key_check').fetchall()
 return {'run_id':run_id,'inserted':added,'integrity':integrity,'foreign_keys':len(fk),'backup_read_check':'PASS'}
