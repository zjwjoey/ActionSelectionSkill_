# 新100条：广泛日常需求优先的独立A/B试验

100条均已实际完成，两组各4次CLI调用，无失败、无结构重试、无缓存复用。程序为冻结e8f70004d8e0d719cbd139c2a93a1e3e9ac6da95；两个隔离上下文获得相同原名、原一级类目、来源ID、6条Action候选及本轮目标。A普通AI不加载Skill；B加载冻结V1.3说明书。运行期间没有改规则或根据结果重新抽样。

用户反馈原话：“整体其实都用不到，受众面有点窄了”，随后授权“继续下一批”。保存为原28条来源绑定的批次经营反馈，不将8组所有大类全部禁入，也不把它当作商品身份、市场销量或独立测试Gold。共同目标调整为“广泛日常用途优先”，不是以提高排除数量为目标。两组收到相同方向说明；原28条没有作为新测试商品。原8组人工确认栏保持原样，没有伪造逐组批准。

## 实际结果

| 建议 | 普通AI A | Skill B |
| --- | --- | --- |
| 保留 | 53 | 50 |
| 观察 | 19 | 21 |
| 用不到 | 28 | 29 |

两组89条决策一致、11条分歧。主对话模型对39条作重点复核，覆盖全部11条分歧；其余条目没有额外逐条裁定，不将一致视为正确。人工Gold=0、准确率未测、正式选品提升未证实。

## 分层结果及代表性

| 原抽样层 | 数量 | A 保留/观察/用不到 | B 保留/观察/用不到 |
| --- | --- | --- | --- |
| random | 60 | 31 / 9 / 20 | 30 / 9 / 21 |
| boundary | 25 | 12 / 6 / 7 | 10 / 8 / 7 |
| confusing | 15 | 10 / 4 / 1 | 10 / 4 / 1 |

从既有10月22日25,152条Amazon记录快照抽样，60随机、25边界、15易混淆；不是当前可购买SKU核验。排除历史曝光ID、规范化品名和ASIN，三项重叠均为0；密封Action50条未读取。混合样本含定向难例，不能将整体比例当Amazon全量分布。

## 11条分歧与本轮AI意见

| 编号 | 原始商品名 | A建议 | B建议 | AI辅助意见（非人工裁定） |
| --- | --- | --- | --- | --- |
| T003 | Hicarer Kit de Movimiento de Reloj de péndulo de Cuarzo con 2 Pares de ／ Mecanismo de repuesto con péndulo para reparación de relojes de pared, funciona con pilas, manecillas doradas y negras | 用不到 | 观察 | 两组均识别替换机芯；分歧是摆钟维修组件是否过于专门，不是整机/配件误认。未确定普通DIY适用范围，AI复核建议继续观察，不把本条直接推广到全部钟表配件。 |
| T023 | XLLGYL1 Set 27 Herramientas para Cerámica y Arcilla ／ Madera y metal, diseño a doble cara, con bolsa; para modelar arcilla, Fimo, porcelana fría; para principiantes y artistas | 用不到 | 保留 | 明确为手动黏土工具，且Action真实同类。A按专门兴趣排除，B按基础手工保留；与用户受众优先口径有关，不能仅以同类参照裁定B正确。建议观察等待基础手工范围确认。 |
| T024 | SATKIT Máscara Respiración Doble Cartucho con Gafas Kit Pintura Anti Gases | 观察 | 用不到 | 明确双滤盒面罩附护目镜，未误认机器。B按专门涂装防护建议用不到符合较窄目标；A询问具体作业也合理。不能由品名证明防护性能或认证不合格。 |
| T027 | Floordirekt Alfombra de pasillo 67 x 600 cm, color rojo ／ Alfombra de pasillo hecha a medida para cocina, pasillo y sala de estar | 保留 | 观察 | 标题同时给固定67×600厘米和hecha a medida。B保留定制履约疑问有字面依据；不能直接认定一定按用户尺寸定制，先观察合理。 |
| T032 | Outsunny Caseta de Jardín Exterior 1,37 m² 163x90x179 cm Gris Oscuro ／ Cobertizo de Jardín Exterior Metálico, Puerta con Pestillo, Ranuras de Ventilación, para Almacenamiento de Herramientas | 观察 | 用不到 | 储物棚主体和尺寸明确，B按庭院搭建设施建议用不到有形态依据；A观察场地条件也合理，不编造锚固或安装要求。 |
| T033 | HENGBIRD Transformador LED 12V 100W Fuente de alimentación, 230V a 12V, Fuente de alimentación conmutada, Compacta, Voltaje constante extremo, Delgada 23mm, 8.3A, AC 230V a DC 12V | 观察 | 用不到 | 12V LED电源的用途清楚，但标题没有说明裸线接线还是成品适配器。B将其直接按安装件排除可能过早；AI复核建议观察，等待供电连接形式。 |
| T040 | Cecotec Panificadora Bread&Co 1000 Delicious. 19 Programas, 1 Kg, 15 Horas programables, Cubeta Apta para lavavajillas, Recetario | 保留 | 观察 | 面包机主体明确。B仅以专门制面包用途观察，与T001全自动咖啡机保留的尺度需统一；仅品名不能证明实际受众小。建议保留经营边界问题，不将B观察当已证优势。 |
| T054 | Luz de escritorio Pac Man & Ghosts - Producto oficial, reactiva al sonido con 3 modos de luz, alimentado por USB o baterías, decoración retro para sala de juegos, regalo para gamers | 观察 | 用不到 | 标题明确游戏主题及玩家礼物定位，B用不到有本轮目标依据；A观察也可接受。不能把所有IP灯具都自动排除，需看用途与定位。 |
| T060 | Melchioni Family ／ Deshidratador Eléctrico BABELE, Deshidratador de Alimentos Multiusos, 5 Bandejas Apilables y Extraíbles, Potencia 250W, Temperatura Regulable 40–70°C | 用不到 | 观察 | 双方主体都清楚，分歧是家庭脱水机是否需求偏专门；B提出具体经营问题合理，无法用目前反馈客观计算哪组错。 |
| T068 | dreame Aqua10 Ultra Roller Complete, Robot Aspirador con Mopa AquaRoll | 保留 | 观察 | 主体是吸拖机器人，原名没有基站或自清洁系统，B没有补出这些属性。是否纳入机器人形态仍属经营边界，AI复核建议观察，不能由普通吸尘器参照放行。 |
| T079 | Orbegozo H 55 Estufa Gas Butano, 3000 W, Negro | 保留 | 观察 | 丁烷取暖炉主体清楚，但标题未说明供气与安装形式。A仅以家用用途保留可能过宽；B具体观察较稳健。不能据此假定是固定安装或移动式。 |

