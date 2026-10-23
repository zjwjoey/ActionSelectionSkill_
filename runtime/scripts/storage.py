"""One independent learning database for every ActionSelectionSkill module."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def encode(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, default=str)


@contextmanager
def connection(root):
    path = Path(root) / "learning_data" / "action_selection.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path, timeout=20)
    c.execute("PRAGMA foreign_keys=ON")
    c.executescript("""
        CREATE TABLE IF NOT EXISTS snapshots(snapshot_id TEXT PRIMARY KEY, manifest TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS source_rows(source_row_id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL REFERENCES snapshots, sku TEXT, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS products(snapshot_id TEXT NOT NULL REFERENCES snapshots, sku TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(snapshot_id,sku));
        CREATE TABLE IF NOT EXISTS batches(batch_id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL REFERENCES snapshots, manifest TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sample_members(batch_id TEXT NOT NULL REFERENCES batches, sku TEXT NOT NULL, ordinal INTEGER NOT NULL, payload TEXT NOT NULL, blind_input TEXT NOT NULL, PRIMARY KEY(batch_id,sku));
        CREATE TABLE IF NOT EXISTS rule_versions(version TEXT PRIMARY KEY, content_hash TEXT NOT NULL, definition TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS analyses(seq INTEGER PRIMARY KEY AUTOINCREMENT, batch_id TEXT NOT NULL, sku TEXT NOT NULL, rules_version TEXT NOT NULL REFERENCES rule_versions, annotation_hash TEXT NOT NULL, payload TEXT NOT NULL, FOREIGN KEY(batch_id,sku) REFERENCES sample_members, UNIQUE(batch_id,sku,rules_version,annotation_hash));
        CREATE TABLE IF NOT EXISTS feedback(seq INTEGER PRIMARY KEY AUTOINCREMENT, batch_id TEXT NOT NULL, sku TEXT NOT NULL, feedback_hash TEXT NOT NULL, payload TEXT NOT NULL, FOREIGN KEY(batch_id,sku) REFERENCES sample_members, UNIQUE(batch_id,sku,feedback_hash));
    """)
    try:
        yield c
        c.commit()
    except BaseException:
        c.rollback()
        raise
    finally:
        c.close()


def append_exact(c, table, key, key_value, payload, columns=()):
    old = c.execute(f"SELECT {','.join(columns)} FROM {table} WHERE {key}=?", (key_value,)).fetchone()
    if old:
        if tuple(old) != tuple(payload):
            raise ValueError("IMMUTABLE_DATABASE_RECORD_CONFLICT:" + table + ":" + str(key_value))
        return
    c.execute(f"INSERT INTO {table}({key},{','.join(columns)}) VALUES({','.join('?' for _ in range(1+len(columns)))})", (key_value, *payload))


def register_snapshot(root, manifest, rows, archives, products):
    with connection(root) as c:
        sid = manifest["snapshot_id"]
        append_exact(c, "snapshots", "snapshot_id", sid, (encode(manifest),), ("manifest",))
        for x in rows + archives:
            append_exact(c, "source_rows", "source_row_id", x["source_row_id"], (sid, x["sku"], encode(x)), ("snapshot_id", "sku", "payload"))
        for x in products:
            old = c.execute("SELECT payload FROM products WHERE snapshot_id=? AND sku=?", (sid,x["sku"])).fetchone()
            if old and old[0] != encode(x):
                raise ValueError("PRODUCT_PROJECTION_CONFLICT")
            if not old:
                c.execute("INSERT INTO products VALUES(?,?,?)", (sid,x["sku"],encode(x)))


def load_products(root, sid):
    with connection(root) as c:
        return [json.loads(x[0]) for x in c.execute("SELECT payload FROM products WHERE snapshot_id=? ORDER BY sku", (sid,))]


def register_batch(root, manifest, samples, blind):
    inputs = {x["sku"]: x for x in blind}
    with connection(root) as c:
        bid = manifest["sample_id"]
        append_exact(c, "batches", "batch_id", bid, (manifest["snapshot_id"], encode(manifest)), ("snapshot_id", "manifest"))
        for i,x in enumerate(samples):
            old = c.execute("SELECT payload,blind_input,ordinal FROM sample_members WHERE batch_id=? AND sku=?",(bid,x["sku"])).fetchone()
            values = (encode(x), encode(inputs[x["sku"]]), i)
            if old and tuple(old) != values:
                raise ValueError("SAMPLE_MEMBERSHIP_CONFLICT")
            if not old:
                c.execute("INSERT INTO sample_members(batch_id,sku,payload,blind_input,ordinal) VALUES(?,?,?,?,?)", (bid,x["sku"],*values))


def members(root, batch, blind=False):
    with connection(root) as c:
        return [json.loads(x[0]) for x in c.execute("SELECT " + ("blind_input" if blind else "payload") + " FROM sample_members WHERE batch_id=? ORDER BY ordinal", (batch,))]


def state(root, batch):
    with connection(root) as c:
        proposals = {json.loads(r[0])["sku"]: json.loads(r[0]) for r in c.execute("SELECT payload FROM analyses WHERE batch_id=? ORDER BY seq", (batch,))}
        feedback = {json.loads(r[0])["sku"]: json.loads(r[0]) for r in c.execute("SELECT payload FROM feedback WHERE batch_id=? ORDER BY seq", (batch,))}
    return proposals, feedback


def register_rule(root, version, hash_value, definitions):
    with connection(root) as c:
        append_exact(c, "rule_versions", "version", version, (hash_value,encode(definitions)), ("content_hash","definition"))


def put_analyses(root, batch, rows):
    with connection(root) as c:
        for x in rows:
            old = c.execute("SELECT payload FROM analyses WHERE batch_id=? AND sku=? AND rules_version=? AND annotation_hash=?", (batch,x["sku"],x["rules_version"],x["annotation_hash"])).fetchone()
            if old and old[0] != encode(x):
                raise ValueError("ANALYSIS_PAYLOAD_CONFLICT")
            if not old:
                c.execute("INSERT INTO analyses(batch_id,sku,rules_version,annotation_hash,payload) VALUES(?,?,?,?,?)", (batch,x["sku"],x["rules_version"],x["annotation_hash"],encode(x)))


def put_feedback(root, batch, rows, digest):
    with connection(root) as c:
        for x in rows:
            c.execute("INSERT OR IGNORE INTO feedback(batch_id,sku,feedback_hash,payload) VALUES(?,?,?,?)", (batch,x["sku"],digest(x),encode(x)))


def history(root,batch):
    with connection(root) as c:
        return [json.loads(x[0]) for x in c.execute("SELECT payload FROM analyses WHERE batch_id=? ORDER BY seq", (batch,))]


def effective_state(root,batch):
    """Human corrections are a separate overlay; original proposals survive."""
    proposals,feedback=state(root,batch)
    result={}
    for sku,x in proposals.items():
        fb=feedback.get(sku,{})
        bound=bool(fb) and fb.get('expected_annotation_hash')==x['annotation_hash']
        result[sku]={**x,**(fb.get('corrections',{}) if bound else {}),
                     'review_status':fb.get('review_status',x['review_status']) if bound else x['review_status'],
                     'human_confirmed':bound and fb.get('review_status')=='已确认',
                     'human_feedback_binding':'CURRENT' if bound else ('STALE' if fb else 'NONE')}
    return result
