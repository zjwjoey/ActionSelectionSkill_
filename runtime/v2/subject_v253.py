"""V2.5.3: subject barriers precede household-appliance boundaries.

V2.5.2 remains frozen. This extension was motivated by four false exclusions
in its new-100 audit; those 100 are development cases for this version.
"""
from __future__ import annotations
import re
from collections import defaultdict
import subject_v252 as base
from assortment import Matcher,norm

VERSION='subject-role-guard-v2.5.3'
GUARDS=[
 ('TAP',r'grifos?|aceiteras?|graseras?'),
 ('HINGE_COMPONENT',r'bisagras?|manillas?|manijas?'),
 ('THERMOMETER',r'termometros?|sensores? de temperatura'),
 ('RUG',r'alfombras?|alfombrillas?|carpets?|rugs?'),
 ('CLEANING_PRODUCT',r'desodorantes?|limpiador(?:es)?(?: para)?|detergentes?|absorbedor(?:es)?|neutralizador(?:es)?'),
 ('CLEANING_KIT',r'kits? (?:de )?limpieza'),
 ('TRANSPORT_BAG',r'bolsas? (?:de )?transporte'),
 ('REMOTE_COMPONENT',r'controles? remotos?|guias? de aire|cartuchos? de filtro'),
 ('STORAGE_BOX',r'cajas? (?:de )?(?:conservacion|almacenaje|almacenamiento)'),
 ('VASE',r'floreros?|jarrones?'),
 ('COVER_COMPONENT',r'cubiertas?|cubretendederos?|tapas?'),
 ('ELECTRICAL_COMPONENT',r'fuentes? de alimentacion|modulos?|controlador(?:es)?'),
 ('VINYL',r'vinilos?|papel pintado'),
 ('WINE_COOLER',r'enfriador(?:es)? de vino'),
]
COMPILED=[(k,re.compile(r'\b(?:'+expr+r')\b')) for k,expr in GUARDS]
BLOCKED={'TAP','HINGE_COMPONENT','THERMOMETER','RUG','CLEANING_PRODUCT','CLEANING_KIT','TRANSPORT_BAG',
 'REMOTE_COMPONENT','STORAGE_BOX','VASE','COVER_COMPONENT','ELECTRICAL_COMPONENT','VINYL','WINE_COOLER',
 'GENERIC_MIXER','KNIFE_UNSPECIFIED','CONTAINER_UNSPECIFIED','THREAD_UNSPECIFIED','GLASS','COFFEE_MAKER',
 'SPECIAL_HEATING','ORGANIZER','NON_UTENSIL','EDIBLE_FOOD'}

def subject(title):
 text=norm(title);s=base.subject(title);oldspan=s.get('evidence_span','')
 pos=text.find(oldspan) if oldspan else len(text)+1
 found=[]
 for code,pat in COMPILED:
  m=pat.search(text)
  if m:found.append((m.start(),-len(m.group()),code,m))
 if found:
  start,negative_length,code,m=min(found)
  # "Limpiador a vapor" and "alfombra de baño" are more specific than
  # generic cleaner/carpet; equal-position longer evidenced noun wins.
  if start<pos or (start==pos and -negative_length>len(oldspan)):
   s={'status':'CLEAR','class_code':code,'evidence_span':m.group(),
      'dependent':code.endswith('_COMPONENT'),'audience':'UNSPECIFIED','subtype':''}
 # A product noun discovered only in another clause isn't the sold subject.
 if s['status']=='CLEAR':
  before=text[:text.find(s['evidence_span'])]
  if re.search(r'[,;|]|\b(?:para|for|with|con|compatible|lavables?|apto|apta)\b',before):
   return {'status':'UNCLEAR','class_code':'','evidence_span':'','dependent':False,'role_note':'NOUN_ONLY_IN_ATTRIBUTE_OR_LATER_CLAUSE'}
 if s.get('class_code')=='HOOK' and not re.search(r'\b(?:puertas?|pared|magneticos?|colgar|ropa|abrigos?|llaves|iman(?:es)?)\b',text):
  s=dict(s,reference_scope_uncertain=True)
 return s

def boundary(title,s):
 if s['class_code'] in BLOCKED:
  return 'COMPONENT_OR_UNVERIFIED_SUBJECT_FAMILY'
 return base.boundary(title,s)

def compatible(a,b):
 return base.compatible(a,b) and a['class_code'] not in BLOCKED and not a.get('reference_scope_uncertain') and not b.get('reference_scope_uncertain')

class Engine:
 def __init__(self,matcher=None):
  self.matcher=matcher or Matcher();self.refs=self.matcher.model['references']
  self.subjects=[subject(r['name_es_original']) for r in self.refs];self.families=defaultdict(list)
  for i,s in enumerate(self.subjects):
   if s['status']=='CLEAR' and not s['dependent']:self.families[s['class_code']].append(i)

 def analyze_many(self,rows):
  subjects=[subject(r['title_original']) for r in rows]
  got=self.matcher.retrieve([r['title_original'] for r in rows]+[s['evidence_span'] or r['title_original'] for r,s in zip(rows,subjects)])
  n=len(rows);out=[]
  for k,(row,s) in enumerate(zip(rows,subjects)):
   scores={};channels=defaultdict(list)
   for label,weight,hits in [('ORIGINAL_TITLE',.7,got[k]),('SUBJECT_SPAN',.3,got[n+k])]:
    for i,score in hits:
     scores[i]=scores.get(i,0)+weight*float(score);channels[i].append(label)
   candidates=set(scores)|set(self.families.get(s['class_code'],[]))
   same=[i for i in candidates if compatible(s,self.subjects[i])]
   same.sort(key=lambda i:(-scores.get(i,0),self.refs[i]['sku']))
   linked=[]
   for i in same[:3]:
    r=self.refs[i];linked.append({'action_sku':r['sku'],'action_title':r['name_es_original'],
     'action_source_row_id':r['source_row_id'],'reference_subject':self.subjects[i],
     'relation':'SAME_FUNCTIONAL_FAMILY','retrieval_score':round(scores.get(i,0),8),
     'retrieval_channels':channels[i] or ['SHARED_SUBJECT_FAMILY'],'subtype_equivalence_verified':False})
   b=boundary(row['title_original'],s)
   decision='用不到' if b in {'MAJOR_HOUSEHOLD_APPLIANCE','FIREARM_SPECIFIC_STORAGE'} else '观察' if b or not linked else '保留'
   out.append({'record_id':row['record_id'],'input_hash':row['input_hash'],'title_original':row['title_original'],
    'sample_cohort':row.get('sample_cohort',''),'subject':s,'boundary_code':b,'decision':decision,
    'action_references':linked,'human_confirmed':False,'method_version':VERSION,
    'reason_code':b or ('SAME_FUNCTIONAL_FAMILY' if linked else 'NO_VERIFIED_SAME_FAMILY')})
  return out
