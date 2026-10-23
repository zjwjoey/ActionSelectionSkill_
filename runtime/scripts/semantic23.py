"""Scoped, title-only V2.3 proposals. Website evidence never enters this engine."""
import argparse, collections, copy, json, re, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import pipeline as p
import semantic22 as old
OUT=ROOT/'outputs/action_semantic_v23_20261022'
VERSION='action-semantic-deepening-v2.3'
TARGET_STATES={'RULE_COVERAGE_GAP','FEATURE_TOO_BROAD'}

def read_rules(paths):
    rules=[]
    for path in paths:
        for line in Path(path).read_text(encoding='utf8').splitlines():
            if not line or line.startswith('#'):continue
            rid,rest=line.split('|',1);regex,typ,use,need=rest.rsplit('|',3)
            re.compile(regex)
            rules.append(dict(id=rid,regex=regex,product_type=typ,function=use,need=need))
    assert len({r['id'] for r in rules})==len(rules)
    return rules

def signature(r):return tuple(r.get(k,'') for k in ('product_type','function','need'))

class Engine:
    def __init__(self,rules,disagreements=()):
        self.rules=rules;self.compiled=[(r,re.compile(r['regex'],re.I)) for r in rules]
        self.disagreements={r['name_es_original']:r for r in disagreements}
    def match(self,title):
        starts={0}
        wrapper=re.match(r'^(?:(?:set|juego|pack|paquete|conjunto|kit|lote)\s+de\s+(?:\d+\s+)?)',title,re.I)
        if wrapper:starts.add(wrapper.end())
        found=[]
        for r,rx in self.compiled:
            for start in sorted(starts):
                m=rx.match(title[start:])
                if not m:continue
                end=start+m.end()
                if end<len(title) and title[end].isalpha() and title[end-1].isalpha():continue
                found.append(dict(rule=r,span=title[start:end],start=start,end=end))
        return sorted(found,key=lambda m:(-(m['end']-m['start']),m['start'],m['rule']['id']))
    def analyze(self,before):
        if before['status'] not in TARGET_STATES:return copy.deepcopy(before)
        title=before['name_es_original'];matches=self.match(title);out=copy.deepcopy(before)
        history=self.disagreements.get(title)
        out.update(version=VERSION,parent_result_hash=before['result_hash'],history_semantic_disagreement=bool(history),history_resolution=None)
        out['rule_conflicts']=[]
        if history:out['history_signature_evidence']=history
        if not matches:
            out['basis']='V23_NO_SUPPORTED_RULE_RETAINED'
            out['analysis_method']='V23_TARGET_REVIEW_NO_NEW_SUPPORTED_TITLE_RULE_PRIOR_CANDIDATE_RETAINED'
            if history:
                out['rule_conflicts']=['HISTORICAL_SAME_TITLE_SEMANTIC_DISAGREEMENT']
                out['status']='RULE_CONFLICT';out['use_need_hypotheses']=[]
                out['uncertainty_codes']=sorted(set(out['uncertainty_codes']+['RULE_OR_HISTORY_CONFLICT']))
        else:
            best=matches[0];width=best['end']-best['start']
            top=[m for m in matches if m['end']-m['start']==width]
            conflict=len({signature(m['rule']) for m in top})>1
            rule=best['rule'];out['product_type_candidate']=rule['product_type']
            out['type_evidence']=[dict(span=best['span'],start=best['start'],end=best['end'],role='MAIN_OBJECT_OR_TYPE_QUALIFIER')]
            out['rule_id']=rule['id'];out['basis']='V23_GENERIC_TITLE_RULE'
            out['matching_rules']=[dict(id=m['rule']['id'],type=m['rule']['product_type'],span=m['span']) for m in matches]
            use,need=rule['function'],rule['need']
            broad=not use or not need or old.BROAD.fullmatch(need) or need in old.WEAK_NEEDS
            vague=not rule['product_type'] or bool(old.GENERIC_TYPE.fullmatch(rule['product_type'])) or any(x in rule['product_type'] for x in ['待核','待定'])
            out['broad_hypotheses_not_for_matching']=[dict(use=use,need=need)] if broad else []
            out['use_need_hypotheses']=[] if broad or vague or conflict else [dict(use=use,consumer_need=need,evidence_span=best['span'],authority='ORDINARY_USE_HYPOTHESIS_NOT_LITERAL_FACT')]
            out['uncertainty_codes']=(['TYPE_INSUFFICIENT'] if vague else [])+(['SPECIFIC_NEED_INSUFFICIENT'] if broad else [])
            out['status']='RULE_CONFLICT' if conflict else 'FEATURE_TOO_BROAD' if broad or vague else 'SPECIFIC_SEMANTIC_CANDIDATE'
            if conflict:
                out['rule_conflicts']=['EQUAL_SPAN_SEMANTIC_CONFLICT'];out['uncertainty_codes'].append('RULE_OR_HISTORY_CONFLICT')
            if history and not conflict:
                if not vague and not broad:
                    out['history_resolution']='NEW_TITLE_GROUNDED_FULL_SIGNATURE_CANDIDATE; PRIOR DISAGREEMENTS RETAINED, NOT HUMAN ADJUDICATED'
                else:
                    out['rule_conflicts']=['HISTORICAL_SAME_TITLE_SEMANTIC_DISAGREEMENT']
                    out['uncertainty_codes']=sorted(set(out['uncertainty_codes']+['RULE_OR_HISTORY_CONFLICT']))
                    out['use_need_hypotheses']=[]
                    out['status']='RULE_CONFLICT'
        out['analysis_method']='AI_AUTHORED_GENERIC_TITLE_RULES_WITH_PROGRAM_APPLICATION_NOT_HUMAN_GOLD'
        out.pop('result_hash',None);out['result_hash']=p.digest(out)
        return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--label',required=True);ap.add_argument('--rules',nargs='+',required=True);a=ap.parse_args()
    rules=read_rules(a.rules);dis=p.read_jsonl(OUT/'audit_review/prior_signature_disagreements25.jsonl');e=Engine(rules,dis)
    baseline=p.read_jsonl(old.OUT/'final_candidate/results.jsonl');rows=[e.analyze(r) for r in baseline]
    frozen=[(b,r) for b,r in zip(baseline,rows) if b['status'] not in TARGET_STATES]
    assert len(frozen)==7045 and all(b==r for b,r in frozen)
    target=OUT/a.label;target.mkdir(parents=True,exist_ok=True)
    summary={'total':len(rows),'target_skus':2992,'frozen_unchanged':len(frozen),'rules':len(rules),'before':dict(collections.Counter(r['status'] for r in baseline)),'after':dict(collections.Counter(r['status'] for r in rows)),'target_after':dict(collections.Counter(r['status'] for b,r in zip(baseline,rows) if b['status'] in TARGET_STATES)),'human_gold':0,'accuracy':None,'website_facts_in_title_results':0}
    p.immutable(target/'rules.json',rules);p.immutable(target/'results.jsonl',rows,jsonl=True);p.immutable(target/'summary.json',summary)
    p.immutable(target/'changes.jsonl',[{'sku':b['sku'],'title':b['name_es_original'],'before_type':b['product_type_candidate'],'after_type':r['product_type_candidate'],'before_status':b['status'],'after_status':r['status'],'before_hash':b['result_hash'],'after_hash':r['result_hash'],'rule_id':r.get('rule_id')} for b,r in zip(baseline,rows) if b['result_hash']!=r['result_hash']],jsonl=True)
    print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
