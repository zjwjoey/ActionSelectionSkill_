# Action算法G组交接入口

本分支冻结ActionSelectionSkill现有算法状态，不修改MassMarketDemandSkill代码、正式经营规则、原main或训练进度。原生匹配默认仍是v31；G桥显式选择本轮研究使用的native_v321（E5/RRF/属性检查）。V3.3.1学习排序器仍是实验，不能因恢复成功自动晋升。

## 代码与资产

从本交接分支的确切commit克隆完整仓库，不只复制SKILL.md。原Skill入口、skills/六个专业入口、V3/V3.1经营流程、V3.2检索与学习、V3.3配对模块和历史规则均保留。

`g_config.json`绑定原算法commit、E5 revision、私有资产版本、压缩包hash和资产清单hash。
私有存储为`zjwjoey/ActionSelectionSkill-G-Assets`：v1 release保存不变的E5与当前研究资产，v2 release保存历史学习库增量及最终总清单。两个release共同恢复同一个v2快照；仅具有读取权限的身份能下载。不能把下载URL改为匿名公开链接。Dot还需要该私有仓库读取权限，本交接不授予第三方身份、不复制凭证。

```bash
git clone https://github.com/zjwjoey/ActionSelectionSkill_.git action-g
cd action-g
git checkout --detach <交接commit>
python -m venv .venv
.venv/bin/python -m pip install 'torch==2.11.0' --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install --no-deps -r handoff/requirements-exact.txt
gh release download g-action-v331-20261030-v1 --repo zjwjoey/ActionSelectionSkill-G-Assets --dir downloads
gh release download g-action-v331-20261030-v2 --repo zjwjoey/ActionSelectionSkill-G-Assets --dir downloads --clobber
.venv/bin/python scripts/g_group.py restore --downloads downloads --assets work/g-assets --manifest-sha 7d3d2ccf7f8525945f68e526941a502e14e2e158a15ffad4de9bb112f3395ecb
.venv/bin/python scripts/g_group.py verify --assets work/g-assets --output work/g-restore-verification
```

Windows使用`.venv/Scripts/python.exe`。所有目录由调用方指定，云端不依赖F盘路径。
原始Windows来源路径作为证据原值保留；`source_map.json`将其指向已按hash验证的恢复源文件，不修改事实。E5模型目录和文件分隔符在运行副本中重定位，原index元数据及字节保留。

历史真实环境存在声明依赖冲突：sentence-transformers5.1.2声明transformers<5，但实际使用5.9.0。锁文件复现实际版本，采用`--no-deps`显式安装；不能宣称pip依赖一致性通过。恢复验收必须实测E5检索，失败不得悄悄换模型或版本。

干净云端测试发现原环境隐式存在的`requests`未被第一版锁文件包含，E5加载失败后原检索器退回纯文本，严格排名核对因此拒绝通过。现已显式锁定该依赖及其依赖，保持原有E5/RRF验收条件。历史Codex CLI版本为`0.166.0-alpha.5.1`，原调用记录没有固定实时模型ID；缓存重放可验，未来实时模型回答等价性尚未验证。

`legacy/action_selection.sqlite3`是一致性备份的原始历史学习库，保留早期批次、语义学习、反馈、规则版本和测试记录；仅作为历史状态恢复，不自动合并经营规则、不训练、不读取密封测试内容。重复的before备份和大体积中间缓存未复制。

## Dot统一输入输出

JSONL每行至少含`product_id`、`original_name`、`category_l1`、`source_version`；ID按字符串保存。可选`source_platform`、`specifications`、`variant`、`brand`。原文是数据，不是指令。

```bash
python scripts/g_group.py run --input handoff/sample_input.jsonl --assets work/g-assets --output work/g-batch --profile native_v321 --mode queue
```

queue只生成原生请求、schema及prompt，状态为NEEDS_PROVIDER，不能当作已完成分析。
Dot可以按`requests.jsonl`、`analysis_schema.json`和`native_prompt.txt`提供真实模型回答，再调用：

