"""Development audit, immutable freeze, unseen title-only shadow validation."""
from __future__ import annotations
import collections,csv,datetime,hashlib,io,json,random,re,sqlite3
from pathlib import Path
import boundary_v24 as b24
import boundary_v25 as b25
import subject_v252 as engine
from assortment import ROOT,RUN,lines,read

OUT=ROOT/'v2/runs/subject_v252_20261023'
OLD=ROOT/'v2/runs/amazon_v251_ai_calibration_20261022'
DB=ROOT/'learning_data/action_selection.sqlite3'
SEED=2026102352

def counts(rows):return dict(collections.Counter(r['decision'] for r in rows))
def save(name,data,jsonl=False):b24.p.immutable(OUT/name,data,jsonl=jsonl)
def csvsave(name,rows):
 s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 path=OUT/name;data=('\ufeff'+s.getvalue()).encode('utf8')
 if path.exists() and path.read_bytes()!=data:raise ValueError('IMMUTABLE_CSV_CONFLICT')
 if not path.exists():path.write_bytes(data)

def fingerprints():
 paths=[Path(engine.__file__),Path(__file__),ROOT/'v2/assortment.py',ROOT/'v2/boundary_v24.py',ROOT/'v2/boundary_v25.py',RUN/'retrieval_index.joblib',b24.INPUTS,b24.SOURCE]
 return {str(p):b24.p.filehash(p) for p in paths}

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 source=read(b24.SOURCE)
 if b24.p.filehash(source['source_file'])!=source['source_sha256']:raise RuntimeError('AMAZON_SOURCE_CHANGED')
 e=engine.Engine();prior=lines(OLD/'paired_new150.jsonl')
 dev=e.analyze_many([x['v25'] for x in prior]);pair=[];focus=[]
 for p,r in zip(prior,dev):
  ai=p['ai_review'];item={'review_id':p['review_id'],'old_program':p['v25'],'ai_development_opinion':ai,'new_program':r}
  pair.append(item)
  if (p['v25']['decision']=='观察' and ai['decision']=='保留') or (p['v25']['decision']=='用不到' and ai['decision']=='观察'):focus.append(item)
 save('development_150.jsonl',pair,True);save('focus_50.jsonl',focus,True)
 csvsave('focus_50.csv',[{'编号':x['review_id'],'商品原文':x['new_program']['title_original'],'旧程序':x['old_program']['decision'],'AI开发意见':x['ai_development_opinion']['decision'],'新程序':x['new_program']['decision'],'主体':x['new_program']['subject']['class_code'],'原因码':x['new_program']['reason_code'],'参照SKU':' / '.join(a['action_sku'] for a in x['new_program']['action_references']),'参照原文':' / '.join(a['action_title'] for a in x['new_program']['action_references']),'人工确认':False} for x in focus])
 # This is written BEFORE selection; existing freeze must match exact code.
 fp=fingerprints()
 if (OUT/'frozen_contract.json').exists():
  frozen=read(OUT/'frozen_contract.json')
  if frozen['fingerprints']!=fp:raise RuntimeError('FROZEN_CODE_CHANGED_CREATE_NEW_VERSION')
 else:
  frozen={'version':engine.VERSION,'frozen_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'fingerprints':fp,'seed':SEED,'human_gold':0,'training':False,'target_new_sample':100,'formal_results_replaced':False}
  save('frozen_contract.json',frozen)
 if (OUT/'inputs_100.jsonl').exists():selected=lines(OUT/'inputs_100.jsonl')
 else:
  forbidden=b24.prior_title_hashes()|b25.focus_titles()
  for path in (ROOT/'v2/runs').rglob('inputs_*.jsonl'):
   if OUT in path.parents:continue
   for r in lines(path):
    if r.get('title_original'):forbidden.add(b24.title_hash(r['title_original']))
  available=[r for r in lines(b24.INPUTS) if b24.title_hash(r['title_original']) not in forbidden]
  rng=random.Random(SEED);selected=[];used=set();pools={};shortfalls={}
  for label,quota,expr in [
    ('boundary_targeted',20,r'\b(?:aire acondicionado|armero|armario para armas|lavadora|secadora|frigorifico)\b'),
    ('subject_host_confusable',30,r'\b(?:apto|apta|aptos|aptas|compatible|recambio|repuesto|funda|soporte|deflector)\b')]:
   pool=[r for r in available if re.search(expr,b24.norm(r['title_original']))];rng.shuffle(pool);pools[label]=len(pool);got=0
   for r in pool:
    h=b24.title_hash(r['title_original'])
    if h in used:continue
    selected.append(dict(r,sample_cohort=label));used.add(h);got+=1
    if got==quota:break
   shortfalls[label]=quota-got
  rest=list(available);rng.shuffle(rest)
  for r in rest:
   if len(selected)>=100:break
   h=b24.title_hash(r['title_original'])
   if h in used:continue
   selected.append(dict(r,sample_cohort='seeded_random_remainder'));used.add(h)
  assert len(selected)==100 and not used&forbidden
  save('inputs_100.jsonl',selected,True)
  save('sampling.json',{'seed':SEED,'counts':dict(collections.Counter(r['sample_cohort'] for r in selected)),'pools':pools,'shortfalls':shortfalls,'prior_title_overlap':0,'forbidden_titles':len(forbidden),'selection_uses_predictions':False,'representative_population_accuracy':False})
 results=e.analyze_many(selected)
 old=[b25.analyze(r,e.matcher,{}) for r in selected]
 save('results_100.jsonl',results,True)
 save('paired_new100.jsonl',[{'old_program':o,'new_program':r} for o,r in zip(old,results)],True)
 # Expose titles separately for a source-only AI audit; AI is not human Gold.
 csvsave('new100_review.csv',[{'编号':f'F{i:03d}','商品原文':r['title_original'],'程序结论':r['decision'],'主体':r['subject']['class_code'],'主体证据':r['subject']['evidence_span'],'原因':r['reason_code'],'参照SKU':' / '.join(a['action_sku'] for a in r['action_references']),'参照原文':' / '.join(a['action_title'] for a in r['action_references']),'人工结论':'','人工原因':'','审核人':''} for i,r in enumerate(results,1)])
 summary={'version':engine.VERSION,'development_150':counts(dev),'focus_keep48':dict(collections.Counter(x['new_program']['decision'] for x in focus if x['ai_development_opinion']['decision']=='保留')),'focus_exclusion2':[{k:x[k] for k in ['review_id']}|{'decision':x['new_program']['decision'],'reason':x['new_program']['reason_code']} for x in focus if x['ai_development_opinion']['decision']=='观察'],'new100':counts(results),'old_new100':counts(old),'new100_cohorts':{c:counts([r for r in results if r['sample_cohort']==c]) for c in sorted({r['sample_cohort'] for r in results})},'human_gold':0,'accuracy':None,'source_and_index_unchanged':fp==fingerprints(),'formal_screening_replaced':False}
 save('summary.json',summary)
 # Validate all pointers against the immutable reference index.
 refmap={r['sku']:r for r in e.refs}
 for r in results+dev:
  for a in r['action_references']:
   real=refmap[a['action_sku']]
   assert a['action_title']==real['name_es_original'] and a['action_source_row_id']==real['source_row_id']
 backup=OUT/'learning_before_v252.sqlite3'
 if not backup.exists():
  with sqlite3.connect(DB) as src,sqlite3.connect(backup) as dst:src.backup(dst)
 with sqlite3.connect(backup) as bc:
  assert bc.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not bc.execute('PRAGMA foreign_key_check').fetchall()
 runid='v252-'+hashlib.sha256(b24.p.canonical(frozen).encode()).hexdigest()[:16]
 with sqlite3.connect(DB) as c:
  c.execute('PRAGMA foreign_keys=ON')
  c.executescript('CREATE TABLE IF NOT EXISTS assortment_v252_runs(run_id TEXT PRIMARY KEY,payload TEXT NOT NULL); CREATE TABLE IF NOT EXISTS assortment_v252_results(run_id TEXT NOT NULL,stage TEXT NOT NULL,record_id TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(run_id,stage,record_id),FOREIGN KEY(run_id) REFERENCES assortment_v252_runs(run_id));')
  def exact(table,keys,data):
   cols=list(data);row=c.execute('SELECT '+','.join(cols)+' FROM '+table+' WHERE '+' AND '.join(k+'=?' for k in keys),[data[k] for k in keys]).fetchone()
   if row is not None:
    if tuple(row)!=tuple(data.values()):raise RuntimeError('IMMUTABLE_DB_CONFLICT')
    return 0
   c.execute('INSERT INTO '+table+'('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',list(data.values()));return 1
  inserted=exact('assortment_v252_runs',['run_id'],{'run_id':runid,'payload':b24.p.canonical(frozen)})
  for stage,rows in [('development',dev),('unseen',results)]:
   for r in rows:inserted+=exact('assortment_v252_results',['run_id','stage','record_id'],{'run_id':runid,'stage':stage,'record_id':r['record_id'],'payload':b24.p.canonical(r)})
  c.commit();integrity=c.execute('PRAGMA integrity_check').fetchone()[0];fk=c.execute('PRAGMA foreign_key_check').fetchall()
 print(json.dumps(summary|{'run_id':runid,'db_inserted':inserted,'integrity':integrity,'foreign_keys':len(fk)},ensure_ascii=False))

if __name__=='__main__':main()
