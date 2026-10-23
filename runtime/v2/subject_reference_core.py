"""Shared retrieval pipeline: validate type relations before ranking/truncation."""
from collections import defaultdict
from assortment import Matcher

class ReferenceEngine:
 def __init__(self,version,parse,boundary,compatible,matcher=None):
  self.version=version;self.parse=parse;self.boundary=boundary;self.compatible=compatible
  self.matcher=matcher or Matcher();self.refs=self.matcher.model['references']
  self.subjects=[parse(r['name_es_original']) for r in self.refs];self.families=defaultdict(list)
  for i,s in enumerate(self.subjects):
   if s['status']=='CLEAR':self.families[s['class_code']].append(i)
 def analyze_many(self,rows):
  subjects=[self.parse(r['title_original']) for r in rows];n=len(rows)
  hits=self.matcher.retrieve([r['title_original'] for r in rows]+[s['evidence_span'] or r['title_original'] for r,s in zip(rows,subjects)])
  out=[]
  for k,(row,s) in enumerate(zip(rows,subjects)):
   scores={};channels=defaultdict(list)
   for label,weight,items in [('ORIGINAL_TITLE',.7,hits[k]),('SOURCE_SUBJECT_SPAN',.3,hits[n+k])]:
    for j,score in items:scores[j]=scores.get(j,0)+weight*float(score);channels[j].append(label)
   candidates=set(scores)|set(self.families.get(s['class_code'],[]))
   same=[j for j in candidates if self.compatible(s,self.subjects[j])]
   same.sort(key=lambda j:(-scores.get(j,0),self.refs[j]['sku']))
   refs=[]
   for j in same[:3]:
    ref=self.refs[j];refs.append({'action_sku':ref['sku'],'action_title':ref['name_es_original'],'action_source_row_id':ref['source_row_id'],
     'reference_subject':self.subjects[j],'relation':'SAME_LITERAL_FUNCTIONAL_TYPE','retrieval_score':round(scores.get(j,0),8),
     'retrieval_channels':channels[j] or ['SUBJECT_FAMILY'],'subtype_equivalence_verified':False})
   b=self.boundary(row['title_original'],s)
   decision='用不到' if b in {'MAJOR_HOUSEHOLD_APPLIANCE','FIREARM_SPECIFIC_STORAGE'} else '观察' if b or not refs else '保留'
   out.append({'record_id':row['record_id'],'input_hash':row['input_hash'],'title_original':row['title_original'],'sample_cohort':row.get('sample_cohort',''),
    'subject':s,'boundary_code':b,'decision':decision,'reason_code':b or ('SAME_LITERAL_FUNCTIONAL_TYPE' if refs else 'NO_VERIFIED_SAME_FUNCTIONAL_REFERENCE'),
    'action_references':refs,'candidate_pool_count':len(candidates),'compatible_pool_count':len(same),'human_confirmed':False,'method_version':self.version})
  return out
