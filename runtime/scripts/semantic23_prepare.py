"""Freeze V2.3 scope and a verified backup of the shared learning database."""
import json, sqlite3, sys, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import pipeline as p
from semantic22_prepare import table_digest, DB
OLD=ROOT/'outputs/action_semantic_v22_20261022'
OUT=ROOT/'outputs/action_semantic_v23_20261022'
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'protected_before.json').exists():
        print('Frozen baseline already exists');return
    rows=p.read_jsonl(OLD/'final_candidate/results.jsonl')
    targets=[r for r in rows if r['status'] in ('RULE_COVERAGE_GAP','FEATURE_TOO_BROAD')]
    assert len(targets)==2992
    files=json.loads((OLD/'protected_before.json').read_text(encoding='utf8'))['files']
    for path,h in files.items():assert p.filehash(path)==h, path
    for f in list(OLD.rglob('*'))+[ROOT/'scripts/semantic22.py',ROOT/'rules/action_semantic22_rules.tsv']:
        if f.is_file() and f.suffix!='.sqlite3':files[str(f)]=p.filehash(f)
    c=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True)
    backup=OUT/'learning_before_semantic23.sqlite3'
    b=sqlite3.connect(backup);c.backup(b);b.close()
    tables=[r[0] for r in c.execute("select name from sqlite_master where type='table'") if not r[0].startswith('sqlite_')]
    hashes={t:table_digest(c,t) for t in tables};c.close()
    restored=OUT/'restore_validation.sqlite3';shutil.copy2(backup,restored)
    rc=sqlite3.connect(restored.as_uri()+'?mode=ro',uri=True)
    integrity=rc.execute('pragma integrity_check').fetchone()[0];fk=rc.execute('pragma foreign_key_check').fetchall();rc.close()
    assert integrity=='ok' and not fk and p.filehash(restored)==p.filehash(backup)
    p.immutable(OUT/'backup_restore_check.json',{'integrity':integrity,'foreign_keys':0,'copy_verified':True,'sha256':p.filehash(backup)})
    restored.unlink()
    p.immutable(OUT/'targets_before.jsonl',targets,jsonl=True)
    p.immutable(OUT/'skill_before.txt',{'text':(ROOT/'skills/action-selection/SKILL.md').read_text(encoding='utf8')})
    p.immutable(OUT/'protected_before.json',{'files':files,'tables':hashes,'backup':str(backup),'backup_sha256':p.filehash(backup)})
    print(json.dumps({'targets':2992,'frozen_other_rows':7045,'protected_files':len(files),'protected_tables':len(hashes),'backup_restore':'PASS'}))
if __name__=='__main__':main()
