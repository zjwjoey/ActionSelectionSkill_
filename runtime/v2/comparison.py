"""Three reproducible program schemes; never label these independent AI arms.

A has no Action inputs. B is an explicitly limited frozen V10 rule replay.
C is frozen V2 retrieval+relation results. Old full-context AI V10 behavior is
not recreated by a regex adapter, and this limitation stays in the deliverable.
"""
import collections,importlib.util,json,random,re,sys
from pathlib import Path
from assortment import ROOT,RUN,WORK,p,read,lines,norm

def common_scope(title):
 t=norm(title)
 if re.search(r'\b(?:repuesto|recambio|compatible con|pieza de repuesto|cartucho de tinta|boquilla para)\b',t):return 'POTENTIAL_MATCH','名称说明配套或兼容关系，保留研究。'
 if re.search(r'\b(?:escritorio|sofa|comoda|mesa de centro|mesa de comedor|aparador|estructura de cama|armario)\b',t) and not re.search(r'\b(?:funda|organizador|protector|tirador|pata|mantel)\b',t[:70]):return 'POTENTIAL_MATCH','名称提示完整家具，按共同日用优先口径保留研究。'
 return None

def baseline_a(row):
 title=row['title_original'];n=norm(title);scope=common_scope(title)
 if scope:decision,reason=scope
 elif len(re.findall(r'[a-z]+',n))<3 or re.search('[\u3400-\u9fff\ufffd]',title):decision,reason='NEEDS_REVIEW','名称不足以支持可靠主体判断。'
 elif re.search(r'\b(?:reactor industrial|sistema de cromatografia|linea de produccion industrial|municion para arma de fuego)\b',n):decision,reason='LOW_MATCH','名称明确描述普通日用目标之外的专用系统。'
 elif re.search(r'\b(?:cocina|limpieza|hogar|organizador|almacenamiento|sarten|olla|cuchillo|toalla|almohada|boligrafo|lampara|taza|vaso|botella|mascota|ropa|cuaderno|decoracion|manualidades|cepillo|pelo|crema|pintura|jardin)\b',n):decision,reason='HIGH_MATCH','名称具有普通消费用品或生活任务线索，可进入核心研究候选。'
 else:decision,reason='POTENTIAL_MATCH','用途尚需进一步研究；没有依据直接排除。'
 return {'record_id':row['record_id'],'input_hash':row['input_hash'],'decision':decision,'reason':reason,'action_references':[],'method':'A_GENERAL_PROGRAM_PROXY_NOT_PLAIN_AI','human_confirmed':False}

def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def old_b(records):
 stage=module('legacy_v10_stage',ROOT/'outputs/staged_2000_20261022/execute_stage.py')
 literal=module('legacy_v10_literal',ROOT/'outputs/review487_20261022/review487.py')
 refine=module('legacy_v10_context',ROOT/'scripts/title_semantic_refinement.py')
 defs=p.load_rules('name-semantics-v10-context-guard');oldrefs=lines(ROOT/'outputs/review150_rules_20261022/final_2000_candidates.jsonl')
 results=[]
 for row in records:
  original={'sku':row['record_id'],'name_es_original':row['title_original'],'name_es_normalized':p.normalize_name(row['title_original']),'snapshot_id':'AMAZON_TECHNICAL_ONLY','source_row_id':row['record_id']}
  a=stage.classify(original,defs['title_families.json']['patterns'])
  for rule in defs['second_pass_policy.json']['rules']+defs['review487_policy.json']['literal_fix_rules']:
   m=re.search(rule['regex'],row['title_original'],re.I)
   if m:
    a={**a,**literal.from_literal(a,original,rule,m.group())};break
  a['usable_for_candidate_observations']=not bool(set(a['uncertainty_codes'])&set(defs['name_rules.json']['blocking_uncertainty_codes']))
  a['annotation_hash']=p.digest({k:a[k] for k in (*p.FIELDS,*p.EXTRA_FIELDS) if k in a})
  a['rules_version']='name-semantics-v10-context-guard'
  a,_=refine.apply(a,defs)
  scope=common_scope(row['title_original'])
  if scope:decision,reason=scope
  elif not a['usable_for_candidate_observations'] or a['review_status']=='信息不足':decision,reason='NEEDS_REVIEW','冻结旧规则回放未能明确主体或领域。'
  else:decision,reason='HIGH_MATCH','冻结旧词族与上下文规则产生普通消费用途候选。'
  pool=[r for r in oldrefs if r['usable_for_candidate_observations'] and r['product_type']==a['product_type']]
  wt=set(re.findall(r'[a-z]+',norm(row['title_original'])))
  pool.sort(key=lambda r:-len(wt&set(re.findall(r'[a-z]+',norm(r['name_es_original'])))))
  refs=[{'action_sku':r['sku'],'action_title':r['name_es_original'],'relation':'LEGACY_LABEL_CANDIDATE_NOT_VERIFIED_SEMANTIC_REFERENCE'} for r in pool[:2]]
  results.append({'record_id':row['record_id'],'input_hash':row['input_hash'],'decision':decision,'reason':reason,'action_references':refs,'legacy_type_candidate':a['product_type'],'method':'B_FROZEN_V10_RULE_REPLAY_NOT_FULL_CONTEXT_AI','frozen_rules_version':'name-semantics-v10-context-guard','human_confirmed':False})
 return results

