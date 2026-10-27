import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from scripts.selection_assistant import check,run,prompt,assistant_schema,candidates
from runtime.v31.core import source,validate

ROOT=Path(__file__).resolve().parents[1]
class Catalog:
    by_sku={'X':{'name_es_original':'Taza de cerámica'}}
    def retrieve(self,title,limit=6):return [dict(sku='X',name_es_original='Taza de cerámica')]

class AssistantContracts(unittest.TestCase):
    def setUp(self):
        self.row=source({'record_id':'synthetic','title_original':'Juego de tazas de cerámica','category_l1_original':''})
        self.a=dict(record_id='synthetic',source_hash=self.row['source_hash'],authority='AI_CANDIDATE',subject_span='tazas de cerámica',subject_type='陶瓷杯',subject_family='餐具',form='bundle',relation='same_type',action_sku='X',reference_span='Taza',reason='合成技术用例，不是Gold',information_status='clear',operating_context='daily',coverage='subject',match_strength='中',boundary='范围内',unknowns=[],features=[],functions=[],needs=[],selection_decision='保留',business_scope='common',review_question='')
    def test_unknown_cannot_retain_or_exclude(self):
        for decision in ['保留','用不到']:
            with self.assertRaises(ValueError):check(self.row,dict(self.a,selection_decision=decision,information_status='insufficient'),Catalog())
    def test_observation_requires_concrete_question_field(self):
        with self.assertRaisesRegex(ValueError,'QUESTION'):check(self.row,dict(self.a,selection_decision='观察'),Catalog())
    def test_exclusion_requires_explicit_experimental_outside_scope(self):
        with self.assertRaisesRegex(ValueError,'OUTSIDE'):check(self.row,dict(self.a,selection_decision='用不到'),Catalog())
    def test_no_reference_is_not_forced_observation(self):
        a=dict(self.a,relation='none',action_sku='',reference_span='',match_strength='未知');validate(self.row,a,Catalog());check(self.row,a,Catalog())
    def test_source_hash_and_real_reference_still_checked(self):
        for a in [dict(self.a,source_hash='wrong'),dict(self.a,reference_span='invented')]:
            with self.assertRaises(ValueError):validate(self.row,a,Catalog())
    def test_same_small_batch_resumes_without_duplicate_events_or_human_gold(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);f=p/'a.jsonl';f.write_text(json.dumps(self.a)+'\n',encoding='utf-8')
            with patch('scripts.selection_assistant.Catalog',return_value=Catalog()):
                r=run(ROOT,[self.row],p/'out',mode='file',analysis=f);r2=run(ROOT,[self.row],p/'out',mode='file',analysis=f)
            self.assertEqual(r['completed'],1);self.assertEqual(r['run_id'],r2['run_id']);self.assertEqual(r2['calls_this_attempt'],0);self.assertEqual(r2['cached_records'],1);self.assertEqual(r2['human_gold'],0)
            from runtime.v31.state import State
            s=State(p/'out/learning.sqlite3')
            try:self.assertEqual(len(s.all('assistant_result')),1);self.assertEqual(s.store.all('v3_feedback'),[])
            finally:s.close()
    def test_frozen_contract_drift_blocks_before_call(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);f=p/'frozen.txt';f.write_text('changed')
            with self.assertRaisesRegex(ValueError,'FROZEN'):run(ROOT,[self.row],p/'out',frozen={str(f):'wrong'})
    def test_plain_and_skill_receive_distinct_instructions_same_structured_contract(self):
        self.assertNotEqual(prompt(ROOT,'ordinary'),prompt(ROOT,'skill'));self.assertIn('selection_decision',assistant_schema()['properties']['analyses']['items']['required'])
    def test_retrieval_views_are_literal_deduplicated_and_not_selection(self):
        class Retrieval:
            def __init__(self):self.queries=[]
            def retrieve(self,q,limit=6):
                self.queries.append(q);return [dict(sku=str(i),name_es_original='reference') for i in (range(6) if '|' in q else range(3,9))]
        c=Retrieval();r=candidates(c,'Taza | para cocina')
        self.assertEqual(c.queries,['Taza | para cocina','Taza']);self.assertEqual(len(r),6);self.assertEqual(len({x['sku'] for x in r}),6)
