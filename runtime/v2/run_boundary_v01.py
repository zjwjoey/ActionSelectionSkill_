"""V0.1 targeted repair, 200 semantics, 60 calibration and frozen fresh300.

No command performs a whole-snapshot re-screen. Human calibration gates remain
independent from technical success and cannot be satisfied by AI notes.
"""
import collections,datetime,json,random,sqlite3,sys
from pathlib import Path
from assortment import ROOT,RUN,Matcher,lines,read
import boundary_learning as old
import run_boundary_learning as oldrun
import semantic_understanding_v01 as s
OUT=s.OUT
def save(n,v,jsonl=False):s.save(n,v,jsonl)
def prepare():
    OUT.mkdir(parents=True,exist_ok=True);oldrun.check_freeze()
    protected=[Path(p) for p in read(old.OUT/'protected_before.json')['files']]+[old.OUT/'summary.json',old.OUT/'full_experiment_final.jsonl',old.OUT/'frozen_boundary_v0.json']
    save('protection.json',{'files':{str(p):old.b24.p.filehash(p) for p in protected},'sealed_read':False,'originals_modified':False})
    backup=OUT/'learning_before_v01.sqlite3'
    if not backup.exists():
        with sqlite3.connect(ROOT/'learning_data/action_selection.sqlite3') as src,sqlite3.connect(backup) as dst:src.backup(dst)
    with sqlite3.connect(backup) as c:
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()
    src={r['record_id']:r for r in lines(old.OUT/'source_records.jsonl')};full=lines(old.OUT/'full_experiment_final.jsonl')
    forbidden=oldrun.prior_titles()
    for p in old.OUT.glob('inputs_*.jsonl'):forbidden.update(old.b24.title_hash(r['title_original']) for r in lines(p))
    pool=[src[r['record_id']] for r in full if r['subject'].get('status')!='CLEAR' and old.b24.title_hash(r['title_original']) not in forbidden]
    groups=collections.defaultdict(list)
    for r in pool:groups[r['category_l1_original']].append(r)
    rng=random.Random(202610230101);selected=[];used=set()
    def take(r):
        h=old.b24.title_hash(r['title_original'])
        if h in used:return False
        used.add(h);selected.append(r);return True
    for cat in sorted(groups):
        rng.shuffle(groups[cat]);n=0
        for r in groups[cat]:
            if take(r):n+=1
            if n==min(5,len(groups[cat])):break
    rng.shuffle(pool)
    for r in pool:
        if len(selected)==200:break
        take(r)
    assert len(selected)==200
    save('inputs_semantic200.jsonl',[dict(r,review_id=f'U{i:03d}',sample_cohort='category_cover_unknown_types') for i,r in enumerate(selected,1)],True)
    save('sampling200.json',{'original_unresolved':15580,'eligible_unexposed_records':len(pool),'selected':200,'category_counts':dict(collections.Counter(r['category_l1_original'] for r in selected)),'prior_title_overlap':0,'category_minimum_sampling_not_population_estimate':True,'seed':202610230101})
    # Replay the actual three historical failures using both the repaired
    # automatic contract and existing exact-source AI candidate evidence.
    e=oldrun.legacy.Engine();refs={r['sku']:r for r in e.refs};cached=s.load_existing_candidates()
    cases=[r for r in src.values() if r['source_row'] in {338,5629,19671}];base=e.analyze_many(cases)
    replay=[]
    for row,p in zip(cases,base):
        automatic=s.analyze(row,p,refs);enriched=s.analyze(row,p,refs,cached.get(s.binding(row)))
        assert automatic['decision']!='暂不纳入' and not automatic.get('action_reference')
        assert enriched['decision']!='暂不纳入' and enriched['subject']['class_code'] not in {'FRIDGE','WASHER','DISHWASHER'}
        replay.append({'source_row':row['source_row'],'title':row['title_original'],'old_type':p['subject']['class_code'],'automatic':automatic,'exact_source_existing_ai':enriched,'regression':'PASS','new_ai_calls':0})
    save('p0_real_regression3.json',replay)
    print(json.dumps({'P0_real_regressions':3,'P0':'PASS','sample200':read(OUT/'sampling200.json')},ensure_ascii=False))
    for r in lines(OUT/'inputs_semantic200.jsonl'):print(r['review_id']+'|'+r['category_l1_original']+'|'+r['title_original'])
