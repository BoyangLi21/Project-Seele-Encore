"""Prepare deterministic, soil-checked trees on the open side of measured woodland edges."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
from scipy import ndimage as nd
from query_blocks import iter_chunks,dimension_dir,decode_modern_section
from plan_r64_playtest_terrain import EXCLUDED

GROWS=set('grass_block dirt podzol coarse_dirt rooted_dirt moss_block'.split())

def shapes(species,height):
    cells={(0,y,0):0 for y in range(1,height+1)}
    for y in range(2,height+2):
        d=height-y
        if species==2:
            r=0 if d<0 else 1 if d<2 else 2 if d%2==0 else 1
        else:
            if d>2:continue
            r=1 if d== -1 else 2
        for z in range(-r,r+1):
            for x in range(-r,r+1):
                if r and x*x+z*z>r*r+1:continue
                cells.setdefault((x,y,z),1)
    return list((x,y,z,part) for (x,y,z),part in cells.items())

def surround(directory,rx,rz,key,fill,margin=12):
    center=np.load(directory/f'r.{rx}.{rz}.npz')[key]
    a=np.full((512+2*margin,512+2*margin),fill,dtype=center.dtype)
    for zj in (-1,0,1):
        for xi in (-1,0,1):
            f=directory/f'r.{rx+xi}.{rz+zj}.npz'
            if not f.exists(): continue
            w,e=max(-margin,512*xi),min(512+margin,512*(xi+1))
            n,s=max(-margin,512*zj),min(512+margin,512*(zj+1))
            b=center if xi==0 and zj==0 else np.load(f)[key]
            a[n+margin:s+margin,w+margin:e+margin]=b[n-zj*512:s-zj*512,w-xi*512:e-xi*512]
    return a

def treejob(job):
    root,survey,plan,out,rx,rz=job
    dest=out/f'r.{rx}.{rz}.npy'
    if dest.exists():return
    p=np.load(plan/f'r.{rx}.{rz}.npz');density=p['forest'];h=p['h'];target=p['target']
    m=12;result=[]
    if density.max()>0:
        k=surround(survey,rx,rz,'k',0,m);v=surround(survey,rx,rz,'v',0,m)
        space=nd.distance_transform_edt((k==3)&(v==0))[m:-m,m:-m]
        yy,xx=np.mgrid[0:512,0:512]
        terrain=surround(plan,rx,rz,'target',-32768,m).astype('f')
        smooth=nd.gaussian_filter(terrain,2)
        gradients=np.hypot(*np.gradient(smooth))[m:-m,m:-m]
        # One jittered root per six-block cell. Coordinates and species are absolute
        # so a canopy footprint crosses region borders without clipping.
        gx0,gz0=rx*512,rz*512
        za,xa=np.mgrid[gz0//6:(gz0+511)//6+1,gx0//6:(gx0+511)//6+1]
        rng=(xa.astype('uint64')*np.uint64(341873128712)^za.astype('uint64')*np.uint64(132897987541)^np.uint64(1964341))
        rng^=rng>>np.uint64(29);rng*=np.uint64(0xff51afd7ed558ccd);rng^=rng>>np.uint64(32)
        wx=xa*6+((rng>>16)%6).astype(int);wz=za*6+((rng>>24)%6).astype(int)
        use=(wx>=gx0)&(wx<gx0+512)&(wz>=gz0)&(wz<gz0+512)
        x=np.clip(wx-gx0,0,511);z=np.clip(wz-gz0,0,511)
        # Interpolate the density so the 8m survey cells do not print through.
        chance=nd.map_coordinates(density.astype('f')/255,( (z-4)/8,(x-4)/8),order=1,mode='nearest')*1.1
        use&=((rng&65535)/65536.<chance)&(space[z,x]>=5)&(gradients[z,x]<1.32)&(target[z,x]<222)
        for j,i in zip(*np.nonzero(use)):
            # If the adjacent file is reserved, hold its whole three-block margin.
            bx,bz=int(wx[j,i]),int(wz[j,i]);lz,lx=bz&511,bx&511
            if any(((bx+dx)>>9,(bz+dz)>>9) in EXCLUDED for dx in (-3,3) for dz in (-3,3)):continue
            rr=int(rng[j,i])
            species=2 if (target[lz,lx]>96 and (rr>>32)%5<3) else (1 if (rr>>35)%5<2 else 0)
            ht=(6 if species==2 else 4)+(rr>>40)%4
            result.append((bx,bz,int(h[lz,lx]),int(target[lz,lx]),species,ht))
    # Basal soil is independently measured, and rock, water or a decorative
    # foundation cannot become a trunk simply because the height is plausible.
    chunks={}
    for row in result:chunks.setdefault((row[0]>>4,row[1]>>4),[]).append(row)
    accepted=[]
    for cx,cz,c in iter_chunks(dimension_dir(root,'projectseele:geofront'),(rx*32,rx*32+31,rz*32,rz*32+31),chunks):
        parts={}
        for row in chunks[cx,cz]:parts.setdefault(row[2]>>4,[]).append(row)
        for sec in c['sections']:
            sy=int(sec['Y'])
            if sy not in parts:continue
            pal,ids=decode_modern_section(sec)
            for bx,bz,old,new,species,ht in parts[sy]:
                ind=((old&15)<<8)|((bz&15)<<4)|(bx&15)
                if str(pal[ids[ind]]['Name']).removeprefix('minecraft:') in GROWS:
                    accepted.append((bx,bz,new,species,ht))
    a=np.array(accepted,dtype=np.int32).reshape(-1,5)
    np.save(dest,a)
    return rx,rz,len(a)

def main():
    p=argparse.ArgumentParser()
    for arg in ('world','survey','plan','out'):p.add_argument('--'+arg,required=True,type=Path)
    p.add_argument('--workers',type=int,default=5)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    coord=[tuple(map(int,s.stem.split('.')[1:])) for s in a.plan.glob('*.npz')]
    coord.sort(key=lambda c:(c!=(6,-5),c))
    jobs=[(a.world,a.survey,a.plan,a.out,*c) for c in coord]
    with ProcessPoolExecutor(a.workers) as pool:
        for i,r in enumerate(pool.map(treejob,jobs),1):print(i,len(jobs),r,flush=True)
if __name__=='__main__':main()
