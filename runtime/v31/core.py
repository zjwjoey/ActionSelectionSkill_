"""Separate source, match and experimental operating boundary contracts."""
from runtime.v3.core import canonical,digest,validate_analysis,decide

VERSION='v3.1-ai-experimental-1'
CHANNEL='AI_EXPERIMENTAL_BOUNDARY'
FEATURES={'autonomous_navigation','automatic_maintenance','robot_cleaner','industrial_context',
          'heavy_duty_machine','large_complete_furniture','powered_furniture','major_appliance',
          'host_dependency','manual_tool','ordinary_consumable','ordinary_accessory','household_good'}
SUBJECT_IDENTITY_FEATURES={'robot_cleaner','major_appliance','large_complete_furniture','manual_tool','ordinary_consumable','ordinary_accessory'}

def sale_role(form):
    # A universal accessory is an independently sold ordinary good, not a
    # proprietary host component. Keep bundles and all machine roles distinct.
    return 'independent_ordinary_good' if form in {'ordinary_good','universal_accessory'} else form

def source(raw):
    rid=str(raw.get('record_id') or '').strip();title=str(raw.get('title_original') or '').strip()
    if not rid or not title:raise ValueError('SOURCE_ID_AND_TITLE_REQUIRED')
    category=str(raw.get('category_l1_original') or '')
    version=str(raw.get('source_version') or raw.get('snapshot_id') or '')
    return dict(record_id=rid,title_original=title,category_l1_original=category,source_version=version,
                source_hash=digest(dict(record_id=rid,title_original=title,category_l1_original=category,source_version=version)))

def validate(row,a,catalog):
    validate_analysis(row,a,catalog)
    if a.get('match_strength') not in {'强','中','弱','未知'}:raise ValueError('MATCH_STRENGTH_REQUIRED')
    if a.get('boundary') not in {'范围内','灰区','范围外','未知'}:raise ValueError('BOUNDARY_REQUIRED')
    if not isinstance(a.get('subject_family'),str) or not a['subject_family'].strip():raise ValueError('SUBJECT_FAMILY_REQUIRED')
    if not isinstance(a.get('unknowns'),list) or any(not isinstance(x,str) for x in a['unknowns']):raise ValueError('UNKNOWNS_REQUIRED')
    if not isinstance(a.get('features'),list):raise ValueError('FEATURE_EVIDENCE_REQUIRED')
    names=[]
    for f in a['features']:
        if set(f)!={'name','span'} or f['name'] not in FEATURES or not f['span'] or f['span'] not in row['title_original']:raise ValueError('FEATURE_MUST_HAVE_LITERAL_TITLE_EVIDENCE')
        names.append(f['name'])
    # Multiple literal spans can support the same named feature. Conditions
    # operate on the distinct feature set, never on repeated evidence count.
    if a['relation'] in {'none','category_only','host_only'} and a['match_strength']=='强':raise ValueError('BROAD_REFERENCE_CANNOT_BE_STRONG')
    return a

def matches(rule,a):
    c=rule['conditions'];features={x['name'] for x in a['features']}
    supported=(a['information_status']=='clear' and a['form'] in c['forms']
            and (not c['families'] or a['subject_family'] in c['families']) and set(c['features_all'])<=features)
    if supported and rule['decision']=='用不到':
        anchors={x['span'].strip().casefold() for x in a['features'] if x['name'] in c['features_all']}
        # Two semantic labels citing the same keyword are not two independent
        # factual conditions for excluding a whole product.
        supported=len(anchors)>=2
    return supported

