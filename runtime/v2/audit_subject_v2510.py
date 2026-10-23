"""Source-bound AI audit, never human gold; append to the same experiment DB."""
import csv,collections,json
import run_subject_v2510 as run
from assortment import lines,norm,read
def main():
 out=run.OUT;raw=list(csv.DictReader((out/'ai_review_50_raw.tsv').open(encoding='utf8'),delimiter='\t'))
 inputs=lines(out/'inputs_50.jsonl');results=lines(out/'results_50.jsonl');assert len(raw)==len(inputs)==50
 rows=[]
 for i,(a,s,r) in enumerate(zip(raw,inputs,results),1):
  assert a['id']==f'P{i:03d}' and norm(a['evidence']) in norm(s['title_original'])
  rows.append({'record_id':s['record_id'],'input_hash':s['input_hash'],'review_id':a['id'],'title_original':s['title_original'],'ai_subject_cn':a['subject_cn'],'source_evidence':a['evidence'],
   'audit_status':a['audit_status'],'program_decision':r['decision'],'ai_proposal':r['decision'],'human_confirmed':False,'gold_label':None,
   'review_origin':'CODEX_AI_POST_RUN','program_result_sha256':run.b24.p.filehash(out/'results_50.jsonl')})
 run.save('ai_review_50_bound.jsonl',rows,True)
 run.csvsave('new50_ai_review.csv',[{'编号':r['review_id'],'原始品名':r['title_original'],'AI识别主体':r['ai_subject_cn'],'原文证据':r['source_evidence'],'程序结论':r['program_decision'],'审查类型':r['audit_status'],'人工裁定':'','审核人':''} for r in rows])
 summary={'reviewed':50,'origin':'AI_POST_RUN_NOT_HUMAN_GOLD','status_counts':dict(collections.Counter(r['audit_status'] for r in rows)),
  'program_counts':dict(collections.Counter(r['program_decision'] for r in rows)),'remaining_subject_errors':['P040','P042'],'unproven_reference_subtypes':['P026','P032','P034','P048'],
  'human_gold':0,'accuracy':None,'false_exclusion_rate':None,'new_exclusions':0,'full_expansion':False,
  'decision':'KEEP_FROZEN_EXPERIMENTAL_CANDIDATE','reason':'Remaining role errors and uncovered types; no fresh exclusions; precision/recall not established.'}
 run.save('ai_audit_summary.json',summary)
 frozen=read(out/'frozen_contract.json');runid=read(out/'summary.json')['run_id']
 print(json.dumps(summary|run.store.persist(out,runid,frozen,{'ai_review50':rows}),ensure_ascii=False))
if __name__=='__main__':main()
