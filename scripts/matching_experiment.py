"""Private-output experiment entrypoint; originals and V1.4 stay read-only."""
import argparse,json,sys,os
from contextlib import contextmanager
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from runtime.matching_v2.experiment import prepare,rows,PROMPT,schema,validate
from runtime.matching_v2.data_audit import digest,write_jsonl
from runtime.v31.state import State
from runtime.v31.model import Model

@contextmanager
def exclusive_method(work,method):
    """Fail closed on same-arm concurrent execution, including stale locks."""
    lock=work/f'.method_{method}.lock'
    with lock.open('x',encoding='utf8') as f:f.write(str(os.getpid()))
    try:yield
    finally:lock.unlink()

def run_unlocked(work,method):
    freeze=json.loads((work/'freeze.json').read_text(encoding='utf8'))
    assert digest(work/'sample200.jsonl')==freeze['sample_sha256']
    for rel,sha in freeze['code_hashes'].items():
        if digest(ROOT/rel)!=sha:raise ValueError('FROZEN_METHOD_CHANGED:'+rel)
    path=work/f'requests_{method}.jsonl'
    if digest(path)!=freeze['request_hashes'][method]:raise ValueError('INPUT_CHANGED')
    requests=rows(path);directory=work/method;directory.mkdir(exist_ok=True)
    state=State(directory/'events.sqlite3')
    try:
        model=Model(state,directory/'calls',mode='codex',timeout=600,instruction=PROMPT,schema_factory=schema)
        results=[]
        for offset in range(0,len(requests),10):
            batch=requests[offset:offset+10]
            answers=model.run(batch,'understand')
            for req,answer in zip(batch,answers):validate(req,answer)
            results+=answers
            write_jsonl(directory/'validated_progress.jsonl',results)
            print(json.dumps({'method':method,'completed':len(results),'calls_this_attempt':model.calls,'cache_reused':model.reused}),flush=True)
        write_jsonl(work/f'results_{method}.jsonl',results)
        (directory/'usage.json').write_text(json.dumps({'calls':state.all('model_call'),'failures':state.all('model_failure'),'db_integrity':state.db.execute('PRAGMA integrity_check').fetchone()[0]},ensure_ascii=False,indent=2),encoding='utf8')
    finally:state.close()

def run(work,method):
    with exclusive_method(work,method):run_unlocked(work,method)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run','collect']);p.add_argument('--work',required=True);p.add_argument('--method',choices=['A','B']);a=p.parse_args();w=Path(a.work).resolve()
    if not w.is_relative_to(ROOT/'work'):p.error('Keep private observations under this checkout work/ ignore directory')
    if a.command=='prepare':print(json.dumps(prepare(ROOT,w),ensure_ascii=False))
    elif a.command=='collect':
        from runtime.matching_v2.reporting import collect
        print(json.dumps(collect(w),ensure_ascii=False))
    else:
        if not a.method:p.error('--method required')
        run(w,a.method)
