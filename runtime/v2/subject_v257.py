"""V2.5.7: identify the sold noun, then rank compatible reference candidates.

Reuses the frozen Action retriever. No training, source edits, SKU exceptions,
human gold labels or inference of absent attributes.
"""
from __future__ import annotations
import re
from collections import defaultdict
import subject_v256 as previous
from assortment import Matcher,norm

VERSION='subject-before-reference-ranking-v2.5.7'
PATTERNS=[
 ('LAUNDRY_BAG',r'bolsas?(?:\s+\w+){0,3}\s+(?:para\s+)?lavadora|bolsas? para lavar (?:ropa|zapatos)'),
 ('FRENCH_PRESS',r'prensa de cafe francesa|cafeteras? francesas?|french press'),
 ('MOKA_POT',r'cafeteras? italianas?'),('TURKISH_COFFEE_POT',r'cafeteras? turcas?'),
 ('FOOD_JAR',r'tarros?(?: de| para)? (?:conservas?|conservacion|vidrio|cristal|despensa)'),
 ('DRILL',r'taladros?(?: de percusion| percutores?)?'),
 ('BIDET_SPRAYER',r'duchas? bidet|duchas? higienicas?'),
 ('NFC_PLAYER',r'reproductor(?:es)? de musica(?: programable)? nfc'),
 ('SEAT_CUSHION',r'cojin(?:es)? (?:de |para )?(?:silla|asiento)'),
 ('MUFFIN_MOLD',r'moldes? (?:para |de )?magdalenas'),
 ('GRATER',r'rallador(?:es)?'),
 ('TEXTILE_CRAFT_KIT',r'kits? de retazos|kits? de costura'),
 ('ELECTRICAL_FRAME',r'marcos? (?:compactos? )?(?:de |para )?\d+ elementos?'),
 ('SALAD_BOWL',r'ensaladeras?'),
 ('POWER_PLUG',r'enchufes? planos?|clavijas? schuko'),
 ('HALLOWEEN_BAT_DECOR',r'murcielagos?(?: halloween)? decoracion|murcielagos? decorativos?'),
 ('PAELLA_PAN',r'paelleras?'),
 ('SPICE_GRINDER',r'(?:grinder|molinillos?) (?:de |para )?(?:especias|hierbas)'),
 ('HUMIDIFIER',r'humidificador(?:es)?'),
 ('COFFEE_CAPSULE_STORAGE',r'organizador(?:es)?(?: de \w+)? para \d+ capsulas de cafe'),
 ('BARISTA_ACCESSORY_KIT',r'kits? barista'),
 ('BLOWER',r'soplador(?:es)?'),('BATHROOM_MIRROR',r'espejos? de bano'),
 ('INLINE_SWITCH',r'interruptor(?:es)? (?:de luz )?en linea|interruptor(?:es)? de cable'),
 ('SHELF_BRACKET',r'escuadras? (?:para|de) estanterias?|soportes? (?:para|de) estantes?'),
 ('PAPER_RAFFIA',r'rafia de papel'),
 ('EARRING_BACK',r'tuercas? de pendientes|cierres? (?:de )?pendientes'),
 ('BLACKOUT_CURTAIN',r'cortinas? opacas?'),
 ('MODELING_CLAY',r'arcillas?(?: firmes? al horno| polimericas?| para moldear| para manualidades)?'),
 ('MONITOR_STAND',r'soportes? (?:de |para )?monitor|elevador(?:es)? (?:de |para )?pantalla'),
 ('WOOD_FINISH_OIL',r'aceites? (?:danes|para madera|de teca)'),
 ('BOOK_SAFE',r'cajas? fuertes? (?:libro|en forma de libro)'),
]
COMPILED=[(code,re.compile(r'\b(?:'+expr+r')\b')) for code,expr in PATTERNS]
ROLE_CONNECTOR=re.compile(r'\b(?:para|for|with|con|incluye|incluido|incluidos|incluyendo|contiene|includes|compatible|accesorios)\b')
RESEARCH_TYPES={'POWER_PLUG','ELECTRICAL_FRAME','INLINE_SWITCH','SHELF_BRACKET','BARISTA_ACCESSORY_KIT'}

