"""Bind final method to existing source rows; reserve a genuinely new review200."""
import collections,json,random,re,sqlite3
from assortment import ROOT,RUN,WORK,p,read,lines,connect,exact_insert,tokens,norm
from amazon_inputs import identity
inputs=lines(RUN/'amazon_inputs.jsonl');run_id=read(RUN/'run_identity.json')['run_id']
with connect() as c:
 for r in inputs:exact_insert(c,'assortment_v2_amazon',['run_id','record_id'],{'run_id':run_id,'record_id':r['record_id'],'ordinal':r['source_row']-2,'source_hash':r['input_hash'],'payload':p.canonical({'input':r,'raw_mapping':'amazon_raw_row_mapping.jsonl','source_file_sha256':r['source_file_sha256']})})
prior=[]
with sqlite3.connect((ROOT/'learning_data/action_selection.sqlite3').as_uri()+'?mode=ro',uri=True) as c:
 for row in c.execute("SELECT source_json FROM cross_platform_samples WHERE platform='Amazon'"):
  r=json.loads(row[0]);prior.append({'title_original':r.get('title_original',''),'url_original':r.get('product_url',''),'record_id':None})
for file in [RUN/'prototype_1_before_technical_gate/technical500_inputs.jsonl',RUN/'technical500_inputs.jsonl']:prior+=lines(file)
prior_ids={r['record_id'] for r in prior};prior_urls={identity(r['url_original']) for r in prior if r['url_original']};prior_titles={norm(r['title_original']) for r in prior};prior_terms=[set(tokens(r['title_original'])) for r in prior]
pool=sorted(inputs,key=lambda r:p.digest(['independent200-finalV2.2',r['record_id']]))
def unseen(r):
 if r['record_id'] in prior_ids or identity(r['url_original']) in prior_urls or norm(r['title_original']) in prior_titles:return False
 ts=set(tokens(r['title_original']))
 return not any(len(ts&v)>=5 and len(ts&v)/max(1,len(ts|v))>=.8 for v in prior_terms)
random120=[]
for r in pool:
 if unseen(r):random120.append(r)
 if len(random120)==120:break
chosen={r['record_id'] for r in random120};hard=[]
for r in pool:
 if r['record_id'] not in chosen and re.search(r'profesional|industrial|compatible|recambio|repuesto|kit|adaptador|filtro|mesa|sofa|armario',r['title_original'],re.I) and unseen(r):hard.append(r)
 if len(hard)==80:break
review=random120+hard;assert len(review)==len({r['record_id'] for r in review})==200
membership=[{'record_id':r['record_id'],'input_hash':r['input_hash'],'cohort':'RANDOM_REVIEW_120' if i<120 else 'DIFFICULT_REVIEW_80'} for i,r in enumerate(review)]
old=RUN/'human_review200_membership.jsonl'
if old.exists():old.rename(RUN/'prototype_2_validation_before_model_dependency_fix/development_review_membership.jsonl')
p.immutable(RUN/'independent200_inputs.jsonl',review,jsonl=True);p.immutable(RUN/'human_review200_membership.jsonl',membership,jsonl=True)
code_files=[WORK/name for name in ['assortment.py','amazon_inputs.py','comparison.py','policy.json']]
protocol={'method_manifest_sha256':p.filehash(RUN/'method_manifest.json'),'method_version':read(WORK/'policy.json')['version'],'amazon_source_sha256':read(RUN/'amazon_source_manifest.json')['source_sha256'],'technical500_role':'DEVELOPMENT_REGRESSION_NO_ACCURACY_CLAIM','independent200_role':'Fresh human review after final rule freeze; no exact/near previous trial or technical title identity','random_review':120,'purposive_review':80,'combined_ratio_not_population_estimate':True,'human_gold':0,'ordinary_AI_test_completed':False,'three_program_schemes_only':True,'code_sha256':{str(f.relative_to(ROOT)):p.filehash(f) for f in code_files},'technical500_sha256':p.filehash(RUN/'technical500_inputs.jsonl'),'independent200_sha256':p.filehash(RUN/'independent200_inputs.jsonl'),'shared_goal':'Everyday assortment first, complete furniture and dedicated parts retained for research; no price/brand/unknown-safety exclusions.'}
p.immutable(RUN/'final_trial_protocol.json',protocol)
p.immutable(RUN/'targeted_test_evidence.json',{'command':'F:/ActionSKUTracker/.venv/Scripts/python.exe v2/test_contracts.py','observed_exit_code':0,'observed_test_count':15,'scope':'Synthetic source, purpose, dependency, typed relation and unmatched retention contracts','production_test_or_formal_accuracy':False})
print(json.dumps({'new_review':200,'prior_development_rows':1000,'bound_source_rows':len(inputs),'source_l1_categories':dict(collections.Counter(r['category_l1_original'] or 'MISSING' for r in review))},ensure_ascii=False))
