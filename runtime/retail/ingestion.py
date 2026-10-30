"""Lossless source identities and explicit quotes for Excel, CSV and JSONL."""
import csv,json,re
from pathlib import Path
from runtime.matching_v2.data_audit import digest,price
from runtime.v3.core import digest as object_hash

ALIASES={
 'title':['title_original','title','官方商品名（原文）','商品名称（西语）','商品名称','标题','name'],
 'id':['source_product_id','ASIN','货号','SKU','sku','编号','商品ID'],
 'price':['price_value','price','当前售价 EUR','当前售价','折后价','售价','价格'],
 'currency':['price_currency','currency','币种'],
 'spec':['specifications','spec','核心规格（西语）','规格'],
 'category':['category_original','category1','一级类目','分类1'],
 'url':['source_url','url','商品链接'],
 'date':['source_date','price_date','日期'],
 'variant':['variant','当前选中规格 / 变体（西语）'],
 'brand':['brand','品牌']}

def ingest(path,platform='auto',source_date='',currency='',price_type='unknown',limit=None):
    path=Path(path).resolve();sha=digest(path);errors=[];records=[]
    def add(raw,row,sheet='',formats=None):
        try:
            if not isinstance(raw,dict):raise ValueError('PRODUCT_ROW_MUST_BE_OBJECT')
            # Excel date cells are preserved as ISO text in the evidence record.
            raw=json.loads(json.dumps(raw,ensure_ascii=False,default=lambda v:v.isoformat() if hasattr(v,'isoformat') else str(v)))
            def key(k):return next((h for h in ALIASES[k] if h in raw),None)
            def get(k):return raw.get(key(k))
            title=str(get('title') or '').strip()
            if not title:raise ValueError('TITLE_MISSING')
            source=str(raw.get('source_platform') or (platform if platform!='auto' else 'amazon' if 'ASIN' in raw else 'ikea' if '货号' in raw and 'ikea' in str(get('url')).lower() else 'supplier'))
            pid=str(get('id') or '').strip();quote_id=object_hash([sha,sheet,row])
            if not pid:pid='source-row:'+quote_id
            val=get('price');nested_currency=val.get('currency') if isinstance(val,dict) else None
            val=val.get('raw',val.get('value')) if isinstance(val,dict) else val
            q=price(val,(formats or {}).get(key('price'),''))
            # A currency label is evidence, a country/platform alone is not.
            explicit=str(get('currency') or nested_currency or currency or ('EUR' if key('price') and 'EUR' in key('price') else '')).upper()
            if explicit and q['currency'] and explicit!=q['currency']:raise ValueError('CONFLICTING_CURRENCY_EVIDENCE')
            q['currency']=explicit or q['currency']
            dt=str(get('date') or source_date or '')
            record=dict(internal_product_id=object_hash([source,pid]),source_platform=source,source_product_id=pid,
                quote_id=quote_id,source_url=str(get('url') or ''),source_file=str(path),source_sha256=sha,source_row=row,source_sheet=sheet,
                source_date=dt,title_original=title,title_language=str(raw.get('title_language') or 'unknown'),brand=str(get('brand') or ''),
                category_original=str(get('category') or ''),category_normalized=None,product_type=None,sold_subject=None,
                specifications=str(get('spec') or ''),variant=str(get('variant') or ''),package_quantity=None,
                price_value=q['value'],price_currency=q['currency'],price_type=str(raw.get('price_type') or price_type),price_date=dt,
                price=q,source_evidence=raw,unknown_fields=[])
            record['unknown_fields']=[k for k in ['brand','source_date','price_currency','specifications','package_quantity'] if not record.get(k)]
            records.append(record)
        except (ValueError,TypeError) as e:errors.append(dict(source_row=row,sheet=sheet,error=str(e)))
    if path.suffix.lower()=='.xlsx':
        import openpyxl
        w=openpyxl.load_workbook(path,read_only=True,data_only=True)
        for sh in w:
            it=sh.iter_rows();head=next(it,[]);names=[str(c.value or '').strip() for c in head]
            if not any(a in names for a in ALIASES['title']):continue
            for rowno,cells in enumerate(it,2):
                if limit and len(records)>=limit:break
                if not any(c.value is not None for c in cells):continue
                add({h:c.value for h,c in zip(names,cells)},rowno,sh.title,{h:c.number_format for h,c in zip(names,cells)})
        w.close()
    elif path.suffix.lower()=='.csv':
        with path.open(encoding='utf-8-sig',newline='') as f:
            for i,r in enumerate(csv.DictReader(f),2):
                if limit and len(records)>=limit:break
                add(r,i)
    elif path.suffix.lower()=='.jsonl':
        for i,line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(),1):
            if limit and len(records)>=limit:break
            if not line.strip():continue
            try:add(json.loads(line),i)
            except ValueError:errors.append(dict(source_row=i,error='INVALID_JSON'))
    else:raise ValueError('INPUT_FORMAT_REQUIRES_XLSX_CSV_JSONL')
    if not records:raise ValueError('NO_VALID_PRODUCT_ROWS')
    return records,errors
