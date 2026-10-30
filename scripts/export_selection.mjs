import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const out=process.argv[2];
const summary=JSON.parse(await fs.readFile(`${out}/summary.json`,'utf8'));
const results=(await fs.readFile(`${out}/results.jsonl`,'utf8')).trim().split('\n').map(JSON.parse);
const wb=Workbook.create();
const safe=x=>typeof x==='string'&&/^[=+@-]/.test(x)?`'${x}`:x??null;
const col=n=>{let s='';for(;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
function tab(name,title,headers,data,widths){
 const sh=wb.worksheets.add(name);sh.showGridLines=false;
 sh.getRangeByIndexes(0,0,Math.max(7,data.length+5),headers.length).format={font:{name:'Arial',size:11,color:'#243746'},verticalAlignment:'top',wrapText:true};
 sh.getRange('A2').values=[[title]];sh.getRange('A2').format={font:{size:15,bold:true},wrapText:false,rowHeight:30};
 sh.getRangeByIndexes(4,0,1,headers.length).values=[headers];sh.getRangeByIndexes(4,0,1,headers.length).format={fill:'#244E62',font:{bold:true,color:'#FFFFFF'},rowHeight:38};
 // Preserve numeric-looking retailer IDs (e.g. IKEA 00473546) as text.
 const ids=headers.map((h,i)=>/ID|SKU/.test(h)?i:-1).filter(i=>i>=0);
 for(const i of ids)sh.getRangeByIndexes(5,i,Math.max(1,data.length),1).setNumberFormat('@');
 if(data.length)sh.getRangeByIndexes(5,0,data.length,headers.length).values=data.map(r=>r.map(safe));
 for(let i=0;i<headers.length;i++)sh.getRangeByIndexes(0,i,Math.max(7,data.length+5),1).format.columnWidth=widths[i]||24;
 for(let i=0;i<data.length;i++){
  const lines=Math.max(...data[i].map((v,j)=>String(v??'').split('\n').reduce((n,l)=>n+Math.max(1,Math.ceil(l.replace(/[^\x00-\x7f]/g,'xx').length/(widths[j]||24))),0)));
  sh.getRangeByIndexes(i+5,0,1,headers.length).format.rowHeight=Math.min(409,Math.max(50,lines*14+10));
 }
 if(data.length)sh.tables.add(`A5:${col(headers.length)}${data.length+5}`,true,`Data${wb.worksheets.items.length}`);
 sh.freezePanes.freezeRows(5);sh.freezePanes.freezeColumns(2);return sh;
}
const relations={IDENTICAL:'同款（需独立核验）',SAME_TYPE:'同类型',FUNCTIONAL_ALTERNATIVE:'功能替代',SHARED_NEED:'相同需求',UNRELATED:'不相关',INSUFFICIENT:'信息不足'};
const rows=results.map(r=>{
 const a=r.analysis,m=r.matches[0],q=m?.reference_quote,p=m?.price;
 return [r.source.source_platform,r.source.source_product_id,r.source.title_original,r.source.price_value,r.source.price_currency||'未知',a?.sold_subject||'待分析',a?.no_confirmed_match?`无可靠匹配；检索候选：${m?.title||'无'}`:m?.title||'无可靠匹配',m?.reference_id||'',q?.price_value??null,relations[m?.relation]||'待核验',m?.scores.balanced.index??null,p?.L3.eligible?'L3单位价':p?.L2.eligible?'L2历史标价':p?.L1_source.valid?'L1本品价格有效':'资料不足',r.decision,r.reason,r.review_question||a?.unknowns.join('；')||'',r.status,r.source.source_url,r.source.source_date,r.record_id];
});
tab('选品结果','跨平台商品研究｜保留为研究候选；AI判断尚未通过独立准确率验收',
 ['平台','原商品ID','原始商品名','本品标价','币种','商品类型','最相近参考商品','参考SKU','参考历史价','商品关系','暂定匹配指数','价格证据','选品建议','简短原因','待确认问题','完成状态','商品链接','来源日期','反馈记录ID'],rows,
 [15,23,72,17,13,30,50,18,18,24,21,27,17,65,65,20,60,20,65]);
const review=results.filter(r=>r.status!='COMPLETE'||r.decision==='观察'||r.matches.some(m=>!m.price.L2.eligible));
tab('需人工复核','先核对售品、匹配与价格；经营裁定与事实审核分开保存',
 ['平台','商品ID','原品名','当前建议','待确认依据','反馈记录ID','人工修改','审核人','修改原因','审核时间'],
 review.map(r=>[r.source.source_platform,r.source.source_product_id,r.source.title_original,r.decision,[r.review_question,...r.matches.slice(0,1).flatMap(m=>m.price.L2.reasons)].filter(Boolean).join('；'),r.record_id,null,null,null,null]),
 [15,23,72,18,85,65,24,22,60,24]);
const metadata=Object.entries(summary).map(([k,v])=>[k,typeof v==='object'?JSON.stringify(v):v]);
metadata.push(['来源口径','原始来源文件只读；原名、报价和证据保存在本地results.jsonl。参考报价为历史零售价格，不是实时价或完整到店成本。'],['指数口径','沿用V2三组未校准权重；表中显示balanced，不是同款概率，不按指数自动排除。'],['反馈','人工栏为填写模板；反馈须通过CLI绑定记录ID与结果hash入库，AI结果不会被覆盖。']);
tab('运行与来源说明','工程完成与判断质量分开验收',['项目','记录'],metadata,[32,115]);
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'选品结果!A5:F7',include:'values',tableMaxRows:3,tableMaxCols:6})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NUM!|#NAME\\?',options:{useRegex:true,maxResults:5}})).ndjson);
const destination=`${out}/outputs/selection_v3`;await fs.mkdir(destination,{recursive:true});
for(const [sheetName,range,name] of [['选品结果','A5:F8','results'],['需人工复核','A5:E7','review'],['运行与来源说明','A5:B10','run']]){
 const img=await wb.render({sheetName,range,scale:1,format:'png'});await fs.writeFile(`${out}/${name}_preview.png`,new Uint8Array(await img.arrayBuffer()));
}
await(await SpreadsheetFile.exportXlsx(wb)).save(`${destination}/选品研究.xlsx`);