## 当前发现

- 专用替换电机、门机遥控器、DIN导轨电源、燃木炉等，双方能基于商品主体和使用依赖提出范围外建议，而非只看Action是否有同款。
- 泛称或作用对象匹配仍有差异；例如B不把纸张当切角器同类，T018/T093更明确组件覆盖。这些局部证据不证明整体优于普通AI。
- T033 LED电源标题未说明连接形式，B直接按安装件排除可能过早；主对话建议观察，保留原始两组结果，不偷偷改表。
- T040面包机观察、T001全自动咖啡机保留，广泛需求口径仍需一致；T023黏土工具、T054主题灯、T068吸拖机器人等是经营尺度分歧，不应伪装成事实错误。
- T090普通AI将Fondue写成“丰都料理器”，Skill保留原词较清楚；两侧最终都观察，不能由此算选品胜率。
- 题材、材质或专门用途只能支持范围建议，不能由品名证明真实受众数量、销量、利润和需求强弱。

本轮与上一轮的商品及目标均不同，不能拿“用不到”从1/2增至28/29宣称准确率或筛除能力提升。当前更明确的效果是两组都响应了目标变化，Skill的独立增益仍未获人工证实。

## 执行与资源

| 项目 | A | B |
| --- | --- | --- |
| input_tokens | 96723 | 111646 |
| output_tokens | 24637 | 24808 |
| cached_input_tokens | 0 | 0 |
| 阶段耗时秒 | 483.69 | 518.11 |
| 批次调用 | 4 | 4 |
| 结构重试 | 0 | 0 |
| 本地缓存复用 | 0 | 0 |

两组并行运行，阶段耗时不相加冒充经过时间。Token仅包含实际CLI日志，不含主对话复核，费用不可取得。各组SQLite integrity_check=ok、foreign_key_check=0；来源、字面引用、只引用所给候选及全部冻结文件检查通过。程序未变，复用e8f7000的Ubuntu/Windows通过证据，不重复全量工程测试。

## 交付与停止

匿名Excel包含100条原名、左右建议、理由、Action引用、具体未决项及重点AI复核；人工裁定/审核人/说明300个单元格全部留空。结果未按AI复核自动覆盖。原100条、150条、原28条和历史裁定均保留。

本目录保留comparison100.jsonl、ai_review.json、owner_feedback.json、metrics.json、evidence.json、两组确切提示词及交付校验。Excel另存work/next100_20261027/outputs/；身份解盲按sha256(next100-20261027:+编号)首字节奇偶决定，奇数左B右A，偶数左A右B，不能当成独立人工盲评成绩。

本轮到100条停止，不扩展500或全量。Master、原始快照、Action参考资产未修改，未合并main。下一步应围绕11条分歧及双方共同尺度问题做经营校准，而不是以排除数量增加认定Skill通过验收。
