"""Verify the relation layer without revising frozen rules."""
import collections,json,sqlite3
from assortment import ROOT,RUN,WORK,p,read,lines
method=read(RUN/'effective_method_v23.json');frozen=read(RUN/'protected_before.json')
assert method['guard_code_sha256']==p.filehash(WORK/'relation_guard_v23.py')
original={r['record_id']:r for r in lines(RUN/'full20018_results.jsonl')};effective=lines(RUN/'effective_full20018_v23.jsonl');refs={r['sku']:r for r in lines(RUN/'action_features.jsonl') if r['state']=='INDEXED_TITLE_ONLY'}
for r in effective:
 before=original[r['record_id']]
 assert all(r[k]==before[k] for k in ['title_original','input_hash','source_record_id','source_row','url_original','category_l1_original','decision'])
 for ref in r['action_references']:
  rf=refs[ref['action_sku']];assert rf['name_es_original']==ref['action_title']
  if ref['relation']=='RELATED_TYPE':assert rf['feature']['head'] not in set(method['generic_heads'])
  if ref['relation']=='SHARED_CONSUMER_NEED':assert set(ref['shared_tasks'])&set(method['narrow_task_relations'])
 assert r['base_result_hash']==p.digest(before)
assert all(p.filehash(f)==h for f,h in frozen['files'].items())
with sqlite3.connect((ROOT/'learning_data/action_selection.sqlite3').as_uri()+'?mode=ro',uri=True) as c:
 assert c.execute('pragma integrity_check').fetchone()[0]=='ok' and not c.execute('pragma foreign_key_check').fetchall()
 assert c.execute('select count(*) from sample_members').fetchone()[0]==5000
 assert c.execute('select count(*) from analyses').fetchone()[0]==9906
summary={'effective_version':method['version'],'rows':len(effective),'input_identity_title_decision_parity':True,'source_bound_references':True,'generic_package_not_labeled_related_type':True,'broad_activity_not_labeled_specific_need':True,'known_human_labels':0,'reference_semantic_accuracy':None,'sqlite_integrity':'ok','foreign_key_errors':0,'old5000_preserved':True,'counts':dict(collections.Counter(r['decision'] for r in effective)),'rows_with_concrete_reference':sum(bool(r['action_references']) for r in effective),'potential_without_concrete_reference':sum(r['decision']=='POTENTIAL_MATCH' and not r['action_references'] for r in effective),'declared_limit':'The200 review set was sampled separately, but three preview rows informed this final relation guard. It is not a pristine independent accuracy benchmark.'}
p.immutable(RUN/'effective_reconciliation.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))
