"""Offline assortment research: corpus retrieval, typed relations and audit cache.

No production writes, external model calls or purchasing decisions. All source
identities and abstentions survive. A similarity score is not an accuracy score.
"""
from __future__ import annotations
import argparse,collections,csv,hashlib,json,re,sqlite3,sys,time,unicodedata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import pipeline as p
WORK=ROOT/'v2';RUN=WORK/'runs/action_assortment_v2_20261022'
DB=ROOT/'learning_data/action_selection.sqlite3'

def read(path):return json.loads(Path(path).read_text(encoding='utf8'))
def lines(path):return p.read_jsonl(Path(path))
def norm(s):
 return re.sub(r'\s+',' ',''.join(c for c in unicodedata.normalize('NFKD',str(s or '').lower()) if not unicodedata.combining(c))).strip()
def tokens(s):return re.findall(r'[a-z][a-z0-9]*',norm(s))
def connect():
 c=sqlite3.connect(DB,timeout=60);c.execute('PRAGMA foreign_keys=ON')
 c.executescript('''
 CREATE TABLE IF NOT EXISTS assortment_v2_runs(run_id TEXT PRIMARY KEY,contract TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS assortment_v2_action(run_id TEXT NOT NULL,sku TEXT NOT NULL,source_hash TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(run_id,sku),FOREIGN KEY(run_id) REFERENCES assortment_v2_runs);
 CREATE TABLE IF NOT EXISTS assortment_v2_amazon(run_id TEXT NOT NULL,record_id TEXT NOT NULL,ordinal INTEGER NOT NULL,source_hash TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(run_id,record_id),FOREIGN KEY(run_id) REFERENCES assortment_v2_runs);
 CREATE TABLE IF NOT EXISTS assortment_v2_results(run_id TEXT NOT NULL,record_id TEXT NOT NULL,method_version TEXT NOT NULL,input_hash TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(run_id,record_id,method_version),FOREIGN KEY(run_id,record_id) REFERENCES assortment_v2_amazon);
 CREATE TABLE IF NOT EXISTS assortment_v2_reviews(run_id TEXT NOT NULL,record_id TEXT NOT NULL,expected_result_hash TEXT NOT NULL,reviewer TEXT NOT NULL,human_target TEXT NOT NULL,reason TEXT NOT NULL,PRIMARY KEY(run_id,record_id,expected_result_hash,reviewer));
 ''');return c

def exact_insert(c,table,keys,row):
 names=list(row);where=' AND '.join(k+'=?' for k in keys)
 old=c.execute('SELECT '+','.join(names)+' FROM '+table+' WHERE '+where,[row[k] for k in keys]).fetchone()
 if old is not None:
  if tuple(old)!=tuple(row[k] for k in names):raise ValueError('IMMUTABLE_V2_ROW_CONFLICT:'+table)
  return False
 c.execute('INSERT INTO '+table+'('+','.join(names)+') VALUES('+','.join('?' for _ in names)+')',[row[k] for k in names]);return True

