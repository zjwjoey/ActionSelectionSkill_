"""Freeze on development60, select new300, bind actual AI work, report separately."""
import collections,copy,datetime,json,random,re,sys
from pathlib import Path
from assortment import ROOT,Matcher,lines,read,norm
import boundary_learning as b
import boundary_validation_v03 as v
import run_boundary_refinement_v02 as previous_run
import run_boundary_learning as source_run
import semantic_understanding_v01 as v01

def save(n,value,jsonl=False):b.b24.p.immutable(v.OUT/n,value,jsonl=jsonl)

def stamp(a,row,reused=False):
    a.update(record_id=row['record_id'],input_hash=row['input_hash'],title_original=row['title_original'],source_binding=v01.binding(row),
        analysis_authority='CODEX_EXISTING_OPINION_MIGRATION' if reused else 'CODEX_SEMANTIC_REVIEW_NOT_HUMAN',
        prompt_version='BOUNDARY-V03-1',prompt_sha256=b.b24.p.filehash(v.PROMPT),method_version=v.VERSION,
        model='CURRENT_CODEX_SESSION_EXACT_ID_NOT_EXPOSED',human_gold=False,reused_parent_opinion=reused,external_api_calls=0)
    return a

def prepare():
    previous_run.check();v.OUT.mkdir(parents=True,exist_ok=True)
    protection=read(previous_run.v.OUT/'protected_before.json')
    protection.update({str(p):b.b24.p.filehash(p) for p in [previous_run.v.OUT/'frozen_v02.json',previous_run.v.OUT/'summary.json',previous_run.v.OUT/'audits60.jsonl',source_run.SOURCE]})
    save('protection.json',protection)
    inputs={r['review_id']:r for r in lines(v01.OUT/'inputs_calibration60.jsonl')}
    groups=read(v.OUT/'key_boundaries60.json');corrections=read(v.OUT/'development_corrections.json')
    # Human-readable development corrections are retained independently; exact
    # machine input below is source-specific annotation data, never SKU rules.
    patches=read(v.OUT/'corrections_machine.json')
    refs={r['sku']:r for r in Matcher().model['references']};out=[]
    for original in lines(previous_run.v.OUT/'audits60.jsonl'):
        a=copy.deepcopy(original);row=inputs[a['review_id']];patch=patches.get(a['review_id'],{})
        a['parent_audit_hash']=b.digest(original)
        a['semantic'].update(patch.get('semantic',{}))
        for key in ['sold_form','scope','boundary_kind','reason']:
            if key in patch:a[key]=patch[key]
        if 'role' in patch:
            a['reference_proof']['role']=patch['role'];a['semantic']['relation']=previous_run.v.ROLES[patch['role']]
        a['reference_proof']['bounded_relationship']=a['reason']
        a['reference_proof']['source_span']=a['semantic']['subject_span']
        if a['sold_form'] in {'host_component','installed_component'}:a['boundary_kind']='COMPONENT';a['scope']='灰区'
        if a['boundary_kind'] in {'COMPLEX_AUTOMATION','FIXED_GATE_SYSTEM'}:a['scope']='灰区'
        a['boundary_evidence_span']=''
        if a['boundary_kind'] in v.OUTSIDE:
            m=re.search(v.BOUNDARY_PHRASES[a['boundary_kind']],row['title_original'],re.I)
            if m:a['boundary_evidence_span']=m.group()
        stamp(a,row,True);v.validate(row,a,refs);out.append(a)
    save('development60_bound.jsonl',out,True)
    save('development60_manifest.json',{'reviews':60,'attribute_corrections':len(patches),'authority':'AI_DEVELOPMENT_REVIEW','human_confirmed':0})

