"""Portable read-only reference lookup; not an autonomous selection model."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def readlines(p):
 with p.open(encoding='utf-8') as f:
  for s in f:
   if s.strip():yield json.loads(s)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('command',choices=['info','verify','search','reference']);parser.add_argument('--title');parser.add_argument('--sku');parser.add_argument('--top',type=int,default=5);args=parser.parse_args()
 if args.command=='verify':
  manifest=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'));bad=[]
  for rel,expected in manifest['files'].items():
   p=ROOT/rel
   if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected['sha256']:bad.append(rel)
  print(json.dumps({'ok':not bad,'checked':len(manifest['files']),'mismatches':bad},ensure_ascii=False));return 1 if bad else 0
 if args.command=='info':
  m=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'));print(json.dumps({k:v for k,v in m.items() if k!='files'},ensure_ascii=False,indent=2));return 0
 if args.command=='reference':
  if not args.sku:parser.error('--sku required')
  ref=next((r for r in readlines(ROOT/'assets/action_reference10037.jsonl') if r['sku']==args.sku),None)
  semantic=next((r for r in readlines(ROOT/'assets/action_semantics/results.jsonl') if r['sku']==args.sku),None)
  print(json.dumps({'reference':ref,'semantic_candidate':semantic},ensure_ascii=False,indent=2));return 0 if ref else 2
 if not args.title:parser.error('--title required')
 sys.path.insert(0,str(ROOT/'runtime/v2'))
 from assortment import Matcher
 matcher=Matcher();items=[]
 for i,score in matcher.retrieve([args.title])[0][:max(1,min(args.top,20))]:
  r=matcher.model['references'][i];items.append({'sku':r['sku'],'name_es_original':r['name_es_original'],'source_row_id':r['source_row_id']})
 print(json.dumps({'input_title':args.title,'retrieval_only_not_selection':True,'candidates':items},ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
