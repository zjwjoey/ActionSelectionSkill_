# V3.3 数据驱动配对学习（显式实验入口）

默认 `run_selection.py --engine v31`、原十分制和六个 Skill 的业务权限不变。
Action 10,037 库、原始文件及历史结果只读。运行产物保存在 F 盘 `work/`，
不上传私有商品、报价、学习 SQLite、模型回答或拟合参数。

## 标签与事实分层

`pair_learning.py dataset` 复用原始请求候选与模型回答。每输入保留5个已分析
候选及3个未评价召回候选。未知不是负例；COMPONENT 表示不适合作整件主要参照，
不等于商品关系无关。AI 给出的 IDENTICAL 不能升级 VERIFIED_IDENTICAL。
事实凭证保存在独立 `source_facts` / 证据台账；整对关系仍需单独审核。

HUMAN_GOLD 要求真实独立审核人的 human: 身份、审核时间、确认记录及文件 hash。
SOURCE_ANCHORED 需要关系依据文件和可验证 hash；它不是人工 Gold。
AI_SILVER 和 UNVERIFIED 不自动晋升。导入工具验证凭证完整性与绑定，
凭证真实性仍须实际审核；工具不能证明任意填写的姓名是真人。

## 可复现的本地实验

依赖现有 requirements 的 scikit-learn/numpy。E5 使用现有本地 CPU 索引和缓存，
不微调，不新增固定第二个语言模型。命令从仓库根目录执行：

```
python scripts/pair_learning.py dataset --results <历史结果.jsonl> --requests <原请求.jsonl> --output <新数据目录> --quotes <原Action报价.jsonl> --semantic-index <既有E5目录>
python scripts/pair_learning.py train --pairs <目录/pairs.jsonl> --variant B --output <新模型B.json>
python scripts/pair_learning.py train --pairs <目录/pairs.jsonl> --variant C --output <新模型C.json>
python scripts/pair_learning.py rank --pairs <同特征版本商品对.jsonl> --model-b <模型B.json> --model-c <模型C.json> --output <新排序.json> --allow-experimental
python scripts/pair_learning.py evaluate --pairs <独立分组商品对.jsonl> --model-b <模型B.json> --model-c <模型C.json> --output <新对照.json> --allow-experimental
python scripts/pair_learning.py active --pairs <商品对.jsonl> --model-b <模型B.json> --model-c <模型C.json> --output <新待审.json> --allow-experimental
```

B 为文本/E5/检索排名特征；C 另加既有确定性属性、角色、型号和销售形式。
特征不含原AI关系、原评分、模型候选排名、SKU、平台、报价或文件路径。
排序器采用同输入内不同相关性候选的双向差分 Logistic Regression，
每个输入的对比总权重相同。标准化仅拟合训练集；C=1固定，不用最终测试调参。
输出为无界排序 utility，不是概率，也不是新的0–10分。

使用 Parent、来源商品族、标题近重复图和已有候选类型连接分组后再分训练/开发/
历史保留集。后者均为已曝光历史，只证明开发行为，不是新盲测。
全新商品单独冻结输入、模型和方法 hash。缺GTIN、型号、跨语言身份映射时，
不能保证物理同款完全隔离；已识别商品族重叠另报，不换验证商品。

## 反馈、训练版本和回滚

```
python scripts/pair_learning.py import-labels --pairs <不可变基础商品对.jsonl> --labels <真实审核.jsonl> --store <独立标签.sqlite3>
python scripts/pair_learning.py materialize --pairs <同一基础商品对.jsonl> --store <独立标签.sqlite3> --output <新版本商品对.jsonl>
python scripts/pair_learning.py register --model <新模型.json> --store <实验模型注册.sqlite3>
python scripts/pair_learning.py select-model --model-hash <已注册hash> --reason <切换或回滚原因> --store <同一注册.sqlite3> --allow-experimental
```

导入幂等；冲突必须显式 supersedes；旧数据、旧反馈和旧模型不覆盖。
新版本只用 train 标签重新拟合，再查看 dev；最终测试反馈加入训练后，
该批不再独立，必须重新冻结新测试。登记、选择和回滚只影响实验指针，
不连接默认生产入口、不等于模型发布批准。真实新标签导入前可用合成夹具验证
机制，但合成夹具和AI复核都不计真人反馈。

主动学习按前两名接近、算法分歧、主体/规格/型号/组件风险和未覆盖类型选取，
同时保留20%随机剩余商品。不得把困难样本的错误比例推算成全量准确率。

## 指标边界

同池比较限于原AI明确评价、有可比较原评分的候选。未知不计错。
无Gold时只报弱标签下的首位关系一致性、MRR/NDCG及排名变化，不称真实准确率。
全20候选实验另报；新增候选未经过原AI评价，不伪造A组分数或新关系。
未全库核实正确参照，不报完整Recall@20/50。
KNOWN_REFERENCE_IN_POOL 仅说明指定已知候选在不在召回池，不能代替Recall。

本轮模型为 `EXPERIMENTAL_WEAK_SUPERVISION`，不能自动晋升。
需要多品类独立真实审核标签与未参与调参的验证证据后，再提出正式候选验收。

实现依据：[scikit-learn LogisticRegression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html)
和 [StandardScaler](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.StandardScaler.html)。
实际环境和拟合参数以本地模型 manifest 为准，不能用新版网页替代运行版本记录。

## V3.3.1 扩样实验

累计500件来源身份去重商品，每件10候选，共5000对；优先复用原始分析。
另外对60件商品的300组未评价候选开展来源绑定AI弱标注（48件风险优先、
12件随机剩余），不把未知自动转负例。追加式标签事件保留原始空标签版本。
此前80件验证已曝光，可纳入开发，但不再充当全新测试。

分组连接使用规范代表元及成员hash排序，消除输入顺序和Python哈希种子
对拆分的影响。新一轮拆分独立冻结，不改旧拆分、旧模型或旧报告。
同一新拆分下同时训练旧150件控制组和扩大500件组，固定C=1和原有特征，
另冻结80件新输入比较；原V3.3模型也保留回放。不能把拆分变化或补标收益
全部归因为商品数量增加。所有模型仍为显式实验，不根据最终测试结果调参。
