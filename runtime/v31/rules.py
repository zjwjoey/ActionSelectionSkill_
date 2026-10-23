"""AI-only experimental rule evidence; never writes V3 human policy tables."""
from runtime.v3.core import digest,LABELS,FORMS
from .core import CHANNEL,FEATURES,SUBJECT_IDENTITY_FEATURES,matches,project,validate

def propose(state,spec):
    r=dict(spec);c=r.get('conditions',{})
    if r.get('channel')!=CHANNEL or r.get('authority')!='AI_CANDIDATE':raise ValueError('AI_EXPERIMENTAL_CHANNEL_REQUIRED')
    if r.get('decision') not in LABELS or not r.get('rationale') or not str(r.get('version','')).strip():raise ValueError('RULE_METADATA_REQUIRED')
    if set(c)!={'families','forms','features_all'} or any(not isinstance(c[k],list) or (not c[k] and k!='families') or any(not isinstance(v,str) or not v.strip() or v=='*' for v in c[k]) for k in c):raise ValueError('BOUNDED_SEMANTIC_CONDITIONS_REQUIRED')
    if not set(c['features_all'])<=FEATURES:raise ValueError('RULE_UNKNOWN_FEATURE')
    if not set(c['forms'])<=FORMS:raise ValueError('RULE_INVALID_FORM')
    # A literal, typed identity fact can define product scope without relying on
    # unconstrained Chinese family phrasing. A context/need-only rule cannot.
    if not c['families'] and (not (set(c['features_all'])&SUBJECT_IDENTITY_FEATURES) or len(set(c['features_all']))<2):raise ValueError('FAMILY_OR_TYPED_SUBJECT_IDENTITY_REQUIRED')
    # Exclusion must be a positive bounded machine/whole-object condition, never
    # a missing reference, keyword, model number, brand or negative condition.
    if r['decision']=='用不到' and (not set(c['forms'])<={'whole_machine','whole_system','ordinary_good'} or len(set(c['features_all']))<2):raise ValueError('EXCLUSION_REQUIRES_COMPOUND_WHOLE_SUBJECT_CONDITION')
    if len(set(r.get('support_ids',[])))<2 or len(set(r.get('counterexample_ids',[])))<2:raise ValueError('MULTIPLE_REAL_SUPPORT_AND_COUNTEREXAMPLES_REQUIRED')
    if set(r['support_ids'])&set(r['counterexample_ids']):raise ValueError('SUPPORT_COUNTEREXAMPLE_OVERLAP')
    r.update(status='CANDIDATE',formal_publication=False)
    r['rule_id']='experiment-'+digest(r)[:24];state.put('rule_candidate',r);return r

def candidate(state,rule_id):
    found=[r for _,r in state.all('rule_candidate') if r['rule_id']==rule_id]
    if len(found)!=1:raise ValueError('EXPERIMENT_RULE_NOT_FOUND')
    return found[0]

def validate_rule(root,state,rule_id,execution,catalog):
    from .workflow import contract
    rule=candidate(state,rule_id);rows={r['record_id']:r for _,r in state.all('result') if r['execution_id']==execution}
    selected=rule['support_ids']+rule['counterexample_ids'];checks=[];titles=set();hashes=set()
    for rid in selected:
        r=rows.get(rid)
        if not r or r['purpose'] not in {'development','smoke'} or not r['review_completed']:raise ValueError('REVIEWED_DEVELOPMENT_SUPPORT_REQUIRED')
        src=next(x for x in state.get(r['run_id'],'run')['sources'] if x['record_id']==rid)
        a=r['initial_analysis'];b=r['review_analysis'];validate(src,a,catalog);validate(src,b,catalog)
        support=rid in rule['support_ids'];ma=matches(rule,a);mb=matches(rule,b)
        if support:
            titles.add(src['title_original'].casefold().strip());hashes.add(src['source_hash'])
            # Both blind rounds must independently suggest the target boundary;
            # agreement is a technical condition, not an accuracy claim.
            expected_boundary='范围外' if rule['decision']=='用不到' else '范围内' if rule['decision']=='保留' else '灰区'
            passed=ma and mb and a['boundary']==b['boundary']==expected_boundary and not ({'subject','boundary'}&set(r['disagreement_layers']))
            if rule['decision']=='保留':passed=passed and all(x['relation'] in {'same_type','related_type'} and x['coverage']=='subject' and x['match_strength'] in {'强','中'} for x in [a,b])
        else:passed=not ma and not mb
        checks.append({'record_id':rid,'source_hash':src['source_hash'],'support':support,'first_match':ma,'second_match':mb,'passed':passed,'authority':'AI_EXPERIMENTAL_NOT_GOLD'})
    passed=all(c['passed'] for c in checks) and len(titles)>=2 and len(hashes)>=2
    result={'rule_id':rule_id,'rule_hash':digest(rule),'execution':execution,'contract':contract(root),'checks':checks,
            'status':'PASS' if passed else 'FAIL','human_gold':False,'independent_accuracy':None}
    return state.put('rule_validation',result),result

def release(root,state,rule_id,validation_id,parent=None):
    from .workflow import contract
    rule=candidate(state,rule_id);validation=state.get(validation_id,'rule_validation')
    if validation['rule_id']!=rule_id or validation['rule_hash']!=digest(rule) or validation['contract']!=contract(root) or validation['status']!='PASS':raise ValueError('EXPERIMENT_VALIDATION_REQUIRED_OR_STALE')
    rules=[];iteration=1
    if parent:
        old=state.get(parent,'release');rules=old['rule_ids'];iteration=old['iteration']+1
    if iteration>2:raise ValueError('MAX_TWO_EXPERIMENT_ITERATIONS')
    if rule_id in rules:raise ValueError('DUPLICATE_EXPERIMENT_RULE')
    return state.put('release',{'channel':CHANNEL,'authority':'AI_EXPERIMENTAL_NOT_HUMAN','rule_ids':rules+[rule_id],
                              'validations':([*old['validations']] if parent else [])+[validation_id],
                              'parent_release':parent,'iteration':iteration,'contract':contract(root),'formal_publication':False})

def active_release(root,state,release_id,catalog):
    from .workflow import contract
    r=state.get(release_id,'release')
    if r['channel']!=CHANNEL or r['formal_publication'] or r['contract']!=contract(root) or not 1<=r['iteration']<=2:raise ValueError('EXPERIMENT_RELEASE_INVALID_OR_STALE')
    rules=[]
    for rid,vid in zip(r['rule_ids'],r['validations']):
        rule=candidate(state,rid);v=state.get(vid,'rule_validation')
        if v['rule_id']!=rid or v['rule_hash']!=digest(rule) or v['status']!='PASS' or v['contract']!=r['contract'] or not all(x['passed'] for x in v['checks']):raise ValueError('EXPERIMENT_EVIDENCE_INVALID')
        rules.append(rule)
    if len(rules)!=len(r['rule_ids']) or not rules:raise ValueError('EMPTY_OR_INCOMPLETE_EXPERIMENT_RELEASE')
    return rules
