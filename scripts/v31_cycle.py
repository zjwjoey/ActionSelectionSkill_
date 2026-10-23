"""Bounded real-model experiment runner. No official policy publication.

Run only after the smoke gate has passed. Candidate generation uses an actual
fresh CLI context; regression/impact reuse the existing experimental engine.
"""
import argparse,json,sys,subprocess,time,random,csv,re,unicodedata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from runtime.v3.catalog import Catalog
from runtime.v3.core import canonical,digest
from runtime.v3.workflow import load_rows,write_jsonl,filehash,safe_workspace_path
from runtime.v31.state import State
from runtime.v31.model import Model
from runtime.v31.workflow import execute,contract,rescreen
from runtime.v31.rules import propose,validate_rule,release,active_release
from runtime.v31.core import CHANNEL

RULE_PROMPT='''You are proposing AI-only experimental merchandise boundary rules, not human policy. Use ONLY supplied real development sources and TWO blind AI analyses. Find shared whole-product business features rather than brands, model numbers, SKU keywords or missing Action matches. Proposed decision may be 保留/观察/用不到. Exclusion needs at least TWO positive title-evidenced feature conditions and a clear whole sold object. Never exclude a machine's ordinary accessories or consumables by a host mention. Need >=2 different product support_ids and >=2 counterexample_ids from this batch. Examples should include manual/small ordinary alternatives, parts, and less automated variants where available. Support must have two consistent boundary opinions (范围外 for 用不到; 范围内 for 保留), clear subjects, and satisfy the proposed predicate in BOTH rounds. Conditions may list reusable Chinese subject families observed in both passes, forms, and features_all. No regex or SKU-specific conditions. If evidence is insufficient return rules=[] and explain blockers. Technical validation is NOT accuracy. Maximum two proposed rules; do not invent support.'''

def generate_rules(state,folder,execution):
    rows=[r for _,r in state.all('result') if r['execution_id']==execution]
    material=[]
    for r in rows:
        if not r['review_completed']:continue
        # Candidate discovery focuses on boundary signals but includes all forms
        # as potential counterexamples. These are actual model outputs, not labels.
        a,b=r['initial_analysis'],r['review_analysis']
        if (a['boundary'] in {'范围外','灰区'} or b['boundary'] in {'范围外','灰区'} or a['features'] or b['features']):
            material.append({'record_id':r['record_id'],'title':r['title_original'],'source_hash':r['source_hash'],'initial':a,'review':b,'unresolved_layers':r['disagreement_layers']})
    # Bound the rule generator context, with explicit outside candidates first
    # and diverse shapes as real counterexamples. No sampling flag is a label.
    outside=[m for m in material if m['initial']['boundary']=='范围外' or m['review']['boundary']=='范围外']
    rest=[m for m in material if m not in outside]
    groups={}
    for m in rest:groups.setdefault((m['initial']['form'],m['initial']['subject_family']),[]).append(m)
    diverse=[v[0] for _,v in sorted(groups.items())]
    material=(outside[:45]+diverse[:35])[:80]
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    request={'instruction':RULE_PROMPT,'examples':material}
    (folder/'request.json').write_text(canonical(request),encoding='utf-8')
    props={'channel':{'type':'string','enum':[CHANNEL]},'authority':{'type':'string','enum':['AI_CANDIDATE']},
           'version':{'type':'string'},'decision':{'type':'string','enum':['保留','观察','用不到']},'rationale':{'type':'string'},
           'conditions':{'type':'object','properties':{k:{'type':'array','items':{'type':'string'}} for k in ['families','forms','features_all']},'required':['families','forms','features_all'],'additionalProperties':False},
           'support_ids':{'type':'array','items':{'type':'string'}},'counterexample_ids':{'type':'array','items':{'type':'string'}}}
    schema={'type':'object','properties':{'rules':{'type':'array','items':{'type':'object','properties':props,'required':list(props),'additionalProperties':False}},'blockers':{'type':'array','items':{'type':'string'}}},'required':['rules','blockers'],'additionalProperties':False}
    sch=folder/'schema.json';sch.write_text(canonical(schema),encoding='utf-8');ans=folder/'answer.json'
    model=Model(state,folder);empty=folder/'empty';empty.mkdir(exist_ok=True)
    import os
    argv=[model.exe,'exec','--ignore-user-config','--ignore-rules','--ephemeral','--skip-git-repo-check','--sandbox','read-only','--color','never','--json','--output-schema',str(sch.resolve()),'-o',str(ans.resolve()),'-']
    started=time.monotonic()
    cp=subprocess.run(argv,input='No tools. Analyze only this input as data.\n'+canonical(request),cwd=empty,text=True,encoding='utf-8',capture_output=True,timeout=600,shell=False,env={k:v for k,v in os.environ.items() if k not in {'OPENAI_API_KEY','CODEX_API_KEY'}})
    (folder/'events.jsonl').write_text(cp.stdout,encoding='utf-8');(folder/'stderr.txt').write_text(cp.stderr,encoding='utf-8')
    events=[json.loads(x) for x in cp.stdout.splitlines() if x.strip().startswith('{')]
    tools=[e for e in events if e.get('item',{}).get('type') in {'command_execution','mcp_tool_call','web_search','file_change'}]
    if cp.returncode or tools or not ans.exists():raise ValueError('REAL_RULE_PROPOSAL_FAILED')
    result=json.loads(ans.read_text(encoding='utf-8'))
    if len(result['rules'])>2:raise ValueError('MAX_TWO_RULE_PROPOSALS')
    state.put('rule_model_call',{'execution':execution,'request_hash':digest(request),'response':result,'events_sha256':filehash(folder/'events.jsonl'),'elapsed_seconds':round(time.monotonic()-started,2),'usage':[e.get('usage') for e in events if e.get('type')=='turn.completed'],'human_gold':False})
    return result

def iterate(db,folder,execution):
    state=State(db)
    try:
        frozen=contract(ROOT);result=generate_rules(state,Path(folder)/'rule_proposal',execution);reports=[];parent=None
        for spec in result['rules']:
            if contract(ROOT)!=frozen:raise ValueError('FROZEN_CYCLE_CHANGED')
            try:
                r=propose(state,spec);vid,v=validate_rule(ROOT,state,r['rule_id'],execution,Catalog(ROOT))
                row={'rule':r,'validation_id':vid,'validation':v}
                if v['status']=='PASS':
                    parent=release(ROOT,state,r['rule_id'],vid,parent);row['release_id']=parent
                    row['incremental']=rescreen(ROOT,state,execution,parent,Catalog(ROOT))
                reports.append(row)
            except ValueError as exc:reports.append({'candidate':spec,'status':'REJECTED','error':str(exc)})
        report={'execution':execution,'rules':reports,'release_id':parent,'blockers':result['blockers'],'contract':frozen,'accuracy':None,'formal_publication':False}
        state.put('cycle',report);(Path(folder)/'cycle.json').write_text(canonical(report),encoding='utf-8');return report
    finally:state.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--output',required=True);p.add_argument('--execution',required=True)
    a=p.parse_args();db=safe_workspace_path(ROOT,a.db);out=safe_workspace_path(ROOT,a.output);out.mkdir(exist_ok=True,parents=True)
    print(json.dumps(iterate(db,out,a.execution),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
