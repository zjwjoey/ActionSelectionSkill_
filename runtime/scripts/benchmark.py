"""P1.1 candidate/gold separation in the shared learning database."""
import argparse
import csv
import json
import re

import storage
from pipeline import ROOT,FIELDS,canonical,digest,immutable,read_jsonl,validate_annotation,normalize_name,MULTI

PHASE='P1.1-20261022'


def schema(root):
    with storage.connection(root) as c:
        c.executescript('''
          CREATE TABLE IF NOT EXISTS benchmark_candidates(candidate_id TEXT PRIMARY KEY,batch_id TEXT NOT NULL,sku TEXT NOT NULL,phase TEXT NOT NULL,candidate_hash TEXT NOT NULL,payload TEXT NOT NULL,FOREIGN KEY(batch_id,sku) REFERENCES sample_members);
          CREATE TABLE IF NOT EXISTS benchmark_adjudications(seq INTEGER PRIMARY KEY AUTOINCREMENT,candidate_id TEXT NOT NULL REFERENCES benchmark_candidates,adjudication_hash TEXT NOT NULL,payload TEXT NOT NULL,UNIQUE(candidate_id,adjudication_hash));
          CREATE TABLE IF NOT EXISTS benchmark_runs(run_id TEXT PRIMARY KEY,payload TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS benchmark_holdout_plans(plan_id TEXT PRIMARY KEY,payload TEXT NOT NULL);
        ''')


def register_candidates(root,batch,rows):
    schema(root)
    with storage.connection(root) as c:
        members={r[0]:json.loads(r[1]) for r in c.execute('select sku,blind_input from sample_members where batch_id=?',(batch,))}
        if len(rows)!=100 or {r['sku'] for r in rows}!=set(members):raise ValueError('CANDIDATE_SCOPE_MUST_EQUAL_FROZEN_100')
        for x in rows:
            if x.get('label_authority')!='AI_CANDIDATE' or x.get('human_confirmed') is not False:raise ValueError('AI_CANNOT_CREATE_GOLD')
            if x['input']!=members[x['sku']] or x['input_hash']!=digest(x['input']):raise ValueError('FROZEN_INPUT_BINDING_MISMATCH')
            title=x['input']['name_es_original']
            bad=bool(re.search('[\u3400-\u9fff]',title) and not re.search('[A-Za-zÀ-ÿ]',title))
            if x['source_anomaly']!=bad:raise ValueError('SOURCE_ANOMALY_FLAG_MISMATCH')
            h=digest({k:v for k,v in x.items() if k not in ['candidate_id','candidate_hash']})
            if x['candidate_hash']!=h:raise ValueError('CANDIDATE_HASH_MISMATCH')
            storage.append_exact(c,'benchmark_candidates','candidate_id',x['candidate_id'],(batch,x['sku'],x['phase'],h,storage.encode(x)),('batch_id','sku','phase','candidate_hash','payload'))


def candidates(root,phase=PHASE):
    schema(root)
    with storage.connection(root) as c:return [json.loads(r[0]) for r in c.execute('select payload from benchmark_candidates where phase=? order by sku',(phase,))]


def adjudicate(root,rows):
    schema(root)
    allowed=set(FIELDS)-{'confidence','evidence'}
    checked=[]
    with storage.connection(root) as c:
        for x in rows:
            r=c.execute('select candidate_hash,payload from benchmark_candidates where candidate_id=?',(x.get('candidate_id'),)).fetchone()
            if not r or x.get('candidate_hash')!=r[0]:raise ValueError('STALE_OR_UNKNOWN_CANDIDATE')
            if x.get('reviewer_kind')!='human' or re.search(r'codex|chatgpt|qwen|\bai\b',str(x.get('reviewer','')),re.I) or not str(x.get('reviewer','')).strip():raise ValueError('EXPLICIT_HUMAN_REVIEW_REQUIRED')
            if not str(x.get('evidence_reference','')).strip():raise ValueError('HUMAN_EVIDENCE_REFERENCE_REQUIRED')
            if x.get('decision') not in ['CONFIRMED','NEEDS_CHANGE','REJECTED']:raise ValueError('INVALID_ADJUDICATION')
            target=x.get('target_labels',{});fields=x.get('confirmed_fields',[])
            if not isinstance(target,dict) or not isinstance(fields,list):raise ValueError('INVALID_TARGET_SCHEMA')
            if x['decision']=='CONFIRMED' and (not fields or set(fields)!=set(target) or any(f not in allowed for f in fields)):raise ValueError('EXPLICIT_CONFIRMED_TARGETS_REQUIRED')
            if x['decision']=='CONFIRMED':
                if x.get('problem_type') not in ['AI判断错误','来源字段异常','品名信息不足','判断正确','待人工确认']:raise ValueError('HUMAN_PROBLEM_TYPE_REQUIRED')
                for f in fields:
                    if f in ['primary_function','usage_scenario','consumer_need','action_pattern']:
                        if not isinstance(target[f],list) or any(not isinstance(v,str) for v in target[f]):raise ValueError('INVALID_TARGET_LABEL_TYPE')
                    elif not isinstance(target[f],str) or not target[f].strip():raise ValueError('INVALID_TARGET_LABEL_TYPE')
                    if f=='review_status' and target[f] not in ['待审核','信息不足']:raise ValueError('TARGET_PREDICTION_STATUS_NOT_HUMAN_DECISION')
            checked.append(x)
        for x in checked:
            c.execute('insert or ignore into benchmark_adjudications(candidate_id,adjudication_hash,payload) values(?,?,?)',(x['candidate_id'],digest(x),storage.encode(x)))
    return {'adjudication_records':len(checked)}


