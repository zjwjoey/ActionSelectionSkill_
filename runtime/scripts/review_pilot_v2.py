"""Explicit second-pass Codex review of the same 100 titles; append-only."""
import json
from collections import Counter
from pathlib import Path

import storage
from pipeline import ROOT,FIELDS,immutable,digest,import_analysis,load_rules

SID='master_d1af859e842adbe1'
BATCH='pilot100_c2217cd5173d'
ROUND='codex-review-20261022-v2'

# These are semantic review decisions, not keyword rules or automatic truth.
CHANGES={
 '3005084':dict(category_l2='瓶类容器',confidence='高',review_status='待审核',usage_scenario=['一般盛装场景']),
 '3212583':dict(action_pattern=['设施铺设'],confidence='高'),
 '3217559':{},
 '3016463':dict(category_l2='器型待核实',product_type='Cazo（小煮锅或舀勺含义待定）',primary_function=[],usage_scenario=['厨房器具场景待核实'],consumer_need=['具体烹饪或舀取需求待核实'],action_pattern=[],confidence='低',review_status='信息不足'),
 '2577328':dict(confidence='高'),
 '3218745':dict(category_l1='家居日用',category_l2='礼赠套装',primary_function=['礼赠'],usage_scenario=['礼赠场景'],action_pattern=['礼赠场景']),
 '3219926':dict(category_l1='服饰配件',category_l2='包袋',primary_function=['携带物品'],usage_scenario=['随身携带'],consumer_need=['物品携带与装饰'],action_pattern=['服饰搭配']),
 '2515506':dict(category_l1='未确定',category_l2='多义词待核实',product_type='Cubo（桶或立方体含义待定）',primary_function=[],usage_scenario=['场景未确定'],consumer_need=['待明确'],action_pattern=[]),
 '2532534':dict(confidence='高'),
 '3201171':dict(product_type='带替换或补充件的点火器',confidence='高'),
 '3205082':dict(product_type='骰子游戏用品',action_pattern=['休闲游戏'],confidence='高'),
 '3225710':dict(action_pattern=['休闲游戏']),
 '3220769':dict(category_l1='未确定',category_l2='船类用途待核实',product_type='船（具体商品用途待定）',primary_function=[],usage_scenario=['场景未确定'],consumer_need=['待明确'],action_pattern=[],confidence='低',review_status='信息不足'),
 '3200752':dict(confidence='高'),
 '3212715':dict(confidence='高'),
 '3222819':dict(confidence='高'),
 '3218030':{},
 '2578510':dict(category_l2='节庆趣味用品',product_type='圣诞帽（名称含舞动与音乐）',primary_function=['圣诞主题趣味'],consumer_need=['节日氛围'],action_pattern=['季节节庆']),
 '3225301':dict(product_type='LED无限效果圣诞摆件'),
 '3210047':dict(category_l1='家居日用'),
 '3205705':dict(product_type='儿童创口敷料'),
 '3012135':dict(product_type='自制钩织造型项目'),
 '2532127':dict(action_pattern=['清洁维护']),
 '3224709':dict(action_pattern=['季节气候','清洁维护'],confidence='中'),
 '3209499':dict(action_pattern=['派对布置']),
 '3211983':dict(product_type='LEGO Technic推土机模型',confidence='中'),
 '3202233':dict(action_pattern=['数码连接','休闲游戏']),
 '3224679':dict(category_l2='数据线'),
 '2550709':dict(product_type='蓄冷用品'),
 '2569076':dict(confidence='中'),
}

