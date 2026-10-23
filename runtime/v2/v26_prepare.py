"""Protect V2.5.13 and build source-bound Action group candidates for V2.6."""
from __future__ import annotations
import collections,hashlib,json,random,re,sqlite3,zipfile
from pathlib import Path
from assortment import ROOT,RUN,Matcher,lines,read,norm
import boundary_v24 as b24
import run_subject_v2513 as oldrun
OUT=ROOT/'v2/runs/semantic_v26_20261023'
V23=ROOT/'outputs/action_semantic_v23_20261022/final_candidate/results.jsonl'
GROUPS=[
 ('G01','表面擦拭','擦拭|清洁抹布|百洁|清洁海绵','清除表面污渍','表面擦拭与日常清洁'),
 ('G02','家庭清洁工具','清洁刷|扫帚|拖把|刮水|除尘|洁厕|垃圾|吸尘|清扫','家庭清扫','清除灰尘污物及废物整理'),
 ('G03','洗衣与衣物护理','洗衣|晾衣|熨|衣物护理|除毛|除绒','洗涤与晾晒衣物','辅助衣物清洁与维护'),
 ('G04','空间收纳整理','收纳|整理|储物|储存箱|储物篮|篮类|抽屉','分区存放物品','整理有限空间中的物品'),
 ('G05','厨房备餐工具','刀具|厨刀|削皮|刨|砧板|刮刀|打蛋器|厨房工具|厨具|厨房剪|切菜','处理食材','切分处理与准备食物'),
 ('G06','锅具与烘焙','锅|烤盘|烘焙|烤模|蛋糕模|烘烤|烤架','烹饪与烘烤','加热食材与制作烘焙食品'),
 ('G07','食品存放','饭盒|食品储|食品保|食物容器|保鲜|密封罐|食品容器','保存和携带食品','食品分装存放与携带'),
 ('G08','餐桌与饮水用品','餐具|杯|碗|餐盘|盘子|餐勺|叉|餐垫|桌布|水瓶|水壶','进餐和饮水','日常进餐饮水与餐桌使用'),
 ('G09','家用小电器','空气炸锅|电饭|搅拌机|电热水壶|咖啡机|电动打蛋|电炸锅|烤面包|奶泡|电煎|蒸汽清洁','家庭辅助处理','家庭食物处理或日常家务'),
 ('G10','家庭空气与温度','风扇|暖风|加湿|冷风|取暖|暖气|空调','空气流动和温度调节','局部空气流动与环境舒适'),
 ('G11','照明','台灯|灯泡|灯具|照明|手电|夜灯|灯带','提供照明','局部或便携照明'),
 ('G12','装饰与节庆','装饰|节庆|圣诞|花瓶|人造植物|相框|摆件|人造花|仿真','装点空间','家庭空间与节日布置'),
 ('G13','蜡烛与空间芳香','香薰|芳香|蜡烛|熏香','烛光或空间芳香','室内氛围与空间气味'),
 ('G14','艺术与手工','手工|绘画|画笔|颜料|编织|黏土|粘土|水彩|油画|丙烯|涂料|彩绘|毛线|钩针|刺绣','制作与创作','手工制作和绘画创作'),
 ('G15','家用纺织与服饰','窗帘|毯|地垫|地毯|床品|被套|枕|毛巾|袜|上衣|裤|睡衣|内衣|服装','覆盖穿着与擦干','家用织物与日常穿着'),
 ('G16','家用五金与工具','工具|螺丝|门锁|挂钩|胶带|紧固|扳手|钳|钻|五金|锤|铰链','家庭维修与固定','日常修整安装与固定'),
 ('G17','园艺','园艺|花盆|浇水|种植|喷壶|园林|植物养护','照料植物','家庭种植与园艺维护'),
 ('G18','玩具与游戏','玩具|游戏|拼图|泡泡|玩偶|积木|毛绒','玩耍与娱乐','玩耍与休闲活动'),
 ('G19','个人护理','洗护|护肤|牙刷|化妆|头发|护理|指甲|梳|美容|洗发|面膜','日常个人护理','清洁梳理和个人整理'),
 ('G20','宠物用品','宠物|猫|狗|犬','照料宠物','家庭宠物喂养玩耍与护理'),
 ('G21','文具与办公','文具|书写|笔记本|圆珠笔|文件|铅笔|记号笔|橡皮|订书','记录与书写','日常书写记录及文件整理'),
 ('G22','旅行与运动','旅行|运动|自行车|露营|背包|健身|行李|旅游','出行与运动','日常出行与休闲运动'),
 ('G23','消费电子配件','充电|手机|电池|耳机|电线|插头|插座|电子|USB','连接与供电','个人设备连接供电与使用'),
 ('G24','食品与饮料','食品|饮料|糖果|零食|饼干|巧克力|茶叶|咖啡粉|调味|糖浆','饮食消费','日常食品与饮料消费'),
]
PRIORITY=['G20','G13','G09','G10','G23','G24','G03','G07','G21','G19','G18','G17','G01','G02','G05','G06','G08','G11','G14','G15','G04','G12','G16','G22']
def save(name,data,jsonl=False):b24.p.immutable(OUT/name,data,jsonl=jsonl)
def protect():
 OUT.mkdir(parents=True,exist_ok=True)
 frozen=read(oldrun.OUT/'frozen_contract.json')
 if oldrun.fingerprints()!=frozen['fingerprints']:raise RuntimeError('V2513_BASELINE_CHANGED')
 files=[]
 for folder in ['v2','scripts','tests','rules','skills/action-selection']:
  for p in (ROOT/folder).rglob('*'):
   if not p.is_file() or any(x in p.parts for x in ['runs','node_modules','__pycache__']):continue
   if p.suffix in {'.py','.mjs','.js','.json','.md','.yaml','.yml','.toml'}:files.append(p)
 files += [p for p in oldrun.OUT.iterdir() if p.is_file() and p.suffix!='.sqlite3']
 files += [RUN/'retrieval_index.joblib',RUN/'action_input_manifest.json',V23]
 archive=OUT/'v2513_protected_program.zip'
 if not archive.exists():
  with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
   for p in sorted(set(files)):z.write(p,str(p.relative_to(ROOT)))
 with zipfile.ZipFile(archive) as z:
  if z.testzip() is not None:raise RuntimeError('PROGRAM_ARCHIVE_INVALID')
  for p,h in frozen['fingerprints'].items():
   rel=str(Path(p).relative_to(ROOT)).replace('\\','/') if Path(p).is_relative_to(ROOT) else None
   if rel and rel in z.namelist() and hashlib.sha256(z.read(rel)).hexdigest()!=h:raise RuntimeError('ARCHIVE_RESTORE_HASH_MISMATCH')
 backup=OUT/'learning_before_v26.sqlite3'
 if not backup.exists():
  with sqlite3.connect(ROOT/'learning_data/action_selection.sqlite3') as src,sqlite3.connect(backup) as dst:src.backup(dst)
 with sqlite3.connect(backup) as c:
  assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()
 save('protection.json',{'v2513_run':'v2513-62086668a1d0918d','baseline_fingerprints':frozen['fingerprints'],'archive_sha256':b24.p.filehash(archive),'archive_crc':'PASS','restored_code_hash_readback':'PASS','backup_integrity':'ok','git_initialized':False,'sealed_content_opened':False})
