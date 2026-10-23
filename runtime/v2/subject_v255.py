"""Positive appliance-form proof and subtype/audience guards.

No keywords alone establish exclusion. Keep prior frozen experiments intact;
reuse the existing retriever and tighten candidate projection in this version.
"""
import re
import subject_v254 as previous
from assortment import norm

VERSION='subject-positive-proof-v2.5.5'

def subject(title):
 s=dict(previous.subject(title));t=norm(title)
 s['audience']='INFANT' if re.search(r'\b(?:bebes?|infantil(?:es)?|ninos?|ninas?)\b',t) else 'UNSPECIFIED'
 if s.get('class_code')=='FOOD_BOX' and re.search(r'\b(?:electric[oa]s?|calentador|autocalentable)\b',t):s['subtype']='ELECTRIC_HEATING'
 return s

def boundary(title,s):
 b=previous.boundary(title,s);t=norm(title)
 if b!='MAJOR_HOUSEHOLD_APPLIANCE':return b
 # A misleading marketplace heading can name the host first. Positive form
 # evidence must coexist with the heading; explicit non-appliance nouns veto
 # exclusion. Abstention is intentional, never a target exclusion quota.
 if re.search(r'\b(?:eliminador|absorbedor|desodorizador|desodorante|ambientador|neutralizador|funda|cubierta|deflector|bisagra|termometro|limpiador|detergente)\b',t):return 'APPLIANCE_COUNTEREVIDENCE_RESEARCH'
 proofs={
  'AC':r'\b\d{4,5}\s*btu\b|\bsplit\b|\bbomba de calor\b',
  'FRIDGE':r'\bcombi\b|\b\d+(?:[.,]\d+)?\s*(?:litros?|l)\b|\bcompresor\b|\b(?:dos|2) puertas\b',
  'WASHER':r'\bcarga (?:frontal|superior)\b|\b\d+(?:[.,]\d+)?\s*kg\b',
  'DRYER':r'\b\d+(?:[.,]\d+)?\s*kg\b|\bbomba de calor\b|\bcondensacion\b',
  'DISHWASHER':r'\b(?:integrable|integrado|empotrado)\b|\b\d+\s*cubiertos\b',
 }
 if not re.search(proofs.get(s['class_code'],r'(?!)'),t):return 'APPLIANCE_FORM_PROOF_INSUFFICIENT'
 return b

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
