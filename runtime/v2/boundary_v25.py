"""V2.5 subject, boundary and Action-reference audit. Append-only shadow run."""
from __future__ import annotations
import collections, csv, hashlib, json, random, re, sqlite3
from pathlib import Path

import boundary_v24 as v24
from assortment import ROOT, RUN, Matcher, lines, read, norm

VERSION = 'amazon-boundary-v2.5'
OUT = ROOT / 'v2/runs/amazon_boundary_v25_20261022'
DB = ROOT / 'learning_data/action_selection.sqlite3'
FOCUS_XLSX = Path(r'D:\Users\Administrator\Downloads\Action_V24_AI_Audit_Focus.xlsx')
SEED = 2026102225

# Narrow corrective vocabulary extracted from recurring *types of failure* in
# the supplied AI audit. It does not encode individual Amazon records or SKUs.
SUBJECT_PATTERNS = [
    ('AIR_CONDITIONER', re.compile(r'\b(?:aire acondicionado|acondicionador de aire)\b', re.I)),
    ('DOORMAT', re.compile(r'\bfelpudo\b', re.I)),
    ('VACUUM_STORAGE_BAG', re.compile(r'\b(?:bolsas?|fundas?)\s+(?:de\s+)?(?:almacenaje|almacenamiento)\s+al\s+vacio\b', re.I)),
    ('STORAGE_BAG', re.compile(r'\b(?:bolsas?|fundas?)\s+(?:de\s+)?(?:almacenaje|almacenamiento)\b', re.I)),
    ('STORAGE_BOX', re.compile(r'\b(?:cajas?|contenedores?)\s+(?:de\s+)?(?:almacenaje|almacenamiento|organizacion)\b', re.I)),
    ('BOWL_SET', re.compile(r'\b(?:juego|set)\s+de\s+(?:\d+\s+)?cuencos?\b|\bcuencos?\s+de\s+acero\b', re.I)),
    ('CUTLERY_SET', re.compile(r'\b(?:juego|set)\s+de\s+cubiertos?\b|\bcubiertos?\b.{0,30}\b(?:piezas?|unidades?)\b', re.I)),
    ('FIREARM_SAFE', re.compile(r'\b(?:armero|armario\s+para\s+armas?|caja\s+fuerte\s+para\s+(?:\d+\s+)?(?:rifles?|armas?)|caja\s+de\s+municiones|caja\s+para\s+cartuchos)\b', re.I)),
    ('GARDEN_SHED', re.compile(r'\b(?:caseta|cobertizo)\s+(?:de\s+)?(?:jardin|exterior|metal|almacenaje)\b', re.I)),
    ('PORTABLE_POWER_STATION', re.compile(r'\b(?:estacion\s+de\s+energia|power\s+station|central\s+electrica\s+portatil)\b', re.I)),
    ('CHRISTMAS_DECOR_STORAGE', re.compile(r'\b(?:bolsa|funda|caja)\s+de\s+(?:almacenamiento|almacenaje)\s+(?:para|de)\s+(?:adornos?|decoraciones?|coronas?|guirnaldas?)\s+naviden\w*', re.I)),
    ('CHRISTMAS_DECOR_OBJECT', re.compile(r'\b(?:adorno|decoracion|figura)\s+naviden\w*', re.I)),
    ('USB_STORAGE_MEDIA', re.compile(r'\b(?:memoria|pendrive|flash\s*drive|unidad)\s+usb\b', re.I)),
    ('USB_POWERED_APPLIANCE', re.compile(r'\b(?:ventilador|humidificador|purificador|enfriador|aire acondicionado)\b.{0,100}\busb\b|\busb\b.{0,100}\b(?:ventilador|humidificador|purificador|enfriador)\b', re.I)),
    ('WATER_JUG', re.compile(r'\b(?:jarra|jarras)\s+(?:de\s+)?(?:agua|acero|agua\s+de\s+acero)\b', re.I)),
    ('LIVING_ROOM_FURNITURE_SET', re.compile(r'\b(?:conjunto|juego|set)\s+(?:de\s+)?(?:salon|comedor|dormitorio|muebles)\b|\bmueble\s+de\s+(?:salon|comedor|dormitorio)\b', re.I)),
    ('BATHROOM_VANITY_SET', re.compile(r'\b(?:mueble|conjunto)\s+de\s+ban\w*.{0,100}\b(?:lavabo|grifo|compartimentos?)\b', re.I)),
]

