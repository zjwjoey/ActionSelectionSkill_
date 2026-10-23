"""Portable batch screening, actual semantic providers, cache and resume."""
from __future__ import annotations
import csv,json,subprocess,tempfile,os
from pathlib import Path
from .core import VERSION,canonical,digest,source_record,validate_analysis,decide
from .store import Store

PROMPT='''Understand the sold product from its original title only. Return one JSON object with record_id, source_hash (copy exactly), authority AI_CANDIDATE, subject_span (literal original substring), subject_type (concrete Chinese type), form, relation, action_sku, reference_span (literal Action original title substring), reason, functions (candidate strings), needs (candidate strings), information_status clear/insufficient, coverage subject/partial/unknown (whole sold subject including every bundle component; never assume full coverage from one component), operating_context daily/specialist/large_installation/unknown. Forms: ordinary_good,bundle,universal_accessory,host_component,installed_component,whole_machine,whole_system,unknown. Relations: same_type,related_type,specific_need,category_only,host_only,none. Identify the actual sold object, not a host mentioned after para/compatible. No images, prices, sales, reviews, inferred materials or missing facts. No found Action reference never means exclusion. Action same need does not prove same product type. Distinguish unknown meaning from uncertain operating scope. Daily small appliances are not automatically specialist. If there is no reliable reference use relation none and blank action_sku/reference_span. Do not output human labels or a final selection decision.'''

def filehash(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load_rows(path):
    p=Path(path)
    if p.suffix.lower()=='.csv':
        with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
    if p.suffix.lower()=='.json':return json.loads(p.read_text(encoding='utf-8-sig'))
    return [json.loads(s) for s in p.read_text(encoding='utf-8-sig').splitlines() if s.strip()]
def write_jsonl(path,rows):Path(path).write_text(''.join(canonical(r)+'\n' for r in rows),encoding='utf-8')
def evidence(root,obj):
    p=Path(obj.get('evidence_reference',''))
    if not p.is_absolute():p=Path(root)/p
    if not p.is_file() or filehash(p)!=obj.get('evidence_sha256'):raise ValueError('OWNER_EVIDENCE_MISSING_OR_CHANGED')

class Provider:
    def __init__(self,mode='queue',notes=None,command_config=None):
        self.mode=mode;self.notes={};self.config={};self.calls=0
        if mode=='file':
            if not notes:raise ValueError('ANALYSIS_FILE_REQUIRED')
            for a in load_rows(notes):
                if a['record_id'] in self.notes:raise ValueError('DUPLICATE_ANALYSIS_ID')
                self.notes[a['record_id']]=a
            self.identity='file:'+filehash(notes)
        elif mode=='command':
            self.config=json.loads(Path(command_config).read_text(encoding='utf-8'))
            argv=self.config.get('argv')
            if not isinstance(argv,list) or not argv or any(not isinstance(v,str) for v in argv):raise ValueError('COMMAND_ARGV_ARRAY_REQUIRED')
            if not self.config.get('identity') or not self.config.get('model'):raise ValueError('PROVIDER_IDENTITY_AND_MODEL_REQUIRED')
            self.identity='command:'+digest(self.config)
        elif mode in {'queue','cache'}:self.identity=mode
        else:raise ValueError('UNKNOWN_PROVIDER')
    def analyze(self,request):
        if self.mode=='file':return self.notes.get(request['record_id'])
        if self.mode=='command':
            self.calls+=1
            p=subprocess.run(self.config['argv'],input=canonical(request),capture_output=True,text=True,encoding='utf-8',
                timeout=min(600,max(1,int(self.config.get('timeout_seconds',120)))),shell=False,
                env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONUTF8='1'))
            if p.returncode:raise ValueError('SEMANTIC_PROVIDER_COMMAND_FAILED')
            return json.loads(p.stdout)
        return None

def asset_contract(root):
    paths=['assets/action_reference10037.jsonl','assets/action_semantics/results.jsonl','assets/action_semantics/product_type_library.json','assets/action_semantics/related_need_groups.json']
    paths+=['rules/v3_type_aliases.json']
    paths += [str(p.relative_to(root)).replace('\\','/') for p in sorted((Path(root)/'runtime/v3').glob('*.py'))]
    return {p:filehash(Path(root)/p) for p in paths}

def safe_workspace_path(root,path):
    root=Path(root).resolve();p=Path(path).resolve()
    # Restrict all generated writes to explicit learning/output locations.
    allowed=[root/'work',root/'learning_data']
    if p==root or (p.is_relative_to(root) and not any(p.is_relative_to(x) for x in allowed)):
        raise ValueError('GENERATED_PATH_MUST_USE_WORK_OR_LEARNING_DATA')
    # The live production project, Master and sibling research stores stay read-only.
    for name in ['ActionSKUTracker','Action-ES-Data-System']:
        if any(part.casefold()==name.casefold() for part in p.parts):
            raise ValueError('PRODUCTION_PATH_IS_READ_ONLY')
    if not p.is_relative_to(root) and p.suffix.lower() in {'.sqlite','.sqlite3','.db'} and p.exists():
        import sqlite3
        db=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)
        try:
            if db.execute('PRAGMA application_id').fetchone()[0]!=1095972403:raise ValueError('EXTERNAL_EXISTING_DATABASE_IS_READ_ONLY')
        finally:db.close()
    return p


