"""Portable V3 commands. Original inputs and frozen assets are always read-only."""
import argparse,json,sys
from pathlib import Path
from .catalog import Catalog
from .core import canonical
from .workflow import Provider,screen,load_rows,safe_workspace_path
from .store import Store
from .feedback import bootstrap_owner,import_feedback,propose,validate_rule,publish,impact

COMMANDS={'knowledge','screen','feedback-bootstrap','feedback-import','rule-propose','rule-validate','rule-publish','impact','rescreen','evaluate'}

def main(argv=None,root=None):
    root=Path(root or Path(__file__).resolve().parents[2])
    p=argparse.ArgumentParser(description='Action V3 source-bound screening and audited feedback')
    p.add_argument('command',choices=sorted(COMMANDS))
    p.add_argument('--input');p.add_argument('--analysis');p.add_argument('--file');p.add_argument('--rule');p.add_argument('--validation')
    p.add_argument('--cases');p.add_argument('--approval');p.add_argument('--release');p.add_argument('--run')
    p.add_argument('--provider',choices=['queue','file','cache','command'],default='queue');p.add_argument('--command-config')
    p.add_argument('--purpose',choices=['development','pilot','independent'],default='pilot')
    p.add_argument('--db',default=str(root/'learning_data/action_selection.sqlite3'))
    p.add_argument('--output',default=str(root/'work/v3'))
    a=p.parse_args(argv)
    def required(key):
        val=getattr(a,key)
        if not val:raise ValueError('--'+key+' required')
        return val
    store=None
    try:
        if a.command=='knowledge':result=Catalog(root).describe()
        elif a.command=='screen':
            provider=Provider('file' if a.analysis else a.provider,notes=a.analysis,command_config=a.command_config)
            result=screen(root,load_rows(required('input')),a.db,a.output,provider,Catalog(root),purpose=a.purpose)
        else:
            store=Store(safe_workspace_path(root,a.db))
            if a.command=='feedback-bootstrap':result=bootstrap_owner(root,store)
            elif a.command=='feedback-import':result=import_feedback(root,store,load_rows(required('file')))
            elif a.command=='rule-propose':result=propose(root,store,json.loads(Path(required('file')).read_text(encoding='utf-8-sig')))
            elif a.command=='rule-validate':result=validate_rule(root,store,required('rule'),required('cases'),Catalog(root))
            elif a.command=='rule-publish':result=publish(root,store,required('rule'),required('validation'),json.loads(Path(required('approval')).read_text(encoding='utf-8-sig')))
            elif a.command in {'impact','rescreen'}:
                result=impact(root,store,required('release'),required('run'))
                if a.command=='rescreen' and result['sources']:
                    store.close();store=None
                    result=screen(root,result['sources'],a.db,a.output,Provider('cache'),Catalog(root),parent_run=a.run,purpose='pilot')
            elif a.command=='evaluate':
                from .evaluation import evaluate
                result=evaluate(root,store,required('run'))
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (ValueError,KeyError,TypeError,OSError) as exc:
        print(json.dumps({'error':str(exc),'type':type(exc).__name__},ensure_ascii=False),file=sys.stderr);return 2
    finally:
        if store:store.close()

if __name__=='__main__':raise SystemExit(main())
