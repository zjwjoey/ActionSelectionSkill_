"""Conservative three-state Amazon screening experiment (append-only V2.4)."""
from __future__ import annotations
import collections, csv, hashlib, json, random, re, sqlite3, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'v2'))
import pipeline as p
from assortment import ROOT as V2ROOT, RUN, Matcher, lines, read, norm

OUT=ROOT/'v2/runs/amazon_boundary_v24_20261022'
DB=ROOT/'learning_data/action_selection.sqlite3'
SEED=2026102224
SOURCE=RUN/'amazon_source_manifest.json'
INPUTS=RUN/'amazon_inputs.jsonl'
V23=ROOT/'outputs/action_semantic_v23_20261022/final_candidate/results.jsonl'

def title_hash(title:str)->str:
    return hashlib.sha256(norm(title).encode('utf-8')).hexdigest()

def prior_title_hashes():
    hashes=set()
    paths=[
      ROOT/'outputs/cross_platform100_20261022/amazon_names_only50.jsonl',
      ROOT/'outputs/p3_ab100_20261022/blind_results100.jsonl',
      ROOT/'outputs/p31_ab200_20261022/blind_results200.jsonl',
      RUN/'technical500_inputs.jsonl',RUN/'independent200_inputs.jsonl',
      ROOT/'outputs/p31_boundary200_20261022/private/prepared_products200.jsonl',
    ]
    for path in paths:
        if not path.exists(): continue
        for row in lines(path):
            title=row.get('title_original') or row.get('product_title_raw') or ''
            if title: hashes.add(title_hash(title))
    return hashes

BOUNDARY_PATTERNS={
 'MAJOR_HOUSEHOLD_APPLIANCE': re.compile(r'\b(?:frigor[ií]fico|nevera|lavadora|secadora|lavavajillas|congelador|arc[oó]n congelador|cocina de gas|cocina el[eé]ctrica)\b',re.I),
 'COMPLETE_LARGE_FURNITURE_SET': re.compile(r'\b(?:conjunto|juego|set)\s+(?:completo\s+)?(?:de\s+)?(?:muebles|comedor|sal[oó]n|dormitorio|sof[aá]s?|jard[ií]n|mesa\s+y\s+sillas|habitaci[oó]n)\b|\b(?:comedor|sal[oó]n|dormitorio)\s+(?:completo\s+)?(?:conjunto|juego|set)\b',re.I),
 'PROFESSIONAL_INDUSTRIAL_EQUIPMENT': re.compile(r'\b(?:m[aá]quina|equipo|sistema|l[ií]nea|torno|reactor|prensa|robot|compresor)\b.{0,45}\b(?:industrial|profesional|de laboratorio|de producci[oó]n|cnc)\b|\b(?:reactor industrial|sistema de cromatograf[ií]a|l[ií]nea de producci[oó]n industrial|equipo industrial)\b',re.I),
 'CLEAR_OUT_OF_TARGET': re.compile(r'\b(?:munici[oó]n|arma de fuego|explosivo|reactor nuclear|sistema de cromatograf[ií]a|l[ií]nea de producci[oó]n industrial)\b',re.I),
}
ACCESSORY_OR_DEPENDENCY=re.compile(r'\b(?:repuesto|recambio|pieza|funda|protector|filtro|adaptador|mando|accesorio|compatible|tapa|soporte|boquilla|cartucho|recambio|para modelos?)\b',re.I)
CONFUSABLE_CUE=re.compile(r'\b(?:para|compatible con|repuesto|recambio|pieza|funda|protector|filtro|adaptador|mando|accesorio|electrodom[eé]stico|mueble|industrial|profesional|completo|conjunto|juego|set)\b',re.I)
PORTABLE_COOLER_CONTEXT=re.compile(r'\b(?:port[aá]til|viaje|insulina|medicamentos|camping|coche|mini|peque[nñ]a?)\b',re.I)

