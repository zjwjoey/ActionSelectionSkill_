"""Build auditable P1.1 candidates, source traces and reference-free retests."""
import csv
import json
import random
import re
import sqlite3
import unicodedata
from collections import Counter,defaultdict
from pathlib import Path

from openpyxl import load_workbook
import benchmark
import storage
from pipeline import ROOT,FIELDS,canonical,digest,filehash,immutable,validate_snapshot,STRATA

SID='master_d1af859e842adbe1'
BATCH='pilot100_c2217cd5173d'
OUT=ROOT/'reports'/'p11'

# Audit records for the 22 changes, not product-classification rules.
CORRECTION_ASSESSMENTS={
 '3005084':('待人工确认','GRANULARITY_POLICY','瓶子主体明确，但一般盛装是否满足本轮用途粒度，应由人确认；不能把状态调整称为已证实语义错误。'),
 '3212583':('AI判断错误','TAG_SCOPE_DRIFT','铺设用品的兴趣创作标签超出原标签定义；属于标签适用边界错误候选。'),
 '3225301':('AI判断错误','UNSUPPORTED_STRUCTURE','无限效果不直接给出镜片结构；v1多加镜这一机制词，需人确认合理命名粒度。'),
 '2532127':('待人工确认','COMMON_USE_BOUNDARY','砂纸可以用于手工。移除创作标签是范围取舍，并不能单凭改动证明原标签错误。'),
 '3224709':('AI判断错误','TAG_SCOPE_DRIFT','冰雪气候与节庆混用，原标签定义边界不清；车用场景本身仍是普通语境推断。'),
 '3016463':('品名信息不足','POLYSEMY','Cazo器型存在解释空间；v2保守处理是候选决定，不是已确认正确答案。'),
 '3210047':('待人工确认','TAXONOMY_POLICY','首饰盒归个人配饰或家庭收纳都可能合理；需要先确认统一分类口径。'),
 '3218745':('待人工确认','BRAND_CONTEXT_DEPENDENCE','Spa语境下沐浴用途有合理性，但不能当字面事实；礼赠主类同样不是唯一正确答案。'),
 '3205705':('待人工确认','TERMINOLOGY_GRANULARITY','创口贴与敷料是细分层次差异；需确认标准词与可接受同义范围。'),
 '3209499':('待人工确认','TAG_DEFINITION_AMBIGUITY','生日是否算节庆取决于标签定义；不能把季节/节庆的复合标签直接当成语义错误。'),
 '3219926':('待人工确认','DECORATION_VS_DIY','名称可描述装饰包袋，也可能是手工套件。v1的DIY和v2的成品携带都不能直接晋升标准答案。'),
 '3012135':('待人工确认','TERMINOLOGY_GRANULARITY','钩织造型比玩偶宽泛；更保守的词不自动等于经核实的正确词。'),
 '2515506':('品名信息不足','POLYSEMY','Cubo有桶/立方体等词义。保留已知词与不确定性，不借来源部门作唯一消歧。'),
 '3201171':('待人工确认','TERMINOLOGY_GRANULARITY','recambio可指替换件或补充件，补充装译法是否过窄需人工认定。'),
 '3211983':('待人工确认','BRAND_CONTEXT_DEPENDENCE','LEGO Technic系列支持模型解读，但属于常识性系列语境；需确认允许使用的推断强度。'),
 '3205082':('AI判断错误','TAG_SCOPE_DRIFT','普通骰子游戏被贴兴趣创作标签，不符合创作活动定义。'),
 '3225710':('AI判断错误','TAG_SCOPE_DRIFT','发射游戏用品被贴兴趣创作标签；应区分娱乐与创作。'),
 '3220769':('品名信息不足','DOMAIN_UNSPECIFIED','Barco仅指船，系列名不足以在本协议下唯一确立玩具用途。'),
 '3224679':('待人工确认','TAXONOMY_POLICY','充电数据线可能是组合类目而非逐商品功能断言；需先统一类目名的事实含义。'),
 '3202233':('AI判断错误','TAG_SCOPE_DRIFT','gaming支持游戏用途，不能因此推导创作活动。'),
 '2550709':('待人工确认','TERMINOLOGY_GRANULARITY','蓄冷块可能是习惯译名，蓄冷用品更宽泛；尚不能证明形状或原译错误。'),
 '2578510':('待人工确认','SCENARIO_AMBIGUITY','帽形音乐舞动商品是否可佩戴不能只凭名称确认；两版场景均需人审。'),
}

