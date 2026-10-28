"""Descriptive comparison, with unavailable human accuracy kept null."""
import collections,json
from .experiment import rows,score,WEIGHTS,comparable
from .data_audit import write_jsonl,digest

def collect(work):
    sample=rows(work/'sample200.jsonl');answers={m:{r['record_id']:r for r in rows(work/f'results_{m}.jsonl')} for m in ['A','B']}
    if len(sample)!=200 or any(len(x)!=200 for x in answers.values()):raise ValueError('INCOMPLETE_200_EXPERIMENT')
    details=[];comparison=[]
    for r in sample:
        refs={c['sku']:c for c in r['recall20']};by_method={}
        for method in ['A','B']:
            a=answers[method][r['experiment_id']];pairs=[]
            for i,pair in enumerate(a['pairs'],1):
                ref=refs[pair['sku']];name=max(0,min(100,ref['retrieval_score']*100))
                scores={k:score(name,pair,method,v) for k,v in WEIGHTS.items()}
                p={'id':r['experiment_id'],'asin':r['asin'],'method':method,'model_rank':i,'amazon_title':r['title'],'amazon_url':r['url'],'amazon_spec':r['spec'],'amazon_category':[r['category1'],r['category2']],'amazon_price':r['price'],'amazon_date':r['source_date'],'amazon_source_file':r['source_file'],'amazon_source_row':r['source_row'],'sku':pair['sku'],'action_title':ref['title'],'action_spec':ref['spec'],'action_category':[ref['category1'],ref['category2']],'action_evidence':ref['price_source'],'relation':pair['relation'],'spec_status':pair['spec_status'],'category_status':pair['category_status'],'name_similarity':name,'scores':scores,'index':scores['balanced']['index'],'reason':pair['reason'],'unknowns':pair['unknowns'],'price':comparable(r,ref['price_source'],pair) if method=='B' else {'eligible':False,'reasons':['A_WITHHOLDS_SPECS_AND_PRICE'],'ratio':None},'no_confirmed_match':a['no_confirmed_match'],'sold_subject':a['sold_subject'],'pack_evidence':{k:pair[k] for k in ['amazon_pack','action_pack','amazon_pack_span','action_pack_span']},'authority':'AI_CANDIDATE_NOT_FACT_GOLD'}
                pairs.append(p)
            pairs.sort(key=lambda p:(-(p['index'] if p['index'] is not None else -1),p['model_rank']))
            for rank,p in enumerate(pairs,1):p['rank']=rank
            details+=pairs;by_method[method]=pairs
        cs=[]
        for p in by_method['B']:
            c={**p,'method':'C','rank':None,'index':None,'C_sensitivity':{},'C_status':'NOT_COVERED_NO_B_FALLBACK'}
            if p['price']['eligible']:
                for w in [.05,.10,.20]:
                    c['C_sensitivity'][str(w)]=round(min(p['scores']['balanced']['cap'],(1-w)*p['index']+w*p['price']['price_band_similarity']),2)
                c['index']=c['C_sensitivity']['0.1'];c['C_status']='PROVISIONAL_COMPARABLE_PAIR_NOT_HUMAN_VALIDATED'
            cs.append(c)
        complete=all(p['price']['eligible'] for p in cs)
        if complete:
            cs.sort(key=lambda p:-p['index'])
            for i,p in enumerate(cs,1):p['rank']=i
        details+=cs
        def winner(method,key):return min(by_method[method],key=lambda p:(-(p['scores'][key]['index'] if p['scores'][key]['index'] is not None else -1),p['model_rank']))['sku']
        comparison.append({'id':r['experiment_id'],'stratum':r['stratum'],'asin':r['asin'],'title':r['title'],'source_file':r['source_file'],'source_row':r['source_row'],'url':r['url'],'baseline_retrieval_top1':r['recall20'][0]['sku'],'A_top1':by_method['A'][0],'B_top1':by_method['B'][0],'C_top1':cs[0] if complete else None,'C_comparable_pairs':sum(p['price']['eligible'] for p in cs),'C_full_top5_comparable':complete,'AB_top1_changed':by_method['A'][0]['sku']!=by_method['B'][0]['sku'],'AB_relation_changed':by_method['A'][0]['relation']!=by_method['B'][0]['relation'],'weight_top1_sensitive':any(len({winner(m,k) for k in WEIGHTS})>1 for m in ['A','B']),'human_fact_relation':None,'human_relevant_action_skus':None,'human_business_value':None})
    write_jsonl(work/'results_ABC_top5.jsonl',details);write_jsonl(work/'comparison200.jsonl',comparison)
    usage={}
    for method in ['A','B']:
        from runtime.v31.state import State
        state=State(work/method/'events.sqlite3')
        calls=[v for _,v in state.all('model_call')];failures=[v for _,v in state.all('model_failure')]
        request_counts=collections.Counter(v['request_hash'] for v in calls)
        available_logs={digest(p) for p in (work/method/'calls').glob('*/events.jsonl')}|{p.stem for p in (work/'cli_event_archive').glob('*.jsonl')}
        usage[method]={'calls':len(calls),'call_records':sum(v['records'] for v in calls),'elapsed_call_seconds':round(sum(v['elapsed_seconds'] for v in calls),2),'tokens':dict(sum((collections.Counter(u) for v in calls for u in v['usage'] if u),collections.Counter())),'failures':failures,'source_or_schema_rejections':len(state.all('model_invalid')),'duplicate_request_calls':sum(n-1 for n in request_counts.values()),'all_call_event_hashes_available':all(v['events_sha256'] in available_logs for v in calls),'integrity':state.db.execute('PRAGMA integrity_check').fetchone()[0],'fk_violations':len(state.db.execute('PRAGMA foreign_key_check').fetchall())};state.close()
    metrics={'sample':200,'top5_rows_per_method':1000,'strata':dict(collections.Counter(r['stratum'] for r in sample)),'AB_top1_changed':sum(r['AB_top1_changed'] for r in comparison),'AB_relation_changed':sum(r['AB_relation_changed'] for r in comparison),'weight_top1_sensitive_queries':sum(r['weight_top1_sensitive'] for r in comparison),'A_changed_from_existing_retrieval_top1':sum(r['A_top1']['sku']!=r['baseline_retrieval_top1'] for r in comparison),'B_changed_from_existing_retrieval_top1':sum(r['B_top1']['sku']!=r['baseline_retrieval_top1'] for r in comparison),'A_relations':dict(collections.Counter(r['A_top1']['relation'] for r in comparison)),'B_relations':dict(collections.Counter(r['B_top1']['relation'] for r in comparison)),'C_comparable_pairs':sum(r['C_comparable_pairs'] for r in comparison),'C_queries_with_any_comparable_pair':sum(r['C_comparable_pairs']>0 for r in comparison),'C_queries_with_full_comparable_top5':sum(r['C_full_top5_comparable'] for r in comparison),'C_noncomparable_reasons':dict(collections.Counter(reason for p in details if p['method']=='C' for reason in p['price']['reasons'])),'human_fact_labels':0,'human_business_labels':0,'Precision_at_1':None,'Recall_at_20':None,'confirmed_high_score_false_matches':None,'confirmed_spec_false_matches':None,'price_improved_accuracy':None,'weights_calibrated':False,'usage':usage}
    (work/'metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf8')
    # 60 unique pairs: score strata + AB changes + conflicts + missing facts.
    pool=[p for p in details if p['method'] in ('A','B')];chosen=[];seen=set()
    groups=[('high_score',lambda p:p['index'] is not None and p['index']>=60),('low_score',lambda p:p['index'] is not None and p['index']<20),('spec_difference',lambda p:p['spec_status']=='DIFFERENT'),('uncertain',lambda p:p['relation'] in ['INSUFFICIENT','SHARED_NEED','FUNCTIONAL_ALTERNATIVE']),('AB_change',lambda p:next(r for r in comparison if r['id']==p['id'])['AB_top1_changed']),('other',lambda p:True)]
    for label,predicate in groups:
        n=0
        for p in pool:
            key=(p['asin'],p['sku'])
            if key in seen or not predicate(p):continue
            chosen.append({**p,'review_stratum':label,'fact_reviewer':None,'fact_relation':None,'fact_evidence':None,'relevant_action_skus_after_catalog_search':None,'business_reviewer':None,'business_value':None});seen.add(key);n+=1
            if n==10 or len(chosen)==60:break
        if len(chosen)==60:break
    if len(chosen)<60:
        for p in pool:
            if (p['asin'],p['sku']) not in seen:
                chosen.append({**p,'review_stratum':'quota_fallback','fact_reviewer':None,'fact_relation':None,'fact_evidence':None,'relevant_action_skus_after_catalog_search':None,'business_reviewer':None,'business_value':None});seen.add((p['asin'],p['sku']))
                if len(chosen)==60:break
    write_jsonl(work/'independent_review60.jsonl',chosen)
    return metrics
