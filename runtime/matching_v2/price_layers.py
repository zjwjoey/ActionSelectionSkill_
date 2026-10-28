"""Source-bound historical prices, independent of identity scores and rankings."""
from __future__ import annotations
import math,re,unicodedata,collections
from datetime import date
from urllib.parse import urlparse

def folded(s):
    return ''.join(c for c in unicodedata.normalize('NFKD',s or '').lower() if not unicodedata.combining(c))

def number(s):
    if not re.fullmatch(r'\d+(?:[.,]\d{1,2})?',s):return None
    n=float(s.replace(',','.'));return n if n>0 and math.isfinite(n) else None

def quantity(title,spec='',variant=''):
    """Literal quantity evidence, never missing-pack=1 or physical-weight=content.

    Only sale title/spec/variant are used. Shipping dimensions and generic item
    weight cannot establish sale content. Multi-format disagreements abstain.
    """
    fields={'title':title or '', 'spec':spec or '', 'variant':variant or ''}
    evidence=[];counts=[];measures=[];conflicts=[];dims=[]
    all_text=folded('\n'.join(fields.values()))
    bundle=bool(re.search(r'\b(?:kit|juego|set|conjunto)\b',folded(title)))
    # A capacity on a durable container is not consumable volume.
    consumable=bool(re.search(r'\b(?:pintura|detergente|suavizante|champu|jabon|gel|crema|aceite|limpiador|desinfectante|bebida|leche|zumo|refresco|cafe|harina|azucar|sal|cera|pegamento|cola|adhesivo)\b',folded(title)))
    container=bool(re.search(r'\b(?:botella|recipiente|dispensador|pulverizador|jarra|taza|vaso|bote|cubo|cafetera|espumador|deposito|cartucho vacio)\b',folded(title)))
    host=bool(re.search(r'\b(?:compatible|repuesto|recambio|soporte|funda|molde|cepillo)\b',folded(title)))
    mass_volume_allowed=consumable and not container and not host
    units=r'(ml|mililitros?|l|litros?|kg|kilogramos?|g|gr|gramos?)'
    count_units=r'(?:unidades?|piezas?|capsulas?|pastillas?|pilas|rollos|bolsas|toallitas|panuelos|perchas|velas|protectores)'
    for field,raw in fields.items():
        t=folded(raw)
        # Preserve dimension evidence separately, including package dimensions.
        for m in re.finditer(r'\d+(?:[.,]\d+)?\s*[x×]\s*\d+(?:[.,]\d+)?(?:\s*[x×]\s*\d+(?:[.,]\d+)?)?\s*(?:mm|cm|metros?)\b',t):
            dims.append({'field':field,'span_folded':m.group(),'scope':'PACKAGE' if re.search(r'paquete|embalaje|package',t[max(0,m.start()-45):m.start()]) else 'UNRESOLVED_AXES'})
        skip=[]
        for m in re.finditer(r'\b(\d+)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*'+units+r'\b',t):
            n=number(m.group(2));unit=m.group(3)
            if n is None or int(m.group(1))<=0:conflicts.append('AMBIGUOUS_OR_NONPOSITIVE_NUMBER');continue
            base='litre' if unit.startswith(('l','mil')) or unit=='ml' else 'kg'
            value=int(m.group(1))*n/(1000 if unit in ['ml','g','gr'] or unit.startswith(('mil','gram')) else 1)
            measures.append((base,value,'EXPLICIT_MULTIPACK_TOTAL',field,m.group()));skip.append(m.span())
            counts.append((int(m.group(1)),field,m.group()))
        for m in re.finditer(r'(?<![\w.,])(\d+(?:[.,]\d+)?)\s*'+units+r'\b',t):
            if any(a<=m.start()<b for a,b in skip):continue
            before=t[max(0,m.start()-45):m.start()]
            if re.search(r'(?:peso|weight|dimensiones|dimensions|embalaje|package)',before):continue
            n=number(m.group(1));unit=m.group(2)
            if n is None:conflicts.append('AMBIGUOUS_NUMBER');continue
            base='litre' if unit.startswith(('l','mil')) or unit=='ml' else 'kg'
            value=n/(1000 if unit in ['ml','g','gr'] or unit.startswith(('mil','gram')) else 1)
            measures.append((base,value,'DECLARED_CONTENT',field,m.group()))
        for m in re.finditer(r'\b(\d+)\s*[x×]\s*(\d+)\s*'+count_units+r'\b',t):
            product=int(m.group(1))*int(m.group(2));skip.append(m.span())
            if product>0:counts.append((product,field,m.group()))
            else:conflicts.append('NONPOSITIVE_SALE_COUNT')
        for m in re.finditer(r'\b(\d+)\s*'+count_units+r'\b',t):
            if any(a<=m.start()<b for a,b in skip):continue
            if int(m.group(1))>0:counts.append((int(m.group(1)),field,m.group()))
        for m in re.finditer(r'\b(?:pack|paquete|lote)\s*(?:de\s*)?(\d+)\b',t):
            if int(m.group(1))>0:counts.append((int(m.group(1)),field,m.group()))
    count_values={n for n,_,_ in counts}
    if len(count_values)>1:conflicts.append('CONFLICTING_COUNTS')
    count=next(iter(count_values)) if len(count_values)==1 else None
    pack_mentioned=bool(re.search(r'\b(?:pack|paquete|lote)\b',all_text))
    bases={b for b,_,_,_,_ in measures};totals=[]
    if len(bases)>1:conflicts.append('MULTIPLE_MEASUREMENT_BASES')
    explicit_totals={round(v,9) for _,v,mode,_,_ in measures if mode=='EXPLICIT_MULTIPACK_TOTAL'}
    declared={round(v,9) for _,v,mode,_,_ in measures if mode=='DECLARED_CONTENT'}
    base=next(iter(bases)) if len(bases)==1 else None
    total=None;basis=None
    if explicit_totals:
        if len(explicit_totals)==1:
            total=next(iter(explicit_totals));basis='EXPLICIT_MULTIPACK_TOTAL'
            if any(v!=total and (count is None or abs(v*count-total)>1e-8) for v in declared):conflicts.append('CONFLICTING_CONTENT')
        else:conflicts.append('CONFLICTING_CONTENT')
    elif len(declared)==1:
        total=next(iter(declared));basis='DECLARED_SALE_CONTENT_NO_INFERRED_PACK_COUNT'
        if pack_mentioned and count is None:conflicts.append('MULTIPACK_COUNT_UNKNOWN')
        if count is not None and count>1:
            if re.search(r'\btotal(?:es)?\b',all_text):basis='EXPLICIT_TOTAL_CONTENT'
            elif re.search(r'\b(?:cada|por unidad)\b',all_text):
                total*=count;basis='DECLARED_EACH_CONTENT_TIMES_EXPLICIT_PACK'
            else:conflicts.append('TOTAL_VS_EACH_UNRESOLVED')
    elif len(declared)>1:conflicts.append('CONFLICTING_CONTENT')
    if bundle:conflicts.append('BUNDLE_UNIT_GRANULARITY_UNCONFIRMED')
    if base and mass_volume_allowed and not conflicts:
        unit=base;amount=total
    elif count is not None and not conflicts:
        unit='item';amount=float(count);basis='EXPLICIT_SALE_COUNT'
    else:unit=None;amount=None
    for b,n,mode,f,span in measures:evidence.append({'field':f,'span_folded':span,'base':b,'value':n,'interpretation':mode})
    for n,f,span in counts:evidence.append({'field':f,'span_folded':span,'base':'item','value':n,'interpretation':'LITERAL_COUNT'})
    reasons=list(dict.fromkeys(conflicts))
    if amount is None:reasons.append('NO_SAFE_SALE_QUANTITY')
    if base and not mass_volume_allowed:reasons.append('CAPACITY_OR_WEIGHT_NOT_CONFIRMED_CONSUMABLE_CONTENT')
    return {'base':unit,'amount':amount,'basis':basis,'explicit_pack_count':count,'evidence':evidence,'dimensions':dims,'reasons':reasons,'consumable_content_cue':mass_volume_allowed,'bundle_cue':bundle,'raw_fields':fields}

