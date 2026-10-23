"""Earlier source nouns veto a recognized host/accessory later in the title."""
import re
import subject_v2511 as previous
from subject_v257 import ROLE_CONNECTOR
from subject_reference_core import ReferenceEngine
from assortment import Matcher,norm
VERSION='subject-earlier-noun-contract-v2.5.12'
HEADS=[('BAKING_PAPER',re.compile(r'\bpapel (?:para )?(?:freidora|horno|pergamino)\b')),
 ('KETTLE',re.compile(r'\bhervidor(?:es)?(?: (?:de )?agua)?(?: electrico)?\b')),
 ('TABLE_LEG',re.compile(r'\bpatas? de (?:mesa|banco)\b'))]
WRAPPERS={'juego','set','pack','paquete','lote','kit','unidad','pieza','producto','nuevo','mini'}
KNOWN_ROLES={'papel','pata','hervidor','bolsa','estuche','carcasa','mango','base','placa','cepillo','cesta','cesto','bandeja','funda','recambio','repuesto','soporte','rasqueta','taquilla'}
def subject(title,features=None):
 t=norm(title);s=dict(previous.subject(title));span=s.get('evidence_span','');pos=t.find(span) if span else len(t)+1
 for code,pattern in HEADS:
  m=pattern.search(t)
  if m and m.start()<pos and not ROLE_CONNECTOR.search(t[:m.start()]):
   s={'status':'CLEAR','class_code':code,'evidence_span':m.group(),'dependent':False,'audience':'UNSPECIFIED','subtype':''};pos=m.start()
 if s['status']=='CLEAR':
  prefix=t[:t.find(s['evidence_span'])]
  if features:
   words=features.words(prefix);vocab=set(features.head_vocabulary)|KNOWN_ROLES
  else:
   words=[w[:-1] if w.endswith('s') else w for w in re.findall(r'[a-z]+',prefix)];vocab=KNOWN_ROLES
  earlier=[w for w in words if w in vocab and w not in WRAPPERS]
  if earlier:
   return {'status':'UNCLEAR','class_code':'','evidence_span':'','dependent':False,
    'role_note':'EARLIER_SOURCE_NOUN_UNRESOLVED','earlier_noun_candidates':earlier,
    'rejected_later_subject':s,'earlier_source_span':prefix.strip()}
 return s
def boundary(title,s):
 if s['class_code']=='TABLE_LEG':return 'FURNITURE_COMPONENT_RESEARCH'
 if s['class_code'] in {'BAKING_PAPER','KETTLE'}:return ''
 return previous.boundary(title,s)
def compatible(a,b):
 if a.get('class_code') in {'BAKING_PAPER','KETTLE','TABLE_LEG'}:
  return a['status']==b['status']=='CLEAR' and a['class_code']==b['class_code'] and not a.get('dependent') and not b.get('dependent')
 return previous.compatible(a,b)
class Engine(ReferenceEngine):
 def __init__(self,matcher=None):
  matcher=matcher or Matcher();features=getattr(matcher,'f',None)
  super().__init__(VERSION,lambda title:subject(title,features),boundary,compatible,matcher)
