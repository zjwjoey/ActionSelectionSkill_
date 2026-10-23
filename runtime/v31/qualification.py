"""Fail-closed full-run qualification from actual completed experiment evidence."""
from .workflow import contract
from .rules import active_release

def qualify(root,state,release,catalog):
    frozen=contract(root);attempts=[r for _,r in state.all('attempt') if r['contract']==frozen and r['completed']==r['records'] and not r['errors'] and r['provider_modes']==['codex','codex']]
    blockers=[];selected={}
    for purpose,n in [('smoke',50),('development',500),('independent',200)]:
        eligible=[r for r in attempts if r['purpose']==purpose and r['records']==n and (purpose!='independent' or r['release']==release)]
        if not eligible:blockers.append(purpose+'_ACTUAL_MODEL_EVIDENCE_MISSING')
        else:selected[purpose]=eligible[-1]
    if not release:blockers.append('VALIDATED_EXPERIMENTAL_RELEASE_MISSING')
    else:active_release(root,state,release,catalog)
    if state.store.check()!={'integrity':'ok','foreign_keys':0}:blockers.append('SHARED_STORE_INTEGRITY_FAILED')
    # Every exclusion must have both model passes and a bounded experiment rule.
    rows=[r for _,r in state.all('result') if 'independent' in selected and r['execution_id']==selected['independent']['execution_id']]
    for r in rows:
        if r['decision']=='用不到' and (not r['review_completed'] or not r['experimental_rules'] or r['human_confirmed']):blockers.append('UNSUPPORTED_INDEPENDENT_EXCLUSION')
    report={'passed':not blockers,'blockers':blockers,'release':release,'selected_executions':{k:v['execution_id'] for k,v in selected.items()},'contract':frozen,'accuracy':None,'human_gold':0,'resource_availability':'CHECK_AT_EXECUTION_NO_PAID_FALLBACK'}
    state.put('full_qualification',report);return report
