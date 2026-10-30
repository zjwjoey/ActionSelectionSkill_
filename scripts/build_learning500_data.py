"""Assemble staged results without treating local exploration as AI analysis."""
import json,argparse,sys,collections
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from runtime.v3.core import digest
from runtime.v3.workflow import write_jsonl,filehash
def read(p):return [json.loads(x) for x in Path(p).read_text(encoding='utf8').splitlines() if x]
def review_queue(results,groups,limit=80):
 """Prioritize source-bound questions, not routine high scores; one slot per SKU."""
 by_record=collections.defaultdict(list)
 for group in groups:
  for evidence in group['evidence']:by_record[evidence['record_id']].append(group)
 ranked=[]
 for r in results:
  if not r.get('analysis'):continue
  related={g['id']:g for g in by_record[r['record_id']]};questions=[];value=0
  for g in related.values():
   questions.append((g['kind'],g['issue'],g['reason'],g['risk'],g['id']))
   value+=min(5,len({e['record_id'] for e in g['evidence']}))
  primary=r.get('primary') or {};check=r.get('attribute_checks',{}).get(primary.get('reference_id'),{})
  if (r.get('match_score_10') or 0)>=7 and check.get('conflicts'):
   questions.append(('MATCH_REVIEW','HIGH_SCORE_EXPLICIT_CONFLICT','高分与字面属性冲突并存，核对主体及规格','不能把同类型得分当同规格事实',''));value+=8
  tr=r.get('retrieval_trace',{})
  if tr.get('semantic50') and set(tr.get('original_v31',[])[:5]).isdisjoint(tr['semantic50'][:5]):
   questions.append(('RECALL_REVIEW','TEXT_SEMANTIC_DISAGREEMENT','文本与语义Top5不重叠，核对有无遗漏正确参照','分歧不等于某一路错误，需全库事实复核',''));value+=4
  if not primary:
   questions.append(('MATCH_REVIEW','NO_CONFIRMED_REFERENCE','未确认主要参照，核对真无同类或召回遗漏','不能因缺少候选宣称全库无匹配',''));value+=3
  if not questions:continue
  src=r['source'];ranked.append((value,src['source_platform'],r['record_id'],[src['source_platform'],src['source_product_id'],src['title_original'],' / '.join(sorted({q[0] for q in questions})),' / '.join(dict.fromkeys(q[1] for q in questions)),'；'.join(dict.fromkeys(q[2] for q in questions)),'；'.join(dict.fromkeys(q[3] for q in questions)),src['source_sha256'],' / '.join(q[4] for q in questions if q[4]),None,None,None,None]))
 # Round-robin across represented sources, preserving priority within each source.
 buckets=collections.defaultdict(list)
 for item in sorted(ranked,key=lambda x:(-x[0],x[2])):buckets[item[1]].append(item[-1])
 selected=[]
 while len(selected)<limit and any(buckets.values()):
  for platform in sorted(buckets):
   if buckets[platform] and len(selected)<limit:selected.append(buckets[platform].pop(0))
 return selected