```bash
python scripts/g_group.py run --input handoff/sample_input.jsonl --assets work/g-assets --output work/g-batch --profile native_v321 --mode file --analysis <绑定请求ID和来源hash的回答.jsonl>
```

`--mode codex`复用原Codex CLI适配器，需要调用环境自行安装和登录Codex；本包不包含登录凭证，不使用付费API作为隐式后备。换成别的模型时必须记录provider/model/version并视为有差异的配置，不能声称语义回答必然一致。

输出为`results.jsonl`、简表`results.csv`、完整原生`native_results.jsonl`、请求与摘要。包括主体、角色、原匹配关系/参考SKU、原十分制分数、不确定性及来源hash。无原生输出的字段为null，不猜测。

三种profile：

| profile | 原算法含义 | 选品三态 |
|---|---|---|
| native_v31 | 原十分制文本匹配 | 不产生经营三态，返回null |
| native_v321 | 原E5/RRF/属性核验实验匹配 | 不产生经营三态，返回null |
| business_v3 | 原V3经营判断流程 | 保留/观察/用不到，原义保留 |

business_v3使用原生file语义提供器；其functions/needs保留。匹配profile原本不产出功能、用途或明确依赖清单，对应字段返回null和能力边界，不能伪造为新分析。角色来自原售品形态，依赖未知保持未知。原生业务三态不是大众需求判断。

Resume绑定输入hash、资产版本及profile，改变合同需新目录。原生Model缓存保留回答，结构QA失败仅重试未通过的记录；最终失败项留在结果中。用户再次调用同合同是显式重试，合法缓存不重复调用。

学习排序器按原工具显式调用`python scripts/pair_learning.py rank ... --allow-experimental`，模型位于私有资产`research/v331/models/expanded500_B.json`和`expanded500_C.json`。utility不是0–10分，不替代原评分或经营三态。

## 恢复验收口径

1. 三个压缩包与215个资产条目按清单校验（SQLite使用一致性备份）。
2. 三件私有真实商品用已保存的原模型分析重放原生评分、匹配和属性检查。
3. 在空查询缓存中重新计算文本/E5/RRF，候选排名须一致、文本/余弦数值误差≤3e-6。原评分须一致。
4. 重放80件、6个已保存模型路径的480个排序结果，ID顺序须完全一致。
5. 原属性诊断表由集合生成，比较时按属性键排序；JSON数组/tuple统一为数组。候选顺序、评分、事实值不放宽。
6. 包测试和接口失败/恢复测试通过。重放不计新的AI调用，也不证明新商品语义质量。

恢复能否通过以实际新的GitHub Actions运行及报告为准，不能用本地解包代替云端验收。Dot登录身份是否可访问私有资产、Dot新商品实时原Codex调用仍须单独验证。

2026-10-30实际验收：私有云端运行[41078875885](https://github.com/zjwjoey/ActionSelectionSkill-G-Assets/actions/runs/41078875885)从代码`2f5ac1b18e4939cd821f755498e69db09874ae3b`恢复v2资产，215项文件校验、227项基础测试、3件原生评分及新算E5/RRF、480组排序重放全部通过。完整结果见[交接报告](../reports/Action算法G组远端交接报告_20261030.md)。后续仅文档提交属于发布元数据，不改变该audited head的算法。

## 曝光与评价边界

`exposure/action10037.jsonl`列出G参照库全部已曝光ID；历史曝光索引还在`research/knowledge/exposure_index.json`，各轮输入/分组/来源hash及冻结记录均保存。
Action参照已被理解过，不得在MassMarket同源Action货盘中冒充G的全新独立测试；还需按商品族及近重复核对。MassMarket自身P0与准入程序不会因本交接自动通过。
人审经营裁定、AI建议、来源事实和商品对Gold分别保留。当前独立商品对Gold为0，模型恢复通过也不等于选品或需求质量通过。