def main():
 inputs=lines(RUN/'technical500_inputs.jsonl')+lines(RUN/'independent200_inputs.jsonl');a=[baseline_a(r) for r in inputs];b=old_b(inputs);c=lines(RUN/'technical500_results.jsonl')+lines(RUN/'independent200_results.jsonl');byc={r['record_id']:r for r in c}
 p.immutable(RUN/'scheme_A700.jsonl',a,jsonl=True);p.immutable(RUN/'scheme_B700.jsonl',b,jsonl=True)
 comparison=[]
 for row,ra,rb in zip(inputs,a,b):
  rc=byc[row['record_id']];assert ra['input_hash']==rb['input_hash']==rc['input_hash']==row['input_hash']
  comparison.append({'record_id':row['record_id'],'title_original':row['title_original'],'category_l1_original':row['category_l1_original'],'A':ra,'B':rb,'C':rc,'all_agree':len({ra['decision'],rb['decision'],rc['decision']})==1})
 p.immutable(RUN/'three_scheme700_comparison.jsonl',comparison,jsonl=True)
 randomizer=random.Random(2026102203);blind=[];mapping=[];reviews=lines(RUN/'human_review200_membership.jsonl');byid={r['record_id']:r for r in comparison}
 for i,member in enumerate(reviews,1):
  r=byid[member['record_id']];sides=['A','B','C'];randomizer.shuffle(sides);alias='V2R-'+str(i).zfill(3)
  x={'case_id':alias,'record_id':r['record_id'],'cohort':member['cohort'],'title_original':r['title_original'],'category_l1_original':r['category_l1_original'],'expected_C_hash':p.digest(r['C']),'human_target':'','human_reason':'','human_reviewer':'','human_reference_relevance':''}
  for j,arm in enumerate(sides,1):x['side'+str(j)+'_decision']=r[arm]['decision'];x['side'+str(j)+'_reason']=r[arm]['reason']
  blind.append(x);mapping.append({'case_id':alias,'record_id':r['record_id'],'side1':sides[0],'side2':sides[1],'side3':sides[2]})
 p.immutable(RUN/'blind_review200.jsonl',blind,jsonl=True);p.immutable(RUN/'private/arm_mapping.json',mapping)
 summary={'records':700,'technical_records':500,'independent_review_records':200,'schemes':{'A':'General deterministic program baseline, no Action input; NOT an ordinary AI arm','B':'Frozen V10 deterministic replay adapter with old2000 candidates; NOT the full prior AI Skill behavior','C':'V2 frozen corpus retrieval and relation engine'},'counts':{k:dict(collections.Counter(r[k]['decision'] for r in comparison)) for k in ['A','B','C']},'cohort_counts':{cohort:{k:dict(collections.Counter(r[k]['decision'] for r in subset)) for k in ['A','B','C']} for cohort,subset in [('technical500',comparison[:500]),('independent200',comparison[500:])]},'all_agree':sum(r['all_agree'] for r in comparison),'disagreements':sum(not r['all_agree'] for r in comparison),'human_review':{'random':120,'difficult':80,'human_labels':0},'formal_accuracy':None,'winner':None,'claim_allowed':'Technical scheme differences only. This does not establish V2 improvement over ordinary AI or full-context V10.'}
 p.immutable(RUN/'three_scheme_summary.json',summary)
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
