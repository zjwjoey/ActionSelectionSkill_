"""Validate and append one immutable V2.3 candidate run to the shared DB."""
import argparse, collections, json, sqlite3, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import pipeline as p
from semantic22_prepare import table_digest,DB
OLD=ROOT/'outputs/action_semantic_v22_20261022';OUT=ROOT/'outputs/action_semantic_v23_20261022'

def exact(c,table,cols,vals,keyn):
    where=' AND '.join(f'{x}=?' for x in cols[:keyn])
    old=c.execute(f"SELECT {','.join(cols)} FROM {table} WHERE {where}",vals[:keyn]).fetchone()
    if old is not None:
        if tuple(old)!=tuple(vals):raise ValueError('IMMUTABLE_APPEND_CONFLICT:'+table)
        return 0
    c.execute(f"INSERT INTO {table}({','.join(cols)}) VALUES({','.join('?' for _ in vals)})",vals);return 1

def schema(c):
    c.executescript('''
      CREATE TABLE IF NOT EXISTS assortment_v23_semantic_runs(run_id TEXT PRIMARY KEY,contract TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS assortment_v23_semantic_records(run_id TEXT NOT NULL,sku TEXT NOT NULL,source_title_hash TEXT NOT NULL,result_hash TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(run_id,sku),FOREIGN KEY(run_id) REFERENCES assortment_v23_semantic_runs(run_id));
      CREATE TABLE IF NOT EXISTS assortment_v23_semantic_history(run_id TEXT NOT NULL,version_record_id TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(run_id,version_record_id),FOREIGN KEY(run_id) REFERENCES assortment_v23_semantic_runs(run_id));
      CREATE TABLE IF NOT EXISTS assortment_v23_semantic_reviews(run_id TEXT NOT NULL,sku TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(run_id,sku),FOREIGN KEY(run_id,sku) REFERENCES assortment_v23_semantic_records(run_id,sku));
    ''')
    assert not c.execute('pragma foreign_key_check').fetchall()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--label',required=True);a=ap.parse_args()
    draft=OUT/a.label;rows=p.read_jsonl(draft/'results.jsonl');before=p.read_jsonl(OLD/'final_candidate/results.jsonl')
    assert len(rows)==len(before)==10037 and len({r['sku'] for r in rows})==10037
    src={r['sku']:r for r in p.read_jsonl(OLD/'inputs.jsonl')}; oldby={r['sku']:r for r in before}
    excluded={r['sku'] for r in json.loads((OLD/'excluded_ids.json').read_text(encoding='utf8'))};assert not set(src)&excluded
    protected=json.loads((OUT/'protected_before.json').read_text(encoding='utf8'))
    for path,h in protected['files'].items():assert p.filehash(path)==h,('PROTECTED_FILE_CHANGED',path)
    scope=[];changed=[]
    for old,new in zip(before,rows):
        x=src[old['sku']]
        assert new['sku']==old['sku'] and new['name_es_original']==x['name_es_original'] and new['source_title_hash']==x['source_title_hash']
        assert new['result_hash']==p.digest({k:v for k,v in new.items() if k!='result_hash'})
        for e in new.get('type_evidence',[])+new.get('literal_qualifiers',[]):assert new['name_es_original'][e['start']:e['end']]==e['span']
        assert not new.get('human_confirmed',False) and not new.get('unsupported_attributes')
        if old['status'] not in {'RULE_COVERAGE_GAP','FEATURE_TOO_BROAD'}:
            assert old==new,('FROZEN_NON_TARGET_CHANGED',old['sku'])
        else:
            if new.get('version')=='action-semantic-deepening-v2.3' and new.get('basis')=='V23_GENERIC_TITLE_RULE':
                decision='PROPOSE_NEW_SPECIFIC_CANDIDATE' if new['status']=='SPECIFIC_SEMANTIC_CANDIDATE' else 'RULE_MATCHED_STILL_BROAD_OR_CONFLICT'
            else:decision='RETAIN_PRIOR_UNRESOLVED'
            scope.append({'sku':old['sku'],'snapshot_id':old['snapshot_id'],'source_row_id':old['source_row_id'],'source_title_hash':old['source_title_hash'],'prior_result_hash':old['result_hash'],'v23_result_hash':new['result_hash'],'name_es_original':old['name_es_original'],'prior_status':old['status'],'v23_status':new['status'],'decision':decision,'rule_id':new.get('rule_id'),'product_type_candidate':new.get('product_type_candidate'),'type_evidence':new.get('type_evidence',[]),'use_need_hypotheses':new.get('use_need_hypotheses',[]),'uncertainty_codes':new.get('uncertainty_codes',[]),'rule_conflicts':new.get('rule_conflicts',[]),'history_signature_evidence':new.get('history_signature_evidence'),'human_confirmed':False,'review_method':'AI_RULE_CANDIDATE_NOT_GOLD'})
            if new['result_hash']!=old['result_hash']:changed.append({'sku':old['sku'],'title':old['name_es_original'],'before_hash':old['result_hash'],'after_hash':new['result_hash'],'old_status':old['status'],'new_status':new['status'],'basis':new.get('basis'),'rule_id':new.get('rule_id')})
    assert len(scope)==2992
    # The website notes are a separate source lane and must never be used as a
    # title-only semantic label.
    notes=json.loads((OUT/'official_verification_notes.json').read_text(encoding='utf8'))
    assert notes['authority']=='CURRENT_OFFICIAL_PAGE_TEXT_NOT_TITLE_ONLY_TRAINING_LABEL'
    candidate_skus={r['sku'] for r in rows}
    for q in notes['records']:assert q['sku'] in candidate_skus and q['human_confirmed'] is False
    statuses=collections.Counter(r['status'] for r in rows);target_statuses=collections.Counter(r['v23_status'] for r in scope)
    type_map=collections.defaultdict(set);need_map=collections.defaultdict(set);type_need=collections.defaultdict(set)
    for r in rows:
        typ=r.get('product_type_candidate')
        if typ:type_map[typ].add(r['sku'])
        if r['status']=='SPECIFIC_SEMANTIC_CANDIDATE' and typ:
            for h in r.get('use_need_hypotheses',[]):
                need_map[(typ,h['consumer_need'])].add(r['sku']);type_need[h['consumer_need']].add((typ,r['sku']))
    type_library={'authority':'AI_CANDIDATE_TYPES_NOT_HUMAN_TAXONOMY','types':[{'type':t,'sku_count':len(ids),'supporting_skus':sorted(ids)} for t,ids in sorted(type_map.items())]}
    edges=[{'type':t,'need_hypothesis':n,'sku_count':len(ids),'supporting_skus':sorted(ids),'authority':'ORDINARY_USE_HYPOTHESIS_NOT_PROVEN_DEMAND'} for (t,n),ids in sorted(need_map.items())]
    related=[{'shared_need_hypothesis':n,'types':[{'type':t,'supporting_skus':sorted({sku for tt,sku in pairs if tt==t})} for t in sorted({tt for tt,_ in pairs})],'relation':'SHARED_NEED_CANDIDATE_NOT_PRODUCT_EQUIVALENCE','not_automatic_match':True} for n,pairs in sorted(type_need.items()) if len({t for t,_ in pairs})>1]
    runid='semantic23_'+p.digest({'version':'action-semantic-deepening-v2.3','results_sha256':p.filehash(draft/'results.jsonl'),'rules_sha256':p.filehash(draft/'rules.json'),'backup_sha256':protected['backup_sha256']})[:16]
    summary=json.loads((draft/'summary.json').read_text(encoding='utf8'))|{'run_id':runid,'new_specific_candidates_in_2992':sum(x['decision']=='PROPOSE_NEW_SPECIFIC_CANDIDATE' for x in scope),'retained_unresolved_in_2992':sum(x['decision']!='PROPOSE_NEW_SPECIFIC_CANDIDATE' for x in scope),'v23_target_statuses':dict(target_statuses),'result_payloads_changed':len(changed),'website_evidence_records':len(notes['records']),'human_gold':0,'accuracy':None,'sealed_titles_read':0,'source_anomalies_included':0}
    p.immutable(OUT/'final_candidate/results.jsonl',rows,jsonl=True)
    p.immutable(OUT/'final_candidate/scope_review_2992.jsonl',scope,jsonl=True)
    p.immutable(OUT/'final_candidate/changes.jsonl',changed,jsonl=True)
    p.immutable(OUT/'final_candidate/product_type_library.json',type_library)
    p.immutable(OUT/'final_candidate/type_need_edges.jsonl',edges,jsonl=True)
    p.immutable(OUT/'final_candidate/related_need_groups.json',related)
    p.immutable(OUT/'final_candidate/summary.json',summary)
    contract={'phase':'Action title semantics V2.3; scoped 1,390 RULE_COVERAGE_GAP + 1,602 FEATURE_TOO_BROAD','version':'action-semantic-deepening-v2.3','run_id':runid,'baseline_run_id':json.loads((OLD/'method_manifest.json').read_text(encoding='utf8'))['run_id'],'baseline_results_sha256':p.filehash(OLD/'final_candidate/results.jsonl'),'rules_sha256':p.filehash(draft/'rules.json'),'engine_sha256':p.filehash(ROOT/'scripts/semantic23.py'),'results_sha256':p.filehash(OUT/'final_candidate/results.jsonl'),'target_scope_sha256':p.filehash(OUT/'final_candidate/scope_review_2992.jsonl'),'website_evidence_sha256':p.filehash(OUT/'official_verification_notes.json'),'human_gold':0,'amazon_results_changed':False,'master_modified':False,'sealed_holdout_used':False}
    contract['run_id']=runid;p.immutable(OUT/'method_manifest.json',contract)
    c=sqlite3.connect(DB,timeout=60);c.execute('pragma foreign_keys=on');schema(c)
    # All pre-existing tables remain bit-for-bit equivalent; the V2.3 run uses
    # a new namespace in the same shared learning database.
    for t,h in protected['tables'].items():assert table_digest(c,t)==h,('OLD_TABLE_CHANGED_BEFORE',t)
    exact(c,'assortment_v23_semantic_runs',['run_id','contract'],[runid,p.canonical(contract)],1);c.commit()
    for start in range(0,len(rows),1000):
        for r in rows[start:start+1000]:exact(c,'assortment_v23_semantic_records',['run_id','sku','source_title_hash','result_hash','payload'],[runid,r['sku'],r['source_title_hash'],r['result_hash'],p.canonical(r)],2)
        assert not c.execute('pragma foreign_key_check').fetchall();c.commit()
    for x in scope:exact(c,'assortment_v23_semantic_reviews',['run_id','sku','payload'],[runid,x['sku'],p.canonical(x)],2)
    c.commit()
    again=sum(exact(c,'assortment_v23_semantic_records',['run_id','sku','source_title_hash','result_hash','payload'],[runid,r['sku'],r['source_title_hash'],r['result_hash'],p.canonical(r)],2) for r in rows)
    assert again==0
    for t,h in protected['tables'].items():assert table_digest(c,t)==h,('OLD_TABLE_CHANGED_AFTER',t)
    integrity=c.execute('pragma integrity_check').fetchone()[0];fk=c.execute('pragma foreign_key_check').fetchall();c.close();assert integrity=='ok' and not fk
    for path,h in protected['files'].items():assert p.filehash(path)==h,('PROTECTED_FILE_CHANGED_AFTER',path)
    persist={'run_id':runid,'database':str(DB),'version_records':len(rows),'target_review_records':len(scope),'idempotent_second_insert_count':again,'integrity_check':integrity,'foreign_key_violations':len(fk),'old_tables_unchanged':len(protected['tables']),'protected_files_unchanged':len(protected['files']),'website_evidence_separate':True,'master_changed':False,'amazon_results_changed':False,'human_gold_added':0}
    p.immutable(OUT/'persistence_and_safety.json',persist)
    (OUT/'V2.3_执行报告.md').write_text(f'''# ActionSelectionSkill V2.3 执行报告\n\n- 版本：`{runid}`（`action-semantic-deepening-v2.3`）\n- 覆盖输入：10,037 个有效 SKU；34 个来源异常及 50 个密封 holdout 未参与。\n- 修复范围：1,390 条 `RULE_COVERAGE_GAP` 与 1,602 条 `FEATURE_TOO_BROAD`，共 2,992 条。\n- 新增具体标题候选：{summary['new_specific_candidates_in_2992']} 条；仍保留未决：{summary['retained_unresolved_in_2992']} 条。未决按 SKU + source title hash 追踪，见 `final_candidate/scope_review_2992.jsonl`。\n- 全库状态：`{dict(statuses)}`。已有 7,045 条（含原 Specific 和 Information-insufficient）保持原 payload/hash；V2.2 输出未覆盖。\n- 官网：{len(notes['records'])} 条当前 Action 商品页证据单独保存于 `official_verification_notes.json`，没有混入标题规则或标题候选。\n- 学习库：在共享 SQLite 中追加 V2.3 命名空间；旧 25 张表摘要保持不变。`integrity_check={integrity}`，外键违规 {len(fk)}，同批重放新增 0 条。\n- 人工标准：0 条；AI 候选不是 Gold，未计算准确率。\n- 与 Amazon：结果未改写。当前版本不能证明 Amazon 选品效果提升。\n\n分类、用途与需求都是候选；详见 `final_candidate/product_type_library.json` 和 `type_need_edges.jsonl`。规则运行结果不是独立语义准确率。\n''',encoding='utf8')
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':main()
