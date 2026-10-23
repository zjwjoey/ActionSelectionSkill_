# Amazon boundary screening V2.5

Historical frozen baseline. Current delegated-AI calibration and execution is documented in [V2.5.1](amazon_semantic_v251.md). Earlier Owner-confirmation pauses below describe the previous stage; the later explicit delegation permits AI experimental decisions while preserving human-Gold separation.

## Scope and frozen inputs

V2.5 refines Amazon title-only judgments using the existing 10,037-title Action feature index. It does not retrain or replace that index. V2.4 remains frozen at `amazon-boundary-v24-12c6ff4a86dd578d`; preserve its run, inputs, results and database rows. The V2.4 AI audit-focus workbook is diagnostic evidence, not a human label set.

The project scope remains everyday consumer products first. Complete furniture stays `RESEARCH_ONLY`/`观察` under the existing Owner direction; dedicated accessories or parts are not excluded just because they mention a large host product. A candidate boundary only becomes `用不到` when the sold subject itself is clear and an already declared boundary is evidenced. For air-conditioning terms, require title evidence of a complete unit (such as BTU capacity or a clear outdoor/split system); mini evaporative coolers, ambiguous portable devices and accessories that mention an AC remain `观察`.

Do not infer that firearm cabinets, ammunition storage, large sheds, portable power stations or professional-sounding consumer tools are confirmed exclusion boundaries. Keep them under review until Owner confirms the boundary. Professional or industrial vocabulary alone is insufficient.

## Judgment contract

Every row keeps exactly one public decision: `保留`, `观察`, or `用不到`. Persist these separate internal facts:

- `product_subject_status`: `CLEAR` or `UNCLEAR`, with class and title evidence.
- `action_reference_exists`: whether an exact Action SKU/title reference is bound.
- `action_reference_relation`: `SAME_CLASS`, `RELATED_CLASS`, `NOT_SAME_CLASS`, or `NO_REFERENCE`.
- `boundary_status`: `NONE`, `UNCONFIRMED_CUE`, `RESEARCH_ONLY`, or `CONFIRMED_CANDIDATE`, with typed evidence.

`保留` requires a clear subject, a sufficiently supported source-use cue, and a real same-class Action reference. Related type, shared task, broad lexical overlap, or a product-theme match cannot be upgraded to same class. A missing or unrelated reference is not an exclusion reason. `观察` covers ambiguity, research-only cases, unresolved boundaries, and references that are not sufficiently same-class. `用不到` requires both a subject-bound confirmed boundary and its evidence; never infer it from absence of Action matches.

## Calibration and validation

The supplied `Action_V24_AI_Audit_Focus.xlsx` contributed failure-mode examples only. It did not supply Gold labels. The first owner-review candidate file has 12 hash-bound cases, with AI recommendation and human decision kept separate. Import only explicitly confirmed reviewer decisions into the human-feedback namespace; never convert the AI recommendation column into Gold.

The first frozen-rules paired shadow sample is `amazon-boundary-v25-2109ef657ef8dc8f`, using 50 boundary-cue and 50 seeded-random titles. It excludes all prior V2.4 tests, all 27 supplied focus cases, and the 100 V2.5 development titles. V2.4 and V2.5 were run on the same 100 rows. V2.5 produced 3 `保留`, 97 `观察`, and 0 `用不到`; therefore this run does not test false exclusions or demonstrate improved screening. Human Gold remains 0; accuracy, recall, precision, false-exclusion rate and measured improvement are unavailable.

For a new validation after calibration, freeze the rule file and create a fresh, disjoint cohort. Include predeclared subject-bound boundary families, confusing accessory/purpose mentions, complete-furniture research cases and random titles. Store the cohort IDs, title hashes, sampling seed, V2.4 and V2.5 results, and blank reviewer fields before unblinding any labels. If rule edits occur after labels are viewed, that cohort becomes development data and cannot be reported as independent validation.

## Implementation and persistence

- `v2/boundary_v25.py`: subject evidence, context-aware boundary states, typed Action reference relation, paired shadow sample, and new append-only `assortment_v25_boundary_*` tables.
- `v2/export_boundary_v25_calibration.py`: exports a small hash-bound owner review from the supplied audit workbook without editing the source workbook.
- `tests/test_boundary_v25.py`: regression cases for subject-vs-purpose, mini cooler vs full AC, full furniture, firearm-safe boundary uncertainty, and same-class reference checks.

V2.5 writes only its own run directory and namespace in the shared `learning_data/action_selection.sqlite3`. Each run is content-addressed and append-only. Verify SQLite integrity and foreign keys after writes. Master, Action snapshot, frozen V2.4 results, V10 and the sealed holdout remain untouched. The current V2.5 shadow run is an experiment only; it does not replace formal screening output.
