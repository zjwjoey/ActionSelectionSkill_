"""Versioned title-grounded semantic candidates in the existing learning system.

No external model training, source writes, sealed-title reads or Amazon scoring.
Ordinary use is explicitly an inference, never a source fact or human gold.
"""
import argparse, collections, copy, hashlib, json, re, sqlite3, sys, unicodedata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import pipeline as p
OUT=ROOT/'outputs/action_semantic_v22_20261022'
OLD=ROOT/'rules/versions/name-semantics-v11-action5000-candidate'
POLICY=ROOT/'rules/action_semantic22_rules.tsv'
VERSION='action-semantic-deepening-v2.2'
BROAD=re.compile(r'^(?:待明确|核心用途待核|一般盛装需求|物品盛放|护理用品|日常使用|一般使用|日常实用|生活便利|服饰穿着|家居装饰|食品消费|休闲娱乐|手工制作|手工创作|收纳整理|植物养护|装饰空间|待核.*)$')
WEAK_NEEDS={'清洁需求','擦拭需求','铺垫需求','测量需求','覆盖需求','盛放需求','一般盛装','食品选择','食物选择','创作材料','个人修整','皮肤护理研究','化妆需求','休闲游戏','烹饪需求','照明需求','灯光配置','物品整理','穿戴装饰','服装穿着','装饰氛围','一般护理','辅助使用','灯光需求','家具配置','创作活动','空间装饰','氛围装饰','衣着配置','鞋履配置','盛装需求','表达与记录'}
GENERIC_TYPE=re.compile(r'^(?:用品|配件|容器|套装|材料|物品|商品|产品|装饰品|手工用品|清洁用品|食品|护理用品|多用途.*|.*所指物待定)$')

def norm(s):
    return re.sub(r'\s+',' ',''.join(c for c in unicodedata.normalize('NFKD',s.lower()) if not unicodedata.combining(c))).strip()

def load_rules():
    allrules=[]
    for file,key,tier in [('title_families.json','patterns',1),('action5000_policy.json','rules',2),('action5000_review_policy.json','rules',3)]:
        for r in json.loads((OLD/file).read_text(encoding='utf8'))[key]:
            allrules.append(dict(r,id=file+':'+r['id'],tier=tier))
    if POLICY.exists():
        for line in POLICY.read_text(encoding='utf8').splitlines():
            if not line or line.startswith('#'):continue
            k,rest=line.split('|',1);rx,typ,use,need=rest.rsplit('|',3)
            re.compile(rx)
            allrules.append(dict(id=k,regex=rx,product_type=typ,function=use,need=need,tier=4))
    return allrules

