"""Read a frozen V2 run; write a separate, private price/evidence review.

No model calls, training, score changes, original data writes or human labels.
"""
from __future__ import annotations
import argparse, collections, csv, hashlib, json, re, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from runtime.matching_v2.experiment import rows, comparable, WEIGHTS
from runtime.matching_v2.data_audit import digest, write_jsonl
from runtime.matching_v2.price_layers import layers, quantity, price_history, folded


def save(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')


def dimension_keys(q):
    """Comparable coordinate multiset only; never proof of axes/form equivalence."""
    out=[]
    for d in q['dimensions']:
        if d['scope']=='PACKAGE':continue
        text=d['span_folded'];values=[float(x.replace(',','.')) for x in re.findall(r'\d+(?:[.,]\d+)?',text)]
        factor=.1 if text.endswith('mm') else 100 if re.search(r'metros?$',text) else 1
        out.append(tuple(sorted(round(v*factor,6) for v in values)))
    return out


def quoted_identifiers(record):
    text='\n'.join(str(record.get(k,'') or '') for k in ['title','spec','variant','details'])
    return {'model_label_spans':re.findall(r'(?:Modelo|N[uú]mero de modelo|Referencia|Model number)\s*[:：]\s*[^\n;|]{1,100}',text,re.I),
            'gtin_label_spans':re.findall(r'(?:EAN|GTIN|UPC)\s*[:：]?\s*\d{8,14}\b',text,re.I),
            'status':'LITERAL_LABELS_ONLY_NOT_IDENTITY_VERIFICATION'}


def full_scores(matcher,titles):
    import numpy as np
    from sklearn.preprocessing import normalize
    from assortment import norm
    m=matcher.model
    word=m['word'].transform([' '.join(matcher.f.words(t)) for t in titles])
    char=m['char'].transform([norm(t) for t in titles]);latent=normalize(m['svd'].transform(word))
    scores=.46*(word@m['word_matrix'].T).toarray()+.20*(char@m['char_matrix'].T).toarray()+.24*(latent@m['latent_matrix'].T)
    refheads=np.array([r['feature']['head'] for r in m['references']])
    for i,t in enumerate(titles):
        h=matcher.f.extract(t,True)['head']
        if h:scores[i]+=.10*(refheads==h)
    return scores


def recall_review(sample, answers, comparison, reviews, action, output):
    """Six fixed evidence strata; focused queries inspect all frozen references."""
    import numpy as np
    from threadpoolctl import threadpool_limits
    sys.path.insert(0,str(ROOT/'runtime/v2'))
    from assortment import Matcher
    matcher=Matcher();refs=matcher.model['references'];n=len(refs)
    cm={r['id']:r for r in comparison};am={r['experiment_id']:r for r in sample}
    predicates=[('high_name_similarity',lambda r:r['stratum']=='high_name_similarity'),
                ('AB_top1_difference',lambda r:cm[r['experiment_id']]['AB_top1_changed']),
                ('spec_conflict',lambda r:any(p['spec_status']=='DIFFERENT' for p in answers[r['experiment_id']]['pairs'])),
                ('host_or_part',lambda r:bool(re.search(r'\b(?:compatible|repuesto|recambio|rejilla|valvula|filtro|para)\b',folded(r['title'])))),
                ('weak_retrieval',lambda r:r['stratum']=='weak_reference'),
                ('no_confirmed_match',lambda r:answers[r['experiment_id']]['no_confirmed_match'])]
    selected=[];seen=set()
    for label,test in predicates:
        for r in [r for r in sample if r['experiment_id'] not in seen and test(r)][:5]:
            seen.add(r['experiment_id']);selected.append((r,label))
    if len(selected)!=30:raise ValueError('INSUFFICIENT_RECALL_STRATUM_NO_SILENT_SUBSTITUTION')
    # No classifier refit; identical frozen retrieval matrix and scoring function.
    with threadpool_limits(limits=2):
        original=full_scores(matcher,[r['title'] for r,_ in selected])
        focused=full_scores(matcher,[answers[r['experiment_id']]['subject_span'] for r,_ in selected])
    summaries=[];candidates=[];differences=[]
    with (output/'recall30_all10037_ranks.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['query_id','Action_SKU','Action_original_title','original_rank','original_score','focused_rank','focused_score','original_top20'])
        for i,(r,label) in enumerate(selected):
            order=np.argsort(-original[i],kind='stable');focus_order=np.argsort(-focused[i],kind='stable')
            ranks={int(j):k+1 for k,j in enumerate(order)};franks={int(j):k+1 for k,j in enumerate(focus_order)}
            old20={c['sku'] for c in r['recall20']}
            rebuilt20={refs[j]['sku'] for j in order[:20]}
            # Account for floating point/tie behavior without hiding real drift.
            if old20!=rebuilt20:
                boundary=float(original[i,order[19]])
                mismatch=old20.symmetric_difference(rebuilt20)
                bad=[x for x in mismatch if abs(float(original[i,next(j for j,v in enumerate(refs) if v['sku']==x)])-boundary)>1e-6]
                if bad:raise ValueError('FROZEN_RETRIEVAL_CHANGED:'+r['experiment_id'])
                differences.append({'id':r['experiment_id'],'kind':'TOP20_BOUNDARY_TIE','count':len(mismatch)})
            for j in order:
                ref=refs[j]
                writer.writerow([r['experiment_id'],ref['sku'],ref['name_es_original'],ranks[int(j)],float(original[i,j]),franks[int(j)],float(focused[i,j]),ref['sku'] in old20])
            chosen=list(dict.fromkeys([int(j) for j in order[:5]]+[int(j) for j in focus_order[:20]]))
            outside=[]
            for j in chosen:
                ref=refs[j];source=action.get(ref['sku'])
                item={'id':r['experiment_id'],'asin':r['asin'],'amazon_title':r['title'],'subject_query':answers[r['experiment_id']]['subject_span'],
                      'sku':ref['sku'],'action_title':ref['name_es_original'],'original_rank':ranks[j],'focused_rank':franks[j],
                      'in_original_top20':ref['sku'] in old20,'source':source,'confirmed_relation':None,'reviewer':None,
                      'status':'NEW_QUERY_CANDIDATE_NOT_CONFIRMED_MISS','possible_retrieval_mechanism':'Literal subject query reduces long-title or host words; not proof of improved semantic recall'}
                candidates.append(item)
                if ref['sku'] not in old20:outside.append(ref['sku'])
            summaries.append({'id':r['experiment_id'],'asin':r['asin'],'title':r['title'],'stratum':label,'subject_query':answers[r['experiment_id']]['subject_span'],
                              'searched_references':n,'outside_top20_candidate_skus':outside,'existing60_overlap':r['asin'] in {x['asin'] for x in reviews},
                              'identical_exists':None,'same_type_exists':None,'substitute_exists':None,'best_sku':None,'reviewer':None,'reviewed_at':None,
                              'status':'UNCONFIRMED_EXISTENCE_NOT_ABSENCE'})
    # Auditors can filter/search the entire reference file, including missing-price SKUs.
    with (output/'action10037_search_catalog.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['SKU','Spanish_title','source_spec','source_url','source_file','title_binding_exact'])
        for ref in refs:
            s=action.get(ref['sku']) or {}
            w.writerow([ref['sku'],ref['name_es_original'],s.get('spec',''),s.get('url',''),s.get('source_file',''),s.get('title_binding_exact')])
    write_jsonl(output/'recall30.jsonl',summaries);write_jsonl(output/'recall30_candidates.jsonl',candidates)
    return {'queries':len(summaries),'all_references':n,'all_rank_rows':len(summaries)*n,'review60_overlap_asins':sum(s['existing60_overlap'] for s in summaries),
            'combined_unique_amazon':len({s['asin'] for s in summaries}|{r['asin'] for r in reviews}),
            'strata':dict(collections.Counter(x['stratum'] for x in summaries)),
            'candidate_rows':len(candidates),'outside_original20_candidates':sum(not x['in_original_top20'] for x in candidates),
            'queries_with_outside_candidates':sum(bool(s['outside_top20_candidate_skus']) for s in summaries),
            'original_retrieval_parity':'PASS_WITH_REPORTED_TIES' if differences else 'PASS','ties':differences,
            'confirmed_misses':None,'Recall_at_20':None,'limitation':'Focused lexical retrieval is not independent exhaustive semantic ground truth'}


def run(source, output):
    started=time.perf_counter();source=source.resolve();output=output.resolve()
    if output==source or source in output.parents:raise ValueError('OUTPUT_MUST_NOT_BE_IN_FROZEN_RUN')
    if output.exists():raise ValueError('OUTPUT_EXISTS_USE_NEW_VERSION')
    freeze=json.loads((source/'freeze.json').read_text(encoding='utf8'))
    if digest(source/'sample200.jsonl')!=freeze['sample_sha256']:raise ValueError('FIXED_SAMPLE_HASH_CHANGED')
    if digest(ROOT/'assets/action_reference10037.jsonl')!=freeze['reference_hash']:raise ValueError('REFERENCE_HASH_CHANGED')
    if {k:list(v) for k,v in WEIGHTS.items()}!=freeze['weights']:raise ValueError('FROZEN_WEIGHTS_CHANGED')
    for method,sha in freeze['request_hashes'].items():
        if digest(source/f'requests_{method}.jsonl')!=sha:raise ValueError('ORIGINAL_REQUEST_CHANGED')
    sample=rows(source/'sample200.jsonl');answers={x['record_id']:x for x in rows(source/'results_B.jsonl')}
    details=rows(source/'results_ABC_top5.jsonl');pairs=[x for x in details if x['method']=='B']
    reviews=rows(source/'independent_review60.jsonl');comparison=rows(source/'comparison200.jsonl')
    action={x['sku']:x for x in rows(source/'action_latest.jsonl')};groups=rows(source/'amazon_index.jsonl')
    if len(sample)!=200 or len(pairs)!=1000 or len(reviews)!=60:raise ValueError('ORIGINAL_RUN_CARDINALITY_INVALID')
    if len({r['asin'] for r in sample})!=200 or len({(p['asin'],p['sku']) for p in pairs})!=1000:raise ValueError('DUPLICATED_FIXED_SAMPLE')
    amazon_audit=json.loads((source/'amazon_audit.json').read_text(encoding='utf8'))
    action_audit=json.loads((source/'action_audit.json').read_text(encoding='utf8'))
    inputs=amazon_audit['inputs']+action_audit['sources']
    verified={x['path']:digest(Path(x['path'])) for x in inputs}
    if any(verified[x['path']]!=x['sha256'] for x in inputs):raise ValueError('ORIGINAL_SOURCE_FILE_CHANGED')
    # Include all frozen run files (raw model/event logs too), plus source books and protected assets.
    protected={str(p):digest(p) for p in source.rglob('*') if p.is_file()}
    protected.update(verified)
    for pattern in ['assets/**/*','releases/**/*','SKILL.md','references/selection*','runtime/v2/**/*','runtime/matching_v2/experiment.py','runtime/matching_v2/reporting.py']:
        for p in ROOT.glob(pattern):
            if p.is_file() and '__pycache__' not in str(p):protected[str(p)]=digest(p)
    output.mkdir(parents=True);save(output/'protected_before.json',protected)
    sm={x['experiment_id']:x for x in sample};result=[];old=[]
    for p in pairs:
        r=sm[p['id']];answer=answers[p['id']];raw=next(x for x in answer['pairs'] if x['sku']==p['sku'])
        c=next(x for x in r['recall20'] if x['sku']==p['sku'])
        strict=comparable(r,c['price_source'],raw)
        if strict!=p['price']:raise ValueError('STRICT_BASELINE_CHANGED')
        old.append(strict)
        evidence=layers(r,c['price_source'],p,verified,bool(answer['subject_span'] and answer['subject_span'] in r['title'] and answer['sold_subject']))
        q1=evidence['L3']['amazon_quantity'];q2=evidence['L3']['action_quantity']
        equal_amount=q1['amount'] is not None and q2['amount'] is not None and q1['base']==q2['base'] and abs(q1['amount']-q2['amount'])<1e-8
        dim_overlap=bool(set(dimension_keys(q1))&set(dimension_keys(q2)))
        result.append({'id':p['id'],'asin':p['asin'],'sku':p['sku'],'amazon_title':r['title'],'action_title':c['title'],
                       'amazon_spec':r['spec'],'action_spec':c['spec'],'rank_preserved':p['rank'],'index_preserved':p['index'],
                       'relation_preserved':p['relation'],'spec_status_preserved':p['spec_status'],'old_strict':strict,
                       'normalized_amount_equal_not_spec_equivalence':equal_amount,'dimension_coordinates_equal_not_axes_or_material_proof':dim_overlap,
                       'layers':evidence})
    write_jsonl(output/'price_layers1000.jsonl',result)
    review_cards=[]
    for i,p in enumerate(reviews,1):
        r=sm[p['id']];c=next(x for x in r['recall20'] if x['sku']==p['sku']);s=c['price_source']
        aq=quantity(r['title'],r['spec'],r.get('variant',''));bq=quantity(s['title'],s.get('spec','')) if s else quantity('')
        checks={'source_record_available':s is not None,'action_title_binding_exact':bool(s and s['title_binding_exact']),
                'amazon_sale_quantity':{'base':aq['base'],'amount':aq['amount']},'action_sale_quantity':{'base':bq['base'],'amount':bq['amount']},
                'numeric_basis_comparable':bool(aq['amount'] is not None and bq['amount'] is not None and aq['base']==bq['base']),
                'product_identity_verified':False,'missing_source_is_not_product_absence':True}
        review_cards.append({'review_id':f'F{i:02d}','original_pair_id':[p['asin'],p['sku']],
          'amazon':{k:r.get(k) for k in ['asin','title','spec','variant','details','url','price','list_price','promotion_status','source_file','source_sha256','source_row','source_date']},
          'action':{'sku':c['sku'],'frozen_title':c['title'],'saved_source':s},
          'amazon_literal_identifiers':quoted_identifiers(r),'action_literal_identifiers':quoted_identifiers(s or {}),
          'amazon_quantity':aq,'action_quantity':bq,'objective_checks':checks,
          'fact_relation':None,'actual_sold_subject_amazon':None,'actual_sold_subject_action':None,'fact_reviewer':None,'fact_evidence':None,'reviewed_at':None,
          'business_value':None,'business_reviewer':None,'unresolved':'No independent identity/type ruling; absent model/GTIN is unknown; snapshot is historical, not a live official verification'})
    write_jsonl(output/'fact_review60.jsonl',review_cards)
    hist,history_rows=price_history(groups);write_jsonl(output/'price_history15596.jsonl',history_rows)
    recall=recall_review(sample,answers,comparison,reviews,action,output)
    counters={}
    for name in ['L2','L3']:
        eligible=[x for x in result if x['layers'][name]['eligible']]
        counters[name]={'pairs':len(eligible),'amazon_skus':len({x['asin'] for x in eligible}),'action_skus':len({x['sku'] for x in eligible}),
                        'date_buckets':dict(collections.Counter(x['layers'][name]['date_bucket'] for x in eligible)),
                        'blockers_overlap':dict(collections.Counter(r for x in result for r in x['layers'][name]['reasons']))}
    l1=[x for x in result if x['layers']['L1']['both_valid']]
    counters['L1']={'both_valid_pairs':len(l1),'amazon_skus':len({x['asin'] for x in l1}),'action_skus':len({x['sku'] for x in l1}),
                    'amazon_valid_pair_occurrences':sum(x['layers']['L1']['amazon']['valid'] for x in result),
                    'action_valid_pair_occurrences':sum(x['layers']['L1']['action']['valid'] for x in result),
                    'amazon_valid_unique':len({x['asin'] for x in result if x['layers']['L1']['amazon']['valid']}),
                    'action_valid_unique':len({x['sku'] for x in result if x['layers']['L1']['action']['valid']}),
                    'blockers_overlap':dict(collections.Counter(side+':'+r for x in result for side in ['amazon','action'] for r in x['layers']['L1'][side]['reasons']))}
    cascade=collections.Counter()
    for x in result:
        e=x['layers']
        reason='L3_STANDARDIZABLE' if e['L3']['eligible'] else 'L2_ONLY_QUANTITY_OR_BASE_UNCONFIRMED' if e['L2']['eligible'] else 'L1_VALID_TYPE_UNCONFIRMED' if e['L1']['both_valid'] else 'L1_SOURCE_PRICE_OR_CURRENCY_INVALID'
        cascade[reason]+=1
    counts_by_asin=collections.Counter(x['asin'] for x in reviews)
    summary={'input_sample':len(sample),'B_pairs':len(pairs),'verified_source_books':len(verified),
      'amazon_records':sum(len(g['observations']) for g in groups),'amazon_asins':len(groups),
      'amazon_positive_price':sum(r['price']['value'] is not None and r['price']['value']>0 for g in groups for r in g['observations']),
      'action_frozen_references':recall['all_references'],'action_saved_skus':len(action),'action_saved_exact_binding':sum(bool(s['title_binding_exact']) for s in action.values()),
      'AB_top1_changed':sum(x['AB_top1_changed'] for x in comparison),'weight_sensitive':sum(x['weight_top1_sensitive'] for x in comparison),
      'old_strict_eligible':sum(x['eligible'] for x in old),'old_strict_blockers_overlap':dict(collections.Counter(r for x in old for r in x['reasons'])),
      'B_spec_status':dict(collections.Counter(x['spec_status'] for x in pairs)),
      'B_category_status':dict(collections.Counter(x['category_status'] for x in pairs)),
      'normalized_amount_equal_pairs_not_equivalence':sum(x['normalized_amount_equal_not_spec_equivalence'] for x in result),
      'dimension_coordinate_overlap_pairs_not_equivalence':sum(x['dimension_coordinates_equal_not_axes_or_material_proof'] for x in result),
      'old_pack_missing_L2_available':sum('EQUIVALENT_PACK_COUNT_UNCONFIRMED' in x['old_strict']['reasons'] and x['layers']['L2']['eligible'] for x in result),
      'old_pack_missing_new_two_explicit_counts':sum('EQUIVALENT_PACK_COUNT_UNCONFIRMED' in x['old_strict']['reasons'] and all(x['layers']['L3'][side+'_quantity']['explicit_pack_count'] is not None for side in ['amazon','action']) for x in result),
      'old_pack_missing_L3_available':sum('EQUIVALENT_PACK_COUNT_UNCONFIRMED' in x['old_strict']['reasons'] and x['layers']['L3']['eligible'] for x in result),
      'L2_partial_top5_queries':sum(0<sum(x['layers']['L2']['eligible'] for x in result if x['id']==r['experiment_id'])<5 for r in sample),
      'L2_full_top5_queries':sum(sum(x['layers']['L2']['eligible'] for x in result if x['id']==r['experiment_id'])==5 for r in sample),
      'layers':counters,'disjoint_price_cascade':dict(cascade),'history':hist,
      'old_history_mixed_change_count':amazon_audit['price_changed_asins'],
      'review60':{'pairs':len(reviews),'unique_pairs':len({(r['asin'],r['sku']) for r in reviews}),'unique_amazon':len(counts_by_asin),'max_pairs_per_amazon':max(counts_by_asin.values()),'strata':dict(collections.Counter(x['review_stratum'] for x in reviews)),'human_fact_labels':0,'sampling_limit':'Pair strata are concentrated by original iteration order; not a 60-product representative sample'},
      'recall30':recall,'weights_unchanged':WEIGHTS,'Precision_at_1':None,'Recall_at_20':None,'price_improved_accuracy':None,
      'new_external_model_calls':0,'new_external_model_tokens':0,'scope':'Deterministic local analysis; excludes interactive assistant conversation tokens',
      'formal_skill_promotion':False,'main_merged':False,'elapsed_seconds':round(time.perf_counter()-started,2)}
    changed=[p for p,h in protected.items() if digest(Path(p))!=h]
    save(output/'protected_after.json',{'checked_files':len(protected),'changed':changed,'pass':not changed})
    if changed:raise ValueError('PROTECTED_INPUT_CHANGED')
    save(output/'summary.json',summary)
    return summary


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--v2-run',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();print(json.dumps(run(args.v2_run,args.output),ensure_ascii=False,indent=2))
