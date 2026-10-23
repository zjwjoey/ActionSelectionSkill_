"""Literal cleaning tools and whole lockers precede their accessories/doors."""
import re
import subject_v2510 as previous
from subject_v257 import ROLE_CONNECTOR
from subject_reference_core import ReferenceEngine
from assortment import norm
VERSION='subject-whole-item-role-proof-v2.5.11'
PATTERNS=[('SHOWER_SQUEEGEE',re.compile(r'\b(?:rasquetas? de ducha|limpiacristales? de ducha)\b')),
          ('LOCKER',re.compile(r'\btaquillas?(?: vestuario)?\b'))]
def subject(title):
 t=norm(title);s=dict(previous.subject(title));span=s.get('evidence_span','');pos=t.find(span) if span else len(t)+1
 for code,pattern in PATTERNS:
  m=pattern.search(t)
  if m and m.start()<pos and not ROLE_CONNECTOR.search(t[:m.start()]):
   s={'status':'CLEAR','class_code':code,'evidence_span':m.group(),'dependent':False,'audience':'UNSPECIFIED','subtype':''};pos=m.start()
 return s
def boundary(title,s):
 if s['class_code']=='LOCKER':return 'FURNITURE_RESEARCH'
 if s['class_code']=='SHOWER_SQUEEGEE':return ''
 return previous.boundary(title,s)
def compatible(a,b):
 if a.get('class_code') in {'SHOWER_SQUEEGEE','LOCKER'}:
  return a['status']==b['status']=='CLEAR' and a['class_code']==b['class_code'] and not a.get('dependent') and not b.get('dependent')
 return previous.compatible(a,b)
class Engine(ReferenceEngine):
 def __init__(self,matcher=None):super().__init__(VERSION,subject,boundary,compatible,matcher)
