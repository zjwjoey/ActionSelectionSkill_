"""Literal evidence extraction for repeated failure families; absent is unknown."""
import re,unicodedata
VERSION='literal-attributes-v1'
def fold(t):return ''.join(c for c in unicodedata.normalize('NFKD',t.casefold()) if not unicodedata.combining(c))
FAMILIES=[('box',r'\b(?:caja|box|boite)\b'),('knife',r'\b(?:cuchillos?|knives|knife)\b'),('battery',r'\b(?:pilas?|baterias?|batter(?:y|ies))\b'),('shelf',r'\b(?:estantes?|estanteria|baldas?|libreria|shel(?:f|ves)|etagere)\b'),('vacuum',r'\b(?:aspirador(?:a)?|vacuum)\b'),('squeegee',r'\b(?:limpiacristales|rasqueta|raclette|squeegee)\b'),('bulb',r'\b(?:bombillas?|bulbs?)\b'),('lamp',r'\b(?:lamparas?|lamps?)\b')]
def extract(title,spec=''):
 text=title+' | '+spec;head=re.split(r'\b(?:para|compatible|for|pour)\b',fold(title),maxsplit=1)[0]
 hits=[(m.start(),family) for family,pattern in FAMILIES if (m:=re.search(pattern,head))]
 family=min(hits)[1] if hits else None
 role='accessory' if re.search(r'\b(?:filtros?|recambios?|repuestos?|replacement|accessories)\b',head) else 'unknown'
 attrs={};evidence={}
 patterns={'model':r'\b(?:CR[- ]?\d{4}|LR\d{2}|AAA|AA)\b','voltage':r'(\d+(?:[.,]\d+)?)\s*(?:V\b|voltios?\b)','levels':r'(\d+)\s*(?:niveles?|pisos?|baldas?|layers?|shelves|etages?)\b','count':r'(\d+)\s*(?:unidades?|piezas?|units?|pieces?)\b','dimensions':r'(\d+(?:[.,]\d+)?\s*[x×]\s*\d+(?:[.,]\d+)?(?:\s*[x×]\s*\d+(?:[.,]\d+)?)?)\s*(cm|mm)\b','capacity':r'(\d+(?:[.,]\d+)?)\s*(ml|litros?|litres?|l)\b','chemistry':r'\b(?:alcalin[ao]s?|litio|lithium|NiMH)\b'}
 for key,pattern in patterns.items():
  ms=list(re.finditer(pattern,text,re.I));values=[]
  for m in ms:
   value=m.group(0).upper().replace('CR-','CR').replace('CR ','CR') if key=='model' else fold(m.group(1)).replace(',','.') if key not in ['chemistry'] else fold(m.group(0))
   if key=='dimensions':value=tuple(round(float(x.strip().replace(',','.'))*(.1 if m.group(2).lower()=='mm' else 1),6) for x in re.split('[x×]',m.group(1)))
   if key=='capacity':value=float(m.group(1).replace(',','.'))*(1000 if m.group(2).lower()!='ml' else 1)
   if value not in values:values.append(value)
  if values:attrs[key]=values;evidence[key]=[m.group(0) for m in ms]
 return dict(family=family,role=role,attributes=attrs,evidence=evidence,source_conflicts=[k for k,v in attrs.items() if len(v)>1 and k in ['model','voltage','capacity']])

KEYS={'battery':['model','voltage','chemistry','count'],'shelf':['levels','dimensions'],'knife':['count'],'box':['capacity','dimensions','count'],'vacuum':[],'squeegee':[],'bulb':['voltage'],'lamp':[]}
def verify(a,b):
 conflicts=[];unknown=[]
 different=a['family'] and b['family'] and a['family']!=b['family']
 if different:conflicts.append('SUBJECT_FAMILY_DIFFERENT')
 if a['role']!=b['role'] and 'accessory' in [a['role'],b['role']]:unknown.append('WHOLE_ACCESSORY_SCOPE_UNCONFIRMED')
 for k in KEYS.get(a['family'],[]):
  x=a['attributes'].get(k);y=b['attributes'].get(k)
  if not x or not y:unknown.append(k)
  elif x!=y:conflicts.append(k)
 source_conflict=bool(a['source_conflicts'] or b['source_conflicts'])
 return dict(input=a,reference=b,conflicts=conflicts,unknown=unknown,block_same_type=bool(different),
  evidence_status='来源存在冲突' if source_conflict else '关键属性未知' if unknown or not a['family'] else '有部分证据' if conflicts else '关键属性已核实',version=VERSION)
