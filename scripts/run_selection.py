"""Unified retail selection CLI. queue produces INCOMPLETE; codex uses real CLI."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from runtime.retail.engine import run,feedback

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input');p.add_argument('--source',default='auto');p.add_argument('--reference',default='action');p.add_argument('--quotes');p.add_argument('--output',required=True);p.add_argument('--source-date',default='');p.add_argument('--currency',default='');p.add_argument('--price-type',choices=['retail','wholesale','unknown'],default='unknown');p.add_argument('--mode',choices=['queue','codex','file'],default='queue');p.add_argument('--analysis');p.add_argument('--limit',type=int);p.add_argument('--batch-size',type=int,default=10);p.add_argument('--no-export',action='store_true');p.add_argument('--feedback-id');p.add_argument('--expected-hash');p.add_argument('--decision');p.add_argument('--reviewer');p.add_argument('--reason');p.add_argument('--kind',default='business')
    a=p.parse_args()
    if a.feedback_id:
        if not all([a.expected_hash,a.decision,a.reviewer,a.reason]):p.error('feedback requires hash, decision, reviewer, reason')
        print(feedback(a.output,a.feedback_id,a.expected_hash,a.decision,a.reviewer,a.reason,a.kind));return 0
    if not a.input:p.error('--input required')
    if not 1<=a.batch_size<=25:p.error('batch-size must be 1..25')
    if a.limit is not None and a.limit<1:p.error('limit must be positive')
    if a.mode=='file' and not a.analysis:p.error('file mode requires --analysis')
    s=run(a.input,a.output,a.source,a.reference,a.quotes,a.mode,a.analysis,a.source_date,a.currency,a.price_type,a.limit,a.batch_size,not a.no_export);print(json.dumps(s,ensure_ascii=False,indent=2));return 2 if s['pending'] or s['errors'] else 0
if __name__=='__main__':raise SystemExit(main())