FURNITURE_RESEARCH = {'LIVING_ROOM_FURNITURE_SET', 'BATHROOM_VANITY_SET'}
FIREARMS_OUT_OF_SCOPE = set()
MAJOR_APPLIANCE_OUT_OF_SCOPE = set()
SPECIALIZED_OUT_OF_SCOPE = set()


def classify_subject(title: str, ft: dict) -> dict:
    """Identify an evidenced subject and explicit counterexamples to broad matches."""
    text = norm(title)
    # The existing V2 extractor stops its identity prefix at purpose and
    # compatibility connectors; use it to keep mentioned host products out of
    # the sold-subject slot. A firearm safe is the exception: its use qualifier
    # proves the specialization, but its head still must be the sold item.
    prefix = norm(ft.get('identity_prefix') or text)
    accessory_lead = re.match(r'^(?:(?:[a-z0-9]+)\s+){0,2}(?:deflector|filtro|protector|soporte|adaptador|panel|mando|recambio|repuesto|pieza|funda|botellero)\b', prefix)
    found = []
    for key, pattern in SUBJECT_PATTERNS:
        match = pattern.search(prefix)
        if not match:
            continue
        # A host appliance mentioned after an accessory lead is context, not
        # the product being sold. This guards e.g. an AC compressor deflector.
        if key == 'AIR_CONDITIONER' and accessory_lead:
            continue
        found.append((key, match.group(0)))
    found_codes={key for key,_ in found}
    if 'AIR_CONDITIONER' in found_codes and re.search(r'\b(?:mini|\d+\s*ml|usb|sin tubo|sin perforacion|ventilador|luz nocturna|enfriador evaporativo)\b',text):
        return {'status':'CLEAR','class_code':'EVAPORATIVE_COOLER','evidence_span':' '.join(span for key,span in found if key in {'AIR_CONDITIONER','USB_POWERED_APPLIANCE'})}
    if not any(k == 'FIREARM_SAFE' for k, _ in found):
        subject_safe = re.match(r'^(?:(?:[a-z0-9]+)\s+){0,2}(?:armero|armario|caja\s+fuerte|caja\s+de\s+municiones)\b', prefix)
        firearm_use = re.search(r'\b(?:rifles?|armas?|municion|cartuchos?)\b', text)
        if subject_safe and firearm_use:
            found.append(('FIREARM_SAFE', subject_safe.group(0)))
    if not any(k == 'BATHROOM_VANITY_SET' for k, _ in found):
        if re.search(r'\b(?:mueble|conjunto)\s+de\s+bano\b',prefix) and re.search(r'\b(?:lavabo|grifo|lavamanos|compartimentos?)\b',text):
            found.append(('BATHROOM_VANITY_SET','mueble de bano'))
    # Storage for seasonal objects is not itself a seasonal decoration.
    if any(k == 'CHRISTMAS_DECOR_STORAGE' for k, _ in found):
        found = [(k, span) for k, span in found if k != 'CHRISTMAS_DECOR_OBJECT']
    if any(k in {'STORAGE_BAG','VACUUM_STORAGE_BAG'} for k, _ in found):
        found = [(k, span) for k, span in found if k != 'CHRISTMAS_DECOR_OBJECT']
    if any(k == 'VACUUM_STORAGE_BAG' for k, _ in found):
        found = [(k, span) for k, span in found if k != 'STORAGE_BAG']
    distinct = list(dict.fromkeys(k for k, _ in found))
    if len(distinct) == 1:
        key = distinct[0]
        span = next(span for k, span in found if k == key)
        return {'status': 'CLEAR', 'class_code': key, 'evidence_span': span}
    if len(distinct) > 1:
        return {'status': 'UNCLEAR', 'class_code': '', 'evidence_span': ' / '.join(span for _, span in found), 'conflicting_classes': distinct}
    if ft.get('head') and ft.get('specific_type_supported'):
        return {'status': 'CLEAR', 'class_code': 'ACTION_HEAD:' + ft['head'], 'evidence_span': ft.get('identity_prefix', '')}
    # Do not turn arbitrary title text into a subject label. Unmapped nouns
    # stay unclear until a generic, reusable lexicon rule supports them.
    return {'status': 'UNCLEAR', 'class_code': '', 'evidence_span': ft.get('identity_prefix', '')}


