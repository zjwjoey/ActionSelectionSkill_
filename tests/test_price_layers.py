"""Price arithmetic must not promote identity or invent missing sale quantities."""
import copy
import unittest
from runtime.matching_v2.price_layers import quantity, layers, price_history, valid_quote


def quote(side, title='Pintura 750 ml', value=9):
    return dict(title=title, spec='', price=dict(value=value, currency='EUR', raw=str(value)),
                source_file=side, source_sha256='hash', source_date='2026-10-26',
                asin='B000000001', sku='1234567', url='https://www.amazon.es/dp/B000000001' if side=='a' else 'https://www.action.com/es-es/p/1234567/paint/',
                title_binding_exact=True)


class LayerTests(unittest.TestCase):
    def test_same_name_different_capacity_converts_without_promoting_identity(self):
        a=quote('a');b=quote('b','Pintura 3 litros',12)
        pair=dict(relation='SAME_TYPE',spec_status='DIFFERENT')
        before=copy.deepcopy((a,b,pair));r=layers(a,b,pair,{'a':'hash','b':'hash'})
        self.assertTrue(r['L3']['eligible']);self.assertEqual(r['L3']['amazon_per_base'],12)
        self.assertEqual(r['L3']['action_per_base'],4)
        self.assertEqual(r['identity_relation_unchanged'],'SAME_TYPE');self.assertEqual((a,b,pair),before)
        self.assertIsNone(r['L3']['amazon_quantity']['explicit_pack_count'])

    def test_explicit_multipack_each_total_and_ambiguous_pack(self):
        self.assertEqual(quantity('Jabon 2 x 500 ml')['amount'],1)
        self.assertEqual(quantity('Jabon pack de 2, 500 ml cada')['amount'],1)
        self.assertEqual(quantity('Jabon pack de 2, total 500 ml')['amount'],.5)
        self.assertIsNone(quantity('Jabon pack de 2, 500 ml')['amount'])
        self.assertEqual(quantity('Cafe 5x30 capsulas')['amount'],150)
        self.assertEqual(quantity('Harina 500 gramos')['amount'],.5)
        self.assertEqual(quantity('Harina 1,5 kg')['amount'],1.5)
        self.assertIsNone(quantity('Jabon 0x500 ml')['amount'])
        self.assertIsNone(quantity('Cafe 0x30 capsulas')['amount'])

    def test_durable_capacity_dimensions_and_feature_counts_are_not_sale_quantity(self):
        for title,spec in [('Botella 1 litro',''),('Caja','20 x 30 x 10 cm'),('Mando 6 funciones 50 colores 4 puertos',''),('Pintura','Peso del paquete: 2 kg'),('Kit limpieza 8 piezas','')]:
            self.assertIsNone(quantity(title,spec)['amount'],title)
        self.assertEqual(quantity('Pilas 24 unidades')['amount'],24)
        self.assertIsNone(quantity('Pilas')['amount'])

    def test_unknown_currency_hash_and_binding_are_fail_closed(self):
        a=quote('a');b=quote('b');p=dict(relation='SAME_TYPE',spec_status='UNKNOWN')
        a['price']['currency']=None
        self.assertFalse(layers(a,b,p,{'a':'hash','b':'hash'})['L2']['eligible'])
        a=quote('a');a.pop('source_sha256')
        self.assertFalse(valid_quote(a,{},'Amazon')['valid'])
        b['title_binding_exact']=False
        self.assertFalse(valid_quote(b,{'b':'hash'},'Action')['valid'])
        b['title_binding_exact']=True;b['sku']='7654321'
        self.assertFalse(valid_quote(b,{'b':'hash'},'Action')['valid'])

    def test_old_dates_allow_historical_research_not_current_quote_claim(self):
        a=quote('a');b=quote('b');b['source_date']='2026-08-01'
        r=layers(a,b,dict(relation='SAME_TYPE',spec_status='UNKNOWN'),{'a':'hash','b':'hash'})
        self.assertTrue(r['L2']['eligible']);self.assertEqual(r['L2']['date_bucket'],'OVER_30_DAYS')

    def test_partial_candidates_and_near_price_do_not_change_identity(self):
        a=quote('a');good=quote('b');bad=quote('b');bad['price']['currency']=None
        p=dict(relation='SAME_TYPE',spec_status='UNKNOWN')
        rs=[layers(a,b,p,{'a':'hash','b':'hash'}) for b in [good,bad,bad,bad,bad]]
        self.assertEqual(sum(r['L2']['eligible'] for r in rs),1)
        p['relation']='UNRELATED'
        r=layers(quote('a','Rejilla para frigorifico'),quote('b','Frigorifico'),p,{'a':'hash','b':'hash'})
        self.assertFalse(r['L2']['eligible']);self.assertEqual(r['identity_relation_unchanged'],'UNRELATED')
        r=layers(quote('a','Jabon 500ml'),quote('b','Jabon 500 gramos'),dict(relation='SAME_TYPE',spec_status='UNKNOWN'),{'a':'hash','b':'hash'})
        self.assertFalse(r['L3']['eligible'])

    def test_currency_evidence_change_is_not_numeric_price_change(self):
        a=quote('a');a['price']['currency']=None;b=quote('a')
        summary,rs=price_history([dict(asin=a['asin'],observations=[a,b])])
        self.assertFalse(rs[0]['numeric_changed'])
        self.assertEqual(rs[0]['classification'],'CURRENCY_EVIDENCE_ONLY_CHANGED')
        self.assertTrue(rs[0]['economic_change_unresolved'])
