"""Record a completed pilot once, checking sources and preserving old runs."""
import collections,json,sqlite3
from assortment import ROOT,lines,read
import boundary_learning as b
import boundary_store as store
import run_boundary_pilot500 as run
from close_boundary_refinement_v02 import digest_old

def main():
 frozen=run.check();rows=lines(run.OUT/'results500.jsonl');audits=lines(run.OUT/'audits500.jsonl')
 assert len(rows)==len(audits)==500
 contract={'method':frozen,'audit_sha256':b.b24.p.filehash(run.OUT/'audits500.jsonl'),'input_sha256':b.b24.p.filehash(run.OUT/'inputs500.jsonl'),'human_gold':0,'status':'AI_PILOT_NOT_PRODUCTION_RELEASE'}
 runid='boundary-v03-pilot500-'+b.digest(contract)[:16];contract['run_id']=runid
 backup=run.OUT/'learning_before_pilot500.sqlite3'
 if not backup.exists():
  with sqlite3.connect(store.DB) as src,sqlite3.connect(backup) as dst:src.backup(dst)
 with sqlite3.connect(backup) as c:
  assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()
  old=digest_old(c,runid)
  tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'boundary_learning_%'")]
  counts={t:c.execute('SELECT COUNT(*) FROM "'+t+'"').fetchone()[0] for t in tables}
 new=store.persist(runid,contract,'random500',rows,audits)
 again=store.persist(runid,contract,'random500',rows,audits);assert again==0
 with sqlite3.connect(store.DB) as c:
  assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()
  assert digest_old(c,runid)==old
  assert all(c.execute('SELECT COUNT(*) FROM "'+t+'"').fetchone()[0]==n for t,n in counts.items())
 protected=read(run.method.OUT/'protection.json');assert all(b.b24.p.filehash(p)==h for p,h in protected.items())
 summary=read(run.OUT/'summary.json')
 run.save('persistence.json',{'run_id':runid,'new_rows':new,'resume_new_rows':again,'integrity':'ok','foreign_key_violations':0,'backup_integrity':'ok','old_rows_unchanged':True,'other_learning_tables_unchanged':True,'master_unchanged':True,'protected_hashes_unchanged':len(protected),'human_feedback_added':0,'formal_rules_published':0})
 inputs={r['record_id']:r for r in lines(run.OUT/'inputs500.jsonl')}
 labels={'纳入候选':'保留','待复核':'观察','暂不纳入':'用不到'}
 reasons={'OPERATING_BOUNDARY_UNCONFIRMED':'经营边界未确认','DEPENDENCY_REVIEW':'专用或安装配件','INFORMATION_INSUFFICIENT':'供货或形态信息不足','REFERENCE_ABSENT':'缺少有效Action参照','REFERENCE_TOO_BROAD':'参照关联过宽','REFERENCE_COVERAGE_INCOMPLETE':'参照仅覆盖套装部分','BOUNDARY_EVIDENCE_CONFLICT':'整机边界证据冲突','SCOPE_KIND_CONFLICT':'范围与主体类型冲突','NOT_PENDING':''}
 table=[]
 for r in rows:
  ref=r.get('action_reference') or {};source=inputs[r['record_id']]
  table.append({'编号':r['review_id'],'西语原始品名':r['title_original'],'商品主体候选':r['subject']['class_code'],'用途候选':r['function_need_hypothesis'],'筛选候选':labels[r['decision']],'观察原因':reasons.get(r['review_reason_code'],r['review_reason_code']),'Action SKU':ref.get('action_sku',''),'Action原始品名':ref.get('action_title',''),'参照关系':r['reference_proof']['role'],'判断说明':r['reason'],'未确认信息':r['uncertainties'],'商品链接':source['url_original'],'来源记录ID':r['record_id'],'来源绑定Hash':r['source_binding'],'人工裁定':'','人工原因':'','审核人':'','证据引用':''})
 run.save('review_table500.json',table)
 run.save('public_summary.json',{'n':500,'states':{labels[k]:v for k,v in summary['states'].items()},'remaining_samples':read(run.OUT/'sampling.json')['remaining_after_selection'],'human_confirmed_new_sample_labels':0,'accuracy':None,'full_rescreen':False,'master_changed':False})
 print(json.dumps(read(run.OUT/'persistence.json'),ensure_ascii=False))

if __name__=='__main__':main()
