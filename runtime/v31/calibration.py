"""Portable frozen40 experimental projection, equivalent to its archived harness."""
import re
from .core import sale_role
from .reviewed import norm

def match_rule(row,a,rule):
    if not a or a['information_status']!='clear' or a['form']=='unknown':return False
    if norm(a['subject_type']) not in {norm(t) for t in rule['aliases']}:return False
    if a['form'] not in rule['forms']:return False
    title=row['title_original']
    if any(re.search(f,title,re.I) for f in rule.get('negative_fact_patterns',[])):return False
    if rule['decision']=='用不到':
        if a['boundary']!='范围外':return False
        if any(not re.search(f,title,re.I) for f in rule.get('literal_fact_patterns',[])):return False
        if rule.get('industrial') and 'industrial_context' not in {f['name'] for f in a['features']}:return False
    elif rule['decision']=='保留' and (a['operating_context']!='daily' or a['boundary']!='范围内'):return False
    return True

def calibrated(row,a,b,base,policy):
    out=dict(base,calibration_rules=[],calibration_authority='OWNER_ACCEPTED_CALIBRATION_EXPERIMENT_NOT_FORMAL',human_confirmed=False)
    if any(not x or x['information_status']!='clear' or x['form']=='unknown' for x in [a,b]):
        return dict(out,decision='观察',reason_code='CALIBRATION_INFORMATION_INSUFFICIENT')
    first=[r for r in policy['rules'] if match_rule(row,a,r)];second=[r for r in policy['rules'] if match_rule(row,b,r)]
    common=[r for r in first if r['id'] in {x['id'] for x in second}]
    if not common:return out
    if len({r['decision'] for r in common})!=1:return dict(out,decision='观察',reason_code='CALIBRATION_RULE_CONFLICT')
    if sale_role(a['form'])!=sale_role(b['form']):return dict(out,decision='观察',reason_code='CALIBRATION_SOLD_FORM_DISAGREEMENT')
    return dict(out,decision=common[0]['decision'],reason_code='OWNER_CALIBRATED_EXPERIMENT_RULE',calibration_rules=[r['id'] for r in common],calibration_support_ids=sorted({s for r in common for s in r['support_ids']}))
