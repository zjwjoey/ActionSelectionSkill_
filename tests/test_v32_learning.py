"""Synthetic regression evidence, never human merchandise labels."""
import json,tempfile,unittest,copy
from pathlib import Path
from runtime.retail.hybrid import rrf,HybridRetriever
from runtime.retail.attributes import extract,verify
from runtime.retail.learning import Learning,aliases_for,load_release
from runtime.v3.core import digest
from runtime.v3.workflow import filehash
class V32Tests(unittest.TestCase):
 def test_rrf_stable_no_duplicate_or_score_conversion(self):
  a=rrf({'text':['a','b'],'dense':['b','a']});self.assertEqual([x['sku'] for x in a],['a','b']);self.assertLess(a[0]['rrf_score'],1)
  self.assertEqual(a,rrf({'text':['a','b'],'dense':['b','a']}))
  with self.assertRaises(ValueError):rrf({'a':['x','x']})
 def test_literal_pack_can_be_bound_to_original_variant(self):
  from runtime.retail.match10 import validate
  req=dict(record_id='r',source_hash='h',title='Arena para gatos',spec='',variant='4 Paquetes',action_candidates=[dict(sku='s',title='Arena',spec='')])
  p=dict(sku='s',relation='SAME_TYPE',spec_status='UNKNOWN',category_status='UNKNOWN',scope='WHOLE',action_span='Arena',amazon_pack=4,amazon_pack_span='4 Paquetes',action_pack=None,action_pack_span='')
  a=dict(record_id='r',source_hash='h',subject_span='Arena',subject_status='clear',form='consumable',pairs=[p])
  validate(req,a);req['variant']=''
  with self.assertRaisesRegex(ValueError,'PACK_EVIDENCE_MISSING'):validate(req,a)
 def test_shelf_levels_and_dimensions_preserved(self):
  c=verify(extract('Estantería 2 niveles','100 x 40 cm'),extract('Estantería 3 niveles','1000 x 400 mm'))
  self.assertIn('levels',c['conflicts']);self.assertNotIn('dimensions',c['conflicts']);self.assertFalse(c['block_same_type'])
 def test_battery_identity_and_missing_chemistry(self):
  a=extract('Pilas Maxell CR2032 3V 5 unidades');b=extract('Pilas Varta CR2025 3V 5 unidades');c=verify(a,b)
  self.assertIn('model',c['conflicts']);self.assertIn('chemistry',c['unknown'])
 def test_sold_box_not_host_knife(self):
  self.assertEqual(extract('Caja para cuchillos de carne')['family'],'box')
  self.assertTrue(verify(extract('Juego de cuchillos 6 piezas'),extract('Caja de madera'))['block_same_type'])
 def test_vacuum_accessory_unknown_not_whole(self):
  a=extract('Filtro para aspirador');b=extract('Aspirador')
  self.assertEqual(a['role'],'accessory');self.assertIn('WHOLE_ACCESSORY_SCOPE_UNCONFIRMED',verify(a,b)['unknown'])
 def test_different_brand_same_type_and_squeegee(self):
  c=verify(extract('Pilas Maxell AAA 1.5V'),extract('Pilas Philips AAA 1.5V'))
  self.assertFalse(c['block_same_type']);self.assertFalse(c['conflicts'])
  self.assertEqual(extract('Raclette vitre')['family'],'squeegee')
  self.assertEqual(verify(extract('Raclette vitre'),extract('Limpiacristales'))['evidence_status'],'关键属性未知')
 def test_conflicting_source_is_not_normalized_away(self):
  a=extract('Botella 300 ml','Capacidad 320 ml');self.assertIn('capacity',a['source_conflicts'])
 def test_learning_idempotency_and_human_gates(self):
  with tempfile.TemporaryDirectory() as d:
   s=Learning(Path(d)/'learning.db');src=dict(record_id='synthetic-r',source_sha='synthetic-sha');body=dict(term='fixtureword',expansion='Caja')
   cid=s.propose('alias',body,src,synthetic=True);self.assertEqual(cid,s.propose('alias',body,src,synthetic=True));self.assertEqual(len(s.events()),2)
   with self.assertRaises(ValueError):s.transition(cid,'HUMAN_VERIFIED','AI',dict(reason='self evaluation'))
   with self.assertRaises(ValueError):s.transition(cid,'APPROVED_FOR_LEARNING','human:fixture',dict(reason='fixture'))
   s.transition(cid,'HUMAN_VERIFIED','human:fixture',dict(reason='synthetic unit test only'));s.transition(cid,'APPROVED_FOR_LEARNING','human:fixture',dict(reason='synthetic unit test only',authorization='test'))
   proof=Path(d)/'proof';proof.write_text('synthetic only')
   receipt=dict(candidate_ids=[cid],reviewer='human:fixture',regression_pass=True,independent_pass=True,evidence_file=str(proof),evidence_sha=filehash(proof),training_ids=['a'],validation_ids=['b'])
   with self.assertRaisesRegex(ValueError,'SYNTHETIC'):s.publish([cid],receipt,Path(d)/'release.json')
   s.close()
 def test_general_alias_applies_other_sku_but_not_substring(self):
  items=[dict(kind='alias',body=dict(term='fixtureword',expansion='Caja'))]
  self.assertEqual(aliases_for(items,'fixtureword nuevo modelo'),['Caja']);self.assertEqual(aliases_for(items,'prefixtureword'),[])
 def test_unapproved_or_tampered_release_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'release.json';r=dict(status='CANDIDATE',items=[]);r['version']=digest(r);p.write_text(json.dumps(r))
   with self.assertRaises(ValueError):load_release(p)
 def test_index_unavailable_retains_v31_candidates(self):
  from unittest.mock import patch
  class Refs:catalog=None;quotes={}
  refs=Refs()
  with tempfile.TemporaryDirectory() as d,patch('runtime.retail.match10.retrieve',return_value=[dict(sku='0001',title='Caja',retrieval_score=.5)]):
   x=HybridRetriever(refs,Path(d)/'absent');rows,t=x.search(dict(title_original='Caja'))
   self.assertEqual(rows[0]['sku'],'0001');self.assertTrue(t['fallback']);self.assertEqual(t['original_v31'],['0001'])
 def test_content_cache_renewed_binding_keeps_original_provenance(self):
  from runtime.retail.learning_pipeline import Extension
  from runtime.retail.match10 import validate
  e=Extension();row=dict(source_platform='supplier',source_product_id='0001',brand='fixture')
  req=dict(record_id='old',source_hash='old-h',title='Caja',spec='',variant='',method_signature='frozen-test',action_candidates=[dict(sku='s',title='Caja',spec='')])
  p=dict(sku='s',action_span='Caja',relation='SAME_TYPE',spec_status='UNKNOWN',category_status='UNKNOWN',scope='WHOLE',amazon_pack=None,action_pack=None,amazon_pack_span='',action_pack_span='')
  a=dict(record_id='old',source_hash='old-h',subject_span='Caja',subject_status='clear',form='whole',pairs=[p])
  e.analysis_cache[e.content_key(row,req)]=dict(analysis=a,source={'observation':'old'})
  fresh={**req,'record_id':'new','source_hash':'new-h'};current={**row,'quote_id':'new'};new=e.reuse(current,fresh)
  self.assertEqual(new['source_hash'],'new-h');self.assertEqual(a['source_hash'],'old-h');validate(fresh,new)
  self.assertIn('new',e.rebound);self.assertIsNone(e.reuse(current,{**fresh,'title':'Otra caja'}))
 def test_bad_sibling_does_not_discard_validated_rows(self):
  from unittest.mock import patch
  from runtime.retail.match10 import run
  def adapter(model,requests,role):
   if model.mode!='queue':raise ValueError('RETRY_ONLY_UNCACHED_ROWS')
   q=requests[0];p=dict(sku='ref',action_span='Caja',relation='SAME_TYPE',spec_status='UNKNOWN',category_status='UNKNOWN',scope='WHOLE',amazon_pack=None,action_pack=None,amazon_pack_span='',action_pack_span='',reason='synthetic fixture',unknowns=[])
   return [dict(record_id=q['record_id'],source_hash=q['source_hash'],subject_span='Caja',subject_status='clear',form='whole',sold_subject='合成测试箱',unknowns=[],no_confirmed_match=False,pairs=[p])]
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);inp=d/'in.jsonl';ref=d/'ref.jsonl';notes=d/'notes.jsonl'
   inp.write_text('{"sku":"a","title":"Caja a"}\n{"sku":"b","title":"Caja b"}\n');ref.write_text('{"sku":"ref","title":"Caja"}\n');notes.write_text('')
   with patch('runtime.v31.model.Model.run',adapter):s=run(inp,d/'run',reference=str(ref),mode='file',analysis=notes,do_export=False)
   self.assertEqual((s['completed'],s['pending']),(1,1));self.assertEqual(len(s['errors']),1)
 def test_known_semantic_type_outside_small_attribute_vocabulary(self):
  from runtime.retail.learning import classify_unknown
  r=dict(analysis=dict(subject_status='clear',form='whole'),source=dict(brand=''),primary=dict(relation='SAME_TYPE',scope='WHOLE'))
  flags=classify_unknown(r,extract('Juguete'),False)
  self.assertIn('A_NEW_SKU_KNOWN_TYPE',flags);self.assertNotIn('C_TYPE_HYPOTHESIS',flags)