def freeze():
    paths=[Path(__file__),Path(v.__file__),v.PROMPT,ROOT/'tests/test_boundary_validation_v03.py',v.OUT/'development60_bound.jsonl',v.OUT/'key_boundaries60.json',v.OUT/'corrections_machine.json']
    hashes={str(p):b.b24.p.filehash(p) for p in paths};hashes.update(read(previous_run.v.OUT/'frozen_v02.json')['hashes'])
    save('frozen_v03.json',{'version':v.VERSION,'frozen_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'hashes':hashes,'human_gold':0,'sample_plan':{'random':200,'boundary':50,'dependency':50,'seed':2026102303300}})

def check():
    previous_run.check();f=read(v.OUT/'frozen_v03.json')
    if not all(b.b24.p.filehash(Path(p))==h for p,h in f['hashes'].items()):raise ValueError('FROZEN_V03_CHANGED')
    return f

def sample():
    f=check()
    if (v.OUT/'inputs_validation300.jsonl').exists():return
    forbidden=source_run.prior_titles()
    for p in b.OUT.glob('inputs_*.jsonl'):forbidden.update(b.b24.title_hash(r['title_original']) for r in lines(p))
    for p in b.OUT.glob('semantic_*.jsonl'):forbidden.update(b.b24.title_hash(r['title_original']) for r in lines(p))
    pool=[r for r in lines(b.OUT/'source_records.jsonl') if b.b24.title_hash(r['title_original']) not in forbidden]
    rng=random.Random(f['sample_plan']['seed']);rng.shuffle(pool);selected=[];used=set()
    for group,n,pattern in [('random',200,None),('boundary',50,r'lavadora|frigorifico|secadora|aire acondicionado|industrial|robot|torno|maquina|mueble|armario|escritorio|termo'),('dependency',50,r'compatible|recambio|repuesto|funda|soporte|kit|mecanismo|control')]:
        got=0
        for r in pool:
            h=b.b24.title_hash(r['title_original'])
            if h in used or pattern and not re.search(pattern,norm(r['title_original'])):continue
            used.add(h);selected.append(dict(r,review_id=f'N{len(selected)+1:03d}',sample_cohort=group));got+=1
            if got==n:break
        if got!=n:raise ValueError('SAMPLE_SHORTFALL_'+group)
    save('inputs_validation300.jsonl',selected,True)
    save('sampling.json',{'size':300,'cohorts':dict(collections.Counter(r['sample_cohort'] for r in selected)),'forbidden_title_count':len(forbidden),'prior_dedicated_review_title_overlap':0,'unique_titles':len(used),'frozen_before_selection':True,'not_population_accuracy_sample_when_pooled':True,'source_previously_mechanically_screened_in_v0':True})
    matcher=Matcher();found=matcher.retrieve([r['title_original'] for r in selected]);jobs=[]
    for r,cands in zip(selected,found):
        refs=[{'sku':matcher.model['references'][j]['sku'],'title':matcher.model['references'][j]['name_es_original']} for j,score in cands[:8]]
        jobs.append(dict(r,reference_candidates=refs))
    for i,name in enumerate(['a','b','c']):save('jobs_'+name+'.jsonl',jobs[i*100:(i+1)*100],True)
    print(json.dumps(read(v.OUT/'sampling.json'),ensure_ascii=False))

def bind():
    check();inputs={r['review_id']:r for r in lines(v.OUT/'inputs_validation300.jsonl')};refs={r['sku']:r for r in Matcher().model['references']};out=[]
    for name in ['a','b','c']:
        for note in lines(v.OUT/('notes_'+name+'.jsonl')):
            row=inputs[note['review_id']];a=make_audit(row,note,refs);v.validate(row,a,refs);out.append(a)
    assert len(out)==300 and len({a['record_id'] for a in out})==300
    save('validation300_bound.jsonl',out,True)

def make_audit(row,n,refs):
    ref=refs.get(n.get('action_sku',''));role=n['role'];a=None
    if n.get('action_sku') and not ref:raise ValueError('UNKNOWN_ACTION_SKU:'+n['review_id'])
    if ref:a={'action_sku':ref['sku'],'action_title':ref['name_es_original'],'source_row_id':ref['source_row_id']}
    p={'type':n['type'],'subject_span':n['subject_span'],'dependency':n['dependency'],'relation':previous_run.v.ROLES[role],
        'function_need_hypothesis':n['function'],'unknowns':n['unknowns']}
    audit={'review_id':n['review_id'],'semantic':p,'sold_form':n['form'],'scope':n['scope'],'boundary_kind':n['boundary_kind'],
        'reason':n['reason'],'boundary_rule':'V03_SEMANTIC_CANDIDATE','reference_proof':{'role':role,'coverage':n['coverage'],'source_span':n['subject_span'],
        'reference_span':ref['name_es_original'] if ref else '', 'bounded_relationship':n['reason']},'action_reference':a,
        'functional_features':n.get('functional_features',[]),'boundary_evidence_span':n.get('boundary_evidence_span',''),'issue_codes':[]}
    return stamp(audit,row)

def evaluate():
    check();refs={r['sku']:r for r in Matcher().model['references']};engine=source_run.legacy.Engine()
    for stage,path in [('development60',v01.OUT/'inputs_calibration60.jsonl'),('validation300',v.OUT/'inputs_validation300.jsonl')]:
        inputs=lines(path);base=engine.analyze_many(inputs);audits={r['record_id']:r for r in lines(v.OUT/(stage+'_bound.jsonl'))}
        out=[dict(v.analyze(r,p,refs,audits[r['record_id']]),review_id=r['review_id'],sample_cohort=r.get('sample_cohort','development')) for r,p in zip(inputs,base)]
        save(stage+'_results.jsonl',out,True)
    rows=lines(v.OUT/'validation300_results.jsonl')
    report={}
    for label in ['random','boundary','dependency']:
        subset=[r for r in rows if r['sample_cohort']==label]
        report[label]={'n':len(subset),'states':dict(collections.Counter(r['decision'] for r in subset)),'pending_reasons':dict(collections.Counter(r['review_reason_code'] for r in subset if r['decision']=='待复核'))}
    save('validation_summary.json',{'cohorts':report,'total':dict(collections.Counter(r['decision'] for r in rows)),'human_gold':0,'accuracy':None,'false_exclusion_rate':None,'full_rescreen':False,'frozen_unchanged':True})
    print(json.dumps(read(v.OUT/'validation_summary.json'),ensure_ascii=False))

if __name__=='__main__':{'prepare':prepare,'freeze':freeze,'sample':sample,'bind':bind,'evaluate':evaluate}[sys.argv[1]]()
