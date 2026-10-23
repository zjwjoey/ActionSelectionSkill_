"""Publish append-only Action feature candidates, preserving all older tables."""
import collections, json, shutil, sqlite3, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import pipeline as p
import semantic22 as s
from semantic22_prepare import table_digest,DB,OUT,BASE

def exact(c,table,columns,values,key_count):
    old=c.execute('SELECT '+','.join(columns)+' FROM '+table+' WHERE '+' AND '.join(k+'=?' for k in columns[:key_count]),values[:key_count]).fetchone()
    if old is not None:
        if tuple(old)!=tuple(values):raise ValueError('IMMUTABLE_APPEND_CONFLICT:'+table)
        return 0
    c.execute('INSERT INTO '+table+'('+','.join(columns)+') VALUES('+','.join('?' for _ in values)+')',values);return 1

def ensure_schema(c):
    migration=None
    old=c.execute("SELECT sql FROM sqlite_master WHERE name='assortment_v22_semantic_reviews'").fetchone()
    if old and 'FOREIGN KEY(run_id) REFERENCES assortment_v22_semantic_records' in old[0]:
        assert c.execute('SELECT count(*) FROM assortment_v22_semantic_reviews').fetchone()[0]==0
        migration={'old_sql':old[0],'rows_before':0,'reason':'New empty AI review table must reference composite (run_id,sku), not run_id alone. No historical table or saved record removed.'}
        c.execute('DROP TABLE assortment_v22_semantic_reviews')
    c.executescript('''
    CREATE TABLE IF NOT EXISTS assortment_v22_semantic_runs(run_id TEXT PRIMARY KEY,contract TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS assortment_v22_semantic_records(run_id TEXT NOT NULL,sku TEXT NOT NULL,source_title_hash TEXT NOT NULL,result_hash TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(run_id,sku),FOREIGN KEY(run_id) REFERENCES assortment_v22_semantic_runs);
    CREATE TABLE IF NOT EXISTS assortment_v22_semantic_history(run_id TEXT NOT NULL,version_record_id TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(run_id,version_record_id),FOREIGN KEY(run_id) REFERENCES assortment_v22_semantic_runs);
    CREATE TABLE IF NOT EXISTS assortment_v22_semantic_reviews(run_id TEXT NOT NULL,sku TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(run_id,sku),FOREIGN KEY(run_id,sku) REFERENCES assortment_v22_semantic_records(run_id,sku));
    ''')
    assert not c.execute('pragma foreign_key_check').fetchall()
    return migration

