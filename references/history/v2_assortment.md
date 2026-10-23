# V2 assortment research workflow

## Files and current scope

Project `F:/ActionSelectionSkill`. Current workspace `v2/`. Current run `v2/runs/action_assortment_v2_20261022/`.

Read `final_manifest.json`, `V2_执行报告.md` and `data_safety_reconciliation.json` after delivery. The policy is `assortment-v2.2-experimental`, frozen in `frozen_policy.json` and bound by `method_manifest.json` / `final_trial_protocol.json`.

Current Action inventory:10,121 distinct SKUs.10,037 titles enter the index;34 source-language anomalies and the original50 sealed holdout are isolated.5,508 indexed titles have recognizable task cues; the rest still participate in lexical/latent retrieval without invented purpose labels. A head token is a surface candidate, not a validated product taxonomy. Existing5,000 learning proposals stay intact.

Owner selected the20,018-group snapshot at `F:/AmazonESBestseller/交付文件/20261022/snapshot20000_csv_170130_27fb/2万快照_保守去重汇总_20018组.csv`. Its `product_title_raw`, `amazon_category_l1`, `target_review_group`, `normalized_product_url` and logical record ordinal are preserved.17,142 rows have L1;2,876 remain blank. Do not infer a category from a URL. Original row fields are retained in the source and `amazon_raw_row_mapping.jsonl`; all record identities survive.

## Commands

Use `F:/ActionSKUTracker/.venv/Scripts/python.exe` read-only for NumPy/SciPy/scikit-learn/joblib/threadpoolctl/psutil; bundled artifact runtime for XLSX authoring. No new dependency installation or model download was needed.

```powershell
$selectionPython='F:/ActionSKUTracker/.venv/Scripts/python.exe'
& $selectionPython v2/run_bulk.py
& $selectionPython v2/evaluation.py
# Import only a genuinely completed, real-human, bound review CSV:
& $selectionPython v2/evaluation.py --human-csv <review-file.csv>
```

`run_bulk.py` checks frozen fingerprints, then resumes/returns ALREADY_COMPLETED; it does not overwrite the first completion summary. `assortment.py screen --input <subset.jsonl> --label <new-label>` can process a source-bound subset in the same run; identical content/version uses the cache. Changed methods belong in a new immutable run. Current same-file resume is verified; cross-snapshot semantic-content caching is not implemented and must not be claimed.

Do not rerun `p0_inventory.py`, `archive_prototype.py`, `freeze_final_candidate.py` or `bind_and_reserve.py` as a routine resume. Those are this run's create-once preparation/migration evidence. Rebuilding the index in place is rejected. A future new source/run requires a new explicit run configuration and manifests; current workspace paths are fixed for this audited run.

## Method

1. Word TF-IDF/bigrams, character ngrams and128-dimensional SVD fitted only to eligible Action titles recall20 candidates.
2. Specific title phrase, consumer-task relation, context conflicts and dependency cues rerank real references. Shared broad nouns do not establish same type; no match never causes LOW automatically.
3. The experimental policy assigns four states and uncertainty notes. HIGH is not a probability, purchasing recommendation or human-validated decision.

Unsupervised co-occurrence is limited with synonyms, unseen nouns, negation, long marketing titles and physical forms. Source categories are not used as a decisive score in this implementation. Complete furniture and dedicated parts are research candidates, not discarded.

## Review and scheme boundaries

Two technical500 batches were exposed during bug diagnosis and are development evidence. Do not call them independent accuracy tests.200 later cases were selected without V2 outcomes, excluding prior exact/near identities;120 random and80 difficult cases remain separate.

The anonymous workbook randomizes method-side identity for each record. It removes identifying wording in the presentation only, preserving original method reasons and mapping in audit files. Keep `private/arm_mapping.json` private until primary review is complete. Complete primary judgments first, reference relevance second.

A is a deterministic general-purpose proxy, not an ordinary AI. B replays frozen V10 rules with the original2,000 candidates, not the complete prior AI reasoning. C is V2. Program differences cannot establish superiority over independent ordinary AI/full-context Skill. Real independent AI arms remain a future capability experiment.

Feedback CSV requires `record_id`, `expected_C_hash`, `human_target`, `human_reason`, and `human_reviewer`. Human target codes are the four states. Existing AI review files are not human feedback. With no targets, `evaluation_pending_human.json` keeps formal metrics null. Reference relevance needs separately adjudicated reference labels; real source identity checks are insufficient.

## Deliverables and recovery

`delivery/` contains the full result workbook, anonymous200 review workbook, all-result CSV and four category CSVs. JSONL retains complete multi-reference evidence. The LOW CSV may be header-only; this means no explicit LOW candidates were found, not proof of zero false exclusions.

`learning_before_v2.sqlite3` is the independent learning backup. Any rollback must stop writers, preserve the current learning database, and restore only `F:/ActionSelectionSkill/learning_data/action_selection.sqlite3`. Never restore over production PRIMARY/Master. Keep immutable V2 inputs/results for audit. No remote push or production branch merge is authorized.
