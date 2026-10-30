import copy,json,tempfile,unittest
from pathlib import Path
from runtime.retail.pair_learning import (FEATURES,BASE_FEATURES,RELATIONS,AUTHORITIES,LabelStore,digest,
 relevance,grouped_split,train,load_model,utility,rerank,evaluate,active_queue,validate_label,save)
from runtime.retail.pair_feedback import validate_dataset,materialize,ModelRegistry

def fixture():
 rows=[]
 for i in range(12):
  for j in range(3):
   f={k:0. for k in FEATURES};f.update(text_similarity=1.-j*.4,e5_similarity=.9-j*.2)
   p=dict(pair_id=f'{i}-{j}',input_id=str(i),input=dict(source_platform='test',source_product_id=f'p{i}',title_original=f'Product {i}'),reference=dict(sku=str(j),title=f'Ref {j}'),features=f,feature_binding={'test':'fixture'},split='train' if i<8 else 'dev',isolation_group=str(i),group_key=str(i),relation=['SAME_TYPE','UNRELATED','INSUFFICIENT_EVIDENCE'][j],scope='WHOLE',spec_relation='UNKNOWN',label_authority='AI_SILVER',baseline_score_10=8-j,source_facts=[])
   rows.append(p)
 return rows

class PairLearningTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def model(self,rows=None,variant='B',filename='model.json'):return train(rows or fixture(),self.path/filename,variant)
 def test_unknown_not_negative(self):
  r=fixture()[2];self.assertIsNone(relevance(r));r['relation']='SAME_TYPE';r['label_authority']='UNVERIFIED';self.assertIsNone(relevance(r))
 def test_components_not_full_primary_positives(self):
  r=fixture()[0];r['scope']='COMPONENT';self.assertEqual(relevance(r),0);self.assertEqual(r['relation'],'SAME_TYPE')
 def test_identity_cannot_be_ai(self):
  with self.assertRaisesRegex(ValueError,'IDENTITY'):validate_label(dict(relation='VERIFIED_IDENTICAL',scope='WHOLE',spec_relation='SAME',label_authority='AI_SILVER'))
 def test_fake_gold_rejected(self):
  with self.assertRaises(ValueError):validate_label(dict(relation='SAME_TYPE',scope='WHOLE',spec_relation='UNKNOWN',label_authority='HUMAN_GOLD',evidence={}))
 def test_dataset_cannot_upgrade_ai_to_gold_without_evidence(self):
  rows=fixture();rows[0]['label_authority']='HUMAN_GOLD'
  with self.assertRaises(ValueError):validate_dataset(rows)
 def test_real_training_and_roundtrip(self):
  m=self.model();self.assertGreater(m['preference_rows'],0);self.assertEqual(m,load_model(self.path/'model.json'));self.assertGreater(utility(m,fixture()[0]),utility(m,fixture()[1]));self.assertFalse(m['formal_promotion'])
 def test_pairwise_does_not_use_scores_or_ids(self):
  a=fixture();m=self.model(a);b=copy.deepcopy(a)
  for p in b:p['baseline_score_10']=-999;p['input']['source_product_id']='changed';p['reference']['sku']='private';p['relation']='UNRELATED'
  self.assertEqual(utility(m,a[0]),utility(m,b[0]));self.assertNotIn('baseline_score_10',m['features']);self.assertNotIn('relation',m['features'])
 def test_unknown_rows_do_not_train(self):
  rows=fixture();m=self.model(rows);self.assertEqual(m['training_pairs'],16);self.assertEqual(len(m['training_ids']),8)
 def test_opt_in_and_binding(self):
  m=self.model()
  with self.assertRaises(ValueError):rerank(m,fixture())
  p=fixture()[0];p['feature_binding']={'other':1}
  with self.assertRaises(ValueError):utility(m,p)
 def test_model_tamper_rejected(self):
  self.model();p=self.path/'model.json';r=json.loads(p.read_text());r['coef'][0]+=1;save(p,r)
  with self.assertRaises(ValueError):load_model(p)
 def test_model_immutable(self):
  self.model()
  with self.assertRaisesRegex(ValueError,'IMMUTABLE'):self.model()
 def test_group_split_and_leak_detector(self):
  rows=fixture()
  for p in rows:p['group_key']='one-family' if int(p['input_id'])<4 else p['group_key']
  grouped_split(rows,{},77);validate_dataset(rows);self.assertEqual(len({p['split'] for p in rows if int(p['input_id'])<4}),1)
  rows[0]['split']='another'
  with self.assertRaises(ValueError):validate_dataset(rows)
 def test_group_allocation_does_not_depend_on_input_order(self):
  rows=fixture()
  for p in rows:p['group_key']='shared' if int(p['input_id'])<4 else p['group_key']
  a=copy.deepcopy(rows);b=list(reversed(copy.deepcopy(rows)))
  grouped_split(a,{},77);grouped_split(b,{},77)
  self.assertEqual({p['pair_id']:(p['split'],p['isolation_group']) for p in a},{p['pair_id']:(p['split'],p['isolation_group']) for p in b})
 def test_group_allocation_stable_across_python_hash_seeds(self):
  import subprocess,sys,os
  program="from test_pair_learning import fixture; from runtime.retail.pair_learning import grouped_split; import json; r=fixture(); [p.update(group_key='shared') for p in r if int(p['input_id'])<4]; grouped_split(r,{},77); print(json.dumps([(p['pair_id'],p['split'],p['isolation_group']) for p in r]))"
  env={**os.environ,'PYTHONPATH':os.pathsep.join([str(Path(__file__).resolve().parents[1]),str(Path(__file__).parent)])}
  a=subprocess.check_output([sys.executable,'-c',program],env={**env,'PYTHONHASHSEED':'1'},text=True)
  b=subprocess.check_output([sys.executable,'-c',program],env={**env,'PYTHONHASHSEED':'2'},text=True)
  self.assertEqual(a,b)
 def test_metrics_weak_not_accuracy(self):
  m=self.model();e=evaluate(fixture(),{'B':m});self.assertIsNone(e['human_gold_metrics']);self.assertIsNone(e['full_catalog_recall']);self.assertIn('AGREEMENT',e['label_basis'])
 def test_active_has_random_and_no_human(self):
  m=self.model();q=active_queue(fixture(),{'B':m},10);self.assertEqual(len(q),10);self.assertEqual(sum(r['sample_arm']=='random_remaining' for r in q),2);self.assertTrue(all(r['human_reviewer'] is None for r in q))
 def test_append_feedback_binding_idempotence_conflict(self):
  p=fixture()[0];store=LabelStore(self.path/'labels.sqlite3');row=dict(pair_id=p['pair_id'],pair_source_hash=digest(p),relation='UNRELATED',scope='WHOLE',spec_relation='UNKNOWN',label_authority='AI_SILVER')
  try:
   h=store.import_label(row,{p['pair_id']:p});self.assertEqual(store.import_label(row,{p['pair_id']:p}),'NO_OP')
   with self.assertRaises(ValueError):store.import_label({**row,'relation':'SAME_TYPE'},{p['pair_id']:p})
   self.assertNotEqual(h,store.import_label({**row,'relation':'SAME_TYPE','supersedes':h},{p['pair_id']:p}))
  finally:store.close()
 def test_feedback_materialization_version_and_retrain(self):
  from runtime.v3.workflow import write_jsonl
  rows=fixture();write_jsonl(self.path/'base.jsonl',rows);p=rows[0];store=LabelStore(self.path/'labels.sqlite3')
  store.import_label(dict(pair_id=p['pair_id'],pair_source_hash=digest(p),relation='UNRELATED',scope='WHOLE',spec_relation='UNKNOWN',label_authority='AI_SILVER'),{p['pair_id']:p});store.close()
  receipt=materialize(self.path/'base.jsonl',self.path/'labels.sqlite3',self.path/'v2.jsonl');self.assertNotEqual(receipt['base_sha'],receipt['new_sha']);self.assertEqual(json.loads((self.path/'base.jsonl').read_text().splitlines()[0])['relation'],'SAME_TYPE')
  from runtime.retail.pair_learning import read
  changed=read(self.path/'v2.jsonl');self.assertEqual(changed[0]['relation'],'UNRELATED');self.model(changed)
 def test_registry_switch_rollback_not_promotion(self):
  a=self.model(filename='a.json');b=self.model(variant='C',filename='b.json');r=ModelRegistry(self.path/'registry.sqlite3')
  try:
   r.register(self.path/'a.json');r.register(self.path/'b.json');r.select(a['model_hash'],'initial experiment',True);r.select(b['model_hash'],'compare',True);r.select(a['model_hash'],'rollback',True);self.assertEqual(r.current(),a['model_hash'])
   with self.assertRaises(ValueError):r.select(b['model_hash'],'no optin')
  finally:r.close()