def boundary_for_title(title, features):
    """Return high-confidence boundary only when cue is in sold-item prefix."""
    normalized=norm(title)
    prefix=features['identity_prefix']
    # The title's sold-item prefix ends before purpose/compatibility clauses.
    if not prefix or features['source_invalid']:
        return {'candidate':False,'clear':False,'code':'','evidence_span':'','reason':'SUBJECT_UNCLEAR'}
    # An accessory/component prefix is the actual sold item, even when the
    # object it fits is a major appliance or furniture item.
    if ACCESSORY_OR_DEPENDENCY.search(prefix):
        mentioned=next((code for code,pat in BOUNDARY_PATTERNS.items() if pat.search(normalized)), '')
        return {'candidate':bool(mentioned),'clear':False,'code':'BOUNDARY_OBJECT_ONLY_IN_PURPOSE_OR_COMPONENT_CONTEXT' if mentioned else '',
                'evidence_span':prefix[:120] if mentioned else '',
                'reason':'TITLE_SUBJECT_IS_ACCESSORY_OR_COMPONENT' if mentioned else ''}
    # Require a boundary noun at the start of the product identity phrase.
    # Merely mentioning a fridge, machine, or furniture set later in the title
    # can describe fit, purpose, or a feature of a different sold item.
    subject= re.sub(r'^(?:\d+\s*(?:pcs?|piezas?|unidades?)?\s+)+','',norm(prefix)).strip()
    anchored={
      'MAJOR_HOUSEHOLD_APPLIANCE': re.compile(r'^(?:frigor[ií]fico|nevera|lavadora|secadora|lavavajillas|congelador|arc[oó]n congelador|cocina de gas|cocina el[eé]ctrica)\b',re.I),
      'COMPLETE_LARGE_FURNITURE_SET': re.compile(r'^(?:conjunto|juego|set)\s+(?:completo\s+)?(?:de\s+)?(?:muebles|comedor|sal[oó]n|dormitorio|sof[aá]s?|jard[ií]n|mesa\s+y\s+sillas|habitaci[oó]n)\b',re.I),
      'PROFESSIONAL_INDUSTRIAL_EQUIPMENT': re.compile(r'^(?:m[aá]quina|equipo|sistema|l[ií]nea|torno|reactor|prensa|robot|compresor)\b.{0,45}\b(?:industrial|profesional|de laboratorio|de producci[oó]n|cnc)\b|^(?:reactor industrial|sistema de cromatograf[ií]a|l[ií]nea de producci[oó]n industrial|equipo industrial)\b',re.I),
      'CLEAR_OUT_OF_TARGET': re.compile(r'^(?:munici[oó]n|arma de fuego|explosivo|reactor nuclear|sistema de cromatograf[ií]a|l[ií]nea de producci[oó]n industrial)\b',re.I),
    }
    hits=[];possible=False
    for code,pat in BOUNDARY_PATTERNS.items():
        mention=pat.search(prefix)
        if mention:
            possible=True
            m=anchored[code].search(subject)
            if code=='MAJOR_HOUSEHOLD_APPLIANCE' and m and re.search(r'\b(?:nevera|frigor[ií]fico)\b',m.group(0),re.I) and PORTABLE_COOLER_CONTEXT.search(normalized):
                # Portable travel/medicine/camping coolers are not clear major
                # appliances even when called "nevera" in the title.
                m=None
            if m: hits.append((code,m.group(0)))
    if not hits:
        # These cues can merit review, but are not sufficient to exclude.
        possible=possible or any(pat.search(normalized) for pat in BOUNDARY_PATTERNS.values()) or bool(re.search(r'\b(?:industrial|profesional|laboratorio|mueble|electrodom[eé]stico)\b',normalized))
        return {'candidate':possible,'clear':False,'code':'BOUNDARY_CUE_NOT_SUBJECT_CONFIRMED' if possible else '',
                'evidence_span':'','reason':'BOUNDARY_CUE_NOT_SUBJECT_CONFIRMED' if possible else ''}
    # Exactly one subject-bound boundary family is required. Overlapping or
    # competing interpretations are review-only.
    unique={h[0] for h in hits}
    if len(unique)!=1:
        return {'candidate':True,'clear':False,'code':'MULTIPLE_BOUNDARY_INTERPRETATIONS','evidence_span':' / '.join(h[1] for h in hits),'reason':'MULTIPLE_BOUNDARY_INTERPRETATIONS'}
    code,span=hits[0]
    return {'candidate':True,'clear':True,'code':code,'evidence_span':span,'reason':'HIGH_CONFIDENCE_SUBJECT_BOUNDARY'}

