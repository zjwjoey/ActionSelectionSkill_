"""Describe the frozen experiment without converting AI labels into Gold."""
import collections,json
from pathlib import Path
from assortment import ROOT,lines,read
import boundary_validation_v03 as v
import run_boundary_validation_v03 as run

def main():
    run.check();rows=lines(v.OUT/'validation300_results.jsonl')
    summary=read(v.OUT/'validation_summary.json');comparison=read(v.OUT/'development_comparison.json')
    persist=read(v.OUT/'persistence.json');groups=read(v.OUT/'key_boundaries60.json')
    dev=lines(v.OUT/'development60_results.jsonl');frozen=read(v.OUT/'frozen_v03.json')
    sections=['# Boundary V0.3：60条边界修复与新300条验证','',
        '本轮完成60条开发案例的关键边界整理、通用程序修复、规则冻结和新300条语义验证。Master、原始快照、Action10037索引和历史结果均保留；未启动全量重筛。',
        '',f"冻结时间：{frozen['frozen_at']}。共享学习库运行ID：`{persist['run_id']}`。",'',
        '## 60条关键问题与程序修复','',
        '原60条归为12类。修正6处没有品名依据的属性：立杆形态、塑料材质、锂电化学体系、裸式模块、便携形态、三水箱。修正保留原问题及来源记录。',
        '',
        '程序现在分别核验来源/提示词/方法版本、AI身份、销售形态与依赖关系、经营边界及字面整机证据。宿主配件不能继承整机排除，未知形态保持待复核。机器人功能数量与门驱动系统不再自动构成已确认经营排除。',
        '',
        '原V0.2开发60条：'+str(comparison['before'])+'；本轮：'+str(comparison['after'])+'。这是同一开发集的变化，不计算独立准确率。',
        '',
        '|关键边界|条数|纳入候选|待复核|暂不纳入|', '|---|---:|---:|---:|---:|']
    for g in groups:
        rr=[r for r in dev if r['review_id'] in g['review_ids']];counts=collections.Counter(r['decision'] for r in rr)
        sections.append('|'+g['name']+'|'+str(len(rr))+'|'+ '|'.join(str(counts[s]) for s in ['纳入候选','待复核','暂不纳入'])+'|')
    sections+=['','固定整机分组包含滑动门驱动案例，其最终结果为待复核。早期边界草案保留原文，最终逐项结果与上表为本轮有效候选。','',
        '## 冻结后的新300条','',
        '从25,152条URL来源记录中抽取，不代表已核实的可购买SKU数量。200条普通随机样本先抽，另抽50条边界专项和50条依赖专项。三组分别统计。',
        '',
        '避开已参与专门语义复核/测试的标题，并追查同一ASIN换标题的身份重叠；300条标题唯一、300个ASIN提示唯一，已知专项历史重叠为0。原快照曾经过V0机械筛选，不称为从未运行过任何程序的商品。未读取密封50条测试内容。',
        '',
        '|样本组|条数|纳入候选|待复核|暂不纳入|','|---|---:|---:|---:|---:|']
    for k,name in [('random','普通随机'),('boundary','边界专项'),('dependency','依赖专项')]:
        c=summary['cohorts'][k];sections.append('|'+name+'|'+str(c['n'])+'|'+'|'.join(str(c['states'].get(s,0)) for s in ['纳入候选','待复核','暂不纳入'])+'|')
    sections+=['','专项样本刻意增加边界难例，合并比例不能推算全量错误率。逐条语义由实际AI分析完成，程序负责来源、形态、参照及三态门禁；没有把Python规则冒充语言模型。','',
        '### 待复核原因','', '|原因|数量|','|---|---:|']
    pending=collections.Counter(r['review_reason_code'] for r in rows if r['decision']=='待复核')
    names={'INFORMATION_INSUFFICIENT':'供货或形态信息不足','DEPENDENCY_REVIEW':'专用或安装配件','OPERATING_BOUNDARY_UNCONFIRMED':'经营边界未确认','REFERENCE_ABSENT':'缺少有效Action参照','REFERENCE_TOO_BROAD':'参照关联过宽','REFERENCE_COVERAGE_INCOMPLETE':'参照仅覆盖套装部分','BOUNDARY_EVIDENCE_CONFLICT':'整机边界证据冲突','SCOPE_KIND_CONFLICT':'范围与主体种类冲突'}
    for k,n in pending.most_common():sections.append(f'|{names.get(k,k)}|{n}|')
    sections+=['','### 本轮排除候选的字面证据','', '|案例|主体候选|整机证据|','|---|---|---|']
    audits={r['record_id']:r for r in lines(v.OUT/'validation300_bound.jsonl')}
    for r in rows:
        if r['decision']=='暂不纳入':sections.append('|'+r['review_id']+'|'+r['subject']['class_code']+'|'+audits[r['record_id']]['boundary_evidence_span']+'|')
    sections+=['','## 发现与使用范围','',
        '新样本仍出现词面检索被材质、套装、宿主或用途词带偏的情况。实际AI可在冻结Action库中补查具体类型，但这表明检索排序仍需改进。缺少具体参照、参照过宽、主体信息不足和经营范围未确认保留独立原因。',
        '',
        '本轮验证期间没有改冻结规则。各组发现保存在findings_a/b/c.json，后续单独AI诊断保留为候选意见，不反向覆盖本轮结果。',
        '',
        '补充来源复核发现3个优先疑点：N038虽是燃气热水主机，但品名未证明固定安装，暂不把该条当作正确排除；N037仅有喷瓶形态参照，不能证明厨房喷油用途；N065的Action mando不能仅凭品牌语境确定为游戏手柄。原冻结结果保留，疑点及待复核建议另列。',
        '',
        '本轮结果可供人工复核，暂不进入自动排除或全量筛选。独立人工Gold为0，主体识别准确率、参照有效率、错误排除率与漏保留率均未测量。程序检查通过不能代替正式选品能力验收。',
        '',
        '## 程序检查与数据保护','',
        '- 沿用冻结前15项专项测试通过的结果，另含10个枚举子场景；未重复执行已通过的全量测试。',
        f"- 冻结文件hash核验通过；{persist['protected_files_unchanged']}个受保护文件hash一致。Master未修改。",
        f"- {persist['eligible_references_verified']}个本轮实际使用的Action参照SKU已核对冻结库及共享库来源行。",
        f"- SQLite integrity_check={persist['integrity']}，foreign_key_check异常={persist['foreign_key_violations']}。",
        f"- 本轮新增{persist['new_rows']}条版本/结果/缓存记录；重复持久化新增{persist['resume_new_rows']}条。历史boundary行内容与其他学习表数量均保持一致。",
        '- 汇总期间B组完成N132说明和N173参照的最终修订，早期141/158/1快照完整保存在attempt1_before_final_b及原数据库run中。最终140/159/1已按最终笔记重新对齐。新run同时绑定规则hash和审查文件hash，不覆盖早期快照；没有重复调用AI分析全部商品。',
        '- 没有写入人工反馈或正式规则发布；没有调用外部翻译/模型API。实际Codex会话模型精确ID与账单未暴露。',
        '',
        '## 保留文件','',
        '- 程序：v2/boundary_validation_v03.py；冻结流程：v2/run_boundary_validation_v03.py。',
        '- 冻结提示词：rules/boundary-v0.3/prompt.md。',
        '- 新300条原始样本、逐条AI笔记、来源绑定记录、程序结果、各组发现与最终统计均在本轮run目录。',
        '- 60条原始开发意见、6处修正、12类关键边界和前后对照均保留。',
        '- Excel提供300条逐项结果及空白人工裁定/原因/审核人/证据栏。填写不直接登记为Gold。',
        '',
        '本轮结束于300条验证，不自动继续新的版本开发或全量筛选。','']
    text='\n'.join(sections)
    destination=ROOT/'outputs/boundary_v03_20261023';destination.mkdir(parents=True,exist_ok=True)
    p=destination/'BoundaryV03_修复与验证报告.md'
    if p.exists():assert p.read_text(encoding='utf-8')==text
    else:p.write_text(text,encoding='utf-8')
    print(json.dumps({'report':str(p),'total':summary['total'],'pending':dict(pending)},ensure_ascii=False))

if __name__=='__main__':main()
