"""Append-only knowledge candidates, explicit human transitions, immutable releases."""
import json,sqlite3,re
from pathlib import Path
from datetime import datetime,timezone
from runtime.v3.core import digest,canonical
from runtime.v3.workflow import filehash
STATES=['OBSERVED','CANDIDATE','SOURCE_VERIFIED','HUMAN_VERIFIED','APPROVED_FOR_LEARNING','REJECTED']
KINDS={'alias','type','positive_pair','negative_pair','spec_rule'}
def now():return datetime.now(timezone.utc).isoformat()
class Learning:
 def __init__(self,path):
  self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(path)
  self.db.execute('CREATE TABLE IF NOT EXISTS knowledge_events(seq INTEGER PRIMARY KEY, event_hash TEXT UNIQUE NOT NULL,payload TEXT NOT NULL)');self.db.commit()
 def append(self,p):
  key=digest(p);old=self.db.execute('SELECT payload FROM knowledge_events WHERE event_hash=?',(key,)).fetchone()
  if old and old[0]!=canonical(p):raise ValueError('KNOWLEDGE_EVENT_HASH_CONFLICT')
  self.db.execute('INSERT OR IGNORE INTO knowledge_events(event_hash,payload) VALUES(?,?)',(key,canonical(p)));self.db.commit();return key
 def events(self):
  rows=self.db.execute('SELECT event_hash,payload FROM knowledge_events ORDER BY seq').fetchall();result=[]
  for h,p in rows:
   p=json.loads(p)
   if digest(p)!=h:raise ValueError('KNOWLEDGE_AUDIT_HASH_MISMATCH')
   result.append(p)
  return result
 def current(self,cid):
  rows=[r for r in self.events() if r.get('candidate_id')==cid]
  if not rows:raise ValueError('UNKNOWN_CANDIDATE')
  return rows[-1]
 def propose(self,kind,body,source,synthetic=False):
  if kind not in KINDS or not source.get('source_sha') or not source.get('record_id'):raise ValueError('SOURCE_BOUND_KNOWLEDGE_REQUIRED')
  if kind=='alias' and (not body.get('term') or not body.get('expansion')):raise ValueError('ALIAS_TERMS_REQUIRED')
  cid=digest(dict(kind=kind,body=body,source=source,synthetic=synthetic))
  if any(e.get('candidate_id')==cid for e in self.events()):return cid
  base=dict(candidate_id=cid,kind=kind,body=body,source=source,synthetic=synthetic)
  self.append({**base,'state':'OBSERVED'});self.append({**base,'state':'CANDIDATE'});return cid
 def transition(self,cid,state,reviewer,evidence):
  r=self.current(cid)
  if state not in STATES or not reviewer.startswith('human:') or not reviewer[6:].strip() or not evidence.get('reason'):raise ValueError('REAL_HUMAN_AND_EVIDENCE_REQUIRED')
  allowed={'CANDIDATE':['SOURCE_VERIFIED','HUMAN_VERIFIED','REJECTED'],'SOURCE_VERIFIED':['HUMAN_VERIFIED','REJECTED'],'HUMAN_VERIFIED':['APPROVED_FOR_LEARNING','REJECTED']}
  if state not in allowed.get(r['state'],[]):raise ValueError('INVALID_KNOWLEDGE_TRANSITION')
  if state=='SOURCE_VERIFIED':
   p=Path(evidence.get('file',''))
   if not p.is_file() or filehash(p)!=evidence.get('sha256'):raise ValueError('SOURCE_PROOF_HASH_INVALID')
  if state=='APPROVED_FOR_LEARNING' and not evidence.get('authorization'):raise ValueError('EXPLICIT_LEARNING_AUTHORIZATION_REQUIRED')
  return self.append({**r,'state':state,'reviewer':reviewer,'review_evidence':evidence,'reviewed_at':now()})
 def collect(self,result,unknown,priority):
  source=result['source'];rid=result['record_id'];key=digest([rid,result['method']])
  body=dict(result_hash=digest(result),method=result['method'],initial_match=result['match_score_10'],hypothesis=result['analysis'],unknown=unknown,priority=priority,candidates=[m['reference_id'] for m in result['matches']],original=source)
  obs=dict(candidate_id=key,record_type='OBSERVATION',kind='observation',body=body,source=dict(record_id=rid,source_sha=source['source_sha256']),state='OBSERVED',synthetic=False,record_id=rid,group_key=key)
  self.append(obs)
  checks=list(result.get('attribute_checks',{}).values());families={c['input']['family'] for c in checks if c['input']['family']}
  claims={p['sku']:p for p in result['analysis']['pairs']}
  reusable=sorted({x for sku,c in result.get('attribute_checks',{}).items() for x in c['conflicts'] if x!='SUBJECT_FAMILY_DIFFERENT' and claims[sku]['spec_status']=='SAME'})
  if reusable and len(families)==1:
   hypothesis=dict(family=next(iter(families)),issue='SPEC_COMPARISON_REVIEW',attributes=reusable)
   group=digest(hypothesis);cid=digest(['spec_rule',hypothesis])
   if not any(e.get('candidate_id')==cid for e in self.events()):
    base=dict(candidate_id=cid,kind='spec_rule',body=hypothesis,source=obs['source'],synthetic=False)
    self.append({**base,'state':'OBSERVED'});self.append({**base,'state':'CANDIDATE'})
   self.append(dict(candidate_id=digest([cid,key]),record_type='EVIDENCE',kind='evidence',knowledge_id=cid,state='OBSERVED',source=obs['source'],body=body,synthetic=False))
   return {**obs,'candidate_id':cid,'record_type':'KNOWLEDGE_CANDIDATE','state':'CANDIDATE','group_key':group}
  return obs
 def publish(self,ids,receipt,path):
  items=[self.current(cid) for cid in ids]
  if not items or any(i['state']!='APPROVED_FOR_LEARNING' for i in items):raise ValueError('APPROVED_KNOWLEDGE_ONLY')
  validate_receipt(receipt,ids)
  if any(i['synthetic'] for i in items):raise ValueError('SYNTHETIC_DATA_NOT_PUBLISHABLE')
  artifact=dict(items=items,receipt=receipt,created_at=now(),status='APPROVED_RELEASE');artifact['version']=digest(artifact)
  path=Path(path)
  if path.exists():raise ValueError('IMMUTABLE_RELEASE_PATH_EXISTS')
  path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(artifact,ensure_ascii=False,indent=2),encoding='utf8');return artifact['version']
 def close(self):self.db.close()
