# ActionSelectionSkill

V3统一筛选开发候选版，2026-10-23。V0.3历史结果及10,037条Action参照保持冻结。

使用入口为根目录的[SKILL.md](SKILL.md)。将整个仓库交给AI读取，或作为一个完整Skill目录安装。仅复制SKILL.md不会携带参照库和配套程序。

## 已包含的成果

- 10,037条Action西班牙语品名参照与对应语义候选。
- 商品类型、用途、消费需求关联及候选规则。
- 当前判断程序与历史源代码，保留一个Skill入口。
- 最近300条和500条实验记录。
- 用户确认的3条具体商品选品反馈，未扩大为整类规则。

最近500条随机样本的AI候选为229条保留、271条观察、0条用不到。尚未获得独立人工验证的正式准确率，不能据此证明排除能力。

## 使用

本地检索已使用Python 3.12验证：

```sh
python -m pip install -r requirements.txt
python scripts/share_tool.py verify
python scripts/share_tool.py info
python scripts/share_tool.py search --title "Pulverizador de aceite para cocina" --top 5
python scripts/share_tool.py reference --sku 3222901
```

V3批量入口接入参照类型、属性和需求候选；支持当前AI的结构化意见、精确来源缓存和可配置的实际AI命令适配器。缺少分析时明确输出待分析队列，不伪装成完成。

```sh
python scripts/share_tool.py knowledge
python scripts/share_tool.py screen --input products.jsonl --provider queue
python scripts/share_tool.py screen --input products.jsonl --analysis analysis.jsonl
python -m unittest discover -s tests -v
```

新设备上无需原始大型SQLite：程序在`learning_data/`建立专用共享学习库，执行记录另存`work/`。反馈、规则提议、正反例验证、人工发布和受影响商品增量重筛已提供命令。完整说明与schema见[V3运行契约](references/v3_workflow.md)。

参照索引使用joblib序列化，仅加载来源可信的文件。本仓库文件可用manifest.json校验。Git保留文件原始字节，避免跨平台换行转换导致校验失效。

## 数据与版本边界

本仓库包含AI候选知识、提示词、规则和程序，没有语言模型微调权重。Master、生产数据库、大型备份、密封50条及账号配置未包含。原始项目和历史输出没有被本次同步覆盖。

`runtime/`保留历史源码；旧历史运行器依赖原工作区，V3便携入口不依赖该工作区或未打包的历史数据库。当前11条开发回放是已曝光样本，仅验证流程；不能证明准确率提升。原1,918类型只作保守归一到1,912个候选类型，全面商品族整理仍待进一步复核。没有自动发布新的泛化经营边界。

“用不到”保留为可复核的建议，不自动删除原始商品。AI意见不充当人工确认标签。
