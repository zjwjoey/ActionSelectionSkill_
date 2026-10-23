"""Conservative exclusion proof: literal appliance heading, not a host hit.

Unknown prefixes cause observation, not an invented brand or exclusion.
The two previous 100-row batches are exposed regression data for V2.5.4.
"""
import re
from collections import defaultdict
import subject_v253 as previous
import subject_v252 as base
from assortment import norm

VERSION='subject-exclusion-proof-v2.5.4'

def subject(title):
 text=norm(title);s=previous.subject(title)
 # Earlier original rules incorrectly treated a brand separator as proof
 # that a later noun was incidental. Recover only literal supported objects,
 # with no purpose/host connector in their prefix.
 if s['status']=='UNCLEAR' and s.get('role_note')=='NOUN_ONLY_IN_ATTRIBUTE_OR_LATER_CLAUSE':
  candidate=base.subject(title)
  span=candidate.get('evidence_span','');before=text[:text.find(span)] if span else text
  if candidate['status']=='CLEAR' and not re.search(r'\b(?:para|for|with|con|compatible|lavables?|apto|apta)\b',before):
   s=candidate
 # An explicit storage noun precedes its contents or appliance host.
 for code,expr in [('BOTTLE_RACK',r'\bbotelleros?\b'),('DEODORIZER',r'\bdesodorizador(?:es)?\b'),
                   ('FOOD_BOX',r'\bporta embutidos\b'),('GIFT_BAG',r'\bbolsas? de celofan\b')]:
  m=re.search(expr,text);old=s.get('evidence_span','')
  if m and (not old or m.start()<text.find(old)):
   s={'status':'CLEAR','class_code':code,'evidence_span':m.group(),'dependent':False,'audience':'UNSPECIFIED','subtype':''}
 return s

def boundary(title,s):
 b=previous.boundary(title,s)
 if s['class_code'] in {'BOTTLE_RACK','DEODORIZER'}:return 'UNVERIFIED_REFERENCE_FAMILY'
 if b=='MAJOR_HOUSEHOLD_APPLIANCE':
  # An appliance noun must begin the literal sold-item heading. Do not
  # silently reinterpret arbitrary preceding nouns as a brand. Brand-leading
  # cases remain research until a stronger subject parser is verified.
  text=norm(title);span=s['evidence_span'];before=text[:text.find(span)].strip(' -:|,')
  if before:return 'APPLIANCE_SUBJECT_PREFIX_UNVERIFIED'
 return b

def compatible(a,b):
 return previous.compatible(a,b) and a['class_code'] not in {'BOTTLE_RACK','DEODORIZER'}

class Engine(previous.Engine):
 def __init__(self,matcher=None):
  super().__init__(matcher);self.subjects=[subject(r['name_es_original']) for r in self.refs];self.families=defaultdict(list)
  for i,s in enumerate(self.subjects):
   if s['status']=='CLEAR' and not s['dependent']:self.families[s['class_code']].append(i)

 def analyze_many(self,rows):
  # Reuse retrieval/projection machinery with scoped callable hooks; no global
  # monkey-patching, reference mutation, retraining or legacy file changes.
  subjects=[subject(r['title_original']) for r in rows]
  got=self.matcher.retrieve([r['title_original'] for r in rows]+[s['evidence_span'] or r['title_original'] for r,s in zip(rows,subjects)])
  n=len(rows);out=[]
  for k,(row,s) in enumerate(zip(rows,subjects)):
   scores={};channels=defaultdict(list)
   for label,weight,hits in [('ORIGINAL_TITLE',.7,got[k]),('SUBJECT_SPAN',.3,got[n+k])]:
    for i,score in hits:scores[i]=scores.get(i,0)+weight*float(score);channels[i].append(label)
   same=[i for i in set(scores)|set(self.families.get(s['class_code'],[])) if compatible(s,self.subjects[i])]
   same.sort(key=lambda i:(-scores.get(i,0),self.refs[i]['sku']))
   refs=[]
   for i in same[:3]:
    r=self.refs[i];refs.append({'action_sku':r['sku'],'action_title':r['name_es_original'],
     'action_source_row_id':r['source_row_id'],'reference_subject':self.subjects[i],
     'relation':'SAME_FUNCTIONAL_FAMILY','retrieval_score':round(scores.get(i,0),8),
     'retrieval_channels':channels[i] or ['SHARED_SUBJECT_FAMILY'],'subtype_equivalence_verified':False})
   b=boundary(row['title_original'],s)
   decision='用不到' if b in {'MAJOR_HOUSEHOLD_APPLIANCE','FIREARM_SPECIFIC_STORAGE'} else '观察' if b or not refs else '保留'
   out.append({'record_id':row['record_id'],'input_hash':row['input_hash'],'title_original':row['title_original'],
    'sample_cohort':row.get('sample_cohort',''),'subject':s,'boundary_code':b,'decision':decision,
    'action_references':refs,'human_confirmed':False,'method_version':VERSION,
    'reason_code':b or ('SAME_FUNCTIONAL_FAMILY' if refs else 'NO_VERIFIED_SAME_FAMILY')})
  return out
