"""Freeze title-only Action semantic deepening inputs; never open sealed titles."""
import collections, hashlib, json, sqlite3, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import pipeline as p
OUT=ROOT/'outputs/action_semantic_v22_20261022'
BASE=ROOT/'v2/runs/action_assortment_v2_20261022'
DB=ROOT/'learning_data/action_selection.sqlite3'

def table_digest(c,t):
    h=hashlib.sha256(); count=0
    # Stable multiset fingerprint independent of row order, without huge memory.
    total=0
    for row in c.execute('SELECT * FROM "'+t.replace('"','""')+'"'):
        total=(total+int(p.digest(row),16))%(1<<256);count+=1
    return {'count':count,'sha256_multiset_sum':f'{total:064x}'}

def main():
    OUT.mkdir(exist_ok=True,parents=True)
    if (OUT/'baseline.json').exists():
        print((OUT/'baseline.json').read_text(encoding='utf8'));return
    inv=p.read_jsonl(BASE/'action_features.jsonl')
    eligible=[r for r in inv if r['state']=='INDEXED_TITLE_ONLY']
    excluded=[{'sku':r['sku'],'state':r['state']} for r in inv if r['state']!='INDEXED_TITLE_ONLY']
    assert len(eligible)==10037 and len(excluded)==84
    old=p.read_jsonl(ROOT/'outputs/staged_5000_20261022/cumulative5000_candidates.jsonl')
    previous={r['sku']:r for r in old}; assert len(previous)==5000
    protection={}
    files=list((ROOT/'source_snapshot').rglob('*'))+list((ROOT/'rules/versions').rglob('*.json'))
    files+=list((ROOT/'v2').glob('*.py'))+list((ROOT/'v2').glob('*.json'))
    files+=list(BASE.glob('*.json'))+list(BASE.glob('*.jsonl'))
    files+=[ROOT/'outputs/staged_5000_20261022/cumulative5000_candidates.jsonl',ROOT/'learning_data/p11/sealed_unseen50_plan.json',Path('F:/ActionSKUTracker/runtime/master/Action_Master.xlsx')]
    for f in files:
        if f.is_file():protection[str(f)]=p.filehash(f)
    c=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True)
    backup=OUT/'learning_before_semantic22.sqlite3'
    b=sqlite3.connect(backup);c.backup(b);assert b.execute('pragma integrity_check').fetchone()[0]=='ok';b.close()
    tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'") if not r[0].startswith('sqlite_')]
    legacy={t:table_digest(c,t) for t in tables}
    learned={r[0] for r in c.execute('select distinct sku from sample_members')};assert learned==set(previous)
    c.close()
    inputs=[];counts=collections.Counter()
    for r in eligible:
        prev=previous.get(r['sku'])
        status=('NEW_SEMANTIC_RECORD' if prev is None else 'SAME_TITLE_EXISTING_CANDIDATE' if prev['name_es_original']==r['name_es_original'] else 'SOURCE_TITLE_CHANGED_RECHECK')
        counts[status]+=1
        # Only title and provenance enter semantic input; source categories omitted.
        inputs.append({k:r[k] for k in ['sku','name_es_original','source_row_id','snapshot_id']}|{'source_title_hash':p.digest(r['name_es_original']),'old_v2_feature':r['feature'],'prior':prev,'reconciliation':status})
    p.immutable(OUT/'inputs.jsonl',inputs,jsonl=True)
    p.immutable(OUT/'excluded_ids.json',excluded)
    p.immutable(OUT/'protected_before.json',{'files':protection,'tables':legacy,'backup':str(backup),'backup_sha256':p.filehash(backup)})
    p.immutable(OUT/'skill_before.txt',{'text':(ROOT/'skills/action-selection/SKILL.md').read_text(encoding='utf8')})
    report={'phase':'Owner V2.2 Action semantic deepening; separate from frozen Amazon method version','inventory':len(inv),'eligible':len(inputs),'previous_distinct_learned':len(previous),'intersection':len(set(previous)&{r['sku'] for r in eligible}),'old_outside_effective':[{'sku':k,'reason':next((e['state'] for e in excluded if e['sku']==k),'NOT_IN_CURRENT_INDEX')} for k in previous if k not in {r['sku'] for r in eligible}],'reconciliation':dict(counts),'sealed_titles_read':0,'source_anomalies':34,'sealed_skus':50,'human_gold':0}
    p.immutable(OUT/'baseline.json',report)
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
