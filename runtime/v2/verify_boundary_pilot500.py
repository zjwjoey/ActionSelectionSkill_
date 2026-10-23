"""Reconcile the new pilot's source, AI notes, DB rows and saved workbook."""
import collections,json,sqlite3,zipfile
from xml.etree import ElementTree as E
from assortment import ROOT,Matcher,lines,read
import boundary_learning as b
import boundary_store as store
import run_boundary_pilot500 as run
import run_boundary_validation_v03 as v03
def main():
 run.check();inputs={r['review_id']:r for r in lines(run.OUT/'inputs500.jsonl')};refs={r['sku']:r for r in Matcher().model['references']}
 audits={a['review_id']:a for a in lines(run.OUT/'audits500.jsonl')}
 for g in 'abc':
  for n in lines(run.OUT/('notes_'+g+'.jsonl')):assert v03.make_audit(inputs[n['review_id']],n,refs)==audits[n['review_id']]
 assert len(audits)==len(inputs)==500
 rows=lines(run.OUT/'results500.jsonl');p=read(run.OUT/'persistence.json')
 with sqlite3.connect('file:'+str(store.DB)+'?mode=ro',uri=True) as c:
  stored={x[0]:json.loads(x[1]) for x in c.execute('SELECT record_id,payload FROM boundary_learning_results WHERE run_id=?',(p['run_id'],))}
  assert stored=={r['record_id']:r for r in rows}
 book=ROOT/'outputs/boundary_v03_pilot500_20261023/Action_新500条随机样本筛选.xlsx'
 ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
 with zipfile.ZipFile(book) as z:
  assert z.testzip() is None
  shared=[]
  if 'xl/sharedStrings.xml' in z.namelist():shared=[''.join(x.itertext()) for x in E.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',ns)]
  def cells(path):
   out={}
   for x in E.fromstring(z.read(path)).findall('.//s:c',ns):
    vv=x.find('s:v',ns);vv=vv.text if vv is not None else ''
    if x.get('t')=='s':vv=shared[int(vv)]
    elif x.get('t')=='inlineStr':vv=''.join(x.find('s:is',ns).itertext())
    out[x.get('r')]=vv
   return out
  summary=cells('xl/worksheets/sheet1.xml');detail=cells('xl/worksheets/sheet2.xml')
  expected={r['编号']:r for r in read(run.OUT/'review_table500.json')};counts=collections.Counter()
  for i in range(5,505):
   rid=f'P{i-4:03d}';assert detail['A'+str(i)]==rid
   assert detail['B'+str(i)]==inputs[rid]['title_original']
   assert detail['E'+str(i)]==expected[rid]['筛选候选'];counts[detail['E'+str(i)]]+=1
   assert all(detail.get(col+str(i),'')=='' for col in 'OPQR')
  assert [int(float(summary['B'+str(i)])) for i in range(6,10)]==[counts[s] for s in ['保留','观察','用不到']]+[500]
  assert int(float(summary['B17']))==int(float(summary['B18']))==0
 protected=read(run.method.OUT/'protection.json');assert all(b.b24.p.filehash(path)==h for path,h in protected.items())
 report={'source_bound_notes':500,'shared_db_rows_match':500,'workbook_rows_match':500,'counts':dict(counts),'frozen_unchanged':True,'master_unchanged':True,'protected_hashes_verified':len(protected),'human_inputs_blank':True,'accuracy':None,'full_rescreen':False,'output':str(book),'output_sha256':b.b24.p.filehash(book)}
 run.save('final_verification.json',report);print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
