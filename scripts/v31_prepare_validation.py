"""Select fresh technical validation only after freezing an experimental version."""
import argparse,json,random,re,unicodedata
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from runtime.v3.workflow import load_rows,write_jsonl,filehash,safe_workspace_path
from runtime.v31.workflow import contract
from runtime.v31.state import State
from runtime.v31.rules import active_release
from runtime.v3.catalog import Catalog

def key(s):return ' '.join(unicodedata.normalize('NFKC',s).casefold().split())
def main():
    p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--source-records',required=True);p.add_argument('--snapshot',required=True);p.add_argument('--development',required=True);p.add_argument('--exposure',required=True);p.add_argument('--output',required=True);p.add_argument('--release')
    a=p.parse_args();out=safe_workspace_path(ROOT,a.output);out.mkdir(exist_ok=True,parents=True)
    if (out/'inputs200.jsonl').exists():raise ValueError('VALIDATION_SAMPLE_ALREADY_FROZEN')
    state=State(safe_workspace_path(ROOT,a.db))
    try:
        if a.release:active_release(ROOT,state,a.release,Catalog(ROOT))
        dev=load_rows(a.development);excluded={key(r['title_original']) for r in dev}
        for r in state.all('run'):
            if r[1]['purpose']!='independent':excluded.update(key(s['title_original']) for s in r[1]['sources'])
        for e in load_rows(a.exposure):
            for r in load_rows(e['path']):
                if isinstance(r,dict) and r.get('title_original'):excluded.add(key(r['title_original']))
        # Prior V3 calibration is not in every old exposure manifest.
        for r in load_rows(ROOT/'reports/v31_ai_review60_20261023/amended300_projection.jsonl'):excluded.add(key(r['title_original']))
        digest=filehash(a.snapshot);rows=load_rows(a.source_records)
        if len(rows)!=25152 or any(r['source_file_sha256']!=digest for r in rows):raise ValueError('SNAPSHOT_BINDING_FAILED')
        pool=[r for r in rows if key(r['title_original']) not in excluded];random.Random(2026102331200).shuffle(pool)
        chosen=[];used=set()
        def take(cohort,n,predicate=lambda r:True,allow_shortfall=False):
            wanted=n
            if n==0:return 0
            for r in pool:
                k=key(r['title_original'])
                if k in used or not predicate(r):continue
                used.add(k);chosen.append({k:r[k] for k in ['record_id','title_original','category_l1_original','snapshot_id','source_file_sha256','source_row','url_original']}|{'cohort':cohort,'review_id':'H31-'+str(len(chosen)+1).zfill(3)})
                n-=1
                if not n:return wanted
            if allow_shortfall:return wanted-n
            raise ValueError('INSUFFICIENT_UNSEEN_VALIDATION_POOL')
        take('random',100)
        # Pre-register targeted technical strata AFTER rule freeze, without
        # using output labels. Suspected whole systems and compatibility parts
        # are both included; lexical sampling signals are never decisions.
        signals={}
        signals['robot_maintenance_suspected_whole']=take('boundary',15,lambda r:bool(re.search(r'robot.*(aspirador|limpiacristal|limpieza)',r['title_original'],re.I)) and bool(re.search(r'auto.?vaci|autolav|autowash|estaci[oó]n|base',r['title_original'],re.I)) and not bool(re.search(r'compatible|repuesto|recambio|cepillo|filtro|bolsas|pa[nñ]os',r['title_original'],re.I)),True)
        signals['robot_vacuum_parts']=take('boundary',10,lambda r:bool(re.search(r'robot|aspirad',r['title_original'],re.I)) and bool(re.search(r'compatible|repuesto|recambio|cepillo|filtro|bolsas|pa[nñ]os',r['title_original'],re.I)),True)
        signals['ordinary_cleaning_counterexamples']=take('boundary',10,lambda r:bool(re.search(r'aspirador|aspiradora|fregona|limpiador de vapor',r['title_original'],re.I)),True)
        signals['other_machine_furniture_signals']=take('boundary',15,lambda r:bool(re.search(r'lavadora|frigor[ií]fico|industrial|torno|escritorio|sof[aá]|soldadura|prensa',r['title_original'],re.I)),True)
        signals['other_boundary_signal_topup']=take('boundary',50-sum(signals.values()),lambda r:bool(re.search(r'robot|aspirad|lavadora|frigor[ií]fico|industrial|torno|escritorio|sof[aá]|soldadura|prensa',r['title_original'],re.I)))
        take('difficult',50,lambda r:len(r['title_original'])<90 or bool(re.search(r'compatible|repuesto|recambio|kit|v[aá]lvula|rejilla',r['title_original'],re.I)))
        frozen=contract(ROOT);write_jsonl(out/'inputs200.jsonl',chosen)
        report={'records':200,'cohorts':{'random':100,'boundary':50,'difficult':50},'boundary_signal_plan_not_labels':{'robot_maintenance_suspected_whole':15,'robot_vacuum_parts':10,'ordinary_cleaning_counterexamples':10,'other_machine_furniture_signals':15},'boundary_signals_actual_not_labels':signals,'known_exposure_overlap':len(used&excluded),'excluded_title_count':len(excluded),'pool':len(pool),'seed':2026102331200,'snapshot_sha256':digest,'release':a.release,'frozen_contract_before_sampling':frozen,'human_gold':0,'previously_mechanically_screened':True,'sealed_data_used':False}
        state.put('validation_sample',report);(out/'sampling_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
    finally:state.close()
if __name__=='__main__':main()
