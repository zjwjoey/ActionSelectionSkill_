"""Read completed analyses, propose hypotheses; never runs or approves a model."""
import json,argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from runtime.retail.discovery import discover,persist
def main():
 p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--store',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 rows=[json.loads(x) for x in (Path(a.run)/'results.jsonl').read_text(encoding='utf8').splitlines() if x]
 groups=discover(rows);persist(groups,a.store);path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(groups,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps(dict(inputs=len(rows),knowledge_hypotheses=len(groups),source_supporting_records=len({e['record_id'] for g in groups for e in g['evidence']}),human_confirmed=0,approved=0,new_model_calls=0)))
if __name__=='__main__':main()
