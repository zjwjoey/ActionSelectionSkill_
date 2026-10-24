import copy,json,tempfile,unittest
from pathlib import Path
from runtime.v31.core import source,reconcile
from runtime.v31.reviewed import VERSION,review_schema,validate_review,reviewed_projection
from runtime.v31.reviewed_workflow import execute_reviewed
from runtime.v31.state import State

ROOT=Path(__file__).resolve().parents[1]
class Catalog:
    by_sku={'A':{'name_es_original':'Cuenco de porcelana','source_row_id':'fixture'}}
    def retrieve(self,title,limit=6):return [dict(sku='A',name_es_original='Cuenco de porcelana')]

class ReviewedObservation(unittest.TestCase):
    def setUp(self):
        self.cat=Catalog();self.row=source({'record_id':'fixture','title_original':'Juego de 6 cuencos de porcelana para cocina'})
        self.a=dict(record_id='fixture',source_hash=self.row['source_hash'],authority='AI_CANDIDATE',subject_span='cuencos de porcelana',subject_type='瓷碗',subject_family='厨房餐具',form='ordinary_good',relation='same_type',action_sku='A',reference_span='Cuenco',reason='合成技术测试，不是人工标签',functions=['盛食物'],needs=['用餐'],information_status='clear',operating_context='daily',coverage='subject',match_strength='强',boundary='范围内',unknowns=[],features=[dict(name='household_good',span='cuencos')],screening_evidence=dict(contract=VERSION,type_key='瓷碗',structure='homogeneous_multipack',structure_span='Juego de 6 cuencos',scope='daily_independent',blockers=[]))
    def result(self,a=None,b=None,base=None):
        a=copy.deepcopy(a or self.a);b=copy.deepcopy(b or a)
        return reviewed_projection(self.row,a,b,self.cat,base or reconcile(self.row,a,b,self.cat))
    def test_same_type_pack_granularity_not_subject_conflict(self):
        b=dict(self.a,form='bundle');old=reconcile(self.row,self.a,b,self.cat)
        self.assertEqual(old['decision'],'观察');new=self.result(b=b,base=old);self.assertEqual(new['decision'],'保留');self.assertTrue(new['homogeneous_pack_compatible'])
    def test_reference_grade_variation_not_operating_blocker(self):
        b=dict(self.a,relation='related_type',match_strength='中');r=self.result(b=b)
        self.assertEqual(r['decision'],'保留');self.assertEqual(r['reference']['relation'],'related_type')
    def test_missing_reference_not_fabricated(self):
        b=dict(self.a,relation='none',action_sku='',reference_span='',match_strength='未知')
        r=self.result(b=b);self.assertEqual(r['decision'],'保留');self.assertIsNone(r['reference']);self.assertEqual(r['action_reference_status'],'unproven_or_disputed')
    def test_use_object_is_not_promoted_to_same_type(self):
        a=dict(self.a,relation='host_only',match_strength='弱');r=self.result(a=a)
        self.assertEqual(r['decision'],'保留');self.assertIsNone(r['reference'])
    def test_custom_order_vetoes_old_retain(self):
        a=copy.deepcopy(self.a);a['screening_evidence'].update(scope='boundary_unresolved',blockers=[dict(code='custom_order',span='Juego',reason='合成示例：定制经营未确认')])
        r=self.result(a=a);self.assertEqual(r['decision'],'观察');self.assertEqual(r['reason_code'],'REVIEW_CONCRETE_BLOCKER')
    def test_single_pass_blocker_is_not_outvoted(self):
        b=copy.deepcopy(self.a);b['screening_evidence'].update(scope='boundary_unresolved',blockers=[dict(code='operating_boundary',span='cocina',reason='合成经营边界')])
        self.assertEqual(self.result(b=b)['decision'],'观察')
    def test_dedicated_component_not_auto_retain(self):
        self.assertEqual(self.result(a=dict(self.a,form='host_component'))['decision'],'观察')
    def test_installed_component_stays_observe(self):self.assertEqual(self.result(a=dict(self.a,form='installed_component'))['decision'],'观察')
    def test_unknown_not_auto_retain(self):self.assertEqual(self.result(a=dict(self.a,information_status='insufficient'))['decision'],'观察')
    def test_gray_scope_not_auto_retain(self):self.assertEqual(self.result(a=dict(self.a,boundary='灰区'))['decision'],'观察')
    def test_different_type_keys_stay_observe(self):
        b=copy.deepcopy(self.a);b['screening_evidence']['type_key']='不同物体'
        self.assertEqual(self.result(b=b)['decision'],'观察')
    def test_mixed_uncovered_bundle_stays_observe(self):
        a=copy.deepcopy(self.a);a['form']='bundle';a['screening_evidence']['structure']='mixed_components'
        self.assertEqual(self.result(a=a)['decision'],'观察')
    def test_source_hash_mismatch_rejected(self):
        with self.assertRaises(ValueError):self.result(a=dict(self.a,source_hash='bad'))
    def test_nonliteral_blocker_rejected(self):
        a=copy.deepcopy(self.a);a['screening_evidence'].update(scope='boundary_unresolved',blockers=[dict(code='host_dependency',span='invented',reason='bad')])
        with self.assertRaisesRegex(ValueError,'LITERAL'):self.result(a=a)
    def test_daily_and_blocker_contract_is_invalid(self):
        a=copy.deepcopy(self.a);a['screening_evidence']['blockers']=[dict(code='source_conflict',span='Juego',reason='conflict')]
        with self.assertRaisesRegex(ValueError,'DAILY'):self.result(a=a)
    def test_original_readings_not_mutated(self):
        a=copy.deepcopy(self.a);b=dict(a,relation='related_type');old=reconcile(self.row,a,b,self.cat);before=copy.deepcopy((a,b,old));self.result(a,b,old);self.assertEqual((a,b,old),before)
    def test_cannot_create_new_exclusion(self):
        a=copy.deepcopy(self.a);a.update(boundary='范围外');a['screening_evidence']['scope']='outside_candidate'
        self.assertEqual(self.result(a=a)['decision'],'观察')
    def test_existing_exclusion_not_broadened_or_removed(self):
        base=reconcile(self.row,self.a,self.a,self.cat);base['decision']='用不到'
        self.assertEqual(self.result(base=base)['decision'],'用不到')
    def test_existing_owner_decision_not_overwritten(self):
        base=reconcile(self.row,self.a,self.a,self.cat);base.update(decision='观察',human_confirmed=True)
        self.assertTrue(self.result(base=base)['human_confirmed']);self.assertEqual(self.result(base=base)['decision'],'观察')
    def test_confirmed_gray_policy_is_preserved(self):
        base=reconcile(self.row,self.a,self.a,self.cat);base.update(decision='观察',calibration_rules=['C_GRAY'])
        self.assertEqual(self.result(base=base)['decision'],'观察')
    def test_missing_review_not_complete(self):
        base=reconcile(self.row,self.a,None,self.cat);self.assertEqual(reviewed_projection(self.row,self.a,None,self.cat,base)['decision'],'观察')
    def test_schema_extensions_are_explicit(self):
        self.assertIn('screening_evidence',review_schema()['properties']['analyses']['items']['required'])
    def test_file_workflow_resume_immutable_and_no_formal_writes(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);f=p/'a.jsonl';f.write_text(json.dumps(self.a,ensure_ascii=False)+'\n',encoding='utf-8');policy=p/'policy.json';policy.write_text('{"rules":[]}',encoding='utf-8')
            args=[ROOT,[self.row],p/'s.db',p/'out',self.cat,policy]
            r=execute_reviewed(*args,mode='file',analysis=f,review=f);r2=execute_reviewed(*args,mode='file',analysis=f,review=f)
            self.assertEqual(r['completed'],1);self.assertEqual(r['execution'],r2['execution']);self.assertEqual(r2['actual_model_process_calls_this_attempt'],0)
            state=State(p/'s.db')
            try:self.assertEqual(len(state.all('reviewed_result')),1);self.assertEqual(state.store.all('v3_feedback'),[]);self.assertEqual(state.store.all('v3_rule_releases'),[])
            finally:state.close()
