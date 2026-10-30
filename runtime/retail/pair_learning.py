"""Explicit opt-in V3.3 pairwise ranker. Never imported by the default engine.

No prices, SKU/title identifiers, AI relation/score/rank or file paths are model
features. Labels and observed facts are separate, append-only evidence layers.
All artifacts from AI labels remain EXPERIMENTAL_WEAK_SUPERVISION.
"""
from __future__ import annotations
import collections, datetime, itertools, json, math, random, re, sqlite3, time
from pathlib import Path
from runtime.v3.core import digest
from runtime.v3.workflow import filehash, write_jsonl
from runtime.retail.attributes import extract, verify, fold, package

VERSION = 'pair-learning-v33.0'
RELATIONS = {'VERIFIED_IDENTICAL','SAME_TYPE','FUNCTIONAL_ALTERNATIVE','SHARED_NEED','UNRELATED','INSUFFICIENT_EVIDENCE'}
AUTHORITIES = {'HUMAN_GOLD','SOURCE_ANCHORED','AI_SILVER','UNVERIFIED'}
SCOPE = {'WHOLE','COMPONENT','UNKNOWN'}
SPEC = {'SAME','DIFFERENT','UNKNOWN','NOT_APPLICABLE'}
BASE_FEATURES = ['text_similarity','e5_similarity','text_rr','semantic_rr','rrf_rr','token_jaccard','e5_available','text_rank_missing','semantic_rank_missing']
STRUCT_FEATURES = ['family_same','family_different','family_unknown','role_conflict','attribute_equal','attribute_different','attribute_missing','model_equal','model_conflict','package_same_explicit','package_different_explicit','reference_spec_available','input_spec_available']
FEATURES = BASE_FEATURES + STRUCT_FEATURES

def read(path):
    return [json.loads(s) for s in Path(path).read_text(encoding='utf-8-sig').splitlines() if s.strip()]

