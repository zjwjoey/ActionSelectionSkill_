import unittest,tempfile
from pathlib import Path
from runtime.retail.attributes import extract,verify,package
from runtime.retail.learning import Learning
from runtime.v3.catalog import Catalog
class Repairs(unittest.TestCase):
 def test_attribute_evidence(self):
  c=verify(extract('Estante 2 niveles','40X50cm'),extract('Estante 3 niveles','400x500mm'))
  self.assertIn('levels',c['conflicts']);self.assertFalse(c['block_same_type']);self.assertTrue(any(x['status']=='EQUAL' for x in c['comparisons']))
 def test_package(self):
  self.assertEqual(package('10 tarros de vidrio'),'HOMOGENEOUS_MULTIPACK');self.assertEqual(extract('10 tarros de vidrio')['attributes']['count'],['10']);self.assertEqual(package('6 cuchillos con caja'),'MAIN_WITH_ACCESSORY')
 def test_targeted_scores_match_full(self):
  c=Catalog(Path(__file__).resolve().parents[1]);r=c.retrieve('Pilas AAA',50);v=c.score_skus('Pilas AAA',[x['sku'] for x in r]);self.assertTrue(all(x['retrieval_score']==v[x['sku']] for x in r))
