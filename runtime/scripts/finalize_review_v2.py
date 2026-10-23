"""Reconcile this review against the pre-review learning DB and publish audit views."""
import csv
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

import storage
from pipeline import ROOT,canonical,digest,filehash,load_rules,validate_snapshot,immutable
from review_pilot_v2 import SID,BATCH,ROUND


def main():
    out=ROOT/'reports'/SID/BATCH/'name-semantics-v2'
    before=json.loads((ROOT/'reports/review_v2_before.json').read_text(encoding='utf-8'))
    olddb=sqlite3.connect(Path(before['backup']).as_uri()+'?mode=ro',uri=True)
    db=sqlite3.connect((ROOT/'learning_data/action_selection.sqlite3').as_uri()+'?mode=ro',uri=True)
    invariants={}
    for table,order in [('snapshots','snapshot_id'),('source_rows','source_row_id'),('products','snapshot_id,sku'),('batches','batch_id'),('sample_members','batch_id,sku'),('feedback','seq')]:
        a=olddb.execute('select * from '+table+' order by '+order).fetchall()
        b=db.execute('select * from '+table+' order by '+order).fetchall()
        assert a==b,table
        invariants[table]={'unchanged':True,'rows':len(a),'logical_sha256':digest(a)}
    old=olddb.execute("select * from analyses where rules_version='name-semantics-v1' order by seq").fetchall()
    retained=db.execute("select * from analyses where rules_version='name-semantics-v1' order by seq").fetchall()
    assert len(old)==100 and old==retained
    assert db.execute('select count(*) from analyses').fetchone()[0]==200
    assert db.execute('select count(distinct sku) from analyses').fetchone()[0]==100
    versions=db.execute('select version,content_hash from rule_versions order by version').fetchall()
    for version,expected in versions:assert digest(load_rules(version))==expected
    assert [v[0] for v in versions]==['name-semantics-v1','name-semantics-v2']
    db.close();olddb.close()
    manifest=validate_snapshot(SID)
    assert filehash(manifest['source'])==before['master_sha_before']==manifest['source_before']['sha256']
    for name,expected in before['rules_v1_files'].items():assert filehash(ROOT/'rules/versions/name-semantics-v1'/name)==expected
    current,fb=storage.state(ROOT,BATCH);assert not fb
    history=storage.history(ROOT,BATCH);parents={x['sku']:x for x in history if x['rules_version']=='name-semantics-v1'}
    assert all(x['ai_review']['parent_annotation_hash']==parents[sku]['annotation_hash'] for sku,x in current.items())
    assert len(list(ROOT.rglob('SKILL.md')))==1
    tests=(ROOT/'reports/targeted_tests_v2.log').read_text(encoding='utf-8-sig');assert re.search('Ran 11 tests',tests) and 'OK' in tests
    assert 'Skill is valid!' in (ROOT/'reports/skill_validation_v2.log').read_text(encoding='utf-8-sig')
    retry=json.loads((ROOT/'reports/actual_resume_v2.json').read_text(encoding='utf-8-sig'));assert retry=={'imported':0,'already_present':100,'total_current':100}
    comparison=json.loads((ROOT/'reports/version_comparison_v1_v2.json').read_text(encoding='utf-8-sig'));assert len(comparison)==100 and all(len(v)==2 for v in comparison.values())
    reviews=json.loads((out/'review_decisions_100.json').read_text(encoding='utf-8'))
    priority=[x for x in reviews if x['priority_from_v1']];assert len(priority)==29
    columns=['sku','name_es_original','before_confidence','after_confidence','before_status','after_status','decision','reason','uncertainty_codes','changed_fields','source_row_id','parent_annotation_hash']
    for name,rows in [('priority_29_review.csv',priority),('all_100_review_changes.csv',reviews)]:
        with (out/name).open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader()
            for x in rows:writer.writerow({k:canonical(x[k]) if isinstance(x[k],(dict,list)) else x[k] for k in columns})
    unresolved=[{'sku':x['sku'],'name_es_original':x['name_es_original'],'reason_codes':x['uncertainty_codes'],'reason':x['ai_review']['reason'],'source_row_id':x['source_row_id']} for x in current.values() if x['review_status']=='信息不足']
    immutable(out/'remaining_15_information_insufficient.json',unresolved)
    report=json.loads((out/'review_import_result.json').read_text(encoding='utf-8'))
    report.update({'scope_unique_skus':100,'historical_analysis_records':200,'v1_analysis_records_unchanged':True,'source_and_sample_invariants':invariants,
                   'master_unchanged':True,'master_sha256':before['master_sha_before'],'snapshot_hashes_verified':True,'rule_versions':[v[0] for v in versions],
                   'targeted_tests_passed':11,'skill_validation':'PASS','actual_reimport':retry,'human_confirmed':0,'owner_feedback_records_created':0,
                   'original_priority_confidence_transitions':dict(Counter(x['before_confidence']+'→'+x['after_confidence'] for x in priority)),
                   'current_mid_confidence_skus':[x['sku'] for x in current.values() if x['confidence']=='中'],
                   'remaining_insufficient_reason_counts':dict(Counter(c for x in unresolved for c in x['reason_codes'])),
                   'unprocessed_full_copy_skus':9992,'expanded_to_500':False,'production_writes':0,'web_or_external_provider_calls':0})
    immutable(out/'review_acceptance.json',report)
    lines=['# 100 SKU 学习结果复核与规则 v2','',
           '本轮仅复核既有100个SKU，其中重点29条。分析依据仍限于原西语品名；原Master、原始快照、样本集合和v1判断均保留。','',
           '## 实际结果','',
           '- 22个SKU修改了分类、商品类型、用途或标签；另6个只校准置信度；其余72个核心字段保留。证据与AI复核记录均补齐。',
           '- 当前：高置信度77个、中置信度8个、信息不足15个；没有将AI复核伪装成人工确认。',
           '- 原15个中置信度：8个在明确粗类上提高置信度，5个维持中等，Cazo与Barco两条因原判断过强降为信息不足。',
           '- 原14个信息不足：Botella可作一般瓶类容器判断，其余13个仍保留。因此总信息不足为14−1+2=15。',
           '- 15个未解决项中6个为中文混入西语字段，9个为品牌式名称、词义或主用途域不足。没有从原类目、中文或网页补猜。',
           '- 学习数据库有200条历史判断，覆盖同一批100个唯一SKU；不是扩大到200个商品。9,992个其他SKU仍未学习。','',
           '## 本轮修正的规则','',
           '1. 置信度按实际声称的粒度计算；可确认饮料、瓶子、上衣或计划工具时，不因未提供容量、材质或载体而一律拒绝。',
           '2. 主体、主类、功能与场景各自记录置信度；来源语言异常、品牌名称、词义多义和主用途域不明分开编码。',
           '3. 装饰图案不等于DIY套件；品牌或系列不自动成为玩具、沐浴用途、宠物食用对象的证据。',
           '4. 不将泛指词收窄为未经标题说明的结构：recambio不限燃料补充装、apósito不限粘贴创口贴、无限效果不保证镜片结构。',
           '5. 区分创作、普通游戏、设施铺设、气候和节庆标签；数据线未说明充电时使用中性分类。',
           '6. 来源词段不能为空，AI不能自行确认。规则版本内容不可重写；旧人工修正绑定的判断失效后，不能直接覆盖新判断。','',
           '## 典型修正','',
           '| SKU | 修正 |','|---|---|',
           '|3219926|钻石画装饰包袋从确定DIY创作改为包袋携带，保留制作方式未知|',
           '|3210047|首饰盒按收纳主功能改为家居日用/首饰收纳|',
           '|3205705|儿童创口贴改为更宽泛的儿童创口敷料|',
           '|3012135|钩织玩偶改为钩织造型，未指定玩偶形态|',
           '|3224679|充电数据线子类改为数据线，不额外声称充电|',
           '|3225301|无限镜效果改为无限效果，不额外声称镜片结构|',
           '|3218745|泡腾球礼盒保留礼赠，撤去由Spa品牌词推定的沐浴护理|',
           '|3016463|Cazo保留小煮锅/舀勺歧义，撤去单一器型|',
           '|3220769|Barco不再仅凭品牌系列认定玩具和玩耍用途|','',
           '## 验证与留档','',
           '- 11项专项测试通过；Skill格式通过；真实v2重复导入新增0条。',
           '- 数据库旧100条v1判断与复核前在线备份逐项一致；原始来源、学习底表、批次、样本成员与反馈表内容一致。',
           '- Master SHA-256与开始时一致；原始快照各文件哈希一致。',
           '- 本轮没有采集、外部模型调用、参数微调、正式Action入库、提交、合并或扩样。','',
           '审查后的100条结果见 ai_learning_results.csv；重点29条前后对照见 priority_29_review.csv；所有差异见 all_100_review_changes.csv。',
           '完整结构验收见 review_acceptance.json。人工审核表仍保留真实审核者与反馈列，当前人工确认数为0。','',
           '本轮停止在100个SKU复核节点。余下15条不应强行消除；后续需要可信的更完整西语名称或真实人工意见后再形成新来源/新判断。']
    (out/'复核结论与规则修正.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='source_and_sample_invariants'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
