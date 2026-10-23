"""Frozen candidate validation; evidence and operating-policy uncertainty differ."""
import copy,re
from assortment import ROOT
import boundary_refinement_v02 as old
import semantic_understanding_v01 as binding_module
import boundary_learning as b
VERSION='boundary-v0.3-candidate'
OUT=ROOT/'v2/runs/boundary_v03_20261023'
PROMPT=ROOT/'rules/boundary-v0.3/prompt.md'
AUTHORITIES={'CODEX_SEMANTIC_REVIEW_NOT_HUMAN','CODEX_EXISTING_OPINION_MIGRATION'}
GRAY={'COMPONENT','FURNITURE_REVIEW','LARGE_FORM_REVIEW','SMALL_APPLIANCE_REVIEW','POWER_TOOL_REVIEW','CHEMICAL_MATERIAL_REVIEW','POWER_GARDEN_REVIEW','INSTALLATION_REVIEW','UNCONFIRMED','COMPLEX_AUTOMATION','FIXED_GATE_SYSTEM'}
OUTSIDE={'MAJOR_APPLIANCE','FIXED_WATER_HEATING','INDUSTRIAL_COMPLETE_MACHINE'}
KINDS=GRAY|OUTSIDE|{'CORE_GOOD'}
DEP={'host_component':'host_specific','installed_component':'installed','unknown':'unknown','universal_accessory':'universal_accessory'}
BOUNDARY_PHRASES={
 'MAJOR_APPLIANCE':r'\b(lavadora|secadora|frigor[ií]fico|nevera|lavavajillas|aire acondicionado split)\b',
 'FIXED_WATER_HEATING':r'\b(termo el[eé]ctrico|calentador de agua|calentador sin tanque)\b',
 'INDUSTRIAL_COMPLETE_MACHINE':r'\b(torno industrial|fresadora industrial|m[aá]quina industrial|torno cnc|fresadora cnc|prensa industrial)\b'}

def validate(row,a,refs):
    if a.get('analysis_authority') not in AUTHORITIES or a.get('authority')=='HUMAN' or a.get('human_gold'):raise ValueError('INVALID_AI_AUTHORITY')
    if a.get('prompt_version')!='BOUNDARY-V03-1' or a.get('prompt_sha256')!=b.b24.p.filehash(PROMPT) or a.get('method_version')!=VERSION:raise ValueError('AUDIT_METHOD_MISMATCH')
    if a.get('input_hash')!=row['input_hash'] or a.get('title_original')!=row['title_original']:raise ValueError('AUDIT_INPUT_MISMATCH')
    if a['boundary_kind'] not in KINDS:raise ValueError('UNKNOWN_BOUNDARY_KIND')
    if a['semantic']['dependency']!=DEP.get(a['sold_form'],'standalone'):raise ValueError('FORM_DEPENDENCY_CONFLICT')
    old.validate(row,a,refs)
    proof=a.get('boundary_evidence_span','')
    if proof and proof not in row['title_original']:raise ValueError('BOUNDARY_SPAN_NOT_LITERAL')
    return a

def analyze(row,base,refs,a=None):
    if a is None:
        r=old.analyze(row,base,refs);r.update(boundary_version=VERSION,review_reason_code='EVIDENCE_MISSING');return r
    validate(row,a,refs);r=old.analyze(row,base,refs,a)
    kind=a['boundary_kind'];form=a['sold_form'];reason=None
    if form=='unknown':reason='INFORMATION_INSUFFICIENT';r.update(scope='未知')
    elif form in {'host_component','installed_component'}:reason='DEPENDENCY_REVIEW';r.update(scope='灰区')
    elif kind in GRAY:reason='OPERATING_BOUNDARY_UNCONFIRMED';r.update(scope='灰区')
    elif kind in OUTSIDE:
        phrase=a.get('boundary_evidence_span','')
        if a['scope']!='范围外' or form not in {'whole_machine','whole_system'} or not re.search(BOUNDARY_PHRASES[kind],phrase,re.I):reason='BOUNDARY_EVIDENCE_CONFLICT';r.update(scope='灰区')
    elif a['scope']!='范围内':reason='SCOPE_KIND_CONFLICT';r.update(scope='灰区')
    if reason:r['decision']='待复核'
    elif r['decision']=='待复核':
        role=a['reference_proof']['role']
        reason='REFERENCE_ABSENT' if role=='none' else 'REFERENCE_COVERAGE_INCOMPLETE' if a['reference_proof']['coverage']=='partial_bundle' else 'REFERENCE_TOO_BROAD'
    if form=='unknown':
        r['subject']['status']='UNCLEAR';r['understanding_status']='INFORMATION_INSUFFICIENT'
    r.update(boundary_version=VERSION,authority=a['analysis_authority'],human_gold=False,human_reviewer='',human_review_status='UNREVIEWED',review_reason_code=reason or 'NOT_PENDING')
    r['type_function_claims']='AI_TITLE_INTERPRETATION_NOT_VERIFIED_ATTRIBUTES'
    return r