def project(row,a,catalog,rules=(),formal=None,owner=None):
    base=decide(row,a,catalog,formal or {},owner=owner)
    result=dict(base,method_version=VERSION,channel=CHANNEL,formal_publication=False,
                match_strength='未知',operating_boundary='未知',experimental_rules=[],unknowns=[])
    if not a:return result
    validate(row,a,catalog);result.update(match_strength=a['match_strength'],operating_boundary=a['boundary'],unknowns=a['unknowns'])
    if base['authority']=='HUMAN_SELECTION' or base['reason_code']=='PUBLISHED_OPERATING_RULE':return result
    matched=[r for r in rules if matches(r,a)]
    if len({r['decision'] for r in matched})>1:
        return dict(result,decision='观察',reason_code='EXPERIMENTAL_RULE_CONFLICT',operating_boundary='灰区')
    if matched:
        decision=matched[0]['decision']
        # Subject uncertainty and host-dependent accessories never get excluded by a machine rule.
        if a['information_status']!='clear' or a['form']=='unknown':decision='观察'
        if decision=='用不到' and a['form'] not in {'whole_machine','whole_system','ordinary_good'}:decision='观察'
        if decision=='保留' and not (a['relation'] in {'same_type','related_type'} and a['coverage']=='subject' and a['match_strength'] in {'强','中'}):
            return dict(result,decision='观察',reason_code='EXPERIMENTAL_RETAIN_REFERENCE_UNPROVEN',experimental_rules=[r['rule_id'] for r in matched])
        return dict(result,decision=decision,reason_code='AI_EXPERIMENTAL_RULE',
                    experimental_rules=[r['rule_id'] for r in matched],operating_boundary='范围外' if decision=='用不到' else '范围内')
    safe=(a['information_status']=='clear' and a['form'] not in {'unknown','host_component','installed_component'}
          and a['operating_context']=='daily' and a['boundary']=='范围内'
          and a['match_strength'] in {'强','中'} and a['relation'] in {'same_type','related_type'} and a['coverage']=='subject')
    result['decision']='保留' if safe else '观察'
    if not safe:
        if a['information_status']!='clear' or a['form']=='unknown':result['reason_code']='INFORMATION_INSUFFICIENT'
        elif a['form'] in {'host_component','installed_component'}:result['reason_code']='DEPENDENCY_SCOPE_UNCONFIRMED'
        elif a['boundary']!='范围内' or a['operating_context']!='daily':result['reason_code']='OPERATING_SCOPE_UNCONFIRMED'
        else:result['reason_code']='REFERENCE_NOT_SUFFICIENT'
    return result

def reconcile(row,first,second,catalog,rules=(),formal=None,owner=None):
    before=project(row,first,catalog,rules,formal,owner);after=project(row,second,catalog,rules,formal,owner)
    layers=[]
    if first and second:
        # Different Chinese family wording is a taxonomy variation, not proof
        # that the models recognized different sold objects. Disjoint literal
        # subject spans and different sold forms remain actual unresolved risks.
        fspan=first['subject_span'].casefold();sspan=second['subject_span'].casefold()
        if sale_role(first['form'])!=sale_role(second['form']) or first['information_status']!=second['information_status'] or not (fspan in sspan or sspan in fspan):layers.append('subject')
        def ref_grade(a):
            if a['relation']=='none':return ('none',)
            strength='eligible' if a['match_strength'] in {'强','中'} else 'insufficient'
            return (a['relation'],a['coverage'],strength)
        if ref_grade(first)!=ref_grade(second):layers.append('reference')
        if first['boundary']!=second['boundary'] or before['decision']!=after['decision']:layers.append('boundary')
    missing=first is None or second is None
    final=dict(after)
    # A validated boundary rule is independent of the availability of an
    # Action counterpart. Reference disagreement cannot veto an independently
    # supported whole-machine boundary; subject/boundary conflicts still can.
    resolved_by_boundary=(not missing and layers==['reference'] and before['decision']==after['decision']=='用不到'
                          and before['experimental_rules'] and after['experimental_rules'])
    if (missing or (layers and not resolved_by_boundary)) and not after['human_confirmed']:
        final.update(decision='观察',reason_code='SECOND_REVIEW_PENDING' if missing else 'UNRESOLVED_AI_DISAGREEMENT')
    return dict(final,initial_decision=before['decision'],review_decision=after['decision'],disagreement=bool(layers),
                disagreement_layers=layers,subject_error_candidate='subject' in layers,
                reference_validity='DISPUTED' if 'reference' in layers else 'AI_AGREEMENT_NOT_GOLD',
                boundary_review='DISPUTED' if 'boundary' in layers else 'AI_AGREEMENT_NOT_GOLD',
                review_completed=not missing,initial_analysis=first,review_analysis=second,
                taxonomy_variation=bool(first and second and first['subject_family']!=second['subject_family']),
                ordinary_role_granularity_variation=bool(first and second and first['form']!=second['form'] and sale_role(first['form'])==sale_role(second['form'])),
                reference_sku_variation=bool(first and second and first['action_sku']!=second['action_sku']),
                reference_disagreement_resolved_by_boundary=bool(resolved_by_boundary))
