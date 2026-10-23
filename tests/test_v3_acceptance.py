"""V3 acceptance contracts with synthetic titles and a small fake catalog.

These tests check source binding, sold-object protection and authority gates.
They do not measure product-classification accuracy or create real feedback.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.v3.core import decide, source_record, validate_analysis


class FakeCatalog:
    def __init__(self):
        self.by_sku = {
            "TEST_MUG": {"sku": "TEST_MUG", "name_es_original": "Taza de cerámica", "title": "Taza de cerámica", "source_row_id": "fixture_mug"},
            "TEST_BLENDER": {"sku": "TEST_BLENDER", "name_es_original": "Batidora de mano", "title": "Batidora de mano", "source_row_id": "fixture_blender"},
            "TEST_FRIDGE": {"sku": "TEST_FRIDGE", "name_es_original": "Frigorífico de mesa", "title": "Frigorífico de mesa", "source_row_id": "fixture_fridge"},
            "TEST_WASHER": {"sku": "TEST_WASHER", "name_es_original": "Lavadora", "title": "Lavadora", "source_row_id": "fixture_washer"},
            "TEST_DISHWASHER": {"sku": "TEST_DISHWASHER", "name_es_original": "Lavavajillas", "title": "Lavavajillas", "source_row_id": "fixture_dishwasher"},
        }
        self.semantics = {
            "TEST_MUG": {"subject_type": "陶瓷杯", "functions": ["盛装饮品"], "needs": ["日常饮用"]},
            "TEST_BLENDER": {"subject_type": "手持搅拌机", "functions": ["搅拌食材"], "needs": ["家庭备餐"]},
            "TEST_FRIDGE": {"subject_type": "冰箱", "functions": ["冷藏食物"], "needs": ["食品保存"]},
            "TEST_WASHER": {"subject_type": "洗衣机", "functions": ["洗涤衣物"], "needs": ["衣物清洁"]},
            "TEST_DISHWASHER": {"subject_type": "洗碗机", "functions": ["清洗餐具"], "needs": ["餐具清洁"]},
        }


class V3AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.catalog = FakeCatalog()
        self.policy = {"version": "synthetic-test-policy", "rules": []}
        self.row = source_record({"record_id": "fixture:amazon:A", "title_original": "Taza de cerámica azul"})

    def analysis(self, row=None, **changes):
        row = row or self.row
        a = {
            "source_hash": row["source_hash"],
            "subject_span": "Taza de cerámica",
            "subject_type": "陶瓷杯",
            "form": "ordinary_good",
            "relation": "same_type",
            "action_sku": "TEST_MUG",
            "reference_span": "Taza de cerámica",
            "reason": "合成测试中源与参照同为陶瓷杯，不代表真人审定。",
            "functions": ["盛装饮品"],
            "needs": ["日常饮用"],
            "information_status": "clear",
            "authority": "AI_CANDIDATE",
            "operating_context": "daily",
            "coverage": "subject",
        }
        a.update(changes)
        return a

    def choose(self, row=None, analysis=None, policy=None, owner=None):
        return decide(row or self.row, analysis if analysis is not None else self.analysis(row), self.catalog, policy if policy is not None else self.policy, owner=owner)

    def assert_rejected_or_observed(self, row, analysis):
        try:
            result = decide(row, analysis, self.catalog, self.policy)
        except ValueError:
            return
        self.assertEqual(result["decision"], "观察")

    def test_same_title_does_not_merge_distinct_source_records(self):
        first = source_record({"record_id": "sku:A", "title_original": "Taza"})
        second = source_record({"record_id": "sku:B", "title_original": "Taza"})
        self.assertNotEqual(first["record_id"], second["record_id"])
        self.assertEqual(first["title_original"], second["title_original"])

    def test_identity_is_required_but_supported_source_keys_are_accepted(self):
        with self.assertRaises(ValueError):
            source_record({"title_original": "Taza sin identidad"})
        for key in ["id", "SKU", "asin"]:
            with self.subTest(key=key):
                row = source_record({key: "fixture-identity", "title_original": "Taza"})
                self.assertTrue(row["record_id"])
                self.assertTrue(row["source_hash"])

    def test_source_change_invalidates_previous_analysis(self):
        updated = source_record({"record_id": self.row["record_id"], "title_original": "Taza de cerámica roja"})
        self.assertNotEqual(updated["source_hash"], self.row["source_hash"])
        with self.assertRaises(ValueError):
            validate_analysis(updated, self.analysis(), self.catalog)

    def test_fake_source_hash_and_nonliteral_subject_are_rejected(self):
        for change in [{"source_hash": "fabricated"}, {"subject_span": "microondas inexistente"}]:
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    validate_analysis(self.row, self.analysis(**change), self.catalog)

    def test_reference_must_be_real_and_have_literal_span(self):
        for change in [
            {"action_sku": "DOES_NOT_EXIST"},
            {"reference_span": "Texto ausente en el título Action"},
            {"action_sku": "", "relation": "same_type", "reference_span": ""},
        ]:
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    validate_analysis(self.row, self.analysis(**change), self.catalog)

    def test_ai_analysis_cannot_claim_human_authority(self):
        with self.assertRaises(ValueError):
            validate_analysis(self.row, self.analysis(authority="HUMAN"), self.catalog)

    def test_absent_ai_analysis_never_fabricates_understanding(self):
        result = decide(self.row, None, self.catalog, self.policy)
        self.assertEqual(result["decision"], "观察")
        self.assertEqual(result["understanding_status"], "NEEDS_SEMANTIC")
        self.assertFalse(result.get("reference"))

    def test_clear_daily_product_with_same_type_reference_can_be_retained(self):
        result = self.choose()
        self.assertEqual(result["decision"], "保留")
        self.assertTrue(result["reference"])
        self.assertTrue(result["reason_code"])

    def test_no_reference_does_not_become_exclusion(self):
        a = self.analysis(action_sku="", reference_span="", relation="none", scope="outside")
        result = self.choose(analysis=a)
        self.assertEqual(result["decision"], "观察")

    def test_clear_daily_small_machine_not_blocked_by_legacy_category(self):
        row = source_record({"record_id": "fixture:blender", "title_original": "Batidora de mano para cocina"})
        a = self.analysis(row, subject_span="Batidora de mano", subject_type="手持搅拌机", form="whole_machine", action_sku="TEST_BLENDER", reference_span="Batidora de mano", functions=["搅拌食材"], needs=["家庭备餐"], operating_context="daily", boundary_kind="SMALL_APPLIANCE_REVIEW")
        self.assertEqual(self.choose(row, a)["decision"], "保留")

    def test_understood_product_and_unknown_operating_scope_remain_distinct(self):
        result = self.choose(analysis=self.analysis(operating_context="specialist"))
        self.assertEqual(result["decision"], "观察")
        self.assertNotEqual(result["understanding_status"], "NEEDS_SEMANTIC")
        self.assertNotIn(result["understanding_status"], {"UNKNOWN", "INFORMATION_INSUFFICIENT"})

    def test_insufficient_information_cannot_be_retained(self):
        a = self.analysis(information_status="insufficient", form="unknown", operating_context="unknown")
        result = self.choose(analysis=a)
        self.assertEqual(result["decision"], "观察")
        self.assertNotEqual(result["understanding_status"], "NEEDS_SEMANTIC")

    def test_scope_claim_from_ai_is_not_published_exclusion_policy(self):
        a = self.analysis(scope="outside", decision="用不到", boundary_kind="MAJOR_APPLIANCE")
        result = self.choose(analysis=a)
        self.assertNotEqual(result["decision"], "用不到")
        policy = {"rules": [{"status": "CANDIDATE", "rule_id": "ai-only", "subject_types": ["陶瓷杯"], "forms": ["ordinary_good"], "decision": "用不到", "authority": "AI_CANDIDATE"}]}
        try:
            result = self.choose(analysis=a, policy=policy)
        except ValueError:
            return
        self.assertNotEqual(result["decision"], "用不到")

    def test_incomplete_publication_metadata_cannot_exclude(self):
        rule = {"status": "PUBLISHED", "rule_id": "unproven", "subject_types": ["陶瓷杯"], "forms": ["ordinary_good"], "decision": "用不到"}
        try:
            result = self.choose(policy={"rules": [rule]})
        except ValueError:
            return
        self.assertNotEqual(result["decision"], "用不到")

    def test_host_words_cannot_be_promoted_to_sold_whole_machine(self):
        fixtures = [
            ("Rejilla de ventilación para frigorífico", "frigorífico", "冰箱", "TEST_FRIDGE", "Frigorífico de mesa"),
            ("Válvula de agua para lavadora", "lavadora", "洗衣机", "TEST_WASHER", "Lavadora"),
            ("Caja de frutas apta para lavavajillas", "lavavajillas", "洗碗机", "TEST_DISHWASHER", "Lavavajillas"),
        ]
        for i, (title, span, subject, sku, refspan) in enumerate(fixtures):
            with self.subTest(title=title):
                row = source_record({"record_id": "fixture:host:%s" % i, "title_original": title})
                a = self.analysis(row, subject_span=span, subject_type=subject, form="whole_machine", action_sku=sku, reference_span=refspan, operating_context="daily")
                self.assert_rejected_or_observed(row, a)

    def test_correct_component_does_not_inherit_host_exclusion(self):
        row = source_record({"record_id": "fixture:grille", "title_original": "Rejilla de ventilación para frigorífico"})
        a = self.analysis(row, subject_span="Rejilla de ventilación", subject_type="通风格栅", form="host_component", action_sku="TEST_FRIDGE", reference_span="Frigorífico de mesa", relation="host_only", scope="outside", operating_context="unknown")
        self.assertEqual(self.choose(row, a)["decision"], "观察")

    def test_component_possessive_host_is_not_promoted_to_whole_machine(self):
        fixtures = [
            ("Válvula de entrada de agua de lavadora", "lavadora", "洗衣机", "TEST_WASHER", "Lavadora"),
            ("Rejilla del frigorífico", "frigorífico", "冰箱", "TEST_FRIDGE", "Frigorífico de mesa"),
        ]
        for i, (title, span, subject, sku, refspan) in enumerate(fixtures):
            with self.subTest(title=title):
                row = source_record({"record_id": "fixture:possessive-host:%s" % i, "title_original": title})
                a = self.analysis(row, subject_span=span, subject_type=subject, form="whole_machine", action_sku=sku, reference_span=refspan, operating_context="daily")
                self.assert_rejected_or_observed(row, a)

    def test_owner_whitespace_reviewer_cannot_confirm_selection(self):
        owner = {"record_id": self.row["record_id"], "source_hash": self.row["source_hash"], "decision": "用不到", "authority": "HUMAN", "reviewer": "   \t"}
        try:
            result = self.choose(owner=owner)
        except ValueError:
            return
        self.assertNotEqual(result["decision"], "用不到")
        self.assertFalse(result.get("human_confirmed"))

    def test_exact_bound_owner_choice_applies_only_to_that_record(self):
        owner = {"record_id": self.row["record_id"], "source_hash": self.row["source_hash"], "decision": "用不到", "authority": "HUMAN", "reviewer": "synthetic-test-owner", "evidence_reference": "fixture-only-not-real-feedback"}
        self.assertEqual(self.choose(owner=owner)["decision"], "用不到")
        other = source_record({"record_id": "fixture:amazon:OTHER", "title_original": self.row["title_original"]})
        try:
            result = self.choose(other, self.analysis(other), owner=owner)
        except ValueError:
            return
        self.assertNotEqual(result["decision"], "用不到")

    def test_owner_requires_human_reviewer_current_source_and_valid_decision(self):
        good = {"record_id": self.row["record_id"], "source_hash": self.row["source_hash"], "decision": "用不到", "authority": "HUMAN", "reviewer": "synthetic-test-owner"}
        changes = [{"authority": "AI_CANDIDATE"}, {"reviewer": ""}, {"source_hash": "stale-source"}, {"decision": "DELETE"}]
        for change in changes:
            with self.subTest(change=change):
                owner = dict(good, **change)
                try:
                    result = self.choose(owner=owner)
                except ValueError:
                    continue
                self.assertNotEqual(result["decision"], "用不到")
                self.assertIn(result["decision"], {"保留", "观察"})


if __name__ == "__main__":
    unittest.main()