class Features:
 def __init__(self,policy):
  self.policy=policy;self.stop=set(policy['stopwords'].split());self.alias=policy['head_aliases']
  self.frames=[(key,label,re.compile(expr,re.I)) for key,label,expr in policy['task_frames']]
  self.compound_heads={'regalo','limpieza','cocina','manualidad','articulo','producto','profesional','industrial','pieza','accesorio','herramienta','hoja','protector','prensa','tela','llave','cafe','te','sal','pan','marco','arbol','filtro','cajon','tapon','perla','barra','fuente','gel','crema','cepillo','brocha','espatula','tijera','ventilador','aspirador','enchufe','adaptador'}
  self.roles={k:re.compile(v,re.I) for k,v in policy['role_patterns'].items()}
  self.head_vocabulary=set()
 def stem(self,w):
  w=self.alias.get(w,w)
  if len(w)>5 and w.endswith('es') and w[-3] in 'rlndz':w=w[:-2]
  elif len(w)>4 and w.endswith('s'):w=w[:-1]
  return self.alias.get(w,w)
 def words(self,title):return [self.stem(w) for w in tokens(title) if w not in self.stop]
 def action_head(self,title):
  # Source noun phrases, never source category or old Chinese labels.
  words=self.words(title);return words[0] if words else ''
 def build_vocabulary(self,rows):
  counts=collections.Counter(self.action_head(r['name_es_original']) for r in rows)
  self.head_vocabulary={k for k,v in counts.items() if v>=2 and len(k)>2 and k not in {'the','beauty','max','more','soft','home','royal','mini','fresh','lab31','nor','tec','fer','code','merry','christma'}}
 def extract(self,title,amazon=False):
  normalized=norm(title);words=self.words(title)
  identity_prefix=re.split(r'\b(?:para|con|sin|compatible|incluye|incluido|ideal|adecuado|como)\b|[,;|]',normalized,maxsplit=1)[0]
  prefix_words=self.words(identity_prefix)[:5]
  head=next((w for w in prefix_words if w in self.head_vocabulary),'') if amazon else self.action_head(title)
  # Detailed source phrase is evidence of type compatibility, not just an
  # overlapping noun somewhere in a long accessory/marketing title.
  phrase=prefix_words[prefix_words.index(head):][:3] if head in prefix_words else []
  frames=[];spans=[]
  for key,label,expr in self.frames:
   m=expr.search(normalized)
   if m:
    if key=='food_consumption' and re.search(r'\b(?:tela|textil|temporizador|tendedero|techo|salpicadero|pantalon|panel|pano|particula)\w*\b',m.group()):continue
    frames.append(key);spans.append({'task':key,'normalized_span':m.group(),'basis':'lexical purpose cue; inferred usual use, not verified fact'})
  # A named use qualifier takes precedence over a broad noun family.
  if re.search(r'\b(?:champu|cera|limpiador)\b.*\b(?:coche|auto|vehiculo)',normalized):
   frames=[f for f in frames if f not in {'hair_care','skin_care'}];frames.append('vehicle_cleaning')
  model_specific=bool(re.search(r'\bpara\s+[A-Z][A-Z0-9-]{2,}(?:\s+[A-Z][A-Z0-9-]{2,})?',title or '')) and bool(re.search(r'\b(?:kit de iluminacion|modulo|kit de montaje|adaptador|soporte|boquilla)\b',normalized))
  part=bool(self.roles['dedicated_part'].search(normalized)) or model_specific or bool(re.search(r'\b(?:hebilla|bisagra|portafiltro|tamper|prensador de cafe|boquilla|aireador|valvula|cierre para bolso)\w*\b',identity_prefix))
  furniture=bool(self.roles['furniture'].search(normalized[:100]))
  prefix=self.roles['furniture_accessory_prefix'].match(normalized)
  if prefix:furniture=False
  bad_source=bool(re.search('[\u3400-\u9fff\ufffd]',title or '')) or not bool(words)
  # A second noun after a purpose connector is not the independent main item.
  return {'head':head,'identity_prefix':identity_prefix,'type_phrase_tokens':phrase,'words':list(dict.fromkeys(words)), 'task_frames':sorted(set(frames)),
   'task_evidence':spans,'source_invalid':bad_source,'specific_type_supported':bool(head and head not in ({self.stem(v) for v in self.policy['generic_heads']}|self.compound_heads)),
   'retail_form':'DEDICATED_COMPONENT' if part else ('COMPLETE_FURNITURE' if furniture else 'NO_EXPLICIT_DEPENDENCY'),
   'independent_use':'TITLE_INDICATES_DEPENDENCY' if part else 'NOT_VERIFIED_FROM_TITLE',
   'professional_context':bool(self.roles['professional_context'].search(normalized)),
   'explicit_outside_scope':self.roles['explicit_outside_scope'].search(normalized).group() if self.roles['explicit_outside_scope'].search(normalized) else '',
   'qualifier_fragments':re.findall(r'\b(?:para|con|sin|compatible con)\s+[^,;.|]{1,70}',normalized)[:8]}

