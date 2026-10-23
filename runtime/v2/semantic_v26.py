"""V2.6 source-bound semantic proposals, relation checks and experimental projection.

This module validates real Codex reasoning; it is NOT a language model implemented
with keyword rules. A missing deep proposal remains observation.
"""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from assortment import ROOT,RUN,Matcher,lines,read,norm
import boundary_v24 as b24
VERSION='semantic-v2.6-minimum-1'
OUT=ROOT/'v2/runs/semantic_v26_20261023'
PROMPT=ROOT/'rules/semantic_v26_prompt.md'
MODEL='CURRENT_CODEX_SESSION_LANGUAGE_REASONING;exact_model_id_not_exposed'
STATES={'保留','观察','用不到'}
RELATIONS={'A','B','C','D','E'}
BOUNDARIES={'NONE','EXPLICIT_SPLIT_AC','FIXED_WATER_HEATER','INDUSTRIAL_CONTROL','EXPLICIT_MAJOR_APPLIANCE','LARGE_COMPLETE_FURNITURE','SPECIAL_INSTALL_EQUIPMENT'}

def digest(value):return hashlib.sha256(b24.p.canonical(value).encode()).hexdigest()
def source_binding(row):
    return digest({k:row.get(k,'') for k in ['record_id','input_hash','title_original','category_l1_original','source_file_sha256','source_row']})
def cache_key(row,contract):
    return digest({'source':source_binding(row),'method':contract,'model':MODEL,'prompt':b24.p.filehash(PROMPT)})

def project(row,proposal,refs,cards):
    """Fail closed on source, reference, form or evidence contradictions."""
    if proposal['source_binding']!=source_binding(row):raise ValueError('SOURCE_BINDING_MISMATCH')
    if proposal['decision'] not in STATES or proposal['relation'] not in RELATIONS:raise ValueError('INVALID_ENUM')
    if proposal['boundary'] not in BOUNDARIES:raise ValueError('INVALID_BOUNDARY')
    if not proposal['subject_span'] or proposal['subject_span'] not in row['title_original']:raise ValueError('SUBJECT_NOT_LITERAL')
    if not proposal['need_explanation'] or not proposal['type']:raise ValueError('MISSING_SEMANTIC_REASON')
    relation=proposal['relation'];sku=proposal.get('action_sku','');reference=None
    if sku:
        if sku not in refs:raise ValueError('REFERENCE_NOT_ELIGIBLE')
        r=refs[sku]
        proof=proposal.get('reference_span','')
        if not proof or proof not in r['name_es_original']:raise ValueError('REFERENCE_PROOF_NOT_LITERAL')
        if proposal['group_id'] not in cards:raise ValueError('UNKNOWN_GROUP')
        reference={'action_sku':sku,'action_title':r['name_es_original'],'source_row_id':r['source_row_id'],'literal_span':proof,'relation':relation,'relevance_explanation':proposal['need_explanation'],'human_confirmed':False}
    elif relation!='E':raise ValueError('RELATION_WITHOUT_REAL_REFERENCE')
    decision=proposal['decision'];reason='AI_SEMANTIC_'+relation
    if decision=='保留' and (relation not in {'A','B','C'} or not proposal.get('form_compatible') or proposal['dependency'] in {'host_specific','installed','unknown'}):
        decision='观察';reason='INSUFFICIENT_RELATION_OR_FORM'
    if decision=='用不到':
        evidence=proposal.get('boundary_span','')
        if proposal['boundary']=='NONE' or not evidence or evidence not in row['title_original'] or not proposal.get('counterexample'):
            raise ValueError('EXCLUSION_WITHOUT_BOUNDARY_PROOF')
        if proposal['dependency'] in {'host_specific','universal_accessory'}:raise ValueError('ACCESSORY_CANNOT_INHERIT_HOST_EXCLUSION')
        if proposal['boundary']=='LARGE_COMPLETE_FURNITURE':
            decision='观察';reason='DAILY_FIRST_FURNITURE_RESEARCH'
        else:reason='AI_EXPERIMENTAL_BOUNDARY_NOT_HUMAN_VALIDATED'
    if decision=='观察' and reason.startswith('AI_SEMANTIC_'):reason=proposal['observation_reason'] or 'SEMANTIC_OR_SCOPE_UNCERTAINTY'
    return {**{k:row.get(k,'') for k in ['record_id','input_hash','title_original','category_l1_original','source_row','sample_cohort','review_id']},
        'version':VERSION,'source_binding':source_binding(row),'decision':decision,'reason_code':reason,
        'semantic':proposal,'action_reference':reference,'source_facts':['title_original','category_l1_original','subject_span','reference_span'],
        'inferences':['type','need_explanation','relation','form_compatible','boundary_scope'],
        'authority':'AI_PROPOSAL_NOT_HUMAN_GOLD','human_confirmed':False}

def bind_compact(row,parts,refs):
    # TSV columns: id/span/type/dependency/group/relation/sku/ref-span/decision/
    # need+relation reasoning/boundary/boundary-span/unknowns-or-observation.
    if len(parts)!=13:raise ValueError('EXPECTED_13_COLUMNS:'+str(len(parts)))
    ident,span,typ,dep,gid,rel,sku,rspan,state,need,bc,bspan,unknown=parts
    return {'review_id':ident,'subject_span':span,'type':typ,'dependency':dep,'group_id':gid,'relation':rel,'action_sku':sku,
        'reference_span':rspan,'decision':state,'need_explanation':need,'boundary':bc,'boundary_span':bspan,
        'unknowns':unknown,'observation_reason':unknown if state=='观察' else '',
        'form_compatible':dep in {'standalone','universal_accessory'},
        'form':{'standalone':'完整或独立使用商品','universal_accessory':'通用辅助用品','host_specific':'依赖特定宿主','installed':'安装型商品','unknown':'形态或主体未明'}[dep],
        'counterexample':'便携家用品、通用配件和名称中的宿主不继承此边界；仅本条明确主体作实验判断' if bc!='NONE' else '',
        'source_binding':source_binding(row),'model':MODEL,'prompt_sha256':b24.p.filehash(PROMPT),
        'prompt_version':'V26-P1','analysis_mode':'REAL_CODEX_SESSION_MANUAL_STRUCTURED_REASONING','human_confirmed':False}
