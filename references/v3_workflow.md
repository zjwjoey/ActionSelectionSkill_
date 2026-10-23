# V3 运行与证据契约

## 目录与版本

根目录只保留一个 `SKILL.md`。`assets/`、V0.3提示词、旧结果及旧源码保持原字节。V3使用 `runtime/v3/`、`rules/v3_type_aliases.json`。默认共享学习库为 `learning_data/action_selection.sqlite3`，输出为 `work/v3/<run_id>/attempt_*`；两者均不提交。库使用专用 application_id，拒绝写入已有非V3数据库。Master及原研究库不作迁移或改写。

10,037条参照与语义候选按SKU、原始品名和来源行逐一对齐。检索候选携带具体类型、可追溯属性、用途/需求假设及语义状态，供实际AI判断使用。原1,918种类型全部可追溯，10项显式名称归一产生1,912种候选类型。尚未完成全面人工商品族整理，不强行合并997种单SKU类型。共同需求不等于同类；检索分数不是选品分数。

## 批量运行

Python 3.12，先安装根目录 `requirements.txt`。JSONL、JSON数组或UTF-8 CSV输入，至少有 `record_id` 和 `title_original`。还支持id/sku/asin等常见别名及可选source_version/snapshot_id。价格、分类等外部字段不进入品名判断；完整输入另存供追溯。

```sh
python scripts/share_tool.py verify
python scripts/share_tool.py knowledge
python scripts/share_tool.py screen --input products.jsonl --provider queue
```

`queue`不调用模型，输出待分析请求及真实Action候选，结果标为观察/NEEDS_SEMANTIC，不能当成已分析完毕。调用Skill的AI可逐条处理 `semantic_requests.jsonl`，另存结构化意见：

```sh
python scripts/share_tool.py screen --input products.jsonl --analysis analysis.jsonl
python scripts/share_tool.py screen --input products.jsonl --provider cache
```

file模式读取AI实际生成的候选，provider_calls=0表示没有通过外部命令发起调用，不等于没有AI分析。cache只复用当前代码/提示词/资产合约及来源完全一致的候选；存在不同意见时观察并报告冲突。没有候选不会假装完成语义。

需要无人逐条接力时，可接入自己的AI命令适配器：

```json
{"identity":"my-provider-v1","model":"actual-model-id","argv":["python","adapter.py"],"timeout_seconds":120}
```

适配器从stdin读取一个UTF-8请求，stdout只返回一个JSON分析对象；调用失败/超时/非法JSON进入阻塞队列。密钥通过环境变量配置，不写入仓库、argv或结果。命令配置的identity/model及适配器版本由操作者维护，换实现要更新identity。未配置实际服务时没有默认网络调用。

```sh
python scripts/share_tool.py screen --input products.jsonl --provider command --command-config provider.json
```

### 分析对象

字段：record_id、source_hash、authority=`AI_CANDIDATE`或`AI_SOURCE_BOUND_REUSE`、subject_span、subject_type、form、relation、action_sku、reference_span、reason、information_status、operating_context、coverage；functions/needs可为字符串数组候选。

- source_hash必须原样返回请求值；绑定记录ID、标题和来源版本。
- subject_span必须是原始名称字面片段；subject_type与reason必须为非空字符串。
- form：ordinary_good / bundle / universal_accessory / host_component / installed_component / whole_machine / whole_system / unknown。
- relation：same_type / related_type / specific_need / category_only / host_only / none。
- coverage：subject / partial / unknown，必须显式给出。套装全部销售主体被覆盖才用subject。
- information_status：clear / insufficient。
- operating_context：daily / specialist / large_installation / unknown，必须显式给出。
- 有参照须使用真实Action SKU和其原名的字面reference_span。none则SKU留空。

字面跨度与结构校验不能证明语义必然正确。AI仍需核对销售主体、配件宿主、适配对象、参照粒度和未证实属性。不能只把关键词命中包装为理解。

## 两个判断维度

主体理解不足进入INFORMATION_INSUFFICIENT；完成理解但边界未批准进入OPERATING_SCOPE_UNCONFIRMED。普通日用且有具体主体/同类或相关类型/具体需求参照时形成保留候选，不再仅因“小家电”固定进入灰区。专用配件仍须明确依赖关系；部分覆盖和宽泛参照不自动保留。

用不到需要来源绑定的Owner具体裁定，或已发布的经营规则。没有Action参照、只有大家电宿主词、价格高、功能多均不能直接排除。规则冲突转观察，不设排除数量目标。

## 反馈迭代

```sh
python scripts/share_tool.py feedback-bootstrap
python scripts/share_tool.py feedback-import --file actual_human_feedback.jsonl
python scripts/share_tool.py rule-propose --file candidate.json
python scripts/share_tool.py rule-validate --rule RULE_ID --cases reviewed_cases.jsonl
python scripts/share_tool.py rule-publish --rule RULE_ID --validation VALIDATION_ID --approval approval.json
python scripts/share_tool.py impact --release RELEASE_ID --run PARENT_RUN
python scripts/share_tool.py rescreen --release RELEASE_ID --run PARENT_RUN
```

所有命令可指定相同 `--db`。真实人工反馈包含record_id/source_hash/decision/authority=HUMAN/reviewer/evidence_reference/evidence_sha256。原文证据文件由操作人保存并提供SHA256；程序验证文件完整性，不具有人工身份认证能力，不能把AI意见改标HUMAN。矛盾反馈禁止覆盖，需后续显式版本裁定。

候选规则需decision、rationale、subject_types数组、forms数组、可选operating_contexts数组和support_feedback_ids数组。支持项必须是同决策的真实人工反馈，并存在落入规则范围的来源绑定语义候选。支持单项只能提出规则，不能自动泛化发布。

验证用例数组/JSONL中每项包含source、analysis、expected_decision，以及真实审核authority/reviewer和证据引用/hash。至少包含命中正例与不命中反例，全部通过才可发布。AI技术用例可测试代码，但不能用作正式规则审批标签。approval还必须绑定rule_id及完整rule_hash，提供真实人工发布证据。

发布及每次加载均复核证据、用例、规则和执行代码/资产合约；变更后需重验。增量重筛只取父批次中符合该规则的具体类型/形态/场景，复用语义缓存，记录父批次，不重跑全量Action。

## 验收

```sh
python -m unittest discover -s tests -v
python scripts/share_tool.py evaluate --run RUN_ID
```

evaluate仅在purpose=independent、来源一致、真实人工标签且未被Owner覆盖的样本上报告选择一致率和误排除数。排除已知300/500历史样本及学习库中开发/试验曝光过的ID和相同标题。已知曝光检查不是对未导入外部实验历史的全知证明，需保留完整试验登记。没有独立人工标签返回null，不输出AI准确率。选择标签不证明主体语义正确率；抽审子集不能外推总体。

`examples/v3_development`是11条已曝光开发回放，不是新样本、人工标准或准确率验收。真正新样本必须冻结代码与规则后另抽，待独立人员裁定。V3尚未自动发布任何泛化经营规则。