def build_groups(matcher):
 refs={r['sku']:r for r in matcher.model['references']}
 # V2.3 already contains only eligible reference titles. No sealed source file.
 semantic={r['sku']:r for r in lines(V23) if r['sku'] in refs and r['name_es_original']==refs[r['sku']]['name_es_original']}
 defs={g[0]:g for g in GROUPS};members=collections.defaultdict(list);unassigned=[]
 for sku,ref in refs.items():
  old=semantic.get(sku,{});typ=old.get('product_type_candidate') or ''
  if old.get('status')!='SPECIFIC_SEMANTIC_CANDIDATE':unassigned.append(sku);continue
  gid=next((g for g in PRIORITY if re.search(defs[g][2],typ)),None)
  if not gid:unassigned.append(sku);continue
  members[gid].append({'sku':sku,'name_es_original':ref['name_es_original'],'source_row_id':ref['source_row_id'],
   'type_candidate':typ,'type_evidence':old.get('type_evidence',[]),'use_need_hypotheses':old.get('use_need_hypotheses',[]),
   'authority':'HISTORICAL_AI_OR_RULE_CANDIDATE_NOT_GOLD'})
 cards=[]
 for gid,name,expr,fn,need in GROUPS:
  rows=members[gid]
  if not rows:continue
  reps=[];types=set()
  for r in rows:
   if r['type_candidate'] not in types:reps.append(r);types.add(r['type_candidate'])
   if len(reps)==8:break
  cards.append({'group_id':gid,'name':name,'function_hypothesis':fn,'need_hypothesis':need,'typical_scenario_hypothesis':'家庭或日常使用；具体场景以原名为准',
   'member_count':len(rows),'specific_type_count':len({r['type_candidate'] for r in rows}),'examples':reps,
   'boundary':'同组不代表同款；安装方式、宿主依赖和特殊用途仍需核对','uncertainty':'分组继承AI/规则候选，不是人工已确认分类，不能证明热销或采购理由'})
 historical=[]
 with sqlite3.connect('file:'+str(ROOT/'learning_data/action_selection.sqlite3').replace('\\','/')+'?mode=ro',uri=True) as c:
  # Only query eligible IDs. Never read payloads of excluded/sealed SKUs.
  keys=list(refs)
  for start in range(0,len(keys),400):
   subset=keys[start:start+400]
   for sku,payload in c.execute('SELECT sku,payload FROM analyses WHERE sku IN ('+','.join('?' for _ in subset)+') ORDER BY seq',subset):
    a=json.loads(payload)
    if a.get('name_es_original')==refs[sku]['name_es_original']:historical.append({'sku':sku,'rules_version':a.get('rules_version'),'product_type':a.get('product_type'),'source_row_id':a.get('source_row_id'),'candidate_only':True})
 save('action_group_cards.json',cards);save('action_group_members.jsonl',[dict(r,group_id=g) for g,rs in members.items() for r in rs],True)
 save('historical_candidate_reuse.json',{'eligible_exact_title_analysis_records':len(historical),'eligible_skus_with_history':len({r['sku'] for r in historical}),'original_learning_members_unchanged':True,'sealed_payloads_queried':0})
 save('group_summary.json',{'groups':len(cards),'members':sum(len(rs) for rs in members.values()),'unassigned_eligible_skus':len(unassigned),'specific_type_nodes':sum(c['specific_type_count'] for c in cards),'eligible_index':len(refs),'all_labels_candidate':True})
 return cards
