"""Reusable title-only subject families and evidence-bound Action matching.

Deterministic candidate engine, not a semantic model or human evaluation.
No SKU exceptions, source writes, training or changes to frozen baselines.
"""
from __future__ import annotations
import re
from collections import defaultdict
from assortment import Matcher, norm

VERSION = 'subject-functional-family-v2.5.2'
# Shared by Amazon and Action. Specific phrases win at the same noun position.
# The earliest sold noun wins over hosts/uses mentioned later in the title.
FAMILIES = [
 ('COFFEE_MAKER',r'cafeteras?|french press'),
 ('FAN',r'ventilador(?:es)?|fan'),
 ('SPECIAL_HEATING',r'estufas?|termos? electricos?'),
 ('ORGANIZER',r'organizador(?:es)?'),
 ('NON_UTENSIL',r'peluches?|esteras?|bandejas? de parrilla'),
 ('AC',r'aire acondicionado|acondicionador de aire'),
 ('AIR_COOLER',r'enfriador(?:es)?(?: de aire)?|climatizador(?:es)? evaporativo'),
 ('DISHWASHER',r'lavavajillas'),('WASHER',r'lavadora(?:s)?'),
 ('DRYER',r'secadora(?:s)?(?: de ropa)?'),('FRIDGE',r'frigorifico(?:s)?|refrigerador(?:es)?'),
 ('WINE_GLASS',r'copas?(?: de cristal)?(?: de| para) vino'),
 ('GLASS',r'vasos?(?! medidores)|copas?'),
 ('FOOD_BOX',r'recipientes?(?: hermeticos?)?|tapers?|tuppers?|fiambreras?|tarteras?|contenedores? (?:de |para )?alimentos|cajas? (?:de |para )?alimentos|cuencos? (?:de |para )?almacenamiento|botes?(?: de cocina)?'),
 ('SPOON',r'cucharillas?|cucharas?(?! medidoras)'),
 ('MEASURING_SPOON',r'cucharas? medidoras?'),
 ('CUTLERY',r'cubiertos?'),('DINNERWARE',r'vajillas?'),
 ('PLATE',r'platos?'),('BOWL',r'cuencos?|boles?|bowls?'),
 ('HAND_MIXER',r'batidoras?(?: electrica)? de varillas|mezcladoras? de mano'),
 ('HAND_BLENDER',r'batidoras? (?:de inmersion|de brazo|de mano)'),
 ('GENERIC_MIXER',r'batidoras?'),
 ('FROTHER',r'espumador(?:es)?(?: de leche)?|batidor(?:es)? de leche'),
 ('PEELER',r'pelador(?:es)?'),('MUG',r'tazas?'),('BOTTLE',r'botellas?|cantimploras?'),
 ('WOK',r'sarten(?:es)? de wok|woks?'),('FRYING_PAN',r'sarten(?:es)?'),('POT',r'ollas?|cacerolas?'),
 ('FRYER',r'freidoras?'),('TOASTER',r'tostador(?:a|as|es)?'),
 ('CONTACT_GRILL',r'parrillas?(?: electricas?)?|grills?(?: de contacto)?'),
 ('KITCHEN_KNIFE',r'cuchillos?'),('BLANKET',r'mantas?|plaids?'),
 ('ARTIFICIAL_PLANT',r'plantas? artificial(?:es)?|plantas? decorativas?'),
 ('CROCHET',r'ganchillos?|agujas? de (?:crochet|ganchillo)'),
 ('SOAP_DISH',r'jaboneras?'),('CABLE_REEL',r'enrollacables?|carretes? de cable|bobinas? de cable'),
 ('SHOPPING_BAG',r'bolsas? (?:de |para )?(?:la )?compras?|bolsos? tote'),
 ('CRAFT_CORD',r'cordones?|hilos?'),('HOOK',r'ganchos?|colgadores?'),
 ('BATH_MAT',r'alfombras?(?: diatomita)? (?:de )?bano|alfombrillas? de bano'),
 ('DOORMAT',r'felpudos?'),('HAIR_TOWEL',r'toallas? (?:para (?:el )?pelo|de microfibra para (?:el )?cabello)|turbantes?'),
 ('TOWEL',r'toallas?'),('HEATER',r'calefactor(?:es)?|convector(?:es)?|radiador(?:es)? convector(?:es)?|calentador(?:es)? de enchufe'),
 ('PHOTO_FRAME',r'marcos? (?:de |para )?(?:fotos|fotografias)|portafotos'),
 ('STEAM_CLEANER',r'limpiador(?:es)? (?:de |a |al )?vapor|limpiadoras? (?:de |a |al )?vapor|limpiavapor'),
 ('FLASHLIGHT',r'linternas?'),('GIFT_BAG',r'bolsas? (?:de |para )?(?:regalo|regalos)'),
 ('GUN_STORAGE',r'armeros?|armarios? para (?:\d+[ -]*)?armas|cajas? (?:fuertes? )?(?:de |para )(?:municiones|cartuchos|rifles|armas)'),
 ('BAKING_DISH',r'moldes? (?:para|de) souffle|cuencos? para horno'),
 ('FURNITURE',r'muebles?|armarios?|escritorios?|sofas?|aparadores?|comodas?|mesas? (?:de comedor|de centro|de escritorio)'),
 ('COMPONENT',r'repuestos?|recambios?|deflector(?:es)?|filtros?|adaptador(?:es)?|mandos?(?: a distancia)?|mecanismos?|piezas? (?:de repuesto|para)|panel(?:es)?|puertas?|fundas?|soportes?|protector(?:es)?|organizador(?:es)? (?:de )?cables|tapon(?:es)?'),
]
COMPILED=[(code,re.compile(r'\b(?:'+expr+r')\b')) for code,expr in FAMILIES]
DEPENDENT=re.compile(r'\b(?:compatible con|recambio para|repuesto para|pieza de repuesto|para modelo)\b')

