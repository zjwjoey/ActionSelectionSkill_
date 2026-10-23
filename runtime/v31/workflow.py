"""Resumable two-pass experiment, comparison and explicit rollback by release ID."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import tempfile
from pathlib import Path
from runtime.v3.core import canonical,digest,decide,source_record as formal_source
from runtime.v3.workflow import safe_workspace_path,asset_contract,write_jsonl
from runtime.v3.feedback import active_policy,evidence
from .core import VERSION,source,validate,project,reconcile
from .state import State
from .model import Model

def contract(root):
    root=Path(root)
    files=list(sorted((root/'runtime/v31').glob('*.py')))
    files += [root/'scripts/v31_cycle.py',root/'scripts/v31_prepare_validation.py']
    return dict(v3=asset_contract(root),v31={p.relative_to(root).as_posix():digest(p.read_text(encoding='utf-8')) for p in files if p.exists()})

def execute(root,raw_rows,db,output,catalog,mode='queue',analysis=None,review=None,release=None,purpose='development',batch_size=20,limit=None):
    from .rules import active_release
    root=Path(root);out=safe_workspace_path(root,output);out.mkdir(parents=True,exist_ok=True)
    state=State(safe_workspace_path(root,db))
    try:
        rows=[source(r) for r in raw_rows]
        raw_by_id={source(r)['record_id']:r for r in raw_rows}
        if not rows or len({r['record_id'] for r in rows})!=len(rows):raise ValueError('EMPTY_OR_DUPLICATE_EXPERIMENT_INPUT')
        if purpose not in {'development','smoke','independent','full'}:raise ValueError('INVALID_EXPERIMENT_PURPOSE')
        policy=active_policy(root,state.store);rules=active_release(root,state,release,catalog) if release else []
        frozen=contract(root)
        if purpose=='full':
            from .qualification import qualify
            gate=qualify(root,state,release,catalog)
            if not gate['passed']:raise ValueError('FULL_EXPERIMENT_TECHNICAL_GATE_NOT_READY:'+','.join(gate['blockers']))
        if purpose=='independent':
            exposed={s['record_id'] for _,r in state.all('run') if r['purpose'] in {'smoke','development'} for s in r['sources']}
            if any(r['record_id'] in exposed for r in rows):raise ValueError('INDEPENDENT_SOURCE_EXPOSED_IN_DEVELOPMENT')
        spec={'version':VERSION,'sources':rows,'contract':frozen,'release':release,'purpose':purpose,'formal_policy_hash':digest(policy)}
        run_id=state.put('run',spec)
        first=Model(state,out/'model',mode='file' if analysis else mode,notes=analysis)
        second=Model(state,out/'model',mode='file' if review else mode,notes=review)
        # Provider identity is a part of execution identity. File revisions cannot
        # silently reuse a prior run's results even when the source is unchanged.
        execution=state.put('execution',{'run':run_id,'analysis_provider':first.identity,'review_provider':second.identity,'batch_size':batch_size})
        completed=[];pending=[];errors=[];owners={}
        # These records are content-addressed and verified when loaded. Use an
        # immutable in-process snapshot rather than re-reading every prior request
        # for every product (quadratic SQL/JSON work during a cache-only replay).
        request_cache={v['key']:v['request'] for _,v in state.all('request')}
        for f in state.store.all('v3_feedback'):
            evidence(root,f);key=(f['record_id'],f['source_hash'])
            if key in owners and owners[key]['decision']!=f['decision']:raise ValueError('CONFLICTING_FORMAL_OWNER_FEEDBACK')
            owners[key]=f
        # V3 Owner binding uses its own hash contract; experimental category-aware
        # hashes are never treated as equivalent without checking the exact source.
        for start in range(0,len(rows),max(1,min(50,batch_size))):
            if limit is not None and len(completed)>=limit:pending.extend(rows[start:]);break
            chunk=rows[start:start+max(1,min(50,batch_size))];requests=[]
            for row in chunk:
                request_key=digest({'row':row,'catalog':frozen['v3']})
                req=request_cache.get(request_key)
                if req is None:
                    req=dict(row,action_candidates=[{'sku':c['sku'],'name_es_original':c['name_es_original']} for c in catalog.retrieve(row['title_original'],limit=6)])
                    state.put('request',{'key':request_key,'request':req});request_cache[request_key]=req
                requests.append(req)
            try:
                def bounded_model(provider,role):
                    for attempt in range(2):
                        try:return provider.run(requests,role,catalog)
                        except ValueError as exc:
                            if attempt or 'RETRY_ONLY_UNCACHED_ROWS' not in str(exc):raise
                if first.mode==second.mode=='codex':
                    def worker(provider,role):
                        ws=State(safe_workspace_path(root,db));wm=Model(ws,provider.dir,mode='codex')
                        try:
                            try:return bounded_model(wm,role),None,wm.calls,wm.reused
                            except (ValueError,KeyError,TypeError,OSError) as exc:return [],str(exc),wm.calls,wm.reused
                        finally:ws.close()
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        fa=pool.submit(worker,first,'understand');fb=pool.submit(worker,second,'critic')
                        va,vb=fa.result(),fb.result()
                    first.calls+=va[2];first.reused+=va[3];second.calls+=vb[2];second.reused+=vb[3]
                    if va[1] or vb[1]:raise ValueError(va[1] or vb[1])
                    aa,bb=va[0],vb[0]
                else:aa=bounded_model(first,'understand');bb=bounded_model(second,'critic')
                amap={a['record_id']:a for a in aa};bmap={a['record_id']:a for a in bb}
                # Validate the whole model batch before committing any result.
                # A malformed row leaves this batch pending without double counting
                # seven already-written records as fifty still pending.
                for row in chunk:
                    for item in [amap.get(row['record_id']),bmap.get(row['record_id'])]:
                        if item:validate(row,item,catalog)
                for row in chunk:
                    a=amap.get(row['record_id']);b=bmap.get(row['record_id'])
                    if not a or not b:pending.append(row)
                    result=reconcile(row,a,b,catalog,rules,policy)
                    result['v3_baseline']=decide(row,a,catalog,policy)['decision']
                    # Honor existing real Owner decisions under their ORIGINAL
                    # V3 source contract. Do not rewrite approval hashes to the
                    # experimental category-aware hash or invent a new approval.
                    fr=formal_source(raw_by_id[row['record_id']]);owner=owners.get((fr['record_id'],fr['source_hash']))
                    if owner:
                        proof=decide(fr,None,catalog,policy,owner=owner)
                        result.update(decision=proof['decision'],authority=proof['authority'],human_confirmed=True,
                                      reason_code='EXACT_FORMAL_OWNER_DECISION',formal_owner_binding=proof,v3_baseline=proof['decision'])
                    result.update(run_id=run_id,execution_id=execution,release_id=release,purpose=purpose)
                    state.put('result',result);completed.append(result)
            except (ValueError,KeyError,TypeError,OSError) as exc:
                errors.append({'records':[r['record_id'] for r in chunk],'error':str(exc)})
                pending.extend(chunk)
                # No auto-spend or endless retry; preserve the batch and stop new calls.
                pending.extend(rows[start+len(chunk):]);break
            if contract(root)!=frozen:raise ValueError('FROZEN_EXECUTION_CONTRACT_CHANGED')
            write_jsonl(out/'progress_results.jsonl',completed)
            (out/'progress.json').write_text(canonical({'completed':len(completed),'pending':len(rows)-len(completed),'execution':execution,'calls':first.calls+second.calls}),encoding='utf-8')
        if contract(root)!=frozen:raise ValueError('FROZEN_EXECUTION_CONTRACT_CHANGED')
        parent=out/execution;parent.mkdir(exist_ok=True)
        target=Path(tempfile.mkdtemp(prefix='attempt_',dir=parent))
        write_jsonl(target/'inputs.jsonl',raw_rows);write_jsonl(target/'results.jsonl',completed)
        write_jsonl(target/'pending.jsonl',pending);write_jsonl(target/'errors.jsonl',errors)
        report={'run_id':run_id,'execution_id':execution,'purpose':purpose,'records':len(rows),'completed':sum(r['review_completed'] for r in completed),
                'result_rows':len(completed),'pending':len(pending),'errors':errors,'decisions':dict(Counter(r['decision'] for r in completed)),
                'disagreements':sum(r['disagreement'] for r in completed),'observation_reasons':dict(Counter(r['reason_code'] for r in completed if r['decision']=='观察')),
                'actual_model_process_calls':first.calls+second.calls,'reused_model_records':first.reused+second.reused,
                'provider_modes':[first.mode,second.mode],'human_gold_count':0,'accuracy':None,'formal_publication':False,
                'integrity':state.store.check(),'release':release,'output':str(target),'contract':frozen}
        state.put('attempt',report);(target/'summary.json').write_text(canonical(report),encoding='utf-8')
        return report
    finally:state.close()

def affected(state,execution,rules):
    from .core import matches
    results=[r for _,r in state.all('result') if r['execution_id']==execution]
    if not results:raise ValueError('BASE_EXECUTION_NOT_FOUND')
    return [r for r in results if not r.get('human_confirmed') and any(a and matches(rule,a) for a in [r['initial_analysis'],r['review_analysis']] for rule in rules)]

def rescreen(root,state,execution,release,catalog):
    from .rules import active_release
    rules=active_release(root,state,release,catalog);rows=affected(state,execution,rules);policy=active_policy(root,state.store)
    if any(r['purpose'] in {'independent','full'} for r in rows):
        # Validation/full runs are immutable evidence, never used as training inputs.
        purpose='incremental_evaluation'
    else:purpose='incremental_development'
    changes=[]
    for old in rows:
        row=state.get(old['run_id'],'run')['sources'];row=next(r for r in row if r['record_id']==old['record_id'])
        new=reconcile(row,old['initial_analysis'],old['review_analysis'],catalog,rules,policy)
        new.update(parent_execution=execution,parent_result_hash=digest(old),release_id=release,purpose=purpose)
        state.put('incremental_result',new)
        changes.append({'record_id':old['record_id'],'source_hash':old['source_hash'],'before':old['decision'],'after':new['decision'],'changed':old['decision']!=new['decision'],'reason':new['reason_code']})
    all_rows=[r for _,r in state.all('result') if r['execution_id']==execution]
    report={'parent_execution':execution,'release_id':release,'affected':len(rows),'unaffected':len(all_rows)-len(rows),
            'changed':sum(c['changed'] for c in changes),'changes':changes,'actual_model_process_calls':0,'rollback':'Use the immutable parent execution or an earlier release ID; no data overwrite.'}
    state.put('incremental',report);return report