def build_action():
 import joblib,numpy as np,psutil
 from sklearn.feature_extraction.text import TfidfVectorizer
 from sklearn.decomposition import TruncatedSVD
 from sklearn.preprocessing import normalize
 from threadpoolctl import threadpool_limits
 start=time.perf_counter();policy=read(WORK/'policy.json');meta=read(RUN/'action_input_manifest.json')
 rows=lines(ROOT/'learning_data'/meta['snapshot_id']/'base.jsonl')
 seal=read(ROOT/'learning_data/p11/sealed_unseen50_plan.json');held={r['sku'] for r in seal['reserved_ids']};held_hash={r['title_sha256'] for r in seal['reserved_ids']}
 f=Features(policy)
 eligible=[r for r in rows if r['sku'] not in held and hashlib.sha256(r['name_es_normalized'].encode()).hexdigest() not in held_hash and not re.search('[\u3400-\u9fff\ufffd]',r['name_es_original'] or '') and len(tokens(r['name_es_original']))>0]
 f.build_vocabulary(eligible);inventory=[]
 for r in rows:
  if r['sku'] in held or hashlib.sha256(r['name_es_normalized'].encode()).hexdigest() in held_hash:
   x={'sku':r['sku'],'source_row_id':r['source_row_id'],'snapshot_id':r['snapshot_id'],'state':'RESERVED_HOLDOUT_NOT_USED','name_es_original':None,'feature':None}
  else:
   ft=f.extract(r['name_es_original']);x={'sku':r['sku'],'name_es_original':r['name_es_original'],'source_row_id':r['source_row_id'],'snapshot_id':r['snapshot_id'],'state':'SOURCE_ANOMALY' if ft['source_invalid'] else 'INDEXED_TITLE_ONLY','feature':ft,'original_category_comparison_only':r.get('category_original'),'original_category_l2_comparison_only':r.get('category_l2_original')}
  inventory.append(x)
 reference=[r for r in inventory if r['state']=='INDEXED_TITLE_ONLY']
 assert len(reference)==len(eligible)
 docs=[' '.join(f.words(r['name_es_original'])) for r in reference]
 word=TfidfVectorizer(ngram_range=(1,2),min_df=1,max_df=.85,max_features=25000,sublinear_tf=True,dtype=np.float32)
 char=TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5),min_df=2,max_features=40000,sublinear_tf=True,dtype=np.float32)
 with threadpool_limits(limits=3):
  wm=word.fit_transform(docs);cm=char.fit_transform([norm(r['name_es_original']) for r in reference]);svd=TruncatedSVD(n_components=min(128,wm.shape[1]-1),random_state=policy['seed'],n_iter=5);latent=normalize(svd.fit_transform(wm)).astype(np.float32)
 model={'policy':policy,'head_vocabulary':sorted(f.head_vocabulary),'word':word,'char':char,'svd':svd,'word_matrix':wm,'char_matrix':cm,'latent_matrix':latent,'references':reference}
 RUN.mkdir(exist_ok=True,parents=True);target=RUN/'retrieval_index.joblib'
 if target.exists():raise ValueError('INDEX_ALREADY_FROZEN_USE_EXISTING_OR_NEW_VERSION')
 joblib.dump(model,target,compress=1)
 p.immutable(RUN/'action_features.jsonl',inventory,jsonl=True)
 p.immutable(RUN/'frozen_policy.json',policy)
 method={'version':policy['version'],'action_snapshot':meta['snapshot_id'],'policy_sha256':p.filehash(WORK/'policy.json'),'code_sha256':p.filehash(__file__),'index_sha256':p.filehash(target),'feature_sha256':p.filehash(RUN/'action_features.jsonl'),'fit_scope':'Eligible Action titles only. No Amazon fitting, no labels, no external outcomes.','latent_dimensions':int(latent.shape[1]),'word_features':int(wm.shape[1]),'character_features':int(cm.shape[1]),'head_vocabulary':len(f.head_vocabulary)}
 p.immutable(RUN/'method_manifest.json',method)
 summary={'action_inventory_distinct_skus':len(rows),'indexed_distinct_skus':len(reference),'state_counts':dict(collections.Counter(r['state'] for r in inventory)),'task_counts':dict(collections.Counter(t for r in reference for t in r['feature']['task_frames'])),'type_surface_counts':dict(collections.Counter(r['feature']['head'] for r in reference)),'task_recognized_skus':sum(bool(r['feature']['task_frames']) for r in reference),'elapsed_seconds':round(time.perf_counter()-start,3),'rss_mb':round(psutil.Process().memory_info().rss/1024**2,2),'no_per_item_llm':True,'formal_accuracy':None}
 p.immutable(RUN/'action_corpus_summary.json',summary)
 contract=p.canonical({'policy':policy,'method':method,'source':meta['snapshot_id']});run_id='action-assortment-v2-'+method['index_sha256'][:12]
 with connect() as c:
  exact_insert(c,'assortment_v2_runs',['run_id'],{'run_id':run_id,'contract':contract})
  for r in inventory:exact_insert(c,'assortment_v2_action',['run_id','sku'],{'run_id':run_id,'sku':r['sku'],'source_hash':p.digest(r),'payload':p.canonical(r)})
 p.immutable(RUN/'run_identity.json',{'run_id':run_id})
 # Reusable graph edges retain actual supporting SKU/title references.
 graph=[]
 for task in summary['task_counts']:
  support=[r for r in reference if task in r['feature']['task_frames']]
  graph.append({'task':task,'candidate_count':len(support),'type_surface_distribution':dict(collections.Counter(r['feature']['head'] for r in support)),'evidence':[{'sku':r['sku'],'title':r['name_es_original'],'source_row_id':r['source_row_id']} for r in support[:12]],'authority':'Observable title cues plus ordinary-use hypotheses, not demand or buying standards'})
 p.immutable(RUN/'assortment_task_graph.json',graph)
 print(json.dumps(summary,ensure_ascii=False),flush=True)

