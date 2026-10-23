"""Export actual experimental records and technical metrics, never AI accuracy."""
import argparse,csv,json,sys,subprocess
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from runtime.v3.core import canonical,digest
from runtime.v3.workflow import safe_workspace_path
from runtime.v31.state import State
from runtime.v31.workflow import contract
from runtime.v31.qualification import qualify
from runtime.v3.catalog import Catalog

def export_run(state,execution,out,release=None):
    rows=[r for _,r in state.all('result') if r['execution_id']==execution]
    if not rows:raise ValueError('REPORT_EXECUTION_NOT_FOUND')
    run=state.get(rows[0]['run_id'],'run');sources={s['record_id']:s for s in run['sources']}
    delta={r['record_id']:r for _,r in state.all('incremental_result') if r['parent_execution']==execution and r['release_id']==release} if release else {}
    finals=[dict(r,**{'decision':delta[r['record_id']]['decision'],'reason_code':delta[r['record_id']]['reason_code'],'operating_boundary':delta[r['record_id']]['operating_boundary'],'experimental_rules':delta[r['record_id']]['experimental_rules']}) if r['record_id'] in delta else r for r in rows]
    finals.sort(key=lambda r:r['record_id'])
    out=Path(out);out.mkdir(exist_ok=True,parents=True)
    (out/'results.jsonl').write_text(''.join(canonical(r)+'\n' for r in finals),encoding='utf-8')
    headers=['来源记录ID','来源Hash','西语原始品名','原始一级类目','V3.0同语义配对结果','V3.1初始建议','二轮建议','实验最终建议','初始主体','复核主体','初始形态','复核形态','初始Action参照SKU','复核Action参照SKU','初始参照关系','复核参照关系','初始覆盖','复核覆盖','初始Action匹配度','复核Action匹配度','初始经营边界','复核经营边界','实验经营边界','未决原因代码','存在AI分歧','分歧层','复核依据','仍然未知','实验规则','人工确认标签']
    def literal(v):return "'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v
    with (out/'review.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(headers)
        for r in finals:
            a=r.get('initial_analysis') or {};b=r.get('review_analysis') or {};src=sources[r['record_id']]
            values=[r['record_id'],r['source_hash'],r['title_original'],src['category_l1_original'],r.get('v3_baseline'),r.get('initial_decision'),r.get('review_decision'),r['decision'],a.get('subject_type'),b.get('subject_type'),a.get('form'),b.get('form'),a.get('action_sku'),b.get('action_sku'),a.get('relation'),b.get('relation'),a.get('coverage'),b.get('coverage'),a.get('match_strength'),b.get('match_strength'),a.get('boundary'),b.get('boundary'),r.get('operating_boundary'),r['reason_code'],'是' if r.get('disagreement') else '否',';'.join(r.get('disagreement_layers',[])),b.get('reason'),';'.join(r.get('unknowns',[])),';'.join(r.get('experimental_rules',[])),None]
            w.writerow([literal(v) for v in values])
    changes=[{'record_id':r['record_id'],'title':r['title_original'],'v3_paired':r.get('v3_baseline'),'v31_final':r['decision'],'reason':r['reason_code'],'experimental_rules':r.get('experimental_rules',[])} for r in finals if r.get('v3_baseline')!=r['decision']]
    completed=[r for r in finals if r['review_completed']]
    report={'execution':execution,'purpose':run['purpose'],'sources':len(run['sources']),'output_rows':len(finals),'both_model_passes_completed':len(completed),'pending':len(run['sources'])-len(completed),'decisions':dict(Counter(r['decision'] for r in finals)),
            'paired_v3_baseline':dict(Counter(r.get('v3_baseline') for r in finals)),'paired_comparison_not_independent_AB':True,
            'disagreements':sum(r['disagreement'] for r in finals),'disagreement_layers':dict(Counter(k for r in finals for k in r['disagreement_layers'])),
            'known_subject_candidates':sum(r['understanding_status']=='UNDERSTOOD_CANDIDATE' for r in finals),'reference_relation':dict(Counter((r.get('review_analysis') or {}).get('relation','not_executed') for r in finals)),
            'rule_conflicts':sum(r['reason_code']=='EXPERIMENTAL_RULE_CONFLICT' for r in finals),'observation_reasons':dict(Counter(r['reason_code'] for r in finals if r['decision']=='观察')),
            'unknown_subjects':sum(r['understanding_status']=='INFORMATION_INSUFFICIENT' for r in finals),'changes':changes,'new_human_gold':0,'formal_accuracy':None,'false_exclusion_rate':None,'retain_recall':None,
            'note':'AI differences and validation are experimental technical evidence. No independent human accuracy claim. Titles are not verified purchasable SKU identities.'}
    (out/'metrics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--development',required=True);p.add_argument('--independent');p.add_argument('--release');p.add_argument('--output',required=True)
    a=p.parse_args();out=safe_workspace_path(ROOT,a.output);out.mkdir(exist_ok=True,parents=True);state=State(safe_workspace_path(ROOT,a.db))
    try:
        development=export_run(state,a.development,out/'development500',a.release)
        independent=export_run(state,a.independent,out/'independent200') if a.independent else None
        calls=[v for _,v in state.all('model_call')];rule_calls=[v for _,v in state.all('rule_model_call')]
        tokens=Counter()
        for c in calls+rule_calls:
            for u in c.get('usage',[]):
                if u:
                    for key,value in u.items():
                        if isinstance(value,(int,float)):tokens[key]+=value
        ledger={'model_process_calls':len(calls),'rule_model_calls':len(rule_calls),'call_records_sum_not_unique':sum(c['records'] for c in calls),'provider_failures':len(state.all('model_failure')),'validation_failure_attempts':len(state.all('model_invalid')),'model_validated_per_record_entries':len(state.all('model_record')),'reported_token_usage':dict(tokens),'external_paid_api_fallback':False,'api_key_used':False,'monetary_cost_not_exposed':True,'calls':calls,'rule_calls':rule_calls}
        (out/'actual_model_call_ledger.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2),encoding='utf-8')
        gate=qualify(ROOT,state,a.release,Catalog(ROOT))
        report={'version':'V3.1 experiment candidate','git_base_before_publication':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'code_content_contract':contract(ROOT),'code_content_contract_hash':digest(contract(ROOT)),
                'development':development,'independent':independent,'actual_model_process_calls':ledger['model_process_calls'],'actual_rule_model_calls':ledger['rule_model_calls'],'full_qualification':gate,'full_25152_performed':False,'shared_store_integrity':state.store.check(),'new_human_gold':0,'formal_publication':False,'main_merge':False,'action_library_frozen':10037,'sealed50_used':False}
        (out/'closure_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'development':development['both_model_passes_completed'],'independent':independent['both_model_passes_completed'] if independent else None,'actual_model_calls':len(calls),'output':str(out)},ensure_ascii=False))
    finally:state.close()
if __name__=='__main__':main()
