---
name: action-selection
description: 基于Action西班牙语品名参照库理解商品主体、用途和需求，辅助筛选Amazon或其他货盘；支持三态筛选、双轮AI实验复核、边界迭代及独立的人工规则发布。
---

# ActionSelectionSkill V3.1

唯一入口。先读[运行与证据契约](references/v3_workflow.md)中与任务有关的部分。固定使用10,037条Action参照及语义候选；V0.3旧程序/结果仍冻结在原路径，旧入口见`releases/v0.3/skill_entry.txt`。

## 执行入口

- `python scripts/share_tool.py verify`：核对完整分享包。
- `python scripts/share_tool.py knowledge`：查看参照、类型归一及需求库覆盖。
- `python scripts/share_tool.py screen --input products.jsonl --provider queue`：准备真实语义请求与Action候选。
- 由当前AI逐条理解请求并保存JSONL，再用`screen --input products.jsonl --analysis analysis.jsonl`校验及筛选。也可使用配置好的`--provider command --command-config provider.json`实际调用模型；无服务时不可声称已调用AI。
- `--provider cache`仅复用当前来源与方法匹配、无冲突的分析。复跑保持数据幂等，每次保留独立执行记录。
- 原`search`与`reference`命令仍可用；检索排序本身不作选品判断。

默认共享库位于`learning_data/`，结果位于`work/`。Master、原始快照、参照资产和历史实验只读，生成物另存。V3正式通道仅使用品名；V3.1实验可辅助使用原始一级类目，并把类目绑定到实验来源hash。不使用图片、价格、销量、评价或详情评分；官网核验可另存证据，不混入名称独立测试。

## 理解商品

先识别实际售卖主体及其字面依据，再判断形态、具体类型、用途/消费需求和经营范围。配件名称中出现的宿主不是整机；套装要检查完整覆盖。保留不确定项，不推测材质、功能、尺寸或适配关系。

Action候选同时提供原名、来源行、类型、属性及需求假设。判断真正同类、相关类型、具体需求关联、宽泛类目、仅宿主或无参照；共同需求不证明同类，品牌/材料相同也不证明等价。参照必须返回真实SKU及其原名字面片段。

分析必须包含来源hash、subject_span、subject_type、form、relation、coverage、information_status、operating_context和reason。完整schema见运行契约。AI候选不能标成人工标准。

## 三态判断

对外仅输出 **保留 / 观察 / 用不到**，内部分别保存理解状态、经营范围状态、具体参照及证据。

- 保留：主体明确、普通日用、具体参照能覆盖销售主体，形成研究候选；普通小家电不因旧灰区标签自动观察。
- 观察：未执行语义、信息不足、部分套装覆盖、只有宽泛/宿主参照、依赖或经营边界未确认、规则/候选冲突。标明具体原因，区分“不认识商品”和“边界未裁定”。
- 用不到：仅凭来源绑定的Owner具体裁定，或完成正例/反例验证和人工发布的经营规则。缺少Action参照不能单独排除，不追求任何排除比例。

输出原始名称、三态、主体及形态、理由、参照SKU/原名/关系、未确认项、来源与方法版本。用不到也是复核建议，不删除原商品。

## 学习与验证

真实人工反馈经`feedback-import`保存；既有3条Owner裁定由`feedback-bootstrap`导入，只作用于对应来源记录。规则通过`rule-propose → rule-validate → rule-publish`发布，需明确类型/形态范围、真实支持反馈、正例及反例、来源绑定的人工用例和发布证据。AI可以准备候选与技术测试，不能伪造人工审批。用`impact`和`rescreen`增量处理受影响商品，不重学Action全库。

本Skill是参照知识、程序、提示词与反馈机制，没有微调权重。类型归一仍属候选，尚无独立验证的正式准确率。冻结规则后抽新样本，登记既有曝光；`evaluate`只在真实独立人工选择标签上报告受审子集一致率及误排除，不以AI自评验收AI，也不外推总体。

## AI自主实验通道

本次64条复核后的观察修复入口为 `experiment-compare-reviewed --input products.jsonl --mode codex`，详见[观察修复契约](references/reviewed_observation.md)。它对同一份双轮分析保存旧校准判断和新判断，修复同类多件装粒度、弱参照阻断与通用配件问题；定制、主体冲突和未确认经营边界继续观察。原命令及历史结果保留，未经验证不替换正式筛选结果。

需要自主模型分析、复核或边界实验时，读[自主实验运行契约](references/v31_autonomous.md)。使用显式`experiment-*`命令；原V3正式命令及人工门禁保持独立。

- 实际执行：`experiment-screen --input products.jsonl --mode codex`。先确认现有ChatGPT登录的Codex CLI可运行；没有可用模型时保留队列和失败证据，不自行购买或切换付费API。
- 同一输入用独立临时上下文分别理解和反例复核，复核请求不含初始答案。两轮分歧未解决时观察。分别保留Action匹配强度和经营边界，不能用相似需求代替同类，也不能以无参照为排除理由。
- 从真实开发记录提出`AI_EXPERIMENTAL_BOUNDARY`候选，经多个支持案例、反例及来源绑定验证后显式发布实验版本，再增量重筛受影响记录。最多两次实验迭代，规则不得按品牌、型号或SKU逐项排除。
- AI实验事件使用同一共享SQLite中的独立`v31_events`命名空间，不导入人工Gold，不调用正式`rule-publish`。实验结果必须标识非正式发布，不能覆盖旧判断或删除商品。
- 冻结规则后才抽独立样本；独立验证记录不得作为该规则的开发支持。技术回归、AI一致与判断变化均不等于实际准确率。