def subject(title):
 text=norm(title)
 # A brand/model with no supported noun stays unclear; no brand lookup.
 matches=[]
 for ordinal,(code,pat) in enumerate(COMPILED):
  m=pat.search(text)
  if m:matches.append((m.start(),-len(m.group()),ordinal,code,m))
 if not matches:return {'status':'UNCLEAR','class_code':'','evidence_span':'','dependent':False}
 _,_,_,code,m=min(matches)
 # Do not promote a host noun from a use/compatibility clause without a noun
 # in the subject position (e.g. "para frigorifico" by itself).
 before=text[:m.start()]
 if re.search(r'\b(?:para|for|with|con|compatible con|apto para|apta para)\b',before):
  return {'status':'UNCLEAR','class_code':'','evidence_span':'','dependent':True}
 if code=='AC' and not re.search(r'\b\d{4,5}\s*btu\b',text) and re.search(r'\b(?:usb|evaporativo|\d+\s*ml|deposito de agua)\b',text):
  code='AIR_COOLER'
 # Compatibility with a cup holder is an attribute, not a dependent part.
 dependent=code=='COMPONENT' or bool(DEPENDENT.search(text[:m.end()]))
 if code=='HAND_BLENDER' and re.search(r'\bvarillas\b',text):code='HAND_MIXER'
 if code=='GENERIC_MIXER' and re.search(r'\bvarillas\b',text):code='HAND_MIXER'
 audience='INFANT' if re.search(r'\b(?:bebe|bebes|infantil|ninos)\b',text) else 'UNSPECIFIED'
 # Distinguish vacuum packaging from ordinary boxes; absence isn't proof.
 subtype='VACUUM' if code=='FOOD_BOX' and re.search(r'\bvacio\b',text) else ''
 if code=='SPOON' and re.search(r'\bcucharas? de chocolate\b',text):code='EDIBLE_FOOD'
 if code=='CRAFT_CORD' and not re.search(r'\b(?:nylon|pulseras|bordar|bordado|macrame|algodon|bisuteria)\b',text):code='THREAD_UNSPECIFIED'
 if code=='TOWEL' and re.search(r'\b(?:pelo|cabello)\b',text):code='HAIR_TOWEL'
 if code=='FRYER':subtype='AIR' if re.search(r'\baire\b',text) else 'OIL' if re.search(r'\baceite\b',text) else 'UNSPECIFIED'
 if code=='KITCHEN_KNIFE' and not re.search(r'\b(?:cocina|jamonero|carne|verduras|mesa|pelar|filetear|pan)\b',text):code='KNIFE_UNSPECIFIED'
 # Only explicitly food-use containers are interchangeable as a family.
 if code=='FOOD_BOX' and not re.search(r'\b(?:alimentos|comida|cocina|fiambrera|fiambreras|tupper|tuppers|taper|tapers|tartera|tarteras|embutidos?|hermeticos?|hermeticas?)\b',text):code='CONTAINER_UNSPECIFIED'
 return {'status':'CLEAR','class_code':code,'evidence_span':m.group(),'dependent':dependent,'audience':audience,'subtype':subtype}

