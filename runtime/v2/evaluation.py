"""Import real, hash-bound human review; never manufacture an adjudicator."""
import argparse,collections,csv,json
from assortment import RUN,read,lines,p,connect

def evaluate(review_csv=None):
 rows=lines(RUN/('blind_review200_v23.jsonl' if (RUN/'blind_review200_v23.jsonl').exists() else 'blind_review200.jsonl'));expected={r['record_id']:r for r in rows}
 opinions=[]
 if review_csv:
  if str(review_csv).lower().endswith('.xlsx'):
   import openpyxl
   book=openpyxl.load_workbook(review_csv,read_only=True,data_only=True);sheet=book['匿名审核200条'];incoming=[]
   for row in sheet.iter_rows(min_row=6,max_row=205,values_only=True):incoming.append({'record_id':row[13],'expected_C_hash':row[14],'human_target':row[10],'human_reason':row[11],'human_reviewer':row[12]})
   book.close()
  else:
   with open(review_csv,encoding='utf-8-sig',newline='') as f:incoming=list(csv.DictReader(f))
  for row in incoming:
   if not row.get('human_target') and not row.get('human_reviewer'):continue
   rid=row.get('record_id');original=expected.get(rid)
   if not original or row.get('expected_C_hash')!=original['expected_C_hash']:raise ValueError('UNKNOWN_OR_STALE_HUMAN_REVIEW')
   if not row.get('human_reviewer','').strip() or row.get('human_reviewer','').strip().lower() in {'ai','codex','chatgpt','assistant'}:raise ValueError('REAL_HUMAN_REVIEWER_REQUIRED')
   if row.get('human_target') not in {'HIGH_MATCH','POTENTIAL_MATCH','NEEDS_REVIEW','LOW_MATCH'}:raise ValueError('HUMAN_TARGET_REQUIRED')
   if not str(row.get('human_reason') or '').strip():raise ValueError('HUMAN_REASON_REQUIRED')
   opinions.append(row)
 if len({r['record_id'] for r in opinions})!=len(opinions):raise ValueError('DUPLICATE_HUMAN_RECORD')
 comparisons={r['record_id']:r for r in lines(RUN/('three_scheme700_comparison_v23.jsonl' if (RUN/'three_scheme700_comparison_v23.jsonl').exists() else 'three_scheme700_comparison.jsonl'))}
 cohorts={}
 for cohort in ['RANDOM_REVIEW_120','DIFFICULT_REVIEW_80']:
  subset=[r for r in opinions if expected[r['record_id']]['cohort']==cohort];metrics={}
  for arm in ['A','B','C']:
   positive=[r for r in subset if r['human_target']=='HIGH_MATCH']
   retained=sum(comparisons[r['record_id']][arm]['decision'] in {'HIGH_MATCH','POTENTIAL_MATCH'} for r in positive)
   wrong_exclusion=sum(comparisons[r['record_id']][arm]['decision']=='LOW_MATCH' for r in positive)
   recommended=[r for r in subset if comparisons[r['record_id']][arm]['decision']=='HIGH_MATCH']
   correct=sum(r['human_target']=='HIGH_MATCH' for r in recommended)
   metrics[arm]={'human_reviewed':len(subset),'must_keep_targets':len(positive),'candidate_pool_recall':retained/len(positive) if positive else None,'false_hard_exclusions':wrong_exclusion if subset else None,'false_hard_exclusion_rate':wrong_exclusion/len(positive) if positive else None,'high_recommendation_precision':correct/len(recommended) if recommended else None,'all_metrics_are_cohort_conditional':True}
  cohorts[cohort]=metrics
 result={'human_labels':len(opinions),'cohorts':cohorts,'reference_validity':'Requires separately adjudicated reference labels; not inferred from real SKU existence','plain_AI_vs_full_context_Skill_superiority':None,'three_program_scheme_comparison_only':True,'no_combined_population_accuracy':True}
 # Read-only default. Importing an explicit, completed file is the only mutation.
 if opinions:
  run_id=read(RUN/'run_identity.json')['run_id']
  with connect() as c:
   for row in opinions:
    previous=c.execute('SELECT human_target,reason FROM assortment_v2_reviews WHERE run_id=? AND record_id=? AND expected_result_hash=? AND reviewer=?',(run_id,row['record_id'],row['expected_C_hash'],row['human_reviewer'])).fetchone()
    if previous and tuple(previous)!=(row['human_target'],row.get('human_reason','')):raise ValueError('HUMAN_DECISION_CONFLICT_REQUIRES_VERSIONED_ADJUDICATION')
    if not previous:c.execute('INSERT INTO assortment_v2_reviews VALUES(?,?,?,?,?,?)',(run_id,row['record_id'],row['expected_C_hash'],row['human_reviewer'],row['human_target'],row.get('human_reason','')))
  p.immutable(RUN/('evaluation_'+p.digest(opinions)[:12]+'.json'),result)
 else:p.immutable(RUN/'evaluation_pending_human.json',result)
 print(json.dumps(result,ensure_ascii=False,indent=2));return result

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--human-csv');evaluate(a.parse_args().human_csv)
