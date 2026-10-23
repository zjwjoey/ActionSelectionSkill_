# ActionSelectionSkill

当前可分享版本，打包日期为2026-10-23，商品边界方法为冻结的V0.3候选版本。

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

检索工具返回Action候选参照，由接收方的AI继续核对商品主体、参照关系和经营范围，输出**保留 / 观察 / 用不到**。脚本不会独立调用语言模型，不需要API密钥。

参照索引使用joblib序列化，仅加载来源可信的文件。本仓库文件可用manifest.json校验。Git保留文件原始字节，避免跨平台换行转换导致校验失效。

## 数据与版本边界

本仓库包含AI候选知识、提示词、规则和程序，没有语言模型微调权重。Master、生产数据库、大型备份、密封50条及账号配置未包含。原始项目和历史输出没有被本次同步覆盖。

`runtime/`保存原程序源码供审查；完整历史运行器依赖原工作区和未打包的历史文件。跨设备使用入口为`scripts/share_tool.py`和SKILL.md，具体边界见[当前方法](references/current_method.md)及[使用说明](使用说明.txt)。

“用不到”保留为可复核的建议，不自动删除原始商品。AI意见不充当人工确认标签。