def boundary_status(subject: dict, v24_boundary: dict, ft: dict | None = None, title: str = '') -> dict:
    code = subject.get('class_code', '')
    if code == 'FIREARM_SAFE':
        return {'status':'UNCONFIRMED_CUE','boundary_code':code,'evidence_span':subject['evidence_span'], 'reason':'专用枪柜主体可识别，但该用途是否属于已确认排除边界仍需人工校准。'}
    if code == 'AIR_CONDITIONER':
        text=norm(title)
        full_unit=bool(re.search(r'\b\d{4,5}\s*btu\b|\b(?:split|bomba de calor|compresor exterior|unidad exterior|kit de ventana)\b',text))
        mini_cooler=bool(re.search(r'\b(?:mini|500\s*ml|usb|sin tubo|sin perforacion|luz nocturna|ventilador)\b',text))
        if full_unit and not mini_cooler:
            return {'status':'CONFIRMED_CANDIDATE','boundary_code':code,'evidence_span':subject['evidence_span'], 'reason':'主体为有制冷能力规格/完整机组证据的空调。'}
        return {'status':'UNCONFIRMED_CUE','boundary_code':'AIR_OR_EVAPORATIVE_COOLER_UNRESOLVED','evidence_span':subject['evidence_span'], 'reason':'标题出现空调/冷风设备词，但没有足够证据区分完整空调与迷你冷风设备。'}
    if code in MAJOR_APPLIANCE_OUT_OF_SCOPE:
        return {'status':'CONFIRMED_CANDIDATE','boundary_code':code,'evidence_span':subject['evidence_span'], 'reason':'主体明确命中当前已声明的高置信度范围外候选边界。'}
    if code in FIREARMS_OUT_OF_SCOPE | SPECIALIZED_OUT_OF_SCOPE:
        return {'status':'UNCONFIRMED_CUE','boundary_code':code,'evidence_span':subject['evidence_span'], 'reason':'商品主体很具体，但货盘边界尚缺Owner确认；保留观察。'}
    if code in FURNITURE_RESEARCH or v24_boundary.get('code') == 'COMPLETE_LARGE_FURNITURE_SET' or (ft or {}).get('retail_form') == 'COMPLETE_FURNITURE':
        return {'status':'RESEARCH_ONLY','boundary_code':code,'evidence_span':subject['evidence_span'], 'reason':'完整家具按当前日用优先口径保留研究，不据此排除。'}
    if v24_boundary.get('clear'):
        return {'status':'CONFIRMED_CANDIDATE','boundary_code':v24_boundary.get('code',''),'evidence_span':v24_boundary.get('evidence_span',''), 'reason':'V2.4已定义边界且其主体检查通过。'}
    if v24_boundary.get('candidate'):
        return {'status':'UNCONFIRMED_CUE','boundary_code':v24_boundary.get('code',''),'evidence_span':v24_boundary.get('evidence_span',''), 'reason':'出现候选边界线索，但未证实线索描述被售商品主体。'}
    return {'status':'NONE','boundary_code':'','evidence_span':'','reason':''}


