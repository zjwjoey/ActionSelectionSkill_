"""Development -> freeze -> unseen100; retain all earlier experiment results."""
import collections,datetime,hashlib,json,random,re
from pathlib import Path
import boundary_v24 as b24
import boundary_v25 as b25
import subject_v256 as oldengine
import subject_v2513 as engine
import subject_experiment_store as store
from assortment import ROOT,RUN,lines,read
OUT=ROOT/'v2/runs/subject_v2513_20261023'
OLD=ROOT/'v2/runs/subject_v256_20261023'
SEED=2026102363
def save(name,value,jsonl=False):b24.p.immutable(OUT/name,value,jsonl=jsonl)
def csvsave(name,rows):
 import csv,io
 s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 data=('\ufeff'+s.getvalue()).encode('utf8');p=OUT/name
 if p.exists() and p.read_bytes()!=data:raise RuntimeError('IMMUTABLE_CSV_CONFLICT')
 if not p.exists():p.write_bytes(data)
def fingerprints():
 paths=[Path(__file__),Path(store.__file__),ROOT/'v2/assortment.py',ROOT/'v2/boundary_v24.py',ROOT/'v2/boundary_v25.py',ROOT/'scripts/pipeline.py',RUN/'retrieval_index.joblib',b24.INPUTS,b24.SOURCE,ROOT/'tests/test_subject_v257.py']
 paths += [ROOT/f'v2/subject_v{v}.py' for v in ['252','253','254','255','256','257','258','259','2510','2511','2512','2513']]
 paths += [ROOT/'v2/subject_reference_core.py',ROOT/'tests/test_subject_v258.py',ROOT/'tests/test_subject_v259.py',ROOT/'tests/test_subject_v2510.py',ROOT/'tests/test_subject_v2511.py',ROOT/'tests/test_subject_v2512.py',ROOT/'tests/test_subject_v2513.py']
 paths += engine.CACHE_PATHS
 return {str(p):b24.p.filehash(p) for p in paths}