def boundary(title,s):
 text=norm(title);code=s['class_code']
 if s['status']!='CLEAR':return 'UNCLEAR_SUBJECT'
 if s['dependent']:return 'DEDICATED_OR_COMPONENT_RESEARCH'
 if code=='FURNITURE':return 'FURNITURE_RESEARCH'
 if code=='GUN_STORAGE':return 'FIREARM_SPECIFIC_STORAGE'
 if code=='AC':
  # Form/use uncertainty, not an arbitrary BTU threshold. Fan mode never
  # changes a complete AC into a small fan/evaporative appliance.
  if re.search(r'\b(?:camping|tiendas de campana|autocaravanas|sin instalacion)\b',text):return 'COMPACT_REFRIGERATION_RESEARCH'
  if re.search(r'\b\d{4,5}\s*btu\b|\bsplit\b|\bbomba de calor\b',text):return 'MAJOR_HOUSEHOLD_APPLIANCE'
  return 'APPLIANCE_FORM_UNCERTAIN'
 if code in {'DISHWASHER','WASHER','DRYER','FRIDGE'}:return 'MAJOR_HOUSEHOLD_APPLIANCE'
 return ''

def compatible(a,b):
 if a['status']!='CLEAR' or b['status']!='CLEAR' or a['dependent'] or b['dependent']:return False
 if a['class_code']!=b['class_code']:return False
 if (a.get('audience')=='INFANT')!=(b.get('audience')=='INFANT'):return False
 if a.get('subtype','')!=b.get('subtype',''):return False
 return True

class Engine:
 def __init__(self,matcher=None):
  self.matcher=matcher or Matcher();self.refs=self.matcher.model['references']
  self.subjects=[subject(r['name_es_original']) for r in self.refs]
  self.families=defaultdict(list)
  for i,s in enumerate(self.subjects):
   if s['status']=='CLEAR' and not s['dependent']:self.families[s['class_code']].append(i)

 def analyze_many(self,rows):
  subjects=[subject(r['title_original']) for r in rows]
  # Frozen TF-IDF/SVD is reused, not retrained. All references are real indexed
  # source rows. The family channel prevents brand/attribute noise losing them.
  queries=[r['title_original'] for r in rows]+[s['evidence_span'] or r['title_original'] for r,s in zip(rows,subjects)]
  retrieved=self.matcher.retrieve(queries);n=len(rows);out=[]
  for k,(row,s) in enumerate(zip(rows,subjects)):
   scores={}
   for channel in (retrieved[k],retrieved[n+k]):
    for i,score in channel:scores[i]=max(scores.get(i,0),float(score))
   candidates=set(scores)|set(self.families.get(s['class_code'],[]))
   same=[i for i in candidates if compatible(s,self.subjects[i]) and s['class_code'] not in {'GENERIC_MIXER','KNIFE_UNSPECIFIED','CONTAINER_UNSPECIFIED','THREAD_UNSPECIFIED','GLASS','COFFEE_MAKER','SPECIAL_HEATING','ORGANIZER','NON_UTENSIL','EDIBLE_FOOD'}]
   same.sort(key=lambda i:(-scores.get(i,0),self.refs[i]['sku']))
   linked=[]
   for i in same[:3]:
    ref=self.refs[i]
    linked.append({'action_sku':ref['sku'],'action_title':ref['name_es_original'],
      'action_source_row_id':ref['source_row_id'],'reference_subject':self.subjects[i],
      'relation':'SAME_FUNCTIONAL_FAMILY','retrieval_score':scores.get(i,0),
      'retrieval_channel':'ORIGINAL_OR_SUBJECT' if i in scores else 'SHARED_SUBJECT_FAMILY',
      'subtype_equivalence_verified':False})
   b=boundary(row['title_original'],s)
   if b in {'MAJOR_HOUSEHOLD_APPLIANCE','FIREARM_SPECIFIC_STORAGE'}:decision='用不到'
   elif b or not linked:decision='观察'
   else:decision='保留'
   out.append({'record_id':row['record_id'],'input_hash':row['input_hash'],'title_original':row['title_original'],
     'sample_cohort':row.get('sample_cohort',''),'subject':s,'boundary_code':b,
     'decision':decision,'action_references':linked,'human_confirmed':False,'method_version':VERSION,
     'reason_code':b or ('SAME_FUNCTIONAL_FAMILY' if linked else 'NO_VERIFIED_SAME_FAMILY')})
  return out
