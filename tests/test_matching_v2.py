from runtime.matching_v2.data_audit import price,history,quantity_evidence
from runtime.matching_v2.experiment import score,comparable,WEIGHTS,validate
import unittest
import tempfile
from pathlib import Path
from scripts.matching_experiment import exclusive_method

def test_no_price_or_currency_inference():
    assert price(None)['value'] is None
    assert price(0)['status']=='INVALID'
    assert price(12.5)['currency'] is None
    assert price('1,234')['value'] is None
    assert price('12,50 €')['value']==12.5
    assert price('12,50 €')['currency']=='EUR'
    assert price('1.234,50 EUR')['value']==1234.5
    assert price('nan')['value'] is None

def test_history_does_not_forward_fill_or_parent_dedup():
    rows=[dict(asin='B000000001',record_id='a',source_date='2026-10-01',price=price(5),title='a',category1='a',category2='',category3='',parent_asin='PARENT0001'),dict(asin='B000000001',record_id='b',source_date='2026-10-02',price=price(None),title='a',category1='a',category2='',category3='',parent_asin='PARENT0001'),dict(asin='B000000002',record_id='c',source_date='2026-10-02',price=price(7),title='a',category1='a',category2='',category3='',parent_asin='PARENT0001')]
    result=history(rows)
    assert len(result)==2
    assert result[0]['latest_record_ids']==['b']
    assert result[0]['observations'][-1]['price']['value'] is None

def test_quantity_is_literal_not_pack_inference():
    assert quantity_evidence('Caja')==[]
    assert quantity_evidence('Botella 1,5 litros')[0]['value']==1.5

def test_score_does_not_hide_missing_or_shared_need():
    pair=dict(relation='SHARED_NEED',spec_status='UNKNOWN',category_status='UNKNOWN')
    assert score(99,pair,'B',WEIGHTS['balanced'])['index']<=34
    pair['relation']='INSUFFICIENT'
    assert score(99,pair,'B',WEIGHTS['balanced'])['index'] is None
    pair['relation']='SAME_TYPE'
    s=score(80,pair,'B',WEIGHTS['balanced'])
    assert s['dimensions'][2:] == [None,None]
    assert s['observed_weight']<1

def test_price_requires_explicit_compatible_units_currency_dates():
    a=dict(price=price('10 EUR'),source_date='2026-10-20')
    b=dict(price=price('5 EUR'),source_date='2026-10-20',title_binding_exact=True)
    pair=dict(relation='SAME_TYPE',spec_status='SAME',amazon_pack=None,action_pack=None)
    assert not comparable(a,b,pair)['eligible']
    pair.update(amazon_pack=2,action_pack=1)
    assert comparable(a,b,pair)['ratio']==1
    b['price']=price(5)
    assert not comparable(a,b,pair)['eligible']
    b['price']=price('5 EUR');b['source_date']='2026-08-01'
    assert not comparable(a,b,pair)['eligible']
    assert not comparable(a,None,pair)['eligible']

class MatchingTests(unittest.TestCase):
    def test_same_arm_run_lock_preserves_other_arm(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            with exclusive_method(p,'A'):
                with self.assertRaises(FileExistsError):
                    with exclusive_method(p,'A'):pass
                with exclusive_method(p,'B'):pass
            self.assertFalse(list(p.glob('*.lock')))
    def test_explicit_count_product_not_dimensions(self):
        req={'source_hash':'h','method':'B','title':'5x30 Cápsulas','action_candidates':[dict(sku=str(i),title='pastillas') for i in range(5)]}
        pairs=[dict(sku=str(i),action_span='pastillas',amazon_pack=150,amazon_pack_span='5x30 Cápsulas',action_pack=None,action_pack_span='') for i in range(5)]
        a=dict(source_hash='h',subject_span='Cápsulas',pairs=pairs)
        validate(req,a)
        req['title']='5x30 cm';a['subject_span']='cm'
        for p in pairs:p['amazon_pack_span']='5x30 cm'
        with self.assertRaises(ValueError):validate(req,a)
    test_price=staticmethod(test_no_price_or_currency_inference)
    test_history=staticmethod(test_history_does_not_forward_fill_or_parent_dedup)
    test_quantity=staticmethod(test_quantity_is_literal_not_pack_inference)
    test_score=staticmethod(test_score_does_not_hide_missing_or_shared_need)
    test_comparability=staticmethod(test_price_requires_explicit_compatible_units_currency_dates)
