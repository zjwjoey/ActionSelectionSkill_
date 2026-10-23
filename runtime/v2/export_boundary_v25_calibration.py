"""Export a small owner-review set from the supplied AI focus workbook."""
from __future__ import annotations
import csv, json, sys
from pathlib import Path

import openpyxl
import boundary_v24 as v24
import boundary_v25 as v25
from assortment import Matcher, lines

ROOT=v24.ROOT
OUTPUT=ROOT/'outputs/amazon_boundary_v25_20261022'/f"V2.5首批人工校准候选_{v25.v24.p.filehash(v25.__file__)[:10]}.csv"
FOCUS_IDS=['AB24-071','AB24-012','AB24-044','AB24-039','AB24-061','AB24-023',
           'AB24-113','AB24-414','AB24-127','AB24-432','AB24-494','AB24-095']

def main():
    wb=openpyxl.load_workbook(v25.FOCUS_XLSX,read_only=True,data_only=True)
    ws=wb['重点SKU预审']
    focus={str(row[0]):row for row in ws.iter_rows(min_row=2,values_only=True) if row[0]}
    source_rows={v24.title_hash(r['title_original']):r for r in lines(v24.INPUTS)}
    v23={r['sku']:r for r in lines(v24.V23)}
    matcher=Matcher();out=[]
    for focus_id in FOCUS_IDS:
        row=focus[focus_id]; title=str(row[3]); src=source_rows[v24.title_hash(title)]
        ft=matcher.f.extract(title,True); boundary=v24.boundary_for_title(title,ft)
        v24row=dict(src);v24row.update({'sample_cohort':'focus_calibration_not_validation','_v24_feature':ft,'_v24_boundary':boundary})
        old=v24.refs_and_decision(v24row,matcher,v23)
        new=v25.analyze(src,matcher,v23)
        out.append({'编号':focus_id,'原V2.4结论':str(row[1] or ''),'旧AI意见':str(row[6] or ''),
            '旧审核问题类型':str(row[7] or ''),'旧审核证据':str(row[8] or ''),
            'V2.5建议结论（非Gold）':new['decision'],'建议原因':new['reason_code'],
            '主体状态':new['product_subject_status'],'主体类型':new['product_subject_class'],'主体证据':new['product_subject_evidence'],
            '真实Action参照':new['action_reference_exists'],'同类参照':new['action_reference_same_class'],
            '参照关系':new['action_reference_relation'],'Action参照SKU':' / '.join(x['action_sku'] for x in new['action_references']),
            '边界状态':new['boundary_status'],'边界类别':new['boundary_code'],'边界证据':new['boundary_evidence_span'],
            '商品西语品名':title,'商品来源记录ID':src['record_id'],'输入Hash':src['input_hash'],
            '人工确认结论':'','人工确认原因':'','审核人':''})
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    with OUTPUT.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
    print(json.dumps({'output':str(OUTPUT),'rows':len(out),'ids':FOCUS_IDS,'all_human_fields_blank':all(not r['人工确认结论'] and not r['审核人'] for r in out)},ensure_ascii=False))

if __name__=='__main__': main()
