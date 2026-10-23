"""Full source/row/reference reconciliation, cache resume and legacy protection."""
import collections,csv,json,sqlite3,time
from assortment import ROOT,RUN,p,read,lines,screen
source=read(RUN/'amazon_source_manifest.json');protected=read(RUN/'protected_before.json')
inputs=lines(RUN/'amazon_inputs.jsonl');result=lines(RUN/'full20018_results.jsonl')
assert len(inputs)==len(result)==20018
assert len({r['record_id'] for r in inputs})==len({r['record_id'] for r in result})==20018
assert {r['record_id'] for r in inputs}=={r['record_id'] for r in result}
byid={r['record_id']:r for r in inputs};refs={r['sku']:r for r in lines(RUN/'action_features.jsonl') if r['state']=='INDEXED_TITLE_ONLY'}
for r in result:
 original=byid[r['record_id']]
 for k in ['source_record_id','source_row','title_original','input_hash','category_l1_original','url_original']:assert original[k]==r[k]
 if r['decision']=='HIGH_MATCH':assert r['retail_form']=='NO_EXPLICIT_DEPENDENCY' and r['action_references'] and r['action_references'][0]['relation']=='SAME_SPECIFIC_TYPE'
 for ref in r['action_references']:
  assert ref['action_sku'] in refs and ref['action_title']==refs[ref['action_sku']]['name_es_original']
  assert ref['action_source_row_id']==refs[ref['action_sku']]['source_row_id']
# Verify the actual original CSV title and source group for every row, not just
# self-consistency between derived exports.
with open(source['source_file'],encoding='utf-8-sig',newline='') as f:
 for ordinal,(raw,r) in enumerate(zip(csv.DictReader(f),inputs),2):
  assert r['source_row']==ordinal and r['title_original']==raw[source['fields']['title']]
  assert r['source_record_id']==raw[source['fields']['original_record_id']]
assert p.filehash(source['source_file'])==source['source_sha256']

_,resume=screen(inputs,'full20018');assert resume['new_computed']==0 and resume['cached']==20018
p.immutable(RUN/'resume_verification.json',resume)
backup=RUN/'learning_before_v2.sqlite3';db=ROOT/'learning_data/action_selection.sqlite3'
preserved={}
def row_hashes(c,table):
 return {p.digest(list(r)) for r in c.execute('SELECT * FROM '+table)}
with sqlite3.connect(backup.as_uri()+'?mode=ro',uri=True) as before,sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as after:
 for (table,) in before.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
  old=row_hashes(before,table);current=row_hashes(after,table)
  # Only an additional Master snapshot/source projection was authorized on old
  # source tables. All earlier rows themselves must still exist byte-for-byte.
  preserved[table]=old<=current if table in {'snapshots','source_rows','products'} else old==current
 assert all(preserved.values()),preserved
 assert after.execute('pragma integrity_check').fetchone()[0]=='ok' and not after.execute('pragma foreign_key_check').fetchall()
 assert after.execute('select count(distinct sku) from sample_members').fetchone()[0]==5000
 assert after.execute('select count(*) from analyses').fetchone()[0]==9906
 assert after.execute('select count(*) from feedback').fetchone()[0]==0
 assert before.execute('pragma integrity_check').fetchone()[0]=='ok' and not before.execute('pragma foreign_key_check').fetchall()
legacy_snapshot=p.validate_snapshot('master_d1af859e842adbe1')
current_snapshot=p.validate_snapshot(read(RUN/'action_input_manifest.json')['snapshot_id'])
assert all(p.filehash(f)==h for f,h in protected['files'].items())
full_counts=collections.Counter(r['decision'] for r in result)
for file,count in [('Amazon20018_全量实验筛选.csv',20018),('高度符合_实验候选.csv',833),('保留研究_实验候选.csv',13264),('待核实_实验候选.csv',5921),('明显不符_实验候选.csv',0)]:
 with (RUN/'delivery'/file).open(encoding='utf-8-sig',newline='') as f:actual=list(csv.DictReader(f))
 assert len(actual)==count
independent={r['record_id'] for r in lines(RUN/'independent200_inputs.jsonl')}
assert not independent & {r['record_id'] for r in lines(RUN/'technical500_inputs.jsonl')}
assert not independent & {r['record_id'] for r in lines(RUN/'prototype_1_before_technical_gate/technical500_inputs.jsonl')}
report={'source_rows_checked_against_actual_csv':20018,'source_group_title_url_input_hash_parity':'PASS','all_reference_ids_and_titles_bind_to_real_action_rows':'PASS','reference_semantic_relevance':'NOT_INDEPENDENTLY_VALIDATED','all_rows_preserved':True,'source_file_hash_unchanged':True,'protected_files_unchanged':len(protected['files']),'old_tables_preserved':preserved,'old_action_sample_members':5000,'old_action_analysis_history':9906,'old_human_feedback':0,'primary_master_written':False,'sqlite_integrity':'ok','foreign_key_errors':0,'backup_integrity':'ok','resume_new_analysis':0,'resume_cache_hits':20018,'independent200_has_no_technical_record_overlap':True,'master_snapshots':{'original':legacy_snapshot['snapshot_id'],'v2_current':current_snapshot['snapshot_id']},'formal_accuracy':None,'counts':dict(full_counts)}
p.immutable(RUN/'data_safety_reconciliation.json',report)
print(json.dumps(report,ensure_ascii=False,indent=2))
