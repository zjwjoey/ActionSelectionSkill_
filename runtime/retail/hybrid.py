"""Optional CPU E5 index, bound to literal catalog IDs; RRF is never a score."""
import json,time,os
from pathlib import Path
from runtime.v3.core import digest
from runtime.v3.workflow import filehash

MODEL='intfloat/multilingual-e5-small'
def rrf(routes,k=60):
 if k<=0:raise ValueError('RRF_K_MUST_BE_POSITIVE')
 scores={};ranks={}
 for name,ids in routes.items():
  if len(ids)!=len(set(ids)):raise ValueError('DUPLICATE_ROUTE_ID')
  for rank,sku in enumerate(ids,1):
   scores[sku]=scores.get(sku,0)+1/(k+rank);ranks.setdefault(sku,{})[name]=rank
 return [dict(sku=s,rrf_score=scores[s],ranks=ranks[s]) for s in sorted(scores,key=lambda s:(-scores[s],s))]

class SemanticIndex:
 def __init__(self,directory):
  import numpy as np
  self.path=Path(directory);self.meta=json.loads((self.path/'index.json').read_text(encoding='utf8'))
  if filehash(self.path/'vectors.npy')!=self.meta['vectors_sha']:raise ValueError('VECTOR_HASH_MISMATCH')
  for rel,h in self.meta.get('model_files',{}).items():
   if filehash(Path(self.meta['model_path'])/rel)!=h:raise ValueError('MODEL_WEIGHT_OR_CONFIG_CHANGED')
  self.vectors=np.load(self.path/'vectors.npy',allow_pickle=False,mmap_mode='r');self.ids=self.meta['ids'];self.model=None
  if self.vectors.shape!=(len(self.ids),384) or len(set(self.ids))!=len(self.ids) or not np.isfinite(self.vectors).all():raise ValueError('VECTOR_SHAPE_OR_IDS_INVALID')
 def encoder(self):
  if self.model is None:
   from sentence_transformers import SentenceTransformer
   import torch
   torch.set_num_threads(4)
   self.model=SentenceTransformer(self.meta['model_path'],device='cpu',local_files_only=True,trust_remote_code=False)
   self.model.max_seq_length=512
  return self.model
 def search(self,text,limit=50):
  import numpy as np
  import sqlite3
  key=digest([self.meta['revision'],self.meta['vectors_sha'],text]);db=sqlite3.connect(self.path/'query_cache.sqlite3')
  try:
   db.execute('CREATE TABLE IF NOT EXISTS queries(key TEXT PRIMARY KEY, vector BLOB NOT NULL)');row=db.execute('SELECT vector FROM queries WHERE key=?',(key,)).fetchone()
   if row:q=np.frombuffer(row[0],dtype='float32')
   else:
    q=np.asarray(self.encoder().encode(['query: '+text],normalize_embeddings=True,show_progress_bar=False)[0],dtype='float32');db.execute('INSERT INTO queries VALUES(?,?)',(key,q.tobytes()));db.commit()
  finally:db.close()
  scores=self.vectors@q
  return [(self.ids[int(i)],float(scores[i])) for i in np.argsort(-scores,kind='stable')[:limit]]

def build(catalog,directory,model_path,revision):
 import numpy as np,psutil
 import torch
 torch.set_num_threads(4)
 from sentence_transformers import SentenceTransformer
 directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
 rows=[(s,r['name_es_original']) for s,r in catalog.by_sku.items()]
 contract=dict(model=MODEL,revision=revision,reference=digest(rows),ids=[s for s,_ in rows],prefix='passage: ',query_prefix='query: ',normalize=True)
 if (directory/'index.json').exists():
  existing=SemanticIndex(directory)
  if any(existing.meta[k]!=v for k,v in contract.items()):raise ValueError('INDEX_CONTRACT_CHANGED_USE_NEW_DIRECTORY')
  return existing.meta
 start=time.monotonic();model=SentenceTransformer(str(model_path),device='cpu',local_files_only=True,trust_remote_code=False);model.max_seq_length=512
 model_files={str(p.relative_to(model_path)):filehash(p) for p in Path(model_path).rglob('*') if p.is_file()}
 vectors=model.encode(['passage: '+t for _,t in rows],batch_size=64,normalize_embeddings=True,show_progress_bar=True)
 temp=directory/'vectors.build.npy';np.save(temp,vectors,allow_pickle=False);os.replace(temp,directory/'vectors.npy')
 meta={**contract,'model_path':str(Path(model_path).resolve()),'model_files':model_files,'license':'MIT','vectors_sha':filehash(directory/'vectors.npy'),'built_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'build_seconds':round(time.monotonic()-start,3),'rss_bytes':psutil.Process().memory_info().rss,'device':'cpu','dimensions':384,'library_versions':{n:__import__('importlib.metadata',fromlist=['version']).version(n) for n in ['torch','sentence-transformers','transformers','numpy']}}
 (directory/'index.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8');return meta

class HybridRetriever:
 def __init__(self,refs,index=None,k=60):
  self.refs=refs;self.index=None;self.k=k;self.fallback=None
  if index:
   try:
    self.index=SemanticIndex(index)
    if not refs.catalog or self.index.meta['reference']!=digest([(s,r['name_es_original']) for s,r in refs.catalog.by_sku.items()]):raise ValueError('SEMANTIC_CATALOG_BINDING_MISMATCH')
   except (OSError,ValueError,ImportError) as e:self.fallback=str(e);self.index=None
 def search(self,row,limit=20,aliases=()):
  from runtime.retail.match10 import retrieve
  original=retrieve(self.refs,row)
  textall=self.refs.catalog.retrieve(row['title_original'],limit=len(self.refs.catalog.by_sku)) if self.refs.catalog else []
  text=textall[:50]
  lexical={r['sku']:dict(sku=r['sku'],title=r['name_es_original'],retrieval_score=r['retrieval_score']) for r in textall}
  lexical.update({r['sku']:r for r in original})
  routes={'v31':[r['sku'] for r in original],'text50':[r['sku'] for r in text]};semantic=[]
  if self.index:
   try:semantic=self.index.search(row['title_original']+' '+row.get('specifications',''),50);routes['semantic']=[s for s,_ in semantic]
   except (OSError,ValueError,ImportError,RuntimeError) as e:self.fallback=type(e).__name__+': '+str(e)
  for i,alias in enumerate(aliases):
   more=self.refs.retrieve(alias);routes['approved_alias_'+str(i)]=[c['sku'] for c in more];lexical.update({c['sku']:c for c in more})
  fused=rrf(routes,self.k) if semantic or aliases else [dict(sku=r['sku'],rrf_score=None,ranks={'v31':i}) for i,r in enumerate(original,1)]
  output=[]
  for f in fused:
   s=f['sku'];c=lexical.get(s)
   if c is None:
    ref=self.refs.catalog.by_sku[s];c=dict(sku=s,title=ref['name_es_original'],retrieval_score=0.0)
   # Preserve lexical name score; cosine/RRF must not become the 0–10 index.
   q=self.refs.quotes.get(s) or {}
   output.append({**c,'spec':q.get('specifications','') if q.get('binding_valid',True) else '', 'category1':c.get('category1',''),'category2':c.get('category2',''),'recall':f})
  return output[:limit],dict(original_v31=routes['v31'],text50=routes['text50'],semantic50=routes.get('semantic',[]),rrf50=[f['sku'] for f in fused[:50]],fallback=self.fallback,rrf_k=self.k)
