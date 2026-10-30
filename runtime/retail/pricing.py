"""Platform-neutral quote identity; reuse V2.1 literal units and price layers."""
from datetime import date
import math
from runtime.matching_v2.price_layers import layers

def valid(record,hashes):
    reasons=[];v=record.get('price_value')
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0:reasons.append('PRICE_MISSING_OR_INVALID')
    if not record.get('price_currency'):reasons.append('CURRENCY_UNKNOWN')
    if not record.get('source_sha256') or hashes.get(record.get('source_file'))!=record.get('source_sha256'):reasons.append('SOURCE_HASH_UNVERIFIED')
    if not record.get('source_product_id'):reasons.append('SOURCE_ID_MISSING')
    try:date.fromisoformat(record.get('price_date',''))
    except (ValueError,TypeError):reasons.append('QUOTE_DATE_UNKNOWN')
    if record.get('binding_valid') is False:reasons.append('REFERENCE_SOURCE_BINDING_MISMATCH')
    return {'valid':not reasons,'reasons':reasons}

def compare(a,b,relation,hashes):
    # Field aliases do not fabricate ASINs or cross-platform identity.
    def adapt(r):return {**r,'title':r['title_original'],'spec':r['specifications']} if r else None
    def validator(r,hs,side):
        if not r:return dict(valid=False,reasons=['REFERENCE_QUOTE_MISSING'])
        return {**valid(r,hs),'value':r['price_value'],'currency':r['price_currency'],'snapshot_date':r['price_date']}
    shared=layers(adapt(a),adapt(b),dict(relation=relation,spec_status='UNKNOWN'),hashes,quote_validator=validator)
    result={'L1_source':shared['L1']['amazon'],'L1_reference':shared['L1']['action'],
            'L2':shared['L2'],'L3':shared['L3'],'identity_unchanged':relation,'limitations':shared['L3']['limitations']}
    result['L2']['ratio']=result['L2']['asking_price_ratio'];result['L3']['ratio']=result['L3']['unit_price_ratio']
    if not b or a['price_type']!='retail' or b['price_type']!='retail':
        for key in ['L2','L3']:
            result[key]['eligible']=False;result[key]['reasons'].append('RETAIL_WHOLESALE_OR_UNKNOWN_BASIS');result[key]['ratio']=None
        result['L2']['asking_price_ratio']=None
        for key in ['amazon_per_base','action_per_base','unit_price_ratio','amazon_per_100ml_or_100g','action_per_100ml_or_100g']:
            if key in result['L3']:result['L3'][key]=None
    return result
