"""Human selection evidence, candidate policies, counterexamples and release."""
from __future__ import annotations
import json
from pathlib import Path
from .core import LABELS,FORMS,CONTEXTS,digest,source_record,decide,rule_matches,valid_reviewer
from .workflow import evidence,filehash,load_rows,asset_contract

def import_feedback(root,store,records):
    inserted=0;validated=[];seen={}
    for raw in records:
        f=dict(raw)
        if f.get('authority')!='HUMAN' or not valid_reviewer(f) or f.get('decision') not in LABELS:raise ValueError('HUMAN_SELECTION_EVIDENCE_REQUIRED')
        evidence(root,f)
        row=store.db.execute('SELECT payload FROM v3_sources WHERE id=? AND hash=?',(f['record_id'],f['source_hash'])).fetchone()
        if not row:raise ValueError('FEEDBACK_SOURCE_NOT_REGISTERED')
        key=(f['record_id'],f['source_hash'])
        if key in seen and seen[key]!=f['decision']:raise ValueError('CONFLICTING_FEEDBACK_BATCH')
        seen[key]=f['decision']
        for old in store.all('v3_feedback'):
            if old['record_id']==f['record_id'] and old['source_hash']==f['source_hash'] and old['decision']!=f['decision']:raise ValueError('CONFLICTING_FEEDBACK_REQUIRES_NEW_VERSION')
        f['feedback_id']=f.get('feedback_id') or 'feedback-'+digest(raw)[:20]
        validated.append(f)
    try:
        for f in validated:inserted+=store.exact('v3_feedback',{'id':f['feedback_id']},f)
        store.db.commit()
    except Exception:store.db.rollback();raise
    return {'accepted':len(validated),'inserted':inserted}

def bootstrap_owner(root,store):
    root=Path(root)
    legacy={r['record_id']:r for r in load_rows(root/'assets/examples/300/inputs_validation300.jsonl')}
    incoming=[]
    mapping={'纳入候选':'保留','待复核':'观察','暂不纳入':'用不到'}
    for f in load_rows(root/'assets/owner_feedback3.jsonl'):
        raw=legacy[f['record_id']]
        oldhash=digest({k:raw.get(k,'') for k in ['record_id','input_hash','title_original','category_l1_original','source_file_sha256','source_row']})
        if oldhash!=f['source_binding']:raise ValueError('LEGACY_FEEDBACK_SOURCE_MISMATCH')
        evidence(root,f);r=source_record(raw)
        store.exact('v3_sources',{'id':r['record_id'],'hash':r['source_hash']},r)
        incoming.append({'record_id':r['record_id'],'source_hash':r['source_hash'],'decision':mapping[f['decision']],
            'authority':'HUMAN','reviewer':f['reviewer'],'evidence_reference':f['evidence_reference'],'evidence_sha256':f['evidence_sha256'],
            'legacy_feedback_id':f['feedback_id'],'scope':'EXACT_RECORD_ONLY','semantic_gold':False})
    store.db.commit()
    return import_feedback(root,store,incoming)