def screen(root,input_rows,db_path,out_dir,provider,catalog,policy=None,parent_run=None,purpose='pilot'):
    root=Path(root);db_path=safe_workspace_path(root,db_path);out_dir=safe_workspace_path(root,out_dir)
    input_rows=list(input_rows);rows=[source_record(r) for r in input_rows]
    if len({r['record_id'] for r in rows})!=len(rows):raise ValueError('DUPLICATE_SOURCE_ID')
    if not rows:raise ValueError('EMPTY_INPUT')
    store=Store(db_path)
    try:
        from .feedback import active_policy
        trusted=active_policy(root,store)
        if policy is not None and policy!=trusted:raise ValueError('POLICY_MUST_BE_VERIFIED_PUBLISHED_REGISTRY')
        policy=trusted
        feedback=store.all('v3_feedback')
        owners={}
        for f in feedback:
            evidence(root,f)
            key=(f['record_id'],f['source_hash'])
            if key in owners and owners[key]['decision']!=f['decision']:raise ValueError('CONFLICTING_OWNER_DECISIONS')
            owners[key]=f
        contract={'method':VERSION,'sources':[(r['record_id'],r['source_hash']) for r in rows],
                  'assets':asset_contract(root),'policy_hash':digest(policy),'provider':provider.identity,'prompt_hash':digest(PROMPT),
                  'feedback_hash':digest(feedback),'parent_run':parent_run,'purpose':purpose}
        all_cached=store.all('v3_analyses') if provider.mode=='cache' else []
        if provider.mode=='cache':contract['cache_set_hash']=digest(sorted(digest(c) for c in all_cached if c.get('provider')!='cache'))
        run_id='v3-'+digest(contract)[:20]
        store.exact('v3_runs',{'id':run_id},contract)
        results=[];requests=[];errors=[];new_rows=0;reused=0
        for row in rows:
            new_rows+=store.exact('v3_sources',{'id':row['record_id'],'hash':row['source_hash']},row)
            key=digest({'source_hash':row['source_hash'],'provider':provider.identity,'method':VERSION,'assets':contract['assets'],'prompt':contract['prompt_hash']})
            cached=store.get('v3_analyses',key) if provider.mode!='cache' else None;a=cached.get('analysis') if cached else None
            if a is not None:reused+=1
            if a is None and provider.mode=='cache':
                matches=[c for c in all_cached if c.get('provider')!='cache' and c.get('source_hash')==row['source_hash'] and c.get('method')==VERSION and c.get('assets')==contract['assets'] and c.get('prompt_hash')==contract['prompt_hash']]
                unique={digest(c['analysis']):c['analysis'] for c in matches}
                if len(unique)==1:a=next(iter(unique.values()));reused+=1
                elif len(unique)>1:errors.append({'record_id':row['record_id'],'error':'AMBIGUOUS_CACHED_ANALYSES'})
            candidates=[]
            try:
                if a is None:
                    candidates=catalog.retrieve(row['title_original'],limit=8)
                    request={'record_id':row['record_id'],'source_hash':row['source_hash'],'title_original':row['title_original'],
                             'prompt':PROMPT,'method':VERSION,'action_candidates':candidates}
                    a=provider.analyze(request)
                if a is not None:
                    validate_analysis(row,a,catalog)
                    if provider.mode!='cache':new_rows+=store.exact('v3_analyses',{'id':key},{'source_hash':row['source_hash'],'provider':provider.identity,'method':VERSION,
                        'assets':contract['assets'],'prompt_hash':contract['prompt_hash'],'analysis':a})
            except (ValueError,KeyError,TypeError,subprocess.SubprocessError,OSError) as exc:
                errors.append({'record_id':row['record_id'],'error':type(exc).__name__+': '+str(exc)[:180]});a=None
            if a is None:
                requests.append({'record_id':row['record_id'],'source_hash':row['source_hash'],'title_original':row['title_original'],
                    'prompt':PROMPT,'method':VERSION,'action_candidates':candidates})
            result=decide(row,a,catalog,policy,owners.get((row['record_id'],row['source_hash'])))
            results.append(result)
            if a is not None or result['human_confirmed']:
                new_rows+=store.exact('v3_results',{'run_id':run_id,'record_id':row['record_id']},result)
            store.db.commit()
        out=Path(out_dir)/run_id;out.mkdir(parents=True,exist_ok=True)
        attempt=Path(tempfile.mkdtemp(prefix='attempt_',dir=out))
        write_jsonl(attempt/'inputs.jsonl',input_rows)
        write_jsonl(attempt/'results.jsonl',results);write_jsonl(attempt/'semantic_requests.jsonl',requests);write_jsonl(attempt/'errors.jsonl',errors)
        headers=['record_id','title_original','decision','subject_type','sold_form','understanding_status','operating_status','reason_code','action_sku','reference_relation','reference_coverage','reason']
        with (attempt/'results.csv').open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=headers);writer.writeheader()
            for r in results:
                ref=r.get('reference') or {};a=r.get('semantic') or {}
                writer.writerow({**{k:r[k] for k in headers if k in r},'action_sku':ref.get('sku',''),'reference_relation':ref.get('relation',''),
                    'subject_type':a.get('subject_type',''),'sold_form':a.get('form',''),'reference_coverage':a.get('coverage','')})
        from collections import Counter
        summary={'run_id':run_id,'records':len(rows),'decisions':{s:sum(r['decision']==s for r in results) for s in ['保留','观察','用不到']},
                 'understanding':dict(Counter(r['understanding_status'] for r in results)),
                 'semantic_completed':len(rows)-len(requests),'semantic_pending':len(requests),'provider_calls':provider.calls,'reused_analyses':reused,
                 'new_data_rows':new_rows,'errors':len(errors),'accuracy':None,'integrity':store.check(),'output':str(attempt),'parent_run':parent_run}
        (attempt/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        return summary
    finally:store.close()
