# Action semantic V2.2 — title-only feature candidates

This is the Owner's Action understanding phase, not a replacement of the frozen Amazon engine whose internal version also contains v2.2. Read `outputs/action_semantic_v22_20261022/final_manifest.json` and `V2.2_执行报告.md` for the verified state.

## Scope and evidence

The current 10,037 eligible SKUs include historical products already in the long-term Master. Old5,000 memberships intersect at4,970;30 are quarantined source anomalies.4,967 titles are unchanged,3 changed,5,067 have no previous SKU learning record. Historical Master reconciliation found no additional trusted SKU, but109 title versions are retained separately. Never replace a current title with its historical variant or double count versions as new SKUs.

Only the title and source/version identity enter analysis. Old candidates are reusable proposals, not human truth. The50 sealed IDs/title fingerprints and34 source anomalies stay excluded. Unconfirmed April archive identities are not promoted to SKUs. Do not read sealed title payloads for rule work or examples.

## Current candidate layer

Use `scripts/semantic22.py`, the frozen parent V11 definitions and `rules/action_semantic22_rules.tsv`. Every rule is a title family or grammatical context, never a SKU branch. Existing candidates are reused when source titles match. Main objects, purpose qualifiers, packaging and multiple functions must survive; a late ingredient/flavor/container noun cannot replace the main item. Ordinary use is always a hypothesis, not a source assertion about performance, material, sales, safety or demand.

Maintain four distinct result states:
- `SPECIFIC_SEMANTIC_CANDIDATE`: a type and discriminating use/need candidate exist; still unconfirmed.
- `FEATURE_TOO_BROAD`: current labels are too general. This is not proof of an inadequate source title.
- `RULE_COVERAGE_GAP`: rules did not recognize the title. This is a program limitation, not a source error.
- `INFORMATION_INSUFFICIENT`: type can be retained, but use remains unestablished.
`RULE_CONFLICT` remains available and blocks relationship use. Zero detected rule conflicts never proves zero semantic errors.

Only specific candidates enter `type_need_edges.jsonl` and `related_need_groups.json`. Sharing a narrow need is a candidate relationship, not equivalence or a decision to retain/exclude Amazon items. Broad needs must not become matching edges. Historical use and need arrays are not positional pairs; never zip them into invented correspondences.

## Persistence and resume

One database remains: `learning_data/action_selection.sqlite3`. New tables are `assortment_v22_semantic_*`; original analyses, samples, feedback and Amazon tables remain intact. Run/record/source/result hashes bind every candidate. AI diagnostic reviews are stored separately from human feedback. Resume finalized imports with:

```powershell
& 'F:/ActionSKUTracker/.venv/Scripts/python.exe' scripts/semantic22_finalize.py
```

This validates frozen outputs and appends exact missing rows; differing retries fail. Changes to the engine/rules require a new output version rather than editing the frozen final candidate. Do not regenerate draft inputs as routine resume. Before recovery stop learning writers, preserve current DB, and restore the verified `learning_before_semantic22.sqlite3` only to this independent learning database. Never restore production PRIMARY/Master.

18 semantic boundary tests and3 storage contract tests passed.100+10 batches persisted10,037 records,109 historical versions and150 AI diagnostic reviews. A new empty review-table composite-FK defect was corrected; first100 records were retained and resumed, with no historical-table changes. See the incident and safety evidence.

## Limits and next design

6,777 specific candidates are available;1,602 broad-feature records,1,390 rule gaps and268 insufficient records remain.3,437 prior SKU candidates and674 identical-title candidates are reused, without declaring them correct.150 purposive AI reviews are developmental evidence, not independent accuracy. No human gold is available. Do not claim full semantic mastery or improved Amazon selection accuracy from coverage.

V2.3 design is in `V2.3_设计.md`: improve remaining context gaps, inspect type synonyms, then evaluate evidence-bound feature use and reference quality on new blinded samples. Keep Amazon20,018 historical decisions and evaluation identities unchanged.