def propose(root,store,spec):
    rule=dict(spec)
    for key in ['subject_types','forms','operating_contexts','support_feedback_ids']:
        if not isinstance(rule.get(key,[]),list) or any(not isinstance(v,str) or not v.strip() for v in rule.get(key,[])):
            raise ValueError('RULE_SCOPE_ARRAY_REQUIRED')
    if rule.get('decision') not in LABELS or (not isinstance(rule.get('rationale'),str) or not rule['rationale'].strip()):raise ValueError('DECISION_AND_RATIONALE_REQUIRED')
    if not rule.get('subject_types') or any(not isinstance(t,str) or not t.strip() or t=='*' for t in rule['subject_types']):raise ValueError('SPECIFIC_SUBJECT_TYPES_REQUIRED')
    if not rule.get('forms') or not set(rule['forms'])<=FORMS:raise ValueError('VALID_FORMS_REQUIRED')
    if not set(rule.get('operating_contexts',[]))<=CONTEXTS:raise ValueError('INVALID_CONTEXT_SCOPE')
    ids=rule.get('support_feedback_ids',[])
    if not ids:raise ValueError('HUMAN_FEEDBACK_SUPPORT_REQUIRED')
    supports=[]
    for fid in ids:
        f=store.get('v3_feedback',fid)
        if not f or f['authority']!='HUMAN' or f['decision']!=rule['decision']:raise ValueError('SUPPORT_DOES_NOT_APPROVE_TARGET_DECISION')
        evidence(root,f);supports.append(f)
    analyses=store.all('v3_analyses')
    # An approval of a particular item cannot support an unrelated type rule.
    for f in supports:
        matched=[x['analysis'] for x in analyses if x.get('source_hash')==f['source_hash'] and rule_matches(rule,x['analysis'])]
        if not matched:raise ValueError('SUPPORT_SUBJECT_NOT_IN_CANDIDATE_SCOPE')
    rule.update(status='CANDIDATE',support_feedback_ids=ids,support_source_hashes=[f['source_hash'] for f in supports])
    rule['rule_id']='rule-'+digest(rule)[:20]
    store.exact('v3_rule_candidates',{'id':rule['rule_id']},rule);store.db.commit();return rule

def validate_rule(root,store,rule_id,cases_path,catalog):
    rule=store.get('v3_rule_candidates',rule_id)
    if not rule:raise ValueError('RULE_CANDIDATE_NOT_FOUND')
    cases=load_rows(cases_path);results=[];matched=0;unmatched=0;all_human=True
    experimental=dict(rule,status='PUBLISHED',validation_status='PASS',release_id='ISOLATED_VALIDATION_ONLY')
    for case in cases:
        row=source_record(case['source']);a=case['analysis'];will_match=rule_matches(rule,a)
        matched+=int(will_match);unmatched+=int(not will_match)
        if case.get('expected_decision') not in LABELS:raise ValueError('EXPECTED_THREE_STATE_LABEL_REQUIRED')
        human=case.get('authority')=='HUMAN' and valid_reviewer(case)
        if human:evidence(root,case)
        all_human=all_human and human
        before=decide(row,a,catalog,{})
        after=decide(row,a,catalog,{'rules':[experimental]})
        results.append({'record_id':row['record_id'],'matched':will_match,'before':before['decision'],'after':after['decision'],
            'expected':case['expected_decision'],'passed':after['decision']==case['expected_decision'],'human_target':human})
    report={'rule_id':rule_id,'rule_hash':digest(rule),'execution_contract':asset_contract(Path(root)),
        'cases_path':str(Path(cases_path).resolve()),'cases_sha256':filehash(cases_path),
        'positive_cases':matched,'counterexamples':unmatched,'case_targets_human':all_human,
        'status':'PASS' if matched>0 and unmatched>0 and all(r['passed'] for r in results) else 'FAIL','results':results}
    report['validation_id']='validation-'+digest(report)[:20]
    store.exact('v3_rule_validation',{'id':report['validation_id']},report);store.db.commit();return report

