"""Bind original CSV rows and freeze unseen technical/review memberships."""
import argparse,collections,csv,hashlib,json,random,re,sqlite3
from pathlib import Path
from assortment import ROOT,RUN,read,lines,p,connect,exact_insert,norm,tokens

def identity(s):
 m=re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})',str(s),re.I)
 return 'ASIN_HINT:'+m.group(1).upper() if m else norm(str(s)).split('/ref=')[0].split('?')[0]

def prepare(path):
 path=Path(path).resolve();sha=p.filehash(path)
 if path.is_relative_to(ROOT/'v2'):raise ValueError('SELECT_ORIGINAL_EXTERNAL_SNAPSHOT')
 with path.open(encoding='utf-8-sig',newline='') as f:raw=list(csv.DictReader(f))
 if not raw:raise ValueError('EMPTY_AMAZON_SOURCE')
 headers=set(raw[0]);title=next((v for v in ['product_title_raw','商品名称（西班牙语）','title_original','title','商品品名'] if v in headers),None)
 if not title:raise ValueError('SOURCE_TITLE_FIELD_NOT_IDENTIFIED')
 category=next((v for v in ['amazon_category_l1','category_l1','一级类目'] if v in headers),None)
 aux=next((v for v in ['research_category','研究类目（未确证留空）'] if v in headers),None)
 group=next((v for v in ['target_review_group','target_group_key','候选组ID','candidate_id','record_id'] if v in headers),None)
 url=next((v for v in ['normalized_product_url','商品链接（规范化）','product_url','absolute_product_url'] if v in headers),None)
 records=[];provenance=[]
 for i,r in enumerate(raw,2):
  rid='AMZV2_'+sha[:12]+'_'+str(i).zfill(6)
  data={'record_id':rid,'source_record_id':r.get(group,'') if group else '', 'source_row':i,'title_original':r.get(title,'') or '', 'category_l1_original':r.get(category,'') or '' if category else '', 'category_auxiliary':r.get(aux,'') or '' if aux else '', 'url_original':r.get(url,'') or '' if url else '', 'identity_semantics':'SOURCE_ROW_NOT_VERIFIED_UNIQUE_BUYABLE_SKU','source_file_sha256':sha}
  data['input_hash']=p.digest(data);records.append(data);provenance.append({'record_id':rid,'original_file':str(path),'physical_csv_row':i,'raw_row':r,'raw_row_hash':p.digest(r)})
 assert len(records)==len({r['record_id'] for r in records})
 assert p.filehash(path)==sha,'SOURCE_CHANGED_DURING_READ'
 # Prior identities and exact/near title variants are excluded from new tests,
 # never removed from the eventual full experiment output.
 prior_ids=set();prior_title=set();prior_tokens=[]
 with sqlite3.connect((ROOT/'learning_data/action_selection.sqlite3').as_uri()+'?mode=ro',uri=True) as c:
  old=[json.loads(r[0]) for r in c.execute("SELECT source_json FROM cross_platform_samples WHERE platform='Amazon'")]
 for r in old:
  for k in ['platform_sku','product_url','source_record_id','target_review_group']:
   if r.get(k):prior_ids.add(identity(r[k]))
  t=r.get('title_original','');prior_title.add(norm(t));prior_tokens.append(set(tokens(t)))
 previous_technical=RUN/'prototype_1_before_technical_gate/technical500_inputs.jsonl'
 development=lines(previous_technical) if previous_technical.exists() else []
 for r in development:
  prior_ids.add(identity(r['url_original']));prior_title.add(norm(r['title_original']));prior_tokens.append(set(tokens(r['title_original'])))
 eligible=[];excluded=collections.Counter()
 for r in records:
  ts=set(tokens(r['title_original']))
  if identity(r['url_original']) in prior_ids or identity(r['source_record_id']) in prior_ids or norm(r['title_original']) in prior_title:excluded['previous_identity_or_exact_title']+=1;continue
  if any(len(ts&prev)>=5 and len(ts&prev)/max(1,len(ts|prev))>=.80 for prev in prior_tokens):excluded['previous_near_title']+=1;continue
  if not r['title_original'].strip():excluded['empty_title']+=1;continue
  eligible.append(r)
 rng=random.Random(2026102202);ordered=sorted(eligible,key=lambda r:r['record_id']);rng.shuffle(ordered)
 # Uniform random diagnostic frame is retained separately from purposive hard cases.
 random400=ordered[:400];used={r['record_id'] for r in random400}
 hard_expr=re.compile(r'industrial|laboratorio|compatible|recambio|repuesto|mesa|sofa|armario|kit|adaptador|profesional|filtro|[\u3400-\u9fff]',re.I)
 hard=[r for r in ordered if r['record_id'] not in used and (hard_expr.search(r['title_original']) or len(tokens(r['title_original']))<5)][:100]
 if len(hard)!=100:raise ValueError('INSUFFICIENT_UNSEEN_DIAGNOSTIC_CASES')
 pilot=random400+hard;membership=[{'record_id':r['record_id'],'cohort':'UNIFORM_RANDOM_400' if i<400 else 'PURPOSIVE_DIFFICULT_100','input_hash':r['input_hash']} for i,r in enumerate(pilot)]
 review=[{'record_id':r['record_id'],'cohort':'RANDOM_REVIEW_120','input_hash':r['input_hash']} for r in random400[:120]]+[{'record_id':r['record_id'],'cohort':'DIFFICULT_REVIEW_80','input_hash':r['input_hash']} for r in hard[:80]]
 manifest={'source_file':str(path),'source_sha256':sha,'source_rows':len(raw),'stable_record_id_policy':'Source file hash plus logical CSV record ordinal (header row counted); source group and URL preserved separately. Never infer a verified SKU.','fields':{'title':title,'official_l1':category,'auxiliary_unverified_category':aux,'original_record_id':group,'original_url':url},'official_l1_nonempty':sum(bool(r['category_l1_original']) for r in records),'aux_category_nonempty':sum(bool(r['category_auxiliary']) for r in records),'prior_test_exclusion_counts':dict(excluded),'development500_excluded':len(development),'eligible_new_test_rows':len(eligible),'pilot_count':500,'random_cohort':400,'difficult_cohort':100,'human_review_count':200,'human_labels':0,'frozen_method_manifest_sha256':p.filehash(RUN/'method_manifest.json'),'all_rows_retained':True,'input_identity_warning':'URL groups / source records, not independently verified unique buyable SKU count'}
 p.immutable(RUN/'amazon_source_manifest.json',manifest);p.immutable(RUN/'amazon_inputs.jsonl',records,jsonl=True);p.immutable(RUN/'amazon_raw_row_mapping.jsonl',provenance,jsonl=True);p.immutable(RUN/'technical500_inputs.jsonl',pilot,jsonl=True);p.immutable(RUN/'technical500_membership.jsonl',membership,jsonl=True);p.immutable(RUN/'human_review200_membership.jsonl',review,jsonl=True)
 run_id=read(RUN/'run_identity.json')['run_id']
 with connect() as c:
  for r,source in zip(records,provenance):exact_insert(c,'assortment_v2_amazon',['run_id','record_id'],{'run_id':run_id,'record_id':r['record_id'],'ordinal':r['source_row']-2,'source_hash':r['input_hash'],'payload':p.canonical({'input':r,'provenance':source})})
 print(json.dumps(manifest,ensure_ascii=False,indent=2))

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--source',required=True);prepare(a.parse_args().source)
