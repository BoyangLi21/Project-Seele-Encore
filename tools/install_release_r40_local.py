"""Install a new owner-local PCL R40 instance and a separate development world."""
from pathlib import Path
import json,hashlib,shutil
from release_combat_r36 import guard
import build_server_ready_pack as base

ROOT=base.ROOT;RELEASE=ROOT/'artifacts/server-ready-r40';STAGE=RELEASE/'stage'


def main():
    guard();published=json.loads((RELEASE/'RELEASE.json').read_text());assert published['server_validation']['passed']
    baseline=json.loads((ROOT/'artifacts/world_combat_r40/baseline.json').read_text());oldworld=Path(baseline['source'])
    for name,row in baseline['files'].items():
        path=oldworld/name
        assert path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256'],('Owner played or edited source since cold backup',name)
    original=oldworld.parent.parent;versions=original.parent;target=versions/'Project SEELE R40'
    assert original.name=='Project SEELE R39' and not target.exists(),'Do not overwrite another installed instance'
    base.copy_tree(STAGE/'client',target)
    base.copy_tree(STAGE/'world',target/'saves/SEELE_R31_WORLD',ignore_world_locks=True)
    meta=json.loads((original/'Project SEELE R39.json').read_text('utf8'))
    meta['id']='Project SEELE R40';(target/'Project SEELE R40.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),'utf8')
    shutil.copy2(original/'Project SEELE R39.jar',target/'Project SEELE R40.jar')
    dev=ROOT/'run/saves/SEELE_R40_WORLD';assert not dev.exists(),'Do not replace an existing development save'
    base.copy_tree(STAGE/'world',dev,ignore_world_locks=True)
    (dev/'r40_ready.json').write_text(json.dumps(dict(revision=40,source=str(oldworld),original_progress=True),ensure_ascii=False,indent=2),'utf8')
    (RELEASE/'installed_local.json').write_text(json.dumps(dict(pcl=str(target),development_world=str(dev),original_retained=str(original),accounts_copied=False),ensure_ascii=False,indent=2),'utf8')
    print('New PCL R40 instance installed; R39 retained',flush=True)


if __name__=='__main__':main()
