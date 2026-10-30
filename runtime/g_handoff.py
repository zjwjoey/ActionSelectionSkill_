"""G-group portability/IO glue. Original algorithms and business rules unchanged."""
import csv,json,hashlib,os,shutil,zipfile,collections,copy
from pathlib import Path
from runtime.v3.core import digest,source_record
from runtime.v3.workflow import filehash,write_jsonl,load_rows
ROOT=Path(__file__).resolve().parents[1]
VERSION='G-ACTION-V331-20261030-v1'

def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def save(path,obj):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

def diagnostics(value,key=''):
 # Native attribute diagnostics iterate a set. This unordered diagnostic table
 # is compared by attribute; ranking/matches and all numerical values stay exact.
 if isinstance(value,dict):return {k:diagnostics(v,k) for k,v in value.items()}
 if isinstance(value,(list,tuple)):
  vals=[diagnostics(v) for v in value]
  return sorted(vals,key=lambda v:(v.get('attribute',''),digest(v))) if key=='comparisons' else vals
 return value

def restore(downloads,destination,manifest_sha):
 downloads=Path(downloads);destination=Path(destination).resolve();manifest=load(downloads/'bundle_manifest.json')
 if filehash(downloads/'bundle_manifest.json')!=manifest_sha:raise ValueError('ASSET_MANIFEST_HASH_MISMATCH')
 for archive in manifest['archives']:
  p=downloads/archive['file']
  if filehash(p)!=archive['sha256']:raise ValueError('ARCHIVE_HASH_MISMATCH')
  with zipfile.ZipFile(p) as z:
   if set(z.namelist())!=set(archive['files']):raise ValueError('ARCHIVE_FILE_SET_MISMATCH')
   for item in z.infolist():
    target=(destination/item.filename).resolve()
    if not target.is_relative_to(destination) or item.is_dir() or item.file_size!=archive['files'][item.filename]['bytes']:raise ValueError('UNSAFE_ARCHIVE_MEMBER')
    if target.exists():
     if filehash(target)!=archive['files'][item.filename]['sha256']:raise ValueError('RESTORE_TARGET_CHANGED')
     continue
    target.parent.mkdir(parents=True,exist_ok=True)
    with z.open(item) as src,target.open('xb') as out:shutil.copyfileobj(src,out)
    if filehash(target)!=archive['files'][item.filename]['sha256']:raise ValueError('EXTRACTED_HASH_MISMATCH')
 save(destination/'asset_receipt.json',dict(version=manifest['version'],manifest_sha=manifest_sha,files=sum(len(a['files']) for a in manifest['archives']),archives=[dict(file=a['file'],sha256=a['sha256']) for a in manifest['archives']]))
 return manifest

def runtime_index(assets,output):
 assets=Path(assets).resolve();out=Path(output).resolve();out.mkdir(parents=True,exist_ok=True)
 meta=load(assets/'e5/index.original.json');meta['model_path']=str(assets/'e5/model');meta['model_files']={k.replace('\\','/'):v for k,v in meta['model_files'].items()}
 target=out/'vectors.npy'
 if not target.exists():
  try:os.link(assets/'e5/vectors.npy',target)
  except OSError:shutil.copyfile(assets/'e5/vectors.npy',target)
 if filehash(target)!=meta['vectors_sha']:raise ValueError('RELOCATED_VECTOR_HASH_MISMATCH')
 if (out/'index.json').exists() and load(out/'index.json')!=meta:raise ValueError('INDEX_RELOCATION_CONTRACT_CHANGED')
 save(out/'index.json',meta);return out

def references(assets):
 from runtime.retail.engine import References
 assets=Path(assets);refs=References('action',None);mapping=load(assets/'source_map.json')
 for r in load_rows(assets/'references/action_latest.jsonl'):
  path=r['source_file']
  if path not in refs.hashes:
   mapped=mapping.get(path)
   if not mapped:raise ValueError('REFERENCE_SOURCE_MAPPING_MISSING')
   actual=filehash(assets/mapped['path'])
   if actual!=mapped['sha256']:raise ValueError('REFERENCE_SOURCE_BYTES_CHANGED')
   refs.hashes[path]=actual
  refs.quotes[r['sku']]={'source_product_id':r['sku'],'title_original':r['title'],'specifications':r.get('spec',''),'variant':'','price_value':r['price']['value'],'price_currency':r['price']['currency'],'price_type':'retail','price_date':r['source_date'],'source_file':path,'source_sha256':r['source_sha256'],'source_url':r['url'],'binding_valid':r['title_binding_exact']}
 return refs

