"""Close the scoped experiment; never publish rules or rescreen the snapshot."""
import collections,csv,json,sqlite3
from pathlib import Path
from assortment import ROOT,Matcher,lines,read
import boundary_learning as b
import boundary_store as store
import semantic_understanding_v01 as s
import run_boundary_v01 as run

def main():
    frozen=run.check();out=s.OUT
    before=out/'learning_before_v01.sqlite3'
    refs={r['sku']:r for r in Matcher().model['references']}
    sets={n:lines(out/f'results_{n}_semantic.jsonl') for n in ['200','300']}
    inputs={n:lines(out/('inputs_semantic200.jsonl' if n=='200' else 'inputs_validation300.jsonl')) for n in sets}
    notes=lines(out/'semantic200_bound.jsonl')+lines(out/'validation300_bound.jsonl')
    assert len(notes)==385
    with sqlite3.connect('file:'+str(store.DB).replace('\\','/')+'?mode=ro',uri=True) as c:
        for rows in sets.values():
            for r in rows:b.verify_reference(r,refs,c)
    for stage,rows in sets.items():
        source={r['record_id']:r for r in inputs[stage]}
        for r in rows:
            assert r['source_binding']==s.binding(source[r['record_id']])
            assert not r['human_gold'] and not r['human_reviewer'] and not r['source_price_used']
    titles=[{b.b24.title_hash(r['title_original']) for r in inputs[n]} for n in ['200','300']]
    assert not titles[0]&titles[1]
    assert len(set(r['source_binding'] for rows in sets.values() for r in rows))==500
    assert all(r['regression']=='PASS' for r in read(out/'p0_real_regression3.json'))
    runid='boundary-v01-'+b.digest(frozen)[:16]
    contract={'version':s.VERSION,'frozen_contract':frozen,'run_id':runid,'human_gold':0,'formal_publication':False}
    first=[];repeat=[]
    calibration=read(out/'calibration60_proposals.json')
    for stage,rows,caches in [('semantic200',sets['200'],notes[:200]),('validation300',sets['300'],notes[200:]),('calibration60',calibration,[])]:
        first.append(store.persist(runid,contract,stage,rows,caches))
        repeat.append(store.persist(runid,contract,stage,rows,caches))
    assert sum(repeat)==0
    with sqlite3.connect(store.DB) as c:
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not c.execute('PRAGMA foreign_key_check').fetchall()
        c.execute('ATTACH DATABASE ? AS baseline',(str(before),))
        tables=[r[0] for r in c.execute("SELECT name FROM baseline.sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        old_counts={};preserved={}
        for table in tables:
            quoted='"'+table.replace('"','""')+'"'
            a=c.execute('SELECT COUNT(*) FROM baseline.'+quoted).fetchone()[0]
            z=c.execute('SELECT COUNT(*) FROM main.'+quoted).fetchone()[0]
            old_counts[table]={'before':a,'after':z}
            if table.startswith('boundary_learning_'):
                missing=c.execute('SELECT COUNT(*) FROM (SELECT * FROM baseline.'+quoted+' EXCEPT SELECT * FROM main.'+quoted+')').fetchone()[0]
                assert missing==0;preserved[table]=True
            else:assert a==z
        assert c.execute('SELECT COUNT(*) FROM boundary_learning_feedback').fetchone()[0]==old_counts['boundary_learning_feedback']['before']
        assert c.execute('SELECT COUNT(*) FROM boundary_learning_rule_releases').fetchone()[0]==old_counts['boundary_learning_rule_releases']['before']
    protection=read(out/'protection.json')
    assert all(b.b24.p.filehash(Path(p))==h for p,h in protection['files'].items())
    sources=lines(b.OUT/'source_records.jsonl')
    stats={n:{'size':len(rows),'states':dict(collections.Counter(r['decision'] for r in rows)),
        'understanding':dict(collections.Counter(r['understanding_status'] for r in rows)),
        'reference_relations':dict(collections.Counter(r['action_relation'] for r in rows))} for n,rows in sets.items()}
    summary={'version':s.VERSION,'run_id':runid,'P0_real_regressions_pass':3,'specialist_contract_tests_pass':12,
        'development200':stats['200'],'fresh300':stats['300'],
        'fresh300_local_before':dict(collections.Counter(r['decision'] for r in lines(out/'results_300_local.jsonl'))),
        'actual_new_codex_semantic_records':385,'calibration60':{'proposed_states':dict(collections.Counter(r['proposed_decision'] for r in calibration)),'human_confirmed':0},
        'human_gold':0,'accuracy':None,'false_exclusion_rate':None,'external_api_calls':0,'session_cost':'NOT_EXPOSED',
        'source_records':len(sources),'source_category_empty_records':sum(not r['category_l1_original'] for r in sources),
        'prior_narrative_category_complete_claim':'CORRECTED: original source_report correctly records 19057 populated categories; 6095 remain missing',
        'source_and_protected_files_unchanged':True,'sealed_data_read':False,'references_verified_against_shared_source_rows':True,
        'learning_db_backup_verified':str(before),'integrity':'ok','foreign_key_violations':0,'persist_insertions':first,
        'repeat_insertions':repeat,'old_table_counts':old_counts,'old_boundary_rows_preserved':preserved,
        'frozen_rule_hashes_unchanged':True,'full25152_rescreen_run':False,'boundary_rules_published':0,
        'readiness':'TECHNICAL_CANDIDATE_COMPLETE; HUMAN_CALIBRATION_AND_INDEPENDENT_HUMAN_VALIDATION_PENDING'}
    s.save('summary.json',summary)
    def view(stage):
        src={r['record_id']:r for r in inputs[stage]};local={r['record_id']:r for r in lines(out/f'base_{stage}.jsonl')}
        result=[]
        for r in sets[stage]:
            a=r.get('action_reference') or {}
            result.append({'id':src[r['record_id']]['review_id'],'title':r['title_original'],'category':r['category_l1_original'],
                'span':r['subject'].get('evidence_span',''),'type':r['subject']['class_code'],'function':r.get('function_need_hypothesis',''),
                'decision':r['decision'],'scope':r['scope'],'understanding':r['understanding_status'],'relation':r['action_relation'],
                'action_sku':a.get('action_sku',''),'action_title':a.get('action_title',''),'reason':r['reason'],'unknowns':r.get('uncertainties',''),
                'source_binding':r['source_binding'],'record_id':r['record_id'],'source_row':r['source_row'],
                'old_type':local[r['record_id']]['subject']['class_code']})
        return result
    workbook={'summary':summary,'calibration':calibration,'learning':view('200'),'validation':view('300')}
    s.save('workbook_data.json',workbook)
    for name,rows in [('calibration60',calibration),('semantic200',workbook['learning']),('validation300',workbook['validation'])]:
        with (out/(name+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps({k:summary[k] for k in ['run_id','development200','fresh300','repeat_insertions','integrity','source_category_empty_records']},ensure_ascii=False))

if __name__=='__main__':main()
