"""Resume the frozen base plus its source-bound relation correction layer."""
import json,runpy
from assortment import RUN,WORK,p,read
runpy.run_path(str(WORK/'run_bulk.py'),run_name='__main__')
if not (RUN/'effective_full20018_v23.jsonl').exists():
 from relation_guard_v23 import main
 main()
method=read(RUN/'effective_method_v23.json')
assert method['guard_code_sha256']==p.filehash(WORK/'relation_guard_v23.py')
assert method['base_manifest_sha256']==p.filehash(RUN/'method_manifest.json')
completion={'version':method['version'],'method_sha256':p.filehash(RUN/'effective_method_v23.json'),'result_sha256':p.filehash(RUN/'effective_full20018_v23.jsonl'),'records':20018,'expensive_retrieval_recomputed':0}
p.immutable(RUN/'effective_completion.json',completion)
print(json.dumps({'effective_state':'ALREADY_COMPLETED','records':20018,'version':method['version'],'new_retrieval':0}),flush=True)
