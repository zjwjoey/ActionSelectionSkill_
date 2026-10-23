"""Human feedback -> common-rule candidates -> explicit release -> delta replay.

No command invents reviewers or marks AI opinions as Gold. This task does not
execute import/publish; the CLI is an audited future input route.
"""
import argparse,collections,json
from pathlib import Path
from assortment import lines,read
import boundary_learning as b
import boundary_store as store

def evidence_check(feedback):
    path=Path(feedback.get('evidence_reference',''))
    if not path.is_file() or b.b24.p.filehash(path)!=feedback.get('evidence_sha256'):raise ValueError('HUMAN_EVIDENCE_FILE_OR_HASH_REQUIRED')

def import_feedback(path):
    current={r['record_id']:r for r in lines(b.OUT/'full_experiment_final.jsonl')};incoming=lines(path);valid=[]
    for f in incoming:
        row=current[f['record_id']];b.validate_feedback(row,f);evidence_check(f)
        valid.append(dict(f,feedback_id=f.get('feedback_id') or 'human-'+b.digest(f)[:24]))
    with store.connect() as c:
        count=sum(store.exact(c,'boundary_learning_feedback',['feedback_id'],{'feedback_id':f['feedback_id'],'record_id':f['record_id'],'payload':b.b24.p.canonical(f)}) for f in valid);c.commit()
    return {'accepted':len(valid),'inserted':count,'authority':'SUPPLIED_HUMAN_EVIDENCE_NOT_IDENTITY_INFERRED_BY_PROGRAM'}

def propose():
    current={r['record_id']:r for r in lines(b.OUT/'full_experiment_final.jsonl')};groups=collections.defaultdict(list)
    with store.connect() as c:
        for payload, in c.execute('SELECT payload FROM boundary_learning_feedback'):
            f=json.loads(payload);r=current.get(f['record_id'])
            if not r:continue
            b.validate_feedback(r,f);evidence_check(f)
            typ=f.get('corrected_subject_type') or r['subject']['class_code']
            groups[(typ,f['decision'])].append(f)
        candidates=[]
        for (typ,decision),fs in groups.items():
            if len({f['record_id'] for f in fs})<2:continue
            rule={'rule_id':'BL-'+b.digest([typ,decision])[:12],'version':'candidate-'+b.digest(fs)[:12],'status':'CANDIDATE',
                'subject_types':[typ],'target_decision':decision,'conditions':'Exact reviewed subject type; compatible independent form; no host inheritance; include still requires A/B/C evidence',
                'support_feedback_ids':[f['feedback_id'] for f in fs],'counterexamples':[],
                'affected_records':len(b.impact(list(current.values()),{'subject_types':[typ]})),
                'test_status':'NOT_RUN','release_approval_reviewer':'','release_approval_evidence':''}
            store.exact(c,'boundary_learning_rule_candidates',['rule_id','version'],{'rule_id':rule['rule_id'],'version':rule['version'],'payload':b.b24.p.canonical(rule)})
            candidates.append(rule)
        c.commit()
    return candidates

def publish(rulefile,testfile):
    rule=read(rulefile);tests=read(testfile)
    with store.connect() as c:
        fs=[json.loads(r[0]) for r in c.execute('SELECT payload FROM boundary_learning_feedback')]
        for f in fs:evidence_check(f)
        published=b.validate_publication(rule,fs,tests)
        approval=Path(rule['release_approval_evidence'])
        if not approval.is_file() or b.b24.p.filehash(approval)!=rule.get('release_approval_sha256'):raise ValueError('RELEASE_APPROVAL_FILE_REQUIRED')
        release_id='release-'+b.digest(published)[:24]
        store.exact(c,'boundary_learning_rule_releases',['release_id'],{'release_id':release_id,'rule_id':rule['rule_id'],'version':rule['version'],'payload':b.b24.p.canonical(published)});c.commit()
    return {'release_id':release_id,'rule':published}

def delta_plan(rule):
    rows=lines(b.OUT/'full_experiment_final.jsonl');affected=set(b.impact(rows,rule));pending={r['record_id'] for r in rows if r['decision']=='待复核'}
    return {'rule_id':rule['rule_id'],'candidate_version':rule['version'],'affected_record_ids':sorted(affected),'pending_review_record_ids':sorted(pending),'new_source_record_ids':[],
        'rule_version_is_not_action_semantic_version':True,'automatic_full_rescreen':False}

def apply_release(release_id):
    with store.connect() as c:
        found=c.execute('SELECT payload FROM boundary_learning_rule_releases WHERE release_id=?',(release_id,)).fetchone()
    if not found:raise ValueError('PUBLISHED_RELEASE_REQUIRED')
    rule=json.loads(found[0]);rows=lines(b.OUT/'full_experiment_final.jsonl');affected=set(b.impact(rows,rule));updates=[]
    for row in rows:
        if row['record_id'] not in affected:continue
        new=dict(row);wanted=rule['target_decision']
        if wanted=='暂不纳入' and (row['subject'].get('dependent') or row['subject'].get('status')!='CLEAR'):wanted='待复核'
        if wanted=='纳入候选' and (row['action_relation'] not in {'A','B','C'} or not row.get('action_reference') or row['subject'].get('dependent')):wanted='待复核'
        new.update(decision=wanted,boundary_version=rule['version'],applied_release_id=release_id,authority='HUMAN_SUPPORTED_RULE_NOT_PER_RECORD_HUMAN_GOLD',human_gold=False)
        updates.append(new)
    b.save('delta_'+release_id+'.jsonl',updates,True)
    return {'processed_affected':len(updates),'source_records_rewritten':0,'historical_results_overwritten':0}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['import-feedback','propose','publish','plan-incremental','apply-release']);p.add_argument('file',nargs='?');p.add_argument('--tests');a=p.parse_args()
    if a.command=='import-feedback':result=import_feedback(a.file)
    elif a.command=='propose':result=propose()
    elif a.command=='publish':result=publish(a.file,a.tests)
    elif a.command=='plan-incremental':result=delta_plan(read(a.file))
    else:result=apply_release(a.file)
    print(json.dumps(result,ensure_ascii=False))
