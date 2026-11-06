"""Join installed north and south grade authorities inside a fresh FULL capture."""
import argparse,json,shutil
from pathlib import Path
import numpy as np


def prepare(a):
    capture=json.loads((a.source/'capture.json').read_text('utf8'))
    if capture['unavailable_chunks']:raise ValueError('Airport connection needs complete saved source terrain')
    with np.load(a.source/'measured.npz')as f:m={k:f[k]for k in f.files}
    x,z,X,Z=map(int,m['bounds']);shape=m['top'].shape
    a.out.mkdir(parents=True,exist_ok=False)
    d={k:np.zeros(shape,bool)for k in ('road','walk','core','cityroad','citypaved','retired_fragments','held',
                                     'tunnel','marking','crossing','conflicting_terrain_constraints','regraded_walk')}
    d.update(bounds=m['bounds'],old_ground=m['top'],ground=m['top'],grade2=np.zeros(shape,np.int16),previous_grade2=np.zeros(shape,np.int16))
    with np.load(a.north/'network.npz')as f:
        bx,bz,bX,bZ=map(int,f['bounds']);top=max(z,bz);bottom=min(Z,bZ)
        if not bx<=x<=X<=bX or top>bottom:raise ValueError('North authority does not cover this source')
        for k in d:
            if k in f.files and k not in ('bounds','old_ground','ground'):
                d[k][top-z:bottom-z+1]=f[k][top-bz:bottom-bz+1,x-bx:X-bx+1]
    with np.load(a.south/'valley-surface.npz')as f,np.load(a.south/'final-grading.npz')as g:
        bx,bz,bX,bZ=map(int,f['bounds'])
        if not (bx<=x<=X<=bX and bz<=z<=Z<=bZ):raise ValueError('South authority does not cover this source')
        area=np.s_[z-bz:Z-bz+1,x-bx:X-bx+1];south=np.indices(shape)[0]+z>=a.south_z_min
        for k in ('road','walk'):d[k][south]=f[k][area][south]
        d['grade2'][south]=g['grade2'][area][south]
    np.savez_compressed(a.out/'network.npz',**d)
    for file in a.north.glob('*.json'):shutil.copy2(file,a.out/file.name)
    catalog=json.loads((a.out/'catalog.json').read_text('utf8'))
    for i,r in enumerate(json.loads((a.south/'regraded-layout.json').read_text('utf8'))['buildings']):
        x,y,z,X,Y,Z=r['bounds']
        catalog.append(dict(id=f'south-port-building-{i}',occupied_bounds=[min(x,X),min(y,Y),min(z,Z),max(x,X),max(y,Y),max(z,Z)]))
    (a.out/'catalog.json').write_text(json.dumps(catalog,indent=2),'utf8')
    (a.out/'authority.json').write_text(json.dumps(dict(source=str(a.source),north=str(a.north),south=str(a.south),
        south_z_min=a.south_z_min,world_written=False),indent=2),'utf8')
    print(a.out,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for k in ('source','north','south','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--south-z-min',type=int,default=1664)
    prepare(p.parse_args())
