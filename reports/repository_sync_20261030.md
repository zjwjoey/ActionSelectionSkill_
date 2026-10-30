# Repository synchronization snapshot — 2026-10-30

Audited code head: `4e236c26014b0b309430b006595c10c8d9c918f0`. Snapshot cutoff: `2026-10-30T14:23:35.611131+00:00`.
This snapshot binds the audited head, not the SHA of its own later documentation commit.

## Synchronization

- 16 local named branches inventoried; local/remote heads are recorded in the companion JSON.
- 9 worktrees checked; ignored private experiments are excluded from the clean Git status claim.
- Two historical branch refs were advanced by fast-forward only. Their commits were already reachable on other remote branches; no history rewrite or main merge.
- Commits present only locally: 0.

## Current research state

- Frozen Action reference: 10,037 records; no re-training of E5 or language models.
- V3.3: 150 input records / 1,200 studied pairs. V3.3.1: 500 / 5,000.
- The expanded training split contains 312 inputs; 104 supply usable preference contrasts (1,310 symmetric preference rows).
- Pair authorities: 2,800 AI_SILVER, 2,200 UNVERIFIED; independent human pair Gold: 0.
- Supplement: 60 inputs / 300 reviewed candidates; AI advice remains AI_SILVER.
- Frozen fresh validation: 80 inputs including Amazon40; 23 form a known-type-disjoint proxy subset. GTIN/cross-language identity isolation remains incomplete.
- On the common weak-labeled pool, original AI / old C / matched-split150 C / expanded500 C top eligibility is 70 / 62 / 65 / 64 out of 78. These are NOT human accuracy figures.
- Expanded C versus old C: 9 weak relevance gains, 4 losses. The controlled150 comparison is mixed; no stable data-size-only advantage is established.
- No formal model promotion. Original AI/QA workflow remains required. No complete-catalog recall or independent accuracy is claimed.

## Engineering evidence

- Audited-head CI: https://github.com/zjwjoey/ActionSelectionSkill_/actions/runs/41069445123; Ubuntu219 and Windows219 passed.
- Local219 tests passed; frozen package assets and source preservation were checked.
- Workbook: 158,001 cells compared, zero mismatches; human-review fields remain blank.
- Current documentation publication receives its own exact-head CI; it does not rewrite the audited research head.

## Private material retained locally

- Full data, quotes, model responses, label SQLite, fitted models, workbooks and run-specific helper scripts remain local.
- The companion manifest contains logical artifact names, sizes and SHA256 only; it does not publish private product rows or raw model answers.
- This is code and state synchronization, not a full data backup or a production deployment. Source recovery and full experiment reproduction still require the retained private artifacts.

## Next decision

The experiment is not accepted for formal matching quality. Prioritize trustworthy pair labels and the remaining subject, qualifier, bundle and accessory/consumable errors before treating further scale as a proven improvement. Do not merge main or switch the default model based only on engineering CI.