AMBIGUITIES={
 '3217559':('TYPE_AMBIGUOUS',['Pomo词形'],['旋钮/把手','其他Pomo词义'],'缺少被修饰对象或更完整的西语名称。'),
 '3016463':('TYPE_AMBIGUOUS',['厨房器具词Cazo'],['小煮锅','舀勺/其他器型'],'需确认器型或接受保留多义的标准标签。'),
 '3203250':('BRAND_ONLY',['Celebrations名称本身'],['品牌/系列','未给商品种类'],'需商品名词，不能靠品牌记忆补巧克力。'),
 '2515506':('TYPE_AMBIGUOUS',['Cubo词形'],['桶','立方体或其他含义'],'需限定对象或用途词，不能根据抽样类目消歧。'),
 '3220769':('DOMAIN_AMBIGUOUS',['船Barco'],['玩具/模型船','其他船主题商品'],'需明确类型/用途词，不能只凭系列名晋升玩具事实。'),
 '3207774':('DOMAIN_AMBIGUOUS',['球发射器'],['游戏玩具','宠物抛球','运动训练'],'需明确使用对象或场景。'),
 '3221083':('DOMAIN_AMBIGUOUS',['Chicken Steak Sticks文字'],['供人食用','供猫或狗等动物'],'需明确食用对象；风味名称不证明配方。'),
 '3006788':('DOMAIN_AMBIGUOUS',['Estuche盒袋/套装','completo完整这一修饰'],['文具用品','其他盒袋或套装'],'需明确内部物品/用途，完整并不等于含齐文具。'),
 '3220659':('DOMAIN_AMBIGUOUS',['Estuche盒袋','de lujo名称修饰'],['文具盒','其他盒袋套装'],'需明确容纳对象，不能把豪华当质量事实。'),
}


def write_csv(path,rows,fields):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for x in rows:w.writerow({k:canonical(x.get(k)) if isinstance(x.get(k),(dict,list)) else x.get(k,'') for k in fields})


def trace_sources(items,manifest):
    ids={x['sku'] for x in items if 'SOURCE_LANGUAGE_INVALID' in x.get('uncertainty_codes',[])}
    assert len(ids)==6
    master=Path(manifest['source']);before=filehash(master)
    wb=load_workbook(master,read_only=True,data_only=True)
    # Read once; no workbook.save, no production repository initialization.
    sheet_rows={sn:{i:r for i,r in enumerate(wb[sn].values,1)} for sn in ['02_SKU_ES_CURRENT','08_LONG_TERM_MASTER']};wb.close()
    dbpath=Path(r'F:\ActionSKUTracker\runtime\db\action_tracker.db')
    c=sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;c.execute('pragma query_only=on');c.execute('begin')
    result=[]
    try:
        with storage.connection(ROOT) as local:
            for sku in sorted(ids):
                refs=[]
                for row in local.execute('select payload from source_rows where sku=?',(sku,)):
                    x=json.loads(row[0]);ref=x['source_reference'];sn=ref['sheet'];r=sheet_rows[sn][ref['excel_row']]
                    value=r[2] if sn=='02_SKU_ES_CURRENT' else r[8]
                    assert value==x['name_es_original']
                    refs.append({'source_row_id':x['source_row_id'],'snapshot_name':x['name_es_original'],'current_master_cell_value':value,'source_reference':ref,'cell_verified':True})
                r=c.execute("select p.name_es as products_name_es,es.name as localization_es_name,es.source,es.updated_at,es.last_commit_id from products p left join product_localizations es on p.official_sku=es.official_sku and es.language='es' where p.official_sku=?",(sku,)).fetchone()
                hist=[]
                for v in c.execute('select source_version_id,source_hash,source_fields_json,created_at,source_run_id from translation_source_versions where official_sku=? order by created_at',(sku,)):
                    f=json.loads(v['source_fields_json']);hist.append({'source_version_id':v['source_version_id'],'source_hash':v['source_hash'],'stored_name':f.get('name_es',f.get('name')),'created_at':v['created_at'],'source_run_id':v['source_run_id']})
                current=dict(r) if r else {};alt=current.get('localization_es_name')
                usable=bool(alt and re.search('[A-Za-zÀ-ÿ]',alt) and not re.search('[\u3400-\u9fff]',alt))
                result.append({'sku':sku,'issue':'来源字段异常','semantic_error_denominator_eligible':False,'source_references':refs,'current_database_readonly':current,'registry_name_versions':hist,
                               'alternative_name_candidate':alt if usable else None,'alternative_verified_as_gold':False,
                               'trace_conclusion':'长期总表与products.name_es一致为中文；本地化西语名称另有候选，存在投影/历史字段差异。' if usable else '长期总表与products.name_es为中文；本次查得的本地化及来源版本未提供西语名称。',
                               'next_action':'人工核对历史来源后建立新来源版本；当前冻结输入不替换。'})
    finally:c.rollback();c.close()
    assert filehash(master)==before==manifest['source_before']['sha256']
    return result


