"""Source-bound Codex semantic review; AI records never enter human Gold."""
from __future__ import annotations
import argparse, collections, csv, json, random, re, sqlite3
from pathlib import Path
import boundary_v24 as b24
import boundary_v25 as b25
from assortment import Matcher, ROOT, RUN, lines, norm, read

OUT=ROOT/'v2/runs/amazon_v251_ai_calibration_20261022'
BASE=b25.OUT/'amazon-boundary-v25-2109ef657ef8dc8f'
CAL=ROOT/'outputs/amazon_boundary_v25_20261022/V2.5首批人工校准候选_144fb2d755.csv'
POLICY={
 'version':'v2.5.1-delegated-ai-calibration','authority':'User delegated AI judgment in this conversation; not human Gold',
 'public_labels':['保留','观察','用不到'],
 'retain':'Clear standalone everyday product with a verified Action functional-class reference; subtype differences are recorded, not claimed equivalent.',
 'observe':['Complete furniture and dedicated components (existing Owner everyday-first scope)', 'Large sheds, power stations, specialized equipment whose industrial status is unproven', 'Missing usable reference or insufficient source information'],
 'outside':['Explicit complete major household appliance with unambiguous form/capacity evidence', 'Dedicated firearm/ammunition storage or firearm consumables', 'Explicit industrial production/process plant'],
 'guards':['Boundary phrase must describe the sold subject', 'Professional/industrial styling alone never excludes', 'Dishwasher-safe/fridge-compatible is a property, not the sold appliance', 'No reference never causes exclusion', 'Same material, interface, theme, brand or room is not same functional class'],
 'reference_levels':['SAME_FUNCTIONAL_CLASS','RELATED_NEED','NO_VERIFIED_REFERENCE'],
 'unknown_performance':'Titles do not establish safety, cooling effectiveness, demand, quality or buying intent',
 'human_gold':0}

