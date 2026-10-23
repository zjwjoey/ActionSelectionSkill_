# Action5000 candidate checkpoint — 2026-10-22

## Read current evidence

- `outputs/staged_5000_20261022/final_manifest.json`: entry and file hashes.
- `final_checkpoint_report.json`: 5,000 imported distinct Action SKUs; old 2,000 unchanged, new 3,000.
- `learning_import_reconciliation.json`: original database rows preserved, integrity=ok/FK=0.
- `Action5000_结项报告.md`: limits and backup recovery instructions.
- `action5000_candidate_reference_pack.jsonl`: 4,400 AI candidates, with source/title evidence and annotation hashes.
- `cumulative5000_pending.jsonl`: 600 pending; do not use as selection negatives.
- `review150_ledger.jsonl`: actual per-item diagnostic AI opinions, not independent targets.
- `candidate_action_patterns5000.json`: candidate patterns and supporting titles, not buying standards.

All filenames above are relative to `outputs/staged_5000_20261022/`.

## Version and method

New 3,000: `name-semantics-v11-action5000-candidate`. Old 2,000 retain their earlier versions. Frozen V10 stays unchanged. V11 adds 479 reusable vocabulary rules and 46 context refinements, no SKU-specific classification branches. Category and normal use remain proposed labels. New 427 pending: 354 rule gaps, 20 source-language anomalies, 53 other uncertainty cases. Combined 600 pending include old 173.

The new records were selected from the frozen `master_d1af859e842adbe1` learning projection, with source-category strata and lexical diversity. Original categories were hidden from semantic input. Frequencies are not Action catalog proportions. Do not use source prices, images, availability status, external review comments or Chinese names as semantic facts. Preserve source anomalies without backtranslation.

Replay context refinements with the frozen JSON contract:

```powershell
& 'F:/ActionSKUTracker/.venv/Scripts/python.exe' scripts/action5000_refine.py --input outputs/staged_5000_20261022/v11_draft_candidates3000.jsonl --policy rules/versions/name-semantics-v11-action5000-candidate/action5000_review_policy.json --output outputs/<new-create-once-output>.jsonl
```

This exports rule candidates. It does not recreate the separate 150 item review or perform database approval. Preserve their existing exact input/output binding. Persistence uses `pipeline.import_analysis` on the existing 100-item batches with explicit V11 version. Each batch's `v11_candidate_input.jsonl` is the accepted import payload. Reimport identical payloads is a no-op (all 30 batches actually verified); do not regenerate changing parent metadata on resume.

Only `feedback`/`benchmark` imports with a real human and matching annotation hash can create human labels. V11 records precisely declare deterministic generation; per-item opinions are nested under `ai_review.per_item_review`. This is not model parameter training.

Stop at 5,000. Future external comparison needs unseen records, an explicit common business target, preserved arms and independent review. Existing V10 external samples cannot become unseen V11 tests merely by rerunning them.