def gold(root,phase=PHASE):
    schema(root)
    with storage.connection(root) as c:
        latest={r[0]:json.loads(r[1]) for r in c.execute('select candidate_id,payload from benchmark_adjudications order by seq')}
    result=[]
    for x in candidates(root,phase):
        a=latest.get(x['candidate_id'])
        if a and a['decision']=='CONFIRMED' and a.get('reviewer_kind')=='human' and a.get('candidate_hash')==x['candidate_hash']:
            result.append({'candidate_id':x['candidate_id'],'sku':x['sku'],'input_hash':x['input_hash'],'source_anomaly':x['source_anomaly'],
                           'target_labels':a['target_labels'],'confirmed_fields':a['confirmed_fields'],'label_authority':'HUMAN_CONFIRMED',
                           'reviewer':a['reviewer'],'problem_type':a['problem_type'],'evidence_reference':a['evidence_reference']})
    return result


def evaluate_predictions(root,predictions,inputs,phase=PHASE):
    items=candidates(root,phase);by={x['sku']:x for x in items}
    if set(predictions)!=set(by) or set(inputs)!=set(by):raise ValueError('RETEST_SCOPE_MISMATCH')
    targets=gold(root,phase);gold_ids={x['sku'] for x in targets}
    schema_errors=[];span_errors=[];source_unquarantined=[];bindings=[];per_item=[]
    for sku,x in sorted(predictions.items()):
        if digest(inputs[sku])!=by[sku]['input_hash']:bindings.append(sku)
        try:validate_annotation(x,inputs[sku],x['rules_version'])
        except (ValueError,TypeError,KeyError) as e:
            schema_errors.append({'sku':sku,'error':str(e)})
            if 'EVIDENCE' in str(e):span_errors.append(sku)
        bad=by[sku]['source_anomaly']
        if bad and x['review_status']!='信息不足':source_unquarantined.append(sku)
        per_item.append({'sku':sku,'source_anomaly':bad,'status':x['review_status'],'label_authority':'AI_CANDIDATE','gold_eligible_now':sku in gold_ids})
    matches=total=0;gold_skus=0
    source_gold=0
    for g in targets:
        if g['label_authority']!='HUMAN_CONFIRMED':raise ValueError('NON_HUMAN_GOLD')
        if g['input_hash']!=digest(inputs[g['sku']]):raise ValueError('GOLD_INPUT_MISMATCH')
        if g['source_anomaly']:
            source_gold+=1
            continue
        gold_skus+=1
        for f in g['confirmed_fields']:
            actual=predictions[g['sku']].get(f);expected=g['target_labels'][f]
            if f in MULTI:
                same=isinstance(actual,list) and {normalize_name(v) for v in actual}=={normalize_name(v) for v in expected}
            else:same=isinstance(actual,str) and normalize_name(actual)==normalize_name(expected)
            total+=1;matches+=same
    result={'input_count':len(inputs),'prediction_count':len(predictions),'scope_unique_skus':len(predictions),
            'schema_failures':schema_errors,'evidence_span_failures':span_errors,'input_binding_failures':bindings,
            'source_anomaly_cases':sum(x['source_anomaly'] for x in items),'source_anomaly_quarantine_failures':source_unquarantined,
            'valid_source_semantic_candidates':sum(not x['source_anomaly'] for x in items),
            'prediction_status_counts':dict(__import__('collections').Counter(x['review_status'] for x in predictions.values())),
            'human_confirmed_semantic_skus':gold_skus,'human_confirmed_semantic_fields':total,'human_confirmed_source_cases':source_gold,
            'semantic_field_accuracy':matches/total if total else None,'semantic_field_error_rate':1-matches/total if total else None,
            'accuracy_reason':'HUMAN_GOLD_ONLY' if total else 'NO_HUMAN_CONFIRMED_GOLD',
            'contract_pass':not(schema_errors or span_errors or bindings or source_unquarantined),
            'not_a_fresh_model_inference':True,'not_a_generalization_test':True,'per_item':per_item}
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['adjudicate','export-gold']);p.add_argument('--input');p.add_argument('--output')
    a=p.parse_args()
    if a.command=='adjudicate':
        if str(a.input).lower().endswith('.csv'):
            with open(a.input,encoding='utf-8-sig',newline='') as f:
                rows=[{'candidate_id':x['candidate_id'],'candidate_hash':x['candidate_hash'],'decision':x['human_decision'],
                       'reviewer_kind':x['human_reviewer_kind'],'reviewer':x['human_reviewer'],'evidence_reference':x['human_evidence_reference'],
                       'confirmed_fields':json.loads(x['human_confirmed_fields']),'target_labels':json.loads(x['human_target_labels']),'problem_type':x['human_problem_type']}
                      for x in csv.DictReader(f) if x['human_decision']!='PENDING']
        else:rows=read_jsonl(a.input)
        r=adjudicate(ROOT,rows)
    else:
        r=gold(ROOT)
        if a.output:
            path=Path(a.output).resolve()
            if not path.is_relative_to(ROOT):raise ValueError('OUTPUT_MUST_STAY_IN_INDEPENDENT_PROJECT')
            immutable(path,r,jsonl=True)
    print(json.dumps(r,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
