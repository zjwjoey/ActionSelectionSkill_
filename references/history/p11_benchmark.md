# P1.1 候选基准与人工裁定协议

当前仍为同一批100个SKU，原始Master与原始快照不变。语义分类器规则保持name-semantics-v2；新增p11-evaluation-v1用于评价权限与数据契约，不声称完成了一轮参数训练。

候选集：`F:/ActionSelectionSkill/learning_data/p11/standard_candidates_100.jsonl`。
审核表：`F:/ActionSelectionSkill/reports/p11/100条标准候选_人工审核表.csv`。
共享数据库新增benchmark_candidates、benchmark_adjudications、benchmark_runs和benchmark_holdout_plans。
原始判断、修正判断、建议问题类型与人工确认分开保存。五种问题类型都是AI审查提议，不能直接用作标准答案。

人工审核表的列：

- `v1_original_judgment / v2_ai_correction`：原始与修正候选，均不是默认真值。
- `problem_type_proposed / assessment_basis`：AI建议的问题类型和依据。
- `human_problem_type`：人工选择AI判断错误、来源字段异常、品名信息不足、判断正确或待人工确认。
- `human_target_labels`：人工填写的JSON目标标签，例如 `{"category_l1":"家居日用","product_type":"瓶子"}`。不得由程序默填AI答案。
- `human_confirmed_fields`：对应字段列表，例如 `["category_l1","product_type"]`。
- `human_decision`：审核后填CONFIRMED、NEEDS_CHANGE或REJECTED；未审为PENDING。
- `human_reviewer_kind`：真实人工审核填写human。
- `human_reviewer / human_evidence_reference`：真实审核者及审核意见/证据定位。
- `candidate_id / candidate_hash`：绑定该轮候选；原输入另有独立哈希。

从独立项目目录运行：

```powershell
$selectionPython='F:/ActionSKUTracker/.venv/Scripts/python.exe'
& $selectionPython scripts/benchmark.py adjudicate --input '实际填好反馈的审核表.csv'
& $selectionPython scripts/benchmark.py export-gold --output learning_data/p11/human_gold_new_version.jsonl
```

导出使用新的版本文件名，不能覆盖旧gold文件。PENDING行跳过；AI身份、缺目标标签、过期哈希和缺审核依据均不放行。
实际人工身份无法仅凭字符串完成身份认证，此入口是本地授权审核记录契约，不声称提供身份验证服务。不要由AI填写human伪造审核。

复测分成两个部分：

1. 可独立验证的程序契约：100条覆盖、SKU与来源哈希、字段结构、证据词段、6条语言异常隔离、不可自行成为gold。
2. 语义准确率：只与明确人工确认的目标字段比较。没有目标时accuracy/error_rate均为null。来源异常可以测试隔离行为，但不进入西语语义准确率分母。

字符串目标采用Unicode/空白规范化后的精确匹配；用途/场景/需求/特点等多标签按集合比较，顺序变化不算错误。暂不自动判断同义词，人工需统一可接受的标准表达。
人工确认决定是human_decision=CONFIRMED；若审核的是模型review_status字段，其目标只能是待审核或信息不足，不能要求AI输出已确认。

本轮是对已有v1/v2预测分别运行修订后的契约，不是一次新模型推理或未见样本泛化评估；即使契约全部通过，也不能证明语义分类能力提高。

信息不足标准：无商品名词的品牌式名称；存在实质不同含义的多义词；无法确定主要用途或对象的跨域名词。仅缺少尺寸、材质或容量不是自动拒绝已知粗类的理由。判断保留哪些常识用途仍需人工统一口径。

下一批预留50个未见SKU，只保存来源ID与名称哈希，不做分类。去除同SKU、同规范化名称、同词头族和高重合名称，仍需独立人员检查近似泄漏。未来执行前冻结规则、提示词和评价方法，先建立独立人工答案，避免看完新样本再改规则并反复刷分。
