"""Typed tools, host nouns and source-supported reference subtypes."""
import re
import subject_v257 as previous
from subject_reference_core import ReferenceEngine
from assortment import norm
VERSION='subject-role-and-functional-subtype-v2.5.8'
HEADS=[
 ('LAUNDRY_BAG',r'bolsas? para lavar (?:ropa|zapatos|zapatillas)'),
 ('LAMP',r'lamparas?|luces? de escritorio'),
 ('MAGNET',r'imanes?|iman'),
 ('SHELVING',r'estanterias?'),
 ('LAUNDRY_LINT_REMOVER',r'quita pelos|bolas? (?:atrapa|recoge)'),
]
PATTERNS=[(k,re.compile(r'\b(?:'+p+r')\b')) for k,p in HEADS]
def subject(title):
 t=norm(title);s=dict(previous.subject(title));span=s.get('evidence_span','');pos=t.find(span) if span else len(t)+1
 options=[]
 for code,pattern in PATTERNS:
  m=pattern.search(t)
  if m and not previous.ROLE_CONNECTOR.search(t[:m.start()]):options.append((m.start(),-len(m.group()),code,m))
 if options:
  start,neg,code,m=min(options)
  if start<pos or (start==pos and -neg>=len(span)):
   s={'status':'CLEAR','class_code':code,'evidence_span':m.group(),'dependent':False,'audience':'UNSPECIFIED','subtype':''}
 code=s.get('class_code')
 if code=='BLOWER':
  s['subtype']='BUBBLE_TOY' if re.search(r'\bburbujas\b',t) else 'POWERED_AIR_TOOL' if re.search(r'\b(?:hojas|limpieza|inflado|bateria|\d+\s*v)\b',t) else 'UNSPECIFIED'
 if code=='FURNITURE':
  s['subtype']='DESK' if re.search(r'\bescritorio\b',t) else 'COFFEE_TABLE' if re.search(r'\bmesa de centro\b',t) else 'CABINET' if re.search(r'\barmario\b',t) else 'SOFA' if re.search(r'\bsofa\b',t) else 'UNSPECIFIED'
 if code=='HAIR_TOWEL':
  s['subtype']='COSMETIC_WRAP' if re.search(r'\bcosmetica\b',t) else 'HAIR_DRYING' if re.search(r'\b(?:pelo|cabello)\b',t) else 'UNSPECIFIED'
 if code=='HUMIDIFIER' and re.search(r'\b(?:puros|cigarcabinet|humidor)\b',t):s['subtype']='CIGAR_USE'
 if code=='LAMP':s['subtype']='DESK' if re.search(r'\bescritorio\b',t) else 'BATHROOM' if re.search(r'\b(?:ducha|bano|espejo)\b',t) else 'UNSPECIFIED'
 if code=='MAGNET':s['subtype']='DECOR_SOUVENIR' if re.search(r'\b(?:souvenir|recuerdo|viaje|vacaciones)\b',t) else 'UTILITY' if re.search(r'\b(?:neodimio|pizarra|fuertes?)\b',t) else 'UNSPECIFIED'
 return s
def boundary(title,s):
 if s['class_code']=='SHELVING':return 'FURNITURE_RESEARCH'
 if s['class_code'] in {'LAMP','MAGNET','LAUNDRY_LINT_REMOVER'}:return '' if s['status']=='CLEAR' else 'UNCLEAR_SUBJECT'
 return previous.boundary(title,s)
def compatible(a,b):
 if a.get('class_code') in {'LAMP','MAGNET','SHELVING','LAUNDRY_LINT_REMOVER'}:
  return a['status']==b['status']=='CLEAR' and a['class_code']==b['class_code'] and not a.get('dependent') and not b.get('dependent') and a.get('subtype','')==b.get('subtype','') and not (a['class_code'] in {'LAMP','MAGNET'} and a.get('subtype')=='UNSPECIFIED')
 if a.get('class_code') in {'BLOWER','HUMIDIFIER'} and a.get('subtype')=='UNSPECIFIED':return False
 return previous.compatible(a,b)
class Engine(ReferenceEngine):
 def __init__(self,matcher=None):super().__init__(VERSION,subject,boundary,compatible,matcher)
