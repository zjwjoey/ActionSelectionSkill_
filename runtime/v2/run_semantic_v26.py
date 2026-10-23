"""Reproducible minimum V2.6 experiment; stages never modify old experiments."""
import collections,datetime,json,random,re,sqlite3,sys
from pathlib import Path
from assortment import ROOT,RUN,Matcher,lines,read,norm
import boundary_v24 as b24
import boundary_v25 as b25
import subject_v2513 as baseline
import run_subject_v2513 as oldrun
import semantic_v26 as s
OUT=s.OUT
def save(name,value,jsonl=False):b24.p.immutable(OUT/name,value,jsonl=jsonl)
def counts(rows):return dict(collections.Counter(r['decision'] for r in rows))

# Conservatively selected literal source anchors, reviewed before freeze. Other
# historical memberships remain quarantined candidates and never imply A-C.
ANCHORS={
'G01':['100241','102235','220140','2525626'],
'G02':['1221151','2507070','2517533'],
'G03':['220085','2502244','2517861','2554513','2503772'],
'G04':['2533351','2533849','2534642','2553666'],
'G05':['2546434','3008431'],
'G06':['2520260','2525119','2533753','2550245'],
'G07':['3002315','3215355'],
'G08':['2513804','2523277','3014877','3009438'],
'G09':['3011080','3201736','3212789'],
'G10':['2534279','2580178','3004974','3215453'],
'G11':['2582385','3002463','3006425'],
'G12':['2508148','2533083','2539018'],
'G13':['2530452','2531079','2547088','2562212'],
'G14':['2507446','2525235'],
'G15':['131502','131602','2511446','2520562'],
'G16':['1200021','1221158','2505686'],
'G17':['2518668','2533698','2540582','2540583'],
'G18':['2531851','2539177','2547238','2552541'],
'G19':['2001236','2500945'],
'G20':['2523820','2525184','2536552','2538645'],
'G21':['2507907','2508891','2513068','2514838'],
'G22':['2525329','2545575','2546873','2549732'],
'G23':['2534669','2536381','2572330'],
'G24':['2049010','2500388']}
def groups():
    refs={r['sku']:r for r in Matcher().model['references']};cards=read(OUT/'action_group_cards.json');out=[]
    for c in cards:
        examples=[]
        for sku in ANCHORS[c['group_id']]:
            if sku not in refs:raise ValueError('ANCHOR_NOT_ELIGIBLE:'+sku)
            r=refs[sku];examples.append({k:r[k] for k in ['sku','name_es_original','source_row_id']})
        out.append({**c,'historical_member_count':c['member_count'],'examples':examples,'member_count':len(examples),
            'authority':'CODEX_REVIEWED_LITERAL_ANCHORS_NOT_HUMAN_GOLD',
            'uncertainty':'仅原文锚点可核实；类型/功能/需求仍为AI候选。旧分组成员未经逐条语义核验，不用于直接定级。'})
    save('action_groups_v26.json',out)
    save('group_library_review.json',{'groups':len(out),'literal_anchors':sum(len(c['examples']) for c in out),'inherited_members_not_promoted':True,'known_wrong_domain_examples_quarantined':['putty_spatula_in_kitchen','precision_knife_in_kitchen','car_polish_in_personal_care','pizza_mould_in_food'],'new_full_action_ai_pass':False})

def fingerprints():
    paths=[Path(__file__),Path(s.__file__),s.PROMPT,OUT/'action_groups_v26.json',OUT/'development_60_inputs.jsonl',OUT/'development_ai.tsv',ROOT/'tests/test_semantic_v26.py']
    return {str(p):b24.p.filehash(p) for p in paths}|oldrun.fingerprints()