def pick_sample(rows, matcher):
    used=prior_title_hashes()
    available=[r for r in rows if title_hash(r['title_original']) not in used]
    randomizer=random.Random(SEED)
    boundary_pools=collections.defaultdict(list);confusable=[]
    for row in available:
        ft=matcher.f.extract(row['title_original'],True)
        b=boundary_for_title(row['title_original'],ft)
        row['_v24_feature']=ft;row['_v24_boundary']=b
        title_norm=norm(row['title_original'])
        mentioned=[key for key,pat in BOUNDARY_PATTERNS.items() if pat.search(title_norm)]
        for key in mentioned: boundary_pools[key].append(row)
        if b['candidate'] or CONFUSABLE_CUE.search(title_norm):
            confusable.append(row)
    quotas={'MAJOR_HOUSEHOLD_APPLIANCE':25,'COMPLETE_LARGE_FURNITURE_SET':20,'PROFESSIONAL_INDUSTRIAL_EQUIPMENT':20,'CLEAR_OUT_OF_TARGET':15}
    selected=[];selected_ids=set();targeted_labels={}
    for key,quota in quotas.items():
        pool=list(boundary_pools[key]);randomizer.shuffle(pool)
        for row in pool[:quota]:
            if row['record_id'] not in selected_ids:
                selected.append(row);selected_ids.add(row['record_id']);targeted_labels[row['record_id']]='reverse_boundary:'+key
    # Fill the reverse-boundary cohort with difficult confusables and remaining
    # explicit boundary candidates; these cues do not become answer labels.
    remainder=[r for pool in boundary_pools.values() for r in pool if r['record_id'] not in selected_ids]
    remainder+= [r for r in confusable if r['record_id'] not in selected_ids]
    randomizer.shuffle(remainder)
    for row in remainder:
        if len(selected)>=100: break
        if row['record_id'] in selected_ids: continue
        selected.append(row);selected_ids.add(row['record_id'])
        targeted_labels[row['record_id']]='reverse_boundary:confusable_or_unfilled_boundary_quota'
    if len(selected)<100:
        fallback=[r for r in available if r['record_id'] not in selected_ids]
        randomizer.shuffle(fallback)
        for row in fallback[:100-len(selected)]:
            selected.append(row);selected_ids.add(row['record_id']);targeted_labels[row['record_id']]='reverse_boundary:random_fallback'
    if len(selected)<100: raise RuntimeError('INSUFFICIENT_REVERSE_BOUNDARY_SAMPLE')
    rest=[r for r in available if r['record_id'] not in selected_ids]
    randomizer.shuffle(rest)
    if len(rest)<400: raise RuntimeError('INSUFFICIENT_COMPARISON_SAMPLE')
    comparison=rest[:400]
    for r in selected:r['sample_cohort']=targeted_labels[r['record_id']]
    for r in comparison:r['sample_cohort']='seeded_comparison_random400'
    return selected+comparison, {'available_after_prior_trial_exclusion':len(available),'prior_titles_excluded':len(used),'reverse_boundary':100,'comparison_random':400,'targeted_strata_counts':dict(collections.Counter(targeted_labels.values())),'candidate_pool_counts':{k:len(v) for k,v in boundary_pools.items()},'confusable_pool_count':len(confusable)}

