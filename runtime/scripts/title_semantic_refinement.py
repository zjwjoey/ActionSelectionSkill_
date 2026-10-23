"""Replayable, title-only refinements of versioned candidates; never human gold.

This is a refinement pass, not a new independent semantic classifier. Frozen
parent proposals are explicit inputs. Rules contain no SKU identifiers.
"""
import copy,json,re
from pathlib import Path

VERSION='name-semantics-v10-context-guard'

def apply(record,definitions):
    result=copy.deepcopy(record);hits=[];spans=[]
    policy=definitions['semantic_refinement.json']
    # Preserve source and unresolved cohorts; refinements never invent a recovery.
    if not record['usable_for_candidate_observations']:
        return result,hits
    for rule in policy['rules']:
        title=record['name_es_original']
        match=re.search(rule['regex'],title,re.I)
        if not match or (rule.get('exclude_regex') and re.search(rule['exclude_regex'],title,re.I)):
            continue
        if rule.get('require_regex') and not re.search(rule['require_regex'],title,re.I):
            continue
        patch=rule['patch']
        if all(result.get(k)==v for k,v in patch.items()):
            continue
        result.update(copy.deepcopy(patch));hits.append(rule['id']);spans.append(match.group())
    if not hits:
        return result,hits
    uncertain=bool(set(result['uncertainty_codes'])&set(definitions['name_rules.json']['blocking_uncertainty_codes']))
    result['review_status']='信息不足' if uncertain else '待审核'
    result['confidence']='低' if uncertain else result.get('confidence','高')
    if uncertain:
        result['dimension_confidence']={'product_identity':'中','primary_domain':'中','function':'低','scenario':'低'}
    result['usable_for_candidate_observations']=not uncertain
    result['checkpoint_queue_reason']='TITLE_FUNCTION_UNRESOLVED' if uncertain else 'CLEAR_CANDIDATE_REVIEWED'
    result['evidence']={
        'title_spans':list(dict.fromkeys(spans+[record['name_es_original']])),
        'inference_boundary':'命名词及其修饰关系支持所列对象/用途；所有功能均为名称宣称或该对象的常规用途候选，消费需求属于AI概括。未出现的疗效、销量、材质、食用对象、规格、交付形态与采购动机不作事实。规则：'+', '.join(hits)
    }
    result['ai_review']={'round_id':'review150-20261022','reviewer_kind':'AI','reviewer':'Codex-authored compositional refinement rules','decision':'ABSTAIN_RETAINED' if uncertain else 'CORRECTED','reason':'通用对象/用途关系复核：'+', '.join(hits),'parent_annotation_hash':record['annotation_hash'],'parent_rules_version':record['rules_version']}
    result['rules_version']=policy['version']
    return result,hits

def validate(record,source,definitions):
    # The legacy importer validates extra fields only for v2. Apply the complete
    # contract explicitly for this newer version before the normal import.
    import pipeline as p
    p.validate_annotation(record,source,definitions['name_rules.json']['version'])
    nr=definitions['name_rules.json']
    assert record['category_l1'] in definitions['taxonomy.json']['category_l1_candidates']
    assert all(t in definitions['function_tags.json']['action_pattern_candidates'] for t in record['action_pattern'])
    assert isinstance(record['uncertainty_codes'],list) and all(c in nr['uncertainty_codes'] for c in record['uncertainty_codes'])
    assert set(record['dimension_confidence'])==set(nr['dimension_confidence_fields'])
    assert set(record['dimension_confidence'].values())<={'高','中','低'}
    assert bool(set(record['uncertainty_codes'])&set(nr['blocking_uncertainty_codes']))==(record['review_status']=='信息不足')
    assert record['name_es_original']==source['name_es_original']
    assert record['human_confirmed'] is False
    assert record['review_status'] in {'待审核','信息不足'}
    assert record['ai_review']['reviewer_kind']=='AI'
    assert record['ai_review']['decision'] in definitions['taxonomy.json']['review_decisions']

def main():
    import argparse,hashlib,sys
    import pipeline as p
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--rules-version',default=VERSION)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    dest=Path(args.output).resolve()
    if not dest.is_relative_to(root/'outputs'):
        raise ValueError('OUTPUT_MUST_STAY_IN_INDEPENDENT_PROJECT_OUTPUTS')
    rows=p.read_jsonl(Path(args.input));definitions=p.load_rules(args.rules_version)
    assert len(rows)==len({x['sku'] for x in rows})==2000
    results=[];changed=[]
    for x in rows:
        new,hits=apply(x,definitions);validate(new,x,definitions)
        if hits:
            new['annotation_hash']=p.digest({k:new[k] for k in (*p.FIELDS,*p.EXTRA_FIELDS) if k in new})
            changed.append(x['sku'])
        results.append(new)
    p.immutable(dest,results,jsonl=True)
    print(json.dumps({'evaluated':len(results),'revised':len(changed),'revised_skus':changed,'mode':'read-only learning DB; immutable candidate export only','rules_version':args.rules_version},ensure_ascii=False))

if __name__=='__main__':main()