def save(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

def immutable(path, value):
    path=Path(path)
    if path.exists():
        if json.loads(path.read_text(encoding='utf8')) != value:raise ValueError('IMMUTABLE_ARTIFACT_EXISTS')
    else:save(path,value)

def source_identity(row):
    return digest([row['source_platform'],row['source_product_id']])

def normalized_title(title):
    return re.sub(r'[^a-z0-9]+',' ',fold(title)).strip()

def pair_record(result, candidate, weak=None):
    src=result['source'];rid=candidate['sku'];identity=source_identity(src)
    relation={'IDENTICAL':'VERIFIED_IDENTICAL','SUBSTITUTE':'FUNCTIONAL_ALTERNATIVE','INSUFFICIENT':'INSUFFICIENT_EVIDENCE'}.get((weak or {}).get('relation'),(weak or {}).get('relation','INSUFFICIENT_EVIDENCE'))
    # AI cannot establish verified identity, including when old schemas allowed it.
    if relation=='VERIFIED_IDENTICAL':relation='INSUFFICIENT_EVIDENCE'
    return dict(pair_id=digest([identity,rid,src['source_sha256'],digest(candidate)]),input_id=identity,
        input=src,reference=dict(sku=rid,title=candidate['title'],spec=candidate.get('spec','')),
        relation=relation,scope=(weak or {}).get('scope','UNKNOWN'),spec_relation=(weak or {}).get('spec_status','UNKNOWN'),
        label_authority='AI_SILVER' if weak else 'UNVERIFIED',source_facts=[],
        label_origin=dict(result_hash=digest(result),analysis_hash=digest(result['analysis']),reason=(weak or {}).get('reason','Candidate not analyzed; unknown is not a negative'),reviewer=None,reviewed_at=None),
        original_ai_pair=weak,original_model_form=(result.get('analysis') or {}).get('form'),
        group_key=src.get('source_evidence',{}).get('family_key') or src.get('family_key') or normalized_title(src['title_original']),
        split=None,features=None)

def build_pairs(results, requests, candidates_per_input=8):
    if not 5<=candidates_per_input<=10:raise ValueError('CANDIDATE_COUNT_5_TO_10')
    pairs=[];seen=set()
    for result in results:
        sid=source_identity(result['source'])
        if sid in seen:raise ValueError('DUPLICATE_INPUT_PRODUCT')
        seen.add(sid);req=requests[result['record_id']];by={c['sku']:c for c in req['action_candidates']}
        # Preserve raw analysis labels, not deterministic post-processing outputs.
        labeled={p['sku']:p for p in result['analysis']['pairs']}
        ids=list(labeled)+[s for s in by if s not in labeled]
        for sku in ids[:candidates_per_input]:
            if sku not in by:raise ValueError('LABEL_REFERENCE_OUTSIDE_REQUEST')
            p=pair_record(result,by[sku],labeled.get(sku))
            score=next((m['scoring']['match_score_10'] for m in result['matches'] if m['reference_id']==sku),None)
            p.update(baseline_score_10=score,baseline_analysis_member=sku in labeled,request_hash=digest(req))
            pairs.append(p)
    return pairs

def grouped_split(pairs, family_keys, seed=3301):
    """Connect identities/known families before assigning entire components."""
    parent={p['input_id']:p['input_id'] for p in pairs}
    def find(x):
        while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
        return x
    def union(a,b):parent[find(a)]=find(b)
    owners={}
    for p in pairs:
        keys={p['group_key'],'title:'+normalized_title(p['input']['title_original'])}
        ev=p['input'].get('source_evidence',{});pe=ev.get('parent_evidence',ev)
        if pe.get('Parent ASIN'):keys.add('parent:'+str(pe['Parent ASIN']))
        if p['relation']=='SAME_TYPE' and p['scope']=='WHOLE':keys.add('type:'+family_keys.get(p['reference']['sku'],p['reference']['sku']))
        for key in keys:
            if key in owners:union(p['input_id'],owners[key])
            else:owners[key]=p['input_id']
    # Same normalized maker/model/title tokens across platforms may still escape:
    # use a conservative title char-ngram duplicate graph, excluding numeric noise.
    ids=list(parent);titles={p['input_id']:p['input']['title_original'] for p in pairs}
    if len(ids)>1:
        from sklearn.feature_extraction.text import TfidfVectorizer
        matrix=TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5)).fit_transform([normalized_title(titles[i]) for i in ids])
        sims=(matrix@matrix.T).toarray()
        for a in range(len(ids)):
            for b in range(a):
                if sims[a,b]>=.80:union(ids[a],ids[b])
    groups=collections.defaultdict(list)
    for sid in parent:groups[find(sid)].append(sid)
    ordered=sorted(groups);random.Random(seed).shuffle(ordered)
    # Group counts, not pair rows. No label-stratified retries of test allocation.
    cut1=max(1,int(len(ordered)*.65));cut2=max(cut1+1,int(len(ordered)*.82))
    assigned={sid:('train' if i<cut1 else 'dev' if i<cut2 else 'historical_holdout') for i,g in enumerate(ordered) for sid in groups[g]}
    for p in pairs:p.update(split=assigned[p['input_id']],isolation_group=digest(sorted(groups[find(p['input_id'])])))
    return dict(seed=seed,groups=len(groups),products=dict(collections.Counter(assigned.values())),pairs=dict(collections.Counter(p['split'] for p in pairs)),family_proxy_limit='Parent/title/AI candidate type/char .80 graph; missing GTIN and cross-language identities remain incomplete')

