"""Independent boundary-v0 candidate policy and source-bound learning contracts.

Title-only local proposals are explicitly local, never fabricated model calls.
Action similarity cannot override operating scope. No price/score input.
"""
from __future__ import annotations
import csv,hashlib,json,re,sqlite3
from pathlib import Path
from assortment import ROOT,Matcher,lines,read,norm
import boundary_v24 as b24
import subject_v2513 as old
VERSION='boundary-v0'
OUT=ROOT/'v2/runs/boundary_v0_20261023'
POLICY=ROOT/'rules/boundary-v0.json'
LABELS={'纳入候选','待复核','暂不纳入'}
MAP={'保留':'纳入候选','观察':'待复核','用不到':'暂不纳入'}

def digest(v):return hashlib.sha256(b24.p.canonical(v).encode()).hexdigest()
def binding(r):return digest({k:r.get(k,'') for k in ['record_id','input_hash','title_original','category_l1_original','source_file_sha256','source_row']})
def save(n,v,jsonl=False):b24.p.immutable(OUT/n,v,jsonl=jsonl)
def subject_pos(t,span):
    p=norm(t).find(norm(span)) if span else -1
    return p if p>=0 else 10**9

# A leading component/cover is the sold object; later host words cannot transfer
# a host boundary. Earlier whole-object nouns beat bundled later accessories.
DEPENDENT_HEAD=re.compile(r'\b(filtros?|fundas?|cubiertas?|interruptores?|interruptor|repuestos?|recambios?|mecanismos?|cartuchos?|patas?|bolsas?|pa[nñ]os?|soportes?|cables?|bater[ií]as?|mandos?|controladores?|bisagras?|tiradores?|tapas?|poleas?|protectores?)\b(?:\s+[\w-]+){0,3}\s+(?:para|de)\s+',re.I)
MACHINE_HEADS=[
('ROBOT_CLEANER',r'\b(?:robot\s+(?:aspirador\w*|limpiacristales|de limpieza)|aspirador\w*\s+robot)\b'),
('POTTERY_WHEEL',r'\btorno\s+(?:de\s+)?(?:alfarer\w*|cer[aá]mic\w*)\b'),
('FIXED_WATER_HEATER',r'\btermo\s+el[eé]ctrico\b'),
('INDUSTRIAL_MACHINE',r'\b(?:torno|fresadora|reactor|prensa|m[aá]quina)\s+(?:industrial|cnc|de producci[oó]n)\b'),
('FIXED_SMOKE_SYSTEM',r'\b(?:sombrerete\s+(?:de\s+)?chimenea|extractor de humos industrial)\b'),
]
def enrich_subject(title,parsed):
    s=dict(parsed);pos=subject_pos(title,s.get('evidence_span',''));head=DEPENDENT_HEAD.search(title)
    # Bundles, negated wireless qualifiers and purpose clauses are not heads.
    identity=re.split(r'[,|;]',title,maxsplit=1)[0]
    if head and (head.start()>=len(identity) or re.search(r'\b(?:con|sin|incluye)\s*$',title[:head.start()],re.I)):
        head=None
    if head and head.start()<pos:
        return dict(s,status='CLEAR',class_code='DEPENDENT_PART',evidence_span=head.group().strip(),dependent=True,subtype='',role_resolution='EARLIER_LITERAL_COMPONENT_HEAD')
    for code,pat in MACHINE_HEADS:
        m=re.search(pat,title,re.I)
        if m and m.start()<=pos:
            s=dict(s,status='CLEAR',class_code=code,evidence_span=m.group(),dependent=False,subtype='',role_resolution='EXPLICIT_COMPOSITE_SOLD_TYPE');pos=m.start()
    return s

def scope(title,s):
    code=s.get('class_code','');t=norm(title)
    if s.get('status')!='CLEAR':return '未知','UNKNOWN_SUBJECT','无法从品名确认具体销售对象'
    if s.get('dependent') or code in {'COMPONENT','ELECTRICAL_COMPONENT','DEPENDENT_PART'}:return '灰区','HOST_OR_INSTALL_DEPENDENCY','专用或安装配件；不继承宿主整机排除'
    if code in {'WASHER','DRYER','FRIDGE','DISHWASHER'}:return '范围外','WHOLE_MAJOR_APPLIANCE','明确大家电整机；配件和保护用品另行处理'
    if code=='AC':
        if 'split' in t:return '范围外','SPLIT_FIXED_HVAC','明确分体空调主机'
        return '灰区','HVAC_FORM_REVIEW','空调形态与经营范围待确认；不以价格判断'
    if code=='FIXED_WATER_HEATER':return '范围外','FIXED_WATER_HEATER','储水热水设备与普通饮水壶区分'
    if code in {'INDUSTRIAL_MACHINE','FIXED_SMOKE_SYSTEM'}:return '范围外',code,'明确专业固定系统或工业机器主体'
    if code=='ROBOT_CLEANER':
        features=sum(bool(re.search(p,t)) for p in [r'autovaci|vaciado automatic',r'autolimp|lavado automatic',r'estacion|base',r'navegacion|mapeo|lidar'])
        if features>=3:return '范围外','COMPLEX_AUTOMATIC_CLEANER','标题明确至少三项自动基站清洁系统特征；普通吸尘器不继承'
        return '灰区','ROBOT_AUTOMATION_REVIEW','自动清洁设备不可由普通吸尘器参照自动放行'
    if code in {'FURNITURE','DESK','TABLE','CABINET','LOCKER'}:return '灰区','COMPLETE_FURNITURE_REVIEW','完整家具按日用优先范围留研究，不按收纳盒放行'
    if code in {'POTTERY_WHEEL','DRILL','ELECTRIC_TOOL','AIR_COOLER'}:return '灰区','ELECTRIC_MACHINE_FORM_REVIEW','动力工具或机器需结合实际形态复核，非一律排除'
    if code=='FAN' and s.get('subtype')=='CEILING':return '灰区','FIXED_FAN_REVIEW','吊扇有固定安装依赖，非普通桌面风扇'
    return '范围内','CORE_TYPE_CANDIDATE','已识别日用具体类型；仍需参照与证据，不自动保留'