def refs_and_decision(row, matcher, action_v23):
    title=row['title_original'];ft=row['_v24_feature'];boundary=row['_v24_boundary']
    common={'record_id':row['record_id'],'source_record_id':row['source_record_id'],'source_row':row['source_row'],'input_hash':row['input_hash'],'source_title_hash':title_hash(title),'title_original':title,'category_l1_original':row.get('category_l1_original',''),'url_original':row.get('url_original',''),'sample_cohort':row['sample_cohort'],'product_type_surface':ft['head'],'identity_prefix':ft['identity_prefix']}
    if boundary['clear']:
        return common|{'decision':'用不到','reason_code':boundary['code'],'reason':'商品主体与高置信度边界类别匹配。','boundary_evidence_span':boundary['evidence_span'],'action_references':[],'uncertainties':[],'human_confirmed':False}
    # Retrieve only after subject and boundary checks, following the required order.
    retrieved=matcher.retrieve([title])[0]
    candidates=[]
    for j,score in retrieved:
        ref=matcher.model['references'][j]
        relation,tasks,conflict=matcher.relation(ft,ref)
        if relation not in {'SAME_SPECIFIC_TYPE','RELATED_TYPE','SHARED_CONSUMER_NEED'}: continue
        if score<matcher.policy['decision']['potential_min_retrieval']: continue
        v23=action_v23.get(ref['sku'],{})
        candidates.append({'action_sku':ref['sku'],'action_title':ref['name_es_original'],'relation':relation,'shared_need_hypotheses':tasks,
          'action_type_candidate_v23':v23.get('product_type_candidate') if v23.get('status')=='SPECIFIC_SEMANTIC_CANDIDATE' else None,
          'action_use_need_candidates_v23':v23.get('use_need_hypotheses',[]) if v23.get('status')=='SPECIFIC_SEMANTIC_CANDIDATE' else [],
          'retrieval_score':round(score,6),'context_conflict':conflict})
    candidates.sort(key=lambda x:(x['relation']!='SAME_SPECIFIC_TYPE',-x['retrieval_score']))
    candidates=candidates[:3]
    recognized=bool(ft['head'] and ft['specific_type_supported'])
    keep=bool(recognized and candidates and candidates[0]['relation']=='SAME_SPECIFIC_TYPE' and not candidates[0]['context_conflict'] and candidates[0]['shared_need_hypotheses'])
    if keep:
        decision='保留';code='SPECIFIC_TYPE_AND_ACTION_REFERENCE';reason='标题支持具体商品类型，且找到同具体类型的Action参照及用途线索。'
    else:
        decision='观察'
        if boundary['candidate']: code='BOUNDARY_CANDIDATE_UNCERTAIN';reason='出现边界候选线索，但不能确认其描述被售商品主体。'
        elif not recognized: code='PRODUCT_SUBJECT_UNCERTAIN';reason='当前标题不足以可靠识别商品主体，暂不排除。'
        elif not candidates: code='NO_SPECIFIC_ACTION_REFERENCE';reason='没有足够具体的Action参照；缺少参照不构成排除理由。'
        else: code='REFERENCE_RELATION_NOT_SPECIFIC_ENOUGH';reason='存在相近Action参照，但类型或消费需求关系不足以直接保留。'
    return common|{'decision':decision,'reason_code':code,'reason':reason,'boundary_candidate_code':boundary['code'],'boundary_evidence_span':boundary['evidence_span'],'action_references':candidates,'uncertainties':list(dict.fromkeys((['标题推断不是事实'] if ft['task_frames'] else [])+(['未确认可独立使用'] if ft['independent_use']!='TITLE_INDICATES_DEPENDENCY' else []))),'human_confirmed':False}

