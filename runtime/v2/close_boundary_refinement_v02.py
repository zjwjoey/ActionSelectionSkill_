"""Append only the audited experiment to the existing shared database."""
import csv,hashlib,json,sqlite3
from pathlib import Path
from assortment import read,lines
import boundary_learning as b
import boundary_store as store
import boundary_refinement_v02 as v
import run_boundary_refinement_v02 as run

def digest_old(c,runid):
    out={}
    for table in ['boundary_learning_runs','boundary_learning_results','boundary_learning_ai_cache','boundary_learning_feedback','boundary_learning_rule_candidates','boundary_learning_rule_releases']:
        sql='SELECT * FROM '+table
        args=()
        if table in {'boundary_learning_runs','boundary_learning_results','boundary_learning_ai_cache'}:sql+=' WHERE run_id<>?';args=(runid,)
        sql+=' ORDER BY 1,2'
        h=hashlib.sha256();count=0
        for row in c.execute(sql,args):h.update(b.b24.p.canonical(row).encode());count+=1
        out[table]={'count':count,'sha256':h.hexdigest()}
    return out

def main():
    frozen=run.check();runid='boundary-v02-'+b.digest(frozen)[:16]
    backup=v.OUT/'learning_before_v02.sqlite3'
    if not backup.exists():
        with sqlite3.connect(store.DB) as src,sqlite3.connect(backup) as dst:src.backup(dst)
    with sqlite3.connect(backup) as c:
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()
        before=digest_old(c,runid)
        tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'boundary_learning_%'")]
        counts={t:c.execute('SELECT COUNT(*) FROM "'+t+'"').fetchone()[0] for t in tables}
    contract={'run_id':runid,'frozen':frozen,'status':'AI_CANDIDATE_NOT_FORMAL_RELEASE','human_gold':0}
    first=store.persist(runid,contract,'ai_reaudit60',lines(v.OUT/'results60.jsonl'),lines(v.OUT/'audits60.jsonl'))
    repeated=store.persist(runid,contract,'ai_reaudit60',lines(v.OUT/'results60.jsonl'),lines(v.OUT/'audits60.jsonl'))
    assert repeated==0
    with sqlite3.connect(store.DB) as c:
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()
        assert digest_old(c,runid)==before
        assert all(c.execute('SELECT COUNT(*) FROM "'+t+'"').fetchone()[0]==n for t,n in counts.items())
    report={'run_id':runid,'new_rows':first,'resume_new_rows':repeated,'old_boundary_rows_unchanged':True,
        'other_learning_table_counts_unchanged':True,'integrity':'ok','foreign_key_violations':0,
        'backup_integrity':'ok','backup':str(backup),'human_feedback_added':0,'rules_published':0}
    run.save('persistence.json',report)
    details=[]
    for r in read(v.OUT/'comparison60.json'):
        a=r['after'];ref=a.get('action_reference') or {}
        details.append({'编号':r['review_id'],'西语原始品名':r['title_original'],'主体候选':a['subject']['class_code'],
            '销售形态':a['sold_form'],'旧候选':r['before']['proposed_decision'],'本轮候选':a['decision'],
            '旧ActionSKU':r['before']['action_sku'],'本轮ActionSKU':ref.get('action_sku',''),'本轮Action原名':ref.get('action_title',''),
            '参照角色':a['reference_proof']['role'],'本轮说明':a['reason'],'问题类型':' / '.join(a['audit_issue_codes']),
            '来源记录ID':r['record_id'],'来源绑定Hash':r['source_binding'],'人工裁定':'','人工原因':'','审核人':'','证据引用':''})
    run.save('review_table.json',details)
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
