import unittest
from runtime.retail.knowledge_trial import quantity_evidence,package_evidence,aliases

class KnowledgeTrialTests(unittest.TestCase):
 def test_explicit_abbreviation(self):
  self.assertEqual(quantity_evidence('Crema corporal 750 ml, 2uds')['count'],2)
 def test_inner_units_are_not_total(self):
  self.assertEqual(quantity_evidence('Toallitas (18 Packs x 48 uds)')['count'],None)
  self.assertEqual(quantity_evidence('864 Toallitas (18 Packs x 48 uds)')['count'],864)
 def test_mixed_piece_count_never_becomes_knife_count(self):
  t='Juego de cuchillos y soporte, 14 piezas'
  self.assertTrue(package_evidence(t)['mixed']);self.assertIsNone(quantity_evidence(t)['count'])
 def test_pencils_with_brush_are_heterogeneous(self):
  self.assertTrue(package_evidence('Juego de lápices de 6 piezas con pincel')['mixed'])
 def test_pack_volume_is_not_count(self):
  self.assertIsNone(quantity_evidence('Recambio pack de 250 ml')['count'])
 def test_bathroom_alias_does_not_expand_mouse_mat_or_car(self):
  self.assertEqual(aliases('Alfombra de baño'),['alfombrilla de bano'])
  self.assertEqual(aliases('Alfombrilla de ratón'),[])
  self.assertEqual(aliases('Alfombra de coche'),[])
 def test_scissor_host_does_not_get_cutting_tool_alias(self):
  self.assertEqual(aliases('Tijera escolar'),['tijeras escolar'])
  self.assertEqual(aliases('Gato de tijera para coche'),[])
