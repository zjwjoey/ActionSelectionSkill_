"""Developer packaging step; never run automatically to accept changed assets."""
import hashlib,json,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def main():
    old=json.loads((ROOT/'releases/v0.3/manifest.json').read_text(encoding='utf-8'))
    frozen={p:v for p,v in old['files'].items() if p not in {'SKILL.md','scripts/share_tool.py'}}
    for rel,item in frozen.items():
        if hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()!=item['sha256']:raise ValueError('FROZEN_ASSET_CHANGED:'+rel)
    paths=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=ROOT).decode('utf-8').split('\0')
    files={}
    for rel in sorted(set(paths)-{'','manifest.json'}):
        p=ROOT/rel
        if p.is_file():files[rel]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
    result={k:v for k,v in old.items() if k!='files'}
    result.update(package_version='v3.3-data-learning-experimental',boundary_method='V3.3 explicit pairwise ranker experiment; V3.1 remains default',
        independent_selection_accuracy=None,frozen_asset_files_verified=len(frozen),files=files)
    (ROOT/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'files':len(files),'frozen_files_verified':len(frozen)}))
if __name__=='__main__':main()
