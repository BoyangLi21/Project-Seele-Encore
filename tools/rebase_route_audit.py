"""Reuse a route audit only when an installed patch cannot touch its samples."""
import argparse,shutil
from pathlib import Path
import numpy as np
from map_pipeline.delivery_check import read,write


def rebase(a):
    audit=read(a.prior/'audit.json');old=Path(audit['authority'])
    receipt=read(a.installation);manifest=read(a.candidate/'manifest.json')
    if receipt['status']!='installed'or not receipt['changed_section_readback']or receipt['cells']!=manifest['cells']:
        raise ValueError('Patch installation/readback is incomplete')
    if str(a.candidate)not in receipt['candidates']:
        raise ValueError('Receipt refers to a different patch')
    for name in('network.npz','catalog.json'):
        if (old/name).read_bytes()!=(a.authority/name).read_bytes():
            raise ValueError('A full route audit is required for changed route declarations')
    with np.load(a.prior/'actual-routes.npz')as f:
        layers={(int(x),int(z)):((int(g)+1)//2,4 if road else 2)for x,z,g,road in zip(f['x'],f['z'],f['grade2'],f['road'])}
    checked=0;overlaps=[]
    for delta in(a.candidate/'delta').glob('*.npz'):
        with np.load(delta)as f:
            for k,(cx,cz)in enumerate(f['coordinates']):
                lo,hi=f['ranges'][k:k+2]
                for q in f['indices'][lo:hi]:
                    q=int(q);x,y,z=int(cx)*16+q%16,q//256-128,int(cz)*16+(q%256)//16
                    checked+=1
                    if(x,z)in layers:
                        floor,depth=layers[x,z]
                        if floor<=y<=floor+depth:overlaps.append([x,y,z])
    if checked!=receipt['cells']or overlaps:
        raise ValueError('A current measurement is required: changed audit samples '+str(overlaps[:4]))
    a.out.mkdir(exist_ok=False)
    for name in('actual-routes.npz','destinations.json','obstacle-examples.json'):
        (a.out/name).hardlink_to(a.prior/name)
    audit.update(authority=str(a.authority),reused_measurement=str(a.prior),rebased_after_installation=str(a.installation),sample_disjoint_patch_cells=checked,route_declarations_exact=True,new_actual_world_scan=False)
    write(a.out/'audit.json',audit)
    write(a.out/'rebase-proof.json',dict(passed=True,prior=str(a.prior),installation=str(a.installation),checked_changes=checked,changed_observed_voxels=0,network_and_catalog_exact=True,world_written=False))
    print('Route audit preserved across',checked,'disjoint installed cells; no audit sample changed.')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for k in('prior','authority','candidate','installation','out'):p.add_argument('--'+k,type=Path,required=True)
    rebase(p.parse_args())
