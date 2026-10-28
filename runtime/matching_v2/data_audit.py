"""Read-only XLSX audit. Observation history is never forward-filled."""
from __future__ import annotations
import collections, hashlib, json, math, re, unicodedata
from pathlib import Path
from decimal import Decimal, InvalidOperation
import openpyxl

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def text(value):
    return '' if value is None else str(value)

def norm(value):
    return ' '.join(unicodedata.normalize('NFKC',text(value)).lower().split())

def price(raw, number_format=''):
    """Currency needs explicit evidence. Ambiguous separators remain invalid."""
    evidence=text(raw)+' '+number_format
    currencies={cur for cur,pattern in [('EUR',r'€|\bEUR\b'),('USD',r'US\$|\bUSD\b'),('GBP',r'£|\bGBP\b')] if re.search(pattern,evidence,re.I)}
    currency=next(iter(currencies)) if len(currencies)==1 else None
    if raw is None or text(raw).strip()=='':return {'raw':raw,'value':None,'currency':currency,'status':'MISSING','number_format':number_format}
    s=re.sub(r'€|EUR|USD|GBP|US\$|£','',text(raw),flags=re.I).strip()
    if isinstance(raw,bool):s='invalid'
    if ',' in s and '.' in s:
        if re.fullmatch(r'\d{1,3}(?:\.\d{3})+,\d{2}',s):s=s.replace('.','').replace(',','.')
        elif re.fullmatch(r'\d{1,3}(?:,\d{3})+\.\d{2}',s):s=s.replace(',','')
        else:s='invalid'
    elif ',' in s:
        s=s.replace(',','.') if re.fullmatch(r'\d+,\d{1,2}',s) else 'invalid'
    try:
        number=float(Decimal(s))
        if not math.isfinite(number) or number<=0:raise ValueError()
    except (InvalidOperation,ValueError):number=None
    return {'raw':raw,'value':number,'currency':currency,'status':'VALID' if number is not None else 'INVALID','number_format':number_format}

def quantity_evidence(value):
    """Literal evidence only, never a count inferred from an unspecified single."""
    return [{'raw':m.group(0),'value':float(m.group(1).replace(',','.')),'unit_raw':m.group(2)} for m in re.finditer(r'(?<![\w.,])(\d+(?:[.,]\d+)?)\s*(ml|litros?|l|kg|gramos?|g|cm|mm|metros?|m|unidades?|piezas?|uds?\.?|conteo)\b',text(value),re.I)]

def flags(title,spec,details,url,asin):
    result=[]
    if not title:result.append('TITLE_MISSING')
    if not re.fullmatch(r'[A-Z0-9]{10}',asin):result.append('ASIN_INVALID')
    url_asin=re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})',url,re.I)
    if url_asin and url_asin.group(1).upper()!=asin:result.append('URL_ASIN_MISMATCH')
    if not url_asin:result.append('URL_ASIN_UNCONFIRMED')
    for label,value in [('TITLE',title),('SPEC',spec),('DETAILS',details)]:
        if re.search(r'[\u3400-\u9fff]',value):result.append(label+'_CJK')
        if re.search(r'\ufffd|Ã.|Â.|â€',value):result.append(label+'_ENCODING_SUSPECT')
        if re.search(r'P\.when\(|function\s*\(|<script|window\.ue',value):result.append(label+'_SCRIPT_RESIDUAL')
        if len(re.findall(r'\b(?:Brand Name|Item Weight|Product Dimensions|Special Features|Number of Items|Colour|Material Type|with|for|and)\b',value,re.I))>=3:result.append(label+'_ENGLISH_SUSPECT')
    # Duplicate explicit attribute keys with different values are candidates,
    # not confirmed contradictions (package/product dimensions may coexist).
    attrs=collections.defaultdict(set)
    for segment in re.split(r';|\n',details):
        if ':' in segment:
            k,v=segment.split(':',1);k=norm(re.sub(r'^\[[^]]+\]\s*','',k))
            if k and len(k)<80 and v.strip():attrs[k].add(norm(v))
    if any(len(v)>1 for v in attrs.values()):result.append('DUPLICATE_ATTRIBUTE_VALUES_REVIEW')
    return result

