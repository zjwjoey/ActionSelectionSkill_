"""Produce source-bound CSVs and matrices for the Artifact Tool workbooks."""
import collections,csv,json
from assortment import ROOT,RUN,p,read,lines
OUT=RUN/'delivery';OUT.mkdir(exist_ok=True)
records=lines(RUN/('effective_full20018_v23.jsonl' if (RUN/'effective_full20018_v23.jsonl').exists() else 'full20018_results.jsonl'));source=read(RUN/'amazon_source_manifest.json');assert len(records)==20018
labels={'HIGH_MATCH':'高度符合','POTENTIAL_MATCH':'保留研究','NEEDS_REVIEW':'待核实','LOW_MATCH':'明显不符'}
tasks={key:label for key,label,_ in read(RUN/'frozen_policy.json')['task_frames']};tasks['vehicle_cleaning']='limpiar vehiculos'

def flatten(r):
 refs=r['action_references'];ref=refs[0] if refs else {}
 return {'记录ID':r['record_id'],'Amazon原始品名':r['title_original'],'一级类目原值':r['category_l1_original'],'实验判断':r['decision'],'主体词候选':r['product_type_surface'],'商品形态线索':r['retail_form'],'标准化用途片段':' / '.join(dict.fromkeys(t['normalized_span'] for t in r['task_evidence'])),'用途与需求候选（推断）':' / '.join(tasks.get(t,t) for t in r['title_purpose_candidates']),'Action参照SKU':ref.get('action_sku',''),'Action原始西语品名':ref.get('action_title',''),'参照关系':r['relation_type'],'判断理由':r['reason'],'不确定性':' / '.join(r['uncertainties']),'原始来源组ID':r['source_record_id'],'原始链接':r['url_original'],'CSV记录行号':r['source_row'],'规则与模型版本':r['rules_model_version'],'输入Hash':r['input_hash'],'来源文件':source['source_file'],'检索相似度（非准确率）':ref.get('retrieval_score')}
flat=[flatten(r) for r in records];headers=list(flat[0])
def csvout(path,rows,fields):
 with path.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for row in rows:
   # Source titles remain exact in JSONL/DB. Prevent CSV formula interpretation.
   w.writerow({k:("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v) for k,v in ((k,row.get(k,'')) for k in fields)})
csvout(OUT/'Amazon20018_全量实验筛选.csv',flat,headers)
for decision,label in labels.items():csvout(OUT/(label+'_实验候选.csv'),[r for r in flat if r['实验判断']==decision],headers)
blind=lines(RUN/('blind_review200_v23.jsonl' if (RUN/'blind_review200_v23.jsonl').exists() else 'blind_review200.jsonl'))
# Remove method-identifying wording only in the anonymous presentation. Original
# method output/reasons and side mapping remain unchanged in the audit files.
for b in blind:
 for side in [1,2,3]:
  key='side'+str(side)+'_reason';reason=b[key]
  reason=reason.replace('冻结旧词族与上下文规则产生普通消费用途候选。','商品主体与常规消费用途支持研究候选。').replace('冻结旧规则回放未能明确主体或领域。','当前证据未能明确主体或领域。').replace('真实Action参照','具体商品参照').replace('Action参照','具体商品参照')
  b[key]=reason
csvout(OUT/'独立200条_匿名人工审核.csv',blind,list(blind[0]))
comparisons=lines(RUN/('three_scheme700_comparison_v23.jsonl' if (RUN/'three_scheme700_comparison_v23.jsonl').exists() else 'three_scheme700_comparison.jsonl'));cmap={r['record_id']:r for r in comparisons}
delta=[{'record_id':r['record_id'],'title_original':r['title_original'],'category_l1_original':r['category_l1_original'],**{k+'_decision':r[k]['decision'] for k in ['A','B','C']},**{k+'_reason':r[k]['reason'] for k in ['A','B','C']}} for r in comparisons if not r['all_agree']]
csvout(OUT/'三方案技术对比_分歧清单.csv',delta,list(delta[0]))
# All200 are fixed post-freeze memberships, never selected by V2 outcome.
human_fields=['case_id','title_original','category_l1_original','cohort','side1_decision','side1_reason','side2_decision','side2_reason','side3_decision','side3_reason','human_target','human_reason','human_reviewer','record_id','expected_C_hash']
refrows=[]
for b in blind:
 c=cmap[b['record_id']]['C'];refs=c['action_references'] or [{}]
 for ref in refs:refrows.append([b['case_id'],c['title_original'],ref.get('action_sku',''),ref.get('action_title',''),ref.get('relation','NO_CLEAR_RELATION'),' / '.join(ref.get('shared_tasks',[])),'','','',b['record_id'],b['expected_C_hash']])
payload={'source':source,'counts':dict(collections.Counter(r['decision'] for r in records)),'full_headers':headers,'full_rows':[[r[h] for h in headers] for r in flat],'human_headers':['审核编号','Amazon原始品名','一级类目原值','样本口径','判断1','理由1','判断2','理由2','判断3','理由3','人工判断','人工原因','真实审核人','记录ID','绑定Hash'],'human_rows':[[b.get(h,'') for h in human_fields] for b in blind],'reference_headers':['审核编号','Amazon原始品名','Action参照SKU','Action原始西语品名','参照关系','共享用途候选','人工参照相关性','人工原因','真实审核人','记录ID','绑定Hash'],'reference_rows':refrows,'action_corpus':read(RUN/'action_corpus_summary.json'),'three_schemes':read(RUN/'three_scheme_summary.json')}
p.immutable(RUN/'workbook_payload.json',payload)
p.immutable(OUT/'csv_export_manifest.json',{'files':{f.name:{'sha256':p.filehash(f),'bytes':f.stat().st_size} for f in OUT.glob('*.csv')},'all_rows':20018,'status_counts':payload['counts'],'human_labels':0,'excel_files_pending':2})
print(json.dumps({'exported_rows':len(flat),'counts':payload['counts'],'human_review_rows':len(blind),'reference_review_rows':len(refrows),'csv_files':len(list(OUT.glob('*.csv')))},ensure_ascii=False))