def family(title):
    text=''.join(ch for ch in unicodedata.normalize('NFKD',title.casefold()) if not unicodedata.combining(ch))
    words=[w for w in re.findall(r'[a-z]+',text) if w not in {'de','del','la','el','los','las','con','para','y','un','una'}]
    return ' '.join(words[:2]),set(words)


def reserve_holdout(products,pilot):
    names={x['name_es_normalized'].casefold() for x in pilot};groups={family(x['name_es_normalized'])[0] for x in pilot};tokens=[family(x['name_es_normalized'])[1] for x in pilot]
    eligible=[]
    for x in products:
        title=x['name_es_normalized'];g,ts=family(title)
        if x['sku'] in {v['sku'] for v in pilot} or title.casefold() in names or g in groups or not ts or re.search('[\u3400-\u9fff]',title):continue
        if any(len(ts&t)/max(1,len(ts|t))>=0.8 for t in tokens):continue
        eligible.append(x)
    rng=random.Random(2026102211);eligible.sort(key=lambda x:x['sku']);rng.shuffle(eligible)
    bycat=defaultdict(list)
    for x in eligible:bycat[STRATA.get(x['category_original'],x['category_original'])].append(x)
    selected=[];seen_groups=set();seen_titles=set()
    while len(selected)<50:
        added=False
        for cat,pool in sorted(bycat.items()):
            while pool:
                x=pool.pop();g,_=family(x['name_es_normalized'])
                if g in seen_groups or x['name_es_normalized'].casefold() in seen_titles:continue
                seen_groups.add(g);seen_titles.add(x['name_es_normalized'].casefold());selected.append(x);added=True;break
            if len(selected)==50:break
        if not added:raise ValueError('INSUFFICIENT_ISOLATED_HOLDOUT')
    sealed=[{'sku':x['sku'],'source_row_id':x['source_row_id'],'title_sha256':digest(x['name_es_normalized']),'source_stratum':STRATA.get(x['category_original'],x['category_original'])} for x in selected]
    plan={'plan_id':'unseen50-design-20261022','seed':2026102211,'reserved_count':50,'executed':False,'labels_created':0,'semantic_predictions_created':0,'eligible_pool_count':len(eligible),
          'isolation':['different SKU','different normalized title','different first-two-content-word family','Jaccard title-token overlap below 0.8'],
          'limits':'Family filter is a lexical proxy; independent human split audit is still required before execution.',
          'protocol':'Freeze classifier/prompt/rules hash before exposing titles. Obtain independent human targets before scoring. Run once in a separate session with names only; no tuning on these 50. Report abstention and source quality separately from accuracy.',
          'reserved_ids':sealed}
    immutable(ROOT/'learning_data/p11/sealed_unseen50_plan.json',plan)
    with storage.connection(ROOT) as c:storage.append_exact(c,'benchmark_holdout_plans','plan_id',plan['plan_id'],(storage.encode(plan),),('payload',))
    return {k:v for k,v in plan.items() if k!='reserved_ids'}


