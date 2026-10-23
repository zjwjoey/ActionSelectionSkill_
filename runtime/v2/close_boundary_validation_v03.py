"""Append this frozen pilot to the shared database and retain audit evidence."""
import collections,json,sqlite3
from assortment import Matcher,lines,read
import boundary_learning as b
import boundary_store as store
import boundary_validation_v03 as v
import run_boundary_validation_v03 as run
from close_boundary_refinement_v02 import digest_old

def main():
    frozen=run.check()
    audit_hashes={stage:b.b24.p.filehash(v.OUT/(stage+'_bound.jsonl')) for stage in ['development60','validation300']}
    runid='boundary-v03-'+b.digest({'frozen':frozen,'audit_hashes':audit_hashes})[:16]
    protected=read(v.OUT/'protection.json')
    mismatches=[p for p,h in protected.items() if b.b24.p.filehash(p)!=h]
    assert not mismatches,mismatches
    identity=read(v.OUT/'identity_overlap_audit.json');assert not identity['overlap']
    rows=lines(v.OUT/'validation300_results.jsonl')
    assert len(rows)==300 and len({r['record_id'] for r in rows})==300
    refs={r['sku']:r for r in Matcher().model['references']}
    with sqlite3.connect('file:'+str(store.DB)+'?mode=ro',uri=True) as c:
        checked=set()
        for result in rows+lines(v.OUT/'development60_results.jsonl'):
            ref=result.get('action_reference')
            assert result['human_gold'] is False and not result['human_reviewer']
            assert result['source_price_used'] is False
            if not ref:continue
            sku=ref['action_sku'];original=refs[sku]
            assert ref['action_title']==original['name_es_original']
            source=c.execute('SELECT sku FROM source_rows WHERE source_row_id=?',(original['source_row_id'],)).fetchone()
            assert source and source[0]==sku
            checked.add(sku)
    backup=v.OUT/('learning_before_'+runid+'.sqlite3')
    if not backup.exists():
        with sqlite3.connect(store.DB) as src,sqlite3.connect(backup) as dst:src.backup(dst)
    with sqlite3.connect(backup) as c:
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not c.execute('PRAGMA foreign_key_check').fetchall()
        before=digest_old(c,runid)
        tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'boundary_learning_%'")]
        counts={t:c.execute('SELECT COUNT(*) FROM "'+t+'"').fetchone()[0] for t in tables}
    contract={'run_id':runid,'frozen':frozen,'audit_hashes':audit_hashes,
        'status':'AI_CANDIDATE_NOT_FORMAL_RELEASE','human_gold':0}
    def persist():
        count=0
        for stage in ['development60','validation300']:
            count+=store.persist(runid,contract,stage,lines(v.OUT/(stage+'_results.jsonl')),lines(v.OUT/(stage+'_bound.jsonl')))
        return count
    first=persist();repeated=persist();assert repeated==0
    with sqlite3.connect(store.DB) as c:
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not c.execute('PRAGMA foreign_key_check').fetchall()
        assert digest_old(c,runid)==before
        assert all(c.execute('SELECT COUNT(*) FROM "'+t+'"').fetchone()[0]==n for t,n in counts.items())
    report={'run_id':runid,'new_rows':first,'resume_new_rows':repeated,
        'old_boundary_rows_unchanged':True,'other_learning_table_counts_unchanged':True,
        'integrity':'ok','foreign_key_violations':0,'backup_integrity':'ok','backup':str(backup),
        'human_feedback_added':0,'rules_published':0,'protected_files_unchanged':len(protected),
        'eligible_references_verified':len(checked),'master_unchanged':True,'full_rescreen':False}
    run.save('persistence.json',report)
    before_rows={r['review_id']:r for r in lines(run.previous_run.v.OUT/'results60.jsonl')}
    after_rows=lines(v.OUT/'development60_results.jsonl')
    changes=[{'review_id':r['review_id'],'before':before_rows[r['review_id']]['decision'],'after':r['decision'],
        'reason':r['reason'],'review_reason_code':r['review_reason_code']}
        for r in after_rows if r['decision']!=before_rows[r['review_id']]['decision']]
    run.save('development_comparison.json',{'n':60,
        'before':dict(collections.Counter(r['decision'] for r in before_rows.values())),
        'after':dict(collections.Counter(r['decision'] for r in after_rows)),
        'decision_changes':changes,'not_independent_validation':True})
    details=[]
    for r in rows:
        ref=r.get('action_reference') or {};proof=r['reference_proof']
        details.append({'编号':r['review_id'],'样本组':{'random':'普通随机','boundary':'边界专项','dependency':'依赖专项'}[r['sample_cohort']],
            '西语原始品名':r['title_original'],'主体候选':r['subject']['class_code'],
            '形态':r['sold_form'],'用途候选':r['function_need_hypothesis'],'候选结论':r['decision'],
            '待复核原因':r['review_reason_code'],'Action SKU':ref.get('action_sku',''),
            'Action西语品名':ref.get('action_title',''),'参照角色':proof['role'],
            '说明':r['reason'],'未确认信息':r['uncertainties'],'来源记录ID':r['record_id'],
            '来源绑定Hash':r['source_binding'],'人工裁定':'','人工原因':'','审核人':'','证据引用':''})
    run.save('review_table300.json',details)
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
