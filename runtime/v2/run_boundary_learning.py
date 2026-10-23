"""Read-only latest merged snapshot import and phased boundary-v0 experiment."""
from __future__ import annotations
import collections,csv,datetime,hashlib,io,json,random,re,sqlite3,sys
from pathlib import Path
from assortment import ROOT,RUN,Matcher,lines,read,norm
import boundary_v24 as b24
import boundary_v25 as b25
import boundary_learning as b
import subject_v2513 as legacy
import run_semantic_v26 as v26run
OUT=b.OUT
SOURCE=Path('F:/AmazonESBestseller/交付文件/20261022/今日快照合并_214818_82be/今日快照_合并去重_25152条.csv')
MANIFEST=SOURCE.parent/'合并核对.json'
def save(n,v,jsonl=False):b.save(n,v,jsonl)
def backup():
    OUT.mkdir(parents=True,exist_ok=True);v26run.check()
    backup_path=OUT/'learning_before_boundary_v0.sqlite3'
    if not backup_path.exists():
        with sqlite3.connect(ROOT/'learning_data/action_selection.sqlite3') as src,sqlite3.connect(backup_path) as dst:src.backup(dst)
    with sqlite3.connect(backup_path) as c:
        if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or c.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('BACKUP_INVALID')
    files=list(p for p in v26run.OUT.iterdir() if p.is_file() and not p.name.startswith('~$') and p.suffix not in {'.sqlite3','.zip'})+[RUN/'retrieval_index.joblib',ROOT/'outputs/staged_5000_20261022/cumulative5000_candidates.jsonl',Path('F:/ActionSKUTracker/runtime/master/Action_Master.xlsx')]
    save('protected_before.json',{'files':{str(p):b24.p.filehash(p) for p in files},'sealed_content_read':False,'backup_recovery_read':'PASS','git_initialized':False})
def ingest():
    OUT.mkdir(parents=True,exist_ok=True);manifest=read(MANIFEST);sha=b24.p.filehash(SOURCE)
    if sha!=manifest['csv_sha256'] or not all(i['snapshot_review']['passed'] for i in manifest['inputs']):raise ValueError('SOURCE_MANIFEST_MISMATCH')
    csv.field_size_limit(10000000);rows=[];titles=[];urls=[];ids=[];cats=collections.Counter();traceable=0
    with SOURCE.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames
        for number,r in enumerate(reader,2):
            title=r['product_title_es'];cat=r['amazon_category_l1'];raw=digest_input={'title_original':title,'category_l1_original':cat}
            row={'record_id':f'B0_{sha[:12]}_{number:06d}','source_row':number,'source_file_sha256':sha,'snapshot_id':'amazon-merged-20261022-'+sha[:16],
                'input_hash':b.digest(raw),'title_original':title,'category_l1_original':cat,'url_original':r.get('normalized_product_url',''),
                'source_run_ids':r.get('merged_run_ids',''),'source_candidate_id':r.get('candidate_id',''),'source_observation_id':r.get('observation_id',''),
                'source_group_id':r.get('target_review_group',''),'asin_hint_unconfirmed':r.get('asin_url_hint',''),'source_row_hash':b.digest(r),'identity':'SOURCE_LINK_RECORD_NOT_VERIFIED_BUYABLE_SKU'}
            rows.append(row);titles.append(b24.title_hash(title));urls.append(row['url_original']);ids.append(row['record_id']);cats[cat]+=1
            if row['source_candidate_id'] and row['source_observation_id'] and row['source_run_ids']:traceable+=1
    if len(rows)!=manifest['csv_rows'] or len(set(ids))!=len(rows):raise ValueError('IMPORT_COUNT_OR_ID_ERROR')
    save('source_records.jsonl',rows,True)
    save('source_report.json',{'selected_file':str(SOURCE),'format':'CSV UTF-8 BOM','sha256':sha,'bytes':SOURCE.stat().st_size,'columns':fields,'column_count':len(fields),
        'original_batch_observations':manifest['raw_observations'],'qualified_batch_observations':manifest['qualified_observations'],'imported_source_records':len(rows),
        'valid_title_records':sum(bool(r['title_original'].strip()) for r in rows),'unique_source_record_ids':len(set(ids)),
        'unique_normalized_titles':len(set(titles)),'duplicate_title_extra_records':len(titles)-len(set(titles)),
        'duplicate_title_groups':sum(n>1 for n in collections.Counter(titles).values()),'distinct_url_strings':len(set(urls)),
        'nonempty_category_records':sum(n for k,n in cats.items() if k),'category_count':sum(bool(k) for k in cats),'category_counts':dict(cats),
        'traceable_source_records':traceable,'conservative_groups_reported':manifest['conservative_groups'],'verified_buyable_skus':0,
        'source_runs':[{k:i[k] for k in ['run_id','database','first_capture','last_capture','snapshot_acceptance']} for i in manifest['inputs']],
        'rejected_candidate':{'path':'F:/AmazonESBestseller/交付文件/20261022/今日快照合并_214722_7ae1','reason':'Explicit incomplete-export marker; CSV only2769bytes'},
        'not_old20018_fallback':True,'rows_deleted_or_title_deduplicated':0,'screening_fields':['product_title_es','amazon_category_l1'],'price_not_used':True})

