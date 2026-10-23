"""Freeze V2 inputs while retaining every historical learning table and file."""
import json,sqlite3,sys,shutil,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'v2';sys.path.insert(0,str(ROOT/'scripts'))
import pipeline as p

def main():
 out=WORK/'runs/action_assortment_v2_20261022';out.mkdir(parents=True,exist_ok=True)
 protected_files=list((ROOT/'rules/versions/name-semantics-v10-context-guard').glob('*.json'))
 protected_files+=list((ROOT/'rules/versions/name-semantics-v11-action5000-candidate').glob('*.json'))
 protected_files+=[ROOT/'learning_data/p11/sealed_unseen50_plan.json',ROOT/'outputs/review150_rules_20261022/final_2000_candidates.jsonl',ROOT/'outputs/staged_5000_20261022/cumulative5000_candidates.jsonl',ROOT/'scripts/pipeline.py',ROOT/'scripts/storage.py']
 for trial in ['p3_ab100_20261022','p31_ab200_20261022']:
  protected_files += [ROOT/'outputs'/trial/arm/'result.jsonl' for arm in ['A','B']]
 master=Path('F:/ActionSKUTracker/runtime/master/Action_Master.xlsx');protected_files.append(master)
 frozen={str(f):p.filehash(f) for f in protected_files}
 db=ROOT/'learning_data/action_selection.sqlite3';backup=out/'learning_before_v2.sqlite3'
 with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as c:
  if not backup.exists():
   with sqlite3.connect(backup) as b:c.backup(b)
  counts={t:c.execute('select count(*) from '+t).fetchone()[0] for t in ['sample_members','analyses','feedback','benchmark_adjudications','cross_platform_samples','cross_platform_proposals']}
 p.immutable(out/'protected_before.json',{'files':frozen,'db_counts':counts,'shared_database':str(db)})
 manifest=p.snapshot(master)
 p.immutable(out/'action_input_manifest.json',manifest)
 # Archived program code is reference evidence; the unique discoverable Skill stays single.
 shutil.copy2(ROOT/'skills/action-selection/SKILL.md',out/'skill_before_v2.txt')
 p.immutable(out/'environment.json',{'python':sys.executable,'available':{m:bool(importlib.util.find_spec(m)) for m in ['numpy','scipy','sklearn','torch','sentence_transformers','psutil']},'model_choice':'Local TF-IDF word/character candidate retrieval plus Action-only latent semantic SVD and typed relation reranking. No downloaded pretrained model or external inference service. Never call latent similarity proof of matching purpose.','cost_assessment':'Sparse local matrices, 128 latent dimensions; benchmark wall time/RSS during index build and batch screening; no per-row LLM loop.'})
 print(json.dumps({'snapshot':manifest['snapshot_id'],'distinct_action_skus':manifest['unique_skus'],'previous_learned_skus':counts['sample_members'],'master_unchanged':p.filehash(master)==frozen[str(master)],'output':str(out)},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
