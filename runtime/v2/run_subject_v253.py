"""Freeze V2.5.3 after a failed V2.5.2 validation, then draw another 100."""
from __future__ import annotations
import collections,datetime,hashlib,json,random,re,sqlite3
from pathlib import Path
import subject_v253 as engine
import boundary_v24 as b24
import boundary_v25 as b25
import run_subject_v252 as common
from assortment import ROOT,RUN,lines,read

OUT=ROOT/'v2/runs/subject_v253_20261023'
PREVIOUS=ROOT/'v2/runs/subject_v252_20261023'
SEED=2026102353
def save(name,data,jsonl=False):b24.p.immutable(OUT/name,data,jsonl=jsonl)
def fingerprints():
 paths=[Path(__file__),Path(engine.__file__),ROOT/'v2/subject_v252.py',ROOT/'v2/run_subject_v252.py',ROOT/'v2/assortment.py',ROOT/'v2/boundary_v24.py',ROOT/'v2/boundary_v25.py',RUN/'retrieval_index.joblib',b24.INPUTS,b24.SOURCE]
 return {str(p):b24.p.filehash(p) for p in paths}

def persist(frozen,stages):
 db=ROOT/'learning_data/action_selection.sqlite3';backup=OUT/'learning_before_v253.sqlite3'
 if not backup.exists():
  with sqlite3.connect(db) as src,sqlite3.connect(backup) as dst:src.backup(dst)
 with sqlite3.connect(backup) as c:
  assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()
 runid='v253-'+hashlib.sha256(b24.p.canonical(frozen).encode()).hexdigest()[:16]
 with sqlite3.connect(db) as c:
  c.execute('PRAGMA foreign_keys=ON')
  c.executescript('CREATE TABLE IF NOT EXISTS assortment_v253_runs(run_id TEXT PRIMARY KEY,payload TEXT NOT NULL); CREATE TABLE IF NOT EXISTS assortment_v253_results(run_id TEXT NOT NULL,stage TEXT NOT NULL,record_id TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(run_id,stage,record_id),FOREIGN KEY(run_id) REFERENCES assortment_v253_runs(run_id));')
  def exact(table,keys,data):
   cols=list(data);old=c.execute('SELECT '+','.join(cols)+' FROM '+table+' WHERE '+' AND '.join(k+'=?' for k in keys),[data[k] for k in keys]).fetchone()
   if old is not None:
    assert tuple(old)==tuple(data.values()),'IMMUTABLE_ROW_CONFLICT'
    return 0
   c.execute('INSERT INTO '+table+'('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',list(data.values()));return 1
  added=exact('assortment_v253_runs',['run_id'],{'run_id':runid,'payload':b24.p.canonical(frozen)})
  for stage,rows in stages.items():
   for r in rows:added+=exact('assortment_v253_results',['run_id','stage','record_id'],{'run_id':runid,'stage':stage,'record_id':r['record_id'],'payload':b24.p.canonical(r)})
  c.commit();check=c.execute('PRAGMA integrity_check').fetchone()[0];fk=c.execute('PRAGMA foreign_key_check').fetchall()
 return {'run_id':runid,'inserted':added,'integrity':check,'foreign_keys':len(fk),'backup_restore_read_check':'PASS'}

def main():
 OUT.mkdir(parents=True,exist_ok=True);common.OUT=OUT
 source=read(b24.SOURCE)
 assert b24.p.filehash(source['source_file'])==source['source_sha256'],'AMAZON_SOURCE_CHANGED'
 e=engine.Engine();devsource=lines(common.OLD/'paired_new150.jsonl');dev=e.analyze_many([p['v25'] for p in devsource])
 regression_inputs=lines(PREVIOUS/'inputs_100.jsonl');reg=e.analyze_many(regression_inputs)
 focus=[]
 for p,r in zip(devsource,dev):
  if (p['v25']['decision']=='观察' and p['ai_review']['decision']=='保留') or (p['v25']['decision']=='用不到' and p['ai_review']['decision']=='观察'):
   focus.append({'review_id':p['review_id'],'old_program':p['v25'],'ai_development_opinion':p['ai_review'],'new_program':r})
 save('focus_50.jsonl',focus,True);save('development_150.jsonl',dev,True);save('exposed_regression_100.jsonl',reg,True)
 common.csvsave('focus_50.csv',[{'编号':p['review_id'],'商品原文':p['new_program']['title_original'],'旧结论':p['old_program']['decision'],'AI候选':p['ai_development_opinion']['decision'],'新程序':p['new_program']['decision'],'主体':p['new_program']['subject']['class_code'],'原因':p['new_program']['reason_code'],'参照SKU':' / '.join(a['action_sku'] for a in p['new_program']['action_references']),'参照原文':' / '.join(a['action_title'] for a in p['new_program']['action_references']),'人工确认':False} for p in focus])
 # Exact four false exclusions, plus their generic tests, are regression data.
 previous=lines(PREVIOUS/'results_100.jsonl')
 audit=[{'review_id':f'F{i:03d}','title_original':previous[i-1]['title_original'],'v252':previous[i-1]['decision'],'v253':reg[i-1]['decision'],'new_subject':reg[i-1]['subject'],'ai_audit_type':'HOST_OR_PROPERTY_MISTAKEN_FOR_SOLD_APPLIANCE','human_confirmed':False} for i in [1,5,8,14]]
 assert all(r['v253']=='观察' for r in audit)
 save('false_exclusion_regression_4.jsonl',audit,True)
 fp=fingerprints()
 if (OUT/'frozen_contract.json').exists():
  frozen=read(OUT/'frozen_contract.json');assert frozen['fingerprints']==fp,'FROZEN_CODE_CHANGED'
 else:
  frozen={'version':engine.VERSION,'frozen_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'fingerprints':fp,'seed':SEED,'human_gold':0,'sample_count':100,'rule_changes_after_sample_forbidden':True,'formal_screening_replaced':False}
  save('frozen_contract.json',frozen)
 if (OUT/'inputs_100.jsonl').exists():selected=lines(OUT/'inputs_100.jsonl')
 else:
  forbidden=b24.prior_title_hashes()|b25.focus_titles()
  for path in (ROOT/'v2/runs').rglob('inputs_*.jsonl'):
   if OUT in path.parents:continue
   forbidden.update(b24.title_hash(r['title_original']) for r in lines(path) if r.get('title_original'))
  available=[r for r in lines(b24.INPUTS) if b24.title_hash(r['title_original']) not in forbidden]
  rng=random.Random(SEED);selected=[];used=set();short={};pools={}
  for label,quota,expr in [('boundary_and_host',20,r'\b(?:aire acondicionado|lavadora|secadora|frigorifico|armero|armas)\b'),('confusable_subject',30,r'\b(?:apto|apta|aptos|aptas|compatible|funda|soporte|repuesto|recambio)\b')]:
   pool=[r for r in available if re.search(expr,b24.norm(r['title_original']))];rng.shuffle(pool);pools[label]=len(pool);got=0
   for r in pool:
    h=b24.title_hash(r['title_original'])
    if h in used:continue
    selected.append(dict(r,sample_cohort=label));used.add(h);got+=1
    if got==quota:break
   short[label]=quota-got
  rng.shuffle(available)
  for r in available:
   if len(selected)==100:break
   h=b24.title_hash(r['title_original'])
   if h in used:continue
   selected.append(dict(r,sample_cohort='seeded_random_remainder'));used.add(h)
  assert len(selected)==100 and not used&forbidden
  save('inputs_100.jsonl',selected,True);save('sampling.json',{'seed':SEED,'counts':dict(collections.Counter(r['sample_cohort'] for r in selected)),'candidate_pools':pools,'shortfalls':short,'prior_title_overlap':0,'forbidden_titles':len(forbidden),'selection_uses_predictions':False,'population_accuracy_estimate':False})
 results=e.analyze_many(selected);old=[b25.analyze(r,e.matcher,{}) for r in selected]
 save('results_100.jsonl',results,True);save('paired_new100.jsonl',[{'v25':o,'v253':r} for o,r in zip(old,results)],True)
 common.csvsave('new100_review.csv',[{'编号':f'G{i:03d}','商品原文':r['title_original'],'程序结论':r['decision'],'主体':r['subject']['class_code'],'证据':r['subject']['evidence_span'],'原因':r['reason_code'],'参照SKU':' / '.join(a['action_sku'] for a in r['action_references']),'参照原文':' / '.join(a['action_title'] for a in r['action_references']),'人工结论':'','人工原因':'','审核人':''} for i,r in enumerate(results,1)])
 refs={r['sku']:r for r in e.refs}
 for r in dev+reg+results:
  for a in r['action_references']:
   assert a['action_title']==refs[a['action_sku']]['name_es_original'] and a['action_source_row_id']==refs[a['action_sku']]['source_row_id']
 summary={'version':engine.VERSION,'focus_keep48':dict(collections.Counter(x['new_program']['decision'] for x in focus if x['ai_development_opinion']['decision']=='保留')),'focus_exclusion2':[(x['review_id'],x['new_program']['decision']) for x in focus if x['ai_development_opinion']['decision']=='观察'],'regression_4_fixed':True,'new100':common.counts(results),'old_v25_new100':common.counts(old),'new100_cohorts':{s:common.counts([r for r in results if r['sample_cohort']==s]) for s in sorted({r['sample_cohort'] for r in results})},'human_gold':0,'accuracy':None,'source_and_index_unchanged':fp==fingerprints(),'formal_screening_replaced':False}
 save('summary.json',summary)
 persistence=persist(frozen,{'development150':dev,'regression100':reg,'unseen100':results})
 print(json.dumps(summary|persistence,ensure_ascii=False))

if __name__=='__main__':main()
