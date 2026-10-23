"""Selection agreement on independent human-reviewed rows; never AI self-accuracy."""
import json
from .workflow import load_rows,evidence

def evaluate(root,store,run_id):
    run=store.get('v3_runs',run_id)
    if not run:raise ValueError('RUN_NOT_FOUND')
    exposed_titles=set();exposed_ids=set()
    for folder,name in [('300','inputs_validation300.jsonl'),('500','inputs500.jsonl')]:
        for r in load_rows(root/'assets/examples'/folder/name):
            exposed_titles.add(r['title_original'].strip());exposed_ids.add(r['record_id'])
    for r in store.all('v3_runs'):
        if r.get('purpose')!='independent':
            for rid,h in r['sources']:
                exposed_ids.add(rid)
                s=store.db.execute('SELECT payload FROM v3_sources WHERE id=? AND hash=?',(rid,h)).fetchone()
                if s:exposed_titles.add(json.loads(s[0])['title_original'].strip())
    labels={}
    for f in store.all('v3_feedback'):
        evidence(root,f)
        if f.get('evaluation_scope')=='independent' and f.get('authority')=='HUMAN':labels[(f['record_id'],f['source_hash'])]=f
    rows=[json.loads(x[0]) for x in store.db.execute('SELECT payload FROM v3_results WHERE run_id=?',(run_id,))]
    eligible=[];leaked=[];overridden=[]
    for r in rows:
        if r.get('human_confirmed'):overridden.append(r['record_id']);continue
        if r['record_id'] in exposed_ids or r['title_original'].strip() in exposed_titles:leaked.append(r['record_id']);continue
        f=labels.get((r['record_id'],r['source_hash']))
        if f and run.get('purpose')=='independent':eligible.append((r,f))
    n=len(eligible);agreed=sum(r['decision']==f['decision'] for r,f in eligible)
    return {'run_id':run_id,'purpose':run.get('purpose'),'input_records':len(run['sources']),'completed_records':len(rows),
        'independently_reviewed_eligible':n,'excluded_exposed_records':leaked,'reviewed_agreement':agreed/n if n else None,
        'excluded_owner_overrides':overridden,
        'false_exclusion_count':sum(r['decision']=='用不到' and f['decision']!='用不到' for r,f in eligible),
        'missed_retain_count':sum(f['decision']=='保留' and r['decision']!='保留' for r,f in eligible),
        'population_accuracy':None,'semantic_accuracy':None,'note':'Selection labels only. Reviewed subset is not a population estimate; AI labels never enter this denominator.'}
