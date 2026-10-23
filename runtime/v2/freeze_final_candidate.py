"""Preserve the second technical run; retain memberships as development checks.

Independent human evaluation is sampled afterwards from outside both pilots.
"""
from pathlib import Path
from assortment import RUN,p,read
archive=RUN/'prototype_2_validation_before_model_dependency_fix';archive.mkdir(exist_ok=False)
names=['retrieval_index.joblib','action_features.jsonl','frozen_policy.json','method_manifest.json','action_corpus_summary.json','assortment_task_graph.json','run_identity.json','scheme_A500.jsonl','scheme_B500.jsonl','technical500_results.jsonl','three_scheme500_comparison.jsonl','blind_review200.jsonl','three_scheme_summary.json']
for name in names:
 f=RUN/name
 if f.exists():f.rename(archive/name)
for f in RUN.glob('technical500_runtime_*.json'):f.rename(archive/f.name)
if (RUN/'private/arm_mapping.json').exists():(RUN/'private/arm_mapping.json').rename(archive/'old_arm_mapping.json')
p.immutable(archive/'followup_fix.json',{'affected_type':'Named-model installation kits','example_observation':'An LED installation kit explicitly for named WIND models was retained HIGH. It must remain research as a dedicated component.','correction':'Generic named-model dependency contract, not SKU override','no_accuracy_claim':True,'preserved_membership':'Current500 is now technical development evidence. New independent human200 will exclude both prior technical500 cohorts.'})
print(archive)
