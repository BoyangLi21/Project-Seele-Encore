"""Measure complete commissioned road widths in an immutable saved snapshot."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.ndimage import label
from repair_hakone_surface_ownership import load_grid,sampled
from plan_hakone_main_districts import ROAD_MATERIALS
from plan_ashi_landscape_r54 import SOIL
from query_blocks import AIR

def measure(a):
    p=load_grid(a.plan/'network.npz');x0,z0,x1,z1=map(int,p['bounds']);shape=p['walk'].shape
    floor=np.full(shape,-32768,np.int16);soil=np.full(shape,-32768,np.int16);blocked=np.zeros(shape,bool);full=np.zeros(shape,bool)
    yy=np.arange(-128,320)[:,None,None];report=[]
    for file in sorted((a.source/'source').glob('*.npz')):
        rx,rz=map(int,file.stem.split('.')[1:])
        left,top=max(x0,rx*512),max(z0,rz*512);right,bottom=min(x1,rx*512+511),min(z1,rz*512+511)
        if left>right or top>bottom or not p['walk'][top-z0:bottom-z0+1,left-x0:right-x0+1].any():continue
        with np.load(file)as d:co,b,names=d['coordinates'],d['blocks'],[str(s).split('[')[0]for s in d['palette']]
        pavement=np.array([s in ROAD_MATERIALS for s in names]);natural=np.array([s in SOIL for s in names]);empty=np.array([s in AIR|{'minecraft:light','minecraft:grass','minecraft:tall_grass','minecraft:fern'}for s in names])
        for (cx,cz),v in zip(co,b):
            X,Z=int(cx)*16,int(cz)*16
            if not(x0<=X<=x1 and z0<=Z<=z1):continue
            ar=np.s_[Z-z0:Z-z0+16,X-x0:X-x0+16];full[ar]=True
            h=(p['grade2'][ar]+1)//2;z,x=np.mgrid[:16,:16]
            mask=p['walk'][ar]
            if not mask.any():continue
            found=pavement[v]&empty[np.roll(v,-1,axis=0)]&empty[np.roll(v,-2,axis=0)]&(abs(yy-h)<=8)
            delta=np.where(found,abs(yy-h),999);j=delta.argmin(0);y=j-128
            floor[ar]=np.where(delta.min(0)<999,y,-32768)
            soil[ar]=np.where(natural[v],yy,-129).max(0)
            blocked[ar]=~empty[v[h+129,z,x]]|~empty[v[h+130,z,x]]
        print('Measured road widths',file.name,flush=True)
    missing=p['walk']&full&(floor==-32768)
    groups,n=label(missing,np.ones((3,3),int));sizes=np.bincount(groups.ravel())
    # Report all components, not a sample-only acceptance list.
    for i in np.flatnonzero(sizes[1:])+1:
        zs,xs=np.nonzero(groups==i);report.append(dict(columns=int(sizes[i]),bounds=[int(xs.min()+x0),int(zs.min()+z0),int(xs.max()+x0),int(zs.max()+z0)]))
    np.savez_compressed(a.plan/'before-measured.npz',bounds=p['bounds'],floor=floor,soil=soil,blocked=blocked,full=full,missing=missing)
    out=dict(road_columns=int((p['walk']&full).sum()),missing_pavement_columns=int(missing.sum()),blocked_at_designed_floor=int((p['walk']&full&blocked).sum()),components=sorted(report,key=lambda r:-r['columns']))
    (a.plan/'before-findings.json').write_text(json.dumps(out,indent=2),'utf8')
    print(json.dumps({k:v for k,v in out.items()if k!='components'}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('plan','source'):p.add_argument('--'+n,type=Path,required=True)
    measure(p.parse_args())
