"""Prepare balanced AI proposals for genuine human calibration; no approval."""
import collections,json,random,sys
from assortment import lines,read
import semantic_understanding_v01 as s
import boundary_learning as old
def main():
    src={r['record_id']:r for r in lines(old.OUT/'source_records.jsonl')}
    candidates=lines(s.OUT/'results_200_semantic.jsonl')+[r for r in lines(old.OUT/'full_experiment_final.jsonl') if r['authority'].startswith('REAL_')]
    rng=random.Random(202610230160);selected=[];used=set();distribution={}
    for label in ['纳入候选','待复核','暂不纳入']:
        pool=[r for r in candidates if r['decision']==label];rng.shuffle(pool);groups=collections.defaultdict(list)
        for r in pool:groups[(r['boundary_rule'],r['subject']['class_code'])].append(r)
        buckets=list(groups.values());got=0
        while got<20 and buckets:
            remaining=[]
            for bucket in buckets:
                while bucket:
                    r=bucket.pop();h=old.b24.title_hash(r['title_original'])
                    if h in used:continue
                    used.add(h);selected.append(r);got+=1;break
                if bucket:remaining.append(bucket)
                if got==20:break
            buckets=remaining
        if got!=20:raise ValueError('CALIBRATION_SHORTFALL:'+label)
        distribution[label]=got
    inp=[];views=[]
    for i,r in enumerate(selected,1):
        a=r.get('action_reference') or {};row=src[r['record_id']];ident=f'C{i:03d}'
        inp.append(dict(row,review_id=ident,sample_cohort='human_calibration_candidate60'))
        views.append({'review_id':ident,'record_id':r['record_id'],'title_original':r['title_original'],'category_l1_original':r['category_l1_original'],
            'subject':r['subject']['class_code'],'subject_span':r['subject']['evidence_span'],'function_need':r.get('function_need_hypothesis') or r['reason'],
            'proposed_decision':r['decision'],'scope':r['scope'],'reason':r['reason'],'uncertainties':r.get('uncertainties','原始AI意见未经过人审'),
            'action_sku':a.get('action_sku',''),'action_title':a.get('action_title',''),'source_binding':r['source_binding'],
            'human_decision':'','corrected_subject_type':'','corrected_function':'','corrected_scope':'','human_reason':'','reviewer':'','evidence_reference':'','human_gold':False})
    s.save('inputs_calibration60.jsonl',inp,True);s.save('calibration60_proposals.json',views)
    s.save('calibration60_manifest.json',{'size':60,'proposed_states':distribution,'selection':'balanced and type-diversified AI opinions; not prevalence/accuracy sample','existing_ai_reused':True,'new_ai_calls':0,'human_confirmed':0,'formal_boundary_release':False})
    print(json.dumps({'calibration60':distribution,'human_confirmed':0,'next_required':'real reviewer decisions; no synthesized identities'},ensure_ascii=False))
if __name__=='__main__':main()