def validate_receipt(r,ids):
 if not r.get('reviewer','').startswith('human:') or not r.get('regression_pass') or not r.get('independent_pass') or not r.get('evidence_file') or not r.get('evidence_sha'):raise ValueError('INDEPENDENT_ACCEPTANCE_RECEIPT_REQUIRED')
 if sorted(ids)!=sorted(r.get('candidate_ids',[])):raise ValueError('RECEIPT_CANDIDATE_BINDING_MISMATCH')
 train=set(r.get('training_ids',[]));test=set(r.get('validation_ids',[]))
 if not train or not test or train&test:raise ValueError('INDEPENDENT_VALIDATION_IDS_REQUIRED')
 if filehash(Path(r['evidence_file']))!=r['evidence_sha']:raise ValueError('RECEIPT_EVIDENCE_CHANGED')
def load_release(path):
 r=json.loads(Path(path).read_text(encoding='utf8'));version=r.pop('version')
 if digest(r)!=version or r.get('status')!='APPROVED_RELEASE':raise ValueError('RELEASE_HASH_OR_STATUS_INVALID')
 validate_receipt(r['receipt'],[i['candidate_id'] for i in r['items']])
 if any(i['synthetic'] or i['state']!='APPROVED_FOR_LEARNING' for i in r['items']):raise ValueError('RELEASE_ITEMS_NOT_APPROVED')
 return version,r['items']
def aliases_for(items,title):
 return [i['body']['expansion'] for i in items if i['kind'] in ['alias','type'] and i['body'].get('term') and i['body'].get('expansion') and re.search(r'(?<!\w)'+re.escape(i['body']['term'])+r'(?!\w)',title,re.I)]
def classify_unknown(result,attrs,known):
 a=result['analysis'];flags=[]
 # The small literal-attribute vocabulary is not the product knowledge universe.
 # A source-bound same-type candidate can establish a KNOWN-TYPE HYPOTHESIS.
 primary=result.get('primary') or {}
 known=known or (primary.get('relation')=='SAME_TYPE' and primary.get('scope')=='WHOLE')
 if a['subject_status']!='clear' or a['form']=='unknown':flags.append('D_INSUFFICIENT_SOURCE')
 elif not attrs['family'] and not known:flags.append('C_TYPE_HYPOTHESIS')
 else:flags.append('B_BRAND_MODEL_NOVELTY_UNCONFIRMED' if result['source'].get('brand') or attrs['attributes'].get('model') else 'A_NEW_SKU_KNOWN_TYPE')
 if result['primary'] is None:flags.append('E_NO_CONFIRMED_REFERENCE')
 if attrs['source_conflicts']:flags.append('F_SOURCE_CONFLICT')
 return flags

def collect_feedback(run,store):
 """Turn real feedback into proposals only; approval remains explicit."""
 from runtime.v31.state import State
 state=State(Path(run)/'state.sqlite3');learning=Learning(store);ids=[]
 try:
  for _,e in state.all('match10_feedback'):
   kind='positive_pair' if e['kind']=='接受匹配结果' else 'negative_pair' if e['kind']=='商品关系判断错误' and e.get('new_relation')=='UNRELATED' else 'type'
   body=dict(reference_id=e.get('new_reference') or e.get('original_reference'),feedback=e,reason=e['reason'])
   ids.append(learning.propose(kind,body,dict(record_id=e['record_id'],source_sha=e['source_sha'],feedback_hash=digest(e))))
  return ids
 finally:state.close();learning.close()
