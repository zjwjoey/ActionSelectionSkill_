"""Apply a frozen title-only context policy to Action candidate proposals.

This refines existing candidates, never Master, source text, feedback or gold.
Use with --input, --policy and --output; each output is create-once.
"""
import argparse
import copy
import json
import re
from pathlib import Path
import pipeline as p


def read_policy(path):
    if Path(path).suffix.lower() == '.json':
        # Replay the actual versioned contract, not an editable authoring file.
        result = json.loads(Path(path).read_text(encoding='utf8'))['rules']
        for rule in result:
            re.compile(rule['regex'], re.I)
        return result
    result = []
    for line in Path(path).read_text(encoding='utf8').splitlines():
        if not line or line.startswith('#'):
            continue
        key, rest = line.split('|', 1)
        regex, typ, l1, l2, fun, need, scene, tag = rest.rsplit('|', 7)
        re.compile(regex, re.I)
        result.append(dict(id=key, regex=regex, product_type=typ,
                           category_l1=l1, category_l2=l2, function=fun,
                           need=need, scene=scene, tag=tag))
    return result


def apply(record, rules):
    x = copy.deepcopy(record)
    if 'SOURCE_LANGUAGE_INVALID' in x['uncertainty_codes']:
        return x, None
    matches = [(r, re.search(r['regex'], x['name_es_original'], re.I)) for r in rules]
    matches = [(r, m) for r, m in matches if m]
    if not matches:
        return x, None
    # Specific context rules follow broad alternatives and take precedence.
    rule, match = matches[-1]
    usable = rule['category_l1'] != '未确定'
    code = 'SUBTYPE_UNSPECIFIED' if usable else 'DOMAIN_AMBIGUOUS'
    x.update(category_l1=rule['category_l1'], category_l2=rule['category_l2'],
             product_type=rule['product_type'], primary_function=[rule['function']] if usable else [],
             consumer_need=[rule['need']] if usable else ['核心用途待核'],
             usage_scenario=[rule['scene']], action_pattern=[rule['tag']] if rule['tag'] else [],
             confidence='中' if usable else '低', review_status='待审核' if usable else '信息不足',
             uncertainty_codes=[code], dimension_confidence={
                 'product_identity': '高' if usable else '中', 'primary_domain': '中' if usable else '低',
                 'function': '中' if usable else '低', 'scenario': '中' if usable else '低'},
             usable_for_candidate_observations=usable,
             checkpoint_queue_reason='CLEAR_CONTEXT_CANDIDATE' if usable else code)
    x['evidence'] = {
        'title_spans': list(dict.fromkeys([match.group(), x['name_es_original']])),
        'inference_boundary': '主体及限定关系依据本条原名；常规用途仅为候选推断。'
        '不凭品牌补用途、结构、性能、材质或采购动机；未明用途保持待核。通用上下文规则：' + rule['id']}
    previous = x['ai_review']
    x['ai_review'] = {**previous,
        'parent_annotation_hash': record['annotation_hash'],
        'parent_rules_version': record['rules_version'],
        'decision': 'CORRECTED' if usable else 'ABSTAIN_RETAINED',
        'reason': 'Title-only context boundary refinement: ' + rule['id'],
        'candidate_usable': usable, 'queue_reason': x['checkpoint_queue_reason'],
        'context_rule': rule['id']}
    x['annotation_hash'] = p.digest({k:x[k] for k in (*p.FIELDS, *p.EXTRA_FIELDS) if k in x})
    return x, rule['id']


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('input', 'policy', 'output'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    rules = read_policy(args.policy)
    pairs = [apply(x, rules) for x in p.read_jsonl(Path(args.input))]
    p.immutable(Path(args.output), [x for x, _ in pairs], jsonl=True)
    print(json.dumps({'processed':len(pairs), 'context_refinements':sum(bool(r) for _,r in pairs)}, ensure_ascii=False))
