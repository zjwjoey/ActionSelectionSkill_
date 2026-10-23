# V2.5.6 title-subject and Action reference candidate

## Scope and execution

Keep the single Skill and shared database. Reuse the frozen 10,037-title Action index. No Master/source changes, Action retraining, prices, images, external translation calls or human-label fabrication.

Commands, from `F:/ActionSelectionSkill`:

```powershell
F:\ActionSKUTracker\.venv\Scripts\python.exe v2/run_subject_v256.py
F:\ActionSKUTracker\.venv\Scripts\python.exe v2/audit_subject_v256.py
```

Run: `v256-2cc50f8ca238b609`; output `v2/runs/subject_v256_20261023/`. Repeat execution must insert zero rows and preserve exact fingerprints. A code change requires a new frozen version and untouched validation sample. Read `frozen_contract.json` before changing any inherited modules: active V2.5.6 imports V2.5.2–V2.5.5, all pinned.

## Implemented program changes

- Amazon and Action share specific literal subject-family rules. References must identify real SKU, original title and source row.
- Retrieve the original title and evidenced subject span using the existing TF-IDF/SVD model; add candidates from the same literal family. This does not train a language model.
- Separate the sold item from hosts, washing/dishwasher properties and included accessories. Unknown subjects remain observation.
- Compare audience and functional subtype: infant/adult, ordinary/vacuum/electrically heated boxes, air/oil fryers, cooking/dining spoons and grill forms. A generic material/interface is insufficient.
- Compact camping/no-install refrigeration stays observation; there is no arbitrary BTU threshold. A fan operating mode does not make a full AC a fan.
- Exclusion requires consistent positive appliance-form evidence and a supported sold-item heading. Unknown leading text or counterevidence means observation. This deliberately misses some branded complete appliances rather than treating arbitrary nouns as brands.
- Original furniture/dedicated-part research scope and three public states remain. No Action reference alone never excludes.

These are deterministic rules with known coverage limits, not a proof of robust Spanish semantic understanding. Reference existence and family agreement do not prove exact subtype equivalence.

## Evidence and current decision

- Original two exclusion disagreements: both observation.
- Prior48 AI retention candidates:44 program retain, four observe: N026/N050 hand mixers lack explicit same-subtype Action evidence; N037 drinking glasses remain an unsupported broad family; N040 oil fryer lacks explicit oil-fryer reference in selected candidates. Their AI opinions are not overwritten.
- Four successive frozen new100 diagnostics were retained. Their exposed cases cannot be counted as untouched V2.5.6 evaluation.
- Final freeze precedes new50 selection:10 boundary/host,15 confusable,25 seeded random; exact prior-title overlap zero.
- New50 program: five retain,45 observe. Source-bound AI post-review: four retain,46 observe; K010 air-cooler-to-generic-fan reference is too broad.
- Remaining subject errors K005/K006 laundry bags called washers, K018 French press called a filter/component. They are observations, not exclusions.26 additional rows are AI-identified rule-coverage gaps. Do not claim these are fixed.
- Final50 has zero program exclusions. False-exclusion rate and human accuracy are unavailable. Do not report zero errors from zero excluded cases.
-98 targeted tests pass. Actual repeat program insertion is zero. SQLite integrity is OK and FK violations zero.35 pre-existing tables match the pre-V2.5.2 backup row for row. Protected historical source/algorithm files match recorded hashes; sealed holdout content was not opened.

Decision: keep the candidate frozen, do not expand to20,018 or replace official Amazon results. Improve subject roles and reference granularity before a later independent test. No further Action full learning is needed to reproduce this experiment.

## Persistence and artifacts

New `assortment_v252_*` through `assortment_v256_*` namespaces preserve each intermediate version in the same database. `assortment_v256_ai_audits` is a separate immutable AI-opinion table, not human feedback/Gold. Backups are read-validated SQLite snapshots. See:

- `focus_50.csv` / `.jsonl`
- `new50_review.csv`, `new50_ai_review.csv`
- `ai_audit_50_raw.tsv`, `ai_audit_50_bound.jsonl`, `ai_audit_summary.json`
- `known_error_regressions_10.jsonl`
- `summary.json`, `sampling.json`, `frozen_contract.json`
- `data_preservation.json`, `final_report.md`, `final_manifest.json`