def envelope(source,native,profile):
 a=native.get('analysis') or native.get('semantic') or {};business='decision' in native
 return dict(group='G',g_version=VERSION,profile=profile,product_id=source['product_id'],original_name=source['original_name'],category_l1=source.get('category_l1',''),source_version=source['source_version'],source_hash=digest(source),status='COMPLETE' if a else 'NEEDS_PROVIDER',subject=dict(text=a.get('sold_subject') or a.get('subject_type'),literal_span=a.get('subject_span'),role=a.get('form'),authority='NATIVE_AI_CANDIDATE_NOT_GOLD'),functions=a.get('functions'),uses=a.get('needs'),dependencies=dict(items=a.get('dependencies'),status='NOT_EXPLICITLY_PRODUCED' if not a.get('dependencies') else 'NATIVE_OUTPUT'),matching=dict(primary=native.get('primary') or native.get('reference'),matches=native.get('matches'),original_score_10=native.get('match_score_10'),score_definition='Original provisional index; not demand probability'),selection=native.get('decision') if business else None,selection_status='NATIVE_THREE_STATE' if business else 'NOT_PRODUCED_BY_MATCH_PROFILE',uncertainty=a.get('unknowns',[])+native.get('issues',[]),basis=a.get('reason'),native_result_hash=digest(native),native_fields_missing_are_null=True,human_gold=False)

def normalize(rows):
 valid=[];fail=[];seen=set()
 for i,r in enumerate(rows):
  try:
   if not isinstance(r,dict) or any(not isinstance(r.get(k),str) or not r[k].strip() for k in ['product_id','original_name','source_version']):raise ValueError('ID_NAME_SOURCE_VERSION_REQUIRED')
   if r['product_id'].strip() in seen:raise ValueError('DUPLICATE_PRODUCT_ID')
   seen.add(r['product_id'].strip());valid.append(r)
  except ValueError as exc:fail.append(dict(group='G',input_index=i,product_id=r.get('product_id') if isinstance(r,dict) else None,status='INVALID_INPUT',error=str(exc)))
 return valid,fail

def run(input_file,assets,out,profile='native_v321',mode='queue',analysis=None,batch_size=10):
 from runtime.retail import match10
 from runtime.retail.ingestion import ingest
 from runtime.retail.learning_pipeline import Extension
 from runtime.v31.state import State
 from runtime.v31.model import Model
 from runtime.v3.catalog import Catalog
 from runtime.v3.workflow import Provider,screen
 out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True);assets=Path(assets).resolve();rows,errors=normalize(load_rows(input_file))
 if profile not in ['native_v31','native_v321','business_v3']:raise ValueError('PROFILE_REQUIRED')
 contract=dict(version=VERSION,input_sha=filehash(input_file),asset_manifest=load(assets/'asset_receipt.json')['manifest_sha'],profile=profile)
 if (out/'contract.json').exists() and load(out/'contract.json')!=contract:raise ValueError('RESUME_CONTRACT_CHANGED')
 save(out/'contract.json',contract)
 if not rows:
  write_jsonl(out/'results.jsonl',errors);summary=dict(total=len(errors),complete=0,pending=0,failed=0,invalid=len(errors),provider_calls_this_attempt=0);save(out/'summary.json',summary)
  with (out/'results.csv').open('w',encoding='utf-8-sig',newline='') as f:
   w=csv.DictWriter(f,fieldnames=['group','input_index','product_id','status','error']);w.writeheader();w.writerows(errors)
  return summary
 if profile=='business_v3':
  # This legacy algorithm has functions/needs and its OWN three-state policy.
  # It is never silently substituted for the matching profile.
  if mode=='codex':raise ValueError('BUSINESS_V3_USES_ORIGINAL_FILE_OR_COMMAND_PROVIDER; PROVIDE_ANALYSIS')
  raw=[dict(record_id=r['product_id'],title_original=r['original_name'],source_version=r['source_version']) for r in rows]
  provider=Provider('file',notes=analysis) if analysis else Provider('queue');summary=screen(ROOT,raw,out/'legacy.sqlite3',out/'legacy',provider,Catalog(ROOT),purpose='pilot');native=load_rows(Path(summary['output'])/'results.jsonl')
  results=[envelope(r,n,profile) for r,n in zip(rows,native)];write_jsonl(out/'native_results.jsonl',native)
 else:
  raw=[dict(source_product_id=r['product_id'],title_original=r['original_name'],category_original=r.get('category_l1',''),source_platform=r.get('source_platform','g-input'),source_version=r['source_version'],specifications=r.get('specifications',''),variant=r.get('variant',''),brand=r.get('brand','')) for r in rows]
  write_jsonl(out/'normalized_input.jsonl',raw)
  products,ingest_errors=ingest(out/'normalized_input.jsonl');refs=references(assets);ext=Extension(runtime_index(assets,out/'e5_runtime'),'off') if profile=='native_v321' else None
  if ext:ext.bind(refs)
  method=digest(dict(native_signature=match10.signature(refs,None),g_contract=contract));requests=[]
  for row in products:
   candidates=ext.retrieve(refs,row) if ext else match10.retrieve(refs,row);q=dict(record_id=row['quote_id'],title=row['title_original'],spec=row['specifications'],variant=row['variant'],category1=row['category_original'],action_candidates=candidates,method_signature=method)
   if ext:ext.prepare(row,q)
   q['source_hash']=digest(q);requests.append(q)
  write_jsonl(out/'requests.jsonl',requests);save(out/'analysis_schema.json',match10.schema(requests));(out/'native_prompt.txt').write_text(match10.PROMPT,encoding='utf8')
  state=State(out/'state.sqlite3');model=Model(state,out/'calls',mode=mode,notes=analysis,instruction=match10.PROMPT,schema_factory=match10.schema,validator=match10.validate);native=[];results=[]
  try:
   for start in range(0,len(requests),batch_size):
    chunk=requests[start:start+batch_size];answers={};failure=None
    for attempt in range(2):
     try:answers={a['record_id']:a for a in model.run(chunk,'understand')};break
     except ValueError as exc:
      failure=str(exc)
      if attempt:break
    for src,row,q in zip(rows[start:start+batch_size],products[start:start+batch_size],chunk):
     a=answers.get(q['record_id'])
     if a:
      n=ext.project(row,a,q['action_candidates'],refs,method,'G_ORIGINAL_MODEL_ADAPTER') if ext else match10.project(row,a,q['action_candidates'],refs,method,'G_ORIGINAL_MODEL_ADAPTER');native.append(n);results.append(envelope(src,n,profile))
     else:results.append(dict(group='G',product_id=src['product_id'],source_version=src['source_version'],status='FAILED' if failure else 'NEEDS_PROVIDER',error=failure,native_request_id=q['record_id']))
    write_jsonl(out/'results.jsonl',results+errors)
   write_jsonl(out/'native_results.jsonl',native);summary=dict(total=len(rows)+len(errors),complete=sum(r['status']=='COMPLETE' for r in results),pending=sum(r['status']=='NEEDS_PROVIDER' for r in results),failed=sum(r['status']=='FAILED' for r in results),invalid=len(errors),provider_calls_this_attempt=model.calls,cache_reused=model.reused,integrity=state.store.check())
  finally:
   state.close()
   if ext:ext.close()
 results+=errors;write_jsonl(out/'results.jsonl',results)
 with (out/'results.csv').open('w',encoding='utf-8-sig',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=['group','product_id','source_version','status','selection','original_score_10']);writer.writeheader()
  for r in results:writer.writerow({**{k:r.get(k) for k in ['group','product_id','source_version','status','selection']},'original_score_10':r.get('matching',{}).get('original_score_10')})
 save(out/'summary.json',summary);return summary

