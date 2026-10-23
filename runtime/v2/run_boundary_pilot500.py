"""A new random pilot with the unchanged frozen V0.3 evidence contract."""
import collections,json,random,sys
from pathlib import Path
from assortment import ROOT,Matcher,lines,read
import boundary_learning as b
import run_boundary_learning as source
import run_boundary_validation_v03 as v03
import boundary_validation_v03 as method
OUT=ROOT/'v2/runs/boundary_v03_pilot500_20261023'
def save(n,x,j=False):b.b24.p.immutable(OUT/n,x,jsonl=j)
def check():
 v03.check();f=read(OUT/'freeze.json')
 assert all(b.b24.p.filehash(p)==h for p,h in f['hashes'].items())
 return f
def prepare():
 frozen=v03.check();OUT.mkdir(exist_ok=True)
 hashes=dict(frozen['hashes']);hashes[str(Path(__file__).resolve())]=b.b24.p.filehash(__file__)
 save('freeze.json',{'method':method.VERSION,'hashes':hashes,'seed':20261023500,'owner_three_cases_not_general_rules':True})
 forbidden=source.prior_titles()
 for p in b.OUT.glob('inputs_*.jsonl'):
  forbidden.update(b.b24.title_hash(r['title_original']) for r in lines(p))
 for p in b.OUT.glob('semantic_*.jsonl'):
  forbidden.update(b.b24.title_hash(r['title_original']) for r in lines(p))
 forbidden.update(b.b24.title_hash(r['title_original']) for r in lines(method.OUT/'inputs_validation300.jsonl'))
 allrows=lines(b.OUT/'source_records.jsonl')
 known_asins={r['asin_hint_unconfirmed'] for r in allrows if b.b24.title_hash(r['title_original']) in forbidden and r.get('asin_hint_unconfirmed')}
 pool=[r for r in allrows if b.b24.title_hash(r['title_original']) not in forbidden and (not r.get('asin_hint_unconfirmed') or r['asin_hint_unconfirmed'] not in known_asins)]
 random.Random(20261023500).shuffle(pool)
 unique=[];used_titles=set();used_asins=set()
 for r in pool:
  title=b.b24.title_hash(r['title_original']);asin=r.get('asin_hint_unconfirmed')
  if title in used_titles or asin and asin in used_asins:continue
  used_titles.add(title)
  if asin:used_asins.add(asin)
  unique.append(r)
 assert len(unique)>=500
 selected=[dict(r,review_id=f'P{i+1:03d}',sample_cohort='random') for i,r in enumerate(unique[:500])]
 save('inputs500.jsonl',selected,True)
 save('sampling.json',{'source_records':len(allrows),'eligible_records_before_selection':len(pool),'eligible_conservative_unique_samples':len(unique),'new_samples':500,'remaining_after_selection':len(unique)-500,'title_overlap':0,'asin_hint_overlap':0,'source_identity':'URL records and ASIN hints, not verified buyable SKU count','previous_full_mechanical_v0_pass':True,'selection':'random_without_replacement','human_labels_for_new500':0})
 matcher=Matcher();candidates=matcher.retrieve([r['title_original'] for r in selected]);jobs=[]
 for r,cs in zip(selected,candidates):
  jobs.append(dict(r,reference_candidates=[{'sku':matcher.model['references'][i]['sku'],'title':matcher.model['references'][i]['name_es_original']} for i,score in cs[:8]]))
 for name,part in [('a',jobs[:200]),('b',jobs[200:350]),('c',jobs[350:])]:save('jobs_'+name+'.jsonl',part,True)
 print(json.dumps(read(OUT/'sampling.json'),ensure_ascii=False))
def finish():
 check();inputs={r['review_id']:r for r in lines(OUT/'inputs500.jsonl')};refs={r['sku']:r for r in Matcher().model['references']};audits=[]
 for group in 'abc':
  assert (OUT/('complete_'+group+'.json')).exists()
  for n in lines(OUT/('notes_'+group+'.jsonl')):
   row=inputs[n['review_id']];a=v03.make_audit(row,n,refs);method.validate(row,a,refs);audits.append(a)
 assert len(audits)==len({a['record_id'] for a in audits})==500
 save('audits500.jsonl',audits,True)
 engine=source.legacy.Engine();rows=list(inputs.values());base=engine.analyze_many(rows);byid={a['record_id']:a for a in audits}
 results=[dict(method.analyze(r,p,refs,byid[r['record_id']]),review_id=r['review_id']) for r,p in zip(rows,base)]
 save('results500.jsonl',results,True)
 save('summary.json',{'n':500,'states':dict(collections.Counter(r['decision'] for r in results)),'pending_reasons':dict(collections.Counter(r['review_reason_code'] for r in results if r['decision']=='待复核')),'human_gold':0,'accuracy':None,'frozen_unchanged':True,'master_changed':False,'full_rescreen':False})
 print(json.dumps(read(OUT/'summary.json'),ensure_ascii=False))
if __name__=='__main__':{'prepare':prepare,'finish':finish}[sys.argv[1]]()