def publish(root,store,rule_id,validation_id,approval):
    rule=store.get('v3_rule_candidates',rule_id);report=store.get('v3_rule_validation',validation_id)
    if not rule or not report or report['rule_id']!=rule_id or report['rule_hash']!=digest(rule):raise ValueError('VALIDATION_RULE_MISMATCH')
    if report.get('execution_contract')!=asset_contract(Path(root)):raise ValueError('VALIDATION_EXECUTION_CONTRACT_CHANGED')
    if report['status']!='PASS' or not report['case_targets_human']:raise ValueError('PASSED_HUMAN_CASES_AND_COUNTEREXAMPLES_REQUIRED')
    if not Path(report['cases_path']).is_file() or filehash(report['cases_path'])!=report['cases_sha256']:raise ValueError('VALIDATION_CASES_CHANGED')
    for case in load_rows(report['cases_path']):
        if case.get('authority')!='HUMAN' or not valid_reviewer(case):raise ValueError('HUMAN_CASE_TARGET_REQUIRED')
        evidence(root,case)
    if approval.get('authority')!='HUMAN' or not valid_reviewer(approval):raise ValueError('HUMAN_RELEASE_APPROVAL_REQUIRED')
    if approval.get('rule_id')!=rule_id or approval.get('rule_hash')!=digest(rule):raise ValueError('APPROVAL_RULE_BINDING_REQUIRED')
    evidence(root,approval)
    for fid in rule['support_feedback_ids']:evidence(root,store.get('v3_feedback',fid))
    released=dict(rule,status='PUBLISHED',validation_status='PASS',validation_id=validation_id,approval=approval)
    released['release_id']='release-'+digest(released)[:20]
    store.exact('v3_rule_releases',{'id':released['release_id']},released);store.db.commit();return released

def active_policy(root,store):
    rules=[]
    for r in store.all('v3_rule_releases'):
        rule=store.get('v3_rule_candidates',r['rule_id']);report=store.get('v3_rule_validation',r['validation_id'])
        if not rule or not report or report['status']!='PASS' or not report['case_targets_human'] or digest(rule)!=report['rule_hash']:raise ValueError('RELEASE_EVIDENCE_INVALID')
        if report.get('execution_contract')!=asset_contract(Path(root)):raise ValueError('RELEASE_EXECUTION_CONTRACT_CHANGED')
        if report['positive_cases']<1 or report['counterexamples']<1 or not all(x['passed'] for x in report['results']):raise ValueError('RELEASE_CASE_RESULT_INVALID')
        if report['validation_id']!='validation-'+digest({k:v for k,v in report.items() if k!='validation_id'})[:20]:raise ValueError('VALIDATION_PAYLOAD_CHANGED')
        if r['release_id']!='release-'+digest({k:v for k,v in r.items() if k!='release_id'})[:20]:raise ValueError('RELEASE_PAYLOAD_CHANGED')
        if any(r.get(k)!=v for k,v in rule.items() if k!='status') or r.get('status')!='PUBLISHED' or r.get('validation_status')!='PASS':raise ValueError('RELEASE_RULE_CHANGED')
        if filehash(report['cases_path'])!=report['cases_sha256']:raise ValueError('RELEASE_CASES_CHANGED')
        for case in load_rows(report['cases_path']):evidence(root,case)
        a=r['approval']
        if a.get('authority')!='HUMAN' or not valid_reviewer(a) or a.get('rule_id')!=rule['rule_id'] or a.get('rule_hash')!=digest(rule):raise ValueError('RELEASE_APPROVAL_CHANGED')
        evidence(root,r['approval'])
        for fid in rule['support_feedback_ids']:evidence(root,store.get('v3_feedback',fid))
        rules.append(r)
    return {'rules':rules,'version':'v3-published-operating-policy'}

def impact(root,store,release_id,run_id):
    active={r['release_id']:r for r in active_policy(root,store)['rules']}
    if release_id not in active:raise ValueError('PUBLISHED_RELEASE_REQUIRED')
    if not store.get('v3_runs',run_id):raise ValueError('BASE_RUN_NOT_FOUND')
    rows=[json.loads(x[0]) for x in store.db.execute('SELECT payload FROM v3_results WHERE run_id=?',(run_id,))]
    changed=[r for r in rows if r.get('semantic') and rule_matches(active[release_id],r['semantic'])]
    sources=[]
    for r in changed:
        s=store.db.execute('SELECT payload FROM v3_sources WHERE id=? AND hash=?',(r['record_id'],r['source_hash'])).fetchone()
        sources.append(json.loads(s[0]))
    total=len(store.get('v3_runs',run_id)['sources'])
    return {'release_id':release_id,'parent_run':run_id,'affected_records':len(sources),'unaffected_records':len(rows)-len(sources),'unresolved_records':total-len(rows),'sources':sources}
