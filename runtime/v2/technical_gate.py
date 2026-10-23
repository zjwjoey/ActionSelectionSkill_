"""Technical permission for experimental bulk processing, never production QA."""
import json,sqlite3
from assortment import ROOT,RUN,p,read,lines
protocol=read(RUN/'final_trial_protocol.json');protected=read(RUN/'protected_before.json')
assert all(p.filehash(f)==h for f,h in protected['files'].items())
assert all(p.filehash(ROOT/f)==h for f,h in protocol['code_sha256'].items())
assert p.filehash(RUN/'method_manifest.json')==protocol['method_manifest_sha256']
source=read(RUN/'amazon_source_manifest.json');assert p.filehash(source['source_file'])==source['source_sha256']
assert source['source_rows']==20018
inputs={r['record_id']:r for r in lines(RUN/'technical500_inputs.jsonl')};result=lines(RUN/'technical500_results.jsonl')
assert len(result)==len(inputs)==500
all_ref={r['sku']:r for r in lines(RUN/'action_features.jsonl') if r['state']=='INDEXED_TITLE_ONLY'}
for r in result:
 original=inputs[r['record_id']];assert r['input_hash']==original['input_hash'] and r['title_original']==original['title_original']
 assert r['decision'] in {'HIGH_MATCH','POTENTIAL_MATCH','NEEDS_REVIEW','LOW_MATCH'} and not r['human_confirmed']
 if r['decision']=='HIGH_MATCH':
  assert r['action_references'] and r['action_references'][0]['relation']=='SAME_SPECIFIC_TYPE'
  assert r['retail_form']=='NO_EXPLICIT_DEPENDENCY'
 for ref in r['action_references']:assert ref['action_sku'] in all_ref and ref['action_title']==all_ref[ref['action_sku']]['name_es_original']
for name in ['master_d1af859e842adbe1',read(RUN/'action_input_manifest.json')['snapshot_id']]:p.validate_snapshot(name)
with sqlite3.connect((ROOT/'learning_data/action_selection.sqlite3').as_uri()+'?mode=ro',uri=True) as c:
 assert c.execute('pragma integrity_check').fetchone()[0]=='ok' and not c.execute('pragma foreign_key_check').fetchall()
 assert c.execute('select count(distinct sku) from sample_members').fetchone()[0]==5000
 assert c.execute('select count(*) from feedback').fetchone()[0]==0
gate={'gate':'PASS_FOR_EXPERIMENTAL_BULK_ONLY','current_method_sha256':protocol['method_manifest_sha256'],'current_source_sha256':source['source_sha256'],'technical_rows_checked':500,'source_mapping':'PASS','reference_real_sku_and_exact_source_title':'PASS','dependency_never_high':'PASS','targeted_contract_tests':15,'independent_human_labels':0,'semantic_accuracy':None,'ordinary_AI_or_full_context_V10_superiority':'NOT_TESTED','full_bulk_authorization':'User task P4 after technical gate, actual Owner-selected20018 source; not30000','low_match_rows_not_physically_deleted':True}
p.immutable(RUN/'technical_gate.json',gate);print(json.dumps(gate,ensure_ascii=False,indent=2))