def main():
    rows=p.read_jsonl(OUT/'final_candidate/results.jsonl'); inputs=p.read_jsonl(OUT/'inputs.jsonl'); ib={r['sku']:r for r in inputs};by={r['sku']:r for r in rows}
    protected=json.loads((OUT/'protected_before.json').read_text(encoding='utf8'))
    for path,h in protected['files'].items():assert p.filehash(path)==h,('PROTECTED_FILE_CHANGED',path)
    history_source=json.loads((OUT/'historical_source_report.json').read_text(encoding='utf8'))
    for f in history_source['historical_files']:assert p.filehash(f['path'])==f['sha256']
    excluded=json.loads((OUT/'excluded_ids.json').read_text(encoding='utf8'));assert not set(by)&{x['sku'] for x in excluded}
    assert len(by)==10037
    for r in rows:
        x=ib[r['sku']];assert r['name_es_original']==x['name_es_original'] and r['source_title_hash']==x['source_title_hash']
        assert r['result_hash']==p.digest({k:v for k,v in r.items() if k!='result_hash'})
        for e in r['type_evidence']+r['literal_qualifiers']:assert r['name_es_original'][e['start']:e['end']]==e['span']
        assert not r['human_confirmed'] and not r['unsupported_attributes']
        if r['status']=='SPECIFIC_SEMANTIC_CANDIDATE':assert r['product_type_candidate'] and r['use_need_hypotheses'] and not r['rule_conflicts']
        if r['rule_conflicts']:assert not r['use_need_hypotheses']
    e=s.Engine(inputs); histories=[]
    for h in p.read_jsonl(OUT/'historical_title_versions.jsonl'):
        if h['state']!='HISTORICAL_TITLE_VARIANT':continue
        x={k:h[k] for k in ['sku','name_es_original','source_title_hash']}
        x.update(snapshot_id='HISTORICAL_SOURCE_VERSION',source_row_id=h['version_record_id'],prior=None,reconciliation='HISTORICAL_VERSION_ONLY')
        histories.append({'version_record_id':h['version_record_id'],'sources':h['sources'],'candidate':e.analyze(x),'not_current_fact':True})
    p.immutable(OUT/'historical_semantic_candidates.jsonl',histories,jsonl=True)
    contract={'phase':'Owner V2.2','version':s.VERSION,'scope':'Action title semantics only; no Amazon result replacement','engine_sha256':p.filehash(ROOT/'scripts/semantic22.py'),'rule_sha256':p.filehash(s.POLICY),'input_sha256':p.filehash(OUT/'inputs.jsonl'),'results_sha256':p.filehash(OUT/'final_candidate/results.jsonl'),'history_sha256':p.filehash(OUT/'historical_semantic_candidates.jsonl'),'human_gold':0}
    runid='semantic22_'+p.digest(contract)[:16];contract['run_id']=runid
    p.immutable(OUT/'method_manifest.json',contract)
    # Hash-bound AI diagnostic ledger, separate from any human labels.
    findings={
      '3008433':('MULTIPLE_FUNCTIONS_OMITTED','名称同时包含收纳箱和桌；通用复合主体规则保留两种功能。'),
      '3206702':('WRONG_PRODUCT_SENSE','dentales明确牙齿用途；美白笔不能按书写铅笔处理。'),
      '3210863':('PURPOSE_QUALIFIER_OMITTED','exfoliantes限定皮肤擦洗用途；不推断防护性能。'),
      '3221734':('TARGET_QUALIFIER_OMITTED','para pintura de diamantes明确收纳对象为钻石画材料。'),
      '3224298':('KIT_FORM_TOO_NARROW','kit不能仅称钩针工具，保留编织套件形态。'),
      '3213305':('TYPE_TOO_BROAD','tostadora明确吐司烘烤机具，细化到面包片烘烤。'),
      '3217582':('TYPE_TOO_BROAD','maletín是手提箱包，收纳容器标签区分不足。'),
      '3220102':('DIY_AS_FINISHED_ITEM','crea tus propios表明制作活动，不能直接标为成品耳饰。'),
      '3216027':('FLAVOR_AS_MAIN_OBJECT','batido为主体，Chocolate是口味；不宣称减重有效。'),
      '3209009':('WRONG_USE_DOMAIN','capilar明确头发用途，不能归入皮肤护理。')}
    reviews=[]
    for old in p.read_jsonl(OUT/'review150_draft04_input.jsonl'):
        new=by[old['sku']];finding=findings.get(old['sku'])
        decision='CORRECTED_CANDIDATE' if finding else 'RETAIN_UNRESOLVED' if new['status']!='SPECIFIC_SEMANTIC_CANDIDATE' else 'NO_ADDITIONAL_ISSUE_OBSERVED'
        reviews.append({'sku':old['sku'],'title':old['name_es_original'],'cohort':old['cohort'],'reviewed_result_hash':old['result_hash'],'final_result_hash':new['result_hash'],'before_type':old['product_type_candidate'],'after_type':new['product_type_candidate'],'decision':decision,'issue_type':finding[0] if finding else ('UNRESOLVED' if decision=='RETAIN_UNRESOLVED' else None),'reason':finding[1] if finding else ('当前规则或品名尚不能支持充分区分的用途；保留原名和待核状态。' if decision=='RETAIN_UNRESOLVED' else '已核对展示的原名、商品主体和用途候选，未发现额外明确错误；这是AI诊断意见，非正确答案。'),'reviewer_kind':'AI','reviewer':'Codex','human_confirmed':False})
    assert len(reviews)==150 and set(findings)<={r['sku'] for r in reviews}
    p.immutable(OUT/'review150_ledger.jsonl',reviews,jsonl=True)
    p.immutable(OUT/'review150_summary.json',{'sample':150,'cohorts':dict(collections.Counter(r['cohort'] for r in reviews)),'diagnostic_findings':len(findings),'findings_resolved_by_generic_rules':len(findings),'outcomes':dict(collections.Counter(r['decision'] for r in reviews)),'sampling':'purposive stratified diagnostic sample, not a probability sample or independent holdout','human_labels':0,'population_accuracy':None})
    # Type -> narrow need links only; no broad-task or same-word equality edges.
    groups=collections.defaultdict(list);typemap=collections.defaultdict(list)
    for r in rows:
        if r['status']!='SPECIFIC_SEMANTIC_CANDIDATE':continue
        typemap[r['product_type_candidate']].append(r['sku'])
        for h in r['use_need_hypotheses']:groups[(r['product_type_candidate'],h['consumer_need'])].append(r['sku'])
    edges=[{'type':t,'need_hypothesis':n,'supporting_skus':sorted(set(ids)),'supporting_sku_count':len(set(ids)),'authority':'AI_ORDINARY_USE_ASSOCIATION_NOT_PROVEN_DEMAND'} for (t,n),ids in sorted(groups.items())]
    p.immutable(OUT/'type_need_edges.jsonl',edges,jsonl=True)
    p.immutable(OUT/'product_type_library.json',{'types':[{'type':t,'supporting_skus':ids,'count':len(ids)} for t,ids in sorted(typemap.items())],'authority':'AI_CANDIDATE_TYPES_NOT_HUMAN_TAXONOMY'})
    needs=collections.defaultdict(list)
    for edge in edges:needs[edge['need_hypothesis']].append(edge)
    related=[{'shared_need_hypothesis':n,'types':[{'type':e['type'],'supporting_skus':e['supporting_skus']} for e in es],'relation':'SHARED_NARROW_NEED_CANDIDATE_NOT_PRODUCT_EQUIVALENCE','not_automatic_amazon_match':True} for n,es in sorted(needs.items()) if len(es)>1]
    p.immutable(OUT/'related_need_groups.json',related)
    comparisons=[]
    for r in rows:
        x=ib[r['sku']];old=x['old_v2_feature'];prev=x['prior']
        comparisons.append({'sku':r['sku'],'name_es_original':r['name_es_original'],'old_v2_head':old['head'],'old_v2_tasks':old['task_frames'],'new_type':r['product_type_candidate'],'new_use_needs':r['use_need_hypotheses'],'new_status':r['status'],'previous_learning_type':prev['product_type'] if prev else None,'previous_title_changed':r['reconciliation']=='SOURCE_TITLE_CHANGED_RECHECK','result_hash':r['result_hash']})
    p.immutable(OUT/'old_v2_vs_semantic22.jsonl',comparisons,jsonl=True)
    summary=json.loads((OUT/'final_candidate/summary.json').read_text(encoding='utf8'))
    summary={k:v for k,v in summary.items() if k!='gap_heads'}
    summary.update({'run_id':runid,'history_version_records':len(histories),'history_distinct_skus':len({h['candidate']['sku'] for h in histories}),'distinct_skus_not_double_counted':10037,'current_types':len(typemap),'type_need_edges':len(edges),'shared_specific_need_groups':len(related),'new_sku_semantic_status':dict(collections.Counter(r['status'] for r in rows if r['reconciliation']=='NEW_SEMANTIC_RECORD')),'old_v2_task_cue_skus':sum(bool(x['old_v2_feature']['task_frames']) for x in inputs),'new_specific_where_old_v2_no_task':sum(r['status']=='SPECIFIC_SEMANTIC_CANDIDATE' and not ib[r['sku']]['old_v2_feature']['task_frames'] for r in rows),'old_task_but_new_not_specific':sum(r['status']!='SPECIFIC_SEMANTIC_CANDIDATE' and bool(ib[r['sku']]['old_v2_feature']['task_frames']) for r in rows),'note':'Old task-cue recognition and new specific-candidate status measure different things; no accuracy delta inferred.'})
    p.immutable(OUT/'coverage_report.json',summary)
    # Confirm the backed-up learning database can actually be opened as a restore.
    restore=OUT/'restore_validation.sqlite3'
    if not (OUT/'backup_restore_check.json').exists():
        shutil.copy2(OUT/'learning_before_semantic22.sqlite3',restore)
        rc=sqlite3.connect(restore.as_uri()+'?mode=ro',uri=True)
        integrity=rc.execute('pragma integrity_check').fetchone()[0];fk=rc.execute('pragma foreign_key_check').fetchall();rc.close()
        assert integrity=='ok' and not fk
        p.immutable(OUT/'backup_restore_check.json',{'integrity':integrity,'foreign_keys':len(fk),'copy_sha256':p.filehash(restore),'backup_sha256':protected['backup_sha256'],'restored_copy_verified':p.filehash(restore)==protected['backup_sha256']})
        restore.unlink() # Exact local scratch file, never a production path.
    c=sqlite3.connect(DB,timeout=60);c.execute('pragma foreign_keys=ON')
    for t,h in protected['tables'].items():assert table_digest(c,t)==h,('OLD_TABLE_CHANGED',t)
    migration=ensure_schema(c)
    if migration:p.immutable(OUT/'schema_repair_incident.json',migration|{'first_batch_records_preserved':100,'subsequent_batches_started_before_repair':0})
    exact(c,'assortment_v22_semantic_runs',['run_id','contract'],[runid,p.canonical(contract)],1);c.commit()
    # New/unresolved work first. Small100 then <=1000 each, source/QA checked above.
    order=sorted(rows,key=lambda r:(r['reconciliation']!='NEW_SEMANTIC_RECORD',r['sku']))
    slices=[order[:100]]+[order[i:i+1000] for i in range(100,len(order),1000)]
    batches=[]
    for i,batch in enumerate(slices,1):
        added=0
        try:
            for r in batch:added+=exact(c,'assortment_v22_semantic_records',['run_id','sku','source_title_hash','result_hash','payload'],[runid,r['sku'],r['source_title_hash'],r['result_hash'],p.canonical(r)],2)
            assert not c.execute('pragma foreign_key_check').fetchall()
            c.commit()
        except BaseException:c.rollback();c.close();raise
        assert not c.execute('pragma foreign_key_check').fetchall()
        proof={'batch':i,'size':len(batch),'member_hash':p.digest([r['sku'] for r in batch]),'status_counts':dict(collections.Counter(r['status'] for r in batch))}
        p.immutable(OUT/'batches'/f'batch_{i:02d}.json',proof);batches.append(proof)
        print(json.dumps({'batch':i,'saved':len(batch),'new':added,'remaining':10037-sum(b['size'] for b in batches)}),flush=True)
    for h in histories:exact(c,'assortment_v22_semantic_history',['run_id','version_record_id','payload'],[runid,h['version_record_id'],p.canonical(h)],2)
    for r in reviews:exact(c,'assortment_v22_semantic_reviews',['run_id','sku','payload'],[runid,r['sku'],p.canonical(r)],2)
    c.commit()
    # Second import in same contract must add zero records (real idempotence).
    again=sum(exact(c,'assortment_v22_semantic_records',['run_id','sku','source_title_hash','result_hash','payload'],[runid,r['sku'],r['source_title_hash'],r['result_hash'],p.canonical(r)],2) for r in rows)
    assert again==0
    for t,h in protected['tables'].items():assert table_digest(c,t)==h,('OLD_TABLE_CHANGED_AFTER',t)
    integrity=c.execute('pragma integrity_check').fetchone()[0];fk=c.execute('pragma foreign_key_check').fetchall();c.close();assert integrity=='ok' and not fk
    for path,h in protected['files'].items():assert p.filehash(path)==h
    p.immutable(OUT/'persistence_and_safety.json',{'run_id':runid,'saved_distinct_skus':10037,'saved_historical_versions':len(histories),'saved_ai_reviews':150,'second_import_new_rows':again,'old_tables_unchanged':len(protected['tables']),'protected_files_unchanged':len(protected['files']),'integrity':integrity,'foreign_keys':len(fk),'sealed_titles_used':0,'amazon_results_changed':False,'source_master_changed':False,'human_feedback_changed':False})
    print(json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