class Matcher:
 def __init__(self):
  import joblib
  self.model=joblib.load(RUN/'retrieval_index.joblib');self.policy=self.model['policy'];self.f=Features(self.policy);self.f.head_vocabulary=set(self.model['head_vocabulary']);self.method=read(RUN/'method_manifest.json')
 def retrieve(self,titles):
  import numpy as np
  from sklearn.preprocessing import normalize
  m=self.model;word=m['word'].transform([' '.join(self.f.words(t)) for t in titles]);char=m['char'].transform([norm(t) for t in titles]);latent=normalize(m['svd'].transform(word))
  sc=.46*(word@m['word_matrix'].T).toarray()+.20*(char@m['char_matrix'].T).toarray()+.24*(latent@m['latent_matrix'].T)
  heads=[self.f.extract(t,True)['head'] for t in titles]
  refheads=np.array([r['feature']['head'] for r in m['references']])
  for i,h in enumerate(heads):
   if h:sc[i]+=.10*(refheads==h)
  n=min(20,sc.shape[1]);ids=np.argpartition(sc,-n,axis=1)[:,-n:]
  return [[(int(j),float(sc[i,j])) for j in sorted(js,key=lambda j:-sc[i,j])] for i,js in enumerate(ids)]
 def relation(self,ft,ref):
  rf=ref['feature'];common=set(ft['task_frames'])&set(rf['task_frames']);same=bool(ft['head'] and ft['head']==rf['head']);qualified=ft['specific_type_supported']
  source_phrase=rf.get('type_phrase_tokens',[])
  phrase_agreement=len(source_phrase)>=2 and all(w in ft.get('type_phrase_tokens',[]) for w in source_phrase)
  # Parallel domain cues can expose same-word false matches (pet food/human food,
  # car shampoo/hair shampoo). A broad category alone never wins.
  conflict=('vehicle_cleaning' in ft['task_frames'])!=('vehicle_cleaning' in rf['task_frames']) and 'hair_care' in set(ft['task_frames'])|set(rf['task_frames'])
  conflict=conflict or (('pet_feeding' in ft['task_frames'])!=('pet_feeding' in rf['task_frames']) and ('food_consumption' in ft['task_frames'] or 'food_consumption' in rf['task_frames']))
  if conflict:return 'NO_CLEAR_RELATION',[],True
  if same and qualified and phrase_agreement:return 'SAME_SPECIFIC_TYPE',sorted(common),False
  if same and common:return 'RELATED_TYPE',sorted(common),False
  specific=common-{'storage','lighting','home_decoration','wearing','food_consumption','surface_cleaning','repair_fastening','plant_care','pet_care'}
  if specific:return 'SHARED_CONSUMER_NEED',sorted(specific),False
  if common:return 'BROAD_TASK_ONLY',sorted(common),False
  return 'NO_CLEAR_RELATION',[],False
 def judge(self,row,retrieved):
  ft=self.f.extract(row['title_original'],True);candidates=[]
  for j,score in retrieved:
   ref=self.model['references'][j];relation,tasks,conflict=self.relation(ft,ref)
   rank={'SAME_SPECIFIC_TYPE':5,'RELATED_TYPE':4,'SHARED_CONSUMER_NEED':3,'BROAD_TASK_ONLY':1,'NO_CLEAR_RELATION':0}[relation]
   candidates.append({'action_sku':ref['sku'],'action_title':ref['name_es_original'],'action_source_row_id':ref['source_row_id'],'relation':relation,'shared_tasks':tasks,'retrieval_score':round(score,6),'rerank':rank+score,'context_conflict':conflict})
  candidates.sort(key=lambda r:-r['rerank']);ref=candidates[0] if candidates else None
  reliable=bool(ref and ref['relation'] in {'SAME_SPECIFIC_TYPE','RELATED_TYPE','SHARED_CONSUMER_NEED'} and ref['retrieval_score']>=self.policy['decision']['potential_min_retrieval'])
  uncertainty=['仅根据名称进行实验筛选，未独立人工验证','一级类目仅为辅助；来源研究类目不视为官方类目']
  if ft['source_invalid'] or len(ft['words'])<2:
   decision='NEEDS_REVIEW';reason='来源语言异常、空值或短名称不能支持主体与用途判断。'
  elif ft['explicit_outside_scope']:
   decision='LOW_MATCH';reason='名称明确出现不服务本次普通日用货盘的专用系统：'+ft['explicit_outside_scope']
  elif ft['retail_form'] in {'COMPLETE_FURNITURE','DEDICATED_COMPONENT'}:
   decision='POTENTIAL_MATCH';reason='名称提示完整家具或专用配套关系；按Owner日用优先口径保留研究。'
  elif reliable and ref['relation']=='SAME_SPECIFIC_TYPE' and ref['shared_tasks'] and ft['specific_type_supported'] and ref['retrieval_score']>=self.policy['decision']['high_min_retrieval'] and not ft['professional_context']:
   decision='HIGH_MATCH';reason='具体类型对应真实Action参照，检索分数和上下文关系满足当前实验门限。'
  elif reliable:
   decision='POTENTIAL_MATCH';reason='存在相近类型或消费任务参照，尚不足以确定高度货盘适配。'
  elif ft['head'] and ft['task_frames']:
   decision='POTENTIAL_MATCH';reason='名称可支持消费任务，但未找到足够具体的Action参照；不因未匹配而排除。'
  else:
   decision='NEEDS_REVIEW';reason='当前知识库不能可靠区分主体或用途；宽泛相似度不能作为保留/排除依据。'
  if ft['professional_context']:uncertainty.append('专业语境待核；未凭单一专业词直接排除')
  if ft['retail_form']=='NO_EXPLICIT_DEPENDENCY':uncertainty.append('未出现配套提示不等于已经证明可独立使用')
  if not reliable:uncertainty.append('没有可信具体Action参照，检索候选仅供诊断')
  refs=[{k:v for k,v in r.items() if k!='rerank'} for r in candidates[:3] if r['relation'] in {'SAME_SPECIFIC_TYPE','RELATED_TYPE','SHARED_CONSUMER_NEED'} and r['retrieval_score']>=self.policy['decision']['potential_min_retrieval']]
  return {'record_id':row['record_id'],'source_record_id':row['source_record_id'],'source_row':row['source_row'],'input_hash':row['input_hash'],'title_original':row['title_original'],'category_l1_original':row['category_l1_original'],'category_auxiliary':row['category_auxiliary'],'decision':decision,'product_type_surface':ft['head'],'title_purpose_candidates':ft['task_frames'],'task_evidence':ft['task_evidence'],'retail_form':ft['retail_form'],'independent_use':ft['independent_use'],'action_references':refs,'relation_type':refs[0]['relation'] if refs else ('BROAD_TASK_ONLY' if ref and ref['relation']=='BROAD_TASK_ONLY' else 'NO_CLEAR_RELATION'),'reason':reason,'uncertainties':uncertainty,'url_original':row['url_original'],'rules_model_version':self.policy['version'],'method_fingerprint':p.digest(self.method),'experimental':True,'human_confirmed':False}