def valid_quote(record,source_hashes,side):
    reasons=[]
    if not record:return {'valid':False,'reasons':['SOURCE_RECORD_MISSING'],'side':side}
    p=record.get('price',{});n=p.get('value')
    if isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) or n<=0:reasons.append('POSITIVE_NUMERIC_PRICE_MISSING')
    if not p.get('currency'):reasons.append('EXPLICIT_CURRENCY_MISSING')
    if not record.get('url'):reasons.append('SOURCE_URL_MISSING')
    if not record.get('source_sha256') or source_hashes.get(record.get('source_file'))!=record.get('source_sha256'):reasons.append('SOURCE_FILE_HASH_UNVERIFIED')
    try:date.fromisoformat(record.get('source_date',''))
    except (ValueError,TypeError):reasons.append('SNAPSHOT_DATE_UNKNOWN')
    if side=='Action':
        if not record.get('title_binding_exact'):reasons.append('FROZEN_TITLE_BINDING_UNCONFIRMED')
        match=re.search(r'/es-es/p/(\d+)/',record.get('url',''))
        if urlparse(record.get('url','')).hostname not in ['action.com','www.action.com'] or not match or match.group(1)!=str(record.get('sku','')):reasons.append('ACTION_SKU_URL_BINDING_UNCONFIRMED')
    if side=='Amazon':
        match=re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})',record.get('url',''),re.I)
        if not match or match.group(1).upper()!=record.get('asin'):reasons.append('ASIN_URL_BINDING_UNCONFIRMED')
    return {'side':side,'valid':not reasons,'reasons':reasons,'value':n,'currency':p.get('currency'),'raw':p.get('raw'),'snapshot_date':record.get('source_date'),'price_time':record.get('price_time'),'date_basis':'EXPORT_SNAPSHOT_NOT_PRECISE_QUOTE_TIME','promotion':record.get('promotion_status',record.get('promotion_note_raw','UNKNOWN')),'source_file':record.get('source_file'),'source_sha256':record.get('source_sha256'),'source_row':record.get('source_row'),'url':record.get('url')}

