"""Operating-mode and multi-object evidence for the existing subject engine."""
import re
import subject_v258 as previous
from subject_reference_core import ReferenceEngine
from assortment import norm
VERSION='subject-operating-mode-proof-v2.5.9'
def subject(title):
 s=dict(previous.subject(title));t=norm(title);code=s.get('class_code')
 if code=='DRILL':
  s['subtype']='MANUAL_PINVISE' if re.search(r'\bmanual\b',t) else 'PERCUSSION' if re.search(r'\b(?:percutor|percusion)\b',t) else 'POWERED' if re.search(r'\b(?:electrico|bateria|inalambrico|\d+\s*[vw])\b',t) else 'UNSPECIFIED'
 if code=='FRYER':
  s['subtype']='STOVETOP' if re.search(r'\b(?:fuegos|fogones|vitroceramica)\b',t) else s.get('subtype','UNSPECIFIED')
 if code=='HEATER':
  s['subtype']='CERAMIC' if re.search(r'\bceramic[oa]\b',t) else 'CONVECTOR' if re.search(r'\b(?:convector|conveccion)\b',t) else 'OIL_FILLED' if re.search(r'\baceite\b',t) else 'UNSPECIFIED'
 if code=='BOTTLE':
  if re.search(r'\b(?:condimentos|aceite|vinagre)\b',t):
   if re.search(r'\bcoctelera\b',t):return {'status':'UNCLEAR','class_code':'','evidence_span':'','dependent':False,'role_note':'MULTIPLE_INCOMPATIBLE_SOURCE_SUBJECTS'}
   s['subtype']='KITCHEN_DISPENSER'
  elif re.search(r'\b(?:agua|water|cantimplora)\b',t):s['subtype']='WATER_BOTTLE'
  else:s['subtype']='UNSPECIFIED'
 # Explicit air-frying and grill functions form a composite product. A pure
 # contact grill is related evidence, not proof of the composite's same type.
 if code in {'FRYER','CONTACT_GRILL'} and re.search(r'\bfreidora(?: de aire| sin aceite)\b',t) and re.search(r'\bgrill\b',t):
  s['class_code']='AIR_FRYER_GRILL_COMPOSITE';s['subtype']='EXPLICIT_DUAL_FUNCTION'
 return s
def boundary(title,s):
 if s.get('role_note')=='MULTIPLE_INCOMPATIBLE_SOURCE_SUBJECTS':return 'SOURCE_SUBJECT_CONFLICT'
 if s['class_code']=='AIR_FRYER_GRILL_COMPOSITE':return ''
 return previous.boundary(title,s)
def compatible(a,b):
 if a.get('class_code') in {'DRILL','HEATER','BOTTLE','FRYER'} and a.get('subtype')=='UNSPECIFIED':return False
 if a.get('class_code')=='AIR_FRYER_GRILL_COMPOSITE':
  return a['status']==b['status']=='CLEAR' and a['class_code']==b['class_code'] and a.get('subtype')==b.get('subtype')
 return previous.compatible(a,b)
class Engine(ReferenceEngine):
 def __init__(self,matcher=None):super().__init__(VERSION,subject,boundary,compatible,matcher)
