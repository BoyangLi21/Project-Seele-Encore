"""Read actual composed blocks across every authored street width, offline."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.ndimage import label
from author_hakone_lakefront import Editor
from repair_hakone_surface_ownership import load_grid,sampled
from query_blocks import AIR
from hakone_earthworks import road_blocks

PAVEMENT={'minecraft:black_concrete','minecraft:white_concrete','minecraft:gray_concrete','minecraft:light_gray_concrete','minecraft:smooth_stone','minecraft:smooth_stone_slab','minecraft:stone_bricks','minecraft:stone_brick_slab','minecraft:stone_brick_stairs','minecraft:deepslate_bricks','minecraft:polished_deepslate','minecraft:blackstone_slab','minecraft:yellow_concrete','minecraft:yellow_terracotta','minecraft:polished_blackstone_slab','projectseele:nerv_floor_panel','projectseele:road_asphalt_slab','projectseele:road_marking_slab'}

def run(a):
    e=Editor(a.candidate);d=load_grid(a.plan/'network.npz');errors=[];checked=0;full=np.zeros(d['walk'].shape,bool)
    grouped=0
    for file in sorted((a.candidate/'source').glob('*.npz')):
        rx,rz=map(int,file.stem.split('.')[1:]);x,z,X,Z=d['bounds']
        if rx*512>X or rx*512+511<x or rz*512>Z or rz*512+511<z:continue
        area=np.s_[max(0,rz*512-z):min(d['walk'].shape[0],rz*512+512-z),max(0,rx*512-x):min(d['walk'].shape[1],rx*512+512-x)]
        if not d['walk'][area].any():continue
        r=e.region(rx*512,rz*512);bare=[s.split('[')[0]for s in r['names']]
        paved=np.array([s in PAVEMENT for s in bare]);empty=np.array([s in AIR|{'minecraft:light','minecraft:grass','minecraft:tall_grass','minecraft:fern'}for s in bare])
        for q,v in zip(r['coords'],r['after']):
            cx,cz=map(int,q);zz,xx=np.mgrid[cz*16:cz*16+16,cx*16:cx*16+16];mask=sampled(d,'walk',xx,zz).astype(bool)
            if not mask.any():continue
            h,slab=road_blocks(sampled(d,'grade2',xx,zz));iz,ix=np.mgrid[:16,:16]
            floor=paved[v[h+128,iz,ix]];body=empty[v[h+129,iz,ix]]&empty[v[h+130,iz,ix]]
            for Z,X in np.argwhere(mask&(~floor|~body)):
                Y=int(h[Z,X]);errors.append(['actual-road-floor-or-body',int(xx[Z,X]),Y,int(zz[Z,X]),[r['names'][v[y+128,Z,X]]for y in range(Y,Y+3)]])
            for Z,X in np.argwhere(mask):full[zz[Z,X]-z,xx[Z,X]-x]=True
            checked+=int(mask.sum())
        e.regions.clear();print('Checked actual complete road widths',file.name,checked,flush=True)
    groups,n=label(d['road']|d['tunnel'],np.ones((3,3),int));sizes=np.bincount(groups.ravel());large=sorted([int(v)for v in sizes[1:]if v>=40],reverse=True)
    connectivity=json.loads((a.plan/'street-connectivity.json').read_text('utf8'))
    for row in connectivity['remaining']:errors.append(['disconnected-commissioned-street',row])
    prior=json.loads((a.candidate/'functional-check.json').read_text('utf8'))
    # Re-measure the final assembly; keep non-geometric/device failures.
    prior_errors=[r for r in prior['errors']if r[0]not in {'road-object','actual-road-floor-or-body','disconnected-commissioned-street'}]
    initial={key:prior.pop(key)for key in ('full_width_before','full_width_after')if key in prior}
    if initial:prior['initial_composition_diagnostics']=initial
    prior.update(errors=prior_errors+errors,actual_road_columns_checked=checked,not_yet_full_road_columns=int((d['walk']&~full).sum()),large_road_components=large,visual_verified=False)
    (a.candidate/'functional-check.json').write_text(json.dumps(prior,indent=2),'utf8')
    print('Actual full-width columns',checked,'errors',len(errors),'nontrivial components',large,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('candidate','plan'):p.add_argument('--'+n,type=Path,required=True)
    run(p.parse_args())
