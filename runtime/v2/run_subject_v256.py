"""Bounded final freeze and fresh-50 validation using the shared database."""
import collections,csv,datetime,hashlib,io,json,random,re,sqlite3
from pathlib import Path
import subject_v256 as engine
import boundary_v24 as b24
import boundary_v25 as b25
from assortment import ROOT,RUN,lines,read
OUT=ROOT/'v2/runs/subject_v256_20261023'
OLD=ROOT/'v2/runs/amazon_v251_ai_calibration_20261022'
SEED=2026102356
def save(name,value,jsonl=False):b24.p.immutable(OUT/name,value,jsonl=jsonl)
def csvsave(name,rows):
 s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 p=OUT/name;data=('\ufeff'+s.getvalue()).encode('utf8')
 if p.exists():assert p.read_bytes()==data,'IMMUTABLE_CSV_CONFLICT'
 else:p.write_bytes(data)
def fingerprints():
 paths=[Path(__file__),ROOT/'v2/assortment.py',ROOT/'v2/boundary_v24.py',ROOT/'v2/boundary_v25.py',ROOT/'scripts/pipeline.py',RUN/'retrieval_index.joblib',b24.INPUTS,b24.SOURCE]
 for v in ['252','253','254','255','256']:
  paths.extend([ROOT/f'v2/subject_v{v}.py',ROOT/f'tests/test_subject_v{v}.py'])
 return {str(p):b24.p.filehash(p) for p in paths}
