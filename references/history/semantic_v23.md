# Action title semantics V2.3

## Run and scope

- Run: `semantic23_d5df918ae3d1e308`, version `action-semantic-deepening-v2.3`.
- Baseline: frozen V2.2 run `semantic22_72d97db7a9d510f1`.
- Eligible source set: 10,037 SKUs. The 34 source anomalies and 50 sealed holdout titles were excluded.
- Only the 1,390 `RULE_COVERAGE_GAP` and 1,602 `FEATURE_TOO_BROAD` rows were reviewed. The other 7,045 result payloads remain identical to V2.2.
- Master, original snapshots, Amazon results, V10 and V2.2 outputs remain unchanged.

## Candidate results

The run proposed a more specific title interpretation for 1,561 of the 2,992 target SKUs. The remaining 1,431 stay unresolved: 884 `RULE_COVERAGE_GAP` and 547 `FEATURE_TOO_BROAD`. The full before/after comparison is in `outputs/action_semantic_v23_20261022/final_candidate/summary.json`; SKU-level decisions and source hashes are in `scope_review_2992.jsonl` and agent diagnostics are in `diagnostic_review_2992.jsonl`.

The 791 generic rules are stored in `final_candidate/rules.json`. Product type and ordinary-use / consumer-need relationships are hypotheses based on Spanish titles. They do not establish quality, sales, demand, independent usability or Action's procurement rationale. A candidate coverage increase is not an accuracy measurement.

## Evidence boundaries

There are zero human-confirmed gold labels, so accuracy is unavailable. Official Action page observations are separately recorded in `outputs/action_semantic_v23_20261022/official_verification_notes.json`; they were not fed into title-only rules or result payloads. The notes include five verified product pages and mark all of them `human_confirmed=false`. Official evidence can confirm page facts, but it does not turn the title-only interpretation into an independently adjudicated label.

The 268 `INFORMATION_INSUFFICIENT` records were left unchanged. Do not infer missing product attributes from the title. Do not read or use the sealed 50-title holdout.

## Persistence and validation

V2.3 is appended in a new namespace in the shared `learning_data/action_selection.sqlite3`; no parallel learning database is created. The run has 10,037 version records and 2,992 review records. A repeated import inserted zero rows. SQLite integrity passed, there were no foreign-key violations, all 25 pre-existing table fingerprints and all 176 protected file hashes remained unchanged. See `outputs/action_semantic_v23_20261022/persistence_and_safety.json` and `backup_restore_check.json`.

The focused regression suite covers the V2.2 semantic/storage contracts and V2.3 behavior. Its exact command and result are recorded in `outputs/action_semantic_v23_20261022/test_evidence.json`; this is not a full-project test run.

## Next gate

Keep this as a candidate version. Before expanding Action coverage or using these relations to screen Amazon/IKEA products, obtain independent human review on a representative sample and resolve remaining title-only ambiguity. Do not overwrite formal Amazon screening results automatically.
