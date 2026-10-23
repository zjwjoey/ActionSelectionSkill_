"""Source-bound60 AI re-audit and new candidate guards, no full rescreen."""
import collections,json,sqlite3,sys
from pathlib import Path
from assortment import ROOT,Matcher,lines,read
import boundary_learning as b
import boundary_store as store
import boundary_refinement_v02 as v
import semantic_understanding_v01 as old
import run_boundary_v01 as parent_run

def save(name,data,jsonl=False):b.b24.p.immutable(v.OUT/name,data,jsonl=jsonl)

def materialize():
    parent_run.check();v.OUT.mkdir(parents=True,exist_ok=True)
    protection={str(p):b.b24.p.filehash(p) for p in [old.OUT/'frozen_v01.json',old.OUT/'summary.json',old.OUT/'calibration60_proposals.json',old.OUT/'results_300_semantic.jsonl']}
    protection.update(read(old.OUT/'protection.json')['files'])
    save('protected_before.json',protection)
    originals={r['review_id']:r for r in read(old.OUT/'calibration60_proposals.json')}
    inputs={r['review_id']:r for r in lines(old.OUT/'inputs_calibration60.jsonl')}
    cached=old.load_existing_candidates()
    for file in ['semantic200_bound.jsonl','validation300_bound.jsonl']:
        cached.update({r['source_binding']:r for r in lines(old.OUT/file)})
    refs={r['sku']:r for r in Matcher().model['references']}
    reviews=[]
    for line in (v.OUT/'ai_review60.tsv').read_text(encoding='utf8').splitlines():
        ident,form,scope,boundary,role,sku,coverage,note,issues=line.split('|')
        row=inputs[ident];prior=originals[ident];base=cached[old.binding(row)]
        semantic=dict(base['semantic'],relation=v.ROLES[role],dependency={'unknown':'unknown','host_component':'host_specific','installed_component':'installed','universal_accessory':'universal_accessory'}.get(form,'standalone'))
        a=None;sku=prior['action_sku'] if sku=='=' else sku
        if sku:
            r=refs[sku];a={'action_sku':sku,'action_title':r['name_es_original'],'source_row_id':r['source_row_id']}
        proof={'role':role,'coverage':coverage,'source_span':semantic['subject_span'],
               'reference_span':a['action_title'] if a else '', 'bounded_relationship':note}
        features=[]
        # Explicit source-specific AI feature annotations, not production SKU rules.
        raw_features={
            'C043':[('navigation','navegación láser'),('dust_disposal','autovaciado')],
            'C050':[('navigation','Navegación Láser'),('dust_disposal','Autovaciado')],
            'C054':[('navigation','Navegación Láser'),('dust_disposal','Autovaciado')],
            'C059':[('navigation','Navegación Láser'),('dust_disposal','Autovaciado')],
            'C053':[('drive','Motor Puerta Corredera'),('transmission','Cremallera de Nailon'),('control','Control Remoto'),('safety_sensor','Sensores Infrarrojos')]}
        features=[{'tag':tag,'span':span} for tag,span in raw_features.get(ident,[])]
        audit={'review_id':ident,'record_id':row['record_id'],'title_original':row['title_original'],'input_hash':row['input_hash'],
            'source_binding':old.binding(row),'semantic':semantic,'sold_form':form,'scope':scope,'boundary_kind':boundary,
            'action_reference':a,'reference_proof':proof,'functional_features':features,'issue_codes':issues.split(','),
            'boundary_rule':'V02_AI_'+boundary,'reason':note,'analysis_authority':'ACTUAL_CODEX_REAUDIT_NOT_HUMAN_GOLD',
            'model':'CURRENT_CODEX_SESSION_EXACT_ID_NOT_EXPOSED','prompt_version':'BOUNDARY-V02-EVIDENCE-1',
            'prompt_sha256':b.b24.p.filehash(v.PROMPT),'human_gold':False,'external_api_calls':0,'parent_opinion_preserved':True}
        v.validate(row,audit,refs);reviews.append(audit)
    assert len(reviews)==60 and len({r['review_id'] for r in reviews})==60
    save('audits60.jsonl',reviews,True)
    print('SOURCE_BOUND_AI_REAUDITS',len(reviews))

def freeze():
    files=[Path(v.__file__),Path(__file__),v.PROMPT,v.OUT/'audits60.jsonl',ROOT/'tests/test_boundary_refinement_v02.py']
    hashes={str(p):b.b24.p.filehash(p) for p in files}
    hashes.update(read(old.OUT/'frozen_v01.json')['hashes'])
    save('frozen_v02.json',{'version':v.VERSION,'hashes':hashes,'human_gold':0,'formal_release':False})

def check():
    parent_run.check();f=read(v.OUT/'frozen_v02.json')
    assert all(b.b24.p.filehash(Path(p))==h for p,h in f['hashes'].items())
    return f

def evaluate():
    contract=check();refs={r['sku']:r for r in Matcher().model['references']}
    inp=lines(old.OUT/'inputs_calibration60.jsonl');base=parent_run.oldrun.legacy.Engine().analyze_many(inp)
    audit={r['record_id']:r for r in lines(v.OUT/'audits60.jsonl')};before={r['record_id']:r for r in read(old.OUT/'calibration60_proposals.json')}
    rows=[dict(v.analyze(r,p,refs,audit[r['record_id']]),review_id=r['review_id']) for r,p in zip(inp,base)]
    with sqlite3.connect('file:'+str(store.DB).replace('\\','/')+'?mode=ro',uri=True) as c:
        for r in rows:b.verify_reference(r,refs,c)
    save('results60.jsonl',rows,True)
    delta=[]
    for r in rows:
        p=before[r['record_id']]
        delta.append({'review_id':r['review_id'],'record_id':r['record_id'],'title_original':r['title_original'],
            'source_binding':r['source_binding'],'before':p,'after':r,
            'decision_changed':p['proposed_decision']!=r['decision'],'reference_changed':p['action_sku']!=(r.get('action_reference') or {}).get('action_sku','')})
    save('comparison60.json',delta)
    report={'version':v.VERSION,'reviewed':60,'states_before':dict(collections.Counter(p['proposed_decision'] for p in before.values())),
        'states_after':dict(collections.Counter(r['decision'] for r in rows)),
        'decisions_changed':sum(r['decision_changed'] for r in delta),'references_changed':sum(r['reference_changed'] for r in delta),
        'withdrawn_exclusion':sum(r['before']['proposed_decision']=='暂不纳入' and r['after']['decision']!='暂不纳入' for r in delta),
        'issue_counts':dict(collections.Counter(code for a in audit.values() for code in a['issue_codes'] if code!='NO_CHANGE')),
        'human_gold':0,'accuracy':None,'full_rescreen':False,'fresh_sample_run':False,'kind':'DEVELOPMENT_REAUDIT_NOT_INDEPENDENT_VALIDATION',
        'parent_and_sources_unchanged':all(b.b24.p.filehash(Path(p))==h for p,h in read(v.OUT/'protected_before.json').items())}
    assert report['parent_and_sources_unchanged'];save('summary.json',report);print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':
    {'materialize':materialize,'freeze':freeze,'evaluate':evaluate}[sys.argv[1]]()
