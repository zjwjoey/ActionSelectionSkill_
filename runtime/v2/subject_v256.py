"""Final title-role and functional-subtype guard; no changes to past runs."""
import re
import subject_v255 as previous
from assortment import norm

VERSION='subject-functional-proof-v2.5.6'

def subject(title):
 s=dict(previous.subject(title));t=norm(title);span=s.get('evidence_span','')
 before=t[:t.find(span)] if span else ''
 if re.search(r'\b(?:incluye|incluido|incluidos|incluyendo|contiene|accesorios|with|includes)\b',before):
  return {'status':'UNCLEAR','class_code':'','evidence_span':'','dependent':False,'role_note':'ONLY_INCLUDED_ACCESSORY_IS_RECOGNIZED'}
 if s.get('class_code')=='SPOON':
  s['subtype']='COOKING' if re.search(r'\b(?:cocina|espatula|raspar|cocinar)\b',t) else 'DINING'
 if s.get('class_code')=='CONTACT_GRILL':
  if re.search(r'\b(?:contacto|electric[oa]|sandwichera|\d+\s*w)\b',t):s['subtype']='ELECTRIC_CONTACT'
  elif re.search(r'\b(?:hierro fundido|sarten)\b',t):s['subtype']='STOVETOP_GRIDDLE'
  elif re.search(r'\bbarbacoa\b',t):s['subtype']='BARBECUE'
  else:s['subtype']='UNSPECIFIED'
 return s

def boundary(title,s):return previous.boundary(title,s)
def compatible(a,b):return previous.compatible(a,b)

class Engine(previous.Engine):
 def analyze_many(self,rows):
  results=super().analyze_many(rows)
  for source,r in zip(rows,results):
   s=subject(source['title_original']);refs=[]
   for ref in r['action_references']:
    rs=subject(ref['action_title'])
    if compatible(s,rs):refs.append(dict(ref,reference_subject=rs))
   b=boundary(source['title_original'],s)
   decision='用不到' if b in {'MAJOR_HOUSEHOLD_APPLIANCE','FIREARM_SPECIFIC_STORAGE'} else '观察' if b or not refs else '保留'
   r.update(subject=s,action_references=refs,boundary_code=b,decision=decision,method_version=VERSION,
     reason_code=b or ('SAME_FUNCTIONAL_FAMILY' if refs else 'NO_VERIFIED_SAME_FAMILY'))
  return results