class FeatureExtractor:
    def __init__(self,refs,index):
        from runtime.retail.hybrid import HybridRetriever
        self.refs=refs;self.hybrid=HybridRetriever(refs,index);self.cache={}
        if not self.hybrid.index:raise ValueError('E5_REQUIRED_FOR_EXPERIMENT')
        self.binding=dict(reference_hash=refs.version,e5_vectors=self.hybrid.index.meta['vectors_sha'],e5_revision=self.hybrid.index.meta['revision'],feature_version=VERSION)

    def query(self,source,ids):
        import numpy as np
        key=digest([source['title_original'],source.get('specifications','')])
        if key not in self.cache:
            _,trace=self.hybrid.search(source,limit=50)
            # Reuse exact existing E5 cache key and normalized vector. No second AI.
            index=self.hybrid.index;index.search(source['title_original']+' '+source.get('specifications',''),50)
            qkey=digest([index.meta['revision'],index.meta['vectors_sha'],source['title_original']+' '+source.get('specifications','')])
            db=sqlite3.connect(index.path/'query_cache.sqlite3')
            try:q=np.frombuffer(db.execute('SELECT vector FROM queries WHERE key=?',(qkey,)).fetchone()[0],dtype='float32')
            finally:db.close()
            self.cache[key]=(trace,index.vectors@q)
        trace,dense=self.cache[key];position={s:i for i,s in enumerate(self.hybrid.index.ids)}
        text=self.refs.catalog.score_skus(source['title_original'],ids);out={}
        ranks={route:{s:i for i,s in enumerate(trace.get(route,[]),1)} for route in ['text50','semantic50','rrf50']}
        a=extract(source['title_original'],source.get('specifications',''));left=set(self.refs.catalog._words(source['title_original']));pa=package(source['title_original'])
        for sku in ids:
            ref=self.refs.catalog.by_sku[sku];q=self.refs.quotes.get(sku) or {};spec=q.get('specifications','') if q.get('binding_valid') else ''
            b=extract(ref['name_es_original'],spec);v=verify(a,b);right=set(self.refs.catalog._words(ref['name_es_original']));comp=v['comparisons']
            pb=package(ref['name_es_original']);explicit={'HOMOGENEOUS_MULTIPACK','MAIN_WITH_ACCESSORY','REPLACEMENT_ACCESSORY'}
            attrs=a['attributes'];bat=b['attributes'];known=bool(a['family'] and b['family'])
            vals=[text[sku],float(dense[position[sku]]),*[1/ranks[r][sku] if sku in ranks[r] else 0. for r in ['text50','semantic50','rrf50']],len(left&right)/max(1,len(left|right)),1.,float(sku not in ranks['text50']),float(sku not in ranks['semantic50']),float(known and a['family']==b['family']),float(known and a['family']!=b['family']),float(not known),float('WHOLE_ACCESSORY_SCOPE_UNCONFIRMED' in v['unknown']),sum(c['status']=='EQUAL' for c in comp),sum(c['status']=='DIFFERENT' for c in comp),sum(c['status']=='MISSING_SOURCE' for c in comp),float(bool(attrs.get('model') and bat.get('model') and attrs['model']==bat['model'])),float(bool(attrs.get('model') and bat.get('model') and attrs['model']!=bat['model'])),float(pa in explicit and pa==pb),float(pa in explicit and pb in explicit and pa!=pb),float(bool(spec)),float(bool(source.get('specifications')))]
            out[sku]=dict(zip(FEATURES,vals))
        return out,trace

def validate_label(row):
    if row.get('relation') not in RELATIONS or row.get('scope') not in SCOPE or row.get('spec_relation') not in SPEC or row.get('label_authority') not in AUTHORITIES:raise ValueError('INVALID_PAIR_LABEL')
    auth=row['label_authority'];proof=row.get('evidence',{})
    if auth in {'HUMAN_GOLD','SOURCE_ANCHORED'}:
        if not all(proof.get(k) for k in ['file','sha256','reason','reviewed_at']):raise ValueError('EVIDENCE_RECEIPT_REQUIRED')
        if filehash(Path(proof['file']))!=proof['sha256']:raise ValueError('EVIDENCE_HASH_CHANGED')
    if auth=='HUMAN_GOLD' and (not proof.get('reviewer','').startswith('human:') or not proof.get('independent_reviewer') or not proof.get('human_confirmation_id')):raise ValueError('INDEPENDENT_HUMAN_RECEIPT_REQUIRED')
    if row['relation']=='VERIFIED_IDENTICAL' and not (proof.get('identity_basis') and auth in {'HUMAN_GOLD','SOURCE_ANCHORED'}):raise ValueError('VERIFIED_IDENTITY_PROOF_REQUIRED')

class LabelStore:
    def __init__(self,path):
        Path(path).parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS pair_label_events(id TEXT PRIMARY KEY,pair_id TEXT NOT NULL,previous TEXT,payload TEXT NOT NULL)');self.db.commit()
    def import_label(self,row,pairs):
        validate_label(row);pair=pairs.get(row['pair_id'])
        if not pair or row.get('pair_source_hash')!=digest(pair):raise ValueError('PAIR_SOURCE_BINDING_MISMATCH')
        previous=self.db.execute('SELECT id,payload FROM pair_label_events WHERE pair_id=? ORDER BY rowid DESC LIMIT 1',(row['pair_id'],)).fetchone()
        h=digest(row)
        if self.db.execute('SELECT 1 FROM pair_label_events WHERE id=?',(h,)).fetchone():return 'NO_OP'
        if previous and row.get('supersedes')!=previous[0]:raise ValueError('LABEL_CONFLICT_REQUIRES_EXPLICIT_SUPERSEDES')
        self.db.execute('INSERT INTO pair_label_events VALUES(?,?,?,?)',(h,row['pair_id'],previous[0] if previous else None,json.dumps(row,ensure_ascii=False)));self.db.commit();return h
    def close(self):self.db.close()

