"""Group real two-pass differences before proposing reusable experiments.

Group counts are not confirmed errors or accuracy. No decisions are changed.
"""
import argparse,json,sys
from pathlib import Path
from collections import Counter,defaultdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from runtime.v3.workflow import load_rows,safe_workspace_path

def analyze(rows):
    forms=Counter();reference=Counter();boundary=Counter();examples=defaultdict(list);outside=[];unknown=[]
    for r in rows:
        a,b=r.get('initial_analysis'),r.get('review_analysis')
        if not a or not b:continue
        item={'record_id':r['record_id'],'source_hash':r['source_hash'],'title':r['title_original'],'first_subject':a['subject_type'],'review_subject':b['subject_type'],'first_span':a['subject_span'],'review_span':b['subject_span'],'first_features':a['features'],'review_features':b['features']}
        if a['form']!=b['form']:
            key=a['form']+' → '+b['form'];forms[key]+=1
            if len(examples['form:'+key])<5:examples['form:'+key].append(item)
        if any(a[k]!=b[k] for k in ['relation','coverage']):
            key=a['relation']+'/'+a['coverage']+' → '+b['relation']+'/'+b['coverage'];reference[key]+=1
            if len(examples['reference:'+key])<5:examples['reference:'+key].append(item)
        if a['boundary']!=b['boundary']:
            key=a['boundary']+' → '+b['boundary'];boundary[key]+=1
            if len(examples['boundary:'+key])<5:examples['boundary:'+key].append(item)
        if a['boundary']==b['boundary']=='范围外':outside.append(dict(item,first_family=a['subject_family'],review_family=b['subject_family'],first_form=a['form'],review_form=b['form'],unresolved_layers=r['disagreement_layers']))
        if a['information_status']=='insufficient' or b['information_status']=='insufficient':unknown.append(item)
    return {'authority':'PROGRAM_GROUPING_OF_AI_CANDIDATES_NOT_GOLD','rows':len(rows),'completed_both':sum(bool(r.get('review_completed')) for r in rows),
            'form_variations':dict(forms.most_common()),'reference_variations':dict(reference.most_common()),'boundary_variations':dict(boundary.most_common()),
            'examples':dict(examples),'both_outside_candidates':outside,'information_insufficient':unknown,'formal_accuracy':None,'confirmed_errors':None}

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    out=safe_workspace_path(ROOT,a.output);out.parent.mkdir(exist_ok=True,parents=True)
    report=analyze(load_rows(a.input));out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in {'examples','information_insufficient','both_outside_candidates'}},ensure_ascii=False))
if __name__=='__main__':main()