def freeze():
    f={'version':s.VERSION,'frozen_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'fingerprints':fingerprints(),'seed':2026102326,'model':s.MODEL,'human_gold':0,'external_api_calls':0,'no_tuning_after_new200':True}
    if (OUT/'frozen_contract.json').exists():
        if read(OUT/'frozen_contract.json')['fingerprints']!=f['fingerprints']:raise ValueError('FROZEN_FILES_CHANGED')
    else:save('frozen_contract.json',f)
def check():
    f=read(OUT/'frozen_contract.json')
    if fingerprints()!=f['fingerprints']:raise ValueError('FROZEN_FILES_CHANGED')
    return f
def sample():
    check()
    if (OUT/'inputs_200.jsonl').exists():return
    forbidden=b24.prior_title_hashes()|b25.focus_titles()
    for path in (ROOT/'v2/runs').rglob('*.jsonl'):
        # Source pools (amazon_inputs.jsonl) are not exposed experiments.
        # Only persisted sampled inputs and this run's dev60 count as exposure.
        if not path.name.startswith('inputs_') and path!=OUT/'development_60_inputs.jsonl':continue
        if path==OUT/'inputs_200.jsonl':continue
        for r in lines(path):
            t=r.get('title_original') or r.get('product_title_raw')
            if t:forbidden.add(b24.title_hash(t))
    available=[r for r in lines(b24.INPUTS) if b24.title_hash(r['title_original']) not in forbidden]
    rng=random.Random(2026102326);rng.shuffle(available);selected=[];used=set()
    def draw(label,n,pattern=None):
        got=0
        for r in available:
            h=b24.title_hash(r['title_original'])
            if h in used or pattern and not re.search(pattern,norm(r['title_original'])):continue
            selected.append(dict(r,sample_cohort=label,review_id=f'N{len(selected)+1:03d}'));used.add(h);got+=1
            if got==n:break
        if got!=n:raise ValueError('SAMPLE_SHORTFALL:'+label)
    draw('random100',100)
    draw('boundary50',50,r'lavadora|frigorifico|aire acondicionado|industrial|profesional|mueble|armario|escritorio|conjunto|instalacion')
    draw('difficult50',50,r'compatible|recambio|repuesto|funda|soporte|para|incluye|conjunto|kit')
    assert not used&forbidden and len(used)==200
    save('inputs_200.jsonl',selected,True);save('sampling.json',{'seed':2026102326,'random_drawn_first':True,'cohorts':dict(collections.Counter(r['sample_cohort'] for r in selected)),'forbidden_titles':len(forbidden),'eligible_unexposed_pool':len(available),'prior_title_overlap':0,'sealed_action_content_read':False,'no_population_rate_from_enriched_strata':True})
def local():
    check();e=baseline.Engine();rows=lines(OUT/'inputs_200.jsonl');result=e.analyze_many(rows)
    save('baseline_200.jsonl',result,True)
    # Retention with existing exact, compatible proof can stay on the fast path.
    queue=[dict(r,local_reason=p['reason_code']) for r,p in zip(rows,result) if p['decision']!='保留' or p.get('boundary_code')]
    save('deep_queue.jsonl',queue,True)
    save('local_stage.json',{'baseline':counts(result),'deep_queue':len(queue),'local_fast':len(rows)-len(queue),'criterion':'non-retain OR boundary cue; exact-compatible local retention reused','semantic_cost_not_measured_by_retrieval_score':True})
    for r in queue:print(r['review_id']+'|'+r['category_l1_original']+'|'+r['title_original'])
def materialize(stage):
    if stage=='new':check()
    rows=lines(OUT/('development_60_inputs.jsonl' if stage=='dev' else 'deep_queue.jsonl'));byid={r['review_id']:r for r in rows}
    refs={r['sku']:r for r in Matcher().model['references']};cards={r['group_id']:r for r in read(OUT/'action_groups_v26.json')}
    path=OUT/('development_ai.tsv' if stage=='dev' else 'new200_ai.tsv');proposals=[];results=[];seen=set()
    for line in path.read_text(encoding='utf8').splitlines():
        if not line.strip():continue
        parts=line.split('|');ident=parts[0]
        if ident in seen or ident not in byid:raise ValueError('DUPLICATE_OR_UNKNOWN_ID:'+ident)
        seen.add(ident);row=byid[ident];a=s.bind_compact(row,parts,refs)
        proposals.append(dict(a,record_id=row['record_id'],input_hash=row['input_hash'],cache_key=s.cache_key(row,'dev' if stage=='dev' else s.digest(read(OUT/'frozen_contract.json')))))
        results.append(s.project(row,a,refs,cards))
    if seen!=set(byid):raise ValueError('MISSING_DEEP_ANALYSIS:'+str(sorted(set(byid)-seen)))
    save(stage+'_ai_bound.jsonl',proposals,True);save(stage+'_deep_results.jsonl',results,True)
    print(json.dumps({'stage':stage,'real_codex_records':len(results),'counts':counts(results),'reference_source_checks':'PASS'},ensure_ascii=False))
if __name__=='__main__':
    command=sys.argv[1]
    if command=='groups':groups()
    elif command=='freeze':freeze()
    elif command=='sample':sample()
    elif command=='local':local()
    elif command in {'dev','new'}:materialize(command)
