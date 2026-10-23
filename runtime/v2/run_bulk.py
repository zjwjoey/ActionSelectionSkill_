"""Resume the experiment only with the exact approved technical fingerprints."""
import json
from assortment import ROOT,RUN,p,read,lines,screen
gate=read(RUN/'technical_gate.json');protocol=read(RUN/'final_trial_protocol.json')
assert gate['gate']=='PASS_FOR_EXPERIMENTAL_BULK_ONLY'
assert p.filehash(RUN/'method_manifest.json')==gate['current_method_sha256']
assert all(p.filehash(ROOT/f)==h for f,h in protocol['code_sha256'].items())
source=read(RUN/'amazon_source_manifest.json');assert p.filehash(source['source_file'])==gate['current_source_sha256']
completion=RUN/'bulk_first_completion.json'
if completion.exists():
 previous=read(completion)
 assert previous['total']==source['source_rows'] and (RUN/'full20018_results.jsonl').exists()
 print(json.dumps({'state':'ALREADY_COMPLETED','rows':previous['total'],'new_analysis':0,'original_completion_preserved':True}),flush=True)
else:
 result,summary=screen(lines(RUN/'amazon_inputs.jsonl'),'full20018')
 p.immutable(completion,summary)
 assert len(result)==source['source_rows']