def hashes():
    paths=[Path(__file__),Path(s.__file__),s.PROMPT,ROOT/'tests/test_boundary_v01.py',OUT/'semantic200_bound.jsonl',OUT/'inputs_calibration60.jsonl']
    return {str(p):old.b24.p.filehash(p) for p in paths}|oldrun.codehashes()
def freeze():
    p=OUT/'frozen_v01.json'
    if p.exists():check();return
    save('frozen_v01.json',{'version':s.VERSION,'frozen_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'hashes':hashes(),'status':'TECHNICAL_CANDIDATE_NOT_PUBLISHED','human_gold':0})
def check():
    f=read(OUT/'frozen_v01.json')
    if f['hashes']!=hashes():raise ValueError('FROZEN_V01_CHANGED')
    return f
def sample300():
    check()
    if (OUT/'inputs_validation300.jsonl').exists():return
    forbidden=oldrun.prior_titles()
    for folder in [old.OUT,OUT]:
        for p in folder.glob('inputs_*.jsonl'):forbidden.update(old.b24.title_hash(r['title_original']) for r in lines(p))
    pool=[r for r in lines(old.OUT/'source_records.jsonl') if old.b24.title_hash(r['title_original']) not in forbidden]
    rng=random.Random(2026102301300);rng.shuffle(pool);selected=[];used=set()
    for r in pool:
        key=old.b24.title_hash(r['title_original'])
        if key in used:continue
        used.add(key);selected.append(dict(r,review_id=f'V{len(selected)+1:03d}',sample_cohort='random_independent300'))
        if len(selected)==300:break
    save('inputs_validation300.jsonl',selected,True);save('sampling300.json',{'size':300,'seed':2026102301300,'random_sample':True,'prior_title_overlap':0,'frozen_before_selection':True,'human_accuracy_unavailable':True})
def analyze(stage):
    if stage=='300':check()
    inputs=lines(OUT/('inputs_semantic200.jsonl' if stage=='200' else 'inputs_validation300.jsonl'));e=oldrun.legacy.Engine();refs={r['sku']:r for r in e.refs}
    inherited=s.load_existing_candidates();newpath=OUT/('semantic200_bound.jsonl' if stage=='200' else 'validation300_bound.jsonl');fresh={a['source_binding']:a for a in lines(newpath)} if newpath.exists() else {}
    base=e.analyze_many(inputs);out=[]
    for r,p in zip(inputs,base):out.append(s.analyze(r,p,refs,fresh.get(s.binding(r)) or inherited.get(s.binding(r))))
    save(f'results_{stage}'+('_semantic' if fresh else '_local')+'.jsonl',out,True);save(f'base_{stage}.jsonl',base,True)
    print(json.dumps({'stage':stage,'states':dict(collections.Counter(r['decision'] for r in out)),'understanding':dict(collections.Counter(r['understanding_status'] for r in out))},ensure_ascii=False))
    if stage=='300' and not fresh:
        pending=[(r,a) for r,a in zip(inputs,out) if a['understanding_status']=='NEEDS_AI']
        # Diagnostic subset only, no independent accuracy estimate from it.
        chosen=pending[:60];save('validation_deep_panel.json',{'review_ids':[r['review_id'] for r,a in chosen],'selection':'first60 pending source-order; diagnostic, not random accuracy'},False)
        for r,a in chosen:print(r['review_id']+'|'+r['category_l1_original']+'|'+r['title_original'])
if __name__=='__main__':
    cmd=sys.argv[1]
    if cmd=='prepare':prepare()
    elif cmd=='freeze':freeze()
    elif cmd=='sample300':sample300()
    elif cmd in {'200','300'}:analyze(cmd)
