"""Boundary V0.2 candidate: explicit sold form and bounded reference evidence.

This validates actual AI analyses; it never fabricates semantic interpretations
or human approval. Frozen V0.1 code and outputs remain untouched.
"""
import copy
from assortment import ROOT
import boundary_learning as b
import semantic_understanding_v01 as parent

VERSION='boundary-v0.2-candidate'
OUT=ROOT/'v2/runs/boundary_v02_20261023'
PROMPT=ROOT/'rules/boundary-v0.2/evidence_prompt.md'
FORMS={'ordinary_good','bundle','universal_accessory','host_component','installed_component','whole_machine','whole_system','unknown'}
ROLES={'same_type':'A','related_type':'B','specific_need':'C','category_only':'D','host_only':'D','none':'E'}
FEATURES={'navigation','dust_disposal','mop_washing','water_management','drive','transmission','control','safety_sensor'}
COMPONENTS={'host_component','installed_component','universal_accessory'}

def validate(row,audit,refs):
    if audit.get('source_binding')!=parent.binding(row):raise ValueError('AUDIT_SOURCE_MISMATCH')
    if audit.get('human_gold') or audit.get('authority')=='HUMAN':raise ValueError('AI_NOT_HUMAN')
    p=audit['semantic']
    if p['subject_span'] not in row['title_original'] or not p['subject_span']:raise ValueError('SUBJECT_NOT_LITERAL')
    if audit['sold_form'] not in FORMS:raise ValueError('UNKNOWN_SOLD_FORM')
    proof=audit['reference_proof'];role=proof['role']
    if role not in ROLES or p['relation']!=ROLES[role]:raise ValueError('REFERENCE_ROLE_RELATION_MISMATCH')
    a=audit.get('action_reference')
    if role=='none':
        if a:raise ValueError('NONE_WITH_REFERENCE')
    else:
        if not a:raise ValueError('REFERENCE_REQUIRED')
        ref=refs.get(a['action_sku'])
        if not ref or a['action_title']!=ref['name_es_original'] or a['source_row_id']!=ref['source_row_id']:raise ValueError('REFERENCE_SOURCE_MISMATCH')
        if not proof.get('source_span') or proof['source_span'] not in row['title_original']:raise ValueError('REFERENCE_SOURCE_SPAN_REQUIRED')
        if not proof.get('reference_span') or proof['reference_span'] not in a['action_title']:raise ValueError('REFERENCE_LITERAL_SPAN_REQUIRED')
        if role in {'same_type','related_type','specific_need'} and not proof.get('bounded_relationship','').strip():raise ValueError('BOUNDED_RELATIONSHIP_REQUIRED')
        if proof.get('coverage') not in {'subject','partial_bundle','host_only','category_only'}:raise ValueError('REFERENCE_COVERAGE_REQUIRED')
    parent.validate_semantic(row,audit,refs)
    seen=set();ranges=[]
    for feature in audit.get('functional_features',[]):
        tag=feature['tag'];span=feature['span']
        if tag not in FEATURES or tag in seen:raise ValueError('DUPLICATE_OR_UNKNOWN_FUNCTION')
        start=row['title_original'].find(span)
        if not span or start<0:raise ValueError('FUNCTION_NOT_LITERAL')
        end=start+len(span)
        if any(start<z and end>x for x,z in ranges):raise ValueError('FUNCTION_SPAN_DOUBLE_COUNT')
        seen.add(tag);ranges.append((start,end))
    return audit

def analyze(row,baseline,refs,audit=None):
    if audit is None:
        result=parent.analyze(row,baseline,refs)
        result.update(decision='待复核',boundary_version=VERSION,evidence_status='NEEDS_STRUCTURED_AUDIT',
                      boundary_rule='V02_EVIDENCE_PENDING',reason='缺少当前版本的主体形态与参照证明；不自动纳入或排除')
        return result
    validate(row,audit,refs)
    result=parent.analyze(row,baseline,refs,audit)
    result.update(boundary_version=VERSION,sold_form=audit['sold_form'],reference_proof=copy.deepcopy(audit['reference_proof']),
                  evidence_status='AI_REVIEWED_NOT_HUMAN_CONFIRMED',audit_issue_codes=list(audit['issue_codes']))
    form=audit['sold_form'];boundary=audit['boundary_kind'];p=audit['semantic'];role=audit['reference_proof']['role']
    reject_reason=None
    if audit['scope']=='范围外':
        if form in COMPONENTS:reject_reason='COMPONENT_NOT_COMPLETE_SYSTEM'
        elif form not in {'whole_machine','whole_system'}:reject_reason='OUTSIDE_BOUNDARY_NOT_CONFIRMED'
        elif boundary not in {'MAJOR_APPLIANCE','FIXED_WATER_HEATING','INDUSTRIAL_COMPLETE_MACHINE','COMPLEX_AUTOMATION','FIXED_GATE_SYSTEM'}:reject_reason='OUTSIDE_BOUNDARY_NOT_CONFIRMED'
        else:
            tags={f['tag'] for f in audit.get('functional_features',[])}
            if boundary=='COMPLEX_AUTOMATION' and len(tags&{'navigation','dust_disposal','mop_washing','water_management'})<3:reject_reason='AUTOMATION_EVIDENCE_INSUFFICIENT'
            if boundary=='FIXED_GATE_SYSTEM' and not {'drive','transmission','control'}<=tags:reject_reason='COMPLETE_GATE_EVIDENCE_INSUFFICIENT'
        if reject_reason:result.update(decision='待复核',scope='灰区',boundary_rule='V02_'+reject_reason,reason=audit['reason']+'；不满足完整主体／边界证明')
    if form=='unknown' or p['dependency']=='unknown':
        result.update(decision='待复核',scope='未知',boundary_rule='V02_INFORMATION_INSUFFICIENT')
    if result['decision']=='纳入候选' and (role in {'host_only','category_only','none'} or audit['reference_proof'].get('coverage')!='subject'):
        result.update(decision='待复核',boundary_rule='V02_REFERENCE_NOT_SUBJECT_PROOF',reason=audit['reason']+'；参照不足以支持完整销售主体')
    result['candidate_boundary_kind']=boundary
    result['functional_features']=copy.deepcopy(audit.get('functional_features',[]))
    result['human_gold']=False;result['human_reviewer']='';result['human_review_status']='UNREVIEWED'
    return result
