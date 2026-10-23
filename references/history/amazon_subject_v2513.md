# V2.5.13 frozen subject/reference candidate

## Run and scope

From `F:/ActionSelectionSkill`:

```powershell
F:\ActionSKUTracker\.venv\Scripts\python.exe v2/run_subject_v2513.py
F:\ActionSKUTracker\.venv\Scripts\python.exe v2/audit_subject_v2513.py
```

Run `v2513-62086668a1d0918d`, outputs `v2/runs/subject_v2513_20261023/`. This supersedes V2.5.6 as the active experimental candidate. No production rollout or full Amazon screening is authorized by this run. Master, original sources, frozen Action10037 index, Action learning membership and human feedback remain unchanged. No pictures, prices, sales, descriptions, external translation calls or parameter training.

## Program contracts

- Use `subject_reference_core.py` for full-pool compatibility filtering **before** rank/truncate. Action SKU/title/source-row pointers must match the frozen index.
- Parse literal sold subjects on both sides. Source unknowns remain observation. Earlier unresolved source nouns veto later recognizable hosts or accessories; common pack wrappers are not subject nouns.
- Differentiate manual/powered drills, bubble toys/powered blowers, passive/facial/room humidifiers, ordinary/electric food boxes, stovetop/air/oil fryers, composite fryer-grills, water/condiment bottles, fan installation forms, hook mounting forms, desk lamps/furniture and hair towels/cosmetic wraps.
- Use specific whole-item heads before their parts: laundry bags before washer hosts, French press before its filter, shower squeegee before its support, locker before its doors, baking paper before fryer, kettle before filter and table leg before table.
- Reuse the frozen existing AI role reviews only when record ID, input hash, original title and literal source evidence match. Hint evidence must include the rejected literal noun span. The hint resolves only an earlier-noun ambiguity; current subtype/reference/boundary gates still run. Mismatched versions, invented evidence and same-title/different-source rows cannot share hints. Cache use is marked AI, never human Gold.
- The rule cache and every imported subject module are fingerprinted by `frozen_contract.json`. Any code/cache change needs a new experiment version and an untouched sample. The final AI audit does not modify frozen program decisions.

## Evidence

- Prior50: program5 retain/45 observe ->16 retain/34 observe. These are development results, not accuracy.
- Prior26 coverage-gap titles now have clear literal subject candidates. This is structural coverage, not26 human-approved correct labels.
- Original two exclusion disagreements remain observation. Original48 AI retention candidates now yield42 retain/six observe; no forced quota.
- Seven successive frozen validation batches in this round contain410 different Amazon records:100+100+100+50+20+20+20. Earlier390 exposed titles are development evidence for V2.5.13; **only the final20 remain its untouched rule-validation sample**. They are independent of rule repair, not an independent-human benchmark.
- Final20 strata: five boundary/host, five confusable, ten seeded random. Program1 retain/19 observe; AI post-review proposes20 observe because S015's water-bottle/protective-cover offering is uncertain from its title. Fourteen additional titles remain uncovered. No fresh excluded cases; exclusion accuracy cannot be measured.
-79 new targeted tests pass. Repeat program/audit must insert0. Shared SQLite integrity/FK checks pass. All48 pre-existing tables, restricted to pre-existing run bindings in append-only experiment tables, match the verified pre-run backup. Protected historical sources match their hashes; sealed holdout content was not opened.

Decision: keep experimental, do not expand to20,018 or replace official Amazon results. More abstentions do not prove better understanding or recall. The earlier-noun vocabulary may overblock a prefix; only exact-source evidence may resolve it. AI self-review is not human confirmation.

## Persistence

Same database: `learning_data/action_selection.sqlite3`. New generic `assortment_subject_experiment_runs` / `assortment_subject_experiment_results` tables append versions and stages, including separate `ai_review20`. Older tables and feedback are not rewritten. `subject_experiment_store.py` performs immutable exact insertion and validates an SQLite backup before writes.

Read `final_report.md`, `focus_50.csv`, `new20_review.csv`, `new20_ai_review.csv`, `data_preservation.json`, `resume_stdout.txt` and `final_manifest.json`. Source-bound post-review opinions and program decisions are stored separately.
