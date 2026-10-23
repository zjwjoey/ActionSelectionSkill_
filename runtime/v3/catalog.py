"""Read-only Action reference catalog with source-bound semantic candidates.

Loading the catalog uses only the standard library. The frozen V2 retrieval
index and its optional numerical dependencies are loaded on the first search.
Retrieval rank, canonical type and shared needs are NOT selection decisions,
verified product facts, or proof that two products are interchangeable.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any
import unicodedata


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _keyed_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8-sig") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            sku = str(row.get("sku", "")).strip()
            if not sku or sku in records:
                raise ValueError(f"CATALOG_INVALID_OR_DUPLICATE_SKU:{path.name}:{number}:{sku}")
            records[sku] = row
    return records


def _normal(text: str) -> str:
    """Frozen V2 lexical normalization, used for search only."""
    return re.sub(
        r"\s+", " ",
        "".join(c for c in unicodedata.normalize("NFKD", text.lower())
                if not unicodedata.combining(c)),
    ).strip()


class Catalog:
    """Load the eligible Action corpus from a portable package root.

    ``by_sku`` and ``semantics`` retain the source dictionaries unchanged.
    ``type_entries`` retains one entry for every original type, including
    singleton types. ``family`` is an explicit candidate type bucket, not a
    broad need bucket or an approved retail taxonomy.
    """

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        asset_root = self.root / "assets"
        semantic_root = asset_root / "action_semantics"
        self.by_sku = _keyed_jsonl(asset_root / "action_reference10037.jsonl")
        self.semantics = _keyed_jsonl(semantic_root / "results.jsonl")
        if set(self.by_sku) != set(self.semantics):
            raise ValueError("CATALOG_SEMANTIC_REFERENCE_SKU_SET_MISMATCH")
        for sku, semantic in self.semantics.items():
            reference = self.by_sku[sku]
            for field in ("name_es_original", "source_row_id"):
                if not reference.get(field) or reference[field] != semantic.get(field):
                    raise ValueError(f"CATALOG_SEMANTIC_SOURCE_MISMATCH:{sku}:{field}")

        self.product_type_library = _json(semantic_root / "product_type_library.json")
        self.related_need_groups = _json(semantic_root / "related_need_groups.json")
        alias_path = self.root / "rules" / "v3_type_aliases.json"
        alias_document = _json(alias_path) if alias_path.exists() else {
            "version": "identity-only", "aliases": []
        }
        self.alias_version = alias_document["version"]
        aliases: dict[str, dict[str, Any]] = {}
        for alias in alias_document.get("aliases", []):
            original = alias.get("original_type")
            canonical = alias.get("canonical_type")
            if not isinstance(original, str) or not original or not isinstance(canonical, str) or not canonical or original in aliases:
                raise ValueError("CATALOG_INVALID_OR_DUPLICATE_TYPE_ALIAS")
            attributes = alias.get("attributes", [])
            if not isinstance(attributes, list):
                raise ValueError(f"CATALOG_INVALID_TYPE_ATTRIBUTES:{original}")
            for attribute in attributes:
                if (not isinstance(attribute, dict)
                        or not isinstance(attribute.get("evidence"), str)
                        or not attribute["evidence"]
                        or attribute["evidence"] not in original
                        or attribute.get("source") != "original_type"):
                    raise ValueError(f"CATALOG_UNSUPPORTED_TYPE_ATTRIBUTE:{original}")
            aliases[original] = alias

        self.type_entries: list[dict[str, Any]] = []
        self._type_by_original: dict[str, dict[str, Any]] = {}
        observed_support: dict[str, set[str]] = defaultdict(set)
        for sku, semantic in self.semantics.items():
            original = semantic.get("product_type_candidate")
            if original:
                observed_support[original].add(sku)
        for original_entry in self.product_type_library["types"]:
            original = original_entry["type"]
            if original in self._type_by_original:
                raise ValueError(f"CATALOG_DUPLICATE_ORIGINAL_TYPE:{original}")
            support = list(original_entry["supporting_skus"])
            if (len(support) != len(set(support))
                    or set(support) != observed_support.get(original, set())
                    or original_entry.get("sku_count", len(support)) != len(support)):
                raise ValueError(f"CATALOG_TYPE_SUPPORT_MISMATCH:{original}")
            alias = aliases.get(original, {})
            canonical = alias.get("canonical_type", original)
            entry = {
                "original_type": original,
                "canonical_type": canonical,
                "family": "CANDIDATE_TYPE::" + canonical,
                "attributes": deepcopy(alias.get("attributes", [])),
                "supporting_skus": support,
                "authority": "AI_CANDIDATE_NOT_HUMAN_TAXONOMY",
                "mapping_status": "EXPLICIT_ALIAS" if original in aliases else "ORIGINAL_TYPE_RETAINED",
                "mapping_reason": alias.get("reason", "原候选类型保留；未依据共同需求进行合并"),
            }
            self.type_entries.append(entry)
            self._type_by_original[original] = entry
        if set(self._type_by_original) != set(observed_support):
            raise ValueError("CATALOG_TYPE_LIBRARY_INCOMPLETE")
        self._unused_aliases = sorted(set(aliases) - set(observed_support))

        self._needs: dict[str, list[str]] = {sku: [] for sku in self.by_sku}
        self._need_evidence: dict[str, list[dict[str, str]]] = {sku: [] for sku in self.by_sku}
        for sku, semantic in self.semantics.items():
            for hypothesis in semantic.get("use_need_hypotheses", []):
                need = hypothesis.get("consumer_need")
                if isinstance(need, str) and need:
                    self._add_need(sku, need, "SEMANTIC_RECORD_HYPOTHESIS")
        for group in self.related_need_groups:
            need = group["shared_need_hypothesis"]
            if not isinstance(need, str) or not need:
                raise ValueError("CATALOG_INVALID_RELATED_NEED")
            for member_type in group["types"]:
                for sku in member_type["supporting_skus"]:
                    if (sku not in self.semantics
                            or self.semantics[sku].get("product_type_candidate") != member_type["type"]):
                        raise ValueError(f"CATALOG_RELATED_NEED_SOURCE_MISMATCH:{sku}")
                    self._add_need(sku, need, "RELATED_NEED_GROUP_HYPOTHESIS")

        self._model: dict[str, Any] | None = None
        self._numerics: Any = None
        self._normalize_vectors: Any = None
        self._stops: set[str] = set()
        self._aliases: dict[str, str] = {}
        self._head_vocabulary: set[str] = set()

    def _add_need(self, sku: str, need: str, source: str) -> None:
        if need not in self._needs[sku]:
            self._needs[sku].append(need)
        evidence = {"need": need, "source": source, "authority": "CANDIDATE_HYPOTHESIS_NOT_LITERAL_FACT"}
        if evidence not in self._need_evidence[sku]:
            self._need_evidence[sku].append(evidence)

    def _load_retriever(self) -> None:
        if self._model is not None:
            return
        directory = self.root / "runtime" / "v2" / "runs" / "action_assortment_v2_20261022"
        index_path = directory / "retrieval_index.joblib"
        manifest = _json(directory / "method_manifest.json")
        # Joblib is executable serialization: load only the packaged frozen
        # index after its manifest binding has been verified, never a query path.
        hasher = hashlib.sha256()
        with index_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        digest = hasher.hexdigest()
        if digest != manifest.get("index_sha256"):
            raise ValueError("CATALOG_FROZEN_INDEX_HASH_MISMATCH")
        import joblib
        import numpy as np
        from sklearn.preprocessing import normalize

        model = joblib.load(index_path)
        indexed: set[str] = set()
        for reference in model["references"]:
            sku = str(reference.get("sku", ""))
            if sku in indexed or sku not in self.by_sku:
                raise ValueError(f"CATALOG_INDEX_REFERENCE_MISMATCH:{sku}")
            indexed.add(sku)
            if any(reference.get(key) != self.by_sku[sku].get(key)
                   for key in ("name_es_original", "source_row_id")):
                raise ValueError(f"CATALOG_INDEX_SOURCE_MISMATCH:{sku}")
        if indexed != set(self.by_sku):
            raise ValueError("CATALOG_INDEX_SKU_SET_MISMATCH")
        self._stops = set(model["policy"]["stopwords"].split())
        self._aliases = model["policy"]["head_aliases"]
        self._head_vocabulary = set(model["head_vocabulary"])
        self._numerics, self._normalize_vectors = np, normalize
        self._model = model

    def _words(self, title: str) -> list[str]:
        words = []
        for word in re.findall(r"[a-z][a-z0-9]*", _normal(title)):
            if word in self._stops:
                continue
            word = self._aliases.get(word, word)
            if len(word) > 5 and word.endswith("es") and word[-3] in "rlndz":
                word = word[:-2]
            elif len(word) > 4 and word.endswith("s"):
                word = word[:-1]
            words.append(self._aliases.get(word, word))
        return words

    def retrieve(self, title: str, limit: int = 8) -> list[dict[str, Any]]:
        """Rank frozen reference candidates; perform no selection inference."""
        if not isinstance(title, str):
            raise TypeError("title must be a string")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError("limit must be a nonnegative integer")
        if not title.strip() or limit == 0:
            return []
        self._load_retriever()
        model = self._model
        assert model is not None
        np = self._numerics
        word = model["word"].transform([" ".join(self._words(title))])
        char = model["char"].transform([_normal(title)])
        latent = self._normalize_vectors(model["svd"].transform(word))
        scores = (
            .46 * (word @ model["word_matrix"].T).toarray()[0]
            + .20 * (char @ model["char_matrix"].T).toarray()[0]
            + .24 * (latent @ model["latent_matrix"].T)[0]
        )
        prefix = re.split(r"\b(?:para|con|sin|compatible|incluye|incluido|ideal|adecuado|como)\b|[,;|]", _normal(title), maxsplit=1)[0]
        head = next((w for w in self._words(prefix)[:5] if w in self._head_vocabulary), "")
        if head:
            scores += .10 * np.array([r["feature"]["head"] == head for r in model["references"]])
        # Stable ordering makes equal-scoring results reproducible; no arbitrary
        # zero-score results are returned for inputs absent from the vocabulary.
        selected = np.argsort(-scores, kind="stable")[:min(limit, len(scores))]
        output = []
        for index in selected:
            if float(scores[index]) <= 0:
                continue
            sku = str(model["references"][int(index)]["sku"])
            reference, semantic = self.by_sku[sku], self.semantics[sku]
            original = semantic.get("product_type_candidate")
            entry = self._type_by_original.get(original, {})
            output.append({
                "sku": sku,
                "name_es_original": reference["name_es_original"],
                "source_row_id": reference["source_row_id"],
                "product_type_candidate": original,
                "canonical_type": entry.get("canonical_type"),
                "family": entry.get("family", "UNCLASSIFIED_CANDIDATE"),
                "attributes": deepcopy(entry.get("attributes", [])),
                "needs": list(self._needs[sku]),
                "need_evidence": deepcopy(self._need_evidence[sku]),
                "semantic_status": semantic["status"],
                "retrieval_score": float(scores[index]),
                "authority": "CANDIDATE_RETRIEVAL_NOT_SELECTION_DECISION",
                "same_type_confirmed": False,
            })
        return output

    def describe(self) -> dict[str, Any]:
        """Report coverage and provenance, never self-estimated accuracy."""
        canonical = Counter(entry["canonical_type"] for entry in self.type_entries)
        return {
            "reference_count": len(self.by_sku),
            "semantic_count": len(self.semantics),
            "source_binding": "SKU_TITLE_SOURCE_ROW_MATCH",
            "semantic_status_counts": dict(Counter(s["status"] for s in self.semantics.values())),
            "original_type_count": len(self.type_entries),
            "canonical_type_count": len(canonical),
            "alias_applied_count": sum(e["mapping_status"] == "EXPLICIT_ALIAS" for e in self.type_entries),
            "canonical_groups_with_multiple_original_types": sum(count > 1 for count in canonical.values()),
            "singleton_original_type_count": sum(len(e["supporting_skus"]) == 1 for e in self.type_entries),
            "type_entries_with_literal_attributes": sum(bool(e["attributes"]) for e in self.type_entries),
            "sku_with_type_candidate": sum(bool(s.get("product_type_candidate")) for s in self.semantics.values()),
            "sku_with_need_hypotheses": sum(bool(needs) for needs in self._needs.values()),
            "related_need_group_count": len(self.related_need_groups),
            "alias_version": self.alias_version,
            "unused_aliases": list(self._unused_aliases),
            "family_authority": "CANDIDATE_TYPE_BUCKET_NOT_CONFIRMED_TAXONOMY",
            "need_authority": "CANDIDATE_HYPOTHESIS_NOT_LITERAL_FACT",
            "need_based_type_merges": 0,
            "human_confirmed_semantic_records": sum(s.get("human_confirmed") is True for s in self.semantics.values()),
            "retrieval_index_loaded": self._model is not None,
            "retrieval_is_selection": False,
        }
