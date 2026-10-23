"""Final bounded experiment: reuse runner, freeze V2.5.5, sample another 100."""
import json,hashlib,sqlite3
from pathlib import Path
import run_subject_v253 as runner
import subject_v255 as engine
from assortment import ROOT,lines

OUT=ROOT/'v2/runs/subject_v255_20261023'
original_fingerprints=runner.fingerprints
def fingerprints():
 fp=original_fingerprints()
 for name in ['v2/run_subject_v255.py','v2/subject_v253.py','v2/subject_v254.py','v2/run_subject_v253.py',
              'tests/test_subject_v252.py','tests/test_subject_v253.py','tests/test_subject_v254.py','tests/test_subject_v255.py']:
  p=ROOT/name;fp[str(p)]=runner.b24.p.filehash(p)
 return fp

def persist(frozen,stages):
 e=engine.Engine()
 for v in ['253','254']:
  rows=e.analyze_many(lines(ROOT/f'v2/runs/subject_v{v}_20261023/inputs_100.jsonl'))
  runner.save(f'exposed_v{v}_regression_100.jsonl',rows,True);stages=dict(stages,**{f'exposed_v{v}_100':rows})
  false_ids=[18,20] if v=='253' else [5]
  assert all(rows[i-1]['decision']=='观察' for i in false_ids)
 db=ROOT/'learning_data/action_selection.sqlite3';backup=OUT/'learning_before_v255.sqlite3'
 if not backup.exists():
  with sqlite3.connect(db) as src,sqlite3.connect(backup) as dst:src.backup(dst)
 with sqlite3.connect(backup) as c:
  assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()
 runid='v255-'+hashlib.sha256(runner.b24.p.canonical(frozen).encode()).hexdigest()[:16]
 with sqlite3.connect(db) as c:
  c.execute('PRAGMA foreign_keys=ON');c.executescript('CREATE TABLE IF NOT EXISTS assortment_v255_runs(run_id TEXT PRIMARY KEY,payload TEXT NOT NULL); CREATE TABLE IF NOT EXISTS assortment_v255_results(run_id TEXT NOT NULL,stage TEXT NOT NULL,record_id TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(run_id,stage,record_id),FOREIGN KEY(run_id) REFERENCES assortment_v255_runs(run_id));')
  def exact(table,keys,data):
   cols=list(data);old=c.execute('SELECT '+','.join(cols)+' FROM '+table+' WHERE '+' AND '.join(k+'=?' for k in keys),[data[k] for k in keys]).fetchone()
   if old is not None:
    assert tuple(old)==tuple(data.values()),'IMMUTABLE_ROW_CONFLICT'
    return 0
   c.execute('INSERT INTO '+table+'('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',list(data.values()));return 1
  added=exact('assortment_v255_runs',['run_id'],{'run_id':runid,'payload':runner.b24.p.canonical(frozen)})
  for stage,rows in stages.items():
   for r in rows:added+=exact('assortment_v255_results',['run_id','stage','record_id'],{'run_id':runid,'stage':stage,'record_id':r['record_id'],'payload':runner.b24.p.canonical(r)})
  c.commit();check=c.execute('PRAGMA integrity_check').fetchone()[0];fk=c.execute('PRAGMA foreign_key_check').fetchall()
 return {'run_id':runid,'inserted':added,'integrity':check,'foreign_keys':len(fk),'prior_false_exclusion_regressions':7,'all_seven_now_observe':True,'backup_read_check':'PASS'}

def main():
 runner.engine=engine;runner.OUT=OUT;runner.SEED=2026102355;runner.fingerprints=fingerprints;runner.persist=persist;runner.main()
if __name__=='__main__':main()
