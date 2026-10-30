# 跨平台共享商品研究引擎

V3从V2.1分支隔离开发。旧main、V1.4、V2、V2.1实验保持历史含义，五个新Skills共用 `runtime/retail` 与一个模型批次。无需按Skill顺序重复调用模型。

## 直接运行

```powershell
python scripts/run_selection.py --input products.xlsx --source auto --reference action --output F:/ai文件/selection_run --mode codex --source-date 2026-10-30 --price-type retail --quotes F:/ai文件/private/action_latest.jsonl
```

输入支持Excel、CSV、JSONL。自动识别ASIN、货号、SKU、原品名、规格、变体、价格等常见字段；未识别字段保留在source_evidence。平台无法自动判断时显式 `--source supplier_name`。内部product ID跟随平台原ID，quote ID跟随文件hash/工作表/原行，不跨平台合并身份。缺原ID使用可追溯来源行ID，多次报价均保存。

日期未给出不猜今天。明确币种可由单元格格式、币种列、EUR表头或 `--currency` 的用户来源声明提供；不得根据平台国家猜测币种。报价类型默认unknown；供应商批发用 `--price-type wholesale`，不与零售直接做同口径L2/L3。

Action召回复用现有冻结检索。`--quotes` 可读已有Action历史来源JSONL，不传时保留参考匹配、价格显示未知。SKU原名绑定失败时不能使用该规格或报价做比较。未来参考目录可用 `--reference other_catalog.jsonl`，通用目录走轻量字符串召回，性能和语义能力须另验收，不冒称与Action冻结索引等效。

`--mode codex` 调用既有登录的Codex CLI与来源绑定缓存；不使用API Key付费回退。`queue` 保存待处理请求、状态为INCOMPLETE，不能叫完成。`file --analysis answers.jsonl` 只接收有来源hash的真实分析文件；导入不伪造模型调用。批量大小1–25，默认10。`--limit` 仅用于明确的小批量验收，省略则处理所有有效行。

同一输出目录再次执行相同命令即Resume。输入、参数或方法变化会拒绝续写，需新目录；不删除旧结果。单批失败保留原因和未完成记录、继续其他批次；再次运行仅请求未缓存记录。完整JSON/SQLite是证据主记录，Excel为研究发布结果。

输出 `outputs/selection_v3/选品研究.xlsx` 有选品结果、需人工复核、运行与来源说明三张表。需要桌面捆绑的Node/Artifact Tool运行库；可用 `V3_RUNTIME_DEPENDENCIES` 指定已有运行库路径。导出临时文件与模块链接位于F盘输出目录，无自动依赖安装。`--no-export` 用于无桌面运行库的测试或暂缓导出。

## 人工反馈

读取results.jsonl相应记录，使用 `runtime.v3.core.digest(record)` 计算结果hash，再执行：

```powershell
python scripts/run_selection.py --output F:/ai文件/selection_run --feedback-id <record_id> --expected-hash <hash> --decision 保留 --reviewer <真实审核人> --reason <理由> --kind business
```

可选决策：接受建议、保留、观察、用不到、事实匹配错误、价格或规格错误。kind可为business/fact/price。实际审核人自行提交；不自动冒充人工。事件保存原建议、修改、理由、时间、原结果hash和方法，原AI记录不改写。反馈只用于后续来源绑定修复或候选经营方法修订，不自动发布全类规则。

## 实际复用与限制

- 直接复用：Catalog冻结索引、V31真实模型适配器/事件存储、V2三权重与字面包装校验、V2.1数量解析、V1.4证据分级经营方法。
- 跨平台适配：输入身份不再依赖ASIN；L1采用源文件与平台原ID，L2独立检查零售/批发口径，历史价与身份分开。
- 修复风险：单条空品名留错误记录；身份绑定、片段、重复引用、缓存上下文、未知币种与空数量均有程序检查。
- 历史模块：旧queue实验、A/B与严格C保留，不串进新版默认流水线。
- 新增：统一CLI、三态输出、Excel、来源记录和人工反馈事件。

主体、关系与经营建议属于AI候选；价格换算正确不证明同款。IDENTICAL需要独立型号/GTIN/规格核验，本版不让AI自动授予。匹配指数不是概率；价格不会决定商品身份。原料、耗材、配件与宿主必须区分，功能推测与来源事实分开。无独立事实标签或Owner业务验收，最终只标记ENGINEERING_READY / DECISION_QUALITY_UNVERIFIED。