def main():
 p=argparse.ArgumentParser();p.add_argument('--pool',required=True);p.add_argument('--development',required=True);p.add_argument('--exploration',required=True);p.add_argument('--validation',required=True);p.add_argument('--groups',required=True);p.add_argument('--output',required=True);a=p.parse_args();pool=Path(a.pool);out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
 frozen=json.loads((pool/'freeze.json').read_text(encoding='utf8'));assert filehash(pool/'all.jsonl')==frozen['all_hash']
 records=read(pool/'all.jsonl');runs={'A':read(Path(a.development)/'results.jsonl'),'B':read(a.exploration),'C':read(Path(a.validation)/'results.jsonl')};lookup={(r['source']['source_platform'],r['source']['source_product_id']):r for rows in runs.values() for r in rows};assert len(lookup)==len(records)==500
 groups=json.loads(Path(a.groups).read_text(encoding='utf8'));merged=[];main=[];details=[]
 for src in records:
  r=lookup[(src['source_platform'],src['source_product_id'])];r={**r,'experiment_split':src['split'],'original_run_result_hash':digest(r),'delivery_projection':True}
  r.setdefault('method','LOCAL_EXPLORATION_NO_MODEL');r.setdefault('analysis',None);r.setdefault('primary',None);r.setdefault('match_score_10',None)
  if src['split']=='B':assert r['analysis'] is None and r['match_score_10'] is None and not r['matches']
  merged.append(r);q=r['primary'] or {};parent=src['parent_source'];identifier=src['parent_evidence'].get('研究记录编号（内部）','');status='来源行身份，无官方SKU' if src['source_product_id'].startswith('source-row:') else '原始平台号'
  main.append([src['source_platform'],src['source_product_id'],identifier,status,src['split'],src['family_key'],src['title_original'],(r['analysis'] or {}).get('sold_subject'),src['price_value'],src['price_currency'],q.get('reference_id'),q.get('title'),r['match_score_10'],q.get('relation'),r.get('evidence_status'),r['status'],r['record_id'],digest(r),r['method'],r['source']['source_sha256'],parent['file'],parent['sha256'],parent['row'],None,None,None,None,None])
  if r['analysis']:
   for m in r['matches']:details.append([src['source_platform'],src['source_product_id'],src['split'],m['reference_id'],m['title'],m['relation'],m['scope'],m['scoring']['match_score_10'],m['reason'],m['spec_status'],json.dumps(r.get('attribute_checks',{}).get(m['reference_id'],{}),ensure_ascii=False),m['score_rank'],m['scoring']['model_rank']])
 write_jsonl(out/'results.jsonl',merged)
 review=review_queue(runs['A'],groups)
 learning=[];approval=[]
 for g in groups:
  learning.append(['KNOWLEDGE_CANDIDATE',g['id'],g['kind'],g['scope'],g['issue'],json.dumps(g['terms'],ensure_ascii=False),'CANDIDATE',len({e['record_id'] for e in g['evidence']}),g['reason'],g['risk'],json.dumps(g['evidence'],ensure_ascii=False)])
  approval.append([g['id'],g['kind'],g['scope'],g['issue'],None,None,None,None,None,None])
 for r in merged:learning.append(['OBSERVATION',r['record_id'],r['experiment_split'],r['source']['source_product_id'],r['source']['title_original'],None,'OBSERVED',1,r['status'],None,r['source']['source_sha256']])
 stats=dict(input_products=500,source_counts=dict(collections.Counter(r['source']['source_platform'] for r in merged)),split_counts=dict(collections.Counter(r['experiment_split'] for r in merged)),source_counts_by_split={s:dict(collections.Counter(r['source']['source_platform'] for r in merged if r['experiment_split']==s)) for s in runs},completed_ai=sum(r['status']=='COMPLETE' and r['analysis'] is not None for r in merged),local_only=200,knowledge_candidates=len(groups),source_supporting_records=len({e['record_id'] for g in groups for e in g['evidence']}),review_inputs=len(review),human_confirmed=0,approved=0,applied_knowledge=0,confirmed_errors=None,generalization_improvements=None,new_errors=None,RETRIEVAL_QUALITY_VERIFIED=False,MATCHING_QUALITY_VERIFIED=False,LEARNING_LOOP_VERIFIED=False,LEARNING_GENERALIZATION_VERIFIED=False,SCORE_CALIBRATED=False)
 payload=dict(mainHeaders=['来源平台','原始商品ID','原始内部研究编号','身份类型','分组','商品族代理键','原始商品名称','实际销售主体','来源售价','币种','参考SKU','参考商品名称','商品匹配分（10分制）','匹配关系','证据状态','实际处理状态','记录ID','结果hash','方法版本','来源hash','原始文件','原始文件hash','原始行号','人工反馈类型','新参考SKU','人工意见','人工关系','建议分数'],main=main,detailHeaders=['平台','输入商品ID','分组','参考SKU','参考原文名称','关系','覆盖范围','匹配分（10分制）','理由','规格比较','逐属性证据','评分排名','原模型排名'],details=details,reviewHeaders=['平台','商品ID','原文名称','知识类型','问题','为何值得审核','扩展风险','来源hash','候选ID','人工结论','人工依据','人工审核人','人工时间'],review=review,learningHeaders=['记录层次','记录ID','类型/分组','范围/商品号','问题/原文','术语假设','状态','证据商品数','理由/实际状态','风险','来源证据'],learning=learning,approvalHeaders=['候选ID','类型','范围','问题','人工确认','人工依据','人工审核人','人工时间','学习批准','批准版本'],approval=approval,summary=[[k,json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v] for k,v in stats.items()]+[['评分','沿用V3.1暂定指数；B组没有AI分析，不能用召回分代替匹配分'],['证据边界','候选来自A；C未用于提炼知识。无人工Gold，不计算准确率，不自动批准'],['身份边界','缺GTIN/型号的跨平台同款和近变体不能保证完全隔离；原始研究编号不冒称官方SKU']])
 (out/'workbook_data.json').write_text(json.dumps(payload,ensure_ascii=False),encoding='utf8');(out/'summary.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(stats,ensure_ascii=False))
if __name__=='__main__':main()
