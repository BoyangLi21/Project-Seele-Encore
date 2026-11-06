"""Apply a verified layered-path declaration change without touching a world."""
import argparse,shutil
from pathlib import Path
import numpy as np
from map_pipeline.delivery_check import read,write


def apply(a):
    patch=read(a.patch);evidence=read(a.evidence)
    if Path(patch['authority'])!=a.authority or not patch['exact_before_required']:
        raise ValueError('Declaration patch belongs to a different authority')
    if evidence['errors']or evidence['operational_transfer_breaks']or evidence['north_pocket_trap']:
        raise ValueError('Physical continuity evidence incomplete')
    if patch['terrain_changes']or patch['entity_changes']:
        raise ValueError('This command cannot apply physical edits')
    for p in evidence['paths']:
        if p['forward']['kind']!='strict_static_clear'or p['reverse']['kind']!='strict_static_clear':
            raise ValueError('A replacement path is not verified in both directions')
    with np.load(a.authority/'network.npz')as f:d={k:f[k]for k in f.files}
    old={k:v.copy()for k,v in d.items()};x,z,_,_=map(int,d['bounds'])
    changed=set()
    for row in patch['headroom_flag_retire']:
        px,pz=row['cell'];j,i=pz-z,px-x
        if (px,pz)in changed:raise ValueError('Duplicate retirement')
        for k,v in row['before'].items():
            if int(d[k][j,i])!=v:raise ValueError('Declaration precondition differs')
        if row['after']!=dict(walk=0,grade2=row['before']['grade2'],road=0):
            raise ValueError('Only obsolete pedestrian declaration can be retired')
        d['walk'][j,i]=False;changed.add((px,pz))
    if len(changed)!=patch['retire_count']:raise ValueError('Retirement count differs')
    for row in patch['retained_north_walk']:
        px,pz=row['cell']
        for k,v in row['unchanged'].items():
            if int(d[k][pz-z,px-x])!=v:raise ValueError('Retained ground path changed')
    for k in d:
        if k!='walk'and not np.array_equal(d[k],old[k]):raise ValueError('Nonwalk field changed')
    if np.count_nonzero(d['walk']!=old['walk'])!=len(changed):raise ValueError('Walk changes outside declared scope')
    shutil.copytree(a.authority,a.out);np.savez_compressed(a.out/'network.npz',**d)
    write(a.out/'layered-walk-replacement.json',dict(patch=str(a.patch),evidence=str(a.evidence),previous=str(a.authority),nodes=patch['nodes'],edges=patch['edges'],paths=patch['paths'],retired_columns=sorted(changed),retained_north_columns=[q['cell']for q in patch['retained_north_walk']],world_written=False))
    write(a.out/'declaration-update.json',dict(status='applied',retired_columns=len(changed),existing_ground_and_road_exact=True,physical_geometry_changed=False,world_written=False))
    print('Applied',len(changed),'obsolete pedestrian declaration retirements; ground, road and world unchanged.')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in('authority','patch','evidence','out'):p.add_argument('--'+key,type=Path,required=True)
    apply(p.parse_args())
