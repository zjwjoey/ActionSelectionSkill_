"""Installation/use-form compatibility for fans and mounting hooks."""
import re
import subject_v259 as previous
from subject_reference_core import ReferenceEngine
from assortment import norm
VERSION='subject-installation-form-proof-v2.5.10'
def subject(title):
 s=dict(previous.subject(title));t=norm(title)
 if s.get('class_code')=='FAN':
  s['subtype']='CEILING' if re.search(r'\btecho\b',t) else 'CAR' if re.search(r'\b(?:coche|automovil|vehiculo)\b',t) else 'TOWER' if re.search(r'\btorre\b',t) else 'STANDING' if re.search(r'\bde pie\b',t) else 'HANDHELD' if re.search(r'\b(?:de mano|manual)\b',t) else 'DESKTOP' if re.search(r'\b(?:escritorio|de mesa|sobremesa)\b',t) else 'UNSPECIFIED'
 if s.get('class_code')=='HOOK':
  s['subtype']='MAGNETIC' if re.search(r'\b(?:magnetic[oa]s?|iman(?:es)?)\b',t) else 'NAIL' if re.search(r'\bclavos?\b',t) else 'ADHESIVE' if re.search(r'\badhesiv[oa]s?\b',t) else 'OVER_DOOR' if re.search(r'\b(?:de|para) (?:la )?puerta\b',t) else 'UNSPECIFIED'
 return s
def boundary(title,s):return previous.boundary(title,s)
def compatible(a,b):
 if a.get('class_code') in {'FAN','HOOK'} and a.get('subtype')=='UNSPECIFIED':return False
 return previous.compatible(a,b)
class Engine(ReferenceEngine):
 def __init__(self,matcher=None):super().__init__(VERSION,subject,boundary,compatible,matcher)
