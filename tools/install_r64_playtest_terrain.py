"""Install an already verified natural-surface delta on a stopped playtest copy."""
import argparse
import filecmp
import json
import os
import shutil
from pathlib import Path
from install_r53_carrier_trays import stopped_world
from write_deep_cells import REGION

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('source','world','staged','backup'):p.add_argument('--'+arg,required=True,type=Path)
    p.add_argument('--region',nargs=2,type=int)
    a=p.parse_args()
    if a.source.resolve()==a.world.resolve() or not (a.world/'level.dat').is_file():
        p.error('Supply a separate cold world copy with its level.dat')
    a.backup.mkdir(parents=True,exist_ok=True)
    lock=a.world/'session.lock'
    if not lock.exists():
        with lock.open('xb') as f:f.write(bytes.fromhex('e29883'))
    paths=[a.staged/('r.%d.%d.json'%tuple(a.region))] if a.region else sorted(a.staged.glob('r.*.*.json'))
    with stopped_world(a.world):
        for f in paths:
            tag=f.stem;data=json.loads(f.read_bytes())
            if not data['cells']:continue
            src=a.source/REGION/(tag+'.mca');dest=a.world/REGION/src.name
            staged=a.staged/src.name; backup=a.backup/src.name;done=a.backup/(tag+'.installed')
            if done.exists():continue
            if backup.exists() and not staged.exists():raise ValueError('Installation requires readback: '+tag)
            if not filecmp.cmp(src,dest,shallow=False):
                raise ValueError('Cold baseline changed; nothing in this region was replaced: '+tag)
            if not backup.exists():
                try:os.link(dest,backup)
                except OSError:shutil.copy2(dest,backup)
            # Link the validated product to a temporary path on the same volume before rename.
            temp=dest.with_name(dest.name+'.terrain-installing')
            if temp.exists():raise ValueError('Unfinished installation: '+str(temp))
            try:os.link(staged,temp)
            except OSError:shutil.copy2(staged,temp)
            os.replace(temp,dest)
            if not filecmp.cmp(staged,dest,shallow=False):raise ValueError('Readback: '+tag)
            done.write_text(str(data['cells']))
            print(tag,data['cells'],len(data['chunks']),flush=True)
if __name__=='__main__':main()