def relevance(pair):
    """Weak preference for primary WHOLE references, not identity/10-point score."""
    if pair['label_authority']=='UNVERIFIED' or pair['relation']=='INSUFFICIENT_EVIDENCE':return None
    if pair['scope']=='UNKNOWN' and pair['relation']!='UNRELATED':return None
    if pair['relation']=='UNRELATED':return 0
    if pair['scope']=='COMPONENT':return 0
    return {'VERIFIED_IDENTICAL':4,'SAME_TYPE':3,'FUNCTIONAL_ALTERNATIVE':2,'SHARED_NEED':1}.get(pair['relation'])

def train(pairs,out,variant='B',c=1.0):
    import numpy as np,sklearn
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    if variant not in {'B','C'}:raise ValueError('INVALID_VARIANT')
    features=BASE_FEATURES if variant=='B' else FEATURES
    selected=[p for p in pairs if p['split']=='train' and relevance(p) is not None]
    if not selected:raise ValueError('NO_TRAINING_LABELS')
    x=np.array([[p['features'][k] for k in features] for p in selected]);scaler=StandardScaler().fit(x)
    by=collections.defaultdict(list)
    for p,z in zip(selected,scaler.transform(x)):by[p['input_id']].append((p,z))
    diffs=[];ys=[];weights=[];effective=[]
    for input_id,group in by.items():
        comparisons=[(a,b) for a,b in itertools.combinations(group,2) if relevance(a[0])!=relevance(b[0])]
        if comparisons:effective.append(input_id)
        for (a,va),(b,vb) in comparisons:
            y=int(relevance(a)>relevance(b));diffs.extend([va-vb,vb-va]);ys.extend([y,1-y]);weights.extend([.5/len(comparisons)]*2)
    if len(effective)<2:raise ValueError('INSUFFICIENT_PREFERENCE_GROUPS')
    started=time.perf_counter();clf=LogisticRegression(C=c,fit_intercept=False,random_state=3301,max_iter=2000,solver='lbfgs').fit(diffs,ys,sample_weight=weights);elapsed=time.perf_counter()-started
    artifact=dict(version=VERSION,status='EXPERIMENTAL_WEAK_SUPERVISION',variant=variant,features=features,coef=clf.coef_[0].tolist(),mean=scaler.mean_.tolist(),scale=scaler.scale_.tolist(),dataset_hash=digest(pairs),training_ids=sorted(effective),training_pairs=len(selected),preference_rows=len(ys),C=c,fit_seconds=elapsed,sklearn=sklearn.__version__,feature_binding=pairs[0]['feature_binding'],created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),human_gold=sum(p['label_authority']=='HUMAN_GOLD' for p in selected),formal_promotion=False,score_semantics='unbounded pairwise utility; never a probability or 0-10 score')
    artifact['model_hash']=digest(artifact);immutable(out,artifact);return artifact

def load_model(path):
    model=json.loads(Path(path).read_text(encoding='utf8'));h=model.pop('model_hash')
    if digest(model)!=h or model['status']!='EXPERIMENTAL_WEAK_SUPERVISION':raise ValueError('MODEL_HASH_OR_STATUS_INVALID')
    if model['features'] not in [BASE_FEATURES,FEATURES] or any(len(model[k])!=len(model['features']) for k in ['coef','mean','scale']) or any(not math.isfinite(v) for k in ['coef','mean','scale'] for v in model[k]) or any(v<=0 for v in model['scale']):raise ValueError('MODEL_FEATURE_CONTRACT_INVALID')
    model['model_hash']=h;return model

def utility(model,pair):
    if pair.get('feature_binding')!=model['feature_binding']:raise ValueError('MODEL_CATALOG_FEATURE_BINDING_CHANGED')
    values=[pair['features'][k] for k in model['features']]
    if any(not math.isfinite(v) for v in values):raise ValueError('NONFINITE_FEATURE')
    return sum((v-m)/s*c for v,m,s,c in zip(values,model['mean'],model['scale'],model['coef']))

def rerank(model,pairs,allow_experimental=False):
    if not allow_experimental:raise ValueError('EXPLICIT_EXPERIMENTAL_OPT_IN_REQUIRED')
    return sorted(pairs,key=lambda p:(-utility(model,p),p['reference']['sku']))

