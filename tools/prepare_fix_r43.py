"""Freeze the latest played R42 before any code/runtime adoption."""
from pathlib import Path
import datetime,hashlib,json,shutil
import nbtlib
from release_combat_r36 import guard

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/repair_r43'


def main():
    guard();OUT.mkdir(exist_ok=True);manifest=OUT/'baseline.json'
    if manifest.exists():print('R43 baseline already frozen');return
    candidates=[ROOT/'run/saves/SEELE_R42_WORLD',Path.home()/'AppData/Roaming/.minecraft/versions/Project SEELE R42/saves/SEELE_R42_WORLD']
    source=max(candidates,key=lambda p:int(nbtlib.load(p/'level.dat')['Data']['LastPlayed']))
    backup=OUT/'source_world_backup';assert not backup.exists();shutil.copytree(source,backup)
    files={p.relative_to(source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
    assert all(hashlib.sha256((backup/k).read_bytes()).hexdigest()==v for k,v in files.items())
    runtime=OUT/'runtime_before';runtime.mkdir()
    names=['eva_body_r42.json','first_battle_r42.json','revision_r42.json']+[f'eva_gameplay_r42_{i}.json' for i in range(5)]
    for name in names:shutil.copy2(ROOT/'run/projectseele-local-maps'/name,runtime/name)
    data=nbtlib.load(source/'level.dat')['Data']
    manifest.write_text(json.dumps(dict(source=str(source),backup=str(backup),created=datetime.datetime.now().astimezone().isoformat(),
        last_played=int(data['LastPlayed']),position=list(map(float,data['Player']['Pos'])),files=files),ensure_ascii=False,indent=2),'utf8')
    print('Frozen',source,len(files),'files',flush=True)


if __name__=='__main__':main()
