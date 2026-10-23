# V3.1 AI自主实验运行契约

本通道复用`runtime/v3`的只读Catalog、分析校验、正式策略校验及Store。新增实现位于`runtime/v31`，不改V3原算法、人工反馈或发布函数。Action固定参照仍为10,037条；不重新学习Action，不接触密封50条。

## 实际模型执行

```sh
python scripts/share_tool.py experiment-screen --input products.jsonl --mode codex --purpose smoke --batch-size 10
```

依赖已安装且可使用现有ChatGPT登录的Codex CLI。每批两次独立`codex exec`，在空执行目录中启动临时只读会话，输入只有品名、可选一级类目和实际Action候选原名。二轮不读取第一轮结论；保存请求、响应、事件hash、使用量及耗时。禁用用户配置加载，不读取API Key；不提供自动切换付费API的路径。配置、账号额度或网络不可用时停止新增调用并留下待处理记录。

模型不得调用文件、网络或命令工具；检测到这些事件则该批不作为成功分析。CLI默认模型由实际运行日志记录；同一模型的不同上下文不是独立人工审查。

可用`--analysis first.jsonl --review second.jsonl --mode file`校验当前模型实际生成的结构化意见。文件路径不同不代表两轮独立；外部使用者需保留生成证据。`--mode queue`只准备请求，不计完成或模型调用。

## 来源与结果

输入需要`record_id`、`title_original`，可附`category_l1_original`及`snapshot_id`。实验来源hash绑定ID、原始品名、一级类目和版本；不替换V3来源hash，也不把旧人工批准自动转绑到实验hash。

输出仅保留/观察/用不到三个决策，并记录两轮语义、匹配强度、经营边界、参照、未决信息、分歧层及版本。初始判断、复核判断及最终实验建议分开。主体、参照或边界存在未解决分歧时维持观察；AI标记范围外本身不足以生成用不到，须有通过验证的实验规则或有效正式证据。

## 候选规则与版本

规则JSON需要`channel=AI_EXPERIMENTAL_BOUNDARY`、`authority=AI_CANDIDATE`、`version`、`decision`、`rationale`、`conditions`、`support_ids`、`counterexample_ids`。

`conditions`包含可复用的`families`、售卖形态`forms`、具备原题字面证据的`features_all`。若受控的正向主体身份特征已定义商品类型，`families`可为空，避免中文自由标签的措辞阻断同类泛化；仍须至少两项正向特征，单一用途或场景不够。不接受SKU、品牌、型号正则或“找不到参照”作为条件。用不到规则要求完整销售主体及至少两个不同原文字面锚点，机器规则不能作用于宿主配件。

```sh
python scripts/share_tool.py experiment-propose --file candidate.json
python scripts/share_tool.py experiment-validate --rule EXPERIMENT_RULE_ID --execution DEVELOPMENT_EXECUTION_ID
python scripts/share_tool.py experiment-release --rule EXPERIMENT_RULE_ID --validation VALIDATION_ID
python scripts/share_tool.py experiment-rescreen --execution BASE_EXECUTION_ID --release RELEASE_ID
```

开发支持至少包含两个不同标题、不同来源hash的商品及两个反例，两轮各自有来源绑定语义。正例要在两轮均满足条件、边界与候选结论一致；反例不得被误触发。技术PASS不证明经营标准正确。发布前验证规则hash、源码和数据契约未变；父版本通过`--parent`指定，最多两次迭代。

新实验版本只增量重筛语义条件命中的记录，复用已完成的来源绑定模型分析；保留父结果及差异。回退使用父执行或旧release，不删除记录。正式`feedback-import`和`rule-publish`仍需要真实人工证据。

## 证据边界

开发、冒烟和独立技术验证分别标记。独立/全量结果不可作为候选规则的开发支持。冻结版本后才选择新验证样本，保存抽样种子、已曝光排除记录与源文件hash。随机层和定向层分开报告，不用偏难样本推算总体效果。

先完成50条冒烟、500条开发及200条独立技术验证。只有实际模型执行、来源绑定、数据完整性、排除保护及技术回归均通过且资源可用，才进入冻结版本全量实验。队列或本地规则回放不能冒充全量AI语义分析。全量实验期间不改规则。

验收报告分别记录模型实际分析数、二轮复核数、失败/待处理、来源与参照风险、规则正反例及影响范围。正式准确率、误排除率和召回率在缺少独立人工标签时保持未验证。

Codex结构化执行接口参考：[OpenAI官方迭代修复示例](https://developers.openai.com/cookbook/examples/codex/build_iterative_repair_loops_with_codex)。具体CLI参数以部署机器`codex exec --help`为准。
