"""Retain pre-gate prototype artifacts before a new candidate build."""
import json
from pathlib import Path
from assortment import RUN,p
archive=RUN/'prototype_1_before_technical_gate'
archive.mkdir(exist_ok=False)
names=['retrieval_index.joblib','action_features.jsonl','frozen_policy.json','method_manifest.json','action_corpus_summary.json','assortment_task_graph.json','run_identity.json','amazon_source_manifest.json','amazon_inputs.jsonl','amazon_raw_row_mapping.jsonl','technical500_inputs.jsonl','technical500_membership.jsonl','human_review200_membership.jsonl','technical500_results.jsonl']
for name in names:
 path=RUN/name
 if path.exists():path.rename(archive/name)
for path in RUN.glob('technical500_runtime_*.json'):path.rename(archive/path.name)
p.immutable(archive/'technical_gate_failure.json',{'stage':'First500 technical development run','gate':'BLOCK_FULL_EXPANSION','observed_systemic_defects':['Food task regex overmatched textil/tela/temporizador prefixes','First known noun late in purpose clause was misread as the main object','Same broad head and weak task were incorrectly labeled same specific type'],'examples':['Coffee tamper vs coffee beans','Heat press vs cookie press','Voltage protector vs screen protector'],'human_gold':0,'accuracy_comparison':None,'corrective_scope':'Generic parsing and relation contract; preserve original500 as development evidence. New validation/review memberships exclude these500.'})
print(archive)