def counts(rows):return dict(collections.Counter(r['decision'] for r in rows))
def main():
 OUT.mkdir(parents=True,exist_ok=True);source=read(b24.SOURCE)
 if b24.p.filehash(source['source_file'])!=source['source_sha256']:raise RuntimeError('SOURCE_CHANGED')
 e=engine.Engine();development=e.analyze_many(lines(OLD/'inputs_50.jsonl'))
 if development[4]['subject']['class_code']!='LAUNDRY_BAG' or development[5]['subject']['class_code']!='LAUNDRY_BAG' or development[17]['subject']['class_code']!='FRENCH_PRESS':raise RuntimeError('KNOWN_SUBJECT_REGRESSION')
 if any(a['reference_subject']['class_code']!='AIR_COOLER' for a in development[9]['action_references']):raise RuntimeError('COOLER_REFERENCED_FAN')
 before=lines(OLD/'results_50.jsonl');ai=lines(OLD/'ai_audit_50_bound.jsonl')
 save('development_50.jsonl',[{'review_id':f'K{i:03d}','before':a,'after':b,'prior_ai_opinion':c} for i,(a,b,c) in enumerate(zip(before,development,ai),1)],True)
 focus_old=lines(OLD/'focus_50.jsonl');focus=e.analyze_many([r['new_program'] for r in focus_old]);save('focus_50.jsonl',[{'review_id':p['review_id'],'before':p['new_program'],'after':r} for p,r in zip(focus_old,focus)],True)
 # Freeze exact dependencies before drawing any new validation title.
 fp=fingerprints()
 if (OUT/'frozen_contract.json').exists():
  frozen=read(OUT/'frozen_contract.json')
  if fp!=frozen['fingerprints']:raise RuntimeError('FROZEN_DEPENDENCY_CHANGED')
 else:
  frozen={'version':engine.VERSION,'frozen_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'seed':SEED,'fingerprints':fp,'target_size':20,'human_gold':0,'formal_results_replaced':False}
  save('frozen_contract.json',frozen)
 if (OUT/'inputs_20.jsonl').exists():selected=lines(OUT/'inputs_20.jsonl')
 else:
  forbidden=b24.prior_title_hashes()|b25.focus_titles()
  for path in (ROOT/'v2/runs').rglob('inputs_*.jsonl'):
   if OUT in path.parents:continue
   forbidden.update(b24.title_hash(r['title_original']) for r in lines(path) if r.get('title_original'))
  available=[r for r in lines(b24.INPUTS) if b24.title_hash(r['title_original']) not in forbidden]
  rng=random.Random(SEED);selected=[];used=set();pools={}
  for label,quota,expr in [('boundary_host',5,r'\b(?:aire acondicionado|frigorifico|lavadora|secadora|armero|armas)\b'),('confusable_subject',5,r'\b(?:incluye|compatible|con|funda|apto|apta|soporte)\b')]:
   pool=[r for r in available if re.search(expr,b24.norm(r['title_original']))];rng.shuffle(pool);pools[label]=len(pool);got=0
   for r in pool:
    h=b24.title_hash(r['title_original'])
    if h in used:continue
    selected.append(dict(r,sample_cohort=label));used.add(h);got+=1
    if got==quota:break
   if got!=quota:raise RuntimeError('SAMPLE_SHORTFALL')
  rng.shuffle(available)
  for r in available:
   if len(selected)==20:break
   h=b24.title_hash(r['title_original'])
   if h in used:continue
   selected.append(dict(r,sample_cohort='seeded_random'));used.add(h)
  assert len(selected)==20 and not used&forbidden
  save('inputs_20.jsonl',selected,True);save('sampling.json',{'seed':SEED,'counts':dict(collections.Counter(r['sample_cohort'] for r in selected)),'candidate_pools':pools,'prior_title_overlap':0,'forbidden_title_count':len(forbidden),'selection_used_predictions':False,'population_accuracy':None})
 results=e.analyze_many(selected);previous=oldengine.Engine(e.matcher).analyze_many(selected)
 save('results_20.jsonl',results,True);save('paired_new20.jsonl',[{'v256':p,'v2513':r} for p,r in zip(previous,results)],True)
 csvsave('new20_review.csv',[{'编号':f'S{i:03d}','原始品名':r['title_original'],'旧程序':p['decision'],'新程序':r['decision'],'商品主体':r['subject']['class_code'],'主体证据':r['subject']['evidence_span'],'功能子类型':r['subject'].get('subtype',''),'原因':r['reason_code'],'参照SKU':' / '.join(a['action_sku'] for a in r['action_references']),'参照原文':' / '.join(a['action_title'] for a in r['action_references']),'人工结论':'','审核人':''} for i,(p,r) in enumerate(zip(previous,results),1)])
 refs={r['sku']:r for r in e.refs}
 for r in development+focus+results:
  for a in r['action_references']:
   if a['action_title']!=refs[a['action_sku']]['name_es_original'] or a['action_source_row_id']!=refs[a['action_sku']]['source_row_id']:raise RuntimeError('REFERENCE_SOURCE_MISMATCH')
 exposed=e.analyze_many(lines(ROOT/'v2/runs/subject_v257_20261023/inputs_100.jsonl'))
 save('exposed_v257_regression100.jsonl',exposed,True)
 if development[37]['decision']=='保留' and any('burbujas' in a['action_title'].lower() for a in development[37]['action_references']):raise RuntimeError('BLOWER_MATCHED_BUBBLE_TOY')
 exposed258=e.analyze_many(lines(ROOT/'v2/runs/subject_v258_20261023/inputs_100.jsonl'))
 save('exposed_v258_regression100.jsonl',exposed258,True)
 exposed259=e.analyze_many(lines(ROOT/'v2/runs/subject_v259_20261023/inputs_100.jsonl'))
 save('exposed_v259_regression100.jsonl',exposed259,True)
 if any('mano' in a['action_title'].lower() for i in [41,66] for a in exposed259[i]['action_references']):raise RuntimeError('CEILING_FAN_REFERENCED_HANDHELD')
 exposed2510=e.analyze_many(lines(ROOT/'v2/runs/subject_v2510_20261023/inputs_50.jsonl'))
 save('exposed_v2510_regression50.jsonl',exposed2510,True)
 if exposed2510[39]['subject']['class_code']!='SHOWER_SQUEEGEE' or exposed2510[41]['subject']['class_code']!='LOCKER':raise RuntimeError('WHOLE_ITEM_REGRESSION')
 exposed2511=e.analyze_many(lines(ROOT/'v2/runs/subject_v2511_20261023/inputs_20.jsonl'))
 save('exposed_v2511_regression20.jsonl',exposed2511,True)
 if exposed2511[15]['subject']['class_code']!='BAKING_PAPER' or any(a['reference_subject']['class_code']=='FRYER' for a in exposed2511[15]['action_references']):raise RuntimeError('PAPER_MATCHED_AIR_FRYER')
 exposed2512=e.analyze_many(lines(ROOT/'v2/runs/subject_v2512_20261023/inputs_20.jsonl'))
 save('exposed_v2512_regression20.jsonl',exposed2512,True)
 runid='v2513-'+hashlib.sha256(b24.p.canonical(frozen).encode()).hexdigest()[:16]
 summary={'run_id':runid,'version':engine.VERSION,'old_development50':counts(before),'new_development50':counts(development),
  'prior26_coverage_gaps_now_clear':sum(r['subject']['status']=='CLEAR' for r,a in zip(development,ai) if a['audit_status']=='RULE_COVERAGE_GAP'),
  'known_three_subjects_corrected':True,'known_cooler_reference_now_same_class':True,
  'old_new20':counts(previous),'new20':counts(results),'new20_cohorts':{s:counts([r for r in results if r['sample_cohort']==s]) for s in sorted({r['sample_cohort'] for r in results})},
  'reference_rows_valid':True,'source_and_index_unchanged':fp==fingerprints(),'human_gold':0,'accuracy':None,'formal_results_replaced':False}
 save('summary.json',summary)
 print(json.dumps(summary|store.persist(OUT,runid,frozen,{'development50':development,'focus50':focus,'unseen20':results,'exposed_v257_100':exposed,'exposed_v258_100':exposed258,'exposed_v259_100':exposed259,'exposed_v2510_50':exposed2510,'exposed_v2511_20':exposed2511,'exposed_v2512_20':exposed2512}),ensure_ascii=False))
if __name__=='__main__':main()
