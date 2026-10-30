"""Default 0–10 matching research; no business selection decisions."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from runtime.retail.match10 import run,migrate
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--task',default='matching');p.add_argument('--input');p.add_argument('--output',required=True);p.add_argument('--source',default='auto');p.add_argument('--reference',default='action');p.add_argument('--quotes');p.add_argument('--mode',choices=['queue','codex','file'],default='queue');p.add_argument('--analysis');p.add_argument('--source-date',default='');p.add_argument('--currency',default='');p.add_argument('--price-type',choices=['retail','wholesale','unknown'],default='unknown');p.add_argument('--limit',type=int);p.add_argument('--batch-size',type=int,default=10);p.add_argument('--no-export',action='store_true');p.add_argument('--migrate-v3');p.add_argument('--import-feedback');p.add_argument('--reviewer')
 p.add_argument('--engine',choices=['v31','v32','v321'],default='v31');p.add_argument('--semantic-index');p.add_argument('--learning',choices=['off','collect','shadow','approved'],default='off');p.add_argument('--learning-store');p.add_argument('--knowledge');p.add_argument('--fine-candidates',type=int,default=20);p.add_argument('--rrf-k',type=int,default=60);p.add_argument('--no-attribute-verification',action='store_true')
 a=p.parse_args()
 if a.import_feedback:
  from runtime.retail.match10_feedback import import_feedback
  result=import_feedback(a.output,a.import_feedback,a.reviewer)
  if a.learning_store:
   from runtime.retail.learning import collect_feedback
   result['learning_proposals']=collect_feedback(a.output,a.learning_store)
  print(json.dumps(result,ensure_ascii=False));return 0
 if a.migrate_v3:print(migrate(a.migrate_v3,a.output,a.quotes,not a.no_export));return 0
 if not a.input:p.error('--input required')
 if not 1<=a.batch_size<=25:p.error('batch size 1..25')
 if a.mode=='file' and not a.analysis:p.error('--analysis required')
 extension=None
 if a.engine in ['v32','v321']:
  from runtime.retail.learning_pipeline import Extension
  extension=Extension(a.semantic_index,a.learning,a.learning_store,a.knowledge,not a.no_attribute_verification,a.fine_candidates,a.rrf_k)
 elif a.learning!='off' or a.semantic_index or a.knowledge:p.error('V3.2 options require --engine v32')
 s=run(a.input,a.output,a.source,a.reference,a.quotes,a.mode,a.analysis,a.source_date,a.currency,a.price_type,a.limit,a.batch_size,not a.no_export,extension);print(json.dumps(s,ensure_ascii=False,indent=2));return 2 if s['pending'] or s['errors'] else 0
if __name__=='__main__':raise SystemExit(main())
