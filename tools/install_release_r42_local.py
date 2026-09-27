"""Install separate R42 entries; never replace the owner's played R41 save."""
from pathlib import Path
import json,hashlib,shutil
from release_combat_r36 import guard
import build_server_ready_pack as base

ROOT=base.ROOT;RELEASE=ROOT/'artifacts/server-ready-r42';STAGE=RELEASE/'stage'


def main():
    guard();release=json.loads((RELEASE/'RELEASE.json').read_text('utf8'));assert release['server_validation']['passed']
    baseline=json.loads((ROOT/'artifacts/rebuild_r42/baseline.json').read_text('utf8'));source=Path(baseline['source'])
    for name,digest in baseline['files'].items():
        p=source/name;assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==digest,('Owner source changed since freeze',name)
    prior=json.loads((ROOT/'artifacts/server-ready-r41/installed_local.json').read_text('utf8'));original=Path(prior['pcl'])
    target=original.parent/'Project SEELE R42';dev=ROOT/'run/saves/SEELE_R42_WORLD'
    assert original.name=='Project SEELE R41' and not target.exists() and not dev.exists(),'Do not overwrite an installed instance or world'
    base.copy_tree(STAGE/'client',target);base.copy_tree(STAGE/'world',target/'saves/SEELE_R42_WORLD',ignore_world_locks=True)
    meta=json.loads((original/'Project SEELE R41.json').read_text('utf8'));meta['id']='Project SEELE R42'
    (target/'Project SEELE R42.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),'utf8')
    shutil.copy2(original/'Project SEELE R41.jar',target/'Project SEELE R42.jar')
    base.copy_tree(STAGE/'world',dev,ignore_world_locks=True)
    (dev/'r42_ready.json').write_text(json.dumps(dict(revision=42,source=str(source),original_progress=True),ensure_ascii=False,indent=2),'utf8')
    for folder in (dev,target/'saves/SEELE_R42_WORLD'):
        assert base.sha256(folder/'nerv_routes_r24.json.gz')==release['native']['navigation']['sha256']
    (RELEASE/'installed_local.json').write_text(json.dumps(dict(pcl=str(target),development_world=str(dev),original_world_retained=str(source),original_instance_retained=str(original),accounts_copied=False),ensure_ascii=False,indent=2),'utf8')
    print('Installed independent R42 client and world; played R41 unchanged',flush=True)


if __name__=='__main__':main()
