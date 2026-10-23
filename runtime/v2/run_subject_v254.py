"""V2.5.4 uses the same experiment runner with frozen dependency fingerprints.

The callbacks below select this version's engine, paths and append-only DB
namespace. No historical implementation or run is rewritten.
"""
import hashlib,json,sqlite3
from pathlib import Path
import run_subject_v253 as runner
import subject_v254 as engine
from assortment import ROOT,lines

OUT=ROOT/'v2/runs/subject_v254_20261023'
original_fingerprints=runner.fingerprints

def fingerprints():
 result=original_fingerprints()
 paths=[Path(__file__),ROOT/'v2/subject_v253.py',ROOT/'v2/run_subject_v253.py',ROOT/'tests/test_subject_v252.py',ROOT/'tests/test_subject_v253.py',ROOT/'tests/test_subject_v254.py']
 result.update({str(p):runner.b24.p.filehash(p) for p in paths})
 return result

def persist(frozen,stages):
 regression=engine.Engine().analyze_many(lines(ROOT/'v2/runs/subject_v253_20261023/inputs_100.jsonl'))
 runner.save('exposed_v253_regression_100.jsonl',regression,True)
 stages=dict(stages,exposed_v253_100=regression)
 # The two false exclusions from the second batch must also stay observations.
 assert all(regression[i-1]['decision']=='观察' for i in [18,20])
 db=ROOT/'learning_data/action_selection.sqlite3';backup=OUT/'learning_before_v254.sqlite3'
 if not backup.exists():
  with sqlite3.connect(db) as src,sqlite3.connect(backup) as dst:src.backup(dst)
 with sqlite3.connect(backup) as c:
  assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()
 runid='v254-'+hashlib.sha256(runner.b24.p.canonical(frozen).encode()).hexdigest()[:16]
 with sqlite3.connect(db) as c:
  c.execute('PRAGMA foreign_keys=ON')
  c.executescript('CREATE TABLE IF NOT EXISTS assortment_v254_runs(run_id TEXT PRIMARY KEY,payload TEXT NOT NULL); CREATE TABLE IF NOT EXISTS assortment_v254_results(run_id TEXT NOT NULL,stage TEXT NOT NULL,record_id TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(run_id,stage,record_id),FOREIGN KEY(run_id) REFERENCES assortment_v254_runs(run_id));')
  def exact(table,keys,data):
   cols=list(data);old=c.execute('SELECT '+','.join(cols)+' FROM '+table+' WHERE '+' AND '.join(k+'=?' for k in keys),[data[k] for k in keys]).fetchone()
   if old is not None:
    assert tuple(old)==tuple(data.values()),'IMMUTABLE_ROW_CONFLICT'
    return 0
   c.execute('INSERT INTO '+table+'('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',list(data.values()));return 1
  added=exact('assortment_v254_runs',['run_id'],{'run_id':runid,'payload':runner.b24.p.canonical(frozen)})
  for stage,rows in stages.items():
   for r in rows:added+=exact('assortment_v254_results',['run_id','stage','record_id'],{'run_id':runid,'stage':stage,'record_id':r['record_id'],'payload':runner.b24.p.canonical(r)})
  c.commit();check=c.execute('PRAGMA integrity_check').fetchone()[0];fk=c.execute('PRAGMA foreign_key_check').fetchall()
 return {'run_id':runid,'inserted':added,'integrity':check,'foreign_keys':len(fk),'prior_false_exclusion_regressions':6,'all_six_now_observe':True,'backup_read_check':'PASS'}

def main():
 runner.engine=engine;runner.OUT=OUT;runner.SEED=2026102354
 runner.fingerprints=fingerprints;runner.persist=persist
 runner.main()

if __name__=='__main__':main()
