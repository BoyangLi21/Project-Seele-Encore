"""Pin actual native classes, resources and explicit motion bundles before launch."""
from pathlib import Path
import hashlib,json,shutil

ROOT=Path(__file__).resolve().parents[1]
EPOCHS=ROOT/'artifacts/rebuild_r44/native_epochs'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def directory_snapshot(source):
    source=Path(source).resolve();rows={p.relative_to(source).as_posix():sha(p) for p in source.rglob('*') if p.is_file()}
    digest=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest();target=EPOCHS/digest
    if not target.exists():
        target.mkdir(parents=True);shutil.copytree(source,target/'files')
        actual={p.relative_to(target/'files').as_posix():sha(p) for p in (target/'files').rglob('*') if p.is_file()}
        assert rows==actual,'Compilation/resource files changed during snapshot'
        (target/'manifest.json').write_text(json.dumps(dict(source=str(source),sha256=digest,files=rows),indent=2),'utf8')
    return target/'files',digest

def freeze(spec,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);witness=[]
    entries=spec.get('environment',{}).get('MOD_CLASSES','').split(';');frozen=[]
    for entry in entries:
        if '%%' not in entry:frozen.append(entry);continue
        name,directory=entry.split('%%',1)
        if name!='projectseele':frozen.append(entry);continue
        target,digest=directory_snapshot(directory);frozen.append(name+'%%'+target.resolve().as_posix());witness.append(dict(source=directory,frozen=str(target),sha256=digest))
    if entries:spec['environment']['MOD_CLASSES']=';'.join(frozen)
    command=spec['command']
    for index,arg in enumerate(command):
        if not arg.startswith('-Dprojectseele.combatBundleDirectory='):continue
        source=Path(arg.split('=',1)[1]);manifest=json.loads((source/'combat_bundle_r44.json').read_text('utf8'))
        for name,digest in manifest['files'].items():assert sha(source/name)==digest,('Motion bundle changed',name)
        rows={name:sha(source/name) for name in [*manifest['files'],'combat_bundle_r44.json']}
        digest=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest();epoch=EPOCHS/digest;target=epoch/'files'
        if not target.exists():
            target.mkdir(parents=True)
            for name in rows:shutil.copy2(source/name,target/name)
            assert all(sha(target/name)==value for name,value in rows.items()),'Bundle changed during freezing'
            (epoch/'manifest.json').write_text(json.dumps(dict(source=str(source),sha256=digest,files=rows),indent=2),'utf8')
        command[index]='-Dprojectseele.combatBundleDirectory='+target.resolve().as_posix();witness.append(dict(bundle=manifest['bundle_id'],source=str(source),frozen=str(target),sha256=digest))
    (out/'runtime_witness.json').write_text(json.dumps(witness,ensure_ascii=False,indent=2),'utf8')
    return spec