def reference_relation(subject: dict, ft: dict, ref: dict, matcher: Matcher) -> dict:
    rft = ref.get('feature', {})
    rtitle = ref.get('name_es_original', '')
    rsubject = classify_subject(rtitle, rft)
    relation, needs, conflict = matcher.relation(ft, ref)
    same = bool(subject.get('class_code') and subject.get('class_code') == rsubject.get('class_code'))
    # An Action token/head match is only same-class when supported by a concrete
    # title phrase. Inferred use or shared scenery cannot upgrade a relation.
    typed_classes={key for key,_ in SUBJECT_PATTERNS}
    if same and subject['class_code'] in typed_classes and relation in {'SAME_SPECIFIC_TYPE','RELATED_TYPE'} and not conflict:
        quality = 'SAME_CLASS'
    elif same and subject['class_code'].startswith('ACTION_HEAD:') and relation == 'SAME_SPECIFIC_TYPE' and not conflict:
        quality = 'SAME_CLASS'
    elif subject.get('status') == 'CLEAR' and rsubject.get('status') == 'CLEAR' and relation == 'SAME_SPECIFIC_TYPE' and not conflict:
        quality = 'SAME_CLASS' if same else 'RELATED_CLASS'
    elif relation in {'SAME_SPECIFIC_TYPE','RELATED_TYPE','SHARED_CONSUMER_NEED'} and not conflict:
        quality = 'RELATED_CLASS'
    else:
        quality = 'NOT_SAME_CLASS'
    return {'action_sku':ref.get('sku',''), 'action_title':rtitle, 'action_source_row_id':ref.get('source_row_id',''),
            'class_relation':quality, 'retrieval_relation':relation, 'shared_need_hypotheses':needs,
            'retrieval_score':None, 'context_conflict':bool(conflict),
            'reference_subject_class':rsubject.get('class_code','')}


def analyze(row: dict, matcher: Matcher, action_v23: dict) -> dict:
    title=row['title_original']; ft=matcher.f.extract(title,True)
    subject=classify_subject(title,ft)
    v24b=v24.boundary_for_title(title,ft)
    boundary=boundary_status(subject,v24b,ft,title)
    retrieved=matcher.retrieve([title])[0]
    refs=[]
    for j,score in retrieved:
        if score < matcher.policy['decision']['potential_min_retrieval']:
            continue
        ref=matcher.model['references'][j]
        item=reference_relation(subject,ft,ref,matcher)
        item['retrieval_score']=round(score,6)
        if item['class_relation'] != 'NOT_SAME_CLASS' or score >= matcher.policy['decision']['potential_min_retrieval']:
            refs.append(item)
    refs.sort(key=lambda x:(x['class_relation']!='SAME_CLASS',x['class_relation']!='RELATED_CLASS',-(x['retrieval_score'] or 0)))
    refs=refs[:3]
    has_real=any(r['action_sku'] and r['action_title'] for r in refs)
    same_refs=[r for r in refs if r['class_relation']=='SAME_CLASS']
    v23=action_v23
    common={'record_id':row['record_id'],'source_record_id':row.get('source_record_id',''),'source_row':row.get('source_row'),
            'input_hash':row['input_hash'],'title_original':title,'title_hash':v24.title_hash(title),
            'category_l1_original':row.get('category_l1_original',''),'category_auxiliary':row.get('category_auxiliary',''),
            'sample_cohort':row.get('sample_cohort',''),'identity_prefix_v24':ft.get('identity_prefix',''),
            'product_type_candidate_v23':v23.get('product_type_candidate') if v23.get('status')=='SPECIFIC_SEMANTIC_CANDIDATE' else None}
    if ft.get('source_invalid'):
        decision='观察'; reason='SOURCE_TITLE_INVALID'
    elif boundary['status']=='CONFIRMED_CANDIDATE':
        decision='用不到'; reason='SUBJECT_BOUND_CONFIRMED_BOUNDARY'
    elif subject['status']!='CLEAR':
        decision='观察'; reason='PRODUCT_SUBJECT_UNCLEAR'
    elif boundary['status'] in {'UNCONFIRMED_CUE','RESEARCH_ONLY'}:
        decision='观察'; reason='BOUNDARY_OR_RESEARCH_SCOPE_REQUIRES_REVIEW'
    elif same_refs and ft.get('task_frames') and not same_refs[0]['context_conflict']:
        decision='保留'; reason='CLEAR_SUBJECT_SAME_CLASS_ACTION_REFERENCE'
    else:
        decision='观察'
        if boundary['status']=='UNCONFIRMED_CUE': reason='BOUNDARY_CUE_UNCONFIRMED'
        elif not refs: reason='NO_USABLE_ACTION_REFERENCE'
        elif not same_refs: reason='ACTION_REFERENCE_NOT_CONFIRMED_SAME_CLASS'
        else: reason='NO_SOURCE_SUPPORTED_USE_CUE'
    return common | {'decision':decision,'reason_code':reason,
        'product_subject_status':subject['status'],'product_subject_class':subject.get('class_code',''),
        'product_subject_evidence':subject.get('evidence_span',''),
        'action_reference_exists':has_real,'action_reference_same_class':bool(same_refs),
        'action_reference_relation':('SAME_CLASS' if same_refs else ('RELATED_CLASS' if any(r['class_relation']=='RELATED_CLASS' for r in refs) else ('NOT_SAME_CLASS' if refs else 'NO_REFERENCE'))),
        'action_references':refs,'boundary_status':boundary['status'],'boundary_code':boundary.get('boundary_code',''),
        'boundary_evidence_span':boundary.get('evidence_span',''),'boundary_reason':boundary.get('reason',''),
        'human_confirmed':False,'method_version':VERSION}