def prior_titles():
    forbidden=b24.prior_title_hashes()|b25.focus_titles()
    for p in (ROOT/'v2/runs').rglob('inputs_*.jsonl'):
        if OUT in p.parents:continue
        forbidden.update(b24.title_hash(r['title_original']) for r in lines(p) if r.get('title_original'))
    forbidden.update(b24.title_hash(r['title_original']) for r in lines(v26run.OUT/'development_60_inputs.jsonl'))
    return forbidden
def sample(stage):
    name=f'inputs_{stage}.jsonl'
    if (OUT/name).exists():return
    if stage==200:check_freeze()
    forbidden=prior_titles()
    if stage==200:forbidden|={b24.title_hash(r['title_original']) for r in lines(OUT/'inputs_500.jsonl')}
    pool=[r for r in lines(OUT/'source_records.jsonl') if r['title_original'].strip() and b24.title_hash(r['title_original']) not in forbidden]
    rng=random.Random(2026102300+stage);rng.shuffle(pool);used=set();selected=[];quota=300 if stage==500 else 100;enriched=100 if stage==500 else 50
    for label,n,pattern in [('random',quota,None),('boundary',enriched,r'lavadora|frigorifico|secadora|aire acondicionado|industrial|robot|torno|maquina|mueble|armario|escritorio|termo'),('difficult',enriched,r'compatible|recambio|repuesto|funda|soporte|para|incluye|kit|mecanismo|control')]:
        got=0
        for r in pool:
            key=b24.title_hash(r['title_original'])
            if key in used or pattern and not re.search(pattern,norm(r['title_original'])):continue
            selected.append(dict(r,sample_cohort=label,review_id=('L' if stage==500 else 'T')+f'{len(selected)+1:03d}'));used.add(key);got+=1
            if got==n:break
        if got!=n:raise ValueError('SAMPLE_SHORTFALL:'+label)
    save(name,selected,True);save(f'sampling_{stage}.json',{'seed':2026102300+stage,'size':stage,'random_first':True,'cohorts':dict(collections.Counter(r['sample_cohort'] for r in selected)),'prior_title_overlap':0,'excluded_title_count':len(forbidden),'no_population_extrapolation_from_enriched_strata':True})
def codehashes():
    return {str(p):b24.p.filehash(p) for p in [Path(__file__),Path(b.__file__),b.POLICY,ROOT/'tests/test_boundary_learning.py',OUT/'semantic_500.jsonl']}|v26run.fingerprints()
def freeze():
    if (OUT/'frozen_boundary_v0.json').exists():check_freeze();return
    save('frozen_boundary_v0.json',{'version':b.VERSION,'frozen_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'fingerprints':codehashes(),'status':'EXPERIMENTAL_CANDIDATE_NOT_PUBLISHED','human_gold':0})
def check_freeze():
    f=read(OUT/'frozen_boundary_v0.json')
    if f['fingerprints']!=codehashes():raise ValueError('FROZEN_BOUNDARY_CHANGED')
    return f
def semantic_file(stage):return OUT/f'semantic_{stage}.jsonl'
def analyze(stage):
    if stage==200:check_freeze()
    rows=lines(OUT/f'inputs_{stage}.jsonl');e=legacy.Engine();base=e.analyze_many(rows)
    save(f'local_v26_fast_{stage}.jsonl',base,True)
    sem={r['record_id']:r for r in lines(semantic_file(stage))} if semantic_file(stage).exists() else {}
    refs={r['sku']:r for r in e.refs};results=[]
    for row,p in zip(rows,base):
        result=b.analyze(row,p,sem.get(row['record_id']));b.verify_reference(result,refs);results.append(result)
    # Initial pass is preserved if an AI review follows, never overwritten.
    name=f'results_{stage}'+('_semantic' if sem else '_initial')+'.jsonl';save(name,results,True)
    print(json.dumps({'stage':stage,'results':name,'counts':dict(collections.Counter(r['decision'] for r in results)),'actual_codex_semantic_records':len(sem)},ensure_ascii=False))
    return rows,base,results
def show(stage):
    rows=lines(OUT/f'inputs_{stage}.jsonl');base=lines(OUT/f'local_v26_fast_{stage}.jsonl')
    # A small source-bound review panel: outside candidates first, then novel
    # machines and unresolved normal examples. Selection is not random accuracy.
    result=lines(OUT/f'results_{stage}_initial.jsonl');rank={'范围外':0,'灰区':1,'未知':2,'范围内':3}
    order=sorted(range(len(rows)),key=lambda i:(rank[result[i]['scope']],i));selected=order[:60 if stage==500 else 40]
    save(f'codex_review_panel_{stage}.json',{'review_ids':[rows[i]['review_id'] for i in selected],'reason':'risk-priority diagnostic panel; not independent human accuracy sample','actual_analysis_not_yet_claimed':True})
    for i in selected:print(rows[i]['review_id']+'|'+result[i]['subject']['class_code']+'|'+rows[i]['title_original'])
if __name__=='__main__':
    command=sys.argv[1]
    if command=='prepare':backup();ingest();sample(500)
    elif command=='freeze':freeze()
    elif command=='sample200':sample(200)
    elif command.startswith('analyze'):analyze(int(command[7:]))
    elif command.startswith('show'):show(int(command[4:]))
