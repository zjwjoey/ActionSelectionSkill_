---
name: product-matching
description: 跨平台商品匹配的V3.1主要入口，输出0到10分暂定指数及Top5、关系和依据。
---

# product-matching V3.1

先召回20候选，再在一次共享批量模型调用中判断关系与整件/组件覆盖。Python沿用旧V2可解释指数换算十分制，不允许AI随意给分。完整可靠参考中选择指数最高项；同分按证据、原模型排名、SKU稳定排序。未确认主分为空；共同词、材质或大类不证明同类。无独立型号/GTIN验证不判同款。

从本Skill上溯两级到仓库根目录，调用共享入口 `python scripts/run_selection.py`。所有工作目录使用F盘；原始商品资料只读。完整参数及版本边界见[共享运行说明](../../references/match10_v31.md)。