def read_amazon(path,snapshot_date):
    p=Path(path);sha=digest(p);w=openpyxl.load_workbook(p,read_only=True,data_only=True);records=[];mapping=[]
    for sheet in w:
        it=sheet.iter_rows();head=next(it,None)
        if not head:continue
        headers=[text(c.value).strip() for c in head]
        if 'ASIN' not in headers:continue
        def find(exact=None,prefix=None):
            return next((i for i,h in enumerate(headers) if h==exact or (prefix and h.startswith(prefix))),None)
        cols={'asin':find('ASIN'),'parent_asin':find('Parent ASIN'),'title':find(prefix='商品名称'),'brand':find('品牌'),'price':find('当前售价'),'list_price':find('划线原价'),'category1':find('一级类目'),'category2':find('二级类目'),'category3':find('三级类目'),'spec':find(prefix='核心规格'),'variant':find(prefix='当前选中规格'),'details':find(prefix='完整商品详情'),'bullets':find(prefix='商品卖点'),'url':find('商品链接')}
        if any(cols[k] is None for k in ('asin','title','price','url')):raise ValueError('REQUIRED_HEADER_MISSING:'+str(p))
        mapping.append({'sheet':sheet.title,'headers':headers,'columns':cols})
        for rowno,row in enumerate(it,2):
            def get(k):
                i=cols[k];return row[i].value if i is not None and i<len(row) else None
            if not any(get(k) is not None for k in ('asin','title','url')):continue
            r={k:text(get(k)).strip() for k in cols if k not in ('price','list_price')}
            for k in ('price','list_price'):
                i=cols[k];r[k]=price(get(k),row[i].number_format if i is not None and i<len(row) else '')
            r.update(source_file=str(p),source_sha256=sha,sheet=sheet.title,source_row=rowno,source_date=snapshot_date,source_date_basis='FILENAME_SNAPSHOT_DATE_NOT_CAPTURE_TIMESTAMP',captured_at=None,price_time=None)
            r['record_id']=hashlib.sha256(f'{sha}:{sheet.title}:{rowno}'.encode()).hexdigest()[:24]
            r['flags']=flags(r['title'],r['spec'],r['details'],r['url'],r['asin'])
            if r['price']['status']!='VALID':r['flags'].append('PRICE_'+r['price']['status'])
            if not r['price']['currency']:r['flags'].append('PRICE_CURRENCY_UNKNOWN')
            if not r['category1']:r['flags'].append('CATEGORY_MISSING')
            r['quantity_evidence']=quantity_evidence(r['title']+'\n'+r['spec'])
            r['pack_count']=None
            r['promotion_status']='REFERENCE_PRICE_PRESENT_NOT_PROMOTION_VERIFIED' if get('list_price') is not None else 'UNKNOWN'
            records.append(r)
    w.close()
    return records,{'path':str(p),'sha256':sha,'mapping':mapping,**summarize(records)}

def summarize(records):
    return {'records':len(records),'unique_asins':len({r['asin'] for r in records if re.fullmatch(r'[A-Z0-9]{10}',r['asin'])}),'unique_urls':len({r['url'] for r in records if r['url']}),'title_nonempty':sum(bool(r['title']) for r in records),'valid_price':sum(r['price']['status']=='VALID' for r in records),'currency_counts':dict(collections.Counter(r['price']['currency'] or 'UNKNOWN' for r in records)),'spec_nonempty':sum(bool(r['spec']) for r in records),'variant_nonempty':sum(bool(r['variant']) for r in records),'literal_quantity_present':sum(bool(r['quantity_evidence']) for r in records),'flags':dict(collections.Counter(f for r in records for f in r['flags']))}

def history(records):
    groups=collections.defaultdict(list)
    for r in records:
        if re.fullmatch(r'[A-Z0-9]{10}',r['asin']):groups[r['asin']].append(r)
    result=[]
    for asin,rows in sorted(groups.items()):
        rows=sorted(rows,key=lambda r:(r['source_date'],r['record_id']))
        newest=[r for r in rows if r['source_date']==rows[-1]['source_date']]
        result.append({'asin':asin,'observations':rows,'latest_date':rows[-1]['source_date'],'latest_record_ids':[r['record_id'] for r in newest],'ambiguous_latest':len(newest)>1,'price_changed':len({(r['price']['value'],r['price']['currency']) for r in rows if r['price']['value'] is not None})>1,'title_changed':len({r['title'] for r in rows if r['title']})>1,'category_changed':len({(r['category1'],r['category2'],r['category3']) for r in rows})>1})
    return result

def read_action(path,snapshot_date,eligible):
    p=Path(path);sha=digest(p);w=openpyxl.load_workbook(p,read_only=True,data_only=True);records=[]
    for s in w:
        it=s.iter_rows();head=next(it,None)
        if not head:continue
        aliases={'当前售价':'折后价','促销原价':'原价'}
        headers=[aliases.get(re.sub(r'（西语）$','',text(c.value)),re.sub(r'（西语）$','',text(c.value))) for c in head]
        if '编号' not in headers or '标题' not in headers:continue
        for rowno,row in enumerate(it,2):
            cells={h:row[i] for i,h in enumerate(headers) if i<len(row)}
            def get(h):return cells[h].value if h in cells else None
            sku=text(get('编号'))
            if sku not in eligible:continue
            title=text(get('标题'));unit=text(get('单价'));fmt=cells['折后价'].number_format if '折后价' in cells else ''
            quote=price(get('折后价'),fmt)
            if not quote['currency'] and '€' in unit:quote['currency']='EUR';quote['currency_evidence']='EXPLICIT_SAME_ROW_UNIT_PRICE_EURO'
            records.append({'sku':sku,'title':title,'frozen_title':eligible[sku]['name_es_original'],'title_binding_exact':title==eligible[sku]['name_es_original'],'category1':text(get('分类1')),'category2':text(get('分类2')),'spec':text(get('规格')),'details':text(get('产品详情')),'price':quote,'list_price':price(get('原价')),'unit_price_raw':unit,'url':text(get('商品链接')),'country':'ES' if '/es-es/' in text(get('商品链接')) else None,'promotion_note_raw':text(get('备注')),'source_file':str(p),'source_sha256':sha,'source_row':rowno,'source_date':snapshot_date,'captured_at':None,'price_time':None,'quantity_evidence':quantity_evidence(text(get('规格'))),'pack_count':None})
    w.close();return records

def write_jsonl(path,rows):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf8') as f:
        for r in rows:f.write(json.dumps(r,ensure_ascii=False,default=str)+'\n')