def layers(amazon,action,pair,source_hashes,subject_clear=True):
    qa=valid_quote(amazon,source_hashes,'Amazon');qb=valid_quote(action,source_hashes,'Action')
    q1=quantity(amazon['title'],amazon.get('spec',''),amazon.get('variant',''))
    q2=quantity(action['title'],action.get('spec','')) if action else quantity('')
    reasons=[]
    if not qa['valid']:reasons.append('AMAZON_L1_INVALID')
    if not qb['valid']:reasons.append('ACTION_L1_INVALID')
    if qa.get('currency') and qb.get('currency') and qa['currency']!=qb['currency']:reasons.append('CURRENCIES_DIFFER')
    if pair['relation'] not in ['IDENTICAL','SAME_TYPE']:reasons.append('TYPE_BASIS_NOT_ESTABLISHED')
    if not subject_clear:reasons.append('SOLD_SUBJECT_UNCLEAR')
    days=None
    if qa.get('snapshot_date') and qb.get('snapshot_date'):
        try:days=abs((date.fromisoformat(qa['snapshot_date'])-date.fromisoformat(qb['snapshot_date'])).days)
        except (ValueError,TypeError):pass
    bucket='UNKNOWN' if days is None else 'SAME_DAY' if days==0 else '1_7_DAYS' if days<=7 else '8_30_DAYS' if days<=30 else 'OVER_30_DAYS'
    l2={'eligible':not reasons,'reasons':reasons,'asking_price_ratio':qa['value']/qb['value'] if not reasons else None,'date_gap_days':days,'date_bucket':bucket,'grade':'HISTORICAL_DISPLAY_PRICE_NOT_EQUIVALENT_UNIT_VALUE' if not reasons else 'UNAVAILABLE','limitations':['Not identity proof; not a value-for-money judgment','Type relation is an existing AI candidate, not independent fact label','Different quality, specification, pack and promotion may affect ratio','Snapshot dates are not verified simultaneous quotes'],'spec_status_preserved':pair['spec_status']}
    unit_reasons=list(reasons)
    if q1['amount'] is None:unit_reasons.append('AMAZON_SALE_QUANTITY_UNCONFIRMED')
    if q2['amount'] is None:unit_reasons.append('ACTION_SALE_QUANTITY_UNCONFIRMED')
    if q1['base'] and q2['base'] and q1['base']!=q2['base']:unit_reasons.append('MEASUREMENT_BASE_DIFFERS')
    l3={'eligible':not unit_reasons,'reasons':unit_reasons,'base':q1['base'] if not unit_reasons else None,'amazon_per_base':None,'action_per_base':None,'unit_price_ratio':None,'amazon_quantity':q1,'action_quantity':q2,'authority':'SOURCE_ARITHMETIC_AND_AI_TYPE_CANDIDATE_NOT_GOLD','date_bucket':bucket,'limitations':['Normalized amount does not establish equal quality, formulation, dimensions, performance or identity']}
    if not unit_reasons:
        l3['amazon_per_base']=qa['value']/q1['amount'];l3['action_per_base']=qb['value']/q2['amount'];l3['unit_price_ratio']=l3['amazon_per_base']/l3['action_per_base']
        if q1['base'] in ['litre','kg']:
            l3['amazon_per_100ml_or_100g']=l3['amazon_per_base']/10;l3['action_per_100ml_or_100g']=l3['action_per_base']/10
    return {'L1':{'amazon':qa,'action':qb,'both_valid':qa['valid'] and qb['valid']},'L2':l2,'L3':l3,'identity_relation_unchanged':pair['relation'],'score_unchanged':True}

def price_history(groups):
    totals=collections.Counter();results=[]
    for g in groups:
        rs=g['observations'];valid=[r for r in rs if r['price']['value'] is not None]
        values={r['price']['value'] for r in valid};currencies={r['price']['currency'] for r in valid}
        numeric=len(values)>1;currency=len(currencies)>1
        if len(valid)<2:status='INSUFFICIENT_VALID_OBSERVATIONS'
        elif numeric and currency:status='BOTH_NUMERIC_AND_CURRENCY_EVIDENCE_CHANGED'
        elif numeric:status='NUMERIC_ONLY_CHANGED'
        elif currency:status='CURRENCY_EVIDENCE_ONLY_CHANGED'
        else:status='NO_OBSERVED_CHANGE'
        unknown=any(r['price']['value'] is None or r['price']['currency'] is None for r in rs) or len(valid)<2
        totals[status]+=1
        if unknown:totals['ECONOMIC_PRICE_CHANGE_UNRESOLVED']+=1
        results.append({'asin':g['asin'],'classification':status,'numeric_changed':numeric,'currency_evidence_changed':currency,'economic_change_unresolved':unknown,'observations':len(rs)})
    return {'counts':dict(totals),'definitions':'Numeric cell changes and currency evidence are distinct; unresolved economic change is overlapping, not an extra disjoint group'},results
