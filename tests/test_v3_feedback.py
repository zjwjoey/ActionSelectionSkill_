"""Temporary-database integration tests; every HUMAN fixture is SYNTHETIC.

No fixture represents actual owner feedback, measured accuracy or a real release.
Repository assets are read-only; all evidence, cases and database writes are temporary.
"""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime.v3.core import decide, digest, source_record
from runtime.v3.feedback import active_policy, impact, import_feedback, propose, publish, validate_rule
from runtime.v3.store import Store
from runtime.v3.workflow import asset_contract, filehash


class FakeCatalog:
    def __init__(self):
        self.by_sku = {
            "TEST_DRILL": {"sku": "TEST_DRILL", "name_es_original": "Taladro eléctrico", "source_row_id": "synthetic:drill"},
            "TEST_MUG": {"sku": "TEST_MUG", "name_es_original": "Taza de cerámica", "source_row_id": "synthetic:mug"},
        }
        self.semantics = {
            "TEST_DRILL": {"subject_type": "电钻", "functions": ["钻孔"], "needs": ["家庭维修"]},
            "TEST_MUG": {"subject_type": "陶瓷杯", "functions": ["盛装饮品"], "needs": ["日常饮用"]},
        }


class V3FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="v3_synthetic_feedback_")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.store = Store(self.folder / "synthetic.sqlite3")
        self.addCleanup(self.store.close)
        self.catalog = FakeCatalog()
        self.evidence_paths = {}
        for kind in ("support", "cases", "approval"):
            p = self.folder / (kind + "_SYNTHETIC.txt")
            p.write_text("SYNTHETIC TEST FIXTURE ONLY; NOT REAL HUMAN FEEDBACK: " + kind, encoding="utf-8")
            self.evidence_paths[kind] = p
        self.row = source_record({"record_id": "synthetic:drill", "title_original": "Taladro eléctrico doméstico", "source_version": "synthetic-v1"})
        self.mug = source_record({"record_id": "synthetic:mug", "title_original": "Taza de cerámica azul", "source_version": "synthetic-v1"})
        self.analysis = self.make_analysis(self.row)
        self.mug_analysis = self.make_analysis(self.mug, subject_span="Taza de cerámica", subject_type="陶瓷杯", form="ordinary_good", action_sku="TEST_MUG", reference_span="Taza de cerámica", functions=["盛装饮品"], needs=["日常饮用"])
        self.register(self.row, self.analysis)
        self.register(self.mug, self.mug_analysis)

    def make_analysis(self, row, **changes):
        a = {"source_hash": row["source_hash"], "subject_span": "Taladro eléctrico", "subject_type": "电钻", "form": "whole_machine", "relation": "same_type", "action_sku": "TEST_DRILL", "reference_span": "Taladro eléctrico", "reason": "合成夹具，只验证契约，不代表真实人工意见。", "functions": ["钻孔"], "needs": ["家庭维修"], "information_status": "clear", "authority": "AI_CANDIDATE", "operating_context": "daily", "coverage": "subject"}
        a.update(changes)
        return a

    def register(self, row, analysis=None):
        self.store.exact("v3_sources", {"id": row["record_id"], "hash": row["source_hash"]}, row)
        if analysis is not None:
            self.store.exact("v3_analyses", {"id": "synthetic-analysis-" + row["source_hash"]}, {"source_hash": row["source_hash"], "analysis": analysis, "fixture": "SYNTHETIC_ONLY"})
        self.store.db.commit()

    def evidence(self, kind):
        p = self.evidence_paths[kind]
        return {"evidence_reference": str(p), "evidence_sha256": filehash(p)}

    def feedback(self, **changes):
        f = {"feedback_id": "synthetic-support", "record_id": self.row["record_id"], "source_hash": self.row["source_hash"], "decision": "用不到", "authority": "HUMAN", "reviewer": "SYNTHETIC_TEST_ONLY", **self.evidence("support")}
        f.update(changes)
        return f

    def seed_support(self):
        return import_feedback(ROOT, self.store, [self.feedback()])

    def spec(self, **changes):
        s = {"subject_types": ["电钻"], "forms": ["whole_machine"], "operating_contexts": ["daily"], "support_feedback_ids": ["synthetic-support"], "decision": "用不到", "rationale": "SYNTHETIC TEST POLICY ONLY; not a real operating boundary."}
        s.update(changes)
        return s

    def candidate(self):
        self.seed_support()
        return propose(ROOT, self.store, self.spec())

    def cases(self, human=True):
        rows = []
        for row, a, expected in ((self.row, self.analysis, "用不到"), (self.mug, self.mug_analysis, "保留")):
            rows.append({"source": row, "analysis": a, "expected_decision": expected, "authority": "HUMAN" if human else "AI_CANDIDATE", "reviewer": "SYNTHETIC_TEST_ONLY" if human else "", **self.evidence("cases")})
        return rows

    def validate(self, rule, cases=None, name="cases.jsonl"):
        path = self.folder / name
        path.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in (self.cases() if cases is None else cases)), encoding="utf-8")
        return validate_rule(ROOT, self.store, rule["rule_id"], path, self.catalog)

    def approval(self, rule, **changes):
        a = {"authority": "HUMAN", "reviewer": "SYNTHETIC_TEST_ONLY", "rule_id": rule["rule_id"], "rule_hash": digest(rule), **self.evidence("approval")}
        a.update(changes)
        return a

    def released(self):
        rule = self.candidate()
        report = self.validate(rule)
        released = publish(ROOT, self.store, rule["rule_id"], report["validation_id"], self.approval(rule))
        return rule, report, released

    def test_feedback_replay_is_idempotent(self):
        self.assertEqual(self.seed_support(), {"accepted": 1, "inserted": 1})
        self.assertEqual(self.seed_support(), {"accepted": 1, "inserted": 0})
        self.assertEqual(len(self.store.all("v3_feedback")), 1)
        self.assertEqual(self.store.check(), {"integrity": "ok", "foreign_keys": 0})

    def test_feedback_rejects_stale_source_evidence_and_invalid_reviewer(self):
        stale = source_record({"record_id": self.row["record_id"], "title_original": self.row["title_original"], "source_version": "synthetic-stale"})
        bad = [({"source_hash": stale["source_hash"]}, "FEEDBACK_SOURCE_NOT_REGISTERED"), ({"evidence_sha256": "0" * 64}, "OWNER_EVIDENCE_MISSING_OR_CHANGED"), ({"reviewer": "   "}, "HUMAN_SELECTION_EVIDENCE_REQUIRED"), ({"reviewer": None}, "HUMAN_SELECTION_EVIDENCE_REQUIRED"), ({"authority": "AI_CANDIDATE"}, "HUMAN_SELECTION_EVIDENCE_REQUIRED")]
        for changes, message in bad:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ValueError, message):
                    import_feedback(ROOT, self.store, [self.feedback(**changes)])
        self.assertEqual(self.store.all("v3_feedback"), [])

    def test_conflicting_feedback_never_overwrites_stored_selection(self):
        self.seed_support()
        with self.assertRaisesRegex(ValueError, "CONFLICTING_FEEDBACK_REQUIRES_NEW_VERSION"):
            import_feedback(ROOT, self.store, [self.feedback(feedback_id="other", decision="保留")])
        self.assertEqual(self.store.get("v3_feedback", "synthetic-support")["decision"], "用不到")
        self.assertEqual(len(self.store.all("v3_feedback")), 1)

    def test_conflicting_feedback_batch_is_atomic(self):
        with self.assertRaisesRegex(ValueError, "CONFLICTING_FEEDBACK_BATCH"):
            import_feedback(ROOT, self.store, [self.feedback(), self.feedback(feedback_id="second", decision="保留")])
        self.assertEqual(self.store.all("v3_feedback"), [])

    def test_candidate_support_must_approve_target_decision(self):
        self.seed_support()
        with self.assertRaisesRegex(ValueError, "SUPPORT_DOES_NOT_APPROVE_TARGET_DECISION"):
            propose(ROOT, self.store, self.spec(decision="保留"))
        self.assertEqual(self.store.all("v3_rule_candidates"), [])

    def test_candidate_support_must_match_subject_form_and_context(self):
        self.seed_support()
        for change in ({"subject_types": ["陶瓷杯"]}, {"forms": ["ordinary_good"]}, {"operating_contexts": ["specialist"]}):
            with self.subTest(change=change):
                with self.assertRaisesRegex(ValueError, "SUPPORT_SUBJECT_NOT_IN_CANDIDATE_SCOPE"):
                    propose(ROOT, self.store, self.spec(**change))
        self.assertEqual(self.store.all("v3_rule_candidates"), [])

    def test_validation_requires_positive_and_counterexample(self):
        rule = self.candidate()
        for index in (0, 1):
            with self.subTest(case=index):
                report = self.validate(rule, [self.cases()[index]], "one_case_%s.jsonl" % index)
                self.assertEqual(report["status"], "FAIL")
                with self.assertRaisesRegex(ValueError, "PASSED_HUMAN_CASES_AND_COUNTEREXAMPLES_REQUIRED"):
                    publish(ROOT, self.store, rule["rule_id"], report["validation_id"], self.approval(rule))
        self.assertEqual(self.store.all("v3_rule_releases"), [])

    def test_ai_targets_cannot_publish_even_when_candidate_checks_pass(self):
        rule = self.candidate()
        report = self.validate(rule, self.cases(human=False))
        self.assertEqual(report["status"], "PASS")
        self.assertFalse(report["case_targets_human"])
        with self.assertRaisesRegex(ValueError, "PASSED_HUMAN_CASES_AND_COUNTEREXAMPLES_REQUIRED"):
            publish(ROOT, self.store, rule["rule_id"], report["validation_id"], self.approval(rule))
        self.assertEqual(active_policy(ROOT, self.store)["rules"], [])

    def test_synthetic_human_release_and_replay_are_verified(self):
        rule, report, released = self.released()
        self.assertEqual(report["positive_cases"], 1)
        self.assertEqual(report["counterexamples"], 1)
        self.assertEqual(publish(ROOT, self.store, rule["rule_id"], report["validation_id"], self.approval(rule)), released)
        policy = active_policy(ROOT, self.store)
        self.assertEqual(len(policy["rules"]), 1)
        self.assertEqual(decide(self.row, self.analysis, self.catalog, policy)["decision"], "用不到")
        self.assertEqual(decide(self.mug, self.mug_analysis, self.catalog, policy)["decision"], "保留")

    def test_publication_requires_bound_approval_and_real_reviewer(self):
        rule = self.candidate()
        report = self.validate(rule)
        for change, error in (({"rule_hash": "fake"}, "APPROVAL_RULE_BINDING_REQUIRED"), ({"rule_id": "other"}, "APPROVAL_RULE_BINDING_REQUIRED"), ({"reviewer": "  "}, "HUMAN_RELEASE_APPROVAL_REQUIRED"), ({"evidence_sha256": "fake"}, "OWNER_EVIDENCE_MISSING_OR_CHANGED")):
            with self.subTest(change=change):
                with self.assertRaisesRegex(ValueError, error):
                    publish(ROOT, self.store, rule["rule_id"], report["validation_id"], self.approval(rule, **change))
        self.assertEqual(self.store.all("v3_rule_releases"), [])

    def test_changed_validation_file_blocks_publish_and_active_policy(self):
        rule, report, _ = self.released()
        path = Path(report["cases_path"])
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "VALIDATION_CASES_CHANGED"):
            publish(ROOT, self.store, rule["rule_id"], report["validation_id"], self.approval(rule))
        with self.assertRaisesRegex(ValueError, "RELEASE_CASES_CHANGED"):
            active_policy(ROOT, self.store)

    def test_changed_support_case_or_approval_evidence_revokes_active_policy(self):
        self.released()
        for kind, path in self.evidence_paths.items():
            with self.subTest(evidence=kind):
                original = path.read_bytes()
                try:
                    path.write_bytes(original + b"\nSYNTHETIC MUTATION")
                    with self.assertRaisesRegex(ValueError, "OWNER_EVIDENCE_MISSING_OR_CHANGED"):
                        active_policy(ROOT, self.store)
                finally:
                    path.write_bytes(original)
        self.assertEqual(len(active_policy(ROOT, self.store)["rules"]), 1)

    def test_execution_contract_drift_blocks_publish_and_existing_release(self):
        rule, report, _ = self.released()
        changed = dict(asset_contract(ROOT), synthetic_execution_contract_drift="changed")
        # Mock drift instead of changing any real code, assets or snapshots.
        with patch("runtime.v3.feedback.asset_contract", return_value=changed):
            with self.assertRaisesRegex(ValueError, "VALIDATION_EXECUTION_CONTRACT_CHANGED"):
                publish(ROOT, self.store, rule["rule_id"], report["validation_id"], self.approval(rule))
            with self.assertRaisesRegex(ValueError, "RELEASE_EXECUTION_CONTRACT_CHANGED"):
                active_policy(ROOT, self.store)

    def test_impact_only_selects_published_type_form_context_and_tracks_unresolved(self):
        rule, _, released = self.released()
        sources = []
        semantics = []
        variants = ({}, {"form": "ordinary_good"}, {"operating_context": "specialist"}, {"subject_type": "合成不同类型"})
        for i, changes in enumerate(variants):
            row = source_record({"record_id": "synthetic:impact:%s" % i, "title_original": self.row["title_original"]})
            a = self.make_analysis(row, **changes)
            self.register(row, a)
            sources.append(row)
            semantics.append(a)
        unresolved = source_record({"record_id": "synthetic:unresolved", "title_original": "Producto sin análisis"})
        self.register(unresolved)
        sources.append(unresolved)
        run_id = "synthetic-run"
        self.store.exact("v3_runs", {"id": run_id}, {"sources": sources, "fixture": "SYNTHETIC_ONLY"})
        for row, a in zip(sources, semantics):
            result = decide(row, a, self.catalog, {})
            self.store.exact("v3_results", {"run_id": run_id, "record_id": row["record_id"]}, result)
        self.store.db.commit()
        with self.assertRaisesRegex(ValueError, "PUBLISHED_RELEASE_REQUIRED"):
            impact(ROOT, self.store, rule["rule_id"], run_id)
        report = impact(ROOT, self.store, released["release_id"], run_id)
        self.assertEqual(report["affected_records"], 1)
        self.assertEqual(report["unaffected_records"], 3)
        self.assertEqual(report["unresolved_records"], 1)
        self.assertEqual([r["record_id"] for r in report["sources"]], [sources[0]["record_id"]])
        self.assertEqual(self.store.check(), {"integrity": "ok", "foreign_keys": 0})


if __name__ == "__main__":
    unittest.main()
