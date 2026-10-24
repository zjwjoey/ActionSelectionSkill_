"""Opt-in reviewed observation contract. Never creates an exclusion or human label."""
import copy, unicodedata,re
from .core import validate
from .model import schema

VERSION='v3.1-reviewed-observation-2'
BLOCKERS={'subject_unclear','mixed_bundle','host_dependency','operating_boundary','custom_order','safety_claim_dependency','source_conflict'}
STRUCTURES={'single','homogeneous_multipack','mixed_components','unknown'}

INSTRUCTION='''
REVIEWED OBSERVATION CONTRACT v2. Provide extra screening_evidence for each record.
type_key: short reusable precise Chinese sold-product type, no brand/model/dimensions/pack count. Use stable common Chinese types, not a broad need. E.g. a pack of porcelain bowls and one porcelain bowl have type_key 瓷碗. A coffee cup and coffee tamper do NOT share type_key. A vacuum bag is not a vacuum. Do not force similarity.
structure: single / homogeneous_multipack / mixed_components / unknown. Homogeneous multipack means multiple units of the SAME complete type, not a tool kit with different functions. structure_span must be a literal title substring supporting this judgement. A tiny incidental pouch/spoon does not automatically make the main subject unknown; if distinct material components truly drive the purchase, mixed_components. Retain uncertainties instead of inventing contents.
scope: daily_independent / boundary_unresolved / outside_candidate / unknown. Ordinary clearly identified daily household materials and universal manual accessories may be candidates EVEN IF no Action counterpart exists. Missing reference, unknown reference specifications, different pack count, variant/material or unverified generic marketing performance alone are NOT operating blockers. Do not mark the SAME type as one model's ordinary_good vs another's bundle only because of unit count.
blockers: arrays of {code,span,reason}, with literal TITLE span. codes subject_unclear,mixed_bundle,host_dependency,operating_boundary,custom_order,safety_claim_dependency,source_conflict. Identify concrete unresolved decisions, not generic unknowns. Complete furniture remains boundary_unresolved. Dedicated fit-critical host parts, novel electrical/heating forms, specialist printing equipment, chemical spray/coating or skin-contact manufacturing inputs remain boundary questions unless the supplied operating calibration explicitly supports that type. Do not expand a domestic fan-heater approval to quartz heaters or heated mats. Explicit made-to-order/photo customization remains custom_order. Safety-critical product identity such as anti-drug drink protection is a blocker, but a generic washable or strong claim on a normal good is not. Ordinary static ornaments differ from large moving sensor-controlled animatronic assemblies.
Source ambiguity about the actual sold object (box vs soft bag, unidentified electrical form) is a blocker. Never infer a power source from a brand. Do not turn absent evidence into fact. An isolated accessory with uncertain compatibility stays observe, not excluded as the machine it fits.
Reference relations describe only true evidence: same_type, related_type, specific_need, category_only, host_only, none. A sock is not a sock clip; tea is not an empty tea filter; cocktail shaker is not a tea pot; decorative stamps are not metal stamping dies. If exact reference proof is absent choose a weaker/none relation, do not boost relation to secure retention. Distinguish reasonable family similarity from guaranteed interchangeability. Use literal original reference names only.
For scope daily_independent keep operating_context daily and boundary 范围内 only if evidence supports them. If any blocking issue exists, set scope boundary_unresolved/unknown/outside_candidate and list it. Daily scope alone is not an approved exclusion. The program will compare two independent readings; your output is AI evidence, never human Gold.
'''

def review_schema(requests=None):
    s=copy.deepcopy(schema(requests));p=s['properties']['analyses']['items']['properties']
    obj={'type':'object','properties':{'contract':{'type':'string','enum':[VERSION]},'type_key':{'type':'string'},'structure':{'type':'string','enum':sorted(STRUCTURES)},'structure_span':{'type':'string'},'scope':{'type':'string','enum':['daily_independent','boundary_unresolved','outside_candidate','unknown']},'blockers':{'type':'array','items':{'type':'object','properties':{'code':{'type':'string','enum':sorted(BLOCKERS)},'span':{'type':'string'},'reason':{'type':'string'}},'required':['code','span','reason'],'additionalProperties':False}}},'required':['contract','type_key','structure','structure_span','scope','blockers'],'additionalProperties':False}
    p['screening_evidence']=obj;s['properties']['analyses']['items']['required'].append('screening_evidence');return s

