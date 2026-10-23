"""Versioned relation-only correction; no retrieval/embedding recomputation.

Package/generic nouns and broad activities cannot establish a concrete type or
consumer-need reference. Preserve base2.2 results and write a separate layer.
"""
import collections,copy,json,sqlite3
from assortment import ROOT,RUN,p,read,lines,connect,exact_insert,Features

def main():
 policy=read(RUN/'frozen_policy.json');f=Features(policy)
 generic={f.stem(w) for w in policy['generic_heads']}|f.compound_heads
 narrow={'drawer_organization','floor_cleaning','dish_cleaning','food_storage','textile_washing','oral_care','vehicle_cleaning'}
 method={'version':'assortment-v2.3-relation-guard-experimental','base_manifest_sha256':p.filehash(RUN/'method_manifest.json'),'guard_code_sha256':p.filehash(__file__),'generic_heads':sorted(generic),'narrow_task_relations':sorted(narrow),'rule':'Keep same specific types; generic same-head is only a broad task, and shared broad activities are not a concrete consumer-need match. No source row or title editing.','no_test_targets_used':True}
 fingerprint=p.digest(method);run_id=read(RUN/'run_identity.json')['run_id'];base=lines(RUN/'full20018_results.jsonl');out=[];audit=[]
 features={r['sku']:r for r in lines(RUN/'action_features.jsonl') if r['state']=='INDEXED_TITLE_ONLY'}
 with connect() as c:
  for old in base:
   r=copy.deepcopy(old);kept=[];removed=[]
   for ref in r['action_references']:
    head=features[ref['action_sku']]['feature']['head'];broad=False
    if ref['relation']=='RELATED_TYPE' and head in generic:broad=True
    if ref['relation']=='SHARED_CONSUMER_NEED' and not set(ref['shared_tasks'])&narrow:broad=True
    if broad:removed.append({**ref,'corrected_relation':'BROAD_TASK_ONLY'})
    else:kept.append(ref)
   r['action_references']=kept
   r['relation_type']=kept[0]['relation'] if kept else ('BROAD_TASK_ONLY' if removed else old['relation_type'])
   if removed:
    r['uncertainties'].append('宽泛活动或套装名词不足以证明具体关联；被降级的检索项不作为可信参照。')
    if not kept:r['reason']+=' 现有参照仅支持宽泛活动，具体参照留空。'
    audit.append({'record_id':r['record_id'],'title_original':r['title_original'],'before_refs':old['action_references'],'after_refs':kept,'demoted':removed,'decision_before':old['decision'],'decision_after':r['decision']})
   r['rules_model_version']=method['version'];r['method_fingerprint']=fingerprint
   r['base_result_hash']=p.digest(old);r['relation_guard_applied']=True
   if r['decision']=='HIGH_MATCH':assert kept and kept[0]['relation']=='SAME_SPECIFIC_TYPE'
   exact_insert(c,'assortment_v2_results',['run_id','record_id','method_version'],{'run_id':run_id,'record_id':r['record_id'],'method_version':fingerprint,'input_hash':r['input_hash'],'payload':p.canonical(r)})
   out.append(r)
   assert r['decision']==old['decision'] and r['input_hash']==old['input_hash']
 p.immutable(RUN/'effective_full20018_v23.jsonl',out,jsonl=True);p.immutable(RUN/'relation_guard_v23_audit.jsonl',audit,jsonl=True);p.immutable(RUN/'effective_method_v23.json',method)
 byid={r['record_id']:r for r in out};comparison=lines(RUN/'three_scheme700_comparison.jsonl')
 for r in comparison:r['C']=byid[r['record_id']]
 p.immutable(RUN/'three_scheme700_comparison_v23.jsonl',comparison,jsonl=True)
 blind=lines(RUN/'blind_review200.jsonl');mapping={r['record_id']:r for r in read(RUN/'private/arm_mapping.json')}
 for r in blind:
  current=byid[r['record_id']];r['expected_C_hash']=p.digest(current)
  for i in [1,2,3]:
   if mapping[r['record_id']]['side'+str(i)]=='C':r['side'+str(i)+'_reason']=current['reason']
 p.immutable(RUN/'blind_review200_v23.jsonl',blind,jsonl=True)
 summary={'effective_version':method['version'],'rows':len(out),'source_identity_or_title_changes':0,'decision_changes':0,'relation_refined_rows':len(audit),'demoted_broad_references':sum(len(r['demoted']) for r in audit),'retrieval_recomputed':0,'embedding_retrained':False,'counts':dict(collections.Counter(r['decision'] for r in out)),'final_reference_review_requirement':'Still needs real-human validation; title/SKU existence alone is insufficient.','review_exposure_note':'Three first rows were visible during workbook layout QA, which exposed the generic-package relation defect. No human targets existed; do not describe all200 as entirely untouched by development. Keep this exposure disclosure.'}
 p.immutable(RUN/'relation_guard_v23_summary.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