def main():
    OUT.mkdir(parents=True,exist_ok=True);manifest=validate_snapshot(SID)
    history=storage.history(ROOT,BATCH);v1={x['sku']:x for x in history if x['rules_version']=='name-semantics-v1'};v2={x['sku']:x for x in history if x['rules_version']=='name-semantics-v2'}
    assert len(history)==200 and len(v1)==len(v2)==100
    inputs={x['sku']:x for x in storage.members(ROOT,BATCH,True)}
    pilot=storage.members(ROOT,BATCH)
    policy=json.loads((ROOT/'rules/benchmark/p11-evaluation-v1.json').read_text(encoding='utf-8'))
    storage.register_rule(ROOT,policy['version'],digest({'benchmark_policy':policy}),{'benchmark_policy':policy})
    corrections=[];candidates=[];ambiguities=[]
    trace=trace_sources(list(v2.values()),manifest);trace_by={x['sku']:x for x in trace}
    corrected={sku for sku,x in v2.items() if x['ai_review']['decision']=='CORRECTED'}
    assert corrected==set(CORRECTION_ASSESSMENTS)
    for sku,after in sorted(v2.items()):
        old=v1[sku];meta=after['ai_review'];source_bad=sku in trace_by
        problem='来源字段异常' if source_bad else ('品名信息不足' if sku in AMBIGUITIES else ('待人工确认' if after['confidence']=='中' else '判断正确'))
        reason=meta['reason'];root_cause='SOURCE_LANGUAGE_INVALID' if source_bad else ('NO_NEW_ISSUE_IDENTIFIED' if problem=='判断正确' else 'INFERENCE_REQUIRES_REVIEW')
        if sku in CORRECTION_ASSESSMENTS:
            problem,root_cause,reason=CORRECTION_ASSESSMENTS[sku]
            changes={f:{'v1':old[f],'v2':after[f]} for f in FIELDS if f not in ['confidence','review_status','evidence'] and old[f]!=after[f]}
            corrections.append({'sku':sku,'name_es_original':inputs[sku]['name_es_original'],'problem_type_proposed':problem,'root_cause':root_cause,'changed_fields':changes,
                                'assessment':reason,'confirmed_error':False,'v2_is_gold':False,'human_confirmation':'待人工确认'})
        if sku in AMBIGUITIES:
            code,supported,alternatives,missing=AMBIGUITIES[sku]
            ambiguities.append({'sku':sku,'name_es_original':inputs[sku]['name_es_original'],'reason_code':code,'supported_information':supported,'unresolved_alternatives':alternatives,
                                'missing_evidence_or_decision':missing,'forbidden_shortcut':'不得用原类目、中文、价格或品牌记忆选择一个答案。','human_confirmation':'待人工确认'})
            if sku not in CORRECTION_ASSESSMENTS:reason=missing
        row={'sku':sku,'phase':benchmark.PHASE,'batch_id':BATCH,'input':inputs[sku],'input_hash':digest(inputs[sku]),'source_row_id':inputs[sku]['source_row_id'],
             'v1_original_judgment':old,'v2_ai_correction':after,'candidate_labels':{f:after[f] for f in FIELDS},
             'problem_type_proposed':problem,'problem_type_is_confirmed':False,'root_cause':root_cause,'assessment_basis':reason,
             'source_anomaly':source_bad,'semantic_score_eligible_if_human_confirmed':not source_bad,'local_source_trace':trace_by.get(sku),
             'label_authority':'AI_CANDIDATE','human_confirmed':False,'human_problem_type':'','human_target_labels':{},'human_reviewer':'','human_evidence_reference':''}
        row['candidate_hash']=digest(row);row['candidate_id']='p11_'+digest([BATCH,sku,row['candidate_hash']])[:24];candidates.append(row)
    assert len(ambiguities)==9
    immutable(ROOT/'learning_data/p11/standard_candidates_100.jsonl',candidates,jsonl=True)
    benchmark.register_candidates(ROOT,BATCH,candidates)
    immutable(OUT/'correction_analysis_22.json',corrections);immutable(OUT/'source_anomalies_6.json',trace);immutable(OUT/'information_insufficient_9.json',ambiguities)
    fields=['sku','candidate_id','candidate_hash','name_es_original','problem_type_proposed','assessment_basis','v1_original_judgment','v2_ai_correction','candidate_labels','source_row_id','source_reference','source_anomaly','label_authority','human_problem_type','human_target_labels','human_confirmed_fields','human_decision','human_reviewer_kind','human_reviewer','human_evidence_reference']
    source_refs={x['sku']:x['source_reference'] for x in pilot}
    audit_rows=[{**x,'name_es_original':x['input']['name_es_original'],'source_reference':source_refs[x['sku']],
                 'human_decision':'PENDING','human_confirmed_fields':[],'human_reviewer_kind':''} for x in candidates]
    write_csv(OUT/'100条标准候选_人工审核表.csv',audit_rows,fields)
    write_csv(OUT/'22条修正原因分析.csv',corrections,['sku','name_es_original','problem_type_proposed','root_cause','changed_fields','assessment','confirmed_error','v2_is_gold','human_confirmation'])
    write_csv(OUT/'9条信息不足分析.csv',ambiguities,['sku','name_es_original','reason_code','supported_information','unresolved_alternatives','missing_evidence_or_decision','forbidden_shortcut','human_confirmation'])
    write_csv(OUT/'6条来源异常追踪.csv',trace,['sku','issue','source_references','current_database_readonly','registry_name_versions','alternative_name_candidate','alternative_verified_as_gold','trace_conclusion','next_action'])
    before=benchmark.evaluate_predictions(ROOT,v1,inputs);after=benchmark.evaluate_predictions(ROOT,v2,inputs)
    immutable(OUT/'retest_before_100.json',before);immutable(OUT/'retest_after_100.json',after)
    empty=benchmark.gold(ROOT);assert not empty
    immutable(OUT/'formal_human_confirmed_benchmark.jsonl',empty,jsonl=True)
    holdout=reserve_holdout(storage.load_products(ROOT,SID),pilot);immutable(OUT/'independent_holdout_plan.json',holdout)
    report={'phase':'P1.1','scope_unique_skus':100,'problem_types_proposed':dict(Counter(x['problem_type_proposed'] for x in candidates)),
            'proposal_status':'ALL_REQUIRE_HUMAN_ADJUDICATION','correction22_proposed_dispositions':dict(Counter(x['problem_type_proposed'] for x in corrections)),
            'correction22_root_causes':dict(Counter(x['root_cause'] for x in corrections)),'confirmed_ai_errors':0,'source_anomalies':6,
            'local_alternative_names_found_not_gold':sum(bool(x['alternative_name_candidate']) for x in trace),'ambiguous_titles':9,'formal_gold_records':0,
            'before_contract_pass':before['contract_pass'],'after_contract_pass':after['contract_pass'],'semantic_accuracy_before':before['semantic_field_accuracy'],
            'semantic_accuracy_after':after['semantic_field_accuracy'],'accuracy_reason':after['accuracy_reason'],
            'fresh_model_inference_executed':False,'retest_type':'Replay the same 100 stored predictions through the revised benchmark/quality contract; no self-answers used as truth.',
            'holdout_reserved_not_executed':50,'original_analysis_rows':len(history),'expanded_to_500':False,'master_sha256':filehash(manifest['source'])}
    with storage.connection(ROOT) as c:storage.append_exact(c,'benchmark_runs','run_id','p11-retest-20261022',(storage.encode(report),),('payload',))
    immutable(OUT/'p11_summary.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