def screen(records,label):
 from threadpoolctl import threadpool_limits
 start=time.perf_counter();matcher=Matcher();version=p.digest(matcher.method);run_id=read(RUN/'run_identity.json')['run_id'];results=[];cached=0;new=0
 with connect() as c,threadpool_limits(limits=3):
  for start_i in range(0,len(records),64):
   group=records[start_i:start_i+64];missing=[];known={}
   for r in group:
    saved=c.execute('SELECT input_hash,payload FROM assortment_v2_results WHERE run_id=? AND record_id=? AND method_version=?',(run_id,r['record_id'],version)).fetchone()
    if saved:
     assert saved[0]==r['input_hash'];known[r['record_id']]=json.loads(saved[1]);cached+=1
    else:missing.append(r)
   candidates=matcher.retrieve([r['title_original'] for r in missing]) if missing else []
   for r,cand in zip(missing,candidates):
    result=matcher.judge(r,cand);exact_insert(c,'assortment_v2_results',['run_id','record_id','method_version'],{'run_id':run_id,'record_id':r['record_id'],'method_version':version,'input_hash':r['input_hash'],'payload':p.canonical(result)});known[r['record_id']]=result;new+=1
   results.extend(known[r['record_id']] for r in group);c.commit()
   if (start_i//64)%20==0:print(json.dumps({'stage':label,'completed':len(results),'total':len(records),'new':new,'cached':cached}),flush=True)
 p.immutable(RUN/(label+'_results.jsonl'),results,jsonl=True)
 summary={'label':label,'total':len(results),'new_computed':new,'cached':cached,'distribution':dict(collections.Counter(r['decision'] for r in results)),'elapsed_seconds':round(time.perf_counter()-start,3),'formal_accuracy':None}
 # Summary is attempt-specific; resuming never replaces earlier runtime evidence.
 target=RUN/(label+'_runtime_'+p.digest(summary)[:10]+'.json');p.immutable(target,summary)
 print(json.dumps(summary,ensure_ascii=False),flush=True);return results,summary

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('command',choices=['build-action','screen']);parser.add_argument('--input');parser.add_argument('--label',default='technical500');a=parser.parse_args()
 if a.command=='build-action':build_action()
 else:screen(lines(a.input),a.label)
