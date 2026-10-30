"""Opt-in, unapproved knowledge experiments; never loaded by the default engine.

Return literal evidence and isolated projections, not approved knowledge or Gold.
"""
import copy,re
from runtime.retail.attributes import extract,fold,package
from runtime.retail import match10

VERSION='knowledge-trial-v322-1'

def package_evidence(title):
 text=fold(title)
 # Explicit heterogeneous composition takes precedence over a total piece count.
 patterns=[r'\bcuchillos?\b.*\b(?:y|con)\s+(?:un\s+)?(?:soporte|taco|afilador)\b',
           r'\blapices\b.*\bcon\s+(?:un\s+)?pincel\b']
 if any(re.search(p,text) for p in patterns):
  return dict(shape='MAIN_WITH_ACCESSORY',mixed=True,span=title,rule='EXPLICIT_MAIN_AND_ACCESSORY')
 return dict(shape=package(title),mixed=False,span=None,rule=None)

def quantity_evidence(title):
 """Keep unit hierarchy. A literal inner pack count is never a total sale count."""
 text=fold(title);out=dict(count=None,inner_count=None,packs=None,state='UNKNOWN',evidence=[],authority='SHADOW_LITERAL_NOT_APPROVED')
 nested=re.search(r'\b(\d+)\s*packs?\s*[x×]\s*(\d+)\s*(?:uds?\.?|unidades?)\b',text)
 if nested:
  packs,inner=map(int,nested.groups());out.update(packs=packs,inner_count=inner,evidence=[nested.group(0)],state='NESTED_PACK_REQUIRES_TOTAL')
  total=re.search(r'\b(\d+)\s+(?:toallitas|panuelos|servilletas|unidades|piezas)\b',text[:nested.start()])
  if total and int(total.group(1))==packs*inner:out.update(count=int(total.group(1)),state='EXPLICIT_TOTAL_CROSSCHECKED');out['evidence'].append(total.group(0))
  return out
 if package_evidence(title)['mixed']:
  out['state']='MIXED_PIECE_TOTAL_NOT_SUBJECT_COUNT';return out
 patterns=[r'\b(\d+)\s*uds?\.?\b',r'\b(?:pack|paquete)\s+de\s+(\d+)\b']
 found=[]
 for pattern in patterns:
  for m in re.finditer(pattern,text):
   # Compatibility/accessory counts do not establish the number being sold.
   before=text[max(0,m.start()-60):m.start()]
   if re.search(r'\b(?:compatible(?:s)?\s+con|para)\s*$',before):continue
   tail=text[m.end():m.end()+28]
   if re.match(r'\s*(?:ml|litros?|gramos?|g|kg|cm|mm)\b',tail):continue
   found.append((int(m.group(1)),m.group(0)))
 values={v for v,_ in found}
 if len(values)==1:out.update(count=next(iter(values)),state='EXPLICIT_UNIT_EXPRESSION',evidence=list(dict.fromkeys(s for _,s in found)))
 elif len(values)>1:out.update(state='CONFLICTING_OR_NESTED_COUNTS',evidence=[s for _,s in found])
 return out

def aliases(title):
 text=fold(title);queries=[]
 if re.search(r'\btijeras?\b',text) and not re.search(r'\b(?:puerta|elevador|elevadora|plataforma|gato)\b',text):
  queries.append(re.sub(r'\btijeras\b','tijera',text) if re.search(r'\btijeras\b',text) else re.sub(r'\btijera\b','tijeras',text))
 if re.search(r'\b(?:alfombra|alfombrilla)\b',text) and re.search(r'\bbano\b',text) and not re.search(r'\b(?:raton|coche|automovil|escalera)\b',text):
  queries.append(re.sub(r'\balfombrilla\b','alfombra',text) if re.search(r'\balfombrilla\b',text) else re.sub(r'\balfombra\b','alfombrilla',text))
 return queries

def commodity_head(span,catalog):
 """Reuse the frozen vocabulary/word normalization; do not learn a new taxonomy."""
 catalog._load_retriever()
 prefix=re.split(r'\b(?:de|para|con)\b',fold(span),maxsplit=1)[0]
 words=catalog._words(prefix)
 return next((w for w in words if w in catalog._head_vocabulary),'')

def project(source,analysis,candidates,refs,method,baseline):
 """Apply only explicit source-bound QA changes to existing model pairs.

 Newly retrieved candidates remain unscored unless actually analyzed separately.
 """
 adjusted=copy.deepcopy(baseline.get('effective_analysis') or analysis)
 original={p['sku']:p for p in analysis['pairs']};changes=[]
 shape=package_evidence(source['title_original']);quantity=quantity_evidence(source['title_original'])
 for p in adjusted['pairs']:
  if shape['mixed'] and original[p['sku']]['scope']=='COMPONENT' and p['scope']=='WHOLE':
   p['scope']='COMPONENT';changes.append(dict(sku=p['sku'],field='scope',before='WHOLE',after='COMPONENT',rule='EXPLICIT_MAIN_AND_ACCESSORY'))
 result=match10.project(source,adjusted,candidates,refs,method,'UNAPPROVED_SHADOW_OFFLINE_PROJECTION_NOT_NEW_MODEL')
 result.update(shadow=True,knowledge_approved=False,shadow_changes=changes,quantity_hypothesis=quantity,package_hypothesis=shape)
 return result
