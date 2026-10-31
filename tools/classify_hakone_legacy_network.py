"""Locate complete surviving legacy road components in the current save."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.ndimage import label,find_objects,binary_dilation
from repair_hakone_surface_ownership import load_grid,sampled

def classify(a):
    d=load_grid(a.plan/'network.npz');x0,z0,x1,z1=map(int,d['bounds']);old=load_grid(a.gis.parent/'world_rebuild_r20/transit/civil/road_contract.npz')
    ox,oz=map(int,old['origin']);old['bounds']=[ox,oz,ox+old['mask'].shape[1]-1,oz+old['mask'].shape[0]-1]
    remaining=np.zeros(d['walk'].shape,bool);level=np.full(remaining.shape,-32768,np.int16)
    mats={'minecraft:black_concrete','minecraft:white_concrete','minecraft:gray_concrete','minecraft:yellow_concrete','projectseele:road_asphalt_slab','projectseele:road_marking_slab'}
    for f in sorted((a.source/'source').glob('*.npz')):
        rx,rz=map(int,f.stem.split('.')[1:])
        if rx*512>x1 or rx*512+511<x0 or rz*512>z1 or rz*512+511<z0:continue
        with np.load(f)as v:co,bs,names=v['coordinates'],v['blocks'],[str(s).split('[')[0]for s in v['palette']]
        paving=np.array([s in mats for s in names])
        for(cx,cz),b in zip(co,bs):
            X,Z=int(cx)*16,int(cz)*16
            if not(x0<=X<=x1 and z0<=Z<=z1):continue
            zz,xx=np.mgrid[Z:Z+16,X:X+16];area=np.s_[Z-z0:Z-z0+16,X-x0:X-x0+16]
            mask=sampled(old,'mask',xx,zz).astype(bool)&~d['held'][area]&~d['core'][area]
            h=(sampled(old,'height2',xx,zz,30000)-1)//2;mask&=(h>=-125)&(h<=310)
            if not mask.any():continue
            h=np.clip(h,-125,310);z,x=np.mgrid[:16,:16];hit=np.zeros((16,16),bool);ys=h.copy()
            for dy in(-2,-1,0,1,2):
                yes=mask&paving[b[h+128+dy,z,x]];hit|=yes;ys[yes]=h[yes]+dy
            level[area]=ys;remaining[area]=hit
        print('Classified legacy network',f.name,flush=True)
    remaining&=~binary_dilation(d['walk'],iterations=2)
    groups,n=label(remaining,np.ones((3,3),int));sizes=np.bincount(groups.ravel());components=[]
    for i,s in enumerate(find_objects(groups),1):
        if s is None:continue
        components.append(dict(id=i,columns=int(sizes[i]),bounds=[s[1].start+x0,s[0].start+z0,s[1].stop+x0-1,s[0].stop+z0-1]))
    np.savez_compressed(a.out/'legacy-components.npz',bounds=d['bounds'],remaining=remaining,level=level,groups=groups)
    (a.out/'legacy-components.json').write_text(json.dumps(sorted(components,key=lambda r:-r['columns']),indent=2),'utf8')
    print('Surviving legacy road columns',int(remaining.sum()),'components',n,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('source','plan','gis','out'):p.add_argument('--'+n,type=Path,required=True)
    classify(p.parse_args())