def validate_review(row,a,catalog):
    validate(row,a,catalog)
    e=a.get('screening_evidence')
    if not isinstance(e,dict) or e.get('contract')!=VERSION:raise ValueError('REVIEW_CONTRACT_REQUIRED')
    if not isinstance(e.get('type_key'),str) or not e['type_key'].strip():raise ValueError('REVIEW_TYPE_REQUIRED')
    if e.get('structure') not in STRUCTURES or not e.get('structure_span') or e['structure_span'] not in row['title_original']:raise ValueError('REVIEW_STRUCTURE_LITERAL_REQUIRED')
    if e.get('scope') not in {'daily_independent','boundary_unresolved','outside_candidate','unknown'}:raise ValueError('REVIEW_SCOPE_REQUIRED')
    if not isinstance(e.get('blockers'),list):raise ValueError('REVIEW_BLOCKERS_REQUIRED')
    for b in e['blockers']:
        if set(b)!={'code','span','reason'} or b['code'] not in BLOCKERS or not b['span'] or b['span'] not in row['title_original'] or not isinstance(b['reason'],str) or not b['reason'].strip():raise ValueError('REVIEW_BLOCKER_LITERAL_REQUIRED')
    if e['blockers'] and e['scope']=='daily_independent':raise ValueError('REVIEW_DAILY_WITH_BLOCKER')
    return a

def norm(s):return ' '.join(unicodedata.normalize('NFKC',s).casefold().split())

def literal_identity_agrees(a,b):
    """Literal sold-object agreement, not equality of Chinese taxonomy wording.

    Generic kit/pack/part labels cannot anchor identity. This only resolves
    naming granularity after the caller separately checks form, scope,
    composition, uncertainty and source-bound evidence in both readings.
    """
    left,right=norm(a['subject_span']),norm(b['subject_span'])
    if not (left in right or right in left):return False
    common=left if len(left)<=len(right) else right
    generic={'kit','set','juego','pack','conjunto','producto','articulo','artículo','pieza','piezas','accesorio','accesorios','herramienta','herramientas','de','del','para','con','un','una','el','la','los','las','y'}
    return any(len(w)>=4 and w not in generic for w in re.findall(r'[^\W\d_]+',common))

def reviewed_projection(row,a,b,catalog,baseline):
    out=copy.deepcopy(baseline)
    out.update(review_contract=VERSION,baseline_decision=baseline['decision'],reviewed_adjustment=False,formal_publication=False)
    if baseline.get('human_confirmed'):return out
    if a is None or b is None:return dict(out,decision='观察',reason_code='SECOND_REVIEW_PENDING')
    validate_review(row,a,catalog);validate_review(row,b,catalog)
    ea,eb=a['screening_evidence'],b['screening_evidence']
    out['blocking_evidence']=ea['blockers']+eb['blockers']
    # New review cannot broaden any exclusion, even if AI labels outside.
    if baseline['decision']=='用不到':return out
    eligible_rel={'same_type','related_type'}
    if a['relation']==b['relation']=='same_type':grade='same_type_candidate'
    elif a['relation'] in eligible_rel and b['relation'] in eligible_rel:grade='family_candidate'
    else:grade='unproven_or_disputed'
    out['action_reference_status']=grade
    # Preserve raw readings, but don't expose a weak/disputed match as an exact reference.
    if grade=='unproven_or_disputed':out['reference']=None
    elif out.get('reference') and grade=='family_candidate':out['reference']['relation']='related_type'
    if out['blocking_evidence']:
        out.update(decision='观察',reason_code='REVIEW_CONCRETE_BLOCKER',reason='存在具体未决项：'+'；'.join(dict.fromkeys(x['reason'] for x in out['blocking_evidence'])))
    else:
        ordinary={'ordinary_good','universal_accessory','bundle'}
        safe=all(x['information_status']=='clear' and x['form'] in ordinary and x['operating_context']=='daily' and x['boundary']=='范围内' for x in [a,b])
        key_equal=norm(ea['type_key'])==norm(eb['type_key'])
        span_equal=literal_identity_agrees(a,b)
        consistent=key_equal or span_equal
        out['type_wording_variation_resolved']=not key_equal and span_equal
        composition=all(e['structure'] in {'single','homogeneous_multipack'} and e['scope']=='daily_independent' for e in [ea,eb])
        # Explicit constrained operating categories may intentionally stay gray.
        protected=baseline.get('calibration_rules') and baseline['decision']=='观察'
        if safe and consistent and composition and not protected:
            out.update(decision='保留',reason_code='REVIEW_CLEAR_DAILY_SUBJECT',reason='两轮均识别为明确独立日用品；同类多件装不改变主体，参照不足不单独阻断初筛。',homogeneous_pack_compatible=ea['structure']!=eb['structure'] or ea['structure']=='homogeneous_multipack')
        elif baseline['decision']=='保留' and (not consistent or not composition):
            out.update(decision='观察',reason_code='REVIEW_SUBJECT_OR_SCOPE_UNRESOLVED',reason='两轮商品类型、组合构成或经营范围未能一致确认。')
    out['reviewed_adjustment']=out['decision']!=baseline['decision']
    out['human_confirmed']=False
    return out
