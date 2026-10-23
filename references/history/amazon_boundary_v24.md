# Amazon boundary screening V2.4

## Purpose and immutable inputs

This experiment tests a more conservative Amazon screening order without retraining Action. It reads the frozen 20,018-row Amazon snapshot, the frozen Action reference index and the V2.3 Action title/need candidates. It writes a new run under `v2/runs/amazon_boundary_v24_20261022/` and a new namespace in the existing `learning_data/action_selection.sqlite3` database. It never edits Master, source snapshots, sealed Action holdout, V10, V2/V2.3 outputs, or prior Amazon decisions.

The 500-row experiment is split into a 100-row reverse-boundary cohort and a 400-row seeded comparison cohort. Exclude exact Amazon rows/titles already used by prior cross-platform, P3/P3.1, technical500 and independent200 samples. Boundary sampling cues are for coverage only; they are not ground-truth labels. Preserve the source row, title hash and original product URL.

Completed run: `amazon-boundary-v24-12c6ff4a86dd578d`, outputs in `v2/runs/amazon_boundary_v24_20261022/`. The human review workbook is in `outputs/amazon_boundary_v24_20261022/`. The run has 22 `保留`, 478 `观察`, and 0 `用不到`. The reverse-boundary cohort contains 25 major-appliance mentions, 7 large-furniture-set mentions, 9 professional/industrial mentions, 5 explicit out-of-target cue rows, and 54 confusable/fill rows. These are cue-coverage counts, not confirmed product classifications. No exclusion was forced to reach a target ratio.

## Decision order

1. **Identify the actual product subject from the Spanish title.** Separate a sold item from its purpose phrase, compatible model, included accessory, brand, model and technical qualifier. If the subject is not clear, emit `观察`.
2. **Check only high-confidence range boundaries.** Candidate families are explicit major household appliances, complete large furniture sets, explicit professional industrial equipment and clearly out-of-target products. Confirm that the boundary phrase describes the product being sold. A word that appears only in a compatibility/purpose phrase, accessory title, brand, model, or feature cannot trigger exclusion. Weak, mixed or uncertain boundary signals become `观察`.
3. **Retrieve concrete Action product-type and consumer-need references.** Bind each reference to an exact Action SKU and Spanish source title. Broad lexical similarity or a broad task alone is not a useful reference.
4. **Emit one of three public outcomes:** `保留` for a specific, supported everyday product type with a sufficiently specific Action reference; `观察` for partial matches, uncertainty, or no usable reference; `用不到` only for an explicit, high-confidence out-of-range product subject.

The `用不到` decision requires a typed, subject-bound reason code and evidence span. It is never produced solely from an absent Action reference, an unknown safety/quality/brand attribute, professional wording by itself, a category label, or a keyword hit without subject confirmation. No required exclusion ratio exists.

## Reverse-boundary review

The reverse-boundary cohort targets both unmistakable out-of-range product subjects and confusing titles that mention a boundary object while selling an accessory, component, consumable, or ordinary household item. Sampling cues do not predetermine decisions. The review file must show the source-bound title, three-state result, boundary reason/evidence, Action references, and blank human decision/reason/reviewer fields. Sort `用不到` first so a reviewer can audit false exclusions.

## Evaluation and persistence

Keep internal reasons, boundary code/evidence and concrete Action SKU references even though the user-facing status has only three values. Record all 500 inputs and outputs by immutable run ID, source hash and method fingerprint. Add results only to new `assortment_v24_boundary_*` tables in the shared learning database. Exact replay must insert zero duplicates. Preserve an online SQLite backup and verify integrity before and after append.

With no human-confirmed labels, report counts and inspectable examples only. Do not report accuracy, recall, false-exclusion rate, or skill improvement as measured facts. The P0 evaluation focus is manual review of all `用不到` rows and representative `观察` rows, especially titles where boundary terms occur in accessories or purpose clauses.
