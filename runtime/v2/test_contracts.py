"""Targeted V2 contracts, synthetic fixtures; no Amazon evaluation labels."""
import json,unittest
from assortment import Features,Matcher,WORK

class Contracts(unittest.TestCase):
 def setUp(self):
  self.f=Features(json.loads((WORK/'policy.json').read_text(encoding='utf8')))
  self.f.head_vocabulary={'organizador','caja','cepillo','champu','mesa','funda','filtro','boligrafo','reactor'}
 def test_source_corruption(self):self.assertTrue(self.f.extract('这是中文品名')['source_invalid'])
 def test_named_vehicle_over_hair(self):
  f=self.f.extract('Champú para coches',True);self.assertIn('vehicle_cleaning',f['task_frames']);self.assertNotIn('hair_care',f['task_frames'])
 def test_specific_dependency(self):self.assertEqual(self.f.extract('Recambio filtro compatible con aspirador X',True)['retail_form'],'DEDICATED_COMPONENT')
 def test_named_model_lighting_part(self):self.assertEqual(self.f.extract('Kit de iluminación LED para MOTOR SERIES',True)['retail_form'],'DEDICATED_COMPONENT')
 def test_accessory_is_not_complete_furniture(self):self.assertNotEqual(self.f.extract('Funda para sofá',True)['retail_form'],'COMPLETE_FURNITURE')
 def test_complete_furniture(self):self.assertEqual(self.f.extract('Mesa auxiliar de madera',True)['retail_form'],'COMPLETE_FURNITURE')
 def test_professional_not_negative(self):self.assertFalse(self.f.extract('Cepillo de limpieza profesional',True)['explicit_outside_scope'])
 def test_purpose_noun_not_main_item(self):self.assertEqual(self.f.extract('Accesorio para cafe con filtro',True)['head'],'')
 def test_textile_not_food(self):self.assertNotIn('food_consumption',self.f.extract('Tela textil de calidad')['task_frames'])
 def test_specialized_latch_research(self):self.assertEqual(self.f.extract('Hebillas para bolsos',True)['retail_form'],'DEDICATED_COMPONENT')
 def test_same_broad_head_not_same_type(self):
  m=object.__new__(Matcher);m.f=self.f;m.policy=self.f.policy
  a=self.f.extract('Cepillo para cocina',True);b={'feature':self.f.extract('Cepillo para pelo')}
  self.assertNotEqual(m.relation(a,b)[0],'SAME_SPECIFIC_TYPE')
 def test_specific_outside_scope(self):self.assertTrue(self.f.extract('Reactor industrial para linea de produccion',True)['explicit_outside_scope'])
 def test_same_name_purpose_conflict(self):
  m=object.__new__(Matcher);m.f=self.f;m.policy=self.f.policy
  a=self.f.extract('Champú para coches',True);b={'feature':self.f.extract('Champú para cabello')}
  self.assertEqual(m.relation(a,b)[0],'NO_CLEAR_RELATION')
 def test_distinct_task_relationship(self):
  m=object.__new__(Matcher);m.f=self.f;m.policy=self.f.policy
  a=self.f.extract('Organizador de cajones',True);b={'feature':self.f.extract('Separadores para cajones')}
  self.assertEqual(m.relation(a,b)[0],'SHARED_CONSUMER_NEED')
 def test_unmatched_not_excluded(self):
  m=object.__new__(Matcher);m.f=self.f;m.policy=self.f.policy;m.model={'references':[]};m.method={}
  r={'record_id':'fixture','source_record_id':'fixture','source_row':2,'input_hash':'fixture','title_original':'Marca X producto ambiguo','category_l1_original':'','category_auxiliary':'Hogar','url_original':''}
  self.assertEqual(m.judge(r,[])['decision'],'NEEDS_REVIEW')

if __name__=='__main__':unittest.main()
