"""Frozen-corpus Catalog contracts; no production or learning-data writes."""

from collections import defaultdict
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.v3 import catalog as catalog_module
from runtime.v3.catalog import Catalog


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.asset_paths = [
            ROOT / "assets/action_reference10037.jsonl",
            ROOT / "assets/action_semantics/results.jsonl",
            ROOT / "assets/action_semantics/product_type_library.json",
            ROOT / "assets/action_semantics/related_need_groups.json",
        ]
        cls.hashes_before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in cls.asset_paths
        }
        cls.catalog = Catalog(ROOT)
        cls.by_type = {
            entry["original_type"]: entry for entry in cls.catalog.type_entries
        }

    @classmethod
    def tearDownClass(cls):
        hashes_after = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in cls.asset_paths
        }
        if hashes_after != cls.hashes_before:
            raise AssertionError("Frozen catalog input assets changed during tests")

    def test_all_10037_sources_bind_to_same_title_and_row(self):
        catalog = self.catalog
        self.assertEqual(len(catalog.by_sku), 10037)
        self.assertEqual(set(catalog.by_sku), set(catalog.semantics))
        for sku, reference in catalog.by_sku.items():
            with self.subTest(sku=sku):
                semantic = catalog.semantics[sku]
                self.assertEqual(reference["name_es_original"], semantic["name_es_original"])
                self.assertEqual(reference["source_row_id"], semantic["source_row_id"])

    def test_all_1918_original_types_and_supports_are_traceable(self):
        expected = defaultdict(set)
        for sku, semantic in self.catalog.semantics.items():
            if semantic.get("product_type_candidate"):
                expected[semantic["product_type_candidate"]].add(sku)
        self.assertEqual(len(self.catalog.type_entries), 1918)
        self.assertEqual(set(self.by_type), set(expected))
        for original, entry in self.by_type.items():
            with self.subTest(original_type=original):
                self.assertEqual(set(entry["supporting_skus"]), expected[original])
                self.assertEqual(len(entry["supporting_skus"]), len(set(entry["supporting_skus"])))
                self.assertTrue(entry["canonical_type"])
                self.assertTrue(entry["family"].startswith("CANDIDATE_TYPE::"))
                self.assertEqual(entry["authority"], "AI_CANDIDATE_NOT_HUMAN_TAXONOMY")

    def test_singleton_types_not_forcibly_merged(self):
        singletons = [e for e in self.catalog.type_entries if len(e["supporting_skus"]) == 1]
        self.assertEqual(len(singletons), 997)
        for entry in singletons:
            if entry["mapping_status"] == "ORIGINAL_TYPE_RETAINED":
                self.assertEqual(entry["original_type"], entry["canonical_type"])
        self.assertEqual(self.by_type["跳房子游戏用品"]["canonical_type"], "跳房子游戏用品")

    def test_only_explicit_aliases_change_type_labels(self):
        rules = json.loads((ROOT / "rules/v3_type_aliases.json").read_text(encoding="utf-8"))
        aliases = {entry["original_type"]: entry for entry in rules["aliases"]}
        for original, entry in self.by_type.items():
            with self.subTest(original_type=original):
                self.assertEqual(entry["canonical_type"], aliases.get(original, {}).get("canonical_type", original))
        self.assertEqual(self.catalog.describe()["alias_applied_count"], 10)
        self.assertEqual(self.catalog.describe()["canonical_type_count"], 1912)
        self.assertEqual(self.catalog.describe()["unused_aliases"], [])

    def test_modifier_split_keeps_specification_brand_and_subject(self):
        expected = {
            "20denier及膝袜": ("及膝袜", "20denier"),
            "XL上菜板": ("上菜板", "XL"),
            "LEGO Technic推土机模型": ("推土机模型", "LEGO Technic"),
            "Turbo Fire飞镖发射玩具": ("飞镖发射玩具", "Turbo Fire"),
            "Twix饮料": ("饮料", "Twix"),
        }
        for original, (canonical, modifier) in expected.items():
            with self.subTest(original_type=original):
                entry = self.by_type[original]
                self.assertEqual(entry["canonical_type"], canonical)
                self.assertEqual(entry["attributes"][0]["value"], modifier)
                self.assertIn(entry["attributes"][0]["evidence"], original)
                self.assertEqual(entry["attributes"][0]["source"], "original_type")

    def test_technical_and_uncertain_type_qualifiers_are_not_stripped(self):
        for original in ("HDMI连接线", "LED灯带", "USB-C手机充电数据线", "3D画笔入门套装", "模具（用途待核实）"):
            with self.subTest(original_type=original):
                self.assertEqual(self.by_type[original]["canonical_type"], original)

    def test_shared_need_is_not_same_type_or_family(self):
        group = next(g for g in self.catalog.related_need_groups if g["shared_need_hypothesis"] == "上妆操作")
        members = {member["type"] for member in group["types"]}
        self.assertIn("化妆刷", members)
        self.assertIn("化妆海绵", members)
        brush, sponge = self.by_type["化妆刷"], self.by_type["化妆海绵"]
        self.assertNotEqual(brush["canonical_type"], sponge["canonical_type"])
        self.assertNotEqual(brush["family"], sponge["family"])
        self.assertEqual(self.catalog.describe()["need_based_type_merges"], 0)

    def test_needs_have_candidate_authority_and_source_support(self):
        allowed = defaultdict(set)
        for sku, semantic in self.catalog.semantics.items():
            for hypothesis in semantic.get("use_need_hypotheses", []):
                if hypothesis.get("consumer_need"):
                    allowed[sku].add(hypothesis["consumer_need"])
        for group in self.catalog.related_need_groups:
            for member in group["types"]:
                for sku in member["supporting_skus"]:
                    allowed[sku].add(group["shared_need_hypothesis"])
        for sku in self.catalog.by_sku:
            self.assertEqual(set(self.catalog._needs[sku]), allowed[sku])
            self.assertTrue(all(e["authority"] == "CANDIDATE_HYPOTHESIS_NOT_LITERAL_FACT"
                                for e in self.catalog._need_evidence[sku]))
        self.assertEqual(self.catalog.describe()["sku_with_need_hypotheses"], 8338)

    def test_semantic_title_and_source_row_mismatch_fail_closed(self):
        sku = next(iter(self.catalog.semantics))
        for field in ("name_es_original", "source_row_id"):
            bad = dict(self.catalog.semantics)
            bad[sku] = dict(bad[sku], **{field: "wrong binding"})
            with self.subTest(field=field), patch.object(
                catalog_module, "_keyed_jsonl",
                side_effect=lambda path: bad if path.name == "results.jsonl" else self.catalog.by_sku,
            ):
                with self.assertRaisesRegex(ValueError, "CATALOG_SEMANTIC_SOURCE_MISMATCH"):
                    Catalog(ROOT)

    def test_semantic_sku_set_mismatch_fails_closed(self):
        bad = dict(self.catalog.semantics)
        bad.pop(next(iter(bad)))
        with patch.object(catalog_module, "_keyed_jsonl",
                          side_effect=lambda path: bad if path.name == "results.jsonl" else self.catalog.by_sku):
            with self.assertRaisesRegex(ValueError, "CATALOG_SEMANTIC_REFERENCE_SKU_SET_MISMATCH"):
                Catalog(ROOT)

    def test_type_support_mismatch_fails_closed(self):
        bad = deepcopy(self.catalog.product_type_library)
        bad["types"][0]["supporting_skus"] = []
        original_reader = catalog_module._json
        with patch.object(catalog_module, "_json",
                          side_effect=lambda path: bad if path.name == "product_type_library.json" else original_reader(path)):
            with self.assertRaisesRegex(ValueError, "CATALOG_TYPE_SUPPORT_MISMATCH"):
                Catalog(ROOT)

    def test_need_group_wrong_type_binding_fails_closed(self):
        bad = deepcopy(self.catalog.related_need_groups)
        bad[0]["types"][0]["type"] = "different product type"
        original_reader = catalog_module._json
        with patch.object(catalog_module, "_json",
                          side_effect=lambda path: bad if path.name == "related_need_groups.json" else original_reader(path)):
            with self.assertRaisesRegex(ValueError, "CATALOG_RELATED_NEED_SOURCE_MISMATCH"):
                Catalog(ROOT)

    def test_unfounded_modifier_attribute_fails_closed(self):
        original_reader = catalog_module._json
        bad = original_reader(ROOT / "rules/v3_type_aliases.json")
        bad["aliases"][0]["attributes"] = [{"value": "invented", "evidence": "invented", "source": "original_type"}]
        with patch.object(catalog_module, "_json",
                          side_effect=lambda path: bad if path.name == "v3_type_aliases.json" else original_reader(path)):
            with self.assertRaisesRegex(ValueError, "CATALOG_UNSUPPORTED_TYPE_ATTRIBUTE"):
                Catalog(ROOT)

    def test_duplicate_sku_rejected(self):
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".jsonl", delete=False) as handle:
            path = Path(handle.name).resolve()
            handle.write('{"sku":"duplicate"}\n{"sku":"duplicate"}\n')
        try:
            with self.assertRaisesRegex(ValueError, "CATALOG_INVALID_OR_DUPLICATE_SKU"):
                catalog_module._keyed_jsonl(path)
        finally:
            path.unlink()

    def test_constructor_portable_outside_cwd_and_standard_library_only(self):
        code = (
            "import sys; from pathlib import Path; "
            "sys.path.insert(0,sys.argv[1]); "
            "from runtime.v3.catalog import Catalog; c=Catalog(Path(sys.argv[1])); "
            "assert len(c.by_sku)==10037; assert c._model is None; "
            "assert not any(m in sys.modules for m in ('numpy','sklearn','joblib'))"
        )
        completed = subprocess.run(
            [sys.executable, "-c", code, str(ROOT)],
            cwd=Path(sys.executable).resolve().parent,
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_empty_queries_and_invalid_limits_do_not_load_retriever(self):
        with patch.object(self.catalog, "_load_retriever", side_effect=AssertionError("should not load")):
            self.assertEqual(self.catalog.retrieve(""), [])
            self.assertEqual(self.catalog.retrieve("   "), [])
            self.assertEqual(self.catalog.retrieve("Paño", 0), [])
            for limit in (-1, True, 1.5):
                with self.assertRaisesRegex(ValueError, "nonnegative integer"):
                    self.catalog.retrieve("Paño", limit)
            with self.assertRaises(TypeError):
                self.catalog.retrieve(None)

    def test_frozen_asset_hashes_match_package_manifest(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        for path in self.asset_paths:
            key = path.relative_to(ROOT).as_posix()
            self.assertEqual(self.hashes_before[path], manifest["files"][key]["sha256"])

    @unittest.skipUnless(
        all(importlib.util.find_spec(name) is not None for name in ("numpy", "sklearn", "joblib")),
        "Frozen-index numerical dependencies are optional for catalog data loading",
    )
    def test_real_retrieval_joins_semantics_without_claiming_same_type(self):
        rows = self.catalog.retrieve("Paños de microfibra Spargo", limit=8)
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[0]["name_es_original"], "Paños de microfibra Spargo")
        required = {"sku", "name_es_original", "source_row_id", "product_type_candidate",
                    "canonical_type", "family", "needs", "semantic_status"}
        for row in rows:
            with self.subTest(sku=row["sku"]):
                self.assertTrue(required.issubset(row))
                reference = self.catalog.by_sku[row["sku"]]
                semantic = self.catalog.semantics[row["sku"]]
                self.assertEqual(row["source_row_id"], reference["source_row_id"])
                self.assertEqual(row["product_type_candidate"], semantic["product_type_candidate"])
                self.assertEqual(row["semantic_status"], semantic["status"])
                self.assertIsInstance(row["needs"], list)
                self.assertFalse(row["same_type_confirmed"])
                self.assertEqual(row["authority"], "CANDIDATE_RETRIEVAL_NOT_SELECTION_DECISION")
                self.assertNotIn("decision", row)
        self.assertIn("表面擦拭", rows[0]["needs"])
        self.assertTrue(self.catalog.describe()["retrieval_index_loaded"])


if __name__ == "__main__":
    unittest.main()
