"""Explicit opt-in experimental commands. Formal V3 commands are unchanged."""
import argparse,json,sys
from pathlib import Path
from runtime.v3.catalog import Catalog
from runtime.v3.workflow import load_rows,safe_workspace_path
from .workflow import execute,rescreen
from .state import State
from .rules import propose,validate_rule,release,active_release

def main(argv=None,root=None):
    root=Path(root or Path(__file__).resolve().parents[2]);p=argparse.ArgumentParser()
    p.add_argument('command',choices=['experiment-screen','experiment-propose','experiment-validate','experiment-release','experiment-rescreen'])
    for k in ['input','analysis','review','file','rule','validation','parent','execution','release']:p.add_argument('--'+k)
    p.add_argument('--mode',choices=['codex','file','queue'],default='queue');p.add_argument('--batch-size',type=int,default=20)
    p.add_argument('--purpose',choices=['smoke','development','independent','full'],default='development')
    p.add_argument('--db',default=str(root/'learning_data/action_selection.sqlite3'));p.add_argument('--output',default=str(root/'work/v31'))
    a=p.parse_args(argv);state=None
    def require(k):
        if not getattr(a,k):raise ValueError('--'+k+' required')
        return getattr(a,k)
    try:
        catalog=Catalog(root)
        if a.command=='experiment-screen':
            result=execute(root,load_rows(require('input')),a.db,a.output,catalog,a.mode,a.analysis,a.review,a.release,a.purpose,a.batch_size)
        else:
            state=State(safe_workspace_path(root,a.db))
            if a.command=='experiment-propose':result=propose(state,json.loads(Path(require('file')).read_text(encoding='utf-8-sig')))
            elif a.command=='experiment-validate':
                key,result=validate_rule(root,state,require('rule'),require('execution'),catalog);result=dict(result,validation_id=key)
            elif a.command=='experiment-release':result={'release_id':release(root,state,require('rule'),require('validation'),a.parent)}
            else:result=rescreen(root,state,require('execution'),require('release'),catalog)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 2 if a.command=='experiment-screen' and (result['errors'] or (a.mode!='queue' and result['pending'])) else 0
    except (ValueError,KeyError,TypeError,OSError) as exc:
        print(json.dumps({'error':str(exc),'type':type(exc).__name__},ensure_ascii=False),file=sys.stderr);return 2
    finally:
        if state:state.close()