def write_csv(path,rows):
 path.parent.mkdir(parents=True,exist_ok=True)
 import io
 s=io.StringIO(newline=''); w=csv.DictWriter(s,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 data=('\ufeff'+s.getvalue()).encode('utf-8')
 if path.exists() and path.read_bytes()!=data: raise ValueError('IMMUTABLE_CSV_CONFLICT')
 if not path.exists():path.write_bytes(data)

def prepare():
 OUT.mkdir(parents=True,exist_ok=True)
 source=read(b24.SOURCE)
 if b24.p.filehash(source['source_file'])!=source['source_sha256']:raise ValueError('SOURCE_CHANGED')
 inputs=lines(b24.INPUTS); byid={r['record_id']:r for r in inputs}
 sources=[]
 for i,r in enumerate(lines(BASE/'paired_results_100.jsonl'),1):sources.append({'review_id':f'B{i:03d}','role':'prior100_diagnosis','source':byid[r['record_id']]})
 for i,r in enumerate(csv.DictReader(CAL.open(encoding='utf-8-sig')),1):sources.append({'review_id':f'C{i:02d}','role':'calibration12','focus_id':r['编号'],'source':byid[r['商品来源记录ID']]})
 b24.p.immutable(OUT/'review_sources_112.jsonl',sources,jsonl=True)
 b24.p.immutable(OUT/'policy.json',POLICY)
 if (OUT/'inputs_150.jsonl').exists():return
 forbidden=b24.prior_title_hashes()|b25.focus_titles()|b25.prior_v25_titles()|{b24.title_hash(r['title_original']) for r in lines(b24.OUT/'inputs_500.jsonl')}
 available=[r for r in inputs if b24.title_hash(r['title_original']) not in forbidden]
 strata=[('explicit_boundary_cues',20,r'aire acondicionado.*\b\d{4,5}\s*btu|\b(?:armero|armario para armas|caja de municiones|lavadora de carga|secadora de ropa|frigorifico combi|reactor industrial|maquina de moldeo)\b'),
 ('accessory_or_property_confusables',30,r'\b(?:filtro|repuesto|funda|cubierta|mando|soporte|deflector|desodorante|huevera)\b.*\b(?:frigorifico|lavadora|aire acondicionado)\b|\b(?:apto|apta|aptos|aptas)\b.*\b(?:lavavajillas|frigorifico)\b'),
 ('furniture_and_specialized_research',20,r'\b(?:armario|conjunto de salon|mueble de bano|caseta|cobertizo|estacion de energia|power station|escritorio|mesa de comedor|sofa)\b')]
 rng=random.Random(2026102251); chosen=[]; used=set();used_titles=set();pools={};shortfall={}
 for label,n,expr in strata:
  pool=[r for r in available if re.search(expr,norm(r['title_original']))];rng.shuffle(pool);pools[label]=len(pool);count=0
  for row in pool:
   h=b24.title_hash(row['title_original'])
   if row['record_id'] in used or h in used_titles:continue
   chosen.append(dict(row,sample_cohort=label));used.add(row['record_id']);used_titles.add(h);count+=1
   if count==n:break
  shortfall[label]=n-count
 rest=[r for r in available if r['record_id'] not in used];rng.shuffle(rest)
 for row in rest:
  if len(chosen)==150:break
  h=b24.title_hash(row['title_original'])
  if h in used_titles:continue
  chosen.append(dict(row,sample_cohort='seeded_random_remainder'));used_titles.add(h)
 if len(chosen)!=150:raise ValueError('INSUFFICIENT_SAMPLE')
 b24.p.immutable(OUT/'inputs_150.jsonl',chosen,jsonl=True)
 b24.p.immutable(OUT/'sampling.json',{'seed':2026102251,'size':150,'stratum_counts':dict(collections.Counter(r['sample_cohort'] for r in chosen)),'candidate_pool_sizes':pools,'quota_shortfalls':shortfall,'prior_rows_excluded':len(inputs)-len(available),'exact_prior_title_overlap':len(used_titles & forbidden),'selection_used_model_predictions':False,'sample_interpretation':'Targeted strata and random remainder reported separately; not population accuracy'})
 b24.p.immutable(OUT/'frozen_contract.json',{'source_sha256':source['source_sha256'],'action_index_sha256':b24.p.filehash(RUN/'retrieval_index.joblib'),'v24_engine_sha256':b24.p.filehash(b24.__file__),'v25_engine_sha256':b24.p.filehash(b25.__file__),'policy_sha256':b24.p.filehash(OUT/'policy.json'),'inputs_sha256':b24.p.filehash(OUT/'inputs_150.jsonl'),'rule_edit_after_new_sample_review':False})

def bind_annotations(file,sources,refs):
 raw=lines(file); source_map={r['review_id']:r for r in sources}
 if len(raw)!=len(source_map) or {r['review_id'] for r in raw}!=set(source_map):raise ValueError('ANNOTATION_COVERAGE_MISMATCH')
 result=[]
 for r in raw:
  src=source_map[r['review_id']]['source'];r=dict(r)
  if r['decision'] not in POLICY['public_labels']:raise ValueError('BAD_PUBLIC_LABEL')
  if not r.get('reason') or not r.get('subject_evidence') or norm(r['subject_evidence']) not in norm(src['title_original']):raise ValueError('SOURCE_EVIDENCE_MISSING:'+r['review_id'])
  ar=[]
  for sku in r.pop('action_skus',[]):
   a=refs[sku];ar.append({'action_sku':sku,'action_title':a['name_es_original'],'action_source_row_id':a['source_row_id']})
  if r['decision']=='保留' and (not ar or r['reference_relation']!='SAME_FUNCTIONAL_CLASS'):raise ValueError('KEEP_WITHOUT_BOUND_REFERENCE:'+r['review_id'])
  if r['decision']=='用不到' and not r.get('boundary_code'):raise ValueError('EXCLUSION_WITHOUT_BOUNDARY')
  result.append(r|{'source_record_id':src['record_id'],'input_hash':src['input_hash'],'title_original':src['title_original'],'action_references':ar,'human_confirmed':False,'review_authority':'CODEX_AI_DELEGATED','policy_version':POLICY['version']})
 return result

def materialize_ai_records(stem):
 path=OUT/(stem+'.tsv');rows=[]
 with path.open(encoding='utf-8-sig',newline='') as f:
  for r in csv.DictReader(f,delimiter='|'):
   if None in r or any(v is None for v in r.values()):raise ValueError('MALFORMED_AI_REVIEW_ROW:'+str(r))
   r['action_skus']=[x.strip() for x in r['action_skus'].split(',') if x.strip()]
   r['reference_relation']='SAME_FUNCTIONAL_CLASS' if r['decision']=='保留' else ('RELATED_NEED' if r['action_skus'] else 'NO_VERIFIED_REFERENCE')
   r['review_id']=r['review_id'].strip();rows.append(r)
 b24.p.immutable(OUT/(stem+'_raw.jsonl'),rows,jsonl=True)
 return rows

def finalize():
 materialize_ai_records('ai_review_112');materialize_ai_records('ai_review_150')
 matcher=Matcher();refs={r['sku']:r for r in matcher.model['references']}
 old_sources=lines(OUT/'review_sources_112.jsonl')
 new_sources=[{'review_id':f'N{i:03d}','source':r} for i,r in enumerate(lines(OUT/'inputs_150.jsonl'),1)]
 reviewed=bind_annotations(OUT/'ai_review_112_raw.jsonl',old_sources,refs)
 new=bind_annotations(OUT/'ai_review_150_raw.jsonl',new_sources,refs)
 old_baseline={r['record_id']:r['v25'] for r in lines(BASE/'paired_results_100.jsonl')}
 diag=[]
 for r in reviewed:
  if not r['review_id'].startswith('B'):continue
  b=old_baseline[r['source_record_id']]
  if b['decision']!='观察':continue
  flags=[]
  if b['product_subject_status']=='UNCLEAR' and r['subject_status']=='CLEAR':flags.append('PROGRAM_SUBJECT_EXTRACTION_GAP')
  if r['decision']=='保留' and not b['action_reference_same_class']:flags.append('RETRIEVAL_OR_RELATION_MISSED_KEEP')
  if r['decision']=='保留' and b['boundary_status'] in {'UNCONFIRMED_CUE','RESEARCH_ONLY'}:flags.append('FALSE_BOUNDARY_CUE')
  if r['decision']=='用不到':flags.append('MISSED_EXPLICIT_BOUNDARY')
  if r['decision']=='观察':flags.append('OBSERVE_STILL_JUSTIFIED_UNDER_POLICY')
  diag.append({'review_id':r['review_id'],'record_id':r['source_record_id'],'baseline_reason':b['reason_code'],'ai_decision':r['decision'],'ai_primary_cause':r['primary_cause'],'diagnostic_flags':flags,'subject':r['subject'],'title':r['title_original'],'reason':r['reason']})
 v23={r['sku']:r for r in lines(b24.V23)};paired=[]
 for src,r in zip(new_sources,new):
  row=src['source'];ft=matcher.f.extract(row['title_original'],True);b=b24.boundary_for_title(row['title_original'],ft)
  old=b24.refs_and_decision(row|{'_v24_feature':ft,'_v24_boundary':b},matcher,v23)
  base=b25.analyze(row,matcher,v23)
  paired.append({'review_id':r['review_id'],'sample_cohort':row['sample_cohort'],'v24':old,'v25':base,'ai_review':r})
 summary={'calibration12_decisions':dict(collections.Counter(r['decision'] for r in reviewed if r['review_id'].startswith('C'))),'prior100_ai_decisions':dict(collections.Counter(r['decision'] for r in reviewed if r['review_id'].startswith('B'))),'observations_reviewed':len(diag),'observations_primary_causes':dict(collections.Counter(r['ai_primary_cause'] for r in diag)),'diagnostic_flags_nonexclusive':dict(collections.Counter(f for r in diag for f in r['diagnostic_flags'])),'new150':{k:dict(collections.Counter((r[k]['decision'] if k!='ai_review' else r[k]['decision']) for r in paired)) for k in ['v24','v25','ai_review']},'new150_by_stratum':{s:{k:dict(collections.Counter(r[k]['decision'] for r in paired if r['sample_cohort']==s)) for k in ['v24','v25','ai_review']} for s in sorted({r['sample_cohort'] for r in paired})},'ai_review_is_human_gold':False,'human_gold':0,'accuracy':None,'model_improvement_measured':False,'master_written':False,'full_action_retraining':False,'formal_amazon_results_replaced':False,'next_action':'Proceed only to targeted subject extraction and semantic reference retrieval optimization; do not expand to full snapshot yet.'}
 for name,value in [('ai_review_112_bound.jsonl',reviewed),('ai_review_150_bound.jsonl',new),('observations_97_diagnosis.jsonl',diag),('paired_new150.jsonl',paired)]:b24.p.immutable(OUT/name,value,jsonl=True)
 b24.p.immutable(OUT/'summary.json',summary)
 for name,rs in [('calibration12_review.csv',[r for r in reviewed if r['review_id'].startswith('C')]),('prior100_review.csv',[r for r in reviewed if r['review_id'].startswith('B')]),('new150_review.csv',new)]:
  write_csv(OUT/name,[{'审核ID':r['review_id'],'西语原名':r['title_original'],'商品主体':r['subject'],'主体依据':r['subject_evidence'],'AI裁定':r['decision'],'原因':r['reason'],'问题归因':r['primary_cause'],'参照层级':r['reference_relation'],'Action参照SKU':' / '.join(a['action_sku'] for a in r['action_references']),'Action参照原名':' / '.join(a['action_title'] for a in r['action_references']),'边界代码':r.get('boundary_code',''),'来源记录':r['source_record_id'],'来源Hash':r['input_hash'],'人工确认':False} for r in rs])
 # One verified backup before the optional AI-review namespace is appended.
 backup=OUT/'learning_before_ai_review.sqlite3'
 if not backup.exists():
  with sqlite3.connect(b25.DB) as src,sqlite3.connect(backup) as dst:src.backup(dst)
 with sqlite3.connect(backup) as c:
  if c.execute('pragma integrity_check').fetchone()[0]!='ok':raise ValueError('BAD_BACKUP')
 run_id='v251-ai-review-'+b24.p.digest({'contract':read(OUT/'frozen_contract.json'),'reviews':reviewed+new})[:16]
 with sqlite3.connect(b25.DB) as c:
  c.execute('PRAGMA foreign_keys=ON')
  before={t:c.execute('SELECT count(*) FROM "'+t+'"').fetchone()[0] for t, in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'") if not t.startswith('assortment_v251_ai_')}
  c.executescript('CREATE TABLE IF NOT EXISTS assortment_v251_ai_runs(run_id TEXT PRIMARY KEY,payload TEXT NOT NULL); CREATE TABLE IF NOT EXISTS assortment_v251_ai_reviews(run_id TEXT NOT NULL,review_id TEXT NOT NULL,input_hash TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(run_id,review_id),FOREIGN KEY(run_id) REFERENCES assortment_v251_ai_runs(run_id));')
  b24.insert_exact(c,'assortment_v251_ai_runs',['run_id','payload'],[run_id,b24.p.canonical(summary)],1)
  inserted=sum(b24.insert_exact(c,'assortment_v251_ai_reviews',['run_id','review_id','input_hash','payload'],[run_id,r['review_id'],r['input_hash'],b24.p.canonical(r)],2) for r in reviewed+new)
  repeated=sum(b24.insert_exact(c,'assortment_v251_ai_reviews',['run_id','review_id','input_hash','payload'],[run_id,r['review_id'],r['input_hash'],b24.p.canonical(r)],2) for r in reviewed+new)
  if repeated:raise ValueError('NON_IDEMPOTENT')
  after={t:c.execute('SELECT count(*) FROM "'+t+'"').fetchone()[0] for t in before}
  if before!=after:raise ValueError('UNRELATED_TABLE_CHANGED')
  integrity=c.execute('pragma integrity_check').fetchone()[0];fk=c.execute('pragma foreign_key_check').fetchall()
  if integrity!='ok' or fk:raise ValueError('INTEGRITY_FAILURE')
 b24.p.immutable(OUT/'persistence.json',{'run_id':run_id,'review_records':262,'replay_inserted':repeated,'integrity':integrity,'foreign_keys':len(fk),'unrelated_table_counts_unchanged':True,'backup_integrity':'ok'})
 print(json.dumps(summary,ensure_ascii=False,indent=2))
 print(json.dumps({'run_id':run_id,'inserted_this_attempt':inserted,'exact_repeat_inserted':repeated},ensure_ascii=False))

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('command',choices=['prepare','finalize']);args=a.parse_args()
 prepare() if args.command=='prepare' else finalize()
