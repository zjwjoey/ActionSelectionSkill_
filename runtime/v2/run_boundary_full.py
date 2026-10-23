"""Gate 500/200, then resumable frozen-policy experiment over every source row."""
import collections,json,sqlite3,sys
from assortment import ROOT,Matcher,lines,read
import boundary_learning as b
import run_boundary_learning as run
import boundary_store as store
OUT=b.OUT
def stage_results(n):return lines(OUT/f'results_{n}_semantic.jsonl')
def gate():
    contract=run.check_freeze();refs={r['sku']:r for r in Matcher().model['references']};allrows=lines(OUT/'source_records.jsonl');byid={r['record_id']:r for r in allrows}
    reports=[]
    with sqlite3.connect('file:'+str(store.DB).replace('\\','/')+'?mode=ro',uri=True) as c:
        for n in [500,200]:
            rows=stage_results(n);sem={a['record_id']:a for a in lines(OUT/f'semantic_{n}.jsonl')}
            if len(rows)!=n or len({r['record_id'] for r in rows})!=n:raise ValueError('STAGE_COUNT')
            for r in rows:
                if r['source_binding']!=b.binding(byid[r['record_id']]):raise ValueError('STAGE_SOURCE_BINDING')
                b.verify_reference(r,refs,c)
                if r['decision']=='暂不纳入':
                    if r['subject'].get('dependent') or not r['boundary_rule'] or r['record_id'] not in sem:raise ValueError('UNREVIEWED_OR_DEPENDENT_EXCLUSION')
            reports.append({'stage':n,'count':len(rows),'source_binding':'PASS','reference_database_check':'PASS','exclusion_source_review':'PASS','counts':dict(collections.Counter(r['decision'] for r in rows))})
    overlap={b.b24.title_hash(r['title_original']) for r in stage_results(500)}&{b.b24.title_hash(r['title_original']) for r in stage_results(200)}
    if overlap:raise ValueError('DEVELOPMENT_INDEPENDENT_OVERLAP')
    b.save('expansion_gate.json',{'technical_gate':'PASS','stages':reports,'known_title_overlap':0,'human_gold':0,'formal_accuracy':None,'semantic_correctness_not_proven':True,'full_mode':'EXPERIMENTAL_ONLY','serious_source_misalignment_detected':False,'systemic_false_exclusion_detected_in_review_panel':False,'does_not_prove_zero_false_exclusions':True})
    return contract
def main():
    contract=gate();runid='boundary-v0-'+b.digest(contract)[:16];source=lines(OUT/'source_records.jsonl');e=run.legacy.Engine();refs={r['sku']:r for r in e.refs}
    semlist=lines(OUT/'semantic_500.jsonl')+lines(OUT/'semantic_200.jsonl');sem={a['record_id']:a for a in semlist}
    stagecache={r['record_id']:r for n in [500,200] for r in stage_results(n)}
    total=collections.Counter();done=[];inserted=0
    (OUT/'chunks').mkdir(exist_ok=True)
    for start in range(0,len(source),500):
        run.check_freeze();chunk=source[start:start+500];name=f'chunks/{start:06d}.jsonl';path=OUT/name
        if path.exists():result=lines(path)
        else:
            missing=[r for r in chunk if r['record_id'] not in stagecache];base=e.analyze_many(missing) if missing else []
            calculated={r['record_id']:b.analyze(r,p,sem.get(r['record_id'])) for r,p in zip(missing,base)}
            result=[stagecache.get(r['record_id']) or calculated[r['record_id']] for r in chunk]
            for r in result:b.verify_reference(r,refs)
            b.save(name,result,True)
        if [r['record_id'] for r in result]!=[r['record_id'] for r in chunk]:raise ValueError('CHUNK_ALIGNMENT')
        for r,row in zip(result,chunk):
            if r['source_binding']!=b.binding(row):raise ValueError('CHUNK_SOURCE_MISMATCH')
        inserted+=store.persist(runid,contract,'full',result)
        done.extend(result);total.update(r['decision'] for r in result)
        print(json.dumps({'processed':len(done),'total':len(source),'remaining':len(source)-len(done),'counts':dict(total)},ensure_ascii=False),flush=True)
    if len(done)!=len(source) or len({r['record_id'] for r in done})!=len(source):raise ValueError('FULL_COUNT_MISMATCH')
    # Do not release any newly discovered exclusion without a separate explicit
    # title-level review. Keep an experimental pre-review result for that audit.
    b.save('full_experiment_pre_review.jsonl',done,True)
    b.save('full_exclusion_queue.jsonl',[r for r in done if r['decision']=='暂不纳入' and r['record_id'] not in sem],True)
    inserted+=store.persist(runid,contract,'development500',stage_results(500),lines(OUT/'semantic_500.jsonl'))
    inserted+=store.persist(runid,contract,'independent200',stage_results(200),lines(OUT/'semantic_200.jsonl'))
    resumed=store.persist(runid,contract,'full',done,semlist)
    if resumed:raise ValueError('NON_IDEMPOTENT_PERSISTENCE')
    b.save('full_run.json',{'run_id':runid,'processed':len(done),'counts':dict(total),'initial_rows_inserted':inserted,'resume_inserted':resumed,'actual_codex_records':len(semlist),'external_api_calls':0,'session_token_cost':'NOT_EXPOSED','unreviewed_exclusions':sum(r['decision']=='暂不纳入' and r['record_id'] not in sem for r in done),'frozen_rules_unchanged':True,'formal_publication':False})
if __name__=='__main__':main()
