"""Explicit provenance-bound knowledge review and publication; no fake labels."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from runtime.retail.learning import Learning
def main():
 p=argparse.ArgumentParser();p.add_argument('--store',required=True);p.add_argument('--action',choices=['propose','review','publish','inspect'],required=True);p.add_argument('--input');p.add_argument('--candidate');p.add_argument('--state');p.add_argument('--reviewer');p.add_argument('--output');a=p.parse_args();s=Learning(a.store)
 try:
  body=json.loads(Path(a.input).read_text(encoding='utf8')) if a.input else {}
  if a.action=='propose':print(s.propose(body['kind'],body['body'],body['source']))
  elif a.action=='review':print(s.transition(a.candidate,a.state,a.reviewer or '',body))
  elif a.action=='publish':print(s.publish(body['candidate_ids'],body,a.output))
  else:print(json.dumps(s.events(),ensure_ascii=False,indent=2))
 finally:s.close()
if __name__=='__main__':main()
