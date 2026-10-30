import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
// Resolve the host-provided artifact dependency without installing repo packages.
const hostRequire=createRequire(process.env.CODEX_NODE_MODULES?path.join(process.env.CODEX_NODE_MODULES,'artifact-host.cjs'):import.meta.url);
const {Workbook,SpreadsheetFile}=await import(pathToFileURL(hostRequire.resolve('@oai/artifact-tool')).href);
const dir=process.argv[2],data=JSON.parse(await fs.readFile(`${dir}/workbook_data.json`,'utf8')),wb=Workbook.create();
const letter=n=>{let s='';for(;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const safe=x=>typeof x==='string'&&/^[=+@-]/.test(x)?`'${x}`:x??null;
const tabs=data.tabs??[
 ['商品匹配结果','500条来源绑定总表｜仅实际完成AI分析者有匹配分',data.mainHeaders,data.main],
 ['Top5匹配明细','只展示实际分析过的关系；召回排名不是人工事实',data.detailHeaders,data.details],
 ['需要人工核查','开发样本优先审核｜问题和建议不等于Gold',data.reviewHeaders,data.review],
 ['未知SKU观察与学习候选','普通观察与可复用知识假设分开；未审批不得发布',data.learningHeaders,data.learning],
 ['人工审核和知识确认','真实人员填写主表黄色反馈栏；以下候选确认栏保留为空',data.approvalHeaders,data.approval],
 ['运行统计及学习效果','工程、匹配、学习、泛化分别验收；缺少标签保持未验证',['项目','值'],data.summary]
];
for(const [name,title,headers,rows] of tabs){
 const sh=wb.worksheets.add(name);sh.showGridLines=false;
 const widths=headers.map(h=>/名称|原文|证据|问题|原因|风险|说明|文件|hash|方法|意见|依据|结论|建议|边界|URL|召回/.test(h)?65:24);
 headers.forEach((h,j)=>{if(/^(审核号|样本号|知识号|证据号)$/.test(h))widths[j]=12;});
 headers.forEach((h,j)=>{if(h==='逐属性证据'||h==='来源证据')widths[j]=95;});
 if(headers.length===2)widths[1]=110;
 sh.getRangeByIndexes(0,0,Math.max(8,rows.length+5),headers.length).format={font:{name:'Arial',size:11,color:'#243746'},wrapText:true,verticalAlignment:'top'};
 sh.getRange('A2').values=[[title]];sh.getRange('A2').format={font:{bold:true,size:16},wrapText:false,rowHeight:32};
 for(let j=0;j<headers.length;j++){
  const width=widths[j];
  sh.getRangeByIndexes(0,j,Math.max(8,rows.length+5),1).format.columnWidth=width;
  if(rows.every(r=>r[j]==null||typeof r[j]==='string'))sh.getRangeByIndexes(5,j,Math.max(1,rows.length),1).setNumberFormat('@');
 }
 if(name==='运行统计及学习效果')sh.getRange('B:B').format.columnWidth=110;
 sh.getRangeByIndexes(4,0,1,headers.length).values=[headers];sh.getRangeByIndexes(4,0,1,headers.length).format={fill:'#294D63',font:{bold:true,color:'#FFFFFF'},horizontalAlignment:'center',verticalAlignment:'center',rowHeight:45};
 if(rows.length){sh.getRangeByIndexes(5,0,rows.length,headers.length).values=rows.map(r=>r.map(safe));sh.tables.add(`A5:${letter(headers.length)}${rows.length+5}`,true,`Data${wb.worksheets.items.length}`);}
 sh.getRangeByIndexes(5,0,Math.max(1,rows.length),headers.length).format.rowHeight=36;
 rows.forEach((row,i)=>{
  const lines=Math.max(1,...row.map((v,j)=>String(v??'').split('\n').reduce((sum,line)=>sum+Math.max(1,Math.ceil([...line].reduce((n,c)=>n+(c.charCodeAt(0)>255?2:1),0)/Math.max(12,widths[j]-2))),0)));
  if(lines>1)sh.getRangeByIndexes(i+5,0,1,headers.length).format.rowHeight=Math.min(409,lines*16+12);
 });
 headers.forEach((h,j)=>{
  if(h.includes('分（10分制）')||h==='建议分数'){sh.getRangeByIndexes(5,j,Math.max(1,rows.length),1).setNumberFormat('0.0');}
  if(h.startsWith('人工')||h==='新参考SKU'||h==='建议分数')sh.getRangeByIndexes(5,j,Math.max(1,rows.length),1).format.fill='#FFF2CC';
 });
 sh.freezePanes.freezeRows(5);sh.freezePanes.freezeColumns(2);
}
wb.recalculate();console.log((await wb.inspect({kind:'table',range:`${tabs[0][0]}!A5:H8`,include:'values',tableMaxRows:4,tableMaxCols:8})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NUM!|#NAME\\?',options:{useRegex:true,maxResults:10}})).ndjson);
for(const [name] of tabs){const img=await wb.render({sheetName:name,range:'A5:F8',scale:1,format:'png'});await fs.writeFile(`${dir}/${name}_preview.png`,new Uint8Array(await img.arrayBuffer()));}
const outputName=path.basename(data.outputName??'ActionSelectionSkill_V322_500条学习与验证.xlsx');
if(!outputName.endsWith('.xlsx'))throw new Error('XLSX_OUTPUT_REQUIRED');
await fs.mkdir(`${dir}/outputs`,{recursive:true});await(await SpreadsheetFile.exportXlsx(wb)).save(`${dir}/outputs/${outputName}`);
