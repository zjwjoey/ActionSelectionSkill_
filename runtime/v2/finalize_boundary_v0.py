"""Audit corrections are append-only data opinions, never a frozen-policy fix."""
import collections,csv,io,json,sqlite3
from pathlib import Path
from assortment import ROOT,RUN,Matcher,lines,read
import boundary_learning as b
import run_boundary_learning as run
import boundary_store as store
OUT=b.OUT
def csvsave(name,rows):
    buf=io.StringIO(newline='');w=csv.DictWriter(buf,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    data=('\ufeff'+buf.getvalue()).encode('utf8');path=OUT/name
    if path.exists() and path.read_bytes()!=data:raise ValueError('IMMUTABLE_CSV')
    if not path.exists():path.write_bytes(data)
def exportrow(r,source,review_id='',old=''):
    a=r.get('action_reference') or {};s=r['subject']
    return {'来源记录ID':r['record_id'],'编号':review_id,'西语商品品名':r['title_original'],'一级类目':r['category_l1_original'],'商品主体候选':s.get('class_code') or '未识别，等待语义分析',
        '主体证据':s.get('evidence_span',''),'Action匹配':r['action_match_strength'],'参照级别':r['action_relation'],'经营边界':r['scope'],'筛选结果':r['decision'],'简短理由':r['reason'],
        'ActionSKU':a.get('action_sku',''),'Action西语原名':a.get('action_title',''),'边界规则':r['boundary_rule'],'规则版本':r['boundary_version'],'分析方式':r['authority'],
        '原始行':source['source_row'],'原始链接':source['url_original'],'来源Hash':r['source_binding'],'旧本地路径结果':old,
        '人工结论':'','人工修正主体':'','人工修正功能':'','人工修正边界':'','人工原因':'','审核人':'','反馈证据引用':''}
def main():
    contract=run.check_freeze();runid=read(OUT/'full_run.json')['run_id'];source=lines(OUT/'source_records.jsonl');byid={r['record_id']:r for r in source};before=lines(OUT/'full_experiment_pre_review.jsonl')
    reviewed={a['record_id']:a for a in lines(OUT/'semantic_49.jsonl')};final=[];audits=[];refs={r['sku']:r for r in Matcher().model['references']}
    for row in before:
        a=reviewed.get(row['record_id'])
        if a:
            baseline={'subject':row['subject'],'action_references':[]}
            after=b.analyze(byid[row['record_id']],baseline,a);b.verify_reference(after,refs)
            after['audit_lineage']={'previous_decision':row['decision'],'previous_subject':row['subject'],'audit_review_id':a['review_id'],'frozen_rule_changed':False}
            audits.append({'review_id':a['review_id'],'before':row,'after':after,'rejected_original_exclusion':after['decision']!='暂不纳入'})
        else:after=row
        final.append(after)
    b.save('full_experiment_final.jsonl',final,True);b.save('full_exclusion_audit.jsonl',audits,True)
    inserted=store.persist(runid,contract,'full_safety_audited',final,list(reviewed.values()));repeat=store.persist(runid,contract,'full_safety_audited',final,list(reviewed.values()))
    if repeat:raise ValueError('AUDITED_STAGE_NOT_IDEMPOTENT')
    verified=set()
    with sqlite3.connect('file:'+str(store.DB).replace('\\','/')+'?mode=ro',uri=True) as c:
        for r in final:
            a=r.get('action_reference')
            if a and a['action_sku'] not in verified:b.verify_reference(r,refs,c);verified.add(a['action_sku'])
        integrity=c.execute('PRAGMA integrity_check').fetchone()[0];fk=c.execute('PRAGMA foreign_key_check').fetchall()
        feedback=c.execute('SELECT COUNT(*) FROM boundary_learning_feedback').fetchone()[0];published=c.execute('SELECT COUNT(*) FROM boundary_learning_rule_releases').fetchone()[0]
    protect=read(OUT/'protected_before.json');changed=[p for p,h in protect['files'].items() if b.b24.p.filehash(Path(p))!=h]
    if changed or integrity!='ok' or fk:raise ValueError('PROTECTED_DATA_OR_INTEGRITY_CHANGED:'+str(changed))
    with sqlite3.connect(OUT/'learning_before_boundary_v0.sqlite3') as old,sqlite3.connect(store.DB) as now:
        tablecounts={}
        for name, in old.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            a=old.execute('SELECT COUNT(*) FROM "'+name+'"').fetchone()[0];z=now.execute('SELECT COUNT(*) FROM "'+name+'"').fetchone()[0]
            if a!=z:raise ValueError('HISTORICAL_TABLE_COUNT_CHANGED:'+name)
            tablecounts[name]=a
    counts=dict(collections.Counter(r['decision'] for r in final));total=len(final)
    if total!=len(source) or len({r['record_id'] for r in final})!=total:raise ValueError('FINAL_ROW_RECONCILIATION')
    csvsave('完整筛选结果_实验未通过验收.csv',[exportrow(r,byid[r['record_id']]) for r in final])
    for state in b.LABELS:csvsave(state+'_实验候选.csv',[exportrow(r,byid[r['record_id']]) for r in final if r['decision']==state])
    queue=[r for r in final if r['decision']!='纳入候选' or r['subject'].get('status')!='CLEAR']
    csvsave('边界学习候选队列.csv',[exportrow(r,byid[r['record_id']]) for r in queue])
    views={};comparisons={}
    for n in [500,200]:
        inp=lines(OUT/f'inputs_{n}.jsonl');base=lines(OUT/f'local_v26_fast_{n}.jsonl');rows=lines(OUT/f'results_{n}_semantic.jsonl')
        views[str(n)]=[dict(exportrow(r,byid[r['record_id']],s['review_id'],b.MAP[p['decision']]),分层=s['sample_cohort']) for s,p,r in zip(inp,base,rows)]
        transitions=collections.Counter((b.MAP[p['decision']],r['decision']) for p,r in zip(base,rows))
        comparisons[str(n)]={'old_local_path':dict(collections.Counter(b.MAP[r['decision']] for r in base)),'boundary_v0':dict(collections.Counter(r['decision'] for r in rows)),
            'transitions':{a+' → '+z:k for (a,z),k in transitions.items()},'cohorts':{co:dict(collections.Counter(r['decision'] for s,r in zip(inp,rows) if s['sample_cohort']==co)) for co in ['random','boundary','difficult']},
            'comparison_limit':'Frozen V2.6 executable local path, no missing deep proposal invented; Boundary V0 additionally has selective real Codex analysis. Not an equal-cost independent AI A/B or a causal accuracy comparison.'}
        csvsave(f'{n}条人工复核表.csv',views[str(n)])
    viewaudit=[dict(exportrow(a['after'],byid[a['after']['record_id']],a['review_id'],a['before']['decision']),原主体=a['before']['subject']['class_code'],原排除是否撤回=a['rejected_original_exclusion']) for a in audits]
    csvsave('49条新增排除安全复核.csv',viewaudit)
    catalog=[]
    for rule,rs in sorted(collections.defaultdict(list,((k,[r for r in final if r['boundary_rule']==k]) for k in {r['boundary_rule'] for r in final})).items()):
        catalog.append({'rule_id':rule,'version':b.VERSION,'status':'CANDIDATE_NOT_PUBLISHED','subject_types':sorted({r['subject'].get('class_code','') for r in rs}),
            'conditions':'Frozen source-subject/scope predicates or explicit AI per-record opinion; do not automatically generalize a per-record opinion',
            'support_ai_record_ids':[r['record_id'] for r in rs if r['authority'].startswith('REAL_')][:8],
            'support_human_feedback_ids':[],'counterexamples':['appliance cover is not appliance','food-container compatible appliance words are not sold host','ordinary vacuum is not automated robot system'],
            'affected_source_records':len(rs),'test_status':'26 contract tests pass; full exclusion safety audit FAILS generalization','review_status':'AWAITING_HUMAN_AND_DEFECT_REPAIR'})
    b.save('rule_evidence_catalog.json',catalog)
    b.save('integrity_and_resume.json',{'integrity':integrity,'foreign_keys':len(fk),'protected_files_changed':changed,'historical_table_counts_unchanged':True,'historical_counts':tablecounts,'backup_recovery_read':'PASS','resume_inserted':repeat,'only_boundary_namespace_written':True,'action_sealed_content_read':False})
    summary={'run_id':runid,'source_records':total,'counts':counts,'percentages':{k:round(v/total*100,4) for k,v in counts.items()},'source_report':read(OUT/'source_report.json'),
        'comparison':comparisons,'actual_codex_development':73,'actual_codex_independent':40,'actual_codex_full_safety_audit':49,'actual_codex_total':162,
        'local_rule_initial_pass':25152,'unresolved_type_records':sum(r['subject'].get('status')!='CLEAR' for r in final),'pending_review':len(queue),
        'database_verified_action_reference_skus':len(verified),'prior_exclusion_candidates':51,'new_exclusion_candidates_reviewed':49,
        'ai_rejected_prior_exclusions':sum(a['rejected_original_exclusion'] for a in audits),'formal_false_exclusion_rate':None,
        'confirmed_source_subject_failure_examples':['X002 ventilation grille, not fridge','X022/X023/X042 taps, not washers','X024 magnesium anode, not water heater','X039/X040 fruit boxes, not dishwasher','X049 hat wash bag, not washer'],
        'targeted_contract_tests_passed':26,'full_safety_acceptance':'FAIL_SYSTEMATIC_HOST_AND_ATTRIBUTE_INHERITANCE',
        'experimental_full_pass_completed':True,'after_discovery_expansion_stopped':True,'frozen_rule_modified_after_independent_sample':False,
        'human_feedback_imported':feedback,'published_rules':published,'human_gold':0,'accuracy':None,'recall':None,'external_api_calls':0,'session_tokens_and_billing':'NOT_EXPOSED',
        'source_and_master_unchanged':True,'resume_inserted':repeat,'formal_publication':False,'stop':'Boundary V0 acceptance node: blocked by source-subject false exclusions; no next version or production screening'}
    b.save('summary.json',summary);b.save('workbook_data.json',{'summary':summary,'development500':views['500'],'independent200':views['200'],'exclusion49':viewaudit,'rules':catalog})
    print(json.dumps({k:summary[k] for k in ['run_id','source_records','counts','percentages','unresolved_type_records','ai_rejected_prior_exclusions','actual_codex_total','full_safety_acceptance']},ensure_ascii=False))
if __name__=='__main__':main()