def development():
 byid={r['record_id']:r for r in lines(b24.INPUTS)};exposed=set()
 for p in (ROOT/'v2/runs').rglob('inputs_*.jsonl'):
  if OUT in p.parents:continue
  exposed.update(r.get('record_id') for r in lines(p))
 pool=[r for k,r in byid.items() if k in exposed];rng=random.Random(2026102360);chosen=[];used=set()
 strata=[('major_appliance',r'aire acondicionado.*btu|frigorifico combi|lavadora de carga|secadora de ropa|termo electrico'),
 ('furniture',r'conjunto.*salon|mueble de bano|mesa.*comedor|armario|escritorio'),
 ('professional_or_home_tool',r'industrial|profesional|prensa|soldador|taladro|power station|estacion de energia'),
 ('host_accessory',r'filtro|recambio|repuesto|soporte|patas.*mesa|fundas?'),
 ('everyday',r'taza|cuchara|papel freidora|bolsa.*lavadora|iman.*frigor'),
 ('related_need_candidate',r'organizador|divisor|separador|perchero|rafia|colgador|caja|cesto')]
 for label,expr in strata:
  options=[r for r in pool if re.search(expr,norm(r['title_original']))];rng.shuffle(options);n=0
  for r in options:
   h=b24.title_hash(r['title_original'])
   if h in used:continue
   chosen.append(dict(r,development_stratum=label,review_id=f'D{len(chosen)+1:03d}'));used.add(h);n+=1
   if n==10:break
  if n!=10:raise RuntimeError('DEV_STRATUM_SHORTFALL:'+label)
 save('development_60_inputs.jsonl',chosen,True)
 return chosen
if __name__=='__main__':
 protect();m=Matcher();cards=build_groups(m);dev=development()
 print(json.dumps({'groups':len(cards),'development':len(dev),'protection':'PASS','summary':read(OUT/'group_summary.json')},ensure_ascii=False))
