import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const dir=process.argv[2],summary=JSON.parse(await fs.readFile(`${dir}/summary.json`,'utf8'));
const rows=(await fs.readFile(`${dir}/results.jsonl`,'utf8')).trim().split('\n').filter(Boolean).map(JSON.parse);
const bindings=JSON.parse(await fs.readFile(`${dir}/feedback_bindings.json`,'utf8'));
const hash=x=>bindings[x.record_id]; // Python canonical hash avoids 1.0 versus 1 serialization drift.
const summaryRows=Object.entries(summary).map(([k,v])=>{
 if(k==='retrieval'&&v?.index_version){const {ids,model_files,...meta}=v.index_version;v={...v,index_version:{...meta,reference_count:ids?.length,model_manifest:'Full ID/model-file manifest remains in the source index.json; not repeated in one Excel cell.'}};}
 return [k,typeof v==='object'?JSON.stringify(v):v];
});
const wb=Workbook.create(),col=n=>{let s='';for(;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const safe=x=>typeof x==='string'&&/^[=+@-]/.test(x)?`'${x}`:x??null;
function table(name,title,headers,data,widths){
 const sh=wb.worksheets.add(name);sh.showGridLines=false;
 sh.getRangeByIndexes(0,0,Math.max(7,data.length+5),headers.length).format={font:{name:'Arial',size:11,color:'#243746'},wrapText:true,verticalAlignment:'top'};
 sh.getRange('A2').values=[[title]];sh.getRange('A2').format={font:{size:15,bold:true},rowHeight:30,wrapText:false};
 for(let j=0;j<headers.length;j++){
  sh.getRangeByIndexes(0,j,Math.max(7,data.length+5),1).format.columnWidth=widths[j]||24;
  const text=(!data.length||data.every(r=>r[j]==null||typeof r[j]==='string'));
  if(text)sh.getRangeByIndexes(5,j,Math.max(1,data.length),1).setNumberFormat('@');
 }
 sh.getRangeByIndexes(4,0,1,headers.length).values=[headers];sh.getRangeByIndexes(4,0,1,headers.length).format={fill:'#294D63',font:{bold:true,color:'#FFFFFF'},rowHeight:42};
 if(data.length){sh.getRangeByIndexes(5,0,data.length,headers.length).values=data.map(r=>r.map(safe));sh.tables.add(`A5:${col(headers.length)}${data.length+5}`,true,`Table${wb.worksheets.items.length}`);}
 for(let i=0;i<data.length;i++){
  const h=Math.max(...data[i].map((v,j)=>String(v??'').split('\n').reduce((n,x)=>n+Math.max(1,Math.ceil(x.replace(/[^\x00-\x7f]/g,'xx').length/(widths[j]||24))),0)));
  sh.getRangeByIndexes(i+5,0,1,headers.length).format.rowHeight=Math.min(409,Math.max(48,h*14+8));
 }
 sh.freezePanes.freezeRows(5);sh.freezePanes.freezeColumns(2);return sh;
}
const rel={IDENTICAL:'同款待独立核验',SAME_TYPE:'同类型候选',FUNCTIONAL_ALTERNATIVE:'功能相近候选',SHARED_NEED:'只有需求关联',UNRELATED:'不相关',INSUFFICIENT:'信息不足'};
const main=rows.map(r=>{const p=r.primary,q=p?.reference_quote,price=p?.price;return[r.source.source_platform,r.source.source_product_id,r.source.title_original,r.analysis?.sold_subject||'主体待确认',r.source.price_value,r.source.price_currency||'未知',p?.title||'未确认匹配',p?.reference_id||'',r.match_score_10,rel[p?.relation]||'未确认匹配',p?.reason||'无可靠整件参考或主体未确认',p?.spec_status||'UNKNOWN',q?.price_value??null,price?.L3.eligible?'L3单位换算':price?.L2.eligible?'L2历史价格带':price?.L1_source.valid?'仅L1报价有效':'价格证据不足',[...(r.issues||[]),...(r.analysis?.unknowns||[])].join('；'),r.source.source_url,r.status,r.record_id,hash(r),r.method,r.source.source_sha256,null,null,null,null,null,r.evidence_status||"V3.1未独立核验"];});
const h=['来源平台','原始商品ID','原始商品名称','实际销售主体','商品价格','币种','最相近参考商品','参考SKU','商品匹配分（10分制）','匹配关系','主要匹配依据','规格比较','参考历史价','价格比较情况','待确认问题','商品原始链接','完成状态','记录ID','结果hash','方法版本','来源hash','人工反馈类型','新参考SKU','人工意见','人工关系','建议分数','证据状态'];
const sh=table('商品匹配结果','商品匹配分｜暂定研究指数，不是采购推荐或同款概率',h,main,[15,23,72,40,17,14,52,18,25,25,75,22,18,27,70,60,20,65,70,70,70,28,22,65,26,20,32]);
sh.getRangeByIndexes(5,8,Math.max(1,main.length),1).setNumberFormat('0.0');sh.getRangeByIndexes(5,8,Math.max(1,main.length),1).format={font:{bold:true,color:'#173B54'},fill:'#E2F0D9'};
sh.getRangeByIndexes(5,21,Math.max(1,main.length),5).format.fill='#FFF2CC';sh.getRangeByIndexes(5,25,Math.max(1,main.length),1).setNumberFormat('0.0');
sh.getRangeByIndexes(5,21,Math.max(1,main.length),1).dataValidation={rule:{type:'list',values:['接受匹配结果','修改最佳参考SKU','商品类型判断错误','商品主体判断错误','商品关系判断错误','规格判断错误','匹配分不合理','无匹配但存在正确参考','价格证据错误']}};
const details=[];
for(const r of rows)for(const m of r.matches)details.push([r.source.source_product_id,m.reference_id,m.title,rel[m.relation],m.scoring.match_score_10,m.reason,m.spec_status,[...m.scoring.limitations,...m.unknowns].join('；'),m.score_rank,m.scoring.model_rank,m.scoring.original_index_100,m.scoring.evidence_coverage,m.scope,m.price.L1_source.valid?'有效':'不足',m.price.L1_reference.valid?'有效':'不足',m.reference_quote?.price_currency||'未知',m.reference_quote?.price_date||'',m.price.L2.asking_price_ratio,m.price.L3.unit_price_ratio,[...m.price.L2.reasons,...m.price.L3.reasons].join('; '),m.scoring.score_version,r.source.price_currency||'未知',r.source.price_date||'',r.source.price_value,m.reference_quote?.price_value??null]);
const detail=table('Top5匹配明细','原模型排名与评分排名同时保存；局部低分不等于商品没有经营价值', ['输入商品ID','参考SKU','参考商品名称','参考关系','匹配分（10分制）','评分依据','规格比较','证据缺失与限制','评分排名','原模型排名','原始100分指数','已知证据权重','覆盖范围','本品L1','参考L1','参考币种','参考日期','L2历史标价比','L3单位价比','价格不可比原因','评分版本','本品币种','本品日期','本品价格','参考价格'],details,[23,18,55,25,25,75,20,80,16,18,23,22,22,18,18,17,20,22,23,65,35,17,20,18,18]);
detail.getRangeByIndexes(5,4,Math.max(1,details.length),1).setNumberFormat('0.0');
const check=rows.filter(r=>r.status!=='COMPLETE'||r.issues.length);
table('需要核查','只列匹配可信度问题；价格缺失本身不自动加入', ['平台','商品ID','原品名','影响匹配的疑问','记录ID'],check.map(r=>[r.source.source_platform,r.source.source_product_id,r.source.title_original,r.issues.join('；'),r.record_id]),[17,23,75,110,65]);
table('运行与来源说明','历史离线换算、来源绑定文件导入与真实模型运行分别标记',['项目','记录'],[...summaryRows,['评分规则','旧V2平衡权重指数除10、保留一位小数；关系既作为维度又作为上限，上限不是二次加分。未知规格仍按旧基线归一，必须阅读证据覆盖率，不是校准概率。RRF仅用于召回排序，不是商品匹配分。'],['主分规则','按原始指数降序、证据覆盖率降序、原模型排名、SKU稳定排序。主体清楚且完整覆盖、关系可靠时取最高候选；无可靠匹配主分为空。'],['价格','价格不进入商品身份分数；两侧币种/快照、L1/L2/L3及不可比原因见明细与本地JSON。'],['反馈','黄色栏由实际审核人填写。使用--import-feedback及真实--reviewer安全回导；绑定hash，原AI结果不覆盖。'],['质量','PROVISIONAL_MATCH_SCORE / SCORE_UNCALIBRATED；没有独立事实Gold，不授予MATCHING_QUALITY_VERIFIED。']],[32,120]);
if(summary.learning){
 const learning=(await fs.readFile(`${dir}/learning_candidates.jsonl`,'utf8')).trim().split('\n').filter(Boolean).map(JSON.parse);
 table('未知SKU与学习候选','AI假设不等于事实；人工反馈填写主表黄色栏，批准与发布需独立验收',['平台','原始商品ID','原始品名','未知原因','当前理解','审核问题','学习状态','候选ID','同类线索组','来源hash','原文证据链接','方法版本','反馈入口'],learning.map(x=>[x.body.original.source_platform,x.body.original.source_product_id,x.body.original.title_original,x.body.unknown.join('；'),x.body.hypothesis.sold_subject,x.body.priority.join('；'),x.state,x.candidate_id,x.group_key,x.source.source_sha,x.body.original.source_url,x.body.method,'主表黄色反馈栏；manage_learning.py 接收来源绑定审核']),[17,23,72,48,45,65,22,70,70,70,60,70,65]);
}
wb.recalculate();console.log((await wb.inspect({kind:'table',range:'商品匹配结果!A5:J7',include:'values',tableMaxRows:3,tableMaxCols:10})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NUM!|#NAME\\?',options:{useRegex:true,maxResults:5}})).ndjson);
const output=`${dir}/outputs/match10`;await fs.mkdir(output,{recursive:true});
for(const [sheetName,range,name]of [['商品匹配结果','A5:J8','main'],['Top5匹配明细','A5:F8','details'],['需要核查','A5:D7','checks'],['运行与来源说明','A5:B9','run']]){
 const img=await wb.render({sheetName,range,scale:1,format:'png'});await fs.writeFile(`${dir}/${name}_preview.png`,new Uint8Array(await img.arrayBuffer()));
}
if(summary.learning){const img=await wb.render({sheetName:'未知SKU与学习候选',range:'A5:G8',scale:1,format:'png'});await fs.writeFile(`${dir}/learning_preview.png`,new Uint8Array(await img.arrayBuffer()));}
await(await SpreadsheetFile.exportXlsx(wb)).save(`${output}/商品匹配评分.xlsx`);
