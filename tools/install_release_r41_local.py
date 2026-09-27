"""Install separate R41 client/world entries without replacing the played R40."""
from pathlib import Path
import json,hashlib,shutil
from release_combat_r36 import guard
import build_server_ready_pack as base

ROOT=base.ROOT;RELEASE=ROOT/'artifacts/server-ready-r41';STAGE=RELEASE/'stage'


def main():
    guard();release=json.loads((RELEASE/'RELEASE.json').read_text('utf8'));assert release['server_validation']['passed']
    baseline=json.loads((ROOT/'artifacts/spatial_repair_r41/baseline.json').read_text('utf8'));source=Path(baseline['source'])
    for name,row in baseline['files'].items():
        p=source/name;assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'],('Owner source changed since freeze',name)
    prior=json.loads((ROOT/'artifacts/server-ready-r40/installed_local.json').read_text('utf8'));original=Path(prior['pcl'])
    target=original.parent/'Project SEELE R41';dev=ROOT/'run/saves/SEELE_R41_WORLD'
    assert original.name=='Project SEELE R40' and not target.exists() and not dev.exists(),'Do not overwrite an installed instance or world'
    base.copy_tree(STAGE/'client',target);base.copy_tree(STAGE/'world',target/'saves/SEELE_R41_WORLD',ignore_world_locks=True)
    meta=json.loads((original/'Project SEELE R40.json').read_text('utf8'));meta['id']='Project SEELE R41'
    (target/'Project SEELE R41.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),'utf8');shutil.copy2(original/'Project SEELE R40.jar',target/'Project SEELE R41.jar')
    base.copy_tree(STAGE/'world',dev,ignore_world_locks=True)
    (dev/'r41_ready.json').write_text(json.dumps(dict(revision=41,source=str(source),original_progress=True),ensure_ascii=False,indent=2),'utf8')
    (RELEASE/'installed_local.json').write_text(json.dumps(dict(pcl=str(target),development_world=str(dev),original_world_retained=str(source),original_instance_retained=str(original),accounts_copied=False),ensure_ascii=False,indent=2),'utf8')
    print('Installed independent R41 client and world; played R40 unchanged',flush=True)


if __name__=='__main__':main()
