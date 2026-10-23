"""Bind the final 50 Codex audit opinions without creating human labels."""
import collections,csv,hashlib,json,sqlite3
from pathlib import Path
import run_subject_v256 as run
from assortment import norm,lines,ROOT,read

def main():
 out=run.OUT;sources=lines(out/'inputs_50.jsonl');results=lines(out/'results_50.jsonl')
 raw=list(csv.DictReader((out/'ai_audit_50_raw.tsv').open(encoding='utf8'),delimiter='\t'))
 assert len(raw)==50 and len({r['id'] for r in raw})==50
 records=[]
 for i,(source,result,a) in enumerate(zip(sources,results,raw),1):
  assert a['id']==f'K{i:03d}' and norm(a['evidence']) in norm(source['title_original'])
  assert result['input_hash']==source['input_hash'] and result['record_id']==source['record_id']
  decision='观察' if a['audit_status']=='REFERENCE_TOO_BROAD' else result['decision']
  records.append({'review_id':a['id'],'record_id':source['record_id'],'input_hash':source['input_hash'],
   'title_original':source['title_original'],'ai_subject_cn':a['subject_cn'],'source_evidence':a['evidence'],
   'audit_status':a['audit_status'],'program_decision':result['decision'],'ai_review_proposal':decision,
   'references':result['action_references'],'ai_authority':'CODEX_AI_POST_RUN_REVIEW',
   'human_confirmed':False,'gold_label':None,'program_result_sha256':run.b24.p.filehash(out/'results_50.jsonl')})
 run.save('ai_audit_50_bound.jsonl',records,True)
 run.csvsave('new50_ai_review.csv',[{'编号':r['review_id'],'原文':r['title_original'],'AI识别主体':r['ai_subject_cn'],'来源证据':r['source_evidence'],'程序结论':r['program_decision'],'AI复核建议':r['ai_review_proposal'],'审查类型':r['audit_status'],'人工结论':'','审核人':''} for r in records])
 contract=read(out/'frozen_contract.json');runid='v256-'+hashlib.sha256(run.b24.p.canonical(contract).encode()).hexdigest()[:16]
 with sqlite3.connect(ROOT/'learning_data/action_selection.sqlite3') as c:
  c.execute('PRAGMA foreign_keys=ON');c.execute('CREATE TABLE IF NOT EXISTS assortment_v256_ai_audits(run_id TEXT NOT NULL,record_id TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(run_id,record_id),FOREIGN KEY(run_id) REFERENCES assortment_v256_runs(run_id))')
  inserted=0
  for r in records:
   payload=run.b24.p.canonical(r);old=c.execute('SELECT payload FROM assortment_v256_ai_audits WHERE run_id=? AND record_id=?',(runid,r['record_id'])).fetchone()
   if old:assert old[0]==payload,'IMMUTABLE_AUDIT_CONFLICT'
   else:c.execute('INSERT INTO assortment_v256_ai_audits VALUES(?,?,?)',(runid,r['record_id'],payload));inserted+=1
  c.commit()
 summary={'reviewed':50,'audit_origin':'AI_POST_RUN_REVIEW_NOT_INDEPENDENT_HUMAN','issue_counts':dict(collections.Counter(r['audit_status'] for r in records)),
  'program_counts':dict(collections.Counter(r['program_decision'] for r in records)),'ai_proposal_counts':dict(collections.Counter(r['ai_review_proposal'] for r in records)),
  'remaining_subject_host_errors':['K005','K006'],'remaining_property_subject_error':['K018'],
  'retained_reference_requiring_finer_functional_scope':['K010'],'fresh_excluded_count':0,
  'false_exclusion_rate':None,'human_accuracy':None,'human_gold':0,
  'decision':'KEEP_EXPERIMENTAL_DO_NOT_EXPAND_TO_FULL_AMAZON',
  'reason':'New50 contains no exclusions, so exclusion capability is not independently validated; literal-noun coverage and reference granularity remain limited.',
  'frozen_program_not_modified_by_audit':True}
 run.save('ai_audit_summary.json',summary)
 print(json.dumps(summary|{'inserted':inserted},ensure_ascii=False))
if __name__=='__main__':main()
