"""Resumable paired comparison on identical two-pass model inputs, opt-in only."""
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from .core import source,reconcile
from .calibration import calibrated
from .reviewed import VERSION,INSTRUCTION,review_schema,validate_review,reviewed_projection
from .model import Model,INSTRUCTION as BASE_INSTRUCTION
from .state import State
from runtime.v3.workflow import safe_workspace_path,load_rows,write_jsonl,filehash
from runtime.v3.core import digest

def execute_reviewed(root,raw,db,output,catalog,policy_path,mode='queue',analysis=None,review=None,prompt=None,batch_size=25,freeze=None):
    root=Path(root);out=safe_workspace_path(root,output);out.mkdir(parents=True,exist_ok=True)
    (out/'requests').mkdir(exist_ok=True)
    state=State(safe_workspace_path(root,db))
    def guard():
        if freeze:
            for rel,sha in freeze['protected_files'].items():
                if filehash(root/rel)!=sha:raise ValueError('REVIEWED_FROZEN_CONTRACT_CHANGED:'+rel)
    try:
        guard();rows=[source(x) for x in raw]
        if not rows or len({x['record_id'] for x in rows})!=len(rows):raise ValueError('EMPTY_OR_DUPLICATE_REVIEWED_INPUT')
        policy=json.loads(Path(policy_path).read_text(encoding='utf-8'))
        instruction=Path(prompt).read_text(encoding='utf-8') if prompt else BASE_INSTRUCTION+INSTRUCTION
        if INSTRUCTION.strip() not in instruction:raise ValueError('REVIEWED_INSTRUCTION_REQUIRED')
        spec={'version':VERSION,'sources':rows,'policy_hash':digest(policy),'prompt_hash':digest(instruction),'freeze':freeze,'paired_same_semantics':True,'human_gold':False}
        run=state.put('reviewed_run',spec)
        def model(role):return Model(state,out/'calls'/role,mode='file' if (analysis if role=='understand' else review) else mode,notes=analysis if role=='understand' else review,instruction=instruction,schema_factory=review_schema,validator=validate_review)
        first,second=model('understand'),model('critic')
        execution=state.put('reviewed_execution',{'run':run,'providers':[first.identity,second.identity],'batch_size':batch_size})
        done={v['record_id']:v for _,v in state.all('reviewed_result') if v['execution']==execution}
        errors=[]
        for start in range(0,len(rows),batch_size):
            guard();chunk=rows[start:start+batch_size]
            if all(r['record_id'] in done for r in chunk):continue
            requests=[dict(r,action_candidates=[{'sku':c['sku'],'name_es_original':c['name_es_original']} for c in catalog.retrieve(r['title_original'],limit=6)]) for r in chunk]
            write_jsonl(out/'requests'/f'{start:04d}.jsonl',requests)
            readings=[]
            try:
                def bounded(provider,role):
                    for attempt in range(2):
                        try:values=provider.run(requests,role,catalog);break
                        except ValueError as exc:
                            if attempt or 'RETRY_ONLY_UNCACHED_ROWS' not in str(exc):raise
                    return values
                if first.mode==second.mode=='codex':
                    def worker(role):
                        ws=State(safe_workspace_path(root,db));wm=Model(ws,out/'calls'/role,mode='codex',instruction=instruction,schema_factory=review_schema,validator=validate_review)
                        try:return bounded(wm,role),wm.calls,wm.reused
                        finally:ws.close()
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        fa=pool.submit(worker,'understand');fb=pool.submit(worker,'critic');va,vb=fa.result(),fb.result()
                    first.calls+=va[1];second.calls+=vb[1]
                    readings=[{v['record_id']:v for v in va[0]},{v['record_id']:v for v in vb[0]}]
                else:
                    readings=[{v['record_id']:v for v in bounded(provider,role)} for provider,role in [(first,'understand'),(second,'critic')]]
                if mode=='queue':break
                staged=[]
                for r in chunk:
                    a=readings[0].get(r['record_id']);b=readings[1].get(r['record_id'])
                    if not a or not b:raise ValueError('REVIEWED_TWO_PASSES_REQUIRED')
                    base=calibrated(r,a,b,reconcile(r,a,b,catalog),policy)
                    new=reviewed_projection(r,a,b,catalog,base)
                    staged.append(dict(record_id=r['record_id'],source_hash=r['source_hash'],source=r,first=a,second=b,baseline=base,reviewed=new,run=run,execution=execution,human_gold=False))
                guard()
                for v in staged:state.put('reviewed_result',v);done[v['record_id']]=v
            except (ValueError,KeyError,TypeError,OSError) as exc:
                errors.append({'start':start,'error':str(exc)});break
            ordered=[done[r['record_id']] for r in rows if r['record_id'] in done]
            write_jsonl(out/'results.jsonl',ordered)
            report={'run':run,'execution':execution,'completed':len(ordered),'pending':len(rows)-len(ordered),'baseline':dict(Counter(v['baseline']['decision'] for v in ordered)),'reviewed':dict(Counter(v['reviewed']['decision'] for v in ordered)),'changed':sum(v['baseline']['decision']!=v['reviewed']['decision'] for v in ordered),'actual_model_process_calls_this_attempt':first.calls+second.calls,'human_gold':0,'formal_accuracy':None}
            (out/'progress.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False),flush=True)
        guard();ordered=[done[r['record_id']] for r in rows if r['record_id'] in done]
        write_jsonl(out/'results.jsonl',ordered)
        report={'run':run,'execution':execution,'completed':len(ordered),'pending':len(rows)-len(ordered),'baseline':dict(Counter(v['baseline']['decision'] for v in ordered)),'reviewed':dict(Counter(v['reviewed']['decision'] for v in ordered)),'changed':sum(v['baseline']['decision']!=v['reviewed']['decision'] for v in ordered),'actual_model_process_calls_this_attempt':first.calls+second.calls,'errors':errors,'human_gold':0,'formal_accuracy':None,'integrity':state.store.check(),'formal_publication':False}
        (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');state.put('reviewed_attempt',report)
        return report
    finally:state.close()
