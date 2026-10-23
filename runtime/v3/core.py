"""Source-bound semantics and operating decisions are separate dimensions."""
from __future__ import annotations
import hashlib,json,re

VERSION='v3.0-candidate'
LABELS={'保留','观察','用不到'}
FORMS={'ordinary_good','bundle','universal_accessory','host_component','installed_component','whole_machine','whole_system','unknown'}
RELATIONS={'same_type','related_type','specific_need','category_only','host_only','none'}
CONTEXTS={'daily','specialist','large_installation','unknown'}

def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def digest(x):return hashlib.sha256(canonical(x).encode('utf-8')).hexdigest()

def valid_reviewer(obj):return isinstance(obj.get('reviewer'),str) and bool(obj['reviewer'].strip())

def source_record(raw):
    rid=next((str(raw[k]).strip() for k in ['record_id','id','sku','SKU','asin','ASIN'] if raw.get(k) is not None and str(raw[k]).strip()),'')
    title=next((str(raw[k]).strip() for k in ['title_original','title','name_es_original','name','商品名称'] if raw.get(k) is not None and str(raw[k]).strip()),'')
    if not rid or not title:raise ValueError('SOURCE_ID_AND_TITLE_REQUIRED')
    version=str(raw.get('source_version') or raw.get('snapshot_id') or '')
    return dict(record_id=rid,title_original=title,source_version=version,
                source_hash=digest({'record_id':rid,'title_original':title,'source_version':version}))

def validate_analysis(row,a,catalog):
    if not isinstance(a,dict):raise ValueError('STRUCTURED_ANALYSIS_REQUIRED')
    if a.get('source_hash')!=row['source_hash']:raise ValueError('ANALYSIS_SOURCE_MISMATCH')
    if a.get('record_id',row['record_id'])!=row['record_id']:raise ValueError('ANALYSIS_ID_MISMATCH')
    if str(a.get('authority','')).upper() not in {'AI_CANDIDATE','AI_SOURCE_BOUND_REUSE'} or a.get('human_gold') or a.get('human_confirmed'):
        raise ValueError('INVALID_ANALYSIS_AUTHORITY')
    span=a.get('subject_span','')
    if not isinstance(span,str) or not span.strip() or span not in row['title_original']:raise ValueError('SUBJECT_SPAN_NOT_LITERAL')
    if any(not isinstance(a.get(k),str) or not a[k].strip() for k in ['subject_type','reason']):raise ValueError('SUBJECT_AND_REASON_REQUIRED')
    if a.get('form') not in FORMS or a.get('relation') not in RELATIONS:raise ValueError('INVALID_FORM_OR_RELATION')
    if a.get('coverage') not in {'subject','partial','unknown'}:raise ValueError('REFERENCE_COVERAGE_REQUIRED')
    if a.get('information_status') not in {'clear','insufficient'}:raise ValueError('INFORMATION_STATUS_REQUIRED')
    if a.get('operating_context') not in CONTEXTS:raise ValueError('INVALID_OPERATING_CONTEXT')
    for key in ['functions','needs']:
        if not isinstance(a.get(key,[]),list) or any(not isinstance(v,str) for v in a.get(key,[])):raise ValueError('INVALID_HYPOTHESIS_LIST')
    if a['form'] in {'whole_machine','whole_system'}:
        prefix=row['title_original'][:row['title_original'].index(span)]
        if re.search(r'\b(?:para|compatible\s+con|apto\s+para|de|del)\s+(?:(?:el|la|los|las|un|una)\s+)?$',prefix,re.I):raise ValueError('HOST_IS_NOT_SOLD_SUBJECT')
    sku=str(a.get('action_sku') or '')
    if a['relation']=='none':
        if sku:raise ValueError('NONE_RELATION_WITH_REFERENCE')
    else:
        ref=catalog.by_sku.get(sku)
        if not ref:raise ValueError('REFERENCE_SKU_NOT_ELIGIBLE')
        ref_title=ref.get('name_es_original') or ref.get('title','')
        ref_span=a.get('reference_span','')
        if not isinstance(ref_span,str) or not ref_span.strip() or ref_span not in ref_title:raise ValueError('REFERENCE_SPAN_NOT_LITERAL')
    return a

