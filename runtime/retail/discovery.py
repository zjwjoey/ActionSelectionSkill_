"""Source-bound reusable hypotheses. No changes to retrieval/score or approval."""
import re,collections,unicodedata
from difflib import SequenceMatcher
from runtime.v3.core import digest
from runtime.retail.attributes import extract,package
from runtime.retail.learning import Learning
VERSION='discovery-v322-1'
def normal(s):return re.sub(r'\s+',' ',''.join(c for c in unicodedata.normalize('NFKD',str(s).lower()) if not unicodedata.combining(c))).strip()
def head(span,brand='',vocabulary=None):
 words=re.findall(r'[^\W\d_]+',normal(span),re.UNICODE)
 brands=set(normal(brand).split());skip=brands|{'set','pack','juego','kit','de','para','con','sin','el','la','los','las'}
 if vocabulary is not None:
  known=[w for w in words if w in vocabulary and w not in skip]
  if known:return known[0]
  # An unknown multiword phrase needs a noun decision, not its first brand,
  # adjective or series word promoted into a synonym rule.
  return words[0] if len(words)==1 and words[0] not in skip else ''
 return next((w for w in words if len(w)>=4 and w not in skip),'')
def discover(results):
 groups={}
 vocabulary=None
 if any((r.get('analysis') or {}).get('pairs') for r in results):
  from pathlib import Path
  from runtime.v3.catalog import Catalog
  catalog=Catalog(Path(__file__).resolve().parents[2]);catalog._load_retriever();vocabulary=catalog._head_vocabulary
 def add(kind,scope,issue,terms,evidence,reason,risk):
  key=digest([VERSION,kind,scope,issue,terms]);g=groups.setdefault(key,dict(id=key,kind=kind,scope=scope,issue=issue,terms=terms,reason=reason,risk=risk,state='CANDIDATE',version=VERSION,evidence=[]))
  if evidence not in g['evidence']:g['evidence'].append(evidence)
 for r in results:
  a=r.get('analysis');src=r['source']
  if not a or r.get('status')!='COMPLETE':continue
  attrs=extract(src['title_original'],src['specifications']);family=attrs['family'];term=head(a.get('subject_span',''),src.get('brand',''),vocabulary)
  scope=family or term or 'UNRESOLVED:'+digest(a.get('sold_subject',''))[:16]
  evidence=dict(record_id=r['record_id'],platform=src['source_platform'],sku=src['source_product_id'],source_sha=src['source_sha256'],file=src['source_file'],span=a.get('subject_span',''),title=src['title_original'],result_hash=digest(r))
  for field,text in [('title',src['title_original']),('spec',src['specifications']),('variant',src.get('variant',''))]:
   for m in re.finditer(r'\b(?:pack\s+de\s+(\d+)|(\d+)\s*(uds?\.?|paquetes?|pzas?\.?))\b',text,re.I):
    count=int(m.group(1) or m.group(2));existing=attrs['attributes'].get('count',[])
    if str(count) not in existing:
     pattern='PACK_DE_N' if m.group(1) else 'N_'+normal(m.group(3)).rstrip('.')
     add('spec_rule',scope,'UNPARSED_EXPLICIT_COUNT',pattern,{**evidence,'field':field,'literal':m.group(0),'value':count},'原文含明确件数表达，现解析器未识别；候选规则需校验销售数量而非包装尺寸','表达可能指配件数量、内包装或变体；不得直接改正式数量')
  by={m['reference_id']:m for m in r.get('matches',[])}
  for p in a.get('pairs',[]):
   m=by.get(p['sku']);refterm=head(p.get('action_span',''),vocabulary=vocabulary)
   if not m:continue
   if p['relation']=='SAME_TYPE' and p.get('scope')=='WHOLE' and term and refterm and term!=refterm:
    ref_family=extract(m['title'])['family']
    plausible=bool(family and family==ref_family) or SequenceMatcher(None,term,refterm).ratio()>=.82
    add('alias' if plausible else 'type',family or term,'POSSIBLE_TERM_EQUIVALENCE' if plausible else 'SUBJECT_TERM_GRANULARITY_REVIEW',[term,refterm],{**evidence,'reference_id':p['sku'],'reference_span':p['action_span']},'字面近形/同词族的术语假设' if plausible else 'AI同类型但两侧主体术语不同，先检查材料、用途或组件是否被错当主体，不直接提出同义词规则','同类型不一定同义；品牌、用途或产品层级可能不同，不能按向量相似自动批准')
   check=r.get('attribute_checks',{}).get(p['sku'],{})
   if check.get('block_same_type') and p['relation']=='SAME_TYPE':
    add('type',family or term,'SUBJECT_HOST_CONFUSION',[family,check['reference']['family']],{**evidence,'reference_id':p['sku']},'AI同类型与明确主体词族冲突，可形成通用主体/宿主反例','词族规则也可能错误；不得自动扩成全类排除')
  shape=package(src['title_original'])
  if shape in ['HOMOGENEOUS_MULTIPACK','MAIN_WITH_ACCESSORY','COMPOSITION_UNKNOWN'] and any(p.get('scope') in ['COMPONENT','UNKNOWN'] for p in a.get('pairs',[])):
   add('type',family or term or 'UNRESOLVED_SUBJECT','PACKAGE_SCOPE_REVIEW',shape,evidence,'多件装/组合形态与模型覆盖关系需对照，可寻找重复粒度问题','出现pack/set并不能确认组成；未知不得改成WHOLE')
 # A one-off rare literal noun is an observation, not automatically a new type.
 return sorted(groups.values(),key=lambda g:(-len({e['record_id'] for e in g['evidence']}),g['id']))
def persist(groups,path):
 s=Learning(path)
 try:
  for g in groups:
   first=g['evidence'][0];cid=g['id']
   if not any(e.get('candidate_id')==cid for e in s.events()):
    body={k:v for k,v in g.items() if k not in ['evidence','state','id']}
    if g['kind']=='alias':body.update(term=g['terms'][0],expansion=g['terms'][1])
    item=dict(candidate_id=cid,kind=g['kind'],body=body,source=dict(record_id=first['record_id'],source_sha=first['source_sha']),synthetic=False)
    s.append({**item,'state':'OBSERVED'});s.append({**item,'state':'CANDIDATE'})
   for evidence in g['evidence']:
    s.append(dict(record_type='DISCOVERY_EVIDENCE',knowledge_id=cid,state='OBSERVED',evidence=evidence,version=VERSION))
 finally:s.close()

def shadow_parse(row,groups):
 """Test pending count expressions on other records; no official fact writes."""
 attrs=extract(row['title_original'],row.get('specifications',''));out=[]
 for g in groups:
  if g['kind']!='spec_rule' or g['issue']!='UNPARSED_EXPLICIT_COUNT' or g['scope']!=attrs['family']:continue
  for field in ['title_original','specifications','variant']:
   for m in re.finditer(r'\b(?:pack\s+de\s+(\d+)|(\d+)\s*(uds?\.?|paquetes?|pzas?\.?))\b',row.get(field,'') or '',re.I):
    pattern='PACK_DE_N' if m.group(1) else 'N_'+normal(m.group(3)).rstrip('.')
    if pattern==g['terms']:
     out.append(dict(candidate_id=g['id'],field=field,literal=m.group(0),possible_count=int(m.group(1) or m.group(2)),original_count=attrs['attributes'].get('count'),authority='SHADOW_HYPOTHESIS_SALE_SCOPE_UNVERIFIED'))
 return out
