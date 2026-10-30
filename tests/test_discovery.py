import unittest,tempfile
from pathlib import Path
from runtime.retail.discovery import discover,head,shadow_parse
class DiscoveryTests(unittest.TestCase):
 def row(self,rid,text):
  return dict(record_id=rid,status='COMPLETE',source=dict(source_platform='supplier',source_product_id=rid,source_sha256='fixture',source_file='fixture',title_original=text,specifications='',variant='',brand=''),analysis=dict(subject_span=text,subject_status='clear',form='consumable',pairs=[]),matches=[],attribute_checks={})
 def test_same_expression_aggregates_sources(self):
  r=discover([self.row('a','Pilas 4 uds'),self.row('b','Pilas 8 uds')]);self.assertEqual(len(r),1);self.assertEqual(len(r[0]['evidence']),2);self.assertEqual(r[0]['state'],'CANDIDATE')
 def test_brand_or_no_match_is_not_knowledge(self):
  self.assertEqual(discover([self.row('a','Objeto marca nueva')]),[])
 def test_different_families_do_not_merge(self):
  self.assertEqual(len(discover([self.row('a','Pilas 4 uds'),self.row('b','Cajas 4 uds')])),2)
 def test_brand_and_adjective_are_not_commodity_aliases(self):
  self.assertEqual(head('Series Brand crema reparadora',vocabulary={'crema'}),'crema')
  self.assertEqual(head('Original Formula',vocabulary={'crema'}),'')
 def test_shadow_count_is_literal_type_scoped_and_not_a_fact_write(self):
  row=dict(title_original='Pilas pack de 4',specifications='')
  rule=dict(id='synthetic',kind='spec_rule',issue='UNPARSED_EXPLICIT_COUNT',scope='battery',terms='PACK_DE_N')
  self.assertEqual(shadow_parse(row,[rule])[0]['possible_count'],4)
  self.assertNotIn('count',row)
  self.assertEqual(shadow_parse(dict(title_original='Caja pack de 4',specifications=''),[rule]),[])
 def test_repeated_discovery_preserves_evidence_and_shadow_accepts_it(self):
  from runtime.retail.discovery import persist
  from runtime.retail.learning import Learning
  from runtime.retail.learning_pipeline import Extension
  groups=discover([self.row('a','Pilas 4 uds'),self.row('b','Pilas 8 uds')])
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'knowledge.sqlite3';persist(groups,path)
   store=Learning(path);before=store.events();store.close();persist(groups,path)
   store=Learning(path);self.assertEqual(store.events(),before);store.close()
   extension=Extension(learning='shadow',store=path)
   self.assertEqual(len(extension.items),1)
   self.assertEqual(extension.items[0]['state'],'CANDIDATE')
