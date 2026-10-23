"""Materialize actual Codex title reasoning and exact-source provenance."""
import sys
from assortment import Matcher,lines
import semantic_understanding_v01 as s
import boundary_learning as b
def main(stage):
    srcfile='inputs_semantic200.jsonl' if stage=='200' else 'inputs_validation300.jsonl'
    rows={r['review_id']:r for r in lines(s.OUT/srcfile)};refs={r['sku']:r for r in Matcher().model['references']};seen=set();out=[]
    for line in (s.OUT/f'ai_{stage}.tsv').read_text(encoding='utf8').splitlines():
        if not line.strip():continue
        p=line.split('|')
        if len(p)!=11:raise ValueError('11_FIELDS_REQUIRED:'+p[0]+':'+str(len(p)))
        ident,span,typ,dep,scope,rel,sku,refspan,fn,reason,unknown=p
        if ident in seen:raise ValueError('DUPLICATE_REVIEW')
        seen.add(ident);r=rows[ident];reference=None
        if sku:
            ref=refs[sku]
            if not refspan or refspan not in ref['name_es_original']:raise ValueError('REFERENCE_SPAN:'+ident)
            reference={'action_sku':sku,'action_title':ref['name_es_original'],'source_row_id':ref['source_row_id'],'relation':rel,'literal_span':refspan}
        a={'record_id':r['record_id'],'review_id':ident,'source_binding':s.binding(r),'input_hash':r['input_hash'],'title_original':r['title_original'],
            'semantic':{'subject_span':span,'type':typ,'dependency':dep,'relation':rel,'function_need_hypothesis':fn,'unknowns':unknown},
            'action_reference':reference,'scope':scope,'boundary_rule':'V01_SEMANTIC_'+scope,'reason':reason,
            'analysis_authority':'REAL_CURRENT_CODEX_SEMANTIC_PROPOSAL_NOT_HUMAN_GOLD','model':'CURRENT_CODEX_SESSION_EXACT_ID_NOT_EXPOSED',
            'prompt_version':'BOUNDARY-V01-SEMANTIC-1','prompt_sha256':b.b24.p.filehash(s.PROMPT),'human_gold':False,'external_api_calls':0,
            'cache_key':s.pending_key(r)}
        s.validate_semantic(r,a,refs);out.append(a)
    if stage=='200' and len(out)!=200:raise ValueError('SEMANTIC200_INCOMPLETE')
    name='semantic200_bound.jsonl' if stage=='200' else 'validation300_bound.jsonl';s.save(name,out,True);print('REAL_CODEX_BOUND',stage,len(out))
if __name__=='__main__':main(sys.argv[1])
