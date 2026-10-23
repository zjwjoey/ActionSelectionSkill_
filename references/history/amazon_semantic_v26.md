# V2.6 semantic screening experiment

Run: `v26-f104d22bbb18bf27`. Artifact directory: `v2/runs/semantic_v26_20261023/`.

## Components and authority

- `v2/semantic_v26.py`: exact input binding, semantic schema, A-E relation/form gates and boundary evidence validation. Receives real AI judgments; no pretence that Python keywords perform deep reasoning.
- `v2/run_semantic_v26.py`: reviewed group anchors, freeze, sample, local queue and source-bound proposal materialization.
- `rules/semantic_v26_prompt.md`: frozen title/category-only reasoning contract.
- `v2/finalize_semantic_v26.py`: reference verification against `source_rows`, shared DB append-only persistence, before/after review export and integrity evidence.
- `tests/test_semantic_v26.py`:18 passing contract tests. These test mechanics, not product-understanding accuracy.
- `action_groups_v26.json`:24 groups,81 literal source anchors. Prototype `action_group_members.jsonl` contains4768 inherited candidates; known domain errors were quarantined, not automatically promoted to trusted members. Full index10037 preserved. Existing4967 eligible exact-title historical SKUs were found in9849 analysis-version records; this is not9849 distinct products or Gold.

## Running and resuming

Use `F:/ActionSKUTracker/.venv/Scripts/python.exe` from project root:

```powershell
python v2/run_semantic_v26.py dev
python v2/run_semantic_v26.py freeze
python v2/run_semantic_v26.py sample
python v2/run_semantic_v26.py local
python v2/run_semantic_v26.py new
python v2/finalize_semantic_v26.py
```

These stages reuse immutable artifacts and fail on dependency/output conflicts. `sample` reuses the existing200 rows; it must not draw replacements. Do not rerun the historical full workflow. `groups` is a pre-freeze library-building stage, not an instruction to rewrite the frozen library. The only Skill entry remains `SKILL.md`.

For future explicitly authorized samples, create a new versioned run namespace and freeze first. Produce actual Codex structured proposals with the documented13-column layout in `bind_compact`; the current module deliberately does not call a paid external API. A missing proposal cannot become an inferred approval. Model descriptor honestly states the current session and unknown exact model ID. Input includes title/category only; record ID, hash and source row are provenance, not screening features. Do not use price, images or product details.

## Decision constraints

1. Identify sold object separately from host and purpose.
2. State form/dependency uncertainty. Specific-host accessories are observation in this minimum version; universal aids are not automatically rejected.
3. Check real Action title evidence, not just group name or retrieval score. A/B/C meanings must have individual explanations. A real SKU does not verify relevance.
4. B/C can support retention when specific consumer need and independent form are supported. D is broad-only and cannot upgrade automatically.
5. Experimental exclusions cite explicit subject/boundary spans and counterexamples. No absence-of-reference exclusion. No blanket industrial/professional keyword rule. Unresolved large furniture is research observation.
6. Save AI judgments separately from human feedback. HumanGold0; accuracy/recall/false-exclusion remain unavailable.

## Results and remaining uncertainty

The200 comparison is91/108/1 versus12/188/0 (retain/observe/not-needed).55 retained proposals use B/C rather than A. Only1 new boundary exclusion means independent exclusion behavior remains weakly sampled. The development60 has22/33/5 and cannot be pooled into independent evidence.

Source corrections include N137 fan-switch accessory rather than fan host, and N118 electrical enclosure rather than domestic cabinet. N092 remains unknown instead of inferring a remote from brand knowledge. These are AI interpretations, not confirmed human labels. Literal-span changes across186 rows mostly reflect changed granularity and accent handling; they are NOT186 verified error corrections.

Human review priorities include the unique new exclusion N073; generic relation strength; N097 balloon/gas-cylinder supply ambiguity; N155 food-contact implications; and N182 possible sealant-gun/hot-glue mechanism mismatch. Do not turn increased retention into a claim of improved selection quality.

Persistence: only `assortment_v26_runs`, `assortment_v26_results`, `assortment_v26_semantic_cache` are written. Shared DB integrity and foreign keys pass; repeated persistence inserts0. Original table counts and protected source hashes remain unchanged. Backup is `learning_before_v26.sqlite3`; program archive is `v2513_protected_program.zip`. Sealed50 Action contents were not opened. Final report and workbook are in the run directory. Stop at V2.6; full Amazon replacement remains off.
