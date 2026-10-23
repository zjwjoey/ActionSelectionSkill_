"""Boundary V0.1: understand sold object before scope; source-bound AI inbox.

Unproved machine heads are escalated, never guessed from appliance mentions.
No new per-product noun list or SKU condition is used by the repair.
"""
from __future__ import annotations
import re
from pathlib import Path
from assortment import ROOT,lines,norm
import boundary_learning as previous
VERSION='boundary-v0.1-candidate'
OUT=ROOT/'v2/runs/boundary_v01_20261023'
PROMPT=ROOT/'rules/boundary-v0.1/semantic_prompt.md'
HIGH_RISK={'WASHER','DRYER','FRIDGE','DISHWASHER','AC','FIXED_WATER_HEATER','INDUSTRIAL_MACHINE','FIXED_SMOKE_SYSTEM','ROBOT_CLEANER'}
def binding(row):return previous.binding(row)
def save(name,data,jsonl=False):previous.b24.p.immutable(OUT/name,data,jsonl=jsonl)
def literal_head_proof(title,span):
    """A matched late host is not proof of a whole object. Unknown brand/prefix
    requires semantic review rather than silently skipping words as a brand.
    """
    t=norm(title);needle=norm(span)
    if not needle or needle not in t:return False
    prefix=t[:t.index(needle)].strip()
    # Grammatical quantity/article prefixes only; never arbitrary brand tokens.
    prefix=re.sub(r'\b(?:un|una|el|la|los|las|\d+|unidad|unidades)\b','',prefix).strip(' -:,.')
    return not prefix
def load_existing_candidates():
    bybinding={}
    for n in [500,200,49]:
        for row in lines(previous.OUT/f'semantic_{n}.jsonl'):bybinding[row['source_binding']]=row
    return bybinding
def validate_semantic(row,semantic,refs):
    if semantic.get('source_binding')!=binding(row):raise ValueError('SEMANTIC_SOURCE_MISMATCH')
    p=semantic['semantic']
    if not p['subject_span'] or p['subject_span'] not in row['title_original']:raise ValueError('SEMANTIC_SUBJECT_NOT_LITERAL')
    if p['dependency'] not in {'standalone','universal_accessory','host_specific','installed','unknown'}:raise ValueError('INVALID_DEPENDENCY')
    if p['relation'] not in {'A','B','C','D','E'}:raise ValueError('INVALID_RELATION')
    if semantic['scope'] not in {'范围内','灰区','范围外','未知'}:raise ValueError('INVALID_SCOPE')
    a=semantic.get('action_reference')
    if a:
        ref=refs.get(a['action_sku'])
        if not ref or a['action_title']!=ref['name_es_original'] or a['source_row_id']!=ref['source_row_id']:raise ValueError('SEMANTIC_REFERENCE_NOT_REAL')
    elif p['relation']!='E':raise ValueError('RELATION_WITHOUT_REFERENCE')
    if semantic.get('human_gold') or semantic.get('authority')=='HUMAN':raise ValueError('AI_CANNOT_CREATE_HUMAN_GOLD')
    return semantic

def analyze(row,baseline,refs,semantic=None):
    # A known-source AI proposal is an explicit semantic input, not a silent
    # replacement for a human label or an inferred approval for a new version.
    if semantic:
        validate_semantic(row,semantic,refs)
        result=previous.analyze(row,baseline,semantic)
        result.update(boundary_version=VERSION,understanding_status='AI_CANDIDATE' if semantic['semantic']['dependency']!='unknown' else 'INFORMATION_INSUFFICIENT',
            semantic_lineage={'source_binding':semantic['source_binding'],'model':semantic.get('model',''),'prompt_version':semantic.get('prompt_version',''),'reused_existing_opinion':semantic.get('prompt_version')!='BOUNDARY-V01-SEMANTIC-1'},
            function_need_hypothesis=semantic['semantic'].get('function_need_hypothesis') or semantic['reason'],uncertainties=semantic['semantic'].get('unknowns',''))
        if semantic['semantic']['dependency']=='unknown':result.update(scope='未知',decision='待复核',boundary_rule='SEMANTIC_INFORMATION_INSUFFICIENT')
        return result
    subject=previous.enrich_subject(row['title_original'],baseline['subject'])
    if subject.get('class_code') in HIGH_RISK and not literal_head_proof(row['title_original'],subject.get('evidence_span','')):
        # Discard BOTH the guessed subject and its host-derived reference. This
        # fixes the contract, not just the final exclusion label.
        result=previous.analyze(row,{'subject':{'status':'UNCLEAR','class_code':'','evidence_span':'','dependent':False},'action_references':[]})
        result.update(subject={'status':'UNCLEAR','class_code':'','evidence_span':'','dependent':False,'rejected_host_candidate':subject,'role_status':'SOLD_HEAD_UNPROVEN'},
            scope='未知',decision='待复核',boundary_rule='SOLD_HEAD_REQUIRES_SEMANTIC_REVIEW',reason='设备词缺少销售主体证明；撤销宿主类型及其参照，进入语义队列',understanding_status='NEEDS_AI')
    else:
        result=previous.analyze(row,baseline)
        result['understanding_status']='LOCAL_CANDIDATE' if result['subject'].get('status')=='CLEAR' else 'NEEDS_AI'
        if subject.get('class_code') in HIGH_RISK:
            # Even a first-word appliance noun can be a mistranslated product
            # name (e.g. "Refrigerador Eliminador De Olor"). A local match alone
            # never certifies a whole-machine exclusion in this candidate.
            result.update(subject={'status':'UNCLEAR','class_code':'','evidence_span':'','dependent':False,'local_machine_candidate':subject},
                action_reference=None,action_relation='E',action_match_strength='未知',scope='未知',decision='待复核',
                boundary_rule='MACHINE_SEMANTIC_CONFIRMATION_REQUIRED',reason='本地设备词仅为候选，先确认实际销售对象再判断边界',understanding_status='NEEDS_AI')
    result.update(boundary_version=VERSION,function_need_hypothesis='',uncertainties='未使用AI补全未知事实；本地候选不代表人工确认')
    return result

def pending_key(row):
    return previous.digest({'binding':binding(row),'model':'CURRENT_CODEX_SESSION_EXACT_ID_NOT_EXPOSED','prompt_sha':previous.b24.p.filehash(PROMPT),'method':VERSION})
