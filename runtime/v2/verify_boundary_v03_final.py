"""Final source/note/database/workbook reconciliation for this pilot."""
import collections,json,sqlite3,zipfile
from pathlib import Path
from xml.etree import ElementTree as E
from assortment import ROOT,Matcher,lines,read
import boundary_learning as b
import boundary_validation_v03 as v
import run_boundary_validation_v03 as run

def main():
    frozen=run.check();inputs={r['review_id']:r for r in lines(v.OUT/'inputs_validation300.jsonl')}
    refs={r['sku']:r for r in Matcher().model['references']}
    audits={r['review_id']:r for r in lines(v.OUT/'validation300_bound.jsonl')}
    for group in 'abc':
        for n in lines(v.OUT/('notes_'+group+'.jsonl')):
            assert run.make_audit(inputs[n['review_id']],n,refs)==audits[n['review_id']]
    assert len(inputs)==len(audits)==300
    p=read(v.OUT/'persistence.json');summary=read(v.OUT/'validation_summary.json')
    with sqlite3.connect('file:'+str(ROOT/'learning_data/action_selection.sqlite3')+'?mode=ro',uri=True) as c:
        for stage in ['development60','validation300']:
            stored={r[0]:json.loads(r[1]) for r in c.execute('SELECT record_id,payload FROM boundary_learning_results WHERE run_id=? AND stage=?',(p['run_id'],stage))}
            disk={r['record_id']:r for r in lines(v.OUT/(stage+'_results.jsonl'))}
            assert stored==disk
    book=ROOT/'outputs/boundary_v03_20261023/BoundaryV03_关键边界与300条验证.xlsx'
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(book) as z:
        assert z.testzip() is None
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            shared=[''.join(x.itertext()) for x in E.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',ns)]
        def cells(path):
            out={}
            for x in E.fromstring(z.read(path)).findall('.//s:c',ns):
                val=x.find('s:v',ns);val=val.text if val is not None else ''
                if x.get('t')=='s':val=shared[int(val)]
                elif x.get('t')=='inlineStr':val=''.join(x.find('s:is',ns).itertext())
                out[x.get('r')]=val
            return out
        overview=cells('xl/worksheets/sheet1.xml');detail=cells('xl/worksheets/sheet4.xml')
        assert [int(float(overview[x])) for x in ['B9','C9','D9','E9']]==[300,140,159,1]
        assert [int(float(overview[x])) for x in ['B25','B26','B27']]==[0,0,0]
        counts=collections.Counter()
        expected={r['review_id']:r for r in lines(v.OUT/'validation300_results.jsonl')}
        for i in range(5,305):
            identity=detail['A'+str(i)];assert identity==f'N{i-4:03d}'
            assert detail['C'+str(i)]==inputs[identity]['title_original']
            assert detail['G'+str(i)]==expected[identity]['decision']
            counts[detail['G'+str(i)]]+=1
            assert all(detail.get(col+str(i),'')=='' for col in 'PQRS')
        assert dict(counts)==summary['total']
    protected=read(v.OUT/'protection.json')
    assert all(b.b24.p.filehash(path)==h for path,h in protected.items())
    evidence={'scope_complete':True,'frozen_hashes':len(frozen['hashes']),'protected_files_unchanged':len(protected),
        'final_notes_equal_bound_audits':300,'database_result_rows_equal_files':360,
        'workbook_rows_equal_sources_and_results':300,'human_inputs_blank':True,'formula_errors':0,
        'final_counts':summary['total'],'run_id':p['run_id'],'human_gold':0,
        'semantic_accuracy':'NOT_MEASURED','auto_exclusion_acceptance':'NOT_ACCEPTED',
        'full_screening_acceptance':'NOT_ACCEPTED','priority_findings':['N038','N037','N065'],
        'full_rescreen':False,'master_unchanged':True,
        'artifacts':{str(path):b.b24.p.filehash(path) for path in [book,ROOT/'outputs/boundary_v03_20261023/BoundaryV03_修复与验证报告.md',ROOT/'skills/action-selection/SKILL.md',ROOT/'skills/action-selection/references/boundary_validation_v03.md']}}
    run.save('final_acceptance.json',evidence)
    print(json.dumps(evidence,ensure_ascii=False))

if __name__=='__main__':main()
