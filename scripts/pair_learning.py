"""V3.3 opt-in pair dataset / training / ranking / feedback tools.

Existing ingestion, retrieval, AI and scoring remain in run_selection.py.
This command only consumes their immutable artifacts.
"""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from runtime.retail.pair_learning import (read,save,build_pairs,grouped_split,FeatureExtractor,
 train,load_model,rerank,evaluate,active_queue,LabelStore,digest)
from runtime.retail.pair_feedback import validate_dataset,materialize,ModelRegistry

def main():
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
 b=sub.add_parser('dataset');b.add_argument('--results',required=True);b.add_argument('--requests',required=True);b.add_argument('--output',required=True);b.add_argument('--quotes');b.add_argument('--semantic-index',required=True);b.add_argument('--candidate-count',type=int,default=8)
 t=sub.add_parser('train');t.add_argument('--pairs',required=True);t.add_argument('--output',required=True);t.add_argument('--variant',choices=['B','C'],default='B');t.add_argument('--regularization',type=float,default=1.)
 for name in ['rank','evaluate','active']:
  q=sub.add_parser(name);q.add_argument('--pairs',required=True);q.add_argument('--model-b',required=True);q.add_argument('--model-c');q.add_argument('--output',required=True);q.add_argument('--allow-experimental',action='store_true')
 f=sub.add_parser('import-labels');f.add_argument('--pairs',required=True);f.add_argument('--labels',required=True);f.add_argument('--store',required=True)
 f=sub.add_parser('materialize');f.add_argument('--pairs',required=True);f.add_argument('--store',required=True);f.add_argument('--output',required=True)
 f=sub.add_parser('register');f.add_argument('--model',required=True);f.add_argument('--store',required=True)
 f=sub.add_parser('select-model');f.add_argument('--model-hash',required=True);f.add_argument('--reason',required=True);f.add_argument('--store',required=True);f.add_argument('--allow-experimental',action='store_true')
 a=p.parse_args()
 if a.command=='dataset':
  from runtime.retail.engine import References
  refs=References('action',a.quotes);extractor=FeatureExtractor(refs,a.semantic_index)
  rows=build_pairs(read(a.results),{r['record_id']:r for r in read(a.requests)},a.candidate_count)
  families={s:e.get('product_type_candidate') or s for s,e in refs.catalog.semantics.items()};split=grouped_split(rows,families)
  by={}
  for r in rows:by.setdefault(r['input_id'],[]).append(r)
  from runtime.v3.workflow import write_jsonl
  out=Path(a.output)
  if out.exists():raise ValueError('DATASET_OUTPUT_ALREADY_EXISTS')
  out.mkdir(parents=True)
  for i,group in enumerate(by.values(),1):
   features,trace=extractor.query(group[0]['input'],[r['reference']['sku'] for r in group])
   for r in group:r.update(features=features[r['reference']['sku']],feature_binding=extractor.binding,retrieval_trace=trace)
   print(json.dumps(dict(features_done=i,total=len(by))),flush=True)
  write_jsonl(out/'pairs.jsonl',rows);save(out/'split.json',split);save(out/'dataset.json',dict(hash=digest(rows),split=split,feature_binding=extractor.binding,products=len(by),pairs=len(rows)))
 elif a.command=='train':
  rows=read(a.pairs);validate_dataset(rows);print(json.dumps(train(rows,a.output,a.variant,a.regularization),ensure_ascii=False))
 elif a.command=='materialize':print(json.dumps(materialize(a.pairs,a.store,a.output),ensure_ascii=False))
 elif a.command in ['register','select-model']:
  registry=ModelRegistry(a.store)
  try:print(registry.register(a.model) if a.command=='register' else registry.select(a.model_hash,a.reason,a.allow_experimental))
  finally:registry.close()
 elif a.command=='import-labels':
  pairs={r['pair_id']:r for r in read(a.pairs)};store=LabelStore(a.store)
  try:print(json.dumps([store.import_label(r,pairs) for r in read(a.labels)]))
  finally:store.close()
 else:
  if not a.allow_experimental:raise ValueError('EXPLICIT_EXPERIMENTAL_OPT_IN_REQUIRED')
  rows=read(a.pairs);models={'B':load_model(a.model_b)}
  if a.model_c:models['C']=load_model(a.model_c)
  out=Path(a.output)
  if out.exists():raise ValueError('OUTPUT_ALREADY_EXISTS_USE_NEW_VERSION')
  if a.command=='evaluate':value=evaluate(rows,models)
  elif a.command=='active':value=active_queue(rows,models)
  else:
   from collections import defaultdict
   by=defaultdict(list)
   for r in rows:by[r['input_id']].append(r)
   value=[dict(input_id=s,model=k,ordered_pair_ids=[p['pair_id'] for p in rerank(m,g,True)],score_semantics='rank utility only; original scores unchanged') for s,g in by.items() for k,m in models.items()]
  save(out,value)
 return 0
if __name__=='__main__':raise SystemExit(main())
