---
name: assortment-selection
description: 仅在用户明确要求时回放历史三态经营研究，退出默认V3.1匹配评分流程。
---

# assortment-selection V3.1

这是可选历史能力。使用 `--task legacy-selection` 明确运行V3旧三态；默认十分制评分流程不调用经营手册、不返回保留/观察/用不到。历史Owner裁定和AI意见分级保留，不将匹配分解释成经营适配或采购建议。

从本Skill上溯两级到仓库根目录，调用共享入口 `python scripts/run_selection.py`。所有工作目录使用F盘；原始商品资料只读。完整参数及版本边界见[共享运行说明](../../references/match10_v31.md)。