NOTES={
 '3005084':'Botella明确支持瓶子和一般盛装用途；缺少容量、材质和专门用途不应否定这个粗粒度判断。未补成运动水瓶。',
 '3212583':'泳池铺块主体清楚；铺设不是兴趣创作。按已声称的泳池铺设粒度校准，具体材料与位置仍未知。',
 '3217559':'Pomo是多义名词；没有商品对象限定，继续保留信息不足，不按来源类目选门把手。',
 '3016463':'Cazo可指小煮锅或舀勺；原版单选小煮锅偏窄。保留厨房语境，暂不确定器型与功能。',
 '3223749':'中文“赏金”不是可用西语商品名。保留源异常，不逆推Bounty或巧克力。',
 '3203250':'Celebrations只有品牌/系列式名称，继续保留信息不足；品牌熟悉度不能替代商品名词。',
 '2577328':'Bebida足以确认饮料这一粗类；没有乳成分和容量不应降低已声称的粗类置信度。',
 '3218745':'保留明确的礼盒和泡腾球；Spa品牌词不足以将具体用途断言为沐浴，撤去护理用途与护理标签。',
 '3219299':'中文“填充纱”混入源字段，继续保留源异常，不倒译西语。',
 '3219926':'con pintura de diamantes说明包袋带钻石画装饰，不足以证明它是待制作DIY套件；主用途改为包袋携带。',
 '2515506':'Cubo同时有桶和立方体等词义；原版直接写桶及盛装用途过强，撤去该确定用途。',
 '2532534':'doméstico为家用容器解读提供语境；只确认家用桶及盛装，不推断清洁桶或垃圾桶。',
 '3221911':'中文“花园套装”不构成西语名称证据，保留异常且不猜内容。',
 '3201171':'Encendedor明确为点火器；recambio可能是替换件或补充件，不限燃料补充装。',
 '3213755':'中文“水塔”混入源字段，不能判成模型、储水设施或玩具。',
 '3205082':'骰子套组和骰子游戏都支持骰子游戏用品这一粗类；标签改为休闲游戏，不推断附完整规则。',
 '3225710':'Dartblaster类型词支持发射游戏用品，但玩具域仍有普通语境推断；撤去创作标签，保留中置信度。',
 '3220769':'Barco只明确船；Zuru/Robo Alive品牌系列提示不足以当作字面玩具证据，撤去确定玩耍功能并保留用途待核实。',
 '3207774':'球发射器可供玩具、宠物或运动使用，继续保留用途域不明。',
 '3221083':'Chicken Steak Sticks识别条状食用商品，但未给食用对象；不使用品牌或来源类目判成人食、狗食或猫食。',
 '3200752':'para perros和Ternera提供狗用与牛肉命名语境；可确认颗粒食品粗类，不能据此宣称完整主粮或肉含量。',
 '3212715':'Top按西语零售普通名词可确认上衣粗类；袖长、性别和材质缺失不是整体信息不足。',
 '3220658':'中文“案例”是源文字异常，不依据文具类目猜文具盒。',
 '3006788':'Estuche completo没有说明内部物品；保留盒袋/套装粗含义，不能认定完整文具套装。',
 '3220659':'Estuche de lujo无法确定装什么；de lujo不作质量证据，继续保留待核实。',
 '3222819':'Planificador足以支持计划工具及安排事项，不声称纸本/墙面/电子载体，可在粗类上校准置信度。',
 '3216909':'中文“奢华香棒”混入源字段，保留源异常，不猜扩香棒原文。',
 '3218030':'花瓣装饰为可解释的普通用途推断，并非标题明确场景；保留中置信度，不认定仿真材质。',
 '2578510':'圣诞帽主题、舞动和音乐来自标题，但可佩戴性不明确；撤去服饰搭配标签和确定服饰子类。',
 '3225301':'efecto infinito不直接证明镜片结构；品类命名去掉“镜”，保留LED与无限效果名称。',
 '3210047':'按主要功能，首饰盒属于物品收纳，不是身体护理；调整到家居日用下首饰收纳。',
 '3205705':'apósito泛指创口敷料，不必是带粘胶的创口贴；使用儿童创口敷料这一更稳妥的类型。',
 '3012135':'figura指造型，不必是玩偶；保留钩织创作，撤去未经名称支持的玩偶细分。',
 '2532127':'砂纸明确支持打磨维护，标题没有创作语境；去掉额外创作标签。',
 '3224709':'刮冰器的车用场景是常见用途推断；校准为中置信度。冰雪属于气候场景，不等于节庆。',
 '3209499':'Happy Birthday支持生日派对，但不表示季节性节日；只保留派对布置。',
 '3211983':'LEGO Technic使拼搭模型解读合理，但属于系列语境推断；显式记录域推断并降低整体置信度，保留待人工复核。',
 '3202233':'游戏耳机支持游戏音频，与创作没有必然联系；将兴趣创作标签改为休闲游戏。',
 '3224679':'标题仅明确数据线；原二级类目“充电数据线”额外暗示充电，改为中性数据线。',
 '2550709':'蓄冷用品并没有在标题中限定块状外形；撤去“块”这一具体形状。',
 '2569076':'arenero在复合零售短语中通常指猫砂盆，但该场景是语境推断而非显式gato；校准中置信度。',
}

BLOCKS={
 '3217559':'TYPE_AMBIGUOUS','3016463':'TYPE_AMBIGUOUS','3203250':'BRAND_ONLY','2515506':'TYPE_AMBIGUOUS',
 '3220769':'DOMAIN_AMBIGUOUS','3207774':'DOMAIN_AMBIGUOUS','3221083':'DOMAIN_AMBIGUOUS',
 '3006788':'DOMAIN_AMBIGUOUS','3220659':'DOMAIN_AMBIGUOUS',
 **{s:'SOURCE_LANGUAGE_INVALID' for s in ['3223749','3219299','3221911','3213755','3220658','3216909']}}
NONBLOCKS={
 '3005084':['SUBTYPE_UNSPECIFIED','SCENARIO_UNSPECIFIED'],
 '3212583':['MECHANISM_UNSPECIFIED'], '2577328':['SUBTYPE_UNSPECIFIED'],
 '3218745':['DOMAIN_INFERRED'], '3219926':['MECHANISM_UNSPECIFIED'],
 '2532534':['SUBTYPE_UNSPECIFIED'], '3201171':['MECHANISM_UNSPECIFIED'],
 '3205082':['SUBTYPE_UNSPECIFIED'],'3225710':['DOMAIN_INFERRED'],
 '3200752':['SUBTYPE_UNSPECIFIED'],'3212715':['SUBTYPE_UNSPECIFIED'],
 '3222819':['SUBTYPE_UNSPECIFIED'], '3218030':['DOMAIN_INFERRED'],
 '2578510':['DOMAIN_INFERRED','MECHANISM_UNSPECIFIED'],
 '3224709':['DOMAIN_INFERRED'], '3211983':['DOMAIN_INFERRED'], '2569076':['DOMAIN_INFERRED']}


