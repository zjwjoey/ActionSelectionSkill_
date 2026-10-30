---
name: product-understanding
description: 理解跨平台商品的实际销售主体、规格与形态，为十分制匹配提供原文证据。
---

# product-understanding V3.1

明确买家收到整机、配件、耗材还是组合；标题中宿主不等于所售主体。数量、颜色、功能数和包装尺寸分别处理，不猜缺失参数。主体不明只报告未确认，不作三态经营取舍。

从本Skill上溯两级到仓库根目录，调用共享入口 `python scripts/run_selection.py`。所有工作目录使用F盘；原始商品资料只读。完整参数及版本边界见[共享运行说明](../../references/match10_v31.md)。

V3.2扩展只在显式engine v32启用，详见[共享实验流程](../../references/v32_learning.md)。与matching-learning共用程序；候选假设不得自动当成事实，经营研究仍不进入默认评分。
