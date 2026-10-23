"""Program integration fixtures, not independent semantic accuracy labels."""
import copy,json,tempfile,unittest
from pathlib import Path
from runtime.v3.core import source_record
from runtime.v3.store import Store
from runtime.v3.workflow import screen,Provider,write_jsonl,safe_workspace_path
from runtime.v3.evaluation import evaluate

ROOT=Path(__file__).resolve().parents[1]

class CatalogFixture:
    by_sku={'MUG':{'name_es_original':'Taza'}}
    def retrieve(self,title,limit=8):return [{'sku':'MUG','name_es_original':'Taza','needs':['饮用'],'same_type_confirmed':False}]

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.dir=Path(self.tmp.name);self.db=self.dir/'test.sqlite3'
        self.raw={'record_id':'fixture:A','title_original':'Taza azul'};self.row=source_record(self.raw)
        self.a={'record_id':self.row['record_id'],'source_hash':self.row['source_hash'],'authority':'AI_CANDIDATE',
            'subject_span':'Taza','subject_type':'杯子','form':'ordinary_good','relation':'same_type','coverage':'subject',
            'action_sku':'MUG','reference_span':'Taza','reason':'合成杯子测试','information_status':'clear','operating_context':'daily'}
    def tearDown(self):self.tmp.cleanup()
    def provider(self,a=None,name='notes.jsonl'):
        p=self.dir/name;write_jsonl(p,[self.a if a is None else a]);return Provider('file',notes=p)
    def run_screen(self,provider,rows=None,**kwargs):
        return screen(ROOT,[self.raw] if rows is None else rows,self.db,self.dir/'outputs',provider,CatalogFixture(),**kwargs)
    def test_file_provider_resume_no_duplicate_data(self):
        first=self.run_screen(self.provider());second=self.run_screen(self.provider())
        self.assertEqual(first['run_id'],second['run_id']);self.assertEqual(second['new_data_rows'],0)
        self.assertEqual(second['reused_analyses'],1);self.assertEqual(second['provider_calls'],0)
        self.assertEqual(second['integrity'],{'integrity':'ok','foreign_keys':0})
    def test_cache_does_not_shadow_new_conflicting_analysis(self):
        self.run_screen(self.provider());old=self.run_screen(Provider('cache'))
        self.assertEqual(old['decisions']['保留'],1)
        changed=dict(self.a,relation='none',action_sku='',reference_span='',reason='第二份合成意见，没有参照')
        self.run_screen(self.provider(changed,'other.jsonl'))
        new=self.run_screen(Provider('cache'))
        self.assertNotEqual(new['run_id'],old['run_id']);self.assertEqual(new['semantic_pending'],1)
        self.assertEqual(new['decisions']['观察'],1);self.assertEqual(new['errors'],1)
    def test_missing_and_partial_coverage_cannot_retain(self):
        for coverage in [None,'partial','unknown']:
            a=dict(self.a,coverage=coverage)
            s=self.run_screen(self.provider(a,str(coverage)+'.jsonl'))
            self.assertEqual(s['decisions']['观察'],1)
            self.assertEqual(s['errors'],1 if coverage is None else 0)
    def test_null_subject_or_reason_or_context_never_completes_semantics(self):
        for key in ['subject_type','reason','operating_context']:
            s=self.run_screen(self.provider(dict(self.a,**{key:None}),key+'.jsonl'))
            self.assertEqual(s['semantic_completed'],0);self.assertEqual(s['errors'],1)
    def test_stale_analysis_queued_not_applied(self):
        s=self.run_screen(self.provider(),rows=[dict(self.raw,title_original='Taza verde')])
        self.assertEqual(s['semantic_pending'],1);self.assertEqual(s['decisions']['保留'],0)
    def test_duplicate_input_rejected_before_database_created(self):
        with self.assertRaisesRegex(ValueError,'DUPLICATE_SOURCE_ID'):self.run_screen(Provider(),rows=[self.raw,self.raw])
        self.assertFalse(self.db.exists())
    def test_queue_contains_actual_action_candidates_not_fake_analysis(self):
        s=self.run_screen(Provider())
        request=json.loads((Path(s['output'])/'semantic_requests.jsonl').read_text(encoding='utf-8'))
        self.assertEqual(request['action_candidates'][0]['sku'],'MUG');self.assertEqual(s['semantic_completed'],0)
        self.assertEqual(s['provider_calls'],0)
    def test_unknown_external_policy_rejected(self):
        with self.assertRaisesRegex(ValueError,'POLICY_MUST_BE_VERIFIED'):self.run_screen(Provider(),policy={'rules':[{'decision':'用不到'}]})
    def test_protected_asset_write_paths_rejected(self):
        for p in [ROOT/'assets/dont-create.sqlite3',ROOT/'runtime/dont-create',ROOT/'SKILL.md']:
            with self.assertRaisesRegex(ValueError,'GENERATED_PATH'):safe_workspace_path(ROOT,p)
        self.assertFalse((ROOT/'assets/dont-create.sqlite3').exists())
    def test_existing_non_v3_database_refused_unchanged(self):
        import sqlite3,hashlib
        db=sqlite3.connect(self.db);db.execute('create table business(x)');db.commit();db.close()
        before=hashlib.sha256(self.db.read_bytes()).hexdigest()
        with self.assertRaises(ValueError):self.run_screen(Provider())
        self.assertEqual(before,hashlib.sha256(self.db.read_bytes()).hexdigest())
    def test_price_changes_do_not_invalidate_title_cache(self):
        a=self.run_screen(self.provider(),rows=[dict(self.raw,price=3)])
        b=self.run_screen(self.provider(),rows=[dict(self.raw,price=5)])
        self.assertEqual(a['run_id'],b['run_id']);self.assertEqual(b['new_data_rows'],0)
    def test_command_provider_is_actually_called_and_resumes(self):
        import sys
        script=self.dir/'fake_provider.py';script.write_text('import json,sys\nr=json.load(sys.stdin)\na='+repr(self.a)+'\na["source_hash"]=r["source_hash"]\nprint(json.dumps(a,ensure_ascii=False))\n',encoding='utf-8')
        cfg=self.dir/'provider.json';cfg.write_text(json.dumps({'argv':[sys.executable,str(script)],'identity':'SYNTHETIC_TEST_ONLY','model':'mock','timeout_seconds':5}),encoding='utf-8')
        a=self.run_screen(Provider('command',command_config=cfg));b=self.run_screen(Provider('command',command_config=cfg))
        self.assertEqual(a['provider_calls'],1);self.assertEqual(b['provider_calls'],0);self.assertEqual(b['new_data_rows'],0)
    def test_no_human_labels_no_accuracy(self):
        s=self.run_screen(self.provider(),purpose='independent');store=Store(self.db)
        try:r=evaluate(ROOT,store,s['run_id'])
        finally:store.close()
        self.assertIsNone(r['reviewed_agreement']);self.assertIsNone(r['population_accuracy']);self.assertEqual(r['independently_reviewed_eligible'],0)
    def add_independent_label(self,store,decision='用不到'):
        from runtime.v3.feedback import import_feedback
        from runtime.v3.workflow import filehash
        evidence=self.dir/'human_fixture.txt';evidence.write_text('SYNTHETIC TEST EVIDENCE ONLY',encoding='utf-8')
        import_feedback(ROOT,store,[{'record_id':self.row['record_id'],'source_hash':self.row['source_hash'],
            'decision':decision,'authority':'HUMAN','reviewer':'SYNTHETIC_TEST_ONLY','evaluation_scope':'independent',
            'evidence_reference':str(evidence),'evidence_sha256':filehash(evidence)}])
    def test_post_prediction_label_does_not_rewrite_evaluation_prediction(self):
        s=self.run_screen(self.provider(),purpose='independent');store=Store(self.db)
        try:
            self.add_independent_label(store);r=evaluate(ROOT,store,s['run_id'])
        finally:store.close()
        self.assertEqual(r['independently_reviewed_eligible'],1);self.assertEqual(r['reviewed_agreement'],0)
    def test_development_exposure_never_counts_as_independent_accuracy(self):
        self.run_screen(self.provider(),purpose='development')
        s=self.run_screen(self.provider(),purpose='independent');store=Store(self.db)
        try:
            self.add_independent_label(store);r=evaluate(ROOT,store,s['run_id'])
        finally:store.close()
        self.assertEqual(r['independently_reviewed_eligible'],0);self.assertIsNone(r['reviewed_agreement'])
    def test_owner_overridden_results_excluded_from_independent_metric(self):
        self.run_screen(Provider(),purpose='independent');store=Store(self.db)
        try:self.add_independent_label(store)
        finally:store.close()
        s=self.run_screen(self.provider(),purpose='independent');store=Store(self.db)
        try:r=evaluate(ROOT,store,s['run_id'])
        finally:store.close()
        self.assertEqual(r['independently_reviewed_eligible'],0);self.assertEqual(r['excluded_owner_overrides'],[self.row['record_id']])

if __name__=='__main__':unittest.main()