def analyze(row,base,semantic=None):
    s=enrich_subject(row['title_original'],base['subject']);state,rule,why=scope(row['title_original'],s)
    refs=base['action_references'];relation='A' if refs else 'E';reason=why;reference=refs[0] if refs else None
    authority='LOCAL_RULE_AND_FROZEN_REFERENCE_PROPOSAL'
    # Semantics must bind this exact row. Historical outputs are never silently
    # accepted as current-row approvals or human labels.
    if semantic:
        if semantic['source_binding']!=binding(row):raise ValueError('STALE_SEMANTIC_BINDING')
        p=semantic['semantic'];s=dict(s,class_code=p['type'],evidence_span=p['subject_span'],status='CLEAR' if p['dependency']!='unknown' else 'UNCLEAR',dependent=p['dependency']=='host_specific',installation_required=p['dependency']=='installed')
        relation=p['relation'];a=semantic.get('action_reference');reference=None if not a else {'action_sku':a['action_sku'],'action_title':a['action_title'],'action_source_row_id':a['source_row_id']}
        state=semantic['scope'];rule=semantic['boundary_rule'];reason=semantic['reason'];authority=semantic['analysis_authority']
    decision='暂不纳入' if state=='范围外' else '纳入候选' if state=='范围内' and relation in {'A','B','C'} and reference else '待复核'
    if decision=='暂不纳入' and (s.get('status')!='CLEAR' or s.get('dependent')):
        decision='待复核';state='灰区';rule='DEPENDENCY_BOUNDARY_CONFLICT';reason='配件或主体未明不能继承整机边界'
    strength='强' if relation=='A' else '中' if relation in {'B','C'} else '弱' if relation=='D' else '未知'
    return {'record_id':row['record_id'],'input_hash':row['input_hash'],'source_binding':binding(row),'title_original':row['title_original'],'category_l1_original':row.get('category_l1_original',''),
        'source_row':row.get('source_row'),'cohort':row.get('sample_cohort',''),'subject':s,'action_relation':relation,'action_match_strength':strength,'action_reference':reference,
        'scope':state,'decision':decision,'reason':reason,'boundary_rule':rule,'boundary_version':VERSION,'rule_status':'CANDIDATE_EXPERIMENT_ONLY','authority':authority,
        'human_review_status':'UNREVIEWED','human_reviewer':'','human_gold':False,'source_price_used':False,
        'learning_questions':[] if decision=='纳入候选' else [rule,'商品主体／形态／边界是否得到原名支持？', '应采用什么具体类型或反例校准？']}

def verify_reference(result,refs,connection=None):
    a=result.get('action_reference')
    if not a:return
    r=refs.get(a['action_sku'])
    if not r or a['action_title']!=r['name_es_original'] or a['action_source_row_id']!=r['source_row_id']:raise ValueError('ACTION_REFERENCE_MISMATCH')
    if connection:
        q=connection.execute("SELECT sku,json_extract(payload,'$.name_es_original') FROM source_rows WHERE source_row_id=?",(r['source_row_id'],)).fetchone()
        if q!=(r['sku'],r['name_es_original']):raise ValueError('ACTION_DATABASE_MISMATCH')

def validate_feedback(row,feedback):
    if feedback.get('source_binding')!=row['source_binding']:raise ValueError('FEEDBACK_SOURCE_MISMATCH')
    if feedback.get('decision') not in LABELS:raise ValueError('INVALID_HUMAN_DECISION')
    if feedback.get('authority')!='HUMAN' or not feedback.get('reviewer','').strip() or not feedback.get('evidence_reference','').strip():raise ValueError('REAL_HUMAN_EVIDENCE_REQUIRED')
    return feedback

def impact(rows,rule):
    """Incremental changes use semantic type/scope, never per-SKU word rules."""
    types=set(rule.get('subject_types',[]));changed_rules=set(rule.get('replaces_rule_ids',[]))
    return [r['record_id'] for r in rows if r['subject']['class_code'] in types or r['boundary_rule'] in changed_rules]

def validate_publication(rule,feedback,tests):
    if rule.get('status')!='CANDIDATE' or not rule.get('support_feedback_ids') or not rule.get('counterexamples'):raise ValueError('RULE_EVIDENCE_INCOMPLETE')
    byid={f['feedback_id']:f for f in feedback if f.get('authority')=='HUMAN' and f.get('reviewer') and f.get('evidence_reference')}
    if not set(rule['support_feedback_ids'])<=set(byid):raise ValueError('HUMAN_SUPPORT_REQUIRED')
    if tests.get('status')!='PASS' or tests.get('candidate_rule_hash')!=digest(rule):raise ValueError('RULE_REGRESSION_REQUIRED')
    if not rule.get('release_approval_reviewer') or not rule.get('release_approval_evidence'):raise ValueError('RULE_RELEASE_APPROVAL_REQUIRED')
    return dict(rule,status='PUBLISHED')
