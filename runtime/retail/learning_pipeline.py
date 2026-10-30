"""Hooks into the V3.1 shared engine; no second model or pricing pipeline."""
import copy,json,time
from pathlib import Path
from runtime.retail import match10
from runtime.retail.hybrid import HybridRetriever
from runtime.retail.attributes import extract,verify,package
from runtime.retail.learning import Learning,load_release,aliases_for,classify_unknown
from runtime.v3.core import digest
from runtime.v3.workflow import filehash,write_jsonl
VERSION='v3.2.1-experimental-v1'
class Extension:
 def __init__(self,index=None,learning='off',store=None,knowledge=None,verification=True,recall_size=20,rrf_k=60):
  if learning not in ['off','collect','shadow','approved'] or not 5<=recall_size<=20:raise ValueError('LEARNING_MODE_OR_FINE_CANDIDATE_LIMIT_INVALID')
  self.index=index;self.mode=learning;self.store_path=store;self.knowledge=knowledge;self.verification=verification;self.limit=recall_size;self.k=rrf_k;self.items=[];self.knowledge_version=None;self.records=[];self.traces={};self.learning_rows=[];self.requests={};self.analysis_cache={};self.rebound={};self.cache_state=None
  if learning=='approved':
   if not knowledge:raise ValueError('APPROVED_KNOWLEDGE_VERSION_REQUIRED')
   self.knowledge_version,self.items=load_release(knowledge)
  elif learning=='shadow' and store:
   st=Learning(store);allitems={r['candidate_id']:r for r in st.events() if r.get('candidate_id') and r.get('kind') in ['alias','type','positive_pair','negative_pair','spec_rule']};st.close();self.items=[r for r in allitems.values() if r['state']!='REJECTED'];self.knowledge_version=digest(self.items)
 def bind(self,refs):
  self.refs=refs;self.retriever=HybridRetriever(refs,self.index,self.k)
  if self.store_path:
   from runtime.v31.state import State
   self.cache_state=State(Path(self.store_path).with_suffix('.analysis.sqlite3'))
   self.analysis_cache={r['key']:r for _,r in self.cache_state.all('content_analysis')}
 def signature(self,base):
  meta=self.retriever.index.meta if self.retriever.index else None
  from importlib.metadata import version,PackageNotFoundError
  libraries={}
  for name in ['sentence-transformers','torch','transformers','numpy']:
   try:libraries[name]=version(name)
   except PackageNotFoundError:libraries[name]=None
  return digest(dict(base=base,version=VERSION,index=meta,libraries=libraries,verification=self.verification,mode=self.mode,knowledge=self.knowledge_version,limit=self.limit,k=self.k))
 def retrieve(self,refs,row):
  aliases=aliases_for(self.items,row['title_original']) if self.mode=='approved' else []
  candidates,trace=self.retriever.search(row,self.limit,aliases)
  if self.mode=='approved':
   for i in self.items:
    if i['kind']=='positive_pair' and i['source']['record_id']==row['quote_id']:
     sku=i['body'].get('reference_id');ref=refs.catalog.by_sku.get(sku) if refs.catalog else None
     if ref and sku not in {c['sku'] for c in candidates}:
      q=refs.quotes.get(sku) or {};candidates=[dict(sku=sku,title=ref['name_es_original'],retrieval_score=0,spec=q.get('specifications',''),category1='',category2='',knowledge_evidence=i['candidate_id'])]+candidates[:self.limit-1]
  if self.mode=='shadow':
   _,trace['shadow']=self.retriever.search(row,self.limit,aliases_for(self.items,row['title_original']))
  self.traces[row['quote_id']]=trace;return candidates
 def prepare(self,row,req):
  if self.verification:req['literal_attributes']=extract(row['title_original'],row['specifications'])
  if self.knowledge_version:req['knowledge_version']=self.knowledge_version
  if self.mode=='approved':req['approved_knowledge']=[i for i in self.items if i['kind'] in ['type','positive_pair','negative_pair','spec_rule'] and i['source']['record_id']==row['quote_id']]
  if self.mode=='approved':
   from runtime.retail.discovery import shadow_parse
   rules=[dict(id=i['candidate_id'],kind=i['kind'],**{k:i['body'].get(k) for k in ['scope','issue','terms']}) for i in self.items if i['kind']=='spec_rule']
   hints=shadow_parse(row,rules)
   for hint in hints:hint['authority']='APPROVED_RULE_LITERAL_SOURCE_EVIDENCE'
   req['approved_count_explanations']=hints
  self.requests[row['quote_id']]=req
 def content_key(self,row,req):return digest(dict(platform=row['source_platform'],product_id=row['source_product_id'],brand=row.get('brand'),request={k:v for k,v in req.items() if k not in ['record_id','source_hash']}))
 def reuse(self,row,req):
  old=self.analysis_cache.get(self.content_key(row,req))
  if not old:return None
  a=copy.deepcopy(old['analysis']);a.update(record_id=req['record_id'],source_hash=req['source_hash']);match10.validate(req,a)
  self.rebound[row['quote_id']]=dict(original_analysis_hash=digest(old['analysis']),original_source=old['source'],reason='Exact input content, candidates and method unchanged; only current observation binding renewed')
  return a
 def project(self,row,a,candidates,refs,method,origin):
  adjusted=copy.deepcopy(a);checks={};by={c['sku']:c for c in candidates};inputattrs=extract(row['title_original'],row['specifications'])
  if self.mode=='approved':
   hints=self.requests.get(row['quote_id'],{}).get('approved_count_explanations',[])
   values=sorted({str(h['possible_count']) for h in hints})
   if len(values)==1 and not inputattrs['attributes'].get('count'):
    inputattrs['attributes']['count']=values;inputattrs['evidence']['count']=[h['literal'] for h in hints]
    inputattrs['approved_knowledge_evidence']=hints
  for p in adjusted['pairs']:
   c=by[p['sku']];check=verify(inputattrs,extract(c['title'],c.get('spec','')));checks[p['sku']]=check
   if not inputattrs['family'] and a['subject_status']=='clear':
    check['type_status']='RULE_NOT_DEFINED';check['evidence_status']='该类型未定义属性规则'
    for comparison in check.get('comparisons',[]):
     if comparison['status']=='TYPE_UNIDENTIFIED':comparison['status']='RULE_NOT_DEFINED'
   if self.verification:
    if p['scope']=='COMPONENT' and p['relation']=='SAME_TYPE' and inputattrs['family'] and inputattrs['family']==check['reference']['family'] and package(row['title_original'])=='HOMOGENEOUS_MULTIPACK' and package(c['title']) not in ['MAIN_WITH_ACCESSORY','COMPOSITION_UNKNOWN','REPLACEMENT_ACCESSORY']:p['scope']='WHOLE'
    if check['block_same_type'] and p['relation']=='SAME_TYPE':p['relation']='INSUFFICIENT';p['scope']='UNKNOWN'
    if check['conflicts'] and not check['block_same_type']:p['spec_status']='DIFFERENT'
    if check['unknown'] and p['spec_status']=='SAME':p['spec_status']='UNKNOWN'
    if 'WHOLE_ACCESSORY_SCOPE_UNCONFIRMED' in check['unknown']:p['scope']='UNKNOWN'
   for i in self.items if self.mode=='approved' else []:
    if i['kind']=='negative_pair' and i['body'].get('reference_id')==p['sku'] and i['source']['record_id']==row['quote_id']:p['relation']='UNRELATED';p['scope']='UNKNOWN'
  result=match10.project(row,adjusted,candidates,refs,method,origin)

  for m in result['matches']:m['retrieval_evidence']={k:by[m['reference_id']].get(k) for k in ['recall','retrieval_score','text_score_status','semantic_score']}
  result['analysis']=a;result['effective_analysis']=adjusted;result['attribute_checks']=checks;result['retrieval_trace']=self.traces[row['quote_id']];result['knowledge_version']=self.knowledge_version;result['engine_version']=VERSION
  result['evidence_status']=(checks[result['primary']['reference_id']]['evidence_status'] if result['primary'] else '关键属性未知')
  if row['quote_id'] in self.rebound:result['origin']='VERIFIED_CONTENT_CACHE_REBIND_NOT_NEW_MODEL';result['analysis_reuse']=self.rebound[row['quote_id']]
  if self.cache_state:
   req=self.requests[row['quote_id']];entry=dict(key=self.content_key(row,req),analysis=a,source=row);self.cache_state.put('content_analysis',entry);self.analysis_cache[entry['key']]=entry
  if result['evidence_status']!='关键属性已核实':result['issues'].append(result['evidence_status'])
  return result
 def finish(self,out,results,summary):
  observed=[]
  st=Learning(self.store_path or Path(out)/'learning.sqlite3') if self.mode in ['collect','shadow'] else None
  try:
   for r in results:
    if r['status']!='COMPLETE':continue
    attrs=extract(r['source']['title_original'],r['source']['specifications']);flags=classify_unknown(r,attrs,attrs['family'] is not None)
    priority=[];tr=r.get('retrieval_trace',{})
    if tr.get('semantic50') and set(tr['original_v31'][:5]).isdisjoint(tr['semantic50'][:5]):priority.append('TEXT_SEMANTIC_DISAGREEMENT')
    if r['match_score_10'] is not None and r['match_score_10']>=7 and r.get('evidence_status')!='关键属性已核实':priority.append('HIGH_SCORE_MISSING_ATTRIBUTES')
    if r['analysis']['form'] in ['bundle','accessory']:priority.append('BUNDLE_OR_ACCESSORY_SCOPE')
    if r['primary'] is None:priority.append('NO_CONFIRMED_REFERENCE')
    scores=[m['scoring']['original_index_100'] for m in r['matches'][:2]]
    if len(scores)==2 and all(s is not None for s in scores) and abs(scores[0]-scores[1])<3:priority.append('CLOSE_TOP_TWO')
    if st:observed.append(st.collect(r,flags,priority))
   self.learning_rows=observed;write_jsonl(Path(out)/'learning_candidates.jsonl',observed)
   ordered=sorted((r for r in observed if r['record_type']=='KNOWLEDGE_CANDIDATE' or 'TEXT_SEMANTIC_DISAGREEMENT' in r['body']['priority']),key=lambda r:(-len(r['body']['priority']),r['record_id']))
   queue=[];groups=set()
   for r in ordered:
    if r['group_key'] not in groups:queue.append(r);groups.add(r['group_key'])
    if len(queue)==50:break
   for r in ordered:
    if len(queue)==50:break
    if r not in queue:queue.append(r)
   write_jsonl(Path(out)/'active_review.jsonl',queue)
   summary['learning']=dict(mode=self.mode,version=self.knowledge_version,observations=len(observed),candidates=len({r['candidate_id'] for r in observed if r['record_type']=='KNOWLEDGE_CANDIDATE'}),review_records=len(queue),hypothesis_groups=len({r['group_key'] for r in observed}),approved_items=len(self.items) if self.mode=='approved' else 0,content_cache_rebound=len(self.rebound),formal_publication=False)
   summary['retrieval']=dict(index_version=self.retriever.index.meta if self.retriever.index else None,fallback=self.retriever.fallback,rrf_k=self.k,fine_candidates=self.limit)
  finally:
   if st:st.close()
 def close(self):
  if self.cache_state:self.cache_state.close()
