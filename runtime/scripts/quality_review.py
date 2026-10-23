"""Local structural checks and source quality audit; no external/model calls."""
import csv
import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

import storage
from pipeline import ROOT, RULE_VERSION, filehash, get_folder, read_jsonl, validate_annotation, validate_snapshot, immutable

SID = "master_d1af859e842adbe1"
BATCH = "pilot100_c2217cd5173d"


def main():
    manifest = validate_snapshot(SID)
    folder = get_folder(SID, BATCH)
    proposals, feedback = storage.state(ROOT, BATCH)
    assert len(proposals) == 100
    members = storage.members(ROOT, BATCH)
    blind = {x['sku']: x for x in storage.members(ROOT, BATCH, blind=True)}
    assert set(proposals) == set(blind)
    assert all(set(x) == {'sku','name_es_original','name_es_normalized','source_row_id','snapshot_id'} for x in blind.values())
    all_rows = storage.load_products(ROOT,SID)
    source_issues=[]
    for x in all_rows:
        title=x['name_es_normalized']
        if re.search(r'[\u3400-\u9fff]',title):
            source_issues.append({'sku':x['sku'],'name_es_original':x['name_es_original'],'source_row_id':x['source_row_id'],'issue':'NON_SPANISH_HAN_IN_NAME'})
        elif not re.search(r'[A-Za-zÀ-ÿ]', title):
            source_issues.append({'sku':x['sku'],'name_es_original':x['name_es_original'],'source_row_id':x['source_row_id'],'issue':'NO_LATIN_LETTERS_IN_NAME'})
    taxonomy=json.loads((ROOT/'rules/taxonomy.json').read_text(encoding='utf-8'))
    tags=json.loads((ROOT/'rules/function_tags.json').read_text(encoding='utf-8'))
    conflicts=[];by_title=defaultdict(set)
    for sku,x in proposals.items():
        validate_annotation(x,blind[sku])
        if x['category_l1'] not in taxonomy['category_l1_candidates']:
            conflicts.append({'sku':sku,'issue':'UNKNOWN_L1'})
        if any(t not in tags['action_pattern_candidates'] for t in x['action_pattern']):
            conflicts.append({'sku':sku,'issue':'UNKNOWN_PATTERN_TAG'})
        by_title[x['name_es_normalized'].casefold()].add((x['category_l1'],x['category_l2'],x['product_type']))
    for title,labels in by_title.items():
        if len(labels)>1: conflicts.append({'title':title,'issue':'IDENTICAL_NAME_DIFFERENT_LABELS'})
    assert not conflicts,conflicts
    source_hash_after=filehash(Path(manifest['source']))
    assert source_hash_after==manifest['source_before']['sha256']
    with sqlite3.connect(ROOT/'learning_data/action_selection.sqlite3') as c:
        check=c.execute('pragma integrity_check').fetchall();fk=c.execute('pragma foreign_key_check').fetchall()
        assert check==[('ok',)] and not fk
        table_counts={t:c.execute('select count(*) from '+t).fetchone()[0] for t in ['products','source_rows','sample_members','analyses','feedback','rule_versions']}
    versions={x['rules_version'] for x in proposals.values()}
    assert len(versions)==1,'Report homogeneous review rounds separately'
    version=next(iter(versions))
    output=ROOT/'reports'/SID/BATCH/version
    output.mkdir(parents=True,exist_ok=True)
    with (output/'posthoc_category_comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['SKU','西语品名','仅事后对照的原始类目','AI一级类目','AI二级类目','判断状态'])
        for m in members:
            x=proposals[m['sku']];w.writerow([m['sku'],x['name_es_original'],m['category_original'],x['category_l1'],x['category_l2'],x['review_status']])
    immutable(ROOT/'reports'/SID/'source_name_quality_issues.json',source_issues)
    reasons=Counter()
    for x in proposals.values():
        if x['review_status']=='信息不足':
            reasons['西语源混入中文' if x['category_l2']=='西语源异常' else '品名信息不足或多义']+=1
    patterns=Counter(t for x in proposals.values() if x['review_status']!='信息不足' for t in x['action_pattern'])
    grouped=defaultdict(list)
    for x in proposals.values():
        if x['review_status']!='信息不足':grouped[x['category_l1']].append(x['sku'])
    type_pairs=defaultdict(set)
    for x in proposals.values():type_pairs[x['category_l1']].add(x['category_l2'])
    immutable(output/'observed_pilot_taxonomy.json',{'version':version,'status':'100-title candidate taxonomy, not human-confirmed','l1_l2_candidates':{k:sorted(v) for k,v in sorted(type_pairs.items())}})
    # The observed taxonomy is an output, not an input rule; exclude it from the frozen rules version.
    report={'status':'PASS','snapshot_id':SID,'sample_id':BATCH,'master_sha256_before':manifest['source_before']['sha256'],'master_sha256_after':source_hash_after,'master_unchanged':True,
            'total_skus':len(all_rows),'nonempty_names':sum(bool(x['name_es_normalized']) for x in all_rows),'names_with_non_spanish_script':len(source_issues),
            'latin_script_name_candidates_not_language_verified':len(all_rows)-len(source_issues),'processed_skus':100,'classified_or_partially_classified':sum(x['review_status']!='信息不足' for x in proposals.values()),
            'insufficient_information':sum(x['review_status']=='信息不足' for x in proposals.values()),'insufficient_reasons':dict(reasons),'detected_structural_classification_conflicts':len(conflicts),
            'human_confirmed':len([x for x in feedback.values() if x.get('review_status')=='已确认']),'rules_version':version,'learning_database_integrity':'PASS','foreign_keys':'PASS','database_counts':table_counts,
            'inference_inputs':'Spanish title only; source category exposed only to sampling and posthoc comparison','no_price_scoring':True,'no_network_collection':True,'parameter_training':False,
            'source_reference_and_evidence_checks':'100/100 PASS','same_title_different_sku_preserved':True,'next_500':'NOT_STARTED; requires human review, source quality handling and explicit authorization'}
    (output/'p1_quality_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'pattern_observations.json').write_text(json.dumps({'basis':'100 title-only proposals, not reviewed truth; stratified sample, counts are not full-catalog frequencies','pattern_counts':dict(patterns),'category_examples_skus':dict(grouped),'not_inferred':['sales','profit','buying reasons','full Action purchasing strategy']},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
