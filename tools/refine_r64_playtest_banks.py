"""Tie remaining chunk-edge faces back into adjacent terrain and leave roads anchored."""
import argparse
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from scipy import ndimage as nd
from plan_r64_playtest_terrain import HALO,AREA,window,support,smooth,EXCLUDED

def refine(job):
    d,fp,rx,rz=job
    old=np.load(d/'landscape'/f'r.{rx}.{rz}.npz')
    x0,z0,h,k,_=window(d/'survey',rx,rz)
    _,_,after,_,_=window(d/'after',rx,rz)
    _,have,_=support(x0,z0,h.shape,fp)
    # The remaining faces include hollow land caps above the older ground, and
    # natural exposed ore at road-protection boundaries. Smooth the target field
    # itself so neighbouring protected anchors cannot retain a long vertical wall.
    t=np.full(h.shape,-32768,np.int16)
    for iz in (-1,0,1):
        for ix in (-1,0,1):
            f=d/'landscape'/f'r.{rx+ix}.{rz+iz}.npz'
            if not f.exists():continue
            xx=rx*512;zz=rz*512
            l,r=max(-HALO,512*ix),min(512+HALO,512*(ix+1))
            n,s=max(-HALO,512*iz),min(512+HALO,512*(iz+1))
            t[n+HALO:s+HALO,l+HALO:r+HALO]=np.load(f)['target'][n-512*iz:s-512*iz,l-512*ix:r-512*ix]
    dry=k==3
    bad=np.zeros(h.shape,bool)
    for ax in (0,1):
        pair=dry&np.roll(dry,-1,ax)
        adj=(have!=np.roll(have,-1,ax))&pair
        # Target steps which the first pass intentionally retained beside an
        # obstacle still need a continuous shoulder on the other side.
        abrupt=(np.abs(t.astype(int)-np.roll(t,-1,ax))>=4)
        face=adj&abrupt
        bad|=face|np.roll(face,1,ax)
    if bad.any() and (rx,rz) not in EXCLUDED:
        wt=nd.gaussian_filter(dry.astype('f'),12)
        grade=nd.gaussian_filter(np.where(dry,t,0).astype('f'),12)/np.maximum(wt,.0001)
        dist=nd.distance_transform_edt(~bad)
        keep=nd.distance_transform_edt((k!=0)&(k!=5))
        blend=smooth(1-dist/44)*smooth(keep/3)*dry
        # Where water is immediately next to the failure, the bank has to descend
        # to the fixed water datum; leave the water and the dry bank foot in place.
        if (k==4).any():
            wd,(j,i)=nd.distance_transform_edt(k!=4,return_indices=True)
            bank=np.clip(grade,h[j,i]+1,h[j,i]+1+.76*wd)
            bank=np.where((np.abs(h.astype(int)-h[j,i])<=2)&(wd<2.1),h,bank)
            grade+=smooth(1-wd/50)*(bank-grade)
        gz,gx=np.ogrid[z0:z0+h.shape[0],x0:x0+h.shape[1]]
        mountain=np.hypot(np.maximum(0,np.maximum(-1343-gx,gx+1129)),np.maximum(0,np.maximum(-1452-gz,gz+1332)))
        blend*=smooth((mountain-32)/24)
        result=np.rint(t+blend*(grade-t)).astype(np.int16)[AREA]
    else:result=t[AREA]
    dest=d/'final-plan'/f'r.{rx}.{rz}.npz'
    np.savez_compressed(dest,h=old['h'],target=result,forest=old['forest'],faces=old['faces'])
    return rx,rz,int((result!=old['target']).sum())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('work',type=Path);p.add_argument('footprint',type=Path);p.add_argument('--workers',type=int,default=6)
    a=p.parse_args();(a.work/'final-plan').mkdir(exist_ok=True)
    coords=[tuple(map(int,f.stem.split('.')[1:])) for f in (a.work/'landscape').glob('*.npz')]
    with ProcessPoolExecutor(a.workers) as pool:
        for r in pool.map(refine,[(a.work,a.footprint,*c) for c in coords]):print(r,flush=True)