def persist(frozen,stages):
 db=ROOT/'learning_data/action_selection.sqlite3';backup=OUT/'learning_before_v256.sqlite3'
 if not backup.exists():
  with sqlite3.connect(db) as src,sqlite3.connect(backup) as dst:src.backup(dst)
 with sqlite3.connect(backup) as c:
  assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()
 runid='v256-'+hashlib.sha256(b24.p.canonical(frozen).encode()).hexdigest()[:16]
 with sqlite3.connect(db) as c:
  c.execute('PRAGMA foreign_keys=ON');c.executescript('CREATE TABLE IF NOT EXISTS assortment_v256_runs(run_id TEXT PRIMARY KEY,payload TEXT NOT NULL); CREATE TABLE IF NOT EXISTS assortment_v256_results(run_id TEXT NOT NULL,stage TEXT NOT NULL,record_id TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(run_id,stage,record_id),FOREIGN KEY(run_id) REFERENCES assortment_v256_runs(run_id));')
  def exact(table,keys,data):
   cols=list(data);old=c.execute('SELECT '+','.join(cols)+' FROM '+table+' WHERE '+' AND '.join(k+'=?' for k in keys),[data[k] for k in keys]).fetchone()
   if old is not None:
    assert tuple(old)==tuple(data.values()),'IMMUTABLE_ROW_CONFLICT'
    return 0
   c.execute('INSERT INTO '+table+'('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',list(data.values()));return 1
  added=exact('assortment_v256_runs',['run_id'],{'run_id':runid,'payload':b24.p.canonical(frozen)})
  for stage,rows in stages.items():
   for r in rows:added+=exact('assortment_v256_results',['run_id','stage','record_id'],{'run_id':runid,'stage':stage,'record_id':r['record_id'],'payload':b24.p.canonical(r)})
  c.commit();check=c.execute('PRAGMA integrity_check').fetchone()[0];fk=c.execute('PRAGMA foreign_key_check').fetchall()
 return {'run_id':runid,'inserted':added,'integrity':check,'foreign_keys':len(fk),'backup_read_check':'PASS'}

def main():
 OUT.mkdir(parents=True,exist_ok=True);e=engine.Engine();stages={}
 source=read(b24.SOURCE);assert b24.p.filehash(source['source_file'])==source['source_sha256']
 devsource=lines(OLD/'paired_new150.jsonl');dev=e.analyze_many([r['v25'] for r in devsource]);stages['development150']=dev
 focus=[]
 for p,r in zip(devsource,dev):
  if (p['v25']['decision']=='观察' and p['ai_review']['decision']=='保留') or (p['v25']['decision']=='用不到' and p['ai_review']['decision']=='观察'):
   focus.append({'review_id':p['review_id'],'old_program':p['v25'],'ai_development_opinion':p['ai_review'],'new_program':r})
 save('focus_50.jsonl',focus,True)
 csvsave('focus_50.csv',[{'编号':p['review_id'],'商品原文':p['new_program']['title_original'],'旧程序':p['old_program']['decision'],'AI开发意见':p['ai_development_opinion']['decision'],'最终程序':p['new_program']['decision'],'主体':p['new_program']['subject']['class_code'],'原因':p['new_program']['reason_code'],'参照SKU':' / '.join(a['action_sku'] for a in p['new_program']['action_references']),'参照原文':' / '.join(a['action_title'] for a in p['new_program']['action_references']),'人工确认':False} for p in focus])
 regressions=[]
 cases={'252':[1,5,8,14],'253':[18,20],'254':[5],'255':[47,56,78]}
 for v in ['252','253','254','255']:
  rows=e.analyze_many(lines(ROOT/f'v2/runs/subject_v{v}_20261023/inputs_100.jsonl'));stages[f'exposed_v{v}_100']=rows
  save(f'exposed_v{v}_regression_100.jsonl',rows,True)
  for i in cases[v]:
   r=rows[i-1];assert r['decision']=='观察',(v,i,r)
   regressions.append({'prior_version':v,'ordinal':i,'title_original':r['title_original'],'decision':r['decision'],'subject':r['subject'],'human_confirmed':False})
 save('known_error_regressions_10.jsonl',regressions,True)
 fp=fingerprints()
 if (OUT/'frozen_contract.json').exists():
  frozen=read(OUT/'frozen_contract.json');assert frozen['fingerprints']==fp,'FROZEN_RULES_CHANGED'
 else:
  frozen={'version':engine.VERSION,'frozen_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'fingerprints':fp,'seed':SEED,'target_new50':True,'human_gold':0,'formal_results_replaced':False}
  save('frozen_contract.json',frozen)
 if (OUT/'inputs_50.jsonl').exists():selected=lines(OUT/'inputs_50.jsonl')
 else:
  forbidden=b24.prior_title_hashes()|b25.focus_titles()
  for path in (ROOT/'v2/runs').rglob('inputs_*.jsonl'):
   if OUT in path.parents:continue
   forbidden.update(b24.title_hash(r['title_original']) for r in lines(path) if r.get('title_original'))
  available=[r for r in lines(b24.INPUTS) if b24.title_hash(r['title_original']) not in forbidden]
  rng=random.Random(SEED);selected=[];used=set()
  for label,quota,expr in [('boundary_host',10,r'\b(?:aire acondicionado|lavadora|secadora|frigorifico|armero|armas)\b'),('confusable',15,r'\b(?:apto|apta|aptos|aptas|compatible|funda|soporte|incluye)\b')]:
   pool=[r for r in available if re.search(expr,b24.norm(r['title_original']))];rng.shuffle(pool);count=0
   for r in pool:
    h=b24.title_hash(r['title_original'])
    if h in used:continue
    selected.append(dict(r,sample_cohort=label));used.add(h);count+=1
    if count==quota:break
   assert count==quota,'TARGET_STRATUM_SHORTFALL'
  rng.shuffle(available)
  for r in available:
   if len(selected)==50:break
   h=b24.title_hash(r['title_original'])
   if h in used:continue
   selected.append(dict(r,sample_cohort='seeded_random'));used.add(h)
  assert len(selected)==50 and not used&forbidden
  save('inputs_50.jsonl',selected,True);save('sampling.json',{'counts':dict(collections.Counter(r['sample_cohort'] for r in selected)),'seed':SEED,'prior_title_overlap':0,'forbidden_title_count':len(forbidden),'selection_uses_predictions':False,'population_accuracy_estimate':False})
 results=e.analyze_many(selected);stages['unseen50']=results
 save('results_50.jsonl',results,True)
 old=[b25.analyze(r,e.matcher,{}) for r in selected]
 save('paired_new50.jsonl',[{'v25':o,'v256':r} for o,r in zip(old,results)],True)
 csvsave('new50_review.csv',[{'编号':f'K{i:03d}','商品原文':r['title_original'],'程序结论':r['decision'],'主体':r['subject']['class_code'],'主体证据':r['subject']['evidence_span'],'原因':r['reason_code'],'参照SKU':' / '.join(a['action_sku'] for a in r['action_references']),'参照原文':' / '.join(a['action_title'] for a in r['action_references']),'人工裁定':'','人工原因':'','审核人':''} for i,r in enumerate(results,1)])
 refs={r['sku']:r for r in e.refs}
 for rows in stages.values():
  for r in rows:
   for a in r['action_references']:assert a['action_title']==refs[a['action_sku']]['name_es_original'] and a['action_source_row_id']==refs[a['action_sku']]['source_row_id']
 summary={'version':engine.VERSION,'focus_keep48':dict(collections.Counter(x['new_program']['decision'] for x in focus if x['ai_development_opinion']['decision']=='保留')),'focus_exclusion2':[(x['review_id'],x['new_program']['decision']) for x in focus if x['ai_development_opinion']['decision']=='观察'],'known_error_regressions':len(regressions),'new50':dict(collections.Counter(r['decision'] for r in results)),'old_v25_new50':dict(collections.Counter(r['decision'] for r in old)),'cohorts':{s:dict(collections.Counter(r['decision'] for r in results if r['sample_cohort']==s)) for s in sorted({r['sample_cohort'] for r in results})},'human_gold':0,'accuracy':None,'source_and_index_unchanged':fp==fingerprints(),'formal_screening_replaced':False}
 save('summary.json',summary);print(json.dumps(summary|persist(frozen,stages),ensure_ascii=False))
if __name__=='__main__':main()
