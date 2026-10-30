# V3.2 混合匹配与学习（实验）

V3.1冻结对照为 `1f0e526aa78de64b2c9109ed63fe4ee992dc0aec`。主要入口仍是run_selection.py，省略engine保持v31。只有显式 `--engine v32` 才使用实验功能；未证明独立收益前不替换默认算法。

## 复用清单

|能力|处理|
|---|---|
|跨平台Excel/CSV/JSONL导入、来源与报价身份|直接复用ingestion；来源表只读|
|TF-IDF/字符/SVD及Action10037|原样复用冻结Catalog和索引，保留v31排名|
|20候选、Top5、十分制、共享Codex适配器|在match10.run加可选钩子，复用调用、校验、计分和缓存；不建立另一套完整引擎|
|价格L1/L2/L3|直接复用，不用价格确定商品身份|
|SQLite审计、Excel安全反馈|保留；真实反馈可转成待验证知识提议，不能自动批准|
|必须扩展|E5/RRF召回、字面属性冲突、未知原因、学习版本、主动学习队列|
|必须保持兼容|旧三态显式模式、V3.1旧输出及原模型回答、201项冻结校验、Owner记录|

## 可选模型和检索

`requirements-embedding.txt`提供可选Sentence Transformers依赖；基础CI/文本回退无需下载大模型。显式build_semantic_index.py指定输出、F盘缓存和不可变revision。模型 `intfloat/multilingual-e5-small`，MIT，CPU；query:/passage:前缀、归一化、512最大长度遵循[模型卡](https://huggingface.co/intfloat/multilingual-e5-small)。[Sentence Transformers接口](https://sbert.net/docs/package_reference/sentence_transformer/model.html)支持固定revision、local_files_only和禁用远程代码。

10037参考向量预计算，模型文件、配置、向量、参考内容、ID、版本绑定。查询向量按内容缓存，不重复编码整个参考库。运行仅用本地模型；丢失/损坏/依赖不可用时记录原因并回退v31，不静默联网。其他供应商参考可使用原通用检索，Action索引不能绑定到其他目录。

保存v31、text50、semantic50、rrf50四路排名。[RRF原论文](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)的倒数排名求和默认k=60；参数可配置，未依据个例调参。RRF只决定召回次序，不作为名称分、关系分或十分制概率。最终精排候选5–20可配置；Top50只做召回比较，不能无限扩大模型上下文。

## 运行方式

`python scripts/run_selection.py --engine v32 --input <原表> --output <新F盘目录> --semantic-index <本地索引> --learning collect --mode codex`

四种learning模式：off不新增学习记录；collect只收集，不能用候选影响行为；shadow仅记录候选知识的召回差异，正式匹配保持原行为（不把shadow称为完成了语义精排）；approved要求已通过人工审批及独立验收的不可变知识文件。

同一次调用理解主体、参考关系及未知项。字面属性覆盖电池型号/电压/数量、架子层数/尺寸、刀具与盒子及配件形态。未知不补值；原AI分析和effective_analysis分别保存，主体冲突关闭同类型主参考资格，明确规格差异保留并重新计算，证据状态不作为概率。有限词表只是可核查属性守卫，不替代语言模型理解全部商品。

## 学习边界和发布

learning.sqlite3为隔离追加事件库。OBSERVED→CANDIDATE为原始观察与AI假设；SOURCE_VERIFIED需文件/hash证明；HUMAN_VERIFIED需真实审核人和理由；APPROVED_FOR_LEARNING还需明确授权。单品反馈只绑定单品，不自动变成整个品类规则。

人工反馈从主表安全回导，附 `--learning-store <库>` 可形成知识候选，仍不自动批准。manage_learning.py提供propose/review/inspect/publish；review输入审核证据JSON，publish输入包含candidate_ids、真实reviewer、regression_pass、independent_pass、不同training_ids/validation_ids和证据文件/hash的验收收据。程序核验绑定和不可变性，但不能技术认证填写姓名者的身份；操作者必须保存实际授权。拒绝合成知识正式发布。

已批准别名/类型术语用于跨SKU召回；正例提供来源绑定参考，负例只抑制被审核的配对，规格修正规则作为审核提示，不虚构原文字面属性。知识启用通过明确版本文件，回滚时选择旧发布文件或off并使用新运行目录；不改历史结果、不替换冻结库。shadow可以比较未批准假设，但不能把假设当事实发布。

主动队列每商品只占一项，按文本/语义分歧、高分缺规格、套装配件、接近的Top2、无匹配等原因排序，优先不同线索组，最多50项；全部观察仍保留。A–F未知原因独立，可同时存在E；无匹配不等于新类型。

## 验证与质量状态

新样本在运行前固定，旧40仅用于回归。本轮A为冻结v31，B为混合检索无守卫，C为同B原始模型分析加守卫（明确是离线重投影，不是另一次模型调用）。D须真实已批准知识；没有人工批准就标NOT_RUN，不复制B冒充D。

Recall需要全库核查且有相关参照集合；Precision需要独立Top1裁定。缺标签输出null而非0或100%。learning_evaluation.py保留独立评估及轻量训练资格检查，未达标签/类型/拆分条件不训练或调权。

工程、召回质量、关系质量、真实学习闭环、泛化分别验收。合成测试只能证明审批/复用/回滚机制，不代表真实人员已审或真实泛化。若无人工标准，继续交付程序、实验结果及审核材料，不授予质量和学习通过状态，不合并main。
