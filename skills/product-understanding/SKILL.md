---
name: product-understanding
description: 理解跨平台商品表的实际销售主体、规格及商品形态；用于零售目录研究，不推断未提供的性能或销量。
---

使用仓库共享入口 `python scripts/run_selection.py --input <商品表> --output <F盘工作目录> --mode codex`。先识别实际售品，再判断参考关系。保留平台货号、原始字段、来源文件行号和未知值；宿主、加工对象和配套系统不能替代售品。原表只读。

Excel、CSV、JSONL由同一导入器处理。件数只使用显式原文，数量缺失不能填1；组合构成未知则明确保留。后续匹配、价格和经营判断复用同次分析及SQLite缓存，不另起一次模型调用。

完整参数与证据边界见 [共享运行说明](../../references/retail_engine_v3.md)。