def main():
    # Pin the original revision, not the latest mutable projection.
    originals=[x for x in storage.history(ROOT,BATCH) if x['rules_version']=='name-semantics-v1']
    assert len(originals)==100==len({x['sku'] for x in originals})
    blind={x['sku']:x for x in storage.members(ROOT,BATCH,blind=True)}
    reviewed=[];audit=[]
    for old in originals:
        sku=old['sku'];new={k:old[k] for k in ('sku',*FIELDS)}
        new.update(CHANGES.get(sku,{}))
        reason=NOTES.get(sku,'逐项对照本条品名：主体、普通用途、场景、数值/型号及标签未发现需修改之处；保留AI提案，未作人工确认。')
        boundary=(reason+' 仅以本字段品名为证据；未说明的材质、尺寸、质量、销量、频率和采购原因不推断。') if sku in NOTES else new['evidence']['inference_boundary']+' 复核：'+reason
        new['evidence']={**new['evidence'],'inference_boundary':boundary}
        if sku=='3222209':new['evidence']['title_spans']+=['20 denier']
        if sku in ['3222689','3224679']:new['evidence']['title_spans']+=['USB-C']
        if sku=='3223320':new['evidence']['title_spans']+=['Plantas de balcón y macetas']
        new['uncertainty_codes']=[BLOCKS[sku]] if sku in BLOCKS else NONBLOCKS.get(sku,[])
        identity='低' if sku in BLOCKS and BLOCKS[sku] in ['SOURCE_LANGUAGE_INVALID','BRAND_ONLY','TYPE_AMBIGUOUS'] else '高'
        domain='低' if sku in BLOCKS else ('中' if 'DOMAIN_INFERRED' in new['uncertainty_codes'] else '高')
        new['dimension_confidence']={'product_identity':identity,'primary_domain':domain,'function':'低' if sku in BLOCKS else '高','scenario':'低' if sku in BLOCKS else ('中' if new['uncertainty_codes'] else '高')}
        changed={k:{'before':old[k],'after':new[k]} for k in FIELDS if k!='evidence' and old[k]!=new[k]}
        content_fields=set(changed)-{'confidence','review_status'}
        decision='CORRECTED' if content_fields else ('CALIBRATED' if changed else ('ABSTAIN_RETAINED' if old['review_status']=='信息不足' else 'KEEP'))
        new['ai_review']={'round_id':ROUND,'reviewer_kind':'AI','reviewer':'Codex','decision':decision,'reason':reason,
                          'parent_rules_version':old['rules_version'],'parent_annotation_hash':old['annotation_hash'],'priority_from_v1':old['confidence']!='高'}
        reviewed.append(new)
        audit.append({'sku':sku,'name_es_original':old['name_es_original'],'priority_from_v1':old['confidence']!='高',
                      'before_confidence':old['confidence'],'after_confidence':new['confidence'],
                      'before_status':old['review_status'],'after_status':new['review_status'],
                      'decision':decision,'reason':reason,'changed_fields':changed,'uncertainty_codes':new['uncertainty_codes'],
                      'parent_annotation_hash':old['annotation_hash'],'source_row_id':blind[sku]['source_row_id']})
    assert len(reviewed)==100
    output=ROOT/'learning_data'/SID/BATCH/'proposals'/f'{ROUND}.jsonl'
    immutable(output,reviewed,jsonl=True)
    report_dir=ROOT/'reports'/SID/BATCH/'name-semantics-v2'
    immutable(report_dir/'review_decisions_100.json',audit)
    result=import_analysis(SID,BATCH,output,reprocess=[x['sku'] for x in reviewed],rules_version='name-semantics-v2')
    result.update({'round_id':ROUND,'priority_rows_reviewed':sum(x['priority_from_v1'] for x in audit),'decisions':dict(Counter(x['decision'] for x in audit)),
                   'content_changed_skus':sum(any(f not in ['confidence','review_status'] for f in x['changed_fields']) for x in audit),
                   'any_core_field_changed_skus':sum(bool(x['changed_fields']) for x in audit),
                   'before_information_insufficient':sum(x['review_status']=='信息不足' for x in originals),
                   'after_information_insufficient':sum(x['review_status']=='信息不足' for x in reviewed),
                   'before_confidence':dict(Counter(x['confidence'] for x in originals)),
                   'after_confidence':dict(Counter(x['confidence'] for x in reviewed))})
    result_path=report_dir/'review_import_result.json'
    if result_path.exists() and json.loads(result_path.read_text(encoding='utf-8'))!=result:
        result_path=report_dir/('review_resume_'+digest(result)[:12]+'.json')
    immutable(result_path,result)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
