"""Synthetic fixtures verify safety and resume, not business accuracy."""
import csv,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from runtime.retail.ingestion import ingest
from runtime.retail.engine import check,feedback,run
from runtime.retail.pricing import compare
from runtime.v3.core import digest

class RetailTests(unittest.TestCase):
    def test_source_ids_and_observations_survive_incomplete_csv(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'input.csv'
            p.write_text('货号,官方商品名（原文）,当前售价 EUR,商品链接\n00123,Caja,2.50,https://www.ikea.com/x\n00123,Caja,3,https://www.ikea.com/x\n0,,1,\n',encoding='utf8')
            r,e=ingest(p,'ikea')
            self.assertEqual(len(e),1);self.assertEqual(r[0]['source_product_id'],'00123')
            self.assertEqual(r[0]['internal_product_id'],r[1]['internal_product_id']);self.assertNotEqual(r[0]['quote_id'],r[1]['quote_id'])
            self.assertEqual(r[0]['price_currency'],'EUR');self.assertIsNone(r[0]['package_quantity'])

    def test_jsonl_does_not_infer_currency_or_date(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'p.jsonl';p.write_text('{"title":"Caja 5L", "price":2.5}\ninvalid\n',encoding='utf8')
            r,e=ingest(p)
            self.assertEqual(len(e),1);self.assertIsNone(r[0]['price_currency']);self.assertEqual(r[0]['price_date'],'')

    def test_excel_dates_remain_serializable_and_ids_keep_zero(self):
        import openpyxl
        from datetime import datetime
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'p.xlsx';w=openpyxl.Workbook();s=w.active
            s.append(['title','sku','date','price']);s.append(['Caja','00123',datetime(2026,10,30),2.5]);w.save(p);w.close()
            r,_=ingest(p);json.dumps(r)
            self.assertEqual(r[0]['source_product_id'],'00123');self.assertTrue(r[0]['source_evidence']['date'].startswith('2026-10-30'))

    def test_wholesale_cannot_be_retail_ratio(self):
        a=dict(source_product_id='a',title_original='Jabon 500ml',specifications='',variant='',price_value=3,price_currency='EUR',price_type='wholesale',price_date='2026-01-01',source_file='f',source_sha256='h')
        b={**a,'price_type':'retail'}
        r=compare(a,b,'SAME_TYPE',{'f':'h'});self.assertTrue(r['L1_source']['valid']);self.assertFalse(r['L2']['eligible'])
        a['price_type']='retail';r=compare(a,b,'UNRELATED',{'f':'h'});self.assertFalse(r['L3']['eligible'])

    def test_reference_source_books_are_hashed_once_per_file(self):
        from runtime.retail.engine import References
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'catalog.jsonl';p.write_text('{"title":"Caja", "sku":"a"}\n',encoding='utf8')
            quote=dict(sku='a',source_file=str(p),source_sha256='fixture',title='Caja',spec='',price=dict(value=2,currency='EUR'),source_date='2026-10-30',url='',title_binding_exact=True)
            q=Path(d)/'quotes.jsonl';q.write_text(json.dumps(quote)+'\n'+json.dumps({**quote,'sku':'b'})+'\n',encoding='utf8')
            from runtime.retail.engine import filehash
            with patch('runtime.retail.engine.filehash',wraps=filehash) as hashed:
                References(str(p),q)
            # One quote-source hash plus one reference-version hash, not per SKU.
            self.assertEqual(hashed.call_count,2)

    def test_unknown_subject_and_identity_assertion_are_rejected(self):
        req=dict(record_id='r',source_hash='h',title='Caja',action_candidates=[])
        a=dict(record_id='r',source_hash='h',subject_span='Caja',subject_status='insufficient',selection='用不到',scope_basis='x',pairs=[])
        with self.assertRaisesRegex(ValueError,'UNKNOWN_SUBJECT'):check(req,a)

    def test_queue_resume_and_feedback_do_not_forge_gold(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'p.jsonl';p.write_text('{"title":"Caja", "sku":"a"}\n',encoding='utf8')
            ref=Path(d)/'ref.jsonl';ref.write_text('{"title":"Caja", "sku":"b"}\n',encoding='utf8')
            out=Path(d)/'out'
            s=run(p,out,reference=str(ref),do_export=False)
            self.assertEqual(s['pending'],1);self.assertEqual(s['calls_total'],0)
            run(p,out,reference=str(ref),do_export=False)
            r=json.loads((out/'results.jsonl').read_text())
            feedback(out,r['record_id'],digest(r),'观察','fixture-reviewer','fixture only')
            self.assertEqual(r,json.loads((out/'results.jsonl').read_text()))
            with self.assertRaisesRegex(ValueError,'STALE_RESULT'):feedback(out,r['record_id'],'bad','保留','reviewer','reason')
            p.write_text('{"title":"Mesa"}\n',encoding='utf8')
            with self.assertRaisesRegex(ValueError,'RESUME_CONTRACT_CHANGED'):run(p,out,reference=str(ref),do_export=False)
