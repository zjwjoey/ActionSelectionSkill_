# Boundary V0 learning and failed acceptance

Run directory `v2/runs/boundary_v0_20261023/`, run ID `boundary-v0-fc7573dd4ad6510d`. The completed task explicitly stops at this acceptance node. Do not silently retry/expand after the failure.

## Source and provenance

Use `source_report.json`: the complete `今日快照合并_214818_82be` CSV has25152 records,136 columns and9 L1 categories. It combines the accepted20k and10k batches delivered2026-10-22; the20k capture began21October. SHA256 `84bacc4c6b66ab7aa1fd7f704d7c3c50a0a195539050fc8e6180f5f0129f68d4`. The nearby214722 export is marked incomplete and rejected. Do not fallback to20018 or the old October14 30026 source.

Stable record ID = snapshot file SHA prefix + original logical CSV row (header counted). Preserve all25152 rows including3355 extra equal-normalized-title records across3128 duplicated-title groups. URL/ASIN hints and conservative groups are not verified buyable SKU identities. Only Spanish title/L1 are screening inputs; run IDs/rows/hashes are provenance. Price, ratings, sales and details are not screening features.

## Components

- `v2/boundary_learning.py`: sold-subject evidence, four scopes, independent Action-match strength, candidate-state projection, reference validation, feedback/publication contracts, semantic-type impact planning.
- `rules/boundary-v0.json`: candidate operating boundaries, counterexamples and no-Gold status; not an Action semantic-library version.
- `v2/run_boundary_learning.py`: source discovery evidence/import, verified DB backup,500 sampling, local experiment, freeze, new200 sampling.
- `v2/bind_boundary_reviews.py`: binds real current-session Codex judgments with source hashes/literal spans; never creates a human identity.
- `v2/run_boundary_full.py`:500/200 source/shape checks, frozen500-row chunks, resume, experimental persistence. Its source checks passed but did NOT catch later semantic false exclusions. Do not interpret expansion_gate.json as final acceptance.
- `v2/finalize_boundary_v0.py`: append-only49-row safety opinions, complete exports, DB/reference/source reconciliation and explicit failed acceptance report.
- `v2/boundary_store.py`: only `boundary_learning_*` tables in the existing shared DB.
- `v2/boundary_feedback.py`: human evidence import, common-type candidate proposals, regression+approval release gate, impact planning and released-rule-only delta replay. None of its human import/publish commands was executed with actual human data this run.

## Judgment order

1. Identify the actual sold object before interpreting named hosts/compatibility.
2. Consult human-confirmed boundary experiences if any; currently none. AI cases are candidate context, not inherited approvals.
3. Bind A/B/C/D/E references to real Action SKU/name/source row. Verify DB existence; semantic relevance is separate.
4. Scope = 范围内 / 灰区 / 范围外 / 未知. Gray includes powered tools, complex appliances, furniture and specific-host/install parts. Explicit outside proposals require a real sold-subject boundary; no high-price inference.
5. Three states = 纳入候选 / 待复核 / 暂不纳入. Clear core type still needs concrete reference evidence. Unknown/no-reference is observation, not automatic exclusion.

## Frozen evidence and failure

Freeze preceded the new200 (100 random first,50 boundary,50 difficult), with no known old/development normalized-title overlap. Development500 =300 random+100 boundary+100 difficult. Initial development errors in trailing bundled parts were fixed before freeze and retained in development_attempt1/2.26 contract tests pass; that is not semantics accuracy.

New200 =31 include/168 review/1 outside. Old-method comparison only replays the executable frozen local path, not a fabricated full semantic A/B; no missing Codex call was invented. After full local traversal the51 outside proposals included host/compatibility errors. Additional49 were actually reviewed by Codex, withdrawing20; the other2 already had explicit semantic review. Full safe-candidate export =3111 include/22010 review/31 outside. Total actual Codex analysis =73development+40independent+49safety=162, not25152. External APIs0; session model exactID/Token billing unavailable.15580 records remain without a clear specific type.

Do not turn the20 withdrawn opinions into a formal false-exclusion rate. Known concrete failures are reproduced in `known_failures/replay.log` with3 failed tests. Frozen rules were NOT fixed after independent exposure. The post-review table is a data-opinion correction, not a program repair. Final acceptance remains FAIL; do not promote the candidate or declare no systematic false exclusion.

## Feedback and incremental iteration (future explicit input)

Required human JSONL fields: record_id, source_binding, decision, authority=`HUMAN`, reviewer, evidence_reference (real local file), evidence_sha256. Optional corrected_subject_type, corrected_function, corrected_scope, reason. Blank review tables are not approvals. `import-feedback FILE` checks exact current source and evidence file SHA; it does not authenticate a person beyond their supplied evidence. Actual human reviewer identity must come from the Owner's supplied review, not an invented string.

`python v2/boundary_feedback.py import-feedback human.jsonl`

`propose` groups at least2 distinct confirmed records by corrected concrete type/decision into an unapproved candidate. It never writes SKU keyword exceptions. A candidate retains support feedback IDs, conditions, counterexamples, affected record count and test status. With zero feedback it generates zero proposals, not synthetic human labels.

`publish RULE.json --tests REGRESSION.json` requires all support IDs in real imported evidence, counterexamples, exact candidate hash in a PASS regression report, reviewer approval and a matching approval evidence file SHA. This completed task did NOT publish any rule. Future publication needs an explicitly authorized repaired candidate; this CLI is not permission to auto-publish after the current failure.

`plan-incremental RULE.json` lists affected semantic types and existing pending records separately; new-source inputs need their own provenance/import gate. `apply-release RELEASE_ID` rejects unpublished rules, replays only affected types into a new delta file, preserves source bindings/history and never labels every affected row humanGold. Existing source/result files remain rollback references; switch a release pointer or ignore a delta to revert, rather than overwrite source rows. Actual full human-feedback-to-release behavior remains unvalidated because there is no human feedback yet.

Deliveries: complete/three-state CSVs, learning queue,500/200 review CSVs,49-exclusion audit CSV, four-tab review XLSX, JSON rule evidence catalog, source/integrity reports and final acceptance report. All human decision/identity fields remain blank. No score/price/image features, no fine tuning, no original source writes, no old semantic rule modifications, no next formal boundary release.
