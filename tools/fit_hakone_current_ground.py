"""Fit the cached geography to measured, still-occupied surface components."""
import argparse,json,gzip,struct
from pathlib import Path
import numpy as np
from repair_hakone_surface_ownership import load_grid
from hakone_earthworks import grade_ground,min_slope_envelope,grade_development
from plan_ashi_landscape_r54 import NATURAL

def fit(a):
    a.out.mkdir(exist_ok=False)
    d=load_grid(a.atlas/'surface-atlas.npz');h=d['height_y'].copy();water=d['water'];owner=d['owner']
    observed=load_grid(a.candidate/'ground-anchors.npz')['height'];mask=observed!=-32768
    # Do not put the former Gora grades back over the joint interface solve.
    measured=load_grid(a.source/'measured.npz');x0,z0,_,_=measured['bounds']
    ground_now=measured['top'][np.ix_(d['z']-z0,d['x']-x0)]
    # Indoor floors and old subterranean station concourses are not surface
    # terrain anchors. Commissioned road/plot grades already own their pixels.
    mask&=(owner==0)&(np.abs(observed.astype(np.int32)-ground_now)<=5)
    # Separate soil anchors from retained three-dimensional concourses and
    # road underpasses. Those floors remain in the block patch at their exact
    # height, but cannot pull the hillside down through an upper street.
    fixed=owner>0
    rows=json.loads((a.candidate/'parcels.json').read_text('utf8'));kept={};samples={}
    regions={}
    for key,b in rows.items():
        x,y,z,X,Y,Z=b;cx,cz=(x+X)//2,(z+Z)//2
        if not(d['x'][0]<=x<=X<=d['x'][-1]and d['z'][0]<=z<=Z<=d['z'][-1]):continue
        region=cx//512,cz//512;regions.setdefault(region,[]).append((key,b))
    for (rx,rz),rs in regions.items():
        file=a.source/'source'/f'r.{rx}.{rz}.npz'
        if not file.exists():continue
        with np.load(file)as f:
            blocks=f['blocks'];coords=f['coordinates'];names=[str(s).split('[')[0]for s in f['palette']]
        foreign=np.array([s not in NATURAL for s in names]);index={tuple(p):i for i,p in enumerate(coords)}
        for key,b in rs:
            x,y,z,X,Y,Z=b;count=0
            for cx in range(x//16,X//16+1):
                for cz in range(z//16,Z//16+1):
                    if(cx,cz)not in index:continue
                    v=blocks[index[cx,cz],max(0,y+129):min(448,y+137),max(0,z-cz*16):min(16,Z-cz*16+1),max(0,x-cx*16):min(16,X-cx*16+1)]
                    count+=int(foreign[v].sum())
            if count<30:continue
            kept[key]=b;samples[key]=count
            ix=np.flatnonzero((d['x']>=x)&(d['x']<=X));iz=np.flatnonzero((d['z']>=z)&(d['z']<=Z));s=np.ix_(iz,ix)
            h[s]=y;fixed[s]=True;owner[s]=6
    # The retained corner shop was raised to the lake's new datum, but its
    # neighbouring newly-authored road still used the former grade. Regrade
    # the full nearby road width, while every occupied parcel stays in place.
    gis=a.source.parent.parent
    road=load_grid(gis/'main-district-integration-v1/coupled-grading.npz')
    sx,sz,SX,SZ=-560,816,-416,944;rx,rz,_,_=road['bounds'];sl=np.s_[sz-rz:SZ-rz+1,sx-rx:SX-rx+1]
    target=road['target'][sl].astype(float);walk=road['walk'][sl].copy();plotmask=np.zeros(target.shape,bool)
    Z,X=np.mgrid[sz:SZ+1,sx:SX+1]
    for b in kept.values():
        x,y,z,xx,Y,zz=b;m=(X>=x)&(X<=xx)&(Z>=z)&(Z<=zz);target[m]=y;plotmask|=m
    pins=plotmask|(((X==sx)|(X==SX)|(Z==sz)|(Z==SZ))&walk)
    fitted=grade_development(target*2,walk|plotmask,[],pins,slope=2,plot_quantum=2)
    soil,err=grade_ground(target,walk|plotmask,fitted/2,slope=2)
    if err.any():raise ValueError('Lake corner road/plot reconciliation failed')
    np.savez_compressed(a.out/'shore-seam.npz',bounds=[sx,sz,SX,SZ],target=soil,walk=walk,road=road['road'][sl],grade2=fitted,plots=plotmask,fixed=pins,old_target=target)
    iz,ix=np.nonzero(walk);wx=ix+sx;wz=iz+sz;even=((wx-d['x'][0])%2==0)&((wz-d['z'][0])%2==0)
    az=(wz[even]-d['z'][0])//2;ax=(wx[even]-d['x'][0])//2
    h[az,ax]=soil[iz[even],ix[even]];fixed[az,ax]=True;owner[az,ax]=7
    bank=h.copy();lake=(owner==3)&(water!=-32768);bank[lake]=water[lake]-1
    upper=min_slope_envelope(np.where(fixed,bank,np.inf),4)
    lower=-min_slope_envelope(np.where(fixed,-bank,np.inf),4)
    mask&=(observed<=upper)&(observed>=lower)
    heights=np.where(mask,observed,bank)
    combined=fixed|mask
    upper=min_slope_envelope(np.where(combined,heights,np.inf),4)
    lower=-min_slope_envelope(np.where(combined,-heights,np.inf),4)
    mask&=(observed<=upper)&(observed>=lower)
    h[mask]=observed[mask];bank[mask]=observed[mask];fixed|=mask
    inside=fixed.copy();inside[1:]&=fixed[:-1];inside[:-1]&=fixed[1:];inside[:,1:]&=fixed[:,:-1];inside[:,:-1]&=fixed[:,1:]
    ground,conflicts=grade_ground(h,fixed&~inside,bank,slope=4)
    np.savez_compressed(a.out/'design.npz',x=d['x'],z=d['z'],height=h,ground=ground,fixed=fixed,owner=owner,water=water,conflict=conflicts)
    (a.out/'retained-parcels.json').write_text(json.dumps(kept,ensure_ascii=False),'utf8')
    bad=conflicts&~fixed;zs,xs=np.nonzero(bad)
    (a.out/'conflicts.json').write_text(json.dumps([[int(d['x'][x]),int(d['z'][z])]for z,x in zip(zs,xs)]),'utf8')
    print('Actual parcels',len(kept),'unresolved soil boundary pixels',len(xs),flush=True)
    if len(xs):return
    h[~fixed]=ground[~fixed];h=np.rint(h).astype(np.int16)
    np.savez_compressed(a.out/'surface-atlas.npz',x=d['x'],z=d['z'],height_y=h,water=water,owner=owner)
    with gzip.open(a.out/'hakone_surface.bin.gz','wb',compresslevel=6)as f:
        f.write(struct.pack('>6i',0x484B3535,int(d['x'][0]),int(d['z'][0]),2,len(d['x']),len(d['z'])))
        f.write((h*16).astype('>i2').tobytes());f.write(water.astype('>i2').tobytes())

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('source','candidate','atlas','out'):p.add_argument('--'+n,type=Path,required=True)
    fit(p.parse_args())