def focus_titles() -> set[str]:
    if not FOCUS_XLSX.exists(): return set()
    import openpyxl
    book=openpyxl.load_workbook(FOCUS_XLSX,read_only=True,data_only=True)
    ws=book['重点SKU预审']
    return {v24.title_hash(str(row[3])) for row in list(ws.iter_rows(min_row=2,values_only=True)) if row[3]}


def prior_v25_titles() -> set[str]:
    hashes=set()
    for path in OUT.rglob('inputs_100.jsonl') if OUT.exists() else []:
        for row in lines(path):
            title=row.get('title_original','')
            if title: hashes.add(v24.title_hash(title))
    return hashes


def choose_sample(inputs: list[dict]) -> tuple[list[dict],dict]:
    v24_rows={v24.title_hash(r['title_original']) for r in lines(v24.OUT/'inputs_500.jsonl')}
    v25_dev=prior_v25_titles()
    forbidden=v24.prior_title_hashes() | v24_rows | focus_titles() | v25_dev
    available=[r for r in inputs if v24.title_hash(r['title_original']) not in forbidden]
    cues=re.compile(r'\b(?:aire acondicionado|armario para armas|armero|rifles?|municion|conjunto de salon|mueble de ban\w*|industrial|profesional|caseta|cobertizo|estacion de energia|power station|para frigorifico|compatible con)\b',re.I)
    boundary=[r for r in available if cues.search(v24.norm(r['title_original']))]
    randomizer=random.Random(SEED); randomizer.shuffle(boundary)
    selected=[]; ids=set()
    for r in boundary:
        if len(selected)>=50: break
        if r['record_id'] not in ids: selected.append(r); ids.add(r['record_id'])
    rest=[r for r in available if r['record_id'] not in ids]; randomizer.shuffle(rest)
    if len(selected)<50: raise RuntimeError('V25_INSUFFICIENT_BOUNDARY_COHORT')
    selected += rest[:50]
    for i,r in enumerate(selected): r['sample_cohort']='boundary_cue_unseen50' if i<50 else 'seeded_random_unseen50'
    return selected,{'total':len(selected),'boundary_cue':50,'seeded_random':50,
        'excluded_rows_in_snapshot':len(inputs)-len(available),'forbidden_title_hash_count':len(forbidden),
        'available_after_exclusion':len(available),'ai_audit_focus_titles_excluded':len(focus_titles()),
        'prior_v25_development_titles_excluded':len(v25_dev),'seed':SEED}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    source=read(v24.SOURCE)
    if v24.p.filehash(source['source_file'])!=source['source_sha256'] or source['source_rows']!=20018:
        raise RuntimeError('V25_AMAZON_SOURCE_FINGERPRINT_MISMATCH')
    inputs=lines(v24.INPUTS); matcher=Matcher(); action_v23={r['sku']:r for r in lines(v24.V23)}
    selected,sampling=choose_sample(inputs)
    results=[]
    for row in selected:
        ft=matcher.f.extract(row['title_original'],True); b=v24.boundary_for_title(row['title_original'],ft)
        v24row=dict(row);v24row.update({'_v24_feature':ft,'_v24_boundary':b})
        old=v24.refs_and_decision(v24row,matcher,action_v23)
        new=analyze(row,matcher,action_v23)
        results.append({'record_id':row['record_id'],'source_hash':row['input_hash'],'cohort':row['sample_cohort'],
                        'title_original':row['title_original'],'v24_decision':old['decision'],'v24_reason_code':old['reason_code'],
                        'v25':new})
    counts={'v24':dict(collections.Counter(r['v24_decision'] for r in results)),
            'v25':dict(collections.Counter(r['v25']['decision'] for r in results)),
            'subject_status':dict(collections.Counter(r['v25']['product_subject_status'] for r in results)),
            'reference_relation':dict(collections.Counter(r['v25']['action_reference_relation'] for r in results)),
            'boundary_status':dict(collections.Counter(r['v25']['boundary_status'] for r in results)),
            'decision_transitions':dict(collections.Counter(r['v24_decision']+' → '+r['v25']['decision'] for r in results))}
    contract={'version':VERSION,'sample_size':len(results),'source_sha256':source['source_sha256'],
              'action_reference_index_sha256':v24.p.filehash(RUN/'retrieval_index.joblib'),
              'action_v23_results_sha256':v24.p.filehash(v24.V23),'v24_run_id':v24.read(v24.OUT/'run_contract.json')['run_id'],
              'engine_sha256':v24.p.filehash(__file__),'focus_audit_sha256':v24.p.filehash(FOCUS_XLSX),
              'seed':SEED,'sample_role':'independent_frozen_rules_validation','human_gold':0,'accuracy':None,'v24_frozen':True,'purpose':'paired shadow validation; no superiority claim'}
    run_id='amazon-boundary-v25-'+v24.p.digest({'contract':contract,'ids':[r['record_id'] for r in selected]})[:16]
    run_dir=OUT/run_id
    run_dir.mkdir(parents=True,exist_ok=True)
    manifest={'run_id':run_id,'contract':contract,'sampling':sampling,'counts':counts,
              'limitations':{'human_gold':0,'accuracy':None,'false_exclusion_rate':None,'improvement_claimed':False,'v24_modified':False,'master_modified':False,'action_index_retrained':False}}
    v24.p.immutable(run_dir/'inputs_100.jsonl',selected,jsonl=True)
    v24.p.immutable(run_dir/'paired_results_100.jsonl',results,jsonl=True)
    v24.p.immutable(run_dir/'run_contract.json',contract)
    v24.p.immutable(run_dir/'summary.json',manifest)
    review=run_dir/'human_review_100.csv'
    rows=[]
    for i,r in enumerate(results,1):
        n=r['v25']; rows.append({'审核编号':f'AB25-{i:03d}','样本层':r['cohort'],'Amazon西语品名':r['title_original'],
            'V2.4结论':r['v24_decision'],'V2.5结论':n['decision'],'V2.5原因':n['reason_code'],
            '商品主体状态':n['product_subject_status'],'主体类型候选':n['product_subject_class'],'主体证据':n['product_subject_evidence'],
            '真实Action参照':n['action_reference_exists'],'同类Action参照':n['action_reference_same_class'],'参照关系':n['action_reference_relation'],
            'Action参照SKU':' / '.join(x['action_sku'] for x in n['action_references']),
            '边界状态':n['boundary_status'],'边界类别':n['boundary_code'],'边界证据':n['boundary_evidence_span'],
            '人工裁定':'','人工原因':'','审核人':'','记录ID':r['record_id'],'输入Hash':r['source_hash']})
    if not review.exists():
        with review.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    else: raise RuntimeError('V25_REVIEW_FILE_ALREADY_EXISTS; use new run id')
    # The run is initially preserved as immutable files. Append to the shared
    # learning DB only after a valid online backup and namespace-specific replay checks.
    backup=run_dir/'learning_before_v25.sqlite3'
    if not backup.exists():
        src=sqlite3.connect(DB);dst=sqlite3.connect(backup);src.backup(dst);dst.close();src.close()
    with sqlite3.connect(backup) as c:
        if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or c.execute('PRAGMA foreign_key_check').fetchall(): raise RuntimeError('V25_BACKUP_INVALID')
    with sqlite3.connect(DB,timeout=90) as c:
        c.execute('PRAGMA foreign_keys=ON')
        before={t:c.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'") if not t.startswith('assortment_v25_boundary_')}
        c.executescript('CREATE TABLE IF NOT EXISTS assortment_v25_boundary_runs(run_id TEXT PRIMARY KEY,contract TEXT NOT NULL,payload TEXT NOT NULL); CREATE TABLE IF NOT EXISTS assortment_v25_boundary_records(run_id TEXT NOT NULL,record_id TEXT NOT NULL,input_hash TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(run_id,record_id),FOREIGN KEY(run_id) REFERENCES assortment_v25_boundary_runs(run_id));')
        c.execute('INSERT INTO assortment_v25_boundary_runs VALUES(?,?,?)',(run_id,v24.p.canonical(contract),v24.p.canonical(manifest)))
        for r in results:c.execute('INSERT INTO assortment_v25_boundary_records VALUES(?,?,?,?)',(run_id,r['record_id'],r['source_hash'],v24.p.canonical(r)))
        c.commit()
        after={t:c.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for t in before}
        integrity=c.execute('PRAGMA integrity_check').fetchone()[0];fk=len(c.execute('PRAGMA foreign_key_check').fetchall())
        if before!=after or integrity!='ok' or fk: raise RuntimeError('V25_DATABASE_INTEGRITY_FAILURE')
        # Verify exact replay is a no-op and old namespaces remain byte-count stable.
        duplicate=sum(c.execute('SELECT count(*) FROM assortment_v25_boundary_records WHERE run_id=? AND record_id=? AND input_hash=?',(run_id,r['record_id'],r['source_hash'])).fetchone()[0] for r in results)
        if duplicate!=len(results): raise RuntimeError('V25_REPLAY_CHECK_FAILED')
    safety={'backup_integrity':'ok','integrity_check':integrity,'foreign_key_violations':fk,
            'all_preexisting_non_v25_table_counts_unchanged':True,'records_appended':len(results),'master_write':False}
    v24.p.immutable(run_dir/'persistence_and_safety.json',safety)
    report=['# ActionSelectionSkill V2.5 paired shadow run','',f"Run: `{run_id}`",'',
        'This is a paired program comparison on 100 titles not used in the V2.4 500-row run or the attached AI-audit focus cases. It is not a human accuracy evaluation.',
        '', '## Counts', '', '```json',json.dumps(counts,ensure_ascii=False,indent=2),'```','',
        'The supplied AI audit was used only to identify recurring failure modes and to exclude its 27 focus titles from the unseen cohort. Its proposed labels were not imported as Gold.',
        'Human-confirmed labels: 0. Accuracy, false-exclusion rate, and improvement remain unavailable.',
        'Large furniture remains research-only under the existing daily-use-first scope. Missing or weak Action references never cause `用不到`.',
        'Master, source snapshots, Action V2.3 feature index and frozen V2.4 outputs were not modified.']
    (run_dir/'V2.5_执行报告.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    print(json.dumps({'run_id':run_id,'run_dir':str(run_dir),'counts':counts,'sampling':sampling,'safety':safety},ensure_ascii=False))


if __name__=='__main__': main()
