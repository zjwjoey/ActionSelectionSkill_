"""Independent-label gates; absence of labels is not zero error."""
def metrics(predictions,labels):
 valid=[x for x in labels if x.get('authority')=='HUMAN_VERIFIED' and x.get('reviewer') and x.get('evidence')]
 by={x['record_id']:x for x in valid};known=[p for p in predictions if p['record_id'] in by]
 result=dict(labelled_inputs=len(known),recall_at_20=None,recall_at_50=None,precision_at_1=None,high_score_errors=None,no_match_quality=None,authority='INDEPENDENT_LABELS_ONLY')
 if not known:return result
 # A retrieval label needs a catalog-wide review, not just marking one retrieved pair.
 covered=[p for p in known if by[p['record_id']].get('catalog_search_complete') and by[p['record_id']].get('relevant_reference_ids')]
 for k in [20,50]:
  if covered:result['recall_at_'+str(k)]=sum(len(set(p['retrieval_trace']['rrf50'][:k])&set(by[p['record_id']]['relevant_reference_ids']))/len(set(by[p['record_id']]['relevant_reference_ids'])) for p in covered)/len(covered)
 top=[p for p in known if by[p['record_id']].get('top1_judged')]
 if top:
  correct=lambda p:(p.get('primary') or {}).get('reference_id') in by[p['record_id']].get('relevant_reference_ids',[])
  result['precision_at_1']=sum(correct(p) for p in top)/len(top)
  result['high_score_errors']=sum(p.get('match_score_10') is not None and p['match_score_10']>=7 and not correct(p) for p in top)
 return result
def training_readiness(labels,min_labels=200):
 valid=[l for l in labels if l.get('authority')=='HUMAN_VERIFIED' and l.get('reviewer') and l.get('evidence')]
 ids=[x['record_id'] for x in valid]
 if len(set(ids))!=len(ids):raise ValueError('DUPLICATE_TRAINING_INPUT_LABEL')
 partitions={s:{l['record_id'] for l in valid if l.get('split')==s} for s in ['train','dev','test']}
 enough=len(valid)>=min_labels and all(partitions.values()) and len({l.get('product_type') for l in valid if l.get('product_type')})>=5
 return dict(eligible_for_isolated_experiment=bool(enough),independent_labels=len(valid),partitions={s:len(v) for s,v in partitions.items()},automatic_training=False,automatic_promotion=False,reason='READY_FOR_SEPARATE_REVIEW' if enough else 'INSUFFICIENT_INDEPENDENT_LABELS_OR_TYPE_COVERAGE')
