"""Measure saved GeoFront ground, infrastructure and canopy directly from chunk sections."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from collections import Counter
import numpy as np
from scipy import ndimage
from query_blocks import iter_chunks, dimension_dir, decode_modern_section, AIR

EMPTY = -32768
SOIL = set("grass_block dirt coarse_dirt rooted_dirt podzol moss_block stone andesite diorite granite tuff gravel sand red_sand clay calcite deepslate mud snow_block".split())
PLANTS = set("grass short_grass tall_grass fern large_fern dandelion poppy oxeye_daisy azure_bluet cornflower sweet_berry_bush dead_bush peony lilac rose_bush lily_of_the_valley allium sunflower blue_orchid white_tulip red_tulip pink_tulip orange_tulip brown_mushroom red_mushroom snow vine sugar_cane hanging_roots azalea flowering_azalea moss_carpet spore_blossom".split())
WATER = set("water seagrass tall_seagrass kelp kelp_plant lily_pad ice blue_ice packed_ice".split())
def kind(name):
    if name in AIR:
        return 0
    if not name.startswith('minecraft:'):
        return 5
    short = name[10:]
    if short in PLANTS or short.endswith('_sapling'):
        return 1
    if short.endswith(('_log', '_wood', '_leaves')) or short in ('bamboo','bamboo_sapling'):
        return 2
    if short in SOIL:
        return 3
    return 4 if short in WATER else 5

def scan(job):
    world,out,rx,rz,selected=job
    dest = out / f'r.{rx}.{rz}.npz'
    if dest.exists():
        return
    ground = np.full((512,512),EMPTY,np.int16)
    kinds = np.zeros((512,512),np.uint8)
    veg = np.zeros((512,512),np.uint8)
    first = np.full((512,512),EMPTY,np.int16)
    root_y = np.full((512,512),32767,np.int16)
    statuses = Counter()
    dim = dimension_dir(world,'projectseele:geofront')
    for cx,cz,c in iter_chunks(dim,(rx*32,rx*32+31,rz*32,rz*32+31),selected):
        status=str(c['Status']).split(':')[-1]
        statuses[status]+=1
        if status!='full':
            continue
        zz,xx=(cz&31)*16,(cx&31)*16
        ix=np.s_[zz:zz+16,xx:xx+16]
        h,k,v,top=ground[ix],kinds[ix],veg[ix],first[ix]
        for sec in sorted(c['sections'],key=lambda val:-int(val['Y'])):
            base=int(sec['Y'])*16
            if base < -128 or k.all(): break
            if base > 320: continue
            palette=sec.get('block_states',{}).get('palette',[])
            cats=np.array([kind(str(p['Name'])) for p in palette],np.uint8)
            if not cats.size or not cats.any(): continue
            is_trunk=np.array([str(p['Name']).endswith(('_log','_wood')) for p in palette])
            if len(cats)==1:
                cube=np.broadcast_to(cats[0],(16,16,16))
            else:
                _,indices=decode_modern_section(sec)
                cube=cats[indices.reshape(16,16,16)]
            if is_trunk.any():
                logs=np.broadcast_to(is_trunk[0],(16,16,16)) if len(cats)==1 else is_trunk[indices.reshape(16,16,16)]
                ly=logs.argmax(axis=0)
                seen=(k==0)&logs.any(axis=0)
                root_y[ix][seen]=base+ly[seen]
            for predicate, dst in ((cube>0,top),(cube>=3,h)):
                alive=(dst==EMPTY)&predicate.any(axis=0)
                ly=15-predicate[::-1].argmax(axis=0)
                dst[alive]=(base+ly)[alive]
                if dst is h: k[alive]=np.take_along_axis(cube,ly[None],axis=0)[0][alive]
            v[:] |= ((cube==2) & ((np.arange(16)[:,None,None]+base)>h[None])).any(axis=0).astype('B')
    np.savez_compressed(dest,h=ground,k=kinds,v=veg,t=first,r=((root_y==ground+1)&(kinds==3)))
    return (rx,rz,len(selected),statuses.get('full',0))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('world','footprint','out'):
        p.add_argument('--'+arg,type=Path,required=True)
    p.add_argument('--workers',type=int,default=5)
    args=p.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    data=np.load(args.footprint)
    a=data['a']; x0,z0=int(data['x0']),int(data['z0'])
    mask=ndimage.binary_dilation(a,np.ones((3,3)),iterations=9)
    zs,xs=np.nonzero(mask)
    by={}
    for x,z in zip((xs+x0).tolist(),(zs+z0).tolist()):
        by.setdefault((x>>5,z>>5),set()).add((x,z))
    order=sorted(by,key=lambda pt:(0 if pt==(6,-5) else 1,min(abs(pt[0]-7)+abs(pt[1]+1),abs(pt[0]-6)+abs(pt[1]+5))))
    jobs=[(args.world,args.out,*key,by[key]) for key in order if not (args.out / ('r.%d.%d.npz'%key)).exists()]
    with ProcessPoolExecutor(args.workers) as workers:
        for idx,rec in enumerate(workers.map(scan,jobs),1):
            print(idx,len(jobs),rec,flush=True)
if __name__=='__main__':
    main()