def subject(title):
 text=norm(title);old=previous.subject(title);span=old.get('evidence_span','')
 pos=text.find(span) if span else len(text)+1
 candidates=[]
 for code,pattern in COMPILED:
  m=pattern.search(text)
  if code=='MODELING_CLAY' and m and re.search(r'\b(?:mascarilla|piel|facial|jabon)\b',text[:m.start()]):continue
  if m and not ROLE_CONNECTOR.search(text[:m.start()]):
   candidates.append((m.start(),-len(m.group()),code,m))
 if candidates:
  start,neglen,code,m=min(candidates)
  if start<pos or (start==pos and -neglen>=len(span)):
   old={'status':'CLEAR','class_code':code,'evidence_span':m.group(),
        'dependent':False,'audience':'UNSPECIFIED','subtype':'','subject_rule':'LITERAL_SOLD_NOUN'}
 code=old.get('class_code','')
 if code in {'FAN','AC','AIR_COOLER'} and re.search(r'\b(?:evaporativo|refrigeracion por agua)\b',text):
  old=dict(old,class_code='AIR_COOLER',functional_evidence=re.search(r'\b(?:evaporativo|refrigeracion por agua)\b',text).group())
 if code=='HUMIDIFIER':
  old['subtype']='RADIATOR_PASSIVE' if re.search(r'\bradiador\b',text) else 'FACIAL' if re.search(r'\bfacial\b',text) else 'ROOM' if re.search(r'\b(?:dormitorio|habitacion|aire|usb|\d+\s*ml)\b',text) else 'UNSPECIFIED'
 if code=='DRILL':old['subtype']='PERCUSSION' if re.search(r'\b(?:percutor|percusion)\b',text) else 'UNSPECIFIED'
 if code=='MODELING_CLAY':old['subtype']='OVEN_POLYMER' if re.search(r'\b(?:horno|polimerica)\b',text) else 'UNSPECIFIED'
 if code=='WOOD_FINISH_OIL':old['subtype']='DANISH' if re.search(r'\bdanes\b',text) else 'TEAK' if re.search(r'\bteca\b',text) else 'UNSPECIFIED'
 if code=='SEAT_CUSHION':old['subtype']='MEDICAL_CLAIM' if re.search(r'\bantiescaras\b',text) else 'UNSPECIFIED'
 # Materials mentioned in skin care or an included component do not become
 # the main craft material. Longer earlier patterns from the frozen parser win.
 if old['status']=='CLEAR' and ROLE_CONNECTOR.search(text[:text.find(old['evidence_span'])]):
  return {'status':'UNCLEAR','class_code':'','evidence_span':'','dependent':False,'role_note':'NOUN_IN_HOST_OR_ATTRIBUTE_CLAUSE'}
 return old

def boundary(title,s):
 if s['class_code'] in RESEARCH_TYPES:return 'INSTALLATION_OR_ACCESSORY_RESEARCH'
 if s.get('subtype')=='MEDICAL_CLAIM':return 'CLAIM_SCOPE_RESEARCH'
 if s['class_code'] in {x[0] for x in PATTERNS}:return '' if s['status']=='CLEAR' else 'UNCLEAR_SUBJECT'
 return previous.boundary(title,s)

def compatible(a,b):
 if a['status']!='CLEAR' or b['status']!='CLEAR' or a.get('dependent') or b.get('dependent'):return False
 if a['class_code']!=b['class_code']:return False
 if a.get('audience','UNSPECIFIED')!=b.get('audience','UNSPECIFIED'):return False
 if a.get('subtype','')!=b.get('subtype',''):return False
 if a['class_code'] in {x[0] for x in PATTERNS}:
  return a['class_code'] not in RESEARCH_TYPES and a.get('subtype') not in {'MEDICAL_CLAIM'}
 return previous.compatible(a,b)

def relation(a,b):
 if compatible(a,b):return 'SAME_FUNCTIONAL_SUBTYPE'
 if a.get('class_code') and a.get('class_code')==b.get('class_code'):return 'RELATED_CLASS_DIFFERENT_OR_UNPROVEN_SUBTYPE'
 return 'NOT_SAME_CLASS'

class Engine:
 def __init__(self,matcher=None):
  self.matcher=matcher or Matcher();self.refs=self.matcher.model['references']
  self.subjects=[subject(r['name_es_original']) for r in self.refs];self.families=defaultdict(list)
  for i,s in enumerate(self.subjects):
   if s['status']=='CLEAR':self.families[s['class_code']].append(i)

 def analyze_many(self,rows):
  subjects=[subject(r['title_original']) for r in rows];n=len(rows)
  hits=self.matcher.retrieve([r['title_original'] for r in rows]+[s['evidence_span'] or r['title_original'] for r,s in zip(rows,subjects)])
  out=[]
  for k,(row,s) in enumerate(zip(rows,subjects)):
   scores={};channels=defaultdict(list)
   for label,weight,items in [('ORIGINAL_TITLE',.7,hits[k]),('SOURCE_SUBJECT_SPAN',.3,hits[n+k])]:
    for j,score in items:scores[j]=scores.get(j,0)+weight*float(score);channels[j].append(label)
   candidates=set(scores)|set(self.families.get(s['class_code'],[]))
   # Crucial: filter the whole candidate pool before selecting the top three.
   same=[j for j in candidates if compatible(s,self.subjects[j])]
   same.sort(key=lambda j:(-scores.get(j,0),self.refs[j]['sku']))
   refs=[]
   for j in same[:3]:
    ref=self.refs[j];refs.append({'action_sku':ref['sku'],'action_title':ref['name_es_original'],
     'action_source_row_id':ref['source_row_id'],'reference_subject':self.subjects[j],
     'relation':relation(s,self.subjects[j]),'retrieval_score':round(scores.get(j,0),8),
     'retrieval_channels':channels[j] or ['SUBJECT_FAMILY'],'subtype_equivalence_verified':False})
   b=boundary(row['title_original'],s)
   decision='用不到' if b in {'MAJOR_HOUSEHOLD_APPLIANCE','FIREARM_SPECIFIC_STORAGE'} else '观察' if b or not refs else '保留'
   out.append({'record_id':row['record_id'],'input_hash':row['input_hash'],'title_original':row['title_original'],
    'sample_cohort':row.get('sample_cohort',''),'subject':s,'boundary_code':b,'decision':decision,
    'reason_code':b or ('SAME_FUNCTIONAL_SUBTYPE' if refs else 'NO_VERIFIED_SAME_FUNCTIONAL_REFERENCE'),
    'action_references':refs,'candidate_pool_count':len(candidates),'compatible_pool_count':len(same),
    'human_confirmed':False,'method_version':VERSION})
  return out
