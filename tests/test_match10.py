"""Provisional score behavior, source-bound caches and safe review import."""
import copy,json,tempfile,unittest
from pathlib import Path
from runtime.retail.match10 import scored,rank_matches,validate,schema
from runtime.retail.match10_feedback import import_feedback
from runtime.v3.core import digest
from runtime.v31.state import State

def candidate(sku,n,rel='SAME_TYPE',spec='UNKNOWN',rank=1,scope='WHOLE'):
 p=dict(relation=rel,spec_status=spec,category_status='UNKNOWN',scope=scope)
 return dict(reference_id=sku,relation=rel,scope=scope,scoring=scored(n,p,rank))
class Match10Tests(unittest.TestCase):
 def test_new_file_analysis_cache_resume_and_changed_source_rejection(self):
  from runtime.retail.match10 import run
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);p=d/'input.jsonl';ref=d/'ref.jsonl';out=d/'run'
   p.write_text('{"title":"Caja", "sku":"0001"}\n',encoding='utf8');ref.write_text('{"title":"Caja", "sku":"0002"}\n',encoding='utf8')
   run(p,out,reference=str(ref),do_export=False)
   req=json.loads((out/'requests.jsonl').read_text(encoding='utf8'))
   pair=dict(sku='0002',action_span='Caja',relation='SAME_TYPE',spec_status='UNKNOWN',category_status='UNKNOWN',amazon_pack=None,action_pack=None,amazon_pack_span='',action_pack_span='',reason='synthetic fixture',unknowns=[],scope='WHOLE')
   a=dict(record_id=req['record_id'],source_hash=req['source_hash'],subject_span='Caja',sold_subject='合成箱体',subject_status='clear',form='whole',no_confirmed_match=False,pairs=[pair],unknowns=[])
   answer=d/'answer.jsonl';answer.write_text(json.dumps(a)+'\n',encoding='utf8')
   run(p,out,reference=str(ref),mode='file',analysis=answer,do_export=False)
   result=json.loads((out/'results.jsonl').read_text(encoding='utf8'));self.assertEqual(result['issues'],[])
   again=run(p,out,reference=str(ref),mode='file',analysis=answer,do_export=False)
   self.assertEqual(again['cached_records'],1);self.assertEqual(again['calls_this_attempt'],0)
   p.write_text('{"title":"Otra caja"}\n',encoding='utf8')
   with self.assertRaisesRegex(ValueError,'INCOMPATIBLE_MATCH10_RESUME'):run(p,out,reference=str(ref),do_export=False)
 def test_sort_by_exact_score_not_ai_order_or_rounded_tie(self):
  a=candidate('a',20,rank=1);b=candidate('b',90,rank=2)
  ordered,p=rank_matches([a,b],dict(subject_status='clear',form='whole',no_confirmed_match=False))
  self.assertEqual(p['reference_id'],'b');self.assertEqual(ordered[0]['scoring']['model_rank'],2)
  self.assertEqual(ordered[0]['score_rank'],1)
 def test_unknown_is_not_zero_and_parts_cannot_be_main(self):
  analysis=dict(subject_status='clear',form='whole',no_confirmed_match=False)
  self.assertIsNone(rank_matches([candidate('a',100,'UNRELATED')],analysis)[1])
  self.assertIsNone(rank_matches([candidate('a',100,scope='COMPONENT')],analysis)[1])
  analysis['subject_status']='insufficient'
  self.assertIsNone(rank_matches([candidate('a',100)],analysis)[1])
 def test_unit_conversion_retains_missing_evidence_and_relation_cap(self):
  a=candidate('a',100);self.assertEqual(a['scoring']['evidence_coverage'],.8)
  self.assertLessEqual(a['scoring']['match_score_10'],8.9)
  b=candidate('a',100,'SHARED_NEED');self.assertLessEqual(b['scoring']['match_score_10'],3.4)
  self.assertNotEqual(a['scoring']['match_score_10'],b['scoring']['match_score_10'])
  self.assertTrue(a['scoring']['limitations'])
 def test_business_schema_and_unverified_identity_are_rejected(self):
  props=schema()['properties']['analyses']['items']['properties'];self.assertNotIn('selection',props)
  req=dict(record_id='r',source_hash='h',title='Caja',action_candidates=[])
  with self.assertRaisesRegex(ValueError,'LEGACY_BUSINESS'):validate(req,dict(selection='保留'))
  a=dict(record_id='r',source_hash='h',subject_span='Caja',subject_status='clear',form='whole',pairs=[])
  validate(req,a)
 def test_feedback_atomic_idempotent_source_bound_and_never_overwrites(self):
  import openpyxl
  with tempfile.TemporaryDirectory() as d:
   out=Path(d);r=dict(record_id='r',source=dict(source_sha256='h',source_product_id='0001',title_original='Caja'),method='m',analysis={},primary=None,match_score_10=None)
   original=json.dumps(r);(out/'results.jsonl').write_text(original+'\n',encoding='utf8')
   w=openpyxl.Workbook();s=w.active;s.title='商品匹配结果';headers=['记录ID','结果hash','方法版本','来源hash','人工反馈类型','新参考SKU','人工意见','人工关系','建议分数','原始商品ID','原始商品名称','参考SKU','商品匹配分（10分制）']
   s.append([]);s.append([]);s.append([]);s.append([]);s.append(headers)
   s.append(['r',digest(r),'m','h','无匹配但存在正确参考','00123','明确找到对应类型','SAME_TYPE',None,'0001','Caja',None,None]);p=out/'review.xlsx';w.save(p)
   self.assertEqual(import_feedback(out,p,'fixture-reviewer')['inserted'],1)
   self.assertEqual(import_feedback(out,p,'fixture-reviewer')['inserted'],0)
   self.assertEqual((out/'results.jsonl').read_text(encoding='utf8'),original+'\n')
   s.cell(6,2,'stale');w.save(p)
   with self.assertRaisesRegex(ValueError,'STALE_OR_UNBOUND'):import_feedback(out,p,'fixture-reviewer')
   state=State(out/'state.sqlite3');self.assertEqual(len(state.all('match10_feedback')),1);state.close();w.close()
