import unittest,tempfile,json,hashlib,zipfile
from pathlib import Path
from runtime.g_handoff import normalize,envelope,restore,save
from runtime.v3.workflow import filehash
class GHandoffTests(unittest.TestCase):
 def test_trim_equivalent_ids_are_not_two_products(self):
  r=dict(product_id='001',original_name='Tijeras',source_version='snapshot1');valid,bad=normalize([r,{**r,'product_id':' 001 '}]);self.assertEqual(len(valid),1);self.assertEqual(len(bad),1)
 def test_all_invalid_batch_is_preserved_without_provider(self):
  from runtime.g_handoff import run,load
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);save(p/'assets/asset_receipt.json',dict(manifest_sha='synthetic-only'));(p/'input.jsonl').write_text('{"product_id":"broken"}\n',encoding='utf8')
   result=run(p/'input.jsonl',p/'assets',p/'out');self.assertEqual(result['invalid'],1);self.assertEqual(result['provider_calls_this_attempt'],0);self.assertEqual(load(p/'out/summary.json')['total'],1);self.assertTrue((p/'out/results.csv').is_file())
 def test_json_tuple_and_unordered_diagnostics_only(self):
  from runtime.g_handoff import diagnostics
  a={'comparisons':[{'attribute':'b','value':(1,2)},{'attribute':'a','value':3}]};b={'comparisons':[{'attribute':'a','value':3},{'attribute':'b','value':[1,2]}]}
  self.assertEqual(diagnostics(a),diagnostics(b));self.assertNotEqual(diagnostics({'matches':[1,2]}),diagnostics({'matches':[2,1]}))
 def test_input_identity_version_and_duplicates_fail_closed(self):
  r=dict(product_id='001',original_name='Tijeras',category_l1='Papelería',source_version='snapshot1')
  valid,bad=normalize([r,r,{**r,'product_id':'002','source_version':''}]);self.assertEqual(len(valid),1);self.assertEqual(len(bad),2);self.assertEqual(valid[0],r)
 def test_matching_does_not_invent_business_or_demand(self):
  src=dict(product_id='p',original_name='Tijeras',source_version='s');n=dict(analysis=dict(sold_subject='剪刀',form='whole',unknowns=['尺寸未知']),primary=None,matches=[],match_score_10=None)
  e=envelope(src,n,'native_v321');self.assertIsNone(e['selection']);self.assertIsNone(e['functions']);self.assertIsNone(e['matching']['original_score_10']);self.assertFalse(e['human_gold'])
 def test_original_three_state_and_functions_preserved(self):
  src=dict(product_id='p',original_name='Tijeras',source_version='s');n=dict(semantic=dict(subject_type='剪刀',form='ordinary_good',functions=['剪切'],needs=['纸张裁切']),decision='观察')
  e=envelope(src,n,'business_v3');self.assertEqual(e['selection'],'观察');self.assertEqual(e['functions'],['剪切']);self.assertEqual(e['uses'],['纸张裁切'])
 def test_verified_asset_restore_is_idempotent_and_rejects_mutation(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);p=d/'part.zip'
   with zipfile.ZipFile(p,'w') as z:z.writestr('data/a.txt','original')
   manifest=dict(version='fixture',archives=[dict(file='part.zip',sha256=filehash(p),files={'data/a.txt':dict(bytes=8,sha256=hashlib.sha256(b'original').hexdigest())})]);save(d/'bundle_manifest.json',manifest);h=filehash(d/'bundle_manifest.json')
   restore(d,d/'out',h);restore(d,d/'out',h);self.assertEqual((d/'out/data/a.txt').read_text(),'original');(d/'out/data/a.txt').write_text('changed')
   with self.assertRaises(ValueError):restore(d,d/'out',h)
 def test_path_escape_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);p=d/'part.zip'
   with zipfile.ZipFile(p,'w') as z:z.writestr('../escape','x')
   save(d/'bundle_manifest.json',dict(version='bad',archives=[dict(file='part.zip',sha256=filehash(p),files={'../escape':dict(bytes=1,sha256=hashlib.sha256(b'x').hexdigest())})]))
   with self.assertRaises(ValueError):restore(d,d/'out',filehash(d/'bundle_manifest.json'))
