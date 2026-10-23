# V2.5.1 delegated AI semantic review

## Authority and scope

The Owner explicitly authorized Codex to adjudicate the 12 calibration cases, settle experimental assortment boundaries, diagnose the 97 prior observations, run a fresh batch, and decide further steps autonomously. No additional Owner question is needed for this scope. AI decisions remain AI evidence; do not write them into human-feedback/Gold tables or fill a human reviewer identity.

Use the frozen 10,037-title Action index and original Amazon 20,018-row snapshot read-only. Preserve V2.4, V2.5, Master, the 50 sealed Action records, and all prior annotations. No full Action retraining or automatic replacement of formal Amazon results is authorized by this experiment.

## Semantic execution

1. The active Codex model reads each original title and records the actual sold subject, a literal Spanish evidence span, use qualifiers, dependency/model restrictions, and remaining uncertainty. Brand/model alone must stay information-insufficient. Distinguish a fan *mode* of an AC from a mini evaporative fan; distinguish a host appliance from its cover, filter or remote.
2. Retrieve real references with `subject_reference_bridge.retrieve_subject_candidates(matcher, title, subject_evidence)`. It merges the original-title and literal subject-span queries against the existing Action index. Returned candidates are not automatically validated relations. If necessary, search source-supported Spanish subject synonyms in the same index; record the resulting real SKU and title.
3. The model checks functional type, purpose and dependency against each reference. Same room, material, USB interface, holiday theme or generic noun does not establish the same functional class. Distinguish same functional class with an unverified subtype from exact product/model equivalence. Preserve uncertainty about compatibility, technical performance, quality and demand.
4. Provide a source-hash-bound AI record. `subject_reference_bridge.project` checks the current source identity, literal subject evidence and exact Action reference provenance, then enforces the public three-state contract. It does not generate a semantic judgment or call a model itself. Per-record review data are annotations, never SKU-specific program rules.

## Experimental business boundaries

- `保留`: clear standalone everyday product, with a verified same-functional-class Action reference and a stated purpose relationship. Preserve size, set quantity and subtype differences.
- `观察`: complete furniture under the existing everyday-first scope; dedicated/model-bound parts; uncertain source; missing usable reference; large sheds, storage-energy systems or specialized devices without a sufficiently established boundary. A specialty/industrial-sounding word alone is not an exclusion.
- `用不到`: clear complete major household appliance/system, explicit industrial production/process equipment, or firearm/ammunition-specific storage/use. These are delegated AI experimental business rules, not empirical claims about Action sales. Compact camping refrigeration remains observation where size/form makes the boundary uncertain; do not invent a universal BTU cutoff.
- Dishwasher-safe and fridge-compatible are source properties and cannot turn tableware or storage boxes into major appliances. A large appliance mentioned in a compatibility clause cannot replace the sold subject.

## Records and reproduction

Current run: `v2/runs/amazon_v251_ai_calibration_20261022/`. Raw model judgments are retained in `ai_review_112.tsv` and `ai_review_150.tsv`; JSONL, source binding, CSV review views, diagnostics and the experiment policy are retained alongside them.

```powershell
$env:PYTHONIOENCODING='utf-8'
& 'F:/ActionSKUTracker/.venv/Scripts/python.exe' v2/review_round_v251.py prepare
& 'F:/ActionSKUTracker/.venv/Scripts/python.exe' v2/review_round_v251.py finalize
& 'F:/ActionSKUTracker/.venv/Scripts/python.exe' v2/subject_reference_bridge.py
```

`prepare` resumes the same frozen sample if it exists. Do not change its TSV/JSONL after publication; revised reviews need a new version directory. `finalize` binds all 262 records and appends only `assortment_v251_ai_*` tables in the shared learning database, with a verified SQLite backup, unrelated-table count check and exact-repeat insertion check. Outputs are AI candidates; repeat imports must be no-ops.

## Current evidence and next-stage decision

The 12 calibration cases became 5 retain, 4 observe, 3 out-of-scope AI proposals. Of the prior 97 observations, 27 became AI retain candidates and 70 stayed observation. Separately, 45 title subjects that the program marked unclear were identifiable in AI review; these counts overlap the decision changes.

The new150 was selected by frozen title cues before its V2.4/V2.5 predictions were revealed: 20 explicit boundary-cue, 30 accessory/property-confusable, 20 furniture/specialized-research, 80 random-remainder rows. It had no prior title overlap. AI proposals were 53 retain, 79 observe, 18 out-of-scope; frozen V2.5 was 7/131/12. Two V2.5 exclusions became AI observation concerns; 48 observations became AI retain proposals. Treat these as disagreements requiring model-guided semantic improvement, not human error rates. Five firearm-storage differences reflect an explicit policy extension, not failed detection under an unchanged policy.

The subsequent bridge was checked on these development records. Among 88 AI-retained records, an AI-selected reference occurred in original top20 retrieval for 64 and subject-query merged top20 for 69; merged top40 found 73. This is candidate retrieval coverage against AI-selected references, not accuracy. Report the candidate budgets separately.

Proceed with targeted subject extraction and reference retrieval; keep full-snapshot screening gated. Freeze a new bridge/policy version before a future unseen validation cohort. The current150 remains independent for the old frozen baselines, but is development evidence for V2.5.1. No human-confirmed accuracy or improvement exists yet.