def evaluate(pairs,models):
    """Only the common AI-analyzed pool, unknowns not converted to negatives."""
    by=collections.defaultdict(list)
    for p in pairs:by[p['input_id']].append(p)
    methods={'A':None,**models};totals={m:collections.defaultdict(list) for m in methods};changes=[]
    for sid,allpairs in by.items():
        common=[p for p in allpairs if p.get('baseline_score_10') is not None and relevance(p) is not None]
        if not common:continue
        positives=[p for p in common if relevance(p)>=2]
        rankings={m:sorted(common,key=lambda p:(-p['baseline_score_10'],p['reference']['sku'])) if model is None else rerank(model,common,True) for m,model in methods.items()}
        for m,ranked in rankings.items():
            top=ranked[0];t=totals[m];t['top_primary_eligible'].append(float(relevance(top)>=2));t['component_top'].append(float(top['scope']=='COMPONENT'));t['top_unrelated'].append(float(top['relation']=='UNRELATED'))
            if positives:t['reciprocal_rank'].append(1/next(i for i,p in enumerate(ranked,1) if relevance(p)>=2))
            gains=[relevance(p) for p in ranked[:5]];ideal=sorted([relevance(p) for p in common],reverse=True)[:5]
            dcg=lambda g:sum((2**v-1)/math.log2(i+2) for i,v in enumerate(g))
            if dcg(ideal)>0:t['ndcg5'].append(dcg(gains)/dcg(ideal))
        row=dict(input_id=sid,platform=allpairs[0]['input']['source_platform'],product_id=allpairs[0]['input']['source_product_id'],title=allpairs[0]['input']['title_original'],common_candidates=len(common),top={m:r[0]['reference']['sku'] for m,r in rankings.items()},top_relevance={m:relevance(r[0]) for m,r in rankings.items()},top5={m:[p['reference']['sku'] for p in r[:5]] for m,r in rankings.items()})
        changes.append(row)
    metrics={m:{k:dict(value=sum(v)/len(v),denominator=len(v)) for k,v in t.items()} for m,t in totals.items()}
    return dict(label_basis='AI_SILVER_AGREEMENT_NOT_REAL_ACCURACY',metrics=metrics,changes=changes,full_catalog_recall=None,human_gold_metrics=None,primary_scope='common explicitly AI-labeled candidates only; unavailable scores/unknowns excluded, not false negatives',excluded_unknown_pairs=sum(relevance(p) is None for p in pairs))

def active_queue(pairs,models,limit=40,random_fraction=.2,seed=3301):
    by=collections.defaultdict(list)
    for p in pairs:by[p['input_id']].append(p)
    tasks=[]
    for sid,rows in by.items():
        ranked=rerank(models['C'] if 'C' in models else models['B'],rows,True);model=models.get('C',models['B']);margin=utility(model,ranked[0])-utility(model,ranked[1]) if len(ranked)>1 else 0.;p=ranked[0];f=p['features'];reasons=[]
        baseline=sorted([r for r in rows if r.get('baseline_score_10') is not None],key=lambda r:-r['baseline_score_10'])
        if margin<.15:reasons.append('CLOSE_TOP_TWO')
        if baseline and p['reference']['sku']!=baseline[0]['reference']['sku']:reasons.append('ALGORITHM_DISAGREEMENT')
        for k,reason in [('family_different','SUBJECT_CONFLICT'),('attribute_different','SPEC_CONFLICT'),('model_conflict','MODEL_CONFLICT'),('role_conflict','WHOLE_COMPONENT_RISK'),('family_unknown','TYPE_SCHEMA_UNKNOWN')]:
            if f[k]:reasons.append(reason)
        tasks.append(dict(input_id=sid,platform=p['input']['source_platform'],product_id=p['input']['source_product_id'],title=p['input']['title_original'],pair_id=p['pair_id'],reference=p['reference'],reasons=reasons,margin=margin,priority=len(reasons),human_relation=None,human_scope=None,human_reviewer=None,human_evidence=None))
    tasks.sort(key=lambda t:(-t['priority'],t['margin'],t['input_id']));n=min(limit,len(tasks));random_n=min(round(n*random_fraction),len(tasks));chosen=tasks[:n-random_n];pool=[t for t in tasks if t not in chosen];random.Random(seed).shuffle(pool)
    for t in chosen:t['sample_arm']='uncertainty_and_disagreement'
    for t in pool[:random_n]:t['sample_arm']='random_remaining'
    return chosen+pool[:random_n]

