"""Reuse exact-source AI role evidence without overriding reference gates."""
from pathlib import Path
import subject_v2512 as previous
from subject_reference_core import ReferenceEngine
from assortment import ROOT,Matcher,lines,norm
VERSION='subject-source-bound-role-cache-v2.5.13'
CACHE_ROOT=ROOT/'v2/runs/amazon_v251_ai_calibration_20261022'
CACHE_PATHS=[CACHE_ROOT/'ai_review_112_bound.jsonl',CACHE_ROOT/'ai_review_150_bound.jsonl']

def resolve_role(source,parsed,review):
 if parsed.get('role_note')!='EARLIER_SOURCE_NOUN_UNRESOLVED' or not review:return parsed
 if review.get('source_record_id')!=source['record_id'] or review.get('input_hash')!=source['input_hash'] or review.get('title_original')!=source['title_original']:
  return dict(parsed,role_cache_note='SOURCE_VERSION_MISMATCH')
 evidence=norm(review.get('subject_evidence',''))
 rejected=parsed.get('rejected_later_subject',{});span=norm(rejected.get('evidence_span',''))
 if review.get('subject_status')!='CLEAR' or not evidence or evidence not in norm(source['title_original']) or not span or span not in evidence:
  return dict(parsed,role_cache_note='SOURCE_SPAN_OR_ROLE_UNSUPPORTED')
 return dict(rejected,role_resolution='EXACT_SOURCE_AI_REVIEW_HINT',
  role_review_id=review['review_id'],role_evidence=review['subject_evidence'],human_confirmed=False)

class Engine(ReferenceEngine):
 def __init__(self,matcher=None,reviews=None):
  matcher=matcher or Matcher();features=getattr(matcher,'f',None)
  parse=lambda title:previous.subject(title,features)
  super().__init__(VERSION,parse,previous.boundary,previous.compatible,matcher)
  self.reviews={r['source_record_id']:r for r in (reviews if reviews is not None else sum((lines(p) for p in CACHE_PATHS),[]))}
 def analyze_many(self,rows):
  # Reference subjects were parsed independently from Action source titles in
  # __init__. Query-only cache use is scoped to exact record/version matches.
  parsed={};bindings={}
  for row in rows:bindings.setdefault(row['title_original'],set()).add((row['record_id'],row['input_hash']))
  for row in rows:
   item=self.parse(row['title_original'])
   # Same-title rows with different source bindings cannot share a hint.
   if len(bindings[row['title_original']])==1:item=resolve_role(row,item,self.reviews.get(row['record_id']))
   parsed[row['title_original']]=item
  plain=self.parse
  try:
   self.parse=lambda title:parsed.get(title,plain(title))
   return super().analyze_many(rows)
  finally:self.parse=plain
