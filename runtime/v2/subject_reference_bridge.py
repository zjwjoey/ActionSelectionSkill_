"""Use source-bound AI subject analysis with the existing Action retriever.

This module does not itself perform semantic inference. The active Codex model
supplies the review; this code verifies provenance, builds real reference
candidates, and projects the three public states under the experiment policy.
"""
from __future__ import annotations
import collections, json
from assortment import Matcher, lines, norm
import boundary_v24 as b24

VERSION='subject-reference-bridge-v2.5.1'
OUT=b24.ROOT/'v2/runs/amazon_v251_ai_calibration_20261022'
BOUNDARIES={'MAJOR_HOUSEHOLD_APPLIANCE','FIREARM_SPECIFIC_STORAGE','INDUSTRIAL_PRODUCTION_EQUIPMENT'}

def check_source_span(title,evidence):
 if not evidence or norm(evidence) not in norm(title):raise ValueError('EVIDENCE_NOT_IN_SOURCE_TITLE')
 return evidence

def project(source,review,references):
 if review['input_hash']!=source['input_hash'] or review['source_record_id']!=source['record_id'] or review['title_original']!=source['title_original']:
  raise ValueError('SOURCE_VERSION_MISMATCH')
 check_source_span(source['title_original'],review['subject_evidence'])
 linked=[]
 for r in review['action_references']:
  ref=references.get(r['action_sku'])
  if not ref or r['action_title']!=ref['name_es_original'] or r['action_source_row_id']!=ref['source_row_id']:
   raise ValueError('REFERENCE_NOT_BOUND_TO_ACTION_SOURCE')
  linked.append(dict(r))
 decision=review['decision'];gates=[]
 if decision not in {'保留','观察','用不到'}:raise ValueError('UNKNOWN_PUBLIC_STATE')
 if review['subject_status']!='CLEAR':decision='观察';gates.append('SUBJECT_INFORMATION_INSUFFICIENT')
 if review['primary_cause']=='FURNITURE_RESEARCH_SCOPE':decision='观察';gates.append('PRESERVE_FURNITURE_RESEARCH_SCOPE')
 if decision=='保留' and (not linked or review['reference_relation']!='SAME_FUNCTIONAL_CLASS'):
  decision='观察';gates.append('NO_VERIFIED_SAME_FUNCTIONAL_CLASS')
 if decision=='用不到' and review.get('boundary_code') not in BOUNDARIES:
  decision='观察';gates.append('BOUNDARY_NOT_IN_FROZEN_AI_POLICY')
 return {'review_id':review['review_id'],'record_id':source['record_id'],'input_hash':source['input_hash'],
  'title_original':source['title_original'],'subject':review['subject'],'subject_evidence':review['subject_evidence'],
  'subject_status':review['subject_status'],'decision':decision,'action_references':linked,
  'has_real_action_reference':bool(linked),'same_functional_class':bool(linked and review['reference_relation']=='SAME_FUNCTIONAL_CLASS'),
  'reference_relation':review['reference_relation'],'boundary_code':review.get('boundary_code',''),
  'reason':review['reason'],'gate_notes':gates,'review_origin':'CODEX_AI_DELEGATED','human_confirmed':False,'bridge_version':VERSION}

def retrieve_subject_candidates(matcher,title,subject_evidence,limit=30):
 check_source_span(title,subject_evidence)
 results=matcher.retrieve([title,subject_evidence])
 return merge_candidates(matcher,results,limit)

def merge_candidates(matcher,results,limit=30):
 bysku={}
 for channel,hits in zip(['original_title','source_subject_span'],results):
  for rank,(j,score) in enumerate(hits,1):
   ref=matcher.model['references'][j];entry=bysku.setdefault(ref['sku'],{'action_sku':ref['sku'],'action_title':ref['name_es_original'],'action_source_row_id':ref['source_row_id'],'retrieval_channels':{},'rrf':0.0})
   entry['retrieval_channels'][channel]={'rank':rank,'score':round(float(score),6)}
   entry['rrf']+=1/(60+rank)
 return sorted(bysku.values(),key=lambda r:(-r['rrf'],r['action_sku']))[:limit]

def main():
 matcher=Matcher();refs={r['sku']:r for r in matcher.model['references']};sources={r['record_id']:r for r in lines(b24.INPUTS)}
 reviews=lines(OUT/'ai_review_112_bound.jsonl')+lines(OUT/'ai_review_150_bound.jsonl')
 projected=[project(sources[r['source_record_id']],r,refs) for r in reviews]
 evidence=[]
 for start in range(0,len(reviews),32):
  batch=reviews[start:start+32];queries=[r['title_original'] for r in batch]+[r['subject_evidence'] for r in batch]
  got=matcher.retrieve(queries);n=len(batch)
  for i,r in enumerate(batch):
   merged=merge_candidates(matcher,[got[i],got[n+i]],40)
   chosen={a['action_sku'] for a in r['action_references']}
   old={matcher.model['references'][j]['sku'] for j,_ in got[i]}
   enhanced={a['action_sku'] for a in merged}
   enhanced20={a['action_sku'] for a in merged[:20]}
   evidence.append({'review_id':r['review_id'],'input_hash':r['input_hash'],'subject_query':r['subject_evidence'],
    'ai_keep_with_bound_reference':r['decision']=='保留','selected_reference_in_original_top20':bool(chosen&old),
    'selected_reference_in_subject_union_top20':bool(chosen&enhanced20),
    'selected_reference_in_subject_union_top40':bool(chosen&enhanced),'candidates':merged})
 keep=[r for r in evidence if r['ai_keep_with_bound_reference']]
 summary={'version':VERSION,'projected_records':len(projected),'projection_state_changes':sum(a['decision']!=b['decision'] for a,b in zip(reviews,projected)),
  'ai_retained_records_with_bound_references':len(keep),'original_top20_contains_ai_selected_reference':sum(r['selected_reference_in_original_top20'] for r in keep),
  'subject_query_union_top20_contains_ai_selected_reference':sum(r['selected_reference_in_subject_union_top20'] for r in keep),
  'subject_query_union_top40_contains_ai_selected_reference':sum(r['selected_reference_in_subject_union_top40'] for r in keep),
  'metric_is':'Retrieval coverage of AI-selected real Action references; not human semantic accuracy. Union has up to 40 candidates vs original20.',
  'semantic_inference_provider':'Current Codex explicit per-title AI review; no model API or training was invoked by this script',
  'row_specific_rules_added':False,'action_index_retrained':False,'human_gold':0,'formal_screening_replaced':False,
  'bridge_code_sha256':b24.p.filehash(__file__)}
 b24.p.immutable(OUT/'bridge_projected_262.jsonl',projected,jsonl=True)
 b24.p.immutable(OUT/'subject_retrieval_evidence_262_v2.jsonl',evidence,jsonl=True)
 b24.p.immutable(OUT/'bridge_summary_v2.json',summary)
 print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