def insert_exact(c,table,cols,values,key_n):
    key=cols[:key_n];where=' AND '.join(f'{k}=?' for k in key)
    old=c.execute(f"SELECT {','.join(cols)} FROM {table} WHERE {where}",values[:key_n]).fetchone()
    if old is not None:
        if tuple(old)!=tuple(values): raise ValueError('IMMUTABLE_V24_ROW_CONFLICT:'+table)
        return 0
    c.execute(f"INSERT INTO {table}({','.join(cols)}) VALUES({','.join('?' for _ in values)})",values);return 1

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    source=read(SOURCE)
    if p.filehash(source['source_file'])!=source['source_sha256'] or source['source_rows']!=20018: raise RuntimeError('AMAZON_SOURCE_FINGERPRINT_MISMATCH')
    inputs=lines(INPUTS);assert len(inputs)==20018 and len({r['record_id'] for r in inputs})==20018
    matcher=Matcher();action_v23={r['sku']:r for r in lines(V23)}
    selected,sampling=pick_sample(inputs,matcher)
    results=[refs_and_decision(r,matcher,action_v23) for r in selected]
    run_id='amazon-boundary-v24-'+p.digest({'source_sha256':source['source_sha256'],'sample_ids':[r['record_id'] for r in selected],'engine_sha256':p.filehash(__file__),'action_v23_sha256':p.filehash(V23)})[:16]
    # One online backup before any new DB namespace is written.
    backup=OUT/'learning_before_amazon_boundary_v24.sqlite3'
    if not backup.exists():
        src=sqlite3.connect(DB);dst=sqlite3.connect(backup);src.backup(dst);dst.close();src.close()
    with sqlite3.connect(backup) as bc:
        if bc.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or bc.execute('PRAGMA foreign_key_check').fetchall(): raise RuntimeError('V24_BACKUP_INVALID')
    contract={'run_id':run_id,'source_sha256':source['source_sha256'],'action_v23_manifest_sha256':p.filehash(ROOT/'outputs/action_semantic_v23_20261022/final_manifest.json'),'action_v23_results_sha256':p.filehash(V23),'legacy_retrieval_method_sha256':p.filehash(RUN/'effective_method_v23.json'),'engine_sha256':p.filehash(__file__),'sample_ids_sha256':p.digest([r['record_id'] for r in selected]),'sample_size':500,'sampling_seed':SEED,'labels':['保留','观察','用不到'],'human_gold':0,'accuracy':None}
    summary={'run_id':run_id,'counts':dict(collections.Counter(r['decision'] for r in results)),'reason_counts':dict(collections.Counter(r['reason_code'] for r in results)),'boundary_candidate_counts':dict(collections.Counter(r.get('boundary_candidate_code') or r.get('reason_code') for r in results if r.get('boundary_candidate_code') or r['decision']=='用不到')),'cohort_counts':dict(collections.Counter(r['sample_cohort'] for r in results)),'reverse_boundary':sampling,'exact_nonoverlap_prior':True,'source_is_verified_buyable_sku_count':False,'human_gold':0,'accuracy':None,'formal_screening_replaced':False}
    # Output files are versioned and immutable.
    sampled=[{k:v for k,v in r.items() if not k.startswith('_v24_')} for r in selected]
    p.immutable(OUT/'inputs_500.jsonl',sampled,jsonl=True);p.immutable(OUT/'results_500.jsonl',results,jsonl=True)
    p.immutable(OUT/'run_contract.json',contract);p.immutable(OUT/'summary.json',summary)
    rows=[]
    for n,r in enumerate(sorted(results,key=lambda x:(x['decision']!='用不到',x['decision']!='观察',x['record_id'])),1):
        rows.append({'审核编号':f'AB24-{n:03d}','Amazon原始品名':r['title_original'],'一级类目辅助字段':r.get('category_l1_original',''),'实验结论':r['decision'],'判断理由':r['reason'],'边界原因码':r.get('boundary_candidate_code') or (r['reason_code'] if r['decision']=='用不到' else ''),'证据片段':r.get('boundary_evidence_span',''),'Action参照SKU':' / '.join(x['action_sku'] for x in r['action_references']),'Action参照品名':' / '.join(x['action_title'] for x in r['action_references']),'样本层':r['sample_cohort'],'记录ID':r['record_id'],'输入Hash':r['input_hash'],'人工裁定':'','人工原因':'','审核人':''})
    import io
    stream=io.StringIO(newline='');w=csv.DictWriter(stream,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    csv_bytes=('\ufeff'+stream.getvalue()).encode('utf-8');review_path=OUT/'human_review_500.csv'
    if review_path.exists() and review_path.read_bytes()!=csv_bytes: raise RuntimeError('IMMUTABLE_V24_REVIEW_FILE_CONFLICT')
    if not review_path.exists(): review_path.write_bytes(csv_bytes)
    # Append only new V2.4 tables to the shared learning DB.
    c=sqlite3.connect(DB,timeout=90);c.execute('PRAGMA foreign_keys=ON')
    before={t:c.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()}
    c.executescript('''CREATE TABLE IF NOT EXISTS assortment_v24_boundary_runs(run_id TEXT PRIMARY KEY,contract TEXT NOT NULL); CREATE TABLE IF NOT EXISTS assortment_v24_boundary_records(run_id TEXT NOT NULL,record_id TEXT NOT NULL,input_hash TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(run_id,record_id),FOREIGN KEY(run_id) REFERENCES assortment_v24_boundary_runs(run_id));''')
    insert_exact(c,'assortment_v24_boundary_runs',['run_id','contract'],[run_id,p.canonical(contract)],1);c.commit()
    for start in range(0,len(results),100):
        for r in results[start:start+100]:insert_exact(c,'assortment_v24_boundary_records',['run_id','record_id','input_hash','payload'],[run_id,r['record_id'],r['input_hash'],p.canonical(r)],2)
        c.commit()
    integrity=c.execute('PRAGMA integrity_check').fetchone()[0];fk=len(c.execute('PRAGMA foreign_key_check').fetchall())
    after={t:c.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall() if t in before}
    if before!=after or integrity!='ok' or fk: raise RuntimeError('V24_OLD_TABLE_OR_INTEGRITY_FAILURE')
    duplicate_insert=sum(insert_exact(c,'assortment_v24_boundary_records',['run_id','record_id','input_hash','payload'],[run_id,r['record_id'],r['input_hash'],p.canonical(r)],2) for r in results)
    if duplicate_insert: raise RuntimeError('V24_REPLAY_NOT_IDEMPOTENT')
    c.commit();c.close()
    persist={'run_id':run_id,'database':str(DB),'rows_inserted':len(results),'second_import_inserted':duplicate_insert,'old_table_row_counts_unchanged':True,'integrity_check':integrity,'foreign_key_violations':fk,'backup_integrity':'ok','backup_sha256':p.filehash(backup)}
    p.immutable(OUT/'persistence_and_safety.json',persist)
    artifact_names=['inputs_500.jsonl','results_500.jsonl','human_review_500.csv','run_contract.json','summary.json','persistence_and_safety.json']
    manifest={'run_id':run_id,'version':'amazon-boundary-screening-v2.4','source':source,'action_v23_run':'semantic23_d5df918ae3d1e308','sampling':sampling,'summary':summary,'persistence':persist,'limitations':{'human_gold':0,'accuracy':None,'screening_effectiveness_claimed':False,'prices_images_sales_reviews_used':False,'previous_results_modified':False,'sealed_action_holdout_used':False},'artifact_sha256':{name:p.filehash(OUT/name) for name in artifact_names}}
    p.immutable(OUT/'final_manifest.json',manifest)
    print(json.dumps({'run_id':run_id,'summary':summary,'persistence':persist},ensure_ascii=False))

if __name__=='__main__': main()