class Engine:
    def __init__(self,inputs):
        self.rules=load_rules()
        self.compiled=[(r,re.compile(r['regex'],re.I)) for r in self.rules]
        self.bytitle=collections.defaultdict(list)
        for x in inputs:
            a=x['prior']
            if a and a.get('usable_for_candidate_observations') and a['name_es_original']==x['name_es_original']:
                self.bytitle[x['name_es_original']].append(a)
        self.cache={}

    def match(self,title):
        if title in self.cache:return self.cache[title]
        # Only main object and explicit packaging wrappers can determine type.
        # A noun mentioned inside a purpose or accessory clause cannot replace it.
        starts={0}
        wrapper=re.match(r'^(?:(?:set|juego|pack|paquete|conjunto|kit|lote)\s+de\s+(?:\d+\s+)?)',title,re.I)
        if wrapper:starts.add(wrapper.end())
        found=[]
        for rule,rx in self.compiled:
            for start in starts:
                m=rx.search(title[start:])
                if not m or m.start()!=0:continue
                end=start+m.end()
                if end<len(title) and title[end].isalpha() and title[end-1].isalpha():continue
                # A set of objects is still that type; generic set-family labels
                # cannot defeat a more specific wrapped object.
                found.append({'rule':rule,'span':title[start:end],'start':start,'end':end})
        found.sort(key=lambda x:(x['rule']['tier'],x['end']-x['start']),reverse=True)
        self.cache[title]=found
        return found

    def analyze(self,x):
        title=x['name_es_original']; prior=x.get('prior'); matches=self.match(title)
        best=matches[0] if matches else None
        same=prior and prior['name_es_original']==title
        old=prior if same and prior.get('usable_for_candidate_observations') else None
        peers=self.bytitle.get(title,[])
        peer_types={r['product_type'] for r in peers}
        conflicts=[]
        if not old and len(peer_types)==1:old=peers[0]
        history_disagreement=len(peer_types)>1
        if history_disagreement:conflicts.append('HISTORICAL_SAME_TITLE_TYPE_DISAGREEMENT')
        if best:
            top=[m for m in matches if m['rule']['tier']==best['rule']['tier'] and m['end']-m['start']==best['end']-best['start']]
            if len({m['rule']['product_type'] for m in top})>1:conflicts.append('EQUAL_PRIORITY_TYPE_CONFLICT')
        explicit_override=best and best['rule']['tier']==4
        if explicit_override and len({m['rule']['product_type'] for m in matches if m['rule']['tier']==4 and m['end']-m['start']==best['end']-best['start']})==1:
            conflicts=[c for c in conflicts if c!='HISTORICAL_SAME_TITLE_TYPE_DISAGREEMENT']
        # Reuse same-source prior candidates; an override needs an explicit new
        # generic rule. Disagreement stays visible, not silently treated as truth.
        if old and not explicit_override:
            typ=old['product_type'];uses=old['primary_function'];needs=old['consumer_need'];basis='REUSED_PRIOR_CANDIDATE' if old['sku']==x['sku'] else 'REUSED_IDENTICAL_TITLE_CANDIDATE'
            evidence=[{'span':title,'start':0,'end':len(title),'role':'TITLE_IDENTITY'}]
            rule_id=None
        elif best:
            r=best['rule'];typ=r['product_type'];uses=[r.get('function','')];needs=[r.get('need','')];basis='GENERIC_TITLE_RULE';rule_id=r['id']
            evidence=[{'span':best['span'],'start':best['start'],'end':best['end'],'role':'MAIN_OBJECT_OR_TYPE_QUALIFIER'}]
        else:
            typ=None;uses=[];needs=[];basis='UNRESOLVED_TITLE';rule_id=None;evidence=[]
        hypotheses=[];broad=[]
        for n in needs:
            # Historical use/need arrays were never declared positional pairs.
            # Preserve the full use set, never invent zip-based correspondences.
            u='；'.join(uses)
            if not u or not n or BROAD.fullmatch(n) or n in WEAK_NEEDS:
                if u or n:broad.append({'use':u,'need':n})
            else:hypotheses.append({'use':u,'consumer_need':n,'evidence_span':title,'authority':'ORDINARY_USE_HYPOTHESIS_NOT_LITERAL_FACT'})
        # Uncertainty is dimension-specific: a known object may still have no
        # sufficiently discriminating use/need for cross-platform relations.
        flags=[]
        if not typ or GENERIC_TYPE.fullmatch(typ) or '待核' in typ or '待定' in typ:flags.append('TYPE_INSUFFICIENT')
        if not hypotheses:flags.append('SPECIFIC_NEED_INSUFFICIENT')
        if best and best['rule'].get('abstain'):flags.extend(best['rule']['abstain'])
        if conflicts:flags.append('RULE_OR_HISTORY_CONFLICT')
        if 'TYPE_INSUFFICIENT' in flags or conflicts:hypotheses=[]
        qualifiers=[{'span':m.group(),'start':m.start(),'end':m.end(),'authority':'TITLE_LITERAL_QUALIFIER'} for m in re.finditer(r'\b(?:para|con|sin|compatible con)\s+[^,;.|]+',title,re.I)]
        status='RULE_CONFLICT' if conflicts else 'RULE_COVERAGE_GAP' if typ is None else ('FEATURE_TOO_BROAD' if broad else 'INFORMATION_INSUFFICIENT') if flags else 'SPECIFIC_SEMANTIC_CANDIDATE'
        r={'sku':x['sku'],'snapshot_id':x['snapshot_id'],'source_row_id':x['source_row_id'],'name_es_original':title,'source_title_hash':x['source_title_hash'],'version':VERSION,'product_type_candidate':typ,'type_evidence':evidence,'literal_qualifiers':qualifiers,'use_need_hypotheses':hypotheses,'broad_hypotheses_not_for_matching':broad,'status':status,'uncertainty_codes':sorted(set(flags)),'rule_conflicts':conflicts,'historical_type_disagreement':history_disagreement,'bundle_prefix':re.match(r'^(?:set|juego|pack|paquete|conjunto|kit|lote)\b',title,re.I).group() if re.match(r'^(?:set|juego|pack|paquete|conjunto|kit|lote)\b',title,re.I) else None,'basis':basis,'rule_id':rule_id,'matching_rules':[{'id':m['rule']['id'],'type':m['rule']['product_type'],'span':m['span']} for m in matches], 'reconciliation':x['reconciliation'],'prior_binding':{'sku':old['sku'],'annotation_hash':old['annotation_hash'],'version':old['rules_version']} if old else ({'sku':prior['sku'],'annotation_hash':prior['annotation_hash'],'version':prior['rules_version']} if prior else None),'human_confirmed':False,'analysis_method':'VERSIONED_RULE_AND_CANDIDATE_REUSE_NOT_PER_ITEM_MODEL_INFERENCE','unsupported_attributes':[]}
        r['result_hash']=p.digest(r)
        return r

def run(label):
    inputs=p.read_jsonl(OUT/'inputs.jsonl'); engine=Engine(inputs)
    rows=[engine.analyze(x) for x in inputs]
    assert len(rows)==len({r['sku'] for r in rows})==10037
    target=OUT/label;target.mkdir(exist_ok=True)
    p.immutable(target/'rules.json',engine.rules)
    p.immutable(target/'results.jsonl',rows,jsonl=True)
    gaps=collections.defaultdict(list)
    for r in rows:
        if r['status']!='SPECIFIC_SEMANTIC_CANDIDATE':gaps[norm(r['name_es_original']).split()[0]].append(r)
    summary={'total':len(rows),'statuses':dict(collections.Counter(r['status'] for r in rows)),'bases':dict(collections.Counter(r['basis'] for r in rows)),'unique_titles':len(engine.cache),'rules':len(engine.rules),'type_candidates':sum(bool(r['product_type_candidate']) for r in rows),'specific_need_candidates':sum(bool(r['use_need_hypotheses']) for r in rows),'human_gold':0,'accuracy':None,'rule_conflict_skus':sum(bool(r['rule_conflicts']) for r in rows),'gap_heads':[{'head':h,'count':len(g),'examples':[r['name_es_original'] for r in g[:12]]} for h,g in sorted(gaps.items(),key=lambda z:-len(z[1]))]}
    p.immutable(target/'summary.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='gap_heads'},ensure_ascii=False))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);a=parser.parse_args();run(a.label)