def verify_restore(assets,out):
 from runtime.retail.learning_pipeline import Extension
 from runtime.retail.pair_learning import load_model,read,rerank
 assets=Path(assets);out=Path(out);out.mkdir(parents=True,exist_ok=True);refs=references(assets);index=runtime_index(assets,out/'e5_runtime');ext=Extension(index,'off');ext.bind(refs);checks=[]
 fields=['primary','matches','match_score_10','effective_analysis','attribute_checks','evidence_status']
 for item in load(assets/'validation/native_canaries.json'):
  r=item['result'];q=item['request'];row=r['source'];ext.traces[row['quote_id']]=r['retrieval_trace']
  restored=ext.project(row,r['analysis'],q['action_candidates'],refs,r['method'],'CLOUD_CACHED_MODEL_REPLAY')
  for field in fields:
   if diagnostics(restored[field])!=diagnostics(r[field]):raise ValueError('NATIVE_REPLAY_DIFFERENCE:'+field)
  candidates,trace=ext.retriever.search(row,20)
  if trace['rrf50']!=r['retrieval_trace']['rrf50']:raise ValueError('FRESH_RETRIEVAL_ORDER_DIFFERENCE')
  expected={c['sku']:c for c in q['action_candidates']}
  for c in candidates:
   for key in ['retrieval_score','semantic_score']:
    if c.get(key) is not None and abs(c[key]-expected[c['sku']][key])>3e-6:raise ValueError('FRESH_RETRIEVAL_SCORE_DIFFERENCE')
  checks.append(dict(native_replay='PASS',fresh_text_e5_rrf='PASS'))
 root=assets/'research/v331';pairs=read(root/'new80_features_unlabeled.jsonl');by=collections.defaultdict(list)
 for p in pairs:by[p['input_id']].append(p)
 models={k:load_model(root/f'models/{k}.json') for k in load(root/'models_freeze.json')['models']};models.update(V33_B=load_model(assets/'research/v33/models/B.json'),V33_C=load_model(assets/'research/v33/models/C.json'))
 predictions=load(root/'new80_frozen_predictions.json')
 for pred in predictions:
  if [p['pair_id'] for p in rerank(models[pred['model']],by[pred['input_id']],True)]!=pred['ordered_pair_ids']:raise ValueError('TRAINED_RANKER_REPLAY_DIFFERENCE')
 result=dict(asset_receipt=load(assets/'asset_receipt.json'),canaries=len(checks),fresh_e5_rrf_checks=checks,ranked_products=len(by),ranked_model_paths=len(models),exact_rankings=len(predictions),native_scores_replayed=True,paid_or_live_ai_calls=0,live_new_product_ai_verified=False,human_quality_accepted=False,root=str(ROOT),platform=__import__('platform').platform());save(out/'restore_verification.json',result);return result
