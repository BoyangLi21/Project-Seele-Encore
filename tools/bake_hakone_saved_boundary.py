"""Bake the cold repair's measured outer blend into future terrain generation.

The surveyed core is unchanged. Its surrounding already-saved transition must
use the SAME measured old surface as the block patch; native noise minus a sea
offset is not a substitute for that source along a previously visited border.
"""
import argparse,gzip,json,struct
from pathlib import Path
import numpy as np
from repair_hakone_surface_ownership import load_grid
from prepare_hakone_main_terrain import sample_grid


def bake(a):
    a.out.mkdir(exist_ok=False)
    d=load_grid(a.atlas/'surface-atlas.npz');m=load_grid(a.source/'measured.npz');p=load_grid(a.proto/'measured.npz')
    x,z,X,Z=map(int,m['bounds']);xs=np.arange(x,X+1,2);zs=np.arange(z,Z+1,2);zz,xx=np.meshgrid(zs,xs,indexing='ij')
    top=m['top'][::2,::2].astype(float);known=m['full'][::2,::2].astype(bool)
    use=p['full'][::2,::2].astype(bool)&~known;top[use]=p['top'][::2,::2][use];known|=use
    # Only unsaved gaps outside the surveyed DEM need interpolation. Their
    # neighbour datum is a continuation of existing geography, not new objects.
    interpolated=top.copy();columns=np.arange(len(xs));rows=np.arange(len(zs));valid_rows=[]
    for iz in range(len(zs)):
        good=np.flatnonzero(known[iz])
        if len(good):interpolated[iz]=np.interp(columns,good,top[iz,good]);valid_rows.append(iz)
    for ix in range(len(xs)):interpolated[:,ix]=np.interp(rows,valid_rows,interpolated[valid_rows,ix])
    interpolated[known]=top[known]
    distance=np.maximum.reduce([d['x'][0]-xx,xx-d['x'][-1],d['z'][0]-zz,zz-d['z'][-1],np.zeros(xx.shape,int)])
    t=np.clip(distance/256,0,1);t=t*t*(3-2*t)
    h=np.rint(sample_grid(d,'height_y',xx,zz)*(1-t)+interpolated*t).astype(np.int16)
    water=sample_grid(d,'water',xx,zz,True).astype(np.int16);water[distance>0]=-32768
    # The original repair leaves columns beyond the finite blend untouched.
    h[(distance>=256)&known]=top[(distance>=256)&known]
    with gzip.open(a.out/'hakone_surface.bin.gz','wb')as f:
        f.write(struct.pack('>6i',0x484B3535,int(xs[0]),int(zs[0]),2,len(xs),len(zs)))
        f.write((h*16).astype('>i2').tobytes());f.write(water.astype('>i2').tobytes())
    if h.size>10000000:raise ValueError('Field exceeds native bounded resource limit')
    inner=distance==0
    if not np.array_equal(h[inner],np.rint(sample_grid(d,'height_y',xx[inner],zz[inner]))):raise ValueError('Surveyed field changed')
    np.savez_compressed(a.out/'surface-atlas.npz',x=xs,z=zs,height_y=h,water=water)
    (a.out/'boundary.json').write_text(json.dumps(dict(source=str(a.source),proto=str(a.proto),core=str(a.atlas),bounds=[int(xs[0]),int(zs[0]),int(xs[-1]),int(zs[-1])],preserved_core_pixels=int(inner.sum()),measured_outer_pixels=int((known&~inner).sum()),runtime_checks=False),indent=2),'utf8')
    print('Baked saved terrain boundary',h.shape,'core preserved',int(inner.sum()),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('atlas','source','proto','out'):p.add_argument('--'+n,type=Path,required=True)
    bake(p.parse_args())
