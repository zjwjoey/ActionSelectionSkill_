"""Keep final title-only AI opinions separate from frozen program decisions."""
import collections,csv,json
import run_subject_v2513 as run
from assortment import lines,norm,read
def main():
 out=run.OUT;raw=list(csv.DictReader((out/'ai_review_20_raw.tsv').open(encoding='utf8'),delimiter='\t'))
 sources=lines(out/'inputs_20.jsonl');program=lines(out/'results_20.jsonl');assert len(raw)==len(sources)==20
 rows=[]
 for i,(a,s,p) in enumerate(zip(raw,sources,program),1):
  assert a['id']==f'S{i:03d}' and norm(a['evidence']) in norm(s['title_original'])
  rows.append({'record_id':s['record_id'],'input_hash':s['input_hash'],'review_id':a['id'],'title_original':s['title_original'],
   'ai_subject_cn':a['subject_cn'],'source_evidence':a['evidence'],'audit_status':a['audit_status'],'program_decision':p['decision'],
   'ai_proposal':'观察' if a['audit_status']=='SOURCE_OFFER_SCOPE_UNCERTAIN' else p['decision'],
   'review_origin':'CODEX_AI_POST_RUN_NOT_GOLD','human_confirmed':False,'gold_label':None,'program_sha256':run.b24.p.filehash(out/'results_20.jsonl')})
 run.save('ai_review_20_bound.jsonl',rows,True)
 run.csvsave('new20_ai_review.csv',[{'编号':r['review_id'],'原始品名':r['title_original'],'AI识别主体':r['ai_subject_cn'],'原文证据':r['source_evidence'],
  '程序结论':r['program_decision'],'AI复核建议':r['ai_proposal'],'问题类别':r['audit_status'],'人工裁定':'','审核人':''} for r in rows])
 focus=lines(out/'focus_50.jsonl')
 run.csvsave('focus_50.csv',[{'编号':r['review_id'],'原始品名':r['after']['title_original'],'V2.5.6程序':r['before']['decision'],'本轮程序':r['after']['decision'],
  '主体':r['after']['subject']['class_code'],'原因':r['after']['reason_code'],'AI角色缓存':r['after']['subject'].get('role_resolution',''),
  '参照SKU':' / '.join(x['action_sku'] for x in r['after']['action_references']),'参照原文':' / '.join(x['action_title'] for x in r['after']['action_references']),'人工裁定':''} for r in focus])
 summary={'reviewed':20,'origin':'AI_POST_RUN_NOT_HUMAN_GOLD','issues':dict(collections.Counter(r['audit_status'] for r in rows)),
  'program_counts':dict(collections.Counter(r['program_decision'] for r in rows)),'ai_proposal_counts':dict(collections.Counter(r['ai_proposal'] for r in rows)),
  'human_gold':0,'accuracy':None,'false_exclusion_rate':None,'unresolved_offer_scope':['S015'],'full_expansion':False,
  'decision':'KEEP_FROZEN_CANDIDATE_AND_OBSERVATION_QUEUE','reason':'Known role/reference defects improved, but coverage and title-only offering ambiguity remain. No formal rollout.'}
 run.save('ai_audit_summary.json',summary)
 identity=read(out/'summary.json')['run_id'];frozen=read(out/'frozen_contract.json')
 print(json.dumps(summary|run.store.persist(out,identity,frozen,{'ai_review20':rows}),ensure_ascii=False))
if __name__=='__main__':main()
