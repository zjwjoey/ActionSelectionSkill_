"""Join the independent cohort diagnostics to the final 2,992-SKU V2.3 ledger."""
import collections,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import pipeline as p
OUT=ROOT/'outputs/action_semantic_v23_20261022';F=OUT/'final_candidate'
def main():
    gap={x['sku']:x for x in p.read_jsonl(OUT/'gap_review/decisions.jsonl')}
    broad={x['sku']:x for x in p.read_jsonl(OUT/'broad_review/diagnostics.jsonl')}
    base={x['sku']:x for x in p.read_jsonl(ROOT/'outputs/action_semantic_v22_20261022/final_candidate/results.jsonl')}
    result={x['sku']:x for x in p.read_jsonl(F/'results.jsonl')}
    scope=p.read_jsonl(F/'scope_review_2992.jsonl');assert len(scope)==2992
    rows=[];decisions=collections.Counter();cohorts=collections.Counter()
    for s in scope:
        old=base[s['sku']];review=gap.get(s['sku']) if old['status']=='RULE_COVERAGE_GAP' else broad.get(s['sku'])
        assert review is not None and review['source_title_hash' if 'source_title_hash' in review else 'source_title_hash']==s['source_title_hash']
        r=result[s['sku']]
        if old['status']=='RULE_COVERAGE_GAP':
            aid=review.get('rule_ids',[]); recommendation=review['status'];reason=review.get('reason');cohort=review.get('cohort');
        else:
            aid=review.get('matching_rule_ids',[]);recommendation=review['decision'];reason=review.get('reason');cohort=None
        item=s|{'cohort_diagnostic':review,'diagnostic_origin':'GAP_REVIEW' if old['status']=='RULE_COVERAGE_GAP' else 'BROAD_REVIEW','combined_v23_rule_ids':aid,'combined_v23_decision':s['decision'],'semantic_candidate_eligible':r['status']=='SPECIFIC_SEMANTIC_CANDIDATE' and bool(r.get('use_need_hypotheses')),'source_review_recommendation':recommendation,'source_review_reason':reason,'human_confirmed':False}
        rows.append(item);decisions[s['decision']]+=1;cohorts[item['diagnostic_origin']]+=1
    assert len({x['sku'] for x in rows})==2992 and cohorts=={'GAP_REVIEW':1390,'BROAD_REVIEW':1602}
    p.immutable(F/'diagnostic_review_2992.jsonl',rows,jsonl=True)
    p.immutable(F/'diagnostic_summary.json',{'sku_count':len(rows),'diagnostic_origin_counts':dict(cohorts),'final_decision_counts':dict(decisions),'gap_agent_counts':dict(collections.Counter(x['status'] for x in gap.values())),'broad_agent_counts':dict(collections.Counter(x['decision'] for x in broad.values())),'human_confirmed':0,'accuracy':None,'website_facts_in_title_results':0})
    print(json.dumps({'joined':len(rows),'decisions':dict(decisions),'gap':len(gap),'broad':len(broad)}))
if __name__=='__main__':main()
