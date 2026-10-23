"""Bind real current-session Codex review notes; never make human feedback."""
import json,sys
from assortment import Matcher,lines
import boundary_learning as b
def main(stage):
    rows={r['review_id']:r for r in lines(b.OUT/f'inputs_{stage}.jsonl')};refs={r['sku']:r for r in Matcher().model['references']};out=[];seen=set()
    for line in (b.OUT/f'codex_{stage}.tsv').read_text(encoding='utf8').splitlines():
        if not line.strip():continue
        parts=line.split('|')
        if len(parts)!=11:raise ValueError('11_COLUMNS_REQUIRED:'+parts[0])
        ident,span,typ,dep,relation,scope,rule,sku,refspan,reason,unknown=parts
        if scope not in {'范围内','灰区','范围外','未知'} or relation not in {'A','B','C','D','E'} or dep not in {'standalone','universal_accessory','host_specific','installed','unknown'}:raise ValueError('INVALID_ENUM:'+ident)
        if ident in seen:raise ValueError('DUPLICATE_AI_REVIEW')
        seen.add(ident);r=rows[ident]
        if span not in r['title_original']:raise ValueError('NON_LITERAL_SUBJECT:'+ident)
        ref=None
        if sku:
            source=refs[sku]
            if refspan not in source['name_es_original']:raise ValueError('NON_LITERAL_REFERENCE:'+ident)
            ref={'action_sku':sku,'action_title':source['name_es_original'],'source_row_id':source['source_row_id'],'relation':relation,'literal_span':refspan}
        elif relation!='E':raise ValueError('REFERENCE_REQUIRED:'+ident)
        out.append({'record_id':r['record_id'],'review_id':ident,'source_binding':b.binding(r),'input_hash':r['input_hash'],'title_original':r['title_original'],
            'semantic':{'subject_span':span,'type':typ,'dependency':dep,'relation':relation,'function_need_hypothesis':reason,'unknowns':unknown},
            'action_reference':ref,'scope':scope,'boundary_rule':rule,'reason':reason,'analysis_authority':'REAL_CURRENT_CODEX_SEMANTIC_PROPOSAL_NOT_HUMAN_GOLD',
            'model':'CURRENT_CODEX_SESSION;exact_model_id_unavailable','prompt_version':'BOUNDARY-V0-TITLE-SCOPE-1','external_api_calls':0,'human_gold':False,
            'prompt_contract':'先识别真实销售主体和使用需求，区分宿主与部件；只用原名一级类目；Action具体参照与经营边界分开；无参照不排除；未知不猜；三态仅AI候选；保留原名片段和未决问题'})
    b.save(f'semantic_{stage}.jsonl',out,True);print('BOUND_REAL_CODEX_REVIEWS',len(out))
if __name__=='__main__':main(int(sys.argv[1]))
