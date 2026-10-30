"""Versioned pair-label materialization and experiment model rollback.

Registry selections are sandbox experiment pointers, never production promotion.
"""
import collections,json,sqlite3,datetime
from pathlib import Path
from runtime.retail.pair_learning import digest,read,save,load_model,validate_label
from runtime.v3.workflow import filehash,write_jsonl

def validate_dataset(pairs):
    ids=set();splits={};groups={};bindings=set()
    for p in pairs:
        validate_label({**p,'evidence':p.get('feedback_evidence',p.get('evidence',{}))})
        if p['pair_id'] in ids:raise ValueError('DUPLICATE_PAIR')
        ids.add(p['pair_id']);sid=p['input_id'];g=p['isolation_group'];split=p['split']
        if sid in splits and splits[sid]!=split:raise ValueError('INPUT_SPLIT_LEAKAGE')
        if g in groups and groups[g]!=split:raise ValueError('FAMILY_SPLIT_LEAKAGE')
        splits[sid]=split;groups[g]=split;bindings.add(digest(p['feature_binding']))
    if len(bindings)!=1:raise ValueError('MIXED_FEATURE_BINDING')
    return dict(pairs=len(ids),products=len(splits),groups=len(groups))

def materialize(pairs_path,store_path,output):
    pairs=read(pairs_path);validate_dataset(pairs);by={p['pair_id']:p for p in pairs}
    if Path(output).exists():raise ValueError('DATASET_VERSION_EXISTS')
    db=sqlite3.connect(Path(store_path).resolve().as_uri()+'?mode=ro',uri=True)
    try:events=db.execute('SELECT id,pair_id,payload FROM pair_label_events ORDER BY rowid').fetchall()
    finally:db.close()
    applied=[]
    for event,pid,payload in events:
        row=json.loads(payload);validate_label(row)
        if digest(row)!=event or pid not in by:raise ValueError('FEEDBACK_EVENT_BINDING_INVALID')
        # Event binds immutable base pair, never prior materialized projection.
        base=next(p for p in pairs if p['pair_id']==pid)
        if row['pair_source_hash']!=digest(base):raise ValueError('FEEDBACK_SOURCE_CHANGED')
        projected={**base,**{k:row[k] for k in ['relation','scope','spec_relation','label_authority']},'feedback_event':event,'feedback_evidence':row.get('evidence',{})}
        by[pid]=projected;applied.append(event)
    rows=[by[p['pair_id']] for p in pairs];write_jsonl(Path(output),rows)
    receipt=dict(base_sha=filehash(Path(pairs_path)),new_sha=filehash(Path(output)),events=applied,created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),authorities=dict(collections.Counter(p['label_authority'] for p in rows)),training_filter='Only split=train is consumed by trainer; reviewing holdout makes that product exposed for future validation')
    save(str(output)+'.version.json',receipt);return receipt

class ModelRegistry:
    def __init__(self,path):
        Path(path).parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS model_events(seq INTEGER PRIMARY KEY,payload TEXT NOT NULL,event_hash TEXT UNIQUE NOT NULL)');self.db.commit()
    def append(self,event):
        h=digest(event);self.db.execute('INSERT OR IGNORE INTO model_events(payload,event_hash) VALUES(?,?)',(json.dumps(event),h));self.db.commit();return h
    def register(self,model_path):
        m=load_model(model_path)
        return self.append(dict(action='REGISTER',model_hash=m['model_hash'],path=str(Path(model_path).resolve()),file_sha=filehash(Path(model_path)),status=m['status'],dataset_hash=m['dataset_hash']))
    def select(self,model_hash,reason,allow_experimental=False):
        if not allow_experimental or not reason.strip():raise ValueError('EXPLICIT_EXPERIMENT_REASON_REQUIRED')
        rows=[json.loads(p) for (p,) in self.db.execute('SELECT payload FROM model_events ORDER BY seq')]
        found=next((r for r in rows if r['action']=='REGISTER' and r['model_hash']==model_hash),None)
        if not found or filehash(Path(found['path']))!=found['file_sha']:raise ValueError('REGISTERED_MODEL_MISSING_OR_CHANGED')
        return self.append(dict(action='SELECT_EXPERIMENT_ONLY',model_hash=model_hash,reason=reason,previous=self.current(),created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),production=False))
    def current(self):
        for (payload,h) in self.db.execute('SELECT payload,event_hash FROM model_events ORDER BY seq DESC'):
            row=json.loads(payload)
            if digest(row)!=h:raise ValueError('REGISTRY_EVENT_CHANGED')
            if row['action']=='SELECT_EXPERIMENT_ONLY':return row['model_hash']
        return None
    def close(self):self.db.close()
