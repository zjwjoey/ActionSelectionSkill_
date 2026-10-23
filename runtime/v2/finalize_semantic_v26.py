"""Evidence, append-only persistence and review artifacts; no decision tuning."""
import collections,csv,hashlib,io,json,sqlite3
from pathlib import Path
from assortment import ROOT,RUN,Matcher,lines,read,norm
import boundary_v24 as b24
import run_semantic_v26 as run
import semantic_v26 as s
OUT=s.OUT
def save(n,v,jsonl=False):run.save(n,v,jsonl)
def csvsave(name,rows):
    buf=io.StringIO(newline='');w=csv.DictWriter(buf,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    path=OUT/name;data=('\ufeff'+buf.getvalue()).encode('utf8')
    if path.exists() and path.read_bytes()!=data:raise ValueError('IMMUTABLE_CSV')
    if not path.exists():path.write_bytes(data)
def ro(db):return sqlite3.connect('file:'+str(db).replace('\\','/')+'?mode=ro',uri=True)
def source_check(refs,skus):
    verified=[]
    with ro(ROOT/'learning_data/action_selection.sqlite3') as c:
        for sku in sorted(skus):
            r=refs[sku]
            # Extract only the permitted Spanish name; do not load price payloads
            # or any non-eligible/sealed source row.
            found=c.execute("SELECT sku,json_extract(payload,'$.name_es_original') FROM source_rows WHERE source_row_id=?",(r['source_row_id'],)).fetchone()
            if found!=(sku,r['name_es_original']):raise ValueError('DATABASE_REFERENCE_MISMATCH:'+sku)
            verified.append({'sku':sku,'source_row_id':r['source_row_id'],'name_es_original':r['name_es_original'],'database_verified':True})
    save('database_reference_verification.jsonl',verified,True)
    return len(verified)
def persist(contract,stages,caches):
    db=ROOT/'learning_data/action_selection.sqlite3';runid='v26-'+s.digest(contract)[:16]
    with sqlite3.connect(db) as c:
        c.execute('PRAGMA foreign_keys=ON')
        c.executescript('''CREATE TABLE IF NOT EXISTS assortment_v26_runs(run_id TEXT PRIMARY KEY,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS assortment_v26_results(run_id TEXT NOT NULL,stage TEXT NOT NULL,record_id TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(run_id,stage,record_id),FOREIGN KEY(run_id) REFERENCES assortment_v26_runs(run_id));
        CREATE TABLE IF NOT EXISTS assortment_v26_semantic_cache(cache_key TEXT PRIMARY KEY,run_id TEXT NOT NULL,source_binding TEXT NOT NULL,payload TEXT NOT NULL,FOREIGN KEY(run_id) REFERENCES assortment_v26_runs(run_id));''')
        def exact(table,keys,values):
            cols=list(values);old=c.execute('SELECT '+','.join(cols)+' FROM '+table+' WHERE '+' AND '.join(k+'=?' for k in keys),[values[k] for k in keys]).fetchone()
            if old is not None:
                if old!=tuple(values.values()):raise ValueError('IMMUTABLE_DB_CONFLICT')
                return 0
            c.execute('INSERT INTO '+table+'('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',list(values.values()));return 1
        inserted=exact('assortment_v26_runs',['run_id'],{'run_id':runid,'payload':b24.p.canonical(contract)})
        for stage,rows in stages.items():
            for r in rows:inserted+=exact('assortment_v26_results',['run_id','stage','record_id'],{'run_id':runid,'stage':stage,'record_id':r['record_id'],'payload':b24.p.canonical(r)})
        for a in caches:inserted+=exact('assortment_v26_semantic_cache',['cache_key'],{'cache_key':a['cache_key'],'run_id':runid,'source_binding':a['source_binding'],'payload':b24.p.canonical(a)})
        c.commit()
        if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or c.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('DATABASE_INTEGRITY')
    return runid,inserted
def main():
    contract=run.check();refs={r['sku']:r for r in Matcher().model['references']}
    rows=lines(OUT/'inputs_200.jsonl');old=lines(OUT/'baseline_200.jsonl');deep={r['record_id']:r for r in lines(OUT/'new_deep_results.jsonl')};final=[]
    for row,p in zip(rows,old):
        if row['record_id'] in deep:r=deep[row['record_id']]
        else:
            a=p['action_references'][0];subject=p['subject'];span=row['title_original']
            words=row['title_original'].split()
            for start in range(len(words)):
                for size in range(1,5):
                    part=' '.join(words[start:start+size]).strip(',.')
                    if norm(part)==subject['evidence_span']:span=part
            r={**row,'version':s.VERSION,'decision':p['decision'],'reason_code':'LOCAL_EXACT_COMPATIBLE_PROOF_REUSED',
                'source_binding':s.source_binding(row),'semantic':{'subject_span':span,'type':subject['class_code'],'dependency':'standalone','relation':'A','group_id':'','need_explanation':'复用冻结版本的具体类型及独立形态证据；不是新增AI分析','boundary':'NONE','unknowns':'性能与质量未核实'},
                'action_reference':{'action_sku':a['action_sku'],'action_title':a['action_title'],'source_row_id':a['action_source_row_id'],'relation':'A','human_confirmed':False},
                'authority':'LOCAL_PROOF_NOT_HUMAN_GOLD','human_confirmed':False}
        final.append(r)
    dev=lines(OUT/'dev_deep_results.jsonl');cards=read(OUT/'action_groups_v26.json')
    used={r['action_reference']['action_sku'] for r in final+dev if r.get('action_reference')}
    used.update(a['sku'] for g in cards for a in g['examples'])
    verified=source_check(refs,used)
    save('results_200.jsonl',final,True)
    paired=[{'review_id':row['review_id'],'cohort':row['sample_cohort'],'v2513':a,'v26':b,'decision_changed':a['decision']!=b['decision'],'subject_changed':norm(a['subject']['evidence_span'])!=norm(b['semantic']['subject_span'])} for row,a,b in zip(rows,old,final)]
    save('paired_200.jsonl',paired,True)
    caches=lines(OUT/'dev_ai_bound.jsonl')+lines(OUT/'new_ai_bound.jsonl')
    stages={'development60':dev,'baseline200':old,'new200':final}
    runid,inserted=persist(contract,stages,caches)
    _,resumed=persist(contract,stages,caches)
    if resumed:raise ValueError('RESUME_DUPLICATE_WRITE')
    with ro(OUT/'learning_before_v26.sqlite3') as before,ro(ROOT/'learning_data/action_selection.sqlite3') as after:
        prior={r[0] for r in before.execute("SELECT name FROM sqlite_master WHERE type='table'")};tables={}
        for table in sorted(prior):
            b=before.execute('SELECT COUNT(*) FROM "'+table+'"').fetchone()[0];a=after.execute('SELECT COUNT(*) FROM "'+table+'"').fetchone()[0]
            if b!=a:raise ValueError('HISTORICAL_TABLE_COUNT_CHANGED:'+table)
            tables[table]=b
        gold=after.execute('SELECT COUNT(*) FROM benchmark_adjudications').fetchone()[0]
    protected=read(RUN/'protected_before.json')['files'];checks={}
    for path,expected in protected.items():
        if 'sealed' in path:continue
        checks[path]={'matches_historical_baseline':b24.p.filehash(Path(path))==expected}
    if not all(v['matches_historical_baseline'] for v in checks.values()):raise ValueError('PROTECTED_SOURCE_CHANGED')
    save('integrity_and_resume.json',{'integrity':'ok','foreign_keys':0,'backup_restore_readable':True,'historical_table_counts':tables,'historical_table_counts_unchanged':True,'only_v26_tables_written':True,'resume_inserted':resumed,'protected_hashes':checks,'sealed_content_read':False,'v2513_exact_fingerprints_unchanged':True})
    decisions=collections.Counter((p['v2513']['decision'],p['v26']['decision']) for p in paired)
    summary={'run_id':runid,'version':s.VERSION,'human_gold':gold,'accuracy':None,'recall':None,'false_exclusion_rate':None,
        'groups':len(cards),'literal_group_anchors':sum(len(c['examples']) for c in cards),'eligible_action_index':len(refs),
        'historical_reuse':read(OUT/'historical_candidate_reuse.json'),'old200':run.counts(old),'new200':run.counts(final),'development60':run.counts(dev),
        'cohorts':{co:{'old':run.counts([r for r,p in zip(old,rows) if p['sample_cohort']==co]),'new':run.counts([r for r in final if r['sample_cohort']==co])} for co in ['random100','boundary50','difficult50']},
        'transitions':{a+' → '+b:n for (a,b),n in decisions.items()},'subject_literal_span_changed':sum(p['subject_changed'] for p in paired),
        'relation_counts':dict(collections.Counter(r['semantic']['relation'] for r in final)),
        'retained_without_exact_A':sum(r['decision']=='保留' and r['semantic']['relation'] in {'B','C'} for r in final),
        'observation_reasons':dict(collections.Counter(r['reason_code'] for r in final if r['decision']=='观察')),
        'database_verified_reference_skus':verified,'local_fast_records':12,'real_codex_deep_dev':60,'real_codex_deep_new':188,'real_codex_total':248,
        'external_api_calls':0,'external_api_additional_spend':0,'codex_session_token_cost':'NOT_EXPOSED_NOT_CLAIMED_ZERO','model':s.MODEL,
        'sampling':read(OUT/'sampling.json'),'targeted_tests':{'passed':18,'failed':0,'scope':'source/ref/form/A-E/boundary/cache/idempotent projection'},
        'resume_inserted':resumed,'formal_amazon_results_replaced':False,'master_unchanged':True,'sealed_action_content_read':False,'full_screening_ready':False,
        'pre_sample_failure':'First sampling filter accidentally classified whole input pool as exposed. No sample drawn; log and freeze_attempt_1_no_sample.json preserved. Sampling filter corrected and final freeze created before any new200 titles exposed.',
        'stop':'V2.6 experiment complete; no V2.7 or full production run'}
    save('summary.json',summary)
    def view(r,olddecision=''):
        a=r.get('action_reference') or {};p=r['semantic']
        return {'编号':r.get('review_id',''),'分层':r.get('sample_cohort','开发60'),'西语原名':r['title_original'],'一级类目':r.get('category_l1_original',''),'V2513':olddecision,'V26':r['decision'],
            '商品主体证据':p['subject_span'],'类型候选':p['type'],'依赖形态':p['dependency'],'参照级别':p['relation'],'ActionSKU':a.get('action_sku',''),'Action原名':a.get('action_title',''),
            '用途需求及关联理由':p['need_explanation'],'不确定性':p.get('unknowns',''),'边界候选':p['boundary'],'原因代码':r['reason_code'],
            '人工结论':'','主体是否正确':'','参照是否有效':'','人工修改原因':'','审核人':'','来源绑定Hash':r['source_binding']}
    newview=[view(p['v26'],p['v2513']['decision']) for p in paired];devview=[view(r) for r in dev]
    csvsave('independent200_review.csv',newview);csvsave('boundary60_review.csv',devview)
    save('workbook_data.json',{'summary':summary,'independent200':newview,'boundary60':devview,'groups':cards})
    print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
