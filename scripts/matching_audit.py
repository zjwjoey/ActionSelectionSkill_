"""Audit explicit local workbook inputs without publishing their contents."""
import argparse,collections,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from runtime.matching_v2.data_audit import read_amazon,read_action,history,summarize,write_jsonl,digest

def audit(config,work):
    work.mkdir(parents=True,exist_ok=True)
    observations=[];reports=[]
    for item in config['amazon']:
        records,report=read_amazon(item['path'],item['snapshot_date']);observations+=records;reports.append(report)
    index=history(observations)
    write_jsonl(work/'amazon_observations.jsonl',observations);write_jsonl(work/'amazon_index.jsonl',index)
    report={'inputs':reports,'combined':summarize(observations),'extra_observations_over_distinct_asins':len(observations)-len(index),'cross_file_repeated_asins':sum(len({r['source_file'] for r in x['observations']})>1 for x in index),'price_changed_asins':sum(x['price_changed'] for x in index),'name_changed_asins':sum(x['title_changed'] for x in index),'category_changed_asins':sum(x['category_changed'] for x in index),'ambiguous_latest_asins':sum(x['ambiguous_latest'] for x in index),'latest_missing_price_with_older_valid':sum(all(r['price']['value'] is None for r in x['observations'] if r['source_date']==x['latest_date']) and any(r['price']['value'] is not None for r in x['observations']) for x in index),'source_alias_authorization':config.get('source_alias_authorization'),'human_labels':0,'semantic_conflict_status':'HEURISTIC_CANDIDATES_NOT_CONFIRMED_ERRORS'}
    (work/'amazon_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    eligible={r['sku']:r for r in map(json.loads,(ROOT/'assets/action_reference10037.jsonl').read_text(encoding='utf8').splitlines())}
    action=[];sources=[]
    for item in config['action']:
        records=read_action(item['path'],item['snapshot_date'],eligible);action+=records
        sources.append({'path':item['path'],'sha256':digest(item['path']),'eligible_rows':len(records)})
    grouped=collections.defaultdict(list)
    for r in action:grouped[r['sku']].append(r)
    # Preserve all observations and flag duplicate latest sources, never silently
    # select between distinct same-date facts for price comparison.
    latest=[];conflicts=[]
    for sku,group in grouped.items():
        d=max(r['source_date'] for r in group);same=[r for r in group if r['source_date']==d]
        if len(same)>1:
            conflicts.append({'sku':sku,'date':d,'rows':same});continue
        latest+=same
    write_jsonl(work/'action_observations.jsonl',action);write_jsonl(work/'action_latest.jsonl',latest);write_jsonl(work/'action_source_conflicts.jsonl',conflicts)
    summary={'reference_skus':len(eligible),'reference_has_price':0,'reference_has_spec':0,'sources':sources,'historical_observations':len(action),'covered_skus':len(latest),'missing_or_conflicted_skus':len(eligible)-len(latest),'conflicted_skus':len(conflicts),'latest_positive_price':sum(r['price']['value'] is not None for r in latest),'latest_explicit_eur':sum(r['price']['currency']=='EUR' for r in latest),'latest_spec':sum(bool(r['spec']) for r in latest),'latest_exact_frozen_title':sum(r['title_binding_exact'] for r in latest),'latest_es_url':sum(r['country']=='ES' for r in latest),'dates':dict(collections.Counter(r['source_date'] for r in latest)),'price_capture_timestamp':'NOT_AVAILABLE_IN_EXPORTS','price_comparable_pairs':'NOT_YET_EVALUATED'}
    (work/'action_audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    return {'amazon':report['combined'],'action':{k:v for k,v in summary.items() if k!='sources'}}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--work',required=True);a=p.parse_args();w=Path(a.work).resolve()
    if not w.is_relative_to(ROOT/'work'):p.error('Private inputs/results must remain under ignored work/')
    if (w/'freeze.json').exists():p.error('Frozen experiment exists; use a new work directory for new input audit')
    print(json.dumps(audit(json.loads(Path(a.config).read_text(encoding='utf8')),w),ensure_ascii=False))
