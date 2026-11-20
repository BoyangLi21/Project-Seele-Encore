"""Plan rounded ground and feathered woodland against real surfaces on both sides of old map cuts.

Raster arrays are indexed by (z,x). The halo contains the full convolution kernel.
Only measured natural dry columns are candidates. Infrastructure and water anchor the grading.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
from scipy import ndimage as nd
from survey_r64_playtest_terrain import EMPTY

HALO=160
SIZE=512+HALO*2
AREA=np.s_[HALO:-HALO,HALO:-HALO]
EXCLUDED={(-1,0),(-1,1),(0,0)}
def smooth(t):
    v=np.clip(t,0,1)
    return v*v*(3-2*v)

def window(surveys,rx,rz):
    x0,z0=rx*512-HALO,rz*512-HALO
    h=np.full((SIZE,SIZE),EMPTY,np.int16)
    k=np.zeros(h.shape,np.uint8)
    v=np.zeros(h.shape,np.uint8)
    for z in range(rz-1,rz+2):
        for x in range(rx-1,rx+2):
            f=surveys/f'r.{x}.{z}.npz'
            if not f.exists():continue
            left,right=max(x*512,x0),min((x+1)*512,x0+SIZE)
            near,far=max(z*512,z0),min((z+1)*512,z0+SIZE)
            a=np.s_[near-z0:far-z0,left-x0:right-x0]
            b=np.s_[near-z*512:far-z*512,left-x*512:right-x*512]
            with np.load(f) as data:
                h[a],k[a],v[a]=data['h'][b],data['k'][b],data['v'][b]
    return x0,z0,h,k,v

def coarse(a):
    n,m=a.shape
    return a.reshape(n//8,8,m//8,8).mean((1,3)).astype(np.float32)

def support(x0,z0,shape,footprint):
    with np.load(footprint) as data:
        base=data['a'];cx0,cz0=int(data['x0']),int(data['z0'])
    z,x=np.ogrid[z0:z0+shape[0],x0:x0+shape[1]]
    j=(z>>4)-cz0;i=(x>>4)-cx0
    have=base[np.clip(j,0,base.shape[0]-1),np.clip(i,0,base.shape[1]-1)] & (i>=0)&(j>=0)&(i<base.shape[1])&(j<base.shape[0])
    rim=(nd.maximum_filter(have.astype('B'),size=177)!=nd.minimum_filter(have.astype('B'),size=177))
    # Internal surveyed lots through Odawara and the Ministry forest tile margins.
    odawara=(x>=1700)&(x<=4600)&(z>=-1840)&(z<=1750)
    forest=((abs(x+2112)<144)|(abs(x-4511)<144)|(abs(z+1424)<144)|(abs(z-1599)<144))&(x>=-2256)&(x<=4655)&(z>=-1568)&(z<=1743)
    return rim|odawara|forest,have,rim

def landscape(x0,z0,h,k,v,footprint):
    allowed,have,rim=support(x0,z0,h.shape,footprint)
    natural=k==3
    face=np.zeros(h.shape,bool)
    for axis in (0,1):
        neighbour=np.roll(h,-1,axis)
        pair=((natural | (k==4)) & np.roll(natural | (k==4),-1,axis)) & (natural | np.roll(natural,-1,axis))
        step=np.abs(h.astype(np.int32)-neighbour)
        border=have!=np.roll(have,-1,axis)
        abrupt=(step>=2)&pair
        aligned=nd.uniform_filter1d(abrupt.astype('f'),size=13,axis=1-axis)>.54
        line=abrupt & ((border & (step>=3)) | aligned) & allowed
        face|=line|np.roll(line,1,axis)
    face[:2]=False;face[-2:]=False;face[:,:2]=False;face[:,-2:]=False
    distance=nd.distance_transform_edt(~face) if face.any() else np.full(h.shape,1000)
    # Extrapolated land supports the convolution beside roads. The actual road, shore,
    # blocks above it and foundations are held fixed, with the surrounding ground tied in.
    safety=nd.distance_transform_edt((k!=0)&(k!=5))
    base=np.where(natural,h,0).astype('f')
    numer=nd.gaussian_filter(base,15,truncate=3.5)
    denom=nd.gaussian_filter(natural.astype('f'),15,truncate=3.5)
    ridge=numer/np.maximum(denom,1e-5)
    if (k==4).any():
        water_dist,(j,i)=nd.distance_transform_edt(k!=4,return_indices=True)
        water=h[j,i]
        # Hold the shoreline at its measured datum. Cut the high land side back to
        # meet it instead of preserving tall walls beside a one-block water margin.
        bank=np.clip(ridge,water+1,water+1+water_dist*.78)
        bank=np.where((np.abs(h.astype(int)-water)<=2)&(water_dist<2.1),h,bank)
        influence=smooth(1-water_dist/72)
        ridge+=influence*(bank-ridge)
    alpha=smooth(1-distance/62)*smooth((safety-2)/11)*natural
    target=np.rint(h+alpha*(ridge-h)).astype(np.int16)
    # Canopy shoulders detected on an 8-block raster. Compare the two sides of
    # each axis over a length of 56 blocks; isolated trees do not seed a forest.
    canopy=coarse(v.astype('f'))
    dry=coarse(natural)
    cover=nd.gaussian_filter(canopy,1.25)
    seam=np.zeros(cover.shape,bool)
    for axis in (0,1):
        a=np.roll(cover,2,axis)-np.roll(cover,-2,axis)
        extent=nd.uniform_filter1d(a,size=7,axis=1-axis)
        seam|=(np.abs(extent)>.145)&(np.sign(extent)==np.sign(a))&(np.abs(a)>.10)
    seam &= coarse(allowed)>0
    seam[:4]=False;seam[-4:]=False;seam[:,:4]=False;seam[:,-4:]=False
    span=nd.distance_transform_edt(~seam)*8 if seam.any() else np.full(cover.shape,1000)
    # Local high-side cover produces a continuous density taper on the sparser side.
    nearby=nd.maximum_filter(nd.gaussian_filter(canopy,1.6),size=9)
    background=nd.gaussian_filter(canopy,5)
    desired=(.72*nearby+.28*background)*smooth(1-span/118)
    # Low-density woodland islands cross bare stretches of the old footprint as well.
    # The ridge height, local relief and overlapping long-wave fields give each island
    # its own contour, while the measured woodland dominates on a dense forest edge.
    gz,gx=np.ogrid[z0+4:z0+h.shape[0]:8,x0+4:x0+h.shape[1]:8]
    climate=.47+.21*np.sin(gx/81+gz/128)+.18*np.cos(gz/57-gx/147)+.12*np.sin(gz/169-gx/43)
    heights=coarse(np.where(natural,h,0))/np.maximum(dry,1e-4)
    height_weight=smooth((heights+64)/85)*smooth((240-heights)/75)
    relief=np.hypot(*np.gradient(nd.gaussian_filter(heights,1.5)))/8
    island=.18*smooth((climate-.28)/.52)*height_weight*smooth((1.85-relief)/1.55)
    island*=nd.gaussian_filter(coarse(rim),2.8)
    desired=np.maximum(desired,island)
    deficit=np.clip((desired-.75*cover-.018),0,.7)*np.clip(dry/.60,0,1)
    return target,alpha.astype('f'),deficit,face

def plan(job):
    surveys,footprint,out,rx,rz=job
    dest=out/f'r.{rx}.{rz}.npz'
    if dest.exists():return
    x0,z0,h,k,v=window(surveys,rx,rz)
    target,alpha,deficit,face=landscape(x0,z0,h,k,v,footprint)
    # The concurrent mountain-building repair occupies this measured footprint.
    # Leave a 32-block buffer and release the grading over another 24 blocks.
    z,x=np.ogrid[z0:z0+SIZE,x0:x0+SIZE]
    dist=np.hypot(np.maximum(0,np.maximum(-1343-x,x+1129)),np.maximum(0,np.maximum(-1452-z,z+1332)))
    weight=smooth((dist-32)/24)
    target=np.rint(h+weight*(target-h)).astype(np.int16)
    alpha*=weight
    deficit*=coarse(weight)
    if (rx,rz) in EXCLUDED:
        target=h.copy();alpha.fill(0);deficit.fill(0)
    q=HALO//8
    d=np.rint(deficit[q:-q,q:-q]*255).astype('B')
    changed=int((target[AREA]!=h[AREA]).sum())
    np.savez_compressed(dest,h=h[AREA],target=target[AREA],alpha=np.rint(alpha[AREA]*255).astype('B'),
                        forest=d,faces=face[AREA])
    return (rx,rz,changed,int((d>5).sum()))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('survey','footprint','out'):
        p.add_argument('--'+arg,type=Path,required=True)
    p.add_argument('--workers',type=int,default=4)
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    coords=[tuple(map(int,f.stem.split('.')[1:])) for f in args.survey.glob('r.*.npz')]
    coords.sort(key=lambda r:(r!=(6,-5),r))
    jobs=[(args.survey,args.footprint,args.out,*c) for c in coords]
    with ProcessPoolExecutor(args.workers) as pool:
        for i,rec in enumerate(pool.map(plan,jobs),1):
            print(i,len(jobs),rec,flush=True)
if __name__=='__main__':main()