def context(a):return a.get('operating_context','daily' if a['form'] in {'ordinary_good','bundle','universal_accessory'} else 'unknown')

def rule_matches(rule,a):
    for key in ['subject_types','forms','operating_contexts']:
        if not isinstance(rule.get(key,[]),list) or any(not isinstance(v,str) or not v.strip() for v in rule.get(key,[])):
            raise ValueError('RULE_SCOPE_ARRAY_REQUIRED')
    return (a['subject_type'] in rule.get('subject_types',[]) and a['form'] in rule.get('forms',[]) and
            (not rule.get('operating_contexts') or context(a) in rule['operating_contexts']))

def decide(row,analysis,catalog,policy,owner=None):
    result={'record_id':row['record_id'],'source_hash':row['source_hash'],'title_original':row['title_original'],
            'decision':'观察','understanding_status':'NEEDS_SEMANTIC','operating_status':'UNASSESSED','reason_code':'SEMANTIC_NOT_EXECUTED',
            'reference':None,'policy_evidence':[],'authority':'PROGRAM_PROJECTION','human_confirmed':False,
            'method_version':VERSION,'semantic':analysis,'reason':'尚未完成实际语义分析'}
    if analysis is not None:
        a=validate_analysis(row,analysis,catalog)
        clear=a['information_status']=='clear' and a['form']!='unknown'
        result.update(understanding_status='UNDERSTOOD_CANDIDATE' if clear else 'INFORMATION_INSUFFICIENT',reason=a['reason'])
        result['operating_status']='DAILY_SCOPE_CANDIDATE' if clear and context(a)=='daily' else 'SCOPE_UNCONFIRMED'
        if a.get('action_sku'):
            ref=catalog.by_sku[str(a['action_sku'])]
            result['reference']={'sku':str(a['action_sku']),'title':ref.get('name_es_original') or ref.get('title',''),
                                 'relation':a['relation'],'source_row_id':ref.get('source_row_id','')}
        matched=[r for r in policy.get('rules',[]) if r.get('status')=='PUBLISHED' and r.get('validation_status')=='PASS' and
                 r.get('release_id') and r.get('rule_id') and r.get('decision') in LABELS and rule_matches(r,a)]
        if not clear:result.update(reason_code='INFORMATION_INSUFFICIENT',operating_status='UNDERSTANDING_PENDING')
        elif len({r['decision'] for r in matched})>1:result.update(reason_code='POLICY_CONFLICT',operating_status='POLICY_CONFLICT')
        elif matched:
            result.update(decision=matched[0]['decision'],reason_code='PUBLISHED_OPERATING_RULE',operating_status='POLICY_CONFIRMED',policy_evidence=[r['release_id'] for r in matched])
        elif a['form'] in {'host_component','installed_component'}:result.update(reason_code='DEPENDENCY_SCOPE_UNCONFIRMED',operating_status='DEPENDENCY_UNCONFIRMED')
        elif context(a)!='daily':result['reason_code']='OPERATING_SCOPE_UNCONFIRMED'
        elif a['relation'] in {'same_type','related_type','specific_need'} and a['coverage']=='subject':
            result.update(decision='保留',reason_code='DAILY_SUBJECT_WITH_BOUNDED_REFERENCE')
        else:result['reason_code']='REFERENCE_NOT_SUFFICIENT'
    if owner:
        if owner.get('authority')!='HUMAN' or not valid_reviewer(owner) or owner.get('decision') not in LABELS:raise ValueError('VALID_OWNER_DECISION_REQUIRED')
        if owner.get('record_id')!=row['record_id'] or owner.get('source_hash')!=row['source_hash']:raise ValueError('OWNER_SOURCE_MISMATCH')
        result.update(decision=owner['decision'],reason_code='EXACT_OWNER_DECISION',authority='HUMAN_SELECTION',human_confirmed=True,
                      operating_status='OWNER_EXACT_RECORD',policy_evidence=[owner.get('feedback_id','')])
    return result
