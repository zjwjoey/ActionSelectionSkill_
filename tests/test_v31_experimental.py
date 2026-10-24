import copy,json,tempfile,unittest
from pathlib import Path
from runtime.v31.core import source,validate,project,reconcile,matches,CHANNEL
from runtime.v31.state import State
from runtime.v31.rules import propose,release,validate_rule,active_release
from runtime.v31.workflow import execute

ROOT=Path(__file__).resolve().parents[1]
class Catalog:
    by_sku={'A':{'name_es_original':'Aspirador de mano'}}
    def retrieve(self,title,limit=6):return [dict(sku='A',name_es_original='Aspirador de mano')]

class Experimental(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.dir=Path(self.tmp.name);self.catalog=Catalog()
        self.raw={'record_id':'fixture1','title_original':'Robot aspirador con navegación láser y autolimpieza','category_l1_original':'Hogar'}
        self.row=source(self.raw)
        self.a=dict(record_id='fixture1',source_hash=self.row['source_hash'],authority='AI_CANDIDATE',subject_span='Robot aspirador',subject_type='吸拖机器人',subject_family='清洁设备',form='whole_machine',relation='specific_need',action_sku='A',reference_span='Aspirador de mano',reason='合成技术用例，不是人工标准',functions=[],needs=['清洁'],information_status='clear',operating_context='unknown',coverage='partial',match_strength='弱',boundary='范围外',unknowns=['经营边界未确认'],features=[dict(name='robot_cleaner',span='Robot aspirador'),dict(name='autonomous_navigation',span='navegación láser')])
        self.rule=dict(channel=CHANNEL,authority='AI_CANDIDATE',version='1',decision='用不到',rationale='合成技术规则',conditions=dict(families=['清洁设备'],forms=['whole_machine'],features_all=['robot_cleaner','autonomous_navigation']),support_ids=['a','b'],counterexample_ids=['c','d'])
    def tearDown(self):self.tmp.cleanup()
    def test_category_is_hash_bound(self):self.assertNotEqual(source(dict(self.raw,category_l1_original='Industrial'))['source_hash'],self.row['source_hash'])
    def test_none_category_equals_missing(self):self.assertEqual(source(dict(self.raw,category_l1_original=None)),source({k:v for k,v in self.raw.items() if k!='category_l1_original'}))
    def test_positive_feature_must_be_literal(self):
        with self.assertRaisesRegex(ValueError,'LITERAL'):validate(self.row,dict(self.a,features=[dict(name='robot_cleaner',span='not in title')]),self.catalog)
    def test_broad_need_not_retain(self):self.assertEqual(project(self.row,self.a,self.catalog)['decision'],'观察')
    def test_no_match_cannot_exclude(self):
        a=dict(self.a,relation='none',action_sku='',reference_span='',match_strength='未知')
        self.assertEqual(project(self.row,a,self.catalog)['decision'],'观察')
    def test_explicit_experiment_not_human(self):
        state=State(self.dir/'s.db')
        try:r=propose(state,self.rule);p=project(self.row,self.a,self.catalog,[r]);self.assertEqual(p['decision'],'用不到');self.assertFalse(p['human_confirmed']);self.assertFalse(p['formal_publication']);self.assertEqual(state.store.all('v3_rule_releases'),[])
        finally:state.close()
    def test_accessory_not_excluded_as_machine(self):
        a=dict(self.a,form='host_component');self.assertFalse(matches(self.rule,a));self.assertEqual(project(self.row,a,self.catalog,[dict(self.rule,rule_id='r')])['decision'],'观察')
    def test_missing_review_observe(self):self.assertEqual(reconcile(self.row,self.a,None,self.catalog)['reason_code'],'SECOND_REVIEW_PENDING')
    def test_conflicting_boundary_observe(self):
        b=dict(self.a,boundary='灰区');r=reconcile(self.row,self.a,b,self.catalog);self.assertEqual(r['decision'],'观察');self.assertIn('boundary',r['disagreement_layers'])
    def test_false_human_candidate_rejected(self):
        with self.assertRaises(ValueError):validate(self.row,dict(self.a,human_confirmed=True),self.catalog)
    def test_rule_requires_counterexamples(self):
        s=State(self.dir/'s.db')
        try:
            with self.assertRaises(ValueError):propose(s,dict(self.rule,counterexample_ids=[]))
        finally:s.close()
    def test_single_keyword_exclusion_refused(self):
        s=State(self.dir/'s.db')
        try:
            c=dict(self.rule['conditions'],features_all=['robot_cleaner'])
            with self.assertRaises(ValueError):propose(s,dict(self.rule,conditions=c))
        finally:s.close()
    def test_fake_human_channel_refused(self):
        s=State(self.dir/'s.db')
        try:
            with self.assertRaises(ValueError):propose(s,dict(self.rule,authority='HUMAN'))
        finally:s.close()
    def test_release_needs_validation(self):
        s=State(self.dir/'s.db')
        try:
            r=propose(s,self.rule)
            with self.assertRaises(ValueError):release(ROOT,s,r['rule_id'],'missing')
        finally:s.close()
    def test_file_two_pass_and_idempotency(self):
        f=self.dir/'first.jsonl';g=self.dir/'review.jsonl'
        f.write_text(json.dumps(self.a,ensure_ascii=False)+'\n',encoding='utf-8');g.write_text(f.read_text(encoding='utf-8'),encoding='utf-8')
        args=[ROOT,[self.raw],self.dir/'s.db',self.dir/'out',self.catalog]
        a=execute(*args,mode='file',analysis=f,review=g);b=execute(*args,mode='file',analysis=f,review=g)
        self.assertEqual(a['execution_id'],b['execution_id']);self.assertEqual(b['reused_model_records'],2);self.assertEqual(a['completed'],1)
        s=State(self.dir/'s.db')
        try:self.assertEqual(len(s.all('result')),1);self.assertEqual(s.store.all('v3_feedback'),[])
        finally:s.close()
    def test_queue_not_counted_completed(self):
        r=execute(ROOT,[self.raw],self.dir/'s.db',self.dir/'q',self.catalog)
        self.assertEqual(r['completed'],0);self.assertEqual(r['pending'],1);self.assertEqual(r['actual_model_process_calls'],0)

    def support_run(self,purpose='development'):
        raw=[];analyses=[]
        for i in range(4):
            rr=dict(self.raw,record_id=str(i),title_original=self.raw['title_original']+' modelo '+str(i))
            aa=dict(self.a,record_id=str(i),source_hash=source(rr)['source_hash'])
            if i>=2:aa.update(form='host_component',boundary='灰区',features=[])
            raw.append(rr);analyses.append(aa)
        p=self.dir/'four.jsonl';p.write_text(''.join(json.dumps(a,ensure_ascii=False)+'\n' for a in analyses),encoding='utf-8')
        return execute(ROOT,raw,self.dir/'s.db',self.dir/'four',self.catalog,mode='file',analysis=p,review=p,purpose=purpose)
    def test_validate_release_and_incremental_preserve_parent(self):
        from runtime.v31.workflow import rescreen
        r=self.support_run();s=State(self.dir/'s.db')
        try:
            before=s.all('result');rule=propose(s,dict(self.rule,support_ids=['0','1'],counterexample_ids=['2','3']))
            vid,v=validate_rule(ROOT,s,rule['rule_id'],r['execution_id'],self.catalog);self.assertEqual(v['status'],'PASS')
            rel=release(ROOT,s,rule['rule_id'],vid);rules=active_release(ROOT,s,rel,self.catalog);self.assertEqual(len(rules),1)
            delta=rescreen(ROOT,s,r['execution_id'],rel,self.catalog);self.assertEqual(delta['affected'],2);self.assertEqual(delta['changed'],2)
            self.assertEqual(before,s.all('result'));self.assertEqual(s.store.all('v3_rule_releases'),[])
            self.assertEqual(s.store.check(),{'integrity':'ok','foreign_keys':0})
        finally:s.close()
    def test_independent_rows_cannot_support_training(self):
        run=self.support_run('independent');s=State(self.dir/'s.db')
        try:
            rule=propose(s,dict(self.rule,support_ids=['0','1'],counterexample_ids=['2','3']))
            with self.assertRaisesRegex(ValueError,'DEVELOPMENT'):validate_rule(ROOT,s,rule['rule_id'],run['execution_id'],self.catalog)
        finally:s.close()
    def test_counterexample_that_matches_fails(self):
        run=self.support_run();s=State(self.dir/'s.db')
        try:
            # Swap one real positive into the declared counterexamples.
            rule=propose(s,dict(self.rule,support_ids=['0','2'],counterexample_ids=['1','3']))
            vid,v=validate_rule(ROOT,s,rule['rule_id'],run['execution_id'],self.catalog);self.assertEqual(v['status'],'FAIL')
            with self.assertRaisesRegex(ValueError,'VALIDATION'):release(ROOT,s,rule['rule_id'],vid)
        finally:s.close()
    def test_experiment_event_tampering_rejected(self):
        s=State(self.dir/'tamper.db')
        try:
            key=s.put('fixture',{'decision':'观察'})
            s.db.execute('UPDATE v31_events SET payload=? WHERE id=?',(json.dumps({'decision':'用不到'},ensure_ascii=False),key));s.db.commit()
            with self.assertRaisesRegex(ValueError,'HASH_MISMATCH'):s.get(key)
        finally:s.close()
    def test_schema_binds_hash_to_exact_allowed_values(self):
        from runtime.v31.model import schema
        fields=schema([self.row])['properties']['analyses']['items']['properties']
        self.assertEqual(fields['source_hash']['enum'],[self.row['source_hash']]);self.assertNotIn('ordinary_accessory',fields['form']['enum'])
    def test_validation_failure_cannot_double_count_partial_batch(self):
        a=copy.deepcopy(self.a);b=dict(a,record_id='second',source_hash=source(dict(self.raw,record_id='second'))['source_hash'],form='ordinary_accessory')
        path=self.dir/'bad.jsonl';path.write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in [a,b]),encoding='utf-8')
        r=execute(ROOT,[self.raw,dict(self.raw,record_id='second')],self.dir/'bad.db',self.dir/'bad',self.catalog,mode='file',analysis=path,review=path)
        self.assertEqual(r['completed'],0);self.assertEqual(r['pending'],2);self.assertEqual(r['result_rows'],0)
    def test_duplicate_feature_spans_not_extra_predicates(self):
        a=dict(self.a,features=self.a['features']+[self.a['features'][0]])
        validate(self.row,a,self.catalog)
        s=State(self.dir/'dup.db')
        try:
            c=dict(self.rule['conditions'],features_all=['robot_cleaner','robot_cleaner'])
            with self.assertRaises(ValueError):propose(s,dict(self.rule,conditions=c))
        finally:s.close()
    def test_absent_reference_grade_not_false_disagreement(self):
        a=dict(self.a,action_sku='',reference_span='',relation='none',match_strength='未知')
        b=dict(a,match_strength='弱',coverage='unknown')
        self.assertNotIn('reference',reconcile(self.row,a,b,self.catalog)['disagreement_layers'])
    def test_full_experiment_needs_prior_real_evidence(self):
        with self.assertRaisesRegex(ValueError,'FULL_EXPERIMENT'):
            execute(ROOT,[self.raw],self.dir/'full.db',self.dir/'full',self.catalog,purpose='full')
    def test_two_names_on_one_keyword_not_compound_boundary(self):
        a=dict(self.a,features=[dict(name='robot_cleaner',span='Robot aspirador'),dict(name='autonomous_navigation',span='Robot aspirador')])
        self.assertFalse(matches(self.rule,a))
    def test_retain_rule_cannot_bypass_concrete_reference(self):
        a=dict(self.a,operating_context='daily',boundary='范围内')
        rule=dict(self.rule,rule_id='r',decision='保留')
        self.assertEqual(project(self.row,a,self.catalog,[rule])['decision'],'观察')
    def test_repeat_attempt_files_are_preserved(self):
        p=self.dir/'a.jsonl';p.write_text(json.dumps(self.a,ensure_ascii=False)+'\n',encoding='utf-8')
        args=[ROOT,[self.raw],self.dir/'s.db',self.dir/'out',self.catalog]
        a=execute(*args,mode='file',analysis=p,review=p);b=execute(*args,mode='file',analysis=p,review=p)
        self.assertNotEqual(a['output'],b['output']);self.assertTrue((Path(a['output'])/'summary.json').is_file())
    def test_formal_owner_binding_preserved_without_rewriting_approval(self):
        from unittest.mock import patch
        from runtime.v3.core import source_record as old_source
        from runtime.v3.store import Store
        from runtime.v31.workflow import affected
        original_all=Store.all
        # Synthetic technical fixture only. No human feedback is persisted.
        owner=dict(record_id=self.raw['record_id'],source_hash=old_source(self.raw)['source_hash'],decision='用不到',authority='HUMAN',reviewer='SYNTHETIC_TEST_ONLY',feedback_id='fixture-only')
        def rows(store,table):return [owner] if table=='v3_feedback' else original_all(store,table)
        f=self.dir/'owner.jsonl';f.write_text(json.dumps(self.a,ensure_ascii=False)+'\n',encoding='utf-8')
        with patch.object(Store,'all',rows),patch('runtime.v31.workflow.evidence'):
            report=execute(ROOT,[self.raw],self.dir/'owner.db',self.dir/'owner',self.catalog,mode='file',analysis=f,review=f)
        result=json.loads((Path(report['output'])/'results.jsonl').read_text(encoding='utf-8'))
        self.assertEqual(result['decision'],result['v3_baseline']);self.assertEqual(result['decision'],'用不到')
        self.assertEqual(result['formal_owner_binding']['source_hash'],owner['source_hash']);self.assertNotEqual(result['source_hash'],owner['source_hash'])
        s=State(self.dir/'owner.db')
        try:self.assertEqual(s.store.all('v3_feedback'),[]);self.assertEqual(affected(s,report['execution_id'],[self.rule]),[])
        finally:s.close()
    def test_repair_feedback_does_not_leak_between_blind_rounds(self):
        from runtime.v31.model import Model
        p=self.dir/'notes.jsonl';p.write_text(json.dumps(self.a,ensure_ascii=False)+'\n',encoding='utf-8')
        s=State(self.dir/'repair.db')
        try:
            m=Model(s,self.dir/'repair',mode='file',notes=p)
            s.put('model_invalid',dict(provider=m.identity,role='understand',error_by_id={self.row['record_id']:dict(source_hash=self.row['source_hash'],error='SUBJECT_SPAN_NOT_LITERAL')}))
            self.assertEqual(m.repair_feedback([self.row],'critic'),{})
            self.assertEqual(m.repair_feedback([self.row],'understand'),{self.row['record_id']:['SUBJECT_SPAN_NOT_LITERAL']})
        finally:s.close()
    def test_typed_subject_rule_not_bound_to_chinese_family_wording(self):
        s=State(self.dir/'typed.db')
        try:
            c=dict(self.rule['conditions'],families=[]);r=propose(s,dict(self.rule,conditions=c))
            self.assertTrue(matches(r,dict(self.a,subject_family='另一种正确的清洁设备表述')))
            self.assertFalse(matches(r,dict(self.a,form='host_component')))
        finally:s.close()
    def test_need_only_rule_without_type_scope_rejected(self):
        s=State(self.dir/'need.db')
        try:
            c=dict(self.rule['conditions'],families=[],features_all=['household_good','host_dependency'])
            with self.assertRaisesRegex(ValueError,'IDENTITY'):propose(s,dict(self.rule,conditions=c))
        finally:s.close()
    def test_ordinary_and_universal_role_granularity_not_subject_error(self):
        a=dict(self.a,form='ordinary_good',operating_context='daily',boundary='范围内',relation='same_type',coverage='subject',match_strength='强')
        b=dict(a,form='universal_accessory');r=reconcile(self.row,a,b,self.catalog)
        self.assertEqual(r['decision'],'保留');self.assertNotIn('subject',r['disagreement_layers'])
        self.assertTrue(r['ordinary_role_granularity_variation'])
        self.assertEqual(reconcile(self.row,a,dict(b,form='host_component'),self.catalog)['decision'],'观察')
    def test_bulk_event_read_uses_one_select_and_verifies_hashes(self):
        s=State(self.dir/'bulk.db')
        try:
            keys=[s.put('fixture',{'n':i}) for i in range(5)];sql=[];s.db.set_trace_callback(sql.append)
            self.assertEqual(len(s.all('fixture')),5)
            self.assertEqual(sum(q.lstrip().upper().startswith('SELECT') for q in sql),1)
            s.db.set_trace_callback(None)
            s.db.execute('UPDATE v31_events SET payload=? WHERE id=?',(json.dumps({'n':'tampered'}),keys[0]));s.db.commit()
            with self.assertRaisesRegex(ValueError,'HASH_MISMATCH'):s.all('fixture')
        finally:s.close()
    def test_api_key_login_rejected_without_model_execution(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from runtime.v31.model import require_chatgpt_login
        with patch('runtime.v31.model.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='',stderr='Logged in using an API key')) as proc:
            with self.assertRaisesRegex(ValueError,'NO_PAID_API'):require_chatgpt_login('fixture-exe')
            self.assertEqual(proc.call_count,1)
        with patch('runtime.v31.model.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='',stderr='Logged in using ChatGPT')):
            require_chatgpt_login('fixture-exe')

    def report_segments_fixture(self):
        from types import SimpleNamespace
        row2=source(dict(self.raw,record_id='fixture2'))
        a2=dict(self.a,record_id='fixture2',source_hash=row2['source_hash'])
        r1=dict(reconcile(self.row,self.a,self.a,self.catalog),run_id='run1',execution_id='exec1')
        r2=dict(reconcile(row2,a2,a2,self.catalog),run_id='run2',execution_id='exec2')
        runs={'run1':{'sources':[self.row,row2],'purpose':'independent','contract':{'frozen':True},'release':'release'},'run2':{'sources':[row2],'purpose':'independent','contract':{'frozen':True},'release':'release'}}
        rows=[('r1',r1),('r2',r2)]
        return SimpleNamespace(all=lambda kind:rows if kind=='result' else [],get=lambda key,kind:runs[key]),runs,rows
    def test_report_disjoint_execution_segments_preserve_two_passes(self):
        from scripts.v31_report import export_run
        state,_,_=self.report_segments_fixture()
        r=export_run(state,'exec1',self.dir/'report',segments=['exec2'])
        self.assertEqual(r['sources'],2);self.assertEqual(r['both_model_passes_completed'],2)
        self.assertEqual(r['pending'],0);self.assertIsNone(r['formal_accuracy'])
    def test_report_overlapping_segments_rejected(self):
        from scripts.v31_report import export_run
        state,_,_=self.report_segments_fixture()
        with self.assertRaisesRegex(ValueError,'OVERLAPPING'):export_run(state,'exec1',self.dir/'report',segments=['exec1'])
    def test_report_changed_segment_contract_rejected(self):
        from scripts.v31_report import export_run
        state,runs,_=self.report_segments_fixture();runs['run2']['contract']={'frozen':False}
        with self.assertRaisesRegex(ValueError,'INCOMPATIBLE'):export_run(state,'exec1',self.dir/'report',segments=['exec2'])

if __name__=='__main__':unittest.main()
